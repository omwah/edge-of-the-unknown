# Sprite Art Migration — replacing the band grammar with `sprite_art`

**Status:** implemented.
**Companion docs:** `docs/SPRITE_ART_SYNC.md` (what stays in sync afterwards),
`sprite-art-designer/docs/EDGE_INTEGRATION.md` (the upstream view of this seam).

This document is a complete handoff. It assumes no prior knowledge of either
repository and names every file, line, and contract the change touches.

> **Prerequisite: `sprite-art-designer/docs/RUNTIME_PACKAGE_SPLIT.md` must land
> first.** That change extracts `rexpaint.py` and `transform.py` — ~500 lines of
> editor-only code — out of the `sprite_art` package into a sibling
> `sprite_art_authoring`. Doing it first means Edge vendors a package that is
> already runtime-only: the copy is a clean directory sync with nothing to strip,
> and the copied test file needs no hand-editing beyond two path constants.
>
> **Before starting, verify it has landed** in the designer checkout you are
> vendoring from:
>
> ```bash
> test ! -e src/sprite_art/rexpaint.py && test ! -e src/sprite_art/transform.py \
>   && echo "split has landed" || echo "STOP — run RUNTIME_PACKAGE_SPLIT.md first"
> ```
>
> If it has not landed, stop and do that first. This document assumes throughout
> that `sprite_art` is ~2000 lines whose entire third-party surface is
> `rich.text`, `rich.cells`, and `yaml`.

---

## 1. What changes, and why

Edge generates ship and station art from **hand-written Python grammars**:

| File | Lines | What it holds |
|---|---|---|
| `edge/art/ship.py` | 567 | `SHIP_GRAMMAR` — asymmetric horizontal sections, tail → nose |
| `edge/art/port.py` | 454 | `PORT_GRAMMAR` — left-half vertical bands, mirrored at render time |
| `edge/art/hull.py` | 382 | shared `Part`/`Slot` types, glyph-flip table, archetype palettes, painter |

`sprite-art-designer` now has a reusable library (`src/sprite_art/`, Rich +
PyYAML only) plus a schema-v4 asset tree of **12 ship and 3 station YAML
documents**, authored in a dedicated TUI. This change retires the grammars
entirely and renders those assets instead.

**There is no backwards compatibility and no dual code path.** The three modules
above are deleted. Do not add a feature flag, a fallback to the old grammar, or a
"legacy" subtype.

### This is an intentional visual migration

Ship and station art **will look different**. Upstream is explicit about this
(`EDGE_INTEGRATION.md` §"Roles and subtypes" and §"Divergences"). Expected
deltas:

- The four original ship roles (`fighter`, `transport`, `warship`,
  `capital_warship`) are native Edge Art Designer compositions, not byte-for-byte
  translations of the old grammar.
- `starbase` at 22×9 is **glyph-identical** to today for every archetype. This is
  the one place you can diff against the old renderer.
- `trading_port` renders its 11×7 silhouette at the shipped caps. It only drops to
  the small-box mast rung when the scaled box falls under 7 rows, which is the
  ladder working as intended rather than a rendering bug — do not "fix" it in
  Edge, and do not confuse it with the cropping bug §4 describes.
- Ships and stations fill their box in **discrete tier steps** and centre, rather
  than tiling a repeatable slot continuously to the exact requested height.

Discovery art (nebula, black hole, wormhole, wreck, entity) must **not** change —
see §6.

---

## 2. Vendoring layout

Copy, do not import. Edge must have no build-time or runtime dependency on the
designer repository.

```text
sprite-art-designer/src/sprite_art/       ->  edge/art/sprite_art/
sprite-art-designer/assets/palettes.yaml  ->  edge/art/assets/palettes.yaml
sprite-art-designer/assets/sprites/       ->  edge/art/assets/sprites/
```

Three things to know:

1. **No import edits are needed.** Every intra-package import in `sprite_art` is
   relative (`from .model import …`), and no module inside it ever writes
   `import sprite_art`. The package re-nests as `edge.art.sprite_art` unchanged.
   (`EDGE_INTEGRATION.md:22` says to "adjust relative imports"; that line is
   stale — ignore it.)
