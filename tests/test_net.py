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
from edge.server.accounts import AccountStore
from edge.server.net import (
    ERR_AUTH,
    ERR_HANDSHAKE,
    ERR_METHOD_NOT_FOUND,
    GameServer,
    LobbyServer,
    RpcError,
    Session,
)
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild
from edge.engine.cron import resolve_cron

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
                # Broadcast notifications (WP65, method="event", no id) share the socket — a
                # real client demuxes them; skip to this request's response.
                while True:
                    msg = json.loads(await conn.recv())
                    if msg.get("id") is not None:
                        return msg

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


# --- broadcast + catch-up (WP65) ---------------------------------------------


async def test_broadcast_pushes_visible_events_to_registered_sessions(tmp_path: Path) -> None:
    server = _server(tmp_path)
    server.start()  # wires on_events → fan-out
    try:
        s1 = Session(conn=None, player_id=1)
        server.register_session(s1)
        svc = server._service  # type: ignore[attr-defined]
        start = svc.game_view(1).sector.sector_id
        neighbour = next(iter(svc.state.adjacency[start]))
        await server.submit(1, Warp(to_sector=neighbour))
        note = s1.outbox.get_nowait()
        assert note["method"] == "event"
        assert note["params"]["seq"] > 0
        assert wire.decode_event(note["params"]["event"])  # a real, decodable event
    finally:
        await server.aclose()


async def test_catch_up_equals_the_live_pushed_stream(tmp_path: Path) -> None:
    server = _server(tmp_path)
    server.start()
    try:
        s1 = Session(conn=None, player_id=1)
        server.register_session(s1)
        svc = server._service  # type: ignore[attr-defined]
        start = svc.game_view(1).sector.sector_id
        neighbour = next(iter(svc.state.adjacency[start]))
        await server.submit(1, Warp(to_sector=neighbour))
        live = []
        while not s1.outbox.empty():
            live.append(s1.outbox.get_nowait())
        catch_up = server.events_since(1, 0)  # same seq window (from the start)
        assert [n["params"]["seq"] for n in live] == [c["seq"] for c in catch_up]
        assert [n["params"]["event"] for n in live] == [c["event"] for c in catch_up]
    finally:
        await server.aclose()


# --- lobby (WP64) ------------------------------------------------------------


def _lobby(tmp_path: Path) -> LobbyServer:
    store = AccountStore(tmp_path / "accounts.db")
    return LobbyServer(store, _config(), tmp_path / "games", tick_seconds=1000.0)


async def test_lobby_register_login_create_join_play(tmp_path: Path) -> None:
    (tmp_path / "games").mkdir()
    lobby = _lobby(tmp_path)
    try:
        session = Session(conn=None)
        hello = await lobby.dispatch(session, "hello", {"fingerprint": wire.wire_fingerprint()})
        assert hello["wire_version"] == wire.WIRE_VERSION
        await lobby.dispatch(session, "register", {"username": "host", "password": "pw"})
        await lobby.dispatch(session, "login", {"username": "host", "password": "pw"})
        gid = (await lobby.dispatch(session, "create_game", {"name": "alpha", "seed": 42}))["game_id"]
        joined = await lobby.dispatch(session, "join_game", {"game_id": gid})
        assert joined["player_id"] == 1  # first seat
        # A game method now routes to the bound game as that seat.
        view = await lobby.dispatch(session, "game_view", {})
        assert wire.decode_dto(view) is not None
    finally:
        await lobby.aclose()


async def test_join_allocates_seat_via_logged_joingame(tmp_path: Path) -> None:
    (tmp_path / "games").mkdir()
    lobby = _lobby(tmp_path)
    try:
        host = Session(conn=None)
        await lobby.dispatch(host, "register", {"username": "host", "password": "pw"})
        await lobby.dispatch(host, "login", {"username": "host", "password": "pw"})
        gid = (await lobby.dispatch(host, "create_game", {"name": "alpha", "seed": 42}))["game_id"]
        await lobby.dispatch(host, "join_game", {"game_id": gid})

        guest = Session(conn=None)
        await lobby.dispatch(guest, "register", {"username": "guest", "password": "pw"})
        await lobby.dispatch(guest, "login", {"username": "guest", "password": "pw"})
        p2 = (await lobby.dispatch(guest, "join_game", {"game_id": gid}))["player_id"]
        assert p2 == 2  # next free seat

        # The roster rebuilds from the command log alone (the §3 seam: joins are logged).
        server = lobby._games[gid]  # type: ignore[attr-defined]
        repo = server.service._repo  # type: ignore[attr-defined]
        meta = repo.load_meta()
        rebuilt = rebuild(_config(), meta.seed, repo.load_commands(), created_at=meta.created_at,
                          maintenance=repo.load_maintenance(), cron_resolver=resolve_cron)
        assert set(rebuilt.players) == {1, 2}
    finally:
        await lobby.aclose()


async def test_resume_returns_same_seat(tmp_path: Path) -> None:
    (tmp_path / "games").mkdir()
    lobby = _lobby(tmp_path)
    try:
        s = Session(conn=None)
        await lobby.dispatch(s, "register", {"username": "host", "password": "pw"})
        await lobby.dispatch(s, "login", {"username": "host", "password": "pw"})
        gid = (await lobby.dispatch(s, "create_game", {"name": "alpha", "seed": 42}))["game_id"]
        first = (await lobby.dispatch(s, "join_game", {"game_id": gid}))["player_id"]
        # A fresh connection resumes the same account into the same seat (no new JoinGame).
        again = Session(conn=None)
        await lobby.dispatch(again, "login", {"username": "host", "password": "pw"})
        assert (await lobby.dispatch(again, "resume", {"game_id": gid}))["player_id"] == first
    finally:
        await lobby.aclose()


