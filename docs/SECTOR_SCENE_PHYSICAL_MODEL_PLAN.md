# Sector scene physical-model composition plan

> Companion to `DESIGN.md`, `SECTOR_SCENE_COMPOSITION.md`, `UI_MOCKUPS.md`, and
> `SPRITE_ART_SYNC.md`. `DESIGN.md` is the
> authoritative *what*; this document is the *how and in what order* for replacing
> the shipped arrival-view composer. The existing scene note remains authoritative
> for current behavior until the replacement lands.
>
> **Status: reviewed plan — composition interview and review corrections approved
> 2026-09-01, with the art-seam, cost, determinism, and packaging corrections of the
> second review folded in the same day.**

## 1. Outcome

Replace the direct paint-as-you-decide `_SceneComposer` with a deterministic,
presentation-only physical scene model. Each visible sector object receives a simple
camera-facing 2.5D shape, a physical parent and allowed placement region/depth range, a
nominal face-area scale class, and a gameplay retention priority. A swappable projection
strategy frames the
highest-ranked subject, projects the accepted objects into terminal-cell bounds, and
selects an existing sprite tier for laddered art or a continuous render box for
procedural art. Fixed-FOV perspective and depth-layered anchor projection implement the
same contract; calibration and explicit review choose the shipped default from measured
composition quality and cost rather than this plan preselecting one.

The system must make every decision inspectable. For each accepted or rejected object,
the gallery and tests must be able to report its physical parent, face shape/area,
generated position/depth, projected bounds, art choice, occlusion, minimums, priority,
and the rule that accepted, moved, or rejected it.

This is presentation only. It adds no authoritative in-sector coordinates, consumes no
game-state RNG, enters no command log or state hash, and changes no game rule. Stable
sector/object identity seeds the local model, so the same DTO and viewport always
produce the same scene.

## 2. Approved design contract

### 2.1 Physical relationship tree

```text
Scene inventory
├─ Entity (foremost subject when present)
├─ Generated space discovery (at most one)
│  ├─ Nebula, black-hole visual system, or wormhole (anchor-scale), or
│  └─ Wreck (wreck-scale)
├─ Planetary system
│  ├─ Planet
│  └─ Orbital infrastructure
│     ├─ Stardock
│     ├─ Starbase
│     └─ Port
├─ Asteroid field
├─ Wrecks and local discoveries
├─ Ships
└─ Presence glyphs
   ├─ Fighters
   └─ Mines
```

A generated sector contains at most one open-space discovery and never generates that
discovery beside a planet. That discovery may itself be a sensor-gated wreck—the most
common configured open-space kind—or an anchor-scale phenomenon. Runtime combat may
subsequently add one or more obvious wrecks to a planet sector or to a sector already
holding its generated discovery. The Entity anomaly is separate and may coexist with
either. The model handles at most one generated discovery, zero or more runtime wrecks,
and the independent Entity.

An anchor-scale discovery ranks above a planet in the general scale contract, but
current generation never places the two together. Its *visible phenomenon* supplies the
physical scale: a nebula's cloud and a black hole's accretion/lensing system matter, not
only the central body or event horizon. A generated wreck remains wreck-scale; being the
only discovery does not promote it to planet scale. The Entity overrides every other
anchor, is the foreground subject, and may occlude lower-priority objects subject to
their visibility floors; unlike a discovery, it can coexist with a planet.

### 2.2 Apparent-scale hierarchy

```text
Entity (foreground subject)
≫ nebula / black-hole visual system
≫ wormhole
> planet
≫ station
≫ wreck
> ship
≫ fighter / mine glyph
```

Wormholes are slightly larger than planets. Wrecks are slightly larger than ships.
The composer uses configurable *display* scale classes rather than literal kilometre
ratios: physical ordering is preserved, while controlled exaggeration keeps stations
and ships legible at terminal resolution.

### 2.3 Retention hierarchy

Physical size does not decide which optional object survives a constrained scene.
Gameplay importance does. Anchor selection is separate: the highest nominal face-area
class in the provisional admitted set frames the scene at that class's own calibrated
target fraction; being the sole object does not alter its retention rank or scale class.
If retention rejects that anchor, the bounded solve re-anchors to the highest class that
remains rather than retaining a lower-priority object merely because it framed first.
Re-anchoring changes the target fraction and therefore every projected box, so each
re-anchor is one of the counted, bounded solve passes of §6.2 rule 4: the count is
configured, reported in the trace, and a rejected anchor is never reconsidered for
admission in a later pass of the same solve, so reject → re-anchor → admit → reject
cannot cycle.

```text
1. Entity
2. Anchor-scale phenomenon or planet/body
3. Orbital infrastructure attached to the planet
4. Ships more hostile than neutral, ordered by encounter disposition
5. Ships exactly neutral
6. Every wreck, generated or runtime (the neutral comparison baseline)
7. Ships friendlier than neutral, ordered by encounter disposition
```

Lower final encounter disposition means higher retention priority, but the server does
not expose that raw float. It projects a coarse retention class around the approved
neutral/wreck baseline plus an opaque per-scene hostility ordinal that preserves the
exact within-class ordering after effective disposition, active grudges, and alliance
standing are applied, plus a combat-threat rank for equal disposition. Stable public
presentation identity is the final deterministic tie-breaker. Wrecks map *at* the neutral
point of that scale rather than beside it, and the class ordering above resolves the
resulting tie in the neutral ship's favour. The ordinal must be a pure deterministic
function of sector state — never an enumeration index over a DTO container — because
resize hysteresis (§4.11) compares plans built from separately constructed DTOs and would
otherwise churn admission for an unchanged sector. The TUI may not reach around the
projection boundary, reconstruct the
private inputs, or infer priority from species/player state. Fighters, mines, and other
presence marks do not participate in retention; after the solve they compete only for
free cells under their separate deterministic glyph rule.

An object that cannot be shown is omitted from the art scene and its name and omitted
state remain explicit in the sidebar/status drawer's complete object list. **Nothing
appears as a text-only row or overflow indicator inside the scene.** There is no fixed
maximum visible-ship count: the solver admits as many ships as meet the physical,
projection, and readability constraints, in retention order. Admission also spends a
configurable estimated render-cost budget keyed by
object kind and selected tier/continuous box class, so removing the fixed count does
not make final cold sprite generation unbounded. Calibration measures actual fog-safe
DTO inventories, including sensor-gated generated wrecks and runtime wrecks. Physical
fit and calibrated cost remain the ordinary bounds; a separately configured high
emergency ship ceiling protects against estimator or pathological-input failure and is
reported whenever it activates.

Spending cost in retention order alone would leave the budget constraining only the
cheap tail, because the anchor is priority 1–2 and §6.1 shows the anchor — a large
phenomenon — is the dominant cold cost. **A continuous anchor's render box class is
therefore a solver variable, not a fixed consequence of framing.** Under cost pressure
the solver may step that box class down a configured, calibrated ladder (which re-frames
the scene and is counted as a bounded solve pass, as above) before it rejects any
retained object. It may never reject the anchor for cost, and it may never step the box
below the anchor class's configured minimum ink extent; if the budget cannot be met at
that minimum, the scene is reported over budget in the trace rather than silently
degraded further. Laddered objects have no equivalent freedom: their cost follows the
rung the projection selects.

### 2.4 Camera and projection

- Expose projection behind one typed strategy interface. Calibration compares fixed-FOV
  perspective and depth-layered anchor projection; only the explicitly approved winner
  proceeds into the production solver. The interface remains extensible, but the losing
  experimental implementation is removed rather than doubling later test paths.
- Select responsive structural modes from the actual drawable scene viewport, after
  header/UI subtraction, never from the overall terminal tier.
- Use a hybrid responsive model: all modes share the physical hierarchy and solver;
  compact modes may impose stricter admissibility limits.
- Frame the Entity first when present. Otherwise frame the highest nominal face-area
  class present at that class's configurable target fraction of scene **height**. A
  generated wreck therefore frames at wreck scale, never the planet target.
- Adjust camera position and aim, not FOV. When a fit fails: adjust the camera first,
  then reposition flexible objects inside their allowed regions/depth ranges, then reject
  the lowest retention priority to the sidebar.
- Flexible objects may move deterministically within their allowed regions when the
  viewport changes. Their identity, parent, nominal scale, and allowed region remain
  stable; the trace must show a resize-driven position change rather than hide it.
- Accept the previous `ScenePlan` as an optional, disposable presentation input. Among
  otherwise valid solutions, prefer the camera, placements, admission set, and sprite
  sizes closest to that plan. Physical constraints and retention always override this
  hysteresis. The previous plan is not game state, persistence, replay, or wire data.
- Camera fitting must retain separation and edge margins rather than eliminate every
  void cell. Its objective and every constraint must be reported in the trace.
- Terminal cell aspect ratio is part of projection. Laddered ship and station art must
  select a complete rung from injected two-axis geometry; no selected rung may be
  centre-cropped. Procedural planets, belts, discoveries, and phenomena instead receive
  continuous render boxes whose estimated visible ink—not merely request boxes—drives
  framing and constraints.
- The solver selects rungs from the geometry catalogue directly. It must not route
  through the shipped `edge/art/sprites.py → fit_box`, whose contract deliberately ends
  in a clamp — "falls back to the smallest tier when nothing fits… cropping it is the
  least-bad option left" — that this model forbids. When no authored rung clears an
  object's available space, the object is rejected to the sidebar (§4.17); it is never
  clamped and cropped. That clamp branch remains correct for its own callers and is not
  changed here.
- Depth on the ladder is expressed as **projected height**, not as a rung index. Two
  ships of different subtypes at equal depth may sit on differently shaped ladders, so
  matching rung indices would render them at unequal apparent size — the failure the
  current composer already exhibits. Rung selection serves the projected height; it does
  not define it.
- The shipped ladder seam recognizes only `entity_type` `ship` and `port`; starbase and
  Stardock are port-kind subtypes. Every other kind is continuous unless that upstream
  contract changes and the vendored art/sync guards change with it.

### 2.5 Camera-facing 2.5D shapes and placement freedom

**Ink terminology.** In this plan, *ink* means terminal cells containing visible sprite
art rather than blank or transparent padding. The terms are used precisely:

- **request/container box** — every cell allocated to a render, including blank space;
- **natural sprite box** — the authored dimensions of one complete ladder rung;
- **ink cell** — a rendered cell containing a visible, non-blank glyph;
- **ink mask** — the exact set of ink cells in the rendered art;
- **ink bounds** — the smallest axis-aligned rectangle enclosing that mask; and
- **ink count** — the number of cells in the mask.

Ink bounds and masks support collision, separation, occlusion, and visible-fraction
checks. Ink count may describe rendering density or measured cost, but it is never the
object's physical-size measure; nominal camera-facing area supplies physical scale.

- Objects are camera-facing billboards with nominal face shapes/areas and a depth
  coordinate, not viewable 3D solids or volumes. Physical scale ordering compares
  nominal face area; final ink is a rendering/readability measurement, not physical
  size.
- Planets use circles. Ports, Stardock, and starbases use calibrated ellipse/rectangle
  faces and remain children of their planet whenever one is present. Their nominal face
  area and allowed orbital placement derive from that planet.
- A station may occupy any valid orbit, including the near or far side; it is not
  limited to a planet limb.
- Ships use camera-facing rectangles with nominal face area below the station class and
  receive wider placement regions/depth ranges than stations. Their long authored hulls
  may contain more painted cells than a sparse station without violating physical scale.
- The composer selects a station's natural authored rung with no padded composition
  footprint. Blank alignment space in a docked header is a separate UI container and
  never contributes to face area, framing, collision, occlusion, or occupancy. This does
  not remove the shared `pad_to` utility from renderers that genuinely require an exact
  container.
- Existing 2D sprites remain the final art. Face-shape geometry controls placement, camera
  fitting, apparent bounds, occlusion, and depth order only.
- Partial occlusion is allowed when the depth relationship makes it physically
  meaningful. Each object class has a configurable minimum visible fraction; an
  object below it is repositioned or rejected rather than left unreadable.
