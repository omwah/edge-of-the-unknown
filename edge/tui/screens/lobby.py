"""LobbyScreen — connect / log in / join a hosted game (WP68).

The minimal front door for `edge --connect ws://host:port`: register or log in, then create or
join a game. On a successful join it hands the app a `RemoteService` (the sync bridge over the
connected client) and opens the ordinary `GameScreen` — so all the gameplay screens are reused
unchanged over the network. Deliberately spartan: a couple of inputs and a status line; the
game itself is the experience, this is just the turnstile.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Static

from edge.server.client import RemoteError
from edge.tui.remote import RemoteBridge


class LobbyScreen(Screen):
    CSS = """
    LobbyScreen Vertical { width: 60; margin: 2 4; }
    LobbyScreen Input { margin: 1 0; }
    LobbyScreen #status { color: $warning; height: 2; }
    """

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url
        self._bridge: RemoteBridge | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Connect to {self._url}")
            yield Input(placeholder="username", id="user")
            yield Input(placeholder="password", password=True, id="pass")
            yield Input(placeholder="game name (create/join)", id="game")
            yield Button("Register + Join", id="register", variant="primary")
            yield Button("Log in + Join", id="login")
            yield Static("", id="status")
        yield Footer()

    def _status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        user = self.query_one("#user", Input).value.strip()
        pw = self.query_one("#pass", Input).value
        game = self.query_one("#game", Input).value.strip() or "alpha"
        if not user or not pw:
            self._status("username and password required")
            return
        try:
            self._connect_and_join(user, pw, game, register=event.button.id == "register")
        except RemoteError as exc:
            self._status(f"failed: {exc.message}")

    def _connect_and_join(self, user: str, pw: str, game: str, *, register: bool) -> None:
        """Bring up the link, authenticate, pick-or-create the game, and enter it (WP68)."""
        bridge = self._bridge or RemoteBridge(self._url)
        self._bridge = bridge
        if self._bridge is not None and self.app is not None:
            self.app._remote_bridge = bridge  # type: ignore[attr-defined]
        bridge.connect()
        client = bridge.client
        if register:
            bridge.run(client.register(user, pw))
        bridge.run(client.login(user, pw))
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
        app._remote_service = service  # type: ignore[attr-defined]
        app.pop_screen()
        app.push_screen(GameScreen(service, pid))  # type: ignore[arg-type]