2. **Assets are read from disk, not embedded.** There is no `importlib.resources`
   use and no `Path(__file__)` anywhere in `sprite_art`. The caller supplies the
   asset root, so the `assets/` tree must exist beside the vendored package at
   runtime.
3. **Do not copy `assets/rexpaint/` or `src/sprite_art_authoring/`.** The former
   is the editor's font atlas and glyph mapping tables; the latter is the
   authoring package the prerequisite split extracted. Neither has a game-side
   consumer, and nothing left in `sprite_art` imports them.

`load_sprite_directory` does a recursive `rglob("*.yaml")`, so the
`ships/` and `ports/` subfolders are presentation only — sprite ids must be
unique across the whole tree, and a duplicate raises `SpriteValidationError` at
load.

---

## 3. The loader

New file, `edge/art/sprites.py`:

```python
"""The vendored sprite library, loaded once from the asset tree beside it."""

from pathlib import Path

from edge.art.sprite_art import SpriteLibrary

SPRITES = SpriteLibrary.from_assets(Path(__file__).parent / "assets")
```

Keep this in its own module rather than as a global inside `generator.py`:
`edge/spacebattle/app.py` needs the library (§7) and should not have to import
the planet, terrain, and starfield generators to get it.

This module grew into the Edge-side **seam** over the vendored library. Besides
`SPRITES` it holds `fit_box` and `pad_to` (§4) — the two halves of turning a
caller's available space into a box the library renders whole. Everything Edge
knows about the tier ladder lives here; nothing outside it should reason about
tiers.

`SpriteLibrary.from_assets` reads `<root>/sprites/` and `<root>/palettes.yaml`
and validates both on load, so a malformed asset fails at import time with an
actionable error rather than at first render.

---

## 4. Rewriting `edge/art/generator.py`

The current file is 119 lines. Changes, in order:

**Remove** the grammar imports and globals:

```python
from edge.art.port import PortGenerator, PORT_SUBTYPES   # :11  — delete
from edge.art.ship import ShipGenerator, SHIP_SUBTYPES   # :12  — delete
from edge.art.hull import ARCHETYPE_STYLES               # :7   — delete
_PORT_GEN = PortGenerator()                              # :20  — delete
_SHIP_GEN = ShipGenerator()                              # :21  — delete
```

**`available_subtypes`** (`:36-39`) — the `port` and `ship` branches become:

```python
if entity_type == "port":
    return list(SPRITES.available_subtypes("port"))
if entity_type == "ship":
    return list(SPRITES.available_subtypes("ship"))
```

The `kind` argument matters: without it the call returns ships *and* stations in
one list. Results are sorted sprite ids.

**`available_archetypes`** (`:47`) — reads the vendored catalog instead of the
deleted `ARCHETYPE_STYLES`:

```python
return sorted(SPRITES.palettes.archetypes)
```

There is no `"default"` alias to filter out — the catalog holds exactly the 14
real archetypes, with `fallback_archetype` naming the fallback separately.

### The RNG hazard — read this before touching the dispatch

`generate_sprite` builds an RNG at `:92-95` and hands **the object** to every
generator:

```python
rng_seed = f"{seed}|{entity_type}|{subtype}"
if archetype_id:
    rng_seed += f"|{archetype_id}"
rng = random.Random(rng_seed)
```

`sprite_art` does not accept an RNG. It re-derives one internally from the raw
integer seed, using the *same* recipe (`sprite_art/render.py:63-81`, the string itself at `:71`):

```python
rng_seed = f"{seed}|{sprite.kind}|{sprite.role}"
if archetype_id:
    rng_seed += f"|{archetype_id}"
```

So the ship and port branches must pass **`seed`, not `rng`**:

```python
if entity_type == "port":
    return SPRITES.generate_port(subtype, seed, width, height, archetype_id)

if entity_type == "ship":
    return SPRITES.generate_ship(subtype, seed, width, height, archetype_id, facing)
```

(Shown here reduced to the seed point. The shipped branches wrap these in the fit
seam — see "The requested box is a *bound*" below.)

Keep the `rng` construction — terrain, planet, starfield, discovery, and static
still consume it.

