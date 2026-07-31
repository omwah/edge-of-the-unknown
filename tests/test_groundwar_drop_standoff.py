"""GW-WP23 — the assault drop lands on a ring outside AA range, and the map cache is sound.

Through GW-WP22 the landing point came from `world.landing_in_component`, which sets down
"near the map's left-middle" with no reference to where the cities are. That made the
`defenses.aa` config comment's own stated intent — "land clear of the umbrella and march
in" — unreachable: a watched run spent ten of twenty-four turns walking, against cities
95/130/203 cells away. These tests pin the properties that fix is made of, on generated
maps rather than fixtures, because the failure was a property of generation.
"""

from __future__ import annotations

import math

import pytest

from edge.config import load_default_config
from edge.core.groundwar import assault as ga
from edge.core.groundwar import interior as gw_interior
from edge.core.groundwar.models import AssaultOperation

CFG = load_default_config()
GW = CFG.groundwar
assert GW is not None

_SEEDS = (1, 2, 3, 4, 5, 6, 7, 11, 23)
_TYPES = ("terrestrial_warm", "terrestrial_cold", "terrestrial_hot", "barren")


def _map(seed: int, planet_type: str = "terrestrial_warm", *, cities: int = 3,
         citadel_level: int = 2) -> ga.AssaultMap:
    return ga.generate_assault_map(
        CFG, seed=seed, planet_type=planet_type, cities=cities, citadel_level=citadel_level)


def _capital(amap: ga.AssaultMap) -> ga.AssaultCity:
    return next((c for c in amap.cities if c.is_citadel), amap.cities[0])


def _radius() -> int:
    """Cells of open ground the drop must leave in front of the capital's footprint.

    GW-WP24 re-anchored the ring from the capital's *centre* to its footprint edge, so
    this is now `drop_standoff` alone rather than `aa.range + drop_standoff`. The
    centre-anchored form coupled the approach length to city size — on a ~30x14
    footprint a 20-cell radius left ~6 cells of open ground off a face and none off a
    corner, so tuning the standoff moved the drop without lengthening the walk in.
    """
    assert GW is not None
    return GW.defenses.drop_standoff


def _clearance(amap: ga.AssaultMap, x: int, y: int) -> float:
    cap = _capital(amap)
    return max(abs(x - cap.cx) - (cap.x1 - cap.x0) / 2,
               abs(y - cap.cy) - (cap.y1 - cap.y0) / 2)


@pytest.mark.parametrize("planet_type", _TYPES)
@pytest.mark.parametrize("seed", _SEEDS)
def test_drop_is_a_short_bounded_approach_from_the_capital(
        seed: int, planet_type: str) -> None:
    """The distance is to the *capital*, not to whichever city sorted first and not to
    the map's west edge. Bounded rather than exact: a capital pinned against a map edge
    can leave no cell at the ring radius in its own component, and the honest answer
    there is the nearest safe ground outside the umbrella, not a spurious failure. The
    bound is what matters — the behaviour this replaces produced 95, 130 and 203."""
    amap = _map(seed, planet_type)
    clear = _clearance(amap, amap.landing_x, amap.landing_y)
    assert clear <= _radius() + 10, (
        f"seed {seed}/{planet_type}: landed {clear:.1f} cells off the capital's footprint")


def test_most_seeds_land_exactly_on_the_ring() -> None:
    """The bounded per-seed check above would still pass if the ring logic quietly
    stopped working, so pin the aggregate: the edge-pinned capitals are the exception,
    not the rule."""
    on_ring = 0
    total = 0
    for planet_type in _TYPES:
        for seed in _SEEDS:
            amap = _map(seed, planet_type)
            clear = _clearance(amap, amap.landing_x, amap.landing_y)
            total += 1
            on_ring += abs(clear - _radius()) <= 1.5
    assert on_ring >= total * 0.8, f"only {on_ring}/{total} landed on the ring"


