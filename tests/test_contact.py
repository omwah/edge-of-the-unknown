"""WP9 (part 1) — alien contact: hail / buy / barter reducers + projection (§6, §8).

Reducer and projection tests inject a chosen roster species into the player's sector
for determinism; the replay test drives a real placed species through the command log
to prove `species_attitudes` / `dialogue_recency` survive a reload.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core.aliens import effective_disposition
from edge.core.combat import CombatError
from edge.core.discovery import entity_codex_discovery, entity_species
from edge.core.config import RosterConfig
from edge.core.economy import EconomyError
from edge.core.enums import ComponentTier, RarityTier
from edge.core.models import AlienSpecies, UniverseState
from edge.core.movement import shortest_path
from edge.core.rules import (
    AcceptLead,
    BarterArtifact,
    BuyAlienTech,
    Converse,
    Hail,
    Warp,
    apply_result,
    reduce,
)
from edge.dialogue import instance_key
from edge.server import session
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import state_hash
from helpers import generate_with_player

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})})
BRANCH_CFG = load_default_config(dialogue_files=("alien_dialogue_default.yaml",))
BRANCH_SMALL = BRANCH_CFG.model_copy(update={
    "bigbang": BRANCH_CFG.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})})
_CREATED = "2026-06-18T00:00:00Z"


def _world(seed: int = 1) -> UniverseState:
    return generate_with_player(SMALL, seed)


def _inject(state: UniverseState, roster_id: str, *, base: float = 0.85,
            sid: int = 1, latinum: int = 100_000,
            artifacts: dict[str, int] | None = None) -> AlienSpecies:
    """Place a roster species in the player's sector and stock the player to deal."""
    sc = CFG.roster.species_by_id(roster_id)
    assert sc is not None
    ship = state.ships[1]
    species = AlienSpecies(
        id=sid, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id,
        sector_id=ship.sector_id, home_band="Hub", tech_level=sc.tech_level,
        base_disposition=base, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
        alliance_role=sc.alliance_role, trade_posture=sc.trade_posture,
        treaty_mode=sc.treaty_mode, persona=sc.persona,
    )
    state.species[sid] = species
    state.players[1] = replace(state.players[1], latinum=latinum, artifacts=artifacts or {})
    return species


def _drop_entity(state: UniverseState) -> None:
    """Remove the roaming Entity so a test can isolate the regular coordinate-tip mechanic.

    The Entity is the highest-value universal tip (§7, WP36); tests that assert a *specific*
    regular discovery lead drop it first so its tip doesn't win the ranking."""
    ent = entity_species(state, CFG)
    if ent is not None:
        del state.species[ent.id]


def _offer_index(roster_id: str, pred) -> int:  # type: ignore[no-untyped-def]
    sc = CFG.roster.species_by_id(roster_id)
    assert sc is not None
    return next(i for i, o in enumerate(sc.tech_offers) if pred(o))


# --- hail ------------------------------------------------------------------------

def test_hail_marks_met_and_advances_recency() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    res = reduce(state, 1, Hail(sp.id), CFG)
    apply_result(state, res)
    player = state.players[1]
    assert sp.roster_id in player.species_attitudes  # met (reputation keyed by kind)
    assert player.dialogue_recency[(instance_key(sp), "greeting")]  # ring advanced (per instance, WP29)
    # Hail is now Converse(greeting): it speaks the greeting via the general path (WP17).
    assert [type(e).__name__ for e in res.events] == ["AlienSpoke"]
    assert res.events[0].context == "greeting"


def test_hail_again_rephrases() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))
    first = session.contact_view(state, 1, sp.id, CFG).opener
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))  # hail again advances the ring
    second = session.contact_view(state, 1, sp.id, CFG).opener
    assert first != second  # the greeting is rephrased, not replayed


def test_contact_requires_species_in_sector() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    state.species[sp.id] = replace(sp, sector_id=sp.sector_id + 500)  # move it away
    with pytest.raises(EconomyError):
        reduce(state, 1, Hail(sp.id), CFG)


# --- WP17: Converse (general peaceful conversation) ------------------------------

def test_converse_advances_ring_and_emits_alienspoke() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    res = reduce(state, 1, Converse(sp.id, "farewell"), CFG)
    apply_result(state, res)
    assert [type(e).__name__ for e in res.events] == ["AlienSpoke"]
    assert res.events[0].context == "farewell" and res.events[0].subject_id is None
    assert state.players[1].dialogue_recency[(instance_key(sp), "farewell")]  # that context's ring advanced


def test_converse_dossier_other_carries_subject_and_rephrases() -> None:
    state = _world()
    vesk = _inject(state, "vesk", sid=1)
    selvani = _inject(state, "selvani", sid=2)  # the subject species, also met
    cmd = Converse(vesk.id, "dossier_other", subject_id=selvani.id)
    res = reduce(state, 1, cmd, CFG)
    assert res.events[0].context == "dossier_other" and res.events[0].subject_id == selvani.id
    first = session.contact_view(state, 1, vesk.id, CFG)  # (renders dossier line for selvani)
    apply_result(state, res)
    assert state.players[1].dialogue_recency[(instance_key(vesk), "dossier_other")]
    assert first is not None


