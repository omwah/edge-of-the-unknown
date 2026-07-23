"""Pure survey-map generation from real universe discoveries (GW-WP05, GW plan §GW-M2).

The production replacement for the POC's invented find-kind generation
(`edge.groundwar.expedition`). Given a landed world's **actual** surface
`Discovery` records and the operation seed, it lays out a walkable terrain map —
optional friendly settlements, one sensor-marked site per *visible* discovery, and a
landing spot — as a **frozen, non-hashed** `SurveyMap` regenerated on demand (G5). The
`SurveyOperation` stores only the seed + the resolved/visible id sets; this module turns
those back into positions, so a save stays the command log, not a dump of every cell.

Two invariants shape the design:

- **G6 real discoveries.** Every site names exactly one existing `Discovery.id`; the
  generator never mints a parallel find. `found`/rarity/name come straight off the record.
- **G7 sensor integrity.** Only the discoveries the caller passes as *visible* are placed.
  A hidden, sensor-ineligible site leaks no marker, circle, clue, or count — it simply is
  not in the map. Each site's position derives from a **per-discovery placement salt**
  (`{seed}|site|{id}`), never list order, so a later descent after a sensor upgrade adds the
  newly resolvable site **without moving** the ones already known (the upgrade-and-return
  property).

Pure `edge.core`: imports the terrain seam and stdlib only — no `edge.art`, no Textual,
no RNG owned by anyone but the local `Random` seeded from the operation seed here.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from random import Random

from edge.core.config import GameConfig
from edge.core.discovery import is_detectable, sector_has_nebula
from edge.core.groundwar.models import SurveyOperation
from edge.core.groundwar.terrain import generate_feature_grid
from edge.core.models import Discovery, UniverseState
from edge.core.movement import MovementError
from edge.core.surface_finds import surface_find_name

Vec = tuple[int, int]

_EDGE_MARGIN = 6
_SETTLEMENT_KEEPOUT = 8  # sites never spawn this close to a settlement footprint
_LANDING_KEEPOUT = 22    # ... nor this close to the shuttle's left-middle landing zone

# A closed, seeded pool of peaceable town names (ported from the POC, order-stable).
SETTLEMENT_NAMES = (
    "Wayrest", "Karsholm", "Lantern Flats", "Umber's Ford", "Tessene",
    "Quiet Harbor", "Millbrace", "Old Anchorage",
)


@dataclass(frozen=True, slots=True)
class SurveySite:
    """One placed surface site — a 1:1 projection of a real surface `Discovery` (G6).

    `x`/`y` is the exact dig cell (never revealed until dug); the sensor `area_*` circle
    contains it but is not centred on it; `clues` are disturbed-ground cells near the truth.
    Identity fields (`discovery_id`/`name`/`kind`/`rarity`) are copied off the record, never
    invented. `found` mirrors prior collection; `hinted`/`area_*` may be narrowed by a
    settlement hint at play time (GW-WP06).
    """

    discovery_id: int
    kind: str
    name: str
    rarity: str
    x: int
    y: int
    area_cx: int
    area_cy: int
    area_r: int
    clues: tuple[Vec, ...]
    found: bool = False


@dataclass(frozen=True, slots=True)
class SurveySettlement:
    """A friendly walled town — resupply + one hint at play time (GW-WP06)."""

    id: int
    name: str
    cx: int
    cy: int
    x0: int
    y0: int
    x1: int
    y1: int

    def inside(self, x: int, y: int) -> bool:
        return self.x0 < x < self.x1 and self.y0 < y < self.y1


@dataclass(frozen=True, slots=True)
class SurveyMap:
    """The regenerated, non-hashed survey layout for one expedition (G5).

    Reconstructed from the operation seed + the visible discoveries + config; safely
    discardable and excluded from `state_hash`. `feature` is the gameplay terrain grid
    (feature names, glyph/colour styling stays in `edge.art`/`edge.tui`); `blocked` are
    the settlement masonry cells foot travel cannot cross.
    """

    width: int
    height: int
    feature: tuple[tuple[str, ...], ...]
    blocked: frozenset[Vec]
    settlements: tuple[SurveySettlement, ...]
    sites: tuple[SurveySite, ...]
    landing_x: int
    landing_y: int

    def site_by_discovery(self, discovery_id: int) -> SurveySite | None:
        return next((s for s in self.sites if s.discovery_id == discovery_id), None)


# --- terrain / passability (pure, ported from the POC into frozen inputs) -----


def _move_cost(feature: list[list[str]], blocked: set[Vec],
               config: GameConfig, x: int, y: int) -> int:
    """Entry cost on foot; 0 == impassable (hard terrain or settlement masonry)."""
    if (x, y) in blocked:
        return 0
    assert config.groundwar is not None
    tc = config.groundwar.terrain.get(feature[y][x])
    return tc.move_cost if tc else 1


def _in_bounds(width: int, height: int, x: int, y: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def _dist(ax: int, ay: int, bx: int, by: int) -> float:
    return math.hypot(ax - bx, ay - by)


def _passable_components(
    feature: list[list[str]], blocked: set[Vec], config: GameConfig, width: int, height: int
) -> tuple[list[list[int]], dict[int, int]]:
    """Label the 4-connected passable regions; return (labels, sizes).

    Sites and the landing must share one region, or the survey is unwinnable — the
    caller keeps the largest component and confines everything to it.
    """
    labels = [[-1] * width for _ in range(height)]
    sizes: dict[int, int] = {}
    label = 0
    for sy in range(height):
        for sx in range(width):
            if labels[sy][sx] != -1 or _move_cost(feature, blocked, config, sx, sy) <= 0:
                continue
            stack = [(sx, sy)]
            labels[sy][sx] = label
            n = 0
            while stack:
                x, y = stack.pop()
                n += 1
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if (_in_bounds(width, height, nx, ny) and labels[ny][nx] == -1
                            and _move_cost(feature, blocked, config, nx, ny) > 0):
                        labels[ny][nx] = label
                        stack.append((nx, ny))
            sizes[label] = n
            label += 1
    return labels, sizes


def _stamp_settlement(
    feature: list[list[str]], blocked: set[Vec], rng: Random, next_id: int, name: str,
    x0: int, y0: int, w: int, h: int,
) -> SurveySettlement:
    """A peaceable walled town: gated walls + homes carve masonry into `blocked`.

    Mutates `feature`/`blocked` in place (the caller owns them during generation) and
    returns the frozen settlement. Glyph/colour art is *not* set here — that is the
    TUI's job in GW-WP07; core owns only which cells are dust vs. impassable masonry.
    """
    s = SurveySettlement(id=next_id, name=name, cx=x0 + w // 2, cy=y0 + h // 2,
                         x0=x0, y0=y0, x1=x0 + w - 1, y1=y0 + h - 1)
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            feature[y][x] = "dust"
    gates = {(x0, s.cy), (x0 + w - 1, s.cy), (s.cx, y0), (s.cx, y0 + h - 1)}
    for x in range(x0, x0 + w):
        for y in (y0, y0 + h - 1):
            if (x, y) not in gates:
                blocked.add((x, y))
    for y in range(y0 + 1, y0 + h - 1):
        for x in (x0, x0 + w - 1):
            if (x, y) not in gates:
                blocked.add((x, y))
    for y in range(y0 + 2, y0 + h - 2, 2):  # homes on a street grid
        for bx in range(x0 + 3, x0 + w - 4, 4):
            for x in (bx, bx + 1):
                if abs(x - s.cx) + abs(y - s.cy) <= 2:
                    continue  # keep the plaza open
                blocked.add((x, y))
    return s


def _keepout(x: int, y: int, settlements: Sequence[SurveySettlement], height: int) -> bool:
    """Whether a candidate site cell is too near a settlement or the landing zone."""
    if any(st.x0 - _SETTLEMENT_KEEPOUT <= x <= st.x1 + _SETTLEMENT_KEEPOUT
           and st.y0 - _SETTLEMENT_KEEPOUT <= y <= st.y1 + _SETTLEMENT_KEEPOUT
           for st in settlements):
        return True
    return _dist(x, y, 6, height // 2) < _LANDING_KEEPOUT


def _site_position(
    feature: list[list[str]], blocked: set[Vec], config: GameConfig,
    labels: list[list[int]], comp: int, settlements: Sequence[SurveySettlement],
    width: int, height: int, salt: Random, *, tries: int = 400,
) -> Vec | None:
    """A passable in-component cell outside every keepout, drawn from a per-site salt.

    Crucially draws only from `salt` (seeded per discovery id), never from shared or
    list-order RNG, so a site's position depends solely on `(seed, discovery_id)` and
    stays put when other sites appear/disappear across descents (upgrade-and-return, G7).
    """
    for _ in range(tries):
        x = salt.randint(_EDGE_MARGIN, width - 1 - _EDGE_MARGIN)
        y = salt.randint(_EDGE_MARGIN, height - 1 - _EDGE_MARGIN)
        if labels[y][x] != comp or _keepout(x, y, settlements, height):
            continue
        return x, y
    return None


def _build_site(
    feature: list[list[str]], blocked: set[Vec], config: GameConfig,
    disc: Discovery, x: int, y: int, width: int, height: int, salt: Random, *,
    found: bool, hinted: bool,
) -> SurveySite:
    exp = config.groundwar.expedition  # type: ignore[union-attr]
    # The sensor circle contains the true spot but is not centred on it. A settlement hint
    # (GW-WP06 talk) tightens it to `city_hint_radius` and re-centres it near the truth, so a
    # hinted site's narrowed circle is reproduced purely from `hinted_discovery_ids` (D5) — no
    # circle state is stored. The true dig cell `(x, y)` is fixed upstream and never moves.
    while True:
        ox = salt.randint(-(exp.area_radius - 3), exp.area_radius - 3)
        oy = salt.randint(-(exp.area_radius - 3), exp.area_radius - 3)
        if math.hypot(ox, oy) <= exp.area_radius - 3:
            break
    if hinted:
        area_r = exp.city_hint_radius
        cx = max(2, min(width - 3, x + salt.randint(-2, 2)))
        cy = max(2, min(height - 3, y + salt.randint(-2, 2)))
    else:
        area_r = exp.area_radius
        cx = max(2, min(width - 3, x + ox))
        cy = max(2, min(height - 3, y + oy))
    clues: list[Vec] = []
    for _ in range(60):
        if len(clues) >= exp.clue_count:
            break
        c = (x + salt.randint(-exp.clue_radius, exp.clue_radius),
             y + salt.randint(-exp.clue_radius, exp.clue_radius))
        if c == (x, y) or c in clues or not _in_bounds(width, height, *c):
            continue
        if _move_cost(feature, blocked, config, *c) > 0:
            clues.append(c)
    return SurveySite(
        discovery_id=disc.id, kind=disc.kind.value,
        name=surface_find_name(disc.kind, disc.id) or disc.name or disc.kind.value,
        rarity=disc.rarity_tier.name, x=x, y=y, area_cx=cx, area_cy=cy,
        area_r=area_r, clues=tuple(clues), found=found,
    )


def _landing(labels: list[list[int]], comp: int, width: int, height: int) -> Vec:
    """Land near the map's left-middle, but only inside the sites' component."""
    mid = height // 2
    for x in range(4, width):
        for dy in range(mid):
            for y in (mid - dy, mid + dy):
                if 0 <= y < height and labels[y][x] == comp:
                    return x, y
    return 4, mid


def eligible_surface_site_ids(
    state: UniverseState, planet_id: int, sensor_rating: int,
    detected: frozenset[int], config: GameConfig,
) -> frozenset[int]:
    """The surface discoveries a survey of `planet_id` can resolve *now* (G7 snapshot).

    A site is visible when the ship's sensor (dimmed by a nebula over the sector) resolves
    it on entry, or when it was already detected on a prior visit (`detected`, the player's
    detection set). The begin reducer snapshots this so a later descent after a sensor
    upgrade widens the set; only these ids are ever placed, so a hidden, out-of-reach site
    leaks nothing. Already-*collected* sites are a subset and stay visible (shown `found`).
    """
    planet = state.planets.get(planet_id)
    if planet is None:
        return frozenset()
    in_nebula = sector_has_nebula(state, planet.sector_id)
    ids = {
        d.id for d in state.discoveries.values()
        if d.planet_id == planet_id
        and (d.id in detected
             or is_detectable(d, sensor_rating, in_nebula=in_nebula, config=config))
    }
    return frozenset(ids)


def generate_survey(
    config: GameConfig, *, seed: int, planet_type: str, inhabited: bool,
    sites: Sequence[Discovery], resolved_ids: frozenset[int] = frozenset(),
    hinted_ids: frozenset[int] = frozenset(),
) -> SurveyMap:
    """Lay out a survey map for the given *visible* surface discoveries (pure, G5/G6/G7).

    `sites` are exactly the discoveries the sensor/detection snapshot resolved — nothing
    hidden and out of reach is passed, so nothing leaks. Terrain and settlements draw from
    the operation-seed RNG (stable per world); each site's position/circle/clues draw from
    its own `{seed}|site|{id}` salt, so the layout of known sites is invariant to which
    other sites are visible. `resolved_ids` marks already-collected sites `found`.
    """
    assert config.groundwar is not None
    exp = config.groundwar.expedition
    width, height = exp.width, exp.height
    rng = Random(f"{seed}|survey|{planet_type}|{int(inhabited)}")
    feature = generate_feature_grid(seed, planet_type, width, height)
    blocked: set[Vec] = set()
    settlements: list[SurveySettlement] = []
    next_id = 1
    if inhabited:
        names = list(SETTLEMENT_NAMES)
        rng.shuffle(names)
        n = rng.randint(exp.settlements_min, exp.settlements_max)
        for i in range(n):
            w, h = 18, 9
            for _ in range(40):
                x0 = rng.randint(3, width - w - 3)
                y0 = rng.randint(3, height - h - 3)
                if not any(abs(x0 - st.x0) < w + 10 and abs(y0 - st.y0) < h + 6
                           for st in settlements):
                    settlements.append(
                        _stamp_settlement(feature, blocked, rng, next_id,
                                          names[i % len(names)], x0, y0, w, h))
                    next_id += 1
                    break
    # Settlements shape passability, so components come after they are stamped.
    labels, sizes = _passable_components(feature, blocked, config, width, height)
    comp = max(sizes, key=lambda k: sizes[k]) if sizes else 0
    placed: list[SurveySite] = []
    for disc in sorted(sites, key=lambda d: d.id):  # id order is deterministic; position is salt-based
        salt = Random(f"{seed}|site|{disc.id}")
        spot = _site_position(feature, blocked, config, labels, comp, settlements,
                              width, height, salt)
        if spot is None:
            continue  # no passable cell found — the site simply does not place this map
        site = _build_site(feature, blocked, config, disc, spot[0], spot[1],
                           width, height, salt, found=disc.id in resolved_ids,
                           hinted=disc.id in hinted_ids)
        placed.append(site)
    lx, ly = _landing(labels, comp, width, height)
    return SurveyMap(
        width=width, height=height,
        feature=tuple(tuple(row) for row in feature), blocked=frozenset(blocked),
        settlements=tuple(settlements), sites=tuple(placed), landing_x=lx, landing_y=ly,
    )


def survey_map_for(state: UniverseState, op: SurveyOperation, config: GameConfig) -> SurveyMap:
    """Regenerate the live map for an active survey operation (G5) — the projection seam.

    Turns the operation's stored seed + visible/resolved/hinted id sets back into positions;
    the begin/dig/talk reducers and the DTO all read the same layout. `inhabited` (settlement
    presence) is recomputed from the world's live population, so a survey of a peopled world
    gets its towns.
    """
    sites = [state.discoveries[i] for i in sorted(op.visible_discovery_ids)
             if i in state.discoveries]
    planet = state.planets.get(op.planet_id)
    inhabited = planet is not None and bool(planet.population)
    return generate_survey(
        config, seed=op.seed, planet_type=op.planet_type, inhabited=inhabited, sites=sites,
        resolved_ids=op.resolved_discovery_ids, hinted_ids=op.hinted_discovery_ids)


# --- live queries (pure, projection- and reducer-shared) ---------------------


def _cell_cost(smap: SurveyMap, config: GameConfig, x: int, y: int) -> int:
    """Foot-entry cost on the live map; 0 == impassable. Reads the frozen `SurveyMap`."""
    if (x, y) in smap.blocked:
        return 0
    assert config.groundwar is not None
    tc = config.groundwar.terrain.get(smap.feature[y][x])
    return tc.move_cost if tc else 1


def path_to(smap: SurveyMap, config: GameConfig, sx: int, sy: int, tx: int, ty: int
            ) -> list[Vec] | None:
    """Cheapest walking path (excluding the start cell) over the whole map, or None."""
    if not _in_bounds(smap.width, smap.height, tx, ty) or _cell_cost(smap, config, tx, ty) <= 0:
        return None
    start = (sx, sy)
    if (tx, ty) == start:
        return None
    best: dict[Vec, int] = {start: 0}
    prev: dict[Vec, Vec] = {}
    heap: list[tuple[int, Vec]] = [(0, start)]
    while heap:
        cost, (cx, cy) = heapq.heappop(heap)
        if (cx, cy) == (tx, ty):
            break
        if cost > best.get((cx, cy), 1 << 30):
            continue
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if not _in_bounds(smap.width, smap.height, nx, ny):
                continue
            step = _cell_cost(smap, config, nx, ny)
            if step <= 0:
                continue
            nc = cost + step
            if nc < best.get((nx, ny), 1 << 30):
                best[(nx, ny)] = nc
                prev[(nx, ny)] = (cx, cy)
                heapq.heappush(heap, (nc, (nx, ny)))
    if (tx, ty) not in prev:
        return None
    path: list[Vec] = []
    cell = (tx, ty)
    while cell != start:
        path.append(cell)
        cell = prev[cell]
    path.reverse()
    return path


def reachable_cells(
    smap: SurveyMap, config: GameConfig, sx: int, sy: int,
) -> dict[Vec, int]:
    """Cells reachable in one local movement turn, with their cheapest entry cost.

    The live DTO uses this same terrain-cost query for its walk-range overlay, so the client
    never approximates reducer pathfinding (GW-WP07/G1).  The start is included at cost 0.
    """
    assert config.groundwar is not None
    budget = config.groundwar.expedition.move
    best: dict[Vec, int] = {(sx, sy): 0}
    heap: list[tuple[int, Vec]] = [(0, (sx, sy))]
    while heap:
        cost, (cx, cy) = heapq.heappop(heap)
        if cost > best.get((cx, cy), budget + 1):
            continue
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if not _in_bounds(smap.width, smap.height, nx, ny):
                continue
            step = _cell_cost(smap, config, nx, ny)
            next_cost = cost + step
            if step <= 0 or next_cost > budget or next_cost >= best.get((nx, ny), budget + 1):
                continue
            best[(nx, ny)] = next_cost
            heapq.heappush(heap, (next_cost, (nx, ny)))
    return best


def dig_trench(smap: SurveyMap, config: GameConfig, x: int, y: int) -> list[Vec]:
    """The cells a dig from `(x, y)` opens — a disc of `dig_radius`, clipped to the map."""
    assert config.groundwar is not None
    r = config.groundwar.expedition.dig_radius
    return [(x + dx, y + dy)
            for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if dx * dx + dy * dy <= r * r and _in_bounds(smap.width, smap.height, x + dx, y + dy)]


def settlement_at(smap: SurveyMap, x: int, y: int) -> SurveySettlement | None:
    return next((s for s in smap.settlements if s.inside(x, y)), None)


def landing_sites(smap: SurveyMap, config: GameConfig) -> frozenset[Vec]:
    """Every cell the shuttle may set down on — the player's drop-site choice.

    Two constraints, in this order. First **reachability**: flood the passable region
    containing `smap.landing_*`, which `generate_survey` guarantees is the one holding
    every site, so no legal drop site can strand the survey on an island away from its
    contacts. Then **terrain**: drop `landing_blocked_features` (open water, peaks, ice),
    which are walkable-or-not but never somewhere a shuttle sets down.

    Pure and deterministic from the regenerated map, so the reducer validating a landing
    and the projection advertising the drop zone agree by construction.
    """
    assert config.groundwar is not None
    blocked_features = frozenset(config.groundwar.expedition.landing_blocked_features)
    start = (smap.landing_x, smap.landing_y)
    if _cell_cost(smap, config, *start) <= 0:
        return frozenset()
    region: set[Vec] = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in region or not _in_bounds(smap.width, smap.height, nx, ny):
                continue
            if _cell_cost(smap, config, nx, ny) <= 0:
                continue
            region.add((nx, ny))
            stack.append((nx, ny))
    return frozenset(
        cell for cell in region if smap.feature[cell[1]][cell[0]] not in blocked_features
    )


def is_landing_site(smap: SurveyMap, config: GameConfig, x: int, y: int) -> bool:
    """Whether `(x, y)` is a legal drop site (see `landing_sites`)."""
    return (x, y) in landing_sites(smap, config)


def suggested_landing(smap: SurveyMap, config: GameConfig, x: int, y: int) -> Vec:
    """Where to rest the drop cursor: the remembered spot when it is still legal, else the
    generated landing zone. A prior descent's position can become illegal — the sensor
    window widens between descents, so the map is not identical run to run."""
    sites = landing_sites(smap, config)
    if (x, y) in sites:
        return x, y
    if (smap.landing_x, smap.landing_y) in sites:
        return smap.landing_x, smap.landing_y
    return min(sites, default=(smap.landing_x, smap.landing_y))


def _unfound(smap: SurveyMap) -> list[SurveySite]:
    return [s for s in smap.sites if not s.found]


def _nearest_unfound(op: SurveyOperation, smap: SurveyMap) -> tuple[SurveySite | None, float]:
    """The nearest unfound site and its distance; `(None, 0.0)` when all are resolved."""
    sites = _unfound(smap)
    if not sites:
        return None, 0.0
    near = min(sites, key=lambda s: _dist(op.explorer_x, op.explorer_y, s.x, s.y))
    return near, _dist(op.explorer_x, op.explorer_y, near.x, near.y)


def scanner_band_index(op: SurveyOperation, smap: SurveyMap, config: GameConfig) -> int:
    """The reading's 1-based band ordinal — 1 is the hottest (saturated) band.

    `0` means there is nothing to read: every contact resolved, or the nearest one
    lies beyond the coldest band. Presentation keys emphasis off this rather than
    matching `scanner_reading`'s authored label text.
    """
    assert config.groundwar is not None
    near, d = _nearest_unfound(op, smap)
    if near is None:
        return 0
    for index, band in enumerate(config.groundwar.expedition.scanner, 1):
        if d <= band.within:
            return index
    return 0


def scanner_reading(op: SurveyOperation, smap: SurveyMap, config: GameConfig
                    ) -> tuple[str, SurveySite | None]:
    """The handheld gradient: a banded reading against the nearest unfound site."""
    assert config.groundwar is not None
    near, d = _nearest_unfound(op, smap)
    if near is None:
        return "all contacts resolved", None
    for band in config.groundwar.expedition.scanner:
        if d <= band.within:
            return band.label, near
    return "no signal", near


def visible_clues(op: SurveyOperation, smap: SurveyMap, config: GameConfig) -> set[Vec]:
    """Disturbed-ground cells the explorer is close enough to notice (unfound sites only)."""
    assert config.groundwar is not None
    sight = config.groundwar.expedition.sight
    out: set[Vec] = set()
    for s in _unfound(smap):
        for c in s.clues:
            if _dist(op.explorer_x, op.explorer_y, *c) <= sight:
                out.add(c)
    return out


# --- actions (pure; the reducer applies turn/reward settlement, G1) -----------


@dataclass(frozen=True, slots=True)
class SurveyActionResult:
    """The delta a survey action produces — the reducer owns state mutation and events.

    `operation` is the new (frozen) `SurveyOperation`; `main_turns` are main-game turns to
    charge (movement only, D4/D12); `excavated_id` is the discovery a dig uncovered (the
    reducer settles its artifact/codex reward, D6); `resupply` and `logs` are for the event
    log / UI.
    """

    operation: SurveyOperation
    main_turns: int = 0
    excavated_id: int | None = None
    resupply: int = 0
    logs: tuple[str, ...] = ()


def _threshold_cost(local_from: int, local_to: int, config: GameConfig) -> int:
    """Main-game turns owed for advancing the local-turn count `local_from → local_to` (D4).

    `ceil(local/L) × main_turn_cost` is the running charge; this returns the increment as a
    threshold boundary is crossed, so marching burns turns in quanta and digging/talking (no
    local-turn advance) burn none.
    """
    assert config.groundwar is not None
    exp = config.groundwar.expedition
    before = math.ceil(local_from / exp.local_turns_per_main_turn)
    after = math.ceil(local_to / exp.local_turns_per_main_turn)
    return (after - before) * exp.main_turn_cost


def survey_move(op: SurveyOperation, smap: SurveyMap, config: GameConfig,
                turns_remaining: int, x: int, y: int) -> SurveyActionResult:
    """March the explorer toward `(x, y)` (GW-WP06, D4/D12).

    One supply per local turn, however many turns the march takes. The march halts early
    on supply exhaustion, or when the next local turn would cross an **unaffordable**
    macro-turn threshold (D12: the quantum is paid before the threshold is crossed;
    extraction stays free). It no longer halts on newly-sighted disturbed ground — that
    auto-stop (once meant to keep a multi-turn march from tramping past a clue) cost more
    clicks than it saved, since `cell.clue` already marks the ground on the map the whole
    time it's in sight; the player decides when to stop and dig. Raises when the target is
    unreachable or no progress at all can be paid for.
    """
    if op.outcome is not None:
        raise MovementError("the expedition has ended — extract to orbit")
    assert config.groundwar is not None
    exp = config.groundwar.expedition
    path = path_to(smap, config, op.explorer_x, op.explorer_y, x, y)
    if path is None:
        raise MovementError("no path to there")
    ex, ey, supplies, local_turn = op.explorer_x, op.explorer_y, op.supplies, op.local_turn
    charged = 0
    turns = 0
    halt: str | None = None
    i = 0
    while i < len(path):
        owed = _threshold_cost(local_turn, local_turn + 1, config)
        if owed > turns_remaining - charged:
            halt = "turns"
            break
        budget = exp.move
        moved = False
        while i < len(path):
            step = _cell_cost(smap, config, *path[i])
            if step > budget:
                break
            budget -= step
            ex, ey = path[i]
            i += 1
            moved = True
        if not moved:
            break
        local_turn += 1
        turns += 1
        charged += owed
        supplies = max(0, supplies - 1)
        if supplies <= 0:
            halt = "supplies"
            break
    if turns == 0:
        raise MovementError("not enough turns to advance the march — extract to orbit")
    logs: list[str] = []
    outcome = op.outcome
    if halt == "supplies":
        outcome = "exhausted"
        logs.append("Supplies spent — the shuttle recalls you to orbit. What you found stays found.")
    if turns > 1:
        logs.append(f"A march of {turns} turns.")
    op2 = replace(op, explorer_x=ex, explorer_y=ey, supplies=supplies,
                  local_turn=local_turn, outcome=outcome)
    return SurveyActionResult(operation=op2, main_turns=charged, logs=tuple(logs))


def survey_dig(op: SurveyOperation, smap: SurveyMap, config: GameConfig) -> SurveyActionResult:
    """Open a trench where the explorer stands (GW-WP06, D6).

    A site anywhere in the trench is uncovered — `excavated_id` names it and the reducer
    settles its artifact + codex reward (no second collect step, no hold gate). Re-digging
    ground already fully turned over is free (no supply spent). A dry dig spends `dig_cost`
    supplies and can exhaust the expedition. Digging costs no main-game turns (local only).
    """
    if op.outcome is not None:
        raise MovementError("the expedition has ended — extract to orbit")
    assert config.groundwar is not None
    exp = config.groundwar.expedition
    trench = dig_trench(smap, config, op.explorer_x, op.explorer_y)
    trench_set = set(trench)
    if trench_set <= op.dug_cells:
        return SurveyActionResult(
            operation=op, logs=("You already turned this ground over — nothing here.",))
    dug = op.dug_cells | frozenset(trench)
    hits = [s for s in smap.sites if not s.found and (s.x, s.y) in trench_set]
    if hits:
        site = min(hits, key=lambda s: _dist(op.explorer_x, op.explorer_y, s.x, s.y))
        gained = max(0, min(exp.supplies_start, op.supplies + exp.find_resupply) - op.supplies)
        resolved = op.resolved_discovery_ids | {site.discovery_id}
        outcome = op.outcome
        if all(s.discovery_id in resolved for s in smap.sites):
            outcome = "complete"
        op2 = replace(op, dug_cells=dug, supplies=op.supplies + gained,
                      resolved_discovery_ids=resolved, outcome=outcome)
        return SurveyActionResult(
            operation=op2, excavated_id=site.discovery_id, resupply=gained,
            logs=(f"Your spade rings on worked stone — {site.name}!",))
    supplies = max(0, op.supplies - exp.dig_cost)
    outcome = op.outcome
    logs = ["You open a trench: nothing but soil and stones."]
    if supplies <= 0 and outcome is None:
        outcome = "exhausted"
        logs.append("Supplies spent — the shuttle recalls you to orbit.")
    op2 = replace(op, dug_cells=dug, supplies=supplies, outcome=outcome)
    return SurveyActionResult(operation=op2, logs=tuple(logs))


def survey_talk(op: SurveyOperation, smap: SurveyMap, config: GameConfig) -> SurveyActionResult:
    """Talk to a settlement the explorer stands in (GW-WP06, D5).

    Resupplies (capped at the start amount) and, if any unhinted unfound site remains, narrows
    the nearest one's search circle — recorded in `hinted_discovery_ids`, which persists across
    descents (D5). A site is hinted at most once. Costs no main-game turns.
    """
    if op.outcome is not None:
        raise MovementError("the expedition has ended — extract to orbit")
    assert config.groundwar is not None
    exp = config.groundwar.expedition
    town = settlement_at(smap, op.explorer_x, op.explorer_y)
    if town is None:
        raise MovementError("no settlement here to talk to")
    gained = max(0, min(exp.supplies_start, op.supplies + exp.settlement_resupply) - op.supplies)
    logs: list[str] = []
    if gained > 0:
        logs.append(f"The people of {town.name} refill your packs: +{gained} supplies.")
    candidates = [s for s in smap.sites
                  if not s.found and s.discovery_id not in op.hinted_discovery_ids]
    hinted = op.hinted_discovery_ids
    if candidates:
        site = min(candidates, key=lambda s: _dist(town.cx, town.cy, s.x, s.y))
        hinted = op.hinted_discovery_ids | {site.discovery_id}
        logs.append(f"An elder of {town.name} recalls old stones nearby — your chart circle tightens.")
    else:
        logs.append(f"{town.name} wishes you fair digging.")
    op2 = replace(op, supplies=op.supplies + gained, hinted_discovery_ids=hinted)
    return SurveyActionResult(operation=op2, resupply=gained, logs=tuple(logs))
