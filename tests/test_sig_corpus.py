"""WP74 — the signature-mechanic corpus routes (SEAMS_PLAN A2, decision D4).

The six previously corpus-dark hooks are now routed from each carrier species'
`contract_offer` node (base corpus `species_grammars`); these tests drive the real
`Converse` path end-to-end: the choice transitions into the `sig.*` prompt, the hook
runs with the right approach, bounded effects land, and the reprogram sub-seam flips
the target kind's live trade posture (`mechanics.effective_trade_posture`).
Under pytest the loader keeps only the base corpus, which is exactly what is under test.
"""

from __future__ import annotations

from dataclasses import replace

from edge.config import load_default_config
from edge.core import mechanics
from edge.core.models import AlienSpecies, UniverseState
from edge.core.rules import Converse, apply_result, reduce
from edge.server.session import contact_view
from helpers import generate_with_player

CFG = load_default_config()
SMALL = CFG.model_copy(
    update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})})
# The sig routes live on each offer node's *catch-all* entry; disable WP57 favors so a live
# job offer never outranks it (the favor flow keeps its own suite, tests/test_contracts.py).
NOJOBS = SMALL.model_copy(update={"aliens": SMALL.aliens.model_copy(
    update={"contracts": SMALL.aliens.contracts.model_copy(update={"enabled": False})})})


def _world_with(roster_id: str, sid: int = 900) -> tuple[UniverseState, int]:
    state = generate_with_player(SMALL, 1)
    ship = state.ships[1]
    sc = CFG.roster.species_by_id(roster_id)
    assert sc is not None
    state.species[sid] = AlienSpecies(
        id=sid, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id,
        sector_id=ship.sector_id, home_band=sc.home_band or "Hub", tech_level=sc.tech_level,
        base_disposition=0.9, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
        persona=sc.persona)
    return state, sid


def test_every_dark_hook_has_a_corpus_route() -> None:
    """Each carrier species' pack routes a choice into its own sig.* namespace (A2 closed)."""
    for roster_id, hook in [
        ("vesk", "reprogram_unlock"), ("helot", "reprogram_unlock"),
        ("stryx", "passage_broker"), ("concordance", "morality_judge"),
        ("selvi", "flee_drop"), ("vennrith", "escalating_demand"),
        ("thessbrood", "trojan_gift"),
    ]:
        sc = CFG.roster.species_by_id(roster_id)
        assert sc is not None and sc.dialogue_pack, roster_id
        targets = {
            ch.next_context
            for entries in sc.dialogue_pack.values()
            for entry in entries
            for ch in (entry.choices or [])
            if ch.next_context
        }
        assert any(t.startswith(f"sig.{hook}.") for t in targets), (roster_id, hook, targets)


def test_trojan_gift_route_pays_sweetener_then_defuses_for_a_fee() -> None:
    state, sid = _world_with("thessbrood")
    before = state.players[1].latinum
    # Fresh contact: contract_offer's catch-all offers the gift; choice 0 accepts it.
    apply_result(state, reduce(state, 1, Converse(sid, "contract_offer", choice_index=0), NOJOBS))
    player = state.players[1]
    assert player.species_arcs["thessbrood"]["sig_stage"] == "carried"
    assert player.latinum == before + 200  # the sweetener
    # While carried, the offer node shows the removal route; choice 0 defuses (paid).
    apply_result(state, reduce(state, 1, Converse(sid, "contract_offer", choice_index=0), NOJOBS))
    player = state.players[1]
    assert player.species_arcs["thessbrood"]["sig_stage"] == "defused"
    assert player.latinum == before + 200 - 140


