# Project Helix — Design Document
## An Exploration-First Space Game on TradeWars 2002 Bones, in Python + Textual

*Version 0.2 — June 2026 (exploration-first revision)*

---

## 1. Purpose and Scope

Project Helix is a game of space exploration and discovery built on the mechanical bones of TradeWars 2002 (TW2002), the classic BBS door game, as a modern terminal application using Python 3.12+ and the Textual TUI framework. The player's goal is to push outward from the Core Space — the protected central region governed at the outset by the Federation — into an unknown warp-connected universe and find what is out there: uncharted planets that can be descended onto, derelict shipwrecks, nebulae and black holes, strange space-borne entities, and the ruins, artifacts, and ancient technology of lost civilizations. The classic TW2002 port pair-trading loop is retained intact — but as a means to an end. Trading funds the faster engines, stronger shields, better sensors, cloaking devices, and armaments needed to travel farther, survive hostile space, and reach rarer and more valuable discoveries. The galaxy is inhabited by alien species whose disposition runs a continuous scale from openly hostile to warmly friendly: most lean friendly and offer technology for barter or for the universal currency, gold-pressed latinum; the hostile-leaning aliens are the escalating price of deep space, with the deadliest among them also the rarest. Species are bound into rival **alliances** the player can join — but only one at a time, so winning one bloc's favor forfeits its rivals' — over a field of unaligned wild cards, and they hold stances toward *each other* as well as toward the player. The Federation is simply the alliance that governs the Core Space at the start; control of that home region can pass to another alliance through the player's deeds or the galaxy's own upheavals, and with it, whether the Core remains a safe harbor.

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

**Goals.** An exploration-first core loop — venture out, discover, return, upgrade, venture farther — layered on an authentic TW2002 foundation (warp graph, turns per day, port pair-trading, single-keystroke commands, ANSI-flavored aesthetics); a tangible risk/reward gradient in which discovery rarity, technology value, and danger all scale with distance from the Core Space; trading as the reliable income floor and discovery as the progression ceiling; deterministic, seedable universe and rules engine with full unit-test coverage of game math; single-player first with a clean path to LAN/hosted multiplayer; modern TUI affordances layered on top (clickable warps, sortable tables, built-in route planner, discovery codex); everything configurable (universe size, economy constants, ship stats, alien species rosters, discovery tables) via versioned config files.

