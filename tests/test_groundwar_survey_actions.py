"""GW-WP06 — authoritative survey actions, persistence, and reward settlement.

Drives the real reducers (`GroundMove` / `SurveyDig` / `SurveyTalk` / `ExtractGroundOperation`)
against a hand-built one-world universe and checks the D4-D6 contract: supplies never go
negative, a dry re-dig is free, a dig settles the artifact/codex/XP reward exactly once
through the discovery rail, macro-turns are charged in the configured quanta (movement only),
supply exhaustion ends the expedition while extraction stays legal, and D5 position/hints
survive a re-descent while trenches and supplies reset. Closes with a command-log replay
golden (same seed + log → identical state hash).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.enums import DiscoveryKind, PayloadKind, RarityTier
from edge.core.groundwar import survey as gw
from edge.core.models import (
    Discovery, DiscoveryPayload, Game, Ownership, Planet, Player, Sector, Ship, UniverseState,
)
from edge.core.movement import MovementError
from edge.core.rules import (
    BeginSurvey, ExtractGroundOperation, GroundMove, SurveyDig, SurveyLand, SurveyTalk,
    apply_result, reduce,
)
from edge.core.surface_finds import surface_find_name
from edge.store.snapshots import state_hash

CFG = load_default_config()
EXP = CFG.groundwar.expedition  # type: ignore[union-attr]


def _world(*, inhabited: bool = False, sites: int = 1, seed: int = 3) -> UniverseState:
    st = UniverseState.new(Game(1, seed, CFG.config_version, "t"))
    st.sectors = {1: Sector(1, 1, (), "Frontier")}
    st.rebuild_adjacency()
    # An inhabited world must be *friendly* to route to survey (else the classifier sends it to
    # assault) — model it as the player's own colony so settlements generate (D1/D5).
    st.planets = {1: Planet(1, 1, "World", "terrestrial_warm", habitability_cap=1000,
                            owner=Ownership("player", 1) if inhabited else Ownership("none"),
                            population={"terran": 500} if inhabited else {})}
    st.ships = {1: Ship(id=1, type_id="trailblazer", name="S", owner_player_id=1,
                        sector_id=1, holds_total=60, turns_per_warp=1, sensor_rating=9)}
    st.players = {1: Player(id=1, name="you", ship_id=1, latinum=100, turns_remaining=250)}
    st.discoveries = {
        10 + i: Discovery(
            id=10 + i, kind=DiscoveryKind.RUINS, rarity_tier=RarityTier.RARE, sector_id=1,
            payload=DiscoveryPayload(kind=PayloadKind.ARTIFACT, barter_tier="II", lore=f"lore{i}"),
            planet_id=1, site_slot=i, hidden=False, name=f"Site {i}")
        for i in range(sites)
    }
    return st


def _land(st: UniverseState, pid: int) -> None:
    """Set the shuttle down on the generated landing zone (GW-WP07-FU2).

    Choosing a drop site is covered in test_groundwar_expedition_view; these tests are
    about what happens once the survey is on the ground, so they take the default.
    """
    op = st.players[pid].ground_operation
    smap = gw.survey_map_for(st, op, CFG)
    x, y = gw.suggested_landing(smap, CFG, op.explorer_x, op.explorer_y)
    apply_result(st, reduce(st, pid, SurveyLand(op.operation_id, x, y), CFG))


def _begin(st: UniverseState) -> None:
    apply_result(st, reduce(st, 1, BeginSurvey(1), CFG))
    _land(st, 1)


def _op(st: UniverseState):
    return st.players[1].ground_operation


def _walk_onto(st: UniverseState, site: gw.SurveySite) -> None:
    """March until the explorer stands on `site` (marches halt early, so loop)."""
    for _ in range(30):
        op = _op(st)
        if (op.explorer_x, op.explorer_y) == (site.x, site.y):
            return
        apply_result(st, reduce(st, 1, GroundMove(op.operation_id, site.x, site.y), CFG))
    raise AssertionError("could not reach the site")


def _stand_on(st: UniverseState, pid: int, x: int, y: int) -> None:
    """Teleport a player's explorer onto `(x, y)` — isolates dig/talk from march distance."""
    op = st.players[pid].ground_operation
    st.players[pid] = replace(  # type: ignore[index]
        st.players[pid], ground_operation=replace(op, explorer_x=x, explorer_y=y))


# --- movement + macro-turn quanta (D4/D12) -----------------------------------


