"""WP9 — command/event serialization round-trips (DESIGN §12)."""

from __future__ import annotations

import pytest

from typing import get_args

from edge.core.enums import Commodity, Component, ComponentTier, PortMode, Subsystem
from edge.core.events import (
    AdmissionAdvanced,
    AlienDestroyed,
    AlienHailed,
    AlienMoved,
    AlienSpoke,
    AlienTraded,
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
    NoticePosted,
    RumorHeard,
    AllianceJoined,
    AllianceResigned,
    AttitudeChanged,
    Banked,
    BaseCommission,
    BeltMined,
    CargoTransferred,
    CloudCityBuilt,
    FightersTransferred,
    GarrisonReinforced,
    CitadelBuildStarted,
    CitadelCompleted,
    CitadelGunSilenced,
    Colonized,
    ColonistsRecruited,
    GroundOrdnanceBought,
    RecruitsDismissed,
    RecruitsHired,
    SuitsPurchased,
    SuitsSold,
    ColonistsSettled,
    ColonyGrew,
    CombatRound,
    InterdictorToggled,
    LimpetsRemoved,
    PlanetBanked,
    PlanetInvaded,
    ProbeReport,
    ComponentInstalled,
    ComponentKnockedOut,
    ComponentPurchased,
    ComponentRemoved,
    CoreLawNotice,
    DevApplied,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    EncounterEnded,
    EncounterEvaded,
    EncounterStarted,
    GenesisDeployed,
    GroundAssaultDropped,
    GroundAssaultSettled,
    GroundBroadcastMade,
    GroundDefenseFireLogged,
    GroundFired,
    GroundJumped,
    GroundMoved,
    GroundOperationBegan,
    GroundOperationEnded,
    GroundTurnEnded,
    ProtectorateAnnexed,
    ProtectorateEstablished,
    GrudgeFormed,
    HazardDamage,
    SurveyDug,
    SurveySiteExcavated,
    SurveyLanded,
    SurveyTalked,
    Event,
    AllianceLeadershipChanged,
    GovernanceChanged,
    Haggled,
    LeadAccepted,
    MarketSettled,
    PlanetProduced,
    PortOrderFilled,
    Repaired,
    SalvageCollected,
    ShipDestroyed,
    ShipPurchased,
    StarbaseClaimed,
    StarbaseRazed,
    StarbaseRepaired,
    StarbaseSalvaged,
    StockRegenerated,
    TerritoryDeployed,
    Traded,
    TurnsReset,
    Warped,
)
from edge.core.rules import (
    AbandonContract,
    AcceptCorpInvite,
    AcceptLead,
    AddNote,
    AttackPlayer,
    AttackSpecies,
    BuyRumor,
    CorpDeposit,
    CorpWithdraw,
    DeclareCorpWar,
    DeliverContract,
    EndCorpWar,
    ExpelFromCorp,
    FormCorp,
    InviteToCorp,
    LeaveCorp,
    TransferPlanetFromCorp,
    TransferPlanetToCorp,
    PostNotice,
    AdvanceAdmission,
    AssaultStarbase,
    BarterArtifact,
    BuyAlienTech,
    BuyComponent,
    BuyGenesis,
    BuyMissiles,
    BuyShip,
    BuildStagingArea,
    BuyFighters,
    BuyMines,
    Cannibalize,
    ClaimStarbase,
    BeginAssault,
    AnnexProtectorate,
    Colonize,
    CombatAction,
    Command,
    Converse,
    DeployBeacon,
    DeployFighters,
    BeginSurvey,
    ReinforceGarrison,
    TransferFighters,
    DeployGenesis,
    DeployMines,
    Deposit,
    Dock,
    ExtractGroundOperation,
    FieldPatch,
    EndGroundTurn,
    GroundBroadcast,
    GroundDrop,
    GroundFire,
    GroundJump,
    GroundMove,
    Hail,
    HaggleOffer,
    MineBelt,
    InstallComponent,
    JoinAlliance,
    JoinGame,
    PetitionCoreSeizure,
    BuyGroundOrdnance,
    BuySuits,
    DismissRecruits,
    HireRecruits,
    RecruitColonists,
    SellSuits,
    RepairAtDock,
    RepairStarbase,
    ResignAlliance,
    Salvage,
    SetAllocation,
    SetPlayerName,
    SettleColonists,
    SurveyDig,
    SurveyLand,
    SurveyTalk,
    SwapComponent,
    BuildCitadel,
    BuyDevice,
    LaunchProbe,
    PlanetDeposit,
    PlanetWithdraw,
    RemoveLimpets,
    RemoveNote,
    ToggleAvoid,
    ToggleInterdictor,
    Trade,
    BatchTransferCargo, TransferCargo,
    TravelTo,
    Warp,
    Withdraw,
)
from edge.core.dev import DevPatch
from edge.store import codec

