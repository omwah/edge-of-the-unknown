"""Persistence behind a repository interface (DESIGN §12).

`Repository` is the abstract seam (the swap point for PostgreSQL later);
`SqliteRepository` is the Phase-1 implementation — one WAL file per game, with
the meta row plus the durable command and event logs. Writes commit immediately,
so a command is durable the moment it is recorded (the BBS hang-up-and-resume
property, §12).
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from edge.core.events import Event
from edge.core.models import Game
from edge.core.rules import Command
from edge.store import codec

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


@dataclass(frozen=True)
class GameMeta:
    seed: int
    config_version: int
    created_at: str
    day_number: int
    core_governing_alliance_id: int | None


@dataclass(frozen=True)
class RecordedCommand:
    seq: int
    player_id: int
    command: Command


@dataclass(frozen=True)
class RecordedMaintenance:
    """One persisted engine-cron firing (WP12): which cron, at which tick, and the
    command it followed (its place in the merged replay order)."""

    seq: int
    after_command_seq: int
    cron_name: str
    tick: int


@dataclass(frozen=True)
class EngineState:
    """The persisted ticker schedule (WP12): the tick counter + each cron's next-due tick."""

    tick: int
    schedule: dict[str, int]


class Repository(ABC):
    """The persistence seam. A new game writes meta once, then appends commands."""

    @abstractmethod
    def save_meta(self, game: Game) -> None: ...

    @abstractmethod
    def load_meta(self) -> GameMeta: ...

    @abstractmethod
    def append_command(self, player_id: int, command: Command) -> int: ...

    @abstractmethod
    def load_commands(self) -> list[RecordedCommand]: ...

    @abstractmethod
    def append_event(self, event: Event, tick: int = 0) -> int: ...

    @abstractmethod
    def load_events(self) -> list[Event]: ...

    @abstractmethod
    def append_maintenance(self, cron_name: str, tick: int, after_command_seq: int) -> int: ...

    @abstractmethod
    def load_maintenance(self) -> list[RecordedMaintenance]: ...

    @abstractmethod
    def save_engine_state(self, tick: int, schedule: dict[str, int]) -> None: ...

    @abstractmethod
    def load_engine_state(self) -> EngineState | None: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> Repository:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.close()


class SqliteRepository(Repository):
    def __init__(self, path: Path | str) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        self._conn.commit()

    def save_meta(self, game: Game) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO meta"
            " (id, seed, config_version, created_at, day_number, core_governing_alliance_id)"
            " VALUES (1, ?, ?, ?, ?, ?)",
            (game.seed, game.config_version, game.created_at, game.day_number,
             game.core_governing_alliance_id),
        )
        self._conn.commit()

    def load_meta(self) -> GameMeta:
        row = self._conn.execute(
            "SELECT seed, config_version, created_at, day_number, core_governing_alliance_id"
            " FROM meta WHERE id = 1"
        ).fetchone()
        if row is None:
            raise LookupError("no game meta saved")
        return GameMeta(seed=row[0], config_version=row[1], created_at=row[2],
                        day_number=row[3], core_governing_alliance_id=row[4])

    def append_command(self, player_id: int, command: Command) -> int:
        type_, payload = codec.encode_command(command)
        cur = self._conn.execute(
            "INSERT INTO command_log (player_id, type, payload) VALUES (?, ?, ?)",
            (player_id, type_, json.dumps(payload)),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def load_commands(self) -> list[RecordedCommand]:
        rows = self._conn.execute(
            "SELECT seq, player_id, type, payload FROM command_log ORDER BY seq"
        ).fetchall()
        return [
            RecordedCommand(seq=r[0], player_id=r[1], command=codec.decode_command(r[2], json.loads(r[3])))
            for r in rows
        ]

    def append_event(self, event: Event, tick: int = 0) -> int:
        type_, payload = codec.encode_event(event)
        cur = self._conn.execute(
            "INSERT INTO event_log (tick, type, payload) VALUES (?, ?, ?)",
            (tick, type_, json.dumps(payload)),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def load_events(self) -> list[Event]:
        rows = self._conn.execute(
            "SELECT type, payload FROM event_log ORDER BY seq"
        ).fetchall()
        return [codec.decode_event(r[0], json.loads(r[1])) for r in rows]

    def append_maintenance(self, cron_name: str, tick: int, after_command_seq: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO maintenance_log (after_command_seq, cron_name, tick) VALUES (?, ?, ?)",
            (after_command_seq, cron_name, tick),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def load_maintenance(self) -> list[RecordedMaintenance]:
        rows = self._conn.execute(
            "SELECT seq, after_command_seq, cron_name, tick FROM maintenance_log ORDER BY seq"
        ).fetchall()
        return [RecordedMaintenance(seq=r[0], after_command_seq=r[1], cron_name=r[2], tick=r[3])
                for r in rows]

    def save_engine_state(self, tick: int, schedule: dict[str, int]) -> None:
        self._conn.execute("INSERT OR REPLACE INTO engine_state (id, tick) VALUES (1, ?)", (tick,))
        for name, next_due in schedule.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO cron_schedule (name, next_due) VALUES (?, ?)", (name, next_due)
            )
        self._conn.commit()

    def load_engine_state(self) -> EngineState | None:
        row = self._conn.execute("SELECT tick FROM engine_state WHERE id = 1").fetchone()
        if row is None:
            return None
        schedule = {
            name: next_due
            for name, next_due in self._conn.execute("SELECT name, next_due FROM cron_schedule").fetchall()
        }
        return EngineState(tick=row[0], schedule=schedule)

    def close(self) -> None:
        self._conn.close()
