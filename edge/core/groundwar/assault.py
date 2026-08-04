"""Pure ground-assault map generation, difficulty derivation, and garrison economy
(GW-WP09, GW plan D7-D11).

The production replacement for the POC's invented setup-menu difficulty
(`edge.groundwar.mapgen`/`GwDifficulty`). Given a world's live state — population,
citadel level, owner, inhabiting species — it derives a battlefield size and
surrender threshold, then lays out a walled-city battlefield as a **frozen,
non-hashed** `AssaultMap` regenerated on demand (G5), mirroring `survey.py`'s
shape exactly. `AssaultOperation` stores only the seed + the snapshotted
derivation inputs; this module turns those back into a layout, so a save stays
the command log, not a dump of every cell.

**The garrison model is not a POC port.** The POC's `GarrisonUnit`s are spawned
dynamically, wave by wave, only during live combat (`rules._spawn_sortie`) —
never placed at battle setup. D11 requires the opposite: a **persistent, finite,
casualty-reducible** headcount living on `Planet.garrison_infantry`/
`garrison_armor`. `generate_assault_map` therefore places **zero** garrison
units — WP10 spawns/places tactical units from `AssaultOperation.reserved_infantry`/
`reserved_armor` (the headcount `BeginAssault` snapshots at open, GW plan
decision #1). The terrain/city/structure generation *is* a near-verbatim port
of `edge.groundwar.mapgen`, since that part is unaffected by the garrison-model
change.

Pure `edge.core`: imports the terrain seam, `edge.core.planets.colonist_capacity`
(one-directional — this module is never imported back by `planets.py`), and
stdlib only. Deliberately does not import `edge.core.rules`, `edge.core.citadels`,
or anything in `edge.server`/`edge.tui`.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from random import Random
from typing import Literal

from edge.core.combat import CombatError
from edge.core.config import GameConfig, GroundwarConfig, GwEmplacement, GwSuit
from edge.core.groundwar import interior as gw_interior
from edge.core.groundwar import world as gw_world
from edge.core.groundwar.models import AssaultGarrisonUnit, AssaultOperation, AssaultTrooper
from edge.core.models import AlienSpecies, Planet, UniverseState
from edge.core.movement import MovementError
from edge.core.planets import colonist_capacity, is_cloud_city_world

Vec = tuple[int, int]

# Kept in lockstep with `citadels.CITADEL_MAX` by convention (both are the fixed
# ladder length); not imported to avoid a `planets.py`-adjacent import cycle risk
# (this module already imports `edge.core.planets`, and `citadels.py` does too).
_CITADEL_MAX = 3

StructureKind = Literal[
    "wall", "gate", "turret", "aa", "sensor", "citadel_gun",
    "building_military", "building_civilian",
]

# Passive geometry — a city's static footprint, not a hidden threat. Projected to the
# client unconditionally (like survey's `blocked`/`gate`/`settlement_id`), unlike the
# active-defense kinds (turret/aa/sensor/citadel_gun), which stay LOS-gated so a remote
# client cannot reverse-engineer a world's defenses without a trooper actually seeing them.
PASSIVE_STRUCTURE_KINDS: frozenset[StructureKind] = frozenset({
    "wall", "gate", "building_military", "building_civilian",
})

# City names moved to `groundwar.world.PLACE_NAMES` in GW-WP19 — a place carries one
# name whether a platoon drops on it or a surveyor walks into it.

# GW-WP16: a Cloud City assault has exactly one `AssaultCity` (the whole
# station — interview decision: surrender is whole-station, not per-district),
# named from this pool instead of the shared place names.
_STATION_NAMES = (
    "Aurora Spar", "Halcyon Reach", "Meridian Vault", "Thresher's Rest",
    "Windward Dock", "Lantern Spire", "Coriolis Bell", "Farview Anchor",
)

# Street paving, footprint dimensions, and the military/civilian building split moved to
# `groundwar.world` in GW-WP19: they describe the world's built-up places, which a survey
# and an assault now share rather than each inventing.


@dataclass(frozen=True, slots=True)
class AssaultStructure:
    """One stamped static defense, at generation-time full health (GW-WP09).

    No live/mutable `hp` here — this is a frozen, regenerated map (G5), exactly
    like `SurveyMap`. Live damage tracking is WP10's id-keyed overlay on
    `AssaultOperation`, the same way `SurveyOperation.resolved_discovery_ids`
    overlays `SurveySite.found` without `SurveySite` itself being mutable.

    GW-WP25 (D35/D36) gave a structure a **footprint**. `x, y` is the anchor — the
    north-west cell — and `w, h` its extent, so a 4x2 depot is *one* object with one
    HP pool and one Resolve drain rather than eight independent cells. Two ints
    beat an explicit cell tuple here: buildings are rectangles, `cells` stays
    derived, and every field is defaulted so a 1x1 structure constructs exactly as
    it did before.

    `origin_dx/dy` names the **firing cell** — where an emplacement's range and
    line of sight are measured from. It is a designated cell rather than "whichever
    of my cells is nearest the target" on purpose: nearest-cell silently extends an
    AA battery's reach by about a cell on the diagonal, and the 12-vs-13 gap
    between `aa.range` and a marauder's missile is the single fact D27's
    silence-then-jump tactic is built on.

    Per D39 only buildings and the big emplacements (`aa`, `citadel_gun`) ever grow.
    Walls and gates stay 1x1 because D22's breach loop picks one individually
    killable segment, and `resolve.wall_breached` is tuned per segment.
    """

    id: int
    kind: StructureKind
    x: int
    y: int
    city_id: int
    hp_max: int
    w: int = 1
    h: int = 1
    origin_dx: int = 0
    origin_dy: int = 0

    @property
    def cells(self) -> tuple[Vec, ...]:
        """Every cell this structure occupies, row-major from the anchor."""
        if self.w == 1 and self.h == 1:
            return ((self.x, self.y),)
        return tuple((self.x + dx, self.y + dy)
                     for dy in range(self.h) for dx in range(self.w))

    @property
    def ox(self) -> int:
        return self.x + self.origin_dx

    @property
    def oy(self) -> int:
        return self.y + self.origin_dy

    def covers(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h


@dataclass(frozen=True, slots=True)
class AssaultCity:
    id: int
    name: str
    cx: int
    cy: int
    x0: int
    y0: int
    x1: int
    y1: int
    is_citadel: bool = False
    citadel_level: int = 0

    def inside(self, x: int, y: int) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


@dataclass(frozen=True, slots=True)
class AssaultMap:
    """The regenerated, non-hashed battlefield layout for one assault (G5).

    Reconstructed from `(seed, planet_type, cities, citadel_level)`; safely
    discardable and excluded from `state_hash`, same contract as `SurveyMap`.
    Contains **zero** placed garrison units (see module docstring) — the
    persistent garrison headcount lives on `AssaultOperation.reserved_infantry`/
    `reserved_armor`; WP10 is responsible for spawning/placing tactical units
    from it. The `citadel_gun` structure is a *ground* emplacement guarding the
    capital city — a distinct, capturable tactical asset from the orbital gun
    tracked by `Planet.gun_integrity`/`citadels.has_gun` (GW plan decision #7).
    There is no "orbital gun"/"orbital base" entry in `StructureKind`, so this
    generator has nothing that could depict an already-razed base or
    already-silenced orbital gun as intact.
    """

    width: int
    height: int
    feature: tuple[tuple[str, ...], ...]
    blocked: frozenset[Vec]
    cities: tuple[AssaultCity, ...]
    structures: tuple[AssaultStructure, ...]
    landing_x: int
    landing_y: int
    # GW-WP16: a Cloud City map's WP15 `defender_slots`, so `_place_units` has
    # somewhere to spawn garrison even with zero `security_door`/`gate` structures
    # to derive a ring-search origin from (a terrestrial `bulkhead`-equivalent has
    # no structure to fall back to the way a terrestrial wall does). Empty/unused
    # for terrestrial maps, which keep deriving origins from gates/walls.
    spawn_anchors: tuple[Vec, ...] = ()
    # GW-WP25: cell -> structure id, covering **every** cell of every footprint.
    # Generation already built this index and threw it away; keeping it deletes the two
    # other places that rebuilt one from `(s.x, s.y)` (`_battle_for` and the server's
    # DTO projection), which were the only readers that had to know a structure was a
    # single cell. Everything downstream — passability, cover, LOS, targeting — asks a
    # cell what is on it and needs no footprint awareness at all.
    # cell keys the structure itself rather than its id: every consumer that asks
    # "what is on this cell" wants the object, and the one place that wants an id
    # (`_battle_for`, keying its mutable twins) just reads `.id` off it.
    struct_at: Mapping[Vec, AssaultStructure] = field(default_factory=dict)

    def structure_at(self, x: int, y: int) -> AssaultStructure | None:
        return self.struct_at.get((x, y))


@dataclass(frozen=True, slots=True)
class TacticalProjection:
    """Pure selected-actor affordances and earned visibility for GW-WP12.

    This is deliberately presentation-neutral.  ``server.session`` crops it into
    DTOs; the standalone harness may consume the same facts without importing the
    server or Textual layers.
    """

    visible: frozenset[Vec]
    reachable: frozenset[Vec]
    jumpable: frozenset[Vec]
    fireable: frozenset[Vec]
    missile_targets: frozenset[Vec]
    aa_threat: frozenset[Vec]
    ground_threat: frozenset[Vec]
    can_broadcast: bool


@dataclass(frozen=True, slots=True)
class AssaultDifficulty:
    """Live-derived battlefield sizing (GW plan D11) — the frozen inputs
    `BeginAssault` snapshots onto `AssaultOperation` and `generate_assault_map`
    consumes."""

    cities: int
    citadel_level: int
    surrender_threshold: int


def derive_difficulty(
    planet: Planet, config: GameConfig, *, distance_band: str,
    species: AlienSpecies | None,
) -> AssaultDifficulty:
    """Derive battlefield size + surrender threshold from live world state (D11).

    Reads only world-intrinsic state — population/capacity, citadel level
    (including whether a gun was ever built, decision #7 below), owner kind, the
    inhabiting species' *base* disposition (not the player's live relationship,
    GW plan decision #6), and the world's distance band — so the same world
    derives the same difficulty for every player and is unaffected by anything
    the calling player carries (fighters, alignment, standing).

    "Surviving gun" (GW plan line 1102) is read as "did this world ever field a
    citadel gun," not "is the orbital gun currently up": by the time this runs,
    `BeginAssault` has already confirmed `ground_access` is droppable, which
    means `citadels.has_gun(planet, config)` is *always* False (the gun-silence
    blocker is a precondition of reaching this point at all). Reading it as
    current `gun_integrity > 0` would make it a permanent no-op, so instead a
    world with `citadel_level >= gun_min_level` — one that built and lost a gun
    in the siege — scores a `had_gun_mult` harder than one that never invested
    in one, even though the literal weapon is down either way (decision #7).

    **GW-WP16 Cloud City branch**: `cities` carries `planet.cloud_city_size`
    directly rather than the population-derived city count below — WP15's own
    `districts_base`/`districts_per_size` formula (`GwCloudCity`, read inside
    `generate_cloud_city_assault_map`) controls room count for a station, not
    this one. `citadel_level`/`surrender_threshold` are untouched: already
    planet-type-agnostic (`colonist_capacity` already returns the
    cloud-city-appropriate `size × berths` figure, so every multiplier above
    already reads correctly for a station).

    **GW-WP19**: the city *count* is no longer derived here — it is
    `world.place_count`, part of the world's stable shared layout, because a survey of
    the same world must walk into the same towns and a conquest must not re-roll them.
    What remains here is what may legitimately vary with the world's live condition:
    the citadel level, and how stubbornly it holds (`surrender_threshold`).
    """
    assert config.groundwar is not None
    cfg = config.groundwar.assault_difficulty
    if is_cloud_city_world(planet.planet_type, config):
        cities = planet.cloud_city_size
    else:
        cities = gw_world.place_count(planet, config, distance_band=distance_band)
    citadel_level = min(planet.citadel_level, _CITADEL_MAX)
    # `hostility_mult`/`alliance_owned_mult`/`had_gun_mult` shift how hard the world
    # *fights*, not how large it is (GW-WP19): every one of them can change over a
    # world's life — ownership and citadel level flip on conquest, and an inhabiting
    # species vanishes if its people do — while the battlefield's size is now part of
    # the world's stable shared layout (`world.place_count`), which none of those events
    # may re-roll. A hostile people, a bloc holding, and a world that built and lost a
    # gun therefore hold out to a lower Resolve instead.
    resist = 1.0
    if (species is not None and config.aliens is not None
            and species.base_disposition < config.aliens.amity_threshold):
        resist *= cfg.hostility_mult
    if planet.owner.kind == "alliance":
        resist *= cfg.alliance_owned_mult
    if config.citadels is not None and planet.citadel_level >= config.citadels.gun_min_level:
        resist *= cfg.had_gun_mult
    surrender_threshold = max(1, round(
        (cfg.surrender_threshold_base
         + citadel_level * cfg.surrender_threshold_per_citadel_level) / resist))
    return AssaultDifficulty(
        cities=cities, citadel_level=citadel_level, surrender_threshold=surrender_threshold)


# --- battlefield generation (ported from edge.groundwar.mapgen, GW-WP09) ------


def _add_structure(
    structures: list[AssaultStructure], struct_at: dict[Vec, AssaultStructure],
    next_id: list[int], kind: StructureKind, x: int, y: int, city_id: int, hp: int,
    *, w: int = 1, h: int = 1, origin: Vec = (0, 0),
) -> AssaultStructure:
    """Stamp one structure and index **every cell of its footprint** (GW-WP25).

    Indexing the whole footprint here is what lets the rest of the system stay
    footprint-blind: passability, cover, line of sight and targeting all ask
    `struct_at` what is on a cell, and get the same answer for the far corner of a
    depot as for its anchor.
    """
    s = AssaultStructure(id=next_id[0], kind=kind, x=x, y=y, city_id=city_id, hp_max=hp,
                         w=w, h=h, origin_dx=origin[0], origin_dy=origin[1])
    structures.append(s)
    for cell in s.cells:
        struct_at[cell] = s
    next_id[0] += 1
    return s


def _stamp_city(
    feature: list[list[str]], blocked: set[Vec], structures: list[AssaultStructure],
    struct_at: dict[Vec, AssaultStructure], next_id: list[int], config: GameConfig,
    stamp: gw_world.PlaceStamp, *, citadel_level: int,
) -> AssaultCity:
    """Fortify one of the world's built-up places into a defended city (GW-WP19).

    The *geometry* — footprint, perimeter, gates, building blocks and their
    military/civilian split — comes from the shared `groundwar.world` stamp a survey
    of this world walks as a town, so the two modes cannot disagree about where a
    wall is. This function adds only what a defence contributes: hit points, turrets
    substituted at the corner/mid-wall slots, and the interior emplacements the live
    `citadel_level` pays for (an extra AA at 3, exactly one `citadel_gun` on the
    capital at 2).
    """
    assert config.groundwar is not None
    d = config.groundwar.defenses
    place = stamp.place
    city = AssaultCity(id=place.id, name=place.name, cx=place.cx, cy=place.cy,
                       x0=place.x0, y0=place.y0, x1=place.x1, y1=place.y1,
                       is_citadel=place.capital, citadel_level=citadel_level)
    gw_world.pave(feature, stamp)

    wall_mult = 2.0 if citadel_level >= 3 else 1.0
    wall_hp = round(d.wall.hp * wall_mult)

    corners = {(place.x0, place.y0), (place.x1, place.y0),
               (place.x0, place.y1), (place.x1, place.y1)}
    mids = {(place.cx, place.y0), (place.cx, place.y1)}  # mid top/bottom wall
    for pos in stamp.perimeter:
        if pos in corners or (pos in mids and citadel_level >= 1):
            _add_structure(structures, struct_at, next_id, "turret", *pos, city.id, d.turret.hp)
        else:
            _add_structure(structures, struct_at, next_id, "wall", *pos, city.id, wall_hp)
        blocked.add(pos)
    for pos in stamp.gates:
        _add_structure(structures, struct_at, next_id, "gate", *pos, city.id, d.gate.hp)

    # Interior emplacements, on the slots the shared stamp reserves for them.
    aa_slot, sensor_slot, aa2_slot, gun_slot = stamp.reserved
    _add_structure(structures, struct_at, next_id, "aa", *aa_slot, city.id, d.aa.hp)
    _add_structure(structures, struct_at, next_id, "sensor", *sensor_slot, city.id, d.sensor.hp)
    if citadel_level >= 3:
        _add_structure(structures, struct_at, next_id, "aa", *aa2_slot, city.id, d.aa.hp)
    if place.capital and citadel_level >= 2:
        _add_structure(
            structures, struct_at, next_id, "citadel_gun", *gun_slot, city.id, d.citadel_gun.hp)

    blocks: tuple[tuple[StructureKind, int, tuple[Vec, ...]], ...] = (
        ("building_military", d.building_military_hp, stamp.military),
        ("building_civilian", d.building_civilian_hp, stamp.civilian),
    )
    for kind, hp, cells in blocks:
        for x, y in cells:
            _add_structure(structures, struct_at, next_id, kind, x, y, city.id, hp)
            blocked.add((x, y))
    return city


# Generation-time terrain/passability helpers live in `groundwar.world` since GW-WP19 —
# `assault.py` and `survey.py` each carried a byte-identical private copy before the two
# modes shared one layout. (The *battle-time* cost/cover functions further down stay
# separate on purpose: a wall reduced to rubble mid-fight must become passable, which the
# static generation-time view knows nothing about.)
_move_cost = gw_world.move_cost
_in_bounds = gw_world.in_bounds
_passable_components = gw_world.passable_components
_landing = gw_world.landing_in_component

# How far off the exact standoff radius still counts as "on the ring" (GW-WP23). Wide
# enough that a ring almost always has candidates to choose between on exposure grounds,
# narrow enough that "just outside AA range" stays true.
_RING_BAND = 1.5


def assault_landing(
    labels: list[list[int]], sizes: Mapping[int, int], width: int, height: int,
    cities: Sequence[AssaultCity], config: GameConfig,
) -> Vec:
    """Set down on a ring just outside the capital's AA umbrella (GW-WP23, D16/D17).

    Assault-only, deliberately **not** shared with survey (D18): a survey faces no AA
    and since GW-WP07-FU2 picks its own drop site, so `landing_in_component`'s
    west-edge default is a suggestion there rather than a forced march. An assault
    had no such escape — it inherited the same west-edge point, computed with no
    reference whatsoever to where the cities are, which is why a GW-WP22 watched run
    spent ten of its twenty-four turns walking (cities at 95/130/203 cells) and the
    `defenses.aa` config comment's stated intent — "land clear of the umbrella and
    march in" — was never actually achievable.

    Anchored on the **capital** (D16), not the nearest city: the capital is the
    objective and the only city that ever carries a `citadel_gun`, so anchoring here
    is what makes `citadel_level` legible in where you come down. Cells covered by
    *another* town's AA are accepted only when nothing clear exists, so a short march
    is never bought with a landing under someone else's guns.

    Degrades rather than failing: with no ring cell at the exact radius (a small map,
    or a capital boxed against an edge) it takes the component cell closest to the
    ring. Pure and deterministic — same labels/cities in, same cell out, no re-rolling
    (decision #3).

    **Lands in the capital's own passable component, not the map's largest one.** These
    are not always the same, and the difference is fatal: on `terrestrial_warm` seed 2 the
    capital sits on a 1149-cell landmass while the largest component is a 2173-cell one
    108 cells away, with no foot route between them. Confining the drop to the largest
    component — as this did through GW-WP22, and as survey still does — puts the platoon
    somewhere it can never walk to the objective from, on a clock, with jump charges
    covering at most ~32 of those cells. The old west-edge landing hid this behind a long
    march that failed for the ordinary reason instead of the impossible one.
    """
    assert config.groundwar is not None
    d = config.groundwar.defenses
    if not cities:
        return _landing(labels, max(sizes, key=lambda k: sizes[k]) if sizes else 0,
                        width, height)
    capital = next((c for c in cities if c.is_citadel), cities[0])
    # Cells of open ground to cross, measured from the capital's *footprint* (GW-WP24) —
    # not `aa.range + standoff` from its centre, which made the approach a function of how
    # big the city happened to be. Clearing the AA umbrella is still required, but as a
    # separate condition below rather than as arithmetic folded into the radius.
    radius = float(d.drop_standoff)

    # Open ground *inside* a city's footprint is passable and often its own component, so
    # neither the component choice nor the ring may consider it: a capital wider than
    # `aa.range + drop_standoff` would otherwise put the drop boat down in the middle of
    # the objective, past every wall, which is not a landing — it is skipping the assault.
    def outside_cities(x: int, y: int) -> bool:
        return not any(c.inside(x, y) for c in cities)

    # The component a foot assault can actually reach the capital across: the one holding
    # the passable cell nearest the capital, breaking ties toward the larger landmass.
    comp: int | None = None
    anchor: tuple[float, int, int] | None = None
    for y in range(height):
        for x in range(width):
            label = labels[y][x]
            if label not in sizes or not outside_cities(x, y):
                continue
            key = (_dist(capital.cx, capital.cy, x, y), -sizes[label], label)
            if anchor is None or key < anchor:
                anchor, comp = key, label
    if comp is None:
        return _landing(labels, 0, width, height)

    # Being *on the ring* outranks being clear of another town's guns, and the ordering
    # matters more than it looks: ranking exposure first lets a seed whose whole ring
    # happens to sit under a neighbouring town's umbrella escape to some empty corner of
    # the map instead — one test seed landed 108 cells from the capital that way, which
    # is the very failure this function exists to remove. So: gather a band around the
    # ring, prefer an unexposed cell *within it*, and only widen if the band is empty.
    # Clearance from the capital's *footprint*, not its centre. Cities are wide rectangles
    # (30x14 in the shipped battlefield) while the ring is a circle, so the same 17-cell
    # radius leaves ~11 cells of open ground off a long face and barely 2 off a corner —
    # measured on shipped seeds. Landing on the ring is the decision (D16/D17); *where* on
    # the ring is free, so spend it on the bearing that actually gives an approach.
    half_w, half_h = (capital.x1 - capital.x0) / 2, (capital.y1 - capital.y0) / 2

    def clearance(x: int, y: int) -> float:
        """Open ground between this cell and the capital's edge — the honest approach
        length, and since GW-WP24 the quantity the ring is actually built on.

        Measuring the ring from the *centre* (D16/D17 as originally decided) couples the
        approach to the city's size, and shipped cities are ~30x14 against a circular
        ring: a 20-cell radius leaves ~6 cells of open ground off a long face and none at
        all off a corner. Tuning the standoff then moved the drop without lengthening the
        approach, which is the thing the standoff exists to create. Anchoring on the
        footprint makes `drop_standoff` mean one size-independent thing — cells of open
        ground you must cross — on every world.
        """
        return max(abs(x - capital.cx) - half_w, abs(y - capital.cy) - half_h)

    # Ranked in one pass, safety first. A capital pinned against a map edge can leave the
    # ring with no cells at all in its component — three shipped `terrestrial_hot` seeds
    # do exactly that, their capitals sitting within ~11 cells of the top edge — and a
    # fallback of "nearest to the ring" then reaches *inward*, setting the platoon down
    # 10-15 cells out, under the very umbrella the standoff exists to clear. So a cell
    # outside every AA envelope always outranks a closer one, and only a capital with no
    # safe ground anywhere in reach falls back to the farthest cell available.
    safe: list[tuple[float, float, int, int]] = []
    exposed_best: tuple[float, int, int] | None = None
    for y in range(height):
        for x in range(width):
            if labels[y][x] != comp or not outside_cities(x, y):
                continue
            here = _dist(capital.cx, capital.cy, x, y)
            if any(_dist(c.cx, c.cy, x, y) <= d.aa.range for c in cities):
                if exposed_best is None or (-here, y, x) < exposed_best:
                    exposed_best = (-here, y, x)
                continue
            off = abs(clearance(x, y) - radius)
            safe.append((off, here, y, x))
    if safe:
        _, _, by, bx = min(safe)
        return bx, by
    if exposed_best is None:  # nothing walkable at all — the shared default still applies
        return _landing(labels, comp, width, height)
    return exposed_best[2], exposed_best[1]


def station_landing(
    zones: Sequence[Vec], city: AssaultCity, config: GameConfig,
) -> Vec:
    """Pick the station deployment zone that best honours the drop standoff (D19).

    Closes the GW-WP16 deferral that only ever used `deployment_zones[0]`: every zone
    the interior layout offers is now a candidate, ranked by the same rule
    `assault_landing` applies outdoors — outside the command core's AA envelope first,
    then nearest the standoff ring.

    A station is far smaller than a battlefield, so the ring usually does not fit at
    all and every zone is inside the envelope. That is the intended degenerate case,
    not a failure: with all candidates exposed, ranking by distance-to-ring picks the
    zone *farthest* from the command core, which is the D19 fallback stated exactly.
    Interior AA is therefore a real cost of the approach rather than something a drop
    can sidestep — the opposite of the terrestrial case, and deliberately so.
    """
    assert config.groundwar is not None
    d = config.groundwar.defenses
    radius = float(d.aa.range + d.drop_standoff)
    return min(zones, key=lambda z: (
        1 if _dist(city.cx, city.cy, *z) <= d.aa.range else 0,
        abs(_dist(city.cx, city.cy, *z) - radius), z[1], z[0]))


def generate_assault_map(
    config: GameConfig, *, seed: int, planet_type: str, cities: int, citadel_level: int,
) -> AssaultMap:
    """Fortify the world's shared ground into a battlefield (pure, deterministic, G5).

    `seed` is the **world's** layout identity (`world.world_ground_seed`), not this
    operation's: since GW-WP19 the terrain grid and the footprints of the world's
    `cities` built-up places come from `groundwar.world`, the same layout a survey of
    this world walks, so taking a world and then surveying it shows the ground you
    fought over — and a second assault reopens the same battlefield rather than a
    freshly rolled one. This function adds the fortification: walls with gates, corner
    turrets, mid-wall turrets at `citadel_level >= 1`, AA + sensor, an extra AA +
    hardened walls at `citadel_level >= 3`, exactly one `citadel_gun` on the capital at
    `citadel_level >= 2`, building blocks.

    The POC never needed foot-reachability (its troopers can jump), so as in GW-WP09 the
    largest 4-connected passable component is computed after fortification and the
    landing point confined to it — never re-rolled, so the same seed always produces
    the same map (determinism over retry, decision #3). Since GW-WP23 that point is
    also placed *relative to the capital*, on a ring just outside AA range
    (`assault_landing`), instead of at the map's west edge irrespective of the cities. Places **zero** garrison units
    (module docstring).
    """
    assert config.groundwar is not None
    ground = gw_world.generate_world_ground(
        config, seed=seed, planet_type=planet_type, places=cities)
    width, height = ground.width, ground.height
    feature = [list(row) for row in ground.feature]
    blocked: set[Vec] = set()
    structures: list[AssaultStructure] = []
    struct_at: dict[Vec, AssaultStructure] = {}
    next_id = [1]

    built = [
        _stamp_city(
            feature, blocked, structures, struct_at, next_id, config, stamp,
            citadel_level=citadel_level if stamp.place.capital else 0)
        for stamp in ground.stamps
    ]

    labels, sizes = _passable_components(feature, blocked, config, width, height)
    landing_x, landing_y = assault_landing(labels, sizes, width, height, built, config)

    return AssaultMap(
        width=width, height=height,
        feature=tuple(tuple(row) for row in feature), blocked=frozenset(blocked),
        cities=tuple(built), structures=tuple(structures),
        landing_x=landing_x, landing_y=landing_y, struct_at=struct_at,
    )


# --- Cloud City station-interior battlefield generation (GW-WP16, GW plan D9) --


def _stamp_district(
    structures: list[AssaultStructure], struct_at: dict[Vec, AssaultStructure],
    next_id: list[int], config: GameConfig, district: gw_interior.District, city_id: int, reserved: set[Vec], *,
    is_citadel: bool, citadel_level: int,
) -> None:
    """Emplacements + building stamps for one district, keyed off its own floor
    cell list (index-based selection, not geometric offsets — robust regardless
    of the room's actual shape). Every non-command-core district gets AA +
    sensor, mirroring `_stamp_city`'s baseline; only the command-core district
    (the station's objective) can carry a `citadel_gun`, at the same
    `citadel_level >= 2` threshold terrestrial capitals use. `habitation`/
    `engineering` districts stamp a fraction of their floor as
    `building_civilian`/`building_military` — WP15's interior vocabulary had
    none, so this is what gives civilian-harm consequences (`_structure_destroyed`,
    `settlement.civilian_loss_per_structure`) real targets on a station.

    `reserved` (the layout's `deployment_zones`) is excluded from every
    candidate cell — a district role can be `plaza`, which *is* eligible
    floor for a landing zone, so without this a drop point could otherwise
    land on a cell a structure just claimed (found via a failing
    `assault_drop` in this WP's own test suite, not assumed safe).
    """
    assert config.groundwar is not None
    d = config.groundwar.defenses
    floor = [p for p in district.floor if p not in reserved]
    if not floor:
        return
    used: set[Vec] = set()

    def _take(start_idx: int) -> Vec | None:
        for step in range(len(floor)):
            pos = floor[(start_idx + step) % len(floor)]
            if pos not in used and pos not in struct_at:
                used.add(pos)
                return pos
        return None

    aa_pos = _take(0)
    if aa_pos is not None:
        _add_structure(structures, struct_at, next_id, "aa", *aa_pos, city_id, d.aa.hp)
    sensor_pos = _take(len(floor) // 3)
    if sensor_pos is not None:
        _add_structure(structures, struct_at, next_id, "sensor", *sensor_pos, city_id, d.sensor.hp)
    if citadel_level >= 3:
        extra_aa = _take(2 * len(floor) // 3)
        if extra_aa is not None:
            _add_structure(structures, struct_at, next_id, "aa", *extra_aa, city_id, d.aa.hp)
    if is_citadel and citadel_level >= 2:
        gun_pos = _take(len(floor) - 1)
        if gun_pos is not None:
            _add_structure(
                structures, struct_at, next_id, "citadel_gun", *gun_pos, city_id, d.citadel_gun.hp)

    if district.role == "habitation":
        building_kind: StructureKind = "building_civilian"
        building_hp = d.building_civilian_hp
    elif district.role == "engineering":
        building_kind = "building_military"
        building_hp = d.building_military_hp
    else:
        return  # plaza / command_core get no building stamps
    for i, pos in enumerate(floor):
        if i % 3 == 0 and pos not in used and pos not in struct_at:
            _add_structure(structures, struct_at, next_id, building_kind, *pos, city_id, building_hp)
            used.add(pos)


def generate_cloud_city_assault_map(
    config: GameConfig, *, seed: int, cloud_city_size: int, citadel_level: int,
) -> AssaultMap:
    """Lay out a Cloud City's tactical battlefield from its GW-WP15 interior
    layout (`edge.core.groundwar.interior.generate_interior`).

    Unlike `generate_assault_map`'s several discrete walled cities, the whole
    station reports to **one shared `AssaultCity`** seated at the command-core
    district (interview decision: surrender is whole-station, not
    per-district) — every stamped structure across every physical room carries
    that one `city_id`, so `_check_cowed`/`broadcast_terms`/`_apply_resolve`
    are whole-station with **no changes to their own code** (they already key
    purely on `city_id`).

    `bulkhead` stays permanent, impassable terrain — no live structure, no
    breach mechanic (interview decision: only `security_door` is destructible).
    Every generated `security_door` cell becomes a destructible `gate`
    structure; no `wall`-kind structure is ever emitted (`city_cowed`'s own
    definition never references walls/gates, so this has no effect on the win
    condition). `blocked` covers every stamped structure's cell (gates
    excluded, mirroring how terrestrial gates are excluded) plus every
    `bulkhead` cell, in parity with `_stamp_city`'s redundant wall-blocked
    bookkeeping even though the terrain `move_cost` check alone already
    covers bulkhead. `spawn_anchors` carries the layout's `defender_slots`.
    """
    assert config.groundwar is not None
    layout = gw_interior.generate_interior(seed, cloud_city_size, config.groundwar.cloud_city)
    structures: list[AssaultStructure] = []
    struct_at: dict[Vec, AssaultStructure] = {}
    next_id = [1]
    rng = Random(f"{seed}|cloud_city_assault|{cloud_city_size}|{citadel_level}")

    command_district = next(dd for dd in layout.districts if dd.role == "command_core")
    city = AssaultCity(
        id=1, name=rng.choice(_STATION_NAMES),
        cx=command_district.cx, cy=command_district.cy,
        x0=command_district.x0, y0=command_district.y0,
        x1=command_district.x1, y1=command_district.y1,
        is_citadel=True, citadel_level=citadel_level,
    )

    reserved_cells = set(layout.deployment_zones)
    for district in layout.districts:
        is_capital = district.role == "command_core"
        _stamp_district(
            structures, struct_at, next_id, config, district, city.id, reserved_cells,
            # Mirrors `generate_assault_map`'s own call to `_stamp_city`: the
            # citadel_level>=3 extra-AA/hardening bonus is capital-only, so a
            # non-capital district is stamped as if citadel_level were 0.
            is_citadel=is_capital, citadel_level=citadel_level if is_capital else 0,
        )

    for y, row in enumerate(layout.feature_grid):
        for x, feature_name in enumerate(row):
            if feature_name == "security_door":
                _add_structure(
                    structures, struct_at, next_id, "gate", x, y, city.id,
                    config.groundwar.defenses.gate.hp)

    blocked: set[Vec] = {pos for pos, s in struct_at.items() if s.kind != "gate"}
    for y, row in enumerate(layout.feature_grid):
        for x, feature_name in enumerate(row):
            if feature_name == "bulkhead":
                blocked.add((x, y))

    landing_x, landing_y = station_landing(layout.deployment_zones, city, config)
    return AssaultMap(
        width=layout.width, height=layout.height, feature=layout.feature_grid,
        blocked=frozenset(blocked), cities=(city,), structures=tuple(structures),
        landing_x=landing_x, landing_y=landing_y, spawn_anchors=layout.defender_slots,
        struct_at=struct_at,
    )


def assault_map_for(state: UniverseState, op: AssaultOperation, config: GameConfig) -> AssaultMap:
    """Regenerate the live battlefield for an active assault operation (G5) — the
    projection seam, mirroring `survey.survey_map_for`."""
    return assault_map_for_state(op, config)


_MAP_CACHE_MAX = 64
# GW-WP23 (D24): the runtime cache GW-WP13 said to add only where measurement warrants
# one. GW-WP22's watched run supplied the warrant — regenerating the battlefield once
# per bot action costs ~0.1s and dominated a ~79s run, because every projection, every
# legality check and every narration line re-derives the same map from the same inputs.
#
# Sound because generation is pure: `generate_assault_map`/`generate_cloud_city_assault_map`
# are total functions of (seed, planet_type, cities, citadel_level) and the config, and
# `AssaultMap` is frozen throughout (tuples/frozensets), so a shared instance cannot be
# mutated by one holder under another. Determinism is therefore untouched — a cache hit
# returns exactly what a recompute would have built. Live battle damage is *not* cached
# here: it is applied downstream by `persistent_structure_hp`/`_battle_for` against this
# immutable layout, which is what makes the layout cacheable in the first place.
#
# `id(config)` is part of the key and the config is held alive by the cached entry, so an
# id cannot be recycled onto a different config while its map is still reachable — tests
# routinely build many configs that differ without any version field changing.
_map_cache: dict[tuple[object, ...], tuple[GameConfig, AssaultMap]] = {}


def clear_assault_map_cache() -> None:
    """Drop every memoized battlefield (GW-WP23). For tests that mutate config in place."""
    _map_cache.clear()


def assault_map_for_state(op: AssaultOperation, config: GameConfig) -> AssaultMap:
    """State-free battlefield regeneration for pure settlement/tests (G5).

    Generates from `op.world_seed` — the world's shared layout identity, not the
    operation's own seed (GW-WP19) — so the battlefield is the same ground a survey
    of this world walks and a repeat assault fights.

    `AssaultOperation.cities` doubles as `cloud_city_size` for a Cloud City
    operation (GW-WP16 — `derive_difficulty` sets it that way instead of the
    population-derived city count), so the dispatch below is the one place
    that distinction matters; every downstream consumer (session, TUI,
    settlement) reads the same `AssaultMap` shape either way.
    """
    station = is_cloud_city_world(op.planet_type, config)
    key = (id(config), station, op.world_seed, op.planet_type, op.cities, op.citadel_level)
    hit = _map_cache.get(key)
    if hit is not None and hit[0] is config:
        return hit[1]
    if station:
        amap = generate_cloud_city_assault_map(
            config, seed=op.world_seed, cloud_city_size=op.cities,
            citadel_level=op.citadel_level)
    else:
        amap = generate_assault_map(
            config, seed=op.world_seed, planet_type=op.planet_type,
            cities=op.cities, citadel_level=op.citadel_level)
    if len(_map_cache) >= _MAP_CACHE_MAX:
        _map_cache.clear()
    _map_cache[key] = (config, amap)
    return amap


def persistent_structure_hp(
    amap: AssaultMap, rubble: Mapping[Vec, str],
) -> dict[int, int]:
    """Project a world's persisted battle damage onto a regenerated map (GW-WP19).

    Operations still do not persist a terrain grid (G5) — but they no longer need to
    guess *which* structures were lost. A world has one stable layout shared with its
    survey map, so `Planet.ground_rubble` records damage by position and this simply
    starts the structure standing there at zero: the breach a previous assault opened is
    the breach the next one drops into. The pre-GW-WP19 version could only spend a
    per-kind count against "the lowest stable structure ids of each kind", which moved
    the damage around whenever the map was re-rolled.
    """
    # GW-WP25: any cell of the footprint being rubble means the whole structure is
    # down. Rubble is recorded per cell (`Planet.ground_rubble`) because that is the
    # granularity a survey walks and a repeat assault re-enters, but a structure has
    # one HP pool, so recognising it from any one of its cells is the correct read.
    return {
        structure.id: 0 for structure in amap.structures
        if any(rubble.get(cell) is not None for cell in structure.cells)
    }


def _paint_radius(amap: AssaultMap, cx: int, cy: int, radius: int, target: set[Vec]) -> None:
    for y in range(max(0, cy - radius), min(amap.height, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(amap.width, cx + radius + 1)):
            if _dist(cx, cy, x, y) <= radius:
                target.add((x, y))


def tactical_projection(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig,
    actor_id: int | None = None,
) -> TacticalProjection:
    """Project visibility and exact legal actions without mutating the battle.

    Enemy units/structures contribute to the DTO only inside ``visible``.  Weapon
    threat is painted only from those visible sources, preventing the old POC
    radar from leaking an unseen battery's position through its range circle.

    Pre-drop (``not op.dropped``), no trooper has earned any visibility yet, but the
    player still needs some read on where to land (GW-WP13-FU1). Every city's
    footprint/name/citadel-tier already reaches the client unconditionally
    (``AssaultCityDTO`` in `server.session`), so painting a coarse, fixed-radius AA
    hazard zone around each city's center — not derived from any actual battery's
    position — reveals nothing about interior defense placement or count. This is
    deliberately *not* the POC's exact-position radar, which this module's
    LOS-gating exists to prevent.
    """
    if config.groundwar is None:
        return TacticalProjection(
            frozenset(), frozenset(), frozenset(), frozenset(), frozenset(),
            frozenset(), frozenset(), False)
    if not op.dropped:
        pre_drop_aa: set[Vec] = set()
        for city in amap.cities:
            _paint_radius(amap, city.cx, city.cy, config.groundwar.defenses.aa.range, pre_drop_aa)
        return TacticalProjection(
            frozenset(), frozenset(), frozenset(), frozenset(), frozenset(),
            frozenset(pre_drop_aa), frozenset(), False)
    battle = _battle_for(op, amap, config)
    visible: set[Vec] = set()
    for trooper in battle.live_troopers():
        sight = _suit(battle, trooper).sight
        for y in range(max(0, trooper.y - sight), min(amap.height, trooper.y + sight + 1)):
            for x in range(max(0, trooper.x - sight), min(amap.width, trooper.x + sight + 1)):
                if (_dist(trooper.x, trooper.y, x, y) <= sight
                        and _line_of_sight(battle, trooper.x, trooper.y, x, y)):
                    visible.add((x, y))

    # GW-WP24 (D30): a scout uncovers enemy *units and emplacements* at `recon_radius`
    # without needing line of sight — reading heat and movement rather than seeing it.
    # Deliberately narrow: only occupied cells are revealed, never open ground or passive
    # geometry, so this finds the AA the platoon must silence (D27) without turning the
    # scout into a map-wide x-ray. This is the scout's reason to exist, replacing
    # `jam_radius`, whose sensor suppression only touched detection and first-strike
    # bonuses that nothing in the fight meaningfully exploited.
    for trooper in battle.live_troopers():
        recon = _suit(battle, trooper).recon_radius
        if recon <= 0:
            continue
        for unit in battle.garrison.values():
            if unit.alive and _dist(trooper.x, trooper.y, unit.x, unit.y) <= recon:
                visible.add((unit.x, unit.y))
        for s in battle.structures.values():
            if s.alive and s.kind not in PASSIVE_STRUCTURE_KINDS and any(
                    _dist(trooper.x, trooper.y, cx, cy) <= recon for cx, cy in s.cells):
                # Reveal the whole footprint: a scout that has spotted one corner of a
                # battery has spotted the battery, and revealing a partial silhouette
                # would render as a fragment of a building.
                visible.update(s.cells)

    actor = battle.troopers.get(actor_id) if actor_id is not None else None
    live_action = actor is not None and actor.alive and op.outcome is None
    reachable: set[Vec] = set()
    jumpable: set[Vec] = set()
    fireable: set[Vec] = set()
    missile_targets: set[Vec] = set()
    can_broadcast = False
    if live_action and actor is not None:
        reachable = set(_reachable(battle, actor))
        suit = _suit(battle, actor)
        if actor.actions > 0 and actor.jump_charges > 0:
            for y in range(max(0, actor.y - suit.jump_range),
                           min(amap.height, actor.y + suit.jump_range + 1)):
                for x in range(max(0, actor.x - suit.jump_range),
                               min(amap.width, actor.x + suit.jump_range + 1)):
                    if (_dist(actor.x, actor.y, x, y) <= suit.jump_range
                            and _battle_move_cost(battle, x, y) > 0
                            and not _occupied(battle, x, y)):
                        jumpable.add((x, y))

        def targets(weapon_range: int) -> set[Vec]:
            if actor.actions <= 0 or weapon_range <= 0:
                return set()
            out: set[Vec] = set()
            for cell in visible:
                x, y = cell
                structure = battle.structure_at(x, y)
                unit = battle.garrison_at(x, y)
                if ((structure is None or not structure.alive) and unit is None):
                    continue
                if (_dist(actor.x, actor.y, x, y) <= weapon_range
                        and _line_of_sight(battle, actor.x, actor.y, x, y)):
                    out.add(cell)
            return out

        fireable = targets(suit.weapon.range)
        if actor.missiles > 0:
            missile_targets = targets(suit.missile.range)
        can_broadcast = any(
            city.id not in battle.broadcast_done
            and battle.city_cowed(city)
            and city_range(city, actor.x, actor.y) <= suit.broadcast_range
            for city in amap.cities
        )

    aa_threat: set[Vec] = set()
    ground_threat: set[Vec] = set()

    for structure in battle.structures.values():
        # Seeing *any* cell of a battery is seeing the battery: gating on the anchor
        # alone would hide a whole emplacement whose north-west corner happens to be
        # fogged, which is the one cell a player has no reason to think is special.
        if not structure.alive or not any(cell in visible for cell in structure.cells):
            continue
        # Painted from the firing cell, matching where the gun actually shoots from.
        if structure.kind == "aa":
            _paint_radius(amap, structure.ox, structure.oy, battle.gw.defenses.aa.range,
                          aa_threat)
        elif structure.kind == "turret":
            _paint_radius(amap, structure.ox, structure.oy, battle.gw.defenses.turret.range,
                          ground_threat)
        elif structure.kind == "citadel_gun":
            _paint_radius(amap, structure.ox, structure.oy, battle.gw.defenses.citadel_gun.range,
                          ground_threat)
    for unit in battle.garrison.values():
        if unit.alive and (unit.x, unit.y) in visible:
            _paint_radius(amap, unit.x, unit.y, getattr(battle.gw.garrison, unit.kind).weapon.range,
                          ground_threat)
    return TacticalProjection(
        visible=frozenset(visible), reachable=frozenset(reachable),
        jumpable=frozenset(jumpable), fireable=frozenset(fireable),
        missile_targets=frozenset(missile_targets), aa_threat=frozenset(aa_threat),
        ground_threat=frozenset(ground_threat), can_broadcast=can_broadcast,
    )


# --- garrison economy (pure; GW plan D11) --------------------------------------


def seed_garrison(
    config: GameConfig, *, capacity: int, citadel_level: int, distance_band: str,
    hostile: bool, alliance_owned: bool, rng: Random,
) -> tuple[int, int]:
    """The (infantry, armor) headcount a freshly-inhabited world starts with (D11).

    Called once, at big-bang seeding, from `edge.bigbang.inhabitants._settle` against
    its salted sub-RNG (never a fresh `Random()`, so the universe stays reproducible
    per seed). Scales the same way the discovery/species bands already do: a wary/
    hostile species, a bloc's own holding, and depth from the Core all raise the
    seeded force; citadel level reuses the *identical* multiplier
    `citadels.citadel_defense_mult` reads for the legacy invasion path
    (`config.citadels.levels[level-1].garrison_mult`), read inline here rather than
    imported (keeps this module free of a `planets.py`-adjacent import cycle risk).
    Armor is seeded only at `citadel_level >= seed_armor_min_citadel_level`, as a
    fraction of the seeded infantry; a world under that level fields no vehicles at
    all, matching the POC's `armor_from_wave` gating in spirit.
    """
    assert config.groundwar is not None
    cfg = config.groundwar.garrison_economy
    frac = rng.uniform(cfg.seed_infantry_frac_min, cfg.seed_infantry_frac_max)
    mult = 1.0
    if hostile:
        mult *= cfg.seed_hostility_mult
    if alliance_owned:
        mult *= cfg.seed_alliance_mult
    mult *= cfg.seed_band_mult.get(distance_band, 1.0)
    if config.citadels is not None and citadel_level >= 1:
        mult *= config.citadels.levels[min(citadel_level, _CITADEL_MAX) - 1].garrison_mult
    infantry = round(capacity * frac * mult)
    armor = round(infantry * cfg.seed_armor_frac) if citadel_level >= cfg.seed_armor_min_citadel_level else 0
    return infantry, armor


def _recover_toward_cap(current: int, cap: int, frac: float) -> int:
    """One day's step toward `cap` at `frac` of the remaining headroom.

    Rounds, but never rounds down to zero progress while headroom and `frac` are
    both positive — otherwise a small gap and a small `frac` could round to 0
    forever and the garrison would never actually reach `cap`. Never overshoots.
    """
    headroom = cap - current
    if headroom <= 0 or frac <= 0.0:
        return current
    gained = max(1, round(headroom * frac))
    return current + min(gained, headroom)


def apply_militia_recovery(planet: Planet, config: GameConfig) -> Planet:
    """One day's automatic militia regrowth toward the population-fraction cap (D11).

    Population-fraction/day, **allocation-independent** — runs regardless of
    ownership (a native/unaligned world regrows its own defenders too, GW plan
    decision #4). A no-op when the world has no population, no capacity, or no
    `groundwar` config, or when garrison is already at the cap; returns the same
    object unchanged in that case (the cron "skip the rewrite" convention
    `produce()`/`advance_build` already use). Armor recovers toward the same
    population-fraction cap at `militia_armor_recovery_frac`, but only when
    `planet.citadel_level >= armor_recovery_min_citadel_level` — an unfortified
    world fields no vehicles and regrows none, matching `seed_garrison`'s own
    armor-seeding gate (decision #5).
    """
    if config.groundwar is None or not planet.population:
        return planet
    capacity = colonist_capacity(planet, config)
    if capacity <= 0:
        return planet
    cfg = config.groundwar.garrison_economy
    cap = round(capacity * cfg.cap_frac)
    infantry = _recover_toward_cap(planet.garrison_infantry, cap, cfg.militia_recovery_frac)
    armor = planet.garrison_armor
    if planet.citadel_level >= cfg.armor_recovery_min_citadel_level:
        armor = _recover_toward_cap(armor, cap, cfg.militia_armor_recovery_frac)
    if infantry == planet.garrison_infantry and armor == planet.garrison_armor:
        return planet
    return replace(planet, garrison_infantry=infantry, garrison_armor=armor)


def apply_ground_recovery(planet: Planet, config: GameConfig, day: int) -> Planet:
    """Recover persisted planetary Resolve by one daily tick (GW-WP11, D8/D14).

    The day marker makes a duplicate cron firing idempotent. Destruction itself does
    not regenerate here: rubble remains strategic state until a later rebuilding
    system explicitly repairs it.
    """
    if (config.groundwar is None or planet.ground_resolve is None
            or planet.ground_last_assault_day is None
            or day <= planet.ground_last_assault_day):
        return planet
    elapsed = day - planet.ground_last_assault_day
    recovered = min(
        config.groundwar.resolve.start,
        planet.ground_resolve
        + elapsed * config.groundwar.settlement.resolve_recovery_per_day,
    )
    return replace(
        planet, ground_resolve=recovered, ground_last_assault_day=day)


# --- tactical assault actions and planetary AI (GW-WP10) ---------------------
#
# The POC `edge.groundwar.rules` is "pure over (Battle, seeded rng)" — the actual
# design (Bresenham LOS, Dijkstra reachability, AA point-blank falloff, sortie
# ring-placement, Resolve deltas) lives in its function bodies, not in its choice
# of a live mutable `Battle` object. Reusing that design without importing
# `edge.groundwar` (a dev-only app outside the core layer graph — `edge.core` may
# not import it) means re-hosting the same bodies against a small *transient*
# scratch battle, rebuilt fresh from the frozen `AssaultOperation` + regenerated
# `AssaultMap` inside each pure entry point below, mutated by near-verbatim ported
# functions, then frozen back into a new `AssaultOperation`. The scratch object
# never crosses a function boundary and is never hashed (only `AssaultOperation`
# is, G2/G4/G5) — exactly the discipline `survey.py` already uses for its own
# scratch Dijkstra dicts/heaps, just extended to a richer piece of scratch state.

TROOPER_NAMES = (
    "Rico", "Zim", "Flores", "Levy", "Jelal", "Kitten", "Shujumi", "Brumby",
    "Rasczak", "Migliaccio", "Bronski", "Cunha", "Navarre", "Mahmud",
)

_RUBBLE_COST = 2  # moving through a destroyed structure cell


# --- scratch battle state (transient, mutable, never hashed/returned) --------


@dataclass(slots=True)
class _Structure:
    """The battle-time mutable twin of `AssaultStructure`, footprint and all.

    Carries `w/h/origin_*` for the same reason the frozen record does: one HP pool
    over N cells, and a single designated cell that range and line of sight are
    measured from (see `AssaultStructure` for why that is a fixed cell rather than
    the nearest one).
    """

    id: int
    kind: StructureKind
    x: int
    y: int
    city_id: int
    hp: int
    hp_max: int
    w: int = 1
    h: int = 1
    origin_dx: int = 0
    origin_dy: int = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def cells(self) -> tuple[Vec, ...]:
        if self.w == 1 and self.h == 1:
            return ((self.x, self.y),)
        return tuple((self.x + dx, self.y + dy)
                     for dy in range(self.h) for dx in range(self.w))

    @property
    def ox(self) -> int:
        return self.x + self.origin_dx

    @property
    def oy(self) -> int:
        return self.y + self.origin_dy


@dataclass(slots=True)
class _Trooper:
    id: int
    suit_id: str
    name: str
    x: int
    y: int
    hp: int
    missiles: int
    jump_charges: int
    mp: int = 0
    actions: int = 0
    fired: bool = False
    detected: bool = False

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass(slots=True)
class _GarrisonUnit:
    id: int
    kind: Literal["infantry", "armor"]
    x: int
    y: int
    hp: int
    city_id: int

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass(slots=True)
class _Battle:
    """The transient scratch object ported functions mutate directly.

    `rng` lives here (not threaded as a per-call argument) so ported bodies can
    call `battle.rng.random()` literally unchanged from the POC — G4's "immutable
    core" governs *hashed* state, and this object is neither. `rng` is `None` for
    entry points that never draw (a typed `None.random()` failure is a loud,
    typecheck-visible bug if a future edit adds a draw without updating the
    caller, unlike silently handing every call site an unseeded `Random()`).
    """

    amap: AssaultMap
    gw: GroundwarConfig
    rng: Random | None
    structures: dict[int, _Structure]
    struct_at: dict[Vec, int]
    troopers: dict[int, _Trooper]
    garrison: dict[int, _GarrisonUnit]
    broadcast_done: set[int]
    cowed_scored: set[int]
    resolve: int
    resolve_cap: int
    surrender_threshold: int
    retrieval_turn: int
    local_turn: int
    outcome: str | None
    infantry_remaining: int
    armor_remaining: int
    next_id: int
    initial_strength: int
    events: list[tuple[str, str, int, int, bool]]  # (kind, text, x, y, friendly)

    def next_unit_id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.amap.width and 0 <= y < self.amap.height

    def structure_at(self, x: int, y: int) -> _Structure | None:
        sid = self.struct_at.get((x, y))
        return self.structures[sid] if sid is not None else None

    def trooper_at(self, x: int, y: int) -> _Trooper | None:
        for t in self.troopers.values():
            if t.alive and t.x == x and t.y == y:
                return t
        return None

    def garrison_at(self, x: int, y: int) -> _GarrisonUnit | None:
        for g in self.garrison.values():
            if g.alive and g.x == x and g.y == y:
                return g
        return None

    def live_troopers(self) -> list[_Trooper]:
        return [t for t in self.troopers.values() if t.alive]

    def city_structures(self, city_id: int, *kinds: StructureKind) -> list[_Structure]:
        return [s for s in self.structures.values()
                if s.city_id == city_id and s.alive and (not kinds or s.kind in kinds)]

    def city_garrison(self, city_id: int) -> list[_GarrisonUnit]:
        return [g for g in self.garrison.values() if g.alive and g.city_id == city_id]

    def city_cowed(self, city: AssaultCity) -> bool:
        """Every active defense of this city silenced — guns, AA, and fielded garrison."""
        return not self.city_structures(city.id, "turret", "aa", "citadel_gun") \
            and not self.city_garrison(city.id)

    def casualties(self) -> int:
        return sum(1 for t in self.troopers.values() if not t.alive)

    def log(self, kind: str, text: str, x: int = -1, y: int = -1, friendly: bool = True) -> None:
        self.events.append((kind, text, x, y, friendly))

    def rand(self) -> Random:
        assert self.rng is not None, "this action needs rng but none was supplied"
        return self.rng


def _suit(battle: _Battle, trooper: _Trooper) -> GwSuit:
    return battle.gw.suits[trooper.suit_id]


def _battle_for(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, rng: Random | None = None,
) -> _Battle:
    """Rebuild the transient scratch battle from the frozen operation + regenerated map
    (G5) — mirrors `survey_map_for`'s "regen + overlay" shape, extended to a full
    platoon/garrison/structure-damage overlay instead of just dug cells."""
    assert config.groundwar is not None
    structures = {
        s.id: _Structure(id=s.id, kind=s.kind, x=s.x, y=s.y, city_id=s.city_id,
                         hp=op.structure_hp.get(s.id, s.hp_max), hp_max=s.hp_max,
                         w=s.w, h=s.h, origin_dx=s.origin_dx, origin_dy=s.origin_dy)
        for s in amap.structures
    }
    # GW-WP25: reuse the map's own index instead of rebuilding one from `(s.x, s.y)`.
    # The old comprehension was one of exactly three places that assumed a structure
    # was a single cell; the map already knows every cell of every footprint.
    struct_at = {cell: s.id for cell, s in amap.struct_at.items()}
    troopers = {
        t.id: _Trooper(id=t.id, suit_id=t.suit_id, name=t.name, x=t.x, y=t.y, hp=t.hp,
                       missiles=t.missiles, jump_charges=t.jump_charges, mp=t.mp,
                       actions=t.actions, fired=t.fired, detected=t.detected)
        for t in op.platoon
    }
    garrison = {
        g.id: _GarrisonUnit(id=g.id, kind=g.kind, x=g.x, y=g.y, hp=g.hp, city_id=g.city_id)
        for g in op.garrison_units
    }
    return _Battle(
        amap=amap, gw=config.groundwar, rng=rng, structures=structures, struct_at=struct_at,
        troopers=troopers, garrison=garrison,
        broadcast_done=set(op.broadcast_cities), cowed_scored=set(op.cowed_cities),
        resolve=op.resolve, resolve_cap=config.groundwar.resolve.cap,
        surrender_threshold=op.surrender_threshold, retrieval_turn=op.retrieval_turn,
        local_turn=op.local_turn, outcome=op.outcome,
        infantry_remaining=op.infantry_remaining, armor_remaining=op.armor_remaining,
        next_id=op.next_unit_id, initial_strength=op.initial_strength, events=[],
    )


def _freeze_battle(op: AssaultOperation, battle: _Battle) -> AssaultOperation:
    """Serialize the mutated scratch battle back into a new frozen `AssaultOperation`.

    Dead troopers are **kept** in `platoon` (sorted by id) — GW-WP11 needs each
    casualty's `suit_id` to settle `Ship.suits`/`Ship.recruits` losses via
    `gw_force.apply_casualties`, which only a per-suit-class breakdown can drive.
    Dead garrison units are **dropped** — WP11 only needs the surviving-defender
    headcount (`infantry_remaining`/`armor_remaining`), never a specific unit's id.
    """
    platoon = tuple(sorted(
        (AssaultTrooper(id=t.id, suit_id=t.suit_id, name=t.name, x=t.x, y=t.y, hp=t.hp,
                        missiles=t.missiles, jump_charges=t.jump_charges, mp=t.mp,
                        actions=t.actions, fired=t.fired, detected=t.detected)
         for t in battle.troopers.values()), key=lambda t: t.id))
    garrison_units = tuple(sorted(
        (AssaultGarrisonUnit(id=g.id, kind=g.kind, x=g.x, y=g.y, hp=g.hp, city_id=g.city_id)
         for g in battle.garrison.values() if g.alive), key=lambda g: g.id))
    structure_hp = {s.id: s.hp for s in battle.structures.values() if s.hp != s.hp_max}
    return replace(
        op, dropped=True, platoon=platoon, garrison_units=garrison_units,
        structure_hp=structure_hp, broadcast_cities=frozenset(battle.broadcast_done),
        cowed_cities=frozenset(battle.cowed_scored), resolve=battle.resolve,
        local_turn=battle.local_turn, outcome=battle.outcome,
        infantry_remaining=battle.infantry_remaining, armor_remaining=battle.armor_remaining,
        next_unit_id=battle.next_id, initial_strength=battle.initial_strength,
        casualties=battle.casualties(),
    )


# --- battle-time geometry (distinct from the *static* generation-time
# `_move_cost` above — a destroyed wall must become passable rubble, which the
# static `blocked` frozenset can never reflect) --------------------------------


def _battle_move_cost(battle: _Battle, x: int, y: int) -> int:
    """Entry cost of a cell on foot; 0 == impassable (live structure or hard terrain)."""
    s = battle.structure_at(x, y)
    if s is not None:
        return 0 if s.alive else _RUBBLE_COST
    tc = battle.gw.terrain.get(battle.amap.feature[y][x])
    return tc.move_cost if tc else 1


def _battle_cover_at(battle: _Battle, x: int, y: int) -> float:
    s = battle.structure_at(x, y)
    if s is not None:
        return 0.15 if not s.alive else 0.0  # rubble is decent cover
    tc = battle.gw.terrain.get(battle.amap.feature[y][x])
    return tc.cover if tc else 0.0


def _occupied(battle: _Battle, x: int, y: int) -> bool:
    return battle.trooper_at(x, y) is not None or battle.garrison_at(x, y) is not None


def _dist(ax: int, ay: int, bx: int, by: int) -> float:
    return math.hypot(ax - bx, ay - by)


def city_range(city: AssaultCity, x: int, y: int) -> float:
    """Distance from a cell to the **nearest cell of a city**, zero inside it.

    GW-WP26: `broadcast_range` used to be measured to `city.cx, city.cy`, which was
    harmless while a capital was 30 cells wide and wrong the moment it became 46. A
    centre-anchored range means Command has to stand *deeper inside a bigger objective*
    to dictate terms — the range shrinks, in effect, exactly as the city grows — which
    inverts D31's whole point that Command wins by surviving to say the words rather
    than by joining the firefight.

    Measured against the bounding box rather than the silhouette on purpose: it is a
    player affordance, so erring generous is the safe direction, and it keeps meaning
    one size-independent thing when GW-WP28 makes cities non-rectangular. Same reasoning
    that anchored the GW-WP24 drop ring on the footprint edge.
    """
    dx = max(city.x0 - x, 0, x - city.x1)
    dy = max(city.y0 - y, 0, y - city.y1)
    return math.hypot(dx, dy)


def _line_of_sight(battle: _Battle, ax: int, ay: int, bx: int, by: int) -> bool:
    """Bresenham; blocked by LOS-blocking terrain or a live structure between endpoints.

    GW-WP25: a structure occupying **either endpoint** is exempted along the whole
    line, not just on the endpoint cell. Excluding only the two endpoint cells was
    correct while every structure was one cell — the target's only cell *was* the
    endpoint — but a shot at the far corner of a 4x2 depot crosses the depot's own
    other cells, which are neither endpoint, so the target would block the shot at
    itself and become unkillable. The same exemption covers a trooper standing in
    the rubble of a big building shooting out of it.
    """
    ignore = {s.id for s in (battle.structure_at(ax, ay), battle.structure_at(bx, by))
              if s is not None}
    dx, dy = abs(bx - ax), abs(by - ay)
    sx, sy = (1 if ax < bx else -1), (1 if ay < by else -1)
    err = dx - dy
    x, y = ax, ay
    while True:
        if (x, y) != (ax, ay) and (x, y) != (bx, by):
            s = battle.structure_at(x, y)
            if s is not None and s.alive and s.id not in ignore:
                return False
            tc = battle.gw.terrain.get(battle.amap.feature[y][x])
            if tc is not None and tc.blocks_los:
                return False
        if (x, y) == (bx, by):
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def _reachable(battle: _Battle, trooper: _Trooper) -> dict[Vec, int]:
    """Dijkstra over move costs within one move action's range; {} once spent."""
    if trooper.actions <= 0:
        return {}
    start = (trooper.x, trooper.y)
    best: dict[Vec, int] = {start: 0}
    heap: list[tuple[int, Vec]] = [(0, start)]
    while heap:
        cost, (x, y) = heapq.heappop(heap)
        if cost > best.get((x, y), 1 << 30):
            continue
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not battle.in_bounds(nx, ny):
                continue
            step = _battle_move_cost(battle, nx, ny)
            if step <= 0 or _occupied(battle, nx, ny):
                continue
            nc = cost + step
            if nc <= trooper.mp and nc < best.get((nx, ny), 1 << 30):
                best[(nx, ny)] = nc
                heapq.heappush(heap, (nc, (nx, ny)))
    del best[start]
    return best


# --- resolve -------------------------------------------------------------------


def _apply_resolve(battle: _Battle, delta: int, why: str) -> None:
    """delta < 0 drains defender resolve (good for the player); > 0 hardens it."""
    battle.resolve = max(0, min(battle.resolve_cap, battle.resolve + delta))
    arrow = "falls" if delta < 0 else "hardens"
    battle.log("resolve", f"Planetary resolve {arrow} {abs(delta)} — {why} "
                          f"({battle.resolve} left)", friendly=delta < 0)
    if battle.resolve <= battle.surrender_threshold and battle.outcome is None:
        battle.outcome = "surrender"
        battle.log("outcome", "The planetary government sues for peace. SURRENDER.",
                   friendly=True)


def _escalation_bonus(battle: _Battle) -> float:
    p = battle.gw.pressure
    turn = battle.local_turn + 1  # POC's 1-indexed `battle.turn`; `local_turn` counts
                                   # *completed* rounds, 0 before the first `EndGroundTurn`
    waves = (turn - 1) // p.escalation_every
    return min(p.escalation_acc_cap, waves * p.escalation_acc_bonus)


def _check_cowed(battle: _Battle, city_id: int) -> None:
    city = next(c for c in battle.amap.cities if c.id == city_id)
    if city_id not in battle.cowed_scored and battle.city_cowed(city):
        battle.cowed_scored.add(city_id)
        _apply_resolve(battle, -battle.gw.resolve.city_cowed, f"{city.name} lies silenced")


def _structure_destroyed(battle: _Battle, s: _Structure) -> None:
    r = battle.gw.resolve
    drains = {
        "turret": r.turret_destroyed, "aa": r.aa_destroyed, "sensor": r.sensor_destroyed,
        "wall": r.wall_breached, "gate": r.wall_breached,
        "citadel_gun": r.citadel_gun_destroyed,
        "building_military": r.military_building_destroyed,
    }
    label = s.kind.replace("_", " ")
    # Logged at the footprint's centre so a destruction marker sits *on* the building
    # rather than on its north-west corner.
    battle.log("destroyed", f"{label} destroyed",
               s.x + (s.w - 1) // 2, s.y + (s.h - 1) // 2, friendly=True)
    if s.kind == "building_civilian":
        _apply_resolve(battle, r.civilian_building_destroyed,
                       "civilian block leveled — atrocity stiffens them")
    else:
        _apply_resolve(battle, -drains[s.kind], f"{label} destroyed")
    _check_cowed(battle, s.city_id)


# --- attacks ---------------------------------------------------------------


def _spotter_bonus(battle: _Battle, tx: int, ty: int) -> float:
    """Accuracy a scout lends a missile fired at `(tx, ty)` (GW-WP24, D34).

    Keyed on the *target*, not the firer: the scout has to be forward, near what is being
    shot at, which is what makes bringing one a positioning decision rather than a passive
    stat. Pairs with `recon_radius` (D30) — the same trooper finds the AA and then makes
    the missile that silences it land.
    """
    best = 0.0
    for ally in battle.live_troopers():
        asuit = _suit(battle, ally)
        if asuit.spot_radius > 0 and _dist(ally.x, ally.y, tx, ty) <= asuit.spot_radius:
            best = max(best, asuit.spot_missile_bonus)
    return best


def _command_move_bonus(battle: _Battle, trooper: _Trooper) -> int:
    """Extra move points a nearby Command suit lends this trooper (GW-WP24, D31)."""
    best = 0
    for ally in battle.live_troopers():
        if ally is trooper:
            continue
        asuit = _suit(battle, ally)
        if (asuit.command_move_bonus > 0
                and _dist(ally.x, ally.y, trooper.x, trooper.y) <= asuit.command_radius):
            best = max(best, asuit.command_move_bonus)
    return best


def _command_bonus(battle: _Battle, trooper: _Trooper) -> float:
    for ally in battle.live_troopers():
        if ally is trooper:
            continue
        asuit = _suit(battle, ally)
        if asuit.command_radius > 0 and _dist(ally.x, ally.y, trooper.x, trooper.y) <= asuit.command_radius:
            return asuit.command_acc_bonus
    return 0.0


def _check_casualties(battle: _Battle) -> None:
    if battle.outcome is not None or battle.initial_strength <= 0:
        return
    dead = battle.casualties()
    if dead >= battle.initial_strength:
        battle.outcome = "wiped"
        battle.log("outcome", "The platoon is gone. Nobody made retrieval.", friendly=False)
    elif dead > battle.gw.pressure.casualty_ceiling * battle.initial_strength:
        battle.outcome = "casualties"
        battle.log("outcome", "Casualties past doctrine ceiling — mission aborted, "
                              "survivors recalled to the boat.", friendly=False)


def _trooper_hit(battle: _Battle, trooper: _Trooper, damage: int, source: str) -> None:
    dmg = max(1, damage - _suit(battle, trooper).armor)
    trooper.hp -= dmg
    battle.log("hit", f"{trooper.name} takes {dmg} from {source}"
                      f" ({max(0, trooper.hp)} hp)", trooper.x, trooper.y, friendly=False)
    if not trooper.alive:
        battle.log("killed", f"{trooper.name} is KIA.", trooper.x, trooper.y, friendly=False)
        _apply_resolve(battle, battle.gw.resolve.trooper_killed,
                       f"{trooper.name} down — the defenders take heart")
        _check_casualties(battle)


def fire_at(
    battle: _Battle, trooper: _Trooper, tx: int, ty: int, *, missile: bool = False,
) -> bool:
    """Attack the cell (structure or garrison unit). Returns True if the action spent."""
    if trooper.actions <= 0 or battle.outcome is not None:
        return False
    suit = _suit(battle, trooper)
    weapon = suit.missile if missile else suit.weapon
    if missile and trooper.missiles <= 0:
        battle.log("info", f"{trooper.name}: no missiles left.")
        return False
    if _dist(trooper.x, trooper.y, tx, ty) > weapon.range:
        battle.log("info", f"{trooper.name}: target out of range.")
        return False
    if not _line_of_sight(battle, trooper.x, trooper.y, tx, ty):
        battle.log("info", f"{trooper.name}: no line of sight.")
        return False
    target_s = battle.structure_at(tx, ty)
    target_g = battle.garrison_at(tx, ty)
    if (target_s is None or not target_s.alive) and target_g is None:
        battle.log("info", f"{trooper.name}: nothing to shoot there.")
        return False

    trooper.actions -= 1
    trooper.fired = True
    if missile:
        trooper.missiles -= 1
    acc = weapon.accuracy + _command_bonus(battle, trooper)
    if missile:
        acc += _spotter_bonus(battle, tx, ty)  # D34
    if not trooper.detected:
        acc += battle.gw.garrison.undetected_first_strike
    trooper.detected = True  # firing reveals you
    kind = "missile" if missile else "shot"
    rng = battle.rand()
    if target_g is not None:
        acc -= _battle_cover_at(battle, tx, ty)
        if rng.random() < acc:
            gcls = getattr(battle.gw.garrison, target_g.kind)
            dmg = max(1, weapon.damage - gcls.armor)
            target_g.hp -= dmg
            battle.log(kind, f"{trooper.name} hits {target_g.kind} for {dmg}", tx, ty)
            if not target_g.alive:
                battle.log("destroyed", f"{target_g.kind} unit destroyed", tx, ty)
                _apply_resolve(battle, -battle.gw.resolve.garrison_killed,
                               "garrison unit destroyed")
                _check_cowed(battle, target_g.city_id)
        else:
            battle.log("miss", f"{trooper.name} misses the {target_g.kind}", tx, ty)
    else:
        assert target_s is not None
        if rng.random() < acc:
            dmg = round(weapon.damage * weapon.structure_mult)
            target_s.hp -= dmg
            battle.log(kind, f"{trooper.name} hits the {target_s.kind.replace('_', ' ')} "
                             f"for {dmg}", tx, ty)
            if not target_s.alive:
                _structure_destroyed(battle, target_s)
        else:
            battle.log("miss", f"{trooper.name}'s {kind} goes wide", tx, ty)
    return True


def broadcast_terms(battle: _Battle, trooper: _Trooper) -> bool:
    """A Command suit dictates terms over a cowed city — the big resolve strike."""
    suit = _suit(battle, trooper)
    if suit.broadcast_range <= 0 or trooper.actions <= 0 or battle.outcome is not None:
        return False
    for city in battle.amap.cities:
        if city.id in battle.broadcast_done:
            continue
        if city_range(city, trooper.x, trooper.y) > suit.broadcast_range:
            continue
        if not battle.city_cowed(city):
            battle.log("info", f"{city.name} still resists — silence its defenses first.")
            continue
        battle.broadcast_done.add(city.id)
        trooper.actions -= 1
        trooper.fired = True
        battle.log("broadcast", f"{trooper.name} broadcasts terms over {city.name}: "
                                f"\"We can do this to every city you have.\"",
                   city.cx, city.cy)
        _apply_resolve(battle, -battle.gw.resolve.broadcast,
                       f"terms dictated over {city.name}")
        return True
    battle.log("info", f"{trooper.name}: no cowed city in broadcast range.")
    return False


# --- movement ----------------------------------------------------------------


def do_move(battle: _Battle, trooper: _Trooper, x: int, y: int) -> bool:
    """One action: walk anywhere within the suit's move range."""
    if battle.outcome is not None or trooper.actions <= 0:
        return False
    options = _reachable(battle, trooper)
    cost = options.get((x, y))
    if cost is None:
        return False
    trooper.x, trooper.y = x, y
    trooper.actions -= 1
    return True


def _aa_reaction_acc(aa_cfg: GwEmplacement, distance: float, escalation: float = 0.0) -> float:
    """AA hit chance against a drop/jump: base accuracy, plus a point-blank ramp that
    fades from full bonus at the muzzle to nothing at the edge of range, plus any
    escalation stiffening. Landing in the heart of the umbrella is deadly."""
    prox = 0.0
    if aa_cfg.range > 0:
        prox = aa_cfg.point_blank_bonus * (1.0 - min(1.0, distance / aa_cfg.range))
    return aa_cfg.accuracy + prox + escalation


def do_jump(battle: _Battle, trooper: _Trooper, x: int, y: int) -> bool:
    """One action: jump-jet hop — ignores terrain, draws AA reaction fire."""
    if battle.outcome is not None or trooper.actions <= 0 or trooper.jump_charges <= 0:
        return False
    suit = _suit(battle, trooper)
    if not battle.in_bounds(x, y) or _dist(trooper.x, trooper.y, x, y) > suit.jump_range:
        return False
    if _battle_move_cost(battle, x, y) <= 0 or _occupied(battle, x, y):
        return False
    trooper.actions -= 1
    trooper.jump_charges -= 1
    trooper.x, trooper.y = x, y
    battle.log("jump", f"{trooper.name} jumps — on the bounce!", x, y)
    aa_cfg = battle.gw.defenses.aa
    rng = battle.rand()
    for s in battle.structures.values():
        if s.kind != "aa" or not s.alive or trooper.hp <= 0:
            continue
        d = _dist(s.ox, s.oy, x, y)
        if d <= aa_cfg.range:
            if rng.random() < _aa_reaction_acc(aa_cfg, d, _escalation_bonus(battle)):
                _trooper_hit(battle, trooper, aa_cfg.damage, "AA fire mid-air")
            else:
                battle.log("miss", "AA fire bursts wide of the jump arc", x, y,
                           friendly=False)
    return True


# --- garrison placement (shared by the drop's pre-placement and sortie spawns) -


def _place_units(
    battle: _Battle, city: AssaultCity, kind: Literal["infantry", "armor"], count: int,
) -> int:
    """Place up to `count` garrison units of `kind` in a ring outward from a set
    of origin cells — ported from the POC's `_spawn_sortie` placement loop,
    factored out so both pre-placement (`GroundDrop`) and escalating sorties
    (`_spawn_sortie`) share it. Draws no rng (placement is a deterministic
    geometric search); returns how many were actually placed, which may be fewer
    than `count` if the city runs out of legal cells nearby.

    Origins are `city`'s gates (or a wall stub when gateless) for a terrestrial
    map; a Cloud City map has no wall structures to fall back to (`bulkhead` is
    permanent, non-structural terrain — GW-WP16), so it instead supplies
    `AssaultMap.spawn_anchors` (WP15's `defender_slots`) directly, which take
    priority whenever the map provides them.
    """
    if count <= 0:
        return 0
    if battle.amap.spawn_anchors:
        origins: list[Vec] = list(battle.amap.spawn_anchors)
    else:
        gates = [(s.ox, s.oy) for s in battle.structures.values()
                 if s.city_id == city.id and s.kind == "gate"]
        origins = gates or [(s.ox, s.oy) for s in battle.structures.values()
                            if s.city_id == city.id and s.kind == "wall"][:2]
    gcls = getattr(battle.gw.garrison, kind)
    placed = 0
    for ox, oy in origins:
        for r in range(1, 5):
            for nx, ny in ((ox - r, oy), (ox + r, oy), (ox, oy - r), (ox, oy + r)):
                if placed >= count:
                    return placed
                if battle.in_bounds(nx, ny) and _battle_move_cost(battle, nx, ny) > 0 \
                        and not _occupied(battle, nx, ny):
                    uid = battle.next_unit_id()
                    u = _GarrisonUnit(id=uid, kind=kind, x=nx, y=ny, hp=gcls.hp, city_id=city.id)
                    battle.garrison[uid] = u
                    placed += 1
    return placed


def _place_preplaced_garrison(battle: _Battle, op: AssaultOperation) -> None:
    """Station the interview-resolved pre-placed garrison share inside cities at drop
    (GW-WP10 garrison-deployment decision), weighting the citadel capital like the
    POC's sortie placement does (1.5x), then bank the rest as the finite pool
    `EndGroundTurn`'s sorties draw down. A running per-kind budget (never exceeding
    `reserved_infantry`/`reserved_armor` × `preplaced_frac`) guarantees the total
    placed can never exceed what the world actually has (G8 — no minting)."""
    frac = battle.gw.garrison.preplaced_frac
    budget_i = round(op.reserved_infantry * frac)
    budget_a = round(op.reserved_armor * frac)
    cities = battle.amap.cities
    total_weight = sum(1.5 if c.is_citadel else 1.0 for c in cities) or 1.0
    placed_i = placed_a = 0
    for city in cities:
        weight = (1.5 if city.is_citadel else 1.0) / total_weight
        want_i = max(0, min(budget_i - placed_i, round(budget_i * weight)))
        want_a = max(0, min(budget_a - placed_a, round(budget_a * weight)))
        placed_i += _place_units(battle, city, "infantry", want_i)
        placed_a += _place_units(battle, city, "armor", want_a)
    battle.infantry_remaining = op.reserved_infantry - placed_i
    battle.armor_remaining = op.reserved_armor - placed_a


# --- detection ---------------------------------------------------------------


def _sensor_jammed(battle: _Battle, sensor: _Structure) -> bool:
    return any(
        _suit(battle, t).jam_radius > 0
        and _dist(t.x, t.y, sensor.ox, sensor.oy) <= _suit(battle, t).jam_radius
        for t in battle.live_troopers()
    )


def update_detection(battle: _Battle) -> None:
    sensors = [s for s in battle.structures.values() if s.kind == "sensor" and s.alive]
    for t in battle.live_troopers():
        seen = False
        for s in sensors:
            if _sensor_jammed(battle, s):
                continue
            if _dist(s.ox, s.oy, t.x, t.y) <= battle.gw.defenses.sensor.radius * _suit(battle, t).signature:
                seen = True
                break
        if not seen:
            for g in battle.garrison.values():
                gcls = getattr(battle.gw.garrison, g.kind)
                if g.alive and _dist(g.x, g.y, t.x, t.y) <= gcls.sight \
                        and _line_of_sight(battle, g.x, g.y, t.x, t.y):
                    seen = True
                    break
        t.detected = seen or t.fired  # firing this turn keeps you lit


# --- defense phase (the planet's go) ------------------------------------------


def _emplacement_fire(battle: _Battle) -> None:
    bonus = _escalation_bonus(battle)
    stats = {"turret": battle.gw.defenses.turret, "citadel_gun": battle.gw.defenses.citadel_gun}
    rng = battle.rand()
    for s in battle.structures.values():
        if s.kind not in stats or not s.alive or battle.outcome is not None:
            continue
        w = stats[s.kind]
        targets = [t for t in battle.live_troopers()
                   if t.detected and _dist(s.ox, s.oy, t.x, t.y) <= w.range
                   and _line_of_sight(battle, s.ox, s.oy, t.x, t.y)]
        if not targets:
            continue
        target = min(targets, key=lambda t: _dist(s.ox, s.oy, t.x, t.y))
        acc = w.accuracy + bonus - _battle_cover_at(battle, target.x, target.y)
        if rng.random() < acc:
            _trooper_hit(battle, target, w.damage, s.kind.replace("_", " "))
        else:
            battle.log("miss", f"{s.kind.replace('_', ' ')} fire misses {target.name}",
                       target.x, target.y, friendly=False)


def _garrison_step(battle: _Battle, g: _GarrisonUnit) -> None:
    gcls = getattr(battle.gw.garrison, g.kind)
    visible = [t for t in battle.live_troopers() if t.detected]
    if not visible:
        return
    target = min(visible, key=lambda t: _dist(g.x, g.y, t.x, t.y))
    in_range = (_dist(g.x, g.y, target.x, target.y) <= gcls.weapon.range
                and _line_of_sight(battle, g.x, g.y, target.x, target.y))
    if in_range:
        rng = battle.rand()
        acc = gcls.weapon.accuracy - _battle_cover_at(battle, target.x, target.y)
        if rng.random() < acc:
            _trooper_hit(battle, target, gcls.weapon.damage, f"garrison {g.kind}")
        else:
            battle.log("miss", f"garrison {g.kind} misses {target.name}",
                       target.x, target.y, friendly=False)
        return
    # close the distance: greedy steps toward the target
    for _ in range(gcls.move):
        dx = (target.x > g.x) - (target.x < g.x)
        dy = (target.y > g.y) - (target.y < g.y)
        steps = [(g.x + dx, g.y + dy), (g.x + dx, g.y), (g.x, g.y + dy)]
        moved = False
        for nx, ny in steps:
            if battle.in_bounds(nx, ny) and _battle_move_cost(battle, nx, ny) > 0 \
                    and not _occupied(battle, nx, ny):
                g.x, g.y = nx, ny
                moved = True
                break
        if not moved:
            break


def _spawn_sortie(battle: _Battle) -> None:
    """An escalating wave, capped by the finite `infantry_remaining`/`armor_remaining`
    pool instead of the POC's unlimited supply (GW-WP10 garrison-deployment decision).
    A kind that has run out simply stops contributing to the wave rather than erroring;
    the POC's per-difficulty `garrison_mult` is dropped (no production equivalent —
    the finite pool already encodes world strength from big-bang seeding)."""
    p = battle.gw.pressure
    turn = battle.local_turn + 1
    if turn % p.escalation_every != 0:
        return
    wave = turn // p.escalation_every
    size = battle.gw.garrison.sortie_base + battle.gw.garrison.sortie_growth * (wave - 1)
    for city in battle.amap.cities:
        if battle.city_cowed(city):
            continue  # a silenced city sends no one
        n = max(1, round(size * (1.5 if city.is_citadel else 1.0)))
        want_armor = 0
        if wave >= battle.gw.garrison.armor_from_wave:
            want_armor = n // 3  # ~1 in 3, matching the POC's `placed % 3 == 2` ratio
        want_infantry = n - want_armor
        want_infantry = min(want_infantry, battle.infantry_remaining)
        want_armor = min(want_armor, battle.armor_remaining)
        placed_i = _place_units(battle, city, "infantry", want_infantry)
        placed_a = _place_units(battle, city, "armor", want_armor)
        battle.infantry_remaining -= placed_i
        battle.armor_remaining -= placed_a
        if placed_i + placed_a:
            battle.log("sortie", f"{city.name} sorties: {placed_i + placed_a} unit(s) "
                                 "take the field", city.cx, city.cy, friendly=False)


def start_player_phase(battle: _Battle) -> None:
    for t in battle.live_troopers():
        suit = _suit(battle, t)
        t.mp = suit.move + _command_move_bonus(battle, t)  # D31
        t.actions = battle.gw.platoon.actions_per_turn
        t.fired = False
    update_detection(battle)


def defense_phase(battle: _Battle) -> None:
    """The planet's whole turn; advances the clock and checks every outcome."""
    if battle.outcome is not None:
        return
    update_detection(battle)
    _emplacement_fire(battle)
    for g in sorted(battle.garrison.values(), key=lambda u: u.id):
        if g.alive and battle.outcome is None:
            _garrison_step(battle, g)
    if battle.outcome is None:
        _spawn_sortie(battle)
    if battle.outcome is None and (battle.local_turn + 1) >= battle.retrieval_turn:
        battle.outcome = "retrieval"
        battle.log("outcome", "The retrieval boat lifts with the planet unbowed. "
                              "Mission failed.", friendly=False)
    battle.local_turn += 1
    if battle.outcome is None:
        start_player_phase(battle)


# --- public pure entry points (reducer-facing) --------------------------------


def assault_turn_cost(config: GameConfig, local_turn: int) -> int:
    """Main-game turns owed for ending one tactical round (D4/D12, mirrors
    `survey.py`'s `_threshold_cost`) — one local turn here is one full `EndGroundTurn`
    round, not one march step."""
    assert config.groundwar is not None
    p = config.groundwar.pressure
    before = math.ceil(local_turn / p.local_turns_per_main_turn)
    after = math.ceil((local_turn + 1) / p.local_turns_per_main_turn)
    return (after - before) * p.main_turn_cost


def _begin_action(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, rng: Random | None, actor_id: int,
) -> tuple[_Battle, _Trooper]:
    if op.outcome is not None:
        raise MovementError("the assault has ended — extract to orbit")
    if not op.dropped:
        raise MovementError("the platoon has not dropped yet")
    battle = _battle_for(op, amap, config, rng)
    trooper = battle.troopers.get(actor_id)
    if trooper is None or not trooper.alive:
        raise MovementError("no such trooper")
    return battle, trooper


def assault_drop(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, rng: Random,
    placements: Sequence[tuple[str, int, int]], *, missile_budget: int | None = None,
) -> AssaultOperation:
    """Land the platoon and populate the battlefield's live garrison (GW-WP10, D3).

    `placements` is `(suit_id, x, y)` per trooper — the reducer has already validated
    it against the player's loadout (`gw_force.validate_loadout`); this checks only
    battlefield legality (distinct, in-bounds, passable cells). Runs AA reaction fire
    on the way down (ported from the POC's `resolve_drop`), then the interview-resolved
    garrison-deployment split: a `preplaced_frac` share of `reserved_infantry`/
    `reserved_armor` stationed inside cities, the remainder held as
    `infantry_remaining`/`armor_remaining` to feed `EndGroundTurn`'s escalating sorties.
    """
    assert config.groundwar is not None
    if op.outcome is not None:
        raise MovementError("the assault has ended — extract to orbit")
    if op.dropped:
        raise MovementError("the platoon has already dropped")
    if not placements:
        raise MovementError("a drop needs at least one trooper")
    seen: set[Vec] = set()
    for suit_id, x, y in placements:
        if (x, y) in seen:
            raise MovementError("two troopers cannot drop on the same cell")
        seen.add((x, y))
        if suit_id not in config.groundwar.suits:
            raise MovementError(f"no such suit class: {suit_id!r}")
        if not (0 <= x < amap.width and 0 <= y < amap.height):
            raise MovementError("a drop cell is off the map")
        if (x, y) in amap.blocked:
            raise MovementError("a drop cell is not passable")
        tc = config.groundwar.terrain.get(amap.feature[y][x])
        if tc is not None and tc.move_cost <= 0:
            raise MovementError("a drop cell is not passable")

    battle = _battle_for(op, amap, config, rng)
    battle.next_id = len(amap.structures) + 1  # dynamic ids start above the static map's range
    aa_cfg = battle.gw.defenses.aa
    missiles_left = sum(config.groundwar.suits[s].missiles for s, _x, _y in placements)
    if missile_budget is not None:
        missiles_left = max(0, missile_budget)
    committed = 0
    for i, (suit_id, x, y) in enumerate(placements):
        suit = battle.gw.suits[suit_id]
        loaded = min(suit.missiles, missiles_left)
        missiles_left -= loaded
        committed += loaded
        tid = battle.next_unit_id()
        t = _Trooper(id=tid, suit_id=suit_id, name=TROOPER_NAMES[i % len(TROOPER_NAMES)],
                    x=x, y=y, hp=suit.hp, missiles=loaded, jump_charges=suit.jump_charges)
        battle.troopers[tid] = t
        battle.log("drop", f"{t.name} ({suit.label}) capsule down", x, y)
        for s in battle.structures.values():
            if s.kind != "aa" or not s.alive:
                continue
            d = _dist(s.ox, s.oy, x, y)
            if d <= aa_cfg.range:
                if rng.random() < _aa_reaction_acc(aa_cfg, d):
                    _trooper_hit(battle, t, aa_cfg.damage, "anti-drop fire")
                else:
                    battle.log("miss", f"flak brackets {t.name}'s capsule", x, y,
                               friendly=False)
    battle.initial_strength = len(battle.troopers)
    _place_preplaced_garrison(battle, op)
    _check_casualties(battle)
    start_player_phase(battle)
    return replace(_freeze_battle(op, battle), ground_missiles_committed=committed)


def assault_move(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, actor_id: int, x: int, y: int,
) -> AssaultOperation:
    """One trooper's single-action ranged move (the POC's `do_move`) — distinct from
    the survey explorer's multi-cell supply march despite sharing the `GroundMove`
    command; draws no rng."""
    battle, trooper = _begin_action(op, amap, config, None, actor_id)
    if not do_move(battle, trooper, x, y):
        raise MovementError("that cell is not reachable this turn")
    return _freeze_battle(op, battle)


def assault_jump(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, rng: Random,
    actor_id: int, x: int, y: int,
) -> tuple[AssaultOperation, bool, tuple[tuple[str, str, int, int, bool], ...]]:
    """Returns `(new_op, hit, events)` — `hit` read directly off `do_jump`'s own log
    entries (an AA reaction landed) rather than diffed from before/after state at the
    reducer, since the trooper who jumped is trivially identified but a diff-based "was
    there an AA hit" would need to inspect the same log anyway. `events` is the full
    battle log for this action (GW-WP13-FU1) — the reducer surfaces the lines its own
    `GroundJumped` summary doesn't already narrate (KIA, Resolve deltas)."""
    battle, trooper = _begin_action(op, amap, config, rng, actor_id)
    if not do_jump(battle, trooper, x, y):
        raise MovementError("that jump is not legal")
    hit = any(kind == "hit" for kind, *_ in battle.events)
    return _freeze_battle(op, battle), hit, tuple(battle.events)


def assault_fire(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, rng: Random,
    actor_id: int, x: int, y: int, missile: bool = False,
) -> tuple[AssaultOperation, bool, bool, str, tuple[tuple[str, str, int, int, bool], ...]]:
    """Returns `(new_op, hit, destroyed, target_kind, events)`.

    `hit`/`destroyed`/`target_kind` are read directly off what `fire_at` actually
    targeted and logged, rather than diffed from before/after frozen state at the
    reducer: a garrison unit standing on a destroyed structure's rubble is a legal,
    occupiable cell, and `fire_at` always prefers the garrison unit there over the
    dead structure beneath it — a reducer-side diff keyed only on the map's static
    structure list at `(x, y)` could misattribute that shot to the structure instead.
    `events` is the full battle log for this action (GW-WP13-FU1) — the reducer
    surfaces the lines its own `GroundFired` summary doesn't already narrate (Resolve
    deltas from a destroyed structure or a newly cowed city).
    """
    battle, trooper = _begin_action(op, amap, config, rng, actor_id)
    target_kind = "garrison" if battle.garrison_at(x, y) is not None else "structure"
    if not fire_at(battle, trooper, x, y, missile=missile):
        raise CombatError("that shot is not legal")
    kinds = {kind for kind, *_ in battle.events}
    hit = bool(kinds & {"shot", "missile"})
    destroyed = "destroyed" in kinds
    return _freeze_battle(op, battle), hit, destroyed, target_kind, tuple(battle.events)


def assault_broadcast(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, actor_id: int,
) -> tuple[AssaultOperation, tuple[tuple[str, str, int, int, bool], ...]]:
    """Returns `(new_op, events)` — no rng, `broadcast_terms` is a deterministic
    range/cowed check, not a roll. `events` is the full battle log for this action
    (GW-WP13-FU1), surfacing the Resolve strike `GroundBroadcastMade`'s summary
    doesn't narrate."""
    battle, trooper = _begin_action(op, amap, config, None, actor_id)
    if not broadcast_terms(battle, trooper):
        raise CombatError("no cowed city in broadcast range")
    return _freeze_battle(op, battle), tuple(battle.events)


def assault_end_turn(
    op: AssaultOperation, amap: AssaultMap, config: GameConfig, rng: Random,
) -> tuple[AssaultOperation, tuple[tuple[str, str, int, int, bool], ...]]:
    """Run the planet's whole turn (`defense_phase`): detection, emplacement fire,
    garrison AI, escalating sorties, the retrieval clock, and the next player phase.

    Returns `(new_op, log)` — `log` is every `(kind, text, x, y, friendly)` line the
    defense phase produced (emplacement/garrison fire, sorties), so the reducer can
    surface each hit instead of only the round summary (a prior gap: trooper HP fell
    during this phase with nothing explaining why)."""
    if op.outcome is not None:
        raise MovementError("the assault has ended — extract to orbit")
    if not op.dropped:
        raise MovementError("the platoon has not dropped yet")
    battle = _battle_for(op, amap, config, rng)
    defense_phase(battle)
    return _freeze_battle(op, battle), tuple(battle.events)
