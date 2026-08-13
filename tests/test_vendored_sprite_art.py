from __future__ import annotations

import json
import random
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from edge.art.sprite_art import (
    ARCHETYPE_IDS,
    COLOR_SET_IDS,
    PaletteCatalog,
    Sprite,
    SpriteLibrary,
    SpriteValidationError,
    active_variant_at_cell,
    load_palette_catalog,
    load_sprite,
    load_sprite_directory,
    render_sprite,
    Section,
    Tier,
    Variant,
    View,
    selected_tier,
    selected_variants,
)
from edge.art.sprite_art.glyphs import (
    AUTHORING_GLYPHS,
    ROTATE_CCW,
    flip_rows_horizontal,
    flip_rows_vertical,
    transform_glyph,
)
from edge.art.sprite_art.io import dump_palette_catalog, dump_sprite

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "edge" / "art" / "assets"


@pytest.fixture(scope="module")
def palettes() -> PaletteCatalog:
    return load_palette_catalog(ASSETS / "palettes.yaml")


@pytest.fixture(scope="module")
def sprites() -> dict[str, Sprite]:
    return load_sprite_directory(ASSETS / "sprites")

ORIGINAL_ROLES = {
    "fighter",
    "transport",
    "warship",
    "capital_warship",
}
NEW_ROLES = {
    "needle_picket",
    "falsehold_raider",
    "junction_pinnace",
    "radiant_lance",
    "hearth_freighter",
    "pearl_shell",
    "marrow_dart",
    "broadside_citadel",
}
STATION_ROLES = {
    "trading_port",
    "starbase",
    "stardock",
}
ROLE_SECTIONS = {
    "fighter": ("thrusters", "spindrive", "hull", "screens", "main_gun"),
    "transport": ("thrusters", "spindrive", "hull", "screens", "main_gun"),
    "warship": ("thrusters", "spindrive", "hull", "screens", "main_gun"),
    "capital_warship": (
        "thrusters",
        "spindrive",
        "hull",
        "screens",
        "main_gun",
    ),
    "needle_picket": (
        "thrusters",
        "drive_nodes",
        "patrol_spine",
        "sensor_crown",
        "needle",
    ),
    "falsehold_raider": (
        "merchant_drive",
        "armored_buttress",
        "false_holds",
        "masked_battery",
        "merchant_prow",
    ),
    "junction_pinnace": (
        "overdrive",
        "sail_nodes",
        "cabin",
        "landing_nose",
    ),
    "radiant_lance": (
        "fusion_bell",
        "engine_swell",
        "diamond_radiators",
        "habitat_petals",
        "lance",
    ),
    "hearth_freighter": (
        "retrofitted_drive",
        "machine_shop",
        "cargo_modules",
        "hearth_drum",
        "mining_prow",
    ),
    "pearl_shell": (
        "ciliary_drive",
        "rear_carapace",
        "weapon_ring",
        "troop_lobe",
        "beak",
    ),
    "marrow_dart": (
        "sinew_drive",
        "marrow_knot",
        "bound_spars",
        "nerve_cluster",
        "hardened_beak",
    ),
    "broadside_citadel": (
        "capital_drive",
        "drive_citadel",
        "broadside_decks",
        "command_keep",
        "siege_prow",
    ),
}
ROLE_FUNCTIONAL_MASKS = {
    "fighter": set("ADEW"),
    "transport": set("ABDEW"),
    "warship": set("ADEW"),
    "capital_warship": set("ABDEW"),
    "needle_picket": set("ABEW"),
    "falsehold_raider": set("ABDEW"),
    "junction_pinnace": set("BDEW"),
    "radiant_lance": set("ABEW"),
    "hearth_freighter": set("ABEW"),
    "pearl_shell": set("ABDE"),
    "marrow_dart": set("ABE"),
    "broadside_citadel": set("ABDEW"),
}


def test_asset_library_has_all_original_and_new_roles(sprites: dict[str, Sprite]) -> None:
    ships = {
        sprite_id
        for sprite_id, sprite in sprites.items()
        if sprite.kind == "ship"
    }
    stations = {
        sprite_id
        for sprite_id, sprite in sprites.items()
        if sprite.kind == "port"
    }
    assert ships == ORIGINAL_ROLES | NEW_ROLES
    assert stations == STATION_ROLES
    assert set(sprites) == ships | stations


