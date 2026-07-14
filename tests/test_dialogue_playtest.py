"""Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/authoring).

Covers the non-UI `PlaytestService` (synthetic cast, band/standing dials, force-enable, recency
advance, intel) and a Textual Pilot flow over `PlaytestApp` (controls modal + the shared contact
screen's `b` backtracking). The harness reuses the *real* `session.contact_view`, so these also
guard that the real projection stays drivable from the synthetic state.
"""

from __future__ import annotations

from edge.config import load_default_config
from edge.core.rules import Converse
from edge.dialogue import instance_key
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



def test_force_enable_makes_every_reply_selectable() -> None:
    svc = _service()
    svc.band = "friendly"
    # A species on the generic baseline menu carries Phase-2 disabled replies (Treaty / Attack),
    # proving there is something for the toggle to flip. (Vesk authors its own enabled-only menu.)
    svc.current = next(sid for sid in svc.species_ids
                       if svc.state.species[sid].roster_id != "vesk")
    plain = svc.contact_view(svc.pid, svc.current)
    assert any(not c.enabled for c in plain.choices)
    svc.toggle_force_enable()
    forced = svc.contact_view(svc.pid, svc.current)
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
    key = (instance_key(sp), "greeting")
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
        await pilot.press("c")
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


async def test_controls_board_is_keyboard_navigable() -> None:
    """PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused one."""
    from edge.dialogue.authoring.playtest import PlaytestControls
    from edge.tui.widgets import ObjectRow

    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, PlaytestControls)
        # Focus lands on a dial, not on the box, so the board is usable without a mouse.
        assert isinstance(app.screen.focused, ObjectRow)
        assert app.screen.focused.dest == "species"

        first_species = svc.current
        await pilot.press("enter")  # advance the focused (species) dial
        await pilot.pause()
        assert svc.current != first_species
        assert isinstance(app.screen.focused, ObjectRow)  # focus survives the recompose
        assert app.screen.focused.dest == "species"
        await pilot.press("left")  # step it back the other way
        await pilot.pause()
        assert svc.current == first_species

        await pilot.press("down")  # onto Standing
        await pilot.pause()
        assert app.screen.focused.dest == "band"
        band = svc.band
        await pilot.press("right")
        await pilot.pause()
        assert svc.band != band

        await pilot.press("down", "space")  # Treaty toggles on Space
        await pilot.pause()
        assert svc.treaty is True
        await pilot.press("c")  # the new hotkey closes it too
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)


async def test_hostile_dial_changes_the_conversation() -> None:
    """PT-41: standing is not just a bar — a hostile species greets you in a hostile voice."""
    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        friendly_opener = app.screen._contact.opener

        svc.band = "hostile"
        app._after_controls(None)  # what closing the dial board does
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert app.screen._contact.standing == "hostile"
        assert app.screen._contact.opener != friendly_opener


def test_every_species_greets_an_enemy_in_its_own_voice() -> None:
    """A pack that authors a greeting must author a hostile one (PT-41).

    The chain never blends packs: a catch-all greeting claims the context outright, so
    `generic`'s standing-keyed openers are unreachable for any species whose own pack (or
    persona) speaks that beat. Without a hostile entry there, hostility is invisible in
    conversation — the bug PT-41 reported. This exercises the persona layer, which is what the
    test loader leaves in the chain (`edge/config.py` drops species sidecars under pytest);
    `test_species_corpus_authors_a_hostile_greeting` covers the species packs themselves.
    """
    svc = _service()
    for sid in svc.species_ids:
        svc.current = sid
        svc.band = "friendly"
        friendly = svc.contact_view(svc.pid, sid).opener
        svc.band = "hostile"
        hostile = svc.contact_view(svc.pid, sid).opener
        roster_id = svc.state.species[sid].roster_id
        assert hostile.strip(), f"{roster_id} has no hostile opener"
        assert hostile != friendly, f"{roster_id} greets an enemy exactly as it greets a friend"


def test_species_corpus_authors_a_hostile_greeting() -> None:
    """Every species pack that claims `greeting` claims the hostile standing too (PT-41).

    Read straight off disk: the shipped species corpus is spliced out of the roster under pytest
    (`edge/config.py`), so the loaded chain cannot see it — but a species greeting entry shadows
    both the persona and generic packs in the *real game*, which is where the bug bit.
    """
    import yaml

    from edge.config import DEFAULT_CONFIG_PATH

    path = DEFAULT_CONFIG_PATH.parent / "dialogue" / "alien_dialogue_species.yaml"
    grammars = yaml.safe_load(path.read_text(encoding="utf-8"))["species_grammars"]
    for species_id, pack in grammars.items():
        greeting = pack.get("greeting")
        if not greeting:
            continue  # a pack that doesn't claim the beat falls through to its persona
        standings = [(entry.get("when") or {}).get("standing") for entry in greeting]
        assert "hostile" in standings, f"{species_id} greets an enemy as it greets a friend"


async def test_clicking_outside_controls_dismisses_it() -> None:
    from edge.dialogue.authoring.playtest import PlaytestControls

    svc = _service()
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("c")
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
        # Baseline menu: 1 Ask about… / 2 coordinates / 3 Trade. Trade with nothing to sell ⇒ a
        # spoken refusal, not a picker.
        await pilot.press("3")
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert app.screen._active_context == "trade_refuse"


async def test_say_reply_records_history_and_b_backtracks() -> None:
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
        await pilot.press("b")  # Back
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


async def test_accept_lead_respects_next_context() -> None:
    from edge.core.config import DialogueChoice, DialogueLine
    svc = _service()
    svc.toggle_intel()
    svc.band = "friendly"
    persona = svc.state.species[svc.current].persona
    pack = svc._config.roster.personas[persona]
    
    # greeting will have a choice with action="accept_lead" and next_context="greeting"
    pack["greeting"] = [
        DialogueLine(
            variants=["I have coordinates for you."],
            choices=[
                DialogueChoice(text="Log it", action="accept_lead", next_context="greeting")
            ]
        )
    ]
    
    app = PlaytestApp(svc)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert len(svc.state.players[svc.pid].leads) == 0
        
        # Select "Log it" choice (option 1)
        await pilot.press("1")
        await pilot.pause()
        
        # Verify coordinates were logged
        assert len(svc.state.players[svc.pid].leads) == 1
        # Verify we transitioned back to "greeting" context
        assert app.screen._active_context == "greeting"
