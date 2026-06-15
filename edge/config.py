"""Configuration loading (the I/O seam for the pure `edge.core.config` schema).

Reads a YAML config file from disk and validates it into a `GameConfig`. This
lives *outside* `edge.core` deliberately: `core` must do no I/O, so the file read
happens here and the parsed mapping is handed to `GameConfig.from_mapping`. The
big bang and the rules engine take a `GameConfig` object, never a path.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from edge.core.config import GameConfig

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


def load_config(path: Path | str) -> GameConfig:
    """Load and validate a YAML game config from `path`."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return GameConfig.from_mapping(data)


def load_default_config() -> GameConfig:
    """Load the bundled default config (`config/default.yaml`)."""
    return load_config(DEFAULT_CONFIG_PATH)
