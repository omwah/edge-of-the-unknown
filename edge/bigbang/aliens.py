"""Populate alien species from the roster (DESIGN §5 step 6, §6; PHASE2_PLAN WP7).

The big bang draws a **seeded subset** of the roster's species pool (not every species
need appear, §6), draws each one's `base_disposition` from its bounded `center ±
variance` spread (so stance varies between universe generations), and assigns each a
**contact point** — a non-Core sector in a distance band — guaranteeing at least one
friendly contact per non-empty band (the §5 step-8 resupply invariant).

Phase 2 places **only friendly-band** species: every drawn disposition is clamped up
into the amity band, so no hostile encounter can spawn (hostiles are Phase 3). The
roster's alliances become `state.alliances`, generalising the Phase-1 Federation stub —
no alliance is privileged in the schema (CLAUDE.md); the default roster simply names the
Federation as the Core's governor and seeds the player into it.

Runs on its own sub-RNG (`Random(seed ^ _SPECIES_SALT)`) so species draws never shift
the topology / port / planet / discovery draw order (golden-master ordering, §5).
"""

from __future__ import annotations

import random
from dataclasses import replace

from edge.core.aliens import is_friendly
from edge.core.config import GameConfig, RosterConfig, SpeciesConfig
from edge.core.enums import PortClass
from edge.core.models import Alliance, AlienSpecies, UniverseState

# Independent draw stream for species placement (§5 RNG discipline).
_SPECIES_SALT = 0x53504543  # "SPEC"


def build_alliances(config: GameConfig) -> dict[int, Alliance]:
    """The roster's alliances as entities (or the Federation stub when no roster)."""
    roster = config.roster
    if roster is None:
        return {1: Alliance(id=1, name="Federation")}
    return {
        a.id: Alliance(id=a.id, name=a.name, banner=a.banner, covets_core=a.covets_core)
        for a in roster.alliances
    }


def _friendly_disposition(center: float, variance: float, config: GameConfig,
                          rng: random.Random) -> float:
    """Draw a base disposition, clamped into the friendly band for Phase-2 placement.

    The draw is the species' per-generation stance (§6); clamping the lower bound to the
    amity threshold keeps every *placed* species friendly while still letting the high
    end vary. (Phase 3 lifts the clamp so hostiles can spawn.)
    """
    floor = config.aliens.amity_threshold
    drawn = rng.uniform(center - variance, center + variance)
    return max(floor, min(1.0, drawn))


