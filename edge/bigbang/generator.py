"""The big bang: deterministic universe generation from (seed, config) (DESIGN §5).

Pipeline (Phase-1 subset): carve the Core, cluster the rest, bridge the groups
(a bidirectional spanning tree guarantees reachability, then extra/one-way
bridges add texture), a light ring-motif pass, distance bands, populate, and
validate — regenerating with a perturbed sub-seed on failure.

Two RNGs, deliberately separate: a *build* RNG `Random((seed, attempt))` drives
generation (so retries are deterministic), while the runtime `UniverseState.rng`
is `Random(seed)` and is left untouched here — gameplay randomness advances only
through the command log, keeping `(seed, command log)` replay exact (§3).
"""

from __future__ import annotations

import math
import random

from edge.bigbang import populate as _populate
from edge.bigbang import validate as _validate
from edge.bigbang.aliens import HomeClusterError, populate_species
from edge.bigbang.discoveries import salt_discoveries
from edge.bigbang.embedding import compute_embedding
from edge.bigbang.naming import NameGenerator
from edge.bigbang.numbering import assign_spatial_ids
from edge.bigbang.topology import (
    OutEdges,
    add_bidirectional,
    add_directed,
    add_ring_motifs,
    bfs_distances,
    carve_core,
    compute_bands,
)
from edge.core.config import BigBangConfig, GameConfig
from edge.core.enums import PortClass
from edge.core.models import Game, Region, Sector, UniverseState
from edge.dialogue.intel import build_species_knowledge

_MAX_ATTEMPTS = 16


class BigBangError(Exception):
    """Generation failed validation after the bounded retries."""


def _cluster_groups(sectors: list[int], cfg: BigBangConfig, rng: random.Random) -> list[list[int]]:
    """Partition `sectors` into contiguous groups of size [cluster_min, cluster_max]."""
    groups: list[list[int]] = []
    i = 0
    n = len(sectors)
    while i < n:
        size = rng.randint(cfg.cluster_min, cfg.cluster_max)
        group = sectors[i : i + size]
        # Fold a too-small trailing remainder into the previous group.
        if len(group) < cfg.cluster_min and groups:
            groups[-1].extend(group)
        else:
            groups.append(group)
        i += size
    return groups


def _connect_group(out: OutEdges, group: list[int], cfg: BigBangConfig, rng: random.Random) -> None:
    """Wire one group: a random spanning tree, then edges toward avg degree ~2.5."""
    cap = cfg.max_warps_per_sector
    if len(group) < 2:
        return
    order = group[:]
    rng.shuffle(order)
    for idx in range(1, len(order)):
        add_bidirectional(out, order[idx], rng.choice(order[:idx]), cap)
    target_edges = int(cfg.intra_group_degree * len(group) / 2)
    current = sum(len(out[s] & set(group)) for s in group) // 2
    attempts = 0
    while current < target_edges and attempts < target_edges * 4:
        a, b = rng.sample(group, 2)
        if add_bidirectional(out, a, b, cap):
            current += 1
        attempts += 1


def _bridge_groups_trunk(out: OutEdges, groups: list[list[int]], cfg: BigBangConfig, rng: random.Random) -> None:
    """`trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra
    (maybe one-way) bridges. A group spanning tree rooted at the Core funnels
    outer-band traffic through the few tree bridges — the trunk-and-branches
    universe of chokepoints (the original, byte-identical algorithm)."""
    cap = cfg.max_warps_per_sector

    def _bridge(g1: list[int], g2: list[int], one_way: bool) -> None:
        for _ in range(6):  # a few member-pair tries in case of cap saturation
            a, b = rng.choice(g1), rng.choice(g2)
            ok = add_directed(out, a, b, cap) if one_way else add_bidirectional(out, a, b, cap)
            if ok:
                return

    # Spanning tree: each group links to a random earlier one (two-way) -> all
    # groups (incl. the core at index 0) mutually reachable.
    for i in range(1, len(groups)):
        _bridge(groups[i], groups[rng.randrange(i)], one_way=False)
    # Extra bridges per group for texture; some directional.
    for i, group in enumerate(groups):
        extra = rng.randint(cfg.bridges_min, cfg.bridges_max) - 1
        for _ in range(max(0, extra)):
            j = rng.randrange(len(groups))
            if j != i:
                _bridge(group, groups[j], one_way=rng.random() < cfg.one_way_chance)