COMMANDS: list[Command] = [
    JoinGame(),
    JoinGame(name="Pathfinder"),
    SetPlayerName(name="ada"),
    Warp(to_sector=12),
    TravelTo(to_sector=20),
    Dock(),
    Trade(commodity=Commodity.FUEL_ORE, units=10, unit_price=13),
    Trade(commodity=Commodity.ORGANICS, units=5),  # unit_price None
    HaggleOffer(commodity=Commodity.EQUIPMENT, units=4, counter_price=20),
    Deposit(amount=500),
    Withdraw(amount=250),
    BuyComponent(Component.TURBINE, ComponentTier.II),
    BuyShip("scout_marauder"),
    RepairAtDock(Subsystem.THRUSTERS, 1),
    RecruitColonists(count=40, from_planet=None),
    RecruitColonists(count=10, from_planet=7),
    RecruitColonists(count=10, from_planet=7, species_id="vesk"),  # multi-species world
    HireRecruits(count=6),
    DismissRecruits(count=2),
    BuySuits(suit_id="marauder", count=3),
    SellSuits(suit_id="scout", count=1),
    BuyGroundOrdnance(count=4),
    Colonize(planet_id=5, colonists=25),
    Colonize(planet_id=5, colonists=25, species_id="terran"),  # explicit multi-species pick
    SettleColonists(planet_id=5, colonists=25),        # WP-PR07 top up an owned colony
    SettleColonists(planet_id=5, colonists=25, species_id="terran"),
    SetAllocation(planet_id=5, allocation={"fuel_ore": 0.5, "organics": 0.5}),
    BuildCitadel(planet_id=5),                       # WP54 open a timed citadel build
    PlanetDeposit(planet_id=5, amount=1_000),        # WP54 treasury deposit
    PlanetWithdraw(planet_id=5, amount=500),         # WP54 treasury withdraw
    SetAllocation(planet_id=5, allocation={"equipment": 0.6}, fighter=0.4),  # WP55 garrison share
    SetAllocation(planet_id=5, allocation={"equipment": 0.5}, garrison=0.5),  # GW-WP09 ground garrison share
    TransferCargo(planet_id=5, commodity=Commodity.EQUIPMENT, units=120),  # §4.2 supply haul
    TransferCargo(planet_id=5, commodity=Commodity.ORGANICS, units=30, to_planet=False),
    TransferFighters(planet_id=5, count=15),  # GW-WP09 unload ship fighters onto a world
    TransferFighters(planet_id=5, count=8, to_planet=False),  # GW-WP09 load stored fighters aboard
    BatchTransferCargo(planet_id=5, units={"fuel_ore": 40, "equipment": 90}),
    ReinforceGarrison(planet_id=5, suit_id="marauder", count=6),  # GW-WP09/D15 station a garrison
    InstallComponent(Subsystem.SPINDRIVE, 3, Component.TURBINE, ComponentTier.II),
    SwapComponent(Subsystem.SCREENS, 1, Component.RADIATOR, ComponentTier.III),
    Cannibalize(Subsystem.MAIN_GUN, 2),
    Cannibalize(Subsystem.FUSION_REACTOR, 0, starbase_id=4),  # WP4 starbase salvage
    FieldPatch(Subsystem.THRUSTERS, 0),
    Salvage(discovery_id=7),      # WP5 log a discovery to the codex
    BeginSurvey(planet_id=5),     # GW-WP03 open a surface-survey expedition
    BeginAssault(planet_id=5),    # GW-WP09 open a tactical ground assault
    AnnexProtectorate(planet_id=5),  # GW-WP11 convert a recovered protectorate
    ExtractGroundOperation(operation_id=123),  # GW-WP03 settle/clear a ground op
    GroundMove(operation_id=123, x=40, y=20, actor_id=0),  # GW-WP06 march the explorer
    SurveyDig(operation_id=123),  # GW-WP06 open a trench
    SurveyLand(operation_id=123, x=17, y=9),  # GW-WP07-FU2 player-chosen drop site
    SurveyTalk(operation_id=123),  # GW-WP06 settlement resupply/hint
    GroundDrop(operation_id=123, placements=(("marauder", 4, 29), ("scout", 5, 29))),  # GW-WP10
    GroundJump(operation_id=123, actor_id=1, x=6, y=27),  # GW-WP10 jump-jet hop
    GroundFire(operation_id=123, actor_id=1, x=10, y=11),  # GW-WP10 fire at a cell
    GroundFire(operation_id=123, actor_id=1, x=10, y=11, missile=True),  # GW-WP10 missile shot
    GroundBroadcast(operation_id=123, actor_id=1),  # GW-WP10 dictate terms over a cowed city
    EndGroundTurn(operation_id=123),  # GW-WP10 close the tactical phase
    MineBelt(planet_id=5),        # PT-30 hand-mine an asteroid belt
    BuildStagingArea(planet_id=5),  # PT-54 stage a Cloud City on a gas giant
    BuyGenesis(),                 # WP10 buy a genesis torpedo
    DeployGenesis(planet_id=5),   # WP10 terraform a world
    Hail(species_id=3),                          # WP9 open alien contact
    Converse(species_id=3, context="farewell"),  # WP17 say a peaceful line
    Converse(species_id=3, context="dossier_other", subject_id=5),  # WP17 ask about X
    Converse(species_id=3, context="branch.vesk_workshop", choice_index=1),  # §6.7 branching reply
    BuyAlienTech(species_id=3, offer_index=1),   # WP9 buy tech for latinum
    BarterArtifact(species_id=3, offer_index=0), # WP9 barter an artifact for tech
    AcceptLead(species_id=3),                    # §6.7 log an alien's coordinate tip
    DeliverContract(contract_id=2),              # WP57 fulfil a deliver favor
    AbandonContract(contract_id=2),              # WP57 release a favor
    BuyRumor(),                                  # WP58 buy a tavern rumor
    PostNotice(text="fuel cheap in the Deep"),   # WP58 pin a noticeboard message
    AddNote(text="quill pack near S9"),          # WP73 captain's note
    RemoveNote(index=0),                         # WP73 delete a note
    ToggleAvoid(sector_id=9),                    # WP73 route-planner avoid list
    AdvanceAdmission(alliance_id=3, task="pay"), # WP38 complete an admission task
    JoinAlliance(alliance_id=3),                 # WP38 join a bloc
    ResignAlliance(),                            # WP38 leave the current bloc
    PetitionCoreSeizure(alliance_id=4),          # WP50 champion a covets_core bloc
    AssaultStarbase(starbase_id=2),              # WP40 begin a set-piece assault
    RepairStarbase(2, Subsystem.FUSION_REACTOR, 0, Component.CONVERTER, ComponentTier.I),  # WP40
    ClaimStarbase(starbase_id=2),                # WP40 claim a repaired base
    BuyFighters(count=20),                       # WP41 buy fighter stock
    BuyMines(count=5),                           # WP41 buy mine stock
    DeployFighters(count=10, mode="toll", toll=50),  # WP41 garrison a sector
    DeployMines(count=3),                        # WP41 seed mines (armid default)
    DeployMines(count=2, kind="limpet"),         # WP56 limpet mines
    DeployBeacon(text="Kilroy was here"),        # WP41 plant a beacon
    BuyDevice(device_id="probe"),                # WP56 buy a device
    LaunchProbe(dest_sector=42),                 # WP56 launch a probe
    ToggleInterdictor(),                         # WP56 toggle the interdictor
    RemoveLimpets(),                             # WP56 strip limpets
    FormCorp(name="Vanguard", tag="VAN"),        # WP66 charter a corp
    InviteToCorp(invitee_player_id=2),           # WP66 invite (step one)
    AcceptCorpInvite(corp_id=1),                 # WP66 accept (step two)
    LeaveCorp(),                                 # WP66 leave / dissolve
    ExpelFromCorp(member_player_id=2),           # WP66 CEO expel
    CorpDeposit(amount=500),                     # WP66 corp bank in
    CorpWithdraw(amount=200),                    # WP66 corp bank out (CEO)
    TransferPlanetToCorp(planet_id=5),           # WP66 member → corp
    TransferPlanetFromCorp(planet_id=5),         # WP66 corp → CEO
    DeclareCorpWar(target_corp_id=2),            # WP66 declare war
    EndCorpWar(target_corp_id=2),                # WP66 withdraw
    AttackPlayer(target_player_id=2),            # WP67 open PvP
    AttackSpecies(species_id=7),                 # WP70 first strike on an alien contact
    CombatAction(action="fight"),                # WP25 one combat round
    CombatAction(action="flee"),
    CombatAction(action="field_patch", subsystem=Subsystem.SCREENS, slot_index=1),
    BuyMissiles(count=3),                        # WP25 Stardock missile ammo
    DevPatch("set", "latinum", 1_000_000),            # dev cheat: set a field
    DevPatch("grant", "component", 2, key="accelerator:III"),  # dev cheat: grant parts
    DevPatch("claim", "planet", ref=5),               # dev cheat: claim a world
]

