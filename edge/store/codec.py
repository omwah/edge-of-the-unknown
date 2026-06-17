"""(De)serialize commands and events to JSON-able payloads for the logs (§12).

Commands round-trip (encode for persistence, decode for replay); events encode
only — they are append-only facts the store never has to reconstruct into objects
for Phase-1 replay (state comes from replaying the *command* log).
"""

from __future__ import annotations

from typing import Any

from edge.core.enums import Commodity, Component, ComponentTier, PortMode, Subsystem
from edge.core.events import (
    Banked,
    ComponentInstalled,
    ComponentRemoved,
    Docked,
    Event,
    Haggled,
    Repaired,
    StockRegenerated,
    Traded,
    TurnsReset,
    Upgraded,
    Warped,
)
from edge.core.rules import (
    BuyUpgrade,
    Cannibalize,
    Command,
    Deposit,
    Dock,
    FieldPatch,
    HaggleOffer,
    InstallComponent,
    SwapComponent,
    Trade,
    TravelTo,
    Warp,
    Withdraw,
)


def encode_command(command: Command) -> tuple[str, dict[str, Any]]:
    """A (type tag, JSON-able payload) pair for a command."""
    match command:
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
        case BuyUpgrade():
            return "BuyUpgrade", {}
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
            }
        case FieldPatch():
            return "FieldPatch", {
                "subsystem": command.subsystem.value, "slot_index": command.slot_index,
            }


def decode_command(type_: str, payload: dict[str, Any]) -> Command:
    """Reconstruct a command from its persisted (type, payload)."""
    match type_:
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
        case "BuyUpgrade":
            return BuyUpgrade()
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
            )
        case "FieldPatch":
            return FieldPatch(
                subsystem=Subsystem(payload["subsystem"]), slot_index=payload["slot_index"],
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
        case Upgraded():
            return "Upgraded", {"player_id": event.player_id, "aspect": event.aspect, "cost": event.cost}
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
        case TurnsReset():
            return "TurnsReset", {"player_id": event.player_id, "turns": event.turns}
        case StockRegenerated():
            return "StockRegenerated", {
                "port_id": event.port_id, "commodity": event.commodity.value, "new_stock": event.new_stock,
            }
        case _:
            raise ValueError(f"unknown event type {type(event).__name__}")


def decode_event(type_: str, payload: dict[str, Any]) -> Event:
    """Reconstruct an event from its persisted (type, payload) — for log views (§11)."""
    match type_:
        case "Warped":
            return Warped(payload["player_id"], payload["from_sector"],
                          payload["to_sector"], payload["turn_cost"])
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
        case "Upgraded":
            return Upgraded(payload["player_id"], payload["aspect"], payload["cost"])
        case "ComponentInstalled":
            return ComponentInstalled(payload["player_id"], payload["subsystem"],
                                      payload["slot_index"], payload["component"], payload["tier"])
        case "ComponentRemoved":
            return ComponentRemoved(payload["player_id"], payload["subsystem"],
                                    payload["slot_index"], payload["component"], payload["tier"])
        case "Repaired":
            return Repaired(payload["player_id"], payload["subsystem"], payload["slot_index"])
        case "TurnsReset":
            return TurnsReset(payload["player_id"], payload["turns"])
        case "StockRegenerated":
            return StockRegenerated(payload["port_id"], Commodity(payload["commodity"]), payload["new_stock"])
        case _:
            raise ValueError(f"unknown event type {type_!r}")
