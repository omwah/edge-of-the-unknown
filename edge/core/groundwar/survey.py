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

import math
from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from edge.core.config import GameConfig
from edge.core.discovery import is_detectable, sector_has_nebula
from edge.core.groundwar.terrain import generate_feature_grid
from edge.core.models import Discovery, UniverseState

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
    disc: Discovery, x: int, y: int, width: int, height: int, salt: Random, *, found: bool,
) -> SurveySite:
    exp = config.groundwar.expedition  # type: ignore[union-attr]
    # The sensor circle contains the true spot but is not centred on it.
    while True:
        ox = salt.randint(-(exp.area_radius - 3), exp.area_radius - 3)
        oy = salt.randint(-(exp.area_radius - 3), exp.area_radius - 3)
        if math.hypot(ox, oy) <= exp.area_radius - 3:
            break
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
        discovery_id=disc.id, kind=disc.kind.value, name=disc.name or disc.kind.value,
        rarity=disc.rarity_tier.name, x=x, y=y, area_cx=cx, area_cy=cy,
        area_r=exp.area_radius, clues=tuple(clues), found=found,
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
                           width, height, salt, found=disc.id in resolved_ids)
        placed.append(site)
    lx, ly = _landing(labels, comp, width, height)
    return SurveyMap(
        width=width, height=height,
        feature=tuple(tuple(row) for row in feature), blocked=frozenset(blocked),
        settlements=tuple(settlements), sites=tuple(placed), landing_x=lx, landing_y=ly,
    )
