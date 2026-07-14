"""Species portrait file selection (`edge.art.portrait`, PT-38 / WP-PR2-11).

PT-38 reported that the `_01` variant is never chosen. It is: these pin the selection
contract that claim rested on — numbered-only variant sets are collected (most species ship
no bare `<id>.<ext>` at all), a deterministic `variant` indexes the sorted list from 0, and
the random draw can return the first file. The real cause of "I never see `_01`" is that a
face is pinned per (game seed, species instance), so a *single* instance — the dialogue
play-test harness's one-of-each cast — shows one variant forever; the harness's portrait dial
(WP-PR2-11) is what makes the others reachable.
"""

from __future__ import annotations

import random
from pathlib import Path

from edge.art.portrait import list_portraits, resolve_portrait

SHIPPED_DIR = "images/species"


def _make(dir_path: Path, *names: str) -> None:
    for name in names:
        (dir_path / name).write_bytes(b"")


def test_numbered_only_variants_are_collected_in_sorted_order(tmp_path: Path) -> None:
    _make(tmp_path, "vesk_02.png", "vesk_01.png", "vesk_03.png", "other_01.png", "notes.txt")
    assert [p.name for p in list_portraits("vesk", tmp_path)] == [
        "vesk_01.png", "vesk_02.png", "vesk_03.png"]


def test_a_bare_file_sorts_ahead_of_its_numbered_variants(tmp_path: Path) -> None:
    _make(tmp_path, "vesk.png", "vesk_01.png")
    assert [p.name for p in list_portraits("vesk", tmp_path)] == ["vesk.png", "vesk_01.png"]


def test_deterministic_variant_zero_picks_the_first_file(tmp_path: Path) -> None:
    _make(tmp_path, "vesk_01.png", "vesk_02.png")
    assert resolve_portrait("vesk", tmp_path, 0).name == "vesk_01.png"  # type: ignore[union-attr]
    assert resolve_portrait("vesk", tmp_path, 1).name == "vesk_02.png"  # type: ignore[union-attr]
    # Any stable per-individual key works: the index wraps rather than falling off the end.
    assert resolve_portrait("vesk", tmp_path, 2).name == "vesk_01.png"  # type: ignore[union-attr]


def test_random_draw_reaches_the_first_variant(tmp_path: Path) -> None:
    _make(tmp_path, "vesk_01.png", "vesk_02.png", "vesk_03.png")
    drawn = {resolve_portrait("vesk", tmp_path).name for _ in range(60)}  # type: ignore[union-attr]
    assert "vesk_01.png" in drawn
    assert len(drawn) == 3  # no candidate is excluded from the draw


def test_no_portraits_resolves_to_none(tmp_path: Path) -> None:
    assert list_portraits("vesk", tmp_path) == []
    assert resolve_portrait("vesk", tmp_path) is None


def test_the_shipped_corpus_can_show_its_first_variant() -> None:
    """The `_01` image of a real multi-variant species is reachable (PT-38, on real assets)."""
    terran = list_portraits("terran", SHIPPED_DIR)
    assert len(terran) > 1, "terran is the multi-variant species these guard; it lost its variants"
    assert terran[0].name == "terran_01.png"
    assert resolve_portrait("terran", SHIPPED_DIR, 0) == terran[0]
    # The seeded key the projection uses (`session.contact_view`) reaches index 0 like any other.
    seeded = {random.Random(f"{seed}|portrait|1").randint(0, 2**31) % len(terran)
              for seed in range(50)}
    assert seeded == set(range(len(terran)))
