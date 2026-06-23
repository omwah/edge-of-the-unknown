"""Config-driven alien dialogue (DESIGN §6.7) — pure core, no I/O.

A species' conversation is **data**, not code: its roster `dialogue_pack` maps a closed
vocabulary of **context keys** (greeting, trade_open, treaty_grant, dossier_other, …) to
lists of conditional **line entries**. Each entry carries a `when` predicate (matched
against the player's standing band and whether a treaty is in force) and a pool of
interchangeable **variants**. At runtime the selector:

  1. resolves the line by falling back up the chain **species → persona → generic**, so a
     sparse roster entry still speaks in its persona's voice and a missing line never
     blanks the screen;
  2. keeps every entry whose `when` matches the encounter state and picks among them by
     `weight` through the seeded RNG;
  3. draws a variant from the chosen entry's pool **excluding the last K shown** (a small
     recency ring, `roster.recency_k`), so repeat encounters rephrase rather than replay;
  4. fills `{placeholders}` from an interaction-context dict.

Selection routes through the seeded RNG and the persisted recency ring, so dialogue is
reproducible from `(seed, command log)` — yet it is purely cosmetic, reporting outcomes
the rules have already decided. Phase 2 reaches only the friendly-path contexts; combat /
signature-mechanic prompts are authored-but-inert until Phase 3.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from string import Formatter

from edge.core.aliens import FRIENDLY, HOSTILE, NEUTRAL, disposition_band, effective_disposition
from edge.core.config import AliensConfig, DialoguePack, RosterConfig, SpeciesConfig
from edge.core.models import AlienSpecies, Player

GENERIC_PERSONA = "generic"

# Standing bands a `when.standing` can name (DESIGN §6.7). `allied` when the player shares
# the species' alliance; `wary` is authored-but-inert in Phase 2 (never computed).
ALLIED = "allied"
WARY = "wary"
STANDINGS = frozenset({ALLIED, FRIENDLY, NEUTRAL, WARY, HOSTILE})

# The closed base vocabulary of context keys (DESIGN §6.7). Signature-mechanic prompts are
# namespaced `sig.*` and validated separately (Phase 3); these are the always-present beats.
DIALOGUE_CONTEXTS = (
    "greeting", "trade_open", "trade_refuse",
    "treaty_offer", "treaty_grant", "treaty_condition", "treaty_refuse",
    "refuel", "extort_response", "demand", "reward",
    "combat_open", "combat_taunt", "surrender", "flee_scorn", "betrayal",
    "farewell", "dossier_self", "dossier_other",
)

# Placeholders every line may use, plus per-context extras (DESIGN §6.7 templates).
_UNIVERSAL_PLACEHOLDERS = frozenset({"player", "species", "alliance"})
_CONTEXT_PLACEHOLDERS: dict[str, frozenset[str]] = {
    "dossier_other": frozenset({"subject"}),
    "demand": frozenset({"subject", "count", "reward", "coords"}),
    "reward": frozenset({"subject", "count", "reward"}),
    "treaty_condition": frozenset({"subject", "count"}),
    "combat_taunt": frozenset({"subject"}),
    "betrayal": frozenset({"subject"}),
}
_SIG_PLACEHOLDERS = frozenset({"subject", "count", "reward", "coords", "item"})

# The Phase-2 friendly-path contexts a contact can reach (combat / sig.* are Phase 3).
_PEACEFUL_CONTEXTS = frozenset({
    "greeting", "trade_open", "trade_refuse", "treaty_offer", "treaty_grant",
    "treaty_condition", "treaty_refuse", "refuel", "extort_response", "farewell",
    "dossier_self", "dossier_other",
})


class DialogueIntegrityError(Exception):
    """A roster's dialogue packs fail the §13 integrity checks."""


# --- standing & predicate matching -----------------------------------------------

def standing_for(effective: float, *, allied: bool, aliens: AliensConfig) -> str:
    """Bucket an effective disposition into a standing band (allied overrides, §6.7)."""
    if allied:
        return ALLIED
    return disposition_band(effective, aliens)  # hostile / neutral / friendly


def allowed_placeholders(context: str) -> frozenset[str]:
    """The placeholder names a variant of `context` may use (validator + docs)."""
    if context.startswith("sig."):
        return _UNIVERSAL_PLACEHOLDERS | _SIG_PLACEHOLDERS
    return _UNIVERSAL_PLACEHOLDERS | _CONTEXT_PLACEHOLDERS.get(context, frozenset())


def _matches(when: object, standing: str, treaty: bool) -> bool:
    """Whether a line entry's `when` predicate holds for the encounter state.

    Phase 2 evaluates `standing` and `treaty`; the forward-compat `posture` / `stage`
    fields can't be evaluated yet, so an entry that sets either is **excluded** in Phase 2
    (it's a Phase-3 line) rather than matched blindly.
    """
    w = when
    if getattr(w, "posture", None) is not None or getattr(w, "stage", None) is not None:
        return False
    if w.standing is not None and w.standing != standing:  # type: ignore[attr-defined]
        return False
    if w.treaty is not None and w.treaty != treaty:  # type: ignore[attr-defined]
        return False
    return True


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


def _pick_variant(variants: Sequence[str], recency: tuple[int, ...],
                  rng: random.Random) -> int:
    """A variant index avoiding the recency ring (falling back to the full pool)."""
    fresh = [i for i in range(len(variants)) if i not in recency]
    return rng.choice(fresh or list(range(len(variants))))


