"""Phase-2 — Tracery realisation of dialogue grammars (DESIGN §6.7).

Covers `edge.dialogue.render.expand` (determinism, shared-fragment merge), the grammar
branch of the selector (placeholder fill, reproducibility, recency rotation), and the
`DialogueLine` realisation invariants.
"""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from edge.core.config import DialogueLine, DialogueWhen
from edge.dialogue import select_line
from edge.dialogue.render import GRAMMAR_VARIANTS, expand
from edge.dialogue.select import FRIENDLY


# --- expand: determinism + shared merge ------------------------------------------

def test_expand_is_deterministic_for_a_seed() -> None:
    rules = {"origin": ["#greet#, friend."], "greet": ["Hail", "Greetings", "Well met"]}
    a = expand(rules, seed="s1")
    b = expand(rules, seed="s1")
    assert a == b and a.endswith(", friend.")
    # The chosen branch is one of the authored options.
    assert a.split(",")[0] in {"Hail", "Greetings", "Well met"}


def test_expand_merges_shared_fragments_and_line_overrides() -> None:
    shared = {"honor": ["friend", "captain"]}
    rules = {"origin": ["Hail, #honor#."]}
    out = expand(rules, shared=shared, seed="x")
    assert out in {"Hail, friend.", "Hail, captain."}
    # A line-local symbol overrides a shared one of the same name.
    over = expand({"origin": ["#honor#"], "honor": ["ally"]}, shared=shared, seed="x")
    assert over == "ally"


def test_expand_does_not_disturb_global_rng() -> None:
    random.seed(123)
    before = [random.random() for _ in range(3)]
    random.seed(123)
    _ = expand({"origin": ["#x#"], "x": ["a", "b", "c"]}, seed="seed")
    after = [random.random() for _ in range(3)]
    assert before == after  # global RNG state restored after expansion


# --- selector: grammar branch ----------------------------------------------------

def _grammar_pack() -> dict:
    grammar = {"origin": ["#greet# {player}"], "greet": ["Hail", "Greetings", "Well met"]}
    return {"greeting": [DialogueLine(grammar=grammar)]}


def test_grammar_entry_fills_placeholders_and_is_reproducible() -> None:
    chain = [_grammar_pack()]
    text, ring = select_line(chain, "greeting", standing=FRIENDLY, treaty=False,
                             ctx={"player": "Cap"}, recency=(), rng=random.Random(7))
    assert text.endswith(" Cap") and ring  # placeholder filled, ring advanced
    again, _ = select_line(chain, "greeting", standing=FRIENDLY, treaty=False,
                           ctx={"player": "Cap"}, recency=(), rng=random.Random(7))
    assert text == again  # same seed → identical realisation


def test_grammar_recency_ring_rotates_index() -> None:
    chain = [_grammar_pack()]
    rng = random.Random(9)
    ring: tuple[int, ...] = ()
    for _ in range(12):
        _, ring = select_line(chain, "greeting", standing=FRIENDLY, treaty=False,
                              ctx={"player": "Cap"}, recency=ring, rng=rng, k=2)
        assert len(ring) <= 2
        assert all(0 <= i < GRAMMAR_VARIANTS for i in ring)
    # With K=2 the last two rotation indices are always distinct.
    assert ring[0] != ring[1]


# --- DialogueLine realisation invariants -----------------------------------------

def test_line_requires_variants_or_grammar() -> None:
    with pytest.raises(ValidationError, match="variants` or `grammar"):
        DialogueLine(when=DialogueWhen())


def test_grammar_line_requires_origin_symbol() -> None:
    with pytest.raises(ValidationError, match="origin"):
        DialogueLine(grammar={"greet": ["Hail"]})
