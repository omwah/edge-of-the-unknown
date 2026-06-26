"""Salience dialogue selection (DESIGN §6.7) — pure, no I/O.

A species' conversation is **data**, not code: its roster `dialogue_pack` maps the closed
vocabulary of **intent** keys (greeting, trade_open, dossier_other, …) to lists of
conditional **line entries**. Each entry carries a `when` predicate and a pool of
interchangeable **variants**. Selection follows the Valve "AI-driven dynamic dialog"
(Ruskin, GDC 2012) / salience-based-narrative pattern: assemble a **fact dictionary** from
the encounter state, score every entry whose criteria all hold by how *specific* it is
(how many facts it pins), and let the **most-specific matching entry win** — ties broken by
`weight` through the seeded RNG. The selector then:

  1. resolves the line by falling back up the chain **species → persona → generic**, so a
     sparse roster entry still speaks in its persona's voice and a missing line never blanks;
  2. among the winning pack, keeps the most-specific matching entry (Ruskin scoring);
  3. draws a variant from the chosen entry's pool **excluding the last K shown** (a small
     recency ring, `roster.recency_k`), so repeat encounters rephrase rather than replay;
  4. fills `{placeholders}` from an interaction-context dict.

`standing` and `treaty` are ordinary fact keys, so the Phase-2 friendly path ports
unchanged; Phase 3 adds richer facts (player needs, intel availability) without touching the
matcher. Selection routes through the seeded RNG and the persisted recency ring, so dialogue
is reproducible from `(seed, command log)` — yet it is purely cosmetic, reporting outcomes
the rules have already decided.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping, Sequence
from string import Formatter

from edge.core.aliens import FRIENDLY, HOSTILE, NEUTRAL, disposition_band, effective_disposition
from edge.core.config import AliensConfig, DialogueLine, DialoguePack, RosterConfig, SpeciesConfig
from edge.core.models import AlienSpecies, Player
from edge.dialogue import render
from edge.dialogue.intents import (
    BRANCH_PREFIX,
    CHOICE_ACTIONS,
    DIALOGUE_CONTEXTS,
    PEACEFUL_CONTEXTS,
    allowed_placeholders,
    is_known_context,
)

GENERIC_PERSONA = "generic"

# Standing bands a `when.standing` can name (DESIGN §6.7). `allied` when the player shares
# the species' alliance; `wary` is authored-but-inert in Phase 2 (never computed).
ALLIED = "allied"
WARY = "wary"
STANDINGS = frozenset({ALLIED, FRIENDLY, NEUTRAL, WARY, HOSTILE})

# Re-export so external callers (server projection, rules) keep a single import surface.
__all__ = [
    "ALLIED", "FRIENDLY", "NEUTRAL", "WARY", "HOSTILE", "STANDINGS", "GENERIC_PERSONA",
    "DIALOGUE_CONTEXTS", "PEACEFUL_CONTEXTS", "DialogueIntegrityError", "allowed_placeholders",
    "standing_for", "build_chain", "select_line", "select_entry", "entry_for", "when_matches",
    "fill", "encounter_rng", "speak", "reachable_contexts", "validate_dialogue",
]


class DialogueIntegrityError(Exception):
    """A roster's dialogue packs fail the §13 integrity checks."""


# --- standing & predicate scoring ------------------------------------------------

def standing_for(effective: float, *, allied: bool, aliens: AliensConfig) -> str:
    """Bucket an effective disposition into a standing band (allied overrides, §6.7)."""
    if allied:
        return ALLIED
    return disposition_band(effective, aliens)  # hostile / neutral / friendly


def _score(when: object, facts: Mapping[str, object]) -> int | None:
    """Specificity of an entry whose criteria all hold, or `None` if it doesn't match.

    Specificity = the number of facts the `when` pins (standing + treaty + each general
    `criteria` key). Phase 2 cannot evaluate the forward-compat `posture` / `stage` fields,
    so an entry that sets either is **excluded** (it is a Phase-3 line) rather than matched.
    """
    if getattr(when, "posture", None) is not None or getattr(when, "stage", None) is not None:
        return None
    score = 0
    standing = getattr(when, "standing", None)
    if standing is not None:
        if standing != facts.get("standing"):
            return None
        score += 1
    treaty = getattr(when, "treaty", None)
    if treaty is not None:
        if treaty != facts.get("treaty"):
            return None
        score += 1
    for key, want in getattr(when, "criteria", {}).items():
        if facts.get(key) != want:
            return None
        score += 1
    return score


