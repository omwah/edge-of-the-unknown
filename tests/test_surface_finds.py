"""POC archaeological identities and art on production surface discoveries."""

from __future__ import annotations

import pytest

from edge.core.enums import DiscoveryKind
from edge.core.surface_finds import FIND_KINDS, surface_find_kind, surface_find_name
from edge.groundwar.findart import ART_H, ART_W, generate_find_art


@pytest.mark.parametrize(
    ("kind", "allowed"),
    [
        (DiscoveryKind.RUINS, {"colonnade", "obelisk", "leviathan"}),
        (DiscoveryKind.ARTIFACT, {"cache", "obelisk", "leviathan"}),
        (DiscoveryKind.ANCIENT_TECH, {"beacon"}),
        (DiscoveryKind.CRASHED_SHIP, {"hulk"}),
    ],
)
def test_production_surface_kinds_select_poc_identities(
    kind: DiscoveryKind, allowed: set[str],
) -> None:
    selected = {surface_find_kind(kind, discovery_id) for discovery_id in range(12)}
    assert selected == allowed
    assert all(surface_find_name(kind, discovery_id) for discovery_id in range(12))


@pytest.mark.parametrize("kind", FIND_KINDS)
def test_poc_find_art_is_exact_size_and_deterministic(kind: str) -> None:
    first = generate_find_art(kind, 41)
    second = generate_find_art(kind, 41)
    assert first == second
    lines = first.plain.splitlines()
    assert len(lines) == ART_H
    assert {len(line) for line in lines} == {ART_W}
