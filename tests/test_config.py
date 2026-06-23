"""WP0 harness check: the default config loads and validates (DESIGN §13)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from edge.config import load_default_config
from edge.core.config import GameConfig, SceneArtConfig


def test_default_config_loads() -> None:
    cfg = load_default_config()
    assert isinstance(cfg, GameConfig)
    assert cfg.config_version == 2  # Phase-2 schema epoch (engine room, §4.1)
    assert cfg.turns_per_day == 250
    assert cfg.seed == 4  # default.yaml pins a curated seed; empty ⇒ random at start
    assert cfg.bigbang.start_sector == "stardock"  # the player starts at the StarDock


def test_seed_accepts_null_for_random() -> None:
    cfg = GameConfig.model_validate({**load_default_config().model_dump(), "seed": None})
    assert cfg.seed is None  # empty seed ⇒ a random universe is rolled at start


def test_default_economy_values() -> None:
    econ = load_default_config().economy
    # BNT's tuned trio (§8).
    assert (econ.fuel_ore.base, econ.fuel_ore.delta) == (11, 5)
    assert (econ.organics.base, econ.organics.delta) == (5, 2)
    assert (econ.equipment.base, econ.equipment.delta) == (15, 7)
    assert econ.floor_frac == 0.25
    assert econ.starting_latinum == 2_000
    assert econ.tier_i_component_latinum == 2_000


def test_default_scene_art_values() -> None:
    scene = load_default_config().scene
    # Sprites are clamped to [min, max] per axis. Planet width is derived as
    # 2*height (both bounds) so the disc stays round (cells are ~2:1).
    assert (scene.planet.min_height, scene.planet.max_height) == (4, 14)
    assert (scene.planet.min_width, scene.planet.max_width) == (8, 28)
    # PlanetScreen's orbit planet is configured independently of the SectorView one.
    assert (scene.planet_detail.min_height, scene.planet_detail.max_height) == (4, 16)
    assert (scene.port.min_width, scene.port.max_width) == (6, 18)
    assert (scene.port.min_height, scene.port.max_height) == (4, 8)
    assert (scene.ship.min_width, scene.ship.max_width) == (6, 16)
    assert (scene.ship.min_height, scene.ship.max_height) == (3, 6)
    assert scene.max_ships_shown == 2
    assert scene.ship_face_inward_chance == 0.5


def test_scene_art_is_optional_with_defaults() -> None:
    # The whole `scene:` block is optional — GameConfig.scene defaults to these,
    # so configs/saves predating it still validate.
    scene = SceneArtConfig()
    assert scene.planet.max_width == 2 * scene.planet.max_height == 24
    assert scene.planet.min_width == 2 * scene.planet.min_height
    assert scene.max_ships_shown == 2


def test_default_ui_values() -> None:
    ui = load_default_config().ui
    assert ui.warp_columns == 3
    assert ui.warp_focus_default == "first"
    assert ui.sidebar_width == 33
    assert ui.sidebar_min_screen_width == 90


def test_scene_art_rejects_min_above_max() -> None:
    from edge.core.config import PlanetSpriteSize, SpriteSize

    with pytest.raises(ValidationError):
        SpriteSize(max_width=10, max_height=10, min_width=20)
    with pytest.raises(ValidationError):
        PlanetSpriteSize(max_height=8, min_height=12)


def test_default_ship_classes_and_hardware() -> None:
    cfg = load_default_config()
    ids = {s.id for s in cfg.ship_classes}
    assert {"scout_marauder", "missile_frigate", "battleship", "imperial_starship"} <= ids
    assert all(s.price > 0 for s in cfg.ship_classes)  # buyable hulls are priced
    assert cfg.hardware.components and cfg.hardware.tiers == ["I", "II"]  # III is barter-only
    assert cfg.ship_class("scout_marauder").subsystems is not None


def test_default_bigbang_and_ship() -> None:
    cfg = load_default_config()
    assert cfg.bigbang.sector_count == 1_000
    assert cfg.bigbang.max_warps_per_sector == 6
    assert sum(cfg.bigbang.port_class_distribution) == 100
    assert len(cfg.bigbang.bands) == 4
    assert cfg.starter_ship.holds_total == 60


def test_species_home_bands_are_valid_distance_bands() -> None:
    cfg = load_default_config()
    assert cfg.roster is not None
    bands = {b.name for b in cfg.bigbang.bands}
    # No species names a non-band like "Core" (the Core is the inner Hub, not a band).
    assert all(s.home_band in bands for s in cfg.roster.species)


def test_invalid_species_home_band_rejected() -> None:
    """A home_band that isn't a configured distance band (e.g. the old 'Core') fails."""
    data = load_default_config().model_dump()
    data["roster"]["species"][0]["home_band"] = "Core"
    with pytest.raises(ValidationError):
        GameConfig.from_mapping(data)


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
