"""Shared procedural-noise helpers for the art generators."""

from opensimplex import OpenSimplex


def fractal_noise(
    gen: OpenSimplex, x: float, y: float, scale: float, octaves: int = 3
) -> float:
    """Sum several octaves of noise so clusters break up at multiple scales.

    Layering higher-frequency octaves over the base field prevents the large,
    smooth low regions that otherwise read as big connected voids. The result is
    normalised back to roughly [-1, 1].
    """
    total = 0.0
    max_amplitude = 0.0
    amplitude = 1.0
    frequency = 1.0 / scale
    for _ in range(max(1, octaves)):
        total += amplitude * gen.noise2(x * frequency, y * frequency)
        max_amplitude += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return total / max_amplitude
