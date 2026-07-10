# Seams & gaps audit — July 2026

An audit of every seam deliberately left during Phases 1–5/4, verified against the
code as of `402c7be` (Phase 4 / M21 complete), plus unimplemented TUI features and
gameplay problems found by inspection. Sources: the Claude session logs for this
project (seam/deferral mentions extracted and de-duplicated), the plan documents
(`PHASE3_PLAN.md`, `PHASE5_4_PLAN.md`), and the code itself.

Each item carries a **Course of action** and, where the fix needs a product call,
a **Decision point** (D1–D10, resolved by interview — answers recorded in §6).

The headline finding: **core is far ahead of the TUI.** Whole shipped systems —
alliance membership, starbase assault/repair/claim, contract fulfilment, sector
territory, probes/interdictor, PvP — have reducers, events, codecs, and tests but
no player-reachable entry point in the TUI. Most of the user-visible complaints
(placeholder tabs, "Phase 2" messages, can't attack first) are symptoms of that
one pattern.

---

## 1. Category A — Deliberate seams from the session logs (status verified)

### A1. The contact-screen `attack` choice is still Phase-3-gated — **stale stub, high priority**
- `edge/core/rules.py:3285` — a dialogue choice with `action: attack` raises
  `"you cannot attack here (Phase 3)"`. Phase 3 shipped the entire combat system,
  but this gate was never lifted; `edge/dialogue/intents.py:36` still carries the
  matching "Phase-3-gated" comment. The default corpus *does* author an attack
  choice (`config/alien_dialogue_default.yaml:305`), so players see the option and
  get refused.
- This is one half of the "you cannot attack a ship on your own" complaint (the
  other half is B1/B6: no in-sector engage affordance at all).
- **Course of action:** lift the gate — an attack choice ends the conversation and
  opens a hostile `Encounter` with the species (reuse the WP24 encounter spawn with
  a forced-violence opener; betrayal consequences via the WP27 attitude/memory rail
  already exist for exactly this). `influence_gate`'s `attack_forbidden` check stays.
  Covered by decision **D2** (how broad the attack surface should be).

### A2. Signature mechanics: 9 of 10 hooks are registry-complete but corpus-dark
- `edge/core/mechanics.py:163` documents it: no default species routes any dialogue
  choice into a `sig.*` context. The corpus contains **zero** `sig.*` context keys
  (only spec-header comments). The roster assigns signature hooks to 13 species
  (trojan_gift, reprogram_unlock, escalating_demand, flee_drop, morality_judge,
  influence_gate ×2, contract_kill ×2, coordinate_broker ×2, passage_broker,
  literalist-none). Of these only the ones with non-dialogue trigger paths do
  anything in play: `contract_kill`/`coordinate_broker` (via `accept_contract` /
  `accept_lead` actions) and `influence_gate` (the attack-forbidden check — itself
  moot while A1 stands). trojan_gift, reprogram_unlock, escalating_demand,
  flee_drop, passage_broker, morality_judge never fire.
- Sub-seams inside the hooks themselves (documented in `mechanics.py`): the
  trojan's device/hold-occupying payload + delayed cron trigger, reprogram_unlock's
  live cross-faction `trade_posture` flip.
- **Course of action:** author `sig.*` choice routes into the corpus for the dark
  hooks (the dialogue authoring pipeline exists for exactly this), or trim the
  roster to wired hooks. Decision **D4**.

### A3. Escort contracts: the merchant is never targetable in combat (WP57 seam)
- The convoy lifecycle (movement, completion, abandon, deadline) is implemented and
  tested, but the "encounter targets the escorted merchant, destroying it and
  failing the contract with the full consequence rail" branch was left as a seam —
  so an escort can never actually be lost to violence, only to the deadline.
- **Course of action:** implement the config-weighted foe-target roll in the
  encounter reducer when an escort is active. Small, self-contained. Decision
  **D6** (bundle into a polish WP).

### A4. Route hazards channel still empty (Phase-2 seam never lit)
- `edge/server/session.py:1160` — `RouteDTO.hazards=[]` with the comment "Phase-3
  encounter seam (empty in Phase 2)". Phase 3 shipped hostile bands, black holes,
  and hostile sector forces; the route planner still warns about none of them, and
  the Computer's hazard-confirm modal (`computer.py:428`) can never appear.
- **Course of action:** populate hazards from known-graph knowledge the player
  already has (charted black holes, known hostile forces, band interrupt risk) —
  fog-of-war-safe because it reads the player's own knowledge. Decision **D6**.

### A5. Lethal hazards clamp instead of podding (WP41 seam)
- `edge/core/rules.py:1335` — "Hazard damage is clamped to leave the ship alive (a
  lethal hazard routing through the escape pod is a documented seam)". Mines and
  black holes can never kill, which softens the frontier's danger.
