"""WP-D — the `edge` entry point: arg parsing and the --serve web host."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from edge.tui import app


def test_serve_hosts_the_plain_command() -> None:
    with patch("textual_serve.server.Server") as server:
        app._serve("0.0.0.0", 1234, plain=True)
    # The served subprocess runs the ordinary app (never --serve), so no recursion.
    assert server.call_args.args[0] == "python -m edge.tui --plain"
    assert server.call_args.kwargs == {"host": "0.0.0.0", "port": 1234}
    server.return_value.serve.assert_called_once()


def test_main_routes_serve_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["edge", "--serve", "--port", "9000"])
    with patch.object(app, "_serve") as serve:
        app.main()
    serve.assert_called_once_with("localhost", 9000, plain=False)
