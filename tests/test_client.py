"""WP61 — the async `GameClient` facade over the in-process service (DESIGN §3/§14).

`LocalClient` must be observably identical to calling `GameService` directly: the same
projections, the same events, single-player byte-for-byte. It also owns the ticker and a
(stubbed) broadcast stream that WP65 makes server-pushed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core.movement import shortest_path
from edge.core.rules import Command, Warp
from edge.server.client import GameClient, LocalClient, RemoteError, RemoteRulesError
from edge.server.service import GameService
from edge.store.repo import SqliteRepository

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"sector_count": 90, "start_sector": 1})})


def _service(tmp_path: Path, name: str = "game.db") -> GameService:
    return GameService.new_game(_config(), 42, SqliteRepository(tmp_path / name), created_at=_CREATED)  # type: ignore[arg-type]


def test_localclient_is_a_gameclient(tmp_path: Path) -> None:
    # runtime_checkable conformance — a bot/test can duck-type the seam.
    client = LocalClient(_service(tmp_path))
    assert isinstance(client, GameClient)


async def test_game_view_matches_service(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    client = LocalClient(svc)
    assert await client.game_view() == svc.game_view(1)
    assert client.state is svc.state
    assert client.config is svc.config
    assert client.player_id == 1


async def test_apply_mutates_and_fans_events(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    client = LocalClient(svc)
    start = (await client.game_view()).sector.sector_id
    target = shortest_path(svc.state.adjacency, start, start)  # trivially self
    assert target is not None
    # Warp to a real neighbour so the command is accepted and produces an event.
    neighbour = next(iter(svc.state.adjacency[start]))
    events = await client.apply(Warp(to_sector=neighbour))
    assert events
    assert (await client.game_view()).sector.sector_id == neighbour


async def test_events_stream_yields_apply_results(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    client = LocalClient(svc)
    start = (await client.game_view()).sector.sector_id
    neighbour = next(iter(svc.state.adjacency[start]))
    stream = client.events()
    produced = await client.apply(Warp(to_sector=neighbour))
    first = await anext(stream)
    assert first == produced[0]


async def test_player_id_seat_is_honoured(tmp_path: Path) -> None:
    # A client bound to a different seat submits and reads as that player.
    svc = _service(tmp_path)
    from edge.core.rules import JoinGame
    svc.apply(2, JoinGame())
    client2 = LocalClient(svc, player_id=2)
    assert client2.player_id == 2
    assert (await client2.game_view()) == svc.game_view(2)


async def test_apply_rejection_propagates(tmp_path: Path) -> None:
    # Facade does not swallow rejections — that is the bot runner's job, not the client's.
    svc = _service(tmp_path)
    client = LocalClient(svc)
    from edge.core.movement import MovementError
    bad: Command = Warp(to_sector=99999)
    with pytest.raises(MovementError):
        await client.apply(bad)


def test_remote_rules_error_matches_local_domain_error_catches() -> None:
    """Hosted denials follow the same warning-toast paths as embedded denials."""
    from edge.core.citadels import CitadelError
    from edge.core.combat import CombatError
    from edge.core.dev import DevPatchError
    from edge.core.economy import EconomyError
    from edge.core.engine_room import EngineRoomError
    from edge.core.movement import MovementError

    exc = RemoteRulesError(-32000, "the Core is a sanctuary — no attacks here")
    assert isinstance(exc, RemoteError)
    assert all(isinstance(exc, kind) for kind in (
        EconomyError, MovementError, CombatError, EngineRoomError, DevPatchError, CitadelError,
    ))
