"""Responsive archetype icon + service banner header shared by ports and starbases."""

from __future__ import annotations

from typing import Literal

from rich.text import Text
from textual import events
from textual.app import active_app
from textual.containers import Horizontal
from textual.widgets import Static

from edge.art.geometry_catalog import load_default_geometry_catalog
from edge.art.scene_paint import natural_fallback_dimensions
from edge.art.stations import render_station_art
from edge.core.config import SceneArtConfig
from edge.tui import art_adapter
from edge.tui.art_memory import remember, remembered

_FALLBACK = "[dim]◇═══ station link ═══◇[/]"


def station_icon_dimensions(app: object | None,
                            kind: Literal["port", "stardock", "starbase"],
                            _cinematic: bool, *,
                            expect_sector: int | None = None,
                            object_id: int | None = None) -> tuple[int, int]:
    """Exterior-art footprint beside a service banner, from scene config.

    `expect_sector`/`object_id` are the internal sector id and the port/starbase's
    own entity id of the station being drawn, when the caller knows them. The
    docking flow always renders the station's SectorScene last, so the published
    `(sector_id, station_kind, object_id)` reference (plan §4 invariant 12) should
    have an exact-match entry; a miss (no preceding render, a stale/mismatched
    sector, or a caller that hasn't threaded `object_id` through yet) falls back to
    the richest authored rung rather than trusting a partial or stale key.
    """
    cfg = getattr(app, "scene_art", None) or SceneArtConfig()
    ref = getattr(app, "sector_station_reference", None)
    if ref is not None and expect_sector is not None and object_id is not None:
        size = ref.lookup(expect_sector, kind, object_id)
        if size is not None:
            return size
    # Direct-open developer/test screens have no preceding Sector render (and a
    # stale/mismatched reference from another sector or station is treated the
    # same). Try the richest complete authored rung for this kind rather than
    # `SceneArtConfig`'s padded bounds — but every generated rung is keyed by a
    # real archetype id (`natural_fallback_dimensions` needs one to find a match;
    # this call site doesn't have the station's archetype to offer, so it misses
    # today and falls through). Threading an archetype id into this fallback is
    # left for a follow-up; `cfg.station_size` remains the honest last resort.
    fallback = natural_fallback_dimensions(load_default_geometry_catalog(), kind)
    if fallback is not None:
        return fallback
    size = cfg.station_size(kind)
    return size.max_width, size.max_height


