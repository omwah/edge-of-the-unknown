# Ground Operations — Survey and Planetary Assault Integration

> Companion to `DESIGN.md`, `GROUNDWAR_POC.md`, `PHASE5_4_PLAN.md`, and
> `SEAMS_PLAN.md`. `DESIGN.md` remains the authoritative *what*; this document
> is the *how and in what order* for replacing the shipped abstract surface and
> invasion paths with the `edge.groundwar` survey and tactical-assault systems.
> Where implementation reality requires a design change, update `DESIGN.md` in
> the same work package and record the reason here.
>
> **Status: COMPLETE — all of GW-WP01–21 shipped, GW-M1 through GW-M5 all
> closed (July 2026). `groundwar.cloud_city_assault_enabled` is on in the
> production default. GW-WP20 closed the protectorate/annexation TUI gap and
> GW-WP21 the terrain band-colour gap; GW-WP21-FU1 then settled
> `_CONTRAST_TRIGGER` at 0.26 on a human read of the rendered comparison,
> closing GW-WP07-FU1's last polish item. **The suite is fully green.** One
> deliberately deferred follow-up remains, flagged not silent: GW-WP13's /
> GW-WP16's balance tuning (garrison counts, defense density, emplacement
> geometry for both terrestrial and Cloud City assaults), which needs a human
> read of the bot seed-matrix runs rather than more harness.**

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
control without misusing `owner=none` or erasing the native people's
`Planet.population` entry (the per-species-count ledger the GW-WP09-PRE follow-up
replaced the single `inhabited_by_species_id` field with, so a colonized or
protectorate-claimed world can carry the player's own people *alongside* the
native one instead of overwriting them).

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

- **inhabited**: a non-empty `Planet.population` (live colonists and/or a native
  people — GW-WP09-PRE follow-up), or an inhabited Cloud City under D9;
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

**Known gaps, deliberately deferred:** ~~`_feature_colors` matches the *first* band with a
given feature name, so where a biome repeats one (`terrestrial_cold` ice, jovian,
asteroid_belt) the later band's colours are unreachable — fixing it needs a band index on
`GroundCellDTO`.~~ **Closed by GW-WP21** (below), which also corrects this note on two
counts: only `terrestrial_cold` was actually affected, and the fix is unique band names
rather than a band index. ~~And `_CONTRAST_TRIGGER` (0.20, `edge/art/terrain.py`) leaves
mountain/dust/snow honestly dim at ~0.25; raising it is shared with the world-art
screens.~~ **Closed by GW-WP21-FU1** — the trigger is 0.26.

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

### GW-WP09-PRE — NPC-inhabited worlds at big bang (L) — SHIPPED

**Status:** shipped July 2026. New `edge/bigbang/inhabitants.py` runs after
`populate_species` (it needs the placed cast *and* the carved home clusters) on its own
salted sub-RNG, so it shifts neither the §7 discovery draw nor species placement. It
seeds the three populations D2/§6.3 imply — the governor's **Core** worlds, a bloc's
**home-cluster** worlds, and **unaligned** worlds that keep `owner=none` beside a
species id — with population drawn as a fraction of each world's own capacity, plus
citadel level / gun integrity / treasury / stores. A fresh seed now reports through the
inspector: *195 planets, 70 inhabited, 1.4M people, 18 assaultable / 51 friendly*.

**The floor is enforced by construction, not by retrying.** The first cut checked a
minimum in the validator and regenerated on failure — and seed 7 then failed all 16
attempts. The shortage is in the **species draw**, not the planet draw: that cast held
61 species of which *zero* were below the amity threshold, and redrawing kept producing
the same friendly skew (the roster skews friendly by design, §6). Two corrections
followed, and both are load-bearing:

1. **The wary pool spans the whole cast, not just unaligned species.** An unaligned
   people is preferred for an unowned world (the cleanest protectorate subject), but a
   bloc's kind living beyond its cluster on nobody's world is equally coherent — and
   necessary, since a cast can hold no wary *unaligned* species at all.
2. **A constructive top-up** settles wary peoples onto free frontier worlds, deepest
   band first, until the floor is met — the same "enforced per seed rather than in
   expectation" approach `_finalize_planets` already uses for the monotone unowned
   fraction.

**The floor is capped by supply** (`target_floors`, read by both the top-up and the
validator so they cannot disagree). A configured floor is a target for a full-size
universe, not a law of nature: a 60-sector test universe has 14 planets, 2 free
unowned worlds and a wholly peaceable cast, and demanding six targets of it made
generation impossible (469 test failures). The invariant now reads "field as many
targets as you can, up to the configured floor", and a peaceable universe is valid
rather than rejected.

**Epoch:** hashed `Planet` state changes, but `config_version` stays 12 — the
per-milestone epoch policy defers the single bump to GW-WP11.

Files (as shipped): `edge/bigbang/inhabitants.py` (new), `edge/bigbang/generator.py`
(pipeline step + `--stats` counts), `edge/bigbang/validate.py`
(`_check_ground_targets`), `edge/core/config.py` (`InhabitantsConfig`),
`config/default.yaml`.
Tests: `tests/test_bigbang_inhabitants.py` (15) — including
`test_a_real_generated_world_routes_to_assault`, which drives the production
`ground_access` classifier against a generated universe and is **the case that could
not be written before this WP** without hand-building state.

*Deviation from the WP's own file list:* `edge/core/planets.py` needed no change (the
belt normalizer already clears inhabitants, and belts are skipped by the capacity
gate), and no golden/wire fixtures moved (no command, event, or DTO changed).

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

### GW-WP09 — Persistent ground defense and assault generation (XL) — SHIPPED

**Status:** shipped July 2026. The D11 persistent planetary ground-defense model
lands as a finite, casualty-reducible garrison — `Planet.garrison_infantry` /
`garrison_armor` — fed by three sources: big-bang seeding (`edge/bigbang/
inhabitants.py`), ownership-independent militia recovery, and dedicated
colonist-allocation training, all in `edge/core/planets.py`. The irreversible
D15 reinforcement rail is the new `ReinforceGarrison` command (recruits+suits
aboard ship → local garrison, one-way as the plan specified), alongside a new
`TransferFighters` command that moves `Planet.fighters` between planet, ship,
and sector deployment — closing a gap the plan named explicitly, and kept
strictly outside the ground-defense calculation under D7 (fighters have no
effect on assault odds).

A new `BeginAssault` reducer opens an `AssaultOperation`: it derives difficulty
from live state — planet type, population, band, the D11 garrison, citadel
level, surviving gun, owner/species — via the new `GwAssaultDifficulty` config
block, which supersedes the POC's menu-selected `GwDifficulty` for production
(that type stays as-is, unused, for the standalone `edge.groundwar` app).
Battlefield/city/structure generation is **ported** from the edge-groundwar POC
into frozen pure models; the POC's garrison model itself is **not** ported,
since its infinite-wave garrison is incompatible with D11's finite headcount —
this WP replaces it rather than reusing it. `BeginAssault` enforces the orbital
ladder (never stamps a razed base or silenced gun), applies the D9 terrestrial-
versus-Cloud-City gate, and snapshots/reserves the committed garrison so a
second concurrent `BeginAssault` cannot spend it twice — the operation only
opens; nothing on the planet mutates until GW-WP11 settles the outcome.

The planet screen gains a garrison readout and a reinforce affordance.

**Epoch:** `config_version` stays 12 (per-milestone batching defers the single
bump to GW-WP11), `WIRE_VERSION` 30→31 for `PlanetDTO` garrison fields plus the
`TransferFighters` / `ReinforceGarrison` / `BeginAssault` commands and events.

Files (as shipped): `edge/bigbang/inhabitants.py`, `edge/core/config.py`,
`edge/core/dto.py`, `edge/core/events.py`, `edge/core/groundwar/access.py`,
`edge/core/groundwar/assault.py` (new), `edge/core/groundwar/force.py`,
`edge/core/groundwar/models.py`, `edge/core/models.py`, `edge/core/planets.py`,
`edge/core/rules.py`, `edge/engine/cron.py`, `edge/server/session.py`,
`edge/server/wire.py`, `edge/store/codec.py`, `edge/tui/screens/planet.py`,
`config/groundwar_default.yaml`.
Tests: `tests/test_groundwar_assault.py` (new, 17) plus additions to
`tests/test_groundwar_access.py`, `tests/test_planets.py`, `tests/test_rules.py`,
`tests/test_bigbang_inhabitants.py`, `tests/test_groundwar_force.py`,
`tests/test_codec.py`, `tests/test_aliens.py`, `tests/test_cli.py`,
`tests/test_tui_flow.py`, and a snapshot refresh — seeded maps, live-state
difficulty scaling, city reachability, no duplicate gun, base/gun/shield/Core
rejection, garrison-reserve conservation, fighters excluded from assault odds.
Full suite green: 3106 passed, 80 snapshots; lint and typecheck clean.
Commit `ground: GW-WP09 assault maps from live worlds` (821bc0c).

### GW-WP10 — Tactical assault actions and planetary AI (XL) — SHIPPED

