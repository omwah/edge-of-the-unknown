"""WP8 — config-driven dialogue (DESIGN §6.7, §13).

Covers the pure-core selector (fallback chain, no-repeat recency ring, placeholder
filling, standing/treaty matching), the per-species reachability helper, and the
dialogue-integrity validator (including the failure modes it must catch).
"""

from __future__ import annotations

import random

import pytest

from edge.config import load_default_config
from edge.core.config import DialogueLine, DialogueWhen, RosterConfig
from edge.dialogue import (
    ALLIED,
    FRIENDLY,
    HOSTILE,
    NEUTRAL,
    DialogueIntegrityError,
    reachable_contexts,
    select_entry,
    select_line,
    speak,
    standing_for,
    validate_dialogue,
)
from edge.core.models import AlienSpecies, ContactSession, Game, Player, UniverseState
from edge.dialogue import facts as dialogue_facts

CFG = load_default_config()


def _line(*variants: str, standing: str | None = None, treaty: bool | None = None,
          weight: int = 1) -> DialogueLine:
    return DialogueLine(variants=list(variants), weight=weight,
                        when=DialogueWhen(standing=standing, treaty=treaty))


# --- selection: fallback chain ---------------------------------------------------

def test_fallback_resolves_species_then_persona_then_generic() -> None:
    species = {"greeting": [_line("species greeting")]}
    persona = {"greeting": [_line("persona greeting")], "farewell": [_line("persona bye")]}
    generic = {"greeting": [_line("generic greeting")], "farewell": [_line("generic bye")],
               "refuel": [_line("generic refuel")]}
    chain = [species, persona, generic]
    rng = random.Random(0)
    assert select_line(chain, "greeting", standing=FRIENDLY, treaty=False, ctx={},
                       recency=(), rng=rng)[0] == "species greeting"  # species wins
    assert select_line(chain, "farewell", standing=FRIENDLY, treaty=False, ctx={},
                       recency=(), rng=rng)[0] == "persona bye"  # species lacks it
    assert select_line(chain, "refuel", standing=FRIENDLY, treaty=False, ctx={},
                       recency=(), rng=rng)[0] == "generic refuel"  # only generic has it


def test_fallback_when_higher_pack_has_key_but_no_matching_entry() -> None:
    # The species pack has the key but only a hostile-standing entry; a friendly
    # encounter must fall through to the generic catch-all rather than blank.
    species = {"greeting": [_line("only when hostile", standing=HOSTILE)]}
    generic = {"greeting": [_line("generic catch-all")]}
    text, _ = select_line([species, generic], "greeting", standing=FRIENDLY, treaty=False,
                          ctx={}, recency=(), rng=random.Random(1))
    assert text == "generic catch-all"


def test_unresolved_context_returns_empty() -> None:
    text, ring = select_line([{"greeting": [_line("hi")]}], "farewell", standing=FRIENDLY,
                             treaty=False, ctx={}, recency=(7,), rng=random.Random(2))
    assert text == "" and ring == (7,)  # recency untouched when nothing resolves


# --- selection: standing / treaty predicate --------------------------------------

def test_when_matches_standing_and_treaty() -> None:
    pack = {"greeting": [
        _line("allied line", standing=ALLIED),
        _line("treaty line", treaty=True),
        _line("default"),
    ]}
    rng = random.Random(3)
    assert select_line([pack], "greeting", standing=ALLIED, treaty=False, ctx={},
                       recency=(), rng=rng)[0] == "allied line"
    assert select_line([pack], "greeting", standing=NEUTRAL, treaty=True, ctx={},
                       recency=(), rng=rng)[0] == "treaty line"
    assert select_line([pack], "greeting", standing=NEUTRAL, treaty=False, ctx={},
                       recency=(), rng=rng)[0] == "default"


