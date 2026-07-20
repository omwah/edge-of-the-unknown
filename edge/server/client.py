"""`GameClient` — the async client seam that unhooks the TUI from the in-process service (WP61).

DESIGN §3/§14. Phase 4 needs the TUI (and bots, and the sysop console) to talk to a game
that may live *in another process*. `ServiceProtocol` (WP60, H16) is the synchronous surface of
the in-process `GameService`; `GameClient` is its **async twin** — the same method names and
shapes, every one a coroutine, so a caller written against it works identically whether the game
is embedded (`LocalClient`) or remote over a socket (`RemoteClient`, WP68). This is the single
refactor that lets a remote client be a drop-in without rewriting the TUI twice.

Two design points the plan pins (H14/H16):

- **`LocalClient` wraps the in-process `GameService` with trivial pass-through.** Core is pure
  and fast, so there is no executor and no thread — a `LocalClient.apply` just calls the
  synchronous service and returns. The `async def` is the *interface contract*, not a promise
  of off-loop work.
- **Whoever owns the service owns the ticker.** `LocalClient` constructs and runs the embedded
  `EngineTicker` (the server owns it for remote games, WP63), so the TUI never thinks about
  ticking — it just starts the client's ticker worker and forgets it. `EdgeApp.player_id`
  becomes a constructor argument fed by the client (framing correction 6).

The `events` async iterator is the **broadcast seam**: single-player synthesizes it from the
events an `apply` returns (there is no second command source), and WP65 makes it a real
server-pushed stream for the remote case. It is stubbed but present so the TUI can consume one
stream in both modes.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast, runtime_checkable

from edge.core import dto
from edge.core.citadels import CitadelError
from edge.core.combat import CombatError
from edge.core.config import GameConfig
from edge.core.dev import DevPatch, DevPatchError
from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.core.engine_room import EngineRoomError
from edge.core.events import Event
from edge.core.models import UniverseState
from edge.core.movement import MovementError
from edge.core.rules import Command
from edge.engine.ticker import EngineTicker
from edge.server import session, wire
from edge.server.service import GameService


T = TypeVar("T")


@runtime_checkable
class GameClient(Protocol):
    """The async surface every game consumer programs against (WP61).

    Mirrors `ServiceProtocol` (WP60) method-for-method, but each is a coroutine so the same
    call site serves an embedded (`LocalClient`) or a networked (`RemoteClient`) game. The
    trusted `state`/`config` accessors stay synchronous properties — they are dev/test/engine
    reads of already-settled state, never part of the request/response wire.
    """

    player_id: int

    # --- the single mutator --------------------------------------------------
    async def apply(self, command: Command) -> tuple[Event, ...]: ...

    # --- the broadcast stream (WP65 makes it server-pushed) ------------------
    def events(self) -> AsyncIterator[Event]: ...

    # --- read-only fog-of-war projections ------------------------------------
    async def game_view(self) -> dto.GameState: ...
    async def port_view(self, port_id: int) -> dto.PortDTO: ...
    async def current_port_view(self) -> dto.PortDTO | None: ...
    async def haggle_quote(self, commodity: Commodity, counter_price: int) -> dto.HaggleQuote: ...
    async def map_view(self, *, route_dest: int | None = ..., full_graph: bool = ...,
                       fit_width: int | None = ...) -> dto.LocalMapDTO: ...
    async def computer_view(self) -> dto.ComputerDTO: ...
    async def tavern_view(self) -> dto.TavernDTO: ...
    async def corp_view(self) -> dto.CorpDTO | None: ...
    async def market_view(self) -> dto.MarketDTO: ...
    async def route_view(self, dst_sector: int, *, full_graph: bool = ...) -> dto.RouteDTO: ...
    async def route_legs_view(self, waypoints: list[int]) -> dto.RouteDTO: ...
    async def engine_room_view(self) -> dto.EngineRoomDTO: ...
    async def stardock_view(self) -> dto.StardockDTO: ...
    async def territory_view(self) -> dto.TerritoryDTO: ...
    async def starbase_view(self, starbase_id: int) -> dto.StarbaseDTO: ...
    async def current_starbase_view(self) -> dto.StarbaseDTO | None: ...
    async def planet_view(self, planet_id: int) -> dto.PlanetDTO: ...
    async def current_planet_view(self) -> dto.PlanetDTO | None: ...
    async def ground_operation_view(
        self, *, viewport_x: int = ..., viewport_y: int = ...,
        viewport_width: int | None = ..., viewport_height: int | None = ...,
    ) -> dto.SurveyExpeditionDTO | None: ...
    async def surface_view(self, planet_id: int) -> dto.SurfaceDTO: ...
    async def contact_view(self, species_id: int, active_context: str = ...,
                           active_subject: int | None = ...) -> dto.ContactDTO: ...
    async def species_in_sector(self) -> int | None: ...
    async def current_contact_view(self) -> dto.ContactDTO | None: ...
    async def encounter_view(self) -> dto.EncounterDTO | None: ...
    async def leads_view(self) -> list[dto.LeadDTO]: ...
    async def messages_view(self) -> dto.MessagesDTO: ...

    # --- display helpers -----------------------------------------------------
    async def describe_event(self, event: Event) -> str: ...
    async def resolve_display_id(self, shown: int) -> int | None: ...

    # --- trusted accessors (dev tooling / bots / engine read raw state) ------
    @property
    def state(self) -> UniverseState: ...
    @property
    def config(self) -> GameConfig: ...


class LocalClient:
    """An embedded `GameClient` over an in-process `GameService` (WP61).

    Every method is a thin, synchronous pass-through wrapped in `async def`: core is pure and
    fast, so there is nothing to await — the coroutine *is* the seam a `RemoteClient` fills with
    a real round-trip. The client owns the embedded `EngineTicker` (the server owns it for
    remote games), so the TUI starts `run_ticker()` as a worker and never thinks about ticking
    again. Its `player_id` is the single seat this client acts as (hardcoded 1 in single-player,
    allocated per-account in multiplayer).
    """

    def __init__(self, service: GameService, player_id: int = 1) -> None:
        self._service = service
        self.player_id = player_id
        self._ticker = EngineTicker(service)
        # The broadcast stream (WP65): the service pushes every persisted event here — from an
        # `apply` *and* from a ticker `apply_maintenance` — so one consumer (the TUI ticker)
        # drains command- and time-driven events on a single channel, exactly as a `RemoteClient`
        # drains the server's pushed notifications. Fog-filtered to this seat, so a future
        # second local seat would only see what it should. Unbounded is fine: a single consumer
        # keeps pace and nothing blocks on a full queue.
        self._events: asyncio.Queue[Event] = asyncio.Queue()
        self._service.on_events = self._on_service_events

    def _on_service_events(self, appended: Sequence[tuple[int, Event]]) -> None:
        """Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam)."""
        for _seq, event in appended:
            if session.event_visible_to(self._service.state, event, self.player_id):
                self._events.put_nowait(event)

    # --- the single mutator --------------------------------------------------

    async def apply(self, command: Command) -> tuple[Event, ...]:
        """Apply a command through the in-process service (events fan out via `on_events`)."""
        return self._service.apply(self.player_id, command)

    # --- the broadcast stream ------------------------------------------------

    async def events(self) -> AsyncIterator[Event]:
        """Yield events as they are produced — the service pushes both apply + tick events."""
        while True:
            yield await self._events.get()

    # --- ticker ownership (the TUI starts this and forgets it) ---------------

    async def run_ticker(self) -> None:
        """Run the embedded engine ticker until stopped (the app's engine worker, §3)."""
        await self._ticker.run()

    def stop_ticker(self) -> None:
        self._ticker.stop()

    @property
    def ticker(self) -> EngineTicker:
        """The embedded ticker (tests/shots that step it directly)."""
        return self._ticker

    @property
    def service(self) -> GameService:
        """The wrapped in-process service (single-player back-compat; never used for remote)."""
        return self._service

    # --- read-only fog-of-war projections ------------------------------------

    async def game_view(self) -> dto.GameState:
        return self._service.game_view(self.player_id)

    async def port_view(self, port_id: int) -> dto.PortDTO:
        return self._service.port_view(self.player_id, port_id)

    async def current_port_view(self) -> dto.PortDTO | None:
        return self._service.current_port_view(self.player_id)

    async def haggle_quote(self, commodity: Commodity, counter_price: int) -> dto.HaggleQuote:
        return self._service.haggle_quote(self.player_id, commodity, counter_price)

    async def map_view(self, *, route_dest: int | None = None, full_graph: bool = False,
                       fit_width: int | None = None) -> dto.LocalMapDTO:
        return self._service.map_view(self.player_id, route_dest=route_dest,
                                      full_graph=full_graph, fit_width=fit_width)

    async def computer_view(self) -> dto.ComputerDTO:
        return self._service.computer_view(self.player_id)

    async def tavern_view(self) -> dto.TavernDTO:
        return self._service.tavern_view(self.player_id)

    async def corp_view(self) -> dto.CorpDTO | None:
        return self._service.corp_view(self.player_id)

    async def market_view(self) -> dto.MarketDTO:
        return self._service.market_view(self.player_id)

    async def route_view(self, dst_sector: int, *, full_graph: bool = False) -> dto.RouteDTO:
        return self._service.route_view(self.player_id, dst_sector, full_graph=full_graph)

    async def route_legs_view(self, waypoints: list[int]) -> dto.RouteDTO:
        return self._service.route_legs_view(self.player_id, waypoints)

    async def engine_room_view(self) -> dto.EngineRoomDTO:
        return self._service.engine_room_view(self.player_id)

    async def stardock_view(self) -> dto.StardockDTO:
        return self._service.stardock_view(self.player_id)

    async def territory_view(self) -> dto.TerritoryDTO:
        return self._service.territory_view(self.player_id)

    async def starbase_view(self, starbase_id: int) -> dto.StarbaseDTO:
        return self._service.starbase_view(self.player_id, starbase_id)

    async def current_starbase_view(self) -> dto.StarbaseDTO | None:
        return self._service.current_starbase_view(self.player_id)

    async def planet_view(self, planet_id: int) -> dto.PlanetDTO:
        return self._service.planet_view(self.player_id, planet_id)

    async def current_planet_view(self) -> dto.PlanetDTO | None:
        return self._service.current_planet_view(self.player_id)

    async def ground_operation_view(
        self, *, viewport_x: int = 0, viewport_y: int = 0,
        viewport_width: int | None = None, viewport_height: int | None = None,
    ) -> dto.SurveyExpeditionDTO | None:
        return self._service.ground_operation_view(
            self.player_id, viewport_x=viewport_x, viewport_y=viewport_y,
            viewport_width=viewport_width, viewport_height=viewport_height,
        )

    async def surface_view(self, planet_id: int) -> dto.SurfaceDTO:
        return self._service.surface_view(self.player_id, planet_id)

    async def contact_view(self, species_id: int, active_context: str = "greeting",
                           active_subject: int | None = None) -> dto.ContactDTO:
        return self._service.contact_view(self.player_id, species_id, active_context, active_subject)

    async def species_in_sector(self) -> int | None:
        return self._service.species_in_sector(self.player_id)

    async def current_contact_view(self) -> dto.ContactDTO | None:
        return self._service.current_contact_view(self.player_id)

    async def encounter_view(self) -> dto.EncounterDTO | None:
        return self._service.encounter_view(self.player_id)

    async def leads_view(self) -> list[dto.LeadDTO]:
        return self._service.leads_view(self.player_id)

    async def messages_view(self) -> dto.MessagesDTO:
        return self._service.messages_view(self.player_id)

    # --- display helpers -----------------------------------------------------

    async def describe_event(self, event: Event) -> str:
        return self._service.describe_event(event)

    async def resolve_display_id(self, shown: int) -> int | None:
        return self._service.resolve_display_id(shown)

    # --- trusted accessors ---------------------------------------------------

    @property
    def state(self) -> UniverseState:
        return self._service.state

    @property
    def config(self) -> GameConfig:
        return self._service.config


if TYPE_CHECKING:  # static conformance: mypy fails if LocalClient drifts from the async protocol.
    def _assert_impl(client: LocalClient) -> GameClient:
        return client


# --- remote client (WP68) -----------------------------------------------------


class RemoteError(Exception):
    """A JSON-RPC error returned by the server (a rules rejection or a transport fault)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RemoteRulesError(
    RemoteError,
    EconomyError,
    MovementError,
    CombatError,
    EngineRoomError,
    DevPatchError,
    CitadelError,
):
    """A remote rules rejection compatible with every local rule-error catch.

    JSON-RPC deliberately exposes one stable rules-rejection code rather than the server's
    Python exception type.  The synchronous TUI already catches the relevant local domain
    errors and turns them into warning notifications, so this bridge exception belongs to all
    of those marker families.  Hosted and embedded play therefore reject commands observably
    alike without coupling the wire contract to Python class names.
    """


class LinkLost(RemoteError):
    """The websocket dropped mid-call — surfaced to the TUI as a retryable status, not a crash."""

    def __init__(self, message: str = "link lost") -> None:
        super().__init__(-1, message)


def _decode_any(value: Any) -> Any:
    """Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists (WP68).

    The server returns None/primitives as-is, dataclasses as `{"kind":"dto",…}`, events as
    `{"kind":"event",…}`, and lists of these; this rebuilds the real objects the caller expects.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_decode_any(v) for v in value]
    if isinstance(value, dict) and value.get("kind") == "dto":
        return wire.decode_dto(value)
    if isinstance(value, dict) and value.get("kind") == "event":
        return wire.decode_event(value)
    return value


