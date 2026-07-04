"""Render a generated universe to an interactive web page (DESIGN §5).

A dev-only topology inspector: it serializes a `UniverseState` to a JSON payload
and writes a **self-contained** HTML page (inline SVG + vanilla JS, no external
assets) that draws the generated warp graph on its real radial embedding, overlays
what populated each sector, distinguishes one-way from two-way warps, outlines the
Core / clusters / distance bands, and lets you edit edges and export the result as
JSON for offline analysis of topology-algorithm changes.

No matplotlib/networkx: the layout is the embedding the generator already computed
(`state.sector_pos`), so this stays a pure serializer plus a file writer. The page
template lives beside this module as `webviz_template.html` (kept as real HTML so it
is editable/lintable), with a single `"__UNIVERSE_DATA__"` token the writer fills.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from edge.core.config import GameConfig
from edge.core.models import UniverseState

_TEMPLATE = Path(__file__).with_name("webviz_template.html")
_DATA_TOKEN = '"__UNIVERSE_DATA__"'


def _classify_edges(state: UniverseState) -> list[dict[str, Any]]:
    """Collapse the directed adjacency into display edges.

    A warp `a→b` is two-way iff its reverse exists (§movement.one_way_exits); those
    are emitted once as an unordered pair (`one_way=False`). A warp with no return
    edge is emitted as the directed pair it is, so the page can arrow it `a→b`.
    """
    edges: list[dict[str, Any]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for a, targets in state.adjacency.items():
        for b in targets:
            if a in state.adjacency.get(b, ()):  # reverse exists -> two-way
                key = (a, b) if a < b else (b, a)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                edges.append({"a": key[0], "b": key[1], "one_way": False})
            else:  # unique direction -> one-way, never duplicated
                edges.append({"a": a, "b": b, "one_way": True})
    return edges


def build_payload(state: UniverseState, config: GameConfig) -> dict[str, Any]:
    """Serialize the generated universe to the JSON shape the web page consumes."""
    # Invert the entity tables into per-sector buckets (mirrors edge/core/dto.py).
    ports: dict[int, list[dict[str, Any]]] = {}
    planets: dict[int, list[dict[str, Any]]] = {}
    species: dict[int, list[dict[str, Any]]] = {}
    discoveries: dict[int, list[dict[str, Any]]] = {}
    for p in state.ports.values():
        ports.setdefault(p.sector_id, []).append({"klass": p.klass.name, "name": p.name})
    for pl in state.planets.values():
        planets.setdefault(pl.sector_id, []).append(
            {"planet_type": pl.planet_type, "owner": pl.owner.kind}
        )
    for sp in state.species.values():
        species.setdefault(sp.sector_id, []).append(
            {"name": sp.name, "roster_id": sp.roster_id}
        )
    for d in state.discoveries.values():
        discoveries.setdefault(d.sector_id, []).append(
            {"kind": d.kind.name, "rarity": d.rarity_tier.name, "hidden": d.hidden}
        )

    sectors: list[dict[str, Any]] = []
    for sid, sec in sorted(state.sectors.items()):
        pos = state.sector_pos.get(sid)
        if pos is None:  # hand-built states have no embedding; nothing to place
            continue
        x, y = pos
        sectors.append(
            {
                "id": sid,
                "spatial_id": state.spatial_ids.get(sid, sid),
                "x": x,
                "y": y,
                "region_id": sec.region_id,
                "band": sec.distance_band,
                "core_hops": state.core_hops.get(sid, 0),
                "is_core": sec.is_galactic_core,
                "ports": ports.get(sid, []),
                "planets": planets.get(sid, []),
                "species": species.get(sid, []),
                "discoveries": discoveries.get(sid, []),
            }
        )

    # A region's "home band" = the band of its innermost (min-hop) sector, matching
    # how numbering treats a cluster as atomic (edge/bigbang/numbering.py).
    members: dict[int, list[int]] = {}
    for sid, sec in state.sectors.items():
        members.setdefault(sec.region_id, []).append(sid)
    regions: list[dict[str, Any]] = []
    for rid, reg in sorted(state.regions.items()):
        sids = members.get(rid, [])
        band = ""
        if sids:
            inner = min(sids, key=lambda s: state.core_hops.get(s, 0))
            band = state.sectors[inner].distance_band
        regions.append(
            {
                "id": rid,
                "name": reg.name,
                "band": band,
                "sector_ids": sorted(sids),
                "alliance_id": reg.controlling_alliance_id,
                "species_id": reg.controlling_species_id,
            }
        )

    bands = [
        {"name": b.name, "min_hops": b.min_hops, "max_hops": b.max_hops}
        for b in config.bigbang.active_bands()
    ]
    hub_sector_ids = sorted(s.id for s in state.sectors.values() if s.is_galactic_core)

    return {
        "meta": {
            "seed": state.game.seed,
            "topology_mode": config.bigbang.topology_mode,
            "sector_count": len(state.sectors),
            "core_sector_count": config.bigbang.core_sector_count,
            "bands": bands,
            "generated_at": state.game.created_at,
        },
        "sectors": sectors,
        "edges": _classify_edges(state),
        "regions": regions,
        "hub_sector_ids": hub_sector_ids,
    }


def dump_json(state: UniverseState, path: Path | str, *, config: GameConfig) -> None:
    """Write just the visualization payload to `path` (no HTML)."""
    payload = build_payload(state, config)
    out = Path(path)
    if out.parent != Path():
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def render_web(state: UniverseState, out_dir: Path | str, *, config: GameConfig) -> Path:
    """Write `index.html` + `universe.json` into `out_dir`; return the HTML path."""
    payload = build_payload(state, config)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    (directory / "universe.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Embed the payload inline so the page works when opened via file:// (a sibling
    # fetch() is blocked in Chrome). Neutralize any "</script>" that could break out.
    data_js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = _TEMPLATE.read_text(encoding="utf-8").replace(_DATA_TOKEN, data_js)
    index = directory / "index.html"
    index.write_text(html, encoding="utf-8")
    return index
