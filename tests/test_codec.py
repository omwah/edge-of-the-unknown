"""WP9 — command/event serialization round-trips (DESIGN §12)."""

from __future__ import annotations

import pytest

from edge.core.enums import Commodity, PortMode
from edge.core.events import (
    Banked,
    Docked,
    Event,
    Haggled,
    StockRegenerated,
    Traded,
    TurnsReset,
    Upgraded,
    Warped,
)
from edge.core.rules import (
    BuyUpgrade,
    Command,
    Deposit,
    Dock,
    HaggleOffer,
    Trade,
    Warp,
    Withdraw,
)
from edge.store import codec

COMMANDS: list[Command] = [
    Warp(to_sector=12),
    Dock(),
    Trade(commodity=Commodity.FUEL_ORE, units=10, unit_price=13),
    Trade(commodity=Commodity.ORGANICS, units=5),  # unit_price None
    HaggleOffer(commodity=Commodity.EQUIPMENT, units=4, counter_price=20),
    Deposit(amount=500),
    Withdraw(amount=250),
    BuyUpgrade(),
]

EVENTS: list[Event] = [
    Warped(1, 7, 12, 1),
    Docked(1, 12, 3),
    Traded(1, 3, Commodity.FUEL_ORE, PortMode.SELL, 10, 13, 130),
    Haggled(1, 3, Commodity.ORGANICS, "accepted", 6),
    Banked(1, "interest", 50, 10_050),
    Upgraded(1, "holds", 2_000),
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


def test_decode_unknown_command_raises() -> None:
    with pytest.raises(ValueError):
        codec.decode_command("Nonsense", {})


def test_encode_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        codec.encode_event(Event())


def test_decode_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        codec.decode_event("Nonsense", {})
