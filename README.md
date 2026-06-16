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

**Phase 1 (the walking skeleton) is complete and playable.** You can generate a
universe, explore it under fog of war with turn costs, find profitable routes
with the ship computer, trade on live pricing, and fund a first ship upgrade at
the StarDock — all on a deterministic core with a background engine ticking
turns, port-stock regeneration, and bank interest.

Phases 2–5 (the discovery system, alien species & diplomacy, the engine-room
component model, combat, multiplayer, and a deeper economy) are designed in
`docs/DESIGN.md` but not yet built. See `docs/PHASE1_PLAN.md` for the completed
work-package breakdown.

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
pixi run tui        # play (use `pixi run tui --plain` to drop animations)
```

From the main menu, press **N** for a new game, then explore: click a warp in
the grid to move (each costs turns), **P** to dock at a port and trade
(**T** trades the highlighted commodity; at a StarDock, **U** buys an upgrade),
**C** for the ship computer's pair-trade finder, **M** for the galactic map.

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
pixi run bigbang --inspect --seed 4              # text report
pixi run bigbang --render universe.png --seed 4  # graph dump, port sectors highlighted
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
edge/bigbang  deterministic universe generation (cluster + bridge + bands).
edge/engine   the asyncio tick loop (turn reset / stock regen / interest).
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
docs/         DESIGN.md (authoritative spec), UI_MOCKUPS.md, PHASE1_PLAN.md
scripts/      helper scripts (build the design PDF, clone references)
```

## Documentation

- **`docs/DESIGN.md`** — the authoritative design document (data model, big bang,
  economy, combat, alien species, roadmap). Read it before any architectural
  change.
- **`docs/UI_MOCKUPS.md`** — TUI wireframes and the region→widget mapping.
- **`docs/PHASE1_PLAN.md`** — the Phase-1 implementation plan and status.

The analyzed TradeWars clones aren't committed; recreate them locally with
`scripts/clone_references.sh` to read alongside DESIGN.md. They carry assorted
licenses, so they are inspiration, never code to copy.
