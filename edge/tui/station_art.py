"""Responsive archetype icon + service banner header shared by ports and starbases."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.containers import Horizontal
from textual.widgets import Static

from edge.art.stations import render_station_art
from edge.tui import art_adapter
from edge.tui.art_memory import remember, remembered

_FALLBACK = "[dim]◇═══ station link ═══◇[/]"


class _StationArt(Static):
    def __init__(self, kind: str, archetype_id: str, service: str,
                 condition: str, *, icon: bool, identity: int,
                 cinematic: bool = False, theme: str = "") -> None:
        # Open on the art we drew last time, not the text fallback (PT-42): a screen that
        # rebuilds itself on every action would otherwise flash the placeholder until
        # `on_mount` re-rendered, which reads as the art "resetting" each time you act.
        # Tier and theme are part of the key — they change the image, so remembering them
        # apart stops a panel opening on the wrong-sized render and then snapping.
        self._key = (kind, archetype_id, service, condition, icon, identity,
                     cinematic, theme)
        super().__init__(remembered(self._key) or _FALLBACK,
                         classes="station-icon" if icon else "station-banner")
        self._kind = kind
        self._archetype = archetype_id
        self._service = service
        self._condition = condition
        self._icon = icon
        self._identity = identity

    def on_mount(self) -> None:
        self.app.theme_changed_signal.subscribe(self, lambda _theme: self._refresh())
        self._refresh()

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh()

    def _refresh(self) -> None:
        cinematic = getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "wide"
        self._key = (self._kind, self._archetype, self._service, self._condition,
                     self._icon, self._identity, cinematic, str(self.app.theme))
        try:
            art: Text
            if self._icon:
                width, height = (36, 12) if cinematic else (24, 8)
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


class StationArtHeader(Horizontal):
    """Stardock-model header: station exterior at left, active-service scene at right."""

    DEFAULT_CSS = """
    StationArtHeader { height: 8; margin-bottom: 1; content-align: left top; }
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

    def __init__(self, kind: str, archetype_id: str, service: str, *,
                 identity: int, condition: str = "open") -> None:
        # Read the tier/theme here, at compose time, where the app is reachable, so each
        # panel opens on the art it last drew *at this size* (edge.tui.art_memory).
        from textual.app import active_app
        app = active_app.get(None)
        cinematic = getattr(getattr(app, "layout_tier", None), "value", "standard") == "wide"
        theme = str(getattr(app, "theme", ""))
        super().__init__(
            _StationArt(kind, archetype_id, service, condition,
                        icon=True, identity=identity, cinematic=cinematic, theme=theme),
            _StationArt(kind, archetype_id, service, condition,
                        icon=False, identity=identity, cinematic=cinematic, theme=theme),
        )

    def on_mount(self) -> None:
        tier = getattr(getattr(self.app, "layout_tier", None), "value", "standard")
        self.add_class(tier)

    def on_resize(self) -> None:
        for tier in ("compact", "standard", "wide"):
            self.remove_class(tier)
        self.add_class(getattr(getattr(self.app, "layout_tier", None), "value", "standard"))