def _bridge_groups_expansive(out: OutEdges, groups: list[list[int]], cfg: BigBangConfig, rng: random.Random) -> None:
    """`expansive` bridging (§5 step 2): a band-lattice web with no chokepoints.

    Stratify the groups into concentric rings (the Core is ring 0), then build:
      * a **ring road** — each ring's groups wired into a cycle, so a band can be
        circled without diving back toward the Core (lateral 2-edge-connectivity);
      * **≥2 radial spokes** between each consecutive ring pair, on distinct outer
        groups, so the rings are radially 2-edge-connected too.
    Cycles-plus-two-spokes make the whole graph **bridgeless**: no single
    inter-region warp is a cut edge, so every group keeps two edge-disjoint paths
    to the Core. Spoke demand is only ~2 per ring boundary (not per group), so the
    10-sector Core is never swamped — the failure mode of a per-group inward rule.
    Ring membership is seeded (a shuffle) so the shape varies per seed.
    """
    cap = cfg.max_warps_per_sector
    if len(groups) < 2:
        return

    def _link(gi: int, gj: int, one_way: bool = False) -> bool:
        # Bridge two groups, preferring member sectors with the most spare degree
        # (a shuffle gives seeded variety among equally-spare endpoints; the stable
        # sort preserves it) so no single sector saturates.
        if gi == gj:
            return False
        a_opts = sorted(groups[gi], key=lambda s: len(out[s]))
        b_opts = sorted(groups[gj], key=lambda s: len(out[s]))
        for a in a_opts:
            for b in b_opts:
                ok = add_directed(out, a, b, cap) if one_way else add_bidirectional(out, a, b, cap)
                if ok:
                    return True
        return False

    non_core = list(range(1, len(groups)))
    rng.shuffle(non_core)
    ring_width = max(2, math.isqrt(len(non_core)))
    rings: list[list[int]] = [[0]]  # ring 0 is the Core group
    for start in range(0, len(non_core), ring_width):
        rings.append(non_core[start : start + ring_width])

    # Ring roads: wire each ring's groups into a cycle (a 2-group ring is a single
    # link — its redundancy comes from the spokes below).
    for ring in rings:
        k = len(ring)
        if k >= 2:
            for idx in range(k):
                _link(ring[idx], ring[(idx + 1) % k])

    # Radial spokes: ≥2 bridges between each consecutive ring pair, spread across
    # distinct outer groups so no single group becomes a radial cut vertex.
    for r in range(1, len(rings)):
        inner, outer = rings[r - 1], rings[r]
        outer_order = outer[:]
        rng.shuffle(outer_order)
        made = attempts = 0
        while made < 2 and attempts < 16:
            gi = outer_order[made % len(outer_order)]
            if _link(gi, rng.choice(inner)):
                made += 1
            attempts += 1

    # Extra chords/one-ways: a little richer routing within the larger rings.
    for ring in rings:
        if len(ring) >= 3:
            for _ in range(rng.randint(0, 2)):
                gi, gj = rng.sample(ring, 2)
                _link(gi, gj, one_way=rng.random() < cfg.one_way_chance)