def populate_species(state: UniverseState, config: GameConfig) -> None:
    """Draw a friendly-band subset of the roster and place it across the bands (WP7)."""
    state.alliances = build_alliances(config)
    roster = config.roster
    if roster is None or not roster.species:
        return

    rng = random.Random(state.game.seed ^ _SPECIES_SALT)

    # Non-Core sectors grouped by band — the home lanes where aliens are met (the Core
    # itself stays free of placed contacts; its safety is the governing alliance's).
    band_order = [b.name for b in config.bigbang.bands]
    sectors_by_band: dict[str, list[int]] = {b: [] for b in band_order}
    for sid in sorted(state.sectors):
        sector = state.sectors[sid]
        if sector.is_galactic_core:
            continue
        sectors_by_band.setdefault(sector.distance_band, []).append(sid)
    # The StarDock sector is reserved for the curated Core-welcome greeting party
    # (`_place_stardock_contacts`) — keep band homes and their clusters off it, so a
    # rival-bloc ship can never wander into the new player's first port of call.
    dock = next((p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)
    reserved = frozenset({dock.sector_id}) if dock is not None else frozenset()
    for sectors in sectors_by_band.values():
        sectors[:] = [s for s in sectors if s not in reserved]
    live_bands = [b for b in band_order if sectors_by_band.get(b)]
    if not live_bands:
        return

    # Seeded subset: shuffle the pool, take a count in [subset_min, subset_max] (clamped
    # to the pool size and to at least one-per-live-band so the resupply invariant holds).
    # Governing-alliance members are excluded here — they are settled in the Core + home
    # lanes by `_populate_governing_space`, the only path that enters the Core (WP18).
    gov = state.game.core_governing_alliance_id
    pool = sorted((s for s in roster.species if s.alliance_id != gov), key=lambda s: s.id)
    rng.shuffle(pool)
    lo = max(roster.subset_min, len(live_bands))
    hi = max(roster.subset_max, lo)
    count = min(len(pool), rng.randint(lo, hi))
    chosen = pool[:count]

    # Band assignment: honour a species' `home_band` hint when that band is live, else
    # round-robin — but first guarantee each live band gets one contact (front of the
    # shuffled list seeds the guarantee deterministically).
    assignment: list[str] = []
    for i, _ in enumerate(chosen):
        assignment.append(live_bands[i] if i < len(live_bands) else "")
    for i, sp in enumerate(chosen):
        if assignment[i]:
            continue
        if sp.home_band in sectors_by_band and sectors_by_band[sp.home_band]:
            assignment[i] = sp.home_band
        else:
            assignment[i] = live_bands[i % len(live_bands)]

    # One base disposition per species *kind*, memoised so every ship of a species shares
    # it — the player's reputation is keyed by kind (`roster_id`), so a kind must present a
    # single effective disposition regardless of which of its ships is met.
    bases: dict[str, float] = {}
    placed: dict[int, AlienSpecies] = {}
    next_id = 1
    for sp, band in zip(chosen, assignment):
        home = rng.choice(sectors_by_band[band])
        next_id = _place_cluster(placed, next_id, sp, home, band,
                                 _base_for(bases, sp, config, rng), state, config, rng,
                                 reserved=reserved)

    _populate_governing_space(state, config, roster, rng, placed, bases)
    _place_stardock_contacts(state, config, roster, rng, placed, bases)
    state.species = placed
    _assign_region_control(state, placed)


def _base_for(bases: dict[str, float], sp: SpeciesConfig,
              config: GameConfig, rng: random.Random) -> float:
    """The species kind's base disposition, drawn once per generation and memoised."""
    if sp.id not in bases:
        bases[sp.id] = _friendly_disposition(sp.disposition_center, sp.disposition_variance,
                                             config, rng)
    return bases[sp.id]


def _cluster_sectors(state: UniverseState, home: int, radius: int,
                     reserved: frozenset[int]) -> list[int]:
    """Non-Core, non-reserved sectors within `radius` warp-hops of `home`.

    A bounded BFS over the directed warp graph (deterministic neighbour order), used to
    scatter a species' satellite ships around its home sector (§6.3 presence). The Core and
    the reserved StarDock sector are excluded so clusters never breach curated space.
    """
    seen = {home}
    frontier = [home]
    out: list[int] = []
    for _ in range(radius):
        nxt: list[int] = []
        for s in frontier:
            for n in sorted(state.adjacency.get(s, ())):
                if n in seen:
                    continue
                seen.add(n)
                nxt.append(n)
                if not state.sectors[n].is_galactic_core and n not in reserved:
                    out.append(n)
        frontier = nxt
    return out


def _place_cluster(placed: dict[int, AlienSpecies], next_id: int, sp: SpeciesConfig,
                   home: int, band: str, base: float, state: UniverseState,
                   config: GameConfig, rng: random.Random, *,
                   reserved: frozenset[int]) -> int:
    """Place a species' home ship plus `ships_per_home - 1` satellites around it (§6.3).

    Satellites are the same kind (shared `roster_id`/base), scattered across non-Core,
    non-reserved sectors within `home_cluster_radius` hops, so a species is *met as a
    cluster* rather than a lone contact. Returns the advanced instance-id counter.
    """
    assert config.roster is not None
    placed[next_id] = _make_species(next_id, sp, home, band, base, config)
    next_id += 1
    satellites = config.roster.ships_per_home - 1
    if satellites <= 0:
        return next_id
    candidates = _cluster_sectors(state, home, config.roster.home_cluster_radius, reserved)
    rng.shuffle(candidates)
    for sat in candidates[:satellites]:
        sat_band = state.sectors[sat].distance_band
        placed[next_id] = _make_species(next_id, sp, sat, sat_band, base, config)
        next_id += 1
    return next_id


def _assign_region_control(state: UniverseState, placed: dict[int, AlienSpecies]) -> None:
    """Stamp each region's controlling species/alliance from the species placed in it.

    A region is controlled by the species present in its sectors — leader first, then
    lowest id (deterministic). Regions with no placed species stay uncontrolled. Pure
    post-processing over `placed`: no RNG draws, so the golden-master draw order is
    untouched (it only mutates `state.regions`, shifting `state_hash`). Core regions
    resolve to the governing leader (always settled in the Core, §6.3).
    """
    by_region: dict[int, list[AlienSpecies]] = {}
    for sp in placed.values():
        sector = state.sectors.get(sp.sector_id)
        if sector is None:
            continue
        by_region.setdefault(sector.region_id, []).append(sp)
    for region_id, members in by_region.items():
        region = state.regions.get(region_id)
        if region is None:
            continue
        controller = min(members, key=lambda s: (s.alliance_role != "leader", s.id))
        state.regions[region_id] = replace(
            region, controlling_species_id=controller.id,
            controlling_alliance_id=controller.alliance_id,
        )


def _make_species(sid: int, sp: SpeciesConfig, sector_id: int, band: str,
                  base: float, config: GameConfig) -> AlienSpecies:
    """Build one placed ship of a species at `sector_id` with its kind's shared `base`."""
    assert is_friendly(base, config.aliens)  # Phase-2 placement invariant
    return AlienSpecies(
        id=sid, roster_id=sp.id, name=sp.name, archetype_id=sp.archetype_id,
        sector_id=sector_id, home_band=band, tech_level=sp.tech_level,
        base_disposition=base, disposition_center=sp.disposition_center,
        disposition_variance=sp.disposition_variance,
        alliance_id=sp.alliance_id, alliance_role=sp.alliance_role,
        threat_tier=sp.threat_tier, trade_posture=sp.trade_posture,
        treaty_mode=sp.treaty_mode, persona=sp.persona,
    )


def _populate_governing_space(state: UniverseState, config: GameConfig, roster: RosterConfig,
                              rng: random.Random, placed: dict[int, AlienSpecies],
                              bases: dict[str, float]) -> None:
    """Settle the Core governor's own people across Core Space and fill it with traffic (§6.3).

    Settles `core_population` distinct governing-alliance members (`alliance_role`
    leader/member — leader always included) across distinct Core sectors so the player's
    home region is inhabited by their own people, then scatters `core_traffic` additional
    governing-member ships (kinds may repeat) so the Core *bustles*. This is the **only**
    generation path that places a species in the Core; every other species is barred (the
    band placement skips the Core). Runs on the same species sub-RNG, so it does not perturb
    the topology/port/planet/discovery draw order (golden-master, §5).
    """
    gov = state.game.core_governing_alliance_id
    if gov is None:
        return
    members = [s for s in roster.species
               if s.alliance_id == gov and s.alliance_role in ("leader", "member")]
    if not members:
        return
    core_sectors = [sid for sid in sorted(state.sectors) if state.sectors[sid].is_galactic_core]
    if not core_sectors:
        return
    members.sort(key=lambda s: (s.alliance_role != "leader", s.id))  # leader first, then stable
    want = min(roster.core_population, len(members), len(core_sectors))
    chosen = members[:want]
    sectors = rng.sample(core_sectors, k=want)
    next_id = max(placed, default=0) + 1
    for sp, sector_id in zip(chosen, sectors):
        band = state.sectors[sector_id].distance_band
        placed[next_id] = _make_species(next_id, sp, sector_id, band, _base_for(bases, sp, config, rng), config)
        next_id += 1

    # Core traffic: extra governing-member ships scattered across the Core (kinds repeat),
    # all sharing their kind's reputation, so the home region feels alive (§6.3).
    for _ in range(roster.core_traffic):
        sp = rng.choice(members)
        sector_id = rng.choice(core_sectors)
        band = state.sectors[sector_id].distance_band
        placed[next_id] = _make_species(next_id, sp, sector_id, band, _base_for(bases, sp, config, rng), config)
        next_id += 1


def _place_stardock_contacts(state: UniverseState, config: GameConfig, roster: RosterConfig,
                             rng: random.Random, placed: dict[int, AlienSpecies],
                             bases: dict[str, float]) -> None:
    """Stage ≥`stardock_contacts` Core-welcome species at the StarDock (high-traffic hub, §6.3).

    The Core is otherwise free of placed contacts, but every game funnels through the
    StarDock — so a brand-new player should meet friendly aliens there. "Core-welcome"
    means the governing alliance's own members plus unaligned neutrals (never a rival
    bloc). Prefer species not already met in a band so the hub adds variety, falling back
    to reuse only if the welcome pool is too small to field the requested count.
    """
    want = roster.stardock_contacts
    dock = next((p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)
    if want <= 0 or dock is None:
        return
    gov = state.game.core_governing_alliance_id
    welcome = [s for s in sorted(roster.species, key=lambda s: s.id)
               if s.alliance_id in (gov, None)]
    already = {s.roster_id for s in placed.values()}
    fresh = [s for s in welcome if s.id not in already]
    pick_from = fresh if len(fresh) >= want else welcome
    rng.shuffle(pick_from)
    band = state.sectors[dock.sector_id].distance_band
    next_id = max(placed, default=0) + 1
    for sp in pick_from[:want]:
        placed[next_id] = _make_species(next_id, sp, dock.sector_id, band,
                                        _base_for(bases, sp, config, rng), config)
        next_id += 1
