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
    TravelTo,
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


def _line_universe() -> UniverseState:
    """Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored."""
    from edge.core.models import Sector

    game = Game(id=1, seed=1, config_version=1, created_at="2026-06-15T00:00:00Z")
    state = UniverseState.new(game)
    state.sectors = {
        1: Sector(id=1, region_id=1, warps_out=(2,), distance_band="Hub"),
        2: Sector(id=2, region_id=1, warps_out=(1, 3), distance_band="Hub"),
        3: Sector(id=3, region_id=1, warps_out=(2, 4), distance_band="Frontier"),
        4: Sector(id=4, region_id=1, warps_out=(3,), distance_band="Frontier"),
    }
    state.rebuild_adjacency()
    state.ships = {
        1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                sector_id=1, holds_total=60, turns_per_warp=1),
    }
    state.players = {
        1: Player(id=1, name="you", ship_id=1, latinum=0, turns_remaining=250,
                  explored_sectors=frozenset({1})),
    }
    return state


def test_warp_records_breadcrumb() -> None:
    state = _line_universe()
    _do(state, Warp(to_sector=2))
    assert dict(state.players[1].entered_from) == {2: 1}
    _do(state, Warp(to_sector=3))
    assert state.players[1].entered_from[3] == 2  # last-entered-from per sector


def test_travel_to_multi_hop_known_route() -> None:
    state = _line_universe()
    _do(state, Warp(to_sector=2))  # uncover the route 1->2->3
    _do(state, Warp(to_sector=3))
    turns = state.players[1].turns_remaining
    result = _do(state, TravelTo(to_sector=1))  # travel back along explored sectors
    assert state.ships[1].sector_id == 1
    assert len(result.events) == 2  # two hops: 3->2, 2->1  # type: ignore[attr-defined]
    assert state.players[1].turns_remaining == turns - 2
    assert state.players[1].entered_from[1] == 2  # crumb updated on the way back


def test_travel_to_rejects_unexplored_route() -> None:
    state = _line_universe()
    _do(state, Warp(to_sector=2))  # explored {1, 2} only
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=4), CONFIG)  # route past 3/4 not uncovered


def test_travel_to_same_sector_and_out_of_turns_are_rejected() -> None:
    from dataclasses import replace

    state = _line_universe()
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=1), CONFIG)  # already in that sector
    _do(state, Warp(to_sector=2))
    state.players[1] = replace(state.players[1], turns_remaining=0)
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=1), CONFIG)  # can't afford the first hop


def test_travel_to_stops_partway_when_turns_run_out() -> None:
    from dataclasses import replace

    state = _line_universe()
    _do(state, Warp(to_sector=2))  # uncover 1->2->3
    _do(state, Warp(to_sector=3))
    state.players[1] = replace(state.players[1], turns_remaining=1)  # only one hop's worth
    result = _do(state, TravelTo(to_sector=1))  # 3->2->1 needs two
    assert state.ships[1].sector_id == 2  # halted midway
    assert len(result.events) == 1 and state.players[1].turns_remaining == 0  # type: ignore[attr-defined]


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


def test_unknown_player_rejected() -> None:
    with pytest.raises(MovementError):
        reduce(_universe(), 99, Dock(), CONFIG)


def test_unknown_upgrade_aspect_rejected() -> None:
    state = _universe()  # player is at the StarDock in sector 2
    bad = CONFIG.model_copy(
        update={"economy": CONFIG.economy.model_copy(update={"first_upgrade_aspect": "warp"})}
    )
    with pytest.raises(EconomyError):
        reduce(state, 1, BuyUpgrade(), bad)


def test_dock_and_trade_require_a_port() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], sector_id=1)  # sector 1 has no port
    with pytest.raises(MovementError):
        reduce(state, 1, Dock(), CONFIG)
    with pytest.raises(MovementError):
        reduce(state, 1, Trade(commodity=Commodity.FUEL_ORE, units=1), CONFIG)
