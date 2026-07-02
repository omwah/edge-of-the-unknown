"""Big-bang validation — the Phase-1 subset of DESIGN §5 step 8 / §13.

Asserts the invariants a new game must satisfy: every sector reachable from
sector 1, the warp-degree cap respected, exactly one reachable StarDock, and at
least one profitable opposed-class port pair within 5 hops of the Core (so a new
player can always earn). Richer §5 checks (home clusters, band monotonicity,
ownership) arrive with their Phase-2/3 generation steps.
"""

from __future__ import annotations

from collections import deque

from edge.bigbang.topology import bfs_distances
from edge.core.aliens import is_friendly
from edge.core.config import GameConfig
from edge.core.discovery import rarity_value
from edge.core.economy import port_unit_price
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.models import Port, UniverseState
from edge.core.starbases import is_operational


class ValidationError(Exception):
    """A generated universe violated a §5 invariant."""


def validate(state: UniverseState, config: GameConfig) -> None:
    _check_reachable(state)
    _check_degree_cap(state, config)
    _check_stardock(state)
    _check_profitable_pair(state, config)
    _check_planet_ownership(state, config)
    _check_starbases(state)
    _check_discovery_gradient(state, config)
    _check_species(state, config)
    if config.bigbang.topology_mode == "expansive":
        _check_expansive_no_chokepoint(state)


def _check_expansive_no_chokepoint(state: UniverseState) -> None:
    """Expansive-mode lattice invariant (§5 step 2): **no inter-region warp is a
    cut edge** — removing any single one leaves every sector reachable from sector
    1. That is the chokepoint-free / two-edge-disjoint-paths property the band
    lattice promises; a rare construction gap trips it and generation retries with
    a perturbed sub-seed.
    """
    adjacency = state.adjacency
    all_sectors = set(state.sectors)

    def _reachable_excluding(ex_u: int, ex_v: int) -> int:
        seen = {1}
        queue: deque[int] = deque([1])
        while queue:
            cur = queue.popleft()
            for nxt in adjacency.get(cur, ()):
                if cur == ex_u and nxt == ex_v:
                    continue
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return len(seen)

    region = {sid: sector.region_id for sid, sector in state.sectors.items()}
    for u, nbrs in adjacency.items():
        for v in nbrs:
            if region[u] != region[v] and _reachable_excluding(u, v) != len(all_sectors):
                raise ValidationError(f"expansive chokepoint: warp {u}->{v} is a cut edge")


def _check_reachable(state: UniverseState) -> None:
    reached = set(bfs_distances(state.adjacency, 1))
    missing = set(state.sectors) - reached
    if missing:
        raise ValidationError(f"{len(missing)} sectors unreachable from sector 1")


def _check_degree_cap(state: UniverseState, config: GameConfig) -> None:
    cap = config.bigbang.max_warps_per_sector
    for sector in state.sectors.values():
        if len(sector.warps_out) > cap:
            raise ValidationError(f"sector {sector.id} exceeds the warp cap ({cap})")


def _check_stardock(state: UniverseState) -> None:
    docks = [p for p in state.ports.values() if p.klass is PortClass.STARDOCK]
    if len(docks) != 1:
        raise ValidationError(f"expected exactly one StarDock, found {len(docks)}")
    if docks[0].sector_id not in bfs_distances(state.adjacency, 1):
        raise ValidationError("StarDock is unreachable from sector 1")


def _best_roundtrip_margin(sell_port: Port, buy_port: Port, config: GameConfig) -> int:
    """Best per-unit profit buying a commodity from `sell_port` and selling to `buy_port`."""
    best = 0
    for commodity in Commodity:
        sell_line = sell_port.line(commodity)  # port sells -> player buys here
        buy_line = buy_port.line(commodity)  # port buys -> player sells here
        if sell_line is None or buy_line is None:
            continue
        if sell_line.mode is not PortMode.SELL or buy_line.mode is not PortMode.BUY:
            continue
        margin = port_unit_price(buy_line, config.economy) - port_unit_price(sell_line, config.economy)
        best = max(best, margin)
    return best


def _check_planet_ownership(state: UniverseState, config: GameConfig) -> None:
    """Ownership invariants (§4.2 / §5 step 8): Core governor-owned, unowned fraction
    non-decreasing across bands, and at least one habitable Hub world."""
    gov = state.game.core_governing_alliance_id
    per_band: dict[str, list[int]] = {}  # band -> [1 if unowned else 0]
    hub_habitable = False
    for planet in state.planets.values():
        sector = state.sectors[planet.sector_id]
        if sector.is_galactic_core:
            if planet.owner.kind != "alliance" or planet.owner.ref != gov:
                raise ValidationError(f"Core planet {planet.id} is not governor-owned")
            continue
        per_band.setdefault(sector.distance_band, []).append(0 if planet.owner.is_owned else 1)
        profile = config.planets.types.get(planet.planet_type)
        if sector.distance_band == "Hub" and profile is not None and profile.colonizable:
            hub_habitable = True

    if not hub_habitable and any(s.distance_band == "Hub" for s in state.sectors.values()):
        raise ValidationError("no habitable world in the Hub band")

    prev = -1.0
    for band in (b.name for b in config.bigbang.active_bands()):
        flags = per_band.get(band)
        if not flags:
            continue
        frac = sum(flags) / len(flags)
        if frac < prev - 1e-9:
            raise ValidationError(
                f"unowned fraction decreases at band {band} ({frac:.3f} < {prev:.3f})"
            )
        prev = frac