# --- selection -------------------------------------------------------------------

def build_chain(roster: RosterConfig, species: SpeciesConfig | None,
                persona: str) -> list[DialoguePack]:
    """The species → persona → generic fallback chain of packs (§6.7)."""
    chain: list[DialoguePack] = []
    if species is not None and species.dialogue_pack:
        chain.append(species.dialogue_pack)
    persona_pack = roster.personas.get(persona)
    if persona_pack:
        chain.append(persona_pack)
    generic = roster.personas.get(GENERIC_PERSONA)
    if generic:
        chain.append(generic)
    return chain


def _fill(template: str, ctx: Mapping[str, str]) -> str:
    """Fill `{placeholders}` from `ctx`; unknown placeholders render empty (never crash)."""
    class _Safe(dict[str, str]):
        def __missing__(self, key: str) -> str:
            return ""
    return template.format_map(_Safe(ctx))


def fill(template: str, ctx: Mapping[str, str]) -> str:
    """Public placeholder fill (e.g. for an authored choice label); see `_fill`."""
    return _fill(template, ctx)


def when_matches(when: object, *, standing: str, treaty: bool,
                 facts: Mapping[str, object] | None = None) -> bool:
    """Whether a `when` predicate holds for a standing/treaty + extra facts (§6.7).

    The boolean form of `_score`: used to gate an authored player `choice` (both the
    read-only projection and the reducer evaluate a choice's `when` the same way).
    """
    all_facts: dict[str, object] = {"standing": standing, "treaty": treaty}
    if facts:
        all_facts.update(facts)
    return _score(when, all_facts) is not None


def _pick_index(n: int, recency: tuple[int, ...], rng: random.Random) -> int:
    """An index in [0, n) avoiding the recency ring (falling back to the full range)."""
    fresh = [i for i in range(n) if i not in recency]
    return rng.choice(fresh or list(range(n)))


def _realise(entry: DialogueLine, *, ctx: Mapping[str, str], recency: tuple[int, ...],
             rng: random.Random, shared: Mapping[str, Sequence[str]] | None) -> tuple[str, int]:
    """Render one entry to (filled text, chosen ring index).

    A `grammar` entry expands a Tracery grammar seeded from the RNG (the ring index rotates
    the phrasing); a `variants` entry picks a phrasing avoiding the ring. Either way the
    chosen index is returned so the caller advances the recency ring.
    """
    if entry.grammar:
        idx = _pick_index(render.GRAMMAR_VARIANTS, recency, rng)
        raw = render.expand(entry.grammar, shared=shared, seed=f"{rng.getrandbits(32)}|{idx}")
        return _fill(raw, ctx), idx
    idx = _pick_index(len(entry.variants), recency, rng)
    return _fill(entry.variants[idx], ctx), idx


def select_line(chain: Sequence[DialoguePack], context: str, *, standing: str,
                treaty: bool, ctx: Mapping[str, str], recency: tuple[int, ...],
                rng: random.Random, k: int = 2,
                facts: Mapping[str, object] | None = None,
                shared: Mapping[str, Sequence[str]] | None = None) -> tuple[str, tuple[int, ...]]:
    """Resolve and render one line for `context`, returning (text, updated recency ring).

    Walks the fallback chain; the first pack with any matching entry for `context` wins.
    Within that pack the **most-specific** matching entry wins (Ruskin scoring), ties broken
    by `weight` through the seeded RNG. Picks a variant avoiding the last `k` indices, fills
    placeholders, and returns the new recency ring (the caller persists it per
    (species, context)). `standing`/`treaty` seed the fact dictionary; `facts` adds any
    further encounter facts (player needs, intel availability — Phase 3). Returns
    ("", recency) only if nothing resolves — the validator guarantees this cannot happen for
    a reachable context.
    """
    entry = select_entry(chain, context, standing=standing, treaty=treaty, rng=rng, facts=facts)
    if entry is None:
        return "", recency
    text, idx = _realise(entry, ctx=ctx, recency=recency, rng=rng, shared=shared)
    new_recency = (*recency, idx)[-k:] if k > 0 else ()
    return text, new_recency


