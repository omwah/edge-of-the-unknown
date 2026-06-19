"""WP8/WP9 — Textual Pilot flow over the live service (DESIGN §13).

Drives the real app: new game, navigate to the StarDock, dock, trade, and buy
the first upgrade — asserting the underlying game state changes through the UI.
Navigation between sectors is done via the service (clicking each warp button is
fiddly); the dock/trade/upgrade interactions are exercised through the UI.
"""

from __future__ import annotations

from edge.core.movement import shortest_path
from edge.core.rules import Warp
from edge.tui.app import EdgeApp
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.widgets import NeighborRow


async def _new_game_at_stardock(app: EdgeApp, pilot: object) -> object:
    """Press New game, then warp the player to the StarDock and dock (press P)."""
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    path = shortest_path(svc.state.adjacency, 1, dock.sector_id)
    assert path is not None
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    await pilot.press("p")  # dock -> StarDockScreen  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return svc


async def test_new_game_pushes_live_game_screen() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert app.service is not None
        view = app.service.game_view(1)
        assert view.sector.sector_id == 1 and view.turns == 250


async def test_sidebar_neighbor_click_warps() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        start = svc.game_view(1).sector.sector_id
        rows = app.screen.query(NeighborRow)
        assert rows
        first = rows.first()
        target = first._sector_id
        await pilot.click(first)
        await pilot.pause()
        moved = svc.game_view(1).sector.sector_id
        assert moved == target != start


async def test_log_hotkey_opens_computer_with_signpost() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("g")  # Log -> Computer, folded in (WP-B)
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        from textual.widgets import DataTable

        rows = app.screen.query_one("#log-table", DataTable)
        cells = [str(rows.get_cell_at((r, 1))) for r in range(rows.row_count)]
        assert any("StarDock" in c for c in cells)


async def test_travel_prompt_warps_along_known_route() -> None:
    from textual.widgets import Input

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Uncover a neighbour with a two-way edge, then travel back to the Core (1).
        a = next(s for s in svc.state.sectors[1].warps_out
                 if 1 in svc.state.sectors[s].warps_out)
        svc.apply(1, Warp(to_sector=a))
        await pilot.press("w")  # open the travel prompt (WP-C)
        await pilot.pause()
        assert isinstance(app.screen, TravelPromptScreen)
        # The prompt takes a *spatial* display id (§5.1) — type Sector 1's spatial id.
        app.screen.query_one("#travel-input", Input).value = str(svc.state.spatial_ids[1])
        await pilot.press("enter")
        await pilot.pause()
        assert svc.game_view(1).sector.sector_id == 1


async def test_sector_title_shows_spatial_id() -> None:
    """The game screen renders the sector's spatial display id, not the internal id (§5.1)."""
    from textual.widgets import Static

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        spatial = svc.state.spatial_ids[1]  # the player starts at internal sector 1
        assert spatial != 1  # the spatial id genuinely differs from the internal id
        title = str(app.screen.query_one("#title", Static).render())
        assert f"[{spatial}]" in title


