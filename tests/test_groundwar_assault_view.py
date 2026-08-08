"""GW-WP12 — fog-safe assault DTO, client parity, and live Textual flow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets import Static

from edge.core.dto import AssaultExpeditionDTO
from edge.core.events import GroundAssaultSettled
from edge.core.groundwar import assault as ga
from edge.core.models import Region
from edge.core.movement import MovementError
from edge.core.rules import BeginAssault, EndGroundTurn, GroundDrop, apply_result, reduce
from edge.server import session, wire
from edge.server.client import LocalClient, RemoteClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.app import EdgeApp
from edge.tui.screens.ground_assault import AssaultResultModal, GroundAssaultScreen
from edge.tui.screens.game import GameScreen
from test_groundwar_assault_actions import CFG, _dropped, _passable, _reducer_world


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
    # Passive geometry (walls/gates/buildings) projects unconditionally, like survey's
    # settlements — only the active-defense kinds stay gated behind live trooper LOS.
    visible_structure_ids = {
        structure.id for structure in amap.structures
        if (structure.x, structure.y) in projected.visible
        or structure.kind in ga.PASSIVE_STRUCTURE_KINDS
    }
    assert {cell.structure_id for cell in view.cells if cell.structure_id} == visible_structure_ids
    assert all((unit.x, unit.y) in projected.visible for unit in view.garrison)


def test_pre_drop_projection_paints_a_coarse_city_hazard_not_exact_batteries() -> None:
    """GW-WP13-FU1: the drop-placement screen gets *some* danger read (a fixed AA-range
    radius around each city center — doctrine knowledge, not sensor telemetry), but
    never leaks which cells inside a city actually hold a live battery."""
    state = _reducer_world()
    apply_result(state, reduce(state, 1, BeginAssault(1), CFG))
    op = state.players[1].ground_operation
    amap = ga.assault_map_for(state, op, CFG)
    projected = ga.tactical_projection(op, amap, CFG)
    assert not op.dropped
    assert projected.visible == projected.reachable == projected.fireable == frozenset()
    assert projected.aa_threat, "the pre-drop screen should show some landing hazard"
    aa_range = CFG.groundwar.defenses.aa.range  # type: ignore[union-attr]
    expected = set()
    for city in amap.cities:
        for y in range(max(0, city.cy - aa_range), min(amap.height, city.cy + aa_range + 1)):
            for x in range(max(0, city.cx - aa_range), min(amap.width, city.cx + aa_range + 1)):
                if (x - city.cx) ** 2 + (y - city.cy) ** 2 <= aa_range ** 2:
                    expected.add((x, y))
    # A plain filled disc around each city center, matching the coarse formula exactly —
    # proof this is doctrine geometry, not derived from any individual battery's position.
    assert projected.aa_threat == frozenset(expected)
    aa_batteries = {(s.x, s.y) for s in amap.structures if s.kind == "aa"}
    assert aa_batteries, "fixture drifted: expected at least one AA battery on the map"


def test_city_geometry_visible_at_range_but_active_defenses_stay_fogged() -> None:
    """A city out of every trooper's LOS must not render as empty ground.

    Walls/gates/buildings are static footprint, not a hidden threat, so they project
    unconditionally — the same way survey never fogs a settlement's `blocked`/`gate`
    cells. Active defenses (turret/aa/sensor/citadel_gun) stay LOS-gated: scouting them
    is still the point, and a remote client must not reverse-engineer their placement.
    """
    state = _reducer_world(reserved_infantry=0)
    op = _dropped(state)
    amap = ga.assault_map_for_state(op, CFG)
    trooper = op.platoon[0]
    city = amap.cities[0]
    assert (trooper.x - city.cx) ** 2 + (trooper.y - city.cy) ** 2 > 30 ** 2, (
        "fixture drifted: the trooper must land well outside every city's sight range")
    far_structures = [s for s in amap.structures if s.city_id == city.id]
    assert any(s.kind in ga.PASSIVE_STRUCTURE_KINDS for s in far_structures)
    assert any(s.kind not in ga.PASSIVE_STRUCTURE_KINDS for s in far_structures)

    view = session.ground_operation_view(
        state, 1, CFG, viewport_x=0, viewport_y=0,
        viewport_width=amap.width, viewport_height=amap.height,
    )
    assert isinstance(view, AssaultExpeditionDTO)
    revealed_kinds = {cell.structure_kind for cell in view.cells if cell.structure_id}
    assert revealed_kinds & ga.PASSIVE_STRUCTURE_KINDS, (
        "a city far outside LOS must still show its walls/gates/buildings")
    assert not (revealed_kinds - ga.PASSIVE_STRUCTURE_KINDS), (
        "active defenses must stay hidden until a trooper actually sees them")


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


async def test_textual_space_selects_next_trooper_and_e_ends_turn(tmp_path: Path) -> None:
    """GW help-text rebind: Space now cycles troopers (Tab's old job) and E ends the
    round (Space's old job) — regression guard that the swapped bindings actually
    reach the screen's actions rather than being swallowed by the focused map."""
    state = _reducer_world(reserved_infantry=0)
    apply_result(state, reduce(state, 1, BeginAssault(1), CFG))
    op = state.players[1].ground_operation
    amap = ga.assault_map_for(state, op, CFG)
    lx, ly = amap.landing_x, amap.landing_y
    ox, oy = next(
        (x, y)
        for dx in range(-3, 4) for dy in range(-3, 4)
        for x, y in ((lx + dx, ly + dy),)
        if (x, y) != (lx, ly) and _passable(amap, x, y)
    )
    apply_result(state, reduce(state, 1, GroundDrop(
        op.operation_id, (("marauder", lx, ly), ("marauder", ox, oy))), CFG))
    service = GameService(state, CFG, SqliteRepository(tmp_path / "keys.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        first_selected = screen.selected_actor_id
        assert first_selected is not None

        await pilot.press("space")
        await pilot.pause()
        assert screen.selected_actor_id is not None
        assert screen.selected_actor_id != first_selected

        turn_before = state.players[1].ground_operation.local_turn  # type: ignore[union-attr]
        await pilot.press("e")
        await pilot.pause()
        assert state.players[1].ground_operation.local_turn == turn_before + 1  # type: ignore[union-attr]


async def test_textual_u_undoes_and_shift_u_redoes_a_move(tmp_path: Path) -> None:
    """GW help follow-up: U steps a completed in-round action back, Shift+U steps it
    forward again — a live regression guard (not just the core reducer test) that
    both keys actually reach the screen and round-trip the server's undo stack."""
    state = _reducer_world(reserved_infantry=0)
    _dropped(state)
    service = GameService(state, CFG, SqliteRepository(tmp_path / "undo.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None and not screen.view.can_undo
        before = (screen.view.troopers[0].x, screen.view.troopers[0].y)
        reachable = next(cell for cell in screen.view.cells if cell.move_reachable)
        await screen.set_cursor(reachable.x, reachable.y)

        await pilot.press("m")
        await pilot.pause()
        assert screen.view is not None
        moved = (screen.view.troopers[0].x, screen.view.troopers[0].y)
        assert moved == (reachable.x, reachable.y) and moved != before
        assert screen.view.can_undo and not screen.view.can_redo

        await pilot.press("u")
        await pilot.pause()
        assert screen.view is not None
        assert (screen.view.troopers[0].x, screen.view.troopers[0].y) == before
        assert not screen.view.can_undo and screen.view.can_redo

        await pilot.press("U")
        await pilot.pause()
        assert screen.view is not None
        assert (screen.view.troopers[0].x, screen.view.troopers[0].y) == moved
        assert screen.view.can_undo and not screen.view.can_redo


def test_tracer_cells_draws_the_path_between_shooter_and_target() -> None:
    from edge.tui.screens._ground_shared import tracer_cells

    assert tracer_cells(0, 0, 0, 0, "red") == {}
    assert tracer_cells(0, 0, 1, 0, "red") == {}, "adjacent cells have no interior to trace"
    assert tracer_cells(0, 0, 3, 0, "red") == {(1, 0): ("─", "red"), (2, 0): ("─", "red")}
    assert tracer_cells(0, 0, 0, 3, "red") == {(0, 1): ("│", "red"), (0, 2): ("│", "red")}
    assert tracer_cells(0, 0, 3, 3, "red") == {(1, 1): ("╲", "red"), (2, 2): ("╲", "red")}
    assert tracer_cells(3, 0, 0, 3, "red") == {(2, 1): ("╱", "red"), (1, 2): ("╱", "red")}


def test_landing_frames_masks_the_touchdown_cell_until_impact() -> None:
    """`GroundDrop`/`SurveyLand` already land the unit server-side before the descent
    animation plays, so the DTO's real glyph sits at the touchdown cell from frame
    one — every pre-impact frame must explicitly override that cell too (not just
    the falling capsule above it), or the trooper/explorer glyph shows through
    underneath the still-descending rocket."""
    from edge.tui.screens._ground_shared import landing_frames

    frames = landing_frames([((10, 10), "M", "black on green")])
    # Frames 0-3 are the sky descent (rocket at y-4..y-1) — the ground cell must
    # read as "inbound", never the real glyph, on every one of them.
    for frame in frames[:4]:
        assert frame.cells[(10, 10)] == ("▼", "black on bright_green")
    # Frame 4 is impact (rocket now at the ground cell) — still not the real glyph.
    assert frames[4].cells[(10, 10)][0] == "▼"
    assert frames[4].cells[(10, 10)] != ("M", "black on green")
    # Only from the settle frame onward does the real glyph appear.
    assert frames[5].cells[(10, 10)] == ("M", "black on green")
    assert frames[6].cells[(10, 10)] == ("M", "black on green")


async def test_narrate_draws_a_tracer_and_collects_a_kia_line(tmp_path: Path) -> None:
    """GW help follow-up: a shot narrated through `_narrate` leaves a tracer overlay
    on the map, and a defender's "killed" line is remembered for the post-mortem
    (whether the trooper who fired or the defender who killed someone)."""
    from edge.core.events import GroundDefenseFireLogged, GroundFired

    state = _reducer_world(reserved_infantry=0)
    op = _dropped(state)
    shooter = op.platoon[0]
    service = GameService(state, CFG, SqliteRepository(tmp_path / "narrate.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None

        fired = GroundFired(1, op.operation_id, shooter.id, shooter.x + 3, shooter.y,
                            False, True, "structure", False)
        killed = GroundDefenseFireLogged(
            1, op.operation_id, "killed", f"{shooter.name} is KIA — cut down by turret.",
            shooter.x, shooter.y, False, shooter.x - 2, shooter.y)
        await screen._narrate([fired, killed])

        assert screen.anim_cells, "a fired shot should leave a tracer overlay"
        assert screen._kia_lines == [f"{shooter.name} is KIA — cut down by turret."]

        modal = AssaultResultModal("World", GroundAssaultSettled(
            1, op.planet_id, "wiped", "", 1, 0, 0, 0, 0), screen._kia_lines)
        app.push_screen(modal)
        await pilot.pause()
        kia = app.screen.query_one("#result-kia", Static)
        assert f"{shooter.name} is KIA" in str(kia.content)


async def test_result_modal_footer_stays_reachable_with_a_full_platoon_wiped() -> None:
    """A 14-trooper wipe (max_troopers) adds 14 causes-of-death lines to the box —
    on a short terminal that must scroll, not push the "Esc or Enter" footer off
    screen with no way back (GW help follow-up)."""
    kia_lines = [f"Trooper{i} is KIA — cut down by turret." for i in range(14)]
    settled = GroundAssaultSettled(1, 1, "wiped", "", 14, 3, 0, 2, 0)
    app = EdgeApp(plain=True)
    async with app.run_test(size=(80, 24)) as pilot:  # 80x24: the app's own supported floor
        app.push_screen(AssaultResultModal("World", settled, kia_lines))
        await pilot.pause()
        footer = app.screen.query_one("#result-footer", Static)
        footer.scroll_visible(animate=False)
        await pilot.pause()
        region = footer.region
        assert 0 <= region.y < 24, "the footer must be scrollable into view, not stranded"


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
        base_screen, base_depth = app.screen, len(app.screen_stack)
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None and screen.view.outcome == outcome
        assert outcome.upper() in screen._status().plain  # noqa: SLF001
        # A settled operation (win or loss) extracts straight away — no "abort and lose
        # everything?" confirm, since there is nothing left to lose — and reports the
        # result in a modal instead of the ConfirmScreen used mid-fight.
        await pilot.press("escape")
        await pilot.pause()
        assert state.players[1].ground_operation is None
        assert isinstance(app.screen, AssaultResultModal)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        # Exactly two pops here: the modal's own dismiss-pop, then _extract()'s
        # explicit pop of this screen. GroundAssaultScreen suppresses its own
        # on_screen_resume self-pop while _extracting (see test below) — without that
        # guard, a resume triggered by the modal popping can race _extract()'s pop and
        # remove an extra screen, landing one level too deep (GW regression).
        assert app.screen is base_screen
        assert len(app.screen_stack) == base_depth


async def test_on_screen_resume_skips_self_pop_while_extracting(tmp_path: Path) -> None:
    """The `_extracting` guard's actual contract, tested directly rather than by timing.

    `on_screen_resume` -> `_load()` self-pops when the ground operation is gone (a
    safety net for e.g. reconnect flows). But `_extract()` also pops this screen once
    it finishes extracting, and popping a screen above this one (a result modal, the
    abort ConfirmScreen) triggers a resume here too. Racing those two "operation's
    gone, pop" paths against real async timing landed the fix on the wrong screen in
    production (only reproducible by injecting a delay, per the GW incident) — headless
    pilot timing never interleaves them, so a flow-level test can pass while this
    exact regression is broken. Assert the guard's contract directly instead."""
    state = _reducer_world(reserved_infantry=0)
    op = _dropped(state)
    state.players[1] = replace(
        state.players[1], ground_operation=replace(op, outcome=None),
    )
    service = GameService(state, CFG, SqliteRepository(tmp_path / "guard.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)
    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None
        depth = len(app.screen_stack)

        # Simulate the operation having just been extracted out from under this
        # screen (as _extract() does) while a resume is in flight.
        state.players[1] = replace(state.players[1], ground_operation=None)
        screen._extracting = True  # noqa: SLF001
        await screen.on_screen_resume()
        assert app.screen is screen
        assert len(app.screen_stack) == depth

        # Un-set the guard: the same resume now self-pops as designed (the safety net
        # for a legitimately vanished operation, e.g. reconnect flows).
        screen._extracting = False  # noqa: SLF001
        await screen.on_screen_resume()
        assert app.screen is not screen
        assert len(app.screen_stack) == depth - 1


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


@pytest.mark.parametrize("size", ((80, 24), (100, 34), (140, 42)))
async def test_first_frame_viewport_matches_the_mounted_map_widget_size(
    size: tuple[int, int], tmp_path: Path,
) -> None:
    """The DTO fetched for the very first rendered frame must cover the whole map
    widget, not a stand-in guess made before that widget existed.

    Before `_settle_viewport`, `on_mount`'s only `_load` ran while `AssaultMapView`
    didn't exist yet (`compose` shows nothing/the squad chooser until the first load
    completes), so `_viewport_size`'s no-widget fallback stood in for the real size.
    On a wide terminal that fallback under-covers the widget, and `_render_frame`
    only ever paints exactly `view.viewport_width`x`view.viewport_height` cells — the
    rest of the widget renders as blank background until an incidental resize event
    corrects it. This is what `test_assault_responsive_snapshots[wide-*]` caught.
    """
    from edge.tui.screens.ground_assault import AssaultMapView

    state = _reducer_world()
    _dropped(state)
    service = GameService(state, CFG, SqliteRepository(tmp_path / f"first-frame-{size[0]}.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)
    async with app.run_test(size=size) as pilot:
        app.client = client
        app.push_screen(GroundAssaultScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None
        maps = screen.query(AssaultMapView)
        assert maps
        widget = maps.first()
        assert (screen.view.viewport_width, screen.view.viewport_height) == (
            widget.size.width, widget.size.height,
        )


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