**Status:** shipped July 2026. The edge-groundwar POC's tactical battle engine —
drop, movement/jump, cover/LOS, firing, AA reactions, detection/jamming,
emplacement fire, garrison AI, escalating sorties, Resolve, broadcast/surrender,
retrieval clock, casualty ceiling — is ported into authoritative, replayable
core rules over frozen `AssaultOperation` state, closing the gap GW-WP09's
battlefield generation left open. `edge/core/groundwar/models.py` gains
`AssaultTrooper` / `AssaultGarrisonUnit` and the live tactical fields on
`AssaultOperation` (platoon, garrison units, a `structure_hp` overlay,
broadcast/cowed city sets, the finite garrison reserve pool, `next_unit_id`,
`initial_strength`).

`edge/core/groundwar/assault.py` carries the ported engine over a transient,
private scratch `_Battle` rebuilt fresh from frozen state on every call —
never hashed, never crossing a function boundary — so the POC's function
bodies carry over almost verbatim behind six pure entry points
(`assault_drop`/`move`/`jump`/`fire`/`broadcast`/`end_turn`). Garrison
deployment is **pre-placed + sortie remainder** (an interview decision this
WP resolved): a `preplaced_frac` share of the world's finite garrison stations
in cities at drop, and the rest feeds escalating sorties capped per-kind by
the shrinking remaining pool — replacing the POC's infinite supply. Battle-time
movement/cover use new scratch-aware cost functions distinct from the static
generation-time ones, since a destroyed wall must become passable rubble.

New commands land in `edge/core/rules.py`: `GroundDrop`, `GroundJump`,
`GroundFire`, `GroundBroadcast`, `EndGroundTurn`; `GroundMove` now branches on
operation kind to cover the assault trooper's single-action move alongside the
existing survey march. D4/D12 macro-turn quanta apply to assaults too —
`EndGroundTurn` is the only turn-advancing action, keeping each player/defense
phase a bounded logged command with no state mutation from animation events.
The POC rules were treated as a behavioral reference, not code exempt from
production standards: state is frozen, event draining and embedded RNG/config
are gone, and typing is strict.

**Epoch:** no `config_version`/`WIRE_VERSION` bump — GW-M3's single epoch stays
deferred to GW-WP11, matching the GW-WP09-PRE and GW-WP09 precedent.

Files (as shipped): `edge/core/groundwar/assault.py`,
`edge/core/groundwar/models.py`, `edge/core/rules.py`, `edge/core/config.py`
(`GwGarrison.preplaced_frac`, `GwPressure` macro-turn fields, `GwResolve.cap`),
`edge/core/events.py` (five new structured events: `GroundAssaultDropped` /
`Jumped` / `Fired` / `BroadcastMade` / `TurnEnded`), `edge/store/codec.py`,
`config/groundwar_default.yaml`.
Tests: `tests/test_groundwar_assault_actions.py` (new, 27) — destroyed-wall
passability, action economy, jump/missile ammo, Resolve in both directions,
civilian atrocity, broadcast gating, sortie-pool conservation, casualty
ceiling/wipe/surrender/retrieval outcomes, a Hypothesis bounds property, plus
reducer-level drop/move/fire/jump/extract/replay coverage — and additions to
`tests/test_codec.py`.
Commit `ground: GW-WP10 authoritative tactical assault` (fdb1eb9).

### GW-WP11 — Strategic assault settlement and consequences (XL) — SHIPPED

**Status:** shipped July 2026; GW-M3 complete. The new pure
`edge/core/groundwar/settlement.py` reconciles all POC-derived tactical endings
(pre-drop abort, retrieval, casualty abort, wipe, and surrender) into one atomic
strategic result. It reuses the authoritative `AssaultOperation` overlay and
existing `groundwar.force.apply_casualties`: surviving recruits, suits, and
unspent committed missiles return to the ship, while dead troopers remove both
their recruit and suit and defender casualties reduce the finite planetary
garrison. Destroyed structures persist by kind as rubble, Resolve persists and
recovers once per daily planet tick, and destroyed civilian buildings reduce
the original species-keyed population without relabelling its inhabitants.

Owned-world surrender reuses and extends the citadel conquest rail: ownership
flips to the attacking player/corporation, treasury becomes loot, surviving
ground defenders remain, the citadel downgrades and its gun is silenced, while
stores and an open citadel build survive. Failed assaults persist casualties,
damage, and Resolve but never flip control. An unaligned inhabited surrender
instead retains `owner=none`, its native population/stores/treasury, and creates
a controller-keyed protectorate. Protectorate administration grants access,
garrison/supply management, and a config-driven share of daily production in a
separate ledger; annexation is an explicit logged command gated by minimum age
and recovered Resolve, then merges the controller share into sovereign stores.

The reducer routes ground violence through the existing alliance-standing,
species attitude/grudge, inter-species spillover, alignment/experience/bounty,
and corp-war consequence rails. This gives unaligned inhabited worlds the same
real species response as owned worlds; `never_forgets` / permanent-betrayal
species form a permanent grudge. Civilian destruction adds an independent
alignment penalty, while annexation carries a stronger species and alignment
cost. New settlement/protectorate events and `AnnexProtectorate` round-trip
through durable and remote codecs; session projections label and authorize
limited protectorate control without presenting it as sovereign ownership.

**Epoch:** GW-M3's batched `config_version` moves 12→13. The command/event wire
moves `WIRE_VERSION` 31→32 and refreshes its fingerprint/envelope fixtures.

Files (as shipped): `edge/core/groundwar/settlement.py`,
`edge/core/groundwar/{assault,access,models}.py`, `edge/core/{models,config,
citadels,aliens,corp,planets,rules,events}.py`, `edge/engine/cron.py`,
`edge/server/{session,wire}.py`, `edge/store/codec.py`,
`config/{default,groundwar_default}.yaml`, and wire fixtures.
Tests: `tests/test_groundwar_settlement.py` (new, 10 tests including a Hypothesis
conservation property) plus codec/config coverage — survivor and equipment
return, partial defender attrition, every former owner kind, unaligned native
protectorates, permanent grudges, civilian harm, failed assault persistence,
open citadel builds, annex gates, daily Resolve recovery, and deterministic full
siege settlement replay. Full suite green: 3176 passed, 80 snapshots; lint clean.
Commit `ground: GW-WP11 assault settlement + consequence parity` — **GW-M3 done.**

### GW-WP12 — Live assault DTO, remote client, and Textual battle (XL) — **SHIPPED**

**Status:** shipped July 22, 2026 in commit `758f764`
(`ground: GW-WP12 add fog-safe remote tactical assault UI`).

**Implementation (as shipped):**

- Added `AssaultExpeditionDTO` and its cell, trooper, garrison, and city DTOs.
  The server regenerates the frozen battlefield and returns only the requested
  viewport; no operation seed crosses the client boundary.
- Added a pure tactical projection over the production assault rules. It computes
  squad line-of-sight, visible enemy units and structures, visible-source threat
  overlays, and the exact legal move, jump, fire, missile, and broadcast choices
  for the selected trooper. The TUI does not reimplement action legality.
- Extended `GameService`, `GameClient`, `LocalClient`, `RemoteClient`, and the
  server protocol so embedded and hosted attackers consume the same assault view.
  Mutations continue through the existing authoritative single-writer command
  queue; planetary defenders remain server-controlled and need not be online.
- Adapted the POC platoon composer and battle presentation into the production
  `GroundAssaultScreen`. Shared structure art, rubble, threat colors, and event
  flash styles now live in `edge/groundwar/widgets.py` and are reused by the POC.
- Implemented keyboard and mouse capsule placement/cursor control, ready-trooper
  selection, move/jump/fire/missile/broadcast/end-turn actions, radar overlays,
  event log and combat flashes, confirmed extraction, surrender/wipe/retrieval
  outcome display and settlement, help/accessibility copy, and compact/standard/
  wide layouts.
- Added operation resume to `GameScreen`: a loaded or reconnected session opens
  the correct survey or assault screen and restores an actionable trooper
  selection rather than stranding the player in orbit.
- Completed the orbit route in `PlanetScreen`. Only a droppable
  assault-classified world opens the composer; blocked worlds list every standing
  orbital-base/citadel-gun/siege-shield rung from `PlanetDTO.ground_blockers`.
- Bumped `WIRE_VERSION` 32→33 and refreshed the wire fingerprint and envelope
  fixtures for the new DTO shapes and complete siege-blocker projection.

Files (as shipped): `edge/core/{dto.py,groundwar/assault.py}`,
`edge/server/{client,protocol,service,session,wire}.py`,
`edge/tui/screens/{game,ground_assault,planet}.py`,
`edge/groundwar/{app,mapgen,widgets}.py`, wire fixtures, responsive SVG
snapshots, and `tests/{test_groundwar_access,test_groundwar_assault_view}.py`.

Tests (as shipped): fog/visibility and legal-action lockstep; cropped viewport
and seed secrecy; local/remote/wire parity; stale actor and operation rejection;
complete siege-blocker projection; Textual Pilot move, surrender, wipe,
confirmed extract, and reconnect flows; all layout tiers; and three responsive
SVG snapshots. Full quality gate green: 3,191 tests and 83 snapshots; Ruff and
strict mypy clean.

