"""The player's ground force — recruits, suits, ordnance, loadouts (GW-WP08, D3).

Ground troops are **hired people in purchased equipment**, held on the ship as
persistent assets:

- `Ship.recruits` — people enlisted at a Stardock for a per-head incentive, exactly
  as colonists are recruited rather than bought (§4.2). They are never cargo.
- `Ship.suits` — powered armour bought at a Stardock, counted by suit-class id.
- `Ship.ground_missiles` — the shared heavy-ordnance magazine.

All three ride **passenger berths** (`Ship.passenger_capacity`), a third occupancy limit
distinct from cargo holds and colonist berths: a recruit takes a berth and so does a
suit, so a platoon can never be stowed by displacing trade goods or colonists. The
magazine is capped by what the owned suits can chamber, so ammunition cannot
accumulate off the books once the suits carrying it are gone (G8).

A **loadout** is the composer's answer to "who drops": suit-class id → count. It is
valid only when every deployed recruit gets an owned suit of that class and the
platoon fits the config's `max_troopers` cap — checked here, recomputed by the
reducer, and projected as affordances so the UI offers only what can actually be
funded and deployed. `apply_casualties` is the D8/D15 return trip: a dead trooper
costs both the recruit *and* the suit they wore, atomically.

Leaf pure module: imports only `edge.core.config` / `edge.core.models`, never
`edge.core.rules`, `edge.server`, or `edge.tui`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from edge.core.config import GameConfig, GroundwarConfig, GwSuit
from edge.core.models import Ship


class GroundForceError(Exception):
    """A recruit/suit/ordnance/loadout rule was violated (surfaced to the player)."""


def groundwar_config(config: GameConfig) -> GroundwarConfig:
    """The ground-operations block, or a clear refusal when the game ships without one."""
    if config.groundwar is None:
        raise GroundForceError("this game has no ground-operations configuration")
    return config.groundwar


# --- occupancy -------------------------------------------------------------


def suits_total(ship: Ship) -> int:
    """Suits of every class carried."""
    return sum(ship.suits.values())


def berths_used(ship: Ship) -> int:
    """Passenger berths occupied — one per recruit, one per suit."""
    return ship.recruits + suits_total(ship)


def berths_free(ship: Ship) -> int:
    return max(0, ship.passenger_capacity - berths_used(ship))


def missile_capacity(ship: Ship, config: GameConfig) -> int:
    """Ground missiles the owned suits can chamber (the magazine ceiling)."""
    suits = groundwar_config(config).suits
    return sum(count * suits[key].missiles for key, count in ship.suits.items() if key in suits)


def suit_spec(config: GameConfig, suit_id: str) -> GwSuit:
    suit = groundwar_config(config).suits.get(suit_id)
    if suit is None:
        raise GroundForceError(f"no such suit class: {suit_id!r}")
    return suit


def resale_price(suit: GwSuit, config: GameConfig) -> int:
    """What the dock pays back for a used suit (a partial refund, never a profit)."""
    return int(suit.cost * groundwar_config(config).ground_force.suit_resale_frac)


# --- inventory deltas ------------------------------------------------------


def with_suits(ship: Ship, suit_id: str, delta: int) -> Mapping[str, int]:
    """`ship.suits` with `delta` of `suit_id` added (zero entries dropped)."""
    new = dict(ship.suits)
    count = new.get(suit_id, 0) + delta
    if count < 0:
        raise GroundForceError(f"no {suit_id} suits aboard to give up")
    if count:
        new[suit_id] = count
    else:
        new.pop(suit_id, None)
    return new


def clamp_magazine(ship: Ship, config: GameConfig) -> Ship:
    """Spill ground missiles the remaining suits can no longer chamber (G8).

    Selling or losing suits shrinks the magazine; the surplus is *lost*, never banked
    as free ordnance for a future platoon.
    """
    ceiling = missile_capacity(ship, config)
    if ship.ground_missiles <= ceiling:
        return ship
    return replace(ship, ground_missiles=ceiling)


# --- loadouts --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoadoutOption:
    """One row of the platoon composer, as an affordance the player can actually use."""

    suit_id: str
    label: str
    role: str
    cost: int
    owned: int  # suits of this class aboard
    deployable: int  # ... capped by the recruits and the platoon ceiling


#: Short role blurbs, keyed by suit class — presentation the composer shows beside
#: each row. Unknown classes simply carry no blurb.
ROLE_BLURBS: Mapping[str, str] = {
    "marauder": "line breaker",
    "scout": "eyes · jamming",
    "command": "aura · terms",
}


def loadout_options(ship: Ship, config: GameConfig) -> tuple[LoadoutOption, ...]:
    """The composer's rows for this ship: every suit class it owns, with real caps."""
    gw = groundwar_config(config)
    ceiling = min(ship.recruits, gw.max_troopers)
    rows = []
    for suit_id, suit in gw.suits.items():
        owned = ship.suits.get(suit_id, 0)
        rows.append(LoadoutOption(
            suit_id=suit_id, label=suit.label, role=ROLE_BLURBS.get(suit_id, ""),
            cost=suit.cost, owned=owned, deployable=min(owned, ceiling),
        ))
    return tuple(rows)


def validate_loadout(
    ship: Ship, loadout: Mapping[str, int], config: GameConfig
) -> Mapping[str, int]:
    """Normalize and check a drop loadout; raise `GroundForceError` on any violation.

    Every deployed recruit must be assigned an owned suit of the requested class
    (D3), the platoon must fit `groundwar.platoon.max_troopers`, and it must be
    non-empty. Returns the loadout with zero entries dropped.
    """
    gw = groundwar_config(config)
    clean: dict[str, int] = {}
    for suit_id, count in loadout.items():
        if count < 0:
            raise GroundForceError("a loadout cannot deploy a negative number of suits")
        if count == 0:
            continue
        if suit_id not in gw.suits:
            raise GroundForceError(f"no such suit class: {suit_id!r}")
        owned = ship.suits.get(suit_id, 0)
        if count > owned:
            raise GroundForceError(
                f"only {owned} {gw.suits[suit_id].label} suit(s) aboard, {count} requested"
            )
        clean[suit_id] = count
    total = sum(clean.values())
    if total == 0:
        raise GroundForceError("a drop needs at least one trooper")
    if total > ship.recruits:
        raise GroundForceError(
            f"only {ship.recruits} recruit(s) aboard to wear {total} suit(s)"
        )
    if total > gw.max_troopers:
        raise GroundForceError(f"a drop lands at most {gw.max_troopers} troopers")
    return clean


def apply_casualties(ship: Ship, losses: Mapping[str, int], config: GameConfig) -> Ship:
    """Remove dead troopers: each costs one recruit **and** the suit they wore (D8).

    Atomic — the recruit and their equipped suit go together, so a mission can never
    return more suits than people or bank the armour of the fallen.
    """
    new_ship = ship
    dead = 0
    for suit_id, count in losses.items():
        if count <= 0:
            continue
        dead += count
        new_ship = replace(new_ship, suits=with_suits(new_ship, suit_id, -count))
    if dead > new_ship.recruits:
        raise GroundForceError("more casualties than recruits aboard")
    new_ship = replace(new_ship, recruits=new_ship.recruits - dead)
    return clamp_magazine(new_ship, config)
