# Phase 1 — Walking Skeleton: Implementation Plan

> Companion to `DESIGN.md` §14. DESIGN is the authoritative *what*; this is the
> *how and in what order*. Where the two ever disagree, DESIGN wins and this doc
> is corrected in the same change.

## 1. Goal & exit criterion

Build the bottom of the layered stack for real and wire the existing Textual
skeleton to it, replacing the hard-coded fixtures in `edge/tui/dummy.py` with a
live in-process `GameService`.

**Exit criterion (DESIGN §14):** a profitable pair-trading loop is fun for 30
minutes and *visibly funds a first ship upgrade*. Single ship type.

**In scope:** core models, the §8 economy (pricing + haggling + banking), the
big bang (cluster+bridge+distance-bands+validate, Core Space sectors 1–10,
StarDock placement), movement with turn costs, SQLite persistence, the engine
tick loop (turn reset / stock regen / interest), and the Game / Port / StarDock /
Computer(Trade) / Map screens running on real state.

## 2. Scope discipline — what Phase 1 deliberately defers

The skeleton already shows screens for Phase 2–3 features. Phase 1 leaves those
on dummy data and does **not** build their engines:

- **Aliens, alliances beyond a Federation stub, encounters, combat, discovery,
  planet descent/surface sites, NPC traders** — Phase 2–3. The big bang seeds a
  single `Federation` alliance as `core_governing_alliance_id` and the player as
  its member (cheap, and the Core-carve needs it); it does **not** seed other
  blocs, home clusters, hostile species, or discoveries yet.
- **Engine-room subsystems/components (§4.1)** — Phase 2. In Phase 1 the player
  ship carries **flat aspect scalars** (holds, shields, warp speed, combat speed,
  cloak, sensors, hull); the status sidebar's integrity line is a static
  "subsystems: all nominal". `EngineRoomScreen` stays on sample data.
- **Planet production/ownership (§4.2)** — Phase 2. Planets are seeded as
  navigational/scene objects with a `planet_type` only; no colonists, yields, or
  ownership math. `PlanetScreen`/`SurfaceScreen` stay on sample data.
- **`AlienContactScreen`, `EncounterScreen`, `MessagesScreen`** — stay on dummy
  data (ship-hail clicks and `G` still open them for demo, reading samples).

### The "first upgrade" decision

The exit criterion needs a latinum sink the player can save toward, but the real
slotted-component model is Phase 2. **Decision:** Phase 1 ships a single
flat-aspect StarDock **Hardware** purchase priced at the §8 Tier-I default
(~2,000 latinum, against 2,000 starting capital) that bumps **one flat ship
aspect**. The two candidate aspects are **cargo holds** and **shields**; which
one (or both, as separate SKUs) is offered is a **config value**, so it is
trivially switchable and not baked into code. **Default: a cargo-holds
expansion** — more holds compounds the trade loop directly (bigger runs → more
profit per turn), which is the clearest demonstration of the exit criterion;
**shields** is the config-selectable alternative.

This keeps Phase 1 honest to "single ship type" while satisfying the exit
criterion; Phase 2 replaces the flat bump with the engine-room slot fill, and the
`BuyUpgrade` command (WP3) carries forward — only its effect changes from
"raise an aspect scalar" to "install a component in a slot."

## 3. Layout to create

```
edge/core/      enums.py models.py economy.py movement.py events.py rules.py  dto.py config.py
edge/bigbang/   generator.py topology.py populate.py validate.py
edge/store/     repo.py schema.sql snapshots.py
edge/server/    service.py session.py
edge/engine/    ticker.py port_economy.py
tests/          test_economy.py test_bigbang.py test_replay.py test_movement.py test_tui_flow.py
config/         default.yaml   (economy constants, bigbang params, turns-per-day, ship class)
```

`combat.py`, `aliens.py`, `discovery.py`, `encounters.py`, `planets.py`,
`engine/planet_growth.py`, `engine/npc.py`, `server/net.py` are **not** created
in Phase 1.

## 4. Work packages

### WP0 — Scaffolding & test harness
- Create the `core` / `bigbang` / `store` / `server` / `engine` packages + `tests/`.
- Dev deps (DESIGN §15): `pytest`, `hypothesis`, `pytest-asyncio`. Add a
  `pixi run test` task. Add `[tool.mypy]` with `strict = true` scoped to
  `edge/core` and `edge/bigbang`; extend `ruff` to the new packages.
