# Sector-scene composition — the arrival view

Status: **the physical-model composer (`edge/scene` + `edge/art/scene_paint.py`) is
the shipped default (WP-SC11)**; the composer described in most of this note —
`_SceneComposer`/legacy — is a permanent, config-selectable alternative, not
deprecated scaffolding. Select it with `scene.composer: legacy` in `config/default.yaml`
(default is `physical`, with `scene.projection_strategy: fixed_fov_perspective |
depth_layered_anchor` selecting the physical model's own strategy). See
`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` for the physical model's full design and
work-package history (WP-SC01–WP-SC11); this note's sections below describe the
*legacy* composer's theory and remain accurate for it, but "current"/"shipped" in the
prose below refers to legacy specifically, not the new default.

Code: `edge/tui/widgets.py` → `_SceneComposer` (the legacy layout) / `SectorScene` (the
widget shell, which dispatches to either composer per `SceneArtConfig.composer`) /
`_render_physical_scene` (the physical-model path, painting the same header/flavor/
beacon chrome and starfield background around the physical model's own object layout).
Preview: `pixi run python -m edge.tui.scene_preview --composer <legacy|fixed_fov_perspective|depth_layered_anchor>`
(dev-only; every composition × every tier × either composer).

This note records the *theory* behind where the legacy composer puts things, so
future changes to it tune the intent instead of rediscovering it. The interview
decisions of 2026-07-17 are folded in throughout. It predates the physical model and
was the sole shipped composer through WP-SC10; WP-SC11 made the physical model the
default while keeping this composer as a live alternative and a reference model for
tests (`tests/test_scene_legacy_parity.py`, `tests/test_ui_snapshots.py`'s pinned
`composer="legacy"` suite).

## 0. As implemented: operational rule tree (audit 2026-08-31)

The sections below explain the intent of individual rules. This section records the
actual control flow in `_SceneComposer.compose`, including the selection and fallback
branches that were previously visible only by reading the code.

```text
Create seeded starfield
└─ Paint header and reserve its rows
   └─ Select at most one discovery for the scene
      ├─ Prefer the first wormhole
      └─ Otherwise take the first discovery

Calculate ref_h: the height a planet would receive in this viewport
└─ Select and paint the initial primary
   ├─ Planet present → paint the first planet
   ├─ No planet, selected discovery present → paint it as primary
   └─ Otherwise → no body primary

Paint one station
├─ First starbase wins over every port
└─ Otherwise paint the first port
   ├─ With a planet: size from rendered planet height
   ├─ Beside a space find: place from the find, but size as a lone station
   └─ Alone: size from body height and choose a seeded random berth

If the selected discovery was not consumed as primary
└─ Paint it as the one secondary discovery

Paint ships
├─ Consider only scene.max_ships_shown ships as sprites
├─ Size from ref_h, not necessarily from the rendered primary
├─ Place nearest first, bottom-up; carry size/row bounds toward far ships
├─ Retry smaller authored sprite rungs, then relax the assigned band
└─ No berth → append an in-scene text row

Paint deferred and excess ships plus the Entity hint as text rows
└─ Scatter fighter and mine glyphs into cells still free
```

Tags are painted immediately after their object rather than in a separate annotation
pass. Later paint normally respects the occupancy map, with deliberate exceptions:
the station may cross the planet's projected rectangle, and an asteroid belt reserves
no rectangle so stations and traffic paint through the field.

### 0.1 The current sizing dependency graph is not one chain

The introductory phrase "sized relative to the primary" is a useful visual goal, but
it is not a literal description of every current calculation:

| object | actual sizing reference |
|---|---|
| planet / belt | viewport width and body height through `primary_body_height` |
| primary nebula | body height directly |
| other primary discovery | hypothetical planet height (`ref_h`) |
| station beside a planet | rendered planet height |
| station beside a discovery or alone | viewport body height |
| secondary discovery | one quarter of viewport body height, capped |
| ship | hypothetical planet height (`ref_h`), then authored tier and fit steps |
| forces | count-derived single glyphs |

Consequently, *semantic primary*, *sizing reference*, *placement anchor*, *paint
layer*, and *retention priority* are separate ideas in the code but are not represented
as separate data. `_SceneComposer` decides each while painting, so a gallery cell can
report the resulting rectangles but cannot explain the complete decision path that
produced them. That missing intermediate representation is the central problem the
physical-model replacement plan addresses.

## 1. The premise: a viewport, not a form

The old scene partitioned the canvas into reserved bands — planet half, port half,
ships row, presence band — so every sector read as the same form with different
values filled in, and most of the canvas was margin around small, evenly-sized
sprites. The redesign treats the scene as **what you see out the window on arrival**:

- **One subject.** Every sector has a primary body — the planet, else a space find,
  else the station — and the composition is built around it. Ships and secondary
  finds and stations are sized relative to that rendered subject. A docked header
  reuses the exact rendered sizing inputs published by the Sector composer (§2), so
  it does not have to guess the now-hidden subject's height.
- **Scale is information.** The size hierarchy encodes what kind of thing you're
  looking at: planet ≫ nebula-class phenomena ≥ station ≫ ship ≫ fighter/mine glyph.
  Within the stations that ordering is itself tiered — **planet ≫ Stardock >
  starbase > port > ship** — so the flagship dock reads grander than an orbital
  base, which reads grander than an ordinary trading port, which still outsizes any
  visiting ship. Two objects of different kinds should never read as peers.
- **Space is allowed to be empty.** Stars showing through is the point — a sector is
  mostly void with a few things in it, not a dashboard.

## 2. The scale chains

Objects derive from the primary body's live rendered height, so the scene scales
together across terminal tiers. This is viewport-dependent: `planet.max_height` is
only a cap on the rendered planet, never the station's direct scaling reference.

| object | size rule | why |
|---|---|---|
| planet | up to 90% of body height, capped by `scene.planet.max_height` and by width; width = 2×height (round disc on ~2:1 cells) | the world is the subject |
| asteroid belt | same height, width = 3×height | a *field*, not a body — it sprawls |
| nebula | box oversized to ~140% body height, ~125% canvas width | dwarfs a planet; its soft SDF rim thins to nothing inside the box, and the crop trims the blank margin, so the box must be oversized for the *visible* cloud to reach past planet scale; paint clips at the canvas edge, so it bleeds off-screen like the real thing |
| other space finds (wormhole, black hole, wreck-as-primary) | `_FIND_PRIMARY` (0.82) of the primary body height | compact phenomena — still the thing you came to look at, so under a planet's 0.9 rather than the 0.6 that left a wormhole 15 rows tall in a 25-row sky |
| secondary find (a wreck beside a world) | `body_h / 4`, capped by `_FIND_SECONDARY_MAX` (10) | grows with the scene, stays well under the world it is parked beside |
| ordinary port | `scene.port_scale` × rendered primary height, clamped by `scene.port` | independently tunable port footprint |
| Stardock | `scene.stardock_scale` × rendered primary height, clamped by `scene.stardock` | independently tunable flagship silhouette, never ordinary-port art |
| starbase | `scene.starbase_scale` × rendered primary height, clamped by `scene.starbase` | independently tunable orbital-base silhouette |
| ship | height from `scene.ship_scale` (0.2) × primary height; width is the open sky, clamped by `scene.ship`; then **stepped down the tier ladder by the ship's depth** (§2.1) | traffic — must stay below `port_scale` so a visiting ship never outsizes the port. No fixed aspect: see the tier note below |
| fighters / mines | single glyphs (`▴` / `✺`) | presence, not objects |

### 2.1 Traffic reads its depth off the ladder

Ships in one scene are **not drawn at the same rung**. `_paint_ships` bands them down
the sky by index (§3), so the band index doubles as distance: band 0 is the top of the
sky and the furthest away, and each ship steps `min(_SHIP_DEPTH_MAX_STEPS, n-1-i)`
rungs down `edge/art/sprites.py` → `rung_below` before it is rendered. A lone ship is
never stepped — there is nothing for it to read as further *than*.

Two things depend on this and neither has another lever:

- **Depth.** Equal-sized hulls read as a formation pasted on a flat backdrop. The
  playtest note is blunt about it: *"it helps if in empty space one ship is smaller
  than the other to give a sense of depth"*, and *"the one further away is more likely
  the one at the top"* (gallery pass 2026-08-16).
- **Scale parity with stations.** Station art tops out at 11–15 columns (§2, the art
  ladder) while a ship's top rung is 46. Config cannot close that gap from the station
  side — the rungs do not exist — so a scene with every hull at the top rung reads as
  *"ships overpower port"* however the caps are tuned. Stepping the far ships down is
  the only lever Edge has short of new upstream art.

The cue is only legible if the vertical order matches the size order, so placement runs
**nearest-first, bottom-up** and carries two bounds up the sky. The near hull claims the
richest rung and the best berth; every further ship is then held above it (`ceiling` in
`_berths`) *and* capped at its drawn width (`cap_w` in `_paint_ships`). Both are needed:
the ceiling alone still produced a small hull under a big one whenever the near ship had
to step further down the ladder than the far one to fit at all — the ordering was right
and the sizes were backwards.

A ship that cannot fit steps *further* down the ladder (`_SHIP_FIT_STEPS`) and retries,
rather than drifting out of position; the ladder is how the scene absorbs "not enough
room", because moving the ship instead breaks the very ordering the rung was chosen for.
Only after the whole ladder fails does the search re-run unconfined — which gives up the
*band*, never the ceiling, so even the last resort cannot invert the cue.

One consequence for the gallery: `scene_gallery`'s "ship drew its narrowest rung" flag
measures the **largest** ship in the scene, so a deliberately-stepped far ship does not
trip it. When the flag does fire on a wide canvas, the near ship really was starved —
usually by a station berthed in its band.

`SceneArtConfig.station_dimensions(kind, primary_height, body_height)` is the one
resolver for all three station kinds. It reproduces the two branches formerly embedded
in `_SceneComposer._paint_station`. With per-kind bounds `S` and scale `k`:

```text
if a primary body was rendered:
    height = clamp(round(primary_height * k), S.min_height, S.max_height)
    width  = clamp(int(height * 2.4), S.min_width, S.max_width)
else (the station is itself the primary):
    height = clamp(int(body_height * 0.6), S.min_height, S.max_height)
    width  = clamp(int(height * 2.6), S.min_width, S.max_width)
```

**The caps must not saturate below the planet's range.** Each kind's `S.max_height`
must stay ≥ `round(planet.max_height × k)`, and `S.max_width` must cover the 2.4
aspect at that height — otherwise the clamp pins the station at one size while the
planet is still growing across normal viewports, and the responsiveness the resolver
exists to provide is silently erased (this shipped once: `starbase.max_height: 9`
against `0.5 × 26` froze every starbase at 8 inked rows). The shipped values are
`port 28×12`, `stardock 38×16`, `starbase 33×14` for scales 0.3 / 0.6 / 0.35 against
`planet.max_height: 40`, with `ship 46×7` at 0.2. Those values realise the §1 tier
ordering **planet ≫ Stardock > starbase > port > ship** at every viewport — at a
full-size planet the requested chain is 40 ≫ 16 > 14 > 12 > 7 rows, and in *ink*
(what the eye actually ranks, after the ladder and the crop) 40 ≫ 14 > 10 > 8 > 5 —
and any retune must preserve that strict
ordering on both the scales and the caps, or two kinds collapse into reading as
peers.

**`planet.max_height` is the governor of the whole chain, not just the planet.**
Every other kind derives from the *rendered* primary height, so this one number
decides where the entire hierarchy stops growing — raise a station cap without it
and nothing moves. 40 is derived rather than chosen: it is the value at which each
kind's existing scale lands exactly on the top rung of its art ladder (port
`0.3 × 40 = 12`, starbase `0.35 × 40 = 14`, ship `0.2 × 40 → 7`), so the scales keep
their playtested ratios and the best art becomes reachable at the same time. This is
the second saturation bug, and the subtler one: at `planet.max_height: 26` with
`port 19×8` / `starbase 22×9` / `ship 36×5`, the chain froze around **terminal height
40** and every rung but stardock's stayed unreachable at *any* size, so a 100-row
console drew the same sprites as a 40-row one. `tests/test_sprite_seam.py::
test_shipped_caps_reach_each_kinds_top_rung` and
`::test_the_scale_chain_reaches_those_caps_at_a_full_size_planet` pin the two halves
— cap and scale — so neither can regress alone.

**Stardock is the deliberate exception to the cap rule.** Its cap (16) sits *below*
`round(0.6 × 40) = 24`, because its ladder stops at `15×15` — 16 already clears the
richest art there is, so the non-saturation rule has nothing left to protect. Do not
"fix" this by raising the cap to 24: the cap is **not inert**. A direct-open docked
screen falls back to the kind's bounds (§2, above) and `StationArtRow` sizes the row
from the returned box, so a 24-row cap pads the docked Stardock header to 24 rows
around 15 rows of art — which is how it was caught, as a wall of blank rows in the
station snapshots. `test_scene_art_is_optional_with_defaults` therefore asserts
`max_height ≥ min(round(planet.max_height × k), top_rung_height)`: the cap must clear
whichever of the scale chain and the art ladder binds *first*.

**The art ladder is the real ceiling.** Past these values config can do no more: the
richest rungs the vendored library holds are `trading_port 11×12`, `starbase 11×14`,
`stardock 15×15`, and `warship 46×7` (stations author only a `vertical` view). A port
is therefore never wider than 11 columns however large the terminal. Making one
bigger needs new tiers authored upstream in `sprite-art-designer` and re-synced
(`docs/SPRITE_ART_SYNC.md`) — never a bigger cap here, which silently buys nothing.

The port and starbase scales are deliberately small —
playtest feedback of 2026-07-17: at 0.35–0.4 an ordinary port read as a rival body
beside the planet, and at 0.5 a starbase (12 inked rows) did the same.
`port_scale` is nonetheless floored by the art at ~0.27: below that the scaled box
never clears 7 rows beside a planet, and `trading_port`'s 6-row rung is a bare
7-wide mast rather than its 11-wide silhouette. 0.3 is the compromise — the
silhouette at the larger primaries, still under the 0.35 playtest ceiling. At small
primaries the port legitimately steps down to that mast; that is the ladder doing
its job, not the bug described below. Note that a
starbase hosts the sector's market and takes the port's slot in the scene, so "the
port is too big" reports usually mean *this* sprite.
Because a small port scale would otherwise let ships outsize the port at mid
viewports, `ship_scale` (0.2, cap 7) must stay *below* `port_scale` on both scale
and cap; `test_default_scene_art_values` asserts the cap inequality and the
ship-below-port ordering. The inequality binds on **height only** — `ship.max_width`
(46) exceeds every station's, because ship art composes at roughly 6:1 and its width
is the open sky rather than a 2.4 aspect off its height.
A second, intentional quantiser exists in the sprite library: ships and stations
select from an authored discrete tier ladder and apply archetype-specific section
repeats rather than continuously tiling a band to the requested height. The selected
art is centred in the exact box, so a tier can leave a small amount of blank slack.
This is accepted by the scene layout; do not reintroduce continuous grammar tiling in
Edge.

**The scene must ask for a box that clears a whole tier.** The library selects a tier
by the requested *height* alone and then centre-crops that tier's natural width down
to the requested width. A box narrower than the selected tier therefore returns the
*middle* of the art — for a ship, the repeating hull band with the prow and drive cut
off, which reads as a one-row band; for an ordinary port, a bare mast. Edge resolves
this at the seam: `edge/art/sprites.py` → `fit_box` walks the ladder richest-first for
the top rung that fits the box on **both** axes and returns that rung's natural size,
and `generate_sprite` renders there and pads the result back into the requested box.
Two consequences for anyone tuning `scene:`:

- The tier ladder *is* the responsiveness mechanism on the width axis. A narrow sky
  must step a ship down a rung (`medium` → `compact`), never shave columns off the
  rung above. `_paint_ships` accordingly passes the sky it actually has as the width
  bound; it must not impose an aspect ratio of its own — ship art composes at roughly
  6:1 (`7×46`, `5×34`, `3×17`), so the old `height × 3` bound selected a tier three
  times wider than the box it was drawn into.
- A cap that clears no rung is a silent breakage, not a smaller sprite. `port` capped
  at 6 rows selected `trading_port`'s 3-wide mast tower instead of its 11×7
  silhouette, and `ship` capped at 16 columns cleared nothing at all (17 is the
  narrowest rung). `tests/test_sprite_seam.py` asserts every vendored subtype clears a
  whole tier at its configured cap, so a future cap change — or a synced asset whose
  ladder moved — fails there rather than in the eye.

The Sector composer records the two rendered inputs `(primary_height, body_height)` on
`SectorScene`, which publishes them as the app's current `sector_station_reference`
(tagged with the rendered sector's internal id). PortScreen, StardockScreen, and the
starbase screen feed those same inputs and their own kind back through
`station_dimensions`. They do not recompute against banner height or
`planet.max_height`; once the Sector view is hidden, config alone cannot reconstruct its
viewport-dependent rendered primary height. A direct-open developer/test screen with no
preceding Sector render falls back to that kind's maximum bounds because no rendered
reference exists. Callers that know their station's internal sector id pass it as
`station_icon_dimensions(..., expect_sector=...)`; a cached reference from a
*different* sector is rejected and falls back to the kind's bounds rather than sizing
the header from stale inputs (the docking flow always renders the station's sector
last, so a mismatch is an invariant bug, not a normal state). PortScreen and
StardockScreen pass it; the starbase screen cannot yet, because `StarbaseDTO` carries
only the display id.

The sprite engine may crop transparent padding to ink for Sector placement, but the
requested generation box—the sizing decision—is shared.

## 3. Placement: why each thing goes where it goes

- **The primary body rides well right of centre and is allowed to run off the edge**
  (`_PRIMARY_CENTRE`, 78% of width). Offset far enough to leave one coherent region of
  open sky on its left — a single large void reads better than two slivers, and it is
  where ships and tags breathe. The disc is deliberately *not* required to fit whole:
  a world filling the window reads as bigger, not broken, and the columns saved by
  clipping the limb are exactly the columns traffic needs. `_PRIMARY_MIN_VISIBLE`
  (70%) is the counterweight — enough of the disc stays on screen that it still reads
  as a world — and `primary_body_height` solves that bound for the radius.

  This replaced an earlier rule that centred at 60% and forced the whole disc on
  screen (`(w - 4) // 2`). That spent the scene's width on the object which was
  already the subject: the planet got bigger, the sky got narrower, and the ship
  ladder stepped traffic *down* — so growing the planet made the ships smaller. At a
  120-column scene the change takes ships from the 17-column rung to the full 46×7
  one while the planet still grows, at a cost of ~8 clipped columns.
- **The disc yields width to keep one whole ship rung.** The planet and the traffic
  share a single width budget — ships ride the sky *left* of the primary, so every row
  the disc gains costs two columns there. Left alone, a growing planet squeezes that sky
  below the 36-column rung and the ladder drops traffic to its 17-column stub, which is
  *smaller* than before the planet could grow at all (this is what raising
  `planet.max_height` to 40 exposed). `_paint_planet` therefore trims the disc back to
  `_SHIP_SKY_RESERVE` (42 = the 36-column rung plus `_paint_ships`' 6 columns of inset)
  when it would otherwise cross that line. The gate tests the **rung, not the width**:
  ship *height* also scales off the planet, so trimming the disc shrinks the very ship
  the extra columns were for — below ~23 planet rows the trade buys a 36-column berth
  for a ship only tall enough to draw the 17-column rung, so it is skipped and stepping
  the ship down stays the intended behaviour (§2). Measured across 525 scene sizes the
  reserve costs at most 2 planet rows, and only ever where it buys a full ship rung.
  Belts are exempt: they anchor to the right edge and size from their own sprawl.
- **A belt is a field, not a body — traffic flies through it.** An asteroid belt is the
  one primary that reserves *nothing* and does not confine ships to its left. It is
  loose rock spread across the sky; things fly among it, and the sprite is speckle that
  a hull paints straight over. Reserving its rect fenced off the two-thirds of a wide
  canvas it sprawls across and crushed the port and both ships into the strip beside
  it — every belt scene in the 2026-08-16 gallery pass came back at the bottom of the
  ratings for exactly that (*"use more of the space by overlapping the asteroid
  field"*). `_paint_planet` sets `_belt_primary`, which suppresses both the reserve and
  the `body` argument to `_paint_ships`. Every other primary — planet, wormhole, black
  hole, nebula, wreck-as-primary — is solid and reserves as before.
- **The station hovers at the world's lower-left limb**, overlapping the disc's bounding
  box by about a third of its own width. Orbiting infrastructure belongs *at* the world;
  the overlap is what makes it read as "in orbit here" rather than "next to it". Its
  offset is computed from the planet's rect, so it follows the disc wherever the disc goes;
  its *size* comes from the rendered primary's height through the resolver in §2.
- **A lone station drifts.** With no world to pin it, its berth is drawn per sector from
  a seeded RNG — deterministic (the same sector always looks the same) but varied, so a
  chain of port-only sectors doesn't render as one repeated postcard.
- **Ships ride the open sky** left of the primary, each in its own horizontal **band**
  of the full canvas height, jittered in column and row inside it. The band is the depth
  slot (§2.1) as well as the anti-collision rule, and three things protect it:
  - the jitter stops `_SHIP_BAND_GAP` rows short of the next band, so two ships can
    never land flush against each other. Jittering across the whole band let one ship
    draw near the bottom of its band and the next near the top of its own, which is how
    a 52-row scene came back with the station and both hulls sharing four rows and
    forty rows of empty sky (*"everything appears in one line horizontally"*);
  - the bands span to the bottom of the canvas rather than stopping a ship-height
    short, so the lowest berth actually reaches the lower screen;
  - each berth must hold a **standoff** from everything already placed, not merely
    avoid overlapping it — `_SHIP_STANDOFF` tries 6×2, then 3×1, then the bare 1-cell
    pad. A ship that merely fits beside another hull or a station still reads as
    crowding it (*"ships too close to each other"*, *"ship too close to port"*, five
    scenes). `_has_clearance` **clamps** the standoff at the canvas edge rather than
    requiring it to fit, or a ship berthed against the screen edge — the one place
    traffic reliably rides — would be refused for wanting clearance off-canvas.

  Candidate columns are the coarse offsets first (they keep a crowded scene from
  degenerating into a row of near-identical berths) and then a full fine sweep: the
  coarse list alone stepped over the single pocket that fit and dropped a third ship to
  a text row with clear sky three columns away. Ships face the world they've arrived
  at; with nothing to face, the second of a pair may face the first.
- **Wrecks berth hard against the left screen edge, as low as they can, with as wide a
  standoff as that berth allows** (14×5 → 1×1; the left bias never relaxes). The
  fiction earns the rule: live traffic and stations keep their distance from a hulk, so
  the hulk gets the far shore of the scene. Two ordering details carry it:
  - the **row is the primary key and the standoff the tiebreak**. Searching
    standoff-first put the hulk wherever the widest clearance happened to be — mid-
    height on a crowded 67-column scene, which reads wrong and eats the middle band
    traffic needs. The wide standoff is also less load-bearing than it was: ships now
    enforce their own clearance from everything, so keeping traffic off the hulk no
    longer rests on the hulk's rect alone;
  - the secondary find is painted **before** the ships. It is the one object with no
    ladder to step down and only one shore it may take, so placing it last let three
    hulls occupy the left edge and pushed the wreck out of the picture into a text row.
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

### 4.1 Docked station headers

PortScreen, StardockScreen, and the starbase screen pair the station exterior on the
left with a service banner on the right. `StationArtRow` owns their shared layout:

- it reruns `station_dimensions` with the exact rendered inputs published by the
  Sector composer;
- the banner remains 8 rows at standard tier and 12 rows at wide tier;
- the row height is the taller of exterior and banner, and the shorter child receives
  an explicit vertical offset so their midpoints align;
- when an odd/even height pair makes exact cell centring impossible (for example a
  9-row port beside an 8-row banner), the half-row is biased downward instead of
  leaving both tops aligned;
- ordinary PortScreen alone adds one blank row above the art/banner pair. Stardock and
  starbase spacing is unchanged.

The Stardock exterior always requests the procedural `stardock` subtype. Scaling must
never route it through `trading_port`; its beacon, docking arms, taper, and engine glow
are part of its identity.

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

`config/default.yaml → scene:` — `planet.max_height` (the governor of the whole
chain, per §2, not merely the subject's own cap); independent `port`, `stardock`, and
`starbase` min/max footprint blocks; independent `port_scale`, `stardock_scale`, and
`starbase_scale`; `ship_scale`; `max_ships_shown` (sprite cap before text-row
overflow); and `ship_face_inward_chance`. The shipped file uses station scales
0.3 / 0.6 / 0.35 respectively; the schema defaults mirror it, so older config-less
saves get the same values. When retuning a station scale or `planet.max_height`,
re-derive that kind's `max_height`/`max_width` per the cap rule in §2 — a stale cap
reintroduces the frozen-station bug — and preserve the tier ordering (planet ≫
Stardock > starbase > port > ship) on both scales and caps; in particular keep
`ship_scale`/`ship.max_height` below the port's, or traffic outsizes the smallest
station kind.

**Raising a cap alone changes nothing.** The two ceilings are independent and both
bind: the scale chain off `planet.max_height` has to reach the cap, and the cap has
to clear a whole rung of the art. A "sprites are too small" report is almost always
the first of those — check `planet.max_height` before touching a station block, and
confirm against the art ladder (§2) that the rung you want exists at all.

The rest of the layout is module constants beside the placement code in
`edge/tui/widgets.py`, not config — they are compositional intent, not balance, and
moving one means rereading the section that argues for it:

| constant | §  | what it decides |
|---|---|---|
| `_PRIMARY_CENTRE` (0.78), `_PRIMARY_MIN_VISIBLE` (0.7) | §3 | where the disc sits and how far it may clip |
| `_SHIP_SKY_RESERVE` (42), `_SHIP_SKY_MIN_RUNG_ROWS` (5) | §3 | when the disc yields width to keep a whole ship rung |
| `_SHIP_DEPTH_MAX_STEPS` (2), `_SHIP_FIT_STEPS` (3) | §2.1 | how far traffic steps down the ladder for depth, and for fit |
| `_SHIP_STANDOFF`, `_SHIP_BAND_GAP` (3) | §3 | how much clear sky a ship holds around itself |
| `_STATION_LIMB` (0.72) | §3 | how far down the limb a station berths |
| `_FIND_PRIMARY` (0.82), `_FIND_SECONDARY_MAX` (10) | §2 | how big a space find draws in each slot |

The first four rows are consumed by `primary_body_height`, which is a module function
precisely so the responsiveness sweeps in `tests/test_sprite_seam.py` exercise the
composer's own rule rather than a copy that can drift. The composition rules that came
out of the 2026-08-16 ratings pass are pinned by
`::test_ship_depth_reads_top_to_bottom`,
`::test_ships_keep_a_vertical_gap_from_each_other`,
`::test_a_belt_reserves_nothing_and_traffic_uses_the_whole_canvas`, and
`::test_no_object_in_the_review_matrix_falls_out_of_the_picture` in the same file,
which run the real composer over the real `scene_gallery` matrix at all four tiers.
Docked vertical centring lives in `StationArtRow`, not in per-screen ad-hoc margins.

## 8. Open follow-ups (2026-08-16 ratings pass)

Four things the ratings pass asked for that are **not** in the shipped scene. They are
recorded here rather than in a tracker because each one is a change to the rules above,
and the argument against doing it casually is the same argument this note exists to
preserve.

### 8.1 A port cannot grow — it needs upstream art (in progress)

The most-repeated complaint in the pass was scale, not placement: *"port too small"*,
*"ships overpower port"*, *"can't see the port"*, and the gallery's own
`port is 11x8 on a 150x52 canvas — tiny for the space available` on nine cells.

**Config cannot fix any of it.** `trading_port`'s richest rung is `11×12` and
`starbase`'s is `11×14`, so a port is never wider than 11 columns however large the
terminal (§2, *the art ladder is the real ceiling*). §2.1's ship-depth ladder was
adopted precisely because it was the only lever on Edge's side — it closes the gap from
the *ship's* end by stepping far traffic down.

The real fix is a richer port tier authored upstream in `sprite-art-designer` and
re-synced. When one lands, the work on Edge's side is:

1. re-derive `scene.port` / `scene.starbase` `max_width`/`max_height` against the new
   rung, per the cap rule in §2 — a cap that clears no rung is a silent breakage, and a
   cap that saturates below the planet's range freezes the station;
2. keep the §1 tier ordering (planet ≫ Stardock > starbase > port > ship) on both the
   scales and the caps;
3. re-check whether `_SHIP_DEPTH_MAX_STEPS` should come *down*. It is at 2 because the
   station could not be made bigger; a genuinely larger port may want traffic stepped
   less hard, and §2.1's second bullet is the thing to re-read;
4. run `tests/test_sprite_seam.py::test_every_subtype_renders_a_whole_tier_at_its_scene_box`
   and the review matrix (`pixi run scene-gallery`), and update the ladder table in
   `docs/SPRITE_ART_SYNC.md` §4.

### 8.2 A secondary find cannot pass behind the primary

Asked for twice — *"the wreck could be larger and BEHIND the planet"*, *"put space
debris in the empty space to the right of the Vesk Trader and behind planet"*.

Today a secondary find berths hard against the **left** screen edge (§3) and is painted
after the primary, so it can only ever sit beside the world, never behind it. Doing it
properly means painting the find *before* the primary so the disc occludes it, and
relaxing the left-edge bias so it can berth under the disc — which trades away the
"hulk gets the far shore" rule that §3 argues for. Worth doing, but it is a deliberate
reversal of a stated rule, not a tweak.

### 8.3 The disc still does not crop as hard as asked at 87 columns

Five scenes at `87×36` asked for a bigger, more cropped primary — *"planet should be
more cropped off screen so ships don't need to be aligned as much"*.

`_SHIP_SKY_RESERVE` is what stops it: at that width it trims the disc from 28 rows to
25 to buy the near ship a 36-column berth (§3). §2.1's depth ladder answered the
*symptom* the note describes — the ships no longer have to line up, because the far one
steps down — but the disc is the same size it was. Revisiting the reserve means
re-reading §3 and re-running
`::test_a_growing_planet_never_starves_the_sky_below_a_whole_ship_rung`, which exists
because removing the reserve once made a bigger planet produce *smaller* ships.

### 8.4 Per-scene station nudges are unaddressed by design

Six notes of the form *"move the Orbital Platform up and to the right a couple of
spaces"*, *"port needs to be further down vertically"*, *"I would put the port caption
below it"*. A lone station's berth is drawn from a seeded RNG so a chain of port-only
sectors does not render as one repeated postcard (§3), so these are taste on one draw
rather than a rule. Most of what prompted them was crowding, which `_SHIP_STANDOFF`
removed — re-run the gallery before tuning `_STATION_LIMB` or the lone-station range.

## 9. Forthcoming: fog-safe priority and station-reference projection (WP-SC01)

Not yet wired into `_SceneComposer` — this is what has landed on the server/DTO
boundary toward `docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md`'s replacement solver
(§2.3/§4.6 of that plan). The eventual solver's retention rule reads from this
projection; the shipped composer above does not yet consume it.

- `SectorShipDTO` carries three new fog-safe fields: `retention_class` (`"hostile"` /
  `"neutral"` / `"friendly"` / `"player"` / `"unidentified"`), an opaque
  `hostility_ordinal` (0 = most retention-worthy within its class; ties share an
  ordinal), and a `combat_threat_rank` (0 = highest threat, scene-wide) — never the raw
  adjusted disposition or its private inputs (attitude offset, grudge severity,
  alliance standing). The ordinal orders on `edge.core.aliens.encounter_disposition`,
  the exact final quantity `core.encounters.roll_encounter` rolls its greeting-vs-
  violence check against, so the client-visible ordering can never disagree with the
  real encounter rule. Both are computed once over the sector's whole vessel multiset
  (`edge.core.aliens.ship_retention_ordinals`) — never per object during DTO
  construction — so rebuilding the same sector state in any container order reproduces
  identical values (a requirement for the eventual solver's resize hysteresis, which
  compares plans built from separately constructed DTOs).
- `StarbaseDTO` carries the internal `sector_id` (as `PortDTO.sector_id` already does),
  closing the `expect_sector` gap noted in §2's docked-header contract: `BaseScreen`
  (`edge/tui/screens/base.py`) now passes it to `StationArtHeader`, so a stale cached
  `sector_station_reference` is rejected there the same way the Stardock header
  already rejects one via `PortDTO.sector_id`.
- Wire version 44. See `edge/server/wire.py`'s `WIRE_VERSION` docstring for the full
  changelog entry.


## 10. The physical model now matches this composer's station sizes (WP-SC12)

Nothing in §§0-9 changes: `_SceneComposer` and `SceneArtConfig`'s
`planet`/`port`/`stardock`/`starbase`/`ship` sizes, scales and caps are
untouched. (At the time this section was written the legacy composer was still
what live play rendered by default; WP-SC11 has since made the physical model
the default — see this note's top-of-file Status line.)

What changed here, before that later default flip, was on the other side of
the eventual cutover. The replacement pipeline
(`edge/scene/`, `docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md`) now reproduces this
document's station scale chain exactly, so a port / Stardock / starbase renders
at the same size under either composer. Read that plan's "Station size parity"
subsection of §9.6 for the mechanism and the measurements; the parts that touch
*this* note are:

- **`primary_body_height` is now load-bearing across the seam.** The physical
  model carries it as `scene.physical_model.station_size_reference`, coefficient
  by coefficient — `9/10` for the `body_h * 0.9` term, `4` header rows,
  `11/20` for `visible_cap`, and `planet.max_height`/`min_height` as the clamps.
  **If you retune `_PRIMARY_CENTRE`, `_PRIMARY_MIN_VISIBLE`, `planet.max_height`
  or the `0.9` body-budget factor, update that config block in the same change**,
  or the two composers silently disagree about station size. The one term
  deliberately *not* mirrored is the `_SHIP_SKY_RESERVE` trim, which is a
  legacy-layout artifact and is rung-neutral across the calibrated canvases.
- **`port_scale` / `starbase_scale` / `stardock_scale` are mirrored too**, as
  `scene.physical_model.station_target_by_scale_class[*].parent_scale`
  (`3/10`, `7/20`, `3/5`), with `lone_scale` `3/5` for the planetless branch and
  each kind's `SpriteSize` min/max height as the clamps. Same rule: change one
  side, change the other.
- **The `scene:` block gained two fields and one scale class.**
  `orbit_offset_region_by_scale_class` says where a station may sit *relative to
  its parent planet* (the absolute `region_by_scale_class` is now only used when
  a station has no planet), and `starbase` is its own `scale_class` beside
  `stardock` and `orbital`, so §1's `Stardock > starbase > port` ordering is
  finally expressed as apparent scale rather than shared between two kinds.
- **The port render seed matches.** `_paint_station` seeds a port sprite from
  `sec.sector_id` and a starbase from `starbase_id`; the physical model now does
  the same, so within one authored tier both composers pick the same variant and
  the ink boxes agree cell for cell, not merely tier for tier.

`edge/devtool/scene_parity.py` measures the whole claim
(`pixi run python -m edge.devtool.scene_parity`), and
`tests/test_scene_legacy_parity.py` guards it in CI. One cell of the matrix is a
known, named miss — see the plan.

## 11. The physical model's solver: units, retention, and placement

§10 covers where the physical model's station *sizes* land relative to this
composer's own scale chain. This section covers the mechanics that decide
*what* the physical model shows and *where* — the counterpart, for
`edge/scene/` + `edge/art/scene_paint.py`, to §§0-6 above for `_SceneComposer`.
Nothing here changes when either composer is selected; both are live and
independently tested (§0's status line, `tests/test_scene_legacy_parity.py`).

### 11.1 Units: exact arithmetic, no floats in a decision

An **ink cell** is a rendered cell whose character is not `" "` — the same test
`_SceneComposer._paint` already applies so stars show through sprite gaps
(§4.1); the physical model's catalogue and paint stage use the identical rule
rather than inventing a second one. **Ink bounds** are the smallest rectangle
enclosing a render's ink cells; **ink count** is how many there are. Bounds
drive geometry (does this fit); count drives cost and density only.

World positions, radii, depths, and face extents are integers in a **scene
unit (su)** — there is no world-space float, and the su-to-cell relationship
exists only once a `ProjectionStrategy` projects a position, so su carries no
fixed cell size of its own. Every intermediate that feeds a comparison or a
rounding is a `fractions.Fraction`, never a `float` — cell rounding is `floor`
for positions and round-half-even for extents, applied to the exact fraction,
so a boundary case is defined rather than platform-dependent. `float` appears
only in diagnostic fields nothing reads back. `cell_aspect` (a `Fraction` from
config; `2/1` mirrors this composer's own `width = 2 x height` disc rule, §2)
converts a square su face into the taller-than-wide terminal cell grid.

A **scale class** (`edge.scene.classify.SCALE_CLASSES`) is a config-named
bucket — `anchor`, `entity`, `stardock`, `starbase`, `orbital`, `wreck`,
`ship`, `belt` — ordered by nominal face area (`width_su * height_su` of the
axis-aligned bounding box, exact even for a circle/ellipse, since a class's
shape is fixed per kind and bounding-box area changes no ordering versus
`pi*a*b`). The shipped areas read `anchor 1800 > entity 476 > stardock 352 >
starbase 238 > port 168 > wreck 96 > ship 60`, which is this composer's own
§1 tier ordering (planet ≫ Stardock > starbase > port > ship) expressed as
apparent scale rather than merely as config scale factors. Stardock and
starbase are their own scale classes — not shades of a shared `orbital` — for
exactly the reason §2's caps insist Stardock never crops through
`trading_port`: without a distinct class, `Stardock > starbase > port` had no
size lever separate from the shared bucket's single target.

A **structural mode** (`wide` / `standard` / `compact`) is selected from the
drawable scene viewport by an ordered list of `(min_cols, min_rows, mode)`
thresholds, most-permissive first — independent of terminal tier and of
`art_detail`, the way this composer's own bands are.

### 11.2 Retention order: what survives when the scene must shed something

`SceneRetention` (`edge.scene.model`, an `IntEnum`, lower value retained
first) orders `ENTITY, ANCHOR, ORBITAL, HOSTILE_SHIP, NEUTRAL_SHIP, WRECK,
FRIENDLY_SHIP`. The Entity hint and the primary body are protected before
anything else — they are what makes the sector legible at all — hostile
traffic outranks neutral and wreck because a threat is plot-critical to show,
and ordinary friendly traffic is shed first because it is the least
consequential thing on screen. This plays the same role §3's ship-depth and
station-limb rules play for the legacy composer: a promise about what a
crowded scene keeps, stated as a numbered order instead of a placement
heuristic.

### 11.3 The solve loop

`edge.scene.solve.solve()` searches an all-integer/rational space — the whole
comparison between two candidate scenes is a lexicographic tuple of integers,
never a weighted float score, which is what keeps the promise auditable rather
than a matter of taste:

1. Sort admitted objects by `(retention, hostility_ordinal, -threat_rank,
   key)` — the fog-safe ordinal from `SectorShipDTO` (never the raw disposition
   or its private inputs, §9 above) breaks ties within a retention tier the
   same way the real encounter rule would.
2. Pick the **anchor** — the admitted object with the largest face area — and
   ask the active `ProjectionStrategy` to frame a camera against it.
3. Sweep camera candidates (height first, since that decides whether the
   anchor fits at all, then a bounded lateral aim offset) and attempt each:
   project every object, then place and admit them in retention order inside
   one joint evaluation (§11.4).
4. If no candidate's hard rules all pass, fall back in order: step the anchor
   down its own box-class ladder (a continuous kind only), then reject the
   single lowest-retention object and retry. A rejected object is never
   re-admitted within the same solve, so the loop is monotone and terminates.
5. Compare every attempted candidate — including failing ones — on an integer
   tuple: how many objects of each retention tier it rejected (most-protected
   tier first, so no number of low-priority admissions ever outweighs one
   higher-tier rejection), then admitted count, minimum-size violations,
   distance from the anchor's target size, separation slack, an integer
   hysteresis penalty against the previous plan, and finally the plan's own
   content hash as a stable tie-break — never iteration order.

The **hard rules**, cheapest and most-rejecting first: near-plane and viewport
containment; minimum projected size for the object's scale class; a ladder
rung (or continuous box class) that actually clears; separation between
inflated ink boxes (skipped for permeable fields — the physical model's
belt, exactly like §3's "a belt is a field, not a body"); occlusion by depth,
enforcing a minimum visible fraction of the farther object of any overlapping
pair; equal-depth scale-class ordering; and the scene's cumulative render-cost
budget plus an emergency ship-count ceiling.

**Hysteresis** — an integer L1 distance between this candidate and the
previous plan's camera height, object positions, admitted set, and art
box sizes, weighted from config — is only ever the second-to-last term of the
comparison tuple, so it can reduce jitter between resizes but can never
outrank a hard rule or a retention-tier difference. This is the physical
model's counterpart to this composer having no equivalent concept at all: a
legacy scene simply re-derives from scratch every render, while the physical
model deliberately damps resize churn.

### 11.4 Joint secondary-object placement

Everything except the anchor and other fixed-position objects (a planet's
orbiting station, say) is `flexible`, and flexible objects are placed inside
the same per-candidate evaluation that checks the hard rules, not as a
separate step before or after the camera search — the two were tried apart
early on and the split could not reach a workable admission rate, because a
position chosen against one camera was then judged against whatever camera
the sweep eventually settled on. Placement proceeds in strict retention order:

- each object's placement **region** — the su box it may move within, and for
  an orbiting object an offset from its already-placed parent rather than an
  absolute box — narrows to the feasible depth band for the current camera
  (found by two bounded binary searches over `strategy.project()`, since
  "too big" and "too small" are each monotonic in depth for both shipped
  strategies) intersected with the visible screen-space extent at each
  sampled depth;
- within that band, candidate depths are walked **near to far** (the nearest
  workable depth wins the richest reachable art, matching this composer's own
  "near hull claims the richest rung" rule in §2.1), and at each depth a
  handful of screen-space lattice slots are tried, rejecting any that overlap
  an already-placed object's inflated ink box by cheap integer rectangle
  arithmetic before spending a real projection on it;
- the object's cost is checked against the shared budget **before** its
  cheapest rung is attempted and again against whichever rung placement
  actually selects, so a candidate too dear for what remains is skipped in
  favor of a cheaper, farther one rather than the object being dropped
  outright;
- because placement is greedy and ordered by retention, a higher-priority
  object is never moved to make room for a lower one — the object that wins a
  contested slot is always the one this composer would also protect first.

Two rung-selection rules ride on top of the depth/slot search, both aimed at
the same complaint — objects rendering at their worst authored tier even on a
roomy canvas:

- **A minimum-richness floor.** `min_rung_index_from_end_by_scale_class`
  excludes a scale class's worst rungs from `_select_rung` outright (as a real
  exclusion on the candidate set, not a bigger absolute cell-count floor,
  since authored rung sizes vary too much by subtype for one number to bind
  correctly everywhere) — a station never renders at the single poorest tier
  of its ladder, matching this composer's §2 art-ladder ceiling in spirit:
  config cannot buy a bigger rung than the art has, but it can refuse the
  worst one that does exist. Ships are deliberately excluded from this floor —
  `DepthLayeredAnchorProjection`'s quantised depth steps make the resulting
  z-band fall between layers often enough to collapse ship admission instead
  of improving it.
- **Cost-aware rung selection.** `_select_rung` filters by an optional
  affordability ceiling *before* ranking rungs, so the cheapest rung that
  still fits the projected box is preferred over refusing the object outright
  because the richest fitting rung was too dear. This can only ever remove a
  candidate, never promote one to a higher cost class, so it cannot violate
  the render-cost-in-retention-order rule above.

### 11.5 Art resolution and paint

For each accepted projection, far to near: resolve the rung's natural box (or
the continuous kind's selected box class), render at that box with a seed
drawn from stable identity (sector id for a port, matching this composer's own
`_paint_station` seed, so the two composers draw the identical variant at the
identical size within one authored rung), crop to ink, and paint into the
scene's cell grid with transparent spaces exactly as this composer's own
`_paint` does. If the actual ink exceeds the estimate used during solving, one
bounded correction re-checks the affected hard rules against the real box —
shrinking one rung or box class, or rejecting — but never raises the object's
cost class and never restarts the camera search. The render cache is keyed by
`(entity_type, subtype, seed, box, facing, archetype, treatment)`, and the
docked-header contract (§2/§4.1 above) is served from the same resolved
`(sector_id, station_kind, object_id) -> natural size` mapping this composer's
`sector_station_reference` already publishes — one seam, two composers.

Glyphs (fighters, mines) scatter after every ink box is placed: a local,
sector-seeded RNG walks free cells and drops a glyph that clears a configured
spacing from ones already placed; a glyph that finds no room in a bounded
number of tries is dropped from the scene and reported through the sidebar
instead, never as scene text — the physical model has no in-scene text-row
overflow at all (unlike this composer's `_deferred` text rows, §4); its
equivalent promise is named sidebar overflow.
