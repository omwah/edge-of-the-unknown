"""Frozen active-operation state for ground operations (GW-WP03, GW plan §Hashed state).

Core-level frozen snapshots that ride `Player.ground_operation` — analogous to
`Player.active_encounter`: a surface **survey** expedition or a tactical
**assault**, discriminated by concrete type (`GroundOperation` is their union).
Each stores only *dynamic authoritative* state plus the **generation identity**
(operation seed + snapshotted inputs) needed to regenerate the large immutable
terrain/site layout on replay — those grids are never stored here (G5), so a save
stays the command log, not a dump of every cell.

The per-world `SurveyProgress` (D5) and provenance-bearing `ArtifactRecord` (D10)
persist on the `Player` **outside** the active operation: position/hints survive
between descents, and each excavated artifact keeps its own history rather than
folding into the legacy fungible `Player.artifacts` tier-count map.

Leaf module: imports only the standard library, so `edge.core.models` can import
it without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """A uniquely provenance-bearing surface artifact (GW plan D10).

    Keyed to the `Discovery.id` it was excavated from and never folded into the
    fungible `Player.artifacts` barter-tier count map: it retains rarity, origin
    world/site, lore identity, and a configurable `research_domain` tag so a future
    research or alien-barter system can consume it without losing its history. The
    minimum stable identity here is what GW plan D6/D10 promise old saves.
    """

    discovery_id: int
    origin_planet_id: int
    origin_site: str  # the discovery/site name it came from
    rarity: str  # DiscoveryRarity name
    research_domain: str  # configurable tag for the deferred research path
    lore_key: str  # codex lore identity
    acquired_day: int


@dataclass(frozen=True, slots=True)
class SurveyProgress:
    """Per-player, per-world survey memory that outlives an expedition (GW plan D5).

    `last_x`/`last_y` persist so a later descent resumes where the surveyor stood;
    `hinted_discovery_ids` persist so settlement hints keep narrowing the same
    sites. Trenches and supplies do **not** live here — they reset each descent and
    stay on the active operation. Hashed, because it changes future search
    information.
    """

    last_x: int
    last_y: int
    hinted_discovery_ids: frozenset[int] = frozenset()


@dataclass(frozen=True, slots=True)
class SurveyOperation:
    """A live surface-survey expedition (GW plan D4-D6) — hashed core state.

    Set on `Player.ground_operation`. The immutable terrain and site layout
    regenerate from `seed` + `planet_type` (G5), so only dynamic state lives here.
    `outcome` is `None` while live and set when the operation settles. Movement,
    docking, hailing, combat, and a second ground operation are all rejected while
    it is set (G9); the extract reducer clears it, persisting `explorer_*` and
    `hinted_discovery_ids` into `Player.ground_survey_progress` while supplies and
    dug trenches reset. Full site generation and the action commands land in
    GW-WP05/06 — the collection fields start empty here.
    """

    operation_id: int
    planet_id: int
    sector_id: int
    planet_type: str
    seed: int  # drawn from state.rng in the begin reducer (G3)
    started_day: int
    explorer_x: int
    explorer_y: int
    supplies: int
    local_turn: int = 0
    visible_discovery_ids: frozenset[int] = frozenset()
    resolved_discovery_ids: frozenset[int] = frozenset()
    hinted_discovery_ids: frozenset[int] = frozenset()
    dug_cells: frozenset[tuple[int, int]] = frozenset()
    outcome: str | None = None
    kind: Literal["survey"] = "survey"


@dataclass(frozen=True, slots=True)
class AssaultOperation:
    """A live tactical assault (GW plan D7-D11) — hashed core state.

    Set on `Player.ground_operation`. Like `SurveyOperation`, the battlefield/city
    layout regenerates from `seed` + `planet_type` (G5); only dynamic state lives
    here. The full platoon/structure/garrison/city dynamic state and the tactical
    action commands land in GW-WP08-11 — this skeleton establishes the state epoch
    and the shared begin/extract lifetime, carrying the retrieval clock and Resolve
    an assault settles against.
    """

    operation_id: int
    planet_id: int
    sector_id: int
    planet_type: str
    seed: int  # drawn from state.rng in the begin reducer (G3)
    started_day: int
    resolve: int
    retrieval_turn: int
    local_turn: int = 0
    casualties: int = 0
    outcome: str | None = None
    kind: Literal["assault"] = "assault"


# The active ground operation on `Player.ground_operation`, discriminated by type
# (and by the `kind` tag for the codec/DTO). At most one is live per player (G9).
GroundOperation = SurveyOperation | AssaultOperation
