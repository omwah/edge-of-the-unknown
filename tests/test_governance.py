"""WP49 — the Core governance-flip reducer (DESIGN §6.3, §4.2).

The flip re-keys every Core planet/base to the new governor and *only* those, evicts
incumbents the new law bars onto legal ground deterministically, and — the WP38 seam —
re-keys the whole Core-safety surface (`governor_hostile` / `may_occupy` / Core law)
with **no code change**, driven solely by `Game.core_governing_alliance_id`. The flip
rides one `ReduceResult`, so it reconstructs under replay.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from edge.config import load_default_config
from edge.core.aliens import governor_hostile, may_occupy
from edge.core.dev import DevPatch
from edge.core.governance import flip_core_governor
from edge.core.models import (
    AlienSpecies,
    Alliance,
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    Starbase,
    UniverseState,
)
from edge.core.rules import apply_result, reduce
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash

CFG = load_default_config()


def _sp(sid: int, sector: int, alliance_id: int) -> AlienSpecies:
    return AlienSpecies(
        id=sid, roster_id=f"s{sid}", name=f"S{sid}", archetype_id="a", sector_id=sector,
        home_band="Hub", tech_level=5, base_disposition=0.8,
        disposition_center=0.8, disposition_variance=0.05, alliance_id=alliance_id)


def _world() -> UniverseState:
    """Core sectors 1,2 + a 3-4-5 Frontier tail; gov=1, rival bloc 2, third bloc 3."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t", core_governing_alliance_id=1))
    state.sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Hub", is_galactic_core=True),
        3: Sector(3, 1, (2, 4), "Frontier"),
        4: Sector(4, 1, (3, 5), "Frontier"),
        5: Sector(5, 1, (4,), "Frontier"),
    }
    state.rebuild_adjacency()
    state.alliances = {
        1: Alliance(1, "Federation"),
        2: Alliance(2, "Cabal", covets_core=True),
        3: Alliance(3, "Others"),
    }
    gov = Ownership("alliance", 1)
    state.planets = {
        1: Planet(1, 1, "Cap-A", "terrestrial_warm", owner=gov),               # Core
        2: Planet(2, 2, "Cap-B", "terrestrial_warm", owner=gov, starbase_id=9),  # Core + base
        3: Planet(3, 4, "Rim", "barren", owner=Ownership("alliance", 3)),        # non-Core, bloc 3
    }
    state.starbases = {9: Starbase(9, 2, 2, "orbital_fort", owner=gov)}
    state.species = {
        1: _sp(1, 1, alliance_id=1),  # gov incumbent in the Core → evicted on flip
        2: _sp(2, 3, alliance_id=1),  # gov member outside the Core → stays
        3: _sp(3, 4, alliance_id=2),  # rival member outside the Core → stays
    }
    state.ships[1] = Ship(1, "t", "P", 1, 3, 60)
    state.players[1] = Player(1, "you", 1, 2_000, alliance_id=1,
                              alliance_standing={2: -0.5})  # ill standing with the rival bloc
    return state


def test_flip_rekeys_every_core_planet_and_base_and_only_those() -> None:
    state = _world()
    delta = flip_core_governor(state, CFG, new_alliance_id=2, cause="dev")
    rekeyed = {p.id: p.owner for p in delta.planets}
    assert rekeyed == {1: Ownership("alliance", 2), 2: Ownership("alliance", 2)}  # both Core planets
    assert all(p.id != 3 for p in delta.planets)  # the non-Core planet is untouched
    (base,) = delta.starbases
    assert base.id == 9 and base.owner == Ownership("alliance", 2)
    assert delta.game.core_governing_alliance_id == 2


def test_flip_evicts_core_incumbents_to_the_nearest_legal_sector() -> None:
    state = _world()
    delta = flip_core_governor(state, CFG, new_alliance_id=2, cause="dev")
    moved = {s.id: s.sector_id for s in delta.species}
    # Only the gov incumbent standing in the Core moves; it lands on the nearest legal
    # ground (sector 3 — sector 2 is Core/illegal, sector 4 holds a rival bloc's planet).
    assert moved == {1: 3}


