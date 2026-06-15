"""MessagesScreen — messages & log (UI_MOCKUPS.md §11).

Phase-1 shell: a tabbed view over the durable event log (DESIGN §12). Only the
**Events** tab is populated in the skeleton; Comms (alien/alliance messages) and
Bounties grow in Phase 3. Filtering, marking read, and opening an entry are stubbed.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

from edge.tui.dummy import MessagesDTO


class MessagesScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("g", "back", "Back"),
        Binding("enter", "noop", "Open"),
        Binding("f", "noop", "Filter"),
        Binding("m", "noop", "Mark read"),
    ]

    CSS = """
    MessagesScreen #messages-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    MessagesScreen TabPane { padding: 1 2; }
    MessagesScreen DataTable { height: auto; max-height: 16; }
    MessagesScreen .note {
        color: $text-muted; margin-top: 1; border-top: solid $primary; padding-top: 1;
    }
    """

    def __init__(self, messages: MessagesDTO) -> None:
        super().__init__()
        self._messages = messages

    def compose(self) -> ComposeResult:
        yield Static("MESSAGES & LOG", id="messages-title")
        with TabbedContent(initial="events"):
            with TabPane("Events", id="events"):
                yield DataTable(id="events-table", cursor_type="row", zebra_stripes=True)
                yield Static(
                    "[b]Enter[/] open   [b]F[/] filter   [b]M[/] mark read   "
                    "[b]Esc[/] back",
                    classes="note",
                )
            with TabPane("Comms", id="comms"):
                yield Static("[dim]Alien & alliance messages — Phase 3.[/]")
            with TabPane("Bounties", id="bounties"):
                yield Static("[dim]Bounty board — Phase 3.[/]")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#events-table", DataTable)
        table.add_columns("When", "Event")
        for entry in self._messages.events:
            table.add_row(Text(entry.when, style="dim"), Text.from_markup(entry.text))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
