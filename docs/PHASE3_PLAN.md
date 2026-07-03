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
2. **Alliance home clusters were spec-only** (before WP23): `edge/bigbang/aliens.py`
   only placed species *ship* clusters and stamped `Region.controlling_alliance_id`
   post-hoc from wherever ships landed; there was no territory carve, no
   alliance-owned cluster worlds tied to blocs, and no neutral-lane validator.
   **WP23 implemented DESIGN §5 step 6 for real** (see below).

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

- **Bands (shipped):** `BigBangConfig.bands` is a `BandSet` nesting `bands.trunk`
  and `bands.expansive` (Hub 0–14 / Frontier 15–35 / Deep 36–58 / Void 59+),
  resolved by `active_bands()` at generation per `topology_mode`. **Same band names
  in the same order — only the hop windows differ** — enforced by a `BandSet`
  validator (`_check_names_match`), so every name-keyed path (placement,
  validation, UI) is mode-agnostic. All threshold consumers (generator, validate,
  populate, aliens) route through `active_bands()`. At 1000 sectors this keeps all
  four bands populated (25/25 seeds sampled) with an outward-growing gradient
  (Hub ≈ 130, outer bands ≈ 285–300).
- **Hop-window checks re-verified under expansive:** `_check_profitable_pair`
  (opposed pair ≤ 5 hops of the Core), StarDock placement within
  `stardock_min/max_hops`, `_check_discovery_gradient` strict monotonicity, ≥1
  contact per band, unowned-planet monotone fraction — all pass at 1000 sectors
  (10/10 seeds generate cleanly). *(Note: `bands.expansive` is tuned to the
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

Implements DESIGN §5 step 6 (framing correction 2). **Shipped.**

- **Carving (`edge/bigbang/aliens.py::_carve_home_clusters`).** Each non-governing
  bloc **present in the cast** gets one home cluster — `home_cluster_[min,max]`
  (3–6) connected sectors BFS-grown in the two innermost bands (Hub + inner
  Frontier), never Core-adjacent, never warp-linked to a rival (a one-hop buffer
  keeps clusters apart). Its non-derelict planets are set alliance-owned, its
  region(s) stamped `controlling_alliance_id`, and its friendly members settled
  there. Everything else is neutral lanes. The cluster sector-sets are recorded on
  `UniverseState.home_clusters` (a generation cache like `core_hops`, excluded from
  `state_hash` — the *effects* on planets/regions/species are the hashed state).
  A `HomeClusterError` (unsatisfiable seating) joins the generation retry loop.
- **Bloc members are friendly (§5).** A key interaction with WP22: a bloc's menace
  is **political** (rival-alliance standing, activated in WP38), *not* low
  disposition, so its members are drawn friendly-band and its home cluster stays
  peaceable. Baseline hostiles therefore come from the **unaligned raiders**
  (present in most, not all, universes); whole-bloc hostility is a Phase-3 politics
  layer, not a generation property.
- **Derelict conflict resolved.** Owning a cluster planet that hosts a *derelict*
  base would violate the §4.2 derelict⇒unowned rule — so such a world is left
  unowned (a salvage cache inside bloc space). This also cleared a retry-budget
  exhaustion at 1000 sectors (0/80 failures after the fix).

Files: `edge/bigbang/aliens.py` (carve), `edge/bigbang/generator.py` (retry),
`edge/bigbang/validate.py` (`_check_home_clusters`), `edge/core/config.py`
(`home_cluster_min/max`), `edge/core/models.py` (`home_clusters` cache),
`config/default.yaml`, `tests/test_bigbang.py`, `tests/test_aliens.py`.
Tests (both modes × 40 seeds): exactly one cluster per cast bloc; cluster smaller
than the Core; never Core-adjacent; never rival-linked; **≥1 all-neutral path from
the Core to every band**; cluster planets alliance-owned (derelicts left unowned).
Full suite 1451 green.

---

## M11 — Encounters & combat

### WP24 — Encounter core: interrupt, detection, disposition, pack spawn (L)

The Phase-1 seam goes live. **Shipped.** The `_should_interrupt` stub is
replaced by the pure `edge/core/encounters.py` roll chain, drawn from
`state.rng` inside the movement reducers (H4). Per sector entered:

1. **Interrupt** — the band's `interrupt_chance` (0 in the Hub) fires and a
   species present in the sector is drawn with weight inverse to threat.
   RNG discipline: no draw at all when an encounter is impossible (zero band
   chance or no candidates — both pure functions of state), so the
   command-stream draw order stays deterministic.
2. **Detection** — the species' sensors (its lead fleet hull's rating) vs the
   player's cloak, dimmed by nebula cover (`detection_*` knobs on
   `EncountersConfig`); an undetected player slips away freely
   (`EncounterEvaded`, no halt).