def test_flip_is_zero_touch_for_the_wp38_safety_surface() -> None:
    state = _world()
    apply_result(state, _as_result(flip_core_governor(state, CFG, 2, "dev")))
    # may_occupy now admits only the new governor's members into the Core — no code change.
    assert may_occupy(state, _sp(9, 1, alliance_id=2), 1, CFG.aliens)
    assert not may_occupy(state, _sp(9, 1, alliance_id=1), 1, CFG.aliens)
    # governor_hostile re-evaluates positionally: the player (member of the *old* gov, ill
    # standing with the new one) is now treated as an enemy of the Core.
    assert governor_hostile(state, state.players[1])


def test_flip_is_pure_and_deterministic() -> None:
    state = _world()
    a = flip_core_governor(state, CFG, 2, "dev")
    b = flip_core_governor(state, CFG, 2, "dev")  # pure: does not mutate state
    assert {p.id: p.owner for p in a.planets} == {p.id: p.owner for p in b.planets}
    assert {s.id: s.sector_id for s in a.species} == {s.id: s.sector_id for s in b.species}


def test_double_flip_round_trips_governance_and_core_ownership() -> None:
    state = _world()
    apply_result(state, _as_result(flip_core_governor(state, CFG, 2, "dev")))
    apply_result(state, _as_result(flip_core_governor(state, CFG, 1, "dev")))
    assert state.game.core_governing_alliance_id == 1
    assert state.planets[1].owner == Ownership("alliance", 1)
    assert state.planets[2].owner == Ownership("alliance", 1)
    assert state.starbases[9].owner == Ownership("alliance", 1)


def _as_result(delta: object) -> object:
    from edge.core.rules import ReduceResult

    return ReduceResult(events=delta.events, game=delta.game, planets=delta.planets,  # type: ignore[attr-defined]
                        starbases=delta.starbases, species=delta.species)  # type: ignore[attr-defined]


# --- WP52: aftermath surfacing (core_status + dock gating) --------------------


def test_core_status_truth_table() -> None:
    from edge.core.aliens import core_status

    state = _world()  # governor is alliance 1
    # A governing member is always safe at home.
    member = replace(state.players[1], alliance_id=1)
    assert core_status(state, member) == "safe"
    # A non-member at neutral/positive standing is tolerated but not home.
    neutral = replace(state.players[1], alliance_id=2, alliance_standing={1: 0.0})
    assert core_status(state, neutral) == "unwelcome"
    positive = replace(state.players[1], alliance_id=2, alliance_standing={1: 0.4})
    assert core_status(state, positive) == "unwelcome"
    # A non-member at negative standing is hunted.
    hunted = replace(state.players[1], alliance_id=2, alliance_standing={1: -0.5})
    assert core_status(state, hunted) == "hunted"
    # An ungoverned Core is safe for everyone.
    ungov = replace(state, game=replace(state.game, core_governing_alliance_id=None))
    assert core_status(ungov, hunted) == "safe"


def test_game_view_surfaces_governor_and_core_status() -> None:
    from edge.core.models import Region

    state = _world()
    state.regions = {1: Region(1, "Hub")}
    state.players[1] = replace(state.players[1], alliance_id=2, alliance_standing={1: -0.5})
    view = session.game_view(state, 1, CFG)
    assert view.governor == "Federation"
    assert view.core_status == "hunted"


# --- dev trigger + replay rail ------------------------------------------------


def test_dev_flip_governor_replays_to_an_identical_hash(tmp_path: Path) -> None:
    cfg = load_default_config()
    svc = GameService.new_game(cfg, 4, SqliteRepository(tmp_path / "g.db"))
    gov = svc.state.game.core_governing_alliance_id
    target = next(a for a in svc.state.alliances if a != gov)
    svc.apply(1, DevPatch(op="flip_governor", target="", value=target))
    assert svc.state.game.core_governing_alliance_id == target
    # Rebuild from (seed, command log) — the flip re-keying must reconstruct exactly.
    from edge.engine.cron import resolve_cron

    repo = svc._repo  # type: ignore[attr-defined]
    reloaded = rebuild(cfg, 4, repo.load_commands(), maintenance=repo.load_maintenance(),
                       cron_resolver=resolve_cron)
    assert state_hash(reloaded) == state_hash(svc.state)


