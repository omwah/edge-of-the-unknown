# Phases 5 & 4 — Depth, then Multiplayer

> Companion to `DESIGN.md`, `PHASE1_PLAN.md`, `PHASE1_5_PLAN.md`, `PHASE2_PLAN.md`,
> `PHASE2_ROUTE_FOLLOWUP.md`, and `PHASE3_PLAN.md`. DESIGN is the authoritative
> *what*; this is the *how and in what order* for the remaining two phases. Where
> the two disagree, DESIGN wins and is corrected in the same change (CLAUDE.md).
>
> **Execution order: Phase 5 (Depth) is built first, Phase 4 (Multiplayer)
> second.** DESIGN §14 numbers them the other way; WP45 lands the §14 note
> recording this reorder and why (below). Phase numbering is *identity*, not
> *sequence* — commits stay tagged `p5:` / `p4:` by content.
>
> **Status: reviewed draft — interview decisions resolved (July 2026).**

## Context

Phase 3 shipped complete (WP19–WP44, milestones M10–M15, full suite green): both
big-bang topologies, hostile-band species, the encounter/combat stack with
localized component damage and the ≥10% escape floor, conversation depth, the
Entity, signature mechanics, joinable alliances over real home-cluster
territory, starbase set-pieces with repair→claim→foothold, sector
fighters/mines/beacons, goal-directed NPC movement, NPC traders moving real
goods, and homeworld raids with bounties.

Every Phase-5 seam was left deliberately and is verified against the code
(July 2026):

- `Port.latinum` is stored and minted/burned against, but **never read as a
  constraint** — the §8 "soft accounting figure" that Phase 5 hardens into a
  real, drainable pool under the order book.
- `engine/port_economy.py::regenerate_ports` is the blind 5%-toward-desired
  drift the order-book market replaces.
- `Game.core_governing_alliance_id` is **read everywhere and written nowhere**
  after generation: `core.aliens.governor_hostile`, `may_occupy`, Core law
  (`rules._core_law_events`), and Core-planet ownership all key off it, so a
  governance flip only has to *write* one field and re-key the derived
  holdings — exactly the seam WP38 promised.
- `Alliance.covets_core` / `AllianceConfig.covets_core` are authored hints,
  inert by design ("may seize the Core in Phase 5").
- `Planet.citadel_level` exists on the model and in the §4 table but is
  **written nowhere and read nowhere** — a bare field awaiting WP54.
- The StarDock screen ships placeholder `Bank`-style panes:
  `TabPane("Tavern")` literally says *"Rumors & contracts — Phase 5"*.
- `RepairStarbase`/`ClaimStarbase` end at "operational, player-owned";
  DESIGN §4.2 explicitly defers *forward-base services* (refuel / repair /
  banking at the foothold) to Phase 5.
- The Armid/limpet mine split, probes/interdictor, favors/escort contracts,
  the sysop console, and scripting hooks are all named Phase-5 items in §14
  and §10 with no code presence.

Phase 4's seams are equally deliberate: `JoinGame` is an ordinary logged
command (a second player joins the same universe by appending their own),
every projection in `server/session.py` takes a `player_id` and enforces fog
of war at the boundary, `GameService.apply` is the single entry point, and
`store/codec.py` already round-trips every command as JSON. What Phase 4 must
*add* — a wire, sessions, auth, corporations, broadcast — is additive around
that spine.

**Interview decisions (July 2026).** Eleven open decisions were resolved by
design interview; each is folded into the WPs below and marked at the point
of use:

1. **NPC Core seizure** ships enabled by default at a low background chance,
   gated on the incumbent's Core bases already being weakened (WP51).
2. **Citadel construction is a timed build** — paid up front, advancing in
   colonist-days on the planet-growth cron; not lootable while building
   (WP54).
3. **Phase 4 ships full PvP** — attacker-driven (TW2002 classic): the
   attacker submits combat rounds; the defender's ship fights back
   automatically from its derived aspects whether or not that player is
   online (new WP67).
4. **PvP limits:** Core sanctuary extends to players, and a per-game
   `pvp` config toggle lets a host run a cooperative universe. Deliberately
   *no* newbie protection and *no* same-corp immunity (interview choice —
   corp trust is social, not mechanical).
5. **PvP stakes:** loser drops to an escape pod (the NPC-combat rule);
   victor salvages 10–20% cargo + loose components; the attacker takes an
   alignment hit keyed to the victim's lawfulness, and lawful kills post a
   claimable bounty on the killer (the WP58 board).
6. **Corporations share property + corp war** — an explicit war declaration
   flags rival members/assets mutually hostile; alliance membership and
   attitudes stay per-player (WP66).
7. **Deployed territory engages all non-owner players** per its mode
   (fighters/mines/toll, citadel and base defenses) — TW2002 classic (WP67).
8. **The player never posts orders** — the order book is port-to-port
   logistics the player observes and arbitrages against (WP47/WP48 as
   planned).
9. **Escort contracts complete by convoy warp** — the escorted merchant
   leaves the drift rail and follows the player's warps; arrival at the
   destination completes it (WP57).
10. **Wire serialization keeps frozen-dataclass DTOs** with an explicit
    hand-written codec mirroring `store/codec.py` (WP62 as planned).
11. **Governance/market defaults confirmed** as planned (WP47/WP51).

**Why Phase 5 first.** (1) The order book, governance flips, citadels, and
contracts all add *hashed state and commands*; landing them before the wire
freezes the protocol surface Phase 4 serializes, so the net layer is written
once against a complete command set instead of chasing churn. (2) The sysop
console and scripting hooks (WP59/WP60) produce exactly the admin tooling and
bot harness Phase 4's QA needs (WP69) — building them first makes multiplayer
testable on day one. (3) Single-player depth is the game; multiplayer is a
delivery mechanism for it. WP45 records this rationale in DESIGN §14.

All work obeys the architecture rules in CLAUDE.md: downward-only layer deps
(`core` has no I/O / async / Textual imports), all randomness through the
state-owned RNG (or salted maintenance sub-RNGs on the drift rail), invariants
in core, every constant in config, the TUI only through the `GameService` +
`session` projection boundary. `ruff` + `mypy --strict` stay green on
`core/dialogue/bigbang/store/server/engine`; `tui/` and `devtool/` are exempt.

---

## Scope and non-goals

**Phase 5 in scope (DESIGN §14 Phase 5 + the items §8/§6.3/§10/§4.2 defer to
it):**

1. Order-book market economy (twclone model): ports post buy/sell orders,
   daily settlement matches them and physically moves goods **and latinum**
   between ports; `Port.latinum` becomes a real, drainable pool (§8).
2. Dynamic governance of the Core Space: a `covets_core` alliance seizing
   control via player-championed conquest or NPC events, flipping
   `Game.core_governing_alliance_id` and re-keying everything derived from it
   (§6.3), including the dynamic planet-ownership flips of §4.2.
3. The config-gated leadership-intrigue event (`internal_rival_species_id`
   usurping an alliance's leadership — §6.3 "left to Phase 5").
4. Full forward-base services at player-owned orbital starbases: repair,
   component swap/restock, banking, munitions resupply (§4.2).
5. Citadels and planetary combat: citadel levels with treasury and defense,
   invasion of owned worlds, conquest ownership flips (§14, §A.3 lineage).
6. The Armid/limpet mine split (§10), probes, and the interdictor (§14).
7. Richer alien interactions: favors and escort contracts (§14), issued
   through the §6.7 dialogue system.
8. Tavern/noticeboard at StarDock: rumors (a latinum-for-`Lead` sink), the
   bounty board, player notices (§14).
9. Sysop console (AAT's admin catalog as the menu, §A.4) — dev tooling.
10. TWX-style scripting hooks for bots (§14) — a stable service protocol and
    an event-triggered bot harness.

**Phase 4 in scope (DESIGN §14 Phase 4):**

11. `server.net`: JSON-RPC over websockets, a versioned wire codec for the
    existing commands/events/DTOs.
12. Lobby and auth: accounts, create/list/join/resume games, the
    account↔player binding entering core only as a `JoinGame` command.
13. Corporations: the `Corporation` entity, corp bank, shared assets
    (`Ownership` gains a `corp` kind), the `T` screen.
14. Broadcast pipeline: visibility-filtered event fan-out to live sessions.
15. Hosted client: a `RemoteClient` for the TUI + `textual serve` deployment.
16. **Full PvP** (interview decision 3): attacker-driven ship-to-ship player
    combat reusing the encounter machinery, player-vs-player territory
    engagement, corp war, escape-pod stakes with salvage, and outlaw
    alignment/bounty consequences — bounded by the Core sanctuary and a
    per-game `pvp` toggle.

**Explicitly out of scope (both phases — record a seam, build nothing):**

- PvP *griefing mitigations beyond the Core + toggle*: newbie protection and
  same-corp immunity were considered and deliberately rejected (interview
  decision 4); if live play demands them they are config additions to the
  WP67 gate predicate, not redesigns.
- Both-online interactive PvP duels (turn timers, response windows). The
  attacker-driven model is the shipped design; the hybrid "online defender
  may inject commands" variant is noted as a seam in WP67 and nothing more.
- PostgreSQL. The repository seam (`store/repo.py`) stays the swap point;
  tens of players on SQLite-behind-one-writer is within the §2 design load.
- Federation/lobby of *many* servers, matchmaking, web accounts.
- Mobile/browser-native clients beyond `textual serve`.
- The stock market / corp shares (twclone protocol catalog) — corporations
  ship with shared bank + assets only.

---

## Framing corrections (found against the code, July 2026)

Items the DESIGN §14 wording implies exist but do not; each is folded into WP
scope below and corrected in DESIGN by WP45/WP61:

1. **"Pydantic DTOs already in place" is wrong.** `edge/core/dto.py` is
   explicit *frozen dataclasses* (chosen for the strict-mypy, zero-dependency
   core; Pydantic is config-only today). Phase 4 does **not** convert them:
   WP62 adds an explicit wire codec (`server/wire.py`) mirroring the proven
   `store/codec.py` style instead. DESIGN §3/§14/§15 wording is corrected by
   WP61.
2. **`Corporation` exists only in the §4 table.** No model, no store, no
   command touches corps. WP66 *adds* the entity rather than consuming it.
3. **`Planet.citadel_level` is dead weight** — never read or written; there
   is no treasury field, no planetary garrison field (`Planet.stores` maps
   the commodity trio only; the §4 table's `fighters` store was never
   realized). WP54/WP55 add `fighters` and `treasury` for real.
4. **There is no `engine.npc` module** as the §3 tree sketches — NPC planning
   lives in `edge/core/npc.py` scheduled from `engine/cron.py` (the H8
   decision). Phase 5 keeps that shape; new background behavior is a pure
   core planner plus a cron entry, never engine-resident logic.
5. **`GameService` is synchronous and single-writer by construction** (one
   in-process caller; SQLite WAL commits per append). That is an *asset*:
   Phase 4 preserves it by marshalling all sessions through one asyncio
   queue (H14) rather than making core re-entrant.
6. **`EdgeApp.player_id` is hardcoded `1`** and the TUI calls `GameService`
   methods synchronously. WP61's protocol/facade refactor is what unhooks
   both without rewriting every screen twice.

---

## Cross-cutting: replay, epochs, layering (H10–H18)

The Phase-2/3 golden-master rail still governs: bigbang output is a pure
function of `(seed, config)`; player progress rides the command log (every new
command/event gets `store/codec.py` entries + round-trip tests); any new field
on a hashed entity regenerates golden masters **in the same commit**, batched
per milestone. Phase 3's H1–H9 remain in force (H9 — the dialogue-sync
contract — binds WP57 in particular). Phases 5–4 add nine more, referenced by
number from the WPs:

- **H10 — Market determinism and conservation.** Order generation and
  settlement are **RNG-free** pure functions with canonical iteration order
  (ports by id, commodities by enum order, orders by explicit sort keys).
  Settlement **conserves goods and latinum across ports exactly** (it is a
  transfer, never a faucet); the player-trade faucet/sink of §8 survives but
  becomes **purse-bounded** — a port can never pay out latinum it does not
  hold, and a partial fill is reported honestly (event carries the filled
  quantity). A liquidity drip (config) guarantees the trade loop can never
  deadlock a new player: property-tested, like the escape floor.
- **H11 — A governance flip is one reducer.** Whether triggered by the
  player's petition (a command) or an NPC event (a persisted cron firing),
  the flip and *all* its re-keying — `Game.core_governing_alliance_id`, Core
  planet/starbase owners, incumbent-species eviction — happen inside a single
  `ReduceResult`, so replay can never observe a half-flipped Core. NPC
  governance rolls use a salted sub-RNG + a `Game.governance_seq` counter,
  exactly the `drift_seq` pattern.
- **H12 — Epoch batching.** `config_version 3→4` rides WP47 (market fields +
  port purses change bigbang output); `4→5` rides the M18 batch (citadel /
  garrison / device fields, WP54–WP56); M19's hashed additions (contracts,
  notices) batch into one golden regeneration at WP57; `5→6` rides WP66
  (the `corp` ownership kind). No other WP moves goldens.
