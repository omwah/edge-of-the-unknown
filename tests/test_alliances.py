"""WP38 — joinable alliances: admission, rival fallout, Core law (§6.3, §10).

Covers the pure standing/admission helpers (`core.aliens`), the JoinAlliance /
ResignAlliance / AdvanceAdmission reducers (gating, exclusivity, fee, fallout), and the
Core-law engagement path in the encounter roll (a rival-aligned player is engaged on
sight by a governing defender).
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core import aliens, encounters
from edge.core.economy import EconomyError
from edge.core.events import AllianceJoined, AllianceResigned
from edge.core.models import (
    AlienSpecies,
    Game,
    Player,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.rules import (
    AdvanceAdmission,
    JoinAlliance,
    ResignAlliance,
    Warp,
    apply_result,
    reduce,
)

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(
    update={"sector_count": 400, "start_sector": 1})})

GOV = CFG.roster.core_governing_alliance_id  # 1 (Terran Federation)
LIBERTY = 4   # rival of the governor
IRON = 3      # petition-gated, not a governor rival


# --- pure helpers -----------------------------------------------------------


def _player(**kw) -> Player:
    base = dict(id=1, name="T", ship_id=1, latinum=100_000)
    base.update(kw)
    return Player(**base)


def _species(roster_id: str, alliance_id: int | None, sector_id: int = 1) -> AlienSpecies:
    return AlienSpecies(
        id=1, roster_id=roster_id, name=roster_id.title(), archetype_id="x",
        sector_id=sector_id, home_band="Hub", tech_level=1,
        base_disposition=1.0, disposition_center=1.0, disposition_variance=0.0,
        alliance_id=alliance_id,
    )


def test_admission_ledger_round_trips() -> None:
    player = _player()
    iron = CFG.roster.alliance(IRON)
    assert not aliens.admission_met(player, iron)
    player = aliens.record_admission_task(player, IRON, "serve")
    player = aliens.record_admission_task(player, IRON, "serve")  # idempotent
    assert aliens.admission_tasks_done(player, IRON) == frozenset({"serve"})
    assert not aliens.admission_met(player, iron)  # still missing "pay"
    player = aliens.record_admission_task(player, IRON, "pay")
    assert aliens.admission_met(player, iron)


def test_join_standing_warms_bloc_and_sours_rivals() -> None:
    # Joining the Iron Covenant (rival of the Verdant Compact) warms 3, sours 2.
    player = aliens.apply_join_standing(_player(), CFG.roster, IRON)
    assert player.alliance_id == IRON
    assert aliens.alliance_standing(player, IRON) == 1.0
    assert aliens.alliance_standing(player, 2) == -1.0  # Verdant Compact, symmetric rival
    assert aliens.alliance_standing(player, GOV) == 0.0  # Federation is not an Iron rival


def test_join_governor_rival_makes_core_unsafe() -> None:
    state = _core_law_state()
    # Aligning with the Liberty Front (a governor rival) sours the Federation.
    player = aliens.apply_join_standing(state.players[1], CFG.roster, LIBERTY)
    state.players[1] = player
    assert aliens.alliance_standing(player, GOV) == -1.0
    assert aliens.governor_hostile(state, player) is True
    # A governing member is still safe in the Core.
    member = replace(player, alliance_id=GOV, alliance_standing={GOV: -1.0})
    assert aliens.governor_hostile(state, member) is False


def test_standing_shift_penalises_rival_species() -> None:
    player = aliens.apply_join_standing(_player(), CFG.roster, LIBERTY)  # governor rival
    gov_species = _species("terran", GOV)
    # Negative standing with the species' bloc → a positive violence penalty.
    assert aliens.alliance_standing_shift(player, gov_species) == 1.0
    friend = _species("terran", LIBERTY)  # a bloc-mate
    assert aliens.alliance_standing_shift(player, friend) == 0.0


# --- reducers ---------------------------------------------------------------


def _generated():
    state = generate(SMALL, 3)
    from edge.core.rules import JoinGame
    apply_result(state, reduce(state, 1, JoinGame(name="T"), SMALL))
    return state


def test_join_requires_admission_price() -> None:
    state = _generated()
    # Iron Covenant petitions: no completed tasks ⇒ rejected.
    with pytest.raises(EconomyError, match="admit you"):
        reduce(state, 1, JoinAlliance(alliance_id=IRON), SMALL)


def test_advance_then_join_succeeds_and_is_exclusive() -> None:
    state = _generated()
    # Bad task token is rejected.
    with pytest.raises(EconomyError, match="admission price"):
        reduce(state, 1, AdvanceAdmission(alliance_id=IRON, task="obey"), SMALL)
    for task in ("serve", "pay"):
        apply_result(state, reduce(state, 1, AdvanceAdmission(alliance_id=IRON, task=task), SMALL))
    before = state.players[1].latinum
    result = reduce(state, 1, JoinAlliance(alliance_id=IRON), SMALL)
    apply_result(state, result)
    player = state.players[1]
    assert player.alliance_id == IRON
    assert player.latinum == before - 1000  # admission fee charged
    assert isinstance(result.events[0], AllianceJoined)
    assert result.events[0].former_alliance_id == GOV  # resigned governing membership
    assert aliens.alliance_standing(player, 2) == -1.0  # Verdant Compact soured


def test_join_liberty_front_is_free_and_sours_governor() -> None:
    state = _generated()
    apply_result(state, reduce(state, 1, JoinAlliance(alliance_id=LIBERTY), SMALL))
    player = state.players[1]
    assert player.alliance_id == LIBERTY
    assert aliens.governor_hostile(state, player) is True


def test_resign_resets_standing() -> None:
    state = _generated()
    apply_result(state, reduce(state, 1, JoinAlliance(alliance_id=LIBERTY), SMALL))
    assert aliens.governor_hostile(state, state.players[1]) is True
    result = reduce(state, 1, ResignAlliance(), SMALL)
    apply_result(state, result)
    player = state.players[1]
    assert player.alliance_id is None
    assert player.alliance_standing == {}
    assert aliens.governor_hostile(state, player) is False
    assert isinstance(result.events[0], AllianceResigned)


def test_resign_when_unaligned_errors() -> None:
    state = _generated()
    apply_result(state, reduce(state, 1, ResignAlliance(), SMALL))  # resign the starting membership
    with pytest.raises(EconomyError, match="belong to no alliance"):
        reduce(state, 1, ResignAlliance(), SMALL)


# --- Core-law engagement ----------------------------------------------------


def _core_law_state() -> UniverseState:
    """A tiny universe: two adjacent sectors, sector 1 the Core, a governing patrol there."""
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=GOV)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(2,), distance_band="Hub",
                              is_galactic_core=True)
    state.sectors[2] = Sector(id=2, region_id=1, warps_out=(1,), distance_band="Hub")
    state.rebuild_adjacency()
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=2, holds_total=20, hull_current=200, hull_max=200,
                          shields=100, warp_speed=3, combat_speed=3, turns_per_warp=1)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=1000, turns_remaining=100,
                              alliance_id=GOV)
    state.species[1] = _species("terran", GOV, sector_id=1)  # a Federation patrol in the Core
    return state


def test_core_law_engages_rival_aligned_player_on_sight() -> None:
    state = _core_law_state()
    # Align with a governor rival → Federation standing goes hostile.
    state.players[1] = aliens.apply_join_standing(state.players[1], CFG.roster, LIBERTY)
    roll = encounters.roll_encounter(
        state, state.players[1], state.ships[1], 1, CFG, random.Random(0))
    assert roll is not None and roll.hostile and roll.encounter is not None
    assert roll.species.roster_id == "terran"


def test_core_law_leaves_loyal_player_alone() -> None:
    state = _core_law_state()  # player is a governing member, standing neutral
    roll = encounters.roll_encounter(
        state, state.players[1], state.ships[1], 1, CFG, random.Random(0))
    assert roll is None  # Hub interrupt_chance is 0 and the player is welcome


def test_core_law_reducer_engages_through_warp() -> None:
    state = _core_law_state()
    state.players[1] = aliens.apply_join_standing(state.players[1], CFG.roster, LIBERTY)
    # Warp from sector 2 into the Core (sector 1): the patrol engages on sight.
    apply_result(state, reduce(state, 1, Warp(to_sector=1), CFG))
    assert state.players[1].active_encounter is not None
