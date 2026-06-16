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

SEEDS = list(range(100))  # the §13 100-seed validation sweep


def _small_config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 80})})


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
    # Player, ship, and the Federation alliance are seeded.
    assert state.players[1].alliance_id == 1
    assert state.alliances[1].name == "Federation"
    assert state.ships[state.players[1].ship_id].sector_id == 1
    assert state.game.core_governing_alliance_id == 1


def test_generation_is_deterministic() -> None:
    a = generate(CONFIG, 7)  # type: ignore[arg-type]
    b = generate(CONFIG, 7)  # type: ignore[arg-type]
    assert a.adjacency == b.adjacency
    assert a.sectors == b.sectors
    assert a.ports == b.ports
    assert a.planets == b.planets


def test_different_seeds_differ() -> None:
    a = generate(CONFIG, 1)  # type: ignore[arg-type]
    b = generate(CONFIG, 2)  # type: ignore[arg-type]
    assert a.adjacency != b.adjacency


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
