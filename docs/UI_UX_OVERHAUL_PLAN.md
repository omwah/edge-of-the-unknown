# Modern ANSI UI/UX Overhaul

## Goal and non-negotiable contract

Modernize the full Textual interface while preserving TW2002 identity: ANSI
cyan/yellow/magenta, ASCII art, terse command cadence, and direct expert
hotkeys remain. The redesign adds hierarchy, responsive layouts, progressive
onboarding, accessible themes and focus, consistent feedback, and equivalent
keyboard/mouse operation.

Supported layouts:

- **Compact:** 80–99 columns or 24–29 rows. Gameplay information wins over art.
- **Standard:** 100–119 columns and at least 30 rows. Authored at 100×34.
- **Wide:** at least 120×36. Adds detail panes and richer art.
- Below 80×24, show a size notice while preserving Help and Quit.

The TUI continues to use only the `GameClient`/service and fog-safe DTO seams.
Presentation preferences stay outside universe state, replay logs, and hashes.
No economy, combat, dialogue, or other gameplay rule changes belong in this
project unless a UI change exposes an existing defect.

## Shared component workbench

The ship Engine Room and a starbase Station must instantiate the **same
underlying `ComponentWorkbench` widget**. Neither host may contain a private
slot renderer. The widget owns layout, slot/inventory rendering, selection,
focus, keyboard/mouse handling, responsive behavior, and typed selection
messages. It never imports `GameService` or command reducers; each host
translates selections into its existing commands.

Both hosts consume the already-shared `Subsystem`/`Slot` DTO shapes but pass a
different `ComponentWorkbenchProfile`:

| Context | Canonical DTO name | Player-facing name | Art | Color |
|---|---|---|---|---|
| Ship | `SPINDRIVE` | Spindrive | Field drive | Cyan |
| Ship | `THRUSTERS` | Thrusters | Rocket/plume | Amber |
| Ship | `SCREENS` | Screens | Faceted shield | Blue |
| Ship | `MAIN GUN` | Main Gun | Spinal barrel | Red |
| Base | `FUSION REACTOR` | Fusion Core | Ring/core installation | Magenta |
| Base | `SCREENS` | Defense Grid | Multi-emitter array | Bright cyan |
| Base | `MAIN GUN` | Orbital Battery | Turret/battery | Yellow |

Ships retain rounded panels and `+ / ! / blank / ✓` slot states. Bases use
heavy industrial borders and square installation glyphs. Monochrome mode must
still distinguish them by titles, glyphs, copy, and art.

## Presentation interfaces

- `UISettings`: theme, reduced motion, art detail, density, onboarding, and
  disabled-reply visibility; persisted locally as JSON.
- `LayoutTier`: compact, standard, wide, unsupported; calculated centrally.
- `ActionDescriptor`: stable ID, title/help, key, enabled state/reason, danger,
  and action. Footer, `.`, `?`, `Ctrl+P`, and clicks derive from it.
- `ComponentWorkbenchProfile`, `WorkbenchCapabilities`, and
  `WorkbenchSelection`: configure the shared component UI without embedding
  rules in the widget.

## Work packages

Each WP is one independently reviewable commit. Run its targeted tests before
committing. Update normative documentation and affected screenshots in the same
WP as the behavior they describe.

### M1 — Specification and baseline

#### WP-UI01 — Responsive UX specification

- Update DESIGN §11 with layout tiers, accessibility rules, action discovery,
  and preference behavior.
- Update DESIGN §§4.1/4.2 to require the shared component workbench.
- Update UI mockups with compact/standard/wide archetypes.
- Record current Textual, Harlequin, CLI, and WCAG research.
- Verify every player screen has an archetype and the keymap has no conflicts.

#### WP-UI02 — Textual and screenshot baseline

