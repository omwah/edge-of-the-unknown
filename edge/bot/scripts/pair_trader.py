"""Example bot: a pair-trader ping-ponging the best trade route (WP60).

The WP48 balance harness promoted to a script. It finds the Computer's top trade pair once,
then cycles buy-sector → sell-sector: fill holds with what the buy port sells, carry it to the
sell port, dump it, repeat — the §8 "trade → fund the first upgrade" loop, driven headlessly.
Used by the Phase-5 exit balance pass (income-per-day across seeds). Run with:

    edge-bot --script edge/bot/scripts/pair_trader.py --save /tmp/trade.db
"""

from __future__ import annotations

from edge.bot.runner import BotRunner
from edge.core.enums import Commodity
from edge.core.rules import CombatAction, Dock, Trade, TravelTo


def _commodity(label: str) -> Commodity:
    """Map a port DTO's display label ("Fuel Ore") back to its `Commodity` enum."""
    return Commodity(label.lower().replace(" ", "_"))

# Bot-local plan carried across turns (the script owns its own state, not the harness).
_PLAN: dict[str, int | str] = {}


def setup(bot: BotRunner) -> None:
    _PLAN.clear()

    @bot.each_turn
    def trade(b: BotRunner) -> None:
        if b.service.encounter_view(b.player_id) is not None:
            b.apply(CombatAction(action="flee"))
            return
        g = b.game()
        if g.turns < 5:
            b.stop()
            return
        if not _PLAN:
            pair = next((p for p in b.computer().pairs
                         if p.buy_sector >= 0 and p.sell_sector >= 0), None)
            if pair is None:
                b.stop()
                return
            _PLAN.update(buy=pair.buy_sector, sell=pair.sell_sector, leg="to_buy")

        here = g.sector.sector_id
        dest = int(_PLAN["buy"] if _PLAN["leg"] == "to_buy" else _PLAN["sell"])
        if here != dest:
            if not b.apply(TravelTo(to_sector=dest)):
                b.stop()
            return

        port = b.current_port()
        if port is None:
            b.apply(Dock())
            return
        if _PLAN["leg"] == "to_buy":
            # Fill holds with the commodity this port sells (bounded by latinum + holds).
            line = next((c for c in port.commodities if c.mode == "SELL"), None)
            if line is not None and line.price > 0:
                units = min(g.ship.holds_total, g.ship.latinum // line.price)
                if units > 0:
                    b.apply(Trade(commodity=_commodity(line.name), units=units))
            _PLAN["leg"] = "to_sell"
        else:
            for c in port.commodities:
                if c.mode == "BUY" and c.player_qty > 0:
                    b.apply(Trade(commodity=_commodity(c.name), units=c.player_qty))
            _PLAN["leg"] = "to_buy"
            b.log(f"cycle complete — latinum {b.game().ship.latinum:,}")