def select_entry(chain: Sequence[DialoguePack], context: str, *, standing: str,
                 treaty: bool, rng: random.Random,
                 facts: Mapping[str, object] | None = None) -> DialogueLine | None:
    """Resolve the winning line **entry** for `context` (no realisation, no ring advance).

    The shared salience walk behind `select_line`: the first pack in the chain with any
    matching entry for `context` wins, then the most-specific matching entry (Ruskin
    scoring), ties broken by `weight` through the seeded RNG. Returns None if nothing
    resolves. Lets the reducer and the read-only projection read an entry's authored
    `choices` deterministically (same RNG inputs ⇒ same winner as the shown line).
    """
    all_facts: dict[str, object] = {"standing": standing, "treaty": treaty}
    if facts:
        all_facts.update(facts)
    for pack in chain:
        entries = pack.get(context)
        if not entries:
            continue
        scored = [(s, e) for e in entries if (s := _score(e.when, all_facts)) is not None]
        if not scored:
            continue
        best = max(s for s, _ in scored)
        winners = [e for s, e in scored if s == best]
        return rng.choices(winners, weights=[e.weight for e in winners], k=1)[0]
    return None


def encounter_rng(seed: int, species_key: str, context: str,
                  recency: tuple[int, ...]) -> random.Random:
    """A deterministic RNG for line selection, reproducible under (seed, command log).

    Seeded from the game seed, the species **kind** (`roster_id`), the context, and the
    current recency ring, so the projection (read-only) and the reducer (which advances the
    ring) agree on the line, and replay reproduces it exactly. Keying by kind means every
    ship of a species draws from one shared, non-repeating dialogue ring. A **string** seed
    is used deliberately — `random.Random` derives it via SHA-512, which is stable across
    processes (unlike the hash-randomised `hash()` of a tuple), keeping replay exact.
    """
    return random.Random(f"{seed}|{species_key}|{context}|{recency}")


def speak(roster: RosterConfig, species: AlienSpecies, player: Player, context: str, *,
          aliens: AliensConfig, rng: random.Random,
          extra: Mapping[str, str] | None = None,
          treaty: bool = False,
          facts: Mapping[str, object] | None = None) -> tuple[str, tuple[int, ...]]:
    """Convenience: select a line for a live encounter and return (text, new recency ring).

    Resolves the species' standing from its effective disposition (Phase 2: friendly /
    allied), builds the pack chain, seeds the interaction context with the common
    `{player}` / `{species}` / `{alliance}` placeholders, and reads the current recency
    ring from the player. The caller stores the returned ring at `(roster_id, context)`.
    """
    sc = roster.species_by_id(species.roster_id)
    chain = build_chain(roster, sc, species.persona)
    allied = player.alliance_id is not None and player.alliance_id == species.alliance_id
    standing = standing_for(effective_disposition(species, player), allied=allied, aliens=aliens)
    alliance = roster.alliance(species.alliance_id) if species.alliance_id is not None else None
    ctx: dict[str, str] = {
        "player": player.name, "species": species.name,
        "alliance": alliance.name if alliance else "the unaligned",
    }
    if extra:
        ctx.update(extra)
    recency = player.dialogue_recency.get((species.roster_id, context), ())
    return select_line(chain, context, standing=standing, treaty=treaty, ctx=ctx,
                       recency=recency, rng=rng, k=roster.recency_k, facts=facts,
                       shared=roster.grammar)


