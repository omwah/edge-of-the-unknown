"""`BotSwarm` — many bots against one authoritative game (DESIGN §14 — WP69).

The multiplayer QA driver: several `BotRunner`s share **one** `ServiceProtocol` (the
single-writer `GameService`, or a `GameServer` behind its queue), each bound to its own seat,
stepped **round-robin** so their commands interleave into one totally-ordered command log. That
total order is the whole correctness story: a swarm run *is* a command log, so
`rebuild(seed, log)` reproduces the live `state_hash` exactly (the H14/H18 determinism proof).

Dev-tier, like the rest of `edge.bot` (never imported by a runtime layer). The socket variant of
the same idea — bots driving `RemoteClient`s against a live `edge-server` — is one async loop
around this shape; the in-process swarm is what the fast regression suite asserts against.
"""

from __future__ import annotations

from collections.abc import Callable

from edge.bot.runner import BotRunner
from edge.server.protocol import ServiceProtocol

BotSetup = Callable[[BotRunner], None]


class BotSwarm:
    """Round-robin driver for N bots sharing one game (WP69)."""

    def __init__(self, service: ServiceProtocol) -> None:
        self._service = service
        self.bots: list[BotRunner] = []

    def add(self, player_id: int, setup: BotSetup) -> BotRunner:
        """Enrol a bot on `player_id` and let `setup` register its triggers + turn driver."""
        bot = BotRunner(self._service, player_id)
        setup(bot)
        self.bots.append(bot)
        return bot

    def run(self, rounds: int) -> int:
        """Step every bot once per round for `rounds` rounds (or until all have stopped).

        Round-robin so commands from different seats interleave — the realistic concurrent-load
        pattern, and the one whose total order the rebuild-hash check certifies deterministic.
        """
        completed = 0
        for _ in range(rounds):
            active = [b for b in self.bots if not b.stopped]
            if not active:
                break
            for bot in active:
                bot.step()
            completed += 1
        return completed
