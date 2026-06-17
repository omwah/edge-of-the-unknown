"""WP5 — discovery salting, the rarity/value gradient, detection, and salvage (§7)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.discovery import is_detectable, rarity_value
from edge.core.enums import PayloadKind, RarityTier
from edge.core.rules import Salvage, Warp, apply_result, reduce

CONFIG = load_default_config().model_copy(
    update={"bigbang": load_default_config().bigbang.model_copy(update={"sector_count": 120})}
)


def _do(state: object, command: object, pid: int = 1) -> object:
    result = reduce(state, pid, command, CONFIG)  # type: ignore[arg-type]
    apply_result(state, result)  # type: ignore[arg-type]
    return result


# --- placement / gradient ---------------------------------------------------


def test_discoveries_deterministic_from_seed() -> None:
    a = generate(CONFIG, 11)  # type: ignore[arg-type]
    b = generate(CONFIG, 11)  # type: ignore[arg-type]
    assert a.discoveries == b.discoveries and a.discoveries  # reproducible + non-empty


@pytest.mark.parametrize("seed", range(40))
def test_rarity_and_value_gradient_monotone(seed: int) -> None:
    """Mean rarity rank and value strictly increase across consecutive non-empty bands."""
    state = generate(CONFIG, seed)  # type: ignore[arg-type]
    by_band: dict[str, list[tuple[int, int]]] = {}
    for d in state.discoveries.values():
        band = state.sectors[d.sector_id].distance_band
        by_band.setdefault(band, []).append((d.rarity_tier.value, rarity_value(d.rarity_tier, CONFIG)))
    prev_rank = prev_value = -1.0
    for band in (b.name for b in CONFIG.bigbang.bands):  # type: ignore[attr-defined]
        finds = by_band.get(band)
        if not finds:
            continue
        mean_rank = sum(r for r, _ in finds) / len(finds)
        mean_value = sum(v for _, v in finds) / len(finds)
        assert mean_rank > prev_rank and mean_value > prev_value
        prev_rank, prev_value = mean_rank, mean_value


# --- detection (the sensor gate) --------------------------------------------


def _hidden_find_with_neighbor(seeds: range) -> tuple[object, object, int]:
    """First (state, hidden high-tier find, two-way neighbour sector) over `seeds`."""
    for seed in seeds:
        state = generate(CONFIG, seed)  # type: ignore[arg-type]
        for d in state.discoveries.values():
            if not (d.hidden and d.planet_id is None and d.rarity_tier.value >= 3):
                continue
            nbr = next((n for n in state.sectors[d.sector_id].warps_out
                        if d.sector_id in state.sectors[n].warps_out), None)
            if nbr is not None:
                return state, d, nbr
    raise AssertionError("no suitable hidden find found")


def test_sensor_gate_requires_reentry_after_upgrade() -> None:
    """Detection snapshots on entry: a hidden find stays unseen after a sensor upgrade
    until the player re-enters the sector (§7)."""
    state, disc, nbr = _hidden_find_with_neighbor(range(40))

    # Enter with weak sensors — the high-tier find isn't detected.
    state.ships[1] = replace(state.ships[1], sector_id=nbr, sensor_rating=1)
    _do(state, Warp(to_sector=disc.sector_id))
    assert disc.id not in state.players[1].detected
    with pytest.raises(Exception):  # can't log what wasn't detected
        reduce(state, 1, Salvage(discovery_id=disc.id), CONFIG)

    # Upgrade sensors but DON'T re-enter — still undetected (the snapshot stands).
    state.ships[1] = replace(state.ships[1], sensor_rating=9)
    assert disc.id not in state.players[1].detected

    # Re-enter (warp out, warp back) — now the stronger sensors pick it up.
    _do(state, Warp(to_sector=nbr))
    _do(state, Warp(to_sector=disc.sector_id))
    assert disc.id in state.players[1].detected
    _do(state, Salvage(discovery_id=disc.id))
    assert disc.id in state.players[1].codex


def test_nebula_interference_lowers_detection() -> None:
    """The nebula penalty pushes a marginal hidden find back under the threshold."""
    state = generate(CONFIG, 5)  # type: ignore[arg-type]
    tier = RarityTier.RARE
    difficulty = CONFIG.discovery.sensor_difficulty[tier.name]  # type: ignore[union-attr]
    disc = next(d for d in state.discoveries.values()
                if d.hidden and d.rarity_tier is tier)
    sensor_at_threshold = difficulty  # exactly clears it in clear space
    assert is_detectable(disc, sensor_at_threshold, in_nebula=False, config=CONFIG)
    assert not is_detectable(disc, sensor_at_threshold, in_nebula=True, config=CONFIG)


# --- salvage (collection) ---------------------------------------------------


def _space_find(state: object, payload_kind: PayloadKind) -> object:
    return next(d for d in state.discoveries.values()  # type: ignore[attr-defined]
                if d.planet_id is None and d.payload.kind is payload_kind)


def _park_and_detect(state: object, disc: object) -> None:
    """Place the ship on the find and mark it detected (these tests assert payload
    handling, not the entry-detection gate, which has its own test)."""
    state.ships[1] = replace(  # type: ignore[attr-defined]
        state.ships[1], sector_id=disc.sector_id, sensor_rating=9)  # type: ignore[attr-defined]
    state.players[1] = replace(  # type: ignore[attr-defined]
        state.players[1], detected=state.players[1].detected | frozenset({disc.id}))  # type: ignore[attr-defined]


def test_salvage_latinum_payload_credits_purse_and_logs_codex() -> None:
    state = generate(CONFIG, 2)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.LATINUM)  # Common → latinum
    _park_and_detect(state, disc)
    before = state.players[1].latinum
    _do(state, Salvage(discovery_id=disc.id))
    assert state.players[1].latinum == before + disc.payload.latinum
    assert disc.id in state.players[1].codex
    assert state.discoveries[disc.id].found_by == 1


def test_salvage_component_payload_into_hold() -> None:
    state = generate(CONFIG, 8)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.COMPONENT)
    _park_and_detect(state, disc)
    key = (disc.payload.component, disc.payload.tier)
    before = state.ships[1].components.get(key, 0)
    _do(state, Salvage(discovery_id=disc.id))
    assert state.ships[1].components.get(key, 0) == before + 1


def test_salvage_artifact_payload_into_barter_store() -> None:
    state = generate(CONFIG, 4)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.ARTIFACT)
    _park_and_detect(state, disc)
    tier = disc.payload.barter_tier
    before = state.players[1].artifacts.get(tier, 0)
    _do(state, Salvage(discovery_id=disc.id))
    assert state.players[1].artifacts.get(tier, 0) == before + 1


def test_double_salvage_rejected() -> None:
    state = generate(CONFIG, 2)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.LATINUM)
    _park_and_detect(state, disc)
    _do(state, Salvage(discovery_id=disc.id))
    codex_after_first = state.players[1].codex
    with pytest.raises(Exception):
        reduce(state, 1, Salvage(discovery_id=disc.id), CONFIG)  # already collected
    assert state.players[1].codex == codex_after_first  # codex unchanged (idempotent)
