"""Expedition mode's Textual screens (the peaceful branch of edge-groundwar).

Same throwaway-UI contract as the battle screen: reads `Expedition`, drains its
events for the log, and routes every mutation through `edge.groundwar.expedition`.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Footer, RichLog, Static

from edge.groundwar import expedition as ex
from edge.groundwar.expedition import Expedition, Site
from edge.groundwar.findart import FIND_KINDS, LORE_PLACEHOLDER, generate_find_art

FLASH_SECONDS = 0.5

_EVENT_STYLES = {
    "find": "bold bright_yellow", "hint": "bold bright_cyan",
    "outcome": "bold bright_magenta", "info": "grey66",
}

# Disturbed ground gets its own backdrop — it must pop against any biome.
CLUE_ART = ("∴", "bold black", "dark_goldenrod")

# A dry hole you already dug — same soil palette as the clues, so worked
# ground reads as one family: ∴ still to dig, ◌ already turned over.
DUG_ART = ("◌", "bold black", "dark_goldenrod")

# Scanner-glow backgrounds by band index (nearest band first: hot → cool).
HEAT_BGS = ("red3", "dark_orange3", "grey46", "grey30")

OVERLAYS = ("scanner", "range", "off")
MARKER = ("✦", "bold gold1")


class FindModal(ModalScreen[None]):
    """The congratulations (or field-notes revisit) card for one found site."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "close", "Close"),
    ]

    CSS = """
    FindModal { align: center middle; background: $background 60%; }
    FindModal #find-box {
        width: 56; max-width: 100%; height: auto; max-height: 95%; overflow-y: auto;
        padding: 1 2; border: round $secondary; background: $surface;
    }
    FindModal #find-title { text-style: bold; margin-bottom: 1; }
    FindModal #find-name { text-style: bold; margin-top: 1; }
    FindModal #find-lore { color: $text-muted; margin-top: 1; }
    FindModal #find-footer { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, site: Site, seed: int, *, first: bool) -> None:
        super().__init__()
        self._site = site
        self._seed = seed
        self._first = first

    def compose(self) -> ComposeResult:
        site = self._site
        kind = FIND_KINDS[site.kind]
        title = Text("A DISCOVERY — the survey pays off!", style="bold bright_yellow") \
            if self._first else Text("FIELD NOTES", style="bold bright_cyan")
        with VerticalScroll(id="find-box"):
            yield Static(title, id="find-title")
            yield Static(generate_find_art(site.kind, self._seed * 100 + site.id))
            yield Static(Text(f"{site.name}", style="bold"), id="find-name")
            yield Static(Text(f"{kind.label} — {kind.blurb}", style="grey70"))
            yield Static(Text(f"[ {LORE_PLACEHOLDER} ]", style="italic grey58"),
                         id="find-lore")
            yield Static("[dim]Esc to close[/]", id="find-footer")

    def action_close(self) -> None:
        self.dismiss(None)


class ExMapView(Widget, can_focus=True):
    """Scrolling viewport over the survey map."""

    def __init__(self, screen: "ExpeditionScreen") -> None:
        super().__init__(id="map")
        self.ex_screen = screen
        self.cam_x = 0
        self.cam_y = 0

    def pan(self, dx: int, dy: int) -> None:
        e = self.ex_screen.exp.config.expedition
        w, h = self.size.width, self.size.height
        if w <= 0:
            return
        self.cam_x = max(0, min(e.width - w, self.cam_x + dx))
        self.cam_y = max(0, min(e.height - h, self.cam_y + dy))
        self.refresh()

    def follow(self, x: int, y: int) -> None:
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
        e = self.ex_screen.exp.config.expedition
        self.cam_x = max(0, min(e.width - w, self.cam_x))
        self.cam_y = max(0, min(e.height - h, self.cam_y))

    def render(self) -> Text:
        scr = self.ex_screen
        exp = scr.exp
        w, h = self.size.width, self.size.height
        now = time.monotonic()
        scr.flashes = {k: v for k, v in scr.flashes.items() if v[1] > now}
        reach = scr.reachable_cache
        clues = scr.clue_cache
        rings = scr.ring_cache
        heat = scr.heat_cache
        out = Text(no_wrap=True)
        for row in range(h):
            y = self.cam_y + row
            if y >= exp.config.expedition.height:
                out.append("\n")
                continue
            for col in range(w):
                x = self.cam_x + col
                if x >= exp.config.expedition.width:
                    break
                ch, style = self._cell(exp, x, y, reach, clues, rings, heat)
                if (x, y) in scr.flashes:
                    style = f"{style.split(' on ')[0]} {scr.flashes[(x, y)][0]}"
                if (x, y) == (scr.cur_x, scr.cur_y):
                    ch, style = ch, "black on bright_white"
                out.append(ch, style)
            if row < h - 1:
                out.append("\n")
        return out

    def _cell(self, exp: Expedition, x: int, y: int,
              reach: dict[tuple[int, int], int], clues: set[tuple[int, int]],
              rings: dict[tuple[int, int], bool],
              heat: dict[tuple[int, int], str]) -> tuple[str, str]:
        p = exp.explorer
        if (x, y) == (p.x, p.y):
            return "@", "black on bright_green"
        site = exp.site_at(x, y)
        if site is not None and site.found:
            mch, mfg = MARKER
            return mch, f"{mfg} on grey19"
        ch, fg, bg = exp.art[y][x]
        if (x, y) in exp.dug:  # a spent hole trumps the clue that led you to it
            dch, dfg, dbg = DUG_ART
            return dch, f"{dfg} on {dbg}"
        if (x, y) in clues:
            cch, cfg, cbg = CLUE_ART
            return cch, f"{cfg} on {cbg}"
        if (x, y) in rings:
            ring_bg = "dark_green" if rings[(x, y)] else "grey35"
            return ch, f"{fg} on {ring_bg}"
        if (x, y) in heat:
            return ch, f"{fg} on {heat[(x, y)]}"
        style = f"{fg} on {bg}" if bg and bg != "black" else fg
        if (x, y) in reach:
            style = f"{fg} on grey27"
        return ch, style or "white"

    async def _on_click(self, event: events.Click) -> None:
        self.ex_screen.set_cursor(self.cam_x + event.x, self.cam_y + event.y)


class ExpeditionScreen(Screen[None]):
    """Walk the survey, follow the scanner, read the ground, dig."""

    BINDINGS = [
        ("q", "quit_expedition", "Return to ship"),
        Binding("question_mark", "help", "Help"),
    ]

    HELP_TITLE = "Expedition"
    HELP = """\