Commit `758f764` — **GW-WP12 done.**

### GW-WP12-FU1 — Post-playtest fixes and known gaps (M)

**Status:** shipped July 2026 (not yet committed). A live playtest of the assault
screen surfaced and fixed a chain of bugs — structures wrongly LOS-gated as a single
class rather than split passive/active (a city outside line of sight rendered as bare
terrain), zero log narration for tactical combat events, silent action rejection, no
win/loss notification, and `AssaultMapView` rebuilding its whole grid every keystroke
instead of caching like survey's map view does. `edge/tui/screens/_ground_shared.py`
gained a `CroppedMapView` base widget (both map views now share one cache-and-restyle
skeleton) and a `LandingAnimationMixin` (assault's capsule drop now plays the same
descent animation as survey's touchdown, generalized to several simultaneous
touchdown points). Full suite green throughout, `pixi run lint` clean.

**Known gaps, surfaced but deliberately deferred:**

- ~~**No shared terrain identity between survey and assault.**~~ **Closed by GW-WP19**
  (below). The original note read: The expectation is that
  returning to a world in survey mode after winning an assault there would show the
  same map with the battle's damage persisted. It doesn't: `GroundOperation`'s own
  DESIGN.md entry says static terrain "is regenerated from identity," and
  `generate_survey` (biome-based) and `generate_assault_map` (city/structure-based)
  are structurally independent generators — neither knows about the other's output,
  and `Planet` persists no rubble/city state beyond the life of the
  `AssaultOperation` that created it. Fixing this needs a shared world-terrain-
  identity model plus persisted structure/rubble state on `Planet` — sized like its
  own work package, not a same-session fix.
