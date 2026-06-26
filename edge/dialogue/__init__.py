"""Alien dialogue (DESIGN §6.7) — a pure, core-level package.

`edge.dialogue` owns the salience-based dialogue system: the intent vocabulary
(`intents`), the criteria-scored selector + recency ring + validator (`select`), and — in
later phases — Tracery realisation (`render`) and the location-intel planner (`intel`). It
imports only the lower `edge.core` modules (models, config, aliens, movement) and is in turn
consumed by `edge.core.rules` and `edge.server`, so the dependency graph stays acyclic and
the dialogue logic stays I/O-free. The dev-only authoring pipeline (`edge.dialogue.authoring`)
is the one impure corner and is never imported from here or from runtime code.
"""

from __future__ import annotations

from edge.dialogue.intents import (
    BRANCH_PREFIX,
    CHOICE_ACTIONS,
    DIALOGUE_CONTEXTS,
    INTENTS,
    PEACEFUL_CONTEXTS,
    Intent,
    allowed_placeholders,
    is_known_context,
)
from edge.dialogue.select import (
    ALLIED,
    FRIENDLY,
    GENERIC_PERSONA,
    HOSTILE,
    NEUTRAL,
    STANDINGS,
    WARY,
    DialogueIntegrityError,
    build_chain,
    dialogue_fingerprint,
    encounter_rng,
    entry_for,
    fill,
    reachable_contexts,
    select_entry,
    select_line,
    speak,
    standing_for,
    validate_dialogue,
    when_matches,
)

# Back-compat alias: external callers historically reached for `dialogue._PEACEFUL_CONTEXTS`.
_PEACEFUL_CONTEXTS = PEACEFUL_CONTEXTS

__all__ = [
    "ALLIED", "FRIENDLY", "NEUTRAL", "WARY", "HOSTILE", "STANDINGS", "GENERIC_PERSONA",
    "DIALOGUE_CONTEXTS", "PEACEFUL_CONTEXTS", "INTENTS", "Intent", "DialogueIntegrityError",
    "allowed_placeholders", "is_known_context", "standing_for", "build_chain", "select_line",
    "select_entry", "entry_for", "when_matches", "fill", "encounter_rng", "speak",
    "reachable_contexts", "validate_dialogue", "CHOICE_ACTIONS", "BRANCH_PREFIX",
    "dialogue_fingerprint",
]
