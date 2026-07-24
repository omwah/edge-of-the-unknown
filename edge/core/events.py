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
    units: int  # units actually filled (may be < requested under a hard port purse, WP47)
    unit_price: int
    total: int
    requested: int = 0  # units the player asked for; == units unless the port's purse capped it


@dataclass(frozen=True)
class BaseCommission(Event):
    """A base-hosted market paid its owner a cut of a trade (§4.2, WP78).

    `player_id` is the trader; the owner (`owner_kind` "player"/"corp", `owner_ref` the
    player/corp id) is credited `amount` latinum out of the port's purse.
    """

    player_id: int
    starbase_id: int
    port_id: int
    owner_kind: str
    owner_ref: int
    amount: int


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
    """A special device bought at Stardock (§4, WP10), e.g. a genesis torpedo."""

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
class GroundOperationBegan(Event):
    """A ground operation (survey/assault) opened on a planet (GW-WP03)."""

    player_id: int
    operation_id: int
    kind: str  # "survey" | "assault"
    planet_id: int


@dataclass(frozen=True)
class GroundOperationEnded(Event):
    """A ground operation settled/extracted, clearing `Player.ground_operation` (GW-WP03)."""

    player_id: int
    operation_id: int
    kind: str  # "survey" | "assault"
    outcome: str  # e.g. "extracted"; richer outcomes land with GW-WP06/WP11


@dataclass(frozen=True)
class GarrisonReinforced(Event):
    """Recruits + suits converted into a world's persistent garrison (GW-WP09, D15).

    Irreversible — `count` becomes exactly that much `garrison_infantry`.
    """

    player_id: int
    planet_id: int
    suit_id: str
    count: int


@dataclass(frozen=True)
class BeltMined(Event):
    """The player hand-mined an asteroid belt, taking raw goods aboard (§4.2, PT-30)."""

    player_id: int
    planet_id: int
    commodity: str  # Commodity value
    amount: int  # units taken into the cargo hold


@dataclass(frozen=True)
class GroundMoved(Event):
    """The survey explorer marched to a new cell (GW-WP06). `main_turns` = macro turns spent."""

    player_id: int
    operation_id: int
    x: int
    y: int
    main_turns: int


@dataclass(frozen=True)
class SurveyDug(Event):
    """A dig at `(x, y)` opened a trench (GW-WP06). `discovery_id` is -1 for a dry hole.

    `resupply` is the supply gain on a successful excavation (0 otherwise); `already_dug`
    marks a free re-dig of ground already fully turned over, distinct from a fresh dry hole
    (both leave `discovery_id` -1). Defaulted so older persisted logs decode unchanged.
    """

    player_id: int
    operation_id: int
    x: int
    y: int
    discovery_id: int
    resupply: int = 0
    already_dug: bool = False


@dataclass(frozen=True)
class SurveySiteExcavated(Event):
    """A surface site was excavated — its artifact + codex lore recorded (GW-WP06, D6)."""

    player_id: int
    operation_id: int
    discovery_id: int
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name


@dataclass(frozen=True)
class SurveyLanded(Event):
    """The shuttle set down on the player's chosen drop site, opening the survey."""

    player_id: int
    operation_id: int
    x: int
    y: int


@dataclass(frozen=True)
class SurveyTalked(Event):
    """The explorer spoke with a settlement (GW-WP06, D5). `hinted_id` -1 when no hint given.

    `resupply` is the supply gain from this visit (0 when already topped up). Defaulted so
    older persisted logs decode unchanged.
    """

    player_id: int
    operation_id: int
    settlement_id: int
    hinted_id: int
    resupply: int = 0


@dataclass(frozen=True)
class GroundAssaultDropped(Event):
    """The platoon landed, opening live tactical play (GW-WP10, D3).

    `casualties_on_drop` counts troopers lost to AA reaction fire on the way down —
    zero on a clean drop.
    """

    player_id: int
    operation_id: int
    trooper_count: int
    casualties_on_drop: int


@dataclass(frozen=True)
class GroundJumped(Event):
    """One trooper jump-jetted to a new cell, possibly drawing AA reaction fire
    (GW-WP10). `hit` is whether that fire connected."""

    player_id: int
    operation_id: int
    actor_id: int
    x: int
    y: int
    hit: bool


@dataclass(frozen=True)
class GroundFired(Event):
    """One trooper fired at a cell (GW-WP10). `target_kind` is "structure" or
    "garrison"; `destroyed` is whether that hit finished the target."""

    player_id: int
    operation_id: int
    actor_id: int
    x: int
    y: int
    missile: bool
    hit: bool
    target_kind: str
    destroyed: bool


