"""Scale-conflict gallery for the sector scene (dev-only, never imported at runtime).

`scene_preview` answers "does this one sector look right?". This answers the harder
question: **across every combination of objects a sector can hold, does the scale
hierarchy hold — and where does it break?**

    pixi run scene-gallery                                   # browse it locally
    pixi run python -m edge.tui.scene_gallery --serve --host 0.0.0.0
    pixi run python -m edge.tui.scene_gallery --html gallery.html
    pixi run python -m edge.tui.scene_gallery                 # findings table only
    pixi run python -m edge.tui.scene_gallery --case port+ships --size 150x52

`--serve` binds **127.0.0.1 by default** and serves a private temp directory, so the
page stays on this machine. `--host` widens that for a container, VM, WSL, or remote
dev box; the page is unauthenticated, so a non-loopback bind publishes the art to
whatever can route to it. Nothing here writes into the repo unless you pass `--html`
with a path inside it.

The hierarchy under test is DESIGN'd in docs/SECTOR_SCENE_COMPOSITION.md §1:

    planet  ≫  Stardock  >  starbase  >  port  >  ship  >  fighters/mines

Two objects of different kinds should never read as peers, and nothing should be
drawn at a rung so low it stops reading as itself. Every case here renders through
the real `_SceneComposer`, then measures the **inked rects the composer actually
placed** (via its own hotspots) rather than the boxes it asked for — the boxes lie,
because the sprite library quantises them to authored tiers and centres the result.

Why this exists: the art migration (docs/SPRITE_ART_MIGRATION.md) replaced grammars
that tiled continuously to any requested height with a library that steps between a
handful of authored rungs and stops at the richest one. Sizing is therefore no
longer a smooth function of the config — it is a step function with a ceiling, and
conflicts appear at combinations rather than at extremes. A matrix is the only way
to see them.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rich.console import Console
from rich.text import Text

from edge.art.geometry_catalog import ArtGeometryCatalog, load_geometry_catalog
from edge.art.scene_paint import paint_grid, resolve_scene
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.core.config import SceneArtConfig
from edge.core.dto import (
    SectorDiscovery,
    SectorDTO,
    SectorForceDTO,
    SectorPlanetDTO,
    SectorPortDTO,
    SectorShipDTO,
    SectorStarbaseDTO,
)
from edge.scene.classify import classify_sector
from edge.scene.geometry import CellBox
from edge.scene.model import ScenePlan, SceneTuning
from edge.scene.project import DepthLayeredAnchorProjection, FixedFovPerspective, ProjectionStrategy
from edge.scene.solve import solve
from edge.tui.widgets import _SceneComposer

# WP-SC09 dev switch (`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §6.4/WP-SC09):
# both the legacy `_SceneComposer` and the two new-pipeline `ProjectionStrategy`
# implementations stay available side by side, defaulting to legacy. There is
# no config knob that reaches real play — this switch lives entirely in this
# dev-only gallery tool; `edge/tui/screens/*.py` never sees it.
_STRATEGIES: dict[str, ProjectionStrategy | None] = {
    "legacy": None,
    "fixed_fov_perspective": FixedFovPerspective(),
    "depth_layered_anchor": DepthLayeredAnchorProjection(),
}
COMPOSERS: tuple[str, ...] = tuple(_STRATEGIES)
DEFAULT_COMPOSER = "legacy"

# The canvas the scene gets at each tier, plus two past where the old chain
# saturated — the conflicts this tool exists for only appear on a large canvas.
SIZES: tuple[tuple[str, int, int], ...] = (
    ("standard 67x30", 67, 30),
    ("wide 87x36", 87, 36),
    ("large 120x44", 120, 44),
    ("huge 150x52", 150, 52),
)

# Rank in the scale hierarchy; a lower rank must never out-measure a higher one.
# A belt ranks with the planet it replaces; a discovery is deliberately unranked —
# a nebula is *meant* to dwarf a planet, so it has no fixed place in the order.
_RANK = {"planet": 0, "belt": 0, "stardock": 1, "starbase": 2, "port": 3, "ship": 4}


@dataclass
class Measured:
    """What one object kind actually occupies in a rendered scene."""

    kind: str
    width: int
    height: int
    count: int


def _ship(name: str, role: str, cid: int) -> SectorShipDTO:
    # `archetype_id` matters only to the new pipeline (WP-SC09): the legacy
    # composer never reads it, but `edge.scene.classify.classify_sector`
    # keys every ship's `LadderKey` on it, and an empty/`None` archetype has
    # no catalogue rungs at all (`edge/art/geometry_catalog.json` only ships
    # per-species archetypes). A real, always-present archetype lets every
    # gallery case actually admit and paint through the new composer too.
    return SectorShipDTO(name=name, role=role, archetype_id=_ARCHETYPE, contact_id=cid)


# A species archetype present for every ship/port/starbase subtype in the
# shipped catalogue (`edge/art/geometry_catalog.json`) — used as every
# fixture's `archetype_id` below so the new pipeline (WP-SC09) can resolve a
# real ladder rung, not just the legacy composer (which never reads the
# field at all).
_ARCHETYPE = "humanoid_diplomat"


def _port(name: str = "Verge Depot", *, stardock: bool = False) -> SectorPortDTO:
    # `klass` is the display label the server builds via `_port_klass_label`, which
    # says "Stardock" for the flagship — match that, or the fixture describes a
    # state the game never produces.
    return SectorPortDTO(port_id=64, name=name,
                         klass="Stardock" if stardock else "Class 1 (SBB)",
                         is_stardock=stardock, archetype_id=_ARCHETYPE)


def _base(name: str = "Orbital Platform", planet_id: int | None = None,
          condition: str = "open") -> SectorStarbaseDTO:
    return SectorStarbaseDTO(starbase_id=4, name=name, owner="yours",
                             operational=condition == "open", planet_id=planet_id,
                             condition=condition, archetype_id=_ARCHETYPE)


def _find(kind: str, name: str, *, collected: bool = True) -> SectorDiscovery:
    return SectorDiscovery(discovery_id=22, label=name, kind=kind, rarity="Rare",
                           salvageable=True, name=name, collected=collected)


def _sector(sid: int, **kw: object) -> SectorDTO:
    base: dict[str, object] = dict(
        region="Gallery", sector_id=sid, display_id=sid, band="Frontier",
        flavor="a test arrangement", beacon=None,
    )
    base.update(kw)
    return SectorDTO(**base)  # type: ignore[arg-type]


_TRAFFIC = [_ship("Vesk Trader", "transport", 2), _ship("Kalt Corvette", "warship", 5)]


def cases() -> dict[str, SectorDTO]:
    """The composition matrix — every pairing where a scale conflict can surface.

    Ordered so related rows sit together: what the ships are standing next to
    changes down the list while the ships themselves stay fixed.
    """
    planet = [SectorPlanetDTO(planet_id=9101, name="New Hesse",
                              ptype="terrestrial_warm")]
    return {
        # --- ships measured against each kind of neighbour --------------------
        "empty+ships": _sector(101, ships=_TRAFFIC),
        "port+ships": _sector(102, ports=[_port("Port Kalso")], ships=_TRAFFIC),
        "stardock+ships": _sector(103, ports=[_port("Stardock", stardock=True)],
                                  ships=_TRAFFIC),
        "starbase+ships": _sector(104, starbases=[_base()], ships=_TRAFFIC),
        "planet+ships": _sector(105, planets=planet, ships=_TRAFFIC),
        "planet+port+ships": _sector(106, planets=planet, ports=[_port("Port Kalso")],
                                     ships=_TRAFFIC),
        "planet+stardock+ships": _sector(107, planets=planet,
                                         ports=[_port("Stardock", stardock=True)],
                                         ships=_TRAFFIC),
        "planet+starbase+ships": _sector(108, planets=planet,
                                         starbases=[_base(planet_id=9101)],
                                         ships=_TRAFFIC),
        # --- stations measured against space finds ----------------------------
        "wormhole+port+ships": _sector(109, discoveries=[_find("wormhole", "the Hollow Gate")],
                                       ports=[_port("Gate Depot")], ships=_TRAFFIC),
        "blackhole+port+ships": _sector(110, discoveries=[_find("black_hole", "Maw")],
                                        ports=[_port("Maw Station")], ships=_TRAFFIC),
        "nebula+port+ships": _sector(111, discoveries=[_find("nebula", "the Rose Veil")],
                                     ports=[_port("Veil Depot")], ships=_TRAFFIC),
        "wreck+ships": _sector(112, discoveries=[_find("wreck", "Vesk Marauder VII")],
                               ships=_TRAFFIC),
        "wormhole+starbase+ships": _sector(113,
                                           discoveries=[_find("wormhole", "the Hollow Gate")],
                                           starbases=[_base("Gate Watch")], ships=_TRAFFIC),
        # --- the sprawlers and the crowded cases ------------------------------
        "belt+port+ships": _sector(114,
                                   planets=[SectorPlanetDTO(planet_id=531,
                                                            name="Cinder Drift",
                                                            ptype="asteroid_belt",
                                                            ore_reserve=1400,
                                                            ore_reserve_max=2600)],
                                   ports=[_port("Drift Depot")], ships=_TRAFFIC),
        "planet+port+wreck+traffic": _sector(115, planets=planet,
                                             ports=[_port("Port Kalso")],
                                             discoveries=[_find("wreck", "Marauder VII")],
                                             ships=_TRAFFIC + [
                                                 _ship("Aki Witness", "transport", 3),
                                                 _ship("Kalt Pike", "fighter", 5)],
                                             force=SectorForceDTO(
                                                 owner="Kalt Ascendancy", yours=False,
                                                 fighters=200, mode="offensive", toll=0,
                                                 armid_mines=0, limpet_mines=0)),
        "derelict-base+ships": _sector(116,
                                       starbases=[_base("Silent Ring",
                                                        condition="derelict")],
                                       ships=_TRAFFIC),
    }


def _slug(scene: str) -> str:
    """A scene id reduced to something safe for `id=` and a `#fragment`.

    Scene ids carry `+` and `@` so they read naturally in a bug report; those are
    legal in an HTML id but awkward in a selector, so the anchor gets a flattened
    form and the visible text keeps the real id.
    """
    return "s-" + re.sub(r"[^a-z0-9]+", "-", scene.lower()).strip("-")


def scene_id(case: str, w: int, h: int) -> str:
    """Stable handle for one cell of the matrix — quote this in a bug report.

    `scene_gallery --case <case> --size <WxH>` reproduces exactly this cell, and
    every sprite inside it is identified by its `SpriteRender.ref`.
    """
    return f"{case}@{w}x{h}"


def measure(sector: SectorDTO, cfg: SceneArtConfig, w: int,
            h: int) -> tuple[_SceneComposer, Text, dict[str, Measured], list[str]]:
    """Render one scene and return (composer, art, what-was-drawn, conflicts).

    The rendered `Text` comes back with the rest because composing is the expensive
    step and the HTML path needs the very same render the measurements describe —
    recomposing for the colour capture would double the build and risk measuring
    one render while displaying another.

    The composer is handed back so callers can read its `render_log` and
    `sprite_rects` — the per-sprite identifiers and footprints.
    """
    composer = _SceneComposer(sector, cfg)
    art = composer.compose(w, h)
    drawn: dict[str, Measured] = {}
    # `sprite_rects`, not `hotspots`: a hotspot carries a *click destination*, and
    # both Stardock and an ordinary port route to "port" while a belt routes to
    # "planet". Measuring off that would compare a Stardock against the port rung
    # and hide the one ordering the hierarchy cares most about.
    for kind, x0, y0, x1, y1 in composer.sprite_rects:
        cw, ch = x1 - x0, y1 - y0
        prev = drawn.get(kind)
        # Keep the largest of a kind; ships are the only kind that repeats.
        if prev is None or ch > prev.height:
            drawn[kind] = Measured(kind, cw, ch, (prev.count if prev else 0) + 1)
        else:
            prev.count += 1
    return composer, art, drawn, _conflicts(drawn, composer, w, h)


def _conflicts(drawn: dict[str, Measured], composer: _SceneComposer,
               w: int, h: int) -> list[str]:
    """Where this scene violates the §1 hierarchy or draws something unreadable."""
    out: list[str] = []
    ranked = [(k, m) for k, m in drawn.items() if k in _RANK]
    for a_kind, a in ranked:
        for b_kind, b in ranked:
            if _RANK[a_kind] < _RANK[b_kind] and a.height <= b.height:
                out.append(
                    f"{b_kind} ({b.width}x{b.height}) is not smaller than "
                    f"{a_kind} ({a.width}x{a.height}) — they read as peers"
                )
    ship = drawn.get("ship")
    if ship is not None and ship.width <= 17:
        sky = min((m.width for k, m in drawn.items() if k != "ship"), default=w)
        out.append(f"ship drew its narrowest rung ({ship.width}x{ship.height}) "
                   f"in a {w}-wide scene (neighbour {sky} wide)")
    port = drawn.get("port")
    if port is not None and port.width <= 7:
        out.append(f"port drew its mast rung ({port.width}x{port.height}), "
                   f"not its silhouette")
    for kind in ("port", "starbase", "stardock"):
        m = drawn.get(kind)
        if m is not None and h >= 44 and m.height <= 8:
            out.append(f"{kind} is {m.width}x{m.height} on a {w}x{h} canvas — "
                       f"tiny for the space available")
    if composer._deferred:
        out.append(f"{len(composer._deferred)} object(s) found no free sky and "
                   f"degraded to text rows")
    return out


@lru_cache(maxsize=1)
def _physical_pipeline() -> tuple[SceneTuning, ArtGeometryCatalog]:
    """The real, config-driven `SceneTuning`/`ArtGeometryCatalog` pair (WP-SC05),
    loaded once and shared across every physical-pipeline render in this process
    — the same `config/default.yaml -> scene.physical_model` a live game would
    use, never invented calibration numbers."""

    cfg = load_config("config/default.yaml")
    pm = cfg.scene.physical_model
    return build_scene_tuning(pm), load_geometry_catalog(build_continuous_yields(pm))


def _grid_to_text(grid: list[list[tuple[str, object]]], w: int, h: int) -> Text:
    out = Text()
    for y in range(h):
        row = grid[y] if y < len(grid) else []
        for x in range(w):
            ch, style = row[x] if x < len(row) else (" ", None)
            out.append(ch, style=style)  # type: ignore[arg-type]
        if y < h - 1:
            out.append("\n")
    return out


def _conflicts_physical(drawn: dict[str, Measured], plan: ScenePlan) -> list[str]:
    """WP-SC09: the same §1 hierarchy check as `_conflicts`, but built entirely
    from `ScenePlan`/`ScenePaint` invariants (accepted objects' `scene_box`,
    `plan.rejected`) — no rectangle-scraping of the rendered text."""

    out: list[str] = []
    ranked = [(k, m) for k, m in drawn.items() if k in _RANK]
    for a_kind, a in ranked:
        for b_kind, b in ranked:
            if _RANK[a_kind] < _RANK[b_kind] and a.height <= b.height:
                out.append(
                    f"{b_kind} ({b.width}x{b.height}) is not smaller than "
                    f"{a_kind} ({a.width}x{a.height}) — they read as peers"
                )
    if plan.rejected:
        out.append(f"{len(plan.rejected)} object(s) rejected by the solver "
                   f"(no clearing placement)")
    return out


@dataclass
class PhysicalRender:
    """One new-pipeline cell's result: the painted art plus everything the
    gallery needs, built entirely from `ScenePlan`/`ScenePaint` (WP-SC09
    bullet 3 — no implementation-specific rectangle heuristics)."""

    plan: ScenePlan
    art: Text
    drawn: dict[str, Measured]
    flags: list[str]
    bounds: list[tuple[str, int, int, int, int]]
    refs: list[str]


def render_physical(sector: SectorDTO, strategy: ProjectionStrategy, w: int,
                    h: int) -> PhysicalRender:
    """Render one scene through the new `edge.scene`/`edge.art.scene_paint`
    pipeline: `classify_sector` -> `solve` -> `resolve_scene` -> `paint_grid`,
    from the same fixture DTO, real config-built tuning/catalogue, and
    `strategy` under test (WP-SC09 bullet 2 — identical inputs across
    composers)."""

    tuning, catalog = _physical_pipeline()
    arrangement, _glyphs = classify_sector(sector, tuning)
    viewport = CellBox(0, 0, w, h)
    plan = solve(arrangement, viewport, tuning, catalog, strategy)
    paint = resolve_scene(plan, arrangement, catalog, tuning)
    grid = paint_grid(paint, viewport)
    art = _grid_to_text(grid, w, h)

    drawn: dict[str, Measured] = {}
    bounds: list[tuple[str, int, int, int, int]] = []
    refs: list[str] = []
    for obj in paint.painted:
        kind = obj.key.tag
        b = obj.scene_box
        bounds.append((kind, b.col, b.row, b.col + b.width, b.row + b.height))
        refs.append(f"{kind}:{obj.key.ident}@{obj.natural_box.width}x{obj.natural_box.height}")
        prev = drawn.get(kind)
        if prev is None or b.height > prev.height:
            drawn[kind] = Measured(kind, b.width, b.height, (prev.count if prev else 0) + 1)
        elif prev is not None:
            prev.count += 1
    flags = _conflicts_physical(drawn, plan)
    return PhysicalRender(plan=plan, art=art, drawn=drawn, flags=flags, bounds=bounds, refs=refs)


def variant_scene_id(case: str, w: int, h: int, composer: str) -> str:
    """Stable per-variant gallery id (WP-SC09 bullet 3: stable ids retained).

    The legacy id is unchanged from `scene_id()` so existing localStorage
    ratings/comments keyed against it keep working; the two new-pipeline
    strategies get an explicit suffix so all three can be reviewed
    independently in the same page.
    """

    base = scene_id(case, w, h)
    return base if composer == "legacy" else f"{base}!{composer}"


_PAGE_CSS = """
/* The subject is a terminal: neutrals carry a cool slate bias off the phosphor
   ground rather than warm paper, and the whole page is monospace-led — the art
   being judged is a character grid, so the chrome around it shares its metrics. */
