"""Every game-side ship/port/planet/archetype must have an art sprite.

These guard the seam between the game config/roster and the standalone `edge.art`
engine (bridged by `edge.tui.art_adapter`): they fail loudly if the config grows a
ship role, port class, planet type, or species archetype the art engine can't draw,
so art coverage can never silently regress to the engine's fallbacks.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from edge.art.generator import available_archetypes, available_subtypes
from edge.config import load_default_config
from edge.core.enums import PortClass
from edge.tui import art_adapter

CONFIG = load_default_config()


def test_planet_types_have_sprites() -> None:
    planet_subtypes = set(available_subtypes("planet"))
    assert planet_subtypes, "the art engine reports no planet subtypes"
    for ptype in CONFIG.planets.types:
        assert art_adapter.planet_subtype(ptype) in planet_subtypes, ptype


def test_port_classes_map_to_sprites() -> None:
    port_subtypes = set(available_subtypes("port"))
    for pc in PortClass:
        # Ordinary ports route by their "Class N" display label; the Stardock is
        # routed separately (by name in the sector list / a hardcoded subtype).
        intended = "stardock" if pc is PortClass.STARDOCK else "trading_port"
        assert intended in port_subtypes, pc
        if pc is not PortClass.STARDOCK:
            assert art_adapter.port_subtype(f"Class {pc.value}") == intended
    # The Stardock is identified by its port name in the sector listing.
    assert art_adapter.port_subtype("Stardock Alpha") == "stardock"


def test_ship_roles_have_sprites() -> None:
    roles = {CONFIG.starter_ship.role} | {c.role for c in CONFIG.ship_classes}
    assert "transport" in roles  # sanity: the starter hull is a transport
    for role in roles:
        entity, subtype = art_adapter.ship_entity(role)
        assert subtype in set(available_subtypes(entity)), role


def test_starbase_role_routes_to_a_port_sprite() -> None:
    # DESIGN §4: a starbase is an (immobile) ship class, but the art engine files
    # `starbase` under *port* subtypes -- the adapter must bridge that gap.
    entity, subtype = art_adapter.ship_entity("starbase")
    assert (entity, subtype) == ("port", "starbase")
    assert subtype in set(available_subtypes(entity))


def test_roster_archetypes_have_palettes() -> None:
    assert CONFIG.roster is not None, "default config ships a roster"
    palettes = set(available_archetypes())
    for sp in CONFIG.roster.species:
        assert sp.archetype_id in palettes, f"{sp.id} -> {sp.archetype_id}"


def test_every_game_type_actually_renders() -> None:
    # Smoke: each mapped subtype produces a non-empty sprite (catches a subtype that
    # the adapter names but the engine can't compose).
    for ptype in CONFIG.planets.types:
        spr = art_adapter.sprite("planet", art_adapter.planet_subtype(ptype),
                                 seed=1, width=20, height=10)
        assert spr.plain.strip(), ptype
    roles = {CONFIG.starter_ship.role} | {c.role for c in CONFIG.ship_classes}
    for role in roles:
        entity, subtype = art_adapter.ship_entity(role)
        spr = art_adapter.sprite(entity, subtype, seed=1, width=18, height=6)
        assert spr.plain.strip(), role


def test_validate_art_coverage_passes_on_default_config() -> None:
    art_adapter.validate_art_coverage(CONFIG)  # must not raise


def test_validate_art_coverage_is_a_noop_without_a_roster() -> None:
    art_adapter.validate_art_coverage(SimpleNamespace(roster=None))  # type: ignore[arg-type]


def test_validate_art_coverage_raises_on_unknown_archetype() -> None:
    bad = SimpleNamespace(roster=SimpleNamespace(
        species=[SimpleNamespace(id="rogue", archetype_id="no_such_palette")]))
    with pytest.raises(ValueError, match="no_such_palette"):
        art_adapter.validate_art_coverage(bad)  # type: ignore[arg-type]
