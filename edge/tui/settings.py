"""Local presentation preferences for the Textual client.

These settings are deliberately outside game config and universe state: changing
contrast or animation must never alter replay hashes or a hosted game.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal

from edge.tui.saves import save_dir


@dataclass(frozen=True)
class UISettings:
    theme: str = "edge-ansi"
    reduced_motion: bool = False
    art_detail: Literal["full", "compact", "minimal"] = "full"
    density: Literal["comfortable", "compact"] = "comfortable"
    show_onboarding: bool = True
    show_disabled_options: bool = False
    # Captain's-objectives progress (WP-UI11) — purely local presentation
    # state, never part of universe state, replays, or hashes.
    objectives_done: tuple[str, ...] = ()
    # A lone remaining trooper has nothing left to choose once its actions run out —
    # ending the round for them is a convenience, not a rules change, so it is opt-in
    # local presentation state like everything else here, not a groundwar config knob.
    auto_end_turn_solo: bool = False


def settings_path() -> Path:
    return save_dir() / "ui-settings.json"


def load_settings() -> tuple[UISettings, str | None]:
    path = settings_path()
    if not path.exists():
        return UISettings(), None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {field: raw[field] for field in asdict(UISettings()) if field in raw}
        if "objectives_done" in known:  # JSON stores lists; the dataclass holds a tuple
            known["objectives_done"] = tuple(known["objectives_done"])
        return UISettings(**known), None
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return UISettings(), f"UI settings were reset: {exc}"


def save_settings(settings: UISettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
