"""`edge-groundwar` — the ground-war POC's Textual shell.

Throwaway UI (the `tui`-tier exemption) over the pure `config`/`mapgen`/`rules`
stack: a setup screen (planet type, difficulty, seed, latinum-budget platoon), then
a battle screen — a scrolling viewport over the full terrain-art battlefield with
a deploy mode (place the drop), IGOUGO play, a status sidebar, a combat log, and
modest cell-flash FX. The UI only *reads* `Battle` and drains `Battle.events`;
every mutation goes through `rules`.
"""

from __future__ import annotations

import random as _random
import time
from dataclasses import dataclass

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Button, Footer, Input, RichLog, Static

from edge.groundwar import rules
from edge.groundwar.config import GroundwarConfig, load_config
from edge.groundwar.expedition import Site, generate_expedition
from edge.groundwar.expedition_ui import ExpeditionScreen
from edge.groundwar.mapgen import PLANET_TYPES, RUBBLE_ART, STRUCTURE_ART, generate_battle
from edge.groundwar.model import Battle, Trooper
from edge.groundwar.widgets import PlatoonComposer


@dataclass
class DeployEntry:
    """One roster slot during deployment — a named trooper awaiting a landing cell."""

    name: str
    suit_key: str
    x: int | None = None
    y: int | None = None

    @property
    def placed(self) -> bool:
        return self.x is not None

FLASH_SECONDS = 0.5

_EVENT_STYLES = {
    "hit": "orange1", "killed": "bold red", "destroyed": "bold bright_yellow",
    "resolve": "bold bright_cyan", "outcome": "bold bright_magenta",
    "broadcast": "bold bright_cyan", "sortie": "red", "drop": "bright_green",
    "jump": "bright_green", "miss": "grey58", "shot": "yellow", "missile": "yellow",
    "info": "grey66",
}

_FLASH_KINDS = {"hit": "on red", "killed": "on bright_red", "destroyed": "on yellow",
                "shot": "on grey54", "missile": "on orange1", "miss": "on grey35",
                "drop": "on green", "jump": "on green", "broadcast": "on cyan",
                "sortie": "on red"}

# Radar overlay (y): background washes for cells an enemy weapon bears on. The AA
# umbrella (anti-drop / anti-jump) is drawn in amber and last, so it dominates any
# overlap — steering the drop and jumps clear of it is the whole point; ground guns
# (turret / citadel gun / garrison) wash dark red.
AA_THREAT_BG = "on #3a2708"
GROUND_THREAT_BG = "on #3a1414"


_CONVENTIONS = """\
[b]?[/] opens help for the screen you are on · [b]Esc[/] closes it
[b]q[/] backs out of the battle · the log at the bottom narrates every exchange\
"""


class HelpScreen(ModalScreen[None]):
    """Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`.

    The host screen declares its help: a `help_keys` table of `(key, action)` rows
    (kept next to the `on_key` handler that implements them), an optional
    `help_legend` table of `(symbol-markup, meaning)` rows for what's on the map,
    optional `HELP` markup prose, and an optional `HELP_TITLE` display name.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
    ]

    CSS = """
    /* Translucent so the battlefield shows through behind the box. */
    HelpScreen { align: center middle; background: $background 60%; }
    HelpScreen #help-box {
        width: 80; max-width: 100%; max-height: 90%; height: auto; overflow-y: auto;
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

        legend = [f"  {sym}  {meaning}"
                  for sym, meaning in getattr(self._host, "help_legend", [])]
        with VerticalScroll(id="help-box"):
            yield Static(title, id="help-title")
            if rows:
                yield Static("Keys", classes="help-section")
                yield Static("\n".join(rows))
            if legend:
                yield Static("Legend", classes="help-section")
                yield Static("\n".join(legend))
            if prose:
                yield Static("How to play", classes="help-section")
                yield Static(prose)
            yield Static("Conventions", classes="help-section")
            yield Static(_CONVENTIONS)
            yield Static("[dim]Esc to close[/]", id="help-footer")

    def action_close(self) -> None:
        self.dismiss(None)


