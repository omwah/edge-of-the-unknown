"""Save-slot location and lifecycle (DESIGN §12).

One file per game in WAL mode under the user's home. The skeleton carries a
single save slot; "New game" replaces it, "Continue" reloads it. Kept out of
`app.py` so the menu can probe for a save without importing the app (no cycle).

Paths are resolved through functions (not module constants) so the location can
be redirected at runtime via ``EDGE_SAVE_DIR`` — tests point it at a scratch dir
so they never touch the real `~/.edge/games`.
"""

from __future__ import annotations

import os
from pathlib import Path

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


def clear_slot() -> None:
    """Remove the save and its WAL/SHM sidecars so a new game starts clean."""
    save = default_save()
    for p in (save, save.with_name(save.name + "-wal"), save.with_name(save.name + "-shm")):
        p.unlink(missing_ok=True)
