"""Phase-3 — location-intel planner + species knowledge table (DESIGN §6.7).

Covers `edge.dialogue.intel`: the generation-time knowledge table (determinism, bounds,
referential integrity) and `pick_intel_target` (disposition gating, the unencountered-only
filter, route reachability, and placeholder bindings).
"""

from __future__ import annotations

from dataclasses import replace

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.models import Player, Ship
from edge.core.movement import shortest_path
from edge.dialogue.intel import KNOWN_PER_SPECIES, build_species_knowledge, pick_intel_target

CFG = load_default_config()
# A 400-sector universe reaches the Deep/Void bands, so rare+ finds exist to tip about.
WIDE = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 400})})


def _state():  # type: ignore[no-untyped-def]
    return generate(WIDE, 7)


def _speaker_with_knowledge(state):  # type: ignore[no-untyped-def]
    """A placed species whose kind knows at least one place, plus a fresh player+ship."""
    sp = next(s for s in state.species.values() if state.species_knowledge.get(s.roster_id))
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="X", owner_player_id=1,
                          sector_id=1, holds_total=10)
    player = Player(id=1, name="Cap", ship_id=1, latinum=0)
    return sp, player


# --- the knowledge table ---------------------------------------------------------

def test_species_knowledge_is_deterministic_bounded_and_referential() -> None:
    a, b = generate(WIDE, 7), generate(WIDE, 7)
    assert a.species_knowledge == b.species_knowledge
    assert a.species_knowledge  # every present kind has an entry
    assert set(a.species_knowledge) == {s.roster_id for s in a.species.values()}
    for refs in a.species_knowledge.values():
        assert len(refs) <= KNOWN_PER_SPECIES
        for r in refs:
            entity = a.discoveries.get(r.ref) if r.kind == "discovery" else a.starbases.get(r.ref)
            assert entity is not None and entity.sector_id == r.sector_id

    # A different seed yields a different assignment (not a constant table).
    assert generate(WIDE, 8).species_knowledge != a.species_knowledge


def test_rebuild_helper_matches_generation() -> None:
    state = generate(WIDE, 7)
    assert build_species_knowledge(state, 7) == state.species_knowledge


# --- pick_intel_target -----------------------------------------------------------

def test_friendly_speaker_offers_a_reachable_unencountered_tip() -> None:
    state = _state()
    sp, player = _speaker_with_knowledge(state)
    player = replace(player, species_attitudes={sp.roster_id: 1.0})  # force friendly band
    target = pick_intel_target(state, player, sp, aliens=CFG.aliens)
    assert target is not None
    assert target.ref.sector_id not in player.explored_sectors  # unencountered
    assert shortest_path(state.adjacency, 1, target.ref.sector_id) is not None  # reachable
    b = target.bindings()
    assert b.keys() == {"target", "coords", "distance", "band", "reward"}
    assert all(b.values()) and target.summary()


def test_hostile_and_neutral_speakers_offer_nothing() -> None:
    state = _state()
    sp, player = _speaker_with_knowledge(state)
    hostile = replace(sp, base_disposition=0.1, alliance_id=None)
    neutral = replace(sp, base_disposition=0.5, alliance_id=None)
    bare = replace(player, species_attitudes={}, alliance_id=None)
    assert pick_intel_target(state, bare, hostile, aliens=CFG.aliens) is None
    assert pick_intel_target(state, bare, neutral, aliens=CFG.aliens) is None


def test_explored_or_logged_places_are_never_revealed() -> None:
    state = _state()
    sp, player = _speaker_with_knowledge(state)
    player = replace(player, species_attitudes={sp.roster_id: 1.0})
    assert pick_intel_target(state, player, sp, aliens=CFG.aliens) is not None
    # Explore every sector the kind knows about → it has nothing new to share.
    known = {r.sector_id for r in state.species_knowledge[sp.roster_id]}
    seen = replace(player, explored_sectors=frozenset(known))
    assert pick_intel_target(state, seen, sp, aliens=CFG.aliens) is None


# --- WP36: the roaming Entity as a live pursuit tip (§7) --------------------------

def test_knowledge_table_never_bakes_the_entity_codex_row() -> None:
    """The reserved Entity codex row is Legendary but must never enter a knowledge table —
    the Entity roams, so its tip is computed live, not baked (§7, WP35/WP36)."""
    from edge.core.enums import DiscoveryKind

    state = _state()
    for refs in state.species_knowledge.values():
        for r in refs:
            if r.kind == "discovery":
                assert state.discoveries[r.ref].kind is not DiscoveryKind.ENTITY


def test_entity_tip_is_live_and_outranks_regular_tips() -> None:
    from edge.core.discovery import entity_species

    state = _state()
    sp, player = _speaker_with_knowledge(state)
    player = replace(player, species_attitudes={sp.roster_id: 1.0})  # friendly band
    ent = entity_species(state, CFG)
    assert ent is not None
    target = pick_intel_target(state, player, sp, aliens=CFG.aliens, entity=ent)
    assert target is not None and target.ref.kind == "entity"
    assert target.ref.sector_id == ent.sector_id  # its CURRENT sector, computed live (H3)
    assert target.label == "the roaming Entity" and target.summary()


def test_entity_tip_reoffers_only_after_it_moves() -> None:
    from edge.core.discovery import entity_species
    from edge.core.models import Lead

    state = _state()
    sp, player = _speaker_with_knowledge(state)
    player = replace(player, species_attitudes={sp.roster_id: 1.0})
    ent = entity_species(state, CFG)
    assert ent is not None
    # A fresh lead to where it is now suppresses the Entity tip (a regular tip may surface).
    player = replace(player, leads=(Lead(kind="entity", ref=ent.id, sector_id=ent.sector_id,
                     origin_sector=1, source_species=sp.roster_id, summary="last known"),))
    held = pick_intel_target(state, player, sp, aliens=CFG.aliens, entity=ent)
    assert held is None or held.ref.kind != "entity"
    # Once it moves, the frozen lead no longer matches its sector → a fresh tip is re-offered.
    dst = next(n for n in state.adjacency[ent.sector_id]
               if not state.sectors[n].is_galactic_core)
    moved = replace(ent, sector_id=dst)
    again = pick_intel_target(state, player, sp, aliens=CFG.aliens, entity=moved)
    assert again is not None and again.ref.kind == "entity" and again.ref.sector_id == dst
