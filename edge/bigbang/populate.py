"""Populate the universe: ports, the Stardock, and planets (DESIGN §5 step 7).

Phase-1 subset: standard ports at config density with the terminal-space class
split; one Stardock placed a few hops out; a *guaranteed* opposed-class port pair
near the Core so a new player can always earn (the §5 profitable-pair promise);
band-weighted planet *types* (no production/ownership yet). Aliens, home clusters,
discoveries, and planet ownership are deferred to Phase 2.

The **player is not created here.** Enrolling a player is a recorded `JoinGame`
command (`core.rules`), not part of seed-derived universe generation — so a player
survives a save/load round-trip via the command log and multiple players can join
the same universe (DESIGN §3). `populate` builds only the shared, seed-derived world.
"""

from __future__ import annotations

import random
from dataclasses import replace
from collections import defaultdict

from edge.bigbang.naming import NameGenerator
from edge.bigbang.topology import bfs_distances
from edge.core.config import GameConfig
from edge.core.economy import capacity_for_size
from edge.core.engine_room import build_layouts
from edge.core.movement import one_way_exits
from edge.core.planets import is_landable, normalize_belt
from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass, Subsystem
from edge.core.models import (
    Ownership,
    Planet,
    Port,
    PortCommodity,
    Starbase,
    SubsystemState,
    UNOWNED,
    UniverseState,
)

# Sub-RNG salt for planet ownership (§5 RNG discipline): an independent draw stream
# so owner assignment never shifts the topology / port / planet-type draw order.
_OWNERSHIP_SALT = 0x504C414E  # "PLAN"
# A second independent salt for orbital-starbase placement (same discipline).
_STARBASE_SALT = 0x42415345  # "BASE"
# A third for base-hosted market minting (WP78): ports minted under starbases.
_MARKET_SALT = 0x4D41524B  # "MARK"

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
    # Seed the port's purse at its size-scaled liquidity floor (§8, WP47), so day-one
    # trading behaves like Phase 1–2: the port can afford to buy, and the daily drip
    # keeps it topped up. A soft figure when the order-book market is disabled.
    purse = size * econ.market.min_purse_per_size
    return Port(id=pid, sector_id=sector_id, name=name, klass=klass, size=size,
                commodities=lines, latinum=purse)