def test_general_criteria_facts_gate_and_score() -> None:
    # A line gated on a general fact (`has_intel_target`) only fires when the fact holds,
    # and — pinning more facts — beats a less-specific standing-only line (Ruskin scoring).
    pack = {"greeting": [
        DialogueLine(variants=["intel"],
                     when=DialogueWhen(standing=FRIENDLY, criteria={"has_intel_target": True})),
        _line("just friendly", standing=FRIENDLY),
        _line("default"),
    ]}
    rng = random.Random(11)
    # Fact present → the 2-criteria intel line wins over the 1-criteria friendly line.
    got, _ = select_line([pack], "greeting", standing=FRIENDLY, treaty=False, ctx={},
                         recency=(), rng=rng, facts={"has_intel_target": True})
    assert got == "intel"
    # Fact absent → the intel line can't match; the friendly line wins.
    got, _ = select_line([pack], "greeting", standing=FRIENDLY, treaty=False, ctx={},
                         recency=(), rng=rng, facts={"has_intel_target": False})
    assert got == "just friendly"
    # Neither standing matches → catch-all default.
    got, _ = select_line([pack], "greeting", standing=NEUTRAL, treaty=False, ctx={},
                         recency=(), rng=rng)
    assert got == "default"


def test_forward_compat_posture_stage_entries_are_skipped_in_phase2() -> None:
    pack = {"greeting": [
        DialogueLine(variants=["phase3"], when=DialogueWhen(posture="earn")),
        _line("phase2"),
    ]}
    text, _ = select_line([pack], "greeting", standing=FRIENDLY, treaty=False, ctx={},
                          recency=(), rng=random.Random(4))
    assert text == "phase2"


# --- selection: recency ring -----------------------------------------------------

def test_recency_ring_avoids_recent_variants() -> None:
    variants = [f"v{i}" for i in range(4)]
    chain = [{"greeting": [DialogueLine(variants=variants)]}]
    rng = random.Random(5)
    ring: tuple[int, ...] = ()
    picks: list[int] = []
    for _ in range(20):
        text, ring = select_line(chain, "greeting", standing=FRIENDLY, treaty=False,
                                 ctx={}, recency=ring, rng=rng, k=2)
        picks.append(variants.index(text))
        assert len(ring) <= 2
    # With K=2 and 4 variants, a pick never repeats either of the last two.
    for i in range(2, len(picks)):
        assert picks[i] not in (picks[i - 1], picks[i - 2])


def test_recency_falls_back_when_pool_smaller_than_ring() -> None:
    # Two variants, K=2: the ring can't exclude everything — selection still succeeds.
    chain = [{"greeting": [DialogueLine(variants=["a", "b"])]}]
    rng = random.Random(6)
    ring = (0, 1)
    text, _ = select_line(chain, "greeting", standing=FRIENDLY, treaty=False, ctx={},
                          recency=ring, rng=rng, k=2)
    assert text in {"a", "b"}


# --- selection: placeholders -----------------------------------------------------

def test_placeholders_fill_and_missing_render_empty() -> None:
    chain = [{"greeting": [DialogueLine(variants=["Hail {player} of {alliance}{missing}"])]}]
    text, _ = select_line(chain, "greeting", standing=FRIENDLY, treaty=False,
                          ctx={"player": "Cap", "alliance": "Fed"}, recency=(),
                          rng=random.Random(7))
    assert text == "Hail Cap of Fed"  # unknown {missing} renders empty, never crashes


# --- standing_for ----------------------------------------------------------------

def test_standing_for_buckets_and_allied_override() -> None:
    aliens = CFG.aliens  # hostility 0.35 / amity 0.65
    assert standing_for(0.9, allied=True, aliens=aliens) == ALLIED
    assert standing_for(0.9, allied=False, aliens=aliens) == FRIENDLY
    assert standing_for(0.5, allied=False, aliens=aliens) == NEUTRAL
    assert standing_for(0.1, allied=False, aliens=aliens) == HOSTILE


# --- reachable_contexts ----------------------------------------------------------

