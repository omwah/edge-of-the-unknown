"""Service-point resolution — where a ship may repair, buy, and bank (§4.1, §4.2, WP53).

DESIGN §4.1 promises "full restoration… at StarDock **or a friendly alien base**", and
§4.2 pays off a repaired, claimed orbital base as a *forward foothold* that offers a
config-gated subset of StarDock services in deep space. This module is the single seam
that decides, for the ship's current sector, **which provider serves it and at what
fee** — so the dock-service reducers (`RepairAtDock`, `BuyComponent`, `BuyMissiles`,
`Deposit`/`Withdraw`) run *one* code path against *two* providers rather than cloning
each command into an `…AtBase` sibling. Command names and payloads are unchanged; only
the rejection condition widens from "must be at a StarDock" to "must be at a service
point offering this service".

Pure and side-effect-free (like `aliens.may_occupy`), so reducers and the projection
share it. A *friendly alien base* provider is a future config extension of the same
seam, not a new code path.
"""

from __future__ import annotations

from dataclasses import dataclass

from edge.core import corp
from edge.core.config import GameConfig
from edge.core.enums import PortClass
from edge.core.models import Player, Ship, UniverseState
from edge.core.starbases import services_operational

# The dock-gated service kinds a service point may offer (the closed vocabulary the
# reducers check against). Kept as plain strings so they cross the config/DTO seams
# without an enum import cycle.
REPAIR = "repair"
COMPONENTS = "components"
MUNITIONS = "munitions"
BANKING = "banking"

# A StarDock is the full-service provider at no markup — the balance baseline.
_STARDOCK_SERVICES = frozenset({REPAIR, COMPONENTS, MUNITIONS, BANKING})


@dataclass(frozen=True, slots=True)
class ServicePoint:
    """The provider serving a ship's current sector (§4.2, WP53).

    `kind` is ``"stardock"`` or ``"player_base"``; `ref` is the port id (StarDock) or
    starbase id (base). `services` is the frozenset of offered `ServiceKind` strings;
    `fee_frac` is the multiplier applied to latinum prices (``1.0`` at a StarDock, the
    base's configured markup at a foothold — never below 1.0).
    """

    kind: str
    ref: int
    services: frozenset[str]
    fee_frac: float


def service_point(
    state: UniverseState, player: Player, ship: Ship, config: GameConfig
) -> ServicePoint | None:
    """The service provider for the ship's current sector, or None (§4.1/§4.2, WP53).

    A StarDock in the sector always wins (full services, no markup). Otherwise a
    **player-owned** orbital base in the sector that is powered *and above the integrity
    gate* (`services_operational`, WP-PR04) serves the config-gated subset at its markup —
    the forward-foothold payoff. Everything else (no port, a trade port, a derelict/rival
    base, or a base battered below the service threshold) yields None, so the service
    reducers reject.
    """
    sector_id = ship.sector_id
    port = state.port_in_sector(sector_id)
    if port is not None and port.klass is PortClass.STARDOCK:
        return ServicePoint("stardock", port.id, _STARDOCK_SERVICES, 1.0)

    if config.starbase is None:
        return None  # no orbital bases in this universe — no foothold possible
    sc = config.starbase.services
    for base in sorted(state.starbases.values(), key=lambda b: b.id):
        if base.sector_id != sector_id:
            continue
        if corp.player_owns(state, base.owner, player.id) and services_operational(base, config):
            offered = frozenset(
                kind for kind, on in (
                    (REPAIR, sc.repair), (COMPONENTS, sc.components),
                    (MUNITIONS, sc.munitions), (BANKING, sc.banking))
                if on
            )
            return ServicePoint("player_base", base.id, offered, sc.fee_frac)
    return None


def require_service(
    state: UniverseState, player: Player, ship: Ship, service: str, config: GameConfig,
) -> ServicePoint:
    """The service point offering `service` here, or raise (the reducer gate, WP53).

    Consolidates the old `_stardock` check: a service is available at a StarDock or at a
    player base that enables it. The error names *why* — no provider, or one that does
    not offer this service — so the UI can explain the rejection.
    """
    from edge.core.economy import EconomyError

    sp = service_point(state, player, ship, config)
    if sp is None:
        raise EconomyError("that service is offered only at a StarDock or a base you own here")
    if service not in sp.services:
        raise EconomyError(f"this base does not offer {service}")
    return sp
