"""WP41 — sector fighters, mines, beacons, black-hole hazards (§10).

Covers the pure territory helpers (`core.territory`), the buy/deploy reducers, and the
movement-entry effects: mine damage, the fighter engage-or-retreat (retreat costs a
fighter), and the black-hole gravity toll.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core import territory
from edge.core.economy import EconomyError
from edge.core.enums import DiscoveryKind, PayloadKind, PortClass, RarityTier
from edge.core.events import HazardDamage, TerritoryDeployed
from edge.core.models import (
    AlienSpecies,
    Discovery,
    DiscoveryPayload,
    Encounter,
    Game,
    Ownership,
    Player,
    Sector,
    SectorForce,
    Ship,
    UniverseState,
)
from edge.core.rules import (
    BuyFighters,
    CombatAction,
    DeployBeacon,
    DeployFighters,
    DeployMines,
    JoinGame,
    LaunchProbe,
    RemoveLimpets,
    ToggleInterdictor,
    Warp,
    apply_result,
    reduce,
)

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(
    update={"sector_count": 400, "start_sector": 1})})
TC = CFG.territory


# --- pure helpers -----------------------------------------------------------


def _force(**kw) -> SectorForce:
    # `mines=` in kwargs maps to armid mines (the WP56 rename; keeps existing callers).
    if "mines" in kw:
        kw["armid_mines"] = kw.pop("mines")
    base = dict(sector_id=2, owner=Ownership("alliance", 2), fighters=5, armid_mines=2)
    base.update(kw)
    return SectorForce(**base)


def test_force_hostile_keys_on_owner_and_standing() -> None:
    state = _mini_state()
    force = _force()
    assert territory.force_hostile_to_player(state, force, state.players[1]) is False  # neutral
    hostile = replace(state.players[1], alliance_standing={2: -1.0})
    assert territory.force_hostile_to_player(state, force, hostile) is True
    # A player-owned garrison never bars the player.
    own = _force(owner=Ownership("player", 1))
    assert territory.force_hostile_to_player(state, own, hostile) is False


def test_fighter_foe_scales_with_count() -> None:
    small, big = territory.fighter_foe(_force(fighters=2), CFG), territory.fighter_foe(_force(fighters=10), CFG)
    assert big.hull > small.hull and big.firing_arc == "all_round" and big.combat_speed == 0


# --- state builders ---------------------------------------------------------


def _mini_state(*, black_hole: bool = False) -> UniverseState:
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(2,), distance_band="Frontier")
    state.sectors[2] = Sector(id=2, region_id=1, warps_out=(1,), distance_band="Frontier")
    state.rebuild_adjacency()
    if black_hole:
        state.discoveries[1] = Discovery(
            id=1, kind=DiscoveryKind.BLACK_HOLE, rarity_tier=RarityTier.RARE, sector_id=2,
            payload=DiscoveryPayload(kind=PayloadKind.LORE, lore="a maw"))
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=20, hull_current=200, hull_max=200,
                          shields=50, warp_speed=3, combat_speed=3, turns_per_warp=1)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=5000, turns_remaining=100)
    return state


def _generated():
    state = generate(SMALL, 3)
    apply_result(state, reduce(state, 1, JoinGame(name="T"), SMALL))
    dock = next(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    ship = state.ships[state.players[1].ship_id]
    state.ships[ship.id] = replace(ship, sector_id=dock)  # sit at the StarDock to buy
    return state


# --- buy + deploy reducers --------------------------------------------------


def test_buy_and_deploy_fighters() -> None:
    state = _generated()
    apply_result(state, reduce(state, 1, BuyFighters(count=20), SMALL))
    ship = state.ships[state.players[1].ship_id]
    assert ship.fighters == 20
    # Move to a guaranteed non-Core sector to deploy.
    non_core = next(s.id for s in state.sectors.values() if not s.is_galactic_core)
    state.ships[ship.id] = replace(ship, sector_id=non_core)
    result = reduce(state, 1, DeployFighters(count=8, mode="toll", toll=25), SMALL)
    apply_result(state, result)
    ship = state.ships[state.players[1].ship_id]
    force = state.sector_forces[ship.sector_id]
    assert ship.fighters == 12 and force.fighters == 8 and force.mode == "toll" and force.toll == 25
    assert force.owner == Ownership("player", 1)
    assert any(isinstance(e, TerritoryDeployed) for e in result.events)


def test_deploy_rejects_core() -> None:
    state = _mini_state()
    state.sectors[1] = replace(state.sectors[1], is_galactic_core=True)
    state.ships[1] = replace(state.ships[1], fighters=5)
    with pytest.raises(EconomyError, match="Core"):
        reduce(state, 1, DeployFighters(count=1), CFG)


def test_deploy_beacon_sets_text_and_charges() -> None:
    state = _mini_state()
    before = state.players[1].latinum
    apply_result(state, reduce(state, 1, DeployBeacon(text="hi there"), CFG))
    assert state.sectors[1].beacon_text == "hi there"
    assert state.players[1].latinum == before - TC.beacon_price


# --- movement entry effects -------------------------------------------------


def _make_hostile(state: UniverseState) -> None:
    state.players[1] = replace(state.players[1], alliance_standing={2: -1.0})


def test_hostile_mines_damage_on_entry_and_are_spent() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=0, mines=2)
    _make_hostile(state)
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    ship = state.ships[1]
    # 2 mines × mine_damage, minus 50 shields absorbed.
    assert ship.hull_current < 200
    assert 2 not in state.sector_forces or state.sector_forces[2].mines == 0  # spent
    assert state.players[1].active_encounter is None  # no fighters ⇒ no engagement


def test_hostile_fighters_force_engagement() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=4, mines=0)
    _make_hostile(state)
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    enc = state.players[1].active_encounter
    assert enc is not None and enc.species_id == 0 and enc.starbase_id is None


def test_retreat_from_fighters_costs_the_garrison_a_fighter() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=4, mines=0)
    # Hand the player a live fighter engagement and force a successful flee.
    foe = territory.fighter_foe(state.sector_forces[2], CFG)
    state.ships[1] = replace(state.ships[1], sector_id=2, combat_speed=99)  # guarantees flee
    state.players[1] = replace(state.players[1], active_encounter=Encounter(
        species_id=0, sector_id=2, foes=(foe,), player_shields=50))
    apply_result(state, reduce(state, 1, CombatAction(action="flee"), CFG))
    assert state.sector_forces[2].fighters == 4 - TC.retreat_fighter_cost


def test_victory_over_fighters_clears_the_garrison() -> None:
    # A generated player ship has a working engine room (Main Gun online).
    state = _generated()
    ship = state.ships[state.players[1].ship_id]
    sid = ship.sector_id
    state.sector_forces[sid] = SectorForce(sector_id=sid, owner=Ownership("alliance", 2), fighters=1)
    foe = replace(territory.fighter_foe(state.sector_forces[sid], SMALL), hull=1, hull_max=1)
    state.players[1] = replace(state.players[1], active_encounter=Encounter(
        species_id=0, sector_id=sid, foes=(foe,), player_shields=ship.shields))
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    assert sid not in state.sector_forces  # garrison wiped (empty force cleared)


def test_black_hole_damages_on_entry() -> None:
    state = _mini_state(black_hole=True)
    result = reduce(state, 1, Warp(to_sector=2), CFG)
    apply_result(state, result)
    assert state.ships[1].hull_current == 200 - TC.black_hole_damage
    assert any(isinstance(e, HazardDamage) and e.source == "black_hole" for e in result.events)


def test_black_hole_lethal_toll_pods_the_player() -> None:
    """A lethal hazard routes through the WP26 escape pod (WP75 — the A5 seam closed)."""
    from edge.core.events import ShipDestroyed
    state = _mini_state(black_hole=True)
    state.ships[1] = replace(state.ships[1], hull_current=5)  # below the toll
    result = reduce(state, 1, Warp(to_sector=2), CFG)
    apply_result(state, result)
    ship = state.ships[1]
    assert ship.type_id == CFG.combat.escape_pod_class  # podded on the spot
    assert ship.sector_id == 2 and ship.hull_current == ship.hull_max
    assert any(isinstance(e, HazardDamage) for e in result.events)
    assert any(isinstance(e, ShipDestroyed) for e in result.events)
    assert state.players[1].active_encounter is None  # no engagement over a wreck


# --- WP56: armid/limpet split, probes, interdictor --------------------------


def test_armid_mines_behave_like_the_old_mines() -> None:
    """Armid is the WP41 mine renamed — same entry damage, spent on detonation."""
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=0, armid_mines=2)
    _make_hostile(state)
    before = state.ships[1].hull_current
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    assert state.ships[1].hull_current < before  # took damage
    assert 2 not in state.sector_forces  # force spent + cleared


def test_mine_deflector_absorbs_armid_hits_one_for_one() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=0, armid_mines=2)
    _make_hostile(state)
    state.ships[1] = replace(state.ships[1], devices={CFG.territory.mine_deflector_device: 2})
    before = state.ships[1].hull_current
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    assert state.ships[1].hull_current == before  # 2 deflectors cancel 2 mines


def test_limpet_attaches_and_is_removable_for_a_fee() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=0, armid_mines=0, limpet_mines=3)
    _make_hostile(state)
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    tag = territory.owner_tag(Ownership("alliance", 2))
    assert state.ships[1].limpets.get(tag) == 3  # attached, tagged to the bloc
    # Removal needs a service point — none here, so it is rejected.
    with pytest.raises(EconomyError):
        reduce(state, 1, RemoveLimpets(), CFG)


def test_limpet_makes_the_player_trackable_by_the_bloc_hunters() -> None:
    from edge.core import npc
    state = _mini_state()
    # A bloc-2 hunter with no personal grudge cannot normally find the player...
    sp = AlienSpecies(id=1, roster_id="hunter", name="H", archetype_id="a", sector_id=1,
                      home_band="Frontier", tech_level=5, base_disposition=0.2,
                      disposition_center=0.2, disposition_variance=0.0, alliance_id=2)
    assert npc._grudge_targets(state, sp) == []
    # ...but a limpet tagged to bloc 2 exposes the player's exact sector to it.
    tag = territory.owner_tag(Ownership("alliance", 2))
    state.ships[1] = replace(state.ships[1], limpets={tag: 1})
    assert npc._grudge_targets(state, sp) == [state.ships[1].sector_id]


def test_deploy_mines_kind_routes_to_the_right_pile() -> None:
    state = _mini_state()
    state.ships[1] = replace(state.ships[1], sector_id=2, mines=10)
    apply_result(state, reduce(state, 1, DeployMines(count=3, kind="armid"), CFG))
    apply_result(state, reduce(state, 1, DeployMines(count=2, kind="limpet"), CFG))
    force = state.sector_forces[2]
    assert force.armid_mines == 3 and force.limpet_mines == 2
    assert state.ships[1].mines == 5  # both drew from the single carried stock


def test_probe_charts_its_path_and_reports() -> None:
    from edge.core.events import ProbeReport
    state = _mini_state()  # sectors 1<->2
    state.ships[1] = replace(state.ships[1], devices={"probe": 1})
    before = set(state.players[1].explored_sectors)
    result = reduce(state, 1, LaunchProbe(dest_sector=2), CFG)
    apply_result(state, result)
    report = next(e for e in result.events if isinstance(e, ProbeReport))
    assert report.dest_sector == 2 and report.sectors_charted >= 1 and not report.destroyed
    assert 2 in state.players[1].explored_sectors and 2 not in before
    assert state.ships[1].devices.get("probe", 0) == 0  # consumed


def test_probe_lost_in_a_hostile_sector() -> None:
    from edge.core.events import ProbeReport
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=0, armid_mines=1)  # hostile-held sector 2
    _make_hostile(state)
    state.ships[1] = replace(state.ships[1], devices={"probe": 1})
    # loss_chance 0.25 default; force the roll low so the probe is certainly destroyed.
    import random
    state.rng = random.Random(0)
    # Try a few seeds to find one that destroys — determinism is what we assert, not odds.
    destroyed_seen = False
    for seed in range(20):
        s = _mini_state()
        s.sector_forces[2] = _force(fighters=0, armid_mines=1)
        _make_hostile(s)
        s.ships[1] = replace(s.ships[1], devices={"probe": 1})
        s.rng = random.Random(seed)
        res = reduce(s, 1, LaunchProbe(dest_sector=2), CFG)
        if next(e for e in res.events if isinstance(e, ProbeReport)).destroyed:
            destroyed_seen = True
            break
    assert destroyed_seen  # a hostile sector can down a probe


# --- NPC entry defenses (WP-PR02) -------------------------------------------


def _species(**kw) -> AlienSpecies:
    # A real roster id so `_npc_combat_stats` resolves a fleet hull. `stryx` is an
    # unaligned scout (hull 80 + shields 120 → pool 200), disposition 0.3 (hostile band).
    base = dict(id=7, roster_id="stryx", name="Stryx", archetype_id="a", sector_id=1,
                home_band="Frontier", tech_level=3, base_disposition=0.3,
                disposition_center=0.3, disposition_variance=0.0, alliance_id=None)
    base.update(kw)
    return AlienSpecies(**base)


def test_force_hostile_to_species_keys_on_owner() -> None:
    state = _mini_state()
    # Player-owned force bars a hostile-band wanderer; a friendly one passes.
    pforce = _force(owner=Ownership("player", 1))
    assert territory.force_hostile_to_species(state, pforce, _species(), CFG) is True
    friendly = _species(base_disposition=0.95)
    assert territory.force_hostile_to_species(state, pforce, friendly, CFG) is False
    # Alliance-owned force bars a rival bloc's species, not its own members. Alliance 2's
    # rival is 3 (helot); alliance 2's own member (selvi) passes free.
    aforce = _force(owner=Ownership("alliance", 2))
    rival = _species(roster_id="helot", alliance_id=3)
    assert territory.force_hostile_to_species(state, aforce, rival, CFG) is True
    member = _species(roster_id="selvi", alliance_id=2)
    assert territory.force_hostile_to_species(state, aforce, member, CFG) is False


def test_npc_entry_mines_destroy_a_light_hull() -> None:
    state = _mini_state()
    force = _force(owner=Ownership("player", 1), fighters=0, mines=5)  # 5×40 = 200 ≥ pool 200
    entry = territory.resolve_npc_entry(state, _species(), force, CFG)
    assert entry.destroyed and entry.cause == "mine"
    assert entry.force is not None and entry.force.armid_mines == 0  # spent


def test_npc_entry_is_inert_for_a_non_hostile_or_empty_force() -> None:
    state = _mini_state()
    friendly = _species(base_disposition=0.95)
    force = _force(owner=Ownership("player", 1), fighters=0, mines=5)
    assert territory.resolve_npc_entry(state, friendly, force, CFG) == territory.NpcEntry(
        False, None, "")
    assert territory.resolve_npc_entry(state, _species(), None, CFG) == territory.NpcEntry(
        False, None, "")


def test_npc_entry_fighters_alone_cannot_kill_a_warship_but_are_attrited() -> None:
    state = _mini_state()
    force = _force(owner=Ownership("player", 1), fighters=4, mines=0)
    entry = territory.resolve_npc_entry(state, _species(), force, CFG)
    assert entry.destroyed is False  # a token garrison can't gut a scout's hull
    assert entry.force is not None and entry.force.fighters < 4  # but the entrant thins it


def test_npc_entry_is_deterministic() -> None:
    state = _mini_state()
    force = _force(owner=Ownership("player", 1), fighters=3, mines=3)
    a = territory.resolve_npc_entry(state, _species(), force, CFG)
    b = territory.resolve_npc_entry(state, _species(), force, CFG)
    assert a == b


def test_alien_drift_destroys_hostile_npc_in_a_minefield() -> None:
    from edge.engine.cron import alien_drift
    from edge.core.events import AlienDestroyed
    state = _mini_state()
    state.ships[1] = replace(state.ships[1], sector_id=2)  # player present ⇒ event surfaces
    state.sector_forces[2] = _force(owner=Ownership("player", 1), fighters=0, mines=5)
    state.species[7] = _species(sector_id=1)  # drifts 1 → 2 into the minefield
    cfg = CFG.model_copy(update={"aliens": CFG.aliens.model_copy(
        update={"drift_enabled": True, "drift_move_chance": 1.0})})
    result = alien_drift(state, cfg)
    assert 7 in result.removed_species_ids  # destroyed, not relocated
    assert all(s.id != 7 for s in result.species)
    assert any(isinstance(e, AlienDestroyed) and e.sector_id == 2 for e in result.events)
    apply_result(state, result)
    assert 7 not in state.species  # gone from the destination
    assert 2 not in state.sector_forces  # mines spent, force cleared


def test_alien_drift_moves_a_friendly_npc_through_a_minefield_unharmed() -> None:
    from edge.engine.cron import alien_drift
    state = _mini_state()
    state.ships[1] = replace(state.ships[1], sector_id=2)
    state.sector_forces[2] = _force(owner=Ownership("player", 1), fighters=0, mines=5)
    state.species[7] = _species(sector_id=1, base_disposition=0.95)  # friendly ⇒ passes free
    cfg = CFG.model_copy(update={"aliens": CFG.aliens.model_copy(
        update={"drift_enabled": True, "drift_move_chance": 1.0})})
    result = alien_drift(state, cfg)
    assert 7 not in result.removed_species_ids
    assert any(s.id == 7 and s.sector_id == 2 for s in result.species)
    assert state.sector_forces[2].armid_mines == 5  # untriggered


def test_interdictor_toggle_pins_drift() -> None:
    from edge.engine.cron import alien_drift
    state = _mini_state()
    state.ships[1] = replace(state.ships[1], sector_id=2, devices={"interdictor": 1})
    apply_result(state, reduce(state, 1, ToggleInterdictor(), CFG))
    assert state.ships[1].interdictor_active
    # A species sitting in the interdicted sector 2 cannot drift out.
    state.species[1] = AlienSpecies(
        id=1, roster_id="drifter", name="D", archetype_id="a", sector_id=2,
        home_band="Frontier", tech_level=5, base_disposition=0.8,
        disposition_center=0.8, disposition_variance=0.0, alliance_id=None)
    drift = alien_drift(state, CFG.model_copy(update={"aliens": CFG.aliens.model_copy(
        update={"drift_enabled": True, "drift_move_chance": 1.0})}))
    assert all(s.id != 1 for s in drift.species)  # pinned — did not move
