"""Core domain entities (DESIGN §4) — the authoritative in-memory model.

Entities are **frozen** dataclasses: a state mutation replaces an entity with a
new instance rather than editing it in place (the event-sourced style — reducers
in `core.rules` return new entities + events, WP3). The mutable `UniverseState`
container holds these snapshots plus the seeded RNG and the runtime adjacency
map; it is the single owner of randomness, so any game is reproducible from
`(seed, command log)` (CLAUDE.md).

Phase 1 scope: the player ship carries **flat aspect scalars** (no engine-room
subsystems yet — that is Phase 2, §4.1); planets are navigational objects with a
type only (no production/ownership); aliens/alliances beyond a Federation stub
are deferred. See PHASE1_PLAN.md §2.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field

from edge.core.enums import (
    Commodity,
    Component,
    ComponentTier,
    DiscoveryKind,
    PayloadKind,
    PortClass,
    PortMode,
    RarityTier,
    Subsystem,
)


@dataclass(frozen=True, slots=True)
class Game:
    """Top-level game record (DESIGN §4)."""

    id: int
    seed: int
    config_version: int
    created_at: str  # ISO timestamp; set by the caller (no clock reads in core)
    day_number: int = 1
    core_governing_alliance_id: int | None = None
    # Monotonic counter advanced by the `alien_drift` cron (WP16): seeds the drift
    # sub-RNG so movement is deterministic and reproduces under replay, without ever
    # touching the shared command-stream RNG. Rebuilt by re-running crons on reload.
    drift_seq: int = 0


@dataclass(frozen=True, slots=True)
class Region:
    """A named cluster from generation (DESIGN §4/§5)."""

    id: int
    name: str
    controlling_species_id: int | None = None
    controlling_alliance_id: int | None = None


@dataclass(frozen=True, slots=True)
class Sector:
    """A node in the warp graph (DESIGN §4). `warps_out` are sector ids."""

    id: int
    region_id: int
    warps_out: tuple[int, ...]
    distance_band: str  # band name (config §5), e.g. "Hub" / "Frontier"
    is_galactic_core: bool = False  # in the protected Core Space (sectors 1–10)
    beacon_text: str | None = None


@dataclass(frozen=True, slots=True)
class PortCommodity:
    """One commodity line at a port: stock + the pricing inputs (DESIGN §8)."""

    commodity: Commodity
    mode: PortMode  # BUY (port buys from player) / SELL (port sells to player)
    stock: int
    capacity: int  # = size * 1000 (§8)
    base: float  # undisturbed per-unit price (config)
    delta: float  # price swing with stock (config)


@dataclass(frozen=True, slots=True)
class Port:
    """A trading port (DESIGN §4). `latinum` is a soft accounting figure in P1 (§8)."""

    id: int
    sector_id: int
    name: str
    klass: PortClass
    size: int
    commodities: tuple[PortCommodity, ...]
    latinum: int = 0

    def line(self, commodity: Commodity) -> PortCommodity | None:
        return next((c for c in self.commodities if c.commodity is commodity), None)


@dataclass(frozen=True, slots=True)
class Ownership:
    """Three-way planet/base ownership (DESIGN §4.2): none / an alliance / a player.

    `kind` is "none" | "alliance" | "player"; `ref` is the alliance_id or player_id
    (None when unowned). Kept as a small frozen value so the three-way stays explicit
    and hashable (it rides `state_hash` cleanly).
    """

    kind: str = "none"
    ref: int | None = None

    @property
    def is_owned(self) -> bool:
        return self.kind != "none"


UNOWNED = Ownership("none")


@dataclass(frozen=True, slots=True)
class Planet:
    """A planet (DESIGN §4.2): a typed, ownable, producing world.

    `planet_type` fixes colonizability, the `yield_profile` over the trio, and the
    `habitability_cap` (max colonists). `owner` is three-way (§4.2): Core worlds are
    governor-owned, the unowned fraction rises with band. `colonists` settle an owned
    colony and produce into `stores` per `allocation` × `yield_profile` (the §8 cron);
    `inhabited_by_species_id` marks an unaligned-species holding (set in WP7).
    """

    id: int
    sector_id: int
    name: str
    planet_type: str
    owner: Ownership = UNOWNED
    inhabited_by_species_id: int | None = None
    colonists: int = 0
    habitability_cap: int = 0
    yield_profile: Mapping[Commodity, float] = field(default_factory=dict)
    allocation: Mapping[Commodity, float] = field(default_factory=dict)
    stores: Mapping[Commodity, int] = field(default_factory=dict)
    citadel_level: int = 0
    starbase_id: int | None = None  # WP4 orbital base


@dataclass(frozen=True, slots=True)
class InstalledComponent:
    """One component slotted into a subsystem (DESIGN §4.1).

    `knocked_out` is set true by Phase-3 combat (localized damage); in Phase 2 it
    is always false. A knocked-out component contributes nothing to derived aspects
    until a field-patch (`repair_kit`) or StarDock restoration clears it.
    """

    kind: Component
    tier: ComponentTier
    knocked_out: bool = False


@dataclass(frozen=True, slots=True)
class SubsystemState:
    """A fixed-length slot tuple for one subsystem (DESIGN §4.1).

    `slots[i]` is the component in slot `i`, or `None` for an empty slot. The
    `keystone_index` names the structural slot (navigator / burner / secondary / …)
    that anchors the subsystem; emptying it leaves the subsystem unable to function
    (the emergent-derelict / knocked-out logic Phase 3 reads).
    """

    slots: tuple[InstalledComponent | None, ...]
    keystone_index: int | None = None

    @property
    def active(self) -> tuple[InstalledComponent, ...]:
        """Filled, non-knocked-out components (the ones the aspect formula counts)."""
        return tuple(c for c in self.slots if c is not None and not c.knocked_out)


@dataclass(frozen=True, slots=True)
class Starbase:
    """An orbital starbase (DESIGN §4.2): the engine-room model minus mobility.

    A starbase reuses the slotted-subsystem model (`SubsystemState`, §4.1) but
    drops `spindrive`/`thrusters` and gains a `fusion_reactor`; its live subsystems
    are `{fusion_reactor, screens, main_gun}`. **Derelict is emergent, not a flag**
    (§4.2): a base is derelict when broken/missing components leave its reactor
    unable to power itself — see `core.starbases.is_operational`. The big bang makes
    an unowned-world base derelict by stripping/damaging components, leaving a
    salvage cache to cannibalize (WP4); repair (refilling slots) and planetary-system
    defense are Phase 3.
    """

    id: int
    sector_id: int
    planet_id: int
    ship_class_id: str
    owner: Ownership = UNOWNED
    subsystems: Mapping[Subsystem, SubsystemState] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Ship:
    """A ship hull (DESIGN §4).

    A player hull carries `subsystems` (the engine-room model, §4.1): its
    `shields` / `warp_speed` / `combat_speed` / `turns_per_warp` scalars are the
    **derived** values written by the reducers whenever a slot changes (derive-on-
    write, PHASE2_PLAN WP1), so everything downstream keeps reading plain aspects.
    An NPC hull leaves `subsystems = None` and carries flat aspects directly (the
    optional-`subsystems`-block rule, §4.1). `components` is the loose-part
    inventory (not yet installed), conserved across install / cannibalize exactly
    as cargo is conserved across trade.
    """

    id: int
    type_id: str  # ship-class id (config), e.g. "trailblazer"
    name: str
    owner_player_id: int | None
    sector_id: int
    holds_total: int
    cargo: Mapping[Commodity, int] = field(default_factory=dict)
    hull_current: int = 0
    hull_max: int = 0
    shields: int = 0
    warp_speed: int = 0
    combat_speed: int = 0
    cloak_rating: int = 0
    sensor_rating: int = 0
    missiles: int = 0
    repair_kits: int = 0
    turns_per_warp: int = 1
    colonist_capacity: int = 0  # life-support berths (separate occupancy limit, §4.2)
    colonists: int = 0  # recruited colonists aboard (≤ colonist_capacity); not cargo
    subsystems: Mapping[Subsystem, SubsystemState] | None = None
    components: Mapping[tuple[Component, ComponentTier], int] = field(default_factory=dict)
    # Counted special devices keyed by device id (e.g. "genesis_torpedo"); bought at
    # StarDock, deployed by their own command (§4, WP10). Not cargo — no hold cost.
    devices: Mapping[str, int] = field(default_factory=dict)

    @property
    def holds_used(self) -> int:
        """Holds occupied — trade cargo plus loose (uninstalled) components.

        Loose parts ride in the hold (§4.1), so they compete with cargo for space:
        buying or salvaging a component, and trading goods, both draw on the same
        `holds_total`. Installed components sit in subsystem slots and cost no hold.
        """
        used = sum(self.cargo.values())
        if self.components:  # the common (no loose parts) path stays a single sum
            used += sum(self.components.values())
        return used

    @property
    def holds_free(self) -> int:
        return self.holds_total - self.holds_used


@dataclass(frozen=True, slots=True)
class DiscoveryPayload:
    """What collecting a discovery yields (DESIGN §7) — a small tagged value.

    `kind` selects which field matters: COMPONENT uses `component` + `tier` (a loose
    part into the hold); LATINUM uses `latinum`; ARTIFACT uses `barter_tier` (a
    ComponentTier name the WP9 contact screen maps to a barter equivalence); LORE
    carries only the `lore` fragment (codex flavor, no material gain).
    """

    kind: PayloadKind
    component: Component | None = None
    tier: ComponentTier | None = None
    latinum: int = 0
    barter_tier: str | None = None  # ComponentTier name for an artifact's barter value
    lore: str | None = None


@dataclass(frozen=True, slots=True)
class Discovery:
    """A thing the big bang salted into the universe to be found (DESIGN §4, §7).

    Located either in open space (`sector_id` set, `planet_id` None) or on a planet
    surface site (`planet_id` + `site_slot`, revealed by descent in WP6); `sector_id`
    always names the containing sector. `hidden` finds need a sensor check on entry
    (`core.discovery`); obvious phenomena are listed automatically. `rarity_tier`
    drives the band gradient and the payload's value; `found_by` is the player id
    that has collected it (None until logged into the codex).
    """

    id: int
    kind: DiscoveryKind
    rarity_tier: RarityTier
    sector_id: int
    payload: DiscoveryPayload
    planet_id: int | None = None
    site_slot: int = 0
    hidden: bool = False
    found_by: int | None = None


@dataclass(frozen=True, slots=True)
class LocationRef:
    """A pointer to a place of interest an alien may know about (DESIGN §6.7 intel).

    `kind` is "discovery" | "starbase" (the headline tip targets: a rare relic/wreck, or a
    forward base with better hardware); `ref` is the entity id; `sector_id` its containing
    sector. Populated per species **kind** into `UniverseState.species_knowledge` at
    generation, so a friendly alien can volunteer coordinates to somewhere unvisited.
    """

    kind: str
    ref: int
    sector_id: int


@dataclass(frozen=True, slots=True)
class Lead:
    """A coordinate tip the player accepted from an alien (DESIGN §6.7, the "map" mechanic).

    A logged pointer to an as-yet-unvisited place, surfaced on the Computer/Map screen as a
    plottable route. Rides the player's state (and so `state_hash`); it is appended by the
    accept-lead command, so it reconstructs deterministically under `(seed, command log)`.
    """

    kind: str  # "discovery" | "starbase"
    ref: int
    sector_id: int
    origin_sector: int  # sector where the tip was accepted (route-gating, §6.7)
    source_species: str  # roster_id of the alien that shared it
    summary: str  # short human label for the Computer/Map screen


@dataclass(frozen=True, slots=True)
class EncounterFoe:
    """One hostile ship of an encounter pack (DESIGN §10, WP24).

    Stats are resolved at spawn from the species' fleet hull + threat rating (a frozen
    snapshot, so combat rounds are pure over the encounter itself): `damage` is the
    per-round output (weapon + threat bonus), `firing_arc` drives the §10 evasion
    counter-play, `combat_speed` the arc contest. `hull`/`shields` tick down per round.
    """

    ship_class_id: str
    name: str
    hull: int
    hull_max: int
    shields: int
    damage: int
    firing_arc: str  # ahead / all_round / spinal
    combat_speed: int
    defense: int = 0  # summed flat damage reduction (armour/screens/energy_plates)


@dataclass(frozen=True, slots=True)
class Encounter:
    """A live hostile encounter (DESIGN §10, WP24) — hashed core state.

    Set on `Player.active_encounter` when a violence roll opens an encounter; movement
    and docking are rejected while it is live. `player_shields` is the fight-local
    shield pool (shields recover after combat; hull damage persists on the `Ship`).
    Rounds advance via the `CombatAction` command, so a fight replays exactly like a
    trade (H4: every roll draws from `state.rng` inside the reducer).
    """

    species_id: int  # the AlienSpecies instance that intercepted the player
    sector_id: int
    foes: tuple[EncounterFoe, ...]
    round: int = 0
    player_shields: int = 0
    detected: bool = True  # the species' sensors found the player (False never stores)


@dataclass(frozen=True, slots=True)
class LastCombat:
    """The player's most recent combat outcome (DESIGN §4, §6.7) — a replay-safe record.

    Written by the combat reducer whenever an encounter ends, it is the H5 source of
    the situational dialogue facts ("just fled combat") and the WP30 callback facts —
    core state reconstructed by the command log, never UI memory. `species` is the
    pack's kind (`roster_id`); `outcome` is fled / victory / destroyed; `day` the
    game day it ended.
    """

    species: str
    outcome: str
    day: int


@dataclass(frozen=True, slots=True)
class ContactSession:
    """One live conversation visit with an alien (DESIGN §6.7) — the per-contact session.

    `species_id` is the `AlienSpecies` **instance** being spoken to (not the kind — a
    visit is with one ship), `sector_id` where the visit happens. `facts` accumulates
    what happened *this visit* — topics asked (`asked.<context>`), offers taken
    (`traded`), tips logged (`accepted_lead`) — and merges into the dialogue fact
    dictionary (`edge.dialogue.facts`), so authored lines can react to being asked
    the same thing twice or circle back to an earlier beat. Lifetime is structural
    (H1): opened by the conversation reducers, cleared by farewell **and by every
    movement reducer** — the UI is never trusted to close it. Hashed state: a visit
    reconstructs exactly under `(seed, command log)`.
    """

    species_id: int
    sector_id: int
    facts: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Player:
    """The player (DESIGN §4). Starts as a member of the Core's governing alliance."""

    id: int
    name: str
    ship_id: int
    latinum: int
    bank_balance: int = 0
    turns_remaining: int = 0
    alliance_id: int | None = None
    explored_sectors: frozenset[int] = frozenset()
    # For each visited sector, the neighbour the player last arrived from — the
    # breadcrumb that colours the "way back" warp (§11, WP-C).
    entered_from: Mapping[int, int] = field(default_factory=dict)
    # Discovery ids the ship's sensors detected **on entering** their sector (§7).
    # Snapshotted at entry, not recomputed — so a sensor upgrade only reveals more
    # after the player re-enters the sector. Obvious finds need no detection.
    detected: frozenset[int] = frozenset()
    # Discovery ids the player has collected/logged — the codex (§4, §7).
    codex: frozenset[int] = frozenset()
    # Recovered artifact barter-goods, keyed by ComponentTier name (count); the WP9
    # contact screen spends these against alien tech (§8 barter equivalence).
    artifacts: Mapping[str, int] = field(default_factory=dict)
    # Per-species attitude offset (roster_id -> offset), raised by trading/favours
    # (lowered by aggression in Phase 3). Shifts a species' base disposition into its
    # effective disposition (`core.aliens.effective_disposition`, §6). Keyed by the
    # **species kind** (`AlienSpecies.roster_id`), not an individual ship, so every ship
    # of a species shares one standing. Empty until the player deals with a species (WP9).
    species_attitudes: Mapping[str, float] = field(default_factory=dict)
    # Where each species was last encountered (roster_id -> sector_id), stamped at hail
    # time so the dossier records the contact point even after the alien moves on (§6,
    # alien-movement WP). Reconstructs under replay (set by the Hail reducer).
    species_last_seen: Mapping[str, int] = field(default_factory=dict)
    # Dialogue no-repeat ring (DESIGN §6.7): per (species instance key, context) the last K
    # variant indices spoken, so a repeat encounter rephrases rather than replays. Keyed
    # **per contact instance** (`dialogue.instance_key`, WP29/H7) so two ships of one
    # species don't share a "what I already said" ring. Cosmetic but persisted (it rides
    # the command log via contact commands, WP9) so dialogue stays reproducible from
    # (seed, command log).
    dialogue_recency: Mapping[tuple[str, str], tuple[int, ...]] = field(default_factory=dict)
    # Per-port haggle attempts made *today* (port_id -> non-accepted offer count, §8,
    # WP13). Drives the patience/history penalty and the per-day `max_rejections` close;
    # reset by the daily_turn_reset cron, so it reconstructs exactly under replay.
    haggle_attempts: Mapping[int, int] = field(default_factory=dict)
    # Coordinate tips the player has accepted from aliens (DESIGN §6.7 intel) — pointers to
    # unvisited places, plotted on the Computer/Map screen. Appended by the accept-lead
    # command, so the log reconstructs them under replay.
    leads: tuple[Lead, ...] = ()
    # The live hostile encounter, if any (DESIGN §10, WP24): set by the movement reducers'
    # encounter roll, cleared by flee/victory. Movement and docking are rejected while set.
    # Hashed state — a fight reconstructs exactly under (seed, command log).
    active_encounter: Encounter | None = None
    # The live conversation visit, if any (DESIGN §6.7, WP28): opened by the conversation
    # reducers, cleared by farewell and by every movement reducer (H1). Its `facts` feed
    # `DialogueWhen.criteria` via `edge.dialogue.facts` so lines can react to this visit.
    contact_session: ContactSession | None = None
    # The most recent combat outcome (DESIGN §4, WP29): written by the combat reducer at
    # every encounter end — the H5 source of the `just_fled_combat` dialogue fact (§6.7).
    last_combat: LastCombat | None = None
    # Persisted cross-visit dialogue-arc flags (DESIGN §4, §6.7, WP30), keyed by species
    # **kind** (`roster_id` → flag map). Set by authored choice `arc` actions (and, from
    # WP33, signature-mechanic stages); surfaced to selection as `arc.<flag>` facts, so an
    # oath sworn in one visit unlocks branches in the next. Hashed state.
    species_arcs: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    # Active vendettas held **against the player**, keyed by the holder species kind
    # (`roster_id`, so every ship of a species shares the vendetta — DESIGN §4, §6.5).
    # Created by player conduct (WP27), decayed by the daily cron; a permanent grudge
    # (duration -1) also locks the attitude offset (§6.5).
    grudges: Mapping[str, Grudge] = field(default_factory=dict)
    # Alignment (lawfulness: killing friendlies lowers it, hunting hostiles raises it)
    # and experience (kills + discoveries) — the §4 counters Core law and later NPC
    # judgements read (WP27; the morality_judge hook and full Core enforcement, WP33/38).
    alignment: int = 0
    experience: int = 0


