# Scripting bots for Edge of the Unknown (DESIGN §14, WP60)

`edge-bot` runs a **bot script** — a Python file that drives one player of a game headlessly.
Bots are the TWX-style scripting hooks of DESIGN §14, and the bot-driven QA harness Phase 4
leans on: because a bot acts only through ordinary commands, a bot run **is** a command log
that replays to the identical `state_hash` like any human session (the WP12 rail).

## The one seam

Everything a bot touches goes through `edge.server.protocol.ServiceProtocol` (H16): the single
`apply(player_id, command)` mutator plus the read-only `*_view` projections. A bot therefore
sees **no more than the player it drives** — fog of war is honest by construction. The same
seam the TUI, the sysop console, and (Phase 4) the network client program against.

## Writing a script

A script defines one function, `setup(bot)`, and registers behaviour on the `BotRunner`:

```python
from edge.core.events import DiscoveryDetected
from edge.core.rules import Warp, Salvage

def setup(bot):
    @bot.on(DiscoveryDetected)              # a TWX trigger: fired per matching event
    def spotted(b, ev):
        b.log(f"found {ev.kind}")

    @bot.each_turn                          # the loop body, run each iteration
    def roam(b):
        g = b.game()                        # an ordinary fog-of-war projection
        if g.turns < 1:
            b.stop(); return
        warp = g.sector.warps[0]
        b.apply(Warp(to_sector=warp.sector_id))   # an ordinary command
```

### `BotRunner` API

- `bot.on(EventType)` — decorator; registers a trigger fired for each such event a command
  produces (the TWX idiom).
- `bot.each_turn` — decorator; registers the per-iteration driver (the main loop body).
- `bot.apply(command)` — submit a command; returns its events (and dispatches them to
  triggers). **Rules rejections are swallowed** — an unaffordable trade or a blocked warp
  returns `()` and stashes the reason on `bot.last_error`, so a heuristic bot never crashes on
  a normal rejection.
- `bot.game()`, `bot.computer()`, `bot.current_port()`, `bot.stardock()` — ordinary projections.
- `bot.service` — the raw `ServiceProtocol` for any other `*_view` (e.g.
  `bot.service.encounter_view(bot.player_id)`).
- `bot.stop()` — end the run early; `bot.log(line)` — record a line (printed at the end).

## Running

```
edge-bot --script edge/bot/scripts/pair_trader.py --save /tmp/trade.db --seed 42 --turns 500
```

If `--save` does not exist it is created fresh from `--seed`; otherwise the existing game is
loaded and continued. `--player` selects the player id to drive (default 1).

Two example scripts ship in `edge/bot/scripts/`:

- **`pair_trader.py`** — finds the Computer's best trade pair and ping-pongs it, the §8
  "trade → fund the first upgrade" loop. This is the Phase-5 exit balance harness.
- **`explorer.py`** — pushes into unexplored space, salvaging finds and fleeing fights.

## Trust model

**There is no sandbox.** A bot script is ordinary Python executed with your privileges — it can
read and write files, open sockets, and do anything you can. Only run scripts you trust, exactly
as you would any program. The harness confines a bot to *game* actions (the `ServiceProtocol`
seam), but it does **not** confine the Python the script itself runs.
