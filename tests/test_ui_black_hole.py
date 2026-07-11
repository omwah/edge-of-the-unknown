"""WP-PR05 — black-hole interaction never crashes (playtest note PT-28).

A black hole deals a flat gravity toll on sector entry (§10, WP41). The playtest
found that entering one — the "click" being the warp into its sector — could crash
the game as the damage was applied and the screen refreshed, for both a nonlethal
toll and a lethal one (which routes the captain through the WP26 escape pod). The
core lethal-hazard path was closed with the WP26/WP75 escape pod; these tests lock
down the TUI flow so the click → damage → refresh sequence can never regress.

They drive the *real* app: a black hole is placed in a neighbouring sector, and the
player warps in through both the mouse (nav-rose click) and the keyboard (Enter on
the focused node). Both inputs must behave identically — survive the refresh, report
the hull damage in the event ticker, and leave a coherent, re-renderable game screen
— nonlethal and lethal alike, and again on a repeat interaction with the hazard now
sitting in the current sector.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.enums import DiscoveryKind, PayloadKind, RarityTier
from edge.core.events import HazardDamage
from edge.core.models import Discovery, DiscoveryPayload
from edge.core.movement import shortest_path
from edge.core.rules import Warp
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import state_hash
from edge.tui.app import EdgeApp
from edge.tui.screens.game import GameScreen
from edge.tui.widgets import NavRose

_CFG = load_default_config()
_POD = _CFG.combat.escape_pod_class


def _put_black_hole(svc: object, sector_id: int) -> int:
    """Drop a black hole into `sector_id`; return its discovery id."""
    state = svc.state  # type: ignore[attr-defined]
    did = (max(state.discoveries) + 1) if state.discoveries else 1
    state.discoveries[did] = Discovery(
        id=did, kind=DiscoveryKind.BLACK_HOLE, rarity_tier=RarityTier.RARE,
        sector_id=sector_id, payload=DiscoveryPayload(kind=PayloadKind.LORE, lore="a maw"))
    return did


def _ship(svc: object):
    state = svc.state  # type: ignore[attr-defined]
    return state.ships[state.players[1].ship_id]


def _set_hull(svc: object, hull: int) -> None:
    state = svc.state  # type: ignore[attr-defined]
    ship = _ship(svc)
    state.ships[ship.id] = replace(ship, hull_current=hull)


def _hazard_logged(screen: GameScreen) -> bool:
    return any("hull damage" in line.lower() or "gravity shear" in line.lower()
               for line in screen._log)  # type: ignore[attr-defined]


async def _new_game(app: EdgeApp, pilot: object) -> object:
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    return svc


@pytest.mark.parametrize("input_kind", ["mouse", "keyboard"])
@pytest.mark.parametrize("lethal", [False, True])
async def test_warp_into_black_hole_never_crashes(input_kind: str, lethal: bool) -> None:
    """The full 2x2 acceptance matrix: mouse/keyboard x nonlethal/lethal, identical."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game(app, pilot)
        screen = app.screen
        assert isinstance(screen, GameScreen)
        start = svc.game_view(1).sector.sector_id  # type: ignore[attr-defined]
        rose = screen.query_one(NavRose)
        node = rose._hits[rose._idx if input_kind == "keyboard" else 0]
        target = node.sector_id
        _put_black_hole(svc, target)
        if lethal:
            _set_hull(svc, 5)  # below the gravity toll
        before = _ship(svc).hull_current

        if input_kind == "mouse":
            compass = rose.query_one("#rose-compass")
            await pilot.click(compass, offset=(node.col0, node.row))
        else:
            assert isinstance(app.focused, NavRose)  # the rose auto-focuses
            await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        moved = svc.game_view(1).sector.sector_id  # type: ignore[attr-defined]
        ship = _ship(svc)
        assert moved == target != start
        assert isinstance(app.screen, GameScreen)  # no crash, screen re-rendered
        assert _hazard_logged(app.screen)  # the toll is reported, not swallowed
        if lethal:
            assert ship.type_id == _POD  # routed through the escape pod
        else:
            assert ship.hull_current < before  # nonlethal toll landed on the hull


async def test_repeated_interaction_with_current_sector_black_hole_is_safe() -> None:
    """After entering, the black hole sits in the current sector; logging it (the
    sidebar/Z action) must not crash nor re-apply the one-time entry toll."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game(app, pilot)
        screen = app.screen
        assert isinstance(screen, GameScreen)
        rose = screen.query_one(NavRose)
        node = rose._hits[0]
        target = node.sector_id
        did = _put_black_hole(svc, target)
        compass = rose.query_one("#rose-compass")
        await pilot.click(compass, offset=(node.col0, node.row))
        await pilot.pause()
        hull_after_entry = _ship(svc).hull_current
        # Log the phenomenon into the codex — codex-only, no toll re-applied.
        await app.screen._salvage(did)  # type: ignore[attr-defined]
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert _ship(svc).hull_current == hull_after_entry


def test_black_hole_damage_survives_save_and_reload(tmp_path) -> None:
    """The gravity toll rides the command log: a save→reload (replay) after a black-hole
    entry reconstructs the exact state (WP-PR05 acceptance — save/autosave after damage).

    Uses a *generated* black hole (not an injected one) so the recorded `Warp` replays it —
    an injected discovery would vanish on regeneration and could not round-trip.
    """
    db = tmp_path / "bh.db"
    svc = GameService.new_game(_CFG, 4, SqliteRepository(db))  # seed 4 places black holes
    state = svc.state
    ship = state.ships[state.players[1].ship_id]
    # Nearest open-space black hole, and a route to it.
    dist = {d.sector_id: shortest_path(state.adjacency, ship.sector_id, d.sector_id)
            for d in state.discoveries.values()
            if d.kind is DiscoveryKind.BLACK_HOLE and d.planet_id is None}
    target, path = min(((s, p) for s, p in dist.items() if p is not None),
                       key=lambda kv: len(kv[1]))
    took_toll = False
    for hop in path[1:]:
        events = svc.apply(1, Warp(to_sector=hop))
        took_toll = took_toll or any(
            isinstance(e, HazardDamage) and e.source == "black_hole" for e in events)
    assert took_toll  # the route actually crossed the hole and applied the gravity toll

    expected = state_hash(svc.state)
    reloaded = GameService.load_game(_CFG, SqliteRepository(db))  # replays the command log
    assert state_hash(reloaded.state) == expected