@dataclass(frozen=True, slots=True)
class Grudge:
    """A durable, dated grievance (DESIGN §4, §6.5) — the diplomacy layer's memory.

    `holder` / `target` are species kinds (`roster_id`) or the literal `"player"`.
    `severity` (0–1) shifts the greeting-vs-violence roll while active (§10) and
    decays on the daily cron at the holder's `attitude_gain_rate` as the player makes
    amends; `duration_days = -1` marks a `never_forgets` / `betrayal_model=permanent`
    grudge that never decays and locks the attitude offset for good (§6.5).
    """

    holder: str
    target: str
    cause: str
    severity: float
    created_day: int
    duration_days: int  # -1 ⇒ never expires (never_forgets / permanent betrayal)


@dataclass(frozen=True, slots=True)
class Alliance:
    """An alliance / rival bloc (DESIGN §4/§6.3).

    No alliance is privileged in the schema (CLAUDE.md): the **Federation** is just
    an ordinary alliance the default roster names as the initial governor of Core
    Space (`Game.core_governing_alliance_id`), with the player seeded as a member.
    `covets_core` marks a bloc that may seize the Core in Phase 5 (an authored hint;
    inert before then). `banner` is the bloc's flavour tag.
    """

    id: int
    name: str
    banner: str = ""
    covets_core: bool = False


