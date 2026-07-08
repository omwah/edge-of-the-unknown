"""WP0 harness check: the default config loads and validates (DESIGN §13)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from edge.config import _merge_dialogue, load_default_config
from edge.core.config import GameConfig, SceneArtConfig


def test_default_config_loads() -> None:
    cfg = load_default_config()
    assert isinstance(cfg, GameConfig)
    assert cfg.config_version == 6  # Phase-4 M21 epoch (corp ownership kind + Player.corp_id/bounty, WP66)
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
    # Buyable hulls are priced; the never-sold hulls are price-0: the escape pod (§10)
    # and the orbital-platform set-piece (a starbase-role emplacement, §4.2).
    never_sold = {cfg.combat.escape_pod_class} | {
        s.id for s in cfg.ship_classes if s.role == "starbase"}
    assert all(s.price > 0 for s in cfg.ship_classes if s.id not in never_sold)
    assert cfg.ship_class(cfg.combat.escape_pod_class).price == 0
    assert cfg.hardware.components and cfg.hardware.tiers == ["I", "II"]  # III is barter-only
    assert cfg.ship_class("scout_marauder").subsystems is not None


def test_default_bigbang_and_ship() -> None:
    cfg = load_default_config()
    assert cfg.bigbang.sector_count == 1_000
    assert cfg.bigbang.max_warps_per_sector == 6
    assert sum(cfg.bigbang.port_class_distribution) == 100
    assert len(cfg.bigbang.topology.trunk.bands) == 4
    assert len(cfg.bigbang.topology.expansive.bands) == 4
    assert len(cfg.bigbang.active_bands()) == 4
    assert cfg.starter_ship.holds_total == 60


def test_species_home_bands_are_valid_distance_bands() -> None:
    cfg = load_default_config()
    assert cfg.roster is not None
    bands = {b.name for b in cfg.bigbang.active_bands()}
    # No species names a non-band like "Core" (the Core is the inner Hub, not a band).
    assert all(s.home_band in bands for s in cfg.roster.species)


def test_invalid_species_home_band_rejected() -> None:
    """A home_band that isn't a configured distance band (e.g. the old 'Core') fails."""
    data = load_default_config().model_dump()
    data["roster"]["species"][0]["home_band"] = "Core"
    with pytest.raises(ValidationError):
        GameConfig.from_mapping(data)


def test_presence_density_knobs() -> None:
    roster = load_default_config().roster
    assert roster is not None
    assert roster.ships_per_home >= 1 and roster.home_cluster_radius >= 1
    assert roster.core_traffic >= 0
    # The default roster spells the "noticeably busy" values.
    assert (roster.ships_per_home, roster.home_cluster_radius, roster.core_traffic) == (4, 2, 8)


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


def test_merge_dialogue_overlays_roster_fields() -> None:
    """A base dialogue doc's fields (personas / recency_k / grammar) overlay the roster."""
    roster: dict = {"species": [{"id": "vesk"}]}
    _merge_dialogue(roster, {"recency_k": 3, "personas": {"generic": {}}})
    assert roster["recency_k"] == 3
    assert roster["personas"] == {"generic": {}}


def test_merge_dialogue_splices_species_grammars_by_id() -> None:
    """`species_grammars` folds per-context into the matching species' `dialogue_pack`."""
    roster: dict = {"species": [{"id": "vesk"}, {"id": "terran", "dialogue_pack": {"farewell": ["x"]}}]}
    sidecar = {"species_grammars": {
        "vesk": {"greeting": [{"grammar": {"origin": ["hi"]}}]},
        "terran": {"greeting": [{"grammar": {"origin": ["hello"]}}]},
    }}
    _merge_dialogue(roster, sidecar)
    by_id = {s["id"]: s for s in roster["species"]}
    assert by_id["vesk"]["dialogue_pack"] == {"greeting": [{"grammar": {"origin": ["hi"]}}]}
    # an existing pack is preserved; the sidecar adds its context alongside.
    assert set(by_id["terran"]["dialogue_pack"]) == {"farewell", "greeting"}


