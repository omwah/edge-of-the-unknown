"""Corporations: membership, shared ownership, and corp war (DESIGN §4, WP66) — pure core.

A `Corporation` (see `models.Corporation`) is a player-level cooperative — distinct from an
`Alliance`, which is NPC diplomacy. Two systemic facts flow from it and are owned here:

- **Shared ownership.** An asset owned `Ownership("corp", id)` treats *every* member as its
  owner. `player_owns` is the single predicate the reducers and hostility helpers consult so a
  "player-or-corp" owner check never diverges between call sites.
- **Corp war.** `DeclareCorpWar` records the target on the declaring corp; hostility is
  mutual-by-declaration — a fight is on if *either* corp lists the other (the
  `rival_alliance_ids` symmetry rule reused). `owner_at_war_with_player` is how a corp-owned
  base/force/citadel reads as hostile to a player of a rival corp, plugged into the same
  `owner_hostile` / `force_hostile_to_player` seams the alliance rules use.

This module imports only `models`, so it sits below `aliens`/`territory`/`rules` (which import
it) and the layer graph stays acyclic.
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.models import Corporation, Ownership, Planet, Player, UniverseState


def player_corp(state: UniverseState, player_id: int) -> Corporation | None:
    """The corporation a player belongs to, or None (§4, WP66)."""
    player = state.players.get(player_id)
    if player is None or player.corp_id is None:
        return None
    return state.corporations.get(player.corp_id)


def player_owns(state: UniverseState, owner: Ownership, player_id: int) -> bool:
    """Whether `player_id` counts as an owner of a holding (§4.2/§4-WP66).

    True for a directly player-owned holding, and for a corp-owned holding when the player is a
    member of that corp — the "a corp asset treats every member as its owner" rule. The single
    predicate behind every owner-gated action (planet bank/build/invade-immunity, forward-base
    services, starbase claim context), so corp and solo ownership never drift apart.
    """
    if owner.kind == "player":
        return owner.ref == player_id
    if owner.kind == "corp" and owner.ref is not None:
        corp = state.corporations.get(owner.ref)
        return corp is not None and player_id in corp.member_player_ids
    return False


def player_controls_planet(state: UniverseState, planet: Planet, player_id: int) -> bool:
    """Whether the player owns a world or administers its protectorate (GW-WP11).

    This is intentionally broader than :func:`player_owns`: D13 grants production
    and ground-defense administration without pretending the retained native polity
    is ordinary player/corp property.
    """
    return player_owns(state, planet.owner, player_id) or player_owns(
        state, planet.protectorate_controller, player_id)


def assault_war_delta(
    state: UniverseState, attacker: Player, former_owner: Ownership,
) -> Corporation | None:
    """Declare the corp-war consequence of assaulting a rival corp holding.

    A solo attacker has no corporation ledger to mutate. For two distinct corps,
    the attacker's declaration is enough because corp hostility is mutual-by-
    declaration throughout the rules.
    """
    if (former_owner.kind != "corp" or former_owner.ref is None
            or attacker.corp_id is None or attacker.corp_id == former_owner.ref):
        return None
    attacking = state.corporations.get(attacker.corp_id)
    if attacking is None or former_owner.ref in attacking.at_war_with:
        return None
    return replace(attacking, at_war_with=attacking.at_war_with | {former_owner.ref})


def corps_at_war(state: UniverseState, corp_a: int | None, corp_b: int | None) -> bool:
    """Whether two corps are at war — mutual-by-declaration (§4-WP66).

    Either side listing the other is enough (the symmetry rule). A None corp (a player with no
    corp) is never at corp-war. Same corp is never at war with itself.
    """
    if corp_a is None or corp_b is None or corp_a == corp_b:
        return False
    a, b = state.corporations.get(corp_a), state.corporations.get(corp_b)
    return (a is not None and corp_b in a.at_war_with) or (b is not None and corp_a in b.at_war_with)


def owner_at_war_with_player(state: UniverseState, owner: Ownership, player: Player) -> bool:
    """Whether a corp-owned holding is hostile to a player via corp war (§4-WP66).

    A corp base/force/citadel engages a player whose corp is at war with the owning corp — the
    corp analogue of the alliance-standing hostility the other owner kinds use. A member (or a
    neutral non-member outside WP67's territory rules) is not engaged by this predicate.
    """
    if owner.kind != "corp" or owner.ref is None:
        return False
    if player_owns(state, owner, player.id):
        return False  # never hostile to its own members
    return corps_at_war(state, owner.ref, player.corp_id)