@dataclass(frozen=True, slots=True)
class AlienSpecies:
    """An alien species placed by the big bang (DESIGN §4, §6.1).

    The roster (`config.roster`) is the authored parameter catalogue; this entity is
    one **per-generation** instance: it carries the identity + the small set of params
    Phase 2 reads, plus `base_disposition` — the per-generation draw from the species'
    `disposition_center ± disposition_variance` spread (so stance varies between
    universes, §6). Deeper Phase-3 params (threat / interception / signature mechanic /
    memory / fleet …) and the `dialogue_pack` stay in the roster config, looked up by
    `roster_id`; they ride generation as static config, not per-entity state.

    `base_disposition` is the species' *base* stance toward the player; the player's
    per-species `attitude` offset (raised by trade/favours) shifts it into the
    **effective disposition** that gates greeting-vs-violence and trade (`core.aliens`).
    `sector_id` is the species' contact point — the home-band sector where it is met.
    """

    id: int
    roster_id: str  # key into `config.roster` for the full param set + dialogue
    name: str
    archetype_id: str
    sector_id: int  # contact point (a non-Core sector in `home_band`)
    home_band: str
    tech_level: int
    base_disposition: float  # per-generation draw, clamped to its placement band
    disposition_center: float
    disposition_variance: float
    alliance_id: int | None = None
    alliance_role: str = "none"  # leader / member / aspirant / none (§6.3)
    threat_tier: str = "feeble"  # fearsome / worthy / feeble / special (dossier label)
    trade_posture: str = "open"  # §6.1: open / earn / goods_only / barter / … / refuses
    treaty_mode: str = "open"  # §6.1: open / conditional / prove_intent / … / none
    persona: str = "generic"  # dialogue voice key (§6.7)


