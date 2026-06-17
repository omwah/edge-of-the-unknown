"""WP9 — command/event serialization round-trips (DESIGN §12)."""

from __future__ import annotations

import pytest

from typing import get_args

from edge.core.enums import Commodity, Component, ComponentTier, PortMode, Subsystem
from edge.core.events import (
    Banked,
    Colonized,
    ColonistsRecruited,
    ColonyGrew,
    ComponentInstalled,
    ComponentPurchased,
    ComponentRemoved,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    Event,
    Haggled,
    PlanetProduced,
    Repaired,
    ShipPurchased,
    StarbaseSalvaged,
    StockRegenerated,
    Traded,
    TurnsReset,
    Warped,
)
from edge.core.rules import (
    BuyComponent,
    BuyShip,
    Cannibalize,
    Colonize,
    Command,
    Deposit,
    Dock,
    FieldPatch,
    HaggleOffer,
    InstallComponent,
    RecruitColonists,
    RepairAtDock,
    Salvage,
    Scan,
    SetAllocation,
    SwapComponent,
    Trade,
    TravelTo,
    Warp,
    Withdraw,
)
from edge.store import codec

COMMANDS: list[Command] = [
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
    Colonize(planet_id=5, colonists=25),
    SetAllocation(planet_id=5, allocation={"fuel_ore": 0.5, "organics": 0.5}),
    InstallComponent(Subsystem.SPINDRIVE, 3, Component.TURBINE, ComponentTier.II),
    SwapComponent(Subsystem.SCREENS, 1, Component.RADIATOR, ComponentTier.III),
    Cannibalize(Subsystem.MAIN_GUN, 2),
    Cannibalize(Subsystem.FUSION_REACTOR, 0, starbase_id=4),  # WP4 starbase salvage
    FieldPatch(Subsystem.THRUSTERS, 0),
    Scan(),                       # WP5 sensor sweep
    Salvage(discovery_id=7),      # WP5 collect a discovery
]

EVENTS: list[Event] = [
    Warped(1, 7, 12, 1),
    Docked(1, 12, 3),
    Traded(1, 3, Commodity.FUEL_ORE, PortMode.SELL, 10, 13, 130),
    Haggled(1, 3, Commodity.ORGANICS, "accepted", 6),
    Banked(1, "interest", 50, 10_050),
    ComponentPurchased(1, "turbine", "II", 8_000),
    ShipPurchased(1, "scout_marauder", 20_000, 0),
    ColonistsRecruited(1, "stardock", 40, 200),
    Colonized(1, 5, 25),
    PlanetProduced(5, 1),
    ColonyGrew(5, 1_050),
    ComponentInstalled(1, "spindrive", 3, "turbine", "II"),
    ComponentRemoved(1, "main_gun", 2, "linkage", "I"),
    Repaired(1, "thrusters", 0),
    StarbaseSalvaged(1, 4, "fusion_reactor", 0, "converter", "I"),
    DiscoveryDetected(1, 7, "wreck", "RARE"),
    DiscoveryCollected(1, 7, "wreck", "RARE", "artifact"),
    TurnsReset(1, 250),
    StockRegenerated(3, Commodity.EQUIPMENT, 480),
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
