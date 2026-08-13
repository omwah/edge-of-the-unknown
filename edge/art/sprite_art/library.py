"""Convenient loaded-library facade for game integration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rich.text import Text

from .io import load_palette_catalog, load_sprite_directory
from .model import PaletteCatalog, Sprite
from .render import render_sprite

DEFAULT_FALLBACK_ROLES: dict[str, str] = {
    "ship": "fighter",
    "port": "trading_port",
}
"""The sprite each kind falls back to for an unrecognized subtype.

These match Edge's own fallbacks: ``ship.SHIP_GRAMMAR`` defaults to ``fighter``
and ``port.PORT_GRAMMAR`` to ``trading_port``. A kind absent from the loaded
tree is simply not registered, so an assets directory holding only one kind
still builds a library."""


class SpriteLibrary:
    """Load an asset tree once and render cached sprites by kind and subtype."""

    def __init__(
        self,
        sprites: dict[str, Sprite],
        palettes: PaletteCatalog,
        *,
        fallback_roles: dict[str, str] | None = None,
    ) -> None:
        requested = (
            DEFAULT_FALLBACK_ROLES if fallback_roles is None else fallback_roles
        )
        kinds = {sprite.kind for sprite in sprites.values()}
        resolved: dict[str, str] = {}
        for kind, role in requested.items():
            if fallback_roles is not None and role not in sprites:
                raise ValueError(f"fallback role {role!r} for {kind!r} is not loaded")
            # Silently skip a default for a kind this tree does not carry, so a
            # ports-only or ships-only tree still constructs.
            if kind in kinds and role in sprites:
                resolved[kind] = role
        self.sprites = sprites
        self.palettes = palettes
        self.fallback_roles = resolved
        self._render_cache = lru_cache(maxsize=128)(self._render)

    @classmethod
    def from_assets(cls, asset_root: str | Path) -> SpriteLibrary:
        root = Path(asset_root)
        return cls(
            load_sprite_directory(root / "sprites"),
            load_palette_catalog(root / "palettes.yaml"),
        )

    def available_subtypes(self, kind: str | None = None) -> tuple[str, ...]:
        """Return the loaded sprite ids, optionally limited to one kind.

        Edge enumerates subtypes per entity type, so a ship role list must not
        pick up stations and vice versa."""

        return tuple(
            sorted(
                sprite_id
                for sprite_id, sprite in self.sprites.items()
                if kind is None or sprite.kind == kind
            )
        )

    @property
    def available_roles(self) -> tuple[str, ...]:
        """Deprecated alias for the ship subtypes."""

        return self.available_subtypes("ship")

    def _resolve(self, kind: str, subtype: str) -> Sprite:
        sprite = self.sprites.get(subtype.lower())
        if sprite is not None and sprite.kind == kind:
            return sprite
        fallback = self.fallback_roles.get(kind)
        if fallback is None:
            raise KeyError(f"no {kind!r} sprite named {subtype!r} and no fallback")
        return self.sprites[fallback]

    def _render(
        self,
        kind: str,
        subtype: str,
        seed: int,
        width: int,
        height: int,
        archetype_id: str | None,
        facing: str | None,
    ) -> Text:
        sprite = self._resolve(kind, subtype)
        normalized_facing = facing.lower() if facing else None
        view_id = (
            "vertical"
            if normalized_facing in {"up", "down"} and "vertical" in sprite.views
            else "horizontal"
            if "horizontal" in sprite.views
            else next(iter(sprite.views))
        )
        view = sprite.views[view_id]
        if normalized_facing not in {view.canonical_facing, view.mirror_facing}:
            normalized_facing = view.canonical_facing
        return render_sprite(
            sprite,
            self.palettes,
            width=width,
            height=height,
            seed=seed,
            archetype_id=archetype_id or self.palettes.fallback_archetype,
            view_id=view_id,
            facing=normalized_facing,
        )

    def generate_sprite(
        self,
        kind: str,
        subtype: str,
        seed: int,
        width: int,
        height: int,
        archetype_id: str | None = None,
        facing: str | None = None,
    ) -> Text:
        """Render one cached sprite, matching Edge's generator arguments.

        ``kind`` and ``subtype`` must equal Edge's ``entity_type`` and
        ``subtype``, because the deterministic seed is built from the sprite's
        ``kind`` and ``role``."""

        return self._render_cache(
            kind, subtype, seed, width, height, archetype_id, facing
        )

    def generate_ship(
        self,
        subtype: str,
        seed: int,
        width: int,
        height: int,
        archetype_id: str | None = None,
        facing: str = "right",
    ) -> Text:
        """Edge-compatible ship renderer, extended to left/right/up/down."""

        return self.generate_sprite(
            "ship", subtype, seed, width, height, archetype_id, facing
        )

    def generate_port(
        self,
        subtype: str,
        seed: int,
        width: int,
        height: int,
        archetype_id: str | None = None,
    ) -> Text:
        """Edge-compatible station renderer for ports, starbases, and stardocks.

        Stations are vertical-only and have no mirror facing, so unlike ships
        they take no ``facing``."""

        return self.generate_sprite(
            "port", subtype, seed, width, height, archetype_id, None
        )

    def clear_cache(self) -> None:
        self._render_cache.cache_clear()