class MapView(Widget, can_focus=True):
    """Scrolling viewport over the battlefield; renders art + pieces + overlays."""

    def __init__(self, screen: "BattleScreen") -> None:
        super().__init__(id="map")
        self.battle_screen = screen
        self.cam_x = 0
        self.cam_y = 0

    # camera -----------------------------------------------------------------

    def pan(self, dx: int, dy: int) -> None:
        """Scroll the viewport without touching the cursor."""
        cfg = self.battle_screen.battle.config
        w, h = self.size.width, self.size.height
        if w <= 0:
            return
        self.cam_x = max(0, min(cfg.width - w, self.cam_x + dx))
        self.cam_y = max(0, min(cfg.height - h, self.cam_y + dy))
        self.refresh()

    def follow(self, x: int, y: int) -> None:
        """Keep (x, y) comfortably inside the viewport."""
        w, h = self.size.width, self.size.height
        if w <= 0:
            return
        margin = 8
        if x < self.cam_x + margin:
            self.cam_x = x - margin
        if x > self.cam_x + w - margin:
            self.cam_x = x - w + margin
        if y < self.cam_y + 3:
            self.cam_y = y - 3
        if y > self.cam_y + h - 3:
            self.cam_y = y - h + 3
        cfg = self.battle_screen.battle.config
        self.cam_x = max(0, min(cfg.width - w, self.cam_x))
        self.cam_y = max(0, min(cfg.height - h, self.cam_y))

    # rendering ----------------------------------------------------------------

    def render(self) -> Text:
        scr = self.battle_screen
        b = scr.battle
        w, h = self.size.width, self.size.height
        now = time.monotonic()
        scr.flashes = {k: v for k, v in scr.flashes.items() if v[1] > now}
        sel = scr.selected
        reach = scr.reachable_cache
        scr.threat_cache = scr.threat_tints() if scr.show_threat else {}
        out = Text(no_wrap=True)
        for row in range(h):
            y = self.cam_y + row
            if y >= b.config.height:
                out.append("\n")
                continue
            for col in range(w):
                x = self.cam_x + col
                if x >= b.config.width:
                    break
                ch, style = self._cell(b, scr, x, y, sel, reach)
                if (x, y) in scr.flashes:
                    style = f"{style.split(' on ')[0]} {scr.flashes[(x, y)][0]}"
                if (x, y) == (scr.cur_x, scr.cur_y):
                    preview = scr.cursor_preview()
                    ch, style = preview if preview else (ch, "black on bright_white")
                out.append(ch, style)
            if row < h - 1:
                out.append("\n")
        return out

    def _cell(self, b: Battle, scr: "BattleScreen", x: int, y: int,
              sel: Trooper | None, reach: dict[tuple[int, int], int]) -> tuple[str, str]:
        if scr.deploying:
            for e in scr.roster:
                if e.placed and (e.x, e.y) == (x, y):
                    return b.config.suits[e.suit_key].glyph, "black on bright_green"
        t = b.trooper_at(x, y)
        if t is not None:
            if t is sel:
                return t.suit.glyph, "black on bright_green"
            return t.suit.glyph, ("black on yellow" if t.detected else "black on green")
        g = b.garrison_at(x, y)
        if g is not None:
            return ("T" if g.kind == "armor" else "i"), "white on dark_red"
        s = b.structure_at(x, y)
        if s is not None:
            ch, fg, bg = STRUCTURE_ART[s.kind] if s.alive else RUBBLE_ART
            if s.alive and s.hp < s.hp_max:
                fg = "orange1"
            return ch, f"{fg} on {bg}"
        ch, fg, bg = b.art[y][x]
        style = f"{fg} on {bg}" if bg and bg != "black" else fg
        if sel is not None and (x, y) in reach:
            style = f"{fg} on grey27"
        tint = scr.threat_cache.get((x, y))
        if tint is not None:  # radar overlay wins on open ground (structures keep theirs)
            style = f"{fg} {tint}"
        return ch, style or "white"

    async def _on_click(self, event: events.Click) -> None:
        self.battle_screen.set_cursor(self.cam_x + event.x, self.cam_y + event.y)


