# Phase 1.5 — Navigation & QoL Follow-ups

> Companion to `DESIGN.md` and `PHASE1_PLAN.md`. DESIGN is the authoritative
> *what*; this is the *how and in what order* for the first round of post-Phase-1
> playtest fixes (`changes_to_make.md`). Where the two disagree, DESIGN wins and
> is corrected in the same change.

## Context

Phase 1 shipped a playable, deterministic trading skeleton (WP0–WP9, all
milestones reached). The first round of playtest feedback (`changes_to_make.md`)
is that the game *works* but **gives the player no sense of direction**:
wandering is fine, but there's no incentive or legibility guiding *where* to go,
and the warp UI is trial-and-error. This round addresses that with a batch of
low/medium-risk navigation + quality-of-life fixes, plus two small plumbing
items (binary rename, web-serve), and lays the groundwork for the one genuinely
hard change — **spatial sector renumbering** — as a researched design proposal
rather than a risky cross-layer cutover.

Decisions already made with the user:
- **Sector renumbering = research spike + DESIGN proposal this round** (prototype
  numbering fn + written proposal); the cross-layer cutover is deferred to its
  own future round. The numbering-*independent* "gravity arrows" (`<<`/`>>`/`--`)
  still ship now.
- Web research on numbering schemes was done up front (see WP-E).

All work obeys the architecture rules in CLAUDE.md: downward-only layer deps,
all randomness through the state RNG, economy/movement invariants in core, every
constant in config, TUI only through the service boundary. `ruff` + `mypy
--strict` stay green on `core/bigbang/store/server/engine`; `tui/` is exempt.

---

## User feedback (source)

The verbatim source for this round, lightly edited for clarity. The framing:
the game *works*, but wandering feels aimless — the player needs an incentive
and the legibility to know *where* to go. Each bullet maps to a work package
below.

**Navigation — quick quality-of-life fixes (→ WP-A, WP-B, WP-C):**

- Allow clicking on warp numbers in the sidebar.
- Tell the player where StarDock is at the start of the game (in the logs).
- On the sidebar map, once a sector is explored, indicate what is there with
  short codes for planets and/or ports, color-coded by type.
- The sidebar map quick reference should also name the region of space (Hub,
  Frontier, …): instead of just "Sector 432," show `[432] Halaf Verge
  (Frontier)`. All sectors in the same region share the same name prefix.
- Add the ability to `(W)` warp to a sector through the intermediary sectors —
  you would have to stop for hostile encounters.
- You can only warp to sectors whose route you have already uncovered.
- Add a third warp-button color marking where you just came from (in addition
  to where you have already been): per sector, where you last entered from.
  Not following the path back can leave a broken trail — acceptable.
- Add a legend for the warp-button colors.

**Navigation — the harder improvement (→ WP-E, research + proposal only):**

- The current navigation leans too much on trial and error and is
  unintuitive.
- It would be more intuitive if the sector numbering grouped numbers by
  proximity. Numbers need not be monotonically increasing — gaps are fine — so
  the numbers can follow a pattern:
  - All sectors in a band of space share the same prefix (e.g. all Hub sectors).
  - All sectors in an alliance or region share a prefix too.
  - The prefix is multi-level; sector numbers may be 4–5 digits.
  - If a region is a "Tunnel" motif (§5 step 3), the numbers within it should
    be strictly sequential (e.g. Halaf 10, 11, 12, 13) to show a linear path.
- Sector numbers should be topologically sorted so a higher number means
  greater distance from the Core.
- In the warp list (§11), use Unicode arrows for the "gravity" of a warp:
  `[12] <<` leads significantly closer to the Core; `[45] >>` leads deeper into
  the frontier; `[22] --` stays within the same distance band.
- Research how this is solved in other games and in human-intuition papers.

**Other (non-warp) issues (→ WP-A legend, WP-B, WP-D):**

- The trading screen needs a list of shortcuts at the bottom — there's no way
  to know that `T` = trade.
- Map and log should be part of the ship's computer, but may keep direct
  hotkeys.
- Rename the TUI binary to `edge` in `pyproject.toml` and the documentation.
- Add a `--serve` option to the renamed `edge` binary to serve a Textual web
  server.

**Amendments — round 2 (`changes_to_make2.md`) (→ WP-A, WP-B):**

- StarDock should be an automatically known route (not just named in the log —
  the path to it should already be uncovered).
