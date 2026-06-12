# Project Helix — Design Document
## A TradeWars 2002 Clone in Python + Textual

*Version 0.1 — June 2026*

---

## 1. Purpose and Scope

Project Helix is a faithful-in-spirit recreation of TradeWars 2002 (TW2002), the classic BBS door game of space trading and galactic conquest, built as a modern terminal application using Python 3.12+ and the Textual TUI framework. The goal is to capture the core TW2002 loop — explore a warp-connected universe, run trade routes between ports, build wealth, upgrade your ship, claim planets, and fight for territory — while delivering it through a polished, mouse-and-keyboard-friendly terminal interface and a codebase that is testable, deterministic, and extensible to multiplayer.

This document is informed by direct source analysis of seven existing TradeWars clones and the original 1986 TradeWars II BASIC source. Section 2 summarizes what each codebase taught us; the remainder of the document specifies our design.

---

## 2. Source Analysis: What We Learned From Each Clone

All repositories were cloned and read directly. Findings below reference actual code, not READMEs.

### 2.1 twclone (rdearman/twclone) — C, PostgreSQL, JSON protocol

The most architecturally mature clone, and our primary structural reference. Key findings from `src/`, `docs/ENGINE.md`, `docs/GALACTIC_ECONOMY.md`, and `docs/PROTOCOL.v3/`:

**Process separation.** twclone splits into a player-facing *server* (sessions, command validation, fast reads, event emission) and a forked *engine* process (clocks, cron jobs, economy ticks, NPC stepping, FedSpace enforcement). The database is the source of truth; a TCP server-to-server channel exists only to reduce latency. The engine runs a short tick loop (250–1000 ms) consuming events in ID order, plus durable cron tasks such as `daily_turn_reset` scheduled at `daily@03:00Z`. This event-rail + cron-task model is directly portable to a Python asyncio design.

**Market-driven economy.** Rather than static stock drift, each port has `max_capacity = size * 1000` and a `desired_stock` ratio (90% for StarDock, 50% for standard ports). An hourly economy tick generates BUY orders for shortages and SELL orders for surpluses; a daily settlement matches orders where `buyer_price >= seller_price` and physically moves goods and credits between ports. Ferengi NPCs do not use the order book — they roam, compare local prices, and execute instant trades against port inventory exactly like players, with persistent cargo and bank balances. NPC factions are modeled as ordinary corporations ("Ferengi Alliance", tag FENG) with corporate bank accounts.

**Economy invariants** stated explicitly in their docs and enforced atomically: no negative bank balances, conservation of goods (trade only moves goods, production/consumption is separate planet logic), and all trades inside transactions to prevent duping. We adopt all three.

**Universe topology.** `bigbang_pg_main.c` generates sectors, reserves sectors 1–10 as protected FedSpace, generates a StarDock, and then adds *tunnels* — isolated chains of 4+ sectors (default: minimum 15 tunnels of minimum length 4, randomized up to +5) grafted onto the main graph, with NPC homeworlds placed at tunnel endpoints, followed by an `ensure_fedspace_exit` pass. Tunnels are the classic TW2002 strategic terrain (one way in, defensible).

**Scaling lesson.** twclone began on SQLite and migrated to PostgreSQL because SQLite's single-writer model bottlenecked at high concurrent player counts. For our single-host scope, SQLite is fine — but we isolate persistence behind a repository interface so the same migration is possible without touching game logic.

**Protocol catalog.** Their PROTOCOL.v3 docs enumerate the full command surface of a complete TW game: ship, player, sector/movement, trade/port, combat/weapons, planets/citadels, corporations/stock market, banking/ledger, NPC/Ferengi AI, tavern/noticeboard, and sysop commands. We use this catalog as our feature checklist and phase planning input.

### 2.2 terminal-space (mrdon/terminal-space) — Python, the closest cousin

A ~3,900-line Python implementation of TW2002 basics with a client/server split. This is our primary *code-level* reference because its domain model is clean, idiomatic Python:

**Domain model.** Plain classes `Galaxy`, `Sector`, `Port`, `TradingCommodity`, `Planet`, `Player`, `Ship`, `Battle`, `DroneStack`, with `to_public()` projection methods that convert internal state to client-safe Pydantic DTOs filtered through a `SessionContext`. This internal-model/public-DTO split is a pattern we adopt wholesale — it keeps fog-of-war (what the player has actually seen) enforced at the serialization boundary.

