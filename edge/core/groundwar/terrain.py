"""Pure gameplay terrain seam for ground operations (GW-WP02).

Owns the *gameplay* half of biome terrain — which feature name sits in which
noise band, and the per-planet noise scale — plus deterministic noise → feature
grid generation. It holds **no glyphs and no colours**: those live in
`edge.art.terrain`, which imports `BIOME_BANDS` from here and layers styling over
the feature names this module emits. Because this is `edge.core`, it never
imports `edge.art` (the split exists so `edge.core` has no upward import); the
only third-party import is the pure `opensimplex` noise generator.

A cell's *feature name* is the key the ground rules price for movement, cover,
and line of sight (`GroundwarConfig.terrain`, `edge.core.config`). Generation is
deterministic from `(noise_seed, planet_type)`, so a survey/assault map replays
from the operation seed with no RNG drawn at projection time (invariant G5).
"""

from __future__ import annotations

from dataclasses import dataclass

from opensimplex import OpenSimplex


@dataclass(frozen=True, slots=True)
class BiomeBands:
    """The gameplay band structure for one planet type.

    `scale_x`/`scale_y` stretch the noise field; `bands` is a nearest-first list
    of `(noise_threshold, feature_name)` — the first band whose threshold the
    noise value does not exceed wins, with the last band as the fallback.
    """

    scale_x: float
    scale_y: float
    bands: tuple[tuple[float, str], ...]


# planet_type -> band structure. Colour and glyph choices for these same bands
# live in `edge.art.terrain` (BIOME_COLORS / FEATURES_REGISTRY), index-aligned to
# `bands`, so there is a single source of truth for *which* feature falls in each
# band. Groundwar gameplay uses only the terrestrial_* and barren entries
# (jovian/asteroid_belt are orbital-only, DESIGN §4.2 / GW plan D9); the full set
# is shared here so planet art has one authority for the band layout.
#
# **A landable biome's band names must be unique** (GW-WP21, guarded by
# `tests/test_terrain_bands.py`): the ground map views colour a cell by looking its
# feature *name* up in this list, so two bands sharing a name collapse to whichever
# comes first and the later band's authored colours can never render. Non-landable
# biomes may repeat a name — planet art indexes bands positionally
# (`edge.art.terrain.get_biome_feature`) and so is unaffected.
BIOME_BANDS: dict[str, BiomeBands] = {
    "terrestrial_warm": BiomeBands(
        scale_x=15.0,
        scale_y=15.0,
        bands=(
            (-0.2, "water_deep"),
            (-0.05, "water_shallow"),
            (0.05, "sand"),
            (0.3, "grass"),
            (0.6, "forest"),
            (0.7, "mountain"),
        ),
    ),
    "terrestrial_cool": BiomeBands(
        scale_x=15.0,
        scale_y=15.0,
        bands=(
            (-0.1, "water_deep"),
            (0.1, "water_shallow"),
            (0.3, "dust"),
            (0.5, "grass"),
            (0.7, "forest"),
            (0.9, "mountain"),
            (1.0, "snow"),
        ),
    ),
    "terrestrial_hot": BiomeBands(
        scale_x=12.0,
        scale_y=12.0,
        bands=(
            (-0.2, "water_deep"),
            (0.0, "water_shallow"),
            (0.1, "sand"),
            (0.2, "ash"),
            (0.5, "dust"),
            (0.8, "mountain"),
            (1.0, "snow"),
        ),
    ),
    "terrestrial_cold": BiomeBands(
        scale_x=18.0,
        scale_y=18.0,
        bands=(
            (-0.2, "water_shallow"),
            (0.1, "ice"),
            (0.4, "snow"),
            (0.7, "mountain"),
            # The top band was a second "ice" until GW-WP21. A band's *name* is the only
            # key `edge.tui.screens._ground_shared.feature_colors` has, so a repeated name
            # made this band's authored cyan-on-blue unreachable — high glacial ice drew
            # in the shallow band's white-on-white. Distinct bands need distinct names.
            (1.0, "glacier"),
        ),
    ),
    "jovian": BiomeBands(
        scale_x=50.0,
        scale_y=5.0,
        bands=(
            (-0.4, "gas_thick"),
            (-0.1, "gas_thin"),
            (0.2, "gas_thin"),
            (0.5, "gas_thick"),
            (0.8, "gas_thin"),
            (1.0, "gas_thick"),
        ),
    ),
    "asteroid_belt": BiomeBands(
        scale_x=8.0,
        scale_y=8.0,
        bands=(
            (-0.3, "void"),
            (0.3, "belt_dust"),
            (0.6, "belt_rock"),
            (0.8, "belt_rock"),
            (1.0, "belt_debris"),
        ),
    ),
    "barren": BiomeBands(
        scale_x=15.0,
        scale_y=15.0,
        bands=(
            (-0.1, "dust"),
            (0.2, "rock"),
            (0.6, "crater"),
            (1.0, "mountain"),
        ),
    ),
}


# The planet types a ground operation can walk on (populated/terrestrial worlds
# plus barren rock). Jovians and asteroid belts stay orbital-only (DESIGN §4.2,
# GW plan D9), so their bands above exist only for planet art parity. The config
# validator uses this to prove every feature these biomes can emit has a terrain
# class, and the mapgen offers exactly these on its setup screen.
LANDABLE_BIOMES: tuple[str, ...] = (
    "terrestrial_warm", "terrestrial_cool", "terrestrial_hot", "terrestrial_cold", "barren",
)


def feature_at(val: float, bands: tuple[tuple[float, str], ...]) -> str:
    """The feature name a noise value falls into (nearest-first, last as fallback)."""
    for threshold, feature_name in bands:
        if val <= threshold:
            return feature_name
    return bands[-1][1]


def generate_feature_grid(
    noise_seed: int, planet_type: str, width: int, height: int
) -> list[list[str]]:
    """A `height × width` grid of gameplay feature names, deterministic from the seed.

    Raises `KeyError` for an unknown `planet_type`. Draws no game RNG — the noise
    is seeded solely from `noise_seed`, so the same seed and inputs reproduce the
    identical grid on every replay (G2/G5).
    """
    layout = BIOME_BANDS[planet_type]
    gen = OpenSimplex(seed=noise_seed)
    return [
        [
            feature_at(float(gen.noise2(x / layout.scale_x, y / layout.scale_y)), layout.bands)
            for x in range(width)
        ]
        for y in range(height)
    ]
