"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

import edge.config

# Dynamic overrides to keep the 1800+ unit tests stable against user-configured edits to config/default.yaml.
# This avoids duplicating large configuration, dialogue, and roster files on disk.
TEST_OVERRIDES: dict[str, Any] = {
    "turns_per_day": 250,
    "seed": 4,
    "bigbang": {
        "sector_count": 1000,
        "max_warps_per_sector": 6,
        "start_sector": "stardock",
        "topology_mode": "expansive",
        "cluster_max": 25,
        "intra_group_degree": 2.5,
        "inter_group_degree": 2.5,
        "core_sector_count": 10,
        "home_cluster_min": 3,
        "home_cluster_max": 6,
    },
    "aliens": {
        "band_disposition_bias": {
            "Hub": 0.0,
            "Frontier": -0.1,
            "Deep": -0.2,
            "Void": -0.3,
        },
    },
    "economy": {
        "floor_frac": 0.25,
        "starting_latinum": 2000,
        "tier_i_component_latinum": 2000,
        "fuel_ore": {"base": 11, "delta": 5},
        "organics": {"base": 5, "delta": 2},
        "equipment": {"base": 15, "delta": 7},
    },
    "scene": {
        "planet": {"min_height": 4, "max_height": 14},
        "planet_detail": {"min_height": 4, "max_height": 16},
        "port": {"min_width": 6, "max_width": 18, "min_height": 4, "max_height": 8},
        "ship": {"min_width": 6, "max_width": 16, "min_height": 3, "max_height": 6},
        "max_ships_shown": 2,
        "ship_face_inward_chance": 0.5,
    },
    "ui": {
        "warp_columns": 3,
        "warp_focus_default": "backtrack",
        "sidebar_width": 33,
        "sidebar_min_screen_width": 90,
    },
    "starter_ship": {
        "holds_total": 60,
    }
}

ROSTER_TEST_OVERRIDES: dict[str, Any] = {
    "ships_per_home": 4,
    "home_cluster_radius": 2,
    "core_traffic": 8,
}

_original_load_config = edge.config.load_config
_original_safe_load = yaml.safe_load

def _recursive_update(d: dict[str, Any], u: dict[str, Any]) -> None:
    for k, v in u.items():
        if isinstance(v, dict) and k in d and isinstance(d[k], dict):
            _recursive_update(d[k], v)
        else:
            d[k] = v

def _test_load_config(path: Path | str) -> edge.config.GameConfig:
    resolved_path = Path(path).resolve()
    is_default = resolved_path == Path(edge.config.DEFAULT_CONFIG_PATH).resolve()
    
    if is_default:
        def patched_safe_load(stream: Any) -> Any:
            data = _original_safe_load(stream)
            if isinstance(data, dict):
                if "config_version" in data:
                    _recursive_update(data, TEST_OVERRIDES)
                elif "core_governing_alliance_id" in data:
                    _recursive_update(data, ROSTER_TEST_OVERRIDES)
            return data
            
        yaml.safe_load = patched_safe_load
        try:
            return _original_load_config(path)
        finally:
            yaml.safe_load = _original_safe_load
    else:
        return _original_load_config(path)


edge.config.load_config = _test_load_config
edge.config.original_load_config = _original_load_config




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


@pytest.fixture(autouse=True)
def _deterministic_color_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin terminal color detection so snapshot captures are machine-independent.

    Rich/Textual sniff `COLORTERM`/`NO_COLOR` even under the headless test
    driver, so the same screen captured in a truecolor tmux and in a color-less
    CI shell produced different SVGs (WP-UI02's byte-stability held only within
    one machine). Every baseline is captured as truecolor.
    """
    monkeypatch.setenv("COLORTERM", "truecolor")
    monkeypatch.delenv("NO_COLOR", raising=False)
    yield
