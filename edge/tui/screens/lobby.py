"""LobbyScreen — connect / log in / join a hosted game (WP68).

The minimal front door for `edge --connect ws://host:port`: register or log in, then create or
join a game. On a successful join it hands the app a `RemoteService` (the sync bridge over the
connected client) and opens the ordinary `GameScreen` — so all the gameplay screens are reused
unchanged over the network. WP-UI19: every field carries a persistent label, the status line
names the connection stage it is in (or failed in), authentication errors read inline next to
the form, and a failed attempt never clears what was typed — retry edits in place.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical

from edge.tui.chrome import EdgeScreen
from textual.widgets import Button, Footer, Input, Label, Static

from edge.server.client import RemoteError
from edge.tui.remote import RemoteBridge


class LobbyScreen(EdgeScreen):
    CSS = """
    LobbyScreen Vertical { width: 60; max-width: 100%; margin: 2 4; }
    LobbyScreen #lobby-title { text-style: bold; margin-bottom: 1; }
    LobbyScreen .field-label { color: $text-muted; margin-top: 1; }
    LobbyScreen Input { margin: 0 0 1 0; }
    LobbyScreen #status { color: $text-muted; height: 2; margin-top: 1; }
    LobbyScreen #status.error { color: $error; }
    """

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url
        self._bridge: RemoteBridge | None = None
        self._busy = False  # WP-UI07: one join attempt at a time
        self._stage = "connecting"  # what the current attempt is doing (WP-UI19)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("JOIN A HOSTED GAME", id="lobby-title")
            yield Label(f"Server  [b]{self._url}[/]")
            yield Label("Username", classes="field-label")
            yield Input(placeholder="your captain's name", id="user")
            yield Label("Password", classes="field-label")
            yield Input(placeholder="••••••", password=True, id="pass")
            yield Label("Game — joined if it exists, created otherwise", classes="field-label")
            yield Input(placeholder="alpha", id="game")
            yield Button("Register + Join", id="register", variant="primary")
            yield Button("Log in + Join", id="login")
            yield Static("", id="status")
        yield Footer()

    def _status(self, text: str, *, error: bool = False) -> None:
        line = self.query_one("#status", Static)
        line.set_class(error, "error")
        line.update(f"[b]Error:[/] {text}" if error else text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._busy:
            return  # WP-UI07: a join is already running — no duplicate submits
        user = self.query_one("#user", Input).value.strip()
        pw = self.query_one("#pass", Input).value
        game = self.query_one("#game", Input).value.strip() or "alpha"
        # WP-UI07 inline validation: name the missing field and put focus there;
        # typed values are never cleared, so a failed attempt is editable in place.
        if not user:
            self._status("username required", error=True)
            self.query_one("#user", Input).focus()
            return
        if not pw:
            self._status("password required", error=True)
            self.query_one("#pass", Input).focus()
            return
        self._busy = True
        for button in self.query(Button):
            button.disabled = True
        self._status(f"connecting to {self._url}…")
        try:
            self._connect_and_join(user, pw, game, register=event.button.id == "register")
        except (RemoteError, OSError) as exc:
            message = exc.message if isinstance(exc, RemoteError) else str(exc)
            self._status(f"failed while {self._stage}: {message}", error=True)
        finally:
            self._busy = False
            for button in self.query(Button):
                button.disabled = False

    def _connect_and_join(self, user: str, pw: str, game: str, *, register: bool) -> None:
        """Bring up the link, authenticate, pick-or-create the game, and enter it (WP68).

        `_stage` tracks progress so a failure names the step it died in (WP-UI19).
        """
        self._stage = "connecting"
        bridge = self._bridge or RemoteBridge(self._url)
        self._bridge = bridge
        if self._bridge is not None and self.app is not None:
            self.app._remote_bridge = bridge  # type: ignore[attr-defined]
        bridge.connect()
        client = bridge.client
        self._stage = "registering" if register else "logging in"
        self._status(f"{self._stage}…")
        if register:
            bridge.run(client.register(user, pw))
        bridge.run(client.login(user, pw))
        self._stage = f"joining game “{game}”"
        self._status(f"{self._stage}…")
        games = {g["name"]: g["game_id"] for g in bridge.run(client.list_games())}
        gid = games.get(game)
        if gid is None:
            gid = bridge.run(client.create_game(game))  # host-gated server-side
        pid = bridge.run(client.join_game(gid))
        self._enter_game(bridge, pid)

    def _enter_game(self, bridge: RemoteBridge, pid: int) -> None:
        from edge.tui.screens.game import GameScreen

        service = bridge.service()
        app = self.app
        app.player_id = pid  # type: ignore[attr-defined]
        app.client = bridge.game_client()  # type: ignore[attr-defined]
        app._remote_service = service  # type: ignore[attr-defined]
        app.pop_screen()
        app.push_screen(GameScreen(service, pid))  # type: ignore[arg-type]