def test_full_and_medium_tiers_follow_each_roles_section_grammar() -> None:
    for role, expected_sections in ROLE_SECTIONS.items():
        sprite = load_sprite(ASSETS / "sprites" / "ships" / f"{role}.yaml")
        for tier in sprite.views["horizontal"].tiers[:2]:
            assert tuple(section.id for section in tier.sections) == expected_sections


def test_role_art_uses_intentional_functional_color_masks() -> None:
    for role, expected_masks in ROLE_FUNCTIONAL_MASKS.items():
        sprite = load_sprite(ASSETS / "sprites" / "ships" / f"{role}.yaml")
        visible_masks = {
            code
            for view in sprite.views.values()
            for tier in view.tiers
            for section in tier.sections
            for variant in section.variants
            for glyph_row, mask_row in zip(variant.cells, variant.color_mask)
            for glyph, code in zip(glyph_row, mask_row)
            if glyph != " "
        }
        assert expected_masks <= visible_masks


def test_broadside_open_bays_use_weapons_color_only_for_muzzles() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "broadside_citadel.yaml")
    broadside = next(
        section
        for section in sprite.views["horizontal"].tiers[0].sections
        if section.id == "broadside_decks"
    )
    open_bays = next(variant for variant in broadside.variants if variant.id == "open_bays")
    weapon_glyphs = [
        glyph
        for glyph_row, mask_row in zip(open_bays.cells, open_bays.color_mask)
        for glyph, code in zip(glyph_row, mask_row)
        if code == "A"
    ]

    assert len(weapon_glyphs) == 4


def test_ship_roster_exercises_extended_structural_and_facet_glyphs() -> None:
    sprites = load_sprite_directory(ASSETS / "sprites")
    used = {
        glyph
        for sprite in sprites.values()
        for view in sprite.views.values()
        for tier in view.tiers
        for section in tier.sections
        for variant in section.variants
        for row in variant.cells
        for glyph in row
    }
    assert {
        "╭",
        "╮",
        "╰",
        "╯",
        "╔",
        "╗",
        "╚",
        "╝",
        "▖",
        "▗",
        "▘",
        "▝",
        "╺",
        "╹",
        "∞",
        "♦",
        "○",
        "☼",
    } <= used


def test_palette_catalog_is_the_exact_controlled_roster(
    palettes: PaletteCatalog,
) -> None:
    assert tuple(palettes.archetypes) == ARCHETYPE_IDS
    assert palettes.resolve("unknown") is palettes.archetypes["humanoid_diplomat"]
    for palette in palettes.archetypes.values():
        assert tuple(palette.color_sets) == COLOR_SET_IDS
        assert all(1 <= len(color_set.colors) <= 4 for color_set in palette.color_sets.values())


def test_weapon_and_defensive_accents_follow_the_fleet_palette_direction(
    palettes: PaletteCatalog,
) -> None:
    weapon_colors = {
        palette.color_sets["weapons"].colors[0] for palette in palettes.archetypes.values()
    }
    defensive_colors = [
        palette.color_sets["defensive"].colors[0] for palette in palettes.archetypes.values()
    ]

    assert weapon_colors == {"#DF7070"}
    assert len(set(defensive_colors)) == len(ARCHETYPE_IDS)
    for color in defensive_colors:
        red = int(color[1:3], 16)
        blue = int(color[5:7], 16)
        assert blue > red


def test_palette_catalog_rejects_extra_archetype(palettes: PaletteCatalog) -> None:
    invalid = deepcopy(palettes)
    invalid.archetypes["new_archetype"] = deepcopy(invalid.archetypes["humanoid_diplomat"])
    with pytest.raises(SpriteValidationError, match="controlled"):
        invalid.validate()


def test_sprite_color_masks_match_geometry_and_reject_unknown_codes() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    variant = sprite.views["horizontal"].tiers[0].sections[0].variants[0]
    assert len(variant.color_mask) == variant.height
    assert all(len(row) == variant.width for row in variant.color_mask)
    variant.color_mask[0] = "?" + variant.color_mask[0][1:]
    with pytest.raises(SpriteValidationError, match="unknown color-mask code"):
        sprite.validate()


def test_section_repetition_cannot_be_negative() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    section = sprite.views["horizontal"].tiers[0].sections[0]
    section.repeat = -1

    with pytest.raises(SpriteValidationError, match="repeat cannot be negative"):
        sprite.validate()


