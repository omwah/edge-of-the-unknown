"""Shared slotted-component UI for ships and orbital starbases.

The widget is deliberately presentation-only. It knows how to display and select
DTO slots, but never imports the service or command reducers. Host screens turn
its canonical `(subsystem name, slot index)` selections into commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from edge.core.dto import Subsystem
from edge.tui import sprites
from edge.tui.chrome import EmptyState
from edge.tui.widgets import ClickableEntry


@dataclass(frozen=True)
class SlotGlyphs:
    filled: str
    selected: str
    knocked: str
    empty: str
    keystone: str = "◆"


@dataclass(frozen=True)
class ComponentWorkbenchProfile:
    context: Literal["ship", "starbase"]
    workbench_title: str
    loose_components_title: str
    subsystem_labels: Mapping[str, str]
    subsystem_art: Mapping[str, tuple[str, ...]]
    subsystem_colors: Mapping[str, str]
    slot_glyphs: SlotGlyphs
    panel_border_token: str
    instructions: str


@dataclass(frozen=True)
class WorkbenchCapabilities:
    install: bool = False
    swap: bool = False
    field_patch: bool = False
    full_repair: bool = False
    salvage: bool = False


@dataclass(frozen=True)
class WorkbenchSelection:
    loose_components: tuple[str, ...]
    slots: tuple[tuple[str, int], ...]


class _BayPanel(Horizontal):
    DEFAULT_CSS = """
    _BayPanel { height: auto; padding: 0 1; margin: 0 1 1 0; }
    _BayPanel.ship-bay { border: round $primary; }
    _BayPanel.starbase-bay { border: heavy $warning; }
    _BayPanel .workbench-slots { width: 1fr; height: auto; }
    _BayPanel .workbench-art { width: auto; height: auto; margin-left: 2; }
    """

    def __init__(self, workbench: "ComponentWorkbench", subsystem: Subsystem) -> None:
        super().__init__(classes=f"{workbench.profile.context}-bay")
        self._workbench = workbench
        self.subsystem = subsystem

    def compose(self) -> ComposeResult:
        with Vertical(classes="workbench-slots"):
            for index, slot in enumerate(self.subsystem.slots):
                yield ClickableEntry(
                    self._workbench.slot_line(self.subsystem, index),
                    dest="workbench-slot", ref=f"{self.subsystem.name}\x1f{index}",
                    classes="workbench-slot",
                )
        art = self._workbench.profile.subsystem_art.get(self.subsystem.name, ())
        if art:
            icon = Static("\n".join(art), classes="workbench-art")
            icon.styles.color = self._workbench.profile.subsystem_colors.get(
                self.subsystem.name, "$primary"
            )
            yield icon

    def on_mount(self) -> None:
        profile = self._workbench.profile
        self.border_title = profile.subsystem_labels.get(self.subsystem.name, self.subsystem.name)
        self.border_subtitle = f"→ {self.subsystem.derived}"


class ComponentWorkbench(Widget):
    """Responsive component grid and loose-component selector shared by both hosts."""

    can_focus = True

    class SelectionChanged(Message):
        def __init__(self, selection: WorkbenchSelection) -> None:
            super().__init__()
            self.selection = selection

    DEFAULT_CSS = """
    ComponentWorkbench { height: 1fr; min-height: 8; }
    ComponentWorkbench #workbench-grid {
        grid-size: 2; grid-columns: 1fr 1fr; grid-rows: auto; height: auto; padding: 1 1 0 1;
    }
    ComponentWorkbench #workbench-loose {
        height: auto; max-height: 9; border: round $primary; padding: 0 1; margin: 0 1 1 1;
    }
    ComponentWorkbench #workbench-instructions { height: auto; color: $text-muted; padding: 0 1; }
    .compact ComponentWorkbench #workbench-grid, ComponentWorkbench.compact #workbench-grid {
        grid-size: 1; grid-columns: 1fr; padding: 0;
    }
    .compact ComponentWorkbench .workbench-art, ComponentWorkbench.compact .workbench-art { display: none; }
    .minimal-art ComponentWorkbench .workbench-art { display: none; }
    .wide ComponentWorkbench.starbase #workbench-grid,
    ComponentWorkbench.wide.starbase #workbench-grid { grid-size: 3; grid-columns: 1fr 1fr 1fr; }
    """

    def __init__(self, subsystems: list[Subsystem], loose_components: list[str],
                 profile: ComponentWorkbenchProfile, capabilities: WorkbenchCapabilities,
                 *, id: str | None = None) -> None:
        super().__init__(id=id, classes=profile.context)
        self.subsystems = subsystems
        self.loose_components = loose_components
        self.profile = profile
        self.capabilities = capabilities
        self._selected_slots: set[tuple[str, int]] = set()
        self._selected_components: set[str] = set()

    @property
    def selection(self) -> WorkbenchSelection:
        return WorkbenchSelection(
            tuple(sorted(self._selected_components)), tuple(sorted(self._selected_slots))
        )

    def compose(self) -> ComposeResult:
        with Grid(id="workbench-grid"):
            for subsystem in self.subsystems:
                yield _BayPanel(self, subsystem)
        with Vertical(id="workbench-loose"):
            yield Static(self.profile.loose_components_title, classes="section-heading")
            if self.loose_components:
                for component in self.loose_components:
                    marker = self.profile.slot_glyphs.selected if component in self._selected_components else " "
                    yield ClickableEntry(
                        f"[{marker}] {component}", dest="workbench-loose", ref=component,
                        classes="workbench-component",
                    )
            else:
                yield EmptyState(
                    "No loose components aboard.",
                    "Buy parts at a hardware emporium or salvage them from wrecks and bases.",
                )
        yield Static(self.profile.instructions, id="workbench-instructions")

    def on_mount(self) -> None:
        settings = getattr(self.app, "ui_settings", None)
        self.set_class(bool(settings and settings.art_detail == "minimal"), "minimal-art")
        tier = getattr(getattr(self.app, "layout_tier", None), "value", "standard")
        self.add_class(tier)

    def slot_line(self, subsystem: Subsystem, index: int) -> str:
        slot = subsystem.slots[index]
        glyphs = self.profile.slot_glyphs
        selected = (subsystem.name, index) in self._selected_slots
        key = f" {glyphs.keystone} keystone" if slot.keystone else ""
        if selected:
            marker = glyphs.selected
        elif slot.state == "filled":
            marker = glyphs.filled
        elif slot.state == "knocked":
            marker = glyphs.knocked
        else:
            marker = glyphs.empty
        label = slot.component or "____"
        state = " knocked-out" if slot.state == "knocked" else ""
        return f"[{marker}] {label}{key}{state}"

    @on(ClickableEntry.Picked)
    async def on_entry_picked(self, message: ClickableEntry.Picked) -> None:
        if message.dest == "workbench-loose":
            self._selected_components.symmetric_difference_update({str(message.ref)})
        elif message.dest == "workbench-slot":
            name, index_text = str(message.ref).split("\x1f", 1)
            index = int(index_text)
            slot = next(s for s in self.subsystems if s.name == name).slots[index]
            if slot.state == "filled" and slot.keystone:
                return
            self._selected_slots.symmetric_difference_update({(name, index)})
        else:
            return
        await self.recompose()
        self.post_message(self.SelectionChanged(self.selection))


SHIP_WORKBENCH_PROFILE = ComponentWorkbenchProfile(
    context="ship", workbench_title="Engine Room", loose_components_title="Loose Components",
    subsystem_labels={
        "SPINDRIVE": "Spindrive", "THRUSTERS": "Thrusters",
        "SCREENS": "Screens", "MAIN GUN": "Main Gun",
    },
    subsystem_art={key: tuple(value) for key, value in sprites.SUBSYSTEMS.items()}, subsystem_colors={
        "SPINDRIVE": "cyan", "THRUSTERS": "yellow", "SCREENS": "blue", "MAIN GUN": "red",
    },
    slot_glyphs=SlotGlyphs(filled="+", selected="✓", knocked="!", empty=" "),
    panel_border_token="$primary",
    instructions="1 Select carried component or installed slot  ·  2 choose Install/Swap/Repair/Salvage",
)

STARBASE_WORKBENCH_PROFILE = ComponentWorkbenchProfile(
    context="starbase", workbench_title="Station Systems",
    loose_components_title="Components aboard your ship",
    subsystem_labels={
        "FUSION REACTOR": "Fusion Core", "SCREENS": "Defense Grid",
        "MAIN GUN": "Orbital Battery",
    },
    subsystem_art={
        "FUSION REACTOR": (" ╭◉╮", "╞██╡", " ╰◉╯"),
        "SCREENS": ("◁ ┼ ▷", " ╲│╱ ", "  ◇  "),
        "MAIN GUN": ("╒═╤═╕", "  █══", "╘═╧═╛"),
    },
    subsystem_colors={"FUSION REACTOR": "magenta", "SCREENS": "cyan", "MAIN GUN": "yellow"},
    slot_glyphs=SlotGlyphs(filled="▣", selected="▰", knocked="▨", empty="▢", keystone="◆"),
    panel_border_token="$warning",
    instructions="Select a ship component + empty installation slot to repair, or a live slot to salvage",
)
