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
from edge.core.dialogue import validate_dialogue

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


def load_config(path: Path | str) -> GameConfig:
    """Load and validate a YAML game config from `path`.

    A `roster_file:` pointer (relative to the config's directory) is resolved here —
    the species roster lives in its own file (`roster_default.yaml`, §6) so a game can
    be generated against a different source roster. The pointer is read at this I/O
    seam and the parsed roster injected as the `roster` field before validation; core
    never touches the filesystem.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    roster_file = data.pop("roster_file", None)
    if roster_file is not None and "roster" not in data:
        with open(path.parent / roster_file, encoding="utf-8") as fh:
            data["roster"] = yaml.safe_load(fh)
    names_file = data.pop("names_file", None)
    if names_file is not None and "names" not in data:
        with open(path.parent / names_file, encoding="utf-8") as fh:
            data["names"] = yaml.safe_load(fh)
    config = GameConfig.from_mapping(data)
    # Dialogue integrity (§13): only when the roster actually authors dialogue packs,
    # so a minimal/in-authoring roster still loads.
    if config.roster is not None and config.roster.personas:
        validate_dialogue(config.roster)
    return config


def load_default_config() -> GameConfig:
    """Load the bundled default config (`config/default.yaml`)."""
    return load_config(DEFAULT_CONFIG_PATH)