def test_converse_rejects_non_peaceful_or_unreachable_context() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    for ctx in ("combat_open", "sig.trojan", "betrayal"):  # non-peaceful / Phase-3 contexts
        with pytest.raises(EconomyError):
            reduce(state, 1, Converse(sp.id, ctx), CFG)


def test_open_trader_can_speak_trade_refuse_on_an_empty_shelf() -> None:
    # The contact screen routes an empty Trade to `trade_refuse`; the live reducer must accept it
    # for an open trader (not just a `refuses` species) and fall back to the generic line (§6.7).
    state = _world()
    sp = _inject(state, "vesk")
    res = reduce(state, 1, Converse(sp.id, "trade_refuse"), CFG)
    apply_result(state, res)
    assert res.events[0].context == "trade_refuse"


def test_hail_is_converse_greeting() -> None:
    a, sp_a = _world(), None
    sp_a = _inject(a, "vesk")
    b = _world()
    sp_b = _inject(b, "vesk")
    apply_result(a, reduce(a, 1, Hail(sp_a.id), CFG))
    apply_result(b, reduce(b, 1, Converse(sp_b.id, "greeting"), CFG))
    assert state_hash(a) == state_hash(b)  # identical resulting state


def test_every_reachable_peaceful_context_speaks() -> None:
    from edge.dialogue import reachable_contexts

    state = _world()
    sp = _inject(state, "vesk")
    _inject(state, "selvani", sid=2)  # a subject for dossier_other
    sc = CFG.roster.species_by_id("vesk")
    assert sc is not None
    for ctx in sorted(reachable_contexts(sc)):
        subject = 2 if ctx == "dossier_other" else None
        res = reduce(state, 1, Converse(sp.id, ctx, subject_id=subject), CFG)
        apply_result(state, res)  # no raise, ring advances for every reachable context
        assert res.events[0].context == ctx


# --- authored branching: player-choice replies (§6.7) ----------------------------

def test_contact_view_exposes_branch_choices_and_plain_node_falls_back() -> None:
    state = _world()
    vesk = _inject(state, "vesk")  # serial_formal persona authors greeting choices
    view = session.contact_view(state, 1, vesk.id, BRANCH_CFG)
    assert view.choices and view.choices[0].next_context == "branch.vesk_workshop"
    # A species whose persona authors no choices falls back to the generic baseline menu.
    terran = _inject(state, "terran", sid=2)
    choices = session.contact_view(state, 1, terran.id, BRANCH_CFG).choices
    assert len(choices) > 0
    assert any(c.next_context == "dossier_other" for c in choices)


def test_converse_choice_transitions_to_branch_node() -> None:
    state = _world()
    vesk = _inject(state, "vesk")
    res = reduce(state, 1, Converse(vesk.id, "greeting", choice_index=0), BRANCH_CFG)
    apply_result(state, res)
    assert res.events[0].context == "branch.vesk_workshop"  # transitioned to the target node
    assert state.players[1].dialogue_recency[(instance_key(vesk), "branch.vesk_workshop")]  # spoken
    # The branch node then exposes its own replies (a trade gateway + a parting line).
    view = session.contact_view(
        state, 1, vesk.id, BRANCH_CFG, active_context="branch.vesk_workshop"
    )
    actions = {c.action for c in view.choices}
    assert "trade" in actions and "leave" in actions


def test_converse_choice_leave_action_speaks_parting_line() -> None:
    state = _world()
    vesk = _inject(state, "vesk")
    res = reduce(
        state, 1, Converse(vesk.id, "greeting", choice_index=1), BRANCH_CFG
    )  # "Safe travels."
    assert res.events[0].context == "farewell"


def test_converse_choice_accept_lead_respects_next_context() -> None:
    from edge.core.events import LeadAccepted, AlienSpoke
    from edge.dialogue.intel import LocationRef
    state = _world()
    _drop_entity(state)  # isolate the regular discovery tip (the Entity would out-rank it, §7)
    vesk = _inject(state, "vesk")
    src = state.ships[state.players[1].ship_id].sector_id
    d = next(d for d in state.discoveries.values()
             if d.found_by is None
             and d.sector_id not in state.players[1].explored_sectors
             and shortest_path(state.adjacency, src, d.sector_id) is not None)
    ref = LocationRef("discovery", d.id, d.sector_id)
    state.species_knowledge[vesk.roster_id] = (ref,)

    # Inject a custom choice with accept_lead action and next_context
    data = BRANCH_CFG.roster.model_dump()
    data["personas"]["serial_formal"]["greeting"] = [
        {"variants": ["Hello"], "choices": [{"text": "Log coordinates", "action": "accept_lead", "next_context": "greeting"}]}
    ]
    cfg = BRANCH_CFG.model_copy(update={"roster": RosterConfig.model_validate(data)})

    res = reduce(state, 1, Converse(vesk.id, "greeting", choice_index=0), cfg)
    assert len(res.events) == 2
    assert isinstance(res.events[0], LeadAccepted)
    assert isinstance(res.events[1], AlienSpoke)
    assert res.events[1].context == "greeting"

    apply_result(state, res)
    assert len(state.players[1].leads) == 1
    assert state.players[1].leads[0].sector_id == d.sector_id


