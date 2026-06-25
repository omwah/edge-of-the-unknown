"""The backend-agnostic authoring pipeline (DESIGN §6.7, dev-only).

Assembles a prompt per (voice, intent), asks a `Backend` for a schema-valid Tracery grammar,
validates and render-smoke-tests it, and assembles `DialoguePack`-shaped dicts ready to write
to a config sidecar. The grammar shape is a **closed** schema (a fixed set of symbols) so the
same JSON-schema works across Ollama / Anthropic / Antigravity strict-output modes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from string import Formatter
from typing import Any

from edge.dialogue import render
from edge.dialogue.intents import INTENTS, allowed_placeholders

# The fixed grammar symbols a generated line may define (a closed schema — see module doc).
# `origin` is the entry point; the rest are optional fragments it may reference via `#name#`.
_GRAMMAR_SYMBOLS = ("origin", "opener", "detail", "honorific", "aside")

# Render smoke-test budget: how many seeds to expand, and the minimum word-characters every
# expansion must carry to count as an actual line (rejects collapse-to-punctuation grammars).
_SMOKE_SEEDS = 24
_MIN_RENDER_WORDCHARS = 12


def output_schema() -> dict[str, Any]:
    """A strict JSON schema for a Tracery grammar (closed symbol set, `origin` required)."""
    str_array = {"type": "array", "items": {"type": "string"}, "minItems": 1}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {sym: str_array for sym in _GRAMMAR_SYMBOLS},
        "required": ["origin"],
    }


@dataclass(frozen=True)
class AuthoringRequest:
    """One unit of authoring: realise `context` in `voice`, using `placeholders` only."""

    context: str  # an intent key (greeting, offer_coordinates, …)
    voice: str  # the persona/species voice description that seeds the grammar
    placeholders: frozenset[str]
    examples: Mapping[str, str] = field(default_factory=dict)


def build_prompt(req: AuthoringRequest) -> str:
    """The instruction handed to a backend to author one persona-voiced grammar (§6.7)."""
    intent = INTENTS.get(req.context)
    concept = intent.concept if intent is not None else "conversation"
    holes = ", ".join(sorted(f"{{{p}}}" for p in req.placeholders)) or "(none)"
    example = (f"\nFor reference, these placeholder values may appear at runtime: "
               f"{dict(req.examples)}." if req.examples else "")
    fragments = ", ".join(s for s in _GRAMMAR_SYMBOLS if s != "origin")
    return (
        "You are authoring branching dialogue for a space-exploration game, offline.\n\n"
        f"THE SPEAKER is the alien species described below. THE LISTENER is the player "
        f"(a lone human captain). Write what the ALIEN SAYS TO THE PLAYER for the "
        f"'{req.context}' beat (game concept: {concept}). Speak in first person as the "
        f"species, addressing the player directly — never narrate from the player's side.\n\n"
        f"Speaker:\n{req.voice}\n\n"
        + (_intent_brief(req.context))
        + "Output a Tracery grammar. Rules:\n"
        "- Return ONLY a JSON object mapping Tracery symbols to arrays of expansion strings.\n"
        "- Define an 'origin' symbol that expands the COMPLETE line. 'origin' MUST build the "
        f"line by referencing the fragment symbols ({fragments}) you define, using #symbol# "
        "syntax — e.g. \"origin\": [\"#opener# #detail#\"]. Don't leave fragments unused.\n"
        "- Two DISTINCT syntaxes, never combined: write #opener# for a grammar symbol, and "
        f"{{player}} for a placeholder. NEVER write #{{player}}# or {{opener}} — that is invalid.\n"
        f"- You may use ONLY these literal placeholders, copied verbatim: {holes}.\n"
        "- Do not invent other {curly} placeholders. Keep every line in the speaker's voice."
        f"{example}"
    )


def _intent_brief(context: str) -> str:
    """A one-line situational brief so the model gets the beat's intent right (§6.7)."""
    briefs = {
        "greeting": "The player has just hailed you; greet them.\n",
        "trade_open": "You are willing to trade; invite the player to deal.\n",
        "trade_refuse": "You will not trade with the player right now; rebuff them.\n",
        "farewell": "The player is leaving; give a parting line.\n",
        "dossier_other": "The player asked your opinion of another species, {subject}; "
                         "tell them what you think of {subject}.\n",
        "offer_coordinates": "You are doing the player a favour: you know of {target} they "
                             "have not found, and you GIVE THEM the route. Tell them to set "
                             "course for sector {coords} — about {distance} jumps out, in the "
                             "{band} — where {reward} awaits.\n",
    }
    return briefs.get(context, "")