- Asteroid belts remain permeable fields: they receive a projection shape for framing
  and scale, but reserve no opaque occupancy region and preserve paint-through by
  stations and traffic.
- Fighters and mines remain deterministic one-cell presence glyphs outside the 2.5D
  solver. They scatter into free projected cells after sprite paint and neither affect
  camera fitting nor participate in shape occlusion/minimum-visible-fraction rules. The
  scatter search is count-bounded like every other search (§6.2 rule 4) and records how
  many glyphs it placed; when free cells run out, the unplaced marks fall to the
  sidebar/object list by name like any other omitted object, and never to scene text or a
  count badge.
- The Entity receives a foreground visual shape, has the highest anchor and retention
  priority, and is never reduced to a text hint in the art scene.

Every shape carries an estimated visible-ink shape/yield, and the catalogue that supplies
it must be keyed the way the vendored library actually varies.

- **The natural box is exact, but only per `(kind, subtype, view axis, tier,
  archetype)`.** `_natural_box` resolves it through `tier.composed_length(axis,
  archetype_id)` and `section.repeat_for(archetype_id)`, and the axis follows the
  requested facing through `_resolve_view` (a vertical view is a different ladder, not a
  rotation). Subtype plus rung index under-specifies the key: a facing flip or a
  different species archetype silently selects different geometry.
- **The ink mask inside that box is not a function of that key.** The renderer seeds from
  `f"{seed}|{kind}|{role}"` (plus archetype) and draws a weighted variant per section, so
  which cells carry glyphs varies with the render seed and the variant pool even though
  every variant in a section shares one rectangular size.

Laddered art therefore carries an **exact natural box plus a conservative ink envelope**
measured over the variant pool and the seeds the game can produce — not a single exact
ink figure. Each constraint declares which side of the envelope it uses: minimum ink for
visible-fraction, legibility, and minimum-extent floors; maximum ink bounds for
separation, collision, and occlusion. The envelope makes **no monotonicity assumption**
about ink versus rung index or requested box. Procedural art uses a calibrated continuous
per-kind relationship between requested box and visible ink, on the same
min-for-visibility / max-for-clearance rule. Framing, separation, occlusion, and
visible-fraction estimates use these values rather than an opaque request rectangle.

The exact face shape and ink yield for each discovery kind, asteroid fields, and the
Entity beyond the approved planet/station/ship shapes is a calibration-gate decision
(WP-SC05),
not an implicit implementation choice.

### 2.6 Labels and accessibility

Add one local, global scene-label preference:

```python
scene_labels: Literal["labeled", "hidden", "hover_hint"]
```

`labeled` attaches names to accepted sprites; `hidden` leaves the art unannotated;
`hover_hint` reveals the same hint through both mouse hover and keyboard focus. This
belongs to `UISettings`, outside game config, universe state, replay, and the wire.
Every hotspot retains a keyboard/list equivalent. Label footprints participate in fit
only in `labeled` mode; labels may not force a text-only scene fallback. `scene_labels`
is independent of the existing `art_detail` and `reduced_motion` settings: none silently
overrides another, and their combined matrix is covered by settings and gallery tests.

## 3. Intermediate scene model

The replacement separates classification, solving, and raster painting. Names below
describe responsibilities; exact Python names are fixed in the implementation WP.

```text
SectorDTO + scene config + UI settings + geometry catalogue
          + viewport + optional previous ScenePlan
                    │
                    ▼
             Physical classification
 (kind, parent, face class, shape, priority, allowed region/depth)
                    │
                    ▼
         Deterministic local 2.5D arrangement
        (face positions, depths, camera anchor)
                    │
                    ▼
          Projection strategy + constraint solver
   (frustum, cell aspect, projected bounds, depth, occlusion)
                    │
                    ▼
               Art resolution
  (ladder rung or continuous box, actual ink, visible fraction)
                    │
          ┌───────────┴───────────┐
          ▼                       ▼
     accepted render plan       rejected-object trace
          │                       └─ sidebar only
          ▼
       depth-ordered 2D sprite paint + hotspots/labels
```

The model should expose immutable records equivalent to:

- `ArtGeometryCatalog`: injected immutable plain-data records for ladder rungs, natural
  boxes, ink envelopes, and calibrated continuous-kind ink yields, keyed as §2.5
  requires; construction and asset loading remain outside `edge/scene/`. Its laddered
  content is **generated, checked in, and guarded**: a `scripts/` generator renders every
  `(kind, subtype, view axis, tier, archetype)` combination once, measures the envelope,
  and writes a versioned data file, and a `--check` test asserts that file still matches
  the vendored assets. An upstream sprite sync that retunes a variant pool then fails CI
  instead of silently shifting scene geometry, so this file joins the silent-contract
  list in `SPRITE_ART_SYNC.md`. The catalogue version is part of the plan-cache
  fingerprint (§6.2 rule 6).
- `PhysicalObject`: tagged stable presentation key, kind, parent key, camera-facing
  shape, nominal face area, estimated ink shape, art mode, scale class, placement
  region/depth range, flexibility, opaque retention key, and interaction destination.
- `WorldArrangement`: viewport-independent identities, parents, allowed regions, and
  initial deterministic positions; a solve records any viewport-driven flexible move.
- `Camera`: fixed FOV, position, aim/target, near plane, cell-aspect correction.
- `ProjectionStrategy`: the typed interface used to compare fixed-FOV perspective and
  depth-layered anchor projection in calibration; only the approved implementation
  enters the production solver.
- `Projection`: screen bounds, depth, optional ladder rung or continuous box class,
  estimated and actual ink bounds, visible fraction, label bounds, accepted/rejected
  state.
- `Decision`: rule id, inputs, outcome and human-readable reason.
- `ScenePlan`: viewport/mode, strategy, camera, ordered projections, rejected keys,
  quantised output fingerprint, structural counters, and — behind the dev/gallery switch
  — the full trace. A previous plan may be supplied only as a hysteresis preference for a
  resize solve.

Trace construction is gated so a 50-ship scene does not build a large prose object on
every resize frame: **structural counters are always recorded** (camera candidates,
reposition candidates, solve passes, occlusion comparisons, validation corrections, cost
spent, and per-object accept/reject rule ids), so §4's invariants and the §6 benchmarks
are assertable in CI, while the human-readable `Decision` reasons are built only under
the dev/gallery switch. No invariant test may depend on prose.

No method in this model paints Rich cells. Rendering consumes an already-resolved
`ScenePlan`; it does not reopen placement decisions.

The model, strategies, and solver live in a new `edge/scene/` package added explicitly
to the strict mypy target list. That package consumes fog-safe `edge.core` DTO/config
and the injected `ArtGeometryCatalog`, but never imports `edge.art.sprites`, Rich,
Textual, I/O, async, or a TUI module. The art/TUI seam builds the catalogue from the
vendored asset metadata plus validated scene config, and retains starfield/cell
painting, labels, focus, and hotspots. No unchecked art-library type crosses into the
strict package.

## 4. Solver invariants

The implementation and its tests must enforce these rules independently of tuned
defaults:

1. Identical DTO, settings, config, geometry catalogue, viewport, and optional previous
   plan produce identical quantised outputs: integer cell bounds, art choice, ordering,
   admission, and rejection — **on every platform**. This is a design constraint on the
   arithmetic, not a hope: camera and projection values resolve to integer cell units
   before any comparison, and candidate scoring is integer or exact rational, so no
   accepted/rejected decision or candidate ordering can turn on a float comparison near a
   quantisation boundary. Floats may appear in reported diagnostics; nothing the solver
   decides may depend on one. Diagnostic float values are reproducible within one process
   but are not asserted byte-identical across platforms. Candidate *ordering*, not merely
   final output, is covered by the determinism tests.
2. Every projected object came through the fog-safe DTO; no hidden object enters the
   physical model or trace.
3. Parent relationships are respected: an orbital station's position and nominal size
   derive from its planet when present.
4. Display scale classes preserve their ordering by nominal camera-facing area at equal
   depth. Rendered ink is not a physical-size metric: sparse vertical infrastructure may
   contain fewer painted cells than a long narrow ship. Projection and art resolution
   must not silently change an object's nominal class.
5. Higher retention priority cannot be rejected while a lower-priority object of the
   same admissibility class remains solely because it was considered earlier.
6. More-hostile ships are retained ahead of less-hostile ships; at equal hostility,
   greater combat threat wins, then stable identity. Neutral ships precede wrecks,
   which precede friendly ships.
7. Every accepted laddered sprite clears a complete authored rung selected from the
   geometry catalogue; the shipped `fit_box` smallest-tier clamp is never the source of
   an accepted box, and an object with no clearing rung is rejected rather than cropped.
   Every accepted continuous sprite clears its configured minimum ink extent. All
   accepted art clears edge margin, separation, declared occlusion, minimum projected
   size, and minimum actual-ink visible fraction—not merely face/request-box constraints.
   Constraint checks read the ink envelope on the declared side: minimum ink for
   visibility floors, maximum ink bounds for clearance.
8. Occlusion follows camera depth. Equal-depth ambiguity is resolved deterministically
   and reported, never by container iteration order.
9. Rejected objects appear by name and omitted state in the complete sidebar/object-list
   projection and nowhere as scene text or an edge/count marker.
10. Every accepted hotspot has the same keyboard/list route, including hover-hint focus.
11. Resizing recomputes from the scene viewport without mutating game state or consuming
    game RNG. When given a previous plan, the deterministic soft objective minimizes
    camera, placement, admission, and art-size change after all hard rules are satisfied.
12. Docked station headers reuse the natural `(width, height)` selected by the sector
    render from an immutable mapping keyed by `(sector_id, station_kind, object_id)`.
    Port and starbase id namespaces may overlap, so all three key parts are required;
    stale or mismatched entries are rejected rather than inferred from body heights.
13. Ship depth variation is a measured soft objective expressed in **projected height**,
    not rung index: when the available depth and authored ladders permit it, prefer
    arrangements whose admitted ships do not all project to the same apparent size. Ships
    of different subtypes at equal depth must project to consistent apparent size even
    though their ladders differ. Equal projected heights remain valid and are never
    forced apart by an artificial tier step at unchanged distance.
14. Admission cannot exceed the configured estimated render-cost budget or the high
    emergency ship ceiling. Cost is spent in retention order and reported per object/art
    choice. Laddered costs are per-rung measurements with no assumed monotonicity;
    continuous-kind cost envelopes are conservative and nondecreasing with box size. The
    budget binds the estimate side within its approved tolerance: the bounded actual-ink
    validation correction of §6.2 rule 2 may shrink an object's box or reject it, and may
    never move it to a higher cost class. Before rejecting any retained object for cost,
    the solver steps the continuous anchor's box class down its configured ladder, but
    never below that class's minimum ink extent and never to the point of rejecting the
    anchor; a scene still over budget at that floor is reported, not degraded further.
15. The Entity, when present, is the foreground anchor and highest retained visual
    object. Fighters/mines remain post-projection glyphs, and belt permeability is
    preserved.
16. A direct-open docked screen with no valid preceding sector reference retains the
    existing per-kind configured maximum-bounds fallback, but selects and publishes the
    natural authored station rung rather than treating blank padding as geometry.
17. Failure to fit any object never permits crop, partial art, or scene text. The art
    scene may contain only its starfield while every object remains named in the
    sidebar/object list; compact mode continues to use its existing inline object list.
18. If any visible object can clear its minimums under a camera inside the bounded
    candidate search, the solver must admit at least one object; starfield-only output
    is valid only when no visible object can fit. "Can fit" means clearing a complete
    authored rung (laddered) or the configured minimum ink extent (continuous) — the same
    bar as invariant 7, so 7 and 18 cannot be played against each other in a viewport
    where only a cropped rung would have fit.
19. Presence glyphs are bounded and accounted: the post-paint scatter is count-bounded,
    reports how many marks it placed, and sends any unplaced mark to the sidebar/object
    list by name rather than to scene text or a count badge.