class RemoteClient:
    """A `GameClient` over a websocket to `edge-server` (WP68) — the hosted-play seam.

    Implements the WP61 async protocol against a remote authoritative game: every mutator/reader
    round-trips as a JSON-RPC call (wire codec both ways, correlated by request id), the
    server-pushed `event` notifications feed `events()`, and identity/ticking live on the server.
    A dropped socket surfaces as `LinkLost` (the TUI shows "link lost — retrying") rather than a
    crash; `reconnect()` re-auths, re-binds the seat, and replays missed events via `events_since`
    — the durable rail as the catch-up buffer (H16). No optimistic prediction: commands
    round-trip and views re-read (correctness over snappiness at LAN scales, §2).
    """

    def __init__(self, url: str, *, player_id: int = 1) -> None:
        self.player_id = player_id
        self._url = url
        self._conn: Any = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._events: asyncio.Queue[Event] = asyncio.Queue()
        self._reader: asyncio.Task[None] | None = None
        self._last_seq = 0
        self._status = "disconnected"
        # Lobby state so a reconnect can re-establish the same seat without user input.
        self._token: str | None = None
        self._game_id: int | None = None
        # A locally-loaded config for pure rendering (static shared file, not per-game state —
        # never sent over the wire; the server uses the same `load_default_config()`).
        self._config: GameConfig | None = None

    # --- connection lifecycle ------------------------------------------------

    async def connect(self, *, fingerprint: str | None = None) -> None:
        """Open the socket and complete the fingerprint handshake (refuses a build mismatch).

        `fingerprint` overrides the sent value (tests drive a mismatch); production sends this
        build's real fingerprint, so a client/server skew is refused cleanly at `hello`.
        """
        from websockets.asyncio.client import connect as ws_connect

        self._conn = await ws_connect(self._url)
        self._reader = asyncio.create_task(self._read_loop())
        await self._call("hello", {"fingerprint": fingerprint or wire.wire_fingerprint()})
        self._status = "connected"

    async def aclose(self) -> None:
        self._status = "closed"
        if self._reader is not None:
            self._reader.cancel()
        if self._conn is not None:
            await self._conn.close()

    @property
    def status(self) -> str:
        """"connected" / "disconnected" / "closed" — the TUI status-bar link state."""
        return self._status

    async def _read_loop(self) -> None:
        """Demux the socket: pushed `event` notifications feed the stream; results resolve calls."""
        try:
            async for raw in self._conn:
                msg = json.loads(raw)
                if msg.get("method") == "event":  # a server push (no id)
                    params = msg.get("params") or {}
                    self._last_seq = max(self._last_seq, int(params.get("seq", 0)))
                    self._events.put_nowait(wire.decode_event(params["event"]))
                    continue
                fut = self._pending.pop(msg.get("id"), None)
                if fut is None or fut.done():
                    continue
                if "error" in msg:
                    err = msg["error"]
                    code = err.get("code", -1)
                    error_type = RemoteRulesError if code == -32000 else RemoteError
                    fut.set_exception(error_type(code, err.get("message", "error")))
                else:
                    fut.set_result(msg.get("result"))
        except Exception:  # noqa: BLE001 — a closed/broken socket ends the loop; fail pending calls
            pass
        finally:
            self._status = "disconnected"
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(LinkLost())
            self._pending.clear()

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        """One JSON-RPC request/response round-trip (raises `RemoteError`/`LinkLost`)."""
        if self._conn is None:
            raise LinkLost("not connected")
        rid = next(self._ids)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[rid] = fut
        try:
            await self._conn.send(json.dumps(
                {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
        except Exception as exc:  # noqa: BLE001
            self._pending.pop(rid, None)
            raise LinkLost(str(exc)) from exc
        return await fut

    # --- lobby (auth + game selection) ---------------------------------------

    async def register(self, username: str, password: str) -> int:
        return int((await self._call("register", {"username": username, "password": password}))["account_id"])

    async def login(self, username: str, password: str) -> str:
        self._token = (await self._call("login", {"username": username, "password": password}))["token"]
        return self._token

    async def list_games(self) -> list[dict[str, Any]]:
        return list((await self._call("list_games", {}))["games"])

    async def create_game(self, name: str, seed: int = 0) -> int:
        return int((await self._call("create_game", {"name": name, "seed": seed}))["game_id"])

    async def sysop_login(self, password: str) -> None:
        """Authenticate this connection with the server's dedicated operator secret."""
        await self._call("sysop_login", {"password": password})

    async def sysop_open(self, name: str) -> tuple[int, str]:
        """Select an existing hosted game by its operator-facing lobby name."""
        result = await self._call("sysop_open", {"name": name})
        return int(result["game_id"]), str(result["db_path"])

    async def sysop_apply(self, game_name: str, player_id: int,
                          patch: DevPatch) -> tuple[Event, ...]:
        """Apply one host-authorized intervention through a live game's writer queue."""
        result = await self._call("sysop_apply", {
            "name": game_name,
            "player_id": player_id,
            "command": wire.encode_command(patch),
        })
        return tuple(wire.decode_event(event) for event in result)

    async def join_game(self, game_id: int) -> int:
        """Join a game and bind this client's seat to the returned player id."""
        self._game_id = game_id
        self.player_id = int((await self._call("join_game", {"game_id": game_id}))["player_id"])
        return self.player_id

    async def reconnect(self) -> None:
        """Re-open the link, re-auth + re-bind the seat, and replay any events missed (WP68).

        The durable event rail is the catch-up buffer: after re-binding we ask for everything
        after the last seq we saw and push it onto the stream, so a blip loses no events.
        """
        await self.connect()
        if self._token is not None:
            await self._call("resume_session", {"token": self._token})
        if self._game_id is not None:
            self.player_id = int((await self._call("resume", {"game_id": self._game_id}))["player_id"])
        for record in (await self._call("events_since", {"since": self._last_seq})):
            self._last_seq = max(self._last_seq, int(record["seq"]))
            self._events.put_nowait(wire.decode_event(record["event"]))

    # --- the single mutator + broadcast stream -------------------------------

    async def apply(self, command: Command) -> tuple[Event, ...]:
        result = await self._call("apply", {"command": wire.encode_command(command)})
        return tuple(wire.decode_event(e) for e in result)

    async def events(self) -> AsyncIterator[Event]:
        while True:
            yield await self._events.get()

    # --- reads (generic round-trip through the wire codec) -------------------

    async def _read(self, method: str, **params: Any) -> T:
        return cast(T, _decode_any(await self._call(method, params)))

    async def game_view(self) -> dto.GameState:
        return await self._read("game_view")

    async def port_view(self, port_id: int) -> dto.PortDTO:
        return await self._read("port_view", port_id=port_id)

    async def current_port_view(self) -> dto.PortDTO | None:
        return await self._read("current_port_view")

    async def haggle_quote(self, commodity: Commodity, counter_price: int) -> dto.HaggleQuote:
        return await self._read("haggle_quote", commodity=commodity.value, counter_price=counter_price)

    async def map_view(self, *, route_dest: int | None = None, full_graph: bool = False,
                       fit_width: int | None = None) -> dto.LocalMapDTO:
        return await self._read("map_view", route_dest=route_dest, full_graph=full_graph,
                                fit_width=fit_width)

    async def computer_view(self) -> dto.ComputerDTO:
        return await self._read("computer_view")

    async def tavern_view(self) -> dto.TavernDTO:
        return await self._read("tavern_view")

    async def corp_view(self) -> dto.CorpDTO | None:
        return await self._read("corp_view")

    async def market_view(self) -> dto.MarketDTO:
        return await self._read("market_view")

    async def route_view(self, dst_sector: int, *, full_graph: bool = False) -> dto.RouteDTO:
        return await self._read("route_view", dst_sector=dst_sector, full_graph=full_graph)

    async def route_legs_view(self, waypoints: list[int]) -> dto.RouteDTO:
        return await self._read("route_legs_view", waypoints=waypoints)

    async def engine_room_view(self) -> dto.EngineRoomDTO:
        return await self._read("engine_room_view")

    async def stardock_view(self) -> dto.StardockDTO:
        return await self._read("stardock_view")

    async def territory_view(self) -> dto.TerritoryDTO:
        return await self._read("territory_view")

    async def starbase_view(self, starbase_id: int) -> dto.StarbaseDTO:
        return await self._read("starbase_view", starbase_id=starbase_id)

    async def current_starbase_view(self) -> dto.StarbaseDTO | None:
        return await self._read("current_starbase_view")

    async def planet_view(self, planet_id: int) -> dto.PlanetDTO:
        return await self._read("planet_view", planet_id=planet_id)

    async def current_planet_view(self) -> dto.PlanetDTO | None:
        return await self._read("current_planet_view")

    async def ground_operation_view(
        self, *, viewport_x: int = 0, viewport_y: int = 0,
        viewport_width: int | None = None, viewport_height: int | None = None,
    ) -> dto.SurveyExpeditionDTO | None:
        return await self._read(
            "ground_operation_view", viewport_x=viewport_x, viewport_y=viewport_y,
            viewport_width=viewport_width, viewport_height=viewport_height,
        )

    async def surface_view(self, planet_id: int) -> dto.SurfaceDTO:
        return await self._read("surface_view", planet_id=planet_id)

    async def contact_view(self, species_id: int, active_context: str = "greeting",
                           active_subject: int | None = None) -> dto.ContactDTO:
        return await self._read("contact_view", species_id=species_id,
                                active_context=active_context, active_subject=active_subject)

    async def species_in_sector(self) -> int | None:
        return await self._read("species_in_sector")

    async def current_contact_view(self) -> dto.ContactDTO | None:
        return await self._read("current_contact_view")

    async def encounter_view(self) -> dto.EncounterDTO | None:
        return await self._read("encounter_view")

    async def leads_view(self) -> list[dto.LeadDTO]:
        return await self._read("leads_view")

    async def messages_view(self) -> dto.MessagesDTO:
        return await self._read("messages_view")

    async def describe_event(self, event: Event) -> str:
        return cast(str, await self._call("describe_event", {"event": wire.encode_event(event)}))

    async def resolve_display_id(self, shown: int) -> int | None:
        return cast(int | None, await self._call("resolve_display_id", {"shown": shown}))

    # --- trusted accessors ---------------------------------------------------

    @property
    def state(self) -> UniverseState:
        raise NotImplementedError("raw state is not available over the wire (fog of war, H15)")

    @property
    def config(self) -> GameConfig:
        """The static shared config, loaded locally for pure rendering (never wired, WP68)."""
        if self._config is None:
            from edge.config import load_default_config
            self._config = load_default_config()
        return self._config


if TYPE_CHECKING:  # static conformance: RemoteClient must also satisfy the async protocol.
    def _assert_remote_impl(client: RemoteClient) -> GameClient:
        return client
