"""WP4 — big-bang generation across many seeds (DESIGN §5, §13).

Generates a smaller universe across a sweep of seeds and asserts the Phase-1
invariants hold every time, plus determinism from the seed.
"""

from __future__ import annotations

import pytest

from edge.bigbang.generator import generate
from edge.bigbang.topology import bfs_distances
from edge.config import load_default_config
from edge.core.enums import PortClass
from edge.core.movement import shortest_path
from edge.core.starbases import is_operational
from helpers import enroll, generate_with_player

SEEDS = list(range(100))  # the §13 100-seed validation sweep


def _small_config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 80, "start_sector": 1})})


CONFIG = _small_config()  # the shipped default: expansive band-lattice


def _with_mode(mode: str) -> object:
    cfg = CONFIG.bigbang  # type: ignore[attr-defined]
    return CONFIG.model_copy(  # type: ignore[attr-defined]
        update={"bigbang": cfg.model_copy(update={"topology_mode": mode})}
    )


TRUNK_CONFIG = _with_mode("trunk")
EXPANSIVE_CONFIG = _with_mode("expansive")


@pytest.mark.parametrize("config", [TRUNK_CONFIG, EXPANSIVE_CONFIG], ids=["trunk", "expansive"])
@pytest.mark.parametrize("seed", SEEDS)
def test_universe_is_valid(config: object, seed: int) -> None:
    """The permanent §13 matrix: full validity across 100 seeds in **both** modes."""
    state = generate(config, seed)  # type: ignore[arg-type]
    cfg = config.bigbang  # type: ignore[attr-defined]

    # All sectors reachable from sector 1.
    assert set(bfs_distances(state.adjacency, 1)) == set(state.sectors)
    # Warp-degree cap respected (TW2002 <= 6).
    assert all(len(s.warps_out) <= cfg.max_warps_per_sector for s in state.sectors.values())
    # Exactly one StarDock, a few hops out.
    docks = [p for p in state.ports.values() if p.klass is PortClass.STARDOCK]
    assert len(docks) == 1
    # Core flagged on sectors 1..N.
    assert all(state.sectors[s].is_galactic_core for s in range(1, cfg.core_sector_count + 1))
    # The governing alliance (the roster's Federation) is seeded by the big bang.
    assert state.alliances[1].name == "Terran Federation"
    assert state.game.core_governing_alliance_id == 1
    # An enrolled player (JoinGame) joins the governor and spawns at the start sector.
    enroll(state, config)  # type: ignore[arg-type]
    assert state.players[1].alliance_id == 1
    assert state.ships[state.players[1].ship_id].sector_id == 1


def _with_start(start: object) -> object:
    return CONFIG.model_copy(  # type: ignore[attr-defined]
        update={"bigbang": CONFIG.bigbang.model_copy(update={"start_sector": start})})  # type: ignore[attr-defined]