20. Structural counters are recorded on every solve, including in production; the
    human-readable decision prose is built only under the dev/gallery switch. No
    invariant test, benchmark assertion, or cache key depends on the prose.

## 5. Calibration gate: no unapproved numerical defaults

The interview approved the rules, but not the numbers. Before production replacement,
WP-SC04/SC05 must produce review sheets and gallery output for explicit approval of:

- the default projection strategy and, if perspective is selected, its fixed FOV;
- planet/highest-anchor target-height fraction;
- scene-viewport structural-mode thresholds;
- nominal face-area classes and exaggeration ranges;
- orbital radii and station placement region/depth range;
- ship and wreck placement regions/depth ranges;
- kind-specific discovery, asteroid-field, and Entity face shapes;
- per-key ink envelopes (laddered `(kind, subtype, view axis, tier, archetype)` natural
  boxes with measured min/max ink, and continuous per-kind yields), plus which side of
  the envelope each constraint reads;
- the continuous anchor box-class ladder and its per-class minimum ink extent;
- edge/separation margins;
- minimum ladder rung or continuous ink extent, and visible fraction per class;
- bounded camera-search, reposition-search, re-anchor, and glyph-scatter ranges;
- the encounter-disposition-to-retention mapping around the neutral baseline;
- laddered per-rung and continuous per-box-class render costs, total painted-sprite cost
  budget, its estimate-side tolerance, and high emergency ship ceiling;
- the strength of the soft ship-depth/rung-variation objective;
- previous-plan hysteresis weights and any small-resize stability expectation;
- the default global label mode;
- absolute total-time ceilings and solver/candidate budgets from §6.

The prototype may use temporary values to render alternatives, but none becomes a
shipped default without review. Approved values then live under `config/default.yaml →
scene:` with schema validation and explanatory comments, except `scene_labels`, which
is a local `UISettings` preference.

## 6. Performance contract

The physical model is allowed to improve composition at a modest fixed CPU cost; it is
not allowed to multiply procedural sprite-rendering cost by the number of camera or
placement candidates. Visual approval alone is insufficient for cutover.

### 6.1 Current baseline

An informal local measurement on 2026-08-31, using the shipped composer and five runs
per representative scene, found these cached-compose medians across 67×30 through
150×52 scene canvases:

| composition | cached median range |
|---|---:|
| empty + ships | 10–26 ms |
| planet + ships | 20–64 ms |
| planet + port + wreck + traffic | 23–66 ms |
| nebula + port + ships | 23–104 ms |

The first uncached observation in those short runs was approximately 140–580 ms for
ordinary scenes and 1–4 seconds for large nebula scenes. These are diagnostic numbers,
not portable acceptance thresholds: they include local hardware, Python startup/cache
state, procedural art, Rich cell conversion, and starfield work. They establish two
facts the implementation must preserve in its measurements:

1. warm revisit cost and cold new-sector/new-size cost are different workloads;
2. procedural sprite generation, especially a large phenomenon, can dominate the
   physical-model arithmetic.

The existing test comment records the real review matrix at roughly 30 seconds for 64
compositions, while the HTML gallery renders each cell twice and approaches one minute.
WP-SC04 must replace the informal figures above with a reproducible baseline report
before comparing a prototype.

### 6.2 Structural cost rules

These are implementation invariants, not tuning choices:

1. **Candidate solving is catalogue-only.** Camera adjustment, projection, placement-
   region sampling, separation, and preliminary occlusion use numerical shape geometry
   corrected by injected static ink bounds/yields. They must not generate Rich sprites
   or flatten them into cell grids.
2. **Sprite resolution follows the solve.** The renderer generates art only for the
   provisionally accepted final projections. Actual ink masks may trigger one bounded
   validation correction, but never restart an unbounded camera search, and that
   correction may only shrink a box or reject an object — never raise its cost class
   (§4.14).
3. **Render once per selected box.** Within one composition, an object may incur at
   most one uncached render for each distinct final sprite box considered by that
   bounded validation step. A composition-local cache is keyed by entity, subtype,
   stable seed, box, facing, archetype, and treatment inputs.
4. **Every search is count-bounded.** Camera candidates, per-object reposition
   candidates, validation corrections, and total solve passes have explicit configured
   or code-level maxima. The `ScenePlan` trace reports the counts actually consumed.
   Camera candidates are quantised at cell/art-rung transition boundaries so the search
   does not spend its budget on states with identical quantised output.
5. **Object-count scaling is visible.** Projection is linear in inventory size.
   Pairwise occlusion may be quadratic, but it runs only over provisionally admitted
   objects and reports comparison count; no hidden nested sprite rendering is allowed.
6. **Plan reuse is explicit.** An immutable plan may be cached only by a complete
   presentation fingerprint: fog-safe sector DTO content, scene config, relevant UI
   settings, geometry-catalogue version, exact drawable viewport, and optional previous-
   plan quantised fingerprint. A stale plan from another sector, state, catalogue,
   setting, size, or resize history must miss rather than render incorrectly. The cache
   belongs to the `SectorScene` widget and is a small bounded LRU — the current sector
   across a handful of recent viewports — so it dies with the screen, holds no cross-
   sector history, and has no module-level global to invalidate. Its capacity is
   configured and its hit/miss counts are reported.
7. **Resize work is coalesced.** The Textual integration must not solve every transient
   intermediate size in a resize burst when only the latest viewport can be displayed.
8. **Diagnostics are not a per-frame cost.** Structural counters are always recorded;
   the decision prose is built only under the dev/gallery switch (§4.20). The benchmark
   reports both configurations so the gating is shown to matter — or shown not to.

CI tests should assert structural counts and bounds, not fragile wall-clock thresholds.
Wall-clock comparisons run in the dedicated benchmark command on a controlled machine
and are attached to the WP review.

### 6.3 Benchmark matrix and instrumentation

Add a dependency-free `edge/devtool/scene_benchmark.py` command using
`time.perf_counter`; do not add a benchmarking package. It runs the current and
replacement composers against identical DTOs, settings, config, and exact scene
viewports. It reports at least median, p95, and maximum for:

- fog-safe sector-DTO inventory distributions over enough seeds/player sensor states to
  report median, p95, p99, and maximum ships/discoveries/stations, plus runtime wreck
  and multiplayer stress;
- cold first arrival with unique sector/object seeds;
- warm repeat arrival at the same viewport;
- resize to a new viewport and resize back to a cached viewport;
- empty, planet-only, ordinary station, normal traffic, crowded planet/station/wreck,
  belt, nebula, black-hole, and wormhole compositions;
- hostile/neutral/friendly admission competition;
- 1, 5, 20, and 50-ship synthetic inventories, because the replacement removes the
  current three-sprite cap;
- all approved scene-viewport structural modes and label modes.

Each sample records:

- inventory, admitted, rejected, and painted object counts;
- total, model-build, solve, sprite-generation, cell-conversion, and paint time;
- camera candidates, reposition candidates, re-anchor and anchor box-class step-down
  passes, total solve passes, occlusion comparisons, glyph-scatter placements, and
  validation corrections;
- estimated versus actual render cost against the budget and its tolerance;
- the same scene with decision prose gated off and on, so §6.2 rule 8's gating is shown
  to be worth its complexity — or shown not to be;
- sprite-cache hits/misses and distinct rendered boxes;
- viewport, selected mode, camera values, and whether the `ScenePlan` cache hit.
- distinct quantised scene count produced by the camera candidates.

Laddered render cost is a measured lookup on the full catalogue key — `(kind, subtype,
view axis, tier, archetype)` — and assumes no monotonic ordering by rung, box, or ink.
Continuous-kind cost envelopes must conservatively avoid decreasing as box size grows.
Synthetic 20/50-ship cases remain future multiplayer and
algorithmic stress tests; they are not presented as the current generated-world
distribution. Each structural mode reports its actual maximum admitted ship count and
whether the emergency ceiling, physical fit, or render budget bound it.

The benchmark output is machine-readable for before/after comparison and has a concise
human summary. The gallery may display timings for diagnosis, but gallery HTML generation
is measured separately from runtime composition because it deliberately renders and
captures more than the game path.

### 6.4 Approval and cutover gate

WP-SC04/SC05 propose, and the review explicitly approves:

- an **absolute** latency budget for warm, cold, resize, and complex-phenomenon p95;
- a solver-only latency and candidate-count budget against its frozen baseline.

No numerical budget is selected in this plan without that approval. Total time has an
absolute ceiling because unchanged procedural generation and Rich conversion make a
relative total-time comparison noisy; solver time and structural counts are assessed
separately. WP-SC06 and WP-SC07 must publish benchmark deltas against the frozen
baseline. WP-SC11 cannot cut over if any approved budget fails, if candidate/sprite-
render counts exceed their hard bounds, or if a visual improvement depends on repeated
speculative sprite rendering.

**If neither strategy can meet the budgets, the answer is no-go, not a slow cutover.**
The shipped composer remains authoritative; `edge/scene/` stays in the tree as unwired,
strict-typed, tested code with the measured no-go recorded in this plan, and the
WP-SC09 dev switch simply keeps defaulting to the legacy path. Nothing half-migrated
ships: WP-SC10's consumer migration does not land under a no-go, and the WP-SC01 DTO
projection — which is independently useful and already wire-versioned — stays. Reopening
requires new evidence or a fresh interview on the visual-quality-versus-cost trade, not a
quieter reading of the same numbers.

## 7. Work packages

Each package is a small, independently reviewable commit. No package may hand-edit the
vendored sprite library or assets. Before cutover, implementation notes remain in this
plan under a clearly marked forthcoming section; the shipped-behavior sections of
`SECTOR_SCENE_COMPOSITION.md` remain unchanged while both composers coexist. WP-SC11
merges the approved replacement rules into that authoritative note when they ship.
Every WP that changes `scene:` values or requested art boxes runs
`test_every_subtype_renders_a_whole_tier_at_its_scene_box`, not only the cutover WP.
Each package below states *what must be true*; §9 states *what to build* — shared
definitions and units (§9.1–9.2), the landed signatures (§9.3), the catalogue generator
(§9.4), projection (§9.5), the solver (§9.6), and art resolution (§9.7). Where §9 and §4
disagree, §4 wins.

### WP-SC01 — Fog-safe priority and station-reference projection

Depends on: none.

Implementation:

- Add a coarse scene retention class, opaque per-scene within-class hostility ordinal,
  and combat-threat tie rank to `SectorShipDTO`; never project the raw adjusted
  disposition or its private inputs. The ordinal is computed as a pure function of sector
  state and stable identity, never from a container position, so two DTOs built from the
  same state carry the same ordinal (§2.3).
- Derive the ordinal from the same final quantity the greeting-versus-violence logic
  orders, then use combat threat and a tagged stable public presentation key. Current
  alien keys use `contact_id`; other-player keys use `player_id`; the tag prevents
  cross-kind collisions. Do not invent a vessel id where the authoritative model has
  no distinct vessel entity.
- Define fog-safe other-player and unidentified values without leaking private state.
  Cross-species equal-disposition ties are expected; DTO/container order is irrelevant.
  Accept that a relative within-sector hostility ordering reaches the client—it is
  already behaviorally inferable—while proving raw values, gaps, grudges, and standing
  components remain undisclosed.
