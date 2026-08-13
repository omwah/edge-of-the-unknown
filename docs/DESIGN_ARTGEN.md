# Edge of the Unknown — Procedural Art Generation Design
## Predictively Generative ASCII Art for Planets, Ships, and Ports

*Version 0.2 — June 2026*

---

## 1. Purpose and Scope

This document outlines the design and architecture for the procedural ASCII art generation system. It replaces the static sprite assets (formerly found in `edge.tui.sprites`) with predictively generative art driven by a seeded random number generator.

The goal is to provide unique, deterministic visual representations for planets, surface terrains, ships, and ports, while strictly adhering to the game's core invariant: all randomness must flow from the game state's master seed, ensuring that every visual discovery remains fully reproducible from the same seed.

### 1.1 Goals and Non-Goals

**Goals.** 
- Generate diverse, recognizable ASCII art for key game entities (planets, starbases, ships, surface terrain).
- Maintain strict determinism; the same entity ID and game seed must always produce the exact same visual representation.
- Integrate smoothly with the existing Textual TUI layer as a pure presentation provider without polluting the `core` game logic.
- Support layered generation (e.g., base shape, details, shading) that scales gracefully across distance bands and entity traits.

**Non-goals (v1).**
- Real-time animated ASCII generation (sprites may have static variants, but generation is run once per entity).
- Highly complex 3D projection algorithms (the style should remain true to the BBS/ANSI heritage of the project).
- Changing the internal data model or properties of planets/ships just to support visual features.

---

## 2. Architecture

The art generation logic will live in a new `edge.art` library to separate it from the `core` game logic and the `tui` rendering layer. 

We will use a hybrid algorithmic approach based on the entity type:
- **Surface Terrain**: Rasterization via Noise (e.g., Simplex, Perlin, or cellular automata) to generate organic, continuous fields.
- **Planets**: A combination of Compositional (assembling predefined parts like atmospheres or rings) and Rasterization (for surface textures).
- **Ships, Ports, and Starbases**: Compositional YAML documents from the vendored
  schema-v4 `sprite_art` library. Ordered sections, archetype-aware variants, and
  discrete tiers produce small hand-authored silhouettes while the library centres
  every result in the requested rectangle. Ships expose a left/right facing view;
  stations use vertical compositions. Discovery art remains algorithmic and keeps
  its own painter, while its palette is resolved from the same catalog.

### 2.1 TUI Integration

Because noise and SDF generation can be more computationally expensive than returning static strings, `edge.art` will generate art **synchronously** but will be aggressively cached using `@functools.lru_cache` (keyed by the local seed, type, and parameters). This ensures that traversing a known sector or repeatedly viewing the same entity is instantaneous and does not block the TUI's `asyncio` event loop.

### 2.2 API Interface & Sizing

A critical requirement of the generation API is that **the target size of the generated sprite must be passed as a parameter** to the generation functions (e.g., `width`, `height`). This ensures the same procedural logic can render a small scene-marker sprite for the Sector View and a large, highly detailed sprite for the full Planet Orbit View simply by altering the bounds, without needing entirely separate code paths.

---

## 3. Data Model & Generation Seeds

To strictly adhere to the game's determinism, `edge.art` must use repeatable seeds. Instead of polluting the `core` or `server` DTOs with visual seeds, `edge.art` will derive seeds locally.

For any given entity, `edge.art` takes the `game_seed`, `entity_id`, and `entity_type` (e.g., 'planet', 'ship') and computes a deterministic local seed using `hash()` or a similar robust combination algorithm (matching the existing pattern in `edge.server.terrain`). This keeps the public DTOs clean while ensuring that the generated visual representation remains identical across different UI clients and replays.

---

## 4. Entity Categories

### 4.1 Planets and Terrain

For planets and terrain, the core `planet_type` (e.g., `terrestrial_warm`, `jovian`, `barren`) acts as the primary constraint:
- **Type Dictates Base**: The `planet_type` determines the core rasterization strategy (e.g., continuous land/water noise for terrestrials, horizontal gas band noise for jovians, dense cratering for barren) and sets the appropriate color palette.
- **Seed Dictates Details**: The locally derived seed sets the specific noise offset/scale and precise feature placement. 
- **Planetary Projections & Polish**: While `terrain` requests generate rectangular fills using full ASCII characters, `planet` requests undergo a specialized masking phase:
  - **SDF Masking & Outlines**: Planets are constrained to a circular SDF, bounded by a dynamically calculated outline using curved ASCII drawing characters. The outline color corresponds to the planet's atmosphere (e.g., cyan for terrestrial, yellow for jovian).
  - **Smooth Fills**: Foreground texture characters are stripped from planetary surfaces, relying entirely on background colors to create a smooth, globe-like appearance.
  - **3D Lighting & Dithering**: A directional 3D light vector casts a dithered shadow (`▓`, `▒`, `░`) across the dark side of the planet, preserving a fraction of the biome's background color instead of falling into pure black.
  - **Polar Ice Caps**: For `terrestrial` subtypes, procedural noise is mathematically boosted near the Y-axis poles, naturally forcing high-altitude snow biomes to form ice caps.
  - **Asteroid Belts**: Treated as a special case, asteroid belts bypass the spherical mask, atmospheric outline, and foreground stripping, allowing the sparse debris to pass through cleanly into the rectangular boundaries.

