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


def test_output_schema_wraps_a_closed_grammar_plus_optional_choices() -> None:
    schema = output_schema()
    assert schema["additionalProperties"] is False
    # Top level: a required `grammar` plus an optional `choices` array (§6.7 branching).
    assert schema["required"] == ["grammar"]
    assert set(schema["properties"]) == {"grammar", "choices"}
    grammar = schema["properties"]["grammar"]
    assert grammar["additionalProperties"] is False
    assert grammar["required"] == ["origin"] and "origin" in grammar["properties"]
    choice = schema["properties"]["choices"]["items"]
    assert choice["required"] == ["text"]
    assert set(choice["properties"]["action"]["enum"]) == {
        "leave", "trade", "barter", "accept_lead", "attack"}


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


def test_repair_strips_hash_fused_onto_placeholder() -> None:
    # qwen2 emits a '#' fused onto a placeholder with no closing '#' (#{player}); repair
    # normalises it (the older #{player}# form too) so it isn't rejected as mixed syntax.
    fixed = repair({"origin": ["Our paths cross, #{player}, near {coords}."]}, "offer_coordinates")
    assert fixed["origin"][0] == "Our paths cross, {player}, near {coords}."
    validate_generated(fixed, "offer_coordinates")  # now passes the §13 floor

    # A real "#symbol#" abutting a placeholder keeps its closing '#' (not mangled by repair).
    assert repair({"origin": ["#opener#{player}"], "opener": ["hi"]},
                  "greeting")["origin"][0] == "#opener#{player}"


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
    assert get_backend("claude").name == "claude"
    assert get_backend("agy").name == "agy"
    with pytest.raises(ValueError, match="unknown backend"):
        get_backend("gpt")


# --- CLI-session backend (Claude Code / Antigravity / any agent CLI) --------------

def test_extract_json_tolerates_fences_and_prose() -> None:
    from edge.dialogue.authoring.backends import _extract_json

    assert _extract_json('```json\n{"origin": ["hi"]}\n```') == {"origin": ["hi"]}
    assert _extract_json('Here you go:\n{"origin": ["x"]}\nDone.') == {"origin": ["x"]}
    assert _extract_json('{"origin": ["y"]}') == {"origin": ["y"]}


def test_extract_json_tolerates_trailing_data() -> None:
    """gemma4:12b appends a second object / prose after a valid one — take the first object."""
    import json

    from edge.dialogue.authoring.backends import _extract_json

    assert _extract_json('{"origin": ["a"]}\n{"origin": ["b"]}') == {"origin": ["a"]}
    assert _extract_json('{"origin": ["a"]}\nHope that helps!') == {"origin": ["a"]}
    with pytest.raises(json.JSONDecodeError):
        _extract_json("sorry, I cannot do that")


def test_author_line_retries_a_backend_that_emits_unparseable_json() -> None:
    """A one-off non-JSON backend response retries instead of aborting the run."""
    from edge.dialogue.authoring.pipeline import author_line
    from edge.dialogue.authoring.backends import _extract_json

    calls = {"n": 0}

    class _Flaky:
        name = "flaky"

        def generate(self, prompt: str, *, schema: object) -> dict:
            calls["n"] += 1
            if calls["n"] == 1:
                _extract_json("not json at all")  # raises JSONDecodeError on the first draw
            return {"origin": ["#opener#"], "opener": ["Well met, {player}, from the {species}."]}

    line = author_line(_Flaky(), AuthoringRequest("greeting", "v", frozenset()), retries=3)
    assert calls["n"] == 2 and line["grammar"]["origin"] == ["#opener#"]


def test_parse_claude_envelope_handles_object_and_string_result() -> None:
    from edge.dialogue.authoring.backends import _parse_claude_envelope

    assert _parse_claude_envelope('{"type":"result","result":{"origin":["a"]}}') == {"origin": ["a"]}
    assert _parse_claude_envelope('{"result":"{\\"origin\\":[\\"b\\"]}"}') == {"origin": ["b"]}
    assert _parse_claude_envelope('{"origin":["c"]}') == {"origin": ["c"]}  # no envelope


def test_cli_backend_requires_a_command() -> None:
    from edge.dialogue.authoring.backends import CliBackend

    with pytest.raises(RuntimeError, match="needs a command"):
        CliBackend("cli")


def test_cli_backend_runs_external_cli_and_cleans_up(tmp_path: object) -> None:
    """The generic `cli` backend writes prompt/schema to a temp dir, runs the configured CLI
    (which writes the grammar to {out_file}), reads it back, and removes the temp dir."""
    import glob
    import sys
    import tempfile
    from pathlib import Path

    from edge.dialogue.authoring.backends import get_backend

    fake = Path(str(tmp_path)) / "fake_agent.py"
    fake.write_text(
        "import sys, json, pathlib\n"
        "assert pathlib.Path(sys.argv[1]).read_text()  # prompt was written\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({'origin': ['from #f#'], 'f': ['the void']}))\n"
    )
    backend = get_backend("cli", command=f"{sys.executable} {fake} {{prompt_file}} {{out_file}}")

    before = set(glob.glob(tempfile.gettempdir() + "/edge-author-cli-*"))
    out = backend.generate("author a greeting", schema={"type": "object", "required": ["origin"]})
    after = set(glob.glob(tempfile.gettempdir() + "/edge-author-cli-*"))

    assert out == {"origin": ["from #f#"], "f": ["the void"]}
    assert not (after - before)  # the session temp dir was cleaned up


