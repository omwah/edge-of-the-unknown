"""Generate `edge/art/geometry_catalog.json` from the vendored sprite library.

The geometry catalogue is the injected data `edge/scene/`'s `ArtGeometryCatalog`
loader hands the solver: an exact authored box plus a measured ink envelope for
every `(kind, subtype, view axis, tier, archetype)` the vendored library can
distinguish (`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §2.5, §9.4).

This script renders; the runtime never does (plan §6.2 rule 1), and
`edge/scene/` never reads the output file — the art/TUI seam
(`edge/art/geometry_catalog.py`) loads it and hands over plain records.

Usage::

    python scripts/gen_geometry_catalog.py           # write edge/art/geometry_catalog.json
    python scripts/gen_geometry_catalog.py --check    # regenerate to a temp file and diff

`tests/test_geometry_catalog.py` runs the `--check` path in CI so an unguarded
upstream sprite sync (`docs/SPRITE_ART_SYNC.md`) fails loudly instead of
silently shifting scene geometry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from edge.art.sprite_art import (  # noqa: E402
    SPRITE_SCHEMA_VERSION,
    render_sprite,
    resolve_archetype,
)
from edge.art.sprites import SPRITES, _natural_box  # noqa: E402
from edge.tui.art_adapter import text_to_cells  # noqa: E402

OUTPUT_PATH = ROOT / "edge" / "art" / "geometry_catalog.json"
ASSET_ROOT = ROOT / "edge" / "art" / "assets"

SCHEMA_VERSION = 1

# Fixed, committed seed sample -- not a random draw. Ink varies within one rung
# because variant choice is seeded (`_seed_rng`, `_choose_variant`); the sample
# exists to capture that envelope, and the natural box must be seed-invariant
# across it (a hard error otherwise -- see `_measure_one`).
SAMPLE_SEEDS: tuple[int, ...] = tuple(range(8))


def _asset_tree_hash() -> str:
    """A stable sha256 over every vendored asset file's contents.

    Not the manifest hash: this is what actually feeds rendering, so a byte
    change in a sprite YAML changes this even if the manifest happens to lag.
    """

    digest = hashlib.sha256()
    for path in sorted(ASSET_ROOT.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(ASSET_ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _ink_bounds_and_count(width: int, height: int, cells: Any) -> tuple[tuple[int, int, int, int], int]:
    """`(col, row, width, height)` bounds and count of ink cells.

    Ink cell: after flattening with `text_to_cells`, a cell is ink iff its
    character is not `" "` (plan §9.1) -- exactly the test `_SceneComposer`
    already applies for transparency.
    """

    min_col = min_row = None
    max_col = max_row = -1
    count = 0
    for row_index, row in enumerate(cells):
        for col_index, (char, _style) in enumerate(row):
            if char == " ":
                continue
            count += 1
            if min_col is None or col_index < min_col:
                min_col = col_index
            if min_row is None or row_index < min_row:
                min_row = row_index
            if col_index > max_col:
                max_col = col_index
            if row_index > max_row:
                max_row = row_index
    if min_col is None or min_row is None:
        # No ink at all: an empty bounds box at the origin.
        return (0, 0, 0, 0), 0
    return (min_col, min_row, max_col - min_col + 1, max_row - min_row + 1), count


def _measure_one(
    kind: str,
    subtype: str,
    axis: str,
    view_id: str,
    archetype_id: str,
    tier_index: int,
    natural: tuple[int, int],
) -> dict[str, Any]:
    sprite = SPRITES.sprites[subtype]
    width, height = natural
    resolved_archetype = resolve_archetype(archetype_id)
    ink_bounds_samples: list[tuple[int, int, int, int]] = []
    ink_count_samples: list[int] = []
    for seed in SAMPLE_SEEDS:
        view = sprite.views[view_id]
        facing = view.canonical_facing
        art = render_sprite(
            sprite,
            SPRITES.palettes,
            width=width,
            height=height,
            seed=seed,
            archetype_id=resolved_archetype,
            view_id=view_id,
            facing=facing,
        )
        lines = art.plain.splitlines()
        actual_height = len(lines)
        actual_width = max((len(line) for line in lines), default=0)
        if (actual_width, actual_height) != (width, height):
            raise AssertionError(
                f"natural box is seed-dependent for {kind}/{subtype}/{axis}/"
                f"{archetype_id}/tier[{tier_index}] at seed {seed}: expected "
                f"{(width, height)}, rendered {(actual_width, actual_height)}"
            )
        cells = text_to_cells(art)
        bounds, count = _ink_bounds_and_count(width, height, cells)
        ink_bounds_samples.append(bounds)
        ink_count_samples.append(count)

    ink_min = tuple(min(sample[i] for sample in ink_bounds_samples) for i in range(4))
    ink_max = tuple(max(sample[i] for sample in ink_bounds_samples) for i in range(4))
    # Cost proxy: composed cell area (width * height) of the natural box, plus
    # the section count (each section is one independent RNG draw and one
    # composed band, so more sections mean more work at the same area). This
    # is a deterministic stand-in for measured wall-clock cost -- timing a
    # render is inherently noisy run-to-run and machine-to-machine, which
    # would make the generated file byte-unreproducible and defeat the
    # `--check` guard (plan §9.4's "measure... median wall-clock" is honored
    # in spirit: relative ordering across rungs tracks actual render work,
    # while the shipped number stays exactly reproducible). WP-SC05's cost
    # calibration is free to replace this proxy with a measured figure.
    section_count = len(sprite.views[view_id].tiers[tier_index].sections)
    raw_cost = width * height * max(1, section_count)
    return {
        "kind": kind,
        "subtype": subtype,
        "axis": axis,
        "archetype_id": archetype_id,
        "index": tier_index,
        "natural": [width, height],
        "ink_min": list(ink_min),
        "ink_max": list(ink_max),
        "ink_count_min": min(ink_count_samples),
        "ink_count_max": max(ink_count_samples),
        "_raw_cost": raw_cost,
    }


def build_records() -> list[dict[str, Any]]:
    archetype_ids = sorted(set(SPRITES.palettes.archetypes) | {SPRITES.palettes.fallback_archetype})
    records: list[dict[str, Any]] = []
    for kind in ("ship", "port"):
        for subtype in SPRITES.available_subtypes(kind):
            sprite = SPRITES.sprites[subtype]
            for view_id, view in sorted(sprite.views.items()):
                for archetype_id in archetype_ids:
                    resolved_archetype = resolve_archetype(archetype_id)
                    for tier_index, tier in enumerate(view.tiers):
                        natural = _natural_box(view, tier, resolved_archetype)
                        records.append(
                            _measure_one(
                                kind,
                                subtype,
                                view.axis,
                                view_id,
                                archetype_id,
                                tier_index,
                                natural,
                            )
                        )

    # Normalize render_cost to integer units against the cheapest rung in the
    # file, per plan §9.4. Never below 1, so cost is always a positive weight.
    cheapest = min(record["_raw_cost"] for record in records)
    for record in records:
        normalized = round(record.pop("_raw_cost") * 10 / cheapest)
        record["render_cost"] = max(1, normalized)

    records.sort(
        key=lambda r: (r["kind"], r["subtype"], r["axis"], r["archetype_id"], r["index"])
    )
    return records


def build_catalog() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "sprite_schema_version": SPRITE_SCHEMA_VERSION,
        "generated_from": _asset_tree_hash(),
        "rungs": build_records(),
    }


def write_catalog(path: Path) -> None:
    catalog = build_catalog()
    text = json.dumps(catalog, indent=2, sort_keys=True) + "\n"
    path.write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate to a temp file and diff against the checked-in catalogue "
        "instead of overwriting it",
    )
    args = parser.parse_args()

    if args.check:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "geometry_catalog.json"
            write_catalog(candidate)
            current = OUTPUT_PATH.read_text() if OUTPUT_PATH.exists() else ""
            new = candidate.read_text()
            if current != new:
                print(
                    "edge/art/geometry_catalog.json is stale. Refresh it with:\n"
                    "    python scripts/gen_geometry_catalog.py",
                    file=sys.stderr,
                )
                return 1
            print("edge/art/geometry_catalog.json is up to date.")
            return 0

    write_catalog(OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
