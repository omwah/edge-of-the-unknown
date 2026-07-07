"""Public projection shapes — the fog-of-war view the TUI consumes (DESIGN §3).

These are the read-only DTOs that `to_public(context)` will emit at the server
boundary (WP6); the TUI reads *only* these, never the core models. They are
deliberately **structurally identical** to today's `edge/tui/dummy.py` fixtures,
which are the de-facto contract — so when the real service lands, `dummy.py` is
refactored to re-export these and the widget code is untouched (WP8).

Scope: Phase-1 screens only (Game / Port / StarDock-commodities / Computer /
Map). DTOs use primitive types (str modes/names), not core enums — the
projection converts enums to display strings. Phase 2–3 DTOs (surface, engine
room, contact, encounter, messages) stay in `dummy.py` until their engines land.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommodityLine:
    name: str
    mode: str  # "BUY" (port buys from you) | "SELL" (port sells to you)
    stock: int
    capacity: int
    price: int
    base_price: int
    player_qty: int

    @property
    def stock_ratio(self) -> float:
        return self.stock / self.capacity if self.capacity else 0.0

    @property
    def trend(self) -> str:
        if self.price > self.base_price:
            return "^"
        if self.price < self.base_price:
            return "v"
        return "="


# Every `*_id` below is the *internal* sector id (the click/message payload and
# key); the parallel `display_id` is the band-monotone spatial id the player sees
# (DESIGN §5.1). The TUI renders `display_id` and acts on `sector_id`.


@dataclass(frozen=True)
class PortDTO:
    name: str
    klass: str
    sector_id: int
    commodities: list[CommodityLine]
    display_id: int = 0  # spatial id of the port's sector (§5.1)
    archetype_id: str | None = None  # controlling species' palette, for the port sprite (§4)


@dataclass(frozen=True)
class SurfaceSite:
    """A surface-exploration site on a descended planet (UI_MOCKUPS.md §4, §7).

    `status` is "unexplored" / "explored" / "logged"; a still-hidden unexplored site
    is masked ("[?]" / "(unsurveyed)") until a sensor sweep reveals it. `salvageable`
    means it's revealed and uncollected, so `Salvage(discovery_id)` can log it.
    """

    marker: str  # "[1]" by slot, or "[?]" for an unsurveyed hidden site
    name: str
    rarity: str  # "Rare" … or "?" while masked
    status: str  # "unexplored" | "explored" | "logged"
    payload: list[str] = field(default_factory=list)  # detail lines (markup ok)
    discovery_id: int = 0
    salvageable: bool = False
    kind: str = ""  # DiscoveryKind value for entity art; "" while masked (fog of war)


@dataclass(frozen=True)
class SurfaceDTO:
    """The descended-planet view: terrain + the planet's surface sites (§7, WP6)."""

    planet: str
    descent_fuel: str  # "n/a" (movement costs turns, not fuel)
    terrain: list[str]  # top-down ASCII map rows (markup ok)
    sites: list[SurfaceSite] = field(default_factory=list)
    planet_id: int = 0
    explorable: bool = False  # at least one site can still be revealed (drives [E])
    terrain_blurb: str = ""  # planet-type flavor caption for the terrain panel title
    ptype: str = ""  # planet_type, so the TUI can render the art-engine terrain backdrop


@dataclass(frozen=True)
class HaggleQuote:
    """A read-only read on a counter-offer before the player commits it (§8).

    `fair` is the undisturbed §8 price; `mode` is the port's stance ("BUY"/"SELL");
    `label` is the likelihood the port would accept this `counter` — one of
    "accepted" / "likely" / "unlikely" / "insulting" / "exhausted". `attempts` /
    `max_attempts` drive the "Round N of M" display and gate the multi-round screen
    (WP13). Purely advisory: it issues no command and never touches the seeded RNG.
    """

    commodity: str
    fair: int
    counter: int
    mode: str
    label: str
    attempts: int = 0
    max_attempts: int = 0


