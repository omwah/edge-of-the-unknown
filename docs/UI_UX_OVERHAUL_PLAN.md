# Detailed Game-Wide Modern ANSI UI/UX Overhaul

## Summary and Design Contract

Modernize the entire TUI while preserving its TW2002 identity: cyan/yellow/magenta ANSI presentation, ASCII art, terse commands, and expert hotkeys remain; layout hierarchy, onboarding, accessibility, mouse support, responsive behavior, and feedback become substantially clearer.

The implementation should follow the current official Textual guidance for [themes](https://textual.textualize.io/guide/design/), [layout](https://textual.textualize.io/guide/layout/), [command discovery](https://textual.textualize.io/guide/command_palette/), and [Pilot/snapshot testing](https://textual.textualize.io/guide/testing/). Upgrade the lockfile from Textual 8.2.7 to 8.2.8. [Textual 8.2.8 release](https://github.com/Textualize/textual/releases/tag/v8.2.8)

The redesign must support:

- Compact terminals at 80×24.
- Standard layouts at 100×34.
- Enhanced layouts at 120×40 and larger.
- New players through visible objectives, explanations, and discoverable actions.
- Experienced players through unchanged direct-key efficiency.
- Keyboard-only, mouse-only, local-terminal, remote-terminal, and browser-served play.
- Ship engine rooms and starbase component stations rendered and operated by one shared component-workbench widget, while using context-specific names, colors, art, copy, and commands.

No gameplay rule, economy, replay, dialogue-selection, or fog-of-war behavior should change unless a UI requirement exposes an existing projection defect.

## Public and Internal Interfaces

### Presentation settings

Add a TUI-only `UISettings` model stored separately from universe state:

```python
@dataclass(frozen=True)
class UISettings:
    theme: str = "edge-ansi"
    reduced_motion: bool = False
    art_detail: Literal["full", "compact", "minimal"] = "full"
    density: Literal["comfortable", "compact"] = "comfortable"
    show_onboarding: bool = True
    show_disabled_options: bool = False
```

Settings are local preferences and must not enter command logs, state hashes, save-game epochs, or multiplayer DTOs. `--plain` temporarily forces reduced motion and minimal decorative effects without overwriting saved preferences.

### Responsive layout

Add a TUI-only layout tier:

```python
class LayoutTier(Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    WIDE = "wide"
```

Tier calculation is centralized:

- `COMPACT`: width 80–99 or height 24–29.
- `STANDARD`: width 100–119 and height at least 30.
- `WIDE`: width at least 120 and height at least 36.
- Below 80×24: render a minimal unsupported-size notice while preserving Help and Quit.

Screens receive `compact`, `standard`, or `wide` CSS classes. A resize may change the structural layout only when the tier changes.

### Unified action description

Add one screen-action contract:

```python
@dataclass(frozen=True)
class ActionDescriptor:
    id: str
    title: str
    help: str
    key: str | None
    enabled: bool
    disabled_reason: str | None
    danger: Literal["none", "caution", "destructive"]
    callback: Callable[[], object]
```

The footer, `.` action menu, `?` help, `Ctrl+P` command palette, and mouse affordances must derive from these descriptors instead of maintaining separate action lists.

### Shared ship/starbase component workbench

Build one reusable `ComponentWorkbench` composite widget. Both the ship Engine Room screen and the starbase Station tab must instantiate this exact widget; neither screen may keep a private subsystem-panel renderer.

The widget accepts the already-shared `Subsystem` and `Slot` DTO shapes plus a presentation profile:

```python
@dataclass(frozen=True)
class SlotGlyphs:
    filled: str
    selected: str
    knocked: str
    empty: str
    keystone: str

@dataclass(frozen=True)
class ComponentWorkbenchProfile:
    context: Literal["ship", "starbase"]
    workbench_title: str
    loose_components_title: str
    subsystem_labels: Mapping[str, str]
    subsystem_art: Mapping[str, tuple[str, ...]]
    subsystem_colors: Mapping[str, str]
    slot_glyphs: SlotGlyphs
    panel_border_token: str
    instructions: str

@dataclass(frozen=True)
class WorkbenchCapabilities:
    install: bool
    swap: bool
    field_patch: bool
    full_repair: bool
    salvage: bool

@dataclass(frozen=True)
class WorkbenchSelection:
    loose_components: tuple[str, ...]
    slots: tuple[tuple[str, int], ...]
```

`ComponentWorkbench` owns:

- Subsystem layout.
- Slot rendering.
- Loose-component rendering.
- Keyboard and mouse selection.
- Selection preservation across a refresh.
- Responsive one-, two-, or three-column layout.
- Step/instruction text.
- State legend.
- Action-request messages containing canonical subsystem names and slot indexes.

It must not import `GameService`, issue core commands, or decide gameplay legality. The containing screen translates a workbench action request into existing ship or starbase commands.

Use these profiles:

| Context | System key | Display name | Art direction | Color |
|---|---|---|---|---|
| Ship | `SPINDRIVE` | Spindrive | Existing field-drive icon | Cyan |
| Ship | `THRUSTERS` | Thrusters | Existing rocket/plume icon | Amber |
| Ship | `SCREENS` | Screens | Existing faceted shield | Blue |
| Ship | `MAIN GUN` | Main Gun | Existing spinal barrel | Red |
| Starbase | `FUSION REACTOR` | Fusion Core | New ring/core installation | Magenta |
| Starbase | `SCREENS` | Defense Grid | New multi-emitter array | Bright cyan |
| Starbase | `MAIN GUN` | Orbital Battery | New turret/battery silhouette | Yellow |

Starbases use square installation glyphs and warning-colored industrial borders; ships retain rounded panels and the existing component markers. State must still be understandable in monochrome through glyph and text differences.

## Work Packages

Each work package should be implemented as a small, independently reviewable commit. A package is complete only when its tests and affected screenshots pass.

### M1 — Specification and framework baseline

#### WP-UI01 — Record the responsive UI contract

Depends on: none.

Implementation:

- Update DESIGN §11 with the three layout tiers, accessibility rules, action-discovery model, and settings behavior.
- Update DESIGN §§4.1 and 4.2 to state that ships and starbases share one component-workbench widget but use different presentation profiles.
- Replace the open narrow-terminal questions in the UI mockups with the chosen 80×24 behavior.
- Add wireframes for compact, standard, and wide versions of the sector view, Computer, contact, combat, and component workbench.
- Update the inspiration document with the current Textual, Harlequin, CLI-guideline, and accessibility research.

Verification:

- No document describes the ship and base component renderers as separate implementations.
- All player screens are assigned a responsive screen archetype.
- The keymap contract remains internally consistent.

Commit: `ui: WP-UI01 responsive UX specification`

#### WP-UI02 — Upgrade Textual and stabilize the capture rail

Depends on: WP-UI01.

Implementation:

- Refresh the lockfile to Textual 8.2.8.
- Add `pytest-textual-snapshot` as a development dependency and document it in DESIGN §15.
- Keep the existing deterministic animation disabling and screenshot settling.
- Extend the capture utility so callers can select terminal size, theme, and art-detail mode without duplicating setup.
- Add a smoke test opening the main menu, game, Computer, contact, component workbench, and lobby under Textual 8.2.8.

Verification:

- Existing tests pass before visual refactoring begins.
- Screenshot generation remains byte-stable across two consecutive runs.
- Local and browser-serving entry points still start.

Commit: `ui: WP-UI02 Textual 8.2.8 and snapshot baseline`

### M2 — Design system and application shell

#### WP-UI03 — Introduce semantic themes

Depends on: WP-UI02.

Implementation:

- Add `edge-ansi`, `edge-high-contrast`, and `edge-monochrome` themes.
- Define semantic variables for text, muted text, disabled text, panels, focus, selection, ownership, rarity, success, warning, danger, and interactive hover.
- Replace raw `cyan`, `red`, `green`, `yellow`, and `dim` markup in shared widgets first.
- Add a small helper that returns Rich `Text` with semantic styles; do not scatter theme names through screen logic.
- Make focus, hover, selection, disabled, and destructive states visually distinct.

Verification:

- Normal text meets 4.5:1 contrast and focus/control indicators meet 3:1 against every supported background.
- High-contrast and monochrome themes retain every state distinction.
- Automated tests fail when a semantic token drops below its required contrast.

Commit: `ui: WP-UI03 semantic ANSI themes`

#### WP-UI04 — Persist presentation settings

Depends on: WP-UI03.

Implementation:

- Add `UISettings` and a small JSON loader/saver beside the existing save-directory utilities.
- Recover from a missing, corrupt, or newer settings file by using defaults and showing one non-fatal warning.
- Replace the current theme-cycling option with the three supported themes.
- Add reduced motion, art detail, density, onboarding, and disabled-reply options.
- Apply settings before the first screen is mounted.
- Keep `--plain` as a temporary runtime override.

Verification:

- Settings survive application restart.
- Settings do not change universe state hashes or command logs.
- A corrupt preferences file does not prevent startup.
- `--plain` does not modify the stored settings file.

Commit: `ui: WP-UI04 persistent presentation settings`

#### WP-UI05 — Add layout tiers and shared screen chrome

Depends on: WP-UI04.

Implementation:

- Centralize `LayoutTier` calculation on the app.
- Toggle tier CSS classes on mounted screens when the terminal crosses a breakpoint.
- Add shared title bar, scroll-safe body, context strip, empty state, action row, and compact footer components.
- Convert one low-risk screen, such as Options, to prove all shared components.
- Preserve focus before a tier change and restore it by widget ID afterward.
- Provide a reusable unsupported-size screen for dimensions below 80×24.

Verification:

- Resize tests cross all three tiers without losing focus.
- At 80×24, the converted screen has no clipped controls or horizontal scrolling.
- At below 80×24, Help and Quit remain operable.

Commit: `ui: WP-UI05 responsive shell and chrome`

#### WP-UI06 — Unify actions, footer, help, and command palette

Depends on: WP-UI05.

Implementation:

- Add `ActionDescriptor`.
- Adapt existing Textual `Binding` declarations into descriptors initially, then allow dynamic descriptors for active tabs and selected objects.
- Rebuild the `.` action menu from descriptors, including disabled actions with explanations.
- Feed enabled descriptors into Textual’s screen-aware `Ctrl+P` system commands.
- Rebuild `?` help from the same source.
- Show only primary actions in the footer; keep the complete list in `.` and `Ctrl+P`.
- Group related footer bindings and use compact key labels.
- Validate global key reservations and per-screen collisions.

Verification:

- A test compares the IDs exposed through footer, action menu, help, and palette.
- Every enabled descriptor invokes the same callback regardless of entry point.
- Disabled descriptors cannot execute and always expose a reason.
- Destructive descriptors always reach the shared deny-focused confirmation screen.

Commit: `ui: WP-UI06 unified action discovery`

#### WP-UI07 — Standardize feedback, focus, and forms

Depends on: WP-UI05, WP-UI06.

Implementation:

- Define success, informational, warning, and error notification helpers with standard titles and timeouts.
- Add inline field validation for lobby, corporation, amount, beacon, note, and travel forms.
- Prevent duplicate submits while an action is running.
- Standardize modal widths by tier and make modal bodies scroll at 80×24.
- Restore the initiating widget’s focus when a modal closes.
- Ensure Tab order follows visual reading order and arrow keys stay within tables, lists, tabs, maps, and the workbench.

Verification:

- Pilot tests complete every form with keyboard only.
- Recoverable errors preserve entered values.
- Focus is always visible and returns to the invoking control.
- No modal exceeds an 80×24 screen.

Commit: `ui: WP-UI07 feedback focus and forms`

### M3 — Shared component mechanism

#### WP-UI08 — Build the presentation-neutral ComponentWorkbench

Depends on: WP-UI03, WP-UI05, WP-UI07.

Implementation:

- Extract the current `_SubsystemPanel` and loose-component picker behavior into one reusable `ComponentWorkbench`.
- Keep the existing shared `Subsystem` and `Slot` DTOs unchanged to avoid wire-protocol changes.
- Add `ComponentWorkbenchProfile`, `WorkbenchCapabilities`, and `WorkbenchSelection`.
- Key profile maps by the existing canonical DTO names; presentation aliases must never be used to construct core commands.
- Render:
  - Compact: one subsystem per row, small art or no art according to settings.
  - Standard: two-column grid.
  - Wide: ship uses two columns; starbase may use three columns.
- Support mouse click, Tab, arrow navigation, Space to toggle selection, and Enter to request the currently advertised action.
- Preserve selection when the host provides a refreshed DTO, removing only selections whose slots or inventory entries no longer exist.
- Post typed action messages; do not call services or reducers.

Verification:

- Unit-test filled, selected, knocked, empty, and keystone slots.
- Test responsive layout and art-detail modes.
- Test multiple loose components and multiple slot selections.
- Test selection reconciliation after a DTO refresh.
- Test that the module has no `GameService` or core-command imports.

Commit: `ui: WP-UI08 shared component workbench`

#### WP-UI09 — Migrate the ship Engine Room

Depends on: WP-UI08.

Implementation:

- Replace `_SubsystemPanel` and `_ComponentsPickerPanel` with `ComponentWorkbench`.
- Add the ship presentation profile with existing ship names, colors, and art.
- Preserve existing commands:
  - Field patch.
  - Dock/base repair.
  - Install into an empty legal slot.
  - Swap one carried component with one installed non-keystone component.
  - Cannibalize selected non-keystone components.
- Move reverse canonical-name-to-enum mapping into one TUI helper used by both component hosts.
- Replace pop-and-push reopening with an in-place DTO refresh so focus and selection can be retained.
- Show a before/after derived-stat preview when exactly one legal swap or install target is selected; the preview is presentation-only and must use already-projected values or an existing pure helper.

Verification:

- Existing engine-room command tests still pass.
- Keyboard and mouse perform the same selections.
- Keystone components cannot be illegally cannibalized.
- Ship snapshots show existing names, ship colors, and ship art.
- No legacy private subsystem renderer remains.

Commit: `ui: WP-UI09 ship engine room on shared workbench`

#### WP-UI10 — Migrate the starbase Station tab

Depends on: WP-UI09.

Implementation:

- Replace the Station tab’s `Static` subsystem cards with the same `ComponentWorkbench`.
- Add the starbase profile:
  - `FUSION REACTOR` → “Fusion Core”.
  - `SCREENS` → “Defense Grid”.
  - `MAIN GUN` → “Orbital Battery”.
  - Industrial square slot glyphs.
  - Magenta/cyan/yellow art.
  - Warning-colored installation borders.
  - New starbase-specific art assets.
- Supply the ship’s carried component list to the workbench through the existing engine-room projection.
- Change Repair and Salvage from “automatically use the first eligible item” to explicit workbench selection:
  - Repair requires one carried component and one legal empty base slot.
  - Salvage requires one installed, non-protected base component.
  - Keystone-first remains a rule enforced by the reducer; the UI marks the reactor keystone and explains why it matters.
- Keep Claim and Assault outside the workbench as base-level actions.
- Refresh the Station tab in place after repair or salvage.
- Keep all standing-based tab gating unchanged.

Verification:

- A structural test asserts that both Engine Room and Station contain `ComponentWorkbench`.
- A structural test asserts that no second slot-rendering implementation exists in BaseScreen.
- Repair and salvage operate by keyboard and mouse.
- Ship and base snapshots visibly differ in names, art, colors, glyphs, and copy.
- Monochrome snapshots still distinguish ship versus starbase through titles, glyphs, and art.
- Existing starbase rule and service tests pass.

Commit: `ui: WP-UI10 starbase station on shared workbench`

### M4 — Main exploration and commerce loop

#### WP-UI11 — Redesign the main menu and first-run guidance

Depends on: WP-UI04–WP-UI07.

Implementation:

- Improve title hierarchy while retaining the starfield and ANSI logo.
- Show Continue as the primary action when a save exists and New Game otherwise.
- Add clear save metadata when available.
- Add a dismissible “Captain’s objectives” overlay derived from existing views and local UI progress: dock, trade, inspect/upgrade, scan, discover.
- Make objectives reopenable from Help.
- Disable animation under reduced-motion/plain modes.

Verification:

- New and returning menu states have deterministic snapshots.
- The objective overlay never changes core state.
- A new player can identify the first gameplay action without opening external documentation.

Commit: `ui: WP-UI11 menu and onboarding`

#### WP-UI12 — Make the sector view responsive

Depends on: WP-UI05–WP-UI07.

Implementation:

- Keep the sector scene and nav rose as the main visual anchor.
- Compact mode:
  - Hide or minimize decorative sprites first.
  - Hide the permanent sidebar.
  - Add `I` to open a ship-status drawer.
  - Retain location, interactive objects, navigation, turns, hazards, and latest event.
- Standard mode retains the current sidebar with clearer groups.
- Wide mode adds objective, presence, and anomaly detail.
- Give every clickable scene object a focused/list equivalent so keyboard users never need coordinate-based navigation.
- Replace raw color-only ownership and danger cues with symbols and labels.

Verification:

- Every sector action remains reachable at 80×24.
- Sidebar visibility changes do not remove access to ship status.
- Scene hotspots and keyboard entries invoke the same actions.
- Resize preserves selected warp.

Commit: `ui: WP-UI12 responsive sector view`

#### WP-UI13 — Clarify navigation and travel

Depends on: WP-UI12.

Implementation:

- Strengthen selected-warp focus.
- Show sector, distance band, explored state, one-way state, hazard, turn cost, Core bearing, and backtrack status through text or symbols.
- Redesign route confirmation to summarize destination, hop count, turns, known hazards, avoid-list effects, and interruption warnings.
- Keep Enter/click as one-hop warp and existing route commands unchanged.

Verification:

- One-way and dangerous routes remain understandable in monochrome.
- Keyboard and mouse select the same nav target.
- Hazard confirmation remains mandatory.
- Existing map/navstrip tests pass.

Commit: `ui: WP-UI13 navigation clarity`

#### WP-UI14 — Standardize trade presentation

Depends on: WP-UI03–WP-UI07.

Implementation:

- Keep one `TradePanel` at ports, StarDock, and bases.
- Align numeric columns and use explicit “Port buys” and “Port sells” wording.
- Show selected commodity, stock/capacity, unit price, estimated transaction total, player quantity, hold impact, and purse limitation.
- Make Trade, Haggle, and Deliver visible context actions.
- Preserve table cursor during market updates.
- Collapse low-priority columns into a selected-row detail block at 80×24.

Verification:

- Port, StarDock, and base trade views render the same component.
- Goods and price direction cannot be confused from labels.
- Existing trade/haggle behavior and conservation tests pass.

Commit: `ui: WP-UI14 unified commerce presentation`

### M5 — Progression, encounter, and social screens

#### WP-UI15 — Consolidate StarDock and base service hubs

Depends on: WP-UI10, WP-UI14.

Implementation:

- Apply one service-hub pattern to StarDock and starbases.
- Group commerce, ship, devices, finance, and social services consistently.
- Use a scrollable selector in compact mode instead of overflowing tabs.
- Show unavailable services with standing or prerequisite explanations.
- Preserve all reducer-side service-point checks.

Verification:

- All services are discoverable at 80×24.
- Changing tabs/subviews preserves selected rows.
- No UI-advertised service is rejected because the UI used different eligibility logic.

Commit: `ui: WP-UI15 service hub consistency`

#### WP-UI16 — Redesign planet and surface workflows

Depends on: WP-UI05–WP-UI07.

Implementation:

- Separate planet identity, ownership, habitability, stores, colony, citadel, orbital base, and cargo transfer into clear sections.
- Collapse secondary colony/citadel details behind focused panels at 80×24.
- Give the surface site list priority over terrain art in compact mode.
- Add selected-site detail with rarity, survey status, required action, and reward visibility.
- Retain art in standard/wide modes.

Verification:

- Colonize, transfer, Genesis, citadel, base entry, descend, survey, and collect remain keyboard and mouse accessible.
- No economic or ownership rule changes.
- Planet and surface tests pass at all three layout tiers.

Commit: `ui: WP-UI16 planet and surface UX`

#### WP-UI17 — Redesign alien contact

Depends on: WP-UI03–WP-UI07.

Implementation:

- Use portrait/dialogue/reply regions responsively.
- Prioritize current speech and numbered replies.
- Make standing readable as a named band, numeric/meter cue, and relationship text.
- Show disabled replies with reasons when the setting is enabled.
- Preserve dialogue scrolling, authored reply order, recency, and session facts.
- Keep dossier, offer, alliance, and farewell actions within the unified action system.

Verification:

- Dialogue selection and recency tests remain unchanged.
- Every reply is reachable by number, arrows/Enter, and mouse.
- Missing portraits do not leave half the screen blank.
- Compact contact remains usable at 80×24.

Commit: `ui: WP-UI17 responsive alien contact`

#### WP-UI18 — Redesign encounter and combat

Depends on: WP-UI03–WP-UI07.

Implementation:

- Separate enemy pack, player status, current round result, tactical advice, and actions.
- Show firing arc, flee chance/floor, ammo, repair kits, shields, hull, and knocked-out components with labels and symbols.
- Keep the last round result visible until the next action.
- Distinguish Fight, Missile, Flee, and Patch without relying on color.
- Preserve combat command semantics and reducer-driven odds.

Verification:

- Combat is playable at 80×24 using keyboard only.
- Flee floor and firing-arc information remain visible.
- Existing combat, damage, salvage, and replay tests pass.

Commit: `ui: WP-UI18 combat dashboard`

#### WP-UI19 — Apply the system to territory, corporations, lobby, and minor screens

Depends on: WP-UI05–WP-UI07.

Implementation:

- Convert Territory cards to responsive one-, two-, or three-column layouts.
- Give corporation empty, member, and CEO states clear primary actions.
- Add persistent lobby field labels, connection progress, inline authentication errors, and retry without data loss.
- Apply shared forms and modals to amount, beacon, note, route, confirmation, and picker screens.
- Apply shared empty states to tavern, market, contracts, corporations, and notices.

Verification:

- Every form works with keyboard and mouse.
- Recoverable remote errors preserve entered values.
- All minor screens fit at 80×24.
- Existing territory, corporation, account, and remote-client tests pass.

Commit: `ui: WP-UI19 remaining workflow consistency`

### M6 — Computer and information architecture

#### WP-UI20 — Restructure the Computer

Depends on: WP-UI05–WP-UI07.

Implementation:

Replace the thirteen-tab strip with five categories:

- Navigation: Map, Route.
- Commerce: Ports, Trade, Market.
- Exploration: Planets, Codex, Leads.
- Relations: Contracts, Alliances, Dossier.
- Records: Log, Notes.

Use a category selector plus a subview selector. Each category remembers its last subview. Direct `M`, `G`, plotted routes, codex links, and contract links must open the correct subview.

Compact mode uses a vertical or popup selector; standard/wide modes may use category tabs with a secondary subview row.

Verification:

- No tab label is clipped at 80×24.
- Every old tab maps to exactly one new subview.
- Direct hotkeys open the expected subview.
- Existing last-tab behavior becomes last-category plus last-subview behavior.

Commit: `ui: WP-UI20 Computer information architecture`

#### WP-UI21 — Improve Computer tables and detail views

Depends on: WP-UI20.

Implementation:

- Standardize column alignment, cursor style, zebra stripes, headers, and empty states.
- Add sorting where the underlying data already provides meaningful sortable values.
- Add `/` filtering without changing service queries.
- Hide low-priority columns in compact mode and show them in a selected-row detail overlay.
- Use a persistent side detail pane in wide mode.
- Preserve cursor by stable row key during refresh.

Verification:

- Every Computer subview works at all three tiers.
- Filtering never alters underlying DTOs.
- Market refreshes preserve the highlighted logical row.
- Plot, engage, note, avoid, contract, alliance, and seizure actions still target the correct row.

Commit: `ui: WP-UI21 Computer tables and details`

### M7 — Regression, accessibility, and playtesting

#### WP-UI22 — Add the responsive visual regression matrix

Depends on: WP-UI11–WP-UI21.

Implementation:

- Capture every player-reachable screen at 80×24 and 100×34.
- Capture representative dense screens at 120×40.
- Capture the sector view, workbench, contact, combat, and Computer in high-contrast and monochrome themes.
- Add automated geometry checks ensuring focusable widgets are within the visible screen or a keyboard-scrollable container.
- Add checks for reserved-key collisions, missing action descriptors, and destructive actions without confirmation.

Verification:

- Snapshot suite passes twice consecutively.
- No player-reachable control is clipped or unreachable.
- Ship and starbase workbench snapshots prove shared structure with distinct presentation.

Commit: `ui: WP-UI22 responsive snapshot coverage`

#### WP-UI23 — Conduct hands-on UX and accessibility passes

Depends on: WP-UI22.

Implementation:

Run these scripted playtests:

1. New player: start, dock, trade, inspect the engine room, scan, and begin exploration.
2. Veteran: dock, trade/haggle, undock, and warp using direct keys only.
3. Keyboard-only: complete the core loop without mouse input.
4. Mouse-only: complete the same loop without direct action keys.
5. Compact: complete the core loop at 80×24.
6. Hosted: log in, join, travel, trade, and recover from a simulated network error.
7. Component workbench: install/swap/repair on the ship, then repair/salvage a starbase using the same interaction model.
8. Monochrome: identify danger, selection, ownership, damage, and disabled actions without color.

Record findings in playtest notes and fix all severity-one issues: blocked progress, hidden required action, lost focus, clipped control, misleading transaction direction, missing confirmation, or inaccessible state.

Acceptance criteria:

- A new player reaches their first trade without external documentation within five minutes.
- A veteran’s dock/trade/warp sequence requires no additional mandatory screen.
- Resizing preserves active screen, category/subview, focused action, selected row, form input, conversation position, workbench selection, and plotted route.
- No core, replay, economy, combat, dialogue, or multiplayer regression remains.
- DESIGN, UI mockups, UI style guide, screenshots, and implemented behavior agree.

Commit: `ui: WP-UI23 UX acceptance and documentation closeout`

## Global Implementation Rules

- Preserve downward-only dependencies. Shared UI widgets may consume DTOs but never service or core state.
- Do not alter `references/`.
- Prefer in-place refresh over popping and reconstructing screens.
- Do not duplicate slot, action, form, empty-state, title-bar, or responsive-tier logic.
- Decorative art is the first content removed under space pressure.
- Every key action must have a mouse/selectable affordance.
- Every disabled action must explain why it is disabled.
- Every destructive action must use the shared deny-focused confirmation.
- Every UI state conveyed by color must also have text, a glyph, or both.
- Update normative documentation and screenshots in the same work package that changes behavior.
- Run targeted tests after each package and the full `pixi run check` before completing each milestone.
