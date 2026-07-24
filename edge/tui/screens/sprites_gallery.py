"""SpriteGalleryScreen — a secret preview of every procedural sprite.

A dev/review screen (not part of the player flow) reachable by a hidden key on the
Main Menu. It sweeps the standalone `edge.art` engine (via `edge.tui.art_adapter`)
and lays out one card per subtype for each entity kind — planets, ports, ships,
discoveries, terrain — plus two kinds the `edge.art` engine doesn't generate: the
hand-drawn engine-room subsystem icons, and the GroundWar expedition field-sketch
art (`edge.groundwar.findart`) used for archaeological finds on a planet descent.
Art cards render the engine's own colours verbatim; only the subsystem icons are
tinted.

These are static *presentation* assets, not game state, so this screen talks to the
art layer directly; no service boundary is crossed.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical

from edge.tui.chrome import EdgeScreen
from textual.widgets import Footer, Static, TabbedContent, TabPane

from edge.art.generator import available_subtypes
from edge.core.surface_finds import FIND_KINDS
from edge.groundwar.findart import generate_find_art
from edge.tui import art_adapter, sprites

_GALLERY_SEED = 7  # fixed so the gallery is reproducible across runs


class _SpriteCard(Vertical):
    """One sprite: its key as a caption above the art.

    The key is a content line (not a border title) so narrow sprites don't truncate
    it — the card's auto width grows to fit the label. Hand-drawn (mono) art is
    tinted via an inline `styles.color` rather than markup so glyphs render verbatim;
    procedural Rich `Text` art carries its own colour and is shown untinted.
    """

    DEFAULT_CSS = """
    _SpriteCard {
        width: auto; height: auto; border: round $primary; padding: 0 1;
    }
    _SpriteCard .card-key {
        width: auto; height: 1; color: $text-muted; text-style: bold;
    }
    _SpriteCard .card-art { width: auto; height: auto; }
    """

    def __init__(self, art: Text | list[str], label: str, color: str | None = None) -> None:
        super().__init__()
        self._art = art
        self._label = label
        self._color = color

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="card-key")
        body = self._art if isinstance(self._art, Text) else "\n".join(self._art)
        art = Static(body, classes="card-art")
        if self._color is not None:  # tint only the mono (list[str]) icons
            art.styles.color = self._color
        yield art


class SpriteGalleryScreen(EdgeScreen):
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

    # (tab label, tab id, art entity_type, sprite w, h, columns).
    _SECTIONS: list[tuple[str, str, str, int, int, int]] = [
        ("Planets", "planets", "planet", 22, 11, 3),
        ("Ports", "ports", "port", 18, 8, 3),
        ("Ships", "ships", "ship", 20, 6, 3),
        ("Discoveries", "discoveries", "discovery", 20, 10, 3),
        ("Terrain", "terrain", "terrain", 30, 8, 2),
    ]

    def compose(self) -> ComposeResult:
        yield Static("SPRITE GALLERY · procedural art assets", id="gallery-title")
        with TabbedContent(initial="planets"):
            for label, tab_id, entity, sw, sh, cols in self._SECTIONS:
                with TabPane(label, id=tab_id):
                    grid = Grid(classes="section-grid")
                    grid.styles.grid_size_columns = cols
                    with grid:
                        for subtype in available_subtypes(entity):
                            spr = art_adapter.sprite(
                                entity, subtype, seed=_GALLERY_SEED, width=sw, height=sh)
                            yield _SpriteCard(spr, subtype)
            with TabPane("Field Finds", id="field_finds"):
                grid = Grid(classes="section-grid")
                grid.styles.grid_size_columns = 2
                with grid:
                    for key in FIND_KINDS:
                        art = generate_find_art(key, _GALLERY_SEED)
                        yield _SpriteCard(art, key)
            with TabPane("Subsystems", id="subsystems"):
                grid = Grid(classes="section-grid")
                grid.styles.grid_size_columns = 4
                with grid:
                    for key, lines in sprites.SUBSYSTEMS.items():
                        yield _SpriteCard(lines, key, sprites.SUBSYSTEM_COLORS.get(key, "cyan"))
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()
