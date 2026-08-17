"""The vendored sprite library, loaded once from the asset tree beside it.

Also holds the *fit* seam — the Edge-side rule for turning a caller's available
space into a box the library renders whole. `fit_box` picks the tier, `pad_to`
puts the render back into the caller's layout. Everything Edge knows about the
tier ladder lives here; nothing outside this module should reason about tiers.
"""

from pathlib import Path

from rich.text import Text

from edge.art.sprite_art import Sprite, SpriteLibrary, Tier, View, resolve_archetype

SPRITES = SpriteLibrary.from_assets(Path(__file__).parent / "assets")


def _resolve_view(sprite: Sprite, facing: str | None) -> View:
    """The view the library will render, mirroring `SpriteLibrary._render`."""
    normalized = facing.lower() if facing else None
    if normalized in {"up", "down"} and "vertical" in sprite.views:
        return sprite.views["vertical"]
    if "horizontal" in sprite.views:
        return sprite.views["horizontal"]
    return next(iter(sprite.views.values()))


def _natural_box(view: View, tier: Tier, archetype_id: str | None) -> tuple[int, int]:
    """The (width, height) a tier occupies when nothing is cropped or padded."""
    composed = tier.composed_length(view.axis, archetype_id)
    cross = tier.cross_axis_size(view.axis)
    return (composed, cross) if view.axis == "horizontal" else (cross, composed)


def fit_box(
    entity_type: str,
    subtype: str,
    *,
    max_width: int,
    max_height: int,
    archetype_id: str | None = None,
    facing: str | None = None,
) -> tuple[int, int]:
    """The box to request so the library's tier choice renders uncropped.

    The library selects a tier by the requested **height** alone, then returns
    that tier's natural width — which `render._fit_grid` centre-crops down to
    whatever width the caller asked for. A ship's horizontal ladder runs about
    6:1 (``7x46``, ``5x34``, ``3x17``), so a caller that asks for its own aspect
    (this scene used to ask for ``height * 3``) selects a tier three times wider
    than its box and gets the middle of the hull band back with the prow and
    drive cropped away.

    This resolves the *available* space to the richest tier that fits it on both
    axes and returns that tier's natural box. Requesting that box is
    self-consistent: its height equals the tier's own selection budget, so the
    library's height-based pick lands on exactly the tier chosen here. The
    caller then pads the render into its layout instead of the library cropping
    it.

    The tier ladder is the responsiveness mechanism, so a narrow sky steps a
    ship down from ``medium`` to ``compact`` rather than shaving columns off
    ``medium``.

    Entity types the library does not draw pass their box through untouched. So
    does an unknown subtype: the library resolves those to a per-kind fallback
    sprite at render time, and second-guessing that here would only disagree
    with it.

    Falls back to the smallest tier when nothing fits. That rung may still
    overflow the box, and cropping it is the least-bad option left.
    """
    if entity_type not in ("ship", "port"):
        return max_width, max_height
    sprite = SPRITES.sprites.get(subtype.lower())
    if sprite is None or sprite.kind != entity_type:
        return max_width, max_height
    view = _resolve_view(sprite, facing)
    # `_render` substitutes the fallback archetype for an unset id, and geometry
    # (section repeats, variant availability) follows the resolved one.
    archetype = resolve_archetype(archetype_id or SPRITES.palettes.fallback_archetype)
    for tier in view.tiers:
        box = _natural_box(view, tier, archetype)
        if box[0] <= max_width and box[1] <= max_height:
            return box
    return _natural_box(view, view.tiers[-1], archetype)


def rung_below(
    entity_type: str,
    subtype: str,
    *,
    max_width: int,
    max_height: int,
    steps: int = 1,
    archetype_id: str | None = None,
    facing: str | None = None,
) -> tuple[int, int]:
    """The natural box `steps` rungs *below* the richest tier that fits the space.

    Depth in a scene is carried by the ladder, not by shaving columns. A ship
    further from the viewer must draw a smaller **tier** — prow and drive intact —
    rather than a centre-crop of the tier above, which is all a narrower box would
    buy (see `fit_box`). Callers therefore ask this for a box and request *that*,
    so the library's height-based pick lands on the intended rung.

    `steps=0` is exactly `fit_box`. Steps past the bottom of the ladder clamp to
    the smallest tier, and entities the library does not ladder pass their box
    through untouched — there is no rung to step to.
    """
    if steps <= 0:
        return fit_box(entity_type, subtype, max_width=max_width,
                       max_height=max_height, archetype_id=archetype_id,
                       facing=facing)
    if entity_type not in ("ship", "port"):
        return max_width, max_height
    sprite = SPRITES.sprites.get(subtype.lower())
    if sprite is None or sprite.kind != entity_type:
        return max_width, max_height
    view = _resolve_view(sprite, facing)
    archetype = resolve_archetype(archetype_id or SPRITES.palettes.fallback_archetype)
    boxes = [_natural_box(view, tier, archetype) for tier in view.tiers]
    top = next((i for i, box in enumerate(boxes)
                if box[0] <= max_width and box[1] <= max_height), len(boxes) - 1)
    return boxes[min(top + steps, len(boxes) - 1)]


def pad_to(art: Text, width: int, height: int) -> Text:
    """Centre `art` in a `width` x `height` box of blanks, preserving its styles.

    The other half of `fit_box`: the library renders a tier at its natural size,
    and callers size their layout from the box they asked for. The scene composer
    and the docked headers need the returned `Text` to be exactly that box, and
    the space-battle blitter needs the centring because it maps each inked cell to
    an offset within the station's footprint. The box is exact — the result is
    always `height` rows of `width` cells.
    """
    lines = art.split(allow_blank=True)
    pad_top = max(0, height - len(lines)) // 2
    out = Text()
    for y in range(height):
        if y:
            out.append("\n")
        row = lines[y - pad_top] if 0 <= y - pad_top < len(lines) else Text()
        left = max(0, width - row.cell_len) // 2
        out.append(" " * left)
        out.append_text(row)
        out.append(" " * max(0, width - left - row.cell_len))
    return out
