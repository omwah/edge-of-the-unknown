"""Tests for the closed DTO -> `WorldArrangement` classifier (WP-SC02).

Covers classification correctness per kind, parent-before-position ordering,
permutation invariance (plan §3, §4.1: "Permuting DTO order does not perturb
identity, base arrangement, or priority"), and that fighters/mines never
become retained solver objects (plan §2.5).
"""

from __future__ import annotations

import random
from fractions import Fraction

from edge.core.dto import (
    SectorAnomalyDTO,
    SectorDiscovery,
    SectorDTO,
    SectorForceDTO,
    SectorPlanetDTO,
    SectorPortDTO,
    SectorShipDTO,
    SectorStarbaseDTO,
)
from edge.scene.classify import classify_sector
from edge.scene.geometry import Region
from edge.scene.model import ArtMode, SceneRetention, SceneTuning

_REGION = Region(x_min=-10, x_max=10, y_min=-10, y_max=10, z_min=1, z_max=20)

TUNING = SceneTuning(
    face_extent_by_scale_class={
        "entity": (6, 4),
        "anchor": (30, 15),
        "belt": (40, 8),
        "orbital": (11, 14),
        "ship": (20, 5),
        "wreck": (10, 4),
    },
    region_by_scale_class={
        "entity": _REGION,
        "anchor": _REGION,
        "belt": _REGION,
        "orbital": Region(x_min=-3, x_max=3, y_min=-3, y_max=3, z_min=0, z_max=0),
        "ship": _REGION,
        "wreck": _REGION,
    },
    target_fraction_by_scale_class={
        "entity": Fraction(1, 2),
        "anchor": Fraction(1, 3),
        "belt": Fraction(1, 2),
        "orbital": Fraction(1, 5),
        "ship": Fraction(1, 6),
        "wreck": Fraction(1, 8),
    },
    ink_ratio_by_scale_class={
        "entity": Fraction(9, 10),
        "anchor": Fraction(9, 10),
        "belt": Fraction(9, 10),
        "orbital": Fraction(4, 5),
        "ship": Fraction(4, 5),
        "wreck": Fraction(4, 5),
    },
    structural_mode_thresholds=((150, 52, "wide"), (100, 40, "standard"), (0, 0, "compact")),
    fixed_fov_num=1,
    fixed_fov_den=2,
    cell_aspect=Fraction(2, 1),
    near_plane_su=1,
    depth_layers=6,
    depth_layer_size_su=4,
    depth_layer_scale=Fraction(4, 5),
    camera_height_fraction_min=Fraction(1, 8),
    camera_height_fraction_max=Fraction(3, 4),
    aim_offsets_su=(0, -1, 1, -2, 2),
    max_camera_candidates=32,
    hysteresis_weight_camera=1,
    hysteresis_weight_position=1,
    hysteresis_weight_admission=4,
    hysteresis_weight_art=1,
    max_passes=64,
    edge_margin=1,
    min_projected_cells_by_scale_class={
        "entity": (2, 2), "anchor": (4, 3), "belt": (4, 2),
        "orbital": (2, 2), "ship": (3, 1), "wreck": (2, 1),
    },
    separation_margin=1,
    min_visible_fraction_by_scale_class={
        "entity": Fraction(1, 2), "anchor": Fraction(1, 3), "belt": Fraction(1, 4),
        "orbital": Fraction(1, 2), "ship": Fraction(1, 2), "wreck": Fraction(1, 3),
    },
    cost_budget=1000,
    emergency_ship_ceiling=50,
    max_reposition_candidates=4,
    max_glyph_tries=8,
    glyph_spacing=1,
)


def _sector(
    *,
    ports: list[SectorPortDTO] | None = None,
    planets: list[SectorPlanetDTO] | None = None,
    ships: list[SectorShipDTO] | None = None,
    discoveries: list[SectorDiscovery] | None = None,
    starbases: list[SectorStarbaseDTO] | None = None,
    anomaly: SectorAnomalyDTO | None = None,
    force: SectorForceDTO | None = None,
) -> SectorDTO:
    return SectorDTO(
        region="Test Zone",
        sector_id=42,
        flavor="",
        beacon=None,
        ports=ports or [],
        planets=planets or [],
        ships=ships or [],
        discoveries=discoveries or [],
        anomaly=anomaly,
        starbases=starbases or [],
        force=force,
    )


