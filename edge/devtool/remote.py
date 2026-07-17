"""Synchronous host-admin bridge for `edge-sysop` live hosted interventions.

The dashboard remains synchronous/Textual and reads trusted reports from the local game DB.
This bridge owns a `RemoteClient` on a private asyncio loop and exposes only the `apply`
shape the existing devtool session needs. The server accepts only `DevPatch` commands after
dedicated sysop-secret authentication and sends them through the live game's writer queue.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, cast

from edge.core.dev import DevPatch
from edge.core.events import Event
from edge.server.client import RemoteClient


class LiveSysopService:
    """Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC."""

    def __init__(self, url: str, password: str, game_name: str,
                 *, call_timeout: float = 120.0) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever,
                                        name="edge-sysop-remote", daemon=True)
        self._thread.start()
        self._client = RemoteClient(url)
        self.game_name = game_name
        self._call_timeout = call_timeout
        try:
            self._call(self._client.connect())
            self._call(self._client.sysop_login(password))
            opened = cast(tuple[int, str], self._call(self._client.sysop_open(game_name)))
            self.game_id, db_path = opened
            self.save_path = Path(db_path).expanduser()
        except Exception:
            self.close()
            raise

    def _call(self, coro: Coroutine[Any, Any, Any]) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(self._call_timeout)

    def apply(self, player_id: int, command: DevPatch) -> tuple[Event, ...]:
        """Apply an intervention to the authoritative live game as the target player."""
        return cast(tuple[Event, ...], self._call(
            self._client.sysop_apply(self.game_name, player_id, command)))

    def close(self) -> None:
        if self._loop.is_running():
            try:
                self._call(self._client.aclose())
            except Exception:  # noqa: BLE001 — cleanup after connection/auth failure
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5.0)
