"""Shared shell chrome and feedback (UI_UX_OVERHAUL_PLAN.md WP-UI05/WP-UI07).

One place for the screen furniture every full screen shares — title bar,
context strip, empty states, the below-minimum terminal notice, the four
standard notification helpers, and the validated one-field form prompt — so no
screen rolls its own variant. All widgets here are presentation-only: they
never import the service, reducers, or DTO modules.
"""

from __future__ import annotations

from typing import Any, Literal, TypeVar, cast

from textual.app import ComposeResult
from textual.binding import ActiveBinding, Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Static


class EdgeScreen(Screen[None]):
    """The base every full screen uses: its footer always leads with **Back**.

    Textual orders the footer by the binding chain — focused widget, then its
    ancestors, then the screen — so a screen-wide key like Esc/Back is pushed behind
    whatever the focused widget happens to own (on the Computer's Map tab, Back landed
    after Engage). Back is the one key that means the same thing on every screen, so it
    is pinned to the front of the footer everywhere instead of drifting with focus.
    """

    def _back_first(self, bindings: dict[str, ActiveBinding]) -> dict[str, ActiveBinding]:
        back = {key: value for key, value in bindings.items() if key == "escape"}
        if not back:
            return bindings
        return back | {key: value for key, value in bindings.items() if key != "escape"}

    @property
    def active_bindings(self) -> dict[str, ActiveBinding]:
        return self._back_first(super().active_bindings)


# --- Notifications (WP-UI07) -------------------------------------------------
# One vocabulary for toast feedback: success/info are quiet and short-lived,
# warnings and errors stay up longer and carry their severity as a title word,
# so the state survives monochrome. Screens call these instead of hand-picking
# severities and timeouts.

def notify_success(host: object, message: str) -> None:
    host.notify(message, title="Done", timeout=3)  # type: ignore[attr-defined]


def notify_info(host: object, message: str) -> None:
    host.notify(message, timeout=3)  # type: ignore[attr-defined]


def notify_warning(host: object, message: str) -> None:
    host.notify(message, title="Warning", severity="warning",  # type: ignore[attr-defined]
                timeout=4)


def notify_error(host: object, message: str) -> None:
    host.notify(message, title="Error", severity="error",  # type: ignore[attr-defined]
                timeout=6)


class TitleBar(Static):
    """The docked one-line screen header: bold title, optional muted context."""

    DEFAULT_CSS = """
    TitleBar {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    """

    def __init__(self, title: str, context: str = "", **kwargs: Any) -> None:
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

    def __init__(self, message: str, hint: str = "", **kwargs: Any) -> None:
        super().__init__(self._markup(message, hint), **kwargs)

    @staticmethod
    def _markup(message: str, hint: str) -> str:
        return f"[i]{message}[/]" + (f"\n{hint}" if hint else "")

    def set_content(self, message: str, hint: str = "") -> None:
        """Swap the copy in place (e.g. 'nothing here' vs 'nothing matches')."""
        self.update(self._markup(message, hint))


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


# --- One-field form prompt (WP-UI07) -----------------------------------------

PromptResult = TypeVar("PromptResult")
InputType = Literal["integer", "number", "text"]


class FieldPrompt(ModalScreen[PromptResult]):
    """The shared one-field prompt: inline validation, no silent failures.

    Subclasses override `parse(raw) -> (value, error)`. An invalid submit keeps
    the modal open with the typed value intact and the reason shown under the
    field; only a valid submit (or Esc → None) dismisses. This replaces the old
    per-screen prompts that closed and returned None on bad input, losing what
    the player typed. Generic over the parsed result, so `push_screen`
    callbacks get the subclass's real value type (str / int / …).
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    FieldPrompt { align: center middle; background: $background 60%; }
    FieldPrompt .form-error { color: $error; height: 1; }
    FieldPrompt Button { margin-top: 1; }
    """

    def __init__(self, prompt: str, *, placeholder: str = "",
                 hint: str = "Enter to confirm · Esc to cancel",
                 input_type: InputType = "text",
                 submit_label: str | None = None) -> None:
        super().__init__()
        self._prompt = prompt
        self._placeholder = placeholder
        self._hint = hint
        self._input_type = input_type
        self._submit_label = submit_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box"):
            yield Static(f"[b]{self._prompt}[/]  [dim]({self._hint})[/]")
            yield Input(placeholder=self._placeholder, type=self._input_type,
                        id="field-input")
            yield Static("", classes="form-error", id="field-error")
            if self._submit_label is not None:
                yield Button(self._submit_label, id="field-submit", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#field-input", Input).focus()

    def parse(self, raw: str) -> tuple[PromptResult | None, str | None]:
        """Return (value, None) to accept or (None, reason) to hold the form open."""
        return cast("PromptResult", raw.strip()), None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_input_changed(self, event: Input.Changed) -> None:
        """A correction clears stale validation copy and restores stable form layout."""
        self.query_one("#field-error", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._submit()

    def _submit(self) -> None:
        value, error = self.parse(self.query_one("#field-input", Input).value)
        if error is not None:
            self.query_one("#field-error", Static).update(error)
            self.query_one("#field-input", Input).focus()
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextPrompt(FieldPrompt[str]):
    """A required-text prompt (notes, notices, beacons, names)."""

    def parse(self, raw: str) -> tuple[str | None, str | None]:
        text = raw.strip()
        if not text:
            return None, "Type a message first — or press Esc to cancel."
        return text, None


class AmountPrompt(FieldPrompt[int]):
    """A positive-integer prompt (latinum amounts, quantities)."""

    def __init__(self, prompt: str, *, placeholder: str = "amount…",
                 hint: str = "Enter to confirm · Esc to cancel",
                 submit_label: str | None = None) -> None:
        super().__init__(prompt, placeholder=placeholder, hint=hint,
                         input_type="integer", submit_label=submit_label)

    def parse(self, raw: str) -> tuple[int | None, str | None]:
        text = raw.strip()
        if not text.isdigit() or int(text) <= 0:
            return None, "Enter a positive whole number — or press Esc to cancel."
        return int(text), None
