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
    select_line,
    speak,
    standing_for,
    validate_dialogue,
)
from edge.core.models import AlienSpecies, Player

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
    assert "trade_open" in rc and "trade_refuse" not in rc
    assert "greeting" in rc and "dossier_other" in rc

    dacaran = CFG.roster.species_by_id("dacaran")  # trade_posture refuses
    assert dacaran is not None
    assert "trade_refuse" in reachable_contexts(dacaran)
    assert "trade_open" not in reachable_contexts(dacaran)

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