- Use the arrow keys to move focus between warp buttons by their on-screen
  layout: Up focuses the button rendered above the current one, Down the one
  below, Left/Right the neighbours. (Pure 2D grid focus — unrelated to warp
  gravity / Core direction.)

---

## WP-A — Warp UI legibility (TUI + projection)

Covers feedback bullets: clickable sidebar warps; region+band sector labels;
sidebar-map content codes; third warp-button color + legend.

**Projection (`edge/server/session.py`, `edge/core/dto.py`)**
- Redesign `WarpDTO` (dto.py:51): keep `sector_id`/`label`; **repurpose `arrow`**
  to carry the gravity glyph (`<<`/`>>`/`--`, computed in WP-C) and **add
  `kind: str`** ∈ {`"backtrack"`, `"explored"`, `"unexplored"`} to drive color.
- Replace `ShipDTO.region_map: list[str]` (dto.py:99) with a structured
  `neighbors: list[NeighborDTO]` where `NeighborDTO` carries `sector_id`,
  `name` (`"[432] Halaf Verge"`), `band`, `explored: bool`, and `codes: list[str]`
  (short content codes for the *explored* sector: e.g. `P` port, `@` planet, plus
  a type hint). Unexplored neighbors carry no codes.
- `_sector_dto` / `_ship_dto` (session.py:28–63): populate the new fields.
  Region name comes from `state.regions[sector.region_id].name` (already wired);
  band from `sector.distance_band`. Content codes derived by scanning
  `state.ports`/`state.planets` for that sector (reuse `port_in_sector` pattern,
  models.py:180) — only when the neighbor is in `player.explored_sectors`.

**Sector title (`edge/tui/screens/game.py:84`)**
- Change `"{region} - Sector {id}"` → `"[{id}] {region} ({band})"` to match the
  requested `[432] Halaf Verge (Frontier)` format. Band comes from the ShipDTO.

**Sidebar (`edge/tui/widgets.py` `StatusSidebar`, lines 175–212)**
- Render `neighbors` as **clickable** rows (reuse the `WarpButton.Warp` message
  or a thin `ClickableEntry`-style line posting the same `Warp(sector_id)`), each
  showing `[id] Name (Band)` + color-coded content codes. This satisfies "allow
  clicking on warp numbers on the sidebar." Color codes: port=magenta, planet=
  green, type-tinted via the existing theme palette (app.py:25).

**Warp buttons + legend (`edge/tui/widgets.py` `WarpButton`/`WarpGrid`)**
- `WarpButton` (line 362): pick variant/class from `warp.kind` — explored=primary
  (cyan), unexplored=dim (existing `.unexplored` class), **backtrack=accent
  (magenta)** via a new `.backtrack` CSS class. Label shows `{id} {arrow} {label}`
  with `arrow` now the gravity glyph.
- Add a small **legend** Static under `WarpGrid` (or in the sidebar) explaining
  the three colors and the `<< / -- / >>` arrows.

**Arrow-key warp focus (round-2 amendment).** Let the arrow keys move focus
between the `WarpButton`s by their **on-screen grid position**: Up focuses the
button rendered directly above the focused one, Down the one below, Left/Right the
horizontal neighbours; Enter warps the focused button (the existing
`WarpButton.Warp` message). This is purely spatial focus over the rendered layout
— it has nothing to do with warp gravity or distance-from-Core. Textual (8.x) has
no built-in arrow focus (only Tab/Shift+Tab), so `WarpGrid` owns the arrow
bindings and steps the grid geometry itself (children flow into the fixed-column
grid, so child index `i` → `(i // cols, i % cols)`; it skips the centre marker and
empty cells). Crucially, `WarpGrid.on_mount` **auto-focuses its first warp
button** so the keys work the instant the sector view appears — no priming Tab —
and re-homes focus on every recompose (after a warp / travel / screen-resume).
`tui/`-only (mypy-exempt); Pilot-tested in `test_tui_flow.py` (auto-focus present,
Right/Left and Down/Up geometry).

---

## WP-B — Real event log + StarDock signpost + Computer reorg

Covers: "tell the player where StarDock is at game start (in the logs)"; "Map and
log should be part of the ship's computer but keep direct hotkeys."

