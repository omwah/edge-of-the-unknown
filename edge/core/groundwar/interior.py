"""Pure station-interior generation for Cloud City assaults (GW-WP15, GW plan D9).

A Cloud City has no ground: its tactical map is the **interior of the floating
station itself**, not planetary terrain wearing a different palette. This module
owns the discrete room/corridor/door layout the way `edge.core.groundwar.terrain`
owns the continuous noise-band biome layout for planets — same split (pure
gameplay feature grid here, glyphs/colours in `edge.art.interior`), different
algorithm, because a station's rooms and corridors are architecture, not organic
noise bands.

The layout is **hub-and-spoke, not a spanning tree over rooms** (interview note:
a random room-to-room spanning tree reads as a maze — you have to cut through
other rooms' doorways to get anywhere), and it is **two levels of branching, not
one long hallway** (follow-up interview note: a single spine with a whole half's
rooms hanging directly off it makes each room span the entire half — too big, and
only one corridor). One horizontal corridor **spine** runs the width of the
station; each spine half (north/south) is divided along its width into several
**branch corridors** (`_half_leaves`), and rooms are stacked in pairs flanking
each branch, not the spine itself. So the hierarchy is spine ->
branch -> room, three hops deep, and a room only ever needs to be as tall as its
stack slot, not the whole half. `_spine_band` reserves the spine's rows before
anything else is placed, so nothing can span across it; `_cut_x`/`_cut_y` are the
two explicit single-axis BSP cuts (`_half_leaves` picks the right one at each
level — a column split for branches, a stack split for the rooms flanking one).
See `_connect_to_spine` for the stub/door pass that stamps the spine, every branch
column, and one door per room on the wall facing its own branch.

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
_DISTRICT_ROLES: tuple[str, ...] = (
    "plaza", "habitation", "engineering", "bar", "store", "promenade")

_HAZARDS: tuple[str, ...] = ("vacuum", "fire", "electrical")

# Every feature name this generator can emit. `GroundwarConfig` validates that
# `terrain:` defines a `GwTerrain` class for each of these, exactly as
# `edge.core.groundwar.terrain.LANDABLE_BIOMES` is validated against `BIOME_BANDS`.
INTERIOR_FEATURES: tuple[str, ...] = (
    "corridor", "plaza", "habitation", "engineering", "command_core",
    "bar", "store", "promenade",
    "cover_strut", "bulkhead", "security_door", "lift",
    "fountain_jet", "fountain_basin", "bar_counter", "bar_counter_end",
    "shelf", "shelf_end", "bed", "console", "table", "stool",
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
_SPINE_THICKNESS = 4  # rows reserved for the main corridor spine
_BRANCH_WIDTH = 3  # columns reserved for each branch corridor stem
_ROOMS_PER_BRANCH = 2  # soft target: how many rooms a branch is sized to serve —
# low on purpose so a half gets several branches rather than one or two wide ones
# (follow-up interview note: "we need multiple branching corridors")


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


_Cut = Callable[[_Rect, Random], "tuple[_Rect, _Rect] | None"]

# A branch segment must fit a branch column plus two _MIN_LEAF flanking rooms —
# a plain `_MIN_LEAF * 2` (enough for two flanks alone) let `_cut_x` cut segments
# too thin for their branch column, yielding sliver rooms a few cells wide.
_MIN_SEGMENT_W = _BRANCH_WIDTH + 2 * _MIN_LEAF


def _cut_x(r: _Rect, rng: Random) -> tuple[_Rect, _Rect] | None:
    """Bisect `r` on the x axis (left/right); `None` if `r.w` can't clear
    `_MIN_SEGMENT_W * 2`. Used only to divide a spine half into branch-corridor
    segments, so the threshold accounts for the branch column each child still
    needs to reserve, not just its two flanking rooms."""
    if r.w < _MIN_SEGMENT_W * 2:
        return None
    cut = rng.randint(_MIN_SEGMENT_W, r.w - _MIN_SEGMENT_W)
    return _Rect(r.x, r.y, cut, r.h), _Rect(r.x + cut, r.y, r.w - cut, r.h)


def _cut_y(r: _Rect, rng: Random) -> tuple[_Rect, _Rect] | None:
    """Bisect `r` on the y axis (top/bottom); `None` if `r.h` can't clear
    `_MIN_LEAF * 2`. Used to stack rooms flanking one branch corridor."""
    if r.h < _MIN_LEAF * 2:
        return None
    cut = rng.randint(_MIN_LEAF, r.h - _MIN_LEAF)
    return _Rect(r.x, r.y, r.w, cut), _Rect(r.x, r.y + cut, r.w, r.h - cut)


def _bsp_leaves(rect: _Rect, target_leaves: int, rng: Random, cut: _Cut) -> list[_Rect]:
    """BSP-partition `rect` toward `target_leaves` leaves along a single axis,
    picked by the caller via `cut` (`_cut_x` or `_cut_y` — never chosen by aspect
    ratio here, that was the pre-spine bug: an aspect-ratio pick silently changes
    axis mid-tree). A soft target — a leaf is never split below `_MIN_LEAF` on its
    split axis, so a small map or a large target may yield fewer leaves than
    requested."""
    leaves = [rect]
    while len(leaves) < target_leaves:
        # Split the largest-area leaf that can still be split.
        candidates = sorted(
            range(len(leaves)), key=lambda i: leaves[i].w * leaves[i].h, reverse=True)
        split_idx = next((i for i in candidates if cut(leaves[i], rng)), None)
        if split_idx is None:
            break  # nothing left worth splitting
        r = leaves.pop(split_idx)
        pieces = cut(r, rng)
        assert pieces is not None  # split_idx was only chosen when cut succeeds
        leaves.extend(pieces)
    return leaves


def _distribute(total: int, parts: int) -> list[int]:
    """`total` split as evenly as possible across `parts` buckets, remainder going
    to the first buckets — how many rooms each branch in a half is asked for."""
    base, extra = divmod(total, parts)
    return [base + 1 if i < extra else base for i in range(parts)]


def _half_leaves(half: _Rect, target: int, rng: Random) -> tuple[list[_Rect], list[_Rect]]:
    """Rooms and branch-corridor columns for one spine half — the "multiple
    branching corridors" follow-up: `half`'s width is first cut (`_cut_x`) into
    roughly `target / _ROOMS_PER_BRANCH` segments, one branch per segment; each
    branch reserves a `_BRANCH_WIDTH`-wide column spanning the segment's *full*
    height (reserved before any room is carved, same discipline `_spine_band`
    uses for the main corridor, so a branch always reaches unobstructed from the
    half's outer edge to the spine). The segment's two flanking strips are then
    each stacked (`_cut_y`) into rooms facing the branch — smaller and more
    numerous than one room spanning the whole half."""
    if target <= 0:
        return [], []
    n_branches = max(1, -(-target // _ROOMS_PER_BRANCH))
    segments = _bsp_leaves(half, n_branches, rng, _cut_x)
    counts = _distribute(target, len(segments))
    rooms: list[_Rect] = []
    branches: list[_Rect] = []
    for seg, count in zip(segments, counts):
        half_bw = _BRANCH_WIDTH // 2
        bx0 = max(seg.x + 1, seg.cx - half_bw)
        bx1 = min(seg.x + seg.w - 1, bx0 + _BRANCH_WIDTH)
        if bx1 <= bx0:
            continue  # segment too narrow for a branch column at all — no rooms either
        branch = _Rect(bx0, seg.y, bx1 - bx0, seg.h)
        branches.append(branch)
        left = _Rect(seg.x, seg.y, bx0 - seg.x, seg.h)
        right = _Rect(bx1, seg.y, seg.x + seg.w - bx1, seg.h)
        left_n = count // 2
        right_n = count - left_n
        if left_n > 0:
            rooms.extend(_bsp_leaves(left, left_n, rng, _cut_y))
        if right_n > 0:
            rooms.extend(_bsp_leaves(right, right_n, rng, _cut_y))
    return rooms, branches


def _spine_band(width: int, height: int) -> tuple[int, int]:
    """The `[y0, y1)` row range reserved for the main corridor spine, vertically
    centred. Raises `InteriorGenerationError` immediately — rather than burning the
    bounded-retry budget on a map shape that can never work regardless of seed —
    when the remaining north/south halves can't each hold at least one
    `_MIN_LEAF`-tall room."""
    y0 = height // 2 - _SPINE_THICKNESS // 2
    y1 = y0 + _SPINE_THICKNESS
    if y0 < _MIN_LEAF or (height - y1) < _MIN_LEAF:
        raise InteriorGenerationError(
            f"Cloud City map too short for a corridor spine (height={height}, "
            f"needs >= {2 * _MIN_LEAF + _SPINE_THICKNESS})")
    return y0, y1


def _generate_leaves(
    width: int, height: int, target_leaves: int, rng: Random,
) -> tuple[list[_Rect], list[_Rect], int, int]:
    """Room and branch-corridor rects split into a north band and a south band
    around a reserved horizontal corridor spine — hub-and-spoke, not a spanning
    tree over rooms (the "should not look like a maze" interview note), and two
    levels of branching, not one long hallway (the "rooms are too big, multiple
    branching corridors" follow-up): every room gets exactly one door onto its own
    branch (`_connect_to_spine`), never onto the spine or another room directly."""
    y0, y1 = _spine_band(width, height)
    north_n = -(-target_leaves // 2)  # ceil — north gets the extra room on an odd split
    south_n = target_leaves - north_n
    north_rooms, north_branches = _half_leaves(_Rect(0, 0, width, y0), north_n, rng)
    south_rooms, south_branches = _half_leaves(_Rect(0, y1, width, height - y1), south_n, rng)
    return north_rooms + south_rooms, north_branches + south_branches, y0, y1


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


def _connect_to_spine(
    grid: list[list[str]], rooms: list[_Room], branches: list[_Rect],
    rng: Random, locked_door_frac: float, spine_y0: int, spine_y1: int,
) -> None:
    """Stamp the spine band and every branch column as corridor, then give each
    room exactly one door on the wall facing its own branch — three-hop
    hub-and-spoke (spine -> branch -> room), never room-to-room and never
    room-to-spine directly. A branch column spans its segment's full height
    (`_half_leaves` reserved it before any room was carved), so its far edge is
    already flush against the spine band stamped just above — no separate stub
    needed to join the two, exactly like a room used to sit flush on the spine
    before branches existed.

    `locked_door_frac` still turns a room's own doorway (where it meets its
    branch) into a `security_door` instead of an open mouth, same knob as before.
    """
    width = len(grid[0])
    for y in range(spine_y0, spine_y1):
        for x in range(1, width - 1):
            grid[y][x] = "corridor"
    for b in branches:
        for y in range(b.y, b.y + b.h):
            for x in range(b.x, b.x + b.w):
                grid[y][x] = "corridor"
    for room in rooms:
        r = room.rect
        branch = next(
            (b for b in branches
             if b.y <= r.y and r.y + r.h <= b.y + b.h
             and (b.x == r.x + r.w or r.x == b.x + b.w)),
            None)
        if branch is None:
            continue  # degenerate leaf with no matching branch — left unreachable, caught by _connectivity_ok
        door_x = r.x + r.w - 1 if branch.x == r.x + r.w else r.x  # own wall facing the branch
        grid[r.cy][door_x] = (
            "security_door" if rng.random() < locked_door_frac else "corridor")


def _grow_patch(floor: set[Vec], start: Vec, budget: int, rng: Random) -> list[Vec]:
    """Randomized flood-fill from `start` over `floor`, collecting up to `budget`
    4-connected cells — one contiguous patch instead of independent per-cell rolls,
    so a hazard or a run of cover reads as a single deliberate zone (a scorched
    corner, a bank of struts) rather than scattered dots (the "chaotic" note)."""
    if budget <= 0:
        return []
    seen = {start}
    patch = [start]
    frontier = [start]
    while frontier and len(patch) < budget:
        cx, cy = frontier.pop(rng.randrange(len(frontier)))
        neighbors = [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]
        rng.shuffle(neighbors)
        for n in neighbors:
            if n in floor and n not in seen:
                seen.add(n)
                patch.append(n)
                frontier.append(n)
                if len(patch) >= budget:
                    break
    return patch


def _sprinkle(
    grid: list[list[str]], rooms: list[_Room], rng: Random,
    hazard_frac: float, cover_frac: float,
) -> None:
    """One hazard patch and one cover-strut patch per non-command-core room, each
    sized to its room's own `hazard_frac`/`cover_frac` share of the floor — see
    `_grow_patch` for why a patch, not a per-cell roll."""
    for room in rooms:
        if room.role == "command_core" or not room.floor:
            continue  # keep the objective legible — no hazards/cover clutter
        floor = set(room.floor)
        hazard_budget = round(len(room.floor) * hazard_frac)
        if hazard_budget > 0:
            kind = rng.choice(_HAZARDS)
            for x, y in _grow_patch(floor, rng.choice(room.floor), hazard_budget, rng):
                grid[y][x] = kind
                floor.discard((x, y))
        cover_budget = round(len(room.floor) * cover_frac)
        if cover_budget > 0 and floor:
            for x, y in _grow_patch(floor, rng.choice(list(floor)), cover_budget, rng):
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


def _landmark_fits(grid: list[list[str]], floor: set[Vec], role: str, cells: list[Vec]) -> bool:
    return all(p in floor and grid[p[1]][p[0]] == role for p in cells)


def _place_row(
    grid: list[list[str]], floor: set[Vec], role: str,
    x0: int, x1: int, y: int, stride: int, kind: str,
) -> None:
    """One `kind` cell every `stride` columns along row `y` — a repeated bunk, console,
    or table run, à la a reference deck-plan's row of identical cabins/consoles. Each
    point is independent (unlike the atomic shapes above): a hazard already sitting on
    one slot just skips that slot rather than cancelling the whole row."""
    for x in range(x0, x1, stride):
        if (x, y) in floor and grid[y][x] == role:
            grid[y][x] = kind


def _place_grid(
    grid: list[list[str]], floor: set[Vec], role: str,
    x0: int, x1: int, y0: int, y1: int, stride_x: int, stride_y: int, kind: str,
) -> None:
    """A regular lattice of `kind` cells — a mess hall's grid of dining tables, not one
    scattered per room. Same independent-point tolerance as `_place_row`."""
    for y in range(y0, y1, stride_y):
        _place_row(grid, floor, role, x0, x1, y, stride_x, kind)


def _place_landmarks(grid: list[list[str]], rooms: list[_Room]) -> None:
    """Stamp recognisable, regularly-arranged furniture into each amenity room instead
    of covering it in dense per-cell texture (interview notes: "too busy", then "still
    looks chaotic" once texture alone was thinned) — a fountain anchors a plaza, a
    counter with stool seating and a few tables a bar, shelf runs a store, a row of
    consoles engineering, a row of bunks habitation, a grid of tables a promenade, and a
    console ring around the objective in command_core (the reference deck-plan's
    bridge/cockpit nook). Order comes from *regularity*
    — a lattice at a fixed stride, like a real deck plan's repeated cabins and dining
    tables — not merely from fewer objects. Every shape composed of two-plus distinct
    feature names (a jet vs. a basin ring, a counter body vs. its end caps, a shelf run
    vs. its end posts) so a landmark reads as a small drawn object, not a solid colour
    block or, for the row/grid placements, a single repeated glyph.

    Purely geometric off each room's own rect/floor, so it draws no `rng` and is safe
    to run last among the grid-mutating passes: every placement only claims cells still
    holding the room's own unclaimed floor value, so a hazard, cover strut, or lift that
    got there first is left alone, and a room too small for a shape silently gets less
    or none of it (matching `_defender_slots`'s own tolerance for a room with nothing to
    give). A landmark is a plain `feature_grid` value like `lift` — cover/move_cost come
    from its own `GwTerrain` entry, not the room it sits in — so it needs no special-
    casing anywhere else (DTO projection, movement, the connectivity check) beyond that.
    """
    for room in rooms:
        floor = set(room.floor)
        r = room.rect
        if room.role == "plaza":
            cx, cy = r.cx, r.cy
            basin = [(cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]
            shape = [(cx, cy), *basin]
            if _landmark_fits(grid, floor, "plaza", shape):
                grid[cy][cx] = "fountain_jet"
                for x, y in basin:
                    grid[y][x] = "fountain_basin"
        elif room.role == "bar":
            xs = list(range(r.x + 2, r.x + r.w - 2))
            y = r.y + 2
            shape = [(x, y) for x in xs]
            if len(shape) >= 3 and _landmark_fits(grid, floor, "bar", shape):
                grid[y][xs[0]] = grid[y][xs[-1]] = "bar_counter_end"
                for x in xs[1:-1]:
                    grid[y][x] = "bar_counter"
                stool_y = y + 1  # patrons' side of the counter, à la the reference deck plan
                for x in xs[1:-1:2]:
                    if (x, stool_y) in floor and grid[stool_y][x] == "bar":
                        grid[stool_y][x] = "stool"
            _place_grid(grid, floor, "bar", r.x + 2, r.x + r.w - 2, r.y + 4, r.y + r.h - 2,
                        5, 3, "table")
        elif room.role == "command_core":
            # A console ring around the objective — the reference deck-plan's circular
            # bridge/cockpit consultation pit — reusing the `console` feature engineering
            # already has rather than adding a lookalike glyph for one landmark.
            cx, cy = r.cx, r.cy
            ring = [(cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]
            if _landmark_fits(grid, floor, "command_core", ring):
                for x, y in ring:
                    grid[y][x] = "console"
        elif room.role == "store":
            xs = list(range(r.x + 2, r.x + r.w - 2))
            for row_y in range(r.y + 2, r.y + r.h - 2, 3):
                shape = [(x, row_y) for x in xs]
                if len(shape) >= 3 and _landmark_fits(grid, floor, "store", shape):
                    grid[row_y][xs[0]] = grid[row_y][xs[-1]] = "shelf_end"
                    for x in xs[1:-1]:
                        grid[row_y][x] = "shelf"
        elif room.role == "habitation":
            _place_row(grid, floor, "habitation", r.x + 2, r.x + r.w - 2, r.cy, 3, "bed")
        elif room.role == "engineering":
            _place_row(grid, floor, "engineering", r.x + 2, r.x + r.w - 2, r.y + 2, 3, "console")
        elif room.role == "promenade":
            _place_grid(grid, floor, "promenade", r.x + 2, r.x + r.w - 2, r.y + 2, r.y + r.h - 2,
                        5, 4, "table")


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

    One corridor spine down the middle, rooms hanging off it north and south —
    see the module docstring and `_generate_leaves`/`_connect_to_spine`. Draws no
    game RNG — reproducible from `(noise_seed, cloud_city_size, config)` alone,
    exactly like `edge.bigbang.generator.generate` is reproducible from
    `(seed, config)` (G2/G5).
    """
    target_leaves = _district_count(cloud_city_size, config)
    _spine_band(config.width, config.height)  # raises immediately if this map shape can't work
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        rng = Random(f"{noise_seed}-{attempt}")
        try:
            grid = [["bulkhead"] * config.width for _ in range(config.height)]
            leaves, branches, spine_y0, spine_y1 = _generate_leaves(
                config.width, config.height, target_leaves, rng)
            rooms = _carve_rooms(grid, leaves, rng)
            _connect_to_spine(
                grid, rooms, branches, rng, config.locked_door_frac, spine_y0, spine_y1)
            _sprinkle(grid, rooms, rng, config.hazard_frac, config.cover_frac)
            lift_links = _place_lifts(grid, rooms, rng, config.lift_pairs)
            _place_landmarks(grid, rooms)
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
