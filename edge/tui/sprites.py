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

# --- planets, large orbit-view variants ------------------------------------
# A second, larger and more detailed rendering of each planet type, for the
# PlanetScreen orbit view (UI_MOCKUPS.md §3) — same taxonomy as PLANETS above,
# but a focal image rather than a tiny scene marker. Lines are centred by the
# widget (text-align: center), so each row is kept roughly symmetric.

PLANETS_LARGE: dict[str, list[str]] = {
    "terrestrial": [
        "        ._-~~~~-_.",
        "      .-~ .~~. ~~-.",
        "    .~~ .(    ). ~~~.",
        "   /~~ (  .~~.  ) ~~~\\",
        "  |~~~  '~(  )~'  ~~~~|",
        "  |~~ .~. '~~' .~~. ~~|",
        "  |~~ ( )  ~~  (  ) ~~|",
        "  |~~~ '~' ~~~~ '~' ~~|",
        "   \\~~~  .~~.   ~~~~~/",
        "    '~~ (    ) ~~~~~'",
        "      '-~ '~~' ~~-'",
        "        '~-____-~'",
    ],
    "jovian": [
        "        ._-~~~~-_.",
        "      .-~~~~~~~~~~-.",
        "    .~~~~~~~~~~~~~~~~.",
        "   /==================\\",
        "  |~~~~~~~~~~~~~~~~~~~~|",
        "  |====================|",
        "  |~~~~~( o )~~~~~~~~~~~|",
        "  |====================|",
        "  |~~~~~~~~~~~~~~~~~~~~|",
        "   \\==================/",
        "      '-~~~~~~~~~~-'",
        "        '~-____-~'",
    ],
    "asteroid_belt": [
        "   .      o          .",
        "      o  .     .  O     o",
        "  .    O    o      .   .",
        "    .     o   .  O    o  .",
        "  o   .      O    .      o",
        "     .   o    .      o  .",
        "  .     O   .   o  .    O",
        "      o   .    .    O  o",
        "   .    o   .     o   .",
    ],
    "barren": [
        "        ._-~~~~-_.",
        "      .-~ o    .~-.",
        "    .~  .  O  .   . ~.",
        "   / .    .-.   o    .\\",
        "  | o    ( . )    .  o |",
        "  |   .   '-'  .    .  |",
        "  | .   o    .   O    .|",
        "  | O .    .   o .   . |",
        "   \\  .  O   .    o  ./",
        "    '~ .   o   .  . ~'",
        "      '-~ .   O .~-'",
        "        '~-____-~'",
    ],
}

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

# --- engine-room subsystem icons (UI_MOCKUPS.md §8) ------------------------
# A tall, vertical glyph per subsystem, drawn down the right-hand side of each
# panel in the Engine Room (beside the slot list) as a representative icon. These
# use box-drawing/block unicode for the TUI; UI_MOCKUPS.md §8 documents the
# ASCII-only transliteration. Keyed by the subsystem name in the DTO (DESIGN
# §4.1: spindrive / thrusters / screens / main_gun).

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


def _planet_key(label: str) -> str:
    """Skeleton: resolve a planet-type key by keyword in the dummy label string."""
    low = label.lower()
    for key in PLANETS:
        if key.replace("_", " ") in low or key in low:
            return key
    return PLANET_DEFAULT


def pick_planet(label: str) -> list[str]:
    """The small scene-marker sprite for a planet (sector view)."""
    return PLANETS[_planet_key(label)]


def pick_planet_large(label: str) -> list[str]:
    """The large, detailed orbit-view sprite for the same planet type (§3)."""
    return PLANETS_LARGE[_planet_key(label)]


def pick_port(label: str) -> list[str]:
    return PORTS["stardock"] if "stardock" in label.lower() else PORTS[PORT_DEFAULT]


def pick_ship(label: str) -> list[str]:
    low = label.lower()
    for kind, words in _SHIP_KEYWORDS.items():
        if any(w in low for w in words):
            return SHIPS[kind]
    return SHIPS[SHIP_DEFAULT]
