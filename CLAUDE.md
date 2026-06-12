# CLAUDE.md — Project Helix

## What this project is

Project Helix is a game of **space exploration and discovery** built on the
mechanical bones of **TradeWars 2002** (the classic BBS door game), in
**Python 3.12+** with the **Textual** TUI framework. The TW2002 foundation
is kept authentic — warp-graph universe, port pair-trading in Fuel Ore /
Organics / Equipment, turns-per-day, planets — but **trading is a means to
an end**: it funds the engines, shields, sensors, cloaks, and armaments
needed to push outward and discover things. Key pillars:

- **Discoveries** — planets (which can be descended onto for surface sites:
  ruins, artifacts, ancient tech, crashed ships), shipwrecks, nebulae,
  black holes, space entities. Rarity *and* technology-progression value
  increase with warp-hop distance from FedSpace (distance bands).
- **Races** — friendly races outnumber hostile; each has a tech level
  (travel speed + what aspect upgrades it can sell for **gold-pressed
  latinum**, the universal currency, or barter against artifacts). Hostile
  races have threat (damage) and interception (anti-flee) ratings; rarity
  scales inversely with threat; player escape chance is always ≥ a config
  floor (default 10%). FedSpace hosts only Federation-aligned friendly races.
- **Ship aspects** — cargo capacity, shields, engine speed, cloak/stealth,
  sensors, armaments; upgraded via trade profits and race tech.

Deterministic, testable, extensible to multiplayer later. Single-player
first.

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
4. Revised the design (v0.2, June 2026) to the exploration-first focus
   described above: races, discoveries, distance bands, latinum, ship
   aspects, encounter/flee rules (DESIGN.md §§7, 8, 11).

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

## Roadmap (from DESIGN.md §15)

- **Phase 1 (current):** core models, big bang (cluster+bridge+distance
  bands+validate, FedSpace sectors 1-10, StarDock), movement with turn
  costs, port docking + trading with live pricing and haggling in latinum,
  SQLite persistence, Textual game screen (sector view, clickable warp
  list, status sidebar, port screen). Exit criterion: pair-trading loop is
  fun for 30 minutes and funds a first ship upgrade.
- **Phase 2 (the pivot phase):** discovery system with distance-banded
  rarity, planet descent + surface sites, sensor detection, discovery
  codex, friendly races with tech barter/latinum sales of aspect upgrades,
  StarDock services, multiple ship types, planets with BNT-style
  production, Genesis torpedoes, Computer screen (pair-trade finder, route
  planner).
- **Phase 3:** hostile races (threat/interception, rarity inverse to
  threat, escape-chance floor), encounter system, ship combat with salvage
  and escape pods, sector fighters/mines, alignment/experience, FedSpace
  law, friendly NPC traders, hostile homeworld raids.
- **Phase 4:** multiplayer (JSON-RPC over websockets), corporations.
- **Phase 5:** order-book economy, citadels, probes, richer race
  interactions, sysop console, scripting hooks.

## Conventions

- Python >= 3.12, `ruff` + `mypy --strict` on `core/` and `bigbang/`.
- Tests: pytest + hypothesis. Property tests for economy invariants;
  golden-master replays of command logs against fixed seeds; bigbang
  validation across many seeds; Textual Pilot for UI flows.
- Dependencies (Phase 1): textual, rich, networkx, pydantic v2; stdlib
  sqlite3. Add nothing else without updating DESIGN.md §16.
- Commit style: small, phase-tagged (e.g. `p1: bigbang cluster pass`).