def test_merge_dialogue_rejects_unknown_species() -> None:
    roster: dict = {"species": [{"id": "vesk"}]}
    with pytest.raises(ValueError, match="unknown species 'ghost'"):
        _merge_dialogue(roster, {"species_grammars": {"ghost": {"greeting": []}}})


def test_merge_dialogue_gates_spliced_offer_coordinates_on_intel() -> None:
    """A spliced offer_coordinates tip is gated on has_intel_target so it never shadows the
    generic 'nowhere new' catch-all with empty {target}/{coords}/... placeholders."""
    roster: dict = {"species": [{"id": "vesk"}]}
    sidecar = {"species_grammars": {"vesk": {
        "greeting": [{"grammar": {"origin": ["hi {player}"]}}],
        "offer_coordinates": [{"grammar": {"origin": ["go to {coords}"]}}],
    }}}
    _merge_dialogue(roster, sidecar)
    pack = roster["species"][0]["dialogue_pack"]
    assert pack["offer_coordinates"][0]["when"] == {"criteria": {"has_intel_target": True}}
    assert "when" not in pack["greeting"][0]  # only the intel context is gated


def test_merge_dialogue_offer_coordinates_falls_back_without_intel() -> None:
    """Self-contained: a gated species tip is skipped when has_intel_target is false, so the
    generic 'nowhere new' catch-all speaks instead of a tip with blank placeholders."""
    import random

    from edge.core.config import RosterConfig
    from edge.dialogue.select import build_chain, select_line

    roster_data: dict = {
        "core_governing_alliance_id": 1,
        "alliances": [{"id": 1, "name": "Fed", "banner": "x"}],
        "species": [{"id": "vesk", "name": "Vesk", "archetype_id": "a", "persona": "generic",
                     "disposition_center": 0.9, "tech_level": 5, "home_band": "Hub"}],
        "personas": {"generic": {"offer_coordinates": [
            {"when": {"criteria": {"has_intel_target": True}},
             "variants": ["Seek {target} at sector {coords}, {player}."]},
            {"variants": ["No fresh coordinates for you, {player}."]},
        ]}},
    }
    sidecar = {"species_grammars": {"vesk": {"offer_coordinates": [
        {"grammar": {"origin": ["Make for sector {coords}, {distance} jumps into the {band}."]}},
    ]}}}
    _merge_dialogue(roster_data, sidecar)
    roster = RosterConfig.model_validate(roster_data)
    sp = roster.species_by_id("vesk")
    chain = build_chain(roster, sp, sp.persona)
    ctx = {"player": "Vale"}
    text, _ = select_line(chain, "offer_coordinates", standing="neutral", treaty=False,
                          ctx=ctx, recency=(), rng=random.Random(1), k=2,
                          facts={"has_intel_target": False})
    assert text == "No fresh coordinates for you, Vale."  # generic fallback, not the blank tip


def test_species_lore_config() -> None:
    cfg = load_default_config()
    for sp in cfg.roster.species:
        assert sp.lore is not None
        assert isinstance(sp.lore.biology_and_appearance, str)
        assert isinstance(sp.lore.psychology_and_culture, str)
        assert isinstance(sp.lore.diplomacy_and_behavior, str)
        assert isinstance(sp.lore.relationships, str)
        assert isinstance(sp.lore.combat_and_ships, str)


def test_production_config_validates() -> None:
    """Ensure the actual production config loads and validates against the schema."""
    from pathlib import Path
    import edge.config
    from edge.core.config import GameConfig

    prod_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
    # Load using the original unpatched load_config to check if the real production config is valid
    cfg = getattr(edge.config, "original_load_config", edge.config.load_config)(prod_path)
    assert isinstance(cfg, GameConfig)
    assert cfg.roster is not None


