# Ground Operations — Survey and Planetary Assault Integration

> Companion to `DESIGN.md`, `GROUNDWAR_POC.md`, `PHASE5_4_PLAN.md`, and
> `SEAMS_PLAN.md`. `DESIGN.md` remains the authoritative *what*; this document
> is the *how and in what order* for replacing the shipped abstract surface and
> invasion paths with the `edge.groundwar` survey and tactical-assault systems.
> Where implementation reality requires a design change, update `DESIGN.md` in
> the same work package and record the reason here.
>
> **Status: implementation underway — GW-WP01–08 shipped; interview decisions resolved (July 2026).
> Next: GW-WP09-PRE (NPC-inhabited worlds at big bang), a prerequisite for GW-WP09 —
> no generated world can route to `Assault` until it lands.**

## Context

The live game currently has two deliberately different planetary interaction
stacks:

1. **Surface discovery** is abstract and replay-safe. `Descend(planet_id)` pays
   a fixed turn cost, `Explore(planet_id)` reveals the next sensor-resolvable
   surface `Discovery`, and `Salvage(discovery_id)` collects its payload. There
   is no persisted descent session, map position, supply clock, or physical
   relationship between a surface marker and the discovery it reveals.
2. **Planetary invasion** is abstract and replay-safe. After the orbital base
   and citadel gun fall, `InvadePlanet(planet_id, fighters)` resolves the whole
   attacker-versus-garrison exchange in one reducer call. Victory flips
   ownership and applies the existing treasury, colonist, citadel, garrison,
   standing, and alignment consequences.

The standalone `edge-groundwar` proof of concept has the missing embodied
play:

- **Expedition mode**: one surveyor walks a seeded terrain map, follows orbital
  search circles and a handheld hot/cold scanner, notices nearby disturbed
  ground, digs exact sites, and may visit friendly settlements for supplies and
  hints.
- **Assault mode**: a player-composed powered-armour platoon drops onto a
  defended world, maneuvers over terrain with cover and line of sight, fights
  emplacements and garrison sorties, and tries to break planetary Resolve and
  broadcast surrender terms before retrieval.

The POC is intentionally not a live-game subsystem. It invents its own sites,
cities, force strength, difficulty, and RNG; holds mutable `Battle` /
`Expedition` objects directly in Textual screens; remembers finds only in
application memory; and has no command/event, state-hash, wire-codec, or
multiplayer surface. Integration is therefore a promotion into the production
architecture, not a direct screen import.

This plan replaces the two abstract paths while preserving the systems they
already get right: seeded universe discoveries, sensor progression, codex and
payload ownership, the orbital siege ladder, persistent planetary defenses, conquest
settlement, diplomacy consequences, command-log rebuild, fog-safe DTOs, and the
single-writer multiplayer server.

## Outcome and exit criterion

A planet presents one coherent ground interaction derived from live state:

- an uninhabited, friendly, or player/corp-owned landable world opens a survey
  expedition against that world's actual seeded discoveries;
- an inhabited world below the configured friendly threshold opens a proper
  tactical assault after its orbital defenses have been defeated;
- neutral/wary standings below that threshold are included; there is no separate
  neutral-permission branch;
- non-landable world objects remain orbital interactions;
- every ground action is authoritative, replayable, remotely playable, and
  resumable after reconnect/reload;
- survey findings and assault outcomes settle through the existing discovery,
  economy, ownership, citadel, diplomacy, and event rails rather than parallel
  POC-only state.

**Exit criterion:** a player can discover a real seeded artifact by reading the
terrain and can conquer one defended non-Core world by forcing surrender; both
command logs rebuild to identical state hashes, a remote client can complete
both flows, and no legacy `Descend`/`Explore` or one-roll `InvadePlanet` path
remains reachable.

## Scope

### In scope

1. A single pure ground-access classifier shared by projection and reducers.
2. Replayable active survey and assault state.
3. Production survey generation from real `Discovery` records.
4. Sensor gating and atomic artifact/codex logging on the terrain map.
5. Friendly settlement resupply/hints keyed to live inhabitants and standing.
6. Tactical assault generation from planet type, population, garrison,
   citadel, gun, ownership, and diplomatic state.
7. Powered-armour movement, jump/AA reactions, cover/LOS, detection/jamming,
   emplacements, sorties, Resolve, broadcast, retrieval, and casualty limits.
8. Strategic settlement of victory, defeat, extraction, defenders, attackers,
   civilian harm, ownership/access, loot, and diplomatic consequences.
9. Config integration, commands/events/codecs, DTOs, local/remote clients,
   Textual screens, help/keymap, snapshots, and replay/property tests.
10. Retirement of the abstract surface and invasion paths after parity.

### Explicit non-goals

- Real-time or simultaneous tactical turns. Assault remains IGOUGO.
- A general army/4X logistics simulation beyond the interview-decided ground
  force model.
- Tactical orbital-base combat. The orbital base remains a space-combat siege
  rung.
- Core-world conquest. Core worlds remain non-invadable.
- Asteroid-belt landing. Belts remain orbital spatial features.
- Procedural alien dialogue inside tactical turns. Settlement and surrender
  text may use existing species/persona flavor later, but dialogue mechanics
  are not widened by this plan.
- A tactical AI client for defending human players. The authoritative
  attacker-driven model remains compatible with an offline defender.

## Interview decision register

All decisions below were resolved by design interview in July 2026 and are
normative inputs to the work packages.

### D1 — Which standing opens which branch? **RESOLVED**

Every inhabited world below the configured **friendly/amity threshold** is
assaultable. There is no neutral/wary permission branch: owned-by-player/corp,
allied, or friendly-band inhabited worlds open survey; below-friendly inhabited
worlds open assault; uninhabited landable worlds open survey. The continuous
disposition value still drives other systems, but surface access deliberately
uses the amity threshold as a hard boundary.

### D2 — What does surrender grant on an unaligned inhabited world? **RESOLVED**

Surrender first creates a **player-controlled protectorate** that retains its
inhabiting species identity. It does not immediately become a player-owned
colony. The player may later choose to take ownership through an explicit,
consequence-bearing action whose gates and effects are specified by GW-WP01.

Alliance-, corp-, and player-owned enemy worlds still follow their applicable
conquest settlement, while an unaligned world's new protectorate state records
control without misusing `owner=none` or erasing `inhabited_by_species_id`.

### D3 — What is the player's ground force? **RESOLVED**

Ground troops are **hired recruits equipped with purchased powered suits at
Stardock**. They are persistent ship-carried assets:

- recruits are people hired at Stardock;
- suits are purchased equipment;
- ground recruits occupy a new ship **passenger capacity distinct from both
  cargo holds and the existing colonist capacity**;
- the assault composer assigns an available suit to each deployed recruit;
- when a platoon member dies, both that recruit and their equipped suit are
  lost.

Surviving recruits and suits return with the platoon under the extraction rules
resolved by D8. Fighters remain space/sector-combat assets and are not
reinterpreted as powered-armour infantry.

### D4 — How do tactical actions consume macro turns? **RESOLVED**

Ground operations consume a **fixed configurable number of main-game turns per
configured multiple of local expedition/assault turns**. Tactical actions
consume only local supplies, action points, and retrieval time; they do not each
cost one main-game turn.

The charge is applied **as tactical-turn thresholds are crossed**, using a
configurable quantization such as `ceil(local_turns /
local_turns_per_main_turn) × main_turn_cost`. An action that would enter a new
threshold block is rejected when its main-game quantum cannot be paid; extraction
remains available without crossing another threshold so the player cannot be
stranded. The first threshold and any launch minimum are config and finalized in
GW-WP01.

### D5 — What survey progress persists between descents? **RESOLVED**

When an expedition ends and the player later descends again:

- the surveyor's **position persists** for that player/world;
- settlement **hints persist** and continue to narrow the same sites;
- resolved discoveries remain resolved through discovery/codex state;
- **trenches reset**;
- **supplies reset** to the configured starting amount.

An active expedition persists exactly across reload/reconnect. This requires a
small per-player/per-world survey-progress record outside the active operation
for position and hints; trenches and supplies remain expedition-local.

### D6 — What happens when a surface discovery is dug? **RESOLVED**

A successful dig **reveals and logs the discovery automatically**. There is no
second surface-collection action and no hold-capacity failure after excavation.
Surface archaeology rewards move to an abstract model:

