"""Pure station-interior generation for Cloud City assaults (GW-WP15, GW plan D9).

A Cloud City has no ground: its tactical map is the **interior of the floating
station itself**, not planetary terrain wearing a different palette. This module
owns the discrete room/corridor/door layout the way `edge.core.groundwar.terrain`
owns the continuous noise-band biome layout for planets — same split (pure
gameplay feature grid here, glyphs/colours in `edge.art.interior`), different
algorithm, because a station's rooms and corridors are architecture, not organic
noise bands.

Two interview decisions (July 2026) shape the connectivity model:

- **Jump-jets never bypass a wall or a locked door here** (unlike the planet
  `move_cost: 0 ⇒ jump clears it` precedent for e.g. mountains — that read does
  not carry over to a station). Jump is a GW-WP16 tactical-movement concern
  scoped to open interior cells and is not modelled by this module at all.
- **A `security_door` is a destructible obstacle** (breach cost is a GW-WP16
  firepower mechanic) and *may* legally be the only connector between two areas,
  since it is always eventually passable. A plain `bulkhead` never is — the
  connectivity invariant below treats the two differently.

Hazards (`vacuum`/`fire`/`electrical`) are placed as inert feature-name tags this
WP (GW-WP16 wires their effects); `defender_slots` are static positions only —
their occupants and behaviour are also GW-WP16.

Deterministic from `(noise_seed, cloud_city_size, config)`; draws no game RNG —
seeds its own `random.Random(f"{noise_seed}-{attempt}")`, mirroring
`edge/bigbang/generator.py`'s bounded-retry idiom (G2/G5: same seed and inputs
reproduce the identical layout on every replay).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from random import Random

from edge.core.config import GwCloudCity

Vec = tuple[int, int]

_MAX_ATTEMPTS = 16

# The room/corridor floor roles a district can be assigned. Exactly one district
# per city is `command_core` (the assault objective); the rest are drawn from
# this pool.
_DISTRICT_ROLES: tuple[str, ...] = ("plaza", "habitation", "engineering")

_HAZARDS: tuple[str, ...] = ("vacuum", "fire", "electrical")

# Every feature name this generator can emit. `GroundwarConfig` validates that
# `terrain:` defines a `GwTerrain` class for each of these, exactly as
# `edge.core.groundwar.terrain.LANDABLE_BIOMES` is validated against `BIOME_BANDS`.
INTERIOR_FEATURES: tuple[str, ...] = (
    "corridor", "plaza", "habitation", "engineering", "command_core",
    "cover_strut", "bulkhead", "security_door", "lift",
    *_HAZARDS,
)

# Wall-like for the neighbor-mask junction reading only (a security_door reads as
# continuous wall from an adjacent bulkhead's perspective — it gets its own fixed
# glyph rather than a junction, see `edge.art.interior`). Distinct from
# `_connectivity_ok`'s own `_passable` — that one treats `security_door` as
# passable (a door is always eventually breachable), this one does not.
WALL_LIKE_FEATURES: tuple[str, ...] = ("bulkhead", "security_door")

_MIN_LEAF = 8  # a leaf below this on its split axis is never split further
_ROOM_MARGIN = 1  # bulkhead ring left around every carved room
_EDGE_MARGIN = 3  # deployment zones must be within this of the map border


def wall_neighbor_mask(
    feature_at: Callable[[int, int], str], x: int, y: int, width: int, height: int,
) -> int:
    """The 4-bit N/S/E/W mask of which orthogonal neighbours of `(x, y)` are
    wall-like (GW-WP15/16 art seam), treating the map edge as wall too so a
    border bulkhead caps cleanly instead of dangling open.

    Pure and core-side so the server can compute it once against the *full* grid
    (`edge.server.session`, `AssaultCellDTO`/`GroundCellDTO.wall_mask`) — a client
    holding only a cropped viewport cannot always see a wall cell's true neighbours
    at the viewport's edge. `edge.art.interior` turns the mask into a box-drawing
    glyph; this module only ever hands out the structural fact.
    """
    def wall_like(nx: int, ny: int) -> bool:
        if not (0 <= nx < width and 0 <= ny < height):
            return True
        return feature_at(nx, ny) in WALL_LIKE_FEATURES

    return (
        (1 if wall_like(x, y - 1) else 0)
        | (2 if wall_like(x, y + 1) else 0)
        | (4 if wall_like(x + 1, y) else 0)
        | (8 if wall_like(x - 1, y) else 0)
    )


@dataclass(frozen=True, slots=True)
class District:
    """One generated room — a district of the station (GW-WP16 consumer).

    `x0/y0/x1/y1` is the room's full leaf rect (the `bulkhead` margin ring
    included, so it matches what `_carve_rooms` partitioned); `floor` is the
    interior cells only (margin excluded), matching `_Room.floor`. Exactly one
    district per layout has `role == "command_core"` — the assault objective.
    """

    id: int
    role: str
    x0: int
    y0: int
    x1: int
    y1: int
    cx: int
    cy: int
    floor: tuple[Vec, ...]


@dataclass(frozen=True, slots=True)
class InteriorLayout:
    """A generated, replay-stable Cloud City interior (GW plan D9).

    `feature_grid` is row-major (`feature_grid[y][x]`), matching
    `edge.core.groundwar.terrain.generate_feature_grid`. `lift_links` pairs
    teleport cells that a future movement mechanic could treat as directly
    adjacent even though they need not be 4-adjacent on the grid — GW-WP16
    proved they are never *required* for connectivity (every room is already
    spanned by corridors/doors before lifts are placed, see
    `test_connectivity_holds_without_lift_links`), so they are treated as inert
    bonus shortcuts, not a tactical teleport action. `defender_slots` are
    positions only — GW-WP16 gives them occupants. `districts` exposes the
    per-room records (`GW-WP16`'s assault-map adapter stamps emplacements from
    these) that WP15 only used internally. `crate_slots` (GW-WP18) are also
    positions only — the friendly tour's salvage reward, drawn from `rng` after
    every earlier field so appending them here never perturbs an existing
    layout's rooms/corridors/hazards/lifts/objective (same tail-append
    reasoning `_defender_slots` already relies on).
    """

    width: int
    height: int
    feature_grid: tuple[tuple[str, ...], ...]
    lift_links: tuple[tuple[Vec, Vec], ...]
    deployment_zones: tuple[Vec, ...]
    objective: Vec
    defender_slots: tuple[Vec, ...]
    districts: tuple[District, ...]
    crate_slots: tuple[Vec, ...] = ()


class InteriorGenerationError(Exception):
    """Interior generation failed the connectivity invariant after the bounded retries."""


@dataclass
class _Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


@dataclass
class _Room:
    rect: _Rect  # the full leaf rect (bulkhead ring included)
    role: str
    floor: list[Vec]  # interior cells, margin excluded


def _split(rect: _Rect, target_leaves: int, rng: Random) -> list[_Rect]:
    """BSP-partition `rect` toward `target_leaves` leaves (a soft target — a leaf
    is never split below `_MIN_LEAF` on its shorter usable axis, so a small map or
    a large target may yield fewer leaves than requested)."""
    leaves = [rect]
    while len(leaves) < target_leaves:
        # Split the largest-area leaf that can still be split.
        candidates = sorted(
            range(len(leaves)), key=lambda i: leaves[i].w * leaves[i].h, reverse=True)
        split_idx = None
        for i in candidates:
            r = leaves[i]
            if r.w >= _MIN_LEAF * 2 or r.h >= _MIN_LEAF * 2:
                split_idx = i
                break
        if split_idx is None:
            break  # nothing left worth splitting
        r = leaves.pop(split_idx)
        vertical = r.w >= r.h  # cut the longer axis
        if vertical and r.w >= _MIN_LEAF * 2:
            cut = rng.randint(_MIN_LEAF, r.w - _MIN_LEAF)
            leaves.append(_Rect(r.x, r.y, cut, r.h))
            leaves.append(_Rect(r.x + cut, r.y, r.w - cut, r.h))
        elif r.h >= _MIN_LEAF * 2:
            cut = rng.randint(_MIN_LEAF, r.h - _MIN_LEAF)
            leaves.append(_Rect(r.x, r.y, r.w, cut))
            leaves.append(_Rect(r.x, r.y + cut, r.w, r.h - cut))
        else:
            leaves.append(r)  # can't split this axis either — put it back untouched
            break
    return leaves


def _carve_rooms(
    grid: list[list[str]], leaves: list[_Rect], rng: Random,
) -> list[_Room]:
    rooms: list[_Room] = []
    order = list(range(len(leaves)))
    rng.shuffle(order)
    command_leaf = order[0] if order else 0
    for i, rect in enumerate(leaves):
        role = "command_core" if i == command_leaf else rng.choice(_DISTRICT_ROLES)
        floor: list[Vec] = []
        for y in range(rect.y + _ROOM_MARGIN, rect.y + rect.h - _ROOM_MARGIN):
            for x in range(rect.x + _ROOM_MARGIN, rect.x + rect.w - _ROOM_MARGIN):
                grid[y][x] = role
                floor.append((x, y))
        rooms.append(_Room(rect=rect, role=role, floor=floor))
    return rooms


def _carve_corridor(grid: list[list[str]], a: Vec, b: Vec) -> None:
    (ax, ay), (bx, by) = a, b
    x, y = ax, ay
    while x != bx:
        x += 1 if bx > x else -1
        if grid[y][x] == "bulkhead":
            grid[y][x] = "corridor"
    while y != by:
        y += 1 if by > y else -1
        if grid[y][x] == "bulkhead":
            grid[y][x] = "corridor"


def _connect_rooms(
    grid: list[list[str]], rooms: list[_Room], rng: Random, locked_door_frac: float,
) -> None:
    """Join every room into one spanning tree via straight corridor carves,
    turning a `locked_door_frac` fraction of connections into a `security_door`
    at one endpoint instead of a plain open corridor mouth."""
    order = list(range(len(rooms)))
    rng.shuffle(order)
    connected = [order[0]] if order else []
    remaining = order[1:]
    while remaining:
        # Connect a random remaining room to a random already-connected one —
        # simple random spanning tree, not a minimum-distance MST (art/rules
        # iteration doesn't need optimal corridors, just guaranteed connectivity).
        b = remaining.pop(rng.randrange(len(remaining)))
        a = rng.choice(connected)
        pa, pb = rooms[a].rect, rooms[b].rect
        _carve_corridor(grid, (pa.cx, pa.cy), (pb.cx, pb.cy))
        if rng.random() < locked_door_frac:
            # Stamp the door at the point the corridor first leaves room b's rect.
            bx, by = pb.cx, pb.cy
            ax, ay = pa.cx, pa.cy
            x, y = bx, by
            while pb.x <= x < pb.x + pb.w and pb.y <= y < pb.y + pb.h:
                x += 1 if ax > x else (-1 if ax < x else 0)
                y += 1 if ay > y else (-1 if ay < y else 0)
                if x == bx and y == by:
                    break
            if grid[y][x] == "corridor":
                grid[y][x] = "security_door"
        connected.append(b)


def _sprinkle(
    grid: list[list[str]], rooms: list[_Room], rng: Random,
    hazard_frac: float, cover_frac: float,
) -> None:
    for room in rooms:
        if room.role == "command_core":
            continue  # keep the objective legible — no hazards/cover clutter
        for x, y in room.floor:
            roll = rng.random()
            if roll < hazard_frac:
                grid[y][x] = rng.choice(_HAZARDS)
            elif roll < hazard_frac + cover_frac:
                grid[y][x] = "cover_strut"


def _place_lifts(
    grid: list[list[str]], rooms: list[_Room], rng: Random, count: int,
) -> tuple[tuple[Vec, Vec], ...]:
    links: list[tuple[Vec, Vec]] = []
    eligible = [r for r in rooms if len(r.floor) >= 2]
    for _ in range(count):
        if len(eligible) < 2:
            break
        ra, rb = rng.sample(eligible, 2)
        pa = rng.choice([p for p in ra.floor if grid[p[1]][p[0]] not in ("lift",)])
        pb = rng.choice([p for p in rb.floor if grid[p[1]][p[0]] not in ("lift",)])
        grid[pa[1]][pa[0]] = "lift"
        grid[pb[1]][pb[0]] = "lift"
        links.append((pa, pb))
    return tuple(links)


def _deployment_zones(grid: list[list[str]], width: int, height: int) -> tuple[Vec, ...]:
    """Up to 4 landing points near the hull, spread across the perimeter rather
    than clustered at the first opening a scan happens to find."""
    candidates: list[Vec] = []
    for y in range(height):
        for x in range(width):
            on_edge = x < _EDGE_MARGIN or x >= width - _EDGE_MARGIN \
                or y < _EDGE_MARGIN or y >= height - _EDGE_MARGIN
            if on_edge and grid[y][x] in ("corridor", "plaza"):
                candidates.append((x, y))
    if not candidates:
        return ()
    step = max(1, len(candidates) // 4)
    return tuple(candidates[::step][:4])


def _defender_slots(rooms: list[_Room], rng: Random) -> tuple[Vec, ...]:
    slots: list[Vec] = []
    for room in rooms:
        if room.role == "command_core" or not room.floor:
            continue
        slots.append(rng.choice(room.floor))
    return tuple(slots)


def _crate_slots(rooms: list[_Room], rng: Random, crate_chance: float) -> tuple[Vec, ...]:
    """Up to one salvage crate per non-command_core district (GW-WP18), each district
    an independent `crate_chance` roll. Position-only, exactly like `_defender_slots` —
    a crate is an overlay entity, not a terrain feature, so it never touches `grid`."""
    slots: list[Vec] = []
    for room in rooms:
        if room.role == "command_core" or not room.floor:
            continue
        if rng.random() < crate_chance:
            slots.append(rng.choice(room.floor))
    return tuple(slots)


def _passable(feature: str) -> bool:
    return feature != "bulkhead"


def _connectivity_ok(layout_grid: list[list[str]], layout: InteriorLayout) -> bool:
    """The GW-WP15 connectivity invariant: every deployment zone, the objective,
    and every defender slot share one component over walk edges (4-directional,
    non-`bulkhead`) plus `lift_links` — `security_door` counts as passable (a
    door is always eventually breachable, GW-WP16); `bulkhead` never does and
    must never be the only route anywhere in this graph."""
    if not layout.deployment_zones:
        return False
    width, height = layout.width, layout.height
    start = layout.deployment_zones[0]
    seen = {start}
    stack = [start]
    link_map: dict[Vec, Vec] = {}
    for a, b in layout.lift_links:
        link_map[a] = b
        link_map[b] = a
    while stack:
        x, y = stack.pop()
        neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        if (x, y) in link_map:
            neighbors.append(link_map[(x, y)])
        for nx, ny in neighbors:
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if (nx, ny) in seen:
                continue
            if not _passable(layout_grid[ny][nx]):
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    targets = (layout.objective, *layout.deployment_zones, *layout.defender_slots)
    return all(t in seen for t in targets)


def _district_count(cloud_city_size: int, config: GwCloudCity) -> int:
    return max(1, config.districts_base + config.districts_per_size * (cloud_city_size - 1))


def generate_interior(
    noise_seed: int, cloud_city_size: int, config: GwCloudCity,
) -> InteriorLayout:
    """A deterministic Cloud City interior layout; raises on repeated failure.

    Draws no game RNG — reproducible from `(noise_seed, cloud_city_size, config)`
    alone, exactly like `edge.bigbang.generator.generate` is reproducible from
    `(seed, config)` (G2/G5).
    """
    target_leaves = _district_count(cloud_city_size, config)
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        rng = Random(f"{noise_seed}-{attempt}")
        try:
            grid = [["bulkhead"] * config.width for _ in range(config.height)]
            leaves = _split(_Rect(0, 0, config.width, config.height), target_leaves, rng)
            rooms = _carve_rooms(grid, leaves, rng)
            _connect_rooms(grid, rooms, rng, config.locked_door_frac)
            _sprinkle(grid, rooms, rng, config.hazard_frac, config.cover_frac)
            lift_links = _place_lifts(grid, rooms, rng, config.lift_pairs)
            deployment_zones = _deployment_zones(grid, config.width, config.height)
            defender_slots = _defender_slots(rooms, rng)
            command_room = next(r for r in rooms if r.role == "command_core")
            objective = rng.choice(command_room.floor)
            crate_slots = _crate_slots(rooms, rng, config.crate_chance)
            districts = tuple(
                District(
                    id=i, role=room.role,
                    x0=room.rect.x, y0=room.rect.y,
                    x1=room.rect.x + room.rect.w - 1, y1=room.rect.y + room.rect.h - 1,
                    cx=room.rect.cx, cy=room.rect.cy,
                    floor=tuple(room.floor),
                )
                for i, room in enumerate(rooms)
            )
            layout = InteriorLayout(
                width=config.width, height=config.height,
                feature_grid=tuple(tuple(row) for row in grid),
                lift_links=lift_links, deployment_zones=deployment_zones,
                objective=objective, defender_slots=defender_slots,
                districts=districts, crate_slots=crate_slots,
            )
            if _connectivity_ok(grid, layout):
                return layout
        except (StopIteration, IndexError, ValueError) as exc:
            last_error = exc
            continue
    raise InteriorGenerationError(
        f"Cloud City interior failed to connect after {_MAX_ATTEMPTS} attempts "
        f"(seed={noise_seed}, size={cloud_city_size})"
    ) from last_error
