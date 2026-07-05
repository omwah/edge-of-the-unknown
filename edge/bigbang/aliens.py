"""Populate alien species from the roster (DESIGN §5 step 6, §6; PHASE2_PLAN WP7).

The big bang draws a **seeded subset** of the roster's species pool (not every species
need appear, §6), draws each one's `base_disposition` from its bounded `center ±
variance` spread (so stance varies between universe generations), and assigns each a
**contact point** — a non-Core sector in a distance band — guaranteeing at least one
friendly contact per non-empty band (the §5 step-8 resupply invariant).

Placement is **band-graded** (§5/§6, Phase 3): the innermost band (Hub) stays peaceable
and each band keeps a guaranteed friendly resupply anchor, but every other outer-band
species takes a downward `band_disposition_bias`, so hostiles spawn in the frontier and
mean stance falls with distance. The roster's alliances become `state.alliances`,
generalising the Phase-1 Federation stub — no alliance is privileged in the schema
(CLAUDE.md); the default roster simply names the Federation as the Core's governor and
seeds the player into it.

Runs on its own sub-RNG (`Random(seed ^ _SPECIES_SALT)`) so species draws never shift
the topology / port / planet / discovery draw order (golden-master ordering, §5).
"""

from __future__ import annotations

import random
from dataclasses import replace

from edge.core.aliens import is_friendly
from edge.core.starbases import is_operational
from edge.core.config import GameConfig, RosterConfig, SpeciesConfig
from edge.core.enums import DiscoveryKind, PayloadKind, PortClass, RarityTier
from edge.core.models import (
    Alliance, AlienSpecies, Discovery, DiscoveryPayload, Grudge, Ownership, UniverseState,
)


class HomeClusterError(Exception):
    """A non-governing bloc could not be given a valid home cluster (§5 step 6)."""

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


def _band_disposition(center: float, variance: float, band: str, *, is_anchor: bool,
                      config: GameConfig, rng: random.Random) -> float:
    """Draw a base disposition, band-graded so danger rises outward (§5/§6, Phase 3).

    The draw is the species' per-generation stance (§6). The **innermost band (Hub) is
    kept peaceable** and each band's **guaranteed resupply anchor** stays friendly
    (clamped up to the amity threshold, §13). Every other placed species takes the
    band's downward `band_disposition_bias`, so the outer bands can spawn hostiles and
    mean stance falls with distance.
    """
    drawn = _clamp01(rng.uniform(center - variance, center + variance))
    innermost = config.bigbang.active_bands()[0].name
    if band == innermost or is_anchor:
        return max(config.aliens.amity_threshold, drawn)
    bias = config.aliens.band_disposition_bias.get(band, 0.0)
    return _clamp01(drawn + bias)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def populate_species(state: UniverseState, config: GameConfig) -> None:
    """Draw a friendly-band subset of the roster and place it across the bands (WP7)."""
    state.alliances = build_alliances(config)
    roster = config.roster
    if roster is None or not roster.species:
        return

    rng = random.Random(state.game.seed ^ _SPECIES_SALT)

    # Non-Core sectors grouped by band — the home lanes where aliens are met (the Core
    # itself stays free of placed contacts; its safety is the governing alliance's).
    band_order = [b.name for b in config.bigbang.active_bands()]
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
    # The singular Entity (§7) is placed separately (`_place_entity`) — always, outside the
    # seeded subset and the per-band accounting — so keep it out of the ordinary draw pool.
    pool = sorted((s for s in roster.species if s.alliance_id != gov and not s.singular_entity),
                  key=lambda s: s.id)
    rng.shuffle(pool)
    lo = max(roster.subset_min, len(live_bands))
    hi = max(roster.subset_max, lo)
    count = min(len(pool), rng.randint(lo, hi))
    chosen = pool[:count]
    # Sort chosen descending by disposition center so the friendliest species serve
    # as the resupply anchors (the first len(live_bands) slots), ensuring hostile-leaning
    # species honor their roster centers and take normal band bias without being forced friendly.
    chosen.sort(key=lambda s: s.disposition_center, reverse=True)


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
    # Each band's guaranteed resupply anchor (i < len(live_bands)) is drawn friendly.
    # Alliance members are **not** blanket-clamped here — their authored disposition_center
    # and the band bias apply normally, so a low-disposition bloc species placed in Deep
    # can be hostile by nature (§6). Alliance friendliness is localised: home clusters
    # (_settle_cluster), the Core (_populate_governing_space), and the StarDock
    # (_place_stardock_contacts) each pass is_anchor=True independently (§6.3).
    for i, (sp, band) in enumerate(zip(chosen, assignment)):
        home = rng.choice(sectors_by_band[band])
        friendly = i < len(live_bands)
        base = _base_for(bases, sp, band, friendly, config, rng)
        next_id = _place_cluster(placed, next_id, sp, home, band,
                                 base, state, config, rng, reserved=reserved)

    _place_entity(state, config, roster, rng, placed, bases, reserved)
    _populate_governing_space(state, config, roster, rng, placed, bases)
    _place_stardock_contacts(state, config, roster, rng, placed, bases)
    state.species = placed
    _assign_region_control(state, placed)
    # Carve each non-governing bloc in the cast its home cluster of alliance territory,
    # separated from the Core and from rival clusters by neutral lanes (§5 step 6, §6.3).
    state.home_clusters = _carve_home_clusters(state, config, roster, rng, placed, bases, reserved)
    _seed_grudges(state, roster)


