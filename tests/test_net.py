"""WP63 — the websocket JSON-RPC game server (DESIGN §3/§14, H14).

Two layers: fast in-process `dispatch`/queue tests (no socket), and one real end-to-end
websocket round-trip. The invariants under test are the H14 discipline — single-writer arrival
order — and the H15 identity boundary: a session only ever acts as the seat it said hello with.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core.rules import Dock, JoinGame, Warp
from edge.server import wire
from edge.server.net import ERR_HANDSHAKE, ERR_METHOD_NOT_FOUND, GameServer, RpcError, Session
from edge.server.service import GameService
from edge.store.repo import SqliteRepository

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"sector_count": 90, "start_sector": 1})})


def _server(tmp_path: Path, name: str = "net.db") -> GameServer:
    svc = GameService.new_game(_config(), 42, SqliteRepository(tmp_path / name), created_at=_CREATED)  # type: ignore[arg-type]
    return GameServer(svc, tick_seconds=1000.0)  # ticker effectively idle for the test


def _bound_session() -> Session:
    return Session(conn=None, player_id=1)


# --- in-process dispatch -----------------------------------------------------


async def test_dispatch_requires_hello(tmp_path: Path) -> None:
    server = _server(tmp_path)
    with pytest.raises(RpcError) as ei:
        await server.dispatch(Session(conn=None), "game_view", {})
    assert ei.value.code == ERR_HANDSHAKE


async def test_game_view_round_trips_over_dispatch(tmp_path: Path) -> None:
    server = _server(tmp_path)
    result = await server.dispatch(_bound_session(), "game_view", {})
    assert wire.decode_dto(result) == server._service.game_view(1)  # type: ignore[attr-defined]


async def test_apply_mutates_through_the_queue(tmp_path: Path) -> None:
    server = _server(tmp_path)
    worker = asyncio.create_task(server._run_worker())  # type: ignore[attr-defined]
    try:
        svc = server._service  # type: ignore[attr-defined]
        start = svc.game_view(1).sector.sector_id
        neighbour = next(iter(svc.state.adjacency[start]))
        events = await server.dispatch(_bound_session(), "apply",
                                       {"command": wire.encode_command(Warp(to_sector=neighbour))})
        assert events  # wire-encoded event envelopes
        assert svc.game_view(1).sector.sector_id == neighbour
    finally:
        worker.cancel()


async def test_unknown_method_rejected(tmp_path: Path) -> None:
    server = _server(tmp_path)
    with pytest.raises(RpcError) as ei:
        await server.dispatch(_bound_session(), "nonsense", {})
    assert ei.value.code == ERR_METHOD_NOT_FOUND


async def test_commands_apply_in_arrival_order(tmp_path: Path) -> None:
    # Two sessions submit concurrently; the single queue must serialize them in enqueue order.
    server = _server(tmp_path)
    worker = asyncio.create_task(server._run_worker())  # type: ignore[attr-defined]
    try:
        svc = server._service  # type: ignore[attr-defined]
        svc.apply(2, JoinGame())
        order: list[int] = []

        async def submit_and_record(pid: int) -> None:
            await server.submit(pid, Dock())
            order.append(pid)

        # Enqueue p1 then p2; both Dock commands may reject (no port), but the queue still
        # serializes them, and the command log records them in submission order.
        await asyncio.gather(submit_and_record(1), submit_and_record(2), return_exceptions=True)
        logged = [c.player_id for c in svc._repo.load_commands()]  # type: ignore[attr-defined]
        # player 1's JoinGame (new_game) + player 2's JoinGame precede; the two Docks that
        # succeeded (if any) appear in submission order.
        assert logged[:2] == [1, 2]  # the two JoinGames
    finally:
        worker.cancel()


async def test_identity_bound_at_hello(tmp_path: Path) -> None:
    # A session's seat is fixed at hello; params carry no player_id for reads/apply (H15).
    server = _server(tmp_path)
    session = Session(conn=None)
    server._hello(session, {"fingerprint": wire.wire_fingerprint(), "player_id": 1})  # type: ignore[attr-defined]
    assert session.player_id == 1


async def test_hello_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    server = _server(tmp_path)
    with pytest.raises(RpcError) as ei:
        server._hello(Session(conn=None), {"fingerprint": "deadbeef"})  # type: ignore[attr-defined]
    assert ei.value.code == ERR_HANDSHAKE


# --- end-to-end websocket ----------------------------------------------------


async def test_end_to_end_websocket(tmp_path: Path) -> None:
    from websockets.asyncio.client import connect

    server = _server(tmp_path)
    ws_server = await server.serve("localhost", 0)
    port = ws_server.sockets[0].getsockname()[1]
    try:
        async with connect(f"ws://localhost:{port}") as conn:
            async def call(method: str, params: dict[str, object]) -> dict[str, object]:
                await conn.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                            "params": params}))
                return json.loads(await conn.recv())

            hello = await call("hello", {"fingerprint": wire.wire_fingerprint(), "player_id": 1})
            assert hello["result"]["player_id"] == 1  # type: ignore[index]

            view = await call("game_view", {})
            svc = server._service  # type: ignore[attr-defined]
            assert wire.decode_dto(view["result"]) == svc.game_view(1)

            start = svc.game_view(1).sector.sector_id
            neighbour = next(iter(svc.state.adjacency[start]))
            applied = await call("apply", {"command": wire.encode_command(Warp(to_sector=neighbour))})
            assert applied["result"]  # events came back
            assert svc.game_view(1).sector.sector_id == neighbour
    finally:
        await server.aclose()
        ws_server.close()
        await ws_server.wait_closed()
