"""One world, one ground layout — the shared survey/assault terrain identity (GW-WP19).

Before this module, a world had *two* unrelated grounds. `survey.generate_survey`
seeded its noise from a per-player operation seed and scattered its own peaceable
towns; `assault.generate_assault_map` seeded its noise from a per-operation seed
and stamped its own fortified cities in lane order. Neither knew about the other's
output, so taking a world by force and then walking it as a protectorate showed a
different planet, and a second assault on the same world fought over a fresh
battlefield. `Planet.ground_damage` was a per-*kind* counter precisely because no
layout was stable enough to pin damage to a position.

This module owns the one identity both modes read:

- **`world_ground_seed`** — derived from `(Game.seed, planet_id)`, so it needs no
  hashed field of its own and is by construction the same for every player and
  every operation on that world. Both begin reducers snapshot it onto the
  operation (`world_seed`), so a mid-operation universe change cannot reshuffle the
  ground underfoot, and pure regeneration seams stay state-free (G5).
- **`place_count`** — how many built-up places a world has, from **stable** world
  facts only: colonist capacity and distance band. Deliberately *not* the other
  multipliers `derive_difficulty` applies — ownership and citadel level flip when a
  world is taken, and an inhabiting species' disposition disappears if its people
  are wiped out. A layout that re-rolls on any of those is exactly the bug this
  module exists to remove; they shift the surrender threshold instead (see
  `assault.derive_difficulty`).
- **`generate_world_ground`** — the biome grid plus one `PlaceStamp` per place:
  the shared *built geometry* (perimeter, gates, interior building blocks with
  their military/civilian split). A survey walks that geometry as a town; an
  assault fights it as a fortified city, adding only its live emplacements. Both
  therefore agree cell-for-cell on where the walls, gates, and buildings are —
  which is what lets `Planet.ground_rubble` persist damage by **position** and a
  survey paint the ruins an assault left behind.

Pure `edge.core`: no I/O, no art, no upward imports. Every function is
deterministic in its arguments and draws no game RNG (G2/G5).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from random import Random

from edge.core.config import GameConfig
from edge.core.groundwar.terrain import generate_feature_grid
from edge.core.models import GroundRubble, Planet
from edge.core.planets import colonist_capacity

Vec = tuple[int, int]
# GW-WP27: a building as `(x, y, w, h)` with `x, y` the north-west anchor. Rectangles
# only — every building the street grid places is one, and keeping it four ints rather
# than a cell tuple keeps `PlaceStamp` small and comparable.
Footprint = tuple[int, int, int, int]

# One pool for both modes: a place has a single name whether you walk into it or
# drop on it. Merges the peaceable town names survey used with the military city
# names assault used, because they were never describing different places — the
# split was an artifact of the two generators never having met.
PLACE_NAMES: tuple[str, ...] = (
    "Wayrest", "Karsholm", "Lantern Flats", "Umber's Ford", "Tessene",
    "Quiet Harbor", "Millbrace", "Old Anchorage",
    "Klendathu Down", "Port Joel", "Zegema Beach", "New Cyrene", "Uxmal",
    "Fort Bannon", "Carr's Landing", "Hesperus", "Tango Urilla", "Sheol",
)

# What a paved footprint plays as underfoot (move 1, no cover) regardless of biome.
STREET_FEATURE = "dust"

# GW-WP27 (D35/D38): grown to hold multi-cell buildings. A trooper and an apartment
# block used to be the same size; at these dimensions a city holds roughly 20 (town) to
# 35 (capital) real buildings on a street grid, and one trooper action crosses about one
# block, which is the readable unit at this scale.
CAPITAL_SIZE = (46, 26)  # (w, h)
PLACE_SIZE = (34, 20)

_BUILDING_MILITARY_FRAC = 0.3  # the POC's military/civilian building-block split

# Street grid. Pitch exceeds the widest/tallest building so every block keeps at least one
# cell of street around it — buildings that touch would read as one shapeless mass.
_BLOCK_PITCH_X = 6
_BLOCK_PITCH_Y = 4
# Buildings the grid may place, as `(w, h, weight)`. Rolled **once per building** rather
# than per cell: the pre-GW-WP27 loop rolled military/civilian independently for each of a
# block's two cells, so a single visual "building" could come out half depot, half housing.
_BUILDING_SIZES: tuple[tuple[int, int, float], ...] = (
    (2, 2, 0.30),   # row house
    (3, 2, 0.28),   # shop row
    (4, 2, 0.20),   # tenement
    (3, 3, 0.12),   # workshop
    (5, 3, 0.10),   # hall / depot
)
# Cells of clear ground held inside the wall. Without it buildings abut the perimeter and
# a breach opens into a wall of masonry rather than into the city.
_SERVICE_ROAD = 1


@dataclass(frozen=True, slots=True)
class GroundPlace:
    """One built-up place on a world: a survey's town, an assault's fortified city.

    Footprint corners are inclusive. `capital` marks the seat a citadel fortifies
    (the last place, matching the POC's `is_citadel = i == n - 1`).
    """

    id: int
    name: str
    x0: int
    y0: int
    x1: int
    y1: int
    capital: bool = False

    @property
    def cx(self) -> int:
        return (self.x0 + self.x1) // 2

    @property
    def cy(self) -> int:
        return (self.y0 + self.y1) // 2

    @property
    def width(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def height(self) -> int:
        return self.y1 - self.y0 + 1

    def inside(self, x: int, y: int) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


@dataclass(frozen=True, slots=True)
class PlaceStamp:
    """The shared built geometry of one place — identical in survey and assault.

    `perimeter` is the wall line minus `gates`; a survey renders every perimeter
    cell as masonry, while an assault renders the same cells as `wall` structures
    with turrets substituted at the corner/mid slots. `military`/`civilian` are the
    interior buildings as **footprints** since GW-WP27, split here (off the world
    seed) rather than per assault, so the *kind* standing at a position is as stable
    as the position. `reserved` are the interior emplacement anchors and the plaza:
    cells no building may take, held regardless of citadel level so the building
    layout does not drift when a citadel is built or lost.
    """

    place: GroundPlace
    perimeter: tuple[Vec, ...]
    gates: tuple[Vec, ...]
    military: tuple[Footprint, ...]
    civilian: tuple[Footprint, ...]
    reserved: tuple[Vec, ...]

    @property
    def buildings(self) -> tuple[Footprint, ...]:
        return self.military + self.civilian

    @property
    def building_cells(self) -> tuple[Vec, ...]:
        """Every cell every building covers — what a survey blocks and paves."""
        return tuple(
            (x + dx, y + dy)
            for x, y, w, h in self.buildings
            for dy in range(h) for dx in range(w)
        )


@dataclass(frozen=True, slots=True)
class WorldGround:
    """A world's regenerated, non-hashed ground identity (G5).

    `feature` is the bare biome grid — footprints are *not* paved here, so an
    uninhabited world (`places=0`) generates the identical terrain an inhabited one
    does, and paving stays the consumer's job (each mode applies `stamps` itself).
    """

    width: int
    height: int
    feature: tuple[tuple[str, ...], ...]
    stamps: tuple[PlaceStamp, ...]

    @property
    def places(self) -> tuple[GroundPlace, ...]:
        return tuple(stamp.place for stamp in self.stamps)


def world_ground_seed(universe_seed: int, planet_id: int) -> int:
    """The stable per-world ground-layout seed (GW-WP19).

    Derived rather than stored: `(Game.seed, planet_id)` is already authoritative
    and replay-exact, so the shared identity costs no hashed field and cannot drift
    between players, modes, or repeat operations.
    """
    return Random(f"{universe_seed}|ground|{planet_id}").getrandbits(63)


def ground_map_size(config: GameConfig) -> tuple[int, int]:
    """The one ground-map grid size both modes use.

    `GroundwarConfig` validates that `expedition` and `battlefield` agree on
    dimensions precisely so this can be a single answer — a survey and an assault
    of the same world must be the same number of cells or no shared identity is
    possible.
    """
    assert config.groundwar is not None
    return config.groundwar.battlefield.width, config.groundwar.battlefield.height


def place_count(planet: Planet, config: GameConfig, *, distance_band: str) -> int:
    """How many built-up places this world has — stable per world (GW-WP19).

    Reads only two facts, both of which outlive any conquest: the world's colonist
    capacity (from `habitability_cap`, or a Cloud City's berths — capacity, not the
    live headcount) and its distance band. Every input `derive_difficulty` also
    weighs is deliberately excluded, because each of them *changes*: ownership and
    citadel level flip when a world is taken, and the inhabiting species'
    disposition disappears entirely if its people are wiped out. Re-rolling a
    world's towns because it changed hands — or because its last native died — is
    the exact discontinuity this seam exists to remove. Those inputs shift how
    stubbornly the world holds out instead (`derive_difficulty`'s `resist`).
    """
    assert config.groundwar is not None
    cfg = config.groundwar.assault_difficulty
    score = float(colonist_capacity(planet, config)) * cfg.band_mult.get(distance_band, 1.0)
    return min(cfg.max_cities, cfg.min_cities + int(score // cfg.population_per_extra_city))


def move_cost(
    feature: list[list[str]], blocked: set[Vec], config: GameConfig, x: int, y: int
) -> int:
    """Foot-entry cost during generation; 0 == impassable (hard terrain or masonry)."""
    if (x, y) in blocked:
        return 0
    assert config.groundwar is not None
    tc = config.groundwar.terrain.get(feature[y][x])
    return tc.move_cost if tc else 1


def in_bounds(width: int, height: int, x: int, y: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def passable_components(
    feature: list[list[str]], blocked: set[Vec], config: GameConfig, width: int, height: int
) -> tuple[list[list[int]], dict[int, int]]:
    """Label the 4-connected passable regions; return (labels, sizes).

    The one copy: `survey.py` and `assault.py` each carried an identical private
    version before GW-WP19. Callers keep the largest component and confine the
    landing (and, for a survey, its sites) to it, so a map is never unwinnable.
    """
    labels = [[-1] * width for _ in range(height)]
    sizes: dict[int, int] = {}
    label = 0
    for sy in range(height):
        for sx in range(width):
            if labels[sy][sx] != -1 or move_cost(feature, blocked, config, sx, sy) <= 0:
                continue
            stack = [(sx, sy)]
            labels[sy][sx] = label
            n = 0
            while stack:
                x, y = stack.pop()
                n += 1
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if (in_bounds(width, height, nx, ny) and labels[ny][nx] == -1
                            and move_cost(feature, blocked, config, nx, ny) > 0):
                        labels[ny][nx] = label
                        stack.append((nx, ny))
            sizes[label] = n
            label += 1
    return labels, sizes


def landing_in_component(
    labels: list[list[int]], comp: int, width: int, height: int
) -> Vec:
    """Set down near the map's left-middle, but only inside `comp`."""
    mid = height // 2
    for x in range(4, width):
        for dy in range(mid):
            for y in (mid - dy, mid + dy):
                if 0 <= y < height and labels[y][x] == comp:
                    return x, y
    return 4, mid


def footprint_passable_frac(
    feature: list[list[str]], config: GameConfig, x0: int, y0: int, w: int, h: int,
) -> float:
    assert config.groundwar is not None
    total = passable = 0
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            total += 1
            tc = config.groundwar.terrain.get(feature[y][x])
            if tc is not None and tc.move_cost > 0:
                passable += 1
    return passable / max(1, total)


def _emplacement_slots(place: GroundPlace) -> tuple[Vec, ...]:
    """Interior cells an assault may put an emplacement on (and a survey leaves open).

    Held *unconditionally*, including the second AA and the level-2 citadel gun:
    reserving only what the current citadel level would build would move the building
    blocks every time a citadel is raised or lost.

    These are **anchors**. Since GW-WP27 the AA batteries and the citadel gun are 2x2,
    so `_reserved_cells` expands each of these into the area a building may not take.
    """
    w = place.width
    return (
        (place.cx - w // 4, place.cy - 1),  # AA battery
        (place.cx + w // 4, place.cy + 1),  # sensor tower
        (place.cx + w // 4, place.cy - 1),  # second AA
        (place.cx, place.cy),               # citadel gun (capital, level 2) / plaza
    )


def _reserved_cells(place: GroundPlace) -> set[Vec]:
    """Every cell the emplacement slots and the central plaza consume.

    The plaza is a small open square rather than the old one-cell cross: at these
    dimensions a city centre that is solid building right up to the citadel gun reads
    as a maze, and the gun itself now needs 2x2 of its own.
    """
    cells: set[Vec] = set()
    for ax, ay in _emplacement_slots(place):
        for dy in range(2):
            for dx in range(2):
                cells.add((ax + dx, ay + dy))
    for dy in range(-2, 3):
        for dx in range(-3, 4):
            cells.add((place.cx + dx, place.cy + dy))
    return cells


def _pick_size(rng: Random) -> tuple[int, int]:
    roll = rng.random() * sum(weight for _, _, weight in _BUILDING_SIZES)
    for w, h, weight in _BUILDING_SIZES:
        roll -= weight
        if roll <= 0:
            return w, h
    return _BUILDING_SIZES[-1][0], _BUILDING_SIZES[-1][1]


def stamp_place(place: GroundPlace, rng: Random) -> PlaceStamp:
    """Derive one place's shared built geometry (pure, GW-WP19).

    Ports the POC's city/town stamping — perimeter wall with a gate mid each
    vertical side, building blocks on a street grid every other row — into one
    description both modes consume. `rng` decides only the military/civilian split,
    drawn here off the world seed so the kind at a position is stable across
    operations (and so positional rubble can name what was destroyed).
    """
    x0, y0, x1, y1 = place.x0, place.y0, place.x1, place.y1
    gates = ((x0, place.cy), (x1, place.cy))
    reserved = _emplacement_slots(place)
    perimeter: list[Vec] = []
    for x in range(x0, x1 + 1):
        for y in (y0, y1):
            perimeter.append((x, y))
    for y in range(y0 + 1, y1):
        for x in (x0, x1):
            if (x, y) not in gates:
                perimeter.append((x, y))

    # Buildings, on a street grid inset by the wall plus a service road.
    blocked = _reserved_cells(place)
    lo_x, lo_y = x0 + 1 + _SERVICE_ROAD, y0 + 1 + _SERVICE_ROAD
    hi_x, hi_y = x1 - 1 - _SERVICE_ROAD, y1 - 1 - _SERVICE_ROAD
    military: list[Footprint] = []
    civilian: list[Footprint] = []
    taken: set[Vec] = set()
    for by in range(lo_y, hi_y + 1, _BLOCK_PITCH_Y):
        for bx in range(lo_x, hi_x + 1, _BLOCK_PITCH_X):
            w, h = _pick_size(rng)
            # Shrink to whatever the slot and the interior actually allow, rather than
            # skipping: a clamped building still fills its block, where skipping would
            # leave the city's east and south edges conspicuously empty.
            w = min(w, _BLOCK_PITCH_X - 1, hi_x - bx + 1)
            h = min(h, _BLOCK_PITCH_Y - 1, hi_y - by + 1)
            if w < 2 or h < 2:
                continue
            cells = [(bx + dx, by + dy) for dy in range(h) for dx in range(w)]
            if any(c in blocked or c in taken for c in cells):
                continue
            taken.update(cells)
            # One roll for the whole building, so a depot is a depot all the way through.
            target = military if rng.random() < _BUILDING_MILITARY_FRAC else civilian
            target.append((bx, by, w, h))
    return PlaceStamp(
        place=place, perimeter=tuple(perimeter), gates=gates,
        military=tuple(military), civilian=tuple(civilian), reserved=reserved,
    )


def generate_world_ground(
    config: GameConfig, *, seed: int, planet_type: str, places: int,
) -> WorldGround:
    """The world's biome grid + the shared geometry of its `places` built-up places.

    Deterministic in `(seed, planet_type, places)` and drawing no game RNG (G2/G5).
    Places are laid out in even vertical lanes (the assault generator's approach,
    which spreads them and picks the most passable footprint per lane) rather than
    the survey generator's free scatter, so the same world always yields the same
    footprints in the same order. The last place is the `capital`.
    """
    width, height = ground_map_size(config)
    feature = generate_feature_grid(seed, planet_type, width, height)
    rng = Random(f"{seed}|places|{planet_type}|{places}")
    names = list(PLACE_NAMES)
    rng.shuffle(names)
    stamps: list[PlaceStamp] = []
    for i in range(max(0, places)):
        capital = i == places - 1
        w, h = CAPITAL_SIZE if capital else PLACE_SIZE
        lane_x0 = width * (i + 1) // (places + 1)
        lane_x1 = width * (i + 2) // (places + 1) - w - 2
        best: tuple[float, int, int] | None = None
        for _ in range(24):
            x0 = rng.randint(max(2, lane_x0), max(max(2, lane_x0), lane_x1))
            y0 = rng.randint(3, height - h - 3)
            frac = footprint_passable_frac(feature, config, x0, y0, w, h)
            if best is None or frac > best[0]:
                best = (frac, x0, y0)
            if frac >= 0.7:
                break
        assert best is not None
        place = GroundPlace(
            id=i + 1, name=names[i % len(names)], x0=best[1], y0=best[2],
            x1=best[1] + w - 1, y1=best[2] + h - 1, capital=capital,
        )
        stamps.append(stamp_place(place, rng))
    return WorldGround(
        width=width, height=height,
        feature=tuple(tuple(row) for row in feature), stamps=tuple(stamps),
    )


def pave(feature: list[list[str]], stamp: PlaceStamp) -> None:
    """Pave a place's footprint: built-up ground plays as street whatever lies under it."""
    for y in range(stamp.place.y0, stamp.place.y1 + 1):
        for x in range(stamp.place.x0, stamp.place.x1 + 1):
            feature[y][x] = STREET_FEATURE


def rubble_at(planet: Planet) -> dict[Vec, str]:
    """A world's persisted battle damage as `position -> destroyed structure kind`.

    The positional record replaces GW-WP11's per-kind counter: with one stable
    layout, damage can say *which* wall fell, so a later assault reopens the same
    breach and a survey paints the same ruin.
    """
    return {(entry.x, entry.y): entry.kind for entry in planet.ground_rubble}


def rubble_counts(planet: Planet) -> Counter[str]:
    """Destroyed-structure counts by kind, derived from the positional record.

    The aggregate `Planet.ground_damage` used to be stored; it is now derived so
    there is exactly one truth about what a world has lost.
    """
    return Counter(entry.kind for entry in planet.ground_rubble)


def merged_rubble(
    planet: Planet, destroyed: dict[Vec, str],
) -> tuple[tuple[GroundRubble, ...], Counter[str]]:
    """Fold a settled operation's destroyed positions into the world's record.

    Returns the new rubble tuple (position-ordered, so it is stable across
    replays) and a count *of newly destroyed kinds only* — what civilian-harm
    consequences must scale from, since a wall already rubble at drop must not be
    charged twice.
    """
    existing = rubble_at(planet)
    fresh = Counter(kind for pos, kind in destroyed.items() if pos not in existing)
    combined = existing | destroyed
    return (
        tuple(GroundRubble(x=x, y=y, kind=combined[(x, y)])
              for x, y in sorted(combined)),
        fresh,
    )