**The load-bearing invariant:** the two recipes agree only while each sprite
document's `kind` equals Edge's `entity_type` and its `role` equals Edge's
`subtype`. All 12 ships carry `kind: ship`; all three stations carry `kind: port`
— including the stardock, which is a `port` whose `role` is `stardock`. Renaming
either field upstream silently re-rolls every sprite in the game with no error.

One asymmetry worth knowing: ship renders burn **two historical colour draws**
before selecting variants (`render.py:76-80`), preserving the draw discipline the
converted grammars were authored against. Station streams are clean. This is
internal to the library, but it explains why ship and station seeds behave
differently if you ever compare streams.

### The requested box is a *bound*, not a size

The ship and port branches must not hand their `width`/`height` straight to the
library. It selects a tier by the requested **height** alone, then centre-crops
that tier's natural width to the requested width — so a box narrower than the
selected tier returns the middle of the art with the ends cut off. Ships came out
as a one-row hull band and ordinary ports as a bare mast for exactly this reason.

`edge/art/sprites.py` holds both halves of the seam — `fit_box` resolves the box
to the richest rung fitting it on **both** axes, and `pad_to` puts the render back
into the caller's box. The dispatch composes them:

```python
if entity_type == "ship":
    fw, fh = fit_box("ship", subtype, max_width=width, max_height=height,
                     archetype_id=archetype_id, facing=facing)
    return pad_to(
        SPRITES.generate_ship(
            subtype, seed, min(fw, width), min(fh, height), archetype_id, facing),
        width, height)
```

Doing it here rather than at each call site fixes the scene composer, the docked
headers, the encounter panel, the sprite gallery, the space-battle station art,
and `art-gen` in one place, and keeps every caller's contract that the returned
`Text` is exactly `width × height`. The `min(...)` clamps matter only when no rung
fits at all — then the smallest rung is cropped rather than allowed to overflow a
widget that was sized from the request.

The corollary is a **configuration** constraint, not a code one: a `scene:` cap
that clears no rung breaks the art silently. See §10 and
`docs/SECTOR_SCENE_COMPOSITION.md`.

### Caching

Keep the outer `@lru_cache(maxsize=128)` on `generate_sprite`. It still serves
planet, terrain, starfield, discovery, and static. `SpriteLibrary` holds its own
128-entry per-instance LRU, which becomes redundant for ship and port but is
harmless. Do not remove either.

---

## 5. Folding the hull painter into `discovery.py`

`edge/art/hull.py` holds two unrelated things. The grammar dies with
`ship.py`/`port.py`; the **painter** does not, because
`edge/art/discovery.py:15-19` imports it:

```python
from edge.art.hull import (
    HullStyle,
    render_grid,
    style_for,
)
```

Discovery is SDF/noise-based, not grammar-based, and has no `sprite_art`
equivalent. Move these into `discovery.py`:

| Symbol | `hull.py` line |
|---|---|
| `BRIGHT_CHARS`, `DARK_CHARS`, `MID_CHARS`, `HULL_CHARS` | 84–95 |
| `VOID_BG`, `WINDOW_PROB` | 98, 101 |
| `HullStyle` (the dataclass only) | 104 |
| `style_for` (rewritten — see §6) | 242 |
| `render_grid` | 311 |

Delete outright, with no replacement:

`Part` (:41), `Slot` (:56), `GLYPH_FLIP_PAIRS` (:69), `GLYPH_FLIP` (:75),
`ARCHETYPE_STYLES` (:124–239), `flip_row` (:248), `select_grammar` (:255),
`compose_horizontal` (:270).

Then delete `edge/art/hull.py`, `edge/art/ship.py`, and `edge/art/port.py`.

> **Name collision, for grep sanity.** `sprite_art/render.py` defines its *own*
> `BRIGHT_CHARS` / `DARK_CHARS` / `HULL_CHARS` with different membership, for the
> six-set palette's glyph-shading slots. They never interact with discovery's
> copies, but both will now live in the same tree.

---

## 6. One palette table: `palettes.yaml`

