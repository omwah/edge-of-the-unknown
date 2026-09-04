# Sector scene calibration review (WP-SC05)

**PENDING HUMAN REVIEW / APPROVAL** -- every value below is a proposal for the maintainer to accept, reject, or adjust per plan §5. Nothing here has been written to `config/default.yaml`.

WP-SC05 calibration review sheet: proposed numeric values plus a traced matrix run through the real edge.scene classifier and both edge.scene.project strategies. Nothing here is a shipped default -- see the field-by-field rationale below for what a reviewer should accept, reject, or adjust.

Geometry catalogue: `1+wp-sc05-proposed-continuous`

## 1. Proposed SceneTuning values (plan §5 bullets, framing/camera/hysteresis)

### `face_extent_by_scale_class`

Proposed: `{'entity': (34, 14), 'anchor': (60, 30), 'belt': (90, 16), 'orbital': (14, 7), 'wreck': (16, 6), 'ship': (12, 5)}`

Preserves plan §2.2's ordering (entity > anchor > belt > orbital > wreck > ship) as bounding-box area (plan §9.1). Numbers are display scene units, not literal kilometres — the composer already exaggerates controlled ratios to stay legible at terminal resolution (plan §2.3). OPEN QUESTION for review: `classify_sector` looks up face extent by `scale_class` alone, and both a planet and every anchor-scale discovery (nebula/black_hole/wormhole) share the single "anchor" class (`edge/scene/classify.py` `_planet_object`/`_anchor_discovery_object`), which is sound because §2.1 says the two never coexist in one sector — but it also means the model as landed cannot express "wormhole slightly larger than planet" or "nebula ≫ wormhole" as a face-area distinction; only the classifier's discovery vs planet FaceShape (ellipse vs circle) differs today. If per-kind anchor sizing is wanted, `SceneTuning` needs a `face_extent_by_kind` map keyed by `continuous_kind`, which is a WP-SC02 model change, not something this calibration pass can retrofit without touching `edge/scene/model.py`/`classify.py`.

### `region_by_scale_class`

Proposed: `one shared region per scale class: Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=400)`

A single generous scene-unit box for every class keeps early calibration simple; it does not yet differentiate ship/wreck placement freedom from station orbital freedom by *size* (plan §5 asks for that distinction). Proposed as a starting point: review should decide whether ships/wrecks warrant a wider region than stations, per plan §2.5 ("[ships] receive wider placement regions/depth ranges than stations") — this proposal does not yet encode that width difference and should be revised before approval.

### `target_fraction_by_scale_class`

Proposed: `{'entity': '1/3', 'anchor': '1/2', 'belt': '1/2', 'orbital': '1/5', 'wreck': '1/8', 'ship': '1/8'}`

The Entity frames tighter than a planet/phenomenon (1/3 vs 1/2 of viewport height) so it reads as a close subject rather than a backdrop; ships/wrecks are rarely the anchor (only when nothing else is present) so their fraction is small and mostly theoretical.

### `ink_ratio_by_scale_class`

Proposed: `{'entity': '4/5', 'anchor': '3/5', 'belt': '1/3', 'orbital': '9/10', 'wreck': '4/5', 'ship': '9/10'}`

Seed ratio `frame()` uses before a laddered anchor snaps to its own rung's exact ratio (plan §9.5). Ships/stations are dense authored art (little padding, 9/10); planets/nebulae fade toward the edge (3/5); belts are the sparsest (1/3, permeable field, plan §2.5).

### `structural_mode_thresholds`

Proposed: `((120, 44, 'wide'), (87, 36, 'standard'), (0, 0, 'compact'))`

Plan §9.1 names exactly three modes (wide/standard/compact); the thresholds reuse the WP-SC04 benchmark canvas breakpoints (87x36, 120x44) so mode selection lines up with the sizes already measured, collapsing the benchmark's four labels to the plan's three names.

### `fixed_fov_num / fixed_fov_den`

Proposed: `1/2`

A gentle half-angle (visible height per depth unit) keeps distant admitted objects legible instead of shrinking sharply toward the frame edges; matches the value the WP-SC04 benchmark already exercised for continuity between the two review passes.

### `cell_aspect`

Proposed: `2`

Matches the shipped composer's existing `width = 2 * height` disc rule (`docs/SECTOR_SCENE_COMPOSITION.md`), so cutover does not silently change the terminal's visual proportions.

### `near_plane_su`

Proposed: `1`

Smallest workable positive depth; effectively "do not let anything sit on the camera plane."

### `depth_layers / depth_layer_size_su / depth_layer_scale`

Proposed: `8 / 6 / 4/5`

8 layers give `DepthLayeredAnchorProjection` enough depth resolution to distinguish near/mid/far traffic without an unbounded search space; a 4/5 per-layer scale gives roughly a 20% size step between adjacent layers, which is visually distinguishable at terminal resolution without ships snapping between wildly different sizes.

### `camera_height_fraction_min / _max`

Proposed: `1/8 / 3/4`