- one artifact/research object is recorded for the player;
- the discovery enters the codex with lore;
- surface digs do **not** uncover latinum or loose ship parts.

Artifacts retain a deliberate later seam for a research path that improves
access to ship upgrades. Research itself is outside this plan, but GW-WP01 and
GW-WP05 must preserve the minimum stable artifact identity/provenance needed so
that later work does not require rewriting old saves. Open-space wreck and
salvage rewards remain unchanged.

### D7 — How does tactical defense relate to `Planet.fighters`? **RESOLVED**

The ground-operations system **replaces the `Planet.fighters` invasion
mechanism**. Fighters are no longer converted into tactical infantry/armour or
used to resolve planetary conquest. They remain space-combat assets used in
ship/space battle and to assault fighters already deployed in a sector.

Planets therefore gain a distinct persistent ground-defense model for tactical
defenders and emplacements. Its exact recruitment/production/recovery model is
resolved separately (D11). Existing fighter production/stock must be migrated
and surfaced as space-fighter logistics rather than silently deleted.

### D8 — What happens on voluntary or forced assault extraction? **RESOLVED**

Surviving attackers return if retrieval succeeds; dead/missing recruits, their
equipped suits, and spent ordnance stay lost. Defender casualties and destroyed
structures **persist** after failed, voluntary, forced, and casualty-ceiling
extractions. Planetary Resolve partially recovers between assaults. Surrender
is the only conquest/protectorate outcome; a failed operation never restores a
pristine battlefield.

### D9 — How should gas giants/Cloud Cities participate? **RESOLVED**

Bare jovians and Cloud Cities remain **orbital-only until a dedicated Cloud City
groundwar gate is crossed**. The classifier and data model retain an explicit
future-assault seam; they must not reuse terrestrial terrain.

The follow-up implementation uses a specialized tactical map resembling the
**interior of a space station**, including new procedural/static art. It lands
in later work packages after the terrestrial/barren replacement is complete.
Friendly/owned Cloud City survey remains orbital-only unless separately expanded
later; the committed follow-up here is the below-friendly assault interior.

### D10 — What identity does a surface artifact retain? **RESOLVED**

Each excavated artifact is a **unique provenance-bearing record**, never folded
into a fungible count. It is keyed to its `Discovery.id` and retains rarity,
origin planet/site, lore identity, and a configurable research domain/tag. A
future research or alien-barter system may consume/use it without losing its
history. Existing generic tier-count artifacts require an explicit compatibility
path rather than silently absorbing new surface artifacts.

### D11 — How are planetary ground defenders created and replenished? **RESOLVED**

Planetary ground defense uses a **combination** of all three sources:

- slow automatic population-based militia recovery supplies a baseline;
- a dedicated colonist allocation trains/equips defenders faster on production
  ticks, with any equipment/material cost made explicit and conserved;
- owners reinforce worlds by deliberately transferring recruits and suits into
  the local typed garrison under D15.

The resulting typed ground garrison is persistent and distinct from
`Planet.fighters`. Big-bang seeding derives its initial force from population,
citadel, owner/species, and band. Tactical casualties reduce it directly; the
D8 recovery rails rebuild it rather than regenerating a fresh force per assault.

### D12 — When are macro-turn quanta charged? **RESOLVED**

Main-game turn quanta are deducted **as local tactical-turn thresholds are
crossed**, not reserved upfront and not deferred until extraction. The reducer
checks affordability before an action advances into the next threshold block.
When the player cannot pay, further time-advancing tactical actions are barred
but extraction remains legal.

### D13 — What rights does a protectorate grant before annexation? **RESOLVED**

A protectorate grants **limited planetary exclusion**, not control of the
surrounding sector:

- warp transit through the sector remains open;
- the controller has exclusive administration, defense management, production
  share, and the future option to annex;
- outsiders cannot colonize the world, withdraw its stores/treasury, manage its
  defenses, or annex it peacefully;
- friendly visitors may orbit, trade, survey/land when the inhabitants would
  normally permit it, and use services their standing allows;
- hostile visitors may assault after defeating the applicable orbital defenses;
- defenses account for both the inhabitants' disposition and the controller's
  wars when deciding whom to engage.

The inhabitants retain their polity, stores/treasury, ordinary service gates,
and control over local recruitment. The controller receives a configured
production share rather than treating all planetary inventory as personally
owned.

### D14 — What gates and consequences apply to annexation? **RESOLVED**

Annexation is not available immediately after surrender. It requires both:

- a configured minimum time under protectorate control; and
- planetary Resolve recovered to a configured threshold.

Annexation is then an explicit command and ownership transition. Because it
converts a retained local polity into player property, it carries additional
species-attitude, grudge, relation-spillover, and alignment consequences beyond
maintaining the protectorate. The reducer rechecks elapsed time, Resolve,
controller identity, and current sovereignty/war state.

### D15 — Can assault platoons be stationed as planetary defenders? **RESOLVED**

After a survey/assault mission, **every surviving deployed recruit and their
surviving suit returns to the ship**; they never remain on the battlefield by
default.

A separate reinforcement action may deliberately transfer recruits and suits
from the ship into a player world/protectorate. On transfer they become
persistent typed local defenders and are no longer individually tracked or
retrievable. The action conserves passenger/suit inventory atomically and makes
the irreversible conversion explicit before confirmation.

## Ground-access contract

One pure `ground_access` seam returns a tagged result, not loosely coordinated
booleans:

```text
GroundAccess = orbital_only(reason)
             | survey(settlements, reason)
             | assault(owner, inhabitants, blockers)
```

Inputs include the planet capability/state, player/corp ownership, alliance
membership/standing/rivalry, inhabiting species' effective disposition and
grudge, Core status, and the orbital siege ladder. `PlanetDTO`, begin-operation
reducers, bot/service queries, and the Computer planet directory consume the
same result. The reducer always recomputes it; the DTO is advisory.

The classifier distinguishes:

- **inhabited**: live colonists, `inhabited_by_species_id`, or an inhabited
  Cloud City under D9;
- **friendly**: player/corp ownership, same alliance, or effective disposition
  in the configured friendly band;
- **hostile**: declared corp war, rival/negative alliance standing, or an
  unaligned inhabiting species in the configured hostile band after attitude
  and grudge effects;
- **below friendly**: any inhabited world whose effective standing is below
  the configured amity threshold; it routes to assault even when its narrower
  disposition-band label is neutral/wary rather than hostile.

## Cross-cutting invariants

- **G1 — Server authority.** The TUI never owns or mutates a live
  `Battle`/`Expedition`; every action is a command and every visible fact is a
  DTO projection.
- **G2 — Replay.** Starting and acting in a ground operation reconstructs from
  `(seed, config, command log)` and yields an identical `state_hash` after
  reload. Projection never draws RNG.
- **G3 — RNG discipline.** The first survey descent on a world draws its map seed
  from `state.rng` and persists it in that player's per-world survey progress;
  later descents reuse it. Other ground-operation begins draw their operation seed
  from `state.rng`. Deterministic static map generation uses that seed. Combat and
  hint rolls either draw from `state.rng` inside their action reducer or from a
  stored operation sequence with a proved replay contract—never UI RNG.
- **G4 — Immutable core.** Production ground entities are frozen snapshots;
  rules return deltas. Config and `random.Random` objects are not embedded in
  hashed state.
- **G5 — Static/dynamic split.** Terrain and immutable placement are
  reproducible from the operation seed and inputs. Only gameplay-visible
  dynamic state is hashed. Styled art is projection/TUI state.
- **G6 — Real discoveries.** A survey site names exactly one existing
  `Discovery.id`; ground generation never mints a parallel name. Successful
  excavation atomically stamps its artifact reward and codex lore.
- **G7 — Sensor integrity.** An unresolved hidden site cannot be inferred from
  the DTO, map art, scanner, clue placement, action legality, or error text.
- **G8 — Conservation.** Ground actions cannot mint troops, fighters,
  components, cargo, artifacts, latinum, supplies, ammunition, or planetary
  stores outside an explicit configured faucet/reward. The D6 surface artifact
  is an explicit discovery faucet; surface latinum/components are not.
- **G9 — One active interruption.** A player cannot move, dock, trade, hail,
  start space combat, or begin a second ground operation while one is active.
  Structural reducers clear/settle it; screen closure is never trusted.
- **G10 — Concurrent world state.** The game server remains the single writer.
  Starting or settling an operation revalidates the planet against live
  ownership, defenses, discoveries, and other active operations.
