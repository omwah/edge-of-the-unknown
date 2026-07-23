"""GW-WP12 — fog-safe assault DTO, client parity, and live Textual flow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from edge.core.dto import AssaultExpeditionDTO
from edge.core.groundwar import assault as ga
from edge.core.models import Region
from edge.core.movement import MovementError
from edge.core.rules import BeginAssault, EndGroundTurn, apply_result, reduce
from edge.server import session, wire
from edge.server.client import LocalClient, RemoteClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.app import EdgeApp
from edge.tui.screens.ground_assault import GroundAssaultScreen
from edge.tui.screens.game import GameScreen
from test_groundwar_assault_actions import CFG, _dropped, _reducer_world


def test_pre_drop_view_is_cropped_seedless_and_loadout_authoritative() -> None:
    state = _reducer_world()
    apply_result(state, reduce(state, 1, BeginAssault(1), CFG))
    view = session.ground_operation_view(
        state, 1, CFG, viewport_x=3, viewport_y=4,
        viewport_width=11, viewport_height=7,
    )
    assert isinstance(view, AssaultExpeditionDTO)
    assert (view.viewport_x, view.viewport_y, view.viewport_width, view.viewport_height) == (
        3, 4, 11, 7,
    )
    assert len(view.cells) == 77
    assert view.loadout is not None and view.can_drop
    assert all(option.deployable <= option.owned for option in view.loadout.options)
    assert not hasattr(view, "seed")
    assert not view.garrison
    assert all(not cell.structure_id for cell in view.cells)


def test_selected_actor_legality_and_fog_match_pure_projection() -> None:
    state = _reducer_world(reserved_infantry=20, reserved_armor=2)
    op = _dropped(state)
    actor_id = op.platoon[0].id
    amap = ga.assault_map_for_state(op, CFG)
    projected = ga.tactical_projection(op, amap, CFG, actor_id)
    view = session.ground_operation_view(state, 1, CFG, selected_actor_id=actor_id)
    assert isinstance(view, AssaultExpeditionDTO)
    by_cell = {(cell.x, cell.y): cell for cell in view.cells}
    assert {cell for cell, value in by_cell.items() if value.move_reachable} == projected.reachable
    assert {cell for cell, value in by_cell.items() if value.jump_reachable} == projected.jumpable
    assert {cell for cell, value in by_cell.items() if value.fire_target} == projected.fireable
    assert {cell for cell, value in by_cell.items() if value.missile_target} == projected.missile_targets
    visible_structure_ids = {
        structure.id for structure in amap.structures
        if (structure.x, structure.y) in projected.visible
    }
    assert {cell.structure_id for cell in view.cells if cell.structure_id} == visible_structure_ids
    assert all((unit.x, unit.y) in projected.visible for unit in view.garrison)


def test_stale_actor_and_operation_commands_are_rejected() -> None:
    state = _reducer_world(reserved_infantry=0)
    op = _dropped(state)
    view = session.ground_operation_view(state, 1, CFG, selected_actor_id=999_999)
    assert isinstance(view, AssaultExpeditionDTO)
    assert not any((view.can_move, view.can_jump, view.can_fire, view.can_missile))
    assert not any(cell.move_reachable or cell.fire_target for cell in view.cells)
    with pytest.raises(MovementError, match="operation"):
        reduce(state, 1, EndGroundTurn(op.operation_id + 1), CFG)


async def test_local_remote_and_wire_views_are_identical(tmp_path: Path) -> None:
    state = _reducer_world()
    op = _dropped(state)
    actor_id = op.platoon[0].id
    service = GameService(state, CFG, SqliteRepository(tmp_path / "assault.db"))
    local = LocalClient(service)
    expected = service.ground_operation_view(
        1, viewport_x=5, viewport_y=2, viewport_width=17, viewport_height=9,
        selected_actor_id=actor_id,
    )
    actual = await local.ground_operation_view(
        viewport_x=5, viewport_y=2, viewport_width=17, viewport_height=9,
        selected_actor_id=actor_id,
    )
    assert actual == expected
    assert actual is not None and wire.decode_dto(wire.encode_dto(actual)) == actual

    remote = RemoteClient("ws://unused")

    async def fake_call(method: str, params: dict[str, object]) -> object:
        assert method == "ground_operation_view"
        assert params["selected_actor_id"] == actor_id
        return wire.encode_dto(expected)

    remote._call = fake_call  # type: ignore[method-assign]
    assert await remote.ground_operation_view(
        viewport_x=5, viewport_y=2, viewport_width=17, viewport_height=9,
        selected_actor_id=actor_id,
    ) == expected


async def test_textual_move_and_confirmed_extract(tmp_path: Path) -> None:
    state = _reducer_world(reserved_infantry=0)
    _dropped(state)
    service = GameService(state, CFG, SqliteRepository(tmp_path / "pilot.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None and screen.view.selected_actor_id
        reachable = next(cell for cell in screen.view.cells if cell.move_reachable)
        await screen.set_cursor(reachable.x, reachable.y)
        await pilot.press("m")
        await pilot.pause()
        moved = state.players[1].ground_operation
        assert moved is not None and (moved.platoon[0].x, moved.platoon[0].y) == (
            reachable.x, reachable.y,
        )
        await pilot.press("escape")
        await pilot.pause()
        assert state.players[1].ground_operation is not None
        await pilot.press("y")
        await pilot.pause()
        assert state.players[1].ground_operation is None
        assert not isinstance(app.screen, GroundAssaultScreen)


async def test_game_screen_reconnect_resumes_active_assault(tmp_path: Path) -> None:
    state = _reducer_world()
    _dropped(state)
    state.regions = {1: Region(1, "Frontier")}
    service = GameService(state, CFG, SqliteRepository(tmp_path / "resume.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)
    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GameScreen(service, 1))
        await pilot.pause()
        assert isinstance(app.screen, GroundAssaultScreen)
        assert app.screen.view is not None


@pytest.mark.parametrize("outcome", ("surrender", "wiped"))
async def test_textual_outcome_and_settlement_flow(
    outcome: str, tmp_path: Path,
) -> None:
    state = _reducer_world(reserved_infantry=0)
    op = _dropped(state)
    platoon = op.platoon
    casualties = op.casualties
    if outcome == "wiped":
        platoon = tuple(replace(trooper, hp=0) for trooper in platoon)
        casualties = op.initial_strength
    state.players[1] = replace(
        state.players[1],
        ground_operation=replace(op, outcome=outcome, platoon=platoon, casualties=casualties),
    )
    service = GameService(state, CFG, SqliteRepository(tmp_path / f"{outcome}.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)
    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None and screen.view.outcome == outcome
        assert outcome.upper() in screen._status().plain  # noqa: SLF001
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert state.players[1].ground_operation is None


@pytest.mark.parametrize("size", ((80, 24), (100, 34), (140, 42)))
async def test_assault_screen_uses_responsive_layout(size: tuple[int, int], tmp_path: Path) -> None:
    state = _reducer_world()
    _dropped(state)
    service = GameService(state, CFG, SqliteRepository(tmp_path / f"{size[0]}.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)
    async with app.run_test(size=size) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.has_class("compact") == (size[0] < 90)
        assert screen.has_class("wide") == (size[0] >= 130)


@pytest.mark.parametrize(
    ("label", "size"),
    (("compact", (80, 24)), ("standard", (100, 34)), ("wide", (140, 42))),
)
def test_assault_responsive_snapshots(
    snap_compare: object, tmp_path: Path, label: str, size: tuple[int, int],
) -> None:
    state = _reducer_world()
    _dropped(state)
    service = GameService(state, CFG, SqliteRepository(tmp_path / f"snapshot-{label}.db"))
    client = LocalClient(service)

    async def open_assault(pilot: object) -> None:
        pilot.app.client = client  # type: ignore[attr-defined]
        pilot.app.push_screen(GroundAssaultScreen(client))  # type: ignore[attr-defined]
        await pilot.pause()  # type: ignore[attr-defined]

    assert snap_compare(  # type: ignore[operator]
        EdgeApp(plain=True), terminal_size=size, run_before=open_assault,
    )
