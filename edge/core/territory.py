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

from edge.core import corp
from edge.core.aliens import alliance_standing, governor_hostile
from edge.core.config import GameConfig
from edge.core.enums import DiscoveryKind
from edge.core.models import AlienSpecies, EncounterFoe, Ownership, Player, SectorForce, UniverseState

FIGHTER_MODES = ("offensive", "defensive", "toll")


def force_in_sector(state: UniverseState, sector_id: int) -> SectorForce | None:
    """The deployed force garrisoning `sector_id`, or None."""
    return state.sector_forces.get(sector_id)


def force_hostile_to_player(state: UniverseState, force: SectorForce, player: Player) -> bool:
    """Whether `force` bars the player — its owner opposes them (§10, WP41).

    A player-owned or unowned force never engages the player. An alliance-owned force
    engages a player at negative standing with that bloc (the governor's own force keys
    on `governor_hostile`), mirroring the base-defense rule (§4.2/§6.3).
    """
    owner = force.owner
    if owner.kind == "alliance" and owner.ref is not None:
        if owner.ref == state.game.core_governing_alliance_id:
            return governor_hostile(state, player)
        return alliance_standing(player, owner.ref) < 0.0
    if owner.kind == "corp":  # a corp force bars a rival-corp player (corp war, WP66)
        return corp.owner_at_war_with_player(state, owner, player)
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
