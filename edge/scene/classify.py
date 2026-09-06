"""The closed classification registry: fog-safe DTOs -> `WorldArrangement`.

Plan §3 ("Physical classification") and the WP-SC02 implementation bullet:
"Classify Entity, the one generated open-space discovery (including a
generated sensor-gated wreck), planets/belts, station kinds, runtime wrecks,
ships, and post-projection glyphs through one closed registry. Build parents
before deterministic face positions/depths." and "Encode nominal face-area
scale separately from retention, and treat glyphs as free-cell consumers
rather than retained solver objects."

`classify_sector` is pure and deterministic: no game RNG, no I/O, no
randomness beyond a stable content hash used only to place objects
within their injected region (never to decide *whether* something is
retained, admitted, or projected — that is WP-SC06's job). Permuting the
order of any DTO container is a no-op on the result: every object's
identity, parent, scale, and retention derive from its own stable content,
never from list position, and the returned tuples are always sorted by
`SceneKey`.

No numeric tuning value is invented here. Every face extent and placement
region is looked up from the injected `SceneTuning`, primarily by
`scale_class`, though a planet/anchor-discovery face extent is looked up
first by `continuous_kind` (`SceneTuning.face_extent_by_kind`) when that kind
has an entry, falling back to the scale_class lookup otherwise (plan §2.2);
the *shape* (circle/ellipse/rect/field) and the *scale_class*/*retention*
assignment are categorical decisions already fixed by
`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §2, not tuned numbers.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from edge.core.dto import (
    SectorDiscovery,
    SectorDTO,
    SectorPlanetDTO,
    SectorPortDTO,
    SectorShipDTO,
    SectorStarbaseDTO,
)
from edge.scene.catalog import LadderKey
from edge.scene.geometry import Face, FaceShape, Region, Vec3
from edge.scene.model import (
    ArtMode,
    GlyphRequest,
    PhysicalObject,
    Placement,
    SceneKey,
    SceneRetention,
    SceneTuning,
    WorldArrangement,
)

SCALE_CLASSES: tuple[str, ...] = (
    "entity", "anchor", "belt", "stardock", "starbase", "orbital", "ship", "wreck",
)
"""The closed, plan-fixed set of `scale_class` values this classifier assigns.

`SceneTuning.face_extent_by_scale_class` and `.region_by_scale_class` must
supply an entry for every class this classifier actually reaches at
runtime (fewer, if a sector never contains e.g. a wreck).

`"stardock"` splits the one *headline* station off the shared `"orbital"`
bucket (plan §2.2's `Stardock > starbase > port` ordering, and AGENTS.md's
"Planets & orbital starbases": Stardock is Core Space's flagship location and
the only place full subsystem swaps and colonist enlistment happen). It is a
scale class, not a retention tier: Stardock is still `SceneRetention.ORBITAL`
and still competes for admission exactly like any other station. What differs
is its nominal face area, and therefore the projected box it asks for and the
authored rung that box can clear.

