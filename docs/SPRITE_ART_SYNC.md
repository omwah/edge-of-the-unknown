# Sprite Art Sync — keeping the vendored library and assets current

**Companion doc:** `docs/SPRITE_ART_MIGRATION.md` (how the vendored code got here).

`edge/art/sprite_art/` and `edge/art/assets/` are **vendored copies** of code and
data authored in a separate repository. This document is the record of that
relationship: what is copied, how to re-copy it, and — most importantly — which
contracts break *silently* when upstream changes.

---

## 1. Provenance

**Upstream:** `sprite-art-designer` (Edge Art Designer), a Python 3.12 / Pixi
Textual application for authoring procedural Unicode sprite art.

**Baseline:** `08192b9eab3928d31f8e9ed37d6644095652a768` (2026-08-13). Its parent
`19bc02e` is where `sprite-art-designer/docs/RUNTIME_PACKAGE_SPLIT.md` landed,
which is the prerequisite for the initial vendoring (see
`docs/SPRITE_ART_MIGRATION.md`); `08192b9` adds only that plan document and
touches no vendored file. Update this line, and `edge/art/sprite_art.manifest`,
on every sync.

The library was `bf03254` (2026-08-12) when the migration was planned, before
that split existed; do not vendor from that commit.

Two rules:

1. **Edge never imports from the designer repo.** There is no path dependency, no
   submodule, no editable install. The relationship is copy-only and
   one-directional: upstream → Edge.
2. **Edge is not a place to edit sprite art.** Sprite YAML and palette values are
   authored in the designer TUI and flow down. A local edit to a vendored file
   will be silently reverted by the next sync — and the `--check` guard (§3) will
   fail before that, which is the point.

The designer repo treats Edge as read-only reference material in the same way.
Neither repo modifies the other.

---

## 2. What is copied

| Upstream path | Edge path | How |
|---|---|---|
| `src/sprite_art/` | `edge/art/sprite_art/` | verbatim, whole directory |
| `assets/palettes.yaml` | `edge/art/assets/palettes.yaml` | verbatim |
| `assets/sprites/` | `edge/art/assets/sprites/` | verbatim (15 YAML files) |
| `tests/test_sprite_art.py` | `tests/test_vendored_sprite_art.py` | verbatim except the `ROOT`/`ASSETS` constants (`:48-49`) |
| `tests/fixtures/tier_renders.json` | `tests/fixtures/tier_renders.json` | verbatim |

**Deliberately not vendored:**

| Upstream path | Why |
|---|---|
| `src/sprite_art_designer/` | the Textual editor; needs `textual`, `textual-colorpicker` |
| `src/sprite_art_authoring/` | REXPaint interchange and authoring-time rotation; no game-side consumer |
| `assets/rexpaint/` | editor font atlas and glyph mapping tables |
| `tools/` | dev-time importers and generators; several read an Edge checkout |
| `tests/test_tui.py`, `tests/test_render_ships.py`, `tests/test_sprite_art_authoring.py` | editor and authoring tests |

If a future upstream change makes `sprite_art` import `sprite_art_authoring`, the
split has regressed and the vendoring seam is broken — `sprite_art` must stay
runtime-only. Treat that as a blocking upstream bug, not something to work around
by vendoring more.

Nothing in `sprite_art` needs an import rewrite — all its intra-package imports
are relative. The copy is byte-for-byte, which is what makes `--check` meaningful.

`[tool.ruff] extend-exclude = ["edge/art/sprite_art"]` in `pyproject.toml` exists
for this reason: Edge's linter must never reformat vendored code, or every sync
becomes a merge.

---

## 3. `scripts/sync_sprite_art.py`

The sync tool. Two modes:

```bash
# Re-copy from a designer checkout and rewrite the manifest.
python scripts/sync_sprite_art.py ../sprite-art-designer

# Verify the working tree still matches the manifest. No writes.
python scripts/sync_sprite_art.py --check
```

What it does:

- Copies each row of the §2 table with `--delete` semantics, so a file removed
  upstream is removed here rather than lingering.
- Applies the one permitted edit: repointing `ROOT` / `ASSETS` in the copied test
  file at `edge/art/assets`.
