"""Shared presentation vocabulary for the POC and live DTO assault screens.

No rules or mutable battle state live here: this is the reusable half of the POC
screen — glyphs, semantic colours, and event-flash styles.  Both the standalone
play-test and production Textual client render the authoritative model with it.
"""

from __future__ import annotations

STRUCTURE_ART: dict[str, tuple[str, str, str]] = {
    "wall": ("█", "grey66", "grey30"),
    "gate": ("▒", "gold3", "grey30"),
    "turret": ("╬", "bright_red", "grey30"),
    "aa": ("⊕", "orange1", "grey23"),
    "sensor": ("⍑", "bright_cyan", "grey23"),
    "citadel_gun": ("✸", "bright_magenta", "grey30"),
    "building_military": ("▪", "indian_red", "grey23"),
    "building_civilian": ("⌂", "grey74", "grey23"),
}

RUBBLE_ART = ("▒", "grey42", "black")
AA_THREAT_BG = "on #3a2708"
GROUND_THREAT_BG = "on #3a1414"

EVENT_STYLES: dict[str, str] = {
    "GroundAssaultDropped": "bold bright_green",
    "GroundJumped": "bright_green",
    "GroundFired": "yellow",
    "GroundBroadcastMade": "bold bright_cyan",
    "GroundTurnEnded": "bold bright_magenta",
    "GroundOperationEnded": "bold bright_yellow",
    "GroundAssaultSettled": "bold bright_yellow",
}

EVENT_FLASH: dict[str, str] = {
    "GroundAssaultDropped": "on green",
    "GroundJumped": "on green",
    "GroundFired": "on orange1",
    "GroundBroadcastMade": "on cyan",
}