**Port classes as an enum.** The eight TW2002 port types are encoded as an enum of buy/sell triples over (Fuel Ore, Organics, Equipment): BBS=1, BSB=2, SBB=3, SSB=4, SBS=5, BSS=6, SSS=7, BBB=8. Port type distribution in their builder: types 1–3 at 20% each, types 4–6 at 10% each, type 7 at 5%, type 8 at 5%. Initial stock per commodity: `randint(200, 2000)`.

**Pricing formula.** Base costs per unit: fuel ore sells at 1 / buys at 1.5; organics 2 / 3; equipment 4 / 6. Live price scales linearly with stock ratio: when a port is *buying*, `price = buy_offer + (amount/capacity) * buy_offer / 2`; when *selling*, `price = sell_cost - (amount/capacity) * sell_cost / 2`. So a port pays more as its buying stock fills and charges less as its selling stock fills — simple, but it produces the right player incentive gradient. We extend this with BlackNova's parameterization (2.3).

**Universe shape.** Hex-grid generation (`gen_hex_center(diameter)`) followed by `remove_warps(graph, warp_density, rnd)` to thin the lattice, using networkx. Coordinates map to sector IDs with sector 1 at origin. Ports placed by density roll; planets via `gauss(4.5, 1.5)` count in ~half the sectors. The hex-grid look is a deliberate aesthetic departure from TW2002's abstract graph; we instead follow the cluster-graph approach (2.5, 2.6) for authenticity, but keep networkx as the generation/validation substrate.

**Client architecture.** Full-screen prompt-toolkit app at 15 FPS with a scene stack (title scene, terminal scene, battle scene), an `InstantCmd` single-keystroke command dispatcher, a TW2002 color theme module, and visual flourishes via `terminaltexteffects` (starfields, animated transitions). Notably it does *not* use Textual — confirming our framework choice gives us widgets (DataTable, Tree, Input, tabs, CSS layout, `textual serve` web hosting) that terminal-space had to hand-build.

**RPC layer.** Client and server share Pydantic models in `tspace/common/` and communicate via JSON-RPC (pjrpc) over aiohttp, with the server embeddable in-process for single-player ("local mode" just instantiates `Server` directly). This embedded-server pattern is exactly how we will do single-player while keeping multiplayer reachable.

### 2.3 BlackNova Traders (cheevauva/blacknovatraders mirror) — PHP/SQL web clone

A long-lived web clone whose economy constants were tuned by years of live games. From `config.php` and `port.php`:

**Parameterized linear pricing.** Each commodity has `base_price`, `delta`, and `limit`: ore (11, 5), organics (5, 2), goods (15, 7), energy (3, 1). Port price = `base ± delta * (port_stock / limit) * inventory_factor`, minus when the port sells (stock depresses price), plus when it buys. This is the same shape as terminal-space's formula but with independently tunable elasticity per commodity — we adopt this parameterization.

**Planet production system.** From `sched_planets.php`: colonists produce per tick as `min(colonists, colonist_limit) * colonist_production_rate (0.005)` allocated across ore/organics/goods/energy/fighters/torpedoes by player-set percentage sliders, with organics consumption (0.05/colonist-tick) and starvation death rate (0.01) when food runs out, colonist reproduction at 0.0005, and credit interest at 1.0005 per tick compounded. This gives us a complete, proven planetary economy spec.

**Equipment price list** (useful baselines): fighters 50, torpedoes 25, armor 5, colonists 5, beacons 100, Genesis torpedo 1,000,000, warp editor 100,000, mine deflector 10, escape pod 100,000, fuel scoop 100,000.

**Combat.** `attack.php` resolves attacks with percentile rolls plus device checks (emergency warp device triggers on a failed roll and teleports the defender to a random sector) and 10–20% salvage of a destroyed ship's cargo. Simple, swingy, fun — a good Phase-3 baseline before TW2002's more elaborate odds tables.

### 2.4 Alien Assault Traders (tarnus/aatraders) — PHP, BNT/NGS fork

