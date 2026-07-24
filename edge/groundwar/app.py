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
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
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
        self.query_one("#planet", Button).display = not cloud_city
        self.query_one("#difficulty", Button).display = assault
        self.query_one("#world", Button).display = expedition
        self.query_one("#city-size", Button).display = cloud_city
        self.query_one("#composer", PlatoonComposer).display = assault
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

    def _new_client(self, state: UniverseState) -> LocalClient:
        app = self.app
        assert isinstance(app, EdgeApp)
        service = GameService(state, self.config, SqliteRepository(":memory:"))
        client = LocalClient(service, player_id=harness.PLAYER_ID)
        app.client = client
        app._start_ticker(client)
        return client

    async def on_platoon_composer_dropped(self, event: PlatoonComposer.Dropped) -> None:
        """The reusable composer committed a squad — build the world and drop in."""
        from edge.tui.screens.ground_assault import GroundAssaultScreen

        planet = PLANET_TYPES[self.planet_idx]
        _, cap, citadel = _ASSAULT_PRESETS[self.difficulty_idx]
        state = harness.assault_state(
            self.config, seed=self._seed(), planet_type=planet,
            habitability_cap=cap, citadel_level=citadel, loadout=dict(event.loadout))
        client = self._new_client(state)
        try:
            await client.apply(BeginAssault(planet_id=harness.PLANET_ID))
        except (EconomyError, MovementError) as exc:
            notify_warning(self, str(exc))
            return
        self.app.push_screen(GroundAssaultScreen(client))

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

    def _initial_screen(self) -> Screen[None]:
        return SetupScreen(self.config_data)


def main() -> None:
    GroundwarApp().run()


if __name__ == "__main__":
    main()