def test_dev_flip_governor_rejects_an_unknown_alliance(tmp_path: Path) -> None:
    import pytest

    from edge.core.dev import DevPatchError

    svc = GameService.new_game(load_default_config(), 4, SqliteRepository(tmp_path / "g.db"))
    with pytest.raises(DevPatchError):
        reduce(svc.state, 1, DevPatch(op="flip_governor", target="", value=9999), svc.config)


# --- WP50: player-championed Core seizure ------------------------------------

import pytest

from edge.core.aliens import seizure_progress
from edge.core.economy import EconomyError
from edge.core.rules import AdvanceAdmission, JoinAlliance, PetitionCoreSeizure
from edge.server import session

# The default roster's covets_core bloc: Liberty Front (id 4) — price [prove, purge],
# bases_to_raze 2, fee 5000, joinable freely (membership_gate open).
LIBERTY = 4


def _seizure_world(*, razed: int = 2, latinum: int = 10_000) -> UniverseState:
    """Core sectors 1,2,3 (Federation planets + bases) + a Frontier tail; `razed` Core bases down."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t", core_governing_alliance_id=1))
    state.sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Hub", is_galactic_core=True),
        3: Sector(3, 1, (2, 4), "Hub", is_galactic_core=True),
        4: Sector(4, 1, (3,), "Frontier"),
    }
    state.rebuild_adjacency()
    state.alliances = {i: Alliance(i, f"A{i}", covets_core=(i == LIBERTY)) for i in (1, 2, 3, 4)}
    fed = Ownership("alliance", 1)
    for i in (1, 2, 3):
        state.planets[i] = Planet(i, i, f"Core-{i}", "terrestrial_warm", owner=fed, starbase_id=i)
        # A razed Core base reads as unowned (the _raze_starbase consequence, WP40).
        owner = Ownership("none") if i <= razed else fed
        state.starbases[i] = Starbase(i, i, i, "orbital_fort", owner=owner)
    state.ships[1] = Ship(1, "t", "P", 1, 4, 60)
    state.players[1] = Player(1, "you", 1, latinum, alliance_id=1, turns_remaining=250)
    return state


def _champion(state: UniverseState, *, tasks: tuple[str, ...] = ("prove", "purge")) -> None:
    """Join Liberty Front and record the seizure tasks (the pre-petition ladder)."""
    apply_result(state, reduce(state, 1, JoinAlliance(alliance_id=LIBERTY), CFG))
    for task in tasks:
        apply_result(state, reduce(state, 1, AdvanceAdmission(alliance_id=LIBERTY, task=task), CFG))


def test_seizure_happy_path_flips_the_core() -> None:
    state = _seizure_world()
    _champion(state)
    result = reduce(state, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)
    apply_result(state, result)
    assert state.game.core_governing_alliance_id == LIBERTY
    assert all(state.planets[i].owner == Ownership("alliance", LIBERTY) for i in (1, 2, 3))
    assert state.players[1].latinum == 10_000 - 5_000  # the fee was charged


def test_seizure_rejects_a_non_member() -> None:
    state = _seizure_world()  # player never joined Liberty Front
    with pytest.raises(EconomyError, match="sworn member"):
        reduce(state, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)


def test_seizure_rejects_unfinished_tasks() -> None:
    state = _seizure_world()
    _champion(state, tasks=("prove",))  # missing "purge"
    with pytest.raises(EconomyError, match="price is not yet paid"):
        reduce(state, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)


def test_seizure_rejects_when_too_few_bases_razed() -> None:
    state = _seizure_world(razed=1)  # only one of the two required Core bases is down
    _champion(state)
    with pytest.raises(EconomyError, match="still holds the Core"):
        reduce(state, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)


def test_seizure_rejects_an_unaffordable_fee() -> None:
    state = _seizure_world(latinum=100)  # cannot afford the 5000 fee
    _champion(state)
    with pytest.raises(EconomyError, match="seizure fee"):
        reduce(state, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)


def test_seizure_rejects_a_bloc_that_already_governs() -> None:
    state = _seizure_world()
    _champion(state)
    apply_result(state, reduce(state, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG))
    with pytest.raises(EconomyError, match="already governs"):
        reduce(state, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)


def test_seizure_checklist_matches_reducer_gating() -> None:
    # Ready state: the projection says ready and the petition succeeds (lockstep, H4).
    ready = _seizure_world()
    _champion(ready)
    cv = session.computer_view(ready, 1, CFG)
    assert cv.seizure is not None and cv.seizure.ready
    reduce(ready, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)  # does not raise

    # Not-ready state (a base short): the projection says not-ready and the petition raises.
    blocked = _seizure_world(razed=1)
    _champion(blocked)
    cv2 = session.computer_view(blocked, 1, CFG)
    assert cv2.seizure is not None and not cv2.seizure.ready and not cv2.seizure.bases_met
    with pytest.raises(EconomyError):
        reduce(blocked, 1, PetitionCoreSeizure(alliance_id=LIBERTY), CFG)


def test_seizure_ledger_records_under_the_reserved_key() -> None:
    state = _seizure_world()
    _champion(state, tasks=("prove",))
    prog = seizure_progress(state, state.players[1], CFG.roster.alliance(LIBERTY),
                            CFG.roster.alliance(LIBERTY).core_seizure)
    assert prog.tasks_done == frozenset({"prove"})  # recorded in the @seizure ledger


# --- WP51: NPC governance + leadership intrigue ------------------------------

from edge.core.enums import Subsystem
from edge.core.engine_room import build_layouts
from edge.core.events import AllianceLeadershipChanged, GovernanceChanged
from edge.core.governance import apply_intrigue, npc_seizure_ready
from edge.engine.cron import governance_tick

IRON = 3  # Iron Covenant — the roster's intrigue bloc (internal_rival vennrith, turns outward)


def _gov_config(*, seizure: float = 0.0, intrigue: float = 0.0,
                min_incumbent: int = 1, enabled: bool = True) -> object:
    base = load_default_config()
    gov = base.aliens.governance.model_copy(update={
        "enabled": enabled, "seizure_chance": seizure,
        "intrigue_chance": intrigue, "min_incumbent_bases": min_incumbent})
    return base.model_copy(update={"aliens": base.aliens.model_copy(update={"governance": gov})})


def _base(bid: int, sector: int, planet: int, owner: Ownership, *, operational: bool) -> Starbase:
    layouts = build_layouts(CFG.starbase.subsystems)
    if not operational:
        reactor = layouts[Subsystem.FUSION_REACTOR]
        slots = list(reactor.slots)
        slots[reactor.keystone_index] = None  # strip the keystone → derelict
        layouts[Subsystem.FUSION_REACTOR] = replace(reactor, slots=tuple(slots))
    return Starbase(id=bid, sector_id=sector, planet_id=planet, ship_class_id="orbital_platform",
                    owner=owner, subsystems=layouts)


def _gov_world(*, incumbent_operational: int = 0, coveter: int = LIBERTY) -> UniverseState:
    """Two Core planets+bases (Federation), `incumbent_operational` of them still live."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t", core_governing_alliance_id=1))
    state.sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Hub", is_galactic_core=True),
        3: Sector(3, 1, (2,), "Frontier"),
    }
    state.rebuild_adjacency()
    state.alliances = {i: Alliance(i, f"A{i}", covets_core=(i == coveter)) for i in (1, 2, 3, 4)}
    fed = Ownership("alliance", 1)
    for i in (1, 2):
        state.planets[i] = Planet(i, i, f"Core-{i}", "terrestrial_warm", owner=fed, starbase_id=i)
        state.starbases[i] = _base(i, i, i, fed, operational=(i <= incumbent_operational))
    return state


