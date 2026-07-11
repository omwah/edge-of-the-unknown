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
from edge.core.enums import DiscoveryKind, PayloadKind, RarityTier
from edge.core.models import AlienSpecies, Discovery, DiscoveryPayload, UniverseState


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


def entity_species(state: UniverseState, config: GameConfig) -> AlienSpecies | None:
    """The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None.

    Identified by the roster's `singular_entity` flag (never by name), so a roster is
    free to name its own arbiter. There is at most one such instance (the big bang
    guarantees exactly one when the roster flags a species).
    """
    if config.roster is None:
        return None
    entity_ids = {s.id for s in config.roster.species if s.singular_entity}
    if not entity_ids:
        return None
    return next((sp for sp in state.species.values() if sp.roster_id in entity_ids), None)


def entity_codex_discovery(state: UniverseState) -> Discovery | None:
    """The reserved hidden `ENTITY`-kind codex row (§7, WP35), or None.

    Created at generation as a Legendary marker; it is *not* a spatial salvage object —
    it is collected by the first `Hail` of the Entity, and is the sensor-gate reference
    for `entity_contactable`. Exactly one exists once an Entity is placed.
    """
    return next((d for d in state.discoveries.values() if d.kind is DiscoveryKind.ENTITY), None)


def entity_contactable(state: UniverseState, sensor_rating: int, sector_id: int,
                       config: GameConfig) -> bool:
    """Whether the Entity's presence resolves into openable contact at this sensor rating.

    The always-on presence hint is shown to everyone (§7, WP35), but opening contact is
    **sensor-gated at Legendary difficulty** — routed through the same `sensor_difficulty`
    machinery hidden finds use, keyed off the reserved codex row. Pure, so the projection
    and the `Hail` reducer agree (H2). No reserved row (or no discovery config) ⇒ ungated.
    """
    disc = entity_codex_discovery(state)
    if disc is None:
        return False
    return is_detectable(disc, sensor_rating,
                         in_nebula=sector_has_nebula(state, sector_id), config=config)


def rarity_value(tier: RarityTier, config: GameConfig) -> int:
    """The latinum-equivalent value of a rarity tier (the gradient the validator checks)."""
    if config.discovery is None:
        return tier.value
    return config.discovery.tier_value.get(tier.name, tier.value)


def describe_payload(payload: DiscoveryPayload) -> str:
    """A short human-readable phrase for what collecting a payload yields (§7).

    One line per payload kind, suitable for both the event log and a "You discovered X"
    notice. Lore reports the fragment itself (codex-only, no material gain).
    """
    if payload.kind is PayloadKind.COMPONENT and payload.component is not None and payload.tier is not None:
        return f"a Tier {payload.tier.name} {payload.component.value} component"
    if payload.kind is PayloadKind.LATINUM:
        return f"{payload.latinum:,} latinum"
    if payload.kind is PayloadKind.ARTIFACT and payload.barter_tier is not None:
        return f"an artifact (barter ≈ Tier {payload.barter_tier})"
    if payload.kind is PayloadKind.WRECK:
        parts = ", ".join(
            f"Tier {tier.name} {component.value}" for component, tier in payload.components)
        if payload.latinum and parts:
            return f"{payload.latinum:,} latinum and {parts}"
        if parts:
            return parts
        return f"{payload.latinum:,} latinum"
    return payload.lore or "a fragment of lore"
