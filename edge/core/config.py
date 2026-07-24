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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from edge.core.enums import Commodity, ComponentTier

_FROZEN = ConfigDict(frozen=True, extra="forbid")

# The built-in signature-mechanic hooks (DESIGN §6.2). A species' `signature_mechanic`
# must name one of these; the roster validator checks it for reference integrity. The
# hooks themselves are implemented in Phase 3 — authored-but-inert in Phase 2 (WP7).
KNOWN_SIGNATURE_HOOKS = frozenset({
    "trojan_gift", "reprogram_unlock", "influence_gate", "morality_judge",
    "escalating_demand", "literalist", "contract_kill", "coordinate_broker",
    "passage_broker", "flee_drop",
})


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


class MarketConfig(BaseModel):
    """The Phase-5 order-book market's tunables (DESIGN §8, WP46).

    The book itself is pure math in `edge.core.market`; these knobs shape it.
    `enabled: False` falls back to the legacy 5% regen byte-identically (the
    WP47 wiring reads the switch; nothing consults it before then).
    """

    model_config = _FROZEN

    enabled: bool = True
    # Dead zone around desired stock: a port posts no order while its stock sits
    # within ±band of the pivot, so the book is silent at equilibrium (no churn).
    order_band: float = 0.10
    # Residual off-map regen fraction (vs the legacy 0.05): the external gradient
    # a closed book needs to keep trading at all (edge.core.market docstring).
    hinterland_frac: float = 0.01
    # Liquidity floor: the daily drip tops a port's purse toward size × this, so
    # player selling stays viable everywhere (§8 faucet; never overshoots).
    min_purse_per_size: int = 200
    # Fraction of the purse gap to the floor closed per daily drip. 0.25 refills
    # a drained purse in about a week of game days — slow enough that a working
    # arbitrageur can genuinely drain a small market first.
    drip_frac: float = 0.25
    # Settlement price policy — named so a future rule is a config value, not a
    # rewrite. "midpoint" (the integer midpoint of the crossed limits) is the
    # only policy implemented.
    settle_price: Literal["midpoint"] = "midpoint"


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

    # The component sink: Stardock hardware prices by tier (§8). Tier III is not
    # latinum-buyable — it comes only from alien barter (WP9) or salvage (WP4).
    tier_i_component_latinum: int = 2_000
    tier_ii_component_latinum: int = 8_000
    repair_kit_latinum: int = 200
    # Fraction of a hull's purchase price credited as trade-in toward a new one,
    # and Stardock battle-damage repair priced at this fraction of a tier price
    # (the repair path is inert until Phase-3 combat knocks components out, §8).
    ship_trade_in_frac: float = 0.5
    repair_cost_frac: float = 0.25
    # Per-head latinum incentive paid to enlist a willing colonist at Stardock
    # (colonists are recruited, not bought — §4.2; not a tradeable commodity).
    colonist_incentive: int = 5

    # Banking + stock regen (engine cron applies these; the math is pure).
    bank_interest_per_day: float = 0.005  # ~0.5%/game-day
    regen_fraction: float = 0.05  # stock moves 5% toward desired each econ tick
    desired_stock_frac_standard: float = 0.50
    desired_stock_frac_stardock: float = 0.90

    # The Phase-5 order-book market (§8, WP46) — pure math in edge.core.market.
    market: MarketConfig = MarketConfig()

    haggling: HagglingConfig = HagglingConfig()

    def pricing(self, commodity: Commodity) -> CommodityPricing:
        """The pricing inputs for one commodity."""
        return {
            Commodity.FUEL_ORE: self.fuel_ore,
            Commodity.ORGANICS: self.organics,
            Commodity.EQUIPMENT: self.equipment,
        }[commodity]

    def component_price(self, tier: ComponentTier) -> int | None:
        """The Stardock latinum price for a component tier, or None if barter-only.

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


def _trunk_bands() -> list[DistanceBand]:
    return [
        DistanceBand(name="Hub", min_hops=0, max_hops=5),
        DistanceBand(name="Frontier", min_hops=6, max_hops=12),
        DistanceBand(name="Deep", min_hops=13, max_hops=20),
        DistanceBand(name="Void", min_hops=21, max_hops=9_999),
    ]


def _expansive_bands() -> list[DistanceBand]:
    return [
        DistanceBand(name="Hub", min_hops=0, max_hops=14),
        DistanceBand(name="Frontier", min_hops=15, max_hops=35),
        DistanceBand(name="Deep", min_hops=36, max_hops=58),
        DistanceBand(name="Void", min_hops=59, max_hops=9_999),
    ]


def _planar_bands() -> list[DistanceBand]:
    return [
        DistanceBand(name="Hub", min_hops=0, max_hops=5),
        DistanceBand(name="Frontier", min_hops=6, max_hops=12),
        DistanceBand(name="Deep", min_hops=13, max_hops=20),
        DistanceBand(name="Void", min_hops=21, max_hops=9_999),
    ]


def _mesh_bands() -> list[DistanceBand]:
    return [
        DistanceBand(name="Hub", min_hops=0, max_hops=8),
        DistanceBand(name="Frontier", min_hops=9, max_hops=16),
        DistanceBand(name="Deep", min_hops=17, max_hops=24),
        DistanceBand(name="Void", min_hops=25, max_hops=9_999),
    ]


def _spiral_bands() -> list[DistanceBand]:
    return [
        DistanceBand(name="Hub", min_hops=0, max_hops=4),
        DistanceBand(name="Frontier", min_hops=5, max_hops=9),
        DistanceBand(name="Deep", min_hops=10, max_hops=14),
        DistanceBand(name="Void", min_hops=15, max_hops=9_999),
    ]


class TopologyModeConfig(BaseModel):
    """The parameters specific to one `topology_mode` (DESIGN §5).

    Everything a mode needs beyond the shared `BigBangConfig` knobs lives here:
    the mode's distance-band hop windows (`bands`) and, for the trunk spanning
    tree, its extra-bridge range (`bridges_min`/`bridges_max` — the other modes
    ignore these, deriving inter-cluster links from ring roads/spokes or the
    grid). `BigBangConfig.active_topology()` resolves the live block.
    """

    model_config = _FROZEN

    bands: list[DistanceBand]
    # Trunk-only: the [min, max] range of extra bridges each cluster gets beyond
    # its one spanning-tree link (DESIGN §5 step 2). Ignored by the other modes.
    bridges_min: int = 1
    bridges_max: int = 5


class TopologySet(BaseModel):
    """Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).

    Each mode lists the same band **names** in the same order — only the hop
    windows differ, so every name-keyed placement/validation/UI path is
    mode-agnostic. `expansive`'s ring-road lattice yields a deeper hop profile
    than the trunk spanning tree, so its windows are wider to keep all four
    bands populated. `BigBangConfig.active_topology()` resolves the live block.
    """

    model_config = _FROZEN

    trunk: TopologyModeConfig = Field(
        default_factory=lambda: TopologyModeConfig(bands=_trunk_bands())
    )
    expansive: TopologyModeConfig = Field(
        default_factory=lambda: TopologyModeConfig(bands=_expansive_bands())
    )
    planar: TopologyModeConfig = Field(
        default_factory=lambda: TopologyModeConfig(bands=_planar_bands())
    )
    mesh: TopologyModeConfig = Field(
        default_factory=lambda: TopologyModeConfig(bands=_mesh_bands())
    )
    spiral: TopologyModeConfig = Field(
        default_factory=lambda: TopologyModeConfig(bands=_spiral_bands())
    )

    @model_validator(mode="after")
    def _check_names_match(self) -> TopologySet:
        names = [b.name for b in self.trunk.bands]
        for mode_name in ("expansive", "planar", "mesh", "spiral"):
            got = [b.name for b in getattr(self, mode_name).bands]
            if got != names:
                raise ValueError(
                    f"topology.{mode_name}.bands names {got} must match "
                    f"topology.trunk.bands {names}"
                )
        return self


class BigBangConfig(BaseModel):
    """Universe-generation parameters (DESIGN §5)."""

    model_config = _FROZEN

    sector_count: int = 1_000  # config range 100–5000
    # How the groups interconnect (DESIGN §5 step 2). `trunk` = a group spanning
    # tree rooted at the Core plus a few extra bridges — a trunk-and-branches
    # universe of chokepoints (the original algorithm). `expansive` = a
    # band-lattice web: each group bridges to same-ring peers plus ≥2 inner
    # bridges, so every ring is a widening lattice with no single-bridge
    # chokepoint. The default stays `trunk`; the flip rides the WP22 config epoch.
    topology_mode: Literal["trunk", "expansive", "planar", "mesh", "spiral"] = "trunk"
    # --- shared across all topology modes ---
    cluster_min: int = 5
    cluster_max: int = 25
    intra_group_degree: float = 2.5  # avg warps per sector inside a cluster (all modes)
    inter_group_degree: float = 2.5  # avg inter-cluster warps per cluster (all modes)
    one_way_chance: float = Field(default=0.15, ge=0.0, le=1.0)
    # The nav rose has eight bearing slots; values above eight cannot be rendered.
    max_warps_per_sector: int = Field(default=6, ge=1, le=8)  # TW2002 default: 6
    core_sector_count: int = 10  # Core Space = sectors 1..N
    # Alliance home clusters (§5 step 6, §6.3): each non-governing bloc in the cast gets
    # one compact cluster of [min, max] connected sectors in the Hub/inner-Frontier —
    # always smaller than the Core, never Core-adjacent, never warp-linked to a rival's.
    home_cluster_min: int = 3
    home_cluster_max: int = 6
    # Where the player's ship starts: "stardock" (at the Stardock — no routing needed),
    # "random" (a seeded random sector), or a specific sector id. The shortest path from
    # the start to the Stardock opens pre-explored so the opening signpost stays actionable.
    start_sector: int | Literal["stardock", "random"] = "stardock"
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
    # --- topology-mode-specific ---
    # Per-mode config blocks, nested by `topology_mode` (§5 step 5): each holds that
    # mode's distance-band hop windows and (trunk only) its extra-bridge range. Same
    # band names/order across modes — only the hop windows differ — so all name-keyed
    # logic is mode-agnostic. Resolved by `active_topology()` / `active_bands()`.
    topology: TopologySet = Field(default_factory=TopologySet)

    def active_topology(self) -> TopologyModeConfig:
        """The config block for the selected `topology_mode` (§5 step 5)."""
        return getattr(self.topology, self.topology_mode)  # type: ignore[no-any-return]

    def active_bands(self) -> list[DistanceBand]:
        """The distance bands for the configured `topology_mode` (§5 step 5)."""
        return self.active_topology().bands


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


class WeaponConfig(BaseModel):
    """One weapon record (DESIGN §4): `{name, damage, firing_arc, rate, special}`.

    `firing_arc` shapes the §10 counter-play: an `ahead`/`spinal` attacker can be
    evaded by maneuvering out of its firing line (a combat-speed contest); `all_round`
    leaves no safe angle. `special` names a behaviour hook (engine_flux, homing, …) —
    carried as data now, mechanically read from Phase-3 WP33+ hooks.
    """

    model_config = _FROZEN

    name: str
    damage: int
    firing_arc: Literal["ahead", "all_round", "spinal"] = "all_round"
    rate: Literal["continuous", "periodic"] = "continuous"
    special: str | None = None


class DefenseConfig(BaseModel):
    """One defense record (DESIGN §4): `{type, value}`.

    `armour`/`screens`/`energy_plates` are flat damage-reducing layers (summed in
    combat); `laser_turret` and `speed_and_size` are carried as data for later hooks.
    """

    model_config = _FROZEN

    type: Literal["laser_turret", "armour", "screens", "energy_plates", "speed_and_size"]
    value: int = 0


class ShipClassConfig(BaseModel):
    """A ship class (DESIGN §4).

    A hull with an engine room carries a `subsystems` layout (the player hulls, §4.1);
    the flat aspect scalars (`shields_max`, `warp_speed`, `combat_speed`) then serve as
    the NPC fallback and as the caps/defaults, with the live values *derived* from the
    slotted layout. An NPC hull omits `subsystems` and uses the flat scalars directly.
    `armament` names weapons from the `GameConfig.weapons` catalog (§4); `defenses`
    are flat damage-reduction layers; `missiles` is the hull's starting homing-missile
    ammo (finite, arc-ignoring, §10).
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
    passenger_capacity: int = 0  # passenger berths — ground recruits + their suits (GW plan D3)
    price: int = 0  # Stardock purchase price in latinum (0 = the free starter hull)
    subsystems: Mapping[str, SubsystemLayout] | None = None
    armament: list[str] = Field(default_factory=list)  # weapon ids (GameConfig.weapons)
    defenses: list[DefenseConfig] = Field(default_factory=list)
    missiles: int = 0  # starting homing-missile ammo (§10)


