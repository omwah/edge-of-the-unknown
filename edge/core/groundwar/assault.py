"""Pure ground-assault map generation, difficulty derivation, and garrison economy
(GW-WP09, GW plan D7-D11).

The production replacement for the POC's invented setup-menu difficulty
(`edge.groundwar.mapgen`/`GwDifficulty`). Given a world's live state — population,
citadel level, owner, inhabiting species — it derives a battlefield size and
surrender threshold, then lays out a walled-city battlefield as a **frozen,
non-hashed** `AssaultMap` regenerated on demand (G5), mirroring `survey.py`'s
shape exactly. `AssaultOperation` stores only the seed + the snapshotted
derivation inputs; this module turns those back into a layout, so a save stays
the command log, not a dump of every cell.

**The garrison model is not a POC port.** The POC's `GarrisonUnit`s are spawned
dynamically, wave by wave, only during live combat (`rules._spawn_sortie`) —
never placed at battle setup. D11 requires the opposite: a **persistent, finite,
casualty-reducible** headcount living on `Planet.garrison_infantry`/
`garrison_armor`. `generate_assault_map` therefore places **zero** garrison
units — WP10 spawns/places tactical units from `AssaultOperation.reserved_infantry`/
`reserved_armor` (the headcount `BeginAssault` snapshots at open, GW plan
decision #1). The terrain/city/structure generation *is* a near-verbatim port
of `edge.groundwar.mapgen`, since that part is unaffected by the garrison-model
change.

Pure `edge.core`: imports the terrain seam, `edge.core.planets.colonist_capacity`
(one-directional — this module is never imported back by `planets.py`), and
stdlib only. Deliberately does not import `edge.core.rules`, `edge.core.citadels`,
or anything in `edge.server`/`edge.tui`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from random import Random
from typing import Literal

from edge.core.config import GameConfig
from edge.core.groundwar.models import AssaultOperation
from edge.core.groundwar.terrain import generate_feature_grid
from edge.core.models import AlienSpecies, Planet, UniverseState
from edge.core.planets import colonist_capacity

Vec = tuple[int, int]

# Kept in lockstep with `citadels.CITADEL_MAX` by convention (both are the fixed
# ladder length); not imported to avoid a `planets.py`-adjacent import cycle risk
# (this module already imports `edge.core.planets`, and `citadels.py` does too).
_CITADEL_MAX = 3

StructureKind = Literal[
    "wall", "gate", "turret", "aa", "sensor", "citadel_gun",
    "building_military", "building_civilian",
]

_CITY_NAMES = (
    "Klendathu Down", "Port Joel", "Zegema Beach", "New Cyrene", "Uxmal",
    "Fort Bannon", "Carr's Landing", "Hesperus", "Tango Urilla", "Sheol",
)

_STREET_FEATURE = "dust"  # what city ground plays as (move 1, no cover)
_CAPITAL_SIZE = (30, 14)  # (w, h) — cosmetic footprint dims, not balance (ported from the POC)
_CITY_SIZE = (24, 11)
_BUILDING_MILITARY_FRAC = 0.3  # the POC's military/civilian building-block split


@dataclass(frozen=True, slots=True)
class AssaultStructure:
    """One stamped static defense, at generation-time full health (GW-WP09).

    No live/mutable `hp` here — this is a frozen, regenerated map (G5), exactly
    like `SurveyMap`. Live damage tracking is WP10's id-keyed overlay on
    `AssaultOperation`, the same way `SurveyOperation.resolved_discovery_ids`
    overlays `SurveySite.found` without `SurveySite` itself being mutable.
    """

    id: int
    kind: StructureKind
    x: int
    y: int
    city_id: int
    hp_max: int


@dataclass(frozen=True, slots=True)
class AssaultCity:
    id: int
    name: str
    cx: int
    cy: int
    x0: int
    y0: int
    x1: int
    y1: int
    is_citadel: bool = False
    citadel_level: int = 0

    def inside(self, x: int, y: int) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


@dataclass(frozen=True, slots=True)
class AssaultMap:
    """The regenerated, non-hashed battlefield layout for one assault (G5).

    Reconstructed from `(seed, planet_type, cities, citadel_level)`; safely
    discardable and excluded from `state_hash`, same contract as `SurveyMap`.
    Contains **zero** placed garrison units (see module docstring) — the
    persistent garrison headcount lives on `AssaultOperation.reserved_infantry`/
    `reserved_armor`; WP10 is responsible for spawning/placing tactical units
    from it. The `citadel_gun` structure is a *ground* emplacement guarding the
    capital city — a distinct, capturable tactical asset from the orbital gun
    tracked by `Planet.gun_integrity`/`citadels.has_gun` (GW plan decision #7).
    There is no "orbital gun"/"orbital base" entry in `StructureKind`, so this
    generator has nothing that could depict an already-razed base or
    already-silenced orbital gun as intact.
    """

    width: int
    height: int
    feature: tuple[tuple[str, ...], ...]
    blocked: frozenset[Vec]
    cities: tuple[AssaultCity, ...]
    structures: tuple[AssaultStructure, ...]
    landing_x: int
    landing_y: int

    def structures_in(self, city_id: int, *kinds: StructureKind) -> tuple[AssaultStructure, ...]:
        return tuple(s for s in self.structures
                     if s.city_id == city_id and (not kinds or s.kind in kinds))


@dataclass(frozen=True, slots=True)
class AssaultDifficulty:
    """Live-derived battlefield sizing (GW plan D11) — the frozen inputs
    `BeginAssault` snapshots onto `AssaultOperation` and `generate_assault_map`
    consumes."""

    cities: int
    citadel_level: int
    surrender_threshold: int


def derive_difficulty(
    planet: Planet, config: GameConfig, *, distance_band: str,
    species: AlienSpecies | None,
) -> AssaultDifficulty:
    """Derive battlefield size + surrender threshold from live world state (D11).

    Reads only world-intrinsic state — population/capacity, citadel level
    (including whether a gun was ever built, decision #7 below), owner kind, the
    inhabiting species' *base* disposition (not the player's live relationship,
    GW plan decision #6), and the world's distance band — so the same world
    derives the same difficulty for every player and is unaffected by anything
    the calling player carries (fighters, alignment, standing).

    "Surviving gun" (GW plan line 1102) is read as "did this world ever field a
    citadel gun," not "is the orbital gun currently up": by the time this runs,
    `BeginAssault` has already confirmed `ground_access` is droppable, which
    means `citadels.has_gun(planet, config)` is *always* False (the gun-silence
    blocker is a precondition of reaching this point at all). Reading it as
    current `gun_integrity > 0` would make it a permanent no-op, so instead a
    world with `citadel_level >= gun_min_level` — one that built and lost a gun
    in the siege — scores a `had_gun_mult` harder than one that never invested
    in one, even though the literal weapon is down either way (decision #7).
    """
    assert config.groundwar is not None
    cfg = config.groundwar.assault_difficulty
    capacity = colonist_capacity(planet, config)
    score = float(capacity)
    if (species is not None and config.aliens is not None
            and species.base_disposition < config.aliens.amity_threshold):
        score *= cfg.hostility_mult
    if planet.owner.kind == "alliance":
        score *= cfg.alliance_owned_mult
    score *= cfg.band_mult.get(distance_band, 1.0)
    if config.citadels is not None and planet.citadel_level >= config.citadels.gun_min_level:
        score *= cfg.had_gun_mult
    cities = min(cfg.max_cities, cfg.min_cities + int(score // cfg.population_per_extra_city))
    citadel_level = min(planet.citadel_level, _CITADEL_MAX)
    surrender_threshold = max(
        1, cfg.surrender_threshold_base + citadel_level * cfg.surrender_threshold_per_citadel_level)
    return AssaultDifficulty(
        cities=cities, citadel_level=citadel_level, surrender_threshold=surrender_threshold)


# --- battlefield generation (ported from edge.groundwar.mapgen, GW-WP09) ------


def _footprint_passable_frac(
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


def _add_structure(
    structures: list[AssaultStructure], struct_at: dict[Vec, int], next_id: list[int],
    kind: StructureKind, x: int, y: int, city_id: int, hp: int,
) -> None:
    s = AssaultStructure(id=next_id[0], kind=kind, x=x, y=y, city_id=city_id, hp_max=hp)
    structures.append(s)
    struct_at[(x, y)] = s.id
    next_id[0] += 1


def _stamp_city(
    feature: list[list[str]], blocked: set[Vec], structures: list[AssaultStructure],
    struct_at: dict[Vec, int], next_id: list[int], config: GameConfig, rng: Random,
    city_id: int, name: str, x0: int, y0: int, w: int, h: int, *,
    is_citadel: bool, citadel_level: int,
) -> AssaultCity:
    assert config.groundwar is not None
    d = config.groundwar.defenses
    city = AssaultCity(id=city_id, name=name, cx=x0 + w // 2, cy=y0 + h // 2,
                       x0=x0, y0=y0, x1=x0 + w - 1, y1=y0 + h - 1,
                       is_citadel=is_citadel, citadel_level=citadel_level)

    # Pave the footprint: city ground plays as street regardless of what's under it.
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            feature[y][x] = _STREET_FEATURE

    wall_mult = 2.0 if citadel_level >= 3 else 1.0
    wall_hp = round(d.wall.hp * wall_mult)

    # Perimeter walls, with a gate at the middle of each vertical side.
    gates = {(x0, y0 + h // 2), (x0 + w - 1, y0 + h // 2)}
    corners = {(x0, y0), (x0 + w - 1, y0), (x0, y0 + h - 1), (x0 + w - 1, y0 + h - 1)}
    mids = {(x0 + w // 2, y0), (x0 + w // 2, y0 + h - 1)}  # mid top/bottom wall
    for x in range(x0, x0 + w):
        for y in (y0, y0 + h - 1):
            pos = (x, y)
            if pos in corners:
                _add_structure(structures, struct_at, next_id, "turret", *pos, city.id, d.turret.hp)
            elif pos in mids and citadel_level >= 1:
                _add_structure(structures, struct_at, next_id, "turret", *pos, city.id, d.turret.hp)
            else:
                _add_structure(structures, struct_at, next_id, "wall", *pos, city.id, wall_hp)
            blocked.add(pos)
    for y in range(y0 + 1, y0 + h - 1):
        for x in (x0, x0 + w - 1):
            pos = (x, y)
            if pos in gates:
                _add_structure(structures, struct_at, next_id, "gate", *pos, city.id, d.gate.hp)
            else:
                _add_structure(structures, struct_at, next_id, "wall", *pos, city.id, wall_hp)
                blocked.add(pos)

    # Interior emplacements: AA battery, sensor tower (an extra AA on a level-3 citadel),
    # and — only on the capital at citadel_level >= 2 — exactly one citadel_gun.
    _add_structure(structures, struct_at, next_id, "aa", city.cx - w // 4, city.cy - 1, city.id, d.aa.hp)
    _add_structure(structures, struct_at, next_id, "sensor", city.cx + w // 4, city.cy + 1, city.id, d.sensor.hp)
    if citadel_level >= 3:
        _add_structure(structures, struct_at, next_id, "aa", city.cx + w // 4, city.cy - 1, city.id, d.aa.hp)
    if is_citadel and citadel_level >= 2:
        _add_structure(structures, struct_at, next_id, "citadel_gun", city.cx, city.cy, city.id, d.citadel_gun.hp)

    # Building blocks on a street grid: rows every other line, 2-cell blocks with gaps.
    for y in range(y0 + 2, y0 + h - 2, 2):
        for bx in range(x0 + 3, x0 + w - 4, 4):
            for x in (bx, bx + 1):
                if (x, y) in struct_at or abs(x - city.cx) + abs(y - city.cy) <= 1:
                    continue
                military = rng.random() < _BUILDING_MILITARY_FRAC
                kind: StructureKind = "building_military" if military else "building_civilian"
                hp = d.building_military_hp if military else d.building_civilian_hp
                _add_structure(structures, struct_at, next_id, kind, x, y, city.id, hp)
                blocked.add((x, y))
    return city


def _move_cost(feature: list[list[str]], blocked: set[Vec], config: GameConfig, x: int, y: int) -> int:
    if (x, y) in blocked:
        return 0
    assert config.groundwar is not None
    tc = config.groundwar.terrain.get(feature[y][x])
    return tc.move_cost if tc else 1


def _in_bounds(width: int, height: int, x: int, y: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def _passable_components(
    feature: list[list[str]], blocked: set[Vec], config: GameConfig, width: int, height: int
) -> tuple[list[list[int]], dict[int, int]]:
    """Label the 4-connected passable regions; return (labels, sizes) — ported from
    `survey.py::_passable_components` (GW-WP09 decision #3: a new invariant the POC
    never needed, since its troopers can jump)."""
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


def _landing(labels: list[list[int]], comp: int, width: int, height: int) -> Vec:
    """Land near the map's left-middle, but only inside the cities' component
    (ported from `survey.py::_landing`)."""
    mid = height // 2
    for x in range(4, width):
        for dy in range(mid):
            for y in (mid - dy, mid + dy):
                if 0 <= y < height and labels[y][x] == comp:
                    return x, y
    return 4, mid


def generate_assault_map(
    config: GameConfig, *, seed: int, planet_type: str, cities: int, citadel_level: int,
) -> AssaultMap:
    """Lay out a defended battlefield: terrain + `cities` walled cities, the last one
    the citadel capital at `citadel_level` (pure, deterministic, GW-WP09/G5).

    Ports `edge.groundwar.mapgen.generate_battle`/`_stamp_city` near-verbatim (walls
    with gates, corner turrets, mid-wall turrets at `citadel_level >= 1`, AA + sensor,
    an extra AA + hardened walls at `citadel_level >= 3`, exactly one `citadel_gun` on
    the capital at `citadel_level >= 2`, building blocks), with one addition the POC
    never needed (its troopers can jump, so it never checked foot-reachability): after
    every city is stamped, the largest 4-connected passable component is computed and
    the landing point confined to it — never re-rolled, so the same seed always
    produces the same map (determinism over retry, matching survey's own "confine,
    don't redraw" contract, decision #3). Places **zero** garrison units (module
    docstring).
    """
    assert config.groundwar is not None
    width, height = config.groundwar.battlefield.width, config.groundwar.battlefield.height
    rng = Random(f"{seed}|assault|{planet_type}|{cities}|{citadel_level}")
    feature = generate_feature_grid(rng.randint(0, 2**31 - 1), planet_type, width, height)
    blocked: set[Vec] = set()
    structures: list[AssaultStructure] = []
    struct_at: dict[Vec, int] = {}
    next_id = [1]

    names = list(_CITY_NAMES)
    rng.shuffle(names)
    n = cities
    built: list[AssaultCity] = []
    for i in range(n):
        is_citadel = i == n - 1
        w, h = _CAPITAL_SIZE if is_citadel else _CITY_SIZE
        lane_x0 = width * (i + 1) // (n + 1)
        lane_x1 = width * (i + 2) // (n + 1) - w - 2
        best: tuple[float, int, int] | None = None
        for _ in range(24):
            x0 = rng.randint(max(2, lane_x0), max(max(2, lane_x0), lane_x1))
            y0 = rng.randint(3, height - h - 3)
            frac = _footprint_passable_frac(feature, config, x0, y0, w, h)
            if best is None or frac > best[0]:
                best = (frac, x0, y0)
            if frac >= 0.7:
                break
        assert best is not None
        city = _stamp_city(
            feature, blocked, structures, struct_at, next_id, config, rng,
            len(built) + 1, names[i % len(names)], best[1], best[2], w, h,
            is_citadel=is_citadel, citadel_level=citadel_level if is_citadel else 0)
        built.append(city)

    labels, sizes = _passable_components(feature, blocked, config, width, height)
    comp = max(sizes, key=lambda k: sizes[k]) if sizes else 0
    landing_x, landing_y = _landing(labels, comp, width, height)

    return AssaultMap(
        width=width, height=height,
        feature=tuple(tuple(row) for row in feature), blocked=frozenset(blocked),
        cities=tuple(built), structures=tuple(structures),
        landing_x=landing_x, landing_y=landing_y,
    )


def assault_map_for(state: UniverseState, op: AssaultOperation, config: GameConfig) -> AssaultMap:
    """Regenerate the live battlefield for an active assault operation (G5) — the
    projection seam, mirroring `survey.survey_map_for`."""
    return generate_assault_map(
        config, seed=op.seed, planet_type=op.planet_type,
        cities=op.cities, citadel_level=op.citadel_level)


# --- garrison economy (pure; GW plan D11) --------------------------------------


def seed_garrison(
    config: GameConfig, *, capacity: int, citadel_level: int, distance_band: str,
    hostile: bool, alliance_owned: bool, rng: Random,
) -> tuple[int, int]:
    """The (infantry, armor) headcount a freshly-inhabited world starts with (D11).

    Called once, at big-bang seeding, from `edge.bigbang.inhabitants._settle` against
    its salted sub-RNG (never a fresh `Random()`, so the universe stays reproducible
    per seed). Scales the same way the discovery/species bands already do: a wary/
    hostile species, a bloc's own holding, and depth from the Core all raise the
    seeded force; citadel level reuses the *identical* multiplier
    `citadels.citadel_defense_mult` reads for the legacy invasion path
    (`config.citadels.levels[level-1].garrison_mult`), read inline here rather than
    imported (keeps this module free of a `planets.py`-adjacent import cycle risk).
    Armor is seeded only at `citadel_level >= seed_armor_min_citadel_level`, as a
    fraction of the seeded infantry; a world under that level fields no vehicles at
    all, matching the POC's `armor_from_wave` gating in spirit.
    """
    assert config.groundwar is not None
    cfg = config.groundwar.garrison_economy
    frac = rng.uniform(cfg.seed_infantry_frac_min, cfg.seed_infantry_frac_max)
    mult = 1.0
    if hostile:
        mult *= cfg.seed_hostility_mult
    if alliance_owned:
        mult *= cfg.seed_alliance_mult
    mult *= cfg.seed_band_mult.get(distance_band, 1.0)
    if config.citadels is not None and citadel_level >= 1:
        mult *= config.citadels.levels[min(citadel_level, _CITADEL_MAX) - 1].garrison_mult
    infantry = round(capacity * frac * mult)
    armor = round(infantry * cfg.seed_armor_frac) if citadel_level >= cfg.seed_armor_min_citadel_level else 0
    return infantry, armor


def _recover_toward_cap(current: int, cap: int, frac: float) -> int:
    """One day's step toward `cap` at `frac` of the remaining headroom.

    Rounds, but never rounds down to zero progress while headroom and `frac` are
    both positive — otherwise a small gap and a small `frac` could round to 0
    forever and the garrison would never actually reach `cap`. Never overshoots.
    """
    headroom = cap - current
    if headroom <= 0 or frac <= 0.0:
        return current
    gained = max(1, round(headroom * frac))
    return current + min(gained, headroom)


def apply_militia_recovery(planet: Planet, config: GameConfig) -> Planet:
    """One day's automatic militia regrowth toward the population-fraction cap (D11).

    Population-fraction/day, **allocation-independent** — runs regardless of
    ownership (a native/unaligned world regrows its own defenders too, GW plan
    decision #4). A no-op when the world has no population, no capacity, or no
    `groundwar` config, or when garrison is already at the cap; returns the same
    object unchanged in that case (the cron "skip the rewrite" convention
    `produce()`/`advance_build` already use). Armor recovers toward the same
    population-fraction cap at `militia_armor_recovery_frac`, but only when
    `planet.citadel_level >= armor_recovery_min_citadel_level` — an unfortified
    world fields no vehicles and regrows none, matching `seed_garrison`'s own
    armor-seeding gate (decision #5).
    """
    if config.groundwar is None or not planet.population:
        return planet
    capacity = colonist_capacity(planet, config)
    if capacity <= 0:
        return planet
    cfg = config.groundwar.garrison_economy
    cap = round(capacity * cfg.cap_frac)
    infantry = _recover_toward_cap(planet.garrison_infantry, cap, cfg.militia_recovery_frac)
    armor = planet.garrison_armor
    if planet.citadel_level >= cfg.armor_recovery_min_citadel_level:
        armor = _recover_toward_cap(armor, cap, cfg.militia_armor_recovery_frac)
    if infantry == planet.garrison_infantry and armor == planet.garrison_armor:
        return planet
    return replace(planet, garrison_infantry=infantry, garrison_armor=armor)
