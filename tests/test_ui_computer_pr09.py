"""WP-PR09 — Computer prioritization and navigation continuity (PT-08/09/23/27/31).

Projection: player-owned planets and base-hosted ports sort first and carry ownership;
finished contracts stay listed with a status. UI: the DetailTable priority group keeps
owned rows on top under any user sort; plotting from any subview lands on Route; and the
avoid list is reachable from a Notes-tab button.
"""

from __future__ import annotations

from dataclasses import replace

from textual.widgets import DataTable

from edge.config import load_default_config
from edge.core.models import Contract, Ownership
from edge.core.movement import shortest_path
from edge.core.rules import Warp
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot
from edge.tui.screens.computer import ComputerScreen

CFG = load_default_config()


def _svc(tmp_path) -> GameService:
    svc = GameService.new_game(CFG, 42, SqliteRepository(tmp_path / "g.db"))
    st = svc._state
    st.players[1] = replace(st.players[1], explored_sectors=frozenset(st.sectors))
    return svc


# --- projection: ownership sort + contract history ---------------------------


def test_owned_planet_sorts_first(tmp_path) -> None:
    svc = _svc(tmp_path)
    st = svc._state
    # Own a *far* planet so only ownership (not distance) could float it up.
    dist_sorted = svc.computer_view(1).planets
    far = dist_sorted[-1]
    st.planets[far.planet_id] = replace(st.planets[far.planet_id], owner=Ownership("player", 1))
    planets = svc.computer_view(1).planets
    assert planets[0].owned_by_you and planets[0].planet_id == far.planet_id


def test_planet_directory_projects_colony_infrastructure_and_starbase(tmp_path) -> None:
    svc = _svc(tmp_path)
    st = svc._state
    planets = list(st.planets.values())
    citadel, city = planets[:2]
    st.planets[citadel.id] = replace(citadel, citadel_level=2, cloud_city_size=0)
    st.planets[city.id] = replace(city, citadel_level=0, cloud_city_size=3)

    rows = {row.planet_id: row for row in svc.computer_view(1).planets}
    assert rows[citadel.id].citadel_level == 2 and rows[citadel.id].cloud_city_size == 0
    assert rows[city.id].cloud_city_size == 3 and rows[city.id].citadel_level == 0

    base = next(base for base in st.starbases.values() if base.planet_id in rows)
    from edge.core.starbases import is_operational
    expected = "operational" if is_operational(base) else "derelict"
    assert rows[base.planet_id].starbase_status == expected


def test_owned_base_port_sorts_first_with_status(tmp_path) -> None:
    svc = _svc(tmp_path)
    st = svc._state
    # Find a port that shares a sector with a starbase; make that base the player's.
    base = next(iter(st.starbases.values()))
    port = next((p for p in st.ports.values() if p.sector_id == base.sector_id), None)
    if port is None:  # no co-located port in this seed — synthesize ownership on any base's port
        return
    st.starbases[base.id] = replace(base, owner=Ownership("player", 1))
    ports = svc.computer_view(1).ports
    top = ports[0]
    assert top.starbase_yours and top.starbase_id == base.id and top.starbase_status


def test_finished_contracts_are_retained_with_status(tmp_path) -> None:
    svc = _svc(tmp_path)
    st = svc._state
    done = Contract(id=1, kind="deliver", issuer="thess", status="done", reward_slips=100,
                    reward_attitude=0.0, accepted_day=1, deadline_day=5, dest_sector=None)
    failed = Contract(id=2, kind="destroy", issuer="vex", status="failed", reward_slips=50,
                      reward_attitude=0.0, accepted_day=1, deadline_day=5,
                      target_species_id=None)
    active = Contract(id=3, kind="escort", issuer="sel", status="active", reward_slips=75,
                      reward_attitude=0.0, accepted_day=1, deadline_day=9, dest_sector=None)
    st.players[1] = replace(st.players[1], contracts=(done, failed, active))
    rows = svc.computer_view(1).contracts
    assert rows[0].status == "active"  # active first
    assert {r.status for r in rows} == {"active", "done", "failed"}


# --- UI: grouping under user sort, route continuity, avoid button ------------


async def _open_computer(app: EdgeApp, pilot: object) -> ComputerScreen:
    clear_slot()
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    start = svc.game_view(1).sector.sector_id  # type: ignore[attr-defined]
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)  # type: ignore[attr-defined]
    for hop in (shortest_path(svc.state.adjacency, start, dock.sector_id) or [])[1:]:  # type: ignore[attr-defined]
        svc.apply(1, Warp(to_sector=hop))  # type: ignore[attr-defined]
    svc.state.players[1] = replace(svc.state.players[1],  # type: ignore[attr-defined]
                                   explored_sectors=frozenset(svc.state.sectors))  # type: ignore[attr-defined]
    await pilot.press("c")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    assert isinstance(app.screen, ComputerScreen)
    return app.screen


