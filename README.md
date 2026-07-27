# Edge of the Unknown

*An exploration-first space game of trade, discovery, and alien diplomacy* — a
modern terminal application in **Python 3.12+** and the
[**Textual**](https://textual.textualize.io/) TUI framework.

Push outward from the **Core Space** — the protected central region governed at
the outset by the Federation — into an unknown, warp-connected universe and find
what is out there: uncharted planets you can descend onto, derelict shipwrecks,
nebulae and black holes, strange space-borne entities, and the ruins, artifacts,
and ancient technology of lost civilizations. A port pair-trading loop is the
economy, but **as a means to an end** — trading funds the faster engines, stronger
shields, better sensors, cloaks, and armaments needed to travel farther, survive
hostile space, and reach rarer, more valuable discoveries.

The galaxy is inhabited by alien species whose **disposition** runs a continuous
scale from openly hostile to warmly friendly: most lean friendly and barter
technology for gold-pressed latinum, while the hostile-leaning are the escalating
price of deep space — the deadliest among them also the rarest. Species are bound
into rival **alliances** you may join one at a time, so winning one bloc's favor
forfeits its rivals'. The Federation merely governs the Core at the start;
control of that home region can change hands through your deeds or the galaxy's
own upheavals — and with it, whether the Core stays a safe harbor.

Deterministic and seedable, test-covered — playable single-player or hosted for
multiplayer, from the same core.

## Status

**All five design phases are complete and playable, including multiplayer** — the
full roadmap in `docs/DESIGN.md` §14 has shipped, followed by two post-launch
correction/depth arcs.

- **Phase 1 (the walking skeleton).** Generate a universe, explore it under fog of
  war with turn costs, find profitable routes with the ship computer, trade on live
  pricing, and fund a first ship upgrade — on a deterministic core with a background
  engine ticking turns, stock regeneration, and bank interest.
- **Phase 2 (exploration & discovery).** The pivot phase: distance-banded discoveries
  (wrecks, nebulae, black holes) with sensor-gated detection and a codex; planet
  descent onto surface sites; the engine-room subsystem/component ship model with
  derived aspects; Stardock services and multiple hulls; typed, ownable planets with
  colonization and derelict-starbase salvage; friendly alien species with config-driven,
  standing-keyed dialogue and tech barter; and the Computer suite (pair-trade finder,
  route planner, codex, alien dossier).
- **Phase 3 (danger).** The frontier bites back. Selectable **universe topologies**
  (`trunk`, `expansive`, `planar`, `mesh`, `spiral`) with band-graded disposition so
  **hostiles populate the outer bands**, and **alliance home clusters** near the Core
  separated by neutral lanes. A live **encounter system** (interrupt roll, detection,
  greeting-vs-violence) and **firing-arc combat** with a floored escape chance,
  localized engine-room damage, field-kit repair, escape pods, and salvage.
  **Conversation depth** — per-visit sessions, situational facts, cross-visit
  callbacks, per-instance phrasing, and live combat dialogue. **Signature mechanics**
  (the morality judge, trojan gifts, brokers, and more, now voiced for every carrier
  species) and the singular roaming **Entity**, hunted by stale leads and a
  sensor-gated contact. **Joinable alliances** with admission prices, rival fallout,
  and Core law keyed to the governor; inter-species relations and reputation
  spillover; **starbase set-pieces** (assault, planetary defense, repair-and-claim);
  sector **fighters, mines, beacons, and black-hole hazards**; goal-directed NPC
  movement, **NPC merchants trading real goods**, and homeworld raids with legendary
  tech caches and bounties.
- **Phase 5 (depth) — built before Phase 4 by design.** An **order-book economy**
  with hard port purses replacing the old blind price drift; **dynamic governance of
  Core Space** — a rival `covets_core` bloc can seize the Core (by the player's deeds
  or NPC events), re-keying who is welcome there; **forward-base services** at
  player-owned orbital starbases; **citadels and planetary siege combat**; contracts,
  a tavern/noticeboard, an admin **sysop console**, and scripting hooks for
  autonomous play.
- **Phase 4 (multiplayer).** A versioned JSON-RPC-over-websockets wire, lobby and
  accounts, broadcast to connected clients, **corporations with corp war**, full
  attacker-driven **PvP**, and a browser-hosted client via `textual serve` — see
  `docs/HOSTING.md` to run a dedicated server and connect remotely.

Two arcs followed the Phase 1–5/4 roadmap itself:

- **Seams & gaps correction (WP70–WP77).** An audit found that core had shipped well
  ahead of the TUI — whole systems (alliance membership, starbase assault/repair,
  contracts, territory, corp war) had reducers and tests but no player-reachable
  screen. The correction arc gave them entry points: in-sector **Engage** and a live
  contact-screen attack choice, a **Territory** screen (fighters/mines/beacons/probes/
  interdictor), a Computer **Alliances** tab, a real Stardock **Bank** tab, a
  normalized keymap with a discoverable numbered action menu, destructive-action
  confirmations, and a complete **Corp** screen (invites, wars, world transfer).
- **Ground operations integration.** The abstract "descend and press a button"
  surface exploration and one-roll planetary invasion were replaced by embodied,
  tactical play adopted from the standalone `edge-groundwar` prototype: a surveyor
  walking seeded terrain toward sensor contacts, and a powered-armor squad assaulting
  a defended world — including **Cloud City**-style station-interior assaults —
  reached in the live game from the Planet screen.
- **Game-wide UI/UX overhaul (WP-UI01–23).** A full modernization of the Textual
  frontend: a responsive shell down to 80×24, a shared `ComponentWorkbench` widget
  reused by the ship engine room and starbase stations, unified action discovery
  (command palette, help, numbered action menu), consistent feedback/focus/forms,
  and a visual-regression snapshot matrix — while keeping the TW2002 ANSI identity,
  hotkeys, and command feel intact.

Two experimental, **not yet integrated** subsystems live alongside the game as
standalone Textual apps for playtesting: `edge-spacebattle` (a positioning-driven
fleet-combat mini-game, a candidate replacement for the current stats-based ship
combat) and `edge-llm-bot` (an Ollama-piloted autonomous player, `docs/SCRIPTING.md`).

The per-phase and per-arc work-package breakdowns live in `docs/PHASE1_PLAN.md`
through `docs/PHASE3_PLAN.md`, `docs/PHASE5_4_PLAN.md`, `docs/SEAMS_PLAN.md`,
`docs/GROUNDWAR_INTEGRATION_PLAN.md`, and `docs/UI_UX_OVERHAUL_PLAN.md`.

## Inspiration

The mechanical foundation — the warp-graph universe, the port economy, the turn
system — is inherited from **TradeWars 2002**, the classic BBS door game; the
exploration-first design builds on it. The exploration reframing draws on 
**Lightspeed** (MicroProse, 1990): the engine-room subsystem/component ship
model, the planet-type taxonomy, and the per-species alien dialogue. The design
was shaped by direct source analysis of seven open-source TradeWars clones plus
the original 1986 TradeWars II BASIC source; `docs/DESIGN.md` appendices A and B
record what each taught us.

## Quick start

This project uses [pixi](https://pixi.sh/) to manage its environment.

```bash
pixi install        # create the environment from pyproject.toml / pixi.lock
pixi run edge       # play (use `pixi run edge --plain` to drop animations)
pixi run serve      # or play in a browser (Textual web server; --host/--port)
```

From the main menu, press **N** for a new game, then explore: click a warp in
the grid (or a neighbour in the sidebar) to move one hop, **W** to travel a known
multi-hop route, **P** to dock at a port and trade (**T** trades the highlighted
commodity; at a Stardock, **U** buys an upgrade), **C** for the ship computer
(pair-trade finder), **G** for its event log, and **.** at any time for a numbered
menu of every action the current screen supports.

To play with someone else, host a dedicated multiplayer server and connect a
browser-served client to it (`docs/HOSTING.md`):

```bash
pixi run host          # edge-server: lobby + accounts over websocket JSON-RPC
pixi run serve-remote   # a second terminal: browser client -> ws://localhost:8765
```

## Development

```bash
pixi run check      # the full gate: ruff + mypy --strict + pytest
pixi run test       # pytest only
pixi run lint       # ruff (edge + tests)
pixi run typecheck  # mypy --strict (core, bigbang, store, server, engine)
pixi run cov        # tests with a coverage report
```

Inspect a generated universe without launching the game:

```bash
pixi run bigbang --stats --seed 4                       # text report
pixi run bigbang --stats --seed 4 --mode trunk          # compare the trunk topology
pixi run bigbang --render universe.png --seed 4           # graph dump, port sectors highlighted
```

The test strategy (DESIGN §13): Hypothesis property tests for the economy
invariants, a golden-master replay that proves a game is reproducible from
`(seed, command log)`, a 100-seed big-bang validation sweep, and Textual `Pilot`
flows over the live service.

## Architecture

Strict, downward-only layered dependencies (DESIGN §3):

```
edge/core     pure rules engine — models, economy, movement, command→event
              reducers (incl. edge/core/groundwar). No I/O, no async, no
              Textual imports.
edge/dialogue pure salience-scored alien dialogue (standing-keyed line pools,
              persona voice, recency ring). Imports core; below core.rules.
edge/bigbang  deterministic universe generation (cluster + bridge + bands +
              home clusters; selectable trunk/expansive/planar/mesh/spiral
              topology).
edge/engine   the asyncio tick loop (turn reset / stock regen / interest / drift).
edge/store    SQLite persistence behind a repository interface.
edge/server   the GameService — embedded in-process for single-player, or
              exposed over a versioned JSON-RPC/websocket wire (edge/server/net.py)
              for multiplayer; fog of war enforced at to_public() either way.
edge/tui      the Textual application — reads only the public DTOs, whether
              talking to a local or remote GameService.
```

Two invariants make the whole thing trustworthy: **all randomness flows through a
single seeded `random.Random`** owned by game state, so a game is fully
reproducible from `(seed, command log)`; and **the TUI never reaches into core
state** — it only sees the read-only projections the server emits, over the
same DTO boundary whether the service is local or remote.

`mypy --strict` and `ruff` run on every real layer (core, dialogue, bigbang,
store, server, engine); the Textual `tui/` and the standalone/dev packages
(`groundwar`, `spacebattle`, `bot`, `devtool`, `art`, `dialogue/authoring`) are
exempt.

## Repository layout

```
edge/         the game: core/bigbang/dialogue/engine/store/server/tui (above),
              plus groundwar (tactical survey/assault app), spacebattle and bot
              (experimental/dev Textual apps), devtool/art (dev tooling)
config/       default.yaml — tunable game constants, plus per-system configs
              (alien_roster/alien_dialogue, groundwar, spacebattle, names)
tests/        pytest + hypothesis suites
docs/         DESIGN.md (authoritative spec) and its companion plans/notes
scripts/      helper scripts (build the design PDF, clone references)
```

## Documentation

- **`docs/DESIGN.md`** — the authoritative design document (data model, big bang,
  economy, combat, alien species, roadmap). Read it before any architectural
  change.
- **`docs/UI_MOCKUPS.md`** — TUI wireframes, the region→widget mapping, and the
  keymap conventions.
- **`docs/PHASE1_PLAN.md`**, **`docs/PHASE2_PLAN.md`**, **`docs/PHASE3_PLAN.md`**,
  **`docs/PHASE5_4_PLAN.md`** — the per-phase work-package breakdowns and status.
- **`docs/SEAMS_PLAN.md`**, **`docs/GROUNDWAR_INTEGRATION_PLAN.md`**,
  **`docs/UI_UX_OVERHAUL_PLAN.md`** — the post-roadmap correction and depth arcs
  (surfacing shipped-but-hidden systems, ground operations, the full UI/UX pass).
- **`docs/HOSTING.md`** — running a dedicated multiplayer server and connecting a
  remote/browser client.
- **`docs/SCRIPTING.md`** — the service protocol and the Ollama-piloted
  `edge-llm-bot` autonomous player.

The analyzed TradeWars clones aren't committed; recreate them locally with
`scripts/clone_references.sh` to read alongside DESIGN.md. They carry assorted
licenses, so they are inspiration, never code to copy.

## License

Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0-or-later)
— see [`LICENSE`](LICENSE).