- **H13 — Pure-core placement.** New rules logic lands as pure modules:
  `core/market.py`, `core/governance.py`, `core/citadels.py`,
  `core/contracts.py`. `engine/cron.py` only *schedules* them (the H8
  discipline); `server/` only projects; `tui/` only renders. Each new module
  opens with a design-referenced docstring and every dataclass field carries
  a `§`-referenced comment — the inline-documentation contract below.
- **H14 — The net layer is a transport, not a second rules engine.** One
  asyncio task owns the authoritative `GameService` + `EngineTicker`; every
  session's commands are marshalled through **one queue** and applied in
  arrival order (total order preserved — the replay contract's precondition);
  projections run on the same loop between commands. No locks, no threads,
  no re-entrancy in core. `server/net.py` contains zero game rules.
- **H15 — Identity stays out of core.** Accounts, password hashes, and
  session tokens live in a server-side store, never in `UniverseState`,
  never in `state_hash`. A human enters the game state exclusively as a
  `player_id` allocated by a logged `JoinGame` — the §3 contract, unchanged.
- **H16 — One service seam for every consumer.** WP60's `ServiceProtocol` is
  the single typed surface the TUI, bots, the sysop console, and the network
  client all program against. DTOs stay frozen dataclasses (framing
  correction 1); the wire codec is explicit and versioned like
  `store/codec.py`, with golden wire fixtures so a protocol break is a test
  failure, not a runtime surprise.
- **H17 — Dead-field honesty.** A WP that ships a model field must ship its
  reader in the same milestone (the `citadel_level` lesson). Conversely, a WP
  must not add speculative fields for later phases; a seam is a comment and a
  test, not a column.
- **H18 — PvP stays inside the replay contract.** A PvP fight is commands
  from **one** player (the attacker, interview decision 3); the defender's
  side is pure automation over their ship's derived aspects — no second
  command source, so the total order of the command log remains the whole
  story and a PvP fight replays like any other. The defender's *ship* state
  changes ride the attacker's commands' `ReduceResult`s; the defender's
  *client* learns of it only through the WP65 broadcast. The `pvp` toggle
  and the Core sanctuary are enforced **in the reducers** (an `AttackPlayer`
  in a pvp-off game or a Core sector is a rejection), never in the
  transport, so a modified client gains nothing.

**Inline-documentation contract (applies to every WP below).** This project's
plans are executed by different agents at different times; the code must carry
its own spec. Concretely: (1) every new module opens with a docstring naming
the DESIGN sections it implements and the invariants it owns; (2) every
public function/dataclass gets a docstring stating *what* and *why* (with `§`
references), not just *how*; (3) every config knob gets a field comment with
its default's rationale; (4) every non-obvious algorithm step (settlement
matching, eviction BFS, invasion odds) is commented at the decision point,
constraint-first (per CLAUDE.md's comment discipline); (5) every WP that
changes behavior updates DESIGN.md in the same change (CLAUDE.md rule), and
every WP touching dialogue schema/vocabulary honors H9's three-place sync.

---

## Milestones

Phase 5 (executed first):

- **M16 — The living market.** WP45–WP48. The order book: ports post orders,
  daily settlement moves real goods and latinum between ports, purses become
  drainable, the Computer gains a market view. *Playable throughout: the
  player's own trading UX is unchanged — the world's economy starts moving
  under it.* One config epoch (`config_version 4`) at WP47.
- **M17 — The Core changes hands.** WP49–WP52. The governance-flip reducer,
  the player-championed seizure path, NPC governance/leadership events, and
  the aftermath surfacing. *Playable: championing a `covets_core` bloc can
  hand you a safe Core under a new flag — or cost you your homeland.*
- **M18 — Footholds, citadels, planetary war.** WP53–WP56. Forward-base
  services, citadel levels with treasuries, invasion/conquest of owned
  worlds, the Armid/limpet split, probes, interdictor. One config epoch
  (`config_version 5`) batched at WP56.
- **M19 — A social galaxy.** WP57–WP60. Favors and escort contracts through
  dialogue, the tavern/noticeboard, the sysop console, scripting hooks, and
  the Phase-5 exit balance pass. Golden batch at WP57.
- Phase-5 exit criterion (proposed for DESIGN §14, landed by WP45): *the
  galaxy no longer waits for the player — prices move, governments fall, and
  a deep-space foothold feels like home.*

Phase 4 (executed second):

- **M20 — The wire.** WP61–WP64. The service protocol + async facade, the
  wire codec, the websocket JSON-RPC server with single-writer discipline,
  and lobby/auth. *Playable: single-player is byte-identical; a second
  terminal can join the same universe over localhost.*
- **M21 — A shared galaxy.** WP65–WP69. Broadcast fan-out, corporations with
  corp war (`config_version 6` at WP66), full attacker-driven PvP (WP67),
  the hosted client, and multiplayer QA with bot swarms. *Phase-4 exit: two
  humans and a bot trade, explore, and share a corp planet in one universe
  hosted via `textual serve` — and a grudge is settled by force outside the
  Core.*

---

## M16 — The living market

### WP45 — Spec deltas: DESIGN.md + this plan (S/M)

Land the DESIGN edits this plan assumes, in the same change as the plan
itself, plus the AGENTS.md roadmap touch-up. **Shipped (the commit that
landed this plan).**

- **§14:** record the execution reorder (Phase 5 built before Phase 4) and
  its rationale (protocol freezes before the wire; sysop/bot tooling feeds
  multiplayer QA); add the Phase-5 exit criterion above; correct the Phase-4
  bullet's "Pydantic DTOs already in place" to "frozen-dataclass DTOs +
  an explicit versioned wire codec".
- **§8:** the order-book model made normative: order generation from
  desired-stock gaps at §8-formula limit prices, daily settlement as a
  conserving transfer of goods and latinum between ports, purse-bounded
  player trades with partial fills, the hinterland drift + liquidity drip
  (the residual faucet/sink), and the revised faucet/sink table.
- **§6.3:** governance-flip mechanics: the seizure ledger, the petition
  command, NPC seizure conditions, the leadership-intrigue event, and the
  full re-key list (planets, bases, species eviction, law, StarDock hub).
- **§4.2:** forward-base services (config-gated service set at player-owned
  operational bases); citadel levels, treasury, and the planetary-combat
  ladder (raze base → silence citadel → ground assault); dynamic ownership
  flips following governance changes marked implemented.
- **§10:** the Armid/limpet split, probe mechanics, interdictor; §4 table
  rows for the new fields (`Planet.fighters`, `Planet.treasury`,
  `Player.contracts`, `state.port_orders`, `state.notices`,
  `Game.governance_seq`).
- **§13:** the new invariants — settlement conservation, purse non-negativity
  + liquidity floor, single-reducer governance flips, invasion-ladder
  ordering, contract determinism.

Files: `docs/DESIGN.md`, `docs/PHASE5_4_PLAN.md` (this file), `AGENTS.md`.
Tests: none (docs). Commit `p5: WP45 phase-5/4 spec deltas + plan`.

### WP46 — Market core: orders and settlement, pure (M/L)

**New module `edge/core/market.py`** — the order book as pure math, no I/O,
no RNG (H10). Contents:

- `PortOrder` (frozen dataclass): `port_id`, `commodity`, `side`
  (`"buy"`/`"sell"`), `qty`, `limit` (per-unit slips). One order per
  `(port, commodity, side)` maximum — regeneration *replaces* a port's open
  orders each cycle, so the book is bounded by `3 × 2 × n_ports` and
  idempotent under repeated generation (no unbounded growth, no stale
  orders).
- `generate_orders(state, config) -> dict[int, tuple[PortOrder, ...]]`:
  for each port line, `desired = desired_frac × capacity` (the existing
  twclone ratios). A **shortage** (`stock < desired × (1 − band)`) posts a
  BUY for the gap at `limit = quoted_unit_price(line)` — the §8 formula at
  current stock, i.e. the port bids its own current fair price. A **surplus**
  (`stock > desired × (1 + band)`) posts a SELL for the excess at the quoted
  ask. `band` (config `market.order_band`, default 0.10) is the dead zone
  that stops the book churning around equilibrium. A BUY is additionally
  clamped so `qty × limit ≤ port.latinum` — a port never bids money it does
  not hold.
- `match_orders(orders, ports, config) -> Settlement`: per commodity (enum
  order), sort BUYs by `limit` descending then `port_id` ascending, SELLs by
  `limit` ascending then `port_id` ascending; greedily match while
  `buy.limit >= sell.limit`; `fill = min(buy.qty, sell.qty, buyer purse //
  price, seller stock, buyer capacity headroom)` at the midpoint price
  `(buy.limit + sell.limit) // 2`. Emit a `Settlement` (frozen) of per-port
  stock deltas, per-port latinum deltas, and per-match records for the event
  log. The function asserts its own conservation (sum of stock deltas = 0
  per commodity; sum of latinum deltas = 0) — the H10 invariant lives *in*
  the module it guards.
- `hinterland_drift(line, config) -> int`: the residual non-market
  faucet/sink — the old `regenerate_stock` at a much smaller
  `market.hinterland_frac` (default 0.01 vs the legacy 0.05), representing
  each port's off-map hinterland producing/consuming. Without it a closed
  book starves (every port converges and trade halts); with it the market
  has a gentle external gradient to arbitrage. Documented as such in the
  module docstring.
- `liquidity_drip(port, config) -> int`: tops a port's purse up toward
  `market.min_purse` (default `size × 200`) by `market.drip_frac` per day —
  the §8 faucet keeping player selling viable everywhere (H10's no-deadlock
  guarantee). Both drifts are deliberately *port-local and deterministic*.

**Config (`edge/core/config.py`, `config/default.yaml`).** New
`MarketConfig` under `EconomyConfig` (`economy.market`): `enabled: bool =
True`, `order_band`, `hinterland_frac`, `min_purse_per_size`, `drip_frac`,
`settle_price: Literal["midpoint"] = "midpoint"` (named so a future policy is
a config value, not a rewrite). Every knob commented with its default's
rationale (inline-doc contract).

**No state/reducer wiring yet** — this WP is the pure engine plus its
property suite, so the math is trusted before it touches the replay rail.

Files: new `edge/core/market.py`, `edge/core/config.py`,
`config/default.yaml`, new `tests/test_market.py`.
Tests (hypothesis-heavy): settlement conserves goods and latinum under
arbitrary books; no fill above purse/stock/capacity; midpoint within
`[sell.limit, buy.limit]`; generation idempotent and RNG-free (two calls,
identical output); the dead band suppresses equilibrium churn; drip never
overshoots `min_purse`; determinism across dict-ordering permutations
(canonical sort proven, H10).
Commit `p5: WP46 order-book market core (pure)`.

### WP47 — Market state, crons, hard purses + the config epoch (M/L)

Wire WP46 into state, the replay rail, and the player's trades.

- **State.** `UniverseState.port_orders: dict[int, tuple[PortOrder, ...]]`
  keyed by port id — **hashed state** (orders are gameplay-visible facts that
  must reconstruct under replay; they are rebuilt by cron firings, which the
  maintenance log replays — the WP12 rail needs nothing new). Codec entries
  for the new event payloads.
- **Crons (`edge/engine/cron.py`).** The durable name
  `hourly_port_economy` is kept (CRONS names are durable — the registry
  comment says so) but its reducer becomes: `market.enabled` ⇒ hinterland
  drift + `generate_orders` (orders upserted into `port_orders`); disabled ⇒
  the legacy `regenerate_ports` body, **byte-identical** (regression-pinned,
  the WP20 trunk pattern). New cron `market_settlement` (daily cadence,
  `ticker.crons.market_settlement`): runs `match_orders`, applies the
  `Settlement` deltas to ports (stock + purse) and the daily
  `liquidity_drip`, clears filled orders, and emits one aggregate
  `MarketSettled` event (matches count, volume, total slips moved) plus
  per-match `PortOrderFilled` events *only* for ports the player has
  explored (the fog-respecting log discipline `planet_growth` set).
- **Purse hardening (`edge/core/economy.py`, `edge/core/rules.py`).**
  `execute_trade` gains the purse bound: when the port buys from the player,
  the affordable quantity is `port.latinum // unit_price`; the trade fills
  partially and `TradeOutcome` reports `requested` vs `filled` (the `Traded`
  event carries both, so the UI can say "the port could only afford 12").
  When the port sells, proceeds credit its purse. `bigbang/populate.py`
  seeds each purse at `min_purse` (size-scaled) so day-one trading feels
  like Phase 1–2. NPC traders (`core/npc.py::plan_trade`) get the same bound
  — merchants can now genuinely drain a small port, which is the arbitrage
  texture the order book exists to create.
- **The epoch.** Purse seeding + the new hashed container change generated
  output and hashes: bump `config_version 3→4`, regenerate golden masters
  once, in this commit (H12).

Files: `edge/core/models.py`, `edge/core/market.py`, `edge/core/economy.py`,
`edge/core/rules.py`, `edge/core/events.py`, `edge/store/codec.py`,
`edge/engine/cron.py`, `edge/engine/ticker.py`, `edge/bigbang/populate.py`,
`edge/core/config.py`, `config/default.yaml`, `tests/test_market.py`,
`tests/test_economy.py`, `tests/test_engine.py`, golden fixtures.
Tests: legacy-mode byte-identity; ticked market run reloads to identical
`state_hash` (the WP12 rail); purse-bounded partial fills (property: player
latinum + port purse conserved across a bounded trade, goods conserved);
settlement events fog-filtered; codec round-trips.
Commit `p5: WP47 market crons + hard port purses (config_version 4)`.

### WP48 — Market surfacing + balance pass (M)

The market becomes visible and tunable.

- **Projection (`edge/server/session.py`, `edge/core/dto.py`).** A
  `MarketDTO`: per *explored-and-docked* port (fog: the player has seen its
  book only if they have docked there since the last settlement — reuse the
  `Player.explored_sectors` + a `last_docked_day` fact derived from the
  existing `Docked` reducer state rather than a new field if possible;
  otherwise document the new field and batch its hash churn here with a
  golden self-consistency regen, not an epoch), its open orders and the last
  `MarketSettled` aggregates. The pair-trade finder (`computer_view`) keeps
  quoting from live §8 prices — unchanged by design; note in its docstring
  that order books do not leak unexplored ports' stock (fog contract).
- **TUI (`edge/tui/screens/computer.py`).** A "Market" tab: DataTable of
  known books (port, commodity, side, qty, limit), last-settlement summary
  line, and each port's purse *as of last dock* (stale-by-design, like the
  ports directory). The ticker (`describe_event`) renders `MarketSettled`
  one-line summaries.
