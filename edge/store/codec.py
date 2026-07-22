"""(De)serialize commands and events to JSON-able payloads for the logs (§12).

Commands round-trip (encode for persistence, decode for replay); events encode
only — they are append-only facts the store never has to reconstruct into objects
for Phase-1 replay (state comes from replaying the *command* log).
"""

from __future__ import annotations

from typing import Any

from edge.core.enums import Commodity, Component, ComponentTier, PortMode, Subsystem
from edge.core.events import (
    AdmissionAdvanced,
    AlienDestroyed,
    AlienHailed,
    AlienMoved,
    AlienSpoke,
    AlienTraded,
    AllianceJoined,
    AllianceLeadershipChanged,
    AllianceResigned,
    AttitudeChanged,
    Banked,
    BaseCommission,
    BeltMined,
    CargoTransferred,
    CloudCityBuilt,
    CitadelBuildStarted,
    CitadelCompleted,
    CitadelGunSilenced,
    Colonized,
    ColonistsRecruited,
    FightersTransferred,
    GarrisonReinforced,
    GroundOrdnanceBought,
    RecruitsDismissed,
    RecruitsHired,
    SuitsPurchased,
    SuitsSold,
    ColonistsSettled,
    ColonyGrew,
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
    CombatRound,
    InterdictorToggled,
    InvasionRepulsed,
    LimpetsRemoved,
    PlanetBanked,
    PlanetInvaded,
    ProbeReport,
    ComponentInstalled,
    ComponentKnockedOut,
    ComponentPurchased,
    ComponentRemoved,
    CoreLawNotice,
    Descended,
    DevApplied,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    EncounterEnded,
    GovernanceChanged,
    EncounterEvaded,
    EncounterStarted,
    Event,
    GenesisDeployed,
    GroundAssaultDropped,
    GroundBroadcastMade,
    GroundFired,
    GroundJumped,
    GroundMoved,
    GroundOperationBegan,
    GroundOperationEnded,
    GroundTurnEnded,
    GrudgeFormed,
    Haggled,
    HazardDamage,
    LeadAccepted,
    MarketSettled,
    PlanetProduced,
    PortOrderFilled,
    Repaired,
    SalvageCollected,
    ShipDestroyed,
    ShipPurchased,
    SiteExplored,
    SurveyDug,
    SurveySiteExcavated,
    SurveyLanded,
    SurveyTalked,
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
from edge.core.dev import DevPatch
from edge.core.rules import (
    AcceptLead,
    AdvanceAdmission,
    AssaultStarbase,
    BarterArtifact,
    BuyFighters,
    BuyMines,
    BuildCitadel,
    BuildStagingArea,
    BuyAlienTech,
    BuyComponent,
    BuyDevice,
    BuyGenesis,
    BuyMissiles,
    BuyShip,
    Cannibalize,
    ClaimStarbase,
    AbandonContract,
    AcceptCorpInvite,
    AttackPlayer,
    AttackSpecies,
    BuyRumor,
    Colonize,
    CombatAction,
    Command,
    Converse,
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
    AddNote,
    PostNotice,
    RemoveNote,
    ToggleAvoid,
    BatchTransferCargo, TransferCargo, TransferFighters,
    BeginAssault,
    DeployBeacon,
    DeployFighters,
    DeployGenesis,
    DeployMines,
    Deposit,
    BeginSurvey,
    Descend,
    Dock,
    Explore,
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
    SurveyDig,
    SurveyLand,
    SurveyTalk,
    InvadePlanet,
    JoinAlliance,
    LaunchProbe,
    JoinGame,
    PetitionCoreSeizure,
    PlanetDeposit,
    PlanetWithdraw,
    BuyGroundOrdnance,
    BuySuits,
    DismissRecruits,
    HireRecruits,
    RecruitColonists,
    ReinforceGarrison,
    SellSuits,
    RemoveLimpets,
    ResignAlliance,
    RepairAtDock,
    RepairStarbase,
    Salvage,
    SetAllocation,
    SetPlayerName,
    SettleColonists,
    SwapComponent,
    ToggleInterdictor,
    Trade,
    TravelTo,
    Warp,
    Withdraw,
)


def encode_command(command: Command) -> tuple[str, dict[str, Any]]:
    """A (type tag, JSON-able payload) pair for a command."""
    match command:
        case JoinGame():
            return "JoinGame", {"name": command.name}
        case SetPlayerName():
            return "SetPlayerName", {"name": command.name}
        case Warp():
            return "Warp", {"to_sector": command.to_sector}
        case TravelTo():
            return "TravelTo", {"to_sector": command.to_sector}
        case Dock():
            return "Dock", {}
        case Trade():
            return "Trade", {
                "commodity": command.commodity.value,
                "units": command.units,
                "unit_price": command.unit_price,
            }
        case HaggleOffer():
            return "HaggleOffer", {
                "commodity": command.commodity.value,
                "units": command.units,
                "counter_price": command.counter_price,
            }
        case Deposit():
            return "Deposit", {"amount": command.amount}
        case Withdraw():
            return "Withdraw", {"amount": command.amount}
        case BuyComponent():
            return "BuyComponent", {"component": command.component.value, "tier": command.tier.name}
        case BuyShip():
            return "BuyShip", {"ship_class_id": command.ship_class_id}
        case RepairAtDock():
            return "RepairAtDock", {
                "subsystem": command.subsystem.value, "slot_index": command.slot_index,
            }
        case RecruitColonists():
            return "RecruitColonists", {
                "count": command.count, "from_planet": command.from_planet,
                "species_id": command.species_id,
            }
        case HireRecruits():
            return "HireRecruits", {"count": command.count}
        case DismissRecruits():
            return "DismissRecruits", {"count": command.count}
        case BuySuits():
            return "BuySuits", {"suit_id": command.suit_id, "count": command.count}
        case SellSuits():
            return "SellSuits", {"suit_id": command.suit_id, "count": command.count}
        case BuyGroundOrdnance():
            return "BuyGroundOrdnance", {"count": command.count}
        case Colonize():
            return "Colonize", {
                "planet_id": command.planet_id, "colonists": command.colonists,
                "species_id": command.species_id,
            }
        case SettleColonists():
            return "SettleColonists", {
                "planet_id": command.planet_id, "colonists": command.colonists,
                "species_id": command.species_id,
            }
        case BuildStagingArea():
            return "BuildStagingArea", {"planet_id": command.planet_id}
        case SetAllocation():
            return "SetAllocation", {
                "planet_id": command.planet_id, "allocation": command.allocation,
                "fighter": command.fighter, "garrison": command.garrison,
            }
        case TransferCargo():
            return "TransferCargo", {
                "planet_id": command.planet_id, "commodity": command.commodity.value,
                "units": command.units, "to_planet": command.to_planet,
            }
        case TransferFighters():
            return "TransferFighters", {
                "planet_id": command.planet_id, "count": command.count,
                "to_planet": command.to_planet,
            }
        case BatchTransferCargo():
            return "BatchTransferCargo", {
                "planet_id": command.planet_id, "units": command.units,
                "to_planet": command.to_planet,
            }
        case BuildCitadel():
            return "BuildCitadel", {"planet_id": command.planet_id}
        case PlanetDeposit():
            return "PlanetDeposit", {"planet_id": command.planet_id, "amount": command.amount}
        case PlanetWithdraw():
            return "PlanetWithdraw", {"planet_id": command.planet_id, "amount": command.amount}
        case InvadePlanet():
            return "InvadePlanet", {"planet_id": command.planet_id, "fighters": command.fighters}
        case ReinforceGarrison():
            return "ReinforceGarrison", {
                "planet_id": command.planet_id, "suit_id": command.suit_id,
                "count": command.count,
            }
        case BeginAssault():
            return "BeginAssault", {"planet_id": command.planet_id}
        case InstallComponent():
            return "InstallComponent", {
                "subsystem": command.subsystem.value, "slot_index": command.slot_index,
                "component": command.component.value, "tier": command.tier.name,
            }
        case SwapComponent():
            return "SwapComponent", {
                "subsystem": command.subsystem.value, "slot_index": command.slot_index,
                "component": command.component.value, "tier": command.tier.name,
            }
        case Cannibalize():
            return "Cannibalize", {
                "subsystem": command.subsystem.value, "slot_index": command.slot_index,
                "starbase_id": command.starbase_id,
            }
        case FieldPatch():
            return "FieldPatch", {
                "subsystem": command.subsystem.value, "slot_index": command.slot_index,
            }
        case CombatAction():
            return "CombatAction", {
                "action": command.action,
                "subsystem": command.subsystem.value if command.subsystem is not None else None,
                "slot_index": command.slot_index,
            }
        case BuyMissiles():
            return "BuyMissiles", {"count": command.count}
        case Salvage():
            return "Salvage", {"discovery_id": command.discovery_id}
        case Descend():
            return "Descend", {"planet_id": command.planet_id}
        case Explore():
            return "Explore", {"planet_id": command.planet_id}
        case BeginSurvey():
            return "BeginSurvey", {"planet_id": command.planet_id}
        case ExtractGroundOperation():
            return "ExtractGroundOperation", {"operation_id": command.operation_id}
        case GroundMove():
            return "GroundMove", {"operation_id": command.operation_id, "x": command.x,
                                  "y": command.y, "actor_id": command.actor_id}
        case SurveyDig():
            return "SurveyDig", {"operation_id": command.operation_id}
        case SurveyLand():
            return "SurveyLand", {"operation_id": command.operation_id,
                                  "x": command.x, "y": command.y}
        case SurveyTalk():
            return "SurveyTalk", {"operation_id": command.operation_id}
        case GroundDrop():
            return "GroundDrop", {
                "operation_id": command.operation_id,
                "placements": [[suit_id, x, y] for suit_id, x, y in command.placements],
            }
        case GroundJump():
            return "GroundJump", {"operation_id": command.operation_id,
                                  "actor_id": command.actor_id, "x": command.x, "y": command.y}
        case GroundFire():
            return "GroundFire", {"operation_id": command.operation_id,
                                  "actor_id": command.actor_id, "x": command.x, "y": command.y,
                                  "missile": command.missile}
        case GroundBroadcast():
            return "GroundBroadcast", {"operation_id": command.operation_id,
                                       "actor_id": command.actor_id}
        case EndGroundTurn():
            return "EndGroundTurn", {"operation_id": command.operation_id}
        case MineBelt():
            return "MineBelt", {"planet_id": command.planet_id}
        case BuyGenesis():
            return "BuyGenesis", {}
        case DeployGenesis():
            return "DeployGenesis", {"planet_id": command.planet_id}
        case Hail():
            return "Hail", {"species_id": command.species_id}
        case Converse():
            return "Converse", {
                "species_id": command.species_id, "context": command.context,
                "subject_id": command.subject_id, "choice_index": command.choice_index,
            }
        case BuyAlienTech():
            return "BuyAlienTech", {"species_id": command.species_id, "offer_index": command.offer_index}
        case BarterArtifact():
            return "BarterArtifact", {"species_id": command.species_id, "offer_index": command.offer_index}
        case AcceptLead():
            return "AcceptLead", {"species_id": command.species_id}
        case DeliverContract():
            return "DeliverContract", {"contract_id": command.contract_id}
        case AbandonContract():
            return "AbandonContract", {"contract_id": command.contract_id}
        case BuyRumor():
            return "BuyRumor", {}
        case PostNotice():
            return "PostNotice", {"text": command.text}
        case AddNote():
            return "AddNote", {"text": command.text}
        case RemoveNote():
            return "RemoveNote", {"index": command.index}
        case ToggleAvoid():
            return "ToggleAvoid", {"sector_id": command.sector_id}
        case AdvanceAdmission():
            return "AdvanceAdmission", {"alliance_id": command.alliance_id, "task": command.task}
        case JoinAlliance():
            return "JoinAlliance", {"alliance_id": command.alliance_id}
        case ResignAlliance():
            return "ResignAlliance", {}
        case PetitionCoreSeizure():
            return "PetitionCoreSeizure", {"alliance_id": command.alliance_id}
        case AssaultStarbase():
            return "AssaultStarbase", {"starbase_id": command.starbase_id}
        case RepairStarbase():
            return "RepairStarbase", {
                "starbase_id": command.starbase_id,
                "subsystem": command.subsystem.value, "slot_index": command.slot_index,
                "component": command.component.value, "tier": command.tier.name,
            }
        case ClaimStarbase():
            return "ClaimStarbase", {"starbase_id": command.starbase_id}
        case BuyFighters():
            return "BuyFighters", {"count": command.count}
        case BuyMines():
            return "BuyMines", {"count": command.count}
        case DeployFighters():
            return "DeployFighters", {
                "count": command.count, "mode": command.mode, "toll": command.toll,
            }
        case DeployMines():
            return "DeployMines", {"count": command.count, "kind": command.kind}
        case DeployBeacon():
            return "DeployBeacon", {"text": command.text}
        case BuyDevice():
            return "BuyDevice", {"device_id": command.device_id}
        case LaunchProbe():
            return "LaunchProbe", {"dest_sector": command.dest_sector}
        case ToggleInterdictor():
            return "ToggleInterdictor", {}
        case RemoveLimpets():
            return "RemoveLimpets", {}
        case FormCorp():
            return "FormCorp", {"name": command.name, "tag": command.tag}
        case InviteToCorp():
            return "InviteToCorp", {"invitee_player_id": command.invitee_player_id}
        case AcceptCorpInvite():
            return "AcceptCorpInvite", {"corp_id": command.corp_id}
        case LeaveCorp():
            return "LeaveCorp", {}
        case ExpelFromCorp():
            return "ExpelFromCorp", {"member_player_id": command.member_player_id}
        case CorpDeposit():
            return "CorpDeposit", {"amount": command.amount}
        case CorpWithdraw():
            return "CorpWithdraw", {"amount": command.amount}
        case TransferPlanetToCorp():
            return "TransferPlanetToCorp", {"planet_id": command.planet_id}
        case TransferPlanetFromCorp():
            return "TransferPlanetFromCorp", {"planet_id": command.planet_id}
        case DeclareCorpWar():
            return "DeclareCorpWar", {"target_corp_id": command.target_corp_id}
        case EndCorpWar():
            return "EndCorpWar", {"target_corp_id": command.target_corp_id}
        case AttackPlayer():
            return "AttackPlayer", {"target_player_id": command.target_player_id}
        case AttackSpecies():
            return "AttackSpecies", {"species_id": command.species_id}
        case DevPatch():
            return "DevPatch", {
                "op": command.op, "target": command.target, "value": command.value,
                "key": command.key, "ref": command.ref,
            }


def decode_command(type_: str, payload: dict[str, Any]) -> Command:
    """Reconstruct a command from its persisted (type, payload)."""
    match type_:
        case "JoinGame":
            return JoinGame(name=payload["name"])
        case "SetPlayerName":
            return SetPlayerName(name=payload["name"])
        case "Warp":
            return Warp(to_sector=payload["to_sector"])
        case "TravelTo":
            return TravelTo(to_sector=payload["to_sector"])
        case "Dock":
            return Dock()
        case "Trade":
            return Trade(
                commodity=Commodity(payload["commodity"]),
                units=payload["units"],
                unit_price=payload["unit_price"],
            )
        case "HaggleOffer":
            return HaggleOffer(
                commodity=Commodity(payload["commodity"]),
                units=payload["units"],
                counter_price=payload["counter_price"],
            )
        case "Deposit":
            return Deposit(amount=payload["amount"])
        case "Withdraw":
            return Withdraw(amount=payload["amount"])
        case "BuyComponent":
            return BuyComponent(
                component=Component(payload["component"]), tier=ComponentTier[payload["tier"]],
            )
        case "BuyShip":
            return BuyShip(ship_class_id=payload["ship_class_id"])
        case "RepairAtDock":
            return RepairAtDock(
                subsystem=Subsystem(payload["subsystem"]), slot_index=payload["slot_index"],
            )
        case "RecruitColonists":
            return RecruitColonists(
                count=payload["count"], from_planet=payload["from_planet"],
                species_id=payload.get("species_id"),
            )
        case "HireRecruits":
            return HireRecruits(count=payload["count"])
        case "DismissRecruits":
            return DismissRecruits(count=payload["count"])
        case "BuySuits":
            return BuySuits(suit_id=payload["suit_id"], count=payload["count"])
        case "SellSuits":
            return SellSuits(suit_id=payload["suit_id"], count=payload["count"])
        case "BuyGroundOrdnance":
            return BuyGroundOrdnance(count=payload["count"])
        case "Colonize":
            return Colonize(
                planet_id=payload["planet_id"], colonists=payload["colonists"],
                species_id=payload.get("species_id"),
            )
        case "SettleColonists":
            return SettleColonists(
                planet_id=payload["planet_id"], colonists=payload["colonists"],
                species_id=payload.get("species_id"),
            )
        case "BuildStagingArea":
            return BuildStagingArea(planet_id=payload["planet_id"])
        case "SetAllocation":
            return SetAllocation(planet_id=payload["planet_id"], allocation=payload["allocation"],
                                 fighter=payload.get("fighter", 0.0),
                                 garrison=payload.get("garrison", 0.0))
        case "TransferCargo":
            return TransferCargo(planet_id=payload["planet_id"],
                                 commodity=Commodity(payload["commodity"]),
                                 units=payload["units"], to_planet=payload["to_planet"])
        case "TransferFighters":
            return TransferFighters(planet_id=payload["planet_id"], count=payload["count"],
                                    to_planet=payload["to_planet"])
        case "BatchTransferCargo":
            return BatchTransferCargo(planet_id=payload["planet_id"], units=payload["units"],
                                      to_planet=payload["to_planet"])
        case "BuildCitadel":
            return BuildCitadel(planet_id=payload["planet_id"])
        case "PlanetDeposit":
            return PlanetDeposit(planet_id=payload["planet_id"], amount=payload["amount"])
        case "PlanetWithdraw":
            return PlanetWithdraw(planet_id=payload["planet_id"], amount=payload["amount"])
        case "InvadePlanet":
            return InvadePlanet(planet_id=payload["planet_id"], fighters=payload["fighters"])
        case "ReinforceGarrison":
            return ReinforceGarrison(
                planet_id=payload["planet_id"], suit_id=payload["suit_id"],
                count=payload["count"])
        case "BeginAssault":
            return BeginAssault(planet_id=payload["planet_id"])
        case "InstallComponent":
            return InstallComponent(
                subsystem=Subsystem(payload["subsystem"]), slot_index=payload["slot_index"],
                component=Component(payload["component"]), tier=ComponentTier[payload["tier"]],
            )
        case "SwapComponent":
            return SwapComponent(
                subsystem=Subsystem(payload["subsystem"]), slot_index=payload["slot_index"],
                component=Component(payload["component"]), tier=ComponentTier[payload["tier"]],
            )
        case "Cannibalize":
            return Cannibalize(
                subsystem=Subsystem(payload["subsystem"]), slot_index=payload["slot_index"],
                starbase_id=payload.get("starbase_id"),
            )
        case "FieldPatch":
            return FieldPatch(
                subsystem=Subsystem(payload["subsystem"]), slot_index=payload["slot_index"],
            )
        case "CombatAction":
            sub = payload.get("subsystem")
            return CombatAction(
                action=payload["action"],
                subsystem=Subsystem(sub) if sub is not None else None,
                slot_index=payload.get("slot_index"),
            )
        case "BuyMissiles":
            return BuyMissiles(count=payload["count"])
        case "Salvage":
            return Salvage(discovery_id=payload["discovery_id"])
        case "Descend":
            return Descend(planet_id=payload["planet_id"])
        case "Explore":
            return Explore(planet_id=payload["planet_id"])
        case "BeginSurvey":
            return BeginSurvey(planet_id=payload["planet_id"])
        case "ExtractGroundOperation":
            return ExtractGroundOperation(operation_id=payload["operation_id"])
        case "GroundMove":
            return GroundMove(operation_id=payload["operation_id"], x=payload["x"],
                              y=payload["y"], actor_id=payload.get("actor_id", 0))
        case "SurveyDig":
            return SurveyDig(operation_id=payload["operation_id"])
        case "SurveyLand":
            return SurveyLand(operation_id=payload["operation_id"],
                              x=payload["x"], y=payload["y"])
        case "SurveyTalk":
            return SurveyTalk(operation_id=payload["operation_id"])
        case "GroundDrop":
            return GroundDrop(
                operation_id=payload["operation_id"],
                placements=tuple((p[0], p[1], p[2]) for p in payload["placements"]),
            )
        case "GroundJump":
            return GroundJump(operation_id=payload["operation_id"], actor_id=payload["actor_id"],
                              x=payload["x"], y=payload["y"])
        case "GroundFire":
            return GroundFire(operation_id=payload["operation_id"], actor_id=payload["actor_id"],
                              x=payload["x"], y=payload["y"], missile=payload["missile"])
        case "GroundBroadcast":
            return GroundBroadcast(operation_id=payload["operation_id"],
                                   actor_id=payload["actor_id"])
        case "EndGroundTurn":
            return EndGroundTurn(operation_id=payload["operation_id"])
        case "MineBelt":
            return MineBelt(planet_id=payload["planet_id"])
        case "BuyGenesis":
            return BuyGenesis()
        case "DeployGenesis":
            return DeployGenesis(planet_id=payload["planet_id"])
        case "Hail":
            return Hail(species_id=payload["species_id"])
        case "Converse":
            return Converse(species_id=payload["species_id"], context=payload["context"],
                            subject_id=payload.get("subject_id"),
                            choice_index=payload.get("choice_index"))
        case "BuyAlienTech":
            return BuyAlienTech(species_id=payload["species_id"], offer_index=payload["offer_index"])
        case "BarterArtifact":
            return BarterArtifact(species_id=payload["species_id"], offer_index=payload["offer_index"])
        case "AcceptLead":
            return AcceptLead(species_id=payload["species_id"])
        case "DeliverContract":
            return DeliverContract(contract_id=payload["contract_id"])
        case "AbandonContract":
            return AbandonContract(contract_id=payload["contract_id"])
        case "BuyRumor":
            return BuyRumor()
        case "PostNotice":
            return PostNotice(text=payload["text"])
        case "AddNote":
            return AddNote(text=payload["text"])
        case "RemoveNote":
            return RemoveNote(index=payload["index"])
        case "ToggleAvoid":
            return ToggleAvoid(sector_id=payload["sector_id"])
        case "AdvanceAdmission":
            return AdvanceAdmission(alliance_id=payload["alliance_id"], task=payload["task"])
        case "JoinAlliance":
            return JoinAlliance(alliance_id=payload["alliance_id"])
        case "ResignAlliance":
            return ResignAlliance()
        case "PetitionCoreSeizure":
            return PetitionCoreSeizure(alliance_id=payload["alliance_id"])
        case "AssaultStarbase":
            return AssaultStarbase(starbase_id=payload["starbase_id"])
        case "RepairStarbase":
            return RepairStarbase(
                starbase_id=payload["starbase_id"],
                subsystem=Subsystem(payload["subsystem"]), slot_index=payload["slot_index"],
                component=Component(payload["component"]), tier=ComponentTier[payload["tier"]],
            )
        case "ClaimStarbase":
            return ClaimStarbase(starbase_id=payload["starbase_id"])
        case "BuyFighters":
            return BuyFighters(count=payload["count"])
        case "BuyMines":
            return BuyMines(count=payload["count"])
        case "DeployFighters":
            return DeployFighters(count=payload["count"], mode=payload["mode"], toll=payload["toll"])
        case "DeployMines":
            return DeployMines(count=payload["count"], kind=payload.get("kind", "armid"))
        case "DeployBeacon":
            return DeployBeacon(text=payload["text"])
        case "BuyDevice":
            return BuyDevice(device_id=payload["device_id"])
        case "LaunchProbe":
            return LaunchProbe(dest_sector=payload["dest_sector"])
        case "ToggleInterdictor":
            return ToggleInterdictor()
        case "RemoveLimpets":
            return RemoveLimpets()
        case "FormCorp":
            return FormCorp(name=payload["name"], tag=payload["tag"])
        case "InviteToCorp":
            return InviteToCorp(invitee_player_id=payload["invitee_player_id"])
        case "AcceptCorpInvite":
            return AcceptCorpInvite(corp_id=payload["corp_id"])
        case "LeaveCorp":
            return LeaveCorp()
        case "ExpelFromCorp":
            return ExpelFromCorp(member_player_id=payload["member_player_id"])
        case "CorpDeposit":
            return CorpDeposit(amount=payload["amount"])
        case "CorpWithdraw":
            return CorpWithdraw(amount=payload["amount"])
        case "TransferPlanetToCorp":
            return TransferPlanetToCorp(planet_id=payload["planet_id"])
        case "TransferPlanetFromCorp":
            return TransferPlanetFromCorp(planet_id=payload["planet_id"])
        case "DeclareCorpWar":
            return DeclareCorpWar(target_corp_id=payload["target_corp_id"])
        case "EndCorpWar":
            return EndCorpWar(target_corp_id=payload["target_corp_id"])
        case "AttackPlayer":
            return AttackPlayer(target_player_id=payload["target_player_id"])
        case "AttackSpecies":
            return AttackSpecies(species_id=payload["species_id"])
        case "DevPatch":
            return DevPatch(
                op=payload["op"], target=payload["target"], value=payload["value"],
                key=payload.get("key"), ref=payload.get("ref"),
            )
        case _:
            raise ValueError(f"unknown command type {type_!r}")


def encode_event(event: Event) -> tuple[str, dict[str, Any]]:
    """A (type tag, JSON-able payload) pair for an event (persistence only)."""
    match event:
        case Warped():
            return "Warped", {
                "player_id": event.player_id, "from_sector": event.from_sector,
                "to_sector": event.to_sector, "turn_cost": event.turn_cost,
                "one_way": event.one_way,
            }
        case Docked():
            return "Docked", {
                "player_id": event.player_id, "sector_id": event.sector_id, "port_id": event.port_id,
            }
        case Traded():
            return "Traded", {
                "player_id": event.player_id, "port_id": event.port_id,
                "commodity": event.commodity.value, "mode": event.mode.value,
                "units": event.units, "unit_price": event.unit_price, "total": event.total,
                "requested": event.requested,
            }
        case MarketSettled():
            return "MarketSettled", {
                "matches": event.matches, "volume": event.volume, "slips": event.slips,
            }
        case PortOrderFilled():
            return "PortOrderFilled", {
                "port_id": event.port_id, "commodity": event.commodity.value,
                "side": event.side, "qty": event.qty, "unit_price": event.unit_price,
                "counterparty_port_id": event.counterparty_port_id,
            }
        case Haggled():
            return "Haggled", {
                "player_id": event.player_id, "port_id": event.port_id,
                "commodity": event.commodity.value, "status": event.status, "price": event.price,
            }
        case BaseCommission():
            return "BaseCommission", {
                "player_id": event.player_id, "starbase_id": event.starbase_id,
                "port_id": event.port_id, "owner_kind": event.owner_kind,
                "owner_ref": event.owner_ref, "amount": event.amount,
            }
        case Banked():
            return "Banked", {
                "player_id": event.player_id, "kind": event.kind,
                "amount": event.amount, "balance": event.balance,
            }
        case ComponentPurchased():
            return "ComponentPurchased", {
                "player_id": event.player_id, "component": event.component,
                "tier": event.tier, "cost": event.cost,
            }
        case ShipPurchased():
            return "ShipPurchased", {
                "player_id": event.player_id, "ship_class_id": event.ship_class_id,
                "cost": event.cost, "trade_in": event.trade_in,
            }
        case ComponentInstalled():
            return "ComponentInstalled", {
                "player_id": event.player_id, "subsystem": event.subsystem,
                "slot_index": event.slot_index, "component": event.component, "tier": event.tier,
            }
        case ComponentRemoved():
            return "ComponentRemoved", {
                "player_id": event.player_id, "subsystem": event.subsystem,
                "slot_index": event.slot_index, "component": event.component, "tier": event.tier,
            }
        case Repaired():
            return "Repaired", {
                "player_id": event.player_id, "subsystem": event.subsystem, "slot_index": event.slot_index,
            }
        case StarbaseSalvaged():
            return "StarbaseSalvaged", {
                "player_id": event.player_id, "starbase_id": event.starbase_id,
                "subsystem": event.subsystem, "slot_index": event.slot_index,
                "component": event.component, "tier": event.tier,
            }
        case DevicePurchased():
            return "DevicePurchased", {
                "player_id": event.player_id, "device_id": event.device_id, "cost": event.cost,
            }
        case GenesisDeployed():
            return "GenesisDeployed", {
                "player_id": event.player_id, "planet_id": event.planet_id, "new_type": event.new_type,
            }
        case Descended():
            return "Descended", {"player_id": event.player_id, "planet_id": event.planet_id}
        case GroundOperationBegan():
            return "GroundOperationBegan", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "kind": event.kind, "planet_id": event.planet_id,
            }
        case GroundOperationEnded():
            return "GroundOperationEnded", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "kind": event.kind, "outcome": event.outcome,
            }
        case GroundMoved():
            return "GroundMoved", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "x": event.x, "y": event.y, "main_turns": event.main_turns,
            }
        case SurveyDug():
            return "SurveyDug", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "x": event.x, "y": event.y, "discovery_id": event.discovery_id,
            }
        case SurveySiteExcavated():
            return "SurveySiteExcavated", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "discovery_id": event.discovery_id, "kind": event.kind, "rarity": event.rarity,
            }
        case SurveyLanded():
            return "SurveyLanded", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "x": event.x, "y": event.y,
            }
        case SurveyTalked():
            return "SurveyTalked", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "settlement_id": event.settlement_id, "hinted_id": event.hinted_id,
            }
        case GroundAssaultDropped():
            return "GroundAssaultDropped", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "trooper_count": event.trooper_count,
                "casualties_on_drop": event.casualties_on_drop,
            }
        case GroundJumped():
            return "GroundJumped", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "actor_id": event.actor_id, "x": event.x, "y": event.y, "hit": event.hit,
            }
        case GroundFired():
            return "GroundFired", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "actor_id": event.actor_id, "x": event.x, "y": event.y,
                "missile": event.missile, "hit": event.hit,
                "target_kind": event.target_kind, "destroyed": event.destroyed,
            }
        case GroundBroadcastMade():
            return "GroundBroadcastMade", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "actor_id": event.actor_id, "city_id": event.city_id,
            }
        case GroundTurnEnded():
            return "GroundTurnEnded", {
                "player_id": event.player_id, "operation_id": event.operation_id,
                "turn": event.turn, "resolve": event.resolve,
                "main_turns": event.main_turns, "outcome": event.outcome,
            }
        case CloudCityBuilt():
            return "CloudCityBuilt", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "size": event.size, "cost": event.cost,
            }
        case BeltMined():
            return "BeltMined", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "commodity": event.commodity, "amount": event.amount,
            }
        case SiteExplored():
            return "SiteExplored", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "discovery_id": event.discovery_id, "kind": event.kind, "rarity": event.rarity,
            }
        case DiscoveryDetected():
            return "DiscoveryDetected", {
                "player_id": event.player_id, "discovery_id": event.discovery_id,
                "kind": event.kind, "rarity": event.rarity,
            }
        case DiscoveryCollected():
            return "DiscoveryCollected", {
                "player_id": event.player_id, "discovery_id": event.discovery_id,
                "kind": event.kind, "rarity": event.rarity, "payload": event.payload,
                "reward": event.reward,
            }
        case RecruitsHired():
            return "RecruitsHired", {
                "player_id": event.player_id, "count": event.count, "cost": event.cost,
            }
        case RecruitsDismissed():
            return "RecruitsDismissed", {
                "player_id": event.player_id, "count": event.count, "severance": event.severance,
            }
        case SuitsPurchased():
            return "SuitsPurchased", {
                "player_id": event.player_id, "suit_id": event.suit_id,
                "count": event.count, "cost": event.cost,
            }
        case SuitsSold():
            return "SuitsSold", {
                "player_id": event.player_id, "suit_id": event.suit_id,
                "count": event.count, "refund": event.refund,
                "missiles_spilled": event.missiles_spilled,
            }
        case GroundOrdnanceBought():
            return "GroundOrdnanceBought", {
                "player_id": event.player_id, "count": event.count, "cost": event.cost,
            }
        case ColonistsRecruited():
            return "ColonistsRecruited", {
                "player_id": event.player_id, "source": event.source,
                "count": event.count, "cost": event.cost,
            }
        case Colonized():
            return "Colonized", {
                "player_id": event.player_id, "planet_id": event.planet_id, "colonists": event.colonists,
            }
        case ColonistsSettled():
            return "ColonistsSettled", {
                "player_id": event.player_id, "planet_id": event.planet_id, "colonists": event.colonists,
            }
        case PlanetProduced():
            return "PlanetProduced", {"planet_id": event.planet_id, "owner_player_id": event.owner_player_id}
        case ColonyGrew():
            return "ColonyGrew", {"planet_id": event.planet_id, "colonists": event.colonists}
        case CargoTransferred():
            return "CargoTransferred", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "commodity": event.commodity.value, "units": event.units,
                "to_planet": event.to_planet,
            }
        case FightersTransferred():
            return "FightersTransferred", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "count": event.count, "to_planet": event.to_planet,
            }
        case GarrisonReinforced():
            return "GarrisonReinforced", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "suit_id": event.suit_id, "count": event.count,
            }
        case CitadelBuildStarted():
            return "CitadelBuildStarted", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "target_level": event.target_level,
            }
        case CitadelCompleted():
            return "CitadelCompleted", {"planet_id": event.planet_id, "level": event.level}
        case CitadelGunSilenced():
            return "CitadelGunSilenced", {"player_id": event.player_id, "planet_id": event.planet_id}
        case ProbeReport():
            return "ProbeReport", {
                "player_id": event.player_id, "dest_sector": event.dest_sector,
                "sectors_charted": event.sectors_charted, "ports": event.ports,
                "planets": event.planets, "contacts": event.contacts, "destroyed": event.destroyed,
            }
        case InterdictorToggled():
            return "InterdictorToggled", {"player_id": event.player_id, "active": event.active}
        case LimpetsRemoved():
            return "LimpetsRemoved", {
                "player_id": event.player_id, "count": event.count, "fee": event.fee,
            }
        case PlanetInvaded():
            return "PlanetInvaded", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "fighters_lost": event.fighters_lost, "colonists": event.colonists,
                "loot": event.loot,
            }
        case InvasionRepulsed():
            return "InvasionRepulsed", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "fighters_lost": event.fighters_lost,
            }
        case PlanetBanked():
            return "PlanetBanked", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "kind": event.kind, "amount": event.amount, "balance": event.balance,
            }
        case ContractAccepted():
            return "ContractAccepted", {
                "player_id": event.player_id, "contract_id": event.contract_id,
                "kind": event.kind, "issuer": event.issuer, "reward": event.reward,
                "deadline_day": event.deadline_day,
            }
        case ContractCompleted():
            return "ContractCompleted", {
                "player_id": event.player_id, "contract_id": event.contract_id,
                "kind": event.kind, "reward": event.reward,
            }
        case ContractFailed():
            return "ContractFailed", {
                "player_id": event.player_id, "contract_id": event.contract_id,
                "kind": event.kind, "reason": event.reason,
            }
        case RumorHeard():
            return "RumorHeard", {
                "player_id": event.player_id, "kind": event.kind, "ref": event.ref,
                "sector_id": event.sector_id, "price": event.price,
            }
        case NoticePosted():
            return "NoticePosted", {"player_id": event.player_id, "day": event.day}
        case CorpFormed():
            return "CorpFormed", {
                "player_id": event.player_id, "corp_id": event.corp_id,
                "name": event.name, "tag": event.tag, "fee": event.fee,
            }
        case CorpInvited():
            return "CorpInvited", {
                "player_id": event.player_id, "corp_id": event.corp_id,
                "invitee_player_id": event.invitee_player_id,
            }
        case CorpJoined():
            return "CorpJoined", {"player_id": event.player_id, "corp_id": event.corp_id}
        case CorpDeparted():
            return "CorpDeparted", {
                "player_id": event.player_id, "corp_id": event.corp_id, "reason": event.reason,
            }
        case CorpBanked():
            return "CorpBanked", {
                "player_id": event.player_id, "corp_id": event.corp_id,
                "kind": event.kind, "amount": event.amount, "balance": event.balance,
            }
        case PlanetTransferred():
            return "PlanetTransferred", {
                "player_id": event.player_id, "planet_id": event.planet_id,
                "corp_id": event.corp_id, "to_corp": event.to_corp,
            }
        case CorpWarDeclared():
            return "CorpWarDeclared", {
                "player_id": event.player_id, "corp_id": event.corp_id,
                "target_corp_id": event.target_corp_id,
            }
        case CorpWarEnded():
            return "CorpWarEnded", {
                "player_id": event.player_id, "corp_id": event.corp_id,
                "target_corp_id": event.target_corp_id,
            }
        case PlayerAttacked():
            return "PlayerAttacked", {
                "player_id": event.player_id, "target_player_id": event.target_player_id,
                "sector_id": event.sector_id,
            }
        case BountyPosted():
            return "BountyPosted", {
                "player_id": event.player_id, "amount": event.amount, "total": event.total,
            }
        case TurnsReset():
            return "TurnsReset", {"player_id": event.player_id, "turns": event.turns}
        case StockRegenerated():
            return "StockRegenerated", {
                "port_id": event.port_id, "commodity": event.commodity.value, "new_stock": event.new_stock,
            }
        case AlienHailed():
            return "AlienHailed", {"player_id": event.player_id, "species_id": event.species_id}
        case AlienMoved():
            return "AlienMoved", {
                "species_id": event.species_id,
                "from_sector": event.from_sector, "to_sector": event.to_sector,
            }
        case AlienDestroyed():
            return "AlienDestroyed", {
                "species_id": event.species_id,
                "sector_id": event.sector_id, "cause": event.cause,
            }
        case AlienSpoke():
            return "AlienSpoke", {
                "player_id": event.player_id, "species_id": event.species_id,
                "context": event.context, "subject_id": event.subject_id,
            }
        case AlienTraded():
            return "AlienTraded", {
                "player_id": event.player_id, "species_id": event.species_id,
                "kind": event.kind, "detail": event.detail, "cost": event.cost,
            }
        case AttitudeChanged():
            return "AttitudeChanged", {
                "player_id": event.player_id, "species_id": event.species_id,
                "offset": event.offset, "effective": event.effective,
            }
        case LeadAccepted():
            return "LeadAccepted", {
                "player_id": event.player_id, "species_id": event.species_id,
                "kind": event.kind, "ref": event.ref, "sector_id": event.sector_id,
            }
        case EncounterStarted():
            return "EncounterStarted", {
                "player_id": event.player_id, "species_id": event.species_id,
                "sector_id": event.sector_id, "hostile": event.hostile,
                "pack_size": event.pack_size, "band": event.band,
            }
        case EncounterEvaded():
            return "EncounterEvaded", {
                "player_id": event.player_id, "species_id": event.species_id,
                "sector_id": event.sector_id,
            }
        case CombatRound():
            return "CombatRound", {
                "player_id": event.player_id, "species_id": event.species_id,
                "round": event.round, "action": event.action,
                "damage_dealt": event.damage_dealt, "damage_taken": event.damage_taken,
                "foes_left": event.foes_left,
            }
        case EncounterEnded():
            return "EncounterEnded", {
                "player_id": event.player_id, "species_id": event.species_id,
                "outcome": event.outcome,
                "destroyed": event.destroyed, "fled": event.fled, "foe_name": event.foe_name,
            }
        case ComponentKnockedOut():
            return "ComponentKnockedOut", {
                "player_id": event.player_id, "subsystem": event.subsystem,
                "slot_index": event.slot_index, "component": event.component,
            }
        case ShipDestroyed():
            return "ShipDestroyed", {
                "player_id": event.player_id, "species_id": event.species_id,
                "sector_id": event.sector_id, "lost_ship": event.lost_ship,
            }
        case SalvageCollected():
            return "SalvageCollected", {
                "player_id": event.player_id, "latinum": event.latinum,
                "components": list(event.components),
            }
        case GrudgeFormed():
            return "GrudgeFormed", {
                "player_id": event.player_id, "species_kind": event.species_kind,
                "severity": event.severity, "permanent": event.permanent,
            }
        case CoreLawNotice():
            return "CoreLawNotice", {
                "player_id": event.player_id, "sector_id": event.sector_id,
            }
        case GovernanceChanged():
            return "GovernanceChanged", {
                "old_alliance_id": event.old_alliance_id,
                "new_alliance_id": event.new_alliance_id, "cause": event.cause,
            }
        case AllianceLeadershipChanged():
            return "AllianceLeadershipChanged", {
                "alliance_id": event.alliance_id,
                "old_leader_roster": event.old_leader_roster,
                "new_leader_roster": event.new_leader_roster,
            }
        case AdmissionAdvanced():
            return "AdmissionAdvanced", {
                "player_id": event.player_id, "alliance_id": event.alliance_id, "task": event.task,
            }
        case AllianceJoined():
            return "AllianceJoined", {
                "player_id": event.player_id, "alliance_id": event.alliance_id,
                "former_alliance_id": event.former_alliance_id,
            }
        case AllianceResigned():
            return "AllianceResigned", {
                "player_id": event.player_id, "former_alliance_id": event.former_alliance_id,
            }
        case StarbaseRazed():
            return "StarbaseRazed", {
                "player_id": event.player_id, "starbase_id": event.starbase_id,
                "planet_id": event.planet_id, "sector_id": event.sector_id,
                "former_owner_kind": event.former_owner_kind,
                "former_owner_ref": event.former_owner_ref, "bounty": event.bounty,
            }
        case StarbaseRepaired():
            return "StarbaseRepaired", {
                "player_id": event.player_id, "starbase_id": event.starbase_id,
                "subsystem": event.subsystem, "slot_index": event.slot_index,
                "component": event.component, "tier": event.tier,
            }
        case StarbaseClaimed():
            return "StarbaseClaimed", {
                "player_id": event.player_id, "starbase_id": event.starbase_id,
                "cost": event.cost,
            }
        case TerritoryDeployed():
            return "TerritoryDeployed", {
                "player_id": event.player_id, "sector_id": event.sector_id,
                "kind": event.kind, "count": event.count, "mode": event.mode,
            }
        case HazardDamage():
            return "HazardDamage", {
                "player_id": event.player_id, "sector_id": event.sector_id,
                "source": event.source, "damage": event.damage,
            }
        case DevApplied():
            return "DevApplied", {"player_id": event.player_id, "detail": event.detail}
        case _:
            raise ValueError(f"unknown event type {type(event).__name__}")


