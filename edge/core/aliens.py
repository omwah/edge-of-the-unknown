"""Alien disposition logic (DESIGN §6) — pure core, no I/O.

Disposition is a continuous 0.0 (most hostile) → 1.0 (most friendly) scale, not a
binary flag (CLAUDE.md). A species' authored `base_disposition` is the *base* stance;
the player's per-species **attitude offset** (raised by trade/favours, lowered by
aggression in Phase 3) shifts it into the **effective disposition** that drives
greeting-vs-violence, prices/barter, and tech unlocks. Config thresholds name the
bands (default hostility 0.35 / amity 0.65, §6).
"""

from __future__ import annotations

from edge.core.config import AliensConfig
from edge.core.models import AlienSpecies, Player

HOSTILE = "hostile"
NEUTRAL = "neutral"
FRIENDLY = "friendly"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def attitude_offset(species: AlienSpecies, player: Player) -> float:
    """The player's accumulated attitude offset toward `species` (0.0 if none yet)."""
    return player.species_attitudes.get(species.id, 0.0)


def effective_disposition(species: AlienSpecies, player: Player) -> float:
    """Base disposition shifted by the player's attitude offset, clamped to [0, 1] (§6)."""
    return _clamp01(species.base_disposition + attitude_offset(species, player))


def disposition_band(value: float, config: AliensConfig) -> str:
    """Name the band a disposition value falls in (hostile / neutral / friendly, §6)."""
    if value < config.hostility_threshold:
        return HOSTILE
    if value >= config.amity_threshold:
        return FRIENDLY
    return NEUTRAL


def is_friendly(value: float, config: AliensConfig) -> bool:
    """Whether a disposition value sits in the friendly (amity) band."""
    return value >= config.amity_threshold
