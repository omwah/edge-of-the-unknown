"""Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.

DESIGN §5.1. Assigns every sector a stable ``(x, y)`` so the main-screen nav rose
(§11) can place a sector's immediate neighbours by real *bearing* rather than the
single core-distance scalar the gravity arrows expose. A **radial tree fan**,
computed once at generation:

- ``radius`` = the sector's hop distance from the Core, so ``core_hops``'s in/out
  intuition is preserved and sector 1 (the Core anchor) sits at the origin;
- ``angle`` from a balanced BFS-tree fan — each sub-branch owns an angular wedge
  sized by its leaf count — so sibling warps that lead into *different*
  sub-regions get distinct bearings (the whole point: two "deeper" exits are no
  longer identical).

Deliberately **not** ``nx.spring_layout``: ``bigbang`` is ``mypy --strict`` and
networkx ships no stubs, and spring_layout drags in scipy (DESIGN §15 keeps scipy
dev-only, in ``render.py``). A force-directed relaxation is also O(n²) per
iteration — prohibitive for a 1000-sector universe generated interactively and
re-run on every golden-master ``rebuild`` — whereas this fan is a single O(n)
pass. The result is a runtime cache **excluded from ``state_hash``**, so any float
variation never touches ``(seed, command log)`` replay; at worst the picture shifts.

Uses only its own ``random.Random(seed)`` for tie-break jitter — never the game
command-stream RNG (the §3 determinism rail).
"""

from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Iterable, Mapping

Pos = tuple[float, float]

_ROOT = 1  # the Core anchor (sector 1); pinned to the origin so "bearing to Core" is global


def compute_embedding(
    adjacency: Mapping[int, Iterable[int]],
    core_hops: Mapping[int, int],
    *,
    seed: int,
    jitter: float = 0.18,
) -> dict[int, Pos]:
    """A stable radial 2D position per sector, fanned out from the Core.

    ``radius`` is the sector's Core hop distance (sector 1 → origin); ``angle``
    comes from a balanced fan over the BFS tree so branches spread around the
    circle. Deterministic in ``seed`` (jitter only) and independent of the game
    RNG. Returns ``{}`` for an empty graph.
    """
    order, parent, children, depth = _bfs_tree(adjacency, _ROOT)
    if not order:
        return {}
    weight = _leaf_weights(order, children)
    # Fan the tree: the root owns the full circle; each node splits its wedge among
    # its children proportional to their leaf weight, and sits at the wedge centre.
    span: dict[int, tuple[float, float]] = {_ROOT: (0.0, 2.0 * math.pi)}
    base_angle: dict[int, float] = {}
    for node in order:
        lo, hi = span[node]
        base_angle[node] = (lo + hi) / 2.0
        kids = children.get(node, ())
        total = sum(weight[k] for k in kids) or 1
        cursor = lo
        for kid in kids:
            nxt = cursor + (hi - lo) * (weight[kid] / total)
            span[kid] = (cursor, nxt)
            cursor = nxt

    # Lattice correction (§5.1): the single-parent tree fan is blind to the
    # cross-links `expansive` mode adds, so a node bearings its own fan slot *and*
    # the (already-refined) angles of **all its min-hop parents** — the circular
    # mean pulls a lattice node toward the centroid of its inner neighbours while
    # the own-slot term keeps sibling wedges distinct (a chain stays radial). BFS
    # order guarantees parents are refined first. One extra O(n·deg) pass, stdlib.
    angle: dict[int, float] = {}
    for node in order:
        cos_sum = math.cos(base_angle[node])
        sin_sum = math.sin(base_angle[node])
        hop = core_hops.get(node, depth[node])
        for nbr in adjacency.get(node, ()):
            if core_hops.get(nbr, depth.get(nbr, hop)) == hop - 1:  # a min-hop parent
                cos_sum += math.cos(angle[nbr])
                sin_sum += math.sin(angle[nbr])
        angle[node] = math.atan2(sin_sum, cos_sum) if (cos_sum or sin_sum) else base_angle[node]

    rng = random.Random(seed)
    pos: dict[int, Pos] = {}
    for node in order:
        radius = float(core_hops.get(node, depth[node]))
        theta = angle[node]
        # A small deterministic jitter breaks exactly-collinear ties (e.g. two
        # single-child chains sharing a wedge centre) without disturbing the fan.
        jx = (rng.random() - 0.5) * jitter
        jy = (rng.random() - 0.5) * jitter
        pos[node] = (radius * math.cos(theta) + jx, radius * math.sin(theta) + jy)
    pos[_ROOT] = (0.0, 0.0)  # pin the Core exactly at the origin
    return pos


def bearing(pos: Mapping[int, Pos], src: int, dst: int) -> float:
    """Direction from sector ``src`` to ``dst`` in radians (``atan2``).

    Returns ``0.0`` when either sector lacks a position or they coincide, so the
    projection degrades cleanly for hand-built (test) states with no embedding.
    """
    if src not in pos or dst not in pos:
        return 0.0
    (ax, ay), (bx, by) = pos[src], pos[dst]
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.atan2(dy, dx)


def _bfs_tree(
    adjacency: Mapping[int, Iterable[int]], root: int,
) -> tuple[list[int], dict[int, int | None], dict[int, list[int]], dict[int, int]]:
    """BFS from ``root`` over out-edges → (visit order, parent, children, depth).

    Neighbours are visited in sorted order so the fan is deterministic. Mirrors the
    ``bfs_distances(out, 1)`` that builds ``core_hops``, so radii and the tree agree.
    """
    order: list[int] = []
    parent: dict[int, int | None] = {root: None}
    children: dict[int, list[int]] = {}
    depth: dict[int, int] = {root: 0}
    seen = {root}
    queue: deque[int] = deque([root])
    while queue:
        cur = queue.popleft()
        order.append(cur)
        for nxt in sorted(adjacency.get(cur, ())):
            if nxt not in seen:
                seen.add(nxt)
                parent[nxt] = cur
                depth[nxt] = depth[cur] + 1
                children.setdefault(cur, []).append(nxt)
                queue.append(nxt)
    return order, parent, children, depth


def _leaf_weights(order: list[int], children: Mapping[int, list[int]]) -> dict[int, int]:
    """Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.

    Processed in reverse BFS order, so every child is weighed before its parent.
    """
    weight: dict[int, int] = {}
    for node in reversed(order):
        kids = children.get(node, ())
        weight[node] = sum(weight[k] for k in kids) or 1
    return weight
