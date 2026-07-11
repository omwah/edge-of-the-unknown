"""Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).

Rolls an open-space find into a fraction of sectors and a surface site onto a
fraction of planets, picking a kind by weight and a rarity tier from the sector's
**distance band** — so rarity (and the value it maps to) rises with distance, the
gradient `validate.py` asserts is monotone. Payloads scale with rarity: latinum and
Tier-I components near home, artifact barter-goods and Tier-III parts in the deep.

Runs on a **dedicated, attempt-aware sub-RNG** (`Random(f"{seed}-disc-{attempt}")`)
independent of the topology/economy build RNG, per the §5 RNG discipline: discovery
draws never shift the port/planet/ownership draw order (golden-master safety), and
folding the attempt in lets the generator's bounded-retry loop escape the rare
seed whose realized rarity gradient just misses monotonicity.
"""

from __future__ import annotations

import random

from edge.core.aliens import HOSTILE, disposition_band
from edge.core.config import DiscoveryConfig, GameConfig
from edge.core.enums import Component, ComponentTier, DiscoveryKind, PayloadKind, RarityTier
from edge.core.models import Discovery, DiscoveryPayload, UniverseState
from edge.core.movement import one_way_exits
from edge.core.planets import is_landable

_PHENOMENA = (DiscoveryKind.NEBULA, DiscoveryKind.BLACK_HOLE, DiscoveryKind.WORMHOLE)


def _roll_tier(dcfg: DiscoveryConfig, band: str, rng: random.Random) -> RarityTier | None:
    weights = dcfg.band_rarity_weights.get(band)
    if not weights:
        return None
    names = list(weights)
    chosen = rng.choices(names, weights=[weights[n] for n in names], k=1)[0]
    return RarityTier[chosen]


def _roll_kind(weights: dict[str, int], rng: random.Random) -> DiscoveryKind:
    names = list(weights)
    return DiscoveryKind(rng.choices(names, weights=[weights[n] for n in names], k=1)[0])


def _make_payload(kind: DiscoveryKind, tier: RarityTier, dcfg: DiscoveryConfig,
                  rng: random.Random) -> DiscoveryPayload:
    """A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component
    → artifact → Tier-III component as rarity climbs."""
    if kind in _PHENOMENA:
        return DiscoveryPayload(kind=PayloadKind.LORE,
                                lore=f"survey log: a {tier.name.lower()} {kind.value.replace('_', ' ')}")
    if tier is RarityTier.COMMON:
        return DiscoveryPayload(kind=PayloadKind.LATINUM, latinum=dcfg.tier_value.get(tier.name, 0))
    if tier is RarityTier.UNCOMMON and dcfg.component_pool:
        return DiscoveryPayload(kind=PayloadKind.COMPONENT,
                                component=Component(rng.choice(dcfg.component_pool)), tier=ComponentTier.I)
    if tier is RarityTier.LEGENDARY and dcfg.component_pool:
        return DiscoveryPayload(kind=PayloadKind.COMPONENT,
                                component=Component(rng.choice(dcfg.component_pool)), tier=ComponentTier.III)
    # Rare / Exceptional (and the fallbacks): an artifact barter-good (§8 equivalence).
    barter = dcfg.barter_equivalence.get(tier.name, ComponentTier.II.name)
    return DiscoveryPayload(kind=PayloadKind.ARTIFACT, barter_tier=barter)


