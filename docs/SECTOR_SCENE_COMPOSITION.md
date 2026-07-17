# Sector-scene composition — the arrival view

Status: shipped (WP-PR2-05, `playtest: WP-PR2-05 arrival-view sector scene`)
Code: `edge/tui/widgets.py` → `_SceneComposer` (the layout) / `SectorScene` (the widget shell)
Preview: `pixi run python -m edge.tui.scene_preview` (dev-only; every composition × every tier)

This note records the *theory* behind where things go, so future changes tune the
intent instead of rediscovering it. The interview decisions of 2026-07-17 are folded
in throughout.

## 1. The premise: a viewport, not a form

The old scene partitioned the canvas into reserved bands — planet half, port half,
ships row, presence band — so every sector read as the same form with different
values filled in, and most of the canvas was margin around small, evenly-sized
sprites. The redesign treats the scene as **what you see out the window on arrival**:

- **One subject.** Every sector has a primary body — the planet, else a space find,
  else the station — and the composition is built around it. Everything else is
  supporting cast, sized *relative to the subject* rather than to a layout slot.
- **Scale is information.** The size hierarchy encodes what kind of thing you're
  looking at: planet ≫ nebula-class phenomena ≥ station ≫ ship ≫ fighter/mine glyph.
  Two objects of different kinds should never read as peers.
- **Space is allowed to be empty.** Stars showing through is the point — a sector is
  mostly void with a few things in it, not a dashboard.

## 2. The scale chain

All sizes derive from one number — the primary body's height — so the whole scene
scales together across terminal tiers:

| object | size rule | why |
|---|---|---|
| planet | up to 90% of body height, capped by `scene.planet.max_height` and by width; width = 2×height (round disc on ~2:1 cells) | the world is the subject |
| asteroid belt | same height, width = 3×height | a *field*, not a body — it sprawls |
| nebula | box oversized to ~140% body height, ~125% canvas width | dwarfs a planet; its soft SDF rim thins to nothing inside the box, and the crop trims the blank margin, so the box must be oversized for the *visible* cloud to reach past planet scale; paint clips at the canvas edge, so it bleeds off-screen like the real thing |
| other space finds (wormhole, black hole, wreck-as-primary) | ~60% of body height | compact phenomena |
| port / starbase | `scene.port_scale` (0.5) × primary height | a structure at a world |
| ship | `scene.ship_scale` (0.3) × primary height, slimmed further if the open sky is narrow | traffic |
| fighters / mines | single glyphs (`▴` / `✺`) | presence, not objects |

## 3. Placement: why each thing goes where it goes

- **The primary body rides just right of centre** (disc centre ≈ 60% of width). Centred
  enough to be the subject, offset enough to leave one coherent region of open sky on
  its left — a single large void reads better than two slivers, and it gives ships and
  tags somewhere to breathe. A disc may crop slightly at the edge, like a world filling
  a viewport; that is deliberate drama, not overflow.
- **The station hovers at the world's lower-left limb**, overlapping the disc's bounding
  box by about a third of its own width. Orbiting infrastructure belongs *at* the world;
  the overlap is what makes it read as "in orbit here" rather than "next to it". Its
  offset is computed from the planet's rect, so it follows the disc wherever the disc goes.
- **A lone station drifts.** With no world to pin it, its berth is drawn per sector from
  a seeded RNG — deterministic (the same sector always looks the same) but varied, so a
  chain of port-only sectors doesn't render as one repeated postcard.
- **Ships ride the open sky** left of the primary, first-free-anchorage-wins: a seeded
  jitter column is tried first, then the sky's edge and middle, scanning downward. The
  jitter is what keeps two-ship sectors from always forming the same tableau. Ships face
  the world they've arrived at; with nothing to face, the second of a pair may face the
  first.
- **Wrecks berth hard against the left screen edge, scanning up from the bottom, with a
  wide standoff** (padding relaxes 14×5 → 1×1 only if no isolated pocket exists; the
  left bias never relaxes). The fiction earns the rule: live traffic and stations keep
  their distance from a hulk, so the hulk gets the far shore of the scene.
- **Fighters and mines scatter as glyphs** through free sky (seeded, count-capped:
  density *hints* at strength). Fighters read as a patrol precisely because they are
  small and dispersed; anything bigger would read as ships. Counts, mode, toll, and
  ownership are the sidebar's story — colour alone (green yours / red foreign) is
  carried in the scene.

## 4. The mechanics that make it work

Three rules keep an unconstrained layout from degenerating:

1. **Crop to ink, then place.** Sprite grammars render into the requested box with
   transparent padding around a possibly smaller drawing. Every sprite is cropped to
   its inked bounding box (`_crop`) *before* placement, and its reserve rect is the
   crop. Reserving the request instead of the drawing fences off empty sky and starves
   later placements — this single fix eliminated every early collision.
2. **Occupancy is law.** Every sprite, tag, text row, and scattered glyph reserves its
   rect; every later placement checks `_is_free` (with a 1-cell pad so nothing hugs
   anything). Nothing ever paints over a reserved cell.
3. **No room → become text.** An object that finds no free sky degrades to a clickable
   text row at the bottom of the scene (`_deferred`), never a forced overlap. The scene
   makes a *promise*: everything present is either drawn in clear space or listed —
   and either way it stays clickable.

## 5. Labels

- A tag is the object's **name only** — status, ownership, kind/rarity, hail/engage
  verbs all live in the sidebar (Ships and Anomalies lists, presence lines). The scene
  shows *what's here*; the sidebar says *what you can do about it*.
- Tags float: centred just below their sprite when that fits (the caption position the
  eye expects), else above, else beside — first free spot wins. They are stamped
  opaquely (stars can't bleed through a space inside a word) and reserved like sprites.
- Fog rules are unchanged: an unscanned find shows no name; a wreck is the exception
  (a hulk is plainly a hulk — PT-49) and wears its ship's name pre-salvage.

## 6. Determinism

Everything random is seeded from stable identity: the starfield and ship jitter per
`sector_id`, the lone-station berth per `sector_id ^ salt`, force scatter per
`sector_id ^ salt`, sprites per `planet_id`/`starbase_id`/`sector_id` as before (the
planet seeds off its own id so the sector view and the PlanetScreen orbit view draw
the same world). A sector composes identically every visit, every replay.

## 7. Tuning knobs

`config/default.yaml → scene:` — `planet.max_height` (subject size cap),
`port_scale` / `ship_scale` (the hierarchy), `max_ships_shown` (sprite cap before
text-row overflow), `ship_face_inward_chance`. The centring factor (0.6) and the
belt/nebula width multipliers live beside the placement code in `_SceneComposer` —
they are compositional intent, not balance, and moving them means rereading §3.
