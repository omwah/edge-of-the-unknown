"""WP-E/WP-G — the spatial sector-numbering function (DESIGN §5.1).

`assign_spatial_ids` derives the player-facing display id; it is wired into
`generate` (cached on `UniverseState.spatial_ids`) but tested here in isolation.
These tests pin its invariants — determinism, bijection, region-atomic prefixes,
and band-monotone ordering — across a sweep of seeds. (The generate-time wiring and
the projection/TUI use are covered by test_bigbang/test_session/test_service.)
"""

from __future__ import annotations

import random

import pytest

from edge.bigbang.generator import build_graph
from edge.bigbang.numbering import assign_spatial_ids
from edge.bigbang.topology import band_for_hops, bfs_distances
from edge.config import load_default_config

SEEDS = list(range(25))


def _small_config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 120})})


CONFIG = _small_config()


def _inputs(seed: int):
    cfg = CONFIG.bigbang  # type: ignore[attr-defined]
    out, groups = build_graph(cfg, random.Random(f"{seed}-0"))
    core_hops = bfs_distances(out, 1)
    return groups, core_hops, cfg.active_bands()


@pytest.mark.parametrize("seed", SEEDS)
def test_is_a_bijection_over_all_sectors(seed: int) -> None:
    groups, core_hops, bands = _inputs(seed)
    ids = assign_spatial_ids(groups, core_hops, bands)
    all_sectors = {sid for g in groups for sid in g}
    assert set(ids) == all_sectors  # every sector mapped
    assert len(set(ids.values())) == len(ids)  # no collisions


@pytest.mark.parametrize("seed", SEEDS)
def test_is_pure_and_deterministic(seed: int) -> None:
    groups, core_hops, bands = _inputs(seed)
    assert assign_spatial_ids(groups, core_hops, bands) == assign_spatial_ids(groups, core_hops, bands)


@pytest.mark.parametrize("seed", SEEDS)
def test_regions_are_atomic_and_band_monotone(seed: int) -> None:
    groups, core_hops, bands = _inputs(seed)
    ids = assign_spatial_ids(groups, core_hops, bands)
    band_index = {b.name: i for i, b in enumerate(bands)}

    # Recover the positional strides from the same width rule the encoder uses.
    ord_digits = max(2, len(str(max(len(g) for g in groups))))
    region_digits = max(2, len(str(max(len(r) for r in _regions_per_band(groups, core_hops, bands)))))
    region_stride = 10**ord_digits
    band_stride = 10 ** (ord_digits + region_digits)

    for group in groups:
        # Every region's sectors share one band+region prefix (region atomic) ...
        assert len({ids[sid] // region_stride for sid in group}) == 1
        # ... and that prefix's band digit is the region's representative band.
        rep_hop = min(core_hops.get(s, 10**9) for s in group)
        rep_band = band_index[band_for_hops(rep_hop, bands)]
        assert all(ids[sid] // band_stride - 1 == rep_band for sid in group)

    # Sorting sectors by id yields non-decreasing band (band-monotone overall).
    by_id = sorted(ids, key=lambda s: ids[s])
    bands_in_id_order = [_sector_band(s, groups, core_hops, bands, band_index) for s in by_id]
    assert bands_in_id_order == sorted(bands_in_id_order)


def test_core_sector_one_gets_the_lowest_id() -> None:
    groups, core_hops, bands = _inputs(7)
    ids = assign_spatial_ids(groups, core_hops, bands)
    assert ids[1] == min(ids.values())  # Terra anchors the numbering at the Core


def test_empty_and_band_cap() -> None:
    _, core_hops, bands = _inputs(1)
    assert assign_spatial_ids([], core_hops, bands) == {}
    too_many = bands * 5  # > 9 bands
    with pytest.raises(ValueError, match="9 distance bands"):
        assign_spatial_ids([[1]], core_hops, too_many)


# --- helpers ---------------------------------------------------------------


def _regions_per_band(groups, core_hops, bands):
    from collections import defaultdict

    band_index = {b.name: i for i, b in enumerate(bands)}
    buckets = defaultdict(list)
    for gi, group in enumerate(groups):
        rep_hop = min(core_hops.get(s, 10**9) for s in group)
        buckets[band_index[band_for_hops(rep_hop, bands)]].append(gi + 1)
    return list(buckets.values())


def _sector_band(sid, groups, core_hops, bands, band_index):
    for group in groups:
        if sid in group:
            rep_hop = min(core_hops.get(s, 10**9) for s in group)
            return band_index[band_for_hops(rep_hop, bands)]
    raise AssertionError(sid)