:root{--bg:#f4f6f8;--fg:#12171d;--muted:#59636e;--rule:#d3dae1;--card:#ffffff;
      --bad:#9c2f22;--badbg:#fbeeec;--ok:#1c6146;--term:#0b0d11;--accent:#2a5d9f}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#0f1216;--fg:#e6ebf1;--muted:#8e99a6;--rule:#262d36;--card:#151a20;
  --bad:#ff9d8a;--badbg:#2b1a17;--ok:#79d2a6;--term:#080a0d;--accent:#7fb0f2}}
:root[data-theme=dark]{--bg:#0f1216;--fg:#e6ebf1;--muted:#8e99a6;--rule:#262d36;
  --card:#151a20;--bad:#ff9d8a;--badbg:#2b1a17;--ok:#79d2a6;--term:#080a0d;
  --accent:#7fb0f2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:14.5px/1.6 ui-monospace,Menlo,Consolas,"DejaVu Sans Mono",monospace;
     font-variant-numeric:tabular-nums}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
.wrap{max-width:1180px;margin:0 auto;padding:40px 24px 96px}
h1{font-size:25px;margin:0 0 6px;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:17px;margin:44px 0 4px;letter-spacing:.02em;text-transform:lowercase;
   color:var(--accent)}
h3{font-size:14px;margin:0;font-weight:700}
.sub{color:var(--muted);margin:0 0 28px;max-width:68ch}
.lede{border-left:3px solid var(--accent);padding:2px 0 2px 16px;margin:0 0 32px;
      color:var(--muted);max-width:74ch}
.lede b{color:var(--fg)}
/* Severity is carried by a stripe as well as a number, so a bad row reads at a
   glance without being read. */
.case.flagged{border-left:3px solid var(--bad)}
.case.ok{border-left:3px solid var(--ok)}
.case{background:var(--card);border:1px solid var(--rule);border-radius:10px;
      margin:18px 0;overflow:hidden}
.case>header{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;
             justify-content:space-between;padding:12px 16px;
             border-bottom:1px solid var(--rule)}
.dims{color:var(--muted);font:12px/1.4 ui-monospace,Menlo,Consolas,monospace}
/* The art is a character grid, so every cell must have the same advance width.
   DejaVu Sans Mono leads because it is the only common mono face that covers the
   box-drawing, block-element, geometric-shape and dingbat ranges this art uses —
   any glyph the face lacks is drawn by a *fallback* font whose advance differs,
   which shears the whole line. Ligatures off for the same reason. */
.scene{overflow-x:auto;background:var(--term);padding:12px 14px}
.scene pre,.bounds{font:12px/1.12 "DejaVu Sans Mono","Liberation Mono",
                   "Noto Sans Mono","Cascadia Mono",ui-monospace,Menlo,Consolas,
                   monospace;
                   font-variant-ligatures:none;font-feature-settings:"liga" 0,"calt" 0;
                   font-variant-east-asian:normal}
.scene pre{margin:0;white-space:pre;color:#cfd6e0}
/* The last resort for a glyph no installed face has: pin it to one cell so a
   proportional fallback cannot widen the row. `1ch` resolves against the pre's
   own font, which is why `.bounds` above must share that font — its rectangles
   are positioned in `ch` too, and would otherwise be measured at the body size. */
.fb{display:inline-block;width:1ch;overflow:hidden;text-align:center;
    vertical-align:top}
.flags{margin:0;padding:10px 16px;list-style:none;background:var(--badbg);
       border-top:1px solid var(--rule)}
.flags li{color:var(--bad);font-size:13.5px;padding:2px 0}
.flags li::before{content:"▲ ";opacity:.75}
.clean{padding:10px 16px;color:var(--ok);font-size:13.5px;border-top:1px solid var(--rule)}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:8px 0 0}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule)}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;
   letter-spacing:.06em}
