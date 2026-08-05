"""`edge-groundwar` — the ground-war POC's Textual shell.

GW-WP14 retargeted this app onto production rules: `edge.core.groundwar` is now the
only ground-operations implementation in the repo. `SetupScreen` builds a throwaway
single-planet `GameService` (`edge.groundwar.harness`), dispatches `BeginAssault` /
`BeginSurvey` into it, and hands off entirely to the production
`edge.tui.screens.ground_assault.GroundAssaultScreen` / `ground_expedition
.GroundExpeditionScreen` — the exact screens `PlanetScreen.action_descend` pushes in
the live game. This app owns no battle/expedition engine of its own; it is a chrome-
and-config-only entry point for playtesting the production ground-war screens without
a full universe.
"""

from __future__ import annotations

import random as _random
from dataclasses import replace as _replace
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Button, Input, Static
from rich.text import Text

from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.economy import EconomyError
from edge.core.groundwar.terrain import LANDABLE_BIOMES
from edge.core.models import UniverseState
from edge.core.movement import MovementError
from edge.core.rules import BeginAssault, BeginSurvey
from edge.groundwar import harness
from edge.groundwar.interior_preview import CloudCityPreviewScreen
from edge.groundwar.spectate import BotDriver
from edge.server.client import LocalClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.app import EdgeApp
from edge.tui.chrome import notify_warning
from edge.tui.composer import PlatoonComposer, options_from_suits
from edge.tui.screens.help import HelpScreen

PLANET_TYPES = LANDABLE_BIOMES

# Short role blurb per suit, shown in the platoon composer's Role column.
_ROLE_BLURB = {"marauder": "heavy firepower", "scout": "recon/jam", "command": "aura/terms"}

# The standalone-only `GwDifficulty` table was retired alongside the POC's own engine
# (GW-WP14) — production derives assault difficulty from live world state
# (`edge.core.groundwar.assault.derive_difficulty`), reading only a world's
# `habitability_cap` (size) and `citadel_level`. These presets feed those two knobs.
_ASSAULT_PRESETS: list[tuple[str, int, int]] = [
    ("Raid", 3_000, 0),
    ("Assault", 6_000, 1),
    ("Siege", 10_000, 2),
    ("Fortress", 15_000, 3),
]


