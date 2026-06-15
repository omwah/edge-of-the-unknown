"""WP0 harness check: the default config loads and validates (DESIGN §13)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from edge.config import load_default_config
from edge.core.config import GameConfig


def test_default_config_loads() -> None:
    cfg = load_default_config()
    assert isinstance(cfg, GameConfig)
    assert cfg.config_version == 1
    assert cfg.turns_per_day == 250


def test_default_economy_values() -> None:
    econ = load_default_config().economy
    # BNT's tuned trio (§8).
    assert (econ.fuel_ore.base, econ.fuel_ore.delta) == (11, 5)
    assert (econ.organics.base, econ.organics.delta) == (5, 2)
    assert (econ.equipment.base, econ.equipment.delta) == (15, 7)
    assert econ.floor_frac == 0.25
    assert econ.starting_latinum == 2_000
    assert econ.first_upgrade_aspect in {"holds", "shields"}


def test_default_bigbang_and_ship() -> None:
    cfg = load_default_config()
    assert cfg.bigbang.sector_count == 1_000
    assert cfg.bigbang.max_warps_per_sector == 6
    assert sum(cfg.bigbang.port_class_distribution) == 100
    assert len(cfg.bigbang.bands) == 4
    assert cfg.starter_ship.holds_total == 60


def test_config_is_frozen() -> None:
    cfg = load_default_config()
    with pytest.raises(ValidationError):
        cfg.turns_per_day = 1  # type: ignore[misc]


def test_from_mapping_rejects_unknown_keys() -> None:
    cfg = load_default_config()
    data = cfg.model_dump()
    data["nonsense_key"] = True
    with pytest.raises(ValidationError):
        GameConfig.from_mapping(data)
