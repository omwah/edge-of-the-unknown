# Trading Enjoyability Plan

Status: proposed  
Scope: make the existing port-pair loop more enjoyable without replacing its economy or controls

## 1. Problem and design goal

Pair trading is the game's dependable income floor. The player finds two compatible
ports, buys at one, warps to the other, sells, and repeats until an upgrade becomes
affordable. The loop is legible and strategically useful, but its optimal play can
collapse into repeated navigation and quick-trade inputs between two screens.

The goal is not to make basic trading complicated. It is to give each arrival a
little context, variation, and forward motion while preserving:

- the three commodities, port classes, live prices, hard purses, and order book;
- the existing `TradePanel`, quick-trade, and optional haggle flow;
- deterministic `(seed, command log)` replay;
- trading as reliable income rather than a source of mandatory combat or surprise loss;
- the ability of a player who wants efficiency to trade just as quickly as today.

The best low-risk direction is to make a trade route feel like a relationship with
two places. Recent archetype-specific station art already makes ports visually
distinct. Short, staged port lore can make them memorable in prose as well.

## 2. Recommended feature: the trade-route travelogue

Every ordinary port receives a small, deterministic **port profile** based on its
immutable builder `archetype_id`, port class, distance band, and seed. The profile
supplies a local identity rather than new economic rules:

- a one-line epithet, such as “A Vesk pressure-market built into a spent refinery”;
- a resident voice or office, such as dockmaster, factor, union clerk, or shrine-keeper;
- two or three short lore beats revealed through normal commerce;
- one commodity-specific detail explaining what the port does with what it buys or
  where what it sells comes from;
- an optional connection to another port when the player repeatedly trades the pair.

The first dock shows the establishing line. The first completed trade reveals a
second detail. Repeated profitable visits eventually reveal a final “route story”
beat. A small **Route Notes** area in the Computer records unlocked text for both
ends of a familiar pair. This turns the same required trips into gradual discovery:
the player is still earning the upgrade, but is also learning who lives along the
route and why its goods move.

Example progression:

1. At **Glasswake Exchange**, the first arrival describes translucent storage
   bladders orbiting a `ribbon_salvager` hull.
2. Selling Equipment reveals that the salvagers rebuild navigation organs for
   ships whose original crews are long dead.
3. Carrying Organics back from **Morrow Agricultural Ring** unlocks a route note:
   Glasswake uses its share to culture replacement nerve-webs; Morrow receives
   repaired weather-control relays in return.

The reveal is informational and collectible. It does not change the quoted price,
consume cargo, require another button, or interrupt departure. A single fresh line
appears after the trade result and then lives in the logbook; familiar copy is not
replayed on every visit.

### Why this is the recommended first implementation

- It builds directly on the new station art and `archetype_id` instead of creating
  a parallel identity system.
- It adds anticipation to repetition without slowing the established input loop.
- It reinforces the exploration pillar: commerce discovers culture and local history.
- It is configuration-heavy and rules-light. Most value comes from authored content,
  a small deterministic selector, a projection, and a few UI lines.
- It remains compatible with Phase 5's moving market. A pair's story describes the
  places and their relationship, not a permanent guarantee of profitable prices.

## 3. Small implementation options

These options can ship independently. Options A–C combine into the recommended
travelogue; D and E are useful polish even if staged lore is deferred.

| Option | Player-facing effect | Relative effort | Persistent state |
|---|---|---:|---|
| A. Port establishing lines | Every dock has a short archetype-, band-, and class-aware description beneath its art. | Very low | None |
| B. Trade-result flavor | A successful trade can append a brief, commodity-aware local line, with repetition suppressed. | Low | Small per-port seen set, or only milestone lines |
| C. Port familiarity and route notes | First trade and later visit/profit milestones reveal two or three permanent lore entries; using both ends unlocks a paired-route entry. | Low–medium | Per-player port/pair familiarity |
| D. Upgrade progress cue | The trade result says how much remains for the player's pinned upgrade, for example “1,240 slips to Tier-II screens.” | Low | Reuse or add one pinned objective id |
| E. Arrival variation | The dock header chooses deterministic, non-mechanical ambience such as shift change, loading ritual, inspection queue, or market chant. | Low | None if keyed by day/visit context |