class HardwareConfig(BaseModel):
    """The Stardock hardware emporium catalog (DESIGN §5, §8).

    `components` are the part kinds offered for sale (Component enum values) and
    `tiers` the tiers stocked (enum names). Prices come from the economy block
    (`component_price`); Tier III is excluded here — it is barter-only (§8).
    """

    model_config = _FROZEN

    components: list[str]
    tiers: list[str]


class DeviceConfig(BaseModel):
    """One buyable special device (§10, §14, WP56): probe / interdictor / mine-deflector.

    Bought at a Stardock into `Ship.devices` (not cargo). `probe_range` is a probe's max
    hop reach; `turn_tax` is the interdictor's per-day upkeep. Unused fields stay 0.
    """

    model_config = _FROZEN

    price: int = Field(ge=0)
    probe_range: int = Field(default=0, ge=0)   # max hops a launched probe flies
    turn_tax: int = Field(default=0, ge=0)      # per-day turn cost while a stance is active
    loss_chance: float = Field(default=0.0, ge=0.0, le=1.0)  # per-hop probe loss in a hostile sector


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
    # Whether a ship can descend onto a solid surface to explore sites (§4.2). Spatial
    # "world objects" with no surface — asteroid belts — set this false: they are scanned
    # and mined in orbit, never landed on, colonized, or given colony/citadel state.
    landable: bool = True


class OwnershipWeights(BaseModel):
    """Big-bang owner roll for a band: relative weight of alliance-owned vs unowned."""

    model_config = _FROZEN

    alliance: int
    none: int


class InhabitantsConfig(BaseModel):
    """Who already lives in the universe when it is generated (GW-WP09-PRE, §4.2).

    The big bang seeds **native polities**: an inhabited world carries a `population`
    entry keyed to its native species, and — sometimes — the citadel/treasury
    holdings that make it worth taking. Three populations, because their politics
    differ: the governor's **Core** worlds, a bloc's **home-cluster** worlds, and the
    **unaligned** worlds beyond them, which keep `owner=none` while holding a people
    (the D2 protectorate's subject, and the only worlds a fresh player may assault).

    `band_chance` is keyed by distance band, so the inhabited frontier thins with
    depth. Population is a fraction of the world's *capacity* (habitability, or a
    Cloud City's berths), never an absolute — a small world holds a small people.
    The `min_*` floors are generation **invariants**: a seed that cannot field them
    is regenerated, so the ground game always has targets to find (GW-WP09-PRE).
    """

    model_config = _FROZEN

    band_chance: dict[str, float] = Field(default_factory=dict)  # band → P(unaligned world peopled)
    home_cluster_chance: float = Field(default=0.7, ge=0.0, le=1.0)  # a bloc peoples its cluster
    core_chance: float = Field(default=0.85, ge=0.0, le=1.0)  # the governor peoples the Core
    population_min_frac: float = Field(default=0.05, gt=0.0, le=1.0)  # of colonist capacity
    population_max_frac: float = Field(default=0.55, gt=0.0, le=1.0)
    # Beyond the blocs a wary people is likelier — the friendly ones live under a flag.
    # Probability an unaligned world draws from the below-amity cast when one is available.
    unaligned_wary_bias: float = Field(default=0.7, ge=0.0, le=1.0)
    citadel_chance: float = Field(default=0.35, ge=0.0, le=1.0)  # an inhabited world has fortified
    citadel_max_level: int = Field(default=3, ge=0)
    treasury_per_1k: int = Field(default=40, ge=0)  # latinum banked per 1000 inhabitants
    stores_per_1k: int = Field(default=30, ge=0)  # goods held per 1000 inhabitants
    # Generation invariants: the minimum ground-target set a universe must field for a
    # *fresh* player (no attitude, no grudges, governing-alliance membership).
    min_assaultable: int = Field(default=6, ge=0)  # below-amity inhabited worlds outside the Core
    min_friendly_inhabited: int = Field(default=4, ge=0)  # worlds whose survey has settlements

    @model_validator(mode="after")
    def _check(self) -> InhabitantsConfig:
        if self.population_max_frac < self.population_min_frac:
            raise ValueError("planets.inhabitants population_max_frac must be ≥ population_min_frac")
        for band, chance in self.band_chance.items():
            if not 0.0 <= chance <= 1.0:
                raise ValueError(f"planets.inhabitants band_chance[{band}] must be in 0..1")
        return self


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
    mining_turn_cost: int = 1  # turns a player spends hand-mining a belt (§4.2, PT-30)
    # A belt is a **finite** body of ore (§4.2, PT-52): each is seeded with a reserve that
    # mining draws down and that **never regrows** — a worked-out belt stays worked out, so a
    # mining camp is a place you exhaust and leave, which is the exploration-first pressure.
    # Reserve = `belt_reserve_base` × the sector band's scale × a per-belt spread draw, so the
    # deep bands hold the richer fields (the same "reward rises with distance" gradient §7 uses).
    belt_reserve_base: int = 600           # mean reserve (Equipment units) of a Hub belt
    belt_reserve_spread: float = Field(default=0.35, ge=0.0, lt=1.0)  # ± fraction, per belt
    belt_reserve_band_scale: dict[str, float] = Field(default_factory=dict)  # band → multiplier
    # Cloud Cities (§4.2, PT-54): a gas giant has no ground, so it holds neither stores nor
    # people until a staging area is built — and that build is paid from the ship's *hold*,
    # since there are no stores to draw on yet. Size n costs n × `cloud_city_stage_cost`.
    cloud_city_stage_cost: int = 50   # equipment aboard per size step (0 ⇒ no cities in this universe)
    cloud_city_berths: int = 5000     # colonist berths per city size (capacity = size × this)
    cloud_city_max_size: int = 4      # the ceiling a city can be built to
    cloud_city_npc_size: int = 2      # the city an alliance-owned gas giant is generated with
    # Band-weighted ownership at generation (unowned fraction non-decreasing, §4.2).
    ownership: dict[str, OwnershipWeights] = Field(default_factory=dict)
    # Who already lives here when the universe is generated (GW-WP09-PRE).
    inhabitants: InhabitantsConfig = InhabitantsConfig()


class BaseServicesConfig(BaseModel):
    """Forward-base service set at a player-owned operational orbital base (§4.2, WP53).

    A repaired, claimed base becomes a working home: the same Stardock commands
    (repair / component purchase / munitions resupply / banking) resolve through one
    service-point seam, differing only in availability and fee. Each service is a bool
    toggle; `fee_frac` is the latinum markup over Stardock prices (frontier convenience
    costs — default 1.25). `component_stock_tiers` caps which tiers a base sells
    (default I/II; Tier III stays barter-only per §8). Banking rides the same
    `Player.bank_balance` invariants as Stardock — location is the value, not yield.
    `trade_cut_frac` is the base-hosted-market commission (§4.2, WP78): the share of
    each commodity trade's value paid from the port's purse to a player/corp owner.
    """

    model_config = _FROZEN

    repair: bool = True
    components: bool = True
    munitions: bool = True
    banking: bool = True
    fee_frac: float = Field(default=1.25, ge=1.0)  # markup over Stardock (≥1: never cheaper)
    component_stock_tiers: list[str] = Field(default_factory=lambda: ["I", "II"])
    trade_cut_frac: float = Field(default=0.05, ge=0.0, le=0.5)  # market commission (WP78)


class StarbaseConfig(BaseModel):
    """Orbital-starbase generation + layout (DESIGN §4.2, WP4).

    A starbase reuses the slotted-subsystem model minus thrusters/spindrive, plus a
    `fusion_reactor` (`subsystems` here are keyed by Subsystem value, like a hull's).
    `owned_base_chance` is the per-planet roll for an **intact** base on an owned
    world; `derelict_chance` the roll for a **derelict** base on an unowned,
    uninhabited world (effected by stripping the reactor keystone, so the remaining
    parts are a salvage cache). `ship_class_id` is the base's class label.
    """

    model_config = _FROZEN

    ship_class_id: str = "orbital_platform"
    owned_base_chance: float = 0.0
    derelict_chance: float = 0.0
    subsystems: Mapping[str, SubsystemLayout]
    # Set-piece assault + planetary defense (§4.2, §10 — WP40). An operational base
    # fields a foe scaled by its surviving component integrity: hull interpolates from
    # `defense_hull_floor` (a fully-degraded but powered base) up to its class hull,
    # shields/damage scale linearly with integrity. Razing a base pays `raze_bounty`
    # latinum + `raze_experience`; claiming a repaired, unowned base costs `claim_cost`.
    defense_hull_floor: float = Field(default=0.5, ge=0.0, le=1.0)
    raze_bounty: int = Field(default=750, ge=0)
    raze_experience: int = Field(default=25, ge=0)
    claim_cost: int = Field(default=2000, ge=0)
    # Service integrity gate (§4.2, WP-PR04): a powered base whose surviving-component
    # integrity falls below this fraction withholds its forward services (market, hardware,
    # munitions, bank) until repaired above it. Recovery (salvage/repair) stays open below
    # the line, so a battered base is always workable — it just cannot yet serve customers.
    service_integrity_min: float = Field(default=0.70, ge=0.0, le=1.0)
    # Forward-base services offered once a base is player-owned and operational (§4.2, WP53).
    services: BaseServicesConfig = BaseServicesConfig()


class DiscoveryConfig(BaseModel):
    """Discovery salting + detection + payout tables (DESIGN §7, WP5).

    The big bang rolls a discovery into a fraction of sectors (`sector_density`) and a
    surface site onto a fraction of planets (`surface_site_chance`), picking a kind by
    weight and a rarity tier from the sector's **band** weights — so rarity (and the
    `tier_value` it maps to) rises with distance, the gradient the validator asserts.
    Detection is a capability gate: a `hidden` find is revealed on entry only when the
    ship's effective sensor rating (minus `nebula_interference` inside a nebula) meets
    the tier's `sensor_difficulty`. `barter_equivalence` maps a rarity tier to a
    component tier for artifact payloads (§8). The black-hole gravity warp is a
    configured-but-inert seam in Phase 2 (`black_hole_gravity_warp` default off).
    """

    model_config = _FROZEN

    sector_density: float = 0.20      # fraction of sectors with a space discovery
    surface_site_chance: float = 0.50  # fraction of planets with surface sites
    surface_sites_max: int = 3        # up to this many sites on a seeded planet (§7, WP6)
    # band name -> {RarityTier name -> weight}; outer bands weight the high tiers.
    band_rarity_weights: dict[str, dict[str, int]]
    tier_value: dict[str, int]        # RarityTier name -> latinum-equivalent value (gradient)
    barter_equivalence: dict[str, str]  # RarityTier name -> ComponentTier name (artifact payloads)
    sensor_difficulty: dict[str, int]  # RarityTier name -> min effective sensor to detect
    nebula_interference: int = 2      # sensor rating subtracted inside a nebula sector
    space_kinds: dict[str, int]       # DiscoveryKind name -> weight (open-space finds)
    surface_kinds: dict[str, int]     # DiscoveryKind name -> weight (planet sites)
    hidden_kinds: list[str] = Field(default_factory=list)  # kinds needing a sensor check
    # Space-discovery kinds that may NOT share a sector with a port (§7 seam). Empty
    # ⇒ every kind may coexist with a port; populate this to bar specific kinds later.
    port_incompatible_kinds: list[str] = Field(default_factory=list)
    component_pool: list[str] = Field(default_factory=list)  # Component names for component payloads
    salvage_turn_cost: int = 2        # turns to collect a discovery (§7)
    scan_turn_cost: int = 1           # turns for an explicit sensor sweep
    surface_hidden_min_rank: int = 3  # surface sites of this rarity rank+ need a sensor sweep
    black_hole_gravity_warp: bool = False  # Phase-3 seam; inert in Phase 2
    black_hole_warp_turn_cost: int = 5


class GenesisConfig(BaseModel):
    """Genesis-torpedo device tunables (DESIGN §4.2, WP10).

    A Genesis torpedo is bought at Stardock for `price` latinum and deployed on an
    **unowned** planet of an `eligible_types` kind (the dead worlds — barren / belts /
    gas giants), transforming it into a `result_type` (a colonizable terrestrial) by
    re-rolling its yield/habitability from config. Deterministic, so it replays.
    """

    model_config = _FROZEN

    device_id: str = "genesis_torpedo"
    price: int = 15_000
    result_type: str = "terrestrial_warm"
    eligible_types: list[str] = Field(default_factory=list)


