"""GW-WP13 — structural performance budgets for ground operations.

Wall-clock assertions flake under CI load and drift as hardware changes, so — like
the state-checkpoint work this module extends (`perf: bound save loading with state
checkpoints`) — every budget here is *structural*: a bounded amount of replay work
or a bounded response size, never a timer. Two concerns from the WP13 plan text:

- **Reload time**: a live ground operation (`SurveyOperation`/`AssaultOperation`,
  hashed on `Player.ground_operation`) must round-trip through the same checkpoint
  codec every other authoritative field does, and a reload after a checkpoint must
  replay only the log tail written *after* it — not regenerate the whole game and
  replay every ground command ever issued, which is exactly the cost the
  checkpoint mechanism exists to bound.
- **DTO viewport projection**: `ground_operation_view` must stay a *crop*, not a
  dump — the cell count returned is bounded by the requested viewport, never by
  the underlying map's full `width * height`, regardless of how large the
  generated battlefield/survey grid is.
"""

from __future__ import annotations

from pathlib import Path

from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.dto import AssaultExpeditionDTO, SurveyExpeditionDTO
from edge.core.enums import PortClass
from edge.core.groundwar.access import Assault, Survey, ground_access
from edge.core.groundwar.assault import assault_map_for
from edge.core.groundwar.models import AssaultOperation
from edge.core.rules import (
    BeginAssault, BeginSurvey, BuySuits, DevPatch, Dock, GroundDrop, HireRecruits,
)
from edge.server.service import GameService
from edge.store.repo import RecordedCommand, RecordedMaintenance, SqliteRepository
from edge.store.snapshots import state_hash

_CREATED = "2026-07-23T00:00:00Z"
_SEED = 11


def _config() -> GameConfig:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"sector_count": 400, "start_sector": 1})})


class _TrackingRepository(SqliteRepository):
    """`SqliteRepository` that records which log-tail cursor a reload asked for —
    the same instrumentation `test_store.py`'s checkpoint tests use to prove a
    reload replays only what's after the checkpoint, not the whole history."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.command_cursors: list[int] = []

    def load_commands_after(self, seq: int) -> list[RecordedCommand]:
        self.command_cursors.append(seq)
        return super().load_commands_after(seq)

    def load_maintenance_after(self, seq: int) -> list[RecordedMaintenance]:
        return super().load_maintenance_after(seq)


def _begin_survey(svc: GameService) -> None:
    state = svc.state
    player = state.players[1]
    planet = next(
        p for p in state.planets.values()
        if isinstance(ground_access(state, player, p, svc.config), Survey))
    svc.apply(1, DevPatch("teleport", "", value=planet.sector_id))
    svc.apply(1, BeginSurvey(planet.id))


def test_reload_with_a_live_survey_replays_only_the_log_tail(tmp_path: Path) -> None:
    path = tmp_path / "survey-tail.db"
    svc = GameService.new_game(_config(), _SEED, SqliteRepository(path), created_at=_CREATED)
    _begin_survey(svc)
    svc.checkpoint()
    checkpoint_seq = svc._repo.load_checkpoint().command_seq  # type: ignore[union-attr]
    # A few more commands after the checkpoint — these, and only these, should replay.
    for _ in range(3):
        svc.apply(1, DevPatch("set", "latinum", svc.state.players[1].latinum + 1))
    expected = state_hash(svc.state)

    tracking = _TrackingRepository(path)
    loaded = GameService.load_game(_config(), tracking)  # type: ignore[arg-type]

    assert state_hash(loaded.state) == expected  # the live SurveyOperation round-tripped
    assert tracking.command_cursors == [checkpoint_seq]  # not a full-history replay


def test_reload_with_a_live_assault_replays_only_the_log_tail(tmp_path: Path) -> None:
    path = tmp_path / "assault-tail.db"
    svc = GameService.new_game(_config(), _SEED, SqliteRepository(path), created_at=_CREATED)
    svc.apply(1, DevPatch("set", "latinum", 200_000))
    state = svc.state
    stardock = next(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    svc.apply(1, DevPatch("teleport", "", value=stardock))
    svc.apply(1, Dock())
    assert svc.config.groundwar is not None
    suit_id = next(iter(svc.config.groundwar.suits))
    svc.apply(1, BuySuits(suit_id=suit_id, count=1))
    svc.apply(1, HireRecruits(count=1))

    player = svc.state.players[1]
    target = next(
        p for p in svc.state.planets.values()
        if isinstance(access := ground_access(svc.state, player, p, svc.config), Assault)
        and access.droppable)
    svc.apply(1, DevPatch("teleport", "", value=target.sector_id))
    svc.apply(1, BeginAssault(target.id))
    op = svc.state.players[1].ground_operation
    assert isinstance(op, AssaultOperation)
    amap = assault_map_for(svc.state, op, svc.config)
    svc.apply(1, GroundDrop(op.operation_id, ((suit_id, amap.landing_x, amap.landing_y),)))

    svc.checkpoint()
    checkpoint_seq = svc._repo.load_checkpoint().command_seq  # type: ignore[union-attr]
    expected = state_hash(svc.state)

    tracking = _TrackingRepository(path)
    loaded = GameService.load_game(_config(), tracking)  # type: ignore[arg-type]

    assert state_hash(loaded.state) == expected
    assert tracking.command_cursors == [checkpoint_seq]


def test_survey_viewport_projection_is_cropped_not_dumped(tmp_path: Path) -> None:
    svc = GameService.new_game(
        _config(), _SEED, SqliteRepository(tmp_path / "survey-viewport.db"), created_at=_CREATED)
    _begin_survey(svc)
    width, height = 5, 4
    dto = svc.ground_operation_view(1, viewport_width=width, viewport_height=height)
    assert isinstance(dto, SurveyExpeditionDTO)
    assert dto.map_width * dto.map_height > width * height  # the underlying map is larger
    assert len(dto.cells) <= width * height  # the response is a crop, not the whole map


def test_assault_viewport_projection_is_cropped_not_dumped(tmp_path: Path) -> None:
    svc = GameService.new_game(
        _config(), _SEED, SqliteRepository(tmp_path / "assault-viewport.db"), created_at=_CREATED)
    state = svc.state
    player = state.players[1]
    target = next(
        p for p in state.planets.values()
        if isinstance(access := ground_access(state, player, p, svc.config), Assault)
        and access.droppable)
    svc.apply(1, DevPatch("teleport", "", value=target.sector_id))
    svc.apply(1, BeginAssault(target.id))
    width, height = 5, 4
    dto = svc.ground_operation_view(1, viewport_width=width, viewport_height=height)
    assert isinstance(dto, AssaultExpeditionDTO)
    assert dto.map_width * dto.map_height > width * height
    assert len(dto.cells) <= width * height
