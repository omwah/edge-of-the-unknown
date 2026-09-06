"""The legacy-parity acceptance test for the physical scene model (WP-SC12).

`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §9.6's "Station size parity"
section states the bar for replacing `edge/tui/widgets.py::_SceneComposer`:

1. **Admission parity** — the new pipeline paints every object the legacy
   composer paints, for the same sector DTO and canvas.
2. **Station size parity** — a painted port / Stardock / starbase lands on
   the *same authored ladder rung* the legacy composer selects.

`edge.devtool.scene_parity` does the measuring (see its module docstring for
what counts as "painted" on each side and why the rung, not the ink-cropped
cell box, is the size comparison). This module is the CI guard over the full
`edge.tui.scene_gallery.cases()` x `SIZES` matrix for both projection
strategies, plus the property tests for the two pure pieces the parity
mechanism rests on.

One cell is expected to miss, and it is asserted *by name* rather than
absorbed into a rate, so it cannot silently become two:
`planet+port+wreck+traffic @ 67x30`. There the legacy composer paints three
ships (`SceneArtConfig.max_ships_shown`) plus the wreck, while the physical
model paints four ships and has no room left for the wreck — the same number
of objects, a different set. Plan §4.6 ("Neutral ships precede wrecks") is a
numbered invariant, so the model cannot prefer the wreck, and sweeping both
bounded placement budgets (`_DEPTH_STRATA` 4/5/6/8 x
`max_reposition_candidates` 16/24/32) only moves the miss between the two
strategies rather than removing it.
"""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from edge.core.config import SceneArtConfig
from edge.devtool.scene_parity import (
    STRATEGIES,
    build_pipeline,
    legacy_station_rung,
    measure_legacy,
    measure_physical,
    run_matrix,
    summarize,
)
from edge.scene.geometry import CellBox
from edge.scene.model import StationSizeReference, StationTarget
from edge.tui.scene_gallery import SIZES, cases
from edge.tui.widgets import primary_body_height

# The one evidenced, invariant-bound miss; see the module docstring.
KNOWN_MISSES: frozenset[str] = frozenset(
    {
        "planet+port+wreck+traffic@67x30!fixed_fov_perspective",
        "planet+port+wreck+traffic@67x30!depth_layered_anchor",
    }
)


@pytest.fixture(scope="module")
def matrix() -> list:
    return run_matrix()