A 75 MB fork of BlackNova with heavy feature accretion: admin tooling (port price re-seeding, universe editors, IP bans, player/planet reports), team systems, shoutboxes, 3D galaxy map imaging. The main lesson is curatorial: AAT shows what twenty years of feature creep on the BNT economy looks like. We mine it for admin/sysop feature ideas (the `admin/` directory is effectively a sysop-tooling catalog) but treat its gameplay code as redundant with BNT.

### 2.5 SectorWars (leonard4/SectorWars) — C++, early-stage

Rudimentary, but it preserves a valuable artifact: `TW Sector Algorithm.txt`, a community description of how TW2002-style universes are believed to be generated. Summarized: allocate ~1000 sectors; repeatedly pick groups of 5–25 unassigned sectors and randomly interlink within each group (bidirectionally); name each group as a region/nebula (40–200 groups); then connect each group to 1–5 other groups with random inter-group warps; finally run pathfinding from a fixed origin to verify full reachability. This cluster-then-bridge algorithm produces the authentic TW2002 feel — local neighborhoods, sparse bridges, natural chokepoints — and is the core of our big bang (Section 6).

### 2.6 ExchangeConflict2016 (jzmiller1) — Python, universe-gen experiments

A Python sandbox focused on generation. Its `bigbang.py` builds a networkx graph with explicit *deadends* (2-sector stubs), *rings* (cycles of size drawn from a weighted choice of {3,5,7,9}), and a connectivity pass that attaches every remaining sector to the connected component — a menu of graph motifs we reuse. It enforces sanity constraints (minimum 20 systems; deadends capped relative to universe size). It also demonstrates per-sector procedural star systems (via StarGen) and a `uniview.py` map debugger that renders the universe with networkx-viewer, coloring port sectors green and empty sectors red — we will build the same kind of dev-mode map inspector with Textual or matplotlib. Its `data/ships.json` shows config-driven ship definitions (holds min/max, shield max, hull cost), which we generalize.

### 2.7 drbeco/tradewars — C clone + original 1986 TradeWars II BASIC source

The `tw2bas/` directory contains Chris Sherrick's original TW2 (RBBS QuixPlus lineage): `TW2.BAS`, `TW2SUB.BAS`, `TWVAR.BAS`, data files, and `TWINSTR.DOC`. The instructions document is primary-source material on the original rules: limited turns per day where each warp move or port landing costs one turn; sector fighters that must be fought (or retreated from at the cost of one fighter) before acting in a sector; trading in three commodities; buying fighters and cargo holds with profits; defending ports and sector chains for exclusive trading; the Cabal NPC menace dwelling in a region of space, with a 100-point bounty per Cabal fighter destroyed and 100,000 points for defeating them. The 500-sector universe (`S(500,1)` in TWVAR.BAS, TWMAP500 tooling) confirms the classic scale. The Cabal is the design ancestor of TW2002's Ferengi; our NPC faction follows the same role — a hostile NPC empire occupying defensible territory that strong players can raid.

### 2.8 Cross-cutting conclusions

Three independent codebases (twclone, terminal-space, ExchangeConflict) converge on the same generation stack — seeded RNG, graph library, validation pass — and two converge on the same pricing shape (linear in stock ratio). The two most complete games (twclone, terminal-space) both separate a pure rules core from transport and UI, and both treat single-player as an embedded server. Where they differ (hex grid vs. cluster graph; order-book economy vs. simple regen), we choose the option closer to TW2002 authenticity for defaults and keep the alternative reachable via configuration.

---

## 3. Design Goals and Non-Goals

**Goals.** Authentic TW2002 core loop and feel (single-keystroke commands, ANSI-flavored aesthetics, the canonical port/planet/combat systems); deterministic, seedable universe and rules engine with full unit-test coverage of game math; single-player first with a clean path to LAN/hosted multiplayer; modern TUI affordances layered on top (clickable warps, sortable tables, built-in route planner); everything configurable (universe size, economy constants, ship stats) via versioned config files.

**Non-goals (v1).** Telnet/BBS door compatibility; TWGS protocol compatibility with existing TW2002 helper tools; massive concurrency (we design for tens of players, not hundreds); pixel graphics.

---

## 4. Architecture

Following the twclone/terminal-space consensus, the system is four layers with strict downward-only dependencies:

```
helix/
├── pyproject.toml
├── helix/
│   ├── core/                 # Pure rules engine. No I/O, no async, no Textual.
│   │   ├── models.py         # Entities: Sector, Port, Planet, Ship, Player, Corp...
│   │   ├── enums.py          # PortClass, Commodity, ShipType ids, etc.
│   │   ├── economy.py        # Pricing, trade resolution, port regen math
│   │   ├── combat.py         # Attack/defense resolution, odds, salvage
│   │   ├── movement.py       # Warp validation, pathfinding, turn costs
│   │   ├── planets.py        # Colonist production, citadel logic
│   │   ├── rules.py          # Command -> Event reducers (the only state mutators)
│   │   └── events.py         # Immutable event dataclasses (facts)
│   ├── bigbang/              # Universe generation (imports core, networkx)
│   │   ├── generator.py      # Cluster-and-bridge graph builder
│   │   ├── topology.py       # Tunnels, deadends, rings, fedspace carving
│   │   ├── populate.py       # Ports, planets, NPCs, StarDock placement
│   │   └── validate.py       # Connectivity, distance, fairness checks
│   ├── engine/               # Time & background simulation (asyncio)
│   │   ├── ticker.py         # Short tick loop + cron tasks (daily turn reset...)
│   │   ├── port_economy.py   # Hourly stock regen / order generation
│   │   ├── planet_growth.py  # BNT-style production tick
│   │   └── npc.py            # Ferengi-style trader AI, Cabal-style raiders
│   ├── store/                # Persistence (SQLite via sqlite3/SQLAlchemy)
│   │   ├── repo.py           # Repository interface (swap target for Postgres)
│   │   ├── schema.sql
│   │   └── snapshots.py      # Save/load, autosave
│   ├── server/               # Game service: applies commands, emits events
│   │   ├── service.py        # In-process API (single-player embeds this)
│   │   ├── session.py        # Player session + fog-of-war context
│   │   └── net.py            # (Phase 4) JSON-RPC over websockets
│   └── tui/                  # Textual application
│       ├── app.py            # HelixApp, screen stack, keybinds
│       ├── screens/          # Sector, Port, Planet, StarDock, Computer, Map...
│       ├── widgets/          # WarpList, HoldsBar, TickerLog, SectorScan...
│       └── theme.tcss        # Textual CSS, TW2002 cyan/magenta/yellow palette
└── tests/
```