@dataclass(frozen=True)
class WarpDTO:
    """One outbound warp — the single, information-rich warp affordance (§5.1, §11).

    Carries everything the sector grid renders: the gravity `arrow` (also the
    separator between the spatial id and the name), the region `label`, `band`, and
    content `codes` (port/planet) — all filled only once the target is explored
    (fog of war); an unexplored warp reads as `—` / `?` with no codes. `kind` drives
    the colour band; `sector_id` stays internal for the warp action.
    """

    sector_id: int
    arrow: str  # gravity glyph relative to the Core: "<<" closer / ">>" deeper / "--" level
    label: str | None = None  # region name (explored) | None (unexplored → "—")
    kind: str = "explored"  # "explored" | "unexplored" | "backtrack" — drives colour
    display_id: int = 0  # spatial id rendered on the warp button (§5.1)
    band: str = ""  # distance-band name (explored) | "?" (unexplored)
    codes: list[str] = field(default_factory=list)  # short content tokens, explored only
    bearing: float = 0.0  # direction to this warp from the current sector, radians (§11 nav rose);
    #                       from the seeded spatial embedding, 0.0 when no layout exists (fallback)

    @property
    def explored(self) -> bool:
        return self.kind != "unexplored"


@dataclass(frozen=True)
class SectorDiscovery:
    """One discovery visible in the current sector (§7, WP5).

    Obvious phenomena and sensor-detected hidden finds appear here; `salvageable`
    is True when it can be collected now (visible and not yet logged). `collected`
    marks one already in the codex. `discovery_id` is the Salvage payload.
    """

    discovery_id: int
    label: str  # "Drifting wreck · Rare"
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name
    salvageable: bool
    collected: bool = False
    warp_to: int | None = None  # one-way exit sector (wormholes only) — clicking warps here


@dataclass(frozen=True)
class SectorPlanetDTO:
    """A planet present in the current sector (§4.2).

    Carries the `planet_type` key directly so the art engine can pick the planet
    sprite without parsing it back out of a display string. `name` is the bare
    display name (the type is conveyed by the sprite, not appended to the label).
    """

    planet_id: int
    name: str  # display name only, e.g. "Terra Nova"
    ptype: str  # planet_type key (art subtype), e.g. "terrestrial_warm"


@dataclass(frozen=True)
class SectorPortDTO:
    """A port present in the current sector (§4).

    `klass` is the display label (e.g. "Class 4 (BBS)" / "StarDock"); `is_stardock`
    lets the docking flow branch without sniffing the name. `archetype_id` is the
    controlling species' palette (the sector's region controller), or None.
    """

    port_id: int
    name: str
    klass: str
    is_stardock: bool
    archetype_id: str | None = None


@dataclass(frozen=True)
class SectorShipDTO:
    """A vessel present in the current sector (§6).

    `role` is the art ship role (transport / fighter / warship / …) derived from the
    species' fleet, `archetype_id` is the vessel's own species palette, and
    `contact_id` is the species id to hail (folding in the old parallel `contact_ids`).
    """

    name: str
    role: str
    archetype_id: str | None = None
    contact_id: int | None = None


@dataclass(frozen=True)
class SectorAnomalyDTO:
    """The roaming Entity's always-on in-sector presence hint (DESIGN §7, WP35).

    Fog-safe: presence is shown to everyone (`label` never names the being), but opening
    contact is sensor-gated — `contactable` is True only when the ship's sensor rating
    resolves it (Legendary difficulty). `contact_id` is the species id to `Hail` once it
    can be reached. Computed live from the Entity's *current* sector (H2), never from
    `Player.detected`, so a drifting Entity's hint tracks it.
    """

    label: str
    contact_id: int
    contactable: bool


@dataclass(frozen=True)
class SectorDTO:
    region: str
    sector_id: int
    flavor: str
    beacon: str | None
    band: str = ""  # distance-band name, e.g. "Frontier" (for the "[id] Region (Band)" title)
    ports: list[SectorPortDTO] = field(default_factory=list)
    planets: list[SectorPlanetDTO] = field(default_factory=list)
    ships: list[SectorShipDTO] = field(default_factory=list)
    warps: list[WarpDTO] = field(default_factory=list)
    discoveries: list[SectorDiscovery] = field(default_factory=list)
    anomaly: SectorAnomalyDTO | None = None  # the roaming Entity's presence hint here (§7, WP35)
    display_id: int = 0  # spatial id shown in the sector title (§5.1)
    core_bearing: float = 0.0  # direction from here to the Core, radians (§11 nav-rose anchor);
    #                            0.0 when no spatial embedding exists (fallback to gravity axis)
    trail: list[int] = field(default_factory=list)  # recent route breadcrumb: spatial ids of the
    #                                                  last sectors travelled, oldest → newest (§11)