async def test_arrow_keys_move_warp_focus() -> None:
    """Arrow keys move focus between warp buttons by their on-screen layout (round-2).

    The current-sector marker (grid centre) is auto-focused on the fresh game screen
    (no priming Tab), so the first arrow press moves *relative to the current sector*;
    further presses step by grid geometry — Right/Left along a row, Down/Up a column.
    """
    from edge.tui.widgets import CurrentSectorMarker, WarpButton, WarpGrid

    def land(buttons: dict, start: tuple[int, int], delta: tuple[int, int], max_row: int):
        r, c = start[0] + delta[0], start[1] + delta[1]
        while 0 <= r <= max_row and 0 <= c < 3:
            if (r, c) in buttons:
                return (r, c)
            r, c = r + delta[0], c + delta[1]
        return None

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        # No Tab pressed: the current-sector marker holds focus as the anchor.
        assert isinstance(app.focused, CurrentSectorMarker)

        grid = app.screen.query_one(WarpGrid)
        children = list(grid.children)
        pos = {c: (i // 3, i % 3) for i, c in enumerate(children)}
        buttons = {pos[c]: c for c in children if isinstance(c, WarpButton)}
        max_row = (len(children) - 1) // 3
        centre = pos[app.focused]  # the marker's grid position (1, 1)

        # First press from the centre lands on the warp in that screen direction.
        keys = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        first = next(((k, land(buttons, centre, d, max_row)) for k, d in keys.items()
                      if land(buttons, centre, d, max_row) is not None), None)
        assert first is not None
        key, target = first
        await pilot.press(key)
        await pilot.pause()
        assert app.focused is buttons[target]

        # Right/Left along a row, relative to the now-focused warp button.
        row_pair = next(((p, (p[0], p[1] + 1)) for p in buttons if (p[0], p[1] + 1) in buttons), None)
        assert row_pair is not None
        src, dst = row_pair
        buttons[src].focus()
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        assert app.focused is buttons[dst]
        await pilot.press("left")
        await pilot.pause()
        assert app.focused is buttons[src]


async def test_dock_and_trade_buys_fuel() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        await pilot.press("t")  # trade the highlighted row (Fuel Ore) -> buy
        await pilot.pause()
        from edge.core.enums import Commodity

        assert svc.state.ships[1].cargo.get(Commodity.FUEL_ORE, 0) > 0
        assert svc.state.players[1].latinum < 2_000  # spent latinum buying


async def test_dock_and_haggle_accepts_fair_counter() -> None:
    """Press H, counter at the fair price (improvement 0 ⇒ always accepted), and the
    deal goes through as a HaggleOffer — the path playtesting found missing."""
    from textual.widgets import Input

    from edge.core.enums import Commodity
    from edge.core.events import Haggled
    from edge.tui.screens.haggle import HaggleScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        port = svc.current_port_view(1)
        assert port is not None
        fair = next(c for c in port.commodities if c.name == "Fuel Ore").price

        await pilot.press("h")  # open the haggle modal on the highlighted row (Fuel Ore)
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)
        # Countering at the fair price does not favour the player → accepted with p=1.0.
        app.screen.query_one("#haggle-input", Input).value = str(fair)
        await pilot.press("enter")
        await pilot.pause()

        assert svc.state.ships[1].cargo.get(Commodity.FUEL_ORE, 0) > 0  # bought via haggle
        assert svc.state.players[1].latinum < 2_000  # spent latinum
        assert any(isinstance(e, Haggled) for e in svc._repo.load_events())  # logged as a haggle


async def test_haggle_walk_away_makes_no_trade() -> None:
    from edge.tui.screens.haggle import HaggleScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)
        await pilot.press("escape")  # walk away — no offer made
        await pilot.pause()
        assert isinstance(app.screen, StarDockScreen)
        assert svc.state.players[1].latinum == 2_000  # nothing spent


async def test_descend_explore_log_flow() -> None:
    """The §13 named flow: survey a planet → descend → explore a site → log it."""
    from collections import defaultdict

    from edge.core.rules import Warp
    from edge.tui.screens.planet import PlanetScreen
    from edge.tui.screens.surface import SurfaceScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None

        # A reachable planet whose lowest-slot site is obvious (so one Explore at the
        # starter sensor reveals the row-0 site, which Log then collects).
        by_planet: dict[int, list[object]] = defaultdict(list)
        for d in svc.state.discoveries.values():
            if d.planet_id is not None:
                by_planet[d.planet_id].append(d)
        target = None
        for _pid, ds in by_planet.items():
            slot0 = min(ds, key=lambda d: d.site_slot)
            if not slot0.hidden and shortest_path(svc.state.adjacency, 1, slot0.sector_id) is not None:
                target = slot0
                break
        assert target is not None
        for hop in shortest_path(svc.state.adjacency, 1, target.sector_id)[1:]:
            svc.apply(1, Warp(to_sector=hop))

        await pilot.press("s")  # survey planet -> PlanetScreen
        await pilot.pause()
        assert isinstance(app.screen, PlanetScreen)
        await pilot.press("d")  # descend -> SurfaceScreen
        await pilot.pause()
        assert isinstance(app.screen, SurfaceScreen)
        await pilot.press("e")  # survey the next site (the obvious slot-0 one)
        await pilot.pause()
        await pilot.press("l")  # log the highlighted (now revealed) site
        await pilot.pause()
        assert target.id in svc.state.players[1].codex


async def test_stardock_hardware_buys_then_engine_room_installs() -> None:
    from textual.widgets import TabbedContent

    from edge.tui.screens.engine_room import EngineRoomScreen, _SubsystemPanel

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        app.screen.query_one(TabbedContent).active = "hardware"
        await pilot.pause()
        lat0 = svc.state.players[1].latinum
        await pilot.press("b")  # buy the highlighted component (Tier-I, affordable)
        await pilot.pause()
        loose = sum(svc.state.ships[1].components.values())
        assert loose == 1 and svc.state.players[1].latinum < lat0
        # Slot it in the engine room. Install is a two-step interaction: select the
        # loose component in the picker, then click a subsystem panel to drop it into
        # that subsystem's first legal empty slot — a derived aspect then rises.
        await pilot.press("e")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, EngineRoomScreen)
        await pilot.click(screen.query(".loose_components").first())  # select the part
        await pilot.pause()
        # Target whichever subsystem accepts the on-hand part (Tier-I parts are widely
        # legal); a successful install reopens the screen, so stop once it lands.
        for panel in list(screen.query(_SubsystemPanel)):
            await pilot.click(panel)
            await pilot.pause()
            if sum(svc.state.ships[1].components.values()) == 0:
                break
        assert sum(svc.state.ships[1].components.values()) == 0  # the loose part was installed