- Add internal `sector_id` to `StarbaseDTO` so every docked station can validate the
  published object-id reference instead of preserving the current `expect_sector` hole.
  `PortDTO` already carries internal `sector_id`; no redundant port field is added.
  Close the hole at the callers in the same commit, or it is only closed on paper: pass
  the new id at the two `expect_sector` sites in `edge/tui/screens/stardock.py` and
  correct the standing comment in `edge/tui/screens/base.py` ("No `expect_sector` guard
  here: StarbaseDTO carries only the display id"), which stops being true here.
- Bump the wire version (43 at planning time) and update explicit DTO codec and
  compatibility tests.

Verification:

- Rebuilding the DTO from unchanged sector state reproduces the ordinal exactly, and
  permuting the source containers does not perturb it.
- Projection tests cover attitude offsets, grudges, alliance hostility, equal and
  cross-species ties, other-player vessels, unidentified/fogged cases, raw-value
  non-disclosure, station sector identity, and local/remote round trips.
- Server-side tests prove the ordinal orders visible ships exactly as encounter
  hostility does without allowing the client to recover the underlying float.

Docs: add a forthcoming projection/fog section here and keep the existing in-progress
banner in `SECTOR_SCENE_COMPOSITION.md`; do not rewrite shipped behavior.

Commit: `ui: WP-SC01 project scene priorities`

### WP-SC02 — Pure geometry catalogue and immutable scene model

Depends on: WP-SC01.

Implementation:

- Create `edge/scene/`; add it to `pyproject.toml`'s strict mypy `files` list; update
  `DESIGN.md` §3 and `AGENTS.md`'s strict-layer/dependency prose in this commit. Ruff
  already covers it through the normal `edge/` target.
- Define the injected `ArtGeometryCatalog` protocol/data records, keyed by `(kind,
  subtype, view axis, tier, archetype)` for laddered art and by kind for continuous art.
  The art/TUI seam may read assets and Rich-backed sprite objects to build it;
  `edge/scene/` sees only plain immutable ladder boxes, ink envelopes, and
  continuous-kind ink-yield records.
- Add the `scripts/` catalogue generator and its `--check` test, write the versioned
  generated data file, and record it in `docs/SPRITE_ART_SYNC.md` as a contract that
  breaks silently on an unguarded upstream sync.
- Add typed immutable vectors, face shapes/areas, placement regions/depth ranges,
  physical objects, world
  arrangements, cameras, projections, decisions, and scene plans, with every numerical
  tuning value injected and no shipped defaults committed. `SceneArtConfig` forbids
  unknown keys, so the intermediate WPs keep the new `scene:` keys out of
  `config/default.yaml` entirely rather than committing placeholder numbers that read as
  approved.
- Classify Entity, the one generated open-space discovery (including a generated
  sensor-gated wreck), planets/belts, station kinds, runtime wrecks, ships, and post-
  projection glyphs through one closed registry. Build parents before deterministic
  face positions/depths.
- Encode nominal face-area scale separately from retention, and treat glyphs as free-
  cell consumers rather than retained solver objects.

Verification:

- Unit tests pin relationships, tagged identities, art modes, scale, retention,
  permeability, ink estimates, and glyph classification.
- The generated catalogue matches a fresh render of the vendored assets on both axes and
  on measured ink; facing and archetype are shown to select different records.
- Permuting DTO order does not perturb identity, base arrangement, or priority.
- Import tests prove `edge/scene/` pulls no `edge.art.sprites`, Rich, Textual, file I/O,
  async, TUI module, unchecked art type, game-state mutation, or game RNG.
- `mypy --strict` covers the package from its first commit.

Docs: replace conceptual names with landed interfaces and update `DESIGN.md` §3.

Commit: `ui: WP-SC02 add pure scene model`

### WP-SC03 — Projection strategies with injected parameters

Depends on: WP-SC02.

Implementation:

- Implement fixed-FOV perspective and depth-layered anchor projection behind one typed
  calibration interface, with terminal-cell aspect correction and no designated winner.
- Select hybrid structural mode from the exact drawable scene viewport.
- Frame Entity first, otherwise the highest nominal face-area class, at that class's
  target fraction and against estimated visible ink rather than request-box extent.
- Project depth, estimated ink bounds, preliminary occlusion, ladder candidates, and
  continuous box candidates without generating art.
- Accept an optional previous plan and expose deterministic hysteresis terms, all
  weights injected and unset until calibration.

Verification:

- Calibration contract tests run identical inventories through both strategies.
- Quantised outputs are deterministic and no accepted/rejected decision or candidate
  ordering turns on a float comparison; candidate ordering itself is asserted, not only
  the final plan. Reported diagnostic floats are in-process reproducible.
- Preliminary equal-depth ordering uses catalogue ink metadata and never compares
  unequal depths. No projection candidate generates sprite art.

Docs: add a forthcoming strategy/viewport section here.

Commit: `ui: WP-SC03 add scene projections`

### WP-SC04 — Baseline, inventory study, and projection approval

Depends on: WP-SC03.

Implementation:

- Drive the real typed `edge/scene/` model and both experimental strategies from the dev
  gallery; do not build a throwaway intermediate model or second debugger.
- Add `edge/devtool/scene_benchmark.py`, freeze a reproducible shipped-composer baseline,
  and separate total, solver, sprite, conversion, and gallery-generation workloads. The
  frozen baseline uses the same scene canvases as §6.1 (67×30 through 150×52) so the
  informal figures and the reproducible ones are comparable at all.
- Measure fog-safe DTO inventories over many seeds and sensor states; distinguish
  generated wreck visibility from runtime wreck and multiplayer stress inventories.
- Report how many distinct quantised scenes each camera search produces and eliminate
  candidates that cannot cross a cell or art-rung boundary.
- Compare and approve one production strategy, its framing model, fixed FOV if relevant,
  class-specific target fractions, and structural viewport modes. Remove the losing
  implementation after recording the evidence; keep the typed interface.
- If neither strategy can meet the budgets, record the no-go per §6.4 and stop here
  rather than proceeding to WP-SC05 on the expectation that calibration will recover it.

Verification:

- Every comparison uses production model/strategy code and exports its full trace.
- The benchmark emits machine-readable samples and a human comparison; repeated runs
  distinguish cache variance from solver cost.

Docs: record the approved strategy/framing result in the forthcoming section.

Commit: `ui: WP-SC04 select scene projection`

### WP-SC05 — Face, ink, constraint, and cost calibration

Depends on: WP-SC04 approval.

Implementation:

- Display face shapes/areas, parent links, camera values, estimated/actual ink, projected
  rectangles, depth, visible fraction, natural art choice, costs, hysteresis, and every
  decision/rejection reason using only the selected strategy.
- Cover Entity + planet, each mutually exclusive generated discovery including a
  sensor-gated wreck, planet/phenomenon + runtime wrecks, permeable belt, arbitrary
  station orbit, hostility/threat ordering, natural unpadded stations, cost pressure,
  failed-anchor sidebar handling, and resize stability.
- Approve all remaining §5 values, the per-key ink/cost envelopes and which side each
  constraint reads, continuous ink/cost envelopes, the anchor box-class ladder and its
  minimum ink extents, total render budget and its estimate-side tolerance, high
  emergency ship ceiling, depth preference, hysteresis, and absolute total/solver/
  candidate budgets.
- Assume no ladder-rung monotonicity. Require only continuous-kind cost envelopes to be
  conservative and nondecreasing as requested box size grows.
- Include a cost-pressure cell that exercises the anchor box-class step-down and shows
  the resulting framing is acceptable, not merely cheaper.

Verification:

- Every matrix cell exports the complete production-model trace with reviewer notes.
- Each structural mode reports maximum admitted ships and which physical, cost, or
  emergency-ceiling constraint binds.

Docs: record the approved tuning table and budgets in the forthcoming section.

Commit: `ui: WP-SC05 calibrate scene constraints`

### WP-SC06 — Constraint solver, admission, and hysteresis

Depends on: WP-SC05 approval.

Implementation:

- Implement bounded camera adjustment → flexible-object reposition → anchor box-class
  step-down → retention/cost rejection using catalogue face-shape and estimated-ink
  geometry only. Re-anchor and step-down passes are counted against the same bounded pass
  budget as every other search and cannot cycle.
- Enforce edges, actual-ink estimates, separation, declared occlusion, minimum projected
  size/visible fraction, equal-depth nominal face-area ordering, permeable belts, the
  calibrated render-cost budget, and the high emergency ship ceiling.
- After hard rules, minimize change from an optional previous plan. Treat ship rung/depth
  variation as a separate soft objective; equal rungs remain valid.
- A failed anchor is rejected to the named sidebar/object-list entry like any other
  object; no crop, partial art, scene label, marker, or bespoke fallback appears.
- Conversely, if any object fits under some bounded candidate, the solver must admit at
  least one; it may not silently return only stars while a valid composition exists.
  "Fits" means a complete authored rung or the configured minimum continuous ink extent
  (§4.18), never a cropped rung.
- Report every candidate, move, comparison, hysteresis delta, cost, and rejection.

Verification:

- Property tests sweep viewports, the selected strategy, inventories, costs, opaque hostility
  ranks, threat, occlusion, previous plans, and ±1-cell resize paths.
- Every solve terminates within hard bounds; higher retention never loses solely to
  consideration order; hysteresis never defeats a hard rule.
- Structural and solver-only benchmarks meet the approved budgets and never render art.

Docs: add forthcoming solver/admission/sidebar rules here.

Commit: `ui: WP-SC06 solve physical scenes`

### WP-SC07 — Art resolution and depth paint

Depends on: WP-SC06.

Implementation:

- Resolve laddered ships/stations to complete existing rungs **through the catalogue**,
  never through `fit_box`'s smallest-tier clamp, and continuous kinds to procedural
  boxes, then crop all outputs to actual ink. An object with no clearing rung is rejected
  by the solver before this step; art resolution never invents a cropped fallback.
- Subsume the shipped `rung_below` behavior into catalogue rung selection driven by the
  approved projected-height depth objective (§4.13), not by stepping rung indices; remove
  the old call only after no legacy composer uses it.
- Run one bounded actual-ink validation/correction without reopening unbounded search;
  verify separation, declared occlusion, visibility, and preservation of nominal class.
- Paint phenomena/background, ordinary depth layers, and foreground Entity according to
  projected depth; preserve belt paint-through and scatter force glyphs afterward.
- Add the composition-local render cache, the widget-owned bounded `ScenePlan` LRU
  (§6.2 rule 6), and render-once-per-final-box counters.
- Publish an immutable mapping from `(sector_id, station_kind, object_id)` to the
  selected natural `(width, height)` for every rendered port/starbase. Reject exact-key
  mismatches; use WP-SC01's `StarbaseDTO.sector_id`; retain the configured-maximum
  direct-open fallback but resolve it to a natural rung without composition padding.

Verification:

- Laddered/continuous, actual-ink ordering/separation/occlusion, belt, Entity, station
  reference, direct-open fallback, cache-count, and cold/warm/resize benchmarks pass.
- No rejected object becomes scene text or a scene overflow marker.

Docs: add forthcoming paint/station/glyph rules here.

Commit: `ui: WP-SC07 render projected scenes`

### WP-SC08 — Labels, hotspots, sidebar overflow, and resize integration

Depends on: WP-SC07.

Implementation:

- Add independent global `scene_labels` setting and Options control for `labeled`,
  `hidden`, and `hover_hint`; do not couple it to `art_detail` or `reduced_motion`.
- Implement hover hints for mouse hover and keyboard focus.
- Build labels/hotspots only from accepted projections; overlapping hits route to the
  visible topmost object.
- Remove `_paint_text_rows`. Ensure every rejected object's name and omitted state
  remains explicit in `StatusSidebar`, `SectorObjectList`, and `StatusDrawerScreen` with
  identical routing. Add no scene count or edge indicator.
- Pass the previous plan into resize solves, coalesce resize bursts, and discard the
  disposable plan on sector/state/settings/catalogue changes.

Verification:

- Settings independence/compatibility, Textual Pilot hover/focus/sidebar routing,
  no-scene-text, topmost hit testing, cache invalidation, and resize stability pass.

Docs: add forthcoming label/overflow behavior here.

Commit: `ui: WP-SC08 integrate physical scene UI`

### WP-SC09 — Dev switch, A/B gallery, and guarded snapshots

Depends on: WP-SC07, WP-SC08.

Implementation:

- Promote WP-SC05's overlays and trace UI; do not implement a second debugger.
- Keep both composers behind a dev/config switch and render A/B cells from identical
  DTO, settings, config, catalogue, previous-plan, and viewport inputs. The switch
  defaults to the legacy composer until WP-SC11.
- Replace implementation-specific rectangle heuristics with `ScenePlan` invariants while
  retaining stable gallery ids, ratings, comments, and before/after export.
- Generate replacement-composer UI snapshots behind the switch for a first, isolated
  human-reviewed diff; do not overwrite the shipped baseline yet.

Verification:

- Full matrix, the selected strategy, both composers, all settings/modes, Entity/belt/wreck/
  crowding cases, performance reports, snapshots, and switch pass.

Docs: record the forthcoming A/B and cutover workflow here.

Commit: `ui: WP-SC09 compare physical scenes`

### WP-SC10 — Consumer migration

Depends on: WP-SC09.

Implementation:

- Migrate or explicitly adapt every known consumer, each with its tests:
  `scene_preview.py`, `scene_gallery.py`, `art_adapter.py`, `dummy.py`, `shots.py`,
  `screens/stardock.py`, `screens/base.py`, `screens/port.py`, and `station_art.py`.
- The docked-header consumers (`station_art.py`, `screens/stardock.py`,
  `screens/base.py`, `screens/port.py`) move onto WP-SC07's published
  `(sector_id, station_kind, object_id)` mapping and WP-SC01's `StarbaseDTO.sector_id`;
  the dev-tool consumers move onto `ScenePlan` invariants.
- Each consumer keeps working under both switch positions until WP-SC11; this package
  adds no behavior of its own.

Verification:

- Consumer tests, docked-header reference/fallback tests, Pilot flows, and both switch
  positions pass.

Docs: none beyond noting the migrated consumer list here.

Commit: `ui: WP-SC10 migrate scene consumers`

### WP-SC11 — Approved cutover and final reconciliation

Depends on: WP-SC01–WP-SC10.

Implementation:

- Cut over and remove the legacy composer only after the complete A/B gallery is
  accepted, performance budgets and automated tests pass, and one hands-on playtest
  session explicitly accepts the replacement. These evidence gates define the rollback
  window; elapsed time does not.
- Remove obsolete constants/config only after no production, preview, gallery, docked-
  header, dummy, shot, or screen consumer remains. Explicitly disposition
  `max_ships_shown` (replaced by cost plus the emergency ceiling) and
  `ship_face_inward_chance` (retain only if the selected strategy still uses its idiom).
- Break loudly on the removed keys rather than deprecating them. `SceneArtConfig` sets
  `extra="forbid"`, so a config file that still names a removed key fails validation
  outright — which is the intended signal at this stage of a single-player, pre-1.0
  project with no external config population to protect. The same commit must sweep every
  YAML in the repo (`config/`, scenarios, and test fixtures) so nothing in-tree is left
  naming a deleted key, and the removal is called out in the commit message.
- Rebaseline final snapshots with human review of every changed image, using WP-SC09's
  isolated replacement snapshots as the comparison rather than one wholesale blind
  update.
- Reconcile `DESIGN.md` §11, `UI_MOCKUPS.md`, `PLAYTEST_NOTES.md`, and
  `SECTOR_SCENE_COMPOSITION.md`; preserve shipped-history rationale where useful.
- Update `config/default.yaml → scene:` and schema comments together. Reconcile
  `SPRITE_ART_SYNC.md` only if requested boxes/ladder assumptions changed; never edit
  vendored files here. Run `graphify update .`.

Verification:

- Create a disposition table for every existing composition test — as a checked-in
  checklist file, not a claim in a commit message, since this is the step most likely to
  be compressed under time pressure: carry unchanged,
  restate against a numbered §4 invariant, replace with an equivalent new assertion, or
  delete with a written implementation-specific reason. Explicitly cover ship depth,
  `rung_below`/rung variation, vertical gaps, belt permeability, sky reserve, whole-art
  survival, and the former no-object-falls-out contract now replaced by named sidebar
  overflow. Budget new assertions where current coverage is absent rather than treating
  the table as sufficient coverage.
- All §4 invariants; art seam, config, wire, settings, Pilot, snapshots, local/remote
  parity, ruff, and strict mypy pass.
- Final controlled benchmarks satisfy approved absolute total-time, solver, candidate,
  render-count, cold/warm/resize, phenomenon, and 50-ship stress budgets.
- No document describes in-scene text overflow or direct paint-as-decision as current.

Commit: `ui: WP-SC11 cut over physical scenes`

## 8. Non-goals

- No authoritative 2.5D/3D coordinates, orbital simulation, physics tick, or navigable
  spatial scene.
- No replacement or hand-edit of the vendored 2D sprites.
- No new rendering dependency or real-time 3D engine.
- No gameplay targeting, combat-position, detection, or movement consequences from the
  presentation model.
- No text-only objects inside the art scene.
- No TUI access to core state outside the service projection boundary.

## 9. Implementation notes (forthcoming)

This section is the construction brief the §7 packages are built against: the
definitions they share, the signatures they land, and the algorithms they implement. §4
remains the acceptance contract — where this section and §4 disagree, §4 wins and this
section is wrong. Every number here is a *shape*, not an approved value: the constants
stay unset until §5's calibration gate, and none of the code below may ship a default.
WP-SC11 folds the surviving rules into `SECTOR_SCENE_COMPOSITION.md` and deletes this
section.

### 9.1 Definitions and units

These are the terms the catalogue generator, the strategies, and the solver must agree
on. Two implementations that define them differently will each pass their own tests.

- **Ink cell.** After a render is flattened by `edge.tui.art_adapter.text_to_cells`, a
  cell is ink iff its character is not `" "`. This is exactly the test
  `_SceneComposer._paint` already applies when it treats spaces as transparent so stars
  show through; the catalogue must not invent a different one (styled blanks are *not*
  ink).
- **Ink bounds / ink count.** The smallest `(width, height)` rectangle enclosing the ink
  cells, and the number of ink cells. Bounds drive geometry; count drives cost and
  density only (§2.5).
- **Scene unit (su).** The integer unit of the world arrangement. All positions, radii,
  depths, and face extents are integers in su; there is no world-space float. The su-to-
  cell relationship is established only by projection, so su has no fixed cell size.
- **Nominal face area.** `width_su * height_su` of the face's axis-aligned bounding box —
  an exact integer, including for circles and ellipses. Scale-class ordering (§4.4)
  compares these integers. Using bounding-box area rather than πab keeps the comparison
  exact and changes no ordering, because a class's shape is fixed per kind.
- **Depth.** Integer `z` in su, increasing away from the camera. Every object has `z > 0`
  relative to the camera plane and `z >= near_plane_su`.
- **Cell aspect.** A terminal cell is taller than it is wide. `cell_aspect` is a
  `Fraction` from config (the shipped composer's `width = 2 x height` disc rule implies
  `2/1`): a face that is square in su projects to `n` columns by `n / cell_aspect` rows.
  It is never hardcoded and never a float.
- **Quantised output.** The integer part of a `ScenePlan` that §4.1 pins: per-object
  integer cell bounds, selected rung or continuous box, admission set, depth order, and
  rejection set. Everything else is diagnostic.
- **Exact arithmetic.** Projection divides, so the model uses `fractions.Fraction` for
  every intermediate that feeds a comparison or a rounding, and `int` everywhere else.
  No solver decision, ordering, or rounding may consume a `float`. Cell rounding is
  `floor` for positions and *round-half-even* for extents, applied to a `Fraction`, so
  the boundary case is defined rather than platform-dependent. `float` appears only in
  diagnostic fields that nothing reads back.
- **Structural mode.** A name selected from the drawable scene viewport by an ordered
  list of `(min_cols, min_rows, mode)` thresholds, first match wins, most permissive
  first. Modes are `wide`, `standard`, `compact`. This is independent of the terminal
  tier and of `art_detail`.

### 9.2 Coordinate and camera conventions

- Right-handed screen-aligned axes: `+x` right, `+y` up, `+z` away from the viewer.
- The camera sits at `(cx, cy, 0)` and looks along `+z`; `aim` shifts the projection
  centre in su without rotating (there is no roll, pitch, or yaw — objects are
  camera-facing billboards, so rotation would have nothing to act on).
- Screen origin is the top-left cell of the drawable scene viewport; `+row` is down, so
  projection negates `y`.
- An object's face is centred on its position and lies in the plane `z = position.z`.
- `near_plane_su` is strictly positive and is a hard constraint: a candidate camera that
  would place any admitted object at `z <= near_plane_su` is rejected before projection,
  never clamped.

### 9.3 Signatures

Field names are binding; module layout inside `edge/scene/` is not. Everything here is
`@dataclass(frozen=True, slots=True)` unless stated, and every collection is a tuple.

```python
# edge/scene/geometry.py
type Su = int

class FaceShape(StrEnum):
    CIRCLE = "circle"; ELLIPSE = "ellipse"; RECT = "rect"; FIELD = "field"

@dataclass(frozen=True, slots=True)
class Face:
    shape: FaceShape
    width_su: Su
    height_su: Su
    @property
    def area_su(self) -> int: ...        # width_su * height_su, exact

@dataclass(frozen=True, slots=True)
class Vec3:
    x: Su; y: Su; z: Su

@dataclass(frozen=True, slots=True)
class Region:
    """The su box an object may be moved within, and the depths it may take."""
    x_min: Su; x_max: Su; y_min: Su; y_max: Su; z_min: Su; z_max: Su

@dataclass(frozen=True, slots=True)
class CellBox:
    """Integer terminal-cell rectangle; the unit of quantised output."""
    col: int; row: int; width: int; height: int
```

```python
# edge/scene/catalog.py
@dataclass(frozen=True, slots=True)
class LadderRung:
    tier_id: str
    index: int                      # 0 = richest rung, ascending down the ladder
    natural: CellBox                # col/row are 0; width/height are the authored box
    ink_min: CellBox                # component-wise minimum ink bounds over the sample
    ink_max: CellBox                # component-wise maximum ink bounds over the sample
    ink_count_min: int
    ink_count_max: int
    render_cost: int                # measured, arbitrary integer units; no monotonicity

@dataclass(frozen=True, slots=True)
class LadderKey:
    kind: Literal["ship", "port"]
    subtype: str
    axis: Literal["horizontal", "vertical", "fixed"]
    archetype_id: str

@dataclass(frozen=True, slots=True)
class ContinuousYield:
    """Calibrated request-box -> visible-ink relationship for one procedural kind."""
    kind: str
    ink_fraction_min: Fraction       # of the request box, conservative low
    ink_fraction_max: Fraction       # conservative high
    min_extent: CellBox              # below this the kind is illegible -> reject
    box_classes: tuple[CellBox, ...] # descending; the anchor step-down ladder (2.3)
    render_cost: tuple[int, ...]     # per box class, nondecreasing with box size

class ArtGeometryCatalog(Protocol):
    version: str
    def rungs(self, key: LadderKey) -> tuple[LadderRung, ...]: ...
    def continuous(self, kind: str) -> ContinuousYield: ...
```

```python
# edge/scene/model.py
class SceneRetention(IntEnum):       # lower value = retained first (2.3)
    ENTITY = 0; ANCHOR = 1; ORBITAL = 2; HOSTILE_SHIP = 3
    NEUTRAL_SHIP = 4; WRECK = 5; FRIENDLY_SHIP = 6

class ArtMode(StrEnum):
    LADDER = "ladder"; CONTINUOUS = "continuous"; GLYPH = "glyph"

@dataclass(frozen=True, slots=True)
class SceneKey:
    """Tagged stable presentation identity; the final deterministic tie-break."""
    tag: Literal["ship", "player", "planet", "port", "starbase", "discovery",
                 "wreck", "entity", "belt", "glyph"]
    ident: int

@dataclass(frozen=True, slots=True)
class PhysicalObject:
    key: SceneKey
    parent: SceneKey | None
    face: Face
    scale_class: str                 # config-named class; ordering is by face.area_su
    art_mode: ArtMode
    ladder_key: LadderKey | None
    continuous_kind: str | None
    retention: SceneRetention
    hostility_ordinal: int           # 0 = most hostile; from the DTO, opaque
    threat_rank: int
    region: Region
    flexible: bool
    occludes: bool                   # False for permeable fields (belts)
    label: str
    destination: str | None          # interaction route; never used by the solver

@dataclass(frozen=True, slots=True)
class Placement:
    key: SceneKey
    position: Vec3

@dataclass(frozen=True, slots=True)
class WorldArrangement:
    objects: tuple[PhysicalObject, ...]
    placements: tuple[Placement, ...]      # deterministic, viewport-independent

@dataclass(frozen=True, slots=True)
class Camera:
    position: Vec3
    aim_x_su: Su
    aim_y_su: Su
    fov_num: int                      # fixed FOV as an exact ratio; strategy-specific
    fov_den: int
    near_plane_su: Su
    cell_aspect: Fraction

@dataclass(frozen=True, slots=True)
class Projection:
    key: SceneKey
    bounds: CellBox                   # request/container box, integer cells
    depth: Su
    rung: LadderRung | None
    box_class: int | None             # index into ContinuousYield.box_classes
    ink_est: CellBox                  # estimated ink bounds (envelope side per rule)
    ink_actual: CellBox | None        # filled after art resolution (WP-SC07)
    visible_fraction: Fraction
    label_bounds: CellBox | None
    accepted: bool

@dataclass(frozen=True, slots=True)
class Decision:
    rule_id: str                      # stable, e.g. "min_visible_fraction"
    key: SceneKey | None
    outcome: Literal["accept", "move", "reject", "step_down", "reanchor"]
    inputs: tuple[tuple[str, int | str], ...]
    reason: str                       # "" unless the dev/gallery switch is on (4.20)

@dataclass(frozen=True, slots=True)
class SolveCounters:
    camera_candidates: int; reposition_candidates: int; passes: int
    reanchors: int; step_downs: int; occlusion_comparisons: int
    validation_corrections: int; glyphs_placed: int; glyphs_dropped: int
    cost_estimated: int; cost_actual: int

@dataclass(frozen=True, slots=True)
class ScenePlan:
    viewport: CellBox
    mode: str
    strategy: str
    camera: Camera
    projections: tuple[Projection, ...]   # depth-ordered, far to near
    rejected: tuple[SceneKey, ...]
    fingerprint: str                       # hash of the quantised output only
    counters: SolveCounters
    trace: tuple[Decision, ...]
```

```python
# edge/scene/project.py
class ProjectionStrategy(Protocol):
    name: str
    def frame(self, arrangement: WorldArrangement, anchor: SceneKey,
              viewport: CellBox, cfg: SceneTuning) -> Camera: ...
    def candidates(self, camera: Camera, anchor: PhysicalObject,
                   viewport: CellBox, cfg: SceneTuning) -> Iterator[Camera]: ...
    def project(self, camera: Camera, obj: PhysicalObject, at: Vec3,
                viewport: CellBox) -> CellBox: ...

# edge/scene/solve.py
def solve(arrangement: WorldArrangement, viewport: CellBox, cfg: SceneTuning,
          catalog: ArtGeometryCatalog, strategy: ProjectionStrategy,
          previous: ScenePlan | None = None, *, trace_prose: bool = False
          ) -> ScenePlan: ...
```

`SceneTuning` is the injected, frozen bundle of every §5 value. It is constructed at the
TUI seam from validated `scene:` config; `edge/scene/` never reads config files and never
supplies a default for one of its fields.

### 9.4 The geometry catalogue generator (WP-SC02)

`scripts/gen_geometry_catalog.py` writes `edge/art/geometry_catalog.json`. It renders;
the runtime never does (§6.2 rule 1), and `edge/scene/` never reads the file — the TUI
seam loads it and hands over plain records.

**What to enumerate.** The full cross product that the library can actually distinguish:

```text
for kind in ("ship", "port"):
    for subtype in SPRITES.available_subtypes(kind):
        for archetype in sorted(palette archetype ids) + [palettes.fallback_archetype]:
            for view in sprite.views:                  # horizontal / vertical / fixed
                for index, tier in enumerate(view.tiers):
                    natural = _natural_box(view, tier, resolve_archetype(archetype))
                    measure(kind, subtype, view.axis, archetype, index, natural)
```

The archetype axis is required because `Tier.composed_length` and `Section.repeat_for`
take an archetype id; the view axis is required because `_resolve_view` maps a requested
facing onto a whole different ladder rather than rotating one.

**How to measure.** For each enumerated combination, render at the natural box across a
fixed seed sample — `range(cfg_sample_seeds)`, a committed constant in the generator, not
a random draw — and flatten each render with `text_to_cells`:

```text
ink_bounds(render) = bbox of cells whose char != " "
ink_count(render)  = count of those cells
LadderRung.ink_min       = component-wise min over the sample
LadderRung.ink_max       = component-wise max over the sample
LadderRung.ink_count_min = min over the sample
LadderRung.ink_count_max = max over the sample
LadderRung.render_cost   = median wall-clock of an uncached render, normalised to
                           integer units against the cheapest rung in the file
```

The sample exists because variant choice is seeded (`_seed_rng`, `_choose_variant`), so
ink varies within one rung even though the natural box does not. The generator asserts
that invariant explicitly: **the natural box must be identical across the whole sample**,
and a violation is a hard error, not a widened envelope — it would mean the box is
seed-dependent and the whole catalogue key is wrong.

**File shape.** Sorted records, stable key order, two-space JSON, ending in a newline, so
the diff of a regeneration is readable:

```json
{"schema_version": 1,
 "sprite_schema_version": "<copied from the vendored assets>",
 "generated_from": "<sha256 of the asset tree>",
 "rungs": [{"kind": "ship", "subtype": "warship", "axis": "horizontal",
            "archetype_id": "federation", "index": 0, "natural": [46, 7],
            "ink_min": [44, 7], "ink_max": [46, 7],
            "ink_count_min": 180, "ink_count_max": 214, "render_cost": 31}]}
```

`ContinuousYield` records are *not* generated here — they are calibration output
(WP-SC05) and land as `scene:` config, because a procedural kind has no authored ladder
to measure.

**The guard.** `tests/test_geometry_catalog.py` regenerates in a temp dir and compares
byte-for-byte, failing with the exact command to refresh. `docs/SPRITE_ART_SYNC.md` gains
this file to its silent-contract list beside the render seed recipe and the tier ladder.

### 9.5 Projection (WP-SC03)

Both strategies implement the same protocol and are compared in WP-SC04; neither is
privileged here.

**Fixed-FOV perspective.** With the FOV expressed as the exact ratio `fov_num/fov_den`
(su of visible height per su of depth):

```text
def project(camera, obj, at, viewport):
    dz = Fraction(at.z - camera.position.z)          # > 0, guarded by near_plane_su
    if dz <= 0 or at.z < camera.near_plane_su: reject
    scale = Fraction(viewport.height * camera.fov_den, camera.fov_num) / dz
    h_cells = round_half_even(Fraction(obj.face.height_su) * scale)
    w_cells = round_half_even(Fraction(obj.face.width_su) * scale * camera.cell_aspect)
    cx = Fraction(at.x - camera.position.x - camera.aim_x_su) * scale * camera.cell_aspect
    cy = Fraction(at.y - camera.position.y - camera.aim_y_su) * scale
    col = floor(Fraction(viewport.width, 2) + cx - Fraction(w_cells, 2))
    row = floor(Fraction(viewport.height, 2) - cy - Fraction(h_cells, 2))
    return CellBox(col, row, max(1, w_cells), max(1, h_cells))
```

Every value above is a `Fraction` or an `int`; `scale` is never materialised as a float.

**Depth-layered anchor projection.** Identical signature, no divide: depth is quantised
into `cfg.depth_layers` layers, each layer carries an exact `Fraction` scale factor
relative to the anchor's layer, and position offsets are scaled by the same factor. It
trades true perspective for cheaper, flatter arithmetic and is the reason the comparison
in WP-SC04 exists at all.

**Framing.** `frame()` solves the inverse problem — place the camera so the anchor's
projected height equals `target_fraction * viewport.height`, measured against
**estimated ink height**, not the request box:

```text
target_h  = round_half_even(cfg.target_fraction[anchor.scale_class] * viewport.height)
ink_ratio = ladder: rung.ink_min.height / rung.natural.height
            continuous: yield.ink_fraction_min          # conservative: frame the ink
want_h    = ceil(target_h / ink_ratio)
camera.z  = the exact depth at which project() yields want_h, floored to su
```

For a laddered anchor, `want_h` is then snapped to the nearest rung at or below it, and
the camera re-derived from that rung, so the anchor never sits between rungs.

### 9.6 The solver (WP-SC06)

The whole search is integer/rational and touches no art. Ordering is lexicographic over
integer tuples, never a weighted float score — that is what makes §4.1 achievable rather
than aspirational.

**Candidate generation, quantised (§6.2 rule 4).** Do not sweep camera distance and hope
for distinct outputs. Invert the projection so each candidate is *guaranteed* to differ:

```text
def camera_candidates(camera, anchor, viewport, cfg):
    h_hi = round_half_even(cfg.anchor_target_max * viewport.height)
    h_lo = round_half_even(cfg.anchor_target_min * viewport.height)
    heights = [h_hi .. h_lo]                       # every integer cell height
    if anchor.art_mode is LADDER:
        heights = unique rung heights within [h_lo, h_hi]   # rung transitions only
    for h in heights:                               # nearest-to-current first
        z = depth_for_height(anchor, h)             # exact inverse of project()
        for dx in aim_offsets(cfg):                 # whole cells, centre-out, bounded
            yield replace(camera, position=..z.., aim_x_su=dx)
    # bounded by cfg.max_camera_candidates; counters record consumed vs available
```

**The pass loop.**

```text
def solve(arrangement, viewport, cfg, catalog, strategy, previous):
    mode      = mode_for(viewport, cfg)
    admitted  = [o for o in arrangement.objects if o.art_mode is not GLYPH]
    admitted.sort(key=lambda o: (o.retention, o.hostility_ordinal,
                                 -o.threat_rank, o.key))
    best = None
    for _ in range(cfg.max_passes):
        anchor = max(admitted, key=lambda o: (o.face.area_su, o.key))   # 2.3
        for cam in strategy.candidates(strategy.frame(...), anchor, viewport, cfg):
            plan = attempt(cam, admitted, ...)      # project, place, check hard rules
            best = better_of(best, plan)
            if plan.hard_ok:
                return finish(plan)                 # glyph scatter + fingerprint
        if repositionable(admitted):                # 1) move flexible objects
            reposition_worst(admitted, cfg); continue   # frustum-aware (below)
        if anchor.art_mode is CONTINUOUS and anchor.box_class < last_class:
            step_down(anchor); continue             # 2) anchor box class (2.3, 4.14)
        if len(admitted) > 0:                       # 3) reject lowest priority
            drop = admitted[-1]; admitted.pop()
            record(Decision("retention_reject", drop.key, "reject", ...))
            continue
        break
    return finish(best or starfield_only(viewport, mode))
```

Each `continue` consumes one counted pass. A rejected object is never re-admitted within
the same solve, so the loop is monotone and cannot cycle (§2.3).

**`attempt` hard rules, in this order** — cheapest and most-rejecting first, so the
expensive checks run on few objects:

```text
1. near-plane and viewport containment (with cfg.edge_margin)
2. minimum projected size, per scale class
3. ladder: a rung whose natural box fits the projected box exists  (4.7)
   continuous: the projected box clears ContinuousYield.min_extent
4. separation: ink_max boxes, inflated by cfg.separation, do not overlap
   (belts and other occludes=False objects are skipped entirely)
5. occlusion by depth: for each nearer/farther pair, visible fraction of the farther
   object >= cfg.min_visible_fraction[class]; equal depth is ordered by
   (face.area_su desc, key) and reported                                  (4.8)
6. equal-depth scale-class ordering is preserved                          (4.4)
7. cumulative render cost <= cfg.cost_budget and ship count <= emergency ceiling
```

**Comparing candidates.** `better_of` compares this integer tuple, all ascending-better:

```text
(rejected_by_retention_tier,      # tuple, most-protected tier first (see below)
 -count_admitted,
  count_min_violations,
  abs(anchor_height - target_height),
 -min_separation_slack,
  hysteresis_delta(plan, previous),
  plan.fingerprint)                 # stable final tie-break, never iteration order
```

`rejected_by_retention_tier` is a length-`len(SceneRetention)` tuple counting how many
objects of each retention tier this attempt rejected, tier-value order (most protected
first). It exists because the raw `-count_admitted` term alone violates §4.5 across the
pass loop, not within one attempt: the pass loop's own fallback ladder monotonically
shrinks `admitted` (rule 3 above), so a **later** pass's `best` candidate is drawn from a
*smaller* admitted set than an **earlier** pass's — and `-count_admitted` compares those
two attempts' raw totals with no regard for which objects they contain. A pass that still
had every ship in `admitted` and happened to fit three of them while rejecting the (higher
priority) anchor previously could out-score a later pass that fit the anchor alone,
because 3 > 1 — silently dropping the object retention exists to protect. Comparing
tier-by-tier first makes any rejection at a higher tier strictly worse than any number of
lower-tier gains, so `best` can never again prefer "more low-priority objects, minus the
anchor" over "the anchor, minus some low-priority objects." This was a latent gap: it
never manifested before the reposition fix below, because flexible objects rarely
succeeded together often enough to reach it.

**Hysteresis metric** (integer L1, weights from config, `0` when `previous is None`):

```text
delta = w_cam * abs(anchor_height_now - anchor_height_prev)
      + w_pos * sum(abs(d_col) + abs(d_row) for objects in both plans)
      + w_adm * len(admitted_now ^ admitted_prev)
      + w_art * sum(abs(d_width) + abs(d_height) for objects in both plans)
```

Hysteresis is only ever the fifth term of the comparison tuple, which is what makes
"hysteresis never defeats a hard rule" (§4.11) structural rather than a matter of weight
tuning.

**Frustum-aware reposition (post-WP-SC09 fix).** `region_by_scale_class` deliberately
gives a non-anchor scale class (ship/wreck) a placement region far wider than the camera,
framed only against the anchor, can ever show at once (§2.5) — the initial hash-derived
placement in `classify.py` samples that whole region blind (it is viewport-independent by
design, plan §9.3), and `reposition_worst`'s original fallback resampled the *same* full
region again on every retry, with no camera awareness at all. Because the visible slice of
a wide region is typically under 10% of its volume, this gave each reposition attempt well
under a 2% chance of landing somewhere `attempt`'s hard rules could ever accept, so a
non-anchor object was rejected almost every time even in the simplest scenes (e.g. a port
with two ships losing both). The fix narrows *where within the region* `reposition_worst`
samples, never the region itself:

```text
def reposition_worst(target, cfg, camera, viewport, strategy):
    z = hash_index(region.z_min..z_max)                  # unchanged: still the full region
    extent = strategy.visible_xy_extent(camera, viewport, z, target.face, cfg)
    x_lo, x_hi, y_lo, y_hi = intersect(region.xy, extent) or region.xy   # fall back untouched
    x = hash_index(x_lo..x_hi); y = hash_index(y_lo..y_hi)
    return Vec3(x, y, z)
```

`visible_xy_extent` (`edge/scene/project.py`, one method per `ProjectionStrategy`) inverts
`project()`'s own forward formulas: given a camera, viewport, depth `z`, and a face size,
it solves for the su-space `(x_min, x_max, y_min, y_max)` box within which that face,
placed anywhere inside, projects fully inside the viewport with `cfg.edge_margin`
clearance — exactly the containment test `attempt` applies after the fact, computed in
advance instead of by trial placement. It is an *estimate* against the pass's currently
framed camera (the one `strategy.frame()` returns for the anchor, not necessarily the
exact candidate `attempt` ultimately accepts, since `candidates()` still sweeps height/aim
around it) — sampling from its intersection with the object's own region only biases the
existing bounded hash draw toward where a camera the solver would plausibly use can show
the object; it never claims an exact guarantee, and a `None`/empty intersection (near-plane
failure, or a face too large to fit at that depth at all) falls back to the untouched full
region, exactly the pre-fix behaviour for that one draw. This keeps the "wide region" design
intent of §2.5 intact — a ship can still land at any depth in its full region, including the
far side of it — while making that freedom actually reachable by the bounded search instead
of resampling a near-uniformly-invisible box every time. No new unbounded work is added: the
reposition fallback still spends exactly `cfg.max_reposition_candidates` attempts per
flexible object, and still shows up in `SolveCounters.reposition_candidates` as before.

**Frustum-aware reposition, z half (follow-up fix).** The xy fix above left z drawn
uniformly from the object's full nominal `region.z_min..z_max` — measured real-world
impact: 0.0% → 14.0% (`FixedFovPerspective`) / 0.0% → 5.2% (`DepthLayeredAnchorProjection`)
admission across the 172 secondary objects in `edge/tui/scene_gallery.py`'s full
case/size matrix, with the remaining rejections dominated by `no_clearing_rung`,
`min_projected_size`, and residual `edge_margin` — because the workable z-band for a
typical ship is only ~10% of its region's z-span, and z sampling still ignored this
entirely. `edge/scene/solve.py::_feasible_z_interval` closes that gap: rather than
deriving a closed-form inversion of `scale(z)` per strategy (`FixedFovPerspective`'s
`Fraction` divide vs. `DepthLayeredAnchorProjection`'s discrete per-layer power, plus a
further per-rung natural-size threshold for a laddered object), it reuses
`strategy.project()` and the exact same `_contained`/`_select_rung`/`_ink_box` functions
`_attempt()` itself calls as an oracle, and finds the feasible z-band by two bounded
binary searches (`O(log(region.z_max - region.z_min))` `project()` calls, never a scan
— §6.2 rule 4) rather than a linear probe. This works exactly because, for either
strategy, `scale(z)` is non-increasing in z, so the "too big" (near-plane/edge-margin)
failure can only occur for z too close to the camera and the "too small"
(`min_projected_size`/`no_clearing_rung`/`min_ink_extent`) failure can only occur for z
too far — each is independently monotonic, so a laddered object's discrete rung ladder
does not need a union over rungs: every rung's natural size only ever moves the
*threshold* at which "too small" flips, never the direction, so the feasible rungs
collapse to one contiguous z-band exactly like the continuous case, with the smallest
authored rung's natural size setting the far edge.

One subtlety the first version of this fix got wrong and had to correct:
`_z_ok_near_and_size`'s near-plane check reports `(False, False)` for a `z` that fails
the near-plane test (`dz <= 0` or `z < camera.near_plane_su`) — a *third*, independent
failure mode from "too small," and a common real shape, since a ship's region commonly
reaches back toward world z≈0 while the pass's framed camera sits far forward of the
anchor. Treating that `False` as "too small at the near end" broke the monotonicity the
binary searches depend on and made the interval come back empty far more often than the
true geometry warranted. The fix clamps both searches to the sub-range that already
clears the near-plane check (`z_valid_min = max(z_min, camera.near_plane_su,
camera.position.z + 1)`) before searching for the too-big/too-small thresholds within it.

The z interval is intersected with `region.z_min..z_max` exactly like the xy fix (a
`None` result, or `z_valid_min > z_max`, falls back to the untouched full region z-range
— this can only ever help, never newly reject a placement the pre-fix behaviour would
have allowed), and the resulting z feeds the existing xy computation unchanged, so the
final sampled point comes from the true joint (x, y, z) feasible volume rather than a
feasible xy slice at a blind z. Measured real-world impact after this fix: 19.8% → 26.2%
(`FixedFovPerspective`) / 6.4% → 33.1% (`DepthLayeredAnchorProjection`) — a clear further
improvement over the xy-only fix, though still short of "high, legacy-composer-like"
reliability; the remaining rejections trace to the estimate being evaluated against the
pass's framed camera rather than the eventual accepted candidate camera (`candidates()`
still sweeps height/aim around it), to only one flexible object being repositioned per
fallback-ladder iteration, and to `separation`/`no_clearing_rung` failures that are
governed by other objects' positions and authored rung granularity rather than by z
alone.

