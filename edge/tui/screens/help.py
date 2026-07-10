"""HelpScreen — contextual help for the current screen (`?` anywhere).

Instead of one monolithic keymap living on the sector view, `?` now opens help
*for the screen you are on*: its advertised key bindings (the same live table the
`.` action menu reads, so it can never drift from reality), an optional curated
`HELP` note the screen declares (context and conventions the binding table can't
carry), and the short global conventions block. The game screen additionally
shows the warp colour legend (`HELP_LEGEND = True`).

To give a screen richer help, declare on it:

    HELP = "[b]...[/] markup paragraphs"   # optional prose under the key table
    HELP_TITLE = "Sector view"             # optional display name (else class name)
    HELP_LEGEND = True                     # optional: append the warp legend
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Static

from edge.tui.widgets import warp_legend_markup
from edge.tui.design import screen_actions

_CONVENTIONS = """\
[b]Esc[/] backs out of any screen · [b].[/] lists this screen's actions (numbered) \
· [b]?[/] this help
destructive acts always confirm first · pickers: [b]↑/↓[/] select, [b]Enter[/] choose\
"""


def _binding_rows(host: Screen) -> list[str]:
    """The host screen's advertised bindings as help rows (never drifts — live)."""
    rows: list[str] = []
    for descriptor in screen_actions(host):
        raw_key = descriptor.key or "Ctrl+P"
        key = {"escape": "Esc", "plus": "+", "minus": "-",
               "question_mark": "?", "full_stop": ".", "ctrl+q": "^Q"}.get(
                   raw_key, raw_key.upper())
        suffix = (f" [dim]— {descriptor.disabled_reason}[/]"
                  if not descriptor.enabled and descriptor.disabled_reason else "")
        rows.append(f"  [b]{key}[/]  {descriptor.title}{suffix}")
    return rows


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
    ]

    CSS = """
    /* Translucent so the host screen shows through behind the box. */
    HelpScreen { align: center middle; background: $background 60%; }
    HelpScreen #help-box {
        width: 80; max-width: 100%; max-height: 90%; height: auto; overflow-y: auto;
        padding: 1 2; border: round $primary; background: $surface;
    }
    HelpScreen #help-title { text-style: bold; color: $primary; margin-bottom: 1; }
    HelpScreen .help-section { text-style: bold; color: $secondary; margin-top: 1; }
    HelpScreen #help-footer { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, host: Screen | None = None) -> None:
        super().__init__()
        self._host = host

    def compose(self) -> ComposeResult:
        host = self._host
        title = "Help"
        rows: list[str] = []
        prose = ""
        legend = False
        if host is not None:
            name = getattr(type(host), "HELP_TITLE", None) or type(host).__name__
            title = f"Help — {name}"
            rows = _binding_rows(host)
            prose = getattr(type(host), "HELP", "")
            legend = bool(getattr(type(host), "HELP_LEGEND", False))

        with VerticalScroll(id="help-box"):
            yield Static(title, id="help-title")
            if rows:
                yield Static("Keys", classes="help-section")
                yield Static("\n".join(rows))
            if prose:
                yield Static("Notes", classes="help-section")
                yield Static(prose)
            yield Static("Conventions", classes="help-section")
            yield Static(_CONVENTIONS)
            if legend:
                ui_config = getattr(self.app, "ui_config", None)
                side = ui_config.nav_core_anchor_side if ui_config else "left"
                yield Static("Warp legend", classes="help-section")
                yield Static(warp_legend_markup(side))
            yield Static("[dim]Esc to close[/]", id="help-footer")

    def action_close(self) -> None:
        self.dismiss(None)