Bounds the framing-height sweep `candidates()` explores (plan §9.6): never frame an anchor smaller than 1/8 of the viewport (illegible) or larger than 3/4 (crowds out everything else).

### `aim_offsets_su`

Proposed: `(0, -2, 2, -4, 4, -6, 6)`

Centre-out, symmetric, bounded horizontal reframe search — enough range to dodge a collision without the candidate search degenerating into a full raster scan (plan §6.2 rule 4).

### `max_camera_candidates`

Proposed: `64`

Hard cap on `candidates()` output; keeps the bounded search bounded in the literal sense plan §6.2 rule 4 requires. 64 = the height sweep (roughly a dozen distinct rung/cell heights in practice) times the 7 aim offsets above, rounded up for headroom.

### `hysteresis weights (camera/position/admission/art)`

Proposed: `1/1/4/1`

Admission changes (an object popping in/out) are the most visually jarring resize artifact, so that term is weighted 4x the others; camera/position/art-size churn are weighted equally as comparatively minor wobble.

### `max_passes`

Proposed: `24`

Hard bound on the whole solve pass loop (plan §9.6, §6.2 rule 4): covers a handful of reposition attempts, at most one reanchor, and a few box-class step-downs before the loop must terminate.

### `edge_margin`

Proposed: `1`

One cell of clearance from every viewport edge (plan §2.4: "retain separation and edge margins rather than eliminate every void cell").

### `min_projected_cells_by_scale_class`

Proposed: `{'entity': (4, 2), 'anchor': (6, 3), 'belt': (6, 2), 'orbital': (3, 2), 'ship': (3, 1), 'wreck': (3, 1)}`

Below these cell dimensions an object reads as noise rather than its own shape; stations/ships need at least 2-3 cells on their short axis to read as a rectangle rather than a dot.

### `separation_margin`

Proposed: `1`

Matches edge_margin: one blank cell of clearance between distinct accepted objects' ink-max boxes (plan §9.6 attempt rule 4).

### `min_visible_fraction_by_scale_class`

Proposed: `{'entity': '1', 'anchor': '1', 'belt': '1', 'orbital': '3/4', 'ship': '3/4', 'wreck': '3/4'}`

The Entity and the framing anchor (planet/belt/discovery) are never partially occluded by construction in every case this tool traced, so their floor is 1 (fully visible or rejected); wrecks/ships/stations may be legitimately partly hidden behind a nearer object but must stay at least 3/4 visible to remain readable (plan §2.5).

### `cost_budget`

Proposed: `250`

Same scale as the catalogue's measured `render_cost` units (plan §9.4): the checked-in ship/port rungs measure in the tens, and the nebula's richest proposed box class above costs 110 -- this budget comfortably covers one rich anchor plus a handful of laddered ships, and is deliberately tight enough that the cost-pressure illustration below actually engages.

### `emergency_ship_ceiling`

Proposed: `40`

Protects against estimator/pathological-input failure (plan §2.3) well above any generated-universe DTO inventory the WP-SC04 benchmark measured, but comfortably below the 50-ship synthetic stress case (plan §6.3) so that case still exercises the ceiling.

### `max_reposition_candidates`

Proposed: `16`

Bounded reposition search (plan §9.6 step 1) -- enough positions inside a flexible object's region to usually dodge a collision without an unbounded scan.

### `max_glyph_tries / glyph_spacing`

Proposed: `20 / 2`

Plan §9.6's glyph scatter: 20 free-cell attempts per fighter/mine glyph before giving up to the sidebar, spaced 2 cells apart so a fighter garrison doesn't read as one solid block.

## 2. Proposed continuous-kind ink/cost envelopes

### `continuous[planet]`

Proposed: `ink_fraction=[3/5,9/10] min_extent=(6, 3) box_classes=((80, 40), (50, 25), (28, 14)) render_cost=(70, 35, 12)`

A disc render fills most of its request box (60-90%); three box classes give the anchor step-down ladder (plan §2.3) room to shrink twice before hitting the legibility floor.

### `continuous[nebula]`

Proposed: `ink_fraction=[2/5,9/10] min_extent=(10, 5) box_classes=((100, 50), (64, 32), (36, 18)) render_cost=(110, 55, 20)`

Cloud phenomena are diffuse (lower ink-fraction floor than a solid disc) but can be dense at full detail; the largest of these boxes is the plan §6.1 cost-dominant case, hence the highest render_cost in this proposal set — this is the anchor the cost-pressure illustration below exercises.

### `continuous[black_hole]`

Proposed: `ink_fraction=[1/2,9/10] min_extent=(8, 4) box_classes=((90, 45), (58, 29), (32, 16)) render_cost=(100, 50, 18)`

Accretion-disc/lensing system, plan §2.1: the visible phenomenon (not just the event horizon) supplies physical scale, so its envelope is sized close to the nebula's.

### `continuous[wormhole]`

Proposed: `ink_fraction=[1/2,4/5] min_extent=(6, 3) box_classes=((50, 25), (32, 16), (18, 9)) render_cost=(40, 20, 8)`

