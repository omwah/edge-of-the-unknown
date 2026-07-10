"""Save-slot location and lifecycle (DESIGN §12).

One file per game in WAL mode under the user's home. The skeleton carries a
single save slot; "New game" replaces it, "Continue" reloads it. Kept out of
`app.py` so the menu can probe for a save without importing the app (no cycle).

Paths are resolved through functions (not module constants) so the location can
be redirected at runtime via ``EDGE_SAVE_DIR`` — tests point it at a scratch dir
so they never touch the real `~/.edge/games`.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import os
from pathlib import Path
import sqlite3

_ENV_OVERRIDE = "EDGE_SAVE_DIR"


def save_dir() -> Path:
    """The directory holding save slots (``EDGE_SAVE_DIR`` overrides the default)."""
    override = os.environ.get(_ENV_OVERRIDE)
    return Path(override) if override else Path.home() / ".edge" / "games"


def default_save() -> Path:
    """The single save slot — one file per game, WAL mode (DESIGN §12)."""
    return save_dir() / "default.db"


def has_save() -> bool:
    """Whether a resumable save exists (drives the menu's Continue affordance)."""
    return default_save().exists()


@dataclass(frozen=True)
class SaveSummary:
    """Lightweight save metadata for the menu (WP-UI11) — no replay needed."""

    seed: int
    created_at: str
    day_number: int
    commands: int
    last_played: str  # save-file mtime, local date


def save_summary() -> SaveSummary | None:
    """Read the save's meta row and log counters without loading the game.

    Opens the SQLite file read-only (never migrates or touches the slot) and
    returns None for a missing, locked, or unreadable save — the menu then
    just shows the plain Continue button.

    The meta row's `day_number` is the value at creation (derived state is
    never written back — DESIGN §12), so the *current* day is reconstructed
    the same way replay does: one `daily_turn_reset` cron firing per dawn in
    the durable maintenance log.
    """
    save = default_save()
    if not save.exists():
        return None
    try:
        with sqlite3.connect(f"file:{save}?mode=ro", uri=True) as conn:
            meta = conn.execute(
                "SELECT seed, created_at, day_number FROM meta WHERE id = 1"
            ).fetchone()
            commands = conn.execute("SELECT COUNT(*) FROM command_log").fetchone()[0]
            dawns = conn.execute(
                "SELECT COUNT(*) FROM maintenance_log WHERE cron_name = 'daily_turn_reset'"
            ).fetchone()[0]
        if meta is None:
            return None
        mtime = datetime.datetime.fromtimestamp(save.stat().st_mtime)
        return SaveSummary(seed=meta[0], created_at=meta[1], day_number=meta[2] + dawns,
                           commands=commands, last_played=mtime.strftime("%Y-%m-%d %H:%M"))
    except (sqlite3.Error, OSError):
        return None


def clear_slot() -> None:
    """Remove the save and its WAL/SHM sidecars so a new game starts clean."""
    save = default_save()
    for p in (save, save.with_name(save.name + "-wal"), save.with_name(save.name + "-shm")):
        p.unlink(missing_ok=True)
