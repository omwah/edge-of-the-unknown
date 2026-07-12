# Playtest Remediation Plan

Status: proposed  
Source: `/home/mcduffie/edge_notes.txt` (31 observations, July 2026)  
Scope: gameplay correctness, projection changes, and TUI follow-up after WP-UI23

## 1. Purpose

This plan converts the July 2026 playtest notes into implementation-sized work
packages. It is intended to be sufficient for an agent with no playtest context
to implement each package, test it, and hand it off independently.

The work must preserve the project's downward-only dependency graph. Rules and
legality belong in `edge/core`; fog-safe presentation data belongs in
`edge/server/session.py` and `edge/core/dto.py`; the TUI only renders projections
and submits commands. Any random choice must use the game-state RNG. Changes to
persisted dataclasses, commands, or events require codec, migration, replay, and
state-hash review.

## 2. Resolved design decisions

These decisions remove ambiguity in the raw notes.

1. **Destroyed NPC ships become persistent wreck discoveries.** Combat no longer
   pays NPC wreck salvage immediately. A destroyed hull creates a sector-space
   `DiscoveryKind.WRECK` with a deterministic payload/cache and visible wreck art.
   The existing scan/salvage/codex flow recovers it. This leaves evidence of the
   battle and reuses the established discovery vocabulary. Player destruction and
   PvP pod/salvage rules remain separate unless explicitly extended later.
2. **“Pack destroyed” is retired from player-facing copy.** Outcomes say exactly
   what happened: all hostile ships destroyed, a named ship destroyed, enemies
   retreated, or combat ended with enemies remaining. An NPC that successfully
   flees must be moved to a legal adjacent sector before the encounter closes.
3. **StarDock commands are tab-scoped.** Rumor/notice work only on Tavern; bank
   commands only on Bank; recruitment only on Colonists; purchase commands only
   on their catalog tab. Hidden footer bindings must not imply actions elsewhere.
4. **Asteroid belts remain spatial “world objects,” but are not planets in the
   interaction sense.** They may be scanned/mined and may have discoveries, but
   cannot be descended onto, colonized, hold colonists/stores, host citadels, or
   receive Genesis terraforming. Existing generated saves must tolerate and
   normalize legacy belt fields rather than requiring a destructive migration.
5. **Starbase integrity gates services, not ownership or recovery.** A configurable
   threshold (default 70%) gates market, hardware, bank, repair service, and
   munitions. Salvage and component repair remain available on a derelict/unowned
   base. Repairing a base does not force a claim; claim becomes an explicit later
   ownership action once the underlying planet permits it.
6. **Compact means removing or resizing decorative art before hiding controls.**
   Every art-bearing screen must remain operable at 80x24 with all primary actions
   visible or reachable through a keyboard-scrollable container.

Before implementing WP-PR01, WP-PR04, WP-PR06, or WP-PR09, update the applicable
sections of `docs/DESIGN.md` in the same commit if the detailed implementation
contract is not already stated there.

## 3. Issue-to-package map

| Playtest note | Package |
|---|---|
| 1 destroyed-ship art and wreck recovery | WP-PR01 |
| 17 cron entrants must trigger mines/fighters | WP-PR02 |
| 18, 26 fleeing alien and “pack destroyed” copy | WP-PR03 |
| 21 repair/salvage before claim; 22 integrity service threshold | WP-PR04 |
| 28 first black-hole click crash | WP-PR05 |
| 30 asteroid belts treated as planets | WP-PR06 |
| 11 unload more colonists to owned world; 10 unified store transfer | WP-PR07 |
| 2–7, 29 StarDock tabs, scope, colonists, bounty board, current hull | WP-PR08 |
| 8–9, 23, 27, 31 Computer sorting/status/route/avoid/contracts | WP-PR09 |
| 12–16 objectives, compact art, drawer navigation, nav rose/help | WP-PR10 |
| 19–20 deployment layout and disabled legality | WP-PR11 |
| 24 Genesis errors; 25 assault art | WP-PR12 |

## 4. Work packages

### WP-PR01 — Persistent combat wrecks — complete

**Goal:** make destroyed NPC hulls persist in the sector and defer recovery to the
discovery interaction.

**Core and data changes**

- Add a replay-stable representation for a combat-created wreck. Prefer the
  existing `Discovery` plus `DiscoveryPayload`; add only the minimum fields needed
  for multiple salvage items (latinum and loose components) if the current payload
  is single-item. Do not encode presentation text in core state.
