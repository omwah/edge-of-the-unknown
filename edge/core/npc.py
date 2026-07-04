"""Goal-directed NPC movement policies (DESIGN §8/§10, WP42) — pure core.

Replaces the Phase-2 pure-random drift with per-species **movement policies**. Each is a
deterministic planner: given the *already legality-filtered* legal candidate sectors (the
cron applies `may_occupy`, H8), a policy picks the next sector, drawing from the passed
drift sub-RNG exactly once (so the command-stream draw discipline is preserved and a
`wander` species stays byte-identical with the old `rng.choice(legal)`).

Policies (`SpeciesConfig.movement_policy`):

- **wander** — uniform random (the default; unchanged behaviour).
- **patrol** — hug the home band: prefer candidates in the species' `home_band`.
- **trade_seek** — drift toward the nearest port (the trade lanes).
- **hunt** — pursue the nearest player the species holds a grudge against; else wander.
- **coward** — flee the nearest player (maximise distance).

Distance is a multi-source BFS over the runtime adjacency (stdlib, pure). Ties are broken
by the single RNG draw, so hunters converge and cowards diverge deterministically.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Mapping, Sequence

from edge.core.config import GameConfig
from edge.core.models import AlienSpecies, UniverseState


def movement_policy(config: GameConfig, sp: AlienSpecies) -> str:
    """The species' authored movement policy (`wander` if none / no roster)."""
    if config.roster is None:
        return "wander"
    sc = config.roster.species_by_id(sp.roster_id)
    return sc.movement_policy if sc is not None else "wander"


def _bfs_from(adjacency: Mapping[int, Sequence[int]], sources: Sequence[int]) -> dict[int, int]:
    """Hop distance from the nearest `sources` node to every reachable sector (BFS)."""
    dist: dict[int, int] = {s: 0 for s in sources}
    queue: deque[int] = deque(sources)
    while queue:
        node = queue.popleft()
        for nxt in adjacency.get(node, ()):
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
    return dist


def _pick_by_distance(
    legal: list[int], dist: Mapping[int, int], rng: random.Random, *, maximize: bool
) -> int:
    """Pick the candidate nearest (or farthest, if `maximize`) a target set.

    Unreachable candidates are treated as infinitely far — deprioritised when seeking,
    preferred when fleeing. Ties break on the single RNG draw (so the stream stays in
    lockstep with `rng.choice(legal)`).
    """
    inf = len(dist) + 1
    scored = [(dist.get(n, inf), n) for n in legal]
    target = max(d for d, _ in scored) if maximize else min(d for d, _ in scored)
    pool = [n for d, n in scored if d == target]
    return rng.choice(pool)


def _player_sectors(state: UniverseState) -> list[int]:
    return sorted({state.ships[p.ship_id].sector_id
                   for p in state.players.values() if p.ship_id in state.ships})


def _port_sectors(state: UniverseState) -> list[int]:
    return sorted({p.sector_id for p in state.ports.values()})


def _grudge_targets(state: UniverseState, sp: AlienSpecies) -> list[int]:
    """The sectors of players the species holds an active grudge against (§6.5)."""
    targets: list[int] = []
    for player in state.players.values():
        if sp.roster_id in player.grudges and player.ship_id in state.ships:
            targets.append(state.ships[player.ship_id].sector_id)
    return sorted(set(targets))


def plan_move(
    state: UniverseState, sp: AlienSpecies, legal: list[int],
    config: GameConfig, rng: random.Random,
) -> int:
    """Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42).

    `legal` is already `may_occupy`-filtered and non-empty; exactly one RNG draw is made.
    """
    policy = movement_policy(config, sp)
    if policy == "wander":
        return rng.choice(legal)
    if policy == "patrol":
        preferred = [n for n in legal if state.sectors[n].distance_band == sp.home_band]
        return rng.choice(preferred or legal)
    if policy == "trade_seek":
        dist = _bfs_from(state.adjacency, _port_sectors(state))
        return _pick_by_distance(legal, dist, rng, maximize=False)
    if policy == "hunt":
        targets = _grudge_targets(state, sp)
        if not targets:
            return rng.choice(legal)  # nothing to hunt — drift
        dist = _bfs_from(state.adjacency, targets)
        return _pick_by_distance(legal, dist, rng, maximize=False)
    if policy == "coward":
        targets = _player_sectors(state)
        if not targets:
            return rng.choice(legal)
        dist = _bfs_from(state.adjacency, targets)
        return _pick_by_distance(legal, dist, rng, maximize=True)
    return rng.choice(legal)
