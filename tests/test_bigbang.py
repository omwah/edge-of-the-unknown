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
