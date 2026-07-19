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
from edge.core.config import SignatureMechanicConfig
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
    update={
        "bigbang": CFG.bigbang.model_copy(
            update={
                "sector_count": 90,
                "start_sector": 1,
                "home_cluster_min": 3,
                "home_cluster_max": 5,
                "core_sector_count": 5,
            }
        )
    }
)



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


def test_run_hook_none_for_absent_or_unregistered() -> None:
    """An absent mechanic, and a hook id the code has not grown, both resolve to None."""
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
    # A hook name not in the registry (a roster naming a hook the code lacks) also → None.
    unknown_sc = terran.model_copy(update={
        "signature_mechanic": SignatureMechanicConfig(hook="not_a_real_hook")})
    assert mechanics.run_hook(replace(ctx, sc=unknown_sc)) is None


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


# --- WP37: transactional hooks (stage machines + bounded effects, §6.2) ---------------

@pytest.mark.parametrize("stage,approach,exp_stage,exp_lat", [
    (None, "offer", "offered", 0),
    (None, "accept", "carried", 200),          # sweetener paid up front, the trap now aboard
    (None, "refuse", "declined", 0),
    ("carried", "defuse", "defused", -140),     # paid removal at the counter-market
    ("carried", "haggle", "sprung", -320),      # any other contact while carrying detonates it
    ("sprung", "defuse", "sprung", 0),          # terminal — inert
])
def test_trojan_gift_stage_machine(stage, approach, exp_stage, exp_lat) -> None:
    r = mechanics.run_hook(_ctx("thessbrood", stage=stage, approach=approach))
    assert r is not None and r.stage == exp_stage and r.latinum_delta == exp_lat


def test_escalating_demand_ladder_climbs_then_satisfies() -> None:
    """comply up the [donate, destroy_target, surrender_base] ladder → satisfied (a boon)."""
    stage, r = None, None
    for expect in ("demand_1", "demand_2", "satisfied"):
        r = mechanics.run_hook(_ctx("vennrith", stage=stage, approach="comply"))
        assert r is not None and r.stage == expect
        stage = r.stage
    assert r is not None and r.attitude_delta > 0 and r.experience_delta > 0


def test_escalating_demand_refuse_betrays() -> None:
    r = mechanics.run_hook(_ctx("vennrith", stage="demand_1", approach="refuse"))
    assert r is not None and r.stage == "betrayed" and r.grudge


@pytest.mark.parametrize("approach,exp_stage", [("accept", "contracted"), ("decline", "declined")])
def test_contract_kill_offer_and_gate(approach, exp_stage) -> None:
    r = mechanics.run_hook(_ctx("cibelline", approach=approach))
    # WP37 authors/gates the contract; the razing + reward payout land in WP40 (no effect yet).
    assert r is not None and r.stage == exp_stage and r.latinum_delta == 0
    assert r.facts["contract_target"] == "vesk"


def test_coordinate_broker_extort() -> None:
    paid = mechanics.run_hook(_ctx("selvani", approach="pay"))
    assert paid is not None and paid.stage == "paid" and paid.latinum_delta < 0
    spurned = mechanics.run_hook(_ctx("selvani", approach="refuse"))
    assert spurned is not None and spurned.stage == "spurned" and spurned.grudge


def test_passage_broker_misleads_without_benefit() -> None:
    r = mechanics.run_hook(_ctx("stryx", approach="pay"))
    assert r is not None and r.stage == "misled" and r.latinum_delta < 0


def test_reprogram_unlock_install_pays_xp_and_binds_target() -> None:
    r = mechanics.run_hook(_ctx("vesk", approach="install"))
    assert r is not None and r.stage == "unlocked" and r.experience_delta > 0
    assert r.facts["reprogram_target"] == "helot" and r.facts["reprogram_posture"] == "open"


def test_transactional_hooks_are_deterministic() -> None:
    """Each hook is a pure function of (stage, approach, params) — the golden-replay guarantee."""
    for rid, appr in [("thessbrood", "accept"), ("vennrith", "comply"), ("cibelline", "accept"),
                      ("selvani", "pay"), ("stryx", "pay"), ("vesk", "install")]:
        assert mechanics.run_hook(_ctx(rid, approach=appr)) == mechanics.run_hook(_ctx(rid, approach=appr))


def _apply(roster_id: str, result: mechanics.MechanicResult, *, latinum: int = 1000):
    """Apply a hook result through the reducer helper against a minimal injected species."""
    from edge.core import rules
    state = generate_with_player(SMALL, 1)
    sc = CFG.roster.species_by_id(roster_id)
    assert sc is not None
    species = AlienSpecies(
        id=1, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id,
        sector_id=state.ships[1].sector_id, home_band=sc.home_band or "Hub",
        tech_level=sc.tech_level, base_disposition=0.5,
        disposition_center=sc.disposition_center, disposition_variance=sc.disposition_variance)
    state.species[1] = species
    state.players[1] = replace(state.players[1], latinum=latinum)
    return rules._apply_mechanic(state, state.players[1], species, sc, result, CFG)


def test_payload_drain_clamps_latinum_at_zero() -> None:
    """A drain larger than the purse clamps at zero — the no-negative-balance invariant."""
    player, _ = _apply("thessbrood", mechanics.MechanicResult(stage="sprung", latinum_delta=-320),
                       latinum=100)
    assert player.latinum == 0


def test_escalating_betrayal_forms_permanent_grudge() -> None:
    """A refused demand routes through WP27: vennrith (never_forgets) forms an undying grudge."""
    result = mechanics.run_hook(_ctx("vennrith", stage="demand_1", approach="refuse"))
    assert result is not None
    player, events = _apply("vennrith", result)
    assert "vennrith" in player.grudges and player.grudges["vennrith"].duration_days < 0
    assert player.species_arcs["vennrith"]["sig_stage"] == "betrayed"
    assert any(type(e).__name__ == "GrudgeFormed" for e in events)
