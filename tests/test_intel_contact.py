"""Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7).

Drives `Converse(offer_coordinates)` and `AcceptLead` against an injected friendly species
whose knowledge points at a real, unvisited discovery — proving the alien volunteers a
coordinate tip and the player logs it as a `Lead` (idempotently).
"""

from __future__ import annotations

import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.models import AlienSpecies, LocationRef, UniverseState
from edge.core.movement import shortest_path
from edge.core.rules import AcceptLead, Converse, apply_result, reduce
from edge.dialogue import instance_key
from edge.server import session
from helpers import generate_with_player

CFG = load_default_config()
SMALL = CFG.model_copy(
    update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 120, "start_sector": 1})})


def _inject(state: UniverseState, roster_id: str = "vesk", base: float = 0.9) -> AlienSpecies:
    sc = CFG.roster.species_by_id(roster_id)
    assert sc is not None
    ship = state.ships[1]
    sp = AlienSpecies(
        id=1, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id,
        sector_id=ship.sector_id, home_band="Hub", tech_level=sc.tech_level,
        base_disposition=base, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
        alliance_role=sc.alliance_role, trade_posture=sc.trade_posture,
        treaty_mode=sc.treaty_mode, persona=sc.persona,
    )
    state.species[1] = sp
    return sp


def _knows_a_far_discovery(state: UniverseState, sp: AlienSpecies) -> int:
    """Point the species' knowledge at a real, reachable, unexplored rare+ discovery."""
    ship = state.ships[1]
    player = state.players[1]
    disc = next(
        d for d in state.discoveries.values()
        if d.rarity_tier.value >= 3
        and d.sector_id not in player.explored_sectors
        and d.found_by is None
        and shortest_path(state.adjacency, ship.sector_id, d.sector_id) is not None
    )
    state.species_knowledge[sp.roster_id] = (LocationRef("discovery", disc.id, disc.sector_id),)
    return disc.id


def test_offer_coordinates_then_accept_logs_one_lead() -> None:
    state = generate_with_player(SMALL, 3)
    sp = _inject(state)
    disc_id = _knows_a_far_discovery(state, sp)

    # The alien volunteers the tip (the conversation reducer doesn't crash and advances the ring).
    apply_result(state, reduce(state, 1, Converse(sp.id, "offer_coordinates"), CFG))
    assert state.players[1].dialogue_recency[(instance_key(sp), "offer_coordinates")]

    # Accepting the tip logs exactly one lead pointing at that discovery.
    here = state.ships[state.players[1].ship_id].sector_id
    apply_result(state, reduce(state, 1, AcceptLead(sp.id), CFG))
    leads = state.players[1].leads
    assert len(leads) == 1
    assert leads[0].kind == "discovery" and leads[0].ref == disc_id
    assert leads[0].source_species == sp.roster_id and leads[0].summary
    assert leads[0].origin_sector == here  # the tip records where it was obtained (§6.7)

    # The logged tip is no longer re-offered, so a re-accept finds nothing new.
    with pytest.raises(EconomyError, match="no coordinates"):
        reduce(state, 1, AcceptLead(sp.id), CFG)
    assert len(state.players[1].leads) == 1


def test_contact_view_surfaces_intel_then_leads_view_plots() -> None:
    state = generate_with_player(SMALL, 3)
    sp = _inject(state)
    _knows_a_far_discovery(state, sp)

    view = session.contact_view(state, 1, sp.id, CFG, active_context="offer_coordinates")
    assert view.intel_summary  # a tip is on offer
    assert next(c for c in view.choices if c.action == "accept_lead").enabled
    assert any(ch.isdigit() for ch in view.opener)  # the line carries {coords}

    apply_result(state, reduce(state, 1, AcceptLead(sp.id), CFG))
    rows = session.leads_view(state, 1, CFG)
    assert len(rows) == 1 and rows[0].reachable and rows[0].summary and rows[0].source
    # Logged at the player's current sector, so it plots over the full graph from here (§6.7).
    assert rows[0].at_origin and rows[0].origin_coords >= 0

    # Once logged, the speaker has nothing new — the Log-coordinates reply is gone (the node falls
    # to its "nothing new" catch-all, whose only reply is to back out).
    view2 = session.contact_view(state, 1, sp.id, CFG, active_context="offer_coordinates")
    assert not any(c.action == "accept_lead" and c.enabled for c in view2.choices)


def test_log_coordinates_only_appears_on_the_offer_node() -> None:
    """Log-coordinates is a reply on the offer_coordinates node, not the greeting — you cannot log
    a route the speaker hasn't volunteered on screen."""
    state = generate_with_player(SMALL, 3)
    sp = _inject(state)
    _knows_a_far_discovery(state, sp)  # a tip exists on offer

    # Default (greeting) context: no Log-coordinates reply at all (it lives on the offer node).
    greeting = session.contact_view(state, 1, sp.id, CFG)  # active_context defaults to "greeting"
    assert not any(c.action == "accept_lead" for c in greeting.choices)

    # On the offer_coordinates node, with a tip on offer, the reply is present and enabled.
    asked = session.contact_view(state, 1, sp.id, CFG, active_context="offer_coordinates")
    assert next(c for c in asked.choices if c.action == "accept_lead").enabled


def test_accept_lead_without_a_tip_is_rejected() -> None:
    state = generate_with_player(SMALL, 3)
    sp = _inject(state, base=0.1)  # hostile band → volunteers nothing
    _knows_a_far_discovery(state, sp)
    with pytest.raises(EconomyError, match="no coordinates"):
        reduce(state, 1, AcceptLead(sp.id), CFG)


def test_offer_coordinates_speaks_even_with_no_tip() -> None:
    # A friendly species that knows nowhere new still answers (the catch-all line), no crash.
    state = generate_with_player(SMALL, 3)
    sp = _inject(state)
    state.species_knowledge[sp.roster_id] = ()
    res = reduce(state, 1, Converse(sp.id, "offer_coordinates"), CFG)
    apply_result(state, res)
    assert state.players[1].dialogue_recency[(instance_key(sp), "offer_coordinates")]
    with pytest.raises(EconomyError):
        reduce(state, 1, AcceptLead(sp.id), CFG)  # nothing to accept