- Upgrade Textual 8.2.7 → 8.2.8.
- Add `pytest-textual-snapshot` as a dev dependency and document it in §15.
- Parameterize deterministic captures by size, theme, and art detail.
- Smoke-test menu, game, Computer, contact, workbench, and lobby.

### M2 — Design system and shell

#### WP-UI03 — Semantic themes

- Add `edge-ansi`, `edge-high-contrast`, and `edge-monochrome`.
- Define semantic text, muted, disabled, focus, selection, success, warning,
  danger, ownership, and rarity tokens.
- Replace raw color markup incrementally.
- Enforce 4.5:1 text and 3:1 focus/control contrast.

#### WP-UI04 — Persistent presentation settings

- Load preferences before the first screen mounts; save atomically.
- Recover from corrupt files with defaults and one warning.
- `--plain` temporarily forces reduced motion/minimal effects without saving.
- Prove settings never affect state hashes or command logs.

#### WP-UI05 — Responsive shell and chrome

- Centralize tier calculation and tier CSS classes.
- Add shared title bar, scroll body, context strip, action row, footer, empty
  state, and modal sizing.
- Preserve focus/selection/scroll when crossing breakpoints.
- Provide the below-minimum size notice.

#### WP-UI06 — Unified action discovery

- Derive `.`, `?`, `Ctrl+P`, footer, and click affordances from one descriptor
  list per active context.
- Show disabled actions with their prerequisite.
- Keep reserved global keys and deny-focused destructive confirmations.
- Add collision and parity tests.

#### WP-UI07 — Feedback, focus, and forms

- Standardize notification severity/titles/timeouts and inline validation.
- Prevent duplicate submissions while work is running.
- Restore initiating focus after modals and use visual reading-order Tab order.
- Make all forms and dialogs usable at 80×24.

### M3 — Shared component mechanism

#### WP-UI08 — Presentation-neutral workbench

- Extract subsystem panels and loose-component selection into one widget.
- Support compact one-column, standard two-column, and wide base three-column
  layouts; art detail may hide decoration, never state.
- Support click, Tab/arrows, Space/Enter, typed selections, and reconciliation
  after DTO refresh.
- Unit-test every slot state and assert there are no service/command imports.

#### WP-UI09 — Ship Engine Room migration

- Replace all private engine-room panel/picker rendering with the workbench.
- Preserve patch, dock repair, install, swap, and cannibalize commands.
- Use canonical DTO names to construct enums; display aliases stay presentational.
- Refresh in place rather than pop/push and test keyboard/mouse parity.

#### WP-UI10 — Starbase Station migration

- Replace private station cards with the same workbench.
- Apply base-specific names, colors, glyphs, industrial art, and instructions.
- Make repair and salvage explicit selections rather than silently choosing the
  first component/slot; leave Claim and Assault as base-level actions.
- Structurally test that both hosts contain `ComponentWorkbench` and no second
  base slot renderer exists.

### M4 — Core exploration and commerce

#### WP-UI11 — Menu and onboarding

- Improve menu hierarchy, save metadata, and primary Continue/New action.
- Add dismissible Captain's objectives: dock, trade, inspect/upgrade, scan,
  discover. Store only local presentation progress.
- Disable repeating effects for plain/reduced-motion modes.

#### WP-UI12 — Responsive sector view

- Preserve scene/nav rose as the visual center.
- Compact hides art and sidebar first, adds an `I` status drawer, and retains
  location, objects, navigation, turns, hazards, and latest event.
- Standard keeps grouped status; wide adds objectives/presence/anomaly detail.
- Give every coordinate hotspot a focused keyboard/list equivalent.

#### WP-UI13 — Navigation clarity

- Strengthen selected-warp focus and label band, explored/one-way/hazard state,
  turn cost, Core bearing, and backtrack status with glyphs/text.
- Route confirmation summarizes destination, hops, turns, hazards, avoids, and
  interruption risk without duplicating reducer logic.

#### WP-UI14 — Unified trade presentation

