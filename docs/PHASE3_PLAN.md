# Phase 3 — Danger (+ topology modes, the Entity, dialogue depth)

> Companion to `DESIGN.md`, `PHASE1_PLAN.md`, `PHASE1_5_PLAN.md`, `PHASE2_PLAN.md`,
> and `PHASE2_ROUTE_FOLLOWUP.md`. DESIGN is the authoritative *what*; this is the
> *how and in what order* for Phase 3. Where the two disagree, DESIGN wins and is
> corrected in the same change (CLAUDE.md).
>
> **Status: reviewed draft — interview decisions resolved.**

## Context

Phase 2 (+ the route follow-up, WP1–WP18) shipped the exploration pivot: the
engine-room component model with derived aspects, StarDock services and multiple
hulls, typed/owned planets with colonization, derelict starbases as salvage
caches, the banded discovery system with sensors and codex, friendly alien
species with config-driven salience dialogue and authored reply menus, tech
barter, alien-ship drift, and the Computer suite. Every Phase-3 seam was left
deliberately: `rules._should_interrupt` is still the Phase-1 `False` stub, the
`EncounterScreen` is a stub fed by `dummy.py`, `FieldPatch` is structurally
present but unreachable, combat intents are authored but inert, and
`_gate_choice` greys ATTACK/TREATY replies.

Phase 3 is **danger**. Per DESIGN §14 the exit criterion is *"the outer bands
feel scary but irresistible; players quote their narrow escapes, and committing
to one alliance visibly remakes the map."* That sentence dictates the spine:
hostile-band species and a real encounter roll (so the outer bands threaten),
component-localized combat with a floored escape chance (so escapes are narrow
rather than fatal), and joinable alliances over real territory (so commitment
remakes the map).

Phase 3 also lands three player-directed system changes that go beyond the §14
list, resolved by design interview (June 2026):