**Non-goals (v1).** Telnet/BBS door compatibility; TWGS protocol compatibility with existing TW2002 helper tools; massive concurrency (we design for tens of players, not hundreds); pixel graphics; full 4X-style diplomacy or empire simulation (an alien species' attitude is a simple score, not a diplomacy tree).

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
│   │   ├── aliens.py         # Species archetypes, disposition, attitude, tech-barter, alliances, inter-species relations, grudges, signature-mechanic hooks
│   │   ├── discovery.py      # Discovery tables, rarity gradient, detection, salvage
│   │   ├── encounters.py     # Hostile-alien encounter rolls, flee resolution (escape floor)
│   │   ├── rules.py          # Command -> Event reducers (the only state mutators)
│   │   └── events.py         # Immutable event dataclasses (facts)
│   ├── bigbang/              # Universe generation (imports core, networkx)
│   │   ├── generator.py      # Cluster-and-bridge graph builder
│   │   ├── topology.py       # Tunnels, deadends, rings, Core Space carving
│   │   ├── populate.py       # Ports, planets, aliens, discoveries, StarDock placement
│   │   └── validate.py       # Connectivity, distance, fairness checks
│   ├── engine/               # Time & background simulation (asyncio)
│   │   ├── ticker.py         # Short tick loop + cron tasks (daily turn reset...)
│   │   ├── port_economy.py   # Hourly stock regen / order generation
│   │   ├── planet_growth.py  # BNT-style production tick
│   │   └── npc.py            # Alien ship AI: friendly traders, hostile hunters
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
| `Game` | id, seed, config_version, created_at, day_number, **core_governing_alliance_id** (which alliance currently governs the Core Space — mutable state; initialized from the roster's `initial_core_governor`, the Federation by default) |
| `Sector` | id, region_id, warps_out [list], beacon_text, fighters (owner, qty, mode), mines (owner, qty), is_galactic_core (in the protected central region, sectors 1–10), distance_band (hops from sector 1, precomputed), phenomena [nebula, black_hole...] |
| `Region` | id, name ("Halaf Zone"...) — the named cluster from generation; controlling_species_id |
| `Port` | id, sector_id, name, class (1–9), size, per-commodity {stock, capacity, mode buy/sell}, latinum |
| `Planet` | id, sector_id, name, class, colonists, allocation %s, stores {ore, organics, equipment, fighters}, citadel_level, owner, surface_sites [Discovery ids] |
| `Ship` | id, type_id, name, owner, sector_id, holds_total, cargo {commodity: qty}, shields {current, max}, engine_speed, cloak_rating, sensor_rating, fighters, armaments, colonists, devices (genesis, probes, beacons...) |
| `Player` | id, name, latinum, bank_balance, turns_remaining, alignment, experience, corp_id, explored_sectors (bitset), ship_id, species_attitudes {species_id: offset} (per-species disposition offset, applied atop base disposition), alliance_id (joined bloc; **starts as the Federation**), alliance_standing {alliance_id: score}, grudges {species_id: Grudge} (active vendettas held against the player), codex (found discovery ids) |
| `AlienSpecies` | id, name, archetype_id, roster_id (source roster + entry), disposition (0.0 hostile – 1.0 friendly; drawn per-generation from a spread around the roster center), tech_level (1–10), home_region_id, threat_rating, interception_rating, encounter_weight, **alliance_id** (nullable; unaligned wild cards have none), **alliance_role** (leader / member / aspirant / none), **threat_tier** (fearsome / worthy / feeble / special — narrative difficulty band, decoupled from raw threat_rating), **combatant** (bool; non-combatants never open fire), **trade_posture** (open / earn / goods_only / barter / alliance_gated / circuit_gated / refuses), **treaty_mode** (open / conditional / prove_intent / alliance_gated / home_planet_only / none / superfluous), **memory_model** (normal / none / never_forgets), **betrayal_model** (recoverable / permanent), **befriend_price** (config task list — serve/obey/prove/pay/purge), **signature_mechanic** (hook id + params, §7), **pack_behavior** (solo / escorted / swarm / family_group / colony) + **escort** (composition), **fleet** [ship_class ids], **starbase_policy** (none / homeworld / territorial / secret / nomadic_holding), **persona** (speech/style key for prose generation), attitude_gain_rate / attitude_loss_rate |
| `Alliance` | id, name, banner_concept, leader_species_id, member_species_ids [list], posture (expansionist / aloof / authoritarian / …), rival_alliance_ids [list] (mutually hostile blocs), admission_price (gated task: destroy N rival starbases, obey leader…), membership_gate (which species authorizes joining), internal_rival_species_id (optional, for leadership-intrigue events), covets_core (bool; this bloc seeks to seize governance of the Core Space). *No alliance is privileged in the schema — the Federation is an ordinary `Alliance` record that the default roster names as `initial_core_governor` (Game)* |
| `Starbase` | id, sector_id, owner_species_id, ship_class_id (a class with role=starbase), size_m, immobile (true), shields {current, max}, hull, armament [weapon ids], defenses [defense ids], destructible (bool), placement (homeworld / territorial / secret) |
| `Grudge` | id, holder (species_id or player), target (species_id or player), cause, severity, created_at, duration (turns/orbits; ∞ for never_forgets), demand (optional linked task it spawns) |
| `Discovery` | id, location (sector_id or planet_id + site slot), kind (wreck, nebula, black_hole, entity, ruins, artifact, ancient_tech, crashed_ship), rarity_tier, hidden (needs sensor check), payload (tech item / latinum / lore fragment), found_by |
| `Corporation` | id, name, tag, ceo_id, bank_balance — NPC factions are corporations (twclone pattern) |
| `EventLog` | id (monotonic), tick, type, payload JSON — the durable rail |
| `Config` | typed key/value by scope, versioned (twclone's DB-backed config, simplified to a YAML file + table snapshot) |

Commodities are the canonical TW2002 trio — Fuel Ore, Organics, Equipment — with port classes the eight buy/sell triples (terminal-space enum, Section 2.2) plus Class 0/9 StarDock selling hardware. BNT's fourth commodity (energy) is deliberately omitted for authenticity.

**Currency.** The universal currency is **gold-pressed latinum** ("latinum"). All port prices, bank balances, hardware costs, and alien technology offers are denominated in it; high-value alien tech may additionally (or exclusively) demand barter in artifacts and recovered technology from the player's discoveries.

**Ship aspects.** Every ship is described by a common set of aspects: *cargo capacity* (holds), *shields* (max + regen), *engine speed* (governs turns-per-warp and is the primary input to flee rolls), *cloak/stealth rating* (chance to avoid detection by hostile aliens; 0 = none), *sensor rating* (chance to detect hidden discoveries and to spot hostiles first), and *armaments* (fighters plus weapon hardpoints). Alien technology upgrades improve individual aspects within hull-defined caps. Ship types are config data, not code (ExchangeConflict's ships.json generalized): each type defines per-aspect base values and caps, turns-per-warp, offensive/defensive odds multipliers, and price. v1 ships at minimum: Merchant Cruiser (starter, 20–75 holds per the original data), Scout Marauder, Missile Frigate, BattleShip, Imperial StarShip, plus alien NPC hulls.

**Ship and starbase classes (config schema).** Generalizing ExchangeConflict's `ships.json` against the Lightspeed stat-block model, every hull — player, NPC, and starbase — is one `ship_class` config record:

| Field | Meaning |
|---|---|
| `id`, `name` | e.g. `broodmaster_battleship`, "Battleship" |
| `role` | `fighter` / `large_fighter` / `warship` / `capital_warship` / `transport` / `light_craft` / `starbase` |
| `owner_species` | which species fields it (null for player/neutral hulls) |
| `length_m` | hull length — the Ship Size Comparison axis; feeds a size term in detection and hit-chance |
| `speed` | max velocity / engine rating (maps to `engine_speed` aspect and flee math) |
| `aspects` | per-aspect base values + caps (holds, shields, cloak, sensors), as for player ships |
| `armament` | list of `weapon` ids |
| `defenses` | list of `defense` ids |
| `turns_per_warp`, `odds_mult` (off/def), `price` | as for player ship types |
| `immobile` | true for starbases |

A **`weapon`** record is `{name, damage, firing_arc, rate, special}` where `firing_arc ∈ {ahead, all_round, spinal}` (spinal = fires only dead-ahead and only periodically — the counter is to strafe past its firing line), `rate ∈ {continuous, periodic}`, and `special` names a behavior hook (`homing`, `neutron_spark`, `blaster`, `engine_flux`, `proton_stalker_pod`, …; see §7 signature mechanics). A **`defense`** record is `{type, value}` with `type ∈ {laser_turret, armour, screens, energy_plates, speed_and_size}` — `energy_plates` and `screens` are damage-reducing layers, `speed_and_size` is the implicit defense of small fast hulls. A **starbase** is simply a `ship_class` with `role=starbase` and `immobile=true`, given shields/hull, armament, and a `destructible` flag; per-species `starbase_policy` (§7) decides whether and where one is placed. Because alliance admission prices are paid in razed starbases (§7), starbases are first-class destructible targets, not scenery.

---

## 6. Universe Generation ("Big Bang")

Deterministic from `(seed, config)`. Default 1000 sectors (config 100–5000). Pipeline, synthesizing SectorWars' algorithm note, twclone's bigbang, and ExchangeConflict's motifs:

1. **Cluster pass.** Partition sectors into groups of 5–25; within each group, connect each sector bidirectionally to a random other member, then add extra intra-group edges until average intra-group degree ≈ 2.5. Name each group from a region-name generator (adjective + noun pools, ExchangeConflict-style word lists).
2. **Bridge pass.** Connect each group to 1–5 other groups via single warps; with probability `one_way_chance` (default 0.15) a bridge is directional only.
3. **Motif pass.** Inject configured counts of *tunnels* (chains of length 4–9 grafted at one end — twclone default ~15), *deadends* (1–2 sector stubs), and *rings* (cycles of 3/5/7/9, ExchangeConflict weights).
4. **Core Space carve.** Sectors 1–10 become the **Core Space**: a fully interlinked neighborhood around sector 1 (Terra), protected (no attacks, no fighter/mine deployment) under its governing alliance, with guaranteed exits to the wider graph (twclone's `ensure_fedspace_exit` analog). The game's `core_governing_alliance_id` is set to the roster's `initial_core_governor` (the Federation by default), and `Player.alliance_id` is seeded to that same alliance.
5. **Distance bands.** Compute every sector's warp-hop distance from sector 1 and bucket into config-defined bands (e.g. Hub 0–5, Frontier 6–12, Deep 13–20, Void 21+). Bands drive alien species placement, discovery rarity, and encounter danger throughout the game.
6. **Populate.** StarDock (Class 9) placed 2–5 hops from the Core Space. Standard ports at ~45% sector density with the terminal-space class distribution (20/20/20/10/10/10/5/5) and initial stock `randint(200, 2000)` scaled by port size; port density thins in the outer bands (deep space is wild, not commercial). Planets seeded in ~25% of sectors. **Aliens:** a seeded subset is drawn from the configured species roster (Section 7) — not every roster member need appear — and each instantiated species draws its base disposition from a config-bounded spread around its roster center, then is assigned home regions. The Core Space and all Hub-band regions receive only members of the initial governing alliance (the Federation by default) whose realized disposition sits in the friendly band; species outside that alliance claim territory in outer bands, with homeworlds at tunnel endpoints (twclone) and mean threat rating rising (and mean disposition falling) with band. **Discoveries:** every sector and planet rolls on its band's rarity table (Section 8); planets additionally roll surface sites (ruins, artifacts, ancient tech, crashed ships).
7. **Validate.** Assert: single strongly-reachable component from sector 1 (treating one-ways correctly); max warps per sector ≤ 6 (TW2002 canon); StarDock reachable; at least one profitable port-pair (opposed classes, e.g. BBS↔SSB) within 5 hops of the Core Space so new players can earn; per-region port balance within tolerance; the Core Space and Hub-band regions host only friendly-band members of the initial governing alliance (no species below the friendly disposition band, and none from a rival bloc, present there at generation); mean discovery rarity/value strictly increasing across bands; mean alien disposition non-increasing across bands; at least one friendly-disposition contact point per band so deep explorers can resupply and barter. Regenerate with a perturbed sub-seed on failure (bounded retries, then error).

A dev tool `helix bigbang --inspect` renders the graph (networkx + matplotlib export, plus an in-TUI map debugger) with port sectors highlighted, mirroring ExchangeConflict's uniview.

---

## 7. Alien Species and Alliances

The universe is inhabited by alien species, generated at big bang from a config-defined roster of archetypes and seeded into regions of the warp graph. Alien species replace the single faceless NPC faction of classic TW2002 — the Cabal/Ferengi lineage survives as the most hostile-leaning archetypes and as the friendly traders who keep the economy circulating. The roster format and the species parameters below were stress-tested against a seventeen-species reference catalogue (the Lightspeed Hyades-cluster roster) to confirm they can express a real, idiosyncratic cast — three rival alliances over a field of wild cards, each species with one memorable systemic hook — purely as data.

**Disposition.** An alien species is not simply *friendly* or *hostile*. Each species carries a **disposition** — a real number on a continuous scale from `0.0` (utterly hostile) to `1.0` (warmly friendly) — which is its innate baseline stance toward outsiders. The roster skews peaceable (default mean disposition above the midpoint, config-tunable), so amicable species outnumber dangerous ones, but most species live in the broad middle: wary, transactional peoples who will trade yet bristle when provoked. Two configurable thresholds carve the scale into descriptive bands used by generation, prose, and UI labels — a *hostility threshold* (default 0.35) below which a species reads as "hostile," and an *amity threshold* (default 0.65) above which it reads as "friendly" — but behavior interpolates continuously along the scale rather than switching at any single line. The Core Space and the Hub distance band are populated exclusively by friendly-band members of the alliance that governs the Core (the Federation at generation, §7.3); the likelihood of low-disposition species rises with distance from the Core Space, so genuinely hostile territory emerges in the Frontier band and deepens outward.

**Effective disposition.** A species' base disposition is adjusted per player by an *attitude offset* — raised by trading and doing favors, lowered by attacking the species' ships — yielding an **effective disposition** clamped to `[0.0, 1.0]`. Effective disposition is the single quantity that drives every interaction: the probability that an encounter opens with violence rather than greeting, the prices and barter terms an alien species offers, and which technology tiers it will unlock. A player can thus thaw a wary species into a trading partner, or sour a friendly one into an enemy, by their conduct — no species is permanently fixed at a binary stance.

**Tech level.** Each species has a tech level (1–10) expressed in two ways: how fast its ships travel (the engine speed of its hulls — which for hostile-leaning species also makes them harder to outrun) and what technology upgrades it can offer the player. Species disposed to deal will sell or barter upgrades to ship aspects — engine tunings, shield arrays, sensor suites, cloaking modules, hold expansions, armaments — priced in gold-pressed latinum or traded against artifacts and recovered technology from the player's discoveries. Higher-tech species offer better goods but demand rarer barter; an alien species' tech level loosely correlates with distance from the Core Space, so the best upgrades require traveling to, and surviving, deep space.

**Threat and interception.** Every species carries a *threat rating* (damage dealt per combat round) and an *interception rating* (how effectively it prevents a fleeing player from escaping), but how readily it brings them to bear scales with effective disposition: the chance an encounter turns violent rises as effective disposition falls toward `0.0`, and a warmly disposed species will almost never open fire. Among the hostile-leaning species, encounter frequency is inversely proportional to threat — the deadliest aliens are the rarest (encounter weights per band live in config alongside the roster). Flee resolution is specified in Section 11; as a hard invariant, the player's escape probability never drops below a configured floor (default 10%), no matter how heavily damaged the ship is.

**Attitude.** The per-player attitude offset described above is a simple scalar — raised by trading and favors, lowered by aggression — that shifts effective disposition and thereby gates access to a species' best technology tiers. Full diplomacy trees are out of scope for v1.

**Configurable roster.** The set of alien species in play is itself a configuration choice, not a fixed cast. Each game is generated against a named **roster file** — a versioned config listing candidate species with their names, archetypes, base dispositions, tech curves, threat/interception tables, encounter weights, and barter preferences. The big bang draws from this roster rather than instantiating it wholesale, so **no two universe generations need be the same**: a given seed populates only a subset of the roster (some species simply do not appear in a given universe), and an entirely different game can be built from a different source roster (a "Federation classic" roster, a "deep hostile rim" roster, a total-conversion roster of original species) without touching code. Selection is seeded and deterministic — `(seed, roster, config)` reproduces the same cast in the same regions — but varies freely across seeds.

**Per-generation disposition variance.** A species' base disposition in the roster is a *center*, not a fixed value. At big bang each instantiated species draws its actual base disposition from a config-bounded spread around that center (default ±a small variance, tunable per species and globally), so the same species can be warier in one universe and warmer in another. Variance is applied through the seeded RNG and is still subject to all placement invariants — the Core Space and the Hub band only ever receive draws that land in the friendly band (Section 6), and the validator's "mean disposition non-increasing across bands" check is asserted on the *realized* dispositions of the actual cast, not the roster centers. This keeps every generation recognizable yet distinct, and lets the same roster yield a gentle galaxy or a tense one depending on the seed.

### 7.1 Species parameter catalogue

Disposition is the spine, but a species is not reducible to one number. The roster entry for each species carries a structured parameter set (mirrored in the `AlienSpecies` data model, Section 5) that turns a flavor paragraph into game logic. Each parameter below is config, drives a specific subsystem, and is illustrated with the reference-roster exemplar that motivated it:

| Parameter | Type / range | Drives | Exemplar |
|---|---|---|---|
| `disposition_center` + `disposition_variance` | 0.0–1.0 center + spread | base stance; per-generation draw | every species |
| `alliance_id` + `alliance_role` | ref + leader/member/aspirant/none | bloc diplomacy (§7.3) | leads bloc / aspires to join / wild card |
| `tech_level` | 1–10 | hull travel speed *and* the upgrade tiers it will sell/barter | high-tech overlords vs. low-tech fodder |
| `threat_rating` | damage per combat round | combat damage output | heavy capital warships |
| `interception_rating` | 0.0–1.0 | anti-flee term in escape math (§11) | fast pursuers |
| `threat_tier` | fearsome / worthy / feeble / special | encounter pacing + dossier label; *decoupled from `threat_rating`* | a tiny hull that is "lethal one-on-one"; a species "feared out of all proportion to its stats" |
| `combatant` | bool | whether an encounter can become combat at all | pure non-combatants (info brokers, judges, wrecked-pod traders) |
| `trade_posture` | open / earn / goods_only / barter / alliance_gated / circuit_gated / refuses | whether and how trade opens | warlike race that trades only after a fight; a faction that refuses trade entirely |
| `treaty_mode` | open / conditional / prove_intent / alliance_gated / home_planet_only / none / superfluous | whether/how a lasting treaty is offered | "must visit our home planet"; "peace reads as war, no treaty"; "treaty is superfluous, we never fight" |
| `memory_model` | normal / none / never_forgets | how attitude offset persists between encounters | a will-less species that responds identically every time regardless of history; a species that "never forgives, never forgets" |
| `betrayal_model` | recoverable / permanent | the attitude floor after the player attacks/fails them | one betrayal → permanent irreversible hatred |
| `befriend_price` | task list (serve / obey / prove / pay / purge) | what raises attitude and unlocks treaties/tech | "destroy these starbases"; "bring us data"; "prove good conduct over time"; "obey escalating demands" |
| `signature_mechanic` | hook id + params (§7.2) | the species' one unique systemic effect | trojan-gift, reprogram-unlock, influence-gate, morality-judge, … |
| `pack_behavior` + `escort` | solo / escorted / swarm / family_group / colony, + composition | how an encounter group is spawned | "warship escorted by three fighters"; "fast fighters in numbers"; family groups; colonial swarms |
| `fleet` | list of `ship_class` ids | which hulls (and starbase) the species fields | a species with four warship classes; a species with no warships at all |
| `starbase_policy` | none / homeworld / territorial / secret / nomadic_holding | placement of the species' base(s) | ship-dwelling nomads with no base; several secret hard-to-find bases; a single defended homeworld |
| `persona` | style key | prose/dialogue generation tone | inverted Yoda-like syntax; concept-fragment telepathy; archaic biblical cadence; mangled translator garble |
| `attitude_gain_rate` / `attitude_loss_rate` | scalars | how fast favors raise, and aggression lowers, the attitude offset | easily-cowed flatterers vs. implacable grudge-keepers |

The point is that two species with *identical* disposition and threat can still play completely differently because their `signature_mechanic`, `trade_posture`, `memory_model`, `befriend_price`, and `persona` differ — which is exactly how a small roster generates large diplomatic combinatorics.

### 7.2 Signature mechanics

The most reusable idea in the reference catalogue is **one memorable systemic hook per species** rather than uniform stat-blocks. We model this as a registry of named **mechanic hooks**: a species' `signature_mechanic` field names a hook and supplies parameters; the hook is implemented once in `core.aliens` / `core.encounters` and is data-configured per species. The built-in hook types (extensible by config) are:

- **`trojan_gift`** — a gift or a request to "lower shields / take this aboard" seeds a delayed harmful payload. Params: `trigger` (accept-gift / lower-shields), `delay`, `effect` (bomb, parasitic infestation that occupies a hold/engine slot, …), `removable_by` (which service or species can purge it). *Counter-mechanic:* a different species may sell removal.
- **`reprogram_unlock`** — installing an item flips another faction's `trade_posture`. Params: `item`, `source_species`, `target_species`, `new_posture`, `side_effect` (e.g. joining an alliance *disables* it — a genuine either/or).
- **`influence_gate`** — the species can forbid being attacked and/or compel player actions while in contact. Params: `cannot_attack_unbidden` (bool), `compel` (forced responses), `breakthrough` (going in "hard and fast" can beat it). Treaties may require travel to a named home planet.
- **`morality_judge`** — a non-trading fixed-lair entity that audits the player's cumulative conduct and dispenses outcomes. Params: `audited_metrics` (aggression, genocide, being-wronged, virtue), `rewards` (blessing, "purge the cluster" of an oppressor), `punishments` (forced battles, colony curse). Fields no ships; defends itself supernaturally.
- **`escalating_demand`** — befriending opens a ladder of mounting demands (donate, destroy named target, surrender your own base); comply and standing holds, **fail once and `betrayal_model=permanent` triggers**. Params: `demand_ladder`, `fail_consequence`.
- **`literalist`** — `memory_model=none`; responses are keyed only to the player's conversational *approach* via a `keyword_map`, ignoring history. Certain offers (e.g. "peace") can be misread as hostile and trigger combat. Params: `keyword_map`.
- **`contract_kill`** — pays resources/goods for razing the starbases of *named* rival species so the patron can move in. Params: `targets`, `reward`, `binding` (trading creates an obligation; betrayal is punished), `redemption` (a path back after refusal).
- **`coordinate_broker`** — a predatory species that pays goods for the coordinates of undefended worlds (it then preys on them). Params: `reward`.
- **`passage_broker`** — sells information and/or special transit (e.g. moving the ship through time) in exchange for goods or the player's home base. Params: `offer`, `price`.
- **`flee_drop`** — `pack_behavior` weak species that flees immediately on contact, dropping collectable cargo packets. Params: `drop_table`.

Combat-side specials are expressed as the `special` field on a **`weapon`** (§5): `engine_flux` (negates the player's engines — counter is to cut engines and drift), `proton_stalker_pod` (autonomous homing platforms), `neutron_spark`/`blaster`/`homing`, etc.; and as exotic **`defense`** types (`energy_plates`, `screens`). Hooks and weapon/defense specials are the seam where a roster expresses personality without code changes.

### 7.3 Alliances

Species are grouped into **alliances** — named blocs declared in the roster. An alliance is config (the `Alliance` entity, §5): a banner concept, a `leader_species`, a member list, a `posture`, a set of `rival_alliance_ids` it is mutually hostile with, and an `admission_price`. Species outside every alliance are **unaligned wild cards**, each pursuing its own agenda. The reference roster's three mutually-hostile blocs over nine wild cards is the canonical shape, but the count and membership are entirely data-driven.

**The Federation is one alliance among many — it just starts in charge of the Core Space.** No alliance is privileged in the data model; the Federation is an ordinary `Alliance` record. What gives it its starting prominence is *governance of the Core Space* — the protected central region of sectors 1–10 (§6). Governance is a single piece of mutable game state, `Game.core_governing_alliance_id`, initialized at big bang from the roster's `initial_core_governor` setting (the Federation in the default roster). The governing alliance's friendly-band members are the species seeded into the Core and the surrounding Hub band, its forces keep the peace there, and **the player begins as a member of that governing alliance** (`Player.alliance_id` starts as the Federation) — which is exactly what makes the Core Space a safe home to bank, trade, and resupply in at the start of a game.

**Core sanctuary follows the governor, not the Federation.** Whether the Core Space is safe for the player is decided by the player's standing with **whichever alliance currently governs it** (§11), not by any fixed Federation status. At game start those are the same alliance, so the Core is home. But because alliance membership is exclusive, **joining any other bloc resigns the player's membership in the governing alliance**; and aligning with an alliance that the governor counts among its `rival_alliance_ids` makes the player an enemy in the Core's eyes — **the Core Space is no longer safe to enter**, its forces engaging the player on sight until that allegiance is given up and amends are made. Aligning with a bloc the governor merely tolerates forfeits the member's standing without making the Core outright hostile. This is the sharpest "every choice closes a door" decision in the game: the deepest alien tech may lie behind a bloc that costs the player their homeland.

**Governance can change hands.** Control of the Core Space is not frozen at the Federation. An alliance flagged `covets_core` can be brought to power — by the player (championing a rival bloc and dismantling the incumbent's Core presence as that bloc's admission price) or by NPC events (a `covets_core` alliance's own expansion, or an `internal_rival` usurping its alliance and turning it outward). When governance flips, `Game.core_governing_alliance_id` updates and everything keyed to it re-evaluates: who is seeded/welcome in the Core, whose law runs there, and — crucially — whether the *player* is now welcome or hunted, on the same standing rule above. A player who fought to install their own alliance inherits a safe Core under a new flag; a player caught on the wrong side of a takeover can lose a home they never attacked. The seize-the-Core endgame is Phase 5 depth (§15); Phase 3 ships the static-governor case (Federation governs throughout) with the standing rule already driving Core safety.

**Alliances are mutually exclusive for the player.** The player may join at most one alliance at a time (`Player.alliance_id`), and per-alliance standing is tracked separately (`Player.alliance_standing`). Joining is gated by the alliance's `admission_price` (a `befriend_price`-style task: e.g. raze a named number of a rival bloc's starbases, or obey the leader) and, where set, by a `membership_gate` — a specific species whose consent is required (the leader, or a designated gatekeeper, must authorize entry; junior members cannot admit the player alone). On joining:

- every member species receives a positive **attitude offset** (their effective disposition toward the player rises), and members are bound by a **no-attack obligation** — attacking a fellow member voids membership and reverses the bonus;
- every species in each `rival_alliance_id` receives a negative attitude offset (rivals turn cold or hostile) — **signing with one bloc closes doors with its rivals**, the central diplomatic tension;
- unaligned species are unaffected except through their own inter-species relations (§7.4).

`alliance_role` distinguishes a **leader** (sets admission price, can be the gate), a **member**, and an **aspirant** (an unaligned species angling to join — a hook for emergent realignment). An optional `internal_rival_species_id` models a junior member scheming to usurp the leader; for v1 this is flavor/intel surfaced in the alien dossier, with an optional config-gated leadership-change event left to Phase 5's richer interactions. Full diplomacy trees remain out of scope; alliance membership is a single exclusive choice with scalar standing, consistent with §3's non-goals.

### 7.4 Inter-species disposition

Disposition is not only player-facing: species hold stances **toward each other**, which drives NPC-vs-NPC behavior and how befriending one party shifts your standing with others. This is a `relations` block in the roster — a sparse, possibly asymmetric matrix mapping an ordered pair `(species_a, species_b)` to a relation value on `0.0` (hatred) … `1.0` (amity), or to a modifier applied atop a derived default. Defaults are derived, overrides are explicit:

- **Derived default:** same alliance ⇒ friendly; rival alliances ⇒ hostile; otherwise neutral. Computed at big bang from the alliance graph so a roster need not spell out every pair.
- **Explicit overrides:** named affinities and hatreds that cut across alliance lines — an aesthetics-driven loathing between two otherwise-unallied species, an infatuation that explains why a species joined a bloc at all. These are the entries that give a roster character.

Inter-species relations feed three systems: (1) **NPC AI** — when ships of two species meet in a sector, their mutual relation decides whether they ignore, trade with, or fight each other (`engine.npc`); (2) **reputation spillover** — helping or harming species X nudges the player's attitude with X's friends and enemies in proportion to the relation (favor an alliance's enemy and its members cool toward you); (3) **alliance cohesion and grudges** (§7.5). The validator asserts relations stay consistent with alliance membership unless an explicit override is present.

### 7.5 Grudges and vendettas

Some stances are **durable, dated grudges** rather than standing relations — the reference roster is full of them ("a 16-orbit grudge," "a 524-orbit grudge over a named individual"). A `Grudge` (§5) records `holder`, `target`, `cause`, `severity`, `created_at`, and `duration` (finite, or infinite for `memory_model=never_forgets`), and may carry a linked **demand** (a `befriend_price` task the grudge spawns — e.g. a jealous species appends "destroy that rival's starbase" as the price of its regard, marking its members with a vendetta tag). Grudges come from two sources:

- **Seeded** — declared in the roster between species; instantiated at big bang and decaying (or not) over game-days.
- **Runtime** — generated by player conduct. Attacking a species creates a grudge against the player; against a `never_forgets` / `betrayal_model=permanent` species it never decays and floors the attitude offset, locking that species out permanently. A `recoverable` species' grudge decays at its `attitude_gain_rate` as the player makes amends.

Grudges modify the relevant relation/attitude while active and can gate or spawn demands, giving the diplomacy layer memory and momentum without a full diplomacy tree.

### 7.6 Combat threat tiers

`threat_tier` (fearsome / worthy / feeble / special) is a **narrative difficulty band kept deliberately separate from the numeric `threat_rating`**, because the reference catalogue shows the two diverge: a tiny, fragile hull can be "lethal one-on-one," and a species can be "feared out of all proportion to its stats." The tier is config and drives (1) encounter pacing — `special`/`fearsome` species are rarer and weightier (consistent with the rarity-inverse-to-threat rule, §7 disposition prose and §11); and (2) the in-game **alien dossier** (§12), where one faction can be configured to *narrate the others* — ranking every species as a foe — turning flavor text into a usable, in-world difficulty guide. `special` flags the irreducibly weird cases (non-combatants, judges, infestation-only "combat," engine-stealing weapons) that don't sort onto a linear scale.

Alien species rosters — names, archetypes, base disposition centers and variance, tech curves, threat/interception tables and threat tiers, encounter weights, barter preferences, signature mechanics, pack/escort composition, fleets and starbase policy, personas, the alliance blocs and their admission prices, the inter-species relation matrix, seeded grudges, and which roster a game uses — are all config data, not code.

---

## 8. Exploration and Discovery

Discovery is the game's central reward system: the universe is salted at big bang with things to find, and finding them is how the player advances beyond what latinum alone can buy.

**Discovery classes.**
- *Astronomical phenomena* — nebulae (sensor interference: ships inside are harder to detect, a hiding mechanic that stacks with cloaking), black holes (navigation hazards with configurable behavior, from damage-on-approach to one-way gravity warps), and rarer singular phenomena.
- *Derelict shipwrecks* — salvageable in space for cargo, latinum, technology, and log fragments that hint at the locations of other discoveries.
- *Space entities* — living things encountered in open space, ranging from harmless curiosities to hazards to beings that can be traded with.
- *Planets* — beyond their classic TW2002 colony role, planets can be **descended onto**. Surface exploration reveals sites: ruins, artifacts, ancient technology caches, crashed ships.

**Rarity gradient.** Every discovery has a rarity tier — Common, Uncommon, Rare, Exceptional, Legendary. Two rules govern placement: (1) rarity probability shifts upward with the sector's distance band, so Core Space neighborhoods hold only common curiosities while the deep frontier holds the legendary finds; and (2) value scales with rarity, specifically *technology-progression* value — rare finds yield aspect upgrades, unique devices, and barter goods that no amount of near-home trading can buy. Band weights and tier payout tables are config data; the big bang validator asserts the gradient is monotonic.

**Discovery flow.** Entering a sector reveals its obvious features; the ship's sensor rating determines whether hidden discoveries (drifting wrecks, nebula-shrouded sites) are detected, so sensors are a real progression axis. Planet descent costs turns and presents the planet's surface sites for exploration one at a time. All outcomes draw from the game's seeded RNG: a given seed always buries the same treasures in the same places.

**The loop.** Trade near home → buy engine/shield/sensor upgrades → push one band deeper → discover → barter finds with high-tech friendly species for better upgrades → push deeper still. Trading remains the reliable income floor; discovery is the progression ceiling.

---

## 9. Economy

**Pricing.** BNT's parameterized linear model with terminal-space's stock-ratio shape, denominated in gold-pressed latinum. Per commodity `c` at a port: when the port *sells* `c`: `price(c) = base[c] - delta[c] * stock_ratio * elasticity`; when it *buys*: `price(c) = base[c] + delta[c] * (1 - stock_ratio) * elasticity`. Defaults (per-unit latinum): fuel ore base 11 delta 5; organics base 5 delta 2; equipment base 15 delta 7 (BNT's tuned values, relabeled to the TW trio). All constants in config.

**Role of trading.** Trading is deliberately the means, not the end: profit curves are tuned so that pair-trading reliably funds early aspect upgrades (engine, shields, sensors, holds), while the highest technology tiers are gated behind alien barter and rare discoveries that latinum alone cannot buy. The pair-trade finder and route planner keep the trading loop tight so it stays a fun engine for exploration rather than a grind.

**Haggling.** TW2002's signature negotiation, implemented as a bounded mini-game: the port quotes; the player counter-offers; acceptance probability falls off with distance from fair price and with the player's recent haggling history at that port; 2 rejections end negotiation at the port's final price; an insulting offer (>~30% off fair) aborts the trade. Tunable; can be disabled for "quick trade" mode.

**Stock regeneration.** Phase 1–2 ships with simple regen: each economy tick (hourly game time), stock moves 5% toward the port's desired level (50% capacity standard, 90% StarDock — twclone ratios). Phase 5 upgrades to twclone's full order-book market (ports post buy/sell orders; daily settlement matches and physically moves goods), which makes inter-port logistics and NPC arbitrage real.

**Banking.** Player bank accounts at StarDock with modest interest (BNT's 1.0005/tick compounded is the reference; we tune to ~0.5%/game-day) and corp accounts. Invariants enforced in one place (`core.economy`): balances never negative, goods conserved, every mutation inside a transaction.

**NPC traders.** Friendly-disposition merchant ships are Ferengi-style mobile arbitrageurs (twclone model): they roam nearby sectors, compare port prices, execute real trades that move real stock and latinum, and hold persistent cargo/cash under their species' corporation. They are the economy's circulation system, and trading alongside them builds attitude with that species.

---

## 10. Time, Turns, and the Engine

Per the original TWINSTR.DOC rules: players get N turns per game-day (default 250, config); each warp move costs turns per the ship's `turns_per_warp`; docking costs 1. The engine (`engine.ticker`, an asyncio task) implements twclone's two-level scheduling: a short tick (default 1 s real time) that consumes the event log, steps NPCs in bounded batches, and runs sweepers; plus durable cron tasks — `daily_turn_reset`, `hourly_port_economy`, `planet_growth`, `interest_accrual` — with persisted `next_due_at` so a reloaded save never double-runs or skips a tick. In single-player, game time can be configured to advance only while playing, or in real time.

---

## 11. Encounters, Combat, and Territory

**Alien encounters.** Moving through or lingering in inhabited territory rolls for encounters from the region's alien species table, with weights inverse to threat rating (Section 7): common raiders harass the Frontier; the apex species of the Void are rarely seen and never forgotten. The encounter is spawned as a **group** per the species' `pack_behavior`/`escort` (§7) — a lone hunter, a warship shadowed by a screen of fighters, a swarm in numbers, a colonial cluster — so the same `threat_rating` can present very differently. Whether a given encounter opens peacefully or with violence is then rolled against the species' effective disposition (Section 7), further shifted by any active **grudge** the species holds against the player and by **alliance standing** (a fellow-member greets warmly; a rival-bloc member is primed to attack) — a high-disposition species greets the player and offers trade, a low-disposition one attacks on sight, and the wary middle is a genuine coin-flip. A `combatant=false` species can never reach violence; its "threat" is delivered through diplomacy (a `signature_mechanic`, §7.2) instead. A hostile-turning encounter opens with a detection check — the species' sensors against the player's cloak rating plus any nebula cover; an undetected player may slip away freely, making stealth a genuine alternative to firepower. Once engaged, each round the player chooses **fight** or **flee**. Weapon **firing arcs** (§5) shape the fight: an `ahead`/`spinal` attacker is evaded by maneuvering out of its firing line (the classic counter to a fast hull with a deadly forward gun), while `all_round` armament leaves no safe angle; weapon `special`s (engine-flux, proton-stalker pods) impose their own counters. Flee success is a function of base chance, the player's engine speed minus the species' interception rating, cloak rating, and accumulated hull damage — and is *clamped to a configured floor (default 10%)*, so escape is always possible even in a crippled ship; this floor is a core invariant with its own property test. A failed flight attempt costs one round of incoming damage at the species' threat rating. Shields absorb damage before hull; ship destruction drops the player to an escape pod if owned.

**Classic stack (Phase 3).** Sector fighters: deployable in offensive/defensive/toll modes; entering a hostile-fighter sector forces engagement or retreat (retreat costs one fighter — the original rule). Mines (Armid/limpet split deferred to Phase 5) damage on entry with deflector mitigation. Ship-to-ship combat resolves in rounds: attacker commits fighters, hit ratios derive from ship-type odds multipliers and percentile rolls (BNT's shape), shields absorb first, destroyed ships yield 10–20% cargo salvage (BNT). Defensive devices: emergency warp (random-sector escape on trigger); cloak doubles as the pre-engagement stealth stat above.

**Territory and law.** The Core Space is combat-free and deployment-free, hosts only friendly-band members of its governing alliance, and that alliance's forces punish criminal alignment there — *for those in good standing with the governor*. The Core's sanctuary follows whoever currently governs it (`Game.core_governing_alliance_id`, §7.3), not the Federation by name: a player who has joined an alliance the governor counts as a rival is treated as an enemy on entry, and the governor's forces engage them on sight, denying the home banking/trade/resupply haven until that allegiance is given up and amends are made. At game start the governor is the Federation and the player is one of its members, so the Core is home; should governance change hands (§7.3), this same rule re-evaluates against the new governor. Hostile-disposition species defend their home regions and occasionally raid trade lanes near the band boundary; raiding *their* homeworlds for legendary-tier technology caches is the single-player long game, with bounties per hostile fighter destroyed echoing the Cabal's 100/kill. Attacking any species' ships drives its attitude offset down — souring effective disposition and locking away tech offers — so piracy has a price even against peoples who greeted you warmly; against a `betrayal_model=permanent` species a single betrayal floors that offset for good (§7.5).

**Starbases and alliance warfare.** A species' starbase (§5) is a `role=starbase` hull — immobile, shielded, armed — placed per its `starbase_policy` (a defended homeworld, scattered secret bases, or none for nomads). Assaulting one is a set-piece combat against fixed defenses, and it is the coin of diplomacy: most alliance `admission_price`s and `contract_kill` mechanics are paid in razed rival starbases (§7.2, §7.3). Razing a base therefore raises standing with the patron that demanded it while driving the target species — and its alliance and friends (§7.4) — toward permanent hostility. **Joining an alliance** (§7.3) is itself a territory commitment: members' sectors become safe to transit while rival-bloc space turns hostile, and breaking a member no-attack obligation voids the membership. This is the spine of the single-player endgame — every "befriend X / raze Y" choice reshapes which regions are open and which are now hunting you.

---

## 12. Textual UI

Textual gives us screens, CSS layout, widgets, mouse support, and free web deployment via `textual serve`. The design honors TW2002 muscle memory while exploiting modern widgets.

**Screen map.** `MainMenu` → `Game` (the primary screen) with modal/pushed screens: `PortScreen`, `PlanetScreen` (orbit view → `SurfaceScreen` for descent and site-by-site exploration), `StarDockScreen` (shipyard/hardware/bank/tavern tabs), `AlienContactScreen` (greeting, tech offers, latinum purchase and artifact barter, treaty/alliance negotiation and admission-price tasks), `EncounterScreen` (greeting or fight/flee rounds, depending on the species' effective disposition), `ComputerScreen`, `MapScreen`, `MessagesScreen`.

**Game screen layout.** Three regions. Left 2/3: the sector view — region name, sector number, ANSI-art flavor header, contents (ports, planets, ships, fighters, beacons) as a Rich-renderable log, and a clickable `WarpList` widget showing outbound warps (unexplored ones dimmed with `?`). Right 1/3: status sidebar — ship name/type, aspect readout (shields, engine speed, cloak, sensors), holds bar (per-commodity fill), fighters/armaments, latinum, turns remaining, current distance band, current region mini-map (explored neighbors as a small node diagram). Bottom: a one-line command input plus a scrolling event ticker.

**Command grammar.** Single-keystroke commands matching TW2002 where it matters — number keys warp by sector number, `M` move (prompt for sector), `P` dock at port, `L` land on planet, `D` re-display sector, `C` computer, `T` corporate/team menu, `G` galactic map, `I` ship info, `Q` quit — implemented as Textual key bindings with an Esc-cancelable prompt model (terminal-space's InstantCmd concept, replaced by Textual's native bindings + Input). Every keystroke action also has a clickable affordance.

**Computer screen** bakes in what the community bolted onto real TW2002 via TWX Proxy/twstak-class tools: explored-universe map (Tree/DataTable), port directory with last-seen stock and class, *pair-trade finder* (scores opposed-class port pairs by round-trip profit per turn using current price model and shortest-path distance), *route planner* (shortest path with one-way awareness; sends the ship hop-by-hop with per-sector hazard confirmation), *discovery codex* (every find logged with location, rarity, and lore fragments; collected log fragments surface as rumor pins on the map), *alien dossier* (known species, disposition, attitude, alliance and player standing, active grudges, last-seen tech offers, and a threat-tier bestiary that — per §7.6 — a chosen faction can be configured to narrate), and notes/avoid lists. Since we own the engine, these are first-class queries rather than screen-scrapers.

**Aesthetics.** A `tw2002` Textual theme: cyan/yellow/magenta on black, CP437-flavored box drawing, optional CRT-ish flourishes (subtle starfield animation on the title screen — terminal-space's terminaltexteffects idea, reimplemented with Textual animation primitives). A `--plain` flag disables effects.

---

## 13. Persistence

SQLite, one file per game (`~/.helix/games/<name>.db`), WAL mode. Tables mirror Section 5 entities plus `event_log` and `config`. Saves are implicit (every command is durable once its transaction commits — the BBS property that you can hang up mid-session and resume, per TWINSTR.DOC). `snapshots.py` adds export/import of a portable save (gzipped JSON of state + command log). The repository interface is the swap point for PostgreSQL if hosted multiplayer ever demands it (twclone's lesson, pre-paid architecturally rather than adopted prematurely).

---

## 14. Testing Strategy

The pure core makes this cheap: property-based tests (hypothesis) for economy invariants (no negative balances, goods conservation under arbitrary trade sequences, price monotonicity in stock) and for encounter invariants (flee probability never below the configured floor under arbitrary damage/engine/interception combinations; hostile encounter weight inverse to threat rating); golden-master tests replaying recorded command logs against fixed seeds and asserting final state hashes; bigbang validation tests across 100 seeds (connectivity, port-pair reachability, degree caps, the Core Space and Hub band hosting only friendly-band members of the initial governing alliance (and none from a rival bloc), mean alien disposition non-increasing across distance bands, discovery rarity and value monotonically increasing across distance bands, roster integrity — every `alliance_id`/`membership_gate`/`fleet`/`signature_mechanic` reference resolves, the inter-species relation matrix is consistent with alliance membership except where explicitly overridden, and each alliance `admission_price` names valid rival targets); and Textual's `Pilot` test harness for UI flows (dock → haggle → buy → warp; descend → explore site → log discovery). NPC AI is tested by running headless bot-vs-engine simulations — twclone's `ai_player` bug-report harness shows how productive bot-driven QA is for this genre, and our service API is bot-friendly by construction.

---

## 15. Roadmap

**Phase 1 — Walking skeleton.** Core models, bigbang (cluster+bridge+distance bands+validate), movement with turn costs, port docking and trading with live pricing and haggling in latinum, SQLite persistence, Textual game screen with sector view/warp list/status bar/port screen. Playable trading game, single ship type. *Exit criterion: profitable pair-trading loop is fun for 30 minutes and visibly funds a first ship upgrade.*

**Phase 2 — Exploration & discovery.** The pivot phase. Discovery system with distance-banded rarity tables (wrecks, nebulae, black holes, entities), planet descent with surface sites (ruins, artifacts, ancient tech, crashed ships), sensor-based detection of hidden finds, discovery codex; friendly-disposition alien species with tech levels, contact screen, latinum sales and artifact barter for aspect upgrades (engine/shields/sensors/cloak/holds); StarDock (shipyard, hardware emporium, bank), multiple ship types from config, planets with BNT production model, Genesis torpedoes, Computer screen with pair-trade finder and route planner. *Exit criterion: a one-hour push-out-and-return exploration run is fun and yields tech that trading alone could not buy.*

**Phase 3 — Danger.** Low-disposition (hostile-band) alien species with threat/interception ratings, threat tiers, and rarity-inverse encounter weights, the encounter system (disposition roll for greeting vs. violence, escort/pack spawns, firing-arc-aware combat, detection, fight/flee rounds, escape-probability floor), ship combat with salvage and escape pods, NPC starbases as destructible set-pieces, black hole and entity hazards live, sector fighters (off/def/toll), mines, alignment/experience, Core Space law keyed to the governing alliance (static Federation governor in this phase, with Core safety already driven by the player's standing with the governor), attitude-offset consequences on effective disposition, signature-mechanic hooks, alliances (join one bloc, admission-price tasks, rival-bloc fallout) and inter-species relations/grudges, friendly-disposition NPC traders moving real goods, hostile homeworld raids with bounties. *Exit criterion: the outer bands feel scary but irresistible; players quote their narrow escapes, and committing to one alliance visibly remakes the map.*

**Phase 4 — Multiplayer.** Extract `server.net` (JSON-RPC over websockets, Pydantic DTOs already in place), lobby/auth, corporations with shared assets and corp bank, broadcast pipeline, `textual serve` hosted client.

**Phase 5 — Depth.** Order-book market economy (twclone Phase-4 model), citadels and planetary combat, **dynamic governance of the Core Space** (a `covets_core` alliance seizing control via player-championed conquest or NPC expansion, flipping `core_governing_alliance_id` and re-keying who is welcome there), probes/interdictor, richer alien interactions (favors, escort contracts), tavern/noticeboard, sysop console (AAT's admin catalog as the menu), TWX-style scripting hooks for bots.

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