"Slightly larger than a planet" (plan §2.2): smaller top box class than the planet/nebula/black_hole entries above, not a separate scale_class (see the face-area open question).

### `continuous[wreck]`

Proposed: `ink_fraction=[1/2,4/5] min_extent=(5, 2) box_classes=((24, 10), (16, 7)) render_cost=(15, 6)`

Wrecks are not laddered (they are `ArtMode.CONTINUOUS` in `classify.py`) so they get their own small envelope; two box classes are enough since a wreck never anchors a crowded scene.

### `continuous[entity]`

Proposed: `ink_fraction=[3/5,9/10] min_extent=(8, 4) box_classes=((40, 16), (26, 10)) render_cost=(35, 14)`

The Entity is unique per sector and never rejected for cost (plan §2.3 invariant), so its ladder only needs enough room for the anchor step-down machinery to have somewhere to go.

### `continuous[belt]`

Proposed: `ink_fraction=[1/5,1/2] min_extent=(12, 3) box_classes=((120, 20), (80, 14)) render_cost=(30, 12)`

Permeable field (plan §2.5): low ink fraction is expected and correct, not a rendering failure — the field is mostly negative space with traffic and stations painted through it.

## 3. Extended proposals (budgets, margins, mode -- not yet SceneTuning fields; see rationale)

### render cost budget estimate-side tolerance

Proposed: `10%`

Plan §4.14: the budget binds the *estimate* side within this tolerance; the bounded actual-ink validation correction (§6.2 rule 2) may shrink or reject but never raise a box's cost class.

### ship-depth/rung-variation objective strength

Proposed: `weight 2 (soft)`

Plan §4.13: prefer arrangements where admitted ships don't all project to the same apparent size, but only as a tiebreaker after every hard rule and the primary hysteresis/admission-count comparison (plan §9.6's lexicographic tuple) — a low, clearly-soft weight.

### default global label mode (`scene_labels`)

Proposed: `"hover_hint"`

Keeps the art scene visually uncluttered by default while remaining fully accessible via mouse hover and keyboard focus (plan §2.6); a player who wants always-on names can switch to `labeled` in Options.

### absolute latency budgets (warm/cold/resize/phenomenon p95)

Proposed: `warm 50ms, cold 200ms, resize 80ms, nebula/black_hole 400ms`

Set from the WP-SC04 reproducible baseline's own cached-median ranges (`docs/SCENE_BENCHMARK_BASELINE.md`): comfortably above the measured cached medians so the physical model has headroom for its own bounded search, while still well under the informal uncached figures the plan's §6.1 baseline records for large nebula scenes ("1-4 seconds").

### solver-only latency and candidate-count budget

Proposed: `solver time <= 30ms warm, <= max_camera_candidates * max_reposition_candidates candidate-projections per solve`