class CitadelLevelConfig(BaseModel):
    """One rung of the citadel ladder (§4.2, §14, WP54).

    Cumulative levels 1-3, each paid up front in equipment (from planet stores) +
    latinum, gated on a minimum colony size, and completed as a timed build measured in
    colonist-days. `garrison_mult` multiplies the planet's fighter garrison in the
    invasion math (WP55) — higher levels make a world harder to take.
    """

    model_config = _FROZEN

    cost_equipment: int = Field(ge=0)
    cost_latinum: int = Field(ge=0)
    min_colonists: int = Field(ge=0)
    build_colonist_days: int = Field(gt=0)  # colonist-days to complete (colonists accrue per tick)
    garrison_mult: float = Field(default=1.0, ge=1.0)  # defense multiplier on the garrison (WP55)


class CitadelConfig(BaseModel):
    """Citadels: planetary defense levels with treasury and a fixed gun (§4.2, §14, WP54).

    `levels[i]` is level `i+1`. L1 grants the treasury + a garrison bonus, L2 the fixed
    **citadel gun** (stats below — it joins sector defense exactly as an orbital base
    does), L3 a **siege shield** (invasion barred while any base or the gun stands). The
    gun's health is `Planet.gun_integrity`, seeded to `gun_hull` on completion and ticked
    down when silenced (WP55).
    """

    model_config = _FROZEN

    levels: list[CitadelLevelConfig]
    gun_min_level: int = 2       # citadel level at which the fixed gun appears
    shield_min_level: int = 3    # level granting the siege shield (WP55)
    gun_hull: int = Field(default=400, gt=0)
    gun_shields: int = Field(default=200, ge=0)
    gun_damage: int = Field(default=40, gt=0)
    gun_defense: int = Field(default=30, ge=0)
    # Ground-assault resolution (§4.2, §14, WP55). Per round each side loses a random
    # fraction of the *other's* current strength (BNT §A.3 shape), drawn in the reducer.
    invasion_round_lo: float = Field(default=0.10, ge=0.0, le=1.0)
    invasion_round_hi: float = Field(default=0.35, ge=0.0, le=1.0)
    civilian_survival_frac: float = Field(default=0.5, ge=0.0, le=1.0)  # colonists kept on conquest
    invasion_alignment_penalty: int = Field(default=20, ge=0)  # alignment hit on a failed assault
    # Garrison production (§4.2, WP55): fighters minted per production tick equal
    # `output × fighter_allocation × fighter_yield` (equipment-flavoured, so a colony trades
    # trade goods for defenders). Requires an owned colony with a fighter allocation share.
    fighter_yield: float = Field(default=0.5, ge=0.0)


class GovernanceConfig(BaseModel):
    """NPC-driven Core upheavals — seizures + leadership intrigue (DESIGN §6.3, WP51).

    A background hum, config-gated. Each day the `governance_tick` cron rolls, per
    eligible bloc, a `seizure_chance` that a `covets_core` bloc (whose home-cluster
    bases are intact) seizes the Core once the incumbent's operational Core-planet bases
    have fallen below `min_incumbent_bases` — so a flip never comes from nowhere. A
    separate `intrigue_chance` rolls an internal leadership coup (§6.3
    `internal_rival_species_id`). All rolls use a salted sub-RNG + `Game.governance_seq`,
    so the galaxy's upheavals replay exactly (H11).
    """

    model_config = _FROZEN

    enabled: bool = True
    seizure_chance: float = Field(default=0.002, ge=0.0, le=1.0)  # per eligible bloc / day
    intrigue_chance: float = Field(default=0.001, ge=0.0, le=1.0)  # per bloc with a rival / day
    # Seizure readiness gate: the incumbent must be down to *fewer* than this many
    # operational Core-planet bases (default 1 ⇒ its Core presence is fully broken first).
    min_incumbent_bases: int = Field(default=1, ge=0)


class ContractsConfig(BaseModel):
    """Favors + escort contracts issued through the dialogue system (DESIGN §6.7, §14 — WP57).

    A friendly (or allied) speaker may offer the player one job — deliver goods to a
    port short of them, destroy a foe it holds a grudge against, or escort one of its
    merchants to a destination. Rewards flow through the existing latinum / attitude /
    artifact rails, so a contract is a bounded faucet (slips) and a standing lever
    (attitude) rather than a new economy. Deterministic offer selection (`pick_contract`)
    mirrors the intel planner so the projection and the reducer agree on the very job the
    player accepts. Config-gated so a host can run a contract-free universe.
    """

    model_config = _FROZEN

    enabled: bool = True
    deadline_days: int = Field(default=12, ge=1)  # days from acceptance before a job lapses
    # A deliver job asks for this many units of a commodity a target port is short of; the
    # reward is `deliver_reward_per_unit × qty` slips (a modest faucet over honest carriage).
    deliver_qty: int = Field(default=25, ge=1)
    deliver_reward_per_unit: int = Field(default=18, ge=0)
    # A destroy job (cash a grudge, §6.5) pays a flat bounty on the kill.
    destroy_reward: int = Field(default=1500, ge=0)
    # An escort job pays for delivering a merchant safely to its destination sector.
    escort_reward: int = Field(default=1200, ge=0)
    # Every completed job also warms the player toward the issuer's kind by this offset
    # (capped so effective disposition never exceeds 1, like every attitude gain).
    attitude_reward: float = Field(default=0.06, ge=0.0, le=1.0)
    # Each combat round fought with a live foe and an escorted merchant in the fight's
    # sector, the pack may fall on the convoy instead (WP75): the merchant is destroyed,
    # the job fails, and the issuer takes the WP27 souring rail (a lost charge is a
    # betrayal of trust). 0 disables convoy targeting entirely.
    escort_target_chance: float = Field(default=0.25, ge=0.0, le=1.0)


class AliensConfig(BaseModel):
    """Disposition thresholds + escape floor for the alien system (DESIGN §6, §10).

    Effective disposition (base + the player's attitude offset, clamped 0–1) falls in
    a band named by these thresholds: < `hostility` is hostile, ≥ `amity` is friendly,
    the middle is neutral. The thresholds gate greeting-vs-violence (§10) and the
    band-graded placement of §5/§6 (Phase 3).
    """

    model_config = _FROZEN

    hostility_threshold: float = 0.35
    amity_threshold: float = 0.65
    escape_floor: float = 0.10  # player escape chance never drops below this (§10)

    # Band-graded placement (Phase 3, §5/§6): a per-band additive bias on each placed
    # species' drawn disposition, so mean stance falls (and danger rises) outward. The
    # innermost band (Hub) stays clamped friendly regardless — the Hub is peaceable by
    # §5 — and each band's guaranteed resupply contact is also drawn friendly (§13); the
    # bias only pushes the *remaining* outer-band species toward hostility.
    band_disposition_bias: dict[str, float] = Field(
        default_factory=lambda: {"Hub": 0.0, "Frontier": -0.1, "Deep": -0.2, "Void": -0.3}
    )
    # Tolerance for the aggregate mean-disposition-falls-outward gradient (a §13 test
    # property over many seeds, not a per-universe invariant — the mandated per-band
    # friendly anchor plus small per-band samples make strict per-seed monotonicity
    # unreliable).
    disposition_gradient_tolerance: float = 0.1

    # Consequences of conduct (§6.5, §10 — WP27). Destroying a species' ship sours the
    # attitude offset by its `attitude_loss_rate` and deepens a grudge against the
    # player by `grudge_severity_per_kill` (capped at 1.0); a `memory_model: none`
    # species forgets instantly (no souring, no grudge), `never_forgets` /
    # `betrayal_model: permanent` grudges never decay and lock the offset for good.
    grudge_severity_per_kill: float = 0.08
    grudge_duration_days: int = 30  # finite-grudge expiry (normal memory)
    # Alignment shifts per kill, keyed by the victim's effective-disposition band at
    # the time — gunning down friendlies is crime, hunting hostiles is lawful bounty.
    alignment_kill_friendly: int = -3
    alignment_kill_neutral: int = -1
    alignment_kill_hostile: int = 1
    # Experience: per kill, max(1, round(threat_rating × scale)); flat per codex stamp.
    experience_kill_scale: float = 10.0
    experience_per_discovery: int = 5
    # Core law (WP27 basics; full enforcement WP38): below this alignment the player
    # is criminal and the governor's patrols take notice on Core entry.
    criminal_alignment: int = -10
    # Bounty paid per hostile combat unit destroyed (§10, WP44 — echoing TW2002's Cabal
    # 100/kill): a latinum faucet that funds the fight against the frontier's raiders. Only
    # **hostile-band** ship kills and hostile sector-fighter garrisons pay — culling raiders
    # is rewarded; gunning down the peaceable is not.
    bounty_per_kill: int = 100

    # Inter-species relations + reputation spillover (§6.4, WP39). The relation matrix is
    # alliance-derived by default — bloc-mates default to `relation_ally_default`, members
    # of a (symmetric) rival bloc to `relation_rival_default` — with the roster's sparse
    # `relations` overrides winning per ordered pair (so the matrix is asymmetric).
    # Spillover: a change of `delta` in the player's attitude toward X nudges attitude with
    # each species Y in proportion to X's relation toward Y (`delta × spillover_fraction ×
    # relation`), for relations of at least `spillover_threshold` magnitude — helping X
    # warms X's friends and chills X's enemies (harming X does the reverse).
    relation_ally_default: float = 0.5
    relation_rival_default: float = -0.5
    spillover_fraction: float = Field(default=0.25, ge=0.0, le=1.0)
    spillover_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    # Alien ship drift (WP16, §6.3): each species rolls `drift_move_chance` per firing
    # to warp to a uniformly-chosen legal adjacent sector. A quiet galaxy is chance 0
    # or `drift_enabled=False`. The cron cadence lives in `ticker.crons.alien_drift`.
    drift_enabled: bool = True
    drift_move_chance: float = Field(default=0.25, ge=0.0, le=1.0)
    # The roaming Entity (§7, WP36) wanders at its own pace and anywhere non-Core (its
    # occupancy is unbound by the alliance/rival rules that gate ordinary drift).
    entity_drift_chance: float = Field(default=0.5, ge=0.0, le=1.0)

    # NPC traders (DESIGN §8, WP43). A friendly merchant species (movement policy
    # `trade_seek`) executes real trades on the `trader_step` cron: it seeds a purse of
    # `trader_start_cash` on its first step, then per step buys the cheapest good deal a
    # co-located port offers (quoted price below `trader_buy_discount_frac × base`) or
    # dumps held cargo the port buys, up to `trader_trade_units` a step, carrying at most
    # `trader_cargo_capacity`. Goods move through the §8 pricing (conserved with the port;
    # prices feed back), so a trader visibly works the lanes. A player sharing the sector
    # of a trading merchant warms toward it by `trader_alongside_attitude` per step
    # (capped so effective ≤ 1) — trading alongside them builds standing.
    trader_start_cash: int = Field(default=5000, ge=0)
    trader_cargo_capacity: int = Field(default=100, ge=0)
    trader_trade_units: int = Field(default=20, ge=1)
    trader_buy_discount_frac: float = Field(default=0.95, ge=0.0, le=1.0)
    trader_alongside_attitude: float = Field(default=0.02, ge=0.0, le=1.0)

    # NPC governance: Core seizures + leadership intrigue (§6.3, WP51). Cadence lives in
    # `ticker.crons.governance_tick`; the rolls are gated + salted by this block.
    governance: GovernanceConfig = GovernanceConfig()

    # Favors + escort contracts issued through dialogue (§6.7, §14, WP57).
    contracts: ContractsConfig = ContractsConfig()


