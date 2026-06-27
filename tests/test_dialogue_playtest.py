"""Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/authoring).

Covers the non-UI `PlaytestService` (synthetic cast, band/standing dials, force-enable, recency
advance, intel) and a Textual Pilot flow over `PlaytestApp` (controls modal + the shared contact
screen's Backspace backtracking). The harness reuses the *real* `session.contact_view`, so these
also guard that the real projection stays drivable from the synthetic state.
"""

from __future__ import annotations

from edge.config import load_default_config
from edge.core.rules import Converse
from edge.dialogue.authoring.playtest import BANDS, PlaytestApp, PlaytestService
from edge.tui.screens.contact import AlienContactScreen
from edge.tui.widgets import ClickableEntry

CFG = load_default_config()
# A small universe is enough — the harness injects its own cast and only needs the generated
# discoveries for the intel tip. `start_sector=1` mirrors the other contact/intel tests.
SMALL = CFG.model_copy(
    update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 120, "start_sector": 1})})


def _service() -> PlaytestService:
    return PlaytestService(SMALL, seed=3)


def test_injects_one_instance_per_roster_species() -> None:
    svc = _service()
    assert CFG.roster is not None
    roster_ids = {sc.id for sc in CFG.roster.species}
    injected = {sp.roster_id for sp in svc.state.species.values()}
    assert injected == roster_ids
    assert len(svc.species_ids) == len(roster_ids)
    # Every species is seeded as an attitude so "Ask about…"/dossier can list all the others.
    assert set(svc.state.players[svc.pid].species_attitudes) == roster_ids


def test_contact_view_resolves_for_every_species_and_band() -> None:
    svc = _service()
    for sid in svc.species_ids:
        svc.current = sid
        has_alliance = svc.state.species[sid].alliance_id is not None
        for band in BANDS:
            svc.band = band
            view = svc.contact_view(svc.pid, sid)
            assert view.opener.strip(), f"empty opener for species {sid} band {band}"
            expected = band if (band != "allied" or has_alliance) else "friendly"
            assert view.standing == expected, (sid, band, view.standing)



def test_force_enable_makes_every_verb_and_choice_selectable() -> None:
    svc = _service()
    svc.band = "friendly"
    # A vanilla view carries Phase-2 disabled verbs (e.g. Treaty / Attack), proving there is
    # something for the toggle to flip.
    plain = svc.contact_view(svc.pid, svc.current)
    assert any(not v.enabled for v in plain.verbs)
    svc.toggle_force_enable()
    forced = svc.contact_view(svc.pid, svc.current)
    assert all(v.enabled for v in forced.verbs)
    assert all(c.enabled for c in forced.choices)


def test_force_enable_traverses_a_branch_species() -> None:
    """With force-enable on, an authored branch species exposes selectable player replies."""
    svc = _service()
    svc.toggle_force_enable()
    # Find a species that authors branching choices on its greeting (e.g. the Vesk workshop).
    for sid in svc.species_ids:
        view = svc.contact_view(svc.pid, sid)
        if view.choices:
            assert all(c.enabled for c in view.choices)
            assert any(c.next_context or c.action for c in view.choices)
            break
    else:  # pragma: no cover - corpus always ships at least one branch node
        raise AssertionError("no branching species found in the default corpus")


def test_apply_converse_advances_the_recency_ring() -> None:
    svc = _service()
    sp = svc.state.species[svc.current]
    key = (sp.roster_id, "greeting")
    assert key not in svc.state.players[svc.pid].dialogue_recency
    svc.apply(svc.pid, Converse(svc.current, "greeting"))
    ring = svc.state.players[svc.pid].dialogue_recency
    assert key in ring and len(ring[key]) >= 1


def test_intel_dial_surfaces_a_coordinate_tip_when_friendly() -> None:
    svc = _service()
    svc.band = "friendly"
    assert svc.contact_view(svc.pid, svc.current).intel_summary == ""  # off by default
    svc.toggle_intel()
    assert svc.contact_view(svc.pid, svc.current).intel_summary  # a tip is now on offer


def test_show_disabled_dial_flips_the_runtime_flag() -> None:
    svc = _service()
    assert svc.config.ui.show_disabled_options is False
    svc.toggle_show_disabled()
    assert svc.config.ui.show_disabled_options is True


def test_cycle_and_select_species() -> None:
    svc = _service()
    first = svc.current
    svc.cycle_species(1)
    assert svc.current != first
    svc.cycle_species(-1)
    assert svc.current == first
    assert CFG.roster is not None
    a_roster_id = CFG.roster.species[-1].id
    assert svc.select_species_by_roster(a_roster_id)
    assert svc.state.species[svc.current].roster_id == a_roster_id
    assert svc.select_species_by_roster("not-a-species") is False


