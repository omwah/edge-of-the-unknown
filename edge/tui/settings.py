"""Local presentation preferences for the Textual client.

These settings are deliberately outside game config and universe state: changing
contrast or animation must never alter replay hashes or a hosted game.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
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


def settings_path():
    return save_dir() / "ui-settings.json"


def load_settings() -> tuple[UISettings, str | None]:
    path = settings_path()
    if not path.exists():
        return UISettings(), None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {field: raw[field] for field in asdict(UISettings()) if field in raw}
        return UISettings(**known), None
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return UISettings(), f"UI settings were reset: {exc}"


def save_settings(settings: UISettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
