# Playtest Remediation Plan 02

Status: proposed
Source: `~/edge-notes/playtest_notes_02.txt` (25 observations, 12 July 2026)
Predecessor: [`PLAYTEST_REMEDIATION_PLAN_01.md`](PLAYTEST_REMEDIATION_PLAN_01.md) — **complete** (WP-PR01..PR12 + follow-ups all landed)
Findings table: [`PLAYTEST_NOTES.md`](PLAYTEST_NOTES.md) → "Second pass" (PT-32..PT-56)

## 1. Purpose

This plan turns the second hands-on playtest pass (after the first remediation
round shipped) into implementation-sized work packages. It is written so an agent
with **no** playtest context can pick up one package, implement it, test it, update
the docs, and hand it off independently. Read this section and §2 before touching
any package.

Preserve the project's **downward-only** dependency graph at all times:

- Game rules and legality live in `edge/core` (**no I/O, no async, no Textual
  imports**). Every random choice uses the game-state RNG (`state.rng` or a
  seed-salted sub-RNG), never `random` module globals.
- Fog-safe presentation data lives in `edge/core/dto.py` and is assembled in
  `edge/server/session.py`. The TUI (`edge/tui`) only renders DTOs and submits
  commands; it never reaches into core state.
- Dev-only dialogue authoring/playtest tooling (`edge/dialogue/authoring/`) is the
  one impure corner and the only place an upward `edge.tui` import is allowed.
- Any change to a **persisted** dataclass, command, or event requires matching work
  in `edge/store/codec.py`, the protocol codec (`edge/server/wire.py` /
  `protocol.py`), the wire **version bump**, migrations, `state_hash`, and golden
  replay fixtures. Projection-only DTO fields still bump the **wire** version but
  need no store migration. Each package below states which class it is.

**Every package finishes by updating documentation in the same commit:** strike
through the closed PT rows in `PLAYTEST_NOTES.md` and append the commit hash/subject
(exactly as the first-pass table already does), and update `docs/DESIGN.md` (and
Help copy) when the package changes a rule, config knob, or control. Sections that
almost always need a DESIGN touch are called out per package.

## 2. Resolved design decisions

These remove ambiguity in the raw notes. Four were settled by interview on
2026-07-12; the rest are stated here so an implementer does not re-litigate them.

1. **Tab-hotkey indicator (PT-32).** A tab's focus hotkey is its **accent-colored,
   underlined leading letter** inside the tab title (e.g. the "N" of "Navigation"),
   **not** a parenthesized letter. Monochrome/high-contrast themes must still make
   the accelerator legible — underline the letter so it survives loss of color.
   Pressing the accelerator, **or** pressing Enter while a tab header is focused,
   moves focus directly onto that tab's **primary content widget** (the first table
   / list / form control), collapsing today's two-step "select tab → then navigate
   in" flow to one step. Per-tab action bindings remain in the footer and are scoped
   to the active tab (the WP-PR08 `check_action` pattern).
2. **Rumor feedback (PT-35).** Buying a rumor opens a small dismissible **modal**
   that reveals the purchased lead's text, then the lead is filed to the computer as
   today. No ticker-only or silent path.
3. **Cloud City (PT-54).** Build the **full** subsystem, split into ordered sub-work
   packages (rules/staging → art → UI). Not a spec-only deferral.
4. **Scene compositing (PT-36/44).** **Split.** The transfer-modal overlay and the
   clamped/greyed transfer controls (PT-45/46/47, WP-PR2-06) are built directly. The
   dock-over-planet scene composite and its wreck slot (PT-36/44, WP-PR2-05) get a
   feasibility **spike** first: the compositing mechanism already exists
   (`SectorScene` hand-paints one character grid — `edge/tui/widgets.py:581`), so the
   spike de-risks *art quality*, not feasibility. Fallback carried in the WP: if the
   stacked-center layout reads poorly at compact 80×24, keep the current
   side-by-side layout there and only overlay at standard/wide tiers.
5. **Belt resource is finite and stored on the belt (PT-52).** Asteroid belts get a
   depletable ore reserve (a new persisted field on the belt planet record). Mining
   draws it down; the reserve does not regrow (or regrows only per an explicit, small
   config rate — decide and record in DESIGN §4.2). Art reflects the remaining
   fraction. This is a **persisted** change (codec/migration/replay).
6. **Discovery names are stored, deterministic, and fog-safe (PT-49).** A discovery
   carries a generated `name` derived from the game RNG at creation time so replays
   match. A combat wreck's name is the **destroyed ship's** name; other space finds
   draw from a seeded name table by kind. This is a **persisted** change.
7. **Partial-fighter invasion is UI-only (PT-53).** The `InvadePlanet` reducer
   already accepts `cmd.fighters` (`edge/core/rules.py:2251`); only the TUI commits
   all of them today. No core change — add an amount prompt.

## 3. Issue-to-package map

| Playtest note(s) | Package |
|---|---|
| PT-32 tabbed-screen keyboard model | WP-PR2-01 |
| PT-33 hardware buy focus, PT-34 Flying/Flown | WP-PR2-02 |
| PT-35 rumor reveal modal | WP-PR2-03 |
| PT-49 discovery names | WP-PR2-04 |
| PT-36 dock-over-planet composite, PT-44 wreck slot | WP-PR2-05 |
| PT-45 modal overlay, PT-46 greyed buttons, PT-47 clamped steppers | WP-PR2-06 |
| PT-48 one-way clarity, PT-55 trail colors match rose | WP-PR2-07 |
| PT-50 map legend colors, PT-51 map P-plot, PT-56 phantom edges | WP-PR2-08 |
| PT-39..PT-42 dialogue playtest tooling | WP-PR2-09 |
| PT-43 attack-screen button hotkeys | WP-PR2-10 |
| PT-38 species portrait `_01` selection | WP-PR2-11 |
| PT-37 NPC hub-drift pileup | WP-PR2-12 |
| PT-52 asteroid mining limits + finite + art | WP-PR2-13 |
| PT-53 partial-fighter invasion | WP-PR2-14 |
| PT-54 Cloud City (jovian) | WP-PR2-15 (a/b/c) |

## 4. Work packages

Each package lists: goal, the concrete changes, likely files, tests, the docs to
update, and the commit subject. "Likely files" are starting points found during
planning — confirm with a fresh search before editing.

---

### WP-PR2-01 — Tabbed-screen keyboard model — landed (with deferrals)

**Landed 2026-07-12** in `playtest: WP-PR2-01 tabbed-screen keyboard model`. A shared
`ServiceHub` (Stardock + Base) and the Computer screen now underline an accelerator
letter in each tab title, bind it to jump-to-tab-and-focus-content, and focus content
on Enter while the tab rail is focused (`edge/tui/widgets.py` `accel_title` /
`first_focusable` / `ServiceHub.activate_and_focus`). **Deferrals (see notes PT-32):**
(a) per-*subview* single-letter hotkeys on Computer are not built — categories get
letters, subviews are reached by arrows + Enter-to-content; (b) tabs whose only free
in-title letter is already an action binding (Stardock **Bank**, Base **Hardware**)
have no letter and stay arrow/Enter-reachable — closing these needs the action-binding
relocation the note anticipates, deliberately out of scope for this additive pass.

#### WP-PR2-01b — Computer: tab-owned keys — landed

**Landed 2026-07-12** in `playtest: WP-PR2-01b computer tab-owned keys`. WP-PR2-01 fixed
the accelerators but left the footer advertising every screen action on every tab. The
model is now inverted for the **Computer**, and this is the pattern the other tabbed
screens should adopt:

- **A tab owns its keys.** `ComputerScreen.PANE_BINDINGS` maps each subview id → its
  `(key, action, description)` triples, and the new shared `ActionPane` (`edge/tui/
  widgets.py`) binds them onto that subview's pane, dispatching into the `screen.`
  namespace so the handlers stay on the screen. Each **category** pane likewise owns the
  numbers `1`..`N` for its own sub-tabs (hidden from the footer; the number leads the
  sub-tab title), so `2` addresses a different tab in each category and can never reach
  into another's. Textual builds the binding chain outward from the focused widget, so a
  pane's keys are live — and in the footer — only while focus is inside it. **No
  `check_action` scoping and no global per-tab bindings.** The screen keeps only `Esc`
  (back), the category accelerators and Enter-to-content.
- **Key map** (interview, 2026-07-12): categories are **N**avigation / **C**ommerce /
  e**X**ploration / **R**elations / Log**b**ook. `C` is Commerce, so the old `C`-closes-
  the-Computer alias is gone (Esc closes). `X` and `R` were freed by moving Abandon and
  Remove-note onto **Delete** and Route-to onto **`W`** — the sector view's key for the
  same verb, so it means one thing everywhere.
