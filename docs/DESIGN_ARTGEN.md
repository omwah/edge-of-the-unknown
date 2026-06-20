# Edge of the Unknown — Procedural Art Generation Design
## Predictively Generative ASCII Art for Planets, Ships, and Ports

*Version 0.1 — June 2026*

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
- **Ships, Ports, and Starbases**: A combination of Compositional (assembling pre-made ASCII fragments like hulls, thrusters) and Signed Distance Fields (SDFs) to trace sharp geometric structures onto an ASCII grid.

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

For planets, the core `planet_type` (e.g., `terrestrial_warm`, `jovian`, `barren`) acts as the primary constraint:
- **Type Dictates Base**: The `planet_type` determines the core rasterization strategy (e.g., continuous land/water noise for terrestrials, horizontal gas band noise for jovians, dense cratering for barren) and sets the appropriate color palette.
- **Seed Dictates Details**: The locally derived seed sets the specific noise offset/scale, precise crater placement, and the generation of optional compositional features like planetary rings or orbiting small moons. 
This ensures that a `terrestrial_warm` world always looks habitable, but every such world is uniquely identifiable.

### 4.2 Ships and Ports

Ship and Port generation maps core data (`ship_class` and port type) to the visual output:
- **Role / Port Type Defines Skeleton**: The `role` (for ships: `fighter`, `freighter`, `capital_warship`) or the port type (`trading port`, `starbase`, `stardock`) dictates the fundamental base composition and SDF skeleton. A freighter will always have a recognizable cargo backbone, while a port will have a stationary, orbital structure.
- **Species Defines Style**: Just like ships, all three types of ports accept an `owner_species` argument. The `owner_species` dictates the stylistic generation parameters and the primary color palette. For example, a hostile insectoid species might generate sharp, angular SDF shapes for both its ships and its orbital starbases, while a friendly trader species might generate smooth, blocky industrial structures.
- **Seed Adds Variation**: The local seed resolves the final geometric parameters, asymmetry, and modular additions (like extra antennae, docking bays, or engine nacelles) within the boundaries of the skeleton and species style.

### 4.3 Engine Room Subsystems

Subsystem icons (e.g., Spindrive, Screens, Thrusters) will also be procedurally generated rather than statically defined, combining two dynamic aspects:
- **Procedurally by Manufacturer**: The `owner_species` (or the manufacturer's species/tech-level) will dictate the visual style of the subsystem. A Federation converter might look standard and modular, while a deep-space alien accelerator might look biomechanical or crystalline.
- **Condition-Based Variations**: The generation will dynamically apply visual wear or damage based on the component's current health status. A knocked-out or heavily damaged component will have its generated structure visibly broken, missing blocks, or corrupted, making the need for repair tangible at a glance.
