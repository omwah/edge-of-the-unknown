"""WP5 — discovery salting, the rarity/value gradient, detection, and salvage (§7)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.discovery import is_detectable, rarity_value
from edge.core.enums import PayloadKind, RarityTier
from edge.core.rules import Descend, Explore, Salvage, Warp, apply_result, reduce
from helpers import generate_with_player

CONFIG = load_default_config().model_copy(
    update={"bigbang": load_default_config().bigbang.model_copy(update={"sector_count": 120})}
)


def _do(state: object, command: object, pid: int = 1) -> object:
    result = reduce(state, pid, command, CONFIG)  # type: ignore[arg-type]
    apply_result(state, result)  # type: ignore[arg-type]
    return result


# --- placement / gradient ---------------------------------------------------


def test_discoveries_deterministic_from_seed() -> None:
    a = generate_with_player(CONFIG, 11)  # type: ignore[arg-type]
    b = generate_with_player(CONFIG, 11)  # type: ignore[arg-type]
    assert a.discoveries == b.discoveries and a.discoveries  # reproducible + non-empty


@pytest.mark.parametrize("seed", range(40))
def test_rarity_and_value_gradient_monotone(seed: int) -> None:
    """Mean rarity rank and value strictly increase across consecutive non-empty bands."""
    state = generate_with_player(CONFIG, seed)  # type: ignore[arg-type]
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
        state = generate_with_player(CONFIG, seed)  # type: ignore[arg-type]
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
    state = generate_with_player(CONFIG, 5)  # type: ignore[arg-type]
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
    state = generate_with_player(CONFIG, 2)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.LATINUM)  # Common → latinum
    _park_and_detect(state, disc)
    before = state.players[1].latinum
    _do(state, Salvage(discovery_id=disc.id))
    assert state.players[1].latinum == before + disc.payload.latinum
    assert disc.id in state.players[1].codex
    assert state.discoveries[disc.id].found_by == 1


def test_salvage_component_payload_into_hold() -> None:
    state = generate_with_player(CONFIG, 8)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.COMPONENT)
    _park_and_detect(state, disc)
    key = (disc.payload.component, disc.payload.tier)
    before = state.ships[1].components.get(key, 0)
    _do(state, Salvage(discovery_id=disc.id))
    assert state.ships[1].components.get(key, 0) == before + 1


def test_salvage_artifact_payload_into_barter_store() -> None:
    state = generate_with_player(CONFIG, 4)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.ARTIFACT)
    _park_and_detect(state, disc)
    tier = disc.payload.barter_tier
    before = state.players[1].artifacts.get(tier, 0)
    _do(state, Salvage(discovery_id=disc.id))
    assert state.players[1].artifacts.get(tier, 0) == before + 1


def test_double_salvage_rejected() -> None:
    state = generate_with_player(CONFIG, 2)  # type: ignore[arg-type]
    disc = _space_find(state, PayloadKind.LATINUM)
    _park_and_detect(state, disc)
    _do(state, Salvage(discovery_id=disc.id))
    codex_after_first = state.players[1].codex
    with pytest.raises(Exception):
        reduce(state, 1, Salvage(discovery_id=disc.id), CONFIG)  # already collected
    assert state.players[1].codex == codex_after_first  # codex unchanged (idempotent)


# --- WP6: planet descent & surface-site exploration -------------------------


def _planet_with_sites(min_sites: int = 2) -> tuple[object, int]:
    """First (state, planet_id) over seeds whose planet carries ≥ min_sites surface sites."""
    from collections import Counter

    for seed in range(40):
        state = generate_with_player(CONFIG, seed)  # type: ignore[arg-type]
        counts = Counter(d.planet_id for d in state.discoveries.values() if d.planet_id is not None)
        hit = next((pid for pid, n in counts.items() if n >= min_sites), None)
        if hit is not None:
            return state, hit
    raise AssertionError("no planet with enough surface sites found")


def _sites(state: object, pid: int) -> list[object]:
    return sorted((d for d in state.discoveries.values() if d.planet_id == pid),  # type: ignore[attr-defined]
                  key=lambda d: d.site_slot)


def test_descend_costs_turns() -> None:
    state, pid = _planet_with_sites()
    state.ships[1] = replace(state.ships[1], sector_id=state.planets[pid].sector_id)  # type: ignore[attr-defined]
    before = state.players[1].turns_remaining  # type: ignore[attr-defined]
    _do(state, Descend(planet_id=pid))
    assert state.players[1].turns_remaining == before - CONFIG.discovery.descent_turn_cost  # type: ignore[union-attr]


def test_explore_reveals_sites_one_at_a_time_then_log() -> None:
    state, pid = _planet_with_sites()
    state.ships[1] = replace(state.ships[1], sector_id=state.planets[pid].sector_id, sensor_rating=9)  # type: ignore[attr-defined]
    sites = _sites(state, pid)
    assert all(s.id not in state.players[1].detected for s in sites)  # nothing surveyed yet

    revealed = 0
    for _ in sites:  # each Explore reveals exactly one more (sensors clear all here)
        _do(state, Explore(planet_id=pid))
        now = sum(1 for s in sites if s.id in state.players[1].detected)
        assert now == revealed + 1
        revealed = now
    with pytest.raises(Exception):  # nothing left to survey
        reduce(state, 1, Explore(planet_id=pid), CONFIG)

    first = sites[0]
    _do(state, Salvage(discovery_id=first.id))
    assert first.id in state.players[1].codex and state.discoveries[first.id].found_by == 1


def test_salvage_unexplored_surface_site_rejected() -> None:
    state, pid = _planet_with_sites(min_sites=1)
    state.ships[1] = replace(state.ships[1], sector_id=state.planets[pid].sector_id, sensor_rating=9)  # type: ignore[attr-defined]
    site = _sites(state, pid)[0]
    with pytest.raises(Exception):  # must Explore before you can log it
        reduce(state, 1, Salvage(discovery_id=site.id), CONFIG)


def test_explore_sensor_gates_hidden_surface_sites() -> None:
    """At weak sensors the obvious sites survey but Rare+ sites stay unresolved (§7)."""
    from collections import defaultdict

    state = pid = None  # type: ignore[assignment]
    for seed in range(60):
        st = generate_with_player(CONFIG, seed)  # type: ignore[arg-type]
        by_planet: dict[int, list[object]] = defaultdict(list)
        for d in st.discoveries.values():
            if d.planet_id is not None:
                by_planet[d.planet_id].append(d)
        hit = next((p for p, ds in by_planet.items()
                    if any(d.hidden for d in ds) and any(not d.hidden for d in ds)), None)
        if hit is not None:
            state, pid = st, hit
            break
    assert state is not None and pid is not None

    state.ships[1] = replace(state.ships[1], sector_id=state.planets[pid].sector_id, sensor_rating=1)
    sites = _sites(state, pid)
    obvious = [d for d in sites if not d.hidden]
    hidden = [d for d in sites if d.hidden]
    for _ in obvious:  # weak sensors still resolve every obvious site
        _do(state, Explore(planet_id=pid))
    assert all(o.id in state.players[1].detected for o in obvious)
    assert all(h.id not in state.players[1].detected for h in hidden)  # Rare+ stay hidden
    with pytest.raises(Exception):  # sensors too weak for what remains
        reduce(state, 1, Explore(planet_id=pid), CONFIG)