def populate(state: UniverseState, config: GameConfig, rng: random.Random) -> None:
    cfg = config.bigbang
    sector_ids = sorted(state.sectors)
    hops = bfs_distances(state.adjacency, 1)

    # --- Stardock: a Class-9 port a few hops out from the Core ---------------
    # Bias toward the *near* edge of the 2–5 hop band: a uniform choice would skew
    # far (the universe simply holds many more sectors at 4–5 hops than at 2–3), so
    # weight each candidate by (max_hops - hops + 1)**3 — the closest tier dominates
    # while farther sectors stay possible, keeping the dock a short hop from home.
    dock_candidates = [
        s for s in sector_ids
        if cfg.stardock_min_hops <= hops.get(s, 10**9) <= cfg.stardock_max_hops
    ]
    if dock_candidates:
        weights = [(cfg.stardock_max_hops - hops[s] + 1) ** 3 for s in dock_candidates]
        dock_sector = rng.choices(dock_candidates, weights=weights, k=1)[0]
    else:
        # Degenerate topology with nothing in-band: fall back to the closest non-Core
        # sector rather than any non-Core sector (which could be deep space).
        non_core = [s for s in sector_ids if s not in range(1, cfg.core_sector_count + 1)]
        dock_sector = min(non_core, key=lambda s: hops.get(s, 10**9))

    names_cfg = config.names
    stardock_gen = NameGenerator(names_cfg.stardock if names_cfg else None, "Stardock", rng)
    port_gen = NameGenerator(names_cfg.ports if names_cfg else None, "Port", rng)
    
    planet_gens = defaultdict(lambda: NameGenerator(None, "Planet", rng))
    if names_cfg:
        terr_gen = NameGenerator(names_cfg.planets.terrestrial, "Planet", rng)
        for t in ["terrestrial_warm", "terrestrial_cool", "terrestrial_hot", "terrestrial_cold"]:
            planet_gens[t] = terr_gen
        planet_gens["jovian"] = NameGenerator(names_cfg.planets.jovian, "Planet", rng)
        planet_gens["barren"] = NameGenerator(names_cfg.planets.barren, "Planet", rng)
        planet_gens["asteroid_belt"] = NameGenerator(names_cfg.planets.asteroid_belt, "Asteroid", rng)

    ports: dict[int, Port] = {}
    used_sectors: set[int] = {dock_sector}
    pid = 1
    ports[pid] = _make_port(pid, dock_sector, PortClass.STARDOCK, size=9, name=stardock_gen.draw(), rng=rng, config=config)
    pid += 1

    # --- standard ports at config density ------------------------------------
    for sid in sector_ids:
        if sid in used_sectors or rng.random() >= cfg.port_density:
            continue
        klass = rng.choices(_TRADE_CLASSES, weights=cfg.port_class_distribution, k=1)[0]
        size = rng.randint(1, 5)
        ports[pid] = _make_port(pid, sid, klass, size, port_gen.draw(), rng, config)
        used_sectors.add(sid)
        pid += 1

    # --- guaranteed profitable opposed pair within 5 hops of the Core --------
    near = [s for s in sector_ids if 1 <= hops.get(s, 10**9) <= 5 and s != dock_sector]
    if len(near) >= 2:
        a, b = rng.sample(near, 2)
        for sector, klass in ((a, PortClass.CLASS_1), (b, PortClass.CLASS_5)):
            existing = next((p for p in ports.values() if p.sector_id == sector), None)
            new_pid = existing.id if existing else pid
            p_name = existing.name if existing else port_gen.draw()
            ports[new_pid] = _make_port(new_pid, sector, klass, size=4, name=p_name, rng=rng, config=config)
            # Mid-stock so the pair quotes a positive round-trip margin.
            ports[new_pid] = _mid_stock(ports[new_pid])
            if existing is None:
                pid += 1
            used_sectors.add(sector)

    state.ports = ports

    # --- planets (type only in Phase 1) --------------------------------------
    # One-way-source sectors carry a wormhole (salt_discoveries, §7) and a sector
    # never holds both a planet and a space discovery, so they stay planet-free.
    one_way = {sid for sid in sector_ids if one_way_exits(state.adjacency, sid)}
    planets: dict[int, Planet] = {}
    plid = 1
    for sid in sector_ids:
        # Draw unconditionally so the build-RNG order is stable; the one-way skip
        # only suppresses placement, it doesn't consume an extra draw.
        if rng.random() >= cfg.planet_density or sid in one_way:
            continue
        band = state.sectors[sid].distance_band
        choices = _PLANET_WEIGHTS.get(band, _PLANET_WEIGHTS["Void"])
        ptype = rng.choices([t for t, _ in choices], weights=[w for _, w in choices], k=1)[0]
        planets[plid] = Planet(id=plid, sector_id=sid, name=planet_gens[ptype].draw(), planet_type=ptype)
        plid += 1
    state.planets = planets
    # Type-derived production shaping + band-weighted ownership (§4.2). Kept in a
    # post-pass so the planet-*type* draws above stay bit-identical to Phase 1; the
    # ownership roll uses its own sub-RNG (golden-master ordering).
    _finalize_planets(state, config)
    _place_starbases(state, config)
    _normalize_belts(state, config)  # belts are spatial features, never colonies/bases (§4.2)
    _host_markets(state, config)
    # The player is enrolled separately by the `JoinGame` reducer (`core.rules`), not
    # seeded here — joining is a recorded command, not seed-derived world generation.


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
    for band in (b.name for b in config.bigbang.active_bands()):
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

    # A gas giant an alliance holds already floats a Cloud City (§4.2, PT-54) — a bloc does not
    # own a world it cannot stand on, and taking one by invasion should take a working city.
    # RNG-free, so it cannot perturb the draw order above.
    size = config.planets.cloud_city_npc_size
    if size > 0:
        for pid, planet in state.planets.items():
            if planet.planet_type == "jovian" and planet.owner.is_owned:
                state.planets[pid] = replace(planet, cloud_city_size=size)


def _strip_reactor_keystone(subsystems: dict[Subsystem, SubsystemState]) -> dict[Subsystem, SubsystemState]:
    """Empty the fusion reactor's keystone slot — the minimal break that derelicts a base.

    Derelict is emergent (§4.2): with the keystone `converter` gone the base can no
    longer power itself, yet every other component remains as a salvage cache. Repair
    is then just refilling the one slot (Phase 3).
    """
    reactor = subsystems[Subsystem.FUSION_REACTOR]
    assert reactor.keystone_index is not None
    slots = list(reactor.slots)
    slots[reactor.keystone_index] = None
    out = dict(subsystems)
    out[Subsystem.FUSION_REACTOR] = replace(reactor, slots=tuple(slots))
    return out


