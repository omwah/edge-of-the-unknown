# Trading Enjoyability Plan 04 — Preparation and Place-Making

Status: proposed (competes with `docs/TRADING_ENJOYABILITY_PLAN.md`,
`docs/TRADING_ENJOYABILITY_PLAN_02.md`, and
`docs/TRADING_ENJOYABILITY_PLAN_03.md`)

Scope: make necessary trade feel purposeful by letting the player choose what a
deal advances and by letting commerce leave visible, useful changes in the galaxy

## 1. The fourth diagnosis

The existing plans identify three real problems:

- Plan 01 says ports are anonymous and gives repeated routes narrative identity.
- Plan 02 says the optimum is solved and makes the market legible, volatile, and
  eventually automatable.
- Plan 03 says cargo is physically passive and connects hauling to ship load and
  environmental hazards.

This plan starts somewhere else:

> **Trade feels monotonous because its result is delayed and fungible. Every run ends
> in more slips, while the thing the player actually cares about—an expedition, an
> upgrade, a foothold, or a discovery—happens later and somewhere else.**

The answer is to make commerce a visible act of **preparation and place-making**.
A trade should answer at least one of these questions immediately:

1. What did this deal make possible for my next expedition?
2. Whose trust or assistance did I choose to earn instead of taking every last slip?
3. What changed at this port or in this region because goods actually arrived?

This does not make trading the game's end state. It shortens the emotional distance
between `sell cargo` and `push farther outward`, and it gives a repeated route a finite
purpose: provision something, watch it come online, then use it to explore.

## 2. Design promises

Every idea below preserves the authoritative constraints in `DESIGN.md`:

- Fuel Ore, Organics, and Equipment remain the only commodities.
- Ordinary pair trading remains a reliable cash floor. The player may always take the
  normal quote and leave without participating in another system.
- Tier III technology remains discovery/barter gated; commercial rewards cannot turn
  slips into the progression ceiling.
- Colonists remain people who are recruited and transported separately, never project
  materials or trade goods.
- A trade conserves goods and cannot overdraw a player or port purse. A completed
  construction project may consume reserved goods through an explicit event, just as
  production and other world processes have explicit sources and sinks.
- All choices are commands and all outcomes replay from `(seed, command log)`. Views
  never draw randomness or inspect hidden state.
- New services resolve through the existing service-point seam. The TUI never reaches
  into core state.
- The fast `T`/`G` path remains the default. Purposeful options are adjacent to trade,
  not modal interruptions inserted into every transaction.

## 3. Idea ladder: low impact to transformative

The tiers describe impact on the game, not a mandatory dependency chain. Tier 0 can
ship alone. Tier 1 needs no regional projects. Tier 3 should be considered only after
the smaller ideas prove that players enjoy choosing non-cash outcomes.

### Tier 0 — Remove advancement friction (very low impact)

These ideas change no prices and add no new rewards. They make the existing
`trade → upgrade → explore` promise easier to execute.

#### 0.1 Reserve-aware Max

Let the player set a protected cash reserve for the next repair, component, hull, or
expedition loadout. The buy quantity control gains a second maximum:

```text
MAX 75       SAFE MAX 48       2,060 slips protected for Tier-I navigator
```

`SAFE MAX` is only a client convenience calculated from a server-projected preview;
the ordinary `MAX` remains available. This prevents the common anti-fun outcome where
the player completes several profitable circuits, reflexively fills the holds, and
discovers they once again cannot buy the upgrade they were supposedly trading toward.
The reserve is a player preference or a stable catalog target, never an escrowed
balance and never a second wallet.

#### 0.2 Procurement checkout

At Stardock or another valid service point, allow one atomic **Sell and Fit** preview:

```text
Sell 62 Equipment here, then install Tier-I radiator
Trade proceeds          +930
Component and fitting -2,000
Balance after             184
```

The command composes the existing authoritative trade and purchase/install reducers.
If either leg is no longer valid, neither commits. This is not a discount or barter
system; it simply removes the screen-changing ceremony between earning the money and
receiving the capability. The player experiences the trade as “I obtained a radiator,”
not “a number increased and later another number decreased.”

#### 0.3 Departure readiness card

