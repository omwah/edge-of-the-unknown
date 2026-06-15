"""ASCII sprite assets for the SectorView scene background (UI_MOCKUPS.md §1).

A small library of monospace "images" keyed by entity *type*. The real game will
select a sprite from a typed DTO (`planet_type`, port class, ship `role`); the
throwaway skeleton keyword-matches the dummy strings (see `pick_*` below). These
are presentation assets, deliberately kept out of widget code so they can later
move to a config/asset file without touching `widgets.py`.

Convention: each sprite is a list of equal-ish-length lines. Sizes follow the
brief — planets are the largest, ports smaller, ships smallest. Sprites are drawn
dimmed as a background; the interface text is stamped bright on top (the art only
fills the negative space the text leaves, so keep them spatially apart).
"""

from __future__ import annotations

# --- planets (largest) -----------------------------------------------------

PLANETS: dict[str, list[str]] = {
    "terrestrial": [
        "   .-~~~-.",
        " .'~ .o. ~'.",
        "/ .o~   ~o. \\",
        ": ~  .O.  ~ :",
        "\\ ~o.   .o~ /",
        " '.~ .o. ~.'",
        "   '-~~~-'",
    ],
    "jovian": [
        "   .-----.",
        " .'~~~~~~~'.",
        "/=========\\",
        ":~~~~~~~~~~~:",
        "\\=========/",
        " '.~~~~~~.'",
        "   '-----'",
    ],
    "asteroid_belt": [
        "  .  o   .  ,",
        " o  . O .  o",
        ". O .  o  .  O",
        " o  . , o   .",
    ],
    "barren": [
        "   .----.",
        " .' o  . '.",
        "/ . () .  \\",
        ": o  .  o .:",
        "\\ . o  () /",
        " '. o  .-'",
        "   '----'",
    ],
}
PLANET_DEFAULT = "terrestrial"

# --- ports / starbases (smaller) -------------------------------------------

PORTS: dict[str, list[str]] = {
    "stardock": [
        " =[#####]=",
        "=[#o#o#o#]=",
        " =[#####]=",
    ],
    "port": [
        "  __||__",
        " [::||::]",
        "  ''||''",
    ],
}
PORT_DEFAULT = "port"

# --- ships (smallest) ------------------------------------------------------

SHIPS: dict[str, list[str]] = {
    "player": [
        "  __",
        " /==}>",
    ],
    "freighter": [
        " ___",
        "[===]=>",
    ],
    "fighter": [
        "<+=-",
    ],
    "warship": [
        " ___",
        "<##==>",
    ],
    "npc": [
        ">--o>",
    ],
}
SHIP_DEFAULT = "npc"

_SHIP_KEYWORDS = {
    "freighter": ("freighter", "trader", "merchant", "hauler"),
    "fighter": ("fighter", "raider", "marauder", "interceptor", "scout"),
    "warship": ("warship", "cruiser", "destroyer", "battleship", "escort"),
}


def pick_planet(label: str) -> list[str]:
    """Skeleton: choose a planet sprite by keyword in the dummy label string."""
    low = label.lower()
    for key in PLANETS:
        if key.replace("_", " ") in low or key in low:
            return PLANETS[key]
    return PLANETS[PLANET_DEFAULT]


def pick_port(label: str) -> list[str]:
    return PORTS["stardock"] if "stardock" in label.lower() else PORTS[PORT_DEFAULT]


def pick_ship(label: str) -> list[str]:
    low = label.lower()
    for kind, words in _SHIP_KEYWORDS.items():
        if any(w in low for w in words):
            return SHIPS[kind]
    return SHIPS[SHIP_DEFAULT]