async def test_game_methods_require_auth_and_seat(tmp_path: Path) -> None:
    (tmp_path / "games").mkdir()
    lobby = _lobby(tmp_path)
    try:
        anon = Session(conn=None)
        with pytest.raises(RpcError) as ei:
            await lobby.dispatch(anon, "list_games", {})
        assert ei.value.code == ERR_AUTH  # not logged in

        s = Session(conn=None)
        await lobby.dispatch(s, "register", {"username": "host", "password": "pw"})
        await lobby.dispatch(s, "login", {"username": "host", "password": "pw"})
        with pytest.raises(RpcError) as ei2:
            await lobby.dispatch(s, "game_view", {})  # logged in but no seat
        assert ei2.value.code == ERR_AUTH
    finally:
        await lobby.aclose()


async def test_create_game_is_host_gated(tmp_path: Path) -> None:
    (tmp_path / "games").mkdir()
    lobby = _lobby(tmp_path)
    try:
        host = Session(conn=None)
        await lobby.dispatch(host, "register", {"username": "host", "password": "pw"})
        guest = Session(conn=None)
        await lobby.dispatch(guest, "register", {"username": "guest", "password": "pw"})
        await lobby.dispatch(guest, "login", {"username": "guest", "password": "pw"})
        with pytest.raises(RpcError) as ei:
            await lobby.dispatch(guest, "create_game", {"name": "x", "seed": 1})
        assert ei.value.code == ERR_AUTH  # non-host
    finally:
        await lobby.aclose()


async def test_rate_limit_rejects_a_flood(tmp_path: Path) -> None:
    store = AccountStore(tmp_path / "accounts.db")
    (tmp_path / "games").mkdir()
    lobby = LobbyServer(store, _config(), tmp_path / "games", rate_limit=3, tick_seconds=1000.0)
    try:
        s = Session(conn=None)
        req = {"jsonrpc": "2.0", "id": 1, "method": "hello",
               "params": {"fingerprint": wire.wire_fingerprint()}}
        results = [await lobby._handle(s, req) for _ in range(4)]  # type: ignore[attr-defined]
        assert results[-1]["error"]["code"] == -32003  # ERR_RATE_LIMITED on the 4th within 1s
    finally:
        await lobby.aclose()


# --- remote client over a real socket (WP68) ---------------------------------


async def _served_lobby(tmp_path: Path) -> tuple[LobbyServer, object, int]:
    (tmp_path / "games").mkdir()
    lobby = _lobby(tmp_path)
    ws_server = await lobby.serve("localhost", 0)
    port = ws_server.sockets[0].getsockname()[1]
    return lobby, ws_server, port


async def test_remote_client_login_join_play_and_push(tmp_path: Path) -> None:
    from edge.server.client import RemoteClient

    lobby, ws_server, port = await _served_lobby(tmp_path)
    client = RemoteClient(f"ws://localhost:{port}")
    try:
        await client.connect()
        await client.register("host", "pw")
        await client.login("host", "pw")
        gid = await client.create_game("alpha", seed=42)
        pid = await client.join_game(gid)
        assert pid == 1

        view = await client.game_view()  # a DTO decoded off the wire
        assert view.sector.sector_id > 0
        start = view.sector.sector_id
        neighbour = next(iter(lobby._games[gid].service.state.adjacency[start]))  # type: ignore[attr-defined]

        events = await client.apply(Warp(to_sector=neighbour))  # a mutator round-trip
        assert events  # events came back decoded
        # the same warp is pushed as a broadcast notification and reaches the stream
        pushed = await asyncio.wait_for(anext(client.events()), timeout=2.0)
        assert pushed is not None
        assert (await client.game_view()).sector.sector_id == neighbour  # view re-reads live
    finally:
        await client.aclose()
        await lobby.aclose()
        ws_server.close()
        await ws_server.wait_closed()


async def test_remote_client_reconnect_catches_up(tmp_path: Path) -> None:
    from edge.server.client import RemoteClient

    lobby, ws_server, port = await _served_lobby(tmp_path)
    client = RemoteClient(f"ws://localhost:{port}")
    try:
        await client.connect()
        await client.register("host", "pw")
        await client.login("host", "pw")
        gid = await client.create_game("alpha", seed=42)
        await client.join_game(gid)
        view = await client.game_view()
        neighbour = next(iter(lobby._games[gid].service.state.adjacency[view.sector.sector_id]))  # type: ignore[attr-defined]
        await client.apply(Warp(to_sector=neighbour))  # produces a persisted, pushed event
        # Drop the link *before* consuming the push, then reconnect and catch up.
        await client._conn.close()  # type: ignore[attr-defined]
        await asyncio.sleep(0.05)
        assert client.status == "disconnected"
        await client.reconnect()
        # events_since(0) replays the whole rail (we never consumed the push), so the warp returns.
        first = await asyncio.wait_for(anext(client.events()), timeout=2.0)
        assert first is not None
    finally:
        await client.aclose()
        await lobby.aclose()
        ws_server.close()
        await ws_server.wait_closed()


async def test_remote_client_refuses_a_fingerprint_mismatch(tmp_path: Path) -> None:
    from edge.server.client import RemoteClient, RemoteError

    lobby, ws_server, port = await _served_lobby(tmp_path)
    client = RemoteClient(f"ws://localhost:{port}")
    try:
        with pytest.raises(RemoteError):
            await client.connect(fingerprint="deadbeefdeadbeef")  # a build-skew hello, refused
    finally:
        await client.aclose()
        await lobby.aclose()
        ws_server.close()
        await ws_server.wait_closed()