**Joint secondary-object placement (post-WP-SC09 redesign).** The two
frustum-aware reposition fixes above each closed exactly the gap they targeted
and then plateaued — 0.0% → 14.0%/5.2% → 26.2%/33.1% admission of the 172
secondary (non-anchor, `flexible=True`) objects in `edge/tui/scene_gallery.py`'s
full case×size matrix, against **93.0%** for the legacy `_SceneComposer` measured
on the same inventories. The plateau was structural, not a matter of one more
per-axis fix: **`§9.6`'s pass loop placed every flexible object independently,
once, before the camera search, and judged the result against a camera the
placement had never seen.** Concretely, three defects compounded:

1. *Placement was outside the candidate loop.* `reposition_worst` estimated
   feasibility against the pass's **framed** camera, while `attempt` judged the
   result against whichever camera `candidates()`'s height/aim sweep eventually
   accepted. The frustum machinery was aimed at the wrong frustum.
2. *Objects could not see each other.* `separation` is a **joint** constraint,
   but each object drew its position with no knowledge of where the others had
   landed, so two ships routinely drew overlapping positions and the solver had
   no mechanism to negotiate.
3. *Only one object moved per pass,* and each pass then re-ran the entire
   camera sweep against the unchanged placements of everything else.

The redesign moves placement **inside** `_attempt`, making it part of a
candidate camera's own evaluation rather than a separate step around it:

```text
def _attempt(camera, admitted, base_positions, ...):
    placed = []
    cost = ships = 0
    for obj in admitted:                      # retention order, §4.5/§4.6
        if cost + cheapest_cost(obj) > cfg.cost_budget: reject "cost_budget"
        if is_ship and ships + 1 > ceiling:   reject "emergency_ship_ceiling"
        if not obj.flexible:                  # anchors/planets/Entity: 1 candidate
            evaluate(obj, base_positions[obj.key])
            continue
        region = absolute_region(obj, placed) # parent-relative for orbitals
        band   = feasible_z_interval(camera, obj, region.z)   # memoised
        if band is None: reject "no_feasible_depth"           # exact: no xy helps
        for z in depth_strata(obj.key, band, preferred=(base.z, previous.z)):
            box = project(obj, at aim centre, z)              # size at this depth
            for slot in shuffled(obj.key, z, slot_lattice(viewport, box)):
                if slot collides an already-placed inflated ink box: continue
                x, y = su_for_screen(strategy, camera, z, slot, box)  # inverse
                clamp (x, y) into region ∩ visible_xy_extent
                evaluate(obj, Vec3(x, y, z))   # every hard rule, vs `placed`
                if accepted: break
        # budget: at most cfg.max_reposition_candidates full evaluations
```