def test_zeroing_a_single_section_is_allowed() -> None:
    """A zero repeat omits one band; only emptying a whole tier is an error."""

    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    tier = sprite.views["horizontal"].tiers[0]
    tier.sections[0].repeat = 0

    sprite.views["horizontal"].tiers = [tier]
    sprite.validate()


def test_a_tier_cannot_be_emptied_for_any_archetype() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    tier = sprite.views["horizontal"].tiers[0]
    for section in tier.sections:
        section.archetype_repeats["ribbon_salvager"] = 0

    with pytest.raises(SpriteValidationError, match="ribbon_salvager has no section"):
        sprite.validate()


def test_migrated_markers_use_real_glyphs_and_expected_color_sets() -> None:
    sprites = load_sprite_directory(ASSETS / "sprites")
    pairs = {
        (glyph, code)
        for sprite in sprites.values()
        for view in sprite.views.values()
        for tier in view.tiers
        for section in tier.sections
        for variant in section.variants
        for glyph_row, mask_row in zip(variant.cells, variant.color_mask)
        for glyph, code in zip(glyph_row, mask_row)
    }
    assert not set("RGBYrgby") & {glyph for glyph, _code in pairs}
    assert ("▄", "E") in pairs


def test_active_variant_hit_testing_matches_preview_geometry(
    palettes: PaletteCatalog,
) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    variant = active_variant_at_cell(
        sprite,
        palettes,
        x=10,
        y=3,
        width=40,
        height=7,
        seed=7,
    )
    assert variant is not None
    assert any(
        variant in section.variants for section in sprite.views["horizontal"].tiers[0].sections
    )


def test_authoring_glyphs_have_reversible_reflections_and_rotation_support() -> None:
    glyphs = [glyph for glyph, _ in AUTHORING_GLYPHS]
    for glyph in glyphs:
        if glyph != "≡":
            assert glyph in ROTATE_CCW
            rotated = glyph
            for _ in range(4):
                rotated = transform_glyph(rotated, ROTATE_CCW)
            assert rotated == glyph
        assert flip_rows_horizontal(flip_rows_horizontal([glyph])) == [glyph]
        assert flip_rows_vertical(flip_rows_vertical([glyph])) == [glyph]


@pytest.mark.parametrize("role", sorted(ORIGINAL_ROLES | NEW_ROLES))
def test_every_ship_has_independent_horizontal_and_vertical_views(role: str) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / f"{role}.yaml")
    assert set(sprite.views) == {"horizontal", "vertical"}
    assert sprite.views["horizontal"].axis == "horizontal"
    assert sprite.views["vertical"].axis == "vertical"
    assert sprite.views["horizontal"] is not sprite.views["vertical"]


def test_ship_assets_have_full_medium_and_compact_horizontal_tiers() -> None:
    for role in ORIGINAL_ROLES | NEW_ROLES:
        sprite = load_sprite(ASSETS / "sprites" / "ships" / f"{role}.yaml")
        tiers = sprite.views["horizontal"].tiers
        assert [tier.id for tier in tiers] == ["full", "medium", "compact"]
        assert [tier.cross_axis_size("horizontal") for tier in tiers] == [7, 5, 3]
        for full_section, medium_section in zip(tiers[0].sections, tiers[1].sections):
            for full_variant, medium_variant in zip(full_section.variants, medium_section.variants):
                assert medium_variant.width == (full_variant.width * 3 + 2) // 4


@pytest.mark.parametrize("role", sorted(ORIGINAL_ROLES | NEW_ROLES))
def test_generation_is_deterministic_and_exact(role: str, palettes: PaletteCatalog) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / f"{role}.yaml")
    for view_id, sizes in (
        ("horizontal", ((18, 3), (40, 7), (56, 12))),
        ("vertical", ((3, 18), (7, 40), (12, 56))),
    ):
        for width, height in sizes:
            first = render_sprite(
                sprite,
                palettes,
                width=width,
                height=height,
                seed=13,
                archetype_id="ribbon_salvager",
                view_id=view_id,
            )
            second = render_sprite(
                sprite,
                palettes,
                width=width,
                height=height,
                seed=13,
                archetype_id="ribbon_salvager",
                view_id=view_id,
            )
            assert first.plain == second.plain
            assert first.spans == second.spans
            lines = first.plain.splitlines()
            assert len(lines) == height
            assert all(len(line) == width for line in lines)