`ARCHETYPE_STYLES` — the hardcoded 14-archetype `HullStyle` dict — is **deleted**.
The vendored `palettes.yaml` becomes the only palette table in the game.
`style_for` derives a `HullStyle` from it on demand:

| `HullStyle` field | Source in the catalog |
|---|---|
| `bright` | `surface` slot 0 |
| `mid` | `surface` slot 1 |
| `dark` | `surface` slot 2 |
| `facet` | `surface` slot 3 |
| `top` | the whole `beacon` set |
| `bottom` | the whole `engine` set |
| `window` | the whole `window` set |

`PaletteCatalog.resolve()` already implements exactly the normalization
`style_for` needs — it lowercases and falls back to `fallback_archetype`
(`humanoid_diplomat`), matching the old `"default"` alias behaviour:

```python
@lru_cache(maxsize=32)
def style_for(archetype_id: str | None) -> HullStyle:
    """Resolve an ``archetype_id`` to its discovery palette from the vendored catalog."""
    palette = SPRITES.palettes.resolve(archetype_id)
    surface = palette.color_set("surface")
    return HullStyle(
        bright=surface.color_for_slot(0),
        mid=surface.color_for_slot(1),
        dark=surface.color_for_slot(2),
        facet=surface.color_for_slot(3),
        top=tuple(palette.color_set("beacon").colors),
        bottom=tuple(palette.color_set("engine").colors),
        window=tuple(palette.color_set("window").colors),
    )
```

### This mapping is lossless — discovery art must not change

Verified against **all 14 archetypes across all 7 fields: zero mismatches.**
`palettes.yaml` was derived from `ARCHETYPE_STYLES` value-for-value, and every
archetype carries all four `surface` slots, so no `color_for_slot` fallback ever
fires.

**Deleting the old table therefore leaves nebula, black hole, wormhole, wreck,
and entity art byte-identical.** Treat any visual change in discovery art as a
bug in this migration, not an accepted side effect.

Two details:

- The `weapons` and `defensive` colour sets have no `HullStyle` counterpart.
  Discovery simply does not consume them.
- `HullStyle.top` / `.bottom` / `.window` are tuples that discovery indexes and
  `rng.choice`es (`discovery.py:55-56`, `:353-354`, `:575-576`). Convert the
  catalog's lists with `tuple(...)`, and keep `HullStyle` frozen so it stays
  hashable for the `lru_cache`.

### Prove it, once

Write a **throwaway migration test**, run it, then delete it in the same commit:

1. Pin the current `ARCHETYPE_STYLES` literal values into the test file (copy
   them out of `hull.py` before deleting it).
2. Assert the catalog-derived `HullStyle` equals the pinned value for all 14 ids.
3. Assert a discovery render (`generate_sprite("discovery", …)`) is unchanged for
   a couple of fixed seeds.

Run it while `hull.py` is still in git history so the old values are recoverable.
This converts the claim above into evidence at the one moment it is cheap.

`validate_art_coverage` (`edge/tui/art_adapter.py:164`) now checks the alien
roster against the YAML catalog, making `palettes.yaml` the single source of
truth for which archetypes exist.

---

## 7. Call-site changes

### `edge/tui/art_adapter.py`

`sprite()`, `port_subtype()`, `text_to_cells()`, and `_to_truecolor()` are all
**unchanged**. `ship_entity()` gains the `art_subtype` lookup described in §8.

Note that `_to_truecolor` still matters: the vendored palettes use ANSI colour
names (`cyan`, `bright_yellow`), and Textual would otherwise remap them through
the active theme's ANSI palette.

### Station subtypes are not all reachable through `port_subtype()`

`port_subtype()` is one ternary (`art_adapter.py:97-99`) returning `"stardock"`
or `"trading_port"`. **It can never return `"starbase"`.** Four call sites pass a
subtype literal directly instead:

| Site | Literal | Context |
|---|---|---|
| `edge/tui/widgets.py:1074` | `"starbase"` | sector scene, when the sector has a base |
| `edge/tui/station_art.py:131` | `"starbase"` | docked-header icon |
| `edge/tui/screens/encounter.py:152` | `"starbase"` | base-assault enemy art |
| `edge/tui/screens/stardock.py:121` | `"stardock"` | Stardock exterior header |

