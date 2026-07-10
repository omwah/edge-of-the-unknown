"""WP-UI08/09/10 — the shared component workbench.

Unit-level: every slot state renders distinctly (including without color),
selection toggles emit typed messages, and keystone slots refuse selection.
Structural: the widget stays presentation-only (no service/command imports)
and both hosts — ship Engine Room and starbase Station — use it, with no
second private slot renderer left behind.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

from textual.app import App, ComposeResult

from edge.core.dto import Slot, Subsystem
from edge.tui.component_workbench import (
    ComponentWorkbench,
    SHIP_WORKBENCH_PROFILE,
    STARBASE_WORKBENCH_PROFILE,
    WorkbenchCapabilities,
    WorkbenchSelection,
)


def _subsystems() -> list[Subsystem]:
    return [
        Subsystem(name="SPINDRIVE", derived="warp 3", slots=[
            Slot(state="filled", component="turbine (I)", keystone=True),
            Slot(state="filled", component="converter (I)"),
            Slot(state="knocked", component="radiator (I)"),
            Slot(state="empty"),
        ]),
        Subsystem(name="MAIN GUN", derived="damage 4", slots=[Slot(state="empty")]),
    ]


def _workbench(loose: tuple[str, ...] = ("converter (I) x1",)) -> ComponentWorkbench:
    return ComponentWorkbench(_subsystems(), list(loose), SHIP_WORKBENCH_PROFILE,
                              WorkbenchCapabilities(install=True, swap=True))


def test_every_slot_state_renders_distinctly() -> None:
    bench = _workbench()
    spindrive = bench.subsystems[0]
    keystone, filled, knocked, empty = (bench.slot_line(spindrive, i) for i in range(4))
    assert keystone.startswith("[+]") and "keystone" in keystone
    assert filled == "[+] converter (I)"
    assert knocked.startswith("[!]") and "knocked-out" in knocked
    assert empty == "[ ] ____"
    # The four lines must be distinguishable as plain text (monochrome rule).
    assert len({keystone, filled, knocked, empty}) == 4


def test_selected_slot_renders_with_selection_glyph() -> None:
    bench = _workbench()
    bench._selected_slots.add(("SPINDRIVE", 1))
    assert bench.slot_line(bench.subsystems[0], 1) == "[✓] converter (I)"
    # Selection never hides the underlying knocked-out state.
    bench._selected_slots.add(("SPINDRIVE", 2))
    assert "knocked-out" in bench.slot_line(bench.subsystems[0], 2)


def test_ship_and_base_profiles_stay_distinguishable_without_color() -> None:
    ship, base = SHIP_WORKBENCH_PROFILE, STARBASE_WORKBENCH_PROFILE
    ship_glyphs = {ship.slot_glyphs.filled, ship.slot_glyphs.knocked, ship.slot_glyphs.empty}
    base_glyphs = {base.slot_glyphs.filled, base.slot_glyphs.knocked, base.slot_glyphs.empty}
    assert not ship_glyphs & base_glyphs
    assert set(ship.subsystem_labels.values()) != set(base.subsystem_labels.values())
    assert ship.instructions != base.instructions


class _Harness(App[None]):
    def __init__(self, bench: ComponentWorkbench) -> None:
        super().__init__()
        self._bench = bench
        self.selections: list[WorkbenchSelection] = []

    def compose(self) -> ComposeResult:
        yield self._bench

    def on_component_workbench_selection_changed(
        self, message: ComponentWorkbench.SelectionChanged
    ) -> None:
        self.selections.append(message.selection)


async def test_click_selection_toggles_and_posts_typed_messages() -> None:
    bench = _workbench()
    app = _Harness(bench)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.click(app.query(".workbench-component").first())
        await pilot.pause()
        assert app.selections[-1].loose_components == ("converter (I) x1",)
        slots = list(app.query(".workbench-slot"))
        await pilot.click(slots[3])  # SPINDRIVE empty slot
        await pilot.pause()
        assert app.selections[-1].slots == (("SPINDRIVE", 3),)
        await pilot.click(app.query(".workbench-slot").first())  # click again: toggle off
        await pilot.pause()
        # Keystone slots refuse selection entirely.
        assert all(("SPINDRIVE", 0) not in s.slots for s in app.selections)
        slots = list(app.query(".workbench-slot"))
        await pilot.click(slots[3])
        await pilot.pause()
        assert app.selections[-1].slots == ()  # toggled back off


async def test_empty_loose_bay_shows_empty_state() -> None:
    from edge.tui.chrome import EmptyState
    bench = _workbench(loose=())
    app = _Harness(bench)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert app.query(EmptyState)


def test_workbench_is_presentation_only() -> None:
    """The widget never imports the service, reducers, engine, or store."""
    import edge.tui.component_workbench as module
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    forbidden = ("edge.server", "edge.core.rules", "edge.engine", "edge.store")
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert not name.startswith(forbidden), (
                f"component_workbench imports {name} — it must stay presentation-only"
            )


def test_both_hosts_use_the_shared_workbench_and_no_private_renderer_remains() -> None:
    import edge.tui.screens.base as base_mod
    import edge.tui.screens.engine_room as engine_mod

    assert engine_mod.ComponentWorkbench is ComponentWorkbench
    assert base_mod.ComponentWorkbench is ComponentWorkbench
    # The old private renderers must not creep back in.
    assert not hasattr(base_mod, "_SLOT_GLYPH")
    for module in (base_mod, engine_mod):
        source = inspect.getsource(module)
        assert "station-panel" not in source
        assert "_SubsystemPanel" not in source
        assert "slot_line" not in source, (
            f"{module.__name__} renders slot lines itself instead of via the workbench"
        )