def _seed_grudges(state: UniverseState, roster: RosterConfig) -> None:
    """Seed the roster's authored inter-species grudges for the cast pairs (§6.5, WP27).

    Only pairs where both kinds were actually drawn get a `Grudge` row (hashed state);
    the NPC-vs-NPC semantics (stances, spillover) land in WP39. Deterministic — no RNG,
    ids assigned in sorted roster order.
    """
    cast = {sp.roster_id for sp in state.species.values()}
    grudges: dict[int, Grudge] = {}
    next_id = 1
    for sp in sorted(roster.species, key=lambda s: s.id):
        if sp.id not in cast:
            continue
        for seed in sp.grudges:
            if seed.target not in cast:
                continue
            grudges[next_id] = Grudge(
                holder=sp.id, target=seed.target, cause=seed.cause,
                severity=seed.severity, created_day=1, duration_days=seed.duration_days,
            )
            next_id += 1
    state.grudges = grudges


def _carve_home_clusters(state: UniverseState, config: GameConfig, roster: RosterConfig,
                         rng: random.Random, placed: dict[int, AlienSpecies],
                         bases: dict[str, float], reserved: frozenset[int]) -> dict[int, tuple[int, ...]]:
    """Give each non-governing bloc in the cast one home cluster (§5 step 6, §6.3).

    A cluster is `home_cluster_[min,max]` connected sectors in the two innermost bands
    (Hub + inner-Frontier), never adjacent to the Core and never warp-linked to another
    bloc's cluster (a one-hop buffer keeps them apart). Its planets are set alliance-owned,
    its region(s) stamped `controlling_alliance_id`, and its friendly members settled
    there. Everything else stays neutral lanes. Raises `HomeClusterError` (→ generation
    retries) if a bloc cannot be seated.
    """
    gov = state.game.core_governing_alliance_id
    blocs = sorted({sp.alliance_id for sp in placed.values()
                    if sp.alliance_id is not None and sp.alliance_id != gov})
    if not blocs:
        return {}

    bands = [b.name for b in config.bigbang.active_bands()]
    core_ids = {s.id for s in state.sectors.values() if s.is_galactic_core}

    members_by_bloc: dict[int, list[SpeciesConfig]] = {}
    for sp in sorted(roster.species, key=lambda s: s.id):
        if sp.alliance_id in blocs:
            members_by_bloc.setdefault(sp.alliance_id, []).append(sp)

    lo, hi = config.bigbang.home_cluster_min, config.bigbang.home_cluster_max

    # Try Frontier first (bands[1]) to keep the Hub strictly friendly and allow
    # non-governing bloc species to be hostile; fall back to Hub + Frontier (bands[:2]) if needed.
    for pass_bands in ({bands[1]}, set(bands[:2])):
        candidates = {
            sid for sid, s in state.sectors.items()
            if s.distance_band in pass_bands and sid not in core_ids and sid not in reserved
            and not any(n in core_ids for n in state.adjacency.get(sid, ()))  # never Core-adjacent
        }
        used: set[int] = set()      # sectors already in a cluster
        blocked: set[int] = set()   # sectors adjacent to a cluster (the rival-unlink buffer)
        clusters: dict[int, tuple[int, ...]] = {}
        success = True
        for bloc in blocs:
            avail = candidates - used - blocked
            cluster = _grow_cluster(state, avail, rng.randint(lo, hi), lo, rng)
            if cluster is None:
                success = False
                break
            clusters[bloc] = tuple(sorted(cluster))
            used |= cluster
            for sid in cluster:
                blocked |= set(state.adjacency.get(sid, ()))
        if success:
            # Settle the clusters now that we know we succeeded.
            for bloc in blocs:
                _settle_cluster(state, config, rng, placed, bases, bloc, set(clusters[bloc]),
                                members_by_bloc.get(bloc, ()))
            return clusters

    raise HomeClusterError("no home cluster available for non-governing alliances")


