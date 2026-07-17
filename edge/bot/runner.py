"""`BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN §14, WP60).

A bot registers **triggers** (`@bot.on(EventType)` — the TWX idiom: a handler fired for every
matching event a command produces) and a **turn driver** (`@bot.each_turn` — the loop body run
each iteration until turns run out or the bot stops). It acts through `bot.apply(command)`,
which submits an ordinary command through the `ServiceProtocol` seam, dispatches the resulting
events to triggers, and — crucially — **swallows rules rejections** (a bot plays heuristically,
so an unaffordable trade or a blocked warp is normal, not a crash; the reason is stashed on
`last_error`). Convenience readers (`game`, `computer`, …) forward the ordinary fog-of-war
projections, so a bot is fog-honest by construction (H16).

Because every action is an ordinary logged command, a bot run **is** a command log: it replays
to the identical `state_hash` like any other (the WP12 rail), which is what makes bot-driven QA
trustworthy for Phase 4.
"""

from __future__ import annotations

from collections.abc import Callable

from edge.core import dto
from edge.core.combat import CombatError
from edge.core.dev import DevPatchError
from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.events import Event
from edge.core.movement import MovementError
from edge.core.rules import Command
from edge.server.protocol import ServiceProtocol

# Rules rejections a heuristic bot expects to hit and recover from (not bugs).
_REJECTIONS = (EconomyError, MovementError, CombatError, EngineRoomError, DevPatchError)

TriggerHandler = Callable[["BotRunner", Event], None]
TurnDriver = Callable[["BotRunner"], None]


class BotRunner:
    """Drives one player of a game through the `ServiceProtocol` seam (dev-tier, WP60)."""

    def __init__(self, service: ServiceProtocol, player_id: int = 1) -> None:
        self.service = service
        self.player_id = player_id
        self.last_error: str | None = None
        self.log_lines: list[str] = []
        self._triggers: dict[type[Event], list[TriggerHandler]] = {}
        self._turn_drivers: list[TurnDriver] = []
        self._stopped = False

    # --- registration (the script's authoring surface) -----------------------

    def on(self, event_type: type[Event]) -> Callable[[TriggerHandler], TriggerHandler]:
        """Register a trigger fired for every `event_type` a command produces (the TWX idiom)."""
        def register(handler: TriggerHandler) -> TriggerHandler:
            self._triggers.setdefault(event_type, []).append(handler)
            return handler
        return register

    def each_turn(self, driver: TurnDriver) -> TurnDriver:
        """Register the per-iteration driver — the bot's main loop body."""
        self._turn_drivers.append(driver)
        return driver

    def stop(self) -> None:
        """End the run early (e.g. the bot has nothing left to do)."""
        self._stopped = True

    def log(self, line: str) -> None:
        self.log_lines.append(line)

    # --- acting --------------------------------------------------------------

    def apply(self, command: Command) -> tuple[Event, ...]:
        """Submit a command, dispatch its events to triggers, and swallow rejections (WP60).

        A rejected command returns `()` and stashes the reason on `last_error` (a bot plays
        heuristically — rejections are normal), so a script never has to wrap every action in
        try/except. Accepted events are dispatched to their registered triggers in order.
        """
        try:
            events = self.service.apply(self.player_id, command)
        except _REJECTIONS as exc:
            self.last_error = str(exc)
            return ()
        self.last_error = None
        for event in events:
            for handler in self._triggers.get(type(event), ()):
                handler(self, event)
        return events

    # --- reading (ordinary fog-of-war projections) ---------------------------

    def game(self) -> dto.GameState:
        return self.service.game_view(self.player_id)

    def computer(self) -> dto.ComputerDTO:
        return self.service.computer_view(self.player_id)

    def current_port(self) -> dto.PortDTO | None:
        return self.service.current_port_view(self.player_id)

    def stardock(self) -> dto.StardockDTO:
        return self.service.stardock_view(self.player_id)

    def current_starbase(self) -> dto.StarbaseDTO | None:
        return self.service.current_starbase_view(self.player_id)

    def engine_room(self) -> dto.EngineRoomDTO:
        return self.service.engine_room_view(self.player_id)

    def tavern(self) -> dto.TavernDTO:
        return self.service.tavern_view(self.player_id)

    # --- the run loop --------------------------------------------------------

    def run(self, turns: int = 1000) -> int:
        """Run the turn drivers up to `turns` iterations (or until `stop`). Returns the count.

        Bounded so a headless run can't spin forever; a driver that makes no progress can call
        `stop` to end early. Triggers fire inside `apply` as a side effect of each command.
        """
        iterations = 0
        for _ in range(turns):
            if self._stopped or not self._turn_drivers:
                break
            self.step()
            iterations += 1
        return iterations

    def step(self) -> None:
        """Run each registered turn driver once (the swarm's round-robin unit, WP69)."""
        for driver in list(self._turn_drivers):
            if self._stopped:
                break
            driver(self)

    @property
    def stopped(self) -> bool:
        return self._stopped
