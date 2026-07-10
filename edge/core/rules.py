"""Command → (state delta, events) reducers (DESIGN §3) — the only state mutators.

Each reducer is pure: it reads the `UniverseState`, validates the command, and
returns a `ReduceResult` of new frozen entities plus the events that occurred —
it never edits state in place. `apply_result` performs the actual upsert into the
mutable container (the service wraps that in a store transaction, WP6). Invariants
are delegated to `core.economy` and `core.movement`; randomness (haggling) is
drawn from the state-owned RNG, so replay from `(seed, command log)` is exact.

Command set: movement (Warp, TravelTo, Dock), trade (Trade, HaggleOffer), banking
(Deposit, Withdraw), StarDock services (BuyComponent, BuyShip, RepairAtDock), and
engine-room work (InstallComponent, SwapComponent, Cannibalize, FieldPatch).
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import assert_never

from edge import dialogue
from edge.core import combat, encounters
from edge.core import citadels
from edge.core import contracts
from edge.core import corp
from edge.core import mechanics
from edge.core import starbases
from edge.core import territory
from edge.core.aliens import (
    FRIENDLY as FRIENDLY_BAND,
    HOSTILE as HOSTILE_BAND,
    NEUTRAL as NEUTRAL_BAND,
    admission_met,
    apply_join_standing,
    apply_resign_standing,
    apply_spillover,
    attitude_locked,
    disposition_band,
    effective_disposition,
    governor_hostile,
    is_criminal,
    record_admission_task,
    record_seizure_task,
    seizure_progress,
    sour_attitude,
)
from edge.core.governance import flip_core_governor
from edge.core.services import COMPONENTS, MUNITIONS, REPAIR, require_service
from edge.core.combat import CombatError
from edge.core.dev import DevPatch, apply_dev_patch

from edge.core.config import GameConfig, SpeciesConfig, TechOfferConfig
from edge.core.economy import (
    EconomyError,
    HaggleStatus,
    deposit,
    execute_trade,
    port_unit_price,
    resolve_haggle,
    withdraw,
)
from edge.core.engine_room import (
    EngineRoomError,
    apply_derived,
    build_subsystems,
    derive_aspects,
    legal_components,
    tier_ceiling,
)
from edge.core.discovery import (
    describe_payload,
    entity_codex_discovery,
    entity_contactable,
    entity_species,
    is_detectable,
    sector_has_nebula,
)
from edge.core.enums import (
    Commodity,
    Component,
    ComponentTier,
    PayloadKind,
    PortClass,
    Subsystem,
)
from edge.core.events import (
    AlienSpoke,
    AlienTraded,
    AttitudeChanged,
    Banked,
    Colonized,
    AdmissionAdvanced,
    AllianceJoined,
    AllianceResigned,
    CitadelBuildStarted,
    CitadelGunSilenced,
    ContractAccepted,
    ContractCompleted,
    ContractFailed,
    CorpBanked,
    CorpDeparted,
    CorpFormed,
    CorpInvited,
    CorpJoined,
    CorpWarDeclared,
    CorpWarEnded,
    PlanetTransferred,
    PlayerAttacked,
    BountyPosted,
    ColonistsRecruited,
    InterdictorToggled,
    InvasionRepulsed,
    LimpetsRemoved,
    NoticePosted,
    PlanetBanked,
    PlanetInvaded,
    ProbeReport,
    RumorHeard,
    ComponentInstalled,
    ComponentKnockedOut,
    ComponentPurchased,
    ComponentRemoved,
    CoreLawNotice,
    Descended,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    EncounterEnded,
    EncounterEvaded,
    EncounterStarted,
    Event,
    GenesisDeployed,
    GrudgeFormed,
    Haggled,
    LeadAccepted,
    Repaired,
    SalvageCollected,
    ShipDestroyed,
    ShipPurchased,
    SiteExplored,
    StarbaseClaimed,
    StarbaseRazed,
    StarbaseRepaired,
    StarbaseSalvaged,
    TerritoryDeployed,
    Traded,
    Warped,
)
from edge.core.events import HazardDamage as HazardDamageEvent
from edge.core.events import CombatRound as CombatRoundEvent
from edge.core.planets import is_colonizable, retype_planet
from edge.core.starbases import is_operational
from edge.core.models import (
    AlienSpecies,
    Alliance,
    Corporation,
    Discovery,
    Encounter,
    Game,
    InstalledComponent,
    LastCombat,
    Lead,
    Notice,
    Ownership,
    Planet,
    Player,
    Port,
    Sector,
    SectorForce,
    Ship,
    Starbase,
    SubsystemState,
    UNOWNED,
    UniverseState,
)
from edge.core.market import PortOrder
from edge.core.movement import MovementError, can_warp, shortest_path
from edge.dialogue import facts as dialogue_facts
from edge.dialogue.intel import IntelTarget, pick_intel_target, pick_rumor

# --- commands ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class JoinGame:
    """Enroll a player into an already-generated universe (DESIGN §3).

    Recorded in the command log like any other command, so `rebuild` replays it and
    reconstructs the player deterministically — joining is a player action, not part
    of seed-derived universe generation (`bigbang.populate` no longer seeds players).
    The new player's id is the `player_id` the command is applied under; its start
    sector / starting balances / starter hull are derived from config + world state.
    """

    name: str = "Trailblazer"


@dataclass(frozen=True, slots=True)
class Warp:
    to_sector: int


@dataclass(frozen=True, slots=True)
class TravelTo:
    """A multi-hop warp to a known sector along its uncovered route (WP-C)."""

    to_sector: int


@dataclass(frozen=True, slots=True)
class Dock:
    pass


@dataclass(frozen=True, slots=True)
class Trade:
    commodity: Commodity
    units: int
    unit_price: int | None = None  # None => quote at the §8 price (quick-trade)


@dataclass(frozen=True, slots=True)
class HaggleOffer:
    commodity: Commodity
    units: int
    counter_price: int


@dataclass(frozen=True, slots=True)
class Deposit:
    amount: int


@dataclass(frozen=True, slots=True)
class Withdraw:
    amount: int


@dataclass(frozen=True, slots=True)
class BuyComponent:
    """Buy a loose component from the StarDock hardware emporium (§8). Tier III is barter-only."""

    component: Component
    tier: ComponentTier


@dataclass(frozen=True, slots=True)
class BuyShip:
    """Trade the current hull for a buyable class at the StarDock shipyard (§8)."""

    ship_class_id: str


@dataclass(frozen=True, slots=True)
class RepairAtDock:
    """StarDock restoration of a knocked-out component (§4.1). Inert until Phase-3 combat."""

    subsystem: Subsystem
    slot_index: int


@dataclass(frozen=True, slots=True)
class RecruitColonists:
    """Recruit colonists into the ship's occupancy (§4.2). Recruited, never bought.

    `from_planet` None ⇒ StarDock recruitment office (pay a per-head latinum incentive);
    a planet id ⇒ emigration from that inhabited world (the disposition gate lands in WP7).
    """

    count: int
    from_planet: int | None = None


@dataclass(frozen=True, slots=True)
class Colonize:
    """Settle recruited colonists onto an unowned colonizable world, claiming it (§8)."""

    planet_id: int
    colonists: int


@dataclass(frozen=True, slots=True)
class SetAllocation:
    """Set a player-owned colony's production split over the trio + garrison (§8, §4.2).

    `allocation` maps Commodity value → share; `fighter` is the optional garrison share
    (§4.2, WP55). The reducer normalizes the trio shares **plus** `fighter` to sum 1.0, so
    `sum(commodity shares) + fighter_allocation == 1.0` holds (the §4 invariant — the trio
    stays sacred, fighters ride their own share rather than a fourth commodity).
    """

    planet_id: int
    allocation: dict[str, float]  # Commodity value -> share
    fighter: float = 0.0  # garrison production share (WP55)


@dataclass(frozen=True, slots=True)
class BuildCitadel:
    """Open a timed build of the next citadel level on an owned world (§4.2, WP54).

    Pays the level's equipment (from planet stores) + latinum up front and opens the
    build; progress accrues on the planet-growth cron. Owner-only, in-sector.
    """

    planet_id: int


@dataclass(frozen=True, slots=True)
class InvadePlanet:
    """Land carried fighters to take an owned world by ground assault (§4.2, §14, WP55).

    Legal only when no operational base defends the sector and the citadel gun is down
    (or was never built), and the L3 siege shield does not bar it. Commits `fighters`
    from the ship; resolution is a per-round exchange against the citadel-scaled garrison.
    Never in the Core (deployment-free, §10).
    """

    planet_id: int
    fighters: int


@dataclass(frozen=True, slots=True)
class PlanetDeposit:
    """Deposit latinum into an owned citadel world's treasury (§4.2, WP54). Owner-only, in-sector."""

    planet_id: int
    amount: int


@dataclass(frozen=True, slots=True)
class PlanetWithdraw:
    """Withdraw latinum from an owned citadel world's treasury (§4.2, WP54). Owner-only, in-sector."""

    planet_id: int
    amount: int


@dataclass(frozen=True, slots=True)
class InstallComponent:
    """Slot a loose component from the hold into an empty subsystem slot (§4.1)."""

    subsystem: Subsystem
    slot_index: int
    component: Component
    tier: ComponentTier


@dataclass(frozen=True, slots=True)
class SwapComponent:
    """Replace a filled slot's component with a loose one; the old part returns to the hold."""

    subsystem: Subsystem
    slot_index: int
    component: Component
    tier: ComponentTier


@dataclass(frozen=True, slots=True)
class Cannibalize:
    """Pull a component out of a filled slot into the loose-part inventory (§4.1).

    `starbase_id` None ⇒ strip the player's own ship; a starbase id ⇒ salvage an
    orbital base in the current sector (§4.2, WP4) — allowed only when that base is
    derelict or player-owned. The salvaged part lands in the ship's loose inventory.
    """

    subsystem: Subsystem
    slot_index: int
    starbase_id: int | None = None


@dataclass(frozen=True, slots=True)
class Salvage:
    """Log/collect a revealed discovery into the codex (§7, WP5/WP6).

    Open-space: a hidden find must have been detected on entry first (sensors are
    snapshotted at entry, so re-enter after a sensor upgrade to pick up more). Surface
    sites must have been explored first (WP6). Either way takes the payload aboard
    (component / latinum / artifact; lore is codex-only) and marks it found.
    """

    discovery_id: int


@dataclass(frozen=True, slots=True)
class Descend:
    """Land on a planet's surface to explore its sites (§7, WP6). Costs turns."""

    planet_id: int


@dataclass(frozen=True, slots=True)
class Explore:
    """Reveal the next surface site of a planet (§7, WP6).

    Surveys site-by-site: each call reveals the lowest-slot still-hidden site the
    ship's sensors can resolve (obvious sites always; Rare+ sites need a sensor
    sweep). Revealed sites enter `Player.detected` and can then be logged (`Salvage`).
    """

    planet_id: int


@dataclass(frozen=True, slots=True)
class BuyGenesis:
    """Buy one Genesis torpedo from the StarDock (§4.2, WP10). A latinum sink."""


@dataclass(frozen=True, slots=True)
class DeployGenesis:
    """Terraform an eligible unowned planet in the current sector (§4.2, WP10).

    Consumes one carried Genesis torpedo and re-types the world to the configured
    colonizable type, re-rolling its yield/habitability — leaving it claimable.
    """

    planet_id: int


@dataclass(frozen=True, slots=True)
class FieldPatch:
    """Spend one repair-kit to un-knock-out a damaged component (§4.1).

    Structurally present in Phase 2 but only meaningful once Phase-3 combat sets
    `knocked_out`; against an undamaged slot it is rejected (nothing to patch).
    """

    subsystem: Subsystem
    slot_index: int


@dataclass(frozen=True, slots=True)
class CombatAction:
    """One combat round of a live encounter (§10, WP25).

    `action` is fight (fire the Main Gun), flee (roll the clamped escape chance),
    launch_missile (finite, arc-ignoring), or field_patch (spend a repair kit on
    `subsystem`/`slot_index` — the pack still gets its volley). Rejected when no
    encounter is live.
    """

    action: str  # fight / flee / launch_missile / field_patch
    subsystem: Subsystem | None = None  # field_patch target
    slot_index: int | None = None


@dataclass(frozen=True, slots=True)
class AttackPlayer:
    """Open attacker-driven PvP combat on another player's ship in this sector (§14, WP67).

    Legal only when `pvp.enabled`, both ships share a non-Core sector, neither is pod-bound or
    already in an encounter. Opens an `Encounter` whose foe is the target's live ship; the
    attacker then submits `CombatAction` rounds and the defender fights back automatically (H18).
    """

    target_player_id: int


@dataclass(frozen=True, slots=True)
class AttackSpecies:
    """Open first-strike combat on an alien contact in this sector (§10, WP70).

    The player-initiated twin of the violence opener: spawns the species' pack per its
    pack behavior onto `Player.active_encounter` and the fight proceeds through ordinary
    `CombatAction` rounds. Gated in the reducer: same sector, non-Core (the sanctuary),
    no pod, not the sensor-gated Entity, a combatant species with a fleet to field, and
    not forbidden by an `influence_gate` mechanic. A first strike is remembered like a
    kill: the attitude sours and a grudge forms before the first round (§6.5).
    """

    species_id: int


@dataclass(frozen=True, slots=True)
class BuyMissiles:
    """Buy homing missiles at the StarDock hardware emporium (§8, §10, WP25)."""

    count: int


@dataclass(frozen=True, slots=True)
class Hail:
    """Open contact with a friendly species in the current sector (§6, §6.7, WP9).

    Marks the species met and advances the greeting recency ring so re-hailing
    rephrases rather than replays. No combat — Phase 2 places only friendly species.
    """

    species_id: int


@dataclass(frozen=True, slots=True)
class Converse:
    """Steer an alien conversation to a peaceful dialogue context (§6.7, WP17).

    Speaks the chosen `context` (a `dialogue._PEACEFUL_CONTEXTS` key) in the species'
    voice and advances that context's recency ring so repeats rephrase — the same
    mechanism `Hail` uses for `greeting`, generalised to every peaceful context.
    `subject_id` names the species asked about for `dossier_other` ("ask about X").
    Combat / signature contexts are Phase 3 and rejected here.

    When `choice_index` is set, this is instead a **player reply** on an authored branching
    node (§6.7): `context` names the node currently shown, and the reducer re-resolves that
    node's line, validates the indexed `choice`, and applies it (transition to its
    `next_context` and/or its mechanical `action`). Conversation position is not stored in
    core state — it rides on the command — so a reply stays reproducible from (seed, log).
    """

    species_id: int
    context: str
    subject_id: int | None = None
    choice_index: int | None = None  # a player reply on a branching node (else a plain say)


@dataclass(frozen=True, slots=True)
class BuyAlienTech:
    """Buy an alien tech offer for latinum (§6, §8, WP9).

    `offer_index` indexes the species' `tech_offers`; the offer must be latinum-mode,
    reachable at the player's effective disposition, and affordable. Delivers a loose
    component or a flat aspect upgrade and raises the player's attitude with the species.
    """

    species_id: int
    offer_index: int


@dataclass(frozen=True, slots=True)
class BarterArtifact:
    """Barter a recovered artifact for an alien tech offer (§6, §8, WP9).

    The offer must be barter-mode and reachable; the player spends one artifact of the
    offer's tier (a discovery payload, §7) for tech no latinum sale gives — the
    exit-criterion payoff. Raises attitude like a purchase.
    """

    species_id: int
    offer_index: int


@dataclass(frozen=True, slots=True)
class AcceptLead:
    """Accept a coordinate tip an alien is offering (§6.7, the "map" mechanic, WP-intel).

    The speaker must currently hold an intel target for the player (friendly standing + a
    known, unvisited place); the tip is logged as a `Lead` on the Computer/Map screen. A
    no-op if the species has nothing new to share or the lead is already logged.
    """

    species_id: int


@dataclass(frozen=True, slots=True)
class DeliverContract:
    """Fulfil an active `deliver` favor at its target port (§6.7, WP57).

    The player must hold an active deliver contract, be in the destination sector docked at
    a port that buys the good, and carry the required cargo. The cargo debits and the reward
    credits — completion is reducer-side, never polled by the UI.
    """

    contract_id: int


@dataclass(frozen=True, slots=True)
class AbandonContract:
    """Release an active favor, failing it honestly (§6.7, WP57).

    An escort releases its merchant back to the drift rails; any kind takes the WP27
    consequence rail only on a *destroyed-merchant* escort failure, not a plain abandon.
    """

    contract_id: int


@dataclass(frozen=True, slots=True)
class BuyRumor:
    """Buy a rumor at the StarDock tavern (§14, WP58) — a latinum-for-`Lead` sink.

    Draws the best undiscovered coordinate tip the Core-welcome species collectively know
    and logs it as a `Lead`. Rejected off the StarDock, when unaffordable, or when the
    tavern has no fresh rumor (every tip the pinned species know is already logged).
    """


@dataclass(frozen=True, slots=True)
class PostNotice:
    """Pin a message to the tavern noticeboard (§14, WP58) — the one string-input command.

    `text` is sanitised at the reducer (printable-only, length-capped) and appended to the
    capped notice ring (oldest evicted). A captain's log single-player; the shared board in
    Phase 4. Rejected off the StarDock or with empty text.
    """

    text: str


@dataclass(frozen=True, slots=True)
class AdvanceAdmission:
    """Record one completed admission task toward a bloc's membership (§6.3, WP38).

    `task` must be one of the alliance's `admission_price` tokens. Completing a task
    writes it into the bloc's `species_arcs` ledger — the seam where gameplay (contract
    kills, favours, mechanic hooks) will feed admission progress. Idempotent per task.
    """

    alliance_id: int
    task: str


@dataclass(frozen=True, slots=True)
class JoinAlliance:
    """Join an alliance/bloc (§6.3, WP38) — the player may belong to at most one.

    Rejected unless the bloc's `membership_gate`/`admission_price` are satisfied and the
    `admission_fee` is affordable. Joining resigns any current membership, warms the
    bloc to +1 standing, and sours its rivals to −1 — which, if the Core governor is a
    rival, makes the Core unsafe (engaged on sight).
    """

    alliance_id: int


@dataclass(frozen=True, slots=True)
class ResignAlliance:
    """Leave the current alliance (§6.3, WP38) — the amends path.

    Standing resets to neutral, so a soured Core governor's sanctuary recovers. A no-op
    error if the player belongs to no bloc.
    """


@dataclass(frozen=True, slots=True)
class PetitionCoreSeizure:
    """Champion a `covets_core` bloc into the Core, flipping the governor (§6.3, WP50).

    Rejected unless the player is a sworn member in good standing, the bloc's
    `core_seizure` ladder is fully paid (its task tokens recorded, `bases_to_raze`
    Core-planet starbases razed, and the `fee` affordable). On success it applies
    `flip_core_governor(cause="player_champion")` — the covets_core bloc becomes the new
    governor and the Core re-keys to it.
    """

    alliance_id: int


@dataclass(frozen=True, slots=True)
class AssaultStarbase:
    """Attack an operational starbase in the current sector (§4.2, §10 — WP40).

    Opens a set-piece encounter against the base (one immobile emplacement). Victory
    razes it — flipping the world toward unowned/claimable, souring its owner bloc, and
    paying a bounty. A derelict base cannot be assaulted (salvage/repair it instead).
    """

    starbase_id: int


@dataclass(frozen=True, slots=True)
class RepairStarbase:
    """Install a loose component from the hold into a base's subsystem slot (§4.2, WP40).

    Refills a derelict base slot-by-slot (the same rules as an engine-room install):
    restoring the reactor keystone makes the base operational, the precondition for
    claiming it into a forward foothold.
    """

    starbase_id: int
    subsystem: Subsystem
    slot_index: int
    component: Component
    tier: ComponentTier


@dataclass(frozen=True, slots=True)
class ClaimStarbase:
    """Claim an operational, unowned base as a player foothold (§4.2, WP40).

    Costs `starbase.claim_cost` latinum; the base must be operational and unowned and sit
    in the player's sector. Sets ownership to the player (a forward foothold — services
    are Phase 5).
    """

    starbase_id: int


@dataclass(frozen=True, slots=True)
class BuyFighters:
    """Buy sector-fighter stock at the StarDock (§10, WP41)."""

    count: int


@dataclass(frozen=True, slots=True)
class BuyMines:
    """Buy space-mine stock at the StarDock (§10, WP41)."""

    count: int


@dataclass(frozen=True, slots=True)
class DeployFighters:
    """Deploy carried fighters to garrison the current sector (§10, WP41).

    `mode` is offensive / defensive / toll (a toll force levies `toll` latinum on hostile
    entrants). Never in the Core. Adds to (and re-modes) any player force already here.
    """

    count: int
    mode: str = "defensive"
    toll: int = 0


@dataclass(frozen=True, slots=True)
class DeployMines:
    """Deploy carried mines into the current sector (§10, WP41/WP56). Never in the Core.

    `kind` is "armid" (damage on entry) or "limpet" (attach + track). Both draw from the
    single carried `Ship.mines` stock.
    """

    count: int
    kind: str = "armid"


@dataclass(frozen=True, slots=True)
class DeployBeacon:
    """Plant a comms beacon in the current sector (§10, WP41).

    Costs `territory.beacon_price` latinum; one per sector (overwrite); never in the Core.
    """

    text: str


@dataclass(frozen=True, slots=True)
class BuyDevice:
    """Buy a special device (probe / interdictor / mine-deflector) at the StarDock (§10, WP56).

    Devices are counted in `Ship.devices` (not cargo). Priced from `config.devices`.
    """

    device_id: str


@dataclass(frozen=True, slots=True)
class LaunchProbe:
    """Send a consumable probe toward `dest_sector`, charting its path (§11, §14, WP56).

    Flies the shortest full-graph path up to the device's hop range, revealing each sector
    it traverses and reporting their contents — recon you buy. Lossy through hostile-held
    sectors. Consumes one `probe` device.
    """

    dest_sector: int