def test_cli_backend_errors_when_cli_writes_no_file(tmp_path: object) -> None:
    import sys
    from pathlib import Path

    from edge.dialogue.authoring.backends import get_backend

    noop = Path(str(tmp_path)) / "noop.py"
    noop.write_text("pass\n")  # never writes {out_file}
    backend = get_backend("cli", command=f"{sys.executable} {noop} {{out_file}}")
    with pytest.raises(RuntimeError, match="produced no grammar.json"):
        backend.generate("x", schema={"type": "object"})


def test_debug_backend_echoes_prompt_and_response(capsys: object) -> None:
    """--debug routes generate through DebugBackend, echoing request + response to stderr while
    forwarding the result and the inner backend's name/model."""
    from edge.dialogue.authoring import DebugBackend, StaticBackend

    dbg = DebugBackend(StaticBackend())
    assert dbg.name == "static"  # transparent: sidecar still named for the inner backend
    result = dbg.generate("AUTHOR THE GREETING", schema=output_schema())

    err = capsys.readouterr().err  # type: ignore[attr-defined]
    assert "← prompt" in err and "AUTHOR THE GREETING" in err  # the request
    assert "→ response" in err and "origin" in err              # the response
    assert result == StaticBackend().generate("x", schema=output_schema())  # forwarded unchanged


def test_author_line_validates_choice_targets_and_retries() -> None:
    """Choice `next_context` validation triggers a retry, not immediate failure."""
    from edge.dialogue.authoring.pipeline import author_line

    call_count = {"n": 0}

    class _BadThenGood:
        name = "flaky_choice"

        def generate(self, prompt: str, *, schema: object) -> dict:
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First attempt: invalid choice target → will fail validation
                return {
                    "grammar": {"origin": ["Well met, {player}. We welcome you to our corner of space."]},
                    "choices": [{"text": "Ask for trade", "next_context": "identify_intent"}]
                }
            # Second attempt: valid choice (known context)
            return {
                "grammar": {"origin": ["Well met, {player}. We welcome you to our corner of space."]},
                "choices": [{"text": "Ask for trade", "next_context": "trade_open"}]
            }

    # With known_contexts, invalid targets trigger a retry instead of immediate failure.
    line = author_line(_BadThenGood(), AuthoringRequest("greeting", "v", frozenset()),
                      known_contexts=frozenset(["greeting", "trade_open"]), retries=3)
    assert call_count["n"] == 2  # first attempt failed, second succeeded
    assert line["choices"][0]["next_context"] == "trade_open"


def test_author_line_accepts_branch_contexts() -> None:
    """Choice targets can point to branch.* reserved namespaces."""
    from edge.dialogue.authoring.pipeline import author_line

    class _SpecialContexts:
        name = "special"

        def generate(self, prompt: str, *, schema: object) -> dict:
            return {
                "grammar": {"origin": ["So, what brings you here to seek our counsel today?"]},
                "choices": [
                    {"text": "A", "next_context": "branch.custom_node"},
                ]
            }

    line = author_line(_SpecialContexts(), AuthoringRequest("greeting", "v", frozenset()),
                      known_contexts=frozenset(["greeting"]))
    assert len(line["choices"]) == 1
    assert line["choices"][0]["next_context"] == "branch.custom_node"


def test_author_packs_generates_dossiers_and_sub_branches() -> None:
    from edge.dialogue.authoring import author_packs, StaticBackend
    voices = {"vesk": "Vesk description"}
    packs = author_packs(StaticBackend(), voices, ["greeting", "dossier_self", "dossier_other"])
    pack = packs["vesk"]
    # Check that dossier_self and dossier_other are present
    assert "dossier_self" in pack
    assert "dossier_other" in pack
    
    # Check that sub-branches are present
    categories = [
        "biology_and_appearance",
        "psychology_and_culture",
        "diplomacy_and_behavior",
        "relationships",
        "combat_and_ships",
    ]
    for cat in categories:
        assert f"branch.dossier_self.{cat}" in pack
        assert f"branch.dossier_other.{cat}" in pack
        
    # Check structure of dossier_self branch
    bio_self = pack["branch.dossier_self.biology_and_appearance"][0]
    assert bio_self["choices"][0]["next_context"] == "back"
    
    # Check structure of dossier_other branch
    bio_other = pack["branch.dossier_other.biology_and_appearance"]
    # Should have entries for each species in the roster + catch-all
    assert len(bio_other) > 1
    assert bio_other[0]["choices"][0]["next_context"] == "back"
    # An entry should have a matching subject criteria
    assert "subject" in bio_other[0]["when"]["criteria"]
