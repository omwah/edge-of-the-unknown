"""edge.bigbang — deterministic universe generation.

Builds the warp graph from `(seed, config)` (DESIGN §5): cluster + bridge passes,
motifs, the Core Space carve, distance bands, population, and validation. Imports
`edge.core` and networkx; networkx is used only to build the graph, which is then
frozen to a plain adjacency dict for runtime.
"""

from __future__ import annotations
