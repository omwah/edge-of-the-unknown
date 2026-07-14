# Trading Enjoyability Plan 02 — the competing plan

Status: proposed (competes with `docs/TRADING_ENJOYABILITY_PLAN.md`)
Scope: make trade *interesting to play*, not just interesting to read about

## 1. Where this plan disagrees

Plan 01 diagnoses pair trading as **anonymous** and prescribes prose: archetype
epithets, staged lore, familiarity stamps, route notes. That work is good and cheap,
and much of it should ship regardless. But it treats a **decision problem** as a
**presentation problem**.

The honest diagnosis: after the player picks a pair, *the loop contains no further
decisions*. Buy-max, warp, sell-max, warp back. Optimal play is a fixed point. The
player is not bored because the ports are nameless; they are bored because they have
already won and are now executing. Lore laid on top of a solved loop is text you read
once and then skip — it decays into a second layer of monotony (Plan 01 half-admits
this in §3B: "that would replace button monotony with text monotony").

The premise of this plan:

> **Trade becomes enjoyable when the correct answer changes, when the player can see
> enough of the market to have opinions about it, and when mastery graduates you out of
> hauling instead of deeper into it.**

Three levers, in that order:

1. **Legibility** — the economy already has depth (elasticity slippage, hard purses,
   an order book, hinterland drift). Almost none of it is visible. The player is
   playing a rich game blind and is therefore playing it stupidly.
2. **Volatility** — a static map has one best route forever. Make the optimum *move*,
   deterministically and telegraphed, so route-finding is a recurring skill rather
   than a one-time lookup.
3. **Graduation** — the endgame answer to a solved loop is not to decorate it but to
   let the player *stop personally executing it*: delegate it, or own it.

Everything Plan 01 preserves — three commodities, the order book, `(seed, command log)`
replay, trading as a dependable income floor, and the ability of an efficient player to
trade as fast as today — this plan preserves too.

## 2. What's already there and invisible (the free win)

Reading `edge/core/economy.py` and `edge/core/market.py`, the game already simulates:

| Live mechanic | Player-visible today? | Latent decision it creates |
|---|---|---|
| Price moves with `stock_ratio` × `elasticity` | No | **Slippage**: dumping 200 units into one port earns less per unit than splitting the load. Nobody knows this. |
| Hard port purse; buy-side **partial fill** | Only as a surprise after the fact | Which port can actually *pay* me today; how much to bring. |
| `liquidity_drip` refills purses toward `size × min_purse_per_size` daily | No | Wait a day, or take the partial? Big ports pay; small ports choke. |
| `hinterland_drift` + order-book settlement move goods between ports nightly | No | Prices *drifted overnight*. The player never sees the delta. |
| Haggle `history_penalty` stiffens a port you keep working | No | Rotating ports has a real payoff already. |

**A large fraction of the fun is already implemented and simply not rendered.** Before
authoring a single line of port lore, render this. It is the highest
enjoyment-per-line-of-code in the whole document, and it is nearly free: a projection
over state that already exists.

## 3. The idea ladder

Ordered low → high impact. Effort and risk are my estimates; each tier is independently
shippable and does not require the tier above it.

### Tier 0 — Legibility (very low effort, surprisingly high impact)

**0.1 The price tape.** Keep a short ring buffer of each port's last N daily quotes
(per commodity, per side) and render a sparkline plus an arrow on the trade panel:
`Equipment 17 ▲ (was 14 three days ago)`. Suddenly the market is a thing that *does
something* between visits. Cost: one small ring per port, one projected field.

**0.2 The slippage preview.** The trade panel already knows the quantity in the
selector. Show the *marginal* and *average* fill price as the quantity climbs:
`80 u @ avg 16.2 (last unit 14.9)`. This converts an invisible curve into a visible
one, and instantly creates a genuine tactic — split the cargo across two buyers — that
the mechanics already reward and nobody is playing.

**0.3 The purse gauge.** Show what the port can actually pay: `purse 3,410 — will fill
~210 u of your 300`. Partial fill stops being an annoyance and becomes a plannable
constraint. Add the drip forecast (`+850/day`) so "come back tomorrow" is a real move.

**0.4 Profit-per-turn, live.** Every trade result and the route planner already have the
numbers. Show `profit/turn`, the only metric that actually ranks routes, and rank the
Computer's pair finder by it. Optimization is a game; give the player its scoreboard.

**0.5 Haggle heat.** Surface the accumulating `history_penalty` (`this factor is tired
of you: −24% haggle`). It's an existing anti-monotony incentive that is currently a
secret.

> Tier 0 changes **zero rules**. It is a projection + TUI arc. My claim is that Tier 0
> alone moves trading from "press T" to "read the tape and decide," and it should ship
> before anything else in either plan.

### Tier 1 — Cheap decisions (low effort)