td.n{font-family:ui-monospace,Menlo,Consolas,monospace}
td.bad{color:var(--bad)}
.count{display:inline-block;min-width:22px;padding:1px 7px;border-radius:99px;
       background:var(--badbg);color:var(--bad);font-size:12px;
       font-family:ui-monospace,Menlo,Consolas,monospace}
.count.zero{background:transparent;color:var(--ok)}
.refs{border-top:1px solid var(--rule);padding:8px 16px}
.refs summary{cursor:pointer;color:var(--muted);font-size:12px;
              text-transform:uppercase;letter-spacing:.06em}
.refs ul{margin:8px 0 2px;padding-left:18px}
.refs li{font:12px/1.7 ui-monospace,Menlo,Consolas,monospace;color:var(--fg);
         word-break:break-all}

/* --- sprite bounds overlay -------------------------------------------------
   The scene is a monospace grid, so a cell maps exactly onto (1ch x 1 line).
   Each box is positioned in those units over the <pre>, which is why the
   rectangles land on the sprite's true footprint rather than near it. They sit
   ON TOP of the art deliberately — the point is to see where a sprite's bounds
   are versus where its ink is, and the gap between the two is the bug. */
.scene{position:relative}
.bounds{position:absolute;inset:12px 14px;pointer-events:none;opacity:0;
        transition:opacity .12s ease}