3. **Greeting vs violence** — vs effective disposition: friendly-band always
   greets, hostile-band always attacks, the wary middle interpolates linearly
   (a coin-flip at the midpoint). Grudge/alliance shift terms land with
   WP27/WP38. `combatant: false` — or an empty `fleet` — can never reach
   violence.
4. **Pack spawn** — per `pack_behavior`/`escort` (solo / escorted / swarm of
   `swarm_size_[min,max]`); each `EncounterFoe` is a frozen stat snapshot
   (hull class × species threat) so combat rounds stay pure.

Frozen `Encounter` on `Player.active_encounter` (hashed): the pack, round
counter, fight-local `player_shields` (shields recover after combat; hull
damage persists on the `Ship`). `Warp`/`TravelTo`/`Dock`/`Descend` are
rejected while engaged; `TravelTo` **halts at the interrupted hop** (the
sector is entered first, then the roll fires). A greeting halts too and routes
into the existing contact screen; a violence opener pushes the (now real)
`EncounterScreen` fed by `session.encounter_view`, and a save quit mid-fight
reopens it on resume.

Files: new `edge/core/encounters.py`, `edge/core/rules.py`,
`edge/core/models.py`, `edge/core/events.py` (`EncounterStarted` /
`EncounterEvaded`), `edge/store/codec.py`, `edge/server/session.py` +
`service.py`, `edge/tui/screens/{encounter,game}.py`, `edge/core/config.py` +
`config/default.yaml` (detection knobs), `tests/test_encounters.py`,
`tests/test_codec.py`.
Tests: mid-fight and interrupted-journey golden reloads; travel halts at the
interrupted hop; movement/dock blocked while engaged; no RNG draw in the Hub;
non-combatant never violent; evaded encounters don't halt; pack shapes;
violence-roll shape (hypothesis).

### WP25 — Combat rounds: weapons schema, arcs, fight/flee, the floor (L)

Per-round resolution in a new pure `edge/core/combat.py`. **Shipped.**

- **The §4 weapon schema added** (framing correction 1): a top-level
  `GameConfig.weapons` catalog of `WeaponConfig {name, damage, firing_arc,
  rate, special?}` records; `ShipClassConfig` gains `armament` (weapon ids),
  `defenses` (`DefenseConfig {type, value}` — armour/screens/energy_plates sum
  to a flat damage reduction), and `missiles` (starting ammo). All four hulls
  armed in `config/default.yaml`; a `GameConfig` validator enforces every
  armament id and every roster `fleet`/`escort` hull resolves.
- **One `CombatAction` = one round:** the player acts (fight / flee /
  launch_missile / field_patch), then every surviving foe returns fire.
  Field-patching routes through the ordinary `_field_patch` validation (kit
  rules stay in one place) and the pack still gets its volley.
- **Player offense:** Main Gun `(gun_damage + efficiency_bonus) × gun_rate`
  from `derive_aspects`; finite arc-ignoring missiles (`missile_damage`),
  bought via `BuyMissiles` at the StarDock (**i** key); hulls carry loadouts
  and ammo carries over on `BuyShip`.