def _grow_cluster(state: UniverseState, avail: set[int], target: int, minimum: int,
                  rng: random.Random) -> set[int] | None:
    """BFS-grow a connected blob of up to `target` sectors within `avail`; None if < min."""
    seeds = sorted(avail)
    rng.shuffle(seeds)
    for seed in seeds:
        cluster = {seed}
        frontier = [seed]
        while frontier and len(cluster) < target:
            cur = frontier.pop(0)
            nbrs = [n for n in sorted(state.adjacency.get(cur, ())) if n in avail and n not in cluster]
            rng.shuffle(nbrs)
            for n in nbrs:
                if len(cluster) >= target:
                    break
                cluster.add(n)
                frontier.append(n)
        if len(cluster) >= minimum:
            return cluster
    return None


def _settle_cluster(state: UniverseState, config: GameConfig, rng: random.Random,
                    placed: dict[int, AlienSpecies], bases: dict[str, float], bloc: int,
                    cluster: set[int], members: "list[SpeciesConfig] | tuple[SpeciesConfig, ...]") -> None:
    """Alliance-own the cluster's planets, stamp its regions, settle its friendly members."""
    for pid, planet in state.planets.items():
        if planet.sector_id not in cluster:
            continue
        # A derelict base must stay on an *unowned* world (§4.2 / the starbase validator),
        # so a cluster leaves a derelict-hosting planet unowned (a salvage cache in bloc space).
        base = state.starbases.get(planet.starbase_id) if planet.starbase_id is not None else None
        if base is not None and not is_operational(base):
            continue
        state.planets[pid] = replace(planet, owner=Ownership(kind="alliance", ref=bloc))
    for sid in cluster:
        rid = state.sectors[sid].region_id
        region = state.regions.get(rid)
        if region is not None:
            state.regions[rid] = replace(region, controlling_alliance_id=bloc)
    slots = sorted(cluster)
    rng.shuffle(slots)
    next_id = max(placed, default=0) + 1
    for i, sp in enumerate(members):
        sector_id = slots[i % len(slots)]
        band = state.sectors[sector_id].distance_band
        # If this species was already drawn in the main band-assignment loop, the memo is
        # reused (is_anchor has no effect on a second call); a species drawn hostile in an
        # outer band stays hostile here — the validator exempts home-cluster Hub sectors
        # from the peaceable check (alliance-political protection, §6.3).
        base_disp = _base_for(bases, sp, band, True, config, rng)
        placed[next_id] = _make_species(next_id, sp, sector_id, band, base_disp, config)
        next_id += 1


def _base_for(bases: dict[str, float], sp: SpeciesConfig, band: str, is_anchor: bool,
              config: GameConfig, rng: random.Random) -> float:
    """The species kind's base disposition, drawn once per generation and memoised.

    Drawn against the band of its *first* placement (reputation is per kind — every ship
    of a kind shares one stance, §6), so a kind's danger is fixed by where it is anchored.
    """
    if sp.id not in bases:
        bases[sp.id] = _band_disposition(sp.disposition_center, sp.disposition_variance,
                                         band, is_anchor=is_anchor, config=config, rng=rng)
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
    # A non-friendly cluster must not spill into the peaceable Hub: its satellites can
    # dip one band inward, so keep hostiles out of the innermost band (§5, validator).
    if not is_friendly(base, config.aliens):
        innermost = config.bigbang.active_bands()[0].name
        candidates = [s for s in candidates if state.sectors[s].distance_band != innermost]
    rng.shuffle(candidates)
    for sat in candidates[:satellites]:
        sat_band = state.sectors[sat].distance_band
        placed[next_id] = _make_species(next_id, sp, sat, sat_band, base, config)
        next_id += 1
    return next_id