class CombatConfig(BaseModel):
    """Combat-round parameters (DESIGN §10, Phase 3 — WP25).

    Flee: `flee_base + flee_speed_coeff·combat_speed − interception_coeff·interception
    + cloak_coeff·cloak − damage_penalty·hull_damage_fraction`, **clamped to
    [`aliens.escape_floor`, `flee_cap`]** — the §13 floor invariant. An `ahead`/`spinal`
    attacker is evaded on a combat-speed contest (`evade_base + evade_speed_coeff·Δspeed`);
    `all_round` cannot be evaded. `threat_damage_scale` turns a species' `threat_rating`
    into bonus damage per round atop its hull's weapon. The Spindrive `efficiency_bonus`
    (§4.1) adds to gun damage, combat speed, and screen deflection once each.
    """

    model_config = _FROZEN

    flee_base: float = 0.35
    flee_speed_coeff: float = 0.05   # per point of player combat speed
    interception_coeff: float = 0.5  # per point of species interception_rating (0..1)
    cloak_coeff: float = 0.03        # per point of cloak rating
    damage_penalty: float = 0.25     # × the player's missing-hull fraction
    flee_cap: float = 0.95
    evade_base: float = 0.35         # vs ahead/spinal arcs (a combat-speed contest)
    evade_speed_coeff: float = 0.06  # per point of (player speed + bonus − foe speed)
    evade_cap: float = 0.9
    threat_damage_scale: float = 3.0  # species threat_rating → bonus damage per round
    missile_damage: int = 30
    missile_price: int = 300         # per missile at the Stardock hardware emporium (§8)
    swarm_size_min: int = 3          # pack size for swarm/colony behaviors (§6.1)
    swarm_size_max: int = 5
    # NPC retreat (§10, WP-PR03): a bloodied surviving pack may break off and warp to a
    # legal adjacent sector rather than fight to the death. It only rolls once the pack's
    # aggregate hull falls to `npc_retreat_hull_frac`, at `npc_retreat_chance` per round,
    # and only for packs whose threat tier allows it (fearsome/special never run).
    npc_retreat_hull_frac: float = 0.35
    npc_retreat_chance: float = 0.4
    npc_retreat_tiers: tuple[str, ...] = ("worthy", "feeble")
    # Localized damage (§4.1, WP26): a volley that reaches the hull may also knock out
    # one subsystem component, the pick weighted toward exposed/forward systems.
    knockout_chance: float = 0.35
    knockout_weights: dict[str, float] = Field(
        default_factory=lambda: {"main_gun": 3.0, "thrusters": 3.0, "screens": 2.0, "spindrive": 1.0}
    )
    # Ship destruction (§10, WP26): hull 0 drops the player to this hull (a real
    # ship class with price 0 — never sold, only issued by the wreck).
    escape_pod_class: str = "escape_pod"
    # Salvage from destroyed NPCs (§10, BNT's 10–20% rule): each wreck pays
    # `hull_max × salvage_hull_value × U[frac_min, frac_max]` latinum, and with
    # `salvage_component_chance` yields one loose Tier-I part (needs a free hold).
    salvage_frac_min: float = 0.10
    salvage_frac_max: float = 0.20
    salvage_hull_value: float = 3.0
    salvage_component_chance: float = 0.25


class TerritoryConfig(BaseModel):
    """Sector fighters / mines / beacons / hazards (DESIGN §10, WP41).

    Deployable territory: `fighter_price`/`mine_price` are per-unit Stardock costs, and
    `beacon_price` the flat cost to plant a comms beacon. A hostile mine field deals
    `mine_damage` per surviving mine on entry (shields absorb first), consuming the mines.
    Hostile fighters force engage-or-retreat — the garrison fights as a foe whose hull is
    `fighter_hull_each` per fighter (arc `all_round`, `fighter_damage_each` per fighter);
    fleeing (retreat) costs the garrison `retreat_fighter_cost` fighters (the original
    rule). A `black_hole` sector deals `black_hole_damage` on entry (a gravity toll).
    """

    model_config = _FROZEN

    fighter_price: int = Field(default=50, ge=0)
    mine_price: int = Field(default=200, ge=0)
    beacon_price: int = Field(default=100, ge=0)
    mine_damage: int = Field(default=40, ge=0)      # per surviving mine, on hostile entry
    fighter_hull_each: int = Field(default=6, ge=1)
    fighter_damage_each: int = Field(default=2, ge=0)
    retreat_fighter_cost: int = Field(default=1, ge=0)  # retreat costs the garrison a fighter
    black_hole_damage: int = Field(default=30, ge=0)
    # Armid/limpet split (§10, WP56). Armid mines damage on entry (above); a carried
    # `mine_deflector` device absorbs armid hits one-for-one. Limpet mines attach to the
    # entrant, tagging it for the owner's hunters; removed for `limpet_removal_fee` at any
    # service point (§4.2/WP53).
    mine_deflector_device: str = "mine_deflector"
    limpet_removal_fee: int = Field(default=500, ge=0)


class EncountersConfig(BaseModel):
    """Encounter-roll parameters (DESIGN §10, Phase 3 — consumed by the WP24 encounter
    system; authored here so the config epoch carries it).

    `interrupt_chance` per band: the probability moving through/lingering in a band
    rolls an encounter (0 in the Hub — home is safe; rising outward). When one fires,
    a species is drawn with weight **inverse to threat rating** (common weak raiders
    harass the frontier; the apex predators of the Void are rarely seen), floored so
    even an apex species appears occasionally.
    """

    model_config = _FROZEN

    interrupt_chance: dict[str, float] = Field(
        default_factory=lambda: {"Hub": 0.0, "Frontier": 0.12, "Deep": 0.22, "Void": 0.32}
    )
    weight_inverse_threat: bool = True
    weight_floor: float = Field(default=0.05, ge=0.0)
    # Pre-engagement detection (§10): the species' sensors (its lead hull's rating)
    # against the player's cloak, dimmed by nebula cover; an undetected player slips
    # away freely — stealth is a genuine alternative to firepower.
    detection_base: float = 0.7
    detection_sensor_coeff: float = 0.05  # per point of the species' hull sensor rating
    detection_cloak_coeff: float = 0.08   # per point of the player's cloak rating
    nebula_cover: float = 0.25            # flat detection penalty inside a nebula


class SeizureConfig(BaseModel):
    """A `covets_core` bloc's Core-seizure ladder (DESIGN §6.3, WP50).

    The price a player champions to flip the Core to this bloc: `price` is a list of
    befriend-price task tokens (the §6.1 vocabulary, recorded in a reserved `species_arcs`
    seizure ledger), `bases_to_raze` is how many of the incumbent's Core-planet starbases
    must be razed (counted from state, not double-booked), and `fee` is a flat latinum cost.
    """

    model_config = _FROZEN

    price: list[Literal["serve", "obey", "prove", "pay", "purge"]] = Field(default_factory=list)
    bases_to_raze: int = Field(default=0, ge=0)
    fee: int = Field(default=0, ge=0)


class AllianceConfig(BaseModel):
    """One alliance / rival bloc in the roster (DESIGN §6.3).

    Joinability (WP38): a player may belong to **at most one** bloc, gated by the
    `admission_price` task ledger and the `membership_gate`. `admission_price` is a
    list of befriend-price task tokens (the §6.1 vocabulary) the player must complete
    (recorded in the `species_arcs` alliance ledger) before the bloc will admit them;
    `admission_fee` is a flat latinum joining cost. `membership_gate` names how the
    gate is administered: `open` (join freely) or `petition` (the `admission_price`
    tasks must be met). `rivals` lists the alliance ids this bloc treats as enemies —
    joining sours the player's standing with them (and rivalry is symmetric, so being
    named a rival is enough); a player whose bloc the Core governor counts as a rival
    finds the Core unsafe (§6.3, WP38).
    """

    model_config = _FROZEN

    id: int
    name: str
    banner: str = ""
    covets_core: bool = False  # may seize the Core in Phase 5 (authored hint, inert now)
    admission_price: list[Literal["serve", "obey", "prove", "pay", "purge"]] = Field(
        default_factory=list
    )
    admission_fee: int = Field(default=0, ge=0)  # flat latinum joining cost (§8)
    membership_gate: Literal["open", "petition"] = "open"
    rivals: list[int] = Field(default_factory=list)  # alliance ids this bloc opposes
    core_seizure: SeizureConfig | None = None  # WP50 Core-seizure ladder (covets_core only)
    # Leadership intrigue (§6.3, WP51): the roster_id of the member/aspirant that may usurp
    # the bloc's leadership on the `governance_tick` cron. `intrigue_turns_outward` makes the
    # usurped bloc gain `covets_core` — the authored §6.3 hook, expressed as data.
    internal_rival_species_id: str | None = None
    intrigue_turns_outward: bool = False

    @model_validator(mode="after")
    def _seizure_only_for_coveters(self) -> AllianceConfig:
        """A Core-seizure ladder is meaningful only on a `covets_core` bloc (§6.3, WP50)."""
        if self.core_seizure is not None and not self.covets_core:
            raise ValueError(f"alliance {self.id} has a core_seizure but is not covets_core")
        return self


class SignatureMechanicConfig(BaseModel):
    """A species' one systemic hook (DESIGN §6.2): a named hook + its params.

    Authored now for Phase-3 forward-compat (the hook is implemented in Phase 3);
    Phase 2 only validates that `hook` names a known mechanic for reference integrity.
    """

    model_config = _FROZEN

    hook: str  # trojan_gift / reprogram_unlock / influence_gate / morality_judge / …
    params: dict[str, Any] = Field(default_factory=dict)


class TechOfferConfig(BaseModel):
    """One aspect-upgrade a species sells or barters (DESIGN §6, §6.1 tech-offer table).

    Either a `component` (a `Component` value installed via the engine room) or a flat
    `aspect` label (sensors / cloak / holds). `mode` is `latinum` (cash sale) or
    `barter` (traded for an artifact of `tier`-equivalent rarity, §8). `min_disposition`
    gates the offer behind effective disposition (favours unlock higher tiers). Consumed
    by WP9; authored now so the roster is complete.
    """

    model_config = _FROZEN

    tier: str  # ComponentTier name (I/II/III)
    mode: Literal["latinum", "barter"] = "latinum"
    component: str | None = None  # a Component value, or None for an `aspect` offer
    aspect: str | None = None  # sensors / cloak / holds (flat aspect upgrade)
    amount: int = 1  # magnitude of an aspect upgrade (ignored for component offers)
    price: int = 0  # latinum price when mode == latinum
    min_disposition: float = 0.0


class PackConfig(BaseModel):
    """How an encounter group spawns (DESIGN §6.1). Phase-3 forward-compat."""

    model_config = _FROZEN

    behavior: Literal["solo", "escorted", "swarm", "family_group", "colony"] = "solo"
    escort: list[str] = Field(default_factory=list)  # ship_class ids accompanying


class DialogueWhen(BaseModel):
    """A line entry's criteria predicate (DESIGN §6.7, salience-scored selection).

    Matched against the encounter **fact dictionary**: `standing` (the effective-disposition
    band, plus an `allied` band when the player shares the species' alliance), whether a
    `treaty` is in force, any general `criteria` (arbitrary fact key → required value — e.g.
    `low_fuel`, `has_intel_target` — for the Ruskin most-specific-wins matcher), and —
    forward-compat for Phase 3 — the species' current `posture` / a `stage` on its
    signature-mechanic or befriend ladder. An omitted field/empty `criteria` matches
    anything; an entry that pins nothing is the catch-all default. A line's **specificity**
    (how many facts it pins) decides ties: the most-specific matching entry wins.
    """

    model_config = _FROZEN

    standing: str | None = None  # allied / friendly / neutral / wary / hostile
    treaty: bool | None = None
    # General encounter facts the line requires (fact key -> required value). Lets new
    # facts (player needs, intel availability) gate lines without schema churn (§6.7).
    criteria: dict[str, str | int | bool] = Field(default_factory=dict)
    posture: str | None = None  # forward-compat (trade_posture-gated lines)
    stage: str | None = None  # forward-compat (signature/befriend ladder stage)


class DialogueChoice(BaseModel):
    """An authored **player reply** on a line entry (DESIGN §6.7, optional branching).

    A line entry may offer a list of `choices`; when present the contact screen renders them
    as numbered player replies instead of (and falling back to) the *derived* Say/Do menu.
    A choice carries a templated `text` label (filled with the same `{placeholders}` as the
    spoken line), an optional `next_context` to transition to (any known context key,
    including a reserved `branch.*` node), an optional mechanical `action` (one of
    `CHOICE_ACTIONS` — leave / trade / barter / accept_lead / attack; `attack` is
    Phase-3-gated), an optional `arc` flag map written to the player's **persisted**
    per-species arc state when the reply is taken (`Player.species_arcs`, surfaced back to
    selection as `arc.<flag>` facts — the §6.7/WP30 cross-visit unlock), and a `when`
    predicate gating whether the reply is offered. Conversation *position* is not stored
    in core state: the reducer re-resolves the line for the active context and validates
    the chosen index, so a reply is reproducible from (seed, log).
    """

    model_config = _FROZEN

    text: str  # the player's reply label (templated with the node's placeholders)
    next_context: str | None = None  # context key to transition to (None ⇒ stay / act only)
    action: str | None = None  # a CHOICE_ACTIONS verb, or None for a pure transition
    # Cross-visit arc flags this reply sets (flag -> value), merged into the player's
    # `species_arcs[roster_id]` by the reducer; gate later entries on `arc.<flag>` (WP30).
    arc: dict[str, str | int | bool] = Field(default_factory=dict)
    when: DialogueWhen = DialogueWhen()
    weight: int = Field(default=1, ge=1)