@dataclass(frozen=True)
class Aspect:
    label: str
    filled: int  # 0..10 for the bar
    note: str


@dataclass(frozen=True)
class Hold:
    label: str
    qty: int
    capacity: int


@dataclass(frozen=True)
class ShipDTO:
    name: str
    klass: str
    aspects: list[Aspect]
    integrity: str
    holds_used: int
    holds_total: int
    holds: list[Hold]
    gun: str
    missiles: int
    kits: int
    latinum: int
    band: str
    colonists: int
    colonist_capacity: int


@dataclass(frozen=True)
class TradePair:
    pair: str
    goods: str
    dist: int
    profit_rt: int  # round-trip profit
    per_turn: int  # profit per turn (the finder's score)
    buy_sector: int = -1  # internal id of the buy port's sector (WP14 route tie-in)
    sell_sector: int = -1  # internal id of the sell port's sector (WP14 route tie-in)


@dataclass(frozen=True)
class CodexEntry:
    """One logged discovery for the Computer's Codex tab (§7, §11, WP11)."""

    name: str  # "wreck · RARE"
    location: str  # "Sector 42" / "Planet 7 · site 2"
    rarity: str
    detail: str  # payload / lore fragment
    sector_id: int = -1  # internal id of the find's containing sector (WP14 route tie-in)


@dataclass(frozen=True)
class RouteHopDTO:
    """One traversed sector on a plotted route — what the player reads (§11, WP14)."""

    display_id: int  # spatial id (§5.1)
    label: str  # "(4) · port" / "(7) · planet @" / "(12)"
    one_way: bool  # no direct way back along this hop


@dataclass(frozen=True)
class RouteDTO:
    """A plotted route for the Computer's Route tab (§11, WP14).

    Read-only and spatial-id only (internal ids stay in core). `reason` is "" when
    reachable, else why not (fog, already here, out of turns). `hazards` is empty in
    Phase 2 — the Phase-3 encounter system fills it without reshaping the DTO.
    """

    origin_display: int
    dest_display: int
    hops: list[RouteHopDTO]
    turn_cost: int
    turns_remaining: int
    affordable: bool  # turns_remaining >= turn_cost
    reachable: bool
    reason: str
    hazards: list[str]
    summary: str  # "3 hops · 6 turns · 1 one-way"


@dataclass(frozen=True)
class DossierEntry:
    """One met species for the Computer's Dossier tab (§6.6, §11, WP11)."""

    species: str
    alliance: str
    band: str  # friendly / neutral / …
    standing: str
    disposition_filled: int  # 0..5 effective-disposition bar
    effective: float
    offers: str  # last-seen tech-offer summary
    last_seen: str = "—"  # spatial id of the sector where last encountered (§6)
    note: str = ""  # a self-description line in the species' own voice (WP8 dialogue)
    role: str = "none"  # alliance role: leader / member / aspirant / none (§6.3; re-derived live, WP51)


@dataclass(frozen=True)
class PortDirEntry:
    """One known port for the Computer's Ports tab (§11, WP15)."""

    port_id: int
    sector_id: int  # internal id (for the [P] route tie-in)
    sector_display: int  # spatial id (§5.1), what the player reads
    name: str
    klass: str  # PortClass label, e.g. "Class 1 (BBS)"
    buys: str  # "Org, Equ" — commodities the port buys
    sells: str  # "Fuel" — commodities the port sells
    dist: int  # hops from the player's current sector (BFS), -1 if unreachable


@dataclass(frozen=True)
class PlanetDirEntry:
    """One charted planet for the Computer's Planets tab (§11, §4.2)."""

    planet_id: int
    sector_id: int  # internal id (for the [P] route tie-in)
    sector_display: int  # spatial id (§5.1), what the player reads
    name: str
    ptype: str  # planet_type label, e.g. "terrestrial_warm"
    owner: str  # claim: "unowned" | alliance name | "you"
    colonists: int  # inhabitant count (settled colony / native population)
    species: str  # inhabiting species name, or "—"
    stores: str  # "Fuel 120  Org 40  Equ 0" — the trio in planetary stores
    dist: int  # hops from the player's current sector (BFS), -1 if unreachable