- **Course of action:** route hull-0 hazard damage through the WP26 escape-pod
  rule. Decision **D6**.

### A6. NPC-side force deployment + `starbase_policy` placement refinement + toll-charging NPCs
- Sector fighters/mines/beacons are player-only; NPCs never deploy forces, and
  `starbase_policy` does not refine base placement (WP41/WP34 deliberate scope).
- **Course of action:** genuine future content (an "NPC territoriality" package);
  record as roadmap, not a defect. Decision **D6**.

### A7. WP61's TUI async migration was deferred
- `app.service` remains a synchronous back-compat property because Textual
  `compose`/`render` can't await; the load-bearing seam (client-owned ticker,
  `GameClient` async surface) is in place and the remote client ships on it.
- **Course of action:** leave as-is. It is architecture debt only; revisit if a
  screen ever needs live push updates mid-compose. No decision needed.

### A8. PvP online-defender hybrid; other explicit non-goals
- The plan records these as "record a seam, build nothing": online-defender PvP
  duels, griefing mitigations beyond Core+toggle, PostgreSQL, multi-server lobby.
  All still true and intentional. No action.

### A9. Dialogue-engine deferred improvements (from the engine evaluation)
- Two improvements were deferred: **session variables** and a **Twine round-trip
  bridge** for corpus authoring. Still open, purely additive. Decision **D6**.

### A10. Balance playtest never happened interactively
- Phase 3's exit criterion was assessed mechanically (faucet math + written
  assessment); the combat-frequency/threat knobs were left "as config dials for a
  hands-on feel-tune" (`PLAYTEST_NOTES.md` documents the dials). The known data
  point: the starter Trailblazer loses to a 3-foe quill swarm in ~4 rounds.
- **Course of action:** a real playtest pass once the TUI gaps above are closed
  (playtesting now would mis-tune against a UI missing half the systems).

---

## 2. Category B — Shipped core systems with **no TUI entry point**

Verified by grepping every command class for references under `edge/tui/`
(excluding `dummy.py`). "Dark" = zero wiring; the feature is unreachable in play.

| # | System | Dark commands | Consequence in play |
|---|--------|---------------|---------------------|
| B1 | **Alliance membership** (P3 M13) | `AdvanceAdmission`, `JoinAlliance`, `ResignAlliance` | The join-one-bloc pillar — admission tasks, rival fallout, Core-standing flips — is invisible. Contact screen shows the species' alliance as a text label only. |
| B2 | **Starbase ops** (P3 WP40) | `AssaultStarbase`, `RepairStarbase`, `ClaimStarbase` | Can't raze a set-piece base (so `destroy` contracts and contract_kill payouts are unfulfillable); can't repair/claim a derelict into a forward foothold (a Phase-3 headline). Only component *scavenging* is wired (planet screen `S`). |
| B3 | **Contract fulfilment** (P5 WP57) | `DeliverContract`, `AbandonContract` | You can *accept* a deliver favor in dialogue but never deliver it — it can only expire. The Computer's Contracts tab is a read-only list with no actions. (Escort completes reducer-side on arrival; destroy blocked by B2.) |
| B4 | **Sector territory** (P3 WP41) | `BuyFighters`, `BuyMines`, `DeployFighters`, `DeployMines`, `DeployBeacon` | Fighters/mines/beacons — deploy modes, tolls, the classic TW sector game — fully dark. |
| B5 | **Devices** (P5 WP56) | `LaunchProbe`, `ToggleInterdictor`, `RemoveLimpets` | The StarDock Devices tab *sells* probes/interdictor/deflectors and its caption says "Launch probes & toggle the interdictor in flight" — but there is no launch or toggle anywhere. Limpets can attach to you and can never be removed. |
| B6 | **PvP** (P4 WP67) | `AttackPlayer` | No attack affordance — and other players' ships are not even projected into `SectorDTO.ships` (`session.py:312` lists species only), so in hosted multiplayer another player in your sector is literally invisible. The WP67 plan's "Projection/TUI" bullet was not built. |
| B7 | **Dock repair & upgrades** | `RepairAtDock`, `SwapComponent` | Engine-room `U` "Upgrade" is a noop; there is no way to repair hull/components at StarDock. After combat you're limited to field patches (in combat only, see B8) and cannibalize/install. |
| B8 | **Field patch outside combat** | `FieldPatch` | Wired in the encounter screen (`K`) but the engine room's advertised `P` Field-patch is a noop — you can't patch between fights. |
| B9 | **Bank at StarDock** | `Deposit`, `Withdraw` (wired only at forward bases, fixed 1 000) | The StarDock Bank tab says "Deposit / withdraw / interest — Phase 2." while the core bank (`Player.bank_balance`, `_bank` reducer) has existed since Phase 5 and *is* usable at player forward bases — in fixed 1k increments only. |
| B10 | **Corp management** (P4 WP66) | `InviteToCorp`, `AcceptCorpInvite`, `ExpelFromCorp`, `DeclareCorpWar`, `EndCorpWar`, `TransferPlanetToCorp/From` | Corp screen wires form/deposit/withdraw/leave only. Invitations, war, and asset transfer are dark — corp war (a WP66 headline) can't be declared. |

