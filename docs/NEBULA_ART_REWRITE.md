# Rewrite the nebula generator to use coherent fractal noise

> Note (2026-06-22): assessment + plan.
> **Implemented 2026-06-23** in `edge/art/discovery.py` `_generate_nebula()` along the
> recommended approach below — a domain-warped multi-octave `fractal_noise` density
> field masked by a smoothstep radial envelope, with the shade ramp and an
> archetype-aware colour ramp both driven by density (stretched across the visible
> density band so cores read white-hot and wisps take the rim hue). `archetype_id`
> is plumbed through `generate()`; the default (no owner) keeps the warm fire palette.

## Context

`edge/art/discovery.py` `_generate_nebula()` draws nebulae as a single radial SDF
blob with **per-pixel white noise** (`rng.uniform(-0.15, 0.15)`) for "texture" and a
**radial color ramp**. White noise is spatially uncorrelated, so it reads as grainy
static rather than gaseous structure; the radial ramp makes a concentric bullseye
instead of color that tracks density. A nebula is the one discovery that is literally
a gas cloud, yet it is the only generator in `edge/art/` that does **not** use the
established coherent-noise idiom. It also hardcodes a fire palette and **ignores
`archetype_id`** (every other subtype honors `style_for(archetype_id)`).

The project already has the right tool and proves it works at these sizes:
- `edge/art/noise.py` — `fractal_noise(gen, x, y, scale, octaves)` (multi-octave OpenSimplex).
- `edge/art/terrain.py` — uses it for jovian gas bands and asteroid-cluster density.
- `edge/art/starfield.py` — uses it for clustered star density (the exact wispy look we want).

Goal: replace the nebula technique with a domain-warped fractal-noise **density field**,
masked by a soft radial **envelope**, with the shade ramp and color both driven by the
density field — and make it archetype-aware like every other subtype.

## Approach (recommended)

Rewrite only `_generate_nebula()` in `edge/art/discovery.py`. Leave all other discovery
subtypes (analytic icons) untouched — they are fine for their tier.

1. **Density field from fractal noise.** Build one `OpenSimplex(seed=rng.randint(...))`
   (same pattern as `terrain.py` / `starfield.py`). For each cell sample
   `fractal_noise(gen, x, y, scale, octaves)` with a nebula scale (~half the sprite width,
   tune like starfield's `scale`) and `octaves=3-4`.

2. **Soft radial envelope, not a hard SDF blob.** Keep the normalized `dx/dy` radial
   distance, but convert it to a smooth falloff (e.g. `env = clamp(1.0 - d, 0, 1)` or a
   smoothstep). Combine as `density = noise01 * env` (noise normalized to 0..1). The
   envelope fades edges to space while the **interior** structure comes from noise —
   giving tendrils, cores, and voids instead of one disc. Retain the existing angular
   `bulge` harmonics applied to the envelope only (cheap lopsidedness), not to texture.

3. **Optional domain warp** for the signature wispy curl: offset the sample coords by a
   second low-frequency noise lookup before the main sample
   (`fractal_noise(gen, x + warp, y + warp, ...)`). One extra sample per cell; cost is in
   line with `planet.py`'s per-cell lighting math.

4. **Shade ramp from density** (reuse the existing block glyphs `█ ▓ ▒ ░ ' '`): threshold
   `density` into the five tiers instead of `fuzzy_d`. Below a low cutoff → space.

5. **Color from density, archetype-aware.** Drive the gradient index by `density`
   (so color tracks structure, not radius). Honor `archetype_id` via
   `style_for(archetype_id)` (already imported) so nebulae vary by region/owner like
   ports/ships do; keep the warm fire palette as the default/fallback when no archetype
   style applies. Optional stretch: sample a second noise field to mix a bicolor emission
   look (warm core vs cool teal rim).

6. **Avoid pure black fill** consistent with `planet.py`'s void rule — drop `on black`
   on lit cells (let the terminal background show) so the cloud doesn't merge oddly when
   composited; empty cells stay a plain space.

## Critical files

- `edge/art/discovery.py` — rewrite `_generate_nebula()`; add
  `from opensimplex import OpenSimplex` and `from edge.art.noise import fractal_noise`.
  The `generate()` dispatch already routes `nebula` here and passes `archetype_id`, so
  plumb `archetype_id` into `_generate_nebula`'s signature.

## Reuse (do not reinvent)

- `edge/art/noise.py:fractal_noise` — the multi-octave sampler.
- `edge/art/starfield.py` `StarfieldGenerator.generate` — canonical density→fill pattern to mirror.
- `edge/art/hull.py:style_for` / `ARCHETYPE_STYLES` — archetype palettes (already imported in discovery.py).

## Verification

- `python -m edge.art.cli discovery nebula ...` (see `edge/art/cli.py` for exact flags;
  it can loop subtypes/archetypes) — eyeball several seeds and a couple of `--archetype-id`
  values: expect wispy filaments + voids and color that follows structure, and visibly
  different clouds per archetype.
- Sweep sizes (small icon vs large panel) to confirm the envelope scales and the noise
  `scale` reads well at both — adjust `scale` relative to width if needed.
- `pytest tests/test_art_coverage.py tests/test_*art*` — ensure the discovery subtype
  still renders for every subtype/size the coverage test exercises (no exceptions, correct
  dimensions). Determinism: same `(seed, subtype, w, h, archetype)` → identical output.