- **G11 — Consequence parity.** A tactical assault cannot evade the standing,
  grudge, spillover, alignment, bounty, ownership, and corp-war effects of the
  abstract invasion it replaces; civilian harm adds consequences rather than
  bypassing the existing rail.
- **G12 — No duplicate defenses.** A base razed in orbit never appears on the
  ground map. A citadel gun with zero integrity never respawns tactically.
- **G13 — Core sanctuary.** No Core world can enter assault mode, regardless of
  crafted commands or stale DTOs.
- **G14 — Wire parity.** Local and remote clients expose the same operation
  views and legal commands. Every command/event/DTO change bumps and tests the
  explicit wire version as required.

## Architecture

### Production package boundary

Promote the rules-quality parts of the POC into a strict, core-level package:

```text
edge/core/groundwar/
    models.py       frozen active-operation snapshots
    access.py       world routing and siege blockers
    terrain.py      gameplay feature generation, no Rich/Textual/art imports
    survey.py       survey generation and pure action resolution
    assault.py      assault generation and pure action resolution
    settlement.py   strategic reconciliation and consequences
```

`edge/core/rules.py` remains the command dispatcher and only authoritative
state-mutation seam. `edge/groundwar/` remains a developer play-test application
and is refactored to consume the production package; its Textual widgets may be
reused by the live TUI only after they use DTOs and a client facade.

Biome feature definitions used by gameplay must move to, or be shared through,
a lower pure module so `edge.core` never imports `edge.art`. Glyph/color
resolution remains in `edge.art`/`edge.tui`.

### Hashed state

Add `Player.ground_operation: GroundOperation | None`, analogous to
`active_encounter`. A discriminated operation stores only dynamic authoritative
state and sufficient generation identity:

- common: operation id/kind, planet/sector, seed, started day/command sequence,
  local turn, outcome;
- survey: explorer, supplies, visible/resolved discovery ids and dug cells;
- assault: deployed platoon, surviving troopers, ordnance, structures/ground
  defenders, Resolve, city states, retrieval clock, casualties, and the
  operation's reserved defender snapshot.

Large immutable terrain/art grids are regenerated from the stored seed and
snapshotted generation inputs. A runtime cache may optimize regeneration but
must be safely discardable and excluded from `state_hash`.

`Player` also carries a compact per-world survey-progress map containing the D5
position and persistent settlement/site hints. It is hashed because it changes
future search information; trenches and replenished supplies stay only on the
active operation.

Surface rewards live as immutable `ArtifactRecord`s on the player (or an
equivalent state-level inventory keyed by owner): discovery id, origin
planet/site, rarity, research domain, lore key, and acquisition day. D10 records
remain individually addressable; they are not collapsed into the legacy
rarity-tier count map.

### Command surface

The exact command names may consolidate during implementation, but the wire
must represent these actions explicitly:

```text
BeginSurvey(planet_id)
GroundMove(operation_id, actor_id, x, y)
SurveyDig(operation_id)
SurveyTalk(operation_id)

BeginGroundAssault(planet_id, loadout)
GroundDrop(operation_id, placements)
GroundJump(operation_id, actor_id, x, y)
GroundFire(operation_id, actor_id, x, y, weapon)
GroundBroadcast(operation_id, actor_id, city_id)
EndGroundTurn(operation_id)

ExtractGroundOperation(operation_id)
```

Every command validates the operation id, player, current planet/sector,
operation phase, actor ownership, and live world preconditions.

## Milestones

| Milestone | Work packages | Result |
|---|---|---|
| **GW-M1 — Contract and core** | GW-WP01–04 | Decisions/spec fixed; replayable ground-operation state and access classifier |
| **GW-M2 — Survey replacement** | GW-WP05–07 | Real discoveries excavated into unique artifacts and codex lore |
| **GW-M3 — Assault replacement** | GW-WP08, GW-WP09-PRE, GW-WP09–11 | Defended worlds fought tactically and settled strategically |
| **GW-M4 — Parity and retirement** | GW-WP12–14 | Remote/UI/bot parity, balance, legacy paths removed |
| **GW-M5 — Cloud City interiors** | GW-WP15–16 | New station-interior art and gated Cloud City assaults |

Each milestone leaves the ordinary sector/port/space game playable. GW-M2 may
ship behind `groundwar.survey_enabled`; GW-M3 behind
`groundwar.assault_enabled`. The flags are migration scaffolding, removed or
defaulted permanently on in GW-M4.

Cloud Cities retain a separate `groundwar.cloud_city_assault_enabled` gate. It
stays off through GW-M4 and turns on only when GW-M5's specialized interior art,
rules, DTO, and tests are complete.

### Config epochs are batched per milestone, not per work package

**Decision (July 2026).** An individual WP does **not** bump `config_version`.
Hashed-state and config changes accumulate across the WPs of a milestone and the
version bumps **once**, when the milestone closes. GW-WP03 stated this intent
("Golden replay regeneration happens in this WP, once") and practice drifted:
WP06, WP07 (twice) and WP08 each took their own epoch, and every bump costs a
`config/default.yaml` edit, a `tests/test_config.py` assertion, and golden/snapshot
churn that reviews have to read past. GW-WP09-PRE through GW-WP11 will each change
hashed `Planet` state; one bump at the end of GW-M3 is the whole cost instead of
three.

This is cheap because **nothing enforces `config_version` at load.** It is stored
on `Game`, in the SQLite `meta` row and in the portable bundle, and shown by the
sysop console, but `GameService.load_game` gates only on the *dialogue
fingerprint*. It is provenance, not a compatibility check.

Two consequences to hold:

- **Mid-milestone saves are not portable across a WP boundary**, and nothing will
  say so. Between bumps, a save's recorded version still matches the build while the
  regenerated universe has moved underneath it, so the log replays onto a different
  world and fails as an arbitrary rules error deep in the replay. The
  `--save` guard in `python -m edge.bigbang` compares the two versions and cannot
  see drift that was never versioned. Discard saves across a WP boundary; do not
  file the resulting replay error as a bug.
- **The closing WP of a milestone owns the epoch**: the bump, the
  `tests/test_config.py` assertion, golden replay regeneration, and the snapshot
  pass, for everything the milestone accumulated.

`WIRE_VERSION` is unaffected and still bumps per change — the wire fingerprint test
forces it, and it is a genuine client/server compatibility gate rather than a record.

## Work packages

### GW-WP01 — Interview decisions and authoritative spec delta (M) — SHIPPED

**Status:** shipped July 2026. The authoritative delta records D1–D15 and
adopts the prototype as the source for the production system; implementation
begins with GW-WP02.

Resolve D1–D15. Update `DESIGN.md` §§3, 4, 4.2, 7, 10, 11, 13, and 14 with:

- the ground-access matrix;
- active ground-operation state and replay lifetime;
- survey discovery/sensor/collection semantics;
- troop/equipment/capacity and turn-economy decisions;
- assault surrender, failed-extraction, garrison, civilian, and conquest rules;
- Cloud City treatment;
- the screen map and exit criterion.

Update `GROUNDWAR_POC.md` from “standalone possible future” to the adopted
prototype/source and state which POC choices survive or change.

Files: `docs/DESIGN.md`, `docs/GROUNDWAR_POC.md`, this plan.
Tests: none (docs).
Commit `ground: GW-WP01 ground-operations decisions + spec`.

### GW-WP02 — Production config and pure terrain seam (M)

Move groundwar balance into frozen Pydantic `GameConfig` models. Keep one
shipped YAML source of truth under `config/default.yaml`; the standalone app
loads that block rather than a divergent loader. Split gameplay biome features
from glyph/color rendering so core terrain generation has no upward import.

Validate ranges and cross-field invariants: non-empty suit/terrain registries,
reachable map dimensions, positive pressure clocks, scanner bands sorted and
non-overlapping, conversion ratios nonzero, and costs/capacities bounded.

Files: `edge/core/config.py`, `edge/config.py`, `config/default.yaml`,
`edge/core/groundwar/terrain.py`, `edge/art/terrain.py`,
`edge/groundwar/config.py`, `edge/groundwar/mapgen.py`.
Tests: config rejection/golden loading; terrain determinism and passable-component
properties across types/seeds.
Commit `ground: GW-WP02 production config + pure terrain seam`.

### GW-WP03 — Frozen operation models, generation identity, and state epoch (L)