def entry_for(roster: RosterConfig, species: AlienSpecies, player: Player, context: str, *,
              aliens: AliensConfig, rng: random.Random, treaty: bool = False,
              facts: Mapping[str, object] | None = None) -> DialogueLine | None:
    """The winning line **entry** for a live encounter context (read-only; for `choices`).

    The `select_entry` counterpart of `speak`: resolves the species' standing and pack chain
    and returns the entry, consuming `rng` exactly as `speak`/`select_line` do up to the
    winner pick — so seeding the same `encounter_rng` yields the entry whose line was shown.
    """
    sc = roster.species_by_id(species.roster_id)
    chain = build_chain(roster, sc, species.persona)
    allied = player.alliance_id is not None and player.alliance_id == species.alliance_id
    standing = standing_for(effective_disposition(species, player), allied=allied, aliens=aliens)
    return select_entry(chain, context, standing=standing, treaty=treaty, rng=rng, facts=facts)


# --- validation (DESIGN §13 dialogue integrity) ----------------------------------

def reachable_contexts(species: SpeciesConfig) -> frozenset[str]:
    """The friendly-path contexts a species can reach in Phase 2 (per its params, §6.7)."""
    keys = set(PEACEFUL_CONTEXTS)
    if species.trade_posture == "refuses":
        keys.discard("trade_open")
    else:
        keys.discard("trade_refuse")
    if species.treaty_mode in {"none", "superfluous"}:
        keys -= {"treaty_offer", "treaty_grant", "treaty_condition", "treaty_refuse"}
    return frozenset(keys)


def _placeholders_in(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name}


def _branch_closure(chain: Sequence[DialoguePack], base: frozenset[str]) -> set[str]:
    """The contexts reachable from `base` by following choices' `next_context` (and farewell).

    Lets validation prove that every branch node a species can reach through its authored
    choices resolves a non-empty line — the branch-graph extension of the catch-all invariant.
    """
    seen = set(base)
    frontier = list(base)
    while frontier:
        ctx = frontier.pop()
        for pack in chain:
            for entry in pack.get(ctx, []):
                for choice in entry.choices:
                    nxt = "farewell" if choice.action == "farewell" else choice.next_context
                    if nxt and nxt not in seen:
                        seen.add(nxt)
                        frontier.append(nxt)
    return seen


def _entry_strings(entry: DialogueLine) -> list[str]:
    """Every authored template string in an entry (variant pool + grammar expansions)."""
    return list(entry.variants) + render.grammar_strings(entry.grammar)


