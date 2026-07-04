"""Local sector ego-graph layout for the Computer → Map tab (§10, §11). Pure.

Lays out the player's surrounding sectors as a small ASCII node-and-edge graph
**centered on the current sector**, arranged in *gravity columns* — toward the
Core on the left, deeper into space on the right (the `<<`/`>>` convention from
the warp list). Nodes are tinted by distance band, fog of war masks unexplored
neighbours, and a passed-in route lights up its path. The output is a list of
Rich-markup row strings the TUI renders verbatim (the established baked-rows
contract) plus a one-line legend.

Deterministic and I/O-free: a function of `(state, player, radius, route)` only,
so it reconstructs identically under `(seed, command log)`. A key simplification
makes the layout tractable: `core_hops` is a BFS distance from the Core, so any
two warp-connected sectors differ by at most one hop — every edge therefore spans
the same gravity column or an adjacent one, and no long cross-column edge routing
is ever needed.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

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

_CELL_GAP = 5  # blank columns between node columns — room for edge connectors
_VSTEP = 2  # blank rows between stacked nodes in a column

_ROUTE_STYLE = "bold yellow"
_UNEXPLORED_STYLE = "dim"  # a sector whose id is known (warp list shows it) but is uncharted
_ONEWAY_STYLE = "dim"  # a warp with no return edge (one-way), drawn faintly

LEGEND = (
    "[reverse bold cyan]@[/] you   [bold yellow]*[/] route   ─ warp   "
    "[magenta]P[/]/[magenta]S[/] port   [green]@[/] planet   [dim](n)[/] unexplored"
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


def _codes(state: UniverseState, sector_id: int) -> str:
    """Short content tokens for an explored sector (mirrors session._sector_codes)."""
    out = ""
    port = state.port_in_sector(sector_id)
    if port is not None:
        out += "S" if port.klass is PortClass.STARDOCK else "P"
    if any(pl.sector_id == sector_id for pl in state.planets.values()):
        out += "@"
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
    return f"({disp}){_codes(state, sector_id)}"


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
    for r in range(1, MAX_FIT_RADIUS + 1):
        cand = _build_at_radius(state, player, r, route)
        rows, _legend, hits, width = cand
        if width <= max_width and len(hits) >= best_nodes:
            best, best_nodes = cand, len(hits)
        if width > max_width:
            break  # wider reach only lays out wider — stop growing
    if best is None:  # even reach 1 overflows the width; show it anyway
        best = _build_at_radius(state, player, 1, route)
    return best[0], best[1], best[2]


def _build_at_radius(
    state: UniverseState, player: Player, radius: int, route: Sequence[int],
) -> tuple[list[str], str, list[dto.MapNodeDTO], int]:
    """Lay out the ego-graph at a fixed `radius`; returns rows/legend/nodes + its width."""
    here = state.ships[player.ship_id].sector_id
    came_from = player.entered_from.get(here)
    hops = _local_bfs(state, here, radius)
    if came_from is not None and came_from in state.sectors:
        hops.setdefault(came_from, 1)  # the way back is always worth showing
    # The immediate ring is always shown (unexplored warps read as a faint id, like
    # the warp list); beyond it only charted sectors appear, so the deep fog doesn't
    # swarm the map.
    hops = {n: d for n, d in hops.items() if d <= 1 or n in player.explored_sectors}
    here_core = state.core_hops.get(here, 0)
    route_set = set(route)

    # Group nodes into gravity columns: offset = clamp(core_hops - here_core).
    columns: dict[int, list[int]] = {}
    for node in hops:
        offset = state.core_hops.get(node, here_core) - here_core
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

    canvas = _Canvas(width, height)
    placed: dict[int, tuple[int, int]] = {}  # sector_id → (row, x of label start)
    occupied: set[tuple[int, int]] = set()  # node-label cells, off-limits to connectors
    boxes: list[tuple[int, int, int, int]] = []  # (sector_id, canvas_row, col0, col1)

    def barycentre(node: int) -> float:
        """Mean row of this node's already-placed neighbours (re-uses gravity order)."""
        rows = [placed[m][0] for m in vis_adj[node] if m in placed]
        return sum(rows) / len(rows) if rows else float(center_row)

    # Place columns centre-outward so each node lands near its placed neighbours —
    # keeping connectors short and the graph legible even at hubs of high degree.
    for off in sorted(present, key=lambda o: (abs(o), o)):
        nodes = sorted(columns[off], key=lambda n: (barycentre(n), state.spatial_ids.get(n, n)))
        if off == 0 and here in nodes:  # keep the current sector dead-centre
            nodes.remove(here)
            nodes.insert(len(nodes) // 2, here)
        count = len(nodes)
        for i, node in enumerate(nodes):
            row = center_row + round((i - (count - 1) / 2) * _VSTEP)
            x = col_x[off]
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
            placed[node] = (row, x)
            occupied.update((row, x + k) for k in range(len(label)))
            if node != here:  # the current sector isn't a route target
                boxes.append((node, row, x, x + len(label)))

    _draw_edges(state, canvas, placed, cell_w, route, occupied)

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


def _draw_edges(
    state: UniverseState, canvas: _Canvas, placed: dict[int, tuple[int, int]],
    cell_w: int, route: Sequence[int], occupied: set[tuple[int, int]],
) -> None:
    """Connect placed nodes; route legs are drawn in the route highlight.

    Every warp-connected pair shares the same gravity column or an adjacent one
    (neighbours differ by ≤1 Core hop), so edges are either a vertical run or a
    single stepped connector across one gap — no long-haul routing. Connectors
    never overwrite node-label cells (`occupied`), so a crossing wire can't mangle
    a sector id.
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
    # Draw route legs last so the highlight wins on cells shared with plain edges.
    for a, b in sorted(edges, key=lambda e: e in route_legs):
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
                canvas.put(y, ax + cell_w // 2, "│", style, protect=occupied)
            continue
        # Adjacent columns: left node's right edge → right node's left edge.
        (ly, lx), (ry, rx) = ((ay, ax), (by, bx)) if ax < bx else ((by, bx), (ay, ax))
        x0, x1 = lx + cell_w, rx - 1  # the gap span between the two cells
        mid = (x0 + x1) // 2
        for x in range(x0, mid):  # horizontal stub on the left node's row
            canvas.put(ly, x, "─", style, protect=occupied)
        for x in range(mid + 1, x1 + 1):  # horizontal stub on the right node's row
            canvas.put(ry, x, "─", style, protect=occupied)
        if ly == ry:
            canvas.put(ly, mid, "─", style, protect=occupied)
        else:  # vertical step at the midpoint, with corners
            canvas.put(ly, mid, "╮" if ly < ry else "╯", style, protect=occupied)
            canvas.put(ry, mid, "╰" if ly < ry else "╭", style, protect=occupied)
            for y in range(min(ly, ry) + 1, max(ly, ry)):
                canvas.put(y, mid, "│", style, protect=occupied)


def _pointer_line(state: UniverseState, route: Sequence[int], hops: dict[int, int]) -> str:
    """A directional pointer when the route's destination is off the local map."""
    if not route:
        return ""
    dest = route[-1]
    if dest in hops:
        return ""
    disp = state.spatial_ids.get(dest, dest)
    return f"[bold yellow]→ S{disp}[/] [dim]({len(route) - 1} hops)[/]"