def test_cycle_band_wraps() -> None:
    svc = _service()
    seen = [svc.band]
    for _ in range(len(BANDS)):
        svc.cycle_band(1)
        seen.append(svc.band)
    assert seen[0] == seen[-1]  # a full lap returns to the start
    assert set(seen) == set(BANDS)


async def test_app_opens_controls_modal_and_toggles_dials() -> None:
    from edge.dialogue.authoring.playtest import PlaytestControls

    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        await pilot.press("f2")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, PlaytestControls)
        before = (svc.force_enable, svc.config.ui.show_disabled_options)
        for dest in ("force_enable", "show_disabled"):
            modal.post_message(ClickableEntry.Picked(dest))
            await pilot.pause()
        assert (svc.force_enable, svc.config.ui.show_disabled_options) != before
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)


async def test_clicking_outside_controls_dismisses_it() -> None:
    from edge.dialogue.authoring.playtest import PlaytestControls

    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("f2")
        await pilot.pause()
        assert isinstance(app.screen, PlaytestControls)
        await pilot.click(offset=(1, 1))  # the backdrop, well clear of the centred box
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)


async def test_farewell_opens_controls_instead_of_a_blank_screen() -> None:
    from edge.dialogue.authoring.playtest import PlaytestControls

    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        await pilot.press("f")  # Farewell — breaks contact
        await pilot.pause()
        assert isinstance(app.screen, PlaytestControls)
        # Closing the modal lands back on a (fresh) contact screen, never a blank one.
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)


async def test_empty_trade_speaks_a_refusal_beat() -> None:
    svc = _service()
    svc.band = "friendly"
    assert svc.select_species_by_roster("dacaran")  # `refuses` posture ⇒ empty shelf
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        await pilot.press("t")  # Trade with nothing to sell ⇒ a spoken refusal, not a picker
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert app.screen._active_context == "trade_refuse"


async def test_say_verb_records_history_and_backspace_backtracks() -> None:
    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert app.screen._history == ()
        # Open subject picker (Ask about... is 1)
        await pilot.press("1")
        await pilot.pause()
        # Click the first subject in the picker
        await pilot.click("SubjectPickerScreen ClickableEntry")
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert app.screen._history == (("greeting", None),)
        await pilot.press("backspace")
        await pilot.pause()
        assert app.screen._history == ()
        assert app.screen._active_context == "greeting"


async def test_back_row_is_clickable() -> None:
    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        # Open subject picker (Ask about... is 1)
        await pilot.press("1")
        await pilot.pause()
        # Click the first subject in the picker
        await pilot.click("SubjectPickerScreen ClickableEntry")
        await pilot.pause()
        assert app.screen._history == (("greeting", None),)
        back = next(w for w in app.screen.query(ClickableEntry) if w._dest == "back")
        await pilot.click(back)
        await pilot.pause()
        assert app.screen._history == ()


async def test_choice_targets_back_performs_backtrack() -> None:
    from edge.core.config import DialogueChoice, DialogueLine
    svc = _service()
    # Inject a branching node and a choice targeting it under the current species' persona pack
    persona = svc.state.species[svc.current].persona
    pack = svc._config.roster.personas[persona]
    
    # We will define a branch context: "branch.test_back"
    # Greeting will have a choice to go to "branch.test_back"
    pack["greeting"] = [
        DialogueLine(
            variants=["Hello"],
            choices=[
                DialogueChoice(text="Go to branch", next_context="branch.test_back")
            ]
        )
    ]
    # "branch.test_back" will have a choice to go "back"
    pack["branch.test_back"] = [
        DialogueLine(
            variants=["Welcome to branch"],
            choices=[
                DialogueChoice(text="Go back", next_context="back")
            ]
        )
    ]
    
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert app.screen._history == ()
        
        # Select "Go to branch" (which is option 1 in greeting)
        await pilot.press("1")
        await pilot.pause()
        
        # Verify we are on "branch.test_back" and history has ("greeting", None)
        assert app.screen._active_context == "branch.test_back"
        assert app.screen._history == (("greeting", None),)
        
        # Select "Go back" (which is option 1 in branch.test_back)
        await pilot.press("1")
        await pilot.pause()
        
        # Verify we navigated back to "greeting" and history is empty
        assert app.screen._active_context == "greeting"
        assert app.screen._history == ()
