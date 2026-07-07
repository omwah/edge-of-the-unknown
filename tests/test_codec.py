"""WP9 — command/event serialization round-trips (DESIGN §12)."""

from __future__ import annotations

import pytest

from typing import get_args

from edge.core.enums import Commodity, Component, ComponentTier, PortMode, Subsystem
from edge.core.events import (
    AdmissionAdvanced,
    AlienHailed,
    AlienMoved,
    AlienSpoke,
    AlienTraded,
    AllianceJoined,
    AllianceResigned,
    AttitudeChanged,
    Banked,
    CitadelBuildStarted,
    CitadelCompleted,
    Colonized,
    ColonistsRecruited,
    ColonyGrew,
    CombatRound,
    PlanetBanked,
    ComponentInstalled,
    ComponentKnockedOut,
    ComponentPurchased,
    ComponentRemoved,
    CoreLawNotice,
    Descended,
    DevApplied,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    EncounterEnded,
    EncounterEvaded,
    EncounterStarted,
    GenesisDeployed,
    GrudgeFormed,
    HazardDamage,
    SiteExplored,
    Event,
    AllianceLeadershipChanged,
    GovernanceChanged,
    Haggled,
    LeadAccepted,
    MarketSettled,
    PlanetProduced,
    PortOrderFilled,
    Repaired,
    SalvageCollected,
    ShipDestroyed,
    ShipPurchased,
    StarbaseClaimed,
    StarbaseRazed,
    StarbaseRepaired,
    StarbaseSalvaged,
    StockRegenerated,
    TerritoryDeployed,
    Traded,
    TurnsReset,
    Warped,
)
from edge.core.rules import (
    AcceptLead,
    AdvanceAdmission,
    AssaultStarbase,
    BarterArtifact,
    BuyAlienTech,
    BuyComponent,
    BuyGenesis,
    BuyMissiles,
    BuyShip,
    BuyFighters,
    BuyMines,
    Cannibalize,
    ClaimStarbase,
    Colonize,
    CombatAction,
    Command,
    Converse,
    DeployBeacon,
    DeployFighters,
    DeployGenesis,
    DeployMines,
    Deposit,
    Descend,
    Dock,
    Explore,
    FieldPatch,
    Hail,
    HaggleOffer,
    InstallComponent,
    JoinAlliance,
    JoinGame,
    PetitionCoreSeizure,
    RecruitColonists,
    RepairAtDock,
    RepairStarbase,
    ResignAlliance,
    Salvage,
    SetAllocation,
    SwapComponent,
    BuildCitadel,
    PlanetDeposit,
    PlanetWithdraw,
    Trade,
    TravelTo,
    Warp,
    Withdraw,
)
from edge.core.dev import DevPatch
from edge.store import codec