Add frozen survey/assault state models and `Player.ground_operation`. Define
stable operation ids and derive the survey map seed on first descent from
`state.rng`, persisting it in per-world progress for reuse; assault seeds remain
per-operation. Add `ReduceResult` support, state hashing, command/event codecs,
wire schemas, and movement/docking/encounter blockers.

Add the D5 per-world survey progress and D10 provenance-bearing artifact record
in the same epoch, including an explicit compatibility policy for pre-existing
generic barter artifacts.

Batch hashed-field and config changes into one config-version/state-hash epoch.
Golden replay regeneration happens in this WP, once.

Files: `edge/core/groundwar/models.py`, `edge/core/models.py`,
`edge/core/rules.py`, `edge/core/events.py`, `edge/store/codec.py`,
`edge/store/snapshots.py`, wire codec/fixtures, `config/default.yaml`.
Tests: model invariants; begin/clear lifetime; rejected commands leave no log;
codec round trips; save/reload mid-operation; identical state hash.
Commit `ground: GW-WP03 replayable active operations (config epoch)`.

### GW-WP04 — Ground-access classifier and orbit projection (M) — SHIPPED

**Status:** shipped July 2026. The pure `ground_access` classifier
(`edge/core/groundwar/access.py`) returns the tagged
`OrbitalOnly | Survey | Assault` result and is now the authoritative routing seam:
`_begin_survey` recomputes it and rejects any non-survey world with the tagged
reason (G1/G13 lockstep), and `PlanetDTO` projects `ground_mode` / `ground_blocker`
/ `ground_settlements` for the bot/service surface (wire v24). Covered by
`tests/test_groundwar_access.py` (landability, D1 inhabited/friendly/below-friendly
split, D9 Cloud City seam, G13 Core sanctuary, G12 siege blockers, assault-disabled,
DTO/reducer lockstep).

**Scope deviation (recorded per the plan's own change rule).** The D2/D13/D14
**protectorate and annexation *commands and hashed state*** are **deferred to the
settlement work (GW-WP11)**, where surrender first *creates* a protectorate. Three
reasons: (1) no protectorate can exist until GW-WP11, so an `Annex` command / a
hashed `Planet` protectorate field would be unreachable dead code today; (2) GW-WP03
declared all hashed-field/config changes batched into a *single* state-hash epoch
("Golden replay regeneration happens in this WP, once") — minting a protectorate
field here would force a second golden/wire epoch for no live behaviour; (3) GW-WP04's
own Files list omits `models.py`, the `rules.py` command surface, `codec.py`,
`events.py`, and the wire fixtures, i.e. the pure classifier + projection *is* the
intended WP04 deliverable. The classifier's `Assault` arm already carries `owner` /
`inhabited` so GW-WP11 can settle protectorate vs. conquest without reshaping the
contract. DESIGN.md's protectorate/annexation matrix (authored in GW-WP01) is
unchanged; only the implementation *order* moves.

Implement the D1/D9/D13 access contract in one pure seam. Cover player/corp
ownership, corp war, alliances/governor, effective
disposition/grudges, inhabitants, landability, Core sanctuary, and
base/gun/shield blockers.

Project the tagged mode and exact blocker through `PlanetDTO`; keep reducers
authoritative by recomputing it. Update the planet directory and bot/service
query surface so automation can distinguish survey and assault and explain
their blockers.

*Deferred to GW-WP11 (see Status above):* explicit protectorate/annexation
commands + hashed state, and the projection of current controller / granted
rights / annexation blockers. Represented in the contract's shape (`Assault.owner`
/ `inhabited`) so no reshaping is needed when surrender first creates a
protectorate.

Files (as shipped): `edge/core/groundwar/access.py`, `edge/core/rules.py`
(`_begin_survey` lockstep), `edge/server/session.py`, `edge/core/dto.py`,
`edge/server/wire.py` (v24). Deferred surface (`client.py` / `protocol.py` /
`planet.py` UI) lands with the survey/assault screens in GW-WP07/WP12.
Tests: `tests/test_groundwar_access.py` — table coverage over
ownership/standing/Core/defense; DTO/reducer lockstep.
Commit `ground: GW-WP04 one ground-access contract` — **GW-M1 done.**

### GW-WP05 — Survey generation from real discoveries (L) — SHIPPED

**Status:** shipped July 2026. New pure `edge/core/groundwar/survey.py` builds a frozen,
non-hashed `SurveyMap` (regenerated from the operation seed, G5) from a world's **real**
surface `Discovery` records: one `SurveySite` per visible discovery keyed to its
`Discovery.id` (G6), terrain + optional friendly settlements + landing confined to one
passable component (reachability). Each site's position/circle/clues draw from a
**per-discovery salt** (`{seed}|site|{id}`), so a later descent after a sensor upgrade
adds the newly resolvable site **without moving** known ones (upgrade-and-return, G7).
`eligible_surface_site_ids` snapshots the sensor/detection window; `_begin_survey` stores
it in `SurveyOperation.visible_discovery_ids` (+ `resolved_discovery_ids` for already-
collected sites), so a hidden out-of-reach site leaks nothing. D6 landed in
`edge/bigbang/discoveries.py`: surface sites **and** hostile-homeworld raid caches now
yield an artifact + codex lore (never latinum/loose components); open-space and combat-
wreck payloads are untouched (`_make_payload` unchanged; a separate `_make_surface_payload`
draws no RNG so later shared-RNG draws stay stable). Movement/dig/talk **actions** and
reward settlement are GW-WP06; the live DTO/Textual is GW-WP07. Covered by
`tests/test_groundwar_survey.py`; `test_encounters.py` raid-cache assertion updated to the
artifact contract.

Files (as shipped): `edge/core/groundwar/survey.py` (new), `edge/core/rules.py`
(`_begin_survey` snapshot), `edge/bigbang/discoveries.py` (D6). No hashed-state/config or
wire change (`SurveyOperation` fields already existed from GW-WP03).

Port expedition generation and movement into immutable pure rules. Generate one
stable site position per eligible existing surface `Discovery`, not POC find
kinds. Preserve actual ids, names, kinds, rarity, payloads, global `found_by`,
and player codex/detection state.

Normalize generated surface-site rewards to the D6 archaeology contract:
artifact/research provenance plus codex lore, never latinum or loose components.
Keep open-space and combat-wreck payload generation byte-compatible. The
artifact record must retain enough stable discovery identity for the deferred
research system without implementing research here.

Sensor-ineligible hidden sites leak no marker, circle, clue, scanner signal,
pathing stop, action, or count. A later operation after a sensor upgrade can add
the newly resolvable site without moving already known sites; use per-discovery
placement salts rather than list-order RNG.

Settlement placement depends on friendly live inhabitants. Sites stay outside
settlement/landing keepouts and in the explorer's passable component.

Files: `edge/core/groundwar/survey.py`, `edge/core/groundwar/terrain.py`,
`edge/bigbang/discoveries.py`, `edge/core/models.py`, `edge/core/discovery.py`,
`edge/core/rules.py`, `edge/core/events.py`.
Tests: deterministic placement; real-id bijection; reachability; sensor
non-leakage; upgrade-and-return; zero-site world; already-collected site;
friendly versus uninhabited settlement generation; every surface find yields
artifact+lore and never latinum/components; open-space payload regression.
Commit `ground: GW-WP05 survey generation from universe discoveries`.

### GW-WP06 — Survey actions, persistence, and reward settlement (L) — SHIPPED

**Status:** shipped July 2026. Pure action functions in `edge/core/groundwar/survey.py`
(`survey_move` / `survey_dig` / `survey_talk` + `survey_map_for` / `path_to` /
`scanner_reading` / `visible_clues`, returning a frozen `SurveyActionResult`) resolve the
POC's walk/dig/talk against the frozen `SurveyOperation` + regenerated `SurveyMap`. The
reducers `GroundMove` / `SurveyDig` / `SurveyTalk` (rules.py) drive them; a dig settles the
D6/D10 reward **atomically through the existing discovery rail** — detection + codex +
experience + `found_by`, plus a provenance-bearing `ArtifactRecord` — with no second collect
step, no hold gate, and never latinum/components. A multiplayer excavation race mints exactly
one artifact (G8). **D4/D12** macro-turn quanta land as config on `GwExpedition`
(`local_turns_per_main_turn` / `main_turn_cost`): marching charges `ceil(local/L)×cost` main
turns as thresholds cross, refusing a march that would cross an unaffordable one; digging and
talking cost only local supplies; extraction is never charged. Extraction persists the D5
map identity/position/hints while trenches and supplies reset next descent (WP03 `_extract`
rail). New
events `GroundMoved`/`SurveyDug`/`SurveySiteExcavated`/`SurveyTalked` + codecs; wire v25.
Epoch: config_version 7→8 (the D4 config). Covered by
`tests/test_groundwar_survey_actions.py` (10 tests incl. a command-log replay golden). The
live DTO/Textual is GW-WP07.