- Writes `edge/art/sprite_art.manifest` — the upstream commit hash, the sync
  date, and a SHA-256 per copied file.
- `--check` recomputes every hash and exits non-zero on any mismatch, printing
  the drifted paths.

A test runs `--check` in CI, so an accidental hand-edit to vendored code fails a
test run rather than becoming invisible local drift.

---

## 4. The contracts that break silently

This is the part a diff will not tell you. Each item below can change upstream
without producing any error in Edge — only wrong output.

### The seed recipe

Both sides build the render RNG from a formatted string, and they must agree:

```python
# sprite_art/render.py:71          # edge/art/generator.py:92
f"{seed}|{sprite.kind}|{sprite.role}"   f"{seed}|{entity_type}|{subtype}"
# + f"|{archetype_id}" when set, on both sides
```

They match **only** while each sprite document's `kind` equals Edge's
`entity_type` and its `role` equals Edge's `subtype`. Ships carry `kind: ship`;
all three stations carry `kind: port` — the stardock is a `port` whose `role` is
`stardock`, matching Edge's `PORT_SUBTYPES` vocabulary.

Renaming `kind` or `role` on any sprite re-rolls that sprite for every seed in
every existing game, with no error and no test failure outside the golden
fixture. This is the single most dangerous upstream edit.

### `id` versus `role`

`available_subtypes()` returns sprite **ids**, and `generate_sprite` resolves by
id — but the seed uses `role`. They coincide in all 15 shipped assets, and the
schema permits them to diverge. If upstream ever ships a sprite whose `id` and
`role` differ, Edge will render it under one name and seed it under another.

### The archetype roster

Exactly 14 ids, pinned in three places upstream (`sprite_art/model.py`
`ARCHETYPE_IDS`, `assets/palettes.yaml`, and the catalog's own validation) and
referenced by Edge's alien roster config (`config/alien_roster_default.yaml`).

Edge keeps **no palette table of its own** — `ARCHETYPE_STYLES` was deleted
during the migration. A sync is therefore the only way archetype colours ever
change in Edge, and `validate_art_coverage` (`edge/tui/art_adapter.py:164`)
checks the roster against the vendored catalog at startup.

### `palettes.yaml` drives discovery art too

**Non-obvious and easy to break.** Edge's nebula, black hole, wormhole, wreck,
and entity painter (`edge/art/discovery.py`) reads its `HullStyle` out of the
same catalog that paints ships and stations:

| `HullStyle` field | Catalog source |
|---|---|
| `bright` / `mid` / `dark` / `facet` | `surface` slots 0 / 1 / 2 / 3 |
| `top` | the `beacon` set |
| `bottom` | the `engine` set |
| `window` | the `window` set |

So retuning an archetype's `surface` colours in the designer to improve a *hull*
silently restyles that archetype's *nebulae* on the next sync. The `weapons` and
`defensive` sets are the only ones discovery ignores.

Two further traps: dropping a `surface` colour below four entries makes
`color_for_slot` fall back to slot 0, which collapses `facet` onto `bright` and
makes facet detail glyphs invisible. And renaming or removing an archetype breaks
`style_for` outright.

**Nothing upstream tests this coupling.** It is Edge's to guard —
`tests/test_sprite_seam.py` and `tests/test_discovery_art.py` are where it
surfaces.

### Tier ladders versus `SceneArtConfig` boxes

**This is the contract that bit hardest.** The library selects a tier by the
requested **height** alone (`render._select_tier`), then centre-crops that tier's
natural width down to the requested width (`render._fit_grid`). A box narrower
than the selected tier does not yield a smaller sprite — it yields the *middle*
of the art. For a ship that is the repeating hull band with prow and drive cut
away (a one-row band on screen); for an ordinary port, a bare mast.

Edge absorbs this at its own seam rather than upstream: `edge/art/sprites.py` →
`fit_box` walks the ladder richest-first for the top rung fitting the box on
**both** axes, and `generate_sprite` renders at that rung's natural size and pads
the result into the requested box. **Nothing about this is the designer's
problem** — the ladder is authored as a scale ladder and is correct as authored;
it is Edge's job to ask for a box that clears a whole rung.

So a sync can break the art **without changing a line of Edge code**: retuning a
section repeat upstream moves a rung's natural width, and a rung that no longer
clears Edge's cap silently steps the render down (or, if nothing clears it,
crops). The ladders as vendored today:

| Sprite | Ladder (w×h) | Edge cap | Selected at the cap |
|---|---|---|---|
| ships (horizontal) | ~`46×7`, ~`34×5`, `17×3` | 46×7 | `full` |
| `trading_port` | `11×12`, `11×7`, `7×6`, `7×3` | 28×12 | `full` |
| `starbase` | `11×14`, `11×8`, `5×5`, `5×3` | 33×14 | `full` |
| `stardock` | `15×15`, `15×11`, `9×6`, `9×3` | 38×16 | `full` |

Every kind reaches its top rung at the shipped caps, so **the ladder — not the config
— is what now limits sprite size**, and a port is never wider than 11 columns however
large the terminal. That is a live constraint rather than a curiosity: the 2026-08-16
scene ratings pass reported *"port too small"* / *"ships overpower port"* across nine
cells of the review matrix, and Edge answered it from the ship's side (stepping distant
traffic down its ladder, `docs/SECTOR_SCENE_COMPOSITION.md` §2.1) because there was no
richer port rung to reach for. **A new port tier authored upstream is the actual fix**
— see that note's §8.1 for the Edge-side follow-up a sync carrying one must do.

`tests/test_sprite_seam.py::test_every_subtype_renders_a_whole_tier_at_its_scene_box`
asserts every vendored subtype clears a whole rung at its configured cap. **Run
it after every sync** — it is the guard that turns this silent failure into a
loud one, and it lives in Edge because the caps do.

Upstream also has `test_every_station_tier_fits_the_boxes_edge_requests`, which
hardcodes the boxes Edge requests. Those numbers go stale whenever the `scene:` block
moves — check them against the table above rather than trusting them. Changing the
`scene:` block still deserves a word to the art side, or a run of
`tools/import_edge_ports.py <edge-checkout> --audit` there — but Edge's own seam
test is the authority, since it reads the caps out of `SceneArtConfig` directly.

### New sprites arrive unreachable

A new ship YAML upstream appears in `available_subtypes()` and the in-game sprite
gallery on the next sync, but stays unreachable in play until a `ship_classes`
entry names it via `art_subtype`.

Eight vendored ships are already in exactly this state by design:
`needle_picket`, `falsehold_raider`, `junction_pinnace`, `radiant_lance`,
`hearth_freighter`, `pearl_shell`, `marrow_dart`, `broadside_citadel`.

**The gallery is not evidence that a sprite is in use.** The two lists are
expected to differ.

### Schema versions

`SPRITE_SCHEMA_VERSION = 4`, `PALETTE_SCHEMA_VERSION = 2`. The library rejects
any other version at load, so a mismatch fails loudly — but only if you sync both
halves. **Never sync the library without the assets, or the assets without the
library.** A schema migration upstream means both move together.

---

## 5. Sync runbook

1. Pull the designer checkout to the commit you intend to vendor.
2. `python scripts/sync_sprite_art.py ../sprite-art-designer`
3. `git diff --stat` — read what actually moved. Asset-only diffs are routine;
   a diff inside `edge/art/sprite_art/` deserves a look at upstream's changelog
   for anything in §4.
4. `pixi run check`
5. `pytest tests/test_discovery_art.py` — the palette-coupling canary (§4).
6. `pytest tests/test_sprite_seam.py` — the tier-ladder canary (§4). A retuned
   section repeat upstream can move a rung past a `scene:` cap, and this is the
   only place that fails when it does.
7. `python -m edge.tui.scene_preview` — the ladders in situ, across every
   composition and terminal tier. A ship that reads as a one-row band or a port
   that reads as a bare mast at a *large* viewport means a rung moved; check §4
   before touching the caps.
8. `pixi run art-gen`, and the in-game sprite gallery, for the visual delta.
9. Note any new sprite ids. They are inert until someone adds a `ship_classes`
   entry with `art_subtype`; that is a gameplay decision, not part of a sync.
10. Update the baseline commit in §1 of this document.
