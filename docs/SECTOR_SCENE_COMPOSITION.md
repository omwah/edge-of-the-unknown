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
| other space finds (wormhole, black hole, wreck-as-primary) | ~60% of body height | compact phenomena |
| ordinary port | `scene.port_scale` × rendered primary height, clamped by `scene.port` | independently tunable port footprint |
| Stardock | `scene.stardock_scale` × rendered primary height, clamped by `scene.stardock` | independently tunable flagship silhouette, never ordinary-port art |
| starbase | `scene.starbase_scale` × rendered primary height, clamped by `scene.starbase` | independently tunable orbital-base silhouette |
| ship | `scene.ship_scale` (0.2) × primary height, slimmed further if the open sky is narrow | traffic — must stay below `port_scale` so a visiting ship never outsizes the port |
| fighters / mines | single glyphs (`▴` / `✺`) | presence, not objects |

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
`port 16×6`, `stardock 38×16`, `starbase 22×9` for scales 0.25 / 0.6 / 0.35 against
`planet.max_height: 26`. Those values realise the §1 tier ordering **planet ≫
Stardock > starbase > port > ship** at every viewport — at a full-size planet the
chain is 26 ≫ 16 > 8–9 > 6 > 5 rows — and any retune must preserve that strict
ordering on both the scales and the caps, or two kinds collapse into reading as
peers. The port and starbase scales are deliberately small —
playtest feedback of 2026-07-17: at 0.35–0.4 an ordinary port read as a rival body
beside the planet, and at 0.5 a starbase (12 inked rows) did the same. Note that a
starbase hosts the sector's market and takes the port's slot in the scene, so "the
port is too big" reports usually mean *this* sprite.
Because a small port scale would otherwise let ships outsize the port at mid
viewports, `ship_scale` (0.2, cap 5) must stay *below* `port_scale` on both scale
and cap; `test_default_scene_art_values` asserts the cap inequality and the
ship-below-port ordering.
A second, minor quantiser exists downstream: archetype station grammars stack 2-row
repeat blocks, so odd requested heights ink one row short (centred in the box by
`render_grid`) — acceptable slack, not worth perturbing the deterministic silhouettes.

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

- **The primary body rides just right of centre** (disc centre ≈ 60% of width). Centred
  enough to be the subject, offset enough to leave one coherent region of open sky on
  its left — a single large void reads better than two slivers, and it gives ships and
  tags somewhere to breathe. A disc may crop slightly at the edge, like a world filling
  a viewport; that is deliberate drama, not overflow.
- **The station hovers at the world's lower-left limb**, overlapping the disc's bounding
  box by about a third of its own width. Orbiting infrastructure belongs *at* the world;
  the overlap is what makes it read as "in orbit here" rather than "next to it". Its
  offset is computed from the planet's rect, so it follows the disc wherever the disc goes;
  its *size* comes from the rendered primary's height through the resolver in §2.
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

`config/default.yaml → scene:` — `planet.max_height` (rendered subject cap only);
independent `port`, `stardock`, and `starbase` min/max footprint blocks; independent
`port_scale`, `stardock_scale`, and `starbase_scale`; `ship_scale`;
`max_ships_shown` (sprite cap before text-row overflow); and
`ship_face_inward_chance`. The shipped file currently uses station scales 0.25 / 0.6 /
0.35 respectively; the schema defaults mirror it, so older config-less saves get the
same values. When retuning a station scale or `planet.max_height`, re-derive that
kind's `max_height`/`max_width` per the cap rule in §2 — a stale cap reintroduces the
frozen-station bug — and preserve the tier ordering (planet ≫ Stardock > starbase >
port > ship) on both scales and caps; in particular keep `ship_scale`/
`ship.max_height` below the port's, or traffic outsizes the smallest station kind.

The centring factor (0.6) and the belt/nebula width multipliers live beside the
placement code in `_SceneComposer` — they are compositional intent, not balance, and
moving them means rereading §3. Docked vertical centring lives in `StationArtRow`, not
in per-screen ad-hoc margins.
