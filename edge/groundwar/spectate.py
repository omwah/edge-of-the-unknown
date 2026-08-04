"""Bot pilot for the ground-war playtest shell — watch a bot fight, to judge the balance.

Balance tuning (GW-WP13/WP16) was deferred for want of a human read of what the bots
actually do. A batch seed matrix cannot supply that on its own: the first measured runs
all ended `retrieval` at turn 24 with near-zero casualties, and a table of identical
rows cannot distinguish "the world is too hard" from "the bot never closed with it".
Watching can. This is the instrument.

**Nothing here is a simulator.** The scenario is `edge.groundwar.harness` (the same
single-planet `GameService` `SetupScreen` already builds), the fight is the production
reducers, and the view is the unmodified
`edge.tui.screens.ground_assault.GroundAssaultScreen` the live game pushes. The bot and
the screen share **one** `GameService`: the bot applies commands through
`ServiceProtocol`, and `GroundAssaultScreen.observe` narrates the resulting events and
re-pulls the view. That shared service is what makes this faithful — there is no replay,
no recording, and no second copy of state that could drift from what the rules ran
against.

This module owns no Textual app. `edge.groundwar.app` hosts it, because the pilot is a
*mode of the existing playtest shell* — the setup screen already picks the seed, world,
difficulty, and squad, and a second program would only have re-implemented all of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edge.bot.runner import BotRunner
from edge.bot.scripts import assaulter
from edge.core.config import GameConfig
from edge.core.groundwar.assault import assault_map_for
from edge.core.groundwar.models import AssaultOperation
from edge.core.models import UniverseState
from edge.core.rules import BeginAssault, Command, ExtractGroundOperation, apply_result, reduce
from edge.groundwar import harness
from edge.server.client import LocalClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.screens.ground_assault import GroundAssaultScreen

# Pace bounds in seconds per bot action. The floor is not zero: at zero the timer fires
# faster than the screen repaints, and a run nobody can follow defeats the purpose.
PACE_MIN = 0.05
PACE_MAX = 4.0
PACE_FACTOR = 1.6
PACE_DEFAULT = 0.35


@dataclass(frozen=True)
class Scenario:
    """The knobs `derive_difficulty` actually reads, plus the squad that lands."""

    seed: int = 7
    planet_type: str = "terrestrial_warm"
    habitability_cap: int = 8_000
    citadel_level: int = 0
    cloud_city_size: int = 0  # > 0 selects the Cloud City (jovian station) branch
    loadout: tuple[tuple[str, int], ...] = (("marauder", 4), ("scout", 3), ("command", 1))

    @property
    def is_cloud_city(self) -> bool:
        return self.cloud_city_size > 0

    def describe(self) -> str:
        where = (f"Cloud City size {self.cloud_city_size}" if self.is_cloud_city
                 else f"{self.planet_type} cap {self.habitability_cap:,}")
        squad = " ".join(f"{count}×{name}" for name, count in self.loadout if count)
        return f"seed {self.seed} · {where} · citadel {self.citadel_level} · {squad}"


def build_state(scenario: Scenario, config: GameConfig) -> UniverseState:
    """The harness world for `scenario`, with the operation already open."""
    loadout = {name: count for name, count in scenario.loadout if count}
    if scenario.is_cloud_city:
        state = harness.cloud_city_assault_state(
            config, seed=scenario.seed, cloud_city_size=scenario.cloud_city_size,
            citadel_level=scenario.citadel_level, loadout=loadout)
    else:
        state = harness.assault_state(
            config, seed=scenario.seed, planet_type=scenario.planet_type,
            habitability_cap=scenario.habitability_cap,
            citadel_level=scenario.citadel_level, loadout=loadout)
    # Open the operation directly rather than through the client: the screen the app
    # pushes expects to arrive at a live operation, exactly as `PlanetScreen` hands off.
    apply_result(state, reduce(state, harness.PLAYER_ID, BeginAssault(harness.PLANET_ID), config))
    return state


class RecordingRunner(BotRunner):
    """A `BotRunner` that remembers what the last `step()` did.

    `BotRunner.step()` returns nothing — a headless bot has no reason to care. A
    spectator does: it needs the events to narrate and the commands to explain *why*
    the screen just changed. Overriding `apply` keeps that bookkeeping out of the bot
    scripts, which stay exactly as the headless tests run them.
    """

    def __init__(self, service: Any, player_id: int) -> None:
        super().__init__(service, player_id)
        self.events: list[Any] = []
        self.commands: list[Command] = []
        self.rejections: list[str] = []

    def apply(self, command: Command) -> tuple[Any, ...]:
        events = super().apply(command)
        self.commands.append(command)
        self.events.extend(events)
        if not events and self.last_error:
            self.rejections.append(self.last_error)
        return events

    def take(self) -> tuple[list[Command], list[Any], list[str]]:
        """Drain and return what accumulated since the previous call."""
        out = (self.commands, self.events, self.rejections)
        self.commands, self.events, self.rejections = [], [], []
        return out


def describe_command(command: Command) -> str:
    """A one-line gloss of a bot decision, for the battle log."""
    if isinstance(command, ExtractGroundOperation):
        return "[dim]bot ▸ extract[/dim]"
    parts = [f"{field.removesuffix('_id')}={value}"
             for field in ("actor_id", "x", "y", "city_id")
             if (value := getattr(command, field, None)) is not None]
    detail = f" {' '.join(parts)}" if parts else ""
    return f"[dim]bot ▸ {type(command).__name__}{detail}[/dim]"


class BotDriver:
    """Runs the assault bot against one scenario, one action at a time.

    Owns the service, client, and runner; the hosting app owns the timer and the keys.
    Splitting it that way is what lets the pilot be a mode of the existing playtest
    shell rather than an app of its own.
    """

    def __init__(self, client: LocalClient, config: GameConfig,
                 *, label: str = "", pace: float = PACE_DEFAULT) -> None:
        # Takes the *already-built* client so the setup screen keeps one world-building
        # path for both pilots: a bot-flown drop is the same operation, opened by the
        # same logged command, as one the human flies.
        self.client = client
        self.service = client.service
        self.config = config
        self.label = label
        self.pace = pace
        self.running = False
        self.steps = 0
        self.finished = False
        self.runner = RecordingRunner(self.service, harness.PLAYER_ID)
        assaulter.setup(self.runner)

    @classmethod
    def for_scenario(cls, scenario: Scenario, config: GameConfig,
                     *, pace: float = PACE_DEFAULT) -> BotDriver:
        """Build a throwaway world for `scenario` and drive it — the headless/test path."""
        state = build_state(scenario, config)
        service = GameService(state, config, SqliteRepository(":memory:"))
        client = LocalClient(service, player_id=harness.PLAYER_ID)
        return cls(client, config, label=scenario.describe(), pace=pace)

    # --- the run loop ---------------------------------------------------------

    async def advance(self, screen: GroundAssaultScreen) -> None:
        """Run one bot action and show its consequences. The whole spectator, really."""
        if self.finished or self.runner.stopped:
            return
        self.runner.take()  # drop anything buffered while a modal was up
        self.runner.step()
        self.steps += 1
        commands, events, rejections = self.runner.take()
        for command in commands:
            screen.note(describe_command(command))
        for reason in rejections:
            screen.note(f"[yellow]bot ✗ {reason}[/yellow]")
        await screen.observe(events, follow=True)
        self._check_finished(screen)

    def _check_finished(self, screen: GroundAssaultScreen) -> None:
        """Freeze on the decided board instead of letting the bot extract off it.

        The bot's next move after an outcome is `ExtractGroundOperation`, which ends the
        operation and pops the screen. For a headless run that is correct; for a human
        judging what just happened it throws the evidence away, so the run stops here
        and leaves the final board up.
        """
        operation = self.operation()
        if operation is not None and operation.outcome is not None:
            self.finished = True
            self.running = False
            screen.note(
                f"[b]● {operation.outcome.upper()}[/b] on turn {operation.local_turn}"
                f" · {operation.casualties}/{operation.initial_strength} lost"
                f" · resolve {operation.resolve} (surrender at"
                f" {operation.surrender_threshold})")
        elif self.runner.stopped:
            self.finished = True
            self.running = False
            screen.note("[yellow]● the bot gave up — no legal action it wanted to take"
                        "[/yellow]")

    # --- reading the live operation -------------------------------------------

    def operation(self) -> AssaultOperation | None:
        """The live operation off trusted state — the same read the bot scripts make.

        Fog of war is not the point here: someone watching for balance needs the real
        numbers (resolve, surrender threshold), not the player's projection of them.
        The *screen* still renders strictly from its DTO.
        """
        player = self.service.state.players.get(harness.PLAYER_ID)
        operation = player.ground_operation if player is not None else None
        return operation if isinstance(operation, AssaultOperation) else None

    def distance_to_objective(self) -> int | None:
        """Manhattan distance from the nearest living trooper to the nearest city.

        The single most diagnostic number in a run: it is what showed the bot spends ten
        of its twenty-four turns marching, then stalls outside weapons range instead of
        entering the city.
        """
        operation = self.operation()
        if operation is None or not operation.dropped:
            return None
        amap = assault_map_for(self.service.state, operation, self.config)
        alive = [t for t in operation.platoon if t.hp > 0]
        if not alive or not amap.cities:
            return None
        return min(abs(t.x - c.cx) + abs(t.y - c.cy) for t in alive for c in amap.cities)

    def status_line(self) -> str:
        operation = self.operation()
        if operation is None:
            return self.label or "no operation"
        parts = [
            f"turn {operation.local_turn}/{operation.retrieval_turn}",
            f"resolve {operation.resolve}→{operation.surrender_threshold}",
            f"alive {sum(1 for t in operation.platoon if t.hp > 0)}",
            f"lost {operation.casualties}",
        ]
        distance = self.distance_to_objective()
        if distance is not None:
            parts.append(f"objective {distance} cells")
        parts.append(f"step {self.steps}")
        return " · ".join(parts)

    # --- pace -----------------------------------------------------------------

    def slower(self) -> float:
        self.pace = min(PACE_MAX, self.pace * PACE_FACTOR)
        return self.pace

    def faster(self) -> float:
        self.pace = max(PACE_MIN, self.pace / PACE_FACTOR)
        return self.pace
