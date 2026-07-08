"""WP66 — corporations: shared bank + assets + corp war (DESIGN §4).

The core invariants: two-step consent join, CEO-gated withdrawals/war, non-negative banks,
corp assets treating every member as owner, mutual-by-declaration war hostility, dissolution
re-keying assets to the departing CEO, and the whole thing replaying from the command log.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core import corp
from edge.core.aliens import owner_hostile
from edge.core.dev import DevPatch
from edge.core.economy import EconomyError
from edge.core.models import (
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    Starbase,
    UniverseState,
)
from edge.core.rules import (
    AcceptCorpInvite,
    CorpDeposit,
    CorpWithdraw,
    DeclareCorpWar,
    EndCorpWar,
    ExpelFromCorp,
    FormCorp,
    InviteToCorp,
    LeaveCorp,
    TransferPlanetFromCorp,
    TransferPlanetToCorp,
    apply_result,
    reduce,
)
from edge.core.starbases import is_operational
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash

CFG = load_default_config()


def _world() -> UniverseState:
    """Two players (both at sector 1) each with a ship; a planet p1 owns in that sector."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t", core_governing_alliance_id=1))
    state.sectors = {1: Sector(1, 1, (), "Hub")}
    state.rebuild_adjacency()
    state.ships = {
        1: Ship(1, "trailblazer", "S.S.", 1, 1, 60),
        2: Ship(2, "trailblazer", "S.S.", 2, 1, 60),
    }
    state.players = {
        1: Player(1, "One", 1, 100_000, turns_remaining=250),
        2: Player(2, "Two", 2, 100_000, turns_remaining=250),
    }
    state.planets = {
        5: Planet(5, 1, "World", "terrestrial_warm", owner=Ownership("player", 1)),
    }
    return state


def _do(state: UniverseState, player_id: int, command: object) -> None:
    apply_result(state, reduce(state, player_id, command, CFG))


def test_form_charges_fee_and_makes_founder_ceo() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="Vanguard", tag="van"))
    c = state.corporations[1]
    assert c.tag == "VAN" and c.ceo_player_id == 1 and c.member_player_ids == frozenset({1})
    assert state.players[1].latinum == 100_000 - CFG.corp.form_fee
    assert state.players[1].corp_id == 1


def test_invite_then_accept_is_two_step_consent() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="V", tag="V"))
    # Player 2 cannot join without an invite.
    with pytest.raises(EconomyError):
        _do(state, 2, AcceptCorpInvite(corp_id=1))
    _do(state, 1, InviteToCorp(invitee_player_id=2))
    _do(state, 2, AcceptCorpInvite(corp_id=1))
    assert state.players[2].corp_id == 1
    assert state.corporations[1].member_player_ids == frozenset({1, 2})


def test_corp_bank_is_non_negative_and_ceo_gated() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="V", tag="V"))
    _do(state, 1, InviteToCorp(invitee_player_id=2))
    _do(state, 2, AcceptCorpInvite(corp_id=1))
    _do(state, 2, CorpDeposit(amount=1_000))  # any member may deposit
    assert state.corporations[1].bank_balance == 1_000
    with pytest.raises(EconomyError):  # a non-CEO member may not withdraw
        _do(state, 2, CorpWithdraw(amount=100))
    with pytest.raises(EconomyError):  # never overdraw the bank
        _do(state, 1, CorpWithdraw(amount=5_000))
    _do(state, 1, CorpWithdraw(amount=400))
    assert state.corporations[1].bank_balance == 600


def test_corp_asset_treats_every_member_as_owner() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="V", tag="V"))
    _do(state, 1, InviteToCorp(invitee_player_id=2))
    _do(state, 2, AcceptCorpInvite(corp_id=1))
    _do(state, 1, TransferPlanetToCorp(planet_id=5))
    assert state.planets[5].owner == Ownership("corp", 1)
    # both members count as owner of the corp planet
    assert corp.player_owns(state, state.planets[5].owner, 1)
    assert corp.player_owns(state, state.planets[5].owner, 2)