**None of these needs changing.** They are listed because an implementer auditing
station coverage by reading `port_subtype()` would conclude the game needs only
two station sprites and skip verifying `starbase` — which is the one station that
should render glyph-identically at 22×9, and the subject of the riskiest existing
test (§9).

### `edge/spacebattle/app.py:521-529` — the consumer that bypasses the adapter

This is the easiest site to miss. It calls the port generator directly, passing
an RNG **object**:

```python
art = PortGenerator().generate(
    _random.Random(self.battle.seed ^ (s.id * 0x9E3779B1)),
    "starbase", s.cls.size * cfg.cell_w, s.cls.size * cfg.cell_h)
```

Rewrite to pass the integer seed — and, because this site does not go through
`generate_sprite`, to repeat the fit seam of §4 by hand:

```python
box_w, box_h = s.cls.size * cfg.cell_w, s.cls.size * cfg.cell_h
fw, fh = fit_box("port", "starbase", max_width=box_w, max_height=box_h)
art = pad_to(
    SPRITES.generate_port(
        "starbase",
        self.battle.seed ^ (s.id * 0x9E3779B1),
        min(fw, box_w), min(fh, box_h),
    ),
    box_w, box_h,
)
```

Both halves are load-bearing. Without `fit_box` the library centre-crops a tier
wider than the footprint; without `pad_to` the art shifts, because
`_blit_station` maps each inked cell to an offset *within* the footprint and
relies on the padding for centring. `fit_box` and `pad_to` both live in
`edge/art/sprites.py` precisely so this site and `generator.py` share one
implementation.

Any integer works — the library stringifies the seed, so negative and very large
values are fine. This site passes no `archetype_id`; leave it that way, it
renders the fallback palette. Drop the now-unused `PortGenerator` import at
`:31`. The surrounding rasterization to `(dx, dy, char, style)` tuples and the
per-station cache are unaffected.

### Sites that need no change

`edge/art/cli.py` and `edge/tui/screens/sprites_gallery.py` both drive off
`available_subtypes()`, so the 8 additional ships appear in the CLI contact
sheets and the in-game gallery automatically. The gallery renders ships at 20×6
and ports at 18×8 (`sprites_gallery.py:85-86`) — neither is a `SceneArtConfig`
box, so include both in the box-fill test (§9).

---

## 8. The 8 extra ship sprites, and the reserved `art_subtype` field

All 12 ship documents are vendored, so `available_subtypes("ship")` returns 12
ids and the sprite gallery shows all of them. **Eight are not reachable from
gameplay, and this migration deliberately leaves them that way:**

`needle_picket`, `falsehold_raider`, `junction_pinnace`, `radiant_lance`,
`hearth_freighter`, `pearl_shell`, `marrow_dart`, `broadside_citadel`.

No `ship_classes` entries are authored for them. This is a decision, not an
oversight — wiring them in is a gameplay and balance change that does not belong
in an art migration.

### Add the routing mechanism now, unused

So the future wiring is a config-only change, add to `ShipClassConfig`
(`edge/core/config.py:402`):

```python
art_subtype: str | None = None  # art sprite id; None routes on `role`
```

and have `art_adapter.ship_entity()` prefer it when set, falling through to
today's `_ROLE_ENTITY` table and keyword scan otherwise. `ship_entity` currently
takes a bare string (`widgets.py:1128` passes `vessel.role`), so pick one:
widen it to accept an optional override, or thread `art_subtype` onto the public
vessel DTO. Populate the field **nowhere** in `config/default.yaml`.

Cover it with one test that sets `art_subtype` on a synthetic ship class and
asserts the resulting sprite differs from the `role`-routed one. A reserved field
with no test rots.

