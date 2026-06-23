"""Shared test helpers.

The big bang no longer seeds players — enrolling a player is a `JoinGame` command
(DESIGN §3). Tests that build a `UniverseState` directly via `generate()` and then
read `state.players[1]` use these to get the same starter player `new_game` produces.
"""

from __future__ import annotations

from typing import Any

from edge.bigbang.generator import generate
from edge.core.config import GameConfig
from edge.core.models import UniverseState
from edge.core.rules import JoinGame, apply_result, reduce


def enroll(state: UniverseState, config: GameConfig, player_id: int = 1) -> UniverseState:
    """Enroll a player into an already-generated universe (mutates + returns `state`)."""
    apply_result(state, reduce(state, player_id, JoinGame(), config))
    return state


def generate_with_player(
    config: GameConfig, seed: int, *, player_id: int = 1, **kwargs: Any
) -> UniverseState:
    """`generate()` then `enroll()` — the common "fresh game with player 1" setup."""
    return enroll(generate(config, seed, **kwargs), config, player_id)
