"""Nav-rose baker (edge/server/navstrip) — pure bearing-placed compass (§11)."""

from __future__ import annotations

import math

from rich.text import Text

from edge.core import dto
from edge.server import navstrip


def _strip(markup: str) -> str:
    # Faithful inverse of the baked markup: Rich un-escapes `\[` back to a literal
    # `[`, so plain-text offsets match the baker's canvas columns exactly.
    return Text.from_markup(markup).plain


def _warp(sector_id: int, bearing: float, display_id: int, *,
          band: str = "Hub", codes: list[str] | None = None,
          kind: str = "explored") -> dto.WarpDTO:
    return dto.WarpDTO(sector_id=sector_id, arrow="--", label="Region", kind=kind,
                       display_id=display_id, band=band, codes=codes or [], bearing=bearing)


def _sector(warps: list[dto.WarpDTO], *, core_bearing: float = math.pi) -> dto.SectorDTO:
    return dto.SectorDTO(region="Region", sector_id=99, flavor="", beacon=None, band="Hub",
                         warps=warps, display_id=999, core_bearing=core_bearing,
                         trail=[dto.TrailCrumb(11, "Hub"), dto.TrailCrumb(22, "Frontier")])


def test_every_warp_becomes_a_node_on_its_label() -> None:
    warps = [_warp(10, 0.0, 110, codes=["P"]), _warp(11, math.pi / 2, 111),
             _warp(12, math.pi, 112)]
    nav = navstrip.build_nav_strip(_sector(warps))
    assert {n.sector_id for n in nav.nodes} == {10, 11, 12}
    for node in nav.nodes:
        cell = _strip(nav.rows[node.row])[node.col0:node.col1]
        assert str(node.display_id) in cell  # the hitbox lands on the id text


def test_bearing_picks_the_octant() -> None:
    # East, North, West bearings → the right column / row of the rose.
    east, north, west = _warp(1, 0.0, 101), _warp(2, math.pi / 2, 102), _warp(3, math.pi, 103)
    nav = navstrip.build_nav_strip(_sector([east, north, west]))
    by_id = {n.sector_id: n for n in nav.nodes}
    center_col = by_id[2].col0  # north sits in the centre column, on the top row
    assert by_id[2].row == 0
    assert by_id[1].row == 2 and by_id[1].col0 > center_col  # east: middle row, right of centre
    assert by_id[3].row == 2 and by_id[3].col0 < center_col  # west: middle row, left of centre


def test_collision_spill_keeps_all_nodes_disjoint() -> None:
    # Six warps all pointing east are forced to spill across free octants.
    warps = [_warp(20 + i, 0.0, 200 + i) for i in range(6)]
    nav = navstrip.build_nav_strip(_sector(warps, core_bearing=0.1))
    assert len({n.sector_id for n in nav.nodes}) == 6
    boxes = [(n.row, n.col0, n.col1) for n in nav.nodes]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (r1, a0, a1), (r2, b0, b1) = boxes[i], boxes[j]
            if r1 == r2:
                assert a1 <= b0 or b1 <= a0  # no overlap on a shared row


def test_core_anchor_and_trail_present() -> None:
    nav = navstrip.build_nav_strip(_sector([_warp(10, 0.0, 110)], core_bearing=math.pi))
    assert any("Core" in _strip(row) for row in nav.rows)  # global-orientation anchor drawn
    assert nav.trail == [dto.TrailCrumb(11, "Hub"), dto.TrailCrumb(22, "Frontier")]  # passed through
    assert nav.you_display == 999


def _anchor_col(rows: list[str]) -> int:
    for row in rows:
        plain = _strip(row)
        if "Core" in plain:
            return plain.index("Core")
    raise AssertionError("no Core anchor found")


def test_core_anchor_side_is_fixed_and_configurable() -> None:
    # Core bearing due east (0.0) — the old bearing rule would have put the anchor on the
    # right. The fixed side wins regardless, so the anchor never jumps between sectors.
    east = _sector([_warp(10, 0.0, 110)], core_bearing=0.0)
    left = navstrip.build_nav_strip(east, core_anchor_side="left").rows
    right = navstrip.build_nav_strip(east, core_anchor_side="right").rows
    assert "◄ Core" in "\n".join(_strip(r) for r in left)   # pinned left, faces left
    assert "Core ►" in "\n".join(_strip(r) for r in right)  # pinned right, faces right
    assert _anchor_col(left) < _anchor_col(right)            # left edge vs right edge

    # A westward core bearing with the same fixed side still pins right (bearing ignored).
    west = _sector([_warp(10, 0.0, 110)], core_bearing=math.pi)
    assert "Core ►" in "\n".join(
        _strip(r) for r in navstrip.build_nav_strip(west, core_anchor_side="right").rows)


def test_fallback_to_gravity_axis_without_embedding() -> None:
    # No embedding: every bearing 0.0 → the baker uses each warp's <</>>/-- arrow.
    warps = [
        dto.WarpDTO(1, "<<", display_id=101, band="Hub"),
        dto.WarpDTO(2, ">>", display_id=202, band="Deep"),
        dto.WarpDTO(3, "--", display_id=303, band="Hub"),
    ]
    sector = dto.SectorDTO(region="R", sector_id=9, flavor="", beacon=None, band="Hub",
                           warps=warps, display_id=9)  # core_bearing defaults to 0.0
    nav = navstrip.build_nav_strip(sector)
    assert {n.sector_id for n in nav.nodes} == {1, 2, 3}


def test_bearings_are_rotated_relative_to_core_bearing() -> None:
    # Core is East (0.0). Anchor is on the left (West, math.pi).
    # Rotation is math.pi - 0.0 = math.pi.
    # Warp 1 (bearing 0.0, toward Core) should rotate to math.pi (Left).
    # Warp 2 (bearing math.pi, away from Core) should rotate to 0.0 / 2*math.pi (Right).
    toward_core = _warp(1, 0.0, 101)
    away_core = _warp(2, math.pi, 102)
    
    sector = _sector([toward_core, away_core], core_bearing=0.0)
    nav = navstrip.build_nav_strip(sector, core_anchor_side="left")
    
    by_id = {n.sector_id: n for n in nav.nodes}
    
    # toward_core (rotated to West/left) should be on the left of center,
    # and away_core (rotated to East/right) should be on the right.
    # Specifically, since West is column "L" and East is column "R",
    # by_id[1].col0 < by_id[2].col0 must hold.
    assert by_id[1].col0 < by_id[2].col0


def test_void_anchor_is_drawn_opposite_to_core_anchor() -> None:
    sector = _sector([_warp(10, 0.0, 110)], core_bearing=math.pi)

    # Left anchor -> Core is on left, Void is on right
    left = navstrip.build_nav_strip(sector, core_anchor_side="left").rows
    left_str = "\n".join(_strip(r) for r in left)
    assert "◄ Core" in left_str
    assert "Void ►" in left_str

    # Right anchor -> Void is on left, Core is on right
    right = navstrip.build_nav_strip(sector, core_anchor_side="right").rows
    right_str = "\n".join(_strip(r) for r in right)
    assert "◄ Void" in right_str
    assert "Core ►" in right_str