body.show-bounds .bounds{opacity:1}
.bound{position:absolute;border:1px solid currentColor;box-sizing:border-box}
.bound::after{content:attr(data-k);position:absolute;top:-1px;left:0;
              transform:translateY(-100%);font:10px/1.3 ui-monospace,Menlo,monospace;
              background:var(--term);padding:0 3px;white-space:nowrap}
.k-planet,.k-belt{color:#ffd166}
.k-discovery{color:#c792ea}
.k-stardock{color:#4dd0e1}
.k-starbase{color:#4db6ac}
.k-port{color:#7bc96f}
.k-ship{color:#ff7b72}
.k-wreck,.k-entity,.k-player,.k-glyph{color:#9aa5b1}
/* --- WP-SC09 A/B/C compare mode ---------------------------------------- */
.variant-group{margin:18px 0}
.variant-group>h3{font-size:13px;margin:0 0 8px;color:var(--muted);
                   text-transform:none;letter-spacing:0}
.variant-row{display:flex;gap:12px;overflow-x:auto;align-items:flex-start}
.variant-row>.case{flex:1 1 360px;min-width:300px;margin:0}
.composer-label{font:600 11px/1 ui-sans-serif,system-ui,sans-serif;
                text-transform:uppercase;letter-spacing:.05em;color:var(--accent)}
.toolbar{position:sticky;top:0;z-index:5;display:flex;gap:12px;align-items:center;
         background:var(--bg);border-bottom:1px solid var(--rule);
         padding:12px 0;margin:0 0 8px}
.toolbar button{font:600 13px/1 ui-sans-serif,system-ui,sans-serif;cursor:pointer;
                padding:9px 15px;border-radius:7px;border:1px solid var(--rule);
                background:var(--card);color:var(--fg)}
.toolbar button:hover{border-color:var(--accent)}
body.show-bounds .toolbar button{background:var(--accent);color:#fff;
                                 border-color:var(--accent)}
.legend{display:flex;gap:12px;flex-wrap:wrap;font:12px/1 ui-monospace,Menlo,monospace;
        color:var(--muted)}
.legend i{font-style:normal;padding-left:14px;position:relative}
.legend i::before{content:"";position:absolute;left:0;top:1px;width:9px;height:9px;
                  border:2px solid currentColor}

/* --- filters ---------------------------------------------------------------- */
.filters{display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:10px 0 14px;
         border-bottom:1px solid var(--rule);margin:0 0 8px}
.filters label{font-size:12px;color:var(--muted);text-transform:uppercase;
               letter-spacing:.06em}
.filters select{font:13px/1 ui-monospace,Menlo,monospace;padding:7px 9px;
                border-radius:6px;border:1px solid var(--rule);background:var(--card);
                color:var(--fg)}
.kinds{display:flex;gap:6px;flex-wrap:wrap}
.kinds label{display:inline-flex;align-items:center;gap:5px;cursor:pointer;
             border:1px solid var(--rule);border-radius:99px;padding:5px 11px;
             font-size:12px;text-transform:none;letter-spacing:0;color:var(--fg);
             background:var(--card)}
.kinds label:has(input:checked){border-color:currentColor;font-weight:700}
.kinds input{margin:0}
.tally{margin-left:auto;font-size:12px;color:var(--muted)}
.linkish{background:none;border:none;color:var(--muted);cursor:pointer;
         font:12px/1 ui-sans-serif,system-ui,sans-serif;text-decoration:underline;
         padding:4px 2px}
.sizegroup>h2{position:sticky;top:57px;background:var(--bg);z-index:4;padding:10px 0 6px;
              margin:28px 0 0;border-bottom:1px solid var(--rule)}
[hidden]{display:none!important}

/* --- per-scene review ------------------------------------------------------- */
.body{display:grid;grid-template-columns:1fr;gap:0}
body.show-review .body{grid-template-columns:minmax(0,1fr) 290px}
.review{display:none;border-left:1px solid var(--rule);padding:12px 14px;
        background:var(--card);min-width:0}
body.show-review .review{display:block}
.review h4{margin:0 0 8px;font-size:11px;text-transform:uppercase;
           letter-spacing:.07em;color:var(--muted);font-weight:600}
.rate{display:flex;gap:4px;margin:0 0 10px}
.rate label{flex:1;text-align:center;border:1px solid var(--rule);border-radius:6px;
            padding:7px 0;cursor:pointer;font-size:13px;background:var(--bg)}
.rate input{position:absolute;opacity:0;width:0;height:0}
.rate label:has(input:checked){background:var(--accent);color:#fff;
                               border-color:var(--accent);font-weight:700}
.rate label:has(input:checked).low{background:var(--bad);border-color:var(--bad)}
.review textarea{width:100%;min-height:110px;resize:vertical;padding:8px;
                 border-radius:6px;border:1px solid var(--rule);background:var(--bg);
                 color:var(--fg);font:12.5px/1.5 ui-monospace,Menlo,monospace}
.clear-one{margin-top:8px;font:12px/1 ui-sans-serif,system-ui,sans-serif;
           background:none;border:none;color:var(--muted);cursor:pointer;padding:4px 0;
           text-decoration:underline}
.case.reviewed{box-shadow:inset 3px 0 0 var(--accent)}
/* Jump targets clear the two sticky headers, and flash so the eye lands on the
   card rather than hunting for which one moved. */
.case{scroll-margin-top:118px}
.case.flash{outline:2px solid var(--accent);outline-offset:3px}
td a.jump{color:var(--accent);text-decoration:none}
td a.jump:hover,td a.jump:focus-visible{text-decoration:underline}
tbody tr:hover{background:color-mix(in srgb,var(--accent) 7%,transparent)}
.scale-hint{font-size:11px;color:var(--muted);margin:0 0 8px}

/* --- export dialog ---------------------------------------------------------- */
dialog{border:1px solid var(--rule);border-radius:10px;background:var(--card);
       color:var(--fg);padding:0;width:min(760px,92vw)}
dialog::backdrop{background:rgba(0,0,0,.55)}
dialog header{padding:14px 16px;border-bottom:1px solid var(--rule);font-weight:700}
dialog .pad{padding:14px 16px}
dialog textarea{width:100%;height:46vh;font:12px/1.5 ui-monospace,Menlo,monospace;
                border:1px solid var(--rule);border-radius:6px;background:var(--bg);
                color:var(--fg);padding:10px}
dialog footer{display:flex;gap:10px;justify-content:flex-end;padding:12px 16px;
              border-top:1px solid var(--rule)}
dialog a,dialog button{font:600 13px/1 ui-sans-serif,system-ui,sans-serif;
                       padding:9px 15px;border-radius:7px;border:1px solid var(--rule);
                       background:var(--card);color:var(--fg);cursor:pointer;
                       text-decoration:none;display:inline-block}
dialog a{background:var(--accent);color:#fff;border-color:var(--accent)}
.toolbar button[disabled]{opacity:.45;cursor:not-allowed}

/* --- expand-to-full-size ----------------------------------------------------
   A/B/C compare mode packs each variant into a `flex:1 1 360px` column, so a
   wide canvas (150x52) is mostly hidden behind horizontal scroll — exactly the
   case where comparing detail across composers matters most. The expand button
   clones one card's `.scene` (art + bounds overlay, so `show-bounds` still
   applies) into an oversized dialog instead of a scaled-down one, so the art is
   read at its native character grid with nothing competing for width. */
.expand-btn{background:none;border:1px solid var(--rule);border-radius:6px;
            color:var(--muted);cursor:pointer;font-size:14px;line-height:1;
            padding:4px 8px;flex:none}
.expand-btn:hover,.expand-btn:focus-visible{border-color:var(--accent);
                                            color:var(--accent)}
dialog#expand-dialog{width:min(96vw,1400px);max-width:96vw}
dialog#expand-dialog header{display:flex;align-items:baseline;justify-content:space-between;
                            gap:12px}
dialog#expand-dialog .composer-label{display:block;margin-bottom:2px}
dialog#expand-dialog .pad{padding:0;max-height:82vh;overflow:auto}
dialog#expand-dialog .pad .scene{padding:16px}
"""


_PAGE_JS = r"""
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

/* Review state is keyed by scene id and kept in localStorage, so a reviewer can
   regenerate the gallery after a code change and keep every note they have made
   — the scene ids are stable across runs precisely so this survives. */
const STORE = 'edge-scene-review-v1';
let review = {};
try { review = JSON.parse(localStorage.getItem(STORE) || '{}'); } catch (e) { review = {}; }

const entry = id => (review[id] = review[id] || { rating: 0, comment: '' });
const scored = r => r && (r.rating > 0 || (r.comment || '').trim().length > 0);

function persist() {
  try { localStorage.setItem(STORE, JSON.stringify(review)); } catch (e) {}
  refreshCounts();
}

function refreshCounts() {
  const n = Object.values(review).filter(scored).length;
  $('#review-count').textContent = n;
  $('#export').disabled = n === 0;
  $$('.case').forEach(c => c.classList.toggle('reviewed', scored(review[c.dataset.scene])));
}

/* ---- filters: canvas size, and which sprite kinds must be present ---------- */
function applyFilters() {
  const size = $('#f-size').value;
  const kinds = $$('.f-kind').filter(b => b.checked).map(b => b.value);
  let visible = 0;
  $$('.sizegroup').forEach(group => {
    const sizeOk = size === 'all' || group.dataset.size === size;
    let shown = 0;
    $$('.case', group).forEach(card => {
      const has = (card.dataset.kinds || '').split(' ');
      const ok = sizeOk && kinds.every(k => has.includes(k));
      card.hidden = !ok;
      if (ok) shown++;
    });
    group.hidden = !sizeOk || shown === 0;
    visible += shown;
  });
  $('#shown').textContent = visible;
}

/* ---- export: one ingestible file of every complaint ------------------------ */
function buildReport() {
  const complaints = [];
  $$('.case').forEach(card => {
    const id = card.dataset.scene;
    const r = review[id];
    if (!scored(r)) return;
    const read = k => { try { return JSON.parse(card.dataset[k] || 'null'); } catch (e) { return null; } };
    complaints.push({
      scene: id,
      case: card.dataset.case,
      canvas: card.dataset.size,
      rating: r.rating || null,
      comment: (r.comment || '').trim(),
      measured: read('measured'),
      auto_flags: read('flags'),
      sprites: read('sprites'),
      reproduce: `pixi run scene-gallery --case ${card.dataset.case} --size ${card.dataset.size}`
    });
  });
  complaints.sort((a, b) => (a.rating || 9) - (b.rating || 9));
  return {
    tool: 'edge.tui.scene_gallery',
    generated: new Date().toISOString(),
    rating_scale: '1 worst .. 5 best',
    count: complaints.length,
    complaints
  };
}

function exportReview() {
  const text = JSON.stringify(buildReport(), null, 2);
  $('#export-text').value = text;
  $('#export-dialog').showModal();
  const blob = new Blob([text], { type: 'application/json' });
  const a = $('#export-download');
  URL.revokeObjectURL(a.href || '');
  a.href = URL.createObjectURL(blob);
  a.download = 'scene-complaints.json';
}

/* ---- wire up --------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
  $('#bounds').addEventListener('click', () =>
    document.body.classList.toggle('show-bounds'));
  $('#reviewing').addEventListener('click', () =>
    document.body.classList.toggle('show-review'));
  $('#f-size').addEventListener('change', applyFilters);
  $$('.f-kind').forEach(b => b.addEventListener('change', applyFilters));
  $('#f-clear').addEventListener('click', () => {
    $('#f-size').value = 'all';
    $$('.f-kind').forEach(b => (b.checked = false));
    applyFilters();
  });
  /* Summary rows jump to their scene. The target may be filtered out of view, in
     which case the jump would silently do nothing — so clear the filters first,
     then scroll and flash so the eye lands on the right card. */
  $$('a.jump').forEach(link => link.addEventListener('click', ev => {
    const target = document.getElementById(link.hash.slice(1));
    if (!target) return;
    ev.preventDefault();
    const group = target.closest('.sizegroup');
    if (target.hidden || (group && group.hidden)) {
      $('#f-size').value = 'all';
      $$('.f-kind').forEach(b => (b.checked = false));
      applyFilters();
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    $$('.case.flash').forEach(c => c.classList.remove('flash'));
    target.classList.add('flash');
    setTimeout(() => target.classList.remove('flash'), 1400);
    history.replaceState(null, '', link.hash);
  }));

  $('#export').addEventListener('click', exportReview);
  $('#export-copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('#export-text').value);
          $('#export-copy').textContent = 'Copied'; }
    catch (e) { $('#export-text').select(); }
  });

  $$('.case').forEach(card => {
    const id = card.dataset.scene;
    const r = entry(id);
    $$('input[type=radio]', card).forEach(radio => {
      radio.checked = Number(radio.value) === r.rating;
      radio.addEventListener('change', () => {
        entry(id).rating = Number(radio.value);
        persist();
      });
    });
    const note = $('textarea', card);
    note.value = r.comment || '';
    note.addEventListener('input', () => { entry(id).comment = note.value; persist(); });
    $('.clear-one', card).addEventListener('click', () => {
      delete review[id];
      $$('input[type=radio]', card).forEach(x => (x.checked = false));
      note.value = '';
      persist();
    });
  });

  /* Expand: clone this card's `.scene` (art + bounds overlay, so the
     `show-bounds` toggle still applies) into the oversized dialog. Cloning
     rather than moving the node means the card behind the dialog stays intact
     and reusable if the dialog is opened again for a sibling variant. */
  $$('.expand-btn').forEach(btn => btn.addEventListener('click', () => {
    const card = btn.closest('.case');
    const label = $('.composer-label', card);
    const expandLabel = $('#expand-label');
    if (label) { expandLabel.textContent = label.textContent; expandLabel.hidden = false; }
    else { expandLabel.hidden = true; }
    $('#expand-title').textContent = card.dataset.scene;
    const body = $('#expand-body');
    body.replaceChildren();
    body.appendChild($('.scene', card).cloneNode(true));
    $('#expand-dialog').showModal();
  }));

  refreshCounts();
  applyFilters();
});
"""

# Must match `.scene pre` in the stylesheet: the overlay is positioned in these
# units, so a change here without a change there slides every rectangle.
_CELL_H = 13.44  # px per line (12px font x 1.12 line-height)


# Glyphs the common monospace faces tend not to carry, so the browser resolves them
# through a proportional fallback and the row shears. Measured against the fonts on
# a stock Linux box: DejaVu Sans Mono covers every glyph this art uses except the
# hexagon; Source Code Pro misses ten, Ubuntu Mono thirty-nine. Pinning these to one
# cell costs a span each and makes the grid hold whatever the reader has installed.
_FALLBACK_RISK = "⬢✦✧☼≡▪◦∙►"


def _pin_wide_glyphs(fragment: str) -> str:
    """Wrap fallback-prone glyphs so each still occupies exactly one cell.

    Safe as a plain substitution: these characters only ever appear in the art's
    text nodes, never inside a tag or attribute of the exported fragment.
    """
    for ch in _FALLBACK_RISK:
        fragment = fragment.replace(ch, f'<span class=fb>{ch}</span>')
    return fragment


def _attr_json(value: object) -> str:
    """JSON safe to sit inside a double-quoted HTML attribute."""
    return html.escape(json.dumps(value, separators=(",", ":")), quote=True)


def _review_html(sid: str) -> str:
    """The per-scene rating + comment panel (hidden until Review mode is on)."""
    stars = "".join(
        f'<label class="{"low" if n <= 2 else ""}">'
        f'<input type=radio name="r-{html.escape(sid, quote=True)}" value="{n}">{n}'
        f"</label>"
        for n in range(1, 6))
    return (
        "<aside class=review>"
        "<h4>Rate this scene</h4>"
        f"<div class=rate>{stars}</div>"
        "<p class=scale-hint>1 worst · 5 best</p>"
        "<h4>Complaint</h4>"
        "<textarea placeholder='What is wrong here? e.g. port reads as a peer of "
        "the ship; disc clips too hard on the right.'></textarea>"
        "<button type=button class=clear-one>clear</button>"
        "</aside>")


def _bounds_html_entries(entries: list[tuple[str, int, int, int, int]]) -> str:
    """Absolute-positioned rectangles on each object's exact placed footprint."""
    boxes = []
    for kind, x0, y0, x1, y1 in entries:
        boxes.append(
            f'<div class="bound k-{kind}" data-k="{html.escape(kind)} '
            f'{x1 - x0}x{y1 - y0}" style="left:{x0}ch;top:{y0 * _CELL_H:.2f}px;'
            f'width:{x1 - x0}ch;height:{(y1 - y0) * _CELL_H:.2f}px"></div>')
    return f'<div class=bounds>{"".join(boxes)}</div>'


def _bounds_html(composer: _SceneComposer) -> str:
    return _bounds_html_entries(list(composer.sprite_rects))


def _card_html(sid: str, name: str, w: int, h: int, art: Text, drawn: dict[str, Measured],
               flags: list[str], refs: list[str], bounds: list[tuple[str, int, int, int, int]],
               composer_label: str | None) -> tuple[str, set[str]]:
    """One reviewable `.case` card, shared by every composer variant.

    Returns the card's HTML plus the sprite kinds it drew (for the kind
    filter). `composer_label`, when given, stamps which composer produced
    this cell — used only in compare mode, where several cards share one
    scene/size pairing.
    """

    console = Console(width=w, record=True, file=io.StringIO(),
                      force_terminal=True, color_system="truecolor")
    console.print(art)
    frag = _pin_wide_glyphs(console.export_html(
        inline_styles=True, code_format='<pre style="margin:0">{code}</pre>'))
    dims = "  ".join(
        f"{k}&nbsp;{m.width}x{m.height}" + (f"&nbsp;x{m.count}" if m.count > 1 else "")
        for k, m in sorted(drawn.items(), key=lambda kv: _RANK.get(kv[0], 9)))
    flag_html = (
        "<ul class=flags>" + "".join(f"<li>{html.escape(f)}</li>" for f in flags) + "</ul>"
        if flags else "<div class=clean>hierarchy holds</div>")
    refs_html = "".join(f"<li>{html.escape(r)}</li>" for r in refs)
    kinds = sorted(drawn)
    data = (
        f'data-scene="{html.escape(sid, quote=True)}" '
        f'data-case="{html.escape(name, quote=True)}" '
        f'data-size="{w}x{h}" '
        f'data-kinds="{html.escape(" ".join(kinds), quote=True)}" '
        f'data-measured="{_attr_json({k: f"{m.width}x{m.height}" for k, m in drawn.items()})}" '
        f'data-flags="{_attr_json(flags)}" '
        f'data-sprites="{_attr_json(refs)}"')
    label_html = (f'<div class=composer-label>{html.escape(composer_label)}</div>'
                  if composer_label else "")
    expand_btn = (
        '<button type=button class=expand-btn title="Expand to full size" '
        'aria-label="Expand to full size">&#10530;</button>')
    card = (
        f"<div class='case {'flagged' if flags else 'ok'}' id=\"{_slug(sid)}\" {data}>"
        f"<header>{label_html}<h3>{html.escape(sid)}</h3>"
        f"<span class=dims>{dims}</span>{expand_btn}</header>"
        f"<div class=body>"
        f"<div class=main>"
        f"<div class=scene>{frag}{_bounds_html_entries(bounds)}</div>{flag_html}"
        f"<details class=refs><summary>sprite ids "
        f"({len(refs)})</summary><ul>{refs_html}</ul></details>"
        f"</div>"
        f"{_review_html(sid)}"
        f"</div></div>")
    return card, set(kinds)


_COMPOSER_LABEL = {
    "legacy": "Legacy (_SceneComposer)",
    "fixed_fov_perspective": "New pipeline — FixedFovPerspective",
    "depth_layered_anchor": "New pipeline — DepthLayeredAnchorProjection",
}


def _render_html(cfg: SceneArtConfig, chosen: dict[str, SectorDTO],
                 sizes: tuple[tuple[str, int, int], ...], *,
                 composer: str = DEFAULT_COMPOSER, compare: bool = False) -> str:
    """Build the gallery page.

    `composer` selects which single composer renders every cell when
    `compare` is off (WP-SC09's dev switch; defaults to `legacy`, matching
    live play). `compare=True` ignores `composer` and instead renders every
    case through all three composers side by side, from identical DTO,
    tuning/catalogue, and viewport inputs — legacy vs both new-pipeline
    `ProjectionStrategy` implementations, so neither is hidden.
    """

    rows: list[str] = []
    body: list[str] = []
    all_kinds: set[str] = set()
    variants = COMPOSERS if compare else (composer,)
    # Grouped by canvas size: comparing the same composition across sizes is the
    # slow read, but comparing every composition *at one size* is how you judge
    # whether the hierarchy holds — so size is the outer axis.
    for label, w, h in sizes:
        cards: list[str] = []
        for name, sector in chosen.items():
            variant_cards: list[str] = []
            summary_flags: list[str] = []
            summary_sid = variant_scene_id(name, w, h, "legacy" if compare else composer)
            for variant in variants:
                if variant == "legacy":
                    scene_composer, art, drawn, flags = measure(sector, cfg, w, h)
                    bounds = list(scene_composer.sprite_rects)
                    refs = [r.ref for r in scene_composer.render_log]
                else:
                    result = render_physical(sector, _STRATEGIES[variant], w, h)  # type: ignore[arg-type]
                    art, drawn, flags = result.art, result.drawn, result.flags
                    bounds, refs = result.bounds, result.refs
                sid = variant_scene_id(name, w, h, variant)
                card, kinds = _card_html(
                    sid, name, w, h, art, drawn, flags, refs, bounds,
                    _COMPOSER_LABEL[variant] if compare else None)
                variant_cards.append(card)
                all_kinds.update(kinds)
                if variant == ("legacy" if compare else composer):
                    summary_flags = flags
            if compare:
                cards.append(
                    f'<div class=variant-group id="{_slug(summary_sid)}-group" '
                    f'data-scene="{html.escape(summary_sid, quote=True)}">'
                    f"<h3>{html.escape(name)} @ {w}x{h}</h3>"
                    f'<div class=variant-row>{"".join(variant_cards)}</div></div>')
            else:
                cards.append(variant_cards[0])
            jump_target = f"{_slug(summary_sid)}-group" if compare else _slug(summary_sid)
            rows.append(
                f'<tr><td class=n><a class=jump href="#{jump_target}">'
                f"{html.escape(summary_sid)}</a></td>"
                f"<td class='n {'bad' if summary_flags else ''}'>"
                f"<span class='count {'zero' if not summary_flags else ''}'>"
                f"{len(summary_flags)}</span></td>"
                f"<td>{html.escape(summary_flags[0]) if summary_flags else ''}</td></tr>")
        body.append(
            f'<section class=sizegroup data-size="{w}x{h}">'
            f"<h2>{html.escape(label)}</h2>{''.join(cards)}</section>")

    total = sum(1 for r in rows if "class=count zero" not in r)
    size_opts = "".join(f'<option value="{w}x{h}">{html.escape(lbl)}</option>'
                        for lbl, w, h in sizes)
    kind_boxes = "".join(
        f'<label class="k-{k}"><input type=checkbox class=f-kind value="{k}">{k}</label>'
        for k in sorted(all_kinds, key=lambda k: _RANK.get(k, 9)))
    # A complete document, not a fragment: the scene art is box-drawing and
    # block-element characters, so without a declared charset the browser falls
    # back to a locale default and every glyph arrives as mojibake ("â–ˆ" for "█").
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sector Scene Gallery</title>
<style>{_PAGE_CSS}</style>
</head>
<body>
<div class=wrap>
<h1>Sector Scene Gallery</h1>
<p class=sub>Every composition the arrival view can take, at four canvas sizes,
measured against the scale hierarchy.</p>
<p class=lede>The hierarchy under test is
<b>planet &gt;&gt; Stardock &gt; starbase &gt; port &gt; ship</b>. Sizes shown are the
<b>inked rects the composer actually placed</b>, not the boxes it requested — the
sprite library quantises every box to an authored tier and centres the result, so
the requested box routinely overstates what you see. Flags mark where two kinds read
as peers, where a sprite fell to its lowest rung, or where an object found no sky.</p>
<div class=toolbar>
  <button type=button id=bounds>Sprite bounds</button>
  <button type=button id=reviewing>Review mode</button>
  <button type=button id=export disabled>Export complaints (<span id=review-count>0</span>)</button>
  <div class=legend>
    <i class=k-planet>planet</i><i class=k-discovery>discovery</i>
    <i class=k-stardock>stardock</i><i class=k-starbase>starbase</i>
    <i class=k-port>port</i><i class=k-ship>ship</i>
  </div>
</div>
<div class=filters>
  <label for=f-size>canvas</label>
  <select id=f-size><option value=all>all sizes</option>{size_opts}</select>
  <label>must contain</label>
  <div class=kinds>{kind_boxes}</div>
  <button type=button id=f-clear class=linkish>reset</button>
  <span class=tally><span id=shown>{len(rows)}</span> scenes shown</span>
</div>
<h2>Summary</h2>
<table><thead><tr><th>scene id</th><th>flags</th><th>first conflict</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<p class=sub style="margin-top:10px">{total} of {len(rows)} combinations carry at
least one conflict.</p>
{''.join(body)}
</div>
<dialog id=export-dialog>
  <header>Complaints</header>
  <div class=pad>
    <textarea id=export-text readonly></textarea>
  </div>
  <footer>
    <button type=button id=export-copy>Copy</button>
    <a id=export-download download=scene-complaints.json>Download JSON</a>
    <button type=button onclick="this.closest('dialog').close()">Close</button>
  </footer>
</dialog>
<dialog id=expand-dialog>
  <header>
    <div>
      <span id=expand-label class=composer-label hidden></span>
      <h3 id=expand-title style="margin:2px 0 0"></h3>
    </div>
    <button type=button onclick="this.closest('dialog').close()">Close</button>
  </header>
  <div class=pad id=expand-body></div>
</dialog>
<script>{_PAGE_JS}</script>
</body>
</html>"""


# Addresses that mean "every interface" — bindable, but not browsable, so the URL
# printed and opened has to name a concrete host instead.
_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "*", ""})


def _serve(page: str, port: int, *, host: str = "127.0.0.1",
           open_browser: bool = True) -> None:
    """Serve the gallery from a private temp dir over HTTP.

    Defaults to loopback and a temp directory: this is a local debugging view of
    unreleased art, so by default it neither leaves the machine nor lands in the
    working tree. `host` widens that deliberately — a container, VM, WSL, or remote
    dev box has to bind an address the browser can actually reach. There is no
    authentication, so anything that can route to `host:port` can read the page;
    the directory holds only this one self-contained file, but treat a non-loopback
    bind as publishing the art to your network.
    """
    import http.server
    import socket
    import tempfile
    import webbrowser

    with tempfile.TemporaryDirectory(prefix="edge-scene-gallery-") as tmp:
        (Path(tmp) / "index.html").write_text(page, encoding="utf-8")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a: object, **kw: object) -> None:
                super().__init__(*a, directory=tmp, **kw)  # type: ignore[arg-type]

            def guess_type(self, path: object) -> str:
                # `mimetypes` yields a bare "text/html" with no charset, which
                # leaves the browser guessing — and it guesses a locale default,
                # turning every block-drawing glyph in the art into mojibake. The
                # document declares utf-8 too; this makes the header agree.
                kind = super().guess_type(path)  # type: ignore[arg-type]
                return f"{kind}; charset=utf-8" if kind.startswith("text/") else kind

            def log_message(self, fmt: str, *a: object) -> None:
                pass  # the request log is noise here; failures still raise

        wildcard = host in _WILDCARD_HOSTS
        browse_host = (socket.gethostname() if wildcard else host)
        # A bare IPv6 literal needs brackets in a URL; a hostname never does.
        if ":" in browse_host and not browse_host.startswith("["):
            browse_host = f"[{browse_host}]"
        url = f"http://{browse_host}:{port}/"
        try:
            server_cls = http.server.ThreadingHTTPServer
            if ":" in host and host not in ("", "*"):  # IPv6 literal
                server_cls = type("_V6", (http.server.ThreadingHTTPServer,),
                                  {"address_family": socket.AF_INET6})
            server = server_cls((("" if host == "*" else host), port), Handler)
        except OSError as exc:
            raise SystemExit(
                f"cannot bind {host}:{port} ({exc}). "
                f"Try another port (--serve 8899) or host (--host 0.0.0.0)."
            ) from exc
        reach = ("all interfaces" if wildcard
                 else "local only" if host in ("127.0.0.1", "localhost", "::1")
                 else "network-reachable")
        print(f"scene gallery on {url}  ({reach} — Ctrl-C to stop)", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
        finally:
            server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", help="only this case (see --list)")
    parser.add_argument("--size", help="only WxH, e.g. 150x52")
    parser.add_argument("--list", action="store_true", help="list case names")
    parser.add_argument("--html", type=Path, help="write the gallery to this path")
    # 8765 belongs to `pixi run serve` (the game's own web client), so the gallery
    # sits one port along and the two can run side by side.
    parser.add_argument("--serve", nargs="?", type=int, const=8766, metavar="PORT",
                        help="serve the gallery on PORT (default 8766) until "
                             "interrupted")
    parser.add_argument("--host", default="127.0.0.1", metavar="ADDR",
                        help="address to bind (default 127.0.0.1, local only). "
                             "Use 0.0.0.0 to reach it from another machine — the "
                             "page is unauthenticated, so that publishes it to "
                             "your network.")
    parser.add_argument("--no-open", action="store_true",
                        help="with --serve, do not launch a browser")
    # WP-SC09 dev switch: defaults to the legacy composer, matching live play.
    # `--compare` ignores `--composer` and renders all three side by side.
    parser.add_argument("--composer", choices=COMPOSERS, default=DEFAULT_COMPOSER,
                        help=f"which composer renders each cell (default: "
                             f"{DEFAULT_COMPOSER}, matching live play)")
    parser.add_argument("--compare", action="store_true",
                        help="A/B/C: render every case through legacy, "
                             "FixedFovPerspective, and DepthLayeredAnchorProjection "
                             "side by side, from identical inputs")
    args = parser.parse_args()

    chosen = cases()
    if args.list:
        print("\n".join(chosen))
        return
    if args.case:
        chosen = {args.case: chosen[args.case]}
    sizes = SIZES
    if args.size:
        sw, _, sh = args.size.partition("x")
        sizes = ((args.size, int(sw), int(sh)),)

    cfg = SceneArtConfig()
    n_variants = len(COMPOSERS) if args.compare else 1
    if args.serve is not None or args.html:
        # Rendering every scene twice over (measure, then colour-capture) takes the
        # better part of a minute at full matrix size; say so rather than look hung.
        print(f"building {len(chosen) * len(sizes) * n_variants} scenes "
              f"({len(chosen)} compositions x {len(sizes)} sizes"
              f"{' x 3 composers' if args.compare else ''})...", flush=True)
    if args.serve is not None:
        _serve(_render_html(cfg, chosen, sizes, composer=args.composer,
                            compare=args.compare),
               args.serve, host=args.host, open_browser=not args.no_open)
        return
    if args.html:
        args.html.write_text(
            _render_html(cfg, chosen, sizes, composer=args.composer, compare=args.compare),
            encoding="utf-8")
        print(f"wrote {args.html}")
        return

    console = Console()
    for name, sector in chosen.items():
        for _label, w, h in sizes:
            for variant in (COMPOSERS if args.compare else (args.composer,)):
                if variant == "legacy":
                    scene_composer, _art, drawn, flags = measure(sector, cfg, w, h)
                    refs = [r.ref for r in scene_composer.render_log]
                else:
                    result = render_physical(sector, _STRATEGIES[variant], w, h)  # type: ignore[arg-type]
                    drawn, flags, refs = result.drawn, result.flags, result.refs
                dims = "  ".join(f"{k} {m.width}x{m.height}"
                                 for k, m in sorted(drawn.items(),
                                                    key=lambda kv: _RANK.get(kv[0], 9)))
                sid = variant_scene_id(name, w, h, variant)
                console.print(f"[b]{sid}[/]  {dims}")
                for f in flags:
                    console.print(f"   [red]▲[/] {f}")
                if args.case or args.size:  # a focused run is a debugging run
                    for ref in refs:
                        console.print(f"   [dim]·[/] [cyan]{ref}[/]")


if __name__ == "__main__":
    main()
