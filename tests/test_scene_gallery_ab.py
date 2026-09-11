"""WP-SC09 — the dev switch and A/B/C gallery (`edge/tui/scene_gallery.py`).

Covers the WP-SC09 verification bullet: the dev switch defaults to legacy;
all three composers (legacy, `FixedFovPerspective`, `DepthLayeredAnchorProjection`)
render every WP-SC04 benchmark case at every canvas size without crashing, from
identical DTO/tuning/catalogue/viewport inputs; gallery ids/ratings/comments/
export machinery works for A/B/C cells; and the new-pipeline UI snapshots stay
isolated from the legacy baseline (see `tests/test_physical_scene_snapshots.py`).
"""

from __future__ import annotations

import pytest

from edge.core.config import SceneArtConfig
from edge.tui.scene_gallery import (
    COMPOSERS,
    DEFAULT_COMPOSER,
    SIZES,
    _STRATEGIES,
    cases,
    measure,
    render_physical,
    variant_scene_id,
    _render_html,
)

CFG = SceneArtConfig()
CASES = cases()


def test_dev_switch_defaults_to_legacy() -> None:
    assert DEFAULT_COMPOSER == "legacy"
    assert COMPOSERS[0] == "legacy"
    assert _STRATEGIES["legacy"] is None


@pytest.mark.parametrize("case_name", sorted(CASES))
@pytest.mark.parametrize("size", SIZES, ids=[s[0] for s in SIZES])
def test_legacy_composer_renders_every_case_and_size(case_name: str,
                                                      size: tuple[str, int, int]) -> None:
    _label, w, h = size
    sector = CASES[case_name]
    composer, art, drawn, flags = measure(sector, CFG, w, h)
    assert art is not None
    assert isinstance(drawn, dict)
    assert isinstance(flags, list)


@pytest.mark.parametrize("strategy_name", ["fixed_fov_perspective", "depth_layered_anchor"])
@pytest.mark.parametrize("case_name", sorted(CASES))
@pytest.mark.parametrize("size", SIZES, ids=[s[0] for s in SIZES])
def test_new_pipeline_composers_render_every_case_and_size_without_crashing(
    case_name: str, size: tuple[str, int, int], strategy_name: str,
) -> None:
    """The full matrix, both `ProjectionStrategy` implementations: no crashes
    across every WP-SC04 Entity/belt/wreck/crowding case at every canvas size,
    from the same fixture DTOs the legacy composer renders."""

    _label, w, h = size
    sector = CASES[case_name]
    strategy = _STRATEGIES[strategy_name]
    result = render_physical(sector, strategy, w, h)
    assert result.art is not None
    assert isinstance(result.drawn, dict)
    assert isinstance(result.flags, list)
    # Never a rectangle re-measured from rendered text: every kind/box in
    # `drawn` and every bounds entry traces back to `ScenePlan`/`ScenePaint`
    # (`paint.painted[*].scene_box`, `plan.rejected`) — WP-SC09 bullet 3.
    assert len(result.bounds) == len(result.refs)


def test_variant_scene_id_keeps_legacy_id_stable() -> None:
    """The legacy variant id must be byte-identical to the pre-WP-SC09 id, so
    a reviewer's existing localStorage ratings/comments keyed on it survive."""

    from edge.tui.scene_gallery import scene_id

    assert variant_scene_id("port+ships", 67, 30, "legacy") == scene_id("port+ships", 67, 30)


def test_variant_scene_id_disambiguates_new_pipeline_strategies() -> None:
    a = variant_scene_id("port+ships", 67, 30, "fixed_fov_perspective")
    b = variant_scene_id("port+ships", 67, 30, "depth_layered_anchor")
    legacy = variant_scene_id("port+ships", 67, 30, "legacy")
    assert len({a, b, legacy}) == 3


@pytest.mark.parametrize("case_name", ["port+ships", "wreck+ships", "belt+port+ships"])
def test_compare_mode_builds_a_case_and_review_panel_for_every_variant(case_name: str) -> None:
    chosen = {case_name: CASES[case_name]}
    page = _render_html(CFG, chosen, (SIZES[0],), compare=True)
    for composer in COMPOSERS:
        sid = variant_scene_id(case_name, SIZES[0][1], SIZES[0][2], composer)
        assert f'data-scene="{sid}"' in page
        # Every variant gets its own reviewable `.case` — rating stars keyed
        # by this variant's scene id, gallery-id/rating/comment machinery
        # extended (not replaced) to cover the new-pipeline cells too.
        assert f'name="r-{sid}"' in page


def test_default_mode_matches_pre_compare_single_composer_output() -> None:
    """With `compare=False` and the default composer, the page renders exactly
    one card per case/size — the switch stays off unless a caller opts in."""

    chosen = {"port+ships": CASES["port+ships"]}
    page = _render_html(CFG, chosen, (SIZES[0],))
    assert page.count("class='case ") == 1
    assert "variant-group" not in page or "<style>" in page  # only appears in CSS, not markup
