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
import hmac
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any

from edge.core.citadels import CitadelError
from edge.core.combat import CombatError
from edge.core.dev import DevPatch, DevPatchError
from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.core.engine_room import EngineRoomError
from edge.core.events import Event
from edge.core.movement import MovementError
from edge.core.rules import Command, JoinGame, SetPlayerName
from edge.engine.ticker import EngineTicker
from edge.server import session as projection
from edge.server import wire
from edge.server.accounts import AccountStore, AuthError
from edge.server.env import sysop_password as load_sysop_password
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
ERR_AUTH = -32002          # not logged in / not authorised / no seat
ERR_RATE_LIMITED = -32003  # per-connection command budget exceeded (DoS hygiene)

# Rules rejections a client is expected to hit and recover from (mirrors the bot runner's set).
_REJECTIONS = (EconomyError, MovementError, CombatError, EngineRoomError, DevPatchError, CitadelError)

# The read projections a session may call — the whitelist *is* the "one method per
# ServiceProtocol member" surface. `apply`, `haggle_quote`, and `describe_event` are handled
# specially (queue / enum / event decoding); every other read is generic: the service method
# takes `player_id` first and the JSON params as keyword arguments.
_READ_METHODS = frozenset({
    "game_view", "port_view", "current_port_view", "map_view", "computer_view", "tavern_view",
    "corp_view", "market_view", "route_view", "route_legs_view", "engine_room_view", "stardock_view",
    "territory_view", "starbase_view", "current_starbase_view", "planet_view",
    "current_planet_view", "ground_operation_view", "surface_view",
    "contact_view", "species_in_sector", "current_contact_view", "encounter_view", "leads_view",
    "messages_view", "corp_view",
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
    """One connected client: the socket, the authenticated account, and the seat it holds.

    `player_id`/`game_id` are set only by the lobby from the account↔game binding — never from
    client params — so a session can act only as the seat it was allocated (H15).
    """

    conn: Any
    account_id: int | None = None  # set on login/resume_session (identity on this connection)
    sysop_authorized: bool = False  # dedicated server secret; independent of player accounts
    game_id: int | None = None     # set on join_game/resume (which game this session is playing)
    player_id: int | None = None   # the seat in that game (from the binding, never from params)
    _hits: list[float] = field(default_factory=list)  # recent command times (rate limiter)
    # Server-pushed JSON-RPC notifications (WP65 broadcast): the fan-out enqueues, a per-connection
    # writer task drains to the socket — so a synchronous `on_events` never awaits a slow client.
    outbox: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)


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

    # --- broadcast fan-out (WP65) --------------------------------------------

    def register_session(self, session: Session) -> None:
        """Track a session so it receives this game's pushed events (the lobby calls it on join)."""
        self._sessions.add(session)

    def unregister_session(self, session: Session) -> None:
        self._sessions.discard(session)

    def _broadcast(self, appended: Any) -> None:
        """Fan freshly-persisted events to every session that should see them (the `on_events` seam).

        Called synchronously on the loop from `apply`/`apply_maintenance`, so it must not await —
        it enqueues onto each session's outbox and returns; a per-connection writer drains to the
        socket. Visibility is the same fog rule the message log uses (`event_visible_to`), so a
        pushed stream never leaks an event about a sector a player has neither entered nor charted.
        """
        state = self._service.state
        for seq, event in appended:
            encoded: Any = None  # encode lazily, at most once, only if some session wants it
            for session in self._sessions:
                if session.player_id is None:
                    continue
                if not projection.event_visible_to(state, event, session.player_id):
                    continue
                if encoded is None:
                    encoded = wire.encode_event(event)
                session.outbox.put_nowait(
                    {"jsonrpc": "2.0", "method": "event", "params": {"seq": seq, "event": encoded}})

    def events_since(self, player_id: int, since: int) -> list[dict[str, Any]]:
        """Catch-up: filtered events after `since` for a reconnecting seat (WP65).

        Re-applies the live push's fog filter over the durable rail, so a client that reconnects
        and asks for everything after its last seq gets exactly the stream it would have received
        live over that window (the catch-up == live-stream property).
        """
        state = self._service.state
        return [
            {"seq": seq, "event": wire.encode_event(event)}
            for seq, event in self._service.events_since(since)
            if projection.event_visible_to(state, event, player_id)
        ]

    async def _drain_outbox(self, session: Session) -> None:
        """Push queued notifications to one connection until the connection closes (WP65)."""
        while True:
            note = await session.outbox.get()
            await session.conn.send(json.dumps(note))

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
                if isinstance(command, SetPlayerName):
                    raise RpcError(ERR_AUTH, "player names are controlled by account identity")
                events = await self.submit(pid, command)
                return [wire.encode_event(e) for e in events]
            if method == "events_since":
                return self.events_since(pid, int(params.get("since", 0)))
            if method == "describe_event":
                return self._service.describe_event(wire.decode_event(params["event"]))
            if method == "resolve_display_id":  # no player_id (a pure spatial-id lookup)
                return self._service.resolve_display_id(int(params["shown"]))
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
        writer = asyncio.create_task(self._drain_outbox(session))  # pushed-event pump (WP65)
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
            writer.cancel()
            self._sessions.discard(session)

    def start(self) -> None:
        """Launch the command worker + ticker tasks (idempotent).

        Separated from `serve` so the multi-game `LobbyServer` can start each game's background
        tasks while owning a single websocket listener itself.
        """
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._run_worker(), name="command-worker")
        if self._ticker_task is None:
            self._ticker_task = asyncio.create_task(self._ticker.run(), name="engine-ticker")
        # Route both command- and tick-driven events to the broadcast fan-out (WP65). Set here,
        # after construction, so a bare GameService (tests, single-writer without sessions) stays
        # push-free until a server actually owns it.
        self._service.on_events = self._broadcast

    @property
    def service(self) -> GameService:
        """The wrapped game service (the lobby reads it to allocate the next seat)."""
        return self._service

    async def serve(self, host: str, port: int) -> Any:
        """Start the background tasks and the websocket listener (single-game CLI path)."""
        from websockets.asyncio.server import serve as ws_serve

        self.start()
        return await ws_serve(self._serve_connection, host, port)

    async def aclose(self) -> None:
        """Stop the ticker and worker (graceful shutdown; the WP12 rail resumes on reload)."""
        self._ticker.stop()
        for task in (self._worker_task, self._ticker_task):
            if task is not None:
                task.cancel()
        self._service.checkpoint()


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# --- lobby (auth + multi-game hosting) ---------------------------------------