@dataclass(frozen=True, slots=True)
class ToggleInterdictor:
    """Engage / disengage the carried interdictor (§14, WP56).

    While engaged, NPC drift out of the player's sector is suppressed and encounter foes
    cannot disengage, at a daily turn tax. A stance, not a default. Requires the device.
    """


@dataclass(frozen=True, slots=True)
class RemoveLimpets:
    """Strip all attached limpet mines at a service point for a fee (§10, §4.2, WP56)."""


# --- corporations (DESIGN §4, WP66) ------------------------------------------


@dataclass(frozen=True, slots=True)
class FormCorp:
    """Charter a new corporation (pays `corp.form_fee`); the founder becomes CEO + sole member."""

    name: str
    tag: str


@dataclass(frozen=True, slots=True)
class InviteToCorp:
    """CEO invites a player to the corp — the first half of the two-step (consent) join."""

    invitee_player_id: int


@dataclass(frozen=True, slots=True)
class AcceptCorpInvite:
    """Accept a standing invite and join the corp (the invitee's consent — no press-ganging)."""

    corp_id: int


@dataclass(frozen=True, slots=True)
class LeaveCorp:
    """Leave the player's corp; the last member out dissolves it (assets re-key to the CEO)."""


@dataclass(frozen=True, slots=True)
class ExpelFromCorp:
    """CEO expels a member from the corp (the CEO cannot expel themselves — they dissolve instead)."""

    member_player_id: int


@dataclass(frozen=True, slots=True)
class CorpDeposit:
    """Deposit personal latinum into the corp bank (any member)."""

    amount: int


@dataclass(frozen=True, slots=True)
class CorpWithdraw:
    """Withdraw from the corp bank into personal latinum (CEO-gated — the shared purse)."""

    amount: int


@dataclass(frozen=True, slots=True)
class TransferPlanetToCorp:
    """Hand a member's owned world to the corp (shared holding) — an in-sector member action."""

    planet_id: int


@dataclass(frozen=True, slots=True)
class TransferPlanetFromCorp:
    """Return a corp-owned world to the CEO's personal ownership (CEO-gated)."""

    planet_id: int


@dataclass(frozen=True, slots=True)
class DeclareCorpWar:
    """CEO declares war on a rival corp — hostility is mutual-by-declaration (either side is enough)."""

    target_corp_id: int


@dataclass(frozen=True, slots=True)
class EndCorpWar:
    """CEO unilaterally withdraws from a war; a cooldown blocks immediate re-declaration."""

    target_corp_id: int


Command = (
    JoinGame
    | Warp | TravelTo | Dock | Trade | HaggleOffer | Deposit | Withdraw
    | BuyComponent | BuyShip | RepairAtDock
    | RecruitColonists | Colonize | SetAllocation
    | BuildCitadel | PlanetDeposit | PlanetWithdraw | InvadePlanet
    | InstallComponent | SwapComponent | Cannibalize | FieldPatch
    | Salvage | Descend | Explore | BuyGenesis | DeployGenesis
    | CombatAction | BuyMissiles | AttackPlayer | AttackSpecies
    | Hail | Converse | BuyAlienTech | BarterArtifact | AcceptLead
    | DeliverContract | AbandonContract | BuyRumor | PostNotice
    | AdvanceAdmission | JoinAlliance | ResignAlliance | PetitionCoreSeizure
    | AssaultStarbase | RepairStarbase | ClaimStarbase
    | BuyFighters | BuyMines | DeployFighters | DeployMines | DeployBeacon
    | BuyDevice | LaunchProbe | ToggleInterdictor | RemoveLimpets
    | FormCorp | InviteToCorp | AcceptCorpInvite | LeaveCorp | ExpelFromCorp
    | CorpDeposit | CorpWithdraw | TransferPlanetToCorp | TransferPlanetFromCorp
    | DeclareCorpWar | EndCorpWar
    | DevPatch  # dev/testing cheat (core.dev); recorded in the log like any command
)


# --- result -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReduceResult:
    """The events that occurred plus the new entities to upsert into state."""

    events: tuple[Event, ...] = ()
    players: tuple[Player, ...] = ()
    ships: tuple[Ship, ...] = ()
    ports: tuple[Port, ...] = ()
    planets: tuple[Planet, ...] = ()
    starbases: tuple[Starbase, ...] = ()
    discoveries: tuple[Discovery, ...] = ()
    species: tuple[AlienSpecies, ...] = ()  # cron-mutated species positions (WP16 drift)
    sectors: tuple[Sector, ...] = ()  # beacon-text updates (WP41)
    sector_forces: tuple[SectorForce, ...] = ()  # deployed fighters/mines (WP41)
    alliances: tuple[Alliance, ...] = ()  # bloc state changes (e.g. intrigue turns outward, WP51)
    corporations: tuple[Corporation, ...] = ()  # corp create/membership/bank/war changes (WP66)
    # Corp ids to delete (dissolution) — removed from state after the upserts (WP66).
    dissolved_corps: tuple[int, ...] = ()
    game: Game | None = None  # set by maintenance reducers (e.g. daily day-number bump)
    # A whole-book replacement of `state.port_orders` (WP47) — None means "unchanged",
    # a mapping means "replace the book". Unlike the entity tuples (which upsert), the
    # market book is regenerated in full each cycle, so it is swapped, not merged.
    port_orders: Mapping[int, tuple[PortOrder, ...]] | None = None
    # A whole-ring replacement of `state.notices` (WP58) — None means "unchanged". The
    # noticeboard is a capped ring the `PostNotice` reducer rebuilds, so it is swapped.
    notices: tuple[Notice, ...] | None = None


def apply_result(state: UniverseState, result: ReduceResult) -> None:
    """Upsert a reducer's new entities into the mutable container (sanctioned)."""
    for player in result.players:
        state.players[player.id] = player
    for ship in result.ships:
        state.ships[ship.id] = ship
    for port in result.ports:
        state.ports[port.id] = port
    for planet in result.planets:
        state.planets[planet.id] = planet
    for starbase in result.starbases:
        state.starbases[starbase.id] = starbase
    for discovery in result.discoveries:
        state.discoveries[discovery.id] = discovery
    for species in result.species:
        state.species[species.id] = species
    for sector in result.sectors:
        state.sectors[sector.id] = sector
    for force in result.sector_forces:
        if force.fighters <= 0 and force.armid_mines <= 0 and force.limpet_mines <= 0:
            state.sector_forces.pop(force.sector_id, None)  # spent forces clear out
        else:
            state.sector_forces[force.sector_id] = force
    for alliance in result.alliances:
        state.alliances[alliance.id] = alliance
    for corporation in result.corporations:
        state.corporations[corporation.id] = corporation
    for corp_id in result.dissolved_corps:
        state.corporations.pop(corp_id, None)
    if result.game is not None:
        state.game = result.game
    if result.port_orders is not None:
        state.port_orders = dict(result.port_orders)  # whole-book replacement (WP47)
    if result.notices is not None:
        state.notices = result.notices  # whole-ring replacement (WP58)


# --- reducers ---------------------------------------------------------------


def reduce(
    state: UniverseState, player_id: int, command: Command, config: GameConfig
) -> ReduceResult:
    """Validate `command` for `player_id` and return its delta + events."""
    match command:
        case JoinGame():
            return _join_game(state, player_id, command, config)
        case Warp():
            return _warp(state, player_id, command, config)
        case TravelTo():
            return _travel(state, player_id, command, config)
        case Dock():
            return _dock(state, player_id)
        case Trade():
            return _trade(state, player_id, command, config)
        case HaggleOffer():
            return _haggle(state, player_id, command, config)
        case Deposit():
            return _bank(state, player_id, command.amount, withdraw_=False)
        case Withdraw():
            return _bank(state, player_id, command.amount, withdraw_=True)
        case BuyComponent():
            return _buy_component(state, player_id, command, config)
        case BuyShip():
            return _buy_ship(state, player_id, command, config)
        case RepairAtDock():
            return _repair_at_dock(state, player_id, command, config)
        case RecruitColonists():
            return _recruit_colonists(state, player_id, command, config)
        case Colonize():
            return _colonize(state, player_id, command, config)
        case SetAllocation():
            return _set_allocation(state, player_id, command, config)
        case BuildCitadel():
            return _build_citadel(state, player_id, command, config)
        case PlanetDeposit():
            return _planet_bank(state, player_id, command.planet_id, command.amount,
                                config, withdraw_=False)
        case PlanetWithdraw():
            return _planet_bank(state, player_id, command.planet_id, command.amount,
                                config, withdraw_=True)
        case InvadePlanet():
            return _invade_planet(state, player_id, command, config)
        case InstallComponent():
            return _install_component(state, player_id, command, config)
        case SwapComponent():
            return _swap_component(state, player_id, command, config)
        case Cannibalize():
            return _cannibalize(state, player_id, command, config)
        case FieldPatch():
            return _field_patch(state, player_id, command, config)
        case Salvage():
            return _salvage(state, player_id, command, config)
        case Descend():
            return _descend(state, player_id, command, config)
        case Explore():
            return _explore(state, player_id, command, config)
        case BuyGenesis():
            return _buy_genesis(state, player_id, config)
        case DeployGenesis():
            return _deploy_genesis(state, player_id, command, config)
        case CombatAction():
            return _combat_action(state, player_id, command, config)
        case AttackPlayer():
            return _attack_player(state, player_id, command, config)
        case AttackSpecies():
            return _attack_species(state, player_id, command, config)
        case BuyMissiles():
            return _buy_missiles(state, player_id, command, config)
        case Hail():
            return _hail(state, player_id, command, config)
        case Converse():
            return _converse(state, player_id, command, config)
        case BuyAlienTech():
            return _buy_alien_tech(state, player_id, command, config)
        case BarterArtifact():
            return _barter_artifact(state, player_id, command, config)
        case AcceptLead():
            return _accept_lead(state, player_id, command, config)
        case DeliverContract():
            return _deliver_contract(state, player_id, command, config)
        case AbandonContract():
            return _abandon_contract(state, player_id, command, config)
        case BuyRumor():
            return _buy_rumor(state, player_id, config)
        case PostNotice():
            return _post_notice(state, player_id, command, config)
        case AdvanceAdmission():
            return _advance_admission(state, player_id, command, config)
        case JoinAlliance():
            return _join_alliance(state, player_id, command, config)
        case ResignAlliance():
            return _resign_alliance(state, player_id, command, config)
        case PetitionCoreSeizure():
            return _petition_core_seizure(state, player_id, command, config)
        case AssaultStarbase():
            return _assault_starbase(state, player_id, command, config)
        case RepairStarbase():
            return _repair_starbase(state, player_id, command, config)
        case ClaimStarbase():
            return _claim_starbase(state, player_id, command, config)
        case BuyFighters():
            return _buy_fighters(state, player_id, command, config)
        case BuyMines():
            return _buy_mines(state, player_id, command, config)
        case DeployFighters():
            return _deploy_fighters(state, player_id, command, config)
        case DeployMines():
            return _deploy_mines(state, player_id, command, config)
        case DeployBeacon():
            return _deploy_beacon(state, player_id, command, config)
        case BuyDevice():
            return _buy_device(state, player_id, command, config)
        case LaunchProbe():
            return _launch_probe(state, player_id, command, config)
        case ToggleInterdictor():
            return _toggle_interdictor(state, player_id, config)
        case RemoveLimpets():
            return _remove_limpets(state, player_id, config)
        case FormCorp():
            return _form_corp(state, player_id, command, config)
        case InviteToCorp():
            return _invite_to_corp(state, player_id, command, config)
        case AcceptCorpInvite():
            return _accept_corp_invite(state, player_id, command, config)
        case LeaveCorp():
            return _leave_corp(state, player_id, config)
        case ExpelFromCorp():
            return _expel_from_corp(state, player_id, command, config)
        case CorpDeposit():
            return _corp_bank(state, player_id, command.amount, config, withdraw_=False)
        case CorpWithdraw():
            return _corp_bank(state, player_id, command.amount, config, withdraw_=True)
        case TransferPlanetToCorp():
            return _transfer_planet(state, player_id, command.planet_id, config, to_corp=True)
        case TransferPlanetFromCorp():
            return _transfer_planet(state, player_id, command.planet_id, config, to_corp=False)
        case DeclareCorpWar():
            return _declare_corp_war(state, player_id, command, config)
        case EndCorpWar():
            return _end_corp_war(state, player_id, command, config)
        case DevPatch():
            return apply_dev_patch(state, player_id, command, config)
        case _ as unreachable:
            assert_never(unreachable)


def _player(state: UniverseState, player_id: int) -> Player:
    player = state.players.get(player_id)
    if player is None:
        raise MovementError(f"no such player {player_id}")
    return player


def _ship(state: UniverseState, player: Player) -> Ship:
    return state.ships[player.ship_id]


def _spatial(state: UniverseState, sector_id: int) -> int:
    """The player-facing spatial id for an internal sector id (§5.1), or the raw id if unmapped.

    Error messages that reach the player must speak in spatial ids, never internal ones; the
    map exists on the state, so this stays pure (no server/display-layer dependency).
    """
    return state.spatial_ids.get(sector_id, sector_id)


def _resolve_start_sector(
    state: UniverseState, config: GameConfig, dock_sector: int | None
) -> int:
    """Resolve the configured start sector (DESIGN §5): the StarDock, a seeded random
    sector, or an explicit id. "random" draws from a *dedicated* sub-RNG so it never
    perturbs the build-RNG order the golden-master replays are keyed off."""
    start_cfg = config.bigbang.start_sector
    if start_cfg == "stardock":
        return dock_sector if dock_sector is not None else min(state.sectors)
    if start_cfg == "random":
        return random.Random(f"{state.game.seed}-start").choice(sorted(state.sectors))
    return start_cfg if start_cfg in state.sectors else 1


def _join_game(
    state: UniverseState, player_id: int, command: JoinGame, config: GameConfig
) -> ReduceResult:
    """Enroll `player_id`: a starter hull at the config start sector, starting
    balances/turns, membership of the Core's governing alliance, and the StarDock
    auto-known as a pre-explored route (DESIGN §3, §5 step 7).

    Player creation lives here — not in `bigbang.populate` — so a player is a recorded
    command that `rebuild` replays, and multiple players can join one universe. The
    block makes no build-RNG draw, so universe generation stays bit-identical.
    """
    if player_id in state.players:
        raise MovementError(f"player {player_id} already joined")

    dock_sector = next(
        (p.sector_id for p in state.ports.values() if p.klass == PortClass.STARDOCK), None
    )
    start_sector = _resolve_start_sector(state, config, dock_sector)

    # The player hull carries the engine-room model (§4.1): build its subsystems from
    # the class layout, then derive-on-write its aspect scalars so the stored
    # shields/warp/combat match the slotted parts (flat config values are the NPC
    # fallback / caps). The Trailblazer's minimal layout derives the Phase-1 flat numbers.
    ship_id = max(state.ships, default=0) + 1
    sc = config.starter_ship
    ship = apply_derived(
        Ship(
            id=ship_id, type_id=sc.id, name=sc.name, owner_player_id=player_id,
            sector_id=start_sector, holds_total=sc.holds_total,
            hull_current=sc.hull_max, hull_max=sc.hull_max, shields=sc.shields_max,
            warp_speed=sc.warp_speed, combat_speed=sc.combat_speed,
            cloak_rating=sc.cloak_rating, sensor_rating=sc.sensor_rating,
            missiles=sc.missiles,
            turns_per_warp=sc.turns_per_warp, colonist_capacity=sc.colonist_capacity,
            subsystems=build_subsystems(sc),
        ),
        config,
    )
    # StarDock is an auto-known route: the shortest path from the start sector to the
    # dock opens pre-explored so the opening signpost is actionable on turn one; the
    # rest stays fogged. Recorded as the breadcrumb chain so the way back reads
    # correctly. Starting *at* the dock collapses to a single explored sector.
    dock_route = (
        shortest_path(state.adjacency, start_sector, dock_sector)
        if dock_sector is not None else None
    ) or [start_sector]
    entered_from = {dock_route[i + 1]: dock_route[i] for i in range(len(dock_route) - 1)}
    player = Player(
        id=player_id, name=command.name, ship_id=ship_id,
        latinum=config.economy.starting_latinum, bank_balance=config.economy.starting_bank,
        turns_remaining=config.turns_per_day,
        alliance_id=state.game.core_governing_alliance_id,
        explored_sectors=frozenset(dock_route), entered_from=entered_from,
    )
    return ReduceResult(players=(player,), ships=(ship,))


def _docked_port(state: UniverseState, ship: Ship) -> Port:
    port = state.port_in_sector(ship.sector_id)
    if port is None:
        raise MovementError("no port in this sector")
    return port


def _detect_in_sector(
    state: UniverseState, detected: frozenset[int], sensor_rating: int,
    sector_id: int, player_id: int, config: GameConfig,
) -> tuple[frozenset[int], tuple[Event, ...]]:
    """Sensor-detect the hidden open-space finds in `sector_id` **on entry** (§7, WP5).

    Pure and deterministic (no RNG): a hidden find is revealed when effective sensor
    rating clears its tier difficulty (a nebula here dims that). The result is
    snapshotted into the player's `detected` set, so later sensor upgrades only help
    on re-entry. Returns the updated set plus one `DiscoveryDetected` per new reveal;
    obvious finds are never added (the projection always shows them).
    """
    if config.discovery is None:
        return detected, ()
    in_nebula = sector_has_nebula(state, sector_id)
    revealed = set(detected)
    events: list[Event] = []
    for d in state.discoveries.values():
        if d.planet_id is not None or d.sector_id != sector_id or d.id in revealed or not d.hidden:
            continue
        if is_detectable(d, sensor_rating, in_nebula=in_nebula, config=config):
            revealed.add(d.id)
            events.append(DiscoveryDetected(player_id, d.id, d.kind.value, d.rarity_tier.name))
    if not events:
        return detected, ()
    return frozenset(revealed), tuple(events)


def _warp(state: UniverseState, player_id: int, cmd: Warp, config: GameConfig) -> ReduceResult:
    player = _player(state, player_id)
    _require_no_encounter(player)
    ship = _ship(state, player)
    if not can_warp(state.adjacency, ship.sector_id, cmd.to_sector):
        raise MovementError(
            f"no warp from {_spatial(state, ship.sector_id)} to {_spatial(state, cmd.to_sector)}")
    cost = ship.turns_per_warp
    if player.turns_remaining < cost:
        raise MovementError("out of turns")
    from_sector = ship.sector_id
    moved_ship = replace(ship, sector_id=cmd.to_sector)
    one_way = from_sector not in state.adjacency.get(cmd.to_sector, ())
    detected, det_events = _detect_in_sector(
        state, player.detected, ship.sensor_rating, cmd.to_sector, player_id, config)
    law_events = _core_law_events(state, player, from_sector, cmd.to_sector, config)
    player, moved_ship, encounter, _halt, entry_events, forces = _entry_effects(
        state, player, moved_ship, cmd.to_sector, config)
    new_player = replace(
        player,
        turns_remaining=player.turns_remaining - cost,
        explored_sectors=player.explored_sectors | frozenset({cmd.to_sector}),
        entered_from={**player.entered_from, cmd.to_sector: from_sector},
        detected=detected,
        active_encounter=encounter,
        contact_session=None,  # movement ends any conversation visit (§6.7 H1)
    )
    # Any escorted merchant sitting where we depart from rides along (§6.7, WP57).
    new_player, convoy, convoy_events = _convoy_step(state, new_player, from_sector, cmd.to_sector)
    return ReduceResult(
        events=(Warped(player_id, from_sector, cmd.to_sector, cost, one_way),
                *det_events, *law_events, *entry_events, *convoy_events),
        players=(new_player,),
        ships=(moved_ship,),
        species=tuple(convoy),
        sector_forces=tuple(forces),
    )


def _require_no_encounter(player: Player) -> None:
    """Movement, docking, and descent are rejected while an encounter is live (§10)."""
    if player.active_encounter is not None:
        raise MovementError("you are engaged — fight or flee first")


def _convoy_step(state: UniverseState, player: Player, from_sector: int, to_sector: int,
                 positions: dict[int, AlienSpecies] | None = None
                 ) -> tuple[Player, list[AlienSpecies], list[Event]]:
    """Move escorted merchants with one player hop and pay arrivals (§6.7, WP57 — interview 9).

    Wraps `contracts.advance_convoy`: relocates each convoyed merchant that sat in
    `from_sector`, completes an escort whose merchant thereby reaches its destination, and
    pays the reward through `apply_reward` (folded into the caller's `ReduceResult`, so
    convoy replays exactly). `positions` threads the merchant's live position through a
    multi-hop journey. Returns `(player, moved_merchants, events)`.
    """
    new_player, moved, completed = contracts.advance_convoy(
        state, player, from_sector, to_sector, state.game.day_number, positions)
    events: list[Event] = []
    for c in completed:
        new_player = contracts.apply_reward(new_player, c, state)
        events.append(ContractCompleted(player.id, c.id, c.kind, c.reward_slips))
    return new_player, moved, events


def _core_law_events(
    state: UniverseState, player: Player, from_sector: int, to_sector: int, config: GameConfig,
) -> tuple[Event, ...]:
    """Core-law basics (WP27): a criminal crossing into Core Space is put on notice.

    One notice per crossing (a non-Core → Core hop), not per intra-Core move. A
    warning only — engagement-on-sight and governor-standing gating land in WP38.
    """
    if not is_criminal(player, config.aliens):
        return ()
    if state.sectors[to_sector].is_galactic_core and not state.sectors[from_sector].is_galactic_core:
        return (CoreLawNotice(player.id, to_sector),)
    return ()


