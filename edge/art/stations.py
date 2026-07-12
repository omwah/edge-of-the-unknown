"""Species-archetype port/starbase raster selection and ANSI rendering."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from edge.art.portrait import REPO_ROOT, render_portrait

STATION_ARCHETYPES = frozenset({
    "amorous_imp", "brain_dome_automaton", "canid_technologist",
    "colonial_broodmaster", "cosmic_arbiter", "engineered_aesthete",
    "horned_grudgekeeper", "humanoid_diplomat", "psionic_overlord",
    "ribbon_salvager", "telepath_aristocrat", "temporal_broker",
    "tentacled_envoy", "winged_schemer",
})
PORT_SERVICES = frozenset({"trade"})
STARBASE_SERVICES = frozenset({"status", "station", "trade", "hardware", "bank"})


def station_asset(
    kind: str, archetype_id: str, service: str, *, cinematic: bool,
) -> Path:
    """Return one responsive banner crop; icons remain procedural cell art."""
    if kind not in ("port", "starbase"):
        raise ValueError(f"unknown station kind: {kind}")
    allowed = PORT_SERVICES if kind == "port" else STARBASE_SERVICES
    if service not in allowed:
        raise ValueError(f"unknown {kind} service art: {service}")
    archetype = archetype_id if archetype_id in STATION_ARCHETYPES else "humanoid_diplomat"
    root = REPO_ROOT / "images" / "ui" / ("ports" if kind == "port" else "starbases")
    layout = "wide" if cinematic else "standard"
    return root / "banners" / f"{archetype}_{service}_{layout}.png"


def _treatment(theme: str, condition: str) -> str:
    effects: list[str] = []
    if theme == "edge-high-contrast":
        effects.append("high_contrast")
    elif theme == "edge-monochrome":
        effects.append("monochrome")
    if condition in ("derelict", "hostile"):
        effects.append(condition)
    return "+".join(effects)


def render_station_art(
    kind: str, archetype_id: str, service: str, theme: str, *,
    cinematic: bool, condition: str = "open",
) -> Text:
    cols, rows = (72, 12) if cinematic else (56, 8)
    path = station_asset(kind, archetype_id, service, cinematic=cinematic)
    return render_portrait(path, cols, rows, treatment=_treatment(theme, condition))
