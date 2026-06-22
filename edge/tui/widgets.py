"""Reusable widgets for the TUI skeleton: starfield, status sidebar, warp list."""

from __future__ import annotations

import random

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Static

from rich.style import Style

from edge.core.config import SceneArtConfig
from edge.core.enums import Commodity

from edge.tui import art_adapter
from edge.tui.dummy import MapBand, MapDTO, NeighborDTO, PortDTO, SectorDTO, ShipDTO, WarpDTO


class Starfield(Static):
    """A sparse twinkling starfield (UI_MOCKUPS.md §0 / §11 aesthetics).

    Seeded so screenshots are reproducible. `animate=False` (the `--plain` path)
    renders a static field with no twinkle timer.
    """

    DEFAULT_CSS = "Starfield { width: 1fr; height: 1fr; color: $primary; }"
    _CHARS = (".", ".", ".", "·", "*", "+")

    def __init__(self, animate: bool = True, density: float = 0.03, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._animate = animate
        self._density = density
        self._rng = random.Random(7)
        self._stars: dict[tuple[int, int], str] = {}

    def on_mount(self) -> None:
        self._populate()
        if self._animate:
            self.set_interval(0.6, self._twinkle)

    def on_resize(self) -> None:
        self._populate()

    def _populate(self) -> None:
        w, h = self.size.width, self.size.height
        self._stars = {}
        if not w or not h:
            return
        for _ in range(int(w * h * self._density)):
            x, y = self._rng.randrange(w), self._rng.randrange(h)
            self._stars[(x, y)] = self._rng.choice(self._CHARS)
        self.refresh()

    def _twinkle(self) -> None:
        if not self._stars:
            return
        keys = list(self._stars)
        for _ in range(max(1, len(keys) // 8)):
            self._stars[self._rng.choice(keys)] = self._rng.choice((*self._CHARS, " "))
        self.refresh()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if not w or not h:
            return Text("")
        grid = [[" "] * w for _ in range(h)]
        for (x, y), ch in self._stars.items():
            if 0 <= x < w and 0 <= y < h:
                grid[y][x] = ch
        return Text("\n".join("".join(row) for row in grid), style="dim cyan")


def bar(filled: int, total: int = 10) -> str:
    filled = max(0, min(total, filled))
    return "█" * filled + "░" * (total - filled)


def _scaled_bar(qty: int, capacity: int, width: int = 12) -> str:
    filled = round(qty / capacity * width) if capacity else 0
    return bar(filled, width)


# Map the public commodity *display* names back to the core enum, so a trade
# screen can turn the highlighted row into a Trade command.
NAME_TO_COMMODITY = {
    "Fuel Ore": Commodity.FUEL_ORE,
    "Organics": Commodity.ORGANICS,
    "Equipment": Commodity.EQUIPMENT,
}


class TradePanel(Vertical):
    """The commodities trade UI: a live pricing table over the docked port.

    Reusable as the body of the standalone `PortScreen` (a plain commodities
    port) or as the **Commodities** tab of a `StarDockScreen` — so docking at a
    port reaches one trade UI regardless of whether the port is a StarDock
    (UI_MOCKUPS.md §2/§5). `show_title` is suppressed inside the StarDock tab,
    where the screen already carries a banner. `refresh_port` re-renders it after
    a trade; `cursor_commodity` is the highlighted row's commodity name.
    """

    DEFAULT_CSS = "TradePanel { height: auto; }"

    def __init__(self, port: PortDTO, *, latinum: int = 0, show_title: bool = True,
                 **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._port = port
        self._latinum = latinum
        self._show_title = show_title

    def compose(self) -> ComposeResult:
        p = self._port
        if self._show_title:
            yield Static(
                f"[b cyan]TRADEPORT · {p.name} · {p.klass}[/]"
                f"      [dim]Sector {p.display_id}[/]",
                id="port-title",
            )
        yield DataTable(id="commodities", zebra_stripes=True, cursor_type="row")
        yield Static(self._footer_text(), id="port-footer")

    def on_mount(self) -> None:
        table = self.query_one("#commodities", DataTable)
        table.add_columns("Commodity", "They", "Stock", "Price/u", "You", "Action")
        self._fill_rows()

    def _fill_rows(self) -> None:
        table = self.query_one("#commodities", DataTable)
        table.clear()
        for c in self._port.commodities:
            stock = f"{bar(round(c.stock_ratio * 9), 9)} {round(c.stock_ratio * 100):>2}%"
            action = "[b]Sell[/]" if c.mode == "BUY" else "[b]Buy[/]"
            table.add_row(
                c.name, c.mode, stock, f"{c.price} {c.trend}", str(c.player_qty), action
            )

    def _footer_text(self) -> str:
        return (
            "[dim]^ port buys from you (you SELL)   v port sells to you (you BUY)[/]\n"
            f"Latinum [yellow]{self._latinum:,}[/]   ·   [b]T[/]rade highlighted   ·   "
            "[b]H[/]aggle   ·   [b]Esc[/] leave dock"
        )

    def refresh_port(self, port: PortDTO, latinum: int) -> None:
        self._port = port
        self._latinum = latinum
        self._fill_rows()
        self.query_one("#port-footer", Static).update(self._footer_text())

    def cursor_commodity(self) -> str | None:
        row = self.query_one("#commodities", DataTable).cursor_row
        if 0 <= row < len(self._port.commodities):
            return self._port.commodities[row].name
        return None


_CODE_STYLE = {"S": "b magenta", "P": "magenta", "@": "green"}


def _code_markup(codes: list[str]) -> str:
    """Render content tokens (S/P StarDock-port, @ planet) colour-coded by type."""
    return " ".join(f"[{_CODE_STYLE.get(c, 'white')}]{c}[/]" for c in codes)


def _warp_legend() -> str:
    """The warp colour/arrow key shown beneath the sidebar (WP-A)."""
    return (
        "[dim]─ warps ─[/]\n"
        "[cyan]■[/] visited  [magenta]■[/] came-from  [dim]■ unmapped[/]\n"
        "[dim]<< toward Core · -- level · >> deeper[/]"
    )


class NeighborRow(Static):
    """A clickable adjacent-sector row in the sidebar quick-reference (WP-A).

    Clicking warps to the neighbour — it reuses `WarpButton.Warp` so the
    GameScreen's existing `on_warp_button_warp` handler drives both affordances.
    """

    DEFAULT_CSS = """
    NeighborRow { height: 1; }
    NeighborRow:hover { background: $boost; text-style: bold; }
    NeighborRow.unexplored { color: $text-disabled; }
    """

    def __init__(self, neighbor: NeighborDTO, **kwargs: object) -> None:
        super().__init__(self._markup(neighbor), **kwargs)
        self._sector_id = neighbor.sector_id
        if not neighbor.explored:
            self.add_class("unexplored")

    @staticmethod
    def _markup(n: NeighborDTO) -> str:
        if not n.explored:
            return f"  {n.name}"
        codes = _code_markup(n.codes)
        tail = f"  {codes}" if codes else ""
        return f"  {n.name} [dim]({n.band})[/]{tail}"

    def on_click(self) -> None:
        self.post_message(WarpButton.Warp(self._sector_id))


class StatusSidebar(Vertical):
    """Right-hand status readout derived from a ShipDTO (UI_MOCKUPS.md §1).

    A container (not a single Static) so the neighbour quick-reference rows are
    individually clickable warp affordances (WP-A).
    """

    DEFAULT_CSS = """
    StatusSidebar { width: 1fr; padding: 0 1; border-left: solid $primary; }
    StatusSidebar > Static { height: auto; }
    """

    def __init__(self, ship: ShipDTO, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._ship = ship

    def compose(self) -> ComposeResult:
        yield Static(self._stats_markup())
        yield Static("[dim]nearby (click to warp):[/]")
        for neighbor in self._ship.neighbors:
            yield NeighborRow(neighbor)
        yield Static(_warp_legend())

    def _stats_markup(self) -> str:
        s = self._ship
        rule = "[dim]" + "─" * 30 + "[/]"
        lines: list[str] = [
            f"[b cyan]{s.name}[/]  [dim]({s.klass})[/]",
            rule,
        ]
        for a in s.aspects:
            lines.append(f"{a.label:<8}[yellow]{bar(a.filled)}[/]  {a.note}")
        lines += [
            f"[green]subsystems: {s.integrity}[/]",
            rule,
            f"Gun [green]{s.gun}[/]  Missiles x{s.missiles}",
            f"Kits x{s.kits}",
            rule,
            f"Holds {s.holds_used}/{s.holds_total}",
        ]
        for h in s.holds:
            lines.append(f" {h.label:<5}[yellow]{_scaled_bar(h.qty, h.capacity)}[/] {h.qty:>3}")
        lines += [
            f"Colonists {s.colonists:,}/{s.colonist_capacity:,}",
            f"Latinum  [b yellow]{s.latinum:,}[/] slips",
            rule,
            f"Band {s.band}",
            rule,
        ]
        return "\n".join(lines)


class SectorScene(Static):
    """The whole sector scene composited into one grid (UI_MOCKUPS.md §1).

    A starfield base with the header, planet/port (port vertically centred against
    the taller planet), ship sprites, and the discoveries list stamped over it. It
    is one Static because a terminal cell holds a single glyph and Textual does not
    blend overlapping widgets/layers — so the only way to show the starfield
    *behind* the sprites and text is to composite them together here. Sprites'
    negative-space cells are left transparent, so stars show through their gaps.

    Planet / port / ship / unlogged-discovery click targets are recorded as
    ``_hotspots`` and routed as ``ClickableEntry.Picked`` (mirroring the keys).
    """

    DEFAULT_CSS = """
    SectorScene { width: 1fr; height: 1fr; background: transparent; }
    """

    _ORBIT_MARGIN = 3  # blank rows between the planet/port band and the ships row

    def __init__(self, sector: SectorDTO, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._sector = sector
        # (x0, y0, x1, y1, dest, ref) recorded each render; on_click maps a hit to
        # the same ClickableEntry.Picked the keyboard/text affordances post.
        self._hotspots: list[tuple[int, int, int, int, str, int | str | None]] = []

    def on_resize(self) -> None:
        self.refresh()

    def _scene_cfg(self) -> SceneArtConfig:
        return getattr(self.app, "scene_art", None) or SceneArtConfig()

    # --- grid helpers --------------------------------------------------------

    def _starfield(self, w: int, h: int) -> list[list[tuple[str, Style | None]]]:
        """Base grid from the procedural `edge.art` starfield (seeded per sector)."""
        cells = art_adapter.text_to_cells(art_adapter.sprite(
            "starfield", "standard", seed=self._sector.sector_id ^ 0x5EED, width=w, height=h))
        grid: list[list[tuple[str, Style | None]]] = [[(" ", None)] * w for _ in range(h)]
        for y in range(min(h, len(cells))):
            for x in range(min(w, len(cells[y]))):
                ch, style = cells[y][x]
                if ch != " ":
                    grid[y][x] = (ch, style)
        return grid

    @staticmethod
    def _paint(grid: list[list[tuple[str, Style | None]]],
               rows: list[list[tuple[str, Style | None]]], top: int, left: int) -> None:
        h, w = len(grid), len(grid[0])
        for r, row in enumerate(rows):
            y = top + r
            if not 0 <= y < h:
                continue
            for c, (ch, style) in enumerate(row):
                x = left + c
                if ch != " " and 0 <= x < w:  # spaces stay transparent -> stars show
                    grid[y][x] = (ch, style)

    def _stamp_line(self, grid: list[list[tuple[str, Style | None]]], markup: str,
                    row: int, x0: int, span: int) -> None:
        """Stamp one markup line centred within the horizontal span [x0, x0+span).

        Unlike sprites, a text line clears the stars within its own extent (so a
        star can't bleed through a space *inside* a word); stars still show in the
        centring margins to either side.
        """
        line = art_adapter.text_to_cells(Text.from_markup(markup))[0:1]
        cells = line[0] if line else []
        if not (0 <= row < len(grid)):
            return
        w = len(grid[0])
        left = x0 + max(0, (span - len(cells)) // 2)
        for c, (ch, style) in enumerate(cells):
            x = left + c
            if 0 <= x < w:
                grid[row][x] = (ch, style)  # blanks included -> overwrite stars

    def _sprite_cells(self, entity: str, subtype: str, *, seed: int, sw: int, sh: int,
                      facing: str = "right",
                      archetype_id: str | None = None) -> list[list[tuple[str, Style | None]]]:
        return art_adapter.text_to_cells(art_adapter.sprite(
            entity, subtype, seed=seed, width=sw, height=sh, facing=facing,
            archetype_id=archetype_id))

    # --- render --------------------------------------------------------------

    def render(self) -> Text:
        self._hotspots = []
        w, h = self.size.width, self.size.height
        if w < 8 or h < 6:
            return Text("")
        sec = self._sector
        cfg = self._scene_cfg()
        grid = self._starfield(w, h)
        half = w // 2
        row = 0

        # Header — sector + band, flavor, beacon; centred across the full width.
        title = f"[{sec.display_id}] {sec.region}" + (f" ({sec.band})" if sec.band else "")
        self._stamp_line(grid, f"[b cyan]{title}[/]", row, 0, w)
        row += 1
        self._stamp_line(grid, f"[i #8a8a8a]░▒▓ {sec.flavor} ▓▒░[/]", row, 0, w)
        row += 1
        if sec.beacon:
            self._stamp_line(grid, f"[yellow]![/] {sec.beacon}", row, 0, w)
            row += 1
        row += 1  # blank

        # Orbit band — planet (left half) | port (right half). Sizes from config,
        # clamped to the space left below `row` for the margin + ships + discoveries.
        reserved = self._ORBIT_MARGIN + (cfg.ship.max_height + 1) + 3
        ph = max(cfg.planet.min_height,
                 min(cfg.planet.max_height, (half - 2) // 2, h - row - reserved))
        pw = ph * 2  # width locked to 2*height so the disc reads round
        portw = max(cfg.port.min_width, min(cfg.port.max_width, half - 2))
        porth = max(cfg.port.min_height, min(cfg.port.max_height, ph))
        band_h = max(ph, porth)
        lcx, rcx = half // 2, half + half // 2  # column centres
        # Planet (or placeholder), top-aligned in the band.
        if sec.planets:
            planet = sec.planets[0]
            sub = art_adapter.planet_subtype(planet.ptype)
            self._paint(grid, self._sprite_cells("planet", sub, seed=sec.sector_id, sw=pw, sh=ph),
                        row, lcx - pw // 2)
        else:
            self._stamp_line(grid, "[#8a8a8a]no planet[/]", row + band_h // 2, 0, half)
        # Port (or placeholder), vertically centred against the taller planet. The
        # controlling species' palette (`archetype_id`) styles the port sprite.
        if sec.ports:
            port = sec.ports[0]
            sub = art_adapter.port_subtype(port.klass)
            self._paint(grid, self._sprite_cells("port", sub, seed=sec.sector_id, sw=portw,
                                                 sh=porth, archetype_id=port.archetype_id),
                        row + (band_h - porth) // 2, rcx - portw // 2)
        else:
            self._stamp_line(grid, "[#8a8a8a]no port[/]", row + band_h // 2, half, half)
        name_row = row + band_h
        if sec.planets:
            self._stamp_line(grid, f"[b yellow]{sec.planets[0].name}[/]", name_row, 0, half)
            self._hotspots.append((0, row, half, name_row + 1, "planet", None))
        if sec.ports:
            self._stamp_line(grid, f"[b yellow]{sec.ports[0].name}[/]", name_row, half, half)
            self._hotspots.append((half, row, w, name_row + 1, "port", None))
        row = name_row + 1 + self._ORBIT_MARGIN

        # Ships — up to N sprites side by side (no heading), names beneath. The 2nd
        # of a pair may face left so the two face inward (deterministic per sector).
        shown = sec.ships[:cfg.max_ships_shown]
        if shown:
            sw = max(cfg.ship.min_width, min(cfg.ship.max_width, (w - 2) // max(1, len(shown)) - 2))
            # Ship height isn't space-clamped (the layout reserves max_height), so it
            # sits at max_height -- but never below the configured min.
            sh = max(cfg.ship.min_height, cfg.ship.max_height)
            gap = 2
            total = len(shown) * sw + (len(shown) - 1) * gap
            sx = max(0, (w - total) // 2)
            frng = random.Random(sec.sector_id)
            for i, vessel in enumerate(shown):
                entity, sub = art_adapter.ship_entity(vessel.role)
                facing = "left" if (i == 1 and frng.random() < cfg.ship_face_inward_chance) else "right"
                left = sx + i * (sw + gap)
                self._paint(grid, self._sprite_cells(entity, sub, seed=sec.sector_id * 16 + i,
                                                     sw=sw, sh=sh, facing=facing,
                                                     archetype_id=vessel.archetype_id), row, left)
                cid = vessel.contact_id
                tag = " [dim](Hail)[/]" if cid is not None else ""
                self._stamp_line(grid, f"{vessel.name}{tag}", row + sh, left, sw)
                if cid is not None:
                    self._hotspots.append((left, row, left + sw, row + sh + 1, "contact", cid))
            row += sh + 1
        # Overflow ships beyond the sprite cap stay hailable as centred text rows.
        for i in range(cfg.max_ships_shown, len(sec.ships)):
            vessel = sec.ships[i]
            cid = vessel.contact_id
            tag = " [dim](Hail)[/]" if cid is not None else ""
            self._stamp_line(grid, f"[white]>[/] {vessel.name}{tag}", row, 0, w)
            if cid is not None:
                self._hotspots.append((0, row, w, row + 1, "contact", cid))
            row += 1

        # Discoveries — their own row under the ships (clickable = scan).
        row += 1
        self._stamp_line(grid, "[b yellow]Discoveries[/]", row, 0, w)
        row += 1
        if sec.discoveries:
            for d in sec.discoveries:
                if d.collected:
                    self._stamp_line(grid, f"[cyan]✦[/] {d.label} — logged", row, 0, w)
                else:
                    self._stamp_line(grid, f"[cyan]✦[/] {d.label} — unlogged (Scan)", row, 0, w)
                    self._hotspots.append((0, row, w, row + 1, "discovery", d.discovery_id))
                row += 1
        else:
            self._stamp_line(grid, "[#8a8a8a]none[/]", row, 0, w)

        out = Text()
        for y in range(h):
            for ch, style in grid[y]:
                out.append(ch, style=style)
            if y < h - 1:
                out.append("\n")
        return out

    def on_click(self, event: events.Click) -> None:
        x, y = int(event.x), int(event.y)
        for x0, y0, x1, y1, dest, ref in self._hotspots:
            if x0 <= x < x1 and y0 <= y < y1:
                event.stop()
                self.post_message(ClickableEntry.Picked(dest, ref))
                return


class MapBandPanel(Static):
    """One distance-band column on the galactic map (UI_MOCKUPS.md §10).

    A bordered panel whose border-title is the band name; the body is the band's
    pre-rendered rows (sector graph / cluster / rumor pins). Clicking it would
    open the sector inspector in the real game — a stub `Picked` message here.
    """

    class Picked(Message):
        def __init__(self, title: str) -> None:
            self.title = title
            super().__init__()

    def __init__(self, band: MapBand, **kwargs: object) -> None:
        super().__init__("\n".join(band.rows), **kwargs)
        self._title = band.title
        self.border_title = band.title

    def on_click(self) -> None:
        self.post_message(self.Picked(self._title))


class _MapLane(Static):
    """A neutral navigable lane drawn between two band columns (§5/§10)."""

    def __init__(self, glyph: str, **kwargs: object) -> None:
        # One blank lead-in lines the lane up with the bordered panels' bodies,
        # then a run of glyphs spans their height so the lane reads as continuous.
        super().__init__("\n".join(["", *([glyph] * 6)]), **kwargs)


class MapView(Horizontal):
    """The banded galactic map: band columns left→right with lane connectors.

    Bands are laid out Core→Hub→Frontier→Void; a `_MapLane` is inserted before
    any band that declares a neutral-lane glyph, so the always-passable lanes
    between alliance home clusters read as gaps in territory (§5/§10).
    """

    DEFAULT_CSS = """
    MapView { height: 1fr; align-vertical: middle; padding: 1 1; }
    MapView MapBandPanel {
        width: 1fr; height: auto; border: round $primary; padding: 0 1;
        color: $text;
    }
    MapView MapBandPanel:hover { border: round $secondary; }
    MapView _MapLane {
        width: 5; height: auto; color: $secondary;
        text-align: center; content-align: center middle;
    }
    """

    def __init__(self, gmap: MapDTO, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._map = gmap

    def compose(self) -> ComposeResult:
        for band in self._map.bands:
            if band.lane:
                yield _MapLane(band.lane)
            yield MapBandPanel(band)


class ClickableEntry(Static):
    """A clickable line in the sector view (a port or planet) that navigates."""

    DEFAULT_CSS = """
    ClickableEntry { height: 1; }
    ClickableEntry:hover { background: $boost; text-style: bold; }
    """

    class Picked(Message):
        def __init__(self, dest: str, ref: int | str | None = None) -> None:
            self.dest = dest
            self.ref = ref  # an optional target id (e.g. a discovery to salvage)
            super().__init__()

    def __init__(self, markup: str, dest: str, ref: int | str | None = None, **kwargs: object) -> None:
        super().__init__(markup, **kwargs)
        self._dest = dest
        self._ref = ref

    def on_click(self) -> None:
        self.post_message(self.Picked(self._dest, self._ref))

class WarpButton(Button):
    """A single clickable warp affordance."""

    class Warp(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id
            super().__init__()

    def __init__(self, warp: WarpDTO) -> None:
        label = f"{warp.display_id} {warp.arrow}"  # spatial id shown; sector_id is the action
        if warp.label:
            label += f" {warp.label}"
        variant = "primary" if warp.kind == "explored" else "default"
        super().__init__(label, variant=variant)
        self._warp = warp
        if warp.kind == "unexplored":
            self.add_class("unexplored")
        elif warp.kind == "backtrack":
            self.add_class("backtrack")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.Warp(self._warp.sector_id))


class CurrentSectorMarker(Static):
    """Marker for the player's current sector (the grid's centre).

    Not clickable (warping to your own sector is a no-op), but it *is* focusable:
    it is the anchor the warp grid focuses on entry, so the first arrow press moves
    relative to the current sector (Up = the warp rendered directly above it, etc.).
    """

    can_focus = True

    DEFAULT_CSS = """
    CurrentSectorMarker {
        width: 1fr; height: 1; content-align: center middle;
        color: $background; background: $secondary; text-style: bold;
    }
    /* The marker is only a focus anchor for the arrow keys — it should look the
       same focused or not (no highlight). */
    CurrentSectorMarker:focus { color: $background; background: $secondary; text-style: bold; }
    """

    def __init__(self, sector_id: int) -> None:
        super().__init__(f"({sector_id})")


class _EmptyWarpCell(Static):
    DEFAULT_CSS = "_EmptyWarpCell { width: 1fr; height: 1; }"


class WarpGrid(Grid):
    """Outbound warps in a 3x3 grid around the current sector.

    The current sector sits in the centre cell (unclickable); the eight cells
    around it hold warp buttons in order (unexplored ones dimmed). TW2002 sectors
    warp to at most six others, so the eight surrounding cells always suffice;
    any overflow spills into a fourth row.
    """

    _SURROUND = (0, 1, 2, 3, 5, 6, 7, 8)  # the 3x3 cells that aren't the centre
    _COLUMNS = 3

    # Arrow keys move focus between warp buttons by their on-screen grid position
    # (Up = the button rendered above, etc.) — purely spatial, nothing to do with
    # warp gravity. They fire while a warp button is focused (the keys bubble up to
    # the grid) and are hidden from the footer.
    BINDINGS = [
        Binding("up", "move(-1, 0)", show=False),
        Binding("down", "move(1, 0)", show=False),
        Binding("left", "move(0, -1)", show=False),
        Binding("right", "move(0, 1)", show=False),
    ]

    DEFAULT_CSS = """
    WarpGrid {
        grid-size: 3;
        grid-columns: 10;
        grid-rows: 1;
        grid-gutter: 0 1;
        height: auto;
        /* Fixed content width (3 columns x 10 + 2 gutters) so the parent can
           centre the whole grid — Grid does not shrink to content under width:auto,
           and a full-width grid would left-pack the cells off-centre. */
        width: 32;
    }
    WarpGrid WarpButton { width: 1fr; height: 1; border: none !important; }
    WarpGrid WarpButton.unexplored { color: $text-disabled; }
    WarpGrid WarpButton.backtrack { color: $accent; }
    """

    def __init__(self, warps: list[WarpDTO], current_sector: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._warps = warps
        self._current = current_sector

    def compose(self):
        cells: list[Static] = [_EmptyWarpCell() for _ in range(9)]
        cells[4] = CurrentSectorMarker(self._current)
        for slot, warp in zip(self._SURROUND, self._warps):
            cells[slot] = WarpButton(warp)
        yield from cells
        for warp in self._warps[len(self._SURROUND):]:  # rare overflow -> extra row
            yield WarpButton(warp)

    def on_mount(self) -> None:
        # Anchor focus on the current-sector marker (the grid centre) as soon as the
        # grid appears, so the arrow keys drive warp selection immediately — without a
        # priming Tab — and the first press moves *relative to the current sector*.
        # The grid is remounted on every recompose (after a warp/travel/screen-resume),
        # so focus re-homes to the centre each time the sector view refreshes.
        self.call_after_refresh(self._focus_anchor)

    def _focus_anchor(self) -> None:
        marker = next((c for c in self.children if isinstance(c, CurrentSectorMarker)), None)
        if marker is not None:
            marker.focus()

    def action_move(self, drow: int, dcol: int) -> None:
        """Move focus to the next warp button in the (drow, dcol) screen direction.

        Children flow into the fixed-column grid in order, so child index i sits at
        (i // columns, i % columns). The anchor is whichever grid cell holds focus —
        the centre marker on entry, then each warp button as you step. We step one
        cell at a time, skipping the centre marker and empty cells, until we land on
        a warp button or walk off the grid.
        """
        children = list(self.children)
        grid = {(i // self._COLUMNS, i % self._COLUMNS): c for i, c in enumerate(children)}
        pos = {c: rc for rc, c in grid.items()}
        focused = self.app.focused
        if focused not in pos:  # focus drifted off the grid — re-anchor on the centre
            self._focus_anchor()
            return
        row, col = pos[focused]
        max_row = (len(children) - 1) // self._COLUMNS
        row, col = row + drow, col + dcol
        while 0 <= row <= max_row and 0 <= col < self._COLUMNS:
            target = grid.get((row, col))
            if isinstance(target, WarpButton):
                target.focus()
                return
            row, col = row + drow, col + dcol
