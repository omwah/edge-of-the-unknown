"""GW-WP09 — persistent ground-defense garrison economy and assault-map generation.

Covers `edge.core.groundwar.assault`'s pure functions: deterministic battlefield
generation (terrain, cities, structures, the reachability invariant a POC never
needed), live-state difficulty derivation (population/citadel/hostility/band/
"had a gun" scaling, GW plan decision #7), big-bang garrison seeding, and the two
automatic-recovery rails (militia infantry, gated armor).
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from edge.config import load_default_config
from edge.core.groundwar.assault import (
    apply_militia_recovery,
    derive_difficulty,
    generate_assault_map,
    seed_garrison,
)
from edge.core.models import AlienSpecies, Planet, UNOWNED

CFG = load_default_config()
AMITY = CFG.aliens.amity_threshold  # type: ignore[union-attr]
GUN_MIN = CFG.citadels.gun_min_level  # type: ignore[union-attr]
GECFG = CFG.groundwar.garrison_economy  # type: ignore[union-attr]
ADCFG = CFG.groundwar.assault_difficulty  # type: ignore[union-attr]


def _planet(**kw: object) -> Planet:
    base: dict[str, object] = dict(
        id=1, sector_id=1, name="World", planet_type="terrestrial_warm",
        owner=UNOWNED, habitability_cap=100_000, population={"vesk": 50_000},
    )
    base.update(kw)
    return Planet(**base)  # type: ignore[arg-type]


def _species(disp: float, *, alliance: int | None = None) -> AlienSpecies:
    return AlienSpecies(
        id=7, roster_id="vesk", name="Vesk", archetype_id="a", sector_id=1,
        home_band="Frontier", tech_level=1, base_disposition=disp,
        disposition_center=disp, disposition_variance=0.0, alliance_id=alliance)


# --- battlefield generation (G5, decision #3) --------------------------------


def test_generate_assault_map_is_deterministic() -> None:
    a = generate_assault_map(CFG, seed=42, planet_type="terrestrial_warm", cities=3, citadel_level=2)
    b = generate_assault_map(CFG, seed=42, planet_type="terrestrial_warm", cities=3, citadel_level=2)
    assert a == b


def test_generate_assault_map_varies_with_seed() -> None:
    a = generate_assault_map(CFG, seed=42, planet_type="terrestrial_warm", cities=3, citadel_level=2)
    b = generate_assault_map(CFG, seed=43, planet_type="terrestrial_warm", cities=3, citadel_level=2)
    assert a != b


@pytest.mark.parametrize("cities", [1, 2, 3, 4])
def test_city_count_matches_cities_arg(cities: int) -> None:
    m = generate_assault_map(CFG, seed=1, planet_type="terrestrial_warm", cities=cities, citadel_level=1)
    assert len(m.cities) == cities


def _flood_from(m, start: tuple[int, int]) -> set[tuple[int, int]]:
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < m.width and 0 <= ny < m.height) or (nx, ny) in seen:
                continue
            if (nx, ny) in m.blocked:
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return seen


def test_every_city_reachable_from_landing() -> None:
    m = generate_assault_map(CFG, seed=7, planet_type="terrestrial_warm", cities=4, citadel_level=3)
    reachable = _flood_from(m, (m.landing_x, m.landing_y))
    for city in m.cities:
        # Every paved cell of a city's footprint not itself a wall/turret must be
        # reachable — the largest-passable-component invariant (decision #3).
        interior = [(x, y) for x in range(city.x0 + 1, city.x1) for y in range(city.y0 + 1, city.y1)
                   if (x, y) not in m.blocked]
        assert any(cell in reachable for cell in interior), f"{city.name} unreachable from landing"


@pytest.mark.parametrize("level,expect_gun", [(0, False), (1, False), (2, True), (3, True)])
def test_citadel_gun_only_at_level_2_plus_and_only_on_the_capital(level: int, expect_gun: bool) -> None:
    m = generate_assault_map(CFG, seed=9, planet_type="terrestrial_warm", cities=2, citadel_level=level)
    guns = [s for s in m.structures if s.kind == "citadel_gun"]
    if expect_gun:
        assert len(guns) == 1
        capital = m.cities[-1]
        assert guns[0].city_id == capital.id
    else:
        assert guns == []


# --- difficulty derivation (D11, decisions #6/#7) ----------------------------


def test_derive_difficulty_scales_with_population() -> None:
    small = derive_difficulty(_planet(habitability_cap=1_000), CFG, distance_band="Hub", species=None)
    big = derive_difficulty(_planet(habitability_cap=1_000_000), CFG, distance_band="Hub", species=None)
    assert big.cities >= small.cities


def test_derive_difficulty_scales_with_citadel_level_only_via_surrender_threshold() -> None:
    """A fortified world holds out to a **lower** Resolve, so a higher citadel level must
    *lower* the threshold (surrender fires at `resolve <= threshold`).

    This asserted the opposite direction until GW-WP24. The old sign made every citadel
    level capitulate at a higher Resolve — sooner — while its extra emplacements were
    themselves Resolve to strip, so fortifying a world made it easier twice over:
    measured at citadel 2 it surrendered in 3-6 turns against 5-12 at citadel 0.
    """
    low = derive_difficulty(_planet(citadel_level=0), CFG, distance_band="Hub", species=None)
    high = derive_difficulty(_planet(citadel_level=3), CFG, distance_band="Hub", species=None)
    assert high.surrender_threshold < low.surrender_threshold
    assert high.cities == low.cities  # citadel level alone never sizes the city count


def test_derive_difficulty_scales_with_hostility() -> None:
    friendly = derive_difficulty(_planet(), CFG, distance_band="Hub", species=_species(AMITY + 0.2))
    hostile = derive_difficulty(_planet(), CFG, distance_band="Hub", species=_species(AMITY - 0.2))
    assert hostile.cities >= friendly.cities


def test_derive_difficulty_scales_with_band() -> None:
    cfg = CFG.model_copy(update={"groundwar": CFG.groundwar.model_copy(
        update={"assault_difficulty": ADCFG.model_copy(update={"band_mult": {"Deep Space": 3.0}})})})
    hub = derive_difficulty(_planet(), cfg, distance_band="Hub", species=None)
    deep = derive_difficulty(_planet(), cfg, distance_band="Deep Space", species=None)
    assert deep.cities >= hub.cities


def test_derive_difficulty_had_gun_scores_higher_than_never_had_one() -> None:
    never_had = derive_difficulty(_planet(citadel_level=GUN_MIN - 1), CFG, distance_band="Hub", species=None)
    had = derive_difficulty(_planet(citadel_level=GUN_MIN), CFG, distance_band="Hub", species=None)
    # Isolate the had-gun multiplier's effect on the underlying capacity score by
    # forcing a population large enough that a small multiplier still tips a city.
    big_never = derive_difficulty(
        _planet(citadel_level=GUN_MIN - 1, habitability_cap=15_000), CFG, distance_band="Hub", species=None)
    big_had = derive_difficulty(
        _planet(citadel_level=GUN_MIN, habitability_cap=15_000), CFG, distance_band="Hub", species=None)
    assert big_had.cities >= big_never.cities
    # Both terms now push the same way: `had_gun_mult` divides the threshold down, and
    # since GW-WP24 the citadel term subtracts rather than adds. A world that built and
    # lost a gun holds out to a lower Resolve than one that never invested.
    assert had.surrender_threshold < never_had.surrender_threshold


@given(fighters=st.integers(min_value=0, max_value=10_000))
def test_derive_difficulty_ignores_fighters(fighters: int) -> None:
    """Fighters are a space asset (D7) — assault difficulty never reads them."""
    baseline = derive_difficulty(_planet(), CFG, distance_band="Hub", species=None)
    varied = derive_difficulty(_planet(fighters=fighters), CFG, distance_band="Hub", species=None)
    assert baseline == varied


# --- garrison seeding (big-bang only, D11) -----------------------------------


def test_seed_garrison_scales_with_hostility_alliance_band_citadel() -> None:
    base = seed_garrison(CFG, capacity=100_000, citadel_level=0, distance_band="Hub",
                         hostile=False, alliance_owned=False, rng=random.Random(1))
    hostile = seed_garrison(CFG, capacity=100_000, citadel_level=0, distance_band="Hub",
                            hostile=True, alliance_owned=False, rng=random.Random(1))
    alliance = seed_garrison(CFG, capacity=100_000, citadel_level=0, distance_band="Hub",
                             hostile=False, alliance_owned=True, rng=random.Random(1))
    citadel = seed_garrison(CFG, capacity=100_000, citadel_level=3, distance_band="Hub",
                            hostile=False, alliance_owned=False, rng=random.Random(1))
    assert hostile[0] > base[0]
    assert alliance[0] > base[0]
    assert citadel[0] > base[0]


def test_seed_garrison_armor_only_above_min_citadel_level() -> None:
    below = seed_garrison(CFG, capacity=100_000, citadel_level=GECFG.seed_armor_min_citadel_level - 1,
                          distance_band="Hub", hostile=False, alliance_owned=False, rng=random.Random(2))
    at = seed_garrison(CFG, capacity=100_000, citadel_level=GECFG.seed_armor_min_citadel_level,
                       distance_band="Hub", hostile=False, alliance_owned=False, rng=random.Random(2))
    assert below[1] == 0
    assert at[1] > 0


# --- automatic militia recovery (D11, decisions #4/#5) -----------------------


def test_apply_militia_recovery_converges_to_the_cap_and_never_overshoots() -> None:
    p = _planet(citadel_level=GECFG.armor_recovery_min_citadel_level, garrison_infantry=0,
               garrison_armor=0)
    cap = round(100_000 * GECFG.cap_frac)
    for _ in range(2000):
        p = apply_militia_recovery(p, CFG)
        assert p.garrison_infantry <= cap
        assert p.garrison_armor <= cap
    assert p.garrison_infantry == cap
    assert p.garrison_armor == cap


def test_apply_militia_recovery_armor_stays_zero_below_the_citadel_gate() -> None:
    p = _planet(citadel_level=GECFG.armor_recovery_min_citadel_level - 1, garrison_armor=0)
    for _ in range(500):
        p = apply_militia_recovery(p, CFG)
    assert p.garrison_armor == 0


def test_apply_militia_recovery_runs_on_an_unowned_world() -> None:
    """Decision #4: militia recovery is ownership-independent — a native/unaligned
    world regrows its own defenders too, unlike `produce()`'s owner-only gate."""
    p = _planet(owner=UNOWNED, garrison_infantry=0)
    grown = apply_militia_recovery(p, CFG)
    assert grown.garrison_infantry > 0


def test_apply_militia_recovery_noop_on_an_empty_or_unconfigured_world() -> None:
    empty = _planet(population={}, habitability_cap=0)
    assert apply_militia_recovery(empty, CFG) is empty
    populated = _planet()
    unconfigured = CFG.model_copy(update={"groundwar": None})
    assert apply_militia_recovery(populated, unconfigured) is populated