A generous fraction of the total warm budget above, leaving most of the 50ms for sprite generation/cell conversion/paint (plan §6.4's total-time-vs-solver-time split); the candidate cap is the product of the two bounded searches above, which is the worst case the solve loop's pass budget can spend before it must fall back to rejection.

## 4. Matrix cells: production classifier + both strategies

Every cell below ran through the real `edge.scene.classify.classify_sector` and the named `edge.scene.project` strategy. `decision` for the anchor is always `"anchor"`; every other object is labelled `would-accept (pending WP-SC06 hard rules)` or `would-reject: <reason>` -- neither is a real admission decision, since the solver does not exist yet.

### empty+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(14, 81, -5)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (21,12,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-18,28,4x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### empty+ships @ standard 67x30 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (21,12,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,15,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### empty+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(14, 81, -17)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (31,15,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-17,33,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### empty+ships @ wide 87x36 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (31,15,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,18,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### empty+ships @ large 120x44 -- fixed_fov_perspective

camera position `(14, 81, -7)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (43,18,34x7) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-16,41,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### empty+ships @ large 120x44 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (48,19,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,22,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### empty+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(14, 81, -19)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (58,22,34x7) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-11,47,7x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### empty+ships @ huge 150x52 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (63,23,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,26,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### port+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-17, -42, 280)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-211,-36,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### port+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### port+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-17, -42, 268)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-199,-33,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### port+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### port+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-17, -42, 252)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-181,-29,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### port+ships @ large 120x44 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### port+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-17, -42, 236)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-165,-24,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### port+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### stardock+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-17, -42, 280)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-211,-36,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### stardock+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### stardock+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-17, -42, 268)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-199,-33,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### stardock+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### stardock+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-17, -42, 252)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-181,-29,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### stardock+ships @ large 120x44 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### stardock+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-17, -42, 236)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-165,-24,25x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### stardock+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-17, -42, 339)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `port:64`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| port:64 | port | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 340 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=17830671323189067475) at z=337 is at/behind near_plane_su=1 |

### starbase+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-113, 19, 3)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (312,-60,28x6) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (26,17,4x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### starbase+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,15,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### starbase+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-113, 19, -9)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (315,-55,27x6) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (35,20,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### starbase+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,18,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### starbase+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-113, 19, -25)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (326,-50,26x6) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (50,25,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### starbase+ships @ large 120x44 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,22,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### starbase+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-113, 19, -41)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (337,-44,26x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (63,29,7x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### starbase+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,26,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,2,100x25) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,51,14x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-152, 69, 298)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,96x24) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,31,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (69,61,17x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,38,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-152, 69, 234)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,149x37) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (92,75,21x4) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ large 120x44 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (72,42,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-152, 69, 235)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-14,3,178x45) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (113,89,24x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### planet+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (87,46,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,2,100x25) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (26,20,4x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,51,14x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-152, 69, 298)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,96x24) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (33,15,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,31,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (35,24,5x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (69,61,17x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (43,18,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,38,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-152, 69, 234)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,149x37) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (49,30,6x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (92,75,21x4) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ large 120x44 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (59,22,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (72,42,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-152, 69, 235)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-14,3,178x45) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (62,35,7x2) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (113,89,24x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### planet+port+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (74,26,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (87,46,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,2,100x25) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (26,20,4x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,51,14x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-152, 69, 298)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,96x24) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (33,15,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,31,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (35,24,5x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (69,61,17x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (43,18,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,38,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-152, 69, 234)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,149x37) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (49,30,6x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (92,75,21x4) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ large 120x44 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (59,22,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (72,42,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-152, 69, 235)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-14,3,178x45) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (62,35,7x2) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (113,89,24x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### planet+stardock+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (74,26,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (87,46,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,2,100x25) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (-73,5,12x3) | 368 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,51,14x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-152, 69, 298)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,96x24) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (13,12,2x1) | 368 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,31,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (-85,5,15x4) | 368 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (69,61,17x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (17,15,3x1) | 368 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,38,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-152, 69, 234)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,149x37) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (-98,7,18x5) | 368 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (92,75,21x4) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ large 120x44 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (34,19,3x1) | 368 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (72,42,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-152, 69, 235)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-14,3,178x45) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (-113,8,22x5) | 368 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (113,89,24x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9101 | (49,23,3x1) | 368 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (87,46,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (4,16,6x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-43,6,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ standard 67x30 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (33,15,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,14,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-29,0,144x36) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (9,19,7x2) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-48,8,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ wide 87x36 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (43,18,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,17,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ large 120x44 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-28,0,176x44) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (18,24,9x2) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-52,9,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ large 120x44 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (59,22,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,21,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-29,0,208x52) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (25,28,10x3) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-57,11,9x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+port+ships @ huge 150x52 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (74,26,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,25,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (4,16,6x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-43,6,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ standard 67x30 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (33,15,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,14,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-29,0,144x36) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (9,19,7x2) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-48,8,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ wide 87x36 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (43,18,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,17,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ large 120x44 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-28,0,176x44) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (18,24,9x2) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-52,9,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ large 120x44 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (59,22,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,21,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-29,0,208x52) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (25,28,10x3) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-57,11,9x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### blackhole+port+ships @ huge 150x52 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 118 | box class 2 (32x16) | 16x8 | 18 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (74,26,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,25,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(43, -32, 71)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-43,-4,153x38) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (3,16,6x2) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-46,6,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ standard 67x30 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (33,15,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,14,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(43, -32, 70)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-47,-5,180x45) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (8,19,7x2) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-52,7,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ wide 87x36 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (43,18,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,17,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ large 120x44 -- fixed_fov_perspective

camera position `(43, -32, 70)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-50,-6,220x55) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (16,24,9x2) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-57,9,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ large 120x44 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (59,22,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,21,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(43, -32, 70)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-55,-7,260x65) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (23,28,11x3) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-62,10,9x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### nebula+port+ships @ huge 150x52 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | - | (74,26,1x1) | 340 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,25,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(14, 81, -5)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (21,12,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-18,28,4x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-191,104,22x4) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ standard 67x30 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (21,12,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,15,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-101,68,13x2) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(14, 81, -17)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (31,15,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-17,33,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-193,112,23x4) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ wide 87x36 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (31,15,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,18,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-91,71,13x2) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ large 120x44 -- fixed_fov_perspective

