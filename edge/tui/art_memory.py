"""What an art panel drew last time, so a rebuilt screen doesn't blink (PT-42).

Several screens rebuild themselves after an action — a Stardock purchase pops the screen
and pushes a fresh one — and every art panel on them is therefore a *new* widget. Those
widgets start on a text fallback and swap in the real art from `on_mount`, so each action
made the art visibly reset: placeholder, then image, every time.

The expensive part (chafa) is already memoised in `edge.art.portrait`; what was missing is
the *frame*. Remembering the rendered `Text` per panel identity lets a rebuilt widget open
on the art it had a moment ago, so the swap is invisible. `on_mount` still re-renders, so a
theme or layout-tier change corrects itself on the next frame — this is a paint-time
smoother, never the source of truth.

Keyed by whatever identifies a panel to its host (kind, archetype, service, tab, …). A
copy goes in and a copy comes out: Rich `Text` is mutable and callers `stylize()` it.
"""

from __future__ import annotations

from rich.text import Text

# Bounded only by the handful of panels a session actually shows (a few dozen at most:
# one per station service per archetype), so no eviction policy is needed.
_LAST: dict[tuple[object, ...], Text] = {}


def remembered(key: tuple[object, ...]) -> Text | None:
    """The art this panel drew last time, or None if it has never been drawn."""
    text = _LAST.get(key)
    return text.copy() if text is not None else None


def remember(key: tuple[object, ...], art: Text) -> Text:
    """Record `art` as this panel's latest render and hand it back for painting."""
    _LAST[key] = art.copy()
    return art
