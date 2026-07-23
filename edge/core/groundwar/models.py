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

from collections.abc import Mapping
from dataclasses import dataclass, field
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

    `map_seed` is the per-player/per-world generation identity: the first descent
    draws it from the authoritative game RNG and every later descent reuses it, so
    returning to a planet cannot redraw its terrain or move known sites.
    `last_x`/`last_y` persist so a later descent resumes where the surveyor stood;
    `hinted_discovery_ids` persist so settlement hints keep narrowing the same
    sites. Trenches and supplies do **not** live here — they reset each descent and
    stay on the active operation. Hashed, because it changes future search
    information.
    """

    last_x: int
    last_y: int
    hinted_discovery_ids: frozenset[int] = frozenset()
    map_seed: int = 0


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
    # The shuttle holds in the upper atmosphere until the player picks a drop site: while
    # `landed` is False, `explorer_*` is only the *suggested* cursor rest, not a position,
    # and marching/digging/talking are refused. Every descent chooses afresh (a remembered
    # position seeds the cursor rather than skipping the choice).
    landed: bool = False
    outcome: str | None = None
    kind: Literal["survey"] = "survey"


@dataclass(frozen=True, slots=True)
class AssaultTrooper:
    """One deployed platoon member — hashed core state (GW-WP10).

    Rides `AssaultOperation.platoon`. Dead troopers (`hp <= 0`) are **kept**, not
    pruned: GW-WP11 needs each casualty's `suit_id` to settle
    `Ship.suits`/`Ship.recruits` losses (`gw_force.apply_casualties`), which only a
    per-suit-class breakdown can drive, not a bare headcount. `suit_id` names the
    config-keyed `GwSuit` rather than embedding suit stats, so a config edit
    between saves still resolves consistently at replay.
    """

    id: int
    suit_id: str
    name: str
    x: int
    y: int
    hp: int
    missiles: int
    jump_charges: int
    mp: int = 0
    actions: int = 0
    fired: bool = False
    detected: bool = False


@dataclass(frozen=True, slots=True)
class AssaultGarrisonUnit:
    """One live tactical ground defender — hashed core state (GW-WP10).

    Rides `AssaultOperation.garrison_units`, whether pre-placed in a city at drop
    or spawned by an escalating sortie. Unlike `AssaultTrooper`, dead units are
    **dropped** here — GW-WP11 only needs the surviving-defender headcount
    (`infantry_remaining`/`armor_remaining`), never a specific unit's identity.
    """

    id: int
    kind: Literal["infantry", "armor"]
    x: int
    y: int
    hp: int
    city_id: int


@dataclass(frozen=True, slots=True)
class AssaultOperation:
    """A live tactical assault (GW plan D7-D11) — hashed core state.

    Set on `Player.ground_operation`. Like `SurveyOperation`, the battlefield/city
    layout regenerates from `seed` + `planet_type` (G5); only dynamic state lives
    here. The full platoon/structure/city dynamic state and the tactical action
    commands land in GW-WP10-11 — this skeleton establishes the state epoch and the
    shared begin/extract lifetime, carrying the retrieval clock and Resolve an
    assault settles against, plus (GW-WP09) the live-derived difficulty and the
    ground-defender reserve `BeginAssault` snapshots at open: `cities`/
    `citadel_level`/`surrender_threshold` feed `generate_assault_map`/Resolve, and
    `reserved_infantry`/`reserved_armor` are the planet's garrison headcount at the
    moment of opening — frozen so a later build/downgrade can't retroactively
    reshape an already-open battlefield, and so WP11 has an immutable number to
    settle against. `Planet.garrison_infantry`/`garrison_armor` are themselves
    untouched by `BeginAssault` — nothing is spent until WP11 ships.
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
    cities: int = 0  # snapshotted city count fed to generate_assault_map at begin (GW-WP09)
    citadel_level: int = 0  # snapshotted planet.citadel_level at begin (GW-WP09)
    surrender_threshold: int = 0  # snapshotted derived difficulty (GW-WP09)
    reserved_infantry: int = 0  # planet.garrison_infantry at begin — WP11 settles against this
    reserved_armor: int = 0  # planet.garrison_armor at begin
    outcome: str | None = None
    kind: Literal["assault"] = "assault"
    # --- live tactical state (GW-WP10) ---
    # `dropped` mirrors `SurveyOperation.landed`: False while the platoon has not yet
    # touched down (only `GroundDrop`/`ExtractGroundOperation` are legal before it flips).
    dropped: bool = False
    platoon: tuple[AssaultTrooper, ...] = ()
    garrison_units: tuple[AssaultGarrisonUnit, ...] = ()
    # Sparse damage overlay on the regenerated, frozen `AssaultMap.structures` (G5) — a
    # structure id absent here is at its generated `hp_max`, mirroring how
    # `SurveyOperation.dug_cells`/`resolved_discovery_ids` overlay the frozen `SurveyMap`.
    structure_hp: Mapping[int, int] = field(default_factory=dict)
    broadcast_cities: frozenset[int] = frozenset()
    cowed_cities: frozenset[int] = frozenset()
    # The finite garrison pool remaining to feed sorties, after `GroundDrop` pre-places a
    # config-fractional share of `reserved_infantry`/`reserved_armor` into the cities.
    infantry_remaining: int = 0
    armor_remaining: int = 0
    # Id counter for units minted after map generation (troopers, pre-placed/sortied garrison);
    # seeded above the regenerated map's structure id range at `GroundDrop` so dynamic ids never
    # collide with static structure ids within one operation's lifetime.
    next_unit_id: int = 1
    initial_strength: int = 0  # platoon size at drop — the casualty-ceiling/wipe denominator
    # Actual shared-magazine rounds loaded into the dropped suits. Settlement debits
    # this commitment and returns only unused rounds carried by surviving troopers.
    ground_missiles_committed: int = 0


# The active ground operation on `Player.ground_operation`, discriminated by type
# (and by the `kind` tag for the codec/DTO). At most one is live per player (G9).
GroundOperation = SurveyOperation | AssaultOperation
