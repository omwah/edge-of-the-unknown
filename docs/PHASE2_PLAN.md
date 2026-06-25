# Phase 2 — Exploration & Discovery (the pivot phase)

> Companion to `DESIGN.md`, `PHASE1_PLAN.md`, and `PHASE1_5_PLAN.md`. DESIGN is
> the authoritative *what*; this is the *how and in what order* for Phase 2. Where
> the two disagree, DESIGN wins and is corrected in the same change (CLAUDE.md).
>
> **Status: reviewed draft — open decisions resolved.**

## Context

Phase 1 (+ 1.5) shipped a playable, deterministic trading skeleton: a warp-graph
universe with distance bands, spatial display ids, port pair-trading with live
pricing and haggling, SQLite persistence via command-log replay, an engine tick
loop, and a Textual game screen wired to a real in-process `GameService`. The
TUI already carries **stub screens** for everything Phase 2 fills in —
`PlanetScreen`, `SurfaceScreen`, `AlienContactScreen`, `EngineRoomScreen`,
`StarDockScreen`, `ComputerScreen` — currently fed by `edge/tui/dummy.py`
sample DTOs. Phase 2's TUI work is largely **replacing dummy data with real
service projections**, not building screens from scratch.

Phase 2 is **the pivot**: it turns a trading game into an exploration game. Per
DESIGN §14, the exit criterion is *"a one-hour push-out-and-return exploration
run is fun and yields tech that trading alone could not buy."* That sentence
dictates the spine: the **engine-room component model** (so there is tech to
*install*), **friendly alien barter + discoveries** (so there is tech trading
*cannot* buy), and the **discovery loop** (so pushing out is the way to get it).

This plan decomposes Phase 2 into eleven work packages across four milestones,
ordered so each milestone is independently playable and the highest-risk core
change (the engine room, which makes ship aspects *derived*) lands first while
the golden-master rail is still small.

All work obeys the architecture rules in CLAUDE.md: downward-only layer deps
(`core` has no I/O / async / Textual imports), all randomness through the
state-owned RNG, economy/movement/encounter invariants in core, every constant
in config, the TUI only through the `GameService` + `session` projection
boundary. `ruff` + `mypy --strict` stay green on
`core/bigbang/store/server/engine`; `tui/` is exempt. `pixi run check` (ruff +
mypy + pytest) and `pixi run cov` (~98%) are the gates.

---

## Scope and non-goals

**In scope (DESIGN §14 Phase 2):**

1. Engine-room subsystem/component model (§4.1) — slotted Spindrive / Thrusters /
   Screens / Main Gun, the shared component vocabulary with tech tiers, **derived
   aspects**, component install / swap / cannibalize upgrades.
2. StarDock services (shipyard, hardware emporium, bank) + multiple ship types
   from config.
3. Typed planets with band-weighted ownership, BNT-style production shaped by
   `planet_type` / habitability, and player colonization / claiming of unowned
   worlds (§4.2, §8).
4. Derelict orbital starbases as scavengeable component caches (the engine-room
   *cannibalize* action feeding the component economy) (§4.2).
5. Discovery system: distance-banded rarity tables (wrecks, nebulae, black holes,
   entities), sensor-based detection of hidden finds, discovery codex (§7).
6. Planet descent with surface sites (ruins, artifacts, ancient tech, crashed
   ships) (§7).
7. Friendly-disposition alien species with tech levels, drawn from a config
   roster, placed by band (§6).
8. Config-driven dialogue (§6.7: standing-keyed line pools, persona voice,
   variant / recency variability) and a derived conversation-verb menu.
9. Alien contact screen: latinum sales and artifact barter for aspect upgrades
   (engine / shields / sensors / cloak / holds) (§6).
10. Genesis torpedoes.
11. Computer screen: pair-trade finder, discovery codex, alien dossier (route
    planner already shipped in 1.5).

**Explicitly deferred to Phase 3 (DESIGN §14), so Phase 2 must not build them
but must leave clean seams:**

- **All hostile-band species and combat.** Phase 2 places only friendly-band
  aliens; no encounter-opens-with-violence, no fight/flee rounds, no threat /
  interception use. The `EncounterScreen` stays a stub.
- **Localized combat damage + field-kit repair.** Phase 2 builds the engine-room
  *model* (slots, derived aspects, install / swap / cannibalize) but components
  are never *knocked out* yet — there is no damage source. The knocked-out
  state, the field-patch repair-kit action, and full StarDock restoration of
  damaged components are wired structurally but exercised in Phase 3. (StarDock
  *upgrade/swap* is Phase 2; *repair of battle damage* is Phase 3.)
- **Starbase planetary-system defense** and **repair/claim of derelict bases into
  forward footholds**. Phase 2 ships derelict bases as salvage caches only.
- Signature mechanics, alliances-as-joinable-blocs, inter-species grudges,
  attitude *souring* from aggression (no aggression yet), NPC traders moving real
  goods, sector fighters / mines, alignment / experience.

The seam pattern is already established: `rules._should_interrupt` (rules.py:188)
is the Phase-1 stub where Phase 3 injects the encounter roll. Phase 2 adds
analogous stubs rather than half-implementing Phase 3 systems.

---

## Cross-cutting: persistence & the golden-master rail

This is the single most important constraint to get right, so it is stated once
here and referenced by every WP.

State is reconstructed as **`generate(seed, config)` + replay(command log)**
(service.py:42, snapshots.py `rebuild`). Two consequences:

1. **Everything the big bang creates is deterministic from the seed** and is
   *not* persisted per-entity — it is regenerated on load. So new bigbang output
   (subsystems, species, discoveries, ownership, starbases) needs **no codec /
   schema work**: it must only be a pure, RNG-disciplined function of
   `(seed, config)`. Adding these is "free" with respect to persistence.

