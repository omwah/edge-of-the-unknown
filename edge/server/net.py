"""`edge/server/net.py` — the websocket JSON-RPC game server (WP63, H14).

DESIGN §3/§14/§15. This is the Phase-4 transport and **nothing else** — it contains zero game
rules (H14). The whole design is one discipline: **a single authoritative task owns the
`GameService` and its `EngineTicker`, and every session's command is marshalled through one
`asyncio.Queue`** so commands apply in strict arrival order (the total order the replay contract
requires). Projections are pure reads of already-settled state, called directly on the same
event loop between applies; there are **no locks** because core is synchronous — an `apply` or a
ticker `step` runs to completion without an `await`, so no two mutations can interleave on the
loop.

Protocol: JSON-RPC 2.0. A connection first sends `hello` (fingerprint handshake + the seat it is
authenticated to hold — a dev `--insecure-player` id until WP64's tokens); thereafter one method
per `ServiceProtocol` member, with wire-codec (`server.wire`) payloads. Identity is enforced at
this boundary, not in core: params never carry a `player_id`, so a session can only ever act as
the seat bound at `hello` — the fog-of-war rule's write-side twin (H15). Rules rejections map to
a stable error code carrying the reducer's message (a rejection is gameplay, not a fault);
anything else is logged and masked as an internal error.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from edge.core.citadels import CitadelError
from edge.core.combat import CombatError
from edge.core.dev import DevPatchError
from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.core.engine_room import EngineRoomError
from edge.core.events import Event
from edge.core.movement import MovementError
from edge.core.rules import Command
from edge.engine.ticker import EngineTicker
from edge.server import wire
from edge.server.service import GameService

log = logging.getLogger("edge.server.net")

# JSON-RPC error codes (2.0 reserves -32768..-32000). A rules rejection is expected gameplay,
# not a fault, so it gets its own application code above the reserved band's edge.
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603
ERR_RULES_REJECTION = -32000
ERR_HANDSHAKE = -32001

# Rules rejections a client is expected to hit and recover from (mirrors the bot runner's set).
_REJECTIONS = (EconomyError, MovementError, CombatError, EngineRoomError, DevPatchError, CitadelError)

# The read projections a session may call — the whitelist *is* the "one method per
# ServiceProtocol member" surface. `apply`, `haggle_quote`, and `describe_event` are handled
# specially (queue / enum / event decoding); every other read is generic: the service method
# takes `player_id` first and the JSON params as keyword arguments.
_READ_METHODS = frozenset({
    "game_view", "port_view", "current_port_view", "map_view", "computer_view", "tavern_view",
    "market_view", "route_view", "route_legs_view", "engine_room_view", "stardock_view",
    "starbase_services_view", "planet_view", "current_planet_view", "surface_view",
    "contact_view", "species_in_sector", "current_contact_view", "encounter_view", "leads_view",
    "messages_view", "resolve_display_id",
})


class RpcError(Exception):
    """A JSON-RPC error to return to the caller (code + message)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _encode_any(value: Any) -> Any:
    """Wire-encode any service return value (events, DTOs, primitives, and lists thereof)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Event):
        return wire.encode_event(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return wire.encode_dto(value)
    if isinstance(value, (list, tuple)):
        return [_encode_any(v) for v in value]
    raise RpcError(ERR_INTERNAL, f"cannot wire-encode result of type {type(value).__name__!r}")


@dataclass(eq=False)  # identity-hashed: one live connection, tracked in the sessions set
class Session:
    """One connected client: the socket and the single seat it is bound to (None until hello)."""

    conn: Any
    player_id: int | None = None


@dataclass
class _QueuedCommand:
    player_id: int
    command: Command
    future: asyncio.Future[tuple[Event, ...]]


class GameServer:
    """Owns one hosted game: the service, the ticker, the single command queue, and sessions.

    Constructed around an already-built `GameService` (new or loaded). `serve()` starts the
    ticker task, the single command worker, and the websocket listener; all three run on one
    event loop, so the synchronous core is never re-entered concurrently (H14).
    """

    def __init__(self, service: GameService, *, tick_seconds: float | None = None,
                 insecure_player: int = 1) -> None:
        self._service = service
        self._ticker = EngineTicker(service, tick_seconds=tick_seconds)
        self._queue: asyncio.Queue[_QueuedCommand] = asyncio.Queue()
        self._sessions: set[Session] = set()
        # Dev identity until WP64: every connection that says hello is bound to this seat. WP64
        # replaces this with a token→player_id lookup; the enforcement point does not move.
        self._insecure_player = insecure_player
        self._worker_task: asyncio.Task[None] | None = None
        self._ticker_task: asyncio.Task[None] | None = None

    # --- the single-writer command path (H14) --------------------------------

    async def submit(self, player_id: int, command: Command) -> tuple[Event, ...]:
        """Enqueue a command and await its events — the one path that mutates state.

        All callers share one queue, so commands apply in strict enqueue (arrival) order — the
        precondition the replay contract needs (a hosted game rebuilds to the same hash as its
        command log because that log *is* the arrival order).
        """
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[tuple[Event, ...]] = loop.create_future()
        await self._queue.put(_QueuedCommand(player_id, command, fut))
        return await fut

    async def _run_worker(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                events = self._service.apply(item.player_id, item.command)
                if not item.future.cancelled():
                    item.future.set_result(events)
            except Exception as exc:  # noqa: BLE001 — surfaced to the caller as an RPC error
                if not item.future.cancelled():
                    item.future.set_exception(exc)

    # --- request dispatch (transport only, no rules) -------------------------

    async def dispatch(self, session: Session, method: str, params: dict[str, Any]) -> Any:
        """Route one JSON-RPC method to the service and wire-encode its result.

        Raises `RpcError` for a rules rejection (stable code + reducer message) or an unknown
        method; the connection handler turns it into a JSON-RPC error object.
        """
        if session.player_id is None:
            raise RpcError(ERR_HANDSHAKE, "send hello before any other method")
        pid = session.player_id
        try:
            if method == "apply":
                command = wire.decode_command(params["command"])
                events = await self.submit(pid, command)
                return [wire.encode_event(e) for e in events]
            if method == "describe_event":
                return self._service.describe_event(wire.decode_event(params["event"]))
            if method == "haggle_quote":
                quote = self._service.haggle_quote(
                    pid, Commodity(params["commodity"]), params["counter_price"])
                return _encode_any(quote)
            if method in _READ_METHODS:
                fn = getattr(self._service, method)
                return _encode_any(fn(pid, **params))
        except _REJECTIONS as exc:
            raise RpcError(ERR_RULES_REJECTION, str(exc)) from exc
        except RpcError:
            raise
        except KeyError as exc:
            raise RpcError(ERR_INVALID_PARAMS, f"missing parameter {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            log.exception("internal error handling %s", method)
            raise RpcError(ERR_INTERNAL, "internal server error") from exc
        raise RpcError(ERR_METHOD_NOT_FOUND, f"unknown method {method!r}")

    def _hello(self, session: Session, params: dict[str, Any]) -> dict[str, Any]:
        """The handshake: refuse a mismatched build, bind the session's seat (dev seat for now)."""
        if params.get("fingerprint") != wire.wire_fingerprint():
            raise RpcError(ERR_HANDSHAKE, "wire fingerprint mismatch — client/server build skew")
        # Insecure dev binding: honour a requested seat if given, else the server default. WP64
        # swaps this for a token lookup — the identity check stays right here at the boundary.
        session.player_id = int(params.get("player_id", self._insecure_player))
        return {"player_id": session.player_id, "wire_version": wire.WIRE_VERSION}

    async def _handle(self, session: Session, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one parsed JSON-RPC request; return a response dict (None for a notification)."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return _error(req_id, ERR_INVALID_REQUEST, "not a JSON-RPC 2.0 request")
        try:
            result = self._hello(session, params) if method == "hello" \
                else await self.dispatch(session, method, params)
        except RpcError as exc:
            return _error(req_id, exc.code, exc.message)
        if req_id is None:
            return None  # a notification expects no response
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    async def _serve_connection(self, conn: Any) -> None:
        session = Session(conn=conn)
        self._sessions.add(session)
        try:
            async for raw in conn:
                try:
                    request = json.loads(raw)
                except json.JSONDecodeError:
                    await conn.send(json.dumps(_error(None, ERR_PARSE, "invalid JSON")))
                    continue
                response = await self._handle(session, request)
                if response is not None:
                    await conn.send(json.dumps(response))
        finally:
            self._sessions.discard(session)

    async def serve(self, host: str, port: int) -> Any:
        """Start the ticker, the command worker, and the websocket listener (returns the server)."""
        from websockets.asyncio.server import serve as ws_serve

        self._worker_task = asyncio.create_task(self._run_worker(), name="command-worker")
        self._ticker_task = asyncio.create_task(self._ticker.run(), name="engine-ticker")
        return await ws_serve(self._serve_connection, host, port)

    async def aclose(self) -> None:
        """Stop the ticker and worker (graceful shutdown; the WP12 rail resumes on reload)."""
        self._ticker.stop()
        for task in (self._worker_task, self._ticker_task):
            if task is not None:
                task.cancel()


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# --- CLI ----------------------------------------------------------------------


def _build_game(db: Path, config: Any, seed: int) -> GameService:
    """Load the game at `db` if it exists, else generate a fresh one there (WP12 resume)."""
    from edge.store.repo import SqliteRepository

    repo = SqliteRepository(db)
    if db.exists():
        return GameService.load_game(config, repo)
    return GameService.new_game(config, seed, repo)


async def _amain(args: argparse.Namespace) -> None:
    from edge.config import load_default_config

    config = load_default_config()
    server = GameServer(_build_game(Path(args.game), config, args.seed),
                        insecure_player=args.insecure_player)
    ws_server = await server.serve(args.host, args.port)
    log.info("edge-server listening on ws://%s:%d (game=%s)", args.host, args.port, args.game)
    try:
        await ws_server.serve_forever()
    finally:
        await server.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="edge-server", description="Host an Edge game over websockets.")
    parser.add_argument("--game", required=True, help="path to the game .db (created if absent)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=0, help="seed for a fresh game")
    parser.add_argument("--insecure-player", type=int, default=1,
                        help="dev: seat every hello binds to (replaced by auth tokens in WP64)")
    asyncio.run(_amain(parser.parse_args()))


if __name__ == "__main__":  # pragma: no cover
    main()