def _inject_species(svc: object, roster_id: str):  # type: ignore[no-untyped-def]
    """Place a friendly roster species in the player's current sector + stock latinum."""
    from dataclasses import replace

    from edge.core.models import AlienSpecies

    sc = svc.config.roster.species_by_id(roster_id)  # type: ignore[attr-defined]
    ship = svc.state.ships[1]  # type: ignore[attr-defined]
    species = AlienSpecies(
        id=1, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id,
        sector_id=ship.sector_id, home_band="Hub", tech_level=sc.tech_level,
        base_disposition=0.9, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
        trade_posture=sc.trade_posture, treaty_mode=sc.treaty_mode, persona=sc.persona,
    )
    svc.state.species[1] = species  # type: ignore[attr-defined]
    svc.state.players[1] = replace(svc.state.players[1], latinum=100_000)  # type: ignore[attr-defined]
    return species


async def test_hail_opens_contact_then_buys_tech() -> None:
    from textual.widgets import Static

    from edge.tui.screens.contact import AlienContactScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "selvani")  # converter (II) latinum offer
        await pilot.press("h")  # hail the species in this sector
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        # The persona-voiced opener renders, and a greyed verb shows its reason.
        assert str(app.screen.query_one("#speech", Static).render())
        verbs = " ".join(str(s.render()) for s in app.screen.query("#verbs Static"))
        assert "(" in verbs and ")" in verbs  # at least one disabled verb shows a reason
        # Click the (available) tech offer → buys it, a loose component lands aboard.
        await pilot.click(app.screen.query(".offer").first())
        await pilot.pause()
        assert sum(svc.state.ships[1].components.values()) == 1


async def test_click_ship_hails_that_specific_species() -> None:
    """Two contacts in the sector: clicking the second ship hails it, not the first."""
    from edge.core.models import AlienSpecies
    from edge.tui.screens.contact import AlienContactScreen
    from edge.tui.widgets import ClickableEntry

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "vesk")  # id 1, the "first" ship (H would hail this one)
        sc2 = svc.config.roster.species_by_id("selvani")
        sector_id = svc.state.ships[1].sector_id
        svc.state.species[2] = AlienSpecies(
            id=2, roster_id="selvani", name=sc2.name, archetype_id=sc2.archetype_id,
            sector_id=sector_id, home_band="Hub", tech_level=sc2.tech_level,
            base_disposition=0.9, disposition_center=sc2.disposition_center,
            disposition_variance=sc2.disposition_variance, alliance_id=sc2.alliance_id,
            trade_posture=sc2.trade_posture, treaty_mode=sc2.treaty_mode, persona=sc2.persona)
        await app.screen.recompose()  # render the now-present ships
        await pilot.pause()
        rows = [e for e in app.screen.query(ClickableEntry) if "vessel" in str(e.render())]
        assert len(rows) == 2  # both contacts show as clickable ships
        await pilot.click(next(e for e in rows if sc2.name in str(e.render())))  # click Selvani
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        met = svc.state.players[1].species_attitudes
        assert 2 in met and 1 not in met  # hailed the clicked ship, not the first


async def test_haggle_session_stays_open_across_a_rejected_round() -> None:
    from textual.widgets import Input

    from edge.tui.screens.haggle import HaggleScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        await pilot.press("h")  # open the multi-round haggle on the highlighted commodity
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)
        # A lowball counter (StarDock sells → the player buys) insults them: the round is
        # spent but the session stays open for another try.
        app.screen.query_one("#haggle-input", Input).value = "1"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)  # not dismissed — multi-round
        assert svc.state.players[1].haggle_attempts  # the spent round was recorded


async def test_computer_dossier_lists_a_met_species() -> None:
    from textual.widgets import DataTable, TabbedContent

    from edge.tui.screens.computer import ComputerScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "vesk")
        await pilot.press("h")  # hail → marks the species met
        await pilot.pause()
        await pilot.press("escape")  # leave contact
        await pilot.pause()
        await pilot.press("c")  # open the computer
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        app.screen.query_one(TabbedContent).active = "dossier"
        await pilot.pause()
        table = app.screen.query_one("#dossier-table", DataTable)
        assert table.row_count == 1
        assert "Vesk" in str(table.get_cell_at((0, 0)))