Why each piece:

- **Screen-space slot search.** Edge margin, separation, and occlusion are all
  *screen-space* constraints. Sampling su space and hoping is what produced the
  <2% hit rate; sampling the screen lattice and inverting through
  `ProjectionStrategy.scale_at()` (a new protocol method, exact `Fraction`, one
  per strategy) samples exactly the quantity the rules measure. A slot is
  rejected against already-placed boxes by integer rectangle arithmetic *before*
  any projection work, so the expensive full evaluation is spent only on slots
  that already look free.
- **Greedy, in retention order.** Objects negotiate by ordering, not by
  backtracking: the higher-priority object always chooses first and is never
  moved to make room. This is a deliberate bounded-work tradeoff (§6.2 rule 4) —
  an exhaustive joint search over `n` objects and `k` positions is `k**n` — and
  it is *also* the only ordering that structurally cannot violate §4.5, since
  the object that wins a contested slot is always the higher-priority one. The
  cost: a scene where moving a high-priority ship would have let two others fit
  keeps the one placement it found. No such case appeared in the matrix.
- **Cost spent in retention order.** §4.14's words, now literal, in two places:
  the running cost is checked against the object's *cheapest authored rung*
  before any placement search is spent on it, and again against the *selected*
  rung inside `_evaluate_placement`, as one more hard rule beside separation and
  occlusion — so a candidate too dear for the remaining budget is refused and
  the object's bounded candidate list continues to a cheaper (farther) one
  rather than the object being dropped. The pre-redesign `_attempt` summed the
  whole scene and, on overflow, cleared the *entire* admitted set — which with a
  50-ship stress inventory produced an empty plan (a §4.18 violation the pass
  loop could not recover from, since `max_passes` is far below the number of
  ships to shed). The pass loop's anchor box-class step-down still runs before
  any *retention* rejection, so §4.14's ordering requirement holds: a
  cost-refused object is reconsidered on the next pass against the cheaper
  anchor, and `step_downs` is observed reaching the bottom of the ladder on the
  stress cases before the reject rung fires.