def _ship(
    name: str,
    *,
    role: str = "fighter",
    contact_id: int | None = 1,
    player_id: int | None = None,
    retention_class: str = "hostile",
    hostility_ordinal: int = 0,
    combat_threat_rank: int = 0,
    archetype_id: str | None = "humanoid_diplomat",
) -> SectorShipDTO:
    return SectorShipDTO(
        name=name,
        role=role,
        archetype_id=archetype_id,
        contact_id=contact_id,
        player_id=player_id,
        retention_class=retention_class,
        hostility_ordinal=hostility_ordinal,
        combat_threat_rank=combat_threat_rank,
    )


# ---------------------------------------------------------------------------
# Per-kind classification correctness
# ---------------------------------------------------------------------------


def test_planet_classifies_as_anchor_circle() -> None:
    dto = _sector(planets=[SectorPlanetDTO(planet_id=1, name="Terra Nova", ptype="terrestrial_warm")])
    arrangement, glyphs = classify_sector(dto, TUNING)
    assert glyphs == ()
    (planet,) = arrangement.objects
    assert planet.scale_class == "anchor"
    assert planet.retention == SceneRetention.ANCHOR
    assert planet.parent is None
    assert planet.occludes is True


def test_asteroid_belt_planet_classifies_as_permeable_belt() -> None:
    dto = _sector(planets=[SectorPlanetDTO(planet_id=1, name="The Rocks", ptype="asteroid_belt")])
    arrangement, _ = classify_sector(dto, TUNING)
    (belt,) = arrangement.objects
    assert belt.scale_class == "belt"
    assert belt.retention == SceneRetention.ANCHOR  # still "planet/body" retention tier
    assert belt.occludes is False


def test_port_parents_to_the_sectors_planet() -> None:
    dto = _sector(
        planets=[SectorPlanetDTO(planet_id=7, name="Terra Nova", ptype="terrestrial_warm")],
        ports=[SectorPortDTO(port_id=3, name="Trade Post", klass="Class 4", is_stardock=False)],
    )
    arrangement, _ = classify_sector(dto, TUNING)
    planet_key = next(o.key for o in arrangement.objects if o.key.tag == "planet")
    port = next(o for o in arrangement.objects if o.key.tag == "port")
    assert port.parent == planet_key
    assert port.scale_class == "orbital"
    assert port.retention == SceneRetention.ORBITAL
    assert port.art_mode is ArtMode.LADDER
    assert port.ladder_key is not None
    assert port.ladder_key.subtype == "trading_port"


def test_stardock_port_selects_stardock_ladder_subtype() -> None:
    dto = _sector(ports=[SectorPortDTO(port_id=1, name="Stardock", klass="Stardock", is_stardock=True)])
    arrangement, _ = classify_sector(dto, TUNING)
    (port,) = arrangement.objects
    assert port.ladder_key is not None
    assert port.ladder_key.subtype == "stardock"


def test_port_with_no_planet_in_sector_has_no_parent() -> None:
    dto = _sector(ports=[SectorPortDTO(port_id=1, name="Trade Post", klass="Class 4", is_stardock=False)])
    arrangement, _ = classify_sector(dto, TUNING)
    (port,) = arrangement.objects
    assert port.parent is None


def test_starbase_parents_to_its_own_planet_id_not_a_default() -> None:
    dto = _sector(
        planets=[
            SectorPlanetDTO(planet_id=1, name="Alpha", ptype="terrestrial_warm"),
            SectorPlanetDTO(planet_id=2, name="Beta", ptype="barren"),
        ],
        starbases=[
            SectorStarbaseDTO(
                starbase_id=9,
                name="Orbital Platform",
                owner="yours",
                operational=True,
                planet_id=2,
            )
        ],
    )
    arrangement, _ = classify_sector(dto, TUNING)
    starbase = next(o for o in arrangement.objects if o.key.tag == "starbase")
    from edge.scene.model import SceneKey

    assert starbase.parent == SceneKey("planet", 2)