@dataclass(frozen=True)
class GroundBroadcastMade(Event):
    """A Command-suit trooper dictated terms over a cowed city — the big Resolve
    strike (GW-WP10)."""

    player_id: int
    operation_id: int
    actor_id: int
    city_id: int


@dataclass(frozen=True)
class GroundDefenseFireLogged(Event):
    """One battle-log line that would otherwise resolve silently (GW-WP10/WP13-FU1).

    Originally scoped to the planet's defense phase during `EndGroundTurn` —
    `EndGroundTurn` used to report only the round summary (`GroundTurnEnded`), so
    trooper HP dropped with no explanation in the log. Now also carries the
    secondary consequence lines (Resolve deltas, city cowing, trooper KIA) that a
    player-caused `GroundFire`/`GroundJump`/`GroundBroadcast` action computes but
    whose own summary event doesn't narrate. `kind` is one of "hit", "killed",
    "miss", "resolve", "destroyed", "sortie". `friendly` mirrors the core battle
    log's flag (whose meaning is kind-dependent, not simply "good news").
    """

    player_id: int
    operation_id: int
    kind: str
    text: str
    x: int
    y: int
    friendly: bool


@dataclass(frozen=True)
class GroundTurnEnded(Event):
    """The planet's whole turn ran: detection, emplacement fire, garrison AI,
    escalating sorties, and the retrieval clock (GW-WP10). `outcome` is empty while
    the assault remains live."""

    player_id: int
    operation_id: int
    turn: int
    resolve: int
    main_turns: int
    outcome: str


@dataclass(frozen=True)
class GroundAssaultSettled(Event):
    """A tactical assault reconciled into persistent strategic state (GW-WP11)."""

    player_id: int
    planet_id: int
    outcome: str
    control: str
    attacker_losses: int
    defender_losses: int
    civilian_losses: int
    missiles_spent: int
    loot: int


@dataclass(frozen=True)
class ProtectorateEstablished(Event):
    """An unaligned native polity surrendered under limited player/corp control."""

    player_id: int
    planet_id: int
    controller_kind: str
    controller_ref: int


@dataclass(frozen=True)
class ProtectorateAnnexed(Event):
    """A recovered protectorate was explicitly converted into ordinary ownership."""

    player_id: int
    planet_id: int
    owner_kind: str
    owner_ref: int


@dataclass(frozen=True)
class RecruitsHired(Event):
    """Ground recruits enlisted at a Stardock for a per-head incentive (GW-WP08, D3)."""

    player_id: int
    count: int
    cost: int  # total latinum incentive paid


@dataclass(frozen=True)
class RecruitsDismissed(Event):
    """Ground recruits released back to the dock, freeing their berths (GW-WP08, D3)."""

    player_id: int
    count: int
    severance: int  # total latinum paid out


@dataclass(frozen=True)
class SuitsPurchased(Event):
    """Powered-armour suits bought at a Stardock (GW-WP08, D3)."""

    player_id: int
    suit_id: str
    count: int
    cost: int


@dataclass(frozen=True)
class SuitsSold(Event):
    """Powered-armour suits sold back to a Stardock at the resale fraction (GW-WP08)."""

    player_id: int
    suit_id: str
    count: int
    refund: int
    missiles_spilled: int  # ordnance the remaining suits can no longer chamber (G8)


@dataclass(frozen=True)
class GroundOrdnanceBought(Event):
    """Ground missiles loaded into the platoon's magazine (GW-WP08, D3)."""

    player_id: int
    count: int
    cost: int


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
class ColonistsSettled(Event):
    """More colonists landed onto an already-owned colony (§8, WP-PR07). `colonists` is the
    accepted count (clamped to berth + remaining habitability)."""

    player_id: int
    planet_id: int
    colonists: int


@dataclass(frozen=True)
class CloudCityBuilt(Event):
    """A staging area was built (or grown) on a gas giant (§4.2, PT-54).

    `size` is the city's new size; `cost` the Equipment taken out of the ship's hold to
    raise it. The first build also claims the world.
    """

    player_id: int
    planet_id: int
    size: int
    cost: int


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
class MarketSettled(Event):
    """The daily order-book settlement summary (§8, WP47).

    One aggregate emitted per settlement, fog-safe (it names no port): `matches` is
    the number of fills, `volume` the total units moved, `slips` the total latinum
    that changed hands between ports.
    """

    matches: int
    volume: int
    slips: int


