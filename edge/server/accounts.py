"""`edge/server/accounts.py` — identity, kept out of core (WP64, H15).

DESIGN §3/§14. Accounts, password hashes, session tokens, and the account↔game↔player_id
bindings live here, in a **server-side SQLite that is not a game save** — never inside
`UniverseState`, never in `state_hash`. A human enters a game exclusively as a `player_id`
allocated by a logged `JoinGame` (the §3 seam); this store only records *which account holds
which seat*, so the replay contract is untouched by identity.

Passwords are salted PBKDF2-HMAC-SHA256 via stdlib `hashlib` (no third-party crypto); tokens
are `secrets.token_urlsafe`. This is honest hygiene for a hosted hobby server, not a hardened
auth system — stated plainly, like the rate limiter in `net.py`.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_PBKDF2_ITERATIONS = 200_000  # ~tens of ms per hash on commodity hardware — deliberate cost
_SALT_BYTES = 16
_TOKEN_TTL_SECONDS = 24 * 3600  # a session token lasts a day; login again after that


class AuthError(Exception):
    """A registration/login/token failure — a lobby rejection, surfaced to the client."""


@dataclass(frozen=True)
class GameRecord:
    """Lobby bookkeeping for one hosted game (not game state — H15)."""

    game_id: int
    name: str
    db_path: str
    seed: int


class AccountStore:
    """The lobby's identity + bookkeeping store (a plain SQLite file, separate from any save)."""

    def __init__(self, path: Path | str) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT UNIQUE NOT NULL,
                pw_hash    BLOB NOT NULL,
                salt       BLOB NOT NULL,
                is_host    INTEGER NOT NULL DEFAULT 0,   -- first account registered hosts games
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT UNIQUE NOT NULL,
                db_path TEXT NOT NULL,
                seed    INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bindings (
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                game_id    INTEGER NOT NULL REFERENCES games(game_id),
                player_id  INTEGER NOT NULL,
                PRIMARY KEY (account_id, game_id)   -- one seat per account per game
            );
            """
        )
        self._conn.commit()

    # --- accounts ------------------------------------------------------------

    def register(self, username: str, password: str) -> int:
        """Create an account (PBKDF2-hashed password). The first account is the host.

        Raises `AuthError` if the username is taken. Host status is positional — a hobby-server
        convenience so `create_game` has an owner without a separate admin flow.
        """
        salt = secrets.token_bytes(_SALT_BYTES)
        pw_hash = self._hash(password, salt)
        is_host = 1 if self._conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0 else 0
        try:
            cur = self._conn.execute(
                "INSERT INTO accounts (username, pw_hash, salt, is_host, created_at) VALUES (?,?,?,?,?)",
                (username, pw_hash, salt, is_host, time.time()),
            )
        except sqlite3.IntegrityError as exc:
            raise AuthError(f"username {username!r} is taken") from exc
        self._conn.commit()
        assert cur.lastrowid is not None
        return int(cur.lastrowid)

    def login(self, username: str, password: str) -> str:
        """Verify credentials and mint a session token (constant-time hash compare)."""
        row = self._conn.execute(
            "SELECT id, pw_hash, salt FROM accounts WHERE username = ?", (username,)).fetchone()
        # Always run a hash even on unknown users so timing does not reveal account existence.
        salt = row["salt"] if row else b"\x00" * _SALT_BYTES
        candidate = self._hash(password, salt)
        if row is None or not hmac.compare_digest(candidate, row["pw_hash"]):
            raise AuthError("invalid username or password")
        token = secrets.token_urlsafe(32)
        self._conn.execute(
            "INSERT INTO sessions (token, account_id, expires_at) VALUES (?,?,?)",
            (token, row["id"], time.time() + _TOKEN_TTL_SECONDS),
        )
        self._conn.commit()
        return token

    def authenticate(self, token: str) -> int:
        """Resolve a token to its account id, or raise if unknown/expired."""
        row = self._conn.execute(
            "SELECT account_id, expires_at FROM sessions WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise AuthError("unknown session token — log in again")
        if row["expires_at"] < time.time():
            self._conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            self._conn.commit()
            raise AuthError("session token expired — log in again")
        return int(row["account_id"])

    def is_host(self, account_id: int) -> bool:
        row = self._conn.execute("SELECT is_host FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return bool(row and row["is_host"])

    # --- games + bindings ----------------------------------------------------

    def create_game(self, name: str, db_path: str, seed: int) -> int:
        """Record a new hosted game (lobby bookkeeping only). Raises if the name is taken."""
        try:
            cur = self._conn.execute(
                "INSERT INTO games (name, db_path, seed) VALUES (?,?,?)", (name, db_path, seed))
        except sqlite3.IntegrityError as exc:
            raise AuthError(f"a game named {name!r} already exists") from exc
        self._conn.commit()
        assert cur.lastrowid is not None
        return int(cur.lastrowid)

    def list_games(self) -> list[GameRecord]:
        rows = self._conn.execute(
            "SELECT game_id, name, db_path, seed FROM games ORDER BY game_id").fetchall()
        return [GameRecord(r["game_id"], r["name"], r["db_path"], r["seed"]) for r in rows]

    def game(self, game_id: int) -> GameRecord:
        row = self._conn.execute(
            "SELECT game_id, name, db_path, seed FROM games WHERE game_id = ?", (game_id,)).fetchone()
        if row is None:
            raise AuthError(f"no game {game_id}")
        return GameRecord(row["game_id"], row["name"], row["db_path"], row["seed"])

    def binding(self, account_id: int, game_id: int) -> int | None:
        """The player_id this account already holds in this game, or None (needs a fresh join)."""
        row = self._conn.execute(
            "SELECT player_id FROM bindings WHERE account_id = ? AND game_id = ?",
            (account_id, game_id)).fetchone()
        return int(row["player_id"]) if row else None

    def bound_seats(self, game_id: int) -> set[int]:
        """Every player_id already claimed by an account in this game (across all accounts)."""
        rows = self._conn.execute(
            "SELECT player_id FROM bindings WHERE game_id = ?", (game_id,)).fetchall()
        return {int(r["player_id"]) for r in rows}

    def bind(self, account_id: int, game_id: int, player_id: int) -> None:
        """Record the account↔game↔player seat (idempotent per account+game — one seat)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO bindings (account_id, game_id, player_id) VALUES (?,?,?)",
            (account_id, game_id, player_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