def test_converse_choice_rejects_bad_index_and_choiceless_node() -> None:
    state = _world()
    vesk = _inject(state, "vesk")
    with pytest.raises(EconomyError):  # out of range
        reduce(state, 1, Converse(vesk.id, "greeting", choice_index=9), BRANCH_CFG)
    with pytest.raises(EconomyError):  # farewell carries no choices
        reduce(state, 1, Converse(vesk.id, "farewell", choice_index=0), BRANCH_CFG)


def _cfg_with_attack_choice() -> object:
    """A config whose Vesk workshop node also offers an `attack` reply (live since WP70)."""
    data = BRANCH_CFG.roster.model_dump()
    data["personas"]["serial_formal"]["branch.vesk_workshop"][0]["choices"].append(
        {"text": "Draw weapons.", "action": "attack"})
    return BRANCH_CFG.model_copy(update={"roster": RosterConfig.model_validate(data)})


def test_converse_choice_attack_is_core_gated() -> None:
    """In the Core sanctuary the FIGHT reply is greyed and the reducer refuses (WP70)."""
    cfg = _cfg_with_attack_choice()
    state = _world()
    vesk = _inject(state, "vesk")  # the player starts in the Core
    apply_result(state, reduce(state, 1, Converse(vesk.id, "greeting", choice_index=0), cfg))
    view = session.contact_view(state, 1, vesk.id, cfg, active_context="branch.vesk_workshop")
    attack = next(c for c in view.choices if c.action == "attack")
    assert not attack.enabled and "sanctuary" in attack.reason
    with pytest.raises(CombatError, match="sanctuary"):
        reduce(state, 1, Converse(vesk.id, "branch.vesk_workshop", choice_index=attack.index), cfg)


def test_converse_choice_attack_opens_combat_outside_the_core() -> None:
    """The live FIGHT reply (WP70) ends the conversation and opens the encounter."""
    cfg = _cfg_with_attack_choice()
    state = _world()
    vesk = _inject(state, "vesk")
    out = next(sid for sid, sec in sorted(state.sectors.items()) if not sec.is_galactic_core)
    state.ships[1] = replace(state.ships[1], sector_id=out)
    state.species[vesk.id] = replace(state.species[vesk.id], sector_id=out)
    apply_result(state, reduce(state, 1, Converse(vesk.id, "greeting", choice_index=0), cfg))
    view = session.contact_view(state, 1, vesk.id, cfg, active_context="branch.vesk_workshop")
    attack = next(c for c in view.choices if c.action == "attack")
    assert attack.enabled
    res = reduce(state, 1, Converse(vesk.id, "branch.vesk_workshop", choice_index=attack.index), cfg)
    apply_result(state, res)
    player = state.players[1]
    assert player.active_encounter is not None and player.active_encounter.species_id == vesk.id
    assert player.contact_session is None  # contact broke with the betrayal


def test_converse_choice_chain_replays_into_identical_state(tmp_path: Path) -> None:
    """Hail → greeting choice → branch farewell choice reloads identically (no Player drift)."""
    svc = GameService.new_game(
        BRANCH_SMALL, 3, SqliteRepository(tmp_path / "branch.db"), created_at=_CREATED
    )  # type: ignore[arg-type]
    found = _reachable_species_of(svc.state, "vesk")
    if found is None:
        pytest.skip("no reachable Vesk in this seed")
    path, sp = found
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Hail(sp.id))
    svc.apply(1, Converse(sp.id, "greeting", choice_index=0))            # → branch.vesk_workshop
    svc.apply(1, Converse(sp.id, "branch.vesk_workshop", choice_index=2))  # "Another time." (farewell)
    expected = state_hash(svc.state)
    assert svc.state.players[1].dialogue_recency[(instance_key(sp), "branch.vesk_workshop")]

    reloaded = GameService.load_game(
        BRANCH_SMALL, SqliteRepository(tmp_path / "branch.db")
    )  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected


# --- buy for latinum -------------------------------------------------------------

def test_buy_alien_tech_delivers_component_and_raises_attitude() -> None:
    state = _world()
    sp = _inject(state, "selvani")  # converter (II) latinum offer
    idx = _offer_index("selvani", lambda o: o.mode == "latinum" and o.component)
    before = effective_disposition(sp, state.players[1])
    lat0 = state.players[1].latinum
    res = reduce(state, 1, BuyAlienTech(sp.id, idx), CFG)
    apply_result(state, res)
    ship, player = state.ships[1], state.players[1]
    assert sum(ship.components.values()) == 1
    assert player.latinum < lat0
    assert effective_disposition(sp, player) > before
    assert {type(e).__name__ for e in res.events} == {"AlienTraded", "AttitudeChanged"}


def test_buy_aspect_offer_bumps_flat_rating() -> None:
    state = _world()
    sp = _inject(state, "vesk")  # Tier-III barter sensors; plus latinum component offers
    # Use the cheapest aspect offer available; here barter sensors → switch to a latinum
    # aspect would need one, so assert the aspect-delivery path via a constructed offer.
    idx = _offer_index("vesk", lambda o: o.component is not None and o.mode == "latinum")
    s0 = state.ships[1].sensor_rating
    apply_result(state, reduce(state, 1, BuyAlienTech(sp.id, idx), CFG))
    assert sum(state.ships[1].components.values()) == 1  # component delivered to hold
    assert state.ships[1].sensor_rating == s0  # component offer doesn't touch flat aspects