This ensures that a `terrestrial_warm` world always looks habitable and dynamically polished, and every such world is uniquely identifiable.

### 4.2 Ships and Ports

Ship and station art is now authored as schema-v4 YAML in the vendored `sprite_art`
library. The game copies the runtime package and its `assets/` tree; it does not
import the designer project. Each document contains ordered sections, variants,
colour masks, and a discrete tier ladder. The library selects a tier that fits the
requested box, resolves archetype-specific variants and repeats, then centres the
result in an exact rectangle. Its per-instance cache is complemented by the
outer generator cache.

- **Roles and subtypes**: ship roles and the three station ids (`trading_port`,
  `starbase`, `stardock`) select authored documents. The catalog also contains
  eight ship documents reserved for future config-only routing through
  `ShipClassConfig.art_subtype`; they are not gameplay classes yet.
- **Sections and variants**: a sprite is an ordered composition of named sections,
  with weighted or archetype-specific variants. The seed selects variants and
  render details from the stable recipe `seed|kind|role|archetype_id`.
- **Tiers and sizing**: each document supplies a discrete size ladder. The richest
  tier that fits is selected and repeats are applied according to the authored
  archetype rules; the result is centred in the requested width and height. This
  intentionally replaces continuous band tiling. The library budgets that choice
  on the requested **height** alone and centre-crops a wider tier, so
  `edge.art.sprites.fit_box` resolves the requested box to the richest rung that
  fits it on *both* axes before rendering, and `generate_sprite` pads that render
  back into the caller's box. Asking for a box that clears no rung does not yield
  a smaller sprite — it yields the middle of a cropped one, which is why the
  `scene:` caps are constrained by the ladders (see
  `docs/SECTOR_SCENE_COMPOSITION.md` §2 and `docs/SPRITE_ART_SYNC.md` §4).
- **Facing and palettes**: ships provide horizontal views and are mirrored for
  `facing="left"`; stations are vertical-only. The vendored palette catalog is
  the single palette source for ship, station, and discovery art, with
  `humanoid_diplomat` as its validated fallback.
- **Integration**: generation remains synchronous and cached. `edge.art.generator`
  routes ship and station requests through one loaded `SpriteLibrary`, while
  terrain, planets, starfields, and discovery generators retain their existing
  local RNG paths.

### 4.3 Engine Room Subsystems

Subsystem icons (e.g., Spindrive, Screens, Thrusters) will also be procedurally generated rather than statically defined, combining two dynamic aspects:
- **Procedurally by Manufacturer**: The manufacturer's `archetype_id` (and tech-level) will dictate the visual style of the subsystem, keyed on archetype rather than species id/name for the same stability reason as ships and ports (§4.2). A Federation (`humanoid_diplomat`) converter might look standard and modular, while a deep-space alien accelerator might look biomechanical or crystalline.
- **Condition-Based Variations**: The generation will dynamically apply visual wear or damage based on the component's current health status. A knocked-out or heavily damaged component will have its generated structure visibly broken, missing blocks, or corrupted, making the need for repair tangible at a glance.

---

## 5. Tooling — Offline Art CLI & Sprite Sheets

`edge.art.cli` is a dev-only inspector (mirroring the bigbang `--render` topology tool) for iterating on the generators outside the TUI. It renders one or many sprites and either prints them to the terminal or exports a vector **sprite sheet**.

```
python -m edge.art.cli --type port --subtype stardock --archetype-id ribbon_salvager
python -m edge.art.cli --type port --subtype all --archetype-id all        # terminal sweep
python -m edge.art.cli --type ship --subtype warship --facing left          # ship, flipped
python -m edge.art.cli --type ship --subtype all --archetype-id all         # ship sweep
```

- **Sweeps**: `--subtype all` enumerates a type's subtypes; `--archetype-id all` enumerates every archetype palette. Combined, they preview the full style × substyle matrix.
- **Facing**: `--facing left|right` (default `right`) points a ship the other way; ignored by the other types. Left/right are the same ship flipped, so they share one seeded composition.
- **Vector export**: `--export PATH` writes the rendered sprite(s) to a single black **contact sheet** instead of printing — each sprite a labelled tile of coloured monospace cells over per-cell background rectangles (≈1:1.8 cell geometry), so the vector output reproduces the terminal look and stays crisp at any zoom. A `.svg`/`.pdf` suffix writes just that format; any other path writes both `PATH.svg` and `PATH.pdf`.
- **All types in one document**: `--type all --export sheet.pdf` sweeps every renderable type into a **multi-page PDF, one page per type** (one page can't hold both wide planets and tall ports without distortion). Types with no generator yet (subsystem) are skipped.
- **Archetype pagination**: ports and ships both carry a 14-wide archetype axis, so `--archetypes-per-page N` (default 2) paginates their pages to N archetypes (columns) × subtypes (rows) each, keeping individual sprites large and legible; `0` keeps them all on one page. Pagination implies a multi-page PDF (SVG cannot paginate).

Implementation lives in `edge/art/export.py`, which lazily imports a headless (`Agg`) matplotlib — already a dev-only dependency (the bigbang renderer) — so no new dependency is introduced and the rest of `edge.art` stays matplotlib-free. The export is purely a visualization of the same deterministic `generate_sprite` output; it adds no randomness and is not part of the runtime render path.
