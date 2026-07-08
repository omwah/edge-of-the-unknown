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
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from edge.core import dto
from edge.core.config import GameConfig
from edge.core.enums import Commodity
from edge.core.events import Event
from edge.core.models import UniverseState
from edge.core.rules import Command
from edge.engine.ticker import EngineTicker
from edge.server import session
from edge.server.service import GameService


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
    async def market_view(self) -> dto.MarketDTO: ...
    async def route_view(self, dst_sector: int, *, full_graph: bool = ...) -> dto.RouteDTO: ...
    async def route_legs_view(self, waypoints: list[int]) -> dto.RouteDTO: ...
    async def engine_room_view(self) -> dto.EngineRoomDTO: ...
    async def stardock_view(self) -> dto.StarDockDTO: ...
    async def starbase_services_view(self) -> dto.StarbaseServicesDTO | None: ...
    async def planet_view(self, planet_id: int) -> dto.PlanetDTO: ...
    async def current_planet_view(self) -> dto.PlanetDTO | None: ...
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

    async def market_view(self) -> dto.MarketDTO:
        return self._service.market_view(self.player_id)

    async def route_view(self, dst_sector: int, *, full_graph: bool = False) -> dto.RouteDTO:
        return self._service.route_view(self.player_id, dst_sector, full_graph=full_graph)

    async def route_legs_view(self, waypoints: list[int]) -> dto.RouteDTO:
        return self._service.route_legs_view(self.player_id, waypoints)

    async def engine_room_view(self) -> dto.EngineRoomDTO:
        return self._service.engine_room_view(self.player_id)

    async def stardock_view(self) -> dto.StarDockDTO:
        return self._service.stardock_view(self.player_id)

    async def starbase_services_view(self) -> dto.StarbaseServicesDTO | None:
        return self._service.starbase_services_view(self.player_id)

    async def planet_view(self, planet_id: int) -> dto.PlanetDTO:
        return self._service.planet_view(self.player_id, planet_id)

    async def current_planet_view(self) -> dto.PlanetDTO | None:
        return self._service.current_planet_view(self.player_id)

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
