"""WP6 — the in-process GameService + fog-of-war projections (DESIGN §3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.movement import MovementError, shortest_path
from edge.core.rules import Dock, Trade, Warp
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import state_hash

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90})})


def _service(tmp_path: Path, name: str = "game.db") -> GameService:
    return GameService.new_game(_config(), 42, SqliteRepository(tmp_path / name), created_at=_CREATED)  # type: ignore[arg-type]


def test_new_game_view_starts_at_core(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    view = svc.game_view(1)
    assert view.turns == view.max_turns == 250
    assert view.sector.sector_id == 1
    assert view.ship.holds_total == 60


def test_warp_updates_view_and_reveals_fog(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    target = svc.state.sectors[1].warps_out[0]
    # Before warping, the neighbour is an unexplored '?' warp.
    before = next(w for w in svc.game_view(1).sector.warps if w.sector_id == target)
    assert not before.explored
    svc.apply(1, Warp(to_sector=target))
    view = svc.game_view(1)
    assert view.sector.sector_id == target
    assert view.turns == 249
    assert target in svc.state.players[1].explored_sectors


def test_illegal_warp_persists_nothing(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    with pytest.raises(MovementError):
        svc.apply(1, Warp(to_sector=99999))
    # Turns untouched; command log empty.
    assert svc.game_view(1).turns == 250
    assert svc.state.players[1].turns_remaining == 250


def test_trade_at_stardock_reflected_in_port_view(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    for hop in shortest_path(svc.state.adjacency, 1, dock.sector_id)[1:]:  # type: ignore[index]
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Dock())
    svc.apply(1, Trade(commodity=Commodity.FUEL_ORE, units=5))
    pv = svc.port_view(1, dock.id)
    fuel = next(c for c in pv.commodities if c.name == "Fuel Ore")
    assert fuel.player_qty == 5  # the 5 units we just bought show as held


def test_load_game_reconstructs_identical_state(tmp_path: Path) -> None:
    svc = _service(tmp_path, "persist.db")
    target = svc.state.sectors[1].warps_out[0]
    svc.apply(1, Warp(to_sector=target))
    expected = state_hash(svc.state)

    reloaded = GameService.load_game(_config(), SqliteRepository(tmp_path / "persist.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected


def test_computer_and_map_views_render(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    cv = svc.computer_view(1)
    assert isinstance(cv.pairs, list)  # may be empty until ports are discovered
    mv = svc.map_view(1)
    assert mv.you_sector == 1 and mv.bands


def test_intro_line_names_the_stardock_sector(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    line = svc.intro_line(1)
    assert line is not None and f"Sector {dock.sector_id}" in line


def test_messages_view_signpost_and_real_events(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    # Fresh game: only the derived StarDock signpost is present.
    fresh = svc.messages_view(1)
    assert len(fresh.events) == 1 and "StarDock" in fresh.events[0].text
    # After a warp, the newest event leads and the signpost sinks to the bottom.
    target = svc.state.sectors[1].warps_out[0]
    svc.apply(1, Warp(to_sector=target))
    after = svc.messages_view(1)
    assert f"Sector {target}" in after.events[0].text
    assert "StarDock" in after.events[-1].text
