"""Core-governance changes — the single place the Core changes hands (§6.3, §4.2, WP49).

Governance is derived from **one** mutable field, `Game.core_governing_alliance_id`
(the WP38 seam): `governor_hostile`, `may_occupy`, the Core-law events, and
`base_owner_hostile` all read it live, so flipping it re-keys the whole Core-safety
surface with zero changes to those functions. This module owns the *entity* re-keying
that must ride the same flip: Core planets and their orbital bases become the new
governor's property, and any incumbent now sitting on newly-illegal Core ground is
evicted to the nearest legal sector.

Pure and RNG-free (H10/H11): eviction resolves by deterministic BFS from the
incumbent's sector, ties broken by lowest sector id, so a flip reconstructs identically
under replay. `flip_core_governor` returns a `GovernanceDelta` of every changed entity;
callers (the dev trigger WP49, the player petition WP50, the NPC cron WP51) compose it
into one `ReduceResult`. It deliberately does **not** touch `Player.alliance_id` or
standings — §6.3's safety rule is positional and the standing math re-evaluates live.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, replace

from edge.core.config import AllianceConfig, GameConfig
from edge.core.events import AllianceLeadershipChanged, Event, GovernanceChanged
from edge.core.models import (
    AlienSpecies,
    Alliance,
    Game,
    Ownership,
    Planet,
    Starbase,
    UniverseState,
)
from edge.core.starbases import is_operational


@dataclass(frozen=True, slots=True)
class GovernanceDelta:
    """Every entity a governance flip changes, ready to fold into one `ReduceResult`."""

    game: Game
    planets: tuple[Planet, ...]
    starbases: tuple[Starbase, ...]
    species: tuple[AlienSpecies, ...]
    events: tuple[Event, ...]


def _sector_legal_for(
    state: UniverseState, species: AlienSpecies, sector_id: int, new_gov: int | None,
) -> bool:
    """`may_occupy` evaluated against a hypothetical governor `new_gov` (pure mirror).

    Mirrors `aliens.may_occupy` exactly but reads the *new* governor rather than
    `state.game`, so eviction can be resolved inside the flip before the game record is
    swapped. The Core admits only the new governor's members; a rival bloc's planet bars
    a non-member; everything else is open.
    """
    sector = state.sectors[sector_id]
    if sector.is_galactic_core:
        return species.alliance_id == new_gov
    for planet in state.planets.values():
        if planet.sector_id != sector_id:
            continue
        owner = planet.owner
        if owner.kind == "alliance" and owner.ref != species.alliance_id:
            return False
    return True


def _nearest_legal(
    state: UniverseState, species: AlienSpecies, new_gov: int | None,
) -> int | None:
    """The closest sector `species` may legally occupy under `new_gov`, or None.

    Deterministic BFS from the incumbent's current sector; among equally-close legal
    sectors the lowest id wins (no RNG), so the relocation is replay-stable. Returns the
    current sector if it is already legal.
    """
    start = species.sector_id
    if _sector_legal_for(state, species, start, new_gov):
        return start
    seen = {start}
    frontier: deque[int] = deque([start])
    while frontier:
        # Expand a whole BFS ring, then pick the lowest-id legal sector in it — this makes
        # "nearest, ties by lowest id" exact regardless of adjacency iteration order.
        ring: list[int] = []
        for _ in range(len(frontier)):
            here = frontier.popleft()
            for nxt in sorted(state.adjacency.get(here, ())):
                if nxt not in seen:
                    seen.add(nxt)
                    ring.append(nxt)
                    frontier.append(nxt)
        legal = [s for s in sorted(ring) if _sector_legal_for(state, species, s, new_gov)]
        if legal:
            return legal[0]
    return None


def flip_core_governor(
    state: UniverseState, config: GameConfig, new_alliance_id: int | None, cause: str,
) -> GovernanceDelta:
    """Change the Core's governing alliance and re-key everything that follows (§6.3, §4.2).

    Sets `Game.core_governing_alliance_id`, re-keys every Core-sector planet (and its
    orbital base) to the new governor, evicts incumbents from now-illegal Core sectors to
    their nearest legal sector, and emits a `GovernanceChanged` event. The base
    *operability* is untouched (components are physical, not political). `config` is
    accepted for signature parity with the reducers (unused today).
    """
    old = state.game.core_governing_alliance_id
    game = replace(state.game, core_governing_alliance_id=new_alliance_id)
    new_owner = Ownership("alliance", new_alliance_id) if new_alliance_id is not None else Ownership("none")

    planets: list[Planet] = []
    starbases: list[Starbase] = []
    for planet in sorted(state.planets.values(), key=lambda p: p.id):
        if not state.sectors[planet.sector_id].is_galactic_core:
            continue
        planets.append(replace(planet, owner=new_owner))
        if planet.starbase_id is not None and planet.starbase_id in state.starbases:
            base = state.starbases[planet.starbase_id]
            if base.owner != new_owner:
                starbases.append(replace(base, owner=new_owner))

    # Evict incumbents the new law bars from their (Core) sector. Only Core sectors can
    # newly bar an occupant (the Core admit-rule is the only governor-dependent clause),
    # so the eviction set is exactly the non-new-governor species standing in the Core.
    moved: list[AlienSpecies] = []
    for sp in sorted(state.species.values(), key=lambda s: s.id):
        if not state.sectors[sp.sector_id].is_galactic_core:
            continue
        if _sector_legal_for(state, sp, sp.sector_id, new_alliance_id):
            continue
        dst = _nearest_legal(state, sp, new_alliance_id)
        if dst is not None and dst != sp.sector_id:
            moved.append(replace(sp, sector_id=dst))

    events: tuple[Event, ...] = (GovernanceChanged(old, new_alliance_id, cause),)
    return GovernanceDelta(
        game=game, planets=tuple(planets), starbases=tuple(starbases),
        species=tuple(moved), events=events,
    )


# --- NPC governance readiness (§6.3, WP51) ----------------------------------


def _operational_core_bases(state: UniverseState, alliance_id: int | None) -> int:
    """Operational Core-sector starbases owned by `alliance_id` (the incumbent's grip)."""
    return sum(
        1 for base in state.starbases.values()
        if state.sectors[base.sector_id].is_galactic_core
        and base.owner.kind == "alliance" and base.owner.ref == alliance_id
        and is_operational(base)
    )


def _home_cluster_bases_intact(state: UniverseState, alliance_id: int) -> bool:
    """Whether the bloc's own home-cluster bases are all operational (its strength, §6.3).

    Vacuously true if the bloc holds no bases in its cluster (nothing to be broken). A
    razed home base means the coveter has itself been destabilized — it cannot seize.
    """
    cluster = set(state.home_clusters.get(alliance_id, ()))
    if not cluster:
        return True
    for base in state.starbases.values():
        if (base.sector_id in cluster and base.owner.kind == "alliance"
                and base.owner.ref == alliance_id and not is_operational(base)):
            return False
    return True


def npc_seizure_ready(state: UniverseState, config: GameConfig, alliance_id: int) -> bool:
    """Whether a bloc is positioned to seize the Core by NPC event (§6.3, WP51 — pure).

    Ready when the bloc covets the Core (its *live* `Alliance.covets_core`, so an
    intrigue-turned-outward bloc qualifies), is not already the governor, holds its own
    home-cluster bases intact, and the incumbent's operational Core-planet bases have
    fallen below `governance.min_incumbent_bases` — the destabilization that keeps a flip
    from coming out of nowhere. The roll itself is the cron's; this is only the gate.
    """
    gov = state.game.core_governing_alliance_id
    if alliance_id == gov:
        return False
    alliance = state.alliances.get(alliance_id)
    if alliance is None or not alliance.covets_core:
        return False
    gc = config.aliens.governance
    if _operational_core_bases(state, gov) >= gc.min_incumbent_bases:
        return False
    return _home_cluster_bases_intact(state, alliance_id)


@dataclass(frozen=True, slots=True)
class IntrigueDelta:
    """A leadership coup's changed species + its event (folded into the cron's result)."""

    species: tuple[AlienSpecies, ...]
    event: AllianceLeadershipChanged


def apply_intrigue(
    state: UniverseState, alliance: AllianceConfig,
    current: Mapping[int, AlienSpecies],
) -> IntrigueDelta | None:
    """Swap a bloc's leadership to its `internal_rival_species_id` (§6.3, WP51 — pure).

    Demotes every current leader of the bloc (of another kind) to member and promotes
    every placed instance of the internal-rival kind to leader. `current` overlays any
    already-changed species this firing (e.g. a seizure eviction), so the coup composes.
    Returns None — a replay-safe no-op — when the rival kind is absent (never invents
    instances) or already leads the bloc (idempotent).
    """
    rival = alliance.internal_rival_species_id
    if rival is None:
        return None

    def cur(sp: AlienSpecies) -> AlienSpecies:
        return current.get(sp.id, sp)

    leaders = sorted(
        (cur(s) for s in state.species.values()
         if s.alliance_id == alliance.id and cur(s).alliance_role == "leader"),
        key=lambda s: s.id,
    )
    promotees = sorted(
        (cur(s) for s in state.species.values() if s.roster_id == rival),
        key=lambda s: s.id,
    )
    if not promotees:
        return None  # the rival kind was not drawn into this universe — nothing to promote
    old_roster = leaders[0].roster_id if leaders else None
    if old_roster == rival:
        return None  # the rival already leads — idempotent
    changed: dict[int, AlienSpecies] = {}
    for s in leaders:
        if s.roster_id != rival:
            changed[s.id] = replace(s, alliance_role="member")
    for s in promotees:
        changed[s.id] = replace(s, alliance_role="leader", alliance_id=alliance.id)
    event = AllianceLeadershipChanged(alliance.id, old_roster, rival)
    return IntrigueDelta(species=tuple(changed.values()), event=event)
