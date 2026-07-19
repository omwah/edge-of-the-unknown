"""Local sector ego-graph layout for the Computer → Map tab (§10, §11). Pure.

Lays out the player's surrounding sectors as a small ASCII node-and-edge graph
**centered on the current sector**, arranged in *gravity columns* — toward the
Core on the left, deeper into space on the right (the `<<`/`>>` convention from
the warp list). Nodes are tinted by distance band, fog of war masks unexplored
neighbours, and a passed-in route lights up its path. The output is a list of
Rich-markup row strings the TUI renders verbatim (the established baked-rows
contract) plus a one-line legend.

Deterministic and I/O-free: a function of `(state, player, radius, route)` only,
so it reconstructs identically under `(seed, command log)`. A simplification keeps
the layout tractable: `core_hops` is a BFS distance from the Core, so a *two-way*
warp joins sectors differing by at most one hop — those edges span the same gravity
column or an adjacent one. A **one-way** warp has no return edge to bound it, so its
ends can sit many columns apart; such a long edge is drawn along one end's row and
severed where it would read as passing *through* an unrelated node (see `_draw_edges`).

The dense ``spiral`` topology is the exception to gravity-column grouping: many
nearby sectors intentionally share one Core-hop radius.  Its generated
``sector_pos`` coordinates are projected into radial/tangential displacement from
the current sector, preserving Coreward-left/outward-right while spreading a ring
around the vertical axis instead of stacking it into one enormous column.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence

from edge.core import corp
from edge.core import dto
from edge.core.enums import PortClass
from edge.core.models import Player, UniverseState
from edge.server.canvas import BAND_COLOR as _BAND_COLOR
from edge.server.canvas import HERE_STYLE as _HERE_STYLE
from edge.server.canvas import Canvas as _Canvas

# Fallback reach (in warp hops) when no config is supplied; the live value comes
# from `ui.local_map_radius` (config). A presentation tuning, not a game rule.
LOCAL_RADIUS = 3

# Upper bound on the reach the fit-to-width search will try (so a very wide terminal
# can't grow the ego-graph without limit). A presentation tuning, not a game rule.
MAX_FIT_RADIUS = 20

# Width-only fitting lets a dense graph keep growing while hundreds of nodes pile
# into a few columns.  Derive a conservative viewport-height proxy from width: an
# 80-column compact map gets 16 rows, scaling to at most 31 on wide terminals.
_FIT_ASPECT_DIVISOR = 5
_MIN_FIT_ROWS = 15
_MAX_FIT_ROWS = 31

_CELL_GAP = 5  # blank columns between node columns — room for edge connectors
_VSTEP = 2  # blank rows between stacked nodes in a column

_ROUTE_STYLE = "bold yellow"
_UNEXPLORED_STYLE = "dim"  # a sector whose id is known (warp list shows it) but is uncharted
_ONEWAY_STYLE = "dim"  # a warp with no return edge (one-way), drawn faintly

# Per-content-code tint, so a node's contents read in the same colours as the legend
# (PT-50). The `(id)` keeps the band/here/route/unexplored style; only these trailing
# code glyphs are recoloured. Must stay in step with `_codes` and `LEGEND`.
_CODE_STYLE: dict[str, str] = {
    "S": "magenta", "P": "magenta", "@": "green", "#": "cyan", "×": "red",
}

LEGEND = (
    "[reverse bold cyan]@[/] you   [bold yellow]*[/] route   ─ warp   "
    "[magenta]P[/]/[magenta]S[/] port   [green]@[/] planet   [cyan]#[/] starbase   "
    "[red]×[/] forces   [dim](n)[/] unexplored"
)


def _local_bfs(state: UniverseState, src: int, radius: int) -> dict[int, int]:
    """Sectors within `radius` out-hops of `src` (inclusive), → hop distance."""
    seen: dict[int, int] = {src: 0}
    queue: deque[int] = deque([src])
    while queue:
        node = queue.popleft()
        if seen[node] >= radius:
            continue
        for nxt in state.adjacency.get(node, ()):  # out-edges only (where you can go)
            if nxt not in seen and nxt in state.sectors:
                seen[nxt] = seen[node] + 1
                queue.append(nxt)
    return seen


def _codes(state: UniverseState, sector_id: int, player: Player | None = None) -> str:
    """Short content tokens for an explored sector (mirrors session._sector_codes):
    port (S/P), planet (@), starbase (#), known forces (× — classic fog: fighters are
    public, mines only your own)."""
    out = ""
    port = state.port_in_sector(sector_id)
    if port is not None:
        out += "S" if port.klass is PortClass.STARDOCK else "P"
    if any(pl.sector_id == sector_id for pl in state.planets.values()):
        out += "@"
    if any(b.sector_id == sector_id for b in state.starbases.values()):
        out += "#"
    force = state.sector_forces.get(sector_id)
    if force is not None and (force.fighters > 0 or (
            player is not None
            and (force.armid_mines > 0 or force.limpet_mines > 0)
            and corp.player_owns(state, force.owner, player.id))):
        out += "×"
    return out


def _label(state: UniverseState, player: Player, sector_id: int, here: int) -> str:
    """The node's display text: `(id)` plus content codes once charted.

    The spatial id is always shown — the warp list already reveals where a warp
    leads, so the map matches it — but an unexplored sector's contents stay fogged
    (no port/planet codes), and it renders faintly (see `_UNEXPLORED_STYLE`).
    """
    disp = state.spatial_ids.get(sector_id, sector_id)
    if sector_id == here:
        return f"({disp}@)"
    if sector_id not in player.explored_sectors:
        return f"({disp})"
    return f"({disp}){_codes(state, sector_id, player)}"


def build_local_map(
    state: UniverseState, player: Player, *, radius: int = LOCAL_RADIUS,
    route: Sequence[int] = (), max_width: int | None = None,
) -> tuple[list[str], str, list[dto.MapNodeDTO]]:
    """Bake the local ego-graph rows (and legend) centered on the player's sector.

    `route` is the internal sector-id path (origin..dest) of a plotted course; any
    of its sectors that fall inside the local view light up, and a destination
    beyond the shown reach gets a directional pointer line so it still reads.

    When `max_width` is given (the Computer/Map tab's available character width), the
    reach is **grown to fit the screen**: the largest hop-radius whose laid-out width
    fits `max_width` is used, so the map shows as many sectors as the width allows
    (falling back to reach 1 when even that overflows). Otherwise the fixed `radius`
    is used (the standalone-map / test path).
    """
    if max_width is None:
        rows, legend, hits, _w = _build_at_radius(state, player, radius, route)
        return rows, legend, hits
    best: tuple[list[str], str, list[dto.MapNodeDTO], int] | None = None
    best_nodes = -1
    max_rows = max(
        _MIN_FIT_ROWS,
        min(_MAX_FIT_ROWS, max_width // _FIT_ASPECT_DIVISOR),
    )
    for r in range(1, MAX_FIT_RADIUS + 1):
        cand = _build_at_radius(state, player, r, route)
        rows, _legend, hits, width = cand
        if width <= max_width and len(rows) <= max_rows and len(hits) >= best_nodes:
            best, best_nodes = cand, len(hits)
        if width > max_width or len(rows) > max_rows:
            break  # wider reach only grows the laid-out graph — stop expanding
    if best is None:  # even reach 1 overflows the width; show it anyway
        best = _build_at_radius(state, player, 1, route)
    return best[0], best[1], best[2]


def _layout_map_nodes(
    state: UniverseState, player: Player, here: int, radius: int,
) -> tuple[dict[int, tuple[int, int]], dict[int, int], int, list[int], dict[int, int], int, int, int]:
    """Topologically lays out local map nodes.
    Returns:
      placed: dict[int, tuple[int, int]] -> sector_id to (row, col_x)
      hops: dict[int, int] -> sector_id to distance
      cell_w: int -> width of a cell
      present: list[int] -> sorted column offsets
      col_x: dict[int, int] -> column offset to x coordinate
      center_row: int -> row index of center/player
      width: int -> total layout width
      height: int -> total layout height
    """
    came_from = player.entered_from.get(here)
    hops = _local_bfs(state, here, radius)
    if came_from is not None and came_from in state.sectors:
        hops.setdefault(came_from, 1)  # the way back is always worth showing
    # The immediate ring is always shown; beyond it only charted sectors appear.
    if radius > 1:
        hops = {n: d for n, d in hops.items() if d <= 1 or n in player.explored_sectors}
    here_core = state.core_hops.get(here, 0)

    def spiral_axes(node: int) -> tuple[float, float] | None:
        """Return (radial, tangential) displacement in the spiral's local frame."""
        if state.topology_mode != "spiral":
            return None
        here_pos = state.sector_pos.get(here)
        node_pos = state.sector_pos.get(node)
        if here_pos is None or node_pos is None:
            return None
        hx, hy = here_pos
        length = math.hypot(hx, hy)
        outward_x, outward_y = ((1.0, 0.0) if length == 0.0
                                 else (hx / length, hy / length))
        dx, dy = node_pos[0] - hx, node_pos[1] - hy
        radial = dx * outward_x + dy * outward_y
        tangential = dx * -outward_y + dy * outward_x
        return radial, tangential

    # Group ordinary topologies into gravity columns. Spiral mode instead projects
    # its exact ring coordinates onto the current sector's outward radial axis.
    columns: dict[int, list[int]] = {}
    for node in hops:
        axes = spiral_axes(node)
        offset = (round(axes[0]) if axes is not None
                  else state.core_hops.get(node, here_core) - here_core)
        offset = max(-radius, min(radius, offset))
        columns.setdefault(offset, []).append(node)
    present = sorted(columns)

    # Undirected adjacency over the visible set, for barycentre ordering.
    vis_adj: dict[int, set[int]] = {n: set() for n in hops}
    for a in hops:
        for b in state.adjacency.get(a, ()):
            if b in vis_adj:
                vis_adj[a].add(b)
                vis_adj[b].add(a)

    cell_w = max((len(_label(state, player, n, here)) for n in hops), default=4)
    col_x = {off: i * (cell_w + _CELL_GAP) for i, off in enumerate(present)}
    kmax = max((len(v) for v in columns.values()), default=1)
    height = (kmax - 1) * _VSTEP + 3
    center_row = height // 2
    width = len(present) * cell_w + max(0, len(present) - 1) * _CELL_GAP

    placed: dict[int, tuple[int, int]] = {}

    def barycentre(node: int) -> float:
        """Mean row of this node's already-placed neighbours (re-uses gravity order)."""
        rows = [placed[m][0] for m in vis_adj[node] if m in placed]
        return sum(rows) / len(rows) if rows else float(center_row)

    # Place columns centre-outward
    for off in sorted(present, key=lambda o: (abs(o), o)):
        def row_order(node: int) -> tuple[float, int]:
            axes = spiral_axes(node)
            primary = axes[1] if axes is not None else barycentre(node)
            return primary, state.spatial_ids.get(node, node)

        nodes = sorted(columns[off], key=row_order)
        if off == 0 and here in nodes:  # keep the current sector dead-centre
            nodes.remove(here)
            nodes.insert(len(nodes) // 2, here)
        count = len(nodes)
        for i, node in enumerate(nodes):
            row = center_row + round((i - (count - 1) / 2) * _VSTEP)
            placed[node] = (row, col_x[off])

    return placed, hops, cell_w, present, col_x, center_row, width, height


def _build_at_radius(
    state: UniverseState, player: Player, radius: int, route: Sequence[int],
) -> tuple[list[str], str, list[dto.MapNodeDTO], int]:
    """Lay out the ego-graph at a fixed `radius`; returns rows/legend/nodes + its width."""
    here = state.ships[player.ship_id].sector_id
    route_set = set(route)

    placed, hops, cell_w, present, col_x, center_row, width, height = _layout_map_nodes(
        state, player, here, radius
    )

    canvas = _Canvas(width, height)
    occupied: set[tuple[int, int]] = set()  # node-label cells, off-limits to connectors
    boxes: list[tuple[int, int, int, int]] = []  # (sector_id, canvas_row, col0, col1)
    spans: dict[int, tuple[int, int, int]] = {}  # sector_id -> (row, col0, col1)

    for node, (row, x) in placed.items():
        label = _label(state, player, node, here)
        if node == here:
            style: str | None = _HERE_STYLE
        elif node in route_set:
            style = _ROUTE_STYLE
        elif node not in player.explored_sectors:
            style = _UNEXPLORED_STYLE
        else:
            style = _BAND_COLOR.get(state.sectors[node].distance_band)
        canvas.put(row, x, label, style)
        # Recolour the trailing content codes to match the legend (PT-50); the `(id)`
        # keeps `style`. Only charted, non-here nodes carry codes (see `_label`).
        if node != here and node in player.explored_sectors:
            codes = _codes(state, node, player)
            base = len(label) - len(codes)
            for k, ch in enumerate(codes):
                canvas.put(row, x + base + k, ch, _CODE_STYLE.get(ch, style))
        occupied.update((row, x + k) for k in range(len(label)))
        spans[node] = (row, x, x + len(label))
        if node != here:  # the current sector isn't a route target
            boxes.append((node, row, x, x + len(label)))

    _draw_edges(state, canvas, placed, cell_w, route, occupied, spans)

    rows = canvas.rows()
    trim = 0
    while rows and rows[0] == "":  # trim leading blank rows (trailing already trimmed)
        rows.pop(0)
        trim += 1
    pointer = _pointer_line(state, route, hops)
    if pointer:
        rows.append(pointer)
    hits = [
        dto.MapNodeDTO(sector_id=sid, display_id=state.spatial_ids.get(sid, sid),
                       row=row - trim, col0=c0, col1=c1,
                       neighbors=frozenset(state.adjacency.get(sid, ())))
        for sid, row, c0, c1 in boxes if row - trim >= 0
    ]
    return rows, LEGEND, hits, width


# Glyphs whose drawn strokes reach toward a horizontal neighbour: a cell with a
# RIGHT arm chains into a label on its right; a LEFT arm into a label on its left.
_RIGHT_ARM = frozenset("─╭╰")
_LEFT_ARM = frozenset("─╮╯")


def _draw_edges(
    state: UniverseState, canvas: _Canvas, placed: dict[int, tuple[int, int]],
    cell_w: int, route: Sequence[int], occupied: set[tuple[int, int]],
    spans: dict[int, tuple[int, int, int]],
) -> None:
    """Connect placed nodes; route legs are drawn in the route highlight.

    Most warp-connected pairs share the same gravity column or an adjacent one
    (BFS neighbours differ by ≤1 Core hop), so an edge is a vertical run or a single
    stepped connector across one gap. **One-way** warps are the exception: with no
    return edge to bound the other direction, their endpoints can sit many columns
    apart, and such an edge is drawn as a long line along one endpoint's row.

    Connectors never overwrite node-label cells (`occupied`). But a line running
    along a non-endpoint node's row would resume on the far side of that label and
    *read* as connecting through it (PT-56). So after drawing, any connector cell
    that abuts a label whose sector is **not** one of the edge's endpoints is erased,
    leaving a one-cell gap so the line clearly passes *behind* the node — the
    occupied-margin the note calls for, applied only where a foreign wire intrudes.
    """
    route_legs = {(route[i], route[i + 1]) for i in range(len(route) - 1)}
    route_legs |= {(b, a) for a, b in route_legs}  # undirected, for drawing
    edges: list[tuple[int, int]] = []
    drawn: set[frozenset[int]] = set()
    for a in placed:
        for b in state.adjacency.get(a, ()):
            if b in placed and (key := frozenset((a, b))) not in drawn:
                drawn.add(key)
                edges.append((a, b))

    # Which edges (as endpoint pairs) painted each connector cell — a cell may be
    # shared by several, so a node's own edge keeps a cell even where a foreign line
    # crosses it. Route legs are re-drawn last (highlight wins), so record then too.
    owners: dict[tuple[int, int], set[frozenset[int]]] = {}

    def paint(y: int, x: int, ch: str, style: str | None, edge: frozenset[int]) -> None:
        if (y, x) in occupied:
            return  # a label cell — never a connector
        canvas.put(y, x, ch, style, protect=occupied)
        owners.setdefault((y, x), set()).add(edge)

    # Draw route legs last so the highlight wins on cells shared with plain edges.
    for a, b in sorted(edges, key=lambda e: e in route_legs):
        edge = frozenset((a, b))
        ay, ax = placed[a]
        by, bx = placed[b]
        one_way = a not in state.adjacency.get(b, ())  # reverse edge absent
        if (a, b) in route_legs:
            style: str | None = _ROUTE_STYLE
        elif one_way:
            style = _ONEWAY_STYLE
        else:
            style = None
        if ax == bx:  # same column → vertical run
            for y in range(min(ay, by) + 1, max(ay, by)):
                paint(y, ax + cell_w // 2, "│", style, edge)
            continue
        # Left node's right edge → right node's left edge (one or more gaps wide).
        (ly, lx), (ry, rx) = ((ay, ax), (by, bx)) if ax < bx else ((by, bx), (ay, ax))
        x0, x1 = lx + cell_w, rx - 1  # the span between the two cells
        mid = (x0 + x1) // 2
        for x in range(x0, mid):  # horizontal stub on the left node's row
            paint(ly, x, "─", style, edge)
        for x in range(mid + 1, x1 + 1):  # horizontal stub on the right node's row
            paint(ry, x, "─", style, edge)
        if ly == ry:
            paint(ly, mid, "─", style, edge)
        else:  # vertical step at the midpoint, with corners
            paint(ly, mid, "╮" if ly < ry else "╯", style, edge)
            paint(ry, mid, "╰" if ly < ry else "╭", style, edge)
            for y in range(min(ly, ry) + 1, max(ly, ry)):
                paint(y, mid, "│", style, edge)

    # Sever foreign wires that abut a non-endpoint label (PT-56): a cell touching a
    # label's left border and reaching rightward, or its right border reaching left,
    # is erased unless an edge incident to that node also owns it.
    for node, (row, c0, c1) in spans.items():
        for fx, arms in ((c0 - 1, _RIGHT_ARM), (c1, _LEFT_ARM)):
            own = owners.get((row, fx))
            if own and all(node not in e for e in own) and canvas.char_at(row, fx) in arms:
                canvas.erase(row, fx)


def _pointer_line(state: UniverseState, route: Sequence[int], hops: dict[int, int]) -> str:
    """A directional pointer when the route's destination is off the local map."""
    if not route:
        return ""
    dest = route[-1]
    if dest in hops:
        return ""
    disp = state.spatial_ids.get(dest, dest)
    return f"[bold yellow]→ S{disp}[/] [dim]({len(route) - 1} hops)[/]"


def local_layout_bearings(state: UniverseState, player: Player, here: int) -> dict[int, float]:
    """Calculate relative bearings for immediate neighbors of sector `here`,
    derived from the same topological gravity-column layout used by the Local Map.
    """
    placed, _, _, _, _, py, _, _ = _layout_map_nodes(state, player, here, radius=1)
    here_x = placed.get(here, (py, 0))[1]

    bearings: dict[int, float] = {}
    for node, (ny, nx) in placed.items():
        if node == here:
            continue
        # Use logical column offset (dx) and row offset (dy) so the aspect ratio
        # matches the compact nav rose and does not squash angles horizontally.
        dx = max(-1, min(1, nx - here_x))
        dy = py - ny  # negate row diff so up is positive y
        bearings[node] = math.atan2(dy, dx)

    return bearings
