"""Battle-state model for the space-battle POC.

Plain mutable dataclasses over a coarse *placement-cell* grid (each cell renders
as several characters, so sprites are bigger than one glyph). Same determinism
contract as groundwar: all randomness flows through the seeded `random.Random`
owned by `Battle`, only `rules.py` mutates state, and the UI drains
`Battle.events` for its log/FX without ever writing.

Directions are octant indices 0..7 (E, NE, N, NW, W, SW, S, SE — y grows
downward, so NE is (+1, -1)); bearings and fighter headings use all eight, but
*ship* facings are restricted to the four cardinals (0/2/4/6 — diagonal hull
art at this scale was unreadable). A ship's velocity persists between turns
(vector-lite):
ships drift by their velocity at the start of their side's turn, and a thrust
action bends the vector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Literal

from edge.spacebattle.config import Quadrant, ShipClass, SpacebattleConfig

Side = Literal["player", "enemy"]
Outcome = Literal["victory", "defeat"]

# Octant index -> unit step. Order: E NE N NW W SW S SE (counterclockwise on
# screen, y down). `FACING_NAMES` pairs with it for the sidebar.
DIRS: tuple[tuple[int, int], ...] = (
    (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1))
FACING_NAMES: tuple[str, ...] = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")


@dataclass(slots=True)
class Ship:
    id: int
    side: Side
    cls: ShipClass
    name: str
    x: int
    y: int
    facing: int                      # octant 0..7
    vx: int = 0
    vy: int = 0
    hull: int = 0
    screens: dict[Quadrant, int] = field(default_factory=dict)
    down: set[str] = field(default_factory=set)   # knocked-out component names
    salvos: int = 0                  # missile salvos remaining
    wings_docked: int = 0
    mines: int = 0
    actions: int = 0
    drones: int = 0                  # recon probes carried
    lance: bool = False              # the player-only grav-lance refit
    lance_charge: int = 0            # turns until the capacitor is ready (0 = ready)
    hull_hit: bool = False           # hull damage since last own turn (blocks screen regen)

    @property
    def alive(self) -> bool:
        return self.hull > 0

    @property
    def turn_taken(self) -> bool:
        return self.actions <= 0

    @property
    def cells(self) -> tuple[tuple[int, int], ...]:
        """Every board cell of the piece's footprint (anchored on the centre).
        Ships are one cell; a starbase spans a `cls.size`-square."""
        r = self.cls.size // 2
        if r == 0:
            return ((self.x, self.y),)
        return tuple((self.x + dx, self.y + dy)
                     for dy in range(-r, r + 1) for dx in range(-r, r + 1))

    @property
    def reactor_ok(self) -> bool:
        """Station power: the §4.2 fusion-reactor keystone is still online.
        Knocking it out is how a starbase is *taken* rather than razed."""
        return "fusion_reactor" not in self.down

    @property
    def speed(self) -> int:
        return max(abs(self.vx), abs(self.vy))

    # component effects ------------------------------------------------------

    @property
    def gun_ok(self) -> bool:
        return "main_gun" not in self.down

    @property
    def launcher_ok(self) -> bool:
        return "launcher" not in self.down

    @property
    def thrust_rating(self) -> int:
        return max(1, self.cls.thrust - (1 if "drive" in self.down else 0))

    @property
    def max_speed(self) -> int:
        return max(1, self.cls.max_speed - (1 if "drive" in self.down else 0))

    @property
    def sensor_range(self) -> int:
        return self.cls.sensor_range // 2 if "sensors" in self.down else self.cls.sensor_range


@dataclass(slots=True)
class FighterWing:
    id: int
    side: Side
    x: int
    y: int
    strength: int          # craft remaining
    endurance: int         # turns of fuel left off the rack
    carrier_id: int        # ship it launched from (recovery target)
    facing: int = 0        # cosmetic — points where it last moved/shot
    actions: int = 0

    @property
    def alive(self) -> bool:
        return self.strength > 0

    @property
    def turn_taken(self) -> bool:
        return self.actions <= 0


@dataclass(slots=True)
class Rock:
    """One cell of rocky debris (belt scenarios). Blocks fire lines and wings;
    destroys salvos that fly onto it; pulverized when a hull rams it."""

    id: int
    x: int
    y: int


@dataclass(slots=True)
class Debris:
    """One cell of drifting wreckage (graveyard scenarios). Blocks fire lines
    and stationing like rock and shreds salvos — but a hull that drifts onto it
    smashes *through*: a lighter impact, vector kept, the wreckage destroyed."""

    id: int
    x: int
    y: int


@dataclass(slots=True)
class Mine:
    id: int
    side: Side
    x: int
    y: int
    revealed: bool = False   # enemy mines start hidden until sensors find them


@dataclass(slots=True)
class Salvo:
    """A missile salvo in flight — a board object chasing its target ship."""

    id: int
    side: Side
    x: int
    y: int
    target_id: int
    count: int
    damage: int
    speed: int
    endurance: int
    accuracy: float


@dataclass(slots=True)
class Event:
    """One log/FX entry drained by the UI after each rules call."""

    kind: str        # "gun" | "hit" | "miss" | "salvo" | "knockout" | "destroyed" | ...
    text: str
    x: int = -1      # placement cell for FX flashes (-1 = no location)
    y: int = -1
    friendly: bool = True


@dataclass(slots=True)
class Battle:
    config: SpacebattleConfig
    rng: Random
    seed: int
    scenario_key: str
    ships: list[Ship] = field(default_factory=list)
    wings: list[FighterWing] = field(default_factory=list)
    mines: list[Mine] = field(default_factory=list)
    salvos: list[Salvo] = field(default_factory=list)
    rocks: dict[tuple[int, int], Rock] = field(default_factory=dict)
    debris: dict[tuple[int, int], Debris] = field(default_factory=dict)
    turn: int = 1
    deployed: bool = False           # pre-battle placement finished
    outcome: Outcome | None = None
    events: list[Event] = field(default_factory=list)
    _next_id: int = 1

    def next_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    # --- convenience reads (no mutation) ---------------------------------

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.config.width and 0 <= y < self.config.height

    def ship_at(self, x: int, y: int) -> Ship | None:
        for s in self.ships:
            if s.alive and (x, y) in s.cells:
                return s
        return None

    def wing_at(self, x: int, y: int) -> FighterWing | None:
        for w in self.wings:
            if w.alive and w.x == x and w.y == y:
                return w
        return None

    def salvo_at(self, x: int, y: int) -> Salvo | None:
        for s in self.salvos:
            if s.count > 0 and s.x == x and s.y == y:
                return s
        return None

    def mine_at(self, x: int, y: int, side: Side | None = None) -> Mine | None:
        for m in self.mines:
            if m.x == x and m.y == y and (side is None or m.side == side):
                return m
        return None

    def ship(self, sid: int) -> Ship | None:
        for s in self.ships:
            if s.id == sid:
                return s
        return None

    def fleet(self, side: Side) -> list[Ship]:
        return [s for s in self.ships if s.alive and s.side == side]

    def side_wings(self, side: Side) -> list[FighterWing]:
        return [w for w in self.wings if w.alive and w.side == side]

    def rock_at(self, x: int, y: int) -> Rock | None:
        return self.rocks.get((x, y))

    def debris_at(self, x: int, y: int) -> Debris | None:
        return self.debris.get((x, y))

    def cell_occupied(self, x: int, y: int) -> bool:
        """A ship (any footprint cell), wing, rock, or wreckage sits here — one
        piece per cell; nothing stations itself inside rubble."""
        return self.ship_at(x, y) is not None or self.wing_at(x, y) is not None \
            or (x, y) in self.rocks or (x, y) in self.debris

    def log(self, kind: str, text: str, x: int = -1, y: int = -1,
            friendly: bool = True) -> None:
        self.events.append(Event(kind, text, x, y, friendly))