The Computer can define a local expedition checklist from existing state: desired
repair level, repair kits, missile count, free holds, and a pinned route or discovery
lead. After a trade, show one compact, truthful state transition:

```text
OUTWARD RUN: READY — repairs funded, 3 kits aboard, 41 free holds
```

This is deliberately not a quest, reward, or lore milestone. It is an immediate cue
to stop grinding. Its success metric is that players leave the profitable pair sooner.

### Tier 1 — Choose what the deal advances (low-to-medium impact)

Today every ordinary trade optimizes one dimension: slips. Add optional **deal terms**
that let the player exchange a bounded part of the cash margin for a benefit already
present in the game's progression systems.

#### 1.1 Cash, standing, or intelligence terms

Before confirming a qualifying trade, the player may select one of a small set of
terms. Availability is derived from live ownership, species, services, and known facts:

- **Market terms** — the normal quote. Maximum slips, no extra effect.
- **Relationship terms** — voluntarily accept a configured worse quote in exchange
  for an explicit increase to the existing species attitude or alliance standing.
  This is available only where a real controlling species/alliance can receive the
  benefit. It makes “trading builds attitude” intentional instead of an invisible
  side effect.
- **Information terms** — waive a bounded part of the proceeds for one legitimate,
  stale lead: a market observation, a known neighboring hazard, or an Entity lead from
  a source allowed to know it. This reuses the existing lead/intel rails and obeys fog;
  it never exposes arbitrary unexplored state.
- **Service terms** — at a real service point only, route some proceeds directly into
  a repair, resupply, or fitting included in the same atomic command. This is the
  mechanical form of procurement checkout, not a new service-credit currency.

The crucial rule is **no hidden best choice**. The confirmation shows the exact cash
given up and the exact standing, lead age, or service received. Quick trade always uses
Market terms. A player who wants only reliable income is never taxed for ignoring this.

#### 1.2 Introductions instead of reputation grinding

A port or species may recognize a player as a commercial partner after a small set of
**distinct useful acts**, such as trading two different commodities or doing business
at two holdings of the same bloc. Count each fact once; never count command volume,
split transactions, lifetime profit, or repeated circuits.

An introduction unlocks horizontal access—a named factor on the contact menu, one
additional information term, or eligibility to propose a local project. It must not
grant a permanent commodity-price multiplier. This rewards breadth and closes quickly,
instead of attaching another experience bar to the grind.

#### 1.3 Commercial dilemmas

Occasionally a port can expose two mutually exclusive, fully stated uses for a scarce
shipment. For example, Equipment can restore the survey office or reinforce the
orbital screens. The player receives the same normal payment either way; the choice
decides which local capability becomes available first.

This differs from a storylet: there is no authored moral vignette and no surprise
consequence. It is a small infrastructure choice expressed through actual goods. Use
it sparingly—at most once while developing a port—so it creates authorship rather than
another prompt on every dock.

### Tier 2 — Ports that visibly develop (medium-to-high impact)

This is the centerpiece. Selected non-Core ports receive one bounded **local
development project**. A project is a public piece of world state, not a private
delivery contract and not a bar that advances merely because the player clicked Trade.

#### 2.1 Project-backed demand

A project reserves a finite requirement from the sacred trio, for example:

```text
Kestrel Reach Survey Relay
Fuel Ore    180 / 180
Organics     74 / 120
Equipment   210 / 300
Outcome: fresh regional hazard scans and more precise discovery leads
```

Its demand enters commerce honestly:

- the port pays for qualifying units from its real purse;
- transferred units leave the ship and enter a project reserve atomically;
- ordinary port stock and project-reserved stock are distinct and visible;
- no premium is required—the persistent outcome is the additional reward;
- NPC traders may contribute through the same market if simulations show the player
  still has time to participate;
- on completion, one `PortProjectCompleted` event consumes the reserve and activates
  the configured outcome.

This is not Plan 02's bulk contract. No player accepts it, no cargo is privately
tagged, no deadline punishes failure, and no one receives a completion purse. It is a
shared change to a place that proceeds only as real goods reach it.

#### 2.2 A small, horizontal project vocabulary

Projects should make a port more useful for exploration without creating an income
snowball. Good initial outcomes are:

- **Survey relay** — provides fresh hazard information and improves the precision,
  not the existence, of leads within already legitimate knowledge bounds.
- **Repair berth** — turns an eligible friendly port into a paid field-repair service
  point. It does not provide free repairs or Tier-II/III components.
- **Search-and-rescue office** — improves local recovery information and can reduce a
  configured service fee after an escape-pod loss; it does not prevent loss.
- **Xenological exchange** — adds a legitimate contact/introduction opportunity with
  a species already present in the region; it does not change base disposition.
- **Navigation office** — unlocks richer route warnings and known safe alternatives;
  it does not add warps or remove hazards.

Avoid first-order profit upgrades such as permanent price bonuses, purse multipliers,
or free cargo. Those compound into “farm the port that rewards farming.” Avoid generic
stat buffs, which turn place-building into an invisible modifier stack.

#### 2.3 The port remembers what was built

Completion must be unmistakable and permanent:

- station art gains a small overlay or caption without changing its immutable
  `archetype_id`;
- the sector and Computer directory show the new service/intel capability;
- arriving NPC traders and local contacts may use the facility through ordinary
  systems;
- the project never resets for another reward cycle.

A completed port is a landmark the player helped make. Repeating one route now has a
visible endpoint, and the reward is a better launch point for the exploration game.

#### 2.4 Player-owned footholds use the same language

The same project schema can later describe provisioning upgrades at a player-owned
orbital starbase: stock a repair workshop, survey office, or rescue beacon and then
pay normal service fees there. This should wrap the existing Phase-5 service-point
rules, not invent a second base-service implementation. Player bases remain stronger
and more configurable than NPC-port projects; schema reuse is the goal, not feature
parity.

### Tier 3 — Trade underwrites exploration (high impact)

Once the player has an introduction or helps complete a project, that place can offer
an **expedition partnership**. This is the high-impact expression of the plan: commerce
does not merely fund exploration indirectly; a commercial relationship shares the
risk of one outward journey.

#### 3.1 Expedition partnerships

The player proposes an objective from facts they actually know: investigate a lead,
scan a target region, make first contact with a named species, or return from a chosen
distance band. The partner offers a deterministic package such as:

- repair and fitting at a disclosed discount;
- a bounded number of repair kits or missiles from real inventory;
- fresher route/hazard intelligence;
- an advance against expected ordinary salvage.

In return, the partner takes a disclosed share of **fungible** proceeds brought back:
latinum or ordinary cargo salvage. The player always keeps codex credit, unique
devices, artifacts, ancient technology, and Tier-III progression items. A sponsor must
never buy the discovery ceiling.

The contract ends when the player returns, expires, or is explicitly abandoned. It
does not demand a prescribed cargo delivery and it does not spawn a discovery. It
changes the risk profile of an expedition the player already wanted to attempt.

#### 3.2 Competing patrons

At high standing, two blocs might offer different support for the same player-chosen
expedition: better repairs from one, better intelligence from another. Accepting one
is a visible political choice and may be unavailable when alliance rivalry makes the
relationship incoherent. It cannot override the one-alliance rule, erase grudges, or
make the hostile Core safe.

This adds strategic texture without growing a diplomacy tree: one expedition, one
partner, existing standing and rivalry predicates.

#### 3.3 A repeating macro-rhythm, not a repeating route

The intended late-game cadence becomes:

1. trade where a relationship or project is useful;
2. choose whether to take cash, standing, information, or immediate service;
3. finish a bounded local improvement or negotiate expedition support;
4. launch outward and discover something;
5. return with new knowledge and resources that open a different frontier hub.

Trading still recurs, but its *purpose and location* change. The renewable content is
the galaxy the player is developing and exploring, not an endlessly replenished task
list.

## 4. What this plan would actually build

### M-A — “Turn profit into readiness”

Ship Tier 0 plus Market/Service deal terms from Tier 1.1:

- reserve-aware Max;
- atomic Sell and Fit at real service points;
- the outward-run readiness card;
- exact, optional Market versus Service terms.

Exit criterion: after earning enough for a selected Tier-I upgrade, a playtester fits
it and departs on the intended outward run without completing an unnecessary extra
circuit or accidentally spending the reserved balance.

### M-B — “Build one useful place”

