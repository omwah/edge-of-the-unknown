# Sector scene physical-model composition plan

> Companion to `DESIGN.md`, `SECTOR_SCENE_COMPOSITION.md`, `UI_MOCKUPS.md`, and
> `SPRITE_ART_SYNC.md`. `DESIGN.md` is the
> authoritative *what*; this document is the *how and in what order* for replacing
> the shipped arrival-view composer. The existing scene note remains authoritative
> for current behavior until the replacement lands.
>
> **Status: reviewed plan — composition interview and review corrections approved
> 2026-09-01, with the art-seam, cost, determinism, and packaging corrections of the
> second review folded in the same day. The legacy composer is kept permanently as a
> config-selectable fallback and reference model for tests (see WP-SC11).
> `fixed_fov_perspective` is the approved default `ProjectionStrategy`; `depth_layered_anchor`
> is likewise kept as a config option and reference strategy (see §2.4, WP-SC04, WP-SC11).**

## 1. Outcome

Replace the direct paint-as-you-decide `_SceneComposer` with a deterministic,
presentation-only physical scene model. Each visible sector object receives a simple
camera-facing 2.5D shape, a physical parent and allowed placement region/depth range, a
nominal face-area scale class, and a gameplay retention priority. A swappable projection
strategy frames the
highest-ranked subject, projects the accepted objects into terminal-cell bounds, and
selects an existing sprite tier for laddered art or a continuous render box for
procedural art. Fixed-FOV perspective and depth-layered anchor projection implement the
same contract; `fixed_fov_perspective` is the approved shipped default, chosen from
measured composition quality and cost, and `depth_layered_anchor` remains a
config-selectable strategy rather than being deleted (see WP-SC11).

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
  perspective and depth-layered anchor projection. **Both remain in the shipped
  solver as config-selectable strategies, the same way the legacy composer is kept
  alongside the physical model (see WP-SC11)** — `fixed_fov_perspective` is the
  approved default; `depth_layered_anchor` stays available as a config option and a
  reference strategy for tests, never deleted as a "losing" experiment.
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
  depth-layered anchor projection in calibration. Both implementations enter the
  production solver as config-selectable strategies: `fixed_fov_perspective` is the
  approved default, `depth_layered_anchor` remains selectable and is retained as a
  reference strategy for tests.
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
baseline. WP-SC11 cannot promote the physical model to the default if any approved
budget fails, if candidate/sprite-render counts exceed their hard bounds, or if a visual
improvement depends on repeated speculative sprite rendering.

**If neither strategy can meet the budgets, the answer is no-go, not a slow cutover.**
The shipped composer remains the default; `edge/scene/` stays in the tree as unwired,
strict-typed, tested code with the measured no-go recorded in this plan, and the
WP-SC09/WP-SC11 config switch simply keeps defaulting to the legacy path. Nothing
half-migrated ships: WP-SC10's consumer migration does not land under a no-go, and the
WP-SC01 DTO projection — which is independently useful and already wire-versioned —
stays. Reopening requires new evidence or a fresh interview on the visual-quality-
versus-cost trade, not a quieter reading of the same numbers. A no-go and a go now
differ only in which composer is the config *default* — both remain shippable,
selectable code either way.

## 7. Work packages

