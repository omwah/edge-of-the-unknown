# Playtest tuning notes

Small, living notes on tuning knobs that only reveal their feel in play. Each
names the config path, the current default, and what to watch for.

## Core governance (`aliens.governance`, WP51/WP52, 2026-07-07)

- **`seizure_chance`** (default `0.002`/day). The background probability that a
  ready `covets_core` bloc seizes the Core on the daily `governance_tick`. A
  seizure only *rolls* once the bloc is `npc_seizure_ready` — its own
  home-cluster bases intact **and** the incumbent's operational Core-planet
  bases below `min_incumbent_bases`. So the rate is not "flips per day" but
  "flips per day *while the Core is already destabilized*". Watch: if a Core
  weakened by raids/player razing sits contested for many in-game days without
  resolving, raise it toward `0.005`; if flips feel arbitrary (player never
  saw the Core weaken first), the gate — not the chance — is the lever.
- **`intrigue_chance`** (default `0.001`/day). Leadership coups inside a bloc.
  Independent of the Core state; a coup only *turns outward* if
  `intrigue_turns_outward` is set on the bloc. Keep well below `seizure_chance`
  so coups are rare colour, not a constant churn of dossier text.
- **`min_incumbent_bases`** (default per roster). The destabilization gate. This
  is what makes a flip feel *earned* rather than random — the number of Core
  bases that must fall first. Tune this before the chances.

Devtool: `python -m edge.devtool governance` reports the live governor, the
incumbent's operational Core-base count, and each `covets_core` bloc's
seizure-readiness — the fastest way to see whether the gate is open.
`python -m edge.devtool flip_governor <alliance_id>` forces a flip (0 =
ungoverned) to exercise the aftermath surfacing directly.

## WP77 readiness (the A10 hands-on pass — seams arc, 2026-07-09)

The precondition A10 named is met: the WP70–WP76 correction arc closed every
player-reachable gap (attack initiative, starbase ops, contracts, dock repair,
bank, territory/devices, alliances, keymap + action menu, corp UI, sig-mechanic
corpus), so a feel-tune no longer mis-tunes against a UI missing half the
systems. What to exercise, and the dials to watch:

- **Combat frequency/threat** — `encounters.interrupt_chance` per band and
  `combat.threat_damage_scale`. Known data point: the starter Trailblazer loses
  to a 3-foe quill swarm in ~4 rounds; with dock repair (`R` in the engine room)
  and the escape-pod rail live, check death now reads as a setback, not a wall.
- **Danger polish (WP75)** — `aliens.contracts.escort_target_chance` (0.25):
  does a convoy feel *escortable* but tense? Lethal hazards can now pod you:
  fly a mined route and check the hazard-confirm modal (`G` engage) reads right.
- **Faucets** — the WP75 escort risk cuts expected contract income; the WP71
  bank interest (`economy.bank_interest_per_day`, 0.5%/day) adds a passive
  faucet. Watch the trade→first-upgrade pacing against DESIGN §8's ratio.
- **Sig mechanics (WP74)** — visit the Thessbrood (gift), Vennrith (demands),
  Stryx (passage), Vesk→Helot (circuit): does each scheme telegraph enough to
  be fair, and is `trojan_gift`'s payload (320) proportionate to the sweetener?
- **Discoverability (WP73)** — a fresh player should find every system through
  `.` (action menu) and `?` (keymap) alone; note any verb that still feels
  buried.

## UI overhaul acceptance (WP-UI23, 2026-07-10)

The game-wide responsive overhaul was closed with scripted Textual Pilot passes,
a fixed-seed screenshot review, and the full regression suite. The review set is
`docs/ui/shots/`; the deterministic regression matrix is
`tests/test_ui_snapshots.py` (43 captures).