1. **Big bang topology modes.** Today `_bridge_groups` hangs every cluster off
   a single parent bridge toward the core — a spanning tree of groups — so all
   traffic to the outer bands funnels through narrow chokepoints:
   trunk-and-branches. Phase 3 adds a config-selectable `topology_mode`:
   `trunk` (today's algorithm, kept byte-identical) and `expansive` — a
   **band-lattice web** where each cluster bridges to 2–4 clusters at similar
   core-depth plus 1–2 inward/outward, forming widening ring-lattices with no
   single-bridge chokepoints.
2. **The Entity.** The `entity` `DiscoveryKind` stops being a common salted
   salvage object and is **replaced entirely** by one roaming, dialogue-only
   singular being per universe — a roster species carrying a new
   `singular_entity` flag (the Concordance / `cosmic_arbiter` in the default
   roster, its lore updated from fixed-lair to roaming). It fields no ships and
   can never be fought; on the contact screen its artwork fills the slot where
   ship art would render. It is found by pursuit: alien leads record its
   **last-known sector and go stale** as it drifts, while in-sector the sensor
   panel **always shows an anomalous-presence hint** but opening contact is
   **sensor-rating-gated**. First contact stamps a Legendary codex entry.
3. **Dialogue depth.** Encounter-based conversation branches carried by **both
   state layers** — a per-contact session (facts accumulated within a visit,
   feeding `DialogueWhen.criteria`) plus small persisted per-species arc flags
   for cross-visit unlocks — and four uniqueness levers: situational facts,
   cross-encounter callbacks, a bigger authored corpus, and **per-instance
   recency rings** (today per-kind).

This plan decomposes Phase 3 into twenty-six work packages (WP19–WP44) across
six milestones (M10–M15), ordered so band semantics settle before hostiles are
placed, hostiles and territory exist before the encounter roll goes live, the
dialogue-session vocabulary freezes before the corpus is authored against it,
and every milestone leaves the game playable.

All work obeys the architecture rules in CLAUDE.md: downward-only layer deps
(`core` has no I/O / async / Textual imports; `dialogue` sits between the lower
core modules and `core.rules`/`server`), all randomness through the state-owned
RNG, invariants in core, every constant in config, the TUI only through the
`GameService` + `session` projection boundary. `ruff` + `mypy --strict` stay
green on `core/dialogue/bigbang/store/server/engine`; `tui/` is exempt.

---

## Scope and non-goals

**In scope (DESIGN §14 Phase 3 + the interview additions):**

1. Topology modes: `trunk` / `expansive` band-lattice, per-mode band retune,
   both modes validated permanently (§5).
2. Hostile-band species: band-graded disposition draws, threat/interception
   live, threat tiers, encounter weights inverse to threat (§6, §10).
3. Alliance home clusters + neutral lanes generated for real (§5 step 6) —
   currently spec-only.
4. The encounter system: interrupt roll, cloak/nebula detection,
   greeting-vs-violence disposition roll, pack/escort spawns, fight/flee
   rounds, firing arcs, the ≥10% escape floor, homing missiles (§10).
5. Localized component damage + field-kit repair + StarDock restoration,
   escape pods, salvage (§4.1, §10).
6. Consequences: attitude souring, `memory_model`/`betrayal_model`, grudges,
   alignment/experience, Core law keyed to the governing alliance (static
   Federation governor this phase) (§6.5, §10).
7. Dialogue: per-contact sessions, situational facts, cross-visit arcs,
   per-instance recency, combat dialogue live, corpus expansion (§6.7).
8. Signature-mechanic hooks (`morality_judge`, `literalist`, `trojan_gift`,
   `reprogram_unlock`, `escalating_demand`, `contract_kill`, brokers, …) (§6.2).
9. The Entity: singular roaming dialogue-only discovery replacing the salted
   `entity` kind (§7).
10. Alliances joinable: admission price, membership gate, rival fallout,
    cluster hostility (§6.3).
11. Inter-species relations matrix, reputation spillover, NPC-vs-NPC stance
    (§6.4).
12. Starbase set-pieces: assault, planetary-system defense, razing
    consequences, derelict repair→claim→foothold (§4.2, §10).
13. Sector fighters (off/def/toll), mines, beacons, black-hole hazards live
    (§10).
14. Goal-directed NPC movement, NPC traders moving real goods, homeworld raids
    with bounties (§8, §10).

**Explicitly deferred (DESIGN §14 Phases 4–5), so Phase 3 must not build them
but must leave clean seams:**

- Multiplayer (`server.net`, lobby, corporations).
- The order-book economy; `Port.latinum` stays a soft figure.
- **Dynamic Core governance** — `Game.core_governing_alliance_id` never changes
  hands this phase; Core law *reads* it (WP38) so Phase 5 only has to write it.
- Citadels and planetary combat; the Armid/limpet mine split; probes /
  interdictor; tavern/noticeboard; sysop console; scripting hooks.
- Full forward-base services (refuel/repair/banking at player bases) — Phase 3
  ends at repair→claim→defends; services are Phase 5.

## Framing corrections (found against the code, June 2026)

Two items the §14 wording implies exist but do not; both are folded into WP
scope below:

1. **The §4 weapon/defense schema is unimplemented.** `ShipClassConfig`
   (config.py) carries flat aspects + optional `subsystems` only — no
   `armament`, no `firing_arc`, no `defenses`, no weapon `special`s anywhere in
   code or config. WP25 *adds* the schema rather than consuming it.
2. **Alliance home clusters are spec-only.** `edge/bigbang/aliens.py` places
   species *ship* clusters and stamps `Region.controlling_alliance_id` post-hoc
   from wherever ships landed; there is no territory carve, no alliance-owned
   cluster worlds tied to blocs, and no neutral-lane validator. WP23 implements
   DESIGN §5 step 6 for real.

---

## Cross-cutting: replay, state-hash epochs, layering

The Phase-2 golden-master rail (PHASE2_PLAN.md "Cross-cutting") still governs:
bigbang output is free (pure function of `(seed, config)`, RNG-disciplined,
appended draws or salted sub-RNGs); player progress rides the command log
(every new command/event gets `store/codec.py` entries + round-trip tests);
any new field on a hashed entity regenerates golden masters **in the same
commit**, batched per milestone. Phase 3 adds nine normative constraints —
referenced by number from the WPs:

- **H1 — Contact-session lifetime.** "Opened at hail, discarded at farewell"
  leaks: the player can warp away, be interrupted, or close the screen.
  `Player.contact_session` is therefore cleared by the **movement and
  encounter reducers**, not just farewell — the TUI is never trusted to close
  it. Its validity is structural: it names a species instance and sector, and
  it is only ever read when both still match.
- **H2 — Entity presence is computed live.** `Player.detected` is an
  entry-time snapshot of discovery ids; the Entity moves, so its hint and
  sensor gate must be computed from its **current** sector — in the projection
  *and re-checked in the `Hail` reducer*, so a replayed command log cannot
  smuggle a contact below sensor rating.
- **H3 — Leads are immutable.** The drift cron never mutates `Player.leads`
  (leads are appended by `AcceptLead` only). Staleness is **derived read-only
  at projection**: lead sector ≠ Entity's current sector ⇒ "trail gone cold".
  Re-asking a speaker yields a fresh lead.
- **H4 — RNG discipline.** Encounter/combat rolls draw from `state.rng`
  inside reducers only; projections never draw. The `contact_view` /
  `_converse_choice` lockstep pattern (view shows exactly what the reducer
  will resolve, both fed identical inputs) is preserved for combat views.
- **H5 — Situational facts are state.** Anything dialogue keys on must
  reconstruct under replay. `Player.last_combat` (species roster_id, outcome,
  day) is written by combat reducers; UI memory never feeds dialogue.
- **H6 — One golden regeneration per epoch.** `expansive` lands behind
  `topology_mode: trunk` default (zero churn); the default flip rides the
  `config_version 2→3` bump in WP22, which regenerates goldens anyway. Later
  hashed-field additions batch per milestone (M11, M12, M13, M14 batches).
- **H7 — Recency re-key.** `Player.dialogue_recency` and the `encounter_rng`
  seed re-key from `(roster_id, context)` to `(species_instance_id, context)`
  inside the M12 batch — one epoch, not two.
- **H8 — Layering.** New pure logic lives in `edge/core` (`encounters.py`,
  `combat.py`, `mechanics.py`, `npc.py`) and `edge/dialogue` (`facts.py`,
  which may import `edge.core.models` and stays below `core.rules`).
  Goal-directed NPC planning is pure core, *scheduled* from `edge/engine`
  crons on the `alien_drift` rail (salted sub-RNG + a `Game` sequence
  counter). The Entity is an ordinary `AlienSpecies` row — no layer learns a
  new entity kind. Art selection stays at the projection boundary (the DTO
  carries a flag; the TUI renders).
- **H9 — Dialogue sync contract (AGENTS.md).** Every WP that touches
  `DialogueWhen`/`DialogueChoice`/`DialogueLine`, the intent vocabulary, or
  the selector updates the `config/alien_dialogue_default.yaml` spec header,
  the authoring prompt context (`edge/dialogue/authoring/pipeline.py`
  `build_prompt`/`_structure_brief`), and DESIGN §6.7/§13 **in the same
  change**.

---

## Milestones

- **M10 — Dangerous worldgen.** WP19–WP23. Spec deltas land; the graph gains
  its two topologies; bands retune; the friendly clamp comes off outside the
  Hub; alliances get real home territory. *Playable throughout: hostiles are
  placed but the encounter roll is still the stub, and FIGHT stays greyed —
  the world darkens before it bites.* One config epoch (`config_version 3`)
  at WP22.
- **M11 — Encounters & combat.** WP24–WP27. The interrupt roll goes live:
  detection, greeting-vs-violence, pack spawns, fight/flee rounds, localized
  damage, pods, salvage, and the consequences (attitude, grudges,
  alignment/experience). *Playable: a fight can be won, lost, or fled — with
  the existing standing-keyed dialogue.*
- **M12 — Conversation depth.** WP28–WP32. Per-contact sessions, situational
  facts, per-instance recency, cross-visit arcs, combat dialogue, then the
  corpus authored against the frozen vocabulary. *Playable: the same alien
  never reads the same way twice, and remembers you.*
- **M13 — Signature mechanics & the Entity.** WP33–WP37. The hook framework,
  then the Entity (generation, presence, pursuit) so first contact delivers a
  real `morality_judge` verdict, then the transactional hooks. *Playable: the
  Entity can be hunted, found, and judged.*
- **M14 — Territory & alliances.** WP38–WP41. Joinable blocs, Core law,
  relations/spillover, starbase set-pieces, fighters/mines/beacons/hazards.
  *Playable: committing to one alliance visibly remakes the map.*
- **M15 — A living, hunted frontier.** WP42–WP44. Goal-directed NPC movement,
  NPC traders, homeworld raids/bounties, and the exit-criterion balance pass.

---

## M10 — Dangerous worldgen

### WP19 — Spec deltas: DESIGN.md + this plan (S/M)

Land the DESIGN.md edits this plan assumes, in the same change as the plan
itself, plus the AGENTS.md roadmap touch-up. Summary of the deltas:

- **§5:** topology modes on `BigBangConfig` (+ per-mode band-threshold
  defaults — a flatter graph compresses hop distances); §5.1 notes that the
  BFS-fan embedding hides cross-links and records the WP21 fix (angle from
  the mean of all min-hop parents, still stdlib O(n)); the neutral-lane /
  home-cluster invariants move from spec-only to implemented (WP23).
- **§6.1:** `singular_entity: bool` roster flag — always drawn, exactly one
  instance, no satellites, outside band guarantees.
- **§6.7:** the per-contact session layer (+H1 lifetime), situational facts,
  persisted `species_arcs`, per-instance recency; combat intents flip from
  authored-but-inert to live.
- **§7:** *Space entities* rewritten — `entity` removed from the salted
  tables; the one roaming Entity, pursuit discovery (stale leads + always-on
  hint + sensor-gated contact), Legendary codex stamp.
- **§10:** the encounter-state/command model (hashed `Encounter`, rounds as
  commands), the greeting-path handoff to the contact screen, the Entity's
  sector hint, the session-dialogue tie-in for combat lines.
- **§13:** the new invariants — escape floor, band-graded placement, both
  topology modes × many seeds, exactly-one-Entity, cluster/lane checks,
  dialogue-session determinism.
- **§4 / §14 / AGENTS.md:** the new Player/Ship fields (`contact_session`,
  `species_arcs`, `last_combat`, `alignment`, `experience`,
  `active_encounter`; `armament`/`defenses`); the Phase-3 roadmap paragraph
  names topology modes, the Entity, and dialogue depth; the planning-docs
  pointer gains `PHASE3_PLAN.md`.

Files: `docs/DESIGN.md`, `docs/PHASE3_PLAN.md` (this file), `AGENTS.md`.
Tests: none (docs). Commit `p3: WP19 phase-3 spec deltas + plan`.

### WP20 — `topology_mode` + the expansive band-lattice (M)

**Config (`edge/core/config.py`, `config/default.yaml`).**
`BigBangConfig.topology_mode: Literal["trunk", "expansive"] = "trunk"`. The
default stays `trunk` in this WP (H6) — the flip, if WP21 recommends it, rides
the WP22 epoch.

**Generator (`edge/bigbang/generator.py`, `edge/bigbang/topology.py`).**
Branch `_bridge_groups` into:

- `_bridge_groups_trunk` — today's body, moved verbatim. Its output for a
  fixed seed must be **byte-identical** to the current algorithm, pinned by a
  regression test, so existing goldens do not move.
- `_bridge_groups_expansive` — stratify the groups into concentric rings (the
  Core is ring 0; membership is a seeded shuffle sliced into rings of
  `isqrt(n_groups)`), then build a **ring road** per ring (its groups wired
  into a cycle) plus **≥2 radial spokes** between each consecutive ring pair on
  distinct outer groups, plus a few one-way chords. Cycles-plus-two-spokes make
  the graph **bridgeless** (no inter-region cut edge), and spoke demand is only
  ~2 per ring boundary — not per group — so the 10-sector Core is never
  saturated (the failure mode of a per-group inward rule, confirmed at 1000
  sectors during implementation). The two mode branches never share a draw
  sequence, so trunk output is unaffected.

`_cluster_groups` (contiguous-id slices) is unchanged — spatial ids (§5.1)
key off group structure, not bridging.

Files: `edge/bigbang/generator.py`, `edge/bigbang/topology.py`,
`edge/core/config.py`, `config/default.yaml`, `edge/bigbang/validate.py`
(an expansive-only `_check_expansive_no_chokepoint`, so generation retries a
rare gap), `tests/test_bigbang.py`.
Tests: trunk-mode byte-identical graph (verified via `git stash` diff of
`state_hash` — identical); expansive across 100 seeds — single reachable
component, degree cap ≤ 6, and the bridgeless property (removing any single
inter-region warp leaves every sector reachable); the two modes differ; trunk
still contains chokepoints. No golden regeneration (default unchanged).

### WP21 — Band retune per mode + validator/embedding verification (M)

The ring-road lattice gives `expansive` a different hop-distance profile than
trunk (in practice a *deeper* one — the ring roads lengthen shortest paths, so
with the trunk thresholds most sectors fall into Void). The four bands must be
made to stay populated and every hop-window check must still pass under
`expansive`.

- **Bands (shipped):** `BigBangConfig.bands` stays the trunk defaults; an
  optional `bands_expansive` override (Hub 0–14 / Frontier 15–35 / Deep 36–58 /
  Void 59+) is resolved by `active_bands()` at generation. **Same band names in
  the same order — only the hop windows differ** — enforced by a config
  validator (`_check_band_names_match`), so every name-keyed path (placement,
  validation, UI) is mode-agnostic. All threshold consumers (generator, validate,
  populate, aliens) route through `active_bands()`. At 1000 sectors this keeps all
  four bands populated (25/25 seeds sampled) with an outward-growing gradient
  (Hub ≈ 130, outer bands ≈ 285–300).
- **Hop-window checks re-verified under expansive:** `_check_profitable_pair`
  (opposed pair ≤ 5 hops of the Core), StarDock placement within
  `stardock_min/max_hops`, `_check_discovery_gradient` strict monotonicity, ≥1
  contact per band, unowned-planet monotone fraction — all pass at 1000 sectors
  (10/10 seeds generate cleanly). *(Note: `bands_expansive` is tuned to the
  ~1000-sector default; smaller universes stay shallow — trunk's bands are
  likewise scale-tuned.)*
- **Embedding (shipped):** the radial fan hung every sector off a single BFS-tree
  parent, blind to the lattice's cross-links. Each sector's angle now blends its
  own fan slot with the (already-refined) angles of **all its min-hop parents**
  via a circular mean — the own-slot term keeps sibling wedges distinct while
  the parents pull a lattice node toward the centroid of its inner neighbours.
  One extra stdlib O(n·deg) pass, deterministic, still outside `state_hash`.
- **Dev tooling (shipped):** `python -m edge.bigbang --mode trunk|expansive`
  (composes with `--render`/`--inspect`); the spring-layout PNG (`render.py`)
  is the visual diff proving the lattice (the nav fan hides it by construction).
- **Deliverable:** `expansive` recommended as the default for new games, recorded
  in DESIGN §5; the actual flip is executed in WP22 with the config epoch.

Files: `edge/core/config.py`, `config/default.yaml`, `edge/bigbang/generator.py`,
`edge/bigbang/validate.py`, `edge/bigbang/populate.py`, `edge/bigbang/aliens.py`,
`edge/bigbang/embedding.py`, `edge/bigbang/__main__.py`, `tests/test_bigbang.py`,
`tests/test_embedding.py`.
Tests: validity across 100 seeds in **both modes** (the permanent matrix); the
`active_bands()` resolver; the band-name-match validator rejecting a mismatch;
all-four-bands populated with an outward gradient at 1000 sectors; expansive
embedding determinism + Core pinned to origin. Trunk output stays byte-identical
(re-verified by `state_hash` diff after the config changes).

### WP22 — Hostile-band placement + the Phase-3 config epoch (M)

The Phase-2 friendly clamp comes off, outside the Hub. **Shipped.**

- **Placement (`edge/bigbang/aliens.py`).** `_friendly_disposition` → the
  band-graded `_band_disposition`: the innermost band (Hub) stays clamped
  friendly and each band's **guaranteed resupply anchor** (the first kind
  assigned to it) is drawn friendly; every other outer-band species takes the
  band's downward `band_disposition_bias`, so hostiles spawn and mean stance
  falls outward. A kind's base is memoised per-kind at its first placement
  (reputation is per kind), so governing/StarDock Core-welcome contacts filter
  out any kind already anchored hostile in a deep band. A **non-friendly
  cluster's satellites are kept out of the Hub** (they can dip one band inward
  at trunk's shallow scale — the case that first tripped the validator).
