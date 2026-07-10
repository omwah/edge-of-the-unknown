"""WP-UI05/WP-UI06 — responsive shell and unified action discovery.

Static collision/parity checks across every screen class (the footer, `.` menu,
`?` help, and Ctrl+P palette all derive from one binding-backed descriptor list,
so drift between them is a test failure), plus live checks that the below-minimum
size notice appears and clears and that focus survives a breakpoint change.
"""

from __future__ import annotations

import collections
import importlib
import inspect
import pkgutil
import re

from textual.binding import Binding
from textual.screen import ModalScreen, Screen

import edge.tui.screens as screens_pkg
from edge.tui.app import EdgeApp
from edge.tui.chrome import SizeNoticeScreen
from edge.tui.design import LayoutTier, layout_tier, screen_actions

# App-level reserved keys (EdgeApp.BINDINGS): a full screen may re-declare one
# only to surface the same action in its footer, never to repurpose the key.
_RESERVED = {"full_stop": "action_menu", "question_mark": "help", "ctrl+q": "quit"}


def _screen_classes() -> list[type[Screen]]:
    out: list[type[Screen]] = []
    for mod_info in pkgutil.iter_modules(screens_pkg.__path__):
        mod = importlib.import_module(f"edge.tui.screens.{mod_info.name}")
        for obj in vars(mod).values():
            if (inspect.isclass(obj) and issubclass(obj, Screen)
                    and obj.__module__ == mod.__name__):
                out.append(obj)
    assert out, "screen discovery found nothing — package layout changed?"
    return out


def _bindings(cls: type[Screen]) -> list[Binding]:
    return [b for b in cls.__dict__.get("BINDINGS", []) if isinstance(b, Binding)]


def test_layout_tier_breakpoints() -> None:
    assert layout_tier(79, 30) is LayoutTier.UNSUPPORTED
    assert layout_tier(100, 23) is LayoutTier.UNSUPPORTED
    assert layout_tier(80, 24) is LayoutTier.COMPACT
    assert layout_tier(99, 34) is LayoutTier.COMPACT
    assert layout_tier(100, 30) is LayoutTier.STANDARD
    assert layout_tier(119, 40) is LayoutTier.STANDARD
    assert layout_tier(120, 36) is LayoutTier.WIDE


def test_no_duplicate_keys_within_any_screen() -> None:
    for cls in _screen_classes():
        keys = [b.key for b in _bindings(cls)]
        dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
        assert not dupes, f"{cls.__name__} binds {dupes} more than once"


def test_reserved_global_keys_are_never_repurposed() -> None:
    for cls in _screen_classes():
        if issubclass(cls, ModalScreen):
            continue  # modals keep their own keys by design (app skips them)
        for binding in _bindings(cls):
            expected = _RESERVED.get(binding.key)
            if expected is not None:
                assert expected in binding.action, (
                    f"{cls.__name__} rebinds reserved key {binding.key!r} to "
                    f"{binding.action!r} — reserved keys may only re-surface the "
                    f"app action for footer display"
                )


def test_screen_actions_parity_with_footer_bindings() -> None:
    """`.` / `?` / Ctrl+P and the footer must advertise the same actions.

    The footer renders shown bindings; `screen_actions` derives its fallback
    from the same list, so parity holds by construction *unless* a screen grows
    an `action_descriptors` override. Any override must ship its own parity
    test proving descriptor keys match the screen's shown bindings.
    """
    for cls in _screen_classes():
        assert "action_descriptors" not in cls.__dict__, (
            f"{cls.__name__} overrides action_descriptors — add a screen-specific "
            f"parity test (descriptor keys == shown binding keys) and update this guard"
        )
        shown = [b for b in _bindings(cls) if b.show]
        fake = type("FakeHost", (), {"BINDINGS": shown})  # screen_actions reads the class
        derived = screen_actions(fake())  # type: ignore[arg-type]
        assert [d.key for d in derived] == [b.key for b in shown]
        assert all(d.title and d.help for d in derived)


def _method_source(cls: type, action: str) -> str:
    method = getattr(cls, f"action_{action}", None)
    try:
        return inspect.getsource(method) if method is not None else ""
    except (OSError, TypeError):
        return ""


def test_danger_map_actions_route_through_confirm_screen() -> None:
    """WP-UI06: destructive descriptors always reach the shared confirmation.

    Every `ACTION_DANGER` entry must name a bound action whose method pushes
    `ConfirmScreen` — directly or through one `self._helper()` level (the game
    screen's attack path). Static, so it holds for key, `.` menu, and palette
    entry points alike (they all invoke the same action method).
    """
    for cls in _screen_classes():
        danger = cls.__dict__.get("ACTION_DANGER", {})
        bound = {b.action for b in _bindings(cls)}
        for action, level in danger.items():
            assert level in ("caution", "destructive"), (
                f"{cls.__name__}.ACTION_DANGER[{action!r}] = {level!r}")
            assert action in bound, (
                f"{cls.__name__}.ACTION_DANGER names unbound action {action!r}")
            src = _method_source(cls, action)
            assert src, f"{cls.__name__} has no action_{action} method"
            if "ConfirmScreen" not in src:
                helpers = re.findall(r"self\.(_\w+)\(", src)
                assert any("ConfirmScreen" in inspect.getsource(getattr(cls, h))
                           for h in helpers if callable(getattr(cls, h, None))), (
                    f"{cls.__name__}.action_{action} is marked {level!r} but "
                    f"neither it nor its helpers reach ConfirmScreen")


def test_confirming_actions_declare_their_danger() -> None:
    """The inverse guard: a bound action that confirms must be in ACTION_DANGER."""
    for cls in _screen_classes():
        if issubclass(cls, ModalScreen):
            continue  # ConfirmScreen itself and other modals
        danger = cls.__dict__.get("ACTION_DANGER", {})
        for binding in _bindings(cls):
            if "ConfirmScreen(" in _method_source(cls, binding.action):
                assert binding.action in danger, (
                    f"{cls.__name__}.action_{binding.action} pushes ConfirmScreen "
                    f"but is missing from ACTION_DANGER — mark it caution or "
                    f"destructive so `.`/palette/help can badge it")


def test_screen_actions_carry_danger_metadata() -> None:
    fake = type("FakeHost", (), {
        "BINDINGS": [Binding("a", "assault", "Assault"), Binding("t", "trade", "Trade")],
        "ACTION_DANGER": {"assault": "destructive"},
    })
    derived = {d.action: d.danger for d in screen_actions(fake())}  # type: ignore[arg-type]
    assert derived == {"assault": "destructive", "trade": "none"}


async def test_size_notice_appears_below_minimum_and_clears() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.resize_terminal(70, 20)
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, SizeNoticeScreen)
        # Help must stay reachable from the notice (WP-UI05).
        await pilot.press("question_mark")
        await pilot.pause()
        from edge.tui.screens.help import HelpScreen
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, SizeNoticeScreen)
        # Growing back past the floor pops the notice without losing the menu.
        await pilot.resize_terminal(100, 34)
        await pilot.pause()
        await pilot.pause()
        assert not isinstance(app.screen, SizeNoticeScreen)
        assert app.screen.has_class("standard")


async def test_focus_survives_breakpoint_change() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        focused = app.focused
        assert focused is not None
        await pilot.resize_terminal(82, 26)  # standard -> compact
        await pilot.pause()
        await pilot.pause()
        assert app.screen.has_class("compact")
        assert app.focused is focused
