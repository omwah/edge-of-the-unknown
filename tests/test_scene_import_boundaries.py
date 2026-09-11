"""`edge/scene/` must stay a pure, downward-only layer (plan §3, §4.2, AGENTS.md).

It consumes fog-safe DTOs/config and an injected `ArtGeometryCatalog`, and
must never import `edge.art.sprites`, Rich, Textual, do file I/O, go async, or
reach into a TUI module, game RNG, or game-state mutation.
"""

from __future__ import annotations

import ast
from pathlib import Path

SCENE_ROOT = Path(__file__).parents[1] / "edge" / "scene"

FORBIDDEN_MODULE_PREFIXES = (
    "edge.art.sprites",
    "edge.art.sprite_art",
    "edge.tui",
    "rich",
    "textual",
    "edge.core.models",  # no direct game-state mutation; only DTO/config types
)

FORBIDDEN_STDLIB = ("asyncio",)

FORBIDDEN_IO_CALLS = {"open"}


def _iter_scene_modules() -> list[Path]:
    return sorted(SCENE_ROOT.rglob("*.py"))


def test_scene_package_exists_and_has_modules() -> None:
    modules = _iter_scene_modules()
    assert modules, "edge/scene/ must contain at least one module"


def test_no_forbidden_imports_in_edge_scene() -> None:
    violations: list[str] = []
    for path in _iter_scene_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name in FORBIDDEN_STDLIB or any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in FORBIDDEN_MODULE_PREFIXES
                ):
                    violations.append(f"{path.relative_to(SCENE_ROOT.parents[1])}: imports {name!r}")
    assert not violations, "\n".join(violations)


def test_no_file_io_or_random_module_use_in_edge_scene() -> None:
    violations: list[str] = []
    for path in _iter_scene_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("random", "pathlib", "os"):
                        violations.append(f"{path}: imports {alias.name!r}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_IO_CALLS:
                    violations.append(f"{path}: calls {node.func.id}()")
    assert not violations, "\n".join(violations)


def test_no_async_def_in_edge_scene() -> None:
    violations: list[str] = []
    for path in _iter_scene_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.AsyncWith, ast.AsyncFor)):
                violations.append(f"{path}: async construct {type(node).__name__}")
    assert not violations, "\n".join(violations)