- **Encounter config.** A new `EncountersConfig` (`encounters:` in
  `config/default.yaml`): per-band `interrupt_chance` (0 in the Hub, rising
  outward) and inverse-threat weighting params — authored here for the epoch,
  **read by WP24**.
- **Validator (`edge/bigbang/validate.py`).** `_check_species`: Hub species all
  friendly (peaceable); Core + governor placement (unchanged); ≥1 **friendly**
  contact per band (resupply). The *mean-disposition-falls-outward* gradient is
  **an aggregate test over many seeds, not a per-generate validator** — the
  mandated per-band friendly anchor plus small per-band samples make strict
  per-seed monotonicity too noisy (would thrash the retry loop); DESIGN §13
  frames it as a suite property, which is honoured here.
- **Epoch (H6).** `config_version` 2→3; `topology_mode` default flipped to
  `expansive`; the generated-state fingerprint changes accordingly. The
  golden-master tests are **self-consistency round-trips** (save→reload,
  generate→replay), so they re-baseline automatically and stay green — no
  frozen-hash fixtures to hand-edit. Full suite (1389) green post-flip.

Files: `edge/bigbang/aliens.py`, `edge/bigbang/validate.py`,
`edge/core/config.py`, `config/default.yaml`, `tests/test_aliens.py`,
`tests/test_bigbang.py`, `tests/test_config.py`, `tests/test_service.py`.
Tests: Hub-peaceable + Core-placement across seeds; outer bands spawn hostiles;
the aggregate mean-disposition gradient (all four bands, non-increasing) at
1000 sectors; the full-validity matrix parametrized over **both modes** × 100
seeds; `EncountersConfig` loads.