def validate_dialogue(roster: RosterConfig) -> None:
    """Assert the §13 dialogue-integrity invariants for a roster (raises on failure).

    - the `generic` persona exists and carries a **catch-all** entry for every base
      context key, so resolution never blanks for any standing/treaty state;
    - every context key (any pack) is in the closed vocabulary, a `sig.*`, or a `branch.*`;
    - every variant's (and authored choice label's) placeholders are fillable for its context;
    - every authored player `choice` names a valid `action` (CHOICE_ACTIONS) and a known
      `next_context`; every `branch.*` node is reachable (targeted by some `next_context`);
    - every species' `persona` resolves to a persona pack;
    - every species resolves a non-empty pool for each context it can reach (Phase 2) —
      **including** branch nodes reached through choices — with `dossier_other` parameterised
      by `{subject}` so it covers every nameable species.
    """
    generic = roster.personas.get(GENERIC_PERSONA)
    if not generic:
        raise DialogueIntegrityError("roster has no 'generic' persona pack")

    # Context-key vocabulary + placeholder fillability across every authored pack.
    packs: list[tuple[str, DialoguePack]] = [(f"persona {p}", pk) for p, pk in roster.personas.items()]
    packs += [(f"species {s.id}", s.dialogue_pack) for s in roster.species if s.dialogue_pack]
    branch_targets: set[str] = set()  # every `next_context` any choice points at
    for label, pack in packs:
        for context, entries in pack.items():
            if not is_known_context(context):
                raise DialogueIntegrityError(f"{label}: unknown context key {context!r}")
            allowed = allowed_placeholders(context)
            for entry in entries:
                for variant in _entry_strings(entry):
                    bad = _placeholders_in(variant) - allowed
                    if bad:
                        raise DialogueIntegrityError(
                            f"{label}/{context}: unfillable placeholder(s) {sorted(bad)} in {variant!r}"
                        )
                for choice in entry.choices:
                    bad = _placeholders_in(choice.text) - allowed
                    if bad:
                        raise DialogueIntegrityError(
                            f"{label}/{context}: unfillable placeholder(s) {sorted(bad)} in "
                            f"choice {choice.text!r}"
                        )
                    if choice.action is not None and choice.action not in CHOICE_ACTIONS:
                        raise DialogueIntegrityError(
                            f"{label}/{context}: unknown choice action {choice.action!r}"
                        )
                    if choice.next_context is not None:
                        if not is_known_context(choice.next_context):
                            raise DialogueIntegrityError(
                                f"{label}/{context}: choice targets unknown context "
                                f"{choice.next_context!r}"
                            )
                        branch_targets.add(choice.next_context)

    # No orphan branch nodes: a `branch.*` context exists only as a choice target, so an
    # unreferenced one is dead config (and would never be reachable in game).
    branch_node_source: dict[str, str] = {
        ctx: label for label, pack in packs for ctx in pack if ctx.startswith(BRANCH_PREFIX)
    }
    for node in sorted(set(branch_node_source) - branch_targets):
        raise DialogueIntegrityError(
            f"branch node {node!r} is unreachable (no choice targets it)"
            f" — defined in {branch_node_source[node]}"
        )

    # The generic pack must carry an unconditional catch-all for every base context.
    for context in DIALOGUE_CONTEXTS:
        catch_all = generic.get(context)
        if not catch_all or not any(_is_catch_all(e.when) for e in catch_all):
            raise DialogueIntegrityError(f"generic persona missing a catch-all '{context}' line")

    # `dossier_other` must be parameterised so one line narrates any subject species.
    if not any("subject" in _placeholders_in(v)
               for e in generic["dossier_other"] for v in _entry_strings(e)):
        raise DialogueIntegrityError("generic dossier_other is not parameterised by {subject}")

    # Per-species: persona resolves, and every reachable context yields a line in all
    # the standings Phase 2 (and Phase 3) can present.
    probe = random.Random(0)
    for sp in roster.species:
        if sp.persona not in roster.personas:
            raise DialogueIntegrityError(f"species {sp.id!r} uses unknown persona {sp.persona!r}")
        chain = build_chain(roster, sp, sp.persona)
        for context in _branch_closure(chain, reachable_contexts(sp)):
            ctx = {p: p for p in allowed_placeholders(context)}
            for standing in (ALLIED, FRIENDLY, NEUTRAL, HOSTILE):
                for treaty in (False, True):
                    text, _ = select_line(chain, context, standing=standing, treaty=treaty,
                                          ctx=ctx, recency=(), rng=probe, k=roster.recency_k,
                                          shared=roster.grammar)
                    if not text:
                        raise DialogueIntegrityError(
                            f"species {sp.id!r} resolves no '{context}' line "
                            f"(standing={standing}, treaty={treaty})"
                        )


def _is_catch_all(when: object) -> bool:
    return (
        all(getattr(when, f, None) is None for f in ("standing", "treaty", "posture", "stage"))
        and not getattr(when, "criteria", {})
    )


def dialogue_fingerprint(roster: RosterConfig) -> str:
    """A 16-hex-char hash of the choice-cardinality structure across all species packs.

    Fingerprints only the per-(species, context) choice counts — the one thing
    `_converse_choice` depends on for replay. Used by `GameService` to detect a
    save/config mismatch before attempting command-log replay, which would otherwise
    fail mid-way with "no such reply" if a sidecar has changed.
    """
    structure: dict[str, dict[str, list[int]]] = {}
    for sp in roster.species:
        counts = {
            ctx: [len(e.choices) for e in entries if e.choices]
            for ctx, entries in sp.dialogue_pack.items()
            if any(e.choices for e in entries)
        }
        if counts:
            structure[sp.id] = counts
    return hashlib.sha256(
        json.dumps(structure, sort_keys=True).encode()
    ).hexdigest()[:16]