A [b]peaceful survey[/], not a raid: ship sensors marked each [b]grey circle[/] \
from orbit — an archaeological site lies somewhere [i]inside[/] each one, but \
the circle is not centered on it.

[b]Finding a site[/] — walk toward a circle; the sidebar [b]SCANNER[/] reads \
hotter as you close on the nearest unfound site (faint → moderate → strong → \
saturated). As you close in, the [b]scanner glow[/] paints the ground inside your sweep — \
warmer tint, nearer site ([b]o[/] cycles the overlay to a walk-range view or \
off). Once the readout saturates the scanner can do no more: look at the \
ground. [b]Disturbed earth[/] [black on dark_goldenrod]∴[/] appears on the map \
only when you are close enough to notice it (the log calls it out too), and \
clusters within a few cells of the true spot. Stand \
on your best guess and [b]dig[/] — only the exact cell pays off; a dry hole \
costs supplies and leaves a spent [black on dark_goldenrod]◌[/] so you never \
dig it twice.

[b]Marching[/] — put the cursor anywhere walkable and [b]m[/]: near cells are \
one turn, far ones a multi-turn march. A march [b]halts itself[/] the moment \
unseen disturbed ground comes into sight, so you won't tramp past the prize.

[b]Supplies[/] — every turn of marching and every dig spends one. At zero the \
shuttle recalls you — but anything found stays found, and the same planet (same \
seed) remembers across descents this session.

