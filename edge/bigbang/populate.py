"""Populate the universe: ports, the StarDock, planets, and the player (DESIGN §5 step 7).

Phase-1 subset: standard ports at config density with the terminal-space class
split; one StarDock placed a few hops out; a *guaranteed* opposed-class port pair
near the Core so a new player can always earn (the §5 profitable-pair promise);
band-weighted planet *types* (no production/ownership yet); a Federation alliance
stub with the player seeded as its member. Aliens, home clusters, discoveries,
and planet ownership are deferred to Phase 2.
"""

from __future__ import annotations

import random
from dataclasses import replace

from edge.bigbang.topology import bfs_distances
from edge.core.config import GameConfig
from edge.core.economy import capacity_for_size
from edge.core.engine_room import apply_derived, build_subsystems
from edge.core.movement import shortest_path
from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass
from edge.core.models import (
    Alliance,
    Ownership,
    Planet,
    Player,
    Port,
    PortCommodity,
    Ship,
    UNOWNED,
    UniverseState,
)

# Sub-RNG salt for planet ownership (§5 RNG discipline): an independent draw stream
# so owner assignment never shifts the topology / port / planet-type draw order.
_OWNERSHIP_SALT = 0x504C414E  # "PLAN"

_REGION_ADJ = ("Halaf", "Vega", "Mirach", "Orin", "Cygnus", "Halcyon", "Tsoraan",
               "Verdani", "Kessrin", "Drelb", "Sol", "Antares", "Lyra", "Nexus")
_REGION_NOUN = ("Run", "Reach", "Verge", "Span", "Cluster", "Drift", "Expanse",
                "Marches", "Belt", "Gate", "Zone", "Hollow")

_TRADE_CLASSES = [
    PortClass.CLASS_1, PortClass.CLASS_2, PortClass.CLASS_3, PortClass.CLASS_4,
    PortClass.CLASS_5, PortClass.CLASS_6, PortClass.CLASS_7, PortClass.CLASS_8,
]

# Band -> weighted planet types (§4.2): the Hub favours habitable terrestrials,
# the outer bands skew to resource-extreme and uncolonisable worlds.
_PLANET_WEIGHTS: dict[str, list[tuple[str, int]]] = {
    "Hub": [("terrestrial_warm", 5), ("terrestrial_cool", 4), ("jovian", 2), ("barren", 1)],
    "Frontier": [("terrestrial_cool", 3), ("terrestrial_hot", 3), ("jovian", 3),
                 ("asteroid_belt", 3), ("barren", 2)],
    "Deep": [("terrestrial_hot", 2), ("terrestrial_cold", 3), ("asteroid_belt", 4),
             ("jovian", 3), ("barren", 4)],
    "Void": [("asteroid_belt", 4), ("barren", 5), ("jovian", 2), ("terrestrial_cold", 1)],
}


def region_name(rng: random.Random) -> str:
    return f"{rng.choice(_REGION_ADJ)} {rng.choice(_REGION_NOUN)}"


def _make_port(pid: int, sector_id: int, klass: PortClass, size: int, name: str,
               rng: random.Random, config: GameConfig) -> Port:
    cfg, econ = config.bigbang, config.economy
    capacity = capacity_for_size(size)
    trades = PORT_CLASS_TRADES[klass]
    lines = tuple(
        PortCommodity(
            commodity=c, mode=trades[c],
            stock=rng.randint(cfg.initial_stock_min, min(cfg.initial_stock_max, capacity)),
            capacity=capacity, base=econ.pricing(c).base, delta=econ.pricing(c).delta,
        )
        for c in Commodity
    )
    return Port(id=pid, sector_id=sector_id, name=name, klass=klass, size=size, commodities=lines)