**1.1 Cargo composition.** Holds are undifferentiated capacity; nothing stops a
full-hold single-commodity run. Make the buy screen a *portfolio* screen: the pair
finder proposes a mixed load (e.g. 60 Organics + 40 Equipment) when one port's purse
can't absorb a monolithic sale. Same trip, real allocation choice.

**1.2 Standing orders / limit orders for the player.** The ports post limit orders into
a book (`market.py`); the player cannot. Let the player leave a **standing bid or ask**
at a docked port that settles overnight against the same matcher. "Sell 200 Fuel Ore at
≥13" executes while you're off exploring three sectors away. This is a small,
architecturally *native* feature — the matcher already exists — and it gives trading a
second time-axis. Massive fun-per-effort.

**1.3 Consignment & the empty leg.** Reward the return trip that is currently dead
weight: a port with excess stock will consign cargo to you (you pay nothing up front,
you owe a % on sale, you eat the risk). Turns "warp home empty" into a decision.

**1.4 Bulk contracts at the dock.** Not Plan 01's narrative micro-contracts —
*market-native* ones, generated straight from the order book's own unfilled demand:
"this port's bid for 400 Equipment went unfilled at settlement; fill it in 4 days for a
premium." Zero new content vocabulary; it is the book asking for help.

### Tier 2 — Make the optimum move (medium effort, the core of this plan)

This is the tier that actually kills monotony. A static universe has one best pair
forever; the fix is not decoration, it's **a market that changes underneath the player
in ways they can read and anticipate.**

**2.1 Hinterland events (news, not noise).** Each port's off-map hinterland gets
occasional, deterministic, *telegraphed* events that swing its desired stock or purse
for a bounded window: a harvest, a refinery fire, a dock strike, a colony boom, an
alliance requisition. Schedule them from `(seed, day, port_id)` — no RNG in projection,
fully replay-safe. Publish them on a **news feed** in the Computer with lead time:
`Morrow Ring: harvest in 2 days — Organics glut expected`.

The player's job stops being "find the pair" and becomes "**read the board and
reposition.**" That is a renewable skill, not a solved lookup. It also makes Plan 01's
lore *matter*: the strike at Glasswake is both a story beat and a price signal.

**2.2 Spread decay under exploitation (the anti-farming rule).** The single most
important mechanic in this document. Today, farming one pair forever is optimal and
boring. Make the market *notice*: sustained one-sided player volume on a pair pushes
both ports toward their desired stock and pulls NPC traders (they already circulate) to
the same lane, so **the spread you farm decays**. Rest the route and it recovers.

This is not a punishment; it is the game telling the truth about arbitrage, and it
converts route-hopping from a flavor preference into the *dominant strategy*. Combined
with 2.1, the player is permanently, pleasantly, hunting.

Tuning guard-rail: decay must be gentle and asymptotic to a floor. The income *floor*
stays dependable (an AGENTS.md pillar); it is the *outsized* spread that erodes.

**2.3 Speculation.** With 2.1 and 2.2 in place, holding cargo becomes strategy: buy the
glut, sit on it, sell into the shortage. Cargo capacity becomes a *position*, not a
bucket, and the engine-room upgrade path acquires a second motive. No new systems — it
falls out of volatility + visible history.

**2.4 Regional and political price structure.** Prices are per-port; make them *mean*
something regionally. Distance band already shifts risk; let alliance politics shift
*price*: a bloc's cluster pays a premium for what its rivals embargo. Now the map has
economic geography, and picking a bloc (an existing, weighty choice) reshapes your
trade options rather than just your combat ones.

### Tier 3 — Graduation (high effort, high payoff)

The premise is that trade is *a means to an end*. Then the correct endgame for a
mastered trade loop is not more trade loops.

**3.1 Delegation: hire haulers.** Once you have run a route profitably, you may **buy a
hauler and assign it to that route.** It runs the circuit on the tick, takes its cut,
suffers the same spread decay, and can be intercepted. The player's turns are freed for
the thing the game is actually about — exploration — while their income compounds.

This is the deepest idea here and the most aligned with the game's stated pillar. It
reframes the whole loop: *you play the route until you understand it well enough to
automate it, then you go find the next frontier.* Monotony is not decorated — it is
**delegated away as a reward for mastery.** It also gives latinum a genuine investment
sink and turns the mid-game into a small logistics empire.

Risks to control: a hauler must never out-earn the player's own attention (cut its
margin), must be at risk (pirates, hostile blocs — a reason to escort or to buy
sensors), and must be capped so this is a business, not an idle game.

**3.2 Own the port.** The seam exists: bases are already ports with an owner commission,
planets already produce by `yield_profile` and habitability, colonists already ride
their own capacity. Close the loop: **your colony produces → your orbital base posts
orders into the book → NPC ports and NPC traders buy from you.** The player graduates
from courier to *node in the economy*. Every existing system (colonization, engine-room
components, starbase defense, alliance hostility) suddenly serves the trade game, and
the trade game serves them back.

