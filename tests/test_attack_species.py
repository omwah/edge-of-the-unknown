"""WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10).

`AttackSpecies` opens the same encounter machinery the WP24 violence opener uses, but by
the player's hand: the gates are shared with the contact projection
(`encounters.first_strike_block`), the §6.5 souring rail fires at initiation, and other
players are projected into the sector view as engageable ships.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from edge.core import encounters
from edge.core.combat import CombatError
from edge.core.discovery import entity_species
from edge.core.events import AttitudeChanged, EncounterStarted, GrudgeFormed
from edge.core.models import AlienSpecies, UniverseState
from edge.core.rules import AttackSpecies, CombatAction, apply_result, reduce
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash
from test_contact import CFG, SMALL, _inject, _world


def _noncore(state: UniverseState) -> int:
    return next(sid for sid, sec in sorted(state.sectors.items()) if not sec.is_galactic_core)


def _stage(state: UniverseState, roster_id: str = "vesk", **kw: object) -> AlienSpecies:
    """Inject `roster_id` and move it + the player's ship to a shared non-Core sector."""
    sp = _inject(state, roster_id, **kw)  # type: ignore[arg-type]
    out = _noncore(state)
    state.ships[1] = replace(state.ships[1], sector_id=out)
    state.species[sp.id] = replace(sp, sector_id=out)
    return state.species[sp.id]


# --- the first strike ---------------------------------------------------------


def test_first_strike_opens_the_encounter_and_sours() -> None:
    state = _world()
    sp = _stage(state)
    res = reduce(state, 1, AttackSpecies(sp.id), CFG)
    apply_result(state, res)
    player = state.players[1]
    enc = player.active_encounter
    assert enc is not None and enc.species_id == sp.id and enc.foes
    assert enc.speech_context == "combat_open"
    assert player.contact_session is None
    started = next(e for e in res.events if isinstance(e, EncounterStarted))
    assert started.hostile and started.species_id == sp.id and started.pack_size == len(enc.foes)
    # First-strike souring (§6.5): one kill's worth of attitude + an honest grudge cause.
    assert any(isinstance(e, GrudgeFormed) for e in res.events)
    assert any(isinstance(e, AttitudeChanged) for e in res.events)
    assert player.species_attitudes["vesk"] < 0
    assert "opened fire" in player.grudges["vesk"].cause


def test_the_fight_proceeds_through_ordinary_rounds() -> None:
    state = _world()
    sp = _stage(state)
    apply_result(state, reduce(state, 1, AttackSpecies(sp.id), CFG))
    for _ in range(40):
        if state.players[1].active_encounter is None:
            break
        apply_result(state, reduce(state, 1, CombatAction(action="fight"), CFG))
    assert state.players[1].active_encounter is None  # resolved (victory or pod), never stuck


def test_attack_rejected_while_already_engaged() -> None:
    state = _world()
    sp = _stage(state)
    apply_result(state, reduce(state, 1, AttackSpecies(sp.id), CFG))
    with pytest.raises(Exception, match="engaged"):
        reduce(state, 1, AttackSpecies(sp.id), CFG)


# --- the shared gates (first_strike_block ⇔ reducer lockstep) -------------------


def test_attack_blocked_in_the_core_sanctuary() -> None:
    state = _world()
    sp = _inject(state, "vesk")  # the player starts in the Core (start_sector 1)
    assert state.sectors[state.ships[1].sector_id].is_galactic_core
    with pytest.raises(CombatError, match="sanctuary"):
        reduce(state, 1, AttackSpecies(sp.id), CFG)


def test_attack_on_the_entity_finds_no_lock() -> None:
    state = _world()
    ent = entity_species(state, CFG)
    assert ent is not None
    out = _noncore(state)
    state.ships[1] = replace(state.ships[1], sector_id=out)
    state.species[ent.id] = replace(ent, sector_id=out)
    with pytest.raises(CombatError, match="nothing to lock"):
        reduce(state, 1, AttackSpecies(ent.id), CFG)


def test_attack_on_an_influence_gate_species_is_stayed() -> None:
    state = _world()
    sp = _stage(state, "dignar")  # cannot_attack_unbidden influence gate (§6.2)
    with pytest.raises(CombatError, match="influence"):
        reduce(state, 1, AttackSpecies(sp.id), CFG)


def test_attack_on_a_noncombatant_is_pointless() -> None:
    state = _world()
    sp = _stage(state, "selvani")  # combatant: false
    with pytest.raises(CombatError, match="no ships"):
        reduce(state, 1, AttackSpecies(sp.id), CFG)


def test_block_reasons_match_between_projection_and_reducer() -> None:
    """The projection greys FIGHT with the very string the reducer raises (lockstep)."""
    state = _world()
    sp = _inject(state, "vesk")  # in the Core
    sc = CFG.roster.species_by_id("vesk")
    reason = encounters.first_strike_block(state, state.ships[1], sp, sc, CFG)
    assert reason is not None
    with pytest.raises(CombatError) as err:
        reduce(state, 1, AttackSpecies(sp.id), CFG)
    assert str(err.value) == reason


# --- other players in the sector view (WP67's projection promise) ---------------


def test_other_players_project_into_the_sector_view(tmp_path: Path) -> None:
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "mp.db"),  # type: ignore[arg-type]
                               created_at="2026-07-08T00:00:00Z")
    state = svc.state
    p1 = state.players[1]
    s1 = state.ships[p1.ship_id]
    s2 = replace(s1, id=900, owner_player_id=2)
    state.ships[900] = s2
    state.players[2] = replace(p1, id=2, name="Rival", ship_id=900, bounty=500)
    view = svc.game_view(1)
    mine = [s for s in view.sector.ships if s.player_id == 2]
    assert len(mine) == 1
    assert "Rival" in mine[0].name and "☠" in mine[0].name  # outlaw marker (bounty > 0)
    assert mine[0].contact_id is None
    # and the player never sees their own ship as a contact
    assert not any(s.player_id == 1 for s in view.sector.ships)


# --- replay ---------------------------------------------------------------------


def test_first_strike_replays_to_identical_hash(tmp_path: Path) -> None:
    from edge.core.dev import DevPatch
    from edge.engine.cron import resolve_cron

    svc = GameService.new_game(SMALL, 5, SqliteRepository(tmp_path / "replay.db"),  # type: ignore[arg-type]
                               created_at="2026-07-08T00:00:00Z")
    there = lambda sp: replace(svc.state.ships[1], sector_id=sp.sector_id)  # noqa: E731
    target = next(
        (sp for _, sp in sorted(svc.state.species.items())
         if not svc.state.sectors[sp.sector_id].is_galactic_core
         and (sc := CFG.roster.species_by_id(sp.roster_id)) is not None
         and encounters.first_strike_block(svc.state, there(sp), sp, sc, SMALL) is None),
        None,
    )
    if target is None:
        pytest.skip("no attackable placed species in this seed")
    svc.apply(1, DevPatch("teleport", "", value=target.sector_id))
    svc.apply(1, AttackSpecies(target.id))
    for _ in range(3):
        if svc.state.players[1].active_encounter is None:
            break
        svc.apply(1, CombatAction(action="flee"))
    live = state_hash(svc.state)
    rebuilt = rebuild(SMALL, 5, svc._repo.load_commands(),  # type: ignore[attr-defined,arg-type]
                      created_at="2026-07-08T00:00:00Z",
                      maintenance=svc._repo.load_maintenance(),  # type: ignore[attr-defined]
                      cron_resolver=resolve_cron)
    assert state_hash(rebuilt) == live