### WP23 — Alliance home clusters + neutral lanes, for real (M/L)

Implements DESIGN §5 step 6 (framing correction 2): each non-governing
alliance in the drawn cast gets a compact home cluster — 3–6 sectors in the
Hub / inner Frontier, never Core-adjacent, never warp-linked to a rival's
cluster — its regions stamped `controlling_alliance_id`, its planets
alliance-owned, and its bloc's friendly-band members placed there (reworking
`_place_cluster` / `_assign_region_control` from "wherever the ships landed"
to "the bloc's carved territory"). Everything else is neutral lanes.

Runs on the species sub-RNG with appended draws; the golden regeneration
rides the WP22 epoch when landed in the same milestone batch (recommended).
Satisfiability risk under `expansive` (a denser Hub makes non-adjacency
harder) is absorbed by the §5 bounded-retry pattern and checked across the
full seed matrix.

Files: new `edge/bigbang/clusters.py` (or grow `aliens.py`),
`edge/bigbang/populate.py` (ownership tie-in), `edge/bigbang/validate.py`,
`config/alien_roster_default.yaml` (per-alliance cluster hints),
`tests/test_bigbang.py`.
Tests (both modes × 100 seeds): exactly one cluster per bloc; cluster smaller
than the Core; never Core-adjacent; never rival-linked; **≥1 all-neutral path
from the Core to every outer band**.

---

## M11 — Encounters & combat

### WP24 — Encounter core: interrupt, detection, disposition, pack spawn (L)