Add introductions and one project type: Survey Relay. Generate projects only at a
small, config-bounded set of eligible Hub/frontier ports so the universe does not fill
with progress bars.

Exit criterion: a player uses normal paid trades to complete one relay, notices the
port's permanent change without consulting release notes, and then launches an
exploration route using the information it provides.

### M-C — “Let commerce share the risk”

Add one expedition partnership type through the existing contract rail, initially
limited to repair/fitting support for investigating a known lead. Add other project
outcomes or patron packages only after balance and comprehension tests.

Exit criterion: the player can explain the sponsor's contribution and share, chooses
the partnership because it changes an expedition they already wanted, and retains all
unique discovery progression.

## 5. Data and layer boundaries

### Configuration

Add a closed project/outcome vocabulary rather than executable config hooks. A likely
shape is:

```yaml
trade_enjoyability:
  project_port_fraction: 0.08
  introductions:
    distinct_commodities: 2
    distinct_holdings: 2
  projects:
    survey_relay:
      requirements:
        fuel_ore: 180
        organics: 120
        equipment: 300
      outcome: regional_survey_intel
  expedition_partnerships:
    known_lead_survey:
      support: repair_discount
      fungible_return_share: 0.15
```

Requirements scale from existing port size/band parameters. Config validation rejects
unknown commodities, outcome ids, negative requirements, free or over-100% shares,
and outcomes that imply a service the service-point resolver cannot provide.

### Core

- Deal-term eligibility and cost are pure functions over projected-authoritative
  facts. `Trade` carries an optional closed term id; quick trade omits it.
- Sell-and-fit is one composite reducer transaction that calls the normal trade and
  install paths and commits only if both succeed.
- Introductions are finite fact bits keyed to meaningful distinct acts, not counters
  that can be farmed with split commands.
- Project state contains id, host port, required/reserved quantities, state, and
  activated outcome. Reservations occur in the trade transaction; completion is an
  explicit event and reducer.
- Partnerships should extend the existing contract model with a bounded kind rather
  than add a parallel quest container.

If implementation adopts these mechanics, `DESIGN.md` §§4, 8, 11, 13, and 14 must be
updated in the same feature change because this document is a proposal, not authority.
No alien-dialogue schema change is required; if partnerships later add dialogue
intents or choices, the dialogue corpus header and authoring prompt must also be kept
in sync under the repository's dialogue contract.

### Big bang and engine

Project candidates are selected deterministically during generation from eligible,
non-Core ports using the game RNG and config-bounded coverage. Generated projects must
not make any band unreachable, alter port classes, or promise a species absent from
the universe.

Project fulfillment is trade-driven. The engine may let NPC traders fill reserved
demand through normal trades, but it must not increment abstract project progress.
No new scheduler is required. Partnership deadlines, if used, follow the existing
contract clock.

### Server projection

- Project details appear only for explored ports and quantities the player may
  legitimately observe.
- Deal-term and Sell-and-Fit previews are resolved server-side against the same rules
  as their commands.
- Intel outcomes pass through the same fog-safe lead and route projections as existing
  Computer data.
- The server projects resolved effect text and exact costs; the TUI does not infer a
  standing delta or sponsorship share.

### TUI

Keep the default trade table fast. Add at most:

- `SAFE MAX` beside ordinary `MAX`;
- an optional Terms row on the confirmation panel;
- one readiness line after the result;
- a Project panel/tab at eligible ports;
- persistent service/intel badges in the Ports directory after completion.

At 80×24, project description and decorative completion art collapse before stock,
price, quantity, confirmation, and focus state. All commands join the canonical
`ActionDescriptor` rail; any irreversible project choice uses the shared confirmation
path.

## 6. Balance guardrails

- The normal quote is always available and is the highest immediate cash payout.
- Non-cash terms expose their exact opportunity cost; there are no random “generous
  factor” outcomes.
- Introduction progress is finite and diversity-based. Repeating a pair forever does
  not manufacture standing or project eligibility beyond the goods it supplies.
- Start with projects at roughly 5–10% of non-Core ports. Scarcity makes completed
  places memorable and limits state/UI noise.
- Project outcomes improve access, information, recovery, or convenience—not the
  base commodity price formula.