- In the combat reducer (`edge/core/rules.py`, currently `_salvage_pack` and the
  NPC-destruction branch), allocate discovery ids deterministically, place one
  wreck per destroyed meaningful hull in the combat sector, and derive cache
  contents using the existing salvage configuration and state RNG.
- Remove immediate `SalvageCollected` payment for NPC kills. Keep bounty and
  experience award timing explicit and tested; bounty may still pay on confirmed
  destruction, while wreck contents wait for collection.
- Decide whether wrecks are sensor-hidden from existing rarity/detection rules or
  immediately visible after witnessed combat. The required behavior is immediate
  visibility to the witnessing player and normal fog behavior for others.
- Emit a new event only if existing discovery-created/detected events cannot
  describe the result. If an event/schema changes, update `edge/store/codec.py`,
  protocol codec fixtures, state hash, migrations, and golden replays.

**Projection and TUI**

- Ensure `game_view` returns the wreck in `sector.discoveries` and that SectorView
  switches from intact ship art to `edge/art/discovery.py` wreck art after combat.
- Give the wreck a clear action label such as “Salvage wreckage”; collection uses
  the existing discovery action and reports each recovered resource.
- Preserve wrecks after collection as codex/log evidence if that is the existing
  discovery convention; otherwise render a depleted/recorded state until departure.

**Likely files:** `edge/core/models.py`, `edge/core/rules.py`,
`edge/core/events.py`, `edge/core/discovery.py`, `edge/core/dto.py`,
`edge/server/session.py`, `edge/store/codec.py`, `edge/tui/screens/game.py`,
combat/discovery/codec/replay/UI tests.

**Acceptance:** a fixed-seed combat kill creates a wreck at the correct sector,
does not immediately credit its cache, survives save/reload and replay, changes
sector art, and credits the deterministic cache exactly once when salvaged.

Commit: `playtest: WP-PR01 persistent combat wrecks`

### WP-PR02 — Territory defenses on NPC cron movement — complete

**Goal:** movement by the NPC cron follows the same sector-entry defense rules as
player movement.

- Extract or extend one pure entry-resolution seam in `edge/core/rules.py` /
  `edge/core/territory.py` for armid mines, fighter modes, ownership/hostility,
  damage, depletion, destruction, and events. Both player warp and NPC movement
  call it; do not duplicate formulas in `edge/engine/npc.py`.
- Defensive fighters engage hostile entrants; offensive fighters engage any
  eligible non-owner; toll behavior for NPCs must be specified (recommended:
  non-paying hostile NPCs are engaged). Friendly/owner entries do not trigger.
- Armid mines are consumed according to current rules and can destroy or damage an
  NPC. Limpets attach and update tracking state if the model supports NPC tags;
  otherwise explicitly defer NPC limpets and test that armids/fighters work.
- Cron event ordering must be deterministic: choose move, resolve entry defenses,
  then open/skip encounters based on survival. A destroyed NPC cannot appear in
  the destination projection or start an encounter.

**Tests:** unit matrix by force mode and relationship; cron integration with fixed
seed; depletion and event ordering; replay equality; no friendly fire.

Commit: `playtest: WP-PR02 NPC entry territory defenses`

### WP-PR03 — Correct flee state and combat outcome language — complete

**Goal:** successful alien flight changes world state and produces truthful copy.

- Inspect `edge/core/combat.py` and the combat-action reducer. On an NPC flee
  success, select a legal outbound warp using state RNG, excluding interdictor-
  blocked routes and any rule-forbidden destination, update every fleeing pack
  member's sector, clear the encounter, and emit a movement/retreat event carrying
  the destination when fog permits it.
- If no legal warp exists, flight fails and combat remains active. If some pack
  members are destroyed and others flee, represent and announce the mixed result.
- Replace “Victory — the pack is destroyed” and every generic “pack” outcome in
  `edge/server/session.py` and encounter UI with concrete counts/names. Reserve
  “victory” for all enemies destroyed; use “enemies retreated” for flight.
- Confirm subsequent sector view and NPC cron see the relocated ships exactly once.

**Tests:** successful flee, blocked flee, mixed destroyed/fled pack, destination
determinism, no ghost ship in origin, event-log wording, encounter-screen Pilot flow.

Commit: `playtest: WP-PR03 alien retreat state and copy`

### WP-PR04 — Starbase recovery and integrity-gated services — complete

**Goal:** let players work on abandoned bases before claiming them and prevent
damaged bases from providing full services.