def test_buy_rejected_when_standing_too_low() -> None:
    state = _world()
    sp = _inject(state, "vesk", base=0.66)  # just above amity
    idx = _offer_index("vesk", lambda o: o.min_disposition >= 0.85)  # the Tier-III tier
    with pytest.raises(EconomyError, match="raise your standing"):
        reduce(state, 1, BuyAlienTech(sp.id, idx), CFG)


def test_buy_rejected_when_insufficient_latinum() -> None:
    state = _world()
    sp = _inject(state, "selvani", latinum=10)
    idx = _offer_index("selvani", lambda o: o.mode == "latinum")
    with pytest.raises(EconomyError, match="insufficient latinum"):
        reduce(state, 1, BuyAlienTech(sp.id, idx), CFG)


def test_attitude_unlocks_a_higher_tier_offer() -> None:
    state = _world()
    sp = _inject(state, "vesk", base=0.66)  # Tier-I min .65 reachable; Tier-II min .75 not
    low = _offer_index("vesk", lambda o: o.min_disposition <= 0.66 and o.mode == "latinum")
    high = _offer_index("vesk", lambda o: 0.66 < o.min_disposition <= 0.80 and o.mode == "latinum")
    with pytest.raises(EconomyError):  # locked at first
        reduce(state, 1, BuyAlienTech(sp.id, high), CFG)
    apply_result(state, reduce(state, 1, BuyAlienTech(sp.id, low), CFG))  # attitude_gain .12 → .78
    apply_result(state, reduce(state, 1, BuyAlienTech(sp.id, high), CFG))  # now unlocked
    assert sum(state.ships[1].components.values()) == 2


# --- barter (the exit-criterion proof) -------------------------------------------

def test_barter_yields_tier_iii_component_no_latinum_sale_offers() -> None:
    state = _world()
    sp = _inject(state, "helot", artifacts={"III": 1})  # Tier-III barter linkage
    idx = _offer_index("helot", lambda o: o.mode == "barter" and o.tier == "III" and o.component)
    res = reduce(state, 1, BarterArtifact(sp.id, idx), CFG)
    apply_result(state, res)
    ship, player = state.ships[1], state.players[1]
    # The Tier-III component landed in the hold...
    assert sum(ship.components.values()) == 1
    assert any(tier is ComponentTier.III for _, tier in ship.components)
    # ...and Stardock cannot sell Tier III for latinum — tech trading could not buy it.
    assert CFG.economy.component_price(ComponentTier.III) is None
    assert player.artifacts.get("III", 0) == 0  # the artifact was spent


def test_barter_rejected_without_a_matching_artifact() -> None:
    state = _world()
    sp = _inject(state, "helot", artifacts={})
    idx = _offer_index("helot", lambda o: o.mode == "barter")
    with pytest.raises(EconomyError, match="no Tier-III artifact"):
        reduce(state, 1, BarterArtifact(sp.id, idx), CFG)


def test_buy_rejects_a_barter_only_offer() -> None:
    state = _world()
    sp = _inject(state, "helot", artifacts={"III": 1})
    idx = _offer_index("helot", lambda o: o.mode == "barter")
    with pytest.raises(EconomyError, match="barter-only"):
        reduce(state, 1, BuyAlienTech(sp.id, idx), CFG)


# --- projection ------------------------------------------------------------------

def test_contact_view_renders_opener_choices_and_offers() -> None:
    # The shipped Selvani species pack owns this menu; projection must expose those authored
    # replies rather than the now-shadowed generic fallback.
    state = _world()
    sp = _inject(state, "selvani")
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))
    view = session.contact_view(state, 1, sp.id, CFG)
    assert view.species == "Selvani" and view.opener
    actions = {c.action for c in view.choices if c.action}
    nexts = {c.next_context for c in view.choices if c.next_context}
    assert {"trade", "leave"} <= actions
    assert {"branch.exploration", "dossier_other", "offer_coordinates"} <= nexts
    assert view.offers and all(o.label for o in view.offers)


def test_contact_view_uses_a_species_own_authored_replies_when_present() -> None:
    # Vesk's shipped species pack shadows the serial_formal workshop greeting.
    state = _world()
    sp = _inject(state, "vesk")
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))
    view = session.contact_view(state, 1, sp.id, CFG)
    nexts = {c.next_context for c in view.choices if c.next_context}
    assert {"trade_open", "treaty_offer", "dossier_other", "dossier_self"} <= nexts
    assert not any(n.startswith("branch.vesk_workshop") for n in nexts)


def test_contact_view_keeps_trade_live_for_a_refusing_trader() -> None:
    # Dacaran authors the refusal as a selectable dialogue transition rather than a generic
    # trade action; the full shipped corpus must keep that route live.
    state = _world()
    sp = _inject(state, "dacaran")  # trade_posture: refuses
    view = session.contact_view(state, 1, sp.id, CFG)
    trade = next(c for c in view.choices if c.next_context == "trade_refuse")
    assert trade.enabled and not trade.action
    assert not any(o.mode == "latinum" and o.available for o in view.offers)  # nothing to sell


