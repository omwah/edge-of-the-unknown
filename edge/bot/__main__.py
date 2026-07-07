"""`edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (WP60).

Loads a user script (a Python file defining `setup(bot)`), attaches it to a `BotRunner`
driving one player of a game, and runs it headless. The game is opened from `--save` (created
fresh from `--seed` if the file does not exist), so a bot run is an ordinary, replayable
command log.

**Trust model:** a script is Python executed with your privileges — there is **no sandbox**.
Only run scripts you trust (see docs/SCRIPTING.md).
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType

from edge.bot.runner import BotRunner
from edge.config import load_default_config
from edge.server.service import GameService
from edge.store.repo import SqliteRepository


def load_script(path: Path) -> ModuleType:
    """Import a bot script by file path (it must define `setup(bot)`)."""
    spec = importlib.util.spec_from_file_location(f"edge_bot_script_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load script {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "setup"):
        raise ValueError(f"script {path} defines no setup(bot) function")
    return module


def open_service(save: Path, seed: int) -> GameService:
    """Open the save (loading an existing game, or creating a fresh one from `seed`)."""
    config = load_default_config()
    repo = SqliteRepository(save)
    if save.exists() and repo.load_meta() is not None:
        return GameService.load_game(config, repo)
    return GameService.new_game(config, seed, repo)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="edge-bot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", required=True, type=Path, help="a Python file with setup(bot)")
    parser.add_argument("--save", required=True, type=Path, help="save DB (created if absent)")
    parser.add_argument("--seed", type=int, default=42, help="seed when creating a new game")
    parser.add_argument("--turns", type=int, default=500, help="max turn-driver iterations")
    parser.add_argument("--player", type=int, default=1, help="player id to drive")
    args = parser.parse_args(argv)

    service = open_service(args.save, args.seed)
    bot = BotRunner(service, args.player)
    load_script(args.script).setup(bot)
    ran = bot.run(args.turns)
    print(f"ran {ran} turns; {len(bot.log_lines)} log lines")
    for line in bot.log_lines[-20:]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
