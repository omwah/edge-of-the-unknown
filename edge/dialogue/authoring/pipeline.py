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
from edge.dialogue.intents import BRANCH_PREFIX, CHOICE_ACTIONS, INTENTS, allowed_placeholders

# The fixed grammar symbols a generated line may define (a closed schema — see module doc).
# `origin` is the entry point; the rest are optional fragments it may reference via `#name#`.
_GRAMMAR_SYMBOLS = ("origin", "opener", "detail", "honorific", "aside")

# Render smoke-test budget: how many seeds to expand, and the minimum word-characters every
# expansion must carry to count as an actual line (rejects collapse-to-punctuation grammars).
_SMOKE_SEEDS = 24
_MIN_RENDER_WORDCHARS = 12


def grammar_schema() -> dict[str, Any]:
    """The strict Tracery-grammar schema (closed symbol set, `origin` required)."""
    str_array = {"type": "array", "items": {"type": "string"}, "minItems": 1}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {sym: str_array for sym in _GRAMMAR_SYMBOLS},
        "required": ["origin"],
    }


def output_schema() -> dict[str, Any]:
    """A strict schema for one authored line: a closed `grammar` plus optional player `choices`.

    The grammar half is unchanged (a closed Tracery symbol set, `origin` required); the
    `choices` half (§6.7 branching) is an optional array of player replies, each a `text`
    label with an optional `next_context` and a `CHOICE_ACTIONS` `action`. `author_line`
    also accepts a bare grammar object (a backend that predates the wrapper), so older
    backends keep working.
    """
    choice = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "next_context": {"type": "string"},
            "action": {"type": "string", "enum": sorted(CHOICE_ACTIONS)},
        },
        "required": ["text"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "grammar": grammar_schema(),
            "choices": {"type": "array", "items": choice},
        },
        "required": ["grammar"],
    }


@dataclass(frozen=True)
class AuthoringRequest:
    """One unit of authoring: realise `context` in `voice`, using `placeholders` only."""

    context: str  # an intent key (greeting, offer_coordinates, …)
    voice: str  # the persona/species voice description that seeds the grammar
    placeholders: frozenset[str]
    examples: Mapping[str, str] = field(default_factory=dict)


def build_prompt(req: AuthoringRequest, known_contexts: frozenset[str] | None = None) -> str:
    """The instruction handed to a backend to author one persona-voiced grammar (§6.7).

    `known_contexts` lists the available contexts; if provided, it's included in the prompt
    so the model knows which contexts are valid for choice transitions.
    """
    intent = INTENTS.get(req.context)
    concept = intent.concept if intent is not None else "conversation"
    holes = ", ".join(sorted(f"{{{p}}}" for p in req.placeholders)) or "(none)"
    example = (f"\nFor reference, these placeholder values may appear at runtime: "
               f"{dict(req.examples)}." if req.examples else "")
    fragments = ", ".join(s for s in _GRAMMAR_SYMBOLS if s != "origin")
    contexts_info = ""
    if known_contexts:
        contexts_list = ", ".join(sorted(known_contexts))
        contexts_info = (
            "\n- For 'next_context' in choices, use ONLY: " + contexts_list +
            ", or a custom branch.* node (e.g. \"branch.inquiry\"). Do not invent other context names."
        )
    return (
        "You are authoring branching dialogue for a space-exploration game, offline.\n\n"
        f"THE SPEAKER is the alien species described below. THE LISTENER is the player "
        f"(a lone human captain). Write what the ALIEN SAYS TO THE PLAYER for the "
        f"'{req.context}' beat (game concept: {concept}). Speak in first person as the "
        f"species, addressing the player directly — never narrate from the player's side.\n\n"
        f"Speaker:\n{req.voice}\n\n"
        + (_intent_brief(req.context))
        + _structure_brief(req.context)
        + "Output a JSON object {\"grammar\": {…}, \"choices\": [...]}. Rules:\n"
        "- 'grammar' is a JSON object mapping Tracery symbols to arrays of expansion strings.\n"
        "- Define an 'origin' symbol that expands the COMPLETE line. 'origin' MUST build the "
        f"line by referencing the fragment symbols ({fragments}) you define, using #symbol# "
        "syntax — e.g. \"origin\": [\"#opener# #detail#\"]. Don't leave fragments unused.\n"
        "- Two DISTINCT syntaxes, never combined: write #opener# for a grammar symbol, and "
        "{player} for a placeholder. NEVER write #{player}# or {opener} — that is invalid.\n"
        f"- You may use ONLY these literal placeholders, copied verbatim: {holes}.\n"
        "- Do not invent other {curly} placeholders. Keep every line in the speaker's voice.\n"
        "- OPTIONALLY add 'choices': an array of the PLAYER'S possible replies to this line, "
        "each {\"text\": <the captain's short reply, plain first person>, \"next_context\": "
        "<a beat to go to, optional>, \"action\": <one of "
        "leave/trade/barter/accept_lead/accept_contract, "
        "optional>}. Only 'text' is required. Omit 'choices' if no branching reply fits."
        + contexts_info
        + example
    )


