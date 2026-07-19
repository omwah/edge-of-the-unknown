"""Spatial sector numbering — the player-facing display id (DESIGN §5.1).

Derives human-legible, band-monotone sector ids from the warp topology. These are a
**secondary, UI-only id**: the internal incremental sector ids stay authoritative
(data model, command/event log, golden-master hashes), and this map is cached on
`UniverseState.spatial_ids` at the end of `generate` (like `core_hops`) and shown
only at the `server/session.py` projection boundary. Because it is derived, nothing
authored or persisted changes — no cutover, no golden-master regeneration.

Clustered modes use a **multi-level, gapped, band-monotone integer**: a band digit,
then a region prefix, then a local ordinal. Spiral mode instead uses a contiguous
`10000 + ordinal` sequence so increasing display IDs trace its numerical backbone.
Both projections are pure, deterministic **bijections**, so the travel prompt can
map a typed spatial id back to internal.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from edge.bigbang.topology import band_for_hops
from edge.core.config import DistanceBand

_INF = 10**9
_MIN_FIELD_DIGITS = 2  # ordinals/regions read as zero-padded pairs at minimum


def _field_digits(largest: int) -> int:
    """Digit width for a 1-based field whose biggest value is `largest`."""
    return max(_MIN_FIELD_DIGITS, len(str(max(1, largest))))


def assign_spatial_ids(
    groups: list[list[int]],
    core_hops: Mapping[int, int],
    bands: list[DistanceBand],
) -> dict[int, int]:
    """Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1).

    `groups[i]` is region `i + 1` (matching the generator's region numbering). Each
    region is assigned a single **home band** — the band of its representative
    (minimum-hop) sector — so a region is *atomic*: all its sectors share one
    `band+region` prefix, even if the cluster physically straddles a band boundary.
    Regions are then ordered within their band by representative hop distance, and
    sectors within a region by hop distance then id (which lays a linear tunnel out
    sequentially). The encoding is positional and gapped:

        new_id = (band_index + 1)·band_stride + region_local·region_stride + ordinal

    with field widths derived from the actual counts, so small universes get compact
    (4–5 digit) ids and large ones widen gracefully. Pure and deterministic.
    """
    if not groups:
        return {}
    if len(bands) > 9:  # one decimal digit reserved for the band
        raise ValueError("spatial numbering supports at most 9 distance bands")

    band_index = {b.name: i for i, b in enumerate(bands)}
    region_sectors = {gi + 1: list(group) for gi, group in enumerate(groups)}

    def rep_hop(rid: int) -> int:
        return min((core_hops.get(s, _INF) for s in region_sectors[rid]), default=_INF)

    def region_band(rid: int) -> int:
        return band_index.get(band_for_hops(rep_hop(rid), bands), len(bands) - 1)

    regions_by_band: dict[int, list[int]] = defaultdict(list)
    for rid in region_sectors:
        regions_by_band[region_band(rid)].append(rid)

    max_ordinal = max(len(s) for s in region_sectors.values())
    max_regions = max(len(r) for r in regions_by_band.values())
    ord_digits = _field_digits(max_ordinal)
    region_digits = _field_digits(max_regions)
    region_stride = 10**ord_digits
    band_stride = 10 ** (ord_digits + region_digits)

    new_id: dict[int, int] = {}
    for band_idx in sorted(regions_by_band):
        ordered_regions = sorted(regions_by_band[band_idx], key=lambda rid: (rep_hop(rid), rid))
        for region_local, rid in enumerate(ordered_regions, start=1):
            ordered = sorted(region_sectors[rid], key=lambda s: (core_hops.get(s, _INF), s))
            for ordinal, sid in enumerate(ordered, start=1):
                new_id[sid] = (band_idx + 1) * band_stride + region_local * region_stride + ordinal
    return new_id


def assign_spiral_spatial_ids(sector_ids: Iterable[int]) -> dict[int, int]:
    """Assign the spiral's contiguous display sequence beginning at ``S10001``.

    Unlike the region-gapped IDs used by the clustered topology modes, the spiral
    is itself the wayfinding hierarchy: following increasing display IDs traces
    its guaranteed numerical backbone without a region-prefix discontinuity.
    """
    return {
        sector_id: 10_000 + ordinal
        for ordinal, sector_id in enumerate(sorted(sector_ids), start=1)
    }
