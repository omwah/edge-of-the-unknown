"""Closed structural glyph alphabet and geometric transforms."""

from __future__ import annotations

from collections.abc import Mapping

ROTATION_FALLBACK = "◇"
BRIGHT_CHARS = frozenset("█■")
DARK_CHARS = frozenset("▒░")
MID_CHARS = frozenset(
    "▖▗▘▝▚▞▟▙▜▛▓▄▀▌▐╾╼╽╿╻╹╺╸─│◢◣◥◤▴▾"
    "╭╮╰╯┌┐└┘├┤┬┴┼▤▦═║╔╗╚╝╠╣╦╩╬"
    "╡╢╖╕╜╛╧╨╤╥╙╘╒╓╫╪╞╟▬▮╱╲"
)
HULL_CHARS = BRIGHT_CHARS | DARK_CHARS | MID_CHARS

AUTHORING_GLYPHS: tuple[tuple[str, str], ...] = (
    (" ", "Void"),
    ("█", "Bright plating"),
    ("■", "Bright plating"),
    ("▓", "Mid plating"),
    ("▒", "Dark plating"),
    ("░", "Deep recess"),
    ("▄", "Lower half"),
    ("▀", "Upper half"),
    ("▌", "Left half"),
    ("▐", "Right half"),
    ("▖", "Lower-left quarter"),
    ("▗", "Lower-right quarter"),
    ("▘", "Upper-left quarter"),
    ("▝", "Upper-right quarter"),
    ("▚", "Diagonal split"),
    ("▞", "Diagonal split"),
    ("▟", "Bevel"),
    ("▙", "Bevel"),
    ("▜", "Bevel"),
    ("▛", "Bevel"),
    ("◢", "Facet edge"),
    ("◣", "Facet edge"),
    ("◥", "Facet edge"),
    ("◤", "Facet edge"),
    ("╭", "Rounded corner"),
    ("╮", "Rounded corner"),
    ("╰", "Rounded corner"),
    ("╯", "Rounded corner"),
    ("─", "Light beam"),
    ("│", "Light beam"),
    ("═", "Heavy beam"),
    ("║", "Heavy beam"),
    ("╾", "Tapered beam"),
    ("╼", "Tapered beam"),
    ("╽", "Tapered beam"),
    ("╿", "Tapered beam"),
    ("╻", "Heavy half beam"),
    ("╹", "Heavy half beam"),
    ("╺", "Heavy half beam"),
    ("╸", "Heavy half beam"),
    ("┌", "Corner"),
    ("┐", "Corner"),
    ("└", "Corner"),
    ("┘", "Corner"),
    ("├", "Junction"),
    ("┤", "Junction"),
    ("┬", "Junction"),
    ("┴", "Junction"),
    ("┼", "Cross junction"),
    ("▤", "Structural hull"),
    ("▦", "Structural hull"),
    ("╔", "Double corner"),
    ("╗", "Double corner"),
    ("╚", "Double corner"),
    ("╝", "Double corner"),
    ("╠", "Double junction"),
    ("╣", "Double junction"),
    ("╦", "Double junction"),
    ("╩", "Double junction"),
    ("╬", "Double cross junction"),
    ("╞", "Mixed junction"),
    ("╟", "Mixed junction"),
    ("╡", "Mixed junction"),
    ("╢", "Mixed junction"),
    ("╖", "Mixed corner"),
    ("╕", "Mixed corner"),
    ("╜", "Mixed corner"),
    ("╛", "Mixed corner"),
    ("╧", "Mixed junction"),
    ("╨", "Mixed junction"),
    ("╤", "Mixed junction"),
    ("╥", "Mixed junction"),
    ("╙", "Mixed corner"),
    ("╘", "Mixed corner"),
    ("╒", "Mixed corner"),
    ("╓", "Mixed corner"),
    ("╫", "Mixed cross junction"),
    ("╪", "Mixed cross junction"),
    ("▬", "Heavy beam"),
    ("▮", "Vertical heavy beam"),
    ("▶", "Muzzle"),
    ("◀", "Muzzle"),
    ("►", "Muzzle"),
    ("◄", "Muzzle"),
    ("▴", "Muzzle"),
    ("▾", "Muzzle"),
    ("↑", "Arrow"),
    ("↓", "Arrow"),
    ("→", "Arrow"),
    ("←", "Arrow"),
    ("↔", "Double arrow"),
    ("↕", "Double arrow"),
    ("▲", "Muzzle"),
    ("▼", "Muzzle"),
    ("╱", "Diagonal"),
    ("╲", "Diagonal"),
    ("◇", "Facet"),
    ("◆", "Facet"),
    ("◊", "Facet"),
    ("☉", "Facet"),
    ("°", "Facet"),
    ("≡", "Facet"),
    ("◘", "Facet"),
    ("◙", "Facet"),
    ("☼", "Facet"),
    ("•", "Facet"),
    ("○", "Facet"),
    ("♥", "Facet"),
    ("♦", "Facet"),
    ("♣", "Facet"),
    ("♠", "Facet"),
    ("∩", "Facet"),
    ("∞", "Facet"),
    ("⌐", "Facet"),
    ("¬", "Facet"),
)