- `core/config.py`: **Pydantic v2** models for game constants; `config/default.yaml`
  holds the §8 economy constants, §5 bigbang params, §9 turns-per-day (250), and
  the single Phase-1 ship class. (Pydantic for config/DTOs; core entities stay
  plain dataclasses per §4.)

### WP1 — `core/enums.py`, `core/models.py`, `core/dto.py`
- **Enums:** `Commodity` (FUEL_ORE/ORGANICS/EQUIPMENT), `PortClass` (the 8 buy/sell
  triples + StarDock Class 9), `PortMode` (BUY/SELL).
- **Models** (frozen dataclasses, no I/O): `Game` (id, seed, day_number,
  core_governing_alliance_id), `Region`, `Sector` (warps_out, beacon_text,
  is_galactic_core, distance_band), `Port` (per-commodity {stock, capacity, mode,
  base, delta}, latinum, size, class), `Planet` (type + name only), `Ship`
  (flat aspects + hull + holds/cargo + latinum-independent gear counts),
  `Player` (latinum, bank_balance, turns_remaining, explored_sectors, alliance_id,
  ship_id), `Alliance` (Federation stub). A `UniverseState` container owns the
  seeded `random.Random` and the runtime **adjacency dict** (networkx is
  generation-only, §15).
- **`core/dto.py`:** the public projection shapes — keep them **structurally
  identical to today's `edge/tui/dummy.py`** so the TUI is the contract and widget
  code is untouched. `to_public(context)` lives at the server boundary (WP6).

### WP2 — `core/economy.py` (the heart; property-tested)
- `stock_ratio = stock/capacity`, `capacity = size × 1000`.
- Pricing per the **normative §8 formula** (sell-side lowers, buy-side raises —
  negative feedback), with per-commodity `elasticity` and a **clamp** to
  `[floor_frac×base, ceiling]`, `floor_frac=0.25`, prices always > 0.
- Trade resolution: buy/sell qty, **mint/burn** latinum (faucet/sink — latinum not
  conserved; goods are), enforce no-negative-balance + goods-conservation, return
  events; every mutation transactional.
- Haggling mini-game (pure, seeded): quote → counter → acceptance prob falling with
  distance-from-fair + recent history; 2 rejections → final price; >~30% off → abort.
- Banking: deposit/withdraw + interest calc (~0.5%/game-day); applied by engine cron.
- Stock-regen helper (5% toward desired: 50% standard / 90% StarDock) — pure;
  the engine calls it.

### WP3 — `core/movement.py`, `core/events.py`, `core/rules.py`
- **movement:** warp legality (target ∈ `warps_out`), `turns_per_warp` cost, dock
  cost 1, `explored_sectors` update, BFS shortest path for the route planner.
- **events:** immutable `Event` dataclasses (Arrived, Docked, Traded, Haggled,
  BankTxn, TurnsReset, StockRegen…) — the durable facts.
- **rules:** `Command → (state_delta, [Event])` reducers, the **only** state
  mutators. Commands: `Warp`, `Dock`, `Trade`, `HaggleOffer`, `Deposit`, `Withdraw`,
  `BuyUpgrade`. Delegate invariants to economy/movement.

### WP4 — `bigbang/` (deterministic from `(seed, config)`)
- **generator.py:** cluster pass (groups 5–25, intra-group degree ≈ 2.5), bridge
  pass (1–5 inter-group links, `one_way_chance=0.15`). Build with networkx, then
  freeze to a plain adjacency dict.
- **topology.py:** light motif pass (a few tunnels/deadends — rings optional in P1),
  **Core Space carve** (sectors 1–10 interlinked around Terra, guaranteed exits),
  **distance bands** (BFS hop-distance from sector 1, bucket per config).
- **populate.py:** StarDock (Class 9) 2–5 hops from Core; standard ports at ~45%
  density with the terminal-space 20/20/20/10/10/10/5/5 class split, initial stock
  `randint(200,2000)×size`; planets ~25% (type only). Seed the Federation alliance
  + player as member. *(Alien/home-cluster/discovery/ownership seeding deferred.)*
- **validate.py — Phase-1 subset of §5 step 8 / §13:** single strongly-reachable
  component from sector 1 (one-ways respected), max warps/sector ≤ 6, StarDock
  reachable, **≥ 1 profitable opposed-class port pair within 5 hops of Core**,
  per-region port-class balance within tolerance. Regenerate with a perturbed
  sub-seed on failure (bounded retries, then error).
