"""WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).

Covers the derive-on-write formula (and the regression pin that the starter hull
derives exactly the Phase-1 flat numbers), cap emergence, the install / swap /
cannibalize / field-patch reducers, and component conservation as a property.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from edge.config import load_default_config
from edge.core.engine_room import (
    EngineRoomError,
    apply_derived,
    build_subsystems,
    derive_aspects,
)
from edge.core.enums import Component, ComponentTier, Subsystem
from edge.core.models import (
    Game,
    InstalledComponent,
    Player,
    Ship,
    SubsystemState,
    UniverseState,
)
from edge.core.rules import (
    Cannibalize,
    FieldPatch,
    InstallComponent,
    SwapComponent,
    apply_result,
    reduce,
)

CONFIG = load_default_config()


def _state(components: dict[tuple[Component, ComponentTier], int] | None = None) -> UniverseState:
    """A one-ship universe: the starter hull with its engine room built (§4.1)."""
    game = Game(id=1, seed=1, config_version=2, created_at="2026-06-16T00:00:00Z")
    state = UniverseState.new(game)
    sc = CONFIG.starter_ship
    ship = Ship(
        id=1, type_id=sc.id, name=sc.name, owner_player_id=1, sector_id=1,
        holds_total=sc.holds_total, hull_current=sc.hull_max, hull_max=sc.hull_max,
        shields=sc.shields_max, warp_speed=sc.warp_speed, combat_speed=sc.combat_speed,
        cloak_rating=sc.cloak_rating, sensor_rating=sc.sensor_rating,
        turns_per_warp=sc.turns_per_warp, subsystems=build_subsystems(sc),
        components=dict(components or {}),
    )
    state.ships = {1: apply_derived(ship, CONFIG)}
    state.players = {1: Player(id=1, name="P", ship_id=1, latinum=10_000, turns_remaining=250)}
    return state


def _do(state: UniverseState, cmd: object) -> None:
    apply_result(state, reduce(state, 1, cmd, CONFIG))  # type: ignore[arg-type]


# --- derived-aspect formula -------------------------------------------------


def test_starter_hull_derives_phase1_flat_numbers() -> None:
    """The minimal starter layout must reproduce the Phase-1 balance exactly."""
    ship = _state().ships[1]
    a = derive_aspects(ship, CONFIG)
    assert (a.shields, a.warp_speed, a.combat_speed, a.turns_per_warp) == (100, 3, 4, 1)
    # And derive-on-write stored those onto the ship's flat fields.
    assert (ship.shields, ship.warp_speed, ship.combat_speed) == (100, 3, 4)


def test_npc_flat_hull_derives_unchanged() -> None:
    """A `subsystems=None` hull returns its flat scalars untouched (the NPC path)."""
    npc = Ship(id=2, type_id="npc", name="Raider", owner_player_id=None, sector_id=1,
               holds_total=0, shields=55, warp_speed=7, combat_speed=9, turns_per_warp=2)
    a = derive_aspects(npc, CONFIG)
    assert (a.shields, a.warp_speed, a.combat_speed, a.turns_per_warp) == (55, 7, 9, 2)


def test_derive_scales_with_slot_count() -> None:
    """A fourth spindrive part raises warp by per_component (Tier I adds nothing more)."""
    state = _state({(Component.ACCELERATOR, ComponentTier.I): 1})
    _do(state, InstallComponent(Subsystem.SPINDRIVE, 3, Component.ACCELERATOR, ComponentTier.I))
    assert state.ships[1].warp_speed == 4


def test_derive_scales_with_tier() -> None:
    """A Tier-III part adds per_tier·(tier-1) on top of per_component."""
    state = _state({(Component.ACCELERATOR, ComponentTier.III): 1})
    _do(state, InstallComponent(Subsystem.SPINDRIVE, 3, Component.ACCELERATOR, ComponentTier.III))
    assert state.ships[1].warp_speed == 6  # 4 parts·1 + tier_bonus 2·1


def test_cap_emerges_from_slots_times_tier() -> None:
    """No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5."""
    state = _state()
    full = SubsystemState(
        slots=tuple(InstalledComponent(Component.ACCELERATOR, ComponentTier.III) for _ in range(5)),
        keystone_index=0,
    )
    subsystems = {**state.ships[1].subsystems, Subsystem.SPINDRIVE: full}  # type: ignore[dict-item]
    ship = replace(state.ships[1], subsystems=subsystems)
    assert derive_aspects(ship, CONFIG).warp_speed == 15


def test_knocked_out_component_does_not_count() -> None:
    """A knocked-out part contributes nothing until it is patched (§4.1)."""
    state = _state()
    sub = state.ships[1].subsystems[Subsystem.THRUSTERS]  # type: ignore[index]
    slots = list(sub.slots)
    slots[1] = replace(slots[1], knocked_out=True)  # type: ignore[arg-type]
    subsystems = {**state.ships[1].subsystems, Subsystem.THRUSTERS: replace(sub, slots=tuple(slots))}  # type: ignore[dict-item]
    ship = apply_derived(replace(state.ships[1], subsystems=subsystems), CONFIG)
    assert ship.combat_speed == 2  # only the keystone burner counts now


# --- install / swap / cannibalize / field-patch reducers --------------------


def test_install_consumes_the_loose_part() -> None:
    state = _state({(Component.RADIATOR, ComponentTier.I): 1})
    _do(state, InstallComponent(Subsystem.SPINDRIVE, 3, Component.RADIATOR, ComponentTier.I))
    ship = state.ships[1]
    assert ship.subsystems[Subsystem.SPINDRIVE].slots[3] == InstalledComponent(  # type: ignore[index]
        Component.RADIATOR, ComponentTier.I)
    assert (Component.RADIATOR, ComponentTier.I) not in ship.components


def test_install_rejected_without_the_part() -> None:
    with pytest.raises(EngineRoomError):
        _do(_state(), InstallComponent(Subsystem.SPINDRIVE, 3, Component.RADIATOR, ComponentTier.I))


def test_install_rejected_into_filled_slot() -> None:
    state = _state({(Component.RADIATOR, ComponentTier.I): 1})
    with pytest.raises(EngineRoomError):
        _do(state, InstallComponent(Subsystem.SPINDRIVE, 0, Component.RADIATOR, ComponentTier.I))


def test_install_rejected_for_illegal_component() -> None:
    state = _state({(Component.BURNER, ComponentTier.I): 1})  # burner isn't legal in spindrive
    with pytest.raises(EngineRoomError):
        _do(state, InstallComponent(Subsystem.SPINDRIVE, 3, Component.BURNER, ComponentTier.I))


def test_cannibalize_returns_part_to_inventory() -> None:
    state = _state()
    _do(state, Cannibalize(Subsystem.SPINDRIVE, 2))  # slot 2 = accelerator
    ship = state.ships[1]
    assert ship.components[(Component.ACCELERATOR, ComponentTier.I)] == 1
    assert ship.subsystems[Subsystem.SPINDRIVE].slots[2] is None  # type: ignore[index]
    assert ship.warp_speed == 2  # one fewer active part


def test_swap_conserves_parts() -> None:
    state = _state({(Component.RADIATOR, ComponentTier.I): 1})
    _do(state, SwapComponent(Subsystem.SPINDRIVE, 2, Component.RADIATOR, ComponentTier.I))
    ship = state.ships[1]
    assert ship.subsystems[Subsystem.SPINDRIVE].slots[2].kind is Component.RADIATOR  # type: ignore[index,union-attr]
    assert ship.components[(Component.ACCELERATOR, ComponentTier.I)] == 1  # old part returned
    assert (Component.RADIATOR, ComponentTier.I) not in ship.components  # new part consumed


def test_engine_room_op_rejected_on_flat_hull() -> None:
    """A `subsystems=None` (NPC-style) hull has no engine room to operate on."""
    state = _state()
    state.ships[1] = replace(state.ships[1], subsystems=None)
    with pytest.raises(EngineRoomError):
        _do(state, Cannibalize(Subsystem.SPINDRIVE, 0))


def test_swap_rejected_on_empty_slot() -> None:
    state = _state({(Component.RADIATOR, ComponentTier.I): 1})
    with pytest.raises(EngineRoomError):
        _do(state, SwapComponent(Subsystem.SPINDRIVE, 4, Component.RADIATOR, ComponentTier.I))


def test_cannibalize_rejected_on_empty_slot() -> None:
    with pytest.raises(EngineRoomError):
        _do(_state(), Cannibalize(Subsystem.SPINDRIVE, 4))


def test_field_patch_rejected_on_undamaged_slot() -> None:
    with pytest.raises(EngineRoomError):
        _do(_state(), FieldPatch(Subsystem.SPINDRIVE, 0))


def test_field_patch_rejected_without_a_kit() -> None:
    state = _state()
    sub = state.ships[1].subsystems[Subsystem.SPINDRIVE]  # type: ignore[index]
    slots = list(sub.slots)
    slots[1] = replace(slots[1], knocked_out=True)  # type: ignore[arg-type]
    subsystems = {**state.ships[1].subsystems, Subsystem.SPINDRIVE: replace(sub, slots=tuple(slots))}  # type: ignore[dict-item]
    state.ships[1] = replace(state.ships[1], subsystems=subsystems, repair_kits=0)
    with pytest.raises(EngineRoomError):
        _do(state, FieldPatch(Subsystem.SPINDRIVE, 1))


def test_field_patch_restores_a_knocked_out_component() -> None:
    state = _state()
    sub = state.ships[1].subsystems[Subsystem.THRUSTERS]  # type: ignore[index]
    slots = list(sub.slots)
    slots[1] = replace(slots[1], knocked_out=True)  # type: ignore[arg-type]
    subsystems = {**state.ships[1].subsystems, Subsystem.THRUSTERS: replace(sub, slots=tuple(slots))}  # type: ignore[dict-item]
    state.ships[1] = apply_derived(
        replace(state.ships[1], subsystems=subsystems, repair_kits=1), CONFIG)
    assert state.ships[1].combat_speed == 2  # damaged
    _do(state, FieldPatch(Subsystem.THRUSTERS, 1))
    assert state.ships[1].combat_speed == 4  # restored
    assert state.ships[1].repair_kits == 0


# --- conservation property (mirrors the goods-conservation pattern) ---------


def _total_parts(ship: Ship) -> int:
    inv = sum(ship.components.values())
    installed = sum(
        1 for sub in (ship.subsystems or {}).values() for slot in sub.slots if slot is not None
    )
    return inv + installed


def _first_filled_nonkeystone(ship: Ship, subsystem: Subsystem) -> int:
    sub = ship.subsystems[subsystem]  # type: ignore[index]
    for i, slot in enumerate(sub.slots):
        if slot is not None and i != sub.keystone_index:
            return i
    return -1  # the reducer rejects an out-of-range slot


def _first_empty(ship: Ship, subsystem: Subsystem) -> int:
    sub = ship.subsystems[subsystem]  # type: ignore[index]
    for i, slot in enumerate(sub.slots):
        if slot is None:
            return i
    return -1


@given(ops=st.lists(st.sampled_from(["install", "cannibalize"]), max_size=18))
def test_install_cannibalize_conserve_components(ops: list[str]) -> None:
    """Every install/cannibalize moves a part between hold and slot — never creates or
    destroys one (a core invariant, like goods conservation under trade)."""
    state = _state({(Component.ACCELERATOR, ComponentTier.I): 3})
    total = _total_parts(state.ships[1])
    for op in ops:
        ship = state.ships[1]
        try:
            if op == "cannibalize":
                _do(state, Cannibalize(Subsystem.SPINDRIVE, _first_filled_nonkeystone(ship, Subsystem.SPINDRIVE)))
            else:
                _do(state, InstallComponent(
                    Subsystem.SPINDRIVE, _first_empty(ship, Subsystem.SPINDRIVE),
                    Component.ACCELERATOR, ComponentTier.I))
        except EngineRoomError:
            pass  # an illegal step is a no-op; conservation must still hold
        assert _total_parts(state.ships[1]) == total