def test_start_sector_stardock_places_player_at_the_dock() -> None:
    state = generate_with_player(_with_start("stardock"), 7)  # type: ignore[arg-type]
    dock = next(p for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    assert state.ships[state.players[1].ship_id].sector_id == dock.sector_id
    # Starting at the dock, only the dock is explored (no pre-routed breadcrumb chain).
    assert state.players[1].explored_sectors == frozenset({dock.sector_id})


def test_start_sector_explicit_id() -> None:
    state = generate_with_player(_with_start(5), 7)  # type: ignore[arg-type]
    assert state.ships[state.players[1].ship_id].sector_id == 5


def test_start_sector_random_is_deterministic_and_valid() -> None:
    a = generate_with_player(_with_start("random"), 7)  # type: ignore[arg-type]
    b = generate_with_player(_with_start("random"), 7)  # type: ignore[arg-type]
    start_a = a.ships[a.players[1].ship_id].sector_id
    assert start_a in a.sectors  # a real sector
    assert start_a == b.ships[b.players[1].ship_id].sector_id  # reproducible from the seed


@pytest.mark.parametrize("seed", range(20))
def test_starbases_placed_and_consistent(seed: int) -> None:
    """Orbital bases hang off planets with the §4.2 derelict/owned split (WP4)."""
    state = generate(CONFIG, seed)  # type: ignore[arg-type]
    for base in state.starbases.values():
        planet = state.planets[base.planet_id]
        assert planet.starbase_id == base.id  # planet back-references its base
        assert base.sector_id == planet.sector_id
        if planet.owner.is_owned:
            assert is_operational(base)  # owned worlds keep working bases
        elif not is_operational(base):
            # A derelict sits only on an unowned, uninhabited world…
            assert not planet.owner.is_owned and planet.inhabited_by_species_id is None
            # …and still holds salvageable components (a cache, not an empty husk).
            assert any(c is not None for sub in base.subsystems.values() for c in sub.slots)


def test_starbase_population_split_over_seeds() -> None:
    """Across seeds, generation yields both intact and derelict bases (WP4)."""
    intact = derelict = 0
    for seed in range(30):
        for base in generate(CONFIG, seed).starbases.values():  # type: ignore[arg-type]
            if is_operational(base):
                intact += 1
            else:
                derelict += 1
    assert intact > 0 and derelict > 0


def test_generation_is_deterministic() -> None:
    a = generate(CONFIG, 7)  # type: ignore[arg-type]
    b = generate(CONFIG, 7)  # type: ignore[arg-type]
    assert a.adjacency == b.adjacency
    assert a.sectors == b.sectors
    assert a.ports == b.ports
    assert a.planets == b.planets
    assert a.starbases == b.starbases


def test_different_seeds_differ() -> None:
    a = generate(CONFIG, 1)  # type: ignore[arg-type]
    b = generate(CONFIG, 2)  # type: ignore[arg-type]
    assert a.adjacency != b.adjacency


# --- WP20: topology modes (trunk / expansive band-lattice, DESIGN §5 step 2) ---

def test_topology_mode_defaults_to_expansive() -> None:
    # The Phase-3 epoch (WP22) flipped the default to the band-lattice.
    assert CONFIG.bigbang.topology_mode == "expansive"  # type: ignore[attr-defined]


def test_topology_modes_differ() -> None:
    trunk = generate(TRUNK_CONFIG, 3)  # type: ignore[arg-type]
    expansive = generate(EXPANSIVE_CONFIG, 3)  # type: ignore[arg-type]
    assert trunk.adjacency != expansive.adjacency


@pytest.mark.parametrize("seed", SEEDS)
def test_expansive_universe_is_valid(seed: int) -> None:
    state = generate(EXPANSIVE_CONFIG, seed)  # type: ignore[arg-type]
    cfg = EXPANSIVE_CONFIG.bigbang  # type: ignore[attr-defined]
    # Single component: every sector reachable from sector 1.
    assert set(bfs_distances(state.adjacency, 1)) == set(state.sectors)
    # Warp-degree cap respected.
    assert all(len(s.warps_out) <= cfg.max_warps_per_sector for s in state.sectors.values())


def _cross_region_edges(state: object) -> list[tuple[int, int]]:
    sectors = state.sectors  # type: ignore[attr-defined]
    return [
        (u, v)
        for u, nbrs in state.adjacency.items()  # type: ignore[attr-defined]
        for v in nbrs
        if sectors[u].region_id != sectors[v].region_id
    ]


@pytest.mark.parametrize("seed", range(30))
def test_expansive_has_no_single_bridge_chokepoint(seed: int) -> None:
    """The lattice property (§5): removing any single inter-region warp leaves
    every sector reachable from sector 1 — i.e. two edge-disjoint inward paths."""
    state = generate(EXPANSIVE_CONFIG, seed)  # type: ignore[arg-type]
    all_sectors = set(state.sectors)
    for u, v in _cross_region_edges(state):
        adj = {sid: set(nbrs) for sid, nbrs in state.adjacency.items()}
        adj[u].discard(v)
        assert set(bfs_distances(adj, 1)) == all_sectors, f"seed {seed}: {u}->{v} is a chokepoint"


def test_trunk_has_chokepoints() -> None:
    """Contrast: the trunk universe *does* funnel through cut edges — removing the
    right inter-region warp strands sectors. (Guards against the modes collapsing.)"""
    for seed in range(30):
        state = generate(TRUNK_CONFIG, seed)  # type: ignore[arg-type]
        all_sectors = set(state.sectors)
        for u, v in _cross_region_edges(state):
            adj = {sid: set(nbrs) for sid, nbrs in state.adjacency.items()}
            adj[u].discard(v)
            if set(bfs_distances(adj, 1)) != all_sectors:
                return  # found a chokepoint, as expected of trunk
    raise AssertionError("expected trunk topology to contain at least one chokepoint")


# --- WP21: per-mode band retune (DESIGN §5 step 5) ---

def test_active_bands_resolves_by_mode() -> None:
    """`active_bands()` returns the trunk `bands` normally and `bands_expansive`
    (same names, deeper thresholds) in expansive mode."""
    trunk_bands = TRUNK_CONFIG.bigbang.active_bands()  # type: ignore[attr-defined]
    exp_bands = EXPANSIVE_CONFIG.bigbang.active_bands()  # type: ignore[attr-defined]
    assert [b.name for b in trunk_bands] == [b.name for b in exp_bands]  # identical names
    # Deeper hop windows under expansive (the ring-road lattice lengthens paths).
    assert exp_bands[-1].min_hops > trunk_bands[-1].min_hops


def test_bands_expansive_name_mismatch_rejected() -> None:
    """The config validator enforces same band names across modes (only thresholds
    differ), so no name-keyed placement/validation silently diverges."""
    import pydantic

    from edge.core.config import BandSet, DistanceBand

    with pytest.raises(pydantic.ValidationError):
        BandSet(
            trunk=[DistanceBand(name="Hub", min_hops=0, max_hops=5)],
            expansive=[DistanceBand(name="Core", min_hops=0, max_hops=9)],
        )


def _big_expansive_config(sector_count: int = 1000) -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"topology_mode": "expansive", "sector_count": sector_count, "start_sector": 1})})