def select_line(chain: Sequence[DialoguePack], context: str, *, standing: str,
                treaty: bool, ctx: Mapping[str, str], recency: tuple[int, ...],
                rng: random.Random, k: int = 2) -> tuple[str, tuple[int, ...]]:
    """Resolve and render one line for `context`, returning (text, updated recency ring).

    Walks the fallback chain; the first pack with a `when`-matching entry for `context`
    wins. Picks an entry by weight, a variant avoiding the last `k` indices, fills
    placeholders, and returns the new recency ring (the caller persists it per
    (species, context)). Returns ("", recency) only if nothing resolves — the validator
    guarantees this cannot happen for a reachable context.
    """
    for pack in chain:
        entries = pack.get(context)
        if not entries:
            continue
        matching = [e for e in entries if _matches(e.when, standing, treaty)]
        if not matching:
            continue
        entry = rng.choices(matching, weights=[e.weight for e in matching], k=1)[0]
        idx = _pick_variant(entry.variants, recency, rng)
        text = _fill(entry.variants[idx], ctx)
        new_recency = (*recency, idx)[-k:] if k > 0 else ()
        return text, new_recency
    return "", recency


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
          treaty: bool = False) -> tuple[str, tuple[int, ...]]:
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
                       recency=recency, rng=rng, k=roster.recency_k)


# --- validation (DESIGN §13 dialogue integrity) ----------------------------------

def reachable_contexts(species: SpeciesConfig) -> frozenset[str]:
    """The friendly-path contexts a species can reach in Phase 2 (per its params, §6.7)."""
    keys = set(_PEACEFUL_CONTEXTS)
    if species.trade_posture == "refuses":
        keys.discard("trade_open")
    else:
        keys.discard("trade_refuse")
    if species.treaty_mode in {"none", "superfluous"}:
        keys -= {"treaty_offer", "treaty_grant", "treaty_condition", "treaty_refuse"}
    return frozenset(keys)


def _placeholders_in(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name}


def validate_dialogue(roster: RosterConfig) -> None:
    """Assert the §13 dialogue-integrity invariants for a roster (raises on failure).

    - the `generic` persona exists and carries a **catch-all** entry for every base
      context key, so resolution never blanks for any standing/treaty state;
    - every context key (any pack) is in the closed vocabulary or a `sig.*` prompt;
    - every variant's placeholders are fillable for its context;
    - every species' `persona` resolves to a persona pack;
    - every species resolves a non-empty pool for each context it can reach (Phase 2),
      with `dossier_other` parameterised by `{subject}` so it covers every nameable species.
    """
    generic = roster.personas.get(GENERIC_PERSONA)
    if not generic:
        raise DialogueIntegrityError("roster has no 'generic' persona pack")

    # Context-key vocabulary + placeholder fillability across every authored pack.
    packs: list[tuple[str, DialoguePack]] = [(f"persona {p}", pk) for p, pk in roster.personas.items()]
    packs += [(f"species {s.id}", s.dialogue_pack) for s in roster.species if s.dialogue_pack]
    for label, pack in packs:
        for context, entries in pack.items():
            if context not in DIALOGUE_CONTEXTS and not context.startswith("sig."):
                raise DialogueIntegrityError(f"{label}: unknown context key {context!r}")
            allowed = allowed_placeholders(context)
            for entry in entries:
                for variant in entry.variants:
                    bad = _placeholders_in(variant) - allowed
                    if bad:
                        raise DialogueIntegrityError(
                            f"{label}/{context}: unfillable placeholder(s) {sorted(bad)} in {variant!r}"
                        )

    # The generic pack must carry an unconditional catch-all for every base context.
    for context in DIALOGUE_CONTEXTS:
        catch_all = generic.get(context)
        if not catch_all or not any(_is_catch_all(e.when) for e in catch_all):
            raise DialogueIntegrityError(f"generic persona missing a catch-all '{context}' line")

    # `dossier_other` must be parameterised so one line narrates any subject species.
    if not any("subject" in _placeholders_in(v) for e in generic["dossier_other"] for v in e.variants):
        raise DialogueIntegrityError("generic dossier_other is not parameterised by {subject}")

    # Per-species: persona resolves, and every reachable context yields a line in all
    # the standings Phase 2 (and Phase 3) can present.
    probe = random.Random(0)
    for sp in roster.species:
        if sp.persona not in roster.personas:
            raise DialogueIntegrityError(f"species {sp.id!r} uses unknown persona {sp.persona!r}")
        chain = build_chain(roster, sp, sp.persona)
        for context in reachable_contexts(sp):
            ctx = {p: p for p in allowed_placeholders(context)}
            for standing in (ALLIED, FRIENDLY, NEUTRAL, HOSTILE):
                for treaty in (False, True):
                    text, _ = select_line(chain, context, standing=standing, treaty=treaty,
                                          ctx=ctx, recency=(), rng=probe, k=roster.recency_k)
                    if not text:
                        raise DialogueIntegrityError(
                            f"species {sp.id!r} resolves no '{context}' line "
                            f"(standing={standing}, treaty={treaty})"
                        )


def _is_catch_all(when: object) -> bool:
    return all(getattr(when, f, None) is None for f in ("standing", "treaty", "posture", "stage"))
