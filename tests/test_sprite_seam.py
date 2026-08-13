from __future__ import annotations

from types import SimpleNamespace

import pytest

from edge.art.discovery import style_for
from edge.art.generator import (
    available_archetypes,
    available_subtypes,
    generate_sprite,
)
from edge.art.sprite_art import selected_tier
from edge.art.sprites import SPRITES, _natural_box, fit_box
from edge.core.config import SceneArtConfig
from edge.tui import art_adapter


@pytest.mark.parametrize(
    ("kind", "subtype", "width", "height"),
    [
        ("ship", "fighter", 36, 5),
        ("ship", "fighter", 20, 6),
        ("port", "trading_port", 19, 8),
        ("port", "trading_port", 18, 8),
        ("port", "starbase", 22, 9),
        ("port", "stardock", 38, 16),
    ],
)
def test_game_sprite_boxes_are_exact(kind: str, subtype: str, width: int, height: int) -> None:
    sprite = generate_sprite(kind, subtype, 17, width, height)
    lines = sprite.plain.splitlines()
    assert len(lines) == height
    assert all(len(line) == width for line in lines)


def _inked_columns(kind: str, subtype: str, width: int, height: int) -> int:
    """How many columns of the render carry ink, ignoring blank padding."""
    lines = generate_sprite(kind, subtype, 17, width, height).plain.splitlines()
    return len({x for line in lines for x, ch in enumerate(line) if ch != " "})


@pytest.mark.parametrize("kind", ["ship", "port"])
def test_every_subtype_renders_a_whole_tier_at_its_scene_box(kind: str) -> None:
    """The scene's boxes must clear a whole tier, not crop the one above it.

    This is the regression guard for the bug that ships rendered as a one-row
    hull band and ordinary ports as a bare mast: the library picks a tier
    by the requested *height* alone and centre-crops its natural width down to
    the requested width, so a box narrower than the selected tier returns the
    middle of the repeat section with the prow and drive cut away. `fit_box`
    resolves the box to a tier that fits it on both axes; asserting the fitted
    box is no wider than the requested one is what catches a config cap (or a
    synced asset) that clears no rung.
    """
    scene = SceneArtConfig()
    size = scene.ship if kind == "ship" else scene.port
    for subtype in available_subtypes(kind):
        fw, fh = fit_box(kind, subtype, max_width=size.max_width,
                         max_height=size.max_height)
        assert fw <= size.max_width, (
            f"{subtype}: narrowest tier is {fw} wide, scene box allows "
            f"{size.max_width} — the render will be cropped through its repeat band"
        )
        assert fh <= size.max_height, f"{subtype}: shortest tier is {fh} rows"


def test_fitted_box_is_the_tier_the_library_then_selects() -> None:
    """`fit_box` must agree with the library's own height-based tier choice.

    Requesting a tier's natural box has to land back on that tier, or Edge would
    size its layout from one rung and receive another.
    """
    for kind, view_id in (("ship", "horizontal"), ("port", "vertical")):
        for subtype in available_subtypes(kind):
            sprite = SPRITES.sprites[subtype]
            for expected in sprite.views[view_id].tiers:
                box = _natural_box(sprite.views[view_id], expected,
                                   SPRITES.palettes.fallback_archetype)
                tier = selected_tier(
                    sprite, width=box[0], height=box[1], view_id=view_id,
                    archetype_id=SPRITES.palettes.fallback_archetype)
                assert tier is expected, (
                    f"{subtype}: asking for {expected.id}'s natural box {box} "
                    f"selected {tier.id} instead"
                )


def test_a_narrow_sky_steps_a_ship_down_a_tier_rather_than_cropping_it() -> None:
    """Tiers are the responsiveness mechanism — the art shrinks by rung."""
    wide = fit_box("ship", "warship", max_width=200, max_height=200)
    narrow = fit_box("ship", "warship", max_width=20, max_height=5)
    assert narrow[0] < wide[0] and narrow[1] < wide[1]
    # The stepped-down rung is drawn whole and centred, so it leaves the box's
    # spare columns blank. A cropped tier would ink every column edge to edge —
    # that full-bleed band is exactly what the bug looked like.
    assert _inked_columns("ship", "warship", 20, 5) == narrow[0] < 20


def test_ordinary_port_renders_its_silhouette_not_its_mast() -> None:
    """`trading_port`'s 6-row rung is a 7-wide mast; the scene must clear 7 rows."""
    scene = SceneArtConfig()
    fw, fh = fit_box("port", "trading_port", max_width=scene.port.max_width,
                     max_height=scene.port.max_height)
    assert (fw, fh) == (11, 7)


def test_sprite_generation_is_deterministic_in_text_and_styles() -> None:
    args = ("ship", "warship", 29, 20, 6, "canid_technologist")
    first = generate_sprite(*args)
    second = generate_sprite(*args)
    assert first.plain == second.plain
    assert first.spans == second.spans


def test_ship_facing_changes_the_rendered_sprite() -> None:
    right = generate_sprite("ship", "fighter", 41, 20, 6, facing="right")
    left = generate_sprite("ship", "fighter", 41, 20, 6, facing="left")
    assert left.plain != right.plain


def test_every_vendored_sprite_has_coverage_at_a_game_box() -> None:
    for subtype in available_subtypes("ship"):
        assert generate_sprite("ship", subtype, 7, 36, 5).plain.strip(), subtype
    for subtype in available_subtypes("port"):
        assert generate_sprite("port", subtype, 16, 19, 8).plain.strip(), subtype


def test_discovery_palette_resolution_uses_catalog_fallback() -> None:
    for archetype in available_archetypes():
        assert style_for(archetype) == style_for(archetype)
    assert style_for("not-a-real-archetype") == style_for("humanoid_diplomat")


def test_configured_art_subtype_overrides_role_routing() -> None:
    synthetic = SimpleNamespace(role="fighter", art_subtype="needle_picket")
    routed = art_adapter.ship_entity(synthetic.role, synthetic.art_subtype)
    role_routed = art_adapter.ship_entity(synthetic.role)
    assert routed == ("ship", "needle_picket")
    assert routed != role_routed
    assert art_adapter.sprite(*routed, seed=3, width=16, height=5).plain != (
        art_adapter.sprite(*role_routed, seed=3, width=16, height=5).plain
    )
