"""`edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted game.

Local play (the save is created fresh from `--seed` when absent, exactly like `edge-bot`):

    edge-llm-bot --save pilot.db --model gemma4:e4b-128k --pace 6 --log-file pilot.log

Hosted play (an `edge-server` game over websocket JSON-RPC, docs/HOSTING.md): the pilot
logs in (registering the account when new), takes a seat, and plays through the wire —
the same fog-of-war seam as local play:

    edge-llm-bot --connect ws://localhost:8765 --user pilot --password s3cret [--game 1]

Requires a local Ollama server (`ollama serve`) with the chosen model pulled. `--pace`
scales the pilot to human speed: a cycle never finishes faster than that many seconds.
`--log-file` appends every action / reasoning / result / chat record as a timestamped line.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from edge.bot.llm.brain import Brain
from edge.bot.llm.ollama import OllamaChat
from edge.bot.llm.tui import LLMBotApp
from edge.bot.runner import BotRunner


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="edge-llm-bot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    where = parser.add_argument_group("game (local save or hosted server)")
    where.add_argument("--save", type=Path, help="local save DB (created if absent)")
    where.add_argument("--connect", metavar="WS_URL",
                       help="play a hosted game instead: edge-server websocket URL")
    where.add_argument("--user", help="account username (hosted play)")
    where.add_argument("--password", default=os.environ.get("EDGE_BOT_PASSWORD"),
                       help="account password (hosted play; default $EDGE_BOT_PASSWORD)")
    where.add_argument("--game", type=int, default=None,
                       help="hosted game id to join (default: first listed, or create one)")
    where.add_argument("--game-name", default="LLM pilot's game",
                       help="name for the game created when the server has none")
    where.add_argument("--seed", type=int, default=42, help="seed when creating a new game")
    where.add_argument("--player", type=int, default=1, help="player id to drive (local play)")
    pilot = parser.add_argument_group("pilot")
    pilot.add_argument("--model", default="gemma4:e4b-128k", help="Ollama model name")
    pilot.add_argument("--host", default=None,
                       help="Ollama server URL (default $OLLAMA_HOST or http://localhost:11434)")
    pilot.add_argument("--pace", type=float, default=6.0,
                       help="minimum seconds per action — human-speed scaling (default 6)")
    pilot.add_argument("--max-actions", type=int, default=0,
                       help="stop after this many actions (0 = unlimited)")
    pilot.add_argument("--log-file", type=Path, default=None,
                       help="append actions/reasoning/chat records to this file")
    args = parser.parse_args(argv)

    if bool(args.save) == bool(args.connect):
        parser.error("pick exactly one of --save (local) or --connect (hosted)")

    session = None
    if args.connect:
        if not args.user or not args.password:
            parser.error("hosted play needs --user and --password (or $EDGE_BOT_PASSWORD)")
        from edge.bot.llm.remote import RemoteSession  # lazy: needs `websockets`

        session = RemoteSession(args.connect)
        player_id = session.open(args.user, args.password, game_id=args.game,
                                 game_name=args.game_name, seed=args.seed)
        bot = BotRunner(session.service, player_id)
    else:
        from edge.bot.__main__ import open_service

        service = open_service(args.save, args.seed, cross_thread=True)
        bot = BotRunner(service, args.player)

    llm = OllamaChat(model=args.model, host=args.host)
    brain = Brain(bot, llm, pace=args.pace, max_actions=args.max_actions)
    try:
        LLMBotApp(brain, log_file=args.log_file).run()
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    main()
