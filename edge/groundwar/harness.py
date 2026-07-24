"""A throwaway single-sector, single-planet `UniverseState` (GW-WP14 Phase 8).

The retargeted `edge-groundwar` POC drives production ground-operations rules
(`BeginAssault`/`BeginSurvey` + the production TUI screens) instead of its own
duplicate engine. It needs a live `GameService`, not a full big-bang universe — this
mirrors `tests/test_groundwar_access.py`'s `_state`/`_planet` pattern: a one-sector Hub
holding one planet and the player's ship.

Two builders, one per mode:

- `assault_state` seeds a below-friendly-species world with a garrison sized by
  `edge.core.groundwar.assault.seed_garrison` (the same call the big bang makes) and
  pre-loads the ship's `recruits`/`suits` from a composed loadout, so `BeginAssault`
  finds the drop already droppable (no orbital base, no citadel gun standing) and
  `GroundAssaultScreen`'s own deploy-composer has something aboard to draw from.
- `expedition_state` seeds an owned (friendly, "inhabited") or unowned ("uninhabited")
  world and salts a handful of real `Discovery` records onto it — survey sites must
  each name a real discovery id (GW plan G6), so a bare planet has nothing to find.
"""

from __future__ import annotations

from dataclasses import replace
from random import Random

from edge.core.config import GameConfig
from edge.core.enums import DiscoveryKind, PayloadKind, RarityTier
from edge.core.groundwar.assault import seed_garrison
from edge.core.groundwar.force import missile_capacity
from edge.core.models import (
    Discovery,
    DiscoveryPayload,
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    UniverseState,
)

PLANET_ID = 1
SHIP_ID = 1
PLAYER_ID = 1
SECTOR_ID = 1

# Any roster kind name works: an inhabiting species with no live/seeded home
# disposition resolves to "unresolvable" in `edge.core.groundwar.access._friendly`,
# which reads as below-friendly — exactly what routes a populated, unowned world to
# assault without having to stand up a whole species/roster fixture.
_HOSTILE_SPECIES_KIND = "vesk"

_SURVEY_KINDS = (
    DiscoveryKind.RUINS, DiscoveryKind.ARTIFACT,
    DiscoveryKind.ANCIENT_TECH, DiscoveryKind.CRASHED_SHIP,
)


def _base_state(config: GameConfig, seed: int, planet: Planet, ship: Ship) -> UniverseState:
    state = UniverseState.new(Game(seed, seed, config.config_version, "edge-groundwar"))
    state.sectors = {SECTOR_ID: Sector(SECTOR_ID, 1, (), "Frontier")}
    state.rebuild_adjacency()
    state.planets = {planet.id: planet}
    state.ships = {ship.id: ship}
    state.players = {PLAYER_ID: Player(id=PLAYER_ID, name="Commander", ship_id=ship.id,
                                       latinum=0, turns_remaining=999)}
    return state


def assault_state(
    config: GameConfig, *, seed: int, planet_type: str,
    habitability_cap: int, citadel_level: int, loadout: dict[str, int],
) -> UniverseState:
    """A below-friendly world sized for a droppable assault, plus a loaded ship.

    `habitability_cap` and `citadel_level` are the two knobs
    `edge.core.groundwar.assault.derive_difficulty` actually reads to size the
    battlefield and surrender threshold — the standalone-only `GwDifficulty` table
    has no effect on production and was retired alongside this rewrite. `gun_integrity`
    stays 0 regardless of `citadel_level`: a droppable assault requires the gun already
    silenced (`ground_access` demands it), but `citadel_level` alone still tells
    `derive_difficulty` this world once fielded one (GW plan decision #7).
    """
    rng = Random(seed)
    infantry, armor = seed_garrison(
        config, capacity=habitability_cap, citadel_level=citadel_level,
        distance_band="Frontier", hostile=True, alliance_owned=False, rng=rng)
    planet = Planet(
        id=PLANET_ID, sector_id=SECTOR_ID, name="Target World", planet_type=planet_type,
        habitability_cap=habitability_cap, population={_HOSTILE_SPECIES_KIND: habitability_cap},
        citadel_level=citadel_level, gun_integrity=0,
        garrison_infantry=infantry, garrison_armor=armor)
    suits_total = sum(loadout.values())
    ship = Ship(
        id=SHIP_ID, type_id="trailblazer", name="S.S. Harness", owner_player_id=PLAYER_ID,
        sector_id=SECTOR_ID, holds_total=60, turns_per_warp=1,
        passenger_capacity=suits_total * 2, recruits=suits_total, suits=dict(loadout))
    ship = replace(ship, ground_missiles=missile_capacity(ship, config))
    return _base_state(config, seed, planet, ship)


def expedition_state(
    config: GameConfig, *, seed: int, planet_type: str, inhabited: bool, site_count: int,
) -> UniverseState:
    """An owned ("inhabited", friendly settlements) or unowned ("uninhabited") world
    with `site_count` real `Discovery` records salted onto its surface."""
    owner = Ownership("player", PLAYER_ID) if inhabited else Ownership("none")
    rng = Random(seed)
    discoveries = {}
    for i in range(1, site_count + 1):
        kind = rng.choice(_SURVEY_KINDS)
        discoveries[i] = Discovery(
            id=i, kind=kind, rarity_tier=rng.choice(list(RarityTier)), sector_id=SECTOR_ID,
            payload=DiscoveryPayload(kind=PayloadKind.ARTIFACT, barter_tier="II", lore="x"),
            planet_id=PLANET_ID, site_slot=i, hidden=False, name=f"Site {i}")
    planet = Planet(
        id=PLANET_ID, sector_id=SECTOR_ID, name="Target World", planet_type=planet_type,
        owner=owner, habitability_cap=50_000)
    ship = Ship(id=SHIP_ID, type_id="trailblazer", name="S.S. Harness",
               owner_player_id=PLAYER_ID, sector_id=SECTOR_ID, holds_total=60, turns_per_warp=1)
    state = _base_state(config, seed, planet, ship)
    state.discoveries = discoveries
    return state
