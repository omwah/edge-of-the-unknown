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
    # Pick a neighbour off the pre-explored StarDock route so it's still fogged.
    explored = svc.state.players[1].explored_sectors
    target = next(s for s in svc.state.sectors[1].warps_out if s not in explored)
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


def test_load_game_replays_maintenance_ticks(tmp_path: Path) -> None:
    """WP12: a session that ticks (interest/regen/growth/reset) reloads identically.

    The prior test reloads *before* any cron fires; this one ticks between commands,
    so it only passes if the maintenance timeline is durable and replayed in order.
    """
    from edge.core.rules import Deposit
    from edge.engine.ticker import EngineTicker

    svc = _service(tmp_path, "ticked.db")
    svc.apply(1, Deposit(amount=1_000))  # a balance for interest to grow
    target = svc.state.sectors[1].warps_out[0]
    svc.apply(1, Warp(to_sector=target))
    ticker = EngineTicker(svc, tick_seconds=0.0, ticks_per_hour=2, ticks_per_day=5)
    for _ in range(7):  # fire port regen, planet growth, interest, daily reset
        ticker.step()
    svc.apply(1, Deposit(amount=200))  # a command *after* the ticks — ordering matters
    expected = state_hash(svc.state)
    assert svc.state.game.day_number == 2  # the daily reset actually fired

    reloaded = GameService.load_game(_config(), SqliteRepository(tmp_path / "ticked.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected


def test_ticker_schedule_survives_reload(tmp_path: Path) -> None:
    """WP12: a reloaded ticker resumes its tick counter and next-due schedule."""
    from edge.engine.ticker import EngineTicker

    svc = _service(tmp_path, "sched.db")
    ticker = EngineTicker(svc, tick_seconds=0.0, ticks_per_hour=2, ticks_per_day=5)
    for _ in range(3):
        ticker.step()
    assert ticker.tick == 3

    reloaded = GameService.load_game(_config(), SqliteRepository(tmp_path / "sched.db"))  # type: ignore[arg-type]
    resumed = EngineTicker(reloaded, tick_seconds=0.0, ticks_per_hour=2, ticks_per_day=5)
    assert resumed.tick == 3  # tick counter restored
    # The hourly crons fired at tick 2; the next is due at 4 — resuming must not refire 2.
    fired = resumed.step()  # advances to tick 4
    assert resumed.tick == 4 and "hourly_port_economy" in fired


def test_computer_and_map_views_render(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    cv = svc.computer_view(1)
    assert isinstance(cv.pairs, list)  # may be empty until ports are discovered
    mv = svc.map_view(1)
    assert mv.you_sector == 1 and mv.bands


def test_current_planet_view_finds_or_none(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    # Move the ship to a sector that has a planet, then to one that doesn't.
    planet = next(iter(svc.state.planets.values()))
    from dataclasses import replace
    svc._state.ships[1] = replace(svc.state.ships[1], sector_id=planet.sector_id)  # type: ignore[attr-defined]
    view = svc.current_planet_view(1)
    assert view is not None and view.planet_id == planet.id
    empty = next(s for s in svc.state.sectors if not any(
        p.sector_id == s for p in svc.state.planets.values()))
    svc._state.ships[1] = replace(svc.state.ships[1], sector_id=empty)  # type: ignore[attr-defined]
    assert svc.current_planet_view(1) is None


def test_intro_line_names_the_stardock_sector(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    line = svc.intro_line(1)
    # The signpost names the StarDock's *spatial* display id (§5.1), not the internal id.
    assert line is not None and f"Sector {svc.state.spatial_ids[dock.sector_id]}" in line


def test_messages_view_signpost_and_real_events(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    # Fresh game: only the derived StarDock signpost is present.
    fresh = svc.messages_view(1)
    assert len(fresh.events) == 1 and "StarDock" in fresh.events[0].text
    # After a warp, the newest event leads (with the spatial id) and the signpost sinks.
    target = svc.state.sectors[1].warps_out[0]
    svc.apply(1, Warp(to_sector=target))
    after = svc.messages_view(1)
    assert f"Sector {svc.state.spatial_ids[target]}" in after.events[0].text
    assert "StarDock" in after.events[-1].text


def test_resolve_display_id_round_trips(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    # A typed spatial id maps back to its internal sector id (§5.1, the travel prompt).
    for internal, spatial in svc.state.spatial_ids.items():
        assert svc.resolve_display_id(spatial) == internal
    # An id that names no sector is rejected.
    assert svc.resolve_display_id(999_999) is None


def test_resolve_display_id_identity_without_spatial_ids(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc.state.spatial_ids = {}  # a state that never ran the numbering pass
    assert svc.resolve_display_id(42) == 42  # falls back to the internal id


def test_describe_event_uses_spatial_id(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    target = svc.state.sectors[1].warps_out[0]
    (event,) = svc.apply(1, Warp(to_sector=target))
    assert f"Sector {svc.state.spatial_ids[target]}" in svc.describe_event(event)