The Phase-1 seam goes live. `rules._should_interrupt` becomes the encounter
roll: species in/near the sector + the WP22 `EncountersConfig` weights, drawn
from `state.rng` in the reducer (H4). On trigger, in order:

1. **Detection** — species sensors vs the player's cloak rating plus nebula
   cover (reusing the effective-sensor machinery); an undetected player slips
   away freely.
2. **Greeting vs violence** — rolled against effective disposition, shifted
   by active grudges and alliance standing (WP27/WP38 hooks; until they land
   the shift terms are zero). A `combatant: false` species can never reach
   violence.
3. **Pack spawn** — the encounter group per the species' `pack_behavior` /
   escort composition.

New frozen `Encounter` model on `Player.active_encounter` (hashed): the pack's
species instance ids, round counter, detection/opening outcome. Movement and
dock commands are rejected while an encounter is live; `TravelTo` halts at the
interrupted hop inside the one command (the hop loop is already structured for
it). The greeting path routes into the existing contact screen; the violent
path opens the `EncounterScreen` (the stub goes real) fed by a new
`session.encounter_view`. All new commands/events enter `store/codec.py` with
round-trip coverage.

Files: new `edge/core/encounters.py`, `edge/core/rules.py`,
`edge/core/models.py`, `edge/core/events.py`, `edge/store/codec.py`,
`edge/server/session.py` + `service.py`, `edge/tui/screens/encounter.py`,
`config/default.yaml`, new `tests/test_encounters.py`, `tests/test_codec.py`.
Tests: golden replay including an interrupted `TravelTo`; disposition-roll
monotonicity property; detection respects cloak+nebula; non-combatant never
violent (hypothesis).

### WP25 — Combat rounds: weapons schema, arcs, fight/flee, the floor (L)

Per-round resolution in a new pure `edge/core/combat.py`.

- **Adds the missing §4 weapon schema** (framing correction 1):
  `WeaponConfig {name, damage, firing_arc: ahead|all_round|spinal, special?}`
  and a `defenses` list on `ShipClassConfig`; the roster's `fleet` ids
  resolve to armed hulls in `config/default.yaml`.
- **Player offense:** the spinal Main Gun (damage/rate from `derive_aspects`)
  plus finite `Ship.missiles` — arc-ignoring, bought at StarDock hardware.
- **Arc rule:** `ahead`/`spinal` attackers are evaded by a combat-speed
  contest (maneuvering out of the firing line); `all_round` leaves no safe
  angle; weapon `special`s hook their own modifiers.
- **Flee:** base chance + combat speed − interception − accumulated damage +
  cloak, **clamped ≥ `escape_floor` (default 0.10)** — a named core invariant
  with its own hypothesis property (§13).
- **Spindrive efficiency** applies its one global bonus (screens, combat
  speed, gun damage) across the fight.
- **Commands:** `CombatAction(fight | flee | launch_missile | field_patch)`
  with the view/reducer lockstep (H4).

Files: new `edge/core/combat.py`, `edge/core/config.py`,
`config/default.yaml`, `edge/core/rules.py`, `edge/store/codec.py`,
`edge/server/session.py`, `edge/tui/screens/encounter.py`, new
`tests/test_combat.py`.
Tests: **escape probability never below the floor under arbitrary
damage/engine/interception values** (hypothesis); arc counters; missile
conservation; golden replay of a full fight.

### WP26 — Localized damage, repair kits, escape pods, salvage (M)

Damage that defeats the screens reduces hull and rolls a **component
knockout** weighted toward exposed/forward subsystems (config weight table);
the owning subsystem's aspect degrades immediately via the Phase-2
derive-on-write rail (`apply_derived` re-run). `FieldPatch` goes live (one
repair-kit, minimal function, between rounds or sectors); `RepairAtDock` goes
live (≈25% of tier price, §8). Hull 0 ⇒ **escape pod** (a config hull; ship
and cargo lost, the pod limps home). Destroyed NPCs yield 10–20% cargo
salvage plus occasional loose components (feeding the component economy).

Files: `edge/core/combat.py`, `edge/core/engine_room.py`,
`edge/core/rules.py`, `config/default.yaml`,
`edge/tui/screens/engine_room.py` (knocked-out states now real),
`tests/test_combat.py`, `tests/test_engine_room.py`.
Tests: knockout degrades exactly the owning subsystem's aspect; field-patch
consumes one kit and restores minimal function; salvage conservation; pod
flow golden replay.

### WP27 — Consequences: attitude, grudges, alignment/experience (M)

- Attacking drives `species_attitudes` down by `attitude_loss_rate`;
  `memory_model` (none / normal / never_forgets) and `betrayal_model`
  (permanent floors the offset for good) go live in `core/aliens.py`.
- **`Grudge` entity** (holder, target, cause, severity, created_at,
  duration): seeded from the roster at big bang + created at runtime by
  player conduct; decays on the daily cron; shifts the WP24 disposition roll.
- `Player.alignment` + `Player.experience` counters (combat outcomes, kills
  of friendlies vs hostiles, discoveries).
- **Core-law basics:** criminal alignment and governor standing gate Core
  entry treatment (full enforcement in WP38).
- **M11 golden batch:** the milestone's Player/Ship field additions land
  together with one golden regeneration (H6).

Files: `edge/core/aliens.py`, `edge/core/models.py`,
`edge/bigbang/aliens.py`, `edge/engine/cron.py`, `edge/core/rules.py`,
`config/alien_roster_default.yaml` (grudge/relations schema only — semantics
in WP39), `tests/test_aliens.py`.
Tests: permanent-betrayal floor property; grudge decay determinism through
the maintenance timeline; alignment arithmetic.

---

## M12 — Conversation depth

### WP28 — The per-contact dialogue session (M)