**Deviation:** the D4 macro-turn config was not present after the WP02/WP03 config epoch, so
WP06 also touches `config.py`/`default.yaml` (config_version 7→8) beyond its listed files.
Recorded here per the plan's change rule.

Implement movement/march halting, scanner readings, clue visibility, digging,
settlement talk/resupply/hints, supply exhaustion, excavation settlement, and
extraction under D4–D6. A successful dig atomically updates detection, codex lore,
experience, artifact state, and the discovery's collection marker through the
existing discovery settlement rail; no second collect command or hold-space
gate follows it.

No UI close action settles or discards state. Reload/reconnect resumes the exact
operation. Voluntary extraction clears active state while preserving the D5
position/hints; a later descent restores those facts with fresh supplies and no
trenches. Main-game turns settle in the configured D4 quanta, with no per-action
macro charge. Under D12 the reducer deducts a quantum before crossing each local
threshold, refuses unaffordable time-advancing actions, and always permits
extraction. Movement from orbit remains impossible until extraction settles.

Files: `edge/core/groundwar/survey.py`, `edge/core/discovery.py`,
`edge/core/rules.py`, `edge/core/events.py`, `edge/store/codec.py`.
Tests: supplies never negative; dry re-dig free; hint once; position/hint
survive re-descent while trenches/supplies reset; artifact/codex/XP exactly once;
simultaneous excavation race; macro-turn quantization; exhaustion; extraction; complete
command-log rebuild golden.
Commit `ground: GW-WP06 authoritative survey actions + rewards`.

### GW-WP07 — Live expedition DTO and Textual replacement (L) — SHIPPED

**Status:** in progress July 2026. `SurveyExpeditionDTO` and its cell/contact/settlement
children project a cropped live viewport without the operation seed, unresolved
discovery identity, or exact dig positions; search rings, scanner heat, clues, one-turn
reachability, legal actions, supplies, and the next macro-turn threshold are computed at
the server boundary. `ground_operation_view` is present on the service, async local and
remote clients, JSON-RPC whitelist, and wire v26. The production
`GroundExpeditionScreen` consumes only that async `GameClient` view and commands, with
keyboard/mouse cursor, keyboard march/dig/talk/extract, find modal/art, contextual
help, event copy, responsive compact/standard/wide snapshots, and automatic resume from
`GameScreen`. `PlanetScreen` renders the classifier's exact Survey / Assault / Orbital-only
route and starts `BeginSurvey` for Survey worlds.

**Correction:** strict POC/plan parity review found that the initial implementation drew a
fresh survey-map seed on every descent and saved only position/hints. `SurveyProgress` now
persists the first descent's map seed, so terrain and known site coordinates remain fixed on
return while supplies and trenches reset as D5 requires. This hashed-state addition advances
`config_version` 8→9. The replacement screen also restores the POC-sized standard viewport
(no extra title row, a three-row event log) and uses keyboard actions without an action-button
row. WP07 remains in progress pending the rest of the recorded POC-parity audit.
The server projection now also uses the bounded discardable G5 survey-map cache promised by
the architecture, so viewport pans do not regenerate OpenSimplex terrain and passability.
The client reuses the POC camera contract (cursor follow, HJKL fast cursor, wasd manual pan
with the cursor riding along), while cursor-only movement redraws only the map widget and
its immutable frame is cached. This restores responsive navigation without giving the
client authoritative state.
Excavation preserves the earned visual chart: a resolved contact continues to project its
scanner field and already-seen nearby clues, with the trench and find marker added on top;
its approximate search circle disappears because the exact site is now marked. Scanner text
and march stopping remain unresolved-contact rules, so retaining the presentation layer
cannot create false action behavior or leak an unseen site.
The POC archaeological corpus is promoted into the production discovery presentation rather
than rewritten: its five find identities, name generator, blurbs, and exact 48×15 procedural
field sketches now decorate compatible existing `Discovery` records. A deterministic
`(Discovery.kind, Discovery.id)` adapter maps ruins/artifacts/ancient technology onto those
identities; crashed ships retain their existing generator because the POC has no equivalent.
Newly generated surface records store the POC-style name; compatible existing records are
decorated with that same deterministic name when projected into a survey, and excavation
carries it into artifact provenance. This generation-visible identity correction advances
`config_version` 9→10.

**Migration note:** the former `SurfaceScreen` remains in-tree for its static screenshot
and historical Phase-2 harness, but no live service route reaches it after this WP. The
optional `groundwar.survey_enabled` scaffolding mentioned above never landed in GW-WP02/03;
rather than add a second config/state epoch solely for a disabled-by-default legacy route,
the authoritative replacement is directly enabled. GW-WP14 still removes the legacy
commands/DTO/screen and their historical tests as planned.

Covered by `tests/test_groundwar_expedition_view.py` (fog/crop, excavation reveal,
local/remote wire parity, Pilot keyboard/mouse/extract and active-operation resume,
and three responsive snapshots). The historical named flow in `tests/test_tui_flow.py` now follows
orbit → survey → march → dig → automatic codex settlement.

Adapt the POC expedition screen to the async `GameClient` facade. It renders a
fog-safe viewport DTO and sends commands; it never receives an `Expedition`
object. Preserve keyboard/mouse cursor, hot/cold scanner, clues, march stopping,
settlement interaction, find art/modal, responsive layouts, help, and theme.

Orbit routes survey worlds into `BeginSurvey`; reconnect detects and resumes an
active survey. Update the remote wire and event rendering. Retain the old surface
screen only behind the migration flag until GW-M4.

Files: `edge/core/dto.py`, `edge/server/session.py`, `edge/server/client.py`,
wire codec, `edge/tui/screens/planet.py`, new/ported ground-operation screen,
`edge/groundwar/expedition_ui.py`, help/keymap docs.
Tests: DTO fog; local/remote parity; Textual Pilot keyboard/mouse flow;
compact/standard/wide snapshots; reconnect mid-survey.
Commit `ground: GW-WP07 live survey expedition UI` — **GW-M2 done.**

### GW-WP07-FU1 — POC presentation parity and terrain legibility (M) — SHIPPED

**Status:** shipped July 2026 (commit `3649bc0`, wire v27). Playtest follow-up closing the
gap between `GroundExpeditionScreen` and the POC `expedition_ui.py`, plus two terrain
colouring defects found while doing it.

**Legibility (both were invisible glyphs, not dim ones).** (a) Overlays repaint the
backdrop while keeping the terrain foreground, but `readable_fg` had corrected that
foreground against the *terrain's* background — 16 of 91 terrain x overlay combinations
were unreadable, `water_deep` on the `dark_orange3` scanner band at a 0.002 luminance gap,
with the scanner overlay on by default. Contrast is now checked against the winning
backdrop (0 of 320 unreadable, worst gap 0.203). (b) Named ANSI colours are
theme-dependent, so contrast measured on rich's nominal 4-bit palette did not describe
what the terminal painted: `terrestrial_cool` forest is authored `bright_green on green`,
whose nominal gap clears the correction threshold, so it was emitted as *names* and a
terminal theme collapsed the pair — trees visible only under the cursor. Styles are pinned
to truecolor hex so measured and rendered contrast are the same thing.

**Terrain glyphs.** Selection took the first non-space registry entry per feature and
reused it everywhere, discarding the authored weights and the blank entries (forest is 40
of 89 parts blank), so forest painted as a solid run of one glyph. Glyphs now draw against
the cumulative weights keyed on feature + cell coordinates + `planet_id` — all public DTO
fields, so texture costs nothing in fog of war and the operation seed still never crosses
the boundary (G5) — via CRC32, not `hash()`, whose per-process salt would make snapshots
irreproducible.

**DTO.** `GroundCellDTO.gate` (town wall gates were indistinguishable from masonry, so the
way in was invisible), `SurveySettlementDTO.plaza_x/plaza_y` (replacing an `(x+y+id) % 11`
plaza guess) and `.hint_available`, `SurveyExpeditionDTO.scanner_band`.