**Course of action (the core of the correction plan):** a "TUI surfacing" work
package series — see §5. Decisions **D1** (priority order), **D2** (attack
surface shape), **D3** (hotkey scheme these new affordances land in).

---

## 3. Category C — TUI skeleton leftovers

- **C1. Dead screens.** `screens/map.py` (`MapScreen`) and `screens/messages.py`
  (`MessagesScreen`) are referenced only by the screenshot harness (`shots.py`).
  Both were superseded by Computer tabs (Map / Log); both are stuffed with noop
  bindings ("Zoom", "Search", "Filter", "Mark read") and stale "Phase 3" copy.
  **Action:** delete (with their shots entries), or wire their noops if kept.
  Decision **D5**.
- **C2. Computer Notes tab.** `computer.py:116` — "Avoid lists & player notes —
  Phase 2." plus a noop `A` "Add note" binding. The one §9 mockup tab never built
  (deliberately deferred in the WP14/15 era). **Action:** build (notes +
  avoid-list honored by the route planner) or drop the tab. Decision **D5**.
- **C3. Main menu.** `L` Load and `O` Options are "unavailable". Load is
  arguably redundant with Continue + the lobby; Options has no backing settings
  screen. **Action:** decision **D5**.
- **C4. Stale placeholder copy.** `engine_room.py:8` docstring says knockouts
  "Phase 2 (nothing is knocked out yet)" — false since WP26. `stardock.py:6`
  says "Bank/Tavern remain stubs" — the tavern has been live since WP58.
  `game.py:6` says "the deferred Phase 2-3 screens still open on sample data" —
  false for every screen except the dead C1 pair. **Action:** fix the copy in
  whatever WP touches each file; no decision needed.
- **C5. Help is only a warp legend.** `HelpScreen` (bound to `?`) shows warp
  colors and nothing else — no key reference, which compounds the hotkey problem.
  **Action:** part of the hotkey redesign (D3).

---

## 4. Category D — Hotkey audit (inconsistent, overloaded, undiscoverable)

Full inventory extracted from every `BINDINGS` table. GameScreen alone has 13;
StarDock 10; Planet 10. The complaints check out — the same key means different
things screen to screen, several advertised keys are noops, and multi-step
features hide behind single letters with no discoverability beyond the footer.

**Conflicts / inconsistencies (worst offenders):**

| Key | Meanings by screen |
|-----|--------------------|
| `g` | Game: open Log · Planet: **Genesis torpedo** (destructive!) · StarDock: Buy Genesis · Computer: Engage route · Messages: back |
| `t` | Game: Corp screen · Port/StarDock: Trade · Planet: Trade (**noop**) · Surface: Take find |
| `s` | Game: Survey planet · Planet: Salvage · Computer: **Seize Core** (a petition, next to harmless keys) |
| `k` | StarDock: Recruit colonists · Planet: Build citadel · Encounter: Field-patch |
| `b` | Game: Base services · StarDock/Starbase: Buy · Contact: Back one |
| `h` | Game: Hail · Port/StarDock: Haggle |
| `m` | Game: Map · Encounter: fire Missile · Starbase: buy Missile (StarDock uses `i` for the same thing) · Messages: back |
| `q` | Main menu: quit app · Port/Help: close screen (elsewhere `escape`) |
| `y` | Corp/Starbase: Withdraw (unmnemonic; planet treasury uses `+`/`-` instead) |
| `p` | Game: Dock · Computer: Plot route · Engine room: Field-patch (**noop**) |