def decode_event(type_: str, payload: dict[str, Any]) -> Event:
    """Reconstruct an event from its persisted (type, payload) — for log views (§11)."""
    match type_:
        case "Warped":
            return Warped(payload["player_id"], payload["from_sector"],
                          payload["to_sector"], payload["turn_cost"],
                          payload.get("one_way", False))
        case "Docked":
            return Docked(payload["player_id"], payload["sector_id"], payload["port_id"])
        case "Traded":
            return Traded(payload["player_id"], payload["port_id"], Commodity(payload["commodity"]),
                          PortMode(payload["mode"]), payload["units"], payload["unit_price"],
                          payload["total"], payload.get("requested", payload["units"]))
        case "MarketSettled":
            return MarketSettled(payload["matches"], payload["volume"], payload["slips"])
        case "PortOrderFilled":
            return PortOrderFilled(payload["port_id"], Commodity(payload["commodity"]),
                                   payload["side"], payload["qty"], payload["unit_price"],
                                   payload["counterparty_port_id"])
        case "Haggled":
            return Haggled(payload["player_id"], payload["port_id"], Commodity(payload["commodity"]),
                           payload["status"], payload["price"])
        case "BaseCommission":
            return BaseCommission(payload["player_id"], payload["starbase_id"], payload["port_id"],
                                  payload["owner_kind"], payload["owner_ref"], payload["amount"])
        case "Banked":
            return Banked(payload["player_id"], payload["kind"], payload["amount"], payload["balance"])
        case "ComponentPurchased":
            return ComponentPurchased(payload["player_id"], payload["component"],
                                      payload["tier"], payload["cost"])
        case "ShipPurchased":
            return ShipPurchased(payload["player_id"], payload["ship_class_id"],
                                 payload["cost"], payload["trade_in"])
        case "ComponentInstalled":
            return ComponentInstalled(payload["player_id"], payload["subsystem"],
                                      payload["slot_index"], payload["component"], payload["tier"])
        case "ComponentRemoved":
            return ComponentRemoved(payload["player_id"], payload["subsystem"],
                                    payload["slot_index"], payload["component"], payload["tier"])
        case "Repaired":
            return Repaired(payload["player_id"], payload["subsystem"], payload["slot_index"])
        case "StarbaseSalvaged":
            return StarbaseSalvaged(payload["player_id"], payload["starbase_id"], payload["subsystem"],
                                    payload["slot_index"], payload["component"], payload["tier"])
        case "DevicePurchased":
            return DevicePurchased(payload["player_id"], payload["device_id"], payload["cost"])
        case "GenesisDeployed":
            return GenesisDeployed(payload["player_id"], payload["planet_id"], payload["new_type"])
        case "Descended":
            return Descended(payload["player_id"], payload["planet_id"])
        case "GroundOperationBegan":
            return GroundOperationBegan(payload["player_id"], payload["operation_id"],
                                        payload["kind"], payload["planet_id"])
        case "GroundOperationEnded":
            return GroundOperationEnded(payload["player_id"], payload["operation_id"],
                                        payload["kind"], payload["outcome"])
        case "GroundMoved":
            return GroundMoved(payload["player_id"], payload["operation_id"],
                               payload["x"], payload["y"], payload["main_turns"])
        case "SurveyDug":
            return SurveyDug(payload["player_id"], payload["operation_id"],
                             payload["x"], payload["y"], payload["discovery_id"])
        case "SurveySiteExcavated":
            return SurveySiteExcavated(payload["player_id"], payload["operation_id"],
                                       payload["discovery_id"], payload["kind"], payload["rarity"])
        case "SurveyLanded":
            return SurveyLanded(payload["player_id"], payload["operation_id"],
                                payload["x"], payload["y"])
        case "SurveyTalked":
            return SurveyTalked(payload["player_id"], payload["operation_id"],
                                payload["settlement_id"], payload["hinted_id"])
        case "GroundAssaultDropped":
            return GroundAssaultDropped(payload["player_id"], payload["operation_id"],
                                        payload["trooper_count"], payload["casualties_on_drop"])
        case "GroundJumped":
            return GroundJumped(payload["player_id"], payload["operation_id"],
                                payload["actor_id"], payload["x"], payload["y"], payload["hit"])
        case "GroundFired":
            return GroundFired(payload["player_id"], payload["operation_id"], payload["actor_id"],
                               payload["x"], payload["y"], payload["missile"], payload["hit"],
                               payload["target_kind"], payload["destroyed"])
        case "GroundBroadcastMade":
            return GroundBroadcastMade(payload["player_id"], payload["operation_id"],
                                       payload["actor_id"], payload["city_id"])
        case "GroundTurnEnded":
            return GroundTurnEnded(payload["player_id"], payload["operation_id"], payload["turn"],
                                   payload["resolve"], payload["main_turns"], payload["outcome"])
        case "BeltMined":
            return BeltMined(payload["player_id"], payload["planet_id"],
                             payload["commodity"], payload["amount"])
        case "CloudCityBuilt":
            return CloudCityBuilt(payload["player_id"], payload["planet_id"],
                                  payload["size"], payload["cost"])
        case "SiteExplored":
            return SiteExplored(payload["player_id"], payload["planet_id"], payload["discovery_id"],
                                payload["kind"], payload["rarity"])
        case "DiscoveryDetected":
            return DiscoveryDetected(payload["player_id"], payload["discovery_id"],
                                     payload["kind"], payload["rarity"])
        case "DiscoveryCollected":
            return DiscoveryCollected(payload["player_id"], payload["discovery_id"],
                                      payload["kind"], payload["rarity"], payload["payload"],
                                      payload.get("reward", ""))
        case "RecruitsHired":
            return RecruitsHired(payload["player_id"], payload["count"], payload["cost"])
        case "RecruitsDismissed":
            return RecruitsDismissed(payload["player_id"], payload["count"], payload["severance"])
        case "SuitsPurchased":
            return SuitsPurchased(payload["player_id"], payload["suit_id"],
                                  payload["count"], payload["cost"])
        case "SuitsSold":
            return SuitsSold(payload["player_id"], payload["suit_id"], payload["count"],
                             payload["refund"], payload["missiles_spilled"])
        case "GroundOrdnanceBought":
            return GroundOrdnanceBought(payload["player_id"], payload["count"], payload["cost"])
        case "ColonistsRecruited":
            return ColonistsRecruited(payload["player_id"], payload["source"],
                                      payload["count"], payload["cost"])
        case "Colonized":
            return Colonized(payload["player_id"], payload["planet_id"], payload["colonists"])
        case "ColonistsSettled":
            return ColonistsSettled(payload["player_id"], payload["planet_id"], payload["colonists"])
        case "PlanetProduced":
            return PlanetProduced(payload["planet_id"], payload["owner_player_id"])
        case "ColonyGrew":
            return ColonyGrew(payload["planet_id"], payload["colonists"])
        case "CargoTransferred":
            return CargoTransferred(payload["player_id"], payload["planet_id"],
                                    Commodity(payload["commodity"]), payload["units"],
                                    payload["to_planet"])
        case "FightersTransferred":
            return FightersTransferred(payload["player_id"], payload["planet_id"],
                                       payload["count"], payload["to_planet"])
        case "GarrisonReinforced":
            return GarrisonReinforced(payload["player_id"], payload["planet_id"],
                                      payload["suit_id"], payload["count"])
        case "CitadelBuildStarted":
            return CitadelBuildStarted(payload["player_id"], payload["planet_id"],
                                       payload["target_level"])
        case "CitadelCompleted":
            return CitadelCompleted(payload["planet_id"], payload["level"])
        case "CitadelGunSilenced":
            return CitadelGunSilenced(payload["player_id"], payload["planet_id"])
        case "ProbeReport":
            return ProbeReport(payload["player_id"], payload["dest_sector"],
                               payload["sectors_charted"], payload["ports"],
                               payload["planets"], payload["contacts"], payload["destroyed"])
        case "InterdictorToggled":
            return InterdictorToggled(payload["player_id"], payload["active"])
        case "LimpetsRemoved":
            return LimpetsRemoved(payload["player_id"], payload["count"], payload["fee"])
        case "PlanetInvaded":
            return PlanetInvaded(payload["player_id"], payload["planet_id"],
                                 payload["fighters_lost"], payload["colonists"], payload["loot"])
        case "InvasionRepulsed":
            return InvasionRepulsed(payload["player_id"], payload["planet_id"],
                                    payload["fighters_lost"])
        case "PlanetBanked":
            return PlanetBanked(payload["player_id"], payload["planet_id"], payload["kind"],
                                payload["amount"], payload["balance"])
        case "ContractAccepted":
            return ContractAccepted(payload["player_id"], payload["contract_id"], payload["kind"],
                                    payload["issuer"], payload["reward"], payload["deadline_day"])
        case "ContractCompleted":
            return ContractCompleted(payload["player_id"], payload["contract_id"],
                                     payload["kind"], payload["reward"])
        case "ContractFailed":
            return ContractFailed(payload["player_id"], payload["contract_id"],
                                  payload["kind"], payload["reason"])
        case "RumorHeard":
            return RumorHeard(payload["player_id"], payload["kind"], payload["ref"],
                              payload["sector_id"], payload["price"])
        case "NoticePosted":
            return NoticePosted(payload["player_id"], payload["day"])
        case "CorpFormed":
            return CorpFormed(payload["player_id"], payload["corp_id"], payload["name"],
                              payload["tag"], payload["fee"])
        case "CorpInvited":
            return CorpInvited(payload["player_id"], payload["corp_id"],
                               payload["invitee_player_id"])
        case "CorpJoined":
            return CorpJoined(payload["player_id"], payload["corp_id"])
        case "CorpDeparted":
            return CorpDeparted(payload["player_id"], payload["corp_id"], payload["reason"])
        case "CorpBanked":
            return CorpBanked(payload["player_id"], payload["corp_id"], payload["kind"],
                              payload["amount"], payload["balance"])
        case "PlanetTransferred":
            return PlanetTransferred(payload["player_id"], payload["planet_id"],
                                     payload["corp_id"], payload["to_corp"])
        case "CorpWarDeclared":
            return CorpWarDeclared(payload["player_id"], payload["corp_id"],
                                   payload["target_corp_id"])
        case "CorpWarEnded":
            return CorpWarEnded(payload["player_id"], payload["corp_id"],
                                payload["target_corp_id"])
        case "PlayerAttacked":
            return PlayerAttacked(payload["player_id"], payload["target_player_id"],
                                  payload["sector_id"])
        case "BountyPosted":
            return BountyPosted(payload["player_id"], payload["amount"], payload["total"])
        case "TurnsReset":
            return TurnsReset(payload["player_id"], payload["turns"])
        case "StockRegenerated":
            return StockRegenerated(payload["port_id"], Commodity(payload["commodity"]), payload["new_stock"])
        case "AlienHailed":
            return AlienHailed(payload["player_id"], payload["species_id"])
        case "AlienMoved":
            return AlienMoved(payload["species_id"], payload["from_sector"], payload["to_sector"])
        case "AlienDestroyed":
            return AlienDestroyed(payload["species_id"], payload["sector_id"], payload["cause"])
        case "AlienSpoke":
            return AlienSpoke(payload["player_id"], payload["species_id"],
                              payload["context"], payload.get("subject_id"))
        case "AlienTraded":
            return AlienTraded(payload["player_id"], payload["species_id"], payload["kind"],
                               payload["detail"], payload["cost"])
        case "AttitudeChanged":
            return AttitudeChanged(payload["player_id"], payload["species_id"],
                                   payload["offset"], payload["effective"])
        case "LeadAccepted":
            return LeadAccepted(payload["player_id"], payload["species_id"],
                                payload["kind"], payload["ref"], payload["sector_id"])
        case "EncounterStarted":
            return EncounterStarted(payload["player_id"], payload["species_id"],
                                    payload["sector_id"], payload["hostile"],
                                    payload["pack_size"], payload["band"])
        case "EncounterEvaded":
            return EncounterEvaded(payload["player_id"], payload["species_id"],
                                   payload["sector_id"])
        case "CombatRound":
            return CombatRound(payload["player_id"], payload["species_id"],
                               payload["round"], payload["action"],
                               payload["damage_dealt"], payload["damage_taken"],
                               payload["foes_left"])
        case "EncounterEnded":
            return EncounterEnded(payload["player_id"], payload["species_id"],
                                  payload["outcome"], payload.get("destroyed", 0),
                                  payload.get("fled", 0), payload.get("foe_name", ""))
        case "ComponentKnockedOut":
            return ComponentKnockedOut(payload["player_id"], payload["subsystem"],
                                       payload["slot_index"], payload["component"])
        case "ShipDestroyed":
            return ShipDestroyed(payload["player_id"], payload["species_id"],
                                 payload["sector_id"], payload["lost_ship"])
        case "SalvageCollected":
            return SalvageCollected(payload["player_id"], payload["latinum"],
                                    tuple(payload["components"]))
        case "GrudgeFormed":
            return GrudgeFormed(payload["player_id"], payload["species_kind"],
                                payload["severity"], payload["permanent"])
        case "CoreLawNotice":
            return CoreLawNotice(payload["player_id"], payload["sector_id"])
        case "GovernanceChanged":
            return GovernanceChanged(payload["old_alliance_id"], payload["new_alliance_id"],
                                     payload["cause"])
        case "AllianceLeadershipChanged":
            return AllianceLeadershipChanged(payload["alliance_id"], payload["old_leader_roster"],
                                             payload["new_leader_roster"])
        case "AdmissionAdvanced":
            return AdmissionAdvanced(payload["player_id"], payload["alliance_id"], payload["task"])
        case "AllianceJoined":
            return AllianceJoined(payload["player_id"], payload["alliance_id"],
                                  payload["former_alliance_id"])
        case "AllianceResigned":
            return AllianceResigned(payload["player_id"], payload["former_alliance_id"])
        case "StarbaseRazed":
            return StarbaseRazed(payload["player_id"], payload["starbase_id"],
                                 payload["planet_id"], payload["sector_id"],
                                 payload["former_owner_kind"], payload["former_owner_ref"],
                                 payload["bounty"])
        case "StarbaseRepaired":
            return StarbaseRepaired(payload["player_id"], payload["starbase_id"],
                                    payload["subsystem"], payload["slot_index"],
                                    payload["component"], payload["tier"])
        case "StarbaseClaimed":
            return StarbaseClaimed(payload["player_id"], payload["starbase_id"], payload["cost"])
        case "TerritoryDeployed":
            return TerritoryDeployed(payload["player_id"], payload["sector_id"],
                                     payload["kind"], payload["count"], payload["mode"])
        case "HazardDamage":
            return HazardDamage(payload["player_id"], payload["sector_id"],
                                payload["source"], payload["damage"])
        case "DevApplied":
            return DevApplied(payload["player_id"], payload["detail"])
        case _:
            raise ValueError(f"unknown event type {type_!r}")
