"""WP10 — Genesis torpedoes: buy at StarDock, terraform an eligible world (§4.2)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.enums import PortClass
from edge.core.events import GenesisDeployed
from edge.core.planets import is_colonizable
from edge.core.rules import BuyGenesis, DeployGenesis, apply_result, reduce

CONFIG = load_default_config().model_copy(
    update={"bigbang": load_default_config().bigbang.model_copy(update={"sector_count": 120})}
)
_DEVICE = CONFIG.genesis.device_id  # type: ignore[union-attr]


def _do(state: object, command: object) -> object:
    result = reduce(state, 1, command, CONFIG)  # type: ignore[arg-type]
    apply_result(state, result)  # type: ignore[arg-type]
    return result


def _at_stardock(state: object) -> None:
    dock = next(p for p in state.ports.values() if p.klass is PortClass.STARDOCK)  # type: ignore[attr-defined]
    state.ships[1] = replace(state.ships[1], sector_id=dock.sector_id)  # type: ignore[attr-defined]
    state.players[1] = replace(state.players[1], latinum=50_000)  # type: ignore[attr-defined]


def _eligible_planet(state: object) -> object:
    return next(pl for pl in state.planets.values()  # type: ignore[attr-defined]
                if not pl.owner.is_owned and pl.planet_type in CONFIG.genesis.eligible_types)  # type: ignore[union-attr]


def test_buy_genesis_at_stardock_costs_latinum() -> None:
    state = generate(CONFIG, 7)  # type: ignore[arg-type]
    _at_stardock(state)
    before = state.players[1].latinum
    _do(state, BuyGenesis())
    assert state.ships[1].devices.get(_DEVICE, 0) == 1
    assert state.players[1].latinum == before - CONFIG.genesis.price  # type: ignore[union-attr]


def test_buy_genesis_requires_stardock() -> None:
    state = generate(CONFIG, 7)  # type: ignore[arg-type]
    # Sit somewhere that isn't a StarDock.
    state.players[1] = replace(state.players[1], latinum=50_000)
    state.ships[1] = replace(state.ships[1], sector_id=1)
    with pytest.raises(Exception):
        reduce(state, 1, BuyGenesis(), CONFIG)


def test_deploy_genesis_retypes_eligible_world() -> None:
    state = generate(CONFIG, 7)  # type: ignore[arg-type]
    planet = _eligible_planet(state)
    assert not is_colonizable(planet.planet_type, CONFIG)  # a dead world to start
    state.ships[1] = replace(state.ships[1], sector_id=planet.sector_id, devices={_DEVICE: 1})
    result = _do(state, DeployGenesis(planet_id=planet.id))

    after = state.planets[planet.id]
    assert after.planet_type == CONFIG.genesis.result_type  # type: ignore[union-attr]
    assert is_colonizable(after.planet_type, CONFIG)  # now claimable
    assert after.habitability_cap > 0 and after.yield_profile
    assert state.ships[1].devices.get(_DEVICE, 0) == 0  # torpedo consumed
    assert isinstance(result.events[0], GenesisDeployed)


def test_deploy_genesis_rejects_without_torpedo() -> None:
    state = generate(CONFIG, 7)  # type: ignore[arg-type]
    planet = _eligible_planet(state)
    state.ships[1] = replace(state.ships[1], sector_id=planet.sector_id, devices={})
    with pytest.raises(Exception):
        reduce(state, 1, DeployGenesis(planet_id=planet.id), CONFIG)


def test_deploy_genesis_rejects_owned_world() -> None:
    state = generate(CONFIG, 7)  # type: ignore[arg-type]
    owned = next(pl for pl in state.planets.values() if pl.owner.is_owned)
    state.ships[1] = replace(state.ships[1], sector_id=owned.sector_id, devices={_DEVICE: 1})
    with pytest.raises(Exception):
        reduce(state, 1, DeployGenesis(planet_id=owned.id), CONFIG)