class DialogueLine(BaseModel):
    """One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight.

    A line realises its beat one of two ways, both templated with `{placeholders}`:

    - **`variants`** — a pool of interchangeable phrasings; the selector draws one through
      the seeded RNG avoiding the recently-shown indices (the recency ring); or
    - **`grammar`** — a Tracery rule map (`symbol -> expansions`, expanded from `origin`),
      authored offline so a compact grammar yields combinatorial variety at runtime
      (`edge.dialogue.render`). The recency ring rotates the expansion so repeats rephrase.

    Exactly one of the two must be non-empty. Among matching entries the most-specific wins,
    ties broken by `weight`. An entry may also carry authored player `choices` (§6.7
    branching); an empty list keeps the legacy derived-menu behaviour on the contact screen.
    """

    model_config = _FROZEN

    variants: list[str] = Field(default_factory=list)
    # Tracery grammar (`symbol -> expansions`); when set, realised by expanding `origin`.
    # References to shared persona/global fragments resolve against `RosterConfig.grammar`.
    grammar: dict[str, list[str]] = Field(default_factory=dict)
    when: DialogueWhen = DialogueWhen()
    weight: int = Field(default=1, ge=1)
    # Authored player replies (optional branching, §6.7). Empty ⇒ the contact screen falls
    # back to the derived Say/Do verb menu; non-empty ⇒ numbered player choices.
    choices: list[DialogueChoice] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_realisation(self) -> DialogueLine:
        if not self.variants and not self.grammar:
            raise ValueError("a dialogue line needs non-empty `variants` or `grammar`")
        if self.grammar and "origin" not in self.grammar:
            raise ValueError("a grammar line must define an 'origin' symbol")
        return self


# A dialogue pack maps a context key (greeting, trade_open, dossier_other, …) to its
# ordered list of conditional line entries (DESIGN §6.7).
DialoguePack = dict[str, list[DialogueLine]]


class SpeciesLoreConfig(BaseModel):
    """Structured background lore for a species, matching the reference headers."""

    model_config = _FROZEN

    biology_and_appearance: str = ""
    psychology_and_culture: str = ""
    diplomacy_and_behavior: str = ""
    relationships: str = ""
    combat_and_ships: str = ""


class GrudgeSeedConfig(BaseModel):
    """An authored, dated grievance a species starts the game holding (DESIGN §6.5).

    Seeded into `UniverseState.grudges` at the big bang when both parties are cast.
    Schema lands in WP27; the NPC-vs-NPC semantics (stances, spillover) are WP39.
    `duration_days: -1` never expires (the roster's centuries-old vendettas).
    """

    model_config = _FROZEN

    target: str  # roster id of the aggrieved-against species
    cause: str
    severity: float = Field(ge=0.0, le=1.0)
    duration_days: int = -1


class SpeciesConfig(BaseModel):
    """A roster species' full §6.1 parameter set (DESIGN §6.1).

    Authored in full as Phase-3 forward-compat; the **friendly-path subset** Phase 2
    actually exercises is the identity, disposition spread, alliance, `tech_level`,
    `home_band`, `trade_posture`/`treaty_mode` (friendly values), `persona`, and
    `tech_offers`. The hostile/Phase-3 fields (`threat_rating`, `interception_rating`,
    `combatant`, `signature_mechanic`, `memory_model`, `betrayal_model`,
    `befriend_price`, `pack`, `fleet`, `starbase_policy`) are carried and checked for
    reference integrity but unread until Phase 3 (PHASE2_PLAN WP7).
    """

    model_config = _FROZEN

    id: str  # roster key (stable; the AlienSpecies entity's `roster_id`)
    name: str
    archetype_id: str
    description: str = ""  # one-line flavour blurb (dossier/codex narration, §6.6/§11)
    lore: SpeciesLoreConfig = Field(default_factory=SpeciesLoreConfig)
    disposition_center: float = Field(ge=0.0, le=1.0)
    disposition_variance: float = Field(default=0.1, ge=0.0, le=1.0)
    tech_level: int = Field(default=1, ge=1, le=10)
    alliance_id: int | None = None
    alliance_role: Literal["leader", "member", "aspirant", "none"] = "none"
    home_band: str | None = None  # preferred band hint (None ⇒ placed by round-robin)
    trade_posture: Literal[
        "open", "earn", "goods_only", "barter", "alliance_gated", "circuit_gated", "refuses"
    ] = "open"
    treaty_mode: Literal[
        "open", "conditional", "prove_intent", "alliance_gated",
        "home_planet_only", "none", "superfluous"
    ] = "open"
    persona: str = "generic"
    tech_offers: list[TechOfferConfig] = Field(default_factory=list)
    # --- Phase-3 forward-compat (authored, validated for reference integrity, unread) -
    threat_tier: Literal["fearsome", "worthy", "feeble", "special"] = "feeble"
    threat_rating: float = 0.0
    interception_rating: float = Field(default=0.0, ge=0.0, le=1.0)
    combatant: bool = True
    memory_model: Literal["normal", "none", "never_forgets"] = "normal"
    betrayal_model: Literal["recoverable", "permanent"] = "recoverable"
    befriend_price: list[Literal["serve", "obey", "prove", "pay", "purge"]] = Field(
        default_factory=list
    )
    signature_mechanic: SignatureMechanicConfig | None = None
    pack: PackConfig = PackConfig()
    fleet: list[str] = Field(default_factory=list)  # ship_class ids the species fields
    starbase_policy: Literal[
        "none", "homeworld", "territorial", "secret", "nomadic_holding"
    ] = "none"
    # Goal-directed drift policy (DESIGN §8/§10, WP42): how this species moves on the
    # `alien_drift` cron. `wander` is pure random (the Phase-2 default, byte-identical);
    # `patrol` hugs the home band; `trade_seek` drifts toward ports; `hunt` pursues a
    # player it holds a grudge against; `coward` flees the nearest player. The Entity
    # keeps its own wander regardless of this field (§7).
    movement_policy: Literal[
        "wander", "patrol", "trade_seek", "hunt", "coward"
    ] = "wander"
    # Which favors this species will offer through dialogue (DESIGN §6.7, WP57): `none`
    # never issues a job; `deliver`/`destroy`/`escort` restrict to one kind; `any` offers
    # whichever fits the live world (a short port ⇒ deliver, a grudge ⇒ destroy, a bloc
    # merchant en route ⇒ escort). Only a friendly/allied-standing speaker ever offers.
    contract_posture: Literal["none", "deliver", "destroy", "escort", "any"] = "any"
    # The one roaming, dialogue-only singular being (DESIGN §7, WP34): an explicit flag
    # (not archetype-string matching, so rosters vary freely). The big bang always draws it
    # (outside the seeded subset), fields exactly one instance in a deep band, and excludes
    # it from clustering / the per-band resupply guarantee / the Core + Stardock paths. It
    # replaces the salted `entity` discovery kind entirely; met only as a voice, never fought
    # (pair with `combatant: false` + empty `fleet`). Codex art keys off `DiscoveryKind.ENTITY`.
    singular_entity: bool = False
    attitude_gain_rate: float = 0.1
    attitude_loss_rate: float = 0.2
    # Inter-species stance overrides (§6.4: sparse, atop alliance-derived defaults) and
    # authored starting grudges (§6.5). Schema + big-bang seeding land in WP27; the
    # NPC-vs-NPC semantics and reputation spillover are WP39.
    relations: dict[str, float] = Field(default_factory=dict)  # roster id → -1..1
    grudges: list[GrudgeSeedConfig] = Field(default_factory=list)
    # Standing-keyed conversation lines (DESIGN §6.7): context key → conditional line
    # entries. A species overrides only the beats that make it distinctive; everything
    # else falls back species → persona → generic (`core.dialogue`). Empty ⇒ the species
    # speaks entirely in its persona's voice.
    dialogue_pack: DialoguePack = Field(default_factory=dict)


class RosterConfig(BaseModel):
    """A named species roster (DESIGN §6): alliances + the species pool drawn from.

    The big bang draws a **seeded subset** of `species` (not all need appear, §6) sized
    in `[subset_min, subset_max]`, clamped to the pool size. Phase 2 places only
    friendly-band members (`bigbang.aliens`). `core_governing_alliance_id` names the
    bloc that governs Core Space (the Federation in the default roster); the player is
    seeded as one of its members.
    """

    model_config = _FROZEN

    core_governing_alliance_id: int
    alliances: list[AllianceConfig]
    species: list[SpeciesConfig]
    # The player's **own people** — the species id whose citizens the Stardock
    # recruitment office enlists. A world the player colonizes is peopled by them, so
    # its orbit view names them rather than reading as nobody in particular. None ⇒ the
    # game has no named home species and such a colony is simply "your colonists".
    player_species_id: str | None = None
    subset_min: int = 6
    subset_max: int = 12
    # High-traffic Core hub: at least this many distinct Core-welcome species (governing
    # alliance members + unaligned neutrals) are staged at the Stardock so a brand-new
    # player meets friendly aliens at the one place every game funnels through (§6.3).
    stardock_contacts: int = Field(default=2, ge=0)
    # How many governing-alliance members to settle in the Core + home lanes (WP18): the
    # governor inhabits its own capital. Clamped to the available members and Core sectors;
    # the founding `leader` is always among them.
    core_population: int = Field(default=3, ge=1)
    # Density knobs (DESIGN §6.3): a species is not a lone contact — it fields a cluster of
    # ships around its home sector, and the Core bustles with governing-alliance traffic.
    # All ships of one species share its kind's reputation/dossier (keyed by `roster_id`),
    # so denser presence never fragments standing.
    ships_per_home: int = Field(default=4, ge=1)      # ships per species home cluster (incl. home)
    home_cluster_radius: int = Field(default=2, ge=1)  # BFS hop radius for the satellites
    core_traffic: int = Field(default=8, ge=0)         # extra governing-member ships filling the Core
    # Persona id → a shareable dialogue pack of generic, voice-correct lines (§6.7). A
    # species inherits its `persona`'s pack and overrides only distinctive beats; the
    # special `generic` persona is the ultimate fallback so a line never blanks.
    personas: dict[str, DialoguePack] = Field(default_factory=dict)
    recency_k: int = Field(default=2, ge=0)  # dialogue no-repeat ring depth (§6.7)
    # Shared Tracery fragments (`symbol -> expansions`) a line's `grammar` may reference —
    # cross-persona vocabulary and persona-voice quirks authored once and reused (§6.7,
    # `edge.dialogue.render`). Merged under each grammar entry, which overrides on collision.
    grammar: dict[str, list[str]] = Field(default_factory=dict)
    # The context the contact screen opens on (§6.7). The `generic` persona MUST author
    # `choices` on this context (validate_dialogue enforces it), so the player always has a
    # config-defined reply menu via the species → persona → generic fallback chain.
    start_context: str = "greeting"
    # Situational-fact buckets (§6.7, WP29): the thresholds behind the `hull` and
    # `low_turns` dialogue facts (`edge.dialogue.facts`). They live with the corpus config
    # because they define what an authored `criteria` gate means — retune them alongside
    # the lines that pin them.
    hull_critical: float = Field(default=0.25, ge=0.0, le=1.0)  # hull ratio ≤ ⇒ "critical"
    hull_scarred: float = Field(default=0.60, ge=0.0, le=1.0)  # hull ratio ≤ ⇒ "scarred"
    low_turns: int = Field(default=25, ge=0)  # turns_remaining below ⇒ `low_turns`

    def alliance(self, alliance_id: int) -> AllianceConfig | None:
        return next((a for a in self.alliances if a.id == alliance_id), None)

    def species_by_id(self, roster_id: str) -> SpeciesConfig | None:
        return next((s for s in self.species if s.id == roster_id), None)

    @model_validator(mode="after")
    def _check_reference_integrity(self) -> RosterConfig:
        """Dialogue/diplomacy reference integrity (§6, §13): ids and hooks resolve."""
        if self.hull_critical > self.hull_scarred:
            raise ValueError("hull_critical must not exceed hull_scarred (bucket order)")
        ids = {a.id for a in self.alliances}
        if self.core_governing_alliance_id not in ids:
            raise ValueError(
                f"core_governing_alliance_id {self.core_governing_alliance_id} is not an alliance"
            )
        for a in self.alliances:
            for rival in a.rivals:
                if rival not in ids or rival == a.id:
                    raise ValueError(f"alliance {a.id} names bad rival {rival!r}")
        seen: set[str] = set()
        for sp in self.species:
            if sp.id in seen:
                raise ValueError(f"duplicate species id {sp.id!r}")
            seen.add(sp.id)
            if sp.alliance_id is not None and sp.alliance_id not in ids:
                raise ValueError(f"species {sp.id!r} references unknown alliance {sp.alliance_id}")
            if sp.signature_mechanic is not None and sp.signature_mechanic.hook not in KNOWN_SIGNATURE_HOOKS:
                raise ValueError(
                    f"species {sp.id!r} has unknown signature hook {sp.signature_mechanic.hook!r}"
                )
        all_ids = {sp.id for sp in self.species}
        for sp in self.species:
            for other in sp.relations:
                if other not in all_ids or other == sp.id:
                    raise ValueError(f"species {sp.id!r} relation names bad target {other!r}")
            for grudge in sp.grudges:
                if grudge.target not in all_ids or grudge.target == sp.id:
                    raise ValueError(f"species {sp.id!r} grudge names bad target {grudge.target!r}")
        return self


