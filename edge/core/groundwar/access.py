"""The one ground-access contract (GW-WP04, GW plan §Ground-access contract).

A single pure seam that answers *how a planet can be interacted with from orbit* as
a **tagged result**, not loosely coordinated booleans:

    GroundAccess = OrbitalOnly(reason)
                 | Survey(settlements, reason)
                 | Assault(owner, inhabited, blockers, reason)

Consumed identically by the begin-operation reducers (which recompute it and stay
authoritative — the DTO is advisory), the `PlanetDTO` projection, and the bot/service
planet query surface. Encodes the interview decisions:

- **D1** every inhabited world **below the amity threshold** routes to assault; there
  is no separate neutral/wary permission branch. Friendly (yours/your corp/your bloc,
  or an inhabiting species in the friendly band) and uninhabited landable worlds route
  to survey.
- **D9** bare jovians / Cloud Cities stay **orbital-only** until the dedicated Cloud
  City assault gate opens (GW-WP15/16); the seam is explicit, never reusing terrestrial
  terrain.
- **G13** a Core world can **never** enter assault — the sanctuary holds regardless of
  crafted commands or stale DTOs.

Leaf-adjacent pure module: imports only lower `edge.core` rule modules (never
`edge.core.rules`, `edge.server`, or `edge.tui`), so the dependency graph stays acyclic
and `rules.py` / `session.py` can both import it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from edge.core import aliens, corp
from edge.core.citadels import has_gun, siege_shielded
from edge.core.config import GameConfig
from edge.core.models import AlienSpecies, Ownership, Planet, Player, UniverseState
from edge.core.planets import is_cloud_city_world, is_landable, native_population_key, pretty_planet_type
from edge.core.starbases import is_operational


@dataclass(frozen=True, slots=True)
class OrbitalOnly:
    """This world is only ever interacted with from orbit (no ground operation).

    A non-landable spatial feature (belt / bare jovian), a Cloud City awaiting its
    interior-assault gate (D9), or a Core world whose sanctuary bars assault (G13).
    """

    reason: str
    mode: ClassVar[str] = "orbital_only"


@dataclass(frozen=True, slots=True)
class Survey:
    """This world opens a surface **survey** expedition (GW-WP05+).

    `settlements` is True when friendly live inhabitants can be visited for
    resupply/hints (D5/D6); False on an uninhabited world.
    """

    settlements: bool
    reason: str
    mode: ClassVar[str] = "survey"


@dataclass(frozen=True, slots=True)
class Assault:
    """This world opens a tactical **assault** once its orbital defences fall (GW-WP08+).

    `blockers` is the siege ladder still standing (operational base, live citadel gun,
    siege shield); an empty tuple means a drop is legal now. `owner` and `inhabited`
    are the strategic-settlement inputs the assault will reconcile against (D2/D7/D11).
    """

    owner: Ownership
    inhabited: bool
    blockers: tuple[str, ...]
    reason: str
    mode: ClassVar[str] = "assault"

    @property
    def droppable(self) -> bool:
        """Whether the orbital ladder is clear and a platoon could land right now."""
        return not self.blockers


# The tagged ground-access result (GW plan §Ground-access contract). Discriminated by
# concrete type / the `mode` class label the DTO and bot surface read.
GroundAccess = OrbitalOnly | Survey | Assault


def inhabiting_species(
    state: UniverseState, planet: Planet, config: GameConfig,
) -> AlienSpecies | None:
    """The native species inhabiting `planet` (D2 holdings), or None (§4.2).

    Named by `native_population_key` — the non-player people in `population` — since a
    world may now hold the player's own colonists alongside a native polity
    (GW-WP09-PRE follow-up); ownership alone (checked first in `_friendly`) already
    decides friendliness for a player-owned world, so this is only ever asked about an
    unowned holding. Public (GW-WP09): `rules._begin_assault` reuses this one seam
    rather than duplicating the `native_population_key` + `resolve_species_by_kind`
    pair a second time.
    """
    key = native_population_key(planet, config)
    if key is None:
        return None
    return aliens.resolve_species_by_kind(state, key, config.roster)


def _is_inhabited(state: UniverseState, planet: Planet) -> bool:
    """Whether a world has a live populace (GW plan §Ground-access contract).

    Live colonists (an owned colony), a native people (a D2 holding), or a built
    Cloud City. A bare, unpeopled world is not inhabited and always surveys.
    """
    return bool(planet.population) or planet.cloud_city_size > 0


def species_effective_standing(
    species: AlienSpecies, player: Player, config: GameConfig
) -> float:
    """An inhabiting species' effective standing toward the player (GW plan §contract).

    Base disposition shifted by the player's attitude offset, then lowered by any active
    grudge and by negative standing with the species' bloc — the same three inputs the
    §10 greeting-vs-violence roll uses, so surface access and combat agree on who is
    hostile. Not clamped: a soured species can read below zero, which is firmly
    below-friendly.
    """
    assert config.aliens is not None  # only called for an inhabiting-species world
    disp = aliens.effective_disposition(species, player)
    disp -= aliens.grudge_shift(species, player)
    disp -= aliens.alliance_standing_shift(player, species)
    return disp


def _friendly(state: UniverseState, player: Player, planet: Planet, config: GameConfig) -> bool:
    """Whether an inhabited world is friendly to the player (GW plan D1 §contract).

    Friendly means: the player (or their corp) owns it; it belongs to the player's own
    bloc (a member/governor holding); or its inhabiting species stands in the configured
    friendly band after attitude, grudge, and alliance-standing effects. Every other
    inhabited world — a rival/other bloc's holding, another player's/corp's world, or an
    unaligned species below amity — is *below friendly* and routes to assault.
    """
    owner = planet.owner
    if corp.player_controls_planet(state, planet, player.id):
        return True
    if (planet.protectorate_controller.kind == "corp"
            and corp.owner_at_war_with_player(
                state, planet.protectorate_controller, player)):
        return False
    if owner.kind == "alliance" and owner.ref is not None and owner.ref == player.alliance_id:
        return True
    species = inhabiting_species(state, planet, config)
    if species is not None and config.aliens is not None:
        return aliens.is_friendly(
            species_effective_standing(species, player, config), config.aliens)
    # Owned by another alliance/corp/player with no inhabiting species → below friendly.
    return False


def _operational_base_in_sector(state: UniverseState, sector_id: int) -> bool:
    return any(b.sector_id == sector_id and is_operational(b) for b in state.starbases.values())


def assault_blockers(
    state: UniverseState, planet: Planet, config: GameConfig
) -> tuple[str, ...]:
    """The siege-ladder rungs still barring a ground assault, in order (GW plan G12).

    An operational orbital base must be razed, the citadel gun silenced, and the L3 siege
    shield brought down before a platoon can land — the same ladder the abstract
    `InvadePlanet` enforces (§4.2). A razed base / silenced gun never appears here (G12,
    derived from live state). An empty tuple means a drop is legal now.
    """
    blockers: list[str] = []
    if _operational_base_in_sector(state, planet.sector_id):
        blockers.append("raze the orbital base first")
    if config.citadels is not None:
        if has_gun(planet, config):
            blockers.append("silence the citadel gun first")
        if siege_shielded(planet, config, base_operational=False):
            blockers.append("the siege shield holds")
    return tuple(blockers)


def ground_access(
    state: UniverseState, player: Player, planet: Planet, config: GameConfig
) -> GroundAccess:
    """Classify how the player may interact with `planet` from orbit (GW plan §contract).

    The one authoritative routing seam behind survey/assault: begin reducers recompute it
    (staying authoritative), while the DTO/bot surface project it advisorily. Order matters
    — non-landable feature (D9) → uninhabited/friendly survey (D1) → Core sanctuary (G13)
    → assault-not-enabled → below-friendly assault (D1).
    """
    # D9: a gas giant / Cloud City is engaged from orbit until the interior-assault gate
    # opens (GW-WP15/16), *regardless* of the config `landable` flag — the seam stays
    # explicit and never reuses terrestrial terrain. Checked before landability because a
    # jovian is nominally landable (the legacy `Descend` path descends to its Cloud City).
    if is_cloud_city_world(planet.planet_type, config):
        if planet.cloud_city_size > 0:
            return OrbitalOnly(
                "a Cloud City is engaged from orbit until station-interior assault opens")
        return OrbitalOnly("a gas giant has no surface to land on")
    if not is_landable(planet.planet_type, config):
        return OrbitalOnly(
            f"a {pretty_planet_type(planet.planet_type).lower()} has no surface to land on")
    if not _is_inhabited(state, planet):
        return Survey(settlements=False, reason="an uninhabited world — survey its surface")
    if _friendly(state, player, planet, config):
        return Survey(settlements=True, reason="a friendly world — survey its surface")
    # A below-friendly inhabited world routes to assault, except where a hard boundary wins:
    if state.sectors[planet.sector_id].is_galactic_core:
        return OrbitalOnly("the Core's worlds cannot be assaulted")  # G13 sanctuary
    if config.citadels is None:
        return OrbitalOnly("ground assault is not enabled in this universe")
    return Assault(
        owner=planet.owner, inhabited=True,
        blockers=assault_blockers(state, planet, config),
        reason="a hostile inhabited world — assault once its orbital defences fall",
    )