def test_ship_uses_wp_sc01_retention_fields_without_recomputing_them() -> None:
    dto = _sector(
        ships=[
            _ship("Raider", retention_class="hostile", hostility_ordinal=0, combat_threat_rank=2),
        ]
    )
    arrangement, _ = classify_sector(dto, TUNING)
    (ship,) = arrangement.objects
    assert ship.retention == SceneRetention.HOSTILE_SHIP
    assert ship.hostility_ordinal == 0
    assert ship.threat_rank == 2
    assert ship.parent is None
    assert ship.art_mode is ArtMode.LADDER


def test_ship_retention_class_mapping_covers_every_dto_value() -> None:
    mapping = {
        "hostile": SceneRetention.HOSTILE_SHIP,
        "neutral": SceneRetention.NEUTRAL_SHIP,
        "friendly": SceneRetention.FRIENDLY_SHIP,
    }
    for retention_class, expected in mapping.items():
        dto = _sector(ships=[_ship("X", retention_class=retention_class, contact_id=99)])
        arrangement, _ = classify_sector(dto, TUNING)
        assert arrangement.objects[0].retention == expected


def test_anchor_discovery_kinds_classify_as_anchor_scale() -> None:
    for kind in ("nebula", "black_hole", "wormhole"):
        dto = _sector(
            discoveries=[
                SectorDiscovery(
                    discovery_id=1, label=f"{kind} label", kind=kind, rarity="Rare", salvageable=True
                )
            ]
        )
        arrangement, _ = classify_sector(dto, TUNING)
        (obj,) = arrangement.objects
        assert obj.scale_class == "anchor"
        assert obj.retention == SceneRetention.ANCHOR
        assert obj.key.tag == "discovery"


def test_wreck_discovery_classifies_as_wreck_scale() -> None:
    dto = _sector(
        discoveries=[
            SectorDiscovery(discovery_id=2, label="a wreck", kind="wreck", rarity="Common", salvageable=True)
        ]
    )
    arrangement, _ = classify_sector(dto, TUNING)
    (obj,) = arrangement.objects
    assert obj.scale_class == "wreck"
    assert obj.retention == SceneRetention.WRECK
    assert obj.key.tag == "wreck"


def test_surface_site_discovery_kinds_are_not_sector_scene_objects() -> None:
    dto = _sector(
        discoveries=[
            SectorDiscovery(discovery_id=3, label="Ruins", kind="ruins", rarity="Rare", salvageable=True)
        ]
    )
    arrangement, _ = classify_sector(dto, TUNING)
    assert arrangement.objects == ()


def test_entity_classifies_as_top_retention_and_optional_destination() -> None:
    dto = _sector(anomaly=SectorAnomalyDTO(label="A Presence", contact_id=5, contactable=True))
    arrangement, _ = classify_sector(dto, TUNING)
    (entity,) = arrangement.objects
    assert entity.retention == SceneRetention.ENTITY
    assert entity.destination == "entity:5"

    dto_not_contactable = _sector(
        anomaly=SectorAnomalyDTO(label="A Presence", contact_id=5, contactable=False)
    )
    arrangement2, _ = classify_sector(dto_not_contactable, TUNING)
    assert arrangement2.objects[0].destination is None


def test_absent_entity_produces_no_entity_object() -> None:
    dto = _sector()
    arrangement, _ = classify_sector(dto, TUNING)
    assert not any(o.key.tag == "entity" for o in arrangement.objects)


# ---------------------------------------------------------------------------
# Glyphs are free-cell consumers, never retained PhysicalObjects
# ---------------------------------------------------------------------------


def test_fighters_and_mines_never_become_physical_objects() -> None:
    dto = _sector(force=SectorForceDTO(owner="yours", yours=True, fighters=5, mode="defensive", toll=0, armid_mines=3, limpet_mines=2))
    arrangement, glyphs = classify_sector(dto, TUNING)
    assert arrangement.objects == ()
    assert not any(o.art_mode is ArtMode.GLYPH for o in arrangement.objects)
    counts = {g.count for g in glyphs}
    assert counts == {5, 5}  # 5 fighters, 3+2=5 mines


def test_zero_fighters_and_mines_produce_no_glyph_requests() -> None:
    dto = _sector(force=SectorForceDTO(owner="yours", yours=True, fighters=0, mode="defensive", toll=0, armid_mines=0, limpet_mines=0))
    _, glyphs = classify_sector(dto, TUNING)
    assert glyphs == ()