`Player.contact_session: ContactSession | None` — a frozen record of
`(species_instance_id, sector_id, facts)` where `facts` accumulates topics
asked, offers seen, and reactions within the visit. Opened at hail; cleared
by farewell **and by every movement/encounter reducer** (H1). The facts merge
into the fact dictionary fed to `DialogueWhen.criteria` — the matcher
(`select._score`) already handles arbitrary criteria keys, so this extends
**fact assembly only**, in a new shared `edge/dialogue/facts.py` used
identically by the `Converse` reducer and the `session` projection so the
view/reducer lockstep holds (H4/H8). H9 sync applies (yaml spec header,
authoring prompt, DESIGN §6.7/§13 in the same change).

Files: `edge/core/models.py`, `edge/core/rules.py`, new
`edge/dialogue/facts.py`, `edge/server/session.py`,
`config/alien_dialogue_default.yaml` (header),
`edge/dialogue/authoring/pipeline.py`, `tests/test_dialogue.py`,
`tests/test_contact.py`.
Tests: golden replay of a branching conversation; session cleared on warp;
view and reducer agree on choices under session facts.

### WP29 — Situational facts + per-instance recency (S/M)

`facts.py` gains the situational vocabulary: distance band, sector features
(nebula/wreck present), hull/fuel state buckets, `just_fled_combat` (from
`Player.last_combat`, H5), cargo summary. `Player.dialogue_recency` and the
`encounter_rng` seed re-key `(roster_id, context)` →
`(species_instance_id, context)` (H7) so two ships of one species stop
finishing each other's sentences. The playtest harness's synthetic-species
keying updates to match.

Files: `edge/dialogue/facts.py`, `edge/dialogue/select.py`,
`edge/core/models.py`, `edge/core/rules.py`, `edge/server/session.py`,
`edge/dialogue/authoring/playtest.py`, spec sync (H9),
`tests/test_dialogue.py`.
Tests: the no-repeat ring property holds per instance; situational criteria
select the pinned line.

### WP30 — Cross-visit arcs + callbacks (S/M)

`Player.species_arcs: Mapping[roster_id, Mapping[str, int|str|bool]]` — small
persisted flags set by authored choice actions and mechanic stages, unlocking
branches across visits. Callback facts derived from `species_last_seen`,
`leads`, and `last_combat` ("back again so soon?", "did you follow the
coordinates?", "you fled our patrol"). **M12 golden batch** (H6/H7 land
here together).

Files: `edge/core/models.py`, `edge/core/rules.py`,
`edge/dialogue/facts.py`, spec sync (H9), `tests/test_dialogue.py`, goldens.
Tests: an arc flag set in visit 1 unlocks a branch in visit 2 across a
save/reload golden.

### WP31 — Combat dialogue live (M)

The `peaceful=False` intents (`combat_open`, `combat_taunt`, `surrender`,
`flee_scorn`, `betrayal`) become reachable from the encounter reducers, keyed
to encounter facts (round, damage dealt/taken, pack size, fleeing);
`EncounterScreen` renders the lines; recency rings advance through combat
commands exactly as `Converse` does. The `_converse` guard still blocks
*conversational* access to combat contexts.

Files: `edge/core/rules.py`, `edge/core/combat.py`,
`edge/dialogue/intents.py`, `edge/server/session.py`,
`edge/tui/screens/encounter.py`, spec sync (H9), `tests/test_dialogue.py`,
`tests/test_combat.py`.
Tests: taunt keyed to round facts; surrender/flee-scorn fire on the right
outcomes; replay-stable.

### WP32 — Corpus expansion (M, mostly authoring)

With the vocabulary frozen (WP28–WP31), author the enlarged corpus via
`edge-author-dialogue`: session/situational/arc criteria examples, combat
beats for every persona and hostile species, and the Entity's
(`biblical_arbiter`) roaming-lore refresh. Validated by `validate_dialogue`
and walked in the playtest harness (`edge-playtest-dialogue`, force-enable
for combat branches).

Files: `config/alien_dialogue_default.yaml`, `config/dialogue/*.yaml`
sidecars, `config/alien_roster_default.yaml` (pack overrides),
`tests/test_dialogue.py`.
Tests: the §13 dialogue-integrity suite green across the grown corpus; every
species resolves the combat contexts its parameters can reach.

---

## M13 — Signature mechanics & the Entity

### WP33 — Signature-mechanic framework + first hooks (M/L)

A hook registry in new `edge/core/mechanics.py` keyed by
`KNOWN_SIGNATURE_HOOKS`; each hook is a pure
`(state, player, species, stage, params) → effects/stage'` with its stage
persisted in `Player.species_arcs` (WP30). First hooks: `morality_judge`
(audited metrics from alignment/experience/grudge history → verdict dialogue
+ blessing/curse effects), `literalist` (keyword map keyed off the choice
taken, `memory_model=none`), `flee_drop` (pack flees on contact, drops cargo
packets), `influence_gate` (cannot-attack-unbidden gates the FIGHT choice).
`sig.*` contexts become reachable.

Files: new `edge/core/mechanics.py`, `edge/core/rules.py`,
`edge/dialogue/facts.py` (stage facts), `config/alien_roster_default.yaml`,
new `tests/test_mechanics.py`.
Tests: stage ladders replay; the judge's verdict is deterministic from the
conduct counters.

### WP34 — The Entity: generation, roster flag, salvage-table removal (M)

- `SpeciesConfig.singular_entity: bool` — an explicit flag (not
  archetype-string matching, keeping rosters free to vary); the default
  roster sets it on `concordance`, whose lore updates fixed-lair → roaming
  (`home_band: Void` kept as the spawn hint).
- **Remove `entity` from `space_kinds` / `hidden_kinds`** in
  `config/default.yaml`; `DiscoveryKind.ENTITY` survives as an enum (codex
  art keys) but is never salted.
- `populate_species` special-cases the flag: always drawn, exactly one
  instance, spawned in a deep-band sector, **excluded** from the per-band
  guarantee accounting, `ships_per_home` clustering, and the StarDock/Core
  paths. `combatant: false` + `fleet: []` are honored (WP24 already
  guarantees no violence path).
- Validator: exactly one Entity instance; never in the Core.
- **M13 golden batch** (discovery-salting draw order shifts).