- Add `starbase.service_integrity_min` to config, default `0.70`, with validation
  in `edge/core/config.py` and the default YAML. Bump config version only if required
  by the repository's compatibility policy.
- Define a single pure predicate beside `edge/core/starbases.py::is_operational`,
  e.g. `services_operational(base, config)`, based on component integrity and the
  threshold. Use it in both reducer authorization and DTO projection so hidden tabs
  and command legality cannot drift.
- Change `RepairStarbase` and salvage authorization: a base with no hostile owner
  may be salvaged and repaired without first being claimed. Installing the first
  component must not silently set owner. `ClaimStarbase` remains explicit and is
  allowed only when the underlying planet/ownership rules permit it.
- Gate market, hardware, munitions, bank, and other forward services below the
  threshold. Recovery actions remain available. `StarbaseDTO` should carry a
  service blocker/required percentage so BaseScreen can explain why tabs are greyed
  out instead of merely omitting them.
- Ensure an owned base damaged below threshold closes services immediately and
  reopens them when repaired above threshold.

**Tests:** unclaimed salvage, unclaimed first and later repairs, explicit claim,
threshold boundaries (69/70/71), command/projection parity, damaged owned base,
save/replay/config loading, BaseScreen disabled-tab flow.

Commit: `playtest: WP-PR04 starbase recovery and integrity gates`

### WP-PR05 — Black-hole interaction crash — complete

**Resolution note:** the original crash did not reproduce in the current tree. It was
the lethal-hazard path, closed at the core by the WP26/WP75 escape pod (the note's own
"the core already has entry-hazard tests" points at `test_territory.py`). WP-PR05
therefore lands as the missing TUI regression lock-down: `tests/test_ui_black_hole.py`
drives the real app through the full mouse/keyboard x nonlethal/lethal matrix (plus a
repeated current-sector interaction), asserting each warp survives the refresh, reports
the toll in the ticker, routes a lethal toll through the escape pod, and never crashes.

**Goal:** fix the first-click crash and lock it down before broader UI work.

- Reproduce with a minimal fixed state in a Textual Pilot test: an undetected or
  newly detected black hole in the current sector, click its sector object/action,
  receive `HazardDamage`, and refresh the game screen.
- Trace the exception through discovery selection, `GameScreen` refresh, event
  rendering, and possible escape-pod replacement. The core already has entry-hazard
  tests; fix the DTO/TUI stale-reference or event handling defect rather than
  suppressing the exception.
- Cover nonlethal damage, lethal damage, repeated selection, and save/autosave after
  damage. The notification must state hull damage and the source.

**Acceptance:** first mouse click and keyboard activation behave identically and
never crash for nonlethal or lethal damage.

Commit: `playtest: WP-PR05 black-hole interaction crash`

### WP-PR06 — Asteroid-belt domain and UI correction — complete

**Goal:** enforce the existing DESIGN §4.2 statement that belts are minable spatial
features, not landable colony planets.

- Audit generation and normalization so asteroid belts always have zero colonists,
  no allocation, no colony stores, no citadel/progress/treasury, and no orbital
  planet starbase. Retain raw-mining output through a dedicated extraction action or
  clearly specified passive cache; do not use colony stores if that exposes planet
  affordances.
- At the reducer boundary reject `Descend`, `Colonize`, colony transfers,
  `BuildCitadel`, planetary banking, invasion, and `DeployGenesis` for belts with
  specific errors. Centralize capability predicates by planet type.
- Extend DTOs with capabilities (landable, colonizable, extractable, supports
  stores/citadel) so `PlanetScreen` renders a belt-specific orbital/mining view and
  never infers legality from labels.
- In Computer and Sector views, label belts as asteroid belts rather than ordinary
  planets while keeping route selection and discoveries available.
- Normalize legacy saves on load or tolerate inert legacy fields; document the
  compatibility choice. Update DESIGN §4.2 if the extraction/cache mechanics need
  clarification.

**Tests:** generation invariants over seeds, every rejected command, extraction,
DTO capabilities, legacy decode, no land/citadel/store controls in Pilot/snapshots.

Commit: `playtest: WP-PR06 asteroid-belt interaction model`

### WP-PR07 — Planet logistics and colonist settlement — complete

**Scope note:** the original transfer editor issued one clamped reducer call per row and
Load-all/Unload-all iterated the trio. The §8 follow-up now routes those aggregate actions
through `BatchTransferCargo`, producing one atomic command/event group; focused row Load /
Unload / Settle actions remain `TransferCargo` / `SettleColonists`.