| Pass | Evidence and result |
|---|---|
| New player | Main-menu/onboarding and live flow tests cover start → dock → first trade → engine room → scan/explore. The objective strip names the next action; first trade is reachable directly, with no external documentation or mandatory detour. Pass. |
| Veteran/direct keys | Pilot exercises `P` dock, trade/haggle, Escape undock, nav selection and Enter warp. No additional screen was introduced. Pass. |
| Keyboard-only | Form, table, category selector, contact, combat, route, and workbench tests exercise Tab/arrows/Enter/direct bindings. Pass. |
| Mouse-only | Scene/nav hotspots, trade/service buttons, category popup, surface actions, forms, and workbench slot/component clicks dispatch the same actions as keys. Pass. |
| Compact 80×24 | Responsive snapshots plus the geometry guard verify controls are visible or inside keyboard-scrollable containers; compact sector, Computer, contact, combat, planet, surface, lobby, and workbench are covered. Pass. |
| Hosted/error recovery | Lobby tests cover register/login, connection progress, simulated `RemoteError`, retained field values, and retry; remote-client tests cover travel/trade projections. Pass. |
| Shared workbench | Structural and interaction tests cover ship install/swap/repair and base repair/salvage through the same widget, including click and keyboard selection. Pass. |
| Monochrome | Snapshot review covers sector danger/ownership, table selection, contact disabled replies, combat damage/actions, and workbench slot states using labels/glyphs in addition to color. Pass. |

Resize preservation is covered for screen/focus, Computer category/subview and
table row, sector warp selection, form values, and workbench selection. Dialogue
position and plotted routes live on the existing screen object and are unaffected
by CSS-tier changes. No severity-one gameplay issue was found. The acceptance run
did find two stale fields in the screenshot-only combat service (`firing_arc` and
`engine_room_view`); both were repaired before regenerating all 44 review shots.

Final gates: snapshot matrix passed twice consecutively; `pixi run shots`
completed; `pixi run check` passed all lint, strict typing, and 2,402 tests.

## Hands-on findings after WP-UI23 (2026-07-10)

The following findings were captured during the first hands-on pass after the UI
overhaul. All findings are open at the time of capture. The detailed implementation
sequence, architectural decisions, affected areas, and acceptance criteria live in
[`PLAYTEST_REMEDIATION_PLAN_01.md`](PLAYTEST_REMEDIATION_PLAN_01.md) (this pass
is complete — every PT-01..PT-31 row below is struck through and closed).

