"""Immutable event facts — the durable rail (DESIGN §3, §12).

Reducers in `core.rules` return events describing what happened; the store
appends them to the `event_log` (assigning the monotonic id/tick) and the engine
tick loop consumes the same log. Events carry only their semantic payload — no
ids/timestamps, which the store layer assigns. Replaying the command log against
a fixed seed reproduces the same events (the save-integrity / golden-master rail).
"""

from __future__ import annotations

from dataclasses import dataclass

from edge.core.enums import Commodity, PortMode


@dataclass(frozen=True)
class Event:
    """Base class for all event facts."""


@dataclass(frozen=True)
class Warped(Event):
    player_id: int
    from_sector: int
    to_sector: int
    turn_cost: int


@dataclass(frozen=True)
class Docked(Event):
    player_id: int
    sector_id: int
    port_id: int


@dataclass(frozen=True)
class Traded(Event):
    player_id: int
    port_id: int
    commodity: Commodity
    mode: PortMode  # the port's mode for this commodity
    units: int
    unit_price: int
    total: int


@dataclass(frozen=True)
class Haggled(Event):
    player_id: int
    port_id: int
    commodity: Commodity
    status: str  # HaggleStatus value
    price: int | None


@dataclass(frozen=True)
class Banked(Event):
    player_id: int
    kind: str  # "deposit" | "withdraw" | "interest"
    amount: int
    balance: int  # resulting bank balance


@dataclass(frozen=True)
class ComponentPurchased(Event):
    player_id: int
    component: str  # Component value
    tier: str  # ComponentTier name
    cost: int


@dataclass(frozen=True)
class ShipPurchased(Event):
    player_id: int
    ship_class_id: str
    cost: int  # net latinum spent (price − trade-in credit)
    trade_in: int  # trade-in credit applied


@dataclass(frozen=True)
class ComponentInstalled(Event):
    player_id: int
    subsystem: str  # Subsystem value
    slot_index: int
    component: str  # Component value
    tier: str  # ComponentTier name (I/II/III)


@dataclass(frozen=True)
class ComponentRemoved(Event):
    player_id: int
    subsystem: str
    slot_index: int
    component: str
    tier: str


@dataclass(frozen=True)
class Repaired(Event):
    player_id: int
    subsystem: str
    slot_index: int


@dataclass(frozen=True)
class DiscoveryDetected(Event):
    """A hidden discovery a ship's sensors picked out on entering its sector (§7, WP5)."""

    player_id: int
    discovery_id: int
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name


@dataclass(frozen=True)
class Descended(Event):
    """The player landed on a planet surface to explore its sites (§7, WP6)."""

    player_id: int
    planet_id: int


@dataclass(frozen=True)
class SiteExplored(Event):
    """A surface site revealed by exploration/sensor sweep on descent (§7, WP6)."""

    player_id: int
    planet_id: int
    discovery_id: int
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name


@dataclass(frozen=True)
class DiscoveryCollected(Event):
    """A discovery logged into the codex, its payload taken aboard (§7, WP5)."""

    player_id: int
    discovery_id: int
    kind: str  # DiscoveryKind value
    rarity: str  # RarityTier name
    payload: str  # PayloadKind value (what was gained)


@dataclass(frozen=True)
class StarbaseSalvaged(Event):
    """A component cannibalized out of an orbital starbase into the ship (§4.2, WP4)."""

    player_id: int
    starbase_id: int
    subsystem: str  # Subsystem value
    slot_index: int
    component: str  # Component value
    tier: str  # ComponentTier name


@dataclass(frozen=True)
class ColonistsRecruited(Event):
    player_id: int
    source: str  # "stardock" | "emigration"
    count: int
    cost: int  # latinum incentive paid


@dataclass(frozen=True)
class Colonized(Event):
    player_id: int
    planet_id: int
    colonists: int


@dataclass(frozen=True)
class PlanetProduced(Event):
    planet_id: int
    owner_player_id: int  # only player-owned colonies announce (alliance output is silent)


@dataclass(frozen=True)
class ColonyGrew(Event):
    planet_id: int
    colonists: int  # new colonist count


@dataclass(frozen=True)
class TurnsReset(Event):
    player_id: int
    turns: int


@dataclass(frozen=True)
class StockRegenerated(Event):
    port_id: int
    commodity: Commodity
    new_stock: int