@dataclass(frozen=True)
class PortOrderFilled(Event):
    """One side of one settled match at an *explored* port (§8, WP47 — fog-respecting).

    Emitted only for a port the player has seen (the `planet_growth` log discipline),
    so it never leaks an unexplored port's book. `side` is "buy" (this port bought) or
    "sell" (this port sold); `counterparty_port_id` names the other port in the match.
    """

    port_id: int
    commodity: Commodity
    side: str
    qty: int
    unit_price: int
    counterparty_port_id: int


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
class AlienDestroyed(Event):
    """A drifting NPC was destroyed by a sector's territory defenses on entry (§10, WP-PR02).

    Emitted by the `alien_drift` cron when a species wanders into a mined/garrisoned sector
    whose owner opposes it and the defenses out-damage its hull. Surfaced only when the
    sector touches a player (fog on the write side, like `AlienMoved`). `cause` is
    ``"mine"`` / ``"fighter"`` / ``"mine+fighter"``.
    """

    species_id: int
    sector_id: int
    cause: str


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
    """A hostile encounter resolved (§10, WP25/WP26/WP-PR03): fled / victory / destroyed / retreated.

    `destroyed`/`fled` count the foes this end downed and the foes that broke off, and
    `foe_name` names the pack — so the log/encounter screen state exactly what happened
    ("2 of 3 destroyed, 1 retreated") instead of the generic "the pack is destroyed"
    (PT-26). Defaulted so older persisted logs decode unchanged.
    """

    player_id: int
    species_id: int
    outcome: str
    destroyed: int = 0
    fled: int = 0
    foe_name: str = ""


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
    """Immediate combat salvage for PvP/fixed set-pieces (§10, WP26).

    Ordinary destroyed NPC hulls use persistent Discovery wrecks (PT-01).
    """

    player_id: int
    latinum: int
    components: tuple[str, ...]  # loose Tier-I part kinds recovered (may be empty)


@dataclass(frozen=True)
class GrudgeFormed(Event):
    """A species' vendetta against the player formed or deepened (§6.5, WP27)."""

    player_id: int
    species_kind: str  # roster id — every ship of the kind shares the vendetta
    severity: float
    permanent: bool  # never_forgets / betrayal_model=permanent: it will not decay


@dataclass(frozen=True)
class GovernanceChanged(Event):
    """Core Space changed hands to a new governing alliance (§6.3, §4.2, WP49).

    `cause` records how ("player_champion" / "npc_seizure" / "dev"). Announced to the
    ticker as the new law of the Core; per-player Core hostility is a projection, not
    carried here (safety follows the governor positionally).
    """

    old_alliance_id: int | None
    new_alliance_id: int | None
    cause: str


@dataclass(frozen=True)
class AllianceLeadershipChanged(Event):
    """An internal coup swapped a bloc's leader (§6.3, WP51).

    `old_leader_roster`/`new_leader_roster` are species kinds (`roster_id`s); the old
    leader is demoted to member and the internal rival promoted. The dossier re-derives
    its role text from the live species, so the UI follows automatically.
    """

    alliance_id: int
    old_leader_roster: str | None
    new_leader_roster: str


@dataclass(frozen=True)
class CoreLawNotice(Event):
    """The governor's patrols flag a criminal player entering Core Space (WP27).

    A warning only; a rival-aligned player is instead engaged on sight (WP38 encounter).
    """

    player_id: int
    sector_id: int


@dataclass(frozen=True)
class AdmissionAdvanced(Event):
    """One admission task toward a bloc's membership was completed (§6.3, WP38)."""

    player_id: int
    alliance_id: int
    task: str


@dataclass(frozen=True)
class AllianceJoined(Event):
    """The player joined a bloc (§6.3, WP38) — exclusive, with rival fallout."""

    player_id: int
    alliance_id: int
    former_alliance_id: int | None  # the membership resigned to join, if any


@dataclass(frozen=True)
class AllianceResigned(Event):
    """The player left their bloc (§6.3, WP38) — standing recovers to neutral."""

    player_id: int
    former_alliance_id: int


@dataclass(frozen=True)
class StarbaseRazed(Event):
    """A starbase was razed in a set-piece assault (§4.2, §10 — WP40).

    The base is derelicted and its world freed; `former_owner_kind`/`ref` name the bloc
    (or player) that lost it, `bounty` the latinum paid for the razing.
    """

    player_id: int
    starbase_id: int
    planet_id: int
    sector_id: int
    former_owner_kind: str
    former_owner_ref: int | None
    bounty: int