Files: `edge/core/config.py`, `config/default.yaml`,
`config/alien_roster_default.yaml`, `edge/bigbang/aliens.py`,
`edge/bigbang/discoveries.py`, `edge/bigbang/validate.py`,
`tests/test_aliens.py`, `tests/test_discovery.py`.
Tests: 100-seed uniqueness/placement (both modes); salting no longer
produces entity discoveries.

### WP35 — Entity presence: hint, gated contact, art, codex (M)

- The sector projection **always** shows an anomalous-presence line when the
  Entity's current sector matches — computed live, never via
  `Player.detected` (H2).
- Opening contact (`Hail`) is gated by sensor rating through the
  `sensor_difficulty` machinery at Legendary difficulty — enforced in the
  reducer as well as the projection (H2).
- **Artwork:** on the contact screen the Entity's art fills the
  portrait/ship-art slot (the `SpeciesPortrait` box) before dialogue starts;
  the sector-view token already styles via `art/hull.py` `cosmic_arbiter`;
  add a full-slot nebular-bloom fallback in `edge/art` for terminals without
  image portraits.
- **Codex:** first contact stamps a **Legendary codex entry** — a reserved
  hidden `Discovery` row created at generation and *collected by the first
  `Hail`*, so the codex path is unchanged.

Files: `edge/server/session.py`, `edge/core/rules.py`, `edge/art/hull.py`,
`edge/art/portrait.py`, `edge/tui/screens/contact.py`,
`tests/test_contact.py`, `tests/test_session.py`.
Tests: hint fog-safety (presence shown, contents not); the reducer rejects
an under-sensored Hail; the codex stamp is once-only and replay-idempotent.

### WP36 — Entity drift + stale leads: the pursuit loop (M)

- The Entity rides the existing `alien_drift` cron (it is an `AlienSpecies`
  row, H8) with a per-species drift-chance override so it wanders at its own
  pace; `may_occupy` special-case: anywhere non-Core.
- `pick_intel_target` computes the Entity tip **live** — a friendly speaker
  who has not yet led the player to the Entity offers its *current* sector at
  accept time (`species_knowledge` stays a generation-time cache; H3).
- The accepted `Lead` freezes that sector. **Staleness is derived at
  projection**: the leads view flags "trail gone cold" when the Entity has
  moved; re-asking yields a fresh lead (the duplicate-exclusion check keys on
  ref+sector, so a moved Entity re-offers).

Files: `edge/dialogue/intel.py`, `edge/engine/cron.py`,
`edge/core/aliens.py`, `edge/server/session.py`, `config/default.yaml`,
`tests/test_dialogue_intel.py`, `tests/test_engine.py`.
Tests: drift determinism under replay (the drift_seq rail); the stale-lead
flag; re-ask issues an updated lead.

### WP37 — Transactional signature hooks (M/L)

The remaining hooks on the WP33 registry: `trojan_gift` (delayed payload
device; a removal market), `reprogram_unlock` (an item flips another species'
`trade_posture`), `escalating_demand` (ladder + permanent failure via WP27
betrayal), `contract_kill` (raze-named-starbases contracts — authored and
gated here; the razing mechanics land in WP40), and the hostile sides of
`coordinate_broker` / `passage_broker` (extort / mislead).

Files: `edge/core/mechanics.py`, `edge/core/rules.py`,
`config/alien_roster_default.yaml`, `tests/test_mechanics.py`.
Tests: each hook's stage machine golden-replayed.

---

## M14 — Territory & alliances

### WP38 — Alliances joinable: admission, fallout, Core law (L)

`JoinAlliance` / `ResignAlliance` commands gated by the bloc's
`admission_price` tasks (a befriend-price ledger in `species_arcs`) and
`membership_gate`. Joining warms members, sours rival blocs, and imposes the
no-attack obligation (attacking a member voids membership). Rival home
clusters (WP23 territory) turn hostile: `may_occupy` widens to
at-war/grudge-driven exclusions and cluster encounter rolls key on alliance
standing. **Core law:** entry treatment keyed to standing with
`Game.core_governing_alliance_id` (static Federation governor this phase) —
a rival-aligned player is engaged on sight in the Core; sanctuary follows the
governor, not the Federation name, and recovers on resignation + amends.
`Player.alliance_standing` map added (**M14 golden batch** opens).

Files: `edge/core/rules.py`, `edge/core/aliens.py`, `edge/core/models.py`,
`edge/core/encounters.py`, `edge/store/codec.py`, `edge/server/session.py`,
TUI (alliance panel on Computer/contact), new `tests/test_alliances.py`.
Tests: join→rival-cluster-hostile golden; membership exclusivity; the Core
turns hostile on rival alignment and recovers on resignation.

### WP39 — Inter-species relations, spillover, NPC-vs-NPC (M)

The roster `relations` block: sparse asymmetric overrides atop
alliance-derived defaults, computed at big bang. Reputation spillover
(helping/harming X nudges attitude with X's friends and enemies in
proportion). NPC-vs-NPC stance feeds WP42's movement policies and same-sector
NPC behavior. Validator: relations consistent with alliance structure unless
explicitly overridden (§13).

Files: `edge/core/config.py`, `config/alien_roster_default.yaml`,
`edge/core/aliens.py`, `edge/bigbang/aliens.py`, `edge/bigbang/validate.py`,
`tests/test_aliens.py`.
Tests: derived-default matrix; spillover arithmetic; validator consistency.

### WP40 — Starbases: set-pieces, planetary defense, repair/claim (L)

Assaulting a `role=starbase` hull is a set-piece combat reusing the
WP25/WP26 rounds against fixed defenses; defense strength scales with
surviving components and `fusion_reactor` efficiency (the Phase-2
`is_operational` seam). An **operational orbital base joins encounters** in
its sector on its owner's side, hostility resolved through
ownership/alliance rules — this is how Core-governor bases enforce WP38's
law. Razing flips the world toward unowned/claimable, drives the target
species + alliance + friends hostile (WP39 spillover), and pays
`contract_kill` / admission credit. **Repair/claim:** refill a derelict's
slots (components + latinum), then claim it into an operational player
foothold. Species `starbase_policy` placement (homeworld / territorial /
secret) joins the big bang.