camera position `(14, 81, -7)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (43,18,34x7) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-16,41,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-261,150,31x6) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ large 120x44 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (48,19,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,22,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-75,75,13x2) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(14, 81, -19)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (58,22,34x7) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-11,47,7x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-260,159,33x6) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wreck+ships @ huge 150x52 -- depth_layered_anchor

camera position `(14, 81, 54)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `ship:4091162512351261573`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (63,23,24x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,26,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (-60,79,13x2) | 83 | box class 1 (16x7) | 8x4 | 6 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (-3879,-639,336x84) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-43,6,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ standard 67x30 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (0,0,0x0) | 63 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='starbase', ident=4) at z=63 is at/behind near_plane_su=1 |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,14,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-29,0,144x36) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (-4651,-767,403x101) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-48,8,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ wide 87x36 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (0,0,0x0) | 63 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='starbase', ident=4) at z=63 is at/behind near_plane_su=1 |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,17,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ large 120x44 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-28,0,176x44) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (-5678,-938,493x123) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-52,9,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ large 120x44 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (0,0,0x0) | 63 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='starbase', ident=4) at z=63 is at/behind near_plane_su=1 |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,21,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(43, -32, 58)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-29,0,208x52) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (-6706,-1108,582x146) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-57,11,9x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### wormhole+starbase+ships @ huge 150x52 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 118 | box class 2 (18x9) | 9x4 | 8 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (0,0,0x0) | 63 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='starbase', ident=4) at z=63 is at/behind near_plane_su=1 |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,25,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(38, 25, 35)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-417,-25,900x80) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (25,21,5x1) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (-147,-161,72x15) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-35,18,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ standard 67x30 -- depth_layered_anchor

camera position `(38, 25, 46)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-57,7,180x16) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (33,15,1x1) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (-15,-32,19x4) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,15,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(38, 25, 35)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-497,-30,1080x96) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (33,26,6x1) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (-173,-193,86x18) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-39,22,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ wide 87x36 -- depth_layered_anchor

camera position `(38, 25, 46)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-47,10,180x16) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (43,18,1x1) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (-5,-29,19x4) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,18,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ large 120x44 -- fixed_fov_perspective