def _structure_brief(context: str) -> str:
    """How the authored line is stored and used — context that steers correct structure (§6.7).

    Tells the model the grammar becomes one per-species pack entry resolved through a
    species -> persona -> generic fallback (so it should be the species' own voice), and that it
    is expanded repeatedly behind a no-repeat recency ring (so it should offer real variety).
    """
    return (
        "HOW THE GAME USES THIS LINE:\n"
        f"- It becomes one entry for the '{context}' beat in THIS species' dialogue pack (a config "
        "'species_grammars' map: species id -> beat -> [line]). At runtime the engine resolves a "
        "beat by walking species -> persona -> a built-in generic fallback and taking the most "
        "specific match, so write the species' OWN distinctive voice here; a plain fallback "
        "already exists, so don't write a bland one.\n"
        "- Your 'origin' is expanded MANY times behind a no-repeat recency ring, so put SEVERAL "
        "distinct alternatives (ideally 3+) in each symbol — a repeat encounter should rephrase, "
        "not replay the same words.\n"
        "- A visit is a multi-exchange SESSION: the player may hear this line early or late in "
        "the same conversation (topics already asked, and the live situation — distance band, "
        "hull damage, cargo, a fresh flight from combat — are facts a human editor can gate "
        "entries on). Keep each expansion self-contained — don't assume it is the first or "
        "only thing said this visit, and don't hard-code a situation the line doesn't pin.\n"
        "- Produce ONE self-contained spoken line per expansion (the alien's turn); the player's "
        "side, if any, goes only in 'choices'.\n\n"
    )


def _intent_brief(context: str) -> str:
    """A one-line situational brief so the model gets the beat's intent right (§6.7)."""
    if context.startswith(BRANCH_PREFIX):
        topic = context[len(BRANCH_PREFIX):].replace("_", " ")
        return (f"The player chose to explore the topic of '{topic}' further. "
                f"Continue the alien's side of the conversation on this subject.\n")
    if context.startswith("sig."):
        # Signature-mechanic prompt (§6.2, WP33): the hook has already run and applied its
        # outcome before this line speaks; author the delivery, gated on `sig_stage`.
        name = context[len("sig."):].replace(".", " ").replace("_", " ")
        return (f"This is the '{name}' signature-mechanic beat: the species' systemic hook "
                "has just run and applied its outcome (a verdict, reaction, or demand). "
                "Speak the alien's line delivering that outcome; gate distinct outcomes on "
                "the persisted `sig_stage` fact (e.g. sig_stage: judged_blessed), and keep a "
                "catch-all sibling.\n")
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
        "contract_offer": "You have a job for the player: {target}. Offer it as a favour — "
                          "done within {deadline} days, it pays {reward}. Speak the ask "
                          "plainly and invite them to take it.\n",
        "contract_report": "The player already took your job ({target}); remind them it "
                           "still stands and {reward} awaits when it is done.\n",
        # The combat beats (§6.7, WP31) — spoken by the encounter reducers, not conversation.
        "combat_open": "Battle is joined with the player's ship — your pack intercepted "
                       "them, or they struck first (WP70); issue the attack challenge.\n",
        "combat_taunt": "Mid-battle: taunt the player over the wideband while your pack "
                        "presses the attack.\n",
        "surrender": "Your pack is bloodied and losing; sue for quarter or signal "
                     "capitulation.\n",
        "flee_scorn": "The player just fled the fight; jeer at their retreating engines.\n",
        "betrayal": "You turn your weapons on the player despite an apparently friendly "
                    "standing; let the betrayal show.\n",
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


