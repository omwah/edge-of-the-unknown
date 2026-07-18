"""`edge-spacebattle` — the space-battle POC's Textual shell.

Throwaway UI (the `tui`-tier exemption) over the pure `config`/`model`/`rules`
stack: a setup screen (scenario + seed), an optional deployment pass (full
peacetime deploy for the prepared scenario; position-and-facing only for the
warp-in ambush), then the turn-based battle on a scrolling starfield board of
coarse placement cells. Multi-char sprites per hull, facing-keyed arcs and
damage, traveling missile salvos, fighter wings, hidden minefields. The UI only
*reads* `Battle` and drains `Battle.events`; every mutation goes through `rules`.
"""

from __future__ import annotations

import random as _random
import time
from dataclasses import dataclass, replace

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Button, Footer, Input, RichLog, Static

from edge.art.port import PortGenerator
from edge.spacebattle import rules
from edge.spacebattle.config import Scenario, SpacebattleConfig, load_config
from edge.spacebattle.model import (
    FACING_NAMES, Battle, FighterWing, Ship,
)
from edge.spacebattle.sprites import (
    DEBRIS_BG, FIGHTER_SPRITES, MINE_GLYPH, ROCK_BG, SALVO_GLYPH,
    debris_sprite, rock_sprite, ship_sprite,
)

FLASH_SECONDS = 0.5

_EVENT_STYLES = {
    "hit": "orange1", "destroyed": "bold red", "knockout": "bold bright_yellow",
    "outcome": "bold bright_magenta", "salvo": "yellow", "gun": "yellow",
    "miss": "grey58", "mine": "bold orange1", "sensor": "bold bright_cyan",
    "thrust": "bright_green", "launch": "bright_green", "intercept": "bright_cyan",
    "info": "grey66",
}

_FLASH_KINDS = {"hit": "on red", "destroyed": "on bright_red",
                "knockout": "on yellow", "mine": "on orange1", "miss": "on grey35",
                "salvo": "on grey54", "launch": "on green", "intercept": "on cyan",
                "sensor": "on cyan"}

_SIDE_STYLE = {"player": "bright_cyan", "enemy": "bright_red"}

_CONVENTIONS = """\
[b]?[/] opens help for the screen you are on · [b]Esc[/] closes it
[b]q[/] backs out of the battle · the log at the bottom narrates every exchange\
"""


@dataclass
class DeployShip:
    """One fleet slot during deployment — a hull awaiting a cell and a facing."""

    name: str
    cls_key: str
    facing: int = 0
    x: int | None = None
    y: int | None = None

    @property
    def placed(self) -> bool:
        return self.x is not None


class HelpScreen(ModalScreen[None]):
    """Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
    ]

    CSS = """
    HelpScreen { align: center middle; background: $background 60%; }
    HelpScreen #help-box {
        width: 84; max-width: 100%; max-height: 90%; height: auto; overflow-y: auto;
        padding: 1 2; border: round $primary; background: $surface;
    }
    HelpScreen #help-title { text-style: bold; color: $primary; margin-bottom: 1; }
    HelpScreen .help-section { text-style: bold; color: $secondary; margin-top: 1; }
    HelpScreen #help-footer { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, host: Screen[None] | None = None) -> None:
        super().__init__()
        self._host = host

    def compose(self) -> ComposeResult:
        host = self._host
        title = "Help"
        rows: list[str] = []
        prose = ""
        if host is not None:
            name = getattr(host, "HELP_TITLE", None) or type(host).__name__
            title = f"Help — {name}"
            rows = [f"  [b]{key}[/]  {action}"
                    for key, action in getattr(host, "help_keys", [])]
            prose = getattr(host, "HELP", "")

        with VerticalScroll(id="help-box"):
            yield Static(title, id="help-title")
            if rows:
                yield Static("Keys", classes="help-section")
                yield Static("\n".join(rows))
            if prose:
                yield Static("How to play", classes="help-section")
                yield Static(prose)
            yield Static("Conventions", classes="help-section")
            yield Static(_CONVENTIONS)
            yield Static("[dim]Esc to close[/]", id="help-footer")

    def action_close(self) -> None:
        self.dismiss(None)


def _make_starfield(seed: int, chars_w: int, chars_h: int,
                    cell_w: int, cell_h: int) -> list[list[tuple[str, str]]]:
    """A static char-level starfield backdrop with dim placement-grid ticks."""
    rng = _random.Random(seed ^ 0x5F1E1D)
    stars = [(".", 50), ("·", 30), ("*", 10), ("+", 5), ("✦", 2)]
    colors = [("grey37", 55), ("grey58", 25), ("white", 12),
              ("bright_cyan", 4), ("bright_yellow", 4)]
    total_s = sum(w for _, w in stars)
    total_c = sum(w for _, w in colors)

    def pick(pool: list[tuple[str, int]], total: int) -> str:
        r = rng.randrange(total)
        for item, w in pool:
            r -= w
            if r < 0:
                return item
        return pool[0][0]

    rows: list[list[tuple[str, str]]] = []
    for y in range(chars_h):
        row: list[tuple[str, str]] = []
        for x in range(chars_w):
            if x % cell_w == 0 and y % cell_h == 0:
                row.append(("·", "grey23"))  # placement-grid tick
            elif rng.random() < 0.045:
                row.append((pick(stars, total_s), pick(colors, total_c)))
            else:
                row.append((" ", "grey37"))
        rows.append(row)
    return rows


