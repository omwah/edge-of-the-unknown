"""PT-42 — art panels must not reset, and screens must not resize, just after they open.

Three distinct causes, three fixes:

- The **contact screen** rebuilt itself on every reply (pop + push), so the portrait — a
  chafa render — was torn down and remounted at each step of a conversation. It now
  repaints the speech and reply menu *in place* and leaves the portrait mounted. Pinned in
  tests/test_tui_flow.py::test_a_reply_repaints_the_menu_without_rebuilding_the_portrait.
- The **station screens** (Stardock, Port, Starbase) genuinely do rebuild after an action,
  and each art panel came back as a *new* widget that opened on a text fallback and only
  swapped in the image from `on_mount` — so the art visibly reset each time. They now open
  on the art they last drew (`edge.tui.art_memory`), making the swap invisible.

- **Every pushed screen** was laid out once with *untiered* CSS and then again a frame
  later, because the responsive tier class was stamped on it via `call_after_refresh`.
  That second layout is what the player sees as a screen resizing itself just after it
  opens — panels snapping to a new width, art re-rendering at a new size. The class is now
  stamped **synchronously**, before the new screen's first layout.

The expensive part (chafa) was already memoised in `edge.art.portrait`; what was missing
was the *frame*.
"""

from __future__ import annotations

from dataclasses import replace

from rich.text import Text

from edge.core.movement import shortest_path
from edge.core.rules import Warp
from edge.tui import art_memory
from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot


# --- art_memory: a paint-time smoother, never the source of truth ------------------


def test_remembered_is_none_until_something_is_drawn() -> None:
    assert art_memory.remembered(("never", "drawn")) is None


def test_remember_hands_back_copies_so_callers_may_stylize() -> None:
    """Rich `Text` is mutable and callers `stylize()` it (a derelict base dims its icon),
    so a shared cache must never hand out the object it is holding."""
    key = ("test", "copy")
    art_memory.remember(key, Text("hull"))

    first = art_memory.remembered(key)
    assert first is not None
    first.stylize("dim")  # a caller mutating what it was given…

    second = art_memory.remembered(key)
    assert second is not None
    assert second.spans == []  # …must not corrupt the next reader
    assert str(second) == "hull"


# --- the station panels open on the art they last drew ----------------------------


async def _dock(app: EdgeApp, pilot: object) -> object:
    clear_slot()
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    start = svc.game_view(1).sector.sector_id
    for hop in (shortest_path(svc.state.adjacency, start, dock.sector_id) or [])[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.state.players[1] = replace(svc.state.players[1], latinum=200_000)
    await pilot.press("p")  # dock  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return svc


async def test_a_purchase_does_not_reset_the_stardock_banner() -> None:
    """A purchase rebuilds the Stardock, so its banner is a brand-new widget. That widget
    must paint the art from its very first frame — it used to open on the ASCII fallback
    and swap the image in from `on_mount`, which is the reset the player saw."""
    from edge.tui.screens.stardock import (
        _CONCOURSE_ART, _StardockServiceArt, StardockScreen,
    )

    app = EdgeApp()
    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        assert isinstance(app.screen, StardockScreen)

        await pilot.press("h")  # → Hardware; its banner renders
        await pilot.pause()
        drawn = str(app.screen.query_one(_StardockServiceArt).render())
        assert "ORBITAL CONCOURSE" not in drawn, "the banner never rendered its image"

        await pilot.press("p")  # purchase → the screen is rebuilt
        await pilot.pause()
        assert sum(svc.state.ships[1].components.values()) == 1  # type: ignore[attr-defined]

        # The rebuilt screen's banner is a different widget than before…
        assert isinstance(app.screen, StardockScreen)
        # …and a panel constructed now — at this tier and theme, which is what the screen
        # hands its panels — opens straight on the remembered art, so the rebuild is
        # invisible rather than a flash of the fallback.
        cinematic = app.layout_tier.value == "wide"
        fresh = _StardockServiceArt("hardware", cinematic, str(app.theme))
        opening = str(fresh.render())
        assert "ORBITAL CONCOURSE" not in opening
        assert opening.strip() and _CONCOURSE_ART not in opening


async def test_station_art_header_opens_on_remembered_art() -> None:
    """The same guarantee for the shared port/starbase header (`_StationArt`), which the
    Port and Base screens use — they rebuild after an action too."""
    from edge.tui.station_art import _FALLBACK, _StationArt

    app = EdgeApp()
    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        cinematic = app.layout_tier.value == "wide"
        theme = str(app.theme)
        art = _StationArt("port", "humanoid_diplomat", "trade", "open",
                          icon=False, identity=7, cinematic=cinematic, theme=theme)
        await app.mount(art)
        await pilot.pause()
        drawn = str(art.render())
        if _FALLBACK in drawn:  # no chafa binding in this environment — nothing to pin
            return

        fresh = _StationArt("port", "humanoid_diplomat", "trade", "open",
                            icon=False, identity=7, cinematic=cinematic, theme=theme)
        assert str(fresh.render()) == drawn, "a rebuilt header did not open on its art"


# --- a screen is laid out *with* its tier class, not re-laid-out a frame later --------


async def test_a_pushed_screen_opens_at_its_final_size() -> None:
    """The tier class must be on a screen before its first layout.

    It used to be stamped with `call_after_refresh`, so a pushed screen laid out once
    under untiered CSS and then a second time once the class landed — visibly resizing
    just after opening (worst on modals and the dialogue screen, whose panels are
    tier-scoped). Asserted with no `pause()` between the push and the check: the class has
    to be there already.
    """
    from edge.tui.screens.rumor import RumorModal

    app = EdgeApp()
    async with app.run_test(size=(110, 36)) as pilot:
        await pilot.pause()
        tier = app.layout_tier.value
        assert app.screen.has_class(tier)  # the resting screen, too

        modal = RumorModal("a trail leads coreward")
        app.push_screen(modal)
        assert modal.has_class(tier), (
            "a pushed screen had no tier class until after a refresh — it will lay out "
            "twice and visibly resize")
        await pilot.pause()  # let it finish mounting, then close it
        await pilot.press("escape")
        await pilot.pause()