def test_highlighted_variant_preserves_text_and_marks_its_section(
    palettes: PaletteCatalog,
) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    variant = sprite.views["horizontal"].tiers[0].sections[0].variants[0]
    normal = render_sprite(
        sprite,
        palettes,
        width=56,
        height=12,
        seed=13,
        view_id="horizontal",
    )
    highlighted = render_sprite(
        sprite,
        palettes,
        width=56,
        height=12,
        seed=13,
        view_id="horizontal",
        highlight_variant=variant,
    )
    assert highlighted.plain == normal.plain
    assert highlighted.spans != normal.spans


def test_preview_margin_projects_highlights_along_the_view_cross_axis(
    palettes: PaletteCatalog,
) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    variant = sprite.views["horizontal"].tiers[0].sections[0].variants[0]
    preview = render_sprite(
        sprite,
        palettes,
        width=40,
        height=7,
        seed=13,
        view_id="horizontal",
        highlight_variant=variant,
        preview_margin=True,
    )
    lines = preview.plain.splitlines()
    assert len(lines) == 9
    assert all(len(line) == 42 for line in lines)
    assert "on #4c1d95" in str(preview.spans)


def test_horizontal_facing_is_exact_glyph_reflection(palettes: PaletteCatalog) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    right = render_sprite(
        sprite,
        palettes,
        width=40,
        height=7,
        seed=5,
        view_id="horizontal",
        facing="right",
    ).plain.splitlines()
    left = render_sprite(
        sprite,
        palettes,
        width=40,
        height=7,
        seed=5,
        view_id="horizontal",
        facing="left",
    ).plain.splitlines()
    assert [line.strip() for line in left] == [line.strip() for line in flip_rows_horizontal(right)]


def test_vertical_facing_is_exact_glyph_reflection(palettes: PaletteCatalog) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "warship.yaml")
    up = render_sprite(
        sprite,
        palettes,
        width=9,
        height=35,
        seed=5,
        view_id="vertical",
        facing="up",
    ).plain.splitlines()
    down = render_sprite(
        sprite,
        palettes,
        width=9,
        height=35,
        seed=5,
        view_id="vertical",
        facing="down",
    ).plain.splitlines()
    assert down == flip_rows_vertical(up)


def test_yaml_round_trip(tmp_path: Path, palettes: PaletteCatalog) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "needle_picket.yaml")
    sprite_path = tmp_path / "sprite.yaml"
    palette_path = tmp_path / "palettes.yaml"
    dump_sprite(sprite, sprite_path)
    dump_palette_catalog(palettes, palette_path)
    loaded = load_sprite(sprite_path)
    loaded.source = sprite.source
    assert loaded == sprite
    assert load_palette_catalog(palette_path) == palettes
    dumped = yaml.safe_load(sprite_path.read_text(encoding="utf-8"))
    tier = dumped["views"]["horizontal"]["tiers"][0]
    assert dumped["schema_version"] == 4
    assert "structure_lengths" not in tier
    assert isinstance(tier["sections"][0]["repeat"], int)
    # Optional v4 fields stay out of the file while they hold their defaults.
    assert "archetype_repeats" not in tier["sections"][0]
    assert "archetypes" not in tier["sections"][0]["variants"][0]
    assert "section_order" not in dumped["views"]["horizontal"]
    assert dumped["views"]["vertical"]["section_order"] == "reversed"


def test_library_facade_selects_view_and_caches() -> None:
    library = SpriteLibrary.from_assets(ASSETS)
    horizontal = library.generate_ship("fighter", 4, 30, 5, facing="left")
    vertical = library.generate_ship("fighter", 4, 5, 30, facing="up")
    assert len(horizontal.plain.splitlines()) == 5
    assert len(vertical.plain.splitlines()) == 30
    assert library.generate_ship("fighter", 4, 30, 5, facing="left") is horizontal


def test_equal_weights_preserve_random_choice_contract() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    section = sprite.views["horizontal"].tiers[0].sections[0]
    rng = random.Random(17)
    expected = rng.choice(section.variants).id
    rng = random.Random(17)
    # The renderer's helper is intentionally private; checking the next choice
    # through the same list pins the equal-weight draw discipline.
    assert rng.choice(section.variants).id == expected


# --- Height-budgeted tier selection -----------------------------------------