**This is a wire change.** Threading the field onto the vessel DTO adds
`SectorShipDTO.art_subtype`, which moves the protocol fingerprint
(`edge/server/wire.py` → `wire_fingerprint`, which hashes every registered DTO's
ordered field schema). `tests/test_wire.py::test_fingerprint_is_stable` will fail
and tell you the remedy: bump `WIRE_VERSION` (42 → **43** here) and regenerate
`tests/fixtures/wire/fingerprint.txt`. `tests/fixtures/wire/envelopes.json`
carries the version in its three golden envelopes and needs the same bump —
nothing else in it changes, since none of those sample types moved. Do not edit
the fingerprint fixture without bumping the version; the two are checked as a
pair, and a client on the old build must fail the handshake loudly rather than
decode a DTO whose shape it does not share.

### Why a new field rather than widening `role`

`role` is **display plus art routing only** today — verified that nothing in
`edge/core`, `edge/bigbang`, or `edge/server` branches on its value. Widening it
to `role: needle_picket` would work mechanically. But `role` is DESIGN §4's
gameplay taxonomy (fighter / warship / capital_warship / transport / starbase)
and surfaces to the player as the Role column in the Stardock ship list
(`edge/tui/screens/stardock.py:512`). `art_subtype` keeps that column meaningful
and lets two classes share one sprite.

### Future work — explicitly out of scope here

Whoever wires these later authors entries in `config/default.yaml`
`ship_classes:` (after `orbital_platform`, `:761`) as NPC hulls, **omitting
`subsystems`** per the `ShipClassConfig` docstring so the flat scalars serve
directly. Each sprite's authored `description` is the intended source for its
stats — e.g. `needle_picket` is "a lean independent patrol hull with exposed
drive nodes and an oversized sensor prow", implying high `sensor_rating` and low
`hull_max`. Constraints that will apply: every `armament` id must exist in the
`weapons` catalog, and every `defenses` entry must use a valid
`DefenseConfig.type` (`laser_turret` / `armour` / `screens` / `energy_plates` /
`speed_and_size`).

---

## 9. Tests

### Delete

`tests/test_ship_art.py` and `tests/test_port_art.py`. Both are written against
deleted internals — between them they import eleven symbols that will not exist:
`_select_grammar`, `_tier_height`, `_compose`, `_grammar_floor`, `_MIRROR`,
`_mirror_part`, `_mirror_row`, `_SELF_SYMMETRIC`, `GLYPH_FLIP`,
`compose_horizontal`, `flip_row`. Nothing in them is salvageable in place; their
*intent* — determinism, fixed draw counts, exact box fill, tier ordering — is
preserved by the two files below.

### Copy from upstream

`sprite-art-designer/tests/test_sprite_art.py` →
`tests/test_vendored_sprite_art.py`, plus
`sprite-art-designer/tests/fixtures/tier_renders.json` →
`tests/fixtures/tier_renders.json`.

Only `ROOT` / `ASSETS` (`test_sprite_art.py:48-49`) need repointing at
`edge/art/assets`. This is the library's own contract guard and travels with the
vendored code — it covers the seed contract, tier selection, exact-rectangle
output, archetype filtering, repeat semantics, the palette contract, and a golden
render fixture.

Because the prerequisite split has landed, this file is already runtime-only: the
REXPaint and rotation tests moved to `tests/test_sprite_art_authoring.py`
upstream, which Edge does not copy. If you find `export_rexpaint` or
`generate_rotated_view` in the file you are copying, the split has **not** landed
— stop and re-read the prerequisite note at the top of this document.

### Write `tests/test_sprite_seam.py`

The Edge-side seam:

- **Exact box fill** at every size the game actually requests: ship 36×5, port
  19×8, starbase 22×9, stardock 38×16 (`SceneArtConfig`, mirrored in
  `config/default.yaml → scene:`), plus the gallery's ship 20×6 and port 18×8.
  Assert every rendered line is exactly `width` cells and there are exactly
  `height` lines. Note this holds because `pad_to` makes it hold — see §4.
- **Determinism** — the same arguments produce identical `.plain` and `.spans`.
- **Facing** — `facing="left"` differs from `"right"` for ships.
- **Coverage** — every id in `available_subtypes("ship")` and
  `available_subtypes("port")` renders non-blank at its gameplay box.
- **Palette resolution** — `style_for` resolves every id in
  `available_archetypes()`, and an unknown id falls back to `humanoid_diplomat`.
  Discovery art now depends on the vendored YAML, so a sync that drops or renames
  an archetype must fail loudly right here.