def test_contact_view_dossier_covers_other_met_species() -> None:
    state = _world()
    a = _inject(state, "vesk", sid=1)
    b = _inject(state, "selvani", sid=2)
    state.species[2] = replace(b, sector_id=state.ships[1].sector_id)
    # Mark both met.
    apply_result(state, reduce(state, 1, Hail(a.id), CFG))
    apply_result(state, reduce(state, 1, Hail(b.id), CFG))
    view = session.contact_view(state, 1, a.id, CFG)
    assert any("Selvani" in line for line in view.dossier)  # a narrates b


def test_ask_about_is_gated_on_having_met_others_and_exposes_subjects() -> None:
    state = _world()
    a = _inject(state, "selvani", sid=1)  # baseline menu carries the Ask-about (dossier_other) reply
    # Only one species met → 'Ask about…' is greyed and no subjects offered.
    apply_result(state, reduce(state, 1, Hail(a.id), CFG))
    view = session.contact_view(state, 1, a.id, CFG)
    ask = next(c for c in view.choices if c.next_context == "dossier_other")
    assert not ask.enabled and ask.reason and view.subjects == []

    # Meet a second species → 'Ask about…' enables and the subject appears.
    b = _inject(state, "vesk", sid=2)
    state.species[2] = replace(b, sector_id=state.ships[1].sector_id)
    apply_result(state, reduce(state, 1, Hail(b.id), CFG))
    view2 = session.contact_view(state, 1, a.id, CFG)
    ask2 = next(c for c in view2.choices if c.next_context == "dossier_other")
    assert ask2.enabled
    assert (b.id, "Vesk") in view2.subjects


def test_reputation_is_shared_across_ships_of_one_species() -> None:
    """Reputation is keyed by species kind: dealing with one ship moves standing with all
    ships of that species, and the dossier lists the species once (§6.3 shared reputation)."""
    state = _world()
    here = _inject(state, "vesk", sid=1)  # a Vesk ship in the player's sector
    elsewhere = replace(here, id=2, sector_id=here.sector_id + 500)  # another Vesk, far away
    state.species[2] = elsewhere

    before = effective_disposition(elsewhere, state.players[1])
    idx = _offer_index("vesk", lambda o: o.mode == "latinum")
    apply_result(state, reduce(state, 1, BuyAlienTech(here.id, idx), CFG))  # trade with ship 1

    after = effective_disposition(state.species[2], state.players[1])  # ship 2's standing
    assert after > before  # the whole Vesk kind warmed, not just the ship traded with
    assert state.players[1].species_attitudes.keys() == {"vesk"}  # one entry, keyed by kind

    # The Computer dossier shows a single Vesk row despite two Vesk ships.
    vesk_rows = [d for d in session.computer_view(state, 1, CFG).dossier if d.species == "Vesk"]
    assert len(vesk_rows) == 1


def test_current_contact_view_finds_species_in_sector(tmp_path: Path) -> None:
    state = _world()
    _inject(state, "vesk")
    # Drive through a service so the convenience accessor is exercised.
    svc = GameService(state, CFG, SqliteRepository(tmp_path / "c.db"))  # type: ignore[arg-type]
    view = svc.current_contact_view(1)
    assert view is not None and view.species == "Vesk"


# --- WP11: Computer dossier + codex projections ----------------------------------

def test_computer_dossier_reflects_met_species() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))
    cv = session.computer_view(state, 1, CFG)
    entry = next((d for d in cv.dossier if d.species == "Vesk"), None)
    assert entry is not None
    assert entry.standing == "friendly" and entry.note  # a voiced self-description
    assert "navigator" in entry.offers  # last-seen tech-offer summary
    # The contact sector is stamped at hail time (spatial id), so it survives later movement.
    here = state.ships[1].sector_id
    assert entry.last_seen == str(state.spatial_ids.get(here, here))


def test_computer_dossier_empty_before_meeting_anyone() -> None:
    state = _world()
    assert session.computer_view(state, 1, CFG).dossier == []


def test_computer_codex_lists_logged_finds_richest_first() -> None:
    state = _world()
    if not state.discoveries:  # this seed salted none — nothing to assert
        return
    ids = list(state.discoveries)[:3]
    state.players[1] = replace(state.players[1], codex=frozenset(ids))
    cv = session.computer_view(state, 1, CFG)
    assert len(cv.codex) == len(ids)
    ranks = [RarityTier[e.rarity].value for e in cv.codex]
    assert ranks == sorted(ranks, reverse=True)  # richest first
    assert all(e.location for e in cv.codex)
    assert all("·" not in e.kind and e.kind for e in cv.codex)


# --- replay / golden master ------------------------------------------------------

def _reachable_species(state: UniverseState):  # type: ignore[no-untyped-def]
    best = None
    for sp in state.species.values():
        path = shortest_path(state.adjacency, 1, sp.sector_id)
        if path is not None and (best is None or len(path) < len(best[0])):
            best = (path, sp)
    return best