### A. Archetype-aware establishing lines

Add a config corpus keyed by `archetype_id`, with optional variants for port posture,
commodity, band, and size. Combine authored fragments deterministically so two ports
of one archetype share a cultural visual language without receiving identical text.
Keep generated facts truthful: prose may name the port's actual buy/sell posture but
must never promise stock, price, safety, ownership, or services that the live DTO does
not support.

This is the smallest useful release. It changes no core rules and can initially be
derived entirely from existing projected facts.

### B. Commodity vignettes after successful trades

Give each archetype a few short reactions for Fuel Ore, Organics, and Equipment,
split by whether the port bought or sold. Show them only at meaningful boundaries:
first transaction, first large transaction, or a familiarity milestone. Do not show
flavor after every ten-unit quick trade; that would replace button monotony with text
monotony.

Examples of useful content are local labor, manufacturing methods, cuisine,
superstitions, or the reason a culture values a commodity. Flavor must not imply a
mechanical bonus unless one actually exists.

### C. Familiarity stamps and paired-route notes

Track compact per-player counters or milestone bits rather than a full quest system:

- first dock or first completed trade at a port;
- a small number of completed trade visits, counted once per docking session;
- whether the player has traded at both ports in a recently used compatible pair;
- optionally, lifetime gross profit on that pair for milestone purposes only.

The important metric is **visits with completed commerce**, not number of button
presses. Splitting one cargo sale into many commands must not farm familiarity.
Suggested reveal ladder: introduction at first trade, local detail at three trading
visits, paired-route note after three completed circuits. Tune these in config.

Expose unlocked entries through the existing Computer/Logbook structure, ideally as
a small Route Notes view or as entries in Notes. The collection should be finite and
visible, for example “Glasswake Exchange: 2/3 notes,” so repetition has a nearby end.
Do not attach power or price bonuses in the first version; lore is the incentive and
the economic profit remains the reward.

### D. Pin an upgrade target

Allow the player to pin a ship, component, armament, or device from an existing
catalog. Trade confirmations then show progress toward it. This gives the grind a
clear horizon and makes each circuit feel consequential without changing its length.
It also directly supports the intended `trade → upgrade → explore farther` loop.

This option has unusually high value for its size and should accompany the lore work
if the relevant catalog DTOs already expose stable item ids and prices.

### E. Non-blocking port ambience

Select one brief arrival detail from archetype-aware pools. Key selection to stable
facts such as port id and game day; never draw randomness during a projection. Put
ambience in the art caption or event ticker, not in a modal. It should be easy to
glance past and should not move focus away from the highlighted commodity.

## 4. Other reasonably easy alternatives

### Trade-route naming

After several circuits, offer a one-action suggestion to name the route locally in
the player's notes. The Computer can then say “Ashglass Run” instead of only listing
sector numbers. This creates ownership with almost no rules impact. Automatic names
can combine the two port names, dominant commodity, or archetype vocabulary.

### Port passport

Give each newly traded port an archetype-styled passport stamp and show completion by
distance band or builder archetype. This is more overtly game-like than prose lore and
works well for players who skim text. It encourages trying another viable pair after
one route becomes familiar, but should not require visiting every generated port.

### Rumor with every familiarity milestone

An unlocked port note may include a fog-safe rumor about an already explored nearby
place, known market movement, or a generic cultural lead. Reusing only information
the player is already allowed to know keeps this presentation-only. Revealing a new
sector, discovery, or market fact would be a separate rules feature and belongs in
the higher-effort tier.

### “Best run” summary

