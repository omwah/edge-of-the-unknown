"""Reusable widgets for the TUI skeleton: starfield, status sidebar, warp list."""

from __future__ import annotations

import random
from collections.abc import Iterator
from contextlib import contextmanager

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical
from textual.message import Message
from textual.widgets import DataTable, Static

from rich.style import Style

from edge.core.config import SceneArtConfig
from edge.core.dto import SectorDiscovery
from edge.core.enums import Commodity

from edge.tui import art_adapter
from edge.tui.dummy import LocalMapDTO, NavStripDTO, PortDTO, SectorDTO, ShipDTO, WarpDTO


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


@contextmanager
def preserve_cursor(table: DataTable) -> Iterator[None]:
    """Keep the highlighted row stable across a clear()+repopulate refresh.

    Textual's ``DataTable.clear()`` resets the cursor to the top, so repeated
    same-row actions (trading one commodity, surveying one site) would force a
    re-select each time. Save the row index, run the refill, then restore it
    clamped to the new row count.
    """
    saved = table.cursor_row
    yield
    if table.row_count:
        table.move_cursor(row=min(max(saved, 0), table.row_count - 1), animate=False)


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
        with preserve_cursor(table):
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


def warp_legend_markup() -> str:
    """The warp colour/arrow key — shown in the Help modal's Warp Legend (?)."""
    return (
        "[cyan]■[/] visited   [magenta]■[/] came-from   [dim]■ unmapped[/]\n"
        "[dim]<< toward Core   -- level   >> deeper[/]"
    )


class AnomalyRow(Static):
    """A clickable discovery row in the sidebar 'Anomalies' list (§7).

    An unlogged find can be scanned/collected; clicking reuses the existing
    `ClickableEntry.Picked("discovery", id)` the scene used, so the GameScreen
    handler is untouched. A logged find is a plain, non-clickable line.
    """

    DEFAULT_CSS = """
    AnomalyRow { height: 1; }
    AnomalyRow.scan:hover { background: $boost; text-style: bold; }
    """

    def __init__(self, discovery: SectorDiscovery, **kwargs: object) -> None:
        super().__init__(self._markup(discovery), **kwargs)
        self._discovery_id = discovery.discovery_id
        self._scan = not discovery.collected
        if self._scan:
            self.add_class("scan")

    @staticmethod
    def _markup(d: SectorDiscovery) -> str:
        # The find's identity stays hidden until scanned — pre-scan it reads generic.
        if d.collected:
            return f"[cyan]✦[/] {d.label} [dim]— logged[/]"
        return "[cyan]✦[/] Anomaly detected [dim](Scan)[/]"

    def on_click(self) -> None:
        if self._scan:
            self.post_message(ClickableEntry.Picked("discovery", self._discovery_id))


class StatusSidebar(Vertical):
    """Right-hand status readout: ship stats + the sector's Anomalies (UI_MOCKUPS.md §1).

    A container (not a single Static) so each anomaly row is an individually
    clickable scan affordance. The warp quick-reference that used to live here is
    folded into the sector warp grid; the warp legend moved to the Help modal.
    """

    DEFAULT_CSS = """
    StatusSidebar { width: 33; padding: 0 1; border-left: solid $primary; }
    StatusSidebar > Static { height: auto; }
    """

    def __init__(self, ship: ShipDTO, discoveries: list[SectorDiscovery],
                 width: int = 33, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._ship = ship
        self._discoveries = discoveries
        self._width = width

    def on_mount(self) -> None:
        self.styles.width = self._width

    def compose(self) -> ComposeResult:
        yield Static(self._stats_markup())
        yield Static("[b yellow]Anomalies[/]")
        if self._discoveries:
            for discovery in self._discoveries:
                yield AnomalyRow(discovery)
        else:
            yield Static("[#8a8a8a]-----[/]")

    def _stats_markup(self) -> str:
        s = self._ship
        # Divider spans the panel's content width (width minus the left border + padding),
        # so it tracks the configured sidebar width instead of a hardcoded 30.
        rule = "[dim]" + "─" * max(8, self._width - 3) + "[/]"
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
        ]
        return "\n".join(lines)


class _TickerDivider(Static):
    """The ticker's top divider — a horizontal rule with a right-aligned expand/collapse
    toggle (▲ to expand up to 5 lines, ▼ to shrink back to one). Clicking it toggles."""

    DEFAULT_CSS = "_TickerDivider { height: 1; color: $primary; }"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._expanded = False

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.refresh()

    def render(self) -> Text:
        width = max(1, self.size.width)
        glyph = "∨∨" if self._expanded else "∧∧"
        rule = "─" * (width - 3) + glyph + "─"
        return Text(rule, style="dim")

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(Ticker.Toggle())