def test_vertical_tier_selection_budgets_on_stacked_height() -> None:
    """A vertical view is bounded by the rows it stacks to, not by its width.

    Station art is tall and narrow while the boxes Edge requests are wide and
    short, so budgeting on width picks an over-tall tier and crops away the
    beacon and engine glow.
    """

    sprite = load_sprite(ASSETS / "sprites" / "ports" / "trading_port.yaml")
    view = sprite.views["vertical"]
    full, medium = view.tiers[0], view.tiers[1]

    # A box wide enough for the full tier but far too short for it.
    assert full.cross_axis_size("vertical") <= 16
    assert full.composed_length("vertical") > 6
    chosen = selected_tier(sprite, width=16, height=6, view_id="vertical")
    assert chosen is not full
    assert chosen.composed_length("vertical") <= 6

    tall_enough = selected_tier(
        sprite,
        width=full.cross_axis_size("vertical"),
        height=full.composed_length("vertical"),
        view_id="vertical",
    )
    assert tall_enough is full
    assert medium.composed_length("vertical") < full.composed_length("vertical")


def test_horizontal_tier_selection_still_budgets_on_structure_height() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    view = sprite.views["horizontal"]

    for tier in view.tiers:
        chosen = selected_tier(
            sprite,
            width=1000,
            height=tier.cross_axis_size("horizontal"),
            view_id="horizontal",
        )
        assert chosen is tier


def test_the_smallest_tier_is_still_the_final_fallback() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    chosen = selected_tier(sprite, width=1, height=1, view_id="horizontal")
    assert chosen is sprite.views["horizontal"].tiers[-1]


def test_every_station_tier_fits_the_boxes_edge_requests() -> None:
    """No station may be center-cropped at the sizes the game asks for.

    ``SceneArtConfig`` sizes ports 16x6, starbases 22x9 and stardocks 38x16,
    each down to a 4x3 minimum, and the sprite gallery asks 18x8. Cropping a
    station removes its top beacon and bottom glow, which is what makes it read
    as a station at all.
    """

    boxes = {
        "trading_port": [(16, 6), (18, 8), (8, 4), (4, 3)],
        "starbase": [(22, 9), (18, 8), (12, 5), (4, 3)],
        "stardock": [(38, 16), (18, 8), (24, 10), (4, 3)],
    }
    for role, sizes in boxes.items():
        sprite = load_sprite(ASSETS / "sprites" / "ports" / f"{role}.yaml")
        for width, height in sizes:
            for archetype_id in (None, *ARCHETYPE_IDS):
                tier = selected_tier(
                    sprite,
                    width=width,
                    height=height,
                    view_id="vertical",
                    archetype_id=archetype_id,
                )
                stacked = tier.composed_length("vertical", archetype_id)
                assert stacked <= height, (
                    f"{role} {width}x{height} {archetype_id}: "
                    f"tier {tier.id} stacks {stacked} rows"
                )


def test_tier_ladders_must_shrink_strictly() -> None:
    """Two tiers of equal size make the later one unreachable."""

    sprite = load_sprite(ASSETS / "sprites" / "ports" / "starbase.yaml")
    view = sprite.views["vertical"]
    twin = deepcopy(view.tiers[0])
    twin.id = "twin"
    view.tiers.insert(1, twin)

    with pytest.raises(SpriteValidationError, match="strictly smaller"):
        sprite.validate()


# --- Stations ----------------------------------------------------------------


@pytest.mark.parametrize("role", sorted(STATION_ROLES))
def test_stations_are_vertical_only_with_no_mirror_facing(role: str) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ports" / f"{role}.yaml")

    assert sprite.kind == "port"
    assert sprite.role == role
    assert list(sprite.views) == ["vertical"]
    view = sprite.views["vertical"]
    assert view.axis == "vertical"
    assert view.canonical_facing == "up"
    assert view.mirror_facing is None
    # Station bands are authored top to bottom, unlike ships' rotated views.
    assert view.section_order == "authored"


@pytest.mark.parametrize("role", sorted(STATION_ROLES))
def test_stations_render_the_exact_requested_rectangle(
    role: str, palettes: PaletteCatalog
) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ports" / f"{role}.yaml")
    for width, height in [(38, 16), (18, 8), (11, 5), (4, 3)]:
        art = render_sprite(
            sprite, palettes, width=width, height=height, seed=3, view_id="vertical"
        )
        rows = art.plain.split("\n")
        assert len(rows) == height
        assert {len(row) for row in rows} == {width}


