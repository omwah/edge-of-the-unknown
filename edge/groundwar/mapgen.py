"""Seeded battlefield generation for the ground-war POC.

Reuses the planet terrain art (`edge.art.terrain` biome/feature registries over
OpenSimplex noise) but keeps *two* grids: the styled art backdrop and a parallel
grid of feature *names* that the rules layer prices for movement, cover, and LOS.
Cities are stamped over the terrain: walled districts with gates, corner turrets,
an AA battery, a sensor tower, streets, and building blocks (military and
civilian); the capital is the citadel city, whose citadel level (difficulty-set,
mirroring `edge.core.citadels` levels) adds mid-wall turrets, the citadel gun,
and hardened walls. Deterministic from `(seed, planet_type, difficulty)`.
"""

from __future__ import annotations

from random import Random

from edge.art.terrain import style_grid
from edge.core.groundwar.terrain import LANDABLE_BIOMES, generate_feature_grid
from edge.groundwar.config import GroundwarConfig
from edge.groundwar.model import Battle, City, Structure, StructureKind

# Planet types offered by the setup screen (populated worlds only — the game's
# premise). Sourced from the core terrain seam so gameplay and setup agree.
PLANET_TYPES = LANDABLE_BIOMES

CITY_NAMES = (
    "Klendathu Down", "Port Joel", "Zegema Beach", "New Cyrene", "Uxmal",
    "Fort Bannon", "Carr's Landing", "Hesperus", "Tango Urilla", "Sheol",
)

STREET_FEATURE = "dust"  # what city ground plays as (move 1, no cover)


def _terrain_grids(
    rng: Random, planet_type: str, width: int, height: int,
) -> tuple[list[list[str]], list[list[tuple[str, str, str]]]]:
    """The gameplay feature grid (pure core seam) and the styled art grid (art layer).

    Both derive from the same `noise_seed`, so the styled backdrop is aligned
    cell-for-cell with the feature names the rules price for movement/cover/LOS —
    the core half draws no game RNG, `rng` drives only glyph selection.
    """
    noise_seed = rng.randint(0, 2**31 - 1)
    feature = generate_feature_grid(noise_seed, planet_type, width, height)
    art = style_grid(rng, noise_seed, planet_type, width, height)
    return feature, art


def _footprint_passable_frac(
    battle: Battle, x0: int, y0: int, w: int, h: int,
) -> float:
    total = passable = 0
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            total += 1
            tc = battle.config.terrain.get(battle.feature[y][x])
            if tc is not None and tc.move_cost > 0:
                passable += 1
    return passable / max(1, total)


def _add_structure(battle: Battle, kind: StructureKind, x: int, y: int,
                   city_id: int, hp: int) -> Structure:
    s = Structure(id=battle.next_id(), kind=kind, x=x, y=y, city_id=city_id,
                  hp=hp, hp_max=hp)
    battle.structures[s.id] = s
    battle.struct_at[(x, y)] = s.id
    return s


def _stamp_city(battle: Battle, rng: Random, name: str, x0: int, y0: int,
                w: int, h: int, *, is_citadel: bool, citadel_level: int) -> City:
    cfg = battle.config
    d = cfg.defenses
    city = City(id=battle.next_id(), name=name, cx=x0 + w // 2, cy=y0 + h // 2,
                x0=x0, y0=y0, x1=x0 + w - 1, y1=y0 + h - 1,
                is_citadel=is_citadel, citadel_level=citadel_level)
    battle.cities.append(city)

    # Pave the footprint: city ground plays as street regardless of what's under it.
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            battle.feature[y][x] = STREET_FEATURE
            battle.art[y][x] = (" ", "grey35", "grey15")

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
                _add_structure(battle, "turret", *pos, city.id, d.turret.hp)
            elif pos in mids and citadel_level >= 1:
                _add_structure(battle, "turret", *pos, city.id, d.turret.hp)
            else:
                _add_structure(battle, "wall", *pos, city.id, wall_hp)
    for y in range(y0 + 1, y0 + h - 1):
        for x in (x0, x0 + w - 1):
            pos = (x, y)
            if pos in gates:
                _add_structure(battle, "gate", *pos, city.id, d.gate.hp)
            else:
                _add_structure(battle, "wall", *pos, city.id, wall_hp)

    # Interior emplacements: AA battery, sensor tower (an extra AA on a level-3 citadel).
    _add_structure(battle, "aa", city.cx - w // 4, city.cy - 1, city.id, d.aa.hp)
    _add_structure(battle, "sensor", city.cx + w // 4, city.cy + 1, city.id, d.sensor.hp)
    if citadel_level >= 3:
        _add_structure(battle, "aa", city.cx + w // 4, city.cy - 1, city.id, d.aa.hp)
    if is_citadel and citadel_level >= 2:
        _add_structure(battle, "citadel_gun", city.cx, city.cy, city.id, d.citadel_gun.hp)

    # Building blocks on a street grid: rows every other line, 2-cell blocks with gaps.
    for y in range(y0 + 2, y0 + h - 2, 2):
        for bx in range(x0 + 3, x0 + w - 4, 4):
            for x in (bx, bx + 1):
                if (x, y) in battle.struct_at or abs(x - city.cx) + abs(y - city.cy) <= 1:
                    continue
                military = rng.random() < 0.3
                kind: StructureKind = "building_military" if military else "building_civilian"
                hp = d.building_military_hp if military else d.building_civilian_hp
                _add_structure(battle, kind, x, y, city.id, hp)
    return city


def generate_battle(
    config: GroundwarConfig, *, seed: int, planet_type: str, difficulty_key: str,
) -> Battle:
    """A fully-populated battlefield (terrain + cities); troopers drop later."""
    diff = config.difficulties[difficulty_key]
    rng = Random(f"{seed}|groundwar|{planet_type}|{difficulty_key}")
    battle = Battle(
        config=config, rng=rng, seed=seed, planet_type=planet_type,
        difficulty_key=difficulty_key,
        surrender_threshold=diff.surrender_threshold, garrison_mult=diff.garrison_mult,
        feature=[], art=[], resolve=float(config.resolve.start),
    )
    battle.feature, battle.art = _terrain_grids(rng, planet_type, config.width, config.height)

    # Cities spread across the map's right two-thirds (the drop approach is from anywhere,
    # but keeping the capital deep makes range and the clock matter).
    names = list(CITY_NAMES)
    rng.shuffle(names)
    n = diff.cities
    for i in range(n):
        is_citadel = i == n - 1
        w, h = (30, 14) if is_citadel else (24, 11)
        lane_x0 = config.width * (i + 1) // (n + 1)
        lane_x1 = config.width * (i + 2) // (n + 1) - w - 2
        best: tuple[float, int, int] | None = None
        for _ in range(24):
            x0 = rng.randint(max(2, lane_x0), max(max(2, lane_x0), lane_x1))
            y0 = rng.randint(3, config.height - h - 3)
            frac = _footprint_passable_frac(battle, x0, y0, w, h)
            if best is None or frac > best[0]:
                best = (frac, x0, y0)
            if frac >= 0.7:
                break
        assert best is not None
        _stamp_city(battle, rng, names[i % len(names)], best[1], best[2], w, h,
                    is_citadel=is_citadel,
                    citadel_level=diff.citadel_level if is_citadel else 0)
    return battle