def test_corp_war_is_mutual_and_hostility_follows() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="A", tag="A"))
    _do(state, 2, FormCorp(name="B", tag="B"))  # corp 2, CEO = player 2
    # A corp-2 base is *not* hostile to player 1 before war...
    base = Starbase(1, 1, 5, "orbital_base", owner=Ownership("corp", 2))
    state.starbases = {1: base}
    assert not owner_hostile(state, base.owner, state.players[1])
    _do(state, 1, DeclareCorpWar(target_corp_id=2))  # A declares on B
    # ...but is once A declares (mutual-by-declaration: only one side declared).
    assert corp.corps_at_war(state, 1, 2)
    assert owner_hostile(state, base.owner, state.players[1])
    # withdrawal opens a cooldown that blocks immediate re-declaration
    _do(state, 1, EndCorpWar(target_corp_id=2))
    assert not corp.corps_at_war(state, 1, 2)
    with pytest.raises(EconomyError):
        _do(state, 1, DeclareCorpWar(target_corp_id=2))


def test_dissolution_rekeys_assets_to_the_departing_ceo() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="V", tag="V"))
    _do(state, 1, TransferPlanetToCorp(planet_id=5))
    _do(state, 1, CorpDeposit(amount=2_000))
    bank_before = 100_000 - CFG.corp.form_fee - 2_000
    _do(state, 1, LeaveCorp())  # last member out ⇒ dissolve
    assert 1 not in state.corporations
    assert state.planets[5].owner == Ownership("player", 1)  # asset stays owned, re-keyed to CEO
    assert state.players[1].latinum == bank_before + 2_000  # bank paid back out
    assert state.players[1].corp_id is None


def test_ceo_leaving_promotes_lowest_id_member() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="V", tag="V"))
    _do(state, 1, InviteToCorp(invitee_player_id=2))
    _do(state, 2, AcceptCorpInvite(corp_id=1))
    _do(state, 1, LeaveCorp())  # CEO leaves, member 2 remains
    assert state.corporations[1].ceo_player_id == 2
    assert state.corporations[1].member_player_ids == frozenset({2})


def test_expel_is_ceo_only_and_not_self() -> None:
    state = _world()
    _do(state, 1, FormCorp(name="V", tag="V"))
    _do(state, 1, InviteToCorp(invitee_player_id=2))
    _do(state, 2, AcceptCorpInvite(corp_id=1))
    with pytest.raises(EconomyError):  # a member cannot expel
        _do(state, 2, ExpelFromCorp(member_player_id=1))
    with pytest.raises(EconomyError):  # the CEO cannot expel themselves
        _do(state, 1, ExpelFromCorp(member_player_id=1))
    _do(state, 1, ExpelFromCorp(member_player_id=2))
    assert state.players[2].corp_id is None
    assert state.corporations[1].member_player_ids == frozenset({1})


def test_corp_lifecycle_replays_to_identical_hash(tmp_path: Path) -> None:
    cfg = load_default_config().model_copy(update={
        "bigbang": load_default_config().bigbang.model_copy(
            update={"sector_count": 80, "start_sector": 1})})
    svc = GameService.new_game(cfg, 7, SqliteRepository(tmp_path / "corp.db"),  # type: ignore[arg-type]
                               created_at="2026-07-07T00:00:00Z")
    svc.apply(1, DevPatch("set", "latinum", 100_000))  # afford the fee on a fresh save
    svc.apply(1, FormCorp(name="Solo", tag="SOLO"))
    svc.apply(1, CorpDeposit(amount=1_000))
    svc.apply(1, CorpWithdraw(amount=250))
    live = state_hash(svc.state)
    from edge.engine.cron import resolve_cron
    rebuilt = rebuild(cfg, 7, svc._repo.load_commands(),  # type: ignore[attr-defined]
                      created_at="2026-07-07T00:00:00Z",
                      maintenance=svc._repo.load_maintenance(),  # type: ignore[attr-defined]
                      cron_resolver=resolve_cron)
    assert state_hash(rebuilt) == live
