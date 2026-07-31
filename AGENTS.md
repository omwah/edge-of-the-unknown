# AGENTS.md — Edge of the Unknown

## What this project is

Edge of the Unknown is a game of **space exploration and discovery** built on the
mechanical bones of **TradeWars 2002** (the classic BBS door game), in
**Python 3.12+** with the **Textual** TUI framework. The TW2002 foundation
is inherited — warp-graph universe, port pair-trading in Fuel Ore /
Organics / Equipment, turns-per-day, planets — and the exploration-first
design is free to diverge from it as its own concepts take shape; **trading is
a means to an end**: it funds the engines, shields, sensors, cloaks, and
armaments needed to push outward and discover things. Key pillars:

- **Discoveries** — planets (which can be descended onto for surface sites:
  ruins, artifacts, ancient tech, crashed ships), shipwrecks, nebulae,
  black holes, space entities. Rarity *and* technology-progression value
  increase with warp-hop distance from the Core Space (distance bands).
- **Alien species** — each has a **disposition** on a continuous `0.0` (most
  hostile) → `1.0` (most friendly) scale, not a binary flag; the roster
  skews friendly. Per-player **attitude offsets** (raised by trading/favors,
  lowered by attacks) shift base disposition into an **effective
  disposition** that drives whether an encounter opens with greeting or
  violence, prices/barter, and tech unlocks. Each species has a tech level
  (travel speed + what aspect upgrades it can sell for **gold-pressed
  latinum**, the universal currency, or barter against artifacts), plus
  threat (damage) and interception (anti-flee) ratings whose use scales with
  how hostile it is; among hostile-leaning aliens, rarity scales inversely
  with threat. Player escape chance is always ≥ a config floor (default
  10%). Config thresholds (default hostility 0.35 / amity 0.65) name the
  bands; the **Core Space** (the protected central region, sectors 1–10) and
  the neutral home lanes around it host only friendly-band members of the alliance
  that governs the Core, while every other bloc holds its own friendly-band **home
  cluster** of worlds just outside the Core (so the whole Hub stays innately
  peaceable; near-home menace is alliance-political, not low disposition). Beyond
  disposition, each species carries a rich **parameter
  set** (DESIGN.md §6.1): a `threat_tier` (narrative difficulty, decoupled from
  raw threat), `combatant` flag, `trade_posture`, `treaty_mode`, `memory_model`
  (none / normal / never_forgets), `betrayal_model` (recoverable / permanent),
  a `befriend_price` task list, `pack_behavior`/escort composition, a `fleet`,
  a `starbase_policy`, a `persona`, a config-driven **`dialogue_pack`**
  (standing-keyed, persona-voiced conversation: a closed vocabulary of context keys →
  conditional line entries with **variant pools and a recency ring** so repeat encounters
  rephrase rather than replay; templated `{placeholders}`; species → persona → generic
  fallback; DESIGN.md §6.7), and one **signature mechanic** — a named,
  config-parameterized systemic hook (trojan-gift, reprogram-unlock,
  influence-gate, morality-judge, escalating-demand, literalist, contract-kill,
  …, DESIGN.md §6.2). Species are grouped into rival **alliances** (DESIGN.md
  §6.3): the player may belong to **at most one**, gated by an `admission_price`
  and a `membership_gate`; joining warms members and turns rival blocs hostile.
  Each non-governing alliance holds a compact **home cluster** of worlds just
  outside the Core — smaller than the Core, never adjacent to it, separated from it
  and from rival clusters by **neutral navigable lanes** of empty space, so the
  outer bands are always reachable without transiting a bloc's territory (DESIGN.md
  §5, §6.3).
  No alliance is privileged in the schema: the **Federation** is just an ordinary
  alliance that the default roster names as the **initial governor of Core
  Space** (`Game.core_governing_alliance_id`), and the player **starts as one of its
  members** — which is what makes the Core a safe home at the start. Core safety
  follows **whoever currently governs the Core**, not the Federation by name:
  joining any other bloc resigns that membership, and aligning with a bloc the
  governor counts as a rival makes **the Core Space itself unsafe to enter** —
  the governor's forces engage the player on sight until that allegiance is given
  up. Governance can change hands (a `covets_core` bloc seizing the Core via the
  player's deeds or NPC events, Phase 5), re-keying who is welcome there.
  Species also hold dispositions **toward each other** — an inter-species
  relation matrix plus dated **grudges/vendettas** (DESIGN.md §6.4–7.5) — which
  drives NPC-vs-NPC behavior and reputation spillover. The **species roster is a
  config file** — each game is generated against a named roster, the big bang
  draws a seeded *subset* of it (not every species need appear), a different
  game can use an entirely different source roster, and each species' base
  disposition is drawn per-generation from a bounded spread around its roster
  center, so disposition varies between universe generations.
- **Ship aspects** — cargo capacity, shields, engine speed (split into **warp
  speed** for travel and **combat speed** for evasion), cloak/stealth, sensors,
  armaments; upgraded via trade profits and alien tech. Every hull (player, NPC,
  and starbase) is a config-driven **ship class** (DESIGN.md §4): `role` (fighter
  / warship / capital_warship / transport / starbase / …), `length_m`, `speed`,
  `armament` (weapons with damage + `firing_arc` of ahead / all_round / spinal),
  and `defenses` (laser_turret / armour / screens / energy_plates /
  speed_and_size). **Starbases** are immobile ship classes — destructible
  set-pieces whose razing is the coin of alliance diplomacy.
- **Engine room** (DESIGN.md §4.1, *Lightspeed*-inspired) — the player ship's
  aspects are **derived from four slotted subsystems** (`spindrive`, `thrusters`,
  `screens`, `main_gun`) built from a small shared component vocabulary
  (accelerator / converter / radiator / secondary / turbine / burner / linkage /
  navigator) in tech tiers I–III. Combat damage **knocks out components**
  (localized degradation); repair is hybrid (carried **repair-kits** field-patch;
  full swaps/upgrades at Stardock or a friendly alien base). Spindrive efficiency
  gives **one global combat bonus**. Weapons are the spinal **Main Gun** plus
  finite **homing missiles** (no point-defense). NPC hulls keep flat
  aspects/defenses via an optional `subsystems` block, so localized damage is
  player-first.
- **Planets & orbital starbases** (DESIGN.md §4.2, *Lightspeed* §1.4.6-inspired) —
  every planet has a **`planet_type`** (terrestrial warm / cool / hot / cold,
  jovian, asteroid_belt, barren) that fixes its colonizability, a `yield_profile`
  over the Fuel Ore / Organics / Equipment trio, and a `habitability` cap — keeping
  the trio sacred (no fourth commodity) while expressing Lightspeed's
  metal/organics/radioactives/water as yield-and-habitability shaping. Planets carry
  **ownership** — `none` / an **alliance_id** / a **player_id** (a `player_id` so the
  model already fits eventual multiplayer): Core Space planets are owned by the
  governing alliance automatically (re-keying if governance flips), and the **unowned
  fraction rises monotonically with distance band**, so the frontier's reward is
  *claimable territory* as well as rarer finds. **Colonists are people, not a
  commodity** — never bought or sold like the Fuel Ore / Organics / Equipment trio.
  They are **recruited** (they have a choice): enlisted at Stardock for a per-head
  latinum *incentive*, or by emigration from inhabited worlds with a positive
  disposition toward the player. They ride a **separate occupancy limit**
  (`Ship.colonist_capacity`), not cargo holds, so peopling a colony never competes
  with trade cargo. A planet may carry an **orbital
  starbase** that reuses the engine-room model **minus thrusters/spindrive, plus a
  `fusion_reactor`** (built from the same shared component vocabulary, so parts are
  fungible across ships and bases). **Derelict is not a special type or stored flag** —
  a base is derelict when broken/missing components leave it unable to power or defend
  itself; the big bang makes an **unowned**-world base derelict by **removing or
  damaging its components** (so repair is just refilling slots), leaving a
  component-salvage cache to strip (engine-room cannibalize) or **repair and claim**
  into an operational forward foothold. A base on an owned planet is built intact and
  **defends the planetary system** against entrants
  hostile to its owner, with hostility resolved through the alliance system (rival
  bloc / at-war / hostile effective disposition). Defense strength scales with
  surviving components and reactor efficiency.

Deterministic, testable, extensible to multiplayer later. Single-player
first.

## Authoritative spec

**`docs/DESIGN.md` is the authoritative design document. Read it before any
architectural decision.** It was produced by analyzing the source code of
seven existing TradeWars clones and the original 1986 TradeWars II BASIC
source. Do not contradict it casually; if implementation reality forces a
deviation, update DESIGN.md in the same change and note the reason.

**Keep the dialogue spec in sync.** The alien-dialogue data model, vocabulary,
selection, validation, and authoring contract are documented for humans *and
LLMs* in two embedded places: the spec header comment at the top of
`config/alien_dialogue_default.yaml` (the authoring/checking reference for
`personas` and `species_grammars`) and the prompt context the authoring tool
feeds its backend (`edge/dialogue/authoring/pipeline.py` — `build_prompt` /
`_structure_brief`). Whenever you change the dialogue mechanics — the
`DialogueWhen` / `DialogueChoice` / `DialogueLine` schema (`edge/core/config.py`),
the intent vocabulary or placeholder sets (`edge/dialogue/intents.py`), the
selector or `validate_dialogue` rules (`edge/dialogue/select.py`), the
`species_grammars` merge (`edge/config.py`), or branch/recency behaviour —
update **both** of those in the same change (and DESIGN.md §6.7/§13 as above) so
the on-disk instructions stay correct and complete enough to author and validate
a corpus.

**Keep the sector-scene note in sync.** `docs/SECTOR_SCENE_COMPOSITION.md` is the
authoritative note for the TUI arrival view (`edge/tui/widgets.py` →
`_SceneComposer` / `SectorScene`) and the docked station headers
(`edge/tui/station_art.py` → `StationArtRow` / `station_icon_dimensions`): the
scale chain off the rendered primary body, the per-kind station caps and their
non-saturation rule (`SceneArtConfig.station_dimensions`, `config/default.yaml
→ scene:`), placement/occupancy/labels, determinism seeds, and the
`sector_station_reference` publish/guard seam. Read it before touching scene
composition, station sizing, or the `scene:` config block; when you change any
of those, update the doc's rules *and* shipped numbers in the same change —
its §2 cap rule exists because a stale cap once silently froze station
responsiveness.

**Keep the checkpoint field set in sync.** `AUTHORITATIVE_STATE_FIELDS` in
`edge/store/state_codec.py` is the single, shared list of the `UniverseState`
containers that both the load checkpoint (DESIGN.md §12) and `state_hash`
(`edge/store/snapshots.py`) treat as authoritative. It enumerates exactly the
fields that evolve during play; everything else on `UniverseState`
(`adjacency`, `core_hops`, `spatial_ids`, `sector_pos`, `species_knowledge`,
`species_home_disposition`, `home_clusters`, `topology_mode`, the `rng`) is a
seed-derived runtime cache regenerated by `generate()` and deliberately
excluded. **Whenever you add, remove, or rename a `UniverseState` field, update
`AUTHORITATIVE_STATE_FIELDS` in the same change** — add it if a reducer or cron
mutates it during play (so it must survive a checkpoint), and leave it out only
if `generate()` rebuilds it identically from `(seed, config)` with no in-play
mutation. An authoritative field must also hold a **codec-supported type**
(primitive / `Enum` / `edge.core` dataclass / dict / tuple / set); a field of an
unsupported type (`datetime`, `bytes`, `Path`, …) makes `_encode` raise, which
`GameService.checkpoint()` swallows — so no checkpoint is ever written and the
feature silently no-ops (the game stays correct, just slow to load). A new
authoritative field omitted from the tuple is **silently
dropped from every checkpoint and reset to its generated default on load**
(and drops out of `state_hash`, weakening determinism checks), while a
runtime-only cache wrongly added forces the codec to serialize regenerable
data. When in doubt, treat the field as authoritative. The `state_hash`
round-trip guard in `load_game` will reject a *corrupt* checkpoint, but it
cannot catch a *missing* field — both sides read the same tuple, so an
omission is consistent and invisible until the value is lost.

## Reference code (read-only)

`references/` contains shallow clones of the analyzed codebases (recreate
with `scripts/clone_references.sh` if absent). **Never modify these; they are for
reading only. Never copy code from them verbatim** — they are inspiration
and a source of constants/algorithms, and they carry assorted licenses
(GPL-era code among them). Reimplement ideas cleanly.

`docs/REFERENCES.md` catalogs what each clone is for — read it before mining
`references/` for an algorithm or constant.

## Work completed so far

**Phases 1, 1.5, 2 (incl. the route follow-up WP14–WP18), and 3
(`docs/PHASE3_PLAN.md`, WP19–WP44 / M10–M15) are implemented and shipped.**
Phases 5 and 4 are planned together in `docs/PHASE5_4_PLAN.md` (WP45–WP69 /
M16–M21) with **Phase 5 executed before Phase 4** (the plan's Context records
why; interview decisions of July 2026 are resolved inline). WP45 was the
spec-delta commit landing that plan; implementation starts at WP46.

## Architecture rules (non-negotiable)

- Layered, downward-only dependencies: `edge/core` (pure rules, **no I/O,
  no async, no Textual imports**), `edge/dialogue` (pure salience dialogue
  system, DESIGN §6.7 — sits between the lower `edge.core` modules it imports
  and `edge.core.rules`/`edge.server` which import it, so the graph stays
  acyclic; its `dialogue/authoring/` subpackage is the **one dev-only impure
  corner**, never imported by runtime — and the *only* place an upward
  `edge.tui` import is allowed: `authoring/playtest.py` drives the real contact
  screen for dialogue play-testing, imported lazily so the runtime path never
  pulls it in), `edge/bigbang` (generation, networkx),
  `edge/engine` (asyncio background ticks), `edge/store` (SQLite behind a
  repository interface), `edge/server` (command -> event service; fog of
  war enforced at the `to_public(context)` serialization boundary),
  `edge/tui` (Textual app only).
- All randomness flows through a seeded `random.Random` owned by game
  state. A game must be reproducible from `(seed, command log)`.
- Economy invariants enforced in core, always: no negative balances, goods
  are conserved by trades, every state mutation is transactional.
- Game constants (ship stats, prices, universe size) live in config files,
  not code.
- Single-player embeds the server in-process; never let the TUI reach
  around the service API into core state directly.

## Roadmap

Per-phase scope lives in `docs/DESIGN.md` §14, with the per-work-package
breakdowns in `docs/PHASE3_PLAN.md` (WP19–WP44 / M10–M15) and
`docs/PHASE5_4_PLAN.md` (WP45–WP69 / M16–M21). Read those rather than a copy
here.

## Conventions

- Python >= 3.12, `ruff` + `mypy --strict` on every real layer — `core/`,
  `bigbang/`, `store/`, `server/`, `engine/` (the throwaway `tui/` is exempt).
- Tests: pytest + hypothesis. Property tests for economy invariants;
  golden-master replays of command logs against fixed seeds; bigbang
  validation across many seeds; Textual Pilot for UI flows.
- Dependencies: see `pyproject.toml`. Add nothing else without updating
  DESIGN.md §15.
- Commit style: small, phase-tagged (e.g. `p1: bigbang cluster pass`).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