def populate(state: UniverseState, config: GameConfig, rng: random.Random) -> None:
    cfg = config.bigbang
    sector_ids = sorted(state.sectors)
    hops = bfs_distances(state.adjacency, 1)

    # --- StarDock: a Class-9 port a few hops out from the Core ---------------
    dock_candidates = [
        s for s in sector_ids
        if cfg.stardock_min_hops <= hops.get(s, 10**9) <= cfg.stardock_max_hops
    ] or [s for s in sector_ids if s not in range(1, cfg.core_sector_count + 1)]
    dock_sector = rng.choice(dock_candidates)

    ports: dict[int, Port] = {}
    used_sectors: set[int] = {dock_sector}
    pid = 1
    ports[pid] = _make_port(pid, dock_sector, PortClass.STARDOCK, size=9, name="StarDock", rng=rng, config=config)
    pid += 1

    # --- standard ports at config density ------------------------------------
    for sid in sector_ids:
        if sid in used_sectors or rng.random() >= cfg.port_density:
            continue
        klass = rng.choices(_TRADE_CLASSES, weights=cfg.port_class_distribution, k=1)[0]
        size = rng.randint(1, 5)
        ports[pid] = _make_port(pid, sid, klass, size, f"Port {pid}", rng, config)
        used_sectors.add(sid)
        pid += 1

    # --- guaranteed profitable opposed pair within 5 hops of the Core --------
    near = [s for s in sector_ids if 1 <= hops.get(s, 10**9) <= 5 and s != dock_sector]
    if len(near) >= 2:
        a, b = rng.sample(near, 2)
        for sector, klass in ((a, PortClass.CLASS_1), (b, PortClass.CLASS_5)):
            existing = next((p for p in ports.values() if p.sector_id == sector), None)
            new_pid = existing.id if existing else pid
            ports[new_pid] = _make_port(new_pid, sector, klass, size=4, name=f"Port {new_pid}", rng=rng, config=config)
            # Mid-stock so the pair quotes a positive round-trip margin.
            ports[new_pid] = _mid_stock(ports[new_pid])
            if existing is None:
                pid += 1
            used_sectors.add(sector)

    state.ports = ports

    # --- planets (type only in Phase 1) --------------------------------------
    planets: dict[int, Planet] = {}
    plid = 1
    for sid in sector_ids:
        if rng.random() >= cfg.planet_density:
            continue
        band = state.sectors[sid].distance_band
        choices = _PLANET_WEIGHTS.get(band, _PLANET_WEIGHTS["Void"])
        ptype = rng.choices([t for t, _ in choices], weights=[w for _, w in choices], k=1)[0]
        planets[plid] = Planet(id=plid, sector_id=sid, name=f"Planet {plid}", planet_type=ptype)
        plid += 1
    state.planets = planets
    # Type-derived production shaping + band-weighted ownership (§4.2). Kept in a
    # post-pass so the planet-*type* draws above stay bit-identical to Phase 1; the
    # ownership roll uses its own sub-RNG (golden-master ordering).
    _finalize_planets(state, config)

    # --- alliance + player + starter ship ------------------------------------
    state.alliances = {1: Alliance(id=1, name="Federation")}
    sc = config.starter_ship
    # The player hull carries the engine-room model (§4.1): build its subsystems
    # from the class layout, then derive-on-write its aspect scalars so the stored
    # shields/warp/combat match the slotted parts (the flat config values are the
    # NPC fallback / caps). The Trailblazer's minimal layout derives exactly the
    # Phase-1 flat numbers (a regression pin, PHASE2_PLAN WP1).
    starter = Ship(
        id=1, type_id=sc.id, name=sc.name, owner_player_id=1, sector_id=1,
        holds_total=sc.holds_total, hull_current=sc.hull_max, hull_max=sc.hull_max,
        shields=sc.shields_max, warp_speed=sc.warp_speed, combat_speed=sc.combat_speed,
        cloak_rating=sc.cloak_rating, sensor_rating=sc.sensor_rating,
        turns_per_warp=sc.turns_per_warp, colonist_capacity=sc.colonist_capacity,
        subsystems=build_subsystems(sc),
    )
    state.ships = {1: apply_derived(starter, config)}
    # StarDock is an auto-known route: the path from the start sector to the dock
    # opens pre-explored so the opening signpost is actionable (the player can
    # `TravelTo` it on turn one). Only the shortest path is revealed — the rest of
    # the universe stays fogged. The route is also recorded as the breadcrumb chain
    # so the way back reads correctly from the dock.
    dock_route = shortest_path(state.adjacency, 1, dock_sector) or [1]
    entered_from = {dock_route[i + 1]: dock_route[i] for i in range(len(dock_route) - 1)}
    state.players = {
        1: Player(
            id=1, name="Trailblazer", ship_id=1,
            latinum=config.economy.starting_latinum, bank_balance=config.economy.starting_bank,
            turns_remaining=config.turns_per_day, alliance_id=1,
            explored_sectors=frozenset(dock_route), entered_from=entered_from,
        )
    }


def _finalize_planets(state: UniverseState, config: GameConfig) -> None:
    """Set each planet's yield/habitability from its type and assign ownership (§4.2).

    Core worlds are owned by the governing alliance unconditionally; non-Core worlds
    are alliance-owned or unowned by a band-weighted, *monotone* unowned fraction
    (Hub→Frontier→Deep→Void), enforced by construction so the §5 step-8 invariant
    holds per seed rather than only in expectation.
    """
    types = config.planets.types
    for pid, planet in list(state.planets.items()):
        profile = types.get(planet.planet_type)
        if profile is not None:
            state.planets[pid] = replace(
                planet, habitability_cap=profile.habitability,
                yield_profile={Commodity(k): v for k, v in profile.yield_profile.items()},
            )

    gov = state.game.core_governing_alliance_id
    orng = random.Random(state.game.seed ^ _OWNERSHIP_SALT)
    by_band: dict[str, list[int]] = {}
    for pid, planet in state.planets.items():
        if state.sectors[planet.sector_id].is_galactic_core:
            state.planets[pid] = replace(planet, owner=Ownership("alliance", gov))
        else:
            by_band.setdefault(state.sectors[planet.sector_id].distance_band, []).append(pid)

    floor = 0.0  # the previous band's realized unowned fraction (kept non-decreasing)
    for band in (b.name for b in config.bigbang.bands):
        pids = by_band.get(band)
        if not pids:
            continue
        weights = config.planets.ownership.get(band)
        target = weights.none / (weights.none + weights.alliance) if weights else floor
        n = len(pids)
        unowned = round(max(target, floor) * n)
        if unowned / n < floor:  # rounding must never drop below the prior band
            unowned = min(n, unowned + 1)
        floor = unowned / n
        orng.shuffle(pids)
        for i, pid in enumerate(pids):
            owner = UNOWNED if i < unowned else Ownership("alliance", gov)
            state.planets[pid] = replace(state.planets[pid], owner=owner)


def _mid_stock(port: Port) -> Port:
    """Set every commodity to ~half capacity (a neutral price point)."""
    lines = tuple(replace(c, stock=c.capacity // 2) for c in port.commodities)
    return replace(port, commodities=lines)