def test_march_charges_macro_turns_in_quanta() -> None:
    st = _world()
    _begin(st)
    op = _op(st)
    smap = gw.survey_map_for(st, op, CFG)
    before = st.players[1].turns_remaining
    apply_result(st, reduce(st, 1, GroundMove(op.operation_id, smap.sites[0].x, smap.sites[0].y), CFG))
    op2 = _op(st)
    spent = before - st.players[1].turns_remaining
    import math
    expected = math.ceil(op2.local_turn / EXP.local_turns_per_main_turn) * EXP.main_turn_cost
    assert spent == expected and spent >= 1


def test_march_no_longer_halts_early_on_a_sighted_clue() -> None:
    """A march used to stop the instant fresh disturbed ground came into sight — cheap
    on a short hop, but it meant a march onto a site's own position (whose clues
    necessarily surround it) never arrived in one `GroundMove` call; `_walk_onto`
    above exists only because of that. The auto-halt was removed: with turns and
    supplies to spare, one call now covers the whole path."""
    st = _world(sites=1)
    _begin(st)
    op = _op(st)
    smap = gw.survey_map_for(st, op, CFG)
    site = smap.sites[0]
    apply_result(st, reduce(st, 1, GroundMove(op.operation_id, site.x, site.y), CFG))
    op2 = _op(st)
    assert (op2.explorer_x, op2.explorer_y) == (site.x, site.y)


def test_move_rejects_when_no_turns_left() -> None:
    st = _world()
    _begin(st)
    st.players[1] = replace(st.players[1], turns_remaining=0)  # type: ignore[index]
    op = _op(st)
    with pytest.raises(MovementError):
        reduce(st, 1, GroundMove(op.operation_id, op.explorer_x + 20, op.explorer_y), CFG)


def test_supplies_never_negative_and_exhaustion_ends_expedition() -> None:
    st = _world(sites=1)
    _begin(st)
    op = _op(st)
    # Strand the surveyor far from the (only) site with almost no supplies, then dig dry.
    st.players[1] = replace(st.players[1], ground_operation=replace(op, supplies=1))  # type: ignore[index]
    op = _op(st)
    apply_result(st, reduce(st, 1, SurveyDig(op.operation_id), CFG))  # dry dig spends the last supply
    op = _op(st)
    assert op.supplies == 0 and op.outcome == "exhausted"
    with pytest.raises(MovementError):  # time-advancing actions barred once exhausted…
        reduce(st, 1, GroundMove(op.operation_id, op.explorer_x + 5, op.explorer_y), CFG)
    apply_result(st, reduce(st, 1, ExtractGroundOperation(op.operation_id), CFG))  # …extraction still legal
    assert _op(st) is None


# --- digging + reward settlement (D6/D10) ------------------------------------


def test_dig_settles_artifact_codex_xp_exactly_once() -> None:
    st = _world(sites=2)  # two sites, so excavating one does not complete the expedition
    _begin(st)
    site = next(s for s in gw.survey_map_for(st, _op(st), CFG).sites if s.discovery_id == 10)
    _stand_on(st, 1, site.x, site.y)
    apply_result(st, reduce(st, 1, SurveyDig(_op(st).operation_id), CFG))
    p = st.players[1]
    assert 10 in p.codex and 10 in p.detected
    assert p.experience == CFG.aliens.experience_per_discovery
    assert len(p.artifact_records) == 1
    rec = p.artifact_records[0]
    assert rec.discovery_id == 10 and rec.rarity == "RARE" and rec.research_domain == "ruins"
    assert rec.origin_site == surface_find_name(DiscoveryKind.RUINS, 10)
    assert st.discoveries[10].found_by == 1
    # A second dig on the same (now spent) ground mints nothing more (exactly once).
    apply_result(st, reduce(st, 1, SurveyDig(_op(st).operation_id), CFG))
    p2 = st.players[1]
    assert len(p2.artifact_records) == 1 and p2.experience == CFG.aliens.experience_per_discovery


def test_dry_redig_is_free() -> None:
    st = _world(sites=1)
    _begin(st)
    op = _op(st)
    apply_result(st, reduce(st, 1, SurveyDig(op.operation_id), CFG))  # first dig (a miss — supplies drop)
    after_first = _op(st).supplies
    apply_result(st, reduce(st, 1, SurveyDig(_op(st).operation_id), CFG))  # same ground, already turned over
    assert _op(st).supplies == after_first  # no further supply spent


