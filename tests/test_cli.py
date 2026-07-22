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
    assert "Sectors" in out and "60" in out and "Stardock" in out


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
    assert "Sectors" in out and "Stardock" in out


# --- the --list tables (the inspector's main readout) -------------------------


def _list_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                 *categories: str) -> str:
    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--sectors", "60", "--seed", "2",
                                     "--list", *categories])
    cli.main()
    return capsys.readouterr().out


def _header(out: str) -> str:
    """The table's header row (its `id` cell is right-justified, so its width varies)."""
    return next(line for line in out.splitlines() if "sector(int/sp)" in line)


def test_planet_listing_carries_inhabitants_population_and_holdings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _list_output(monkeypatch, capsys, "planets")
    header = _header(out)
    for column in ("band", "type", "owner", "species", "pop", "cit", "gun", "figs",
                   "treasury", "special", "base", "name"):
        assert column in header, f"the planets table lost its {column!r} column"


def test_listing_columns_stay_aligned_under_a_long_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The old hand-padded table shifted every row whose planet_type overflowed its
    width (`terrestrial_warm` is 16 chars in a 15-wide column). Auto-sizing means a
    column starts at the same offset on every row, header included."""
    out = _list_output(monkeypatch, capsys, "planets")
    lines = out.splitlines()
    header = _header(out)
    start = header.index("owner")
    rows = [line for line in lines[lines.index(header) + 2:] if line.strip()]
    assert rows, "expected at least one planet row"
    for row in rows:
        # Every row's owner cell begins exactly under the header's, whatever precedes it.
        assert row[start - 1] == " " and row[start] != " ", f"column drift: {row!r}"


def test_listings_emit_no_trailing_whitespace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rich pads rows to the table width; the renderer strips that so output diffs
    and greps cleanly."""
    out = _list_output(monkeypatch, capsys, "all")
    assert not [line for line in out.splitlines() if line != line.rstrip()]


def test_every_category_renders(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from edge.bigbang.inspect import LIST_CATEGORIES

    out = _list_output(monkeypatch, capsys, "all")
    for category in LIST_CATEGORIES:
        assert f"{category} (" in out, f"{category} listing missing"


def test_species_listing_carries_the_archetype(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The planet `species` column reads `Name (archetype)`; the species table is where
    that archetype is defined, so it names the column too."""
    out = _list_output(monkeypatch, capsys, "species")
    assert "archetype" in _header(out)


# --- --save: inspect a real game rather than a fresh seed ---------------------


def _small_config():
    """A 90-sector config — the same object the CLI and the save builder must share.

    90 rather than 60 (GW-WP09): `_demo_save` needs at least one unowned, colonizable,
    *uninhabited* world for seed 2 under the test overrides' bigbang parameters — the
    GW-WP09-PRE native-population seeding pass can otherwise leave every unowned
    colonizable world in a 60-sector universe already peopled.
    """
    from edge.config import load_default_config

    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"sector_count": 90})})


def _demo_save(path: Path, config) -> int:
    """A real game: enrol, then claim a world with colonists. Returns the planet id."""
    from edge.core.dev import DevPatch
    from edge.core.planets import colonist_capacity
    from edge.core.rules import Colonize
    from edge.server.service import GameService
    from edge.store.repo import SqliteRepository

    with SqliteRepository(path) as repo:
        service = GameService.new_game(config, seed=2, repo=repo)
        state = service.state
        # Unowned, colonizable, and *uninhabited* (GW-WP09-PRE seeds native peoples onto
        # some unowned worlds too) — this test asserts the exact "50" the player brings,
        # which a native population sharing the world would fold into a larger total.
        target = next(p for p in state.planets.values()
                      if not p.owner.is_owned and colonist_capacity(p, config) > 0
                      and not p.population)
        service.apply(1, DevPatch(op="set", target="ship.colonists", value=50))
        service.apply(1, DevPatch(op="teleport", target="sector", value=target.sector_id))
        service.apply(1, Colonize(planet_id=target.id, colonists=50))
        return target.id


def test_save_lists_state_a_fresh_seed_never_has(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Colonists and player ownership exist only in a played game — which is the whole
    reason --save exists. The universe is rebuilt from the log, so it must show them."""
    config = _small_config()
    monkeypatch.setattr(cli, "load_default_config", lambda: config)
    db = tmp_path / "slot.db"
    planet_id = _demo_save(db, config)

    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--save", str(db), "--list", "planets"])
    cli.main()
    out = capsys.readouterr().out
    assert f"save {db}" in out  # provenance names the save, not a seed
    row = next(line for line in out.splitlines() if line.split()[:1] == [str(planet_id)])
    assert "player:1" in row and "50" in row


def test_save_refuses_generation_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--save inspects an existing universe; honouring --seed/--sectors would be a lie."""
    db = tmp_path / "slot.db"
    db.write_bytes(b"")
    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--save", str(db), "--sectors", "60"])
    with pytest.raises(SystemExit):
        cli.main()


def test_save_reports_a_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--save", str(tmp_path / "nope.db"),
                                     "--list", "planets"])
    with pytest.raises(SystemExit):
        cli.main()


def test_save_from_another_config_epoch_is_refused_before_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A save replays onto a universe regenerated from the *current* config. If the
    config moved, the log lands on the wrong world — caught up front rather than as an
    arbitrary mid-replay rules error."""
    config = _small_config()
    monkeypatch.setattr(cli, "load_default_config", lambda: config)
    db = tmp_path / "slot.db"
    _demo_save(db, config)
    moved = config.model_copy(update={"config_version": config.config_version + 1})
    monkeypatch.setattr(cli, "load_default_config", lambda: moved)

    monkeypatch.setattr("sys.argv", ["edge.bigbang", "--save", str(db), "--list", "planets"])
    with pytest.raises(SystemExit):
        cli.main()
