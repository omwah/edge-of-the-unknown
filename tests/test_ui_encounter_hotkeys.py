"""Encounter-screen button/hotkey parity (PT-43 / WP-PR2-10).

The four combat buttons advertise their accelerator in the label (`▶ FIRE [F]`), which
`ui: WP-UI18 combat dashboard` shipped. These guard that promise: the bracketed letter in a
button's label IS the key bound to the action that button fires, the letter is carried by the
text (not by colour, so monochrome loses nothing), and pressing the key issues the same
command that clicking the button does.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from edge.core.dto import EncounterDTO
from edge.core.rules import CombatAction
from edge.tui.app import EdgeApp
from edge.tui.dummy import sample_encounter_view
from edge.tui.screens.encounter import EncounterScreen
from textual.widgets import Button

BUTTON_LETTER = re.compile(r"\[([A-Z])\]")


class RecordingEncounterService:
    """A live encounter that records the commands the screen applies (and never resolves).

    Its engine room carries one knocked-out slot, so `[K] PATCH` has something to repair —
    without a target the screen (correctly) refuses the key, and the parity check below would
    be testing the wrong thing.
    """

    def __init__(self) -> None:
        self.applied: list[CombatAction] = []

    def encounter_view(self, player_id: int) -> EncounterDTO:
        return sample_encounter_view()

    def engine_room_view(self, player_id: int) -> SimpleNamespace:
        knocked = SimpleNamespace(state="knocked")
        return SimpleNamespace(
            subsystems=[SimpleNamespace(name="Spindrive", slots=[knocked])])

    def apply(self, player_id: int, command: CombatAction) -> tuple[object, ...]:
        self.applied.append(command)
        return ()


def _bindings() -> dict[str, str]:
    """action name → the key bound to it."""
    return {b.action: b.key for b in EncounterScreen.BINDINGS}


def test_every_action_button_has_a_binding_and_names_it() -> None:
    """The button→action map and the binding table cover exactly the same actions."""
    keys = _bindings()
    for action in EncounterScreen.BUTTON_ACTIONS.values():
        assert action in keys, f"button action {action!r} has no key binding"
        assert hasattr(EncounterScreen, f"action_{action}"), f"no handler for {action!r}"


@pytest.mark.parametrize("button_id,action", sorted(EncounterScreen.BUTTON_ACTIONS.items()))
async def test_button_label_carries_its_binding_letter(button_id: str, action: str) -> None:
    """The `[F]` in a label is the key that fires it — a rename cannot leave the label stale."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        app.push_screen(EncounterScreen(RecordingEncounterService(), 1))
        await pilot.pause()
        label = str(app.screen.query_one(f"#{button_id}", Button).label)
        letters = BUTTON_LETTER.findall(label)
        assert letters, f"{button_id} label {label!r} advertises no hotkey"
        assert letters[0].lower() == _bindings()[action], (
            f"{button_id} label {label!r} disagrees with its binding")


def test_no_button_label_hides_its_hotkey_in_markup() -> None:
    """Repo-wide: a `[K]` in a Button label must be escaped, or Rich eats it (PT-43).

    This is the bug itself: the encounter buttons *said* `▶ FIRE [F]` in the source and rendered
    `▶ FIRE `, because a Button label is Rich markup and `[F]` parses as a (meaningless) style
    tag. The same trap had swallowed the Help and Surface accelerators. Any new button that
    advertises a key must escape the bracket — `\\[F]` — and this fails if one forgets.
    """
    from pathlib import Path

    unescaped = re.compile(r"""Button\(f?["'][^"']*(?<!\\)\[[A-Za-z]\]""")
    offenders = [
        f"{path.relative_to(Path.cwd())}:{n}: {line.strip()}"
        for path in sorted(Path("edge/tui").rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if unescaped.search(line)
    ]
    assert not offenders, "Button labels whose hotkey Rich will swallow:\n" + "\n".join(offenders)


async def test_the_hotkey_and_the_click_issue_the_same_command() -> None:
    """Keyboard and mouse are one path: `f` and the FIRE button both apply the same action."""
    service = RecordingEncounterService()
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        app.push_screen(EncounterScreen(service, 1))
        await pilot.pause()

        await pilot.press("f")
        await pilot.pause()
        assert [c.action for c in service.applied] == ["fight"]

        await pilot.click("#btn-fight")
        await pilot.pause()
        assert [c.action for c in service.applied] == ["fight", "fight"]

        # …and each remaining letter fires its own action, in the order the labels promise.
        for key, expected in (("m", "launch_missile"), ("k", "field_patch"), ("r", "flee")):
            before = len(service.applied)
            await pilot.press(key)
            await pilot.pause()
            assert len(service.applied) == before + 1, f"{key!r} fired nothing"
            assert service.applied[-1].action == expected