class SpriteSize(BaseModel):
    """Footprint bounds (character cells) for one SectorView scene sprite.

    A sprite is sized to the space it's given, clamped to ``[min, max]`` per axis
    so it never shrinks below legibility nor crowds the layout.
    """

    model_config = _FROZEN

    max_width: int = Field(gt=0)
    max_height: int = Field(gt=0)
    min_width: int = Field(default=4, gt=0)
    min_height: int = Field(default=3, gt=0)

    @model_validator(mode="after")
    def _check_bounds(self) -> SpriteSize:
        if self.min_width > self.max_width:
            raise ValueError(f"min_width {self.min_width} > max_width {self.max_width}")
        if self.min_height > self.max_height:
            raise ValueError(f"min_height {self.min_height} > max_height {self.max_height}")
        return self


class PlanetSpriteSize(BaseModel):
    """Planet sprite footprint: height is authored, width is *derived* as 2*height.

    Terminal cells are roughly twice as tall as they are wide, so a 2:1 character
    grid keeps the planet disc round rather than oblong. Callers read `*_width`;
    they never set it, so the round-aspect invariant can't drift.
    """

    model_config = _FROZEN

    max_height: int = Field(default=12, gt=0)
    min_height: int = Field(default=4, gt=0)

    @property
    def max_width(self) -> int:
        return self.max_height * 2

    @property
    def min_width(self) -> int:
        return self.min_height * 2

    @model_validator(mode="after")
    def _check_bounds(self) -> PlanetSpriteSize:
        if self.min_height > self.max_height:
            raise ValueError(f"min_height {self.min_height} > max_height {self.max_height}")
        return self


class SceneArtConfig(BaseModel):
    """Sizes/counts for the SectorView sprite scene (presentation only, no rules).

    The constants the SectorView uses to build its planet/port/ship sprites, kept
    in config per CLAUDE.md (constants live in config, not code). Consumed only by
    the throwaway `tui` layer.
    """

    model_config = _FROZEN

    planet: PlanetSpriteSize = PlanetSpriteSize(max_height=26)  # SectorView primary body
    planet_detail: PlanetSpriteSize = PlanetSpriteSize(max_height=14)  # PlanetScreen orbit view
    # Station max_height must stay ≥ round(scale × planet.max_height) — a lower cap
    # saturates while the planet is still growing, freezing the station at one size
    # across most viewports (the responsiveness bug this guards against). max_width
    # covers the 2.4 primary-branch aspect at max_height.
    port: SpriteSize = SpriteSize(max_width=16, max_height=6)
    stardock: SpriteSize = SpriteSize(max_width=38, max_height=16)
    starbase: SpriteSize = SpriteSize(max_width=22, max_height=9)
    ship: SpriteSize = SpriteSize(max_width=16, max_height=5)
    max_ships_shown: int = Field(default=3, gt=0)  # sprites; extras list as text
    ship_face_inward_chance: float = Field(default=0.5, ge=0.0, le=1.0)
    # Arrival-view scale hierarchy (PT-36): a station beside a rendered primary
    # body scales from that body's actual height; a lone station scales from the
    # scene body. The docked header reuses the Sector composer's resolved dimensions.
    port_scale: float = Field(default=0.25, gt=0.0, le=1.0)
    stardock_scale: float = Field(default=0.6, gt=0.0, le=1.0)
    starbase_scale: float = Field(default=0.35, gt=0.0, le=1.0)
    # Below port_scale so traffic never outsizes the port it visits (§ scale hierarchy).
    ship_scale: float = Field(default=0.2, gt=0.0, le=1.0)  # of the primary body's height

    def station_size(self, kind: Literal["port", "stardock", "starbase"]) -> SpriteSize:
        """The per-type footprint bounds shared by Sector and docked station views."""
        return {"port": self.port, "stardock": self.stardock,
                "starbase": self.starbase}[kind]

    def station_dimensions(
        self, kind: Literal["port", "stardock", "starbase"],
        *, primary_height: int | None, body_height: int,
    ) -> tuple[int, int]:
        """Resolve the original `_paint_station` sizing with per-kind config."""
        size = self.station_size(kind)
        scale = {"port": self.port_scale, "stardock": self.stardock_scale,
                 "starbase": self.starbase_scale}[kind]
        if primary_height is not None:
            height = max(size.min_height,
                         min(size.max_height, round(primary_height * scale)))
            width = max(size.min_width, min(size.max_width, int(height * 2.4)))
        else:
            height = max(size.min_height,
                         min(size.max_height, int(body_height * 0.6)))
            width = max(size.min_width, min(size.max_width, int(height * 2.6)))
        return width, height


class UIConfig(BaseModel):
    """TUI presentation options (no rules) — the sector-screen warp grid + sidebar.

    Distinct from `SceneArtConfig` (sprite footprints): these tune how the screen lays
    out. `warp_columns` is the warp-grid width (cells fill the printable area and wrap
    into rows); `warp_focus_default` is where keyboard focus lands when the sector view
    loads — the first warp (reading order), the came-from/backtrack warp, or the first
    still-unmapped warp. `sidebar_width` is the status sidebar's fixed character width
    (its content is fixed-width, so a proportional column just wastes space);
    `sidebar_min_screen_width` hides the sidebar entirely when the terminal is narrower
    than this, so the sector view isn't squished on small screens. tui-layer only.
    """

    model_config = _FROZEN

    warp_columns: int = Field(default=3, gt=0)
    warp_focus_default: Literal["first", "backtrack", "unexplored"] = "backtrack"
    # Which frame edge the nav rose's `Core` orientation anchor pins to (§11). Fixed —
    # not bearing-driven — so the anchor never jumps sides between sectors; the arrow
    # always faces the same way. `left` ⇒ `◄ Core` at the left edge; `right` ⇒ `Core ►`.
    nav_core_anchor_side: Literal["left", "right"] = "left"
    sidebar_width: int = Field(default=33, gt=0)
    sidebar_min_screen_width: int = Field(default=90, gt=0)
    local_map_radius: int = Field(default=3, gt=0)  # Computer/Map ego-graph reach in warp hops
    # Directory of species portrait images (absolute, or relative to the repo root). Each
    # species uses `<roster_id>.<ext>` and/or `<roster_id>_<digits>.<ext>` variant files.
    portrait_dir: str = "images"
    # chafa `--symbols` selector for the species portrait on the alien contact screen.
    portrait_symbols: str = "vhalf+quad+geometric"
    # Terminal cell width/height, so the portrait keeps its proportions (lower = wider; raise
    # if portraits look stretched, lower if they look squashed horizontally). Terminal-dependent.
    portrait_font_ratio: float = Field(default=0.5, gt=0.0)
    # Debug: show disabled menu options (greyed) instead of filtering them out (debugging only).
    show_disabled_options: bool = False


class NameList(BaseModel):
    """A list of first and last names for combinatoric generation."""

    model_config = _FROZEN

    first_part: list[str] = Field(default_factory=list)
    second_part: list[str] = Field(default_factory=list)


class PlanetNamesConfig(BaseModel):
    """Separate naming lists for grouped planet types."""

    model_config = _FROZEN

    terrestrial: NameList = Field(default_factory=NameList)
    jovian: NameList = Field(default_factory=NameList)
    asteroid_belt: NameList = Field(default_factory=NameList)
    barren: NameList = Field(default_factory=NameList)


class NamesConfig(BaseModel):
    """Configurable name pools for universe entities."""

    model_config = _FROZEN

    regions: NameList = Field(default_factory=NameList)
    ports: NameList = Field(default_factory=NameList)
    stardock: NameList = Field(default_factory=NameList)
    planets: PlanetNamesConfig = Field(default_factory=PlanetNamesConfig)
    # Per-`DiscoveryKind` pools (keyed by the enum's value, e.g. "nebula"), so a find is a
    # *place* — "the Cygnus Veil" — rather than "Nebula ∗ Rare" (PT-49). A kind with no pool
    # falls back to a numbered name, so a roster need not fill every key.
    discoveries: dict[str, NameList] = Field(default_factory=dict)


class CronCadenceConfig(BaseModel):
    """Per-cron cadences in ticks (§9).

    With the default ``tick_seconds=1.0`` each tick is one real second, so a
    cadence of 1200 means "every 20 real minutes".  Operators can tune these
    independently; they do not have to be multiples of each other.
    """

    model_config = _FROZEN

    daily_turn_reset: int = Field(default=1200, ge=1)   # every 20 minutes
    interest_accrual: int = Field(default=1200, ge=1)   # every 20 minutes
    port_economy: int = Field(default=1200, ge=1)       # every 20 minutes
    planet_growth: int = Field(default=1200, ge=1)      # every 20 minutes
    market_settlement: int = Field(default=1200, ge=1)  # daily order-book settlement (§8, WP47)
    governance_tick: int = Field(default=1200, ge=1)    # daily NPC seizures/intrigue (§6.3, WP51)
    alien_drift: int = Field(default=120, ge=1)         # every 2 minutes
    trader_step: int = Field(default=120, ge=1)         # every 2 minutes (NPC traders work the lanes, WP43)


class TickerConfig(BaseModel):
    """Engine tick-loop timing (§9).

    ``tick_seconds`` is the real-time pause between engine ticks.  Cron
    cadences are the intervals (in ticks) at which each job fires.
    """

    model_config = _FROZEN

    tick_seconds: float = Field(default=1.0, gt=0)
    crons: CronCadenceConfig = CronCadenceConfig()


class TavernConfig(BaseModel):
    """The Stardock tavern — rumors + the noticeboard (DESIGN §14 — WP58).

    Rumors are intel for cash (the contact-for-standing path's twin): `rumor_price` slips
    buys the best undiscovered coordinate tip the Core-welcome species collectively know,
    logged as a `Lead`. The noticeboard is a capped ring of player notices (`notice_cap`,
    oldest evicted) — a captain's log single-player, the shared board in Phase 4.
    """

    model_config = _FROZEN

    rumor_price: int = Field(default=500, ge=0)  # a latinum sink: a tip for cash
    notice_cap: int = Field(default=50, ge=1)  # ring size; oldest notice evicted past it
    notice_max_len: int = Field(default=200, ge=1)  # per-notice text cap (sanitised at reducer)


class PvpConfig(BaseModel):
    """Player-vs-player combat rules (DESIGN §14, interview decisions 3-5 — WP67).

    `enabled` is the per-game host toggle: off makes an `AttackPlayer` a rejection in the
    reducer (a cooperative universe; the enforcement is in core, never the transport, so a
    modified client gains nothing). A victor salvages `U[salvage_frac_min, salvage_frac_max]`
    of the loser's cargo + loose components. Killing a *lawful* player (alignment ≥ criminal
    line) drops the attacker's alignment by `alignment_hit` and posts a bounty of `bounty_frac`
    × the victim's ship price — claimable by whoever later pods the outlaw.
    """

    model_config = _FROZEN

    enabled: bool = True  # host toggle; off ⇒ AttackPlayer rejected (cooperative universe)
    salvage_frac_min: float = Field(default=0.10, ge=0.0, le=1.0)  # the §A.3 10-20% echo
    salvage_frac_max: float = Field(default=0.20, ge=0.0, le=1.0)
    bounty_frac: float = Field(default=0.25, ge=0.0)  # bounty as a fraction of victim ship price
    alignment_hit: int = Field(default=200, ge=0)  # alignment lost for a lawful-player kill


