"""WP64 — the lobby account store + auth (DESIGN §3, H15).

Identity lives in a server-side store, never in game state. A player enters a game only as a
`player_id` allocated by a logged `JoinGame`, so the roster rebuilds under replay.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from edge.server.accounts import AccountStore, AuthError


def _store(tmp_path: Path) -> AccountStore:
    return AccountStore(tmp_path / "accounts.db")


def test_register_and_login_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    aid = store.register("ada", "hunter2")
    token = store.login("ada", "hunter2")
    assert store.authenticate(token) == aid


def test_first_account_is_host(tmp_path: Path) -> None:
    store = _store(tmp_path)
    host = store.register("host", "pw")
    guest = store.register("guest", "pw")
    assert store.is_host(host) and not store.is_host(guest)


def test_duplicate_username_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.register("ada", "pw")
    with pytest.raises(AuthError):
        store.register("ada", "other")


def test_wrong_password_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.register("ada", "pw")
    with pytest.raises(AuthError):
        store.login("ada", "nope")


def test_unknown_user_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(AuthError):
        store.login("nobody", "pw")


def test_unknown_token_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(AuthError):
        store.authenticate("not-a-real-token")


def test_expired_token_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    store.register("ada", "pw")
    token = store.login("ada", "pw")
    # Jump past the token TTL — the next authenticate must reject and purge it.
    real_now = time.time()
    monkeypatch.setattr(time, "time", lambda: real_now + 10**9)
    with pytest.raises(AuthError):
        store.authenticate(token)


def test_binding_uniqueness_one_seat_per_account_per_game(tmp_path: Path) -> None:
    store = _store(tmp_path)
    aid = store.register("ada", "pw")
    gid = store.create_game("alpha", str(tmp_path / "alpha.db"), seed=1)
    assert store.binding(aid, gid) is None
    store.bind(aid, gid, player_id=2)
    assert store.binding(aid, gid) == 2
    store.bind(aid, gid, player_id=2)  # idempotent — still one seat
    assert store.binding(aid, gid) == 2


def test_duplicate_game_name_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_game("alpha", str(tmp_path / "a.db"), seed=1)
    with pytest.raises(AuthError):
        store.create_game("alpha", str(tmp_path / "b.db"), seed=2)


def test_persistence_across_reopen(tmp_path: Path) -> None:
    store = _store(tmp_path)
    aid = store.register("ada", "pw")
    store.close()
    reopened = AccountStore(tmp_path / "accounts.db")
    # Credentials survive a reopen (the store is durable, separate from any game save).
    token = reopened.login("ada", "pw")
    assert reopened.authenticate(token) == aid