@dataclass(frozen=True)
class StarbaseRepaired(Event):
    """A loose component was installed into a base slot, refilling a derelict (§4.2, WP40)."""

    player_id: int
    starbase_id: int
    subsystem: str
    slot_index: int
    component: str
    tier: str


@dataclass(frozen=True)
class StarbaseClaimed(Event):
    """A repaired, unowned base was claimed as a player foothold (§4.2, WP40)."""

    player_id: int
    starbase_id: int
    cost: int


@dataclass(frozen=True)
class TerritoryDeployed(Event):
    """Fighters / mines / a beacon were deployed to a sector (§10, WP41).

    `kind` is "fighters" | "mines" | "beacon"; `count` the number deployed (1 for a
    beacon). `mode` names a fighter garrison's stance (else empty).
    """

    player_id: int
    sector_id: int
    kind: str
    count: int
    mode: str = ""


@dataclass(frozen=True)
class HazardDamage(Event):
    """A sector hazard damaged the ship on entry (§10, WP41).

    `source` is "mine" | "black_hole"; `damage` the hull points taken after shields.
    """

    player_id: int
    sector_id: int
    source: str
    damage: int


@dataclass(frozen=True)
class CargoTransferred(Event):
    """Goods moved between the ship's hold and an owned world's stores (§4.2).

    `to_planet` True is an unload (ship → stores); False a load (stores → ship).
    Goods are conserved — haulage, not a trade. This is the colony-supply rail:
    how citadel equipment reaches a world (the WP54 build draws from stores).
    """

    player_id: int
    planet_id: int
    commodity: Commodity
    units: int
    to_planet: bool


@dataclass(frozen=True)
class FightersTransferred(Event):
    """Fighters moved between a ship's bays and a planet's stored stock (GW-WP09).

    `to_planet` True is an unload (ship → stores); False a load (stores → ship).
    Fighters are conserved — mirrors `CargoTransferred`, but for the space-fighter
    reserve rather than trade goods.
    """

    player_id: int
    planet_id: int
    count: int
    to_planet: bool


@dataclass(frozen=True)
class CitadelBuildStarted(Event):
    """A timed citadel build was opened on a planet (§4.2, WP54).

    Paid up front; `target_level` is the level under construction. Progress accrues on
    the planet-growth cron in colonist-days until `CitadelCompleted`.
    """

    player_id: int
    planet_id: int
    target_level: int


@dataclass(frozen=True)
class CitadelCompleted(Event):
    """A citadel build finished, raising the planet to `level` (§4.2, WP54)."""

    planet_id: int
    level: int


@dataclass(frozen=True)
class ProbeReport(Event):
    """A launched probe charted its path and reported its findings (§11, §14, WP56).

    `sectors_charted` new sectors were revealed; `ports`/`planets`/`contacts` count what
    the probe saw en route; `destroyed` is True if it was lost in a hostile sector before
    reaching `dest_sector`.
    """

    player_id: int
    dest_sector: int
    sectors_charted: int
    ports: int
    planets: int
    contacts: int
    destroyed: bool


@dataclass(frozen=True)
class InterdictorToggled(Event):
    """The interdictor was engaged or disengaged (§14, WP56)."""

    player_id: int
    active: bool


@dataclass(frozen=True)
class LimpetsRemoved(Event):
    """Attached limpet mines were stripped at a service point (§10, WP56)."""

    player_id: int
    count: int
    fee: int


@dataclass(frozen=True)
class CitadelGunSilenced(Event):
    """A planet's citadel gun was knocked out in combat (§4.2, WP55) — a siege rung."""

    player_id: int
    planet_id: int


@dataclass(frozen=True)
class PlanetInvaded(Event):
    """A ground assault took an owned world (§4.2, §14, GW-WP11 tactical settlement).

    `fighters_lost` attacker losses died taking it; `colonists` survived the conquest;
    `loot` latinum (captured treasury + looted stores value) was seized. The planet's
    `owner` flips to the invader and its citadel drops one level.
    """

    player_id: int
    planet_id: int
    fighters_lost: int
    colonists: int
    loot: int


@dataclass(frozen=True)
class RumorHeard(Event):
    """The player bought a rumor at the tavern (DESIGN §14 — WP58).

    A latinum sink that logs a coordinate `Lead` (`kind`/`ref`/`sector_id`) the Core-welcome
    species collectively knew — intel for cash. `price` is the slips paid.
    """

    player_id: int
    kind: str
    ref: int
    sector_id: int
    price: int