class BattleScreen(Screen[None]):
    """Deploy the platoon, then fight the IGOUGO battle."""

    BINDINGS = [
        ("q", "quit_battle", "Abort"),
        Binding("z", "toggle_log", "Log"),
        Binding("question_mark", "help", "Help"),
    ]

    # Log panel heights: a 2-line peek by default (height = 2 lines + the top
    # border), expandable to the full readable size with `z`.
    LOG_COLLAPSED_H = 3
    LOG_EXPANDED_H = 9

    HELP_TITLE = "Battle"
    HELP = """\
This is a [b]demonstration raid[/], not extermination: drain planetary [b]RESOLVE[/] \
below the surrender threshold before the retrieval boat lifts.

[b]Your turn, step by step[/] — [b]Tab[/] selects a trooper (▶ in the sidebar; \
its reachable cells are tinted on the map). Each trooper gets [b]two actions per \
turn[/], any mix: move then fire, fire twice, jump then fire, move twice… Put the \
cursor on a tinted cell and press [b]m[/] to walk there (one action, up to the \
suit's full range) or [b]g[/] to jump-jet; put it on a target and press [b]f[/] \
to fire or [b]i[/] for a missile. A trooper out of actions greys out in the \
roster and Tab skips it. Work through the platoon in any order, then [b]Space[/] \
ends your turn: the planet shoots back, and everyone refreshes.

[b]What drains resolve[/] — destroying [i]military[/] assets: turrets [red]╬[/], \
AA batteries [red]⊕[/], sensor towers [cyan]⍑[/], the citadel gun [magenta]✸[/], \
garrison units, military blocks [red]▪[/], breaching walls, silencing ("cowing") \
a whole city, and — biggest of all — a [b]Command suit broadcasting terms[/] over \
a cowed city ([b]b[/], within range of its center).
[b]What backfires[/] — leveling civilian blocks ⌂ and losing troopers \
[i]harden[/] resolve.

[b]Detection[/] — sensor towers light you up (Scouts jam them up close); unseen \
suits shoot with a first-strike bonus, but firing reveals you. Jumping is fast \
and clears any terrain, but live AA fires on you mid-air — as it does at your \
drop capsules, hardest at point-blank. Land clear of the AA umbrella and march \
in; jump only when you must.

[b]Radar[/] ([b]y[/]) — washes every cell an enemy weapon covers: [orange1]amber[/] \
is the AA umbrella (drop/jump danger), [red]red[/] is gun range (turrets, the \
citadel gun, garrison). Use it to pick a safe landing zone and a route in.

[b]The clock[/] — sorties spawn and defenses stiffen every few turns; casualties \
past the doctrine ceiling abort the mission; and the boat leaves on schedule, \
surrender or no. Speed wins, not attrition.\
"""

    _DEPLOY_KEYS = [
        ("arrows/hjkl", "move the drop cursor (click works too)"),
        ("w/a/s/d", "pan the map (the cursor rides along)"),
        ("Tab / Shift+Tab", "next / previous unplaced trooper (placed ones leave the tab order)"),
        ("Enter", "drop the selected trooper's capsule at the cursor"),
        ("c", "scatter the rest of the stick around the cursor"),
        ("u", "undo the last placement"),
        ("y", "toggle the enemy-range radar (amber = AA umbrella, red = gun range)"),
        ("z", "expand / collapse the combat-log panel"),
        ("q", "abort back to setup"),
    ]
    _PLAY_KEYS = [
        ("arrows/hjkl", "move the cursor (click works too)"),
        ("H/J/K/L", "pan the cursor fast"),
        ("w/a/s/d", "pan the map (the cursor rides along)"),
        ("Tab / Shift+Tab", "next / previous ready trooper (spent ones leave the tab order)"),
        ("m / Enter", "move the selected trooper to the cursor (one action)"),
        ("g", "jump-jet to the cursor (one action; draws AA fire mid-air)"),
        ("f", "fire at the cursor cell"),
        ("i", "fire a homing missile at the cursor cell"),
        ("b", "broadcast terms (Command suit, over a cowed city)"),
        ("y", "toggle the enemy-range radar (amber = AA umbrella, red = gun range)"),
        ("z", "expand / collapse the combat-log panel"),
        ("Space", "end turn — the planet takes its go"),
        ("q", "abort the mission"),
    ]

    help_legend = [
        ("[black on green]M[/][black on green]S[/][black on green]C[/]",
         "your troopers (Marauder/Scout/Command; [black on yellow]yellow[/] = "
         "detected, [black on bright_green]green[/] = selected)"),
        ("[white on dark_red]i[/] [white on dark_red]T[/]",
         "garrison infantry / armor"),
        ("[bright_red on grey30]╬[/]", "turret"),
        ("[orange1 on grey23]⊕[/]", "AA battery (fires on drops and jumps)"),
        ("[bright_cyan on grey23]⍑[/]", "sensor tower (lights you up)"),
        ("[bright_magenta on grey30]✸[/]", "citadel gun"),
        ("[grey66 on grey30]█[/] [gold3 on grey30]▒[/]", "city wall / gate"),
        ("[indian_red on grey23]▪[/] [grey74 on grey23]⌂[/]",
         "military block (drains resolve) / civilian block (atrocity — hardens it)"),
        ("[grey42]▒[/]", "rubble (passable, decent cover)"),
        ("[white on grey27] [/]", "tinted ground — where the selected trooper can walk"),
        ("[white on #3a2708] [/] [white on #3a1414] [/]",
         "radar (y): AA umbrella (amber) / enemy gun range (red)"),
    ]

    @property
    def help_keys(self) -> list[tuple[str, str]]:
        return self._DEPLOY_KEYS if self.deploying else self._PLAY_KEYS

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen(self))

    def action_toggle_log(self) -> None:
        self.log_expanded = not self.log_expanded
        self.query_one("#log", RichLog).styles.height = (
            self.LOG_EXPANDED_H if self.log_expanded else self.LOG_COLLAPSED_H)

    def __init__(self, config: GroundwarConfig, battle: Battle,
                 loadout: dict[str, int]) -> None:
        super().__init__()
        self.config = config
        self.battle = battle
        suit_keys = [k for k, n in loadout.items() for _ in range(n)]
        self.roster: list[DeployEntry] = [
            DeployEntry(name=rules.TROOPER_NAMES[i % len(rules.TROOPER_NAMES)], suit_key=k)
            for i, k in enumerate(suit_keys)
        ]
        self.deploy_idx = 0
        self.drop_order: list[DeployEntry] = []  # placement stack for undo
        self.cur_x, self.cur_y = self._first_landable(battle)
        self.selected: Trooper | None = None
        self.reachable_cache: dict[tuple[int, int], int] = {}
        self.flashes: dict[tuple[int, int], tuple[str, float]] = {}
        self.show_threat = False  # enemy-range radar overlay (y toggles)
        self.threat_cache: dict[tuple[int, int], str] = {}
        self.log_expanded = False  # combat-log panel starts as a 2-line peek (z expands)

    @staticmethod
    def _first_landable(battle: Battle) -> tuple[int, int]:
        """A passable starting cursor near the map's left-middle."""
        mid = battle.config.height // 2
        for x in range(6, battle.config.width):
            for dy in range(0, mid):
                for y in (mid - dy, mid + dy):
                    if 0 <= y < battle.config.height and rules.move_cost(battle, x, y) > 0:
                        return x, y
        return 6, mid

    @property
    def deploying(self) -> bool:
        return not self.battle.dropped

    @property
    def deploy_selected(self) -> DeployEntry | None:
        """The roster entry the next capsule drops for (None once all are placed)."""
        if not self.deploying:
            return None
        n = len(self.roster)
        for off in range(n):
            e = self.roster[(self.deploy_idx + off) % n]
            if not e.placed:
                self.deploy_idx = (self.deploy_idx + off) % n
                return e
        return None

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
        log.write(Text("MOBILE INFANTRY DROP — place your capsules. Tab picks the next "
                       "trooper from the roster (placed ones grey out); the cursor shows "
                       "the landing point: green = clear skies, red = inside AA cover "
                       "(flak on the way down). Press 'y' for the enemy-range radar to "
                       "see the AA umbrella at a glance. Enter drops the capsule, 'c' "
                       "scatters the rest, ? for help.", style="bold"))
        self.query_one(MapView).focus()
        self.refresh_ui()

    # --- shared helpers -------------------------------------------------------

    def _cursor_in_aa(self) -> bool:
        aa_range = self.battle.config.defenses.aa.range
        return any(
            s.kind == "aa" and s.alive
            and rules.dist(s.x, s.y, self.cur_x, self.cur_y) <= aa_range
            for s in self.battle.structures.values()
        )

    def cursor_preview(self) -> tuple[str, str] | None:
        """During deploy: the next capsule's glyph at the cursor — red inside AA cover."""
        entry = self.deploy_selected
        if entry is None:
            return None
        glyph = self.battle.config.suits[entry.suit_key].glyph
        if rules.move_cost(self.battle, self.cur_x, self.cur_y) <= 0:
            return "x", "bright_white on grey35"  # unlandable ground
        return glyph, ("bright_white on red" if self._cursor_in_aa()
                       else "black on bright_green")

    def set_cursor(self, x: int, y: int) -> None:
        b = self.battle
        self.cur_x = max(0, min(b.config.width - 1, x))
        self.cur_y = max(0, min(b.config.height - 1, y))
        view = self.query_one(MapView)
        view.follow(self.cur_x, self.cur_y)
        self.refresh_ui()

    def drain_events(self) -> None:
        log = self.query_one("#log", RichLog)
        now = time.monotonic()
        for e in self.battle.events:
            style = _EVENT_STYLES.get(e.kind, "white")
            log.write(Text(e.text, style=style))
            if e.x >= 0 and e.kind in _FLASH_KINDS:
                self.flashes[(e.x, e.y)] = (_FLASH_KINDS[e.kind], now + FLASH_SECONDS)
        if self.battle.events:
            self.set_timer(FLASH_SECONDS + 0.1, self.refresh_ui)
        self.battle.events.clear()

    def _next_ready(self, after: Trooper | None, step: int = 1) -> Trooper | None:
        """The adjacent live trooper still holding an action — the tab order skips
        the spent. `step` is +1 for Tab, -1 for Shift+Tab."""
        troopers = self.battle.troopers
        n = len(troopers)
        start = troopers.index(after) if after in troopers else (0 if step < 0 else -1)
        for off in range(1, n + 1):
            t = troopers[(start + step * off) % n]
            if t.alive and not t.turn_taken:
                return t
        return None

    def refresh_ui(self) -> None:
        if self.selected is not None and (not self.selected.alive or self.battle.outcome):
            self.selected = None
        if self.selected is not None and self.selected.turn_taken:
            nxt = self._next_ready(after=self.selected)  # spent: pass the baton
            self.selected = nxt
            if nxt is not None:  # bring the cursor (and camera) along to the new trooper
                self.cur_x, self.cur_y = nxt.x, nxt.y
                self.query_one(MapView).follow(nxt.x, nxt.y)
        self.reachable_cache = (
            rules.reachable(self.battle, self.selected)
            if self.selected is not None and not self.deploying else {}
        )
        self.query_one(MapView).refresh()
        self.query_one("#sidebar", Static).update(self._sidebar())

    # --- radar overlay ---------------------------------------------------------

    def threat_tints(self) -> dict[tuple[int, int], str]:
        """Every cell an alive enemy weapon bears on — the radar overlay (y).
        Ground guns (turret, citadel gun, garrison) wash dark red; the AA umbrella
        (anti-drop / anti-jump) washes amber over the top. Pure weapon range, not
        line of sight, so it reads as a stable danger radius while you plan."""
        b = self.battle
        d = b.config.defenses
        out: dict[tuple[int, int], str] = {}

        def paint(cx: int, cy: int, rng: int, tint: str) -> None:
            for dx in range(-rng, rng + 1):
                for dy in range(-rng, rng + 1):
                    x, y = cx + dx, cy + dy
                    if (dx or dy) and b.in_bounds(x, y) and rules.dist(cx, cy, x, y) <= rng:
                        out[(x, y)] = tint

        # Ground fire first...
        for s in b.structures.values():
            if not s.alive:
                continue
            if s.kind == "turret":
                paint(s.x, s.y, d.turret.range, GROUND_THREAT_BG)
            elif s.kind == "citadel_gun":
                paint(s.x, s.y, d.citadel_gun.range, GROUND_THREAT_BG)
        for g in b.garrison.values():
            if g.alive:
                gcls = getattr(b.config.garrison, g.kind)
                paint(g.x, g.y, gcls.weapon.range, GROUND_THREAT_BG)
        # ...then the AA umbrella last, so it dominates any overlap.
        for s in b.structures.values():
            if s.alive and s.kind == "aa":
                paint(s.x, s.y, d.aa.range, AA_THREAT_BG)
        return out

    # --- sidebar ---------------------------------------------------------------

    def _sidebar(self) -> Text:
        b = self.battle
        p = b.config.pressure
        out = Text()

        def line(txt: str, style: str = "white") -> None:
            out.append(txt + "\n", style)

        diff = b.config.difficulties[b.difficulty_key]
        line(f"{diff.label} · {b.planet_type} · seed {b.seed}", "grey66")
        if self.deploying:
            line("── DEPLOY ──", "bold bright_green")
            selected = self.deploy_selected
            for e in self.roster:
                suit = b.config.suits[e.suit_key]
                if e.placed:
                    line(f" ✓{suit.glyph} {e.name:<10} down", "grey42")
                    continue
                mark = "▶" if e is selected else " "
                style = "bright_green" if e is selected else "white"
                line(f" {mark}{suit.glyph} {e.name:<10} {suit.label}", style)
            if selected is not None:
                line("")
                line(f"next: {selected.name} ({b.config.suits[selected.suit_key].label})",
                     "bold")
                danger = self._cursor_in_aa()
                line("cursor: " + ("IN AA COVER — flak!" if danger else "clear skies"),
                     "bold red" if danger else "green")
            line("")
            line(f"y radar: {'ON — steer clear of amber' if self.show_threat else 'off'}",
                 "bold orange1" if self.show_threat else "grey66")
            line("tab next · Enter place", "grey66")
            line("c scatter rest · u undo", "grey66")
            return out

        left = p.retrieval_turns - b.turn + 1
        line(f"Turn {b.turn} · retrieval in {left}", "bold" if left > 5 else "bold red")
        frac = min(1.0, b.resolve / b.config.resolve.start)
        bar = "█" * round(16 * frac) + "░" * (16 - round(16 * frac))
        color = "red" if b.resolve > b.surrender_threshold * 2 else "yellow"
        line(f"RESOLVE {bar} {b.resolve:>3.0f}", color)
        line(f"  surrender at ≤ {b.surrender_threshold}", "grey66")
        ceiling = int(p.casualty_ceiling * b.initial_strength)
        line(f"KIA {b.casualties()}/{b.initial_strength} (abort past {ceiling})",
             "red" if b.casualties() else "grey66")
        line("")
        line("── PLATOON ──", "bold")
        for t in b.troopers:
            if not t.alive:
                line(f"  ✝ {t.name}", "grey42")
                continue
            det = "!" if t.detected else " "
            if t.turn_taken:
                line(f" ✓{t.suit.glyph} {t.name:<10} {t.hp:>3}hp{det}", "grey42")
                continue
            mark = "▶" if t is self.selected else " "
            style = "bright_green" if t is self.selected else "white"
            line(f" {mark}{t.suit.glyph} {t.name:<10} {t.hp:>3}hp{det} {'●' * t.actions}",
                 style)
        if self.selected is not None:
            t = self.selected
            line("")
            line(f"── {t.name} · {t.suit.label} ──", "bold bright_green")
            line(f"  hp {t.hp}/{t.suit.hp}"
                 f"  actions {t.actions}/{b.config.actions_per_turn}"
                 f" · move {t.mp}mp")
            line(f"  missiles {t.missiles} · jumps {t.jump_charges}")
            line(f"  {'DETECTED' if t.detected else 'unseen'}",
                 "red" if t.detected else "green")
        line("")
        line("── CITIES ──", "bold")
        for c in b.cities:
            cowed = b.city_cowed(c)
            tag = "⭑" if c.is_citadel else " "
            state = "cowed" if cowed else \
                f"{len(b.city_structures(c.id, 'turret', 'aa', 'citadel_gun'))} guns"
            bc = " ✓terms" if c.broadcast_done else ""
            line(f" {tag}{c.name[:16]:<16} {state}{bc}", "green" if cowed else "white")
        line("")
        if b.outcome is not None:
            won = b.outcome == "surrender"
            line("═" * 26, "bold")
            line("VICTORY — THEY SURRENDER" if won else f"DEFEAT — {b.outcome}",
                 "bold bright_green" if won else "bold red")
            line("q to return to setup", "grey66")
        else:
            line(f"y radar: {'ON' if self.show_threat else 'off'}",
                 "bold orange1" if self.show_threat else "grey66")
            line("tab select · m move · g jump", "grey66")
            line("f fire · i missile · b terms", "grey66")
            line("space end turn · q abort", "grey66")
        return out

    # --- input -----------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        moves = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
                 "k": (0, -1), "j": (0, 1), "h": (-1, 0), "l": (1, 0)}
        if event.key in moves:
            dx, dy = moves[event.key]
            self.set_cursor(self.cur_x + dx, self.cur_y + dy)
            event.stop()
            return
        if event.key in ("H", "L", "K", "J"):  # shift-vi keys pan fast
            dx, dy = moves[event.key.lower()]
            self.set_cursor(self.cur_x + dx * 8, self.cur_y + dy * 4)
            event.stop()
            return
        pans = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
        if event.key in pans:
            dx, dy = pans[event.key]
            view = self.query_one(MapView)
            old_x, old_y = view.cam_x, view.cam_y
            view.pan(dx * 8, dy * 4)
            # Drag the cursor by the camera's actual (clamped) shift so it keeps its
            # place on screen — otherwise the next cursor move yanks the view back.
            b = self.battle
            self.cur_x = max(0, min(b.config.width - 1, self.cur_x + view.cam_x - old_x))
            self.cur_y = max(0, min(b.config.height - 1, self.cur_y + view.cam_y - old_y))
            self.refresh_ui()
            event.stop()
            return
        if event.key == "y":  # enemy-range radar — usable in deploy and play
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
            "m": self._act_move, "enter": self._act_move,
            "g": self._act_jump, "f": self._act_fire, "i": self._act_missile,
            "b": self._act_broadcast, "space": self._end_turn,
        }.get(event.key)
        if handler is not None:
            handler()
            event.stop()

    # --- deploy mode ------------------------------------------------------------

    def _deploy_key(self, event: events.Key) -> None:
        entry = self.deploy_selected
        if event.key == "tab" and entry is not None:
            # advance past the current pick; deploy_selected snaps to the next unplaced
            self.deploy_idx = (self.deploy_idx + 1) % len(self.roster)
        elif event.key == "shift+tab" and entry is not None:
            n = len(self.roster)
            for off in range(1, n + 1):
                i = (self.deploy_idx - off) % n
                if not self.roster[i].placed:
                    self.deploy_idx = i
                    break
        elif event.key == "enter" and entry is not None:
            if not self._place(entry, self.cur_x, self.cur_y):
                self.query_one("#log", RichLog).write(
                    Text("Can't land a capsule there.", style="grey66"))
            self._maybe_launch()
        elif event.key == "c" and entry is not None:
            rng = _random.Random(len(self.drop_order))
            while (entry := self.deploy_selected) is not None:
                for radius in range(2, 14):
                    if any(
                        self._place(entry,
                                    self.cur_x + rng.randint(-radius, radius),
                                    self.cur_y + rng.randint(-radius // 2 - 1, radius // 2 + 1))
                        for _ in range(60)
                    ):
                        break
                else:
                    self.query_one("#log", RichLog).write(
                        Text("No landable ground here for the rest of the stick.",
                             style="grey66"))
                    break
            self._maybe_launch()
        elif event.key == "u" and self.drop_order:
            undone = self.drop_order.pop()
            undone.x = undone.y = None
            self.deploy_idx = self.roster.index(undone)
        else:
            return
        self.refresh_ui()
        event.stop()

    def _place(self, entry: DeployEntry, x: int, y: int) -> bool:
        b = self.battle
        if not b.in_bounds(x, y) or rules.move_cost(b, x, y) <= 0:
            return False
        if any(e.placed and (e.x, e.y) == (x, y) for e in self.roster):
            return False
        entry.x, entry.y = x, y
        self.drop_order.append(entry)
        return True

    def _maybe_launch(self) -> None:
        drops = [(e.suit_key, e.x, e.y) for e in self.roster
                 if e.x is not None and e.y is not None]
        if len(drops) < len(self.roster):
            return
        rules.resolve_drop(self.battle, drops)  # roster order, so names line up
        self.drain_events()
        self.selected = self._next_ready(after=None)
        log = self.query_one("#log", RichLog)
        log.write(Text("YOUR TURN — Tab selects a trooper (tinted cells = where it "
                       "can walk). Cursor + m moves, f fires, i missile, g jumps. "
                       "Two actions each per turn, any mix (move+fire, fire twice, "
                       "jump+fire…) — spent troopers grey out and Tab skips them; "
                       "Space ends the turn. ? for the full how-to.", style="bold"))
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

    def _act_move(self) -> None:
        t = self.selected
        if t is None:
            self._select_next()
            return
        if rules.do_move(self.battle, t, self.cur_x, self.cur_y):
            self.drain_events()
            self.refresh_ui()

    def _act_jump(self) -> None:
        if self.selected is not None:
            rules.do_jump(self.battle, self.selected, self.cur_x, self.cur_y)
            self.drain_events()
            self.refresh_ui()

    def _act_fire(self, missile: bool = False) -> None:
        if self.selected is not None:
            rules.fire_at(self.battle, self.selected, self.cur_x, self.cur_y,
                          missile=missile)
            self.drain_events()
            self.refresh_ui()

    def _act_missile(self) -> None:
        self._act_fire(missile=True)

    def _act_broadcast(self) -> None:
        if self.selected is not None:
            rules.broadcast_terms(self.battle, self.selected)
            self.drain_events()
            self.refresh_ui()

    def _end_turn(self) -> None:
        rules.defense_phase(self.battle)
        self.drain_events()
        if self.battle.outcome is None:  # new round: highlight the first platoon member
            first = self._next_ready(after=None)
            self.selected = first
            if first is not None:
                self.set_cursor(first.x, first.y)
        self.refresh_ui()

    def action_quit_battle(self) -> None:
        self.app.pop_screen()


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
your latinum budget; the class \
[b]mixture[/] is the puzzle, and what lands is all you get. \
[b]Marauder[/]: heavy armor, the guns that break turrets and walls. \
[b]Scout[/]: fast and far-seeing, jams city sensors; barely armed. \
[b]Command[/]: an accuracy aura, and the [b]broadcast[/] that dictates terms \
over a beaten city — usually how you win. Difficulty sets the city count, the \
capital's citadel level, and how low resolve must fall.

[b]Expedition[/] — pick inhabited (settlements resupply and hint, but sites \
keep their distance from towns) or uninhabited (no help, sites anywhere). The \
same seed rebuilds the same planet, and this session it [i]remembers what you \
already found[/] there.

The same seed always builds the same map, in either mode.\
"""

    help_keys = [
        ("Tab / Shift+Tab", "move between the pickers, the squad table, and DROP"),
        ("↑ ↓", "select a suit row in the squad table"),
        ("− / +", "adjust the selected suit (or click the row's − / + buttons)"),
        ("Enter/click", "activate the focused button"),
        ("?", "this help"),
    ]

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen(self))

    # Short role blurb per suit, shown in the platoon composer's Role column.
    _ROLE_BLURB = {"marauder": "heavy firepower", "scout": "recon/jam",
                   "command": "aura/terms"}

    def __init__(self, config: GroundwarConfig) -> None:
        super().__init__()
        self.config = config
        self.mode = "assault"  # or "expedition"
        self.inhabited = True
        self.planet_idx = 0
        self.difficulty_idx = 1  # default "raid"

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
            with Horizontal(classes="row"):
                yield Input(placeholder="seed (blank = random)", id="seed")
            # The drop table + DROP button, packaged for reuse in the main game.
            yield PlatoonComposer(
                self.config.suits, budget=self.config.latinum_budget,
                max_troopers=self.config.max_troopers,
                initial={"marauder": 4, "scout": 3, "command": 1},
                role_blurbs=self._ROLE_BLURB, id="composer")
            with Horizontal(classes="row", id="land-row"):
                yield Button("LAND!", id="land", variant="success")

    def on_mount(self) -> None:
        self._update()

    def _update(self) -> None:
        expedition = self.mode == "expedition"
        planet = PLANET_TYPES[self.planet_idx]
        diff = list(self.config.difficulties.values())[self.difficulty_idx]
        self.query_one("#mode", Button).label = \
            f"Mode: {'Expedition' if expedition else 'Assault'}"
        self.query_one("#planet", Button).label = f"Planet: {planet}"
        self.query_one("#difficulty", Button).label = f"Difficulty: {diff.label}"
        self.query_one("#world", Button).label = \
            f"World: {'inhabited' if self.inhabited else 'uninhabited'}"
        # Each mode owns its controls: the platoon composer is assault's,
        # the inhabited toggle + LAND button are expedition's.
        self.query_one("#difficulty", Button).display = not expedition
        self.query_one("#world", Button).display = expedition
        self.query_one("#composer", PlatoonComposer).display = not expedition
        self.query_one("#land-row", Horizontal).display = expedition
        brief = Text()
        if expedition:
            e = self.config.expedition
            brief.append(
                "A peaceful survey on a friendly world: follow the sensor circles, "
                "run the scanner hot, read the ground, and dig on the exact spot.\n",
                "grey70")
            brief.append(
                f"  {e.sites_min}–{e.sites_max} sensor contacts · "
                f"{e.supplies_start} supplies · "
                f"{'settlements resupply and hint' if self.inhabited else 'no help down there'}\n",
                "grey70")
        else:
            brief.append(
                "A demonstration raid, not extermination: drop, break their defenses, "
                "dictate terms, and be gone before the boat lifts.\n", "grey70")
            brief.append(
                f"  {diff.cities} cities · citadel level {diff.citadel_level} · "
                f"surrender at resolve ≤ {diff.surrender_threshold} · "
                f"retrieval turn {self.config.pressure.retrieval_turns}\n", "grey70")
        self.query_one("#briefing", Static).update(brief)

    def _seed(self) -> int:
        raw = self.query_one("#seed", Input).value.strip()
        return int(raw) if raw.lstrip("-").isdigit() else _random.randrange(1 << 31)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "mode":
            self.mode = "expedition" if self.mode == "assault" else "assault"
        elif bid == "world":
            self.inhabited = not self.inhabited
        elif bid == "planet":
            self.planet_idx = (self.planet_idx + 1) % len(PLANET_TYPES)
        elif bid == "difficulty":
            self.difficulty_idx = (self.difficulty_idx + 1) % len(self.config.difficulties)
        elif bid == "land":
            self._launch_expedition(self._seed(), PLANET_TYPES[self.planet_idx])
            return
        self._update()

    def on_platoon_composer_dropped(self, event: PlatoonComposer.Dropped) -> None:
        """The reusable composer committed a squad — build the raid and drop in."""
        planet = PLANET_TYPES[self.planet_idx]
        diff_key = list(self.config.difficulties)[self.difficulty_idx]
        battle = generate_battle(self.config, seed=self._seed(), planet_type=planet,
                                 difficulty_key=diff_key)
        self.app.push_screen(BattleScreen(self.config, battle, event.loadout))

    def _launch_expedition(self, seed: int, planet: str) -> None:
        # The same planet (seed/type/world) remembers its finds across descents
        # this session — the app holds the registry, generation re-marks them.
        app = self.app
        assert isinstance(app, GroundwarApp)
        key = (seed, planet, self.inhabited)
        found = app.expedition_finds.setdefault(key, set())
        exp = generate_expedition(self.config, seed=seed, planet_type=planet,
                                  inhabited=self.inhabited,
                                  found_ids=frozenset(found))

        def on_found(site: Site) -> None:
            found.add(site.id)

        self.app.push_screen(ExpeditionScreen(exp, on_found))


class GroundwarApp(App[None]):
    TITLE = "edge-groundwar"

    CSS = """
    #main { height: 1fr; }
    #map { width: 1fr; height: 100%; }
    #sidebar { width: 34; height: 100%; padding: 0 1; background: $surface;
               border-left: solid $primary; }
    #log { height: 3; border-top: solid $primary; }
    #setup { padding: 1 2; }
    #title { padding: 1 0; }
    #setup .row { height: 3; }
    #setup Button { margin-right: 1; }
    #seed { width: 40; }
    """

    def __init__(self, config: GroundwarConfig | None = None) -> None:
        super().__init__()
        self.config_data = config or load_config()
        # (seed, planet_type, inhabited) -> found site ids; session-only memory.
        self.expedition_finds: dict[tuple[int, str, bool], set[int]] = {}

    def on_mount(self) -> None:
        self.push_screen(SetupScreen(self.config_data))


def main() -> None:
    GroundwarApp().run()


if __name__ == "__main__":
    main()