| ID | Area | Finding | Planned work |
|---|---|---|---|
| PT-01 | Combat aftermath | ~~Destroying a ship should visibly change the sector. Prefer creating a persistent wreck discovery and recovering salvage through that discovery, leaving evidence that a battle occurred here.~~ Implemented by `playtest: WP-PR01 persistent combat wrecks`. | WP-PR01 complete |
| PT-02 | Stardock catalog | ~~Move missiles and Genesis torpedoes into the Devices catalog and rename the tab **Devices & Armaments**.~~ Fixed in `playtest: WP-PR08 Stardock scoped service UX`. | WP-PR08 |
| PT-03 | Stardock focus | ~~After a Devices purchase, keep the purchased row highlighted instead of returning focus to the tab, matching Trade behavior.~~ Fixed in `playtest: WP-PR08 Stardock scoped service UX`. | WP-PR08 |
| PT-04 | Stardock bindings | ~~Rumor purchase and notice posting should be available only in the Tavern, not as screen-global actions.~~ Fixed in `playtest: WP-PR08 Stardock scoped service UX`. | WP-PR08 |
| PT-05 | Stardock bindings | ~~Deposit and withdrawal should be available only in the Bank tab, not as screen-global actions.~~ Fixed in `playtest: WP-PR08 Stardock scoped service UX`. | WP-PR08 |
| PT-06 | Colonist recruitment | ~~The Stardock Colonists tab provides berth occupancy, incentive, recruit controls, and responsive station-concourse art.~~ Completed by `playtest: WP-PR08 Stardock scoped service UX` plus the PT-06 art follow-up: generated DS9-like raster, Chafa ANSI conversion, explicit accessibility variants, responsive sizes, and a text fallback. | WP-PR08 complete |
| PT-07 | Tavern | ~~Improve the bounty board's information hierarchy and interactions; the current single-column prose list is difficult to scan.~~ Fixed in `playtest: WP-PR08 Stardock scoped service UX`. | WP-PR08 |
| PT-08 | Computer / Planets | ~~Sort player-owned planets ahead of the normal selected sort order and show their ownership clearly.~~ Fixed in `playtest: WP-PR09 Computer ownership and route UX` — owned worlds sort first with a ★ marker. | WP-PR09 |
| PT-09 | Computer / Ports | ~~Show when a port is attached to the player's starbase and sort those ports ahead of the normal selected sort order.~~ Fixed in `playtest: WP-PR09 Computer ownership and route UX` — a player-base port sorts first with a ⚓ marker + status. | WP-PR09 |
| PT-10 | Planet logistics | ~~Replace separate store-transfer prompts with one editor: a row per commodity, `−`/`+` controls stepping by 10, exact amount entry, and Load All / Unload All actions.~~ Fixed in `playtest: WP-PR07 planet transfer workbench`. | WP-PR07 |
| PT-11 | Planet colonists | ~~Allow colonists already aboard to be settled onto a planet the player owns; the current flow rejects an additional unload after initial colonization.~~ Fixed in `playtest: WP-PR07 planet transfer workbench` — new `SettleColonists` command tops up an owned colony. | WP-PR07 |
| PT-12 | Objectives | Hiding Captain's Objectives should also remove objective detail from the sidebar. | WP-PR10 |
| PT-13 | Responsive UI | Apply compact-tier behavior to remaining art-bearing screens so decorative art cannot displace primary controls at 80x24. | WP-PR10 |
| PT-14 | Status Drawer | Sector objects in the Status Drawer must be keyboard navigable and activatable. | WP-PR10 |
| PT-15 | Nav rose | Initially select the sector the player just came from to support fast backtracking. | WP-PR10 |
| PT-16 | Help | Document all new nav-rose symbols, including backtrack, direction, one-way, avoided, content, and hazard markers. | WP-PR10 |
| PT-17 | NPC movement | ~~Hostile aliens entering a defended sector through cron movement must trigger applicable mines and fighters.~~ Fixed in `playtest: WP-PR02 NPC entry territory defenses`. | WP-PR02 |
| PT-18 | Combat retreat | ~~When an alien successfully flees, do not report “Victory — the pack is destroyed”; remove the alien from the sector and move it to a legal destination.~~ Fixed in `playtest: WP-PR03 alien retreat state and copy`. | WP-PR03 |
| PT-19 | Deployments | Replace the six-box deployment grid with a vertical list that retains an image/glyph, purpose, stock, and action for each deployable. | WP-PR11 |
| PT-20 | Deployments | Grey out deployments that are illegal in the current sector and display their blocker instead of allowing a doomed attempt. | WP-PR11 |
| PT-21 | Derelict starbases | ~~Permit salvage and component repair on an unclaimed derelict base. The first repair must not force the player to claim it before further recovery work.~~ Fixed in `playtest: WP-PR04 starbase recovery and integrity gates`. | WP-PR04 |
| PT-22 | Starbase integrity | ~~Gate starbase services below a configurable integrity threshold, initially proposed at 70%, while keeping recovery actions available.~~ Fixed in `playtest: WP-PR04 starbase recovery and integrity gates`. | WP-PR04 |
| PT-23 | Computer / Avoid list | ~~Make adding a sector to the route avoid list discoverable through visible actions and Help; the current `V` workflow is not obvious.~~ Fixed in `playtest: WP-PR09 Computer ownership and route UX` — Notes-tab button + route-context V hint + Help. **Partial vs. plan:** the plan also listed a per-row avoid action on the route/port/planet tables; that specific affordance was **not** built (`V` still prompts for a sector). See §8. | WP-PR09 |
| PT-24 | Genesis feedback | Distinguish “no Genesis torpedo aboard” from “Genesis cannot be deployed on this target” and state the specific target blocker. | WP-PR12 |
| PT-25 | Starbase assault | A starbase assault should render the target base, not ordinary ship art. | WP-PR12 |
| PT-26 | Combat language | ~~Replace or explain “the pack is destroyed”; player-facing results should state concretely which enemies were destroyed or retreated.~~ Fixed in `playtest: WP-PR03 alien retreat state and copy`. | WP-PR03 |
| PT-27 | Contracts | ~~Retain completed contracts in the Computer and render them grey/dim with actions disabled instead of hiding them.~~ Fixed in `playtest: WP-PR09 Computer ownership and route UX` — finished favors stay listed, dim, actions off. | WP-PR09 |
| PT-28 | Black holes | ~~First activation of a black hole can crash the game when gravity damage is applied to the player's ship. Reproduce with both mouse and keyboard and cover lethal and nonlethal damage.~~ Did not reproduce — the lethal-hazard crash was already closed by the WP26/WP75 escape pod; regression-locked in `playtest: WP-PR05 black-hole interaction crash`. | WP-PR05 |
| PT-29 | Stardock Shipyard | ~~The currently flown hull is shown as purchasable even though it cannot be bought. Mark it as current and disable its purchase action.~~ Fixed in `playtest: WP-PR08 Stardock scoped service UX`. | WP-PR08 |
| PT-30 | Asteroid belts | ~~Asteroid belts are not landable planets and must not expose colonies, citadels, colony stores, or planetary descent.~~ Fixed in `playtest: WP-PR06 asteroid-belt interaction model` — per-type `landable`/`colonizable` capabilities gate every seam; belts generate/normalize inert (unowned, base-less, no surface sites) and render an orbital view. **OUTSTANDING (the "…mining interactions" half):** belts now produce *nothing* — the plan's "retain raw-mining output via a dedicated extraction action or passive cache" was deferred; a player belt-mining action is unbuilt. See §8 and DESIGN §4.2. | WP-PR06 |
| PT-31 | Computer routing | ~~Plotting a route from a non-Navigation subview briefly shows Route and then returns to the original subview. The completed action must remain on Route without a flash-back.~~ Did not reproduce — plotting from any subview already lands on Route (WP-UI20/21); regression-locked in `playtest: WP-PR09 Computer ownership and route UX`. | WP-PR09 |