@dataclass(frozen=True)
class NoticePosted(Event):
    """A player pinned a message to the tavern noticeboard (DESIGN §14 — WP58)."""

    player_id: int
    day: int


@dataclass(frozen=True)
class ContractAccepted(Event):
    """The player accepted a favor from an alien (DESIGN §6.7, §14 — WP57).

    `kind` is deliver / destroy / escort; `issuer` the species kind (roster_id); `reward`
    the latinum on completion; `deadline_day` when it lapses. Logs the job so the
    Computer's contracts panel and the message log reconstruct under replay.
    """

    player_id: int
    contract_id: int
    kind: str
    issuer: str
    reward: int
    deadline_day: int


@dataclass(frozen=True)
class ContractCompleted(Event):
    """A favor was fulfilled and paid (DESIGN §6.7, WP57): reward slips credited."""

    player_id: int
    contract_id: int
    kind: str
    reward: int


@dataclass(frozen=True)
class ContractFailed(Event):
    """A favor lapsed or was abandoned (DESIGN §6.7, WP57).

    `reason` is "deadline" (the daily cron) or "abandoned" (the player released it).
    An escort that fails also releases its merchant back to the drift rails.
    """

    player_id: int
    contract_id: int
    kind: str
    reason: str


@dataclass(frozen=True)
class PlanetBanked(Event):
    """A treasury deposit/withdraw at an owned citadel world (§4.2, WP54).

    `kind` is "deposit" | "withdraw"; `balance` is the treasury after the move.
    """

    player_id: int
    planet_id: int
    kind: str
    amount: int
    balance: int


# --- corporations (DESIGN §4, WP66) ------------------------------------------


@dataclass(frozen=True)
class CorpFormed(Event):
    """A player chartered a corporation (§4, WP66). `tag` is the short handle; `fee` the sink paid."""

    player_id: int
    corp_id: int
    name: str
    tag: str
    fee: int


@dataclass(frozen=True)
class CorpInvited(Event):
    """The CEO invited a player to the corp (§4, WP66) — the first half of the two-step join."""

    player_id: int  # the inviting CEO
    corp_id: int
    invitee_player_id: int


@dataclass(frozen=True)
class CorpJoined(Event):
    """A player accepted an invite and joined the corp (§4, WP66)."""

    player_id: int
    corp_id: int


@dataclass(frozen=True)
class CorpDeparted(Event):
    """A player left, was expelled, or the corp dissolved (§4, WP66).

    `reason` is "left" | "expelled" | "dissolved". On dissolution the last member's departure
    re-keys corp assets to the departing CEO (never to `none`).
    """

    player_id: int
    corp_id: int
    reason: str


@dataclass(frozen=True)
class CorpBanked(Event):
    """A corp bank deposit/withdraw (§4, WP66). `kind` is "deposit" | "withdraw"; `balance` after."""

    player_id: int
    corp_id: int
    kind: str
    amount: int
    balance: int


@dataclass(frozen=True)
class PlanetTransferred(Event):
    """A planet moved between a player and their corp (§4, WP66). `to_corp` marks the direction."""

    player_id: int
    planet_id: int
    corp_id: int
    to_corp: bool


@dataclass(frozen=True)
class CorpWarDeclared(Event):
    """One corp declared war on another (§4, WP66) — hostility is mutual-by-declaration."""

    player_id: int  # the declaring CEO
    corp_id: int
    target_corp_id: int


@dataclass(frozen=True)
class CorpWarEnded(Event):
    """A corp unilaterally withdrew from a war (§4, WP66); a cooldown blocks immediate re-declaration."""

    player_id: int
    corp_id: int
    target_corp_id: int


# --- PvP (DESIGN §14, WP67) --------------------------------------------------


@dataclass(frozen=True)
class PlayerAttacked(Event):
    """One player opened attacker-driven PvP combat on another (§14, WP67).

    Sector-scoped, so it reaches the defender (and bystanders) through the broadcast — how an
    offline/absent defender's client learns the fight began.
    """

    player_id: int  # the attacker
    target_player_id: int
    sector_id: int


@dataclass(frozen=True)
class BountyPosted(Event):
    """A claimable outlaw bounty was posted on a player for a lawful kill (§14, WP67).

    `amount` is the bounty *added* this event (bounties accrue); `total` is the running head
    price any player who later pods them collects.
    """

    player_id: int  # the outlaw the bounty rides on
    amount: int
    total: int