- **Back leads the footer on every screen.** New `chrome.EdgeScreen` base (all 15 full
  screens) reorders `active_bindings` so Esc/Back is first; Textual's chain order had it
  trailing whatever the focused widget owned (on the Map tab it landed after Engage).
- **Consequences (all tested in `tests/test_ui_computer_keys.py`):** the footer offers
  exactly the visible tab's verbs and no navigation keys; a key may mean two things on
  two tabs (Delete abandons a favor on Contracts, removes a note on Notes —
  `action_remove_note` split out of the old dual-purpose `action_abandon_contract`);
  `action_descriptors` scopes the `.` menu / `?` help / palette the same way (with a
  parity test, and the guard in `tests/test_ui_actions.py` updated to allow the override
  and to see pane bindings).
- **Focus follows the visible tab**, because the scoping depends on it: accelerator,
  Enter-on-rail, `show_subview()` deep links, and mount all land focus on the tab's
  primary control, and `_follow_focus_to_visible_pane` never leaves it stranded in a
  pane that is no longer showing. `first_focusable` now honours a `focus-first` class,
  which `DetailTable` puts on its table — DOM order was handing focus to the filter
  `Input` above it, where the tab's action letters would have been typed as filter text.
- **`Records` → `Logbook` (accelerator `B`).** A focused `DetailTable` owns `O` (cycle
  sort), which sits between the table and the screen in the binding chain, so the old
  `O` accelerator was unreachable from the very place it had to work. Every letter of
  "Records" was taken by an action; the category was renamed rather than take a key away
  from the tables. Pane ids (`cat-records` / `log` / `notes`) are unchanged.

**Nothing is deferred:** all three tabbed screens (Computer, Stardock, Base) are on the
model. Computer sub-tabs are numbered `1`..`N` per category; the two services hubs take
letters only.

#### WP-PR2-01c — Stardock: tab-owned keys — landed

**Landed 2026-07-12** in `playtest: WP-PR2-01c stardock tab-owned keys`. The Stardock now
uses the WP-PR2-01b model. It is a *flat* tab row (no category level), so it keeps letter
accelerators and takes no sub-tab numbers — numbers exist on the Computer only to
separate a category's sub-tabs, which the Stardock does not have.

- **The shared `ServiceHub` carries the model**, so the Base screen inherits it for free
  when it is ported: hosts pass `actions` (tab id → triples), the hub builds each tab as
  an `ActionPane`, focuses the visible tab's content on mount and on every switch, and
  blurs before a programmatic switch (Textual re-activates whichever pane holds focus, so
  a stale focus silently reverts the switch). `StardockScreen` drops `check_action` /
  `_TAB_SCOPED` entirely and gains `action_descriptors`, scoped like the footer.
- **Key map** (interview, 2026-07-12): tabs are **C**ommodities · **S**hipyard ·
  **H**ardware · **D**evices & Armaments · Co**l**onists · **B**ank · Ta**v**ern. Two verbs
  moved to free those letters: **Haggle is `G`** (H names Hardware) and **Buy is
  `P`/Purchase** (B names the Bank). `G` haggles on the **Port** screen too — the Stardock
  hosts that same `TradePanel`, so the verb must not answer to two keys depending on the
  route in. `E` (Engine Room) is **Hardware's own key**, not a screen key — you buy a part
  and slot it in one errand. `Esc` (undock) is the only screen-wide verb left.
- **A focused text `Input` disarms a screen**, and this is now enforced centrally:
  `first_focusable` never auto-focuses an `Input` (only a `focus-first` nomination can).
  Landing on the Colonists amount field took every letter key as typing — the tab's verbs
  stopped firing, Textual dropped them from the footer, and even the accelerators that
  would have let you *leave the tab* were swallowed. This generalizes the `DetailTable`
  filter-box fix from WP-PR2-01b. Colonists nominates its Recruit button instead.
- **A pane with no focusable content must hold focus itself** (`widgets.focus_content`):
  the Bank is pure text, and a pane whose keys follow focus cannot fire them if it can
  never be focused — Deposit/Withdraw would have been advertised but dead.
- **Colonists typing affordance** (interview, 2026-07-12): the tab lands on its Recruit
  button, which leaves the digits free — typing one **starts an amount** (it fills the
  field and hands over focus, so the rest is ordinary typing and `Enter` recruits), and
  `+`/`−` step it without entering the field. The digits are pane keys kept off the footer
  (`PANE_HIDDEN`, carried by `ServiceHub` alongside `actions`). `AmountStepper`'s field is
  now `select_on_focus=False`: focusing used to select the whole amount, so the next
  keystroke *replaced* it instead of extending it — multi-digit typing was impossible.
- **Spelling:** `StarDock` → **`Stardock`** repo-wide (identifiers, strings, docs). This
  renames the projection DTO `StarDockDTO` → `StardockDTO`, which moves the wire
  fingerprint: **`WIRE_VERSION` 16 → 17**, `tests/fixtures/wire/{fingerprint.txt,
  envelopes.json}` regenerated. Projection-only, so no store migration.

#### WP-PR2-01d — Starbase: tab-owned keys — landed

**Landed 2026-07-12** in `playtest: WP-PR2-01d starbase tab-owned keys`. The last screen
onto the WP-PR2-01b model, and the one that pays for it. It cost almost nothing: the model
already lived in `ServiceHub` (WP-PR2-01c), so the screen just declares `PANE_BINDINGS`,
passes it to the hub, and drops its `check_action`-flavoured "switch to the X tab first"
guards, which are now unreachable — the key does not exist off its tab.

- **Status is a panel, not a tab** (interview, 2026-07-12). Status and Station are merged:
  Station leads with a bordered one-line **Status** panel (owner · standing · integrity),
  because standing is what you read *while* you act, not a place you navigate to. That
  makes **Station the one tab never withheld** — a hostile base shows nothing else, and
  Assault is its door; the installations half explains itself when the base withholds it.
  **Trade → Commodities**, matching the Stardock.
- **Key map:** tabs **S**tation · **C**ommodities · **H**ardware · **B**ank. Moving the
  verbs off the screen freed `H`, so **Hardware finally has an accelerator** (WP-PR2-01 had
  to leave it letterless), and `C`/`H`/`B` name the same services they do at the Stardock.
  Verbs: `R` repair, `V` salvage, `L` claim, `A` assault (Station); `T`/`G` trade, haggle
  (Commodities); `P` purchase, `M` missile (Hardware); `A`/`W` bank. Salvage is `V` and
  Claim is `L` because the accelerators took `S` and `C` — a pane key may never shadow one.
  **`A` is Assault on Station and Deposit on Bank** — one key, two verbs, two tabs, which
  is the reuse the whole model exists to allow.
- **A withheld tab keeps no keys — and neither does an impossible verb.** The Base gates
  its tabs by standing and service integrity; `ServiceHub` gives an unavailable entry *no*
  bindings. `_pane_actions` then drops any single verb this base cannot honour: you cannot
  **Assault** or **Claim** a base you already hold, repair a full rack, salvage an empty
  one, or buy munitions a base does not sell, so none of those reach the footer (they used
  to sit there and answer with a notification). Availability is now expressed by the
  **absence of the keys** rather than by a per-action predicate — the cleanest statement
  yet of why the model beats `check_action`.


**Goal:** give Computer, Stardock, and Starbase tabs (and Computer subtabs) accent-
letter focus hotkeys shown in the tab title, and make the hotkey **and** Enter-on-a-
tab drop focus straight onto the tab's primary content.

**Changes**

- Pick a unique accelerator letter per tab and subtab. Render it in the `TabPane`
  title as an **underlined accent-colored** letter (Rich markup, e.g.
  `[u]N[/]avigation`), with a monochrome fallback that keeps the underline. Keep the
  letter choice in one small table beside the screen so titles and bindings cannot
  drift.
- Add a binding per accelerator that (a) activates the matching `TabbedContent` tab
  and (b) focuses that tab's primary content widget. Add one helper, e.g.
  `_focus_primary(tab_id)`, that maps each tab id → its first focusable content
  widget id and calls `.focus()`.
- On `TabActivated` (arrow-key navigation) plus an Enter binding while a tab header
  is focused, call the same `_focus_primary` so Enter-into-a-tab lands on content.
- Keep per-tab action bindings footer-scoped via `check_action` (Stardock already
  does this at `edge/tui/screens/stardock.py:346`; mirror it in `base.py` and
  `computer.py`). Ensure the footer only shows bindings valid for the active tab.
