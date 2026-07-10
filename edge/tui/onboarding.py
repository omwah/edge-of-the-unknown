"""Captain's objectives — progressive onboarding (UI_UX_OVERHAUL_PLAN.md WP-UI11).

A dismissible one-line strip on the game screen walks a new captain through the
first-session loop: dock, trade, inspect/upgrade, scan, discover. Progress is
purely local presentation state (`UISettings.objectives_done`) — never part of
universe state, replay logs, or hashes — and marking happens at the UI seams
where the player performs each act, so it works equally for new and continued
games. The strip hides itself once every objective is done, and clicking it (or
pressing `O` on the game screen) dismisses it; the Options screen re-enables it.
"""

from __future__ import annotations

from textual.widgets import Static

# (id, label, hint) in teaching order — the first-trade-within-five-minutes path.
OBJECTIVES: tuple[tuple[str, str, str], ...] = (
    ("dock", "Dock", "press P at a port to dock"),
    ("trade", "Trade", "buy or sell a commodity in the trade panel"),
    ("inspect", "Inspect ship", "open the Engine Room with E"),
    ("scan", "Scan", "press Z to log a find in sensor range"),
    ("discover", "Discover", "collect a discovery into your codex"),
)

OBJECTIVE_IDS = tuple(obj_id for obj_id, _, _ in OBJECTIVES)


def all_done(done: tuple[str, ...]) -> bool:
    return set(OBJECTIVE_IDS) <= set(done)


def next_hint(done: tuple[str, ...]) -> str:
    """The hint for the first objective still open ('' when all are done)."""
    for obj_id, _, hint in OBJECTIVES:
        if obj_id not in done:
            return hint
    return ""


class ObjectivesStrip(Static):
    """The one-line objectives readout; click to dismiss (same as `O`)."""

    DEFAULT_CSS = """
    ObjectivesStrip { height: 1; padding: 0 1; background: $panel; color: $text-muted; }
    ObjectivesStrip:hover { background: $boost; }
    """

    def __init__(self, done: tuple[str, ...], **kwargs: object) -> None:
        super().__init__(self._markup(done), **kwargs)
        self.tooltip = next_hint(done)

    @staticmethod
    def _markup(done: tuple[str, ...]) -> str:
        parts = []
        for obj_id, label, _ in OBJECTIVES:
            if obj_id in done:
                parts.append(f"[green]✓ {label}[/]")
            else:
                parts.append(f"· {label}")
        return ("[b]OBJECTIVES[/]  " + "   ".join(parts)
                + "   [dim](O or click hides — hint: " + (next_hint(done) or "done!") + ")[/]")

    def show_progress(self, done: tuple[str, ...]) -> None:
        self.update(self._markup(done))
        self.tooltip = next_hint(done)

    def on_click(self) -> None:
        self.app.update_ui_settings(show_onboarding=False)  # type: ignore[attr-defined]
        self.remove()