def test_reachable_contexts_reflects_params() -> None:
    vesk = CFG.roster.species_by_id("vesk")  # trade_posture open, treaty_mode open
    assert vesk is not None
    rc = reachable_contexts(vesk)
    # An open trader reaches both trade_open and trade_refuse — the latter for an empty shelf
    # (nothing affordable), routed to the generic catch-all (§6.7).
    assert "trade_open" in rc and "trade_refuse" in rc
    assert "greeting" in rc and "dossier_other" in rc

    dacaran = CFG.roster.species_by_id("dacaran")  # trade_posture refuses
    assert dacaran is not None
    assert "trade_refuse" in reachable_contexts(dacaran)
    assert "trade_open" not in reachable_contexts(dacaran)  # a refuser never opens trade

    stryx = CFG.roster.species_by_id("stryx")  # treaty_mode none
    assert stryx is not None
    assert not ({"treaty_offer", "treaty_grant"} & reachable_contexts(stryx))


# --- speak (end-to-end, deterministic) -------------------------------------------

def _species(roster_id: str) -> AlienSpecies:
    sc = CFG.roster.species_by_id(roster_id)
    assert sc is not None
    return AlienSpecies(
        id=1, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id,
        sector_id=11, home_band="Hub", tech_level=sc.tech_level,
        base_disposition=0.8, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
        persona=sc.persona,
    )


def test_speak_is_deterministic_and_voiced() -> None:
    sp = _species("vennrith")  # inverted_syntax persona
    player = Player(id=1, name="Cap", ship_id=1, latinum=0, alliance_id=1)
    a = speak(CFG.roster, sp, player, "greeting", aliens=CFG.aliens, rng=random.Random(42))
    b = speak(CFG.roster, sp, player, "greeting", aliens=CFG.aliens, rng=random.Random(42))
    assert a == b  # same seed → same line + ring
    assert "Vennrith" in a[0]
    # farewell isn't in the inverted_syntax pack → falls back to the generic voice.
    fare, _ = speak(CFG.roster, sp, player, "farewell", aliens=CFG.aliens, rng=random.Random(1))
    assert "Cap" in fare or "Vennrith" in fare


def test_speak_dossier_other_fills_subject() -> None:
    sp = _species("vesk")
    player = Player(id=1, name="Cap", ship_id=1, latinum=0, alliance_id=1)
    text, _ = speak(CFG.roster, sp, player, "dossier_other", aliens=CFG.aliens,
                    rng=random.Random(3), extra={"subject": "Quill"})
    assert "Quill" in text


# --- validate_dialogue: the default roster passes, mutants fail -------------------

def test_default_roster_dialogue_is_valid() -> None:
    validate_dialogue(CFG.roster)  # must not raise


def _mutated_roster(mutate) -> RosterConfig:  # type: ignore[no-untyped-def]
    data = CFG.roster.model_dump()
    mutate(data)
    return RosterConfig.model_validate(data)


def test_validate_requires_generic_persona() -> None:
    roster = _mutated_roster(lambda d: d["personas"].pop("generic"))
    with pytest.raises(DialogueIntegrityError, match="generic"):
        validate_dialogue(roster)


def test_validate_requires_catch_all_for_every_context() -> None:
    roster = _mutated_roster(lambda d: d["personas"]["generic"].pop("farewell"))
    with pytest.raises(DialogueIntegrityError, match="catch-all 'farewell'"):
        validate_dialogue(roster)


def test_validate_rejects_unknown_context_key() -> None:
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["personas"]["generic"]["not_a_context"] = [{"variants": ["x"]}]
    with pytest.raises(DialogueIntegrityError, match="unknown context key"):
        validate_dialogue(_mutated_roster(mutate))


def test_validate_rejects_unfillable_placeholder() -> None:
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["personas"]["generic"]["farewell"] = [{"variants": ["bye {nonsense}"]}]
    with pytest.raises(DialogueIntegrityError, match="unfillable placeholder"):
        validate_dialogue(_mutated_roster(mutate))


