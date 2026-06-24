"""Procedural Discovery art.

Generates perfectly scaled, mathematically driven ASCII art for space discoveries
(anomalies, structures, and wrecks). By using Signed Distance Fields (SDFs) and 
coordinate math instead of fixed 9-slice grammars, astronomical objects like 
nebulas and black holes can be drawn with true circular/elliptical shapes, and 
structures scale geometrically to any requested bounding box.
"""

import random
import math
from rich.text import Text
from opensimplex import OpenSimplex

from edge.art.hull import (
    BRIGHT_CHARS,
    DARK_CHARS,
    MID_CHARS,
    HullStyle,
    render_grid,
    style_for,
)
from edge.art.noise import fractal_noise

# Export the known grammar keys so generator.py knows what subtypes exist.
# Since we use an algorithmic switch, we just list them here to satisfy the API.
DISCOVERY_GRAMMAR = {
    "nebula": True,
    "black_hole": True,
    "wormhole": True,
    "wreck": True,
    "entity": True,
    "ruins": True,
    "artifact": True,
    "ancient_tech": True,
    "crashed_ship": True,
}

class DiscoveryGenerator:
    """Generates dynamic mathematical sprites for space discoveries."""

    @staticmethod
    def _nebula_palette(style: HullStyle, archetype_id: str | None) -> list[str]:
        """The core→rim emission ramp (densest first).

        Emission nebulae glow, so every stop is a saturated, *bright* hue — even the
        faint rim, which covers the most area and would otherwise drag the whole cloud
        toward a muddy dark red. With no owner archetype a nebula reads as a vivid warm
        fire ramp (white-hot core → gold → orange → rose → magenta). When an archetype
        applies, the cloud is tinted from that owner's saturated nav-light/window hues
        (never the dull hull-plating greys), the same way ports and ships vary by owner.
        """
        if archetype_id is None:
            return ["#ffffff", "#fff27a", "#ffb13b", "#ff6a2a", "#ff2e6e", "#d22bb8"]
        # Saturated owner hues, brightest first; skip the grey bright/mid/dark plating.
        return ["#ffffff", style.window[0], style.top[0],
                style.top[-1], style.bottom[0], style.bottom[-1]]

    def _generate_nebula(self, rng: random.Random, width: int, height: int,
                         archetype_id: str | None = None) -> Text:
        """A gaseous cloud as a domain-warped fractal-noise density field.

        Unlike the other (analytic-icon) discovery subtypes, a nebula is literally
        gas, so it uses the coherent-noise idiom shared by `terrain`/`starfield`:
        a multi-octave noise density field (domain-warped for wispy curl) gives the
        interior tendrils, cores, and voids, while a soft radial envelope fades the
        edges to space. Both the shade ramp and colour are driven by that density
        (so colour tracks structure, not radius), and the palette is archetype-aware.
        """
        palette = self._nebula_palette(style_for(archetype_id), archetype_id)
        gen = OpenSimplex(seed=rng.randint(0, 2**31 - 1))

        radius_x = width / 2.0
        radius_y = height / 2.0
        offset_x = rng.uniform(-0.12, 0.12) * radius_x
        offset_y = rng.uniform(-0.12, 0.12) * radius_y
        center_x = (width - 1) / 2.0 + offset_x
        center_y = (height - 1) / 2.0 + offset_y

        # Angular harmonics make the *envelope* lopsided (cheap asymmetry); texture
        # comes from the noise field, not from these.
        bulge_p1, bulge_p2, bulge_p3 = (rng.uniform(0, math.pi * 2) for _ in range(3))
        bulge_a1 = rng.uniform(0.10, 0.22)
        bulge_a2 = rng.uniform(0.05, 0.13)
        bulge_a3 = rng.uniform(0.10, 0.22)

        # Feature sizes relative to the sprite: a mid-scale density field, a coarser
        # field warping the sample coords for the signature curl.
        scale = max(6.0, width * 0.7)
        warp_scale = max(10.0, width * 1.4)
        warp_amp = width * 0.22

        # A second, anisotropic field paints cool blue emission *streaks* woven through
        # the warm gas (a bicolour nebula look). Stretching the sample coords along one
        # axis makes the features read as filaments rather than blobs. Kept to the
        # default (ownerless) palette so archetype-tinted clouds stay one owner hue.
        blue_streaks = archetype_id is None
        blue_ramp = ["#eaf4ff", "#9ad0ff", "#4aa3ff", "#2f6bff"]
        blue_scale = max(5.0, width * 0.42)

        def streak_field(px: float, py: float) -> float:
            # Anisotropic sample (stretched coords ⇒ directional filaments).
            return fractal_noise(gen, (px + 500.0) * 0.45, (py + 500.0) * 1.6, blue_scale, 3)

        map_text = Text()
        n_pal = len(palette)
        n_blue = len(blue_ramp)
        space_cut = 0.16  # density floor — below this the cell is open space
        peak = 0.72       # density that reads fully white-hot (top of the colour ramp)
        for y in range(height):
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                d = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)
                bulge = (
                    math.sin(angle * 2 + bulge_p1) * bulge_a1
                    + math.cos(angle * 3 + bulge_p2) * bulge_a2
                    + math.sin(angle + bulge_p3) * bulge_a3
                )
                radius_mult = max(0.55, 1.0 + bulge)
                # Smooth envelope: 1 at the core, easing to 0 past the bulged edge.
                env = max(0.0, 1.0 - d / radius_mult)
                env = env * env * (3.0 - 2.0 * env)  # smoothstep

                # Domain-warp the sample coords, then read the multi-octave field.
                wx = fractal_noise(gen, x + 100.0, y, warp_scale, 2) * warp_amp
                wy = fractal_noise(gen, x, y + 100.0, warp_scale, 2) * warp_amp
                n01 = (fractal_noise(gen, x + wx, y + wy, scale, 4) + 1.0) / 2.0
                density = n01 * env

                if density < space_cut:
                    map_text.append(" ")  # space — stars show through when composited
                    continue
                if density < 0.30:
                    char = "░"
                elif density < 0.45:
                    char = "▒"
                elif density < 0.62:
                    char = "▓"
                else:
                    char = "█"

                # Colour tracks structure: stretch the palette across the visible
                # density band so dense cores reach the hot head (white/yellow) and
                # thin wisps take the cool rim hue, rather than clustering mid-ramp.
                ct = (density - space_cut) / (peak - space_cut)
                ct = max(0.0, min(1.0, ct))

                # Blue filaments trace the zero-crossing contours of the anisotropic
                # field. Normalising the contour distance by the local gradient keeps
                # streaks a constant ~1–2 cells wide (instead of blobbing where the
                # field is flat), so every cloud gets a few thin threads.
                ramp, n_ramp = palette, n_pal
                if blue_streaks:
                    s = streak_field(x, y)
                    sx = streak_field(x + 1, y) - streak_field(x - 1, y)
                    sy = streak_field(x, y + 1) - streak_field(x, y - 1)
                    grad = math.hypot(sx, sy) * 0.5 + 1e-6
                    # Contour a *periodic* phase of the field so several parallel
                    # filaments (not just one zero-crossing) thread the cloud; the
                    # gradient normalisation keeps each ~1 cell wide.
                    phase = s / 0.55
                    dist_cells = abs(phase - round(phase)) * 0.55 / grad
                    if dist_cells < 0.85:
                        ramp, n_ramp = blue_ramp, n_blue
                idx = int((1.0 - ct) * (n_ramp - 1) + 0.5)
                map_text.append(char, style=f"bold {ramp[idx]}")

            if y < height - 1:
                map_text.append("\n")

        return map_text

    # The accretion-disk glow ramp, hottest first: white-hot inner edge → gold →
    # orange → red rim. A black hole is not archetype-tinted — the glow is the light
    # of doomed matter, the same colour for any owner — so this is a fixed ramp.
    _BLACK_HOLE_PALETTE = ["#ffffff", "#ffe25a", "#ffae3a", "#ff6a2a", "#ff2e2e"]

    def _generate_black_hole(self, rng: random.Random, width: int, height: int) -> Text:
        """A Gargantua-style black hole: a glowing edge-on accretion disk straight
        through the middle, a gravitational-lensing halo ring arcing over and under a
        dark event horizon, and a white-hot photon ring hugging the horizon.

        Like the other icon subtypes this is analytic (no noise): every cell's
        *intensity* in [0,1] is the max of three fields — photon ring, lensing halo,
        and accretion disk — zeroed inside the event horizon. Intensity drives both
        the shade ramp (█▓▒░) and the colour (hot white core → red rim), so the glow
        fills the frame and the dark sits only at the centre.
        """
        palette = self._BLACK_HOLE_PALETTE
        n_pal = len(palette)

        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        radius_x = width / 2.0
        radius_y = height / 2.0

        R_EH = 0.20          # event-horizon radius (the dark hole)
        PHOTON_W = 0.07      # white-hot photon ring just outside the horizon
        R_HALO = 0.72        # radius of the lensing halo ring (the top/bottom arcs)
        HALO_W = 0.30        # halo thickness falloff
        THICK_C = 0.46       # disk half-thickness (in dy) at the centre
        THICK_E = 0.12       # disk half-thickness at the frame edge

        def smoothstep(s: float) -> float:
            s = max(0.0, min(1.0, s))
            return s * s * (3.0 - 2.0 * s)

        map_text = Text()
        floor = 0.16  # below this a cell is open space (stars show through)
        for y in range(height):
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                r = math.sqrt(dx * dx + dy * dy)

                if r < R_EH:
                    map_text.append(" ")  # event horizon — pure dark
                    continue

                # Photon ring: a thin white-hot annulus on the horizon's lip.
                photon = 1.0 if r < R_EH + PHOTON_W else 0.0

                # Lensing halo: a bright ring at R_HALO, soft-edged — its top and
                # bottom are the arcs that cap the silhouette.
                halo = smoothstep(1.0 - abs(r - R_HALO) / HALO_W)

                # Accretion disk: an edge-on band centred on dy=0, fat at the centre
                # and thinning toward the edges, reaching the full frame width. Its
                # brightness eases down with |dx| so the rim runs red, not dark.
                adx = min(1.0, abs(dx))
                thick = THICK_C - (THICK_C - THICK_E) * adx
                disk = max(0.0, 1.0 - abs(dy) / thick) * (1.0 - 0.30 * adx)

                intensity = max(photon, halo, disk)
                intensity += rng.uniform(-0.04, 0.04)  # faint grain (seeded)

                if intensity < floor:
                    map_text.append(" ")
                    continue
                if intensity < 0.34:
                    char = "░"
                elif intensity < 0.52:
                    char = "▒"
                elif intensity < 0.72:
                    char = "▓"
                else:
                    char = "█"
                ct = max(0.0, min(1.0, intensity))
                idx = int((1.0 - ct) * (n_pal - 1) + 0.5)
                map_text.append(char, style=f"bold {palette[idx]}")

            if y < height - 1:
                map_text.append("\n")

        return map_text

    # The vortex glow ramp, brightest first: white-hot throat → pale cyan → sky
    # blue → deep blue → violet rim. Cool exotic-energy hues, deliberately the
    # cold inverse of the black hole's hot accretion ramp so the two read apart.
    _WORMHOLE_PALETTE = ["#ffffff", "#9fe8ff", "#46c4ff", "#2f7bff", "#6a3cff"]

    def _generate_wormhole(self, rng: random.Random, width: int, height: int) -> Text:
        """A face-on swirling vortex: two or three logarithmic-spiral arms winding
        into a white-hot throat — the light at the tunnel's end — fading to space at
        the rim, glowing in cold blue/violet exotic-energy hues.

        Like the black hole this is analytic: each cell's *intensity* in [0,1] comes
        from a radial funnel envelope modulated by a spiral arm field, with the throat
        pinned bright. Intensity drives both the shade ramp (█▓▒░) and the colour
        (white throat → violet rim), so the swirl fills the frame with structure
        rather than flat grey.
        """
        palette = self._WORMHOLE_PALETTE
        n_pal = len(palette)

        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        radius_x = width / 2.0
        radius_y = height / 2.0

        arms = rng.choice((2, 3))         # two- or three-armed spiral
        spin = rng.uniform(0.0, math.tau)  # rotational phase, per sprite
        twist = rng.uniform(5.5, 7.5)      # how tightly the arms wind inward
        R_THROAT = 0.14                    # the bright open throat

        def smoothstep(s: float) -> float:
            s = max(0.0, min(1.0, s))
            return s * s * (3.0 - 2.0 * s)

        map_text = Text()
        floor = 0.16  # below this a cell is open space (stars show through)
        for y in range(height):
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                r = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)

                # Radial funnel: a broad glow reaching the frame edges (touching the
                # edge midpoints at r=1, leaving only the corners as space).
                env = max(0.0, 1.0 - (r / 1.35) ** 2)
                # Spiral arms winding into the throat; sharpened so bright arms
                # alternate with dimmer gaps without ever going fully dark.
                swirl = math.sin(arms * angle - twist * r + spin)
                arm = (0.5 + 0.5 * swirl) ** 1.5
                # A smooth central glow guarantees the throat is the brightest point
                # regardless of which arm phase falls on centre.
                core = smoothstep((0.34 - r) / 0.34)
                intensity = max(env * (0.40 + 0.70 * arm), core)

                if r < R_THROAT:
                    intensity = 1.0  # the open throat — light at the tunnel's end
                else:
                    intensity += rng.uniform(-0.04, 0.04)  # faint grain (seeded)

                # Faint sparkle of exotic energy flung out past the arms.
                if 0.10 < intensity < floor and rng.random() < 0.12:
                    map_text.append("·", style="bold #9fe8ff")
                    continue
                if intensity < floor:
                    map_text.append(" ")
                    continue
                if intensity < 0.34:
                    char = "░"
                elif intensity < 0.52:
                    char = "▒"
                elif intensity < 0.74:
                    char = "▓"
                else:
                    char = "█"
                ct = max(0.0, min(1.0, intensity))
                idx = int((1.0 - ct) * (n_pal - 1) + 0.5)
                map_text.append(char, style=f"bold {palette[idx]}")

            if y < height - 1:
                map_text.append("\n")

        return map_text

    def _generate_wreck(self, rng: random.Random, width: int, height: int,
                        archetype_id: str | None = None) -> Text:
        """A field of scattered space debris: one large broken hull mass plus
        smaller fragments drifting around it, with a thinning halo of specks.

        Unlike the glowing phenomena, a wreck is solid metal, so it builds a glyph
        grid and goes through ``render_grid`` — keeping the grey/archetype-tinted
        hull tones and the occasional window glint of a still-powered console. Each
        chunk is an irregular, jagged-edged blob (rotated, elongated, with a sinusoid
        on its rim) so the silhouette reads as torn wreckage, never a clean disk.
        """
        style = style_for(archetype_id)
        top_color = rng.choice(style.top)
        bottom_color = rng.choice(style.bottom)

        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        radius_x = width / 2.0
        radius_y = height / 2.0

        # A handful of debris chunks: a large broken hull mass near the centre,
        # the rest smaller fragments flung out around it. Each carries a jagged-rim
        # spec (frequency / phase / amplitude) so no edge is smooth.
        n_chunks = rng.randint(3, 5)
        chunks = []
        for i in range(n_chunks):
            if i == 0:
                cx = rng.uniform(-0.18, 0.18)
                cy = rng.uniform(-0.15, 0.15)
                cr = rng.uniform(0.42, 0.55)
            else:
                ang = rng.uniform(0.0, math.tau)
                dist = rng.uniform(0.42, 0.88)
                cx = math.cos(ang) * dist
                cy = math.sin(ang) * dist
                cr = rng.uniform(0.12, 0.27)
            chunks.append((
                cx, cy, cr,
                rng.uniform(0.55, 1.0),         # elongation
                rng.uniform(0.0, math.tau),     # rotation
                float(rng.choice((4, 5, 6))),   # jag frequency
                rng.uniform(0.0, math.tau),     # jag phase
                rng.uniform(0.12, 0.22),        # jag amplitude
            ))

        # All hull-set glyphs (render as plating tones over the void): torn corners
        # and plate shards for chunk rims, dark specks/struts for drifting debris.
        rim_glyphs = ("▙", "▟", "▛", "▜", "◣", "◢", "◤", "◥", "▄", "▀")
        speck_glyphs = ("░", "▒", "░", "╱", "╲")

        rows = []
        for y in range(height):
            row_chars = []
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y

                # Distance to the nearest chunk, as a ratio of that chunk's jagged
                # edge radius (<1 ⇒ inside the chunk).
                best = 9.0
                for cx, cy, cr, elong, rot, jf, jp, ja in chunks:
                    ox, oy = dx - cx, dy - cy
                    rx = ox * math.cos(rot) + oy * math.sin(rot)
                    ry = (-ox * math.sin(rot) + oy * math.cos(rot)) / elong
                    rd = math.hypot(rx, ry)
                    edge = cr * (1.0 + ja * math.sin(math.atan2(ry, rx) * jf + jp))
                    if edge > 0:
                        best = min(best, rd / edge)

                if best < 0.62:
                    char = "█" if rng.random() > 0.28 else "▓"
                elif best < 0.98:
                    char = rng.choice(rim_glyphs) if rng.random() > 0.30 else "▒"
                else:
                    # Scattered debris drifting away, thinning with distance.
                    d = math.hypot(dx, dy)
                    if rng.random() < max(0.0, 0.24 - 0.20 * d):
                        char = rng.choice(speck_glyphs)
                    else:
                        char = " "
                row_chars.append(char)
            rows.append("".join(row_chars))

        return render_grid(rows, style, top_color, bottom_color, rng, width, height)

    def generate(
        self,
        rng: random.Random,
        subtype: str,
        width: int,
        height: int,
        archetype_id: str | None = None,
    ) -> Text:
        """Generate a procedural discovery sprite, hued by archetype."""
        if subtype == "nebula":
            return self._generate_nebula(rng, width, height, archetype_id)
        if subtype == "black_hole":
            return self._generate_black_hole(rng, width, height)
        if subtype == "wormhole":
            return self._generate_wormhole(rng, width, height)
        if subtype == "wreck":
            return self._generate_wreck(rng, width, height, archetype_id)

        style = style_for(archetype_id)
        
        top_color = rng.choice(style.top)
        bottom_color = rng.choice(style.bottom)

        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        radius_x = width / 2.0
        radius_y = height / 2.0

        rows = []
        for y in range(height):
            row_chars = []
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                d_sq = dx * dx + dy * dy
                d = math.sqrt(d_sq) if d_sq > 0 else 0

                char = " "

                if subtype == "artifact":
                    # Pristine mathematical diamond
                    manhattan = abs(dx) + abs(dy)
                    if manhattan < 0.9:
                        if manhattan < 0.3: char = "█"
                        elif manhattan < 0.6: char = "▓"
                        else: char = "▒"
                        if manhattan < 0.9 and manhattan > 0.8:
                            char = "◇"

                elif subtype == "ruins":
                    # Ziggurat / Pyramid shape (stepped)
                    step_y = int((dy + 1.0) * 5) / 5.0 # 0 to 2
                    allowed_dx = step_y * 0.8
                    if dy > -0.5 and abs(dx) < allowed_dx:
                        char = "█"
                        if rng.random() < 0.2: char = "▒"
                        if abs(dx) > allowed_dx - 0.2: 
                            char = "│"

                elif subtype == "entity":
                    # Crystalline star shape
                    star_d = abs(dx) + abs(dy) + max(abs(dx), abs(dy))
                    if star_d < 1.2:
                        char = "█"
                        if star_d > 0.8: char = "▒"
                        if abs(dx) < 0.1 or abs(dy) < 0.1: char = "◇"
                        if d < 0.2: char = "R"

                elif subtype == "ancient_tech":
                    # Octagonal / Gear-like machinery
                    oct_d = max(abs(dx), abs(dy), (abs(dx) + abs(dy)) * 0.7)
                    if oct_d < 0.8:
                        if oct_d < 0.2: char = " " # Hollow core
                        elif oct_d < 0.3: char = "R" # Inner ring
                        elif oct_d > 0.7: char = "≡" # Outer treads
                        else: 
                            char = "█" if rng.random() > 0.3 else "▓"

                elif subtype == "crashed_ship":
                    # Angled swath of debris
                    line_d = abs(dx - dy) # diagonal line
                    if d < 0.9 and line_d < 0.3:
                        prob = max(0, 1.0 - d - line_d * 2)
                        if rng.random() < prob:
                            if line_d < 0.1 and d < 0.5: char = "█"
                            elif d < 0.7: char = "▓"
                            else: char = "▒"

                else:
                    # Fallback to an orb
                    if d < 0.8: char = "█"

                row_chars.append(char)
            rows.append("".join(row_chars))

        return render_grid(rows, style, top_color, bottom_color, rng, width, height)