- Do not collide with existing global bindings (Escape/back, `?` help, `.` action
  menu). If a natural letter is taken, choose another and keep it consistent.

**Likely files:** `edge/tui/screens/computer.py`, `edge/tui/screens/stardock.py`,
`edge/tui/screens/base.py`, `edge/tui/widgets.py` (if a shared helper fits),
`edge/tui/screens/help.py` (document the accelerators), tab/keyboard Pilot + snapshot
tests.

**Docs:** update Help legend (accelerator letters + Enter-to-content behavior). No
DESIGN change (pure TUI).

**Tests:** per-screen accelerator → correct tab + focus lands on primary content;
Enter-on-tab-header → content focus; footer shows only active-tab actions;
compact/standard/wide snapshots of the new tab titles; monochrome snapshot proving
the accelerator letter is legible without color.

Commit: `playtest: WP-PR2-01 tabbed-screen keyboard model`

---

### WP-PR2-02 — Stardock hardware focus and Flying/Flown labels

**Goal:** keep the just-bought hardware/shipyard row focused after purchase, and
label hulls **Flying** (current) vs **Flown** (formerly owned, not now).

**Changes**

- Reuse the WP-PR08 stable-row-key restore (buy → refresh → re-select by stable
  key via `get_row_index`, not by index). Apply it to the hardware/shipyard catalog
  the same way Devices & Armaments already does; find where the shipyard/hardware
  `DataTable` is rebuilt after `BuyComponent`/ship purchase and restore selection by
  key.
- Add a per-ship status to the Shipyard projection: `Flying` for the hull the player
  currently occupies, `Flown` for a hull class the player has owned before but no
  longer possesses, blank/purchasable otherwise. The "have I flown this before" fact
  needs a source — check whether player history already records prior hull classes;
  if not, derive it from the cheapest available signal and record the choice. If it
  requires a new **persisted** field, treat it as a persisted change (codec/replay);
  if it is projection-derivable, it is wire-only.

**Likely files:** `edge/tui/screens/stardock.py`, `edge/core/dto.py`,
`edge/server/session.py`, (possibly `edge/core/models.py` if a "flown hull classes"
set must persist), codec/replay tests if persisted, Shipyard Pilot + snapshot tests.

**Docs:** `PLAYTEST_NOTES.md` rows PT-33/PT-34. DESIGN only if a persisted field is
added (note it in §4).

**Tests:** buy a hardware row → same row stays selected (stable key); Flying label on
the occupied hull and rejection of its purchase (regression against WP-PR08 PT-29);
Flown label after switching hulls; snapshot of the Shipyard tab.

Commit: `playtest: WP-PR2-02 hardware focus and Flying/Flown labels`

---

### WP-PR2-03 — Rumor reveal modal — landed

**Landed 2026-07-12** in `playtest: WP-PR2-03 rumor reveal modal`. No event/DTO
schema change was needed: `action_buy_rumor` applies `BuyRumor`, reads the freshest
lead's summary from the existing fog-safe `leads_view` (the rumour appends its lead
last), then reveals it in `edge/tui/screens/rumor.py::RumorModal` over the rebuilt
tavern. The no-fresh-rumour path is the reducer's existing rejection (no modal).

**Goal:** reveal the purchased rumor's lead text in a dismissible modal on purchase.

**Changes**

- Find what `BuyRumor` returns today (`edge/core/rules.py:655`, `_buy_rumor` at
  `:1149`, `RumorHeard` event, `edge/dialogue/intel.py::pick_rumor`). Ensure the
  resulting `Lead`'s human text is available to the TUI — via the command result /
  a DTO field on the response, **not** by the TUI reading core state. If the text is
  only in the event, surface it through the service response the screen already
  receives.
- Add a small `ModalScreen` (pattern: `edge/tui/screens/transfer.py` /
  `confirm.py`) that shows the rumor/lead text with an `[Enter]/[Esc] Close` action,
  keyboard-navigable and dismissible. Open it from `action_buy_rumor`
  (`edge/tui/screens/stardock.py:486`) after a successful purchase; keep the
  existing "lead logged" ticker line as the breadcrumb.
- Handle the no-fresh-rumor path (already rejected by the reducer) without opening an
  empty modal.

**Likely files:** `edge/tui/screens/stardock.py`, new
`edge/tui/screens/rumor.py` (or inline modal), `edge/core/dto.py` /
`edge/server/session.py` if the lead text needs a response field, Stardock Tavern
Pilot + snapshot tests.

**Docs:** `PLAYTEST_NOTES.md` PT-35; Help "Tavern" copy if it mentions rumor flow.

**Tests:** buy rumor → modal shows the lead text → dismiss with keyboard and mouse →
lead present in computer; no-rumor-available path shows no modal; modal snapshot in
default/high-contrast/monochrome.

Commit: `playtest: WP-PR2-03 rumor reveal modal`

---

### WP-PR2-04 — Discovery names — landed

**Landed 2026-07-13** in `playtest: WP-PR2-04 named discoveries`.

- **`Discovery.name` is live state** (in `state_hash`), stamped at creation. Pools live in
  **config** per the constants rule: `names.discoveries` in `names_default.yaml`, keyed by
  `DiscoveryKind`, drawn combinatorially by a new `bigbang.naming.DiscoveryNamer` **without
  replacement** — no two finds in a universe share a name (the later raid-cache pass is seeded
  with the names already spoken for), and an exhausted pool falls through to numbering
  ("Black Hole 1"). A kind with no pool is legal.
- **A combat wreck takes the destroyed foe's own name** (`_combat_wrecks` reads `foe.name`), so
  the sector view reads "Wreckage of the Vesk Marauder VII" — the raider you just shot, not a
  generic hulk. The sector row names a wreck **before** salvage (a hulk is plainly a hulk, so it
  costs no fog); other finds stay "Anomaly detected" until scanned, as before.
- **Naming rides a names-only sub-RNG**, so it is replay-deterministic *and* cannot perturb
  placement. `test_naming_does_not_move_a_single_discovery` proves it by regenerating a seed
  against a config with **no name pools** and asserting identical placement — which is why this
  epoch needed no golden-replay churn at all.
- **No store migration, contrary to §2.6/this WP's plan.** The save is `(seed, command log)` and
  the universe is *regenerated* (`store.snapshots.rebuild`) — there is no discovery table, so
  there is nothing to migrate and no legacy row to back-fill. Wire **17 → 18** (projection-only:
  `SectorDiscovery.name`, `CodexEntry.kind`); fingerprint + envelope fixtures regenerated.
- **Projection/TUI:** `_discovery_label` leads with the name and trails kind/rarity as the
  subtitle it always was (a wormhole still leads with its one-way warning); the Codex's `name`
  column is now the find's name and a new **Kind** column carries what it *is*.

Tests: `tests/test_discovery_names.py` (named, unique, deterministic, placement-invariant,
in `state_hash`, pool fallback + exhaustion) and
`test_combat.py::test_a_combat_wreck_wears_the_destroyed_ship_s_name`.

**Goal:** give space discoveries stored, deterministic, flavorful names; a combat
wreck takes the **destroyed ship's** name.

**Changes (core / persisted)**

- Add a `name: str` field to the `Discovery` dataclass (`edge/core/models.py:302`).
  Generate it at creation time from the game RNG so replays are byte-stable. Add a
  small seeded name generator in `edge/core/discovery.py` keyed by
  `PayloadKind`/`DiscoveryKind` (wreck → ship-name table; nebula/black hole/etc →
  kind-appropriate table). Keep the tables in config or a module constant per the
  repo's "constants in config" rule — decide and record.
- Combat wrecks (created by the WP-PR01 path — `edge/core/rules.py` around the
  `wrecks:` tuple at `:2799`) must carry the **destroyed hull's** name rather than a
  generic draw. Thread the destroyed ship/NPC name into wreck creation.
- Persisted change: update `edge/store/codec.py`, the protocol codec, **bump the wire
  version**, add a migration that back-fills a name for legacy discoveries (a seeded
  default is fine), update `state_hash`, and update golden replay fixtures.

**Changes (projection / TUI)**

- Surface `name` on the discovery DTO (`SectorDiscovery` / codex DTO) and show it
  instead of "`<Kind> ∗ <rarity>`". The rarity/kind can remain as a subtitle.
- Update sector-scene labels (`edge/tui/widgets.py` `SectorScene`) and the Codex
  (`edge/tui/screens/computer.py`) to render the name.

