"""Loads `edge/art/geometry_catalog.json` into `edge.scene.catalog.ArtGeometryCatalog`.

This is the art/TUI seam side of the injected catalogue
(`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §9.3, §9.4): the only place that
reads the generated file and turns it into the plain immutable records
`edge/scene/` is allowed to see. `edge/scene/` itself never does file I/O.

The file is generated and checked in by `scripts/gen_geometry_catalog.py`; do
not hand-edit it (`tests/test_geometry_catalog.py` guards drift, per
`docs/SPRITE_ART_SYNC.md`).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from edge.scene.catalog import ContinuousYield, LadderKey, LadderRung
from edge.scene.geometry import CellBox

DEFAULT_CATALOG_PATH = Path(__file__).parent / "geometry_catalog.json"


def _cell_box(values: list[int]) -> CellBox:
    if len(values) == 2:
        width, height = values
        return CellBox(col=0, row=0, width=width, height=height)
    col, row, width, height = values
    return CellBox(col=col, row=row, width=width, height=height)


class JsonArtGeometryCatalog:
    """Concrete `ArtGeometryCatalog` backed by the generated JSON file.

    Continuous-kind yields are calibration output (WP-SC05) and are not
    present in the generated file; `continuous()` raises `KeyError` for every
    kind until that data is injected, matching the "no shipped defaults" rule
    for WP-SC02.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self.version = str(data["schema_version"])
        self._rungs: dict[LadderKey, tuple[LadderRung, ...]] = {}
        by_key: dict[LadderKey, list[LadderRung]] = {}
        for record in data["rungs"]:
            key = LadderKey(
                kind=record["kind"],
                subtype=record["subtype"],
                axis=record["axis"],
                archetype_id=record["archetype_id"],
            )
            rung = LadderRung(
                tier_id=str(record["index"]),
                index=record["index"],
                natural=_cell_box(record["natural"]),
                ink_min=_cell_box(record["ink_min"]),
                ink_max=_cell_box(record["ink_max"]),
                ink_count_min=record["ink_count_min"],
                ink_count_max=record["ink_count_max"],
                render_cost=record["render_cost"],
            )
            by_key.setdefault(key, []).append(rung)
        for key, rungs in by_key.items():
            self._rungs[key] = tuple(sorted(rungs, key=lambda r: r.index))
        self._continuous: dict[str, ContinuousYield] = {}

    @classmethod
    def from_file(cls, path: Path = DEFAULT_CATALOG_PATH) -> JsonArtGeometryCatalog:
        return cls(json.loads(path.read_text()))

    def rungs(self, key: LadderKey) -> tuple[LadderRung, ...]:
        return self._rungs.get(key, ())

    def continuous(self, kind: str) -> ContinuousYield:
        return self._continuous[kind]


@lru_cache(maxsize=1)
def load_default_geometry_catalog() -> JsonArtGeometryCatalog:
    """The one process-wide catalogue instance, loaded from the shipped file."""

    return JsonArtGeometryCatalog.from_file()
