"""`edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).

Dev-tier, like `dialogue/authoring/`: never imported by a runtime layer. A bot programs
against the one `server.protocol.ServiceProtocol` seam (H16) — it submits ordinary commands
and reads ordinary DTOs, so it is **fog-honest by construction** (a bot can see no more than
the player it drives). `BotRunner` gives it the TWX trigger idiom (`on(EventType)`) plus a
per-turn driver; `edge-bot --script path.py --save game.db` runs a user script.

See `docs/SCRIPTING.md` for the API and the trust model (scripts are Python running with your
privileges — no sandbox).
"""

from edge.bot.runner import BotRunner

__all__ = ["BotRunner"]
