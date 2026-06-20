"""Procedural surface-terrain art for the descent screen (§7, WP6).

Builds the top-down ASCII map shown in the SurfaceScreen `terrain` panel. The map is
**purely cosmetic** — it carries no rules state — but it is generated deterministically
from `(seed, planet_id)` so a given world always looks the same and `(seed, command log)`
replay stays exact.

Each `planet_type` has its own *flavor*: a palette of glyph strata laid over a smoothed
value-noise elevation field, plus type-appropriate water. Terrestrial worlds grow seas,
rivers, and lakes; the scorched and frozen variants swap those for lava and ice; gas
giants render banded cloud decks with a storm spot; airless worlds (belts, barren rock)
go sparse and crater-pocked with no water at all. Revealed surface sites are stamped onto
the map at the markers the SurfaceScreen lists below it.

The output is a list of Rich-markup rows (literal `[` is escaped) ready to drop into the
`SurfaceDTO.terrain` field. The generator lives in the server layer beside `surface_view`,
which owns the only call site.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from edge.core.dto import SurfaceSite

Cell = tuple[str, str | None]  # (glyph, Rich style or None for an unstyled gap)

DEFAULT_WIDTH = 54
DEFAULT_HEIGHT = 8


@dataclass(frozen=True)
class _Flavor:
    """One planet-type's look: water behaviour, elevation strata, and noise shape."""

    blurb: str
    cell_w: int  # value-noise lattice spacing (wider == broader, smoother features)
    cell_h: int
    sea_level: float  # land below this floods; 0.0 == a waterless world
    water_glyphs: str
    water_style: str
    deep_style: str
    rivers: int
    lakes: int
    # land strata, low → high: (upper bound as a fraction of the above-sea range, glyphs, style)
    strata: tuple[tuple[float, str, str], ...]
    density: float = 1.0  # chance a land cell is drawn vs. left as void (airless worlds < 1)
    sparkle: tuple[str, str] | None = None  # rare accent glyph scattered over land
    peak_cap: tuple[str, str] | None = None  # cap glyph on the very highest cells (snow/ice)
    banded: bool = False  # gas giants: near-horizontal cloud decks instead of relief
    craters: int = 0  # airless worlds: ring craters stamped over the field
    storm: tuple[str, str] | None = None  # gas-giant great-spot (glyphs, style)


_TERRESTRIAL_WARM = _Flavor(
    blurb="a warm, living world",
    cell_w=9, cell_h=4, sea_level=0.44,
    water_glyphs="~≈", water_style="blue", deep_style="dark_blue",
    rivers=2, lakes=1,
    strata=(
        (0.10, ".·,", "yellow"),       # beaches & sand
        (0.42, '",.\'', "green"),      # plains & grass
        (0.70, "♣♠ϒ", "spring_green4"),  # forest
        (0.88, "^n∧", "dark_green"),   # hills
        (1.00, "▲^", "grey70"),        # mountains
    ),
    sparkle=("¸˙", "spring_green3"),
    peak_cap=("▲", "white"),
)

_TERRESTRIAL_COOL = _Flavor(
    blurb="a temperate green world",
    cell_w=8, cell_h=4, sea_level=0.46,
    water_glyphs="~≈", water_style="steel_blue", deep_style="dark_blue",
    rivers=2, lakes=2,
    strata=(
        (0.12, ".·", "grey58"),        # shingle shore
        (0.40, ',."', "dark_sea_green4"),  # heath & meadow
        (0.68, "♣♠ϒ", "green"),        # forest
        (0.86, "^n∧", "grey50"),       # highland
        (1.00, "▲^", "grey78"),        # snow-streaked peaks
    ),
    sparkle=("˙·", "pale_turquoise4"),
    peak_cap=("▲", "white"),
)

_TERRESTRIAL_HOT = _Flavor(
    blurb="a scorched, volcanic world",
    cell_w=8, cell_h=4, sea_level=0.30,
    water_glyphs="~≈", water_style="dark_orange", deep_style="red",  # lava, not water
    rivers=2, lakes=1,
    strata=(
        (0.18, "·.", "orange1"),       # cinder flats by the lava
        (0.46, ",.˷", "khaki3"),       # dust & ash dunes
        (0.72, "nʌ", "tan"),           # baked badlands
        (0.90, "^∧", "grey46"),        # scarps
        (1.00, "▲^", "grey35"),        # cinder cones
    ),
    sparkle=("∴*", "orange_red1"),
)

