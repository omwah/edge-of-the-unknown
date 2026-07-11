"""Sector territory: fighters, mines, beacons, hazards (DESIGN §10, WP41) — pure core.

The classic TW territory stack, reframed for Edge of the Unknown. Deployed **sector
forces** (`SectorForce`) garrison a sector with fighters and/or mines under an owner
(a player or an alliance). A force bars only entrants its owner opposes:

- **Mines** damage a hostile entrant on arrival (shields absorb first), then are spent.
- **Fighters** force *engage-or-retreat* — the garrison fights as a single all-round foe
  scaled by fighter count; retreating (fleeing) costs the garrison a fighter (the
  original rule, applied by the reducer).
- **Toll** fighters levy `toll` latinum on a hostile entrant instead of always fighting
  (the reducer decides); **beacons** are cosmetic comms buoys (`Sector.beacon_text`).
- **Black holes** deal a flat gravity toll on entry, independent of any force.

Every function here is pure; the movement reducers pass state and apply the effects.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from edge.core import corp
from edge.core.aliens import (
    alliance_rivals,
    alliance_standing,
    effective_disposition,
    governor_hostile,
    is_friendly,
)
from edge.core.config import GameConfig
from edge.core.enums import DiscoveryKind
from edge.core.models import AlienSpecies, EncounterFoe, Ownership, Player, SectorForce, UniverseState

FIGHTER_MODES = ("offensive", "defensive", "toll")


@dataclass(frozen=True, slots=True)
class DeploymentLegality:
    """Pure reducer-parity affordance for one Territory action (WP-PR11)."""

    id: str
    quantity: int
    enabled: bool
    blocker: str = ""
    active: bool = False


def deployment_legality(
    state: UniverseState, player_id: int, action_id: str, config: GameConfig,
) -> DeploymentLegality:
    """Return exact pre-submit legality for a Territory action.

    Command-specific input (fighter mode/count, beacon text, probe destination) is
    still validated by reducers; this covers every fact already known before opening
    those forms and is itself called by the reducers so projection cannot drift.
    """
    from edge.core.services import service_point

    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    sector = state.sectors[ship.sector_id]
    own = Ownership("player", player_id)
    existing = state.sector_forces.get(ship.sector_id)
    foreign_force = existing is not None and existing.owner != own

    quantity = 0
    blocker = ""
    active = False
    if action_id == "fighters":
        quantity = ship.fighters
        active = existing is not None and existing.owner == own and existing.fighters > 0
        if sector.is_galactic_core:
            blocker = "deployment is barred in Core Space"
        elif quantity < 1:
            blocker = "no fighters aboard"
        elif foreign_force:
            blocker = "another force already holds this sector"
    elif action_id in ("armid", "limpet"):
        quantity = ship.mines
        active = (existing is not None and existing.owner == own and
                  (existing.armid_mines if action_id == "armid" else existing.limpet_mines) > 0)
        if sector.is_galactic_core:
            blocker = "deployment is barred in Core Space"
        elif quantity < 1:
            blocker = "no space mines aboard"
        elif foreign_force:
            blocker = "another force already holds this sector"
    elif action_id == "beacon":
        quantity = player.latinum // max(1, config.territory.beacon_price)
        active = bool(sector.beacon_text)
        if sector.is_galactic_core:
            blocker = "deployment is barred in Core Space"
        elif player.latinum < config.territory.beacon_price:
            blocker = f"need {config.territory.beacon_price} latinum to plant a beacon"
    elif action_id == "probe":
        quantity = ship.devices.get("probe", 0)
        if config.devices.get("probe") is None:
            blocker = "probes are not sold in this universe"
        elif quantity < 1:
            blocker = "no probe aboard"
    elif action_id == "interdictor":
        quantity = ship.devices.get("interdictor", 0)
        active = ship.interdictor_active
        if quantity < 1:
            blocker = "no interdictor aboard"
    elif action_id == "strip":
        quantity = sum(ship.limpets.values())
        if quantity < 1:
            blocker = "no limpets attached"
        elif service_point(state, player, ship, config) is None:
            blocker = "limpets can only be removed at a StarDock or a base you own"
        elif player.latinum < config.territory.limpet_removal_fee:
            blocker = f"need {config.territory.limpet_removal_fee} latinum to strip the limpets"
    else:
        raise ValueError(f"unknown deployment action {action_id!r}")
    return DeploymentLegality(action_id, quantity, not blocker, blocker, active)


def force_in_sector(state: UniverseState, sector_id: int) -> SectorForce | None:
    """The deployed force garrisoning `sector_id`, or None."""
    return state.sector_forces.get(sector_id)


def force_hostile_to_player(state: UniverseState, force: SectorForce, player: Player,
                            *, pvp_enabled: bool = False) -> bool:
    """Whether `force` bars the player — its owner opposes them (§10, WP41; §14 WP67).

    An alliance-owned force engages a player at negative standing with that bloc (the governor's
    own force keys on `governor_hostile`), mirroring the base-defense rule (§4.2/§6.3). When
    `pvp_enabled` (WP67, interview decision 7) deployed territory additionally engages **any
    non-owner player**: another player's fighters/mines are a hazard to walk into, and a
    corp force bars any non-member. Its own owner (player or corp member) always passes free,
    so single-player and cooperative games are unchanged.
    """
    owner = force.owner
    if owner.kind == "alliance" and owner.ref is not None:
        if owner.ref == state.game.core_governing_alliance_id:
            return governor_hostile(state, player)
        return alliance_standing(player, owner.ref) < 0.0
    if owner.kind == "corp":
        if corp.owner_at_war_with_player(state, owner, player):
            return True  # corp war (WP66) — hostile regardless of the pvp toggle
        return pvp_enabled and not corp.player_owns(state, owner, player.id)
    if owner.kind == "player":  # a player force bars a *different* player when pvp is on (WP67)
        return pvp_enabled and owner.ref != player.id
    return False


def owner_tag(owner: Ownership) -> str:
    """A string tag for a force/holding owner — the limpet key (§10, WP56).

    ``"alliance:2"`` / ``"player:3"`` / ``"none"``. Used to tag a limpet on an entrant so
    the deploying owner's hunters can read the limpeted ship's exact position.
    """
    return f"{owner.kind}:{owner.ref}" if owner.ref is not None else owner.kind


def limpet_tags_for_species(sp: AlienSpecies) -> str:
    """The limpet owner tag whose limpets *this species* can track (§10, WP56).

    A species hunts on behalf of its alliance, so it reads limpets tagged to that bloc.
    An unaligned species tracks nothing (returns a tag that never matches a real owner).
    """
    return f"alliance:{sp.alliance_id}" if sp.alliance_id is not None else "alliance:None"


def fighter_foe(force: SectorForce, config: GameConfig) -> EncounterFoe:
    """The garrison as a single all-round combat foe, scaled by fighter count (§10, WP41)."""
    tc = config.territory
    hull = max(1, force.fighters * tc.fighter_hull_each)
    damage = max(1, force.fighters * tc.fighter_damage_each)
    return EncounterFoe(
        ship_class_id="sector_fighters", name=f"{force.fighters} sector fighters",
        hull=hull, hull_max=hull, shields=0, damage=damage,
        firing_arc="all_round", combat_speed=0, defense=0,
    )


def sector_has_black_hole(state: UniverseState, sector_id: int) -> bool:
    """Whether a black hole lurks in `sector_id` — a gravity hazard on entry (§10, WP41)."""
    return any(
        d.kind is DiscoveryKind.BLACK_HOLE and d.planet_id is None and d.sector_id == sector_id
        for d in state.discoveries.values()
    )


# --- NPC entry defenses (§10, WP-PR02) --------------------------------------
#
# Player warp resolves territory hazards in `rules._territory_entry` (a black hole
# toll, an armid detonation, a fighter *engagement* the player answers interactively).
# An NPC drifting on the cron has no interactive turn, so its entry resolves here
# deterministically: the shared hostility rule below decides whether the garrison/
# minefield bars the entrant, then the defenses fight to a conclusion in one pass —
# either the NPC is destroyed or the forces it triggered are spent. The mine-damage
# and fighter-hull formulas are the same `config.territory` constants the player path
# uses, so the two never drift.


def force_hostile_to_species(
    state: UniverseState, force: SectorForce, species: AlienSpecies, config: GameConfig,
) -> bool:
    """Whether a deployed `force` bars an NPC `species` drifting into its sector (§10, WP-PR02).

    The NPC mirror of `force_hostile_to_player`: a garrison/minefield engages an alien whose
    bloc its owner opposes.
    - An **alliance**-owned force (the Core governor's included) bars a species of a *rival*
      bloc (rivalry symmetric, §6.3); the owner bloc's own members pass free.
    - A **player**-owned force bars a species not friendly toward that player (effective
      disposition below the amity band) — your fighters defend against a hostile wanderer.
      An unknown/absent owner player bars nothing.
    - **corp**-owned forces do not yet engage NPCs (deferred with NPC limpets, WP-PR02).
    """
    owner = force.owner
    if owner.kind == "alliance" and owner.ref is not None:
        if species.alliance_id is None or species.alliance_id == owner.ref:
            return False
        return species.alliance_id in alliance_rivals(config.roster, owner.ref)
    if owner.kind == "player" and owner.ref is not None:
        player = state.players.get(owner.ref)
        if player is None:
            return False
        return not is_friendly(effective_disposition(species, player), config.aliens)
    return False


def _npc_combat_stats(species: AlienSpecies, config: GameConfig) -> tuple[int, int]:
    """The NPC's territory-fight profile: (hull+shields pool, per-round return damage).

    Derived from its fleet lead hull class × species threat (mirroring `encounters._foe`),
    so a warship shrugs off a token garrison while a minefield can gut a light hull.
    Returns ``(0, 0)`` for a shipless kind (the Entity, a pure contact) — never
    destructible by territory.
    """
    roster = config.roster
    sc = roster.species_by_id(species.roster_id) if roster is not None else None
    if sc is None or not sc.fleet:
        return 0, 0
    try:
        klass = config.ship_class(sc.fleet[0])
    except (KeyError, ValueError):
        return 0, 0
    pool = klass.hull_max + klass.shields_max
    weapon = config.weapons[klass.armament[0]] if klass.armament else None
    threat_bonus = round(sc.threat_rating * config.combat.threat_damage_scale)
    damage = (weapon.damage if weapon is not None else 1) + threat_bonus
    return pool, max(0, damage)


@dataclass(frozen=True, slots=True)
class NpcEntry:
    """The outcome of an NPC entering a defended sector (§10, WP-PR02).

    `destroyed` — the defenses out-damaged the entrant's hull. `force` — the post-fight
    garrison/minefield (armid spent, fighters attrited), or None when nothing changed.
    `cause` — ``"mine"`` / ``"fighter"`` / ``"mine+fighter"`` for the log (empty when idle).
    """

    destroyed: bool
    force: SectorForce | None
    cause: str


def resolve_npc_entry(
    state: UniverseState, species: AlienSpecies, force: SectorForce | None, config: GameConfig,
) -> NpcEntry:
    """Resolve `force`'s defenses against `species` drifting in (§10, WP-PR02) — pure, no RNG.

    A non-hostile or empty force is inert. Otherwise armid mines detonate first (NPCs carry
    no deflector), then any fighter garrison fights to a conclusion: each round the garrison
    volleys and, if the entrant survives, its return fire downs `damage // fighter_hull_each`
    fighters — so either the NPC dies or the garrison is wiped (an NPC that entered cannot
    retreat). Limpets never attach to an NPC (no tracking model), so a limpet-only field is
    inert here — deferred with corp/NPC tags.
    """
    if force is None or not force_hostile_to_species(state, force, species, config):
        return NpcEntry(False, None, "")
    pool, npc_damage = _npc_combat_stats(species, config)
    if pool <= 0:
        return NpcEntry(False, None, "")  # shipless entrant — nothing to destroy
    tc = config.territory
    remaining = pool
    causes: list[str] = []
    new_armid = force.armid_mines
    new_fighters = force.fighters
    if force.armid_mines > 0:
        remaining -= force.armid_mines * tc.mine_damage
        new_armid = 0
        causes.append("mine")
    if remaining > 0 and force.fighters > 0:
        causes.append("fighter")
        fighters = force.fighters
        while fighters > 0 and remaining > 0:
            remaining -= fighters * tc.fighter_damage_each
            if remaining <= 0:
                break
            fighters = max(0, fighters - max(1, npc_damage // tc.fighter_hull_each))
        new_fighters = fighters
    changed = new_armid != force.armid_mines or new_fighters != force.fighters
    updated = replace(force, armid_mines=new_armid, fighters=new_fighters) if changed else None
    return NpcEntry(remaining <= 0, updated, "+".join(causes))