`"starbase"` splits off the same shared `"orbital"` bucket for the same
reason, one tier down (WP-SC12). Plan §2.2 orders `Stardock > starbase >
port`, and the legacy composer has always sized a starbase above a port
(`SceneArtConfig.starbase_scale` 0.35 vs `port_scale` 0.3) — but with both
sharing one scale class the physical model could express neither the size
ordering nor the two different station-size parity targets. `"orbital"` now
means an ordinary trading port."""

_ANCHOR_DISCOVERY_KINDS = frozenset({"nebula", "black_hole", "wormhole"})
"""Sector-space anchor-scale phenomena (plan §2.1, §2.2)."""

_WRECK_DISCOVERY_KIND = "wreck"

# Surface-site discovery kinds (ruins/artifact/ancient_tech/crashed_ship) are
# planet-descent finds, never sector-scene objects; anything not named above
# or below is silently skipped rather than guessed at, keeping this a closed
# registry rather than a catch-all.

_SHIP_RETENTION: dict[str, SceneRetention] = {
    "hostile": SceneRetention.HOSTILE_SHIP,
    "neutral": SceneRetention.NEUTRAL_SHIP,
    "friendly": SceneRetention.FRIENDLY_SHIP,
    # Another player's vessel and a not-yet-resolved "unidentified" ship both
    # fall back to the neutral tier: WP-SC01 always fills `retention_class` in
    # for a real projection, so this only matters for legacy fixtures/tests
    # that leave the dataclass default in place.
    "player": SceneRetention.NEUTRAL_SHIP,
    "unidentified": SceneRetention.NEUTRAL_SHIP,
}


def _stable_int(key: str, modulus: int) -> int:
    """A deterministic, seed-free integer in `[0, modulus)` from `key`.

    Not game RNG and not `random.Random` at all: this is a pure function of
    its input string, used only to place a flexible object somewhere inside
    its already-decided allowed region. It never decides admission, ordering,
    or retention — those come from the DTO's own fields. Python's built-in
    `hash()` is deliberately avoided: it is salted per-process
    (`PYTHONHASHSEED`), which would make placement non-reproducible across
    runs; `blake2b` is not.
    """

    if modulus <= 0:
        return 0
    digest = hashlib.blake2b(key.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % modulus


def _stable_offset(region: Region, key: str) -> Vec3:
    x = region.x_min + _stable_int(f"{key}|x", region.x_max - region.x_min + 1)
    y = region.y_min + _stable_int(f"{key}|y", region.y_max - region.y_min + 1)
    z = region.z_min + _stable_int(f"{key}|z", region.z_max - region.z_min + 1)
    return Vec3(x, y, z)


def _face(
    tuning: SceneTuning, scale_class: str, shape: FaceShape, continuous_kind: str | None = None
) -> Face:
    """`continuous_kind`, when given and present in `face_extent_by_kind`,
    overrides the scale-class extent (plan §2.2 per-kind apparent scale)."""
    if continuous_kind is not None and continuous_kind in tuning.face_extent_by_kind:
        width, height = tuning.face_extent_by_kind[continuous_kind]
    else:
        width, height = tuning.face_extent_by_scale_class[scale_class]
    return Face(shape=shape, width_su=width, height_su=height)


def _region(tuning: SceneTuning, scale_class: str) -> Region:
    return tuning.region_by_scale_class[scale_class]


def _planet_object(planet: SectorPlanetDTO, tuning: SceneTuning) -> PhysicalObject:
    is_belt = planet.ptype == "asteroid_belt"
    scale_class = "belt" if is_belt else "anchor"
    shape = FaceShape.FIELD if is_belt else FaceShape.CIRCLE
    return PhysicalObject(
        key=SceneKey("planet", planet.planet_id),
        parent=None,
        face=_face(tuning, scale_class, shape, continuous_kind=planet.ptype),
        scale_class=scale_class,
        art_mode=ArtMode.CONTINUOUS,
        ladder_key=None,
        continuous_kind=planet.ptype,
        archetype_id=planet.archetype_id,
        retention=SceneRetention.ANCHOR,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(tuning, scale_class),
        flexible=False,
        occludes=not is_belt,
        label=planet.name,
        destination=f"planet:{planet.planet_id}",
    )


def _port_ladder_subtype(port: SectorPortDTO) -> str:
    return "stardock" if port.is_stardock else "trading_port"


def _port_object(
    port: SectorPortDTO, tuning: SceneTuning, parent: SceneKey | None
) -> PhysicalObject:
    # `SectorPortDTO.is_stardock` is the only signal distinguishing the
    # flagship from an ordinary trading post, and it already selects a
    # distinct authored ladder (`_port_ladder_subtype`). It now also selects
    # a distinct *scale class*, so the richer ladder is actually reachable --
    # see `SCALE_CLASSES`.
    scale_class = "stardock" if port.is_stardock else "orbital"
    return PhysicalObject(
        key=SceneKey("port", port.port_id),
        parent=parent,
        face=_face(tuning, scale_class, FaceShape.RECT),
        scale_class=scale_class,
        art_mode=ArtMode.LADDER,
        ladder_key=LadderKey(
            kind="port",
            subtype=_port_ladder_subtype(port),
            axis="vertical",
            archetype_id=port.archetype_id or "",
        ),
        continuous_kind=None,
        archetype_id=port.archetype_id or None,
        retention=SceneRetention.ORBITAL,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(tuning, scale_class),
        flexible=True,
        occludes=True,
        label=port.name,
        destination=f"port:{port.port_id}",
    )


def _starbase_scale_class(tuning: SceneTuning) -> str:
    """`"starbase"` where the injected tuning declares it, else `"orbital"`.

    The split is a WP-SC12 addition; a `SceneTuning` built before it (every
    hand-built test fixture, and any caller that has not adopted the new
    class) simply keeps the shared station bucket, exactly as before."""
    return "starbase" if "starbase" in tuning.face_extent_by_scale_class else "orbital"


def _starbase_object(
    starbase: SectorStarbaseDTO, tuning: SceneTuning, parent: SceneKey | None
) -> PhysicalObject:
    scale_class = _starbase_scale_class(tuning)
    return PhysicalObject(
        key=SceneKey("starbase", starbase.starbase_id),
        parent=parent,
        face=_face(tuning, scale_class, FaceShape.RECT),
        scale_class=scale_class,
        art_mode=ArtMode.LADDER,
        ladder_key=LadderKey(
            kind="port",
            subtype="starbase",
            axis="vertical",
            archetype_id=starbase.archetype_id or "",
        ),
        continuous_kind=None,
        archetype_id=starbase.archetype_id or None,
        retention=SceneRetention.ORBITAL,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(tuning, scale_class),
        flexible=True,
        occludes=True,
        label=starbase.name,
        destination=f"starbase:{starbase.starbase_id}",
    )


def _placement_region(tuning: SceneTuning, obj: PhysicalObject, *, parented: bool) -> Region:
    """Where `obj` may be placed: its parent-relative orbit offset box when it
    has a parent and its class declares one, else its absolute region.

    `edge.scene.solve._absolute_region` applies the identical rule at solve
    time; this is the classifier's matching initial draw, so a station's
    hash-derived starting position is inside the same volume the solver will
    later search."""
    if parented and obj.scale_class in tuning.orbit_offset_region_by_scale_class:
        return tuning.orbit_offset_region_by_scale_class[obj.scale_class]
    return obj.region


def _ship_key(ship: SectorShipDTO) -> SceneKey:
    """A stable identity for a fog-safe ship row.

    The DTO deliberately carries no unique vessel id (AGENTS.md/plan WP-SC01:
    "do not invent a vessel id where the authoritative model has no distinct
    vessel entity"). Two ship rows with identical fog-safe content are
    genuinely indistinguishable to the client, so hashing that content is the
    best available stable key -- and it is exactly as stable as the plan
    requires: unaffected by container order, and identical for two calls with
    the same DTO content.
    """

    signature = "|".join(
        (
            ship.name,
            ship.role,
            ship.archetype_id or "",
            str(ship.contact_id),
            str(ship.player_id),
            ship.retention_class,
            str(ship.hostility_ordinal),
            str(ship.combat_threat_rank),
        )
    )
    ident = int.from_bytes(hashlib.blake2b(signature.encode(), digest_size=8).digest(), "big")
    tag: Literal["ship", "player"] = "player" if ship.player_id is not None else "ship"
    return SceneKey(tag, ident)


def _ship_object(ship: SectorShipDTO, tuning: SceneTuning) -> PhysicalObject:
    key = _ship_key(ship)
    return PhysicalObject(
        key=key,
        parent=None,
        face=_face(tuning, "ship", FaceShape.RECT),
        scale_class="ship",
        art_mode=ArtMode.LADDER,
        ladder_key=LadderKey(
            kind="ship",
            subtype=(ship.art_subtype or ship.role).lower(),
            axis="horizontal",
            archetype_id=ship.archetype_id or "",
        ),
        continuous_kind=None,
        archetype_id=ship.archetype_id or None,
        retention=_SHIP_RETENTION.get(ship.retention_class, SceneRetention.NEUTRAL_SHIP),
        hostility_ordinal=ship.hostility_ordinal,
        threat_rank=ship.combat_threat_rank,
        region=_region(tuning, "ship"),
        flexible=True,
        occludes=True,
        label=ship.name,
        destination=f"ship:{key.ident}",
    )


def _anchor_discovery_object(disc: SectorDiscovery, tuning: SceneTuning) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("discovery", disc.discovery_id),
        parent=None,
        face=_face(tuning, "anchor", FaceShape.ELLIPSE, continuous_kind=disc.kind),
        scale_class="anchor",
        art_mode=ArtMode.CONTINUOUS,
        ladder_key=None,
        continuous_kind=disc.kind,
        archetype_id=None,
        # No ownership/species association exists on `SectorDiscovery` today (plan §9.7
        # gap fix): a nebula/black hole/wormhole is not associated with any species or
        # alliance at the DTO level, so this is a principled `None`, not an omission.
        retention=SceneRetention.ANCHOR,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(tuning, "anchor"),
        flexible=False,
        occludes=True,
        label=disc.name or disc.label,
        destination=f"discovery:{disc.discovery_id}",
    )


def _wreck_object(disc: SectorDiscovery, tuning: SceneTuning) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("wreck", disc.discovery_id),
        parent=None,
        face=_face(tuning, "wreck", FaceShape.RECT),
        scale_class="wreck",
        art_mode=ArtMode.CONTINUOUS,
        ladder_key=None,
        continuous_kind=disc.kind,
        archetype_id=None,
        # A wreck's `SectorDiscovery` carries no owning-species signal either (plan §9.7
        # gap fix note): principled `None`, not fabricated.
        retention=SceneRetention.WRECK,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(tuning, "wreck"),
        flexible=True,
        occludes=True,
        label=disc.name or disc.label,
        destination=f"discovery:{disc.discovery_id}",
    )


def _entity_object(dto: SectorDTO, tuning: SceneTuning) -> PhysicalObject | None:
    dto_anomaly = dto.anomaly
    if dto_anomaly is None:
        return None
    return PhysicalObject(
        key=SceneKey("entity", dto_anomaly.contact_id),
        parent=None,
        face=_face(tuning, "entity", FaceShape.RECT),
        scale_class="entity",
        art_mode=ArtMode.CONTINUOUS,
        ladder_key=None,
        continuous_kind="entity",
        archetype_id=None,
        # The generated Entity carries no species/owner association at the DTO level
        # (`SectorAnomalyDTO` has none) -- principled `None`, not fabricated.
        retention=SceneRetention.ENTITY,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(tuning, "entity"),
        flexible=False,
        occludes=True,
        label=dto_anomaly.label,
        destination=f"entity:{dto_anomaly.contact_id}" if dto_anomaly.contactable else None,
    )


def _placement_order(objects: tuple[PhysicalObject, ...]) -> list[SceneKey]:
    """Parents before children, each tier sorted by `SceneKey` (plan bullet
    "build parents before deterministic face positions/depths").

    WP-SC02's classification hierarchy is exactly two levels deep (a planet,
    then the orbital infrastructure parented to it), so two sorted tiers are
    sufficient; a deeper hierarchy would need a real topological sort.
    """

    roots = sorted(obj.key for obj in objects if obj.parent is None)
    children = sorted(obj.key for obj in objects if obj.parent is not None)
    return [*roots, *children]


def _glyph_requests(dto: SectorDTO) -> tuple[GlyphRequest, ...]:
    force = dto.force
    if force is None:
        return ()
    requests: list[GlyphRequest] = []
    if force.fighters > 0:
        ident = _stable_int(f"{dto.sector_id}|fighters", 2**63)
        requests.append(GlyphRequest(key=SceneKey("glyph", ident), count=force.fighters))
    mines = force.armid_mines + force.limpet_mines
    if mines > 0:
        ident = _stable_int(f"{dto.sector_id}|mines", 2**63)
        requests.append(GlyphRequest(key=SceneKey("glyph", ident), count=mines))
    requests.sort(key=lambda g: g.key)
    return tuple(requests)


def classify_sector(
    dto: SectorDTO, tuning: SceneTuning
) -> tuple[WorldArrangement, tuple[GlyphRequest, ...]]:
    """Classify one fog-safe sector DTO into a `WorldArrangement` plus glyphs.

    Deterministic and order-independent: the same DTO content always produces
    the same result, and shuffling any of `dto.ports`, `dto.planets`,
    `dto.ships`, `dto.discoveries`, or `dto.starbases` never changes it.
    """

    objects: list[PhysicalObject] = []

    planet_keys: dict[int, SceneKey] = {
        planet.planet_id: SceneKey("planet", planet.planet_id) for planet in dto.planets
    }
    default_planet_id = min(planet_keys) if planet_keys else None
    default_planet_key = planet_keys[default_planet_id] if default_planet_id is not None else None

    for planet in sorted(dto.planets, key=lambda p: p.planet_id):
        objects.append(_planet_object(planet, tuning))

    for port in sorted(dto.ports, key=lambda p: p.port_id):
        objects.append(_port_object(port, tuning, default_planet_key))

    for starbase in sorted(dto.starbases, key=lambda s: s.starbase_id):
        parent = (
            planet_keys.get(starbase.planet_id)
            if starbase.planet_id is not None
            else default_planet_key
        )
        objects.append(_starbase_object(starbase, tuning, parent))

    for ship in sorted(dto.ships, key=_ship_key):
        objects.append(_ship_object(ship, tuning))

    for disc in sorted(dto.discoveries, key=lambda d: d.discovery_id):
        if disc.kind in _ANCHOR_DISCOVERY_KINDS:
            objects.append(_anchor_discovery_object(disc, tuning))
        elif disc.kind == _WRECK_DISCOVERY_KIND:
            objects.append(_wreck_object(disc, tuning))
        # else: a planet-descent surface-site kind, or an unrecognized kind --
        # not a sector-scene object; silently skipped (closed registry).

    entity_object = _entity_object(dto, tuning)
    if entity_object is not None:
        objects.append(entity_object)

    objects.sort(key=lambda o: o.key)
    by_key = {obj.key: obj for obj in objects}

    placements: dict[SceneKey, Placement] = {}
    for key in _placement_order(tuple(objects)):
        obj = by_key[key]
        parented = obj.parent is not None and obj.parent in placements
        offset = _stable_offset(
            _placement_region(tuning, obj, parented=parented), f"{key.tag}:{key.ident}"
        )
        if obj.parent is not None and obj.parent in placements:
            parent_position = placements[obj.parent].position
            position = Vec3(
                parent_position.x + offset.x,
                parent_position.y + offset.y,
                parent_position.z + offset.z,
            )
        else:
            position = offset
        placements[key] = Placement(key=key, position=position)

    glyphs = _glyph_requests(dto)
    arrangement = WorldArrangement(
        objects=tuple(objects),
        placements=tuple(placements[obj.key] for obj in objects),
        sector_id=dto.sector_id,
        glyphs=glyphs,
    )
    return arrangement, glyphs