def _roll_encounter(
    state: UniverseState, player: Player, ship: Ship, sector_id: int, config: GameConfig,
) -> tuple[Player, Encounter | None, bool, tuple[Event, ...]]:
    """The §10 encounter roll on entering `sector_id` (WP24).

    Returns `(player, encounter, halt, events)`: `encounter` goes onto
    `Player.active_encounter` on a violence opener; `halt` stops a multi-hop journey
    (any *detected* encounter halts — a greeting hands off to the contact screen, a
    fight to the encounter screen); an undetected slip-away neither halts nor stores.
    A violence opener also speaks its beat (`combat_open` / `betrayal`, §6.7 WP31) —
    the returned player carries the advanced recency ring. Draws from `state.rng`
    inside the reducer (H4), so a journey replays exactly.
    """
    # A hostile operational base defends its system on sight (§4.2, WP40) — deterministic,
    # checked before the ship-encounter roll so it never perturbs the RNG draw order (H4).
    base_enc = encounters.roll_base_defense(state, player, ship, sector_id, config)
    if base_enc is not None:
        band = state.sectors[sector_id].distance_band
        started = EncounterStarted(player.id, 0, sector_id, True, len(base_enc.foes), band)
        return player, base_enc, True, (started,)
    # The citadel gun is the ladder's second rung (§4.2, WP54): it defends only once no
    # operational base does, so razing the base exposes it. Deterministic, like base defense.
    gun_enc = encounters.roll_citadel_defense(state, player, ship, sector_id, config)
    if gun_enc is not None:
        band = state.sectors[sector_id].distance_band
        started = EncounterStarted(player.id, 0, sector_id, True, len(gun_enc.foes), band)
        return player, gun_enc, True, (started,)
    roll = encounters.roll_encounter(state, player, ship, sector_id, config, state.rng)
    if roll is None:
        return player, None, False, ()
    if not roll.detected:
        return player, None, False, (EncounterEvaded(player.id, roll.species.id, sector_id),)
    band = state.sectors[sector_id].distance_band
    pack_size = len(roll.encounter.foes) if roll.encounter is not None else 0
    events: list[Event] = [EncounterStarted(
        player.id, roll.species.id, sector_id, roll.hostile, pack_size, band)]
    if (roll.encounter is not None and roll.encounter.speech_context is not None
            and config.roster is not None):
        player, spoke = _combat_speak(
            state, player, roll.species, roll.encounter.speech_context, config,
            dialogue_facts.encounter_facts(roll.encounter))
        events.append(spoke)
    return player, roll.encounter, True, tuple(events)


def _territory_entry(
    state: UniverseState, player: Player, ship: Ship, sector_id: int, config: GameConfig,
) -> tuple[Ship, Encounter | None, list[SectorForce], list[Event], bool]:
    """Territory hazards on entering `sector_id` (§10, WP41): black hole, mines, fighters.

    Deterministic (no RNG). A black hole deals a flat gravity toll; a hostile mine field
    detonates (shields absorb, mines spent); a hostile fighter garrison forces an
    engagement (a combat encounter — engage-or-retreat, reconciled at the fight's end).
    A lethal hazard routes through the WP26 escape pod (§10, WP75): hull 0 pods the
    player on the spot, and no engagement spawns over a wreck. Returns
    `(ship, encounter, force_updates, events, destroyed)`.
    """
    tc = config.territory
    events: list[Event] = []
    forces: list[SectorForce] = []

    def _apply(hull_raw: int, source: str) -> None:
        nonlocal ship
        hit = min(ship.hull_current, max(0, hull_raw))
        if hit > 0:
            ship = replace(ship, hull_current=ship.hull_current - hit)
            events.append(HazardDamageEvent(player.id, sector_id, source, hit))

    def _podded() -> bool:
        nonlocal ship
        if ship.hull_current > 0:
            return False
        events.append(ShipDestroyed(player.id, 0, sector_id, ship.type_id))
        ship = _escape_pod(ship, config)
        return True

    if tc.black_hole_damage > 0 and territory.sector_has_black_hole(state, sector_id):
        _apply(tc.black_hole_damage, "black_hole")
        if _podded():
            return ship, None, forces, events, True

    force = state.sector_forces.get(sector_id)
    encounter: Encounter | None = None
    if force is not None and territory.force_hostile_to_player(
            state, force, player, pvp_enabled=config.pvp.enabled):
        if force.armid_mines > 0:
            # A carried mine-deflector absorbs armid mines one-for-one (§10, WP56); shields
            # then soak the remaining blast before the hull takes it.
            deflectors = ship.devices.get(tc.mine_deflector_device, 0)
            effective = max(0, force.armid_mines - deflectors)
            raw = effective * tc.mine_damage
            _apply(raw - min(ship.shields, raw), "mine")
        if force.limpet_mines > 0:
            # Limpets attach to the entrant, tagged to the owner so their hunters track it.
            tag = territory.owner_tag(force.owner)
            ship = replace(ship, limpets={
                **ship.limpets, tag: ship.limpets.get(tag, 0) + force.limpet_mines})
        if force.armid_mines > 0 or force.limpet_mines > 0:
            force = replace(force, armid_mines=0, limpet_mines=0)  # both piles are spent
            forces.append(force)
        if _podded():
            return ship, None, forces, events, True
        if force.fighters > 0:
            encounter = Encounter(
                species_id=0, sector_id=sector_id, foes=(territory.fighter_foe(force, config),),
                round=0, player_shields=ship.shields, detected=True, speech_context="combat_open",
            )
    return ship, encounter, forces, events, False


def _entry_effects(
    state: UniverseState, player: Player, ship: Ship, sector_id: int, config: GameConfig,
) -> tuple[Player, Ship, Encounter | None, bool, list[Event], list[SectorForce]]:
    """Everything that happens on *entering* `sector_id`: territory then the encounter roll.

    Territory hazards (WP41) apply first and can spawn a fighter engagement (which halts,
    like a base defense); otherwise the §4.2/§24 base-defense + ship-encounter roll runs.
    A lethal hazard pods the player (§10, WP75) and halts the journey — no encounter
    rolls over a wreck. Returns the (possibly damaged) ship and any deployed-force
    updates alongside the roll.
    """
    ship, t_enc, forces, events, destroyed = _territory_entry(state, player, ship, sector_id, config)
    if destroyed:
        return player, ship, None, True, events, forces
    if t_enc is not None:
        band = state.sectors[sector_id].distance_band
        events.append(EncounterStarted(player.id, 0, sector_id, True, len(t_enc.foes), band))
        return player, ship, t_enc, True, events, forces
    player, encounter, halt, enc_events = _roll_encounter(state, player, ship, sector_id, config)
    events.extend(enc_events)
    return player, ship, encounter, halt, events, forces


def _travel(state: UniverseState, player_id: int, cmd: TravelTo, config: GameConfig) -> ReduceResult:
    """Multi-hop warp along a *known* route (§9, §11, §6.7, WP-C).

    Route-locked to charted space, with one exception: a **logged coordinate lead** is the
    map (§6.7), so the player may auto-travel over the *full* graph to a destination they hold
    a lead for — the computer has the coordinates and plots the course, charting each hop as it
    flies. Everywhere else still routes through already-explored sectors only, so exploration
    is not trivialised. The journey applies hop-by-hop (one `Warped` per hop), halting early if
    turns run out or the §10 encounter roll fires — the journey stops **at the interrupted
    hop** (the sector is entered; a detected encounter then takes over, WP24).
    """
    player = _player(state, player_id)
    _require_no_encounter(player)
    ship = _ship(state, player)
    # A tip's coordinates unlock full-graph plotting *from the sector it was obtained in*; away
    # from that origin (or with no lead) the route is locked to already-charted space (§6.7).
    lead = next((ld for ld in player.leads if ld.sector_id == cmd.to_sector), None)
    at_origin = lead is not None and lead.origin_sector == ship.sector_id
    allowed = None if at_origin else set(player.explored_sectors)
    path = shortest_path(state.adjacency, ship.sector_id, cmd.to_sector, allowed=allowed)
    if path is None:
        if lead is not None:  # holds the tip but can't reach it from here — point them home
            raise MovementError(f"return to {_spatial(state, lead.origin_sector)} to follow that lead")
        raise MovementError(f"no uncovered route to {_spatial(state, cmd.to_sector)}")
    hops = path[1:]
    if not hops:
        raise MovementError("already in that sector")
    cost = ship.turns_per_warp
    if player.turns_remaining < cost:
        raise MovementError("out of turns")

    events: list[Event] = []
    current = ship.sector_id
    turns = player.turns_remaining
    explored = player.explored_sectors
    entered = dict(player.entered_from)
    detected = player.detected
    encounter: Encounter | None = None
    ship_now = ship
    force_updates: dict[int, SectorForce] = {}
    convoy_updates: dict[int, AlienSpecies] = {}
    for nxt in hops:
        if turns < cost:
            break
        turns -= cost
        one_way = current not in state.adjacency.get(nxt, ())
        events.append(Warped(player_id, current, nxt, cost, one_way))
        entered[nxt] = current
        explored = explored | frozenset({nxt})
        detected, det_events = _detect_in_sector(
            state, detected, ship_now.sensor_rating, nxt, player_id, config)
        events.extend(det_events)
        events.extend(_core_law_events(state, player, current, nxt, config))
        # Escorted merchants ride each departing hop alongside the player (§6.7, WP57).
        player, convoy, convoy_events = _convoy_step(state, player, current, nxt, convoy_updates)
        for merchant in convoy:
            convoy_updates[merchant.id] = merchant
        events.extend(convoy_events)
        current = nxt
        ship_now = replace(ship_now, sector_id=nxt)
        # Territory hazards + the §10 encounter roll — the journey halts *at* the
        # interrupted hop (WP24/WP41).
        player, ship_now, encounter, halt, entry_events, forces = _entry_effects(
            state, player, ship_now, nxt, config)
        events.extend(entry_events)
        for f in forces:
            force_updates[f.sector_id] = f
        if halt:
            break

    new_player = replace(player, turns_remaining=turns, explored_sectors=explored,
                         entered_from=entered, detected=detected,
                         active_encounter=encounter,
                         contact_session=None)  # movement ends any visit (§6.7 H1)
    return ReduceResult(events=tuple(events), players=(new_player,), ships=(ship_now,),
                        species=tuple(convoy_updates.values()),
                        sector_forces=tuple(force_updates.values()))


def _dock(state: UniverseState, player_id: int) -> ReduceResult:
    player = _player(state, player_id)
    _require_no_encounter(player)
    ship = _ship(state, player)
    port = _docked_port(state, ship)
    # The Core StarDock is the governor's haven — a hunted player (§6.3 hostile-governor)
    # is turned away at the airlock, which denies every dock-gated service (trade,
    # recruitment, bank) at one lever rather than per command (WP52).
    if (port.klass is PortClass.STARDOCK
            and state.sectors[ship.sector_id].is_galactic_core
            and governor_hostile(state, player)):
        raise MovementError("the governor's forces bar you from the Core StarDock")
    if player.turns_remaining < 1:
        raise MovementError("out of turns")
    new_player = replace(player, turns_remaining=player.turns_remaining - 1)
    return ReduceResult(
        events=(Docked(player_id, ship.sector_id, port.id),), players=(new_player,)
    )


