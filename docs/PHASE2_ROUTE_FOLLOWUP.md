# Phase 2 follow-up — Computer tabs: Route planner + Ports directory (§11)

> Companion to `DESIGN.md`, `PHASE2_PLAN.md`, and `UI_MOCKUPS.md`. DESIGN is the
> authoritative *what*; this is the *how and in what order* for the Phase-2
> Computer tabs still stubbed. Where the two disagree, DESIGN wins and is
> corrected in the same change (CLAUDE.md).
>
> **Status: WP14–WP16 + WP18 shipped (Route + Ports + drift + Federation); WP17 draft.**
>
> Work packages: **WP14 — Route planner** · **WP15 — Ports directory** ·
> **WP16 — Alien ship movement** · **WP17 — Alien encounter "Say / Do" menu** ·
> **WP18 — Federation species (humanoid diplomats)**. WP14 lands first (WP15's
> per-row `[P] Plot route` reuses WP14's `route_view`); WP16, WP17, and WP18 are
> independent of the others (WP18 has a single optional one-line tie-in to WP16).

## Context

Phase 2's planned work packages (WP1–WP13) are all committed and the gates are
green. Two Computer tabs named in `UI_MOCKUPS.md §9` never got past a stub: the
**Route** tab still reads `"Shortest path + hazard confirm — Phase 2."` and the
**Ports** tab reads `"Port directory (last-seen stock + class) — Phase 2."`. The
affordances meant to feed Route — `[P] Plot route` on the **Trade** tab and a
plot action on the **Codex** tab — are wired to `action_noop` ("Not wired in the
skeleton.") in `edge/tui/screens/computer.py`. WP14 builds Route (below); WP15
builds the Ports directory (further below).

The misleading part is that WP11's prose says *"route planner already shipped in
1.5."* What shipped in 1.5 is the **travel primitive**, not the planner:

- `core/movement.py:shortest_path(adjacency, src, dst, allowed=…)` — BFS over the
  directional warp graph, optionally route-locked to a set of sectors.
- `core/rules.py:TravelTo` + `_travel` — a multi-hop, **route-locked** warp that
  applies hop-by-hop (one `Warped` per hop), halting early on out-of-turns or
  `_should_interrupt` (the Phase-3 combat seam).
- `tui/screens/travel.py:TravelPromptScreen` — a bare modal on the *game* screen
  that asks for a destination sector **number** and issues a `TravelTo`.

So the engine can already *execute* a multi-hop journey. What does not exist is
the Computer's ability to **show a route before committing to it** (the hop list,
turn cost, reachability, one-way segments, hazard preview) and to **originate a
route from the things the player is already looking at** — a profitable port pair
on the Trade tab, a logged find on the Codex tab. This follow-up builds exactly
that: a read-only `route_view` projection, the Route tab that renders it, and the
two tie-ins. No new game command is needed — `TravelTo` is the executor.

This is the first of two work packages, **WP14**, continuing the Phase-2
numbering. It is purely additive and TUI-facing: a pure-core path helper, a new
read-only DTO + projection, the Route tab, and tie-in plumbing on two existing
tabs. It changes no reducer and touches no RNG, so the golden-master rail is
unaffected. **WP15** (the Ports directory) follows it, sharing the same additive,
projection-only character.

---

# WP14 — Route planner

## Scope and non-goals

**In scope:**

- A pure-core route describer over `shortest_path` (hops, turn cost, one-way
  flags, reachability through explored sectors).
- `RouteDTO` + `route_view(player_id, dst_sector)` read-only projection (spatial
  display ids, per-hop port/planet markers, affordability vs. `turns_remaining`).
- The **Route** tab: render a plotted route, `[G] Engage` to issue the existing
  `TravelTo`, with a hazard-confirm seam (trivial in Phase 2, grows in Phase 3).
- **Trade → Route** tie-in: `[P]` on the selected pair plots `you → buy-port →
  sell-port` (the round trip the finder scored).
- **Codex → Route** tie-in: plot a route to the highlighted find's sector.
- Machine-readable target sectors on `TradePair` / `CodexEntry` so the tie-ins
  route without re-parsing display strings.

**Non-goals (deferred):**

- **Notes** tab / avoid-lists (`[A] Add note`) — separate UI_MOCKUPS §9 tab, not
  route work; stays a stub.
- **Ports** tab directory — its own work package, **WP15** (below).
- Real hazard sources (hostile-band species in a sector, defending starbases,
  sector mines/fighters) — those arrive with the Phase-3 encounter system. WP14
  ships the *confirm seam* and a `hazards: list[str]` channel that is empty in
  Phase 2; Phase 3 fills it without reshaping the DTO.
- Weighting paths by anything but hop count (turn-cost is uniform `turns_per_warp`
  in Phase 2; a cost-weighted Dijkstra is a Phase-5 economy-of-movement concern).
- Routing through **un**explored sectors (the route-lock is a deliberate fog-of-war
  rule, §11 — you can only travel a path you have uncovered).

---

## Design

### Core — `core/movement.py`

Add a pure describer that turns a path into a costed, annotated plan. No new
graph algorithm — it composes `shortest_path` with a small per-hop annotation:

```python
@dataclass(frozen=True)
class RouteHop:
    sector_id: int        # internal id
    one_way: bool         # reverse edge absent — the return leg differs

@dataclass(frozen=True)
class RoutePlan:
    src: int
    dst: int
    hops: tuple[RouteHop, ...]     # excludes src; empty iff src == dst
    reachable: bool                # a route exists within `allowed`
    turn_cost: int                 # len(hops) * turns_per_warp

def plan_route(adjacency, src, dst, *, allowed, turns_per_warp) -> RoutePlan:
    ...
```

`one_way` is `dst not in adjacency.get(hop, ())` for the reverse direction —
i.e. the edge `b → a` is missing for a traversed `a → b`. This is what lets the
Route tab warn "one-way: no direct way back." `plan_route` stays in `core`
(pure, no I/O), mirrors the existing `shortest_path` signature, and is the only
new algorithmic surface.

A **multi-leg** variant `plan_route_legs(adjacency, src, waypoints, …)` chains
`plan_route` across `[src, w1, w2, …]` and concatenates, for the Trade tie-in's
`you → buy → sell` round trip. Each leg is independently route-locked; the first
unreachable leg makes the whole plan `reachable=False`.

### DTO — `core/dto.py`

```python
@dataclass(frozen=True)
class RouteHopDTO:
    display_id: int       # spatial id (§5.1), what the player reads
    label: str            # "(4) · port" / "(7) · planet o" / "(12)"
    one_way: bool

@dataclass(frozen=True)
class RouteDTO:
    origin_display: int
    dest_display: int
    hops: list[RouteHopDTO]
    turn_cost: int
    turns_remaining: int
    affordable: bool          # turns_remaining >= turn_cost
    reachable: bool
    reason: str               # "" when reachable, else why not
    hazards: list[str]        # empty in Phase 2 (Phase-3 seam)
    summary: str              # "3 hops · 6 turns · 1 one-way"
```

`RouteDTO` is read-only and carries **only spatial display ids** outward (the
internal ids stay in core), consistent with every other projection. `reason`
distinguishes the failure modes the tab must explain: *no uncovered route* (fog),
*already here*, *out of turns* (reachable but `not affordable`).

Add machine-readable targets to the two source DTOs so the tie-ins need no string
parsing (both are additive fields, default-safe):

- `TradePair`: `buy_sector: int`, `sell_sector: int` (internal ids; the display
  strings already carry the spatial ids from the recent finder tweak).
- `CodexEntry`: `sector_id: int` (internal id of the find's containing sector —
  `Discovery.sector_id` always names it, even for planet sites).

### Service — `server/session.py` + `server/service.py`

- `session.route_view(state, player_id, dst_sector, config) -> RouteDTO` — calls
  `plan_route` with `allowed=player.explored_sectors` and
  `turns_per_warp=ship.turns_per_warp`, maps internal ids through
  `_display(...)`, labels each hop from `_sector_codes` (port/planet/base
  markers it already computes), and fills `hazards=[]` for now.
- `session.route_legs_view(...)` — the multi-leg wrapper for the Trade round trip.
- `service.route_view(player_id, dst)` / `service.route_legs_view(player_id,
  waypoints)` — thin pass-throughs, matching the existing projection methods.
- `_codex_entries` and `_best_pair` populate the new `sector_id` /
  `buy_sector` / `sell_sector` fields. No behavioural change to either; they
  already hold the sector ids locally.

`route_view` is a **pure read-only projection** — no RNG, no state mutation, no
event — so it is outside the golden-master surface entirely.

### Reducers

**None.** `TravelTo` is the executor and already exists (route-locked, hop-by-hop,
interrupt-aware). The Route tab's `[G] Engage` issues `service.apply(pid,
TravelTo(to_sector=dst))` for the final destination; the engine re-derives the
same locked path and halts on the same seam. For the Trade round trip, `[G]`
engages the **first** leg (`you → buy-port`); the player re-plots from there
(keeps each `TravelTo` a single auditable command and lets a mid-route
interruption — Phase 3 — leave the player somewhere sensible rather than
silently mid-chain).

### TUI — `edge/tui/screens/computer.py` (+ small new widget)

- **Route tab**: replace the stub with a `DataTable` (Hop / Sector / Notes) plus
  a summary line and a `[G] Engage  ·  [Esc] Back` footer. A `RouteTab` populated
  from a `RouteDTO`; empty state prompts "Plot a route from the Trade or Codex
  tab, or press R to enter a destination."
- **`action_plot_route` (`[P]` on Trade)**: read the highlighted `TradePair`,
  call `route_legs_view(pid, [buy_sector, sell_sector])`, store the result, and
  switch `TabbedContent.active = "route"` to show it. Replaces `action_noop`.
- **Codex `[P]`**: highlighted `CodexEntry` → `route_view(pid, entry.sector_id)`
  → Route tab. (Codex tab gains a `[P] Plot route` binding mirroring Trade.)
- **`[G] Engage`** on the Route tab: `TravelTo` the destination, then `pop_screen`
  back to the game screen so the player sees the hop-by-hop warp resolve. If
  `not affordable` / `not reachable`, `[G]` is inert and the reason is shown.
- **Hazard confirm seam**: when `dto.hazards` is non-empty, `[G]` first raises a
  confirm `ModalScreen` listing them; empty in Phase 2, so the modal never
  appears yet — but the call site exists for Phase 3 to light up.
- Optional `[R]` keeps the old `TravelPromptScreen` behaviour *inside* the
  Computer (type a destination sector), so the tab is usable without a Trade/Codex
  selection. The game-screen `TravelPromptScreen` stays as-is.

The Computer screen currently builds its DTOs once in `__init__`; the plotted
route is per-interaction, so it is fetched on the `[P]`/`[R]` action and the
Route tab re-rendered then (the other tabs keep their snapshot-on-open model).

---

## Tests

- **Core (`tests/test_movement.py`)**: `plan_route` on the existing small
  directional fixture (`1<->2, 2->3 one-way, 3<->4`) — hop list, `turn_cost ==
  hops * turns_per_warp`, `one_way` true on the `2->3` segment and false on
  two-way segments; `allowed` exclusion makes an un-uncovered destination
  `reachable=False`; `src == dst` yields empty hops; `plan_route_legs`
  concatenates and fails closed on an unreachable leg. Property: a returned route
  is a valid walk in `adjacency` and every hop ∈ `allowed`.
- **Service (`tests/test_session.py`)**: `route_view` maps to spatial ids; an
  out-of-turns ship is `reachable=True, affordable=False` with the turns reason;
  a fogged destination is `reachable=False`; the Trade tie-in's
  `route_legs_view([buy, sell])` reproduces the finder pair's hop distance;
  `CodexEntry.sector_id` routes to the find's sector. All through the service
  projection only.
- **Codec / golden master**: untouched — no new command or event. A regression
  assertion that the existing `state_hash` rail is unchanged by the additive DTO
  fields (they are projection-only, not persisted state).
- **Textual Pilot (`tests/test_tui_flow.py`)**: open Computer → Trade tab → `[P]`
  → assert the Route tab is now active and its table lists the plotted hops →
  `[G]` engages and pops back to the game screen with the ship advanced toward the
  buy port. A second flow: hail/seed a discovery into the codex (reuse the WP6
  flow), open Codex → `[P]` → Route tab populated for the find's sector.

---

## Verification

- **Gates**: `pixi run lint` (ruff), `pixi run python -m mypy` (--strict on
  `core/bigbang/store/server/engine`; `tui/` exempt), `pixi run python -m pytest`.
- **Determinism**: nothing new touches the RNG or the command log; the existing
  golden-master replays stay green unchanged. `route_view` is referentially
  transparent given state.
- **Manual**: in `pixi run edge`, open the Computer on a game with a known
  profitable pair, `[P]` to plot, confirm the hop list / turn cost read true
  against the Map, `[G]`, and watch the multi-hop warp resolve — then plot to a
  logged Codex find and confirm it routes to the right sector.

---

## Suggested order / commits (phase-tagged, small)

1. `p2: WP14 (core) plan_route / plan_route_legs over shortest_path` — core +
   `test_movement` (pure, no UI).
2. `p2: WP14 (service) route_view + RouteDTO; target sectors on pair/codex` —
   projection + `test_session`, additive DTO fields.
3. `p2: WP14 (tui) Route tab + Trade/Codex plot tie-ins + Engage` — computer.py
   wiring + `test_tui_flow`. → **Route tab live.**

Dependency order is also the commit order: the TUI tie-ins need the projection,
which needs the core describer. Each commit is independently green.

---

# WP15 — Ports directory

The other tab `UI_MOCKUPS.md §9` reserves and still stubs: **Ports** — a
directory of the ports the player knows about, with their class and goods, so the
trade loop can be navigated from the Computer rather than from memory. It pairs
naturally with WP14: each row carries a `[P] Plot route` straight into the Route
tab.

## Scope and non-goals

**In scope:**

- A read-only `PortDirEntry` DTO + `port_directory(player_id)` projection: every
  port in an **explored** sector (the same fog-of-war set the pair-trade finder
  uses), with its spatial sector id, name, class, the buy/sell triple, and a
  hop-distance from the player's current sector.
- The **Ports** tab: a sortable `DataTable` (Sector / Port / Class / Buys / Sells
  / Dist), richest context first, with a `[P] Plot route to highlighted` tie-in
  into WP14's Route tab and the existing fog-of-war empty state.
- Consistency with the finder: both read "ports in explored sectors," so the
  Ports tab is the human-readable index behind the Trade tab's scored pairs.

**Non-goals (deferred):**

- A **last-seen intel snapshot** (freezing stock/price as it was when the player
  last docked/scanned, so the directory can show *stale* numbers in a sector the
  player has left). Phase 2 has no per-player port-intel store; WP15 shows the
  **current public view** of explored-sector ports — the same simplification the
  pair-trade finder already makes. A true `Player.port_intel` last-seen snapshot
  is a documented later refinement (see *Design → Fog of war*), additive to this
  DTO when it lands.
- Live **price** columns (the finder already scores profit; the directory is a
  *where/what* index, not a second pricer). Class + buy/sell triple is enough to
  read the trade graph; per-commodity prices stay on the Port screen.
- **Filtering / search** UI (by class, by commodity, by band). The table is
  sortable; richer querying is a nice-to-have, not in scope.

## Design

### DTO — `core/dto.py`

```python
@dataclass(frozen=True)
class PortDirEntry:
    """One known port for the Computer's Ports tab (§11)."""

    port_id: int
    sector_id: int        # internal id (for the [P] route tie-in)
    sector_display: int   # spatial id (§5.1), what the player reads
    name: str
    klass: str            # PortClass label, e.g. "Class 1 (BBS)"
    buys: str             # "Org, Equ"  — commodities the port buys
    sells: str            # "Fuel"      — commodities the port sells
    dist: int             # hops from the player's current sector (BFS), -1 if fogged