class LobbyServer:
    """The multi-game front door (WP64): accounts, game creation/listing, and join/resume.

    Owns the `AccountStore` (identity, H15) and a registry of open `GameServer`s — **one
    authoritative task per open game**. Pre-auth methods (`register`, `login`) and the lobby
    methods run here; game methods (`apply`, the `*_view`s) are delegated to the bound game's
    `GameServer.dispatch`, so the single-writer discipline (H14) holds per game. A player enters
    a game only as a `player_id` allocated by a logged `JoinGame` — the §3 seam, unchanged.
    """

    def __init__(self, accounts: AccountStore, config: Any, games_dir: Path, *,
                 rate_limit: int = 50, tick_seconds: float | None = None,
                 sysop_password: str | None = None) -> None:
        self._accounts = accounts
        self._config = config
        self._games_dir = games_dir
        self._games: dict[int, GameServer] = {}
        self._rate_limit = rate_limit  # commands/second/connection — DoS hygiene, not security
        self._tick_seconds = tick_seconds
        self._sysop_password = sysop_password
        self._sessions: set[Session] = set()

    # --- game registry -------------------------------------------------------

    def _open_game(self, game_id: int) -> GameServer:
        """Return the running `GameServer` for a game, opening (loading/starting) it on first use."""
        server = self._games.get(game_id)
        if server is None:
            record = self._accounts.game(game_id)
            service = _build_game(Path(record.db_path), self._config, record.seed)
            server = GameServer(service, tick_seconds=self._tick_seconds)
            server.start()
            self._games[game_id] = server
        return server

    # --- method handlers -----------------------------------------------------

    async def dispatch(self, session: Session, method: str, params: dict[str, Any]) -> Any:
        """Route a lobby or game method, enforcing auth and the identity boundary."""
        if method == "hello":
            if params.get("fingerprint") != wire.wire_fingerprint():
                raise RpcError(ERR_HANDSHAKE, "wire fingerprint mismatch — client/server build skew")
            return {"wire_version": wire.WIRE_VERSION}
        if method == "register":
            return {"account_id": self._accounts.register(params["username"], params["password"])}
        if method == "login":
            token = self._accounts.login(params["username"], params["password"])
            session.account_id = self._accounts.authenticate(token)
            return {"token": token}
        if method == "resume_session":
            session.account_id = self._accounts.authenticate(params["token"])
            return {"account_id": session.account_id}
        if method == "sysop_login":
            supplied = str(params.get("password", ""))
            if self._sysop_password is None or not hmac.compare_digest(
                    supplied, self._sysop_password):
                raise RpcError(ERR_AUTH, "invalid sysop password")
            session.sysop_authorized = True
            return {"authorized": True}
        if method in {"sysop_open", "sysop_apply"}:
            if not session.sysop_authorized:
                raise RpcError(ERR_AUTH, "sysop authentication required")
            if method == "sysop_open":
                record = self._accounts.game_named(str(params["name"]))
                self._open_game(record.game_id)
                return {"game_id": record.game_id, "name": record.name,
                        "db_path": record.db_path}
            record = self._accounts.game_named(str(params["name"]))
            player_id = int(params["player_id"])
            command = wire.decode_command(params["command"])
            if not isinstance(command, DevPatch):
                raise RpcError(ERR_INVALID_PARAMS, "sysop_apply accepts only DevPatch commands")
            try:
                events = await self._open_game(record.game_id).submit(player_id, command)
            except _REJECTIONS as exc:
                raise RpcError(ERR_RULES_REJECTION, str(exc)) from exc
            return [wire.encode_event(event) for event in events]

        # Everything below requires a logged-in connection.
        if session.account_id is None:
            raise RpcError(ERR_AUTH, "log in before this method")

        if method == "list_games":
            return {"games": [{"game_id": g.game_id, "name": g.name} for g in self._accounts.list_games()]}
        if method == "create_game":
            if not self._accounts.is_host(session.account_id):
                raise RpcError(ERR_AUTH, "only the host may create games")
            return {"game_id": self._create_game(params["name"], int(params.get("seed", 0)))}
        if method == "join_game":
            return {"player_id": await self._join(session, int(params["game_id"]))}
        if method == "resume":
            return {"player_id": await self._resume(session, int(params["game_id"]))}

        # A game method — delegate to the bound game's single-writer server (H14).
        if session.game_id is None or session.player_id is None:
            raise RpcError(ERR_AUTH, "join or resume a game before playing")
        return await self._games[session.game_id].dispatch(session, method, params)

    def _create_game(self, name: str, seed: int) -> int:
        db_path = str(self._games_dir / f"{name}.db")
        return self._accounts.create_game(name, db_path, seed)

    async def _join(self, session: Session, game_id: int) -> int:
        """Allocate (or reuse) this account's seat in a game by appending a logged `JoinGame`.

        A returning account resumes its existing seat; a new one gets the next free `player_id`
        via a `JoinGame` command through the game's queue (the §3 seam — a new player is one more
        log entry, so the roster rebuilds under replay). The binding records account↔game↔seat.
        """
        server = self._open_game(game_id)
        username = self._accounts.username(session.account_id)  # type: ignore[arg-type]
        existing = self._accounts.binding(session.account_id, game_id)  # type: ignore[arg-type]
        if existing is not None:
            # A server interruption between lobby binding and the logged JoinGame used to
            # leave a durable seat pointing at no player. Repair that legacy/partial state
            # through the same replayable command rail before exposing the seat.
            if existing not in server.service.state.players:
                await server.submit(existing, JoinGame(name=username))
            elif server.service.state.players[existing].name != username:
                await server.submit(existing, SetPlayerName(username))
            session.game_id, session.player_id = game_id, existing
            server.register_session(session)
            return existing
        # Prefer an already-enrolled but unclaimed seat — a fresh game's `new_game` enrolls
        # player 1, and that seat belongs to the first human to join (not an orphan). Only when
        # every enrolled seat is claimed do we append a new `JoinGame` (the §3 seam).
        bound = self._accounts.bound_seats(game_id)
        free = sorted(pid for pid in server.service.state.players if pid not in bound)
        if free:
            player_id = free[0]
            if server.service.state.players[player_id].name != username:
                await server.submit(player_id, SetPlayerName(username))
        else:
            player_id = max(server.service.state.players, default=0) + 1
            await server.submit(player_id, JoinGame(name=username))
        self._accounts.bind(session.account_id, game_id, player_id)  # type: ignore[arg-type]
        session.game_id, session.player_id = game_id, player_id
        server.register_session(session)  # start receiving this game's broadcasts (WP65)
        return player_id

    async def _resume(self, session: Session, game_id: int) -> int:
        """Re-bind an existing seat, repairing a stale binding through `JoinGame`."""
        server = self._open_game(game_id)
        username = self._accounts.username(session.account_id)  # type: ignore[arg-type]
        existing = self._accounts.binding(session.account_id, game_id)  # type: ignore[arg-type]
        if existing is None:
            raise RpcError(ERR_AUTH, "no seat in that game — join it first")
        if existing not in server.service.state.players:
            await server.submit(existing, JoinGame(name=username))
        elif server.service.state.players[existing].name != username:
            await server.submit(existing, SetPlayerName(username))
        session.game_id, session.player_id = game_id, existing
        server.register_session(session)  # resume receiving this game's broadcasts (WP65)
        return existing

    # --- connection loop -----------------------------------------------------

    def _rate_ok(self, session: Session) -> bool:
        """Token-bucket over a 1-second window: reject a connection flooding the loop (hygiene)."""
        now = time.monotonic()
        session._hits[:] = [t for t in session._hits if now - t < 1.0]
        if len(session._hits) >= self._rate_limit:
            return False
        session._hits.append(now)
        return True

    async def _handle(self, session: Session, request: dict[str, Any]) -> dict[str, Any] | None:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return _error(req_id, ERR_INVALID_REQUEST, "not a JSON-RPC 2.0 request")
        if not self._rate_ok(session):
            return _error(req_id, ERR_RATE_LIMITED, "rate limit exceeded — slow down")
        try:
            result = await self.dispatch(session, method, params)
        except RpcError as exc:
            return _error(req_id, exc.code, exc.message)
        except AuthError as exc:
            return _error(req_id, ERR_AUTH, str(exc))
        except KeyError as exc:
            return _error(req_id, ERR_INVALID_PARAMS, f"missing parameter {exc}")
        if req_id is None:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    async def _serve_connection(self, conn: Any) -> None:
        session = Session(conn=conn)
        self._sessions.add(session)
        writer = asyncio.create_task(self._drain_outbox(session))  # pushed-event pump (WP65)
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
            writer.cancel()
            self._sessions.discard(session)
            if session.game_id is not None and session.game_id in self._games:
                self._games[session.game_id].unregister_session(session)

    @staticmethod
    async def _drain_outbox(session: Session) -> None:
        """Push a lobby connection's queued game notifications to its socket (WP65)."""
        while True:
            note = await session.outbox.get()
            await session.conn.send(json.dumps(note))

    async def serve(self, host: str, port: int) -> Any:
        from websockets.asyncio.server import serve as ws_serve

        return await ws_serve(self._serve_connection, host, port)

    async def aclose(self) -> None:
        for server in self._games.values():
            await server.aclose()
        self._accounts.close()