BIG_EXPANSIVE = _big_expansive_config()


@pytest.mark.parametrize("seed", range(8))
def test_expansive_populates_all_four_bands(seed: int) -> None:
    """At the real 1000-sector scale the retuned `bands.expansive` keeps all four
    bands populated, with the frontier bands larger than the Hub (danger/reward
    rises outward, §5/§7)."""
    from collections import Counter

    state = generate(BIG_EXPANSIVE, seed)  # type: ignore[arg-type]
    counts = Counter(s.distance_band for s in state.sectors.values())
    for band in ("Hub", "Frontier", "Deep", "Void"):
        assert counts.get(band, 0) > 0, f"seed {seed}: band {band} empty ({dict(counts)})"
    assert counts["Hub"] < counts["Frontier"]  # the Hub is the small safe centre


# --- WP23: alliance home clusters + neutral lanes (DESIGN §5 step 6) ---

@pytest.mark.parametrize("config", [TRUNK_CONFIG, EXPANSIVE_CONFIG], ids=["trunk", "expansive"])
@pytest.mark.parametrize("seed", range(40))
def test_home_clusters_well_formed(config: object, seed: int) -> None:
    """Both modes: one cluster per cast bloc; each smaller than the Core, never
    Core-adjacent, never rival-linked; and an all-neutral path from the Core to every
    band (the frontier reachable without transiting a bloc's territory)."""
    state = generate(config, seed)  # type: ignore[arg-type]
    gov = state.game.core_governing_alliance_id
    cast_blocs = {sp.alliance_id for sp in state.species.values()
                  if sp.alliance_id is not None and sp.alliance_id != gov}
    clusters = state.home_clusters
    assert set(clusters) == cast_blocs  # exactly one cluster per bloc in the cast

    core_ids = {s.id for s in state.sectors.values() if s.is_galactic_core}
    sector_bloc = {sid: bloc for bloc, secs in clusters.items() for sid in secs}
    for bloc, secs in clusters.items():
        assert 3 <= len(secs) < config.bigbang.core_sector_count  # type: ignore[attr-defined]
        for sid in secs:
            assert not any(n in core_ids for n in state.adjacency[sid])  # never Core-adjacent
            for n in state.adjacency[sid]:
                assert sector_bloc.get(n, bloc) == bloc  # never warp-linked to a rival

    # An all-neutral path (avoiding every cluster) from the Core reaches every band.
    cluster_sectors = set(sector_bloc)
    reached = set(core_ids)
    frontier = list(core_ids)
    while frontier:
        cur = frontier.pop()
        for n in state.adjacency[cur]:
            if n not in reached and n not in cluster_sectors:
                reached.add(n)
                frontier.append(n)
    live_bands = {s.distance_band for s in state.sectors.values() if not s.is_galactic_core}
    reached_bands = {state.sectors[s].distance_band for s in reached}
    assert live_bands <= reached_bands