- **Whole-tier fit** — the guard that exact box fill alone does *not* give you.
  A cropped render fills its box perfectly; that is what made the original bug
  invisible to the box-fill assertions. Read the caps out of `SceneArtConfig` and
  assert `fit_box` returns a rung no larger than the cap on either axis, for
  every vendored subtype. Add the two behavioural companions: that requesting a
  rung's natural box selects *that* rung back (`fit_box` must agree with the
  library's own height-based choice), and that a narrower bound steps a ship down
  a rung while leaving the box's spare columns blank — a cropped tier inks edge to
  edge, which is the signature to test against.

### The highest-risk existing test — run this first

`tests/test_station_archetype_art.py:55`
(`test_archetype_icons_are_distinct_procedural_cell_art`) requires
`trading_port` and `starbase` at seed 17, 24×8, to produce **14 distinct
`.plain` strings** across all archetypes.

`sprite_art` varies station geometry per archetype (`Variant.archetypes`,
`Section.archetype_repeats`), so this should hold. But a failure means the
vendored stations are not archetype-differentiated at that particular box, which
is a genuine finding — do not weaken the test to make it pass. Report it.

### Existing tests that keep working

- `tests/test_art_coverage.py:43` (`test_ship_roles_have_sprites`) passes
  unchanged: it checks every *configured* role has a sprite, and vendoring extra
  sprites cannot break that direction. Extend it to honour `art_subtype` when
  set, so the reserved field is covered before anyone populates it.
- `tests/test_station_archetype_art.py:110` asserts the Stardock header requests
  `("port", "stardock")` and never `("port", "trading_port")`. Unaffected, but
  it is a real contract (`SECTOR_SCENE_COMPOSITION.md` §4.1) — keep it.
- `tests/test_discovery_art.py` must pass **unchanged**. If it does not, §6 is
  wrong.

---

## 10. Project configuration

- **`scene:` caps must clear a whole tier.** The shipped caps were authored
  against the old band grammar, which tiled continuously to any box. Tiered art
  does not: a cap that clears no rung silently returns a cropped one. Two caps
  had to move (`config/default.yaml → scene:` and the `SceneArtConfig` defaults
  that mirror it):

  | Key | Was | Now | Why |
  |---|---|---|---|
  | `port.max_height` | 6 | **8** | 6 selected `trading_port`'s 7-wide mast rung; its 11-wide silhouette is on the 7-row rung (8 also satisfies the non-saturation rule at the new `port_scale`) |
  | `port.max_width` | 16 | **19** | forced by the pre-existing `max_width ≥ int(max_height × 2.4)` rule once the height cap moved |
  | `ship.max_width` | 16 | **36** | no ship rung is under 17 columns; 36 clears `medium` (~34×5) |
  | `port_scale` | 0.25 | **0.3** | beside a planet the scaled box is what selects the rung, and 0.25 never reached 7 rows — the port stayed on the mast rung at every viewport |

  These four move together: `port_scale` sets what the port is *asked* for beside
  a planet, and the caps set the ceiling. `test_config.py` holds both standing
  rules — `max_height ≥ round(scale × planet.max_height)` and
  `max_width ≥ int(max_height × 2.4)` — plus the ordering `ship.max_height <
  port.max_height`. Changing one number without re-running it will trip a rule.

  `_paint_ships` (`widgets.py`) also stopped imposing `sh * 3` as its width; it
  passes the available sky instead and lets `fit_box` pick the rung.
- **`[project] dependencies`** (`pyproject.toml:9`) lists only `opensimplex` and
  `tracery`. Add `pyyaml`, and `rich` while you are there — both are already
  de-facto dependencies present in `[tool.pixi.dependencies]`, so nothing new
  installs, but the vendored library imports them directly.
- **Exclude the vendored tree from ruff:**

  ```toml
  [tool.ruff]
  target-version = "py312"
  extend-exclude = ["edge/art/sprite_art"]
  ```

  This is what makes the byte-for-byte sync check in `docs/SPRITE_ART_SYNC.md`
  achievable — Edge's linter must never rewrite vendored code.