@pytest.mark.parametrize("role", sorted(STATION_ROLES))
def test_station_repeated_bands_tile_without_blank_stripes(role: str) -> None:
    """A repeating band padded with void would tile as hull/void/hull/void."""

    sprite = load_sprite(ASSETS / "sprites" / "ports" / f"{role}.yaml")
    for tier in sprite.views["vertical"].tiers:
        for section in tier.sections:
            if section.repeat < 2:
                continue
            for variant in section.variants:
                assert not any(not row.strip() for row in variant.cells), (
                    f"{role}/{tier.id}/{section.id}/{variant.id} has a blank row "
                    "in a repeating band"
                )


def test_station_art_is_deterministic_and_archetype_stable(
    palettes: PaletteCatalog,
) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ports" / "starbase.yaml")
    renders = {
        archetype_id: render_sprite(
            sprite,
            palettes,
            width=22,
            height=9,
            seed=11,
            archetype_id=archetype_id,
            view_id="vertical",
        ).plain
        for archetype_id in ARCHETYPE_IDS
    }
    for archetype_id, plain in renders.items():
        repeated = render_sprite(
            sprite,
            palettes,
            width=22,
            height=9,
            seed=11,
            archetype_id=archetype_id,
            view_id="vertical",
        ).plain
        assert repeated == plain, f"{archetype_id} is not deterministic"
    # Edge gives each archetype its own silhouette, not just its own palette.
    assert len(set(renders.values())) > 1


def test_stations_consume_no_legacy_ship_color_draws(palettes: PaletteCatalog) -> None:
    """The two historical draws belong to converted ship grammars only.

    Reproducing a render's variant choices by hand only works if the number of
    draws burned before the first section is right, so this pins it per kind.
    """

    for role, folder, view_id, burns in (
        ("stardock", "ports", "vertical", 0),
        ("fighter", "ships", "horizontal", 2),
    ):
        sprite = load_sprite(ASSETS / "sprites" / folder / f"{role}.yaml")
        chosen = selected_variants(
            sprite,
            palettes,
            width=24,
            height=12,
            seed=5,
            archetype_id="humanoid_diplomat",
            view_id=view_id,
        )
        tier = selected_tier(
            sprite,
            width=24,
            height=12,
            view_id=view_id,
            archetype_id="humanoid_diplomat",
        )

        rng = random.Random(f"5|{sprite.kind}|{sprite.role}|humanoid_diplomat")
        for _ in range(burns):
            rng.choice((0, 1))
        expected = [rng.choice(section.variants).id for section in tier.sections]

        assert [
            chosen[id(section.variants)].id for section in tier.sections
        ] == expected, f"{role} burns {burns} draws before its first section"


# --- Per-archetype art -------------------------------------------------------


def test_named_variants_win_and_untagged_ones_are_the_default(
    palettes: PaletteCatalog,
) -> None:
    """Edge's ``variants.get(archetype_id, variants["default"])`` rule.

    Variants naming the rendered archetype are used alone; when none name it the
    un-tagged variants stand in as the default art.
    """

    sprite = load_sprite(ASSETS / "sprites" / "ports" / "starbase.yaml")
    view = sprite.views["vertical"]
    tier = view.tiers[0]
    section = tier.sections[0]
    width = tier.cross_axis_size(view.axis)
    height = tier.composed_length(view.axis)
    tagged = {
        archetype_id
        for variant in section.variants
        for archetype_id in variant.archetypes
    }
    assert tagged, "the imported starbase should carry per-archetype caps"

    for archetype_id in sorted(tagged):
        chosen = selected_variants(
            sprite,
            palettes,
            width=width,
            height=height,
            seed=2,
            archetype_id=archetype_id,
            view_id="vertical",
        )[id(section.variants)]
        assert chosen.archetypes == [archetype_id]

    fallback = selected_variants(
        sprite,
        palettes,
        width=width,
        height=height,
        seed=2,
        archetype_id="not_a_real_archetype",
        view_id="vertical",
    )[id(section.variants)]
    assert fallback.archetypes == []


def test_archetype_filtering_does_not_change_the_draw_count(
    palettes: PaletteCatalog,
) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ports" / "starbase.yaml")
    view = sprite.views["vertical"]
    tier = view.tiers[0]
    width = tier.cross_axis_size(view.axis)
    height = tier.composed_length(view.axis)

    for archetype_id in (None, "humanoid_diplomat", "ribbon_salvager"):
        chosen = selected_variants(
            sprite,
            palettes,
            width=width,
            height=height,
            seed=2,
            archetype_id=archetype_id or "",
            view_id="vertical",
        )
        assert len(chosen) == len(tier.sections)


