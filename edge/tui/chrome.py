"""Shared shell chrome (UI_UX_OVERHAUL_PLAN.md WP-UI05).

One place for the screen furniture every full screen shares — title bar,
context strip, empty states, and the below-minimum terminal notice — so no
screen rolls its own variant. All widgets here are presentation-only: they
never import the service, reducers, or DTO modules.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class TitleBar(Static):
    """The docked one-line screen header: bold title, optional muted context."""

    DEFAULT_CSS = """
    TitleBar {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    """

    def __init__(self, title: str, context: str = "", **kwargs: object) -> None:
        markup = title if not context else f"{title}        {context}"
        super().__init__(markup, **kwargs)


class ContextStrip(Static):
    """A muted one-to-few-line strip for status/legend copy under the body."""

    DEFAULT_CSS = """
    ContextStrip {
        height: auto; max-height: 4; padding: 0 1;
        border-top: solid $primary; color: $text-muted;
    }
    """


class EmptyState(Static):
    """A consistent 'nothing here' block: what is empty and what fills it."""

    DEFAULT_CSS = """
    EmptyState { height: auto; padding: 0 1; color: $text-muted; }
    """

    def __init__(self, message: str, hint: str = "", **kwargs: object) -> None:
        markup = f"[i]{message}[/]" + (f"\n{hint}" if hint else "")
        super().__init__(markup, **kwargs)


class SizeNoticeScreen(ModalScreen[None]):
    """Shown while the terminal is below the 80×24 floor (WP-UI05).

    It never traps the player: Help and Quit stay live, and the app pops the
    notice automatically the moment the terminal grows back past the minimum.
    """

    BINDINGS = [
        Binding("question_mark", "help", "Help"),
        Binding("ctrl+q", "app.quit", "Quit"),
    ]

    CSS = """
    SizeNoticeScreen { align: center middle; background: $background 80%; }
    SizeNoticeScreen #size-notice-box {
        width: auto; max-width: 100%; height: auto; padding: 1 2;
        border: round $warning; background: $surface;
    }
    SizeNoticeScreen .size-notice-hint { color: $text-muted; }
    """

    def compose(self) -> ComposeResult:
        size = self.app.size
        with Vertical(id="size-notice-box"):
            yield Static("[b]Terminal too small[/]")
            yield Static(
                f"Now {size.width}×{size.height} — Edge of the Unknown needs at "
                "least 80×24.",
            )
            yield Static("Enlarge the window to continue playing.",
                         classes="size-notice-hint")
            yield Static("[b]?[/] help · [b]^Q[/] quit", classes="size-notice-hint")

    def action_help(self) -> None:
        from edge.tui.screens.help import HelpScreen
        screens = self.app.screen_stack
        index = screens.index(self)
        host = screens[index - 1] if index > 0 else self
        self.app.push_screen(HelpScreen(host))