camera position `(38, 25, 35)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-600,-37,1320x117) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (48,31,7x2) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (-205,-236,106x22) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-40,27,7x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ large 120x44 -- depth_layered_anchor

camera position `(38, 25, 46)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-30,14,180x16) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (59,22,1x1) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (12,-25,19x4) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,22,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(38, 25, 35)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-705,-44,1560x139) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (60,37,8x2) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (-238,-279,125x26) | 55 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (-43,32,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### belt+port+ships @ huge 150x52 -- depth_layered_anchor

camera position `(38, 25, 46)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:531`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:531 | planet | belt | continuous | (90,16,1440) | - | (-15,18,180x16) | 47 | box class 1 (80x14) | 16x3 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:531 | (74,26,1x1) | 387 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (27,-21,19x4) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,26,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+port+wreck+traffic @ standard 67x30 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,2,100x25) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (26,20,4x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (186,98,22x5) | 299 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (121,23,9x2) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,51,14x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+wreck+traffic @ standard 67x30 -- depth_layered_anchor

camera position `(-152, 69, 298)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,96x24) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (33,15,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (201,107,24x5) | 299 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (43,16,1x1) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,31,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+wreck+traffic @ wide 87x36 -- fixed_fov_perspective

camera position `(-152, 69, 233)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (35,24,5x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (226,119,26x5) | 299 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (148,28,11x2) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (69,61,17x3) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+wreck+traffic @ wide 87x36 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (43,18,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 299 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=280966382190528449) at z=299 is at/behind near_plane_su=1 |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (55,19,1x1) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (55,38,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+wreck+traffic @ large 120x44 -- fixed_fov_perspective

camera position `(-152, 69, 234)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,149x37) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (49,30,6x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (287,147,32x7) | 299 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (189,34,14x3) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (92,75,21x4) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+wreck+traffic @ large 120x44 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (59,22,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 299 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=280966382190528449) at z=299 is at/behind near_plane_su=1 |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (72,23,1x1) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (72,42,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+wreck+traffic @ huge 150x52 -- fixed_fov_perspective

camera position `(-152, 69, 235)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (-14,3,178x45) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (62,35,7x2) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (348,176,39x8) | 299 | rung 'proposed-rich' (index 0) | 26x6 | 22 | would-accept (pending WP-SC06 hard rules) |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (228,41,17x3) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (113,89,24x5) | 337 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+wreck+traffic @ huge 150x52 -- depth_layered_anchor

camera position `(-152, 69, 304)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9101`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9101 | planet | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 305 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9101 | (74,26,1x1) | 645 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:280966382190528449 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 299 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=280966382190528449) at z=299 is at/behind near_plane_su=1 |
| ship:2899285926333283485 | ship | ship | ladder | (12,5,60) | - | (87,27,1x1) | 385 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (87,46,8x2) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### derelict-base+ships @ standard 67x30 -- fixed_fov_perspective

camera position `(-113, 19, 3)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (312,-60,28x6) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (26,17,4x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### derelict-base+ships @ standard 67x30 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (19,11,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (33,15,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### derelict-base+ships @ wide 87x36 -- fixed_fov_perspective

camera position `(-113, 19, -9)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (315,-55,27x6) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (35,20,5x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### derelict-base+ships @ wide 87x36 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (29,14,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (43,18,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### derelict-base+ships @ large 120x44 -- fixed_fov_perspective

camera position `(-113, 19, -25)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (326,-50,26x6) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (50,25,6x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### derelict-base+ships @ large 120x44 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (46,18,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (59,22,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### derelict-base+ships @ huge 150x52 -- fixed_fov_perspective

camera position `(-113, 19, -41)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (337,-44,26x5) | 55 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (63,29,7x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### derelict-base+ships @ huge 150x52 -- depth_layered_anchor

camera position `(-113, 19, 62)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `starbase:4`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| starbase:4 | starbase | orbital | ladder | (14,7,98) | - | (61,22,28x7) | 63 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:4091162512351261573 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 55 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4091162512351261573) at z=55 is at/behind near_plane_su=1 |
| ship:17830671323189067475 | ship | ship | ladder | (12,5,60) | - | (74,26,1x1) | 337 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### entity+planet @ standard 67x30 -- fixed_fov_perspective

camera position `(3, 82, 284)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-8,6,83x17) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet @ standard 67x30 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-1,8,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet @ wide 87x36 -- fixed_fov_perspective

camera position `(3, 82, 283)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-6,8,98x20) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet @ wide 87x36 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (9,11,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet @ large 120x44 -- fixed_fov_perspective

camera position `(3, 82, 284)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-1,9,122x25) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet @ large 120x44 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (26,15,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet @ huge 150x52 -- fixed_fov_perspective

camera position `(3, 82, 283)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (4,11,141x29) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet @ huge 150x52 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (41,19,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ standard 67x30 -- fixed_fov_perspective

camera position `(3, 82, 284)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-8,6,83x17) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ standard 67x30 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-1,8,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ wide 87x36 -- fixed_fov_perspective

camera position `(3, 82, 283)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-6,8,98x20) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ wide 87x36 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (9,11,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ large 120x44 -- fixed_fov_perspective

camera position `(3, 82, 284)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (-1,9,122x25) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ large 120x44 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (26,15,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ huge 150x52 -- fixed_fov_perspective

camera position `(3, 82, 283)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (4,11,141x29) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### entity+planet+hostile-ship @ huge 150x52 -- depth_layered_anchor

camera position `(3, 82, 332)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `entity:900`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| entity:900 | entity | entity | continuous | (34,14,476) | - | (41,19,68x14) | 333 | box class 1 (26x10) | 16x6 | 14 | anchor |
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,0,0x0) | 172 | box class 2 (28x14) | 17x8 | 12 | would-reject: SceneKey(tag='planet', ident=9401) at z=172 is at/behind near_plane_su=1 |
| ship:4609209796538076908 | ship | ship | ladder | (12,5,60) | - | (0,0,0x0) | 34 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-reject: SceneKey(tag='ship', ident=4609209796538076908) at z=34 is at/behind near_plane_su=1 |

### discovery:wreck (generated, sensor-gated) @ standard 67x30 -- fixed_fov_perspective

camera position `(-142, -53, 38)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (12,11,43x8) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### discovery:wreck (generated, sensor-gated) @ standard 67x30 -- depth_layered_anchor

camera position `(-142, -53, 82)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (17,12,32x6) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### discovery:wreck (generated, sensor-gated) @ wide 87x36 -- fixed_fov_perspective

camera position `(-142, -53, 29)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (22,14,43x8) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### discovery:wreck (generated, sensor-gated) @ wide 87x36 -- depth_layered_anchor

camera position `(-142, -53, 82)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (27,15,32x6) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### discovery:wreck (generated, sensor-gated) @ large 120x44 -- fixed_fov_perspective

camera position `(-142, -53, 39)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (28,16,64x12) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### discovery:wreck (generated, sensor-gated) @ large 120x44 -- depth_layered_anchor

camera position `(-142, -53, 82)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (44,19,32x6) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### discovery:wreck (generated, sensor-gated) @ huge 150x52 -- fixed_fov_perspective

camera position `(-142, -53, 31)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (43,20,64x12) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### discovery:wreck (generated, sensor-gated) @ huge 150x52 -- depth_layered_anchor

camera position `(-142, -53, 82)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `wreck:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (59,23,32x6) | 83 | box class 1 (16x7) | 8x4 | 6 | anchor |

### planet+port+runtime-wrecks @ standard 67x30 -- fixed_fov_perspective

camera position `(153, -5, 100)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-17,2,100x25) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (26,20,4x1) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+runtime-wrecks @ standard 67x30 -- depth_layered_anchor

camera position `(153, -5, 165)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,96x24) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (33,15,1x1) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+runtime-wrecks @ wide 87x36 -- fixed_fov_perspective

camera position `(153, -5, 100)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (35,24,5x1) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+runtime-wrecks @ wide 87x36 -- depth_layered_anchor

camera position `(153, -5, 171)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (43,18,1x1) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+runtime-wrecks @ large 120x44 -- fixed_fov_perspective

camera position `(153, -5, 101)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,149x37) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (49,30,6x1) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+runtime-wrecks @ large 120x44 -- depth_layered_anchor

camera position `(153, -5, 171)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (59,22,1x1) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+runtime-wrecks @ huge 150x52 -- fixed_fov_perspective

camera position `(153, -5, 102)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-14,3,178x45) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (62,35,7x2) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+port+runtime-wrecks @ huge 150x52 -- depth_layered_anchor