def build_graph(cfg: BigBangConfig, rng: random.Random) -> tuple[OutEdges, list[list[int]]]:
    """Build the warp graph and return its adjacency plus the region groups."""
    n = cfg.sector_count
    cap = cfg.max_warps_per_sector
    out: OutEdges = {sid: set() for sid in range(1, n + 1)}

    core = list(range(1, cfg.core_sector_count + 1))
    carve_core(out, core, rng, cap)
    other = _cluster_groups(list(range(cfg.core_sector_count + 1, n + 1)), cfg, rng)
    groups = [core, *other]
    for group in other:
        _connect_group(out, group, cfg, rng)
    if cfg.topology_mode == "expansive":
        _bridge_groups_expansive(out, groups, cfg, rng)
    else:
        _bridge_groups_trunk(out, groups, cfg, rng)
    add_ring_motifs(out, groups, rng, cap, count=max(1, n // 50))
    return out, groups


def generate(config: GameConfig, seed: int, *, created_at: str = "1970-01-01T00:00:00Z") -> UniverseState:
    """Generate a validated universe from `(seed, config)`; raise on repeated failure."""
    cfg = config.bigbang
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        build_rng = random.Random(f"{seed}-{attempt}")  # str seed: deterministic, typed
        out, groups = build_graph(cfg, build_rng)
        active_bands = cfg.active_bands()  # per-mode hop thresholds (§5 step 5)
        bands = compute_bands(out, 1, active_bands)

        gov = config.roster.core_governing_alliance_id if config.roster else 1
        game = Game(
            id=1, seed=seed, config_version=config.config_version,
            created_at=created_at, core_governing_alliance_id=gov,
        )
        state = UniverseState.new(game)  # runtime rng = Random(seed), left untouched

        sector_to_region = {sid: gi + 1 for gi, group in enumerate(groups) for sid in group}
        core_ids = set(range(1, cfg.core_sector_count + 1))
        
        names_cfg = config.names
        region_gen = NameGenerator(names_cfg.regions if names_cfg else None, "Region", build_rng)
        
        state.regions = {
            gi + 1: Region(id=gi + 1, name=region_gen.draw())
            for gi in range(len(groups))
        }
        state.sectors = {
            sid: Sector(
                id=sid,
                region_id=sector_to_region[sid],
                warps_out=tuple(sorted(out[sid])),
                distance_band=bands.get(sid, active_bands[-1].name),
                is_galactic_core=sid in core_ids,
            )
            for sid in out
        }
        state.rebuild_adjacency()
        state.core_hops = bfs_distances(out, 1)  # gravity-arrow cache (§11, WP-C)
        state.spatial_ids = assign_spatial_ids(groups, state.core_hops, active_bands)  # §5.1 display ids
        state.sector_pos = compute_embedding(out, state.core_hops, seed=seed)  # §5.1 nav-rose layout

        _populate.populate(state, config, build_rng)
        salt_discoveries(state, config, attempt)  # §7 finds on an independent sub-RNG

        try:
            populate_species(state, config)  # §6 aliens + home clusters on an independent sub-RNG
            # §6.7 intel: give each species kind the places it can tip the player toward.
            state.species_knowledge = build_species_knowledge(state, seed)
            _validate.validate(state, config)
        except (_validate.ValidationError, HomeClusterError) as exc:
            last_error = exc
            continue
        return state

    raise BigBangError(f"big bang failed validation after {_MAX_ATTEMPTS} attempts: {last_error}")


def summarize(state: UniverseState) -> str:
    """A text report of a generated universe (the `--inspect` dev view, §5)."""
    from collections import Counter

    bands = Counter(s.distance_band for s in state.sectors.values())
    classes = Counter(p.klass.name for p in state.ports.values())
    dock = next((p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)
    degrees = [len(s.warps_out) for s in state.sectors.values()]
    lines = [
        f"seed={state.game.seed}  sectors={len(state.sectors)}  regions={len(state.regions)}",
        f"ports={len(state.ports)}  planets={len(state.planets)}  "
        f"max_warps={max(degrees) if degrees else 0}",
        "bands:        " + ", ".join(f"{b}={n}" for b, n in sorted(bands.items())),
        "port classes: " + ", ".join(f"{c}={n}" for c, n in sorted(classes.items())),
        f"stardock:     sector {dock.sector_id}" if dock else "stardock:     MISSING",
    ]
    return "\n".join(lines)
