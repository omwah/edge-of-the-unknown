"""WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).

A PvP fight is authored entirely by the attacker's commands; the defender's ship fights back
automatically from its derived aspects and takes damage on its *real* ship. The gates (pvp
toggle, Core sanctuary, pod-bound) live in the reducer, and a lawful kill outlaws the attacker.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.events import BountyPosted, PlayerAttacked, ShipDestroyed
from edge.core.models import Ownership, SectorForce
from edge.core import territory
from edge.core.combat import CombatError
from edge.core.rules import AttackPlayer, CombatAction, apply_result, reduce
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash


def _cfg(**pvp: object) -> object:
    base = load_default_config()
    cfg = base.model_copy(update={"bigbang": base.bigbang.model_copy(
        update={"sector_count": 80, "start_sector": 1})})
    if pvp:
        cfg = cfg.model_copy(update={"pvp": cfg.pvp.model_copy(update=pvp)})
    return cfg


def _two_players(tmp_path: Path, cfg: object, *, def_hull: int = 1,
                 def_type: str = "scout_marauder", def_alignment: int = 0,
                 def_cargo: dict[Commodity, int] | None = None) -> GameService:
    """A service with player 1 (attacker) and an injected player 2 (defender) in one frontier sector."""
    svc = GameService.new_game(cfg, 3, SqliteRepository(tmp_path / "pvp.db"),  # type: ignore[arg-type]
                               created_at="2026-07-08T00:00:00Z")
    state = svc.state
    noncore = next(sid for sid, sec in sorted(state.sectors.items()) if not sec.is_galactic_core)
    p1 = state.players[1]
    s1 = state.ships[p1.ship_id]
    state.ships[s1.id] = replace(s1, sector_id=noncore)
    state.players[1] = replace(p1, explored_sectors=p1.explored_sectors | {noncore})
    s2 = replace(s1, id=900, owner_player_id=2, sector_id=noncore, type_id=def_type,
                 hull_current=def_hull, cargo=dict(def_cargo or {}))
    state.ships[900] = s2
    state.players[2] = replace(p1, id=2, name="Two", ship_id=900, active_encounter=None,
                               alignment=def_alignment, explored_sectors=frozenset({noncore}))
    return svc


def _do(state: object, pid: int, cmd: object, cfg: object) -> object:
    result = reduce(state, pid, cmd, cfg)  # type: ignore[arg-type]
    apply_result(state, result)  # type: ignore[arg-type]
    return result


def _fight_to_the_end(state: object, cfg: object, attacker: int = 1) -> list[object]:
    """Fire fight rounds until the encounter clears; return every event produced (through shields)."""
    events: list[object] = []
    for _ in range(30):
        if state.players[attacker].active_encounter is None:  # type: ignore[attr-defined]
            break
        events.extend(_do(state, attacker, CombatAction(action="fight"), cfg).events)  # type: ignore[attr-defined]
    return events


# --- gates (H18) -------------------------------------------------------------


def test_attack_rejected_when_pvp_disabled(tmp_path: Path) -> None:
    cfg = _cfg(enabled=False)
    svc = _two_players(tmp_path, cfg)
    with pytest.raises(CombatError):
        reduce(svc.state, 1, AttackPlayer(target_player_id=2), cfg)  # type: ignore[arg-type]


def test_attack_rejected_in_the_core(tmp_path: Path) -> None:
    cfg = _cfg()
    svc = _two_players(tmp_path, cfg)
    core = next(sid for sid, sec in svc.state.sectors.items() if sec.is_galactic_core)
    for pid in (1, 2):
        sh = svc.state.ships[svc.state.players[pid].ship_id]
        svc.state.ships[sh.id] = replace(sh, sector_id=core)
    with pytest.raises(CombatError):
        reduce(svc.state, 1, AttackPlayer(target_player_id=2), cfg)  # type: ignore[arg-type]


def test_attack_rejected_against_a_pod(tmp_path: Path) -> None:
    cfg = _cfg()
    svc = _two_players(tmp_path, cfg, def_type="escape_pod")
    with pytest.raises(CombatError):
        reduce(svc.state, 1, AttackPlayer(target_player_id=2), cfg)  # type: ignore[arg-type]


# --- the fight ---------------------------------------------------------------


def test_a_kill_pods_the_defender_and_salvages_to_the_victor(tmp_path: Path) -> None:
    cfg = _cfg()
    svc = _two_players(tmp_path, cfg, def_hull=1, def_cargo={Commodity.FUEL_ORE: 100})
    state = svc.state
    open_res = _do(state, 1, AttackPlayer(target_player_id=2), cfg)
    assert any(isinstance(e, PlayerAttacked) for e in open_res.events)  # type: ignore[attr-defined]
    events = _fight_to_the_end(state, cfg)
    assert any(isinstance(e, ShipDestroyed) and e.player_id == 2 for e in events)
    # defender dropped to an escape pod
    assert state.ships[900].type_id == cfg.combat.escape_pod_class  # type: ignore[attr-defined]
    # the victor salvaged some of the defender's cargo into its holds (moved, not minted)
    assert state.ships[state.players[1].ship_id].cargo.get(Commodity.FUEL_ORE, 0) > 0
    # a lawful victim (scout_marauder, price>0) outlaws the attacker: alignment down + bounty up
    assert state.players[1].alignment < 0
    assert state.players[1].bounty > 0
    assert any(isinstance(e, BountyPosted) for e in events)


def test_killing_a_criminal_posts_no_bounty(tmp_path: Path) -> None:
    cfg = _cfg()
    svc = _two_players(tmp_path, cfg, def_hull=1, def_alignment=-50)  # already an outlaw
    state = svc.state
    _do(state, 1, AttackPlayer(target_player_id=2), cfg)
    events = _fight_to_the_end(state, cfg)
    assert any(isinstance(e, ShipDestroyed) and e.player_id == 2 for e in events)
    assert not any(isinstance(e, BountyPosted) for e in events)
    assert state.players[1].bounty == 0


def test_bounty_is_claimed_when_an_outlaw_is_podded(tmp_path: Path) -> None:
    cfg = _cfg()
    svc = _two_players(tmp_path, cfg, def_hull=1, def_alignment=-50)
    state = svc.state
    state.players[2] = replace(state.players[2], bounty=7_500)  # a head price rides on the defender
    latinum_before = state.players[1].latinum
    _do(state, 1, AttackPlayer(target_player_id=2), cfg)
    _fight_to_the_end(state, cfg)
    assert state.players[1].latinum == latinum_before + 7_500  # collected on the pod-kill
    assert state.players[2].bounty == 0  # reset once podded


# --- territory vs players (interview decision 7) -----------------------------


def test_player_force_bars_a_different_player_only_when_pvp_on(tmp_path: Path) -> None:
    cfg_on, cfg_off = _cfg(), _cfg(enabled=False)
    svc = _two_players(tmp_path, cfg_on)
    force = SectorForce(sector_id=1, owner=Ownership("player", 2), fighters=10)
    p1 = svc.state.players[1]
    assert territory.force_hostile_to_player(svc.state, force, p1, pvp_enabled=True)
    assert not territory.force_hostile_to_player(svc.state, force, p1, pvp_enabled=False)
    # its own owner is never barred
    assert not territory.force_hostile_to_player(
        svc.state, force, svc.state.players[2], pvp_enabled=True)


# --- replay ------------------------------------------------------------------


def test_pvp_fight_replays_to_identical_hash(tmp_path: Path) -> None:
    cfg = _cfg()
    from edge.core.rules import JoinGame
    from edge.core.dev import DevPatch
    from edge.engine.cron import resolve_cron
    svc = GameService.new_game(cfg, 5, SqliteRepository(tmp_path / "replay.db"),  # type: ignore[arg-type]
                               created_at="2026-07-08T00:00:00Z")
    svc.apply(2, JoinGame())  # enrol a second seat through the log (§3 seam)
    noncore = next(sid for sid, sec in sorted(svc.state.sectors.items()) if not sec.is_galactic_core)
    svc.apply(1, DevPatch("teleport", "", value=noncore))
    svc.apply(2, DevPatch("teleport", "", value=noncore))
    svc.apply(1, AttackPlayer(target_player_id=2))
    for _ in range(3):
        if svc.state.players[1].active_encounter is None:
            break
        svc.apply(1, CombatAction(action="fight"))
    live = state_hash(svc.state)
    rebuilt = rebuild(cfg, 5, svc._repo.load_commands(),  # type: ignore[attr-defined,arg-type]
                      created_at="2026-07-08T00:00:00Z",
                      maintenance=svc._repo.load_maintenance(),  # type: ignore[attr-defined]
                      cron_resolver=resolve_cron)
    assert state_hash(rebuilt) == live