- **Arc rule:** `ahead`/`spinal` foe fire is evaded on a combat-speed contest
  (`evade_base + evade_speed_coeff·Δspeed`); `all_round` cannot be evaded;
  **spinal weapons fire only every other round** (recharging). `special`s are
  carried as data for the WP33+ hooks.
- **Flee:** `flee_base + speed·coeff − interception·coeff + cloak·coeff −
  damage_penalty·missing-hull`, **clamped to [`escape_floor`, `flee_cap`]** —
  the named pure `combat.flee_chance` is the §13 property-test target, and the
  `encounter_view` shows the *same* number the reducer rolls (H4 lockstep).
- **Spindrive efficiency** adds once each to gun damage, combat speed (both
  contests), and screen deflection.
- **The WP26 seam, explicit:** hull driven to 0 clamps at 1 and
  force-disengages (`crippled`) until escape pods land — death is never
  unhandled. (WP26 replaced this with the `destroyed` outcome + escape pod.)

Files: new `edge/core/combat.py`, `edge/core/config.py`,
`config/default.yaml`, `edge/core/rules.py`, `edge/store/codec.py`,
`edge/server/session.py`, `edge/core/dto.py`,
`edge/tui/screens/{encounter,stardock}.py`, `tests/test_combat.py`.
Tests: **escape probability never below the floor under arbitrary
damage/engine/interception values** (hypothesis, 300 examples); shields absorb
before hull on both sides; missiles finite + conserved; spinal fires every
other round; victory/crippled outcomes; the crippled clamp; flee succeeds from
a wreck within bounded attempts (the floor in action); StarDock missile
purchase; full-fight golden reload.

### WP26 — Localized damage, repair kits, escape pods, salvage (M)

Combat damage localizes into the engine room; destruction and salvage land.
**Shipped.**

- **Component knockout:** a volley that reaches the hull rolls
  `knockout_chance` and, on a hit, marks one active slot `knocked_out` —
  the subsystem pick weighted by the `knockout_weights` table (forward-heavy:
  main_gun/thrusters 3, screens 2, spindrive 1), the slot uniform within it.
  The reducer re-runs `apply_derived` immediately, so the owning aspect
  degrades for the rest of the fight (the Phase-2 derive-on-write rail; the
  `ComponentKnockedOut` event feeds the ticker and the encounter screen's
  integrity flag). No knockout while shields hold — only hull-reaching damage
  localizes.
- **FieldPatch / RepairAtDock exercised for real:** the Phase-2 reducers were
  already live (kit spend + `knocked_out=False` + re-derive; dock repair at
  ≈25% of tier price, §8) — combat now produces the knocked slots they exist
  for, and the encounter screen's **K** action patches mid-fight.
- **Escape pod replaces the crippled seam:** hull 0 ⇒ outcome `destroyed`;
  the reducer swaps the hull for the `combat.escape_pod_class` — a real
  price-0 ship class (single-slot subsystems, 1-warp drive, vestigial gun)
  the shipyard listing never sells. Cargo, loose components, devices,
  missiles, kits, and colonists go down with the ship; latinum and the bank
  live on the player; the pod keeps the sector — it limps home. Emits
  `ShipDestroyed` + `EncounterEnded(destroyed)`.
- **Salvage:** victory rolls per-wreck `hull_max × salvage_hull_value ×
  U[salvage_frac_min, salvage_frac_max]` latinum (BNT's 10–20% rule mapped
  onto cargo-less NPC hulls) plus a `salvage_component_chance` shot at one
  loose Tier-I part per wreck (needs a free hold, else left adrift; RNG draws
  are hold-independent so replays stay exact). `SalvageCollected` event.

