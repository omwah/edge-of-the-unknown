"""WP33 — signature-mechanic framework + first hooks (§6.2).

Two layers: pure-hook unit tests (verdict determinism, one-shot flee drop, the attack
gate) and reducer-level integration through the real `Converse` path (a choice into a
`sig.*` prompt runs the hook, applies its effects, speaks the verdict, and replays to
the identical state hash).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import DEFAULT_CONFIG_PATH, load_config_with_sidecar
from edge.core import mechanics
from edge.core.models import AlienSpecies, Player, UniverseState
from edge.core.rules import Converse, apply_result, reduce
from edge.dialogue.select import validate_dialogue
from edge.store.snapshots import state_hash
from helpers import generate_with_player

# The morality_judge verdict corpus lives in the species-grammar sidecar, which the loader
# strips under pytest (edge.config — tests default to the base personas). These tests exercise
# the mechanic through real dialogue, so they opt back into the sidecar via load_config_with_sidecar.
_SIDECAR = DEFAULT_CONFIG_PATH.parent / "dialogue" / "alien_dialogue_species.yaml"
CFG = load_config_with_sidecar(_SIDECAR)
SMALL = CFG.model_copy(
    update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})})


def _ctx(roster_id: str, *, alignment: int = 0, stage: str | None = None,
         approach: str | None = None) -> mechanics.MechanicContext:
    """A pure hook context around a synthetic player/species for the given roster kind."""
    sc = CFG.roster.species_by_id(roster_id)
    assert sc is not None and sc.signature_mechanic is not None
    species = AlienSpecies(
        id=1, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id, sector_id=5,
        home_band=sc.home_band or "Hub", tech_level=sc.tech_level, base_disposition=0.9,
        disposition_center=sc.disposition_center, disposition_variance=sc.disposition_variance)
    player = Player(id=1, name="Rook", ship_id=1, latinum=0, alignment=alignment)
    return mechanics.MechanicContext(
        player=player, species=species, sc=sc, aliens=CFG.aliens, stage=stage,
        params=sc.signature_mechanic.params, approach=approach)


# --- pure hooks ------------------------------------------------------------------------

@pytest.mark.parametrize("alignment,verdict,stage", [
    (10, "blessed", "judged_blessed"),
    (3, "blessed", "judged_blessed"),   # boundary: >= bless_alignment
    (2, "weighed", "judged_weighed"),
    (-2, "weighed", "judged_weighed"),
    (-3, "cursed", "judged_cursed"),    # boundary: <= curse_alignment
    (-10, "cursed", "judged_cursed"),
])
def test_morality_judge_verdict_deterministic(alignment: int, verdict: str, stage: str) -> None:
    """The judge's verdict is a pure function of the alignment conduct counter."""
    result = mechanics.run_hook(_ctx("concordance", alignment=alignment))
    assert result is not None
    assert result.facts["verdict"] == verdict
    assert result.stage == stage
    # Idempotent: auditing the same conduct twice yields the identical verdict.
    assert mechanics.run_hook(_ctx("concordance", alignment=alignment)) == result


def test_morality_judge_effects_by_band() -> None:
    """Blessing pays attitude + experience; a curse forms a grudge; a weigh does nothing."""
    blessed = mechanics.run_hook(_ctx("concordance", alignment=10))
    assert blessed is not None and blessed.attitude_delta > 0 and blessed.experience_delta > 0
    assert not blessed.grudge
    cursed = mechanics.run_hook(_ctx("concordance", alignment=-10))
    assert cursed is not None and cursed.grudge and cursed.experience_delta == 0
    weighed = mechanics.run_hook(_ctx("concordance", alignment=0))
    assert weighed is not None
    assert not weighed.grudge and weighed.attitude_delta == 0 and weighed.experience_delta == 0


def test_flee_drop_is_one_shot() -> None:
    """A flee_drop species drops cargo the first contact, nothing once already fled."""
    first = mechanics.run_hook(_ctx("selvi", stage=None))
    assert first is not None and first.latinum_delta > 0 and first.stage == "fled"
    again = mechanics.run_hook(_ctx("selvi", stage="fled"))
    assert again is not None and again.latinum_delta == 0


def test_influence_gate_forbids_attack() -> None:
    """`attack_forbidden` is true only for a cannot_attack_unbidden influence-gate species."""
    dignar = CFG.roster.species_by_id("dignar")
    terran = CFG.roster.species_by_id("terran")
    assert dignar is not None and terran is not None
    assert mechanics.attack_forbidden(dignar) is True
    assert mechanics.attack_forbidden(terran) is False


