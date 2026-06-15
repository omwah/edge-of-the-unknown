"""Core domain entities (DESIGN §4) — the authoritative in-memory model.

Entities are **frozen** dataclasses: a state mutation replaces an entity with a
new instance rather than editing it in place (the event-sourced style — reducers
in `core.rules` return new entities + events, WP3). The mutable `UniverseState`
container holds these snapshots plus the seeded RNG and the runtime adjacency
map; it is the single owner of randomness, so any game is reproducible from
`(seed, command log)` (CLAUDE.md).

Phase 1 scope: the player ship carries **flat aspect scalars** (no engine-room
subsystems yet — that is Phase 2, §4.1); planets are navigational objects with a
type only (no production/ownership); aliens/alliances beyond a Federation stub
are deferred. See PHASE1_PLAN.md §2.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field

from edge.core.enums import Commodity, PortClass, PortMode


@dataclass(frozen=True, slots=True)
class Game:
    """Top-level game record (DESIGN §4)."""

    id: int
    seed: int
    config_version: int
    created_at: str  # ISO timestamp; set by the caller (no clock reads in core)
    day_number: int = 1
    core_governing_alliance_id: int | None = None


@dataclass(frozen=True, slots=True)
class Region:
    """A named cluster from generation (DESIGN §4/§5)."""

    id: int
    name: str
    controlling_species_id: int | None = None
    controlling_alliance_id: int | None = None


@dataclass(frozen=True, slots=True)
class Sector:
    """A node in the warp graph (DESIGN §4). `warps_out` are sector ids."""

    id: int
    region_id: int
    warps_out: tuple[int, ...]
    distance_band: str  # band name (config §5), e.g. "Hub" / "Frontier"
    is_galactic_core: bool = False  # in the protected Core Space (sectors 1–10)
    beacon_text: str | None = None


@dataclass(frozen=True, slots=True)
class PortCommodity:
    """One commodity line at a port: stock + the pricing inputs (DESIGN §8)."""

    commodity: Commodity
    mode: PortMode  # BUY (port buys from player) / SELL (port sells to player)
    stock: int
    capacity: int  # = size * 1000 (§8)
    base: float  # undisturbed per-unit price (config)
    delta: float  # price swing with stock (config)


@dataclass(frozen=True, slots=True)
class Port:
    """A trading port (DESIGN §4). `latinum` is a soft accounting figure in P1 (§8)."""

    id: int
    sector_id: int
    name: str
    klass: PortClass
    size: int
    commodities: tuple[PortCommodity, ...]
    latinum: int = 0

    def line(self, commodity: Commodity) -> PortCommodity | None:
        return next((c for c in self.commodities if c.commodity is commodity), None)


@dataclass(frozen=True, slots=True)
class Planet:
    """A planet (DESIGN §4.2). Phase 1: a navigational object with a type only."""

    id: int
    sector_id: int
    name: str
    planet_type: str


@dataclass(frozen=True, slots=True)
class Ship:
    """A ship hull (DESIGN §4). Phase 1: flat aspect scalars, no subsystems (§4.1)."""

    id: int
    type_id: str  # ship-class id (config), e.g. "trailblazer"
    name: str
    owner_player_id: int | None
    sector_id: int
    holds_total: int
    cargo: Mapping[Commodity, int] = field(default_factory=dict)
    hull_current: int = 0
    hull_max: int = 0
    shields: int = 0
    warp_speed: int = 0
    combat_speed: int = 0
    cloak_rating: int = 0
    sensor_rating: int = 0
    missiles: int = 0
    repair_kits: int = 0
    turns_per_warp: int = 1

    @property
    def holds_used(self) -> int:
        return sum(self.cargo.values())

    @property
    def holds_free(self) -> int:
        return self.holds_total - self.holds_used


@dataclass(frozen=True, slots=True)
class Player:
    """The player (DESIGN §4). Starts as a member of the Core's governing alliance."""

    id: int
    name: str
    ship_id: int
    latinum: int
    bank_balance: int = 0
    turns_remaining: int = 0
    alliance_id: int | None = None
    explored_sectors: frozenset[int] = frozenset()


@dataclass(frozen=True, slots=True)
class Alliance:
    """An alliance (DESIGN §4/§6.3). Phase 1 uses only a Federation stub."""

    id: int
    name: str


@dataclass
class UniverseState:
    """The authoritative mutable container: entities + the seeded RNG + adjacency.

    Not frozen — it owns the evolving `random.Random` and the entity maps. The
    entities it holds are immutable snapshots; mutation swaps a snapshot for a new
    one (reducers, WP3). `adjacency` is the runtime fast-lookup warp map (plain
    dicts per DESIGN §3), projected from the sectors' `warps_out`.
    """

    game: Game
    rng: random.Random
    regions: dict[int, Region] = field(default_factory=dict)
    sectors: dict[int, Sector] = field(default_factory=dict)
    ports: dict[int, Port] = field(default_factory=dict)
    planets: dict[int, Planet] = field(default_factory=dict)
    ships: dict[int, Ship] = field(default_factory=dict)
    players: dict[int, Player] = field(default_factory=dict)
    alliances: dict[int, Alliance] = field(default_factory=dict)
    adjacency: dict[int, tuple[int, ...]] = field(default_factory=dict)

    @classmethod
    def new(cls, game: Game) -> UniverseState:
        """A fresh universe seeded from the game's seed (RNG owned here, §3)."""
        return cls(game=game, rng=random.Random(game.seed))

    def rebuild_adjacency(self) -> None:
        """Project the runtime adjacency map from the sectors' warp lists."""
        self.adjacency = {s.id: s.warps_out for s in self.sectors.values()}

    def port_in_sector(self, sector_id: int) -> Port | None:
        return next((p for p in self.ports.values() if p.sector_id == sector_id), None)