def test_validate_rejects_unknown_species_persona() -> None:
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["species"][0]["persona"] = "ghost_voice"
    with pytest.raises(DialogueIntegrityError, match="unknown persona"):
        validate_dialogue(_mutated_roster(mutate))


def test_validate_requires_dossier_other_subject() -> None:
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["personas"]["generic"]["dossier_other"] = [{"variants": ["I know them well."]}]
    with pytest.raises(DialogueIntegrityError, match="dossier_other"):
        validate_dialogue(_mutated_roster(mutate))


# --- authored branching (§6.7): select_entry + choice validation -----------------

def test_select_entry_returns_winning_entry_with_its_choices() -> None:
    from edge.core.config import DialogueChoice

    entry = DialogueLine(variants=["Hi {player}"],
                         choices=[DialogueChoice(text="Bye", action="leave")])
    got = select_entry([{"greeting": [entry]}], "greeting", standing=FRIENDLY, treaty=False,
                       rng=random.Random(0))
    assert got is not None and got.choices[0].action == "leave"


def test_validate_rejects_unknown_choice_action() -> None:
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["personas"]["generic"]["greeting"][0]["choices"] = [{"text": "x", "action": "explode"}]
    with pytest.raises(DialogueIntegrityError, match="choice action"):
        validate_dialogue(_mutated_roster(mutate))


def test_validate_rejects_choice_to_unknown_context() -> None:
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["personas"]["generic"]["greeting"][0]["choices"] = [
            {"text": "x", "next_context": "not_a_context"}]
    with pytest.raises(DialogueIntegrityError, match="targets unknown context"):
        validate_dialogue(_mutated_roster(mutate))


def test_validate_rejects_unfillable_choice_placeholder() -> None:
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["personas"]["generic"]["greeting"][0]["choices"] = [{"text": "buy {nonsense}"}]
    with pytest.raises(DialogueIntegrityError, match="unfillable placeholder"):
        validate_dialogue(_mutated_roster(mutate))


def test_validate_rejects_orphan_branch_node() -> None:
    # A `branch.*` node nothing targets is dead config — the validator must catch it.
    def mutate(d: dict) -> None:  # type: ignore[type-arg]
        d["personas"]["generic"]["branch.orphan"] = [{"variants": ["Nobody comes here, {player}."]}]
    with pytest.raises(DialogueIntegrityError, match="unreachable"):
        validate_dialogue(_mutated_roster(mutate))


# --- WP18: Federation humanoid_diplomat allied voice ---


def _terran_entity() -> AlienSpecies:
    return AlienSpecies(
        id=1, roster_id="terran", name="Terrans", archetype_id="humanoid_diplomat",
        sector_id=1, home_band="Hub", tech_level=8, base_disposition=1.0,
        disposition_center=1.0, disposition_variance=0.03, alliance_id=1,
        alliance_role="leader", persona="humanoid_diplomat")


def test_federation_member_greets_a_fellow_citizen_as_allied() -> None:
    roster = CFG.roster
    assert roster is not None
    terran = _terran_entity()
    member = Player(id=1, name="Cap", ship_id=1, latinum=0, alliance_id=1)  # fellow citizen
    outsider = Player(id=2, name="Cap", ship_id=1, latinum=0, alliance_id=None)

    allied_markers = ("stands with you", "fellow citizen", "friendly flag")

    member_lines = {speak(roster, terran, member, "greeting",
                          aliens=CFG.aliens, rng=random.Random(s))[0] for s in range(20)}
    outsider_lines = {speak(roster, terran, outsider, "greeting",
                            aliens=CFG.aliens, rng=random.Random(s))[0] for s in range(20)}

    def has_kin_line(lines: set[str]) -> bool:
        return any(any(m in line for m in allied_markers) for line in lines)

    # The allied 'fellow-citizen' branch fires for kin — and never for an outsider.
    assert has_kin_line(member_lines)
    assert not has_kin_line(outsider_lines)
    # The outsider still hears the warm generic peaceful opener.
    assert any("come in peace" in line or "understanding" in line for line in outsider_lines)

