"""WP75 — danger polish (SEAMS_PLAN A3/A4/A5).

Three seams closed: a live pack can fall on an escorted merchant (failing the contract
with the full WP27 consequence rail), the route planner warns about hazards the player
already knows, and a lethal territory hazard routes through the WP26 escape pod (the
black-hole case lives in test_territory.py; the mine case is covered here).
"""

from __future__ import annotations

from dataclasses import replace

from edge.config import load_default_config
from edge.core import contracts, territory
from edge.core.enums import Commodity, DiscoveryKind, PayloadKind, PortClass, PortMode, RarityTier
from edge.core.events import AttitudeChanged, ContractFailed, GrudgeFormed, ShipDestroyed
from edge.core.models import (
    AlienSpecies,
    Discovery,
    DiscoveryPayload,
    Encounter,
    Game,
    Ownership,
    Player,
    Port,
    PortCommodity,
    Sector,
    SectorForce,
    Ship,
    UniverseState,
)
from edge.core.rules import CombatAction, Warp, apply_result, reduce
from edge.server.session import route_view

CFG = load_default_config()
def _with_chance(chance: float):
    return CFG.model_copy(update={"aliens": CFG.aliens.model_copy(
        update={"contracts": CFG.aliens.contracts.model_copy(
            update={"escort_target_chance": chance})})})


ALWAYS_TARGET = _with_chance(1.0)
NEVER_TARGET = _with_chance(0.0)


def _sp(sid: int, roster_id: str, sector: int, *, alliance_id: int | None = None,
        disp: float = 1.0) -> AlienSpecies:
    return AlienSpecies(
        id=sid, roster_id=roster_id, name=roster_id.title(), archetype_id="a",
        sector_id=sector, home_band="Hub", tech_level=5, base_disposition=disp,
        disposition_center=disp, disposition_variance=0.0, alliance_id=alliance_id)