class Ticker(Vertical):
    """The bottom event ticker (UI_MOCKUPS.md §1).

    Collapsed it shows only the most recent log line under a divider; clicking the
    divider's ▲ indicator expands it to overlay the screen with the last five lines
    (▼ shrinks it back). It rides a higher layer when expanded, so growing upward
    draws *over* the sector view rather than reflowing it.
    """

    class Toggle(Message):
        pass

    DEFAULT_CSS = """
    Ticker { height: 2; background: $surface; padding: 0 1; }
    /* Expanded, it rides the overlay layer docked to the bottom, so it grows upward
       *over* the sector view instead of reflowing it (the screen declares the layer). */
    Ticker.expanded { height: 6; layer: overlay; dock: bottom; }
    Ticker #ticker-body { height: 1fr; color: $text; }
    """

    def __init__(self, lines: list[str], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._lines = lines
        self._expanded = False

    def compose(self) -> ComposeResult:
        yield _TickerDivider(id="ticker-divider")
        yield Static(self._body_text(), id="ticker-body")

    def _body_text(self) -> str:
        count = 5 if self._expanded else 1
        return "\n".join(self._lines[-count:])

    def on_ticker_toggle(self, msg: Ticker.Toggle) -> None:
        msg.stop()
        self._expanded = not self._expanded
        self.set_class(self._expanded, "expanded")
        self.query_one("#ticker-divider", _TickerDivider).set_expanded(self._expanded)
        self.query_one("#ticker-body", Static).update(self._body_text())


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
        # A sector with a visible discovery has no planet (bigbang keeps space finds
        # off planet sectors), so the find takes the planet slot. A wormhole is the
        # preferred primary — it's the navigable one. Centre it across the whole view
        # when there's no port; otherwise keep it in the left (planet) half.
        disc = None
        if sec.discoveries and not sec.planets:
            disc = next((d for d in sec.discoveries if d.kind == "wormhole"), sec.discoveries[0])
        disc_centered = disc is not None and not sec.ports
        # Planet (or placeholder), top-aligned in the band.
        if sec.planets:
            planet = sec.planets[0]
            sub = art_adapter.planet_subtype(planet.ptype)
            # Seed off the planet's own id (not the sector's) so this sprite matches the
            # PlanetScreen orbit view, which seeds with planet_id — same planet, same art.
            self._paint(grid, self._sprite_cells("planet", sub, seed=planet.planet_id, sw=pw, sh=ph),
                        row, lcx - pw // 2)
        elif disc is not None:
            dleft = (w // 2 - pw // 2) if disc_centered else (lcx - pw // 2)
            self._paint(grid, self._sprite_cells("discovery", disc.kind, seed=sec.sector_id, sw=pw, sh=ph),
                        row, dleft)

        # Port (or placeholder), vertically centred against the taller planet. The
        # controlling species' palette (`archetype_id`) styles the port sprite.
        if sec.ports:
            port = sec.ports[0]
            sub = art_adapter.port_subtype(port.klass)
            self._paint(grid, self._sprite_cells("port", sub, seed=sec.sector_id, sw=portw,
                                                 sh=porth, archetype_id=port.archetype_id),
                        row + (band_h - porth) // 2, rcx - portw // 2)

        name_row = row + band_h
        if sec.planets:
            self._stamp_line(grid, f"[b yellow]{sec.planets[0].name}[/]", name_row, 0, half)
            self._hotspots.append((0, row, half, name_row + 1, "planet", None))
        elif disc is not None:
            # No caption until scanned — a sensor sweep (sidebar/Z) reveals the identity.
            span = w if disc_centered else half
            if disc.collected:
                self._stamp_line(grid, f"[b cyan]{disc.label}[/]", name_row, 0, span)
            if disc.kind == "wormhole" and disc.warp_to is not None:
                dest, ref = "wormhole", disc.warp_to  # click warps to the far side
            else:
                dest, ref = "discovery", disc.discovery_id  # click scans/salvages
            self._hotspots.append((0, row, span, name_row + 1, dest, ref))
        if sec.ports:
            self._stamp_line(grid, f"[b yellow]{sec.ports[0].name}[/]", name_row, half, half)
            self._hotspots.append((half, row, w, name_row + 1, "port", None))
        row = name_row + 1 + self._ORBIT_MARGIN

        # Ships — up to N sprites side by side (no heading), names beneath. The 2nd
        # of a pair may face left so the two face inward (deterministic per sector).
        shown = sec.ships[:cfg.max_ships_shown]
        if shown:
            n = len(shown)
            sw = max(cfg.ship.min_width, min(cfg.ship.max_width, (w - 2) // max(1, n) - 2))
            # Ship height isn't space-clamped (the layout reserves max_height), so it
            # sits at max_height -- but never below the configured min.
            sh = max(cfg.ship.min_height, cfg.ship.max_height)
            col_w = w / n  # one equal-width column per ship
            frng = random.Random(sec.sector_id)
            for i, vessel in enumerate(shown):
                entity, sub = art_adapter.ship_entity(vessel.role)
                facing = "left" if (i == 1 and frng.random() < cfg.ship_face_inward_chance) else "right"
                # Centre each ship within its own column, so a pair sits at the middle of
                # its half rather than clustering against the other in the centre.
                left = max(0, int(i * col_w + (col_w - sw) / 2))
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

        # (Discoveries are listed in the sidebar's "Anomalies" panel, not the scene.)

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


class LocalMapView(Static):
    """The local sector ego-graph (Computer/Map screen → §10, §11).

    A node-and-edge graph of the player's surrounding sectors, centered on the
    current sector and laid out in gravity columns (toward-Core left, deeper
    right). The rows + legend are baked server-side (`session.map_view`); this
    widget just renders them and can re-render to overlay a freshly plotted route
    via `update_map`. Clicking a sector node posts `Picked(sector_id)` so the
    screen can plot a route to it.
    """

    DEFAULT_CSS = """
    LocalMapView { height: auto; padding: 1 2; }
    """

    class Picked(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id  # internal id of the clicked sector
            super().__init__()

    def __init__(self, gmap: LocalMapDTO, **kwargs: object) -> None:
        super().__init__(self._content(gmap), **kwargs)
        self._map = gmap

    @staticmethod
    def _content(gmap: LocalMapDTO) -> str:
        body = "\n".join(gmap.rows) if gmap.rows else "[dim]no charted neighbours[/]"
        return f"{body}\n\n{gmap.legend}" if gmap.legend else body

    def update_map(self, gmap: LocalMapDTO) -> None:
        self._map = gmap
        self.update(self._content(gmap))

    def on_click(self, event: events.Click) -> None:
        # Click coords are relative to the widget box; shift past the padding to land
        # in the baked `rows` grid, then hit-test the node label boxes.
        pad = self.styles.padding
        col, row = int(event.x) - pad.left, int(event.y) - pad.top
        for node in self._map.nodes:
            if node.row == row and node.col0 <= col < node.col1:
                event.stop()
                self.post_message(self.Picked(node.sector_id))
                return


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

class WarpCell(Static):
    """One outbound warp — the single, information-rich warp affordance (§5.1).

    Focusable (arrow-key navigable) and clickable. Renders, left-justified, the
    spatial id, the gravity arrow as the separator, and the region name + band;
    the port/planet `codes` are right-justified against the cell's right edge.
    Colour follows `kind` (visited / came-from / unmapped) via CSS classes.
    """

    can_focus = True

    class Warp(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id
            super().__init__()

    # Enter/Space activate the focused cell (it's a Static, not a Button, so it needs
    # its own keys — the arrow keys that move focus are bound on the parent grid).
    BINDINGS = [
        Binding("enter", "warp", "Warp", show=False),
        Binding("space", "warp", "Warp", show=False),
    ]

    DEFAULT_CSS = """
    WarpCell { width: 1fr; height: 1; padding: 0 1; color: $primary; }
    WarpCell.unexplored { color: $text-disabled; }
    WarpCell.backtrack { color: $accent; }
    WarpCell:hover { background: $boost; }
    """

    def __init__(self, warp: WarpDTO, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._warp = warp
        if warp.kind == "unexplored":
            self.add_class("unexplored")
        elif warp.kind == "backtrack":
            self.add_class("backtrack")

    def render(self) -> Text:
        w = self._warp
        name = w.label or "—"
        left = Text.from_markup(f"{w.display_id} {w.arrow} {name}")
        if w.band:
            # Drop the band's dim when focused, else `reverse` turns it into a darker
            # background shade than the rest of the label (uneven highlight).
            left.append(f" ({w.band})", style="" if self.has_focus else "dim")
        if self.has_focus:
            left.stylize("reverse bold")  # invert just the warp text, not the whole grid cell
        codes = _code_markup(w.codes)
        right = Text.from_markup(codes) if codes else Text("")
        # Left-justify the warp text, right-justify the codes; pad between to fill the
        # printable cell width (account for the 1-cell horizontal padding each side).
        width = max(0, self.size.width - 2)
        gap = width - left.cell_len - right.cell_len
        if gap < 1:  # no room for the codes — drop them rather than overflow/wrap
            left.truncate(width, overflow="ellipsis")
            return left
        left.append(" " * gap)
        left.append_text(right)
        return left

    def on_click(self) -> None:
        self.action_warp()

    def on_focus(self) -> None:
        self.refresh()  # repaint so the focused-text inversion in render() applies

    def on_blur(self) -> None:
        self.refresh()

    def action_warp(self) -> None:
        self.post_message(self.Warp(self._warp.sector_id))


class SectionRule(Static):
    """A full-width horizontal rule with a centred caption laid over the line."""

    DEFAULT_CSS = "SectionRule { height: 1; color: $primary; }"

    def __init__(self, label: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._label = label

    def render(self) -> Text:
        width = max(1, self.size.width)
        cap = f" {self._label} "
        dashes = max(0, width - len(cap))
        left = dashes // 2
        out = Text()
        out.append("─" * left, style="dim")
        out.append(cap, style="bold")
        out.append("─" * (dashes - left), style="dim")
        return out


class WarpGrid(Grid):
    """Outbound warps laid out in a configurable-width grid (§5.1, §11).

    Cells fill the printable area and wrap into rows (`columns` wide); TW2002 sectors
    warp to at most `max_warps_per_sector` others. There is no current-sector cell —
    the warps *are* the grid. The grid reserves `min_rows` rows (= ceil(max warps /
    columns)) so its height is the same in every sector regardless of warp count.
    Keyboard focus lands on a cell chosen by `focus_default` (first / came-from /
    first unexplored); arrow keys step between cells, Enter/Space activates the focus.
    """

    # Arrow keys move focus between warp cells by their on-screen grid position
    # (Up = the cell rendered above, etc.). They fire while a cell is focused (the keys
    # bubble up to the grid) and are hidden from the footer.
    BINDINGS = [
        Binding("up", "move(-1, 0)", show=False),
        Binding("down", "move(1, 0)", show=False),
        Binding("left", "move(0, -1)", show=False),
        Binding("right", "move(0, 1)", show=False),
    ]

    DEFAULT_CSS = """
    WarpGrid {
        grid-rows: 1;
        grid-gutter: 0 1;
        height: auto;
        width: 1fr;  /* full warp-area width; cell size derives from columns (§5.1) */
    }
    """

    def __init__(
        self, warps: list[WarpDTO], columns: int = 3, focus_default: str = "first",
        min_rows: int = 1, **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._warps = warps
        self._columns = max(1, columns)
        self._focus_default = focus_default
        self._min_rows = max(1, min_rows)

    def compose(self) -> ComposeResult:
        for warp in self._warps:
            yield WarpCell(warp)

    def on_mount(self) -> None:
        self.styles.grid_size_columns = self._columns
        # Reserve a consistent height: the rows the full warp cap would need, so the
        # grid (and thus the sector scene above it) doesn't resize per sector. Each row
        # is 1 tall with no row gutter, so height in cells == row count.
        used_rows = -(-len(self._warps) // self._columns)  # ceil
        self.styles.height = max(self._min_rows, used_rows)
        # Anchor focus as soon as the grid appears, so arrow keys drive selection
        # immediately (no priming Tab). The grid is remounted on every recompose, so
        # focus re-homes each time the sector view refreshes.
        self.call_after_refresh(self._focus_anchor)

    def _focus_anchor(self) -> None:
        cells = [c for c in self.children if isinstance(c, WarpCell)]
        if not cells:
            return
        target = cells[0]
        if self._focus_default == "backtrack":
            target = next((c for c in cells if c._warp.kind == "backtrack"), cells[0])
        elif self._focus_default == "unexplored":
            target = next((c for c in cells if c._warp.kind == "unexplored"), cells[0])
        target.focus()

    def action_move(self, drow: int, dcol: int) -> None:
        """Move focus to the next warp cell in the (drow, dcol) screen direction.

        Children flow into the fixed-column grid in order, so child index i sits at
        (i // columns, i % columns). We step one cell at a time from the focused cell
        until we land on another warp cell or walk off the grid.
        """
        children = list(self.children)
        grid = {(i // self._columns, i % self._columns): c for i, c in enumerate(children)}
        pos = {c: rc for rc, c in grid.items()}
        focused = self.app.focused
        if focused not in pos:  # focus drifted off the grid — re-anchor
            self._focus_anchor()
            return
        row, col = pos[focused]
        max_row = (len(children) - 1) // self._columns
        row, col = row + drow, col + dcol
        while 0 <= row <= max_row and 0 <= col < self._columns:
            target = grid.get((row, col))
            if isinstance(target, WarpCell):
                target.focus()
                return
            row, col = row + drow, col + dcol


class NavRose(Static):
    """The always-visible nav rose — the sole main-screen warp affordance (§11).

    A compact bearing-placed compass baked server-side (`session.game_view` →
    `navstrip.build_nav_strip`): the player (`@`) centred, each outbound warp in the
    octant of its real bearing, a fixed `Core` anchor for global orientation, and a
    recent-route breadcrumb. This widget renders the baked rows verbatim, highlights
    the keyboard-selected warp (a style span over its baked cell — canvas columns line
    up with `Text.from_markup` offsets), shows its detail line, and warps on click or
    Enter. Replaces the old flat `WarpGrid`; one click / keypress = one warp.
    """

    can_focus = True

    class Picked(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id  # internal id of the chosen warp target
            super().__init__()

    BINDINGS = [
        Binding("up", "move(-1)", show=False),
        Binding("left", "move(-1)", show=False),
        Binding("down", "move(1)", show=False),
        Binding("right", "move(1)", show=False),
        Binding("enter", "warp", "Warp", show=False),
        Binding("space", "warp", "Warp", show=False),
    ]

    DEFAULT_CSS = "NavRose { height: auto; padding: 0 1; }"

    def __init__(self, nav: NavStripDTO, warps: list[WarpDTO], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._nav = nav
        self._warps = {w.sector_id: w for w in warps}
        # Cycle order runs top-to-bottom, left-to-right around the rose.
        self._hits = sorted(nav.nodes, key=lambda n: (n.row, n.col0))
        self._idx = 0

    def on_mount(self) -> None:
        # Grab focus as the rose appears so arrow keys drive selection immediately
        # (no priming Tab); re-homes on each recompose, as the old warp grid did.
        if self._hits:
            self.call_after_refresh(self.focus)

    def render(self) -> Text:
        focus_node = self._hits[self._idx] if self._hits else None
        lines: list[Text] = []
        for i, row in enumerate(self._nav.rows):
            line = Text.from_markup(row)
            if focus_node is not None and self.has_focus and focus_node.row == i:
                line.stylize("reverse bold", focus_node.col0, focus_node.col1)
            lines.append(line)
        out = Text("\n").join(lines)
        out.append("\n\n")
        out.append_text(self._trail_line())
        out.append("\n")
        out.append_text(self._detail_line(focus_node))
        if self._nav.legend:
            out.append("\n")
            out.append_text(Text.from_markup(self._nav.legend))
        return out

    def _trail_line(self) -> Text:
        if not self._nav.trail:
            return Text("trail: —", style="dim")
        line = Text("trail: ", style="dim")
        line.append(" › ".join(str(c) for c in self._nav.trail), style="dim")
        line.append(" › ", style="dim")
        line.append("[you]", style="bold")
        return line

    def _detail_line(self, focus_node: object) -> Text:
        if focus_node is None:
            return Text("no warps out of here", style="dim")
        node = self._hits[self._idx]
        warp = self._warps.get(node.sector_id)
        line = Text("▶ ", style="bold")
        line.append(f"{node.display_id}  ", style="bold")
        if warp is None or not warp.explored:
            line.append("uncharted", style="dim")
        else:
            codes = " " + "".join(warp.codes) if warp.codes else ""
            line.append(f"{warp.label or '—'} · {warp.band}{codes}")
        line.append("     (↵ to warp)", style="dim")
        return line

    def action_move(self, step: int) -> None:
        if self._hits:
            self._idx = (self._idx + step) % len(self._hits)
            self.refresh()

    def action_warp(self) -> None:
        if self._hits:
            self.post_message(self.Picked(self._hits[self._idx].sector_id))

    def on_click(self, event: events.Click) -> None:
        pad = self.styles.padding
        col, row = int(event.x) - pad.left, int(event.y) - pad.top
        for i, node in enumerate(self._hits):
            if node.row == row and node.col0 <= col < node.col1:
                event.stop()
                self._idx = i
                self.refresh()
                self.post_message(self.Picked(node.sector_id))
                return

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()