[b]Settlements[/] — on inhabited worlds, walk inside a town and [b]talk[/]: \
they refill your packs, and each town (once) shares an elder's memory that \
[green]tightens one search circle[/].

[b]The payoff[/] — a found site is marked [gold1]✦[/] on the chart. Put the \
cursor on it and press [b]v[/] any time to revisit the find and its notes.\
"""

    help_legend = [
        ("[black on bright_green]@[/]", "you, the surveyor"),
        ("[white on grey35] [/]", "sensor search circle — a site lies somewhere inside"),
        ("[white on dark_green] [/]", "narrowed circle (a settlement's hint)"),
        ("[black on dark_goldenrod]∴[/]",
         "disturbed ground — the dig spot is within a few cells"),
        ("[black on dark_goldenrod]◌[/]", "a hole you already dug (nothing there)"),
        ("[bold gold1 on grey19]✦[/]", "found site (press v on it to revisit)"),
        ("[white on grey46] [/][white on dark_orange3] [/][white on red3] [/]",
         "scanner glow — ground inside your sweep, warmer = nearer a buried site"),
        ("[white on grey27] [/]", "one turn's walking range (o cycles the overlays)"),
        ("[grey62 on grey30]█[/] [gold3 on grey30]▒[/]",
         "settlement wall / gate (walk in through a gate)"),
        ("[navajo_white3 on grey23]⌂[/] [bright_cyan on grey15]◉[/]",
         "homes / the plaza well — talk (t) anywhere inside town"),
    ]

    help_keys = [
        ("arrows/hjkl", "move the cursor (click works too)"),
        ("H/J/K/L", "pan the cursor fast"),
        ("w/a/s/d", "pan the map (the cursor rides along)"),
        ("m / Enter", "march to the cursor (a supply per turn; far cells take several)"),
        ("x", "dig where you stand"),
        ("o", "cycle the map overlay: scanner glow / walk range / off"),
        ("t", "talk (inside a settlement): resupply + a hint"),
        ("v", "view a found site under the cursor"),
        ("q", "return to the ship"),
    ]

    def action_help(self) -> None:
        from edge.groundwar.app import HelpScreen
        self.app.push_screen(HelpScreen(self))

    def __init__(self, exp: Expedition,
                 on_found: Callable[[Site], None] | None = None) -> None:
        super().__init__()
        self.exp = exp
        self.on_found = on_found
        self.cur_x, self.cur_y = exp.explorer.x, exp.explorer.y
        self.overlay = "scanner"  # "scanner" glow | "range" (one turn's walk) | "off"
        self.reachable_cache: dict[tuple[int, int], int] = {}
        self.clue_cache: set[tuple[int, int]] = set()
        self.ring_cache: dict[tuple[int, int], bool] = {}
        self.heat_cache: dict[tuple[int, int], str] = {}
        self.flashes: dict[tuple[int, int], tuple[str, float]] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="main"):
                yield ExMapView(self)
                yield Static(id="sidebar")
            yield RichLog(id="log", markup=False, wrap=True)
            yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.can_focus = False
        log.write(Text("SURVEY LANDING — the grey circles are sensor contacts from "
                       "orbit. Walk (cursor + m) toward one; the scanner in the "
                       "sidebar runs hot/cold. Near the spot, watch for disturbed "
                       "ground ∴ and dig (x) on the exact cell. ? for the full "
                       "how-to.", style="bold"))
        view = self.query_one(ExMapView)
        view.focus()
        self.drain_events()
        self.refresh_ui()
        self.call_after_refresh(self._center_start)

    def _center_start(self) -> None:
        view = self.query_one(ExMapView)
        view.follow(self.exp.explorer.x, self.exp.explorer.y)
        view.refresh()

    # --- shared helpers ---------------------------------------------------

    def set_cursor(self, x: int, y: int) -> None:
        e = self.exp.config.expedition
        self.cur_x = max(0, min(e.width - 1, x))
        self.cur_y = max(0, min(e.height - 1, y))
        view = self.query_one(ExMapView)
        view.follow(self.cur_x, self.cur_y)
        self.refresh_ui()

    def drain_events(self) -> None:
        log = self.query_one("#log", RichLog)
        now = time.monotonic()
        for e in self.exp.events:
            style = _EVENT_STYLES.get(e.kind, "white")
            log.write(Text(e.text, style=style))
            if e.x >= 0 and e.kind in ("find", "hint"):
                self.flashes[(e.x, e.y)] = ("on yellow", now + FLASH_SECONDS)
        if self.exp.events:
            self.set_timer(FLASH_SECONDS + 0.1, self.refresh_ui)
        self.exp.events.clear()

    def refresh_ui(self) -> None:
        exp = self.exp
        live = exp.outcome is None
        self.reachable_cache = \
            ex.reachable(exp) if live and self.overlay == "range" else {}
        self.heat_cache = self._heat() if live and self.overlay == "scanner" else {}
        self.clue_cache = ex.visible_clues(exp)
        self.ring_cache = self._rings()
        self.query_one(ExMapView).refresh()
        self.query_one("#sidebar", Static).update(self._sidebar())

    def _heat(self) -> dict[tuple[int, int], str]:
        """The scanner glow: ground inside the sweep, tinted by how near the
        nearest unfound site lies to *that cell* (same bands as the readout)."""
        exp = self.exp
        sites = exp.unfound()
        if not sites:
            return {}
        e = exp.config.expedition
        p = exp.explorer
        bands = e.scanner
        out: dict[tuple[int, int], str] = {}
        for dy in range(-e.sight, e.sight + 1):
            for dx in range(-e.sight, e.sight + 1):
                if dx * dx + dy * dy > e.sight * e.sight:
                    continue
                x, y = p.x + dx, p.y + dy
                if not exp.in_bounds(x, y):
                    continue
                d = min(ex.dist(x, y, s.x, s.y) for s in sites)
                # The coldest band stays untinted — a faint whiff is the readout's
                # job; painting it would smear a grey halo over the whole march.
                for i, band in enumerate(bands[:-1]):
                    if d <= band.within:
                        out[(x, y)] = HEAT_BGS[min(i, len(HEAT_BGS) - 1)]
                        break
        return out

    def _rings(self) -> dict[tuple[int, int], bool]:
        """Search-circle outline cells → hinted? for every unfound site."""
        out: dict[tuple[int, int], bool] = {}
        exp = self.exp
        for s in exp.unfound():
            r = s.area_r
            for dy in range(-r - 1, r + 2):
                for dx in range(-r - 1, r + 2):
                    if abs((dx * dx + dy * dy) ** 0.5 - r) < 0.5:
                        c = (s.area_cx + dx, s.area_cy + dy)
                        if exp.in_bounds(*c):
                            out[c] = s.hinted or out.get(c, False)
        return out

    # --- sidebar ----------------------------------------------------------

    def _sidebar(self) -> Text:
        exp = self.exp
        e = exp.config.expedition
        out = Text()

        def line(txt: str, style: str = "white") -> None:
            out.append(txt + "\n", style)

        world = "inhabited" if exp.inhabited else "uninhabited"
        line(f"survey · {exp.planet_type} · {world}", "grey66")
        line(f"seed {exp.seed} · turn {exp.turn}", "grey66")
        frac = exp.explorer.supplies / e.supplies_start
        bar = "█" * round(16 * frac) + "░" * (16 - round(16 * frac))
        color = "bright_green" if frac > 0.5 else "yellow" if frac > 0.2 else "red"
        line(f"SUPPLIES {bar} {exp.explorer.supplies:>3}", color)
        line("")
        reading, _near = ex.scanner_reading(exp)
        line("── SCANNER ──", "bold")
        hot = reading.startswith("SATURATED")
        line(f" {reading}", "bold bright_yellow" if hot
             else "bright_cyan" if reading not in ("no signal",) else "grey58")
        line(f" overlay: {self.overlay} (o cycles)", "grey58")
        line("")
        line("── CONTACTS ──", "bold")
        for s in exp.sites:
            if s.found:
                line(f" ✦ {s.name[:26]}", "gold1")
            elif s.hinted:
                line(f" ? contact {s.id} — narrowed", "bright_cyan")
            else:
                line(f" ? contact {s.id} — area marked", "grey70")
        if exp.inhabited:
            line("")
            line("── SETTLEMENTS ──", "bold")
            for t in exp.settlements:
                tag = "hint shared" if t.hint_given else "will talk"
                line(f"  {t.name[:16]:<16} {tag}",
                     "grey42" if t.hint_given else "white")
        line("")
        if exp.outcome is not None:
            done = exp.outcome == "complete"
            line("═" * 26, "bold")
            line("SURVEY COMPLETE" if done else "RECALLED — SUPPLIES SPENT",
                 "bold bright_green" if done else "bold yellow")
            found = sum(1 for s in exp.sites if s.found)
            line(f"{found}/{len(exp.sites)} contacts resolved", "grey70")
            line("v on a ✦ revisits it", "grey66")
            line("q to return to the ship", "grey66")
        else:
            line("m walk · x dig · t talk", "grey66")
            line("v view find · q return", "grey66")
        return out

    # --- input ------------------------------------------------------------

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
            self.set_cursor(self.cur_x + dx * 8, self.cur_y + dy * 4)
            event.stop()
            return
        pans = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
        if event.key in pans:
            dx, dy = pans[event.key]
            view = self.query_one(ExMapView)
            old_x, old_y = view.cam_x, view.cam_y
            view.pan(dx * 8, dy * 4)
            e = self.exp.config.expedition
            self.cur_x = max(0, min(e.width - 1, self.cur_x + view.cam_x - old_x))
            self.cur_y = max(0, min(e.height - 1, self.cur_y + view.cam_y - old_y))
            self.refresh_ui()
            event.stop()
            return
        handler = {
            "m": self._act_move, "enter": self._act_move,
            "x": self._act_dig, "t": self._act_talk, "v": self._act_view,
            "o": self._act_overlay,
        }.get(event.key)
        if handler is not None:
            handler()
            event.stop()

    def _act_move(self) -> None:
        if ex.do_move(self.exp, self.cur_x, self.cur_y):
            self.query_one(ExMapView).follow(self.exp.explorer.x, self.exp.explorer.y)
        self.drain_events()
        self.refresh_ui()

    def _act_dig(self) -> None:
        site = ex.do_dig(self.exp)
        self.drain_events()
        self.refresh_ui()
        if site is not None:
            if self.on_found is not None:
                self.on_found(site)
            self.app.push_screen(FindModal(site, self.exp.seed, first=True))

    def _act_overlay(self) -> None:
        self.overlay = OVERLAYS[(OVERLAYS.index(self.overlay) + 1) % len(OVERLAYS)]
        self.refresh_ui()

    def _act_talk(self) -> None:
        ex.do_talk(self.exp)
        self.drain_events()
        self.refresh_ui()

    def _act_view(self) -> None:
        site = self.exp.site_at(self.cur_x, self.cur_y)
        if site is not None and site.found:
            self.app.push_screen(FindModal(site, self.exp.seed, first=False))

    def action_quit_expedition(self) -> None:
        self.app.pop_screen()
