"""Engine-room subsystem icons for the TUI (UI_MOCKUPS.md §8).

The procedural `edge.art` engine (wired via `edge.tui.art_adapter`) now supplies
all ship / port / planet / terrain / starfield art across the TUI. It has no
*subsystem* generator, so these small, hand-drawn vertical glyphs — one per
engine-room subsystem, drawn down the right of each panel — stay here. Keyed by
the subsystem name in the DTO (DESIGN §4.1: spindrive / thrusters / screens /
main_gun).
"""

from __future__ import annotations

SUBSYSTEMS: dict[str, list[str]] = {
    "SPINDRIVE": [  # warp-drive block radiating a field sideways
        " »✦«",
        " ▟█▙",
        " ▐█▌",
        " ▐█▌",
        " ▜█▛",
        " »▼«",
    ],
    "THRUSTERS": [  # slim rocket body firing a twin plume
        "  ╱╲",
        "  ┃┃",
        " ▟██▙",
        " ╲▼▼╱",
        "  ⇣⇣",
    ],
    "SCREENS": [  # faceted diamond deflector shield
        "  ╱╲",
        " ╱  ╲",
        "▐    ▌",
        " ╲  ╱",
        "  ╲╱",
    ],
    "MAIN GUN": [  # flared muzzle over a heavy spinal barrel
        "  ▲",
        " ╱█╲",
        " ▐█▌",
        " ▐█▌",
        " ▐█▌",
        " ▙█▟",
    ],
}


# A representative colour per subsystem (warp = cyan, thrust = amber, shields =
# blue, weapon = red), keyed by the DTO subsystem name. Shared by the Engine
# Room panels and the sprite gallery so the colour mapping lives in one place.
SUBSYSTEM_COLORS: dict[str, str] = {
    "SPINDRIVE": "cyan",
    "THRUSTERS": "yellow",
    "SCREENS": "blue",
    "MAIN GUN": "red",
}


def pick_subsystem(name: str) -> list[str]:
    """The decorative ASCII icon for an engine-room subsystem (§8)."""
    return SUBSYSTEMS.get(name, [])