**Screen.** Full POC help prose plus a symbol legend, carried by a new generic
`HELP_LEGEND_ROWS` hook on the shared `HelpScreen`; `z` log expand; log lines coloured by
event type; trench/find/hint cell flashes; outcome summary and key cheatsheet.

**Known gaps, deliberately deferred:** `_feature_colors` matches the *first* band with a
given feature name, so where a biome repeats one (`terrestrial_cold` ice, jovian,
asteroid_belt) the later band's colours are unreachable — fixing it needs a band index on
`GroundCellDTO`. And `_CONTRAST_TRIGGER` (0.20, `edge/art/terrain.py`) leaves
mountain/dust/snow honestly dim at ~0.25; raising it is shared with the world-art screens.

### GW-WP07-FU2 — Player-chosen survey drop site (M) — SHIPPED

**Status:** shipped July 2026. Playtest follow-up: `_begin_survey` placed the explorer at
`(width // 2, height // 2)` — the map centre — regardless of terrain, discarding the
`SurveyMap.landing_x/landing_y` that `_landing()` had already computed inside the sites'
passable component. A descent could therefore start in open water, on a peak, or on an
island with no walking route to any contact.

**The drop site is now the player's choice.** `SurveyOperation.landed` starts False: the
shuttle holds inbound, `explorer_*` is only where the cursor should rest, and
march/dig/talk are refused by `_active_survey` until touchdown (extraction stays legal
throughout, so a descent can be aborted from orbit). `SurveyLand(operation_id, x, y)` +
`SurveyLanded` commit the choice, validated in the reducer against the pure
`landing_sites(smap, config)`: the flood of the region containing the generated landing
zone — guaranteed by `generate_survey` to hold every site, so **no legal drop site can
strand a survey away from its contacts** — minus the new config list
`expedition.landing_blocked_features` (open water, peaks, ice). `suggested_landing` rests
the cursor on the remembered position when it is still legal, else the generated zone.

**Decision (interview, July 2026):** every descent chooses afresh. D5's remembered position
seeds the cursor rather than skipping the choice, so a return trip can deliberately land
somewhere new; `_begin_survey` still persists and restores that position.

**Screen.** Pre-landing the drop zone is lit, the explorer is not drawn (there is no
explorer yet), the cursor turns red over illegal ground, and the sidebar becomes a
SELECT DROP SITE panel. Enter commits in both phases (`action_confirm`) — note no letter
key can: `l` is vim-right in `on_key`, which stops the event before bindings run.
Touchdown plays a descent + dust-plume animation with staged log beats, skippable with any
key; it overrides glyphs rather than styles, so it invalidates the cached frame via an
animation step counter in the frame key.

Epoch: config_version 10→11 (`landing_blocked_features`), wire v27→v28
(`SurveyLand`/`SurveyLanded`, `SurveyExpeditionDTO.landed`/`can_land`/`suggested_landing_*`,
`GroundCellDTO.landing_site`).
Tests: drop zone excludes unsafe terrain and keeps every contact reachable from its
extremes; survey begins inbound with actions refused and extraction legal; landing
validates the cell and happens once.

### GW-WP08 — Ground-force economy and assault composer (XL) — SHIPPED

**Status:** shipped July 2026. The D3 force model is live as persistent ship-carried
assets: `Ship.recruits` (people *hired* at a Stardock for a per-head incentive, the same
posture as colonists — never merchandise), `Ship.suits` (powered armour *bought* there,
counted by suit-class id), and `Ship.ground_missiles` (the heavy-ordnance magazine). All
three ride the new per-hull `passenger_capacity` — a **third** occupancy limit beside
cargo holds and colonist berths, so a platoon never displaces trade goods or peopling a
colony. Commands `HireRecruits` / `DismissRecruits` / `BuySuits` / `SellSuits` /
`BuyGroundOrdnance` are Stardock-gated and clamp to berths, stock, and purse; dismissal
pays severance and resale refunds `ground_force.suit_resale_frac`, so churning a platoon
is a sink rather than a free undo. A hull swap refuses a force the new hull cannot berth,
and the escape pod loses the force with the hull.

**Two conservation rules landed beyond the plan's letter, both recorded in DESIGN §4.2.**
(1) A *suit* takes a passenger berth of its own, not just its wearer — otherwise a hull
could stockpile armour it could never crew — so a hull fields at most half its passenger
capacity as armoured troopers. (2) Ordnance is capped by what the carried suits can
chamber (`missile_capacity`), and surplus **spills** when suits are sold or lost, so
ammunition can never outlive the armour that held it (G8).

Loadout validation and casualty settlement are the pure `edge/core/groundwar/force.py`
seam: `validate_loadout` accepts only owned suits worn by aboard recruits within
`platoon.max_troopers`, and `apply_casualties` removes the recruit *and* their suit
atomically (D8) before re-clamping the magazine. The composer is promoted rather than
rewritten: the POC's `CountSelector` / `PlatoonComposer` moved from `edge/groundwar/`
into `edge/tui/composer.py` and now take `SuitOption` rows with a per-row `available`
ceiling; `GroundForceDTO.options` projects exactly that ceiling (suits owned ∧ recruits
aboard ∧ platoon cap), so a composer built from the projection cannot offer a drop the
reducer would refuse — and the standalone harness drives the *same* widget through
`options_from_suits` with its buy-at-drop latinum budget. The live drop screen itself
lands with the assault UI in GW-WP12; WP08 ships the economy, the seam, and the
projection it consumes.

The Stardock gains a **Marines** tab (`M`, `P` purchases with a quantity prompt) whose
catalog rows carry a `max_affordable` already folded from purse, free berths, and
magazine ceiling, so the tab offers nothing that would bounce.

Epoch: config_version 11→12 (`passenger_capacity` on every hull +
`groundwar.ground_force`), wire v28→v29 (the five commands, their five events,
`ShipDTO` force fields, `BarracksItem` / `LoadoutOptionDTO` / `GroundForceDTO`).
Files (as shipped): `edge/core/config.py`, `edge/core/models.py`,
`edge/core/groundwar/force.py` (new), `edge/core/rules.py`, `edge/core/events.py`,
`edge/core/dto.py`, `edge/store/codec.py`, `edge/server/session.py`,
`edge/server/wire.py`, `edge/tui/composer.py` (moved from `edge/groundwar/widgets.py`),
`edge/tui/screens/stardock.py`, `edge/tui/widgets.py`, `edge/groundwar/app.py`,
`config/default.yaml`, `config/groundwar_default.yaml`, `docs/DESIGN.md`.
Tests: `tests/test_groundwar_force.py` (21) — berth/cargo/colonist separation, purse and
berth clamps, severance and resale conservation, magazine ceiling and spill, loadout
validation, casualty atomicity, hull-swap refusal, catalog/composer projection, codec
round trips, and a Pilot flow hiring through the Marines tab.

*Deferred (recorded per the plan's change rule):* the D15 reinforcement command (which
needs the persistent ground garrison of GW-WP09) and the drop screen itself (GW-WP12).

Implement the D3 force model: persistent recruits hired at Stardock, persistent
powered suits purchased there, a new per-hull passenger capacity separate from
colonist capacity and cargo, ammunition, casualty persistence, and loadout
validation. Port the platoon composer to the client facade and project only
affordances the player can actually fund/deploy.

Define hiring and suit prices, the per-hull passenger cap, Stardock/base service
availability, transfer/refit, and escape-pod behavior. The assault composer may
deploy no more recruits than the ship carries and must assign one owned suit to
each. A killed trooper atomically removes the recruit and equipped suit;
survivors return under D8.

Files depend on D3; expected: `edge/core/models.py`, `edge/core/config.py`,
`config/default.yaml`, `edge/core/rules.py`, `edge/core/events.py`, service-point
and Stardock/base DTO/screens, `edge/groundwar/widgets.py`.
Tests: capacity and cost conservation; no negative balances/ammo; loadout
round-trip; casualty persistence; service availability; property tests.
Commit `ground: GW-WP08 ground force + assault composer`.

### GW-WP09-PRE — NPC-inhabited worlds at big bang (L) — NEXT

**Why this exists.** Found while extending the bigbang inspector (July 2026):
**nothing in the codebase ever sets `Planet.inhabited_by_species_id`.** The only
writer is `edge/core/planets.py:233`, and it *clears* the field (the belt
normalizer). A fresh 1000-sector universe (seed 1986) generates 195 planets with
**0 inhabited worlds, 0 colonists, 0 citadels, 0 garrison fighters, 0 treasury**.

