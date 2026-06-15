"""Hourly port stock regeneration (DESIGN §8, §9).

A pure maintenance reducer: each port's commodity stock moves a fixed fraction
toward its desired level (50% capacity standard, 90% StarDock). Regeneration is
silent state evolution — it emits no per-commodity events (which at scale would
flood the log); the new ports are simply upserted.
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.config import GameConfig
from edge.core.economy import regenerate_stock
from edge.core.enums import PortClass
from edge.core.models import UniverseState
from edge.core.rules import ReduceResult


def regenerate_ports(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Regenerate every port's stock toward its desired level."""
    econ = config.economy
    new_ports = []
    for port in state.ports.values():
        desired = (
            econ.desired_stock_frac_stardock
            if port.klass is PortClass.STARDOCK
            else econ.desired_stock_frac_standard
        )
        lines = tuple(
            replace(
                line,
                stock=regenerate_stock(
                    line.stock, line.capacity,
                    desired_frac=desired, regen_frac=econ.regen_fraction,
                ),
            )
            for line in port.commodities
        )
        new_ports.append(replace(port, commodities=lines))
    return ReduceResult(ports=tuple(new_ports))
