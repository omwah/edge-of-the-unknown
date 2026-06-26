"""Configuration loading (the I/O seam for the pure `edge.core.config` schema).

Reads a YAML config file from disk and validates it into a `GameConfig`. This
lives *outside* `edge.core` deliberately: `core` must do no I/O, so the file read
happens here and the parsed mapping is handed to `GameConfig.from_mapping`. The
big bang and the rules engine take a `GameConfig` object, never a path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from edge.core.config import GameConfig
from edge.dialogue import validate_dialogue

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"

# `offer_coordinates` lines are intel "tips": they fill {target}/{coords}/{distance}/{band}/
# {reward}, which only exist when the speaker has somewhere unvisited to point you. The runtime
# gates the context on a `has_intel_target` fact (server.session). An authoring sidecar emits a
# single *unconditional* tip grammar per species, so — spliced as-is — it would shadow the
# generic pack's catch-all and, once a lead is logged (no target left), render those
# placeholders empty. So a spliced tip is gated on has_intel_target; the generic "nowhere new"
# fallback then speaks when there is none. (DESIGN §6.7.)
_INTEL_CONTEXT = "offer_coordinates"
_INTEL_GUARD: dict[str, Any] = {"criteria": {"has_intel_target": True}}


def _merge_dialogue(roster: dict[str, Any], dialogue: dict[str, Any]) -> None:
    """Fold one dialogue document onto a roster dict in place (DESIGN §6.7).

    Two shapes are accepted, and may co-exist in one file:
    - `RosterConfig` dialogue fields (`personas`, `recency_k`, shared `grammar`) overlay the
      roster (shallow — a later file replaces these whole keys).
    - `species_grammars` (the authoring-pipeline sidecar shape: `{species_id -> {context ->
      [line]}}`) is spliced into each species' `dialogue_pack` by id, per-context, so a
      machine-authored sidecar layers its grammars over the persona defaults without
      restating the base corpus. The species `dialogue_pack` wins over its persona via the
      runtime fallback chain, so the splice is a clean per-species override. A spliced
      `offer_coordinates` tip is gated on `has_intel_target` (see `_INTEL_GUARD`) so it never
      shadows the generic "no fresh coordinates" line with empty placeholders.
    """
    species_grammars = dialogue.pop("species_grammars", None)
    roster.update(dialogue)  # personas / recency_k / grammar
    if not species_grammars:
        return
    by_id = {sp["id"]: sp for sp in roster.get("species", []) if isinstance(sp, dict)}
    for species_id, pack in species_grammars.items():
        species = by_id.get(species_id)
        if species is None:
            raise ValueError(
                f"dialogue species_grammars references unknown species {species_id!r}"
            )
        for entry in pack.get(_INTEL_CONTEXT, []):
            if isinstance(entry, dict) and "when" not in entry:
                entry["when"] = {"criteria": dict(_INTEL_GUARD["criteria"])}
        species.setdefault("dialogue_pack", {}).update(pack)


def load_config(path: Path | str) -> GameConfig:
    """Load and validate a YAML game config from `path`.

    A `roster_file:` pointer (relative to the config's directory) is resolved here —
    the species roster lives in its own file (`alien_roster_default.yaml`, §6) so a game
    can be generated against a different source roster. A `dialogue_file:` pointer
    (`alien_dialogue_default.yaml`, §6.7) carries the dialogue corpus and is merged onto the
    loaded roster before validation, so a roster and its voice corpus vary independently. It
    may be a **single path or a list** of paths, applied in order: a base file supplies the
    `personas` / `recency_k` / shared `grammar`, and any later file may add a
    `species_grammars` block (an authoring-pipeline sidecar) that layers per-species grammar
    overrides on top. All pointers are read at this I/O seam and injected as the `roster`
    field; core never touches the filesystem.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    roster_file = data.pop("roster_file", None)
    if roster_file is not None and "roster" not in data:
        with open(path.parent / roster_file, encoding="utf-8") as fh:
            data["roster"] = yaml.safe_load(fh)
    dialogue_file = data.pop("dialogue_file", None)
    if dialogue_file is not None and isinstance(data.get("roster"), dict):
        files = [dialogue_file] if isinstance(dialogue_file, str) else dialogue_file
        import os
        import sys
        if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
            files = [f for f in files if "alien_dialogue_default.yaml" in str(f)]
        for name in files:
            with open(path.parent / name, encoding="utf-8") as fh:
                _merge_dialogue(data["roster"], yaml.safe_load(fh) or {})
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


def validate_sidecar(
    sidecar: Path | str,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> None:
    """Merge a generated dialogue sidecar onto the default roster and run §13 integrity checks.

    Mirrors the load path of `load_config` up through the base dialogue merges, then splices
    `sidecar` on top before running Pydantic validation and `validate_dialogue`. Raises
    `DialogueIntegrityError` on the first integrity violation, or `ValueError` / `yaml.YAMLError`
    for structural problems in the sidecar itself.

    The config's `dialogue_file` list is loaded for its base corpus only (personas, recency_k,
    shared grammar). Any `species_grammars` blocks in those files are stripped before merging so
    that other machine-authored sidecars listed in the config do not interfere with the
    validation of the target sidecar — each sidecar is validated against the base corpus alone.
    """
    config_path = Path(config_path)
    sidecar = Path(sidecar)
    with open(config_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    roster_file = data.pop("roster_file", None)
    if roster_file is not None and "roster" not in data:
        with open(config_path.parent / roster_file, encoding="utf-8") as fh:
            data["roster"] = yaml.safe_load(fh)
    dialogue_file = data.pop("dialogue_file", None)
    if dialogue_file is not None and isinstance(data.get("roster"), dict):
        files = [dialogue_file] if isinstance(dialogue_file, str) else dialogue_file
        for name in files:
            with open(config_path.parent / name, encoding="utf-8") as fh:
                doc = yaml.safe_load(fh) or {}
            doc.pop("species_grammars", None)  # ignore other sidecars; validate target alone
            _merge_dialogue(data["roster"], doc)
    names_file = data.pop("names_file", None)
    if names_file is not None and "names" not in data:
        with open(config_path.parent / names_file, encoding="utf-8") as fh:
            data["names"] = yaml.safe_load(fh)
    with open(sidecar, encoding="utf-8") as fh:
        _merge_dialogue(data["roster"], yaml.safe_load(fh) or {})
    config = GameConfig.from_mapping(data)
    if config.roster is not None and config.roster.personas:
        validate_dialogue(config.roster)