When leaving or after completing a circuit, show a compact summary: turns spent,
gross profit, profit per turn, and progress toward the pinned upgrade. This gives the
player a small optimization game without modifying the economy. It should summarize
a route automatically and never require bookkeeping during each transaction.

## 5. Higher-effort options

### A. Port storylets

Ports occasionally offer a short, authored situation tied to their archetype and
commodity posture: a dock strike, a disputed cargo seal, a ceremonial inspection,
or a request to carry a harmless personal parcel to the paired station. A choice can
alter a small reward, alignment, standing, or later text.

This is attractive but needs a real replay-safe command/event/state model, eligibility
rules, recency, save migration, validation, and enough content to avoid obvious
repetition. It also risks turning routine docking into modal friction. Storylets should
be opt-in from the port screen and should never block ordinary trade.

### B. Micro-contracts generated from market shortages

Offer a limited delivery commission when a known port has a genuine shortage:
deliver a quantity by a deadline for a modest premium or a lore/standing reward.
This reuses the existing contract and order-book foundations and gives a player a
reason to select a route rather than only accept the mathematically best pair.

This requires careful reward tuning so contracts do not replace ordinary arbitrage,
fog-safe offer generation, deadline/progress UI, and safeguards against being paid
twice for the same units. It should extend Phase 5 contracts, not create a second
contract vocabulary in port code.

### C. Route incidents

Once a route becomes familiar, rare events can alter one circuit: a customs hail,
distress call, merchant convoy, temporary hazard, or optional detour. The event gives
the repeated path a changing rhythm and can connect port lore to the space between
the ports.

This is substantially more expensive because it touches movement and encounters,
needs deterministic scheduling, and can disrupt the dependable income floor. Incidents
must be uncommon, telegraphed, and usually optional; they should not routinely make a
known profitable run lose money or turns.

### D. Port reputation and services

Repeated fair dealing could build local reputation that unlocks cosmetic recognition,
better market intelligence, a small service, or access to special inventory. This
makes the relationship systemic, but price discounts are dangerous: they reward the
already optimal route and make switching routes feel punitive.

If implemented, prefer horizontal benefits such as a rumor, stale order-book preview,
one free route note, or access to an optional contract. Avoid permanent commodity
price multipliers until economy simulations show they cannot compound into a dominant
strategy.

### E. Merchant rivals and recurring characters

A named NPC trader may work the same pair, appear in port lore, affect stock through
real trades, and develop a friendly rivalry with the player. This makes the market's
existing NPC circulation visible and personal.

It needs identity persistence, NPC schedules or goal selection, dialogue, projection,
and behavior when the NPC moves elsewhere or is destroyed. It is a strong long-term
feature, but not a minimal trading polish item.

## 6. Proposed data and layer boundaries

The first release should introduce the least state that produces visible value.

### Configuration

Add a dedicated port-lore config file rather than putting prose in Python. A likely
shape is:

```yaml
archetypes:
  ribbon_salvager:
    epithets: [...]
    arrivals: [...]
    commodities:
      equipment:
        port_buys: [...]
        port_sells: [...]
    familiarity:
      first_trade: [...]
      regular: [...]
    route_links: [...]
```

Templates may use a small closed placeholder set such as `{port_name}`, `{commodity}`,
`{band}`, and `{other_port_name}`. Validate unknown archetypes, missing pools, invalid
placeholders, and empty variant lists at config load. This is port lore, not alien
conversation: do not expand the §6.7 dialogue intent/branch machinery unless port
storylets later need genuine choices.

### Core

For establishing lines alone, no core change is required. Familiarity adds a compact,
hashed per-player structure keyed by port id and a canonical unordered or directed
port-pair key. Update it only after a successful non-zero trade. Count at most one
qualifying visit per dock session so repeated quick-trade presses cannot advance it.

If profit milestones are used, calculate them from authoritative before/after balances
or explicit trade outcomes. Do not parse event copy. Lore selection itself should be
pure and deterministic; reducers record which finite milestone was unlocked.

### Server projection

