"""GW-WP08 — the ground-force economy: recruits, suits, ordnance, loadouts.

Drives the real reducers (`HireRecruits` / `DismissRecruits` / `BuySuits` / `SellSuits` /
`BuyGroundOrdnance`) against a hand-built Stardock world and checks the D3 contract:
recruits are people *hired* and suits are equipment *bought*, both on a passenger berth
of their own (never a cargo hold or a colonist berth); latinum and inventory are
conserved with no negative balances or ammunition; the magazine follows the suits that
chamber it (G8); a loadout can only deploy owned suits worn by aboard recruits; a
casualty costs the recruit *and* their suit atomically (D8); and a hull swap or an
escape pod cannot smuggle a force through a berth it no longer has.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass
from edge.core.groundwar import force
from edge.core.models import (
    Game, Player, Port, PortCommodity, Region, Sector, Ship, UniverseState,
)
from edge.core.rules import (
    BuyGroundOrdnance, BuyShip, BuySuits, DismissRecruits, HireRecruits, SellSuits,
    apply_result, reduce,
)
from edge.server import session
from edge.store import codec

CFG = load_default_config()
GW = CFG.groundwar
GF = GW.ground_force
SUIT = "scout"  # the cheapest suit — keeps the arithmetic in these tests small
SPEC = GW.suits[SUIT]


def _world(*, latinum: int = 100_000, passenger_capacity: int = 8) -> UniverseState:
    """One sector, a Stardock over it, a docked player with money."""
    st = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    st.sectors = {1: Sector(1, 1, (), "Hub")}
    st.regions = {1: Region(1, "Hub")}
    st.rebuild_adjacency()
    trades = PORT_CLASS_TRADES[PortClass.STARDOCK]
    st.ports = {1: Port(1, 1, "Dock", PortClass.STARDOCK, 1,
                        tuple(PortCommodity(c, trades[c], 500, 1000, 11, 5) for c in Commodity))}
    st.ships = {1: Ship(id=1, type_id="trailblazer", name="S", owner_player_id=1,
                        sector_id=1, holds_total=60, turns_per_warp=1,
                        passenger_capacity=passenger_capacity)}
    st.players = {1: Player(id=1, name="you", ship_id=1, latinum=latinum, turns_remaining=250)}
    return st


def _ship(st: UniverseState) -> Ship:
    return st.ships[1]


def _do(st: UniverseState, command: object) -> None:
    apply_result(st, reduce(st, 1, command, CFG))  # type: ignore[arg-type]


# --- hiring and dismissal (people, not merchandise) --------------------------


def test_hiring_pays_the_incentive_and_takes_passenger_berths() -> None:
    st = _world()
    before = st.players[1].latinum
    _do(st, HireRecruits(count=3))
    assert _ship(st).recruits == 3
    assert st.players[1].latinum == before - 3 * GF.recruit_price
    # Recruits ride *passenger* berths — cargo and colonist berths are untouched.
    assert _ship(st).holds_used == 0 and _ship(st).colonists == 0
    assert force.berths_used(_ship(st)) == 3


def test_hiring_clamps_to_free_berths_and_to_the_purse() -> None:
    st = _world(passenger_capacity=2)
    _do(st, HireRecruits(count=99))  # "hire all" moves what fits
    assert _ship(st).recruits == 2
    with pytest.raises(EconomyError):
        _do(st, HireRecruits(count=1))  # no berth left

    thin = _world(latinum=GF.recruit_price + 1)
    _do(thin, HireRecruits(count=99))  # ... and what the purse affords
    assert thin.ships[1].recruits == 1
    assert thin.players[1].latinum == 1


def test_a_suit_takes_a_berth_of_its_own() -> None:
    """A recruit and their suit are two occupants, so a hull carries half a platoon armoured."""
    st = _world(passenger_capacity=4)
    _do(st, HireRecruits(count=2))
    _do(st, BuySuits(suit_id=SUIT, count=2))
    assert force.berths_used(_ship(st)) == 4 == _ship(st).passenger_capacity
    with pytest.raises(EconomyError):
        _do(st, BuySuits(suit_id=SUIT, count=1))
    with pytest.raises(EconomyError):
        _do(st, HireRecruits(count=1))


def test_dismissal_frees_berths_and_pays_severance() -> None:
    st = _world()
    _do(st, HireRecruits(count=4))
    before = st.players[1].latinum
    _do(st, DismissRecruits(count=10))  # clamped to what is aboard
    assert _ship(st).recruits == 0
    assert st.players[1].latinum == before - 4 * GF.recruit_severance
    with pytest.raises(EconomyError):
        _do(st, DismissRecruits(count=1))


def test_services_are_stardock_only() -> None:
    st = _world()
    st.ports[1] = replace(st.ports[1], klass=PortClass.CLASS_1)
    for command in (HireRecruits(count=1), BuySuits(suit_id=SUIT, count=1),
                    BuyGroundOrdnance(count=1)):
        with pytest.raises(EconomyError):
            _do(st, command)


# --- suits and the magazine that follows them (G8) ---------------------------


def test_buying_and_selling_suits_conserves_latinum_at_the_resale_fraction() -> None:
    st = _world()
    before = st.players[1].latinum
    _do(st, BuySuits(suit_id=SUIT, count=2))
    assert st.players[1].latinum == before - 2 * SPEC.cost
    _do(st, SellSuits(suit_id=SUIT, count=2))
    assert _ship(st).suits == {}
    refund = 2 * int(SPEC.cost * GF.suit_resale_frac)
    assert st.players[1].latinum == before - 2 * SPEC.cost + refund
    assert refund < 2 * SPEC.cost  # churning armour is a sink, never a profit


def test_ordnance_is_capped_by_what_the_owned_suits_can_chamber() -> None:
    st = _world()
    with pytest.raises(EconomyError):
        _do(st, BuyGroundOrdnance(count=1))  # no suits ⇒ no magazine at all
    _do(st, BuySuits(suit_id="marauder", count=2))
    ceiling = 2 * GW.suits["marauder"].missiles
    _do(st, BuyGroundOrdnance(count=99))
    assert _ship(st).ground_missiles == ceiling == force.missile_capacity(_ship(st), CFG)
    with pytest.raises(EconomyError):
        _do(st, BuyGroundOrdnance(count=1))


def test_selling_suits_spills_the_ordnance_they_carried() -> None:
    """Ammunition follows the armour — it is never banked for a future platoon (G8)."""
    st = _world()
    _do(st, BuySuits(suit_id="marauder", count=2))
    _do(st, BuyGroundOrdnance(count=99))
    carried = _ship(st).ground_missiles
    res = reduce(st, 1, SellSuits(suit_id="marauder", count=1), CFG)
    apply_result(st, res)
    assert _ship(st).ground_missiles == carried // 2
    assert res.events[0].missiles_spilled == carried - carried // 2


# --- loadout validation (D3) -------------------------------------------------


def test_a_loadout_needs_an_owned_suit_and_an_aboard_recruit_for_every_trooper() -> None:
    st = _world()
    _do(st, HireRecruits(count=2))
    _do(st, BuySuits(suit_id=SUIT, count=3))
    ship = _ship(st)
    assert force.validate_loadout(ship, {SUIT: 2}, CFG) == {SUIT: 2}
    assert force.validate_loadout(ship, {SUIT: 1, "marauder": 0}, CFG) == {SUIT: 1}
    with pytest.raises(force.GroundForceError):
        force.validate_loadout(ship, {SUIT: 3}, CFG)  # only 2 recruits to wear them
    with pytest.raises(force.GroundForceError):
        force.validate_loadout(ship, {"marauder": 1}, CFG)  # no such suit aboard
    with pytest.raises(force.GroundForceError):
        force.validate_loadout(ship, {"no_such_suit": 1}, CFG)
    with pytest.raises(force.GroundForceError):
        force.validate_loadout(ship, {}, CFG)  # a drop needs someone in it


def test_a_loadout_cannot_exceed_the_configured_platoon_ceiling() -> None:
    st = _world(passenger_capacity=200)
    over = GW.max_troopers + 1
    _do(st, HireRecruits(count=over))
    _do(st, BuySuits(suit_id=SUIT, count=over))
    with pytest.raises(force.GroundForceError):
        force.validate_loadout(_ship(st), {SUIT: over}, CFG)


def test_a_casualty_costs_the_recruit_and_the_suit_together() -> None:
    st = _world()
    _do(st, HireRecruits(count=4))
    _do(st, BuySuits(suit_id="marauder", count=4))
    _do(st, BuyGroundOrdnance(count=99))
    ship = _ship(st)
    survivors = force.apply_casualties(ship, {"marauder": 3}, CFG)
    assert survivors.recruits == 1 and survivors.suits == {"marauder": 1}
    # The dead suits' magazines go with them, so ordnance cannot outlive its armour.
    assert survivors.ground_missiles == force.missile_capacity(survivors, CFG)
    with pytest.raises(force.GroundForceError):
        force.apply_casualties(ship, {"marauder": 9}, CFG)


# --- reinforcement: ship troopers become a planetary garrison (D15, GW-WP09) --


def test_reinforcement_removes_exact_recruits_and_suits() -> None:
    st = _world()
    _do(st, HireRecruits(count=4))
    _do(st, BuySuits(suit_id="marauder", count=4))
    _do(st, BuyGroundOrdnance(count=99))
    ship = _ship(st)
    reinforced = force.apply_reinforcement(ship, "marauder", 3, CFG)
    assert reinforced.recruits == 1 and reinforced.suits == {"marauder": 1}
    # Same "ammunition follows the armour" invariant as a casualty (G8).
    assert reinforced.ground_missiles == force.missile_capacity(reinforced, CFG)


def test_reinforcement_raises_on_recruit_or_suit_shortfall() -> None:
    st = _world()
    _do(st, HireRecruits(count=2))
    _do(st, BuySuits(suit_id="marauder", count=2))
    ship = _ship(st)
    with pytest.raises(force.GroundForceError):
        force.apply_reinforcement(ship, "marauder", 3, CFG)  # only 2 recruits/suits aboard
    with pytest.raises(force.GroundForceError):
        force.apply_reinforcement(ship, "scout", 1, CFG)  # no scout suits aboard at all
    with pytest.raises(force.GroundForceError):
        force.apply_reinforcement(ship, "marauder", 0, CFG)


# --- hulls: the force cannot ride a berth it does not have -------------------


def test_a_hull_swap_refuses_a_force_the_new_hull_cannot_berth() -> None:
    st = _world(passenger_capacity=8)
    _do(st, HireRecruits(count=4))
    _do(st, BuySuits(suit_id=SUIT, count=4))
    # scout_marauder berths 6; 8 occupants do not fit.
    with pytest.raises(EconomyError, match="passenger berths"):
        _do(st, BuyShip("scout_marauder"))
    _do(st, DismissRecruits(count=2))
    _do(st, SellSuits(suit_id=SUIT, count=2))
    _do(st, BuyShip("scout_marauder"))
    assert _ship(st).passenger_capacity == CFG.ship_class("scout_marauder").passenger_capacity
    assert _ship(st).recruits == 2 and force.suits_total(_ship(st)) == 2


# --- projection + wire -------------------------------------------------------


def test_the_barracks_catalog_offers_only_what_can_be_taken_aboard() -> None:
    st = _world(latinum=GF.recruit_price, passenger_capacity=3)
    view = session.stardock_view(st, 1, CFG)
    rows = {b.id: b for b in view.barracks}
    assert rows["recruit"].max_affordable == 1  # purse-bound, not berth-bound
    assert rows["ordnance"].max_affordable == 0  # no suits ⇒ no magazine
    assert view.ground_force is not None and view.ground_force.passenger_capacity == 3
    # An empty barracks still names every suit class, so the catalog is browsable.
    assert {r.kind for r in view.barracks} == {"recruit", "suit", "ordnance"}


def test_the_composer_projection_never_offers_an_undeployable_drop() -> None:
    st = _world()
    _do(st, HireRecruits(count=1))
    _do(st, BuySuits(suit_id=SUIT, count=3))
    gf = session.ground_force_view(st.players[1], _ship(st), CFG)
    assert gf is not None
    option = next(o for o in gf.options if o.suit_id == SUIT)
    assert option.owned == 3 and option.deployable == 1  # one recruit to wear them
    # Every projected option is a loadout the reducer would accept.
    for o in gf.options:
        if o.deployable:
            assert force.validate_loadout(_ship(st), {o.suit_id: o.deployable}, CFG)


def test_the_ship_view_reports_the_force_aboard() -> None:
    st = _world()
    _do(st, HireRecruits(count=2))
    _do(st, BuySuits(suit_id=SUIT, count=2))
    view = session.game_view(st, 1, CFG)
    assert view.ship.recruits == 2 and view.ship.suits_carried == 2
    assert view.ship.passenger_capacity == 8


@pytest.mark.parametrize("command", [
    HireRecruits(count=3), DismissRecruits(count=1), BuySuits(suit_id=SUIT, count=2),
    SellSuits(suit_id=SUIT, count=1), BuyGroundOrdnance(count=4),
])
def test_command_codecs_round_trip(command: object) -> None:
    type_, payload = codec.encode_command(command)  # type: ignore[arg-type]
    assert codec.decode_command(type_, payload) == command


# --- the Stardock barracks tab, live (GW-WP08) -------------------------------


async def test_the_barracks_tab_hires_through_the_service() -> None:
    """`M` reaches the Marines tab and `P` on a row hires through the real reducer."""
    from dataclasses import replace as _replace

    from textual.widgets import DataTable, TabbedContent

    from edge.core.movement import shortest_path
    from edge.core.rules import Warp
    from edge.tui.app import EdgeApp
    from edge.tui.saves import clear_slot
    from edge.tui.screens.stardock import StardockScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        clear_slot()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        dock = next(p for p in svc.state.ports.values() if p.klass is PortClass.STARDOCK)
        start = svc.game_view(1).sector.sector_id
        for hop in (shortest_path(svc.state.adjacency, start, dock.sector_id) or [])[1:]:
            svc.apply(1, Warp(to_sector=hop))
        svc.state.players[1] = _replace(svc.state.players[1], latinum=200_000)
        await pilot.press("p")  # dock
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, StardockScreen)

        await pilot.press("m")  # → Marines
        await pilot.pause()
        assert screen.query_one(TabbedContent).active == "barracks"
        table = screen.query_one("#barracks-table", DataTable)
        assert table.row_count == len(GW.suits) + 2  # recruits + every suit + ordnance

        before = svc.state.ships[svc.state.players[1].ship_id].recruits
        screen._buy_barracks()  # the row under the cursor is the recruit line
        await pilot.pause()
        modal = app.screen
        modal.query_one("Input").value = "3"  # type: ignore[attr-defined]
        await pilot.press("enter")
        await pilot.pause()
        assert svc.state.ships[svc.state.players[1].ship_id].recruits == before + 3