def author_line(backend: Any, req: AuthoringRequest, *, known_contexts: frozenset[str] | None = None,
                retries: int = 3) -> dict[str, Any]:
    """Author one grammar line entry: generate → repair → prune → validate, with retries.

    LLM sampling is stochastic, so a grammar that fails the quality floor on one draw often
    passes on the next. We retry the generator up to `retries` times rather than relax the
    floor — keeping output quality high while tolerating flaky small models. A backend whose
    response won't even parse as JSON (`JSONDecodeError`) is treated the same way — one bad
    draw retries instead of aborting the whole run. If `known_contexts` is provided, choice
    targets are validated and an invalid one triggers a retry (§6.7). Raises the last error if
    every attempt fails. (Backend *configuration* errors — a missing CLI, a bad host — surface
    as other exception types and abort immediately, by design.)
    """
    prompt = build_prompt(req, known_contexts=known_contexts)
    last: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            raw = backend.generate(prompt, schema=output_schema())
            # Accept both the wrapped {grammar, choices} shape and a bare grammar object (a
            # backend that predates the wrapper — e.g. StaticBackend — returns just the grammar).
            raw_grammar = raw.get("grammar", raw) if isinstance(raw, dict) else raw
            grammar = prune_unreachable(repair(raw_grammar, req.context))
            validate_generated(grammar, req.context)
            # Validate choice targets if known_contexts is provided (§6.7 branching).
            choices = raw.get("choices") if isinstance(raw, dict) else None
            if choices and known_contexts:
                for choice in choices:
                    next_ctx = choice.get("next_context")
                    if next_ctx is not None:
                        if not (next_ctx in known_contexts or
                                next_ctx.startswith(BRANCH_PREFIX)):
                            raise AuthoringError(
                                f"{req.context}: choice targets unknown context {next_ctx!r}"
                            )
        except (AuthoringError, json.JSONDecodeError) as exc:
            last = exc
            continue
        line: dict[str, Any] = {"grammar": grammar}
        choices = raw.get("choices") if isinstance(raw, dict) else None
        if choices:  # carry authored player replies through to the config sidecar (§6.7)
            line["choices"] = choices
        return line
    assert last is not None
    raise last


