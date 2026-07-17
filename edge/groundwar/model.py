"""Battle-state model for the ground-war POC.

Plain mutable dataclasses (this is a self-contained scenario, not the replayed core
game), but with the same determinism contract: all randomness flows through the
seeded `random.Random` owned by `Battle`, and only `rules.py` mutates state. The
UI reads state and drains `Battle.events` for its log/FX; it never writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Literal

from edge.groundwar.config import GroundwarConfig, SuitClass

Vec = tuple[int, int]

StructureKind = Literal[
    "wall", "gate", "turret", "aa", "sensor", "citadel_gun",
    "building_military", "building_civilian",
]

Outcome = Literal["surrender", "retrieval", "casualties", "wiped"]


@dataclass(slots=True)
class Structure:
    id: int
    kind: StructureKind
    x: int
    y: int
    city_id: int
    hp: int
    hp_max: int

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass(slots=True)
class Trooper:
    id: int
    suit: SuitClass
    name: str
    x: int
    y: int
    hp: int
    missiles: int
    jump_charges: int
    mp: int = 0            # walk range per move action
    actions: int = 0       # actions left this turn — any mix of move/jump/fire/broadcast
    fired: bool = False    # attacked this turn (keeps you lit for detection)
    detected: bool = False

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def turn_taken(self) -> bool:
        """Every action spent — nothing left to do this turn."""
        return self.actions <= 0


@dataclass(slots=True)
class GarrisonUnit:
    id: int
    kind: Literal["infantry", "armor"]
    x: int
    y: int
    hp: int
    hp_max: int
    city_id: int

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass(slots=True)
class City:
    id: int
    name: str
    cx: int
    cy: int
    x0: int
    y0: int
    x1: int
    y1: int
    is_citadel: bool = False
    citadel_level: int = 0
    broadcast_done: bool = False
    cowed_scored: bool = False  # the one-time city_cowed resolve event fired


@dataclass(slots=True)
class Event:
    """One log/FX entry drained by the UI after each rules call."""

    kind: str        # "shot" | "hit" | "miss" | "destroyed" | "resolve" | "info" | ...
    text: str
    x: int = -1      # battlefield cell for FX flashes (-1 = no location)
    y: int = -1
    friendly: bool = True  # colors the log line


@dataclass(slots=True)
class Battle:
    config: GroundwarConfig
    rng: Random
    seed: int
    planet_type: str
    difficulty_key: str
    surrender_threshold: int
    garrison_mult: float
    # terrain
    feature: list[list[str]]                 # gameplay feature name per cell
    art: list[list[tuple[str, str, str]]]    # (char, fg, bg) per cell, pure backdrop
    # pieces
    cities: list[City] = field(default_factory=list)
    structures: dict[int, Structure] = field(default_factory=dict)
    struct_at: dict[Vec, int] = field(default_factory=dict)
    troopers: list[Trooper] = field(default_factory=list)
    garrison: dict[int, GarrisonUnit] = field(default_factory=dict)
    # progress
    turn: int = 1
    resolve: float = 100.0
    dropped: bool = False
    initial_strength: int = 0
    outcome: Outcome | None = None
    events: list[Event] = field(default_factory=list)
    _next_id: int = 1

    def next_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    # --- convenience reads (no mutation) ---------------------------------

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.config.width and 0 <= y < self.config.height

    def structure_at(self, x: int, y: int) -> Structure | None:
        sid = self.struct_at.get((x, y))
        return self.structures[sid] if sid is not None else None

    def trooper_at(self, x: int, y: int) -> Trooper | None:
        for t in self.troopers:
            if t.alive and t.x == x and t.y == y:
                return t
        return None

    def garrison_at(self, x: int, y: int) -> GarrisonUnit | None:
        for g in self.garrison.values():
            if g.alive and g.x == x and g.y == y:
                return g
        return None

    def live_troopers(self) -> list[Trooper]:
        return [t for t in self.troopers if t.alive]

    def city_structures(self, city_id: int, *kinds: StructureKind) -> list[Structure]:
        return [s for s in self.structures.values()
                if s.city_id == city_id and s.alive and (not kinds or s.kind in kinds)]

    def city_garrison(self, city_id: int) -> list[GarrisonUnit]:
        return [g for g in self.garrison.values() if g.alive and g.city_id == city_id]

    def city_cowed(self, city: City) -> bool:
        """Every active defense of this city silenced — guns, AA, and fielded garrison."""
        return not self.city_structures(city.id, "turret", "aa", "citadel_gun") \
            and not self.city_garrison(city.id)

    def casualties(self) -> int:
        return sum(1 for t in self.troopers if not t.alive)

    def log(self, kind: str, text: str, x: int = -1, y: int = -1, friendly: bool = True) -> None:
        self.events.append(Event(kind, text, x, y, friendly))