def salt_discoveries(state: UniverseState, config: GameConfig, attempt: int) -> None:
    """Populate `state.discoveries` deterministically from the seed (§7)."""
    dcfg = config.discovery
    if dcfg is None:
        return
    rng = random.Random(f"{state.game.seed}-disc-{attempt}")
    discoveries: dict[int, Discovery] = {}
    did = 1

    planet_sectors = {p.sector_id for p in state.planets.values()}
    port_sectors = {p.sector_id for p in state.ports.values()}
    no_port_kinds = set(dcfg.port_incompatible_kinds)

    # Wormholes: one per one-way-source sector, anchoring the far side of the edge.
    # Force-placed (not rolled) and kept off planets by the populate planet exclusion.
    wormhole_sectors = {sid for sid in sorted(state.sectors)
                        if one_way_exits(state.adjacency, sid)}
    for sid in sorted(wormhole_sectors):
        tier = _roll_tier(dcfg, state.sectors[sid].distance_band, rng)
        if tier is None:
            continue
        discoveries[did] = Discovery(
            id=did, kind=DiscoveryKind.WORMHOLE, rarity_tier=tier, sector_id=sid,
            payload=_make_payload(DiscoveryKind.WORMHOLE, tier, dcfg, rng),
            hidden=DiscoveryKind.WORMHOLE.value in dcfg.hidden_kinds,
        )
        did += 1

    for sid in sorted(state.sectors):  # open-space finds, deterministic sector order
        if rng.random() >= dcfg.sector_density:
            continue
        # Space discoveries never share a sector with a planet; wormhole sectors are
        # already taken. A port may coexist unless the rolled kind is barred (§7 seam).
        if sid in planet_sectors or sid in wormhole_sectors:
            continue
        tier = _roll_tier(dcfg, state.sectors[sid].distance_band, rng)
        if tier is None:
            continue
        kind = _roll_kind(dcfg.space_kinds, rng)
        if sid in port_sectors and kind.value in no_port_kinds:
            continue
        discoveries[did] = Discovery(
            id=did, kind=kind, rarity_tier=tier, sector_id=sid,
            payload=_make_payload(kind, tier, dcfg, rng),
            hidden=kind.value in dcfg.hidden_kinds,
        )
        did += 1

    for pid in sorted(state.planets):  # surface sites (descent + Explore reveal them, WP6)
        planet = state.planets[pid]
        if not is_landable(planet.planet_type, config):
            continue  # spatial features (asteroid belts) have no surface to descend onto (§4.2)
        if rng.random() >= dcfg.surface_site_chance:
            continue
        band = state.sectors[planet.sector_id].distance_band
        n_sites = rng.randint(1, max(1, dcfg.surface_sites_max))
        for slot in range(n_sites):
            tier = _roll_tier(dcfg, band, rng)
            if tier is None:
                continue
            kind = _roll_kind(dcfg.surface_kinds, rng)
            # Rare+ surface sites are sensor-gated — descent reveals the slot, but a
            # sensor sweep (Explore with enough sensor rating) identifies them.
            hidden = tier.value >= dcfg.surface_hidden_min_rank
            discoveries[did] = Discovery(
                id=did, kind=kind, rarity_tier=tier, sector_id=planet.sector_id,
                payload=_make_payload(kind, tier, dcfg, rng), planet_id=pid, site_slot=slot,
                hidden=hidden,
            )
            did += 1

    # Floor: every terrestrial world is worth a descent, so guarantee it carries at least
    # one uncommon-or-better surface site. Drawing the guaranteed tier from the planet's
    # band (then flooring at UNCOMMON) keeps each band's mean rarity near its natural value,
    # protecting the strictly-rising gradient `validate.py` asserts — only the Hub, whose
    # rolls are COMMON/UNCOMMON, gets nudged up.
    for pid in sorted(state.planets):
        planet = state.planets[pid]
        if not planet.planet_type.startswith("terrestrial_"):
            continue
        sites = [d for d in discoveries.values() if d.planet_id == pid]
        if any(d.rarity_tier.value >= RarityTier.UNCOMMON.value for d in sites):
            continue
        band = state.sectors[planet.sector_id].distance_band
        rolled = _roll_tier(dcfg, band, rng)
        tier = rolled if rolled is not None and rolled.value > RarityTier.UNCOMMON.value else RarityTier.UNCOMMON
        kind = _roll_kind(dcfg.surface_kinds, rng)
        slot = max((d.site_slot for d in sites), default=-1) + 1
        discoveries[did] = Discovery(
            id=did, kind=kind, rarity_tier=tier, sector_id=planet.sector_id,
            payload=_make_payload(kind, tier, dcfg, rng), planet_id=pid, site_slot=slot,
            hidden=tier.value >= dcfg.surface_hidden_min_rank,
        )
        did += 1

    state.discoveries = discoveries


def salt_raid_caches(state: UniverseState, config: GameConfig) -> None:
    """Salt a legendary technology cache onto each hostile species' homeworld (§7, §10 — WP44).

    Runs **after** `populate_species` (it needs placed species) on its own sub-RNG, so it
    never shifts the §7 discovery draw order. A hostile-band species whose home (contact)
    sector holds a planet gets one **legendary** Tier-III component cache on that world — the
    reward for raiding the raiders — appended to `state.discoveries`. The cache is hidden
    (sensor-gated) and `raid_cache`-marked, so it is descended-to and codex-logged like any
    surface site but is excluded from the spatial rarity gradient (its placement follows
    hostile homeworlds, not the band curve). One per sector; never in the Core.
    """
    dcfg = config.discovery
    if dcfg is None or config.roster is None or not dcfg.component_pool:
        return
    rng = random.Random(f"{state.game.seed}-raidcache")
    next_id = (max(state.discoveries) + 1) if state.discoveries else 1
    planet_by_sector: dict[int, int] = {}
    for pid in sorted(state.planets):
        planet = state.planets[pid]
        if not is_landable(planet.planet_type, config):
            continue  # a raid cache is a surface site — a belt has no surface to hide it on (§4.2)
        planet_by_sector.setdefault(planet.sector_id, pid)
    seeded: set[int] = set()
    for sp in sorted(state.species.values(), key=lambda s: s.id):
        sector = sp.sector_id
        if (sector in seeded or state.sectors[sector].is_galactic_core
                or disposition_band(sp.base_disposition, config.aliens) != HOSTILE):
            continue
        home_pid = planet_by_sector.get(sector)
        if home_pid is None:
            continue  # a homeworld raid needs a homeworld to cache the tech on
        seeded.add(sector)
        slot = max((d.site_slot for d in state.discoveries.values() if d.planet_id == home_pid),
                   default=-1) + 1
        state.discoveries[next_id] = Discovery(
            id=next_id, kind=DiscoveryKind.ANCIENT_TECH, rarity_tier=RarityTier.LEGENDARY,
            sector_id=sector, planet_id=home_pid, site_slot=slot,
            payload=DiscoveryPayload(kind=PayloadKind.COMPONENT,
                                     component=Component(rng.choice(dcfg.component_pool)),
                                     tier=ComponentTier.III),
            hidden=True, raid_cache=True,
        )
        next_id += 1
