"""Seeded spatial embedding (edge/bigbang/embedding) — pure, deterministic (§5.1).

The embedding is the nav rose's sense of direction: a stable per-sector 2D position
derived once at generation. It is a runtime cache, so it must be reproducible from
the seed and must never leak into `state_hash` / the `(seed, command log)` rail.
"""

from __future__ import annotations

import math

from edge.bigbang.embedding import bearing, compute_embedding
from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.store.snapshots import state_hash


def _small_config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"sector_count": 80, "start_sector": 1})})


CONFIG = _small_config()
EXPANSIVE_CONFIG = CONFIG.model_copy(update={  # type: ignore[attr-defined]
    "bigbang": CONFIG.bigbang.model_copy(update={"topology_mode": "expansive"})})  # type: ignore[attr-defined]


def test_embedding_is_populated_and_deterministic() -> None:
    a = generate(CONFIG, 42)  # type: ignore[arg-type]
    b = generate(CONFIG, 42)  # type: ignore[arg-type]
    assert a.sector_pos  # a position for every sector
    assert set(a.sector_pos) == set(a.sectors)
    assert a.sector_pos == b.sector_pos  # same seed → identical layout


def test_embedding_deterministic_under_expansive() -> None:
    """The lattice-corrected angle (mean of min-hop parents, §5.1) stays a pure,
    reproducible function of the seed in expansive mode too."""
    a = generate(EXPANSIVE_CONFIG, 42)  # type: ignore[arg-type]
    b = generate(EXPANSIVE_CONFIG, 42)  # type: ignore[arg-type]
    assert set(a.sector_pos) == set(a.sectors)
    assert a.sector_pos == b.sector_pos
    assert a.sector_pos[1] == (0.0, 0.0)  # Core still pinned to the origin


def test_core_pinned_to_origin() -> None:
    state = generate(CONFIG, 7)  # type: ignore[arg-type]
    assert state.sector_pos[1] == (0.0, 0.0)  # "bearing to Core" is globally consistent


def test_bearing_antisymmetry_over_bidirectional_warps() -> None:
    """A→B and B→A point exactly opposite (±π), so the map never contradicts itself."""
    state = generate(CONFIG, 3)  # type: ignore[arg-type]
    pos = state.sector_pos
    for a, outs in state.adjacency.items():
        for b in outs:
            if a in state.adjacency.get(b, ()) and pos[a] != pos[b]:  # bidirectional, distinct
                diff = (bearing(pos, a, b) - bearing(pos, b, a)) % (2 * math.pi)
                assert abs(diff - math.pi) < 1e-6


def test_sector_pos_excluded_from_state_hash() -> None:
    """Clearing or perturbing the cache leaves the fingerprint unchanged — replays safe."""
    state = generate(CONFIG, 11)  # type: ignore[arg-type]
    baseline = state_hash(state)
    state.sector_pos = {}
    assert state_hash(state) == baseline
    state.sector_pos = {1: (5.0, 5.0), 2: (-3.0, 1.0)}
    assert state_hash(state) == baseline


def test_bearing_degrades_when_position_missing() -> None:
    assert bearing({}, 1, 2) == 0.0
    assert bearing({1: (0.0, 0.0)}, 1, 2) == 0.0  # only one endpoint known
    assert bearing({1: (0.0, 0.0), 2: (0.0, 0.0)}, 1, 2) == 0.0  # coincident


def test_compute_embedding_is_pure_over_its_args() -> None:
    adjacency = {1: [2, 3], 2: [1, 4], 3: [1], 4: [2]}
    core_hops = {1: 0, 2: 1, 3: 1, 4: 2}
    first = compute_embedding(adjacency, core_hops, seed=99)
    second = compute_embedding(adjacency, core_hops, seed=99)
    assert first == second
    assert first[1] == (0.0, 0.0)
    assert set(first) == {1, 2, 3, 4}
