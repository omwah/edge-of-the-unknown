"""ActionMenuScreen — the numbered context-action menu (`.` anywhere — WP73, D3).

One key lists everything doable on the current screen: every advertised binding,
numbered. Press the number (or click) to run it; Esc backs out. This is the
discoverability layer the footer can't be on a narrow terminal — features stop
being buried in hotkeys because the menu *is* the hotkey table, live.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Static

from edge.tui.widgets import ClickableEntry


def _host_bindings(host: Screen) -> list[Binding]:
    """The host screen's advertised bindings (class-declared, `show=True`)."""
    out: list[Binding] = []
    for b in getattr(type(host), "BINDINGS", []):
        if isinstance(b, Binding) and b.show:
            out.append(b)
    return out


class ActionMenuScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    ActionMenuScreen { align: center middle; background: $background 60%; }
    ActionMenuScreen #action-box {
        width: 52; max-height: 80%; height: auto; padding: 1 2;
        border: round $primary; background: $surface;
    }
    ActionMenuScreen #action-title { text-style: bold; color: $primary; margin-bottom: 1; }
    """

    def __init__(self, host: Screen) -> None:
        super().__init__()
        self._host = host
        self._actions = _host_bindings(host)

    def compose(self) -> ComposeResult:
        with Vertical(id="action-box"):
            yield Static(f"Actions — {type(self._host).__name__}", id="action-title")
            with VerticalScroll():
                for n, b in enumerate(self._actions, start=1):
                    label = b.description or b.action
                    num = f"{n}." if n <= 9 else "  "
                    yield ClickableEntry(f"  [b]{num}[/] {label}  [dim]({b.key})[/]",
                                         dest="action", ref=str(n - 1))
            yield Static("[dim]number / click to run · Esc to close[/]")

    @on(ClickableEntry.Picked)
    async def on_action_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "action":
            await self._run(int(msg.ref))

    async def on_key(self, event: object) -> None:
        key = getattr(event, "key", "")
        if key.isdigit() and 1 <= int(key) <= min(9, len(self._actions)):
            getattr(event, "stop", lambda: None)()
            await self._run(int(key) - 1)

    async def _run(self, index: int) -> None:
        if not 0 <= index < len(self._actions):
            return
        action = self._actions[index].action
        host = self._host
        self.dismiss(None)
        await host.run_action(action)

    def action_close(self) -> None:
        self.dismiss(None)