**Advertised-but-noop keys:** Engine room `P`/`U` (the footer text itself
advertises them), Computer `A`, Planet `T`, Map `+`/`-`/`/`, Messages
`enter`/`f`/`m`, menu `L`/`O`.

**Structural problems:**
1. **No global consistency contract** — nothing reserves keys for global actions
   vs screen-local verbs, so collisions accumulated one screen at a time.
2. **No discoverability layer** — the Footer truncates on narrow terminals, Help
   shows no keys, and there is no command palette; features live *only* in
   hotkeys, which is why they feel "buried".
3. **Dangerous keys sit beside routine ones** (Genesis `g` next to Log `g`
   muscle-memory; Seize Core on `s`).

**Course of action:** a keymap-normalization WP: (a) a written keymap convention
in `UI_MOCKUPS.md` (reserved global keys; per-screen verbs drawn from a consistent
vocabulary: Esc=back everywhere, one Trade key, one Buy key, arrows+enter for
tables); (b) a real Help keymap overlay; (c) optionally a command palette and/or
numbered action menu to de-bury features. Shape is decision **D3**; confirm
dialogs for destructive actions is decision **D7**.

---

## 5. Course of action — proposed work packages

Execution order (interview, July 2026): **WP70 → WP75 → WP71 → WP72 → WP73 →
WP74 → WP76 → WP77**. Combat initiative leads (D1); the danger-polish bundle
follows immediately because it is cheap (D6); multiplayer parity is in-arc, not
deferred (D10) — WP70 includes other-player rendering + `AttackPlayer`, and the
corp UI (WP76) ships in this arc. Sizes are relative (S/M/L).

- **WP70 — Combat initiative (M) — SHIPPED.** New `AttackSpecies` command +
  `_attack_species` reducer (pack spawn via the WP24 machinery; first-strike souring
  at initiation — one kill's worth with an honest grudge cause — plus §6.4 spillover);
  gates live in the shared pure `encounters.first_strike_block` (Core sanctuary /
  Entity / influence_gate / shipless kinds), used by both the reducer and
  `session._gate_choice` so the FIGHT menu and the rule agree. The A1 stub is gone:
  the contact `attack` reply delegates to `_attack_species` and the TUI pops back to
  the encounter screen. Game screen gained `A` Attack + a ConfirmScreen (D7) with
  distinct species/player wording; other players project into `SectorDTO.ships`
  (`player_id`, corp tag + outlaw ☠ in the name) and are clickable "(Engage)" targets
  wired to `AttackPlayer` (closing B6). Codec entry, WIRE_VERSION 1→2 + wire-fixture
  regen, H9 three-place dialogue-spec sync, DESIGN §6.7/§10 updated. Tests:
  `tests/test_attack_species.py` (gates, souring, lockstep, projection, replay hash)
  + rewritten contact-menu / contact attack tests.
- **WP75 — Danger polish (S, runs second per D6) — SHIPPED.** Escort-merchant
  targeting (A3): each fought round with a live foe and an escorted merchant in the
  fight's sector, a config-weighted roll (`aliens.contracts.escort_target_chance`,
  default 0.25) drops the volley on the convoy — contract failed
  (`merchant destroyed`) with the full WP27 rail against the issuer (souring +
  honest-cause grudge + §6.4 spillover). Route hazards (A4): `RouteDTO.hazards`
  now lists charted black holes + known hostile forces (explored hops only —
  full-graph lead routes stay fogged) + per-band encounter interrupt risk; the
  Computer's hazard-confirm modal fires for real. Lethal hazards (A5): black-hole
  tolls and mine fields route hull 0 through the WP26 escape pod (`ShipDestroyed`,
  no engagement spawns over the wreck). Tests: `tests/test_danger_polish.py` +
  the rewritten `test_black_hole_lethal_toll_pods_the_player`. NPC territoriality
  (A6) stays roadmap.