def _place_starbases(state: UniverseState, config: GameConfig) -> None:
    """Hang orbital bases off planets (§4.2, WP4) using an independent sub-RNG.

    Owned worlds carry an **intact** base with probability `owned_base_chance`; an
    unowned, uninhabited world carries a **derelict** (built then stripped of its
    reactor keystone) with probability `derelict_chance`. Placement runs after
    ownership so an owned/unowned split is known, and on its own RNG stream so it
    never perturbs the topology/port/planet draws (golden-master ordering, §5).
    """
    sbcfg = config.starbase
    if sbcfg is None:
        return
    srng = random.Random(state.game.seed ^ _STARBASE_SALT)
    bases: dict[int, Starbase] = {}
    bid = 1
    for pid in sorted(state.planets):  # deterministic order, independent of dict order
        planet = state.planets[pid]
        subsystems = build_layouts(sbcfg.subsystems)
        if planet.owner.is_owned:
            if srng.random() >= sbcfg.owned_base_chance:
                continue
            owner = planet.owner
        elif planet.inhabited_by_species_id is None:
            if srng.random() >= sbcfg.derelict_chance:
                continue
            owner = UNOWNED
            subsystems = _strip_reactor_keystone(subsystems)  # derelict by construction
        else:
            continue
        bases[bid] = Starbase(
            id=bid, sector_id=planet.sector_id, planet_id=pid,
            ship_class_id=sbcfg.ship_class_id, owner=owner, subsystems=subsystems,
        )
        state.planets[pid] = replace(planet, starbase_id=bid)
        bid += 1
    state.starbases = bases


def _normalize_belts(state: UniverseState, config: GameConfig) -> None:
    """Enforce the belt invariant (§4.2): asteroid belts are spatial features, not colonies.

    A belt holds no owner, colonists, stores, allocation, citadel, treasury, garrison, or
    orbital starbase — it is scanned and mined in orbit only. Run after starbase placement
    (so a belt's base is dropped before markets are minted) and before the ownership/type
    RNG-free, so it never perturbs golden-master ordering. `core.planets.normalize_belt`
    is idempotent, so re-reading a legacy belt on load converges to the same clean world.
    """
    belt_pids = {pid for pid, p in state.planets.items()
                 if not is_landable(p.planet_type, config)}
    if not belt_pids:
        return
    # Drop any orbital base hung off a belt before it can host a market.
    state.starbases = {bid: b for bid, b in state.starbases.items()
                       if b.planet_id not in belt_pids}
    # A belt is a *finite* body of ore (§4.2, PT-52): seed its reserve here, band-weighted, on
    # its own sub-RNG — like every other post-pass, so it cannot perturb the planet-type draw
    # order the golden masters depend on. Richer fields lie further out, so the deep bands pay
    # for the trip; the reserve never regrows, so a mining camp is a place you exhaust.
    cfg = config.planets
    rng = random.Random(f"{state.game.seed}-beltreserve")
    for pid in sorted(belt_pids):
        planet = normalize_belt(state.planets[pid], config)
        band = state.sectors[planet.sector_id].distance_band
        scale = cfg.belt_reserve_band_scale.get(band, 1.0)
        spread = rng.uniform(1.0 - cfg.belt_reserve_spread, 1.0 + cfg.belt_reserve_spread)
        reserve = max(cfg.asteroid_mining, round(cfg.belt_reserve_base * scale * spread))
        state.planets[pid] = replace(planet, ore_reserve=reserve, ore_reserve_max=reserve)


def _host_markets(state: UniverseState, config: GameConfig) -> None:
    """Every starbase sector hosts a market: mint a port where none exists (§4.2, WP78).

    The base **is** the sector's trading post — a starbase takes the place of a
    free-standing port. Where the port draw already landed one in a base's sector it
    simply becomes base-hosted; otherwise a standard-class port is minted here. Access
    is gated at the trade seam (`rules._market_port`): dark while the base is derelict,
    closed to players its owner counts as enemies — so a derelict's market is one more
    thing repair-and-claim switches on. Runs on its own sub-RNG after starbase
    placement so it never perturbs the earlier draws (golden-master ordering, §5).
    """
    if not state.starbases:
        return
    mrng = random.Random(state.game.seed ^ _MARKET_SALT)
    names_cfg = config.names
    port_gen = NameGenerator(names_cfg.ports if names_cfg else None, "Port", mrng)
    with_port = {p.sector_id for p in state.ports.values()}
    pid = max(state.ports, default=0) + 1
    for bid in sorted(state.starbases):
        sector_id = state.starbases[bid].sector_id
        if sector_id in with_port:
            continue
        klass = mrng.choices(_TRADE_CLASSES, weights=config.bigbang.port_class_distribution, k=1)[0]
        size = mrng.randint(1, 5)
        state.ports[pid] = _make_port(pid, sector_id, klass, size, port_gen.draw(), mrng, config)
        with_port.add(sector_id)
        pid += 1


def _mid_stock(port: Port) -> Port:
    """Set every commodity to ~half capacity (a neutral price point)."""
    lines = tuple(replace(c, stock=c.capacity // 2) for c in port.commodities)
    return replace(port, commodities=lines)
