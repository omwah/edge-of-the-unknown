"""GW-WP05 — survey generation from real universe discoveries (GW plan §GW-M2).

Two halves:

- the pure `generate_survey` / `eligible_surface_site_ids` map builder — deterministic
  placement, one site per real `Discovery.id` (G6), reachability, sensor non-leakage +
  upgrade-and-return via per-discovery salts (G7), the zero-site and already-collected
  cases, and friendly-vs-uninhabited settlement generation;
- the D6 payload normalization in the big bang — every surface find yields an
  artifact plus codex lore and never latinum/components, while open-space and
  combat-wreck payloads stay untouched.
"""

from __future__ import annotations

from collections import Counter

import pytest

from edge.config import load_default_config
from edge.core.enums import DiscoveryKind, PayloadKind, RarityTier
from edge.core.groundwar.survey import (
    _move_cost,
    _passable_components,
    eligible_surface_site_ids,
    generate_survey,
)
from edge.core.models import Discovery, DiscoveryPayload
from edge.core.surface_finds import surface_find_name
from edge.bigbang.generator import generate

CFG = load_default_config()


def _disc(i: int, *, hidden: bool = False, rarity: RarityTier = RarityTier.RARE) -> Discovery:
    return Discovery(
        id=i, kind=DiscoveryKind.RUINS, rarity_tier=rarity, sector_id=1,
        payload=DiscoveryPayload(kind=PayloadKind.ARTIFACT, barter_tier="II", lore="x"),
        planet_id=1, site_slot=i, hidden=hidden, name=f"Site {i}")


def _survey(sites, *, seed: int = 7, inhabited: bool = True, resolved=frozenset()):
    return generate_survey(CFG, seed=seed, planet_type="terrestrial_warm",
                           inhabited=inhabited, sites=sites, resolved_ids=resolved)


# --- pure generation ---------------------------------------------------------


def test_placement_is_deterministic() -> None:
    sites = [_disc(i) for i in range(1, 5)]
    a = _survey(sites)
    b = _survey(sites)
    assert [(s.discovery_id, s.x, s.y) for s in a.sites] == [
        (s.discovery_id, s.x, s.y) for s in b.sites]
    assert a.feature == b.feature and a.settlements == b.settlements


def test_one_site_per_real_discovery_id() -> None:
    sites = [_disc(i) for i in (3, 8, 11)]
    m = _survey(sites)
    assert sorted(s.discovery_id for s in m.sites) == [3, 8, 11]
    for s in m.sites:  # POC presentation decorates the record without changing its id (G6)
        src = next(d for d in sites if d.id == s.discovery_id)
        assert s.name == surface_find_name(src.kind, src.id)
        assert s.rarity == src.rarity_tier.name


def test_sites_and_landing_share_one_passable_component() -> None:
    m = _survey([_disc(i) for i in range(1, 6)])
    feat = [list(r) for r in m.feature]
    blocked = set(m.blocked)
    labels, _ = _passable_components(feat, blocked, CFG, m.width, m.height)
    comp = labels[m.landing_y][m.landing_x]
    assert _move_cost(feat, blocked, CFG, m.landing_x, m.landing_y) > 0
    assert all(labels[s.y][s.x] == comp for s in m.sites)


def test_hidden_site_never_placed_when_not_passed() -> None:
    # G7: only the caller's visible list is placed; a withheld (hidden) site leaks nothing.
    visible = [_disc(1), _disc(2)]
    m = _survey(visible)
    assert {s.discovery_id for s in m.sites} == {1, 2}


def test_upgrade_and_return_keeps_known_sites_put() -> None:
    base = [_disc(1), _disc(2), _disc(3)]
    before = {s.discovery_id: (s.x, s.y) for s in _survey(base).sites}
    after = {s.discovery_id: (s.x, s.y)
             for s in _survey(base + [_disc(4)]).sites}  # a newly-resolved site appears
    assert all(before[i] == after[i] for i in before)  # …and moves none of the old ones
    assert 4 in after


def test_zero_site_world_still_lands() -> None:
    m = _survey([])
    assert m.sites == ()
    feat = [list(r) for r in m.feature]
    assert _move_cost(feat, set(m.blocked), CFG, m.landing_x, m.landing_y) > 0


def test_already_collected_site_marked_found() -> None:
    sites = [_disc(1), _disc(2)]
    m = _survey(sites, resolved=frozenset({1}))
    by_id = {s.discovery_id: s for s in m.sites}
    assert by_id[1].found and not by_id[2].found


def test_friendly_world_gets_settlements_uninhabited_does_not() -> None:
    sites = [_disc(i) for i in range(1, 4)]
    assert len(_survey(sites, inhabited=True).settlements) >= 1
    assert _survey(sites, inhabited=False).settlements == ()


# --- Cloud City tour (GW-WP17) -------------------------------------------------


