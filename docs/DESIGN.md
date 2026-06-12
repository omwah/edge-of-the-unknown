# Project Helix — Design Document
## An Exploration-First Space Game on TradeWars 2002 Bones, in Python + Textual

*Version 0.2 — June 2026 (exploration-first revision)*

---

## 1. Purpose and Scope

Project Helix is a game of space exploration and discovery built on the mechanical bones of TradeWars 2002 (TW2002), the classic BBS door game, as a modern terminal application using Python 3.12+ and the Textual TUI framework. The player's goal is to push outward from FedSpace into an unknown warp-connected universe and find what is out there: uncharted planets that can be descended onto, derelict shipwrecks, nebulae and black holes, strange space-borne entities, and the ruins, artifacts, and ancient technology of lost civilizations. The classic TW2002 port pair-trading loop is retained intact — but as a means to an end. Trading funds the faster engines, stronger shields, better sensors, cloaking devices, and armaments needed to travel farther, survive hostile space, and reach rarer and more valuable discoveries. The galaxy is inhabited by friendly and hostile alien races: friendly races (the majority) offer technology for barter or for the universal currency, gold-pressed latinum; hostile races are the escalating price of deep space, with the deadliest among them also the rarest.

This document is informed by direct source analysis of seven existing TradeWars clones and the original 1986 TradeWars II BASIC source; the warp-graph universe, port economy, turn system, and engine foundations remain TW2002-authentic even where the goals diverge. Section 2 summarizes what each codebase taught us; the remainder of the document specifies our design.

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

**Goals.** An exploration-first core loop — venture out, discover, return, upgrade, venture farther — layered on an authentic TW2002 foundation (warp graph, turns per day, port pair-trading, single-keystroke commands, ANSI-flavored aesthetics); a tangible risk/reward gradient in which discovery rarity, technology value, and danger all scale with distance from FedSpace; trading as the reliable income floor and discovery as the progression ceiling; deterministic, seedable universe and rules engine with full unit-test coverage of game math; single-player first with a clean path to LAN/hosted multiplayer; modern TUI affordances layered on top (clickable warps, sortable tables, built-in route planner, discovery codex); everything configurable (universe size, economy constants, ship stats, race rosters, discovery tables) via versioned config files.