- **mypy** already excludes `edge/art` (it is outside `[tool.mypy] files`), so the
  vendored package is not type-checked here. That is deliberate; upstream runs
  `mypy --strict` over it.
- **Packaging** — `[tool.hatch.build.targets.wheel] packages = ["edge"]` picks up
  the asset YAML automatically, since hatchling includes non-Python files under a
  packaged directory.

---

## 11. Documentation to update in the same change

Per `AGENTS.md`, contract docs move with the implementation.

- **`docs/DESIGN_ARTGEN.md`** §2 and §4.2 describe the mirror-and-stack port
  grammar, the five-slot ship grammar, left-half authoring, and the
  one-draw-per-slot rule. All of it is now false. Rewrite around tiers, sections,
  variants, and archetype-driven geometry. Keep §2.1 (synchronous + cached), §2.2
  (target size is a parameter), and §3 (seeds derived locally) — those survive.
- **`docs/SECTOR_SCENE_COMPOSITION.md`** §2 states that archetype station
  grammars stack 2-row repeat blocks so odd heights ink one row short. Tier
  selection replaces continuous tiling with a discrete ladder plus centring;
  update the rule and the accepted-slack note. The §2 cap rule and
  `station_dimensions` are unchanged.
- **`images/ui/starbases/PROVENANCE.md:11`** claims the icon "deliberately
  continues the procedural `edge.art.port` band-grammar method" — a dangling
  reference to a deleted module.
- **`AGENTS.md`** gains a pointer to this document and to
  `docs/SPRITE_ART_SYNC.md`, alongside the existing keep-in-sync notes.

---

## 12. Suggested commit ordering

0. **In `sprite-art-designer`:** land `docs/RUNTIME_PACKAGE_SPLIT.md` and run
   `pixi run check` there. Note the resulting commit hash — it is the vendoring
   baseline for `docs/SPRITE_ART_SYNC.md` §1.
1. Vendor the package and assets; add `edge/art/sprites.py`; add the ruff
   exclusion and the dependency entries.
2. Rewrite `generator.py` to route ship and port through `SPRITES`.
3. Fold the painter into `discovery.py`, repoint `style_for` at the catalog, and
   delete `hull.py` / `ship.py` / `port.py`. **Run the §6 migration test here**,
   while the old `ARCHETYPE_STYLES` values are still in the working tree.
4. Fix `edge/spacebattle/app.py`.
5. Tests: delete two files, copy the vendored suite, write the seam suite.
6. Docs (§11).
7. The `art_subtype` field as a small separate commit — it is a schema change,
   not an art one.

---

## 13. Verification

```bash
pixi run check      # ruff over `edge tests`, mypy on the typed layers, full pytest
```

Then, in order:

1. `pytest tests/test_station_archetype_art.py -k distinct` — the most likely
   failure (§9).
2. `pytest tests/test_discovery_art.py` — must pass unchanged, proving §6.
3. `pytest tests/test_sprite_seam.py` — the fit contract (§4, §9). Exact box fill
   alone will not catch a crop, because a cropped render fills its box perfectly.
4. `python -m edge.tui.scene_preview` — **the check that would have caught the
   original bug.** Read the ships and the ordinary port at a large viewport: a
   one-row hull band or a bare mast means the box clears no rung (§4, §10).
5. `pixi run art-gen` — the dev CLI contact sheets, for a first visual read of
   every subtype and archetype.
6. `pixi run edge`, then open the sprite gallery screen — confirms the 12 ships
   and 3 stations render in the real terminal, at real sizes, through
   `_to_truecolor`.
7. `edge-spacebattle` — the one non-TUI consumer, confirming §7's rewrite.

Expect ship and station art to look different (§1). Expect discovery, planet,
terrain, and starfield art to look **identical**.

Two suites need regenerating rather than fixing, because the change is
intentional: the Textual snapshots (`pytest tests/test_ui_snapshots.py
--snapshot-update`, ~35 of them carry ship or station art) and the wire
fingerprint (§8). Regenerate the snapshots **last**, after the caps are settled —
otherwise you bake in an intermediate size and lose the diff that shows the art
actually changed.
