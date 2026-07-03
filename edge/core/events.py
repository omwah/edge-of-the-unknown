"""Immutable event facts — the durable rail (DESIGN §3, §12).

Reducers in `core.rules` return events describing what happened; the store
appends them to the `event_log` (assigning the monotonic id/tick) and the engine
tick loop consumes the same log. Events carry only their semantic payload — no
ids/timestamps, which the store layer assigns. Replaying the command log against
a fixed seed reproduces the same events (the save-integrity / golden-master rail).
"""

from __future__ import annotations

from dataclasses import dataclass

from edge.core.enums import Commodity, PortMode


@dataclass(frozen=True)
class Event:
    """Base class for all event facts."""


@dataclass(frozen=True)
class DevApplied(Event):
    """A dev/testing `DevPatch` mutated the player (see `core.dev`).

    `detail` is a human summary (prefixed `[dev]`). Deliberately has no
    `format_log_line` case, so it stays invisible in the in-game message log —
    it is an audit marker on the event rail, not player-facing.
    """

    player_id: int
    detail: str


@dataclass(frozen=True)
class Warped(Event):
    player_id: int
    from_sector: int
    to_sector: int
    turn_cost: int
    # True when the traversed warp has no reverse edge — there is no *direct* warp
    # back (the way home runs through other sectors). Drives a one-way heads-up in
    # the log/ticker (§9). Defaulted so older persisted logs decode unchanged.
    one_way: bool = False


@dataclass(frozen=True)
class Docked(Event):
    player_id: int
    sector_id: int
    port_id: int


@dataclass(frozen=True)
class Traded(Event):
    player_id: int
    port_id: int
    commodity: Commodity
    mode: PortMode  # the port's mode for this commodity
    units: int
    unit_price: int
    total: int


@dataclass(frozen=True)
class Haggled(Event):
    player_id: int
    port_id: int
    commodity: Commodity
    status: str  # HaggleStatus value
    price: int | None


@dataclass(frozen=True)
class Banked(Event):
    player_id: int
    kind: str  # "deposit" | "withdraw" | "interest"
    amount: int
    balance: int  # resulting bank balance


@dataclass(frozen=True)
class ComponentPurchased(Event):
    player_id: int
    component: str  # Component value
    tier: str  # ComponentTier name
    cost: int


@dataclass(frozen=True)
class ShipPurchased(Event):
    player_id: int
    ship_class_id: str
    cost: int  # net latinum spent (price − trade-in credit)
    trade_in: int  # trade-in credit applied


@dataclass(frozen=True)
class ComponentInstalled(Event):
    player_id: int
    subsystem: str  # Subsystem value
    slot_index: int
    component: str  # Component value
    tier: str  # ComponentTier name (I/II/III)


@dataclass(frozen=True)
class ComponentRemoved(Event):
    player_id: int
    subsystem: str
    slot_index: int
    component: str
    tier: str


@dataclass(frozen=True)
class Repaired(Event):
    player_id: int
    subsystem: str
    slot_index: int


@dataclass(frozen=True)
class DiscoveryDetected(Event):
    """A hidden discovery a ship's sensors picked out on entering its sector (§7, WP5)."""

    player_id: int
    discovery_id: int
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name


@dataclass(frozen=True)
class DevicePurchased(Event):
    """A special device bought at StarDock (§4, WP10), e.g. a genesis torpedo."""

    player_id: int
    device_id: str
    cost: int


@dataclass(frozen=True)
class GenesisDeployed(Event):
    """A Genesis torpedo terraformed a planet to a new type (§4.2, WP10)."""

    player_id: int
    planet_id: int
    new_type: str  # the planet_type the world became


@dataclass(frozen=True)
class Descended(Event):
    """The player landed on a planet surface to explore its sites (§7, WP6)."""

    player_id: int
    planet_id: int


@dataclass(frozen=True)
class SiteExplored(Event):
    """A surface site revealed by exploration/sensor sweep on descent (§7, WP6)."""

    player_id: int
    planet_id: int
    discovery_id: int
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name


@dataclass(frozen=True)
class DiscoveryCollected(Event):
    """A discovery logged into the codex, its payload taken aboard (§7, WP5)."""

    player_id: int
    discovery_id: int
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name
    payload: str  # PayloadKind value (what was gained)
    reward: str = ""  # human-readable detail of the gain (component/latinum/artifact/lore)


@dataclass(frozen=True)
class StarbaseSalvaged(Event):
    """A component cannibalized out of an orbital starbase into the ship (§4.2, WP4)."""

    player_id: int
    starbase_id: int
    subsystem: str  # Subsystem value
    slot_index: int
    component: str  # Component value
    tier: str  # ComponentTier name


@dataclass(frozen=True)
class ColonistsRecruited(Event):
    player_id: int
    source: str  # "stardock" | "emigration"
    count: int
    cost: int  # latinum incentive paid


