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
