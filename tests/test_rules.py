"""WP3 — command reducers over a tiny hand-built universe (DESIGN §3)."""

from __future__ import annotations

import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.events import Banked, Docked, Traded, Upgraded, Warped
from edge.core.models import (
    Game,
    Player,
    Port,
    PortCommodity,
    Ship,
    UniverseState,
)
from edge.core.movement import MovementError
from edge.core.rules import (
    BuyUpgrade,
    Deposit,
    Dock,
    HaggleOffer,
    Trade,
    Warp,
    Withdraw,
    apply_result,
    reduce,
)

CONFIG = load_default_config()


def _universe() -> UniverseState:
    """Sectors 1<->2; a StarDock (sells all) sits in sector 2 with the player."""
    game = Game(id=1, seed=1, config_version=1, created_at="2026-06-15T00:00:00Z")
    state = UniverseState.new(game)
    from edge.core.models import Sector

    state.sectors = {
        1: Sector(id=1, region_id=1, warps_out=(2,), distance_band="Hub", is_galactic_core=True),
        2: Sector(id=2, region_id=1, warps_out=(1,), distance_band="Hub", is_galactic_core=True),
    }
    state.rebuild_adjacency()
    state.ports = {
        1: Port(
            id=1, sector_id=2, name="Sol StarDock", klass=PortClass.STARDOCK, size=1,
            commodities=(
                PortCommodity(Commodity.FUEL_ORE, PortMode.SELL, 500, 1000, 11, 5),
                PortCommodity(Commodity.ORGANICS, PortMode.SELL, 500, 1000, 5, 2),
            ),
        )
    }
    state.ships = {
        1: Ship(id=1, type_id="trailblazer", name="S.S. Wayfarer", owner_player_id=1,
                sector_id=2, holds_total=60, turns_per_warp=1, shields=80),
    }
    state.players = {
        1: Player(id=1, name="you", ship_id=1, latinum=10_000, turns_remaining=250),
    }
    return state


def _do(state: UniverseState, command: object) -> object:
    result = reduce(state, 1, command, CONFIG)  # type: ignore[arg-type]
    apply_result(state, result)
    return result


def test_warp_costs_turns_and_records_exploration() -> None:
    from dataclasses import replace

    state = _universe()
    # Move the ship to sector 1 first so we can warp back to 2.
    state.ships[1] = replace(state.ships[1], sector_id=1)
    result = _do(state, Warp(to_sector=2))
    assert isinstance(result.events[0], Warped)  # type: ignore[attr-defined]
    assert state.players[1].turns_remaining == 249
    assert state.ships[1].sector_id == 2
    assert 2 in state.players[1].explored_sectors


def test_warp_rejects_illegal_and_when_out_of_turns() -> None:
    state = _universe()
    with pytest.raises(MovementError):
        reduce(state, 1, Warp(to_sector=99), CONFIG)
    from dataclasses import replace

    state.players[1] = replace(state.players[1], turns_remaining=0)
    state.ships[1] = replace(state.ships[1], sector_id=1)
    with pytest.raises(MovementError):
        reduce(state, 1, Warp(to_sector=2), CONFIG)


def test_dock_costs_one_turn() -> None:
    state = _universe()
    _do(state, Dock())
    assert state.players[1].turns_remaining == 249
    res = reduce(state, 1, Dock(), CONFIG)
    assert isinstance(res.events[0], Docked)


def test_trade_buy_moves_goods_and_burns_latinum() -> None:
    state = _universe()
    before = state.players[1].latinum
    result = _do(state, Trade(commodity=Commodity.FUEL_ORE, units=10))
    traded = result.events[0]  # type: ignore[attr-defined]
    assert isinstance(traded, Traded)
    assert state.ships[1].cargo[Commodity.FUEL_ORE] == 10
    assert state.ports[1].commodities[0].stock == 490  # 500 - 10
    assert state.players[1].latinum == before - traded.total


def test_buy_upgrade_at_stardock_bumps_holds() -> None:
    state = _universe()
    holds0 = state.ships[1].holds_total
    result = _do(state, BuyUpgrade())
    assert isinstance(result.events[0], Upgraded)  # type: ignore[attr-defined]
    assert state.ships[1].holds_total == holds0 + CONFIG.economy.first_upgrade_amount
    assert state.players[1].latinum == 10_000 - CONFIG.economy.first_upgrade_latinum


def test_bank_deposit_then_withdraw() -> None:
    state = _universe()
    _do(state, Deposit(amount=1_000))
    assert (state.players[1].latinum, state.players[1].bank_balance) == (9_000, 1_000)
    result = _do(state, Withdraw(amount=400))
    assert isinstance(result.events[0], Banked)  # type: ignore[attr-defined]
    assert (state.players[1].latinum, state.players[1].bank_balance) == (9_400, 600)


def test_haggle_is_deterministic_from_seed() -> None:
    a = _universe()
    b = _universe()
    cmd = HaggleOffer(commodity=Commodity.FUEL_ORE, units=5, counter_price=10)
    ra = reduce(a, 1, cmd, CONFIG)
    rb = reduce(b, 1, cmd, CONFIG)
    # Same seed -> same haggle resolution (status + any resulting trade).
    assert [type(e) for e in ra.events] == [type(e) for e in rb.events]


def test_upgrade_requires_stardock() -> None:
    state = _universe()
    from dataclasses import replace

    state.ports[1] = replace(state.ports[1], klass=PortClass.CLASS_1)
    with pytest.raises(EconomyError):
        reduce(state, 1, BuyUpgrade(), CONFIG)