def test_home_cluster_planets_alliance_owned() -> None:
    """A cluster's non-derelict planets are owned by its bloc; a derelict-hosting world
    stays unowned (§4.2), so the base validator's derelict⇒unowned rule still holds."""
    from edge.core.starbases import is_operational

    for seed in range(10):
        state = generate(BIG_EXPANSIVE, seed)  # type: ignore[arg-type]
        for bloc, secs in state.home_clusters.items():
            for planet in state.planets.values():
                if planet.sector_id not in secs:
                    continue
                base = state.starbases.get(planet.starbase_id) if planet.starbase_id else None
                if base is not None and not is_operational(base):
                    assert planet.owner.kind == "none"  # derelict cache stays unowned
                else:
                    assert planet.owner == type(planet.owner)(kind="alliance", ref=bloc)


@pytest.mark.parametrize("seed", range(20))
def test_spatial_ids_wired_into_generate(seed: int) -> None:
    """`generate` caches a spatial display id per sector (DESIGN §5.1, WP-G)."""
    state = generate(CONFIG, seed)  # type: ignore[arg-type]
    spatial = state.spatial_ids
    assert set(spatial) == set(state.sectors)  # every sector mapped
    assert len(set(spatial.values())) == len(spatial)  # bijection (reversible for input)
    assert spatial[1] == min(spatial.values())  # Terra anchors the lowest id


@pytest.mark.parametrize("seed", range(20))
def test_stardock_route_starts_explored(seed: int) -> None:
    """The path from the start sector to StarDock opens pre-explored (round-2).

    Only the shortest path is revealed — the rest of the universe stays fogged —
    and the breadcrumb chain matches it, so `TravelTo(dock)` works on turn one.
    """
    state = generate_with_player(CONFIG, seed)  # type: ignore[arg-type]
    player = state.players[1]
    dock = next(p for p in state.ports.values() if p.klass is PortClass.STARDOCK)

    route = shortest_path(state.adjacency, 1, dock.sector_id)
    assert route is not None
    # Exactly the route is explored — nothing more, nothing less.
    assert player.explored_sectors == frozenset(route)
    # The breadcrumb chains each hop back to its predecessor.
    assert dict(player.entered_from) == {route[i + 1]: route[i] for i in range(len(route) - 1)}
    # The route is uncovered for route-locked travel, off-route stays fogged.
    assert shortest_path(state.adjacency, 1, dock.sector_id, allowed=set(player.explored_sectors))
    assert len(player.explored_sectors) < len(state.sectors)


def test_mesh_topology_generation() -> None:
    """Test generating in mesh topology mode."""
    mesh_cfg = CONFIG.model_copy(
        update={
            "bigbang": CONFIG.bigbang.model_copy(
                update={"topology_mode": "mesh", "sector_count": 100}
            )
        }
    )
    state = generate(mesh_cfg, seed=4)  # type: ignore[arg-type]
    
    assert len(state.sectors) == 100
    
    import math
    n = 100
    R = math.isqrt(n)
    if R * R < n:
        R = math.isqrt(n) + 1
    C = (n + R - 1) // R
    
    coords = {}
    for sid, (x, y) in state.sector_pos.items():
        c = int(round(x + C / 2.0))
        r = int(round(y + R / 2.0))
        coords[sid] = (r, c)
        assert 0 <= r < R
        assert 0 <= c < C

    for u, nbrs in state.adjacency.items():
        ru, cu = coords[u]
        for v in nbrs:
            rv, cv = coords[v]
            dr = abs(ru - rv)
            dc = abs(cu - cv)
            assert (dr == 1 and dc == 0) or (dr == 1 and dc == 1), f"Invalid mesh edge {u} ({ru},{cu}) -> {v} ({rv},{cv})"
