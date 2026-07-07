"""Location-intel planner (DESIGN §6.7) — pure, deterministic.

The headline dialogue mechanic: aliens know about places the player hasn't found, and
friendly ones volunteer the coordinates. This module owns two pure pieces:

- `build_species_knowledge` — a generation-time pass that gives each species **kind** a
  small, band-appropriate set of known places of interest (rare relics/wrecks, forward
  starbases). Seeded from the game seed, so it reconstructs under `(seed, command log)`.
- `pick_intel_target` — at contact time, choose the single best tip a given speaker can
  offer this player: disposition-gated (only friendly/allied volunteer in Phase 2), filtered
  to places the player hasn't explored or logged, ranked by value (rarity × band distance),
  and bound to the dialogue placeholders (`{target}`, `{coords}`, `{distance}`, `{band}`,
  `{reward}`). Deterministic — the read-only projection and the accept-lead reducer agree.

Reuses the existing pathfinding (`core.movement.shortest_path`) and disposition helpers
(`core.aliens`); does no I/O and owns no RNG of its own beyond the seeded sub-RNG it derives.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from edge.core.aliens import effective_disposition, is_friendly
from edge.core.config import AliensConfig
from edge.core.enums import DiscoveryKind, PayloadKind, RarityTier
from edge.core.models import AlienSpecies, LocationRef, Player, UniverseState
from edge.core.movement import shortest_path

# How many places of interest a species kind knows about (a tip never exhausts in one game).
KNOWN_PER_SPECIES = 3
# Rarity floor for a discovery to be tip-worthy — common/uncommon finds aren't worth a map.
_TIP_RARITY_FLOOR = RarityTier.RARE.value


# --- generation: the species knowledge table -------------------------------------

def _candidates(state: UniverseState) -> list[LocationRef]:
    """The universe's tip-worthy places of interest (rare+ finds, every starbase)."""
    refs: list[LocationRef] = [
        LocationRef("discovery", d.id, d.sector_id)
        for d in state.discoveries.values()
        if d.rarity_tier.value >= _TIP_RARITY_FLOOR and d.kind is not DiscoveryKind.ENTITY
        # The reserved Entity codex row (§7, WP35) is not a fixed place — the Entity roams;
        # its tip is computed live in `pick_intel_target`, not baked into the knowledge table.
    ]
    refs += [LocationRef("starbase", b.id, b.sector_id) for b in state.starbases.values()]
    # Deterministic order before any sampling (sector, kind, ref).
    refs.sort(key=lambda r: (r.sector_id, r.kind, r.ref))
    return refs


def build_species_knowledge(state: UniverseState, seed: int) -> dict[str, tuple[LocationRef, ...]]:
    """Assign each present species **kind** a seeded subset of places it knows (§6.7).

    Weighted toward the deep frontier (a place's hop-distance from the Core is its weight),
    so high-value, far-flung tips dominate — the reward of talking to aliens is reach. One
    draw per `roster_id` (shared by every ship of that kind), seeded from the game seed so it
    reconstructs identically on reload.
    """
    candidates = _candidates(state)
    if not candidates:
        return {}
    weights = [max(1, state.core_hops.get(r.sector_id, 1)) for r in candidates]
    knowledge: dict[str, tuple[LocationRef, ...]] = {}
    for roster_id in sorted({sp.roster_id for sp in state.species.values()}):
        rng = random.Random(f"{seed}|knowledge|{roster_id}")
        knowledge[roster_id] = _weighted_sample(candidates, weights, KNOWN_PER_SPECIES, rng)
    return knowledge


def _weighted_sample(items: list[LocationRef], weights: list[int], k: int,
                     rng: random.Random) -> tuple[LocationRef, ...]:
    """Up to `k` distinct items drawn without replacement, weighted (deterministic)."""
    pool = list(zip(items, weights, strict=True))
    chosen: list[LocationRef] = []
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool)
        pick = rng.randint(1, total)
        acc = 0
        for i, (item, w) in enumerate(pool):
            acc += w
            if acc >= pick:
                chosen.append(item)
                pool.pop(i)
                break
    return tuple(chosen)


# --- contact time: choose and bind a tip -----------------------------------------

