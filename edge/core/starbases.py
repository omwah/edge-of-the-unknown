"""Orbital starbase helpers (DESIGN §4.2) — pure core, no I/O, no RNG.

A starbase reuses the engine-room slotted-subsystem model (§4.1) minus mobility,
plus a `fusion_reactor`. **Derelict is emergent, not a stored flag**: a base is
operational only while its reactor keystone (the structural `converter`) is filled
and undamaged — strip or knock it out and the base can no longer power itself, so
it reads as derelict. The big bang makes unowned-world bases derelict by removing
that keystone, leaving the remaining components as a salvage cache (WP4); repair is
just refilling the slot (Phase 3). `is_operational` is the seam Phase-3 planetary
defense will read.
"""

from __future__ import annotations

from edge.core.enums import Subsystem
from edge.core.models import Starbase


def is_operational(base: Starbase) -> bool:
    """Whether `base` can power itself — its reactor keystone is filled and intact.

    Derelict is exactly `not is_operational(base)` (§4.2): no separate flag.
    """
    reactor = base.subsystems.get(Subsystem.FUSION_REACTOR)
    if reactor is None or reactor.keystone_index is None:
        return False
    keystone = reactor.slots[reactor.keystone_index]
    return keystone is not None and not keystone.knocked_out
