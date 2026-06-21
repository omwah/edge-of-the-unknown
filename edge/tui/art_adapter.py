"""Bridge between the game's typed DTOs and the standalone `edge.art` engine.

`edge.art` is a pure, Rich-based procedural sprite library that knows *nothing*
about the game (its vocabulary is its own: ship/port/planet/terrain/starfield
subtypes and a palette per archetype id). This module is the **only** TUI seam
that imports it, and the single place that maps the game's display strings and
config vocabulary onto the art engine's names. Keeping that mapping here lets the
art engine stay independent — it can be reused, re-skinned, or swapped without
touching game code — and gives the runtime check and the coverage tests one
source of truth.

The art engine emits `rich.text.Text`; the SectorView renders those sprites
directly (see `edge.tui.widgets.ArtView`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from edge.art.generator import (
    available_archetypes,
    available_subtypes,
    generate_sprite,
)

if TYPE_CHECKING:
    from edge.core.config import GameConfig


# --- game vocabulary -> art subtype ----------------------------------------

# Ship `role` (config ShipClassConfig.role) -> art (entity_type, subtype). The
# `starbase` role has no *ship* sprite -- a starbase is a *port* subtype -- so it
# routes to the port generator (DESIGN §4: starbases are immobile ship classes).
_ROLE_ENTITY: dict[str, tuple[str, str]] = {
    "transport": ("ship", "transport"),
    "fighter": ("ship", "fighter"),
    "warship": ("ship", "warship"),
    "capital_warship": ("ship", "capital_warship"),
    "starbase": ("port", "starbase"),
}

# Keyword fallback for free-text ship *names* (the dummy `SectorDTO.ships` strings
# carry no role) -> a ship art subtype. Order matters: first match wins.
_SHIP_NAME_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("capital_warship", ("capital", "dreadnought", "imperial", "battleship")),
    ("warship", ("warship", "cruiser", "destroyer", "frigate", "escort")),
    ("fighter", ("fighter", "raider", "marauder", "interceptor", "scout")),
    ("transport", ("freighter", "trader", "merchant", "hauler", "transport")),
)


def planet_subtype(ptype: str) -> str:
    """The art planet subtype for a config `planet_type` (a 1:1 pass-through)."""
    return ptype


def planet_subtype_from_name(name: str) -> str:
    """Best-effort planet subtype from a free-text planet *name* (no ptype to hand).

    Used by the sector scene, whose `SectorDTO.planets` are display strings only;
    screens with a real `PlanetDTO.ptype` use `planet_subtype` directly.
    """
    low = name.lower()
    for sub in available_subtypes("planet"):
        if sub in low or sub.replace("_", " ") in low:
            return sub
    if "asteroid" in low or "belt" in low:
        return "asteroid_belt"
    if "gas" in low or "jovian" in low or "giant" in low:
        return "jovian"
    if "barren" in low or "rock" in low or "dead" in low:
        return "barren"
    return "terrestrial_warm"


def port_subtype(klass: str) -> str:
    """The art port subtype for a port's display class string (e.g. "Class 4 (BBS)")."""
    return "stardock" if "stardock" in klass.lower() else "trading_port"


def ship_entity(role_or_name: str) -> tuple[str, str]:
    """(entity_type, subtype) for a ship `role`, or a free-text ship-name fallback."""
    key = role_or_name.strip().lower()
    if key in _ROLE_ENTITY:
        return _ROLE_ENTITY[key]
    for subtype, words in _SHIP_NAME_KEYWORDS:
        if any(w in key for w in words):
            return ("ship", subtype)
    return ("ship", "fighter")  # the art engine's own ship default


# --- sprite generation ------------------------------------------------------


def sprite(
    entity_type: str,
    subtype: str,
    *,
    seed: int,
    width: int,
    height: int,
    archetype_id: str | None = None,
    facing: str = "right",
) -> Text:
    """A procedural sprite as a Rich `Text` (a thin wrapper over the art engine)."""
    return generate_sprite(
        entity_type, subtype, seed, width, height, archetype_id, facing
    )


# --- runtime coverage check -------------------------------------------------


def validate_art_coverage(config: GameConfig) -> None:
    """Raise if any roster species names an `archetype_id` the art engine can't paint.

    Run at game startup (see `EdgeApp`) so roster/art drift fails fast and
    deterministically rather than silently falling back to the default palette.
    A roster-less config (no aliens placed) is a no-op.
    """
    if config.roster is None:
        return
    palettes = set(available_archetypes())
    missing = [
        (sp.id, sp.archetype_id)
        for sp in config.roster.species
        if sp.archetype_id not in palettes
    ]
    if missing:
        detail = ", ".join(f"{sid} -> {aid!r}" for sid, aid in missing)
        raise ValueError(
            "alien roster references archetype_ids with no art palette: "
            f"{detail}. Available palettes: {sorted(palettes)}"
        )


__all__ = [
    "available_archetypes",
    "available_subtypes",
    "planet_subtype",
    "planet_subtype_from_name",
    "port_subtype",
    "ship_entity",
    "sprite",
    "validate_art_coverage",
]