def _trade(
    state: UniverseState, player_id: int, cmd: Trade, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    port = _docked_port(state, ship)
    line = port.line(cmd.commodity)
    if line is None:
        raise EconomyError(f"port does not trade {cmd.commodity.value}")
    price = cmd.unit_price if cmd.unit_price is not None else port_unit_price(line, config.economy)
    out = execute_trade(
        port=port, ship=ship, player=player,
        commodity=cmd.commodity, units=cmd.units, unit_price=price,
        port_purse=config.economy.market.enabled,
    )
    return ReduceResult(
        events=(Traded(player_id, port.id, cmd.commodity, out.mode, out.units,
                       out.unit_price, out.total, out.requested),),
        players=(out.player,), ships=(out.ship,), ports=(out.port,),
    )


def _haggle(
    state: UniverseState, player_id: int, cmd: HaggleOffer, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    port = _docked_port(state, ship)
    line = port.line(cmd.commodity)
    if line is None:
        raise EconomyError(f"port does not trade {cmd.commodity.value}")
    fair = port_unit_price(line, config.economy)
    hg = config.economy.haggling
    # Per-day, per-port attempt history drives the patience penalty + the `max_rejections`
    # close. Reset by the daily cron, so it reconstructs exactly under replay (WP13).
    attempts = player.haggle_attempts.get(port.id, 0)
    if attempts >= hg.max_rejections:
        # Negotiation is closed for the day — the port holds firm at the fair price.
        haggled = Haggled(player_id, port.id, cmd.commodity, HaggleStatus.EXHAUSTED.value, fair)
        return ReduceResult(events=(haggled,))

    result = resolve_haggle(
        fair, cmd.counter_price, line.mode, state.rng,
        insult_frac=hg.insult_frac, history_penalty=hg.history_penalty, recent_attempts=attempts,
    )
    haggled = Haggled(player_id, port.id, cmd.commodity, result.status.value, result.price)
    if result.status is HaggleStatus.ACCEPTED and result.price is not None:
        out = execute_trade(
            port=port, ship=ship, player=player,
            commodity=cmd.commodity, units=cmd.units, unit_price=result.price,
            port_purse=config.economy.market.enabled,
        )
        traded = Traded(player_id, port.id, cmd.commodity, out.mode, out.units,
                        out.unit_price, out.total, out.requested)
        return ReduceResult(
            events=(haggled, traded), players=(out.player,), ships=(out.ship,), ports=(out.port,),
        )
    # A non-accepted offer wears the port's patience: bump the attempt counter.
    new_player = replace(player, haggle_attempts={**player.haggle_attempts, port.id: attempts + 1})
    return ReduceResult(events=(haggled,), players=(new_player,))


def _bank(
    state: UniverseState, player_id: int, amount: int, *, withdraw_: bool
) -> ReduceResult:
    # Banking stays ungated at the reducer (WP53): the plan's "rejection conditions only
    # widen" rule bars narrowing it, and it was never `_stardock`-gated. It is *surfaced*
    # as a service at StarDock and player bases (`services.BANKING`) but the account is
    # reachable anywhere, riding the same `Player.bank_balance` invariants.
    player = _player(state, player_id)
    new_player = withdraw(player, amount) if withdraw_ else deposit(player, amount)
    kind = "withdraw" if withdraw_ else "deposit"
    return ReduceResult(
        events=(Banked(player_id, kind, amount, new_player.bank_balance),),
        players=(new_player,),
    )


# --- StarDock services: buy component / buy hull / repair (§8, §11) ---------


def _stardock(state: UniverseState, ship: Ship) -> Port:
    """The StarDock in the ship's current sector, or raise (services are dock-only)."""
    port = _docked_port(state, ship)
    if port.klass is not PortClass.STARDOCK:
        raise EconomyError("that service is offered only at a StarDock")
    return port


def _buy_component(
    state: UniverseState, player_id: int, cmd: BuyComponent, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    sp = require_service(state, player, ship, COMPONENTS, config)
    base_price = config.economy.component_price(cmd.tier)
    if base_price is None:
        raise EconomyError(f"tier {cmd.tier.name} components are barter-only, not for sale")
    if cmd.component.value not in config.hardware.components or cmd.tier.name not in config.hardware.tiers:
        raise EconomyError(f"this dock does not stock {cmd.component.value} (tier {cmd.tier.name})")
    # A forward base stocks only the configured tiers (default I/II; §4.2, WP53) and
    # charges the frontier markup; a StarDock stocks everything at fee_frac 1.0.
    if sp.kind == "player_base" and config.starbase is not None:
        if cmd.tier.name not in config.starbase.services.component_stock_tiers:
            raise EconomyError(f"this base does not stock tier {cmd.tier.name} components")
    price = round(base_price * sp.fee_frac)
    if player.latinum < price:
        raise EconomyError("insufficient latinum for the component")
    if ship.holds_free < 1:
        raise EconomyError("no free hold for the component — sell cargo first")
    key = (cmd.component, cmd.tier)
    new_components = {**ship.components, key: ship.components.get(key, 0) + 1}
    new_ship = replace(ship, components=new_components)
    new_player = replace(player, latinum=player.latinum - price)
    return ReduceResult(
        events=(ComponentPurchased(player_id, cmd.component.value, cmd.tier.name, price),),
        players=(new_player,), ships=(new_ship,),
    )


def _buy_ship(
    state: UniverseState, player_id: int, cmd: BuyShip, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    try:
        new_class = config.ship_class(cmd.ship_class_id)
    except KeyError as exc:
        raise EconomyError(f"no such hull {cmd.ship_class_id!r}") from exc
    if new_class.id == ship.type_id:
        raise EconomyError("you already fly that hull")
    if new_class.price <= 0:
        raise EconomyError("that hull is not for sale")

    # Trade-in credit for the current hull (the starter hull is free → 0 credit).
    old_class = config.ship_class(ship.type_id)
    trade_in = round(old_class.price * config.economy.ship_trade_in_frac)
    net_cost = new_class.price - trade_in
    if player.latinum < net_cost:
        raise EconomyError("insufficient latinum for the hull, even after trade-in")
    if ship.colonists > new_class.colonist_capacity:
        raise EconomyError("the new hull has too few berths for your colonists — settle them first")

    # The old hull's installed components return to loose inventory; the new hull
    # arrives with its own fresh base slots. Cargo and existing loose parts carry over.
    returned = _strip_installed(ship)
    merged = dict(ship.components)
    for key, count in returned.items():
        merged[key] = merged.get(key, 0) + count
    new_ship = apply_derived(replace(
        ship, type_id=new_class.id, name=new_class.name, holds_total=new_class.holds_total,
        hull_max=new_class.hull_max, hull_current=new_class.hull_max,
        cloak_rating=new_class.cloak_rating, sensor_rating=new_class.sensor_rating,
        shields=new_class.shields_max, warp_speed=new_class.warp_speed,
        combat_speed=new_class.combat_speed, turns_per_warp=new_class.turns_per_warp,
        colonist_capacity=new_class.colonist_capacity,
        missiles=ship.missiles + new_class.missiles,  # ammo carries over + hull loadout
        subsystems=build_subsystems(new_class), components=merged,
    ), config)
    if new_ship.holds_used > new_ship.holds_total:
        raise EconomyError(
            "returned components plus cargo exceed the new hull's holds — "
            "sell components down to make room first"
        )
    new_player = replace(player, latinum=player.latinum - net_cost)
    return ReduceResult(
        events=(ShipPurchased(player_id, new_class.id, net_cost, trade_in),),
        players=(new_player,), ships=(new_ship,),
    )


def _strip_installed(ship: Ship) -> dict[tuple[Component, ComponentTier], int]:
    """Count every component installed in the hull's subsystems (for trade-in return)."""
    counts: dict[tuple[Component, ComponentTier], int] = {}
    for sub in (ship.subsystems or {}).values():
        for slot in sub.slots:
            if slot is not None:
                key = (slot.kind, slot.tier)
                counts[key] = counts.get(key, 0) + 1
    return counts


def _repair_at_dock(
    state: UniverseState, player_id: int, cmd: RepairAtDock, config: GameConfig
) -> ReduceResult:
    """Pay the StarDock to restore a knocked-out component (§4.1, §8).

    Inert in Phase 2 (nothing is knocked out yet); the path is exercised in Phase 3.
    """
    player = _player(state, player_id)
    ship = _engine_ship(state, player_id)
    sp = require_service(state, player, ship, REPAIR, config)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is empty — nothing to repair")
    if not comp.knocked_out:
        raise EngineRoomError("component is not knocked out")
    price = config.economy.component_price(comp.tier) or config.economy.tier_ii_component_latinum
    cost = round(price * config.economy.repair_cost_frac * sp.fee_frac)
    if player.latinum < cost:
        raise EconomyError("insufficient latinum for the repair")
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index, replace(comp, knocked_out=False))
    new_ship = apply_derived(new_ship, config)
    new_player = replace(player, latinum=player.latinum - cost)
    return ReduceResult(
        events=(Repaired(player_id, cmd.subsystem.value, cmd.slot_index),),
        players=(new_player,), ships=(new_ship,),
    )


# --- colonists: recruit / colonize / allocation (§4.2, §8) ------------------


def _even_allocation() -> dict[Commodity, float]:
    """An equal split of production over the trio — the default for a new colony."""
    share = 1.0 / len(Commodity)
    return {c: share for c in Commodity}


def _recruit_colonists(
    state: UniverseState, player_id: int, cmd: RecruitColonists, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    if cmd.count <= 0:
        raise EconomyError("recruit count must be positive")
    free = ship.colonist_capacity - ship.colonists
    if free <= 0:
        raise EconomyError("no colonist berths free")
    count = min(cmd.count, free)  # clamp to the ship's separate occupancy limit (§4.2)

    if cmd.from_planet is None:
        # StarDock recruitment office — a per-head latinum incentive (not a purchase).
        _stardock(state, ship)
        cost = count * config.economy.colonist_incentive
        if player.latinum < cost:
            raise EconomyError("insufficient latinum for the recruitment incentive")
        new_player = replace(player, latinum=player.latinum - cost)
        new_ship = replace(ship, colonists=ship.colonists + count)
        return ReduceResult(
            events=(ColonistsRecruited(player_id, "stardock", count, cost),),
            players=(new_player,), ships=(new_ship,),
        )

    # Emigration from an inhabited world in orbit (the disposition gate lands in WP7).
    planet = state.planets.get(cmd.from_planet)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such world here to recruit from")
    if planet.inhabited_by_species_id is None:
        raise EconomyError("that world has no population to emigrate")
    new_ship = replace(ship, colonists=ship.colonists + count)
    return ReduceResult(
        events=(ColonistsRecruited(player_id, "emigration", count, 0),), ships=(new_ship,),
    )


def _colonize(
    state: UniverseState, player_id: int, cmd: Colonize, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    planet = state.planets.get(cmd.planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such world in this sector")
    if planet.owner.is_owned:
        raise EconomyError("that world is already claimed")  # Core worlds are governor-owned
    if not is_colonizable(planet.planet_type, config):
        raise EconomyError(f"a {planet.planet_type} world cannot be colonized")
    if cmd.colonists <= 0:
        raise EconomyError("must land at least one colonist")
    if cmd.colonists > ship.colonists:
        raise EconomyError("not enough colonists aboard")
    new_ship = replace(ship, colonists=ship.colonists - cmd.colonists)
    new_planet = replace(
        planet, owner=Ownership("player", player_id),
        colonists=planet.colonists + cmd.colonists,
        allocation=planet.allocation or _even_allocation(),
    )
    return ReduceResult(
        events=(Colonized(player_id, planet.id, cmd.colonists),),
        ships=(new_ship,), planets=(new_planet,),
    )


def _set_allocation(
    state: UniverseState, player_id: int, cmd: SetAllocation, config: GameConfig
) -> ReduceResult:
    _player(state, player_id)
    planet = state.planets.get(cmd.planet_id)
    if planet is None:
        raise EconomyError("no such world")
    if not corp.player_owns(state, planet.owner, player_id):
        raise EconomyError("you do not own that world")
    alloc = {c: float(cmd.allocation.get(c.value, 0.0)) for c in Commodity}
    fighter = max(0.0, float(cmd.fighter))
    total = sum(alloc.values()) + fighter
    if total <= 0:
        raise EconomyError("allocation must be positive")
    # Normalize the trio + fighter share together so they sum to 1.0 (§4.2 invariant, WP55).
    normalized = {c: v / total for c, v in alloc.items()}
    return ReduceResult(planets=(replace(
        planet, allocation=normalized, fighter_allocation=fighter / total),))


# --- citadels: build ladder + treasury (§4.2, WP54) -------------------------


def _owned_planet_here(state: UniverseState, player_id: int, planet_id: int) -> Planet:
    """The player-owned planet in the ship's sector, or raise (citadel ops gate, WP54)."""
    ship = _ship(state, _player(state, player_id))
    planet = state.planets.get(planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such world in this sector")
    if not corp.player_owns(state, planet.owner, player_id):
        raise EconomyError("you do not own that world")
    return planet


def _build_citadel(
    state: UniverseState, player_id: int, cmd: BuildCitadel, config: GameConfig
) -> ReduceResult:
    """Open a timed build of the next citadel level, paid up front (§4.2, WP54)."""
    player = _player(state, player_id)
    planet = _owned_planet_here(state, player_id, cmd.planet_id)
    target = planet.citadel_level + 1
    lc = citadels.level_config(config, target)  # raises CitadelError past the top
    if player.latinum < lc.cost_latinum:
        raise EconomyError(
            f"need {lc.cost_latinum} latinum for citadel level {target} (have {player.latinum})")
    # open_build validates the ladder + colonist gate + equipment stores and removes the
    # equipment; the latinum is burned here (a §8 sink). Both charged up front (interview #2).
    new_planet, target_level = citadels.open_build(planet, config)
    new_player = replace(player, latinum=player.latinum - lc.cost_latinum)
    return ReduceResult(
        events=(CitadelBuildStarted(player_id, planet.id, target_level),),
        players=(new_player,), planets=(new_planet,),
    )


def _planet_bank(
    state: UniverseState, player_id: int, planet_id: int, amount: int,
    config: GameConfig, *, withdraw_: bool
) -> ReduceResult:
    """Deposit/withdraw latinum against an owned citadel world's treasury (§4.2, WP54).

    Interest-free — the treasury's value is *location* (a bank in deep space), not yield
    (documented rationale). Conserves latinum: it moves between the player's purse and the
    planet's `treasury`, never minted. Requires a level-1+ citadel (the treasury it grants).
    """
    player = _player(state, player_id)
    planet = _owned_planet_here(state, player_id, planet_id)
    if planet.citadel_level < 1:
        raise EconomyError("this world has no citadel treasury (build level 1 first)")
    if amount <= 0:
        raise EconomyError("amount must be positive")
    if withdraw_:
        if planet.treasury < amount:
            raise EconomyError("the treasury does not hold that much")
        new_player = replace(player, latinum=player.latinum + amount)
        new_planet = replace(planet, treasury=planet.treasury - amount)
        kind = "withdraw"
    else:
        if player.latinum < amount:
            raise EconomyError("insufficient latinum to deposit")
        new_player = replace(player, latinum=player.latinum - amount)
        new_planet = replace(planet, treasury=planet.treasury + amount)
        kind = "deposit"
    return ReduceResult(
        events=(PlanetBanked(player_id, planet.id, kind, amount, new_planet.treasury),),
        players=(new_player,), planets=(new_planet,),
    )


def _invade_planet(
    state: UniverseState, player_id: int, cmd: InvadePlanet, config: GameConfig
) -> ReduceResult:
    """Ground-assault an owned world once its defences have fallen (§4.2, §14, WP55).

    Enforces the invasion ladder in order (no operational base, gun down, no siege shield),
    commits carried fighters, and resolves the fight in `citadels.resolve_invasion` (drawing
    from `state.rng`, H4). Victory flips ownership and captures the treasury; defeat costs
    the committed fighters, drops alignment, and sours the owner bloc (the WP27 rail).
    """
    if config.citadels is None:
        raise CombatError("planetary invasion is not enabled in this universe")
    player = _player(state, player_id)
    _require_no_encounter(player)
    ship = _ship(state, player)
    planet = state.planets.get(cmd.planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise CombatError("no such world in this sector")
    if not planet.owner.is_owned or corp.player_owns(state, planet.owner, player_id):
        raise CombatError("there is nothing to invade — it is unowned or already yours")
    # Core worlds can never be invaded (deployment-free Core, §10 — assert, don't special-case).
    if state.sectors[ship.sector_id].is_galactic_core:
        raise CombatError("the Core's worlds cannot be invaded")
    # The ladder, in order: an operational base must be razed, then the gun silenced, and
    # the L3 siege shield must not stand — each rung rejects until the previous falls.
    if any(b.sector_id == ship.sector_id and is_operational(b) for b in state.starbases.values()):
        raise CombatError("raze the orbital base before a ground assault")
    if citadels.has_gun(planet, config):
        raise CombatError("silence the citadel gun before a ground assault")
    if citadels.siege_shielded(planet, config, base_operational=False):
        raise CombatError("the citadel's siege shield holds — nothing can land")
    if cmd.fighters < 1 or ship.fighters < cmd.fighters:
        raise CombatError("not enough fighters aboard to commit")

    outcome = citadels.resolve_invasion(planet, cmd.fighters, config, state.rng)
    new_ship = replace(ship, fighters=ship.fighters - cmd.fighters)
    former = planet.owner

    def _sour(p: Player) -> Player:
        # Taking (or trying to take) a bloc's world is an act of war (the WP38 rail).
        if former.kind == "alliance" and former.ref is not None:
            return replace(p, alliance_standing={**p.alliance_standing, former.ref: -1.0})
        return p

    if outcome.victory:
        new_planet, loot = citadels.conquer(planet, player_id, outcome.attacker_survivors, config)
        new_player = _sour(replace(player, latinum=player.latinum + loot))
        return ReduceResult(
            events=(PlanetInvaded(player_id, planet.id, outcome.fighters_lost,
                                  new_planet.colonists, loot),),
            players=(new_player,), ships=(new_ship,), planets=(new_planet,),
        )
    # Repulsed: the committed fighters are gone, alignment drops, the garrison is attrited.
    new_player = _sour(replace(
        player, alignment=player.alignment - config.citadels.invasion_alignment_penalty))
    mult = citadels.citadel_defense_mult(planet, config)
    raw_survivors = min(planet.fighters, round(outcome.defender_survivors / mult)) if mult else 0
    new_planet = replace(planet, fighters=raw_survivors)
    return ReduceResult(
        events=(InvasionRepulsed(player_id, planet.id, outcome.fighters_lost),),
        players=(new_player,), ships=(new_ship,), planets=(new_planet,),
    )


# --- engine room: install / swap / cannibalize / field-patch (§4.1) ---------


def _engine_ship(state: UniverseState, player_id: int) -> Ship:
    ship = _ship(state, _player(state, player_id))
    if ship.subsystems is None:
        raise EngineRoomError("this hull has no engine room")
    return ship


def _subsystem(ship: Ship, subsystem: Subsystem) -> SubsystemState:
    assert ship.subsystems is not None  # guarded by _engine_ship
    sub = ship.subsystems.get(subsystem)
    if sub is None:
        raise EngineRoomError(f"hull has no {subsystem.value} subsystem")
    return sub


def _check_slot(sub: SubsystemState, slot_index: int) -> None:
    if not 0 <= slot_index < len(sub.slots):
        raise EngineRoomError(f"no slot {slot_index} in subsystem")


def _validate_install(
    ship: Ship, subsystem: Subsystem, component: Component, tier: ComponentTier, config: GameConfig
) -> None:
    klass = config.ship_class(ship.type_id)
    if component not in legal_components(klass, subsystem):
        raise EngineRoomError(f"{component.value} is not legal in {subsystem.value}")
    if tier.value > tier_ceiling(config.engine_room).value:
        raise EngineRoomError(f"tier {tier.name} exceeds the install ceiling")


def _inv_take(components: Mapping[tuple[Component, ComponentTier], int],
              key: tuple[Component, ComponentTier]) -> dict[tuple[Component, ComponentTier], int]:
    """Return the inventory with one of `key` removed; raise if none on hand."""
    have = components.get(key, 0)
    if have < 1:
        raise EngineRoomError(f"no {key[0].value} (tier {key[1].name}) in the hold")
    new = dict(components)
    if have == 1:
        del new[key]
    else:
        new[key] = have - 1
    return new


def _inv_add(components: Mapping[tuple[Component, ComponentTier], int],
             key: tuple[Component, ComponentTier]) -> dict[tuple[Component, ComponentTier], int]:
    """Return the inventory with one of `key` added."""
    new = dict(components)
    new[key] = new.get(key, 0) + 1
    return new


def _with_slot(ship: Ship, subsystem: Subsystem, slot_index: int,
               value: InstalledComponent | None) -> Ship:
    """Return `ship` with one subsystem slot replaced (subsystems map copied)."""
    assert ship.subsystems is not None
    sub = ship.subsystems[subsystem]
    slots = list(sub.slots)
    slots[slot_index] = value
    new_sub = replace(sub, slots=tuple(slots))
    return replace(ship, subsystems={**ship.subsystems, subsystem: new_sub})


def _install_component(
    state: UniverseState, player_id: int, cmd: InstallComponent, config: GameConfig
) -> ReduceResult:
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    if sub.slots[cmd.slot_index] is not None:
        raise EngineRoomError("slot is already filled")
    _validate_install(ship, cmd.subsystem, cmd.component, cmd.tier, config)
    new_components = _inv_take(ship.components, (cmd.component, cmd.tier))
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index,
                          InstalledComponent(cmd.component, cmd.tier))
    new_ship = apply_derived(replace(new_ship, components=new_components), config)
    return ReduceResult(
        events=(ComponentInstalled(player_id, cmd.subsystem.value, cmd.slot_index,
                                   cmd.component.value, cmd.tier.name),),
        ships=(new_ship,),
    )


def _swap_component(
    state: UniverseState, player_id: int, cmd: SwapComponent, config: GameConfig
) -> ReduceResult:
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    old = sub.slots[cmd.slot_index]
    if old is None:
        raise EngineRoomError("slot is empty — install instead of swap")
    _validate_install(ship, cmd.subsystem, cmd.component, cmd.tier, config)
    # The new part comes off the hold; the old part goes back on (conserved).
    new_components = _inv_add(
        _inv_take(ship.components, (cmd.component, cmd.tier)), (old.kind, old.tier)
    )
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index,
                          InstalledComponent(cmd.component, cmd.tier))
    new_ship = apply_derived(replace(new_ship, components=new_components), config)
    return ReduceResult(
        events=(
            ComponentRemoved(player_id, cmd.subsystem.value, cmd.slot_index,
                             old.kind.value, old.tier.name),
            ComponentInstalled(player_id, cmd.subsystem.value, cmd.slot_index,
                               cmd.component.value, cmd.tier.name),
        ),
        ships=(new_ship,),
    )


def _cannibalize(
    state: UniverseState, player_id: int, cmd: Cannibalize, config: GameConfig
) -> ReduceResult:
    if cmd.starbase_id is not None:
        return _cannibalize_starbase(state, player_id, cmd, config)
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is already empty")
    if ship.holds_free < 1:
        raise EngineRoomError("no free hold for the salvaged component — sell cargo first")
    new_components = _inv_add(ship.components, (comp.kind, comp.tier))
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index, None)
    new_ship = apply_derived(replace(new_ship, components=new_components), config)
    return ReduceResult(
        events=(ComponentRemoved(player_id, cmd.subsystem.value, cmd.slot_index,
                                 comp.kind.value, comp.tier.name),),
        ships=(new_ship,),
    )


def _cannibalize_starbase(
    state: UniverseState, player_id: int, cmd: Cannibalize, config: GameConfig
) -> ReduceResult:
    """Strip a component out of an orbital starbase into the ship's hold (§4.2, WP4).

    Allowed only when the base is derelict (the frontier salvage cache) or already
    player-owned. The base loses exactly what the ship gains (components conserved).
    """
    assert cmd.starbase_id is not None
    player = _player(state, player_id)
    ship = _ship(state, player)
    base = state.starbases.get(cmd.starbase_id)
    if base is None or base.sector_id != ship.sector_id:
        raise EngineRoomError("no such starbase in this sector")
    player_owned = corp.player_owns(state, base.owner, player_id)
    if is_operational(base) and not player_owned:
        raise EngineRoomError("that starbase is operational — only a derelict or your own base can be salvaged")
    sub = base.subsystems.get(cmd.subsystem)
    if sub is None:
        raise EngineRoomError(f"starbase has no {cmd.subsystem.value} subsystem")
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is already empty")
    if ship.holds_free < 1:
        raise EngineRoomError("no free hold for the salvaged component — sell cargo first")
    slots = list(sub.slots)
    slots[cmd.slot_index] = None
    new_base = replace(base, subsystems={**base.subsystems, cmd.subsystem: replace(sub, slots=tuple(slots))})
    new_ship = replace(ship, components=_inv_add(ship.components, (comp.kind, comp.tier)))
    return ReduceResult(
        events=(StarbaseSalvaged(player_id, base.id, cmd.subsystem.value, cmd.slot_index,
                                 comp.kind.value, comp.tier.name),),
        ships=(new_ship,), starbases=(new_base,),
    )


def _field_patch(
    state: UniverseState, player_id: int, cmd: FieldPatch, config: GameConfig
) -> ReduceResult:
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is empty — nothing to patch")
    if not comp.knocked_out:
        raise EngineRoomError("component is not knocked out")
    if ship.repair_kits < 1:
        raise EngineRoomError("no repair kits")
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index,
                          replace(comp, knocked_out=False))
    new_ship = apply_derived(replace(new_ship, repair_kits=ship.repair_kits - 1), config)
    return ReduceResult(
        events=(Repaired(player_id, cmd.subsystem.value, cmd.slot_index),),
        ships=(new_ship,),
    )


# --- combat: encounter rounds + missile purchase (§10, WP24/WP25) -----------


def _attack_player(
    state: UniverseState, player_id: int, cmd: AttackPlayer, config: GameConfig
) -> ReduceResult:
    """Open attacker-driven PvP on another player's ship in this sector (§14, WP67).

    The gate is enforced here in the reducer (H18), never in the transport, so a modified client
    gains nothing: `pvp.enabled`, a shared non-Core sector (the Core sanctuary extends to
    players), neither party pod-bound or already fighting. The foe is the defender's live ship;
    the attacker submits the rounds from here on.
    """
    if not config.pvp.enabled:
        raise CombatError("player-vs-player combat is disabled in this game")
    attacker = _player(state, player_id)
    _require_no_encounter(attacker)
    if cmd.target_player_id == player_id:
        raise CombatError("you cannot attack yourself")
    target = state.players.get(cmd.target_player_id)
    if target is None:
        raise CombatError("no such player")
    a_ship, d_ship = _ship(state, attacker), _ship(state, target)
    if a_ship.sector_id != d_ship.sector_id:
        raise CombatError("that player is not in your sector")
    if state.sectors[a_ship.sector_id].is_galactic_core:
        raise CombatError("the Core is a sanctuary — no attacks here")
    if target.active_encounter is not None:
        raise CombatError("that player is already in a fight")
    pod = config.combat.escape_pod_class
    if a_ship.type_id == pod or d_ship.type_id == pod:
        raise CombatError("an escape pod can neither attack nor be attacked")
    foe = combat.player_foe(d_ship, config, f"{target.name} ({config.ship_class(d_ship.type_id).name})")
    aspects = derive_aspects(a_ship, config)
    enc = Encounter(species_id=0, sector_id=a_ship.sector_id, foes=(foe,),
                    player_shields=aspects.shields, target_player_id=cmd.target_player_id)
    new_attacker = replace(attacker, active_encounter=enc)
    return ReduceResult(events=(PlayerAttacked(player_id, cmd.target_player_id, a_ship.sector_id),),
                        players=(new_attacker,))


def _attack_species(
    state: UniverseState, player_id: int, cmd: AttackSpecies, config: GameConfig
) -> ReduceResult:
    """Open first-strike combat on an alien contact in this sector (§10, WP70).

    The player-initiated twin of the WP24 violence opener: the same pack spawn, the
    same `CombatAction` rounds. Because the player chose it, the §6.5 souring rail
    fires at initiation — a first strike sours like one kill (with an honest grudge
    cause) even if the player then flees; kills during the fight add more through
    the ordinary WP27 rail. The gates (Core sanctuary, the Entity, influence_gate's
    forbid, shipless kinds) live in `encounters.first_strike_block` — shared with the
    contact projection so the FIGHT menu and this reducer can never disagree — and
    are enforced here regardless, so a crafted log gains nothing (H18 discipline).
    """
    player = _player(state, player_id)
    _require_no_encounter(player)
    ship = _ship(state, player)
    species = _species_here(state, ship, cmd.species_id)
    sc = _species_config(config, species)
    block = encounters.first_strike_block(state, ship, species, sc, config)
    if block is not None:
        raise CombatError(block)
    pack = encounters.spawn_pack(species, sc, ship.sector_id, ship, config, state.rng)
    pack = replace(pack, speech_context="combat_open")
    events: list[Event] = [EncounterStarted(
        player_id, species.id, ship.sector_id, True, len(pack.foes),
        state.sectors[ship.sector_id].distance_band)]
    al = config.aliens
    prior = player.species_attitudes.get(species.roster_id, 0.0)
    soured = sour_attitude(player, species, sc, al, state.game.day_number, 1,
                           cause=f"opened fire on {species.name} ships unprovoked")
    if soured is not player:  # memory_model none forgets instantly (no events)
        grudge = soured.grudges[species.roster_id]
        events.append(GrudgeFormed(
            player_id, species.roster_id, grudge.severity, grudge.duration_days < 0))
        events.append(AttitudeChanged(
            player_id, species.id,
            round(soured.species_attitudes[species.roster_id], 6),
            round(effective_disposition(species, soured), 6)))
        # Reputation spillover (§6.4, WP39): striking this species chills its friends
        # and warms its enemies, same as a kill would.
        if config.roster is not None:
            delta = soured.species_attitudes[species.roster_id] - prior
            spilled = apply_spillover(soured, species.roster_id, delta, config.roster, al)
            soured = replace(soured, species_attitudes=spilled)
    # The pack speaks its opener beat (§6.7, WP31) — same voice as a rolled violence opener.
    soured, spoke = _combat_speak(state, soured, species, "combat_open", config,
                                  dialogue_facts.encounter_facts(pack))
    events.append(spoke)
    new_player = replace(soured, active_encounter=pack, contact_session=None)
    return ReduceResult(events=tuple(events), players=(new_player,))


@dataclass(frozen=True, slots=True)
class _PvpDelta:
    """The extra state a PvP round mutates beyond the attacker's own ship (§14, WP67)."""

    attacker: Player
    attacker_ship: Ship
    players: tuple[Player, ...]  # the defender (podded / bounty-cleared)
    ships: tuple[Ship, ...]      # the defender's ship (wounded or podded)
    events: tuple[Event, ...]


def _pvp_apply(state: UniverseState, attacker_id: int, enc: Encounter, result: combat.RoundResult,
               attacker: Player, attacker_ship: Ship, config: GameConfig) -> _PvpDelta:
    """Sync the defender's real ship with a PvP round and resolve a kill (§14, WP67).

    Hull damage always persists onto the defender's ship (the fight is authored entirely by the
    attacker's commands, yet mutates real defender state — H18). On the attacker's victory the
    defender drops to an escape pod (the WP26 rule verbatim, bank/planets/corp intact), the
    victor salvages a fraction of the defender's cargo + loose components (moved, never minted),
    and a *lawful*-player kill outlaws the attacker: an alignment hit plus a claimable bounty.
    Podding a defender who already carried a bounty collects it (the WP44 kill hook, player-side).
    """
    assert enc.target_player_id is not None
    defender = state.players[enc.target_player_id]
    d_ship = state.ships[defender.ship_id]
    pv = config.pvp

    if result.outcome != combat.VICTORY:
        # Ongoing / attacker fled or died: mirror the encounter foe's remaining hull onto the ship.
        foe_hull = result.encounter.foes[0].hull if result.encounter is not None else d_ship.hull_current
        wounded = replace(d_ship, hull_current=max(0, foe_hull))
        return _PvpDelta(attacker, attacker_ship, (), (wounded,), ())

    events: list[Event] = [ShipDestroyed(enc.target_player_id, 0, d_ship.sector_id, d_ship.type_id)]
    # Salvage a fraction of the defender's cargo + loose components into the victor's free holds.
    frac = pv.salvage_frac_min + state.rng.random() * (pv.salvage_frac_max - pv.salvage_frac_min)
    cargo = dict(attacker_ship.cargo)
    comps = dict(attacker_ship.components)
    free = attacker_ship.holds_free
    taken_labels: list[str] = []
    for commodity, qty in sorted(d_ship.cargo.items(), key=lambda kv: kv[0].value):
        take = min(int(qty * frac), free)
        if take > 0:
            cargo[commodity] = cargo.get(commodity, 0) + take
            free -= take
            taken_labels.append(f"{take} {commodity.value}")
    for key, count in sorted(d_ship.components.items(), key=lambda kv: (kv[0][0].value, kv[0][1].value)):
        take = min(int(count * frac), free)
        if take > 0:
            comps[key] = comps.get(key, 0) + take
            free -= take
            taken_labels.append(f"{take}×{key[0].value}")
    new_attacker_ship = replace(attacker_ship, cargo=cargo, components=comps)
    events.append(SalvageCollected(attacker_id, 0, tuple(taken_labels)))

    new_attacker = attacker
    # Outlawry (§14, interview decision 5): a lawful victim's death outlaws the attacker.
    if not is_criminal(defender, config.aliens):
        bounty = round(pv.bounty_frac * config.ship_class(d_ship.type_id).price)
        new_attacker = replace(new_attacker, alignment=new_attacker.alignment - pv.alignment_hit,
                               bounty=new_attacker.bounty + bounty)
        if bounty > 0:  # a price-0 hull (e.g. a pod/starter) still costs alignment but posts no bounty
            events.append(BountyPosted(attacker_id, bounty, new_attacker.bounty))
    # Claim any bounty the defender already carried (the WP44 pod-kill hook, player-side).
    if defender.bounty > 0:
        new_attacker = replace(new_attacker, latinum=new_attacker.latinum + defender.bounty)
    podded = _escape_pod(d_ship, config)
    new_defender = replace(defender, bounty=0)  # a podded outlaw's head price resets
    return _PvpDelta(new_attacker, new_attacker_ship, (new_defender,), (podded,), tuple(events))


def _combat_action(
    state: UniverseState, player_id: int, cmd: CombatAction, config: GameConfig
) -> ReduceResult:
    """Resolve one round of the live encounter (§10, WP25).

    Field-patching first spends the kit through the ordinary `_field_patch` validation
    (so slot/kit rules stay in one place), then the pack still takes its volley. Every
    roll draws from `state.rng` here in the reducer (H4).
    """
    player = _player(state, player_id)
    enc = player.active_encounter
    if enc is None:
        raise CombatError("no live encounter")
    ship = _ship(state, player)
    species = state.species.get(enc.species_id)
    sc = _species_config(config, species) if species is not None else None
    interception = sc.interception_rating if sc is not None else 0.0

    events: list[Event] = []
    if cmd.action == "field_patch":
        if cmd.subsystem is None or cmd.slot_index is None:
            raise CombatError("field_patch needs a subsystem and slot")
        patched = _field_patch(
            state, player_id, FieldPatch(cmd.subsystem, cmd.slot_index), config)
        ship = patched.ships[0]
        events.extend(patched.events)

    aspects = derive_aspects(ship, config)
    result = combat.resolve_round(
        enc, ship, aspects, interception, cmd.action, config, state.rng,
        escape_floor=config.aliens.escape_floor,
    )
    foes_left = (
        sum(1 for f in result.encounter.foes if f.hull > 0)
        if result.encounter is not None else 0
    )
    events.append(CombatRoundEvent(
        player_id, enc.species_id, enc.round + 1, cmd.action,
        result.damage_dealt, result.damage_taken, foes_left,
    ))
    new_ship = result.ship
    new_player = replace(player, active_encounter=result.encounter)
    if foes_left > 0:
        # A surviving pack may fall on an escorted merchant instead (§6.7, WP75 — the
        # WP57 A3 seam): the convoy is a target while the fight rages in its sector.
        new_player, escort_events = _escort_under_fire(state, new_player, enc.sector_id, config)
        events.extend(escort_events)
    if result.foes_destroyed > 0 and species is not None and sc is not None:
        # Consequences of the kill (§6.5, WP27): souring + grudge, alignment by the
        # victim's band *before* the souring, experience scaled by threat.
        al = config.aliens
        band = disposition_band(effective_disposition(species, new_player), al)
        align_per_kill = {
            HOSTILE_BAND: al.alignment_kill_hostile,
            NEUTRAL_BAND: al.alignment_kill_neutral,
            FRIENDLY_BAND: al.alignment_kill_friendly,
        }[band]
        xp = max(1, round(sc.threat_rating * al.experience_kill_scale)) * result.foes_destroyed
        prior = new_player.species_attitudes.get(species.roster_id, 0.0)
        soured = sour_attitude(
            new_player, species, sc, al, state.game.day_number, result.foes_destroyed)
        if soured is not new_player:  # memory_model none forgets instantly (no events)
            grudge = soured.grudges[species.roster_id]
            events.append(GrudgeFormed(
                player_id, species.roster_id, grudge.severity, grudge.duration_days < 0))
            events.append(AttitudeChanged(
                player_id, species.id,
                round(soured.species_attitudes[species.roster_id], 6),
                round(effective_disposition(species, soured), 6)))
            # Reputation spillover (§6.4, WP39): harming this species chills its friends
            # and warms its enemies in proportion to their relations to it.
            if config.roster is not None:
                delta = soured.species_attitudes[species.roster_id] - prior
                spilled = apply_spillover(
                    soured, species.roster_id, delta, config.roster, al)
                soured = replace(soured, species_attitudes=spilled)
        # Bounty for culling a hostile-band raider (§10, WP44) — a latinum faucet that
        # funds the fight; friendly/neutral kills pay nothing.
        bounty = encounters.kill_bounty(
            config, hostile=band == HOSTILE_BAND, count=result.foes_destroyed)
        new_player = replace(
            soured,
            alignment=soured.alignment + align_per_kill * result.foes_destroyed,
            experience=soured.experience + xp,
            latinum=soured.latinum + bounty,
        )
    if result.knockout is not None:
        # The owning subsystem's aspect degrades immediately (§4.1 derive-on-write).
        sub, slot_index, component = result.knockout
        new_ship = apply_derived(new_ship, config)
        events.append(ComponentKnockedOut(player_id, sub.value, slot_index, component))
    if (result.outcome is None and result.encounter is not None
            and species is not None and sc is not None):
        # The pack speaks its round beat (§6.7, WP31): a taunt while it presses the
        # attack, suing for quarter once bloodied. Keyed to the post-round encounter
        # facts — the very state the encounter screen renders the line under.
        enc_facts = dialogue_facts.encounter_facts(result.encounter)
        beat = "surrender" if enc_facts["pack_bloodied"] else "combat_taunt"
        new_player = replace(
            new_player, active_encounter=replace(result.encounter, speech_context=beat))
        new_player, spoke = _combat_speak(state, new_player, species, beat, config, enc_facts)
        events.append(spoke)
    razed_bases: tuple[Starbase, ...] = ()
    razed_planets: tuple[Planet, ...] = ()
    silenced_planets: tuple[Planet, ...] = ()
    extra_players: tuple[Player, ...] = ()
    extra_ships: tuple[Ship, ...] = ()
    if enc.target_player_id is not None:
        # PvP (§14, WP67): the foe *is* the defender's live ship — reconcile its damage and,
        # on a kill, pod the defender + salvage + outlawry (H18: all from the attacker's command).
        pvp = _pvp_apply(state, player_id, enc, result, new_player, new_ship, config)
        new_player, new_ship = pvp.attacker, pvp.attacker_ship
        extra_players, extra_ships = pvp.players, pvp.ships
        events.extend(pvp.events)
    if result.outcome == combat.VICTORY:
        if enc.target_player_id is None:
            # NPC / set-piece wreck salvage (PvP salvage is handled in `_pvp_apply`).
            new_ship, salvage = _combat_salvage(player_id, enc, new_ship, config, state.rng)
            new_player = replace(new_player, latinum=new_player.latinum + salvage.latinum)
            events.append(salvage)
        if enc.starbase_id is not None:
            new_player, razed_bases, razed_planets, raze_events = _raze_starbase(
                state, new_player, enc.starbase_id, config)
            events.extend(raze_events)
        elif enc.citadel_planet_id is not None:
            # Silencing the gun is the ladder's second rung (§4.2, WP55): zero its
            # integrity (mirroring how base components fall), exposing a ground assault.
            gun_planet = state.planets.get(enc.citadel_planet_id)
            if gun_planet is not None and gun_planet.gun_integrity > 0:
                silenced_planets = (replace(gun_planet, gun_integrity=0),)
                events.append(CitadelGunSilenced(player_id, gun_planet.id))
    elif result.outcome == combat.DESTROYED:
        # Hull 0 (§10, WP26): ship, cargo, and stores are lost; the escape pod —
        # a real config hull — is issued in place, and the pod limps home.
        events.append(ShipDestroyed(
            player_id, enc.species_id, new_ship.sector_id, new_ship.type_id))
        new_ship = _escape_pod(new_ship, config)
    elif result.outcome == combat.FLED and species is not None and sc is not None:
        # Parting scorn at the player's retreating engines (§6.7, WP31) — the ring
        # advances so a repeat escape from this pack is jeered differently.
        new_player, spoke = _combat_speak(state, new_player, species, "flee_scorn", config,
                                          dialogue_facts.encounter_facts(enc))
        events.append(spoke)
    force_updates: tuple[SectorForce, ...] = ()
    if result.outcome is not None:
        if species is not None:
            # The H5 record situational dialogue facts read (`just_fled_combat`, §6.7)
            # and the WP30 callbacks build on — written here, never by the UI.
            new_player = replace(new_player, last_combat=LastCombat(
                species=species.roster_id, outcome=result.outcome,
                day=state.game.day_number))
            # A destroy favor cashes at the same hook as the kill bounty (§6.7, WP57):
            # a victory over this species instance settles any contract naming it.
            if (result.outcome == combat.VICTORY and enc.starbase_id is None
                    and enc.citadel_planet_id is None):
                new_player, done_jobs = contracts.complete_destroy_on_kill(new_player, species)
                for c in done_jobs:
                    new_player = contracts.apply_reward(new_player, c, state)
                    events.append(ContractCompleted(player_id, c.id, c.kind, c.reward_slips))
        # A sector-fighter garrison engagement (§10, WP41: species 0, no starbase): victory
        # wipes the garrison, retreat costs it `retreat_fighter_cost` fighters (the classic rule).
        if enc.species_id == 0 and enc.starbase_id is None:
            force = state.sector_forces.get(enc.sector_id)
            if force is not None and force.fighters > 0:
                if result.outcome == combat.VICTORY:
                    # A garrison only engages an entrant its owner opposes (§10, WP41), so a
                    # wiped garrison is always hostile — every downed fighter pays a bounty.
                    bounty = encounters.kill_bounty(config, hostile=True, count=force.fighters)
                    new_player = replace(new_player, latinum=new_player.latinum + bounty)
                    force_updates = (replace(force, fighters=0),)
                elif result.outcome == combat.FLED:
                    force_updates = (replace(
                        force, fighters=max(0, force.fighters - config.territory.retreat_fighter_cost)),)
        events.append(EncounterEnded(player_id, enc.species_id, result.outcome))
    return ReduceResult(events=tuple(events), players=(new_player, *extra_players),
                        ships=(new_ship, *extra_ships),
                        starbases=razed_bases, planets=razed_planets + silenced_planets,
                        sector_forces=force_updates)


def _escort_under_fire(state: UniverseState, player: Player, sector_id: int,
                       config: GameConfig) -> tuple[Player, list[Event]]:
    """The pack's side volley at an escorted merchant (§6.7, WP75 — the WP57 A3 seam).

    Each fought round with a live foe left and an active escort whose merchant sits in
    the fight's sector, a config-weighted roll may drop the volley on the convoy: the
    merchant's ship is destroyed (the kind persists — packs are ephemeral — but the job
    is lost), the contract fails, and the issuing kind takes the full WP27 consequence
    rail — one kill's worth of souring with an honest grudge cause, plus §6.4 spillover.
    RNG discipline (H4): the roll draws only when a targetable merchant is present.
    """
    cc = config.aliens.contracts
    if cc.escort_target_chance <= 0.0 or config.roster is None:
        return player, []
    events: list[Event] = []
    new_player = player
    for c in contracts.active(new_player, "escort"):
        if c.target_species_id is None:
            continue
        merchant = state.species.get(c.target_species_id)
        if merchant is None or merchant.sector_id != sector_id:
            continue
        if state.rng.random() >= cc.escort_target_chance:
            continue
        new_player = contracts.set_status(new_player, c.id, "failed")
        events.append(ContractFailed(player.id, c.id, c.kind, "merchant destroyed"))
        issuer = next((sp for sp in sorted(state.species.values(), key=lambda sp: sp.id)
                       if sp.roster_id == c.issuer), merchant)
        sc = config.roster.species_by_id(issuer.roster_id)
        if sc is None:
            continue
        al = config.aliens
        prior = new_player.species_attitudes.get(issuer.roster_id, 0.0)
        soured = sour_attitude(
            new_player, issuer, sc, al, state.game.day_number, 1,
            cause=f"lost {merchant.name}'s convoy under the player's escort")
        if soured is not new_player:  # memory_model none forgets instantly (no events)
            grudge = soured.grudges[issuer.roster_id]
            events.append(GrudgeFormed(
                player.id, issuer.roster_id, grudge.severity, grudge.duration_days < 0))
            events.append(AttitudeChanged(
                player.id, issuer.id,
                round(soured.species_attitudes[issuer.roster_id], 6),
                round(effective_disposition(issuer, soured), 6)))
            delta = soured.species_attitudes[issuer.roster_id] - prior
            spilled = apply_spillover(soured, issuer.roster_id, delta, config.roster, al)
            new_player = replace(soured, species_attitudes=spilled)
    return new_player, events


def _escape_pod(wreck: Ship, config: GameConfig) -> Ship:
    """Replace a destroyed hull with the configured escape pod (§10, WP26).

    Cargo, loose components, devices, missiles, kits, and any colonists aboard go
    down with the ship; the pod keeps the hull's id and sector so the player limps
    home from where the fight ended. Latinum and the bank live on the player.
    """
    pod = config.ship_class(config.combat.escape_pod_class)
    return apply_derived(replace(
        wreck, type_id=pod.id, name=pod.name, holds_total=pod.holds_total,
        hull_max=pod.hull_max, hull_current=pod.hull_max,
        cloak_rating=pod.cloak_rating, sensor_rating=pod.sensor_rating,
        shields=pod.shields_max, warp_speed=pod.warp_speed,
        combat_speed=pod.combat_speed, turns_per_warp=pod.turns_per_warp,
        colonist_capacity=pod.colonist_capacity, colonists=0,
        cargo={}, components={}, devices={}, missiles=0, repair_kits=0,
        subsystems=build_subsystems(pod),
    ), config)


def _combat_salvage(
    player_id: int, enc: Encounter, ship: Ship, config: GameConfig, rng: random.Random
) -> tuple[Ship, SalvageCollected]:
    """Roll post-victory wreck salvage over the whole destroyed pack (§10, WP26).

    Per wreck: `hull_max × salvage_hull_value × U[frac_min, frac_max]` latinum (the
    BNT 10–20% rule mapped onto cargo-less NPC hulls), plus an occasional loose
    Tier-I component — which needs a free hold, else it is left adrift. Draw order
    is fixed (foes in pack order, fraction then component roll) so replays are exact.
    """
    cc = config.combat
    latinum = 0
    parts: list[str] = []
    components = dict(ship.components)
    free = ship.holds_free
    for foe in enc.foes:
        frac = cc.salvage_frac_min + rng.random() * (cc.salvage_frac_max - cc.salvage_frac_min)
        latinum += round(foe.hull_max * cc.salvage_hull_value * frac)
        if rng.random() < cc.salvage_component_chance:
            kind = rng.choice(list(Component))
            if free >= 1:
                key = (kind, ComponentTier.I)
                components[key] = components.get(key, 0) + 1
                parts.append(kind.value)
                free -= 1
    new_ship = replace(ship, components=components) if parts else ship
    return new_ship, SalvageCollected(player_id, latinum, tuple(parts))


# --- starbases: assault, raze, repair, claim (§4.2, §10 — WP40) -------------


def _starbase_here(state: UniverseState, ship: Ship, starbase_id: int) -> Starbase:
    base = state.starbases.get(starbase_id)
    if base is None or base.sector_id != ship.sector_id:
        raise CombatError("no such starbase here")
    return base


def _raze_starbase(
    state: UniverseState, player: Player, starbase_id: int, config: GameConfig,
) -> tuple[Player, tuple[Starbase, ...], tuple[Planet, ...], tuple[Event, ...]]:
    """Raze a defeated base (§4.2, §10 — WP40): derelict it, free its world, sour its bloc.

    The base is stripped of its reactor keystone (so it reads derelict — repairable and
    claimable), its host world drops to unowned if the bloc owned it, and the owning
    alliance is soured to hostile standing (the WP38/WP39 fallout). Pays a bounty +
    experience. Contract-kill/admission credit for a *named* razing is a documented seam
    (the WP37 `contract_kill` hook is registry-complete but not yet corpus-wired).
    """
    base = state.starbases[starbase_id]
    sbcfg = config.starbase
    assert sbcfg is not None
    subsystems = dict(base.subsystems)
    reactor = subsystems.get(Subsystem.FUSION_REACTOR)
    if reactor is not None and reactor.keystone_index is not None:
        slots = list(reactor.slots)
        slots[reactor.keystone_index] = None  # the minimal break that derelicts it (§4.2)
        subsystems[Subsystem.FUSION_REACTOR] = replace(reactor, slots=tuple(slots))
    former = base.owner
    new_base = replace(base, owner=UNOWNED, subsystems=subsystems)
    razed_planets: tuple[Planet, ...] = ()
    planet = state.planets.get(base.planet_id)
    if planet is not None and planet.owner == former and former.kind == "alliance":
        razed_planets = (replace(planet, owner=UNOWNED),)  # the frontier reward: claimable land
    new_player = player
    if former.kind == "alliance" and former.ref is not None:
        standing = {**new_player.alliance_standing, former.ref: -1.0}
        new_player = replace(new_player, alliance_standing=standing)
    new_player = replace(
        new_player,
        latinum=new_player.latinum + sbcfg.raze_bounty,
        experience=new_player.experience + sbcfg.raze_experience,
    )
    events: list[Event] = [StarbaseRazed(
        player.id, starbase_id, base.planet_id, base.sector_id,
        former.kind, former.ref, sbcfg.raze_bounty)]
    # A destroy favor targeting this base settles on the razing (§6.7, WP57 — the seam
    # this docstring named is now live for named base kills).
    new_player, done_jobs = contracts.complete_destroy_on_raze(new_player, starbase_id)
    for c in done_jobs:
        new_player = contracts.apply_reward(new_player, c, state)
        events.append(ContractCompleted(player.id, c.id, c.kind, c.reward_slips))
    return new_player, (new_base,), razed_planets, tuple(events)


def _assault_starbase(
    state: UniverseState, player_id: int, cmd: AssaultStarbase, config: GameConfig
) -> ReduceResult:
    """Open a set-piece assault on an operational base in the sector (§4.2, §10 — WP40)."""
    player = _player(state, player_id)
    _require_no_encounter(player)
    ship = _ship(state, player)
    base = _starbase_here(state, ship, cmd.starbase_id)
    if not is_operational(base):
        raise CombatError("that base is derelict — salvage or repair it, not assault it")
    foe = starbases.assault_foe(base, config)
    enc = Encounter(
        species_id=0, sector_id=ship.sector_id, foes=(foe,), round=0,
        player_shields=ship.shields, detected=True,
        speech_context="combat_open", starbase_id=base.id,
    )
    new_player = replace(player, active_encounter=enc, contact_session=None)
    band = state.sectors[ship.sector_id].distance_band
    return ReduceResult(
        events=(EncounterStarted(player_id, 0, ship.sector_id, True, 1, band),),
        players=(new_player,),
    )


def _repair_starbase(
    state: UniverseState, player_id: int, cmd: RepairStarbase, config: GameConfig
) -> ReduceResult:
    """Install a loose hold component into a base slot (§4.2, WP40) — refilling a derelict."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    base = state.starbases.get(cmd.starbase_id)
    if base is None or base.sector_id != ship.sector_id:
        raise EngineRoomError("no such starbase here")
    sub_state = base.subsystems.get(cmd.subsystem)
    if sub_state is None:
        raise EngineRoomError("that base has no such subsystem")
    if not 0 <= cmd.slot_index < len(sub_state.slots):
        raise EngineRoomError("no such slot")
    if sub_state.slots[cmd.slot_index] is not None:
        raise EngineRoomError("slot is occupied")
    key = (cmd.component, cmd.tier)
    if ship.components.get(key, 0) < 1:
        raise EngineRoomError("you do not carry that component")
    slots = list(sub_state.slots)
    slots[cmd.slot_index] = InstalledComponent(cmd.component, cmd.tier)
    subsystems = dict(base.subsystems)
    subsystems[cmd.subsystem] = replace(sub_state, slots=tuple(slots))
    new_base = replace(base, subsystems=subsystems)
    new_ship = replace(ship, components=_inv_take(ship.components, key))
    return ReduceResult(
        events=(StarbaseRepaired(player_id, cmd.starbase_id, cmd.subsystem.value,
                                 cmd.slot_index, cmd.component.value, cmd.tier.name),),
        ships=(new_ship,), starbases=(new_base,),
    )


def _claim_starbase(
    state: UniverseState, player_id: int, cmd: ClaimStarbase, config: GameConfig
) -> ReduceResult:
    """Claim an operational, unowned base as a player foothold (§4.2, WP40)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    base = state.starbases.get(cmd.starbase_id)
    if base is None or base.sector_id != ship.sector_id:
        raise EconomyError("no such starbase here")
    if base.owner.is_owned:
        raise EconomyError("that base already has an owner")
    if not is_operational(base):
        raise EconomyError("repair the base's reactor before claiming it")
    assert config.starbase is not None
    cost = config.starbase.claim_cost
    if player.latinum < cost:
        raise EconomyError("insufficient latinum to claim the base")
    new_base = replace(base, owner=Ownership("player", player_id))
    new_player = replace(player, latinum=player.latinum - cost)
    return ReduceResult(
        events=(StarbaseClaimed(player_id, cmd.starbase_id, cost),),
        players=(new_player,), starbases=(new_base,),
    )


# --- territory: fighters, mines, beacons (§10, WP41) ------------------------


def _buy_fighters(
    state: UniverseState, player_id: int, cmd: BuyFighters, config: GameConfig
) -> ReduceResult:
    """Buy sector-fighter stock at the StarDock (§10, WP41)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    if cmd.count < 1:
        raise EconomyError("buy at least one fighter")
    cost = cmd.count * config.territory.fighter_price
    if player.latinum < cost:
        raise EconomyError(f"need {cost} latinum for {cmd.count} fighters")
    new_player = replace(player, latinum=player.latinum - cost)
    new_ship = replace(ship, fighters=ship.fighters + cmd.count)
    return ReduceResult(
        events=(DevicePurchased(player_id, "sector_fighter", cost),),
        players=(new_player,), ships=(new_ship,),
    )


def _buy_mines(
    state: UniverseState, player_id: int, cmd: BuyMines, config: GameConfig
) -> ReduceResult:
    """Buy space-mine stock at the StarDock (§10, WP41)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    if cmd.count < 1:
        raise EconomyError("buy at least one mine")
    cost = cmd.count * config.territory.mine_price
    if player.latinum < cost:
        raise EconomyError(f"need {cost} latinum for {cmd.count} mines")
    new_player = replace(player, latinum=player.latinum - cost)
    new_ship = replace(ship, mines=ship.mines + cmd.count)
    return ReduceResult(
        events=(DevicePurchased(player_id, "space_mine", cost),),
        players=(new_player,), ships=(new_ship,),
    )


def _require_deployable_sector(state: UniverseState, ship: Ship) -> None:
    """Territory may not be deployed in the Core (§10, WP41)."""
    if state.sectors[ship.sector_id].is_galactic_core:
        raise EconomyError("you cannot deploy in the Core")


def _deploy_fighters(
    state: UniverseState, player_id: int, cmd: DeployFighters, config: GameConfig
) -> ReduceResult:
    """Garrison the current sector with carried fighters (§10, WP41)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _require_deployable_sector(state, ship)
    if cmd.mode not in territory.FIGHTER_MODES:
        raise EconomyError(f"unknown fighter mode {cmd.mode!r}")
    if cmd.count < 1 or ship.fighters < cmd.count:
        raise EconomyError("not enough fighters aboard")
    existing = state.sector_forces.get(ship.sector_id)
    owner = Ownership("player", player_id)
    if existing is not None and existing.owner != owner:
        raise EconomyError("another force already holds this sector")
    have = existing.fighters if existing is not None else 0
    force = SectorForce(
        sector_id=ship.sector_id, owner=owner, fighters=have + cmd.count, mode=cmd.mode,
        toll=cmd.toll,
        armid_mines=existing.armid_mines if existing is not None else 0,
        limpet_mines=existing.limpet_mines if existing is not None else 0)
    new_ship = replace(ship, fighters=ship.fighters - cmd.count)
    return ReduceResult(
        events=(TerritoryDeployed(player_id, ship.sector_id, "fighters", cmd.count, cmd.mode),),
        ships=(new_ship,), sector_forces=(force,),
    )


def _deploy_mines(
    state: UniverseState, player_id: int, cmd: DeployMines, config: GameConfig
) -> ReduceResult:
    """Seed the current sector with carried mines — armid or limpet (§10, WP41/WP56)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _require_deployable_sector(state, ship)
    if cmd.kind not in ("armid", "limpet"):
        raise EconomyError(f"unknown mine kind {cmd.kind!r}")
    if cmd.count < 1 or ship.mines < cmd.count:
        raise EconomyError("not enough mines aboard")
    existing = state.sector_forces.get(ship.sector_id)
    owner = Ownership("player", player_id)
    if existing is not None and existing.owner != owner:
        raise EconomyError("another force already holds this sector")
    armid = existing.armid_mines if existing is not None else 0
    limpet = existing.limpet_mines if existing is not None else 0
    if cmd.kind == "armid":
        armid += cmd.count
    else:
        limpet += cmd.count
    force = SectorForce(
        sector_id=ship.sector_id, owner=owner,
        fighters=existing.fighters if existing is not None else 0,
        mode=existing.mode if existing is not None else "defensive",
        toll=existing.toll if existing is not None else 0,
        armid_mines=armid, limpet_mines=limpet)
    new_ship = replace(ship, mines=ship.mines - cmd.count)
    return ReduceResult(
        events=(TerritoryDeployed(player_id, ship.sector_id, f"{cmd.kind}_mines", cmd.count),),
        ships=(new_ship,), sector_forces=(force,),
    )


def _deploy_beacon(
    state: UniverseState, player_id: int, cmd: DeployBeacon, config: GameConfig
) -> ReduceResult:
    """Plant a comms beacon in the current sector — one per sector, overwrite (§10, WP41)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _require_deployable_sector(state, ship)
    cost = config.territory.beacon_price
    if player.latinum < cost:
        raise EconomyError(f"need {cost} latinum to plant a beacon")
    sector = state.sectors[ship.sector_id]
    new_sector = replace(sector, beacon_text=cmd.text)
    new_player = replace(player, latinum=player.latinum - cost)
    return ReduceResult(
        events=(TerritoryDeployed(player_id, ship.sector_id, "beacon", 1),),
        players=(new_player,), sectors=(new_sector,),
    )


def _buy_device(
    state: UniverseState, player_id: int, cmd: BuyDevice, config: GameConfig
) -> ReduceResult:
    """Buy a probe / interdictor / mine-deflector at the StarDock (§10, §14, WP56)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    spec = config.devices.get(cmd.device_id)
    if spec is None:
        raise EconomyError(f"this dock does not stock {cmd.device_id!r}")
    if player.latinum < spec.price:
        raise EconomyError(f"need {spec.price} latinum for the {cmd.device_id}")
    new_ship = replace(ship, devices={
        **ship.devices, cmd.device_id: ship.devices.get(cmd.device_id, 0) + 1})
    new_player = replace(player, latinum=player.latinum - spec.price)
    return ReduceResult(
        events=(DevicePurchased(player_id, cmd.device_id, spec.price),),
        players=(new_player,), ships=(new_ship,),
    )


def _launch_probe(
    state: UniverseState, player_id: int, cmd: LaunchProbe, config: GameConfig
) -> ReduceResult:
    """Send a consumable probe toward a sector, charting its path (§11, §14, WP56).

    Flies the shortest full-graph path (recon *buys* knowledge — no explored-only gate),
    up to the device's `probe_range` hops, revealing each traversed sector and tallying
    its contents. Each hop through a hostile-force sector rolls `loss_chance` from
    `state.rng` (H4) to destroy the probe mid-flight, so deep probing is lossy.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    spec = config.devices.get("probe")
    if spec is None:
        raise EconomyError("probes are not sold in this universe")
    if ship.devices.get("probe", 0) < 1:
        raise EconomyError("no probe aboard")
    if cmd.dest_sector not in state.sectors:
        raise MovementError("no such sector")
    path = shortest_path(state.adjacency, ship.sector_id, cmd.dest_sector)
    if path is None:
        raise MovementError("no route to that sector for the probe")

    charted = set(player.explored_sectors)
    newly = ports = planets = contacts = 0
    destroyed = False
    for sid in path[1:1 + spec.probe_range]:  # sectors beyond the origin, up to the range
        if sid not in charted:
            charted.add(sid)
            newly += 1
        if state.port_in_sector(sid) is not None:
            ports += 1
        planets += sum(1 for pl in state.planets.values() if pl.sector_id == sid)
        contacts += sum(1 for sp in state.species.values() if sp.sector_id == sid)
        force = state.sector_forces.get(sid)
        if (force is not None and territory.force_hostile_to_player(
                    state, force, player, pvp_enabled=config.pvp.enabled)
                and state.rng.random() < spec.loss_chance):
            destroyed = True
            break  # lost before it could report from deeper in

    devices = {**ship.devices, "probe": ship.devices["probe"] - 1}
    if devices["probe"] <= 0:
        del devices["probe"]
    new_ship = replace(ship, devices=devices)
    new_player = replace(player, explored_sectors=frozenset(charted))
    return ReduceResult(
        events=(ProbeReport(player_id, cmd.dest_sector, newly, ports, planets, contacts, destroyed),),
        players=(new_player,), ships=(new_ship,),
    )


def _toggle_interdictor(
    state: UniverseState, player_id: int, config: GameConfig
) -> ReduceResult:
    """Engage / disengage the carried interdictor (§14, WP56)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    if ship.devices.get("interdictor", 0) < 1:
        raise EconomyError("no interdictor aboard")
    new_ship = replace(ship, interdictor_active=not ship.interdictor_active)
    return ReduceResult(
        events=(InterdictorToggled(player_id, new_ship.interdictor_active),),
        ships=(new_ship,),
    )


def _remove_limpets(
    state: UniverseState, player_id: int, config: GameConfig
) -> ReduceResult:
    """Strip attached limpet mines at a service point for a fee (§10, §4.2, WP56)."""
    from edge.core.services import service_point

    player = _player(state, player_id)
    ship = _ship(state, player)
    if service_point(state, player, ship, config) is None:
        raise EconomyError("limpets can only be removed at a StarDock or a base you own")
    if not ship.limpets:
        raise EconomyError("no limpets attached")
    fee = config.territory.limpet_removal_fee
    if player.latinum < fee:
        raise EconomyError(f"need {fee} latinum to strip the limpets")
    count = sum(ship.limpets.values())
    new_ship = replace(ship, limpets={})
    new_player = replace(player, latinum=player.latinum - fee)
    return ReduceResult(
        events=(LimpetsRemoved(player_id, count, fee),),
        players=(new_player,), ships=(new_ship,),
    )


def _buy_missiles(
    state: UniverseState, player_id: int, cmd: BuyMissiles, config: GameConfig
) -> ReduceResult:
    """Buy homing missiles at a StarDock or a player base (§8, §10, WP25/WP53)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    sp = require_service(state, player, ship, MUNITIONS, config)
    if cmd.count < 1:
        raise EconomyError("buy at least one missile")
    cost = round(cmd.count * config.combat.missile_price * sp.fee_frac)
    if player.latinum < cost:
        raise EconomyError(f"need {cost} latinum for {cmd.count} missiles")
    new_player = replace(player, latinum=player.latinum - cost)
    new_ship = replace(ship, missiles=ship.missiles + cmd.count)
    return ReduceResult(
        events=(DevicePurchased(player_id, f"homing_missile x{cmd.count}", cost),),
        players=(new_player,), ships=(new_ship,),
    )


# --- discovery: descend / explore / salvage / log to codex (§7, WP5/WP6) ----


def _planet_in_sector(state: UniverseState, ship: Ship, planet_id: int) -> Planet:
    planet = state.planets.get(planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such planet in this sector")
    return planet


def _surface_sites(state: UniverseState, planet_id: int) -> list[Discovery]:
    """A planet's surface-site discoveries, in slot order (§7, WP6)."""
    sites = [d for d in state.discoveries.values() if d.planet_id == planet_id]
    return sorted(sites, key=lambda d: d.site_slot)


def _descend(
    state: UniverseState, player_id: int, cmd: Descend, config: GameConfig
) -> ReduceResult:
    """Land on a planet surface (§7, WP6). A turn cost that opens site exploration."""
    player = _player(state, player_id)
    _require_no_encounter(player)
    ship = _ship(state, player)
    _planet_in_sector(state, ship, cmd.planet_id)
    cost = config.discovery.descent_turn_cost if config.discovery is not None else 1
    if player.turns_remaining < cost:
        raise MovementError("out of turns")
    new_player = replace(player, turns_remaining=player.turns_remaining - cost)
    return ReduceResult(events=(Descended(player_id, cmd.planet_id),), players=(new_player,))


def _explore(
    state: UniverseState, player_id: int, cmd: Explore, config: GameConfig
) -> ReduceResult:
    """Reveal the next still-hidden surface site the ship's sensors can resolve (§7, WP6)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _planet_in_sector(state, ship, cmd.planet_id)
    undetected = [d for d in _surface_sites(state, cmd.planet_id) if d.id not in player.detected]
    if not undetected:
        raise EconomyError("every site here is already surveyed")
    target = next(
        (d for d in undetected
         if is_detectable(d, ship.sensor_rating, in_nebula=False, config=config)),
        None,
    )
    if target is None:
        raise EconomyError("sensors too weak to resolve the remaining sites — upgrade and retry")
    cost = config.discovery.explore_turn_cost if config.discovery is not None else 1
    if player.turns_remaining < cost:
        raise MovementError("out of turns")
    # Surveying both reveals the site and logs it to the codex; taking the payload
    # aboard is a separate, optional act (Salvage). So a surveyed-but-untaken site stays
    # `found_by=None` — the player can leave it for the next person.
    new_player = replace(player, turns_remaining=player.turns_remaining - cost,
                         detected=player.detected | frozenset({target.id}),
                         codex=player.codex | frozenset({target.id}),
                         experience=player.experience + config.aliens.experience_per_discovery)
    return ReduceResult(
        events=(SiteExplored(player_id, cmd.planet_id, target.id,
                             target.kind.value, target.rarity_tier.name),),
        players=(new_player,),
    )


def _salvage(
    state: UniverseState, player_id: int, cmd: Salvage, config: GameConfig
) -> ReduceResult:
    """Log a revealed discovery into the codex (§7, WP5/WP6).

    Open-space: a hidden find must already be in `detected` (sensed on entry).
    Surface site: must have been explored (also in `detected`). Either way the
    payload is taken aboard (component → hold, latinum → purse, artifact → barter
    store; lore is codex-only) and the find marked `found_by`.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    disc = state.discoveries.get(cmd.discovery_id)
    if disc is None:
        raise EconomyError("no such discovery")
    if disc.sector_id != ship.sector_id:
        raise EconomyError("that discovery is not in this sector")
    if disc.found_by is not None:
        raise EconomyError("that discovery has already been collected")
    if disc.planet_id is not None:
        if disc.id not in player.detected:
            raise EconomyError("unexplored — survey the site first")
    elif disc.hidden and disc.id not in player.detected:
        raise EconomyError("undetected — re-enter the sector with stronger sensors")
    cost = config.discovery.salvage_turn_cost if config.discovery is not None else 1
    if player.turns_remaining < cost:
        raise MovementError("out of turns")

    payload = disc.payload
    xp = config.aliens.experience_per_discovery if disc.id not in player.codex else 0
    new_player = replace(player, turns_remaining=player.turns_remaining - cost,
                         codex=player.codex | frozenset({disc.id}),
                         experience=player.experience + xp)
    new_ship = ship
    if payload.kind is PayloadKind.COMPONENT and payload.component is not None and payload.tier is not None:
        if ship.holds_free < 1:
            raise EngineRoomError("no free hold for the salvaged component — sell cargo first")
        key = (payload.component, payload.tier)
        new_ship = replace(ship, components={**ship.components, key: ship.components.get(key, 0) + 1})
    elif payload.kind is PayloadKind.LATINUM:
        new_player = replace(new_player, latinum=new_player.latinum + payload.latinum)
    elif payload.kind is PayloadKind.ARTIFACT and payload.barter_tier is not None:
        artifacts = dict(player.artifacts)
        artifacts[payload.barter_tier] = artifacts.get(payload.barter_tier, 0) + 1
        new_player = replace(new_player, artifacts=artifacts)
    # LORE: codex-only, nothing material.
    new_disc = replace(disc, found_by=player_id)
    return ReduceResult(
        events=(DiscoveryCollected(player_id, disc.id, disc.kind.value,
                                   disc.rarity_tier.name, payload.kind.value,
                                   describe_payload(payload)),),
        players=(new_player,), ships=(new_ship,), discoveries=(new_disc,),
    )


# --- Genesis torpedoes: buy / deploy (§4.2, WP10) ---------------------------


def _buy_genesis(state: UniverseState, player_id: int, config: GameConfig) -> ReduceResult:
    """Buy one Genesis torpedo from the StarDock (§4.2, WP10)."""
    if config.genesis is None:
        raise EconomyError("genesis torpedoes are not sold in this universe")
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    gen = config.genesis
    if player.latinum < gen.price:
        raise EconomyError("insufficient latinum for a genesis torpedo")
    new_devices = {**ship.devices, gen.device_id: ship.devices.get(gen.device_id, 0) + 1}
    new_ship = replace(ship, devices=new_devices)
    new_player = replace(player, latinum=player.latinum - gen.price)
    return ReduceResult(
        events=(DevicePurchased(player_id, gen.device_id, gen.price),),
        players=(new_player,), ships=(new_ship,),
    )


def _deploy_genesis(
    state: UniverseState, player_id: int, cmd: DeployGenesis, config: GameConfig
) -> ReduceResult:
    """Terraform an eligible unowned planet in the current sector (§4.2, WP10).

    Deterministic: the world is re-typed to the configured `result_type` and its
    yield/habitability re-rolled from config (no RNG), so the change replays exactly.
    """
    if config.genesis is None:
        raise EconomyError("genesis torpedoes are not sold in this universe")
    player = _player(state, player_id)
    ship = _ship(state, player)
    gen = config.genesis
    if ship.devices.get(gen.device_id, 0) < 1:
        raise EconomyError("no genesis torpedo aboard")
    planet = state.planets.get(cmd.planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such planet in this sector")
    if planet.owner.is_owned:
        raise EconomyError("that world is claimed — genesis only re-forms unclaimed worlds")
    if planet.planet_type not in gen.eligible_types:
        raise EconomyError(f"a {planet.planet_type} world cannot be re-formed by genesis")
    new_devices = dict(ship.devices)
    new_devices[gen.device_id] = new_devices[gen.device_id] - 1
    if new_devices[gen.device_id] == 0:
        del new_devices[gen.device_id]
    new_ship = replace(ship, devices=new_devices)
    new_planet = retype_planet(planet, gen.result_type, config)
    return ReduceResult(
        events=(GenesisDeployed(player_id, planet.id, gen.result_type),),
        ships=(new_ship,), planets=(new_planet,),
    )


# --- alien contact: hail / buy / barter (§6, §8, WP9) -----------------------


def _species_here(state: UniverseState, ship: Ship, species_id: int) -> AlienSpecies:
    """The species at the player's current sector, or raise if not in contact range."""
    species = state.species.get(species_id)
    if species is None or species.sector_id != ship.sector_id:
        raise EconomyError("no such species in this sector")
    return species


def _species_config(config: GameConfig, species: AlienSpecies) -> SpeciesConfig:
    if config.roster is None:
        raise EconomyError("no species roster configured")
    sc = config.roster.species_by_id(species.roster_id)
    if sc is None:
        raise EconomyError(f"species {species.roster_id!r} is not in the roster")
    return sc


def _advance_recency(player: Player, species_key: str, context: str,
                     new_ring: tuple[int, ...]) -> dict[tuple[str, str], tuple[int, ...]]:
    """A copy of the player's dialogue recency with one (instance key, context) slot updated."""
    recency = dict(player.dialogue_recency)
    recency[(species_key, context)] = new_ring
    return recency


def _met(player: Player, roster_id: str) -> Mapping[str, float]:
    """Mark a species *kind* met (attitude entry exists) without changing the offset."""
    if roster_id in player.species_attitudes:
        return player.species_attitudes
    return {**player.species_attitudes, roster_id: 0.0}


def _subject_extra(state: UniverseState, subject_id: int | None) -> dict[str, str]:
    """The `{subject}` placeholder fill for an 'ask about X' line, or empty (§6.7, WP17)."""
    if subject_id is None:
        return {}
    subject = state.species.get(subject_id)
    return {"subject": subject.name} if subject is not None else {}


def _hail(state: UniverseState, player_id: int, cmd: Hail, config: GameConfig) -> ReduceResult:
    """Open contact — the greeting case of the general conversation path (WP17).

    The roaming Entity's sensor gate and first-contact codex stamp live in `_converse`
    (§7, WP35), so both the hail and a raw `Converse(greeting)` obey them.
    """
    return _converse(state, player_id, Converse(cmd.species_id, "greeting"), config)


def _stamp_entity_codex(result: ReduceResult, player_id: int, state: UniverseState,
                        config: GameConfig) -> ReduceResult:
    """Log the Entity's reserved codex row on first contact (§7, WP35), folding it into `result`.

    Once-only and replay-idempotent: the reserved row is collected exactly once (`found_by`
    latches), so a re-hail leaves `result` untouched. Awards `experience_per_discovery` and
    emits `DiscoveryCollected` — no new command/event type, so the codec is unchanged.
    """
    disc = entity_codex_discovery(state)
    if disc is None or disc.found_by is not None:
        return result  # no reserved row, or already logged — idempotent
    player = next((p for p in result.players if p.id == player_id), state.players[player_id])
    new_player = replace(
        player, codex=player.codex | frozenset({disc.id}),
        experience=player.experience + config.aliens.experience_per_discovery)
    new_disc = replace(disc, found_by=player_id)
    event = DiscoveryCollected(player_id, disc.id, disc.kind.value, disc.rarity_tier.name,
                               disc.payload.kind.value, describe_payload(disc.payload))
    others = tuple(p for p in result.players if p.id != player_id)
    return replace(result, players=others + (new_player,),
                   events=result.events + (event,),
                   discoveries=result.discoveries + (new_disc,))


def _intel_bindings(state: UniverseState, player: Player, species: AlienSpecies,
                    context: str, config: GameConfig) -> tuple[dict[str, str], dict[str, object]]:
    """The `offer_coordinates` placeholder fills + `has_intel_target` fact for a context (§6.7).

    Empty for every other context. Shared by the plain say path, the branch-choice path, and
    (mirrored in) the read-only projection, so all agree on the tip a friendly speaker offers.
    """
    extra: dict[str, str] = {}
    facts: dict[str, object] = {}
    if context == "offer_coordinates":
        target = pick_intel_target(state, player, species, aliens=config.aliens,
                                   entity=entity_species(state, config))
        facts["has_intel_target"] = target is not None
        if target is not None:
            extra.update(target.bindings())
    elif context in ("contract_offer", "contract_report"):
        offer = contracts.pick_contract(state, species, player, config)
        facts["has_contract_offer"] = offer is not None
        if offer is not None:
            extra.update(contracts.offer_bindings(state, offer, config))
    return extra, facts


def _speak_context(state: UniverseState, player: Player, ship: Ship, species: AlienSpecies,
                   context: str, config: GameConfig, *, extra: Mapping[str, str] | None = None,
                   facts: Mapping[str, object] | None = None,
                   subject_id: int | None = None) -> tuple[Player, AlienSpoke]:
    """Speak `context` in the species' voice: advance its recency ring, return (player, event).

    The ring-advancing core both the plain say path and a branch transition share. Marks the
    species met and records where it was seen, exactly as a hail does. Also drives the
    per-contact session (§6.7, WP28): selection reads the **pre-utterance** session facts
    (the very facts the projection showed the line under — lockstep), then the utterance is
    recorded on the session; `farewell` closes the visit.
    """
    assert config.roster is not None
    all_facts = dialogue_facts.contact_facts(state, player, species,
                                             roster=config.roster, extra=facts)
    key = dialogue.instance_key(species)
    ring = player.dialogue_recency.get((key, context), ())
    rng = dialogue.encounter_rng(state.game.seed, key, context, ring)
    _, new_ring = dialogue.speak(config.roster, species, player, context,
                                 aliens=config.aliens, rng=rng, extra=extra, facts=all_facts)
    session = dialogue_facts.note_topic(
        dialogue_facts.ensure_session(player, species, ship.sector_id), context)
    new_player = replace(
        player, species_attitudes=_met(player, species.roster_id),
        species_last_seen={**player.species_last_seen, species.roster_id: ship.sector_id},
        dialogue_recency=_advance_recency(player, key, context, new_ring),
        contact_session=None if context == "farewell" else session)
    return new_player, AlienSpoke(player.id, species.id, context, subject_id)


def _combat_speak(state: UniverseState, player: Player, species: AlienSpecies, context: str,
                  config: GameConfig, facts: Mapping[str, object]) -> tuple[Player, AlienSpoke]:
    """Speak a combat beat in the species' voice (§6.7, WP31): advance its recency ring.

    The combat sibling of `_speak_context`, minus the visit bookkeeping — a firefight is
    not a conversation, so it never opens a session, marks the species met, or stamps
    `species_last_seen`. Selection reads the same shared fact assembly (situational +
    callback + arc layers under the encounter facts), and the ring advances through the
    command exactly as `Converse` does, so repeat interceptions rephrase and the fight
    replays exactly. The encounter screen renders the beat read-only from
    `Encounter.speech_context`.
    """
    assert config.roster is not None
    all_facts = dialogue_facts.contact_facts(state, player, species,
                                             roster=config.roster, extra=facts)
    key = dialogue.instance_key(species)
    ring = player.dialogue_recency.get((key, context), ())
    rng = dialogue.encounter_rng(state.game.seed, key, context, ring)
    _, new_ring = dialogue.speak(config.roster, species, player, context,
                                 aliens=config.aliens, rng=rng, facts=all_facts)
    new_player = replace(
        player, dialogue_recency=_advance_recency(player, key, context, new_ring))
    return new_player, AlienSpoke(player.id, species.id, context, None)


def _converse(state: UniverseState, player_id: int, cmd: Converse,
              config: GameConfig) -> ReduceResult:
    """Speak a chosen peaceful dialogue context and advance its recency ring (§6.7, WP17).

    The single ring-advancing conversation path (`Hail` is `Converse(greeting)`). Guards:
    the context must be peaceful (combat / signature lines are Phase 3) and the species
    must be in the player's sector — a rejected context raises rather than silently
    no-ops, so neither the codec nor the menu can smuggle a Phase-3 line through. When the
    command carries a `choice_index` it is instead a player reply on a branching node,
    handled by `_converse_choice`.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    species = _species_here(state, ship, cmd.species_id)
    sc = _species_config(config, species)
    entity = sc.singular_entity
    if entity and not entity_contactable(state, ship.sensor_rating, ship.sector_id, config):
        # The roaming Entity's contact is sensor-gated at Legendary difficulty (§7, WP35, H2)
        # — re-checked here (not only in the projection) so a crafted or replayed command log
        # can never reach it below sensor rating. First contact stamps its codex row below.
        raise EconomyError(
            "the anomaly slips past your sensors — you cannot make contact "
            "(raise your sensor rating)")
    if cmd.choice_index is not None:
        result = _converse_choice(state, player_id, cmd, config, player, ship, species)
        return _stamp_entity_codex(result, player_id, state, config) if entity else result
    if cmd.context not in dialogue.reachable_contexts(sc):
        # Non-peaceful (combat / sig.*) or a context the species can't reach (its params):
        # raise rather than silently no-op, so the codec/menu can't smuggle a line through.
        raise EconomyError(f"not something you can say here ({cmd.context})")
    subject = _subject_extra(state, cmd.subject_id)
    intel_extra, facts = _intel_bindings(state, player, species, cmd.context, config)
    new_player, event = _speak_context(
        state, player, ship, species, cmd.context, config,
        extra={**subject, **intel_extra}, facts=facts, subject_id=cmd.subject_id)
    result = ReduceResult(events=(event,), players=(new_player,))
    return _stamp_entity_codex(result, player_id, state, config) if entity else result


def _converse_choice(state: UniverseState, player_id: int, cmd: Converse, config: GameConfig,
                     player: Player, ship: Ship, species: AlienSpecies) -> ReduceResult:
    """Apply an authored player reply on a branching node (§6.7 optional branching).

    `cmd.context` names the node shown; the reducer re-resolves that node's line (read-only,
    with the same RNG inputs the projection used, so it sees the very choices the player
    did), validates the indexed choice and its `when`, then applies it: an `accept_lead`
    choice delegates to the lead logger; `attack` ends the conversation and opens
    first-strike combat (`_attack_species`, WP70); `leave` speaks the parting line; any
    other choice transitions to its `next_context` (or re-speaks the node for a
    trade/barter gateway, the mechanical effect riding on the follow-up Buy/Barter
    command). Position lives only on the command, so this stays replay-stable.
    """
    assert config.roster is not None
    assert cmd.choice_index is not None  # _converse only routes here when it is set
    if not dialogue.is_known_context(cmd.context):
        raise EconomyError(f"unknown dialogue context ({cmd.context})")
    _, facts = _intel_bindings(state, player, species, cmd.context, config)
    if (cmd.context == "dossier_other" or cmd.context.startswith("branch.dossier_other.")) and cmd.subject_id is not None:
        subject_sp = state.species.get(cmd.subject_id)
        if subject_sp is not None:
            facts["subject"] = subject_sp.roster_id
    # Session facts join the node's own (§6.7, WP28) — the same merge the projection's
    # `_contact_choices` makes, so `choice_index` resolves into the very menu shown.
    facts = dialogue_facts.contact_facts(state, player, species,
                                         roster=config.roster, extra=facts)
    key = dialogue.instance_key(species)
    ring = player.dialogue_recency.get((key, cmd.context), ())
    rng = dialogue.encounter_rng(state.game.seed, key, cmd.context, ring)
    # The reply menu resolves via the same fallback (entry choices → generic baseline) the
    # contact-screen view uses, so the position `choice_index` carries agrees on both sides.
    choices = dialogue.choices_for(config.roster, species, player, cmd.context,
                                   aliens=config.aliens, rng=rng, facts=facts)
    if not choices:
        raise EconomyError("there is nothing to choose here")
    if not 0 <= cmd.choice_index < len(choices):
        raise EconomyError("no such reply")
    choice = choices[cmd.choice_index]
    allied = player.alliance_id is not None and player.alliance_id == species.alliance_id
    standing = dialogue.standing_for(
        effective_disposition(species, player), allied=allied, aliens=config.aliens)
    if not dialogue.when_matches(choice.when, standing=standing, treaty=False, facts=facts):
        raise EconomyError("you cannot say that right now")
    if choice.action == "attack":
        # Live since WP70: the reply ends the conversation and opens first-strike combat.
        # `_attack_species` owns every gate (Core sanctuary, the Entity, influence_gate's
        # forbid, shipless kinds) and the §6.5 first-strike souring.
        return _attack_species(state, player_id, AttackSpecies(cmd.species_id), config)

    mutated_player = player
    log_events: tuple[Event, ...] = ()
    if choice.action == "accept_lead":
        lead_result = _accept_lead(state, player_id, AcceptLead(cmd.species_id), config)
        log_events = lead_result.events
        mutated_player = lead_result.players[0]
    if choice.action == "accept_contract":
        job_result = _accept_contract(state, player_id, species, config)
        log_events = job_result.events
        mutated_player = job_result.players[0]
    if choice.arc:
        # The reply's authored arc flags persist on the species kind (§6.7, WP30) —
        # applied before the follow-up line speaks, so it can already react to them.
        arcs = dict(mutated_player.species_arcs)
        arcs[species.roster_id] = {**arcs.get(species.roster_id, {}), **choice.arc}
        mutated_player = replace(mutated_player, species_arcs=arcs)

    target = "farewell" if choice.action == "leave" else (choice.next_context or cmd.context)
    if target == "back":
        return ReduceResult(events=log_events, players=(mutated_player,))
    if target.startswith("sig."):
        # A choice into a signature-mechanic prompt (§6.2, WP33): run the hook, apply its
        # effects, then speak the sig line under the verdict it produced.
        return _resolve_mechanic(
            state, config, mutated_player, ship, species, target, log_events)
    extra, t_facts = _intel_bindings(state, mutated_player, species, target, config)
    if (target == "dossier_other" or target.startswith("branch.dossier_other.")) and cmd.subject_id is not None:
        subject_sp = state.species.get(cmd.subject_id)
        if subject_sp is not None:
            extra["subject"] = subject_sp.name
            t_facts["subject"] = subject_sp.roster_id
    new_player, speak_event = _speak_context(
        state, mutated_player, ship, species, target, config, extra=extra, facts=t_facts,
        subject_id=cmd.subject_id)
    return ReduceResult(events=log_events + (speak_event,), players=(new_player,))


def _resolve_mechanic(state: UniverseState, config: GameConfig, player: Player, ship: Ship,
                      species: AlienSpecies, target: str,
                      log_events: tuple[Event, ...]) -> ReduceResult:
    """Run the species' signature-mechanic hook, apply its effects, then speak the sig line.

    Reached when an authored choice transitions into a `sig.*` prompt (§6.2, WP33). The hook
    (`core.mechanics.run_hook`) is pure: it audits conduct and returns a ladder `stage`
    (persisted in `species_arcs` under `mechanics.STAGE_FLAG`), transient `facts` the verdict
    line gates on (e.g. `{verdict: blessed}`), and bounded effects this reducer applies and
    reports. An absent or not-yet-implemented (WP37) hook resolves to `None` — the sig line
    then simply speaks with no effect, so a `sig.*` branch never crashes on an inert hook.
    """
    assert config.roster is not None
    sc = _species_config(config, species)
    params = sc.signature_mechanic.params if sc.signature_mechanic is not None else {}
    stage = player.species_arcs.get(species.roster_id, {}).get(mechanics.STAGE_FLAG)
    # The reply keyword a transactional hook keys on (§6.2, WP37) is the last segment of the
    # `sig.<hook>.<node>` context the choice routes into — e.g. `sig.trojan_gift.accept` →
    # "accept". morality_judge ignores it, so this is inert for the WP33 hooks.
    approach = target.rsplit(".", 1)[-1] if target.startswith("sig.") else None
    result = mechanics.run_hook(mechanics.MechanicContext(
        player=player, species=species, sc=sc, aliens=config.aliens,
        stage=stage if isinstance(stage, str) else None, params=params, approach=approach))
    mutated_player = player
    effect_events: tuple[Event, ...] = ()
    if result is not None:
        mutated_player, effect_events = _apply_mechanic(
            state, mutated_player, species, sc, result, config)
    # The verdict line gates on the **persisted** `sig_stage` (surfaced by
    # `dialogue.facts`), never a transient hook fact — so the projection reconstructs the
    # same line/menu the reducer speaks (the §6.7 view/reducer lockstep). The stage is
    # already persisted on `mutated_player` above, before this utterance selects.
    extra, t_facts = _intel_bindings(state, mutated_player, species, target, config)
    new_player, speak_event = _speak_context(
        state, mutated_player, ship, species, target, config, extra=extra, facts=t_facts)
    return ReduceResult(events=log_events + effect_events + (speak_event,),
                        players=(new_player,))


def _apply_mechanic(state: UniverseState, player: Player, species: AlienSpecies,
                    sc: SpeciesConfig, result: mechanics.MechanicResult,
                    config: GameConfig) -> tuple[Player, tuple[Event, ...]]:
    """Apply a hook's bounded effects to the player and emit the matching WP27 events.

    Effects are mutually-exclusive in practice: a `grudge` (a curse) routes through the WP27
    `sour_attitude` machinery (attitude drop + grudge + `memory_model`/permanent handling),
    while a plain `attitude_delta` (a boon) shifts the offset directly unless a permanent
    grudge has locked it. Alignment/experience deltas add straight on; a latinum delta (a
    boon or a WP37 drain) is applied clamped at zero (no negative balance). The ladder stage
    persists in `species_arcs` so the mechanic replays exactly.
    """
    events: list[Event] = []
    new_player = player
    if result.stage:
        arcs = dict(new_player.species_arcs)
        arcs[species.roster_id] = {
            **arcs.get(species.roster_id, {}), mechanics.STAGE_FLAG: result.stage}
        new_player = replace(new_player, species_arcs=arcs)
    if result.grudge:
        soured = sour_attitude(
            new_player, species, sc, config.aliens, state.game.day_number, 1)
        if soured is not new_player:  # memory_model none forgets instantly (no events)
            grudge = soured.grudges[species.roster_id]
            events.append(GrudgeFormed(
                player.id, species.roster_id, grudge.severity, grudge.duration_days < 0))
            events.append(AttitudeChanged(
                player.id, species.id,
                round(soured.species_attitudes[species.roster_id], 6),
                round(effective_disposition(species, soured), 6)))
            new_player = soured
    elif result.attitude_delta and not attitude_locked(new_player, species.roster_id):
        offset = new_player.species_attitudes.get(species.roster_id, 0.0)
        new_offset = round(max(-1.0, min(1.0, offset + result.attitude_delta)), 6)
        if new_offset != offset:
            new_player = replace(new_player, species_attitudes={
                **new_player.species_attitudes, species.roster_id: new_offset})
            events.append(AttitudeChanged(
                player.id, species.id, new_offset,
                round(effective_disposition(species, new_player), 6)))
    if result.alignment_delta or result.experience_delta:
        new_player = replace(
            new_player, alignment=new_player.alignment + result.alignment_delta,
            experience=new_player.experience + result.experience_delta)
    if result.latinum_delta:
        # A drain (a trojan payload, an extortion, a broker's price) can exceed the purse:
        # clamp at zero so the no-negative-balance invariant holds (they take all you have).
        new_player = replace(new_player, latinum=max(0, new_player.latinum + result.latinum_delta))
    return new_player, tuple(events)


def _accept_lead(state: UniverseState, player_id: int, cmd: AcceptLead,
                 config: GameConfig) -> ReduceResult:
    """Log the coordinate tip the species is offering as a `Lead` (§6.7, the map mechanic).

    Guards mirror conversation: the species must be in the player's sector and currently
    hold an intel target. A tip already in the leads log is never re-offered (the planner
    excludes it), so this never stacks duplicates — a re-accept simply finds nothing new.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    species = _species_here(state, ship, cmd.species_id)
    target: IntelTarget | None = pick_intel_target(
        state, player, species, aliens=config.aliens, entity=entity_species(state, config))
    if target is None:
        raise EconomyError("they have no coordinates to share")
    lead = Lead(kind=target.ref.kind, ref=target.ref.ref, sector_id=target.ref.sector_id,
                origin_sector=ship.sector_id,
                source_species=species.roster_id, summary=target.summary())
    session = dialogue_facts.note(
        dialogue_facts.ensure_session(player, species, ship.sector_id),
        dialogue_facts.ACCEPTED_LEAD)
    new_player = replace(player, leads=(*player.leads, lead),
                         species_attitudes=_met(player, species.roster_id),
                         contact_session=session)
    event = LeadAccepted(player_id, species.id, target.ref.kind, target.ref.ref,
                         target.ref.sector_id)
    return ReduceResult(events=(event,), players=(new_player,))


def _accept_contract(state: UniverseState, player_id: int, species: AlienSpecies,
                     config: GameConfig) -> ReduceResult:
    """Book the favor a species is offering onto the player's slate (§6.7, WP57).

    Re-picks the offer deterministically (`pick_contract`, the same choice the projection
    showed — H4 lockstep) rather than trusting a passed job, so a crafted/replayed command
    can never smuggle a richer contract through. Appends it as an active job and logs the
    acceptance. A no-op error if the speaker has nothing to offer now.
    """
    player = _player(state, player_id)
    offer = contracts.pick_contract(state, species, player, config)
    if offer is None:
        raise EconomyError("they have no work for you right now")
    booked = contracts.accept(player, offer, state.game.day_number, config)
    new_player = replace(player, contracts=(*player.contracts, booked),
                         species_attitudes=_met(player, species.roster_id))
    event = ContractAccepted(player_id, booked.id, booked.kind, booked.issuer,
                             booked.reward_slips, booked.deadline_day)
    return ReduceResult(events=(event,), players=(new_player,))


def _deliver_contract(state: UniverseState, player_id: int, cmd: DeliverContract,
                      config: GameConfig) -> ReduceResult:
    """Fulfil a `deliver` favor at its destination port (§6.7, WP57).

    Guards: the job is an active deliver contract, the ship is in the destination sector,
    and it carries the required cargo. The cargo debits (conserved out of the hold), the
    reward credits through `apply_reward`, and the contract flips to done. Rewards flow
    through the same latinum/attitude rails a completed favor always uses.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    contract = contracts.by_id(player, cmd.contract_id)
    if contract is None or contract.status != "active" or contract.kind != "deliver":
        raise EconomyError("no such active delivery")
    if contract.commodity is None or contract.dest_sector is None:
        raise EconomyError("that delivery has no destination")
    if ship.sector_id != contract.dest_sector:
        raise EconomyError(
            f"deliver it at sector {_spatial(state, contract.dest_sector)}")
    have = ship.cargo.get(contract.commodity, 0)
    if have < contract.qty:
        raise EconomyError(
            f"you carry only {have} of {contract.qty} {contract.commodity.value}")
    new_cargo = {**ship.cargo, contract.commodity: have - contract.qty}
    new_ship = replace(ship, cargo=new_cargo)
    done_player = contracts.set_status(player, contract.id, "done")
    paid = contracts.apply_reward(done_player, contract, state)
    event = ContractCompleted(player_id, contract.id, contract.kind, contract.reward_slips)
    return ReduceResult(events=(event,), players=(paid,), ships=(new_ship,))


def _abandon_contract(state: UniverseState, player_id: int, cmd: AbandonContract,
                      config: GameConfig) -> ReduceResult:
    """Release an active favor, failing it honestly (§6.7, WP57).

    An escort merchant simply resumes its rails (the `is_convoyed` predicate goes false once
    the job is no longer active). No consequence rail on a plain abandon — that is reserved
    for a *destroyed* escort merchant (the WP27 rail, handled in combat).
    """
    player = _player(state, player_id)
    contract = contracts.by_id(player, cmd.contract_id)
    if contract is None or contract.status != "active":
        raise EconomyError("no such active contract")
    new_player = contracts.set_status(player, contract.id, "failed")
    event = ContractFailed(player_id, contract.id, contract.kind, "abandoned")
    return ReduceResult(events=(event,), players=(new_player,))


def _core_welcome_species(state: UniverseState, port: Port) -> list[AlienSpecies]:
    """The Core-welcome species staged at the StarDock — the tavern's rumour-mongers (§14).

    These are the species pinned to the hub (the governing alliance's friendly members and
    the peaceable wanderers stationed there); their pooled knowledge is what the tavern sells.
    """
    return [sp for sp in state.species.values() if sp.sector_id == port.sector_id]


def _buy_rumor(state: UniverseState, player_id: int, config: GameConfig) -> ReduceResult:
    """Buy a rumour at the tavern — a latinum-for-`Lead` sink (§14, WP58).

    Gated to the StarDock (the tavern is there); charges `tavern.rumor_price`; draws the best
    undiscovered tip the Core-welcome species collectively know (`pick_rumor`, deterministic +
    deduped against the player's leads/codex/explored, so repeat buys exhaust like repeated
    asks). Logs it as a `Lead` — intel for cash, the standing-free twin of asking a contact.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    port = _stardock(state, ship)
    price = config.tavern.rumor_price
    if player.latinum < price:
        raise EconomyError(f"a rumour costs {price} slips")
    target = pick_rumor(state, player, _core_welcome_species(state, port),
                        aliens=config.aliens, entity=entity_species(state, config))
    if target is None:
        raise EconomyError("the tavern has no fresh rumours for you")
    lead = Lead(kind=target.ref.kind, ref=target.ref.ref, sector_id=target.ref.sector_id,
                origin_sector=ship.sector_id, source_species="tavern",
                summary=target.summary())
    new_player = replace(player, latinum=player.latinum - price, leads=(*player.leads, lead))
    event = RumorHeard(player_id, target.ref.kind, target.ref.ref, target.ref.sector_id, price)
    return ReduceResult(events=(event,), players=(new_player,))


def _post_notice(state: UniverseState, player_id: int, cmd: PostNotice,
                 config: GameConfig) -> ReduceResult:
    """Pin a sanitised message to the tavern noticeboard's capped ring (§14, WP58).

    The one string-input command, so validation is explicit: text is stripped to printable
    characters and length-capped, and an empty result is rejected. The notice appends to the
    ring; the oldest is evicted once it exceeds `tavern.notice_cap`.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)  # the board is at the tavern
    text = "".join(ch for ch in cmd.text if ch.isprintable()).strip()[:config.tavern.notice_max_len]
    if not text:
        raise EconomyError("your notice is empty")
    notice = Notice(author_player_id=player_id, day=state.game.day_number, text=text)
    ring = (*state.notices, notice)[-config.tavern.notice_cap:]
    event = NoticePosted(player_id, state.game.day_number)
    return ReduceResult(events=(event,), notices=ring)


# --- corporations (DESIGN §4, WP66) ------------------------------------------


def _corp_of(state: UniverseState, player_id: int) -> Corporation:
    """The player's corporation, or raise (the gate on every corp action)."""
    c = corp.player_corp(state, player_id)
    if c is None:
        raise EconomyError("you are not in a corporation")
    return c


def _form_corp(state: UniverseState, player_id: int, cmd: FormCorp,
               config: GameConfig) -> ReduceResult:
    """Charter a corporation: pay the fee, become CEO + sole member (§4, WP66)."""
    player = _player(state, player_id)
    if player.corp_id is not None:
        raise EconomyError("you already belong to a corporation")
    name = cmd.name.strip()
    tag = cmd.tag.strip().upper()
    cc = config.corp
    if not name:
        raise EconomyError("a corporation needs a name")
    if not tag or not tag.isalnum() or len(tag) > cc.tag_max_len:
        raise EconomyError(f"tag must be 1-{cc.tag_max_len} alphanumeric characters")
    if any(existing.tag == tag for existing in state.corporations.values()):
        raise EconomyError(f"the tag {tag!r} is already taken")
    if player.latinum < cc.form_fee:
        raise EconomyError(
            f"chartering a corp costs {cc.form_fee} latinum (have {player.latinum})")
    cid = max(state.corporations, default=0) + 1
    corp_ent = Corporation(id=cid, name=name, tag=tag, ceo_player_id=player_id,
                           member_player_ids=frozenset({player_id}))
    new_player = replace(player, latinum=player.latinum - cc.form_fee, corp_id=cid)
    return ReduceResult(events=(CorpFormed(player_id, cid, name, tag, cc.form_fee),),
                        players=(new_player,), corporations=(corp_ent,))


def _invite_to_corp(state: UniverseState, player_id: int, cmd: InviteToCorp,
                    config: GameConfig) -> ReduceResult:
    """CEO invites a player — step one of the two-step (consent) join (§4, WP66)."""
    _player(state, player_id)
    c = _corp_of(state, player_id)
    if c.ceo_player_id != player_id:
        raise EconomyError("only the CEO may invite members")
    invitee = state.players.get(cmd.invitee_player_id)
    if invitee is None:
        raise EconomyError("no such player")
    if invitee.corp_id is not None:
        raise EconomyError("that player already belongs to a corporation")
    new_corp = replace(c, invited_player_ids=c.invited_player_ids | {cmd.invitee_player_id})
    return ReduceResult(events=(CorpInvited(player_id, c.id, cmd.invitee_player_id),),
                        corporations=(new_corp,))


def _accept_corp_invite(state: UniverseState, player_id: int, cmd: AcceptCorpInvite,
                        config: GameConfig) -> ReduceResult:
    """The invitee consents and joins (§4, WP66) — no press-ganging."""
    player = _player(state, player_id)
    if player.corp_id is not None:
        raise EconomyError("you already belong to a corporation")
    c = state.corporations.get(cmd.corp_id)
    if c is None:
        raise EconomyError("no such corporation")
    if player_id not in c.invited_player_ids:
        raise EconomyError("you have not been invited to that corporation")
    new_corp = replace(c, member_player_ids=c.member_player_ids | {player_id},
                       invited_player_ids=c.invited_player_ids - {player_id})
    new_player = replace(player, corp_id=c.id)
    return ReduceResult(events=(CorpJoined(player_id, c.id),),
                        players=(new_player,), corporations=(new_corp,))


def _dissolve_corp(state: UniverseState, c: Corporation, ceo: Player) -> ReduceResult:
    """Wind up a corp when its last member (the CEO) leaves (§4, WP66).

    Assets re-key to the departing CEO — owned things stay owned, never revert to `none`
    (documented rationale) — and the shared bank pays out to their personal latinum (no
    latinum vanishes). Any war another corp still holds against this one ends with it.
    """
    corp_owner = Ownership("corp", c.id)
    to_ceo = Ownership("player", ceo.id)
    planets = tuple(replace(p, owner=to_ceo) for p in state.planets.values() if p.owner == corp_owner)
    starbases = tuple(replace(b, owner=to_ceo) for b in state.starbases.values() if b.owner == corp_owner)
    forces = tuple(replace(f, owner=to_ceo) for f in state.sector_forces.values() if f.owner == corp_owner)
    paid_out = replace(ceo, corp_id=None, latinum=ceo.latinum + c.bank_balance)
    others = tuple(replace(o, at_war_with=o.at_war_with - {c.id})
                   for o in state.corporations.values()
                   if o.id != c.id and c.id in o.at_war_with)
    return ReduceResult(events=(CorpDeparted(ceo.id, c.id, "dissolved"),),
                        players=(paid_out,), planets=planets, starbases=starbases,
                        sector_forces=forces, corporations=others, dissolved_corps=(c.id,))


def _depart_corp(state: UniverseState, c: Corporation, member_id: int, reason: str) -> ReduceResult:
    """Remove a member; the last one out dissolves the corp (§4, WP66)."""
    remaining = c.member_player_ids - {member_id}
    departing = replace(state.players[member_id], corp_id=None)
    if not remaining:
        return _dissolve_corp(state, c, departing)
    # A departing CEO hands the chair to the lowest-id remaining member (deterministic, no RNG).
    ceo = min(remaining) if member_id == c.ceo_player_id else c.ceo_player_id
    new_corp = replace(c, member_player_ids=remaining, ceo_player_id=ceo,
                       invited_player_ids=c.invited_player_ids - {member_id})
    return ReduceResult(events=(CorpDeparted(member_id, c.id, reason),),
                        players=(departing,), corporations=(new_corp,))


def _leave_corp(state: UniverseState, player_id: int, config: GameConfig) -> ReduceResult:
    _player(state, player_id)
    return _depart_corp(state, _corp_of(state, player_id), player_id, "left")


def _expel_from_corp(state: UniverseState, player_id: int, cmd: ExpelFromCorp,
                     config: GameConfig) -> ReduceResult:
    _player(state, player_id)
    c = _corp_of(state, player_id)
    if c.ceo_player_id != player_id:
        raise EconomyError("only the CEO may expel members")
    if cmd.member_player_id == player_id:
        raise EconomyError("the CEO cannot expel themselves — leave to dissolve the corp")
    if cmd.member_player_id not in c.member_player_ids:
        raise EconomyError("that player is not a member")
    return _depart_corp(state, c, cmd.member_player_id, "expelled")


def _corp_bank(state: UniverseState, player_id: int, amount: int, config: GameConfig,
               *, withdraw_: bool) -> ReduceResult:
    """Move latinum between a member's purse and the corp bank (§4, WP66).

    Deposits are open to any member; withdrawals are CEO-gated (the shared purse). Neither the
    purse nor the bank may go negative — the `core.economy` non-negativity invariant, reused.
    """
    player = _player(state, player_id)
    c = _corp_of(state, player_id)
    if amount <= 0:
        raise EconomyError("amount must be positive")
    if withdraw_:
        if c.ceo_player_id != player_id:
            raise EconomyError("only the CEO may withdraw from the corp bank")
        if c.bank_balance < amount:
            raise EconomyError("the corp bank lacks that balance")
        new_corp = replace(c, bank_balance=c.bank_balance - amount)
        new_player = replace(player, latinum=player.latinum + amount)
        kind = "withdraw"
    else:
        if player.latinum < amount:
            raise EconomyError("insufficient latinum")
        new_corp = replace(c, bank_balance=c.bank_balance + amount)
        new_player = replace(player, latinum=player.latinum - amount)
        kind = "deposit"
    event = CorpBanked(player_id, c.id, kind, amount, new_corp.bank_balance)
    return ReduceResult(events=(event,), players=(new_player,), corporations=(new_corp,))


def _transfer_planet(state: UniverseState, player_id: int, planet_id: int, config: GameConfig,
                     *, to_corp: bool) -> ReduceResult:
    """Move a world between a member's personal ownership and the corp (§4, WP66) — in-sector."""
    player = _player(state, player_id)
    c = _corp_of(state, player_id)
    ship = _ship(state, player)
    planet = state.planets.get(planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such world in this sector")
    if to_corp:
        if not (planet.owner.kind == "player" and planet.owner.ref == player_id):
            raise EconomyError("you do not personally own that world")
        new_owner = Ownership("corp", c.id)
    else:
        if c.ceo_player_id != player_id:
            raise EconomyError("only the CEO may return corp worlds")
        if not (planet.owner.kind == "corp" and planet.owner.ref == c.id):
            raise EconomyError("that world is not owned by your corp")
        new_owner = Ownership("player", player_id)
    event = PlanetTransferred(player_id, planet_id, c.id, to_corp)
    return ReduceResult(events=(event,), planets=(replace(planet, owner=new_owner),))


def _declare_corp_war(state: UniverseState, player_id: int, cmd: DeclareCorpWar,
                      config: GameConfig) -> ReduceResult:
    """CEO declares war on a rival corp (§4, WP66) — hostility is mutual-by-declaration."""
    _player(state, player_id)
    c = _corp_of(state, player_id)
    if c.ceo_player_id != player_id:
        raise EconomyError("only the CEO may declare war")
    target = state.corporations.get(cmd.target_corp_id)
    if target is None:
        raise EconomyError("no such corporation")
    if target.id == c.id:
        raise EconomyError("a corporation cannot war itself")
    if cmd.target_corp_id in c.at_war_with:
        raise EconomyError("already at war with that corporation")
    ready_day = c.war_cooldowns.get(cmd.target_corp_id)
    if ready_day is not None and state.game.day_number < ready_day:
        raise EconomyError(f"a war cooldown blocks re-declaration until day {ready_day}")
    new_corp = replace(c, at_war_with=c.at_war_with | {cmd.target_corp_id})
    return ReduceResult(events=(CorpWarDeclared(player_id, c.id, cmd.target_corp_id),),
                        corporations=(new_corp,))


def _end_corp_war(state: UniverseState, player_id: int, cmd: EndCorpWar,
                  config: GameConfig) -> ReduceResult:
    """CEO unilaterally withdraws from a war, opening a re-declaration cooldown (§4, WP66)."""
    _player(state, player_id)
    c = _corp_of(state, player_id)
    if c.ceo_player_id != player_id:
        raise EconomyError("only the CEO may end a war")
    if cmd.target_corp_id not in c.at_war_with:
        raise EconomyError("you are not at war with that corporation")
    ready_day = state.game.day_number + config.corp.war_cooldown_days
    new_corp = replace(c, at_war_with=c.at_war_with - {cmd.target_corp_id},
                       war_cooldowns={**c.war_cooldowns, cmd.target_corp_id: ready_day})
    return ReduceResult(events=(CorpWarEnded(player_id, c.id, cmd.target_corp_id),),
                        corporations=(new_corp,))


def _advance_admission(state: UniverseState, player_id: int, cmd: AdvanceAdmission,
                       config: GameConfig) -> ReduceResult:
    """Record one completed admission or Core-seizure task in a bloc's ledger (§6.3, WP38/WP50).

    A task token may belong to the bloc's `admission_price`, its `core_seizure.price`, or
    both; it is recorded into whichever ledger(s) it belongs — admission into the
    `@alliance` ledger, seizure into the reserved `@seizure` ledger (WP50) — so seizure
    progress rides the same replay-safe machinery without double-booking.
    """
    player = _player(state, player_id)
    if config.roster is None:
        raise EconomyError("no alliances in this game")
    ac = config.roster.alliance(cmd.alliance_id)
    if ac is None:
        raise EconomyError("no such alliance")
    in_admission = cmd.task in ac.admission_price
    in_seizure = ac.core_seizure is not None and cmd.task in ac.core_seizure.price
    if not in_admission and not in_seizure:
        raise EconomyError(f"{cmd.task!r} is not part of {ac.name}'s admission price")
    new_player = player
    if in_admission:
        new_player = record_admission_task(new_player, cmd.alliance_id, cmd.task)
    if in_seizure:
        new_player = record_seizure_task(new_player, cmd.alliance_id, cmd.task)
    return ReduceResult(
        events=(AdmissionAdvanced(player_id, cmd.alliance_id, cmd.task),),
        players=(new_player,),
    )


def _petition_core_seizure(state: UniverseState, player_id: int, cmd: PetitionCoreSeizure,
                           config: GameConfig) -> ReduceResult:
    """Champion a `covets_core` bloc into the Core, flipping the governor (§6.3, WP50).

    Every gate carries a precise reason (the `_gate_choice` explain-why discipline) so the
    projection checklist and this reducer stay in lockstep. On success it charges the fee
    and folds `flip_core_governor` into one `ReduceResult` (game + re-keyed Core planets/
    bases + relocated incumbents).
    """
    player = _player(state, player_id)
    _require_no_encounter(player)
    if config.roster is None:
        raise EconomyError("no alliances in this game")
    ac = config.roster.alliance(cmd.alliance_id)
    if ac is None:
        raise EconomyError("no such alliance")
    if ac.core_seizure is None or not ac.covets_core:
        raise EconomyError(f"{ac.name} cannot seize the Core")
    prog = seizure_progress(state, player, ac, ac.core_seizure)
    if prog.already_governs:
        raise EconomyError(f"{ac.name} already governs the Core")
    if not prog.is_member:
        raise EconomyError(f"you must be a sworn member of {ac.name} to champion them")
    if not prog.consented:
        raise EconomyError(f"{ac.name} will not have you champion them at this standing")
    if not prog.tasks_met:
        missing = sorted(set(prog.tasks_required) - prog.tasks_done)
        raise EconomyError(f"{ac.name}'s price is not yet paid: {', '.join(missing)}")
    if not prog.bases_met:
        raise EconomyError(
            f"the incumbent still holds the Core — raze {prog.bases_required - prog.bases_razed} "
            "more of its Core-planet bases")
    if not prog.fee_affordable:
        raise EconomyError(f"you cannot afford {ac.name}'s seizure fee ({prog.fee})")
    new_player = replace(player, latinum=player.latinum - ac.core_seizure.fee)
    delta = flip_core_governor(state, config, cmd.alliance_id, cause="player_champion")
    return ReduceResult(
        events=delta.events, players=(new_player,), game=delta.game,
        planets=delta.planets, starbases=delta.starbases, species=delta.species,
    )


def _join_alliance(state: UniverseState, player_id: int, cmd: JoinAlliance,
                   config: GameConfig) -> ReduceResult:
    """Join a bloc (§6.3, WP38): gated by admission, exclusive, with rival fallout."""
    player = _player(state, player_id)
    _require_no_encounter(player)
    if config.roster is None:
        raise EconomyError("no alliances in this game")
    ac = config.roster.alliance(cmd.alliance_id)
    if ac is None:
        raise EconomyError("no such alliance")
    if player.alliance_id == cmd.alliance_id:
        raise EconomyError(f"you are already a member of {ac.name}")
    if ac.membership_gate == "petition" and not admission_met(player, ac):
        raise EconomyError(f"{ac.name} will not admit you until you meet their price")
    if player.latinum < ac.admission_fee:
        raise EconomyError(f"you cannot afford {ac.name}'s admission fee")
    former = player.alliance_id
    new_player = replace(player, latinum=player.latinum - ac.admission_fee)
    new_player = apply_join_standing(new_player, config.roster, cmd.alliance_id)
    return ReduceResult(
        events=(AllianceJoined(player_id, cmd.alliance_id, former),),
        players=(new_player,),
    )


def _resign_alliance(state: UniverseState, player_id: int,
                     cmd: ResignAlliance, config: GameConfig) -> ReduceResult:
    """Leave the current bloc (§6.3, WP38): standing resets, sanctuary recovers."""
    player = _player(state, player_id)
    _require_no_encounter(player)
    if player.alliance_id is None:
        raise EconomyError("you belong to no alliance")
    former = player.alliance_id
    new_player = apply_resign_standing(player)
    return ReduceResult(
        events=(AllianceResigned(player_id, former),),
        players=(new_player,),
    )


def _select_offer(config: GameConfig, species: AlienSpecies, player: Player,
                  offer_index: int) -> TechOfferConfig:
    sc = _species_config(config, species)
    if not 0 <= offer_index < len(sc.tech_offers):
        raise EconomyError("no such tech offer")
    offer = sc.tech_offers[offer_index]
    if effective_disposition(species, player) < offer.min_disposition:
        raise EconomyError("they will not offer you that yet — raise your standing first")
    return offer


def _deliver_offer(ship: Ship, offer: TechOfferConfig) -> tuple[Ship, str]:
    """Apply a tech offer to the hull: a loose component or a flat aspect bump."""
    if offer.component is not None:
        if ship.holds_free < 1:
            raise EconomyError("no free hold for the component — sell cargo first")
        component, tier = Component(offer.component), ComponentTier[offer.tier]
        key = (component, tier)
        new_ship = replace(ship, components={**ship.components, key: ship.components.get(key, 0) + 1})
        return new_ship, f"{component.value} ({offer.tier})"
    if offer.aspect == "sensors":
        return replace(ship, sensor_rating=ship.sensor_rating + offer.amount), f"sensors +{offer.amount}"
    if offer.aspect == "cloak":
        return replace(ship, cloak_rating=ship.cloak_rating + offer.amount), f"cloak +{offer.amount}"
    if offer.aspect == "holds":
        return replace(ship, holds_total=ship.holds_total + offer.amount), f"holds +{offer.amount}"
    raise EconomyError(f"unsupported tech offer ({offer.aspect})")


def _raise_attitude(player: Player, species: AlienSpecies,
                    config: GameConfig) -> tuple[Player, AttitudeChanged]:
    """Raise the player's attitude offset toward `species` (capped so effective ≤ 1).

    A permanent grudge (§6.5: `never_forgets` / `betrayal_model=permanent`) locks the
    offset where the betrayal left it — amends no longer move it (WP27).
    """
    sc = _species_config(config, species)
    cap = max(0.0, 1.0 - species.base_disposition)
    current = player.species_attitudes.get(species.roster_id, 0.0)
    if attitude_locked(player, species.roster_id):
        effective = effective_disposition(species, player)
        return player, AttitudeChanged(player.id, species.id, round(current, 6), round(effective, 6))
    new_offset = min(cap, current + sc.attitude_gain_rate)
    attitudes = {**player.species_attitudes, species.roster_id: new_offset}
    new_player = replace(player, species_attitudes=attitudes)
    # Reputation spillover (§6.4, WP39): warming to this species also nudges its friends
    # and enemies in proportion to their relations to it.
    if config.roster is not None:
        spilled = apply_spillover(
            new_player, species.roster_id, new_offset - current, config.roster, config.aliens)
        new_player = replace(new_player, species_attitudes=spilled)
    effective = effective_disposition(species, new_player)
    return new_player, AttitudeChanged(player.id, species.id, round(new_offset, 6), round(effective, 6))


def _trade_alien(state: UniverseState, player_id: int, species_id: int, offer_index: int,
                 config: GameConfig, *, barter: bool) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    species = _species_here(state, ship, species_id)
    assert config.roster is not None
    offer = _select_offer(config, species, player, offer_index)

    cost = 0
    if barter:
        if offer.mode != "barter":
            raise EconomyError("that offer is a latinum sale, not a barter")
        if player.artifacts.get(offer.tier, 0) < 1:
            raise EconomyError(f"you have no Tier-{offer.tier} artifact to barter")
    else:
        if offer.mode != "latinum":
            raise EconomyError("that offer is barter-only — trade an artifact for it")
        cost = offer.price
        if player.latinum < cost:
            raise EconomyError("insufficient latinum for that offer")

    new_ship, detail = _deliver_offer(ship, offer)
    new_player = player
    if barter:
        artifacts = dict(player.artifacts)
        artifacts[offer.tier] = artifacts[offer.tier] - 1
        if artifacts[offer.tier] == 0:
            del artifacts[offer.tier]
        new_player = replace(new_player, artifacts=artifacts)
    else:
        new_player = replace(new_player, latinum=new_player.latinum - cost)

    new_player, attitude_event = _raise_attitude(new_player, species, config)
    # Advance the trade dialogue ring so a repeat sale rephrases, then mark the visit's
    # session `traded` (§6.7, WP28) — selection sees the pre-utterance facts (lockstep).
    trade_facts = dialogue_facts.contact_facts(state, new_player, species,
                                               roster=config.roster)
    key = dialogue.instance_key(species)
    ring = player.dialogue_recency.get((key, "trade_open"), ())
    rng = dialogue.encounter_rng(state.game.seed, key, "trade_open", ring)
    _, new_ring = dialogue.speak(config.roster, species, new_player, "trade_open",
                                 aliens=config.aliens, rng=rng, facts=trade_facts)
    session = dialogue_facts.note(
        dialogue_facts.ensure_session(new_player, species, ship.sector_id),
        dialogue_facts.TRADED)
    new_player = replace(new_player,
                         dialogue_recency=_advance_recency(new_player, key, "trade_open", new_ring),
                         contact_session=session)
    kind = "barter" if barter else "buy"
    return ReduceResult(
        events=(AlienTraded(player_id, species.id, kind, detail, cost), attitude_event),
        players=(new_player,), ships=(new_ship,),
    )


def _buy_alien_tech(state: UniverseState, player_id: int, cmd: BuyAlienTech,
                    config: GameConfig) -> ReduceResult:
    return _trade_alien(state, player_id, cmd.species_id, cmd.offer_index, config, barter=False)


def _barter_artifact(state: UniverseState, player_id: int, cmd: BarterArtifact,
                     config: GameConfig) -> ReduceResult:
    return _trade_alien(state, player_id, cmd.species_id, cmd.offer_index, config, barter=True)
