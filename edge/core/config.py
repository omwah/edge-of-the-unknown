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
    # Where the player's ship starts: "stardock" (at the StarDock — no routing needed),
    # "random" (a seeded random sector), or a specific sector id. The shortest path from
    # the start to the StarDock opens pre-explored so the opening signpost stays actionable.
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
    descent_turn_cost: int = 3        # turns to descend to a planet surface (§7, WP6)
    explore_turn_cost: int = 1        # turns to reveal one surface site (§7, WP6)
    surface_hidden_min_rank: int = 3  # surface sites of this rarity rank+ need a sensor sweep
    black_hole_gravity_warp: bool = False  # Phase-3 seam; inert in Phase 2
    black_hole_warp_turn_cost: int = 5


class GenesisConfig(BaseModel):
    """Genesis-torpedo device tunables (DESIGN §4.2, WP10).

    A Genesis torpedo is bought at StarDock for `price` latinum and deployed on an
    **unowned** planet of an `eligible_types` kind (the dead worlds — barren / belts /
    gas giants), transforming it into a `result_type` (a colonizable terrestrial) by
    re-rolling its yield/habitability from config. Deterministic, so it replays.
    """

    model_config = _FROZEN

    device_id: str = "genesis_torpedo"
    price: int = 15_000
    result_type: str = "terrestrial_warm"
    eligible_types: list[str] = Field(default_factory=list)


class AliensConfig(BaseModel):
    """Disposition thresholds + escape floor for the alien system (DESIGN §6, §10).

    Effective disposition (base + the player's attitude offset, clamped 0–1) falls in
    a band named by these thresholds: < `hostility` is hostile, ≥ `amity` is friendly,
    the middle is neutral. Phase 2 places only friendly-band species; the thresholds
    are read now (`core.aliens`) and gate greeting-vs-violence in Phase 3.
    """

    model_config = _FROZEN

    hostility_threshold: float = 0.35
    amity_threshold: float = 0.65
    escape_floor: float = 0.10  # player escape chance never drops below this (§10)

    # Alien ship drift (WP16, §6.3): each species rolls `drift_move_chance` per firing
    # to warp to a uniformly-chosen legal adjacent sector. A quiet galaxy is chance 0
    # or `drift_enabled=False`. The cron cadence lives in `ticker.crons.alien_drift`.
    drift_enabled: bool = True
    drift_move_chance: float = Field(default=0.25, ge=0.0, le=1.0)


class AllianceConfig(BaseModel):
    """One alliance / rival bloc in the roster (DESIGN §6.3)."""

    model_config = _FROZEN

    id: int
    name: str
    banner: str = ""
    covets_core: bool = False  # may seize the Core in Phase 5 (authored hint, inert now)


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
    `CHOICE_ACTIONS` — farewell / trade / barter / accept_lead / attack; `attack` is
    Phase-3-gated), and a `when` predicate gating whether the reply is offered. Conversation
    *position* is not stored in core state: the reducer re-resolves the line for the active
    context and validates the chosen index, so a reply is reproducible from (seed, log).
    """

    model_config = _FROZEN

    text: str  # the player's reply label (templated with the node's placeholders)
    next_context: str | None = None  # context key to transition to (None ⇒ stay / act only)
    action: str | None = None  # a CHOICE_ACTIONS verb, or None for a pure transition
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
    attitude_gain_rate: float = 0.1
    attitude_loss_rate: float = 0.2
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
    subset_min: int = 6
    subset_max: int = 12
    # High-traffic Core hub: at least this many distinct Core-welcome species (governing
    # alliance members + unaligned neutrals) are staged at the StarDock so a brand-new
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
    floor_context: str = "greeting"
    floor_keys: list[str] = Field(default_factory=lambda: ["ask", "farewell"])

    def alliance(self, alliance_id: int) -> AllianceConfig | None:
        return next((a for a in self.alliances if a.id == alliance_id), None)

    def species_by_id(self, roster_id: str) -> SpeciesConfig | None:
        return next((s for s in self.species if s.id == roster_id), None)

    @model_validator(mode="after")
    def _check_reference_integrity(self) -> RosterConfig:
        """Dialogue/diplomacy reference integrity (§6, §13): ids and hooks resolve."""
        ids = {a.id for a in self.alliances}
        if self.core_governing_alliance_id not in ids:
            raise ValueError(
                f"core_governing_alliance_id {self.core_governing_alliance_id} is not an alliance"
            )
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

    planet: PlanetSpriteSize = PlanetSpriteSize()  # SectorView orbit-row planet
    planet_detail: PlanetSpriteSize = PlanetSpriteSize(max_height=14)  # PlanetScreen orbit view
    port: SpriteSize = SpriteSize(max_width=18, max_height=8)
    ship: SpriteSize = SpriteSize(max_width=16, max_height=6)
    max_ships_shown: int = Field(default=2, gt=0)  # sprites; extras list as text
    ship_face_inward_chance: float = Field(default=0.5, ge=0.0, le=1.0)


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
    warp_focus_default: Literal["first", "backtrack", "unexplored"] = "first"
    sidebar_width: int = Field(default=33, gt=0)
    sidebar_min_screen_width: int = Field(default=90, gt=0)
    surface_terrain_height: int = Field(default=12, gt=0)  # SurfaceScreen terrain panel height
    local_map_radius: int = Field(default=3, gt=0)  # Computer/Map ego-graph reach in warp hops
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
    alien_drift: int = Field(default=120, ge=1)         # every 2 minutes


class TickerConfig(BaseModel):
    """Engine tick-loop timing (§9).

    ``tick_seconds`` is the real-time pause between engine ticks.  Cron
    cadences are the intervals (in ticks) at which each job fires.
    """

    model_config = _FROZEN

    tick_seconds: float = Field(default=1.0, gt=0)
    crons: CronCadenceConfig = CronCadenceConfig()


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
    bigbang: BigBangConfig = BigBangConfig()
    engine_room: EngineRoomConfig
    planets: PlanetsConfig
    starbase: StarbaseConfig | None = None  # WP4 orbital bases (None ⇒ none generated)
    discovery: DiscoveryConfig | None = None  # WP5 discoveries (None ⇒ none salted)
    genesis: GenesisConfig | None = None  # WP10 genesis torpedoes (None ⇒ not sold)
    roster: RosterConfig | None = None  # WP7 species roster (None ⇒ no aliens placed)
    names: NamesConfig | None = None  # Configurable name pools
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
        bands = {b.name for b in self.bigbang.bands}
        for sp in self.roster.species:
            if sp.home_band is not None and sp.home_band not in bands:
                raise ValueError(
                    f"species {sp.id!r} home_band {sp.home_band!r} is not a configured "
                    f"distance band (valid: {', '.join(sorted(bands))})"
                )
        return self

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GameConfig:
        """Validate an already-parsed mapping (e.g. from YAML) into a GameConfig."""
        return cls.model_validate(data)
