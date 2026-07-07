"""Example bot: an explorer that pushes into unexplored space, salvaging as it goes (WP60).

Demonstrates the trigger idiom (`@bot.on(DiscoveryDetected)`) and the turn driver. Each turn
it salvages anything collectable in the current sector, then warps toward an unexplored
neighbour (falling back to any warp), fleeing if it stumbles into a fight. Run with:

    edge-bot --script edge/bot/scripts/explorer.py --save /tmp/explore.db
"""

from __future__ import annotations

from edge.bot.runner import BotRunner
from edge.core.events import DiscoveryCollected, DiscoveryDetected
from edge.core.rules import CombatAction, Salvage, Warp


def setup(bot: BotRunner) -> None:
    @bot.on(DiscoveryDetected)
    def spotted(b: BotRunner, ev: DiscoveryDetected) -> None:
        b.log(f"detected {ev.kind} ({ev.rarity})")

    @bot.on(DiscoveryCollected)
    def logged(b: BotRunner, ev: DiscoveryCollected) -> None:
        b.log(f"logged {ev.kind} → codex")

    @bot.each_turn
    def roam(b: BotRunner) -> None:
        # Break off any fight first (an explorer runs, it doesn't brawl).
        if b.service.encounter_view(b.player_id) is not None:
            b.apply(CombatAction(action="flee"))
            return
        g = b.game()
        if g.turns < 1:
            b.stop()
            return
        for d in g.sector.discoveries:
            if d.salvageable:
                b.apply(Salvage(discovery_id=d.discovery_id))
        warps = g.sector.warps
        if not warps:
            b.stop()
            return
        target = next((w for w in warps if w.kind == "unexplored"), warps[0])
        if not b.apply(Warp(to_sector=target.sector_id)):
            b.stop()  # blocked (out of turns / engaged and couldn't flee) — done