**Goal:** provide one legible transfer editor and allow adding colonists to an
already owned colony.

- Add or extend a core command for ship-to-owned-planet colonist settlement. It must
  require same sector, player/corporation authorization, a colonizable world, a
  positive amount no greater than ship occupants, and remaining habitability. Move
  the clamped accepted count atomically; do not route it through initial `Colonize`,
  whose purpose is claiming an unowned world.
- Replace one-commodity-at-a-time prompts in `PlanetScreen` with a transfer form:
  one row per commodity, `−` and `+` buttons stepping by 10, an editable exact
  numeric field, clear aboard/store maximums, and per-row validation. Add “Unload
  all” and “Load all” actions that compute a valid aggregate without exceeding ship
  holds or available stores.
- Include a colonist row for unloading people to owned worlds; never mix colonists
  into cargo-hold arithmetic. State clearly that colonists cannot be loaded back
  aboard through this form unless a separately authorized emigration rule exists.
- Prefer a batch transfer command so “all” is one transaction/event group and cannot
  partially mutate on failure. If adding it, update codec/protocol/replay fixtures.
- Preserve keyboard order: row field, decrement, increment, then aggregate buttons;
  Enter submits and inline errors retain focus.

**Tests:** owned-world top-up, habitability clamp/error, ownership and location,
commodity conservation property, batch atomicity, exact/step/all Pilot flows,
compact 80x24 geometry.

Commit: `playtest: WP-PR07 planet transfer workbench`

### WP-PR08 — StarDock information architecture and scoped actions — complete

**Deferred:** the bespoke DS9-style station-concourse raster (imagegen → image-to-ANSI
pipeline) is not done — the `imagegen` skill was unavailable in this environment. The
Colonists tab ships a compact ASCII concourse banner (`_CONCOURSE_ART`) as a stand-in;
swapping in the generated raster is a follow-up. Everything else in PT-02..07/29 is done.

**Goal:** make StarDock tabs self-contained, purchasable catalogs stable, and the
Tavern/colonist workflows understandable.

- Rename Devices to **Devices & Armaments**. Put Genesis torpedoes, homing missiles,
  fighters, both mine types/stocks, probes, interdictor, and mine deflector into one
  projected catalog with price, carried quantity/capacity, affordability, and a
  stable item id. `B` buys the selected row; amount-purchased items open an amount
  prompt. Remove separate global G/I/F/M purchase bindings.
- Preserve active tab and selected stable row key after every purchase, including
  Devices & Armaments. Do not restore by index when filtering can change the rows.
- Make R/N bindings active only while Tavern is active and D/W only while Bank is
  active. Use dynamic `check_action`, pane-local buttons, or scoped widgets; footer
  discoverability must match actual availability.
- Add a **Colonists** tab with berth occupancy, incentive per recruit, affordable/
  available count, amount entry, and recruit-all-up-to-capacity. Move K recruitment
  into this tab.
- Create the station-concourse art requested by the playtest using the `imagegen`
  skill in the implementation turn, then pass the approved raster through the
  repository's image-to-ANSI pipeline. Commit the source/derived asset according to
  existing art policy, include attribution/provenance metadata, provide
  high-contrast/monochrome fallbacks, and hide or shorten it at compact size.
- Redesign the bounty board from one “Notice” column into structured rows/cards:
  target, reason/type, reward or threat, status, and relevant destination/action.
  Change `TavernDTO.bounties` from voiced strings to DTO records; retain prose in a
  detail panel. Empty state should explain how bounties appear.
- Exclude or disable the currently flown hull in Shipyard. Recommended: retain it
  as a clearly marked “CURRENT” comparison row but make purchase impossible at both
  projection and reducer layers; `B` explains why without rebuilding the screen.

**Tests:** tab-scoped key matrix, stable row-key selection after repeated purchase,
all catalog reducers, colonist capacity/affordability, structured bounty projection,
current-hull rejection, compact/contrast snapshots.

Commit: `playtest: WP-PR08 StarDock scoped service UX`

### WP-PR09 — Computer prioritization and navigation continuity — complete

**Notes:** PT-31 (route flash-back) did not reproduce — plotting from Trade/Ports/Planets/
Codex/Leads/Map already lands on Route (fixed by the WP-UI20/21 remembered-subview work);
locked with a regression test. Grouping-under-sort is a new `DetailTable.set_rows(group_first=…)`
priority-group (owned planets/base ports, active contracts) that survives any user column sort.
Finished contracts are kept as a bounded (12) most-recent tail, dim, with actions disabled.

