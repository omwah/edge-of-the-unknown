# Ground-war prototype and production source (`edge-groundwar`)

A standalone, Starship-Troopers-inspired turn-based tactical game built from Edge
of the Unknown parts. The prototype has been **adopted** as the mechanical and
visual source for the production ground-operation system specified in
`DESIGN.md` §§3–4.2, 7, 10–11, 13–14 and
`GROUNDWAR_INTEGRATION_PLAN.md`. It is not yet wired to live universe state: the
existing entry point remains a deterministic playtest and balance harness while
the GW work packages move its pure mechanics into `edge/core/groundwar/`.

Run it: `edge-groundwar` (or `python -m edge.groundwar`).

## Premise

The player commands a platoon of powered-armor Mobile Infantry dropped onto a
defended, city-holding world. The goal is **surrender, not extermination** — a
demonstration of power, novel-style: drain the planetary **Resolve** meter below
the difficulty's threshold by destroying *military* assets (turrets, AA, sensors,
garrison, the citadel gun), silencing ("cowing") cities, and having a Command suit
broadcast terms over a cowed city. Leveling civilian blocks **backfires** (resolve
hardens), as does losing troopers.

## Interview decisions (July 2026)

- Standalone `edge/groundwar/` package + `edge-groundwar` entry point.
- Tactical cell grid: the terrain art *is* the board (movement cost / cover / LOS
  per feature), scrolling map ~220×56, one viewport + vi/arrow cursor.
- Individual troopers; three suit classes — **Marauder** (heavy firepower,
  missiles), **Scout** (fast, long sight, jams sensors), **Command** (accuracy
  aura, broadcast terms).
- All four pressure mechanisms: retrieval-boat timer, no reinforcements,
  escalating sorties/accuracy, casualty ceiling (doctrine abort).
- Planetary Resolve meter (single win meter; per-city "cowed" states feed it).
- City defenses: anti-drop/anti-jump AA, perimeter walls/gates/turrets, garrison
  sorties, sensor towers vs. scout jamming (undetected units get a first-strike
  accuracy bonus). The capital is the **citadel city** — difficulty sets its
  citadel level (mirrors `edge.core.citadels`): mid-wall turrets (L1+), the
  citadel gun (L2+), double walls + extra AA (L3).
- Point-budget platoon composer; drop-zone placement on the map (AA contests
  close landings).
- IGOUGO turns; seeded generator + setup menu (planet type / difficulty / seed);
  modest FX (cell flashes + combat log).

## Current prototype layout

- `config/groundwar_default.yaml` — every balance constant.
- `edge/groundwar/config.py` — typed loader.
- `edge/groundwar/model.py` — battle-state dataclasses (UI reads, never writes).
- `edge/groundwar/mapgen.py` — seeded battlefield: `edge.art.terrain` biome art +
  a parallel gameplay feature grid; stamped walled cities.
- `edge/groundwar/rules.py` — pure turn rules (movement, jump+AA reaction, LOS,
  detection/jamming, fire, resolve, garrison AI, sorties, outcomes). Only mutator.
- `edge/groundwar/app.py` — throwaway Textual shell (tui-tier exemption).

Deterministic from `(seed, planet_type, difficulty)` plus the battle's own rng
stream; all randomness flows through `Battle.rng`.

## Adopted production contract

The prototype establishes the tactical vocabulary we are retaining:

- terrain-as-board, scrolling viewport, cover/movement/LOS, seeded map identity;
- individual Marauder, Scout, and Command suits; point-budget composition and
  contested drop placement;
- IGOUGO assault turns, military-target pressure, city cowing, broadcast terms,
  civilian harm backfiring, retrieval pressure, and Resolve-based surrender;
- the survey sibling's movement, scanner bands, hints, trenches, supplies, and
  automatic dig resolution; and
- its procedural terrain and tactical art as the reference look, with a separate
  station-interior map and new art reserved for the later Cloud City gate.

Production deliberately changes the prototype's surrounding economy and state:

- real `Planet`/`Player`/`Ship` state replaces the setup menu, and one active
  operation is hashed, command-logged, saveable, reconnectable server state;
- one access classifier chooses survey for uninhabited/friendly/allied/owned
  landable worlds, assault for every inhabited landable world below the friendly
  threshold, and orbital-only for belts, gated jovians, and Core worlds;
- Stardock hires persistent recruits and sells suits; recruits use ship passenger
  capacity distinct from cargo and colonists, and a death loses recruit plus suit;
- local actions consume tactical resources, with main turns charged only at
  configurable local-turn thresholds and extraction always remaining possible;
- repeat survey visits retain position/hints/resolved discoveries but reset
  trenches and supplies; digging grants a unique provenance artifact and codex
  lore automatically, never latinum or loose parts;
- persistent planetary ground defense replaces `Planet.fighters` as invasion
  strength; fighters move wholly to space/sector combat;
- assault aftermath persists, surrender creates a limited protectorate, and later
  annexation requires elapsed time, recovered Resolve, and explicit political
  consequences; and
- mission survivors return to the ship, while a separate confirmed reinforcement
  action irreversibly converts recruits+suits into typed local defenders;
- a survey march no longer auto-halts the instant fresh disturbed ground comes into
  sight — a clue stays visible on the map for the whole march anyway, so the
  auto-stop cost more clicks than it saved (GW-WP13-FU1 parity audit);
- the scanner heat-map overlay defaults **off** rather than on, toggled with the
  same key as before (GW-WP13-FU1 parity audit); and
- pre-drop, the assault screen paints a coarse, fixed-radius AA hazard zone around
  each city's center rather than the POC's exact-battery-position radar — doctrine
  knowledge of a city's footprint, not sensor telemetry, so a remote client still
  cannot reverse-engineer interior defense placement before a trooper has actually
  seen it (GW-WP13-FU1, restoring *some* landing-danger read without reintroducing
  the leak GW-WP12 removed).

## Balance snapshot

A scripted competent bot (drop outside AA range, missile priority targets,
advance/broadcast) wins ~2/10 raids at `raid` difficulty, in 12–18 of 24 turns
when it wins — losses are clock/approach failures, not attrition. Humans should
land somewhat higher; tune in the YAML (`pressure`, `resolve`, suit costs).

## Productionization path

`GROUNDWAR_INTEGRATION_PLAN.md` is the executable work plan. Its milestones move
configuration and terrain into the production dependency graph, add frozen replay
models and ground access, ship the survey loop, replace fighter invasion with the
recruit/suit assault and persistent defense economy, then complete UI/migration/
multiplayer parity and the separately gated Cloud City interior. Until the
relevant work package lands, code under `edge/groundwar/` remains a prototype
harness rather than an authority over live game state.
