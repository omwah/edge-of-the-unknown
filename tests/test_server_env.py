"""Dedicated server operator secret loading without a dotenv dependency."""

from pathlib import Path

import pytest

from edge.server.env import dotenv_value, sysop_password
from edge.server.net import _parse_args


def test_sysop_password_precedence_is_cli_then_environment_then_local_dotenv(
        tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("EDGE_SYSOP_PASSWORD='file secret' # local operator config\n",
                      encoding="utf-8")

    assert sysop_password("cli-secret", environ={"EDGE_SYSOP_PASSWORD": "env-secret"},
                          dotenv_path=dotenv) == "cli-secret"
    assert sysop_password(environ={"EDGE_SYSOP_PASSWORD": "env-secret"},
                          dotenv_path=dotenv) == "env-secret"
    assert sysop_password(environ={}, dotenv_path=dotenv) == "file secret"


def test_dotenv_accepts_export_and_ignores_other_keys(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("OTHER=value\nexport EDGE_SYSOP_PASSWORD=operator-secret\n",
                      encoding="utf-8")

    assert dotenv_value("EDGE_SYSOP_PASSWORD", dotenv) == "operator-secret"


def test_default_dotenv_is_local_to_process_working_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("EDGE_SYSOP_PASSWORD=local-secret\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert sysop_password(environ={}) == "local-secret"


def test_server_defaults_to_user_edge_server_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("EDGE_SYSOP_PASSWORD", "operator-secret")

    args = _parse_args([])

    assert args.accounts == str(tmp_path / ".edge" / "server" / "accounts.db")
    assert args.games_dir == str(tmp_path / ".edge" / "server" / "games")


def test_server_accepts_explicit_dotenv_path(tmp_path: Path) -> None:
    dotenv = tmp_path / "server.env"
    dotenv.write_text("EDGE_SYSOP_PASSWORD=file-secret\n", encoding="utf-8")

    args = _parse_args(["--env-file", str(dotenv)])

    assert args.sysop_password == "file-secret"