# --- WP28: shared fact assembly (edge.dialogue.facts) -----------------------------


def _bare_state() -> UniverseState:
    return UniverseState.new(Game(id=1, seed=0, config_version=3, created_at="t"))


def test_contact_facts_layer_session_then_extras() -> None:
    from dataclasses import replace

    sp = _species("vesk")
    visit = ContactSession(species_id=sp.id, sector_id=11,
                           facts={"asked.greeting": True, "traded": True})
    player = Player(id=1, name="Cap", ship_id=1, latinum=0, contact_session=visit)
    facts = dialogue_facts.contact_facts(
        _bare_state(), player, sp, roster=CFG.roster,
        extra={"has_intel_target": True, "traded": False})
    assert facts["asked.greeting"] is True
    assert facts["has_intel_target"] is True
    assert facts["traded"] is False  # the caller's extras win over the session layer
    # A session held for a different species instance contributes nothing (the
    # always-present WP30 callback layer remains, all false for a stranger).
    other = replace(sp, id=2)
    other_facts = dialogue_facts.contact_facts(_bare_state(), player, other, roster=CFG.roster)
    assert "asked.greeting" not in other_facts and "traded" not in other_facts
    assert other_facts["met_before"] is False


def test_ensure_session_and_notes_are_incremental() -> None:
    from dataclasses import replace

    sp = _species("vesk")
    player = Player(id=1, name="Cap", ship_id=1, latinum=0)
    fresh = dialogue_facts.ensure_session(player, sp, 11)
    assert fresh.species_id == sp.id and fresh.sector_id == 11 and not fresh.facts

    noted = dialogue_facts.note_topic(fresh, "greeting")
    assert noted.facts == {"asked.greeting": True}
    assert dialogue_facts.note_topic(noted, "greeting") is noted  # already recorded — no-op

    held = replace(player, contact_session=noted)
    assert dialogue_facts.ensure_session(held, sp, 11) is noted  # the visit continues
    assert not dialogue_facts.ensure_session(held, replace(sp, id=2), 11).facts  # a new visit


def test_session_fact_pins_the_more_specific_entry() -> None:
    # The selection-level proof: a session fact fed through `facts` lets an `asked.*`-keyed
    # entry outscore the plain line, exactly like any other criteria fact (§6.7).
    pack = {"greeting": [
        DialogueLine(variants=["Back again so soon."],
                     when=DialogueWhen(criteria={"asked.greeting": True})),
        _line("First contact."),
    ]}
    rng = random.Random(9)
    got, _ = select_line([pack], "greeting", standing=FRIENDLY, treaty=False, ctx={},
                         recency=(), rng=rng, facts={"asked.greeting": True})
    assert got == "Back again so soon."
    got, _ = select_line([pack], "greeting", standing=FRIENDLY, treaty=False, ctx={},
                         recency=(), rng=rng, facts={})
    assert got == "First contact."


# --- WP29: situational facts -------------------------------------------------------