- Keep one `TradePanel` at ports, StarDock, and bases.
- Use explicit “Port buys/sells,” aligned numbers, stock/capacity, unit price,
  estimated total, hold impact, and purse limitation.
- Preserve cursor across market refresh; compact moves secondary columns into
  selected-row detail.

### M5 — Progression and encounters

#### WP-UI15 — Service hubs

- Apply one service-hub pattern to StarDock and bases.
- Compact uses a scrollable selector instead of overflowing tabs.
- Explain unavailable services and preserve reducer-side eligibility.

#### WP-UI16 — Planet and surface

- Separate identity/ownership/habitability, colony economy, base, citadel, and
  cargo transfer into progressive panels.
- Compact prioritizes site list/detail over terrain art.
- Keep all colonize/transfer/Genesis/citadel/descent/survey actions available.

#### WP-UI17 — Alien contact

- Make portrait/dialogue/replies responsive; current speech and numbered replies
  have priority.
- Show named standing plus meter/text and optional disabled-reply reasons.
- Preserve authored order, recency, session facts, and all contact actions.

#### WP-UI18 — Combat dashboard

- Separate enemy pack, player condition, round result, tactical advice, and
  actions. Keep the last result until the next action.
- Label firing arcs, flee odds/floor, ammo, kits, hull/shields, and component
  damage without relying on color.

#### WP-UI19 — Territory, corporations, lobby, and minor screens

- Make card grids responsive; clarify corporation empty/member/CEO states.
- Add persistent lobby labels, connection progress, inline errors, and retry
  without losing input.
- Apply shared forms, modals, and empty states throughout.

### M6 — Computer information architecture

#### WP-UI20 — Computer categories

Replace thirteen flat tabs with categories while preserving all subviews:

- Navigation: Map, Route.
- Commerce: Ports, Trade, Market.
- Exploration: Planets, Codex, Leads.
- Relations: Contracts, Alliances, Dossier.
- Records: Log, Notes.

Remember the last subview per category. Direct Map/Log/route/codex/contract
links must open the correct target. Compact uses a vertical or popup selector.

#### WP-UI21 — Tables and detail views

- Standardize headers, alignment, cursor, zebra, empty states, and stable keys.
- Add `/` filtering and sorting only where existing DTO data supports it.
- Compact hides low-priority columns into a detail overlay; wide adds a side
  detail pane. Preserve logical selection across refresh.

### M7 — Regression and acceptance

#### WP-UI22 — Responsive visual regression matrix

- Capture every player screen at 80×24 and 100×34, representative dense screens
  at 120×40, and core screens in high-contrast/monochrome.
- Assert visible or keyboard-scrollable geometry, action parity, key collisions,
  and destructive confirmation coverage.

#### WP-UI23 — Hands-on acceptance

Exercise new-player, veteran-keyboard, mouse-only, compact, hosted, workbench,
and monochrome scenarios. Fix all blocked-progress, hidden-action, lost-focus,
clipped-control, misleading-trade, missing-confirmation, and color-only defects.

Final acceptance:

- A new player reaches a first trade without external help within five minutes.
- A veteran's dock/trade/warp path gains no mandatory screen.
- Resizing preserves screen, subview, focus, row, input, conversation,
  workbench selection, and route.
- All core/replay/economy/combat/dialogue/multiplayer tests pass.
- DESIGN, mockups, style guide, screenshots, and implementation agree.

## Global implementation rules

- Commit after every WP and include its identifier in the subject.
- Never modify `references/`.
- Prefer in-place refresh to screen reconstruction.
- Do not duplicate slot, action, form, empty-state, title, or breakpoint logic.
- Remove decorative art before gameplay information under space pressure.
- Every key action has a mouse/selectable affordance.
- Every disabled action explains why; every destructive action confirms.
- Every color state also has text or a glyph.
- Run targeted tests per WP and `pixi run check` before each milestone closes.