- **Balance.** Retune so the §8 target ratio (first upgrade within an
  opening session) still holds under purse bounds: verify with the WP44
  balance harness (a scripted bot trading a fixed seed); adjust `min_purse`
  / `drip_frac` defaults, not code. Record the measured income-per-day in
  the commit message (the Phase-1 exit-criterion discipline).

Files: `edge/core/dto.py`, `edge/server/session.py`,
`edge/tui/screens/computer.py`, `edge/tui/widgets.py` (if a shared table
pattern is extracted — prefer reusing the ports-directory table wholesale),
`tests/test_session.py`, `tests/test_tui_flow.py`.
Tests: fog property — a `MarketDTO` never names a port outside explored
sectors; projection determinism; Pilot flow (open Computer → Market tab).
Commit `p5: WP48 market view + balance pass` — **M16 done.**

---

## M17 — The Core changes hands

### WP49 — The governance-flip reducer (M/L)

**New module `edge/core/governance.py`** — the single place Core governance
changes (H11). Contents:

- `flip_core_governor(state, config, new_alliance_id, cause) ->
  GovernanceDelta`: a pure function returning every changed entity, composed
  by callers into one `ReduceResult`:
  1. `Game.core_governing_alliance_id = new_alliance_id` (the one mutable
     field everything else derives from — the WP38 seam pays off here:
     `governor_hostile`, `may_occupy`, `_core_law_events`, and
     `base_owner_hostile` need **zero changes**, verified by test).
  2. **Core planets re-key** (§4.2 "re-keying if governance flips"): every
     planet in a `is_galactic_core` sector gets
     `owner = Ownership("alliance", new_alliance_id)`.
  3. **Core orbital bases re-key** with their planets (same ownership rule);
     their operability is untouched (components are physical, not political).
  4. **Incumbent eviction:** species instances whose `alliance_id` is the
     *old* governor and whose `sector_id` is now illegal under `may_occupy`
     are relocated to the nearest legal sector by deterministic BFS from
     their current sector (ties broken by lowest sector id — no RNG, so the
     flip is pure). StarDock-pinned contacts are re-evaluated: rival-bloc
     members leave the hub; `stardock_contacts` re-fills from Core-welcome
     species only if any are present (never invents new instances).
  5. Events: `GovernanceChanged(old, new, cause)` + a `CoreLawNotice` so the
     ticker announces the new law; per-player, the projection (not the
     reducer) surfaces whether the Core is now hostile to *them*.
- `governance_delta` deliberately does **not** touch `Player.alliance_id` or
  standings: §6.3's rule is positional ("safety follows the governor"), and
  the standing math already re-evaluates live.

Wire a **dev/test trigger** first: a `DevPatch` op (`flip_governor`) so the
whole re-key surface is testable before the player/NPC paths exist (WP50/51),
and so the sysop console (WP59) gets it for free.

Files: new `edge/core/governance.py`, `edge/core/dev.py`,
`edge/core/events.py`, `edge/store/codec.py`, new `tests/test_governance.py`.
Tests: flip re-keys every Core planet/base and only those; eviction lands
every incumbent on legal ground deterministically; `governor_hostile` /
`may_occupy` / Core law flip behavior with **no code change** (the zero-touch
assertions); flip inside one `ReduceResult` replays to identical
`state_hash`; double-flip round-trips.
Commit `p5: WP49 governance flip reducer + dev trigger`.

