"""DevPatch dev/testing command — reducer behaviour + replay determinism.

Proves the cheat command mutates as specified, validates its targets, and — the
key property — replays identically from `(seed, command log)` so a cheated save
reconstructs exactly on reload (DESIGN §3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edge.config import GameConfig, load_default_config
from edge.core.dev import DevPatch, DevPatchError
from edge.core.enums import Component, ComponentTier
from edge.core.events import DevApplied
from edge.core.models import UniverseState
from edge.core.rules import apply_result, reduce
from edge.server.service import GameService
from edge.store.codec import (
    decode_command,
    decode_event,
    encode_command,
    encode_event,
)
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash
from helpers import generate_with_player

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> GameConfig:
    cfg = load_default_config()
    return cfg.model_copy(
        update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})}
    )


def _state() -> tuple[UniverseState, GameConfig]:
    config = _config()
    return generate_with_player(config, 42, created_at=_CREATED), config


def _apply(state: UniverseState, config: GameConfig, patch: DevPatch) -> None:
    apply_result(state, reduce(state, 1, patch, config))


def test_set_and_add_latinum() -> None:
    state, config = _state()
    result = reduce(state, 1, DevPatch("set", "latinum", 1_000_000), config)
    assert result.players[0].latinum == 1_000_000
    assert any(isinstance(e, DevApplied) for e in result.events)

    _apply(state, config, DevPatch("set", "latinum", 1000))
    _apply(state, config, DevPatch("add", "latinum", 250))
    assert state.players[1].latinum == 1250


def test_negative_clamps_to_zero() -> None:
    state, config = _state()
    _apply(state, config, DevPatch("set", "latinum", -5))
    assert state.players[1].latinum == 0


def test_grant_loose_component() -> None:
    state, config = _state()
    _apply(state, config, DevPatch("grant", "component", 3, key="accelerator:II"))
    assert state.ships[1].components[(Component.ACCELERATOR, ComponentTier.II)] == 3


def test_grant_artifact_and_device() -> None:
    state, config = _state()
    _apply(state, config, DevPatch("grant", "artifact", 2, key="III"))
    _apply(state, config, DevPatch("grant", "device", 1, key="genesis_torpedo"))
    assert state.players[1].artifacts["III"] == 2
    assert state.ships[1].devices["genesis_torpedo"] == 1


def test_teleport_moves_and_explores() -> None:
    state, config = _state()
    target = sorted(state.sectors)[5]
    _apply(state, config, DevPatch("teleport", "sector", target))
    assert state.ships[1].sector_id == target
    assert target in state.players[1].explored_sectors


def test_teleport_unknown_sector_raises() -> None:
    state, config = _state()
    with pytest.raises(DevPatchError):
        reduce(state, 1, DevPatch("teleport", "sector", 10**9), config)


def test_claim_planet() -> None:
    state, config = _state()
    pid = min(state.planets)
    _apply(state, config, DevPatch("claim", "planet", ref=pid))
    assert state.planets[pid].owner.kind == "player"
    assert state.planets[pid].owner.ref == 1


def test_claim_unknown_planet_raises() -> None:
    state, config = _state()
    with pytest.raises(DevPatchError):
        reduce(state, 1, DevPatch("claim", "planet", ref=10**9), config)


def test_colonists_over_capacity_raises() -> None:
    state, config = _state()
    cap = state.ships[1].colonist_capacity
    with pytest.raises(DevPatchError):
        reduce(state, 1, DevPatch("set", "ship.colonists", cap + 1), config)


def test_holds_below_used_raises() -> None:
    state, config = _state()
    _apply(state, config, DevPatch("cargo", "fuel_ore", 5))  # occupy 5 holds
    with pytest.raises(DevPatchError):
        reduce(state, 1, DevPatch("set", "ship.holds_total", 4), config)


def test_unknown_patch_raises() -> None:
    state, config = _state()
    with pytest.raises(DevPatchError):
        reduce(state, 1, DevPatch("frobnicate", "everything", 1), config)


def test_devpatch_survives_reload(tmp_path: Path) -> None:
    """The golden-master rail: a DevPatch replays to an identical state hash."""
    config = _config()
    repo = SqliteRepository(tmp_path / "game.db")
    svc = GameService.new_game(config, 42, repo, created_at=_CREATED)
    svc.apply(1, DevPatch("set", "latinum", 1_000_000))
    svc.apply(1, DevPatch("grant", "component", 2, key="accelerator:II"))
    expected = state_hash(svc.state)

    meta = repo.load_meta()
    reloaded = rebuild(config, meta.seed, repo.load_commands(), created_at=meta.created_at)
    assert state_hash(reloaded) == expected
    assert reloaded.players[1].latinum == 1_000_000
    repo.close()


def test_codec_round_trip() -> None:
    for patch in (
        DevPatch("set", "latinum", 1_000_000),
        DevPatch("grant", "component", 4, key="accelerator:III"),
        DevPatch("claim", "planet", ref=7),
        DevPatch("teleport", "sector", 12),
    ):
        assert decode_command(*encode_command(patch)) == patch
    event = DevApplied(1, "[dev] set latinum=1000000")
    assert decode_event(*encode_event(event)) == event
