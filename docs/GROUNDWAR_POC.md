# Ground-war prototype and production source (`edge-groundwar`)

A standalone, Starship-Troopers-inspired turn-based tactical game built from Edge
of the Unknown parts. The prototype's mechanics and look were **adopted** as the
source for the production ground-operation system specified in `DESIGN.md`
§§3–4.2, 7, 10–11, 13–14 and `GROUNDWAR_INTEGRATION_PLAN.md` (GW-WP01–13), reached
in the live game from `PlanetScreen.action_descend` and rendered by
`edge.tui.screens.ground_assault`/`ground_expedition`.

**GW-WP14 retired the prototype's own duplicate engine and retargeted this app onto
those same production rules and screens.** `edge-groundwar` is no longer a separate
implementation to keep in sync — it is a lightweight playtest entry point: its
`SetupScreen` builds a throwaway single-planet `GameService`
(`edge.groundwar.harness`), dispatches `BeginAssault`/`BeginSurvey` into it, and
hands off entirely to the production `GroundAssaultScreen`/`GroundExpeditionScreen`.
`findart.py` and `widgets.py` remain live production dependencies despite living
under this nominally-POC package.

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

## Current layout

- `config/groundwar_default.yaml` — every balance constant, read by both the live
  game and this playtest app.
- `edge/groundwar/config.py` — typed loader (a thin re-export over the production
  `GameConfig.groundwar` block; no divergent balance).
- `edge/groundwar/harness.py` — builds a throwaway single-sector, single-planet
  `UniverseState` (assault: a below-friendly world sized for a droppable raid, plus
  a loaded ship; expedition: an owned/unowned world with real `Discovery` records
  salted onto it) so `SetupScreen` can start a real `GameService` without a full
  big-bang universe.
- `edge/groundwar/app.py` — `SetupScreen` (mode / planet / difficulty / world / seed
  pickers, the platoon composer) plus `GroundwarApp` (an `edge.tui.app.EdgeApp`
  subclass, so it gets the same chrome/theme/client wiring as the live game). Owns
  no ground-operations rules of its own — `edge.core.groundwar` is the only
  implementation, exercised through the identical production screens.
- `edge/groundwar/findart.py` / `widgets.py` — production dependencies (Field Finds
  art, assault map glyphs/colors) that happen to live in this package.

Deterministic from `(seed, planet_type, difficulty preset)`: the harness state feeds
the same `BeginAssault`/`BeginSurvey` reducers the live game uses, which draw their
own operation seed from `state.rng`.

## Adopted production contract

The prototype establishes the tactical vocabulary we are retaining:

- terrain-as-board, scrolling viewport, cover/movement/LOS, seeded map identity;
- individual Marauder, Scout, and Command suits; point-budget composition and
  contested drop placement;
- IGOUGO assault turns, military-target pressure, city cowing, broadcast terms,
  civilian harm backfiring, retrieval pressure, and Resolve-based surrender;
- the survey sibling's movement, scanner bands, hints, trenches, supplies, and
  automatic dig resolution; and
- its procedural terrain and tactical art as the reference look; the station's
  interior map and art (GW-WP15) are a separate discrete generator, not a reuse
  of this terrain, and now feed a live Cloud City assault (GW-WP16).

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

## Balance snapshot (historical, pre-GW-WP14)

A scripted competent bot (drop outside AA range, missile priority targets,
advance/broadcast) won ~2/10 raids at the prototype's own `raid` difficulty
preset, in 12–18 of 24 turns when it won — losses were clock/approach failures,
not attrition. That preset table (`GwDifficulty`/`config.groundwar.difficulties`)
no longer exists: production derives difficulty from live world state
(`edge.core.groundwar.assault.derive_difficulty`), so this snapshot is a rough
historical reference, not a live number. Tune balance in the YAML
(`assault_difficulty`, `garrison_economy`, `pressure`, `resolve`, suit costs) and
re-measure against `edge/bot/scripts/assaulter.py` for a current read.

## Productionization path

`GROUNDWAR_INTEGRATION_PLAN.md` is the executable work plan (GW-WP01–16,
GW-M1–M5 — all shipped). Its milestones moved configuration and terrain into
the production dependency graph, added frozen replay models and ground access,
shipped the survey loop, replaced fighter invasion with the recruit/suit
assault and persistent defense economy, retired the superseded abstract
surface/invasion paths, retired this app's own duplicate engine so
`edge.core.groundwar` is the sole authority over live game state (GW-M4), and
— finally — built the station-interior generator/art and adapted tactical
assault to it, so a below-friendly Cloud City now assaults through the same
production `GroundAssaultScreen` a terrestrial world does (GW-M5). Balance
tuning (garrison counts, defense density, emplacement geometry, for both
terrestrial and Cloud City assaults) is the one deliberately deferred
follow-up, flagged in GW-WP13's status note.
