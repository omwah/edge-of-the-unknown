"""WP58 — the StarDock tavern: rumors, bounty board, noticeboard (DESIGN §14).

Rumors are a latinum-for-`Lead` sink drawn from the Core-welcome species' pooled knowledge
(deduped, so repeat buys exhaust); the noticeboard is a capped, sanitised ring. These tests
drive the reducers and the projection directly.
"""

from __future__ import annotations

from dataclasses import replace

from edge.config import load_default_config
from edge.core.enums import (
    Commodity,
    DiscoveryKind,
    PayloadKind,
    PortClass,
    PortMode,
    RarityTier,
)
from edge.core.models import (
    AlienSpecies,
    Discovery,
    DiscoveryPayload,
    Game,
    LocationRef,
    Notice,
    Player,
    Port,
    PortCommodity,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.economy import EconomyError
from edge.core.movement import MovementError
from edge.core.rules import BuyRumor, PostNotice, apply_result, reduce
from edge.server.session import tavern_view
from edge.store import codec
import pytest

CFG = load_default_config()


def _world() -> UniverseState:
    """A StarDock in sector 1 (player docked there) + a rare find out in sector 3."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Frontier"),
        3: Sector(3, 1, (2,), "Deep"),
    }
    state.rebuild_adjacency()
    state.core_hops = {1: 0, 2: 1, 3: 2}
    state.spatial_ids = {1: 1, 2: 2, 3: 3}
    state.ports = {
        9: Port(9, 1, "StarDock", PortClass.STARDOCK, 9, (
            PortCommodity(Commodity.FUEL_ORE, PortMode.BUY, 100, 5000, 11, 5),
        ), latinum=50_000),
    }
    # A rare discovery out in the Deep, known by a Core-welcome species.
    state.discoveries = {
        42: Discovery(id=42, kind=DiscoveryKind.RUINS, rarity_tier=RarityTier.RARE,
                      sector_id=3, payload=DiscoveryPayload(kind=PayloadKind.LATINUM, latinum=500)),
    }
    welcome = AlienSpecies(
        id=10, roster_id="terran", name="Terran", archetype_id="a", sector_id=1,
        home_band="Hub", tech_level=5, base_disposition=1.0,
        disposition_center=1.0, disposition_variance=0.0, alliance_id=1)
    state.species = {10: welcome}
    state.species_knowledge = {"terran": (LocationRef("discovery", 42, 3),)}
    state.ships = {1: Ship(id=1, type_id="trailblazer", name="TB", owner_player_id=1,
                           sector_id=1, holds_total=50, hull_current=100, hull_max=100,
                           shields=10, warp_speed=1, combat_speed=1, sensor_rating=100,
                           turns_per_warp=1)}
    state.players = {1: Player(id=1, name="Cap", ship_id=1, latinum=5000,
                               turns_remaining=100, alliance_id=1,
                               explored_sectors=frozenset({1}))}
    return state


# --- rumors ----------------------------------------------------------------------


def test_buy_rumor_logs_a_lead_and_charges() -> None:
    state = _world()
    before = state.players[1].latinum
    apply_result(state, reduce(state, 1, BuyRumor(), CFG))
    player = state.players[1]
    assert player.latinum == before - CFG.tavern.rumor_price
    assert len(player.leads) == 1 and player.leads[0].ref == 42
    assert player.leads[0].source_species == "tavern"


def test_rumor_exhausts_when_nothing_new() -> None:
    state = _world()
    apply_result(state, reduce(state, 1, BuyRumor(), CFG))  # logs the only tip
    # A second buy finds nothing fresh (the tip is already a lead) → rejected, no charge.
    with pytest.raises(EconomyError):
        reduce(state, 1, BuyRumor(), CFG)


def test_rumor_rejected_off_dock() -> None:
    state = _world()
    state.ships[1] = replace(state.ships[1], sector_id=2)  # not at the StarDock
    with pytest.raises((EconomyError, MovementError)):
        reduce(state, 1, BuyRumor(), CFG)


def test_tavern_view_reports_rumor_availability() -> None:
    state = _world()
    tav = tavern_view(state, 1, CFG)
    assert tav.rumor_available is True and tav.rumor_price == CFG.tavern.rumor_price
    apply_result(state, reduce(state, 1, BuyRumor(), CFG))
    assert tavern_view(state, 1, CFG).rumor_available is False  # exhausted


# --- noticeboard -----------------------------------------------------------------


def test_post_notice_appends_sanitised() -> None:
    state = _world()
    apply_result(state, reduce(state, 1, PostNotice(text="  fuel cheap\x07 in the Deep  "), CFG))
    assert len(state.notices) == 1
    assert state.notices[0].text == "fuel cheap in the Deep"  # trimmed + control char stripped
    assert state.notices[0].author_player_id == 1


def test_notice_ring_evicts_oldest() -> None:
    state = _world()
    cap = CFG.tavern.notice_cap
    state.notices = tuple(Notice(1, 1, f"old {i}") for i in range(cap))
    apply_result(state, reduce(state, 1, PostNotice(text="newest"), CFG))
    assert len(state.notices) == cap
    assert state.notices[-1].text == "newest"
    assert state.notices[0].text == "old 1"  # "old 0" evicted


def test_empty_notice_rejected() -> None:
    state = _world()
    with pytest.raises(EconomyError):
        reduce(state, 1, PostNotice(text="   \x00  "), CFG)


def test_tavern_view_lists_notices() -> None:
    state = _world()
    state.notices = (Notice(1, 3, "mine"), Notice(2, 4, "theirs"))
    tav = tavern_view(state, 1, CFG)
    assert [n.author for n in tav.notices] == ["You", "Captain #2"]
    assert tav.notices[0].text == "mine"


# --- codec -----------------------------------------------------------------------


def test_tavern_codec_round_trip() -> None:
    for cmd in (BuyRumor(), PostNotice(text="hi")):
        type_, payload = codec.encode_command(cmd)
        assert codec.decode_command(type_, payload) == cmd
