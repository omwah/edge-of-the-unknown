"""WP62 — the versioned wire codec (DESIGN §3/§14, H16).

Every command, event, and DTO must round-trip through the wire unchanged (the wire and the
durable log speak one dialect); the fingerprint must be stable (a protocol break is a diff in
review); and malformed/mismatched envelopes must reject loudly.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from edge.config import load_default_config
from edge.core import dto
from edge.server import wire
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from test_codec import COMMANDS, EVENTS

_FIXTURES = Path(__file__).parent / "fixtures" / "wire"


# --- commands / events (reuse the exhaustive codec fixtures) ------------------


@pytest.mark.parametrize("command", COMMANDS)
def test_command_round_trips(command: object) -> None:
    msg = wire.encode_command(command)  # type: ignore[arg-type]
    assert msg["v"] == wire.WIRE_VERSION and msg["kind"] == "command"
    assert wire.decode_command(msg) == command


@pytest.mark.parametrize("event", EVENTS)
def test_event_round_trips(event: object) -> None:
    msg = wire.encode_event(event)  # type: ignore[arg-type]
    assert msg["v"] == wire.WIRE_VERSION and msg["kind"] == "event"
    assert wire.decode_event(msg) == event


# --- DTOs (collected live + hand-built) --------------------------------------


def _config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"sector_count": 90, "start_sector": 1})})


def _collect_dtos(root: Any, seen: dict[str, Any]) -> None:
    """Recursively gather one instance per DTO class reachable from `root`."""
    if dataclasses.is_dataclass(root) and not isinstance(root, type):
        seen.setdefault(type(root).__name__, root)
        for f in dataclasses.fields(root):
            _collect_dtos(getattr(root, f.name), seen)
    elif isinstance(root, (list, tuple, frozenset)):
        for item in root:
            _collect_dtos(item, seen)


def _live_dtos() -> dict[str, Any]:
    """Project a real game through every view and collect the DTO instances produced."""
    svc = GameService.new_game(_config(), 42, SqliteRepository(Path("/tmp/_wire_probe.db")),  # noqa: S108
                               created_at="2026-06-15T00:00:00Z")
    seen: dict[str, Any] = {}
    for view in (
        svc.game_view(1), svc.computer_view(1), svc.map_view(1), svc.stardock_view(1),
        svc.engine_room_view(1), svc.tavern_view(1), svc.market_view(1), svc.messages_view(1),
    ):
        _collect_dtos(view, seen)
    for planet in svc.state.planets.values():
        _collect_dtos(svc.planet_view(1, planet.id), seen)
        _collect_dtos(svc.surface_view(1, planet.id), seen)
    for port in svc.state.ports.values():
        _collect_dtos(svc.port_view(1, port.id), seen)
    return seen


def test_dto_round_trips_cover_live_projections() -> None:
    live = _live_dtos()
    assert live, "no DTOs collected from live projections"
    for name, instance in live.items():
        msg = wire.encode_dto(instance)
        assert msg["kind"] == "dto"
        assert wire.decode_dto(msg) == instance, f"{name} did not round-trip"


def test_hand_built_dtos_round_trip() -> None:
    # Cover container shapes not always reachable from a fresh game: a fixed tuple field
    # (citadel_next_cost), tuple-list fields (stores/salvage), and a non-empty frozenset.
    samples = [
        dto.PlanetDTO(
            planet_id=5, name="Kestrel", ptype="terrestrial_warm", owner="you",
            colonizable=True, claimable=False, owned_by_you=True, colonists=1000,
            habitability_cap=5000, stores=[("Fuel Ore", 10), ("Organics", 5)],
            allocation=[("Fuel Ore", 50), ("Organics", 50)], ship_colonists=0,
            ship_colonist_capacity=100, citadel_next_cost=(300, 5000),
        ),
        dto.StarbaseDTO(
            starbase_id=4, name="Orbital Platform", sector_display=61, planet_id=5,
            planet_name="Kestrel", owner="yours", standing="yours", operational=True,
            integrity_pct=80,
            subsystems=[dto.Subsystem(name="FUSION REACTOR", derived="3/3 live",
                                      slots=[dto.Slot(state="filled", component="converter",
                                                      keystone=True)])],
            salvage=[("main_gun", 2, "linkage")], empty_slots=[("screens", 1, False)],
            claimable=False, claim_cost=10_000, assaultable=False,
            market_port_id=7, market_name="Foothold Market", market_open=True,
            market_notice="", trade_cut_pct=5, services=["components"], fee_frac=1.25,
            hardware=[dto.HardwareItem(component="converter", tier="I", price=1250,
                                       affordable=True)],
            missile_price=125, latinum=1000, bank_balance=0,
        ),
        dto.MapNodeDTO(sector_id=3, display_id=3, row=0, col0=0, col1=1,
                       neighbors=frozenset({1, 2, 4})),
    ]
    for instance in samples:
        assert wire.decode_dto(wire.encode_dto(instance)) == instance


def test_registry_covers_every_dto_class() -> None:
    declared = {n for n, o in vars(dto).items()
                if isinstance(o, type) and dataclasses.is_dataclass(o) and o.__module__ == dto.__name__}
    assert declared == set(wire.DTO_REGISTRY), "a dto.py dataclass is missing from DTO_REGISTRY"


# --- fingerprint + rejection paths -------------------------------------------


def test_fingerprint_is_stable() -> None:
    golden = (_FIXTURES / "fingerprint.txt").read_text().strip()
    assert wire.wire_fingerprint() == golden, (
        "wire fingerprint changed — a command/event/DTO schema moved. If intentional, bump "
        "WIRE_VERSION and regenerate tests/fixtures/wire/fingerprint.txt."
    )


def test_golden_envelopes_stable() -> None:
    golden = json.loads((_FIXTURES / "envelopes.json").read_text())
    from test_codec import COMMANDS as _CMDS, EVENTS as _EVTS
    assert wire.encode_command(_CMDS[0]) == golden["command"]
    assert wire.encode_event(_EVTS[0]) == golden["event"]
    # And a sample DTO envelope is byte-stable (a shape drift is a review diff).
    sample = dto.MapNodeDTO(sector_id=3, display_id=3, row=0, col0=0, col1=1,
                            neighbors=frozenset({1, 2, 4}))
    assert wire.encode_dto(sample) == golden["dto"]


def test_bad_version_rejected() -> None:
    msg = wire.encode_command(COMMANDS[2])
    msg["v"] = 999
    with pytest.raises(wire.WireError):
        wire.decode_command(msg)


def test_wrong_kind_rejected() -> None:
    msg = wire.encode_event(EVENTS[0])
    with pytest.raises(wire.WireError):
        wire.decode_command(msg)  # an event envelope handed to the command decoder


def test_unregistered_dto_rejected() -> None:
    @dataclasses.dataclass(frozen=True)
    class Rogue:
        x: int

    with pytest.raises(wire.WireError):
        wire.encode_dto(Rogue(1))
