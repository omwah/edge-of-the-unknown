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
                
                if subtype == "black_hole":
                    # Elliptical accretion disk, dark center (event horizon)
                    tilt_x = dx * 0.8 + dy * 0.6
                    tilt_y = -dx * 0.6 + dy * 0.8
                    disk_d = tilt_x * tilt_x + (tilt_y * 2.5) ** 2
                    
                    if d_sq < 0.15:
                        char = " " # Event horizon
                    elif disk_d < 1.0 and d_sq > 0.1:
                        # Accretion disk
                        if disk_d < 0.3: char = "█"
                        elif disk_d < 0.6: char = "▓"
                        elif disk_d < 0.8: char = "▒"
                        else: char = "░"
                    elif d_sq < 0.25:
                        # Photon ring edge glow
                        char = "R" if rng.random() > 0.5 else "Y"

                elif subtype == "wormhole":
                    # Swirling vortex: a two-armed spiral funnelling into a bright
                    # throat (distinct from the black hole's tilted accretion disk).
                    angle = math.atan2(dy, dx)
                    swirl = math.sin(angle * 2.0 - d * 6.5)
                    if d < 0.18:
                        char = "◉"  # the open throat
                    elif d < 1.0:
                        if swirl > 0.45:
                            char = "█" if d < 0.5 else "▓"
                        elif swirl > -0.1:
                            char = "▒" if d < 0.7 else "░"
                        elif d > 0.85:
                            char = "·"

                elif subtype == "nebula":
                    # Handled above
                    pass

                elif subtype == "artifact":
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

                elif subtype == "wreck":
                    # Circular debris field, heavy center
                    if d < 0.8:
                        prob = max(0, 1.0 - d * 1.5)
                        if rng.random() < prob:
                            if d < 0.2: char = "█"
                            elif d < 0.4: char = "▓"
                            else: char = rng.choice(["▒", "░", "╱", "╲"])

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