**Message log backed by real events (`edge/server/session.py` + `service.py`)**
- Add `messages_view(state, player_id) -> MessagesDTO` projecting the persisted
  `event_log` (read via the repo / `service`) into `LogEntry(when, text)` rows
  (shape already in `dummy.py:152–164`; promote it to `dto.py`). Reuse the
  formatting already in `game.py:_format` (lines 224–237) — extract it to a shared
  `format_event` helper so the ticker and the Log tab render identically.
- **StarDock signpost:** at `GameService.new_game` (service.py:34), compute the
  StarDock sector (the Class-9 port, `PortClass.STARDOCK`) and persist a synthetic
  intro entry, e.g. `"Navigation beacon: StarDock lies in Sector N — <region>."`
  Surface it as the first line of both the game-screen ticker
  (`game.py:144`) and the Log tab. This is an intentional reveal (a known
  landmark giving the player a goal), consistent with DESIGN §5's "StarDock
  reachable" guarantee.

**StarDock as an auto-known route (round-2 amendment).** Naming StarDock in the
log isn't enough — the *route* to it should already be uncovered so the player
can `(W)` travel there from turn one (route-lock requires explored sectors).
Adjacency and `core_hops` already exist before `populate` runs (generator.py:148–
151), so in `populate.py` (where player 1 is built, populate.py:140) seed the
opening fog with the StarDock path: `path = shortest_path(state.adjacency, 1,
dock.sector_id)`, then `explored_sectors = frozenset(path)` and a matching
`entered_from` chain (`{path[i+1]: path[i]}`). Only the shortest path is revealed
— everything off it stays fogged — so the frontier is still earned. This makes
the signpost actionable and the warp buttons along the way render explored.
Touches the **core/bigbang** layer, so it must go through the build RNG-free
deterministic path helper (no randomness) and is covered by a bigbang test.

**Fold Map + Log into the Computer (`edge/tui/screens/computer.py`)**
- Move the live `MapView` (widgets.py:309) into the Computer's **Map** tab (wire to
  `service.map_view`, currently a stub at computer.py) and add a **Log** tab wired
  to `messages_view`.
- Give `ComputerScreen.__init__` an `initial_tab` param.
- In `game.py` (lines 203–217), keep the `m` and `g`/`l` bindings but have them
  push `ComputerScreen(initial_tab="map")` / `("log")` instead of the standalone
  `MapScreen`/`MessagesScreen`. The standalone screens become thin or are
  retired. `c` opens Computer at its default tab.

---

## WP-C — Navigation mechanics: gravity arrows, multi-hop warp, route-lock, breadcrumb

Covers: gravity arrows; `(W)` warp through intermediaries (stopping for hostile
encounters — stubbed, encounters are Phase 3); "only warp to sectors you've
uncovered the route to"; "where you came from" breadcrumb.

**Gravity arrows (cheap, numbering-independent)**
- Add a runtime-only `core_hops: dict[int, int]` to `UniverseState`
  (models.py:150, alongside `adjacency` — **not** a frozen entity field, so it
  does **not** affect `state_hash`/golden masters). Populate it once after
  generation via `bfs_distances(adjacency, 1)` (topology.py:41).
- In `_sector_dto`, set each warp's `arrow`: `<<` if
  `core_hops[target] < core_hops[current]`, `>>` if greater, `--` if equal
  (toward/away/level relative to the Core). Matches the requested glyphs exactly.

**Breadcrumb / "last entered from" (`edge/core/models.py`, `rules.py`)**
- Add `Player.entered_from: Mapping[int, int]` (frozen, default empty): for each
  visited sector, the neighbor you last arrived from.
- In `_warp` (rules.py:157): record `entered_from[to_sector] = from_sector`.
- In `_sector_dto`: mark the warp whose target == `entered_from.get(current)` as
  `kind="backtrack"` (the third color, WP-A). Per the feedback, an off-path
  return can leave a stale crumb — that's acceptable/expected.

**Multi-hop warp + route-lock (`edge/core/movement.py`, `rules.py`)**
- Extend `shortest_path` (movement.py:30) with an optional `allowed: set[int] |
  None` to restrict traversal to a sector set (route-lock).
- New command `TravelTo(to_sector: int)` in rules.py: compute the shortest path
  **through already-explored sectors only** (`allowed = player.explored_sectors`),
  requiring the destination itself to be explored — this is the literal
  "only warp to sectors you've uncovered the route to." Validate turns for the
  whole path, then apply hop-by-hop, emitting one `Warped` per hop and updating
  `entered_from`/`explored_sectors`/turns each step. Add a `_should_interrupt`
  stub (returns `None` in Phase 1) where Phase 3 will inject the hostile-encounter
  check that halts mid-route.