def test_reprogram_install_flips_the_helot_trade_posture_live() -> None:
    helot_sc = CFG.roster.species_by_id("helot")
    assert helot_sc is not None and helot_sc.trade_posture == "circuit_gated"
    # A helot contact before the install: the trade reply is gated by the circuit.
    state_h, hid = _world_with("helot", sid=901)
    view = contact_view(state_h, 1, hid, SMALL)
    trade = next(c for c in view.choices if c.action == "trade")
    assert not trade.enabled and "circuit" in trade.reason
    # Install the circuit at the Vesk (choice 0 on their catch-all offer node).
    state, vid = _world_with("vesk")
    apply_result(state, reduce(state, 1, Converse(vid, "contract_offer", choice_index=0), NOJOBS))
    player = state.players[1]
    assert player.species_arcs["vesk"]["sig_stage"] == "unlocked"
    assert player.species_arcs["helot"][mechanics.POSTURE_OVERRIDE_FLAG] == "open"
    # The live posture the player now experiences at any helot is open.
    helot = AlienSpecies(
        id=902, roster_id="helot", name="Helot", archetype_id=helot_sc.archetype_id,
        sector_id=1, home_band="Frontier", tech_level=helot_sc.tech_level,
        base_disposition=0.5, disposition_center=0.5, disposition_variance=0.0)
    assert mechanics.effective_trade_posture(player, helot, helot_sc) == "open"
    # And the contact menu agrees (view/reducer lockstep).
    state.species[902] = replace(helot, sector_id=state.ships[1].sector_id)
    view = contact_view(state, 1, 902, SMALL)
    trade = next(c for c in view.choices if c.action == "trade")
    assert trade.enabled


def test_alliance_gated_trade_opens_for_sworn_members() -> None:
    vennrith_sc = CFG.roster.species_by_id("vennrith")
    assert vennrith_sc is not None and vennrith_sc.trade_posture == "alliance_gated"
    state, sid = _world_with("vennrith")
    sp = state.species[sid]
    member = replace(state.players[1], alliance_id=sp.alliance_id)
    assert mechanics.effective_trade_posture(member, sp, vennrith_sc) == "open"
    outsider = replace(state.players[1], alliance_id=None)
    assert mechanics.effective_trade_posture(outsider, sp, vennrith_sc) == "alliance_gated"


def test_escalating_demand_ladder_climbs_and_betrayal_is_permanent() -> None:
    state, sid = _world_with("vennrith")
    # Open the ladder (choice 0 on the catch-all offer node = comply with the demand).
    apply_result(state, reduce(state, 1, Converse(sid, "contract_offer", choice_index=0), NOJOBS))
    assert state.players[1].species_arcs["vennrith"]["sig_stage"] == "demand_1"
    # Climb from the comply node itself (choice 0 = comply again).
    apply_result(state, reduce(
        state, 1, Converse(sid, "sig.escalating_demand.comply", choice_index=0), NOJOBS))
    assert state.players[1].species_arcs["vennrith"]["sig_stage"] == "demand_2"
    apply_result(state, reduce(
        state, 1, Converse(sid, "sig.escalating_demand.comply", choice_index=0), NOJOBS))
    assert state.players[1].species_arcs["vennrith"]["sig_stage"] == "satisfied"
    # A fresh world: a single refusal is a permanent betrayal (their model).
    state2, sid2 = _world_with("vennrith")
    apply_result(state2, reduce(state2, 1, Converse(sid2, "contract_offer", choice_index=1), NOJOBS))
    assert state2.players[1].species_arcs["vennrith"]["sig_stage"] == "betrayed"
    grudge = state2.players[1].grudges["vennrith"]
    assert grudge.duration_days < 0  # betrayal_model permanent


def test_flee_drop_route_pays_once() -> None:
    state, sid = _world_with("selvi")
    before = state.players[1].latinum
    apply_result(state, reduce(state, 1, Converse(sid, "contract_offer", choice_index=0), NOJOBS))
    assert state.players[1].species_arcs["selvi"]["sig_stage"] == "fled"
    assert state.players[1].latinum == before + 150
    apply_result(state, reduce(
        state, 1, Converse(sid, "sig.flee_drop.contact", choice_index=0), NOJOBS))
    assert state.players[1].latinum == before + 150  # one-shot: nothing more falls