- **WP71 — Surfacing pass 1: the frontier loop (L) — SHIPPED.** Planet screen
  gained `A` Assault / `R` Repair / `B` Claim (B2) driven by new
  `PlanetDTO.base_assaultable/base_claimable/base_claim_cost/base_empty_slots`
  (keystone-first, so repair heads straight for what revives a derelict); the
  Computer Contracts tab gained `D` Deliver / `X` Abandon (row-keyed) and the
  port screen a `D` Deliver shortcut (B3); the engine room's `P` field-patch and
  `U` upgrade are live plus a new `R` dock repair (`RepairAtDock`; B7/B8); the
  StarDock Bank tab is real — balance, typed-amount `D`/`W` deposit/withdraw via
  `_AmountInput`, and the interest note (B9/D8 — the `interest_accrual` cron and
  `economy.bank_interest_per_day` already existed, so only the UI was missing).
  Tests: `tests/test_surfacing.py` (projection seam).
- **WP72 — Surfacing pass 2: territory, devices, alliances (L) — SHIPPED.** New
  `TerritoryScreen` (game screen `D` Deploy) driven by a new `territory_view` /
  `TerritoryDTO`: deploy fighters (mode picker incl. toll), armid/limpet mines,
  beacon, probe launch, interdictor toggle, limpet strip (B4+B5); StarDock `F`/`M`
  buy fighters/mines. Alliances on both surfaces (B1/D9): contact screen `J`
  Join/Resign derived verb (`ContactDTO.alliance_id`/`alliance_member`) and a
  Computer **Alliances** tab (`ComputerDTO.alliances` / `AllianceRowDTO`: standing,
  gate, fee, admission ledger, governor/covets flags) with `J` join/resign and `T`
  log-admission-task (the WP38 seam surfaced; gameplay hooks still to feed it).
  WIRE_VERSION 2→3 (+ WP71's DTO fields) with fixture regen; `territory_view` on
  GameClient/LocalClient/RemoteClient + the net read whitelist. Tests:
  `tests/test_surfacing.py` WP72 section.
- **WP73 — Keymap normalization & discoverability (M).** The §4 plan: a keymap
  convention doc in `UI_MOCKUPS.md`, conflict fixes, a real Help keymap, **and a
  numbered context-action menu** (one key lists everything doable here) (D3);
  ConfirmScreen on Genesis / Seize Core / Invade / ResignAlliance / friendly
  first-strikes (D7); stale-copy fixes (C4); delete `MapScreen`/`MessagesScreen`
  + their shots entries, **build the Notes tab** (notes + route-planner
  avoid-list), drop menu Load, add a minimal Options screen (D5).
- **WP74 — Signature-mechanic corpus (M, content).** Author `sig.*` routes for
  all six dark hooks — authored directly in-session (D4: Claude writes the
  corpus content, human-reviewed; not the local-model pipeline) — and wire the
  trojan device/cron payload and reprogram posture-flip sub-seams live.
- **WP76 — Corp completeness (S–M).** Invite/accept/expel/war/transfer UI (B10) —
  in-arc per D10.
- **WP77 — Balance playtest (ongoing).** A10, after WP70–73 land.

---

## 6. Decision points (interview record)

Interview held 2026-07-08.

| # | Question | Decision |
|---|----------|----------|
| D1 | Priority order of the correction WPs | **Combat initiative first** (WP70 leads) |
| D2 | Attack surface | **Both**: in-sector Engage + live contact attack choice; PvP rides the same affordance |
| D3 | Hotkey scheme | **Normalize + numbered context-action menu**: convention doc, conflict fixes, Help keymap, action menu |
| D4 | Dark signature hooks | **Author corpus for all six** — Claude authors the content directly (human-reviewed), not the local-model pipeline |
| D5 | Skeleton leftovers | **Delete dead screens; build the Notes tab; drop menu Load; build a minimal Options screen** |
| D6 | Danger polish bundle | **Do it early — it's cheap** (WP75 runs right after WP70); NPC territoriality stays roadmap |
| D7 | Destructive confirms | **Yes**: ConfirmScreen on Genesis, Seize Core, Invade, ResignAlliance, friendly first-strikes |
| D8 | Bank scope | **Deposit/withdraw + daily interest tick** (config rate, existing daily cron) |
| D9 | Alliance UI home | **Both**: contact-screen derived verbs + a Computer Alliances tab |
| D10 | Multiplayer TUI parity | **Parity now**: other-player rendering + AttackPlayer in WP70; corp UI (WP76) in-arc |