_TERRESTRIAL_COLD = _Flavor(
    blurb="a frozen, ice-locked world",
    cell_w=9, cell_h=4, sea_level=0.40,
    water_glyphs="~_˷", water_style="cyan", deep_style="steel_blue",  # frozen sea
    rivers=1, lakes=2,
    strata=(
        (0.16, "·.˙", "white"),        # ice shelf
        (0.48, ",.\"", "grey85"),      # snow fields
        (0.74, "·^", "light_steel_blue"),  # firn & ridges
        (0.90, "^∧", "grey62"),        # frost-shattered rock
        (1.00, "▲^", "white"),         # glacial peaks
    ),
    sparkle=("˙*", "bright_cyan"),
    peak_cap=("▲", "bright_white"),
)

_JOVIAN = _Flavor(
    blurb="a banded gas giant",
    cell_w=64, cell_h=2, sea_level=0.0,  # wide lattice ⇒ near-horizontal cloud decks
    water_glyphs="", water_style="", deep_style="",
    rivers=0, lakes=0,
    strata=(
        (0.20, "≈~", "tan"),
        (0.40, "~-", "orange1"),
        (0.58, "≈~", "khaki1"),
        (0.74, "~-", "light_salmon3"),
        (0.88, "≈~", "wheat1"),
        (1.00, "~-", "rosy_brown"),
    ),
    storm=("@◍O", "orange_red1"),
)

_ASTEROID_BELT = _Flavor(
    blurb="a tumbling rubble belt",
    cell_w=5, cell_h=3, sea_level=0.0,
    water_glyphs="", water_style="", deep_style="",
    rivers=0, lakes=0,
    strata=(
        (0.45, "·.", "grey42"),        # dust & grit
        (0.72, "ºo", "grey58"),        # pebbles
        (0.90, "Oøʘ", "grey70"),       # boulders
        (1.00, "@▲", "grey85"),        # planetesimals
    ),
    density=0.5,
    sparkle=("*✦", "bright_cyan"),     # metal glints
    craters=0,
)

_BARREN = _Flavor(
    blurb="a cratered, airless rock",
    cell_w=6, cell_h=3, sea_level=0.0,
    water_glyphs="", water_style="", deep_style="",
    rivers=0, lakes=0,
    strata=(
        (0.30, "·.", "grey37"),        # regolith dust
        (0.58, ",˷", "grey50"),        # mare flats
        (0.80, "nº", "grey62"),        # rilles & rubble
        (0.94, "^∧", "grey74"),        # ridges
        (1.00, "▲^", "grey85"),        # massifs
    ),
    density=0.85,
    sparkle=("˙·", "grey46"),
    craters=5,
)

_FLAVORS: dict[str, _Flavor] = {
    "terrestrial_warm": _TERRESTRIAL_WARM,
    "terrestrial_cool": _TERRESTRIAL_COOL,
    "terrestrial_hot": _TERRESTRIAL_HOT,
    "terrestrial_cold": _TERRESTRIAL_COLD,
    "jovian": _JOVIAN,
    "asteroid_belt": _ASTEROID_BELT,
    "barren": _BARREN,
}


def _flavor_for(planet_type: str) -> _Flavor:
    """Resolve a flavor by exact type, then by `terrestrial_*` family, else temperate."""
    if planet_type in _FLAVORS:
        return _FLAVORS[planet_type]
    if planet_type.startswith("terrestrial"):
        return _TERRESTRIAL_WARM
    return _BARREN


def blurb_for(planet_type: str) -> str:
    """The one-line flavor caption for a planet type (used in the panel title)."""
    return _flavor_for(planet_type).blurb


# --- value noise -----------------------------------------------------------


def _lattice(cols: int, rows: int, rng: random.Random) -> list[list[float]]:
    return [[rng.random() for _ in range(cols)] for _ in range(rows)]


def _sample(grid: list[list[float]], gx: float, gy: float) -> float:
    """Smoothstep-interpolated read of a lattice at fractional grid coords."""
    ix, iy = int(gx), int(gy)
    fx, fy = gx - ix, gy - iy
    sx = fx * fx * (3 - 2 * fx)
    sy = fy * fy * (3 - 2 * fy)
    v00, v10 = grid[iy][ix], grid[iy][ix + 1]
    v01, v11 = grid[iy + 1][ix], grid[iy + 1][ix + 1]
    top = v00 + (v10 - v00) * sx
    bot = v01 + (v11 - v01) * sx
    return top + (bot - top) * sy


