"""Small stdlib-only environment loader for server operator settings.

Edge deliberately does not depend on python-dotenv. Operator secrets use the process
environment first and fall back to a `.env` file in the directory where the command runs.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from pathlib import Path

SYSOP_PASSWORD_ENV = "EDGE_SYSOP_PASSWORD"


def dotenv_value(key: str, path: Path | None = None) -> str | None:
    """Read one shell-like `KEY=value` from a local dotenv file without mutating `os.environ`."""
    source = path or Path.cwd() / ".env"
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        name, separator, value = line.partition("=")
        if not separator or name.strip() != key:
            continue
        lexer = shlex.shlex(value, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        return " ".join(lexer).strip()
    return None


def sysop_password(explicit: str | None = None, *,
                   environ: Mapping[str, str] | None = None,
                   dotenv_path: Path | None = None) -> str | None:
    """Resolve CLI → process environment → local `.env` sysop-secret precedence."""
    if explicit:
        return explicit
    environment = os.environ if environ is None else environ
    from_environment = environment.get(SYSOP_PASSWORD_ENV)
    if from_environment:
        return from_environment
    return dotenv_value(SYSOP_PASSWORD_ENV, dotenv_path)
