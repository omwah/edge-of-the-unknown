"""Dev/testing cheat command (NOT part of normal play).

`DevPatch` is a single, generic mutation command the `edge.devtool` CLI appends
to a save's command log so a tester can reach hard-to-earn states quickly: pile
on latinum, grant high-tier components, claim worlds, teleport the hull. It is
deliberately isolated here (rather than in `core.rules`) to keep the cheat
surface obvious and out of the way of the real command set.

Because every mutation flows through the command log like any other command, it
**replays deterministically** — a cheated save reconstructs identically from
`(seed, command log)` (CLAUDE.md §3). The reducer intentionally bypasses the
economy faucet/sink invariants (that is the point of a cheat) but still validates
that targets exist and keeps counts non-negative, so it can't wedge the state.

Imports flow downward only (`models`/`enums`/`events`/`config`); `ReduceResult`
is imported lazily inside the reducer to avoid an import cycle with `core.rules`
(which imports this module for the `Command` union).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from edge.core.config import GameConfig
from edge.core.enums import Commodity, Component, ComponentTier
from edge.core.events import DevApplied
from edge.core.models import Ownership, Planet, Player, Ship, UniverseState

if TYPE_CHECKING:  # avoid a runtime cycle: rules imports this module for the union
    from edge.core.rules import ReduceResult


class DevPatchError(Exception):
    """A malformed or impossible dev patch (unknown target, missing entity, bad key)."""


@dataclass(frozen=True, slots=True)
class DevPatch:
    """A single dev/testing mutation (see module docstring).

    `op` selects the verb; `target` names the field/path; `value` is the numeric
    amount (set/add value, grant qty, cargo units, teleport sector id); `key` is a
    secondary selector ("accelerator:III", a commodity name, an artifact tier, a
    device id); `ref` is an entity id (planet id for `claim`).
    """

    op: str
    target: str
    value: int = 0
    key: str | None = None
    ref: int | None = None


# Player integer fields settable directly (clamped >= 0).
_PLAYER_INT_FIELDS = ("latinum", "bank_balance", "turns_remaining")
# Ship integer fields settable directly (field-specific clamps below).
_SHIP_INT_FIELDS = (
    "missiles", "repair_kits", "colonist_capacity", "colonists", "holds_total", "hull_current",
)
# Raw ship aspect overrides (an escape hatch). The first three are *derived* from
# the engine room, so a raw set is overwritten by the next engine-room action.
_DERIVED_ASPECTS = ("shields", "warp_speed", "combat_speed")
_RAW_ASPECTS = (*_DERIVED_ASPECTS, "cloak_rating", "sensor_rating")


def _resolve(op: str, current: int, value: int) -> int:
    """Apply a set/add op to a current integer."""
    if op == "set":
        return value
    if op == "add":
        return current + value
    raise DevPatchError(f"op {op!r} is not set/add for a numeric target")


def _parse_component(key: str | None) -> tuple[Component, ComponentTier]:
    """Parse a "<component>:<tier>" grant key (e.g. 'accelerator:III')."""
    if key is None or ":" not in key:
        raise DevPatchError("grant component needs key '<component>:<tier>' e.g. accelerator:III")
    name, _, tier = key.partition(":")
    try:
        return Component(name), ComponentTier[tier]
    except (ValueError, KeyError) as exc:
        raise DevPatchError(f"bad component key {key!r}") from exc


def apply_dev_patch(
    state: UniverseState, player_id: int, cmd: DevPatch, config: GameConfig
) -> ReduceResult:
    """Apply a `DevPatch`, returning the new entities + a `DevApplied` event.

    Dispatches on `(op, target)` over the whitelist; raises `DevPatchError` for an
    unknown verb/target, a missing entity, or a bad key. Bypasses economy
    invariants by design, but validates targets and keeps counts non-negative.
    """
    from edge.core.rules import ReduceResult  # local import: breaks the rules<->dev cycle

    player = state.players.get(player_id)
    if player is None:
        raise DevPatchError(f"no such player {player_id}")
    ship = state.ships[player.ship_id]
    op, target = cmd.op, cmd.target

    def done(detail: str, *, ship_: Ship | None = None, player_: Player | None = None,
             planets: tuple[Planet, ...] = ()) -> ReduceResult:
        return ReduceResult(
            events=(DevApplied(player_id, f"[dev] {detail}"),),
            players=(player_,) if player_ is not None else (),
            ships=(ship_,) if ship_ is not None else (),
            planets=planets,
        )

    # --- player integer fields ----------------------------------------------
    if target in _PLAYER_INT_FIELDS:
        new = max(0, _resolve(op, getattr(player, target), cmd.value))
        change: dict[str, Any] = {target: new}
        return done(f"{op} {target}={new}", player_=replace(player, **change))

    # --- ship integer fields (field-specific clamps) ------------------------
    if target.startswith("ship."):
        field = target[len("ship."):]
        if field not in _SHIP_INT_FIELDS:
            raise DevPatchError(f"unknown ship field {field!r}")
        new = _clamp_ship_field(ship, field, _resolve(op, getattr(ship, field), cmd.value))
        change = {field: new}
        return done(f"{op} ship.{field}={new}", ship_=replace(ship, **change))

    # --- raw aspect override (escape hatch) ---------------------------------
    if target.startswith("aspect."):
        field = target[len("aspect."):]
        if field not in _RAW_ASPECTS:
            raise DevPatchError(f"unknown aspect {field!r}")
        new = max(0, _resolve(op, getattr(ship, field), cmd.value))
        warn = " (reverts on next engine-room action)" if field in _DERIVED_ASPECTS else ""
        change = {field: new}
        return done(f"{op} aspect.{field}={new}{warn}", ship_=replace(ship, **change))

    # --- grants --------------------------------------------------------------
    if op == "grant" and target == "component":
        if cmd.value <= 0:
            raise DevPatchError("grant qty must be positive")
        key = _parse_component(cmd.key)
        comps = {**ship.components, key: ship.components.get(key, 0) + cmd.value}
        return done(f"grant {cmd.value}x {cmd.key} (loose)", ship_=replace(ship, components=comps))

    if op == "grant" and target == "artifact":
        if cmd.value <= 0:
            raise DevPatchError("grant qty must be positive")
        tier = cmd.key
        if tier is None or tier not in ComponentTier.__members__:
            raise DevPatchError("grant artifact needs key tier I/II/III")
        arts = {**player.artifacts, tier: player.artifacts.get(tier, 0) + cmd.value}
        return done(f"grant {cmd.value}x artifact ({tier})", player_=replace(player, artifacts=arts))

    if op == "grant" and target == "device":
        if cmd.value <= 0:
            raise DevPatchError("grant qty must be positive")
        if not cmd.key:
            raise DevPatchError("grant device needs key <device_id>")
        devices = {**ship.devices, cmd.key: ship.devices.get(cmd.key, 0) + cmd.value}
        return done(f"grant {cmd.value}x device {cmd.key}", ship_=replace(ship, devices=devices))

    # --- cargo ---------------------------------------------------------------
    if op == "cargo":
        try:
            commodity = Commodity(target)
        except ValueError as exc:
            raise DevPatchError(f"unknown commodity {target!r}") from exc
        if cmd.value < 0:
            raise DevPatchError("cargo units must be >= 0")
        cargo = {**ship.cargo, commodity: cmd.value}
        new_ship = replace(ship, cargo=cargo)
        if new_ship.holds_used > new_ship.holds_total:
            raise DevPatchError(
                f"cargo would need {new_ship.holds_used} holds but the hull has {new_ship.holds_total}"
            )
        return done(f"cargo {target}={cmd.value}", ship_=new_ship)

    # --- world: teleport / claim --------------------------------------------
    if op == "teleport":
        if cmd.value not in state.sectors:
            raise DevPatchError(f"no such sector {cmd.value}")
        new_ship = replace(ship, sector_id=cmd.value)
        new_player = replace(player, explored_sectors=player.explored_sectors | {cmd.value})
        return done(f"teleport to sector {cmd.value}", ship_=new_ship, player_=new_player)

    if op == "claim":
        if cmd.ref is None or cmd.ref not in state.planets:
            raise DevPatchError(f"no such planet {cmd.ref}")
        planet = state.planets[cmd.ref]
        new_planet = replace(planet, owner=Ownership("player", player_id))
        return done(f"claim planet {cmd.ref}", planets=(new_planet,))

    # --- governance: flip the Core's governing alliance (WP49) --------------
    if op == "flip_governor":
        from edge.core.governance import flip_core_governor

        new_gov = cmd.value if cmd.value else None  # value 0 ⇒ ungoverned Core
        if new_gov is not None and new_gov not in state.alliances:
            raise DevPatchError(f"no such alliance {new_gov}")
        delta = flip_core_governor(state, config, new_gov, cause="dev")
        return ReduceResult(
            events=(DevApplied(player_id, f"[dev] flip Core governor → {new_gov}"), *delta.events),
            game=delta.game, planets=delta.planets, starbases=delta.starbases,
            species=delta.species,
        )

    raise DevPatchError(f"unknown dev patch: op={op!r} target={target!r}")


def _clamp_ship_field(ship: Ship, field: str, new: int) -> int:
    """Field-specific validation for a ship integer set/add (raises on hard limits)."""
    if field == "colonists":
        if not 0 <= new <= ship.colonist_capacity:
            raise DevPatchError(f"colonists must be 0..{ship.colonist_capacity} (capacity)")
        return new
    if field == "holds_total":
        if new < ship.holds_used:
            raise DevPatchError(f"holds_total must be >= holds_used ({ship.holds_used})")
        return new
    if field == "hull_current":
        if not 0 <= new <= ship.hull_max:
            raise DevPatchError(f"hull_current must be 0..{ship.hull_max} (hull_max)")
        return new
    return max(0, new)  # missiles / repair_kits / colonist_capacity