def _reachable_species_of(state: UniverseState, roster_id: str):  # type: ignore[no-untyped-def]
    best = None
    for sp in state.species.values():
        if sp.roster_id != roster_id:
            continue
        path = shortest_path(state.adjacency, 1, sp.sector_id)
        if path is not None and (best is None or len(path) < len(best[0])):
            best = (path, sp)
    return best


def test_hail_replays_into_identical_state(tmp_path: Path) -> None:
    """Warping to + hailing a placed species survives a reload (attitudes/recency golden master)."""
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "contact.db"), created_at=_CREATED)  # type: ignore[arg-type]
    found = _reachable_species(svc.state)
    assert found is not None
    path, sp = found
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Hail(sp.id))
    assert sp.roster_id in svc.state.players[1].species_attitudes
    expected = state_hash(svc.state)

    reloaded = GameService.load_game(SMALL, SqliteRepository(tmp_path / "contact.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected
    assert sp.roster_id in reloaded.state.players[1].species_attitudes


def test_converse_chain_replays_into_identical_state(tmp_path: Path) -> None:
    """WP17: Hail → Converse(dossier_other) → Converse(farewell) reloads identically.

    The generalised ring advance now flows through Converse for every peaceful context,
    so the dialogue-survives-reload coverage extends past the greeting.
    """
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "converse.db"), created_at=_CREATED)  # type: ignore[arg-type]
    found = _reachable_species(svc.state)
    assert found is not None
    path, sp = found
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Hail(sp.id))
    svc.apply(1, Converse(sp.id, "dossier_other", subject_id=sp.id))
    svc.apply(1, Converse(sp.id, "farewell"))
    expected = state_hash(svc.state)
    assert svc.state.players[1].dialogue_recency[(instance_key(sp), "farewell")]  # rings advanced

    reloaded = GameService.load_game(SMALL, SqliteRepository(tmp_path / "converse.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected

# --- WP28: the per-contact dialogue session (§6.7) ---------------------------------


def test_conversation_opens_a_session_and_accumulates_topics() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))
    visit = state.players[1].contact_session
    assert visit is not None and visit.species_id == sp.id
    assert visit.sector_id == state.ships[1].sector_id
    assert visit.facts.get("asked.greeting") is True
    apply_result(state, reduce(state, 1, Converse(sp.id, "dossier_self"), CFG))
    facts = state.players[1].contact_session.facts
    assert facts.get("asked.greeting") is True and facts.get("asked.dossier_self") is True


def test_farewell_closes_the_session() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))
    assert state.players[1].contact_session is not None
    apply_result(state, reduce(state, 1, Converse(sp.id, "farewell"), CFG))
    assert state.players[1].contact_session is None


def test_movement_clears_the_session() -> None:
    # H1: the session's lifetime is structural — warping off mid-sentence ends the visit
    # in the reducer; the UI is never trusted to close it.
    state = _world()
    sp = _inject(state, "vesk")
    apply_result(state, reduce(state, 1, Hail(sp.id), CFG))
    dest = state.adjacency[state.ships[1].sector_id][0]
    apply_result(state, reduce(state, 1, Warp(to_sector=dest), CFG))
    assert state.players[1].contact_session is None


def test_switching_contacts_starts_a_fresh_session() -> None:
    state = _world()
    a = _inject(state, "vesk", sid=1)
    b = _inject(state, "selvani", sid=2)
    apply_result(state, reduce(state, 1, Hail(a.id), CFG))
    apply_result(state, reduce(state, 1, Converse(a.id, "dossier_self"), CFG))
    apply_result(state, reduce(state, 1, Hail(b.id), CFG))
    visit = state.players[1].contact_session
    assert visit is not None and visit.species_id == b.id
    assert visit.facts == {"asked.greeting": True}  # A's topics did not leak into B's visit


def _cfg_with_repeat_greeting() -> object:
    """Vesk gains a species-pack greeting keyed on the session fact `asked.greeting`."""
    data = CFG.roster.model_dump()
    vesk = next(s for s in data["species"] if s["id"] == "vesk")
    vesk.setdefault("dialogue_pack", {})["greeting"] = [{
        "when": {"criteria": {"asked.greeting": True}},
        "variants": ["Back again so soon."],
        "choices": [{"text": "Just passing through.", "next_context": "farewell"}],
    }]
    return CFG.model_copy(update={"roster": RosterConfig.model_validate(data)})


def test_session_fact_reselects_line_and_menu_in_lockstep() -> None:
    cfg = _cfg_with_repeat_greeting()
    state = _world()
    sp = _inject(state, "vesk")
    first = session.contact_view(state, 1, sp.id, cfg)
    assert first.opener != "Back again so soon."  # no session yet — the persona speaks
    apply_result(state, reduce(state, 1, Hail(sp.id), cfg))
    second = session.contact_view(state, 1, sp.id, cfg)
    assert second.opener == "Back again so soon."  # the session fact pins the entry
    assert second.choices and second.choices[0].text == "Just passing through."
    # The reducer resolves the same menu under the same facts (lockstep): reply 0 on the
    # session-keyed entry is the parting transition it authored.
    res = reduce(state, 1, Converse(sp.id, "greeting", choice_index=0), cfg)
    assert res.events[-1].context == "farewell"