- **Single-hop warps stay open:** clicking an adjacent warp (even an unexplored,
  dimmed neighbor) still issues plain `Warp` — that is how the player *uncovers*
  new space. Route-lock applies only to the new `TravelTo` long-jump. (The only
  playable reading; noted explicitly.)
- **TUI:** bind `w` in `game.py` to a small destination prompt (Textual `Input`
  modal, or pick from explored sectors) → `TravelTo`; also expose it in the
  Computer **Route** tab (computer.py) per DESIGN §11's hop-by-hop route planner.

---

## WP-D — Packaging: rename binary, add `--serve`

Covers: "rename the tui binary to edge"; "add a --serve option for a Textual
webserver."

- **Binary rename (`pyproject.toml`):** add `[project.scripts]` with
  `edge = "edge.tui.app:main"`; rename the pixi task `tui` → `edge`
  (pyproject.toml:41). Update docs (README, CLAUDE.md references to `pixi run
  tui`, any UI_MOCKUPS/PHASE1 mentions).
- **`--serve` (`edge/tui/app.py:76` `main`):** add `--serve` (+ `--host`/`--port`)
  argparse flags. When set, launch the Textual web server instead of `.run()`.
  Implementation via the `textual-serve` `Server` class wrapping the plain
  `edge` command (the served subprocess runs the normal app, *not* `--serve`,
  avoiding recursion). Add `textual-serve` to `[tool.pixi.dependencies]` and to
  DESIGN §15's dependency list (the spec already anticipates `textual serve`).

---

## WP-E — Sector renumbering: research + DESIGN proposal + prototype (no cutover)

The hard item, scoped to a **proposal + prototype** this round per the user's
decision. The risk that makes a full cutover its own round: sector IDs are the
primary key across `models.py`, `adjacency`, `events`, the SQLite **command/event
log**, **golden-master state hashes** (`store/snapshots.py`), and every test
fixture — changing them invalidates all recorded replays.

### Research findings (web, June 2026)

- **TW2002 itself** numbers up to 5000 sectors with *no spatial meaning* — the
  universe is a directed graph and "efficiently navigating the graph is a large
  part of what makes the game compelling" — i.e. the trial-and-error the feedback
  is reacting to is *original-game-authentic*, so we are deliberately diverging.
- **Star Trek / Federation coordinates** put **distance-from-core on the primary
  axis** (origin at a beacon near the core worlds) — direct precedent for
  "higher number ⇒ farther from Core."
- **Elite Dangerous** uses a **hierarchical name**: `Sector + boxel (regional grid
  cell) + mass + ordinal` (e.g. `Jellyfish Sector FB-X c1-5`) — strong precedent
  for a **multi-level prefix (region) + local ordinal** scheme.
- **Outer Reaches (PBM)** labels a grid with **letter-number subregion
  coordinates** — precedent for readable region prefixes.
- **Wayfinding research** (hierarchical navigation graphs; "fine-to-coarse"
  planning heuristic): people plan **coarsely between regions and finely within**,
  and hierarchical/regional labeling **reduces cognitive load and aids recall**.
  This directly endorses *region-prefix + locally-sequential-within-region*, plus
  coarse directional cues (the gravity arrows from WP-C).

### Proposed scheme (to be written into DESIGN.md §5)

A **multi-level, gapped, band-monotone ID**, e.g. `BRR LL`:
- **Band digit(s)** first, so a numerically larger ID ⇒ farther from Core
  (topological sort on `core_hops`): Core/Hub < Frontier < Deep < Void.
- **Region prefix** shared by all sectors in a region (Elite-style boxel idea;
  satisfies "all sectors in a region share the same prefix"). Alliance/home-cluster
  regions get their own reserved prefix block.
- **Local ordinal** within the region, **gapped** (no monotonic global counter —
  the feedback explicitly allows gaps), and **strictly sequential for `tunnel`
  motif regions** (Halaf 10,11,12,13) to signal a linear path. (Tunnels are a
  DESIGN §5 step-3 motif not yet generated in code — coordinate with that.)
- IDs stay integers (so the column type and codec are unchanged) but are *encoded*
  as `band*10000 + region*100 + ordinal` (4–5 digit), preserving sortability.