That is not a cosmetic gap — it removes the entire target set of GW-M3. The
classifier's `_is_inhabited` (`access.py:100`) counts live colonists, an
inhabiting species, or a built Cloud City. In a generated universe every world is
therefore either uninhabited (→ `Survey`) or a Cloud City (→ `OrbitalOnly` under
D9); a world the player colonizes is their own, hence friendly (→ `Survey`).
**No world can route to `Assault` at all.** GW-WP09–WP12 would build tactical
generation, actions, settlement, and a battle UI against a universe that contains
nothing to assault, verifiable only through hand-built test states — and D2's
protectorate arc, whose whole subject is the *unaligned inhabited* world, would
have no instance to apply to.

The same gap silently disables shipped behaviour: `RecruitColonists(from_planet=…)`
emigration requires an inhabiting species, survey settlements require friendly live
inhabitants, `populate.py:274`'s "an inhabited world gets no derelict base" branch
never fires, and `validate.py:161`'s companion check is unreachable. D11 already
assumes this data exists — it derives initial ground defense "from population,
citadel, owner/species, and band" — so the population it reads must be seeded
before it can read it.

**Scope.** Seed the inhabited universe at generation:

- **Inhabitants.** Assign `inhabited_by_species_id` from the generated species
  subset across a band-weighted fraction of landable worlds. A species' home
  cluster is populated by that species (§5 step 6, §6.3); worlds beyond it draw
  from species whose `home_band` and disposition make them plausible there. The
  Core stays governor-owned and friendly (G13 is unaffected either way).
- **Population.** Draw native `colonists` against `planet_type`/`habitability_cap`,
  so an inhabited world reads as a real polity rather than a flag.
- **Holdings.** Seed `citadel_level`, `gun_integrity`, `treasury`, and stores on
  inhabited and alliance-held worlds, so the orbital siege ladder has something to
  defeat and GW-WP09's ground garrison has live inputs to scale from. The **ground**
  garrison itself remains GW-WP09's (D11); this WP supplies what it reads.
- **Reachability invariant.** `validate.py` gains a check that a generated universe
  contains at least a configured minimum of **assault-eligible** worlds (inhabited,
  below-friendly, non-Core, landable) outside the Core, and of friendly inhabited
  worlds (which give the shipped survey path real settlements). A seed that cannot
  produce a target set is a generation failure, not a surprise at GW-WP12.
- **Ownership coherence.** An unaligned inhabited world keeps `owner=none` with a
  species id (risk 6's exact shape, and the D2 protectorate's subject); a bloc's
  world is alliance-owned *and* inhabited. Neither may contradict the other.

**Ordering.** Must land **before GW-WP09**. WP09 derives assault difficulty from
population, citadel, owner/species and band; without this, every derivation reads
zero and the tuning work in GW-WP13 would be measuring an empty universe.

**Epoch.** Generation-visible hashed `Planet` fields change, but this WP does **not**
bump `config_version` — under the per-milestone epoch policy above, GW-M3's closing
WP (GW-WP11) carries the single bump, the `test_config.py` assertion, golden replay
regeneration, and the snapshot pass for everything WP09-PRE through WP11 accumulated.
Saves do not survive this WP; that is expected and unsignalled.

**Acceptance readout.** `python -m edge.bigbang --list planets` shows populated
`species` / `pop` / `cit` / `gun` / `treasury` columns on a fresh seed (they are
empty by construction today), and `--stats` reports the inhabited/assaultable
counts.

Files: `edge/bigbang/populate.py`, `edge/bigbang/validate.py`,
`edge/bigbang/generator.py` (summary counts), `edge/core/config.py`,
`config/default.yaml`, `edge/core/planets.py` if the belt normalizer needs to stay
consistent, golden/wire fixtures.
Tests: band-weighted inhabited distribution; Core exclusion; home-cluster species
consistency; unaligned worlds keep `owner=none` with a species id; population within
habitability; determinism across seeds; the minimum assault-eligible and friendly
inhabited counts hold over a seed matrix; `ground_access` returns `Assault` for a
real generated world (the case that cannot be written today without hand-building
state).
Commit `ground: GW-WP09-PRE seed NPC-inhabited worlds`.

### GW-WP09 — Persistent ground defense and assault generation (XL)

Implement the D11 persistent planetary ground-defense model, its big-bang
seeding, reinforcement/replenishment rail, player/protectorate management, DTO
surface, and migration away from `Planet.fighters` as invasion defense.
Planet-produced/stored fighters remain space assets; add any missing transfer
path needed to move them between a planet, ship, and sector deployment.

Ground garrisons combine D11's automatic population baseline, dedicated
colonist allocation, and stationed recruit+suit reinforcements. Define exact
production inputs, caps, the irreversible D15 reinforcement command,
owner/protectorate rights,
and how typed infantry/armour equipment maps onto tactical units without
creating or destroying resources implicitly. Mission survivors return to the
ship; only an explicit transfer merges them into local defense.

Port battlefield/city/structure/garrison generation to frozen pure models.
Difficulty is derived from live state rather than selected from a setup menu:
planet type, population, band, the D11 persistent ground garrison, citadel level,
surviving gun, owner/species, and config scaling curves.

Enforce the orbital ladder at begin. Never stamp a razed base or silenced gun.
Snapshot/reserve the ground defenders committed to the operation so another
command cannot spend them twice. Keep `Planet.fighters` entirely outside this
calculation under D7. Apply the D9 terrestrial-versus-Cloud-City gate.

Files: `edge/core/groundwar/assault.py`, `edge/core/groundwar/access.py`,
`edge/core/models.py`, `edge/core/planets.py`, `edge/bigbang/populate.py`,
`edge/core/citadels.py`, `edge/core/rules.py`, `edge/core/events.py`, planet DTO/UI.
Tests: seeded maps; live-state scaling; city reachability; no duplicate gun;
base/gun/shield/Core rejection; ground-defender reserve conservation; fighters
have no effect on assault odds; concurrent start race.
Commit `ground: GW-WP09 assault maps from live worlds`.

### GW-WP10 — Tactical assault actions and planetary AI (XL)

Port drop placement and AA reaction, individual actions, movement/jump, cover,
LOS, firing, missiles, Scout jamming/detection, Command aura/broadcast, city
cowing, Resolve, defense phase, garrison movement/fire, escalating sorties,
retrieval, casualty ceiling, surrender, and extraction. Each player/defense
phase is a bounded logged command; animation events do not mutate state.

The POC rules are a behavioral reference, not code exempt from production
standards: freeze state, remove event draining and embedded RNG/config, typecheck
strictly, and separate presentation labels from rules facts.

Files: `edge/core/groundwar/assault.py`, `edge/core/rules.py`,
`edge/core/events.py`, codecs.
Tests: geometry; action economy; jump/AA; detection/jamming; Resolve directions;
civilian harm; broadcast gates; AI determinism; escalation; every outcome;
Hypothesis termination and bounds; reload at multiple tactical turns.
Commit `ground: GW-WP10 authoritative tactical assault`.

### GW-WP11 — Strategic assault settlement and consequences (XL)

Settle surrender, retrieval, casualty abort, and wipe under D2/D3/D7/D8.
Reconcile strategic defenders/attackers, persistent destroyed defenses, Resolve
recovery, colonists/civilians, citadel downgrade/build progress, treasury,
stores, ownership/protectorate/access, surviving ground defenders, and loot
atomically.

Reuse and extend existing invasion consequences: alliance standing, species
attitude and grudges, relation spillover, alignment, experience, corp war,
bounty/outlawry, and civilian-atrocity penalties. An unaligned inhabited world
must receive a real species consequence path; the old owner-only invasion did
not cover it.

Files: `edge/core/groundwar/settlement.py`, `edge/core/citadels.py`,
`edge/core/aliens.py`, `edge/core/corp.py`, `edge/core/rules.py`,
`edge/core/events.py`.
Tests: conservation and ownership properties; partial defender attrition;
survivor return; every owner kind; unaligned species; betrayal/permanent grudge;
civilian harm; failed assault; open citadel build; full siege replay golden.
Commit `ground: GW-WP11 assault settlement + consequence parity` — **GW-M3 done.**

### GW-WP12 — Live assault DTO, remote client, and Textual battle (XL)