class SetupScreen(Screen[None]):
    """Mode / planet / seed pickers; platoon composer (assault) or world toggle
    (expedition)."""

    BINDINGS = [Binding("question_mark", "help", "Help")]

    HELP_TITLE = "Mission setup"
    HELP = """\
[b]Mode[/] picks the branch of play. [b]Assault[/] is the Mobile Infantry raid; \
[b]Expedition[/] is the peaceful archaeology survey on a friendly world — no \
platoon, just you, a scanner, and the ground.

[b]Assault[/] — compose the drop in the squad table (Tab to it, [b]↑↓[/] to \
select a suit, [b]−[/] / [b]+[/] to adjust — or click the row buttons) against \
your latinum budget; the class [b]mixture[/] is the puzzle, and what lands is \
all you get. [b]Marauder[/]: heavy armor, the guns that break turrets and walls. \
[b]Scout[/]: fast and far-seeing, jams city sensors; barely armed. [b]Command[/]: \
an accuracy aura, and the [b]broadcast[/] that dictates terms over a beaten city \
— usually how you win. Difficulty sets the world's size and citadel level, which \
production derives the battlefield and garrison from.

[b]Expedition[/] — pick inhabited (friendly, settlements resupply and hint) or \
uninhabited (no help, sites anywhere).

[b]Cloud City preview[/] — a read-only look at the GW-WP15 station-interior \
generator and art: no reducer runs yet (the live gate stays off until GW-WP16), \
so this just renders a generated layout. Pick a size and PREVIEW; the preview \
screen's own [b]?[/]-adjacent hints show its size/reroll keys.

Once you drop or land, you are on the exact screen the live game uses — see its \
own [b]?[/] help for controls.\
"""

    # Cycled by the Mode button, in this order.
    _MODES = ("assault", "expedition", "cloud_city")

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen(self))

    def __init__(self, config: GameConfig) -> None:
        super().__init__()
        self.config = config
        self.gw = config.groundwar
        assert self.gw is not None
        self.mode = "assault"  # one of _MODES
        self.inhabited = True
        self.planet_idx = 0
        self.difficulty_idx = 1  # default "Assault"
        self.cloud_city_size = 1
        # GW-WP22: who fights the drop. "bot" hands the same operation to the assault
        # bot and watches it on the same screen — the balance-tuning instrument.
        self.bot_pilot = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="setup"):
            yield Static(
                Text("EDGE OF THE UNKNOWN — PLANETFALL", style="bold bright_green"),
                id="title")
            yield Static(id="briefing")
            with Horizontal(classes="row"):
                yield Button("Mode", id="mode")
                yield Button("Planet type", id="planet")
                yield Button("Difficulty", id="difficulty")
                yield Button("World", id="world")
                yield Button("City size", id="city-size")
                yield Button("Pilot", id="pilot")
            with Horizontal(classes="row"):
                yield Input(placeholder="seed (blank = random)", id="seed")
            yield PlatoonComposer(
                options_from_suits(self.gw.suits, _ROLE_BLURB),
                budget=self.gw.latinum_budget,
                max_troopers=self.gw.max_troopers,
                initial={"marauder": 4, "scout": 3, "command": 1},
                id="composer")
            with Horizontal(classes="row", id="land-row"):
                yield Button("LAND!", id="land", variant="success")
            with Horizontal(classes="row", id="preview-row"):
                yield Button("PREVIEW", id="preview", variant="success")

    def on_mount(self) -> None:
        self._update()

    def _update(self) -> None:
        expedition = self.mode == "expedition"
        cloud_city = self.mode == "cloud_city"
        assault = self.mode == "assault"
        planet = PLANET_TYPES[self.planet_idx]
        label, cap, citadel = _ASSAULT_PRESETS[self.difficulty_idx]
        self.query_one("#mode", Button).label = f"Mode: {self.mode.replace('_', ' ').title()}"
        self.query_one("#planet", Button).label = f"Planet: {planet}"
        self.query_one("#difficulty", Button).label = f"Difficulty: {label}"
        self.query_one("#world", Button).label = \
            f"World: {'inhabited' if self.inhabited else 'uninhabited'}"
        self.query_one("#city-size", Button).label = f"City size: {self.cloud_city_size}"
        self.query_one("#pilot", Button).label = \
            f"Pilot: {'bot' if self.bot_pilot else 'you'}"
        self.query_one("#planet", Button).display = not cloud_city
        self.query_one("#difficulty", Button).display = assault
        self.query_one("#world", Button).display = expedition
        self.query_one("#city-size", Button).display = cloud_city
        # The composer now serves both fighting modes: GW-WP16 shipped the Cloud City
        # assault but left this shell preview-only, so a station could not be played or
        # watched here at all. Its balance is the least-tuned of the two.
        self.query_one("#composer", PlatoonComposer).display = assault or cloud_city
        self.query_one("#pilot", Button).display = assault or cloud_city
        self.query_one("#land-row", Horizontal).display = expedition
        self.query_one("#preview-row", Horizontal).display = cloud_city
        brief = Text()
        if expedition:
            e = self.gw.expedition
            brief.append(
                "A peaceful survey on a friendly world: follow the sensor circles, "
                "run the scanner hot, read the ground, and dig on the exact spot.\n",
                "grey70")
            brief.append(
                f"  {e.sites_min}–{e.sites_max} real sites · "
                f"{'friendly settlements resupply and hint' if self.inhabited else 'no help down there'}\n",
                "grey70")
        elif cloud_city:
            brief.append(
                "GW-WP15 read-only preview: the interior generator + art, no reducer "
                "yet — the live assault gate stays off until GW-WP16.\n", "grey70")
        else:
            brief.append(
                "A demonstration raid, not extermination: drop, break their defenses, "
                "dictate terms, and be gone before the boat lifts.\n", "grey70")
            brief.append(
                f"  world capacity {cap:,} · citadel level {citadel}\n", "grey70")
        self.query_one("#briefing", Static).update(brief)

    def _seed(self) -> int:
        raw = self.query_one("#seed", Input).value.strip()
        return int(raw) if raw.lstrip("-").isdigit() else _random.randrange(1 << 31)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "mode":
            self.mode = self._MODES[(self._MODES.index(self.mode) + 1) % len(self._MODES)]
        elif bid == "world":
            self.inhabited = not self.inhabited
        elif bid == "planet":
            self.planet_idx = (self.planet_idx + 1) % len(PLANET_TYPES)
        elif bid == "difficulty":
            self.difficulty_idx = (self.difficulty_idx + 1) % len(_ASSAULT_PRESETS)
        elif bid == "pilot":
            self.bot_pilot = not self.bot_pilot
        elif bid == "city-size":
            max_size = self.config.planets.cloud_city_max_size
            self.cloud_city_size = self.cloud_city_size % max_size + 1
        elif bid == "land":
            self._launch_expedition(self._seed(), PLANET_TYPES[self.planet_idx])
            return
        elif bid == "preview":
            self.app.push_screen(
                CloudCityPreviewScreen(self.config, self.cloud_city_size, self._seed()))
            return
        self._update()

    def _new_client(self, state: UniverseState, *, ticker: bool = True) -> LocalClient:
        app = self.app
        assert isinstance(app, EdgeApp)
        if isinstance(app, GroundwarApp):
            # A bot left attached across runs is not just idle: `action_extract` (Escape)
            # on the assault screen clears its operation straight through the shared
            # client, without ever going through `BotDriver._check_finished` — so a bot
            # escaped-out-of mid-run survives with `running=True` and no operation. The
            # next `GroundAssaultScreen` (even a human-flown one) still passes
            # `advance_bot`'s screen-type check, so the orphaned bot resumes ticking
            # against it: `drive()` sees `op is None`, tries to start a fresh assault, and
            # calls `b.game()`, which crashes — the harness's throwaway single-sector
            # state never populates `state.regions`. Starting any new run must detach it.
            app.stop_bot_pilot()
        service = GameService(state, self.config, SqliteRepository(":memory:"))
        client = LocalClient(service, player_id=harness.PLAYER_ID)
        app.client = client
        if ticker:
            # Skipped for a bot pilot: the background day-tick would keep advancing the
            # calendar while the run is paused for inspection, which is the one thing a
            # spectator must not do. A tactical operation resolves without it.
            app._start_ticker(client)
        return client

    async def on_platoon_composer_dropped(self, event: PlatoonComposer.Dropped) -> None:
        """The reusable composer committed a squad — build the world and drop in.

        Serves both fighting modes and both pilots. The world is built the same way
        regardless: a bot-flown drop must be the same operation the human would have
        got, or watching it would prove nothing about the balance.
        """
        from edge.tui.screens.ground_assault import GroundAssaultScreen

        loadout = dict(event.loadout)
        seed = self._seed()
        if self.mode == "cloud_city":
            state = harness.cloud_city_assault_state(
                self.config, seed=seed, cloud_city_size=self.cloud_city_size,
                citadel_level=_ASSAULT_PRESETS[self.difficulty_idx][2], loadout=loadout)
            label = f"seed {seed} · Cloud City size {self.cloud_city_size}"
        else:
            planet = PLANET_TYPES[self.planet_idx]
            _, cap, citadel = _ASSAULT_PRESETS[self.difficulty_idx]
            state = harness.assault_state(
                self.config, seed=seed, planet_type=planet,
                habitability_cap=cap, citadel_level=citadel, loadout=loadout)
            label = f"seed {seed} · {planet} cap {cap:,} · citadel {citadel}"
        client = self._new_client(state, ticker=not self.bot_pilot)
        try:
            await client.apply(BeginAssault(planet_id=harness.PLANET_ID))
        except (EconomyError, MovementError) as exc:
            notify_warning(self, str(exc))
            return
        self.app.push_screen(GroundAssaultScreen(client))
        if self.bot_pilot:
            app = self.app
            assert isinstance(app, GroundwarApp)
            app.start_bot_pilot(client, label)

    def _launch_expedition(self, seed: int, planet: str) -> None:
        from edge.tui.screens.ground_expedition import GroundExpeditionScreen

        e = self.gw.expedition
        sites = _random.Random(seed).randint(e.sites_min, e.sites_max)
        state = harness.expedition_state(
            self.config, seed=seed, planet_type=planet,
            inhabited=self.inhabited, site_count=sites)
        client = self._new_client(state)

        async def begin_and_push() -> None:
            try:
                await client.apply(BeginSurvey(planet_id=harness.PLANET_ID))
            except (EconomyError, MovementError) as exc:
                notify_warning(self, str(exc))
                return
            self.app.push_screen(GroundExpeditionScreen(client))

        self.run_worker(begin_and_push())


