"""Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.

A grammar line carries a compact Tracery rule map (`symbol -> expansions`) authored offline
by an LLM; at runtime a small grammar yields combinatorial variety without any model in the
client. `expand` flattens the grammar from its `origin` symbol, merging in shared
persona/global fragments (`RosterConfig.grammar`).

**Determinism.** pytracery draws from the process-global `random` module. We seed it from a
derived **string** seed (stable across processes, like `select.encounter_rng`) and restore
the prior global state, so expansion is reproducible from `(seed, command log)` without
disturbing the game's own seeded RNG. Tracery's `#symbol#` / `[k:v]` syntax never uses
`{}`, so `{placeholder}` tokens pass through untouched and are filled afterwards by the
selector.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

import tracery

# The symbol every dialogue grammar expands from.
ORIGIN = "origin"

# How many distinct phrasings a grammar line offers the recency ring. Each index seeds a
# different expansion; the ring rotates the index so repeats rephrase. Must exceed the ring
# depth `k` (default 2) so a fresh index always exists — 8 leaves comfortable headroom.
GRAMMAR_VARIANTS = 8


def expand(rules: Mapping[str, Sequence[str]], *,
           shared: Mapping[str, Sequence[str]] | None = None,
           seed: str, origin: str = ORIGIN) -> str:
    """Deterministically expand a Tracery grammar to one string (§6.7).

    `rules` are the line's own `symbol -> expansions`; `shared` are persona/global fragments
    merged underneath (line rules win on key collision). Reproducible: the global `random`
    state is saved, seeded from `seed`, and restored, so the game RNG is untouched.
    """
    merged: dict[str, list[str]] = {k: list(v) for k, v in (shared or {}).items()}
    merged.update({k: list(v) for k, v in rules.items()})
    grammar = tracery.Grammar(merged)
    state = random.getstate()
    try:
        random.seed(seed)
        return str(grammar.flatten(f"#{origin}#"))
    finally:
        random.setstate(state)


def grammar_strings(rules: Mapping[str, Sequence[str]]) -> list[str]:
    """Every authored expansion string in a grammar (for placeholder validation)."""
    return [s for expansions in rules.values() for s in expansions]
