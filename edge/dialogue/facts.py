"""Shared dialogue fact assembly (DESIGN §6.7, WP28) — pure, no I/O, no RNG.

The **one** place the fact dictionary fed to `DialogueWhen.criteria` is assembled, used
identically by the `Converse` reducer (`core.rules`) and the read-only contact projection
(`server.session`), so the view/reducer lockstep holds (H4/H8): the same player state
produces the same facts, hence the same winning entry and the same reply menu on both
sides. Reducers also come here to *write* the per-contact session (`ensure_session` /
`note_topic` / `note`), keeping the session-fact vocabulary in one module.

Session facts (the WP28 vocabulary; all authored `criteria` keys):

- ``asked.<context>: true``  — the context was spoken earlier *this visit* (set for every
  spoken context, so an entry can react to being asked the same thing twice);
- ``traded: true``           — the player bought or bartered a tech offer this visit;
- ``accepted_lead: true``    — the player logged a coordinate tip this visit.

Situational facts (band, sector features, hull state, `just_fled_combat`, …) join this
module in WP29; persisted cross-visit arc facts in WP30.
"""

from __future__ import annotations

from collections.abc import Mapping

from edge.core.models import AlienSpecies, ContactSession, Player, UniverseState

# Session-fact keys (the closed WP28 vocabulary — documented in the corpus spec header).
TOPIC_PREFIX = "asked."
TRADED = "traded"
ACCEPTED_LEAD = "accepted_lead"


# --- session writing (reducer-side helpers) ---------------------------------------

def ensure_session(player: Player, species: AlienSpecies, sector_id: int) -> ContactSession:
    """The live session for this species instance, or a fresh one (a new visit).

    A session held for a *different* species (the player turned to another contact
    without moving) is replaced — a visit is with one ship.
    """
    session = player.contact_session
    if session is not None and session.species_id == species.id:
        return session
    return ContactSession(species_id=species.id, sector_id=sector_id)


def note_topic(session: ContactSession, context: str) -> ContactSession:
    """Record that `context` was spoken this visit (`asked.<context>: true`)."""
    return note(session, f"{TOPIC_PREFIX}{context}")


def note(session: ContactSession, key: str, value: object = True) -> ContactSession:
    """The session with one fact recorded (a no-op when it already holds)."""
    if session.facts.get(key) == value:
        return session
    return ContactSession(species_id=session.species_id, sector_id=session.sector_id,
                          facts={**session.facts, key: value})


# --- fact assembly (the reducer/projection lockstep seam) --------------------------

def session_facts(player: Player, species: AlienSpecies) -> dict[str, object]:
    """The facts the live contact session contributes (empty when none, or another's)."""
    session = player.contact_session
    if session is None or session.species_id != species.id:
        return {}
    return dict(session.facts)


def contact_facts(state: UniverseState, player: Player, species: AlienSpecies, *,
                  extra: Mapping[str, object] | None = None) -> dict[str, object]:
    """The full fact dictionary for one dialogue selection (§6.7).

    Layered: the per-contact session facts (this module), then the caller's
    context-specific extras (`subject`, `has_intel_target`, …) on top. `state` is
    accepted now so the WP29 situational layer (band, sector features, hull state)
    slots in without touching any call site. Both the `Converse` reducer and the
    contact projection MUST build their facts here — never assemble ad hoc.
    """
    facts: dict[str, object] = session_facts(player, species)
    if extra:
        facts.update(extra)
    return facts