**Likely files:** `edge/core/models.py`, `edge/core/discovery.py`,
`edge/core/rules.py`, `edge/core/dto.py`, `edge/server/session.py`,
`edge/store/codec.py`, `edge/server/wire.py`/`protocol.py`, migration + replay
fixtures, `edge/tui/widgets.py`, `edge/tui/screens/computer.py`, tests.

**Docs:** DESIGN §7 (discovery naming rule) + §13 if a new validation applies;
`PLAYTEST_NOTES.md` PT-49.

**Tests:** fixed-seed generation gives stable names; a combat kill's wreck name equals
the destroyed ship's name; legacy save decodes with a back-filled name; `state_hash`
round-trips; codex/sector snapshots show names.

Commit: `playtest: WP-PR2-04 named discoveries`

---

### WP-PR2-05 — Sector-scene compositing spike + wreck slot

**Goal (spike-gated):** composite Stardock/starbase/port art **over** the planet art
(hovering, centered), and reserve a slot for a wreck sprite when a planet already
occupies the sector.

**Step 1 — spike (deliver a short written finding + snapshots, no production commit
yet):**

- In `SectorScene.render` (`edge/tui/widgets.py:581`), the orbit band currently
  paints planet in the left half (`lcx`) and port in the right half (`rcx`) using
  `_paint` (transparent-space stamping). Prototype a **stacked-center** layout:
  paint the planet first, then paint the dock/port/starbase sprite centered on the
  same column so the planet shows around/behind it. Capture snapshots at 80×24,
  100×34, 120×40.
- Judge readability. Record the outcome in the WP handoff and in
  `PLAYTEST_NOTES.md` PT-36.

**Step 2 — implement (per the spike outcome):**

- If it reads well: change the orbit-band layout to stacked-center for standard/wide;
  keep side-by-side at compact 80×24 if the spike showed crowding (the §2.4
  fallback). Paint order planet → dock so the dock "hovers".
- Add a **wreck slot**: when a planet occupies the primary position and the sector
  also has a wreck discovery, place the wreck sprite in a distinct, non-overlapping
  position (the freed right/opposite half, or below the orbit band) so the wreck is
  visible alongside the planet. Record the layout rule in a comment.
- Preserve `_hotspots` for every sprite so clicks still route to the right entry.

**Likely files:** `edge/tui/widgets.py` (`SectorScene`), `edge/tui/art_adapter.py` if
a new sprite pairing is needed, sector-scene snapshot tests.

**Docs:** `docs/ui/UI_MOCKUPS.md` §1 if the sector-scene layout spec changes;
`PLAYTEST_NOTES.md` PT-36/PT-44.

**Tests:** planet+dock composite snapshots at all three tiers; planet+wreck slot
snapshot; hotspot click routing for planet, dock, and wreck; compact fallback
snapshot if used.

Commit: `playtest: WP-PR2-05 dock-over-planet composite and wreck slot`

---

### WP-PR2-06 — Transfer modal overlay and clamped controls

**Goal:** overlay the transfer modal on the planet screen without blanking the
background; grey unavailable transfer buttons; clamp `+`/`−` to the available amount.

**Changes**

- `TransferWorkbenchScreen` is a `ModalScreen` (`edge/tui/screens/transfer.py:34`).
  Make it visually **overlay** the planet screen: keep the dimmed/rendered background
  visible instead of a solid fill (Textual modal transparency — set the modal
  screen's background transparent or a translucent tint, and confirm the underlying
  `PlanetScreen` still paints). Verify at all tiers and in monochrome.
- Grey out (disable) a row's Load/Unload/Settle button when its source is empty:
  Load disabled when stores of that commodity are 0, Unload disabled when aboard is
  0, Settle disabled when no colonists aboard or no habitability room. Use the same
  legality the reducer enforces so a disabled button and a rejected command never
  disagree.
- Clamp the `+`/`−` steppers and the exact-entry field so the value can never exceed
  the moveable maximum (min of source amount and destination room). The stepper stops
  at the cap; the numeric field rejects/clamps over-cap input inline without losing
  focus. (Steppers were added by the WP-PR07 §8.1 follow-up; extend that widget.)

**Likely files:** `edge/tui/screens/transfer.py`, `edge/tui/screens/planet.py`
(caller), transfer Pilot + snapshot tests.

**Docs:** `PLAYTEST_NOTES.md` PT-45/46/47. No DESIGN change.

**Tests:** modal renders over a visible planet background (snapshot); empty-source
rows show disabled buttons; stepper and field clamp at the cap and never exceed
source/room; keyboard flow retains focus on clamp; compact geometry check.

Commit: `playtest: WP-PR2-06 transfer overlay and clamped controls`

---

### WP-PR2-07 — Nav-compass clarity and trail colors

**Goal:** clarify or remove the "one-way" nav-rose indicator, and make the nav-rose
trail sector text use the same color convention as the rose interior.

**Changes**

- Decide what "one-way" should communicate to a new player. The nav rose already
  marks a warp `kind` and draws backtrack/one-way cells (`edge/tui/widgets.py`
  around `:1204`–`1214`, and the sidebar row at `:1164`). Either (a) replace the
  bare "one-way" label with plain-language help ("no return warp") wherever it
  appears, or (b) drop the in-rose glyph and explain one-way only in Help + the
  sensor warning that already fires (`edge/tui/screens/game.py:363`). Record the
  choice in the handoff; keep it consistent across rose, sidebar, and Help.
- Make the nav-rose **trail** (the `#rose-trail` element, `edge/tui/widgets.py:1504`)
  color its sector-id text with the same convention (band/backtrack/avoided/content
  colors) used inside the rose cells, so the trail and the rose read as one system.
  Reuse the existing cell color source rather than duplicating a glyph/color table.

**Likely files:** `edge/tui/widgets.py` (`NavRose`, `WarpCell`, trail), `edge/tui/
screens/help.py`, nav-rose Pilot + snapshot tests.

**Docs:** Help nav-rose legend (must match `WarpOption`/cell definitions — do not
duplicate stale glyphs); `PLAYTEST_NOTES.md` PT-48/PT-55.

**Tests:** one-way presentation matches the chosen decision across rose/sidebar/Help;
trail colors match rose-cell colors for band, backtrack, avoided, and content;
snapshots including monochrome.

Commit: `playtest: WP-PR2-07 nav compass clarity and trail colors`

---

### WP-PR2-08 — Computer map: legend colors, P-plot, phantom edges

**Goal:** color per-sector content text to match the legend, add `P` to plot a route
from the Map view, and fix edges drawn between unconnected sectors.

**Changes**

- **Legend colors (PT-50):** in `edge/server/mapgraph.py`, `_label` builds one string
  `(id)codes` and `_build_at_radius` paints it with a single node style
  (`:230`–`231`). Split the label so the content codes (`S`/`P`/`@`/`#`/`×` from
  `_codes`, `:70`) are painted in their legend colors while the id keeps the
  band/here/route/unexplored style. Update the `LEGEND` string and `canvas.put`
  usage; keep fog-of-war (no codes for unexplored sectors).
- **P to plot (PT-51):** the Map tab currently plots on Enter/click
  (`edge/tui/screens/computer.py` `on_...` map handlers around `:780`). Add a `P`
  binding on the Map subview that plots a route to the highlighted map node, mirroring
  the `plot_route` action already bound screen-wide (`:68`) and the other sector
  tables. Ensure it lands on the Route subview (WP-UI20/21 remembered-subview path).
- **Phantom edges (PT-56, repro sector 11703 seed 4):** investigate
  `_draw_edges` (`edge/server/mapgraph.py:256`). Edges are only drawn between nodes
  that are genuinely in `state.adjacency`, so the likely cause is a **rendering
  artifact**: a stepped connector's horizontal stub runs along a row shared by an
  unrelated node in an adjacent column and visually reads as a connection, or two
  columns are packed close enough that a `│` run abuts a non-neighbor. Reproduce with
  a fixed-seed 4 test at/near sector 11703, then fix by widening/protecting the gap,
  routing the stub clear of non-neighbor rows, or extending the `occupied`-style
  protection to a small margin around each label. Do **not** just hide edges — prove
  the drawn set equals the true adjacency set.

**Likely files:** `edge/server/mapgraph.py`, `edge/server/canvas.py`,
`edge/tui/screens/computer.py`, `edge/server/session.py` (`map_view`), mapgraph unit
tests + Computer Pilot/snapshot tests.

**Docs:** `PLAYTEST_NOTES.md` PT-50/51/56. No DESIGN change unless the map spec in
DESIGN §11 states edge rules.

