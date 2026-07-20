"""Sync bridge: drive an async `RemoteClient` from the synchronous TUI (WP68).

Most Textual screens read the game through a `GameService`-shaped **synchronous** surface
(`compose`/`render` are sync, and WP61 deferred their screen-level `await` migration). A hosted
game speaks the async `GameClient` over a socket, so this bridge runs the client on a background
event loop. Legacy screens block through `RemoteService`; the GW-WP07 expedition uses
`BridgedGameClient`, preserving the async facade without crossing websocket loop ownership.

`RemoteBridge` owns the loop/thread and exposes `run(coro)` for the lobby flow; `RemoteService`
is the `GameService`-shaped facade the game screens consume unchanged: every `service.foo(pid,
…)` call forwards to the seat-bound `client.foo(…)` and blocks for the reply.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any, cast

from edge.server.client import RemoteClient


class RemoteBridge:
    """Owns the background asyncio loop a `RemoteClient` runs on (WP68).

    The loop lives on a daemon thread so the synchronous TUI can schedule client coroutines onto
    it and wait for the result. `run` is the one primitive; the lobby screen uses it for
    login/join, and `RemoteService` uses it for every game call.
    """

    def __init__(self, url: str) -> None:
        self.client = RemoteClient(url)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="remote-loop", daemon=True)
        self._thread.start()
        self._game_client = BridgedGameClient(self)

    def run(self, coro: Any) -> Any:
        """Schedule `coro` on the client's loop and block until it completes (or raises)."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def connect(self) -> None:
        self.run(self.client.connect())

    def service(self) -> RemoteService:
        """A `GameService`-shaped synchronous facade over the connected client."""
        return RemoteService(self.client, self.run)

    def game_client(self) -> BridgedGameClient:
        """An awaitable facade safe to call from Textual's loop (GW-WP07)."""
        return self._game_client

    def close(self) -> None:
        try:
            self.run(self.client.aclose())
        except Exception:  # noqa: BLE001 — shutting down; a dead socket is fine
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)


class BridgedGameClient:
    """Run the full async ``RemoteClient`` surface on its owning background loop.

    Awaiting a raw ``RemoteClient`` coroutine from Textual's loop would cross event-loop
    ownership (the websocket lives on ``RemoteBridge._loop``).  This proxy preserves the
    ``GameClient`` coroutine shape while wrapping each concurrent future for the caller's
    loop.  It is intentionally generic so every present/future client read follows the same
    seam rather than growing another synchronous screen exception.
    """

    def __init__(self, bridge: RemoteBridge) -> None:
        self._bridge = bridge

    @property
    def player_id(self) -> int:
        return self._bridge.client.player_id

    @property
    def config(self) -> Any:
        return self._bridge.client.config

    @property
    def state(self) -> Any:
        return self._bridge.client.state

    def __getattr__(self, name: str) -> Callable[..., Any]:
        method = getattr(self._bridge.client, name)

        async def call(*args: Any, **kwargs: Any) -> Any:
            future = asyncio.run_coroutine_threadsafe(method(*args, **kwargs), self._bridge._loop)
            return await asyncio.wrap_future(future)

        return call

    async def events(self) -> Any:
        """Bridge the async event iterator one item at a time onto Textual's loop."""
        stream = self._bridge.client.events()
        while True:
            future = asyncio.run_coroutine_threadsafe(anext(stream), self._bridge._loop)
            yield await asyncio.wrap_future(future)


class RemoteService:
    """A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68).

    The game screens call `service.method(player_id, …)`; this drops the (server-enforced)
    `player_id`, forwards the rest to the seat-bound async client method, and blocks for the
    reply. A handful of methods differ from the generic shape and are spelled out below.
    """

    def __init__(self, client: RemoteClient, run: Callable[[Any], Any]) -> None:
        self._client = client
        self._run = run

    # --- methods whose signature isn't "(player_id, *args)" ------------------

    def apply(self, player_id: int, command: Any) -> Any:
        return self._run(self._client.apply(command))

    def describe_event(self, event: Any) -> str:
        return cast(str, self._run(self._client.describe_event(event)))

    def resolve_display_id(self, shown: int) -> int | None:
        return cast("int | None", self._run(self._client.resolve_display_id(shown)))

    @property
    def config(self) -> Any:
        """The static shared config, loaded locally for rendering (never wired, WP68)."""
        return self._client.config

    @property
    def state(self) -> Any:
        raise NotImplementedError("raw state is unavailable over a remote link (fog of war, H15)")

    # --- everything else: generic (player_id, *args) → client.method(*args) --

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name.startswith("_"):
            raise AttributeError(name)
        method = getattr(self._client, name)

        def call(_player_id: int | None = None, *args: Any, **kwargs: Any) -> Any:
            return self._run(method(*args, **kwargs))

        return call