# Keep these as derived UI views of the stable REXPaint authoring alphabet.  Space
# stays with shaded glyphs because it is the canvas eraser even though it has no
# rendered color; every other non-hull glyph uses the facet palette slot.
SHADED_AUTHORING_GLYPHS: tuple[tuple[str, str], ...] = tuple(
    entry for entry in AUTHORING_GLYPHS if entry[0] == " " or entry[0] in HULL_CHARS
)
FACET_AUTHORING_GLYPHS: tuple[tuple[str, str], ...] = tuple(
    entry for entry in AUTHORING_GLYPHS if entry not in SHADED_AUTHORING_GLYPHS
)


def _cycles(*cycles: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for cycle in cycles:
        for index, glyph in enumerate(cycle):
            result[glyph] = cycle[(index + 1) % len(cycle)]
    return result


# Each value is the source glyph rotated 90 degrees counter-clockwise.
ROTATE_CCW: dict[str, str] = {
    **_cycles(
        "─│",
        "═║",
        "╾╽╼╿",
        "╻╺╹╸",
        "▄▐▀▌",
        "▖▗▝▘",
        "▚▞",
        "▟▜▛▙",
        "◢◥◤◣",
        "╭╰╯╮",
        "┌└┘┐",
        "├┴┤┬",
        "╔╚╝╗",
        "╠╩╣╦",
        "╞╨╢╥",
        "╟╧╡╤",
        "╖╒╘╛",
        "╕╓╙╜",
        "╫╪",
        "▶▴◀▾",
        "►▲◄▼",
        "→↑←↓",
        "↔↕",
        "▬▮",
        "╱╲",
    ),
}
for _glyph in " █■▓▒░◇◆◊☉°◘◙☼•○♥♦♣♠∩∞⌐¬┼▤▦╬":
    ROTATE_CCW[_glyph] = _glyph
ROTATE_CCW["≡"] = "║"


HORIZONTAL_FLIP: dict[str, str] = {}
for _left, _right in (
    ("▟", "▙"),
    ("▜", "▛"),
    ("▖", "▗"),
    ("▘", "▝"),
    ("▚", "▞"),
    ("╾", "╼"),
    ("╽", "╽"),
    ("╿", "╿"),
    ("╺", "╸"),
    ("◢", "◣"),
    ("◥", "◤"),
    ("╭", "╮"),
    ("╰", "╯"),
    ("┌", "┐"),
    ("└", "┘"),
    ("├", "┤"),
    ("╔", "╗"),
    ("╚", "╝"),
    ("╠", "╣"),
    ("╞", "╢"),
    ("╟", "╡"),
    ("╖", "╓"),
    ("╕", "╒"),
    ("╜", "╘"),
    ("╛", "╙"),
    ("▶", "◀"),
    ("►", "◄"),
    ("→", "←"),
    ("▴", "▴"),
    ("▾", "▾"),
    ("▲", "▲"),
    ("▼", "▼"),
    ("▌", "▐"),
    ("╱", "╲"),
):
    HORIZONTAL_FLIP[_left] = _right
    HORIZONTAL_FLIP[_right] = _left


VERTICAL_FLIP: dict[str, str] = {}
for _top, _bottom in (
    ("▟", "▜"),
    ("▙", "▛"),
    ("▖", "▘"),
    ("▗", "▝"),
    ("▚", "▞"),
    ("╽", "╿"),
    ("╻", "╹"),
    ("◢", "◥"),
    ("◣", "◤"),
    ("╭", "╰"),
    ("╮", "╯"),
    ("┌", "└"),
    ("┐", "┘"),
    ("╔", "╚"),
    ("╗", "╝"),
    ("╦", "╩"),
    ("╖", "╜"),
    ("╕", "╛"),
    ("╒", "╘"),
    ("╓", "╙"),
    ("╧", "╤"),
    ("╨", "╥"),
    ("┬", "┴"),
    ("▴", "▾"),
    ("▲", "▼"),
    ("↑", "↓"),
    ("▄", "▀"),
    ("╱", "╲"),
):
    VERTICAL_FLIP[_top] = _bottom
    VERTICAL_FLIP[_bottom] = _top


def transform_glyph(
    glyph: str,
    table: Mapping[str, str],
    fallback: str | None = None,
) -> str:
    if glyph in table:
        return table[glyph]
    return glyph if fallback is None else fallback


def flip_rows_horizontal(rows: list[str]) -> list[str]:
    return [
        "".join(HORIZONTAL_FLIP.get(glyph, glyph) for glyph in reversed(row))
        for row in rows
    ]


def flip_rows_vertical(rows: list[str]) -> list[str]:
    return [
        "".join(VERTICAL_FLIP.get(glyph, glyph) for glyph in row)
        for row in reversed(rows)
    ]
