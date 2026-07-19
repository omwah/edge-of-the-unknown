"""Groundwar POC config — a thin adapter over the production schema (GW-WP02).

Balance no longer lives in a divergent loader here: it is the frozen Pydantic
`GroundwarConfig` validated by `edge.core.config` from the single YAML source of
truth (`config/groundwar_default.yaml`, merged into the default config as the
`groundwar:` block). This module only re-exports the production models under the
names the standalone app already imports, and loads that block through the
production config loader so the standalone and the live game read identical
numbers.
"""

from __future__ import annotations

from pathlib import Path

from edge.core.config import (
    GroundwarConfig as GroundwarConfig,
)
from edge.core.config import (
    GwEmplacement as EmplacementStats,
)
from edge.core.config import (
    GwSuit as SuitClass,
)
from edge.core.config import (
    GwWeapon as WeaponStats,
)

__all__ = ["EmplacementStats", "GroundwarConfig", "SuitClass", "WeaponStats", "load_config"]


def load_config(path: Path | None = None) -> GroundwarConfig:
    """The `groundwar:` block from the production config (default, or from `path`).

    Loads the full `GameConfig` — the same seam the live game uses — and returns
    its validated ground-operations block, so the standalone play-test app cannot
    drift from shipped balance. `path`, when given, is a full game config file.
    """
    from edge.config import load_config as load_full_config
    from edge.config import load_default_config

    config = load_full_config(path) if path is not None else load_default_config()
    if config.groundwar is None:
        raise ValueError("config has no `groundwar:` block")
    return config.groundwar
