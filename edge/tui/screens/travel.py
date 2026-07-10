"""TravelPromptScreen — pick a destination for multi-hop travel (WP-C).

A small modal that asks for a destination sector number and dismisses with it
(or `None` on cancel). The GameScreen turns the answer into a `TravelTo` command,
which is route-locked to sectors the player has already uncovered (§9, §11).
WP-UI07: built on the shared `FieldPrompt`, so a non-numeric entry holds the
form open with an inline reason instead of silently cancelling.
"""

from __future__ import annotations

from edge.tui.chrome import FieldPrompt


class TravelPromptScreen(FieldPrompt):
    def __init__(self) -> None:
        super().__init__("Travel to sector", placeholder="sector number",
                         hint="known route only · Enter to go · Esc to cancel",
                         input_type="integer")

    def parse(self, raw: str) -> tuple[object | None, str | None]:
        text = raw.strip()
        if not text.isdigit():
            return None, "Enter a sector number — or press Esc to cancel."
        return int(text), None
