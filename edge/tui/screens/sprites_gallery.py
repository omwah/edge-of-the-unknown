"""SpriteGalleryScreen — a secret preview of every sprite asset.

A dev/review screen (not part of the player flow) reachable by a hidden key on
the Main Menu. It lays out every sprite in `edge.tui.sprites` — planets (scene
markers and large orbit views), ports, ships, and engine-room subsystem icons —
one category per tab, each sprite in a labelled card tinted with its category
colour.

Sprites are static *presentation* assets, not game state, so this screen reads
them straight from the asset module rather than from a DTO; no service boundary
is crossed. Each card colours its art via an inline `styles.color` (never
`[colour]…[/]` markup) so glyphs render verbatim — several planet/ship sprites
end in a backslash, which would otherwise escape a trailing close tag.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static, TabbedContent, TabPane

from edge.tui import sprites


class _SpriteCard(Vertical):
    """One sprite: its key as a caption above the art, which is tinted with its
    category colour. The key is a content line (not a border title) so narrow
    sprites don't truncate it — the card's auto width grows to fit the label."""

    DEFAULT_CSS = """
    _SpriteCard {
        width: auto; height: auto; border: round $primary; padding: 0 1;
    }
    _SpriteCard .card-key {
        width: auto; height: 1; color: $text-muted; text-style: bold;
    }
    _SpriteCard .card-art { width: auto; height: auto; }
    """

    def __init__(self, lines: list[str], color: str, label: str) -> None:
        super().__init__()
        self._lines = lines
        self._color = color
        self._label = label

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="card-key")
        # Colour the art via an inline style rather than markup so the glyphs
        # render verbatim (several sprites end in '\', which would escape a
        # trailing close tag).
        art = Static("\n".join(self._lines), classes="card-art")
        art.styles.color = self._color
        yield art


class SpriteGalleryScreen(Screen):
    BINDINGS = [Binding("escape", "back", "Back")]

    CSS = """
    SpriteGalleryScreen #gallery-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    SpriteGalleryScreen TabPane { padding: 1 2; }
    SpriteGalleryScreen .section-grid {
        grid-gutter: 0 1; grid-rows: auto; height: auto;
    }
    """

    # (tab label, tab id, sprite dict, colour, columns). `None` colour means use
    # SUBSYSTEM_COLORS per key; otherwise the whole category shares one tint. The
    # column count keeps each card within the 100-col width — the large orbit
    # views need to wrap onto two rows.
    _SECTIONS: list[tuple[str, str, dict[str, list[str]], str | None, int]] = [
        ("Planets", "planets", sprites.PLANETS, "cyan", 4),
        ("Orbit Views", "orbit", sprites.PLANETS_LARGE, "cyan", 2),
        ("Ports", "ports", sprites.PORTS, "magenta", 2),
        ("Ships", "ships", sprites.SHIPS, "white", 5),
        ("Subsystems", "subsystems", sprites.SUBSYSTEMS, None, 4),
    ]

    def compose(self) -> ComposeResult:
        yield Static("SPRITE GALLERY · all sprite assets", id="gallery-title")
        with TabbedContent(initial="planets"):
            for label, tab_id, table, color, cols in self._SECTIONS:
                with TabPane(label, id=tab_id):
                    grid = Grid(classes="section-grid")
                    grid.styles.grid_size_columns = cols
                    with grid:
                        for key, lines in table.items():
                            tint = color or sprites.SUBSYSTEM_COLORS.get(key, "cyan")
                            yield _SpriteCard(lines, tint, key)
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()