Adapt the POC battle screen and platoon composer to DTO/client authority.
Viewport projection exposes only visible enemy units/structures, legal selected
actions, local stats, Resolve/retrieval/casualties, and event FX. The remote
attacker drives commands through the game's single-writer queue; defenders need
not be online.

Support keyboard and mouse drop placement, selection, move/jump/fire/missile,
broadcast, end turn, extraction confirmation, reconnect/resume, responsive
layouts, help, and accessibility copy. Orbit routes only assault-classified
worlds to the composer and states every siege blocker.

Files: DTO/session/client/wire layers, `edge/tui/screens/planet.py`, new/ported
ground battle screen, `edge/groundwar/app.py`, `edge/groundwar/widgets.py`.
Tests: fog and legal-action lockstep; local/remote parity; Pilot flows for win,
loss, extract, and reconnect; responsive snapshots; stale-command rejection.
Commit `ground: GW-WP12 live tactical assault UI`.

### GW-WP13 — Balance, bots, performance, and multiplayer contention (L)

Build deterministic survey and assault bots over the public client/service
surface. Run seed matrices across planet types, bands, populations, citadel
levels, ground-defense strengths, and loadouts. Tune search time, supply
pressure, victory
rates, casualties, suit costs, macro turn costs, rewards, and repeated-assault
recovery.

Profile terrain regeneration, state hashing, DTO viewport projection, command
log growth, remote latency, and reload time. Add safe runtime caches only where
measurement warrants them. Exercise two-player contention over discoveries,
world ownership, and simultaneous operations under the single writer.

Files: test/bot harnesses, config, balance notes.
Tests: statistical bounds with fixed seed sets; performance budgets; bot golden
logs; multiplayer contention/reconnect soak.
Commit `ground: GW-WP13 ground-operations balance + soak`.

### GW-WP14 — Legacy retirement, documentation, and exit gate (M/L)

Default the new paths on and remove or migrate:

- `Descend`, `Explore`, their events/codecs, and the old `SurfaceDTO` /
  `SurfaceScreen`;
- one-roll `InvadePlanet` and its direct TUI prompt;
- separate POC config loading and mutable duplicate production rules;
- feature flags and compatibility shims no longer needed.

Keep reusable POC launcher/play-test support pointed at production rules. Update
`DESIGN.md`, `GROUNDWAR_POC.md`, UI/keymap docs, scripting/service docs, wire
fixtures, screenshots, and the project work-completed summary. Run the full
quality suite and manually assess the exit criterion.

Files: repository-wide removal/update set.
Tests: no references to retired commands/views; full `pixi run check`; portable
save/rebuild; hosted-client smoke; manual exit-criterion record.
Commit `ground: GW-WP14 retire abstract surface/invasion paths` — **GW-M4 done.**

### GW-WP15 — Cloud City station-interior terrain and art (L)

Design and implement the D9 interior-map vocabulary without reusing planetary
biomes: pressure hulls, bulkheads, corridors, lifts/shafts, plazas/habitation,
engineering, security doors, cover, vacuum/fire/electrical hazards, defensive
emplacements, and a command/citadel core. Define a pure gameplay-feature grid
below core and a separate glyph/color/art resolver above it, preserving G5.

Generation derives scale and district count from `cloud_city_size`, population,
citadel/defense state, and seed. Every deployment zone, objective, and defender
must share a traversable component, accounting for locked doors and jump/vertical
movement rules. The standalone groundwar harness gains a Cloud City scenario for
art/rules iteration while the live feature gate remains off.

Files: new groundwar interior generator and art modules, `edge/art` station
interior assets, config, standalone harness.
Tests: deterministic generation; connectivity/reachability; feature/art registry
coverage; compact/standard/wide viewport snapshots; visual review sheet.
Commit `ground: GW-WP15 Cloud City station-interior maps + art`.

### GW-WP16 — Gated Cloud City assault integration (L/XL)

Adapt assault generation and tactics to the station interior: boarding/drop
entry, doors and corridors, interior hazards, Cloud City defensive structures,
Resolve objectives, retrieval/extraction, persistent damage, and D8 settlement.
Reuse recruits/suits, ground defenders, diplomacy, protectorate, conquest, wire,
DTO, and command rails; specialize only topology/art and rules that truly differ.

When parity, balance, remote play, and persistence tests pass, enable
`groundwar.cloud_city_assault_enabled`. Below-friendly inhabited Cloud Cities
then route to assault; bare jovians and friendly/owned Cloud Cities remain
orbital-only under D9.

Files: core groundwar access/assault/settlement, DTO/session/client/wire, planet
and battle TUI, config and docs.
Tests: gate-off orbital behavior; gate-on access; assault win/fail/extract;
persistent interior damage; protectorate/conquest; reload and remote-client
goldens; fighter non-involvement.
Commit `ground: GW-WP16 Cloud City interior assaults` — **GW-M5 done.**

## Verification matrix

| Concern | Required evidence |
|---|---|
| Determinism | Same seed + ground command log → identical hash, including mid-operation reload |
| Discovery integrity | One ground site ↔ one real discovery; sensor-hidden sites leak nothing; dig atomically yields artifact+lore |
| Economy | Troop/suit/loadout costs and rewards conserve or use explicit sinks/faucets |
| Strategic reconciliation | Tactical casualties/defenses settle exactly once into planet/ship/player state |
| Diplomacy | Alliance, species, grudge, corp-war, alignment, and civilian consequences covered |
| Safety | Core/non-landable/defended gates rejected in reducers, not merely hidden in UI |
| Multiplayer | Local and remote parity; contention serialized; reconnect resumes exact operation |
| UI | Keyboard/mouse; compact/standard/wide; fog-correct viewport; destructive confirms |
| Performance | Bounded generation, projection, hash, log, and reload costs at configured max map |

## Principal risks

1. **D3 force-model expansion.** Persistent troops and suits touch more systems
   than surveying and may dominate the schedule. GW-WP08 is isolated so the
   survey milestone can ship first.
2. **Oversized hashed state/logs.** Storing full art/terrain or emitting one event
   per cell would bloat hashes and wire traffic. Preserve the static/dynamic
   split and viewport DTO.
3. **Sensor leaks.** The POC assumes every generated site is a known orbital
   contact; the live discovery system does not. G7 receives dedicated negative
   tests at rule and DTO levels.
4. **Strategic/tactical mismatch.** POC difficulty/garrison counts are invented,
   while D7 removes fighters from invasion entirely. D11's persistent ground
   defense must land before assault generation or failed assaults will have no
   honest strategic aftermath.
5. **Duplicate siege defenses.** POC citadel levels generate a gun while the live
   ladder requires that gun already silenced. G12 makes surviving defense state
   an explicit generation input.
6. **Unaligned-world sovereignty.** Below-friendly inhabitants can exist on
   `owner=none`; surrender must create the D2 protectorate without erasing
   species identity, and later ownership must be an explicit action rather than
   an accidental conquest side effect.
7. **Cloud City semantics and art.** Walking on a bare gas giant is invalid and
   terrestrial terrain cannot depict a station interior. D9 keeps the gate off
   until GW-WP15–16 supply dedicated gameplay topology, new art, and integration.
8. **Remote command volume.** Tactical play produces far more commands than the
   abstract reducers. GW-WP13 measures log/wire/reload behavior before retirement.
9. **An empty target set.** The big bang seeds no inhabitants, population, or
   planetary holdings, so today *no generated world routes to `Assault`* and the
   whole of GW-M3 could be built and "passing" against hand-built test states
   only. GW-WP09-PRE seeds the inhabited universe and adds a generation-time
   invariant that a minimum target set exists, so the milestone is verified
   against real seeds rather than fixtures.

## Definition of done

- D1–D15 are resolved and recorded in both this plan and authoritative DESIGN.
- GW-WP01–16 (with GW-WP09-PRE) acceptance tests pass.
- A **generated** universe contains inhabited worlds that route to survey and to
  assault; neither path is reachable only through hand-built state.
- `ruff`, strict `mypy` production layers, pytest/property tests, codec fixtures,
  and Textual Pilot/snapshots are green.
- Survey and assault work through local and remote clients.
- A save can reload at any operation phase without state drift.
- Abstract surface exploration and one-roll planetary invasion are unreachable
  and removed.
- `GROUNDWAR_POC.md` accurately describes the retained standalone harness and
  the production subsystem it exercises.
