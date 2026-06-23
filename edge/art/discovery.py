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

from edge.art.hull import (
    BRIGHT_CHARS,
    DARK_CHARS,
    MID_CHARS,
    HullStyle,
    render_grid,
    style_for,
)

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

    def _generate_nebula(self, rng: random.Random, width: int, height: int) -> Text:
        """Draws a vibrant, multi-colored gas cloud."""
        # Offset the core slightly from the exact geometric center
        # Offset the core slightly from the exact geometric center
        # Using standard width/2.0 radius
        radius_x = width / 2.0
        radius_y = height / 2.0
        offset_x = rng.uniform(-0.15, 0.15) * radius_x
        offset_y = rng.uniform(-0.15, 0.15) * radius_y
        
        center_x = (width - 1) / 2.0 + offset_x
        center_y = (height - 1) / 2.0 + offset_y

        # User-requested fire palette: White core -> Yellow -> Orange -> Red outer
        nebula_gradient = [
            "bright_white",
            "bright_yellow",
            "orange1",
            "dark_orange",
            "bright_red",
            "red"
        ]
        
        # Generate organic macro-distortion parameters for a mildly lopsided cloud
        bulge_p1 = rng.uniform(0, math.pi * 2)
        bulge_p2 = rng.uniform(0, math.pi * 2)
        bulge_p3 = rng.uniform(0, math.pi * 2)
        
        # Gently boosted amplitudes for moderate organic waviness
        bulge_a1 = rng.uniform(0.1, 0.25)  # 2-lobed stretch
        bulge_a2 = rng.uniform(0.05, 0.15) # 3-lobed stretch
        bulge_a3 = rng.uniform(0.1, 0.25)  # 1-lobed offset
        
        map_text = Text()
        for y in range(height):
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                d = math.sqrt(dx * dx + dy * dy)
                
                # Apply macroscopic organic bulges based on angle for organic asymmetry
                angle = math.atan2(dy, dx)
                bulge = (
                    math.sin(angle * 2 + bulge_p1) * bulge_a1 + 
                    math.cos(angle * 3 + bulge_p2) * bulge_a2 +
                    math.sin(angle + bulge_p3) * bulge_a3
                )
                
                # Scale the boundary by the bulge. Modest floor to prevent extreme pinching.
                radius_mult = max(0.5, 1.0 + bulge)
                organic_d = d / radius_mult
                
                # Keep some high-frequency pixel noise for gaseous texture
                noise = rng.uniform(-0.15, 0.15)
                fuzzy_d = organic_d + noise
                
                if fuzzy_d < 0.3:
                    char = "█"
                elif fuzzy_d < 0.6:
                    char = "▓"
                elif fuzzy_d < 0.9:
                    char = "▒"
                elif fuzzy_d < 1.1:
                    char = "░"
                else:
                    char = " "
                
                if char == " ":
                    map_text.append(" ")
                else:
                    # Smooth radial gradient from the core outward
                    # fuzzy_d naturally ranges from ~0.0 at the core to ~1.1 at the edges
                    normalized_d = max(0.0, min(1.0, fuzzy_d / 1.1))
                    
                    color_idx = int(normalized_d * len(nebula_gradient))
                    if color_idx >= len(nebula_gradient):
                        color_idx = len(nebula_gradient) - 1
                        
                    color = nebula_gradient[color_idx]
                    map_text.append(char, style=f"bold {color} on black")
            
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
            return self._generate_nebula(rng, width, height)

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