```

Carried out of `ComputerDTO` as `ports: list[PortDirEntry] = field(default_factory=list)`,
matching how `codex` / `dossier` already hang off it (default-safe, additive).

### Service — `server/session.py`

- `_port_directory(state, player_id) -> list[PortDirEntry]` — filter ports to
  `sector_id in player.explored_sectors` (the finder's `seen` set), compute
  `dist` from `bfs_distances(adjacency, ship.sector_id)` (already used by
  `computer_view`), map sector ids through `_display(...)`, and split each port's
  `commodities` into buy/sell labels by `PortMode` (the same split `_best_pair`
  reads). Sort by `(dist, sector_display)` so the nearest known ports lead.
- `computer_view` gains `ports=_port_directory(state, player_id)` — one more
  field on the DTO it already builds; no new service method needed (the Ports tab
  reads the same `ComputerDTO` the screen already fetches once in `__init__`).

`port_directory` is a **pure read-only projection** — no RNG, no mutation, no
event — outside the golden-master surface, exactly like the codex/dossier
projections beside it.

### Fog of war

The directory honours the established fog rule: a port appears only once its
**sector is explored**. It shows the port's *current* public class and buy/sell
triple — which never changes for a port (class and trade direction are fixed at
big bang; only stock/price drift), so "current vs. last-seen" only matters for
the *numbers* WP15 deliberately omits. If a future work package adds a
`Player.port_intel: Mapping[int, PortSnapshot]` last-seen store (stamped on dock
/ scan), `PortDirEntry` grows `last_seen_day` + stock columns and the projection
reads the snapshot instead of the live port — additive, no reshaping.

### TUI — `edge/tui/screens/computer.py`

- **Ports tab**: replace the stub `Static` with a `DataTable` (Sector / Port /
  Class / Buys / Sells / Dist), populated in `on_mount` from
  `self._computer.ports` (the screen already holds the `ComputerDTO`). Empty
  state: "No ports discovered yet — explore to chart them." (the fog-of-war
  prompt the other tabs use).
- **`[P] Plot route to highlighted`**: a binding on the Ports tab that reads the
  highlighted `PortDirEntry`, calls WP14's `route_view(pid, entry.sector_id)`,
  and switches `TabbedContent.active = "route"` — the same handoff the Trade and
  Codex tabs use, so all three "plot" affordances converge on the Route tab.
- Cursor-row → entry resolution mirrors the existing finder/codex row handling
  (`DataTable.cursor_row` index into the stored DTO list).

## Tests

- **Service (`tests/test_session.py`)**: `port_directory` lists exactly the ports
  in explored sectors (a fogged-sector port is absent until its sector is
  explored); `dist` equals the BFS hop count from the player's sector and the
  rows are sorted nearest-first; buy/sell labels match the port's `PortClass`
  trade triple; the entry count tracks the finder's `seen` set. Through the
  service projection only.
- **Golden master / codec**: untouched — additive projection field, no command or
  event; assert the `state_hash` rail is unchanged.
- **Textual Pilot (`tests/test_tui_flow.py`)**: open Computer → Ports tab →
  assert the known ports are listed with class + dist → highlight a row → `[P]`
  → assert the Route tab is now active and plotted to that port's sector (reuses
  WP14's Route assertions).

## Verification

- **Gates**: `pixi run lint`, `pixi run python -m mypy`, `pixi run python -m pytest`.
- **Determinism**: projection-only; the existing golden-master replays stay green
  unchanged.
- **Manual**: `pixi run edge` — explore a few sectors, open the Computer → Ports,
  confirm the charted ports read true against the Map (class, buy/sell, distance),
  and `[P]` on one routes there via the Route tab.

## Suggested order / commits (phase-tagged, small)

1. `p2: WP15 (service) port_directory projection + PortDirEntry DTO` — projection
   + `test_session` (lands on top of WP14's DTO additions).
2. `p2: WP15 (tui) Ports directory tab + plot-route tie-in` — computer.py wiring
   + `test_tui_flow`. → **Ports tab live; with WP14, UI_MOCKUPS §9 complete bar
   the Notes/avoid-list tab.**

WP15 depends on WP14 only for the `[P]` tie-in (`route_view`); its projection is
independent and could land first, but the natural order is WP14 then WP15 so the
plot handoff is wired the moment the Ports rows appear.

---

# WP16 — Alien ship movement (cron drift)

Aliens are pre-staged at one sector each and never move, so a contact you found
once is always exactly where you left it — the galaxy feels static, and a met
species is trivially re-found. WP16 makes alien ships **drift between sectors** on
the tick clock: each firing, every species rolls a chance to warp to an adjacent
sector it is *allowed* to occupy (alliance territory rules). This is what makes
the dossier's new **"Last seen"** column meaningful — it records where you *met*
a species, which may no longer be where it *is*.

## Context & the constraints it must respect

Movement is an **engine-tick (cron) effect**, not a player command, so it inherits
the WP12 maintenance discipline:

- **Crons are pure `(state, config) -> ReduceResult`** (`engine/cron.py` — "no RNG,
  no I/O"). A move "roll" needs randomness, which the existing crons deliberately
  avoid. WP16 must introduce that randomness **without** consuming from the shared
  runtime `state.rng` (whose draw order the command-replay stream depends on) and
  **without** breaking the "a reloaded save never double-runs or skips a tick"
  promise.
- **Replay reconstructs state as `generate(seed) + replay(command log + maintenance
  timeline)`** (WP12). The ticker persists each cron firing and re-runs the reducer
  on reload via `resolve_cron`. So WP16's drift must be a **deterministic function
  of replay-durable inputs** — the same firings in the same order must move the
  same ships to the same sectors, live or reloaded.

## Scope and non-goals

**In scope:**

- A new cron `alien_drift` in the `CRONS` registry (durable name), scheduled on
  its own interval (config-driven), that for each species rolls `move_chance` and,
  on success, warps it to a uniformly-chosen **valid** adjacent sector.
- A **territory-validity predicate** (pure, `core/aliens.py`): a species may enter
  a sector only if it is **not Core Space** and **not owned by a rival alliance**
  (planet `Ownership` keyed to an alliance other than the species'). Unaligned
  neutrals avoid all alliance-owned sectors; governing-alliance members and
  unaligned may never re-enter the Core (it stays protected/empty). StarDock-staged
  contacts are **pinned** (they are the hub's standing welcome, §6.3 — they don't
  wander off).
- A per-firing **sub-RNG** seeded from replay-durable inputs (below), so drift is
  deterministic and does not perturb the command RNG stream.
- An `AlienMoved(species_id, from_sector, to_sector)` event, surfaced to the player
  **only** when the move touches the player's current sector (an alien warps in or
  out beside them) — so the log isn't flooded by galaxy-wide drift.

**Non-goals (deferred):**

- **Rivalry/grudge-aware routing** (the §6.4 inter-species relation matrix, at-war
  states, vendettas). Phase 2 has only the coarse "owned by a different alliance"
  gate; the relation matrix that makes *some* rival territory passable and *some*
  neutral territory hostile is Phase 3, and slots into the same predicate.
- **Goal-directed movement** (aliens seeking the player, fleeing, patrolling trade
  lanes, returning home). WP16 is an unbiased random walk within legal territory;
  intent-driven movement is Phase 3 (encounter system) / Phase 5.
- **Pack/fleet/escort co-movement** — a species moves as a single contact token;
  multi-hull packs are Phase 3.
- **Player-ship interception on drift** (an alien warping into your sector starting
  combat). Phase 2 contacts are friendly; the encounter roll is Phase 3. WP16 only
  changes *where* a contact is, not what meeting it does.

## Design

### Config — `core/config.py` (`AliensConfig`)

```python
drift_enabled: bool = True
drift_move_chance: float = Field(default=0.25, ge=0.0, le=1.0)  # per species, per firing
drift_ticks_per_firing: int = ...   # cadence, like the other crons' intervals
```

Tunable, defaulted, frozen — a quiet galaxy is `drift_move_chance=0` or
`drift_enabled=False`.

### Core — territory validity (`core/aliens.py`, pure)

```python
def may_occupy(state, species, sector_id, config) -> bool:
    """Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules)."""
    sector = state.sectors[sector_id]
    if sector.is_galactic_core:
        return False                      # the Core stays protected/empty
    for planet in state.planets.values():
        if planet.sector_id != sector_id:
            continue
        owner = planet.owner
        if owner.kind == "alliance" and owner.ref != species.alliance_id:
            return False                  # a rival bloc's holding is off-limits
    return True
