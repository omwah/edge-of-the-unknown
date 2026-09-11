# WP-SC11 composition-test disposition table

Plan `docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` WP-SC11 requires a checked-in
disposition for every existing composition test when the physical-model composer
becomes the default: carry unchanged as legacy-path regression coverage, restate
against a numbered §4 invariant for the physical model, duplicate so both composers
keep independent coverage, or delete with a written reason.

This is a **module-level** disposition, not a line-by-line one: every test file below
was run against the new default and its actual pass/fail outcome recorded, rather than
predicted. Two tests needed either a fix (not a disposition change) or a fix to the
composer they exercise; both are named explicitly.

| Test module | Disposition | Notes |
|---|---|---|
| `tests/test_ui_snapshots.py` | **Pinned to `composer="legacy"`** via an autouse fixture (`_pin_legacy_composer`) | General UI smoke coverage predating the physical model, not composer-specific. Rebaselining ~72 unrelated snapshots for a visual composer swap was rejected as unreviewable; pinning keeps every baseline meaningful as legacy regression coverage instead. All 72 captures still pass. |
| `tests/test_physical_scene_snapshots.py` | **Unchanged** | Already exercises the physical composer directly via a standalone test app, independent of `SceneArtConfig.composer`/`EdgeApp`. Unaffected by the default flip either way. |
| `tests/test_scene_gallery_ab.py` | **Unchanged** | Renders all three composer variants explicitly by name for the A/B gallery; does not read the app-level default. |
| `tests/test_scene_legacy_parity.py` | **Unchanged** | Measures both composers against each other by name; the one known parity miss (`planet+port+wreck+traffic @ 67x30`, §9.6) is already asserted by name so it can't silently become two. |
| `tests/test_scene_classify.py`, `test_scene_model.py`, `test_scene_solve.py`, `test_scene_frustum.py`, `test_scene_project.py`, `test_scene_paint.py` | **Unchanged, extended** | Pure `edge/scene`/`edge/art/scene_paint` unit coverage, composer-selection-agnostic. Extended in this pass: ship/entity/wormhole `destination` routing coverage (`test_scene_classify.py`), a stardock-vs-port station-kind key test (`test_scene_paint.py`) — both closing real correctness gaps found while wiring the default (see below). |
| `tests/test_station_archetype_art.py` | **Restated** | `station_icon_dimensions`'s two `StationReference`-shape tests were already restated in the prior WP-SC10 commit against the exact-key-match invariant; unaffected by the default flip itself. |
| `tests/test_tui_flow.py::test_sector_title_shows_spatial_id` | **Fixed a real gap, not disposed** | Failed under the flip: the physical-model render path had no sector title/header chrome at all (`edge/tui/widgets.py::_render_physical_scene` now paints the same header/flavor/beacon line and starfield background the legacy composer does, reserving body rows for the physical model exactly as the legacy composer reserves them for `_SceneComposer`). Passes now. |
| `tests/test_tui_flow.py::test_sector_view_caps_ship_sprites_and_keeps_overflow_hailable` | **Fixed a real gap, not disposed** | Failed for the same header-chrome reason (its own assertion needs the header text present) and would separately have exercised a hotspot-routing bug: `edge/scene/classify.py` was building `PhysicalObject.destination` as `"ship:<hash>"`/`"entity:<id>"`/always `"discovery:<id>"` for wormholes, none of which match `ClickableEntry.Picked`'s real "contact"/"player"/"wormhole" vocabulary (`edge/tui/screens/game.py::on_clickable_entry_picked`). Fixed at the source (`classify.py`'s three `_ship_object`/`_entity_object`/`_anchor_discovery_object` destination fields), not papered over in the widget seam, so every consumer of `PhysicalObject.destination` gets the fix. Passes now. |
| `tests/test_tui_flow.py` (all other cases) | **Unchanged** | Full 62-case module run green against the new default with no other changes needed. |
| Legacy-composer-only config keys `scene.max_ships_shown` / `scene.ship_face_inward_chance` | **Kept, not deleted** | Per the plan's revised WP-SC11: these remain live, legacy-composer-only settings for as long as the legacy composer ships. Not disposed of; no test references them changed. |

## Gaps found and fixed while wiring the default (not pre-existing composition-test
failures — these were latent bugs the flip exposed for the first time)

1. **No sector header/starfield in the physical path.** `edge.art.scene_paint.paint_grid`
   deliberately paints no starfield (plan §3: that is the art/TUI seam's job), and no
   `PhysicalObject` models the sector title/flavor/beacon line at all (it is chrome, not
   a solver object). `_render_physical_scene` now builds the same starfield base
   (`edge.tui.art_adapter`) and stamps the same header/flavor/beacon text the legacy
   composer does, then solves/paints the physical model only into the remaining body
   rows (offsetting painted content and hotspots by the header height) — matching plan
   §2.4's "Select responsive structural modes from the actual drawable scene viewport,
   after header/UI subtraction".
2. **Wrong click-routing vocabulary for ships/entity/wormholes.** See the disposition
   row above. Also fixed: `StationKey`/`build_station_reference` published a Stardock
   under the `station_kind` `"port"` (mirroring `SceneKey.tag`, which the plan
   deliberately keeps shared for ships/starbases per §2.4's "Stardock is a port-kind
   subtype"), but every docked-header consumer asks for `"stardock"` by name
   (`edge/tui/station_art.py`, `screens/stardock.py`). `build_station_reference` now
   derives the public station kind from `ladder_key.subtype` instead of `SceneKey.tag`
   (`edge.art.scene_paint._public_station_kind`), covered by a new
   `test_scene_paint.py` test.
3. **`archetype_id=""` ladder-key crash.** Found and fixed during WP-SC10 (see that
   plan section and `SECTOR_SCENE_BENCHMARK_BASELINE.md`), not this pass — listed here
   only because it is the same class of gap (a real production path the physical
   composer had never actually been exercised against end-to-end until it became the
   default).

## What this table does not cover

Per-assertion coverage of every individual test function's exact expectations was not
re-derived line by line; the module-level run-and-record above is what the time budget
for this pass allowed. If a future change finds a composition test whose *intent*
silently stopped matching either composer, that is grounds to extend this table, not
evidence this table is wrong.