When a finding is fixed, strike through its finding text and append the implementing
commit. Do not remove closed findings; they are the acceptance history for the
remediation pass.

## Hands-on findings — second pass after the remediation round (2026-07-12)

A second hands-on session with 25 observations) after the WP-PR01..PR12 remediation 
round closed. These are **all open** at capture. The detailed, agent-followable
implementation sequence — work packages, files touched, DESIGN/config/wire changes,
and acceptance criteria — lives in [`PLAYTEST_REMEDIATION_PLAN_02.md`](PLAYTEST_REMEDIATION_PLAN_02.md).

Four decision points from the raw notes were resolved by interview (2026-07-12):

- **PT-32 tab-hotkey indicator** — a **colored/underlined accent letter** in the
  tab title (with a monochrome-safe fallback), not parenthesized letters.
- **PT-35 rumor feedback** — a **modal reveal** of the purchased rumor's lead
  text on purchase, then filed to the computer as today.
- **PT-54 Cloud City** — **build the full subsystem, split into ordered sub-work
  packages** (rules/staging → art → UI), not a spec-only deferral.
- **PT-36/44 scene compositing** — **split**: the transfer-modal overlay and the
  clamped/greyed transfer controls (PT-45/46/47) are built directly; the
  dock-over-planet scene compositing and its wreck slot (PT-36/44) get a
  feasibility **spike** gate first.

