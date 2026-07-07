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
