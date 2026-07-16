"""Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-only).

The pilot stack (`BotRunner`, `describe`, `ActionCatalog`) is written against the
synchronous `ServiceProtocol`; a hosted game (`edge-server`, WP63/WP68) speaks the async
`RemoteClient`. `RemoteSession` bridges the two: it runs a private asyncio loop on a
daemon thread, drives the websocket client there, and exposes a `service` facade whose
method calls block the calling thread until the wire answers — so the whole local pilot
works over a hosted game unchanged.

A wire rules-rejection (JSON-RPC code -32000) is translated back into an `EconomyError`,
one of the rejection types `BotRunner.apply` already swallows, so a hostile trade or a
blocked warp stays a readable rejection instead of a crash — exactly like local play.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

from edge.core.economy import EconomyError
from edge.server.client import RemoteClient, RemoteError

# JSON-RPC code the server uses for an expected rules rejection (edge/server/net.py).
_ERR_RULES_REJECTION = -32000

# ServiceProtocol methods whose first argument is `player_id`; the async client is
# already bound to its seat, so the facade drops it. Everything else passes through.
_NO_PLAYER_PREFIX = frozenset({"describe_event", "resolve_display_id"})


class RemoteSession:
    """Owns the loop thread + connected client; `service` is the sync facade."""

    def __init__(self, url: str, *, call_timeout: float = 120.0) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever,
                                        name="edge-llm-remote", daemon=True)
        self._thread.start()
        self.client = RemoteClient(url)
        self.call_timeout = call_timeout
        self.service = _SyncClientFacade(self)

    def call(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """Run a client coroutine on the loop thread; block until it answers."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(self.call_timeout)

    def open(self, username: str, password: str, *, game_id: int | None,
             game_name: str, seed: int) -> int:
        """Connect, auth (registering a fresh account when needed), and take a seat.

        Joins `game_id` when given; otherwise joins the first hosted game, or creates
        `game_name` from `seed` on an empty server. Returns the seat's player id.
        """
        client = self.client
        self.call(client.connect())
        try:
            self.call(client.login(username, password))
        except RemoteError:  # unknown account — register it, then log in
            self.call(client.register(username, password))
            self.call(client.login(username, password))
        if game_id is None:
            games = self.call(client.list_games())
            game_id = int(games[0]["game_id"]) if games else self.call(
                client.create_game(game_name, seed))
        player_id: int = self.call(client.join_game(game_id))
        return player_id

    def close(self) -> None:
        try:
            self.call(self.client.aclose())
        except Exception:  # noqa: BLE001 — closing a dropped link must not raise
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)


class _SyncClientFacade:
    """Duck-typed `ServiceProtocol`: each method blocks on the async client twin.

    `ServiceProtocol` methods carry a leading `player_id`; the remote client is bound to
    its seat, so the facade drops that argument and forwards the rest verbatim.
    """

    def __init__(self, session: RemoteSession) -> None:
        self._session = session

    def __getattr__(self, name: str) -> Any:
        method = getattr(self._session.client, name)
        drop_player = name not in _NO_PLAYER_PREFIX

        def call(*args: Any, **kwargs: Any) -> Any:
            if drop_player and args:
                args = args[1:]
            try:
                return self._session.call(method(*args, **kwargs))
            except RemoteError as exc:
                if exc.code == _ERR_RULES_REJECTION:
                    raise EconomyError(exc.message) from exc  # a swallowable rejection
                raise

        call.__name__ = name
        return call
