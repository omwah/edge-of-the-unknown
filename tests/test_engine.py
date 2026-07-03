"""WP7 — the engine cron reducers and tick scheduler (DESIGN §9).

WP16 adds the `alien_drift` cron (alien ships drift between sectors on the clock).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core.aliens import may_occupy
from edge.core.config import GameConfig
from edge.core.models import AlienSpecies, Game, Sector, UniverseState
from edge.engine import cron
from edge.engine.cron import accrue_interest, alien_drift, daily_turn_reset, regenerate_ports
from edge.engine.ticker import EngineTicker
from edge.server.service import GameService
from edge.store.repo import SqliteRepository


def _with_drift(config: GameConfig, chance: float) -> GameConfig:
    """A config copy with the drift move-chance overridden (the cron knob)."""
    return config.model_copy(
        update={"aliens": config.aliens.model_copy(update={"drift_move_chance": chance})})


def _sp(sid: int, sector_id: int, alliance_id: int | None = 2) -> AlienSpecies:
    return AlienSpecies(
        id=sid, roster_id=f"s{sid}", name=f"S{sid}", archetype_id="a", sector_id=sector_id,
        home_band="Frontier", tech_level=5, base_disposition=0.8,
        disposition_center=0.8, disposition_variance=0.05, alliance_id=alliance_id)


def _drift_world() -> UniverseState:
    """1(Core)-2-3-4 chain plus a dead-end sector 5 whose only neighbour is the Core."""
    state = UniverseState.new(Game(1, 99, 1, "t", core_governing_alliance_id=1))
    state.sectors = {
        1: Sector(1, 1, (2, 5), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Frontier"),
        3: Sector(3, 1, (2, 4), "Frontier"),
        4: Sector(4, 1, (3,), "Frontier"),
        5: Sector(5, 1, (1,), "Frontier"),  # only exit is back into the Core
    }
    state.rebuild_adjacency()
    return state

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90})})


def _service(tmp_path: Path) -> GameService:
    return GameService.new_game(_config(), 42, SqliteRepository(tmp_path / "g.db"), created_at=_CREATED)  # type: ignore[arg-type]


def test_daily_turn_reset_refills_and_advances_day(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc._state.players[1] = replace(svc.state.players[1], turns_remaining=3)  # type: ignore[attr-defined]
    day0 = svc.state.game.day_number
    svc.apply_maintenance(daily_turn_reset(svc.state, svc.config))
    assert svc.state.players[1].turns_remaining == 250
    assert svc.state.game.day_number == day0 + 1


def test_interest_grows_only_nonempty_balances(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc._state.players[1] = replace(svc.state.players[1], bank_balance=10_000)  # type: ignore[attr-defined]
    svc.apply_maintenance(accrue_interest(svc.state, svc.config))
    assert svc.state.players[1].bank_balance == 10_050  # 0.5%/day


def test_interest_skips_when_rounding_yields_no_change(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    # A balance of 1 at 0.5%/day rounds back to 1 — no event, no change.
    svc._state.players[1] = replace(svc.state.players[1], bank_balance=1)  # type: ignore[attr-defined]
    result = accrue_interest(svc.state, svc.config)
    assert result.players == () and result.events == ()


def test_regen_moves_stock_toward_desired(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    port = next(iter(svc.state.ports.values()))
    drained = replace(port, commodities=tuple(replace(c, stock=0) for c in port.commodities))
    svc._state.ports[port.id] = drained  # type: ignore[attr-defined]
    svc.apply_maintenance(regenerate_ports(svc.state, svc.config))
    assert all(c.stock > 0 for c in svc.state.ports[port.id].commodities)


def test_cron_cadence_fires_once_per_interval(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    ticker = EngineTicker(svc, tick_seconds=0.0, ticks_per_hour=2, ticks_per_day=5)
    fired_by_tick = [ticker.step() for _ in range(5)]
    # hourly (interval 2) at ticks 2 and 4; the day crons (interval 5) at tick 5.
    assert fired_by_tick[1] == ["hourly_port_economy", "hourly_planet_growth"]  # tick 2
    assert fired_by_tick[3] == ["hourly_port_economy", "hourly_planet_growth"]  # tick 4
    assert fired_by_tick[4] == ["interest_accrual", "daily_turn_reset"]  # tick 5
    assert fired_by_tick[0] == [] and fired_by_tick[2] == []  # no spurious/double fires


async def test_async_run_ticks_then_stops(tmp_path: Path) -> None:
    import asyncio

    svc = _service(tmp_path)
    ticker = EngineTicker(svc, tick_seconds=0.001, ticks_per_hour=2, ticks_per_day=5)
    task = asyncio.create_task(ticker.run())
    await asyncio.sleep(0.05)
    ticker.stop()
    await asyncio.wait_for(task, timeout=1.0)
    assert ticker.tick > 0  # the loop advanced


# --- WP16: alien_drift cron ---


def test_drift_steps_to_a_legal_neighbour_at_full_chance() -> None:
    state = _drift_world()
    state.species = {1: _sp(1, 2)}  # at sector 2; neighbours 1(Core, barred), 3(ok)
    result = alien_drift(state, _with_drift(load_default_config(), 1.0))
    assert len(result.species) == 1
    assert result.species[0].sector_id == 3  # the only legal neighbour
    assert result.game is not None and result.game.drift_seq == 1  # counter advanced


def test_drift_never_moves_at_zero_chance() -> None:
    state = _drift_world()
    state.species = {1: _sp(1, 2)}
    result = alien_drift(state, _with_drift(load_default_config(), 0.0))
    assert result.species == ()
    assert result.game is not None and result.game.drift_seq == 1  # seq still advances


def test_drift_leaves_a_hemmed_in_species_put() -> None:
    state = _drift_world()
    state.species = {1: _sp(1, 5)}  # sector 5's only neighbour is the Core — no legal move
    result = alien_drift(state, _with_drift(load_default_config(), 1.0))
    assert result.species == ()


def test_drift_is_reproducible_from_seed_and_seq() -> None:
    state = _drift_world()
    state.species = {1: _sp(1, 2), 2: _sp(2, 3)}
    cfg = _with_drift(load_default_config(), 0.5)
    r1 = alien_drift(state, cfg)  # pure: does not mutate `state`
    r2 = alien_drift(state, cfg)
    assert {(s.id, s.sector_id) for s in r1.species} == {(s.id, s.sector_id) for s in r2.species}


def test_drift_does_not_consume_the_shared_rng(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    before = svc.state.rng.getstate()
    alien_drift(svc.state, _with_drift(svc.config, 1.0))
    assert svc.state.rng.getstate() == before  # drift uses only its salted sub-RNG


def test_drift_pins_stardock_contacts(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    pinned = cron._pinned_species(svc.state)
    assert pinned  # the generated universe stages contacts at the StarDock
    result = alien_drift(svc.state, _with_drift(svc.config, 1.0))
    assert {s.id for s in result.species}.isdisjoint(pinned)  # staged contacts never wander


@pytest.mark.parametrize("seed", range(8))
def test_drift_never_lands_in_core_or_rival_territory(tmp_path: Path, seed: int) -> None:
    from edge.core.discovery import entity_species

    svc = GameService.new_game(_config(), seed, SqliteRepository(tmp_path / f"d{seed}.db"))  # type: ignore[arg-type]
    cfg = _with_drift(svc.config, 1.0)
    entity = entity_species(svc.state, cfg)
    entity_id = entity.id if entity is not None else None
    for sp in alien_drift(svc.state, cfg).species:
        if sp.id == entity_id:
            # The roaming Entity is unbound by the rival rules — it may sit anywhere non-Core (§7).
            assert not svc.state.sectors[sp.sector_id].is_galactic_core
        else:
            assert may_occupy(svc.state, sp, sp.sector_id, cfg.aliens)


def test_drift_lets_governor_members_into_the_core_but_not_others() -> None:
    """WP18: the governing alliance's members may drift into the Core; others never (WP16).

    Sector 5's only neighbour is the Core (sector 1): a deterministic contrast — the
    governor must step in, a non-governor is hemmed in and stays put.
    """
    state = _drift_world()
    cfg = _with_drift(load_default_config(), 1.0)
    gov = state.game.core_governing_alliance_id

    state.species = {1: _sp(1, 5, alliance_id=gov)}
    assert alien_drift(state, cfg).species[0].sector_id == 1  # the governor enters its capital

    state.species = {1: _sp(1, 5, alliance_id=2)}
    assert alien_drift(state, cfg).species == ()  # a rival/unaligned ship can't — no legal move


def test_entity_drifts_on_its_own_chance(tmp_path: Path) -> None:
    """The Entity moves on `entity_drift_chance` even when ordinary drift is off, and the
    drift is deterministic for a given firing (the drift_seq rail) — §7, WP36."""
    from edge.core.discovery import entity_species

    svc = GameService.new_game(_config(), 7, SqliteRepository(tmp_path / "ent.db"))  # type: ignore[arg-type]
    cfg = svc.config.model_copy(update={"aliens": svc.config.aliens.model_copy(
        update={"drift_move_chance": 0.0, "entity_drift_chance": 1.0})})
    ent = entity_species(svc.state, cfg)
    assert ent is not None
    result = alien_drift(svc.state, cfg)
    moved = {s.id: s.sector_id for s in result.species}
    assert moved.get(ent.id) is not None      # the Entity moved though ordinary drift is 0
    assert set(moved) == {ent.id}             # and it alone
    assert not svc.state.sectors[moved[ent.id]].is_galactic_core  # never into the Core
    # Same firing (drift_seq unchanged until applied) ⇒ identical result — deterministic.
    assert alien_drift(svc.state, cfg).species == result.species
