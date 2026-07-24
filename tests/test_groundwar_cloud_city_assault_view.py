"""GW-WP16 — Cloud City assault via the production TUI (Textual Pilot smoke test).

Confirms the unmodified `GroundAssaultScreen`/`edge.groundwar.harness` render and
accept input against a Cloud City `AssaultMap` — the same production screen the
live game pushes for a terrestrial assault, now driven against the new topology.
The gate is forced on locally for this test only (`config/groundwar_default.yaml`
keeps it off until GW-WP16 closes GW-M5); this proves the screen works once it
does, without depending on the flip having already happened.
"""

from __future__ import annotations

from pathlib import Path

from edge.config import load_default_config
from edge.core.groundwar import assault as ga
from edge.core.rules import BeginAssault, GroundDrop, apply_result, reduce
from edge.groundwar import harness
from edge.server.client import LocalClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.app import EdgeApp
from edge.tui.screens.ground_assault import GroundAssaultScreen

CFG = load_default_config()
assert CFG.groundwar is not None
GATE_ON = CFG.model_copy(update={
    "groundwar": CFG.groundwar.model_copy(update={"cloud_city_assault_enabled": True})})


def _dropped_state() -> object:
    state = harness.cloud_city_assault_state(
        GATE_ON, seed=7, cloud_city_size=2, citadel_level=0,
        loadout={"marauder": 2, "scout": 1, "command": 1})
    apply_result(state, reduce(state, harness.PLAYER_ID, BeginAssault(harness.PLANET_ID), GATE_ON))
    op = state.players[harness.PLAYER_ID].ground_operation
    assert op is not None
    amap = ga.assault_map_for(state, op, GATE_ON)
    apply_result(state, reduce(
        state, harness.PLAYER_ID,
        GroundDrop(op.operation_id, (("marauder", amap.landing_x, amap.landing_y),)), GATE_ON))
    return state


async def test_cloud_city_assault_renders_via_production_screen(tmp_path: Path) -> None:
    state = _dropped_state()
    service = GameService(state, GATE_ON, SqliteRepository(tmp_path / "cc.db"))
    client = LocalClient(service, player_id=harness.PLAYER_ID)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None
        assert screen.view.selected_actor_id
        # Whole-station model (interview decision): the CITIES panel has exactly
        # one row regardless of how many physical districts were generated.
        assert len(screen.view.cities) == 1
        assert screen.view.cities[0].is_citadel


async def test_cloud_city_assault_move_and_extract_via_pilot(tmp_path: Path) -> None:
    state = _dropped_state()
    service = GameService(state, GATE_ON, SqliteRepository(tmp_path / "cc2.db"))
    client = LocalClient(service, player_id=harness.PLAYER_ID)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        reachable = next(
            (cell for cell in screen.view.cells if cell.move_reachable), None)
        if reachable is not None:
            await screen.set_cursor(reachable.x, reachable.y)
            await pilot.press("m")
            await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert state.players[harness.PLAYER_ID].ground_operation is None
        assert not isinstance(app.screen, GroundAssaultScreen)
