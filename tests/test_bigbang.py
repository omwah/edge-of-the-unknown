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

SEEDS = list(range(100))  # the §13 100-seed validation sweep


def _small_config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 80, "start_sector": 1})})


CONFIG = _small_config()


@pytest.mark.parametrize("seed", SEEDS)
def test_universe_is_valid(seed: int) -> None:
    state = generate(CONFIG, seed)  # type: ignore[arg-type]
    cfg = CONFIG.bigbang  # type: ignore[attr-defined]

    # All sectors reachable from sector 1.
    assert set(bfs_distances(state.adjacency, 1)) == set(state.sectors)
    # Warp-degree cap respected (TW2002 <= 6).
    assert all(len(s.warps_out) <= cfg.max_warps_per_sector for s in state.sectors.values())
    # Exactly one StarDock, a few hops out.
    docks = [p for p in state.ports.values() if p.klass is PortClass.STARDOCK]
    assert len(docks) == 1
    # Core flagged on sectors 1..N.
    assert all(state.sectors[s].is_galactic_core for s in range(1, cfg.core_sector_count + 1))
    # Player, ship, and the governing alliance (the roster's Federation) are seeded.
    assert state.players[1].alliance_id == 1
    assert state.alliances[1].name == "Terran Federation"
    assert state.ships[state.players[1].ship_id].sector_id == 1
    assert state.game.core_governing_alliance_id == 1


def _with_start(start: object) -> object:
    return CONFIG.model_copy(  # type: ignore[attr-defined]
        update={"bigbang": CONFIG.bigbang.model_copy(update={"start_sector": start})})  # type: ignore[attr-defined]


def test_start_sector_stardock_places_player_at_the_dock() -> None:
    state = generate(_with_start("stardock"), 7)  # type: ignore[arg-type]
    dock = next(p for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    assert state.ships[state.players[1].ship_id].sector_id == dock.sector_id
    # Starting at the dock, only the dock is explored (no pre-routed breadcrumb chain).
    assert state.players[1].explored_sectors == frozenset({dock.sector_id})


def test_start_sector_explicit_id() -> None:
    state = generate(_with_start(5), 7)  # type: ignore[arg-type]
    assert state.ships[state.players[1].ship_id].sector_id == 5


def test_start_sector_random_is_deterministic_and_valid() -> None:
    a = generate(_with_start("random"), 7)  # type: ignore[arg-type]
    b = generate(_with_start("random"), 7)  # type: ignore[arg-type]
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
    state = generate(CONFIG, seed)  # type: ignore[arg-type]
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