```

Pure and side-effect-free, so it is unit-testable in isolation and reused by the
cron. Phase 3 widens the rival check from "different alliance" to "alliance the
species' bloc is at war with / holds a grudge against" (§6.4) — same signature.

### Cron — `engine/cron.py` (`alien_drift`)

```python
def alien_drift(state, config, *, firing: int) -> ReduceResult:
    rng = random.Random(f"{state.game.seed}|alien_drift|{firing}")  # sub-RNG, salted
    moved, events = [], []
    for sp in sorted(state.species.values(), key=lambda s: s.id):
        if sp.id in pinned(state):                 # StarDock contacts don't wander
            continue
        if rng.random() >= config.aliens.drift_move_chance:
            continue
        legal = [n for n in sorted(state.adjacency.get(sp.sector_id, ()))
                 if may_occupy(state, sp, n, config)]
        if not legal:
            continue
        dst = rng.choice(legal)
        moved.append(replace(sp, sector_id=dst))
        events.append(AlienMoved(sp.id, sp.sector_id, dst))  # filtered to player sector below
    return ReduceResult(events=tuple(events), species=tuple(moved))
```

Two things this needs from the surrounding machinery:

- **A `species=` channel on `ReduceResult` + `apply_result` upsert.** `AlienSpecies`
  is the first cron-mutated *species* entity; add the tuple field and the upsert
  branch beside the existing `players` / `ships` / `planets` ones (one-line each).
- **A replay-durable `firing` index.** Crons today take `(state, config)` only. The
  drift roll must vary per firing yet reproduce under replay. Carry a monotonic
  counter on `state.game` (e.g. `drift_seq`), advanced by the cron itself
  (`game=replace(state.game, drift_seq=firing + 1)` in the result), and seed the
  sub-RNG from it. Because the counter is **state** rebuilt by re-running crons in
  the merged maintenance order (WP12), live and reloaded runs seed identically.
  This keeps the shared `state.rng` untouched (the species sub-RNG discipline from
  big-bang placement, applied to the tick loop).

### Event & fog of war — `AlienMoved`

Emit `AlienMoved` only when `from`/`to` equals the player's sector, so the log
reads "a Vesk vessel warps in" / "the Selvani slip away" — a real, diegetic cue —
and stays silent for the rest of the galaxy's drift. The dossier's **Last seen**
column is **not** updated by movement: it is stamped at hail time
(`Player.species_last_seen`, already shipped) so it always reports the contact
point, never a live-position fog leak. The live sector view (`_sector_dto`, the
WP "ships in sector" change) shows a species **only where it currently is** — so a
drifted contact genuinely has to be re-found, and the dossier tells you where to
start looking. This player-visible/remembered split is the whole point of the
feature.

### Determinism / replay

`alien_drift` is deterministic given `(seed, drift_seq)`; it never reads
`state.rng`, so it cannot shift command-stream draws (haggle, etc.). Under WP12 the
firing is persisted and the reducer re-runs on reload in the merged order, so
species positions reconstruct exactly. Adding `Game.drift_seq` and the
`AlienMoved` event must round-trip the snapshot/`state_hash` and (if cron events
are persisted to the event log) the codec — following the existing
`TurnsReset` / `PlanetProduced` cron-event pattern.

## Tests

- **Core (`tests/test_aliens.py`)**: `may_occupy` — false for a Core sector, false
  for a sector holding a rival-alliance planet, true for empty/neutral and for the
  species' own-alliance holdings.
- **Cron (`tests/test_cron.py` / `test_engine`)**: with `drift_move_chance=1.0`
  every unpinned species steps to a legal neighbour; with `0.0` none move; a
  species hemmed in by Core/rival territory stays put; StarDock contacts never
  move; the same `(seed, drift_seq)` reproduces the identical move set; drift never
  lands a species in a Core or rival-owned sector (property test over seeds).
- **Replay / golden master (`tests/test_service.py`)**: a session that **ticks**
  enough to fire `alien_drift` a few times, then reloads, has identical species
  `sector_id`s and `state_hash` (the WP12 "save fidelity under ticking" test,
  extended to species). Proves the maintenance timeline replays movement.
- **Determinism guard**: `alien_drift` does not consume `state.rng` — a recorded
  command log's `state_hash` is unchanged whether or not drift fired between
  commands (drift uses only its sub-RNG).
- **Projection (`tests/test_session.py`)**: after a drift that moves a met species,
  the dossier **Last seen** still shows the hail sector, while `game_view` shows the
  species only in its new sector (the fog split).

## Verification

- **Gates**: `pixi run lint`, `pixi run python -m mypy`, `pixi run python -m pytest`.
- **Determinism**: drift is a pure function of `(seed, drift_seq)`; the shared RNG
  stream and the existing golden-master replays are untouched.
- **Manual**: `pixi run edge` — meet a species, leave, let the tick loop run, return
  to the contact sector and find it empty; open the Computer → Dossier and confirm
  **Last seen** still names where you met them; spot the `AlienMoved` log line when a
  vessel warps into your sector.

## Suggested order / commits (phase-tagged, small)

1. `p2: WP16 (core) may_occupy territory predicate + AliensConfig drift knobs` —
   pure core + `test_aliens`.
2. `p2: WP16 (engine) alien_drift cron + ReduceResult.species + Game.drift_seq` —
   cron reducer, registry entry, `AlienMoved` event/codec + `test_cron`.
3. `p2: WP16 (replay) tick-then-reload species fidelity + dossier/fog projection` —
   `test_service` + `test_session`. → **Aliens roam; the Last-seen dossier earns
   its column.**

WP16 is independent of WP14/WP15 (no shared surface beyond the dossier column,
which is already shipped). It depends only on the WP12 maintenance timeline being
in place — which it is.

---

# WP17 — Alien encounter "Say / Do" menu

The contact screen already renders a **"Say / Do"** verb menu (`contact.py`,
heading at line 96) — derived from species params, greyed-with-reasons — but the
verbs are **inert `Static` text**. The only things a player can actually *do* on
the screen are `H` (re-greet), `Esc`/`6` (leave), and click a tech offer; the
`trade` / `barter` / `treaty` / `fight` verbs are decoration. WP17 makes the menu
**live**: each enabled verb is clickable and key-bound and dispatches its action,
so the conversation is something you steer rather than read.

## Context

The pieces this needs already exist:

- **The verb menu is derived**, not authored: `session._contact_verbs` builds the
  rows from `trade_posture` / `treaty_mode` / `combatant` and the available offers,
  attaching a `key`, `label`, `enabled`, and a `reason` when greyed (§6.7). WP17
  consumes that — it does not re-derive the menu.
- **The dialogue engine is config-driven and replay-safe**: `dialogue.speak`
  renders a persona-voiced line for a context, and the **recency ring**
  (`Player.dialogue_recency`) is advanced by a reducer so repeats rephrase. The
  `greeting` context already works end-to-end: the `Hail` reducer advances the
  greeting ring (`rules.py:_hail`), and the contact view shows the opener read-only
  (`session._line`). WP17 generalises that one worked example to the rest of the
  peaceful contexts.
- **Action verbs already have working reducers**: `BuyAlienTech` / `BarterArtifact`
  fire from offer clicks today. WP17 lets the **Buy tech** / **Barter** verbs reach
  them (focus/scroll the offer list, or act on the sole offer) rather than making
  the player hunt the separate offer panel.

So WP17 is mostly **wiring + one generalised command**, not new systems.

## Scope and non-goals

**In scope:**

- **Clickable + key-bound verbs.** Replace the inert `Static` verb rows with
  `ClickableEntry` (the same affordance the offers and sector entries use), keyed by
  `verb.key`, and add a `BINDINGS` entry per enabled verb so both mouse and keyboard
  drive the menu. Disabled verbs stay greyed and show their `reason` (unchanged).
- **A generalised `Converse` command** (core) that speaks a chosen **peaceful**
  dialogue context and advances its recency ring — the same mechanism `Hail` uses
  for `greeting`, lifted to any `_PEACEFUL_CONTEXTS` key. `Hail` becomes
  `Converse(greeting)` (or delegates to a shared ring-advance helper).
- **"Say" verbs** (dialogue, no mechanical effect): **Greet** (`greeting`),
  **Ask about…** (`dossier_other`, parameterised by a chosen subject species),
  **Farewell** (`farewell`, then break contact). Each renders its line into the
  speech panel and rephrases on repeat via the ring.
- **"Do" verbs** (mechanical): **Buy tech** and **Barter** focus the offer list and
  act on it (reusing the existing reducers); **Leave** breaks contact. Grouped under
  the **Say** / **Do** sub-headings the menu name already promises.
- **A subject picker** for *Ask about…*: a small modal listing the species the
  player has met (the dossier set), dismissing with the chosen `subject` species id.

**Non-goals (deferred):**

- **Treaty** and **Attack** verbs — Phase 3 (treaties, the encounter/combat system,
  `combat_*` contexts). They stay derived-and-greyed with their current reasons.
- **Signature-mechanic verbs** (`sig.*` contexts: trojan-gift, reprogram-unlock,
  escalating-demand, …) and the `demand` / `reward` / `extort_response` contexts —
  Phase 3 (§6.2), they need the mechanic state machine.
- **`befriend_price` quest tasks / branching dialogue trees** — Phase 3 (§6.1). WP17
  is a flat verb menu, not a conversation graph.
- **Free-text / open-ended input.** The menu is a closed verb set (the dialogue
  vocabulary is a closed set of context keys by design, §6.7).
- **New dialogue *content*.** WP17 surfaces lines the packs already define for the
  peaceful contexts; it authors no new pack entries beyond what `validate_dialogue`
  already requires.

## Design

### Core — `Converse` command + reducer (`core/rules.py`)

```python
@dataclass(frozen=True)
class Converse:
    species_id: int
    context: str                 # must be in dialogue._PEACEFUL_CONTEXTS
    subject_id: int | None = None  # for dossier_other ("ask about X")

