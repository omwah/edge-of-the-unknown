from pathlib import Path

import pytest
from rich.cells import cell_len

from edge.art.concourse import (
    STARDOCK_ART_TABS,
    concourse_asset,
    render_concourse,
    render_stardock_art,
    stardock_asset,
)


@pytest.mark.parametrize("theme", [
    "edge-ansi", "edge-high-contrast", "edge-monochrome",
])
@pytest.mark.parametrize("cinematic, expected", [(False, (56, 8)), (True, (72, 12))])
def test_concourse_variants_fill_their_terminal_box(
    theme: str, cinematic: bool, expected: tuple[int, int]
) -> None:
    path = concourse_asset(theme, cinematic=cinematic)
    assert path.is_file()

    art = render_concourse(theme, cinematic=cinematic)
    lines = art.plain.splitlines()
    assert len(lines) == expected[1]
    assert max(cell_len(line) for line in lines) == expected[0]


def test_unknown_theme_uses_default_variant() -> None:
    assert concourse_asset("unknown", cinematic=False) == concourse_asset(
        "edge-ansi", cinematic=False
    )


def test_accessibility_variants_are_explicit_assets() -> None:
    paths = {
        concourse_asset(theme, cinematic=True)
        for theme in ("edge-ansi", "edge-high-contrast", "edge-monochrome")
    }
    assert len(paths) == 3
    assert all(isinstance(path, Path) and path.is_file() for path in paths)


@pytest.mark.parametrize("tab", sorted(STARDOCK_ART_TABS))
@pytest.mark.parametrize("theme", [
    "edge-ansi", "edge-high-contrast", "edge-monochrome",
])
@pytest.mark.parametrize("cinematic, expected", [(False, (56, 8)), (True, (72, 12))])
def test_every_stardock_tab_has_responsive_accessible_art(
    tab: str, theme: str, cinematic: bool, expected: tuple[int, int]
) -> None:
    assert stardock_asset(tab, theme, cinematic=cinematic).is_file()
    lines = render_stardock_art(tab, theme, cinematic=cinematic).plain.splitlines()
    assert len(lines) == expected[1]
    assert max(cell_len(line) for line in lines) == expected[0]


def test_unknown_stardock_tab_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown StarDock art tab"):
        stardock_asset("brig", "edge-ansi", cinematic=False)