### WP50 — Player-championed seizure (M)

The conquest path: championing a `covets_core` bloc into the Core.

- **Config (`AllianceConfig`).** `core_seizure: SeizureConfig | None` —
  present only on `covets_core` blocs (validator-enforced): `price` (task
  tokens, the §6.1 vocabulary), `bases_to_raze` (how many of the incumbent's
  **Core-planet** starbases must be razed), `fee` (slips). The default
  roster gives its `covets_core` bloc a demanding ladder.
- **Ledger: reuse, don't reinvent.** Seizure progress rides the existing
  WP38 admission machinery — `record_admission_task` under a reserved
  `seizure:<alliance_id>` key in `Player.species_arcs` (the same replay-safe
  ledger `AdvanceAdmission` writes; the razed-base count is *derived* from
  already-recorded `StarbaseRazed` consequences, not double-booked).
- **Command `PetitionCoreSeizure(alliance_id)`** (`core/rules.py`):
  validates the player is a member of that bloc, the `membership_gate`
  species consents (standing check, as joining), the ledger is complete, the
  incumbent's Core presence is dismantled (`bases_to_raze` met), and the fee
  is paid — then applies `flip_core_governor(..., cause="player_champion")`.
  Rejections carry precise reasons (the `_gate_choice` explain-why
  discipline) so the UI can show a checklist.
- **Projection/TUI.** The Computer's alien-dossier/alliance panel gains a
  "Seizure" checklist (tasks done / bases razed / fee) and the petition
  action. Deliberately **not** a new dialogue `CHOICE_ACTION` — the H9
  three-place sync is reserved for WP57's contracts; authored `governance.*`
  flavor lines may *accompany* the petition later via the ordinary corpus
  without schema changes.

Files: `edge/core/config.py`, `edge/core/rules.py`, `edge/core/aliens.py`
(ledger helpers), `edge/core/events.py`, `edge/store/codec.py`,
`config/alien_roster_default.yaml`, `edge/server/session.py`,
`edge/core/dto.py`, `edge/tui/screens/computer.py`,
`tests/test_governance.py`, `tests/test_alliances.py`.
Tests: full happy path (join bloc → tasks → raze → petition → flip) as a
golden command log; every rejection reason; the checklist projection matches
reducer gating exactly (view/reducer lockstep, H4 pattern).
Commit `p5: WP50 player-championed Core seizure`.

### WP51 — NPC governance + leadership intrigue (M)

The galaxy's own upheavals (§6.3 "or by NPC events"), config-gated.

- **Cron `governance_tick`** (daily; `aliens.governance` config block,
  `enabled` default **true** with a low `seizure_chance`, default 0.002/day
  — a background hum, not a metronome). Salted sub-RNG +
  `Game.governance_seq` (the `drift_seq` pattern, H11). Eligibility, checked
  pure in `core/governance.py::npc_seizure_ready`: a `covets_core` bloc that
  is not the governor, whose home-cluster bases are intact (operational),
  while the incumbent's Core-planet bases have fallen below
  `min_incumbent_bases` (so the player's own razing — or NPC raids — visibly
  destabilizes the Core first; a flip never comes from nowhere). On a
  successful roll: `flip_core_governor(..., cause="npc_seizure")`.
- **Leadership intrigue** (§6.3's `internal_rival_species_id`): same cron,
  separate `intrigue_chance` (default 0.001/day): the rival species becomes
  `alliance_role="leader"` (old leader demoted to member), emitting
  `AllianceLeadershipChanged`; per config the usurped bloc may gain
  `covets_core` (`intrigue_turns_outward: bool`) — the authored hook §6.3
  promised, expressed as data. Dossier text re-derives from roles, so the UI
  follows automatically.
- Both events honor **H11** (one `ReduceResult` per firing) and replay
  through the maintenance log like drift. `species_arcs`, grudges, and
  standings are untouched by NPC flips — political, not personal.

Files: `edge/core/governance.py`, `edge/engine/cron.py`,
`edge/engine/ticker.py`, `edge/core/config.py`, `config/default.yaml`,
`edge/core/models.py` (`Game.governance_seq`), `edge/core/events.py`,
`edge/store/codec.py`, `tests/test_governance.py`, `tests/test_engine.py`.
Tests: readiness predicate truth table; deterministic firing under the
maintenance replay (ticked run → reload → identical hash); a full NPC flip
golden log; intrigue role swap + dossier projection.
Commit `p5: WP51 NPC governance + leadership intrigue`.

### WP52 — Aftermath surfacing + the hostile-Core experience (M)

Make a flip *legible* and the hostile Core survivable-but-hard.

- **Projection.** `GameState`/sidebar gains the current governor's name and
  the player's Core status (safe / unwelcome / hunted — derived via
  `governor_hostile`); the map/nav rose re-tints Core markers by that
  status; `MessagesScreen` renders the governance events; the dossier's
  alliance section shows governor + `covets_core` intel.
- **Hostile-Core mechanics tightened** (already mostly live via WP38's
  standing rule — this WP closes the service gaps): docking at the Core
  StarDock is rejected while the governor is hostile (services denied, with
  a clear reason — the §6.3 "denied the haven" promise); recruitment and
  bank access follow docking. Core-governor bases already engage via
  `base_owner_hostile` — add the encounter-open dialogue context reuse
  (`combat_open` keyed to the governor species) so the engagement speaks.
- **Devtool/sysop:** `flip_governor` op documented; a `governance` report
  (current governor, eligible blocs, incumbent base count) added to
  `edge/devtool`.
- **Docs:** DESIGN §6.3/§10 marked implemented; a `docs/` playtest note on
  tuning `seizure_chance`.

Files: `edge/server/session.py`, `edge/core/dto.py`, `edge/core/rules.py`
(dock gating), `edge/tui/screens/game.py`, `edge/tui/screens/map.py`,
`edge/tui/widgets.py`, `edge/devtool/__main__.py`, `docs/DESIGN.md`,
`tests/test_session.py`, `tests/test_rules.py`.
Tests: dock rejection matrix (member / neutral / rival vs governor); status
projection truth table; Pilot flow — flip via devtool, observe banner + tint.
Commit `p5: WP52 governance aftermath surfacing` — **M17 done.**

---

## M18 — Footholds, citadels, planetary war

### WP53 — Forward-base services (M/L)

The §4.2 payoff: a repaired, claimed base becomes a working home.

- **The refactor (emphasized).** `core/rules.py` gates StarDock services
  through `_stardock(state, ship)` (raises unless docked at the Class-9
  port). Extract a **`ServicePoint` resolver** — new
  `edge/core/services.py`: `service_point(state, player, ship, config) ->
  ServicePoint | None` returning a frozen descriptor `{kind:
  "stardock" | "player_base", ref, services: frozenset[ServiceKind],
  fee_frac}`. `RepairAtDock`, `BuyComponent`, `BuyMissiles` (+ kits),
  `Deposit`/`Withdraw` are refactored to consume the resolver instead of
  `_stardock` — **one code path, two providers**, rather than parallel
  `…AtBase` command clones. Command names and payloads are unchanged, so
  the log/codec/goldens don't move; only rejection conditions widen. The
  resolver's docstring records the §4.1 promise it implements ("full
  restoration… at StarDock or a friendly alien base") and that *friendly
  alien base* service remains a future config extension of the same seam.
- **Config.** `StarbaseConfig.services: BaseServicesConfig` — per-service
  bools (`repair`, `components`, `munitions`, `banking`) + `fee_frac`
  (default 1.25 — frontier convenience costs) + `component_stock_tiers`
  (default `[I, II]`; Tier III stays barter-only, §8).
- **Gating.** A `player_base` service point exists when the player's ship is
  in the sector of a planet whose operational (`starbases.is_operational`)
  base is `Ownership("player", player_id)` and the service is enabled.
  Component *purchases* at a base draw from a config catalog at
  `fee_frac × StarDock price`; swaps/repairs reuse the engine-room reducers
  unchanged (they never cared *where* the ship was based — verify and pin).
- **TUI.** Docking at an owned base opens `StarbaseServicesScreen` reusing
  the StarDock tab panes (hardware table, bank pane) — composition, not
  copy; the sector view labels the base "⌂ yours — services".

Files: new `edge/core/services.py`, `edge/core/rules.py`,
`edge/core/config.py`, `config/default.yaml`, `edge/server/session.py`,
`edge/core/dto.py`, `edge/tui/screens/stardock.py` (pane extraction),
new `edge/tui/screens/starbase_services.py`, `tests/test_rules.py`,
new `tests/test_services.py`.
Tests: resolver truth table (dock/base/neither, each service toggle);
StarDock behavior byte-identical post-refactor (regression suite untouched);
fees applied exactly once; banking at a base rides the same
`Player.bank_balance` invariants (property tests reuse `test_economy`).
Commit `p5: WP53 forward-base services via ServicePoint resolver`.

### WP54 — Citadels: levels, treasury, the planetary gun (M)

`Planet.citadel_level` finally earns its keep (H17).

- **New module `edge/core/citadels.py`** + `CitadelConfig` (config): per
  level 1–3, `cost_equipment`, `cost_latinum`, `min_colonists`,
  `build_colonist_days`, and what it grants — L1: **treasury** (a planetary
  latinum store) + a garrison defense bonus; L2: the **citadel gun** (a
  fixed planetary emplacement joining defense, stats in config); L3: a
  **siege shield** (invasion impossible while any orbital base *or* the gun
  is operational — the WP55 ladder). Levels are cumulative; costs are drawn
  from planet `stores` + player latinum (conservation: equipment leaves
  stores, latinum burns — a real §8 sink).
- **Timed construction (interview decision 2).** `BuildCitadel` pays the
  full cost up front and opens a build: `Planet.citadel_progress: int`
  (colonist-days accrued; `-1`/absent ⇒ no build open) advances on the
  existing `hourly_planet_growth` cron by `colonists / day` (pro-rated per
  firing, integer-accumulated so replay is exact), completing —
  `citadel_level += 1`, progress cleared, `CitadelCompleted` event — when it
  reaches the level's `build_colonist_days`. One build open per planet; a
  build is **not** lootable or cancellable (interview: plain timed, not the
  raidable variant) — conquest mid-build simply inherits the open build.
  The rate riding colonists makes big colonies build faster, which is the
  point of the gate.