def _fbm(width: int, height: int, rng: random.Random, cell_w: int, cell_h: int) -> list[list[float]]:
    """Two-octave value noise in [0, 1] over a width×height field."""
    coarse = _lattice(width // cell_w + 2, height // cell_h + 2, rng)
    fcw, fch = max(2, cell_w // 2), max(1, cell_h // 2)
    fine = _lattice(width // fcw + 2, height // fch + 2, rng)
    out: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            v = 0.65 * _sample(coarse, x / cell_w, y / cell_h)
            v += 0.35 * _sample(fine, x / fcw, y / fch)
            row.append(v)
        out.append(row)
    return out


# --- water carving ---------------------------------------------------------


def _carve_lakes(elev: list[list[float]], flavor: _Flavor, rng: random.Random) -> None:
    """Press a few rounded basins below sea level so they pool into lakes."""
    height, width = len(elev), len(elev[0])
    for _ in range(flavor.lakes):
        cx, cy = rng.randint(4, width - 5), rng.randint(1, height - 2)
        r = rng.uniform(2.5, 4.0)
        for y in range(height):
            for x in range(width):
                d2 = ((x - cx) / r) ** 2 + ((y - cy) / (r * 0.55)) ** 2
                if d2 < 1.0:
                    elev[y][x] -= (1.0 - d2) * 0.5


def _carve_rivers(
    elev: list[list[float]], water: list[list[bool]], flavor: _Flavor, rng: random.Random
) -> None:
    """Walk each river downhill from a high cell until it meets the sea or an edge."""
    height, width = len(elev), len(elev[0])
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for _ in range(flavor.rivers):
        x = rng.randint(width // 4, 3 * width // 4)
        y = rng.randint(0, height - 1)
        # bias the source toward higher ground
        for _ in range(6):
            best = max(
                ((x + dx, y + dy) for dx, dy in steps if 0 <= x + dx < width and 0 <= y + dy < height),
                key=lambda p: elev[p[1]][p[0]],
                default=(x, y),
            )
            x, y = best
        for _ in range(width + height):
            water[y][x] = True
            if elev[y][x] < flavor.sea_level:
                break
            lower = [
                (x + dx, y + dy)
                for dx, dy in steps
                if 0 <= x + dx < width and 0 <= y + dy < height and not water[y + dy][x + dx]
            ]
            if not lower:
                break
            nx, ny = min(lower, key=lambda p: elev[p[1]][p[0]])
            if elev[ny][nx] >= elev[y][x] + 0.04:  # stuck in a pit → stop
                break
            x, y = nx, ny


# --- rendering -------------------------------------------------------------


def _land_cell(elev: float, flavor: _Flavor, rng: random.Random) -> Cell:
    """Pick a glyph+style for above-sea land at this elevation."""
    span = max(1e-6, 1.0 - flavor.sea_level)
    t = (elev - flavor.sea_level) / span
    for frac, glyphs, style in flavor.strata:
        if t <= frac:
            if flavor.peak_cap is not None and t > 0.965:
                cap_glyphs, cap_style = flavor.peak_cap
                return rng.choice(cap_glyphs), cap_style
            if flavor.sparkle is not None and rng.random() < 0.05:
                spk_glyphs, spk_style = flavor.sparkle
                return rng.choice(spk_glyphs), spk_style
            return rng.choice(glyphs), style
    glyphs, style = flavor.strata[-1][1], flavor.strata[-1][2]
    return rng.choice(glyphs), style


def _water_cell(elev: float, flavor: _Flavor, rng: random.Random) -> Cell:
    deep = elev < flavor.sea_level - 0.12
    return rng.choice(flavor.water_glyphs), (flavor.deep_style if deep else flavor.water_style)


def _stamp_craters(grid: list[list[Cell]], flavor: _Flavor, rng: random.Random) -> None:
    """Drop a few ring craters onto an airless surface."""
    height, width = len(grid), len(grid[0])
    rim = "grey85"
    for _ in range(flavor.craters):
        cx, cy = rng.randint(2, width - 3), rng.randint(0, height - 1)
        r = rng.randint(1, 2)
        for y in range(max(0, cy - r), min(height, cy + r + 1)):
            for x in range(max(0, cx - r), min(width, cx + r + 1)):
                d = abs(x - cx) + abs(y - cy)
                if d == r:
                    grid[y][x] = (rng.choice("()·"), rim)
                elif d < r:
                    grid[y][x] = (rng.choice("·˳"), "grey30")


def _stamp_storm(grid: list[list[Cell]], flavor: _Flavor, rng: random.Random) -> None:
    """Stamp a gas-giant great-spot oval."""
    if flavor.storm is None:
        return
    glyphs, style = flavor.storm
    height, width = len(grid), len(grid[0])
    cx = rng.randint(width // 3, 2 * width // 3)
    cy = rng.randint(2, height - 3)
    rx, ry = rng.randint(4, 6), rng.randint(1, 2)
    for y in range(height):
        for x in range(width):
            if ((x - cx) / rx) ** 2 + ((y - cy) / max(1, ry)) ** 2 <= 1.0:
                grid[y][x] = (rng.choice(glyphs), style)


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _place_sites(
    grid: list[list[Cell]], sites: list[SurfaceSite], rng: random.Random
) -> None:
    """Stamp each surface site's marker (and a label, once revealed) onto the map."""
    height, width = len(grid), len(grid[0])
    placed: list[tuple[int, int, int]] = []  # (row, x0, x1) keep-out boxes

    def _free(y: int, x0: int, x1: int) -> bool:
        return all(not (y == ry and x0 <= rx1 + 1 and rx0 - 1 <= x1) for ry, rx0, rx1 in placed)

    def _stamp(y: int, x: int, text: str, style: str) -> None:
        for i, ch in enumerate(text):
            if 0 <= x + i < width:
                grid[y][x + i] = (ch, style)

    for site in sites:
        masked = site.marker.strip() == "[?]"
        style = "bright_red" if masked else "bright_yellow"
        revealed = not masked and site.status != "unexplored"
        label = _slug(site.name) if revealed else ""
        full = site.marker + (" " + label if label else "")
        for _ in range(48):
            y = rng.randint(0, height - 1)
            x = rng.randint(1, max(1, width - len(full) - 1))
            if _free(y, x, x + len(full) - 1):
                _stamp(y, x, site.marker, style)
                if label:
                    _stamp(y, x + len(site.marker) + 1, label, "cyan")
                placed.append((y, x, x + len(full) - 1))
                break


def _row_markup(row: list[Cell]) -> str:
    """Serialize a row of cells into a Rich-markup string, run-length grouped by style."""
    parts: list[str] = []
    i, n = 0, len(row)
    while i < n:
        style = row[i][1]
        j = i
        while j < n and row[j][1] == style:
            j += 1
        text = "".join(c[0] for c in row[i:j]).replace("[", r"\[")
        parts.append(text if style is None else f"[{style}]{text}[/]")
        i = j
    return "".join(parts)


def render_terrain(
    planet_type: str,
    sites: list[SurfaceSite],
    *,
    seed: int,
    planet_id: int,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> list[str]:
    """A deterministic, flavored top-down surface map as Rich-markup rows (§7, WP6)."""
    rng = random.Random(f"{seed}|surface|{planet_id}")
    flavor = _flavor_for(planet_type)

    elev = _fbm(width, height, rng, flavor.cell_w, flavor.cell_h)
    water = [[False] * width for _ in range(height)]
    if flavor.sea_level > 0.0:
        _carve_lakes(elev, flavor, rng)
        _carve_rivers(elev, water, flavor, rng)

    grid: list[list[Cell]] = []
    for y in range(height):
        line: list[Cell] = []
        for x in range(width):
            e = elev[y][x]
            if flavor.sea_level > 0.0 and (water[y][x] or e < flavor.sea_level):
                line.append(_water_cell(e, flavor, rng))
            elif rng.random() <= flavor.density:
                line.append(_land_cell(e, flavor, rng))
            else:
                line.append((" ", None))  # void on an airless world
        grid.append(line)

    if flavor.craters:
        _stamp_craters(grid, flavor, rng)
    if flavor.storm is not None:
        _stamp_storm(grid, flavor, rng)
    _place_sites(grid, sites, rng)

    return [_row_markup(row) for row in grid]