**Tests:** seed-4 regression asserting no drawn edge between non-adjacent sectors near
11703; content codes rendered in legend colors (snapshot); `P` on Map plots and lands
on Route; fog preserved for unexplored nodes.

Commit: `playtest: WP-PR2-08 computer map colors, P-plot, and edge fix`

---

### WP-PR2-09 — Dialogue playtest tooling fixes — landed

**Landed 2026-07-13** in `playtest: WP-PR2-09 dialogue playtest tooling fixes` (PT-39/40/41),
after `playtest: WP-PR2-09 art panels stop resetting` (PT-42, below). Neither commit stayed
inside the dev-only corner the package assumed.

- **PT-39 keyboard nav.** Every dial on `PlaytestControls` is an `ObjectRow` — the shared
  focusable/clickable row — so ↑↓ walk the dials, Enter/Space advances the focused one, and
  ←→ step a multi-valued dial (species, standing) either way. Flipping a dial recomposes the
  board, so focus is explicitly restored to the dial you were on. `ClickableEntry` grew a
  public `dest` property so a keyboard caller can act on the focused row.
- **PT-40 hotkey.** `F2` → **`c`**, on the board and its host (`c` was free on the contact
  screen underneath, which owns `b`/`f`/`j`/`f5`/digits).
- **PT-41 hostile has no effect — the dial was never broken; the corpus was.** The dial does
  set effective disposition (standing, band, and the disposition bar all changed with it), but
  the **greeting did not**, and that bug was in the *game*, not the harness. The fallback chain
  never blends packs: a pack that authors `greeting` claims that context outright — and every
  species pack and every persona pack authored **only a catch-all greeting**. `generic`'s
  standing-keyed openers, which exist, were unreachable for all fifteen species, so a species
  you had wronged still greeted you as a friend. Two changes:
  - **Corpus:** every persona (`config/alien_dialogue_default.yaml`) *and* every species
    (`config/dialogue/alien_dialogue_species.yaml`) now authors a `when: {standing: hostile}`
    opener in its own voice.
  - **Selector:** in `select._score` a pinned `standing` counts double (`STANDING_WEIGHT`), so
    the hostile opener beats the same pack's situational colour ("we have met before", "your
    hull is scarred") rather than tying at one criterion each and being settled by the weighted
    RNG. **Replay-safe:** exactly one context in the shipped corpus mixed a standing entry with
    a criteria entry (terran `dossier_self`) and its winner is unchanged, so no line selection —
    and therefore no recency ring, and no `state_hash` — moves.
  - Spec kept in sync per AGENTS.md: DESIGN §6.7, the `alien_dialogue_default.yaml` SELECTION
    header, and the authoring prompt (`authoring/pipeline.py::_structure_brief`).
- **Found on the way:** `edge/config.py:89` **strips species dialogue sidecars under pytest**,
  so tests only ever see the persona/generic corpus. That is why the species-level fix alone
  would have looked untested; the persona layer carries it under test, and
  `test_species_corpus_authors_a_hostile_greeting` reads the species corpus straight off disk.

Tests: `tests/test_dialogue_playtest.py` (keyboard flow on the board, `c` opens/closes, the
hostile dial changes the conversation, every species/persona greets an enemy differently) and
`tests/test_dialogue.py::test_standing_outranks_a_situational_criterion`.

> **PT-42 (art panel reset) landed 2026-07-12** in `playtest: WP-PR2-09 art panels stop
> resetting`. It was **not** dev-only, and not one bug:
>
> - **Contact screen (the reported case).** `_reopen` popped the screen and pushed a fresh
>   one on every reply, rebuilding the whole widget tree — portrait included. It now
>   repaints the speech and the reply menu **in place** (`_verb_widgets` is shared by
>   `compose` and `_reopen`, so a repaint cannot drift from a first paint) and leaves the
>   portrait mounted. Between two nodes of one conversation the speaker does not change and
>   neither does their face.
> - **Station screens (Stardock · Port · Starbase).** These genuinely *do* rebuild after an
>   action (`_issue` / `_reopen` pop and push), so every art panel returns as a new widget.
>   Each opened on a text fallback and swapped the image in from `on_mount` — one frame of
>   placeholder per action, which is the reset the player sees. New `edge/tui/art_memory.py`
>   remembers the rendered `Text` per panel identity so a rebuilt panel opens on the art it
>   had a moment ago; `on_mount` still re-renders, so a theme or tier change corrects itself
>   on the next frame. It is a paint-time smoother, never the source of truth (copies in and
>   out — Rich `Text` is mutable and callers `stylize()` it). The *chafa render* was already
>   memoised in `edge.art.portrait`; what was missing was the frame.
>
> - **Every pushed screen resized itself just after opening** (reported alongside PT-42:
>   "the dialogue screen and the rumour modal start smaller, then expand"). `EdgeApp.
>   push_screen` stamped the responsive tier class with `call_after_refresh`, so a screen
>   laid out **once under untiered CSS and again a frame later** once the class landed.
>   Now stamped synchronously, before the new screen's first layout. This was not only a
>   flicker: the tiers were *silently not applying* on first paint, so at 80×24 the
>   Computer's tables were not folding their `fold=True` columns, and at ≥120 the
>   `DetailTable` side detail panel never appeared. Both snapshot baselines changed to the
>   correct, tier-aware layout.
>
> Tests: `tests/test_ui_art_refresh.py`, plus
> `test_a_reply_repaints_the_menu_without_rebuilding_the_portrait` in the flow suite.

**Goal:** make the dialogue-authoring playtest harness usable: keyboard-navigable
controls modal, move its hotkey `F2`→`c`, make the hostile dial actually affect the
conversation, and stop the art panel resetting after each action. This is the
dev-only impure corner (`edge/dialogue/authoring/playtest.py`); it is never imported
by runtime.

**Changes**

- **Keyboard navigation (PT-39):** `PlaytestControls` (`playtest.py:286`) rows are
  clickable; add focusable widgets (or a `DataTable`/list) so arrows move between
  dials and Enter/Space flips the highlighted dial. Escape closes.
- **Hotkey move (PT-40):** change the controls binding from `F2` to `c` on
  `PlaytestControls` (`:288`) and the host (`:358`), and every doc string / hint that
  says "F2" (`:6`, `:310`, `:371`). Make sure `c` does not collide with a contact-
  screen binding used underneath.
- **Hostile has no effect (PT-41):** trace how the modal's standing-band dial feeds
  the simulated contact. `_BAND_BASE` maps hostile→0.10 (`:60`); confirm that setting
  the band actually recomputes the effective disposition the contact screen reads,
  and that a hostile band changes greeting vs. violence / disabled replies. Fix the
  wiring so the dial mutates the sim state the real contact screen consumes.
- **Art panel reset (PT-42):** on the dialogue/contact screen, the portrait/art panel
  re-renders after each dialogue action. Find where the contact screen refreshes
  after an action (`edge/tui/screens/contact.py`) and avoid rebuilding the portrait
  when only the dialogue text changed (cache the resolved portrait per contact
  instance; re-render only on contact change). This also benefits the real game
  contact screen — verify it there too.

**Likely files:** `edge/dialogue/authoring/playtest.py`, `edge/tui/screens/contact.py`,
playtest/contact tests (dev-tooling tests may live under `tests/`).

**Docs:** `edge/dialogue/authoring/README.md` (hotkey change), `PLAYTEST_NOTES.md`
PT-39..42. No DESIGN change.

**Tests:** controls modal keyboard flow; `c` opens/closes controls; setting hostile
changes the contact's greeting/replies in the harness; portrait not rebuilt on a
text-only dialogue step (assert render/refresh count or cached identity).

Commit: `playtest: WP-PR2-09 dialogue playtest tooling fixes`

---

### WP-PR2-10 — Attack-screen button hotkeys in text — landed

**Landed 2026-07-13** in `playtest: WP-PR2-10 attack-screen button hotkeys`. The labels already
*said* `▶ FIRE [F]` in the source (since `ui: WP-UI18 combat dashboard`), which is why this
looked at first like a note filed against a stale build — but they rendered as `▶ FIRE `. **A
Button label is Rich markup**, so an unescaped `[F]` parses as a style tag and disappears; the
shipped snapshot baseline had no accelerators in it at all. Escaping the bracket (`\[F]` — the
convention `planet.py` already used for `\[I] Invade`) restores all four. The same trap had
swallowed the **Help** (`[O]`) and **Surface** (`[E]`/`[T]`) accelerators, fixed in the same pass.