Each package is a small, independently reviewable commit. No package may hand-edit the
vendored sprite library or assets. Every WP that changes `scene:` values or requested art
boxes runs `test_every_subtype_renders_a_whole_tier_at_its_scene_box`, not only the
cutover WP. Each package below states *what must be true*; the shipped solver mechanics —
units, retention order, the solve loop, joint placement, and art resolution — live in
`SECTOR_SCENE_COMPOSITION.md` §11 now that WP-SC11 has shipped them, alongside that note's
existing §§0-10 for the legacy composer. Where that note and §4 here disagree, §4 wins.

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
- Compare and approve one production **default** strategy, its framing model, fixed FOV
  if relevant, class-specific target fractions, and structural viewport modes.
  `fixed_fov_perspective` is the approved default — `depth_layered_anchor` is kept, not
  removed, as a config-selectable strategy and a reference model for parity/regression
  tests (see WP-SC11, and the measured `DepthLayeredAnchorProjection` parity miss
  recorded in `SECTOR_SCENE_COMPOSITION.md` §9's legacy-parity discussion). The typed
  interface stays extensible either way.
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

Docs: consumer disposition — `station_art.py`/`screens/stardock.py`/`screens/base.py`/
`screens/port.py` migrated onto the WP-SC07 `StationReference` (required adding
`PortDTO.port_id`, wire v46, since ports had no entity id distinct from `sector_id`);
`scene_preview.py` gained a `--composer` flag reusing `scene_gallery.py`'s
`COMPOSERS`/`render_physical` seam; `scene_gallery.py` was already there;
`art_adapter.py`/`dummy.py`/`shots.py` were audited and found to have no
composer-specific coupling to migrate (pure vocabulary/sample/end-to-end-Pilot
consumers respectively). A port/starbase/ship with no `archetype_id` (reachable in
real play when no alliance controls its sector — `session.py`'s
`_controlling_archetype` fallback can return `None`) used to crash
`edge.scene.project`'s `frame()` when that object became the sole/anchor body, because
the generated ladder catalogue has no `archetype_id=""` rungs (only
`SPRITES.palettes.fallback_archetype`'s). Fixed by adding
`SceneTuning.fallback_archetype_id` (populated in `edge/art/scene_tuning.py` from
`SPRITES.palettes.fallback_archetype`) and using it in `edge/scene/classify.py`'s
three `LadderKey` sites instead of `archetype_id or ""`.

Commit: `ui: WP-SC10 migrate scene consumers`

### WP-SC11 — Approved cutover and final reconciliation

Depends on: WP-SC01–WP-SC10.

The legacy composer and the non-default `ProjectionStrategy` are both kept, not removed:
the legacy composer and `depth_layered_anchor` are permanent, config-selectable
alternatives — each a fallback and a reference model that tests may run the defaults'
behavior against. This section's cutover is "make the physical model with
`fixed_fov_perspective` the default," not "delete the losers."

Implementation:

- Make the physical-model composer running `fixed_fov_perspective` the **default**
  only after the complete A/B gallery is accepted, performance budgets and automated
  tests pass, and one hands-on playtest session explicitly accepts the replacement.
  These evidence gates define the readiness bar; elapsed time does not.
- **Do not remove the legacy composer, `DepthLayeredAnchorProjection`, or the WP-SC09
  dev switch.** Promote the switch from a dev-only toggle to a documented,
  schema-validated `scene:` config option (e.g. `scene.composer: physical | legacy` and,
  under `physical`, `scene.projection_strategy: fixed_fov_perspective |
  depth_layered_anchor`) that selects the composer and strategy at runtime, defaulting to
  `physical`/`fixed_fov_perspective` once approved. All implementations stay in the tree,
  tested, and covered by the A/B gallery indefinitely — neither the legacy path nor
  `depth_layered_anchor` is deprecated scaffolding awaiting deletion.
- Do not disposition `max_ships_shown` or `ship_face_inward_chance` as dead config to be
  deleted: both remain live, legacy-composer-only settings for as long as the legacy
  composer ships. `SceneArtConfig` continues to accept them; only the *physical* model's
  keys are validated under its own `extra="forbid"` schema.
- Keep both YAML surfaces intact — no sweep to delete "removed keys," because none are
  removed. New physical-model keys are added to `config/default.yaml → scene:` alongside
  the existing legacy keys, each documented as to which composer reads it.
- Rebaseline default snapshots with human review of every changed image (the physical
  model becoming the default changes what an un-configured snapshot renders), using
  WP-SC09's isolated replacement snapshots as the comparison rather than one wholesale
  blind update. Keep a parallel legacy-composer snapshot suite alive under the
  `legacy` config selection so both paths stay under regression coverage.
- Reconcile `DESIGN.md` §11, `UI_MOCKUPS.md`, `PLAYTEST_NOTES.md`, and
  `SECTOR_SCENE_COMPOSITION.md` to describe two supported composers (default: physical,
  optional: legacy) rather than a single surviving one; preserve shipped-history
  rationale where useful.
- Update `config/default.yaml → scene:` and schema comments together, documenting the
  `composer` selector and which keys belong to which composer. Reconcile
  `SPRITE_ART_SYNC.md` only if requested boxes/ladder assumptions changed; never edit
  vendored files here. Run `graphify update .`.

Verification:

- Create a disposition table for every existing legacy-composer composition test — as a
  checked-in checklist file, not a claim in a commit message, since this is the step
  most likely to be compressed under time pressure: carry unchanged as a legacy-path
  regression test, restate against a numbered §4 invariant for the physical model,
  duplicate so both composers keep independent coverage, or delete with a written
  implementation-specific reason. Because the legacy composer is retained rather than
  removed, the default disposition is "keep as legacy coverage," not "delete" — deletion
  still requires a written reason. Explicitly cover ship depth, `rung_below`/rung
  variation, vertical gaps, belt permeability, sky reserve, whole-art survival, and the
  former no-object-falls-out contract, replaced *for the physical model* by named
  sidebar overflow (the legacy composer keeps its existing contract). Budget new
  assertions where current coverage is absent rather than treating the table as
  sufficient coverage.
- All §4 invariants; art seam, config, wire, settings, Pilot, snapshots, local/remote
  parity, ruff, and strict mypy pass.
- Final controlled benchmarks satisfy approved absolute total-time, solver, candidate,
  render-count, cold/warm/resize, phenomenon, and 50-ship stress budgets.
- No document describes in-scene text overflow or direct paint-as-decision as current.
- The `legacy` composer and the `depth_layered_anchor` strategy selections still boot,
  render, and pass their retained snapshot/parity suites — cutover to a new default must
  not silently rot either kept alternative.

Commit: `ui: WP-SC11 default to the physical-model scene composer`

## 8. Non-goals

- No authoritative 2.5D/3D coordinates, orbital simulation, physics tick, or navigable
  spatial scene.
- No replacement or hand-edit of the vendored 2D sprites.
- No new rendering dependency or real-time 3D engine.
- No gameplay targeting, combat-position, detection, or movement consequences from the
  presentation model.
- No text-only objects inside the art scene.
- No TUI access to core state outside the service projection boundary.

