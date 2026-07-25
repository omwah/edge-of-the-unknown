"""GW-WP07 — fog-safe expedition DTO, client parity, and live Textual flow."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets._footer import FooterKey

from edge.config import load_default_config
from edge.core.enums import DiscoveryKind, PayloadKind, RarityTier
from edge.core.groundwar import survey as gw
from edge.core.models import (
    Discovery,
    DiscoveryPayload,
    Game,
    Ownership,
    Planet,
    Player,
    Region,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.movement import MovementError
from edge.core.rules import (
    BeginSurvey,
    GroundMove,
    SurveyDig,
    SurveyLand,
    apply_result,
    reduce,
)
from edge.server import session, wire
from edge.server.client import LocalClient, RemoteClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.app import EdgeApp
from edge.tui.screens.ground_expedition import GroundExpeditionScreen, SurveyMapView


CFG = load_default_config()


def _world(*, sites: int = 2) -> UniverseState:
    state = UniverseState.new(Game(1, 91, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.regions = {1: Region(1, "Frontier")}
    state.rebuild_adjacency()
    state.planets = {
        1: Planet(
            1, 1, "Morrow", "terrestrial_warm", habitability_cap=1_000,
            owner=Ownership("none"),
        )
    }
    state.ships = {
        1: Ship(
            id=1, type_id="trailblazer", name="S", owner_player_id=1,
            sector_id=1, holds_total=60, turns_per_warp=1, sensor_rating=9,
        )
    }
    state.players = {
        1: Player(id=1, name="you", ship_id=1, latinum=100, turns_remaining=250)
    }
    state.discoveries = {
        10 + i: Discovery(
            id=10 + i,
            kind=DiscoveryKind.RUINS,
            rarity_tier=RarityTier.RARE,
            sector_id=1,
            payload=DiscoveryPayload(
                kind=PayloadKind.ARTIFACT, barter_tier="II", lore=f"lore-{i}"
            ),
            planet_id=1,
            site_slot=i,
            hidden=False,
            name=f"Buried Site {i}",
        )
        for i in range(sites)
    }
    apply_result(state, reduce(state, 1, BeginSurvey(1), CFG))
    return state



def _landed(state: UniverseState, x: int | None = None, y: int | None = None) -> UniverseState:
    """Put the survey on the ground at `(x, y)`, defaulting to the map centre.

    The pre-drop-site starting condition, for the tests that are about viewport, keys, and
    excavation rather than about choosing a drop site.
    """
    op = state.players[1].ground_operation
    assert op is not None
    exp = CFG.groundwar.expedition  # type: ignore[union-attr]
    state.players[1] = replace(
        state.players[1],
        ground_operation=replace(
            op, landed=True,
            explorer_x=exp.width // 2 if x is None else x,
            explorer_y=exp.height // 2 if y is None else y,
        ),
    )
    return state


def test_view_is_cropped_and_masks_unresolved_site_identity() -> None:
    state = _world(sites=2)
    op = state.players[1].ground_operation
    assert op is not None
    # Simulate the begin snapshot excluding one sensor-ineligible discovery: projection must
    # not recover it by scanning live universe records (G7).
    state.players[1] = replace(
        state.players[1], ground_operation=replace(op, visible_discovery_ids=frozenset({10}))
    )

    view = session.ground_operation_view(
        state, 1, CFG, viewport_x=3, viewport_y=4, viewport_width=11, viewport_height=7
    )
    assert view is not None
    assert (view.viewport_x, view.viewport_y, view.viewport_width, view.viewport_height) == (
        3, 4, 11, 7,
    )
    assert len(view.cells) == 77
    assert all(3 <= cell.x < 14 and 4 <= cell.y < 11 for cell in view.cells)
    assert len(view.contacts) == 1
    contact = view.contacts[0]
    assert (contact.discovery_id, contact.name, contact.kind, contact.rarity) == (0, "", "", "")
    assert not any(cell.found_contact_id for cell in view.cells)
    assert not hasattr(view, "seed")


def test_viewport_pans_reuse_the_generated_survey_map(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _world()
    session._SURVEY_MAP_CACHE.clear()
    generated = 0
    original = gw.survey_map_for

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal generated
        generated += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(gw, "survey_map_for", counted)
    for viewport_x in (0, 8, 16, 24):
        assert session.ground_operation_view(
            state, 1, CFG, viewport_x=viewport_x,
            viewport_width=66, viewport_height=25,
        ) is not None
    assert generated == 1


def test_excavation_reveals_only_the_settled_contact_and_marker() -> None:
    state = _world(sites=2)
    op = state.players[1].ground_operation
    assert op is not None
    site = gw.survey_map_for(state, op, CFG).sites[0]
    _landed(state, site.x, site.y)
    apply_result(state, reduce(state, 1, SurveyDig(op.operation_id), CFG))

    view = session.ground_operation_view(state, 1, CFG)
    assert view is not None
    found = next(contact for contact in view.contacts if contact.found)
    assert found.discovery_id == site.discovery_id
    assert found.name == site.name and found.kind == "ruins" and found.rarity == "RARE"
    marker = next(cell for cell in view.cells if cell.found_contact_id == found.contact_id)
    assert (marker.x, marker.y) == (site.x, site.y)
    unresolved = [contact for contact in view.contacts if not contact.found]
    assert all(contact.discovery_id == 0 and not contact.name for contact in unresolved)


async def test_local_client_and_wire_round_trip_match_service(tmp_path: Path) -> None:
    state = _world()
    service = GameService(state, CFG, SqliteRepository(tmp_path / "survey.db"))
    client = LocalClient(service)
    expected = service.ground_operation_view(
        1, viewport_x=5, viewport_y=2, viewport_width=17, viewport_height=9
    )
    actual = await client.ground_operation_view(
        viewport_x=5, viewport_y=2, viewport_width=17, viewport_height=9
    )
    assert actual == expected
    assert actual is not None
    assert wire.decode_dto(wire.encode_dto(actual)) == actual


async def test_remote_client_decodes_the_same_cropped_view() -> None:
    state = _world()
    expected = session.ground_operation_view(
        state, 1, CFG, viewport_x=9, viewport_y=6, viewport_width=13, viewport_height=8
    )
    assert expected is not None
    remote = RemoteClient("ws://unused")

    async def fake_call(method: str, params: dict[str, object]) -> object:
        assert method == "ground_operation_view"
        assert params == {
            "viewport_x": 9, "viewport_y": 6,
            "viewport_width": 13, "viewport_height": 8,
        }
        return wire.encode_dto(expected)

    remote._call = fake_call  # type: ignore[method-assign]
    assert await remote.ground_operation_view(
        viewport_x=9, viewport_y=6, viewport_width=13, viewport_height=8
    ) == expected


async def test_textual_keyboard_mouse_and_extract_flow(tmp_path: Path) -> None:
    state = _landed(_world())  # cursor/pan mechanics, not drop-site selection
    service = GameService(state, CFG, SqliteRepository(tmp_path / "pilot.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GroundExpeditionScreen(client))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GroundExpeditionScreen)
        start_cursor = (screen.cursor_x, screen.cursor_y)
        await pilot.press("right")
        await pilot.pause()
        assert (screen.cursor_x, screen.cursor_y) != start_cursor

        before_pan = (screen.camera_x, screen.camera_y, screen.cursor_x, screen.cursor_y)
        await pilot.press("d")
        await pilot.pause()
        assert screen.camera_x == before_pan[0] + 8
        assert screen.cursor_x == before_pan[2] + 8

        map_widget = screen.query_one(SurveyMapView)
        assert screen.view is not None
        clicked = screen.view.viewport_x + 2, screen.view.viewport_y + 2
        await pilot.click(map_widget, offset=(2, 2))
        await pilot.pause()
        assert (screen.cursor_x, screen.cursor_y) == clicked

        await pilot.press("escape")
        await pilot.pause()
        assert state.players[1].ground_operation is None
        assert not isinstance(app.screen, GroundExpeditionScreen)


async def test_excavation_keeps_the_same_map_and_viewport(tmp_path: Path) -> None:
    state = _world(sites=2)
    op = state.players[1].ground_operation
    assert op is not None
    site = gw.survey_map_for(state, op, CFG).sites[0]
    _landed(state, site.x, site.y)
    service = GameService(state, CFG, SqliteRepository(tmp_path / "excavate.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        screen = GroundExpeditionScreen(client)
        app.push_screen(screen)
        await pilot.pause()
        assert screen.view is not None
        assert not screen.view.is_cloud_city
        x_key = next(k for k in screen.query(FooterKey) if k.key == "x")
        assert x_key.description == "Dig"
        before = screen.view
        before_size = screen.query_one(SurveyMapView).size
        before_render = screen.query_one(SurveyMapView).render().plain.splitlines()
        before_camera = screen.camera_x, screen.camera_y
        before_features = {(cell.x, cell.y): cell.feature for cell in before.cells}
        before_overlays = {
            (cell.x, cell.y): (cell.heat, cell.clue)
            for cell in before.cells
        }
        before_ring_cells = sum(bool(cell.search_ring) for cell in before.cells)

        await pilot.press("x")
        await pilot.pause()
        assert not isinstance(app.screen, GroundExpeditionScreen)
        await pilot.press("escape")
        await pilot.pause()

        assert app.screen is screen
        assert screen.view is not None
        after = screen.view
        assert screen.query_one(SurveyMapView).size == before_size
        after_render = screen.query_one(SurveyMapView).render().plain.splitlines()
        assert len(after_render) == len(before_render)
        assert [len(line) for line in after_render] == [len(line) for line in before_render]
        assert (screen.camera_x, screen.camera_y) == before_camera
        assert (after.viewport_x, after.viewport_y) == (before.viewport_x, before.viewport_y)
        assert (after.viewport_width, after.viewport_height) == (
            before.viewport_width, before.viewport_height)
        assert {(cell.x, cell.y): cell.feature for cell in after.cells} == before_features
        assert {
            (cell.x, cell.y): (cell.heat, cell.clue)
            for cell in after.cells
        } == before_overlays
        assert sum(bool(cell.search_ring) for cell in after.cells) < before_ring_cells


async def test_game_screen_resumes_an_active_survey(tmp_path: Path) -> None:
    """A loaded/reconnected session cannot strand the player behind the G9 blocker."""
    from edge.tui.screens.game import GameScreen

    state = _world()
    service = GameService(state, CFG, SqliteRepository(tmp_path / "resume.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        app.push_screen(GameScreen(service, 1))
        await pilot.pause()
        assert isinstance(app.screen, GroundExpeditionScreen)
        assert app.screen.view is not None
        assert app.screen.view.operation_id == state.players[1].ground_operation.operation_id  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("label", "size"),
    (("compact", (80, 24)), ("standard", (100, 34)), ("wide", (140, 42))),
    ids=("compact", "standard", "wide"),
)
def test_expedition_responsive_snapshots(
    snap_compare: object, tmp_path: Path, label: str, size: tuple[int, int]
) -> None:
    state = _world()
    service = GameService(state, CFG, SqliteRepository(tmp_path / f"{label}.db"))
    client = LocalClient(service)

    async def open_expedition(pilot: object) -> None:
        pilot.app.client = client  # type: ignore[attr-defined]
        pilot.app.push_screen(GroundExpeditionScreen(client))  # type: ignore[attr-defined]
        await pilot.pause()  # type: ignore[attr-defined]

    assert snap_compare(  # type: ignore[operator]
        EdgeApp(plain=True), terminal_size=size, run_before=open_expedition
    )


# --- GW-WP07-FU1 presentation fields ---------------------------------------------


def _inhabited_view() -> object:
    """A live survey reprojected against a peopled world, so towns exist."""
    state = _world()
    state.planets[1] = replace(state.planets[1], population={"terran": 50_000})
    return session.ground_operation_view(state, 1, CFG)


def test_town_gates_project_as_walkable_breaks_in_the_wall() -> None:
    view = _inhabited_view()
    assert view is not None
    gates = [cell for cell in view.cells if cell.gate]
    # `_stamp_settlement` leaves one mid-edge gate per side of every town.
    assert len(gates) == 4 * len(view.settlements)
    # A gate the client paints as a doorway must actually be enterable.
    assert not any(cell.blocked for cell in gates)


def test_settlement_projects_its_real_plaza_and_hint_offer() -> None:
    view = _inhabited_view()
    assert view is not None
    assert view.settlements
    by_cell = {(cell.x, cell.y): cell for cell in view.cells}
    for town in view.settlements:
        plaza = by_cell[(town.plaza_x, town.plaza_y)]
        assert plaza.settlement_id == town.settlement_id
        assert not plaza.blocked  # the plaza is the open centre, never masonry
    # Nothing has been hinted yet, so talking is still worth a circle.
    assert all(town.hint_available for town in view.settlements)


def test_hint_offer_closes_once_every_contact_is_hinted() -> None:
    state = _world(sites=2)
    state.planets[1] = replace(state.planets[1], population={"terran": 50_000})
    op = state.players[1].ground_operation
    assert op is not None
    state.players[1] = replace(
        state.players[1],
        ground_operation=replace(op, hinted_discovery_ids=frozenset({10, 11})),
    )
    view = session.ground_operation_view(state, 1, CFG)
    assert view is not None
    assert view.settlements
    assert not any(town.hint_available for town in view.settlements)


def test_scanner_band_matches_the_authored_reading() -> None:
    state = _world()
    view = session.ground_operation_view(state, 1, CFG)
    assert view is not None
    bands = CFG.groundwar.expedition.scanner  # type: ignore[union-attr]
    assert 1 <= view.scanner_band <= len(bands)
    # The band ordinal is the index of the very label the reading reports.
    assert bands[view.scanner_band - 1].label == view.scanner


def test_terrain_glyphs_follow_the_authored_weights() -> None:
    """Foliage reads as foliage only if the blank-weighted entries survive.

    The old renderer took the first non-space glyph for a feature and used it for every
    cell, so a forest painted as a solid wall of one glyph and its clearings (40 of the
    feature's 89 authored parts) vanished.
    """
    from edge.art.terrain import FEATURES_REGISTRY
    from edge.tui.screens.ground_expedition import _feature_glyph

    drawn = Counter(_feature_glyph(1, "forest", x, y) for y in range(60) for x in range(60))
    authored = dict(FEATURES_REGISTRY["forest"])
    total = sum(authored.values())
    assert drawn[" "] / 3600 == pytest.approx(authored[" "] / total, abs=0.03)
    assert set(drawn) == set(authored)  # every authored glyph is reachable


def test_terrain_glyphs_are_stable_and_positional() -> None:
    from edge.tui.screens.ground_expedition import _feature_glyph

    # Stable: the same cell renders identically every call (and, via crc32 rather than
    # a salted hash(), across processes — which the snapshot tests rely on).
    assert _feature_glyph(1, "forest", 7, 9) == _feature_glyph(1, "forest", 7, 9)
    # Positional: a feature is not one fixed glyph everywhere.
    assert len({_feature_glyph(1, "forest", x, 0) for x in range(60)}) > 1
    # Per-planet: two worlds of the same type do not share a texture.
    assert any(_feature_glyph(1, "forest", x, 0) != _feature_glyph(2, "forest", x, 0)
               for x in range(60))


def test_terrain_stays_legible_under_every_overlay_backdrop() -> None:
    """Overlays repaint the backdrop, so contrast must be re-checked against it.

    Correcting the foreground against the terrain's own background and then swapping
    that background for an overlay's defeated the correction: `water_deep` on the
    `dark_orange3` scanner band measured a 0.002 luminance gap — an invisible glyph, on
    the overlay that is on by default.
    """
    from rich.color import Color

    from edge.art.terrain import BIOME_COLORS, _luminance
    from edge.core.groundwar.terrain import BIOME_BANDS
    from edge.tui.screens.ground_expedition import _HEAT, _feature_colors, _styled

    def luminance(color: str) -> float:
        rgb = Color.parse(color).get_truecolor()
        return _luminance((rgb.red / 255, rgb.green / 255, rgb.blue / 255))

    backdrops = ["dark_green", "grey35", "grey27", *(h for h in _HEAT if h)]
    for ptype, layout in BIOME_BANDS.items():
        colors = BIOME_COLORS.get(ptype, [])
        for index, (_threshold, feature) in enumerate(layout.bands):
            if index >= len(colors):
                continue
            fg, terrain_bg = _feature_colors(ptype, feature)
            for bg in [*backdrops, terrain_bg]:
                if not bg:
                    continue
                rendered_fg = _styled(fg, bg).split(" on ")[0]
                assert luminance(rendered_fg) != pytest.approx(luminance(bg), abs=0.15), (
                    f"{ptype}/{feature} is unreadable on {bg}"
                )


def test_terrain_styles_pin_concrete_colours_not_theme_names() -> None:
    """Named ANSI colours are theme-dependent, so contrast math on the nominal palette
    does not describe what the terminal paints.

    `terrestrial_cool` forest is authored `bright_green` on `green`: the nominal gap
    clears the correction threshold, but a terminal theme renders the pair as one colour
    and the trees vanish until the cursor lands on them. Emitting truecolor keeps the
    measured contrast and the rendered contrast the same thing.
    """
    from edge.art.terrain import BIOME_COLORS
    from edge.core.groundwar.terrain import BIOME_BANDS
    from edge.tui.screens.ground_expedition import _feature_colors, _styled

    for ptype, layout in BIOME_BANDS.items():
        colors = BIOME_COLORS.get(ptype, [])
        for index, (_threshold, feature) in enumerate(layout.bands):
            if index >= len(colors):
                continue
            fg, bg = _feature_colors(ptype, feature)
            for part in _styled(fg, bg).split(" on "):
                assert part.startswith("#"), f"{ptype}/{feature} emits themeable {part!r}"

    # The reported case: forest must not render as its own background.
    fg, bg = _feature_colors("terrestrial_cool", "forest")
    rendered_fg, rendered_bg = _styled(fg, bg).split(" on ")
    assert rendered_fg != rendered_bg


# --- GW-WP07-FU2 player-chosen drop site -----------------------------------------


def test_drop_zone_excludes_unsafe_terrain_and_unreachable_ground() -> None:
    """The reported bug: the explorer was placed at the map centre regardless of terrain,
    so a descent could start in water or on an island away from every contact."""
    state = _world(sites=3)
    op = state.players[1].ground_operation
    assert op is not None
    smap = gw.survey_map_for(state, op, CFG)
    drops = gw.landing_sites(smap, CFG)
    assert drops

    blocked = set(CFG.groundwar.expedition.landing_blocked_features)  # type: ignore[union-attr]
    assert blocked, "the fixture config must actually name unsafe terrain"
    assert not any(smap.feature[y][x] in blocked for x, y in drops)

    # Every contact stays reachable on foot from the extremes of the drop zone.
    for probe in (min(drops), max(drops)):
        for site in smap.sites:
            assert gw.path_to(smap, CFG, probe[0], probe[1], site.x, site.y) is not None


def test_survey_begins_inbound_and_actions_wait_for_touchdown() -> None:
    state = _world()
    op = state.players[1].ground_operation
    assert op is not None and not op.landed

    view = session.ground_operation_view(state, 1, CFG)
    assert view is not None
    assert view.can_land and not view.landed
    assert not (view.can_move or view.can_dig or view.can_talk)
    assert view.can_extract, "aborting before touchdown must stay legal"
    # The suggested rest for the cursor is itself a legal drop site.
    assert (view.suggested_landing_x, view.suggested_landing_y) in gw.landing_sites(
        gw.survey_map_for(state, op, CFG), CFG)

    with pytest.raises(MovementError):
        reduce(state, 1, GroundMove(op.operation_id, 20, 20), CFG)


def test_landing_validates_the_chosen_cell_and_happens_once() -> None:
    state = _world()
    op = state.players[1].ground_operation
    assert op is not None
    smap = gw.survey_map_for(state, op, CFG)
    drops = gw.landing_sites(smap, CFG)
    illegal = next((x, y) for y in range(smap.height) for x in range(smap.width)
                   if (x, y) not in drops)

    with pytest.raises(MovementError):
        reduce(state, 1, SurveyLand(op.operation_id, *illegal), CFG)

    chosen = max(drops)  # deliberately not the generated landing zone
    apply_result(state, reduce(state, 1, SurveyLand(op.operation_id, *chosen), CFG))
    landed_op = state.players[1].ground_operation
    assert landed_op is not None
    assert landed_op.landed and (landed_op.explorer_x, landed_op.explorer_y) == chosen

    with pytest.raises(MovementError):
        reduce(state, 1, SurveyLand(op.operation_id, *chosen), CFG)

    view = session.ground_operation_view(state, 1, CFG)
    assert view is not None
    assert view.landed and not view.can_land and view.can_move
    # The drop zone is only advertised while inbound.
    assert not any(cell.landing_site for cell in view.cells)


def test_inbound_view_keeps_terrain_colour_and_dims_only_refused_ground() -> None:
    """Choosing a drop site means reading terrain, so terrain must keep its own colours.

    An earlier pass washed every landable cell with a flat grey, which covered more than
    half the map and hid the biome detail the choice depends on. Legal ground now renders
    exactly as it does once landed; only refused ground recedes.
    """
    from rich.color import Color

    from edge.art.terrain import BIOME_COLORS, _luminance
    from edge.core.groundwar.terrain import BIOME_BANDS
    from edge.tui.screens.ground_expedition import (
        _feature_colors,
        _styled,
        _styled_excluded,
    )

    def luminance(color: str) -> float:
        rgb = Color.parse(color).get_truecolor()
        return _luminance((rgb.red / 255, rgb.green / 255, rgb.blue / 255))

    for ptype, layout in BIOME_BANDS.items():
        colors = BIOME_COLORS.get(ptype, [])
        for index, (_threshold, feature) in enumerate(layout.bands):
            if index >= len(colors):
                continue
            fg, bg = _feature_colors(ptype, feature)
            normal, excluded = _styled(fg, bg), _styled_excluded(fg, bg)
            assert excluded != normal, f"{ptype}/{feature} does not recede when refused"
            # Refused ground still has to be readable — dimming fg and bg by different
            # amounts collapsed `sand` (fg darker than bg) to a 0.063 gap before the
            # post-dim contrast correction.
            front, back = excluded.split(" on ")
            assert luminance(front) != pytest.approx(luminance(back), abs=0.15), (
                f"{ptype}/{feature} is unreadable when dimmed")


# --- GW-WP18: Cloud City tour crates, end to end -----------------------------

_CRATE_CFG = CFG.model_copy(update={"groundwar": CFG.groundwar.model_copy(  # type: ignore[union-attr]
    update={"cloud_city": CFG.groundwar.cloud_city.model_copy(  # type: ignore[union-attr]
        update={"crate_chance": 1.0})})})


def _cloud_city_world() -> UniverseState:
    """A player-owned, staged Cloud City with the tour already open — `crate_chance`
    forced to 1.0 so a crate is guaranteed, mirroring `_world`'s terrestrial setup."""
    state = UniverseState.new(Game(1, 91, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.regions = {1: Region(1, "Frontier")}
    state.rebuild_adjacency()
    state.planets = {
        1: Planet(1, 1, "Sky Reach", "jovian", cloud_city_size=3,
                  owner=Ownership("player", 1)),
    }
    state.ships = {
        1: Ship(id=1, type_id="trailblazer", name="S", owner_player_id=1,
               sector_id=1, holds_total=60, turns_per_warp=1),
    }
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=100, turns_remaining=250)}
    apply_result(state, reduce(state, 1, BeginSurvey(1), _CRATE_CFG))
    return state


def _landed_on_a_crate(state: UniverseState) -> object:
    """Land the tour directly on its (guaranteed) first crate; returns that crate."""
    op = state.players[1].ground_operation
    assert op is not None
    crate = gw.survey_map_for(state, op, _CRATE_CFG).crates[0]
    state.players[1] = replace(
        state.players[1],
        ground_operation=replace(op, landed=True, explorer_x=crate.x, explorer_y=crate.y),
    )
    return crate


def test_cloud_city_view_projects_crates_and_is_cloud_city_flag() -> None:
    state = _cloud_city_world()
    crate = _landed_on_a_crate(state)
    view = session.ground_operation_view(state, 1, _CRATE_CFG)
    assert view is not None
    assert view.is_cloud_city is True
    assert any(c.crate_id == crate.id and not c.opened for c in view.crates)
    marker = next(cell for cell in view.cells if cell.crate_id == crate.id)
    assert (marker.x, marker.y) == (crate.x, crate.y)


async def test_cloud_city_tour_open_crate_via_pilot(tmp_path: Path) -> None:
    """`X` opens the crate underfoot instead of digging, no modal pushed (unlike a
    real excavation), and the sidebar/DTO reflect the reward in place."""
    state = _cloud_city_world()
    crate = _landed_on_a_crate(state)
    service = GameService(state, _CRATE_CFG, SqliteRepository(tmp_path / "crate.db"))
    client = LocalClient(service)
    app = EdgeApp(plain=True)

    async with app.run_test(size=(100, 34)) as pilot:
        app.client = client
        screen = GroundExpeditionScreen(client)
        app.push_screen(screen)
        await pilot.pause()
        assert screen.view is not None
        assert screen.view.is_cloud_city
        # A Cloud City tour opens crates, not trenches — the footer should say so.
        x_key = next(k for k in screen.query(FooterKey) if k.key == "x")
        assert x_key.description == "Open"
        before_components = sum(state.ships[1].components.values())

        await pilot.press("x")
        await pilot.pause()

        assert isinstance(app.screen, GroundExpeditionScreen)  # no find modal for a crate
        assert screen.view is not None
        opened = next(c for c in screen.view.crates if c.crate_id == crate.id)
        assert opened.opened
        assert sum(state.ships[1].components.values()) == before_components + 1
        op = state.players[1].ground_operation
        assert op is not None and crate.id in op.opened_crate_ids  # type: ignore[union-attr]

        # Re-pressing X on the now-empty crate is a no-op refusal, not a second reward.
        await pilot.press("x")
        await pilot.pause()
        assert sum(state.ships[1].components.values()) == before_components + 1
