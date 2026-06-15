"""edge.core — the pure rules engine.

No I/O, no async, no Textual imports (CLAUDE.md architecture rules). Everything
here is deterministic and unit/property-testable in isolation: domain models,
the economy, movement, the command→event reducers, and the typed config schema.
All randomness flows through a seeded `random.Random` owned by game state.
"""

from __future__ import annotations