Files: `edge/core/combat.py`, `edge/core/config.py`, `config/default.yaml`
(knockout/pod/salvage knobs + the `escape_pod` hull), `edge/core/rules.py`
(`_escape_pod`, `_combat_salvage`, knockout re-derive), `edge/core/events.py`,
`edge/store/codec.py`, `edge/server/session.py` (event formatting, shipyard
skips price-0 hulls), `edge/tui/screens/encounter.py`, `tests/test_combat.py`,
`tests/test_codec.py`, `tests/test_config.py`.
Tests: knockout degrades exactly the owning subsystem's aspect (forced-weight
config); field-patch consumes one kit and restores the aspect mid-fight;
salvage conserved and inside the configured window, components need a free
hold; destruction issues the pod with everything lost; pod-flow golden reload
(fight lost to destruction replays to the identical hash).

### WP27 — Consequences: attitude, grudges, alignment/experience (M)

Conduct now has memory. **Shipped.**

- **Souring** (`core.aliens.sour_attitude`): each foe destroyed drops the
  species' attitude offset by its `attitude_loss_rate` and deepens the grudge
  it holds against the player by `grudge_severity_per_kill` (capped 1.0).
  `memory_model: none` forgets instantly (no souring, no grudge);
  `never_forgets` / `betrayal_model: permanent` record an undying grudge
  (`duration_days -1`) that also **locks the attitude offset** — `_raise_attitude`
  refuses amends while it stands (§6.5's permanent lockout). Emits
  `AttitudeChanged` + the new `GrudgeFormed`.
- **`Grudge`** (holder, target, cause, severity, created_day, duration_days):
  player-targeted vendettas ride `Player.grudges` (keyed by species kind);
  roster-authored inter-species grudges (`SpeciesConfig.grudges` +
  `relations` — schema + validation + `_seed_grudges` at the big bang) land in
  the new hashed `UniverseState.grudges` map for the cast pairs, semantics
  WP39. Finite grudges cool by the holder's `attitude_gain_rate` on the daily
  cron and lapse past their duration; permanent ones never move. An active
  grudge's severity is **subtracted from effective disposition** in the WP24
  greeting-vs-violence roll (`grudge_shift`).
- **`Player.alignment` / `Player.experience`:** per kill, alignment shifts by
  the victim's effective-disposition band (`alignment_kill_friendly/-3,
  _neutral/-1, _hostile/+1`) and experience pays
  `max(1, round(threat × experience_kill_scale))`; each new codex stamp
  (survey or salvage) pays `experience_per_discovery`.
- **Core-law basics:** below `criminal_alignment` the player is criminal
  (`is_criminal`); a non-Core → Core crossing then emits `CoreLawNotice` —
  one warning per crossing, from both `Warp` and the `TravelTo` hop loop
  (engagement-on-sight + governor-standing gating are WP38).
- **M11 golden batch:** the milestone's hashed additions land together —
  `Player.grudges/alignment/experience`, `UniverseState.grudges` (added to
  `state_hash`). Goldens are self-consistency round-trips, so the fingerprint
  change re-baselines automatically (H6; no `config_version` bump — nothing
  about the config contract changed).

Files: `edge/core/aliens.py`, `edge/core/models.py`, `edge/core/config.py` +
`config/default.yaml` (consequence knobs), `edge/bigbang/aliens.py`,
`edge/engine/cron.py`, `edge/core/rules.py`, `edge/core/encounters.py`,
`edge/core/events.py`, `edge/store/{codec,snapshots}.py`,
`edge/server/session.py`, `config/alien_roster_default.yaml` (relations +
grudges authored on vennrith/quill), `tests/test_aliens.py`,
`tests/test_codec.py`.
Tests: permanent-betrayal floor property (hypothesis: no number of amends
raises the offset after betraying a permanent species); grudge decay exact
values through the daily-cron timeline (permanent untouched); kill
consequences through the combat reducer (alignment band arithmetic, threat-
scaled xp, GrudgeFormed); discovery xp; Core-law notice for criminals only,
once per crossing; seeded grudges land exactly for cast pairs.

---

## M12 — Conversation depth

### WP28 — The per-contact dialogue session (M)

A conversation now remembers this visit. **Shipped.**

- **`Player.contact_session: ContactSession | None`** (hashed): a frozen
  record of `(species_id, sector_id, facts)` — the species **instance**
  spoken to, where, and what happened this visit. Session facts (the WP28
  vocabulary, documented in the corpus spec header): `asked.<context>: true`
  for every context spoken (so a line can react to a repeat question),
  `traded: true` on a tech buy/barter, `accepted_lead: true` on a logged tip.
- **Lifetime is structural (H1):** any conversation reducer opens/continues
  the session (`Hail` is `Converse(greeting)`; turning to another species
  starts a fresh visit); `farewell` closes it; **`Warp` and every `TravelTo`
  hop clear it unconditionally** — the UI is never trusted to close it.
- **Shared fact assembly** in the new `edge/dialogue/facts.py`
  (`contact_facts` = session facts + the caller's per-context extras;
  `ensure_session`/`note_topic`/`note` for the reducer side): the `Converse`
  reducer (`_speak_context`, `_converse_choice`), `_trade_alien`,
  `_accept_lead`, and the `contact_view` projection all merge facts there, so
  the lockstep holds — selection always reads the **pre-utterance** session
  facts the projection showed the line/menu under, then the utterance is
  recorded. `contact_facts` already takes `state` so the WP29 situational
  layer slots in without touching call sites. The matcher (`select._score`)
  needed no change — `asked.*` keys are ordinary criteria facts.
- **H9 sync:** the corpus spec header gains the FACTS section (per-context +
  session vocabulary); the authoring prompt's `_structure_brief` now tells
  the model each expansion may land mid-visit (self-contained lines). DESIGN
  §6.7/§13 already carried the WP19 spec text. No new events/commands — the
  session rides existing commands, so codec/store are untouched; goldens
  re-baseline via self-consistency (no `config_version` bump).

Files: `edge/core/models.py`, `edge/core/rules.py`, new
`edge/dialogue/facts.py`, `edge/server/session.py`,
`config/alien_dialogue_default.yaml` (header),
`edge/dialogue/authoring/pipeline.py`, `tests/test_dialogue.py`,
`tests/test_contact.py`.
Tests: session opens at hail and accumulates topics; farewell closes it;
warp clears it (H1); switching contacts starts fresh (no fact leak); an
`asked.greeting`-keyed species entry re-selects line **and menu** in
view/reducer lockstep; trade + lead mark the session; a visit left open
mid-conversation replays to the identical hash on reload.

### WP29 — Situational facts + per-instance recency (S/M)

Lines can name the actual situation, and each contact keeps its own phrasing
stream. **Shipped.**

- **Situational vocabulary** (`facts.situational_facts`, layered *under* the
  session facts in `contact_facts` — no call-site change): `band` (the
  sector's distance-band name), `in_nebula`, `wreck_here` (a visible
  uncollected wreck), `hull` (`critical` ≤25% / `scarred` ≤60% / `sound`),
  `low_turns`, `holds_empty`/`holds_full`, `carrying` (largest cargo stack,
  absent when unladen), and `just_fled_combat` (fled earlier *today*).
  Booleans are always present (real `true`/`false`) so authors can pin either
  polarity. Degrades to empty for hand-built states with no ship/sector, so
  pure selector rigs and the playtest harness work unchanged.
- **`Player.last_combat: LastCombat | None`** (hashed; species kind, outcome,
  day — exactly the DESIGN §4 record): stamped by `_combat_action` at every
  encounter end — the H5 source of `just_fled_combat` and the WP30 callbacks;
  never UI memory.
- **Per-instance recency re-key (H7):** `dialogue.instance_key(species)` =
  `roster_id#instance_id`; `Player.dialogue_recency` rings and the
  `encounter_rng` seed now key on it everywhere (`_speak_context`,
  `_converse_choice`, `_trade_alien`, the projection's `_line` /
  `_contact_choices`, and the playtest harness), so two ships of one species
  stop finishing each other's sentences. Key type stays `tuple[str, str]` —
  no persistence/schema change; goldens re-baseline via self-consistency.
- **H9 sync:** the corpus spec header gains the SITUATIONAL facts vocabulary
  and the per-instance ring note; the authoring prompt warns lines not to
  hard-code a situation they don't pin. DESIGN §4/§6.7 already carried the
  WP19 spec text (per-instance `dialogue_recency`, `last_combat`).

Files: `edge/dialogue/facts.py`, `edge/dialogue/select.py` (+`__init__`),
`edge/core/models.py`, `edge/core/rules.py`, `edge/server/session.py`,
`edge/dialogue/authoring/playtest.py`, `config/alien_dialogue_default.yaml`
(header), `edge/dialogue/authoring/pipeline.py`, `tests/test_dialogue.py`,
`tests/test_contact.py`, `tests/test_combat.py`, `tests/test_intel_contact.py`
+ `tests/test_dialogue_playtest.py` (re-keyed assertions).
Tests: the situational vocabulary end-to-end (incl. wreck flip, stale-flight
expiry, hand-built degrade); hailing ship A never advances ship B's ring;
a `band`-pinned species entry wins in the live sector and falls through
elsewhere; every encounter end stamps `last_combat`.

### WP30 — Cross-visit arcs + callbacks (S/M)

Conversations remember earlier visits. **Shipped.**

- **`Player.species_arcs`** (hashed; `roster_id → {flag: str|int|bool}`):
  persisted flags surfaced to selection as `arc.<flag>` facts. Set by the new
  authored **`DialogueChoice.arc`** map — `_converse_choice` merges a taken
  reply's flags onto the species kind *before* the follow-up line speaks, so
  the line can already react. (Signature-mechanic stages join in WP33.)
- **Callback facts** (`facts.callback_facts`, layered between situational and
  arc facts — always-present booleans): `met_before` (kind in
  `species_last_seen`), `lead_pending` / `lead_followed` (a tip from this
  kind, unvisited vs. visited), `fled_us` (most recent combat = fleeing this
  kind). "Back again so soon?", "did the coordinates pan out?", "you fled our
  patrol" are all authorable gates now.
- **M12 golden batch closes** (H6/H7): the milestone's hashed additions —
  `contact_session` (WP28), `last_combat` + the per-instance recency re-key
  (WP29), `species_arcs` (here) — are all in; goldens re-baselined via
  self-consistency throughout, no `config_version` bump (the `arc` choice
  field is additive with a default).
- **H9 sync:** corpus header gains the `arc:` choice field and the CALLBACK/
  ARC facts vocabulary. The machine-authoring output schema stays closed
  (arc-setting is a hand-authored feature). DESIGN §4/§6.7 already carried
  the WP19 spec text.

Files: `edge/core/models.py`, `edge/core/config.py` (`DialogueChoice.arc`),
`edge/core/rules.py`, `edge/dialogue/facts.py`,
`config/alien_dialogue_default.yaml` (header), `tests/test_dialogue.py`,
`tests/test_contact.py`.
Tests: callback-fact derivation (incl. lead pending→followed flip and
stranger isolation); an oath sworn via an `arc` reply rewrites the greeting,
survives movement (new visit), and unlocks the branch after a save/reload
golden.

### WP31 — Combat dialogue live (M)

The pack speaks. **Shipped.** — milestone **M12 mechanics complete** (WP32 is
authoring).

- **`Encounter.speech_context`** (hashed): the beat the pack last spoke, set
  by the reducers and rendered read-only by `encounter_view` into the new
  `EncounterDTO.speech`; the `EncounterScreen` shows it as a voiced quote
  under the banner, and the log records each beat via a fixed
  `format_event` body (`AlienSpoke` stays silent for conversation).
- **Beats:** the violent interception stamps the opener in
  `encounters.roll_encounter` — **`betrayal`** when the species' visible
  standing band is friendly (a grudge-shifted violence roll), else
  `combat_open`; each ongoing `CombatAction` round speaks `combat_taunt`, or
  **`surrender`** once the pack is bloodied (≥ half destroyed); a successful
  flee speaks `flee_scorn` before `EncounterEnded`. Victory/destruction stay
  wordless (outcome notes carry those).
- **`_combat_speak`** — the combat sibling of `_speak_context`: advances the
  per-instance recency ring through the movement/combat command (H4-clean,
  the derived `encounter_rng`), selects under the shared fact assembly
  (situational + callback + arc) plus the new **encounter facts**
  (`facts.encounter_facts`: `round`, `pack_size`, `foes_left`,
  `pack_bloodied`, `shields_down` — all derived from the hashed `Encounter`,
  so reducer and projection agree), but never opens a session or marks the
  species met — a firefight is not a visit. `_roll_encounter` now returns the
  player so the opener's ring advance rides `Warp`/`TravelTo`.
- **Guard unchanged:** `reachable_contexts` still excludes `peaceful=False`
  intents, so `Converse` cannot reach combat beats; the new
  `dialogue.combat_contexts(sc)` names what a `combatant`+fleet species can
  be driven to, and `validate_dialogue` now proves those resolve too.
- **H9 sync:** corpus header marks the combat contexts LIVE and adds the
  ENCOUNTER facts vocabulary; the authoring prompt gains per-beat briefs
  (combat_open/taunt/surrender/flee_scorn/betrayal) for WP32; DESIGN §6.7's
  encounter-fact list aligned to the implemented vocabulary.

Files: `edge/core/models.py`, `edge/core/encounters.py`,
`edge/core/rules.py`, `edge/dialogue/{facts,select,intents}.py`
(+`__init__`), `edge/core/dto.py`, `edge/server/session.py`,
`edge/tui/screens/encounter.py`, `edge/dialogue/authoring/pipeline.py`,
`config/alien_dialogue_default.yaml` (header), `docs/DESIGN.md` (§6.7),
`tests/test_dialogue.py`, `tests/test_combat.py`, `tests/test_encounters.py`.
Tests: encounter-fact derivation + combat-context gating; a round-1-keyed
taunt renders on the view and rotates next round; a bloodied pack sues for
quarter; flee scorn fires (ring advanced, ordered before `EncounterEnded`);
the violent opener speaks `combat_open`, and a grudge-pushed friendly opens
with `betrayal`; the fight/interrupted-travel goldens stay replay-stable.

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
`KNOWN_SIGNATURE_HOOKS`; each hook is a pure `(MechanicContext) →
MechanicResult` with its stage persisted in `Player.species_arcs` (WP30).
**Shipped.**

- **Registry (`edge/core/mechanics.py`).** `MECHANIC_HOOKS` maps hook id → a
  pure hook. `MechanicResult` carries the ladder `stage` (persisted under the
  reserved `STAGE_FLAG` key in `species_arcs`, surfaced as the `sig_stage`
  fact), transient selection `facts`, and **bounded effects** the reducer
  applies (attitude offset shift / alignment / experience / a latinum drop / a
  grudge). `run_hook` resolves an absent or not-yet-implemented (WP37) hook to
  `None` — the sig line then just speaks, inert. First hooks: `morality_judge`
  (audits `Player.alignment` → blessed/cursed/weighed verdict, deterministic
  from the conduct counter; blessing pays attitude + experience, a curse routes
  through the WP27 `sour_attitude` machinery), `flee_drop` (one-shot cargo drop
  on contact), `influence_gate` (`attack_forbidden` withholds the FIGHT reply),
  and `literalist` (`memory_model=none`, reaction keyed to the reply keyword).
- **Dispatch (`edge/core/rules.py`).** A `choices` reply into a `sig.*` context
  routes through `_resolve_mechanic`: run the hook, apply effects
  (`_apply_mechanic`, emitting the existing `AttitudeChanged`/`GrudgeFormed`
  events — no codec churn), persist the stage, then speak the sig line. The line
  gates on the **persisted** `sig_stage` (never a transient outcome), so the
  projection reconstructs the same line/menu the reducer speaks (the §6.7
  view/reducer lockstep). The influence-gate attack lock names its gate.
- **Projection (`edge/server/session.py`).** `contact_view` renders `sig.*`
  nodes read-only from `sig_stage` (like `branch.*`), so the Entity's verdict
  and its follow-up menu display on the contact screen.
- **Facts (`edge/dialogue/facts.py`).** `arc_facts` surfaces the mechanic stage
  as the bare `sig_stage` fact (plus `arc.sig_stage`).
- **Corpus + roster.** The Entity (`concordance`) authors
  `sig.morality_judge.verdict` (blessed/cursed/weighed variants gated on
  `sig_stage`, + a catch-all) reached by a new greeting reply; its roster
  `signature_mechanic.params` carry the verdict bands + boon magnitudes. H9 sync:
  spec header (`sig.*` LIVE + the `sig_stage` fact), authoring `_intent_brief`
  (a `sig.*` brief), DESIGN §6.2/§6.7.
- **Deferred within the framework (seams left clean):** `flee_drop`'s
  encounter-side flee/drop integration and `literalist`'s keyword-choice
  plumbing are registry-complete + unit-tested but not yet wired into an
  encounter/dialogue flow (no default species reaches them); the transactional
  hooks are WP37.

Files: new `edge/core/mechanics.py`, `edge/core/rules.py`,
`edge/server/session.py`, `edge/dialogue/facts.py`,
`config/alien_roster_default.yaml`, `config/dialogue/alien_dialogue_species.yaml`,
`config/alien_dialogue_default.yaml` (spec header),
`edge/dialogue/authoring/pipeline.py`, `docs/DESIGN.md`, new
`tests/test_mechanics.py`.
Tests: verdict determinism across the alignment bands (incl. boundaries); the
blessing/curse/weigh effects; flee_drop one-shot; influence-gate attack lock;
`run_hook` None for absent/WP37 hooks; the judgment reducer blesses/curses with
a grudge and **speaks the sig context**; the stage-ladder replays to the
identical `state_hash`; the sig corpus stays `validate_dialogue`-green.

### WP34 — The Entity: generation, roster flag, salvage-table removal (M)

**Shipped.**

- `SpeciesConfig.singular_entity: bool` — an explicit flag (not archetype-string
  matching, keeping rosters free to vary); the default roster sets it on
  `concordance` (lore already roaming from WP32; `home_band: Void` is the spawn hint).
- **Removed `entity` from `space_kinds` / `hidden_kinds`** in
  `config/default.yaml`; `DiscoveryKind.ENTITY` survives as an enum (codex art keys)
  but is never salted — `_roll_kind` reads the weights, so dropping it is sufficient.
- `populate_species` special-cases the flag: excluded from the seeded subset `pool`
  and the StarDock `welcome` list, then placed by the new `_place_entity` — always
  drawn, **exactly one** instance, in a deep band (its `home_band` hint, else the
  deepest live band inward), no cluster satellites, never Core/StarDock, drawn
  peaceable (anchor draw — an impartial arbiter that greets whoever finds it).
  `combatant: false` + empty `fleet` are honored at contact (WP24 — no violence path).
- Validator (`_check_species`): exactly one Entity instance; never in the Core.
- **M13 golden batch:** removing `entity` and adding the Entity shift the generation
  draw order (and the validation-retry cadence). Goldens re-baseline via
  self-consistency (no `config_version` bump). Two seed-pinned functional tests
  re-baselined to working seeds (`test_salvage_artifact_payload` 3→9;
  `test_core_law_notice` 3→4 — seed 3 now places the small-universe StarDock outside
  the Core). Full suite green.

Files: `edge/core/config.py`, `config/default.yaml`,
`config/alien_roster_default.yaml`, `edge/bigbang/aliens.py`,
`edge/bigbang/validate.py`, `tests/test_aliens.py`, `tests/test_discovery.py`.
Tests: singular-entity uniqueness + never-Core across 50 seeds × both modes;
deep-band spawn at the 1000-sector default; `entity` never salted across seeds.

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
