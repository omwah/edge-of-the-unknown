"""WP6 — the in-process GameService + fog-of-war projections (DESIGN §3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.movement import MovementError, shortest_path
from edge.core.rules import Dock, JoinGame, Trade, Warp
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import state_hash

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})})


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
    # Pick a neighbour off the pre-explored Stardock route so it's still fogged.
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


def test_haggle_quote_labels_track_generosity(tmp_path: Path) -> None:
    """The advisory haggle hint reads accepted / insulting / (un)likely for a buy."""
    svc = _service(tmp_path)
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    for hop in shortest_path(svc.state.adjacency, 1, dock.sector_id)[1:]:  # type: ignore[index]
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Dock())
    fair = next(c for c in svc.port_view(1, dock.id).commodities if c.name == "Fuel Ore").price

    # Fuel Ore at a Stardock is a player buy: paying fair (or more) is auto-accepted,
    # paying a pittance is insulting, and a mild discount is a real negotiation.
    assert svc.haggle_quote(1, Commodity.FUEL_ORE, fair).label == "accepted"
    assert svc.haggle_quote(1, Commodity.FUEL_ORE, 1).label == "insulting"
    mild = fair - max(1, round(fair * 0.1))  # ~10% under fair, within the insult band
    assert svc.haggle_quote(1, Commodity.FUEL_ORE, mild).label in {"likely", "unlikely"}


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


def test_second_player_joins_same_universe_and_survives_reload(tmp_path: Path) -> None:
    """Enrolment is a recorded `JoinGame` (not seeded by the big bang), so a second
    player joins the *same* universe by appending the command and is rebuilt on load —
    the multiplayer seam (§3, §14 Phase 4)."""
    svc = _service(tmp_path, "mp.db")
    assert set(svc.state.players) == {1}  # only player 1 enrolled by new_game

    svc.apply(2, JoinGame(name="Pathfinder"))
    p2 = svc.state.players[2]
    assert p2.name == "Pathfinder" and p2.alliance_id == svc.state.game.core_governing_alliance_id
    # Distinct hull, owned by player 2 — no clash with player 1's ship.
    assert p2.ship_id != svc.state.players[1].ship_id
    assert svc.state.ships[p2.ship_id].owner_player_id == 2
    expected = state_hash(svc.state)

    # Both joins live in the command log, so reload reconstructs both players.
    reloaded = GameService.load_game(_config(), SqliteRepository(tmp_path / "mp.db"))  # type: ignore[arg-type]
    assert set(reloaded.state.players) == {1, 2}
    assert state_hash(reloaded.state) == expected


def test_double_join_same_id_rejected(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    with pytest.raises(MovementError):
        svc.apply(1, JoinGame())  # player 1 already enrolled by new_game


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


def _drift_config() -> object:
    """Config that drifts aliens fast and surely (small cadence, certain move)."""
    cfg = load_default_config()
    return cfg.model_copy(update={
        "bigbang": cfg.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1}),
        "aliens": cfg.aliens.model_copy(update={"drift_move_chance": 1.0}),
        "ticker": cfg.ticker.model_copy(update={
            "crons": cfg.ticker.crons.model_copy(update={"alien_drift": 2})}),
    })


def test_load_game_replays_alien_drift(tmp_path: Path) -> None:
    """WP16: ticking fires `alien_drift`; species positions reconstruct on reload.

    Drift is a pure function of `(seed, drift_seq)` and never touches the shared RNG,
    so the maintenance timeline replays movement exactly — same positions, same hash.
    """
    from edge.engine.ticker import EngineTicker

    cfg = _drift_config()
    svc = GameService.new_game(cfg, 42, SqliteRepository(tmp_path / "drift.db"), created_at=_CREATED)  # type: ignore[arg-type]
    ticker = EngineTicker(svc, tick_seconds=0.0, ticks_per_hour=100, ticks_per_day=1000)
    for _ in range(7):  # drift cadence 2 → fires at ticks 2/4/6
        ticker.step()
    expected = state_hash(svc.state)
    positions = {sid: sp.sector_id for sid, sp in svc.state.species.items()}
    assert svc.state.game.drift_seq == 3  # drift actually fired three times

    reloaded = GameService.load_game(cfg, SqliteRepository(tmp_path / "drift.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected
    assert {sid: sp.sector_id for sid, sp in reloaded.state.species.items()} == positions


def test_discovery_collection_replays_into_identical_state(tmp_path: Path) -> None:
    """WP5: warping to + salvaging a discovery survives a reload (Player.codex golden master).

    Everything flows through the command log — warp and salvage — so replay
    reproduces the codex exactly; no direct state pokes. Visibility is recomputed
    live from sensors, so the salvage's gate is deterministic on replay too.
    """
    from edge.core.rules import Salvage, Warp

    svc = _service(tmp_path, "codex.db")
    sensor = svc.state.ships[1].sensor_rating
    diff = svc.config.discovery.sensor_difficulty  # type: ignore[union-attr]
    # Nearest open-space find the starter sensors can see on arrival (obvious or low-tier).
    candidates = []
    for d in svc.state.discoveries.values():
        if d.planet_id is not None:
            continue
        path = shortest_path(svc.state.adjacency, 1, d.sector_id)
        if path is None:
            continue
        # Obvious finds need no detection; a hidden one must be detectable AND reached
        # via a real warp (≥1 hop) so on-entry detection actually fires before salvage.
        if not d.hidden:
            candidates.append((len(path), path, d))
        elif sensor >= diff[d.rarity_tier.name] and len(path) >= 2:
            candidates.append((len(path), path, d))
    candidates.sort(key=lambda t: t[0])
    _, path, disc = candidates[0]
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Salvage(discovery_id=disc.id))
    assert disc.id in svc.state.players[1].codex
    expected = state_hash(svc.state)

    reloaded = GameService.load_game(_config(), SqliteRepository(tmp_path / "codex.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected
    assert disc.id in reloaded.state.players[1].codex


def test_genesis_deploy_replays_into_identical_state(tmp_path: Path) -> None:
    """WP10: buy + deploy a genesis torpedo survives a reload (planet retype golden master).

    Everything flows through the command log (warp → buy → warp → deploy) so replay
    reproduces the retype exactly. A cheap-genesis config keeps it inside starting
    capital — no direct state pokes that would diverge on reload.
    """
    from edge.core.enums import PortClass
    from edge.core.rules import BuyGenesis, DeployGenesis

    cfg = _config()
    cfg = cfg.model_copy(update={"genesis": cfg.genesis.model_copy(update={"price": 1_000})})  # type: ignore[union-attr]
    db = tmp_path / "genesis.db"
    svc = GameService.new_game(cfg, 42, SqliteRepository(db), created_at=_CREATED)  # type: ignore[arg-type]
    dock = next(p for p in svc.state.ports.values() if p.klass is PortClass.STARDOCK)
    for hop in shortest_path(svc.state.adjacency, 1, dock.sector_id)[1:]:  # type: ignore[index]
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, BuyGenesis())
    target = next(
        pl for pl in svc.state.planets.values()
        if not pl.owner.is_owned and pl.planet_type in cfg.genesis.eligible_types  # type: ignore[union-attr]
        and shortest_path(svc.state.adjacency, dock.sector_id, pl.sector_id) is not None
    )
    for hop in shortest_path(svc.state.adjacency, dock.sector_id, target.sector_id)[1:]:  # type: ignore[index]
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, DeployGenesis(planet_id=target.id))
    assert svc.state.planets[target.id].planet_type == cfg.genesis.result_type  # type: ignore[union-attr]
    expected = state_hash(svc.state)

    reloaded = GameService.load_game(cfg, SqliteRepository(db))  # type: ignore[arg-type]
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
    assert mv.you_sector == 1 and mv.rows and mv.legend


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


def test_messages_view_lists_real_events(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    # Fresh game: no events yet (the opening Stardock beacon was removed).
    assert svc.messages_view(1).events == []
    # After a warp, the newest event leads, its destination in the spatial-sector gutter.
    target = svc.state.sectors[1].warps_out[0]
    svc.apply(1, Warp(to_sector=target))
    after = svc.messages_view(1)
    assert f"S{svc.state.spatial_ids[target]}" in after.events[0].text


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
    events = svc.apply(1, Warp(to_sector=target))  # may also detect a discovery on entry
    # The spatial id rides in the sector gutter the ticker prepends to each event.
    assert any(f"S{svc.state.spatial_ids[target]}" in svc.describe_event(e) for e in events)


def test_gameservice_conforms_to_protocol(tmp_path: Path) -> None:
    """The service satisfies the H16 seam every consumer programs against (WP60)."""
    from edge.server.protocol import ServiceProtocol
    assert isinstance(_service(tmp_path), ServiceProtocol)
