"""OptionsScreen — a minimal settings panel off the main menu (WP73, D5).

Session-scoped toggles only: the visual theme and whether greyed (unavailable)
dialogue replies are shown on the contact screen. Game-mechanical constants stay
in the config files (AGENTS.md — constants live in config, not the UI).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from edge.tui.widgets import ClickableEntry


class OptionsScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("t", "toggle_theme", "Theme"),
        Binding("g", "toggle_greyed", "Greyed replies"),
    ]

    CSS = """
    OptionsScreen { align: center middle; background: $background 60%; }
    OptionsScreen #options-box {
        width: 60; height: auto; padding: 1 2; border: round $primary; background: $surface;
    }
    OptionsScreen #options-title { text-style: bold; color: $primary; margin-bottom: 1; }
    OptionsScreen #options-footer { color: $text-muted; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="options-box"):
            yield Static("Options", id="options-title")
            yield ClickableEntry(self._theme_line(), dest="opt", ref="theme")
            yield ClickableEntry(self._greyed_line(), dest="opt", ref="greyed")
            yield Static("[dim]T / G toggle · Esc to close · session-scoped; game "
                         "constants live in config files[/]", id="options-footer")

    def _theme_line(self) -> str:
        return f"  [b]T[/] Theme: [cyan]{self.app.theme}[/]"

    def _greyed_line(self) -> str:
        ui = getattr(self.app, "ui_config", None)
        shown = bool(ui and ui.show_disabled_options)
        return (f"  [b]G[/] Show greyed dialogue replies: "
                f"[cyan]{'yes' if shown else 'no'}[/]")

    def on_clickable_entry_picked(self, msg: object) -> None:
        ref = getattr(msg, "ref", "")
        if ref == "theme":
            self.action_toggle_theme()
        elif ref == "greyed":
            self.action_toggle_greyed()

    def action_toggle_theme(self) -> None:
        names = sorted(self.app.available_themes)
        cur = self.app.theme
        idx = names.index(cur) if cur in names else -1
        self.app.theme = names[(idx + 1) % len(names)]
        self._redraw()

    def action_toggle_greyed(self) -> None:
        ui = getattr(self.app, "ui_config", None)
        if ui is None:
            self.notify("No UI config loaded yet.", timeout=2)
            return
        self.app.ui_config = ui.model_copy(  # type: ignore[attr-defined]
            update={"show_disabled_options": not ui.show_disabled_options})
        self._redraw()

    def _redraw(self) -> None:
        entries = list(self.query(ClickableEntry))
        if len(entries) >= 2:
            entries[0].update(self._theme_line())
            entries[1].update(self._greyed_line())

    def action_close(self) -> None:
        self.dismiss(None)