async def test_continue_focused_and_new_game_confirms_when_save_exists() -> None:
    """With a save present, Continue takes focus and New game asks before clobbering it."""
    from textual.widgets import Button

    from edge.tui.screens.confirm import ConfirmScreen
    from edge.tui.screens.game import GameScreen
    from edge.tui.screens.main_menu import MainMenuScreen

    # First run writes a save into the (isolated) scratch save dir.
    async with EdgeApp().run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

    # Second run: a save now exists.
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)
        assert app.focused is app.screen.query_one("#continue", Button)  # Continue is focused
        # New game asks first; "Keep save" (Esc) returns to the menu, no game started.
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)
        assert app.service is None
        # Confirming overwrites and starts a fresh game.
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert app.service is not None


async def test_continue_reloads_saved_game() -> None:
    """Pressing Continue replays the saved command log back to where the player left off."""
    from edge.tui.screens.game import GameScreen

    app1 = EdgeApp()
    async with app1.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app1.service
        assert svc is not None
        target = svc.state.sectors[1].warps_out[0]
        svc.apply(1, Warp(to_sector=target))  # a durable command in the save's log
        moved = svc.game_view(1).sector.sector_id

    app2 = EdgeApp()
    async with app2.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("c")  # Continue
        await pilot.pause()
        assert isinstance(app2.screen, GameScreen)
        assert app2.service is not None
        assert app2.service.game_view(1).sector.sector_id == moved  # resumed, not reset


async def test_stardock_shipyard_swaps_hull() -> None:
    from dataclasses import replace

    from textual.widgets import TabbedContent

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        svc.state.players[1] = replace(svc.state.players[1], latinum=50_000)  # afford a hull
        app.screen.query_one(TabbedContent).active = "shipyard"
        await pilot.pause()
        await pilot.press("b")  # buy the highlighted hull (Scout Marauder)
        await pilot.pause()
        assert svc.state.ships[1].type_id == "scout_marauder"
        assert svc.state.players[1].latinum < 50_000


async def test_trade_plot_route_and_engage() -> None:
    """WP14: Trade tab → [P] plots the round trip → [G] engages and travels (§11)."""
    from textual.widgets import DataTable, TabbedContent

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert svc.computer_view(1).pairs  # the default seed has a scored pair
        await pilot.press("escape")  # undock back to the game screen
        await pilot.pause()
        await pilot.press("c")  # open the Computer on the Trade tab
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)

        before = svc.state.ships[1].sector_id
        await pilot.press("p")  # plot the highlighted pair's round trip
        await pilot.pause()
        assert app.screen.query_one(TabbedContent).active == "route"
        assert app.screen.query_one("#route-table", DataTable).row_count >= 1

        await pilot.press("g")  # engage
        await pilot.pause()
        assert not isinstance(app.screen, ComputerScreen)  # popped back to the game
        assert svc.state.ships[1].sector_id != before  # advanced off the buy port


async def test_codex_plot_route_to_a_logged_find() -> None:
    """WP14: a logged discovery → Codex [P] routes to the find's sector (§11)."""
    from textual.widgets import DataTable, TabbedContent

    from edge.core.rules import Salvage, Warp

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None

        # Seed the codex: warp to the nearest obvious open-space find and salvage it.
        sensor = svc.state.ships[1].sensor_rating
        diff = svc.config.discovery.sensor_difficulty  # type: ignore[union-attr]
        candidates = []
        for d in svc.state.discoveries.values():
            if d.planet_id is not None:
                continue
            path = shortest_path(svc.state.adjacency, 1, d.sector_id)
            if path is None:
                continue
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

        app.push_screen(ComputerScreen(svc, 1, initial_tab="codex"))
        await pilot.pause()
        await pilot.press("p")  # plot a route to the highlighted find
        await pilot.pause()
        assert app.screen.query_one(TabbedContent).active == "route"
        # The plotted route targets the find's sector and renders its hops.
        assert app.screen._engage_target == disc.sector_id  # type: ignore[attr-defined]
        route = svc.route_view(1, disc.sector_id)
        assert app.screen.query_one("#route-table", DataTable).row_count == len(route.hops)


async def test_ports_directory_lists_and_plots_route() -> None:
    """WP15: Ports tab lists charted ports → [P] plots a route to one (§11)."""
    from textual.widgets import DataTable, TabbedContent

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        directory = svc.computer_view(1).ports
        assert directory  # at least the StarDock is charted
        await pilot.press("escape")  # undock back to the game screen
        await pilot.pause()
        await pilot.press("c")  # open the Computer
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)

        app.screen.query_one(TabbedContent).active = "ports"
        await pilot.pause()
        assert app.screen.query_one("#ports-table", DataTable).row_count == len(directory)

        await pilot.press("p")  # plot a route to the highlighted (nearest) port
        await pilot.pause()
        assert app.screen.query_one(TabbedContent).active == "route"
        assert app.screen._engage_target == directory[0].sector_id  # type: ignore[attr-defined]