@pytest.mark.parametrize("planet_type", _TYPES)
@pytest.mark.parametrize("seed", _SEEDS)
def test_drop_is_outside_every_aa_umbrella(seed: int, planet_type: str) -> None:
    """`tactical_projection` paints the pre-drop hazard from every city centre at
    `aa.range`; landing inside one is dropping into the fire the standoff exists to avoid
    — including a *neighbouring* town's, which is why this checks all cities.

    Conditional on safe ground existing, because sometimes it does not: on
    `terrestrial_hot` seeds 2, 4 and 11 the capital sits within ~11 cells of the map's top
    edge and every walkable cell that can reach it lies under some umbrella. There is then
    no such thing as a clean drop on that world, and the generator must not pretend
    otherwise — but it must still take the safe cell whenever one exists, which is the
    property that would silently rot."""
    assert GW is not None
    amap = _map(seed, planet_type)
    feature = [list(row) for row in amap.feature]
    labels, _sizes = ga._passable_components(
        feature, set(amap.blocked), CFG, amap.width, amap.height)
    comp = labels[amap.landing_y][amap.landing_x]

    def safe(x: int, y: int) -> bool:
        return all(math.hypot(c.cx - x, c.cy - y) > GW.defenses.aa.range  # type: ignore[union-attr]
                   for c in amap.cities)

    any_safe = any(
        labels[y][x] == comp and safe(x, y) and not any(c.inside(x, y) for c in amap.cities)
        for y in range(amap.height) for x in range(amap.width))
    if any_safe:
        assert safe(amap.landing_x, amap.landing_y), (
            f"seed {seed}/{planet_type}: landed under AA with safe ground available")


@pytest.mark.parametrize("planet_type", _TYPES)
@pytest.mark.parametrize("seed", _SEEDS)
def test_drop_is_never_inside_a_city_footprint(seed: int, planet_type: str) -> None:
    """Open ground inside the walls is passable and can be its own component, so without
    an explicit exclusion a capital wider than the ring radius would put the drop boat
    down past every wall — skipping the assault rather than beginning it."""
    amap = _map(seed, planet_type)
    for city in amap.cities:
        assert not city.inside(amap.landing_x, amap.landing_y)


@pytest.mark.parametrize("planet_type", _TYPES)
@pytest.mark.parametrize("seed", _SEEDS)
def test_capital_is_reachable_on_foot_from_the_drop(seed: int, planet_type: str) -> None:
    """The bug the standoff work uncovered: confining the drop to the map's *largest*
    passable component put the platoon on a landmass with no foot route to the objective
    at all (`terrestrial_warm` seed 2 — a 2173-cell component 108 cells from a capital
    sitting on a 1149-cell one). Jump charges cover ~32 cells, so that assault could not
    be completed by any play. The drop must share a component with the capital's edge."""
    amap = _map(seed, planet_type)
    cap = _capital(amap)
    feature = [list(row) for row in amap.feature]
    labels, _sizes = ga._passable_components(
        feature, set(amap.blocked), CFG, amap.width, amap.height)
    landing_comp = labels[amap.landing_y][amap.landing_x]
    assert landing_comp >= 0
    touching = any(
        labels[y][x] == landing_comp
        for y in range(max(0, cap.y0 - 2), min(amap.height, cap.y1 + 3))
        for x in range(max(0, cap.x0 - 2), min(amap.width, cap.x1 + 3)))
    assert touching, f"seed {seed}/{planet_type}: capital unreachable from the drop"


def test_landing_is_deterministic_for_one_seed() -> None:
    """Determinism over retry (decision #3) — the landing is derived, never re-rolled."""
    for seed in _SEEDS:
        first, second = _map(seed), _map(seed)
        assert (first.landing_x, first.landing_y) == (second.landing_x, second.landing_y)