class GroundwarApp(EdgeApp):
    TITLE = "edge-groundwar"

    # All `ctrl+…`, and only live while a bot is flying: the assault screen owns every
    # plain letter it binds (`m` move, `f` fire, `space` end turn, …), and a spectator
    # key that shadowed one would change what is being observed.
    BINDINGS = [
        Binding("ctrl+s", "toggle_bot", "Run bot", priority=True),
        Binding("ctrl+n", "step_bot", "Step", priority=True),
        Binding("ctrl+d", "bot_slower", "Slower", priority=True),
        Binding("ctrl+u", "bot_faster", "Faster", priority=True),
    ]

    # `EdgeApp.CSS_PATH` is a bare filename Textual resolves against the *subclass's*
    # module file, not the declaring class's — inheriting it unchanged would look for
    # a stylesheet next to this file instead of `edge/tui/app.tcss`. Point it at the
    # real one explicitly so the reused production screens get the same global rules.
    CSS_PATH = Path(__file__).resolve().parent.parent / "tui" / "app.tcss"

    CSS = """
    #setup { padding: 1 2; }
    #title { padding: 1 0; }
    #setup .row { height: 3; }
    #setup Button { margin-right: 1; }
    #seed { width: 40; }
    """

    def __init__(self, config: GameConfig | None = None) -> None:
        super().__init__()
        self.config_data = config or load_default_config()
        self.bot: BotDriver | None = None
        self._bot_timer: Timer | None = None

    def _initial_screen(self) -> Screen[None]:
        return SetupScreen(self.config_data)

    # --- bot pilot (GW-WP22) --------------------------------------------------

    def start_bot_pilot(self, client: LocalClient, label: str) -> None:
        """Attach the assault bot to the operation the pushed screen is showing."""
        self.bot = BotDriver(client, self.config_data, label=label)
        self.bot.running = True
        self._reset_bot_timer()
        self._sync_bot_labels()

    def _reset_bot_timer(self) -> None:
        """Textual timers hold a fixed interval, so a pace change means a new timer."""
        if self._bot_timer is not None:
            self._bot_timer.stop()
        self._bot_timer = None
        if self.bot is not None:
            self._bot_timer = self.set_interval(self.bot.pace, self._bot_tick)

    def stop_bot_pilot(self) -> None:
        """Detach any bot left over from a previous run before a new one starts."""
        if self._bot_timer is not None:
            self._bot_timer.stop()
        self._bot_timer = None
        self.bot = None

    async def _bot_tick(self) -> None:
        if self.bot is not None and self.bot.running:
            await self.advance_bot()

    async def advance_bot(self) -> None:
        """One bot action, narrated onto the live assault screen."""
        from edge.tui.screens.ground_assault import GroundAssaultScreen

        bot = self.bot
        if bot is None or bot.finished:
            return
        screen = self.screen if self.is_running else None
        if not isinstance(screen, GroundAssaultScreen):
            return  # a modal is up (outcome, help) — let the human read it first
        await bot.advance(screen)
        self._sync_bot_labels()

    def action_toggle_bot(self) -> None:
        if self.bot is None:
            return
        if self.bot.finished:
            self.bot.running = False
        else:
            self.bot.running = not self.bot.running
        self._sync_bot_labels()

    async def action_step_bot(self) -> None:
        if self.bot is None or self.bot.finished:
            return
        self.bot.running = False
        await self.advance_bot()

    def action_bot_slower(self) -> None:
        if self.bot is None:
            return
        self.bot.slower()
        self._reset_bot_timer()
        self._sync_bot_labels()

    def action_bot_faster(self) -> None:
        if self.bot is None:
            return
        self.bot.faster()
        self._reset_bot_timer()
        self._sync_bot_labels()

    def _sync_bot_labels(self) -> None:
        """Keep the Footer and subtitle telling the truth about the run right now."""
        bot = self.bot
        if bot is None:
            return
        self._set_binding_description("ctrl+s", "Pause" if bot.running else "Run bot")
        self._set_binding_description("ctrl+d", f"Slower ({bot.pace:.2f}s)")
        self.sub_title = bot.status_line()
        self.refresh_bindings()

    def _set_binding_description(self, key: str, description: str) -> None:
        bindings = self._bindings.key_to_bindings.get(key, [])
        self._bindings.key_to_bindings[key] = [
            _replace(binding, description=description) for binding in bindings
        ]


def main() -> None:
    GroundwarApp().run()


if __name__ == "__main__":
    main()