class StationArtRow(Horizontal):
    """Exterior and banner sharing one explicitly centered vertical midpoint."""

    def __init__(
        self,
        kind: Literal["port", "stardock", "starbase"],
        icon: Static,
        banner: Static,
        expect_sector: int | None = None,
        object_id: int | None = None,
        **kwargs: object,
    ) -> None:
        self._station_kind = kind
        self._station_icon = icon
        self._station_banner = banner
        self._expect_sector = expect_sector
        self._object_id = object_id
        super().__init__(icon, banner, **kwargs)  # type: ignore[arg-type]
        app = active_app.get(None)
        cinematic = getattr(getattr(app, "layout_tier", None), "value", "standard") == "wide"
        self._center_art(app, cinematic)

    def _center_art(self, app: object | None, cinematic: bool) -> None:
        icon_width, icon_height = station_icon_dimensions(
            app, self._station_kind, cinematic,
            expect_sector=self._expect_sector, object_id=self._object_id)
        banner_height = 12 if cinematic else 8
        row_height = max(icon_height, banner_height)
        self.styles.height = row_height
        self._station_icon.styles.width = icon_width
        self._station_icon.styles.height = icon_height
        self._station_icon.offset = (0, (row_height - icon_height + 1) // 2)
        self._station_banner.offset = (0, (row_height - banner_height + 1) // 2)

    def on_mount(self) -> None:
        cinematic = getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "wide"
        self._center_art(self.app, cinematic)

    def on_resize(self) -> None:
        cinematic = getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "wide"
        self._center_art(self.app, cinematic)


class _StationArt(Static):
    def __init__(self, kind: Literal["port", "starbase"], archetype_id: str, service: str,
                 condition: str, *, icon: bool, identity: int,
                 cinematic: bool = False, theme: str = "",
                 icon_size: tuple[int, int] | None = None,
                 expect_sector: int | None = None,
                 object_id: int | None = None) -> None:
        # Open on the art we drew last time, not the text fallback (PT-42): a screen that
        # rebuilds itself on every action would otherwise flash the placeholder until
        # `on_mount` re-rendered, which reads as the art "resetting" each time you act.
        # Tier and theme are part of the key — they change the image, so remembering them
        # apart stops a panel opening on the wrong-sized render and then snapping.
        self._key = (kind, archetype_id, service, condition, icon, identity,
                     cinematic, theme, icon_size)
        super().__init__(remembered(self._key) or _FALLBACK,
                         classes="station-icon" if icon else "station-banner")
        self._kind = kind
        self._archetype = archetype_id
        self._service = service
        self._condition = condition
        self._icon = icon
        self._identity = identity
        self._expect_sector = expect_sector
        self._object_id = object_id
        if icon_size is not None:
            self.styles.width, self.styles.height = icon_size

    def on_mount(self) -> None:
        self.app.theme_changed_signal.subscribe(self, lambda _theme: self._refresh())
        self._refresh()

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh()

    def _refresh(self) -> None:
        cinematic = getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "wide"
        icon_size = (station_icon_dimensions(self.app, self._kind, cinematic,
                                             expect_sector=self._expect_sector,
                                             object_id=self._object_id)
                     if self._icon else None)
        self._key = (self._kind, self._archetype, self._service, self._condition,
                     self._icon, self._identity, cinematic, str(self.app.theme), icon_size)
        try:
            art: Text
            if self._icon:
                assert icon_size is not None
                width, height = icon_size
                self.styles.width, self.styles.height = icon_size
                subtype = "trading_port" if self._kind == "port" else "starbase"
                art = art_adapter.sprite(
                    "port", subtype, seed=self._identity, width=width, height=height,
                    archetype_id=self._archetype,
                )
                if self._condition == "derelict":
                    art.stylize("dim")
                elif self._condition == "hostile":
                    art.stylize("on dark_red")
            else:
                art = render_station_art(
                    self._kind, self._archetype, self._service, str(self.app.theme),
                    cinematic=cinematic, condition=self._condition,
                )
        except (ImportError, OSError, ValueError):
            self.update(_FALLBACK)
            return
        self.update(remember(self._key, art))


class StationArtHeader(StationArtRow):
    """Stardock-model header: station exterior at left, active-service scene at right."""

    DEFAULT_CSS = """
    StationArtHeader { height: 8; margin-bottom: 1; align: left middle; }
    StationArtHeader .station-icon {
        width: 24; height: 8; margin-right: 1; content-align: left top;
    }
    StationArtHeader .station-banner { width: 56; height: 8; content-align: left top; }
    .compact StationArtHeader, StationArtHeader.compact { display: none; }
    .wide StationArtHeader, StationArtHeader.wide { height: 12; }
    .wide StationArtHeader .station-icon, StationArtHeader.wide .station-icon {
        width: 36; height: 12;
    }
    .wide StationArtHeader .station-banner, StationArtHeader.wide .station-banner {
        width: 72; height: 12;
    }
    """

    def __init__(self, kind: Literal["port", "starbase"], archetype_id: str, service: str, *,
                 identity: int, condition: str = "open",
                 expect_sector: int | None = None,
                 object_id: int | None = None) -> None:
        # Read the tier/theme here, at compose time, where the app is reachable, so each
        # panel opens on the art it last drew *at this size* (edge.tui.art_memory).
        app = active_app.get(None)
        cinematic = getattr(getattr(app, "layout_tier", None), "value", "standard") == "wide"
        theme = str(getattr(app, "theme", ""))
        icon_size = station_icon_dimensions(app, kind, cinematic,
                                            expect_sector=expect_sector, object_id=object_id)
        super().__init__(
            kind,
            _StationArt(kind, archetype_id, service, condition,
                        icon=True, identity=identity, cinematic=cinematic, theme=theme,
                        icon_size=icon_size, expect_sector=expect_sector, object_id=object_id),
            _StationArt(kind, archetype_id, service, condition,
                        icon=False, identity=identity, cinematic=cinematic, theme=theme),
            expect_sector=expect_sector,
            object_id=object_id,
        )

    def on_mount(self) -> None:
        super().on_mount()
        tier = getattr(getattr(self.app, "layout_tier", None), "value", "standard")
        self.add_class(tier)

    def on_resize(self) -> None:
        super().on_resize()
        for tier in ("compact", "standard", "wide"):
            self.remove_class(tier)
        self.add_class(getattr(getattr(self.app, "layout_tier", None), "value", "standard"))