@dataclass(frozen=True)
class Colonized(Event):
    player_id: int
    planet_id: int
    colonists: int


@dataclass(frozen=True)
class PlanetProduced(Event):
    planet_id: int
    owner_player_id: int  # only player-owned colonies announce (alliance output is silent)


@dataclass(frozen=True)
class ColonyGrew(Event):
    planet_id: int
    colonists: int  # new colonist count


@dataclass(frozen=True)
class TurnsReset(Event):
    player_id: int
    turns: int


@dataclass(frozen=True)
class StockRegenerated(Event):
    port_id: int
    commodity: Commodity
    new_stock: int


@dataclass(frozen=True)
class AlienHailed(Event):
    """The player opened contact with a friendly species (§6, §6.7, WP9)."""

    player_id: int
    species_id: int


@dataclass(frozen=True)
class AlienSpoke(Event):
    """The player steered the conversation to a peaceful dialogue context (§6.7, WP17).

    `context` is the dialogue key spoken (greeting / dossier_other / farewell / …);
    `subject_id` is the species asked about for `dossier_other`, else None. Records the
    ring-advancing conversation turn so the log can carry "you asked the Vesk about the
    Selvani" and replay reconstructs every peaceful exchange.
    """

    player_id: int
    species_id: int
    context: str
    subject_id: int | None = None


@dataclass(frozen=True)
class AlienMoved(Event):
    """A species drifted between sectors on the tick clock (§6.3, WP16).

    Emitted by the `alien_drift` cron, but surfaced to the player only when the move
    touches their current sector (a vessel warps in/out beside them) — so the log isn't
    flooded by galaxy-wide drift. `from_sector`/`to_sector` are internal ids.
    """

    species_id: int
    from_sector: int
    to_sector: int


@dataclass(frozen=True)
class AlienTraded(Event):
    """Bought or bartered alien tech (§6, §8, WP9).

    `kind` is "buy" (latinum) or "barter" (an artifact); `detail` labels the delivered
    upgrade (a component+tier, or an aspect); `cost` is the latinum paid (0 for barter).
    """

    player_id: int
    species_id: int
    kind: str
    detail: str
    cost: int


@dataclass(frozen=True)
class AttitudeChanged(Event):
    """The player's standing with a species shifted (§6, WP9).

    `offset` is the new accumulated attitude offset; `effective` the resulting effective
    disposition (base + offset, clamped) that gates greetings, prices, and tech tiers.
    """

    player_id: int
    species_id: int
    offset: float
    effective: float


@dataclass(frozen=True)
class LeadAccepted(Event):
    """The player accepted a coordinate tip from an alien (§6.7, the "map" mechanic).

    Logs the place pointed to (`kind`/`ref`/`sector_id`) and the species that shared it,
    so the leads list on the Computer/Map screen reconstructs under replay.
    """

    player_id: int
    species_id: int
    kind: str
    ref: int
    sector_id: int


@dataclass(frozen=True)
class EncounterStarted(Event):
    """An interrupt roll produced an encounter on entering a sector (§10, WP24).

    `hostile=True` ⇒ a violence opener: the pack in `pack_size` is live on
    `Player.active_encounter` and movement is blocked until it resolves.
    `hostile=False` ⇒ a peaceful opener — the journey halts and the contact screen
    takes over (nothing stored). The band rides along for the log line's colour.
    """

    player_id: int
    species_id: int
    sector_id: int
    hostile: bool
    pack_size: int
    band: str


@dataclass(frozen=True)
class EncounterEvaded(Event):
    """The species' sensors missed the player — slipped away unseen (§10, WP24)."""

    player_id: int
    species_id: int
    sector_id: int


@dataclass(frozen=True)
class CombatRound(Event):
    """One resolved combat round (§10, WP25): the player's action + the pack's volley."""

    player_id: int
    species_id: int
    round: int
    action: str  # fight / flee / launch_missile / field_patch
    damage_dealt: int
    damage_taken: int
    foes_left: int


@dataclass(frozen=True)
class EncounterEnded(Event):
    """A hostile encounter resolved (§10, WP25/WP26): fled / victory / destroyed."""

    player_id: int
    species_id: int
    outcome: str


@dataclass(frozen=True)
class ComponentKnockedOut(Event):
    """A volley localized into a subsystem component (§4.1, WP26)."""

    player_id: int
    subsystem: str
    slot_index: int
    component: str


@dataclass(frozen=True)
class ShipDestroyed(Event):
    """The player's hull reached zero — dropped to the escape pod (§10, WP26)."""

    player_id: int
    species_id: int
    sector_id: int
    lost_ship: str  # the destroyed hull's class id


@dataclass(frozen=True)
class SalvageCollected(Event):
    """Post-victory wreck salvage (§10, WP26): latinum plus any loose components."""

    player_id: int
    latinum: int
    components: tuple[str, ...]  # loose Tier-I part kinds recovered (may be empty)
