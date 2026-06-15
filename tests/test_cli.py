"""WP9 — the `python -m edge.bigbang` CLI inspector (DESIGN §5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from edge.bigbang import __main__ as cli


def test_inspect_prints_report(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--inspect", "--sectors", "60", "--seed", "2"])
    cli.main()
    out = capsys.readouterr().out
    assert "sectors=60" in out and "stardock:" in out


def test_render_writes_png(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    png = tmp_path / "u.png"
    monkeypatch.setattr(
        "sys.argv",
        ["edge.bigbang", "--render", str(png), "--sectors", "60", "--seed", "2"],
    )
    cli.main()
    assert png.exists() and png.stat().st_size > 0


def test_default_prints_summary(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--sectors", "60", "--seed", "2"])
    cli.main()
    assert "generated universe" in capsys.readouterr().out