@dataclass(frozen=True)
class SeizureStatusDTO:
    """The Core-seizure checklist for the Computer's alliance panel (§6.3, WP50).

    Computed for the `covets_core` bloc the player has sworn to; its `ready` flag matches
    the petition reducer's gating exactly (view/reducer lockstep, H4). `*_done`/`*_needed`
    drive a checkbox list, and `ready` gates the petition action.
    """

    alliance_id: int
    alliance_name: str
    tasks_done: list[str]
    tasks_needed: list[str]
    tasks_met: bool
    bases_razed: int
    bases_needed: int
    bases_met: bool
    fee: int
    fee_affordable: bool
    consented: bool
    already_governs: bool
    ready: bool


@dataclass(frozen=True)
class ComputerDTO:
    pairs: list[TradePair]
    selected: str
    codex: list[CodexEntry] = field(default_factory=list)
    dossier: list[DossierEntry] = field(default_factory=list)
    ports: list[PortDirEntry] = field(default_factory=list)
    planets: list[PlanetDirEntry] = field(default_factory=list)
    leads: list[LeadDTO] = field(default_factory=list)
    seizure: SeizureStatusDTO | None = None  # WP50 Core-seizure checklist (if championing a bloc)


@dataclass(frozen=True)
class MarketOrderDTO:
    """One open order on the Computer's Market tab (§8, WP48)."""

    sector_display: int  # spatial id of the posting port
    port_name: str
    commodity: str  # short label, e.g. "Fuel"
    side: str  # "buys" | "sells" — the port's side of the order
    qty: int  # units still wanted/offered
    limit: int  # per-unit limit in slips (max bid / min ask)


@dataclass(frozen=True)
class MarketDTO:
    """The order-book market for the Computer's Market tab (§8, WP48).

    Fog-respecting: only explored ports' books appear (never a port outside the
    player's explored sectors). Purses are shown as-of-now (stale-by-design, like the
    Ports directory). `last_*` are the most recent `MarketSettled` aggregates from the
    log; `enabled` is False when the legacy regen economy is running (no book to show).
    """

    enabled: bool
    orders: list[MarketOrderDTO] = field(default_factory=list)
    purses: list[tuple[int, str, int]] = field(default_factory=list)  # (sector_display, name, purse)
    last_matches: int = 0
    last_volume: int = 0
    last_slips: int = 0
    summary: str = "no settlement yet"


@dataclass(frozen=True)
class MapNodeDTO:
    """A clickable sector node on the local map: its label's cell box in `rows`.

    `row`/`col0`/`col1` are character coordinates into the (stripped) `rows` grid —
    `col0` inclusive, `col1` exclusive — so the TUI can map a click to `sector_id`.
    """

    sector_id: int  # internal id — the route-plot target
    display_id: int  # spatial id shown in the label
    row: int
    col0: int
    col1: int
    # Internal ids this node warps to — the arrow-nav tie-breaker: when two candidate
    # sectors are equally close, the warp-linked one wins (§11 layout-aware nav). Empty
    # where the baker has no adjacency (the nav rose), which falls back to "prefer up".
    neighbors: frozenset[int] = frozenset()


@dataclass(frozen=True)
class LocalMapDTO:
    """The local sector ego-graph for the Computer → Map tab (§10, §11).

    `rows` are pre-baked Rich-markup lines of a node-and-edge graph centered on the
    player's sector (gravity columns, fog of war, optional route overlay); the TUI
    renders them verbatim. `legend` is the one-line glyph key. `nodes` carries each
    drawn sector's clickable cell box, so clicking a node plots a route to it.
    """

    you_sector: int
    you_band: str
    rows: list[str]
    legend: str = ""
    you_display: int = 0  # spatial id of the player's sector (§5.1)
    nodes: list[MapNodeDTO] = field(default_factory=list)


@dataclass(frozen=True)
class NavStripDTO:
    """The always-visible main-screen nav rose — the sole warp affordance (§11).

    A compact bearing-placed compass of the current sector's immediate neighbours,
    baked server-side into Rich-markup `rows` (open-diagonals style: `@` centred,
    ids in octant slots, a fixed `Core` anchor) the TUI renders verbatim. `nodes`
    carries each neighbour's clickable/focusable cell box (reusing the `MapNodeDTO`
    contract) so a click or keyboard-select warps there; `core_bearing` orients the
    anchor; `trail` is the recent-route breadcrumb (spatial ids, oldest → newest).
    """

    rows: list[str]
    legend: str = ""
    you_display: int = 0  # spatial id of the player's sector (§5.1)
    core_bearing: float = 0.0  # direction from here to the Core, radians (anchor placement)
    nodes: list[MapNodeDTO] = field(default_factory=list)
    trail: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class LogEntry:
    """One line in the messages/event log (UI_MOCKUPS.md §11, DESIGN §12)."""

    when: str  # short label, e.g. "" or "start"; markup-free
    text: str  # markup ok


