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
    display_id: int = 0  # spatial id shown in the sector title (§5.1)


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
class ComputerDTO:
    pairs: list[TradePair]
    selected: str
    codex: list[CodexEntry] = field(default_factory=list)
    dossier: list[DossierEntry] = field(default_factory=list)
    ports: list[PortDirEntry] = field(default_factory=list)
    planets: list[PlanetDirEntry] = field(default_factory=list)
    leads: list[LeadDTO] = field(default_factory=list)


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


@dataclass(frozen=True)
class ContactVerbDTO:
    """One row of the alien-contact verb menu (§6.7), derived from species params.

    A disabled verb carries the `reason` it is greyed (e.g. "they refuse to trade").
    `kind` groups the row under the **Say** (dialogue) or **Do** (mechanical) heading;
    a "say" verb names the dialogue `context` it speaks and, for *Ask about…*, sets
    `needs_subject` so the TUI opens the subject picker (WP17). The dispatch metadata
    lets the screen drive the menu without hardcoding a verb→action map.
    """

    key: str
    label: str
    enabled: bool = True
    reason: str = ""
    kind: str = "do"  # "say" | "do"
    context: str = ""  # the dialogue context a "say" verb speaks ("" for "do" verbs)
    needs_subject: bool = False  # this "say" verb opens the subject picker (dossier_other)


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
    persona: str
    alliance: str
    standing: str  # "friendly" / "allied" / …
    band: str
    disposition_filled: int  # 0..5 effective-disposition bar
    base_disposition: float
    attitude: float
    effective: float
    opener: str  # the greeting line (WP8 dialogue)
    verbs: list[ContactVerbDTO]
    offers: list[TechOfferDTO]
    dossier: list[str]  # lines about other met species, in this species' voice
    subjects: list[tuple[int, str]] = field(default_factory=list)  # (id, name) of met others (WP17 Ask about…)
    intel_summary: str = ""  # the coordinate tip on offer (§6.7), or "" if none available
    # Authored player replies on the active node (§6.7 branching); empty ⇒ derived verb menu.
    choices: list[ContactChoiceDTO] = field(default_factory=list)
    # The always-present floor (§6.7): top-level verbs (Ask about… / Farewell / Leave) the screen
    # appends *after* authored `choices` on a branching top node, so a player can always ask
    # about others or exit even when the author didn't write those replies. Empty on plain nodes
    # (the derived menu already carries them) and on deeper `branch.*` nodes. Each floor verb the
    # grammar already covers (an authored reply with the same action/next_context) is dropped.
    floor_verbs: list[ContactVerbDTO] = field(default_factory=list)


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
