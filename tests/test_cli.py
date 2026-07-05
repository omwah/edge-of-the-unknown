"""WP9 — the `python -m edge.bigbang` CLI inspector (DESIGN §5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edge.bigbang import __main__ as cli


def test_stats_prints_report(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--stats", "--sectors", "60", "--seed", "2"])
    cli.main()
    out = capsys.readouterr().out
    assert "Sectors" in out and "60" in out and "StarDock" in out


def test_render_web_writes_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "viz"
    monkeypatch.setattr(
        "sys.argv",
        ["edge.bigbang", "--render", str(out), "--sectors", "60", "--seed", "2"],
    )
    cli.main()
    index = out / "index.html"
    data = out / "universe.json"
    assert index.exists() and index.stat().st_size > 0
    assert data.exists() and data.stat().st_size > 0
    # the payload is embedded inline (the token is fully substituted)
    assert '"__UNIVERSE_DATA__"' not in index.read_text(encoding="utf-8")


def test_dump_json_writes_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "u.json"
    monkeypatch.setattr(
        "sys.argv",
        ["edge.bigbang", "--dump-json", str(out), "--sectors", "60", "--seed", "2"],
    )
    cli.main()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["meta"]["sector_count"] == 60
    assert len(payload["sectors"]) == 60
    assert payload["edges"] and payload["hub_sector_ids"]


def test_default_prints_summary(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--sectors", "60", "--seed", "2"])
    cli.main()
    assert "generated universe" in capsys.readouterr().out


def test_no_arguments_prints_stats(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edge.bigbang"])
    cli.main()
    out = capsys.readouterr().out
    assert "Sectors" in out and "StarDock" in out