COMMANDS: list[Command] = [
    JoinGame(),
    JoinGame(name="Pathfinder"),
    Warp(to_sector=12),
    TravelTo(to_sector=20),
    Dock(),
    Trade(commodity=Commodity.FUEL_ORE, units=10, unit_price=13),
    Trade(commodity=Commodity.ORGANICS, units=5),  # unit_price None
    HaggleOffer(commodity=Commodity.EQUIPMENT, units=4, counter_price=20),
    Deposit(amount=500),
    Withdraw(amount=250),
    BuyComponent(Component.TURBINE, ComponentTier.II),
    BuyShip("scout_marauder"),
    RepairAtDock(Subsystem.THRUSTERS, 1),
    RecruitColonists(count=40, from_planet=None),
    RecruitColonists(count=10, from_planet=7),
    Colonize(planet_id=5, colonists=25),
    SetAllocation(planet_id=5, allocation={"fuel_ore": 0.5, "organics": 0.5}),
    BuildCitadel(planet_id=5),                       # WP54 open a timed citadel build
    PlanetDeposit(planet_id=5, amount=1_000),        # WP54 treasury deposit
    PlanetWithdraw(planet_id=5, amount=500),         # WP54 treasury withdraw
    InstallComponent(Subsystem.SPINDRIVE, 3, Component.TURBINE, ComponentTier.II),
    SwapComponent(Subsystem.SCREENS, 1, Component.RADIATOR, ComponentTier.III),
    Cannibalize(Subsystem.MAIN_GUN, 2),
    Cannibalize(Subsystem.FUSION_REACTOR, 0, starbase_id=4),  # WP4 starbase salvage
    FieldPatch(Subsystem.THRUSTERS, 0),
    Salvage(discovery_id=7),      # WP5 log a discovery to the codex
    Descend(planet_id=5),         # WP6 descend to a planet surface
    Explore(planet_id=5),         # WP6 survey the next surface site
    BuyGenesis(),                 # WP10 buy a genesis torpedo
    DeployGenesis(planet_id=5),   # WP10 terraform a world
    Hail(species_id=3),                          # WP9 open alien contact
    Converse(species_id=3, context="farewell"),  # WP17 say a peaceful line
    Converse(species_id=3, context="dossier_other", subject_id=5),  # WP17 ask about X
    Converse(species_id=3, context="branch.vesk_workshop", choice_index=1),  # §6.7 branching reply
    BuyAlienTech(species_id=3, offer_index=1),   # WP9 buy tech for latinum
    BarterArtifact(species_id=3, offer_index=0), # WP9 barter an artifact for tech
    AcceptLead(species_id=3),                    # §6.7 log an alien's coordinate tip
    AdvanceAdmission(alliance_id=3, task="pay"), # WP38 complete an admission task
    JoinAlliance(alliance_id=3),                 # WP38 join a bloc
    ResignAlliance(),                            # WP38 leave the current bloc
    PetitionCoreSeizure(alliance_id=4),          # WP50 champion a covets_core bloc
    AssaultStarbase(starbase_id=2),              # WP40 begin a set-piece assault
    RepairStarbase(2, Subsystem.FUSION_REACTOR, 0, Component.CONVERTER, ComponentTier.I),  # WP40
    ClaimStarbase(starbase_id=2),                # WP40 claim a repaired base
    BuyFighters(count=20),                       # WP41 buy fighter stock
    BuyMines(count=5),                           # WP41 buy mine stock
    DeployFighters(count=10, mode="toll", toll=50),  # WP41 garrison a sector
    DeployMines(count=3),                        # WP41 seed mines
    DeployBeacon(text="Kilroy was here"),        # WP41 plant a beacon
    CombatAction(action="fight"),                # WP25 one combat round
    CombatAction(action="flee"),
    CombatAction(action="field_patch", subsystem=Subsystem.SCREENS, slot_index=1),
    BuyMissiles(count=3),                        # WP25 StarDock missile ammo
    DevPatch("set", "latinum", 1_000_000),            # dev cheat: set a field
    DevPatch("grant", "component", 2, key="accelerator:III"),  # dev cheat: grant parts
    DevPatch("claim", "planet", ref=5),               # dev cheat: claim a world
]

