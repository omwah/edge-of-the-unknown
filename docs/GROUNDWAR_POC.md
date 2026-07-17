# Ground-war POC (`edge-groundwar`)

A standalone, Starship-Troopers-inspired turn-based tactical game built from Edge
of the Unknown parts, as a proof of concept. **Not integrated** with the live game:
if it proves out, it would replace the surface screen for *populated* planets (the
discovery mini-game expanding to cover uninhabited/conquered worlds instead).

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

## Layout

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

## Balance snapshot

A scripted competent bot (drop outside AA range, missile priority targets,
advance/broadcast) wins ~2/10 raids at `raid` difficulty, in 12–18 of 24 turns
when it wins — losses are clock/approach failures, not attrition. Humans should
land somewhat higher; tune in the YAML (`pressure`, `resolve`, suit costs).

## Integration path (later, if adopted)

Feed real `Planet` state instead of the setup menu: `planet_type` → terrain,
citadel level/gun from the planet, garrison from `Planet.fighters`, ownership →
who you're raiding; surrender outcome → ownership flip / tribute at the
service-layer seam. Resolve events would become command-log events.