def test_npc_seizure_readiness_truth_table() -> None:
    cfg = _gov_config()
    broken = _gov_world(incumbent_operational=0)  # incumbent driven out of the Core
    assert npc_seizure_ready(broken, cfg, LIBERTY)          # coveter, Core broken → ready
    assert not npc_seizure_ready(broken, cfg, 2)            # a non-covets bloc is never ready
    assert not npc_seizure_ready(broken, cfg, 1)            # the incumbent cannot seize itself
    strong = _gov_world(incumbent_operational=1)            # a Core base still stands
    assert not npc_seizure_ready(strong, cfg, LIBERTY)      # not destabilized enough → not ready


def test_npc_seizure_readiness_needs_intact_home_bases() -> None:
    state = _gov_world(incumbent_operational=0)
    state.home_clusters = {LIBERTY: (3,)}
    state.planets[3] = Planet(3, 3, "Home", "barren", owner=Ownership("alliance", LIBERTY), starbase_id=3)
    state.starbases[3] = _base(3, 3, 3, Ownership("alliance", LIBERTY), operational=False)  # razed
    assert not npc_seizure_ready(state, _gov_config(), LIBERTY)  # its own strength is broken


def test_governance_tick_npc_seizure_flips_the_core() -> None:
    state = _gov_world(incumbent_operational=0)
    result = governance_tick(state, _gov_config(seizure=1.0))  # force the roll
    apply_result(state, result)
    assert state.game.core_governing_alliance_id == LIBERTY
    assert state.game.governance_seq == 1
    assert any(isinstance(e, GovernanceChanged) and e.cause == "npc_seizure" for e in result.events)
    assert all(state.planets[i].owner == Ownership("alliance", LIBERTY) for i in (1, 2))