**Goal:** make owned infrastructure and completed work visible, and eliminate
surprising tab jumps.

- Extend `PlanetDirEntry` with `owned_by_you`/ownership kind and sort player-owned
  (and corporation-owned, if applicable) entries first, then preserve the existing
  user-selected column/direction within each group. Show an ownership marker.
- Extend `PortDirEntry` with attached starbase id/name, whether that base is owned by
  the player/corporation, and market/service status. Player-base ports sort first,
  then normal sorting. Preserve fog-of-war: only explored ports and known base facts.
- Keep terminal contracts in the Computer projection instead of filtering through
  `contracts.active(player)`. Add `status` to `ContractDTO`; group active first and
  render completed/failed/expired rows dim/grey with actions disabled. Decide a
  bounded history policy if persisted contracts are currently pruned.
- Make avoid-list discovery obvious in Navigation/Notes: an “Add sector…” button,
  visible `V` hint in route context, row action on route/port/planet tables, and Help
  documentation. Continue using `ToggleAvoid` and display ids.
- Fix route plotting from another subview by updating the remembered Computer
  category/subview state before rebuilding. The final visible pane must be Route;
  there must be no one-frame route flash followed by the former tab. Test links from
  Ports, Planets, Leads, Contracts, and Map.
- Sorting/grouping must use stable row keys and retain the selected target after
  refresh when it still exists.

**Likely files:** `edge/core/dto.py`, `edge/server/session.py`,
`edge/tui/screens/computer.py`, contract helpers, protocol codec tests, Computer
Pilot/snapshot tests.

Commit: `playtest: WP-PR09 Computer ownership and route UX`

### WP-PR10 — Responsive shell, status drawer, and nav rose — complete

**Progress (2026-07-11):** the first implementation slice makes the projected
backtrack edge the default NavRose selection (with first-edge fallback), adds
explicit Up/Down traversal to the Status Drawer object list, verifies the shared
onboarding visibility switch for both objective presentations, completes the Help
legend, and removes Port/StarDock decorative art at 80x24. Compact StarDock
snapshots were intentionally refreshed. The follow-up completes the parametric
80x24 geometry inventory across Sector, Computer, Lobby, Port, StarDock, Planet,
Surface, Contact, Encounter, Territory, Base, Help, and shared detail modals; it
also adds high-contrast and monochrome baselines for the previously uncovered
Port, Planet, Surface, Territory, and Base families. Multi-hop and generated
one-way-wormhole tests cover NavRose backtrack focus and its first-edge fallback.

**Goal:** finish responsive and keyboard behavior missed by the UI overhaul.

- Objectives have one source of truth. When `show_onboarding` is false, remove both
  `ObjectivesStrip` and the sidebar objectives detail; when re-enabled, both return.
  Completion state remains persisted independently of visibility.
- Inventory every art-bearing screen (at minimum Port, StarDock, Planet, Surface,
  Contact, Encounter, Territory, Base/service screens, and modal details). Add
  compact rules that hide/reduce decorative art and preserve controls in scrollable
  containers. Extend the WP-UI22 geometry test parametrically rather than adding
  isolated assertions.
- Convert Status Drawer object lines into a focusable list/table. Up/Down moves,
  Enter opens the same planet/port/discovery/starbase/contact action as the sector
  object, Escape closes, and the initial row is sensible. Disabled objects explain
  why. Mouse behavior remains equivalent.
- Record the previous sector in the fog-safe navigation projection or derive it from
  the last `Warped` event. Mark that warp `kind="backtrack"` and initially focus it
  in `NavRose`; do not reorder spatial placement. On first sector/no return edge,
  retain current focus behavior.
- Document every nav-rose symbol in Help: closer/deeper/level arrows, unexplored,
  backtrack, one-way, avoided, content codes, and hazard markers. Keep labels in
  sync with `WarpOption` rather than duplicating stale glyph definitions.

**Tests:** objective visibility matrix, all art screens at 80x24, keyboard-only
drawer flows, backtrack focus after multiple warps and one-way travel, Help content,
high-contrast/monochrome snapshots.

Commit: `playtest: WP-PR10 responsive shell and nav polish`

### WP-PR11 — Deployment list and legality projection — complete

