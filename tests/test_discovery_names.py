"""Named discoveries (PT-49 / WP-PR2-04, DESIGN §7).

A find is a *place* you can talk about — "the Cygnus Veil" — not "Nebula ∗ Rare". Names are
drawn at creation from seeded per-kind pools (`names.discoveries`), so they are stable under
`(seed, command log)` replay; a **combat wreck takes the destroyed ship's own name**. Naming
rides a names-only sub-RNG, so it must not move a single discovery's placement.
"""

from __future__ import annotations

from collections import Counter

import pytest

from edge.bigbang.generator import generate
from edge.bigbang.naming import DiscoveryNamer
from edge.config import load_default_config
from edge.core.enums import DiscoveryKind
from edge.store.snapshots import state_hash

CFG = load_default_config()
SEEDS = (4, 11, 23)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_discovery_is_named(seed: int) -> None:
    state = generate(CFG, seed)
    assert state.discoveries
    unnamed = [d.id for d in state.discoveries.values() if not d.name.strip()]
    assert not unnamed, f"unnamed discoveries: {unnamed[:5]}"


@pytest.mark.parametrize("seed", SEEDS)
def test_names_are_unique_within_a_universe(seed: int) -> None:
    """Two finds never share a name — including across the later raid-cache pass."""
    names = Counter(d.name for d in generate(CFG, seed).discoveries.values())
    assert not [n for n, c in names.items() if c > 1]


def test_names_are_deterministic_from_the_seed() -> None:
    a = {d.id: d.name for d in generate(CFG, 4).discoveries.values()}
    b = {d.id: d.name for d in generate(CFG, 4).discoveries.values()}
    assert a == b
    other = {d.id: d.name for d in generate(CFG, 5).discoveries.values()}
    assert a != other  # a different universe names its finds differently


def test_naming_does_not_move_a_single_discovery() -> None:
    """The names-only sub-RNG rail (the reason this change is replay-safe).

    Naming must never perturb the placement draw the §7 band gradient and the golden replays
    depend on. Prove it by generating the same seed against a config with **no name pools at
    all**: every find must land in the same place, of the same kind and tier, with the same
    payload — only what it is *called* may differ.
    """
    def placement(state: object) -> dict[int, tuple[object, ...]]:
        return {d.id: (d.kind, d.rarity_tier, d.sector_id, d.planet_id, d.site_slot,
                       d.hidden, d.raid_cache, d.payload)
                for d in state.discoveries.values()}  # type: ignore[attr-defined]

    nameless = CFG.model_copy(
        update={"names": CFG.names.model_copy(update={"discoveries": {}})})
    named = generate(CFG, 4)
    unnamed = generate(nameless, 4)
    assert placement(named) == placement(unnamed)
    assert {d.name for d in named.discoveries.values()} != {
        d.name for d in unnamed.discoveries.values()}  # …only the names moved


def test_names_are_in_the_state_hash() -> None:
    """A name is persisted state: rename one and the fingerprint must move."""
    import dataclasses

    state = generate(CFG, 4)
    before = state_hash(state)
    did = next(iter(state.discoveries))
    state.discoveries[did] = dataclasses.replace(state.discoveries[did], name="Renamed")
    assert state_hash(state) != before


def test_a_kind_with_no_pool_falls_back_to_numbering() -> None:
    import random

    namer = DiscoveryNamer(None, random.Random(1))
    drawn = [namer.draw(DiscoveryKind.BLACK_HOLE) for _ in range(3)]
    assert drawn == ["Black Hole 1", "Black Hole 2", "Black Hole 3"]


def test_an_exhausted_pool_keeps_drawing_unique_names() -> None:
    import random

    from edge.core.config import NameList, NamesConfig

    names = NamesConfig(discoveries={
        "nebula": NameList(first_part=["Lone"], second_part=["Veil"])})
    namer = DiscoveryNamer(names, random.Random(1))
    drawn = [namer.draw(DiscoveryKind.NEBULA) for _ in range(3)]
    assert drawn[0] == "Lone Veil"
    assert len(set(drawn)) == 3, "an exhausted pool must not repeat itself"