@dataclass
class UniverseState:
    """The authoritative mutable container: entities + the seeded RNG + adjacency.

    Not frozen — it owns the evolving `random.Random` and the entity maps. The
    entities it holds are immutable snapshots; mutation swaps a snapshot for a new
    one (reducers, WP3). `adjacency` is the runtime fast-lookup warp map (plain
    dicts per DESIGN §3), projected from the sectors' `warps_out`.
    """

    game: Game
    rng: random.Random
    regions: dict[int, Region] = field(default_factory=dict)
    sectors: dict[int, Sector] = field(default_factory=dict)
    ports: dict[int, Port] = field(default_factory=dict)
    planets: dict[int, Planet] = field(default_factory=dict)
    starbases: dict[int, Starbase] = field(default_factory=dict)
    discoveries: dict[int, Discovery] = field(default_factory=dict)
    ships: dict[int, Ship] = field(default_factory=dict)
    players: dict[int, Player] = field(default_factory=dict)
    alliances: dict[int, Alliance] = field(default_factory=dict)
    species: dict[int, AlienSpecies] = field(default_factory=dict)
    # Inter-species grudges seeded from the roster at the big bang (DESIGN §4, §6.5) —
    # hashed state (they will drive NPC-vs-NPC stances and reputation spillover, WP39).
    # Player-targeted grudges live on `Player.grudges` instead.
    grudges: dict[int, Grudge] = field(default_factory=dict)
    adjacency: dict[int, tuple[int, ...]] = field(default_factory=dict)
    # Hop distance from the Core (sector 1) per sector — a runtime-only cache (like
    # adjacency, excluded from `state_hash`) driving the warp "gravity" arrows (§11).
    core_hops: dict[int, int] = field(default_factory=dict)
    # Internal sector id -> band-monotone spatial *display* id (DESIGN §5.1). A
    # runtime-only cache derived from topology at generation; the internal ids stay
    # authoritative, so this never touches persistence or `state_hash`. Surfaced
    # only at the projection boundary; empty for hand-built (test) states.
    spatial_ids: dict[int, int] = field(default_factory=dict)
    # Internal sector id -> stable 2D layout position (x, y), a seeded force-directed
    # embedding computed once at generation (DESIGN §5.1). A runtime-only cache like
    # `core_hops`/`spatial_ids`: derived from topology, excluded from `state_hash`,
    # never persisted (recomputed on reload), so it drives the direction-aware nav rose
    # (§11) without touching the `(seed, command log)` rail. Empty for hand-built (test)
    # states — the projection then degrades to the `core_hops` gravity axis.
    sector_pos: dict[int, tuple[float, float]] = field(default_factory=dict)
    # Per species **kind** (roster_id), the places of interest that kind knows about and a
    # friendly member may volunteer as a coordinate tip (DESIGN §6.7 intel). A generation-
    # time cache rebuilt by the big bang (like `core_hops`/`spatial_ids`), excluded from
    # `state_hash`; empty for hand-built (test) states until populated.
    species_knowledge: dict[str, tuple[LocationRef, ...]] = field(default_factory=dict)
    # Alliance id -> its home-cluster sectors (DESIGN §5 step 6, §6.3). A generation-time
    # cache rebuilt by the big bang (like `core_hops`/`species_knowledge`), excluded from
    # `state_hash` — the cluster's *effects* (alliance-owned planets, stamped region
    # control, settled members) ride the hashed entities; this is the sector-set index for
    # territory queries and the §5 validator. Empty for hand-built (test) states.
    home_clusters: dict[int, tuple[int, ...]] = field(default_factory=dict)

    @classmethod
    def new(cls, game: Game) -> UniverseState:
        """A fresh universe seeded from the game's seed (RNG owned here, §3)."""
        return cls(game=game, rng=random.Random(game.seed))

    def rebuild_adjacency(self) -> None:
        """Project the runtime adjacency map from the sectors' warp lists."""
        self.adjacency = {s.id: s.warps_out for s in self.sectors.values()}

    def port_in_sector(self, sector_id: int) -> Port | None:
        return next((p for p in self.ports.values() if p.sector_id == sector_id), None)