@dataclass(frozen=True)
class MessagesDTO:
    """The messages & log view, projected from the durable event_log (§12)."""

    events: list[LogEntry]


@dataclass(frozen=True)
class Slot:
    """One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).

    `state` is "filled" | "empty" | "knocked" (knocked-out by combat — Phase 3);
    a filled slot names its `component`, and the structural `keystone` slot is marked.
    """

    state: str
    component: str = ""
    keystone: bool = False


@dataclass(frozen=True)
class Subsystem:
    """One subsystem panel: its derived aspect and its slot grid (§4.1)."""

    name: str  # "SPINDRIVE", "THRUSTERS", "SCREENS", "MAIN GUN"
    derived: str  # the aspect this subsystem drives, e.g. "warp 3"
    slots: list[Slot]


@dataclass(frozen=True)
class EngineRoomDTO:
    """The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)."""

    ship: str
    efficiency_bonus: str  # spindrive global combat buff, e.g. "+2 all"
    subsystems: list[Subsystem]
    kits: int
    on_hand: list[str]  # loose carried components, e.g. ["converter (I) x1"]


@dataclass(frozen=True)
class HardwareItem:
    """One row in the StarDock hardware emporium (UI_MOCKUPS.md §5, DESIGN §8)."""

    component: str
    tier: str
    price: int  # latinum
    affordable: bool


@dataclass(frozen=True)
class ShipyardItem:
    """One buyable hull in the StarDock shipyard, with a stat line (§8, §11)."""

    class_id: str
    name: str
    role: str
    price: int
    net_price: int  # price after the current hull's trade-in credit
    holds: int
    shields: int
    warp: int
    combat: int
    affordable: bool
    owned: bool  # the hull the player currently flies


@dataclass(frozen=True)
class StarDockDTO:
    """The StarDock services catalog (hardware + shipyard), fog-of-war scoped (§3)."""

    sector_display: int
    latinum: int
    hardware: list[HardwareItem]
    shipyard: list[ShipyardItem]


@dataclass(frozen=True)
class PlanetDTO:
    """The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)."""

    planet_id: int
    name: str
    ptype: str
    owner: str  # display: "unowned" | alliance name | "you"
    colonizable: bool
    claimable: bool  # unowned + colonizable (the player can settle it)
    owned_by_you: bool
    colonists: int
    habitability_cap: int
    stores: list[tuple[str, int]]  # (commodity label, quantity)
    allocation: list[tuple[str, int]]  # (commodity label, percent)
    ship_colonists: int  # colonists aboard the player's ship (for the Colonize affordance)
    ship_colonist_capacity: int
    ship_genesis: int = 0  # genesis torpedoes aboard (drives the Genesis affordance, WP10)
    genesis_eligible: bool = False  # this world can be re-formed by a genesis torpedo
    starbase: str | None = None  # WP4 display status: "operational" | "derelict — salvageable"
    starbase_id: int | None = None
    starbase_derelict: bool = False
    # Salvageable components on a derelict/own base: (subsystem value, slot index, label).
    salvage: list[tuple[str, int, str]] = field(default_factory=list)


@dataclass(frozen=True)
class GameState:
    """The game-screen view bundle (the public counterpart of `UniverseState`)."""

    turns: int
    max_turns: int
    ship: ShipDTO
    sector: SectorDTO
    nav: NavStripDTO | None = None  # the main-screen nav rose (§11); None for legacy fixtures


@dataclass(frozen=True)
class TechOfferDTO:
    """One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or barter."""

    index: int
    label: str  # "radiator (II)" / "sensors +1"
    tier: str
    mode: str  # "latinum" / "barter"
    price: int  # latinum price (0 for barter)
    barter_cost: str  # "1 Tier-III artifact" or ""
    available: bool
    reason: str = ""  # why unavailable (standing / latinum / artifact / hold)