def _collect_branch_targets(pack: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Branch-node next_context values referenced by any choice in pack."""
    targets: set[str] = set()
    for entries in pack.values():
        for entry in entries:
            for choice in (entry.get("choices") or []):
                nxt = choice.get("next_context") or ""
                if nxt.startswith(BRANCH_PREFIX):
                    targets.add(nxt)
    return targets


def unresolved_branch_targets(
    packs: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, set[str]]:
    """Branch-node contexts referenced in choices but not yet authored, per voice.

    A non-empty return value means more branch passes are needed. Used by the CLI to
    decide whether to prompt for an extra pass after the branch_passes budget runs out.
    """
    result: dict[str, set[str]] = {}
    for voice_id, pack in packs.items():
        authored = frozenset(pack)
        unresolved = _collect_branch_targets(pack) - authored
        if unresolved:
            result[voice_id] = unresolved
    return result


def extend_packs(
    backend: Any,
    voices: Mapping[str, str],
    packs: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    retries: int = 3,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Author one round of unresolved branch nodes across all voices (for interactive use).

    For each voice, discovers every branch.* context referenced in a choice but not yet in
    the pack and generates an entry for it. Intended for the CLI's Y/N loop when the caller
    wants more branch authoring past the initial branch_passes budget. Mutates packs in
    place and returns it.
    """
    for voice_id, voice in voices.items():
        pack = packs.get(voice_id, {})
        known = set(pack)
        new_targets = _collect_branch_targets(pack) - known
        if not new_targets:
            continue
        known.update(new_targets)
        for branch_ctx in sorted(new_targets):
            if backend.__class__.__name__ != "DebugBackend":
                import sys
                print(f"  {voice_id} -> {branch_ctx}...", file=sys.stderr, flush=True)
            req = AuthoringRequest(
                context=branch_ctx, voice=voice,
                placeholders=allowed_placeholders(branch_ctx),
                examples={},
            )
            pack[branch_ctx] = [author_line(backend, req, known_contexts=frozenset(known),
                                             retries=retries)]
        packs[voice_id] = pack
    return packs


def author_packs(backend: Any, voices: Mapping[str, str], contexts: Sequence[str], *,
                 examples: Mapping[str, Mapping[str, str]] | None = None,
                 retries: int = 3,
                 branch_passes: int = 2,
                 existing_packs: Mapping[str, Mapping[str, list[dict[str, Any]]]] | None = None,
                 ) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Author a `{voice -> {context -> [line]}}` pack tree for every (voice, context) pair.

    `voices` maps a persona/species id to its voice description; `contexts` are the intents to
    author; `examples` optionally supplies per-context placeholder samples to ground the model.
    Each entry is generated with `retries` and validated, so only sound grammars are kept.
    Choice `next_context` targets are validated against the known contexts; an invalid target
    triggers a retry, so bad choices never make it into the output (§6.7 branching).

    If `existing_packs` is provided, each voice's pack is seeded from it and only missing
    contexts are authored — letting a resume run fill in what a previous run left incomplete.

    After the base contexts are authored, up to `branch_passes` rounds of branch-node discovery
    follow: any `branch.*` context referenced in a generated choice is authored in turn, using
    the same voice. Each round's `known_contexts` grows to include all discovered branch nodes so
    far, letting the model make valid intra-branch references. Set `branch_passes=0` to skip
    branch authoring entirely.
    """
    examples = examples or {}
    packs: dict[str, dict[str, list[dict[str, Any]]]] = {}
    base_known = frozenset(contexts)
    for voice_id, voice in voices.items():
        # Seed from existing pack if provided; only author contexts not already present.
        pack: dict[str, list[dict[str, Any]]] = (
            dict(existing_packs[voice_id])
            if existing_packs and voice_id in existing_packs
            else {}
        )
        known: set[str] = set(base_known) | set(pack)

        from edge.config import load_default_config
        cfg = load_default_config()
        species = next((s for s in cfg.roster.species if s.id == voice_id), None)
        sp_name = species.name if species else voice_id

        for context in contexts:
            if context in pack:
                continue  # already authored — preserve it

            if context == "dossier_self":
                pack["dossier_self"] = _author_dossier_self(voice_id, sp_name)
                _author_dossier_self_branches(backend, voice_id, voice, pack)
                known.update(pack)
                continue

            if context == "dossier_other":
                pack["dossier_other"] = _author_dossier_other(sp_name)
                _author_dossier_other_branches(backend, voice_id, voice, pack)
                known.update(pack)
                continue

            if backend.__class__.__name__ != "DebugBackend":
                import sys
                print(f"  {voice_id} -> {context}...", file=sys.stderr, flush=True)
            req = AuthoringRequest(
                context=context, voice=voice,
                placeholders=allowed_placeholders(context),
                examples=examples.get(context, {}),
            )
            pack[context] = [author_line(backend, req, known_contexts=frozenset(known),
                                         retries=retries)]

        # Check and author missing dossier branch nodes if dossier contexts are already present
        if "dossier_self" in pack:
            _author_dossier_self_branches(backend, voice_id, voice, pack)
        if "dossier_other" in pack:
            _author_dossier_other_branches(backend, voice_id, voice, pack)
        known.update(pack)

        for _ in range(branch_passes):
            new_targets = _collect_branch_targets(pack) - known
            if not new_targets:
                break
            known.update(new_targets)
            for branch_ctx in sorted(new_targets):
                if backend.__class__.__name__ != "DebugBackend":
                    import sys
                    print(f"  {voice_id} -> {branch_ctx}...", file=sys.stderr, flush=True)
                req = AuthoringRequest(
                    context=branch_ctx, voice=voice,
                    placeholders=allowed_placeholders(branch_ctx),
                    examples={},
                )
                pack[branch_ctx] = [author_line(backend, req, known_contexts=frozenset(known),
                                                 retries=retries)]
        packs[voice_id] = pack
    return packs


def _author_dossier_self(voice_id: str, species_name: str) -> list[dict[str, Any]]:
    d_self = []
    for std in ["hostile", "neutral", "wary"]:
        d_self.append({
            "when": {"standing": std},
            "variants": [
                f"The {species_name} do not share our history with those we do not trust.",
                "Why should we tell you of our ways, traveler?"
            ]
        })
    categories = [
        ("biology_and_appearance", "biology and appearance"),
        ("psychology_and_culture", "psychology and culture"),
        ("diplomacy_and_behavior", "diplomacy and behavior"),
        ("relationships", "relationships"),
        ("combat_and_ships", "combat and ships"),
    ]
    choices_self = []
    for cat_key, cat_desc in categories:
        choices_self.append({
            "text": f"Tell me about your {cat_desc}.",
            "next_context": f"branch.dossier_self.{cat_key}"
        })
    choices_self.append({
        "text": "Never mind.",
        "next_context": "back"
    })
    d_self.append({
        "variants": [
            f"We are the {species_name}, of {{alliance}}. What would you like to know about us?"
        ],
        "choices": choices_self
    })
    return d_self


def _author_dossier_self_branches(backend: Any, voice_id: str, voice: str, pack: dict[str, list[dict[str, Any]]]) -> None:
    from edge.config import load_default_config
    cfg = load_default_config()
    species = next((s for s in cfg.roster.species if s.id == voice_id), None)
    if not species:
        return

    categories = [
        ("biology_and_appearance", "biology and appearance"),
        ("psychology_and_culture", "psychology and culture"),
        ("diplomacy_and_behavior", "diplomacy and behavior"),
        ("relationships", "relationships"),
        ("combat_and_ships", "combat and ships"),
    ]
    lore = getattr(species, "lore", None) or {}
    targets = _collect_branch_targets(pack)

    for cat_key, cat_desc in categories:
        branch_key = f"branch.dossier_self.{cat_key}"
        if branch_key not in targets:
            continue
        if branch_key in pack:
            continue

        raw_text = getattr(lore, cat_key, f"No record of {species.name} {cat_desc} is available.").strip()
        if backend.__class__.__name__ == "StaticBackend":
            rewritten = raw_text
        else:
            rewritten = _rewrite_self_lore(backend, species.name, voice, cat_desc, raw_text)

        pack[branch_key] = [
            {
                "variants": [rewritten],
                "choices": [
                    {"text": "Go back.", "next_context": "back"}
                ]
            }
        ]


def _rewrite_self_lore(backend: Any, speaker_name: str, speaker_voice: str, cat_desc: str, fact_text: str) -> str:
    prompt = (
        "You are writing dialogue for a space exploration game.\n\n"
        f"SPEAKER SPECIES DETAIL:\n{speaker_voice}\n\n"
        f"FACTUAL DESCRIPTION OF THEIR {cat_desc.upper()}:\n"
        f"\"{fact_text}\"\n\n"
        f"Rewrite this factual description from the perspective of the speaker ({speaker_name}) describing themselves to the player. "
        "Adhere to the speaker's voice/persona. "
        "Keep all the factual details, but express them in the speaker's style and viewpoint. "
        "Keep it concise (1-2 sentences). Do not add any greeting or signoff. "
        "Use {player} for the player, {species} for their species, and {alliance} if needed.\n\n"
        "Output a JSON object {\"rewritten_text\": \"<your rewritten dialogue text>\"}."
    )
    schema = {
        "type": "object",
        "properties": {
            "rewritten_text": {"type": "string"}
        },
        "required": ["rewritten_text"],
        "additionalProperties": False
    }
    import sys
    if backend.__class__.__name__ != "DebugBackend":
        print(f"    (LLM rewriting self {cat_desc} for {speaker_name}...)", file=sys.stderr, flush=True)
    res = backend.generate(prompt, schema=schema)
    return res["rewritten_text"]


def _author_dossier_other(species_name: str) -> list[dict[str, Any]]:
    d_other = []
    for std in ["hostile", "neutral", "wary"]:
        d_other.append({
            "when": {"standing": std},
            "variants": [
                "Why should we tell you about the {subject}?",
                "Ask someone else. We share no data with you."
            ]
        })
    categories = [
        ("biology_and_appearance", "biology and appearance"),
        ("psychology_and_culture", "psychology and culture"),
        ("diplomacy_and_behavior", "diplomacy and behavior"),
        ("relationships", "relationships"),
        ("combat_and_ships", "combat and ships"),
    ]
    choices_other = []
    for cat_key, cat_desc in categories:
        choices_other.append({
            "text": f"Tell me about their {cat_desc}.",
            "next_context": f"branch.dossier_other.{cat_key}"
        })
    choices_other.append({
        "text": "Never mind.",
        "next_context": "back"
    })
    d_other.append({
        "variants": [
            "Ah, the {subject}. We have compiled data on them. What interests you?"
        ],
        "choices": choices_other
    })
    return d_other


def _author_dossier_other_branches(backend: Any, voice_id: str, voice: str, pack: dict[str, list[dict[str, Any]]]) -> None:
    from edge.config import load_default_config
    cfg = load_default_config()
    species = next((s for s in cfg.roster.species if s.id == voice_id), None)
    if not species:
        return

    categories = [
        ("biology_and_appearance", "biology and appearance"),
        ("psychology_and_culture", "psychology and culture"),
        ("diplomacy_and_behavior", "diplomacy and behavior"),
        ("relationships", "relationships"),
        ("combat_and_ships", "combat and ships"),
    ]

    targets = _collect_branch_targets(pack)
    for cat_key, cat_desc in categories:
        branch_key = f"branch.dossier_other.{cat_key}"
        if branch_key not in targets:
            continue
        if branch_key in pack:
            continue

        branch_entries = []
        # For each subject other than the speaker
        for other_sp in cfg.roster.species:
            other_sp_id = other_sp.id
            if other_sp_id == voice_id:
                continue
            other_lore = getattr(other_sp, "lore", None) or {}
            other_raw = getattr(other_lore, cat_key, f"No record of {other_sp.name} {cat_desc} is available.").strip()
            other_desc = other_sp.description or f"a {other_sp.archetype_id} species"

            if backend.__class__.__name__ == "StaticBackend":
                rewritten = f"The {other_sp.name}: {other_raw}"
            else:
                rewritten = _rewrite_other_lore(backend, species.name, voice, other_sp.name, other_desc, cat_desc, other_raw)

            branch_entries.append({
                "when": {
                    "criteria": {
                        "subject": other_sp_id
                    }
                },
                "variants": [rewritten],
                "choices": [
                    {"text": "Go back.", "next_context": "back"}
                ]
            })

        # Catch-all entry for the branch node to satisfy the validator
        branch_entries.append({
            "variants": [
                f"Our database on the {{subject}}'s {cat_desc} is incomplete."
            ],
            "choices": [
                {"text": "Go back.", "next_context": "back"}
            ]
        })
        pack[branch_key] = branch_entries


def _rewrite_other_lore(backend: Any, speaker_name: str, speaker_voice: str, subject_name: str, subject_desc: str, cat_desc: str, fact_text: str) -> str:
    prompt = (
        "You are writing dialogue for a space exploration game.\n\n"
        f"SPEAKER SPECIES DETAIL:\n{speaker_voice}\n\n"
        f"SUBJECT SPECIES: {subject_name}\n"
        f"SUBJECT DESCRIPTION: {subject_desc}\n\n"
        f"FACTUAL DESCRIPTION OF THE {subject_name.upper()} {cat_desc.upper()}:\n"
        f"\"{fact_text}\"\n\n"
        f"Rewrite this factual description from the perspective of the speaker ({speaker_name}) describing the subject ({subject_name}) to the player. "
        "Adhere to the speaker's voice/persona and their relationship/attitude toward the subject. "
        "Keep all the factual details, but express them in the speaker's style and viewpoint. "
        "Keep it concise (1-2 sentences). Do not add any greeting or signoff. "
        "Use {subject} to refer to the subject species, {player} for the player, and {alliance} if needed.\n\n"
        "Output a JSON object {\"rewritten_text\": \"<your rewritten dialogue text>\"}."
    )
    schema = {
        "type": "object",
        "properties": {
            "rewritten_text": {"type": "string"}
        },
        "required": ["rewritten_text"],
        "additionalProperties": False
    }
    import sys
    if backend.__class__.__name__ != "DebugBackend":
        print(f"    (LLM rewriting other {cat_desc} about {subject_name} for {speaker_name}...)", file=sys.stderr, flush=True)
    res = backend.generate(prompt, schema=schema)
    return res["rewritten_text"]