def test_cloud_city_survey_uses_the_interior_layout_with_no_sites_or_settlements() -> None:
    """A Cloud City tour ignores any passed-in `sites` entirely — it's a built
    station, not an archaeology find (GW-WP17) — and its dimensions come from
    `groundwar.cloud_city`, not the planet expedition map."""
    m = generate_survey(
        CFG, seed=42, planet_type="jovian", inhabited=True, sites=[_disc(1)],
        cloud_city_size=2)
    assert m.sites == ()
    assert m.settlements == ()
    cc = CFG.groundwar.cloud_city  # type: ignore[union-attr]
    assert (m.width, m.height) == (cc.width, cc.height)
    feature_names = {name for row in m.feature for name in row}
    assert "bulkhead" in feature_names  # the room/corridor layout, not biome noise
    assert _move_cost([list(r) for r in m.feature], set(m.blocked), CFG,
                      m.landing_x, m.landing_y) > 0


def test_cloud_city_survey_is_deterministic() -> None:
    a = generate_survey(CFG, seed=99, planet_type="jovian", inhabited=True,
                        sites=[], cloud_city_size=3)
    b = generate_survey(CFG, seed=99, planet_type="jovian", inhabited=True,
                        sites=[], cloud_city_size=3)
    assert a.feature == b.feature and (a.landing_x, a.landing_y) == (b.landing_x, b.landing_y)


def test_eligible_surface_site_ids_excludes_every_cloud_city() -> None:
    """A Cloud City never surfaces a dig site, regardless of what big bang rolled
    for the underlying jovian before it was staged (GW-WP17)."""
    from edge.core.models import Game, Planet, Sector, UniverseState

    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.planets = {1: Planet(id=1, sector_id=1, name="Sky City",
                               planet_type="jovian", cloud_city_size=2)}
    state.discoveries = {1: _disc(1)}
    assert eligible_surface_site_ids(state, 1, 9999, frozenset(), CFG) == frozenset()


# --- eligibility snapshot on a real universe ---------------------------------


def _planet_with_hidden_and_obvious():
    """A world with both a hidden and an obvious surface site — excluding jovians:
    a Cloud City never surfaces a site regardless (GW-WP17, `eligible_surface_site_ids`),
    so a seed that happens to land this fixture on one would test the wrong predicate."""
    for seed in range(80):
        st = generate(CFG, seed)
        by_planet: dict[int, list[Discovery]] = {}
        for d in st.discoveries.values():
            if d.planet_id is not None:
                by_planet.setdefault(d.planet_id, []).append(d)
        for pid, ds in by_planet.items():
            if st.planets[pid].planet_type == "jovian":
                continue
            if any(d.hidden for d in ds) and any(not d.hidden for d in ds):
                return st, pid
    raise AssertionError("no planet with both hidden and obvious sites found")


def test_eligibility_is_sensor_monotone_and_non_leaking() -> None:
    st, pid = _planet_with_hidden_and_obvious()
    sites = [d for d in st.discoveries.values() if d.planet_id == pid]
    low = eligible_surface_site_ids(st, pid, 0, frozenset(), CFG)
    high = eligible_surface_site_ids(st, pid, 9999, frozenset(), CFG)
    assert low <= high  # a stronger sensor never resolves *fewer* sites
    assert high == {d.id for d in sites}  # a strong enough sensor resolves them all
    hidden = {d.id for d in sites if d.hidden}
    assert not (hidden & low) or high != low  # weak sensor withholds at least the hidden ones


def test_already_detected_site_is_visible_regardless_of_sensor() -> None:
    st, pid = _planet_with_hidden_and_obvious()
    hidden = next(d for d in st.discoveries.values() if d.planet_id == pid and d.hidden)
    seen = eligible_surface_site_ids(st, pid, 0, frozenset({hidden.id}), CFG)
    assert hidden.id in seen  # prior detection keeps it visible even at zero sensor


# --- D6 payload normalization ------------------------------------------------


@pytest.mark.parametrize("seed", range(8))
def test_every_surface_find_is_artifact_plus_lore(seed: int) -> None:
    st = generate(CFG, seed)
    surface = [d for d in st.discoveries.values() if d.planet_id is not None]
    assert surface, "expected some surface sites"
    for d in surface:
        assert d.payload.kind is PayloadKind.ARTIFACT and d.payload.lore
        assert d.payload.latinum == 0 and d.payload.component is None


def test_open_space_payloads_keep_their_variety() -> None:
    # D6 touches only surface sites; open-space finds still span latinum/component/artifact/lore.
    kinds: Counter[PayloadKind] = Counter()
    for seed in range(10):
        st = generate(CFG, seed)
        for d in st.discoveries.values():
            if d.planet_id is None:
                kinds[d.payload.kind] += 1
    assert kinds[PayloadKind.LATINUM] and kinds[PayloadKind.COMPONENT]
    assert kinds[PayloadKind.ARTIFACT] and kinds[PayloadKind.LORE]