2. **Player progress flows through the command log.** Every new player action
   (install a component, colonize a world, salvage a wreck, barter for an
   upgrade, log a discovery) is a new `Command` that must be added to
   `edge/store/codec.py` (`encode_command` / `decode_command`) so replay
   reproduces it exactly. New `Event`s that the Log tab renders also get
   `encode_event` / `decode_event` entries. **Codec coverage is asserted** —
   `tests/test_codec.py` should round-trip every command/event variant; add a
   `assert_never`-style exhaustiveness guard so a new command can't silently
   skip the log.

3. **Golden masters.** `state_hash` covers the frozen entities (not the runtime
   caches — `adjacency`, `core_hops`, `spatial_ids` are excluded). Any new field
   on a hashed entity (e.g. `Ship.subsystems`, `Planet.owner`,
   `Player.codex`) **changes the hash**, so the golden-master fixtures in
   `tests/` must be **regenerated in the same commit that adds the field**, with
   the regeneration noted in the commit message. Bump `config_version` (currently
   1) **once** at the start of Phase 2 to mark the schema epoch; do not bump it
   per-WP. Prefer landing all entity-field additions for a milestone together so
   the golden master is regenerated once per milestone, not once per WP.

The RNG-ordering rule deserves emphasis: the big bang draws from `state.rng` in a
fixed sequence, and golden-master replay depends on that order. **New generation
steps append to the end of the existing draw sequence** (or take a derived
sub-RNG, the §5 "perturbed sub-seed" pattern) so they do not shift the draws that
ports/planets/StarDock already consume. Where a step is logically independent
(e.g. discovery salting), give it its own `random.Random(seed ^ salt)` so its
draws never interleave with topology/economy draws.

---

## Milestones

- **M6 — Engine room & StarDock economy.** WP1 + WP2. Ship aspects become derived
  from slotted subsystems; StarDock sells components and hulls; the component
  economy exists. *Playable: the Phase-1 "first upgrade" is replaced by real
  slotted upgrades and a hull purchase.* (M1–M5 were Phase 1.)
- **M7 — Living worlds.** WP3 + WP4. Typed planets gain ownership and production;
  the player colonizes unowned worlds; derelict orbital starbases are
  component-salvage caches. *Playable: a deep-space production foothold + free
  components from a derelict.*
- **M8 — Discovery.** WP5 + WP6 + WP10. The universe is salted with band-banded
  discoveries; sensors gate hidden finds; planet descent reveals surface sites; a
  codex logs them; Genesis torpedoes. *Playable: the push-out-and-find loop.*
- **M9 — Aliens.** WP7 + WP8 + WP9 + WP11. Friendly species populate the bands;
  the contact screen speaks config-driven dialogue and barters discoveries for
  tech the player cannot otherwise buy; the Computer's pair-trade finder, codex,
  and dossier tie the loop together. *Hits the Phase-2 exit criterion.*

---

## WP1 — Engine room: subsystems, components, derived aspects (§4.1)

The spine. Today `Ship` carries **flat aspect scalars** (models.py:97–126);
Phase 2 makes the player ship's `shields` / `warp_speed` / `combat_speed` /
main-gun aspects **derived from four slotted subsystems**, while NPC hulls keep
flat aspects (the optional-`subsystems`-block rule, §4.1). This must land first
because every later upgrade source (StarDock hardware, alien barter, derelict
salvage) installs *components*, and Phase 3 combat *damages* them.

**Core data model (`edge/core/models.py`, `edge/core/enums.py`).**
- Add enums: `Component` (`accelerator`, `converter`, `radiator`, `secondary`,
  `turbine`, `burner`, `linkage`, `navigator`), `ComponentTier` (I/II/III),
  `Subsystem` (`spindrive`, `thrusters`, `screens`, `main_gun`; plus
  `fusion_reactor` for WP4 bases).
- New frozen entities: `InstalledComponent(kind: Component, tier: ComponentTier,
  knocked_out: bool = False)` and `SubsystemState(slots: tuple[InstalledComponent
  | None, ...], keystone_index: int | None)`. A subsystem is a fixed-length slot
  tuple; `None` = empty slot. `knocked_out` exists in the model now but is never
  set true in Phase 2 (Phase 3 combat sets it).
- `Ship` gains `subsystems: Mapping[Subsystem, SubsystemState] | None = None`
  (None ⇒ flat-aspect NPC hull) and `repair_kits` already exists. The flat aspect
  fields (`shields`, `warp_speed`, `combat_speed`) **stay on `Ship`** as the NPC
  fallback and as the *cache the derived value is written into* — see below.

**Derived aspects (`edge/core/engine_room.py`, NEW — pure core).**
- `derive_aspects(ship, config) -> ShipAspects` computes `shields`, `warp_speed`
  → `turns_per_warp`, `combat_speed`, and main-gun damage/rate from the filled
  slots and their tiers via config formulas; plus the **spindrive efficiency
  rating** → the one global combat bonus (§4.1). For a `subsystems=None` hull it
  returns the flat scalars unchanged.
- **Derive-on-write.** Reducers that change slots recompute and store the flat
  aspect scalars onto the `Ship` (the existing fields), so everything downstream
  (flee math, `turns_per_warp`, the sidebar) keeps reading plain aspects with no
  change, and `state_hash` stays a function of stored fields. `engine_room.py`
  owns the formula; `rules` calls it whenever subsystems change. This keeps the
  derived values *in* the hash deterministically and avoids a read-time
  projection that could drift.
- Caps emerge from `(slot count × max tier)` (§4.1) — no separate cap number.