`EncounterScreen.BUTTON_ACTIONS` is now a class-level id → action map (it was a dict rebuilt
inside `on_button_pressed`), so the buttons and the `BINDINGS` table can be asserted against each
other instead of drifting. `tests/test_ui_encounter_hotkeys.py` guards it three ways: the
bracketed letter in each label *is* the key bound to the action that button fires; the key and
the click issue the same command; and a **repo-wide scan** fails on any `Button` label whose
hotkey Rich would eat. 10 snapshot baselines refreshed (encounter/surface/combat, all tiers plus
high-contrast and monochrome) — the letters live in the text, not in colour, so monochrome loses
nothing.

**Goal:** show each attack/encounter button's hotkey in its label.

**Changes**

- In the encounter/attack screen (`edge/tui/screens/encounter.py`), add the
  accelerator letter into each button's text (the `[F]ire`, `[M]issile`, `[G]`
  engage, retreat, etc. convention already used elsewhere — e.g. planet.py uses
  `\[I] Invade`). Keep the letters in sync with the actual `BINDINGS`.
- Verify monochrome legibility (the accelerator must not rely on color alone).

**Likely files:** `edge/tui/screens/encounter.py`, encounter Pilot + snapshot tests.

**Docs:** `PLAYTEST_NOTES.md` PT-43. No DESIGN change.

**Tests:** each button label contains its binding letter and the letter triggers it;
encounter snapshot in default + monochrome.

Commit: `playtest: WP-PR2-10 attack-screen button hotkeys`

---

### WP-PR2-11 — Species portrait `_01` selection — landed

**Landed 2026-07-13** in `playtest: WP-PR2-11 species portrait variant selection`. **The bug as
filed does not exist**, and the investigation this package asked for is what closes it.
`list_portraits` collects numbered-only variant sets correctly (no species ships a bare
`<id>.<ext>`, so the "bare file is always index 0" hypothesis had nothing to bite on),
`resolve_portrait(variant=0)` returns the first sorted file, and the seeded variant the
projection draws (`session.contact_view:1962`) is uniform — index 0 comes up as often as any
other across seeds. All four facts are now pinned by `tests/test_species_portrait.py`, against
both a synthetic dir and the shipped assets.

**The real cause:** a face is keyed to **(game seed, species instance id)**, so any *single*
instance wears one variant forever. The report came from the dialogue play-test harness, which
injects exactly **one** instance per species — so terran (the only multi-variant species) locks
to one of its three faces for a given `--seed`, and `_01` (the newer curated Midjourney
reference) simply never came up. In a real game each terran ship is its own instance and wears
its own face, so nothing was broken there.

**Fixed by making the variants reachable where they were being reviewed:** the play-test
controls board gains a **Portrait** dial (`PlaytestService.cycle_portrait` / `portrait_label`)
that steps a variant offset over the seeded draw and names the resolved image file, so an
author can walk every face a species has — `_01` included — and knows which asset they are
looking at.

**Goal:** ensure the portrait variant selector can pick the `_01`/`_1` image.

**Changes**

- `resolve_portrait`/`list_portraits` (`edge/art/portrait.py:54`,`:70`) collect
  `<id>.<ext>` plus `<id>_<digits>.<ext>` variants "sorted by name" and pick by
  `variant` (deterministic) else random. Investigate why the `_01` variant is never
  chosen: likely the bare `<id>.<ext>` is always index 0 and a species that only has
  numbered variants (no bare file), or an off-by-one in the `variant` index, or the
  random draw excluding index 0. Add a focused test that a species whose files are
  `x_01`, `x_02` can resolve to `x_01`, and that deterministic `variant=0` picks the
  first sorted file. Fix the indexing/inclusion bug the test exposes.

**Likely files:** `edge/art/portrait.py`, `tests/` portrait test.

**Docs:** `PLAYTEST_NOTES.md` PT-38. No DESIGN change.

**Tests:** variant list ordering includes numbered-only sets; `_01` is reachable for
both deterministic and random selection; existing bare-file behavior unchanged.

Commit: `playtest: WP-PR2-11 species portrait variant selection`

---

### WP-PR2-12 — NPC hub-drift dispersion — landed

**Landed 2026-07-13** in `playtest: WP-PR2-12 the Stardock is not a trap`. **This WP's premise
was wrong, and the real cause is a one-liner.** The pileup is not a movement-policy bias
(`trade_seek` pulling toward the hub, `wander` lacking repulsion) — it is an **absorbing state**:

- `cron._pinned_species` pinned **whoever was standing in the dock sector this tick**. The
  Stardock sits *inside* Core Space, so governing-alliance ships may legally drift in — and the
  moment one did, it matched the "pinned" test and never moved again. The hub was a one-way trap
  that slowly swallowed the Core's traffic. Measured on seed 4: the 2 staged greeters became 7
  ships and climbing over 200 drift firings, permanently the most crowded sector in the universe.
- The greeting party is now pinned by **identity** — `AlienSpecies.stardock_staged`, set in
  `_place_stardock_contacts` at generation — so a passer-by is free to leave. After the fix the
  dock holds exactly its 2 greeters over 300 firings and **no sector exceeds 3 ships**.
- **The dispersion knob this WP proposed (`aliens.drift_*`, crowd-avoidance in `plan_move`) is
  therefore unnecessary and was not added.** `core.npc.plan_move` is untouched: `wander` stays
  byte-identical, no movement output moves, and **no golden replay changes**. Adding a repulsion
  term would have papered over the trap while leaving it in place.
- No wire bump (the flag is on the model, not a DTO); no store migration (the world is
  regenerated from the seed).

Tests (`tests/test_engine.py`): the pin is by identity, a visitor that drifts into the dock can
drift out again (chosen among species the Core actually admits — the Core rule hems everyone else
in, which is not this bug), and a 200-firing soak asserts the dock never grows past its greeters
plus a couple of passers-by.

**Goal:** stop cron drift from piling hub-space ships into the Stardock sector.

**Changes**

- The daily/periodic `alien_drift` cron (`edge/engine/cron.py:258`) moves non-pinned
  species by `npc.plan_move` (`edge/core/npc.py:101`). Stardock-pinned species don't
  wander (`_pinned_species`, `:250`), so the pileup is drifting NPCs whose movement
  policy pulls them toward the hub — most likely `trade_seek` drifting to the nearest
  port, and the Stardock (a port) acting as a sink, or `patrol`/`wander` lacking any
  repulsion from an already-crowded sector.
- Reproduce deterministically: run the drift cron many times on a fixed seed and
  count ships per hub sector; assert the Stardock sector does not exceed a sane cap.
- Fix in `plan_move` (pure core, so it stays testable and replay-stable): add a
  dispersion term — e.g. `trade_seek` picks among *several* nearby ports rather than
  always the single nearest, and/or any policy avoids a destination already crowded
  above a config threshold (a new `aliens.drift_*` knob, recorded in DESIGN §6.3 and
  the config default). Keep `wander` byte-identical if it is unchanged. Draw any new
  randomness from the same sub-RNG the cron already salts so replays stay stable.

**Likely files:** `edge/core/npc.py`, `edge/core/config.py` (+ default YAML) if a knob
is added, `edge/engine/cron.py` (only if the seam needs it), npc/cron tests, replay
fixtures if a knob changes movement.

**Docs:** DESIGN §6.3 (movement policy / dispersion knob) + `PLAYTEST_NOTES.md` (add a
tuning note like the governance block); PT-37. This is a **movement** change — if it
alters `plan_move` output for existing policies, update golden replays.

**Tests:** fixed-seed drift over N days keeps hub sectors under the cap; `wander`
unchanged (byte-identical) if untouched; determinism/replay equality.

Commit: `playtest: WP-PR2-12 NPC hub-drift dispersion`

---

### WP-PR2-13 — Asteroid mining limits and finite yield — landed

**Landed 2026-07-13** in `playtest: WP-PR2-13 finite asteroid belts`.

- **The reserve, and the regrowth decision (§2.5 left it open): no regrowth.** `Planet.ore_reserve`
  / `ore_reserve_max` are seeded at generation as `belt_reserve_base` × the sector band's
  `belt_reserve_band_scale` × a per-belt `belt_reserve_spread` draw (config), on **its own
  sub-RNG** so seeding reserves cannot perturb the planet-type draw order. A worked-out belt
  **stays worked out** — a mining camp is a place you exhaust and leave, not a renewable parking
  spot, and the richer deep fields are what pull the player outward (seed 4: a Void belt holds
  2,664 ore ≈ 54 hauls; a Hub belt about a third of that). Recorded in DESIGN §4.2.
