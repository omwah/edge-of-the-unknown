"""WP-SC10 — `edge/tui/scene_preview.py`'s `--composer` switch.

The dev CLI preview (unlike `scene_gallery.py`) has no existing test coverage; this
just confirms every composer choice renders every hand-built case without crashing,
so the WP-SC10 migration (adapting `scene_preview.py` onto the same
`COMPOSERS`/`render_physical` seam `scene_gallery.py` already uses) is covered by
something other than manual invocation.
"""

from __future__ import annotations

import pytest

from edge.core.config import SceneArtConfig
from edge.tui.scene_gallery import COMPOSERS, _STRATEGIES, render_physical
from edge.tui.scene_preview import _cases
from edge.tui.widgets import _SceneComposer

CASES = _cases()


@pytest.mark.parametrize("composer", COMPOSERS)
@pytest.mark.parametrize("case_name", sorted(CASES))
def test_every_composer_renders_every_preview_case(composer: str, case_name: str) -> None:
    sector = CASES[case_name]
    strategy = _STRATEGIES[composer]
    if strategy is None:
        art = _SceneComposer(sector, SceneArtConfig()).compose(67, 30)
    else:
        art = render_physical(sector, strategy, 67, 30).art
    assert art.plain.strip("\n") != ""
