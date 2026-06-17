"""Big-bang validation — the Phase-1 subset of DESIGN §5 step 8 / §13.

Asserts the invariants a new game must satisfy: every sector reachable from
sector 1, the warp-degree cap respected, exactly one reachable StarDock, and at
least one profitable opposed-class port pair within 5 hops of the Core (so a new
player can always earn). Richer §5 checks (home clusters, band monotonicity,
ownership) arrive with their Phase-2/3 generation steps.
"""

from __future__ import annotations

from edge.bigbang.topology import bfs_distances
from edge.core.config import GameConfig
from edge.core.economy import port_unit_price
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.models import Port, UniverseState


class ValidationError(Exception):
    """A generated universe violated a §5 invariant."""


def validate(state: UniverseState, config: GameConfig) -> None:
    _check_reachable(state)
    _check_degree_cap(state, config)
    _check_stardock(state)
    _check_profitable_pair(state, config)
    _check_planet_ownership(state, config)


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
    for band in (b.name for b in config.bigbang.bands):
        flags = per_band.get(band)
        if not flags:
            continue
        frac = sum(flags) / len(flags)
        if frac < prev - 1e-9:
            raise ValidationError(
                f"unowned fraction decreases at band {band} ({frac:.3f} < {prev:.3f})"
            )
        prev = frac


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