**Command/event flow.** The TUI (or a bot, or a network client) submits a `Command` to `server.service`. The service validates it against a `SessionContext` (terminal-space pattern), calls the appropriate pure reducer in `core.rules`, which returns `(new_state_delta, [events])`. Events are appended to an event log table (twclone's durable rail) and fanned out to subscribed sessions; the engine's tick loop consumes the same log for background reactions. All randomness flows through a seeded `random.Random` owned by the game state, so any game is fully reproducible from `(seed, command log)` — which is also our save-game integrity check and our regression-test harness.

**Fog of war at the boundary.** Internal models are complete; everything sent to a client passes through `to_public(context)` projections that strip unexplored warps, unseen port stock, and cloaked ships, exactly as terminal-space does.

**Single-player = embedded server.** The Textual app instantiates `service.GameService` in-process with a background asyncio task running `engine.ticker`. Multiplayer later swaps the in-process call for JSON-RPC over websockets without changing the TUI's interface to the service.

---

## 5. Data Model

Core entities and their key fields (persisted 1:1 in SQLite tables; in memory as dataclasses):

| Entity | Key fields |
|---|---|
| `Game` | id, seed, config_version, created_at, day_number |
| `Sector` | id, region_id, warps_out [list], beacon_text, fighters (owner, qty, mode), mines (owner, qty), is_fedspace |
| `Region` | id, name ("Halaf Zone"...) — the named cluster from generation |
| `Port` | id, sector_id, name, class (1–9), size, per-commodity {stock, capacity, mode buy/sell}, credits |
| `Planet` | id, sector_id, name, class, colonists, allocation %s, stores {ore, organics, equipment, fighters}, citadel_level, owner |
| `Ship` | id, type_id, name, owner, sector_id, holds_total, cargo {commodity: qty}, fighters, shields, colonists, devices (genesis, probes, beacons, cloak...) |
| `Player` | id, name, credits, bank_balance, turns_remaining, alignment, experience, corp_id, explored_sectors (bitset), ship_id |
| `Corporation` | id, name, tag, ceo_id, bank_balance — NPC factions are corporations (twclone pattern) |
| `EventLog` | id (monotonic), tick, type, payload JSON — the durable rail |
| `Config` | typed key/value by scope, versioned (twclone's DB-backed config, simplified to a YAML file + table snapshot) |

Commodities are the canonical TW2002 trio — Fuel Ore, Organics, Equipment — with port classes the eight buy/sell triples (terminal-space enum, Section 2.2) plus Class 0/9 StarDock selling hardware. BNT's fourth commodity (energy) is deliberately omitted for authenticity.

Ship types are config data, not code (ExchangeConflict's ships.json generalized): each type defines holds min/max, fighter/shield/mine maxes, turns-per-warp, offensive/defensive odds multipliers, and price. v1 ships at minimum: Merchant Cruiser (starter, 20–75 holds per the original data), Scout Marauder, Missile Frigate, BattleShip, Imperial StarShip, plus the Ferengi NPC hulls.

---

## 6. Universe Generation ("Big Bang")

Deterministic from `(seed, config)`. Default 1000 sectors (config 100–5000). Pipeline, synthesizing SectorWars' algorithm note, twclone's bigbang, and ExchangeConflict's motifs:

1. **Cluster pass.** Partition sectors into groups of 5–25; within each group, connect each sector bidirectionally to a random other member, then add extra intra-group edges until average intra-group degree ≈ 2.5. Name each group from a region-name generator (adjective + noun pools, ExchangeConflict-style word lists).
2. **Bridge pass.** Connect each group to 1–5 other groups via single warps; with probability `one_way_chance` (default 0.15) a bridge is directional only.
3. **Motif pass.** Inject configured counts of *tunnels* (chains of length 4–9 grafted at one end — twclone default ~15), *deadends* (1–2 sector stubs), and *rings* (cycles of 3/5/7/9, ExchangeConflict weights).
4. **FedSpace carve.** Sectors 1–10 become FedSpace: fully interlinked neighborhood around sector 1 (Terra), protected (no attacks, no fighter/mine deployment), with guaranteed exits to the wider graph (twclone's `ensure_fedspace_exit`).
5. **Populate.** StarDock (Class 9) placed 2–5 hops from FedSpace. Standard ports at ~45% sector density with the terminal-space class distribution (20/20/20/10/10/10/5/5) and initial stock `randint(200, 2000)` scaled by port size. Planets seeded in ~25% of sectors. NPC faction homeworlds at tunnel endpoints (twclone), with garrisons scaled to distance from FedSpace — our Cabal-descendant raider territory.
6. **Validate.** Assert: single strongly-reachable component from sector 1 (treating one-ways correctly); max warps per sector ≤ 6 (TW2002 canon); StarDock reachable; at least one profitable port-pair (opposed classes, e.g. BBS↔SSB) within 5 hops of FedSpace so new players can earn; per-region port balance within tolerance. Regenerate with a perturbed sub-seed on failure (bounded retries, then error).

A dev tool `helix bigbang --inspect` renders the graph (networkx + matplotlib export, plus an in-TUI map debugger) with port sectors highlighted, mirroring ExchangeConflict's uniview.

---

## 7. Economy

**Pricing.** BNT's parameterized linear model with terminal-space's stock-ratio shape. Per commodity `c` at a port: when the port *sells* `c`: `price(c) = base[c] - delta[c] * stock_ratio * elasticity`; when it *buys*: `price(c) = base[c] + delta[c] * (1 - stock_ratio) * elasticity`. Defaults (per-unit credits): fuel ore base 11 delta 5; organics base 5 delta 2; equipment base 15 delta 7 (BNT's tuned values, relabeled to the TW trio). All constants in config.

**Haggling.** TW2002's signature negotiation, implemented as a bounded mini-game: the port quotes; the player counter-offers; acceptance probability falls off with distance from fair price and with the player's recent haggling history at that port; 2 rejections end negotiation at the port's final price; an insulting offer (>~30% off fair) aborts the trade. Tunable; can be disabled for "quick trade" mode.

**Stock regeneration.** Phase 1–2 ships with simple regen: each economy tick (hourly game time), stock moves 5% toward the port's desired level (50% capacity standard, 90% StarDock — twclone ratios). Phase 5 upgrades to twclone's full order-book market (ports post buy/sell orders; daily settlement matches and physically moves goods), which makes inter-port logistics and NPC arbitrage real.

**Banking.** Player bank accounts at StarDock with modest interest (BNT's 1.0005/tick compounded is the reference; we tune to ~0.5%/game-day) and corp accounts. Invariants enforced in one place (`core.economy`): balances never negative, goods conserved, every mutation inside a transaction.

**NPC traders.** Ferengi-style mobile arbitrageurs (twclone model): roam nearby sectors, compare port prices, execute real trades that move real stock and credits, hold persistent cargo/cash under their faction corporation. They are the economy's circulation system and an emergent piracy target.

---

## 8. Time, Turns, and the Engine

Per the original TWINSTR.DOC rules: players get N turns per game-day (default 250, config); each warp move costs turns per the ship's `turns_per_warp`; docking costs 1. The engine (`engine.ticker`, an asyncio task) implements twclone's two-level scheduling: a short tick (default 1 s real time) that consumes the event log, steps NPCs in bounded batches, and runs sweepers; plus durable cron tasks — `daily_turn_reset`, `hourly_port_economy`, `planet_growth`, `interest_accrual` — with persisted `next_due_at` so a reloaded save never double-runs or skips a tick. In single-player, game time can be configured to advance only while playing, or in real time.

---

## 9. Combat and Territory

Phase 3 ships the classic stack. Sector fighters: deployable in offensive/defensive/toll modes; entering a hostile-fighter sector forces engagement or retreat (retreat costs one fighter — the original rule). Mines (Armid/limpet split deferred to Phase 5) damage on entry with deflector mitigation. Ship-to-ship combat resolves in rounds: attacker commits fighters, hit ratios derive from ship-type odds multipliers and percentile rolls (BNT's shape), shields absorb first, destroyed ships yield 10–20% cargo salvage (BNT) and drop the pilot to an escape pod if owned. Defensive devices: emergency warp (random-sector escape on trigger), cloak (Phase 5). FedSpace is combat-free and deployment-free; Federal response punishes criminal alignment there. NPC raiders defend their tunnel territory and occasionally raid trade lanes; clearing their homeworld is the single-player long-game objective, with bounties per fighter destroyed echoing the Cabal's 100/kill.

---

## 10. Textual UI

Textual gives us screens, CSS layout, widgets, mouse support, and free web deployment via `textual serve`. The design honors TW2002 muscle memory while exploiting modern widgets.

**Screen map.** `MainMenu` → `Game` (the primary screen) with modal/pushed screens: `PortScreen`, `PlanetScreen`, `StarDockScreen` (shipyard/hardware/bank/tavern tabs), `ComputerScreen`, `MapScreen`, `MessagesScreen`.

**Game screen layout.** Three regions. Left 2/3: the sector view — region name, sector number, ANSI-art flavor header, contents (ports, planets, ships, fighters, beacons) as a Rich-renderable log, and a clickable `WarpList` widget showing outbound warps (unexplored ones dimmed with `?`). Right 1/3: status sidebar — ship name/type, holds bar (per-commodity fill), fighters/shields, credits, turns remaining, current region mini-map (explored neighbors as a small node diagram). Bottom: a one-line command input plus a scrolling event ticker.

**Command grammar.** Single-keystroke commands matching TW2002 where it matters — number keys warp by sector number, `M` move (prompt for sector), `P` dock at port, `L` land on planet, `D` re-display sector, `C` computer, `T` corporate/team menu, `G` galactic map, `I` ship info, `Q` quit — implemented as Textual key bindings with an Esc-cancelable prompt model (terminal-space's InstantCmd concept, replaced by Textual's native bindings + Input). Every keystroke action also has a clickable affordance.

**Computer screen** bakes in what the community bolted onto real TW2002 via TWX Proxy/twstak-class tools: explored-universe map (Tree/DataTable), port directory with last-seen stock and class, *pair-trade finder* (scores opposed-class port pairs by round-trip profit per turn using current price model and shortest-path distance), *route planner* (shortest path with one-way awareness; sends the ship hop-by-hop with per-sector hazard confirmation), and notes/avoid lists. Since we own the engine, these are first-class queries rather than screen-scrapers.

**Aesthetics.** A `tw2002` Textual theme: cyan/yellow/magenta on black, CP437-flavored box drawing, optional CRT-ish flourishes (subtle starfield animation on the title screen — terminal-space's terminaltexteffects idea, reimplemented with Textual animation primitives). A `--plain` flag disables effects.

---

## 11. Persistence

SQLite, one file per game (`~/.helix/games/<name>.db`), WAL mode. Tables mirror Section 5 entities plus `event_log` and `config`. Saves are implicit (every command is durable once its transaction commits — the BBS property that you can hang up mid-session and resume, per TWINSTR.DOC). `snapshots.py` adds export/import of a portable save (gzipped JSON of state + command log). The repository interface is the swap point for PostgreSQL if hosted multiplayer ever demands it (twclone's lesson, pre-paid architecturally rather than adopted prematurely).

---

## 12. Testing Strategy

The pure core makes this cheap: property-based tests (hypothesis) for economy invariants (no negative balances, goods conservation under arbitrary trade sequences, price monotonicity in stock); golden-master tests replaying recorded command logs against fixed seeds and asserting final state hashes; bigbang validation tests across 100 seeds (connectivity, port-pair reachability, degree caps); and Textual's `Pilot` test harness for UI flows (dock → haggle → buy → warp). NPC AI is tested by running headless bot-vs-engine simulations — twclone's `ai_player` bug-report harness shows how productive bot-driven QA is for this genre, and our service API is bot-friendly by construction.

---

## 13. Roadmap

**Phase 1 — Walking skeleton.** Core models, bigbang (cluster+bridge+validate), movement with turn costs, port docking and trading with live pricing and haggling, SQLite persistence, Textual game screen with sector view/warp list/status bar/port screen. Playable trading game, single ship type. *Exit criterion: profitable pair-trading loop is fun for 30 minutes.*

**Phase 2 — Progression.** StarDock (shipyard, hardware emporium, bank), multiple ship types from config, cargo/hold upgrades, planets with landing and BNT production model, Genesis torpedoes, explored-map Computer screen with pair-trade finder and route planner.

**Phase 3 — Conflict.** Sector fighters (off/def/toll), mines, ship combat with salvage and escape pods, alignment/experience, FedSpace law, NPC raider faction in tunnel territory with bounties, NPC Ferengi-style traders moving real goods.

**Phase 4 — Multiplayer.** Extract `server.net` (JSON-RPC over websockets, Pydantic DTOs already in place), lobby/auth, corporations with shared assets and corp bank, broadcast pipeline, `textual serve` hosted client.

**Phase 5 — Depth.** Order-book market economy (twclone Phase-4 model), citadels and planetary combat, cloaking/probes/interdictor, tavern/noticeboard, sysop console (AAT's admin catalog as the menu), TWX-style scripting hooks for bots.

---

## 14. Technology Stack

Python ≥ 3.12; Textual (TUI) + Rich; networkx (generation/pathfinding only — runtime adjacency is plain dicts); Pydantic v2 (DTOs/config); SQLite stdlib (repository pattern; SQLAlchemy optional later); hypothesis + pytest (+ pytest-asyncio, textual Pilot); ruff + mypy strict on `core/` and `bigbang/`. Phase 4 adds websockets + pjrpc-style JSON-RPC.

---

## Appendix A — Analyzed Repositories

| Repo | Language | Role in this design |
|---|---|---|
| rdearman/twclone | C + PostgreSQL | Architecture (server/engine split, event rails, cron), market economy, tunnels/FedSpace bigbang, protocol catalog |
| mrdon/terminal-space | Python | Domain model, port class enum & distribution, pricing shape, public-DTO/fog-of-war pattern, embedded-server single-player |
| cheevauva/blacknovatraders (BNT mirror) | PHP | Tuned economy constants, planet production math, equipment prices, combat baseline |
| tarnus/aatraders | PHP | Sysop/admin feature catalog |
| leonard4/SectorWars | C++ | TW sector-graph algorithm description (cluster-and-bridge) |
| jzmiller1/ExchangeConflict2016 | Python | Graph motifs (deadends/rings), networkx generation, map inspector, config-driven ships |
| drbeco/tradewars (incl. tw2bas/) | C + 1986 BASIC | Original rules (turns, sector fighters, retreat cost, Cabal NPCs, 500-sector scale), authenticity reference |