EVENTS: list[Event] = [
    Warped(1, 7, 12, 1),
    Warped(1, 7, 12, 1, one_way=True),  # one-way warp heads-up (§9)
    Docked(1, 12, 3),
    Traded(1, 3, Commodity.FUEL_ORE, PortMode.SELL, 10, 13, 130),
    Traded(1, 3, Commodity.ORGANICS, PortMode.BUY, 12, 6, 72, 20),  # WP47 partial fill (requested 20)
    MarketSettled(4, 120, 900),                        # WP47 daily settlement summary
    PortOrderFilled(3, Commodity.FUEL_ORE, "buy", 40, 9, 5),  # WP47 one explored-port fill
    Haggled(1, 3, Commodity.ORGANICS, "accepted", 6),
    Banked(1, "interest", 50, 10_050),
    ComponentPurchased(1, "turbine", "II", 8_000),
    ShipPurchased(1, "scout_marauder", 20_000, 0),
    ColonistsRecruited(1, "stardock", 40, 200),
    Colonized(1, 5, 25),
    PlanetProduced(5, 1),
    ColonyGrew(5, 1_050),
    CitadelBuildStarted(1, 5, 1),                      # WP54 citadel build opened
    CitadelCompleted(5, 1),                            # WP54 citadel level reached
    PlanetBanked(1, 5, "deposit", 1_000, 1_000),       # WP54 treasury move
    ComponentInstalled(1, "spindrive", 3, "turbine", "II"),
    ComponentRemoved(1, "main_gun", 2, "linkage", "I"),
    Repaired(1, "thrusters", 0),
    StarbaseSalvaged(1, 4, "fusion_reactor", 0, "converter", "I"),
    DiscoveryDetected(1, 7, "wreck", "RARE"),
    DiscoveryCollected(1, 7, "wreck", "RARE", "artifact"),
    Descended(1, 5),
    SiteExplored(1, 5, 9, "ruins", "RARE"),
    DevicePurchased(1, "genesis_torpedo", 15_000),
    GenesisDeployed(1, 5, "terrestrial_warm"),
    TurnsReset(1, 250),
    StockRegenerated(3, Commodity.EQUIPMENT, 480),
    AlienHailed(1, 3),
    AlienMoved(3, 7, 12),
    AlienSpoke(1, 3, "greeting", None),
    AlienSpoke(1, 3, "dossier_other", 5),
    AlienTraded(1, 3, "buy", "radiator (II)", 7_000),
    AttitudeChanged(1, 3, 0.12, 0.87),
    LeadAccepted(1, 3, "discovery", 42, 17),  # §6.7 accepted a coordinate tip
    EncounterStarted(1, 3, 55, True, 3, "Deep"),   # WP24 a violence opener
    EncounterStarted(1, 3, 55, False, 0, "Deep"),  # WP24 a peaceful interception
    EncounterEvaded(1, 3, 55),                     # WP24 slipped away unseen
    CombatRound(1, 3, 2, "fight", 24, 11, 2),      # WP25 one resolved round
    EncounterEnded(1, 3, "fled"),                  # WP25 outcome
    ComponentKnockedOut(1, "thrusters", 1, "burner"),   # WP26 localized damage
    ShipDestroyed(1, 3, 55, "trailblazer"),             # WP26 hull 0 → escape pod
    SalvageCollected(1, 42, ("burner", "linkage")),     # WP26 wreck salvage
    SalvageCollected(1, 17, ()),                        # WP26 latinum-only salvage
    GrudgeFormed(1, "vennrith", 0.6, True),             # WP27 a permanent vendetta
    CoreLawNotice(1, 3),                                # WP27 governor's warning
    GovernanceChanged(1, 2, "dev"),                     # WP49 the Core changed hands
    AllianceLeadershipChanged(3, "thessarch", "vennrith"),  # WP51 an internal coup
    AdmissionAdvanced(1, 3, "pay"),                     # WP38 admission task done
    AllianceJoined(1, 3, None),                         # WP38 joined a bloc (was unaligned)
    AllianceJoined(1, 3, 1),                            # WP38 switched blocs
    AllianceResigned(1, 3),                             # WP38 left a bloc
    StarbaseRazed(1, 2, 5, 55, "alliance", 3, 750),     # WP40 razed a bloc base
    StarbaseRazed(1, 2, 5, 55, "none", None, 750),      # WP40 razed an unowned base
    StarbaseRepaired(1, 2, "fusion_reactor", 0, "converter", "I"),  # WP40 refill a slot
    StarbaseClaimed(1, 2, 2000),                        # WP40 claimed a base
    TerritoryDeployed(1, 55, "fighters", 10, "toll"),   # WP41 deployed a garrison
    TerritoryDeployed(1, 55, "beacon", 1),              # WP41 planted a beacon
    HazardDamage(1, 55, "mine", 80),                    # WP41 mine field on entry
    HazardDamage(1, 55, "black_hole", 30),              # WP41 gravity shear
    DevApplied(1, "[dev] set latinum=1000000"),  # dev cheat audit marker
]


@pytest.mark.parametrize("command", COMMANDS)
def test_command_round_trips(command: Command) -> None:
    type_, payload = codec.encode_command(command)
    assert codec.decode_command(type_, payload) == command


@pytest.mark.parametrize("event", EVENTS)
def test_event_round_trips(event: Event) -> None:
    type_, payload = codec.encode_event(event)
    assert type_ == type(event).__name__
    assert isinstance(payload, dict)
    assert codec.decode_event(type_, payload) == event


def test_every_command_variant_is_covered() -> None:
    """Exhaustiveness guard: every member of the `Command` union round-trips (§12).

    Fails the build if a new command type is added without a `COMMANDS` fixture (and
    thus without a codec entry), so a command can't silently skip the log.
    """
    covered = {type(c) for c in COMMANDS}
    declared = set(get_args(Command))
    assert declared - covered == set(), f"command variants missing a codec fixture: {declared - covered}"


def test_decode_unknown_command_raises() -> None:
    with pytest.raises(ValueError):
        codec.decode_command("Nonsense", {})


def test_encode_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        codec.encode_event(Event())


def test_decode_unknown_event_raises() -> None:
    with pytest.raises(ValueError):
        codec.decode_event("Nonsense", {})