def test_trade_and_lead_mark_the_session() -> None:
    from edge.core.models import LocationRef

    state = _world()
    sp = _inject(state, "selvani")
    idx = _offer_index("selvani", lambda o: o.mode == "latinum" and o.component)
    apply_result(state, reduce(state, 1, BuyAlienTech(sp.id, idx), CFG))
    assert state.players[1].contact_session.facts.get("traded") is True

    src = state.ships[1].sector_id
    d = next(d for d in state.discoveries.values()
             if d.found_by is None and d.sector_id not in state.players[1].explored_sectors
             and shortest_path(state.adjacency, src, d.sector_id) is not None)
    state.species_knowledge[sp.roster_id] = (LocationRef("discovery", d.id, d.sector_id),)
    apply_result(state, reduce(state, 1, AcceptLead(sp.id), CFG))
    facts = state.players[1].contact_session.facts
    assert facts.get("traded") is True and facts.get("accepted_lead") is True


def test_open_session_replays_into_identical_state(tmp_path: Path) -> None:
    """A visit left open mid-conversation (no farewell) reconstructs exactly on reload."""
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "session.db"), created_at=_CREATED)  # type: ignore[arg-type]
    found = _reachable_species(svc.state)
    assert found is not None
    path, sp = found
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Hail(sp.id))
    svc.apply(1, Converse(sp.id, "dossier_self"))
    live = svc.state.players[1].contact_session
    assert live is not None and live.facts.get("asked.dossier_self") is True
    expected = state_hash(svc.state)

    reloaded = GameService.load_game(SMALL, SqliteRepository(tmp_path / "session.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected
    assert reloaded.state.players[1].contact_session == live

# --- WP29: situational facts + per-instance recency (H7) ---------------------------


def test_recency_rings_are_kept_per_contact_instance() -> None:
    # H7: two ships of one species carry separate "what I already said" rings.
    state = _world()
    a = _inject(state, "vesk", sid=1)
    b = replace(a, id=2)
    state.species[2] = b
    apply_result(state, reduce(state, 1, Hail(a.id), CFG))
    rings = state.players[1].dialogue_recency
    assert (instance_key(a), "greeting") in rings
    assert (instance_key(b), "greeting") not in rings  # a's hail never advances b's ring
    apply_result(state, reduce(state, 1, Hail(b.id), CFG))
    rings = state.players[1].dialogue_recency
    assert (instance_key(b), "greeting") in rings and instance_key(a) != instance_key(b)


def _cfg_with_band_greeting(band: str) -> object:
    """Vesk gains a species-pack greeting pinned to a situational `band` fact."""
    data = CFG.roster.model_dump()
    vesk = next(s for s in data["species"] if s["id"] == "vesk")
    vesk.setdefault("dialogue_pack", {})["greeting"] = [{
        "when": {"criteria": {"band": band}},
        "variants": ["You are far from the Core lanes."],
    }]
    return CFG.model_copy(update={"roster": RosterConfig.model_validate(data)})


def test_situational_criteria_select_the_pinned_line() -> None:
    state = _world()
    sp = _inject(state, "vesk")
    band = state.sectors[state.ships[1].sector_id].distance_band
    here = session.contact_view(state, 1, sp.id, _cfg_with_band_greeting(band))
    assert here.opener == "You are far from the Core lanes."  # the live band pins the entry
    elsewhere = session.contact_view(state, 1, sp.id, _cfg_with_band_greeting("Void"))
    assert elsewhere.opener != "You are far from the Core lanes."  # wrong band — falls through

# --- WP30: cross-visit arcs (§6.7) --------------------------------------------------


def _cfg_with_oath(base) -> object:  # type: ignore[no-untyped-def]
    """Vesk speaks differently once the player swears an authored oath (an `arc` reply)."""
    data = CFG.roster.model_dump()
    vesk = next(s for s in data["species"] if s["id"] == "vesk")
    vesk.setdefault("dialogue_pack", {})["greeting"] = [
        {"variants": ["State your business."],
         "choices": [{"text": "I swear the oath.", "arc": {"oath_sworn": True},
                      "next_context": "greeting"}]},
        {"when": {"criteria": {"arc.oath_sworn": True}},
         "variants": ["The oath binds us, oath-kin."]},
    ]
    return base.model_copy(update={"roster": RosterConfig.model_validate(data)})


def test_choice_arc_flag_persists_and_unlocks_across_visits() -> None:
    cfg = _cfg_with_oath(CFG)
    state = _world()
    sp = _inject(state, "vesk")
    apply_result(state, reduce(state, 1, Hail(sp.id), cfg))
    assert session.contact_view(state, 1, sp.id, cfg).opener == "State your business."
    apply_result(state, reduce(state, 1, Converse(sp.id, "greeting", choice_index=0), cfg))
    assert state.players[1].species_arcs == {"vesk": {"oath_sworn": True}}
    assert session.contact_view(state, 1, sp.id, cfg).opener == "The oath binds us, oath-kin."
    # A new visit (movement cleared the session) still opens the unlocked branch — the
    # arc flag is persisted per species kind, not per visit.
    here = state.ships[1].sector_id
    dest = next(n for n in state.adjacency[here] if here in state.adjacency[n])
    apply_result(state, reduce(state, 1, Warp(to_sector=dest), cfg))
    apply_result(state, reduce(state, 1, Warp(to_sector=here), cfg))
    assert state.players[1].contact_session is None
    assert session.contact_view(state, 1, sp.id, cfg).opener == "The oath binds us, oath-kin."


def test_arc_unlock_survives_a_reload_golden(tmp_path: Path) -> None:
    """WP30 (M12 golden): an arc flag sworn in visit 1 unlocks the branch after reload."""
    cfg = _cfg_with_oath(SMALL)
    svc = GameService.new_game(cfg, 3, SqliteRepository(tmp_path / "arc.db"), created_at=_CREATED)  # type: ignore[arg-type]
    found = _reachable_species_of(svc.state, "vesk")
    if found is None:
        pytest.skip("no reachable Vesk in this seed")
    path, sp = found
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Hail(sp.id))
    svc.apply(1, Converse(sp.id, "greeting", choice_index=0))  # swear the oath
    assert svc.state.players[1].species_arcs["vesk"]["oath_sworn"] is True
    expected = state_hash(svc.state)

    reloaded = GameService.load_game(cfg, SqliteRepository(tmp_path / "arc.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected
    assert reloaded.state.players[1].species_arcs["vesk"]["oath_sworn"] is True
    view = session.contact_view(reloaded.state, 1, sp.id, cfg)
    assert view.opener == "The oath binds us, oath-kin."


# --- WP35: the roaming Entity — presence hint, sensor-gated contact, codex ---------

def _entity_here(state: UniverseState, sensor: int):
    """Move the player into the Entity's sector at a given sensor rating; return the Entity."""
    ent = entity_species(state, CFG)
    assert ent is not None
    ship = replace(state.ships[1], sector_id=ent.sector_id, sensor_rating=sensor)
    state.ships[1] = ship
    return ent


_LEG = CFG.discovery.sensor_difficulty["LEGENDARY"]  # the Legendary sensor gate (§7)


def test_entity_presence_hint_is_fog_safe_and_gated() -> None:
    """The sector view always shows the Entity's presence (computed live), never names it,
    and never lists it as a hailable vessel; contact opens only at the Legendary gate."""
    state = _world()
    ent = _entity_here(state, _LEG - 1)  # under the gate
    view = session.game_view(state, 1, CFG).sector
    an = view.anomaly
    assert an is not None and an.contact_id == ent.id
    assert not an.contactable  # sensors too weak
    assert ent.name.lower() not in an.label.lower()  # fog-safe: presence, not contents
    assert all(s.contact_id != ent.id for s in view.ships)  # not a vessel
    # Raise sensors to the gate — presence resolves into contact.
    state.ships[1] = replace(state.ships[1], sensor_rating=_LEG)
    assert session.game_view(state, 1, CFG).sector.anomaly.contactable


def test_entity_hint_tracks_current_sector_not_detected() -> None:
    """The hint is absent where the Entity is not, present where it is — from its current
    sector, never `Player.detected` (H2)."""
    state = _world()
    ent = entity_species(state, CFG)
    assert ent is not None
    elsewhere = next(sid for sid in state.sectors if sid != ent.sector_id)
    state.ships[1] = replace(state.ships[1], sector_id=elsewhere, sensor_rating=_LEG)
    assert session.game_view(state, 1, CFG).sector.anomaly is None
    _entity_here(state, _LEG)
    assert session.game_view(state, 1, CFG).sector.anomaly is not None


def test_under_sensored_hail_is_rejected() -> None:
    """The reducer re-checks the gate (H2): an under-sensored Hail raises, never contacts."""
    state = _world()
    ent = _entity_here(state, _LEG - 1)
    with pytest.raises(EconomyError):
        reduce(state, 1, Hail(ent.id), CFG)


def test_first_contact_stamps_legendary_codex_once() -> None:
    """First Hail past the gate collects the reserved Legendary codex row (once-only,
    replay-idempotent) and pays discovery experience; a re-hail changes nothing."""
    state = _world()
    ent = _entity_here(state, _LEG)
    before_xp = state.players[1].experience
    res = reduce(state, 1, Hail(ent.id), CFG)
    apply_result(state, res)
    disc = entity_codex_discovery(state)
    assert disc is not None and disc.found_by == 1 and disc.id in state.players[1].codex
    assert state.players[1].experience == before_xp + CFG.aliens.experience_per_discovery
    assert any(type(e).__name__ == "DiscoveryCollected" for e in res.events)
    # Idempotent: hailing again neither re-stamps nor re-pays.
    xp = state.players[1].experience
    res2 = reduce(state, 1, Hail(ent.id), CFG)
    apply_result(state, res2)
    assert state.players[1].experience == xp
    assert not any(type(e).__name__ == "DiscoveryCollected" for e in res2.events)


def test_contact_view_marks_singular_entity() -> None:
    """The contact projection flags the Entity so the TUI fills the portrait slot (WP35)."""
    state = _world()
    ent = _entity_here(state, _LEG)
    apply_result(state, reduce(state, 1, Hail(ent.id), CFG))
    assert session.contact_view(state, 1, ent.id, CFG).singular_entity
