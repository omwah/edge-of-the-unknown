"""WP-UI02/WP-UI22 — deterministic snapshot smoke matrix (pytest-textual-snapshot).

Captures the static, seed-free surfaces — main menu, the shared component
workbench in both host profiles, modals, and the below-minimum size notice —
parameterized by terminal size and theme. Screens that need a live universe
(game, Computer, contact, lobby) are exercised functionally in
`test_tui_flow.py`; their visual matrix is WP-UI22's remit once per-screen
responsive work (WP-UI11+) lands.

Regenerate accepted baselines with `pytest --snapshot-update`.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot

from edge.core.dto import Slot, Subsystem
from edge.tui.app import EdgeApp
from edge.tui.component_workbench import (
    ComponentWorkbench,
    SHIP_WORKBENCH_PROFILE,
    STARBASE_WORKBENCH_PROFILE,
    ComponentWorkbenchProfile,
    WorkbenchCapabilities,
)

SIZES = {"compact": (80, 24), "standard": (100, 34), "wide": (120, 40)}


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_main_menu_sizes(snap_compare, size: tuple[int, int]) -> None:
    assert snap_compare(EdgeApp(plain=True), terminal_size=size)


@pytest.mark.parametrize("theme", ["edge-ansi", "edge-high-contrast", "edge-monochrome"])
def test_main_menu_themes(snap_compare, theme: str) -> None:
    async def apply_theme(pilot: Pilot) -> None:
        pilot.app.theme = theme

    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["standard"],
                        run_before=apply_theme)


def test_options_modal(snap_compare) -> None:
    assert snap_compare(EdgeApp(plain=True), press=["o"], terminal_size=SIZES["standard"])


def test_help_modal(snap_compare) -> None:
    assert snap_compare(EdgeApp(plain=True), press=["question_mark"],
                        terminal_size=SIZES["standard"])


def test_size_notice(snap_compare) -> None:
    async def shrink(pilot: Pilot) -> None:
        await pilot.resize_terminal(70, 20)
        await pilot.pause()
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["compact"],
                        run_before=shrink)


def _sample_subsystems(profile: ComponentWorkbenchProfile) -> list[Subsystem]:
    subsystems = []
    for name in profile.subsystem_labels:
        subsystems.append(Subsystem(name=name, derived="aspect 3", slots=[
            Slot(state="filled", component="converter (I)", keystone=True),
            Slot(state="filled", component="turbine (II)"),
            Slot(state="knocked", component="radiator (I)"),
            Slot(state="empty"),
        ]))
    return subsystems


class _WorkbenchApp(App[None]):
    def __init__(self, profile: ComponentWorkbenchProfile, loose: list[str]) -> None:
        super().__init__()
        self._profile = profile
        self._loose = loose

    def compose(self) -> ComposeResult:
        yield ComponentWorkbench(_sample_subsystems(self._profile), self._loose,
                                 self._profile, WorkbenchCapabilities(install=True))


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_ship_workbench_sizes(snap_compare, size: tuple[int, int]) -> None:
    app = _WorkbenchApp(SHIP_WORKBENCH_PROFILE, ["converter (I) x1", "burner (II) x2"])
    assert snap_compare(app, terminal_size=size)


def test_base_workbench_with_empty_loose_bay(snap_compare) -> None:
    app = _WorkbenchApp(STARBASE_WORKBENCH_PROFILE, [])
    assert snap_compare(app, terminal_size=SIZES["standard"])
