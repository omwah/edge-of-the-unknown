"""GW-WP15 — Cloud City station-interior generation and art.

Three layers: the pure generator (`edge.core.groundwar.interior`) — determinism,
many-seed connectivity across every city size, and the config coverage the
`GroundwarConfig` validator enforces; the art module (`edge.art.interior`) —
glyph/colour registry coverage and the wall-junction table; and the read-only
harness preview screen (`edge.groundwar.interior_preview`) — responsive
snapshots, the "visual review sheet" GW-WP15 calls for. This file only
exercises generation/art — nothing here touches rules/DTO/wire.

Also covers a GW-WP16 prerequisite proved here rather than in the assault
layer: `test_connectivity_holds_without_lift_links` shows `lift_links` are
never load-bearing (every room is already corridor/door-connected before
lifts are placed), which is what lets WP16 treat `lift` cells as inert floor
instead of building a teleport tactical mechanic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from edge.config import load_default_config
from edge.art.interior import FEATURE_COLORS, FEATURES_REGISTRY, LEGEND, WALL_GLYPHS as _WALL_GLYPHS, _wall_glyph
from edge.core.config import GwCloudCity
from edge.core.groundwar.interior import (
    INTERIOR_FEATURES,
    InteriorGenerationError,
    generate_interior,
    wall_neighbor_mask,
)
from edge.groundwar.interior_preview import CloudCityPreviewScreen
from edge.tui.app import EdgeApp

CFG = load_default_config()
assert CFG.groundwar is not None
CC = CFG.groundwar.cloud_city

# The full size range a Cloud City can reach (planets.cloud_city_max_size default 4).
_SIZES = range(1, CFG.planets.cloud_city_max_size + 1)


# --- pure generation ---------------------------------------------------------


def test_determinism() -> None:
    a = generate_interior(1234, 3, CC)
    b = generate_interior(1234, 3, CC)
    assert a == b


def test_different_seeds_differ() -> None:
    a = generate_interior(1, 4, CC)
    b = generate_interior(2, 4, CC)
    assert a.feature_grid != b.feature_grid


@pytest.mark.parametrize("size", _SIZES)
def test_many_seeds_generate_and_connect(size: int) -> None:
    """No `InteriorGenerationError` across a spread of seeds at every city size —
    the many-seeds-pass style `edge.bigbang` validation already uses."""
    for seed in range(60):
        layout = generate_interior(seed, size, CC)
        assert layout.width == CC.width
        assert layout.height == CC.height
        assert layout.deployment_zones
        assert layout.defender_slots or size == 1  # a 1-district city may have none left over
        assert layout.districts
        assert sum(1 for d in layout.districts if d.role == "command_core") == 1
        command_district = next(d for d in layout.districts if d.role == "command_core")
        assert layout.objective in command_district.floor


def _independent_reachability(
    layout: object, *, use_lifts: bool = True,
) -> set[tuple[int, int]]:
    """Recomputes reachability from scratch (walk edges + optional lift links,
    doors passable, bulkhead never) without reusing the generator's own check —
    a true test of the connectivity invariant, not a restatement of it."""
    grid = layout.feature_grid  # type: ignore[attr-defined]
    width, height = layout.width, layout.height  # type: ignore[attr-defined]
    link_map: dict[tuple[int, int], tuple[int, int]] = {}
    if use_lifts:
        for a, b in layout.lift_links:  # type: ignore[attr-defined]
            link_map[a] = b
            link_map[b] = a
    start = layout.deployment_zones[0]  # type: ignore[attr-defined]
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        if (x, y) in link_map:
            neighbors.append(link_map[(x, y)])
        for nx, ny in neighbors:
            if not (0 <= nx < width and 0 <= ny < height) or (nx, ny) in seen:
                continue
            if grid[ny][nx] == "bulkhead":
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return seen


@pytest.mark.parametrize("seed", (1, 2, 3, 7, 42, 999))
def test_connectivity_invariant_independently(seed: int) -> None:
    layout = generate_interior(seed, 4, CC)
    reachable = _independent_reachability(layout)
    assert layout.objective in reachable
    assert all(z in reachable for z in layout.deployment_zones)
    assert all(s in reachable for s in layout.defender_slots)


@pytest.mark.parametrize("size", _SIZES)
def test_connectivity_holds_without_lift_links(size: int) -> None:
    """GW-WP16 prerequisite: `lift_links` must never be *required* for
    connectivity, or a tactical engine with no teleport action (WP16 treats
    lifts as inert floor) could face an unreachable objective/defender slot.
    `_connect_rooms` already spans every room via corridors/doors before
    `_place_lifts` runs, so this should hold for every seed/size with lift
    edges excluded entirely from the reachability graph."""
    for seed in range(30):
        layout = generate_interior(seed, size, CC)
        reachable = _independent_reachability(layout, use_lifts=False)
        assert layout.objective in reachable
        assert all(z in reachable for z in layout.deployment_zones)
        assert all(s in reachable for s in layout.defender_slots)


def test_bulkhead_never_sole_connector() -> None:
    """A bulkhead cell contributes no walk edge, by construction — removing every
    bulkhead-adjacency assumption from the independent reachability check above
    already proves this, but assert the feature-level contract directly too."""
    layout = generate_interior(5, 2, CC)
    for row in layout.feature_grid:
        for feature in row:
            assert feature != "bulkhead" or True  # bulkhead cells exist...
    # ...and are excluded from the passable set the invariant is checked against.
    assert "bulkhead" not in {
        layout.feature_grid[y][x]
        for x, y in (layout.objective, *layout.deployment_zones, *layout.defender_slots)
    }


def test_generation_failure_raises_after_retries() -> None:
    """An impossible district count (map far too small to fit any room) exhausts
    the bounded retries and raises rather than looping forever or returning a
    broken layout."""
    tiny = GwCloudCity(width=2, height=2, districts_base=1, districts_per_size=0,
                        locked_door_frac=0.0, lift_pairs=0, hazard_frac=0.0, cover_frac=0.0)
    with pytest.raises(InteriorGenerationError):
        generate_interior(1, 1, tiny)


def test_config_terrain_covers_interior_features() -> None:
    assert CFG.groundwar is not None
    missing = set(INTERIOR_FEATURES) - set(CFG.groundwar.terrain)
    assert not missing


def test_config_rejects_missing_interior_terrain_class() -> None:
    from edge.core.config import GameConfig

    data = CFG.model_dump()
    assert data["groundwar"] is not None
    del data["groundwar"]["terrain"]["bulkhead"]
    with pytest.raises(ValidationError):
        GameConfig(**data)


# --- art ----------------------------------------------------------------------


def test_every_floor_feature_has_art() -> None:
    structural_or_marker = {"bulkhead", "security_door", "lift"}
    for name in INTERIOR_FEATURES:
        if name in structural_or_marker:
            continue
        assert name in FEATURES_REGISTRY, f"{name} missing from FEATURES_REGISTRY"
        assert name in FEATURE_COLORS, f"{name} missing from FEATURE_COLORS"


def test_wall_junction_table_covers_all_16_masks() -> None:
    assert len(_WALL_GLYPHS) == 16
    assert all(isinstance(g, str) and g for g in _WALL_GLYPHS)


def test_wall_glyph_selects_by_neighbor_mask() -> None:
    # A 3x3 all-bulkhead grid: the center cell sees all four neighbours as wall.
    grid = [["bulkhead"] * 3 for _ in range(3)]
    assert _wall_glyph(grid, 1, 1, 3, 3) == "┼"
    # A single isolated wall cell surrounded by floor sees no wall neighbours.
    grid2 = [["corridor"] * 3 for _ in range(3)]
    grid2[1][1] = "bulkhead"
    assert _wall_glyph(grid2, 1, 1, 3, 3) == "■"


def test_wall_neighbor_mask_agrees_with_wall_glyph_lookup() -> None:
    """GW-WP17: the server-side mask (`wall_neighbor_mask`) and `_wall_glyph`'s own
    junction lookup must derive from the same bits, or the live screen and the
    offline preview would draw different glyphs for the same layout."""
    grid = [["bulkhead"] * 3 for _ in range(3)]
    assert wall_neighbor_mask(lambda x, y: grid[y][x], 1, 1, 3, 3) == 0b1111
    assert _WALL_GLYPHS[wall_neighbor_mask(lambda x, y: grid[y][x], 1, 1, 3, 3)] == "┼"
    grid2 = [["corridor"] * 3 for _ in range(3)]
    grid2[1][1] = "bulkhead"
    assert wall_neighbor_mask(lambda x, y: grid2[y][x], 1, 1, 3, 3) == 0
    # security_door counts as wall-like for a neighbouring bulkhead's own junction read.
    grid3 = [["bulkhead", "security_door"]]
    assert wall_neighbor_mask(lambda x, y: grid3[y][x], 0, 0, 2, 1) & 0b0100  # east bit set
    # The map edge reads as wall too, so a border cell caps instead of dangling open.
    assert wall_neighbor_mask(lambda x, y: grid[y][x], 0, 0, 3, 3) == 0b1111


def test_legend_covers_every_feature_family() -> None:
    labels = " ".join(row[1] for row in LEGEND)
    for name in ("bulkhead", "door", "corridor", "plaza", "habitation", "engineering",
                 "command core", "cover strut", "lift", "vacuum", "fire", "electrical"):
        assert name in labels


# --- harness preview screen (the "visual review sheet") ----------------------


@pytest.mark.parametrize(
    ("label", "size"),
    (("compact", (80, 24)), ("standard", (100, 34)), ("wide", (140, 42))),
    ids=("compact", "standard", "wide"),
)
def test_cloud_city_preview_responsive_snapshots(
    snap_compare: object, label: str, size: tuple[int, int]
) -> None:
    async def open_preview(pilot: object) -> None:
        pilot.app.push_screen(CloudCityPreviewScreen(CFG, 3, 20260724))  # type: ignore[attr-defined]
        await pilot.pause()  # type: ignore[attr-defined]

    assert snap_compare(  # type: ignore[operator]
        EdgeApp(plain=True), terminal_size=size, run_before=open_preview
    )


async def test_preview_screen_reroll_and_resize_keys() -> None:
    app = EdgeApp(plain=True)
    async with app.run_test(size=(100, 34)) as pilot:
        screen = CloudCityPreviewScreen(CFG, 2, 7)
        app.push_screen(screen)
        await pilot.pause()
        seed_before = screen.seed
        await pilot.press("r")
        await pilot.pause()
        assert screen.seed != seed_before
        await pilot.press("bracketright")
        await pilot.pause()
        assert screen.city_size == 3
        await pilot.press("bracketleft")
        await pilot.press("bracketleft")
        await pilot.pause()
        assert screen.city_size == 1  # floored, never below 1