@dataclass(frozen=True)
class ContactChoiceDTO:
    """One authored player reply on a branching dialogue node (§6.7 optional branching).

    Present only when the active node carries authored `choices`; the screen then renders
    these numbered replies in place of (and falling back to) the derived Say/Do menu.
    `index` is the canonical index in the node's choice list (what the `Converse` command
    carries), so hidden/ungated replies don't shift it. A disabled reply (e.g. a Phase-3
    `attack`) shows its `reason`; `action`/`next_context` let the screen drive navigation.
    """

    index: int
    text: str
    action: str = ""  # a CHOICE_ACTIONS verb, or "" for a pure transition
    next_context: str = ""  # the node it transitions to, or "" to stay / act only
    enabled: bool = True
    reason: str = ""


@dataclass(frozen=True)
class ContactDTO:
    """A peaceful alien contact screen (§6, §6.7, §11)."""

    species: str
    roster_id: str  # config roster key (e.g. "vesk") — selects the species portrait image
    persona: str
    alliance: str
    standing: str  # "friendly" / "allied" / …
    band: str
    disposition_filled: int  # 0..5 effective-disposition bar
    base_disposition: float
    attitude: float
    effective: float
    opener: str  # the greeting line (WP8 dialogue)
    offers: list[TechOfferDTO]
    dossier: list[str]  # lines about other met species, in this species' voice
    subjects: list[tuple[int, str]] = field(default_factory=list)  # (id, name) of met others (WP17 Ask about…)
    intel_summary: str = ""  # the coordinate tip on offer (§6.7), or "" if none available
    # The authored player replies on the active node (§6.7): the whole reply menu. Resolved via
    # the species → persona → generic fallback chain, so the `generic` persona's `start_context`
    # choices are the guaranteed baseline (validate_dialogue requires them). Each carries its own
    # gating (`enabled`/`reason`) ported from the old derived verb menu.
    choices: list[ContactChoiceDTO] = field(default_factory=list)
    portrait_variant: int = 0  # seeded-random variant for the species portrait image
    singular_entity: bool = False  # the roaming Entity (§7): art fills the slot, a nebular bloom
    #                                fallback when it has no portrait image (WP35)
    debug_context: str = ""
    debug_when: str = ""


@dataclass(frozen=True)
class LeadDTO:
    """A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row."""

    summary: str  # the human label logged at accept time
    source: str  # the species that shared it (display name)
    coords: int  # the destination's spatial display id
    distance: int  # fewest-hop route length from the player's ship (-1 if unreachable)
    turn_cost: int  # turns to fly the route
    reachable: bool
    sector_id: int = -1  # internal id of the tip's destination (WP14 route tie-in)
    at_origin: bool = True  # player is in the sector the tip was obtained in (full-graph plot)
    origin_coords: int = -1  # spatial display id of where the tip was obtained (return hint)
    stale: bool = False  # a roaming-Entity lead whose quarry has since moved on (§7, WP36)


@dataclass(frozen=True)
class EncounterFoeDTO:
    """One pack member on the encounter screen (§10, WP24/25)."""

    name: str
    hull_filled: int  # 0..10 bar
    hull_pct: int
    shields_pct: int
    firing_arc: str  # ahead / all_round / spinal
    alive: bool


@dataclass(frozen=True)
class EncounterDTO:
    """The live hostile encounter (§10, WP24/25) — the encounter screen's projection.

    Mirrors what the `CombatAction` reducer will resolve (H4 lockstep): the flee
    chance shown is computed by the same `combat.flee_chance` the reducer rolls.
    """

    species_id: int
    title: str  # "Quill Scout Marauder pack (x3)"
    species_name: str
    archetype_id: str
    band: str  # standing band label (hostile / wary / …)
    disposition_filled: int  # 0..5 bar
    round_no: int
    foes: list[EncounterFoeDTO]
    arc_hint: str  # firing-arc counter-play tip
    shields_pct: int  # fight-local shield pool
    hull_pct: int
    combat_line: str  # "Combat spd 4 (+1 eff)  vs intercept 0.6"
    integrity_flag: str  # knocked-out component note ("all nominal" when clean)
    flee_chance: int  # % (the same formula the reducer rolls)
    flee_floor: int  # % (the config escape floor)
    missiles: int
    repair_kits: int
    gun_online: bool
    # The pack's spoken combat beat (§6.7, WP31), rendered read-only in the species'
    # voice from the encounter's `speech_context`; "" when it carries none.
    speech: str = ""