camera position `(153, -5, 171)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| port:64 | port | orbital | ladder | (14,7,98) | planet:9401 | (74,26,1x1) | 512 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |
| wreck:22 | wreck | wreck | continuous | (16,6,96) | - | (0,0,0x0) | 83 | box class 1 (16x7) | 8x4 | 6 | would-reject: SceneKey(tag='wreck', ident=22) at z=83 is at/behind near_plane_su=1 |

### planet+starbase(arbitrary-orbit) @ standard 67x30 -- fixed_fov_perspective

camera position `(153, -5, 100)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-17,2,100x25) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (-73,5,12x3) | 235 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase(arbitrary-orbit) @ standard 67x30 -- depth_layered_anchor

camera position `(153, -5, 165)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,96x24) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (13,12,2x1) | 235 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase(arbitrary-orbit) @ wide 87x36 -- fixed_fov_perspective

camera position `(153, -5, 100)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (-85,5,15x4) | 235 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase(arbitrary-orbit) @ wide 87x36 -- depth_layered_anchor

camera position `(153, -5, 171)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (17,15,3x1) | 235 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase(arbitrary-orbit) @ large 120x44 -- fixed_fov_perspective

camera position `(153, -5, 101)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-15,3,149x37) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (-98,7,18x5) | 235 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase(arbitrary-orbit) @ large 120x44 -- depth_layered_anchor

camera position `(153, -5, 171)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (34,19,3x1) | 235 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase(arbitrary-orbit) @ huge 150x52 -- fixed_fov_perspective

camera position `(153, -5, 102)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (-14,3,178x45) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (-113,8,22x5) | 235 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |

### planet+starbase(arbitrary-orbit) @ huge 150x52 -- depth_layered_anchor

camera position `(153, -5, 171)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `planet:9401`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| planet:9401 | planet | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 172 | box class 2 (28x14) | 17x8 | 12 | anchor |
| starbase:4 | starbase | orbital | ladder | (14,7,98) | planet:9401 | (49,23,3x1) | 235 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ standard 67x30 -- fixed_fov_perspective

camera position `(11, 45, -21)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (-16,20,7x2) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (21,12,24x5) | 39 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (213,-5,14x3) | 80 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (-71,55,7x2) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (-25,13,7x1) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ standard 67x30 -- depth_layered_anchor

camera position `(11, 45, 38)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (32,15,1x1) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (21,12,24x5) | 39 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (96,7,5x1) | 80 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (31,16,1x1) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (32,14,1x1) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ wide 87x36 -- fixed_fov_perspective

camera position `(11, 45, -33)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (-13,24,8x2) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (31,15,24x5) | 39 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (236,-4,15x3) | 80 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (-75,64,8x2) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (-23,15,8x2) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ wide 87x36 -- depth_layered_anchor

camera position `(11, 45, 38)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (42,18,1x1) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (31,15,24x5) | 39 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (106,10,5x1) | 80 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (41,19,1x1) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (42,17,1x1) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ large 120x44 -- fixed_fov_perspective

camera position `(11, 45, -23)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (-12,30,11x2) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (43,18,34x7) | 39 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (317,-7,21x4) | 80 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (-93,81,11x2) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (-25,19,10x2) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ large 120x44 -- depth_layered_anchor

camera position `(11, 45, 38)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (59,22,1x1) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (48,19,24x5) | 39 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (123,14,5x1) | 80 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (57,23,1x1) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (59,21,1x1) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ huge 150x52 -- fixed_fov_perspective

camera position `(11, 45, -35)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (-5,35,12x2) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (58,22,34x7) | 39 | rung 'proposed-rich' (index 0) | 26x6 | 22 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (347,-5,22x5) | 80 | rung 'proposed-mid' (index 1) | 15x4 | 10 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (-95,92,12x2) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (-20,23,11x2) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### hostility-ordering @ huge 150x52 -- depth_layered_anchor

camera position `(11, 45, 38)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `ship:4834297406759931817`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| ship:5124953552923901438 | ship | ship | ladder | (12,5,60) | - | (74,26,1x1) | 176 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:4834297406759931817 | ship | ship | ladder | (12,5,60) | - | (63,23,24x5) | 39 | rung 'proposed-mid' (index 1) | 15x4 | 10 | anchor |
| ship:17811398839952431149 | ship | ship | ladder | (12,5,60) | - | (138,18,5x1) | 80 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:3780958429964456802 | ship | ship | ladder | (12,5,60) | - | (72,27,1x1) | 174 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |
| ship:16382782393866022688 | ship | ship | ladder | (12,5,60) | - | (74,25,1x1) | 190 | rung 'proposed-thin' (index 2) | 7x2 | 3 | would-accept (pending WP-SC06 hard rules) |

### cost-pressure(nebula-anchor) @ standard 67x30 -- fixed_fov_perspective

camera position `(43, -32, 71)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-43,-4,153x38) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

