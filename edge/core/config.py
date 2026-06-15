"""Typed game-configuration schema (DESIGN §4 Config, §15).

Pure Pydantic v2 models for the tunable constants that drive the economy (§8),
universe generation (§5), and the player's starter ship (§4). These are *data
definitions only* — no file I/O lives here (that would violate core purity); the
YAML file is read by `edge.config`, which validates the parsed mapping through
`GameConfig.from_mapping`.

Every game constant lives in config, not code (CLAUDE.md), so balance is tunable
and testable without touching the rules engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from edge.core.enums import Commodity

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class CommodityPricing(BaseModel):
    """Per-commodity pricing inputs for the §8 stock-ratio formula."""

    model_config = _FROZEN

    base: float  # undisturbed per-unit price in latinum
    delta: float  # how far price swings with stock
    elasticity: float = 1.0  # multiplies the swing (per-commodity tunable)


class HagglingConfig(BaseModel):
    """The haggling mini-game's tunables (DESIGN §8)."""

    model_config = _FROZEN

    insult_frac: float = 0.30  # counter better-for-player than fair by > this aborts
    max_rejections: int = 2  # rejections that end negotiation at the port's price
    history_penalty: float = 0.08  # acceptance drop per recent attempt at this port


class EconomyConfig(BaseModel):
    """Economy constants (DESIGN §8). All latinum figures in slips."""

    model_config = _FROZEN

    starting_latinum: int = 2_000
    starting_bank: int = 0

    # Pricing clamp: price stays within [floor_frac*base, ceiling_frac*base] and
    # always > 0 — a core invariant with its own property test (§8/§13).
    floor_frac: float = 0.25
    ceiling_frac: float = 2.0
    fuel_ore: CommodityPricing = CommodityPricing(base=11, delta=5)
    organics: CommodityPricing = CommodityPricing(base=5, delta=2)
    equipment: CommodityPricing = CommodityPricing(base=15, delta=7)

    # The upgrade sink + Phase-1 "first upgrade" (PHASE1_PLAN §2).
    tier_i_component_latinum: int = 2_000
    tier_ii_component_latinum: int = 8_000
    repair_kit_latinum: int = 200
    first_upgrade_latinum: int = 2_000
    first_upgrade_aspect: str = "holds"  # "holds" | "shields" (config-selectable)

    # Banking + stock regen (engine cron applies these; the math is pure).
    bank_interest_per_day: float = 0.005  # ~0.5%/game-day
    regen_fraction: float = 0.05  # stock moves 5% toward desired each econ tick
    desired_stock_frac_standard: float = 0.50
    desired_stock_frac_stardock: float = 0.90

    haggling: HagglingConfig = HagglingConfig()

    def pricing(self, commodity: Commodity) -> CommodityPricing:
        """The pricing inputs for one commodity."""
        return {
            Commodity.FUEL_ORE: self.fuel_ore,
            Commodity.ORGANICS: self.organics,
            Commodity.EQUIPMENT: self.equipment,
        }[commodity]


class DistanceBand(BaseModel):
    """One distance band (DESIGN §5 step 5): warp-hops from sector 1, inclusive."""

    model_config = _FROZEN

    name: str
    min_hops: int
    max_hops: int  # inclusive; the outermost band uses a large sentinel


class BigBangConfig(BaseModel):
    """Universe-generation parameters (DESIGN §5)."""

    model_config = _FROZEN

    sector_count: int = 1_000  # config range 100–5000
    cluster_min: int = 5
    cluster_max: int = 25
    intra_group_degree: float = 2.5
    bridges_min: int = 1
    bridges_max: int = 5
    one_way_chance: float = 0.15
    max_warps_per_sector: int = 6  # TW2002 canon
    core_sector_count: int = 10  # Core Space = sectors 1..N
    stardock_min_hops: int = 2
    stardock_max_hops: int = 5
    port_density: float = 0.45
    planet_density: float = 0.25
    # terminal-space class split (§5 / §A.2): eight buy/sell triples.
    port_class_distribution: list[int] = Field(
        default_factory=lambda: [20, 20, 20, 10, 10, 10, 5, 5]
    )
    initial_stock_min: int = 200
    initial_stock_max: int = 2_000
    bands: list[DistanceBand] = Field(
        default_factory=lambda: [
            DistanceBand(name="Hub", min_hops=0, max_hops=5),
            DistanceBand(name="Frontier", min_hops=6, max_hops=12),
            DistanceBand(name="Deep", min_hops=13, max_hops=20),
            DistanceBand(name="Void", min_hops=21, max_hops=9_999),
        ]
    )


class ShipClassConfig(BaseModel):
    """A ship class (DESIGN §4). Phase 1 uses flat aspect scalars (no subsystems)."""

    model_config = _FROZEN

    id: str
    name: str
    role: str
    holds_total: int
    turns_per_warp: int
    shields_max: int
    warp_speed: int
    combat_speed: int
    cloak_rating: int
    sensor_rating: int
    hull_max: int


class GameConfig(BaseModel):
    """Top-level config bundle, validated from the parsed YAML mapping."""

    model_config = _FROZEN

    config_version: int
    turns_per_day: int = 250  # TWINSTR.DOC default (§9)
    economy: EconomyConfig = EconomyConfig()
    bigbang: BigBangConfig = BigBangConfig()
    starter_ship: ShipClassConfig

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GameConfig:
        """Validate an already-parsed mapping (e.g. from YAML) into a GameConfig."""
        return cls.model_validate(data)