- **One clamp, three consumers.** `belt_mining_yield(planet, config)` (signature was
  `planet_type`) now clamps the nominal `asteroid_mining` haul to the ore actually left, so the
  `MineBelt` reducer, the owned-world auto-collect, and the `PlanetDTO.mine_yield` projection
  cannot disagree. An exhausted belt **rejects with its own error** rather than yielding 0, and
  projects `mine_yield == 0` so the screen greys `[M]` — legality and affordance from one fact.
- **Art thins with the field.** The orbit view carries a reserve bar (`n of N, 40%`), and the
  belt sprite drops rocks by a **stable per-cell rank**, so working a field empties *that* field
  rather than redrawing it — in the sector scene as well as the orbit view (`SectorPlanetDTO`
  carries the reserve too).
- **"Unseeded" must never read as "spent".** A belt straight out of the constructor has no
  reserve; `normalize_belt` — the existing idempotent legacy converger — now fills a
  reserve-*less* belt to a full band-agnostic field, while leaving a genuinely exhausted one
  (`ore_reserve_max > 0`, `ore_reserve == 0`) alone. This is what a pre-PT-52 save converges to.
- **No store migration** (see FU-01's sibling correction in WP-PR2-04): the world is regenerated
  from the seed. Wire **18 → 19** (`ore_reserve`/`ore_reserve_max` on `PlanetDTO` and
  `SectorPlanetDTO`); fingerprint + envelope fixtures regenerated.

Tests: `tests/test_asteroid_belts.py` (band-weighted seeding, draw-down, no regrowth, haul
clamped to the ore left, worked-out rejection + greyed projection, unseeded-is-full, art thinning)
and the corrected owned-belt production case in `tests/test_planets.py`.

**Goal:** make a belt a finite, depletable resource with a mining cap, reflected in
the art.

**Changes (core / persisted)**

- Add a depletable reserve to the belt planet record (e.g. `ore_reserve: int` on the
  belt `Planet`, or a belt-specific field), initialized at generation from a
  band-weighted config amount (`edge/bigbang` belt generation +
  `edge/core/planets.py`). Decide regrowth: none, or a small
  `planets.belt_regrow_per_day` — record in DESIGN §4.2.
- `MineBelt` (`edge/core/rules.py`, added by the PT-30 follow-up) must draw from and
  decrement the reserve, clamp the haul to `min(free holds, reserve, per-action cap)`,
  and reject with a specific error when the reserve is exhausted. Update the shared
  `planets.belt_mining_yield` seam so the reducer, the owned-world auto-collect, and
  the `PlanetDTO.mine_yield` projection all honor the reserve.
- Persisted change: codec/migration (back-fill a reserve for legacy belts), wire
  bump, `state_hash`, replay fixtures.

**Changes (art / TUI)**

- Reflect the remaining reserve fraction in the belt art (`edge/art/planet.py` belt
  subtype, and the `PlanetScreen` orbital/mining panel `edge/tui/screens/planet.py`):
  fewer/denser rocks as it depletes, and a numeric "reserve remaining" readout. Show
  the exhausted state clearly and disable the `[M] Mine belt` affordance when empty.

**Likely files:** `edge/core/models.py`, `edge/core/planets.py`, `edge/core/rules.py`,
`edge/bigbang/` (belt gen), `edge/core/dto.py`, `edge/server/session.py`,
`edge/store/codec.py`, wire/migration/replay, `edge/art/planet.py`,
`edge/tui/screens/planet.py`, `tests/test_asteroid_belts.py`.

**Docs:** DESIGN §4.2 (finite belt reserve + regrowth decision); a tuning note in
`PLAYTEST_NOTES.md`; PT-52.

**Tests:** reserve decrements per haul; exhaustion rejects with a specific error and
disables the action; generation seeds a band-weighted reserve; legacy belt decodes
with a back-filled reserve; `state_hash` round-trips; art/panel snapshot at full and
depleted reserve.

Commit: `playtest: WP-PR2-13 finite asteroid belts`

---

### WP-PR2-14 — Partial-fighter invasion (UI) — landed

**Landed 2026-07-13** in `playtest: WP-PR2-14 partial-fighter invasion`. UI-only, exactly as
§2.7 predicted: `InvadePlanet` always took `cmd.fighters` and the core already leaves the
remainder aboard (`test_citadels.py` commits 300 of 500 and asserts the ship keeps 200) — only
the planet screen hard-coded `p.ship_fighters`.

- New shared **`AmountPrompt`** (`edge/tui/screens/amount.py`): the *quantity* sibling of
  `ConfirmScreen`, wrapping the same `AmountStepper` so typing, −/+ stepping, and clamping
  behave as they do at the Stardock and in the transfer workbench. Dismisses with the amount or
  `None`, so a caller reads it like a confirm. `[I]` opens it defaulting to the whole wing
  (the common case stays cheap), clamped to `1..ship_fighters`, `[A]` commits them all, step 10.
- **It is the destructive confirmation, so it inherits the safety rule.** `ACTION_DANGER` marks
  `invade` destructive, and `ConfirmScreen` enforces "a stray Enter must not destroy" by focusing
  *deny*. `AmountPrompt(dangerous=True)` therefore lands focus on **Cancel** and binds no
  screen-wide Enter — Enter presses whatever is focused, so a stray Enter after the hotkey
  cancels. Enter *inside* the amount field commits, since typing a number and pressing Enter is
  unambiguous intent. `tests/test_ui_actions.py`'s danger guard (which caught the regression when
  the prompt first bypassed `ConfirmScreen`) now accepts either confirming modal and asserts the
  focus rule.
- Planet-screen affordance and Help updated: the invasion line no longer promises to land *all*
  fighters.

Tests: `tests/test_ui_invade_amount.py` (prompt appears; a partial commit issues
`InvadePlanet(id, n)`; clamps at 1 and at `ship_fighters`; `[A]` refills; cancel and stray-Enter
land nobody; a blocked invasion never reaches the prompt).

**Goal:** let the player choose how many fighters to commit to an invasion.

**Changes**

- The reducer already accepts `cmd.fighters` (`edge/core/rules.py:2251`); only the
  planet screen commits all `p.ship_fighters` today
  (`edge/tui/screens/planet.py:173`,`:368`). Change `action_invade` to open an amount
  prompt (reuse the existing amount-prompt pattern used for buy-quantity / transfer
  fields), defaulting to a sensible value (all, or a suggested fraction), clamped to
  `1..ship_fighters`, then submit `InvadePlanet(fighters=chosen)`.
- Keep the `can_invade`/`invade_blocker` gating and the destructive-confirm behavior.

**Likely files:** `edge/tui/screens/planet.py`, planet invade Pilot + snapshot tests.

**Docs:** `PLAYTEST_NOTES.md` PT-53. No DESIGN change (rule already supports it).

**Tests:** amount prompt appears; committing fewer than all fighters leaves the
remainder aboard; clamp at 1 and at `ship_fighters`; blocker states still bar the
attempt.

Commit: `playtest: WP-PR2-14 partial-fighter invasion`

---

### WP-PR2-15 — Cloud City on jovian worlds (split a/b/c)

**Goal:** turn gas giants (`planet_type == "jovian"`) into a **Cloud City** variant:
you cannot store anything until a **staging area** is built (a one-haul resource
cost, since nothing can be stored beforehand); once built, the city can hold stores
and a **size-scaled** number of colonists; the structure uses distinct floating-city
art. Build in three ordered sub-packages so a simpler agent can land it incrementally.

Read DESIGN §4.2 first. This introduces new planet state and a new build action — a
**persisted** change touching codec/migration/replay across all three sub-WPs'
data. Do the DESIGN §4.2 spec update in **WP-PR2-15a** before writing code.

#### WP-PR2-15a — Cloud City rules and staging (core)

- Update **DESIGN §4.2** first: define the Cloud City variant, the staging-area
  prerequisite, its one-haul build cost (small enough to fit typical early ship
  holds — state the constant), the store gating (no stores until staged), and the
  colonist-berth scaling formula by city size. Keep the Fuel Ore/Organics/Equipment
  trio sacred (no fourth commodity).
- Add jovian state: a `staging_built` flag (or a `cloud_city_size` int where 0 = not
  built) on the `Planet`/belt-analog record. Gate `PlanetDeposit`/store transfers and
  colonist settlement on jovians behind it in the reducers (`edge/core/rules.py`).
- Add a `BuildStagingArea` (or reuse a generalized citadel-like build) command:
  requires same sector, a colonizable-jovian target, and the build cost aboard;
  consumes it; sets `staging_built`/initial size. Colonist capacity on a jovian
  derives from city size (`edge/core/planets.py` capability seam).
