"""Phase-5 — the offline authoring pipeline (DESIGN §6.7, dev-only).

Exercises the backend-agnostic pipeline with the `StaticBackend` (no network/model): prompt
assembly, the strict output schema, per-line validation, and that a generated grammar both
validates and renders through the *runtime* selector — proving the authored config is loadable.
"""

from __future__ import annotations

import pytest

from edge.core.config import DialogueLine
from edge.dialogue import select_line
from edge.dialogue.authoring import (
    AuthoringRequest,
    StaticBackend,
    author_packs,
    build_prompt,
    get_backend,
    output_schema,
    validate_generated,
)
from edge.dialogue.authoring.pipeline import AuthoringError, prune_unreachable, repair
from edge.dialogue.intents import allowed_placeholders


def test_output_schema_is_closed_and_requires_origin() -> None:
    schema = output_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["origin"] and "origin" in schema["properties"]


def test_build_prompt_lists_only_allowed_placeholders() -> None:
    req = AuthoringRequest("offer_coordinates", "A terse trader.",
                           allowed_placeholders("offer_coordinates"),
                           examples={"coords": "42"})
    prompt = build_prompt(req)
    assert "offer_coordinates" in prompt and "{coords}" in prompt and "origin" in prompt


def test_validate_rejects_unfillable_placeholder() -> None:
    with pytest.raises(AuthoringError, match="unfillable"):
        validate_generated({"origin": ["Hello {nonsense}"]}, "greeting")


def test_validate_rejects_undefined_symbol() -> None:
    with pytest.raises(AuthoringError, match="undefined symbol"):
        validate_generated({"origin": ["#missing#"]}, "greeting")


def test_validate_rejects_mixed_symbol_placeholder_syntax() -> None:
    # The `#{player}#` mash-up small models emit — caught even though it's not a bare ref.
    with pytest.raises(AuthoringError, match="mixed"):
        validate_generated({"origin": ["Hail #{player}#"]}, "greeting")


def test_prune_drops_fragments_origin_never_reaches() -> None:
    # Dead fragments a small model emits are pruned (robustness), not fatal — but garbage
    # inside them is dropped with them, so it can never reach the rendered line.
    pruned = prune_unreachable(
        {"origin": ["Hail, #opener#, and well met."], "opener": ["esteemed {player}"],
         "aside": ["#{species}# garbage"]})
    assert pruned == {"origin": ["Hail, #opener#, and well met."], "opener": ["esteemed {player}"]}
    validate_generated(pruned, "greeting")  # the pruned grammar is clean


def test_repair_normalizes_placeholder_syntax_and_drops_dangling_refs() -> None:
    # The two mistakes models actually make: `#species#` for a placeholder, and a `#ref#`
    # to a fragment they never defined. Repair fixes the first and drops the second.
    fixed = repair({"origin": ["#missing# We greet you, #species#, from afar, #{player}#."]},
                   "greeting")
    line = fixed["origin"][0]
    assert "{species}" in line and "{player}" in line  # symbol → placeholder
    assert "#missing#" not in line and "#" not in line  # dangling ref dropped


def test_static_backend_authors_a_loadable_renderable_pack() -> None:
    voices = {"vesk": "Vesk: stern reptilian merchants (persona: serial_formal)"}
    packs = author_packs(StaticBackend(), voices, ["greeting", "offer_coordinates"])
    pack = packs["vesk"]
    assert set(pack) == {"greeting", "offer_coordinates"}

    # Each authored entry round-trips into a real DialogueLine and renders via the selector.
    for context, entries in pack.items():
        line = DialogueLine(**entries[0])  # grammar-based line — validators accept it
        chain = [{context: [line]}]
        import random
        text, _ = select_line(chain, context, standing="friendly", treaty=False,
                              ctx={"player": "Cap"}, recency=(), rng=random.Random(0))
        assert text and "((" not in text


def test_get_backend_resolves_and_rejects_unknown() -> None:
    assert get_backend("static").name == "static"
    assert get_backend("ollama").name == "ollama"
    with pytest.raises(ValueError, match="unknown backend"):
        get_backend("gpt")
