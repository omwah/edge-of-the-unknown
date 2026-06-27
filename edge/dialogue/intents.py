"""Dialogue **intents**, grouped by core game concept (DESIGN §6.7).

An *intent* is a unit of conversational meaning — what a speaker is trying to convey —
organised by the game concept it belongs to (trade / discovery / diplomacy / …) rather
than assembled from sentence fragments. Each intent declares the **placeholders** a line
realising it may reference, so the validator can prove every authored variant is fillable.

This module is the closed vocabulary the selector and the authoring pipeline share. It is
the generalisation of the old flat ``DIALOGUE_CONTEXTS`` tuple: the context keys are the
same strings, now carrying a `concept` grouping and an explicit placeholder set. New
intents (e.g. the location-tip `offer_coordinates`) slot in by adding one `Intent` here.

Pure data — no I/O, no RNG.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Game concepts an intent can belong to (DESIGN §6.7 — "core game concepts, not fragments").
TRADE = "trade"
DISCOVERY = "discovery"
DIPLOMACY = "diplomacy"
ENCOUNTER = "encounter"  # refuel / extort / demand / reward / combat — the meeting itself
LORE = "lore"  # dossiers — who the speaker is and what it knows of others

# Placeholders every line may use regardless of intent (DESIGN §6.7 templates).
UNIVERSAL_PLACEHOLDERS = frozenset({"player", "species", "alliance"})

# Signature-mechanic prompt placeholders (Phase 3 `sig.*` contexts), validated separately.
SIG_PLACEHOLDERS = frozenset({"subject", "count", "reward", "coords", "item"})

# The mechanical verbs an authored player `choice` may carry (DESIGN §6.7 branching). A
# choice with no `action` is a pure conversation transition (it just moves to `next_context`).
# `attack` is recognised but Phase-3-gated (rejected by the reducer in Phase 2).
CHOICE_ACTIONS = frozenset({"leave", "trade", "barter", "accept_lead", "attack"})

# Reserved namespace for authored intermediate **branch nodes** — context keys that exist
# only as conversation-graph targets (reached via a choice's `next_context`), distinct from
# the closed intent vocabulary. Mirrors the `sig.*` prompt namespace.
BRANCH_PREFIX = "branch."


@dataclass(frozen=True, slots=True)
class Intent:
    """One conversational beat: its concept, extra placeholders, and Phase-2 reachability.

    `placeholders` are the per-intent names *in addition to* the universal set. `peaceful`
    marks the Phase-2 friendly-path intents a contact can reach (combat / sig.* are Phase 3).
    """

    key: str
    concept: str
    placeholders: frozenset[str] = frozenset()
    peaceful: bool = True


# The closed intent catalogue (DESIGN §6.7). Order is documentation-only; the keys are the
# stable vocabulary. Grouped by concept so authoring prompts can speak of "trade lines",
# "diplomacy lines", etc., rather than an undifferentiated context list.
_INTENTS: tuple[Intent, ...] = (
    # --- diplomacy ---------------------------------------------------------------
    Intent("greeting", DIPLOMACY),
    Intent("treaty_offer", DIPLOMACY),
    Intent("treaty_grant", DIPLOMACY),
    Intent("treaty_condition", DIPLOMACY, frozenset({"subject", "count"})),
    Intent("treaty_refuse", DIPLOMACY),
    Intent("farewell", DIPLOMACY),
    # --- trade -------------------------------------------------------------------
    Intent("trade_open", TRADE),
    Intent("trade_refuse", TRADE),
    # --- discovery (the location-tip "map" mechanic, §6.7) -----------------------
    Intent("offer_coordinates", DISCOVERY,
           frozenset({"target", "coords", "distance", "band", "reward"})),
    # --- lore / dossiers ---------------------------------------------------------
    Intent("dossier_self", LORE),
    Intent("dossier_other", LORE, frozenset({"subject"})),
    # --- encounter (the meeting itself) ------------------------------------------
    Intent("refuel", ENCOUNTER),
    Intent("extort_response", ENCOUNTER),
    Intent("demand", ENCOUNTER, frozenset({"subject", "count", "reward", "coords"})),
    Intent("reward", ENCOUNTER, frozenset({"subject", "count", "reward"})),
    # --- combat / betrayal — authored-but-inert until Phase 3 --------------------
    Intent("combat_open", ENCOUNTER, peaceful=False),
    Intent("combat_taunt", ENCOUNTER, frozenset({"subject"}), peaceful=False),
    Intent("surrender", ENCOUNTER, peaceful=False),
    Intent("flee_scorn", ENCOUNTER, peaceful=False),
    Intent("betrayal", ENCOUNTER, frozenset({"subject"}), peaceful=False),
)

INTENTS: Mapping[str, Intent] = {i.key: i for i in _INTENTS}

# Back-compat alias for the old flat vocabulary name (the closed set of base context keys).
DIALOGUE_CONTEXTS: tuple[str, ...] = tuple(INTENTS)

# The Phase-2 friendly-path contexts a contact can reach (combat / sig.* are Phase 3).
PEACEFUL_CONTEXTS: frozenset[str] = frozenset(k for k, i in INTENTS.items() if i.peaceful)


def allowed_placeholders(context: str) -> frozenset[str]:
    """The placeholder names a variant of `context` may use (validator + authoring)."""
    if context.startswith("sig.") or context.startswith(BRANCH_PREFIX):
        # Branch nodes are authored set-pieces; allow the same rich placeholder set as the
        # signature-mechanic prompts (subject / item / coords / …) on top of the universals.
        return UNIVERSAL_PLACEHOLDERS | SIG_PLACEHOLDERS
    intent = INTENTS.get(context)
    extra = intent.placeholders if intent is not None else frozenset()
    return UNIVERSAL_PLACEHOLDERS | extra


def is_known_context(context: str) -> bool:
    """Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace, or is 'back'."""
    return context in INTENTS or context.startswith("sig.") or context.startswith(BRANCH_PREFIX) or context == "back"
