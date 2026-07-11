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
overhaul. They were originally recorded in `~/edge_notes.txt`; this section is
now the durable project copy. All findings are open at the time of capture. The
detailed implementation sequence, architectural decisions, affected areas, and
acceptance criteria live in
[`PLAYTEST_REMEDIATION_PLAN.md`](PLAYTEST_REMEDIATION_PLAN.md).

| ID | Area | Finding | Planned work |
|---|---|---|---|
| PT-01 | Combat aftermath | ~~Destroying a ship should visibly change the sector. Prefer creating a persistent wreck discovery and recovering salvage through that discovery, leaving evidence that a battle occurred here.~~ Implemented by `playtest: WP-PR01 persistent combat wrecks`. | WP-PR01 complete |
| PT-02 | StarDock catalog | Move missiles and Genesis torpedoes into the Devices catalog and rename the tab **Devices & Armaments**. | WP-PR08 |
| PT-03 | StarDock focus | After a Devices purchase, keep the purchased row highlighted instead of returning focus to the tab, matching Trade behavior. | WP-PR08 |
| PT-04 | StarDock bindings | Rumor purchase and notice posting should be available only in the Tavern, not as screen-global actions. | WP-PR08 |
| PT-05 | StarDock bindings | Deposit and withdrawal should be available only in the Bank tab, not as screen-global actions. | WP-PR08 |
| PT-06 | Colonist recruitment | Add a StarDock Colonists tab. It should use station-concourse art showing people moving through a busy orbital station; generate a raster concept and convert it through the image-to-ANSI pipeline. | WP-PR08 |
| PT-07 | Tavern | Improve the bounty board's information hierarchy and interactions; the current single-column prose list is difficult to scan. | WP-PR08 |
| PT-08 | Computer / Planets | Sort player-owned planets ahead of the normal selected sort order and show their ownership clearly. | WP-PR09 |
| PT-09 | Computer / Ports | Show when a port is attached to the player's starbase and sort those ports ahead of the normal selected sort order. | WP-PR09 |
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
| PT-23 | Computer / Avoid list | Make adding a sector to the route avoid list discoverable through visible actions and Help; the current `V` workflow is not obvious. | WP-PR09 |
| PT-24 | Genesis feedback | Distinguish “no Genesis torpedo aboard” from “Genesis cannot be deployed on this target” and state the specific target blocker. | WP-PR12 |
| PT-25 | Starbase assault | A starbase assault should render the target base, not ordinary ship art. | WP-PR12 |
| PT-26 | Combat language | ~~Replace or explain “the pack is destroyed”; player-facing results should state concretely which enemies were destroyed or retreated.~~ Fixed in `playtest: WP-PR03 alien retreat state and copy`. | WP-PR03 |
| PT-27 | Contracts | Retain completed contracts in the Computer and render them grey/dim with actions disabled instead of hiding them. | WP-PR09 |
| PT-28 | Black holes | ~~First activation of a black hole can crash the game when gravity damage is applied to the player's ship. Reproduce with both mouse and keyboard and cover lethal and nonlethal damage.~~ Did not reproduce — the lethal-hazard crash was already closed by the WP26/WP75 escape pod; regression-locked in `playtest: WP-PR05 black-hole interaction crash`. | WP-PR05 |
| PT-29 | StarDock Shipyard | The currently flown hull is shown as purchasable even though it cannot be bought. Mark it as current and disable its purchase action. | WP-PR08 |
| PT-30 | Asteroid belts | ~~Asteroid belts are not landable planets and must not expose colonies, citadels, colony stores, or planetary descent. Preserve only their intended scanning/mining interactions.~~ Fixed in `playtest: WP-PR06 asteroid-belt interaction model` — per-type `landable`/`colonizable` capabilities gate every seam; belts generate/normalize inert (unowned, base-less, no surface sites) and render an orbital view. | WP-PR06 |
| PT-31 | Computer routing | Plotting a route from a non-Navigation subview briefly shows Route and then returns to the original subview. The completed action must remain on Route without a flash-back. | WP-PR09 |

When a finding is fixed, strike through its finding text and append the implementing
commit. Do not remove closed findings; they are the acceptance history for the
remediation pass.