**3.3 Cornering and market-making.** With a visible book (Tier 0) and player limit
orders (1.2), let a rich player *move* a regional price: buy out a commodity across a
cluster, then sell into the hole they made. High skill ceiling, emergent, entirely
built from parts that already exist. Needs simulation before shipping — it is the one
idea here that can genuinely break the economy — but it is the natural apex of a game
whose economy is an order book.

**3.4 Contraband.** Alliance politics already gate hostility; let them gate *cargo*. An
embargoed commodity pays a large premium in a bloc that bans it, and running it means
sensor/cloak checks at the border. This makes trade *tense* without making it combat,
gives cloak and sensors a peaceful use, and makes the alliance choice bite economically.

## 4. What I would actually build

A three-milestone arc. Each ships value alone; each makes the next more valuable.

**M-A — "Show me the market" (Tier 0 + 1.2).**
Price tape, slippage preview, purse gauge and drip forecast, profit-per-turn ranking,
haggle heat, and player limit orders into the existing matcher.
*Exit criterion:* a playtester can explain **why** a route is good, changes their fill
size because of the slippage curve, and leaves a standing order before going exploring.

**M-B — "The board moves" (2.1 + 2.2, then 2.3 falls out free).**
Deterministic telegraphed hinterland events on a news feed; spread decay under sustained
exploitation with a dependable floor; speculation emerges.
*Exit criterion:* over a 90-minute session the player's best route changes at least
twice, they anticipated at least one change from the news feed, and total income is
within a tuned band of today's (the floor held).

**M-C — "Stop hauling" (3.1, then 3.2).**
Hire a hauler for a known route; then let an owned base post orders into the book.
*Exit criterion:* a mid-game player's income continues while they spend a session doing
nothing but exploring, and they choose *which* routes to automate.

Plan 01's TR-01/TR-02 (captions and staged lore) should ship alongside M-A — cheap,
orthogonal, and much better once the ports they describe are also economically alive.
I would drop Plan 01's familiarity-milestone bookkeeping (it rewards the repetition we
are trying to eliminate) and let the **news feed** carry the flavor instead: the same
authored voice, attached to something that changes the price.

## 5. Layer boundaries (non-negotiables preserved)

- **Determinism.** Hinterland events are a pure function of `(seed, day, port_id)`;
  spread decay is a pure function of recorded volume; the settlement matcher is already
  pure. No RNG in projections. `(seed, command log)` replay is untouched.
- **`edge/core`** gets: a bounded price/volume ring per port, an event schedule
  (pure derivation, not stored draws), a decay term folded into desired-stock, and
  player orders in the existing `PortOrder` book. Conservation asserts in `market.py`
  stay as they are — player orders settle through the same matcher, so goods and
  latinum still sum to zero.
- **`edge/server`** projects only what fog allows: the tape and news for ports the
  player has visited or has intel on. A shortage at an unexplored port is not a hint
  you get for free (that's a discovery, and discovery is the other pillar).
- **`edge/tui`** reuses `TradePanel` and `StationArtHeader`. Compact-layout rule: at
  80×24 the tape and gauges collapse before controls do. `T`/`G` flow unchanged and
  no slower.
- **Haulers and owned-base orders** run on existing crons (`market_settlement`,
  `port_economy`) — no new scheduler.

## 6. Tests

- Same seed + command log ⇒ identical price tapes, identical event schedule, identical
  decay curve, identical fills.
- Player limit orders obey the same conservation invariant as port orders (stock deltas
  sum to zero; latinum deltas sum to zero; no purse goes negative).
- Spread decay is bounded: property test that a farmed pair's profit/turn asymptotes to
  a configured floor > 0 and *never* inverts to a loss.
- Hinterland events never violate the price clamp `[floor_frac, ceiling_frac] × base`.
- Projections never advance RNG and never reveal an unexplored port's tape or news.
- Haulers cannot mint goods: every hauler circuit is a normal trade through the same
  reducers.
- Existing economy property tests unchanged.

## 7. The honest comparison

| | Plan 01 (travelogue) | Plan 02 (this) |
|---|---|---|
| Diagnosis | Ports are anonymous | The loop has no decisions |
| Fix | Authored prose + collectibles | Legibility, volatility, graduation |
| Cost | Content-heavy, rules-light | Rules-heavy, content-light |
| Risk | Text monotony; players skim; the loop is still solved | Balance risk — decay/events/cornering can destabilize the income floor |
| Longevity | Finite (lore is consumed once) | Renewable (the optimum keeps moving) |
| Serves the pillar? | Indirectly (commerce reveals culture) | Directly (trade funds and then *frees* exploration) |

They are not exclusive, and the best outcome is a merge: **Plan 02's Tier 0 + Tier 2
with Plan 01's authored voice attached to the news feed.** If only one thing ships, ship
Tier 0 — the game is already more interesting than it looks, and nobody can see it.
