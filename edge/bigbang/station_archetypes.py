"""Deterministic builder-archetype assignment for ports and orbital bases."""

from __future__ import annotations

import random
from dataclasses import replace

from edge.core.config import GameConfig
from edge.core.models import AlienSpecies, Ownership, UniverseState


def _builder(state: UniverseState, *, owner: Ownership | None,
             sector_id: int) -> AlienSpecies | None:
    """Resolve the species whose configured archetype designed the structure."""
    if owner is not None and owner.kind == "species" and owner.ref is not None:
        return state.species.get(owner.ref)
    if owner is not None and owner.kind == "alliance":
        members = [sp for sp in state.species.values() if sp.alliance_id == owner.ref]
        if members:
            return min(members, key=lambda sp: (sp.alliance_role != "leader", sp.id))
    sector = state.sectors.get(sector_id)
    region = state.regions.get(sector.region_id) if sector is not None else None
    if region is None or region.controlling_species_id is None:
        return None
    return state.species.get(region.controlling_species_id)


def _archetype(state: UniverseState, config: GameConfig, *, kind: str, identity: int,
               owner: Ownership | None, sector_id: int) -> str:
    builder = _builder(state, owner=owner, sector_id=sector_id)
    if builder is not None:
        return builder.archetype_id
    choices = sorted({sp.archetype_id for sp in state.species.values() if sp.archetype_id})
    if not choices and config.roster is not None:
        choices = sorted({sp.archetype_id for sp in config.roster.species})
    if not choices:
        return "humanoid_diplomat"
    rng = random.Random(f"{state.game.seed}|station-archetype|{kind}|{identity}")
    return rng.choice(choices)


def assign_station_archetypes(state: UniverseState, config: GameConfig) -> None:
    """Stamp every structure's builder archetype after alien regions exist (§5)."""
    state.ports = {
        pid: replace(
            port,
            archetype_id=_archetype(
                state, config, kind="port", identity=pid, owner=None,
                sector_id=port.sector_id),
        )
        for pid, port in state.ports.items()
    }
    state.starbases = {
        bid: replace(
            base,
            archetype_id=_archetype(
                state, config, kind="starbase", identity=bid, owner=base.owner,
                sector_id=base.sector_id),
        )
        for bid, base in state.starbases.items()
    }
