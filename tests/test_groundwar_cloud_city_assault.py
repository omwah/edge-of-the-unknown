"""GW-WP16 — Cloud City station-interior assault-map generation.

Covers `edge.core.groundwar.assault.generate_cloud_city_assault_map`: determinism,
the whole-station single-`AssaultCity` model (interview decision — surrender is
whole-station, not per-district), the permanent-bulkhead/destructible-`security_door`
split (interview decision — no `wall`-kind structure is ever emitted), `blocked`
coverage, and `spawn_anchors`. `derive_difficulty`'s jovian branch and the
`assault_map_for_state` dispatch are covered here too; `access.py`'s gate is covered
in `tests/test_groundwar_access.py`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.groundwar.assault import (
    AssaultOperation,
    assault_map_for_state,
    derive_difficulty,
    generate_cloud_city_assault_map,
)
from edge.core.models import AlienSpecies, Planet, UNOWNED

CFG = load_default_config()
assert CFG.groundwar is not None
MAX_SIZE = CFG.planets.cloud_city_max_size

_SIZES = range(1, MAX_SIZE + 1)
_LEVELS = range(4)


def _planet(**kw: object) -> Planet:
    base: dict[str, object] = dict(
        id=1, sector_id=1, name="Skyhold", planet_type="jovian",
        owner=UNOWNED, cloud_city_size=2, population={"vesk": 5_000},
    )
    base.update(kw)
    return Planet(**base)  # type: ignore[arg-type]


def _species(disp: float) -> AlienSpecies:
    return AlienSpecies(
        id=7, roster_id="vesk", name="Vesk", archetype_id="a", sector_id=1,
        home_band="Frontier", tech_level=1, base_disposition=disp,
        disposition_center=disp, disposition_variance=0.0)


# --- generation ---------------------------------------------------------------


def test_deterministic() -> None:
    a = generate_cloud_city_assault_map(CFG, seed=42, cloud_city_size=3, citadel_level=2)
    b = generate_cloud_city_assault_map(CFG, seed=42, cloud_city_size=3, citadel_level=2)
    assert a == b


def test_varies_with_seed() -> None:
    a = generate_cloud_city_assault_map(CFG, seed=1, cloud_city_size=3, citadel_level=2)
    b = generate_cloud_city_assault_map(CFG, seed=2, cloud_city_size=3, citadel_level=2)
    assert a.feature != b.feature or a.structures != b.structures


@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("citadel_level", _LEVELS)
def test_generates_across_every_size_and_citadel_level(size: int, citadel_level: int) -> None:
    for seed in range(8):
        amap = generate_cloud_city_assault_map(
            CFG, seed=seed, cloud_city_size=size, citadel_level=citadel_level)
        assert amap.width > 0 and amap.height > 0
        assert 0 <= amap.landing_x < amap.width
        assert 0 <= amap.landing_y < amap.height


def test_whole_station_is_one_shared_city() -> None:
    """Interview decision: surrender is whole-station, not per-district — every
    stamped structure across every physical room reports to the same `city_id`,
    which is what makes `_check_cowed`/`broadcast_terms` whole-station with no
    changes to their own (city_id-keyed) logic."""
    amap = generate_cloud_city_assault_map(CFG, seed=7, cloud_city_size=4, citadel_level=3)
    assert len(amap.cities) == 1
    city = amap.cities[0]
    assert city.is_citadel
    assert amap.structures  # a size-4/level-3 station has *something* stamped
    assert all(s.city_id == city.id for s in amap.structures)


def test_no_wall_structures_are_ever_emitted() -> None:
    """Interview decision: bulkhead is permanently indestructible; only
    `security_door` is destructible. `city_cowed`'s own definition never
    references walls/gates, so this has no effect on the win condition."""
    for seed in range(20):
        amap = generate_cloud_city_assault_map(CFG, seed=seed, cloud_city_size=4, citadel_level=3)
        assert all(s.kind != "wall" for s in amap.structures)


def test_gates_match_security_door_cells_exactly() -> None:
    for seed in range(20):
        amap = generate_cloud_city_assault_map(CFG, seed=seed, cloud_city_size=3, citadel_level=1)
        gate_cells = {(s.x, s.y) for s in amap.structures if s.kind == "gate"}
        door_cells = {
            (x, y) for y, row in enumerate(amap.feature)
            for x, feature in enumerate(row) if feature == "security_door"
        }
        assert gate_cells == door_cells


def test_blocked_covers_bulkhead_and_non_gate_structures_only() -> None:
    amap = generate_cloud_city_assault_map(CFG, seed=3, cloud_city_size=4, citadel_level=2)
    bulkhead_cells = {
        (x, y) for y, row in enumerate(amap.feature)
        for x, feature in enumerate(row) if feature == "bulkhead"
    }
    assert bulkhead_cells <= amap.blocked
    for s in amap.structures:
        if s.kind == "gate":
            assert (s.x, s.y) not in amap.blocked
        else:
            assert (s.x, s.y) in amap.blocked


def test_citadel_gun_only_on_command_core_and_only_at_level_2_plus() -> None:
    for citadel_level in _LEVELS:
        amap = generate_cloud_city_assault_map(
            CFG, seed=11, cloud_city_size=4, citadel_level=citadel_level)
        guns = [s for s in amap.structures if s.kind == "citadel_gun"]
        if citadel_level >= 2:
            assert len(guns) == 1
        else:
            assert not guns


def test_civilian_and_military_buildings_are_stamped() -> None:
    """WP15's interior vocabulary had no buildings; without these, civilian-harm
    consequences (`settlement.civilian_loss_per_structure`) would never have a
    target on a station."""
    amap = generate_cloud_city_assault_map(CFG, seed=7, cloud_city_size=4, citadel_level=1)
    kinds = Counter(s.kind for s in amap.structures)
    assert kinds["building_civilian"] > 0
    assert kinds["building_military"] > 0


def test_spawn_anchors_present_and_in_bounds() -> None:
    """`_place_units` only ever searches a ring *around* each anchor (never the
    anchor cell itself), so an anchor sharing a cell with a stamped structure is
    harmless — this only checks presence/bounds; `_place_units` actually placing
    units from these anchors is covered end-to-end in
    `test_groundwar_cloud_city_assault_tactics.py`."""
    for seed in range(10):
        amap = generate_cloud_city_assault_map(CFG, seed=seed, cloud_city_size=3, citadel_level=1)
        assert amap.spawn_anchors
        assert all(0 <= x < amap.width and 0 <= y < amap.height for x, y in amap.spawn_anchors)


def test_terrestrial_map_has_no_spawn_anchors() -> None:
    """Regression guard: `spawn_anchors` is Cloud-City-only — a terrestrial map
    still derives sortie origins from gates/walls, unchanged."""
    from edge.core.groundwar.assault import generate_assault_map

    amap = generate_assault_map(CFG, seed=1, planet_type="terrestrial_warm", cities=2, citadel_level=1)
    assert amap.spawn_anchors == ()


# --- derive_difficulty jovian branch + dispatch --------------------------------


def test_derive_difficulty_uses_cloud_city_size_directly() -> None:
    planet = _planet(cloud_city_size=3)
    species = _species(0.1)
    difficulty = derive_difficulty(planet, CFG, distance_band="Frontier", species=species)
    assert difficulty.cities == 3


def test_derive_difficulty_ignores_population_formula_for_jovian() -> None:
    """A huge cloud_city_berths-driven capacity must not inflate `cities` past
    the raw `cloud_city_size` for a jovian world — the population-derived
    formula is terrestrial-only."""
    planet = _planet(cloud_city_size=1)
    species = _species(0.1)  # hostile, would multiply score if it mattered
    difficulty = derive_difficulty(planet, CFG, distance_band="Frontier", species=species)
    assert difficulty.cities == 1


def test_assault_map_for_state_dispatches_on_planet_type() -> None:
    op = AssaultOperation(
        operation_id=1, planet_id=1, sector_id=1, planet_type="jovian",
        seed=42, started_day=1, resolve=100, retrieval_turn=20,
        cities=2, citadel_level=1, surrender_threshold=30,
    )
    amap = assault_map_for_state(op, CFG)
    assert len(amap.cities) == 1
    assert amap.cities[0].is_citadel

    terrestrial_op = replace(op, planet_type="terrestrial_warm")
    tmap = assault_map_for_state(terrestrial_op, CFG)
    assert len(tmap.cities) == terrestrial_op.cities