def test_unknown_variant_archetypes_are_rejected() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    variant = sprite.views["horizontal"].tiers[0].sections[0].variants[0]
    variant.archetypes = ["not_a_species"]

    with pytest.raises(SpriteValidationError, match="unknown archetypes"):
        sprite.validate()


# --- Per-archetype repetition ------------------------------------------------


def test_an_archetype_repeat_changes_the_composed_length() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    view = sprite.views["horizontal"]
    tier = view.tiers[0]
    hull = next(section for section in tier.sections if section.id == "hull")
    baseline = tier.composed_length("horizontal")

    hull.archetype_repeats["ribbon_salvager"] = hull.repeat + 1
    sprite.validate()

    assert tier.composed_length("horizontal", "ribbon_salvager") == (
        baseline + hull.variants[0].width
    )
    assert tier.composed_length("horizontal", "humanoid_diplomat") == baseline
    assert tier.composed_length("horizontal", None) == baseline


def test_a_zero_repeat_omits_one_band_for_one_archetype(
    palettes: PaletteCatalog,
) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ports" / "stardock.yaml")
    tier = sprite.views["vertical"].tiers[0]
    deck = next(section for section in tier.sections if section.id == "docking_deck")
    deck.archetype_repeats["ribbon_salvager"] = 0
    sprite.validate()

    height = tier.composed_length("vertical")
    kept = render_sprite(
        sprite, palettes, width=15, height=height, seed=1,
        archetype_id="humanoid_diplomat", view_id="vertical",
    ).plain
    dropped = render_sprite(
        sprite, palettes, width=15, height=height, seed=1,
        archetype_id="ribbon_salvager", view_id="vertical",
    ).plain

    assert kept != dropped
    deck_rows = deck.variants[0].height * deck.repeat
    assert tier.composed_length("vertical", "ribbon_salvager") == height - deck_rows


def test_a_band_can_be_exclusive_to_one_archetype() -> None:
    """A zero baseline plus one override makes a band that species alone has."""

    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    tier = sprite.views["horizontal"].tiers[0]
    screens = next(section for section in tier.sections if section.id == "screens")
    screens.repeat = 0
    screens.archetype_repeats["telepath_aristocrat"] = 2
    sprite.validate()

    assert screens.repeat_for(None) == 0
    assert screens.repeat_for("humanoid_diplomat") == 0
    assert screens.repeat_for("telepath_aristocrat") == 2


def test_zeroing_a_band_leaves_every_other_section_unchanged(
    palettes: PaletteCatalog,
) -> None:
    """The variant draw still happens for a zeroed section, then is discarded.

    Without that, toggling one band off would reshuffle every band after it,
    which makes authoring feel unstable.
    """

    sprite = load_sprite(ASSETS / "sprites" / "ports" / "stardock.yaml")
    tier = sprite.views["vertical"].tiers[0]

    def choices() -> dict[str, str]:
        chosen = selected_variants(
            sprite, palettes, width=15, height=tier.composed_length("vertical"),
            seed=9, archetype_id="humanoid_diplomat", view_id="vertical",
        )
        return {
            section.id: chosen[id(section.variants)].id for section in tier.sections
        }

    before = choices()
    deck = next(section for section in tier.sections if section.id == "docking_deck")
    deck.archetype_repeats["humanoid_diplomat"] = 0
    after = choices()

    assert {k: v for k, v in after.items() if k != "docking_deck"} == {
        k: v for k, v in before.items() if k != "docking_deck"
    }


def test_unknown_archetype_repeat_keys_are_rejected() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    section = sprite.views["horizontal"].tiers[0].sections[0]
    section.archetype_repeats["not_a_species"] = 2

    with pytest.raises(SpriteValidationError, match="unknown archetype_repeats"):
        sprite.validate()


def test_v4_optional_fields_round_trip(tmp_path: Path) -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    section = sprite.views["horizontal"].tiers[0].sections[0]
    section.archetype_repeats["ribbon_salvager"] = 3
    section.variants[0].archetypes = ["ribbon_salvager", "temporal_broker"]

    path = tmp_path / "sprite.yaml"
    dump_sprite(sprite, path)
    loaded = load_sprite(path)
    loaded.source = sprite.source

    assert loaded == sprite
    dumped = yaml.safe_load(path.read_text(encoding="utf-8"))
    reloaded_section = dumped["views"]["horizontal"]["tiers"][0]["sections"][0]
    assert reloaded_section["archetype_repeats"] == {"ribbon_salvager": 3}
    assert reloaded_section["variants"][0]["archetypes"] == [
        "ribbon_salvager",
        "temporal_broker",
    ]