**Config (`edge/core/config.py`, `config/default.yaml`).**
- `ComponentTierPrices` (Tier I latinum, Tier II latinum + barter-equiv, Tier III
  barter-only — the §8 economy constants already name these:
  `tier_i_component_latinum`, `tier_ii_component_latinum`).
- `SubsystemLayout` per subsystem: slot count, `legal_components`, `base_component`
  per base slot, `keystone` component (navigator / burner / secondary / —, §4.1).
- Aspect formulas: per-subsystem `{base, per_component, per_tier}` coefficients and
  the spindrive-efficiency → global-bonus table (modeled on the manual's chart).
- Extend `ShipClassConfig` (config.py:130) with an **optional `subsystems`**
  block; the starter `trailblazer` (default.yaml:69) gains the layout "complete
  but minimal — every base slot filled, every upgrade slot empty" (§4.1), making
  it the canonical first upgrade target.

**Reducers (`edge/core/rules.py`) + commands.**
- `InstallComponent(subsystem, slot_index, component, tier)` — consume a component
  from the hold / inventory (or, at a service, from purchase — see WP2/WP9), place
  it, recompute aspects. Validate slot legality + tier ceiling.
- `SwapComponent(subsystem, slot_index, ...)` and `Cannibalize(subsystem,
  slot_index)` (pull a component into a portable component inventory — feeds WP4
  salvage and barter).
- **Component inventory:** add `Ship.components: Mapping[(Component, ComponentTier),
  int]` (loose parts not yet installed), conserved across install / cannibalize
  exactly as cargo is conserved across trade (a core invariant + property test).
- `FieldPatch(subsystem, slot_index)` — spends one `repair_kit` to un-knock-out a
  component. **Structurally present, no-op-reachable in Phase 2** (nothing is
  knocked out yet); fully exercised in Phase 3.
- Events: `ComponentInstalled`, `ComponentRemoved`, `Repaired`. Add all to the
  codec (commands round-trip, events encode + decode for the Log tab).

**Projection (`edge/server/session.py`, `edge/core/dto.py`).**
- `EngineRoomDTO` (promote from dummy.py): per-subsystem slot grid (keystone /
  filled-with-tier / empty / knocked-out), the derived aspect each subsystem
  yields, the global efficiency bonus, repair-kit count, loose-component
  inventory. Add `engine_room_view(state, player_id)` to `session` + `GameService`.
- The sidebar's "subsystem-integrity line" (§11): a compact one-liner flagging any
  knocked-out component (always clean in Phase 2).

**TUI (`edge/tui/screens/engine_room.py`).** Wire the existing stub (engine_room.py)
to `engine_room_view`; the four `_SubsystemPanel`s render real slots; `install` /
`cannibalize` actions issue the new commands. Field-patch present but inert.

**Tests.** `tests/test_engine_room.py` (NEW): derive_aspects formula across slot/
tier combinations; cap emergence; component conservation under install/cannibalize
sequences (hypothesis property test); starter hull derives exactly the Phase-1
flat numbers (a regression pin so the existing balance is unchanged). Codec
round-trip for the new commands/events. **Regenerate golden masters** (Ship gains
`subsystems`/`components`).

---

## WP2 — StarDock services & multiple ship types

Replaces the Phase-1 single flat "first upgrade" (`BuyUpgrade`, rules.py:312) with
the real services hub (DESIGN §11, §8).

**Config.** A `ship_classes` list (config.py / default.yaml) of buyable hulls
beyond the starter — at minimum the §4 v1 set (Scout Marauder, Missile Frigate,
BattleShip, Imperial StarShip) with `role`, aspects or a `subsystems` layout,
`turns_per_warp`, `price`. A `hardware` catalog: components for sale by tier with
prices (Tier I latinum per the economy block).

**Reducers + commands (`edge/core/rules.py`).**
- `BuyComponent(component, tier)` — latinum → a loose component in the hold (then
  `InstallComponent` from WP1 installs it). Tier III is **not** purchasable for
  latinum (barter-only, §8) — validated.
- `BuyShip(ship_class_id)` — latinum → swap the player's hull, carrying the
  starter subsystem layout for the new class. **Trade-in / migration rule:** the
  old hull is credited back at a config fraction of its purchase price toward the
  new one, and its installed components return to **loose inventory** in the hold
  (reinstallable into the new hull's legal slots via `InstallComponent`). If the
  returned components plus existing cargo would exceed the new hull's holds, the
  swap is **refused** — the player must sell components down to make room first.
- `RepairAtDock(...)` — full restoration of knocked-out components ≈ 25% of tier
  price (§8). Inert in Phase 2 (no damage), live in Phase 3.
- **Retire `BuyUpgrade`.** It is removed from `rules.py` (rules.py:312), its
  command/event from `store/codec.py`, and the `Upgraded` event from
  `core/events.py`. The Phase-1 golden master / `test_tui_flow` hardware path is
  re-cut against `BuyComponent`+`InstallComponent` (the `U` hotkey now opens the
  StarDock Hardware tab rather than firing a one-shot upgrade). Any saved command
  log that referenced `BuyUpgrade` is a Phase-1 artifact and is regenerated.

**Projection + TUI (`edge/tui/screens/stardock.py`).** The Hardware tab lists
buyable components (price, tier, latinum-vs-barter); the Shipyard tab lists hulls
with a stat comparison; Commodities (trade) and Bank already work (stardock.py).
Add `stardock_view` to `session` / `GameService` for the hardware + shipyard
catalogs (fog-of-war: only what this dock offers).

**Tests.** `test_service` / `test_rules`: buy component → install → derived aspect
rises; buy ship → cargo migrates, holds clamp; Tier III latinum purchase rejected.
`test_tui_flow`: Hardware tab buys+installs; Shipyard tab swaps hull.

---

## WP3 — Typed planets: ownership, production, colonization (§4.2, §8)

Planets are type-only today (models.py:87, populate.py:116). Phase 2 makes them
**owned territory that produces**.

**Core model (`edge/core/models.py`).** `Planet` gains: `owner` (a tagged value:
`none` / `alliance_id:int` / `player_id:int`), `inhabited_by_species_id: int |
None`, `colonists: int`, `allocation: Mapping[Commodity, float]` (+ a fighters
share later), `stores: Mapping[Commodity, int]`, `habitability_cap: int`,
`yield_profile: Mapping[Commodity, float]`, `citadel_level: int = 0`,
`starbase_id: int | None` (WP4). Represent `owner` as a small frozen
`Ownership(kind, ref)` to keep the three-way explicit and hashable.

**Config (`config/default.yaml`).** Per-`planet_type` `yield_profile` +
`habitability` (the §4.2 table); colonist production rates, food/growth/starvation
constants (BNT model, §8/§A.3); the per-head `colonist_incentive` (recruitment cost,
§4.2) and a per-hull `colonist_capacity` on `ShipClassConfig` (the separate
occupancy limit); band-weighted **ownership** distribution (Core =
governor-owned; unowned fraction non-decreasing by band, §4.2). The existing
`_PLANET_WEIGHTS` (populate.py:42) covers types; add an ownership-weight table.

**Big bang (`edge/bigbang/populate.py`).** Extend planet seeding: Core planets →
`owner = core_governing_alliance_id` unconditionally; Hub heavily alliance-owned;
unowned fraction rises Frontier→Deep→Void (band-monotone). Set `habitability_cap`
/ `yield_profile` from the type. **Append these draws after the existing planet-
type draw** (golden-master ordering, see cross-cutting). Validate (WP-validate):
all Core planets governor-owned; unowned fraction non-decreasing across bands;
≥1 habitable Hub world (the §5 step-8 invariants — extend `bigbang/validate.py`).

**Engine cron (`edge/engine/`).** New `planet_growth` durable cron task
(cron.py / ticker.py pattern) running BNT production: colonists generate
ore/organics/equipment per allocation × `yield_profile`, capped by
`habitability`, with food consumption / growth; only an **owned** planet collects
output. `jovian` fuel-scoop / `asteroid_belt` mining produce without colonists;
`barren` produces nothing. The math is **pure core** (`core/economy.py` or a new
`core/planets.py`); the cron just schedules it. Events: `PlanetProduced`,
`ColonyGrew`.

**Reducers + commands.** `Colonize(planet_id, colonists)` — move colonists from
the ship to an **unowned colonizable** world, setting `owner = player_id` (the §8
claim path; Core worlds off-limits). `SetAllocation(planet_id, allocation)`.
**Colonists are recruited, not bought** (§4.2 — they are people with a choice, not
a commodity), so the load path is `RecruitColonists(source, count)`, not a hardware
purchase: two sources, (a) **StarDock's recruitment office** — pay a per-head
latinum *incentive* (config `colonist_incentive`) to enlist willing recruits, and
(b) **emigration from an inhabited world with positive disposition** toward the
player (alliance member in good standing, or an unaligned species at amicable
effective disposition — gated, no incentive or a lower one). Colonists ride a
**separate occupancy limit** `Ship.colonist_capacity` (a per-hull config stat),
**not** the cargo holds, so recruiting never competes with trade cargo; recruiting
is clamped to remaining capacity. Add `Ship.colonists` (current, ≤ capacity).
Events: `ColonistsRecruited`, `Colonized`. Codec + golden master.

**Projection + TUI (`edge/tui/screens/planet.py`).** Wire `PlanetScreen` (orbit
view) to a real `planet_view`: type, owner, colonists, allocation sliders, stores,
starbase status, and a Descend affordance (WP6). `Claim` / `Colonize` actions for
unowned worlds.

**Tests.** Property: production conserves goods into `stores`, never negative,
respects habitability cap; only owners collect. Bigbang validate across seeds
(ownership invariants). `test_engine` for the `planet_growth` cron determinism.

---

## WP4 — Orbital starbases & component salvage (§4.2)

Phase-2 slice per the roadmap: **derelict bases as scavengeable component
caches.** Defense and claim-into-foothold are Phase 3.

**Core model.** `Starbase` entity (engine-room model **minus** spindrive/thrusters,
**plus** `fusion_reactor`, §4.2): `id`, `sector_id`, `planet_id`, `owner`,
`ship_class_id`, `subsystems: {fusion_reactor, screens, main_gun}` reusing WP1's
`SubsystemState`, flat `armament`/`defenses` extras. **Derelict is emergent, not a
flag** (§4.2): a helper `is_operational(starbase)` = keystone reactor `converter`
present + minimal screens/gun — reuse the WP1 component-health logic.

**Big bang (`edge/bigbang/populate.py`).** Place orbital bases per config /
owner `starbase_policy`. Owned-planet bases are built **intact**; an
**unowned + uninhabited** world gets an `is_derelict` roll, and a derelict is
effected by **removing/damaging components** (so repair is just refilling slots).
Validate: any derelict base sits on an unowned/uninhabited planet; every base on
an owned planet is operational (extend `validate.py`, §5 step 8).

**Reducers.** Reuse WP1's `Cannibalize` against a `Starbase` subsystem slot
(strip a component into the ship's loose inventory) when the base is **derelict
or player-owned** (§4.2). No defense, no claim/repair in Phase 2 — but leave the
`is_operational` seam that Phase 3 uses for planetary-system defense.

**TUI.** Surface the base on `PlanetScreen` (a "derelict starbase — salvage"
affordance) and as a discovery in the sector view (a derelict base is itself a
find, §7). Salvage issues `Cannibalize`.

**Tests.** Bigbang derelict-placement invariants; salvage conserves components
(ship inventory gains exactly what the base loses).

---

## WP5 — Discovery system: rarity, phenomena, sensor detection, codex (§7)

The reward system. The universe is **salted at big bang** and finds are revealed
by entry + sensor checks.

**Core model.** `Discovery` entity (§4): `id`, `location` (sector_id or
planet_id + surface-site slot), `kind` (`wreck`, `nebula`, `black_hole`, `entity`,
`ruins`, `artifact`, `ancient_tech`, `crashed_ship`), `rarity_tier` (Common →
Legendary), `hidden: bool` (needs a sensor check), `payload` (a tagged value:
component(s) of a tier, latinum, an **artifact** barter-good, or a lore fragment),
`found_by: int | None`. `Player` gains `codex: frozenset[int]` (found discovery
ids) — §4 names it.

**Config.** Per-band rarity weight tables and per-tier payout tables (§7); the
barter-equivalence mapping (Rare ≈ Tier II, Exceptional ≈ Tier III, §8). Phenomena
behavior params: a **nebula sensor-interference value** and the black-hole
**one-way gravity-warp** target/turn-cost. Phase 2 ships only the
**navigational/sensor face** — the nebula is a real working detection modifier
(it lowers sensor detection inside it, dovetailing with the WP5 hidden-discovery
sensor gate and seeding the Phase-3 stealth mechanic), and the black hole is
flavor plus an **optional one-way gravity warp** (a movement-only effect:
relocate the ship + spend turns, touching the warp/movement path, not combat).
The black hole's **damage-on-approach** behavior is left as a configured-but-inert
seam switched on in Phase 3 with the rest of hazard combat (DESIGN §491 files
"hazards live" under Phase 3) — Phase 2 has no damage source.

**Big bang (`edge/bigbang/` — new `discoveries.py` step, called from
`generator.py`).** Roll every sector and planet on its band's rarity table; salt
surface sites onto planets (ruins/artifacts/ancient tech/crashed ships), with the
least-habitable deep worlds favored for the richest ruins (§7). **Use a dedicated
sub-RNG** (`random.Random(seed ^ DISCOVERY_SALT)`) so discovery draws don't shift
the topology/economy/port/planet draw order (golden-master safety — see
cross-cutting). Validate: mean rarity **and** value strictly increasing across
bands (§5 step 8 / §13).

**Detection + reducers.** Entering a sector reveals **obvious** features
automatically (the sector projection already lists contents); **hidden**
discoveries (`hidden=True`) require a sensor roll — `Ship.sensor_rating` vs the
discovery's tier — performed on entry (extend `_warp` / `_travel`, or a `Scan`
command for an explicit sweep). `Salvage(discovery_id)` / `Investigate(...)`
collect the payload into the hold (components / latinum / artifact) and add the id
to `codex`. Costs turns. Events: `DiscoveryDetected`, `DiscoveryCollected`. Codec
+ golden master (`Player.codex`).

**Projection + TUI.** Sector view shows detected discoveries; the Computer's
**Codex** tab (WP11) lists found discoveries with location, rarity, and lore
fragments (rumor pins from lore fragments are a nice-to-have). Sensor rating
becomes a visible progression axis in the sidebar.

**Tests.** Property/golden: discovery placement deterministic from seed; rarity/
value gradient monotonic across bands (bigbang validate, 100 seeds). Sensor-gate:
a hidden find below sensor threshold is not revealed; collecting it conserves the
payload into hold/inventory + adds to codex idempotently.

---

## WP6 — Planet descent & surface sites (§7)

**Reducers.** `Descend(planet_id)` (costs turns, §7) opens the surface; `Explore`
(site-by-site) reveals one surface-site discovery at a time, rolling sensor-gated
hidden sites; `Ascend`. Surface sites are `Discovery` rows located at
`planet_id + site_slot` (WP5). Reuse WP5's collect/codex path. Events:
`Descended`, `SiteExplored`. Codec + golden master if surface-site state lands on
an entity (recommend: keep sites as `Discovery` rows seeded at big bang, so only
`codex` + a per-planet "explored sites" set on `Player` need persisting through
the command log).

**TUI (`edge/tui/screens/surface.py`).** Wire the existing `SurfaceScreen` stub
(surface.py) to a real `surface_view`: terrain panel + site list + per-site detail;
`Explore` / `Sensor sweep` / `Log to codex` actions issue the commands. The
`PlanetScreen` `Descend` action (planet.py) pushes it.

**Tests.** `test_tui_flow`: descend → explore site → log discovery (the §13 named
UI flow). Descent turn-cost accounting; explore reveals exactly the seeded sites
for a seed.

---

## WP7 — Friendly alien species & roster (§6)

Phase 2 places **only friendly-band** species (hostiles are Phase 3), drawn from a
config roster, so the contact/barter loop has partners without combat.

**Config (`config/alien_roster_default.yaml`, NEW — a named roster file, §6).** Author
the **full §6.1 parameter set** for every species entry, not just the part Phase 2
runs. The **friendly-path subset Phase 2 actually exercises** is `name`,
`archetype_id`, `disposition_center` + `disposition_variance`, `alliance_id` +
`alliance_role`, `tech_level`, `home_region` hint, `trade_posture`, `treaty_mode`
(the friendly values), `persona`, `dialogue_pack` (WP8), `attitude_gain_rate`, and
a **tech-offer table** (which components/aspect upgrades it sells/barters at which
tier, gated by effective disposition). The hostile/Phase-3 params (`threat_rating`,
`interception_rating`, `combatant`, `pack_behavior`, `signature_mechanic`,
`betrayal_model`, `memory_model`, `fleet`, `starbase_policy`) are **authored in
full now as Phase-3 forward-compat** but **unused in Phase 2**: the schema carries
them and the roster validator checks them for **reference integrity** (every
`alliance_id` / `signature_mechanic` id / enum resolves), while no Phase-2 code
path reads them. This front-loads authoring so Phase 3 switches systems on rather
than re-authoring the roster; the accepted cost is that those fields are proven
only by static validation, not by gameplay, until Phase 3.

**Core model (`edge/core/models.py`).** `AlienSpecies` entity (the §4 field set);
`Player.species_attitudes: Mapping[int, float]` (per-species offset) — **raised by
trading/favors only in Phase 2** (no aggression to lower it yet). `effective_
disposition(species, player)` helper in a new `core/aliens.py`: `clamp(base +
offset, 0, 1)`. The Federation stays an ordinary `Alliance` (already so,
populate.py:130) with the player seeded as a member.

**Big bang (`edge/bigbang/`).** Draw a **seeded subset** of the roster (not all),
draw each species' base disposition from its bounded spread (§6 per-generation
variance), and assign home regions by band — but with the Phase-2 placement
**clamped to the friendly band** for every band (so no hostiles spawn). Append
draws after existing steps (golden-master ordering). Validate: mean disposition
non-increasing across bands holds trivially (all friendly now); ≥1 friendly
contact per band (the §5 step-8 resupply invariant); roster reference integrity
(every `alliance_id` resolves).

**Tests.** Bigbang: seeded subset is deterministic; all placed species
friendly-band; per-band contact-point invariant. `effective_disposition` clamps.

---

## WP8 — Dialogue system (§6.7)

Config-driven, persona-voiced, standing-keyed conversation with non-repeating
variability. Pure core (no I/O), consumed by the contact/encounter screens.

**Config.** A `dialogue_pack` schema: `context_key` (greeting, trade_open,
trade_refuse, treaty, farewell, dossier_other, …) → list of conditional
**line entries**, each with a `when` predicate (standing band / treaty / grudge /
mechanic-stage) and a **variant pool** (multiple phrasings). Persona packs provide
the **generic fallback**; species packs override. Templated `{placeholders}`.

**Core (`edge/core/dialogue.py`, NEW).** `select_line(species, context, ctx_vars,
recency, rng) -> (text, new_recency)`: resolve species → `persona` → generic
fallback; filter entries by `when`; pick a variant from the pool **avoiding the
last K** via a recency ring; fill placeholders. `Player.dialogue_recency:
Mapping[(species_id, context), tuple[int, ...]]` (§4 names it) — the persisted
no-repeat ring (cosmetic but persisted for reproducible playback, so it rides the
command log via the contact commands).

**Validation (`bigbang/validate.py` or a roster validator).** Dialogue integrity
(§13): every species resolves a non-empty pool for each reachable context key;
every placeholder is fillable; `dossier_other` covers every nameable species.

**Tests (property, §13).** Selection never repeats a variant within the K-deep
ring when the pool has > K entries; species→persona→generic fallback resolves;
placeholder filling total over the reachable context set.

---

## WP9 — Alien contact: tech barter + latinum sales (§6, §11)

Where discoveries become tech trading cannot buy — the **exit-criterion payoff**.

**Reducers + commands (`edge/core/rules.py`).** `Hail(species_id)` / contact opens
a conversation (no combat — friendly only). `BuyAlienTech(offer_id)` — latinum →
a component / loose part / aspect upgrade, gated by effective disposition tier
(§6). `BarterArtifact(artifact_discovery_id, offer_id)` — trade a discovery
artifact (its rarity → component-tier equivalence, §8) for a **Tier II/III**
component that no latinum sale offers. Trading/bartering **raises the attitude
offset** (`attitude_gain_rate`), unlocking higher tiers (the favor loop). Events:
`AlienTraded`, `AttitudeChanged`. Codec + golden master (`species_attitudes`,
`dialogue_recency`).

**Projection + TUI (`edge/tui/screens/contact.py`).** Wire `AlienContactScreen`
(contact.py) to a real `contact_view`: the **opener line from WP8**, a **derived
verb menu** (verbs enabled/disabled from species params — a greyed verb shows
*why*, §6.7), the tech-offer list (latinum price and/or barter-equivalence shown
side by side so the player can weigh cash vs artifact, §8), and the **dossier
panel** narrating other species (WP8 `dossier_other`). The verb menu is *derived*,
not authored (§6.7) — `contact_view` computes it from posture/treaty_mode/standing.

**Tests.** `test_service`: barter an artifact → receive a Tier-III component that
no `BuyComponent` offers (proves "tech trading cannot buy"); attitude rises with
trade and unlocks a tier. `test_tui_flow`: hail → buy/barter → verb-menu disable
reasons render. Dialogue lines come from the pack (WP8).

---

## WP10 — Genesis torpedoes

A device that transforms a planet (the classic TW2002 terraform/create). Scope to
the §4.2 planet-type model: `GenesisTorpedo` is a `Ship.devices` counted item
(bought at StarDock); using it on an eligible target **creates or re-types** a
planet (e.g. barren → a colonizable terrestrial), re-rolling its `yield_profile`/
`habitability`. Reducer `DeployGenesis(target)`; validate eligibility; event
`GenesisDeployed`. Codec + golden master (planet retype is a command-log effect,
so it replays deterministically). Small WP; can ride with M8.

**Tests.** Deploy retypes the planet deterministically; ineligible target rejected;
replay reproduces the retype.

---

## WP11 — Computer screen: pair-trade finder, codex, dossier (§11)

The query console that ties the loop together (route planner already shipped in
1.5; Map/Log already folded in).

- **Pair-trade finder** (`core/economy.py` helper + `computer_view`): score
  opposed-class port pairs by round-trip profit per turn using the live price
  model + shortest-path distance (§11). Pure core scoring; projection ranks the
  player's known ports.
- **Codex tab** (`computer_view`): every found discovery with location, rarity,
  lore fragments (WP5/WP6).
- **Dossier tab**: known species, disposition, attitude, alliance/player standing,
  last-seen tech offers; narrated in a chosen faction's voice where configured
  (§6.6/§6.7 — the dossier line pool from WP8).

**TUI (`edge/tui/screens/computer.py`).** Fill the Ports / Codex / Dossier tabs
the stub (computer.py) already reserves; the Trade tab becomes the live pair-trade
finder.

**Tests.** Pair-trade finder ranks a known-profitable pair first (deterministic
fixture); codex/dossier projections reflect collected finds / met species.

---

## WP12 — Durable engine maintenance (cron effects survive reload)

A persistence-correctness gap the rest of the plan silently depends on. State is
reconstructed as **`generate(seed) + replay(command log)`** (snapshots.py:69
`rebuild`), but the engine ticker's cron effects do **not** flow through that
path. `EngineTicker.step` (ticker.py:59) applies each due cron via
`GameService.apply_maintenance` (service.py:62), which mutates live state and
appends the cron's *events* to the `event_log` — and the event log is **not** a
rebuild input. So on reload every cron-driven mutation is lost: port stock regen,
daily interest accrual, the daily turn reset, and (new in WP3) `planet_growth`
production/colony growth all rewind to their command-only values. The schedule is
lost too — the tick counter and each cron's `next_due` (ticker.py:45–51) live only
in the ticker instance, and `Game.day_number` is written to `meta` once at
`new_game` (service.py:38) and never re-saved — so a reloaded game restarts the
cron clock at tick 0, violating the §9/§12 promise that "a reloaded save never
double-runs or skips a tick." `export_save` (snapshots.py:82) inherits the same
gap, so portable saves are affected identically.

This blocks nothing in M6–M9 *within a single session* (the ticker keeps live
state correct while running), but it must land before Phase 2 ships, or any
save/resume silently corrupts the economy and colony state. Independent of every
gameplay WP; recommended to land right after **M7** (WP3's `planet_growth` is the
most visible loss) but valid any time.

**Approach (recommended): one ordered, replayable timeline.** Keep the
"command log is the source of truth" model rather than snapshotting derived state.
Make maintenance a durable, replayable entry interleaved with player commands in a
single monotonic sequence, so `rebuild` reproduces state exactly:
- Persist each cron firing as a `MaintenanceTick(cron_name, tick)` record (a new
  durable log, or a typed entry in a **unified ordered log** alongside
  `command_log` — ordering across the two streams must be total, since interest
  accruing *before* vs *after* a player's purchase changes the result). Add it to
  `edge/store/codec.py` like any command/event.
- `apply_maintenance` (service.py:62) appends the `MaintenanceTick` to that log
  the moment it fires (same immediate-commit durability as `append_command`).
- `rebuild` (snapshots.py:69) replays the merged stream in `seq` order, re-running
  the **pure** cron reducer (`cron.fn` from cron.py) for each `MaintenanceTick` —
  no derived state is stored, only the fact and tick that it fired, so the
  determinism rail and `state_hash` stay honest.
- **Persist the schedule.** Store the ticker's `tick` counter and each cron's
  `next_due` (a small `engine` meta table or columns) and restore them in
  `continue_game`, so firing resumes mid-interval without double-running or
  skipping. Re-save `Game.day_number` when the daily reset fires (today it is
  written only at `new_game`).

**Rejected alternative:** periodic full-state snapshots (the gzipped-JSON path
§12 anticipates) would also fix it, but it departs from pure replay, duplicates
the golden-master rail, and is deferred — note it here so the choice is explicit.

**Tests.** A recorded session that warps, trades, **then ticks** (interest +
port regen + planet growth fire) reloads to an **identical `state_hash`** — the
proof the maintenance timeline replays (extends the existing
`test_load_game_reconstructs_identical_state`, which currently reloads *before*
any cron fires and so passes blind to this gap). Schedule round-trips: a reload at
tick N re-fires the next cron at exactly its original `next_due`, never twice,
never skipped (deterministic ticker-driven fixture). Codec round-trip +
exhaustiveness for `MaintenanceTick`. `export_save`/`import` of a ticked game
round-trips identically.

---

## WP13 — Multi-round haggle sessions (§8)

The haggle **engine** shipped in Phase 1 — `HaggleOffer` + `_haggle` (rules.py),
`resolve_haggle`/`haggle_acceptance_probability` (economy.py), `HagglingConfig`
(`insult_frac` / `max_rejections` / `history_penalty`), the `Haggled` event, codec,
and tests. A follow-up wired a **single counter-offer** into the trade UI
(`HaggleScreen` modal, `H` on the port / StarDock screens, the read-only
`haggle_quote` hint) so haggling is real and visible. What is **not** yet built is
the full mini-game the design and the original mockup imply: an
**accept / counter / walk-away loop over multiple rounds**, with the port's patience
wearing thin as the player keeps pushing.

**The blocker (why it was deferred).** `_haggle` calls
`haggle_acceptance_probability(..., recent_attempts=0)` — the history penalty exists
in config but is always fed zero, because nothing tracks how many times the player
has already haggled this port today. Wiring a real `recent_attempts` means the count
is **player progress that must survive replay**: state is reconstructed as
`generate(seed) + replay(command log)`, so the count cannot be ephemeral UI state —
each `HaggleOffer` must carry (or the reducer must derive) a value that is identical
on replay. Today's single-offer flow is replay-safe precisely because it pins
`recent_attempts=0`.

**Approach.**
- **Track attempts in the command log, not the UI.** Add per-(player, port, day)
  haggle-attempt tracking to core state (e.g. a small map on `Player`, reset by the
  `daily_turn_reset` cron), incremented inside `_haggle` on each non-accepted offer
  and read as `recent_attempts`. Because it is mutated by the reducer and reset by a
  durable cron (WP12), it reconstructs exactly under replay — no new command field
  needed. Enforce `max_rejections`: once exceeded, the port closes negotiation at the
  fair price for the rest of the day.
- **Promote the modal into a session screen.** Turn the Part-1 `HaggleScreen` into a
  stateful accept / counter / walk loop showing "Round N of M", the running quote,
  and the live `haggle_quote` hint; each counter issues a `HaggleOffer` and the
  screen reacts to the `Haggled` result until accept / walk / exhaustion.
- Optional persona flavour line per round (ties into the §6.7 dialogue work).

**Tests.** History penalty actually lowers acceptance across rounds (deterministic
seed); `max_rejections` closes negotiation at fair; the attempt counter round-trips
through reload (golden-master) and resets on the daily cron; Pilot flow for the
multi-round screen.

---

## Suggested order / commits (phase-tagged, small)

Grouped by milestone; land each WP's entity-field additions + golden-master
regeneration together.

1. `p2: WP1` engine room — subsystems, components, derived aspects (core + config
   + EngineRoomScreen). *Bump `config_version`; regenerate golden masters once.*
2. `p2: WP2` StarDock hardware + shipyard + multiple ship classes.  → **M6**
3. `p2: WP3` typed planets — ownership, BNT production cron, colonization.
4. `p2: WP4` orbital starbases + derelict salvage.  → **M7**
4a. `p2: WP12` durable engine maintenance (cron effects survive reload).
   *Independent infra; recommended here, where saved worlds first need to persist
   production. May land any time before Phase 2 ships.*
5. `p2: WP5` discovery system — rarity tables, sensor detection, codex.
6. `p2: WP6` planet descent + surface sites.
7. `p2: WP10` Genesis torpedoes.  → **M8**
8. `p2: WP7` friendly alien species + roster file.
9. `p2: WP8` dialogue system (config + core + validation).
10. `p2: WP9` alien contact — tech barter + latinum sales.
11. `p2: WP11` Computer — pair-trade finder, codex, dossier.  → **M9 (exit
    criterion)**

Within a milestone, the order above is the dependency order. WP8 must precede WP9
(contact needs dialogue). WP1 must precede WP2/WP4/WP9 (they install components).
WP5 must precede WP6/WP9 (surface sites and barter consume discoveries). WP3
should precede WP4 (starbases hang on planets). WP12 depends only on the cron set
existing (WP3's `planet_growth` is the last cron added this phase), so it can land
any time after M7 but **must** precede the Phase-2 ship.

---

## Verification

- **Core property tests (hypothesis).** Component conservation under
  install/cannibalize/barter (mirrors the goods-conservation pattern);
  derive_aspects monotonic in slot count/tier; planet production never negative,
  capped by habitability, owner-only collection; discovery payloads conserved on
  collect; dialogue no-repeat within the K-deep recency ring (§13);
  effective-disposition clamp.
- **Golden-master replays.** Regenerate per milestone (entity-field epochs);
  every replay green afterward. The proof that new commands replay: a recorded
  log that installs a component, colonizes a world, salvages a derelict,
  descends + explores, and barters an artifact reproduces the same `state_hash`.
- **Codec exhaustiveness.** `test_codec` round-trips every new command and event;
  an exhaustiveness guard fails the build if a command type is missing from
  `encode_command`.
- **Save fidelity under ticking (WP12).** A session that *ticks* before saving
  (interest, port regen, planet growth fire) reloads to an identical `state_hash`,
  and the cron schedule resumes at the original `next_due` — never double-run,
  never skipped (§9/§12). Distinct from the golden-master replays above, which
  exercise the command log; this one proves the maintenance timeline replays too.
- **Bigbang validation (100 seeds, `bigbang/validate.py` + `test_bigbang`).** New
  §5 step-8 invariants: all Core planets governor-owned; unowned fraction
  non-decreasing across bands; ≥1 habitable Hub world; any derelict base on an
  unowned/uninhabited world while owned-planet bases are operational; discovery
  rarity **and** value monotonic across bands; all placed species friendly-band
  with ≥1 contact per band; roster + dialogue reference integrity (§13).
- **Determinism / RNG ordering.** A regression test asserting the Phase-1 port/
  planet placement is **unchanged** by the new generation steps (proves the new
  draws were appended / sub-RNG'd, not interleaved) — guards the golden-master
  rail at generation time.
- **Textual Pilot (`test_tui_flow`).** Engine room install/cannibalize; StarDock
  buy component + swap hull; planet colonize; descend → explore site → log
  discovery (§13 named flow); hail alien → buy/barter tech → verb-menu disable
  reasons. All read through the service projection only.
- **Manual / exit criterion.** `pixi run edge`: a one-hour push-out run —
  trade near home, slot a first upgrade, push a band out, detect + salvage a
  discovery, descend a planet, hail a friendly species, barter an artifact for a
  Tier-II/III component the StarDock does not sell, return. Confirm it is fun and
  yields tech trading alone could not buy (DESIGN §14 Phase-2 exit criterion).
- **Gates.** `pixi run check` (ruff + mypy --strict on
  core/bigbang/store/server/engine) green; `pixi run cov` holds ~98%.
