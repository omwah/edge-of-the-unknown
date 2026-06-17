"""Discovery detection + valuation — pure core, no I/O, no RNG (DESIGN §7, WP5).

Detection is a **capability gate**, not a dice roll: a hidden find is revealed on
entry only when the ship's *effective* sensor rating — its `sensor_rating` minus a
nebula's interference when one shrouds the sector — meets the rarity tier's
configured difficulty. Obvious finds (phenomena) need no check. Keeping this
deterministic means it never touches `state.rng`, so the golden-master replay
order is unchanged, while sensors stay a real progression axis (raise them to
reach deeper-tier hidden finds; nebulae hide things). The big bang owns placement;
this module owns "can the player see / value it".
"""

from __future__ import annotations

from edge.core.config import GameConfig
from edge.core.enums import DiscoveryKind, RarityTier
from edge.core.models import Discovery, UniverseState


def sector_has_nebula(state: UniverseState, sector_id: int) -> bool:
    """Whether an (uncollected-or-not) nebula shrouds `sector_id` — it dims sensors."""
    return any(
        d.kind is DiscoveryKind.NEBULA and d.planet_id is None and d.sector_id == sector_id
        for d in state.discoveries.values()
    )


def effective_sensor(sensor_rating: int, *, in_nebula: bool, config: GameConfig) -> int:
    """The ship's sensor rating after nebula interference (never negative)."""
    penalty = config.discovery.nebula_interference if (in_nebula and config.discovery) else 0
    return max(0, sensor_rating - penalty)


def is_detectable(discovery: Discovery, sensor_rating: int, *, in_nebula: bool,
                  config: GameConfig) -> bool:
    """Whether `discovery` is visible to a ship with this sensor rating on entry (§7).

    Obvious finds are always visible; a hidden find needs effective sensor ≥ the
    tier's difficulty. With no discovery config, nothing is gated (all visible).
    """
    if not discovery.hidden:
        return True
    if config.discovery is None:
        return True
    difficulty = config.discovery.sensor_difficulty.get(discovery.rarity_tier.name, 0)
    return effective_sensor(sensor_rating, in_nebula=in_nebula, config=config) >= difficulty


def rarity_value(tier: RarityTier, config: GameConfig) -> int:
    """The latinum-equivalent value of a rarity tier (the gradient the validator checks)."""
    if config.discovery is None:
        return tier.value
    return config.discovery.tier_value.get(tier.name, tier.value)