class MapView(Widget, can_focus=True):
    """Scrolling viewport (in chars) over the cell board; sprites + overlays."""

    def __init__(self, screen: "BattleScreen") -> None:
        super().__init__(id="map")
        self.battle_screen = screen
        self.cam_x = 0
        self.cam_y = 0

    # camera -----------------------------------------------------------------

    @property
    def chars_w(self) -> int:
        cfg = self.battle_screen.battle.config
        return cfg.width * cfg.cell_w

    @property
    def chars_h(self) -> int:
        cfg = self.battle_screen.battle.config
        return cfg.height * cfg.cell_h

    def pan(self, dx: int, dy: int) -> None:
        w, h = self.size.width, self.size.height
        if w <= 0:
            return
        self.cam_x = max(0, min(self.chars_w - w, self.cam_x + dx))
        self.cam_y = max(0, min(self.chars_h - h, self.cam_y + dy))
        self.refresh()

    def follow_cell(self, cx: int, cy: int) -> None:
        """Keep the placement cell comfortably inside the viewport."""
        cfg = self.battle_screen.battle.config
        x, y = cx * cfg.cell_w, cy * cfg.cell_h
        w, h = self.size.width, self.size.height
        if w <= 0:
            return
        margin_x, margin_y = cfg.cell_w * 2, cfg.cell_h * 2
        if x < self.cam_x + margin_x:
            self.cam_x = x - margin_x
        if x + cfg.cell_w > self.cam_x + w - margin_x:
            self.cam_x = x + cfg.cell_w - w + margin_x
        if y < self.cam_y + margin_y:
            self.cam_y = y - margin_y
        if y + cfg.cell_h > self.cam_y + h - margin_y:
            self.cam_y = y + cfg.cell_h - h + margin_y
        self.cam_x = max(0, min(self.chars_w - w, self.cam_x))
        self.cam_y = max(0, min(self.chars_h - h, self.cam_y))

    # rendering ----------------------------------------------------------------

    def render(self) -> Text:
        scr = self.battle_screen
        b = scr.battle
        cfg = b.config
        w, h = self.size.width, self.size.height
        now = time.monotonic()
        scr.flashes = {k: v for k, v in scr.flashes.items() if v[1] > now}
        overlay = scr.overlay()
        tints = scr.cell_tints()
        out = Text(no_wrap=True)
        for row in range(h):
            y = self.cam_y + row
            if y >= self.chars_h:
                out.append("\n")
                continue
            for col in range(w):
                x = self.cam_x + col
                if x >= self.chars_w:
                    break
                cell = (x // cfg.cell_w, y // cfg.cell_h)
                got = overlay.get((x, y))
                if got is not None:
                    ch, style = got
                else:
                    ch, style = scr.starfield[y][x]
                bg = tints.get(cell)
                if cell in scr.flashes:
                    bg = scr.flashes[cell][0]
                if cell == (scr.cur_x, scr.cur_y):
                    bg = "on grey35" if got is not None else "on grey27"
                if bg:
                    style = f"{style.split(' on ')[0]} {bg}"
                out.append(ch, style)
            if row < h - 1:
                out.append("\n")
        return out

    async def _on_click(self, event: events.Click) -> None:
        cfg = self.battle_screen.battle.config
        self.battle_screen.set_cursor((self.cam_x + event.x) // cfg.cell_w,
                                      (self.cam_y + event.y) // cfg.cell_h)


class BattleScreen(Screen[None]):
    """Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle."""

    BINDINGS = [
        ("q", "quit_battle", "Abort"),
        Binding("question_mark", "help", "Help"),
    ]

    HELP_TITLE = "Space battle"
    HELP = """\
Turn-based fleet action on a starfield of [b]placement cells[/]. Each ship gets \
[b]two actions[/] a turn, any mix; fighters get two of their own.

[b]Vector-lite movement[/] — a ship carries its velocity between turns and \
[b]drifts that far at end of turn[/]. The [b]t[/] burn bends your vector toward \
the cursor (with one free 90° of facing); the little side-colored [b]+[/] marks \
where each ship will drift. [b]b[/] burns back toward a dead stop. Momentum is \
real: line up broadsides, don't overshoot into their minefield.

[b]Facing is armor and armament[/] — the main gun bears through its arc \
(spinal: dead ahead only; ahead: a forward wedge). Hits strike the aspect they \
arrive on: fore/aft hits are [b]rakes[/] (bonus damage), so keep your bows on \
and your kilt clear. Screens are [b]ablative shields[/] that soak damage before \
the hull; once a facing's screen is down, hits knock out what lives there — gun \
forward, drive aft, launchers on the flanks, and a [b]shield generator[/] behind \
each facing.

[b]Missiles[/] are traveling salvos: they chase their target a few cells per \
turn until fuel-out. Launchers are [b]flank[/] mounts — the target must lie \
abeam (not ahead or astern), and a launch takes the [b]whole turn[/], so the \
gun line and the missile broadside are different postures. In defense: keep \
your speed up (fast targets shake birds off), out-run them, drag them through \
rocks, park a fighter wing alongside and [b]e[/] intercept — and every ship's \
[b]point-defense[/] thins whatever arrives, best where screens still hold. \
[b]Fighters[/] dash, strafe, dogfight, and intercept — but burn fuel every \
turn off the rack; recover them ([b]o[/]) to rearm.

[b]Mines[/] wait invisibly for a hull to drift onto them; sensors paint enemy \
mines only inside sensor range. In combat you can drop one alongside \
([b]n[/]) — the full minefield picture is a peacetime luxury.

[b]The Basilisk kit[/] — sidewall [b]screens regenerate[/] a little each turn \
a ship's hull goes unhurt, so standing off pays — but only while that facing's \
[b]shield generator[/] is intact. Batter a quadrant's screen down and land a \
hull hit and you may knock its generator out; that side then stops recovering \
until [b]u[/] repairs it. [b]u[/] spends the whole turn \
on damage control to restore one knocked-out component; [b]p[/] throws a recon \
drone downrange to paint hidden mines; and a fleeing ship's kilt is wide open \
(aft rakes hit doubly hard from dead astern). If you took the [b]grav-lance \
refit[/] at setup, [b]c[/] discharges it: whole turn, knife range, forward \
wedge — the struck quadrant's screen collapses to nothing, no hull damage. \
The lance kills nobody; the follow-up rake does. Capacitor takes turns to \
recharge, and the aliens have nothing like it.

[b]Rocky debris[/] (belt scenarios) — rock cells block gun and fighter fire \
lines, shred any missile salvo that flies onto them, and can't be stationed \
on. A hull that drifts into a rock ploughs through it: the rock is pulverized, \
the ship stops dead, and the impact damage scales with how fast you were \
going. Use the belt as cover — and mind your vector.

[b]Drifting wreckage[/] (graveyard scenarios) — torn hull plate behaves like \
rock for fire lines, salvos, and stationing, but a ship that drifts onto it \
[b]smashes through[/]: a lighter impact, the wreckage destroyed, and your \
vector kept. Rocks stop you dead; wreckage just costs you skin — sometimes \
the short way through the graveyard is worth the scrape.

[b]Starbase assault[/] (siege scenarios) — the base is an immobile emplacement \
with an all-round battery, ring-mounted launchers, fighter pickets, guard \
ships, and a hidden perimeter minefield. Its screens cover four quadrants like \
any hull, and its gun weakens as its components go down. Two ways to win: raze \
the hull, or collapse the [b]far-side (aft) screen[/] and knock out the \
[b]fusion reactor[/] homed there — reactor dark means the base is disabled and \
boarded, the way an orbital base is taken in the main game. Fighting around \
behind it, through the perimeter, is the whole battle.\
"""

    _DEPLOY_FULL_KEYS = [
        ("arrows/hjkl", "move the cell cursor (click works too)"),
        ("w/a/s/d", "pan the map"),
        ("Tab / Shift+Tab", "next / previous unplaced ship"),
        ("r / R", "rotate the pending ship's facing"),
        ("Enter", "place the selected ship at the cursor"),
        ("n", "lay a mine at the cursor (fleet stock, anywhere in your zone)"),
        ("v", "pre-launch a fighter wing at the cursor"),
        ("x", "pick the asset under the cursor back up (ship/mine/wing)"),
        ("u", "undo the last ship placement"),
        ("Space", "done — sound general quarters"),
        ("q", "abort back to setup"),
    ]
    _DEPLOY_WARP_KEYS = [
        ("arrows/hjkl", "move the cell cursor inside the warp-in pocket"),
        ("Tab / Shift+Tab", "next / previous unplaced ship"),
        ("r / R", "rotate the pending ship's facing"),
        ("Enter", "place the selected ship at the cursor"),
        ("x", "pick the ship under the cursor back up"),
        ("u", "undo the last ship placement"),
        ("y", "toggle the enemy threat overlay (their gun arcs)"),
        ("Space", "done — you are committed"),
        ("q", "abort back to setup"),
    ]
    _PLAY_KEYS = [
        ("arrows/hjkl", "move the cell cursor (click works too)"),
        ("H/J/K/L", "move the cursor fast"),
        ("w/a/s/d", "pan the map"),
        ("Tab / Shift+Tab", "next / previous ready ship or wing"),
        ("t / Enter", "ship: burn toward the cursor (free 90° of facing)"),
        ("b", "ship: burn back toward a dead stop"),
        ("r", "rotate to face the cursor (an action)"),
        ("f", "fire main gun at the cursor (arc + range)"),
        ("i", "launch a missile salvo (whole turn; target must lie abeam)"),
        ("v", "launch a docked fighter wing to the cursor (alongside)"),
        ("o", "recover the friendly wing under the cursor (alongside)"),
        ("n", "lay a mine at the cursor (alongside)"),
        ("c", "fire the grav lance at the cursor (refit only; whole turn, knife range)"),
        ("p", "launch a recon drone at the cursor (reveals mines around it)"),
        ("u", "damage control — whole turn, restores one knocked-out component"),
        ("y", "toggle the enemy threat overlay (their gun arcs, dark red)"),
        ("m / Enter", "wing: dash to the cursor"),
        ("g", "wing: strafe/dogfight the target under the cursor"),
        ("e", "wing: intercept the salvo under the cursor"),
        ("Space", "end turn — drift, salvos fly, the enemy moves"),
        ("q", "abort the battle"),
    ]

    @property
    def help_keys(self) -> list[tuple[str, str]]:
        if self.mode == "deploy_full":
            return self._DEPLOY_FULL_KEYS
        if self.mode == "deploy_warp":
            return self._DEPLOY_WARP_KEYS
        return self._PLAY_KEYS

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen(self))

    def __init__(self, config: SpacebattleConfig, battle: Battle,
                 scenario: Scenario, lance_refit: bool = False) -> None:
        super().__init__()
        self.config = config
        self.battle = battle
        self.scenario = scenario
        self.lance_refit = lance_refit
        self.mode = "deploy_full" if scenario.deploy == "full" else "deploy_warp"
        self.roster = [DeployShip(name=rules.PLAYER_NAMES[i % len(rules.PLAYER_NAMES)],
                                  cls_key=k)
                       for i, k in enumerate(scenario.player)]
        self.deploy_idx = 0
        self.place_order: list[DeployShip] = []
        self.selected: Ship | FighterWing | None = None
        self.show_threat = False  # enemy gun-arc threat overlay (T toggles)
        self.flashes: dict[tuple[int, int], tuple[str, float]] = {}
        # Main-game PortGenerator starbase art, rasterized once per station.
        self._station_art_cache: dict[int, list[tuple[int, int, str, str]]] = {}
        self.starfield = _make_starfield(
            battle.seed, config.width * config.cell_w,
            config.height * config.cell_h, config.cell_w, config.cell_h)
        zx, zy = self._zone_center()
        self.cur_x, self.cur_y = zx, zy

    # --- zones ----------------------------------------------------------------

    def _zone_max_x(self) -> int:
        if self.mode == "deploy_warp":
            return self.scenario.warp_zone_cells - 1
        return int(self.config.width * self.scenario.player_zone_frac) - 1

    def _in_zone(self, x: int, y: int) -> bool:
        return 0 <= x <= self._zone_max_x() and 0 <= y < self.config.height

    def _zone_center(self) -> tuple[int, int]:
        return max(0, self._zone_max_x() // 2), self.config.height // 2

    @property
    def deploying(self) -> bool:
        return not self.battle.deployed

    @property
    def deploy_selected(self) -> DeployShip | None:
        if not self.deploying:
            return None
        n = len(self.roster)
        for off in range(n):
            e = self.roster[(self.deploy_idx + off) % n]
            if not e.placed:
                self.deploy_idx = (self.deploy_idx + off) % n
                return e
        return None

    # --- compose / mount --------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="main"):
                yield MapView(self)
                yield Static(id="sidebar")
            yield RichLog(id="log", markup=False, wrap=True)
            yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.can_focus = False
        if self.mode == "deploy_full":
            log.write(Text(
                "GENERAL QUARTERS IN YOUR OWN TIME — a hostile fleet is inbound. "
                "Place your ships (r rotates facing), then seed the sector: 'n' "
                "lays mines anywhere in your zone, 'v' pre-launches fighter "
                "screens, 'x' picks anything back up to re-place it. Space when "
                "ready; ? for help.", style="bold"))
        else:
            log.write(Text(
                "WARP-IN — you tumble out of warp into a hostile picket. Position "
                "and facing are all you get: place each ship in the warp pocket "
                "(r rotates), then Space. Their mines are already out there, "
                "somewhere. ? for help.", style="bold"))
        self.query_one(MapView).focus()
        view = self.query_one(MapView)
        view.follow_cell(self.cur_x, self.cur_y)
        self.refresh_ui()

    # --- overlays (read by MapView) --------------------------------------------

    def _blit_sprite(self, overlay: dict[tuple[int, int], tuple[str, str]],
                     cx: int, cy: int, rows: tuple[str, ...], style: str) -> None:
        cfg = self.config
        oy = cy * cfg.cell_h + (cfg.cell_h - len(rows)) // 2
        for r, line in enumerate(rows):
            ox = cx * cfg.cell_w + (cfg.cell_w - len(line)) // 2
            for c, ch in enumerate(line):
                if ch != " ":
                    overlay[(ox + c, oy + r)] = (ch, style)

    def _center(self, cx: int, cy: int) -> tuple[int, int]:
        return (cx * self.config.cell_w + self.config.cell_w // 2,
                cy * self.config.cell_h + self.config.cell_h // 2)

    def _station_art(self, s: Ship) -> list[tuple[int, int, str, str]]:
        """The full main-game starbase art (`edge.art.port.PortGenerator`),
        rasterized to (dx, dy, char, style) offsets over the station's
        footprint. Deterministic per (battle seed, station id); cached."""
        cached = self._station_art_cache.get(s.id)
        if cached is None:
            cfg = self.config
            art = PortGenerator().generate(
                _random.Random(self.battle.seed ^ (s.id * 0x9E3779B1)),
                "starbase", s.cls.size * cfg.cell_w, s.cls.size * cfg.cell_h)
            console = self.app.console
            cached = []
            for r, line in enumerate(art.split(allow_blank=True)):
                for c, ch in enumerate(line.plain):
                    if ch != " ":
                        style = line.get_style_at_offset(console, c)
                        cached.append((c, r, ch, str(style)))
            self._station_art_cache[s.id] = cached
        return cached

    def _blit_station(self, overlay: dict[tuple[int, int], tuple[str, str]],
                      s: Ship) -> None:
        cfg = self.config
        half = s.cls.size // 2
        ox, oy = (s.x - half) * cfg.cell_w, (s.y - half) * cfg.cell_h
        for dx, dy, ch, style in self._station_art(s):
            overlay[(ox + dx, oy + dy)] = (ch, style)

    def overlay(self) -> dict[tuple[int, int], tuple[str, str]]:
        b = self.battle
        cfg = self.config
        out: dict[tuple[int, int], tuple[str, str]] = {}
        # rocks and wreckage under everything — pieces and ghosts draw over the rubble
        for (rx, ry) in b.rocks:
            ox, oy = rx * cfg.cell_w, ry * cfg.cell_h
            for dx, dy, ch, style in rock_sprite(b.seed, rx, ry,
                                                 cfg.cell_w, cfg.cell_h):
                out[(ox + dx, oy + dy)] = (ch, style)
        for (rx, ry) in b.debris:
            ox, oy = rx * cfg.cell_w, ry * cfg.cell_h
            for dx, dy, ch, style in debris_sprite(b.seed, rx, ry,
                                                   cfg.cell_w, cfg.cell_h):
                out[(ox + dx, oy + dy)] = (ch, style)
        # drift ghosts next, so real pieces draw over them
        for s in b.ships:
            if s.alive and (s.vx or s.vy):
                gx, gy = self._center(s.x + s.vx, s.y + s.vy)
                if b.in_bounds(s.x + s.vx, s.y + s.vy):
                    out[(gx, gy)] = ("+", "grey42" if s.side == "enemy"
                                     else "cyan")
        for m in b.mines:
            if m.side == "player" or m.revealed:
                mx, my = self._center(m.x, m.y)
                out[(mx, my)] = (MINE_GLYPH,
                                 "bright_cyan" if m.side == "player" else "red")
        for sv in b.salvos:
            sx, sy = self._center(sv.x, sv.y)
            style = "bright_yellow" if sv.side == "player" else "bright_red"
            out[(sx, sy)] = (SALVO_GLYPH, f"bold {style}")
            out[(sx + 1, sy)] = (str(min(9, sv.count)), style)
        for w in b.wings:
            if not w.alive:
                continue
            style = _SIDE_STYLE[w.side]
            if w is self.selected:
                style = "black on bright_green"
            elif w.side == "player" and w.turn_taken and not self.deploying:
                style = "grey50"
            self._blit_sprite(out, w.x, w.y, (FIGHTER_SPRITES[w.facing],), style)
        for s in b.ships:
            if not s.alive:
                continue
            if s.cls.station:  # the full main-game art over its whole footprint
                self._blit_station(out, s)
                continue
            style = _SIDE_STYLE[s.side]
            if s.hull < s.cls.hull_max * 0.4:
                style = "orange1"
            if s is self.selected:
                style = f"{style} on dark_green"
            elif s.side == "player" and s.turn_taken and not self.deploying:
                style = "grey50"
            self._blit_sprite(out, s.x, s.y, ship_sprite(s.cls.hull_art, s.facing),
                              style)
        # deployment: already-placed roster ships + the cursor ghost
        if self.deploying:
            for e in self.roster:
                if e.placed:
                    cls = self.config.ships[e.cls_key]
                    self._blit_sprite(out, e.x, e.y,  # type: ignore[arg-type]
                                      ship_sprite(cls.hull_art, e.facing),
                                      "bright_green")
            pend = self.deploy_selected
            if pend is not None:
                ok = self._can_place(self.cur_x, self.cur_y)
                cls = self.config.ships[pend.cls_key]
                self._blit_sprite(out, self.cur_x, self.cur_y,
                                  ship_sprite(cls.hull_art, pend.facing),
                                  "black on green" if ok else "white on red")
        return out

    def _threat_tints(self) -> dict[tuple[int, int], str]:
        """Every cell an alive enemy gun currently bears on (arc + range) — the
        mirror of the player's own selected-ship range tint, unioned over the
        whole hostile force, including the all-round starbase battery."""
        b = self.battle
        out: dict[tuple[int, int], str] = {}
        for s in b.fleet("enemy"):
            if not s.gun_ok:
                continue
            rng = s.cls.main_gun.range
            for dx in range(-rng, rng + 1):
                for dy in range(-rng, rng + 1):
                    x, y = s.x + dx, s.y + dy
                    if (dx or dy) and b.in_bounds(x, y) and \
                            rules.dist(s.x, s.y, x, y) <= rng and \
                            rules.arc_ok(s, x, y):
                        out[(x, y)] = "on #3a1414"
        return out

    def cell_tints(self) -> dict[tuple[int, int], str]:
        """Background tints per placement cell: zones, ranges, wing reach, the
        optional enemy-threat overlay — with the rock wash applied last so
        debris always keeps its regolith ground."""
        tints: dict[tuple[int, int], str] = {}
        b = self.battle
        if self.deploying:
            for y in range(self.config.height):
                for x in range(self._zone_max_x() + 1):
                    tints[(x, y)] = "on grey11"
            if self.show_threat:
                tints.update(self._threat_tints())
            tints.update(dict.fromkeys(b.rocks, ROCK_BG))
            tints.update(dict.fromkeys(b.debris, DEBRIS_BG))
            return tints
        sel = self.selected
        if isinstance(sel, Ship) and sel.gun_ok:
            gun = sel.cls.main_gun
            for dx in range(-gun.range, gun.range + 1):
                for dy in range(-gun.range, gun.range + 1):
                    x, y = sel.x + dx, sel.y + dy
                    if (dx or dy) and b.in_bounds(x, y) and \
                            rules.dist(sel.x, sel.y, x, y) <= gun.range and \
                            rules.arc_ok(sel, x, y):
                        tints[(x, y)] = "on grey15"
        elif isinstance(sel, FighterWing):
            r = self.config.fighters.speed
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    x, y = sel.x + dx, sel.y + dy
                    if (dx or dy) and b.in_bounds(x, y):
                        tints[(x, y)] = "on grey15"
        if self.show_threat:
            tints.update(self._threat_tints())
        tints.update(dict.fromkeys(b.rocks, ROCK_BG))
        tints.update(dict.fromkeys(b.debris, DEBRIS_BG))
        return tints

    # --- shared helpers ---------------------------------------------------------

    def set_cursor(self, x: int, y: int) -> None:
        self.cur_x = max(0, min(self.config.width - 1, x))
        self.cur_y = max(0, min(self.config.height - 1, y))
        self.query_one(MapView).follow_cell(self.cur_x, self.cur_y)
        self.refresh_ui()

    def drain_events(self) -> None:
        log = self.query_one("#log", RichLog)
        now = time.monotonic()
        for e in self.battle.events:
            style = _EVENT_STYLES.get(e.kind, "white")
            if not e.friendly and e.kind not in ("info",):
                style = f"{style}"
            log.write(Text(("· " if e.friendly else "▸ ") + e.text, style=style))
            if e.x >= 0 and e.kind in _FLASH_KINDS:
                self.flashes[(e.x, e.y)] = (_FLASH_KINDS[e.kind], now + FLASH_SECONDS)
        if self.battle.events:
            self.set_timer(FLASH_SECONDS + 0.1, self.refresh_ui)
        self.battle.events.clear()

    def _ready_pieces(self) -> list[Ship | FighterWing]:
        b = self.battle
        return [*b.fleet("player"), *b.side_wings("player")]

    def _next_ready(self, after: Ship | FighterWing | None,
                    step: int = 1) -> Ship | FighterWing | None:
        pieces = self._ready_pieces()
        if not pieces:
            return None
        n = len(pieces)
        start = pieces.index(after) if after in pieces else (0 if step < 0 else -1)
        for off in range(1, n + 1):
            p = pieces[(start + step * off) % n]
            if not p.turn_taken:
                return p
        return None

    def refresh_ui(self) -> None:
        sel = self.selected
        if sel is not None and (not sel.alive or self.battle.outcome):
            self.selected = None
        elif sel is not None and sel.turn_taken and not self.deploying:
            nxt = self._next_ready(after=sel)
            self.selected = nxt
            if nxt is not None:
                self.cur_x, self.cur_y = nxt.x, nxt.y
                self.query_one(MapView).follow_cell(nxt.x, nxt.y)
        self.query_one(MapView).refresh()
        self.query_one("#sidebar", Static).update(self._sidebar())

    # --- sidebar ---------------------------------------------------------------

    def _ship_lines(self, out: Text, s: Ship) -> None:
        def line(txt: str, style: str = "white") -> None:
            out.append(txt + "\n", style)

        mark = "▶" if s is self.selected else " "
        style = "bright_green" if s is self.selected else "white"
        spent = s.turn_taken and not self.deploying
        if spent:
            style = "grey42"
        frac = max(0.0, s.hull / s.cls.hull_max)
        bar = "█" * round(8 * frac) + "░" * (8 - round(8 * frac))
        line(f"{mark}{s.name}  {'●' * s.actions}", style)
        line(f"  hull {bar} {s.hull:>3}", "orange1" if frac < 0.4 else style)
        sc = s.screens
        line(f"  scr F{sc.get('fore', 0):>2} A{sc.get('aft', 0):>2}"
             f" P{sc.get('port', 0):>2} S{sc.get('starboard', 0):>2}", style)
        line(f"  vec ({s.vx:+d},{s.vy:+d}) face {FACING_NAMES[s.facing]}"
             f" · gun {s.cls.main_gun.arc}", style)
        line(f"  salvos {s.salvos} · wings {s.wings_docked}", style)
        line(f"  mines {s.mines} · drones {s.drones}", style)
        if s.lance:
            ready = s.lance_charge == 0
            line("  LANCE ready" if ready else f"  lance charging {s.lance_charge}",
                 "bold bright_magenta" if ready else "grey58")
        if s.down:
            line("  DOWN: " + ", ".join(sorted(s.down)).replace("_", " "), "bold red")

    def _sidebar(self) -> Text:
        b = self.battle
        out = Text()

        def line(txt: str, style: str = "white") -> None:
            out.append(txt + "\n", style)

        line(f"{self.scenario.label} · seed {b.seed}", "grey66")
        if self.deploying:
            zone = "your zone" if self.mode == "deploy_full" else "warp pocket"
            line(f"── DEPLOY ({zone} tinted) ──", "bold bright_green")
            selected = self.deploy_selected
            for e in self.roster:
                cls = self.config.ships[e.cls_key]
                if e.placed:
                    line(f" ✓ {e.name:<14} down", "grey42")
                    continue
                mark = "▶" if e is selected else " "
                style = "bright_green" if e is selected else "white"
                line(f" {mark} {e.name:<14} {cls.label}", style)
            if selected is not None:
                cls = self.config.ships[selected.cls_key]
                line("")
                line(f"next: {selected.name} ({cls.label})", "bold")
                line(f"facing {FACING_NAMES[selected.facing]} (r rotates)", "bold")
            if self.mode == "deploy_full":
                line("")
                line(f"mine stock {self._mine_stock()} (n lays)", "white")
                line(f"wings docked {self._wing_stock()} (v launches)", "white")
            line("")
            line("x picks an asset back up", "grey66")
            done = all(e.placed for e in self.roster)
            line("Space: sound general quarters" if done
                 else "place every ship first", "bold bright_green" if done else "grey66")
            return out

        line(f"Turn {b.turn}", "bold")
        line("")
        line("── YOUR FLEET ──", "bold")
        for s in b.fleet("player"):
            self._ship_lines(out, s)
        for w in b.side_wings("player"):
            mark = "▶" if w is self.selected else " "
            style = "grey42" if w.turn_taken else \
                ("bright_green" if w is self.selected else "white")
            line(f"{mark}-=▶ wing ×{w.strength}  fuel {w.endurance}"
                 f"  {'●' * w.actions}", style)
        line("")
        line("── CONTACTS ──", "bold")
        for s in b.fleet("enemy"):
            pct = round(100 * s.hull / s.cls.hull_max)
            if s.cls.station:
                integ = round(100 * rules.station_integrity(s))
                line(f"  {s.name:<12} {pct:>3}%", "bright_red")
                line(f"   ⌂ systems {integ:>3}% · reactor "
                     f"{'LIVE' if s.reactor_ok else 'DARK'}", "red")
                continue
            near = min((rules.dist(s.x, s.y, p.x, p.y) for p in b.fleet("player")),
                       default=99)
            line(f"  {s.name:<12} {pct:>3}% · {near}c", "bright_red")
        for w in b.side_wings("enemy"):
            line(f"  fighters ×{w.strength}", "red")
        inbound = sum(1 for sv in b.salvos if sv.side == "enemy")
        if inbound:
            line(f"  ⚠ {inbound} salvo(s) inbound", "bold orange1")
        line("")
        if b.outcome is not None:
            won = b.outcome == "victory"
            won_label = ("VICTORY — THE BASE HAS FALLEN"
                         if self.scenario.station else "VICTORY — SECTOR SECURED")
            line("═" * 26, "bold")
            line(won_label if won else "DEFEAT — FLEET LOST",
                 "bold bright_green" if won else "bold red")
            line("q to return to setup", "grey66")
        else:
            line("tab select · t burn · r rotate", "grey66")
            line("f gun · i salvo · n mine", "grey66")
            line("v launch · o recover · g strafe", "grey66")
            line("c lance · p drone · u dmg-ctl", "grey66")
            line("e intercept · space end turn", "grey66")
            line(f"y enemy threat overlay: {'ON' if self.show_threat else 'off'}",
                 "bold bright_red" if self.show_threat else "grey66")
        return out

    def _mine_stock(self) -> int:
        return sum(self.config.ships[e.cls_key].mine_stock for e in self.roster) \
            - self._mines_laid

    def _wing_stock(self) -> int:
        return sum(self.config.ships[e.cls_key].fighter_wings for e in self.roster) \
            - self._wings_out

    # --- input -----------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        moves = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
                 "k": (0, -1), "j": (0, 1), "h": (-1, 0), "l": (1, 0)}
        if event.key in moves:
            dx, dy = moves[event.key]
            self.set_cursor(self.cur_x + dx, self.cur_y + dy)
            event.stop()
            return
        if event.key in ("H", "L", "K", "J"):
            dx, dy = moves[event.key.lower()]
            self.set_cursor(self.cur_x + dx * 4, self.cur_y + dy * 3)
            event.stop()
            return
        pans = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
        if event.key in pans:
            dx, dy = pans[event.key]
            view = self.query_one(MapView)
            cfg = self.config
            old_x, old_y = view.cam_x, view.cam_y
            view.pan(dx * cfg.cell_w * 2, dy * cfg.cell_h * 2)
            self.cur_x = max(0, min(cfg.width - 1,
                                    self.cur_x + (view.cam_x - old_x) // cfg.cell_w))
            self.cur_y = max(0, min(cfg.height - 1,
                                    self.cur_y + (view.cam_y - old_y) // cfg.cell_h))
            self.refresh_ui()
            event.stop()
            return
        if event.key == "y":  # works in every mode; enemies exist on warp-in too
            self.show_threat = not self.show_threat
            self.refresh_ui()
            event.stop()
            return
        if self.deploying:
            self._deploy_key(event)
            return
        if self.battle.outcome is not None:
            return
        handler = {
            "tab": self._select_next, "shift+tab": self._select_prev,
            "t": self._act_thrust, "b": self._act_brake, "r": self._act_rotate,
            "f": self._act_fire, "i": self._act_salvo, "v": self._act_launch,
            "o": self._act_recover, "n": self._act_mine,
            "m": self._act_wing_move, "g": self._act_strafe,
            "e": self._act_intercept, "enter": self._act_default,
            "c": self._act_lance, "p": self._act_drone, "u": self._act_dc,
            "space": self._end_turn,
        }.get(event.key)
        if handler is not None:
            handler()
            event.stop()

    # --- deploy mode ------------------------------------------------------------

    def _can_place(self, x: int, y: int) -> bool:
        if not self._in_zone(x, y) or self.battle.cell_occupied(x, y):
            return False
        return not any(e.placed and (e.x, e.y) == (x, y) for e in self.roster)

    @property
    def _mines_laid(self) -> int:
        return sum(1 for m in self.battle.mines if m.side == "player")

    @property
    def _wings_out(self) -> int:
        return len(self.battle.side_wings("player"))

    def _deploy_key(self, event: events.Key) -> None:
        entry = self.deploy_selected
        log = self.query_one("#log", RichLog)
        if event.key == "tab" and entry is not None:
            self.deploy_idx = (self.deploy_idx + 1) % len(self.roster)
        elif event.key == "shift+tab" and entry is not None:
            n = len(self.roster)
            for off in range(1, n + 1):
                i = (self.deploy_idx - off) % n
                if not self.roster[i].placed:
                    self.deploy_idx = i
                    break
        elif event.key in ("r", "R") and entry is not None:
            entry.facing = (entry.facing + (2 if event.key == "r" else -2)) % 8
        elif event.key == "enter" and entry is not None:
            if self._can_place(self.cur_x, self.cur_y):
                entry.x, entry.y = self.cur_x, self.cur_y
                self.place_order.append(entry)
            else:
                log.write(Text("Can't hold station there.", style="grey66"))
        elif event.key == "u" and self.place_order:
            undone = self.place_order.pop()
            undone.x = undone.y = None
            self.deploy_idx = self.roster.index(undone)
        elif event.key == "x":
            self._deploy_pickup()
        elif event.key == "n" and self.mode == "deploy_full":
            self._deploy_mine()
        elif event.key == "v" and self.mode == "deploy_full":
            self._deploy_wing()
        elif event.key == "space":
            self._finish_deploy()
        else:
            return
        self.refresh_ui()
        event.stop()

    def _deploy_pickup(self) -> None:
        """Lift the asset under the cursor back into the roster/stock so it can
        be re-placed: a ship keeps its facing and becomes the pending pick."""
        b = self.battle
        at = (self.cur_x, self.cur_y)
        for e in self.roster:
            if e.placed and (e.x, e.y) == at:
                e.x = e.y = None
                if e in self.place_order:
                    self.place_order.remove(e)
                self.deploy_idx = self.roster.index(e)
                return
        wing = b.wing_at(*at)
        if wing is not None and wing.side == "player":
            b.wings.remove(wing)
            return
        mine = b.mine_at(*at, side="player")
        if mine is not None:
            b.mines.remove(mine)
            return
        self.query_one("#log", RichLog).write(
            Text("Nothing of yours to pick up there.", style="grey66"))

    def _deploy_mine(self) -> None:
        log = self.query_one("#log", RichLog)
        if self._mine_stock() <= 0:
            log.write(Text("No mines left in the fleet stock.", style="grey66"))
            return
        if not self._in_zone(self.cur_x, self.cur_y) or \
                self.battle.mine_at(self.cur_x, self.cur_y) is not None or \
                (self.cur_x, self.cur_y) in self.battle.rocks:
            log.write(Text("Mines go on a free cell inside your zone.", style="grey66"))
            return
        from edge.spacebattle.model import Mine
        self.battle.mines.append(Mine(id=self.battle.next_id(), side="player",
                                      x=self.cur_x, y=self.cur_y, revealed=True))

    def _deploy_wing(self) -> None:
        log = self.query_one("#log", RichLog)
        if self._wing_stock() <= 0:
            log.write(Text("No wings left docked.", style="grey66"))
            return
        if not self._in_zone(self.cur_x, self.cur_y) or \
                self.battle.cell_occupied(self.cur_x, self.cur_y) or \
                any(e.placed and (e.x, e.y) == (self.cur_x, self.cur_y)
                    for e in self.roster):
            log.write(Text("Wings deploy to a free cell inside your zone.",
                           style="grey66"))
            return
        fc = self.config.fighters
        self.battle.wings.append(FighterWing(
            id=self.battle.next_id(), side="player", x=self.cur_x, y=self.cur_y,
            strength=fc.wing_size, endurance=fc.endurance, carrier_id=-1))

    def _finish_deploy(self) -> None:
        log = self.query_one("#log", RichLog)
        if not all(e.placed for e in self.roster):
            log.write(Text("Every ship needs a station first.", style="grey66"))
            return
        b = self.battle
        laid, out = self._mines_laid, self._wings_out
        for i, e in enumerate(self.roster):
            cls = self.config.ships[e.cls_key]
            ship = rules.spawn_ship(b, "player", cls, e.name,
                                    e.x, e.y, e.facing,  # type: ignore[arg-type]
                                    lance=self.lance_refit and i == 0)
            take_m = min(ship.mines, laid)
            ship.mines -= take_m
            laid -= take_m
            take_w = min(ship.wings_docked, out)
            ship.wings_docked -= take_w
            out -= take_w
        for w in b.side_wings("player"):  # adopt the nearest hull as carrier
            near = min(b.fleet("player"),
                       key=lambda s: rules.dist(s.x, s.y, w.x, w.y))
            w.carrier_id = near.id
        b.deployed = True
        if self.mode == "deploy_full":
            rules.warp_in_enemy(b)
        self.mode = "play"
        rules.begin_turn(b, "player", first=True)
        self.drain_events()
        self.selected = self._next_ready(after=None)
        log.write(Text(
            "YOUR TURN — Tab selects a ship or wing (its gun arc / dash range is "
            "tinted). t burns toward the cursor, r rotates, f fires, i throws a "
            "salvo. Two actions each; watch the '+' drift markers. Space ends "
            "the turn. ? for the full how-to.", style="bold"))
        self.refresh_ui()

    # --- play mode ----------------------------------------------------------------

    def _select_next(self, step: int = 1) -> None:
        nxt = self._next_ready(after=self.selected, step=step)
        if nxt is None:
            return
        self.selected = nxt
        self.set_cursor(nxt.x, nxt.y)

    def _select_prev(self) -> None:
        self._select_next(step=-1)

    def _after_rules(self) -> None:
        self.drain_events()
        self.refresh_ui()

    def _sel_ship(self) -> Ship | None:
        return self.selected if isinstance(self.selected, Ship) else None

    def _sel_wing(self) -> FighterWing | None:
        return self.selected if isinstance(self.selected, FighterWing) else None

    def _act_default(self) -> None:
        if self._sel_wing() is not None:
            self._act_wing_move()
        else:
            self._act_thrust()

    def _act_thrust(self) -> None:
        s = self._sel_ship()
        if s is None:
            self._select_next()
            return
        rules.do_thrust(self.battle, s, self.cur_x, self.cur_y)
        self._after_rules()

    def _act_brake(self) -> None:
        s = self._sel_ship()
        if s is not None:
            rules.do_thrust(self.battle, s, s.x, s.y)
            self._after_rules()

    def _act_rotate(self) -> None:
        s = self._sel_ship()
        if s is not None:
            want = rules.cardinal(self.cur_x - s.x, self.cur_y - s.y)
            rules.do_rotate(self.battle, s, want)
            self._after_rules()

    def _act_fire(self) -> None:
        s = self._sel_ship()
        if s is not None:
            rules.fire_gun(self.battle, s, self.cur_x, self.cur_y)
            self._after_rules()

    def _act_salvo(self) -> None:
        s = self._sel_ship()
        target = self.battle.ship_at(self.cur_x, self.cur_y)
        if s is not None:
            if target is None or target.side != "enemy":
                self.battle.log("info", "Salvoes lock onto an enemy ship — put the "
                                        "cursor on one.")
            else:
                rules.launch_salvo(self.battle, s, target)
            self._after_rules()

    def _act_launch(self) -> None:
        s = self._sel_ship()
        if s is not None:
            rules.launch_wing(self.battle, s, self.cur_x, self.cur_y)
            self._after_rules()

    def _act_recover(self) -> None:
        s = self._sel_ship()
        wing = self.battle.wing_at(self.cur_x, self.cur_y)
        if s is not None and wing is not None:
            rules.recover_wing(self.battle, s, wing)
            self._after_rules()

    def _act_mine(self) -> None:
        s = self._sel_ship()
        if s is not None:
            rules.lay_mine(self.battle, s, self.cur_x, self.cur_y)
            self._after_rules()

    def _act_lance(self) -> None:
        s = self._sel_ship()
        if s is not None:
            rules.fire_lance(self.battle, s, self.cur_x, self.cur_y)
            self._after_rules()

    def _act_drone(self) -> None:
        s = self._sel_ship()
        if s is not None:
            rules.launch_drone(self.battle, s, self.cur_x, self.cur_y)
            self._after_rules()

    def _act_dc(self) -> None:
        s = self._sel_ship()
        if s is not None:
            rules.damage_control(self.battle, s)
            self._after_rules()

    def _act_wing_move(self) -> None:
        w = self._sel_wing()
        if w is not None:
            rules.move_wing(self.battle, w, self.cur_x, self.cur_y)
            self._after_rules()

    def _act_strafe(self) -> None:
        w = self._sel_wing()
        if w is not None:
            rules.wing_attack(self.battle, w, self.cur_x, self.cur_y)
            self._after_rules()

    def _act_intercept(self) -> None:
        w = self._sel_wing()
        salvo = self.battle.salvo_at(self.cur_x, self.cur_y)
        if w is not None:
            if salvo is None:
                self.battle.log("info", "Put the cursor on the salvo to intercept.")
            else:
                rules.intercept_salvo(self.battle, w, salvo)
            self._after_rules()

    def _end_turn(self) -> None:
        b = self.battle
        rules.end_turn(b, "player")
        rules.enemy_turn(b)
        if b.outcome is None:
            rules.begin_turn(b, "player")
        self.selected = None
        self.drain_events()
        self.selected = self._next_ready(after=None)
        if self.selected is not None:
            self.set_cursor(self.selected.x, self.selected.y)
        self.refresh_ui()

    def action_quit_battle(self) -> None:
        self.app.pop_screen()


class SetupScreen(Screen[None]):
    """Scenario / seed pickers."""

    BINDINGS = [Binding("question_mark", "help", "Help")]

    HELP_TITLE = "Battle setup"
    HELP = """\
Two ways into the same fight, exercising the two deployment interfaces:

[b]Prepared defense[/] — peacetime. You know they're coming: place your ships \
with chosen facings, then seed your whole zone with mines and pre-launched \
fighter screens [i]without[/] walking a ship around. Then the enemy warps in.

[b]Ambushed on warp-in[/] — you arrive in [i]their[/] sector. You pick only \
where each ship tumbles out of warp inside the pocket, and which way it faces. \
Their pickets are out and their minefield is already sown — and invisible \
until your sensors paint it.

[b]Belt skirmish[/] / [b]Ship graveyard[/] — the same fight threaded through \
an obstacle field: rocks stop a drifting hull dead; wreckage can be smashed \
through at a lighter cost in hull.

[b]Starbase assault[/] — warp in against a fortified, immobile starbase behind \
its perimeter defense. Raze it, or fight around behind it and knock out its \
reactor to take it intact.

[b]Fleet size[/] — the [b]−[/] / [b]+[/] steppers set exactly how many hulls \
each side brings before you launch. The hulls are drawn by cycling that \
scenario's own ship mix, so its composition's flavour is preserved. The enemy \
count can go to [b]0[/]: in a starbase assault that leaves just the base to \
break, and the siege starbase itself is always present regardless.

The same seed always builds the same battle.\
"""

    help_keys = [
        ("?", "this help"),
        ("−/+ steppers", "set how many ships each side brings (enemy may be 0)"),
        ("Enter/click", "activate the focused button"),
    ]

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen(self))

    # Explicit fleet sizes per side. The player always brings at least one hull;
    # the enemy count may be 0 (e.g. a starbase assault against the base alone —
    # the siege starbase itself is spawned separately and is always present).
    _MAX_FLEET = 8

    def __init__(self, config: SpacebattleConfig) -> None:
        super().__init__()
        self.config = config
        self.lance_refit = False
        self.player_count = 2
        self.enemy_count = 2

    def compose(self) -> ComposeResult:
        with Vertical(id="setup"):
            yield Static(
                Text("EDGE OF THE UNKNOWN — FLEET ACTION", style="bold bright_cyan"),
                id="title")
            yield Static(id="briefing")
            with Horizontal(classes="row"):
                yield Input(placeholder="seed (blank = random)", id="seed")
            with Horizontal(classes="row"):
                yield Button("−", id="pf_dec", classes="step")
                yield Button("+", id="pf_inc", classes="step")
                yield Static(self._forces_label("player"), id="pf-label",
                             classes="blurb")
            with Horizontal(classes="row"):
                yield Button("−", id="ef_dec", classes="step")
                yield Button("+", id="ef_inc", classes="step")
                yield Static(self._forces_label("enemy"), id="ef-label",
                             classes="blurb")
            with Horizontal(classes="row"):
                yield Button("Flagship: standard magazine", id="refit")
                yield Static("  the experimental grav-lance refit trades half "
                             "the missile magazine", classes="blurb")
            for key, sc in self.config.scenarios.items():
                with Horizontal(classes="row"):
                    yield Button(sc.label, id=f"go-{key}", variant="success")
                    yield Static(f"  {sc.blurb}", classes="blurb")

    def on_mount(self) -> None:
        brief = Text()
        brief.append(
            "Turn-based fleet combat: momentum, facing, arcs, screens, traveling "
            "missiles, fighter wings, hidden mines. Two actions per ship. "
            "? for the rules of the road.\n", "grey70")
        self.query_one("#briefing", Static).update(brief)

    def _forces_label(self, side: str) -> str:
        count = self.player_count if side == "player" else self.enemy_count
        who = "Player" if side == "player" else "Enemy"
        ships = f"{count} ship{'' if count == 1 else 's'}"
        if side == "enemy" and count == 0:
            ships += " (starbase only, in a siege)"
        return f"  {who} fleet: {ships}"

    @staticmethod
    def _fleet(base: tuple[str, ...], count: int) -> tuple[str, ...]:
        """Build a fleet of exactly `count` hulls, cycling the scenario's ship
        mix so its composition's flavour is preserved. `count` may be 0."""
        return tuple(base[i % len(base)] for i in range(count))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "refit":
            self.lance_refit = not self.lance_refit
            event.button.label = ("Flagship: GRAV-LANCE refit (½ salvos)"
                                  if self.lance_refit
                                  else "Flagship: standard magazine")
            return
        if bid in ("pf_dec", "pf_inc", "ef_dec", "ef_inc"):
            side = "player" if bid.startswith("pf") else "enemy"
            step = 1 if bid.endswith("inc") else -1
            if side == "player":
                self.player_count = max(1, min(self._MAX_FLEET,
                                               self.player_count + step))
            else:
                self.enemy_count = max(0, min(self._MAX_FLEET,
                                              self.enemy_count + step))
            label_id = "#pf-label" if side == "player" else "#ef-label"
            self.query_one(label_id, Static).update(self._forces_label(side))
            return
        if not bid.startswith("go-"):
            return
        key = bid[3:]
        base = self.config.scenarios[key]
        scenario = replace(
            base,
            player=self._fleet(base.player, self.player_count),
            enemy=self._fleet(base.enemy, self.enemy_count),
        )
        config = replace(
            self.config, scenarios={**self.config.scenarios, key: scenario})
        raw = self.query_one("#seed", Input).value.strip()
        seed = int(raw) if raw.lstrip("-").isdigit() else _random.randrange(1 << 31)
        battle = rules.make_battle(config, seed, key)
        rules.seed_rocks(battle)
        rules.seed_debris(battle)
        if scenario.station is not None:
            rules.setup_siege(battle)
        elif scenario.deploy == "warp_in":
            rules.setup_ambush(battle)
        self.app.push_screen(
            BattleScreen(config, battle, scenario, self.lance_refit))


class SpacebattleApp(App[None]):
    TITLE = "edge-spacebattle"

    CSS = """
    #main { height: 1fr; }
    #map { width: 1fr; height: 100%; }
    #sidebar { width: 36; height: 100%; padding: 0 1; background: $surface;
               border-left: solid $primary; }
    #log { height: 9; border-top: solid $primary; }
    #setup { padding: 1 2; }
    #title { padding: 1 0; }
    #setup .row { height: 3; }
    #setup Button { margin-right: 1; min-width: 24; }
    #setup Button.step { min-width: 5; width: 5; }
    #setup .blurb { padding: 1 0; color: $text-muted; }
    #seed { width: 40; }
    """

    def __init__(self, config: SpacebattleConfig | None = None) -> None:
        super().__init__()
        self.config_data = config or load_config()

    def on_mount(self) -> None:
        self.push_screen(SetupScreen(self.config_data))


def main() -> None:
    SpacebattleApp().run()


if __name__ == "__main__":
    main()
