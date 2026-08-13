"""Sync the runtime sprite-art package and assets from a designer checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "edge" / "art" / "sprite_art.manifest"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def tracked_files() -> list[Path]:
    paths = [
        *sorted((ROOT / "edge" / "art" / "sprite_art").rglob("*.py")),
        ROOT / "edge" / "art" / "assets" / "palettes.yaml",
        *(ROOT / "edge" / "art" / "assets" / "sprites").rglob("*.yaml"),
        ROOT / "tests" / "test_vendored_sprite_art.py",
        ROOT / "tests" / "fixtures" / "tier_renders.json",
    ]
    return [path for path in paths if path.is_file()]


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def designer_commit(source: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def sync(source: Path) -> None:
    package_source = source / "src" / "sprite_art"
    assets_source = source / "assets"
    if not (package_source / "__init__.py").is_file():
        raise SystemExit(f"not a sprite-art-designer checkout: {source}")

    package_target = ROOT / "edge" / "art" / "sprite_art"
    assets_target = ROOT / "edge" / "art" / "assets"
    shutil.rmtree(package_target, ignore_errors=True)
    shutil.rmtree(assets_target, ignore_errors=True)
    package_target.parent.mkdir(parents=True, exist_ok=True)
    assets_target.mkdir(parents=True)
    shutil.copytree(
        package_source,
        package_target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(assets_source / "palettes.yaml", assets_target / "palettes.yaml")
    shutil.copytree(assets_source / "sprites", assets_target / "sprites")

    test_text = (source / "tests" / "test_sprite_art.py").read_text()
    test_text = test_text.replace("from sprite_art import (", "from edge.art.sprite_art import (")
    test_text = test_text.replace(
        "from sprite_art.glyphs import (", "from edge.art.sprite_art.glyphs import ("
    )
    test_text = test_text.replace(
        "from sprite_art.io import", "from edge.art.sprite_art.io import"
    )
    test_text = test_text.replace(
        'ASSETS = ROOT / "assets"',
        '''ASSETS = ROOT / "edge" / "art" / "assets"


@pytest.fixture(scope="module")
def palettes() -> PaletteCatalog:
    return load_palette_catalog(ASSETS / "palettes.yaml")


@pytest.fixture(scope="module")
def sprites() -> dict[str, Sprite]:
    return load_sprite_directory(ASSETS / "sprites")
''',
    )
    (ROOT / "tests" / "test_vendored_sprite_art.py").write_text(test_text)
    fixture_target = ROOT / "tests" / "fixtures" / "tier_renders.json"
    fixture_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "tests" / "fixtures" / "tier_renders.json", fixture_target)
    write_manifest(designer_commit(source))


def write_manifest(commit: str) -> None:
    MANIFEST.write_text(json.dumps({
        "upstream_commit": commit,
        "synced": date.today().isoformat(),
        "files": {relative(path): sha256(path) for path in tracked_files()},
    }, indent=2) + "\n")


def check() -> None:
    if not MANIFEST.is_file():
        raise SystemExit(f"missing manifest: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text())
    expected: dict[str, str] = manifest["files"]
    actual = {relative(path): sha256(path) for path in tracked_files()}
    drift = sorted(
        path for path in set(expected) | set(actual)
        if expected.get(path) != actual.get(path)
    )
    if drift:
        for path in drift:
            print(path)
        raise SystemExit(1)


parser = argparse.ArgumentParser()
parser.add_argument("source", nargs="?", type=Path)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
if args.check:
    check()
elif args.source is not None:
    sync(args.source.resolve())
else:
    parser.error("provide a designer checkout or --check")