def _place_entity(state: UniverseState, config: GameConfig, roster: RosterConfig,
                  rng: random.Random, placed: dict[int, AlienSpecies],
                  bases: dict[str, float], reserved: frozenset[int]) -> None:
    """Place the singular roaming Entity (DESIGN §7, WP34) — exactly one, deep-band, no satellites.

    The roster's `singular_entity` species (the Concordance) is **always** drawn — never subject
    to the seeded subset or the per-band resupply accounting — and fielded as **one** instance in
    a deep band (its `home_band` hint, else the deepest live band with sectors), never in the Core
    or on the reserved StarDock sector, and with no cluster satellites. It is drawn peaceable (an
    impartial arbiter that greets whoever finds it); it fields no ships and never fights
    (`combatant: false` + empty `fleet`, honoured at contact/encounter time, WP24), so the
    encounter is always the conversation. A roster with no flagged species places nothing.
    """
    entity = next((s for s in roster.species if s.singular_entity), None)
    if entity is None:
        return
    band_order = [b.name for b in config.bigbang.active_bands()]
    core_ids = {s.id for s in state.sectors.values() if s.is_galactic_core}

    def sectors_in(band: str) -> list[int]:
        return sorted(sid for sid, s in state.sectors.items()
                      if s.distance_band == band and sid not in core_ids and sid not in reserved)

    # Prefer the roster's `home_band` spawn hint (Void), then the deepest live band inward.
    prefer = [entity.home_band] if entity.home_band else []
    for band in [*prefer, *reversed(band_order)]:
        candidates = sectors_in(band)
        if not candidates:
            continue
        home = rng.choice(candidates)
        base = _base_for(bases, entity, band, True, config, rng)  # peaceable (anchor draw)
        next_id = max(placed, default=0) + 1
        placed[next_id] = _make_species(next_id, entity, home, band, base, config)
        _reserve_entity_codex(state, home)
        return


def _reserve_entity_codex(state: UniverseState, home_sector: int) -> None:
    """Create the reserved hidden Legendary codex row for the Entity (DESIGN §7, WP35).

    Not a spatial salvage object — it is stamped into the codex by the **first `Hail`** of
    the Entity (`rules._hail`), never salvaged, and is the Legendary sensor-gate reference
    for opening contact (`discovery.entity_contactable`). It is excluded from the spatial
    discovery gradient and the sector-view listing (it just marks the find in the codex).
    Appended at `max+1` so existing discovery ids never renumber; drawn from no RNG, so the
    generation draw order is untouched. `home_sector` is a placeholder anchor (the Entity
    roams from WP36); the row's location is never read.
    """
    next_id = max(state.discoveries, default=0) + 1
    state.discoveries[next_id] = Discovery(
        id=next_id, kind=DiscoveryKind.ENTITY, rarity_tier=RarityTier.LEGENDARY,
        sector_id=home_sector, hidden=True,
        payload=DiscoveryPayload(kind=PayloadKind.LORE,
                                 lore="first contact with the singular roaming Entity"),
    )


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
    """Build one placed ship of a species at `sector_id` with its kind's shared `base`.

    `base` may be hostile now (Phase 3 lifts the Phase-2 friendly-only clamp); band-graded
    placement and the validator (`_check_species`) keep the Hub peaceable.
    """
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
    # Governing members inhabit the Core (Hub band) → always drawn friendly (§6.3).
    for sp, sector_id in zip(chosen, sectors):
        band = state.sectors[sector_id].distance_band
        base = _base_for(bases, sp, band, True, config, rng)
        placed[next_id] = _make_species(next_id, sp, sector_id, band, base, config)
        next_id += 1

    # Core traffic: extra governing-member ships scattered across the Core (kinds repeat),
    # all sharing their kind's reputation, so the home region feels alive (§6.3).
    for _ in range(roster.core_traffic):
        sp = rng.choice(members)
        sector_id = rng.choice(core_sectors)
        band = state.sectors[sector_id].distance_band
        base = _base_for(bases, sp, band, True, config, rng)
        placed[next_id] = _make_species(next_id, sp, sector_id, band, base, config)
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
    # Core-welcome must stay friendly: a kind already anchored hostile in a deep band
    # (its base is memoised) can never greet a new player at the dock, so exclude it.
    hostile_kinds = {sp.roster_id for sp in placed.values()
                     if not is_friendly(sp.base_disposition, config.aliens)}
    welcome = [s for s in sorted(roster.species, key=lambda s: s.id)
               if s.alliance_id in (gov, None) and s.id not in hostile_kinds
               and not s.singular_entity]  # the roaming Entity never idles at the dock (§7)
    already = {s.roster_id for s in placed.values()}
    fresh = [s for s in welcome if s.id not in already]
    pick_from = fresh if len(fresh) >= want else welcome
    rng.shuffle(pick_from)
    band = state.sectors[dock.sector_id].distance_band
    next_id = max(placed, default=0) + 1
    for sp in pick_from[:want]:
        base = _base_for(bases, sp, band, True, config, rng)
        placed[next_id] = _make_species(next_id, sp, dock.sector_id, band, base, config)
        next_id += 1