- **Model.** `Planet.treasury: int = 0`, `Planet.fighters: int = 0` (the
  §4 table's garrison store, produced from WP55's allocation), and
  `Planet.citadel_progress` — hashed fields, batched into the M18 epoch at
  WP56 (H12); until then they ship behind the epoch commit ordering
  (WP54–56 land in one golden window).
- **Commands.** `BuildCitadel(planet_id)` (next level, full validation, pays
  and opens the timed build above),
  `PlanetDeposit`/`PlanetWithdraw(planet_id, amount)` (owner-only, in-sector;
  the treasury is banking *without* interest — its value is location, not
  yield; documented rationale).
- **Defense integration (reuse).** The citadel gun joins encounters exactly
  as bases do: a `citadels.citadel_foe(planet, config) -> EncounterFoe` —
  the third reuse of the `EncounterFoe` spawn pattern after
  `starbases.assault_foe` and `territory.fighter_foe`; the sector-entry
  hostility check keys off planet ownership like `base_owner_hostile`
  (extend that helper to accept the planet-owner case rather than writing a
  sibling).

Files: new `edge/core/citadels.py`, `edge/core/models.py`,
`edge/core/config.py`, `config/default.yaml`, `edge/core/rules.py`,
`edge/core/events.py`, `edge/store/codec.py`, `edge/server/session.py`,
`edge/core/dto.py`, `edge/tui/screens/planet.py`, new
`tests/test_citadels.py`.
Tests: build ladder costs/validation; timed-build accrual exact under cron
replay (ticked build → reload → identical hash; completion fires once);
one-build-per-planet; treasury conservation (property); gun-foe stats derive
from config; L3 shield predicate; owner-only gating.
Commit `p5: WP54 citadels — levels, treasury, timed builds, planetary gun`.

### WP55 — Planetary combat: siege and conquest (L)

The invasion ladder (§14 "citadels and planetary combat"), deliberately
sequenced so set-piece work already shipped is the on-ramp:

1. **Raze the orbital base** — exists (WP40 assault).
2. **Silence the citadel gun** — a `CombatAction` fight against
   `citadel_foe` (the WP24–26 machinery unchanged; the "foe" is immobile,
   like a base assault). Victory marks the gun knocked out (a
   `citadel_gun_down` transient on the planet? No — H17: derive it from a
   new `Planet.gun_integrity: int` field ticked by the fight, mirroring how
   base components degrade; document the parallel).
3. **Ground assault** — new command `InvadePlanet(planet_id, fighters)`:
   legal only when no operational base defends the sector, the gun is down
   (or never built), and L3's shield rule passes. Resolution is pure in
   `core/citadels.py::resolve_invasion`: attacker commits carried
   `Ship.fighters`; defense strength = `planet.fighters ×
   citadel_defense_mult(level)`; per-round percentile exchange (BNT §A.3
   shape) drawn from `state.rng` **inside the reducer** (H4), until one side
   breaks. Victory: `owner` flips to the player, colonists survive at
   `civilian_survival_frac` (config), citadel drops one level, stores are
   looted at salvage fractions (10–20%, the §A.3 echo), treasury is
   captured. Defeat: committed fighters die, alignment drops, and the full
   WP27 consequence rail fires (attitude souring toward the owner species /
   bloc, grudges, spillover — *reuse `sour_attitude`/`apply_spillover`,
   listed here as the load-bearing dependency*).
- **Production.** `Planet.allocation` gains a fighter share: rather than
  widening the `Commodity`-keyed map (the trio is sacred, §4), add
  `Planet.fighter_allocation: float` with the invariant `sum(allocation) +
  fighter_allocation == 1.0`; `planets.produce` mints garrison fighters from
  it (equipment-flavored yield shaping, config rate). `SetAllocation` and
  the planet screen grow the slider.
- **Core-law interaction:** invading *any* owned world in Core space is
  simply impossible (deployment-free Core, §10 — assert, don't special-case).

Files: `edge/core/citadels.py`, `edge/core/planets.py`, `edge/core/models.py`,
`edge/core/rules.py`, `edge/core/aliens.py` (consequence reuse),
`edge/core/events.py`, `edge/store/codec.py`, `edge/core/config.py`,
`config/default.yaml`, `edge/server/session.py`, `edge/core/dto.py`,
`edge/tui/screens/planet.py`, `tests/test_citadels.py`,
`tests/test_planets.py`, `tests/test_rules.py`.
Tests: ladder ordering enforced (each rung rejects until the previous falls);
invasion property tests (fighters conserved-or-destroyed, never minted;
ownership flips exactly on victory; allocation invariant); consequence rail
parity with ship-combat betrayal; a full siege golden log.
Commit `p5: WP55 planetary siege + conquest`.

### WP56 — Mine split, probes, interdictor + the M18 epoch (M)

Three §10/§14 devices, then the batched epoch.

- **Armid/limpet split (§10).** `SectorForce.mines` becomes `armid_mines` +
  `limpet_mines` (codec migration; `DeployMines` gains a `kind`). Armid
  keeps today's entry-damage behavior (rename only). Limpets **attach**: a
  hostile entrant picks up `Ship.limpets: Mapping[str, int]` (owner tag →
  count); while limpeted, the *owner's* hunt-policy NPCs (WP42) read the
  player's **exact** current sector instead of last-known — a tracking
  device, mechanically expressed through the planner that already exists.
  Removal at any `ServicePoint` (WP53 reuse) for a fee. Mine deflectors
  (`HardwareConfig` device, the §A.3 price list) absorb armid hits 1:1.
- **Probes.** A consumable device (`HardwareConfig`, StarDock-bought).
  `LaunchProbe(dest_sector)`: BFS over the **known-graph** rules of
  `TravelTo` *except* probes may path the full graph up to
  `probe_range` hops (they are how you buy knowledge); the reducer charts
  each traversed sector (`explored_sectors`) and emits a `ProbeReport`
  event summarizing contents (port class, planet count, contacts) — the
  §11 promise that computer features are first-class queries. A per-hop
  destruction roll in hostile-force sectors (from `state.rng`, H4) makes
  deep probing lossy.
- **Interdictor.** A ship device toggled by `ToggleInterdictor`: while
  active in the player's sector, NPC drift out of that sector is suppressed
  (`alien_drift` checks presence — one legality hook in `may_occupy`'s
  caller, not a new rule path) and encounter foes cannot disengage; upkeep
  is a per-day turn tax (config) so it is a stance, not a default.
- **The epoch.** All M18 hashed fields (`treasury`, `fighters`,
  `gun_integrity`, `fighter_allocation`, mine split, `limpets`, devices)
  batch into **`config_version 4→5`** with one golden regeneration (H12).

Files: `edge/core/models.py`, `edge/core/territory.py`, `edge/core/npc.py`,
`edge/core/rules.py`, `edge/core/config.py`, `config/default.yaml`,
`edge/core/events.py`, `edge/store/codec.py`, `edge/engine/cron.py`,
`edge/server/session.py`, `edge/core/dto.py`, TUI touchpoints,
`tests/test_territory.py` (new or extended), `tests/test_movement.py`,
golden fixtures.
Tests: armid parity with old mines; limpet attach/track/remove lifecycle
(hunter converges on live position — extend the WP42 fixture graphs); probe
charting + loss rolls replay-stable; interdictor pins drift deterministically.
Commit `p5: WP56 armid/limpet split, probes, interdictor (config_version 5)`
— **M18 done.**

---

## M19 — A social galaxy

### WP57 — Favors and escort contracts (L)

Richer alien interactions (§14), delivered through the §6.7 dialogue system —
the one WP in these phases that touches the dialogue schema, so **H9 binds**:
the `config/alien_dialogue_default.yaml` spec header, the authoring prompt
context (`edge/dialogue/authoring/pipeline.py` `build_prompt` /
`_structure_brief`), and DESIGN §6.7/§13 all update in this change.

- **New module `edge/core/contracts.py`.** `Contract` (frozen): `id`,
  `kind` (`deliver` / `destroy` / `escort`), `issuer` (roster_id), `target`
  (a `LocationRef`-shaped ref: commodity+qty+port for deliver; a starbase or
  species instance for destroy; a merchant species instance + destination
  port for escort), `reward` (slips and/or attitude and/or a component
  tier), `accepted_day`, `deadline_day`, `status`
  (`offered/active/done/failed`). Stored on `Player.contracts:
  tuple[Contract, ...]` (hashed; golden batch here, H12).
- **Offer planning (reuse emphasized).** A pure
  `pick_contract(state, species, player, config)` mirroring
  `dialogue.intel.pick_intel_target` — disposition-gated, seeded, drawing
  targets from live state (a port the issuer's book shows short ⇒ deliver;
  a grudge target ⇒ destroy — the §6.5 `demand` finally cashable; a
  `trade_seek` merchant of the issuer's bloc ⇒ escort, never a
  StarDock-pinned instance). Placeholders
  (`{target}`, `{reward}`, `{deadline}`) bind into authored lines.
- **Dialogue vocabulary.** One new intent context `contract_offer` (+
  `contract_report`) and one new `CHOICE_ACTIONS` entry `accept_contract`
  (the H9 sync list above). The generic persona authors baseline lines;
  species packs override in voice. `Converse` handles accept → appends the
  contract (replayable command rail, like `AcceptLead`).
- **Completion detection is reducer-side, never polled by UI:** deliver — a
  new `DeliverContract` command at the target port (cargo debits, reward
  credits); destroy — the combat/assault reducers check active contracts on
  kill (same hook point as bounties, WP44); failure on deadline via the
  daily cron (next to grudge decay). Rewards flow through the existing
  latinum/attitude/component rails.
- **Escort = convoy warp (interview decision 9).** Accepting an escort
  contract puts the merchant **under convoy**: it leaves the drift/trader
  rails (`alien_drift` and `trader_step` skip a convoyed instance — one
  predicate, `contracts.is_convoyed`) and instead **moves with the player's
  movement reducers**: each `Warp`/`TravelTo` hop that departs the
  merchant's sector relocates the merchant alongside the player (inside the
  same `ReduceResult`, so convoy replays exactly). A hop taken from
  *elsewhere* leaves the merchant waiting where it is (the convoy suspends;
  return to resume — never fails silently). En-route encounter spawns treat
  the convoy as present: a violent opening may target the merchant (a
  config-weighted foe-target roll), and a destroyed merchant fails the
  contract with the full WP27 consequence rail toward its species. The
  contract **completes when the convoy reaches the destination sector**
  (checked in the same movement reducer), releasing the merchant back to
  its rails. Edge cases pinned by test: farewell/abandon (an
  `AbandonContract` command releases + fails honestly), deadline expiry
  mid-convoy, merchant pinned at StarDock never offered as escort.