**Completed (2026-07-11):** Territory now projects typed, stable-key
`DeploymentOptionDTO` affordances from pure core predicates shared by the reducers.
The TUI renders one vertical sequence at every layout tier, shows stock/purpose and
the exact blocker, disables impossible buttons, and makes accelerator keys report
the same blocker before opening a form. Focus restoration uses option ids. The DTO
addition intentionally bumps the wire protocol to v8; compact/standard/wide and
alternate-theme snapshots cover the new list.

**Goal:** replace the six-card grid with a readable vertical action list and disable
impossible deployments before submission.

- Replace `TerritoryScreen`'s Grid with a `VerticalScroll` list. Each row contains a
  compact image/glyph, title and purpose, carried stock, legality/blocker text, and
  one focusable action button. Wide mode may allocate more detail horizontally but
  must remain a single vertical sequence.
- Extend `TerritoryDTO` with per-action affordances, preferably a typed
  `DeploymentOptionDTO(id, quantity, enabled, blocker, active)`. Compute legality
  through shared core predicates: Core prohibition, stock, existing ownership,
  device installed, service-point requirement, interdictor state, and any sector
  conflicts. Reducers remain authoritative.
- Disable buttons and dynamic hotkey actions when unavailable. Grey rows with the
  exact blocker; accelerators must notify the same blocker instead of opening a form.
- Preserve focus/scroll position after deployment by stable option id.

**Tests:** affordance/reducer parity matrix, Core and zero-stock states, installed
device states, keyboard traversal, focus restoration, compact/wide snapshots.

Commit: `playtest: WP-PR11 deployment action list`

### WP-PR12 — Error specificity and set-piece art — complete

**Completed (2026-07-11):** Genesis eligibility is split into `genesis_has_device` and
`genesis_eligible` (the valid-target axis) on `PlanetDTO`, plus a `genesis_blocker` string
computed by the shared core predicate `planets.genesis_blocker` — the `DeployGenesis`
reducer raises the very same message the projection shows (reducer/UI parity, tested). The
PlanetScreen shows the Genesis affordance only when unblocked and otherwise names the reason;
`action_genesis` reports the specific blocker. Starbase assaults now project
`EncounterDTO.target_kind == "starbase"` with the base's owner archetype and a stable
per-base seed, so the encounter screen draws `edge/art/port.py` starbase art instead of a
ship sprite; ordinary alien/PvP fights keep `target_kind == "ship"`. Wire bumped to v9.

**Goal:** close the remaining small but visible feedback defects.

- Split Genesis eligibility into at least `has_device` and `valid_target` in
  `PlanetDTO`, plus a human blocker computed from shared core predicates. Attempting
  deployment with no torpedo says “No Genesis torpedo aboard”; an owned,
  ineligible-type, asteroid-belt, or otherwise blocked target names that reason.
  `DeployGenesis` must raise the same specific errors.
- When assaulting a starbase, render the target's starbase/port archetype using
  `edge/art/port.py` and its stable id/archetype seed, not a ship sprite. Keep normal
  alien/PvP combat ship art unchanged. Add a target-kind field to encounter DTO only
  if role/class data is insufficient.

**Tests:** Genesis blocker matrix at reducer and UI, starbase assault snapshot in
default/high-contrast/monochrome modes, ordinary ship encounter regression.

Commit: `playtest: WP-PR12 precise errors and assault art`

## 5. Recommended execution order

1. WP-PR05 first because it is a crash and should produce a minimal regression fix.
2. WP-PR01 through WP-PR04 next; these change combat/world semantics and may affect
   projections used by later UI packages.
3. WP-PR06 and WP-PR07 establish planet capabilities and logistics before their UI
   is polished elsewhere.
4. WP-PR08 and WP-PR09 reshape StarDock and Computer DTOs.
5. WP-PR10 through WP-PR12 finish cross-screen accessibility, deployment, and copy.

WP-PR01, WP-PR02, and WP-PR03 should be developed serially because they overlap
combat and movement reducers. WP-PR08 and WP-PR09 can be independent after their
DTO contracts are settled. Avoid combining all work into one schema epoch unless
multiple persisted fields genuinely require it; most additions are projection-only.

## 6. Verification and handoff requirements

Every package must include focused tests and finish with:

```text
pixi run ruff check .
pixi run mypy edge/core edge/bigbang edge/store edge/server edge/engine
pixi run pytest <focused test files>
pixi run check
```

For TUI packages, add keyboard and mouse Pilot coverage, an 80x24 geometry check,
and snapshots at 80x24, 100x34, and 120x40 where visual structure changes. Refresh
only intentional baselines and inspect default, high-contrast, and monochrome output.