- **`edge bigbang --inspect`** dev tool: networkx/matplotlib graph dump with port
  sectors highlighted.

### WP5 — `store/` (SQLite, WAL, one file per game)
- `schema.sql`: tables mirroring the Phase-1 entities + `event_log` + `config`.
- `repo.py`: Repository **interface** (the Postgres swap point) over `sqlite3`;
  load/save entities, append event, read command log.
- `snapshots.py`: full save/load; gzipped-JSON export of `(seed + command log)`
  for portability and as the golden-master input.
- Implicit save: a command is durable once its transaction commits.

### WP6 — `server/` (in-process service)
- `service.py`: `GameService.apply(command)` → validate against session →
  `core.rules` reducer → persist events → fan out public deltas. Owns `GameState`
  + the seeded RNG; single-player embeds it in-process.
- `session.py`: `SessionContext` + **fog-of-war `to_public(context)`** (strip
  unexplored warps, unseen port stock) emitting the WP1 DTO shapes.

### WP7 — `engine/` (asyncio ticker, minimal)
- `ticker.py`: short tick consuming the event log + durable cron tasks with
  persisted `next_due_at` (no double-run/skip on reload): `daily_turn_reset`,
  `hourly_port_economy` (→ `port_economy.regen`), `interest_accrual`. Single-player
  config: advance game time only while playing, or real time. `planet_growth`/`npc`
  deferred.

### WP8 — TUI wiring (retire `dummy.py` as the data source)
- `EdgeApp` instantiates `GameService` in-process + a background ticker task; a
  New-Game flow (seed / universe size) runs the big bang.
- Replace the `sample_*` calls with adapters over `service.to_public()`. Because
  the DTO shapes match `dummy.py`, widget changes are minimal.
- Wire real commands: number-key/warp-grid → `Warp`; `P` → `Dock`; `TradePanel`
  buy/sell + haggle → `Trade`/`HaggleOffer`; bank tab → `Deposit`/`Withdraw`;
  StarDock Hardware → `BuyUpgrade`. Live sidebar + event ticker fed by real events.
- Out-of-scope screens (Planet/Surface/Engine/Contact/Encounter/Messages) keep
  reading samples.

### WP9 — Tests (woven through; obligations per DESIGN §13)
- **Economy (hypothesis):** no negative balances; goods conserved over arbitrary
  trade sequences; price monotonic in stock; clamp within `[floor, ceiling]` and
  never ≤ 0; the negative-feedback rule (buying never lowers / selling never raises
  the quoted price).
- **Big bang (100 seeds):** connectivity, port-pair reachability, degree ≤ 6.
- **Golden-master replay:** record a command log against a fixed seed; assert the
  final state hash.
- **Movement:** turn-cost accounting, warp legality, shortest path.
- **TUI (Textual Pilot):** dock → haggle → buy → warp on the real service.

## 5. Milestones (suggested order)

1. **M1 — Provable economy.** WP0 + WP1 + WP2 + economy property tests. The
   pricing/trade/haggle/bank rules are correct in isolation, no universe needed.
2. **M2 — A valid galaxy.** WP4 + bigbang validation tests; `--inspect` renders it.
3. **M3 — Headless game.** WP3 + WP5 + the golden-master harness: warp/dock/trade
   via commands, save, reload, byte-identical replay from `(seed, command log)`.
4. **M4 — Living service.** WP6 + WP7: an in-process service with a ticking economy
   (turns reset, stock regenerates, interest accrues).
5. **M5 — Playable.** WP8 + the Pilot flow test, then resolve the "first upgrade"
   decision (§2) and run the 30-minute exit-criterion playtest.

## 6. Risks & decisions

- **DTO duplication.** `dummy.py` shapes become `core/dto.py`. Keep them dataclasses
  (not Pydantic) to avoid reworking widget code; Pydantic is for config only in P1.
- **"First upgrade" (§2).** A config-driven flat-aspect StarDock Hardware
  purchase (~2,000 latinum), default **cargo-holds expansion**, shields as the
  config alternative. The `BuyUpgrade` command survives into Phase 2 unchanged;
  only its effect swaps to a component slot-fill.
- **Determinism surface.** Every random draw — bigbang and runtime — must flow
  through the one `GameState` RNG, or golden-master replay (our save-integrity
  check) breaks. Audit for stray `random.*` calls.
- **Engine/RNG/asyncio.** The ticker mutates state on a background task; route all
  mutations through `core.rules` under the store transaction so ticks and commands
  can't race or desync the replay.