- Project requirements must be large enough to feel communal but small enough to
  finish before the first useful outward push from that hub. Initial target: 3–6
  ordinary cargo loads, not dozens.
- A partnership's support is capped below its expected fungible return share. It is
  risk-sharing, not a faucet.
- Unique discoveries, artifacts, ancient technology, codex credit, and Tier-III items
  are never sponsor property.
- Core safety and alliance hostility always win over commercial access. A project or
  patron cannot launder hostile standing into sanctuary.

## 7. Tests and acceptance criteria

- Fixed seed plus command/maintenance logs reproduce project placement, reservations,
  completion, introductions, deal terms, and partnership settlement exactly.
- `SAFE MAX` never spends below the selected reserve; ordinary `MAX` is unchanged.
- Sell-and-fit either commits both normal reducer results or neither and never displays
  a preview different from execution.
- Market terms match the legacy trade result byte-for-byte when the optional term is
  absent.
- Relationship terms cannot target a missing species/alliance and apply the projected
  exact standing delta once.
- Information terms and completed intel projects never reveal a fact outside the
  player's visibility or the source's allowed knowledge.
- Split trades cannot farm introductions; each distinct fact unlocks once.
- Every unit reserved for a project leaves ship/port circulation exactly once. Trades
  conserve it; `PortProjectCompleted` accounts explicitly for consumption.
- A project cannot complete twice, reset, change `archetype_id`, or activate an
  unconfigured service.
- NPC contribution uses the same stock/purse rules and cannot mint project goods.
- Partnership support and return shares never make a balance negative; abandoned or
  expired partnerships settle deterministically.
- Existing price monotonicity, positive clamps, purse, escape-floor, replay, service-
  point, and compact-layout tests remain intact.

Playtest measures should include more than “did profit increase?”:

- circuits completed after the player was already ready to depart (target: decrease);
- time between earning an upgrade and using it (target: decrease);
- whether players can name a port they helped change after one session;
- fraction of trades using normal terms versus an intentional alternative;
- whether players understand that project supply is paid commerce, not donation;
- whether a partnership causes an expedition that would otherwise be postponed,
  without replacing ordinary self-funded exploration.

## 8. Honest comparison

| | Plan 01 | Plan 02 | Plan 03 | Plan 04 (this) |
|---|---|---|---|---|
| Diagnosis | Repetition lacks identity | The optimum is solved | Hauling is physically passive | Profit is abstract and disconnected from its purpose |
| Primary lever | Lore and familiarity | Information, volatility, automation | Mass, hazards, cargo behavior | Reward choice, preparation, persistent local change |
| Player fantasy | Route chronicler | Market analyst / logistics owner | Specialist cargo pilot | Expedition quartermaster / frontier patron |
| Low-impact win | Port captions | Surface existing market facts | Hazard tags | Reserve-aware buying and atomic procurement |
| High-impact win | Storylets and recurring characters | Haulers and player market power | Smuggling and reactive cargo | Developed frontier hubs and expedition partnerships |
| Main risk | Text is consumed once | Economy balance destabilizes | Trading becomes punitive travel | Projects become disguised chores or buff trees |
| Guardrail | Non-blocking, finite lore | Dependable spread floor | Optional/telegraphed hazards | Paid ordinary trade, finite projects, horizontal outcomes |

The plans can coexist, but combining all of them would bury the fast TW-derived loop.
Plan 04 deliberately does **not** require price volatility, cargo spoilage, route
incidents, merchant automation, port lore milestones, or private delivery missions.
Its smallest coherent bet is M-A plus one Survey Relay: make the upgrade immediate,
let several paid cargo loads change one place, and see whether that change sends the
player outward sooner.

## 9. Recommendation

Build **M-A**, then prototype **one Survey Relay at one eligible frontier port** behind
config. This is enough to test the plan's distinct claim:

> Necessary trading becomes more enjoyable when the player can see it preparing the
> next voyage and can finish a small, permanent improvement that makes that voyage
> possible.

Do not begin with a generalized project engine or a catalog of sponsors. If the relay
does not make players care about its port and depart into the frontier, more project
types will only produce more chores. If it works, add Repair Berth next, then one
known-lead expedition partnership through the existing contract and service-point
seams.