Each handoff should state:

- the playtest notes closed by number;
- any DESIGN/config/protocol/schema changes;
- focused and full verification results;
- snapshot files intentionally changed;
- any follow-up explicitly deferred.

## 7. Completion criteria

The remediation is complete when all 31 notes are covered by passing automated
tests, the scripted acceptance pass in `docs/PLAYTEST_NOTES.md` has been rerun, no
global StarDock shortcut performs a context-inappropriate action, combat/world
state remains replay-deterministic, all primary workflows work at 80x24, and the
documentation and Help accurately describe the resulting controls and rules.

**Not yet met:** PT-23's per-row avoid action in §8 remains open, so the remediation is
not fully complete against the plan as written. (PT-06's station-concourse art and PT-30's
belt raw-mining output were closed 2026-07-11.)

## 8. Outstanding follow-ups (deferred, still open)

These were consciously deferred during implementation and are **not** resolved.
They are tracked here so a struck-through playtest note never hides open work.

- ~~**PT-06 — station-concourse art (WP-PR08).**~~ **Done (2026-07-11).** A generated,
  DS9-like hopeful recruitment concourse now runs through the existing Chafa image-to-ANSI
  seam. Explicit full-colour, high-contrast, and monochrome raster variants feed a 56×8
  standard panel and 72×12 wide cinematic panel; compact 80×24 hides the decoration,
  and the prior ASCII banner remains the missing-asset/Chafa fallback. Provenance lives in
  `images/ui/stardock/PROVENANCE.md`.
- ~~**WP-PR07 — batch transfer command (optional).**~~ **Done (2026-07-11).**
  `BatchTransferCargo` now makes Load-all/Unload-all a single reducer result and persisted
  command/event group, clamps all three rows against shared hold capacity in stable commodity
  order, and preserves exact conservation. Row actions remain focused `TransferCargo` /
  `SettleColonists` commands. Codec, wire v11, replay coverage, and DESIGN §4.2 are updated.
- ~~**WP-PR06 / PT-30 — belt raw-mining output.**~~ **Done (2026-07-11).** The `MineBelt`
  command is the dedicated extraction action: a turn cost (`planets.mining_turn_cost`) that
  hauls the belt's yield (Equipment, `planets.asteroid_mining`, clamped to free cargo holds)
  aboard and emits `BeltMined`. The shared pure seam `planets.belt_mining_yield` is used by
  the reducer, the owned-world `produce` auto-collect, and the `PlanetDTO.mine_yield`
  projection; the PlanetScreen orbital panel shows an `[M] Mine belt` affordance (belt-only
  via `check_action`). Wire bumped to v10. DESIGN §4.2 updated. Tests in
  `tests/test_asteroid_belts.py` (fill/clamp/full-holds/out-of-turns/non-belt + projection).
- ~~**WP-PR09 / PT-23 — per-row avoid action.**~~ **Done (2026-07-11).** `V` now
  directly toggles the highlighted sector in the Ports, Planets, and Route tables; stable
  row keys preserve the intended target across table sorting/repainting. Other subviews retain
  the sector prompt, and the Notes button remains the explicit full-list entry point.

### 8.1 Post-hoc audit (2026-07-11) — undocumented gaps in landed WP-PR05–PR09

A line-by-line re-diff of the implemented WPs against their plan bullets surfaced the
following, which were **not** previously tracked. **All were closed** in the follow-up commit
`playtest: WP-PR-followup close §8.1 audit gaps`; the entries are kept as a record.

- ~~**WP-PR05 — missing save/autosave-after-damage test.**~~ **Done.**
  `tests/test_ui_black_hole.py::test_black_hole_damage_survives_save_and_reload` warps into a
  *generated* black hole (so the `Warp` replays it) and asserts `state_hash` round-trips.
- ~~**WP-PR06 — sector-view belt labelling.**~~ **Done.** `SectorObjectList` now labels a belt
  "— Asteroid Belt (Orbit)" (not "(Survey)"), so the sector view marks the type.
- ~~**WP-PR07 — workbench polish + test gaps.**~~ **Done.** Control order is now
  `[field] [−] [+]`; `Enter` in the amount field unloads/settles the row; added a
  commodity-conservation **property** test and an **80×24 geometry** test.
