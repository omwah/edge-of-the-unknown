"""Bridge between the game's typed DTOs and the standalone `edge.art` engine.

`edge.art` is a pure, Rich-based procedural sprite library that knows *nothing*
about the game (its vocabulary is its own: ship/port/planet/terrain/starfield
subtypes and a palette per archetype id). This module is the **only** TUI seam
that imports it, and the single place that maps the game's display strings and
config vocabulary onto the art engine's names. Keeping that mapping here lets the
art engine stay independent — it can be reused, re-skinned, or swapped without
touching game code — and gives the runtime check and the coverage tests one
source of truth.

The art engine emits `rich.text.Text`; `text_to_cells` flattens a sprite into the
per-cell `(char, style)` grid the `SectorScene` composites over its starfield base.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.color import Color
from rich.console import Console
from rich.style import Style
from rich.text import Text

from edge.art.generator import (
    available_archetypes,
    available_subtypes,
    generate_sprite,
)

if TYPE_CHECKING:
    from edge.core.config import GameConfig

# A throwaway console used only to resolve a sprite's authored Rich styles into
# per-cell colours for the SectorScene grid; it never writes anywhere. Truecolor
# keeps named/RGB colours intact rather than downgrading them off a fake tty.
_CONSOLE = Console(color_system="truecolor")


def _truecolor(color: Color | None) -> Color | None:
    """Resolve a (possibly ANSI/named) colour to an explicit RGB triplet colour."""
    return Color.from_triplet(color.get_truecolor()) if color is not None else None


def _to_truecolor(text: Text) -> Text:
    """Re-resolve every style in `text` to explicit truecolor.

    The art palettes use ANSI names (``blue``, ``cyan``, …) meaning the *standard*
    ANSI hues. Textual otherwise remaps those names through its theme's ANSI palette
    (a Monokai-ish one where ``blue`` is a violet), so the rendered sprite drifts
    from the intended colours. Baking each colour to its standard RGB triplet here
    pins the sprite to the art's intent regardless of the active Textual theme,
    while leaving UI markup text (rendered elsewhere) free to follow the theme.
    """
    out = Text()
    lines = text.split(allow_blank=True)
    for i, line in enumerate(lines):
        for seg in line.render(_CONSOLE):
            st = seg.style
            if st is not None:
                st = st + Style.from_color(_truecolor(st.color), _truecolor(st.bgcolor))
            out.append(seg.text, style=st)
        if i < len(lines) - 1:
            out.append("\n")
    return out


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

# Defensive keyword fallback for a free-text ship *name* -> a ship art subtype, used
# only when `ship_entity` is handed a name rather than an authoritative `role`. Order
# matters: first match wins.
_SHIP_NAME_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("capital_warship", ("capital", "dreadnought", "imperial", "battleship")),
    ("warship", ("warship", "cruiser", "destroyer", "frigate", "escort")),
    ("fighter", ("fighter", "raider", "marauder", "interceptor", "scout")),
    ("transport", ("freighter", "trader", "merchant", "hauler", "transport")),
)


def planet_subtype(ptype: str) -> str:
    """The art planet subtype for a config `planet_type` (a 1:1 pass-through)."""
    return ptype


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
    """A procedural sprite as a Rich `Text` (a thin wrapper over the art engine).

    Colours are baked to explicit truecolor so the sprite renders as the art
    intends rather than being re-tinted through the active Textual theme's ANSI
    palette (see `_to_truecolor`).
    """
    return _to_truecolor(generate_sprite(
        entity_type, subtype, seed, width, height, archetype_id, facing
    ))


def text_to_cells(
    text: Text, *, keep_space_style: bool = False
) -> list[list[tuple[str, Style | None]]]:
    """Flatten a Rich `Text` sprite into per-cell `(char, style)` rows for stamping.

    Each cell keeps the art's own resolved colour. By default a space cell carries
    ``None`` so the `SectorScene` compositor treats it as transparent (the starfield
    shows through the sprite's negative space). Set ``keep_space_style`` for an opaque
    sprite — e.g. terrain, whose colour partly lives in the *background* of space
    glyphs — so those backgrounds aren't dropped (rendering as black).
    """
    rows: list[list[tuple[str, Style | None]]] = []
    for line in text.split(allow_blank=True):
        cells: list[tuple[str, Style | None]] = []
        for segment in line.render(_CONSOLE):
            style = segment.style
            for ch in segment.text:
                cells.append((ch, style if (keep_space_style or ch != " ") else None))
        rows.append(cells)
    return rows


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
    "port_subtype",
    "ship_entity",
    "sprite",
    "text_to_cells",
    "validate_art_coverage",
]