def test_no_force_produces_no_glyph_requests() -> None:
    dto = _sector()
    _, glyphs = classify_sector(dto, TUNING)
    assert glyphs == ()


# ---------------------------------------------------------------------------
# Parent-before-position ordering
# ---------------------------------------------------------------------------


def test_orbital_placement_is_an_offset_from_its_parents_placement() -> None:
    dto = _sector(
        planets=[SectorPlanetDTO(planet_id=1, name="Terra Nova", ptype="terrestrial_warm")],
        ports=[SectorPortDTO(port_id=1, name="Trade Post", klass="Class 4", is_stardock=False)],
    )
    arrangement, _ = classify_sector(dto, TUNING)
    by_key = {p.key: p for p in arrangement.placements}
    planet_key = next(o.key for o in arrangement.objects if o.key.tag == "planet")
    port_key = next(o.key for o in arrangement.objects if o.key.tag == "port")
    planet_pos = by_key[planet_key].position
    port_pos = by_key[port_key].position
    orbital_region = TUNING.region_by_scale_class["orbital"]
    assert orbital_region.x_min <= port_pos.x - planet_pos.x <= orbital_region.x_max
    assert orbital_region.y_min <= port_pos.y - planet_pos.y <= orbital_region.y_max


# ---------------------------------------------------------------------------
# Permutation invariance (plan §4.1 verification)
# ---------------------------------------------------------------------------


def _big_sector() -> SectorDTO:
    return _sector(
        planets=[
            SectorPlanetDTO(planet_id=1, name="Alpha", ptype="terrestrial_warm"),
            SectorPlanetDTO(planet_id=2, name="Beta", ptype="asteroid_belt"),
        ],
        ports=[
            SectorPortDTO(port_id=1, name="Trade Post", klass="Class 4", is_stardock=False),
            SectorPortDTO(port_id=2, name="Stardock", klass="Stardock", is_stardock=True),
        ],
        starbases=[
            SectorStarbaseDTO(starbase_id=1, name="Platform A", owner="yours", operational=True, planet_id=1),
        ],
        ships=[
            _ship("Raider", contact_id=1, retention_class="hostile", hostility_ordinal=0, combat_threat_rank=2),
            _ship("Trader", contact_id=2, retention_class="friendly", hostility_ordinal=1, combat_threat_rank=0),
            _ship("Watcher", contact_id=3, retention_class="neutral", hostility_ordinal=2, combat_threat_rank=1),
        ],
        discoveries=[
            SectorDiscovery(discovery_id=1, label="Nebula", kind="nebula", rarity="Rare", salvageable=True),
            SectorDiscovery(discovery_id=2, label="Wreck", kind="wreck", rarity="Common", salvageable=True),
        ],
        anomaly=SectorAnomalyDTO(label="A Presence", contact_id=99, contactable=True),
        force=SectorForceDTO(owner="yours", yours=True, fighters=4, mode="defensive", toll=0, armid_mines=1, limpet_mines=0),
    )


def _canonical(arrangement: object, glyphs: object) -> tuple[object, object]:
    from edge.scene.model import WorldArrangement

    assert isinstance(arrangement, WorldArrangement)
    return (
        tuple((o.key, o.parent, o.scale_class, o.retention, o.face) for o in arrangement.objects),
        tuple((p.key, p.position) for p in arrangement.placements),
    ), glyphs


def test_permuting_every_dto_container_produces_an_identical_result() -> None:
    base = _big_sector()
    baseline_arrangement, baseline_glyphs = classify_sector(base, TUNING)
    baseline = _canonical(baseline_arrangement, baseline_glyphs)

    rng = random.Random(1234)
    for _ in range(20):
        shuffled = _sector(
            planets=rng.sample(base.planets, k=len(base.planets)),
            ports=rng.sample(base.ports, k=len(base.ports)),
            starbases=rng.sample(base.starbases, k=len(base.starbases)),
            ships=rng.sample(base.ships, k=len(base.ships)),
            discoveries=rng.sample(base.discoveries, k=len(base.discoveries)),
            anomaly=base.anomaly,
            force=base.force,
        )
        arrangement, glyphs = classify_sector(shuffled, TUNING)
        assert _canonical(arrangement, glyphs) == baseline