class CorpConfig(BaseModel):
    """Player corporations — shared bank + assets + corp war (DESIGN §4 — WP66).

    Forming a corp costs `form_fee` slips (a §8 sink). `tag_max_len` bounds the short
    uppercase handle shown in the sector view. `war_cooldown_days` is how long after
    withdrawing a corp must wait before re-declaring war on the same rival — so war is a
    stance with a cost, not a toll-dodge toggle spammed each hop.
    """

    model_config = _FROZEN

    form_fee: int = Field(default=5000, ge=0)  # latinum to charter a corp (a §8 sink)
    tag_max_len: int = Field(default=5, ge=1)  # sector-view handle length cap
    war_cooldown_days: int = Field(default=3, ge=0)  # re-declare delay after withdrawal


# --------------------------------------------------------------------------- #
# Ground operations (GROUNDWAR_INTEGRATION_PLAN GW-WP02).                       #
#                                                                              #
# Production schema for the survey/assault balance the standalone `edge.groundwar`
# play-test app pioneered. The single YAML source of truth lives in
# `config/groundwar_default.yaml`, resolved by `edge.config` via the
# `groundwar_file:` pointer and validated here — the standalone app now consumes
# this block rather than its own divergent loader. Gameplay terrain feature names
# come from the pure `edge.core.groundwar.terrain` seam; glyph/colour styling
# stays in `edge.art`. Field names mirror the YAML; flattened accessors on
# `GroundwarConfig` (`width`, `latinum_budget`, …) match how the rules read it.
# --------------------------------------------------------------------------- #


class GwWeapon(BaseModel):
    """A suit/garrison weapon or missile (§ ground combat)."""

    model_config = _FROZEN

    range: int = Field(ge=0)
    damage: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    structure_mult: float = Field(default=1.0, ge=0.0)  # damage multiplier vs. structures


class GwSuit(BaseModel):
    """A purchasable powered-armour suit class (GW plan D3)."""

    model_config = _FROZEN

    label: str
    glyph: str
    cost: int = Field(ge=0)  # latinum
    hp: int = Field(gt=0)
    armor: int = Field(ge=0)  # flat damage soak per hit
    move: int = Field(gt=0)  # move points per turn (terrain costs apply)
    jump_range: int = Field(ge=0)
    jump_charges: int = Field(ge=0)
    sight: int = Field(gt=0)
    signature: float = Field(gt=0.0)  # multiplier on enemy sensor radius — must be nonzero
    weapon: GwWeapon
    missiles: int = Field(ge=0)
    missile: GwWeapon
    jam_radius: int = Field(default=0, ge=0)
    command_radius: int = Field(default=0, ge=0)
    command_acc_bonus: float = Field(default=0.0, ge=0.0)
    broadcast_range: int = Field(default=0, ge=0)


class GwGarrisonClass(BaseModel):
    """A planetary ground-defender unit type (infantry / armour)."""

    model_config = _FROZEN

    hp: int = Field(gt=0)
    armor: int = Field(ge=0)
    move: int = Field(gt=0)
    sight: int = Field(gt=0)
    weapon: GwWeapon


class GwTerrain(BaseModel):
    """Gameplay class for a terrain feature name (keyed by `terrain` feature names)."""

    model_config = _FROZEN

    move_cost: int = Field(ge=0)  # 0 == impassable on foot (jump jets clear it)
    cover: float = Field(ge=0.0, le=1.0)  # accuracy soaked by occupying the cell
    blocks_los: bool


class GwPressure(BaseModel):
    """The retrieval clock and escalation ramp bounding an assault."""

    model_config = _FROZEN

    retrieval_turns: int = Field(gt=0)  # boat pickup — surrender must land before this
    casualty_ceiling: float = Field(gt=0.0, le=1.0)  # abort past this fraction of the drop dead
    escalation_every: int = Field(gt=0)  # a sortie wave + defense stiffening every N turns
    escalation_acc_bonus: float = Field(ge=0.0)  # accuracy gained per escalation step
    escalation_acc_cap: float = Field(ge=0.0)  # ... up to this much bonus
    # Macro-turn economy (GW plan D4/D12, GW-WP10): tactical actions cost only local
    # actions, but ending a tactical turn burns main-game turns in quanta — mirrors
    # `GwExpedition.local_turns_per_main_turn`/`main_turn_cost` exactly, since D4's text
    # names "local expedition/assault turns" as the same mechanism for both modes. One
    # local turn here is one full IGOUGO round (`EndGroundTurn`), not one march step.
    local_turns_per_main_turn: int = Field(gt=0)
    main_turn_cost: int = Field(ge=0)


class GwResolve(BaseModel):
    """Planetary Resolve start value and the deltas each event applies to it."""

    model_config = _FROZEN

    start: int
    cap: int  # hardening ceiling — kept above `start` so atrocity/kill events retain headroom
    surrender_threshold: int
    turret_destroyed: int
    aa_destroyed: int
    sensor_destroyed: int
    wall_breached: int
    garrison_killed: int
    military_building_destroyed: int
    citadel_gun_destroyed: int
    city_cowed: int
    broadcast: int
    civilian_building_destroyed: int
    trooper_killed: int

    @model_validator(mode="after")
    def _check(self) -> GwResolve:
        if self.cap < self.start:
            raise ValueError("groundwar.resolve.cap must be >= start")
        return self


class GwEmplacement(BaseModel):
    """A static defensive structure (wall/gate/turret/AA/sensor/citadel gun)."""

    model_config = _FROZEN

    hp: int = Field(gt=0)
    range: int = Field(default=0, ge=0)
    damage: int = Field(default=0, ge=0)
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    radius: int = Field(default=0, ge=0)
    point_blank_bonus: float = Field(default=0.0, ge=0.0)  # accuracy added at the muzzle


class GwDefenses(BaseModel):
    """The static-defense catalog stamped into a defended city."""

    model_config = _FROZEN

    wall: GwEmplacement
    gate: GwEmplacement
    turret: GwEmplacement
    aa: GwEmplacement
    sensor: GwEmplacement
    citadel_gun: GwEmplacement
    building_military_hp: int = Field(gt=0)
    building_civilian_hp: int = Field(gt=0)


class GwGarrison(BaseModel):
    """Garrison unit stats and the escalating-sortie schedule."""

    model_config = _FROZEN

    infantry: GwGarrisonClass
    armor: GwGarrisonClass
    sortie_base: int = Field(ge=0)  # units in the first sortie wave
    sortie_growth: int = Field(ge=0)  # extra units per later wave
    armor_from_wave: int = Field(ge=0)  # waves before tanks join the sorties
    # GW-WP10: the fraction of `reserved_infantry`/`reserved_armor` stationed inside cities
    # at `GroundDrop` (the interview-resolved "pre-placed + sortie remainder" garrison-
    # deployment model); the rest stays held back to feed escalating sorties as before.
    preplaced_frac: float = Field(default=0.35, ge=0.0, le=1.0)
    undetected_first_strike: float = Field(ge=0.0)  # accuracy bonus firing while undetected


class GwScannerBand(BaseModel):
    """One handheld-scanner reading band, applying out to `within` cells."""

    model_config = _FROZEN

    within: float = Field(gt=0.0)  # applies out to this distance from the nearest unfound site
    label: str


class GwExpedition(BaseModel):
    """The peaceful archaeology mode — its own map size and search tuning (GW plan D4-D6)."""

    model_config = _FROZEN

    width: int = Field(ge=2)
    height: int = Field(ge=2)
    sites_min: int = Field(ge=1)  # sensor contacts per descent
    sites_max: int = Field(ge=1)
    supplies_start: int = Field(gt=0)  # every move or dig spends 1; settlements refill it
    dig_cost: int = Field(ge=0)
    dig_radius: int = Field(ge=0)  # a dig opens a trench this wide
    find_resupply: int = Field(ge=0)  # supplies regained at each successful find
    settlement_resupply: int = Field(ge=0)  # supplies regained per settlement visit
    move: int = Field(gt=0)  # move points per turn (terrain costs apply)
    sight: int = Field(gt=0)  # you must be this close to notice disturbed ground
    area_radius: int = Field(gt=0)  # the ship-sensor "general area" circle
    clue_radius: int = Field(ge=0)  # disturbed-ground clues lie within this of the true spot
    clue_count: int = Field(ge=0)
    settlements_min: int = Field(ge=0)  # inhabited worlds only
    settlements_max: int = Field(ge=0)
    city_hint_radius: int = Field(ge=0)  # a settlement's hint shrinks one search circle to this
    scanner: tuple[GwScannerBand, ...]  # nearest-first, non-overlapping
    # Macro-turn economy (GW plan D4/D12): tactical actions cost only local supplies, but
    # marching burns main-game turns in quanta — `main_turn_cost` turns are charged each time
    # the running local-turn count crosses a `local_turns_per_main_turn` threshold. The reducer
    # refuses a march that would cross an unaffordable threshold; extraction is never charged.
    local_turns_per_main_turn: int = Field(gt=0)
    main_turn_cost: int = Field(ge=0)
    # The drop site is the player's choice, but the shuttle refuses open water, peaks, and
    # ice: these feature names are excluded from the landable set (and the set is further
    # confined to the sites' own passable region, so a descent can never strand you on an
    # island away from every contact).
    landing_blocked_features: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> GwExpedition:
        if self.sites_max < self.sites_min:
            raise ValueError("expedition sites_max must be ≥ sites_min")
        if self.settlements_max < self.settlements_min:
            raise ValueError("expedition settlements_max must be ≥ settlements_min")
        if not self.scanner:
            raise ValueError("expedition scanner must define at least one band")
        withins = [b.within for b in self.scanner]
        if withins != sorted(withins) or len(set(withins)) != len(withins):
            raise ValueError(
                "expedition scanner bands must be sorted nearest-first and non-overlapping"
            )
        return self


class GwGroundForce(BaseModel):
    """The player's persistent ground force — recruits, suits, ordnance (GW plan D3).

    Ground troops are *people hired* at Stardock (a per-head incentive, exactly as
    colonists are recruited rather than bought, §4.2) wearing *equipment purchased*
    there (`GwSuit.cost`). Both ride a hull's **passenger berths**
    (`ShipClassConfig.passenger_capacity`) — a third occupancy limit, distinct from cargo
    holds and from colonist berths, so a platoon never competes with trade goods or
    with peopling a colony.

    Ordnance is the suits' heavy shots. Its magazine is the force itself: a ship may
    carry no more ground missiles than its owned suits can chamber
    (`sum(count × suit.missiles)`), so selling suits spills the surplus rather than
    letting ammunition accumulate off the books (G8).
    """

    model_config = _FROZEN

    recruit_price: int = Field(default=250, ge=0)  # latinum incentive per head hired
    recruit_severance: int = Field(default=50, ge=0)  # paid out when a recruit is released
    suit_resale_frac: float = Field(default=0.5, ge=0.0, le=1.0)  # refund when a suit is sold
    missile_price: int = Field(default=400, ge=0)  # latinum per ground missile


class GwGarrisonEconomy(BaseModel):
    """Persistent planetary ground-garrison economy (GW plan D11, GW-WP09).

    Three independent rails feed `Planet.garrison_infantry`/`garrison_armor`:
    big-bang seeding (once, at generation), automatic militia recovery (every
    production tick, ownership-independent), and colonist-allocation training
    (every tick, owner-only, equipment-gated). `ReinforceGarrison` (GW-WP09/D15)
    is the fourth, ship-side, rail — its 1:1 recruit+suit → infantry conversion
    needs no config knob here.
    """

    model_config = _FROZEN

    # --- colonist-allocation training (produce(), owner-only) ---
    train_yield: float = Field(default=0.4, ge=0.0)  # infantry minted per (output × garrison_allocation)
    train_equipment_cost: int = Field(default=3, ge=0)  # equipment consumed per infantry unit trained

    # --- automatic militia baseline recovery (cron, ownership-independent) ---
    militia_recovery_frac: float = Field(default=0.01, ge=0.0, le=1.0)  # infantry: population-fraction/day
    militia_armor_recovery_frac: float = Field(default=0.003, ge=0.0, le=1.0)  # armor: same shape, slower
    armor_recovery_min_citadel_level: int = Field(default=2, ge=0)  # an unfortified world fields/regrows none

    # --- shared ceiling ---
    cap_frac: float = Field(default=0.35, gt=0.0, le=1.0)  # garrison_infantry ceiling, as a fraction of colonist_capacity

    # --- big-bang seeding (edge/bigbang/inhabitants.py) ---
    seed_infantry_frac_min: float = Field(default=0.02, ge=0.0)
    seed_infantry_frac_max: float = Field(default=0.12, ge=0.0)
    seed_hostility_mult: float = Field(default=1.6, ge=1.0)  # a below-amity species defends harder
    seed_alliance_mult: float = Field(default=1.3, ge=1.0)  # a bloc-held world defends harder than unaligned
    seed_band_mult: dict[str, float] = Field(default_factory=dict)  # distance band → seeding multiplier
    seed_armor_min_citadel_level: int = Field(default=2, ge=0)  # matches citadels.gun_min_level by convention
    seed_armor_frac: float = Field(default=0.25, ge=0.0, le=1.0)  # armor seeded as this fraction of seeded infantry

    @model_validator(mode="after")
    def _check(self) -> GwGarrisonEconomy:
        if self.seed_infantry_frac_max < self.seed_infantry_frac_min:
            raise ValueError("groundwar.garrison_economy seed_infantry_frac_max must be ≥ _min")
        for band, mult in self.seed_band_mult.items():
            if mult <= 0.0:
                raise ValueError(f"groundwar.garrison_economy seed_band_mult[{band}] must be > 0")
        return self


