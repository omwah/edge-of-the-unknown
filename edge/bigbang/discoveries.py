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

from edge.core.config import DiscoveryConfig, GameConfig
from edge.core.enums import Component, ComponentTier, DiscoveryKind, PayloadKind, RarityTier
from edge.core.models import Discovery, DiscoveryPayload, UniverseState

_PHENOMENA = (DiscoveryKind.NEBULA, DiscoveryKind.BLACK_HOLE)


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

    for sid in sorted(state.sectors):  # open-space finds, deterministic sector order
        if rng.random() >= dcfg.sector_density:
            continue
        tier = _roll_tier(dcfg, state.sectors[sid].distance_band, rng)
        if tier is None:
            continue
        kind = _roll_kind(dcfg.space_kinds, rng)
        discoveries[did] = Discovery(
            id=did, kind=kind, rarity_tier=tier, sector_id=sid,
            payload=_make_payload(kind, tier, dcfg, rng),
            hidden=kind.value in dcfg.hidden_kinds,
        )
        did += 1

    for pid in sorted(state.planets):  # surface sites (descent reveals them in WP6)
        planet = state.planets[pid]
        if rng.random() >= dcfg.surface_site_chance:
            continue
        tier = _roll_tier(dcfg, state.sectors[planet.sector_id].distance_band, rng)
        if tier is None:
            continue
        kind = _roll_kind(dcfg.surface_kinds, rng)
        discoveries[did] = Discovery(
            id=did, kind=kind, rarity_tier=tier, sector_id=planet.sector_id,
            payload=_make_payload(kind, tier, dcfg, rng), planet_id=pid, site_slot=0,
        )
        did += 1

    state.discoveries = discoveries
