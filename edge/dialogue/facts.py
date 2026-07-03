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

Situational facts (the WP29 vocabulary — the live circumstances, always present so an
author can pin either polarity; booleans are real ``true``/``false``, buckets are strings):

- ``band``               — the sector's distance band name (e.g. ``Hub`` / ``Frontier``);
- ``in_nebula``          — a nebula shrouds this sector;
- ``wreck_here``         — a visible (obvious or detected), uncollected wreck lies here;
- ``hull``               — ``critical`` (≤25%) / ``scarred`` (≤60%) / ``sound``;
- ``low_turns``          — the player is nearly out of turns (< ``LOW_TURNS``);
- ``holds_empty`` / ``holds_full`` — the cargo bay's extremes;
- ``carrying``           — the largest cargo stack's commodity name (only when laden);
- ``just_fled_combat``   — the player fled a fight earlier *today* (from
  ``Player.last_combat``, the record combat reducers write — H5, never UI memory).

Persisted cross-visit arc facts join in WP30.
"""

from __future__ import annotations

from collections.abc import Mapping

from edge.core.discovery import sector_has_nebula
from edge.core.enums import DiscoveryKind
from edge.core.models import AlienSpecies, ContactSession, Player, UniverseState

# Session-fact keys (the closed WP28 vocabulary — documented in the corpus spec header).
TOPIC_PREFIX = "asked."
TRADED = "traded"
ACCEPTED_LEAD = "accepted_lead"

# Situational buckets (WP29). Display-style thresholds (like the projection's gauges), not
# economy tunables: authored dialogue only needs coarse, stable strata to react to.
HULL_CRITICAL = 0.25  # hull ratio at or below ⇒ "critical"
HULL_SCARRED = 0.60  # hull ratio at or below ⇒ "scarred" (else "sound")
LOW_TURNS = 25  # turns_remaining below ⇒ `low_turns` (a tenth of the daily 250)


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


def situational_facts(state: UniverseState, player: Player) -> dict[str, object]:
    """The live-circumstance facts (§6.7, WP29) — the module-doc vocabulary.

    Pure and deterministic over core state (H5: `just_fled_combat` reads the
    `Player.last_combat` record combat reducers write, never UI memory). Degrades to
    empty for hand-built states that carry no ship/sector for the player, so the pure
    selector tests and the playtest harness keep working unchanged.
    """
    ship = state.ships.get(player.ship_id)
    if ship is None:
        return {}
    sector = state.sectors.get(ship.sector_id)
    if sector is None:
        return {}
    ratio = ship.hull_current / ship.hull_max if ship.hull_max > 0 else 1.0
    hull = "critical" if ratio <= HULL_CRITICAL else ("scarred" if ratio <= HULL_SCARRED else "sound")
    wreck_here = any(
        d.kind is DiscoveryKind.WRECK and d.planet_id is None and d.found_by is None
        and d.sector_id == ship.sector_id and (not d.hidden or d.id in player.detected)
        for d in state.discoveries.values()
    )
    last = player.last_combat
    facts: dict[str, object] = {
        "band": sector.distance_band,
        "in_nebula": sector_has_nebula(state, ship.sector_id),
        "wreck_here": wreck_here,
        "hull": hull,
        "low_turns": player.turns_remaining < LOW_TURNS,
        "holds_empty": ship.holds_used == 0,
        "holds_full": ship.holds_free <= 0,
        "just_fled_combat": (last is not None and last.outcome == "fled"
                             and last.day == state.game.day_number),
    }
    if ship.cargo and any(ship.cargo.values()):
        top = max(ship.cargo, key=lambda c: ship.cargo[c])
        facts["carrying"] = top.value
    return facts


def contact_facts(state: UniverseState, player: Player, species: AlienSpecies, *,
                  extra: Mapping[str, object] | None = None) -> dict[str, object]:
    """The full fact dictionary for one dialogue selection (§6.7).

    Layered, later layers winning: the situational facts (WP29), the per-contact
    session facts (WP28), then the caller's context-specific extras (`subject`,
    `has_intel_target`, …) on top. Both the `Converse` reducer and the contact
    projection MUST build their facts here — never assemble ad hoc.
    """
    facts: dict[str, object] = situational_facts(state, player)
    facts.update(session_facts(player, species))
    if extra:
        facts.update(extra)
    return facts