def _strings(grammar: Mapping[str, Sequence[str]]) -> list[str]:
    return [s for vals in grammar.values() for s in vals]


def _placeholders_in(template: str) -> set[str]:
    # `str.Formatter` rejects malformed braces (e.g. `{a {b}}`) with a raw ValueError; small
    # models emit these, so surface it as an AuthoringError — a retryable validation failure,
    # not a crash that aborts the whole batch.
    try:
        return {name for _, name, _, _ in Formatter().parse(template) if name}
    except ValueError as exc:
        raise AuthoringError(f"malformed placeholder syntax in {template!r}: {exc}") from exc


class AuthoringError(Exception):
    """A generated grammar failed validation (bad placeholder, empty render, …)."""


_SYMBOL_REF = re.compile(r"#([^#]+)#")  # a Tracery #symbol# reference


def validate_generated(grammar: Mapping[str, Sequence[str]], context: str) -> None:
    """Assert a generated grammar is fillable, well-formed, and renders non-empty (§13).

    Catches the failure modes small models actually produce: unfillable placeholders, the
    `#{player}#` syntax mash-up, `#symbol#` references to undefined symbols (even inside
    fragments `origin` doesn't reach), an `origin` that ignores the fragments it defined, and
    grammars that render empty or leave an unresolved `((symbol))`.
    """
    if "origin" not in grammar:
        raise AuthoringError(f"{context}: grammar defines no 'origin' symbol")
    allowed = allowed_placeholders(context)
    defined = set(grammar)
    for template in _strings(grammar):
        bad = _placeholders_in(template) - allowed
        if bad:
            raise AuthoringError(f"{context}: unfillable placeholder(s) {sorted(bad)} in {template!r}")
        if "#{" in template or "}#" in template:
            raise AuthoringError(f"{context}: mixed #symbol#/{{placeholder}} syntax in {template!r}")
        if "{{" in template or "}}" in template:
            # Escaped braces render literally under runtime `str.format_map` (e.g. `{{player}}`
            # -> `{player}`), so the placeholder never fills — never what the model meant.
            raise AuthoringError(f"{context}: escaped/literal braces in {template!r}")
        if any(field == "" for _, field, _, _ in Formatter().parse(template)):
            # A bare positional `{}` crashes runtime `str.format_map`; reject it here.
            raise AuthoringError(f"{context}: positional '{{}}' field in {template!r}")
        for ref in _SYMBOL_REF.findall(template):
            if "{" in ref or "}" in ref:
                raise AuthoringError(f"{context}: malformed symbol reference #{ref}# in {template!r}")
            if ref not in defined:
                raise AuthoringError(f"{context}: reference to undefined symbol #{ref}# in {template!r}")
    # Render smoke test across many seeds (runtime draws far more than a few): every
    # expansion must have no unresolved symbol and clear the substance floor, so grammars
    # whose fragments can collapse to punctuation/whitespace ("." / ". .") are rejected here
    # rather than blanking a line in game.
    for seed in (str(i) for i in range(_SMOKE_SEEDS)):
        text = render.expand(grammar, seed=seed)
        if "((" in text:
            raise AuthoringError(f"{context}: grammar leaves an undefined symbol: {text!r}")
        if len(re.findall(r"\w", text)) < _MIN_RENDER_WORDCHARS:
            raise AuthoringError(f"{context}: a grammar expansion is too thin to be a line: {text!r}")


def _reachable_from(grammar: Mapping[str, Sequence[str]], seeds: set[str]) -> set[str]:
    """Every symbol reachable by following #symbol# references from `seeds` (transitively)."""
    reached: set[str] = set()
    queue = list(seeds)
    while queue:
        sym = queue.pop()
        if sym in reached or sym not in grammar:
            continue
        reached.add(sym)
        for tpl in grammar[sym]:
            queue.extend(_SYMBOL_REF.findall(tpl))
    return reached