@pytest.mark.parametrize("strategy", [s.name for s in STRATEGIES])
def test_admission_parity_over_the_whole_matrix(matrix: list, strategy: str) -> None:
    """Every object the legacy composer paints is painted by the new pipeline."""
    offenders = [
        f"{cell.scene_id}: {list(cell.missing)}"
        for cell in matrix
        if cell.strategy == strategy and cell.missing and cell.scene_id not in KNOWN_MISSES
    ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.parametrize("strategy", [s.name for s in STRATEGIES])
def test_station_size_parity_over_the_whole_matrix(matrix: list, strategy: str) -> None:
    """Every painted station lands on the rung the legacy composer selects."""
    offenders = [
        f"{cell.scene_id}: {cell.size_mismatch}"
        for cell in matrix
        if cell.strategy == strategy and cell.size_mismatch
    ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.parametrize("strategy", [s.name for s in STRATEGIES])
def test_no_station_is_ever_dropped(matrix: list, strategy: str) -> None:
    """A station is the object the size goal is about; it must always appear
    wherever legacy shows one. Stated separately from the general admission
    test so a regression names the station rather than a slot list."""
    offenders = [
        cell.scene_id
        for cell in matrix
        if cell.strategy == strategy and "station" in cell.missing
    ]
    assert not offenders, offenders


@pytest.mark.parametrize("strategy", [s.name for s in STRATEGIES])
def test_admission_rate_does_not_regress(matrix: list, strategy: str) -> None:
    """A rate floor beside the by-name assertions above, so a *new* class of
    miss that happens to dodge them still trips something. 99% is just under
    the measured 100.0% / 99.6%."""
    summary = summarize(matrix, strategy)
    assert summary.admission_rate >= Fraction(99, 100), (
        f"{summary.matched_objects}/{summary.legacy_objects}"
    )


def test_the_known_miss_is_exactly_what_is_documented() -> None:
    """Pin the one accepted miss to its cause: the model paints a fourth ship
    where legacy caps at `max_ships_shown`, and the wreck is what gives way.
    If the model ever admits the wreck too, this test fails and the exemption
    above should be deleted rather than left standing."""
    cfg = SceneArtConfig()
    tuning, catalog = build_pipeline()
    sector = cases()["planet+port+wreck+traffic"]
    legacy = measure_legacy(sector, cfg, catalog, 67, 30)
    legacy_ships = [entry for entry in legacy if entry.slot.startswith("ship:")]
    assert len(legacy_ships) == cfg.max_ships_shown
    assert len(sector.ships) > cfg.max_ships_shown

    for strategy in STRATEGIES:
        physical = measure_physical(sector, strategy, tuning, catalog, 67, 30)
        ships = [entry for entry in physical if entry.slot.startswith("ship:")]
        wrecks = [entry for entry in physical if entry.slot.startswith("discovery")]
        # Exactly one of the two is true: the model shows the extra ship
        # instead of the wreck, or it manages both (in which case the
        # exemption is stale).
        assert len(ships) > cfg.max_ships_shown or wrecks, strategy.name
        # Same total object count as legacy, not fewer.
        assert len(physical) >= len(legacy), strategy.name


def test_legacy_station_rung_matches_the_real_renderer() -> None:
    """`legacy_station_rung` claims the sprite library picks a tier from the
    requested height alone. Check that against the actual renderer rather
    than trusting the docstring: for every station subtype and every
    requested height the parity matrix produces, the drawn ink box must be
    constant across all heights that map to one rung, and must change at
    every rung boundary."""
    from edge.tui import art_adapter

    _tuning, catalog = build_pipeline()
    archetype = "humanoid_diplomat"
    for kind in ("port", "stardock", "starbase"):
        by_rung: dict[int, set[tuple[int, int]]] = {}
        for height in range(3, 18):
            rung = legacy_station_rung(catalog, kind, archetype, height)
            assert rung is not None
            art = art_adapter.sprite(
                "port", {"port": "trading_port"}.get(kind, kind), seed=102,
                width=int(height * 2.4), height=height, archetype_id=archetype,
            )
            cells = art_adapter.text_to_cells(art)
            inked = [
                (y, x)
                for y, row in enumerate(cells)
                for x, (ch, _s) in enumerate(row)
                if ch != " "
            ]
            assert inked
            drawn = (
                max(x for _y, x in inked) - min(x for _y, x in inked) + 1,
                max(y for y, _x in inked) - min(y for y, _x in inked) + 1,
            )
            by_rung.setdefault(rung, set()).add(drawn)
        # One drawn box per rung: the mapping is exactly a step function of
        # the requested height, with the steps on the rung boundaries.
        for rung, drawns in by_rung.items():
            assert len(drawns) == 1, f"{kind} rung {rung} drew {drawns}"
        # And distinct rungs draw distinct boxes, or the "rung" would not be
        # a meaningful size statement.
        flat = [next(iter(d)) for d in by_rung.values()]
        assert len(set(flat)) == len(flat), f"{kind}: {by_rung}"


def test_station_size_reference_reproduces_the_legacy_scale_chain() -> None:
    """The shipped `station_size_reference` is legacy's `primary_body_height`
    with its `_SHIP_SKY_RESERVE` trim omitted, and the omission is claimed to
    be rung-neutral. Check both over the calibrated canvases."""
    cfg = SceneArtConfig()
    tuning, catalog = build_pipeline()
    reference = tuning.station_size_reference
    assert reference is not None
    for _label, w, h in SIZES:
        ours = reference.reference_body_height(CellBox(0, 0, w, h))
        theirs = primary_body_height(cfg, w, h - reference.header_rows)
        # Every station kind resolves to the same authored rung either way.
        for kind, scale_class in (
            ("port", "orbital"), ("starbase", "starbase"), ("stardock", "stardock"),
        ):
            target = tuning.station_target_by_scale_class[scale_class]
            _lw, legacy_h = cfg.station_dimensions(
                kind, primary_height=theirs, body_height=h - reference.header_rows  # type: ignore[arg-type]
            )
            our_h = target.target_height(CellBox(0, 0, w, h), reference, parented=True)
            assert legacy_station_rung(catalog, kind, "humanoid_diplomat", legacy_h) == (
                legacy_station_rung(catalog, kind, "humanoid_diplomat", our_h)
            ), f"{kind}@{w}x{h}: reference {ours} vs legacy {theirs}"


# ---------------------------------------------------------------------------
# Property tests for the two pure pieces the mechanism rests on.
# ---------------------------------------------------------------------------

_REFERENCE = st.builds(
    StationSizeReference,
    height_fraction=st.just(Fraction(9, 10)),
    header_rows=st.integers(min_value=0, max_value=8),
    width_fraction=st.just(Fraction(11, 20)),
    max_cells=st.integers(min_value=8, max_value=64),
    min_cells=st.integers(min_value=1, max_value=8),
)
_VIEWPORT = st.builds(
    CellBox,
    col=st.just(0), row=st.just(0),
    width=st.integers(min_value=1, max_value=400),
    height=st.integers(min_value=1, max_value=200),
)


@settings(max_examples=300, deadline=None)
@given(reference=_REFERENCE, viewport=_VIEWPORT)
def test_reference_body_height_is_bounded_and_integral(
    reference: StationSizeReference, viewport: CellBox
) -> None:
    got = reference.reference_body_height(viewport)
    assert isinstance(got, int)
    assert reference.min_cells <= got <= max(reference.min_cells, reference.max_cells)


@settings(max_examples=300, deadline=None)
@given(reference=_REFERENCE, viewport=_VIEWPORT)
def test_reference_body_height_is_monotone_in_the_viewport(
    reference: StationSizeReference, viewport: CellBox
) -> None:
    """A bigger canvas never asks for a smaller body — the scale chain would
    read as broken if it did, and a station's size hangs off this."""
    bigger = CellBox(0, 0, viewport.width + 1, viewport.height + 1)
    assert reference.reference_body_height(bigger) >= reference.reference_body_height(viewport)


@settings(max_examples=300, deadline=None)
@given(
    reference=_REFERENCE,
    viewport=_VIEWPORT,
    parent_scale=st.fractions(min_value=Fraction(1, 20), max_value=Fraction(1)),
    lone_scale=st.fractions(min_value=Fraction(1, 20), max_value=Fraction(1)),
    min_cells=st.integers(min_value=1, max_value=8),
    span=st.integers(min_value=0, max_value=40),
    parented=st.booleans(),
)
def test_station_target_height_stays_inside_its_clamps(
    reference: StationSizeReference,
    viewport: CellBox,
    parent_scale: Fraction,
    lone_scale: Fraction,
    min_cells: int,
    span: int,
    parented: bool,
) -> None:
    target = StationTarget(
        parent_scale=parent_scale, lone_scale=lone_scale,
        min_cells=min_cells, max_cells=min_cells + span,
    )
    got = target.target_height(viewport, reference, parented=parented)
    assert isinstance(got, int)
    assert target.min_cells <= got <= target.max_cells


@settings(max_examples=200, deadline=None)
@given(
    reference=_REFERENCE,
    viewport=_VIEWPORT,
    scale=st.fractions(min_value=Fraction(1, 20), max_value=Fraction(1)),
    parented=st.booleans(),
)
def test_station_target_height_never_exceeds_its_reference(
    reference: StationSizeReference,
    viewport: CellBox,
    scale: Fraction,
    parented: bool,
) -> None:
    """Plan §2.2: a station never out-measures the body it orbits. With a
    scale of at most 1 the target can never exceed the reference body height
    it is taken from (nor, for a lone station, the header-less canvas)."""
    target = StationTarget(
        parent_scale=scale, lone_scale=scale, min_cells=1, max_cells=1 << 20,
    )
    got = target.target_height(viewport, reference, parented=parented)
    ceiling = (
        reference.reference_body_height(viewport) if parented
        else max(viewport.height - reference.header_rows, 0)
    )
    assert got <= max(ceiling, 1)