- Persisted: codec, config knobs (`planets.cloud_city_*`), wire bump, migration
  (legacy jovians default to not-staged), `state_hash`, replay fixtures. Extend the
  per-planet-type capability predicates (from WP-PR06) so jovians expose
  `stageable`/`buildable` and gate stores/colonists correctly.

Commit: `playtest: WP-PR2-15a Cloud City rules and staging`

#### WP-PR2-15b — Cloud City art (floating structure)

- Add a distinct floating-city art variant (`edge/art/planet.py` and/or a new
  concourse-style sprite) — a structure hovering in the jovian's clouds, visually
  different from a surface colony. Provide standard/wide sizes and monochrome/high-
  contrast fallbacks per the art policy. Wire it into `art_adapter` and the sector
  scene / PlanetScreen orbital view so a staged jovian renders the city and an
  un-staged one renders bare clouds.

Commit: `playtest: WP-PR2-15b Cloud City art`

#### WP-PR2-15c — Cloud City UI

- In `PlanetScreen` (`edge/tui/screens/planet.py`), for a jovian: show the staging
  prerequisite and a `[Build staging area]` affordance (gated/greyed per capability
  and cost, with the exact blocker), the build cost, and — once built — the store
  transfer and size-scaled colonist settlement controls (reuse the WP-PR2-06 transfer
  workbench and `SettleColonists`). Project the needed facts on `PlanetDTO` and
  assemble them in `session.py`.

Commit: `playtest: WP-PR2-15c Cloud City UI`

**Likely files (across a/b/c):** `docs/DESIGN.md` §4.2, `edge/core/models.py`,
`edge/core/planets.py`, `edge/core/rules.py`, `edge/core/config.py` + default YAML,
`edge/core/dto.py`, `edge/server/session.py`, `edge/store/codec.py`,
wire/migration/replay, `edge/art/planet.py`, `edge/tui/art_adapter.py`,
`edge/tui/screens/planet.py`, `edge/tui/widgets.py`, planet/cloud-city tests.

**Docs:** DESIGN §4.2 (the spec, in 15a); `PLAYTEST_NOTES.md` PT-54 across the three
commits; a Cloud City tuning note.

**Tests:** stores/colonists rejected on an un-staged jovian with specific errors;
build consumes the one-haul cost and enables stores; colonist capacity scales with
size; legacy jovian decodes un-staged; `state_hash` round-trips; art snapshots
staged vs un-staged; PlanetScreen jovian flow at all tiers.

## 5. Recommended execution order

Group by risk and dependency; land core/persisted changes before the UI that renders
them.

1. **Quick isolated fixes first** (low risk, no schema): WP-PR2-11 (portrait
   variant), WP-PR2-10 (attack hotkeys), WP-PR2-14 (partial invasion), WP-PR2-09
   (dialogue tooling, dev-only). These build confidence and unblock nothing else.
2. **Core/persisted changes next**, so downstream UI has stable DTOs: WP-PR2-04
   (named discoveries), WP-PR2-13 (finite belts), WP-PR2-12 (NPC dispersion —
   movement/replay). Do WP-PR2-04 before WP-PR2-05 (the wreck slot benefits from
   named wrecks).
3. **Stardock/Tavern UX**: WP-PR2-02, WP-PR2-03, then the tabbed-keyboard model
   WP-PR2-01 (which touches Stardock/Computer/Base together — settle its DTO/binding
   scope once, last of this group).
4. **Map and nav**: WP-PR2-08 (map colors/P-plot/edge fix), WP-PR2-07 (nav compass).
5. **Scene and transfer visuals**: WP-PR2-06 (transfer overlay + clamps — no gate),
   then WP-PR2-05 (scene composite — **spike-gated**).
6. **Cloud City last**, in order a → b → c (each sub-WP depends on the previous).

WP-PR2-04, WP-PR2-13, and WP-PR2-15 each open a wire-version/schema epoch; avoid
bundling unrelated schema changes into one epoch. Most other packages are
projection-only (wire bump, no store migration) or pure TUI (no wire change).

## 6. Verification and handoff requirements

Per the project convention (memory: skip running ruff/mypy/pytest yourself — the
maintainer runs them), each package must be **left in a state ready** for:

```text
pixi run ruff check .
pixi run mypy edge/core edge/bigbang edge/store edge/server edge/engine
pixi run pytest <focused test files>
pixi run check
```

Add focused tests with each package. For TUI packages add keyboard **and** mouse
Pilot coverage, an 80×24 geometry check, and snapshots at 80×24, 100×34, and 120×40
where visual structure changes — reviewed in default, high-contrast, and monochrome.
Refresh only intentional baselines.

Each handoff states:

- the PT notes closed by number (and strike them through in `PLAYTEST_NOTES.md` with
  the commit subject);
- any DESIGN / config / wire-version / schema / migration changes;
- focused and full verification status (or that it is left for the maintainer to run);
- snapshot files intentionally changed;
- anything explicitly deferred (track it in a §8-style "Outstanding follow-ups" block
  appended to this plan, never by silently leaving a struck-through note that hides
  open work — the pattern the first plan established).

## 7. Completion criteria

This remediation is complete when all of PT-32..PT-56 are covered by passing
automated tests and struck through in `PLAYTEST_NOTES.md`; combat/world/movement
state remains replay-deterministic (`state_hash` stable across the schema epochs);
all primary workflows work at 80×24; the Cloud City subsystem is documented in
DESIGN §4.2 and reachable in-game; and Help + DESIGN accurately describe the resulting
controls and rules. Deferred items, if any, are recorded in an appended
"Outstanding follow-ups" section rather than left implicit.

## 8. Outstanding follow-ups

### FU-01 — The config loader strips the species dialogue sidecar under pytest (open)

**Found during WP-PR2-09 / PT-41.** `edge/config.py:89` inspects `sys.modules` /
`PYTEST_CURRENT_TEST` and, when it decides it is running under pytest, filters
`dialogue_file:` down to `alien_dialogue_default.yaml` alone — dropping
`config/dialogue/alien_dialogue_species.yaml`, the shipped **species** corpus. So the whole
test suite resolves dialogue against the persona/generic chain only, and never sees the packs
that win in a real game (a species pack shadows both).

Why this matters, concretely: PT-41's bug (every species greeted an enemy like a friend) lived
*in the species corpus*, and no test could have caught it — the fix had to be duplicated at the
persona layer to be testable at all, and the species half is guarded by a test that parses the
YAML off disk (`test_species_corpus_authors_a_hostile_greeting`) rather than through the loader.
Any future corpus regression in `alien_dialogue_species.yaml` is similarly invisible.

It is also **runtime code branching on the test runner**, which the layering rules otherwise
forbid; the intent was presumably to pin the suite to a stable base corpus so a swapped/authored
species sidecar cannot move golden lines.

**Resolve by** making the corpus an explicit input rather than an ambient one: drop the
`sys.modules` sniff from `edge/config.py`, and have the tests that need a pinned corpus load a
config that names only the base dialogue file (a fixture, or a test config path), while the
default load — the one the game uses — keeps the species sidecar. Then re-point the dialogue
tests at the full shipped chain and confirm nothing in the corpus-driven suites (contact,
encounter, snapshots) depends on the persona fallback being reachable where a species pack
actually speaks.

Sized as a small, self-contained package; not blocking any WP in §4.

### FU-02 — Order-dependent flake: `test_corp_charter_submits_via_button_and_validates` (open)

**Found during WP-PR2-04** (present on a clean tree — not introduced by any package here).
`tests/test_ui_forms.py::test_corp_charter_submits_via_button_and_validates` **fails under
`pytest-randomly`'s shuffled order and passes with `-p no:randomly`**: the full suite is
2683 green in fixed order, while a shuffled `-x` run stops on this test with the submitted
charter name never arriving (`assert [] == ["Void Runners"]` — the button press produced no
result).

So some earlier test leaks state the corp form then reads — an app/screen singleton, a stale
`EdgeApp` focus, or a monkeypatched service that outlives its test. It is a **real defect in
the test suite's isolation**, not a UI bug, but it makes every future `-x` run untrustworthy
(it can mask an actual regression by stopping early on this).

**Resolve by** finding the leaking neighbour (`pytest -p randomly --randomly-seed=<seed>` from a
failing run reproduces the order; bisect with `-p no:randomly` plus an explicit test list), then
fixing the leak at its source — an autouse fixture that resets whatever is shared, not an
`@pytest.mark.order` or a `no:randomly` blanket, which would hide the next one.