def _converse(state, player_id, cmd, config) -> ReduceResult:
    species = _species_here(state, ship, cmd.species_id)     # must be in-sector
    if cmd.context not in dialogue._PEACEFUL_CONTEXTS:
        raise EconomyError("not something you can say here")  # combat/sig are Phase 3
    extra = _subject_extra(state, cmd.subject_id)            # {"subject": name} or {}
    ring = player.dialogue_recency.get((species.id, cmd.context), ())
    rng = dialogue.encounter_rng(state.game.seed, species.id, cmd.context, ring)
    line, new_ring = dialogue.speak(config.roster, species, player, cmd.context,
                                    aliens=config.aliens, rng=rng, extra=extra)
    new_player = replace(player,
        species_attitudes=_met(player, species.id),
        species_last_seen={**player.species_last_seen, species.id: ship.sector_id},
        dialogue_recency=_advance_recency(player, species.id, cmd.context, new_ring))
    return ReduceResult(events=(AlienSpoke(player_id, species.id, cmd.context),),
                        players=(new_player,))
```

`_hail` collapses to `Converse(greeting)` (or both call one shared helper), so there
is a single ring-advancing conversation path. The reducer is the **only** thing that
advances the ring; the projection stays read-only (below). Guard: a non-peaceful or
unreachable context raises rather than silently no-ops, so the codec/menu can't smuggle
a Phase-3 line in.

### DTO — `ContactVerbDTO` (`core/dto.py`)

Add the dispatch metadata so the TUI need not hardcode the verb→action map:

```python
kind: str = "do"               # "say" | "do" — groups under the Say / Do sub-headings
context: str = ""              # the dialogue context a "say" verb speaks ("" for "do" verbs)
needs_subject: bool = False    # this "say" verb opens the subject picker (dossier_other)
```

`_contact_verbs` tags each row: `greeting` / `dossier_other` / `farewell` as
`kind="say"` (with `context`, and `needs_subject=True` for *Ask about…*), and
`trade` / `barter` / `treaty` / `fight` / `leave` as `kind="do"`. Existing fields
(`key` / `label` / `enabled` / `reason`) are unchanged, so the derivation stays the
single source of truth.

### Speech display — the read-only / ring-advance split

The contact view shows the **active context's** line read-only, exactly as the
opener does today (`session._line`, which renders from the current ring without
advancing). The screen tracks an `active_context` (default `greeting`); a "say" verb
sets it. To keep "what is shown" identical to "what was spoken" — and reproducible
under replay — the flow mirrors the established greeting precedent:

1. The screen applies `Converse(context, subject)` — the reducer speaks the line
   from the **pre-advance** ring and advances it.
2. The view re-renders the active context read-only; because both the reducer and
   `_line` seed the **same** `encounter_rng(seed, species, context, ring)`, they
   agree on the variant for a given ring state.

This is the same read-only-projection / reducer-advances-ring seam WP9 already
solved for the opener — WP17 just lets contexts other than `greeting` use it. The
`AlienSpoke` event also lets the message log carry "you asked the Vesk about the
Selvani" if desired.

### TUI — `tui/screens/contact.py`

- Render the menu as two labelled groups — **Say** and **Do** — of `ClickableEntry`
  rows (keyed by `verb.key`), greying disabled rows with their reason as now.
- A `BINDINGS` entry per verb key dispatches the same handler as a click.
- Dispatch:
  - `kind == "say"`, `needs_subject` → push a `SubjectPickerScreen` (modal listing
    met species from `contact.dossier` / the dossier set); on pick, apply
    `Converse(context, subject_id)` and re-render the speech panel.
  - `kind == "say"`, no subject → apply `Converse(context)`; *farewell* additionally
    pops the screen after showing the line.
  - `kind == "do"`: **Buy tech** / **Barter** focus the offers panel (and act on the
    lone offer if there is exactly one of that mode); **Leave** pops; **Greet** is
    `Converse(greeting)` (the current `H`).
- Disabled verbs are inert (notify the reason on click), matching the offers.

### Codec — `store/codec.py`

`Converse` joins `encode_command` / `decode_command` and the
`test_every_command_variant_is_covered` exhaustiveness guard; `AlienSpoke` joins the
event codec. `Hail`'s wire form is retained (or re-expressed as `Converse(greeting)`)
so old logs still replay. Because the ring advance now flows through `Converse`, the
existing "dialogue survives reload" replay coverage extends to every peaceful context.

## Tests

- **Core (`tests/test_contact.py`)**: `Converse(dossier_other, subject)` renders a
  line naming the subject and advances that context's ring (a repeat rephrases);
  `Converse` on a `combat_*` / `sig.*` context raises; `Hail` and `Converse(greeting)`
  produce identical state. Property: every `_PEACEFUL_CONTEXTS` key speaks a non-empty,
  placeholder-clean line for a default-roster species (dovetails with
  `validate_dialogue`).
- **Codec (`tests/test_codec.py`)**: `Converse` (each context, with/without subject)
  and `AlienSpoke` round-trip; the exhaustiveness guard stays green.
- **Replay (`tests/test_contact.py`)**: a log of `Hail → Converse(dossier_other) →
  Converse(farewell)` reloads to an identical `state_hash`, proving the generalised
  ring advance reconstructs.
- **Textual Pilot (`tests/test_tui_flow.py`)**: open contact → click **Ask about…** →
  pick a met species in the modal → the speech panel updates with a subject-named
  line; click **Buy tech** → it focuses/acts on the offer (a component lands aboard);
  a greyed **Treaty** click notifies its Phase-3 reason; **Farewell** speaks then
  closes the screen. All through the service.

## Verification

- **Gates**: `pixi run lint`, `pixi run python -m mypy`, `pixi run python -m pytest`.
- **Determinism**: the ring advances only via `Converse`; the line shown equals the
  line spoken because both seed the same `encounter_rng`; `(seed, command log)`
  reproduces every conversation.
- **Manual**: `pixi run edge` — hail a species, work the **Say** menu (greet again →
  rephrased; ask about another met species → it talks about them), use **Buy tech** /
  **Barter** from the menu rather than the offer panel, **Farewell** to leave.

## Suggested order / commits (phase-tagged, small)

1. `p2: WP17 (core) Converse command + reducer; Hail = Converse(greeting)` —
   core + `test_contact`, codec + guard.
2. `p2: WP17 (service) verb kind/context tagging + AlienSpoke; subject extras` —
   `_contact_verbs` metadata + `test_session`.
3. `p2: WP17 (tui) clickable Say/Do menu + subject picker + Do-verb wiring` —
   `contact.py` + `test_tui_flow`. → **The encounter menu is interactive.**

WP17 is independent of WP14–WP16; it depends only on the WP9 contact screen and the
WP8 dialogue engine, both shipped. It is the natural completion of the contact
screen — the offers panel already acts; this makes the conversation act too.

---

# WP18 — Federation species (humanoid diplomats in Federation space)

The **Terran Federation governs the Core but has no people of its own.** It is
`alliance_id: 1` in the roster — the Core's governor, the bloc the player starts
in — yet *every* species in `roster_default.yaml` is either unaligned (`null`) or a
member of a rival bloc (2/3/4). So the Core is contact-free except the WP-staged
StarDock greeters (drawn from unaligned neutrals, since there were no Federation
members to draw from). WP18 fixes that: it gives the Federation its **founding
species** — Star-Trek-human-style **humanoid diplomats**, the warmest contacts in
the game — and settles them through **Federation space** (the Core and the
governor's home lanes), so the player's home region finally feels *inhabited by
their own people*, not just protected by faceless law.

## Context

This is the natural completion of three threads already in place:

- **The governing-alliance model** (`Game.core_governing_alliance_id`, §6.3). The
  Federation is the default governor and the player is seeded into it — but with no
  member species, "you are a Federation member" is currently an abstraction with no
  faces attached.
- **The StarDock-greeter staging** (shipped): `_place_stardock_contacts` already
  seeds **Core-welcome** species at the hub, and its comment notes the workaround —
  "the default roster names no species as Federation members, so the hub is seeded
  from the broader Core-welcome set." WP18 removes the need for that workaround by
  *supplying* Federation members; the greeter logic then naturally prefers them.
- **The §6.7 dialogue engine + allied standing band.** A fellow alliance member is
  read in the **allied** band (effective disposition boosted by shared membership),
  which the dialogue `when` predicates already key on. A maximally-friendly
  Federation species lands squarely there — the ideal showcase for the allied-voice
  lines.

The Star Trek frame: the United Federation of Planets / Starfleet — principled,
exploratory, diplomacy-first ("we come in peace," mutual understanding, peaceful
contact), optimistic and humanoid. The roster's existing Terran Federation banner,
*"Exploration & mutual defence,"* already reads as exactly this; WP18 puts a face
and a voice to it.

## Scope and non-goals

**In scope:**

- **Roster content** (`config/roster_default.yaml`): one to three **Federation-member
  species** — `alliance_id: 1`, `alliance_role: member` (one `leader`) — with the new
  **`archetype_id: humanoid_diplomat`**, `disposition_center: 1.0` (with small
  `disposition_variance`, so they draw at the very top of the friendly band — "100%
  friendly to the player"), `trade_posture: open`, `treaty_mode: open`, generous
  `tech_offers`, and `persona: humanoid_diplomat`. The flagship is the **Terrans**
  (humans); any companions are their close Federation partners.
- **A new `humanoid_diplomat` persona dialogue pack** in the `personas:` block — the
  Starfleet voice: warm, formal-but-friendly, exploration- and cooperation-minded,
  with **allied-band** greeting/trade/treaty lines that speak to the player *as a
  fellow Federation citizen* (the §6.7 standing-keyed `when` machinery).
- **Placement in Federation space** (`bigbang/aliens.py`): a new generation step
  that settles governing-alliance members across the **Core and the governor's home
  lanes**, so the Core is populated by its own people. Generalises
  `_place_stardock_contacts`; the StarDock greeter step then prefers real Federation
  members over the unaligned-neutral fallback.
- **Validation + drift relaxation**: the §13 "no contacts inside Core Space"
  invariant (`bigbang/validate.py`) is relaxed for **the governing alliance's own
  members** (they belong there — it is their capital), exactly as the dock sector is
  already exempted. WP16's `may_occupy` predicate likewise lets a governing-alliance
  member **drift within the Core**, while every other species still may not enter it.

**Non-goals (deferred):**

- **Changing who governs the Core / dynamic governance** — Phase 5
  (`covets_core`). WP18 populates *the current* governor's space; if governance
  flips later, re-population follows that, not this WP.
- **A full multi-species Federation** (a deep bench of member races). WP18 establishes
  the `humanoid_diplomat` archetype and a small founding set; more members are just
  more roster entries against the same machinery.
- **Hostility / betrayal arcs for the Federation.** They are 100%-friendly by
  construction in Phase 2; a player turning *against* the governor already has its
  consequences in the §6.3/§10 territory rules (the Core turns hostile to a
  rival-aligned player) and does not need new Federation-specific combat content here.
- **New mechanics.** WP18 is roster content + a placement/validation generalisation;
  it introduces no new command, DTO, or screen. `archetype_id` stays a flavour label
  (carried on the entity, not gated in code); the persona drives the voice.

## Design

### Roster — the species (`config/roster_default.yaml`)

A new "Federation core" group, e.g. (abbreviated):

```yaml
  - id: terran
    name: Terrans
    archetype_id: humanoid_diplomat
    description: >-
      Humans of the Terran Federation — principled explorers and diplomats, the
      Core's founding people and the player's own. The warmest contact in the game.
    disposition_center: 1.0
    disposition_variance: 0.03      # always at the very top of the friendly band
    tech_level: 8
    alliance_id: 1                  # the Core governor
    alliance_role: leader
    home_band: Core
    trade_posture: open
    treaty_mode: open
    persona: humanoid_diplomat
    threat_tier: feeble
    combatant: true                 # capable, but never reaches violence at 100% amity
    memory_model: normal
    betrayal_model: recoverable
    tech_offers:
      - { tier: I,   mode: latinum, component: turbine,   price: 1600, min_disposition: 0.60 }
      - { tier: II,  mode: latinum, component: converter, price: 6500, min_disposition: 0.70 }
      - { tier: III, mode: barter,  aspect: shields,                   min_disposition: 0.80 }
  # + 0-2 close Federation partners (alliance_role: member), same archetype/persona.