@dataclass(frozen=True)
class IntelTarget:
    """A chosen tip, ready to bind to dialogue placeholders and log as a `Lead`."""

    ref: LocationRef
    coords: int  # the destination's spatial display id (§5.1)
    distance: int  # fewest-hop route length from the player's ship
    band: str  # the destination's distance band
    label: str  # human target label (e.g. "ancient ruins", "a forward starbase")
    reward: str  # what waits there (e.g. "a Tier III component", "better hardware")

    def bindings(self) -> dict[str, str]:
        """The `{placeholder}` values an `offer_coordinates` line fills."""
        return {
            "target": self.label,
            "coords": str(self.coords),
            "distance": str(self.distance),
            "band": self.band,
            "reward": self.reward,
        }

    def summary(self) -> str:
        """A one-line label for the Computer/Map leads log."""
        return f"{self.label} — {self.band}, sector {self.coords} ({self.distance} hops)"


_DISCOVERY_LABELS: dict[DiscoveryKind, str] = {
    DiscoveryKind.RUINS: "ancient ruins",
    DiscoveryKind.ARTIFACT: "a buried artifact",
    DiscoveryKind.ANCIENT_TECH: "a cache of ancient tech",
    DiscoveryKind.CRASHED_SHIP: "a crashed ship",
    DiscoveryKind.WRECK: "a derelict wreck",
    DiscoveryKind.NEBULA: "an uncharted nebula",
    DiscoveryKind.BLACK_HOLE: "a black hole",
    DiscoveryKind.WORMHOLE: "a hidden wormhole",
    DiscoveryKind.ENTITY: "a space entity",
}


def _reward_phrase(state: UniverseState, ref: LocationRef) -> str:
    if ref.kind == "entity":
        return "a Legendary first contact"
    if ref.kind == "starbase":
        return "better hardware than yours"
    disc = state.discoveries.get(ref.ref)
    if disc is None:
        return "something of worth"
    payload = disc.payload
    if payload.kind is PayloadKind.COMPONENT and payload.tier is not None:
        return f"a Tier {payload.tier.name} component"
    if payload.kind is PayloadKind.LATINUM:
        return "gold-pressed latinum"
    if payload.kind is PayloadKind.ARTIFACT:
        return "an artifact worth bartering"
    return "ancient lore"


def _label(state: UniverseState, ref: LocationRef) -> str:
    if ref.kind == "entity":
        return "the roaming Entity"
    if ref.kind == "starbase":
        return "a forward starbase"
    disc = state.discoveries.get(ref.ref)
    return _DISCOVERY_LABELS.get(disc.kind, "a place of interest") if disc else "a place of interest"


def _value(state: UniverseState, ref: LocationRef) -> int:
    """A tip's worth: rarity (or a base for bases) scaled, plus its Core distance."""
    hops_from_core = state.core_hops.get(ref.sector_id, 0)
    if ref.kind == "entity":
        base = RarityTier.LEGENDARY.value + 1  # the singular pursuit prize outranks ordinary tips
    elif ref.kind == "discovery":
        disc = state.discoveries.get(ref.ref)
        base = disc.rarity_tier.value if disc else 0
    else:
        base = RarityTier.RARE.value  # a forward base ranks as a Rare-tier prize
    return base * 100 + hops_from_core


def _is_unencountered(state: UniverseState, player: Player, ref: LocationRef) -> bool:
    """Whether the place is still worth a tip: unexplored, uncollected, and not yet logged."""
    if ref.sector_id in player.explored_sectors:
        return False
    if any(lead.kind == ref.kind and lead.ref == ref.ref for lead in player.leads):
        return False  # already in the player's leads log — don't re-offer it
    if ref.kind == "discovery":
        disc = state.discoveries.get(ref.ref)
        if disc is None or disc.id in player.codex or disc.found_by is not None:
            return False
    elif state.starbases.get(ref.ref) is None:
        return False
    return True