def test_run_hook_none_for_absent_or_unimplemented() -> None:
    """An absent mechanic, and a WP37-and-later hook, both resolve to None (never raise)."""
    terran = CFG.roster.species_by_id("terran")  # no signature_mechanic
    assert terran is not None and terran.signature_mechanic is None
    species = AlienSpecies(
        id=1, roster_id="terran", name="Terran", archetype_id=terran.archetype_id, sector_id=5,
        home_band="Hub", tech_level=1, base_disposition=0.9,
        disposition_center=0.9, disposition_variance=0.1)
    ctx = mechanics.MechanicContext(
        player=Player(id=1, name="R", ship_id=1, latinum=0), species=species, sc=terran,
        aliens=CFG.aliens, stage=None, params={})
    assert mechanics.run_hook(ctx) is None
    # A hook name known to config but not yet implemented (WP37) also resolves to None.
    trojan = CFG.roster.species_by_id("thessbrood")
    assert trojan is not None and trojan.signature_mechanic is not None
    assert trojan.signature_mechanic.hook not in mechanics.MECHANIC_HOOKS
    assert mechanics.run_hook(_ctx("thessbrood")) is None


# --- reducer integration ---------------------------------------------------------------

def _entity_world(alignment: int, *, seed: int = 1) -> tuple[UniverseState, int]:
    """A generated world with the Concordance placed in the player's sector."""
    state = generate_with_player(SMALL, seed)
    # The Entity's contact is sensor-gated at Legendary difficulty (§7, WP35), so the ship
    # must carry sensors strong enough to resolve it before the judgment can be reached.
    ship = replace(state.ships[1], sensor_rating=CFG.discovery.sensor_difficulty["LEGENDARY"])
    state.ships[1] = ship
    sc = CFG.roster.species_by_id("concordance")
    assert sc is not None
    species = AlienSpecies(
        id=1, roster_id="concordance", name=sc.name, archetype_id=sc.archetype_id,
        sector_id=ship.sector_id, home_band="Void", tech_level=sc.tech_level,
        base_disposition=0.9, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
        persona=sc.persona)
    state.species[1] = species
    state.players[1] = replace(state.players[1], alignment=alignment)
    return state, species.id


def _submit(state: UniverseState, sid: int) -> object:
    # choice 0 on the Concordance greeting is "Submit to the judgment" → the sig prompt.
    return reduce(state, 1, Converse(sid, "greeting", choice_index=0), CFG)


def test_judgment_reducer_blesses() -> None:
    """A virtuous player is blessed: stage persisted, attitude up, experience paid, spoken."""
    state, sid = _entity_world(10)
    res = _submit(state, sid)
    player = res.players[0]
    assert player.species_arcs["concordance"]["sig_stage"] == "judged_blessed"
    assert player.species_attitudes["concordance"] > 0
    assert player.experience > 0
    assert "concordance" not in player.grudges
    contexts = {getattr(e, "context", None) for e in res.events}
    assert "sig.morality_judge.verdict" in contexts


def test_judgment_reducer_curses_with_grudge() -> None:
    """A criminal player is cursed: a permanent grudge forms (never_forgets Entity)."""
    state, sid = _entity_world(-10)
    res = _submit(state, sid)
    player = res.players[0]
    assert player.species_arcs["concordance"]["sig_stage"] == "judged_cursed"
    grudge = player.grudges["concordance"]
    assert grudge.duration_days < 0  # permanent (never_forgets / betrayal permanent)


def test_judgment_stage_ladder_replays() -> None:
    """The judgment command replays to the identical state hash (the stage-ladder rail)."""
    state_a, sid_a = _entity_world(10)
    apply_result(state_a, _submit(state_a, sid_a))
    state_b, sid_b = _entity_world(10)
    apply_result(state_b, _submit(state_b, sid_b))
    assert state_hash(state_a) == state_hash(state_b)
    # Re-entry ("Judge me once more") is reachable from the blessed node and stays stable.
    res = reduce(state_a, 1, Converse(sid_a, "sig.morality_judge.verdict", choice_index=1), CFG)
    assert res.players[0].species_arcs["concordance"]["sig_stage"] == "judged_blessed"


def test_attack_reply_gated_by_influence() -> None:
    """The reducer rejects an `attack` reply against an influence-gate species by its gate."""
    state = generate_with_player(SMALL, 1)
    ship = state.ships[1]
    sc = CFG.roster.species_by_id("dignar")
    assert sc is not None
    species = AlienSpecies(
        id=1, roster_id="dignar", name=sc.name, archetype_id=sc.archetype_id,
        sector_id=ship.sector_id, home_band="Hub", tech_level=sc.tech_level,
        base_disposition=0.7, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, persona=sc.persona)
    state.species[1] = species
    assert mechanics.attack_forbidden(sc)  # the gate the reducer message names


def test_corpus_stays_valid() -> None:
    """The sig.* verdict corpus resolves under the §13 integrity suite."""
    validate_dialogue(CFG.roster)
