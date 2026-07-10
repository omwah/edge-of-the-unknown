"""HelpScreen — the key reference + warp legend overlay (`?` / Ctrl+H).

WP73: a real keymap (the §4 keymap-normalization decision, D3) — the global
conventions, the main screens' verbs, and the warp colour legend. The per-screen
numbered action menu (`.`) lists exactly what the *current* screen can do; this
overlay is the study-at-leisure companion.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from edge.tui.widgets import warp_legend_markup

_KEYMAP = """\
[b]Conventions[/]
  [b]Esc[/] backs out of any screen · [b].[/] lists this screen's actions (numbered) \
· [b]?[/] this help
  [b]T[/] trade · [b]B[/] buy · [b]H[/] haggle · destructive acts always confirm first

[b]Game screen[/]
  [b]W[/] travel   [b]P[/] dock   [b]S[/] survey planet   [b]H[/] hail   [b]A[/] attack \
  [b]Z[/] scan
  [b]C[/] computer   [b]E[/] engine room   [b]M[/] map   [b]G[/] log   [b]D[/] deploy \
  [b]T[/] corp   [b]B[/] base

[b]Computer[/] (tabs: Map · Ports · Planets · Trade · Market · Log · Route · Codex ·
Leads · Contracts · Alliances · Dossier · Notes)
  [b]P[/] plot route   [b]R[/] route to…   [b]G[/] engage route   [b]D[/] deliver favor \
  [b]X[/] abandon/remove
  [b]J[/] join/resign bloc   [b]T[/] log admission task   [b]A[/] add note \
  [b]V[/] avoid sector   [b]S[/] seize Core

[b]Port / StarDock[/]
  [b]T[/] trade   [b]H[/] haggle   [b]B[/] buy (active tab)   [b]D[/] deposit / deliver \
  [b]W[/] withdraw
  [b]G[/] genesis   [b]I[/] missile   [b]K[/] recruit   [b]E[/] engine room \
  [b]F[/]/[b]M[/] fighters/mines   [b]R[/] rumor   [b]N[/] notice

[b]Planet (orbit)[/]
  [b]D[/] descend   [b]C[/] colonize   [b]G[/] genesis   [b]K[/] citadel   [b]I[/] invade
  [b]B[/] enter base   [b]+[/]/[b]-[/] treasury   [b]T[/]/[b]L[/] unload/load cargo

[b]Starbase[/] (tabs by standing: Station · Trade · Hardware · Bank)
  [b]T[/] trade desk   [b]R[/] repair slot   [b]S[/] salvage   [b]C[/] claim \
  [b]A[/] assault
  [b]B[/] buy part   [b]M[/] missile   [b]D[/]/[b]W[/] bank deposit/withdraw

[b]Engine room[/]
  [b]P[/] field-patch   [b]R[/] dock repair   [b]X[/] cannibalize   [b]U[/] upgrade (swap)

[b]Territory & devices[/] (game screen [b]D[/])
  [b]F[/] fighters   [b]M[/]/[b]L[/] armid/limpet mines   [b]B[/] beacon   [b]P[/] probe \
  [b]I[/] interdictor   [b]R[/] strip limpets

[b]Contact / Encounter[/]
  [b]1–9[/] replies   [b]B[/] back   [b]F[/]/[b]Esc[/] farewell   [b]J[/] join/resign bloc
  [dim]a live fight has no Esc — fight, missile, patch, or flee[/]\
"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
    ]

    CSS = """
    /* Translucent so the game window shows through behind the box (the global
       `Screen` rule would otherwise paint it opaque and blank the screen). */
    HelpScreen { align: center middle; background: $background 60%; }
    HelpScreen #help-box {
        width: 90; max-height: 90%; height: auto; padding: 1 2;
        border: round $primary; background: $surface;
    }
    HelpScreen #help-title { text-style: bold; color: $primary; margin-bottom: 1; }
    HelpScreen .help-section { text-style: bold; color: $secondary; margin-top: 1; }
    HelpScreen #help-footer { color: $text-muted; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        # Resolve config-driven anchor side from the app
        ui_config = getattr(self.app, "ui_config", None)
        side = ui_config.nav_core_anchor_side if ui_config else "left"

        with VerticalScroll(id="help-box"):
            yield Static("Help — keys", id="help-title")
            yield Static(_KEYMAP)
            yield Static("Warp legend", classes="help-section")
            yield Static(warp_legend_markup(side))
            yield Static("[dim]Esc to close[/]", id="help-footer")

    def action_close(self) -> None:
        self.dismiss(None)