def _world() -> UniverseState:
    """Sectors 1-2-3 (Frontier) with a port in 2; player + tough ship in sector 1."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {
        1: Sector(1, 1, (2,), "Frontier"),
        2: Sector(2, 1, (1, 3), "Frontier"),
        3: Sector(3, 1, (2,), "Frontier"),
    }
    state.rebuild_adjacency()
    state.ports = {
        7: Port(7, 2, "Mart", PortClass.CLASS_1, 5, (
            PortCommodity(Commodity.FUEL_ORE, PortMode.BUY, 100, 5000, 11, 5),
        ), latinum=50_000),
    }
    from edge.core.engine_room import build_subsystems
    state.ships = {1: Ship(
        id=1, type_id="trailblazer", name="TB", owner_player_id=1, sector_id=1,
        holds_total=100, hull_current=1000, hull_max=1000, shields=100,
        warp_speed=1, combat_speed=1, turns_per_warp=1,
        subsystems=build_subsystems(CFG.ship_class("trailblazer")))}
    state.players = {1: Player(id=1, name="Cap", ship_id=1, latinum=1000,
                               turns_remaining=100, alliance_id=1)}
    return state


def _escorting(state: UniverseState) -> None:
    """Book an active escort of merchant 11 (issuer terran) riding with the player."""
    issuer = _sp(10, "terran", 1, alliance_id=1)
    merchant = _sp(11, "selvani", 1, alliance_id=1, disp=0.78)  # selvani = trade_seek
    state.species = {10: issuer, 11: merchant}
    offer = contracts.pick_contract(state, issuer, state.players[1], CFG)
    assert offer is not None and offer.kind == "escort" and offer.target_species_id == 11
    booked = contracts.accept(state.players[1], offer, 1, CFG)
    state.players[1] = replace(state.players[1], contracts=(booked,))


def _garrison_fight(state: UniverseState) -> None:
    """A live fighter engagement in sector 1 that the player cannot end this round."""
    force = SectorForce(sector_id=1, owner=Ownership("alliance", 2), fighters=8)
    state.sector_forces[1] = force
    foe = territory.fighter_foe(force, CFG)
    state.players[1] = replace(state.players[1], active_encounter=Encounter(
        species_id=0, sector_id=1, foes=(foe,), player_shields=100))


# --- A3: the pack may fall on the escorted merchant --------------------------------


def test_escort_merchant_destroyed_under_fire_fails_contract_with_consequences() -> None:
    state = _world()
    _escorting(state)
    _garrison_fight(state)
    result = reduce(state, 1, CombatAction(action="fight"), ALWAYS_TARGET)
    apply_result(state, result)
    player = state.players[1]
    assert player.contracts[0].status == "failed"
    failed = next(e for e in result.events if isinstance(e, ContractFailed))
    assert failed.reason == "merchant destroyed"
    # The full WP27 rail against the issuer's kind: souring + an honest grudge cause.
    assert player.species_attitudes.get("terran", 0.0) < 0.0
    grudge = player.grudges.get("terran")
    assert grudge is not None and "escort" in grudge.cause
    assert any(isinstance(e, GrudgeFormed) for e in result.events)
    assert any(isinstance(e, AttitudeChanged) for e in result.events)
    assert contracts.is_convoyed(state, 11) is False  # released back to the rails


def test_escort_merchant_safe_when_roll_disabled_or_elsewhere() -> None:
    # chance 0 — the merchant is never targeted.
    state = _world()
    _escorting(state)
    _garrison_fight(state)
    apply_result(state, reduce(state, 1, CombatAction(action="fight"), NEVER_TARGET))
    assert state.players[1].contracts[0].status == "active"
    # merchant in another sector — no roll even at chance 1 (suspended convoy is safe).
    state = _world()
    _escorting(state)
    state.species[11] = replace(state.species[11], sector_id=3)
    _garrison_fight(state)
    apply_result(state, reduce(state, 1, CombatAction(action="fight"), ALWAYS_TARGET))
    assert state.players[1].contracts[0].status == "active"


# --- A4: route hazards from the player's own knowledge -----------------------------


def test_route_hazards_list_known_black_hole_forces_and_band_risk() -> None:
    state = _world()
    state.discoveries[1] = Discovery(
        id=1, kind=DiscoveryKind.BLACK_HOLE, rarity_tier=RarityTier.RARE, sector_id=2,
        payload=DiscoveryPayload(kind=PayloadKind.LORE, lore="a maw"))
    state.sector_forces[2] = SectorForce(
        sector_id=2, owner=Ownership("alliance", 2), fighters=6, armid_mines=1)
    state.players[1] = replace(
        state.players[1], explored_sectors=frozenset({1, 2, 3}),
        alliance_standing={2: -1.0})  # the bloc's force is a known enemy
    dto = route_view(state, 1, 3, CFG)
    text = "\n".join(dto.hazards)
    assert "Black hole" in text
    assert "Hostile 6 fighters + mines" in text
    assert "Encounter risk" in text and "Frontier" in text  # band interrupt risk


def test_route_hazards_hide_unexplored_dangers() -> None:
    """A full-graph lead route may cross unexplored space — fog hides its hazards."""
    from edge.core.models import Lead
    state = _world()
    state.discoveries[1] = Discovery(
        id=1, kind=DiscoveryKind.BLACK_HOLE, rarity_tier=RarityTier.RARE, sector_id=2,
        payload=DiscoveryPayload(kind=PayloadKind.LORE, lore="a maw"))
    # A coordinate tip to sector 3 obtained here (sector 1): plotting it routes over the
    # full graph through unexplored sector 2, whose black hole the player has never seen.
    state.players[1] = replace(
        state.players[1], explored_sectors=frozenset({1}),
        leads=(Lead(kind="discovery", ref=9, sector_id=3, origin_sector=1,
                    source_species="terran", summary="a tip"),))
    dto = route_view(state, 1, 3, CFG, full_graph=True)
    assert dto.reachable
    assert not any("Black hole" in h for h in dto.hazards)
    assert any("Encounter risk" in h for h in dto.hazards)  # band risk is world knowledge


# --- A5: a lethal mine field pods the player ---------------------------------------


def test_lethal_mine_field_pods_the_player_and_spawns_no_engagement() -> None:
    state = _world()
    state.ships[1] = replace(state.ships[1], hull_current=5, shields=0)
    state.sector_forces[2] = SectorForce(
        sector_id=2, owner=Ownership("alliance", 2), fighters=4, armid_mines=3)
    state.players[1] = replace(state.players[1], alliance_standing={2: -1.0})
    result = reduce(state, 1, Warp(to_sector=2), CFG)
    apply_result(state, result)
    ship = state.ships[1]
    assert ship.type_id == CFG.combat.escape_pod_class
    assert ship.hull_current == ship.hull_max and ship.sector_id == 2
    assert any(isinstance(e, ShipDestroyed) for e in result.events)
    assert state.players[1].active_encounter is None  # fighters spare the wreck
    assert state.sector_forces[2].armid_mines == 0  # the field is spent