def test_situational_facts_cover_the_vocabulary() -> None:
    from edge.core.enums import Commodity, DiscoveryKind, PayloadKind, RarityTier
    from edge.core.models import Discovery, DiscoveryPayload, LastCombat, Sector, Ship

    state = _bare_state()
    state.sectors[5] = Sector(id=5, region_id=1, warps_out=(), distance_band="Frontier")
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="S", owner_player_id=1,
                          sector_id=5, holds_total=10, cargo={Commodity.FUEL_ORE: 3},
                          hull_current=10, hull_max=100)
    player = Player(id=1, name="Cap", ship_id=1, latinum=0, turns_remaining=200,
                    last_combat=LastCombat(species="quill", outcome="fled", day=1))
    facts = dialogue_facts.situational_facts(state, player, CFG.roster)
    assert facts["band"] == "Frontier"
    assert facts["hull"] == "critical"  # 10% of hull_max
    assert facts["in_nebula"] is False and facts["wreck_here"] is False
    assert facts["low_turns"] is False
    assert facts["holds_empty"] is False and facts["holds_full"] is False
    assert facts["carrying"] == "fuel_ore"
    assert facts["just_fled_combat"] is True  # fled today (day 1)

    # A visible wreck in the sector flips `wreck_here`.
    state.discoveries[9] = Discovery(id=9, kind=DiscoveryKind.WRECK, rarity_tier=RarityTier.COMMON,
                                     sector_id=5, payload=DiscoveryPayload(kind=PayloadKind.LORE))
    assert dialogue_facts.situational_facts(state, player, CFG.roster)["wreck_here"] is True
    # A stale flight (yesterday) no longer reads as "just fled".
    stale = Player(id=1, name="Cap", ship_id=1, latinum=0, turns_remaining=200,
                   last_combat=LastCombat(species="quill", outcome="fled", day=0))
    assert dialogue_facts.situational_facts(state, stale, CFG.roster)["just_fled_combat"] is False
    # Hand-built rigs without a ship/sector degrade to empty — pure tests keep working.
    assert dialogue_facts.situational_facts(_bare_state(), player, CFG.roster) == {}


# --- WP30: callback + arc facts ----------------------------------------------------


def test_callback_and_arc_facts() -> None:
    from dataclasses import replace

    from edge.core.models import LastCombat, Lead

    sp = _species("vesk")
    fresh = Player(id=1, name="Cap", ship_id=1, latinum=0)
    assert dialogue_facts.callback_facts(fresh, sp) == {
        "met_before": False, "lead_pending": False, "lead_followed": False, "fled_us": False}

    lead = Lead(kind="discovery", ref=7, sector_id=42, origin_sector=11,
                source_species="vesk", summary="a drifting wreck")
    seasoned = Player(id=1, name="Cap", ship_id=1, latinum=0,
                      species_last_seen={"vesk": 11}, leads=(lead,),
                      last_combat=LastCombat(species="vesk", outcome="fled", day=3),
                      species_arcs={"vesk": {"oath_sworn": True, "debt": 2}})
    cb = dialogue_facts.callback_facts(seasoned, sp)
    assert cb["met_before"] is True and cb["fled_us"] is True
    assert cb["lead_pending"] is True and cb["lead_followed"] is False  # 42 unvisited
    followed = replace(seasoned, explored_sectors=frozenset({42}))
    cb = dialogue_facts.callback_facts(followed, sp)
    assert cb["lead_pending"] is False and cb["lead_followed"] is True

    # Arc flags surface namespaced; another kind's history contributes nothing.
    assert dialogue_facts.arc_facts(seasoned, sp) == {"arc.oath_sworn": True, "arc.debt": 2}
    assert dialogue_facts.arc_facts(seasoned, _species("selvani")) == {}
    assert dialogue_facts.callback_facts(seasoned, _species("selvani"))["met_before"] is False


# --- WP31: encounter facts + combat-context gating ---------------------------------


def test_encounter_facts_and_combat_contexts() -> None:
    from edge.core.models import Encounter, EncounterFoe
    from edge.dialogue import combat_contexts

    def foe(hull: int) -> EncounterFoe:
        return EncounterFoe(ship_class_id="x", name="F", hull=hull, hull_max=50, shields=0,
                            damage=5, firing_arc="all_round", combat_speed=1)

    enc = Encounter(species_id=1, sector_id=9, foes=(foe(50), foe(0), foe(0)),
                    round=3, player_shields=0)
    assert dialogue_facts.encounter_facts(enc) == {
        "round": 3, "pack_size": 3, "foes_left": 1,
        "pack_bloodied": True, "shields_down": True}

    fighter = next(s for s in CFG.roster.species if s.combatant and s.fleet)
    assert combat_contexts(fighter) == frozenset(
        {"combat_open", "combat_taunt", "surrender", "flee_scorn", "betrayal"})
    pacifist = next(s for s in CFG.roster.species if not s.combatant or not s.fleet)
    assert combat_contexts(pacifist) == frozenset()