def _entity_offerable(player: Player, ref: LocationRef) -> bool:
    """Whether the Entity tip is fresh: the player holds no lead to where it is **now** (§7).

    Keyed on ref **and sector** — a moved Entity (same ref, new sector) is re-offered, so
    re-asking a friendly speaker updates a cold trail; an already-logged current position is
    not re-offered (WP36, H3). Not suppressed by `explored_sectors` — the Entity roams, so
    having once passed through its current sector doesn't mean it is findable there now.
    """
    return not any(
        lead.kind == ref.kind and lead.ref == ref.ref and lead.sector_id == ref.sector_id
        for lead in player.leads
    )


def pick_intel_target(state: UniverseState, player: Player, speaker: AlienSpecies, *,
                      aliens: AliensConfig, entity: AlienSpecies | None = None) -> IntelTarget | None:
    """The single best coordinate tip `speaker` can offer `player`, or None (§6.7).

    Disposition-gated: only an allied or friendly-band speaker volunteers intel in Phase 2.
    Considers only places the player hasn't explored or logged, reachable from the player's
    ship, and picks the highest-value one (deterministically — ties by farther route, then
    lowest ref id) so the projection and the accept-lead reducer agree. When `entity` (the
    roaming Entity, §7/WP36) is supplied, its **live current sector** is a candidate tip too,
    computed here rather than from the generation-time knowledge table (H3).
    """
    allied = player.alliance_id is not None and player.alliance_id == speaker.alliance_id
    if not (allied or is_friendly(effective_disposition(speaker, player), aliens)):
        return None
    ship = state.ships.get(player.ship_id)
    if ship is None:
        return None
    src = ship.sector_id

    best: tuple[int, int, int] | None = None  # (value, distance, -ref) sort key
    chosen: tuple[LocationRef, int] | None = None
    candidates = list(state.species_knowledge.get(speaker.roster_id, ()))  # deterministic order
    # The Entity's live tip (its current sector), offered by any friendly speaker unless the
    # player already holds a fresh lead to where it is now (§7, WP36).
    entity_ref = (LocationRef("entity", entity.id, entity.sector_id)
                  if entity is not None and _entity_offerable(
                      player, LocationRef("entity", entity.id, entity.sector_id)) else None)
    for ref in candidates:
        if not _is_unencountered(state, player, ref):
            continue
        path = shortest_path(state.adjacency, src, ref.sector_id)
        if path is None:
            continue
        distance = len(path) - 1
        key = (_value(state, ref), distance, -ref.ref)
        if best is None or key > best:
            best, chosen = key, (ref, distance)
    if entity_ref is not None:
        path = shortest_path(state.adjacency, src, entity_ref.sector_id)
        if path is not None:
            distance = len(path) - 1
            key = (_value(state, entity_ref), distance, -entity_ref.ref)
            if best is None or key > best:
                best, chosen = key, (entity_ref, distance)

    if chosen is None:
        return None
    ref, distance = chosen
    return IntelTarget(
        ref=ref,
        coords=state.spatial_ids.get(ref.sector_id, ref.sector_id),
        distance=distance,
        band=state.sectors[ref.sector_id].distance_band,
        label=_label(state, ref),
        reward=_reward_phrase(state, ref),
    )


def pick_rumor(state: UniverseState, player: Player, speakers: list[AlienSpecies], *,
               aliens: AliensConfig, entity: AlienSpecies | None = None) -> IntelTarget | None:
    """The best undiscovered tip a set of speakers collectively know (DESIGN §14 — WP58).

    The tavern draws intel for cash from the union of the Core-welcome species' knowledge:
    it runs the ordinary per-speaker `pick_intel_target` and keeps the highest-value result
    (ties by farther route, then lowest ref id — the same ranking a single speaker uses), so
    a rumor is deterministic and never re-offers a tip already logged (the `_is_unencountered`
    dedup). Returns None when nobody knows anywhere fresh — the tavern is out of rumors.
    """
    best_key: tuple[int, int, int] | None = None
    best: IntelTarget | None = None
    for speaker in sorted(speakers, key=lambda s: s.id):
        target = pick_intel_target(state, player, speaker, aliens=aliens, entity=entity)
        if target is None:
            continue
        key = (_value(state, target.ref), target.distance, -target.ref.ref)
        if best_key is None or key > best_key:
            best_key, best = key, target
    return best
