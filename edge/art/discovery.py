"""Procedural Discovery art.

Generates perfectly scaled, mathematically driven ASCII art for space discoveries
(anomalies, structures, and wrecks). By using Signed Distance Fields (SDFs) and 
coordinate math instead of fixed 9-slice grammars, astronomical objects like 
nebulas and black holes can be drawn with true circular/elliptical shapes, and 
structures scale geometrically to any requested bounding box.
"""

import random
import math
from dataclasses import dataclass, replace
from rich.color import Color
from rich.text import Text
from opensimplex import OpenSimplex

from edge.art.hull import (
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

# ---------------------------------------------------------------------------
# Surface-scene scaffold
#
# The four *surface-site* subtypes (ruins / artifact / ancient_tech /
# crashed_ship) are not free-floating icons — they are places **on a planet**.
# So instead of the hull-plating ``render_grid`` path they build a ``rich.Text``
# directly (per cell, like ``_generate_entity``), painting an exotic *alien-dusk*
# sky above a textured ground, with the discovery structure overlaid on top.
# Each sprite picks one dusk palette per seed, so repeated finds feel like
# different worlds; a structure's *accent* (lights / chevrons / windows / stone
# highlight) borrows the owner archetype's window hue when one applies.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Scene:
    """A surface backdrop: a single, uniform daylight sky colour and a solid
    sunlit ground colour. Both are flat — no gradient, no noise, no stars — so the
    structure in front reads cleanly against a high-contrast background."""

    sky: str
    ground: str


# One bright, uniform daylight sky for every scene; the ground tint varies a
# little per find (different planet soils) so repeats don't look identical.
_DAY_SKY = "#5aa0e0"
_GROUNDS = ("#9a7a48", "#8f7250", "#a07c44", "#8a6e40")
_DAY_SCENES: tuple[_Scene, ...] = tuple(_Scene(_DAY_SKY, g) for g in _GROUNDS)

# Cool stone and grey hull ramps (bright → mid → dark); sunlit grass for the hill.
_STONE = ("#b3b9c6", "#878d9c", "#565b6a")
_HULL = ("#9aa0aa", "#70757f", "#494d56")
_GRASS = "#5a9e3e"


def _hx(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def _clamp8(v: float) -> int:
    return 0 if v < 0 else 255 if v > 255 else int(v)


def _hex(r: float, g: float, b: float) -> str:
    return f"#{_clamp8(r):02x}{_clamp8(g):02x}{_clamp8(b):02x}"


def _mix(a: str, b: str, t: float) -> str:
    """Linear blend between two ``#rrggbb`` colours (t=0 → a, t=1 → b)."""
    ra, ga, ba = _hx(a)
    rb, gb, bb = _hx(b)
    return _hex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t)


def _shade(c: str, f: float) -> str:
    """Scale a colour's brightness by ``f`` (clamped per channel)."""
    r, g, b = _hx(c)
    return _hex(r * f, g * f, b * f)


def _pick_scene(rng: random.Random) -> _Scene:
    return rng.choice(_DAY_SCENES)


def _to_hex(c: str) -> str:
    """Normalise a colour to ``#rrggbb`` so it can be blended (the hull palette
    uses Rich *named* colours like ``bright_cyan``, which ``_mix`` can't parse)."""
    if c.startswith("#"):
        return c
    t = Color.parse(c).get_truecolor()
    return _hex(t.red, t.green, t.blue)


def _accent_hue(archetype_id: str | None, fallback: str) -> str:
    """The structure accent (always hex): the owner archetype's window hue when one
    applies, otherwise the subtype's fixed fallback. (``style_for(None)`` resolves to
    the grey default, so a missing archetype must short-circuit to ``fallback``.)"""
    if archetype_id is None:
        return fallback
    return _to_hex(style_for(archetype_id).window[0])


def _horizon(height: int) -> int:
    """The row where ground meets sky (ground ≈ the bottom ~38%), clamped small."""
    return min(height - 1, max(2, round(height * 0.62)))


def _base_cell(scene: _Scene, y: int, horizon: int) -> tuple[str, str]:
    """The flat backdrop behind the structure: solid daylight sky above the
    horizon, solid sunlit ground below — a blank cell painted as a background
    colour, so nothing in the background competes with the foreground."""
    return " ", f"on {scene.sky if y < horizon else scene.ground}"


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

    # The body glow ramp, brightest first: lit subsurface violet → bruised purple →
    # deep void. An eldritch horror is its own otherworldly thing, so (like the black
    # hole and wormhole) it ignores archetype tint and owns this sickly palette.
    _ENTITY_BODY = ["#d49bff", "#a64ad0", "#732aa8", "#4a1a6e", "#280e44"]
    # The eyes glow a luminous, sickly green — the cold complement of the violet flesh,
    # brightest at the pupil — so a dozen of them seem to stare out of the dark mass.
    _ENTITY_EYE = ["#eaffbe", "#b6ff4a", "#7ad62a", "#2e5e16"]

    def _generate_entity(self, rng: random.Random, width: int, height: int) -> Text:
        """A planet-sized eldritch horror: a vast amorphous body of bruised violet
        flesh, writhing tentacles groping out past its edge, and a constellation of
        luminous green eyes staring from the dark mass.

        Like the other cosmic phenomena this is analytic and archetype-independent.
        A per-angle *reach* function (low harmonics for the lumpy body + narrow,
        slowly-writhing bumps for the tentacles) sets the silhouette; body *depth*
        drives a veined subsurface glow; a seeded set of eyes is overlaid on top.
        """
        body_pal = self._ENTITY_BODY
        eye_pal = self._ENTITY_EYE
        n_body, n_eye = len(body_pal), len(eye_pal)

        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        radius_x = width / 2.0
        radius_y = height / 2.0

        R0 = 0.74  # base body radius — planet-sized, fills the frame
        # Lumpy-outline harmonics + veining/pulse phases, drawn once per sprite.
        p1, p2, p3 = (rng.uniform(0.0, math.tau) for _ in range(3))
        vphase = rng.uniform(0.0, math.tau)
        pphase = rng.uniform(0.0, math.tau)

        # Writhing tentacles: a narrow angular bump each, its centreline slowly
        # snaking with radius so the arm curves rather than spikes straight out.
        tentacles = []
        for _ in range(rng.randint(5, 8)):
            tentacles.append((
                rng.uniform(0.0, math.tau),     # base angle
                rng.uniform(0.16, 0.30),        # angular width
                rng.uniform(0.30, 0.62),        # extra reach (past the body)
                rng.uniform(0.10, 0.26),        # writhe amplitude
                rng.uniform(3.0, 5.0),          # writhe frequency (in r)
                rng.uniform(0.0, math.tau),     # writhe phase
            ))

        # Eyes: one great eye near the core, the rest scattered across the body.
        eyes = []
        for i in range(rng.randint(5, 8)):
            if i == 0:
                ex, ey, er = (rng.uniform(-0.12, 0.12), rng.uniform(-0.10, 0.10),
                              rng.uniform(0.18, 0.24))
            else:
                ea, edist = rng.uniform(0.0, math.tau), rng.uniform(0.18, 0.58)
                ex, ey, er = (math.cos(ea) * edist, math.sin(ea) * edist,
                              rng.uniform(0.09, 0.15))
            eyes.append((ex, ey, er, rng.choice(("◉", "⊙", "◎"))))

        def smoothstep(s: float) -> float:
            s = max(0.0, min(1.0, s))
            return s * s * (3.0 - 2.0 * s)

        map_text = Text()
        floor = 0.20
        for y in range(height):
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                r = math.hypot(dx, dy)
                angle = math.atan2(dy, dx)

                # Lumpy body outline plus writhing tentacle bumps.
                reach = (R0 + 0.10 * math.sin(3 * angle + p1)
                         + 0.07 * math.sin(5 * angle + p2)
                         + 0.12 * math.sin(2 * angle + p3))
                for ta, tw, tlen, wamp, wfreq, wph in tentacles:
                    ea = ta + wamp * math.sin(r * wfreq + wph)
                    da = math.atan2(math.sin(angle - ea), math.cos(angle - ea))
                    reach += tlen * math.exp(-(da / tw) ** 2)

                depth = reach - r
                if depth <= 0.0:
                    map_text.append(" ")  # outside the horror — open space
                    continue

                # Eyes win over flesh: glowing green orbs, brightest at the pupil.
                eye_hit = False
                for ex, ey, er, glyph in eyes:
                    ed = math.hypot(dx - ex, dy - ey)
                    if ed < er:
                        t = ed / er  # 0 pupil → 1 rim
                        idx = min(n_eye - 1, int(t * n_eye))
                        char = glyph if t < 0.5 else "●"
                        map_text.append(char, style=f"bold {eye_pal[idx]}")
                        eye_hit = True
                        break
                if eye_hit:
                    continue

                # Flesh: veined subsurface glow, brighter the deeper into the mass,
                # tapering the tentacle tips to wisps.
                nd = smoothstep(min(1.0, depth / (reach * 0.6)))
                vein = 0.14 * math.sin(5 * angle + 9 * r + vphase) * (0.4 + 0.6 * nd)
                pulse = 0.06 * math.sin(7 * r - 4 * angle + pphase)
                intensity = 0.42 + 0.46 * nd + vein + pulse
                intensity += rng.uniform(-0.03, 0.03)  # faint grain (seeded)

                if intensity < floor:
                    map_text.append(" ")
                    continue
                if intensity < 0.42:
                    char = "░"
                elif intensity < 0.60:
                    char = "▒"
                elif intensity < 0.80:
                    char = "▓"
                else:
                    char = "█"
                ct = max(0.0, min(1.0, intensity))
                idx = int((1.0 - ct) * (n_body - 1) + 0.5)
                map_text.append(char, style=f"bold {body_pal[idx]}")

            if y < height - 1:
                map_text.append("\n")

        return map_text

    def _generate_ruins(self, rng: random.Random, width: int, height: int,
                        archetype_id: str | None = None) -> Text:
        """Roman columns on a dusk-lit plain: fluted shafts with capitals and
        bases, a couple snapped short, one toppled into drums on the foreground,
        and a stepped pyramid set back near the horizon."""
        scene = _pick_scene(rng)
        horizon = _horizon(height)
        accent = _accent_hue(archetype_id, "#cdb78c")

        # Background pyramid, wide and squat, a dark silhouette against the sky.
        pyr_x = (width - 1) * rng.uniform(0.16, 0.42)
        pyr_h = max(2.0, horizon * rng.uniform(0.45, 0.7))
        pyr_apex = horizon - pyr_h
        pyr_half = pyr_h * 1.6

        # Standing columns; some broken. One fallen column on the near ground.
        n_cols = rng.randint(3, 5)
        cw = max(0.8, width * 0.03)
        cols: list[tuple[float, float, bool]] = []
        left, right = width * 0.12, width * 0.9
        for i in range(n_cols):
            cx = left + (right - left) * (i + 0.5) / n_cols
            broken = rng.random() < 0.33
            frac = rng.uniform(0.34, 0.55) if broken else rng.uniform(0.72, 0.94)
            top_y = horizon - max(2.0, (horizon - 1) * frac)
            cols.append((cx, top_y, broken))
        fy = min(height - 1, horizon + max(1, (height - horizon) // 3))
        fx0 = width * rng.uniform(0.45, 0.62)
        fx1 = fx0 + max(3.0, width * 0.22)

        out = Text()
        for y in range(height):
            for x in range(width):
                cell: tuple[str, str] | None = None
                if y < horizon:  # pyramid set back near the horizon (recedes, darker)
                    span = pyr_half * (y - pyr_apex) / max(1.0, horizon - pyr_apex)
                    if span > 0 and abs(x - pyr_x) <= span:
                        col = _shade(_STONE[2], 1.0 if x < pyr_x - 0.5 else 0.72)
                        cell = ("█", f"bold {col}")
                for cx, top_y, broken in cols:  # standing columns (foreground)
                    if abs(x - cx) <= cw and top_y <= y <= horizon - 1:
                        edge = abs(x - cx) >= cw - 0.5
                        if y <= top_y + 0.6 and not broken:      # capital
                            cell = ("▀", f"bold {_mix(_STONE[0], accent, 0.25)}")
                        elif y >= horizon - 1.4:                 # base
                            cell = ("▄", f"bold {_mix(_STONE[0], accent, 0.25)}")
                        elif broken and y <= top_y + 1.2:        # snapped rubble
                            cell = (rng.choice("▒▓"), f"bold {_STONE[2]}")
                        else:                                    # fluted shaft
                            ch = "║" if edge else "█"
                            shade = 1.12 if x < cx else 0.86
                            col = _shade(_mix(_STONE[1], accent, 0.12), shade)
                            cell = (ch, f"bold {col}")
                        break
                if cell is None:  # one-cell capital overhang on intact columns
                    for cx, top_y, broken in cols:
                        if (not broken and abs(x - cx) <= cw + 1
                                and top_y - 0.4 <= y <= top_y + 0.6):
                            cell = ("▄", f"bold {_mix(_STONE[0], accent, 0.25)}")
                            break
                if cell is None and y == fy and fx0 <= x <= fx1:  # fallen drums
                    t = (x - fx0) / max(1.0, fx1 - fx0)
                    ch = "◖" if t < 0.12 else "◗" if t > 0.88 else ("█" if int(x) % 3 else "▓")
                    cell = (ch, f"bold {_shade(_mix(_STONE[1], accent, 0.1), 0.95)}")
                ch, st = cell if cell is not None else _base_cell(scene, y, horizon)
                out.append(ch, style=st)
            if y < height - 1:
                out.append("\n")
        return out

    def _generate_artifact(self, rng: random.Random, width: int, height: int,
                           archetype_id: str | None = None) -> Text:
        """A Stargate: a great ring standing on a base, chevrons spaced round the
        rim, an event-horizon pool of watery cyan shimmer filling the centre."""
        scene = _pick_scene(rng)
        gen = OpenSimplex(seed=rng.randint(0, 2**31 - 1))
        horizon = _horizon(height)
        accent = _accent_hue(archetype_id, "#ff9a3a")

        cx = (width - 1) / 2.0
        margin = 2                    # keep the gate clear of the frame bottom
        plat_h = max(1, height // 14)
        plat_top = max(1, height - plat_h - margin)  # a low base, raised off the floor
        # As large as the frame allows: the ring is 2*ro cells wide and ro cells
        # tall, its bottom rim resting on the low platform, so it can fill the
        # sprite (the lower half stands over the ground).
        ro = max(3.0, min(width * 0.30, plat_top - 0.5))
        cy = plat_top - ro / 2.0     # bottom rim sits on the platform (dy is doubled)
        ri = ro * 0.64
        thr = ro - ri
        n_chev = rng.randint(7, 9)
        spin = rng.uniform(0.0, math.tau)

        out = Text()
        for y in range(height):
            for x in range(width):
                cell: tuple[str, str] | None = None
                dx = x - cx
                dy = (y - cy) * 2.0  # correct the ~2:1 cell aspect → round ring
                rr = math.hypot(dx, dy)
                ang = math.atan2(dy, dx)
                if rr <= ri:                                     # event-horizon pool
                    ripple = math.sin(y * 1.7 + fractal_noise(gen, x, y, 5.0, 2) * 3.0)
                    sh = 0.5 + 0.5 * ripple
                    col = _mix("#0a3550", "#7fe8ff", sh)
                    ch = "░" if sh < 0.33 else "▒" if sh < 0.66 else "▓"
                    cell = (ch, f"{_mix(col, '#ffffff', 0.2)} on {_shade(col, 0.7)}")
                elif ri < rr <= ro:                              # ring body + chevrons
                    chev = False
                    for k in range(n_chev):
                        ca = spin + k * math.tau / n_chev
                        da = math.atan2(math.sin(ang - ca), math.cos(ang - ca))
                        if abs(da) < 0.22 and rr > ri + thr * 0.25:
                            chev = True
                            break
                    if chev:
                        cell = ("◆" if rr > ro - thr * 0.5 else "▲", f"bold {accent}")
                    else:
                        col = _shade(_STONE[1], 1.1 if math.cos(ang) < 0 else 0.82)
                        cell = ("█" if rr > ro - thr * 0.6 else "▓", f"bold {col}")
                elif plat_top <= y < plat_top + plat_h and abs(dx) <= ro * 0.8:
                    cell = ("▄" if y == plat_top else "█", f"bold {_STONE[2]}")  # base
                ch, st = cell if cell is not None else _base_cell(scene, y, horizon)
                out.append(ch, style=st)
            if y < height - 1:
                out.append("\n")
        return out

    # Luminous alien runes etched across the monolith's face.
    _RUNES = "╬╫╪┼◈▚▞╳▣▦⌖⍒"

    def _generate_ancient_tech(self, rng: random.Random, width: int, height: int,
                               archetype_id: str | None = None) -> Text:
        """An alien monolith: a tall dark obsidian slab standing on the ground, its
        face etched with a grid of luminous, slowly-flickering runes, a chamfered
        top, a wider plinth, and a faint pool of its glow cast on the dirt."""
        scene = _pick_scene(rng)
        gen = OpenSimplex(seed=rng.randint(0, 2**31 - 1))
        horizon = _horizon(height)
        accent = _accent_hue(archetype_id, "#5affb0")

        mono_top = max(1, height // 10)                  # a row or two of sky above
        plinth_h = max(1, height // 14)
        plinth_top = height - 1 - max(1, height // 12)   # tall slab, base off the floor
        body, edge_lit, edge_dark = "#262a36", "#69708a", "#171a22"

        # A cluster of three slabs of differing size, each on its own base course
        # so the raised bases read as depth of field: a tall one left of centre, a
        # medium companion 3 chars to its right, and a smallest one set further back
        # to the left, both offset vertically and horizontally from the main slab.
        hw = max(1.5, width * 0.07)                       # narrow → reads as tall slab
        cx = width * 0.38
        hw2 = max(1.0, hw * 0.62)
        cx2 = cx + hw + hw2 + 3.0                          # 3-char gap to the right
        plinth_top2 = max(mono_top + 2, plinth_top - 2)   # base raised → set back
        short_top2 = mono_top + (plinth_top2 - mono_top) * 0.4
        hw3 = max(1.0, hw * 0.42)                          # smallest, a third size
        cx3 = max(hw3 + 1.0, cx - hw - hw3 - 2.5)          # to the left of the main
        plinth_top3 = max(mono_top + 2, plinth_top - 3)   # base raised further back
        short_top3 = mono_top + (plinth_top3 - mono_top) * 0.55
        # (centre, half-width, top row, plinth-top, plinth-height)
        monoliths = [
            (cx, hw, mono_top, plinth_top, plinth_h),
            (cx2, hw2, short_top2, plinth_top2, plinth_h),
            (cx3, hw3, short_top3, plinth_top3, plinth_h),
        ]

        def mono_cell(mcx: float, mhw: float, mtop: float,
                      mp_top: int, mp_h: int, x: int, y: int) -> tuple[str, str] | None:
            dxa = abs(x - mcx)
            chamf = mtop + 1
            if mp_top <= y < mp_top + mp_h and dxa <= mhw + 1.2:
                return ("▀" if y == mp_top else "█", f"bold {_STONE[2]}")  # plinth
            if mtop <= y < mp_top and dxa <= mhw:
                # Chamfer the two top corners away (sky shows through).
                if y <= chamf and dxa >= mhw - (chamf - y) - 0.5:
                    return None
                if dxa >= mhw - 0.7:                          # lit / shadowed edges
                    return ("█", f"bold {edge_lit if x < mcx else edge_dark}")
                if int(dxa) % 2 == 0 and (int(y) - int(mtop)) % 2 == 1:   # rune row
                    flick = fractal_noise(gen, x * 2.0, y * 2.0, 3.0, 2) \
                        + rng.uniform(-0.25, 0.25)
                    glyph = rng.choice(self._RUNES)
                    if flick > 0.12:
                        return (glyph, f"bold {accent}")
                    if flick > -0.25:
                        return (glyph, f"dim {accent}")
                    return ("░", f"bold {body}")
                return ("█", f"bold {body}")                  # dark obsidian body
            return None

        out = Text()
        for y in range(height):
            for x in range(width):
                cell: tuple[str, str] | None = None
                for spec in monoliths:
                    cell = mono_cell(*spec, x, y)
                    if cell is not None:
                        break
                if cell is None and horizon <= y <= horizon + max(1, height // 8):
                    glow = 0.0  # faint pool of rune-glow on the dirt at each base
                    for mcx_i, mhw_i, *_ in monoliths:
                        if abs(x - mcx_i) <= mhw_i + 2.0:
                            glow = max(glow, (1.0 - (y - horizon)
                                              / max(1.0, height - horizon)) * 0.3)
                    if glow > 0.0:
                        cell = (" ", f"on {_mix(scene.ground, accent, glow)}")
                ch, st = cell if cell is not None else _base_cell(scene, y, horizon)
                out.append(ch, style=st)
            if y < height - 1:
                out.append("\n")
        return out

    def _generate_crashed_ship(self, rng: random.Random, width: int, height: int,
                               archetype_id: str | None = None) -> Text:
        """A huge derelict starship fuselage half-buried in a desert dune: a long
        cylinder on its side with a rounded nose cap and a weathered stripe, the
        stern torn open with engine bells sunk in the sand, rocks strewn about, and
        a great pale planet rising on the horizon behind it."""
        sand = "#c8ac76"
        scene = replace(_pick_scene(rng), ground=sand)
        gen = OpenSimplex(seed=rng.randint(0, 2**31 - 1))
        horizon = _horizon(height)
        accent = _accent_hue(archetype_id, "#b4523a")    # weathered hull-stripe red

        # Desert dune the wreck lies across, half-sunk.
        dcx = width * rng.uniform(0.40, 0.58)
        dune_amp = max(2.0, height * 0.16)
        dw = max(7.0, width * 0.62)

        def sand_h(px: float) -> int:
            return int(round(horizon - dune_amp * math.exp(-((px - dcx) / dw) ** 2)))

        # Fuselage: a long cylinder on its side, tilted, mostly buried.
        hx = width * 0.46
        big_a = max(11.0, width * 0.42)
        big_b = max(3.0, height * 0.27)
        tilt = rng.uniform(-0.12, -0.05)
        ct, st = math.cos(tilt), math.sin(tilt)
        hy = sand_h(hx) - big_b * 0.05
        seam_gap = max(3, int(round(big_a * 0.18)))
        hull_lit, hull_mid, hull_dark = "#cdb98e", "#9a8d70", "#5f5743"

        # Rounded nose cap (the fuselage's capped front), raised at the left end.
        ncx = hx - big_a * 0.90
        ncy = hy - big_b * 0.20
        nr = big_b * 1.25

        # Engine bells sunk in the dune past the torn stern.
        eng = []
        for k in range(2):
            ecx = hx + big_a * (0.80 + 0.30 * k)
            er = big_b * (1.15 - 0.20 * k)
            eng.append((ecx, sand_h(ecx) - er * 0.40, er))

        # A debris field strewn across the dune — rocks and torn hull fragments,
        # thicker toward the foreground.
        debris = []
        for _ in range(rng.randint(12, 18)):
            dpx = rng.uniform(0.04, 0.96) * width
            dpy = sand_h(dpx) + rng.uniform(0.4, height * 0.46)
            debris.append((dpx, dpy, rng.uniform(0.8, 2.4), rng.random() < 0.4))

        out = Text()
        for y in range(height):
            for x in range(width):
                sh = sand_h(x)
                cell: tuple[str, str] | None = None

                # Rounded nose cap, drawn first (the fuselage's capped front).
                nd = math.hypot(x - ncx, (y - ncy) * 2.0) / nr
                if nd <= 1.0 and y < sh:
                    tone = (_shade(hull_lit, 1.08) if nd < 0.5
                            else hull_mid if nd < 0.8 else _shade(hull_dark, 1.1))
                    cell = ("█", f"bold {tone}")

                # Cylindrical fuselage body (top lit, belly dark), torn at the stern.
                if cell is None and y < sh:
                    du, dv = x - hx, (y - hy) * 2.0
                    u = (du * ct + dv * st) / big_a
                    v = (-du * st + dv * ct) / big_b
                    if abs(u) <= 1.0 and abs(v) <= 1.0:
                        torn = 1.0
                        if u > 0.5:                            # ragged broken stern
                            torn = 1.0 - (u - 0.5) / 0.5 * 0.7 \
                                + 0.4 * fractal_noise(gen, x * 1.5, y * 1.5, 3.0, 2)
                        if abs(v) <= torn:
                            f = 1.12 - 0.30 * (v + 1.0)        # cylinder shading
                            if int((u + 1.0) * big_a) % seam_gap == 0:
                                f *= 0.72                      # subtle ring seam
                            base = accent if -0.85 <= v <= -0.35 and u < 0.35 else hull_mid
                            cell = ("█", f"bold {_shade(base, f)}")

                # Engine bells at the torn stern (concentric tube ends).
                if cell is None and y < sh:
                    for ecx, ecy, er in eng:
                        ed = math.hypot(x - ecx, (y - ecy) * 2.0) / er
                        if ed <= 1.0:
                            tone = (hull_dark if ed < 0.4 else _shade(hull_mid, 0.8)
                                    if ed < 0.62 else _shade(hull_lit, 0.95)
                                    if ed < 0.85 else hull_mid)
                            cell = ("█", f"bold {tone}")
                            break

                # Debris field: rocks and torn hull fragments across the dune.
                if cell is None and y >= sh - 1:
                    for dpx, dpy, drad, metal in debris:
                        if abs(x - dpx) <= drad and abs(y - dpy) <= drad * 0.6:
                            if metal:
                                col = _shade(hull_mid, 0.68 + 0.12 * ((x + y) % 3))
                                cell = ("◣" if (x + y) % 2 else "◢", f"bold {col}")
                            else:
                                col = _shade("#7a6a52", 0.8 + 0.12 * ((x + y) % 3))
                                cell = ("█" if (x + y) % 2 else "▓", f"bold {col}")
                            break

                # Textured desert sand: dune mottling and faint wind ripples.
                if cell is None and y >= sh:
                    n = fractal_noise(gen, x * 0.5, y * 1.3, max(5.0, width * 0.4), 3)
                    col = _shade(sand, 1.0 + 0.07 * n)
                    rip = fractal_noise(gen, x * 0.8 + 40.0, y * 2.4, 3.5, 2)
                    if rip > 0.5:
                        cell = ("░", f"{_shade(sand, 0.9)} on {col}")
                    elif rip < -0.55 and (x + y) % 2 == 0:
                        cell = ("·", f"{_shade(sand, 1.12)} on {col}")
                    else:
                        cell = (" ", f"on {col}")

                ch, sst = cell if cell is not None else _base_cell(scene, y, sh)
                out.append(ch, style=sst)
            if y < height - 1:
                out.append("\n")
        return out

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
        if subtype == "entity":
            return self._generate_entity(rng, width, height)
        if subtype == "ruins":
            return self._generate_ruins(rng, width, height, archetype_id)
        if subtype == "artifact":
            return self._generate_artifact(rng, width, height, archetype_id)
        if subtype == "ancient_tech":
            return self._generate_ancient_tech(rng, width, height, archetype_id)
        if subtype == "crashed_ship":
            return self._generate_crashed_ship(rng, width, height, archetype_id)

        # Defensive fallback: a plain hull orb for any unknown subtype.
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
                row_chars.append("█" if dx * dx + dy * dy < 0.64 else " ")
            rows.append("".join(row_chars))
        return render_grid(rows, style, top_color, bottom_color, rng, width, height)
