"""Nav-rose widget presentation (WP-PR2-07 / PT-48, PT-55).

`NavRose` bakes two client-side columns beside the compass: a recent-route *trail* and
a selected-warp *detail* panel. These pin the two playtest fixes — the trail ids read in
the same band palette as the rose cells, and a one-way warp is marked "one-way" while its
destination id is masked until the target is charted.
The column builders are pure (they read the DTO passed to `__init__`), so they are
exercised directly without mounting the widget.
"""

from __future__ import annotations

from edge.core import dto
from edge.server.canvas import BAND_COLOR
from edge.tui.widgets import NavRose


def _rose(*, trail: list[dto.TrailCrumb], warp: dto.WarpDTO | None = None) -> NavRose:
    nodes = []
    warps: list[dto.WarpDTO] = []
    if warp is not None:
        nodes = [dto.MapNodeDTO(sector_id=warp.sector_id, display_id=warp.display_id,
                                row=2, col0=0, col1=3)]
        warps = [warp]
    nav = dto.NavStripDTO(rows=["", "", "@", "", ""], nodes=nodes, trail=trail, you_display=999)
    return NavRose(nav, warps)


def test_trail_ids_are_tinted_by_band_like_the_rose() -> None:
    # PT-55: each crumb's id carries its band's colour (the same BAND_COLOR the rose cells
    # use), packed toward the bottom; "you" stays the bold-cyan anchor.
    rose = _rose(trail=[dto.TrailCrumb(11, "Hub"), dto.TrailCrumb(22, "Deep")])
    col = rose._trail_column()
    assert (col[2].plain, col[2].style) == ("11", BAND_COLOR["Hub"])      # cyan
    assert (col[3].plain, col[3].style) == ("22", BAND_COLOR["Deep"])     # magenta
    assert col[4].plain == "999" and "cyan" in str(col[4].style)          # you


def test_unknown_band_crumb_falls_back_to_dim() -> None:
    rose = _rose(trail=[dto.TrailCrumb(7, "")])
    col = rose._trail_column()
    assert (col[3].plain, col[3].style) == ("7", "dim")


def test_one_way_warp_to_a_charted_sector_shows_id_and_one_way() -> None:
    # PT-48: a one-way warp to a sector you've already charted marks "one-way" and still
    # shows the destination id — you know where it goes.
    warp = dto.WarpDTO(sector_id=5, arrow=">>", label="Rim", kind="explored",
                       display_id=105, band="Deep", one_way=True, turn_cost=2)
    rose = _rose(trail=[], warp=warp)
    detail = " ".join(line.plain for line in rose._detail_column(rose._hits[0]))
    assert "one-way" in detail
    assert "105" in detail  # charted → address shown


def test_one_way_warp_to_an_uncharted_sector_hides_the_address() -> None:
    # PT-48: sensors reveal the exit is one-way (like a wormhole), but the destination id is
    # masked until you take it — the detail header reads `S?????` (one `?` per id digit).
    warp = dto.WarpDTO(sector_id=5, arrow=">>", kind="unexplored",
                       display_id=10547, one_way=True, turn_cost=2)
    rose = _rose(trail=[], warp=warp)
    detail = " ".join(line.plain for line in rose._detail_column(rose._hits[0]))
    assert "one-way" in detail
    assert "10547" not in detail and "S?????" in detail  # address hidden, one ? per digit


def test_two_way_warp_shows_no_one_way_marker() -> None:
    warp = dto.WarpDTO(sector_id=5, arrow=">>", label="Rim", kind="explored",
                       display_id=105, band="Deep", one_way=False, turn_cost=1)
    rose = _rose(trail=[], warp=warp)
    detail = " ".join(line.plain for line in rose._detail_column(rose._hits[0]))
    assert "one-way" not in detail