Files: new `edge/core/contracts.py`, `edge/core/models.py`,
`edge/core/rules.py`, `edge/dialogue/intents.py`, `edge/dialogue/select.py`
(validator additions), `edge/core/config.py` (`SpeciesConfig.contracts`
posture), `config/alien_dialogue_default.yaml` (+ spec header),
`edge/dialogue/authoring/pipeline.py`, `edge/engine/cron.py`,
`edge/core/events.py`, `edge/store/codec.py`, `edge/server/session.py`,
`edge/core/dto.py`, `edge/tui/screens/contact.py`,
`edge/tui/screens/computer.py` (contracts panel), `docs/DESIGN.md`,
new `tests/test_contracts.py`, `tests/test_dialogue.py`, golden fixtures
(M19 batch).
Tests: offer determinism (view/reducer lockstep — the contact screen shows
exactly the contract the reducer will book, H4 pattern); each kind's full
lifecycle golden log; deadline failure via cron replay; dialogue-integrity
suite green with the new vocabulary; H9 three-place sync asserted by the
existing spec-header test.
Commit `p5: WP57 favors + escort contracts (dialogue-issued)`.

### WP58 — Tavern, rumors, noticeboard (M)

The StarDock tavern pane goes live (§14; the placeholder names this WP).

- **Rumors.** `BuyRumor` command (config `tavern.rumor_price`, a latinum
  sink): draws from the union of Core-welcome species'
  `species_knowledge` (reuse the intel planner's gating/dedup wholesale) and
  books a `Lead` — the tavern is intel for cash where contacts are intel for
  standing. Repeat purchases exhaust like repeated asks (same dedup rail).
- **Bounty board.** Read-only projection: hostile-band species with
  `bounty_per_kill`, active player grudges (who hunts you), open contracts
  (WP57), and — post-M17 — the governance situation. Pure projection work;
  no new state.
- **Noticeboard.** `PostNotice(text)` appends to `state.notices` (a capped
  ring, config `tavern.notice_cap` default 50, oldest evicted; hashed —
  part of the M19 golden batch at WP57): `{author_player_id, day, text}`.
  Single-player it is a captain's log pinned where you drink; Phase 4 makes
  it the shared board for free (same state, many authors). Text sanitized
  at the reducer (length cap, printable-only) — the one string-input command
  in the game, so validation is explicit and tested.
- **TUI.** The Tavern tab renders the three panels; `describe_event` covers
  the new events.

Files: `edge/core/models.py`, `edge/core/rules.py`, `edge/core/config.py`,
`config/default.yaml`, `edge/core/events.py`, `edge/store/codec.py`,
`edge/server/session.py`, `edge/core/dto.py`, `edge/tui/screens/stardock.py`,
`tests/test_rules.py`, `tests/test_session.py`, `tests/test_tui_flow.py`.
Tests: rumor draws deterministic + deduped against leads/codex; notice ring
eviction; input validation property (arbitrary text never corrupts codec
round-trip); Pilot flow (tavern → buy rumor → lead on Computer).
Commit `p5: WP58 tavern — rumors, bounty board, noticeboard`.

### WP59 — Sysop console (M)

AAT's admin catalog (§A.4) as a menu, built on rails that already exist. The
sysop console is **dev tooling** (the `devtool`/`tui` exemption tier — not
imported by any runtime layer, H13/H16 discipline like
`dialogue/authoring/`).

- **`edge-sysop` console script** (`edge/devtool/sysop.py`), menu-driven over
  a save file: **Reports** — players (latinum/bank/turns/standings), economy
  aggregates (money supply: player + bank + port purses + treasuries; the
  H10 conservation audit as a *tool*), market books, species/alliance
  standings, governance state, notices. **Interventions** — every mutation
  goes through the **existing `DevPatch` command rail** (extended with the
  ops the catalog needs: grant/seize latinum, set turns, teleport, flip
  governor (WP49), force settlement, expire contract, moderate/delete
  notice) so *every sysop act is a logged, replayable command* — the audit
  trail is the command log itself, which is the twclone lesson stated in
  its docstring. **Config** — dump the resolved `GameConfig`, diff two
  saves' meta.
- Reports read through `GameService` + a handful of new read-only session
  projections where fog must be bypassed — add explicit
  `sysop_view` functions in `edge/devtool/reports.py` that take the raw
  state (devtool is trusted; document that these never move into `server/`).

Files: new `edge/devtool/sysop.py`, new `edge/devtool/reports.py`,
`edge/core/dev.py` (new ops), `pyproject.toml` (script entry),
`tests/test_devtool.py`.
Tests: every new DevPatch op replay-safe (apply → rebuild → identical hash);
money-supply audit balances on a played fixture; menu smoke test.
Commit `p5: WP59 sysop console over the DevPatch rail`.

### WP60 — Scripting hooks, the service protocol + Phase-5 exit (M)

TWX-style scripting (§14) — and, deliberately, the seam Phase 4 stands on.

- **`ServiceProtocol`** (new `edge/server/protocol.py`): a typed
  `Protocol` capturing exactly the surface `GameService` already exposes —
  `apply(player_id, command) -> tuple[Event, ...]` plus every `*_view`
  reader and `resolve_display_id`/`describe_event`. `GameService` is
  declared its implementation (a static `mypy` assertion, no runtime
  change). This is **H16's one seam**: the TUI (WP61), bots (this WP), the
  sysop reports, and the remote client (WP68) all type against it.
- **Bot harness** (`edge/bot/`, dev-tier like `dialogue/authoring/`):
  `BotRunner(service, player_id)` — an event-trigger registry
  (`on(EventType) -> handler`, the TWX trigger idiom) plus a turn driver;
  bots submit ordinary commands and read ordinary DTOs (fog-honest by
  construction — a bot cannot see more than a player). `edge-bot --script
  path.py --save game.db` executes a user script defining `setup(bot)`.
  Ships two example scripts: `pair_trader.py` (the WP48 balance harness,
  promoted) and `explorer.py`. `docs/SCRIPTING.md` documents the API and the
  trust model (scripts are Python running with your privileges — no
  sandbox; stated plainly).
- **Phase-5 exit balance pass:** run the trader + explorer bots across
  seeds; verify the §8 ratio under purses, contract/rumor sinks absorbing
  faucets (bounties, treasuries), and record numbers in the commit. Playtest
  checklist against the M16–M19 exit lines.

Files: new `edge/server/protocol.py`, new `edge/bot/__init__.py` +
`edge/bot/runner.py` + `edge/bot/scripts/`, `pyproject.toml`,
new `docs/SCRIPTING.md`, `tests/test_bot.py`, `tests/test_service.py`
(protocol conformance).
Tests: protocol conformance (static + runtime duck test); bot runs are
replayable logs (rebuild parity); trigger dispatch; example scripts complete
on fixture seeds.
Commit `p5: WP60 scripting hooks + service protocol` — **M19 / Phase 5
done.**

---

## M20 — The wire

### WP61 — Phase-4 spec deltas + the async client facade (M/L)

The one refactor that makes a remote client possible without rewriting the
TUI twice — do it first, while everything still runs in-process.

- **Spec deltas (DESIGN):** §3/§14/§15 corrected per framing correction 1
  (dataclass DTOs + wire codec; websockets + JSON-RPC as the Phase-4 deps);
  §3 gains the session/broadcast paragraph (below); §14 Phase 4 rewritten
  against this plan — expanding the **full PvP** summary WP45 planted there
  (interview decision 3: the attacker-driven model, Core sanctuary + `pvp`
  toggle, pod/salvage/outlaw stakes, corp war, territory engaging all
  non-owner players); §10 gains the PvP paragraph WP67 implements.
- **`GameClient` facade** (new `edge/server/client.py`): an async interface
  mirroring `ServiceProtocol` (`async def apply(...)`, `async def
  game_view(...)`, …) plus `events` (an async iterator of pushed events —
  the broadcast seam, stubbed single-player as "events returned by my own
  apply"). `LocalClient(service)` wraps the in-process `GameService` with
  trivial pass-through (no executor games — core is fast and pure).
- **TUI refactor:** `EdgeApp` and screens hold a `GameClient` instead of a
  `GameService`; call sites become `await` (Textual handlers already run on
  the loop; `tui/` is the throwaway layer, so this churn is cheap and
  contained — enumerate the touched screens in the commit body). The
  embedded `EngineTicker` stays owned by whoever owns the *service* —
  `LocalClient` for single-player; the server for remote (WP63) — encoded
  in the client constructor so the TUI never thinks about ticking.
  `EdgeApp.player_id` becomes a constructor argument fed by the client
  (framing correction 6).
- Single-player behavior must be **observably identical** (same Pilot suite
  green, same golden logs).

Files: `docs/DESIGN.md`, new `edge/server/client.py`, `edge/tui/app.py`,
`edge/tui/screens/*.py` (mechanical await-ing), `tests/test_app.py`,
`tests/test_tui_flow.py`.
Tests: Pilot suite green over `LocalClient`; facade conformance to
`ServiceProtocol` shape (typed); no runtime import of `server.net` (doesn't
exist yet) from `tui`.
Commit `p4: WP61 GameClient facade + TUI async refactor`.

### WP62 — The wire codec (M)

**New `edge/server/wire.py`** — explicit, versioned serialization in the
`store/codec.py` house style (H16):

- **Commands/events reuse `store/codec.py` verbatim** (single source of
  truth — the wire and the log speak the same dialect; a divergence would be
  a replay bug factory, stated in the docstring).
- **DTO encoding:** explicit `encode_dto` / `decode_dto` per DTO class
  (mirroring codec's per-type functions — verbose by design: an exhaustive,
  mypy-checked mapping that breaks loudly when a DTO gains a field). No
  reflection, no pickle, no Pydantic conversion (framing correction 1).
- **Envelope:** `{"v": WIRE_VERSION, "kind": ..., "payload": ...}`;
  `WIRE_VERSION` starts at 1 and bumps on any breaking change; a
  `wire_fingerprint()` (sorted kinds + version hash) lets client and server
  refuse mismatched builds at handshake — the `dialogue_fingerprint`
  pattern, reused.
- **Golden wire fixtures:** every command, event, and DTO round-trips
  against checked-in JSON (`tests/fixtures/wire/`), so a protocol break is a
  diff in review, not a runtime surprise.

Files: new `edge/server/wire.py`, new `tests/test_wire.py` + fixtures.
Tests: exhaustive round-trip (parametrized over every command/event/DTO
constructor the test factory builds); fingerprint stability; unknown-kind /
bad-version rejection paths.
Commit `p4: WP62 versioned wire codec + golden fixtures`.

### WP63 — The net server: JSON-RPC over websockets (L)

**New `edge/server/net.py`** + the `edge-server` entry point. H14 is the
whole design:

- **One authoritative task** owns `GameService` + `EngineTicker` for a
  hosted game. All sessions' `apply` calls are marshalled through a single
  `asyncio.Queue`; the owner task dequeues, applies (total order — the
  replay contract's precondition), and answers. Projections execute on the
  same loop between applies (pure reads of settled state; no locks anywhere,
  and a comment explains *why* there are none). SQLite keeps its one
  writer.
- **Protocol:** JSON-RPC 2.0 over `websockets` (dependency added to
  `pyproject.toml`/pixi and DESIGN §15 in the same commit): one method per
  `ServiceProtocol` member (`apply`, `game_view`, …) with wire-codec
  payloads; server-initiated **notifications** reserved for WP65. Errors:
  rules rejections map to a stable error code + the reducer's message
  (rejections are gameplay, not faults); internal errors are logged and
  masked.
- **Session registry:** connection → authenticated account → `player_id`
  (binding from WP64; until then a `--insecure-player N` dev flag). A
  session's `apply` is *validated for identity* at the boundary: a session
  may only submit commands as its own player_id — the fog-of-war rule's
  write-side twin, enforced in `net.py` (transport-level), not core.
- **`edge-server` CLI:** `--game path.db --config ... --host --port`;
  graceful shutdown persists ticker state (the WP12 rail already handles
  resume).

Files: new `edge/server/net.py`, `pyproject.toml`, `config`/docs touches,
`docs/DESIGN.md` §15, new `tests/test_net.py` (pytest-asyncio,
in-process client/server pairs over a real socket).
Tests: request/response round-trip for every method; interleaved sessions'
commands apply in arrival order (queue property); identity enforcement (a
session cannot act as another player); rejection vs internal-error mapping;
server restart resumes ticker schedule.
Commit `p4: WP63 websocket JSON-RPC server (single-writer loop)`.

### WP64 — Lobby and auth (M)

Identity, kept out of core (H15).

- **Account store:** a server-side SQLite (`accounts.db`, separate from any
  game save — never inside `UniverseState` or `state_hash`): accounts
  (username, salted PBKDF2-HMAC via stdlib `hashlib`, created_at), sessions
  (token via `secrets.token_urlsafe`, expiry), and per-game bindings
  (account ↔ game ↔ player_id).
- **Lobby methods (pre-auth + post-auth):** `register`, `login` → token;
  `list_games`, `create_game(config, seed)` (host-gated), `join_game(game)`
  — allocates a player by appending **`JoinGame`** through the same command
  queue (the §3 seam working as designed: a new player is one more log
  entry), binds account↔player, returns the player_id; `resume(game)`
  re-binds an existing player. Multi-game hosting = one authoritative task
  per open game (a registry keyed by game id).
- **Rate limiting** minimal and honest: a per-connection command budget per
  second (config) so a hostile client cannot starve the loop; documented as
  DoS *hygiene*, not security hardening.

Files: `edge/server/net.py`, new `edge/server/accounts.py`,
`tests/test_net.py`, new `tests/test_accounts.py`, `docs/DESIGN.md` (§3
lobby note).
Tests: register/login/token lifecycle; join allocates via a logged JoinGame
(rebuild reproduces the roster of players); binding uniqueness; wrong-token
and expired-token paths; budget enforcement.
Commit `p4: WP64 lobby + accounts (identity outside core)` — **M20 done.**

---

## M21 — A shared galaxy

### WP65 — Broadcast pipeline (M)

Events reach the players who should see them, and only those.

- **Visibility filter (`edge/server/session.py`):**
  `event_visible_to(state, event, player_id) -> bool` — a pure function
  **refactored out of `format_log_line`'s existing event→sector/player
  mapping** (that logic already decides what the single-player ticker shows;
  extracting it is the reuse, and `format_log_line` becomes its first
  consumer, so single-player behavior cannot drift from multiplayer
  visibility). Default policy: player-addressed events to that player;
  sector-scoped events to players present or with the sector explored
  (config-tightenable to present-only); global events (governance,
  settlement aggregates) to all.
- **Server fan-out (`edge/server/net.py`):** after every applied command
  *and* every maintenance firing, filtered events are pushed as JSON-RPC
  notifications (`event`, with the event-log `seq`). Reconnect catch-up:
  `events_since(seq)` reads `repo.load_events` — the durable rail doubles
  as the replay buffer, no new queue state.
- **Client (`edge/server/client.py` / TUI):** `RemoteClient.events` yields
  pushed events; the TUI ticker consumes the same stream in both modes
  (LocalClient synthesizes it from apply results + a maintenance hook —
  the WP61 stub made real).

Files: `edge/server/session.py`, `edge/server/net.py`,
`edge/server/client.py`, `edge/store/repo.py` (a `load_events_since(seq)`
reader), `tests/test_session.py`, `tests/test_net.py`.
Tests: visibility property — no event about an unexplored, absent sector
ever reaches a player (the fog write-side twin, fuzzed); catch-up equals
live stream (same seq window ⇒ same events); ticker parity local vs remote.
Commit `p4: WP65 visibility-filtered broadcast + catch-up`.

### WP66 — Corporations + corp war (L)

The §4 `Corporation` row becomes real (framing correction 2), with shared
assets and corp war (interview decision 6) — one config epoch.

- **Model:** `Corporation` (frozen): `id`, `name`, `tag` (validated short
  uppercase, unique), `ceo_player_id`, `member_player_ids:
  frozenset[int]`, `bank_balance`, `at_war_with: frozenset[int]` (corp
  ids). `UniverseState.corporations` (hashed).
  **`Ownership` gains kind `"corp"`** — the one schema-wide change, and the
  reason this WP owns **`config_version 5→6`** (H12): every ownership
  consumer (`base_owner_hostile`, `force_hostile_to_player`, planet defense,
  beacon control, invasion legality, production collection) is audited for
  the new kind in this commit — grep-driven, enumerated in the commit body.
  Rule: a corp asset treats every member as its owner. The epoch batch also
  carries WP67's PvP fields (`Player.bounty`, the `Encounter` PvP target
  ref) — declared here, read in WP67, same milestone (H17-compliant, one
  golden regeneration).
- **Corp war (interview decision 6):** `DeclareCorpWar(corp_id)` (CEO-gated)
  makes the hostility mutual-by-declaration (either side declaring is
  enough — the `rival_alliance_ids` symmetry rule reused); `EndCorpWar` is
  unilateral withdrawal (config cooldown before re-declaring, so war isn't
  a toggle spammed for toll evasion). While at war, each side's members and
  assets read as hostile to the other in every hostility helper — the same
  audit list as the ownership kind, extended in the same commit. War state
  is corp-level; per-player alliance membership, attitudes, and grudges are
  untouched (property, not politics).
- **Commands:** `FormCorp(name, tag)` (fee, §8 sink), `InviteToCorp(player)`
  / `AcceptCorpInvite` (two-step consent — no press-ganging),
  `LeaveCorp` / `ExpelFromCorp`, `CorpDeposit`/`CorpWithdraw` (member /
  CEO-gated; never negative — the `core.economy` invariant functions
  reused), `TransferPlanetToCorp(planet_id)` (and back, CEO-gated),
  `DeclareCorpWar`/`EndCorpWar`. Dissolution (last member leaves): assets
  re-key to the departing CEO — never to `none` (owned things stay owned;
  documented rationale); open wars end with the corp.
- **Multiplayer semantics:** invites, expulsions, and declarations are
  ordinary logged commands, so corp history replays; `alliance` diplomacy
  stays per-player (recorded in DESIGN §4). Note there is deliberately **no
  same-corp damage immunity** (interview decision 4): the no-attack norm
  inside a corp is social, enforced by expulsion, not by the rules engine.
- **TUI:** the `T` screen (corp roster, bank, holdings, wars, invite flow) —
  single-player it manages a corp of one (useful for estate-keeping;
  cheap to render since DTOs exist for multiplayer anyway).

Files: `edge/core/models.py`, `edge/core/rules.py`, `edge/core/aliens.py` +
`edge/core/territory.py` + `edge/core/citadels.py` (ownership audits),
`edge/core/events.py`, `edge/store/codec.py`, `edge/core/config.py`,
`edge/server/session.py`, `edge/core/dto.py`, new
`edge/tui/screens/corp.py`, `tests/test_corp.py` (new), golden fixtures
(epoch).
Tests: corp bank invariants (property); ownership-kind audit matrix (every
consumer × corp-owned asset × member/non-member/at-war); invite consent
flow; war declare/withdraw/cooldown lifecycle; dissolution re-key; full corp
golden log; epoch regen in-commit.
Commit `p4: WP66 corporations + corp war + corp ownership kind
(config_version 6)`.

### WP67 — Full PvP: attacker-driven combat, territory, outlawry (L)

Interview decision 3, bounded by decisions 4/5/7 and H18. Built as a *reuse*
of the WP24–WP26 encounter machinery, not a parallel combat system.

- **Config.** `GameConfig.pvp: PvpConfig` — `enabled: bool` (the per-game
  host toggle, interview decision 4; reducers gate on it, H18),
  `salvage_frac_min/max` (0.10/0.20, the §A.3 echo), `bounty_frac` (bounty
  posted on a lawful kill as a fraction of the victim's ship price),
  `alignment_hit` scalars.
- **Engagement.** New command `AttackPlayer(target_player_id)`: legal when
  both ships share a non-Core sector, `pvp.enabled`, target not already in
  an encounter, and neither party is pod-bound. Opens an `Encounter` whose
  foe is **derived from the target's live `Ship`** — a
  `combat.player_foe(ship, config) -> EncounterFoe` resolving hull/shields/
  damage/arc/speed from the same derived aspects the defender's own fights
  use (subsystem-derived for player hulls, §4.1), so a tuned engine room
  defends its owner even offline. The `Encounter` gains
  `target_player_id: int | None` (the `starbase_id` pattern; field landed
  in the WP66 epoch batch). Rounds are the existing `CombatAction`s from
  the attacker only (H18); defender-side damage is applied to the target's
  real `Ship` (components knock out, hull persists) inside the same
  `ReduceResult`s, and the defender experiences the fight as broadcast
  events (WP65) — attacker-driven, TW2002 classic.
- **Resolution.** Defender hull at zero ⇒ the WP26 escape-pod rule verbatim
  (pod at their ship's sector; bank/planets/corp intact); victor draws
  salvage — `salvage_frac` of cargo + loose components (conservation:
  moved, never minted). Flee stays the attacker's option; the defender's
  automation never flees (a fixed emplacement-like stance — documented,
  with the hybrid online-defender variant noted as a future seam).
- **Outlawry (interview decision 5).** Killing a *lawful* player
  (`alignment ≥ 0`, the `is_criminal` line reused) drops the attacker's
  alignment (`alignment_hit`, the WP27 rail) and posts a **claimable
  bounty**: `Player.bounty: int` (hashed; WP66 epoch batch) accrues
  `bounty_frac × victim ship price`; any player who pods the outlaw
  collects it (the same kill hook the WP44 NPC bounties use). The WP58
  bounty board lists outlaws — the tavern's third panel becomes
  multiplayer-live for free.
- **Territory vs players (interview decision 7).** The movement reducers'
  entry checks (`_territory_entry`, mine hits, toll, base/citadel defense)
  extend to player entrants: every deployed force and defense engages any
  non-owner player per its mode, with corp membership and corp war (WP66)
  resolved through the same hostility helpers audited there. Core
  deployment-free rules already exclude the Core (assert, don't
  special-case).
- **Projection/TUI.** Another player's ship renders in the sector view as a
  clickable contact (name, corp tag, outlaw marker); `EncounterScreen`
  reuses as-is for the attacker; the defender's side is ticker/notification
  narrative. Fog: a cloaked player ship is subject to the same
  detection-vs-cloak projection rule as NPC hostiles (reuse the WP24
  detection math at the boundary).

Files: `edge/core/config.py`, `config/default.yaml`, `edge/core/combat.py`
(`player_foe`), `edge/core/rules.py` (`AttackPlayer`, territory-entry
extension, kill/bounty hooks), `edge/core/models.py` (fields landed at
WP66), `edge/core/events.py`, `edge/store/codec.py`,
`edge/server/session.py`, `edge/core/dto.py`, `edge/tui/screens/game.py`,
`tests/test_pvp.py` (new), `tests/test_territory.py`.
Tests: H18 reducer gating (pvp off / Core / pod-bound rejections); a full
PvP fight golden log (two scripted players, rebuild-hash equality);
salvage/pod conservation properties; outlaw bounty accrual + claim; lawful
vs criminal victim alignment matrix; territory engagement matrix
(owner/corp-mate/at-war/neutral × mode); cloak-vs-detection projection
parity with NPC rules.
Commit `p4: WP67 attacker-driven PvP + territory + outlawry`.

### WP68 — The hosted client (M)

- **`RemoteClient`** (`edge/server/client.py`): implements the WP61
  `GameClient` over a websocket — wire codec both ways, request ids,
  the WP62 fingerprint handshake, pushed-event consumption, and
  reconnect-with-catch-up (resume token + `events_since`). Timeouts
  surface as a status-bar "link lost — retrying" rather than crashes
  (the TUI's one concession to the network).
- **Entry points:** `edge --connect ws://host:port` (login/lobby screens —
  minimal Textual forms in `tui/screens/lobby.py`); `pixi run serve` gains
  the hosted recipe: `edge-server` + `textual serve "edge --connect …"` —
  documented in `docs/HOSTING.md` (ports, systemd sketch, save backup =
  copy the `.db`).
- **Latency posture:** no optimistic prediction — commands round-trip and
  views re-read (the TUI already re-reads after every apply; stated as the
  design: correctness over snappiness at LAN scales, per §2's tens-of-
  players goal).

Files: `edge/server/client.py`, `edge/tui/app.py`, new
`edge/tui/screens/lobby.py`, `pyproject.toml`/pixi tasks, new
`docs/HOSTING.md`, `tests/test_net.py` (client-side paths).
Tests: end-to-end in-process socket test — login → join → warp → trade →
event push received; reconnect catch-up mid-session; fingerprint mismatch
refused cleanly.
Commit `p4: WP68 remote client + hosted deployment`.

### WP69 — Multiplayer QA, bot swarms, exit criterion (M/L)

Prove the promises before calling Phase 4 done.

- **Bot swarm harness:** WP60's `BotRunner` driven through `RemoteClient` —
  N bots + optional humans against one `edge-server`. Scenarios: parallel
  traders (economy invariants under concurrent load), a co-located pair
  (broadcast visibility), corp lifecycle, a corp war ending in a PvP kill
  (pod, salvage, bounty claimed by a third bot — the WP67 stack end to
  end), and a governance flip with spectators.
- **Assertions:** after any swarm run, server-side `rebuild` from
  `(seed, command log, maintenance log)` reproduces the live `state_hash`
  (the single-writer queue makes this *the* multiplayer correctness proof —
  total order in, determinism out); fog fuzz — no DTO or pushed event ever
  names an unexplored sector for its recipient (extends WP65's property);
  no cross-player latinum/goods leaks (conservation audited via the WP59
  money-supply report).
- **Multi-player golden logs** join the regression suite (two-player trade +
  corp + PvP duel + flip fixture).
- **Docs + exit:** DESIGN §14 Phase 4 marked shipped; `HOSTING.md`
  finalized. Exit criterion: *two humans and a bot trade, explore, and share
  a corp planet in one universe hosted via `textual serve`; a grudge is
  settled by force outside the Core; and the server rebuild-hash check
  passes after the session.*

Files: `edge/bot/` (swarm driver), `tests/test_multiplayer.py` (new,
pytest-asyncio, marked slow), fixtures, `docs/DESIGN.md`, `docs/HOSTING.md`.
Tests: as above — the WP *is* tests.
Commit `p4: WP69 multiplayer QA + exit criterion` — **M21 / Phase 4 done.**

---

## Suggested order / commits (phase-tagged, small)

`p5: WP45` docs → `p5: WP46` market core → `p5: WP47` market wiring +
**config_version 4 + golden regen** → `p5: WP48` market view/balance →
**M16** → `p5: WP49` flip reducer → `p5: WP50` player seizure → `p5: WP51`
NPC governance → `p5: WP52` aftermath → **M17** → `p5: WP53` base services
→ `p5: WP54` citadels → `p5: WP55` planetary war → `p5: WP56` devices +
**config_version 5 + golden regen** → **M18** → `p5: WP57` contracts
(+M19 golden batch) → `p5: WP58` tavern → `p5: WP59` sysop → `p5: WP60`
scripting + protocol → **M19 / Phase 5 exit** → `p4: WP61` client facade →
`p4: WP62` wire codec → `p4: WP63` net server → `p4: WP64` lobby/auth →
**M20** → `p4: WP65` broadcast → `p4: WP66` corporations + corp war +
**config_version 6 + golden regen (incl. PvP fields)** → `p4: WP67` PvP →
`p4: WP68` hosted client → `p4: WP69` QA → **M21 / Phase 4 exit**.

**Hard dependencies:** WP46→WP47→WP48 (math → rail → view); WP49→WP50/WP51
(one flip reducer before either trigger) and WP49→WP52; WP53→WP56 (limpet
removal uses the ServicePoint) and WP53→WP54/WP55 only softly (screens
compose); WP54→WP55 (gun before siege); WP57 before WP58's contract panel
rows; WP60→WP61 (`ServiceProtocol` before the facade); WP61→WP63→WP64→WP65
→WP68 (facade → server → auth → broadcast → client); WP62→WP63 (codec before
transport); WP65/WP66→WP67 (the defender's broadcast experience and the
corp-war/hostility audits + epoch fields before PvP goes live); WP67→WP69
(the QA swarm exercises the duel). The sysop/scripting pair
(WP59/WP60) is parallel to the rest of M19; the market milestone (M16) is
parallel to M17 in principle — kept first because its epoch (v4) should land
before governance golden logs are recorded against it.

---

## Verification

- **Per WP:** the named test files; property tests for every new invariant
  (settlement conservation, purse bounds + liquidity floor, invasion
  conservation, corp bank, fog on DTOs *and* broadcast); golden-master
  replays regenerated **only** at the batched epochs (WP47, WP56, WP57,
  WP66), noted in each commit. Per project practice, the implementing agent
  reminds the user to run `ruff` / `mypy --strict` / `pytest` rather than
  assuming CI.
- **Economy:** the WP59 money-supply audit run on long bot sessions — every
  slip accounted to a named faucet/sink; the §8 first-upgrade ratio
  re-measured at WP48 and WP60.
- **Governance:** golden logs for all three flip causes (dev, player
  champion, NPC); the zero-touch assertions (law/occupancy/defense re-key
  with no code change) pinned permanently.
- **Dialogue:** WP57 runs the full `validate_dialogue` suite and
  `edge-playtest-dialogue` (force-enable) over the contract nodes; the H9
  spec-header/prompt sync is asserted by test, not review.
- **Multiplayer:** WP69's swarm + rebuild-hash equality is the standing
  regression; the fog fuzzers run in the normal suite (fast paths) with the
  socket swarms marked slow. PvP-specific: the H18 gating matrix (pvp off /
  Core / pod-bound) and the duel golden log run in the fast suite.
- **Playable checkpoints:** after M16 prices move without the player; after
  M17 the Core can change hands and the player feels it; after M18 a
  foothold services a deep-space campaign and a world can be taken by
  force; after M19 the tavern hums and bots can play the game; after M20 a
  second terminal joins; M21 ends on the hosted two-human session with a
  duel settled outside the Core.
