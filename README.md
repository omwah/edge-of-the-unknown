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

Deterministic and seedable, test-covered, single-player first, with the data
model laid out so multiplayer can follow later.

## Status

**Phases 1–3 are complete and playable.**

- **Phase 1 (the walking skeleton).** Generate a universe, explore it under fog of
  war with turn costs, find profitable routes with the ship computer, trade on live
  pricing, and fund a first ship upgrade — on a deterministic core with a background
  engine ticking turns, stock regeneration, and bank interest.
- **Phase 2 (exploration & discovery).** The pivot phase: distance-banded discoveries
  (wrecks, nebulae, black holes) with sensor-gated detection and a codex; planet
  descent onto surface sites; the engine-room subsystem/component ship model with
  derived aspects; StarDock services and multiple hulls; typed, ownable planets with
  colonization and derelict-starbase salvage; friendly alien species with config-driven,
  standing-keyed dialogue and tech barter; and the Computer suite (pair-trade finder,
  route planner, codex, alien dossier).
- **Phase 3 (danger) — complete.** The frontier bites back. Selectable **universe
  topologies** (`trunk` chokepoints vs. the new default `expansive` band-lattice) with
  band-graded disposition so **hostiles populate the outer bands**, and **alliance home
  clusters** near the Core separated by neutral lanes. A live **encounter system**
  (interrupt roll, detection, greeting-vs-violence) and **firing-arc combat** with a
  floored escape chance, localized engine-room damage, field-kit repair, escape pods,
  and salvage. **Conversation depth** — per-visit sessions, situational facts, cross-visit
  callbacks, per-instance phrasing, and live combat dialogue. **Signature mechanics** (the
  morality judge, trojan gifts, brokers, and more) and the singular roaming **Entity**,
  hunted by stale leads and a sensor-gated contact. **Joinable alliances** with admission
  prices, rival fallout, and Core law keyed to the governor; inter-species relations and
  reputation spillover; **starbase set-pieces** (assault, planetary defense, repair-and-claim);
  sector **fighters, mines, beacons, and black-hole hazards**; goal-directed NPC movement,
  **NPC merchants trading real goods**, and homeworld raids with legendary tech caches and
  bounties.

Phases 4–5 (multiplayer, corporations, the order-book economy, dynamic Core governance)
are designed in `docs/DESIGN.md` but not yet built. The per-phase work-package
breakdowns live in `docs/PHASE1_PLAN.md`, `docs/PHASE2_PLAN.md`, and
`docs/PHASE3_PLAN.md`.

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
commodity; at a StarDock, **U** buys an upgrade), **C** for the ship computer
(pair-trade finder), **M** for its galactic map, **G** for its event log.

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
              reducers. No I/O, no async, no Textual imports.
edge/dialogue pure salience-scored alien dialogue (standing-keyed line pools,
              persona voice, recency ring). Imports core; below core.rules.
edge/bigbang  deterministic universe generation (cluster + bridge + bands +
              home clusters; selectable trunk / expansive topology).
edge/engine   the asyncio tick loop (turn reset / stock regen / interest / drift).
edge/store    SQLite persistence behind a repository interface.
edge/server   the in-process GameService; fog of war enforced at to_public().
edge/tui      the Textual application — reads only the public DTOs.
```

Two invariants make the whole thing trustworthy: **all randomness flows through a
single seeded `random.Random`** owned by game state, so a game is fully
reproducible from `(seed, command log)`; and **the TUI never reaches into core
state** — it only sees the read-only projections the server emits.

`mypy --strict` and `ruff` run on every real layer; the Textual skeleton is the
one exemption.

## Repository layout

```
edge/         the game (the layers above)
config/       default.yaml — all tunable game constants (economy, generation, ship)
tests/        pytest + hypothesis suites
docs/         DESIGN.md (authoritative spec), UI_MOCKUPS.md, PHASE{1,2,3}_PLAN.md
scripts/      helper scripts (build the design PDF, clone references)
```

## Documentation

- **`docs/DESIGN.md`** — the authoritative design document (data model, big bang,
  economy, combat, alien species, roadmap). Read it before any architectural
  change.
- **`docs/UI_MOCKUPS.md`** — TUI wireframes and the region→widget mapping.
- **`docs/PHASE1_PLAN.md`**, **`docs/PHASE2_PLAN.md`**, **`docs/PHASE3_PLAN.md`** — the
  per-phase work-package breakdowns and status.

The analyzed TradeWars clones aren't committed; recreate them locally with
`scripts/clone_references.sh` to read alongside DESIGN.md. They carry assorted
licenses, so they are inspiration, never code to copy.
