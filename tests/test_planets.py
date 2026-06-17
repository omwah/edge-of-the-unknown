"""WP3 — planetary production (DESIGN §4.2, §8) and the planet_growth cron."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.events import PlanetProduced
from edge.core.models import Game, Ownership, Planet, Sector, UniverseState
from edge.core.planets import is_colonizable, produce
from edge.engine.cron import planet_growth

CONFIG = load_default_config()


def _colony(ptype: str = "terrestrial_warm", colonists: int = 1000, owner: Ownership | None = None,
            stores: dict[Commodity, int] | None = None) -> Planet:
    profile = CONFIG.planets.types[ptype]
    return Planet(
        id=1, sector_id=1, name="P", planet_type=ptype,
        owner=owner if owner is not None else Ownership("player", 1),
        colonists=colonists, habitability_cap=profile.habitability,
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
    belt = _colony("asteroid_belt", colonists=0, stores={})
    assert produce(belt, CONFIG).stores[Commodity.EQUIPMENT] == CONFIG.planets.asteroid_mining
    barren = _colony("barren", colonists=0, stores={})
    assert produce(barren, CONFIG) is barren  # produces nothing


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
    changed = {p.id for p in ra.planets}
    assert 3 not in changed  # the unowned world never produces (§8)
    produced = [e for e in ra.events if isinstance(e, PlanetProduced)]
    assert produced and all(e.owner_player_id == 1 for e in produced)  # only the player's colony announces
    assert all(e.planet_id == 1 for e in produced)  # the alliance colony evolves silently
