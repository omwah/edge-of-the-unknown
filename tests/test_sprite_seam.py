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
from edge.core.config import PlanetSpriteSize, SceneArtConfig, SpriteSize
from edge.tui import art_adapter


@pytest.mark.parametrize(
    ("kind", "subtype", "width", "height"),
    [
        ("ship", "fighter", 46, 7),
        ("ship", "fighter", 20, 6),
        ("port", "trading_port", 28, 12),
        ("port", "trading_port", 18, 8),
        ("port", "starbase", 33, 14),
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
    """`trading_port`'s 6-row rung is a 7-wide mast; the scene must clear its top."""
    scene = SceneArtConfig()
    fw, fh = fit_box("port", "trading_port", max_width=scene.port.max_width,
                     max_height=scene.port.max_height)
    assert (fw, fh) == (11, 12)


@pytest.mark.parametrize(
    ("kind", "subtype", "top_rung"),
    [
        ("port", "trading_port", (11, 12)),
        ("port", "starbase", (11, 14)),
        ("port", "stardock", (15, 15)),
        ("ship", "warship", (46, 7)),
    ],
)
def test_shipped_caps_reach_each_kinds_top_rung(
    kind: str, subtype: str, top_rung: tuple[int, int]
) -> None:
    """The scene must be able to draw the richest art the library holds.

    The regression this guards is the *other* direction from the mast bug: caps
    low enough to clear a rung but never the best one, so the sprite looks
    correct while the top of every ladder stays unreachable at any terminal
    size. It shipped once — `port` at 19x8 and `ship` at 36x5 pinned an ordinary
    port to its 11x7 rung and a warship to 36x5 on a 100-row console, because
    both the caps and `planet.max_height` saturated around 40 rows.

    Each kind is checked against its own configured bounds, which is what the
    Sector composer and the docked headers actually resolve through.
    """
    scene = SceneArtConfig()
    size = scene.ship if kind == "ship" else scene.station_size(
        "stardock" if subtype == "stardock" else
        "starbase" if subtype == "starbase" else "port")
    assert fit_box(kind, subtype, max_width=size.max_width,
                   max_height=size.max_height) == top_rung


def test_the_scale_chain_reaches_those_caps_at_a_full_size_planet() -> None:
    """A cap is only reachable if the *scale* off the planet gets there too.

    `planet.max_height` is the single reference every other kind derives from, so
    a generous cap with a small planet still freezes the scene. This pins the two
    halves together: at a full-size planet each kind must resolve to a box that
    clears its top rung.
    """
    scene = SceneArtConfig()
    primary = scene.planet.max_height
    for kind, subtype, top_rung in (
        ("port", "trading_port", (11, 12)),
        ("starbase", "starbase", (11, 14)),
        ("stardock", "stardock", (15, 15)),
    ):
        w, h = scene.station_dimensions(kind, primary_height=primary,
                                        body_height=primary)
        assert fit_box("port", subtype, max_width=w, max_height=h) == top_rung, (
            f"{subtype}: scale chain resolves {w}x{h} at a {primary}-row planet, "
            f"which does not clear its {top_rung} top rung"
        )
    ship_h = min(scene.ship.max_height, round(primary * scene.ship_scale))
    assert fit_box("ship", "warship", max_width=scene.ship.max_width,
                   max_height=ship_h) == (46, 7)


def _scene_chain(scene: SceneArtConfig, w: int, h: int) -> tuple[int, tuple[int, int]]:
    """Primary height and ship rung for a `w`x`h` scene, without a running app.

    Calls the composer's own `primary_body_height`, so the sweep below cannot pass
    against a stale copy of the sizing rule. Only `_paint_ships`' two lines (sky
    width off the primary's left edge, height off `ship_scale`) are restated here.
    """
    from edge.tui.widgets import _PRIMARY_CENTRE, primary_body_height

    body_h = h - 5  # header rows + the blank under them, as `compose` computes it
    ph = primary_body_height(scene, w, body_h)
    sky = max(2, int(w * _PRIMARY_CENTRE) - ph) - 2
    sh = max(scene.ship.min_height, min(scene.ship.max_height,
                                        round(ph * scene.ship_scale)))
    sw = max(scene.ship.min_width, min(scene.ship.max_width, sky - 4))
    return ph, fit_box("ship", "warship", max_width=sw, max_height=sh)


def test_the_scene_keeps_growing_past_the_tier_where_it_used_to_saturate() -> None:
    """A bigger console must draw bigger art — the whole point of the retune.

    The shipped bug was that every sprite stopped growing around a 40-row terminal,
    so a 100-row console rendered the same scene as a 40-row one. Growth is checked
    on the planet (which governs the chain) and on the ship rung (the object the
    saturation was most visible on).
    """
    scene = SceneArtConfig()
    small_planet, small_ship = _scene_chain(scene, 87, 36)
    large_planet, large_ship = _scene_chain(scene, 190, 60)
    assert large_planet > small_planet
    assert large_ship[0] > small_ship[0]
    # And the largest viewport must reach the top of both ladders, not merely grow.
    assert large_planet == scene.planet.max_height
    assert large_ship == (46, 7)


def test_a_growing_planet_never_starves_the_sky_below_a_whole_ship_rung() -> None:
    """The disc and the traffic share one width budget (§3).

    Raising `planet.max_height` widens the disc by two columns per row, out of the
    same sky ships are placed in. Without `_SHIP_SKY_RESERVE` that pushed traffic
    *below* its pre-retune rung on mid-width consoles — the scene grew a bigger
    planet by making the ships smaller than they had been. Swept broadly because
    the failure was a band of widths, not a single size.
    """
    scene = SceneArtConfig()
    baseline = SceneArtConfig(planet=PlanetSpriteSize(min_height=4, max_height=26),
                              ship=SpriteSize(min_width=6, min_height=3,
                                              max_width=36, max_height=5))
    for h in (30, 36, 40, 44, 48, 52, 58):
        for w in range(60, 210, 2):
            _, was = _scene_chain(baseline, w, h)
            planet, now = _scene_chain(scene, w, h)
            assert now[0] >= was[0], (
                f"{w}x{h}: ship rung fell from {was} to {now} — a bigger planet "
                f"({planet} rows) starved the sky it rides in"
            )


def test_the_sky_reserve_is_skipped_when_it_would_buy_nothing() -> None:
    """The reserve trades planet rows for a ship rung; it must not trade for free.

    Ship *height* scales off the planet too, so trimming the disc to widen the sky
    also shrinks the ship meant to fill it. On a small scene the trim therefore buys
    a 36-column berth for a ship only tall enough to draw the 17-column rung — pure
    loss, and the gate must decline it.
    """
    scene = SceneArtConfig()
    planet, rung = _scene_chain(scene, 98, 30)
    assert rung[0] == 17           # too short for the 36-wide rung either way
    assert planet == 22            # so the disc keeps every row it had


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