```

The low `min_disposition` thresholds and `disposition_center: 1.0` mean a
Federation member — being a *fellow citizen* — opens essentially every offer
immediately, making them the natural first tech vendor a new player reaches.

### Roster — the `humanoid_diplomat` persona pack

A new entry in `personas:`, voiced as Starfleet — warm, exploratory, principled —
with **allied-keyed** variants so the lines address the player as kin:

```yaml
  humanoid_diplomat:
    greeting:
      - when: { standing: allied }
        variants:
          - "Welcome home, {player}. The Federation stands with you."
          - "{player}! Good to see a fellow citizen out on the lanes. Safe travels."
      - variants:    # fallback for any non-allied standing
          - "We come in peace, {player}. The Terran Federation greets you."
    trade_open:
      - variants:
          - "Everything we've built is open to a friend of the Federation, {player}."
    treaty_offer:
      - variants:
          - "Between friends a treaty is a formality — but gladly, {player}."
    dossier_other:
      - variants:
          - "The {subject}? We seek peaceful understanding with all peoples, {player}."
    farewell:
      - variants:
          - "Go well, {player}. To boldly go — and come home safe."
```

The `dialogue_pack` validator (§13) already enforces that the persona resolves a
non-empty pool for every reachable context and that `dossier_other` is
subject-parameterised, so the pack must cover the peaceful set — no new validation
rule, just new content the existing rule checks.

### Placement — `bigbang/aliens.py`

A `_populate_governing_space(state, config, rng, placed)` step (sibling to
`_place_stardock_contacts`) settles `alliance_id == core_governing_alliance_id`,
`alliance_role in {leader, member}` species across **Core sectors and the governor's
near-Core home lanes**, guaranteeing the founding `leader` species appears. Count is
config-driven (e.g. `RosterConfig.core_population` or reuse the
`stardock_contacts` knob's sibling). The existing band-placement still skips Core for
*non*-governing species; this step is the **only** way species enter the Core, and it
admits only the governor's own members. The StarDock greeter step is updated to
prefer real governing-alliance members (now that they exist) over the unaligned
fallback. Runs on the same `_SPECIES_SALT` sub-RNG, so it does not perturb the
port/planet/discovery draw order (golden-master ordering).

### Validation + drift — `bigbang/validate.py`, `core/aliens.py`

- `_check_species`: the "placed inside Core Space" rejection gains a second
  exemption — `sp.alliance_id == state.game.core_governing_alliance_id` — beside the
  existing dock-sector one. (Governor's members belong in the Core; everyone else is
  still barred.) Add an invariant: **at least one** governing-alliance member is
  placed in Core (the Federation inhabits its own capital).
- WP16 `may_occupy`: `if sector.is_galactic_core: return species.alliance_id ==
  governing_id` — Federation ships may drift within the Core; all others still can't
  enter it. (If WP16 has not landed yet, this is a one-line addition when it does;
  WP18 does not depend on WP16.)

## Tests

- **Roster integrity (`tests/test_aliens.py`)**: the Federation members resolve their
  alliance (`alliance_id: 1` ∈ alliances), carry `archetype_id: humanoid_diplomat`,
  and draw `is_friendly` at the top of the band (`base_disposition` ≈ 1.0); the
  `humanoid_diplomat` persona passes `validate_dialogue` (every peaceful context
  non-empty, `dossier_other` parameterised).
- **Placement (`tests/test_aliens.py`, parametrised over seeds)**: ≥1 governing-alliance
  member is placed in Core Space; **no** non-governing species is ever placed in Core
  (the relaxed invariant still bars rivals); every live band still has its contact;
  determinism guard — adding the Core population does not perturb port/planet draws.
- **Dialogue (`tests/test_dialogue.py`)**: a Federation member greeted by the
  (Federation-member) player speaks an **allied**-band line; a hypothetical
  non-member hears the generic peaceful greeting (the `when: {standing: allied}`
  branch fires only for kin).
- **Drift (WP16 tests, when present)**: a Federation ship may step to an adjacent Core
  sector; a rival ship adjacent to the Core never enters it.

## Verification

- **Gates**: `pixi run lint`, `pixi run python -m mypy`, `pixi run python -m pytest`
  (roster/dialogue validation runs at config-load).
- **Determinism**: placement uses the species sub-RNG; the golden-master replays stay
  green.
- **Manual**: `pixi run edge` — start a new game in the Core and find **Terran
  vessels** in nearby sectors; hail one and hear the *fellow-citizen* greeting, buy
  cheap early tech, and confirm the Computer dossier reads them as allied/100%-friendly.

## Suggested order / commits (phase-tagged, small)

1. `p2: WP18 (roster) Federation humanoid_diplomat species + persona pack` —
   `roster_default.yaml` content; `test_aliens` integrity + `validate_dialogue`.
2. `p2: WP18 (bigbang) settle governing-alliance members in Core + validation` —
   `_populate_governing_space`, the Core exemption + "Federation inhabits its capital"
   invariant, StarDock greeter preference; `test_aliens` placement.
3. `p2: WP18 (drift) may_occupy lets governor members roam the Core` — the one-line
   WP16 relaxation + test (lands with or after WP16). → **The Federation has a face.**

WP18 depends only on the shipped roster/placement/dialogue machinery; its WP16 tie-in
is a single line that can land whenever WP16 does. It is the content payoff of the
governing-alliance model — the player's home region, peopled by the player's own.