def _check_starbases(state: UniverseState) -> None:
    """Orbital-base invariants (§4.2 / §5 step 8, WP4).

    Every base sits in its planet's sector and is back-referenced by that planet;
    a derelict base sits only on an unowned, uninhabited world; and a base on an
    owned planet is operational (derelicts are an unowned-frontier reward, not a
    governing alliance's neglect).
    """
    for base in state.starbases.values():
        planet = state.planets.get(base.planet_id)
        if planet is None:
            raise ValidationError(f"starbase {base.id} references missing planet {base.planet_id}")
        if planet.starbase_id != base.id:
            raise ValidationError(f"planet {planet.id} does not back-reference starbase {base.id}")
        if base.sector_id != planet.sector_id:
            raise ValidationError(f"starbase {base.id} not in its planet's sector")
        if planet.owner.is_owned and not is_operational(base):
            raise ValidationError(f"starbase {base.id} on owned planet {planet.id} is derelict")
        if not is_operational(base) and (planet.owner.is_owned or planet.inhabited_by_species_id is not None):
            raise ValidationError(f"derelict starbase {base.id} is not on an unowned, uninhabited world")


def _check_discovery_gradient(state: UniverseState, config: GameConfig) -> None:
    """Discovery gradient (§7 / §5 step 8): mean rarity **and** value strictly rising
    across consecutive non-empty bands, so the deep frontier holds the richer finds."""
    if config.discovery is None or not state.discoveries:
        return
    by_band: dict[str, list[tuple[int, int]]] = {}  # band -> [(rarity rank, value)]
    for d in state.discoveries.values():
        band = state.sectors[d.sector_id].distance_band
        by_band.setdefault(band, []).append((d.rarity_tier.value, rarity_value(d.rarity_tier, config)))

    prev_rank = prev_value = -1.0
    for band in (b.name for b in config.bigbang.active_bands()):
        finds = by_band.get(band)
        if not finds:
            continue
        mean_rank = sum(r for r, _ in finds) / len(finds)
        mean_value = sum(v for _, v in finds) / len(finds)
        if mean_rank <= prev_rank or mean_value <= prev_value:
            raise ValidationError(
                f"discovery gradient not strictly increasing at band {band} "
                f"(rank {mean_rank:.2f}≤{prev_rank:.2f} or value {mean_value:.0f}≤{prev_value:.0f})"
            )
        prev_rank, prev_value = mean_rank, mean_value


def _check_species(state: UniverseState, config: GameConfig) -> None:
    """Alien-placement invariants (§6 / §5 step 8).

    Reference integrity (the governing alliance and every species' `alliance_id` resolve);
    Core placement (only the governor and the StarDock hub sit in Core Space, §6.3); the
    **Hub is peaceable** (every species in the innermost band is friendly, §5); and every
    non-empty band keeps at least one **friendly** contact (the §5 step-8 resupply
    invariant). Hostiles are permitted — and expected — in the outer bands; the
    *mean*-disposition-falls-outward gradient is an aggregate property checked over many
    seeds in the test suite (§13), not a per-universe invariant, since the mandated
    resupply anchor plus small per-band samples make strict per-seed monotonicity noisy.
    """
    if config.roster is None:
        return
    gov = state.game.core_governing_alliance_id
    if gov is not None and gov not in state.alliances:
        raise ValidationError(f"governing alliance {gov} is not in the roster")
    if not state.species:
        return

    core_ids = {s.id for s in state.sectors.values() if s.is_galactic_core}
    # The StarDock is a sanctioned Core-side contact point (high-traffic hub); the
    # governing alliance's own members also belong in the Core — it is their capital (WP18).
    dock_sector = next((p.sector_id for p in state.ports.values()
                        if p.klass is PortClass.STARDOCK), None)
    innermost = config.bigbang.active_bands()[0].name  # the Hub — peaceable by §5
    friendly_bands: set[str] = set()
    gov_in_core = 0
    for sp in state.species.values():
        if sp.alliance_id is not None and sp.alliance_id not in state.alliances:
            raise ValidationError(f"species {sp.id} references missing alliance {sp.alliance_id}")
        is_governor = sp.alliance_id is not None and sp.alliance_id == gov
        if sp.sector_id in core_ids:
            if sp.sector_id != dock_sector and not is_governor:
                raise ValidationError(f"species {sp.id} placed inside Core Space")
            if is_governor:
                gov_in_core += 1
        band = state.sectors[sp.sector_id].distance_band
        friendly = is_friendly(sp.base_disposition, config.aliens)
        if band == innermost and not friendly:
            raise ValidationError(f"species {sp.id} is not friendly in the peaceable Hub")
        if friendly:
            friendly_bands.add(band)

    # The governor inhabits its own capital: if the roster fields governing members, at
    # least one must be settled in the Core (WP18).
    if config.roster is not None and any(
        s.alliance_id == gov and s.alliance_role in ("leader", "member")
        for s in config.roster.species
    ) and gov_in_core == 0:
        raise ValidationError("the governing alliance does not inhabit its Core capital")

    for band in (b.name for b in config.bigbang.active_bands()):
        has_non_core = any(
            not s.is_galactic_core and s.distance_band == band for s in state.sectors.values()
        )
        if has_non_core and band not in friendly_bands:
            raise ValidationError(f"no friendly alien contact in band {band}")


def _check_profitable_pair(state: UniverseState, config: GameConfig) -> None:
    hops = bfs_distances(state.adjacency, 1)
    near = [
        p for p in state.ports.values()
        if hops.get(p.sector_id, 10**9) <= 5 and p.klass is not PortClass.STARDOCK
    ]
    for a in near:
        for b in near:
            if a.id != b.id and _best_roundtrip_margin(a, b, config) > 0:
                return
    raise ValidationError("no profitable opposed-class port pair within 5 hops of the Core")