- **Parent-relative regions.** `region_by_scale_class["orbital"]` is documented
  as an offset from the parent planet; the old reposition sampled it absolutely
  and pulled stations out of orbit. `_absolute_region` re-adds the parent origin
  (parents are placed first because `ANCHOR < ORBITAL` in retention order).
- **Empty feasible z-band is now an honest reject,** not a fallback to the full
  region. `_feasible_z_interval` evaluates the depth-dependent rules at the
  camera's aim point, the most permissive xy there is, and the min-size/rung/
  ink-extent rules are xy-independent — so an empty band proves no placement can
  pass *under this camera*. The object still gets a fresh chance under every
  other camera candidate, which the old single-shot draw did not.

**Deviations from the original §9.6 pseudocode** (none touches a §4 invariant):

| §9.6 as written | Now | Why |
|---|---|---|
| `attempt(cam, admitted, …)` projects fixed placements | `_attempt` also *places* | the fix; see above |
| fallback ladder `reposition → step_down → reject` | `step_down → reject` | reposition is subsumed; a pass is no longer spent on it |
| `reposition_worst` / per-object reposition budget | `cfg.max_reposition_candidates` is the per-object, per-camera full-evaluation budget | same config key, same counter, new (documented) semantics |
| `candidates()` yields only swept heights | yields the framed camera first | §9.6 says "nearest-to-current first"; "current" was being dropped, and for a *continuous* anchor the approved WP-SC05 numbers put `frame()`'s own height (`target_fraction / ink_ratio`, e.g. `1/2 ÷ 3/5 = 5/6`) outside `[camera_height_fraction_min, max]` = `[1/8, 3/4]`, so the framed camera was unreachable for every planet/nebula scene |
| cost/ceiling checked as a whole-candidate sum | spent per object in retention order | §4.14's own wording; see above |

New code-level (not config) search bounds, as §6.2 rule 4 permits: `_SLOT_COLS`
= 7, `_SLOT_ROWS` = 5, `_DEPTH_STRATA` = 4. New trace rule ids:
`no_feasible_depth`, `no_feasible_placement`, `cost_budget`,
`emergency_ship_ceiling`. `SolveCounters.reposition_candidates` now reports
placement evaluations; every other counter is unchanged.

**Measured result** (`edge/tui/scene_gallery.py::cases()` × `SIZES`, 172
secondary objects, real `build_scene_tuning()`/`load_geometry_catalog()` config):

| | `FixedFovPerspective` | `DepthLayeredAnchorProjection` |
|---|---:|---:|
| WP-SC06 as shipped | 0.0% | 0.0% |
| + xy frustum fix | 14.0% | 5.2% |
| + z feasibility fix | 26.2% | 33.1% |
| + framed camera as candidate #0 | 27.9% | 33.1% |
| **+ joint placement** | **94.8%** (163/172) | **99.4%** (171/172) |
| legacy `_SceneComposer` baseline | 93.0% (160/172) | 93.0% (160/172) |

**Open observation, not a §4 violation.** On the §6.3 synthetic stress
inventories the 50-ship case admits *fewer* objects than the 20-ship case under
`FixedFovPerspective` (3 vs 8; `DepthLayeredAnchorProjection` holds at 8). Both
are cost-bound — `cost_estimated` is 246–250 against a 250 budget, and the
anchor has already stepped its box class down to the bottom rung
(`step_downs` = 2) — so §4.14 is satisfied: cost really is being spent in
retention order. What differs is *which* rung the first-placed ships take. The
retention sort tie-breaks on `SceneKey`, so a 50-ship inventory presents a
different ship first than a 20-ship one, and a first ship that lands at a near
depth takes a rich, expensive rung and starves the rest. Cost is checked inside
`_evaluate_placement`, so a candidate too dear for the remaining budget is
refused and the object's bounded candidate list continues to a cheaper (farther)
one — but the *first* objects are never under budget pressure and so never look
for a cheaper rung. Correcting this would mean a new soft objective trading rung
richness against admitted count, which is a §5 calibration decision (and would
pull against §4.13's depth-variation objective), so it is recorded here rather
than invented. It does not appear at any inventory size a generated universe
produces.

Solver-only wall clock on the plan §6.3 synthetic stress inventories
(150×52, one planet plus N ships, no art rendered): 1 ship 0.5–10 ms, 5 ships
2–44 ms, 20 ships 0.7–1.2 s, 50 ships 0.7–1.2 s. `tests/test_scene_joint_placement.py`
is the CI guard for the admission rate, the hard rules on every admitted object,
determinism, retention order, the bounded counters, and §2.5's wide-region
intent.

**Minimum-richness floor (post-WP-SC09 fix).** Maintainer review of real
rendered output (`pixi run scene-gallery --serve --compare`) surfaced two
complaints: composers were shrinking ports/stardocks/starbases to their worst
authored rung, and ships were rarely landing on their larger tiers even on
large viewports. Inspecting the checked-in `edge/art/geometry_catalog.json`
confirmed the root cause: `min_projected_cells_by_scale_class`'s `orbital`
(3, 2) and `ship` (3, 1) floors are both *smaller than the smallest authored
rung of every ladder* (e.g. `trading_port`'s worst vertical rung is 7x3;
`capital_warship`'s worst horizontal rung is 18x3) — so they impose no real
constraint on which rung `_select_rung` (`edge/scene/solve.py`) picks.

The fix adds a second, genuine exclusion alongside that floor:
`SceneTuning.min_rung_index_from_end_by_scale_class` (`Mapping[str, int]`,
config field `scene.physical_model.min_rung_index_from_end_by_scale_class`,
built by `edge.art.scene_tuning.build_scene_tuning`) names, per
`PhysicalObject.scale_class`, how many of the *worst* (highest-`index`)
rungs of a laddered object's own ladder `_select_rung` must never select —
not a bigger absolute cell-count floor, since natural rung sizes vary
substantially by subtype/axis (a single number tuned to exclude one
subtype's worst rung would under- or over-constrain another's). `index`
ascends from 0 (richest) per `LadderRung`'s docstring; the exclusion is
computed against `max(r.index for r in catalog.rungs(key))` for that
specific ladder, not a hardcoded rung count, so it scales correctly even
though port/starbase/stardock ladders have 4 rungs and ship ladders have 3.

This plugs into the *existing* rung-selection/z-feasibility machinery as an
additional exclusion on what "clears" means, not a post-hoc filter:
`_select_rung` filters `catalog.rungs(key)` down to the allowed subset before
ranking or fit-testing, and every caller that reasons about whether some rung
clears at a given projected size or depth (`_evaluate_placement`,
`_z_ok_near_and_size` -> `_feasible_z_interval`, `_cheapest_cost`'s render-cost
floor) goes through it, so an object that can only ever reach an excluded
rung is rejected outright — never shown degraded — consistently with this
plan's no-cropping philosophy. `_feasible_z_interval`'s monotonic-band
argument (§9.6 above) is unaffected: shrinking the *set* of rungs `_select_rung`
will ever return does not change the direction in which the natural-size
threshold moves as z increases, only which authored size sets the far edge.

Calibration, from the real gallery case/size matrix (`edge.tui.scene_gallery`'s
`cases()` x `SIZES`, both projection strategies) via
`build_scene_tuning()`/`load_geometry_catalog()` ->
`classify_sector()` -> `solve()`:

- `orbital: 1` (never the single worst of 4 rungs) ships in
  `config/default.yaml`. Rung-distribution proof: before, 34/196
  (`FixedFovPerspective`) and 37/196 (`DepthLayeredAnchorProjection`) admitted
  ports/starbases/stardocks used the worst rung; after, 0 in both — fully
  eliminated, redistributed to indices 0-2. This costs some admission,
  directly (an orbital that could only reach the excluded rung is now
  rejected) and indirectly (a richer orbital rung costs more `render_cost`,
  leaving less of `cost_budget` for the ships sharing the same solve, and a
  rejected/repositioned orbital changes which camera the joint solve scores
  best): orbital/ship/wreck admission across the full matrix moved from
  ~95.4%/99.5% to ~75.5%/81.6% (`FixedFovPerspective`/
  `DepthLayeredAnchorProjection`). `tests/test_scene_joint_placement.py`'s
  admission-rate floor was lowered from 85% to 70% to match, documented
  in-line with the same numbers on that module's smaller matrix (~77%/~84%).
- `ship` is **deliberately absent** from the shipped map. Measurement showed
  that excluding even the single worst of a ship's 3 rungs collapses
  `DepthLayeredAnchorProjection`'s ship/wreck admission from ~99% to ~3%: that
  strategy's depth is quantised into `depth_layers` (8) discrete steps of
  `depth_layer_scale` (4/5) each, and the narrower "2-of-3 rungs both clear"
  z-band the floor demands frequently falls entirely between two of those
  steps, so almost no depth layer lands inside it. `FixedFovPerspective`'s
  continuous depth scaling does not have this failure mode (its admission
  actually rose slightly under a ship floor, from cost/camera-selection
  interaction), so the ship complaint is confirmed real but not fixable by
  this mechanism alone — the maintainer's "ships never use the larger sizes
  even on large screens" observation most likely also implicates
  `target_fraction_by_scale_class["ship"]` (1/8, i.e. ships are framed small
  by design) and/or the depth-layered strategy's coarse layer granularity,
  neither of which this fix touches. Recorded here as an open follow-up
  rather than shipped half-working.

**Glyph scatter**, after the solve and after paint (§4.19):

```text
free = viewport cells not covered by any accepted ink_actual box
rng  = Random(f"{sector_id}|glyphs|{viewport.width}x{viewport.height}")  # local, not game RNG
for glyph in sorted(glyphs, key=lambda g: g.key):
    for _ in range(cfg.max_glyph_tries):
        pick a free cell; if it clears cfg.glyph_spacing from placed glyphs: place
    else: counters.glyphs_dropped += 1  ->  sidebar entry, never scene text
```

### 9.7 Art resolution and paint (WP-SC07)

```text
for projection in plan.projections (far -> near):
    box  = projection.rung.natural if LADDER else box_classes[projection.box_class]
    art  = render(entity_type, subtype, seed=stable_identity, box, facing, archetype)
    ink  = crop_to_ink(art)                       # char != " " bbox
    if ink exceeds projection.ink_est on either axis:
        one bounded correction: re-check rules 4-6 with the actual box; on failure
        shrink one rung / one box class, or reject.  Never raise the cost class (4.14),
        never restart the camera search (6.2 rule 2).
    paint(ink) into the cell grid, spaces transparent
```

The composition-local render cache is keyed exactly by `(entity_type, subtype, seed, box,
facing, archetype, treatment)` (§6.2 rule 3), and the `render_once_per_final_box` counter
asserts it. The docked-header mapping publishes `(sector_id, station_kind, object_id) ->
natural (width, height)` — the *rung's* box, never a padded container (§4.12).

### 9.8 Deliberately still open

Everything in §5. This section fixes the shapes — types, keys, units, orderings,
algorithms — precisely so that calibration is only choosing numbers, and so a wrong number
is a config edit rather than a rewrite. Two further choices are recorded here as made,
and are revisable only with the same explicit approval as a §5 value: bounding-box face
area (§9.1) and lexicographic integer candidate comparison (§9.6).
