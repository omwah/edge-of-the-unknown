# Playtest tuning notes

Small, living notes on tuning knobs that only reveal their feel in play. Each
names the config path, the current default, and what to watch for.

## Core governance (`aliens.governance`, WP51/WP52)

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

## WP77 readiness (the A10 hands-on pass — seams arc, July 2026)

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