class GwAssaultDifficulty(BaseModel):
    """Live-state assault difficulty derivation (GW-WP09). The standalone-only
    `GwDifficulty` preset table it once existed alongside was retired in GW-WP14, when
    the `edge.groundwar` app was retargeted onto this same live-state derivation; this
    block is read only by `edge.core.groundwar.assault.derive_difficulty`.
    """

    model_config = _FROZEN

    min_cities: int = Field(default=1, gt=0)
    max_cities: int = Field(default=4, ge=1)
    population_per_extra_city: int = Field(default=4000, gt=0)  # scaled capacity per city beyond min_cities
    surrender_threshold_base: int = Field(default=30, gt=0)
    surrender_threshold_per_citadel_level: int = Field(default=8, ge=0)
    hostility_mult: float = Field(default=1.4, ge=1.0)  # below-amity species → larger battlefield
    band_mult: dict[str, float] = Field(default_factory=dict)  # distance band → capacity-score multiplier
    alliance_owned_mult: float = Field(default=1.2, ge=1.0)  # a bloc-held world reads slightly harder
    had_gun_mult: float = Field(default=1.15, ge=1.0)  # a world that built+lost a gun fights harder (GW plan D11)

    @model_validator(mode="after")
    def _check(self) -> GwAssaultDifficulty:
        if self.max_cities < self.min_cities:
            raise ValueError("groundwar.assault_difficulty max_cities must be ≥ min_cities")
        return self


class GwSettlement(BaseModel):
    """Strategic aftermath of a tactical assault (GW-WP11, D2/D8/D13/D14).

    These values deliberately sit beside the tactical balance rather than in the
    reducer: they govern how quickly a battered polity recovers, how long a
    protectorate must exist before annexation, and how civilian harm feeds the
    existing reputation/alignment rails.
    """

    model_config = _FROZEN

    resolve_recovery_per_day: int = Field(default=8, ge=0)
    protectorate_min_days: int = Field(default=5, ge=0)
    annex_resolve_threshold: int = Field(default=80, ge=0)
    protectorate_production_share: float = Field(default=0.1, ge=0.0, le=1.0)
    civilian_loss_per_structure: float = Field(default=0.02, ge=0.0, le=1.0)
    civilian_alignment_penalty: int = Field(default=3, ge=0)
    annex_alignment_penalty: int = Field(default=15, ge=0)
    defenders_per_consequence: int = Field(default=10, gt=0)


class GwBattlefield(BaseModel):
    """Assault battlefield dimensions."""

    model_config = _FROZEN

    width: int = Field(ge=2)
    height: int = Field(ge=2)


class GwCloudCity(BaseModel):
    """Station-interior generation tuning (GW-WP15; the assault gate stays off
    until GW-WP16). `districts_base`/`districts_per_size` size the room count
    against `Planet.cloud_city_size` (1..`planets.cloud_city_max_size`);
    `locked_door_frac` and `lift_pairs` shape the connectivity graph
    (`edge.core.groundwar.interior`); `hazard_frac`/`cover_frac` sprinkle inert
    `vacuum`/`fire`/`electrical`/`cover_strut` cells onto room floors.
    """

    model_config = _FROZEN

    width: int = Field(default=60, ge=2)
    height: int = Field(default=32, ge=2)
    districts_base: int = Field(default=3, ge=1)
    districts_per_size: int = Field(default=2, ge=0)
    locked_door_frac: float = Field(default=0.35, ge=0.0, le=1.0)
    lift_pairs: int = Field(default=2, ge=0)
    hazard_frac: float = Field(default=0.03, ge=0.0, le=1.0)
    cover_frac: float = Field(default=0.08, ge=0.0, le=1.0)


class GwPlatoon(BaseModel):
    """Drop-squad budget and size caps."""

    model_config = _FROZEN

    latinum: int = Field(ge=0)  # latinum available to outfit the drop
    max_troopers: int = Field(gt=0)
    actions_per_turn: int = Field(default=2, gt=0)


class GroundwarConfig(BaseModel):
    """Ground-operations balance (survey + assault), one YAML source of truth.

    Field names mirror `config/groundwar_default.yaml`. The flattened accessors
    (`width`, `height`, `latinum_budget`, `max_troopers`, `actions_per_turn`)
    match how `edge.groundwar` reads the config, so promoting the standalone app
    onto this schema needs no call-site churn.
    """

    model_config = _FROZEN

    battlefield: GwBattlefield
    pressure: GwPressure
    resolve: GwResolve
    platoon: GwPlatoon
    suits: dict[str, GwSuit]
    defenses: GwDefenses
    garrison: GwGarrison
    terrain: dict[str, GwTerrain]
    expedition: GwExpedition
    ground_force: GwGroundForce = GwGroundForce()
    garrison_economy: GwGarrisonEconomy = GwGarrisonEconomy()
    assault_difficulty: GwAssaultDifficulty = GwAssaultDifficulty()
    settlement: GwSettlement = GwSettlement()
    cloud_city: GwCloudCity = GwCloudCity()
    # GW-WP16 migration gate (GW plan "Cloud Cities retain a separate gate"):
    # stays False until the station-interior assault path (generation, tactics,
    # settlement, remote/UI parity) is proven — ground_access keeps routing every
    # Cloud City OrbitalOnly while it is off, regardless of standing.
    cloud_city_assault_enabled: bool = False

    @property
    def width(self) -> int:
        return self.battlefield.width

    @property
    def height(self) -> int:
        return self.battlefield.height

    @property
    def latinum_budget(self) -> int:
        return self.platoon.latinum

    @property
    def max_troopers(self) -> int:
        return self.platoon.max_troopers

    @property
    def actions_per_turn(self) -> int:
        return self.platoon.actions_per_turn

    @model_validator(mode="after")
    def _check(self) -> GroundwarConfig:
        if not self.suits:
            raise ValueError("groundwar.suits must define at least one suit")
        if not self.terrain:
            raise ValueError("groundwar.terrain must define at least one terrain class")
        # Every feature a landable biome can emit must have a terrain class, or a
        # generated cell would silently read as impassable (no move cost lookup).
        from edge.core.groundwar.interior import INTERIOR_FEATURES
        from edge.core.groundwar.terrain import BIOME_BANDS, LANDABLE_BIOMES

        needed = {name for pt in LANDABLE_BIOMES for _, name in BIOME_BANDS[pt].bands}
        missing = needed - set(self.terrain)
        if missing:
            raise ValueError(
                "groundwar.terrain missing classes for landable biome features: "
                f"{', '.join(sorted(missing))}"
            )
        missing_interior = set(INTERIOR_FEATURES) - set(self.terrain)
        if missing_interior:
            raise ValueError(
                "groundwar.terrain missing classes for Cloud City interior features: "
                f"{', '.join(sorted(missing_interior))}"
            )
        return self


class GameConfig(BaseModel):
    """Top-level config bundle, validated from the parsed YAML mapping."""

    model_config = _FROZEN

    config_version: int
    # Universe seed for a new game; null/omitted ⇒ a random seed is rolled at start
    # (the chosen seed is persisted, so the game still replays from (seed, command log)).
    seed: int | None = None
    turns_per_day: int = 250  # TWINSTR.DOC default (§9)
    scene: SceneArtConfig = SceneArtConfig()
    ui: UIConfig = UIConfig()
    ticker: TickerConfig = TickerConfig()
    economy: EconomyConfig = EconomyConfig()
    aliens: AliensConfig = AliensConfig()
    encounters: EncountersConfig = EncountersConfig()  # §10 encounter rolls (Phase 3, WP24)
    combat: CombatConfig = CombatConfig()  # §10 combat rounds (Phase 3, WP25)
    territory: TerritoryConfig = TerritoryConfig()  # §10 fighters/mines/beacons/hazards (WP41)
    weapons: dict[str, WeaponConfig] = Field(default_factory=dict)  # §4 weapon catalog
    bigbang: BigBangConfig = BigBangConfig()
    engine_room: EngineRoomConfig
    planets: PlanetsConfig
    starbase: StarbaseConfig | None = None  # WP4 orbital bases (None ⇒ none generated)
    discovery: DiscoveryConfig | None = None  # WP5 discoveries (None ⇒ none salted)
    genesis: GenesisConfig | None = None  # WP10 genesis torpedoes (None ⇒ not sold)
    citadels: CitadelConfig | None = None  # WP54 citadels (None ⇒ not buildable)
    tavern: TavernConfig = TavernConfig()  # WP58 rumors + noticeboard at the Stardock
    corp: CorpConfig = CorpConfig()  # WP66 player corporations (shared bank/assets + corp war)
    pvp: PvpConfig = PvpConfig()  # WP67 attacker-driven player-vs-player combat
    devices: dict[str, DeviceConfig] = Field(default_factory=dict)  # WP56 probes/interdictor/deflector
    roster: RosterConfig | None = None  # WP7 species roster (None ⇒ no aliens placed)
    names: NamesConfig | None = None  # Configurable name pools
    starter_ship: ShipClassConfig
    ship_classes: list[ShipClassConfig] = Field(default_factory=list)  # buyable hulls (Stardock)
    hardware: HardwareConfig
    groundwar: GroundwarConfig | None = None  # GW-WP02 ground operations (None ⇒ not configured)

    def ship_class(self, class_id: str) -> ShipClassConfig:
        """The ship-class config for `class_id` — the starter hull or a buyable one."""
        if class_id == self.starter_ship.id:
            return self.starter_ship
        for klass in self.ship_classes:
            if klass.id == class_id:
                return klass
        raise KeyError(f"unknown ship class {class_id!r}")

    @model_validator(mode="after")
    def _check_species_home_bands(self) -> GameConfig:
        """Every species' `home_band` hint must name a configured distance band (§6).

        The bands are defined in `bigbang.bands` (Hub/Frontier/Deep/Void by default),
        so this cross-check lives here rather than on `RosterConfig`, which is validated
        in isolation and can't see them. The **Core Space is not a band** — it is the
        innermost part of the Hub (sectors 1..N), and governing-alliance members are
        settled there by generation regardless of this hint — so `home_band: Core` is
        invalid and must be spelled as the band that contains the Core (`Hub`).
        """
        if self.roster is None:
            return self
        bands = {b.name for b in self.bigbang.active_bands()}  # names match across modes
        for sp in self.roster.species:
            if sp.home_band is not None and sp.home_band not in bands:
                raise ValueError(
                    f"species {sp.id!r} home_band {sp.home_band!r} is not a configured "
                    f"distance band (valid: {', '.join(sorted(bands))})"
                )
        return self

    @model_validator(mode="after")
    def _check_combat_refs(self) -> GameConfig:
        """§4/§10 reference integrity: every hull's `armament` ids resolve in the
        `weapons` catalog, and every roster species' `fleet` ids name known hulls
        (a violent pack spawn must always be able to arm itself, WP24/25)."""
        classes = [self.starter_ship, *self.ship_classes]
        for klass in classes:
            for weapon_id in klass.armament:
                if weapon_id not in self.weapons:
                    raise ValueError(f"ship class {klass.id!r} names unknown weapon {weapon_id!r}")
        if self.roster is not None:
            known = {k.id for k in classes}
            for sp in self.roster.species:
                for hull in (*sp.fleet, *sp.pack.escort):
                    if hull not in known:
                        raise ValueError(f"species {sp.id!r} fleet/escort names unknown hull {hull!r}")
        pod = self.combat.escape_pod_class
        if pod not in {k.id for k in classes}:
            raise ValueError(f"combat.escape_pod_class names unknown hull {pod!r}")
        return self

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GameConfig:
        """Validate an already-parsed mapping (e.g. from YAML) into a GameConfig."""
        return cls.model_validate(data)
