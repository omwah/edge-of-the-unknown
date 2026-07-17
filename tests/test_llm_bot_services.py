"""Computer intel and service-point actions exposed to the LLM pilot."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from edge.bot.llm.actions import ActionCatalog
from edge.bot.llm.describe import _computer, _engine_room, _starbase, _stardock
from edge.core import dto
from edge.core.enums import Component, ComponentTier, Subsystem
from edge.core.rules import BuyComponent, BuyRumor, Deposit, Dock, InstallComponent, RecruitColonists


def _computer_view() -> dto.ComputerDTO:
    return dto.ComputerDTO(
        pairs=[], selected="",
        ports=[dto.PortDirEntry(
            port_id=1, sector_id=10, sector_display=3, name="Sol Stardock",
            klass="Stardock", buys="Fuel, Org, Equ", sells="Fuel, Org, Equ", dist=12,
        )],
        planets=[dto.PlanetDirEntry(
            planet_id=7, sector_id=70, sector_display=17, name="Far Hope",
            ptype="terrestrial_cool", owner="unowned", colonists=0, species="—",
            stores="Fuel 0 Org 0 Equ 0", dist=3, citadel_level=2,
            starbase_status="operational",
        ), dto.PlanetDirEntry(
            planet_id=8, sector_id=80, sector_display=18, name="Cloud Rest",
            ptype="jovian", owner="you", colonists=500, species="—",
            stores="Fuel 50 Org 0 Equ 0", dist=4, cloud_city_size=3,
        )],
        codex=[dto.CodexEntry(
            name="Silent Kestrel", location="Sector 12", rarity="Rare",
            detail="recovered navigation core", kind="wreck · RARE",
        )],
        leads=[dto.LeadDTO(
            summary="an old relay beyond the frontier", source="tavern", coords=44,
            distance=5, turn_cost=7, reachable=True,
        )],
        contracts=[dto.ContractDTO(
            contract_id=4, kind="deliver", issuer="selvani",
            summary="deliver equipment to Far Hope", reward=2_000,
            deadline_day=8, dest_display=17,
        )],
    )


def _hardware() -> list[dto.HardwareItem]:
    return [dto.HardwareItem("converter", "II", 4_000, True)]


def _base() -> dto.StarbaseDTO:
    return dto.StarbaseDTO(
        starbase_id=9, name="Orbital Platform", sector_display=17, planet_id=7,
        planet_name="Far Hope", owner="you", standing="yours", operational=True,
        services_operational=True, service_integrity_min_pct=70, integrity_pct=100,
        subsystems=[], salvage=[], empty_slots=[], claimable=False, claim_cost=0,
        assaultable=False, market_port_id=3, market_name="Far Hope Exchange",
        market_open=True, market_notice="", trade_cut_pct=5,
        services=["components", "banking"], fee_frac=1.2, hardware=_hardware(),
        missile_price=100, latinum=8_000, bank_balance=2_500,
    )


def _dock() -> dto.StardockDTO:
    return dto.StardockDTO(
        sector_display=1, latinum=8_000, hardware=_hardware(), shipyard=[],
        bank_balance=2_500, interest_per_day=0.005, colonist_incentive=5,
        ship_colonists=10, ship_colonist_capacity=50, colonists_recruitable=40,
    )


def _room() -> dto.EngineRoomDTO:
    return dto.EngineRoomDTO(
        ship="Trailblazer", efficiency_bonus="+0", kits=0,
        on_hand=["converter (II) x1"],
        subsystems=[dto.Subsystem(
            name="SPINDRIVE", derived="warp 3",
            slots=[dto.Slot(state="filled", component="converter (I)"),
                   dto.Slot(state="empty")],
        )],
    )


def test_computer_description_includes_planets_codex_and_leads() -> None:
    lines: list[str] = []
    _computer(lines, _computer_view())
    text = "\n".join(lines)
    assert "Stardock location: sector 3 (12 hops)" in text
    assert "travel_to with this sector" in text
    assert "Known planet: planet_id 7" in text and "sector 17" in text
    assert "colony Citadel L2 · starbase operational" in text
    assert "Known planet: planet_id 8" in text
    assert "colony Cloud City size 3 · starbase none" in text
    assert "Codex: Silent Kestrel" in text
    assert "Lead: sector 44" in text and "5 hops / 7 turns" in text
    assert "Contract 4:" in text and "destination sector 17" in text


def test_service_descriptions_expose_hardware_bank_colonists_and_rumor() -> None:
    lines: list[str] = []
    _starbase(lines, _base())
    _stardock(lines, _dock(), dto.TavernDTO(rumor_price=500, rumor_available=True))
    _engine_room(lines, _room())
    text = "\n".join(lines)
    assert "BOARDED STARBASE 9" in text
    assert "A starbase is not Stardock" in text
    assert "no colonist recruitment, tavern, rumor, or shipyard" in text
    assert "Stardock only: colonist recruitment, tavern rumors, and shipyard" in text
    assert "Hardware offer_index 0: converter tier II" in text
    assert "Bank: 2,500 slips deposited" in text
    assert "up to 40 recruitable" in text
    assert "Tavern rumor: available for 500 slips" in text
    assert "install_component {subsystem, slot_index, offer_index}" in text


class _Service:
    def __init__(self) -> None:
        self.commands: list[object] = []

    def encounter_view(self, _player_id: int) -> None:
        return None

    def describe_event(self, _event: object) -> str:
        return "done"

    def leads_view(self, _player_id: int) -> list[dto.LeadDTO]:
        return [dto.LeadDTO("a fresh lead", "tavern", 44, 5, 7, True)]


class _Bot:
    def __init__(self, *, at_stardock: bool = False) -> None:
        self.player_id = 1
        self.last_error: str | None = None
        self.service = _Service()
        self._base = None if at_stardock else _base()
        port = SimpleNamespace(is_stardock=True) if at_stardock else None
        self._game = SimpleNamespace(
            sector=SimpleNamespace(sector_id=1, ports=[port] if port else []),
        )

    def game(self) -> Any:
        return self._game

    def current_starbase(self) -> dto.StarbaseDTO | None:
        return self._base

    def stardock(self) -> dto.StardockDTO:
        return _dock()

    def engine_room(self) -> dto.EngineRoomDTO:
        return _room()

    def apply(self, command: object) -> tuple[object, ...]:
        self.service.commands.append(command)
        return (object(),)


def _decision(action: str, **values: object) -> dict[str, object]:
    return {"action": action, **values}


def test_boarded_starbase_supports_hardware_install_and_banking() -> None:
    bot = _Bot()
    catalog = ActionCatalog(bot)  # type: ignore[arg-type]
    assert catalog.execute(_decision("dock_starbase", starbase_id=9)).ok
    assert catalog.boarded_starbase_id == 9

    assert catalog.execute(_decision("buy_component", offer_index=0)).ok
    bought = bot.service.commands[-1]
    assert isinstance(bought, BuyComponent)
    assert (bought.component, bought.tier) == (Component.CONVERTER, ComponentTier.II)
    assert catalog.execute(_decision(
        "install_component", subsystem="spindrive", slot_index=1, offer_index=0,
    )).ok
    installed = bot.service.commands[-1]
    assert isinstance(installed, InstallComponent)
    assert (installed.subsystem, installed.slot_index, installed.component, installed.tier) == (
        Subsystem.SPINDRIVE, 1, Component.CONVERTER, ComponentTier.II,
    )
    assert catalog.execute(_decision("deposit", count=1_000)).ok
    deposited = bot.service.commands[-1]
    assert isinstance(deposited, Deposit) and deposited.amount == 1_000


def test_stardock_supports_colonists_and_rumors() -> None:
    bot = _Bot(at_stardock=True)
    catalog = ActionCatalog(bot)  # type: ignore[arg-type]
    assert catalog.execute(_decision("dock_trading_port")).ok
    assert isinstance(bot.service.commands[-1], Dock)
    rejected = catalog.execute(_decision("recruit_colonists", count=20))
    assert not rejected.ok
    assert "docking at Stardock" in rejected.summary

    assert catalog.execute(_decision("dock_stardock")).ok
    assert isinstance(bot.service.commands[-1], Dock)
    assert catalog.execute(_decision("recruit_colonists", count=20)).ok
    recruited = bot.service.commands[-1]
    assert isinstance(recruited, RecruitColonists) and recruited.count == 20
    outcome = catalog.execute(_decision("buy_rumor"))
    assert outcome.ok and "a fresh lead" in outcome.summary
    assert isinstance(bot.service.commands[-1], BuyRumor)
