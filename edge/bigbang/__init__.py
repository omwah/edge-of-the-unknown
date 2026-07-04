"""edge.bigbang — deterministic universe generation.

Builds the warp graph from `(seed, config)` (DESIGN §5): cluster + bridge passes,
motifs, the Core Space carve, distance bands, population, and validation. Pure
`edge.core` + stdlib — the graph is plain adjacency dicts (no networkx), kept
`mypy --strict`-clean and frozen for runtime.
"""

from __future__ import annotations