Files: `edge/core/starbases.py`, `edge/core/combat.py`,
`edge/core/rules.py`, `edge/bigbang/populate.py`, `edge/server/session.py`,
`edge/tui/screens/planet.py`, new `tests/test_starbases.py`.
Tests: derelict→repair→claim→defends golden; razing consequences; defense
scaling with components.

### WP41 — Sector fighters, mines, beacons, hazards (M/L)

The classic territory stack: deployable **sector fighters** (offensive /
defensive / toll; entering a hostile-fighter sector forces engage-or-retreat,
and retreat costs one fighter — the original rule); **mines** (damage on
entry, deflector mitigation; the Armid/limpet split stays Phase 5);
**beacons** per §10 (a finite `Ship.devices` item bought at StarDock,
deployable to a controlled sector, one per sector, overwrite semantics, never
in the Core); the **black-hole hazard** flag flips on (damage-on-approach /
gravity-warp per config). Sector deployables live in a new hashed entity map
(**M14 golden batch** closes).

Files: `edge/core/models.py`, `edge/core/rules.py`,
`edge/core/movement.py`, `edge/store/codec.py`, `edge/server/session.py`,
`config/default.yaml`, new `tests/test_territory.py`.
Tests: toll/def engagement matrix; retreat-costs-one-fighter; beacon
overwrite; mine mitigation; hazard damage replay.

---

## M15 — A living, hunted frontier

### WP42 — Goal-directed NPC movement (M)

Replace pure random drift with per-species movement **policies** — patrol the
home cluster, seek trade lanes, hunt the player's last-known sector for
grudge-holders, flee stronger contacts — as pure planners in a new
`edge/core/npc.py`, scheduled on the existing `alien_drift` cron rail (same
salted sub-RNG + sequence counter, H8); `may_occupy` remains the legality
gate; the Entity keeps its own wander policy.

Files: new `edge/core/npc.py`, `edge/engine/cron.py`,
`config/alien_roster_default.yaml` (policy per species),
`tests/test_engine.py`.
Tests: policy determinism through the maintenance timeline; hunters converge
and cowards diverge on fixture graphs.

### WP43 — NPC traders moving real goods (M)

Friendly merchant species execute real trades on the cron clock: compare
known port prices, move stock and latinum through the same `core/economy.py`
invariants (goods conserved, prices feed back), and hold persistent
cargo/cash per species. Trading alongside them builds attitude.

Files: `edge/core/npc.py`, `edge/engine/cron.py` (a `trader_step` cron),
`edge/core/models.py` (species cargo/cash), `tests/test_engine.py`,
`tests/test_economy.py`.
Tests: conservation under NPC trades (hypothesis); reload-identical
`state_hash` after ticked trading (the Phase-2 WP12 rail).

### WP44 — Homeworld raids, bounties, exit-criterion balance (M)

Hostile species defend their home regions and raid trade lanes near the band
boundary (WP42 policies + WP24 weights). Raiding their homeworlds yields
legendary-tier technology caches (a discovery-salting tie-in), with
**bounties per hostile fighter destroyed** (config; echoing the Cabal's
100/kill) and alignment/experience payoffs. Ends with a balance pass over
encounter frequency, threat, and economy sinks against the §14 exit
criterion.

Files: `config/default.yaml`, `config/alien_roster_default.yaml`,
`edge/core/encounters.py`, `edge/bigbang/discoveries.py`,
`tests/test_encounters.py`; manual playtest per the Phase-2 verification
style.
Tests: bounty accounting; raid-cache placement invariants; the full-phase
golden suite green.

---

## Suggested order / commits (phase-tagged, small)

`p3: WP19` docs → `p3: WP20` expansive topology (trunk default, zero churn) →
`p3: WP21` band retune + embedding → `p3: WP22` hostiles + **config_version 3
+ topology default flip + one golden regen** → `p3: WP23` home clusters →
**M10** → WP24 → WP25 → WP26 → WP27 (+M11 golden batch) → **M11** → WP28 →
WP29 → WP30 (+M12 golden batch) → WP31 → WP32 → **M12** → WP33 → WP34 (+M13
golden batch) → WP35 → WP36 → WP37 → **M13** → WP38 → WP39 → WP40 → WP41
(+M14 golden batch) → **M14** → WP42 → WP43 → WP44 → **M15** (exit
criterion).

**Hard dependencies:** WP21→WP22 (bands before the gradient); WP22/WP23→WP24
(hostiles + territory before rolls); WP24→WP25→WP26 (encounter → rounds →
damage); WP28→WP31 (session facts before combat dialogue); WP28–WP31→WP32
(vocabulary frozen before the corpus); WP33→WP35/WP36 (the judge hook before
Entity contact pays off); WP23→WP38 (clusters before cluster hostility);
WP25/WP26→WP40 (combat before set-pieces); WP42→WP43/WP44 (movement AI before
traders and raids). The Entity block (WP34–WP36) is otherwise parallel to M14
and can be swapped later if schedule demands — it only consumes drift, intel,
sensors, and dialogue.

---

## Verification

- **Per WP:** the named test files above; property tests for the invariants
  (escape floor, disposition gradients, conservation under NPC trades,
  no-repeat recency per instance); golden-master replays regenerated **only**
  at the batched epochs (WP22, M11, M12, M13, M14), noted in each commit.
- **Topology:** the bigbang validation matrix runs **both modes × 100 seeds
  permanently**; `edge bigbang --render --mode expansive` vs `trunk` (the
  spring-layout PNG shows the cross-bridges the nav fan hides) confirms the
  lattice visually.
- **Dialogue:** the `validate_dialogue` integrity suite plus
  `edge-playtest-dialogue` (force-enable) to walk combat, branch, and Entity
  nodes.
- **Playable checkpoints:** after M11 a fight can be won, lost, or fled;
  after M13 the Entity can be hunted, found, and judged; M15 ends on the §14
  exit-criterion playtest.
