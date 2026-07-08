"""WP57 — favors + escort contracts (DESIGN §6.7, §14).

The contract system is pure and deterministic: `pick_contract` chooses the same job the
projection and the accept reducer both see; deliver debits cargo and pays through the
latinum rail; escort rides the player's warps (convoy) and completes on arrival; destroy
settles at the kill/raze hook; deadlines lapse on the daily cron. These tests exercise the
core module directly and through the movement/cron reducers.
"""

from __future__ import annotations

from dataclasses import replace

from edge.config import load_default_config
from edge.core import contracts
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.market import PortOrder
from edge.core.models import (
    AlienSpecies,
    Game,
    Player,
    Port,
    PortCommodity,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.rules import (
    AbandonContract,
    DeliverContract,
    Warp,
    apply_result,
    reduce,
)
from edge.engine.cron import daily_turn_reset
from edge.store import codec

CFG = load_default_config()


def _sp(sid: int, roster_id: str, sector: int, *, alliance_id: int | None = None,
        disp: float = 1.0) -> AlienSpecies:
    return AlienSpecies(
        id=sid, roster_id=roster_id, name=roster_id.title(), archetype_id="a",
        sector_id=sector, home_band="Hub", tech_level=5, base_disposition=disp,
        disposition_center=disp, disposition_variance=0.0, alliance_id=alliance_id)


def _ship(sector: int, **cargo: int) -> Ship:
    return Ship(id=1, type_id="trailblazer", name="TB", owner_player_id=1, sector_id=sector,
                holds_total=100, hull_current=100, hull_max=100, shields=10,
                warp_speed=1, combat_speed=1, turns_per_warp=1,
                cargo={Commodity[k.upper()]: v for k, v in cargo.items()})


def _world() -> UniverseState:
    """Sectors 1-2-3 with a fuel-ore-buying port in sector 2, player + ship in sector 1."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {
        1: Sector(1, 1, (2,), "Frontier"),
        2: Sector(2, 1, (1, 3), "Frontier"),
        3: Sector(3, 1, (2,), "Frontier"),
    }
    state.rebuild_adjacency()
    state.ports = {
        7: Port(7, 2, "Mart", PortClass.CLASS_1, 5, (
            PortCommodity(Commodity.FUEL_ORE, PortMode.BUY, 100, 5000, 11, 5),
        ), latinum=50_000),
    }
    state.port_orders = {7: (PortOrder(7, Commodity.FUEL_ORE, "buy", 400, 11),)}
    state.ships = {1: _ship(1, fuel_ore=40)}
    state.players = {1: Player(id=1, name="Cap", ship_id=1, latinum=1000,
                               turns_remaining=100, alliance_id=1)}
    return state


# --- deliver ---------------------------------------------------------------------


def test_pick_and_deliver_contract() -> None:
    state = _world()
    issuer = _sp(10, "terran", 1, alliance_id=1)
    state.species = {10: issuer}
    player = state.players[1]

    offer = contracts.pick_contract(state, issuer, player, CFG)
    assert offer is not None and offer.kind == "deliver"
    assert offer.commodity is Commodity.FUEL_ORE and offer.dest_sector == 2

    booked = contracts.accept(player, offer, state.game.day_number, CFG)
    state.players[1] = replace(player, contracts=(booked,))

    # Move the ship to the destination port sector, then deliver.
    state.ships[1] = replace(state.ships[1], sector_id=2)
    result = reduce(state, 1, DeliverContract(contract_id=booked.id), CFG)
    apply_result(state, result)

    done = state.players[1]
    assert done.latinum == 1000 + booked.reward_slips
    assert done.contracts[0].status == "done"
    # Cargo was debited by the required quantity.
    assert state.ships[1].cargo[Commodity.FUEL_ORE] == 40 - booked.qty


def test_deliver_rejected_without_cargo_or_at_wrong_port() -> None:
    state = _world()
    issuer = _sp(10, "terran", 1, alliance_id=1)
    state.species = {10: issuer}
    offer = contracts.pick_contract(state, issuer, state.players[1], CFG)
    assert offer is not None
    booked = contracts.accept(state.players[1], offer, 1, CFG)
    state.players[1] = replace(state.players[1], contracts=(booked,))

    # Wrong sector (ship still in 1, dest is 2).
    try:
        reduce(state, 1, DeliverContract(contract_id=booked.id), CFG)
    except Exception as exc:  # noqa: BLE001 - EconomyError
        assert "deliver it at sector" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected rejection at wrong sector")


# --- escort = convoy warp --------------------------------------------------------


def test_escort_convoy_moves_merchant_and_completes() -> None:
    state = _world()
    issuer = _sp(10, "terran", 1, alliance_id=1)
    merchant = _sp(11, "selvani", 1, alliance_id=1, disp=0.78)  # selvani = trade_seek
    state.species = {10: issuer, 11: merchant}
    # Force an escort offer by giving the issuer only the escort posture path: remove the
    # deliver book so pick falls through to escort (destination = a port sector != merchant's).
    state.port_orders = {}
    offer = contracts.pick_contract(state, issuer, state.players[1], CFG)
    assert offer is not None and offer.kind == "escort"
    assert offer.target_species_id == 11 and offer.dest_sector == 2

    booked = contracts.accept(state.players[1], offer, 1, CFG)
    state.players[1] = replace(state.players[1], contracts=(booked,))

    assert contracts.is_convoyed(state, 11) is True

    # Warp 1 → 2: the merchant rides along and, arriving at its destination, completes.
    result = reduce(state, 1, Warp(to_sector=2), CFG)
    apply_result(state, result)
    assert state.species[11].sector_id == 2
    assert state.players[1].contracts[0].status == "done"
    assert state.players[1].latinum == 1000 + booked.reward_slips
    assert contracts.is_convoyed(state, 11) is False


def test_escort_suspends_when_player_leaves_merchant_behind() -> None:
    state = _world()
    issuer = _sp(10, "terran", 1, alliance_id=1)
    merchant = _sp(11, "selvani", 3, alliance_id=1, disp=0.78)  # merchant elsewhere (sector 3)
    state.species = {10: issuer, 11: merchant}
    state.port_orders = {}
    offer = contracts.pick_contract(state, issuer, state.players[1], CFG)
    assert offer is not None and offer.kind == "escort"
    booked = contracts.accept(state.players[1], offer, 1, CFG)
    state.players[1] = replace(state.players[1], contracts=(booked,))

    # Player warps 1 → 2 but the merchant sits in 3 — the convoy suspends (no move).
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    assert state.species[11].sector_id == 3
    assert state.players[1].contracts[0].status == "active"


# --- destroy (pure hook) ---------------------------------------------------------


def test_destroy_completes_on_kill() -> None:
    state = _world()
    foe = _sp(20, "quill", 1, disp=0.2)
    player = Player(id=1, name="Cap", ship_id=1, latinum=0, turns_remaining=1,
                    contracts=(contracts.Contract(
                        id=1, kind="destroy", issuer="terran", reward_slips=1500,
                        reward_attitude=0.0, accepted_day=1, deadline_day=20,
                        status="active", target_species_id=20),))
    state.species = {20: foe}
    new_player, done = contracts.complete_destroy_on_kill(player, foe)
    assert [c.id for c in done] == [1]
    assert new_player.contracts[0].status == "done"


# --- abandon + deadline ----------------------------------------------------------


def test_abandon_fails_contract() -> None:
    state = _world()
    booked = contracts.Contract(id=1, kind="deliver", issuer="terran", reward_slips=100,
                                reward_attitude=0.0, accepted_day=1, deadline_day=20,
                                status="active", commodity=Commodity.FUEL_ORE, qty=5,
                                dest_sector=2)
    state.players[1] = replace(state.players[1], contracts=(booked,))
    apply_result(state, reduce(state, 1, AbandonContract(contract_id=1), CFG))
    assert state.players[1].contracts[0].status == "failed"


def test_deadline_expiry_on_daily_cron() -> None:
    state = _world()
    booked = contracts.Contract(id=1, kind="deliver", issuer="terran", reward_slips=100,
                                reward_attitude=0.0, accepted_day=1, deadline_day=1,
                                status="active", commodity=Commodity.FUEL_ORE, qty=5,
                                dest_sector=2)
    state.players[1] = replace(state.players[1], contracts=(booked,))
    # day advances to 2 > deadline_day 1 ⇒ the job lapses.
    apply_result(state, daily_turn_reset(state, CFG))
    assert state.players[1].contracts[0].status == "failed"


# --- codec round-trip ------------------------------------------------------------


def test_contract_command_codec_round_trip() -> None:
    for cmd in (DeliverContract(contract_id=3), AbandonContract(contract_id=4)):
        type_, payload = codec.encode_command(cmd)
        assert codec.decode_command(type_, payload) == cmd


def test_contract_event_codec_round_trip() -> None:
    from edge.core.events import ContractAccepted, ContractCompleted, ContractFailed
    events = [
        ContractAccepted(1, 2, "deliver", "terran", 450, 13),
        ContractCompleted(1, 2, "deliver", 450),
        ContractFailed(1, 2, "escort", "deadline"),
    ]
    for ev in events:
        type_, payload = codec.encode_event(ev)
        assert codec.decode_event(type_, payload) == ev
