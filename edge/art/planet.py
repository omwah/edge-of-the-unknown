"""Procedural planet generation using Signed Distance Fields."""

import random
import math
from rich.text import Text
from edge.art.terrain import TerrainGenerator

def get_outline_char(u: bool, d: bool, l: bool, r: bool,
                     ne: bool, nw: bool, se: bool, sw: bool) -> str:
    """Pick a connecting box-drawing glyph for a boundary cell.

    Selection is driven by which sides of the cell face the *exterior* of the
    planet (``True`` == that neighbour is outside the disc). Because the glyph
    is derived from the local boundary tangent, adjacent boundary cells emit
    glyphs that link into a continuous ring rather than a chunky octagon.
    """
    vert = u or d  # exterior lies above and/or below -> boundary runs horizontally
    horz = l or r  # exterior lies left and/or right  -> boundary runs vertically

    if vert and horz:
        # Convex corner: connect the two interior-facing sides.
        v = "u" if u else "d"
        h = "l" if l else "r"
        return {
            ("u", "l"): "╭", ("u", "r"): "╮",
            ("d", "l"): "╰", ("d", "r"): "╯",
        }[(v, h)]
    if vert:
        return "─"
    if horz:
        return "│"
    # Only a diagonal neighbour is exterior: a steep shoulder step. The two
    # orthogonal boundary cells flanking it are a horizontal run and a vertical
    # run, so connect toward both with the matching box-curve glyph.
    if nw:
        return "╯"
    if ne:
        return "╰"
    if sw:
        return "╮"
    if se:
        return "╭"
    return " "

ATMOSPHERE_COLORS = {
    "terrestrial_warm": "bright_cyan",
    "terrestrial_cool": "cyan",
    "terrestrial_hot": "bright_red",
    "terrestrial_cold": "bright_white",
    "jovian": "bright_yellow",
    "barren": "bright_black",
}

def get_atmosphere_color(subtype: str) -> str:
    """Return the atmospheric outline color based on the planet subtype."""
    return ATMOSPHERE_COLORS.get(subtype.lower(), "bright_white")

# Shadow-side fill backgrounds: a dark-grey ramp used in place of pure black so
# the planet's shaded crescent still reads as part of the disc when composited
# over the black starfield void. Collapsing a shaded cell to "black" (#000000)
# makes it indistinguishable from empty space, which breaks the sphere
# silhouette on the main game screen -- so the dimming never goes fully black.
SHADOW_BG_DEEP = "grey11"  # #1c1c1c -- darkest night side, still above the void
SHADOW_BG_MID = "grey15"   # #262626
SHADOW_BG_NEAR = "grey19"  # #303030 -- just inside the terminator

class PlanetGenerator:
    """Procedural planet generator using SDF masks over terrain fills."""
    
    def __init__(self, terrain_gen: TerrainGenerator):
        self.terrain_gen = terrain_gen
        
    @property
    def biomes_registry(self) -> dict:
        """Expose the terrain's biome registry for iteration in CLI."""
        return self.terrain_gen.biomes_registry

    def generate(self, rng: random.Random, subtype: str, width: int, height: int) -> Text:
        """Generate a procedural planet wrapped in a circular SDF."""
        grid = self.terrain_gen.get_grid(rng, subtype, width, height)
        map_text = Text()

        is_asteroid = subtype.lower() in ("asteroid_belt", "asteroid")
        outline_color = get_atmosphere_color(subtype)

        if is_asteroid:
            # Pass through directly without border or spherical mask.
            for y in range(height):
                for x in range(width):
                    char, fg, _ = grid[y][x]
                    map_text.append(char, style=fg)
                if y < height - 1:
                    map_text.append("\n")
            return map_text

        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        radius_x = width / 2.0
        radius_y = height / 2.0

        # Precompute the disc membership mask so boundary cells can be found by
        # inspecting their neighbours instead of binning a thick angular band.
        dist_sq = [[0.0] * width for _ in range(height)]
        inside = [[False] * width for _ in range(height)]
        for y in range(height):
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                d = dx * dx + dy * dy
                dist_sq[y][x] = d
                inside[y][x] = d <= 1.0

        def is_exterior(px: int, py: int) -> bool:
            """A cell off the grid or outside the disc counts as exterior."""
            if px < 0 or py < 0 or px >= width or py >= height:
                return True
            return not inside[py][px]

        # Light vector (coming from top-left-front)
        Lx, Ly, Lz = -0.7, -0.3, 0.6
        length = math.sqrt(Lx*Lx + Ly*Ly + Lz*Lz)
        Lx, Ly, Lz = Lx/length, Ly/length, Lz/length

        for y in range(height):
            for x in range(width):
                if not inside[y][x]:
                    map_text.append(" ", style="black")
                    continue

                u = is_exterior(x, y - 1)
                d = is_exterior(x, y + 1)
                l = is_exterior(x - 1, y)
                r = is_exterior(x + 1, y)
                ne = is_exterior(x + 1, y - 1)
                nw = is_exterior(x - 1, y - 1)
                se = is_exterior(x + 1, y + 1)
                sw = is_exterior(x - 1, y + 1)

                if u or d or l or r or ne or nw or se or sw:
                    # Boundary cell: draw a connecting outline glyph.
                    char = get_outline_char(u, d, l, r, ne, nw, se, sw)

                    # Dim the outline if it sits on the dark side of the planet.
                    dx = (x - center_x) / radius_x
                    dy = (y - center_y) / radius_y
                    norm = math.sqrt(dist_sq[y][x]) or 1.0
                    outline_dot = (dx / norm) * Lx + (dy / norm) * Ly
                    style = f"dim {outline_color}" if outline_dot < -0.2 else outline_color
                    map_text.append(char, style=style)
                else:
                    # Interior terrain fill with spherical lighting.
                    char, fg, bg = grid[y][x]

                    # Prevent the planet surface from turning invisible in the void.
                    if not bg or bg in ("black", "default"):
                        bg = "bright_black"

                    dx = (x - center_x) / radius_x
                    dy = (y - center_y) / radius_y
                    z = math.sqrt(max(0.0, 1.0 - dist_sq[y][x]))
                    dot = dx*Lx + dy*Ly + z*Lz

                    # Apply shadow dithering based on dot product. The block glyph
                    # paints the terrain colour over a dark-grey fill; darker tiers
                    # use sparser ink so the surface fades toward grey -- never to
                    # pure black, which would merge the night side into the void.
                    #
                    # The terrain generator is bg-only (use_fg_color=False), so each
                    # cell's surface colour lives in `bg`. A block glyph only shows
                    # colour through its foreground, so each tier promotes that
                    # surface colour into `fg`, then sets `bg` to the dark backing.
                    # (The guard above has already replaced any black/default bg, so
                    # `bg` here is always a visible colour.)
                    if dot < -0.1:
                        char = "░"
                        fg = bg
                        bg = SHADOW_BG_DEEP
                    elif dot < 0.15:
                        char = "▒"
                        fg = bg
                        bg = SHADOW_BG_MID
                    elif dot < 0.4:
                        char = "▓"
                        fg = bg
                        bg = SHADOW_BG_NEAR
                    else:
                        char = "█"
                        fg = bg
                        bg = None

                    if bg and bg not in ("black", "default"):
                        style = f"{fg} on {bg}" if fg else f"on {bg}"
                    else:
                        style = fg
                    map_text.append(char, style=style)

            if y < height - 1:
                map_text.append("\n")

        return map_text