def test_simultaneous_excavation_mints_one_artifact() -> None:
    st = _world(sites=1)
    st.players[2] = replace(st.players[1], id=2, ship_id=2)  # type: ignore[index]
    st.ships[2] = replace(st.ships[1], id=2, owner_player_id=2)  # type: ignore[index]
    for pid in (1, 2):
        apply_result(st, reduce(st, pid, BeginSurvey(1), CFG))
        _land(st, pid)
        site = gw.survey_map_for(st, st.players[pid].ground_operation, CFG).sites[0]
        _stand_on(st, pid, site.x, site.y)
        apply_result(st, reduce(st, pid, SurveyDig(st.players[pid].ground_operation.operation_id), CFG))
    # First to dig owns the artifact; the second logs knowledge but mints no second record (G8).
    assert st.discoveries[10].found_by == 1
    assert len(st.players[1].artifact_records) == 1
    assert len(st.players[2].artifact_records) == 0 and 10 in st.players[2].codex


# --- settlement talk (D5) ----------------------------------------------------


def test_talk_resupplies_and_hints_once() -> None:
    st = _world(inhabited=True, sites=3)
    _begin(st)
    smap = gw.survey_map_for(st, _op(st), CFG)
    assert smap.settlements, "an inhabited world should have settlements"
    town = smap.settlements[0]
    # Stand in the town, drop supplies so a resupply is observable.
    st.players[1] = replace(  # type: ignore[index]
        st.players[1], ground_operation=replace(_op(st), explorer_x=town.cx, explorer_y=town.cy,
                                                supplies=10))
    apply_result(st, reduce(st, 1, SurveyTalk(_op(st).operation_id), CFG))
    op = _op(st)
    assert op.supplies > 10  # resupplied
    assert len(op.hinted_discovery_ids) == 1  # one site narrowed
    hinted = set(op.hinted_discovery_ids)
    apply_result(st, reduce(st, 1, SurveyTalk(op.operation_id), CFG))  # talk again
    # A site is hinted at most once; a second talk never re-hints the same one.
    assert hinted <= set(_op(st).hinted_discovery_ids)


def test_talk_off_settlement_rejected() -> None:
    st = _world(inhabited=True, sites=1)
    _begin(st)
    op = _op(st)  # lands away from any town
    with pytest.raises(MovementError):
        reduce(st, 1, SurveyTalk(op.operation_id), CFG)


# --- D5 persistence across re-descent ----------------------------------------


def test_position_and_hints_persist_while_trenches_and_supplies_reset() -> None:
    st = _world(inhabited=True, sites=2)
    _begin(st)
    op = _op(st)
    # Dig once (lay a trench) and record a hint by talking in a town.
    smap = gw.survey_map_for(st, op, CFG)
    town = smap.settlements[0]
    st.players[1] = replace(  # type: ignore[index]
        st.players[1], ground_operation=replace(op, explorer_x=town.cx, explorer_y=town.cy))
    apply_result(st, reduce(st, 1, SurveyTalk(_op(st).operation_id), CFG))
    apply_result(st, reduce(st, 1, SurveyDig(_op(st).operation_id), CFG))
    before = _op(st)
    before_map = gw.survey_map_for(st, before, CFG)
    saved_pos = (before.explorer_x, before.explorer_y)
    saved_hints = before.hinted_discovery_ids
    assert before.dug_cells  # a trench was laid
    apply_result(st, reduce(st, 1, ExtractGroundOperation(before.operation_id), CFG))
    apply_result(st, reduce(st, 1, BeginSurvey(1), CFG))
    after = _op(st)
    after_map = gw.survey_map_for(st, after, CFG)
    assert after.seed == before.seed                              # terrain identity persists
    assert after_map.feature == before_map.feature
    assert [(s.discovery_id, s.x, s.y) for s in after_map.sites] == [
        (s.discovery_id, s.x, s.y) for s in before_map.sites
    ]
    assert (after.explorer_x, after.explorer_y) == saved_pos  # position persists (D5)
    assert after.hinted_discovery_ids == saved_hints          # hints persist (D5)
    assert after.dug_cells == frozenset()                     # trenches reset
    assert after.supplies == EXP.supplies_start               # supplies reset


# --- replay determinism ------------------------------------------------------


def test_command_log_rebuilds_to_identical_hash() -> None:
    def play() -> str:
        st = _world(sites=1)
        _begin(st)
        site = gw.survey_map_for(st, _op(st), CFG).sites[0]
        _walk_onto(st, site)
        apply_result(st, reduce(st, 1, SurveyDig(_op(st).operation_id), CFG))
        apply_result(st, reduce(st, 1, ExtractGroundOperation(_op(st).operation_id), CFG))
        return state_hash(st)

    assert play() == play()  # same seed + command log → identical state
