# CLAUDE.md — Project Helix

## What this project is

Project Helix is a clone of **TradeWars 2002** (the classic BBS door game of
space trading and galactic conquest) built in **Python 3.12+** with the
**Textual** TUI framework. The intent is an authentic TW2002 core loop —
warp-graph universe, port pair-trading in Fuel Ore / Organics / Equipment,
turns-per-day, planets, sector fighters, NPC raiders — delivered through a
modern terminal UI, with a codebase that is deterministic, testable, and
extensible to multiplayer later. Single-player first.

## Authoritative spec

**`docs/DESIGN.md` is the authoritative design document. Read it before any
architectural decision.** It was produced by analyzing the source code of
seven existing TradeWars clones and the original 1986 TradeWars II BASIC
source. Do not contradict it casually; if implementation reality forces a
deviation, update DESIGN.md in the same change and note the reason.

## Reference code (read-only)

`references/` contains shallow clones of the analyzed codebases (recreate
with `clone_references.sh` if absent). **Never modify these; they are for
reading only. Never copy code from them verbatim** — they are inspiration
and a source of constants/algorithms, and they carry assorted licenses
(GPL-era code among them). Reimplement ideas cleanly.

What each is for:
- `references/twclone` — architecture reference: server/engine process split,
  durable event log + cron-task scheduling, market-driven port economy
  (docs/GALACTIC_ECONOMY.md, docs/ENGINE.md), tunnel/FedSpace universe gen,
  full TW command catalog in docs/PROTOCOL.v3/.
- `references/terminal-space` — closest Python cousin: clean domain model,
  PortClass enum (8 buy/sell triples), port type distribution
  (20/20/20/10/10/10/5/5), stock-ratio pricing, `to_public(context)`
  fog-of-war DTO pattern, embedded-server single-player.
- `references/blacknovatraders` — tuned economy constants (config.php),
  linear pricing `base ± delta * stock/limit`, planet/colonist production
  math (sched_planets.php), combat baseline (attack.php).
- `references/tradewars/tw2bas/` — the original 1986 BASIC source +
  TWINSTR.DOC rulebook: turn costs, sector-fighter rules, retreat costs one
  fighter, Cabal NPCs, 500-sector scale. Authenticity reference.
- `references/SectorWars` — contains "TW Sector Algorithm.txt": the
  cluster-and-bridge universe generation algorithm we use.
- `references/ExchangeConflict2016` — networkx generation motifs (deadends,
  rings), uniview-style map inspector idea, config-driven ship data.
- `references/aatraders` — sysop/admin feature catalog only (Phase 5).

## Work completed so far

1. Researched and identified all notable open-source TW2002 clones.
2. Cloned and analyzed their source directly (architecture, economy
   formulas, universe-gen algorithms, original game rules).
3. Wrote `docs/DESIGN.md`: full design — layered architecture
   (core / bigbang / engine / store / server / tui), data model, big bang
   pipeline, economy formulas, turn/tick engine, combat, Textual UI design,
   persistence, testing strategy, 5-phase roadmap.

**No implementation code exists yet.** The next session starts Phase 1.

## Architecture rules (non-negotiable)

- Layered, downward-only dependencies: `helix/core` (pure rules, **no I/O,
  no async, no Textual imports**), `helix/bigbang` (generation, networkx),
  `helix/engine` (asyncio background ticks), `helix/store` (SQLite behind a
  repository interface), `helix/server` (command -> event service; fog of
  war enforced at the `to_public(context)` serialization boundary),
  `helix/tui` (Textual app only).
- All randomness flows through a seeded `random.Random` owned by game
  state. A game must be reproducible from `(seed, command log)`.
- Economy invariants enforced in core, always: no negative balances, goods
  are conserved by trades, every state mutation is transactional.
- Game constants (ship stats, prices, universe size) live in config files,
  not code.
- Single-player embeds the server in-process; never let the TUI reach
  around the service API into core state directly.

## Roadmap (from DESIGN.md §13)

- **Phase 1 (current):** core models, big bang (cluster+bridge+validate,
  FedSpace sectors 1-10, StarDock), movement with turn costs, port docking
  + trading with live pricing and haggling, SQLite persistence, Textual
  game screen (sector view, clickable warp list, status sidebar, port
  screen). Exit criterion: pair-trading loop is fun for 30 minutes.
- **Phase 2:** StarDock services, multiple ship types, planets with
  BNT-style production, Genesis torpedoes, Computer screen (pair-trade
  finder, route planner).
- **Phase 3:** sector fighters/mines, ship combat with salvage and escape
  pods, alignment/experience, FedSpace law, NPC raider faction + NPC
  traders.
- **Phase 4:** multiplayer (JSON-RPC over websockets), corporations.
- **Phase 5:** order-book economy, citadels, cloaking/probes, sysop
  console, scripting hooks.

## Conventions

- Python >= 3.12, `ruff` + `mypy --strict` on `core/` and `bigbang/`.
- Tests: pytest + hypothesis. Property tests for economy invariants;
  golden-master replays of command logs against fixed seeds; bigbang
  validation across many seeds; Textual Pilot for UI flows.
- Dependencies (Phase 1): textual, rich, networkx, pydantic v2; stdlib
  sqlite3. Add nothing else without updating DESIGN.md §14.
- Commit style: small, phase-tagged (e.g. `p1: bigbang cluster pass`).