### cost-pressure(nebula-anchor) @ standard 67x30 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-27,0,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

### cost-pressure(nebula-anchor) @ wide 87x36 -- fixed_fov_perspective

camera position `(43, -32, 70)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-47,-5,180x45) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

### cost-pressure(nebula-anchor) @ wide 87x36 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (55 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-17,3,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

### cost-pressure(nebula-anchor) @ large 120x44 -- fixed_fov_perspective

camera position `(43, -32, 70)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-50,-6,220x55) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

### cost-pressure(nebula-anchor) @ large 120x44 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (0,7,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

### cost-pressure(nebula-anchor) @ huge 150x52 -- fixed_fov_perspective

camera position `(43, -32, 70)`, aim_x `0`, 64 candidates (64 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (-55,-7,260x65) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

### cost-pressure(nebula-anchor) @ huge 150x52 -- depth_layered_anchor

camera position `(43, -32, 117)`, aim_x `0`, 56 candidates (56 distinct quantised scenes), anchor `discovery:22`

| object | kind | scale_class | art_mode | face(w,h,area) | parent | projected box | depth | art choice | ink_est | cost | decision |
|---|---|---|---|---|---|---|---:|---|---|---:|---|
| discovery:22 | discovery | anchor | continuous | (60,30,1800) | - | (15,11,120x30) | 118 | box class 2 (36x18) | 14x7 | 20 | anchor |

## 5. Cost-pressure illustration (anchor box-class step-down)

Case `cost-pressure(nebula-anchor)`, anchor kind `nebula`, proposed budget 250. Illustrative manual walk of the anchor's box_classes ladder (descending) against the proposed cost budget, stopping at the first class whose render_cost fits — exactly the order plan §2.3/§4.14 describe for the real step-down loop, which WP-SC06's solver performs automatically and never below the class's configured minimum ink extent (never illustrated here as rejecting the anchor).

| box class | box | render_cost | fits budget |
|---:|---|---:|---|
| 0 | 100x50 | 110 | True |
| 1 | 64x32 | 55 | True |
| 2 | 36x18 | 20 | True |

Chosen box class under this illustration: 0.

## 6. Failed-anchor sidebar illustration

Case `planet+ships` at `12x6` (12x6), anchor kind `terrestrial_warm`. min_extent={'width': 6, 'height': 3}, smallest_available={'width': 28, 'height': 14}, would_fit=False.

Illustrative floor check only (plan §4.18's "can fit" bar): at this viewport the anchor's smallest configured box class (28x14) does not clear the viewport, so a real WP-SC06 solver would reject every object to the sidebar and render starfield only (plan §4.17), never a cropped or partial anchor.

## 7. Resize-stability illustration (±1 column, fixed admission set)

- `planet+port+ships` / fixed_fov_perspective: anchor height 30 (87x36) -> 30 (88x36), hysteresis delta 1. A ±1-column resize with an unchanged admission set (WP-SC06's own reposition/admission solve is what actually varies the admitted set — this illustration holds it fixed) should produce a small hysteresis delta; the actual acceptance threshold for "small" is a WP-SC06/solver-tuning decision, not fixed here.
- `planet+port+ships` / depth_layered_anchor: anchor height 30 (87x36) -> 30 (88x36), hysteresis delta 1. A ±1-column resize with an unchanged admission set (WP-SC06's own reposition/admission solve is what actually varies the admitted set — this illustration holds it fixed) should produce a small hysteresis delta; the actual acceptance threshold for "small" is a WP-SC06/solver-tuning decision, not fixed here.

## 8. Open questions for the reviewer

- Single shared `"anchor"` face_extent bucket for planet and every generated discovery kind cannot express per-kind face-area differences (nebula ≫ wormhole > planet, plan §2.2) — flagged in the face_extent_by_scale_class proposal above; needs a WP-SC02 model change (`face_extent_by_kind`), not something calibration numbers alone can fix.
- `region_by_scale_class` proposes one shared region size for ships vs stations; plan §2.5 asks ships to have *wider* placement freedom than stations, which this first-pass proposal does not yet encode (see the region_by_scale_class rationale above).
- "Arbitrary station orbit, including the near or far side" (plan §2.5) is not yet distinguishable from any other flexible placement: `classify_sector`'s stable-hash offset picks one point in the shared orbital region without a near/far concept. The `planet+starbase(arbitrary-orbit)` matrix cell above only proves the station parents correctly to its planet; it does not exercise near/far placement, which likely needs its own region shape or reposition-search concept beyond what `edge/scene/solve.py` (WP-SC06) implements today.
- This tool's per-object `visible_fraction_note` is a hand-computed illustration ('1, assumed unoccluded'), not a call into the real WP-SC06 occlusion pass (`edge/scene/solve.py` now implements one) -- wiring the trace through the actual `solve()` output, rather than this tool's own `frame()`/`project()`-only walk, would give a real occlusion-based figure and is worth doing in a follow-up pass of this tool now that WP-SC06 has landed.