def test_governance_tick_is_quiet_when_no_bloc_is_ready() -> None:
    state = _gov_world(incumbent_operational=2)  # incumbent Core intact → nobody ready
    result = governance_tick(state, _gov_config(seizure=1.0))
    assert not any(isinstance(e, GovernanceChanged) for e in result.events)
    assert result.game is not None and result.game.governance_seq == 1  # seq still advances


def _intrigue_world() -> UniverseState:
    """Iron Covenant (3) with a leader (thessarch) and its internal rival (vennrith)."""
    state = _gov_world(incumbent_operational=2)  # keep the incumbent strong: isolate intrigue

    def sp(sid: int, roster: str, role: str) -> AlienSpecies:
        return AlienSpecies(id=sid, roster_id=roster, name=roster.title(), archetype_id="a",
                            sector_id=3, home_band="Deep", tech_level=5, base_disposition=0.4,
                            disposition_center=0.4, disposition_variance=0.05,
                            alliance_id=IRON, alliance_role=role)
    state.species = {1: sp(1, "thessarch", "leader"), 2: sp(2, "vennrith", "member")}
    state.ships[1] = Ship(1, "t", "P", 1, 3, 60)
    state.players[1] = Player(1, "you", 1, 2_000, turns_remaining=250,
                              species_attitudes={"thessarch": 0.1, "vennrith": 0.1})
    return state


def test_governance_tick_intrigue_swaps_leadership_and_turns_the_bloc_outward() -> None:
    state = _intrigue_world()
    result = governance_tick(state, _gov_config(intrigue=1.0))
    apply_result(state, result)
    assert state.species[1].alliance_role == "member"   # thessarch demoted
    assert state.species[2].alliance_role == "leader"   # vennrith usurps
    assert state.alliances[IRON].covets_core is True    # intrigue_turns_outward
    assert any(isinstance(e, AllianceLeadershipChanged) and e.new_leader_roster == "vennrith"
               and e.old_leader_roster == "thessarch" for e in result.events)


def test_intrigue_is_idempotent_once_the_rival_leads() -> None:
    state = _intrigue_world()
    apply_result(state, governance_tick(state, _gov_config(intrigue=1.0)))
    # A second firing finds vennrith already leading → no-op (no event, no re-swap).
    again = governance_tick(state, _gov_config(intrigue=1.0))
    assert not any(isinstance(e, AllianceLeadershipChanged) for e in again.events)


def test_intrigue_never_invents_a_missing_rival() -> None:
    state = _gov_world(incumbent_operational=2)  # no species placed at all
    assert apply_intrigue(state, CFG.roster.alliance(IRON), {}) is None


def test_intrigue_follows_into_the_dossier() -> None:
    state = _intrigue_world()
    apply_result(state, governance_tick(state, _gov_config(intrigue=1.0)))
    roles = {e.species: e.role for e in session.computer_view(state, 1, CFG).dossier}
    assert roles.get("Vennrith") == "leader" and roles.get("Thessarch") == "member"


def test_governance_tick_is_deterministic_under_replay() -> None:
    def run() -> str:
        state = _intrigue_world()
        cfg = _gov_config(seizure=1.0, intrigue=1.0)
        for _ in range(3):
            apply_result(state, governance_tick(state, cfg))
        return state_hash(state)
    assert run() == run()


def test_governance_tick_disabled_is_inert() -> None:
    state = _gov_world(incumbent_operational=0)
    result = governance_tick(state, _gov_config(seizure=1.0, enabled=False))
    assert result.events == () and result.game is None  # nothing fires, seq untouched