### Deliverables this round (no production cutover)
1. **DESIGN.md update**: new §5 sub-section specifying the scheme, the research
   rationale above, and the validator invariant "ID order is consistent with
   `core_hops` order."
2. **Prototype function** (in `bigbang/`, behind a test, not wired into
   `generate`): `assign_spatial_ids(groups, core_hops, bands, cfg) -> dict[old,new]`
   producing the encoded IDs deterministically from the build RNG.
3. **A migration note** in the proposal: the cutover round must remap the command
   log or (cleaner) treat it as a `config_version` bump that regenerates golden
   masters, since IDs are derived, not authored.

---

## Suggested order / commits (phase-tagged, small)

1. `p1.5: WP-A` warp UI legibility (DTO + projection + widgets).
2. `p1.5: WP-C` gravity arrows + breadcrumb + multi-hop/route-lock (core + TUI).
3. `p1.5: WP-B` real event log + StarDock signpost + auto-known route + Computer reorg.
4. `p1.5: WP-D` rename binary + `--serve`.
5. `p1.5: WP-E` renumbering proposal (DESIGN.md) + prototype + tests.

WP-A and WP-C share the `WarpDTO` change, so land A and C together or A first.
WP-B's auto-known route depends on WP-C's `shortest_path` route-lock landing
first. (WP-A–WP-D are already committed; the round-2 amendments add the
arrow-key focus to WP-A and the auto-known route to WP-B.)

## Verification

- **Core tests (`tests/`):** extend `test_movement.py` for `shortest_path(...,
  allowed=...)` and `TravelTo` (turn accounting over a multi-hop route, route-lock
  rejects unexplored destinations, hop-by-hop `Warped` events, `entered_from`
  updates). Add a `test_rules.py` case for the breadcrumb. Property/golden-master
  tests must still pass — confirm `core_hops` (runtime-only) and the WP-A DTO
  changes do **not** alter `state_hash`; if `Player.entered_from` is included in
  the hash, regenerate the golden master and note it.
- **Projection:** unit-test `messages_view` (StarDock intro present; events
  formatted) and the gravity-arrow logic (`<<`/`>>`/`--`) against a tiny fixture
  universe.
- **Bigbang (WP-B route):** assert the new game seeds `explored_sectors` with a
  contiguous path from sector 1 to the StarDock sector (and a matching
  `entered_from` chain), that the off-route remainder stays fogged, and that
  `TravelTo(stardock)` succeeds from the opening state.
- **TUI (Textual Pilot, `test_tui_flow.py`):** click a sidebar neighbor → warp;
  press `w` → TravelTo a known sector; open Computer → Map/Log tabs render;
  assert the warp legend + `[id] Region (Band)` title; **arrow-key focus:** Down
  moves focus to the warp button rendered below the focused one (Up above,
  Left/Right horizontally), Enter warps it.
- **WP-E:** a bigbang test asserting `assign_spatial_ids` is deterministic and
  band-monotone (ID order matches `core_hops` order) across several seeds.
- **Manual:** `pixi run edge` (renamed) and `pixi run edge --serve` then open the
  browser; confirm the StarDock signpost appears in the opening log, gravity
  arrows point sensibly, and the backtrack color marks the way you came.
- Gates: `pixi run check` (ruff + mypy --strict + pytest) green; `pixi run cov`
  holds ~98%.

## Sources (numbering research)
- [TradeWars 2002 — Break Into Chat BBS wiki](https://breakintochat.com/wiki/TradeWars_2002)
- [The Stardock — TW2002 navigation manual](https://www.thestardock.com/files/ModernManual/core/navigation.md)
- [Star Trek galactic coordinates — Memory Alpha](https://memory-alpha.fandom.com/wiki/Coordinates)
- [Elite Dangerous boxel / sector naming — Frontier Forums](https://forums.frontier.co.uk/threads/marxs-guide-to-boxels-subsectors.618286/)
- [Outer Reaches (PBM) grid coordinates — Wikipedia](https://en.wikipedia.org/wiki/Outer_Reaches_(play-by-mail_game))
- [Applying hierarchical graphs to pedestrian navigation — ACM SIGSPATIAL](https://dl.acm.org/doi/abs/10.1145/1463434.1463499)
- [The dynamic nature of cognition during wayfinding — PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2660842/)