| ID | Area | Finding | Planned work |
|---|---|---|---|
| PT-32 | Tabbed screens | ~~Computer/Stardock/Starbase tab (and Computer subtab) focus should have accent-letter hotkeys shown in the tab title; the hotkey and Enter-on-a-tab should both drop focus straight onto the tab's primary content (one step, not two). Per-tab action bindings show in the footer.~~ Accelerators + Enter-to-content landed in `playtest: WP-PR2-01 tabbed-screen keyboard model` (underlined tab-title letters on Stardock/Base via `ServiceHub`, per-category on Computer). The **footer scoping** it left undone landed for the **Computer** in `playtest: WP-PR2-01b computer tab-owned keys` — per-tab verbs are now bound to the tab's own `ActionPane` (never the screen), so the footer, `.` menu, `?` help and palette offer only the visible tab's actions; sub-tabs are **numbered `1`..`N`** (the number is its hotkey, owned by the category pane, kept off the footer); categories are **N**avigation / **C**ommerce / e**X**ploration / **R**elations / Log**b**ook (`O` was unusable — a focused table owns it; `X`/`R` were freed by moving Abandon/Remove-note to **Delete** and Route-to to **`W`**, the sector view's key; `C` is Commerce, so Esc alone closes); **Back now leads the footer on every screen** (`chrome.EdgeScreen`) instead of trailing the focused widget's keys; focus follows the tab onto its table, not the filter box. The **Stardock** followed in `playtest: WP-PR2-01c stardock tab-owned keys` — the shared `ServiceHub` now carries the model (so the Base screen inherits it when ported), `check_action` is gone, and the tabs are **C**ommodities · **S**hipyard · **H**ardware · **D**evices & Armaments · Co**l**onists · **B**ank · Ta**v**ern; freeing those letters moved **Haggle to `G`** (on the Port screen too, since it hosts the same trade panel) and **Buy to `P`/Purchase**. It stays a flat tab row, so it takes letters but no sub-tab numbers. Two focus rules were hardened there: a tab **never auto-focuses a text `Input`** (the Colonists amount field was eating every letter key — verbs stopped firing, the footer emptied, and even the accelerators to leave the tab were swallowed), and a **text-only pane holds focus itself** (the Bank), or its own keys would be advertised but dead. Spelling normalized `StarDock` → `Stardock` repo-wide. The **Starbase** closed it out in `playtest: WP-PR2-01d starbase tab-owned keys` — tabs **S**tation · **C**ommodities · **H**ardware · **B**ank (moving the verbs off the screen finally freed a letter for **Hardware**, which had none, and `C`/`H`/`B` now match the Stardock). **Status is now a bordered one-line panel atop Station, not a tab** — standing is read *while* acting — which makes Station the one tab never withheld (a hostile base shows nothing else; Assault is its door). `A` is Assault on Station and Deposit on Bank; Salvage is `V` and Claim `L` (the accelerators took `S`/`C`); `P` purchases and `T`/`G` trade/haggle as everywhere else. Best of all, a tab the base **withholds** now keeps **no keys**, so the footer cannot offer a verb the reducers would refuse. All three tabbed screens are on the model; nothing is deferred. See plan §4 WP-PR2-01. | WP-PR2-01, WP-PR2-01b, WP-PR2-01c, WP-PR2-01d |
| PT-33 | Stardock hardware | ~~Buying from the hardware/shipyard catalog still drops focus off the just-bought row (Devices was fixed in WP-PR08; hardware regressed/uncovered).~~ Fixed in `playtest: WP-PR2-02 hardware focus and Flying/Flown labels` — the post-purchase rebuild now returns keyboard focus to the restored buy table, not just its cursor. | WP-PR2-02 |
| PT-34 | Stardock Shipyard | ~~The hull you are currently flying should read **"Flying"**; a hull you owned before but no longer possess should read **"Flown"**.~~ Fixed in `playtest: WP-PR2-02 hardware focus and Flying/Flown labels` — new persisted `Player.flown_classes` (grows on BuyShip) drives a `ShipyardItem.flown` projection; the shipyard shows Flying / Flown / affordability. Wire → v13. | WP-PR2-02 |
| PT-35 | Tavern rumor | ~~Buying a rumor should reveal what you got (modal reveal, per interview), not just a "logged in your computer" line.~~ Fixed in `playtest: WP-PR2-03 rumor reveal modal` — a keyboard-first `RumorModal` reveals the purchased lead's summary (read fog-safe from `leads_view`), then it stays filed in the computer. | WP-PR2-03 |
| PT-36 | Sector scene | Investigate compositing Stardock/starbase/port art **over** the planet art (hovering, centered) instead of side-by-side. Spike first (per interview). | WP-PR2-05 |
| PT-37 | NPC movement | Cron drift piles hub-space ships into the Stardock sector over time; they should disperse, not accumulate in one sector. | WP-PR2-12 |
| PT-38 | Species art | ~~With multiple portrait variants the selector never picks the `_01`/`_1` image.~~ Closed in `playtest: WP-PR2-11 species portrait variant selection` — **not a selector bug.** `list_portraits` collects numbered-only sets correctly (no species ships a bare `<id>.<ext>`), `resolve_portrait(variant=0)` returns the first sorted file, and the seeded variant the projection draws (`session.contact_view`) hits index 0 as often as any other across seeds — all four now pinned by `tests/test_species_portrait.py`. The real cause: a face is pinned per **(game seed, species instance)**, so a *single* instance shows one variant forever — and the dialogue play-test harness (where this was seen) injects exactly one instance per species, locking terran to one of its three faces for a given `--seed`. Fixed by giving the harness a **Portrait dial** that steps through a species' variants and names the resolved file, so every face — `_01` included — is reviewable. | WP-PR2-11 |
| PT-39 | Dialogue playtest | ~~The playtest controls modal must be keyboard navigable.~~ Fixed in `playtest: WP-PR2-09 dialogue playtest tooling fixes` — every dial is now an `ObjectRow` (the shared focusable/clickable row): ↑↓ walk the dials, Enter/Space advances the focused one, ←→ steps a multi-valued dial either way, and focus returns to the dial you flipped after the board recomposes. | WP-PR2-09 |
| PT-40 | Dialogue playtest | ~~Move the controls hotkey from `F2` to `c`.~~ Fixed in `playtest: WP-PR2-09 dialogue playtest tooling fixes` — `c` opens and closes the board (`c` was free on the contact screen underneath, which owns `b`/`f`/`j`/`f5`/digits). | WP-PR2-09 |
| PT-41 | Dialogue playtest | ~~Setting yourself hostile in the controls modal has no visible effect on the conversation.~~ Fixed in `playtest: WP-PR2-09 dialogue playtest tooling fixes`. **The dial was never broken — the corpus was, and the bug was in the real game, not the harness.** The dial does set the effective disposition (the DTO's standing/band/bar all changed), but *the greeting did not*: the fallback chain never blends packs, so a pack that authors `greeting` claims that context outright — and **every** species pack and **every** persona pack authored only a catch-all greeting. `generic`'s standing-keyed openers (which do exist) were therefore unreachable for all fifteen species, and a species you had wronged still welcomed you as a friend. Two changes: (a) every persona *and* every species greeting now carries a `when: {standing: hostile}` opener in its own voice; (b) in `select._score` a pinned `standing` counts double (`STANDING_WEIGHT`), so a hostile opener beats the same pack's situational colour ("we have met before", "your hull is scarred") instead of tying at one criterion each and being settled by a coin flip. Selection is unchanged for the pre-existing corpus (only one context anywhere mixed a standing entry with a criteria entry, and its winner is the same either way), so replays are stable. | WP-PR2-09 |
| PT-42 | Dialogue screen · station screens | ~~The art panel resets unnecessarily after each dialogue action.~~ Landed in `playtest: WP-PR2-09 art panels stop resetting`. **Two causes, two fixes.** The **contact screen** rebuilt itself on every reply (`_reopen` popped and re-pushed it), tearing down and remounting the portrait — a chafa render — at each step; between two nodes of one conversation the speaker does not change and neither does their face, so it now repaints only the speech and the reply menu **in place** and leaves the portrait mounted. The **station screens** (Stardock, Port, Starbase — the same reset, reported separately) genuinely do rebuild after an action, and each art panel came back as a *new* widget that opened on a text fallback and only swapped the image in from `on_mount`; they now open on the art they last drew (`edge/tui/art_memory.py`), so the swap is invisible. The chafa render was already memoised — what was missing was the *frame*. **Third cause, found from the same report** ("the dialogue screen and the rumour modal start smaller, then expand"): `EdgeApp.push_screen` stamped the responsive **tier class** via `call_after_refresh`, so every pushed screen laid out once under untiered CSS and again a frame later. Now stamped synchronously. That was a functional bug, not just a flicker — the tiers were not applying on first paint, so compact tables were not folding their `fold=True` columns and the wide `DetailTable` side detail panel never appeared. | WP-PR2-09 |
| PT-43 | Attack screen | ~~Button hotkeys must be indicated in the button text.~~ Fixed in `playtest: WP-PR2-10 attack-screen button hotkeys`. The labels were *already written* with their accelerators (`▶ FIRE [F]`, since `ui: WP-UI18 combat dashboard`) — and rendered without them: **a Button label is Rich markup, so the unescaped `[F]` parsed as a style tag and vanished.** Escaping it (`\[F]`, the convention `planet.py` already used) makes all four combat keys visible; the same trap had swallowed the Help (`[O]`) and Surface (`[E]`/`[T]`) accelerators, fixed alongside. Guarded three ways in `tests/test_ui_encounter_hotkeys.py`: the bracketed letter in each label *is* the key bound to the action that button fires (`EncounterScreen.BUTTON_ACTIONS` is now a class map, so a rename cannot leave a label stale), key and click issue the same command, and a repo-wide scan fails on any `Button` label whose hotkey Rich would eat. 10 snapshot baselines refreshed (encounter/surface/combat, all tiers + themes) — the letters are in the text, so monochrome loses nothing. | WP-PR2-10 |
| PT-44 | Sector scene | The dock-over-planet composite must leave room for a wreck sprite when a planet already occupies the sector. | WP-PR2-05 |
| PT-45 | Transfer modal | Draw the transfer modal over the planet screen without blanking the background — overlay it. | WP-PR2-06 |
| PT-46 | Transfer modal | Grey out transfer buttons that are unavailable because there is nothing to move. | WP-PR2-06 |
| PT-47 | Transfer modal | The `+`/`−` steppers must not exceed what is actually available. | WP-PR2-06 |
| PT-48 | Nav compass | "One-way" in the nav rose is unclear and reads as superfluous; clarify or remove it. | WP-PR2-07 |
| PT-49 | Discoveries | ~~Space discoveries should have flavorful names, not "Wreck ∗ Common". Wrecks are named after a ship; a battle wreck takes the destroyed ship's name.~~ Fixed in `playtest: WP-PR2-04 named discoveries` — `Discovery.name` is live state, stamped at creation from per-kind config pools (`names.discoveries` in `names_default.yaml`, drawn combinatorially **without replacement**, so no two finds in a universe share a name; an exhausted pool numbers itself, "Black Hole 1"). A combat wreck takes the **destroyed foe's own name**, so "Wreckage of the Vesk Marauder VII" is the raider you just shot. Names ride a **names-only sub-RNG**, so they are replay-deterministic *and* cannot move a single find — proven by generating a seed against a config with no name pools and asserting identical placement, which is why this schema epoch needed no replay-fixture churn. Sector rows and the Codex lead with the name (kind/rarity become the subtitle; the Codex gains a "Kind" column). **No store migration**: the save is `(seed, command log)` and the universe is regenerated, so there is no discovery table to migrate — the plan's assumption of one was wrong. Wire **17 → 18** (projection-only). | WP-PR2-04 |
| PT-50 | Computer map | Per-sector content text (planet/port/starbase/…) should be colored to match the legend. | WP-PR2-08 |
| PT-51 | Computer map | `P` should plot a route in the Map view too (parity with Enter and other sector tables). | WP-PR2-08 |
| PT-52 | Asteroid mining | The mining interface needs limits — a finite belt resource that depletes, reflected in the art — not unlimited extraction. | WP-PR2-13 |
| PT-53 | Invasion | ~~Invading must not force committing **all** fighters; let the player choose how many.~~ Fixed in `playtest: WP-PR2-14 partial-fighter invasion` — UI-only, as the plan predicted: `InvadePlanet` always took an amount and the core already spared the remainder (`test_citadels.py` commits 300 of 500), but the planet screen hard-coded `p.ship_fighters`. `[I]` now opens a new shared **`AmountPrompt`** (`edge/tui/screens/amount.py`) — the quantity sibling of `ConfirmScreen`, wrapping the same `AmountStepper` — defaulting to the whole wing, clamped to `1..ship_fighters`, with `[A]` to commit them all. It **is** the destructive confirmation, so it keeps `ConfirmScreen`'s safety rule: `dangerous=True` lands focus on **Cancel** and binds no screen-wide Enter, so a stray Enter after the hotkey can never land troops (Enter *in* the amount field commits, which is unambiguous intent). `tests/test_ui_actions.py`'s danger guard now accepts either confirming modal and asserts that rule. | WP-PR2-14 |
| PT-54 | Jovian worlds | Gas giants become a **Cloud City** variant: a pre-built staging area gated before stores exist, one-haul build cost, size-scaled colonist berths, and distinct floating-city art. | WP-PR2-15 |
| PT-55 | Nav compass | The nav-rose trail sector text colors should match the color convention used inside the rose itself. | WP-PR2-07 |
| PT-56 | Computer map | The map draws edges between sectors that are not actually connected (repro: sector 11703 in seed 4). | WP-PR2-08 |

When a finding is fixed, strike through its finding text and append the implementing
commit, exactly as for the first-pass table above.
