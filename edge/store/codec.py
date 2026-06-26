"""(De)serialize commands and events to JSON-able payloads for the logs (§12).

Commands round-trip (encode for persistence, decode for replay); events encode
only — they are append-only facts the store never has to reconstruct into objects
for Phase-1 replay (state comes from replaying the *command* log).
"""

from __future__ import annotations

from typing import Any

from edge.core.enums import Commodity, Component, ComponentTier, PortMode, Subsystem
from edge.core.events import (
    AlienHailed,
    AlienMoved,
    AlienSpoke,
    AlienTraded,
    AttitudeChanged,
    Banked,
    Colonized,
    ColonistsRecruited,
    ColonyGrew,
    ComponentInstalled,
    ComponentPurchased,
    ComponentRemoved,
    Descended,
    DevApplied,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    Event,
    GenesisDeployed,
    Haggled,
    LeadAccepted,
    PlanetProduced,
    Repaired,
    ShipPurchased,
    SiteExplored,
    StarbaseSalvaged,
    StockRegenerated,
    Traded,
    TurnsReset,
    Warped,
)
from edge.core.dev import DevPatch
from edge.core.rules import (
    AcceptLead,
    BarterArtifact,
    BuyAlienTech,
    BuyComponent,
    BuyGenesis,
    BuyShip,
    Cannibalize,
    Colonize,
    Command,
    Converse,
    DeployGenesis,
    Deposit,
    Descend,
    Dock,
    Explore,
    FieldPatch,
    Hail,
    HaggleOffer,
    InstallComponent,
    JoinGame,
    RecruitColonists,
    RepairAtDock,
    Salvage,
    SetAllocation,
    SwapComponent,
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
            return "RecruitColonists", {"count": command.count, "from_planet": command.from_planet}
        case Colonize():
            return "Colonize", {"planet_id": command.planet_id, "colonists": command.colonists}
        case SetAllocation():
            return "SetAllocation", {"planet_id": command.planet_id, "allocation": command.allocation}
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
        case Salvage():
            return "Salvage", {"discovery_id": command.discovery_id}
        case Descend():
            return "Descend", {"planet_id": command.planet_id}
        case Explore():
            return "Explore", {"planet_id": command.planet_id}
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
            return RecruitColonists(count=payload["count"], from_planet=payload["from_planet"])
        case "Colonize":
            return Colonize(planet_id=payload["planet_id"], colonists=payload["colonists"])
        case "SetAllocation":
            return SetAllocation(planet_id=payload["planet_id"], allocation=payload["allocation"])
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
        case "Salvage":
            return Salvage(discovery_id=payload["discovery_id"])
        case "Descend":
            return Descend(planet_id=payload["planet_id"])
        case "Explore":
            return Explore(planet_id=payload["planet_id"])
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
            }
        case Haggled():
            return "Haggled", {
                "player_id": event.player_id, "port_id": event.port_id,
                "commodity": event.commodity.value, "status": event.status, "price": event.price,
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
        case ColonistsRecruited():
            return "ColonistsRecruited", {
                "player_id": event.player_id, "source": event.source,
                "count": event.count, "cost": event.cost,
            }
        case Colonized():
            return "Colonized", {
                "player_id": event.player_id, "planet_id": event.planet_id, "colonists": event.colonists,
            }
        case PlanetProduced():
            return "PlanetProduced", {"planet_id": event.planet_id, "owner_player_id": event.owner_player_id}
        case ColonyGrew():
            return "ColonyGrew", {"planet_id": event.planet_id, "colonists": event.colonists}
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
                          PortMode(payload["mode"]), payload["units"], payload["unit_price"], payload["total"])
        case "Haggled":
            return Haggled(payload["player_id"], payload["port_id"], Commodity(payload["commodity"]),
                           payload["status"], payload["price"])
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
        case "ColonistsRecruited":
            return ColonistsRecruited(payload["player_id"], payload["source"],
                                      payload["count"], payload["cost"])
        case "Colonized":
            return Colonized(payload["player_id"], payload["planet_id"], payload["colonists"])
        case "PlanetProduced":
            return PlanetProduced(payload["planet_id"], payload["owner_player_id"])
        case "ColonyGrew":
            return ColonyGrew(payload["planet_id"], payload["colonists"])
        case "TurnsReset":
            return TurnsReset(payload["player_id"], payload["turns"])
        case "StockRegenerated":
            return StockRegenerated(payload["port_id"], Commodity(payload["commodity"]), payload["new_stock"])
        case "AlienHailed":
            return AlienHailed(payload["player_id"], payload["species_id"])
        case "AlienMoved":
            return AlienMoved(payload["species_id"], payload["from_sector"], payload["to_sector"])
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
        case "DevApplied":
            return DevApplied(payload["player_id"], payload["detail"])
        case _:
            raise ValueError(f"unknown event type {type_!r}")
