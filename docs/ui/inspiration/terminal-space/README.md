# terminal-space — live captures

Text snapshots of [terminal-space](https://github.com/mrdon/terminal-space)
v0.2.0 (Apache-2.0), our closest Python/TUI cousin, captured for layout
reference. Grabbed by running the published package under `tmux` at 120×40 and
`tmux capture-pane` (it's a `prompt_toolkit` full-screen app, so these are text
snapshots — the right "screenshot" for a TUI):

```sh
python3 -m venv /tmp/tspace-venv && /tmp/tspace-venv/bin/pip install terminal-space
tmux new-session -d -s ts -x 120 -y 40 && tmux set -t ts status off
tmux send-keys -t ts '/tmp/tspace-venv/bin/python -m tspace.client_app' Enter
tmux capture-pane -t ts -p          # navigate with send-keys, capture each screen
```

(The local `references/terminal-space` checkout is newer and pins a `pjrpc`
version whose API has since changed — `AbstractAsyncClient.retried` is gone — so
the self-consistent **published 0.2.0** was used instead.)

## The captures

| File | Screen | What to steal → our screen |
|------|--------|----------------------------|
| [`01-main-menu.txt`](01-main-menu.txt) | Title + starfield + menu dialog | Animated starfield behind a centered modal menu (New Game / Join / Quit) → **MainMenu** |
| [`02-game-sector.txt`](02-game-sector.txt) | Primary game screen | `StatFrame` sidebar (Player / Holds / Ship, with weapon & countermeasure **lists**) + center sector/command region + right **Map** warp tree → **Game** |
| [`03-port-trade.txt`](03-port-trade.txt) | Docked port / commerce report | Docking menu, the `Status / Trading / % of max / OnBoard` trade table, and the `How many holds…[200]?` buy prompt → **PortScreen** |
| [`04-warp-planet-approach.txt`](04-warp-planet-approach.txt) | Warp transition (modal) | Accelerating starfield → block-shaded **planet-approach** animation in a "Warping to N" float → our warp flourish (§11) / **MainMenu** starfield |
| [`05-sector-explored.txt`](05-sector-explored.txt) | Arrived sector + grown Map tree | Right-hand **Map** widget as an *explored-universe tree* (`2 (SSB) → 1 (BBS) → …`) → **MapScreen / Computer** map |

## Observations

- **Sidebar-left, map-right.** Their layout is the inverse of our §11 (we put the
  sector view left, stats right). Worth A/B-ing in our skeleton — their left
  stack of three `Frame`s reads cleanly.
- **Stat lists render as `- item`.** Weapons/Countermeasures are multi-line stat
  values — this is the `StatFrame` list pattern we already mirror in
  `edge/tui/widgets.py:StatusSidebar`.
- **Sector as a command log, not widgets.** The center is a scrolling
  command/response transcript (`Command [TL=00:00:00]:[1] (?=Help)?`), very
  faithful to BBS TW2002. Our skeleton instead renders sector contents as
  structured widgets + a separate ticker — a deliberate modernization.
- **Commerce report columns** (`Status / Trading / % of max / OnBoard`) are a
  more TW-authentic framing than our `They / Stock / Price/u / You`; consider
  folding `% of max` and an `OnBoard` column into our PortScreen table.
- **Warp = a modal animation**, not an instant jump: a "Warping to N" float runs
  an accelerating starfield then a planet-approach reveal before the OK button
  enables. Nice touch for our own warp flourish.
- **The Map widget is an explored-universe tree**, rooted at the current sector
  and expanding as you travel — closer to our Computer/MapScreen tree than to a
  spatial map.
- **Unfinished / not reachable in 0.2.0** (so not captured): the three "bottom
  frame content" placeholders are stubs; the menu bar (File/Edit/View/Info) is
  placeholder (no map view); and `scene/battle.py` combat has no NPC ships wired
  into the local galaxy builder, so it can't be triggered in a fresh local game.