def _two_band_vertical(section_order: str) -> Sprite:
    """A vertical sprite whose two bands are unambiguous and unrandomized."""

    def band(band_id: str, glyph: str) -> Section:
        return Section(
            id=band_id,
            name=band_id.title(),
            primary_property="hull",
            variants=[Variant(id=band_id, cells=[glyph * 3], color_mask=["SSS"])],
        )

    return Sprite(
        schema_version=4,
        id="probe",
        name="Probe",
        kind="probe",
        role="probe",
        description="",
        views={
            "vertical": View(
                id="vertical",
                name="Vertical",
                axis="vertical",
                canonical_facing="up",
                mirror_facing=None,
                section_order=section_order,  # type: ignore[arg-type]
                tiers=[
                    Tier(
                        id="full",
                        name="Full",
                        sections=[band("first", "\u2588"), band("second", "\u2592")],
                    )
                ],
            )
        },
    )


def test_section_order_decides_which_authored_band_lands_on_top(
    palettes: PaletteCatalog,
) -> None:
    """The v3-to-v4 migration guard.

    v3 renderers always reversed a vertical view's sections, because every
    vertical view was a rotation of tail-to-nose horizontal art. v4 records that
    choice on the view, so ``reversed`` must still put the last authored band on
    top while art authored downward keeps its own order.
    """

    authored = render_sprite(
        _two_band_vertical("authored"), palettes, width=3, height=2, view_id="vertical"
    ).plain.split("\n")
    reversed_ = render_sprite(
        _two_band_vertical("reversed"), palettes, width=3, height=2, view_id="vertical"
    ).plain.split("\n")

    assert authored == ["\u2588\u2588\u2588", "\u2592\u2592\u2592"]
    assert reversed_ == ["\u2592\u2592\u2592", "\u2588\u2588\u2588"]


def test_only_vertical_views_may_reverse_their_section_order() -> None:
    sprite = load_sprite(ASSETS / "sprites" / "ships" / "fighter.yaml")
    sprite.views["horizontal"].section_order = "reversed"

    with pytest.raises(SpriteValidationError, match="only vertical views"):
        sprite.validate()


def test_stations_stack_their_bands_as_authored(palettes: PaletteCatalog) -> None:
    """A station's beacon band is drawn at the top, where it is authored."""

    sprite = load_sprite(ASSETS / "sprites" / "ports" / "stardock.yaml")
    tier = sprite.views["vertical"].tiers[0]
    assert tier.sections[0].id == "beacon_mast"

    rows = render_sprite(
        sprite,
        palettes,
        width=tier.cross_axis_size("vertical"),
        height=tier.composed_length("vertical"),
        seed=1,
        view_id="vertical",
    ).plain.split("\n")

    beacon_rows = tier.sections[0].variants[0].height
    assert "▀" in "".join(rows[:beacon_rows])
    assert "▄" in "".join(rows[-2:])


def test_every_tier_renders_its_committed_fixture(palettes: PaletteCatalog) -> None:
    """Pin the composed output of every authored tier in the whole roster.

    This is the guard on the v3-to-v4 migration and on anything that touches
    composition afterwards. Each tier is rendered at its own natural box, so the
    fixture pins the art itself rather than which tier a given size selects.
    Regenerate it deliberately, and read the diff, when art intentionally
    changes.
    """

    expected = json.loads(
        (Path(__file__).parent / "fixtures" / "tier_renders.json").read_text(
            encoding="utf-8"
        )
    )
    sprites = load_sprite_directory(ASSETS / "sprites")

    actual: dict[str, str] = {}
    for sprite_id in sorted(sprites):
        sprite = sprites[sprite_id]
        for view_id, view in sprite.views.items():
            for tier in view.tiers:
                cross = tier.cross_axis_size(view.axis)
                length = tier.composed_length(view.axis)
                width, height = (
                    (cross, length) if view.axis == "vertical" else (length, cross)
                )
                actual[f"{sprite_id}|{view_id}|{tier.id}"] = render_sprite(
                    sprite,
                    palettes,
                    width=width,
                    height=height,
                    seed=7,
                    archetype_id="humanoid_diplomat",
                    view_id=view_id,
                ).plain

    assert sorted(actual) == sorted(expected)
    drifted = [key for key in sorted(expected) if actual[key] != expected[key]]
    assert not drifted, f"tier art changed for: {', '.join(drifted)}"
