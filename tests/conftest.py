"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point the TUI save slot at a per-test scratch dir.

    `EdgeApp.start_new_game` writes to `~/.edge/games` by default (DESIGN §12);
    redirecting it here keeps the real user save untouched and stops one test's
    save from leaking into the next (e.g. tripping the "new game overwrites your
    save" confirmation in another test).
    """
    monkeypatch.setenv("EDGE_SAVE_DIR", str(tmp_path / "saves"))
    yield