def prune_unreachable(grammar: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    """Drop symbols `origin` never references — harmless dead authoring small models emit.

    Pruning before validation makes the pipeline robust to a model that wires only some of
    its fragments, while keeping validation strict on everything that can actually render: a
    malformed or undefined reference is only fatal if `origin` can reach it.
    """
    if "origin" not in grammar:
        return {k: list(v) for k, v in grammar.items()}  # validation will reject it
    origin_refs = {r for tpl in grammar["origin"] for r in _SYMBOL_REF.findall(tpl)}
    keep = {"origin"} | _reachable_from(grammar, origin_refs)
    return {k: list(v) for k, v in grammar.items() if k in keep}


def repair(grammar: Mapping[str, Sequence[str]], context: str) -> dict[str, list[str]]:
    """Normalise the two mistakes small models reliably make, before validation.

    (1) `#name#`, or a `#` fused onto a placeholder (`#{name}` / `#{name}#`), where `name` is a
    placeholder → `{name}`: the model meant the placeholder, not a grammar symbol. (2) A `#ref#`
    to a symbol that isn't defined → dropped:
    the model wanted a fragment it never wrote; the rest of the line stands (and the substance
    floor rejects it if that left it too thin). This is graceful repair of *candidate* content
    a human reviews before merging — it never invents text, only fixes syntax and removes
    dangling references. Hard floors (allowed placeholders, substance, no `((`) still apply.
    """
    allowed = allowed_placeholders(context)

    def to_placeholder(s: str) -> str:
        # A '#' fused onto a {placeholder} is a model slip (#{player}, #{player}#); strip it.
        # The lookbehind leaves the closing '#' of a real "#symbol#" that abuts a placeholder
        # intact (that abutment is rejected elsewhere, not silently mangled here).
        s = re.sub(r"(?<!\w)#(\{\w+\}#?)", lambda m: m.group(1).rstrip("#"), s)
        return re.sub(r"#(\w+)#",
                      lambda m: f"{{{m.group(1)}}}" if m.group(1) in allowed else m.group(0), s)

    step1 = {k: [to_placeholder(x) for x in v] for k, v in grammar.items()}
    defined = set(step1)

    def drop_dangling(s: str) -> str:
        return re.sub(r"#(\w+)#",
                      lambda m: m.group(0) if m.group(1) in defined else "", s)

    return {k: [drop_dangling(x) for x in v] for k, v in step1.items()}


def author_line(backend: Any, req: AuthoringRequest, *, retries: int = 3) -> dict[str, Any]:
    """Author one grammar line entry: generate → repair → prune → validate, with retries.

    LLM sampling is stochastic, so a grammar that fails the quality floor on one draw often
    passes on the next. We retry the generator up to `retries` times rather than relax the
    floor — keeping output quality high while tolerating flaky small models. A backend whose
    response won't even parse as JSON (`JSONDecodeError`) is treated the same way — one bad
    draw retries instead of aborting the whole run. Raises the last error if every attempt
    fails. (Backend *configuration* errors — a missing CLI, a bad host — surface as other
    exception types and abort immediately, by design.)
    """
    prompt = build_prompt(req)
    last: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            raw = backend.generate(prompt, schema=output_schema())
            grammar = prune_unreachable(repair(raw, req.context))
            validate_generated(grammar, req.context)
        except (AuthoringError, json.JSONDecodeError) as exc:
            last = exc
            continue
        return {"grammar": grammar}
    assert last is not None
    raise last


def author_packs(backend: Any, voices: Mapping[str, str], contexts: Sequence[str], *,
                 examples: Mapping[str, Mapping[str, str]] | None = None,
                 retries: int = 3) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Author a `{voice -> {context -> [line]}}` pack tree for every (voice, context) pair.

    `voices` maps a persona/species id to its voice description; `contexts` are the intents to
    author; `examples` optionally supplies per-context placeholder samples to ground the model.
    Each entry is generated with `retries` and validated, so only sound grammars are kept.
    """
    examples = examples or {}
    packs: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for voice_id, voice in voices.items():
        pack: dict[str, list[dict[str, Any]]] = {}
        for context in contexts:
            req = AuthoringRequest(
                context=context, voice=voice,
                placeholders=allowed_placeholders(context),
                examples=examples.get(context, {}),
            )
            pack[context] = [author_line(backend, req, retries=retries)]
        packs[voice_id] = pack
    return packs
