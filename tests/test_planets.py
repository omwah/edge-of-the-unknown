"""WP3 — planetary production (DESIGN §4.2, §8) and the planet_growth cron."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.events import PlanetProduced
from edge.core.models import Game, Ownership, Planet, Sector, UniverseState
from edge.core.planets import garrison_training, is_colonizable, produce
from edge.engine.cron import planet_growth

CONFIG = load_default_config()


def _colony(ptype: str = "terrestrial_warm", colonists: int = 1000, owner: Ownership | None = None,
            stores: dict[Commodity, int] | None = None) -> Planet:
    profile = CONFIG.planets.types[ptype]
    return Planet(
        id=1, sector_id=1, name="P", planet_type=ptype,
        owner=owner if owner is not None else Ownership("player", 1),
        population={"terran": colonists} if colonists else {},
        habitability_cap=profile.habitability,
        yield_profile={Commodity(k): v for k, v in profile.yield_profile.items()},
        allocation={c: 1 / 3 for c in Commodity},
        stores=dict(stores or {Commodity.ORGANICS: 10_000}),
    )


def test_unowned_planet_does_not_produce() -> None:
    unowned = _colony(owner=Ownership("none"))
    assert produce(unowned, CONFIG) is unowned  # only owners collect (§8)


def test_owned_colony_accumulates_into_stores() -> None:
    before = _colony(stores={Commodity.ORGANICS: 10_000})
    after = produce(before, CONFIG)
    # Organics-rich warm world: equipment store rises (allocation × yield).
    assert after.stores[Commodity.EQUIPMENT] >= before.stores.get(Commodity.EQUIPMENT, 0)
    assert all(v >= 0 for v in after.stores.values())  # never negative


def test_growth_when_fed_capped_by_habitability() -> None:
    fed = _colony(colonists=CONFIG.planets.types["terrestrial_warm"].habitability,
                  stores={Commodity.ORGANICS: 10_000_000})
    after = produce(fed, CONFIG)
    assert after.colonists <= fed.habitability_cap  # never exceeds the cap


def test_starvation_when_unfed() -> None:
    starving = _colony(colonists=1000, stores={Commodity.ORGANICS: 0})
    after = produce(starving, CONFIG)
    assert after.colonists < 1000  # died back without food


def test_extraction_types_produce_without_colonists() -> None:
    jovian = _colony("jovian", colonists=0, stores={})
    after = produce(jovian, CONFIG)
    assert after.stores[Commodity.FUEL_ORE] == CONFIG.planets.jovian_scoop
    # A belt draws from its finite reserve (PT-52) — auto-collect can no more mint ore out of a
    # worked-out field than a player can. (Belts are always unowned, so this branch is
    # unreachable in a real game; it stays correct in case one ever becomes ownable.)
    belt = replace(_colony("asteroid_belt", colonists=0, stores={}),
                   ore_reserve=500, ore_reserve_max=500)
    mined = produce(belt, CONFIG)
    assert mined.stores[Commodity.EQUIPMENT] == CONFIG.planets.asteroid_mining
    assert mined.ore_reserve == 500 - CONFIG.planets.asteroid_mining
    spent = replace(belt, ore_reserve=0)
    assert produce(spent, CONFIG) is spent  # a spent field yields nothing
    barren = _colony("barren", colonists=0, stores={})
    assert produce(barren, CONFIG) is barren  # produces nothing


def _garrisoned(garrison_allocation: float = 0.5, equipment: int = 100_000,
                garrison_infantry: int = 0) -> Planet:
    p = _colony(stores={Commodity.ORGANICS: 10_000, Commodity.EQUIPMENT: equipment})
    return replace(p, garrison_allocation=garrison_allocation, garrison_infantry=garrison_infantry)


def test_produce_trains_garrison_from_allocation() -> None:
    before = _garrisoned()
    after = produce(before, CONFIG)
    assert after.garrison_infantry > before.garrison_infantry


def test_garrison_training_conserves_equipment_exactly() -> None:
    """The pure formula in isolation (`produce()`'s own equipment store also gains
    from ordinary trio production in the same tick, so the net *store* delta is not
    a clean multiple of what training alone spent — this checks the formula, not
    the combined tick)."""
    gained, spent = garrison_training(
        CONFIG, output=1000.0, allocation=0.5, equipment_available=10_000,
        current_infantry=0, cap=1_000_000)
    gcfg = CONFIG.groundwar.garrison_economy  # type: ignore[union-attr]
    assert spent == gained * gcfg.train_equipment_cost
    assert gained > 0


def test_garrison_training_respects_cap_headroom_even_with_ample_equipment() -> None:
    gained, spent = garrison_training(
        CONFIG, output=1_000_000.0, allocation=1.0, equipment_available=10_000_000,
        current_infantry=95, cap=100)
    assert gained == 5
    assert spent == 5 * CONFIG.groundwar.garrison_economy.train_equipment_cost  # type: ignore[union-attr]


def test_produce_garrison_training_clamped_by_equipment() -> None:
    before = _garrisoned(equipment=0)
    after = produce(before, CONFIG)
    assert after.garrison_infantry == before.garrison_infantry  # no equipment ⇒ no training


def test_produce_garrison_training_clamped_by_cap() -> None:
    profile = CONFIG.planets.types["terrestrial_warm"]
    gcfg = CONFIG.groundwar.garrison_economy  # type: ignore[union-attr]
    cap = round(profile.habitability * gcfg.cap_frac)
    before = _garrisoned(garrison_infantry=cap)
    after = produce(before, CONFIG)
    assert after.garrison_infantry == cap  # already at the ceiling — no further gain


def test_produce_unowned_world_does_not_train_garrison() -> None:
    before = replace(_garrisoned(), owner=Ownership("none"))
    after = produce(before, CONFIG)
    assert after is before  # unowned worlds are a full no-op in produce()


def test_is_colonizable_matches_config() -> None:
    assert is_colonizable("terrestrial_cool", CONFIG)
    assert not is_colonizable("jovian", CONFIG)
    assert not is_colonizable("barren", CONFIG)


@given(ticks=st.integers(min_value=0, max_value=50))
def test_stores_never_negative_over_many_ticks(ticks: int) -> None:
    planet = _colony(stores={Commodity.ORGANICS: 5_000})
    for _ in range(ticks):
        planet = produce(planet, CONFIG)
        assert all(v >= 0 for v in planet.stores.values())
        assert 0 <= planet.colonists <= planet.habitability_cap


def _state_with_planets() -> UniverseState:
    game = Game(id=1, seed=1, config_version=2, created_at="t", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors = {1: Sector(1, 1, (), "Hub")}
    state.planets = {
        1: _colony(owner=Ownership("player", 1)),                       # the player's colony
        2: replace(_colony(owner=Ownership("alliance", 1)), id=2),      # alliance colony (silent)
        3: replace(_colony(owner=Ownership("none")), id=3),            # unowned (no production)
    }
    return state


def test_planet_growth_cron_owner_scoped_and_deterministic() -> None:
    a, b = _state_with_planets(), _state_with_planets()
    ra, rb = planet_growth(a, CONFIG), planet_growth(b, CONFIG)
    # Pure + deterministic: identical inputs → identical changed planets.
    assert {p.id: p.stores for p in ra.planets} == {p.id: p.stores for p in rb.planets}
    by_id = {p.id: p for p in ra.planets}
    # The unowned world never *produces* (§8) — stores/colonists are untouched — but it
    # does appear in `changed` from GW-WP09's ownership-independent militia-recovery
    # rail (decision #4), which is a distinct concern from `produce()`'s owner gate.
    assert by_id[3].stores == a.planets[3].stores
    assert by_id[3].colonists == a.planets[3].colonists
    assert by_id[3].garrison_infantry > a.planets[3].garrison_infantry
    produced = [e for e in ra.events if isinstance(e, PlanetProduced)]
    assert produced and all(e.owner_player_id == 1 for e in produced)  # only the player's colony announces
    assert all(e.planet_id == 1 for e in produced)  # the alliance colony evolves silently


def test_planet_growth_militia_recovery_skips_a_truly_empty_world() -> None:
    """GW-WP09 decision #4: militia recovery runs for owned and unaligned-*inhabited*
    worlds alike, but a bare, unpeopled world grows no garrison out of nothing."""
    state = _state_with_planets()
    state.planets[4] = replace(_colony(owner=Ownership("none"), colonists=0), id=4,
                               population={}, stores={})
    result = planet_growth(state, CONFIG)
    by_id = {p.id: p for p in result.planets}
    assert 4 not in by_id  # nothing at all changed on the empty world