- ~~**Protectorate/annexation has no TUI surface.**~~ **Closed by GW-WP20** (below).
  The original note read: `AnnexProtectorate` exists in
  `edge/core/rules.py` (GW-WP11) and `session._owner_label` already renders
  `"protectorate (yours)"`/`"protectorate"` as plain text, but `PlanetDTO` carries no
  protectorate/garrison-share/annex-eligibility fields and no screen offers an Annex
  action, administers a production share, or manages a protectorate's garrison — the
  rights DESIGN.md §4.2 describes ("The controller alone may administer production
  share, manage and reinforce ground defense, and later seek annexation") are
  implemented in core but never reach a player.

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

**Status: infrastructure landed 2026-07-23; balance tuning deliberately deferred.**
Shipped: deterministic `edge/bot/scripts/surveyor.py`/`assaulter.py` (drive a survey
or tactical assault end to end over `ServiceProtocol`, reading trusted raw state like
`edge.bot` already does elsewhere); `tests/test_groundwar_bots.py` (per-seed
determinism replay for both bot kinds — the crown-jewel property, since a ground op
draws from the shared `state.rng` and is exactly the class of bug that bit GW-WP09 —
plus loose, non-degenerate aggregate outcome bounds, deliberately not a tight
win-rate assertion a crude bot could never honor); `tests/test_groundwar_multiplayer.py`
(extends the WP69 `BotSwarm` pattern: two survey bots never double-claim a discovery
under real concurrent pressure — G8 stress-tested rather than single-player-only; two
assault bots on the *same* world replay deterministically and never drive its garrison
negative); `tests/test_groundwar_performance.py` (structural, not wall-clock, budgets:
a live survey/assault operation checkpoints and reloads by replaying only the log tail,
matching the `perf: bound save loading with state checkpoints` contract; `ground_operation_view`
stays a viewport crop regardless of the underlying map's full size).

**Not done, and not a silent gap**: actual numeric tuning (search time, supply
pressure, victory rates, casualties, suit/ordnance costs, macro-turn costs, rewards,
repeated-assault recovery) is a subjective balance call, not something the harness
above can derive on its own — it needs a human read of what the bots' seed-matrix runs
actually show. Also open: remote-latency profiling and a reconnect-specific soak (the
in-process `BotSwarm` proves single-writer determinism under concurrent load, not
socket reconnection); safe runtime caches, only if a future measurement pass finds one
warranted (none did here). Revisit as a WP13 follow-up once there's a balance verdict
to act on.

### GW-WP13-FU1 — POC parity fixes: narration, settlement hints, drop hazard (M) — SHIPPED

A pre-WP14 feature-parity audit of survey/assault against the `edge-groundwar` POC
(mechanics, help text, logging) found production a faithful, mostly-superset port,
with four gaps a human interview resolved:

- **Narration**: `SurveyActionResult`'s computed-but-discarded `logs` field is
  retired; `SurveyDug`/`SurveyTalked` gained typed `resupply`/`already_dug` fields
  so the log distinguishes a hit, a dry hole, and a free re-dig, and shows resupply
  amounts. `assault_fire`/`assault_jump`/`assault_broadcast` now also return their
  full battle-event tuple (mirroring `assault_end_turn`'s existing `(new_op, log)`
  shape); the reducers forward the Resolve-delta/KIA lines their own summary events
  don't narrate as `GroundDefenseFireLogged`, generalized beyond its original
  `EndGroundTurn`-only scope.
- **Per-town settlement hint cap restored** (`hinted_settlement_ids` on
  `SurveyOperation`/`SurveyProgress`, persisting across descents like site hints
  already did) — a survey-wide-only cap had let one town dispense every remaining
  hint if talked to repeatedly.
- **Limited drop-zone hazard visualization**: `tactical_projection` pre-drop paints
  a coarse, fixed-radius AA hazard zone around each city's center (from
  `defenses.aa.range`, not any actual battery's position) — some landing-danger
  read, without reintroducing the exact-position leak GW-WP12 removed.
- **Bundled polish**: `AssaultExpeditionDTO.casualty_ceiling` (wire v35, sidebar
  shows the abort threshold), help text covers jamming/sortie-escalation/doctrine-
  abort, and `GROUNDWAR_POC.md` documents the two previously-undocumented behavior
  changes (march no longer auto-halts on a sighted clue; scanner overlay defaults
  off) plus the new hazard-visualization design.

Files: `edge/core/groundwar/{survey,assault,models}.py`, `edge/core/events.py`,
`edge/core/rules.py`, `edge/core/dto.py`, `edge/server/{session,wire}.py`,
`edge/tui/screens/ground_assault.py`, `docs/GROUNDWAR_POC.md`.
Tests: per-town hint cap (single-descent + checkpoint round-trip), pre-drop hazard
radius (exact-shape assertion vs. real battery positions), narration coverage per
fixed reducer; full `pixi run check` green (3137 passed, one pre-existing unrelated
snapshot failure confirmed present on `main` beforehand).
Commit `ground: GW-WP13-FU1 POC parity fixes before legacy retirement`.

### GW-WP14 — Legacy retirement, documentation, and exit gate (M/L)

Default the new paths on and remove or migrate:

- `Descend`, `Explore`, their events/codecs, and the old `SurfaceDTO` /
  `SurfaceScreen`;
- one-roll `InvadePlanet` and its direct TUI prompt;
- separate POC config loading and mutable duplicate production rules;
- feature flags and compatibility shims no longer needed;
- the legacy planet-surface-site art `SurfaceScreen` alone rendered: all four
  `ruins`/`artifact`/`ancient_tech`/`crashed_ship` generators in
  `edge/art/discovery.py` (and their `DISCOVERY_GRAMMAR`/`available_subtypes`
  entries, plus the surface-scene scaffold only they used), superseded by the
  GroundWar expedition field-sketch art (`edge/groundwar/findart.py`,
  `edge/core/surface_finds.py`). `crashed_ship` gets a sixth Field Finds
  identity ("hulk," with new field-sketch art in `findart.py`) rather than
  being kept as a fallback — the interview decision that closed the gap the
  WP07 migration note flagged ("crashed ships retain their existing generator
  because the POC has no equivalent"). `edge/tui/widgets.py`'s sector-scene
  `_paint_discovery` only ever hits the five free-floating kinds
  (`nebula`/`black_hole`/`wormhole`/`wreck`/`entity`) per DESIGN §7, since
  surface-site kinds never appear as sector-space discoveries. The
  `DiscoveryKind` enum values themselves stay — they remain the authoritative
  mechanical category — only the old presentation layer goes.

Keep reusable POC launcher/play-test support pointed at production rules. Update
`DESIGN.md`, `GROUNDWAR_POC.md`, UI/keymap docs, scripting/service docs, wire
fixtures, screenshots, and the project work-completed summary. Run the full
quality suite and manually assess the exit criterion.

Files: repository-wide removal/update set.
Tests: no references to retired commands/views; full `pixi run check`; portable
save/rebuild; hosted-client smoke; manual exit-criterion record.
Commit `ground: GW-WP14 retire abstract surface/invasion paths` — **GW-M4 done.**

**Status: SHIPPED 2026-07-23.** Removed `Descend`/`Explore` (rules + `Descended`/
`SiteExplored` events + `SurfaceDTO`/`SurfaceSite`/`surface_view` read method/RPC
whitelist entry), one-roll `InvadePlanet` (rules + `citadels.resolve_invasion`/
`citadel_defense_mult`/`InvasionOutcome`/`conquer` + `InvasionRepulsed` event +
`PlanetDTO.can_invade`/`invade_blocker`/`ship_fighters` + the `[I]` PlanetScreen
prompt), `edge/tui/screens/surface.py`, `edge/server/terrain.py`, and the dead
`descent_turn_cost`/`explore_turn_cost`/`surface_terrain_height` config fields
(kept `surface_site_chance`/`surface_sites_max`/`surface_kinds`/
`surface_hidden_min_rank` — still read by `edge/bigbang/discoveries.py`
generation, unrelated to the retired commands). `PlanetInvaded` (the conquest
event) and `is_landable`/`has_gun`/`siege_shielded` stayed — confirmed shared
with the GW-WP11 tactical-assault settlement path and `ground_access`. All four
legacy surface-site art generators retired per the art-layer note above;
`edge/core/surface_finds.py`'s find-modal fallback in `ground_expedition.py`
collapsed to the single always-mapped path now that every surface `DiscoveryKind`
has a Field Finds identity. `WIRE_VERSION` 35→36 (RPC method + codec surface
changed); `config_version` unchanged (no `AUTHORITATIVE_STATE_FIELDS`-relevant
shape touched by this WP). Two gaps found outside the plan's original file list
during a repo-wide sweep and fixed in the same pass: `edge/bot/llm/actions.py`
(the dev-only LLM pilot) still called `Descend`/`Explore` — its vocabulary
entries and system-prompt line describing them were removed; `tests/test_discovery_art.py`
and `tests/test_surface_finds.py` asserted the pre-redirect `crashed_ship → None`
behavior and needed updating for the "hulk" mapping. `docs/ui/shots/surface.svg`
and its five snapshot baselines deleted; `test_planet_sizes[wide]`'s baseline
regenerated (the `[I] Invade` footer entry is gone from the wide-tier render).
`test_options_modal` remains failing — confirmed pre-existing on a clean stash
(unrelated to this WP, not chased). Full suite green otherwise.

**POC retarget shipped in the same session** (`ground: GW-WP14 retarget groundwar
POC onto production rules`, closing GW-M4). Deleted the standalone-only engine
outright — `edge/groundwar/rules.py`, `model.py`, `mapgen.py`, `expedition.py`,
`expedition_ui.py` — rather than porting it to a DTO-driven render layer as
originally scoped: `GroundAssaultScreen`/`GroundExpeditionScreen` turned out to have
no `EdgeApp`-specific dependencies (just `self.app.push_screen`/`pop_screen`/
`notify`, which any Textual `App` provides), so `GroundwarApp` now **subclasses
`EdgeApp`** directly (`edge/tui/app.py` gained one small seam for this,
`_initial_screen()`, so a subclass can push a different first screen than
`MainMenuScreen` without duplicating `on_mount`'s theme/ticker setup) and
`SetupScreen` hands off to the *actual* production screens instead of reimplementing
their rendering. New `edge/groundwar/harness.py` builds a throwaway single-sector,
single-planet `UniverseState` (mirroring `tests/test_groundwar_access.py`'s
`_state`/`_planet` pattern) — an assault builder that sizes a droppable below-
friendly world via `edge.core.groundwar.assault.seed_garrison` and pre-loads the
ship's `recruits`/`suits` from the composed loadout, and a survey builder that
salts real `Discovery` records onto an owned/unowned world (survey sites must each
name a real discovery id, G6 — a bare planet has nothing to find). `SetupScreen`
builds a harness state, constructs a throwaway `GameService`/`SqliteRepository
(":memory:")`/`LocalClient`, dispatches `BeginAssault`/`BeginSurvey`, and pushes
`GroundAssaultScreen`/`GroundExpeditionScreen` — the identical screens
`PlanetScreen.action_descend` pushes in the live game. The standalone-only
`GwDifficulty`/`config.groundwar.difficulties` preset table (already documented as
"superseded by live state in production") was retired alongside it — the setup
screen's difficulty picker now feeds `habitability_cap`/`citadel_level` presets
straight into the same live-state derivation
(`edge.core.groundwar.assault.derive_difficulty`) production itself uses, rather
than a parallel table nothing else read. Verified end-to-end via a Textual `Pilot`
harness (drop a composed platoon → land on `GroundAssaultScreen`; land on a friendly
world → arrive on `GroundExpeditionScreen`; `?` help and Esc-back-with-confirm both
route correctly) plus the full `tests/test_groundwar_*.py` suite (200 passed,
unaffected — it already exercised production rules directly, never the POC's own
engine) and the full quality suite. `edge/groundwar/findart.py`/`widgets.py`
untouched throughout (confirmed live production dependencies). `docs/
GROUNDWAR_POC.md` rewritten to describe the retargeted shape.

### GW-WP15 — Cloud City station-interior terrain and art (L) — SHIPPED

**Status: shipped July 2026.** Interview decisions this session (recorded in
DESIGN.md's Cloud City section): a **flat single-level** map (lifts are
same-grid teleport links, no z-axis); a new **wall-aware** structural art
renderer for walls/doors specifically (planet terrain's per-cell glyph-pool
style is kept for every other feature); hazards (`vacuum`/`fire`/`electrical`)
are **inert data tags** this WP, no effects wired; and — diverging deliberately
from the planet `move_cost: 0 ⇒ jump clears it` precedent — **jump-jets never
bypass a wall or door on a station**, while a **`security_door` is destructible**
(breach cost is GW-WP16) and may legally be the sole connector between two
areas, whereas a plain `bulkhead` never may.

New pure `edge/core/groundwar/interior.py`: `generate_interior` BSP-partitions
the map into `districts_base + districts_per_size × (size − 1)` rooms
(`groundwar.cloud_city` config), carves `corridor` connections through a
`bulkhead` ring (a `locked_door_frac` becoming `security_door` instead),
drops `lift_pairs` teleport links, and sprinkles hazard/`cover_strut` cells.
The connectivity invariant (every deployment zone/objective/defender slot in
one component, doors passable, bulkhead never the sole connector) is checked
by BFS with bounded retries (mirrors `edge.bigbang.generator`'s idiom),
raising `InteriorGenerationError` on repeated failure. District count derives
from `cloud_city_size` and the operation seed only — population/citadel-state
scaling (as the original text sketched) is deferred; nothing yet reads
population into interior generation. New `edge/art/interior.py`: per-cell
glyph pools for floor features (reusing `edge.art.terrain`'s style), a
16-case wall-junction box-drawing table for `bulkhead`/`security_door`, and a
shared `LEGEND`. New terrain classes slot into the existing
`GroundwarConfig.terrain: dict[str, GwTerrain]` mapping unchanged — no schema
growth beyond the new `GwCloudCity` model.

The standalone `edge-groundwar` harness gained a **read-only preview mode**
(`edge/groundwar/interior_preview.py`, `CloudCityPreviewScreen`) reachable from
`SetupScreen`'s Mode cycle — it calls the generator/art directly with no
command/DTO/`GameService` involved (there is nothing to drive yet). The live
gate (`groundwar.cloud_city_assault_enabled`) stays off; `ground_access` still
routes every Cloud City `OrbitalOnly`.

Files: `edge/core/groundwar/interior.py`, `edge/art/interior.py`,
`edge/groundwar/interior_preview.py`, `edge/groundwar/app.py`,
`edge/core/config.py`, `config/groundwar_default.yaml`.
Tests: `tests/test_groundwar_interior.py` — determinism; many-seed connectivity
across every city size (1..`planets.cloud_city_max_size`); independent
(non-reused) reachability re-check; config terrain-coverage validation
(positive and negative); art/glyph registry coverage; the 16-case wall-junction
table; compact/standard/wide `snap_compare` responsive snapshots of the preview
screen (the "visual review sheet"); preview-screen reroll/resize key handling.
Commit `ground: GW-WP15 Cloud City station-interior maps + art`.

### GW-WP16 — Gated Cloud City assault integration (L/XL) — SHIPPED

**Status: shipped July 2026 — GW-M5 done, all of GW-WP01–16 shipped.** Interview
decisions this session: **bulkhead stays permanently indestructible** (only
`security_door` is destructible — the "Recommended" option, bounding structure
count to actual doorways instead of ~400+ wall cells per station); **surrender/
Resolve is whole-station**, not per-district (the user chose this over the
per-district recommendation).

Research before implementation (an advisor pass, before committing to the
shape) found the tactical engine already almost entirely **topology-agnostic**:
`_battle_move_cost`/`_line_of_sight`/`_battle_cover_at`/`_reachable` read
terrain by feature name and live `AssaultStructure`s, not planet type;
`_check_cowed`/`broadcast_terms`/`_apply_resolve` key purely on `city_id`;
`settle_assault` (D8) reads structure-kind counters and headcounts only;
`session._assault_operation_view`/`AssaultCityDTO` project whatever
`AssaultMap` they're given with no hardcoded assumptions. So this WP turned out
to be almost entirely a **generation-adapter + gating** problem:

- New `edge/core/groundwar/interior.py::District`/`InteriorLayout.districts`
  exposes the per-room records WP15's generator already built internally but
  never surfaced. A new defensive test
  (`test_connectivity_holds_without_lift_links`) proves `lift_links` are never
  load-bearing (`_connect_rooms` already spans every room via corridors/doors
  *before* `_place_lifts` runs) — so `lift` cells are inert floor tactically,
  no teleport mechanic needed; `lift`'s existing `GwTerrain` entry already
  reads as ordinary floor.
- New `edge/core/groundwar/assault.py::generate_cloud_city_assault_map` builds
  an `AssaultMap` from `generate_interior`: **one shared `AssaultCity`** seated
  at the command-core district (every structure across every physical room
  reports to it — this alone makes surrender whole-station with **zero
  changes** to `_check_cowed`/`broadcast_terms`/`_apply_resolve`'s own
  `city_id`-keyed code), AA/sensor per district (extra AA + a `citadel_gun` at
  `citadel_level >= 2`/`>= 3` capital-only, mirroring `_stamp_city`'s own
  thresholds), `building_civilian`/`building_military` stamped in
  `habitation`/`engineering` districts (WP15's vocabulary had none — this is
  what gives civilian-harm consequences a real target on a station), every
  `security_door` → a `gate` structure, **no `wall`-kind structure ever
  emitted** (`city_cowed` never references walls/gates, so this has zero
  effect on the win condition). New `AssaultMap.spawn_anchors` carries the
  layout's `defender_slots` so `_place_units` has somewhere to spawn garrison
  even on a station with zero doors (found via a real generated-seed
  distribution during testing — some seeds have zero `security_door` cells).
  A real bug caught by the test suite, not assumed safe: a WP15 deployment
  zone could land on a cell a district's emplacement stamp later claimed,
  making `assault_drop` reject it — fixed by reserving `deployment_zones`
  cells from `_stamp_district`'s candidate floor before this WP shipped, not
  after a report.
- `derive_difficulty` branches: for a jovian world, `cities` carries
  `planet.cloud_city_size` directly (WP15's own district-count formula
  controls room count, not the population-derived terrestrial one) —
  `citadel_level`/`surrender_threshold` are untouched, already
  planet-type-agnostic. `AssaultOperation.cities` therefore doubles as
  `cloud_city_size` for a jovian operation, reusing the existing field rather
  than adding a new hashed one. `assault_map_for_state` dispatches on
  `is_cloud_city_world(op.planet_type, config)`.
- `edge/core/groundwar/access.py::ground_access` gates the below-friendly →
  `Assault` path **inside** the existing Cloud City branch on
  `groundwar.cloud_city_assault_enabled` — friendly/owned Cloud Cities and a
  bare gas giant stay `OrbitalOnly` regardless; the Core sanctuary (G13) and
  "citadels not configured" checks apply exactly as they do everywhere else.
- **Confirmed zero-touch by actually exercising the code, not just reading
  it**: `edge/server/session.py`/`edge/core/dto.py` (generic DTO projection),
  `edge/core/groundwar/settlement.py` (D8, planet-type-agnostic), the
  unmodified `edge/tui/screens/ground_assault.py` (a Pilot smoke test pushes
  it against a live Cloud City operation and it renders/accepts input with no
  code changes — the CITIES panel just shows one row). Wire/DTO shape is
  unchanged, so `WIRE_VERSION` did not bump; `config_version` 13→14 closes the
  GW-M5 epoch batching both this WP's `cloud_city_assault_enabled` flag and
  WP15's deferred `GwCloudCity`/terrain-class additions in one bump, per
  "config epochs batch per milestone."
- `edge/groundwar/harness.py` gained `cloud_city_assault_state` (mirrors
  `assault_state`'s shape: `seed_garrison`-sized garrison, loaded ship, gun
  already silenced) for the Pilot smoke test; no new interactive
  `edge-groundwar` setup-screen mode was added (flagged as a follow-up, not
  required to prove the topology adapter's correctness).
- **Not tuned this WP, flagged not silent** (a WP13-style follow-up): garrison
  counts, defense density per district, emplacement placement geometry,
  multi-drop-zone landing (only `deployment_zones[0]` is used), a dedicated
  Cloud-City bot/multiplayer contention scenario (the existing groundwar
  bot/multiplayer tests already stress the shared tactical engine), and TUI
  wording polish ("planetfall"/city terminology reading oddly for a station).

Files: `edge/core/groundwar/interior.py`, `edge/core/groundwar/assault.py`,
`edge/core/groundwar/access.py`, `edge/core/config.py`,
`config/groundwar_default.yaml`, `edge/groundwar/harness.py`,
`config/default.yaml`, `tests/test_config.py`.
Tests: `tests/test_groundwar_interior.py` (District/no-lift-links proof),
`tests/test_groundwar_cloud_city_assault.py` (pure generation), `tests/
test_groundwar_cloud_city_assault_tactics.py` (drop/fight/broadcast/settle
end-to-end), `tests/test_groundwar_cloud_city_assault_view.py` (Textual
Pilot), `tests/test_groundwar_access.py` (gate-off/gate-on table). Full
`-k groundwar` suite green, no regressions in the terrestrial assault path.
Commit `ground: GW-WP16 Cloud City interior assaults` — **GW-M5 done.**

### GW-WP17 — Cloud City survey tour + the interior render fix it exposed (M) — SHIPPED

Two findings drove this WP, both surfaced while scoping a user request to visit an
owned Cloud City rather than leave it permanently `OrbitalOnly`:

- **A player-buildable citadel on a jovian was never excluded.** `citadels.open_build`
  only checked colonist/equipment minimums, both of which a staged Cloud City can
  satisfy (`cloud_city_size × berths` colonists, stores once staged) — so a player
  could build/upgrade a citadel on their own gas giant, which has no ground to fortify.
  Fixed by excluding every `is_cloud_city_world` planet in `citadels.open_build`
  (raises `CitadelError`) and the `session.py` `can_build_citadel` projection
  (`sovereign_by_you and not city_world`). A citadel level already standing on one
  (bigbang NPC seeding on an alliance-owned jovian, or one inherited by conquering a
  hostile station) is untouched — only the player's own *build* path is barred, so
  WP16's command-core `citadel_gun` structure is unaffected.
- **GW-WP15/16 shipped without live rendering.** `edge.art.interior.style_interior`
  (wall-aware junction glyphs, door/lift landmarks) was complete but wired only into
  the offline `interior_preview` harness. The live `GroundAssaultScreen` dispatched
  every cell through `_ground_shared.feature_colors`/`feature_glyph`, keyed on
  `(ptype, feature)` — `BIOME_BANDS["jovian"]` only has the pre-Cloud-City
  `gas_thick`/`gas_thin` bands, and `FEATURES_REGISTRY` had no interior feature
  entries at all, so a live Cloud City assault rendered every room/wall as a plain
  `?`. `test_groundwar_cloud_city_assault_view.py` never caught it because it only
  asserts DTO shape (`view.cities`, `is_citadel`), never glyph/color content —
  confirmed empirically before reporting it, not assumed from reading code.

Fix and feature landed together:

- `edge/core/groundwar/interior.py` gained `WALL_LIKE_FEATURES` and
  `wall_neighbor_mask()` — the pure 4-bit N/S/E/W junction-mask math extracted from
  `edge.art.interior._wall_glyph` so a server can compute it once against the *full*
  grid (a client holding only a cropped viewport can't always see a wall cell's true
  neighbours at the viewport's edge). `edge/art/interior.py._wall_glyph` now calls it
  instead of duplicating the math; `_WALL_GLYPHS` renamed public `WALL_GLYPHS` since
  the live-screen resolver indexes it directly.
- `AssaultCellDTO`/`GroundCellDTO` gain `wall_mask: int = 0`, populated in
  `session.py` only for a `"bulkhead"` cell (0 elsewhere, harmless). `WIRE_VERSION`
  37 (v36→v37; DTO shape changed, unlike WP16).
- `_ground_shared.feature_colors`/`glyph_ramp`/`feature_glyph` check
  `edge.art.interior`'s `FEATURE_COLORS`/`FEATURES_REGISTRY` before the biome tables
  (the two feature-name sets are disjoint — validated by `GroundwarConfig` — so this
  never shadows a planet texture); `bulkhead` resolves via `WALL_GLYPHS[wall_mask]`,
  `security_door`/`lift` to their own fixed landmark glyph rather than randomized
  texture. Both `GroundAssaultScreen` and the new tour screen consume the same path.
- `ground_access` routes a friendly/owned, staged Cloud City to `Survey` (previously
  permanently `OrbitalOnly`) — `settlements=False` (the whole station is already one
  friendly place, no separate "town" structure), reason "a Cloud City — tour its halls
  from the inside." A bare (unstaged) jovian and a below-friendly Cloud City are
  unchanged.
- `SurveyOperation.cloud_city_size` snapshots the station's size at descent —
  mirroring the existing `planet_type` snapshot — since the interior layout is a pure
  function of `(seed, cloud_city_size)` and a city that grows mid-tour must not
  reshuffle rooms underfoot. `_begin_survey` (`rules.py`) sets it and picks the
  default rest position from `groundwar.cloud_city` dimensions, not the (much larger)
  planet expedition map, for a Cloud City.
- `groundwar.survey.generate_survey` branches on `is_cloud_city_world` to
  `_generate_cloud_city_survey`, which calls `generate_interior` directly and returns
  a `SurveyMap` with `settlements=()`/`sites=()`/`blocked=frozenset()` (bulkhead
  impassability already comes from `GwTerrain.move_cost`, validated for every
  `INTERIOR_FEATURES` name — no core movement/pathing/LOS changes were needed, only
  the terrain-grid source and the art). `eligible_surface_site_ids` now excludes every
  Cloud City outright — a built station never surfaces a dig site regardless of what
  big bang happened to roll for the underlying jovian type before it was staged.
- `planet.py`'s ground panel and orbit-art tooltip read `p.cloud_city` to swap in
  "Tour"/"Tour the city" copy over "Survey"/"Survey surface" — the reducer path
  (`BeginSurvey` → `GroundExpeditionScreen`) is identical either way.

Files: `edge/core/citadels.py`, `edge/core/planets.py`,
`edge/core/groundwar/interior.py`, `edge/core/groundwar/access.py`,
`edge/core/groundwar/models.py`, `edge/core/groundwar/survey.py`, `edge/core/rules.py`,
`edge/core/dto.py`, `edge/art/interior.py`, `edge/tui/screens/_ground_shared.py`,
`edge/tui/screens/ground_assault.py`, `edge/tui/screens/ground_expedition.py`,
`edge/tui/screens/planet.py`, `edge/server/session.py`, `edge/server/wire.py`,
`docs/DESIGN.md`.
Tests: `tests/test_citadels.py` (Cloud City citadel-build rejection),
`tests/test_groundwar_interior.py` (renamed `WALL_GLYPHS` import),
`tests/test_wire.py` (regenerated golden fingerprint/envelopes for v37).
Commit `ground: GW-WP17 Cloud City survey tour + interior render fix`.

### GW-WP18 — Cloud City salvage crates + two shipped-with-WP17 bugs (M) — SHIPPED

A follow-up request ("I should be able to visit... even with no finds" reversed to
"I should be able to dig!" once the tour existed) — clarified to *crates*, not
literal digging through a metal floor: standing over one and opening it. Landed
alongside two bugs the tour work exposed:

- **Double-width glyphs broke the sidebar.** The interior `engineering`/`electrical`
  glyph pools (`edge/art/interior.py`, shipped in GW-WP17) picked `⚌`/`⚡`, both
  `rich.cells.cell_len` == 2 — a double-width glyph desyncs the fixed per-cell grid
  one column per occurrence, cascading through the row and misaligning the sidebar's
  border. Swept the *entire* shared render path (biome terrain, hardcoded screen
  markers, `STRUCTURE_ART`/`RUBBLE_ART`) and confirmed those two were the only
  offenders; replaced with `╫`/`⌁` (both width 1) and added
  `tests/test_ground_render_glyph_widths.py` as a permanent guard — two registries
  swept automatically, the hardcoded markers inventoried once.
- **A crate's `opened` flag never reached the live view.** `_cached_survey_map_for`'s
  cache key omitted `op.opened_crate_ids` (and `op.cloud_city_size`), so a crate
  opened server-side (confirmed via the event log) kept rendering `opened=False`
  forever — caught by a Textual Pilot test that actually pressed `X` and checked the
  *next* rendered view, not just that the reducer accepted the command.

The crate mechanic itself:

- `citadels`'s salvage precedent, not a `Discovery`: opening a crate pulls a Tier-I
  `Component` into the ship's loose inventory the same way `Cannibalize` pulls one
  out of a derelict base — never routed through the artifact/codex/experience rail
  the G6 invariant reserves for real surface finds (property-tested, untouched here).
  Refuses outright (`ship.holds_free < 1`) rather than mutate when the hold is full,
  leaving the crate unopened — matching `Cannibalize`'s own defensive pattern.
- `edge.core.groundwar.interior.generate_interior` gained `_crate_slots` (up to one
  per non-command_core district, `groundwar.cloud_city.crate_chance` per-district
  odds) and `InteriorLayout.crate_slots`, drawn from the *tail* of the same `rng`
  stream — after every earlier field, so appending it never perturbs an
  already-generated layout's rooms/corridors/hazards/lifts/objective (verified by
  hashing `feature_grid` across 80 `(seed, size)` pairs before/after, not just
  reasoned about — `test_crate_slots_do_not_perturb_the_existing_layout`).
- `groundwar.survey.CrateSite`/`SurveyMap.crates` project `layout.crate_slots` into
  numbered crates — **1-based** ids (`enumerate(..., 1)`), matching `found_contact_id`'s
  own "0 means nothing here" convention; a first-crate id of 0 would have been
  indistinguishable from "no crate" on `GroundCellDTO.crate_id`.
  `SurveyOperation.opened_crate_ids` snapshots which have been opened — a crate has
  no durable backing entity the way a `Discovery` does, so this is its only record,
  persisted into `SurveyProgress` on extraction exactly like `hinted_discovery_ids`.
- New `OpenCrate` command / `CrateOpened` event, a `_open_crate` reducer beside
  `_survey_dig` (not folded into it — the G6 reward rail must stay untouched), and
  `Player`/`GameCommand`/codec/wire wiring identical in shape to `SurveyDig`'s.
- `SurveyExpeditionDTO.is_cloud_city`/`crates` (`CrateDTO`) and
  `GroundCellDTO.crate_id` project the above; `GroundExpeditionScreen`'s `X` key
  (`action_dig`) branches on `is_cloud_city` to send `OpenCrate` instead of
  `SurveyDig` — same key, same screen, different verb — with its own sidebar
  CRATES section (replacing CONTACTS/SETTLEMENTS, which are always empty for a
  Cloud City) and a `▣` crate glyph on the map. `can_dig`'s server-side legality
  gained `or is_cloud_city` since opening a crate costs no supplies, unlike a dig.
  `WIRE_VERSION` stayed 37 — folded into the not-yet-committed GW-WP17 bump rather
  than a second version, one golden regeneration for both.

Files (added to GW-WP17's list, same commit boundary target): `edge/core/config.py`
(`GwCloudCity.crate_chance`), `config/groundwar_default.yaml`,
`edge/core/groundwar/interior.py`, `edge/core/groundwar/survey.py`,
`edge/core/groundwar/models.py`, `edge/core/rules.py`, `edge/core/events.py`,
`edge/core/dto.py`, `edge/store/codec.py`, `edge/server/session.py`,
`edge/server/wire.py`, `edge/art/interior.py`, `edge/tui/screens/_ground_shared.py`,
`edge/tui/screens/ground_expedition.py`, `edge/tui/screens/planet.py`, `docs/DESIGN.md`.
Tests: `tests/test_ground_render_glyph_widths.py` (new — width guard),
`tests/test_groundwar_interior.py` (crate-slot placement + no-perturbation),
`tests/test_groundwar_survey.py` (crate projection/ids),
`tests/test_groundwar_access.py` (`OpenCrate` reducer: grant/refuse/already-opened/
no-crate-here), `tests/test_groundwar_expedition_view.py` (DTO projection + a
Textual Pilot round-trip that caught the cache-key bug), `tests/test_codec.py`,
`tests/test_wire.py` (regenerated goldens).
Commit (pending, same boundary as GW-WP17 unless split at the user's request).

### GW-WP19 — One world, one ground: shared survey/assault layout (XL) — SHIPPED

Closes the first of the two **known gaps GW-WP12-FU1 recorded** ("No shared terrain
identity between survey and assault", explicitly sized there as "its own work
package"). The user's framing when reopening it: *after making a world a protectorate
with a successful ground assault we can then survey the same world, which still
includes the damage from the assault.*

**The premise checked out; the payoff did not.** A protectorate world does route to
`Survey` — `access._friendly` calls `corp.player_controls_planet`, which counts
`protectorate_controller` — but what it showed you was a different planet. Three
independent breaks, not one:

1. **Different noise seed.** `generate_survey` passed its operation seed straight into
   `generate_feature_grid`; `generate_assault_map` passed
   `Random(f"{seed}|assault|…").randint(...)`. And the two operation seeds came from
   different places: survey's was per-*player* per-world (`SurveyProgress.map_seed`),
   assault's freshly drawn per operation. Nothing tied either to the planet.
2. **Towns and cities were unrelated.** Survey scattered 18×9 `SurveySettlement`s from a
   peaceable name pool; assault stamped walled `AssaultCity`s in per-city lanes from a
   military pool. The place you fought over did not exist on the survey map.
3. **Damage was not positional.** `Planet.ground_damage` was a per-kind `Counter`, and
   `models.py` said why in as many words: *"Damage is aggregated by tactical structure
   kind because each operation regenerates a fresh deterministic layout."* So a survey
   had nothing to paint — and **a second assault on the same world also got a brand-new
   battlefield**, a consistency hole wider than the survey mismatch that prompted the WP.

**One piece of luck made the fix tractable:** `battlefield` and `expedition` were already
both 220×56, so no cropping or rescaling was needed (the config comment calling expedition
"smaller than the battlefield" was stale and is corrected). And `Game.seed` meant the
shared identity could be **derived** rather than stored.

**Implementation.** New pure `edge/core/groundwar/world.py` owns the one identity:
`world_ground_seed(Game.seed, planet_id)` (derived — **no new hashed field** for the seam
itself), `place_count`, `generate_world_ground` → a `WorldGround` of biome grid +
one `PlaceStamp` per place (footprint, perimeter, gates, military/civilian building
blocks, reserved emplacement slots). `survey.generate_survey` renders each stamp as a
walkable town; `assault._stamp_city` fortifies the identical geometry, adding only hit
points, turrets on the corner/mid-wall slots, and the live `citadel_level`'s
emplacements. The generation-time terrain/passability helpers (`move_cost`,
`passable_components`, `landing_in_component`, `footprint_passable_frac`) had been
byte-identical private copies in both modules and are now one copy in `world.py`; the
*battle-time* cost/cover functions stay separate on purpose (rubble mid-fight).

- **`Planet.ground_rubble: tuple[GroundRubble, ...]` replaces `ground_damage`** —
  positional, monotone, and the single truth (`world.rubble_counts` derives the aggregate
  the counter used to store). `persistent_structure_hp` now zeroes *the structure that
  stood there* instead of spending a per-kind count against "the lowest stable ids of
  each kind". Rubble is walkable in both modes (`survey._cell_cost` checks it ahead of
  the terrain class, since a station's `security_door`/`bulkhead` is impassable by
  *feature*, not by `blocked`).
- **`SurveyOperation.world_seed`/`places` and `AssaultOperation.world_seed`** snapshot the
  identity at begin (mirroring `cloud_city_size`/`cities`), so a mid-operation change
  cannot reshuffle the ground and the pure regeneration seams stay state-free.
  `SurveyProgress.map_seed` is **retired**: generation identity was never one player's
  memory of a place. Position, hints, and opened crates still persist per player (D5).
- **Cloud Cities get the same treatment** (the user chose this): the tour and the
  interior assault now generate from the same `world_seed`, so a station taken by force
  is toured room for room as the one fought through, with blown doors showing as rubble.
- **A projection bug fixed on the way**: `session.py` re-derived town gates from the town
  box as "mid-edge on all four sides", which the shared layout makes wrong (top/bottom
  mid cells are turret slots). `SurveyMap.gates` now carries them and the projection
  reads it — the same class of guess GW-WP07-FU1 removed for settlement plazas.
- **Cache-key discipline** (the GW-WP18 lesson): `_cached_survey_map_for`'s key gains
  `world_seed`, `places`, and `ground_rubble`, or a wall levelled by an assault would keep
  rendering intact for the life of the process.

**Deliberate scope calls, recorded per the plan's change rule.**
`assault_difficulty.hostility_mult`/`alliance_owned_mult`/`had_gun_mult` no longer size
the battlefield. Each of them *changes* over a world's life — ownership and citadel level
flip on conquest, and the inhabiting species vanishes if its people are wiped out — so
each was a path by which a layout could re-roll, which is the bug being removed.
`place_count` is now capacity × band only, and the three multipliers lower
`surrender_threshold` instead (a hostile people, a bloc holding, or a world that built and
lost a gun holds out to a lower Resolve). The species path was caught by asking what
happens to a world whose last native dies, not by a test failure. `expedition.settlements_min`/
`settlements_max` are **retired**: town count is `world.place_count`, and a separate knob
could only ever have disagreed with the assault it must match. Place footprints adopt the
assault's sizes (24×11, capital 30×14) and the lane layout, and the two name pools merge
into one `PLACE_NAMES` — a place has one name whichever way you arrive.

**Epoch:** `config_version` 14→15 (hashed `Planet`/operation shape + the two retired
expedition fields), `WIRE_VERSION` 37→38 (`GroundCellDTO.rubble`).

Files: `edge/core/groundwar/world.py` (new), `edge/core/groundwar/{survey,assault,
settlement,models}.py`, `edge/core/{models,config,dto,rules}.py`,
`edge/server/{session,wire}.py`, `edge/tui/screens/ground_expedition.py`,
`config/{default,groundwar_default}.yaml`, `docs/DESIGN.md`.
Tests: `tests/test_groundwar_world.py` (new, 10) — the two assertions that could not be
written before (`test_survey_and_assault_of_one_world_share_terrain_and_places`,
`test_surveying_a_conquered_world_shows_the_assaults_rubble`), plus derived-seed
stability, generation determinism, an uninhabited world keeping its terrain without
towns, the conquest-does-not-re-roll guard, the shared-grid config rejection, positional
settlement, repeat-assault breach reuse, and two players getting one world. Existing
suites updated for the new contract (`test_groundwar_{survey,survey_actions,settlement,
cloud_city_assault_tactics}.py`) and the ground snapshots regenerated.

**Still open** (unchanged by this WP): the second GW-WP12-FU1 known gap — protectorate/
annexation has no TUI surface — plus GW-WP13's and GW-WP16's deferred balance tuning.
*(The protectorate gap is closed by GW-WP20 below.)*

### GW-WP20 — Protectorate administration and annexation UI (M) — SHIPPED

Closes the **second** of the two known gaps GW-WP12-FU1 recorded: "the rights DESIGN.md
§4.2 describes are implemented in core but never reach a player." Everything D13/D14
grants had been in core since GW-WP11 — `AnnexProtectorate`, `annex_ready`'s two gates,
`player_controls_planet` widening allocation/transfer/fighters/reinforce to a controller,
`_planet_bank` deliberately *not* widened, and `planets.py`'s per-day share accrual into
`Planet.protectorate_stores`. Nothing projected or offered any of it.

**The gap was not only a missing button.** Two shipped screens were written under a
sovereign-ownership assumption that a protectorate quietly violates, and both were
already wrong before this WP added anything:

1. **The transfer workbench offered cargo the reducer would refuse.** `_transfer_cargo`
   and `_batch_transfer_cargo` branch on `corp.player_owns`: a *controller* loads from
   `protectorate_stores`, not `planet.stores`. The workbench read `PlanetDTO.stores` for
   both its readout and its stepper ceiling, so a world with 9,000 Fuel in native stores
   and 30 in the controller's share offered a 60-unit load (holds-clamped) that the
   reducer would cut to 30. Fixed by projecting the share and clamping to it, with the
   row relabelled "your share"; unloading still credits the inhabitants either way.
2. **The citadel panel offered banking on a protectorate.** Its gate is `owned_by_you`,
   which is the broader owns-*or-controls* test, while `_planet_bank` uses
   `_owned_planet_here` **without** `controlled=True` — D13 keeps the treasury with its
   people. Deposit/Withdraw were reachable and could only ever refuse.

**Implementation.** `PlanetDTO` gains ten fields — `protectorate` / `protectorate_yours` /
`protectorate_days` / `protectorate_share_pct` / `protectorate_stores`, and the D14 gate as
`ground_resolve` / `annex_resolve_threshold` / `can_annex` / `annex_blocker`. `planet_view`
fills them from `gw_settlement.annex_ready` itself, so the greyed line and the refusal are
one sentence rather than two paraphrases (the projection adds only the reducer's in-sector
check, which `annex_ready` does not cover because it takes no ship). The share ledger
projects **only to its controller** — an outsider sees `protectorate=True` and nothing of
another player's books.

`PlanetScreen` gains a Protectorate panel (age held, the share ledger, and a Resolve bar
against the annex threshold — the half of the D14 gate a player can watch recover) and an
`A` / `Annex — take ownership` action behind `ConfirmScreen`, listed in `ACTION_DANGER`
beside genesis/reinforce since it dissolves a polity and carries the stronger species,
grudge, spillover, and alignment consequences. `check_action` hides the key entirely on a
world that is not your protectorate, but keeps it live when it is merely *barred*, so
pressing it explains rather than doing nothing (the shipped `build_city` precedent). The
stores table splits into "Their stores" / "Your share" columns on a protectorate, and the
citadel line reads "their treasury".

No hashed state or config changed — `config_version` stays 15. `WIRE_VERSION` 38→39 for
the `PlanetDTO` shape, with the fingerprint and envelope goldens regenerated.

Files: `edge/core/dto.py`, `edge/server/session.py`, `edge/server/wire.py`,
`edge/tui/screens/planet.py`, `edge/tui/screens/transfer.py`, wire fixtures.
Tests: `tests/test_groundwar_protectorate_ui.py` (new, 15) — control age/share
projection, the no-leak case for another power's protectorate, both D14 blockers asserted
**equal to the reducer's own `EconomyError` string**, annex merging the share into stores
without minting or dropping (G8), the out-of-sector gate barred in both places, the panel
at all three layout tiers, the greyed-with-reason case, the hidden-key case, the split
stores table, banking hidden, and the workbench load drawing the share while the natives'
9,000 stays untouched.

Full suite: 3,270 passed, 80 snapshots, lint and strict mypy clean. **Two pre-existing
failures**, both confirmed present on a clean stash *before* this WP and deliberately not
chased (they are core/engine and chrome, outside a projection-and-screens WP):
`tests/test_ui_snapshots.py::test_options_modal`, already recorded as pre-existing under
GW-WP14; and — newly observed here, not previously recorded —
`tests/test_groundwar_cloud_city_assault_tactics.py::test_settle_assault_extraction_leaves_ownership_untouched`,
where the drop now leaves `AssaultOperation.outcome` already set (the op reaches
`assault_end_turn` at `resolve=101`), so the next `assault_end_turn` raises "the assault
has ended — extract to orbit" instead of running a defense phase. Worth a look as its own
item: either the fixture's starting Resolve/retrieval clock drifted from the engine, or a
Cloud City drop is ending the operation earlier than the terrestrial path it shares.
**Diagnosed and fixed in GW-WP21 (below) — it was neither: the fixture drops a lone
trooper onto a fully-armed station, and the station shoots it down.**

**Still open after this WP:** GW-WP13's and GW-WP16's deferred balance tuning
(garrison counts, defense density, emplacement geometry, victory/casualty rates), which
the plan records as needing a human read of the bot seed-matrix runs rather than more
harness — plus the two pre-existing failures above.

### GW-WP21 — Unique band names per landable biome, and two red tests (S) — SHIPPED

Three small items, all surfaced by GW-WP20's full-suite run.

**1. Closes GW-WP07-FU1's deferred colour gap.** That note read: "`_feature_colors`
matches the *first* band with a given feature name, so where a biome repeats one
(`terrestrial_cold` ice, jovian, asteroid_belt) the later band's colours are unreachable —
fixing it needs a band index on `GroundCellDTO`."

Two corrections to that note, from tracing it rather than re-reading it:

- **The scope is narrower than recorded.** Of the three biomes named, only
  `terrestrial_cold` is affected. Jovian ground maps are Cloud City *interiors*, whose
  feature names are a disjoint namespace `feature_colors` resolves before it ever consults
  `ptype`; asteroid belts are not landable at all (`LANDABLE_BIOMES`, D9). Both are still
  reached by *planet art*, which calls `get_biome_feature` and indexes bands positionally —
  correct already. So the live defect was exactly one: `terrestrial_cold`'s high ice band
  (authored `bright_cyan` on `blue`) rendering in the shallow band's `bright_white` on
  `white`. Rare enough to hide — about 0.4% of cells on a sample cold world — but two
  terrains authored to look different drew identically.
- **A band index on `GroundCellDTO` is the wrong fix.** It would grow every projected cell,
  need a wire bump, and require the band index to survive from generation through the
  frozen map models — all to work *around* the root cause. The root cause is that a band's
  name is its only identity in the colour lookup **and** its gameplay key, so two bands
  sharing a name are indistinguishable in every respect except the colours one of them can
  never reach. The fix is to stop sharing: `terrestrial_cold`'s top band is now `glacier`.

`glacier` gets its own terrain class (deliberately *identical* to `ice` — the split is a
rendering fix, and changing movement or cover in the same commit would smuggle a balance
edit in behind a cosmetic one; it is now free to diverge when that is an intended tuning
decision), its own heavier glyphs so the two ice bands separate by weight as well as
colour, and a place in `landing_blocked_features`, which it had implicitly as `ice` and
must not silently lose. No DTO, wire, or hashed-state change; `config_version` stays 15.

The invariant is now stated where the bands are authored and **guarded by tests**, scoped
to `LANDABLE_BIOMES` because that is where it bites.

**2. `test_settle_assault_extraction_leaves_ownership_untouched` — a fixture, not a
regression.** The GW-WP20 note above guessed at a drifted retrieval clock or a Cloud City
drop path diverging from the terrestrial one. It is neither. The fixture drops **one**
trooper onto the `_map()`/`_op()` defaults — a size-3 station at citadel level 2 — and the
station's AA and citadel guns shoot the capsule down during `assault_drop` on 4 of 6 seeds,
including the seed the test pins. The operation is `wiped` before the test's
`assault_end_turn` is reached, and that call correctly refuses to run a defense phase for a
finished operation. The engine is right; the scenario simply became unreachable.

Fixed the way the sibling `test_retrieval_clock_ends_the_mission_unbowed` already solves
it — drop on an undefended station (`cloud_city_size=1`, `citadel_level=0`), where the
drop survives on 6 of 6 seeds — plus an explicit `assert op.outcome is None` so the test
fails loudly at the *setup* step if this ever recurs, instead of failing later somewhere
that invites the same misdiagnosis. The test's actual subject, that a `retrieval` outcome
leaves ownership untouched, was never broken.

Whether a lone capsule surviving a fully-armed station only a third of the time is
correctly *tuned* is a separate question, and belongs to GW-WP13/WP16's deferred balance
pass — recorded there, not decided here.

**3. `test_options_modal` — a stale baseline, not a regression.** Carried as a known
pre-existing failure since GW-WP14 without anyone establishing *why*. Diffing the text of
the committed SVG against a fresh capture shows exactly two differences: a new
`U — Auto-end assault turn (solo trooper)` row, and the footer key hint growing from
`T/R/A/D/O/G change` to `T/R/A/D/O/G/U change`. Everything else is identical content in a
different element order. `git log -S` puts the cause at `5f3c764` (GW-WP12-FU1), which
added the option and touched no snapshot file. The modal is rendering its new option
correctly, so the baseline is simply out of date — refreshed, and the whole snapshot
matrix (72) is green.

**Not taken here, deferred to a human:** GW-WP07-FU1's other gap, `_CONTRAST_TRIGGER`
(0.20). Measured, and the note is accurate: six landable bands sit between 0.20 and 0.26 —
`terrestrial_cold` ice, `terrestrial_cool` dust/snow/mountain, `terrestrial_warm` mountain,
`terrestrial_hot` mountain — so a 0.26 trigger corrects exactly the cluster the note names
and nothing else. But the correction is not obviously an improvement: `readable_fg` moves
*away* from the background, so on the pale biomes it darkens ice/snow/dust from
`bright_white` to `#666666` grey on white, which reads better and looks dirtier. Since
`BIOME_COLORS` is shared with the orbital planet-art screens, the change restyles every
world in the game. That is an aesthetic verdict for a human at a terminal, not a
luminance-threshold argument, so it went to one with the measurements attached —
see GW-WP21-FU1.

Files: `edge/core/groundwar/terrain.py`, `edge/art/terrain.py`,
`config/groundwar_default.yaml`.
Tests: `tests/test_terrain_bands.py` (new, 17) — band-name uniqueness per landable biome,
every band resolving to the colour pair authored at *its own* index, the concrete
shelf-ice/glacier regression, terrain-class and glyph coverage for every landable band,
and `glacier` still barred as a survey drop site;
`tests/test_groundwar_cloud_city_assault_tactics.py` (fixture fix);
`tests/__snapshots__/test_ui_snapshots/test_options_modal.svg` (baseline refresh).

**The whole suite is now green** — 3,289 passed, 80 snapshots, no known failures.

### GW-WP21-FU1 — `_CONTRAST_TRIGGER` raised to 0.26 (S) — SHIPPED

**Status:** shipped July 2026. Closes the last item GW-WP07-FU1 deferred, and the only one
GW-WP21 left open.

GW-WP21 measured the three candidates but declined to pick, because the choice is aesthetic
and `BIOME_COLORS` is shared with the orbital planet-art screens — the threshold restyles
every world in the game, not just the ground maps. The candidates were rendered to an image
(all five landable biomes at 0.20 / 0.26 / 0.35, one noise seed and one glyph seed
throughout, so the correction is the only variable) and read by a human, who chose 0.26 for
every biome.

**Confirmed against the rendering, not just the arithmetic.** The visible effect is
narrower than the luminance table implies: on the pale biomes the corrected bands are
sparse punctuation glyphs (`_ - * +`), so darkening their foreground moves very few pixels.
The band that actually changes is mountain rock — `#777777` → `#909090` against its grey —
which is also the one a player reads most, since relief drives every march decision. 0.35
was rejected as buying almost nothing over 0.26 while reaching bands that were already fine.

**Blast radius, measured rather than assumed.** Three expedition snapshots moved; diffing
their `<text>` content shows **zero** character differences, and diffing their style blocks
shows exactly **one** changed rule — the `#777777` → `#909090` above. Baselines refreshed.
The rest of the 80-snapshot matrix is untouched, which is the evidence that the restyle
stayed inside the terrain art.

Files: `edge/art/terrain.py` (the constant, plus the rationale recorded at the constant so
the next person to reach for it knows what it costs).
Tests: `tests/__snapshots__/test_groundwar_expedition_view/*.svg` (3 baselines refreshed);
full snapshot matrix and `tests/test_terrain_bands.py` re-run green.

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
- GW-WP01–21 (with GW-WP09-PRE) acceptance tests pass.
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