# --- CLI ----------------------------------------------------------------------


def _build_game(db: Path, config: Any, seed: int) -> GameService:
    """Load the game at `db` if it exists, else generate a fresh one there (WP12 resume).

    Existence is checked *before* opening the repository — a `SqliteRepository` creates the file
    on connect, so a fresh game would otherwise look like an empty save.
    """
    from edge.store.repo import SqliteRepository

    existed = db.exists()
    repo = SqliteRepository(db)
    if existed:
        return GameService.load_game(config, repo)
    return GameService.new_game(config, seed, repo)


async def _amain(args: argparse.Namespace) -> None:
    from edge.config import load_default_config

    config = load_default_config()
    if args.accounts:  # lobby mode: accounts + multi-game hosting (WP64)
        accounts_path = Path(args.accounts)
        accounts_path.parent.mkdir(parents=True, exist_ok=True)
        games_dir = Path(args.games_dir)
        games_dir.mkdir(parents=True, exist_ok=True)
        server: GameServer | LobbyServer = LobbyServer(
            AccountStore(accounts_path), config, games_dir,
            sysop_password=args.sysop_password)
        ws_server = await server.serve(args.host, args.port)
        log.info("edge-server lobby on ws://%s:%d (accounts=%s)",
                 args.host, args.port, accounts_path)
    else:  # single-game dev path (WP63): insecure seat, no accounts
        server = GameServer(_build_game(Path(args.game), config, args.seed),
                            insecure_player=args.insecure_player)
        ws_server = await server.serve(args.host, args.port)
        log.info("edge-server listening on ws://%s:%d (game=%s)", args.host, args.port, args.game)
    try:
        await ws_server.serve_forever()
    finally:
        await server.aclose()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse server launch settings, including default storage and operator-secret sources."""
    parser = argparse.ArgumentParser(prog="edge-server", description="Host an Edge game over websockets.")
    server_dir = Path.home() / ".edge" / "server"
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--game", help="single-game dev mode: path to the game .db")
    mode.add_argument("--accounts", help="lobby accounts DB (default ~/.edge/server/accounts.db)")
    parser.add_argument("--games-dir", default=str(server_dir / "games"),
                        help="lobby game DB directory (default ~/.edge/server/games)")
    parser.add_argument("--sysop-password",
                        help="operator secret (default $EDGE_SYSOP_PASSWORD, then ./.env)")
    parser.add_argument("--env-file", type=Path,
                        help="dotenv file for EDGE_SYSOP_PASSWORD (default: ./.env)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=0, help="seed for a fresh single-game")
    parser.add_argument("--insecure-player", type=int, default=1,
                        help="single-game dev: seat every hello binds to (lobby mode uses tokens)")
    args = parser.parse_args(argv)
    if not args.accounts and not args.game:
        args.accounts = str(server_dir / "accounts.db")
    if args.accounts:
        args.sysop_password = load_sysop_password(
            args.sysop_password, dotenv_path=args.env_file,
        )
        if not args.sysop_password:
            parser.error("set --sysop-password, export EDGE_SYSOP_PASSWORD, or put "
                         "EDGE_SYSOP_PASSWORD in ./.env (or pass --env-file)")
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_amain(_parse_args()))


if __name__ == "__main__":  # pragma: no cover
    main()