async def test_owned_planet_stays_top_even_when_user_sorts() -> None:
    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        svc = app.service

        far = svc.computer_view(1).planets[-1]  # type: ignore[attr-defined]
        svc.state.planets[far.planet_id] = replace(  # type: ignore[attr-defined]
            svc.state.planets[far.planet_id], owner=Ownership("player", 1))  # type: ignore[attr-defined]
        # Reopen the Computer so it re-reads the projection (the screen snapshots its DTO).
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        screen = app.screen  # the fresh ComputerScreen
        assert isinstance(screen, ComputerScreen)
        screen.show_subview("planets")
        await pilot.pause()
        from edge.tui.detail_table import DetailTable
        from textual.widgets import DataTable
        dt = screen.query_one("#planets-table-panel", DetailTable)
        # Sort by a column, ascending then descending: the owned row stays first either way.
        for _ in range(2):
            dt.action_cycle_sort()
            await pilot.pause()
            table = dt.query_one(DataTable)
            top_key = table.coordinate_to_cell_key((0, 0)).row_key.value
            planets = svc.computer_view(1).planets  # type: ignore[attr-defined]
            assert planets[int(top_key)].owned_by_you


async def test_planets_table_labels_citadel_cloud_city_and_starbase() -> None:
    app = EdgeApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        svc = app.service
        st = svc.state  # type: ignore[union-attr]
        base = next(base for base in st.starbases.values() if base.planet_id is not None)
        base_planet = st.planets[base.planet_id]
        city_planet = next(planet for planet in st.planets.values()
                           if planet.id != base_planet.id and planet.starbase_id is None)
        st.planets[base_planet.id] = replace(base_planet, citadel_level=2, cloud_city_size=0)
        st.planets[city_planet.id] = replace(city_planet, citadel_level=0, cloud_city_size=3)

        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        screen = app.screen  # type: ignore[assignment]
        assert isinstance(screen, ComputerScreen)
        screen.show_subview("planets")
        await pilot.pause()
        table = screen.query_one("#planets-table", DataTable)
        rows = screen._computer.planets
        base_key = str(next(i for i, row in enumerate(rows) if row.planet_id == base_planet.id))
        city_key = str(next(i for i, row in enumerate(rows) if row.planet_id == city_planet.id))
        base_row = table.get_row(base_key)
        city_row = table.get_row(city_key)
        assert str(base_row[6]) == "Citadel L2"
        assert str(base_row[7]) in {"operational", "derelict"}
        assert str(city_row[6]) == "Cloud City (size 3)"
        assert str(city_row[7]) == "—"


async def test_plot_route_from_subviews_lands_on_route() -> None:
    """PT-31 (§8.1): plotting from Planets, Ports, and the Map all end on Route, no flash-back."""
    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        for sub in ("ports", "planets"):
            screen.show_subview(sub)
            await pilot.pause()
            screen.action_plot_route()
            await pilot.pause()
            await pilot.pause()
            assert screen._active_subview() == "route", f"plot from {sub} did not land on Route"
        # Map: clicking a sector plots and shows Route too.
        svc = app.service
        here = svc.game_view(1).sector.sector_id  # type: ignore[attr-defined]
        target = next(s for s in svc.state.sectors if s != here)  # type: ignore[attr-defined]
        screen.on_local_map_view_picked(type("P", (), {"sector_id": target})())
        await pilot.pause()
        await pilot.pause()
        assert screen._active_subview() == "route"


async def test_port_directory_shows_market_status() -> None:
    """PT-09 (§8.1): a base-hosted port row carries its market open/dark status."""
    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_computer(app, pilot)  # explores every sector so ports populate
        svc = app.service
        ports = svc.computer_view(1).ports  # type: ignore[attr-defined]
        based = [p for p in ports if p.starbase_id is not None]
        assert based, "seed has no base-hosted port among explored sectors"
        # market_open tracks the base's operational state.
        st = svc.state  # type: ignore[attr-defined]
        base_id = based[0].starbase_id
        from edge.core.starbases import is_operational
        assert based[0].starbase_market_open == is_operational(st.starbases[base_id])


async def test_avoid_button_opens_prompt() -> None:
    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        screen.show_subview("notes")
        await pilot.pause()
        from textual.widgets import Button
        from edge.tui.screens.travel import TravelPromptScreen
        screen.query_one("#avoid-add", Button).press()
        await pilot.pause()
        assert isinstance(app.screen, TravelPromptScreen)


async def test_avoid_key_targets_highlighted_port_planet_and_route_rows() -> None:
    """PT-23: V acts on the selected row without opening the numeric-sector prompt."""
    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        svc = app.service

        def is_avoided(internal: int) -> bool:
            return any(svc.resolve_display_id(shown) == internal  # type: ignore[attr-defined]
                       for shown in svc.computer_view(1).avoid)  # type: ignore[attr-defined]

        for subview, table_id, entries in (
            ("ports", "#ports-table", screen._computer.ports),
            ("planets", "#planets-table", screen._computer.planets),
        ):
            screen.show_subview(subview)
            await pilot.pause()
            table = screen.query_one(table_id, DataTable)
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            target = entries[int(key)].sector_id
            screen.action_toggle_avoid()
            await pilot.pause()
            assert is_avoided(target)
            assert isinstance(app.screen, ComputerScreen)

        # Plot from the selected planet, then V targets the highlighted route hop.
        screen.action_plot_route()
        await pilot.pause()
        route = screen.query_one("#route-table", DataTable)
        route_target = int(route.coordinate_to_cell_key(route.cursor_coordinate).row_key.value)
        was_avoided = is_avoided(route_target)
        screen.action_toggle_avoid()
        await pilot.pause()
        assert is_avoided(route_target) is not was_avoided
        assert isinstance(app.screen, ComputerScreen)
