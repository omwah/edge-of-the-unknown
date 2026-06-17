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

from edge.core.enums import Commodity, ComponentTier

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

    # The component sink: StarDock hardware prices by tier (§8). Tier III is not
    # latinum-buyable — it comes only from alien barter (WP9) or salvage (WP4).
    tier_i_component_latinum: int = 2_000
    tier_ii_component_latinum: int = 8_000
    repair_kit_latinum: int = 200
    # Fraction of a hull's purchase price credited as trade-in toward a new one,
    # and StarDock battle-damage repair priced at this fraction of a tier price
    # (the repair path is inert until Phase-3 combat knocks components out, §8).
    ship_trade_in_frac: float = 0.5
    repair_cost_frac: float = 0.25
    # Per-head latinum incentive paid to enlist a willing colonist at StarDock
    # (colonists are recruited, not bought — §4.2; not a tradeable commodity).
    colonist_incentive: int = 5

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

    def component_price(self, tier: ComponentTier) -> int | None:
        """The StarDock latinum price for a component tier, or None if barter-only.

        Tier III has no latinum price (it is bartered for, not bought, §8).
        """
        return {
            ComponentTier.I: self.tier_i_component_latinum,
            ComponentTier.II: self.tier_ii_component_latinum,
        }.get(tier)


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


class SubsystemLayout(BaseModel):
    """One subsystem's slot layout for a hull (DESIGN §4.1).

    `slot_count` fixed slots; `base_components` are the parts pre-installed at Tier I
    when the hull is built (index 0 is the keystone slot), the rest start empty;
    `legal_components` is what may be installed/swapped into any slot;
    `keystone` names the structural component (it sits at `base_components[0]`).
    Component names are the `Component` enum values.
    """

    model_config = _FROZEN

    slot_count: int
    legal_components: list[str]
    base_components: list[str]
    keystone: str


class AspectFormula(BaseModel):
    """Coefficients turning a subsystem's filled slots into a derived aspect (§4.1).

    `value = base + per_component·active + per_tier·tier_bonus`, where `active` is the
    number of filled non-knocked-out slots and `tier_bonus` sums `(tier − 1)` over them
    (so Tier-I parts add nothing beyond `per_component`). Caps emerge from slot count ×
    max tier — there is no separate cap number (§4.1).
    """

    model_config = _FROZEN

    base: float = 0.0
    per_component: float = 0.0
    per_tier: float = 0.0


class EngineRoomConfig(BaseModel):
    """Game-global engine-room tunables (DESIGN §4.1).

    The per-subsystem layouts live on each `ShipClassConfig`; these are the formulas
    shared across all hulls: how each subsystem's parts map to its aspect, the
    spindrive-efficiency → one global combat bonus, the warp-speed → turns-per-warp
    relation, and the main-gun rate-of-fire.
    """

    model_config = _FROZEN

    # Keyed by Subsystem value: spindrive→warp, thrusters→combat, screens→shields,
    # main_gun→gun damage. (sensors/cloak stay flat scalars — not subsystem-derived.)
    aspects: Mapping[str, AspectFormula]
    efficiency: AspectFormula  # applied to the spindrive's filled slots → global bonus
    warp_turn_divisor: float = 3.0  # turns_per_warp = max(1, round(divisor / warp_speed))
    gun_rate_base: int = 1
    gun_rate_step: int = 2  # +1 rate per this many parts in the main gun
    tier_ceiling: str = "III"  # highest installable tier (enum name)


class ShipClassConfig(BaseModel):
    """A ship class (DESIGN §4).

    A hull with an engine room carries a `subsystems` layout (the player hulls, §4.1);
    the flat aspect scalars (`shields_max`, `warp_speed`, `combat_speed`) then serve as
    the NPC fallback and as the caps/defaults, with the live values *derived* from the
    slotted layout. An NPC hull omits `subsystems` and uses the flat scalars directly.
    """

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
    colonist_capacity: int = 0  # life-support berths — recruited colonists (§4.2)
    price: int = 0  # StarDock purchase price in latinum (0 = the free starter hull)
    subsystems: Mapping[str, SubsystemLayout] | None = None


class HardwareConfig(BaseModel):
    """The StarDock hardware emporium catalog (DESIGN §5, §8).

    `components` are the part kinds offered for sale (Component enum values) and
    `tiers` the tiers stocked (enum names). Prices come from the economy block
    (`component_price`); Tier III is excluded here — it is barter-only (§8).
    """

    model_config = _FROZEN

    components: list[str]
    tiers: list[str]


class PlanetTypeProfile(BaseModel):
    """Per-`planet_type` production shaping (DESIGN §4.2 table).

    `yield_profile` multiplies per-commodity colonist output (keyed by Commodity
    value); `habitability` caps colonist population/growth (0 for uncolonizable
    types); `colonizable` gates the claim/colonize path (extraction types produce
    without colonists instead).
    """

    model_config = _FROZEN

    colonizable: bool
    habitability: int
    yield_profile: dict[str, float] = Field(default_factory=dict)


class OwnershipWeights(BaseModel):
    """Big-bang owner roll for a band: relative weight of alliance-owned vs unowned."""

    model_config = _FROZEN

    alliance: int
    none: int


class PlanetsConfig(BaseModel):
    """Planetary production constants + the per-type table (DESIGN §4.2, §8/§A.3)."""

    model_config = _FROZEN

    types: dict[str, PlanetTypeProfile]
    # BNT colonist model (§A.3 / §559), per production tick.
    production_rate: float = 0.005
    food_per_colonist: float = 0.05
    growth_rate: float = 0.02
    starvation_rate: float = 0.05
    jovian_scoop: int = 50  # fuel-ore per tick from a gas giant (no colonists)
    asteroid_mining: int = 50  # equipment per tick from a belt (no colonists)
    # Band-weighted ownership at generation (unowned fraction non-decreasing, §4.2).
    ownership: dict[str, OwnershipWeights] = Field(default_factory=dict)


class GameConfig(BaseModel):
    """Top-level config bundle, validated from the parsed YAML mapping."""

    model_config = _FROZEN

    config_version: int
    turns_per_day: int = 250  # TWINSTR.DOC default (§9)
    economy: EconomyConfig = EconomyConfig()
    bigbang: BigBangConfig = BigBangConfig()
    engine_room: EngineRoomConfig
    planets: PlanetsConfig
    starter_ship: ShipClassConfig
    ship_classes: list[ShipClassConfig] = Field(default_factory=list)  # buyable hulls (StarDock)
    hardware: HardwareConfig

    def ship_class(self, class_id: str) -> ShipClassConfig:
        """The ship-class config for `class_id` — the starter hull or a buyable one."""
        if class_id == self.starter_ship.id:
            return self.starter_ship
        for klass in self.ship_classes:
            if klass.id == class_id:
                return klass
        raise KeyError(f"unknown ship class {class_id!r}")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GameConfig:
        """Validate an already-parsed mapping (e.g. from YAML) into a GameConfig."""
        return cls.model_validate(data)
