"""OptionsScreen — a minimal settings panel off the main menu (WP73, D5).

Local presentation preferences only. Game-mechanical constants stay in config.
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
        Binding("r", "toggle_motion", "Reduced motion"),
        Binding("a", "toggle_art", "Art detail"),
        Binding("d", "toggle_density", "Density"),
        Binding("o", "toggle_onboarding", "Onboarding"),
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
            yield ClickableEntry(self._motion_line(), dest="opt", ref="motion")
            yield ClickableEntry(self._art_line(), dest="opt", ref="art")
            yield ClickableEntry(self._density_line(), dest="opt", ref="density")
            yield ClickableEntry(self._onboarding_line(), dest="opt", ref="onboarding")
            yield ClickableEntry(self._greyed_line(), dest="opt", ref="greyed")
            yield Static("[dim]T/R/A/D/O/G change · Esc closes · preferences are local[/]",
                         id="options-footer")

    def _theme_line(self) -> str:
        return f"  [b]T[/] Theme: [cyan]{self.app.theme}[/]"

    def _greyed_line(self) -> str:
        shown = self.app.ui_settings.show_disabled_options  # type: ignore[attr-defined]
        return (f"  [b]G[/] Show greyed dialogue replies: "
                f"[cyan]{'yes' if shown else 'no'}[/]")

    def _motion_line(self) -> str:
        value = self.app.ui_settings.reduced_motion  # type: ignore[attr-defined]
        return f"  [b]R[/] Reduced motion: [cyan]{'yes' if value else 'no'}[/]"

    def _art_line(self) -> str:
        value = self.app.ui_settings.art_detail  # type: ignore[attr-defined]
        return f"  [b]A[/] Art detail: [cyan]{value}[/]"

    def _density_line(self) -> str:
        value = self.app.ui_settings.density  # type: ignore[attr-defined]
        return f"  [b]D[/] Density: [cyan]{value}[/]"

    def _onboarding_line(self) -> str:
        value = self.app.ui_settings.show_onboarding  # type: ignore[attr-defined]
        return f"  [b]O[/] Captain's objectives: [cyan]{'shown' if value else 'hidden'}[/]"

    def on_clickable_entry_picked(self, msg: object) -> None:
        ref = getattr(msg, "ref", "")
        if ref == "theme":
            self.action_toggle_theme()
        elif ref == "motion":
            self.action_toggle_motion()
        elif ref == "art":
            self.action_toggle_art()
        elif ref == "density":
            self.action_toggle_density()
        elif ref == "onboarding":
            self.action_toggle_onboarding()
        elif ref == "greyed":
            self.action_toggle_greyed()

    def action_toggle_theme(self) -> None:
        names = ["edge-ansi", "edge-high-contrast", "edge-monochrome"]
        cur = self.app.theme
        idx = names.index(cur) if cur in names else -1
        self.app.update_ui_settings(theme=names[(idx + 1) % len(names)])  # type: ignore[attr-defined]
        self._redraw()

    def action_toggle_motion(self) -> None:
        settings = self.app.ui_settings  # type: ignore[attr-defined]
        self.app.update_ui_settings(reduced_motion=not settings.reduced_motion)  # type: ignore[attr-defined]
        self._redraw()

    def action_toggle_art(self) -> None:
        settings = self.app.ui_settings  # type: ignore[attr-defined]
        values = ["full", "compact", "minimal"]
        value = values[(values.index(settings.art_detail) + 1) % len(values)]
        self.app.update_ui_settings(art_detail=value)  # type: ignore[attr-defined]
        self._redraw()

    def action_toggle_density(self) -> None:
        settings = self.app.ui_settings  # type: ignore[attr-defined]
        value = "compact" if settings.density == "comfortable" else "comfortable"
        self.app.update_ui_settings(density=value)  # type: ignore[attr-defined]
        self._redraw()

    def action_toggle_onboarding(self) -> None:
        settings = self.app.ui_settings  # type: ignore[attr-defined]
        self.app.update_ui_settings(show_onboarding=not settings.show_onboarding)  # type: ignore[attr-defined]
        self._redraw()

    def action_toggle_greyed(self) -> None:
        settings = self.app.ui_settings  # type: ignore[attr-defined]
        value = not settings.show_disabled_options
        self.app.update_ui_settings(show_disabled_options=value)  # type: ignore[attr-defined]
        ui = getattr(self.app, "ui_config", None)
        if ui is not None:
            self.app.ui_config = ui.model_copy(update={"show_disabled_options": value})  # type: ignore[attr-defined]
        self._redraw()

    def _redraw(self) -> None:
        entries = list(self.query(ClickableEntry))
        lines = [self._theme_line(), self._motion_line(), self._art_line(),
                 self._density_line(), self._onboarding_line(), self._greyed_line()]
        for entry, line in zip(entries, lines, strict=False):
            entry.update(line)

    def action_close(self) -> None:
        self.dismiss(None)