**Non-goals (v1).** Telnet/BBS door compatibility; TWGS protocol compatibility with existing TW2002 helper tools; massive concurrency (we design for tens of players, not hundreds); pixel graphics; full 4X-style diplomacy or empire simulation (race attitude is a simple score, not a diplomacy tree).

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
│   │   ├── planets.py        # Colonist production, descent & surface exploration
│   │   ├── races.py          # Race archetypes, disposition, attitude, tech-barter offers
│   │   ├── discovery.py      # Discovery tables, rarity gradient, detection, salvage
│   │   ├── encounters.py     # Hostile-race encounter rolls, flee resolution (escape floor)
│   │   ├── rules.py          # Command -> Event reducers (the only state mutators)
│   │   └── events.py         # Immutable event dataclasses (facts)
│   ├── bigbang/              # Universe generation (imports core, networkx)
│   │   ├── generator.py      # Cluster-and-bridge graph builder
│   │   ├── topology.py       # Tunnels, deadends, rings, fedspace carving
│   │   ├── populate.py       # Ports, planets, races, discoveries, StarDock placement
│   │   └── validate.py       # Connectivity, distance, fairness checks
│   ├── engine/               # Time & background simulation (asyncio)
│   │   ├── ticker.py         # Short tick loop + cron tasks (daily turn reset...)
│   │   ├── port_economy.py   # Hourly stock regen / order generation
│   │   ├── planet_growth.py  # BNT-style production tick
│   │   └── npc.py            # Race ship AI: friendly traders, hostile hunters
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
| `Sector` | id, region_id, warps_out [list], beacon_text, fighters (owner, qty, mode), mines (owner, qty), is_fedspace, distance_band (hops from sector 1, precomputed), phenomena [nebula, black_hole...] |
| `Region` | id, name ("Halaf Zone"...) — the named cluster from generation; controlling_race_id |
| `Port` | id, sector_id, name, class (1–9), size, per-commodity {stock, capacity, mode buy/sell}, latinum |
| `Planet` | id, sector_id, name, class, colonists, allocation %s, stores {ore, organics, equipment, fighters}, citadel_level, owner, surface_sites [Discovery ids] |
| `Ship` | id, type_id, name, owner, sector_id, holds_total, cargo {commodity: qty}, shields {current, max}, engine_speed, cloak_rating, sensor_rating, fighters, armaments, colonists, devices (genesis, probes, beacons...) |
| `Player` | id, name, latinum, bank_balance, turns_remaining, alignment, experience, corp_id, explored_sectors (bitset), ship_id, race_attitudes {race_id: score}, codex (found discovery ids) |
| `Race` | id, name, archetype_id, disposition (friendly/hostile), federation_aligned, tech_level (1–10), home_region_id, threat_rating + interception_rating (hostile only), encounter_weight |
| `Discovery` | id, location (sector_id or planet_id + site slot), kind (wreck, nebula, black_hole, entity, ruins, artifact, ancient_tech, crashed_ship), rarity_tier, hidden (needs sensor check), payload (tech item / latinum / lore fragment), found_by |
| `Corporation` | id, name, tag, ceo_id, bank_balance — NPC factions are corporations (twclone pattern) |
| `EventLog` | id (monotonic), tick, type, payload JSON — the durable rail |
| `Config` | typed key/value by scope, versioned (twclone's DB-backed config, simplified to a YAML file + table snapshot) |

Commodities are the canonical TW2002 trio — Fuel Ore, Organics, Equipment — with port classes the eight buy/sell triples (terminal-space enum, Section 2.2) plus Class 0/9 StarDock selling hardware. BNT's fourth commodity (energy) is deliberately omitted for authenticity.

**Currency.** The universal currency is **gold-pressed latinum** ("latinum"). All port prices, bank balances, hardware costs, and race technology offers are denominated in it; high-value race tech may additionally (or exclusively) demand barter in artifacts and recovered technology from the player's discoveries.

**Ship aspects.** Every ship is described by a common set of aspects: *cargo capacity* (holds), *shields* (max + regen), *engine speed* (governs turns-per-warp and is the primary input to flee rolls), *cloak/stealth rating* (chance to avoid detection by hostile races; 0 = none), *sensor rating* (chance to detect hidden discoveries and to spot hostiles first), and *armaments* (fighters plus weapon hardpoints). Race technology upgrades improve individual aspects within hull-defined caps. Ship types are config data, not code (ExchangeConflict's ships.json generalized): each type defines per-aspect base values and caps, turns-per-warp, offensive/defensive odds multipliers, and price. v1 ships at minimum: Merchant Cruiser (starter, 20–75 holds per the original data), Scout Marauder, Missile Frigate, BattleShip, Imperial StarShip, plus race NPC hulls.

---

## 6. Universe Generation ("Big Bang")

Deterministic from `(seed, config)`. Default 1000 sectors (config 100–5000). Pipeline, synthesizing SectorWars' algorithm note, twclone's bigbang, and ExchangeConflict's motifs:

1. **Cluster pass.** Partition sectors into groups of 5–25; within each group, connect each sector bidirectionally to a random other member, then add extra intra-group edges until average intra-group degree ≈ 2.5. Name each group from a region-name generator (adjective + noun pools, ExchangeConflict-style word lists).
2. **Bridge pass.** Connect each group to 1–5 other groups via single warps; with probability `one_way_chance` (default 0.15) a bridge is directional only.
3. **Motif pass.** Inject configured counts of *tunnels* (chains of length 4–9 grafted at one end — twclone default ~15), *deadends* (1–2 sector stubs), and *rings* (cycles of 3/5/7/9, ExchangeConflict weights).
4. **FedSpace carve.** Sectors 1–10 become FedSpace: fully interlinked neighborhood around sector 1 (Terra), protected (no attacks, no fighter/mine deployment), with guaranteed exits to the wider graph (twclone's `ensure_fedspace_exit`).
5. **Distance bands.** Compute every sector's warp-hop distance from sector 1 and bucket into config-defined bands (e.g. Core 0–5, Frontier 6–12, Deep 13–20, Void 21+). Bands drive race placement, discovery rarity, and encounter danger throughout the game.
6. **Populate.** StarDock (Class 9) placed 2–5 hops from FedSpace. Standard ports at ~45% sector density with the terminal-space class distribution (20/20/20/10/10/10/5/5) and initial stock `randint(200, 2000)` scaled by port size; port density thins in the outer bands (deep space is wild, not commercial). Planets seeded in ~25% of sectors. **Races:** the friendly-majority roster (Section 7) is assigned home regions — FedSpace and all Core-band regions receive only Federation-aligned friendly races; hostile races claim territory in outer bands, with homeworlds at tunnel endpoints (twclone) and mean threat rating rising with band. **Discoveries:** every sector and planet rolls on its band's rarity table (Section 8); planets additionally roll surface sites (ruins, artifacts, ancient tech, crashed ships).
7. **Validate.** Assert: single strongly-reachable component from sector 1 (treating one-ways correctly); max warps per sector ≤ 6 (TW2002 canon); StarDock reachable; at least one profitable port-pair (opposed classes, e.g. BBS↔SSB) within 5 hops of FedSpace so new players can earn; per-region port balance within tolerance; no hostile race presence in FedSpace or Core-band regions; mean discovery rarity/value strictly increasing across bands; at least one friendly-race contact point per band so deep explorers can resupply and barter. Regenerate with a perturbed sub-seed on failure (bounded retries, then error).

A dev tool `helix bigbang --inspect` renders the graph (networkx + matplotlib export, plus an in-TUI map debugger) with port sectors highlighted, mirroring ExchangeConflict's uniview.

---

## 7. Races

The universe is inhabited by alien races, generated at big bang from a config-defined roster of archetypes and seeded into regions of the warp graph. Races replace the single faceless NPC faction of classic TW2002 — the Cabal/Ferengi lineage survives as hostile-race archetypes and as the friendly traders who keep the economy circulating.

**Disposition.** Every race is friendly or hostile, and friendly races outnumber hostile ones (default 70/30 roster split, config-tunable). FedSpace and the Core distance band are populated exclusively by friendly races aligned with the Federation; hostile territory begins in the Frontier band and deepens outward.

**Tech level.** Each race has a tech level (1–10) expressed in two ways: how fast its ships travel (the engine speed of its hulls — which for hostile races also makes them harder to outrun) and what technology upgrades it can offer the player. Friendly races sell or barter upgrades to ship aspects — engine tunings, shield arrays, sensor suites, cloaking modules, hold expansions, armaments — priced in gold-pressed latinum or traded against artifacts and recovered technology from the player's discoveries. Higher-tech races offer better goods but demand rarer barter; race tech level loosely correlates with distance from FedSpace, so the best upgrades require traveling to, and surviving, deep space.

**Hostile races.** Each hostile race has a *threat rating* (damage dealt per combat round) and an *interception rating* (how effectively it prevents a fleeing player from escaping). Encounter frequency is inversely proportional to threat: the deadliest races are the rarest (encounter weights per band live in config alongside the roster). Flee resolution is specified in Section 11; as a hard invariant, the player's escape probability never drops below a configured floor (default 10%), no matter how heavily damaged the ship is.

**Attitude.** Friendly races track a simple per-player attitude score — raised by trading with them and doing favors, lowered by attacking their ships — which gates access to their best technology tiers. Full diplomacy trees are out of scope for v1.

Race rosters — names, archetypes, dispositions, tech curves, threat/interception tables, encounter weights, barter preferences — are config data, not code.

---

## 8. Exploration and Discovery

Discovery is the game's central reward system: the universe is salted at big bang with things to find, and finding them is how the player advances beyond what latinum alone can buy.

**Discovery classes.**
- *Astronomical phenomena* — nebulae (sensor interference: ships inside are harder to detect, a hiding mechanic that stacks with cloaking), black holes (navigation hazards with configurable behavior, from damage-on-approach to one-way gravity warps), and rarer singular phenomena.
- *Derelict shipwrecks* — salvageable in space for cargo, latinum, technology, and log fragments that hint at the locations of other discoveries.
- *Space entities* — living things encountered in open space, ranging from harmless curiosities to hazards to beings that can be traded with.
- *Planets* — beyond their classic TW2002 colony role, planets can be **descended onto**. Surface exploration reveals sites: ruins, artifacts, ancient technology caches, crashed ships.

**Rarity gradient.** Every discovery has a rarity tier — Common, Uncommon, Rare, Exceptional, Legendary. Two rules govern placement: (1) rarity probability shifts upward with the sector's distance band, so FedSpace neighborhoods hold only common curiosities while the deep frontier holds the legendary finds; and (2) value scales with rarity, specifically *technology-progression* value — rare finds yield aspect upgrades, unique devices, and barter goods that no amount of near-home trading can buy. Band weights and tier payout tables are config data; the big bang validator asserts the gradient is monotonic.

**Discovery flow.** Entering a sector reveals its obvious features; the ship's sensor rating determines whether hidden discoveries (drifting wrecks, nebula-shrouded sites) are detected, so sensors are a real progression axis. Planet descent costs turns and presents the planet's surface sites for exploration one at a time. All outcomes draw from the game's seeded RNG: a given seed always buries the same treasures in the same places.

**The loop.** Trade near home → buy engine/shield/sensor upgrades → push one band deeper → discover → barter finds with high-tech friendly races for better upgrades → push deeper still. Trading remains the reliable income floor; discovery is the progression ceiling.

---

## 9. Economy

**Pricing.** BNT's parameterized linear model with terminal-space's stock-ratio shape, denominated in gold-pressed latinum. Per commodity `c` at a port: when the port *sells* `c`: `price(c) = base[c] - delta[c] * stock_ratio * elasticity`; when it *buys*: `price(c) = base[c] + delta[c] * (1 - stock_ratio) * elasticity`. Defaults (per-unit latinum): fuel ore base 11 delta 5; organics base 5 delta 2; equipment base 15 delta 7 (BNT's tuned values, relabeled to the TW trio). All constants in config.

**Role of trading.** Trading is deliberately the means, not the end: profit curves are tuned so that pair-trading reliably funds early aspect upgrades (engine, shields, sensors, holds), while the highest technology tiers are gated behind race barter and rare discoveries that latinum alone cannot buy. The pair-trade finder and route planner keep the trading loop tight so it stays a fun engine for exploration rather than a grind.

**Haggling.** TW2002's signature negotiation, implemented as a bounded mini-game: the port quotes; the player counter-offers; acceptance probability falls off with distance from fair price and with the player's recent haggling history at that port; 2 rejections end negotiation at the port's final price; an insulting offer (>~30% off fair) aborts the trade. Tunable; can be disabled for "quick trade" mode.

**Stock regeneration.** Phase 1–2 ships with simple regen: each economy tick (hourly game time), stock moves 5% toward the port's desired level (50% capacity standard, 90% StarDock — twclone ratios). Phase 5 upgrades to twclone's full order-book market (ports post buy/sell orders; daily settlement matches and physically moves goods), which makes inter-port logistics and NPC arbitrage real.

**Banking.** Player bank accounts at StarDock with modest interest (BNT's 1.0005/tick compounded is the reference; we tune to ~0.5%/game-day) and corp accounts. Invariants enforced in one place (`core.economy`): balances never negative, goods conserved, every mutation inside a transaction.

**NPC traders.** Friendly-race merchant ships are Ferengi-style mobile arbitrageurs (twclone model): they roam nearby sectors, compare port prices, execute real trades that move real stock and latinum, and hold persistent cargo/cash under their race's corporation. They are the economy's circulation system, and trading alongside them builds race attitude.

---

## 10. Time, Turns, and the Engine

Per the original TWINSTR.DOC rules: players get N turns per game-day (default 250, config); each warp move costs turns per the ship's `turns_per_warp`; docking costs 1. The engine (`engine.ticker`, an asyncio task) implements twclone's two-level scheduling: a short tick (default 1 s real time) that consumes the event log, steps NPCs in bounded batches, and runs sweepers; plus durable cron tasks — `daily_turn_reset`, `hourly_port_economy`, `planet_growth`, `interest_accrual` — with persisted `next_due_at` so a reloaded save never double-runs or skips a tick. In single-player, game time can be configured to advance only while playing, or in real time.

---

## 11. Encounters, Combat, and Territory

**Hostile-race encounters.** Moving through or lingering in hostile territory rolls for encounters from the region's race table, with weights inverse to threat rating (Section 7): common raiders harass the Frontier; the apex races of the Void are rarely seen and never forgotten. An encounter opens with a detection check — the race's sensors against the player's cloak rating plus any nebula cover; an undetected player may slip away freely, making stealth a genuine alternative to firepower. Once engaged, each round the player chooses **fight** or **flee**. Flee success is a function of base chance, the player's engine speed minus the race's interception rating, cloak rating, and accumulated hull damage — and is *clamped to a configured floor (default 10%)*, so escape is always possible even in a crippled ship; this floor is a core invariant with its own property test. A failed flight attempt costs one round of incoming damage at the race's threat rating. Shields absorb damage before hull; ship destruction drops the player to an escape pod if owned.

**Classic stack (Phase 3).** Sector fighters: deployable in offensive/defensive/toll modes; entering a hostile-fighter sector forces engagement or retreat (retreat costs one fighter — the original rule). Mines (Armid/limpet split deferred to Phase 5) damage on entry with deflector mitigation. Ship-to-ship combat resolves in rounds: attacker commits fighters, hit ratios derive from ship-type odds multipliers and percentile rolls (BNT's shape), shields absorb first, destroyed ships yield 10–20% cargo salvage (BNT). Defensive devices: emergency warp (random-sector escape on trigger); cloak doubles as the pre-engagement stealth stat above.

**Territory and law.** FedSpace is combat-free and deployment-free, hosts only Federation-aligned friendly races, and Federal response punishes criminal alignment there. Hostile races defend their home regions and occasionally raid trade lanes near the band boundary; raiding *their* homeworlds for legendary-tier technology caches is the single-player long game, with bounties per hostile fighter destroyed echoing the Cabal's 100/kill. Attacking friendly-race ships tanks attitude and locks away their tech offers — piracy has a price.

---

## 12. Textual UI

Textual gives us screens, CSS layout, widgets, mouse support, and free web deployment via `textual serve`. The design honors TW2002 muscle memory while exploiting modern widgets.

**Screen map.** `MainMenu` → `Game` (the primary screen) with modal/pushed screens: `PortScreen`, `PlanetScreen` (orbit view → `SurfaceScreen` for descent and site-by-site exploration), `StarDockScreen` (shipyard/hardware/bank/tavern tabs), `RaceContactScreen` (greeting, tech offers, latinum purchase and artifact barter), `EncounterScreen` (fight/flee rounds against hostile races), `ComputerScreen`, `MapScreen`, `MessagesScreen`.

**Game screen layout.** Three regions. Left 2/3: the sector view — region name, sector number, ANSI-art flavor header, contents (ports, planets, ships, fighters, beacons) as a Rich-renderable log, and a clickable `WarpList` widget showing outbound warps (unexplored ones dimmed with `?`). Right 1/3: status sidebar — ship name/type, aspect readout (shields, engine speed, cloak, sensors), holds bar (per-commodity fill), fighters/armaments, latinum, turns remaining, current distance band, current region mini-map (explored neighbors as a small node diagram). Bottom: a one-line command input plus a scrolling event ticker.

**Command grammar.** Single-keystroke commands matching TW2002 where it matters — number keys warp by sector number, `M` move (prompt for sector), `P` dock at port, `L` land on planet, `D` re-display sector, `C` computer, `T` corporate/team menu, `G` galactic map, `I` ship info, `Q` quit — implemented as Textual key bindings with an Esc-cancelable prompt model (terminal-space's InstantCmd concept, replaced by Textual's native bindings + Input). Every keystroke action also has a clickable affordance.

**Computer screen** bakes in what the community bolted onto real TW2002 via TWX Proxy/twstak-class tools: explored-universe map (Tree/DataTable), port directory with last-seen stock and class, *pair-trade finder* (scores opposed-class port pairs by round-trip profit per turn using current price model and shortest-path distance), *route planner* (shortest path with one-way awareness; sends the ship hop-by-hop with per-sector hazard confirmation), *discovery codex* (every find logged with location, rarity, and lore fragments; collected log fragments surface as rumor pins on the map), *race dossier* (known races, disposition, attitude, last-seen tech offers), and notes/avoid lists. Since we own the engine, these are first-class queries rather than screen-scrapers.

**Aesthetics.** A `tw2002` Textual theme: cyan/yellow/magenta on black, CP437-flavored box drawing, optional CRT-ish flourishes (subtle starfield animation on the title screen — terminal-space's terminaltexteffects idea, reimplemented with Textual animation primitives). A `--plain` flag disables effects.

---

## 13. Persistence

SQLite, one file per game (`~/.helix/games/<name>.db`), WAL mode. Tables mirror Section 5 entities plus `event_log` and `config`. Saves are implicit (every command is durable once its transaction commits — the BBS property that you can hang up mid-session and resume, per TWINSTR.DOC). `snapshots.py` adds export/import of a portable save (gzipped JSON of state + command log). The repository interface is the swap point for PostgreSQL if hosted multiplayer ever demands it (twclone's lesson, pre-paid architecturally rather than adopted prematurely).

---

## 14. Testing Strategy

The pure core makes this cheap: property-based tests (hypothesis) for economy invariants (no negative balances, goods conservation under arbitrary trade sequences, price monotonicity in stock) and for encounter invariants (flee probability never below the configured floor under arbitrary damage/engine/interception combinations; hostile encounter weight inverse to threat rating); golden-master tests replaying recorded command logs against fixed seeds and asserting final state hashes; bigbang validation tests across 100 seeds (connectivity, port-pair reachability, degree caps, FedSpace/Core hosting only Federation-aligned friendly races, discovery rarity and value monotonically increasing across distance bands); and Textual's `Pilot` test harness for UI flows (dock → haggle → buy → warp; descend → explore site → log discovery). NPC AI is tested by running headless bot-vs-engine simulations — twclone's `ai_player` bug-report harness shows how productive bot-driven QA is for this genre, and our service API is bot-friendly by construction.

---

## 15. Roadmap

**Phase 1 — Walking skeleton.** Core models, bigbang (cluster+bridge+distance bands+validate), movement with turn costs, port docking and trading with live pricing and haggling in latinum, SQLite persistence, Textual game screen with sector view/warp list/status bar/port screen. Playable trading game, single ship type. *Exit criterion: profitable pair-trading loop is fun for 30 minutes and visibly funds a first ship upgrade.*

**Phase 2 — Exploration & discovery.** The pivot phase. Discovery system with distance-banded rarity tables (wrecks, nebulae, black holes, entities), planet descent with surface sites (ruins, artifacts, ancient tech, crashed ships), sensor-based detection of hidden finds, discovery codex; friendly races with tech levels, contact screen, latinum sales and artifact barter for aspect upgrades (engine/shields/sensors/cloak/holds); StarDock (shipyard, hardware emporium, bank), multiple ship types from config, planets with BNT production model, Genesis torpedoes, Computer screen with pair-trade finder and route planner. *Exit criterion: a one-hour push-out-and-return exploration run is fun and yields tech that trading alone could not buy.*

**Phase 3 — Danger.** Hostile races with threat/interception ratings and rarity-inverse encounter weights, the encounter system (detection, fight/flee rounds, escape-probability floor), ship combat with salvage and escape pods, black hole and entity hazards live, sector fighters (off/def/toll), mines, alignment/experience, FedSpace law, race attitude consequences, friendly-race NPC traders moving real goods, hostile homeworld raids with bounties. *Exit criterion: the outer bands feel scary but irresistible; players quote their narrow escapes.*

**Phase 4 — Multiplayer.** Extract `server.net` (JSON-RPC over websockets, Pydantic DTOs already in place), lobby/auth, corporations with shared assets and corp bank, broadcast pipeline, `textual serve` hosted client.

**Phase 5 — Depth.** Order-book market economy (twclone Phase-4 model), citadels and planetary combat, probes/interdictor, richer race interactions (favors, escort contracts), tavern/noticeboard, sysop console (AAT's admin catalog as the menu), TWX-style scripting hooks for bots.

---

## 16. Technology Stack

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
