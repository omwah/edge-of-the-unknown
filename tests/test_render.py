"""WP4 — smoke test for the matplotlib graph inspector (DESIGN §5)."""

from __future__ import annotations

from pathlib import Path

from edge.bigbang.generator import generate
from edge.bigbang.render import render_graph
from edge.config import load_default_config


def test_render_writes_a_png(tmp_path: Path) -> None:
    cfg = load_default_config()
    cfg = cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 60})})
    state = generate(cfg, 1)
    out = tmp_path / "universe.png"
    render_graph(state, out, layout_seed=1)
    assert out.exists() and out.stat().st_size > 0