Project only lore the player has unlocked plus the one current arrival line. Keep fog
intact: a route note must not name an unexplored port merely because a config template
or global pair finder knows it exists. The server supplies resolved display data; the
TUI must not inspect raw state or choose lore variants.

### TUI

Reuse `StationArtHeader` and `TradePanel`. Add at most:

- one or two caption lines between station art and the trade table;
- a non-blocking unlock notification after a successful trade;
- a Logbook/Notes destination for accumulated entries;
- optional pinned-upgrade progress in the trade result detail.

At 80×24, decorative lore should collapse before controls do. Focus, selected
commodity, and the `T`/`G` trade flow must remain unchanged.

## 7. Delivery sequence

### TR-01 — Port identity captions

- Define and validate the port-lore config corpus.
- Deterministically resolve an epithet and arrival line from port id,
  `archetype_id`, class, band, and current posture.
- Project and render the lines under existing station art.
- Cover every configured archetype with generic fallback behavior.

Exit criterion: ports of different archetypes sound different, two same-archetype
ports are distinguishable, projections draw no randomness, and compact trading is
no slower than before.

### TR-02 — Familiarity and lore reveals

- Add first-trade and repeat-visit milestone state and events.
- Suppress farming by counting completed trade visits rather than commands.
- Render a new line once at unlock, then store it in the player's notes.
- Add save/codec/replay/state-hash coverage for the new state.

Exit criterion: three ordinary circuits reveal staged lore exactly once and replay
to the same state and wording.

### TR-03 — Paired-route notes and progress cue

- Recognize a pair from actual player trade activity, not merely route-planner advice.
- Unlock a joint note after a configured number of completed circuits.
- Add collection progress and optional route naming in Computer/Notes.
- Add pinned-upgrade progress to trade summaries if stable catalog ids permit it.

Exit criterion: a player saving for an upgrade sees both financial progress and a
finite narrative payoff while using the unchanged pair-trade controls.

### TR-04 — Evaluate before adding mechanics

Playtest the minimal release before choosing a higher-effort option. Capture:

- how many circuits occur before the first affordable Tier-I and Tier-II upgrade;
- how often a circuit produces fresh lore;
- whether players read the caption without it delaying trade;
- whether collection progress encourages route variety;
- whether players can still execute a familiar circuit at the previous input speed.

Only then choose between market-derived micro-contracts, optional storylets, or route
incidents. The likely next step is micro-contracts because Phase 5 already supplies
contract and order-book seams.

## 8. Tests and acceptance criteria

- Fixed seed plus command log produces identical port profiles, unlock order, and text.
- Projections never advance RNG or reveal an unexplored port.
- Zero-fill, rejected, or unaffordable trades do not advance familiarity.
- Many trade commands in one docking session count as one qualifying visit.
- Reload and replay preserve unlocked lore and do not repeat its notification.
- Every active `archetype_id` resolves valid content or an explicit generic fallback.
- Every rendered placeholder is drawn from the closed, validated set.
- Existing economy property tests remain unchanged: goods and latinum are conserved,
  balances and purses stay non-negative, and quoted-price monotonicity still holds.
- Existing `TradePanel` keyboard/mouse flows and commodity selection remain intact at
  compact, standard, and wide layouts.
- Lore never claims a price, stock level, service, owner, safety state, or route fact
  contradicted by the live projection.

## 9. Recommendation

Implement TR-01 through TR-03 as one small feature arc, with TR-01 independently
shippable. Combine archetype-aware captions, three finite familiarity reveals, a
paired-route note, and pinned-upgrade progress. This is enough to change the emotional
shape of pair trading—from anonymous repetition into a short relationship with two
places—while leaving its proven economic mechanism and rapid controls alone.

Defer price bonuses, random route interruptions, and modal storylets. They add more
balance and pacing risk than the initial problem requires. If the minimal version
tests well but still needs systemic variety, extend the existing Phase 5 contract
system with market-derived micro-contracts as the next step.