def test_standoff_knob_moves_the_ring() -> None:
    """`drop_standoff` is a knob so the balance can be slid while watching a run (D17);
    a knob that does not move the drop would be a lie in the config file."""
    assert GW is not None
    wider = CFG.model_copy(update={"groundwar": GW.model_copy(update={
        "defenses": GW.defenses.model_copy(update={"drop_standoff": 24})})})
    base = _map(3)
    far = ga.generate_assault_map(
        wider, seed=3, planet_type="terrestrial_warm", cities=3, citadel_level=2)
    assert (_clearance(far, far.landing_x, far.landing_y)
            > _clearance(base, base.landing_x, base.landing_y) + 5)


# --- Cloud City (D19) --------------------------------------------------------


@pytest.mark.parametrize("size", (1, 2, 3))
def test_station_landing_uses_every_deployment_zone(size: int) -> None:
    """GW-WP16 shipped the Cloud City assault using `deployment_zones[0]` unconditionally.
    All zones are candidates now, ranked by the same standoff rule — which inside a
    station almost always degenerates to "farthest from the command core", the stated D19
    fallback."""
    assert GW is not None
    amap = ga.generate_cloud_city_assault_map(
        CFG, seed=5, cloud_city_size=size, citadel_level=2)
    layout = gw_interior.generate_interior(5, size, GW.cloud_city)
    core = _capital(amap)
    landing = (amap.landing_x, amap.landing_y)
    assert landing in layout.deployment_zones
    # The chosen zone must be the best of *all* of them under the standoff rule, not
    # index 0 — which is what GW-WP16 shipped and D19 closes.
    assert landing == ga.station_landing(layout.deployment_zones, core, CFG)
    if len(layout.deployment_zones) > 1:
        safe = [z for z in layout.deployment_zones
                if math.hypot(z[0] - core.cx, z[1] - core.cy) > GW.defenses.aa.range]
        if safe:
            assert landing in safe  # never pick an exposed zone while a safe one exists


# --- the runtime cache (D24) -------------------------------------------------


def _op(seed: int, *, citadel_level: int = 2) -> AssaultOperation:
    return AssaultOperation(
        operation_id=1, planet_id=1, sector_id=1, planet_type="terrestrial_warm",
        seed=seed, started_day=1, resolve=100, retrieval_turn=24, world_seed=seed,
        cities=3, citadel_level=citadel_level, surrender_threshold=40)


def test_map_cache_returns_an_identical_map() -> None:
    """A cache hit must be indistinguishable from a recompute, or determinism is gone."""
    ga.clear_assault_map_cache()
    first = ga.assault_map_for_state(_op(3), CFG)
    cached = ga.assault_map_for_state(_op(3), CFG)
    assert cached is first  # the point of the cache
    ga.clear_assault_map_cache()
    rebuilt = ga.assault_map_for_state(_op(3), CFG)
    assert rebuilt is not first
    assert rebuilt == first  # ... and equal to what a cold generation produces


def test_map_cache_keys_on_the_inputs_that_change_the_map() -> None:
    """Citadel level and world seed both reshape the battlefield; neither may collide."""
    ga.clear_assault_map_cache()
    a = ga.assault_map_for_state(_op(3, citadel_level=0), CFG)
    b = ga.assault_map_for_state(_op(3, citadel_level=2), CFG)
    c = ga.assault_map_for_state(_op(4, citadel_level=2), CFG)
    assert a is not b and b is not c
    assert len(a.structures) != len(b.structures)


def test_map_cache_does_not_leak_across_configs() -> None:
    """Configs are rebuilt constantly in tests and differ without any version field
    changing, so the cache key carries `id(config)` *and* holds the config alive — an id
    recycled onto a different config would otherwise serve a map built from the old one."""
    assert GW is not None
    ga.clear_assault_map_cache()
    base = ga.assault_map_for_state(_op(3), CFG)
    other = CFG.model_copy(update={"groundwar": GW.model_copy(update={
        "defenses": GW.defenses.model_copy(update={"drop_standoff": 9})})})
    shifted = ga.assault_map_for_state(_op(3), other)
    assert (shifted.landing_x, shifted.landing_y) != (base.landing_x, base.landing_y)
