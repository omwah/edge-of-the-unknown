"""ANSI sprite sets for the space-battle POC.

Ships are multi-character sprites sized between groundwar's single glyphs and
the big sector-view hulls: authored on a grid of up to `cell_w` x `cell_h`
chars (7x3 by default) so each piece fills its placement cell. Sprite keys are
real ship-class ids from the main game (`missile_frigate`, `scout_marauder`,
`battleship`) but the art is new — deliberately unconstrained by the sector-view
generator, per the POC brief (the big art may later be redrawn to match this).

Ships face the four cardinals only (diagonal hull art at this scale read as
noise): E and N are hand-drawn, W and S derived by horizontal/vertical
glyph-aware mirroring. Facing indices stay `model.DIRS` octants (0 E, 2 N,
4 W, 6 S); odd octants snap to the neighboring cardinal so bearings-derived
lookups can never miss.

Fighters are 3-char darts (one row); mines and missile salvos are single-glyph
markers rendered by the app.
"""

from __future__ import annotations

import random

# Glyphs that must swap when mirrored left<->right.
_HPAIRS = (("▐", "▌"), ("▖", "▗"), ("▘", "▝"), ("▙", "▟"), ("▛", "▜"),
           ("◣", "◢"), ("◤", "◥"), ("▶", "◀"), ("►", "◄"), ("╱", "╲"))
# Glyphs that must swap when mirrored top<->bottom.
_VPAIRS = (("▄", "▀"), ("▖", "▘"), ("▗", "▝"), ("▙", "▛"), ("▟", "▜"),
           ("◣", "◤"), ("◢", "◥"), ("▲", "▼"), ("╱", "╲"), ("▂", "▔"),
           ("▞", "▚"))

_HFLIP: dict[str, str] = {}
_VFLIP: dict[str, str] = {}
for _a, _b in _HPAIRS:
    _HFLIP[_a], _HFLIP[_b] = _b, _a
for _a, _b in _VPAIRS:
    _VFLIP[_a], _VFLIP[_b] = _b, _a
del _a, _b

Rows = tuple[str, ...]


def _hflip(rows: Rows) -> Rows:
    return tuple("".join(_HFLIP.get(c, c) for c in reversed(row)) for row in rows)


def _vflip(rows: Rows) -> Rows:
    return tuple("".join(_VFLIP.get(c, c) for c in row) for row in reversed(rows))


def _facings(east: Rows, north: Rows) -> dict[int, Rows]:
    """The four cardinal aspects from the two authored ones."""
    return {0: east, 2: north, 4: _hflip(east), 6: _vflip(north)}


# --- hull sprite sets (key = main-game ship_classes id) ------------------------

SHIP_SPRITES: dict[str, dict[int, Rows]] = {
    # Warship: boxy central hull, flank launcher bays, blunt ram nose. The N/S
    # aspects flare to full width — a bow-on warship shows its beam, not a sliver.
    "missile_frigate": _facings(
        east=("▗▄▄▖ ",
              "≡███▶",
              "▝▀▀▘ "),
        north=(" ▗▲▖ ",
               "▐███▌",
               " ▀≡▀ "),
    ),
    # Fighter-role escort: light dart hull, forward gun, flared tail fins.
    "scout_marauder": _facings(
        east=(" ▗▖  ",
              "≡██▶ ",
              " ▝▘  "),
        north=("  ▲  ",
               " ▐█▌ ",
               " ▘≡▝ "),
    ),
    # Capital: long spinal hull with the railgun groove (≣) down the axis.
    "battleship": _facings(
        east=("▗▄▄▄▄▖ ",
              "≡██≣██▶",
              "▝▀▀▀▀▘ "),
        north=(" ▟▲▙ ",
               "▐█≣█▌",
               " ▀≡▀ "),
    ),
}

# Fighter wings: 3-char darts, one row, per facing octant.
FIGHTER_SPRITES: dict[int, str] = {
    0: "-=▶", 1: " ◥ ", 2: " ▲ ", 3: " ◤ ",
    4: "◀=-", 5: " ◣ ", 6: " ▼ ", 7: " ◢ ",
}

MINE_GLYPH = "◉"
SALVO_GLYPH = "✦"

# Rocky debris, after `edge.art.terrain`'s asteroid-belt vocabulary: `rock`
# glyphs (• ⬢ ⛬) with `debris`/`dust` satellites (* ⸝ ⹁ . _). The belt biome's
# grey-on-black palette vanished into the starfield here, so rocks wear warm
# sunlit-regolith tans instead (nothing in the starfield palette is warm brown),
# and the app washes every rock cell with `ROCK_BG` so clumps read as one mass.
_ROCK_CORES = (("⬢", "bold #c9a066"), ("⬢", "#b08d57"), ("⛬", "#c9a066"),
               ("•", "bold #d9b47f"))
_ROCK_BITS = (("*", "#8a6f4d"), ("⸝", "#8a6f4d"), ("⹁", "#6e5a3e"),
              (".", "#6e5a3e"), ("·", "#8a6f4d"), ("_", "#6e5a3e"),
              ("•", "#a5834f"), ("˚", "#8a6f4d"))

ROCK_BG = "on #201709"  # dark regolith wash behind a rock cell's whole footprint


def rock_sprite(seed: int, cx: int, cy: int, cell_w: int,
                cell_h: int) -> list[tuple[int, int, str, str]]:
    """Deterministic debris scatter for a rock cell: (dx, dy, char, style)
    offsets within the cell. Keyed on (battle seed, cell) so the field is
    stable across renders and varies rock to rock."""
    rng = random.Random((seed * 73856093) ^ (cx * 19349663) ^ (cy * 83492791))
    out: list[tuple[int, int, str, str]] = []
    core = rng.choice(_ROCK_CORES)
    ccx = cell_w // 2 + rng.randint(-1, 1)
    ccy = cell_h // 2
    out.append((ccx, ccy, *core))
    taken = {(ccx, ccy)}
    for _ in range(rng.randint(3, 5)):
        dx = rng.randint(1, cell_w - 2)
        dy = rng.randint(0, cell_h - 1)
        if (dx, dy) not in taken:
            taken.add((dx, dy))
            out.append((dx, dy, *rng.choice(_ROCK_BITS)))
    return out


def ship_sprite(hull_art: str, facing: int) -> Rows:
    sprites = SHIP_SPRITES.get(hull_art) or SHIP_SPRITES["missile_frigate"]
    return sprites[(facing % 8) & ~1]  # odd octants snap down to a cardinal