- ~~**WP-PR08 — cursor-by-index, no bounty detail panel, no new snapshots.**~~ **Done.**
  The buy-tab cursor is restored by **stable row key** (`get_row_index`), not an index; the
  bounty board has a **detail panel** mirroring the highlighted row's prose (updates on
  `RowHighlighted`); added compact + high-contrast/monochrome **snapshots** for the Devices &
  Armaments, Colonists, and Tavern tabs.
- ~~**WP-PR09 — port market status + thin route-plot test.**~~ **Done.** `PortDirEntry` gained
  `starbase_market_open` (surfaced in the port row); the route-plot regression now covers
  plotting from **Ports, Planets, and Map**.

**Not audited here:** the UI/UX overhaul (`UI_UX_OVERHAUL_PLAN.md`, WP-UI01–23) was
completed in earlier sessions and closed by WP-UI23; this pass did not re-diff it bullet by
bullet, so any latent gaps there remain unassessed. One cross-cutting intersection worth a
look: WP-UI15's "changing tabs/subviews preserves selected rows" vs. WP-PR08's index-based
StarDock cursor restore (above). *(That re-diff was subsequently done — see §8.2.)*

### 8.2 WP-UI01–UI22 audit (2026-07-11) — unresolved overhaul items

A follow-up **bullet-level re-diff of the UI/UX overhaul** (`UI_UX_OVERHAUL_PLAN.md`) against
the implemented tree. All 23 WP-UI packages are committed and WP-UI23 (closeout) is complete;
the items below are **unmet implementation/verification bullets** discovered by the audit —
none block the shipped experience, but each is a spec bullet that is not satisfied. The audit
was **targeted** (existence of each package's key deliverables + its named verification tests),
not an exhaustive behavioural replay, so absence of a finding is not proof of full conformance.

**Unresolved — feature/behaviour bullets:**

- ~~**WP-UI09 — no before/after derived-stat swap/install preview.**~~ **Done (2026-07-11).**
  Selecting exactly one carried component and one slot now shows reducer-validated before/after
  deltas for shields, warp speed, combat speed, turns/warp, gun damage/rate, and efficiency.
  Invalid pairings show the authoritative blocker. The read-only server projection derives from
  the reducer's unapplied result, so preview numbers cannot diverge from the eventual command.
- ~~**WP-UI11 — objectives not reopenable *from Help*.**~~ **Done (2026-07-11).** When
  objectives are hidden, contextual Help exposes a visible `[O] Show Captain's objectives`
  button and binding. Restoring persists the preference and recomposes the underlying screen
  immediately; Options retains its equivalent toggle.

**Unresolved — missing verification bullets (behaviour present, gate absent):**

- ~~**WP-UI03 — no automated contrast gate.**~~ **Done (2026-07-11).** A numerical WCAG
  relative-luminance suite now gates readable semantic text at 4.5:1 and focus, selection, and
  disabled indicators at 3:1 across every background/surface/panel in all three themes. The
  audit caught and corrected selection colors that
  were slightly below 3:1 rather than merely adding a test around the existing palette.
- **WP-UI04 — no corrupt-settings-recovery test.** `edge/tui/settings.py` does recover from a
  missing/corrupt/newer file (`try/except (OSError, TypeError, ValueError, JSONDecodeError)` →
  defaults), so the behaviour is present, but there is no test asserting the plan's "A corrupt
  preferences file does not prevent startup." Follow-up: add a focused loader test (garbage JSON
  → defaults + one warning, startup proceeds).

**Spot-verified present (no action):** WP-UI01 docs (`UI_MOCKUPS.md`, `UI_INSPIRATION.md`,
`docs/ui/`, `docs/shots/`); WP-UI02 Textual **8.2.8** pinned in `pixi.lock` + `pytest-textual-snapshot`
in `pyproject.toml`/DESIGN §15; WP-UI05/06 `LayoutTier` + `ActionDescriptor`/`screen_actions` with
reserved-key, descriptor-parity, and destructive-confirmation guards (`test_ui_actions.py`);
WP-UI10 `STARBASE_WORKBENCH_PROFILE` + structural test that both Engine Room and Station use the
one `ComponentWorkbench` (`test_component_workbench.py`); WP-UI14 one `TradePanel` across port /
StarDock / base; WP-UI17 standing meter + reasoned disabled replies; WP-UI21 `DetailTable`
sorting/filtering/stable-key; WP-UI22 geometry + collision + destructive checks.

**Cross-check resolved:** the WP-UI15 "preserve selected rows" vs. WP-PR08 index-cursor concern
(noted in §8.1) is closed — WP-PR08's cursor is now restored by stable row key (§8.1, done).