EVENTS: list[Event] = [
    Warped(1, 7, 12, 1),
    Warped(1, 7, 12, 1, one_way=True),  # one-way warp heads-up (§9)
    Docked(1, 12, 3),
    Traded(1, 3, Commodity.FUEL_ORE, PortMode.SELL, 10, 13, 130),
    Traded(1, 3, Commodity.ORGANICS, PortMode.BUY, 12, 6, 72, 20),  # WP47 partial fill (requested 20)
    MarketSettled(4, 120, 900),                        # WP47 daily settlement summary
    PortOrderFilled(3, Commodity.FUEL_ORE, "buy", 40, 9, 5),  # WP47 one explored-port fill
    Haggled(1, 3, Commodity.ORGANICS, "accepted", 6),
    BaseCommission(2, 4, 3, "player", 1, 36),          # WP78 base-hosted market rent
    BaseCommission(2, 4, 3, "corp", 1, 36),
    Banked(1, "interest", 50, 10_050),
    ComponentPurchased(1, "turbine", "II", 8_000),
    ShipPurchased(1, "scout_marauder", 20_000, 0),
    ColonistsRecruited(1, "stardock", 40, 200),
    RecruitsHired(1, 6, 1500),
    RecruitsDismissed(1, 2, 100),
    SuitsPurchased(1, "marauder", 3, 5400),
    SuitsSold(1, "scout", 1, 350, 0),
    GroundOrdnanceBought(1, 4, 1600),
    Colonized(1, 5, 25),
    ColonistsSettled(1, 5, 25),
    PlanetProduced(5, 1),
    ColonyGrew(5, 1_050),
    CargoTransferred(1, 5, Commodity.EQUIPMENT, 120, True),  # §4.2 colony-supply haul
    FightersTransferred(1, 5, 15, True),               # GW-WP09 ship -> planet fighter haul
    GarrisonReinforced(1, 5, "marauder", 6),            # GW-WP09/D15 station a garrison
    CitadelBuildStarted(1, 5, 1),                      # WP54 citadel build opened
    CitadelCompleted(5, 1),                            # WP54 citadel level reached
    PlanetBanked(1, 5, "deposit", 1_000, 1_000),       # WP54 treasury move
    CitadelGunSilenced(1, 5),                          # WP55 gun knocked out
    PlanetInvaded(1, 5, 40, 500, 3_000),               # WP55 conquest
    ProbeReport(1, 42, 6, 2, 3, 1, False),             # WP56 probe recon
    InterdictorToggled(1, True),                       # WP56 interdictor engaged
    LimpetsRemoved(1, 4, 500),                         # WP56 limpets stripped
    ComponentInstalled(1, "spindrive", 3, "turbine", "II"),
    ComponentRemoved(1, "main_gun", 2, "linkage", "I"),
    Repaired(1, "thrusters", 0),
    StarbaseSalvaged(1, 4, "fusion_reactor", 0, "converter", "I"),
    DiscoveryDetected(1, 7, "wreck", "RARE"),
    DiscoveryCollected(1, 7, "wreck", "RARE", "artifact"),
    GroundOperationBegan(1, 123, "survey", 5),
    GroundOperationEnded(1, 123, "survey", "extracted"),
    GroundAssaultDropped(1, 123, 4, 0),                 # GW-WP10 platoon landed
    GroundJumped(1, 123, 1, 6, 27, True),               # GW-WP10 jump drew AA fire
    GroundFired(1, 123, 1, 10, 11, False, True, "structure", True),  # GW-WP10 shot destroyed a wall
    GroundBroadcastMade(1, 123, 1, 2),                  # GW-WP10 terms dictated over a cowed city
    GroundTurnEnded(1, 123, 3, 88, 1, ""),              # GW-WP10 tactical round settled
    GroundDefenseFireLogged(1, 123, "hit", "Doc takes 6 from garrison infantry (14 hp)",
                            10, 11, False),              # a defender-phase hit, now surfaced
    GroundAssaultSettled(1, 5, "surrender", "protectorate", 1, 7, 20, 2, 0),
    ProtectorateEstablished(1, 5, "player", 1),
    ProtectorateAnnexed(1, 5, "player", 1),
    GroundMoved(1, 123, 40, 20, 2),
    SurveyDug(1, 123, 40, 20, 9),
    SurveySiteExcavated(1, 123, 9, "ruins", "RARE"),
    SurveyLanded(1, 123, 17, 9),
    SurveyTalked(1, 123, 1, 9),
    BeltMined(1, 5, "equipment", 50),
    CloudCityBuilt(1, 5, 1, 50),
    DevicePurchased(1, "genesis_torpedo", 15_000),
    GenesisDeployed(1, 5, "terrestrial_warm"),
    TurnsReset(1, 250),
    StockRegenerated(3, Commodity.EQUIPMENT, 480),
    AlienHailed(1, 3),
    AlienMoved(3, 7, 12),
    AlienDestroyed(4, 12, "mine+fighter"),
    AlienSpoke(1, 3, "greeting", None),
    AlienSpoke(1, 3, "dossier_other", 5),
    AlienTraded(1, 3, "buy", "radiator (II)", 7_000),
    AttitudeChanged(1, 3, 0.12, 0.87),
    LeadAccepted(1, 3, "discovery", 42, 17),  # §6.7 accepted a coordinate tip
    ContractAccepted(1, 2, "deliver", "terran", 450, 13),  # WP57 took a favor
    ContractCompleted(1, 2, "deliver", 450),               # WP57 fulfilled a favor
    ContractFailed(1, 2, "escort", "deadline"),            # WP57 a favor lapsed
    RumorHeard(1, "discovery", 42, 17, 500),               # WP58 bought a tavern rumor
    NoticePosted(1, 5),                                    # WP58 pinned a notice
    CorpFormed(1, 1, "Vanguard", "VAN", 5000),             # WP66 chartered a corp
    CorpInvited(1, 1, 2),                                  # WP66 CEO invited a player
    CorpJoined(2, 1),                                      # WP66 invitee joined
    CorpDeparted(2, 1, "expelled"),                        # WP66 left/expelled/dissolved
    CorpBanked(1, 1, "deposit", 500, 500),                 # WP66 corp bank move
    PlanetTransferred(1, 5, 1, True),                      # WP66 world → corp
    CorpWarDeclared(1, 1, 2),                              # WP66 declared war
    CorpWarEnded(1, 1, 2),                                 # WP66 withdrew from war
    PlayerAttacked(1, 2, 55),                              # WP67 opened PvP
    BountyPosted(1, 5000, 5000),                           # WP67 outlaw bounty
    EncounterStarted(1, 3, 55, True, 3, "Deep"),   # WP24 a violence opener
    EncounterStarted(1, 3, 55, False, 0, "Deep"),  # WP24 a peaceful interception
    EncounterEvaded(1, 3, 55),                     # WP24 slipped away unseen
    CombatRound(1, 3, 2, "fight", 24, 11, 2),      # WP25 one resolved round
    EncounterEnded(1, 3, "fled"),                  # WP25 outcome
    EncounterEnded(1, 3, "retreated", destroyed=2, fled=1, foe_name="Stryx pack"),  # WP-PR03
    ComponentKnockedOut(1, "thrusters", 1, "burner"),   # WP26 localized damage
    ShipDestroyed(1, 3, 55, "trailblazer"),             # WP26 hull 0 → escape pod
    SalvageCollected(1, 42, ("burner", "linkage")),     # WP26 wreck salvage
    SalvageCollected(1, 17, ()),                        # WP26 latinum-only salvage
    GrudgeFormed(1, "vennrith", 0.6, True),             # WP27 a permanent vendetta
    CoreLawNotice(1, 3),                                # WP27 governor's warning
    GovernanceChanged(1, 2, "dev"),                     # WP49 the Core changed hands
    AllianceLeadershipChanged(3, "thessarch", "vennrith"),  # WP51 an internal coup
    AdmissionAdvanced(1, 3, "pay"),                     # WP38 admission task done
    AllianceJoined(1, 3, None),                         # WP38 joined a bloc (was unaligned)
    AllianceJoined(1, 3, 1),                            # WP38 switched blocs
    AllianceResigned(1, 3),                             # WP38 left a bloc
    StarbaseRazed(1, 2, 5, 55, "alliance", 3, 750),     # WP40 razed a bloc base
    StarbaseRazed(1, 2, 5, 55, "none", None, 750),      # WP40 razed an unowned base
    StarbaseRepaired(1, 2, "fusion_reactor", 0, "converter", "I"),  # WP40 refill a slot
    StarbaseClaimed(1, 2, 2000),                        # WP40 claimed a base
    TerritoryDeployed(1, 55, "fighters", 10, "toll"),   # WP41 deployed a garrison
    TerritoryDeployed(1, 55, "beacon", 1),              # WP41 planted a beacon
    HazardDamage(1, 55, "mine", 80),                    # WP41 mine field on entry
    HazardDamage(1, 55, "black_hole", 30),              # WP41 gravity shear
    DevApplied(1, "[dev] set latinum=1000000"),  # dev cheat audit marker
]


@pytest.mark.parametrize("command", COMMANDS)
def test_command_round_trips(command: Command) -> None:
    type_, payload = codec.encode_command(command)
    assert codec.decode_command(type_, payload) == command


@pytest.mark.parametrize("event", EVENTS)
def test_event_round_trips(event: Event) -> None:
    type_, payload = codec.encode_event(event)
    assert type_ == type(event).__name__
    assert isinstance(payload, dict)
    assert codec.decode_event(type_, payload) == event


def test_every_command_variant_is_covered() -> None:
    """Exhaustiveness guard: every member of the `Command` union round-trips (§12).

    Fails the build if a new command type is added without a `COMMANDS` fixture (and
    thus without a codec entry), so a command can't silently skip the log.
    """
    covered = {type(c) for c in COMMANDS}
    declared = set(get_args(Command))
    assert declared - covered == set(), f"command variants missing a codec fixture: {declared - covered}"


def test_decode_unknown_command_raises() -> None:
    with pytest.raises(ValueError):
        codec.decode_command("Nonsense", {})


def test_encode_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        codec.encode_event(Event())


def test_decode_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        codec.decode_event("Nonsense", {})
