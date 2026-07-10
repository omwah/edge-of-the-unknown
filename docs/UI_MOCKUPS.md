# Edge of the Unknown — TUI Mockups

Companion to `DESIGN.md` §11 (Textual UI). These are **wireframes**, not
final art: their job is to lock screen layout, information architecture, and
the mapping of every region to a Textual widget *before* code exists. The
medium is deliberately the medium the game ships in — monospace text.

When implementation reality forces a layout change, update this doc in the
same change (same rule as DESIGN.md). Layout and data placement are normative;
pixel-exact spacing is not.

## How to read these

- Each screen has a **wireframe** (one fenced block) followed by **annotations**:
  region → widget, key bindings, data source, and the DESIGN.md section it realizes.
- Tokens in `[ ]` are clickable affordances **and** key bindings (§11 grammar:
  every keystroke action also has a mouse affordance).
- **This document is ASCII-only** (plus the block-bar glyphs `█`/`░`), so the
  borders and columns stay aligned in any monospace markdown renderer — wider or
  ambiguous-width unicode breaks that alignment. This constraint binds *the doc
  only*: wherever an annotation says **"ASCII art"** (scene sprites, planet art,
  subsystem icons, …), the **Textual UI is free to use the richer unicode glyph
  set** — the `tw2002` CP437/box-drawing set, block shapes, arrows, etc. — and CSS
  fractional widths, not these fixed ASCII columns. When a TUI asset uses unicode,
  this doc shows its ASCII transliteration instead (e.g. the §8 subsystem icons).

### Glyph legend (wireframes)

```
  P  port             @  planet            #  starbase (orbital)
  >  ship (NPC)       *  discovery / find  !  beacon
  f  fighters         x  mine              ~  hazard (black hole / nebula)
  bars:  █ filled / stocked      ░ empty / depleted
  slots: [+] healthy   [!] knocked-out     [ ] empty slot
  < > ^ v / \  warp direction      ?  unexplored / unknown stock
```

### Theme

The `tw2002` theme (§11): cyan/yellow/magenta on black, CP437 box drawing,
optional starfield on the title screen. A `--plain` flag drops animation/CRT
flourishes.

---

## Screen map

```
MainMenu -> Game -+- PortScreen
                  +- PlanetScreen -> SurfaceScreen
                  +- StarDockScreen   (tabs: Commodities . Shipyard . Hardware . Bank . Tavern)
                  +- AlienContactScreen
                  +- EncounterScreen
                  +- EngineRoomScreen
                  +- ComputerScreen   (tabs: Map . Ports . Trade . Route . Codex
                  |                           . Dossier . Notes)
                  +- MapScreen
                  +- MessagesScreen
```

Phase 1 builds: **MainMenu, Game, PortScreen, StarDockScreen, ComputerScreen,
MapScreen, MessagesScreen** (shell). The rest are Phase 2-3 (marked per screen).

---

## 0. MainMenu / Title  *(Phase 1)*

```
┌─ EDGE OF THE UNKNOWN ────────────────────────────────────────────────┐
│                                                                      │
│       E D G E   O F   T H E   U N K N O W N                          │
│     trade . discover . navigate the alien frontier                   │
│                                                                      │
│        .  *      .       *        .   *    .                         │
│     *        starfield (animated unless --plain)    .                │
│        .         *      .       *        .                           │
│                                                                      │
│           [N]  New game                                              │
│           [C]  Continue   (last: "Halaf Run", day 4)                 │
│           [L]  Load game ...                                         │
│           [O]  Options                                               │
│           [Q]  Quit                                                  │
│                                                                      │
│     v0.1 . seed-reproducible . a TradeWars 2002 descendant           │
└──────────────────────────────────────────────────────────────────────┘
```

- **Title/starfield**: `Static` + Textual animation (§11 aesthetics); suppressed
  under `--plain`.
- **Menu**: `ListView` / bound keys; `[C]` shown only if a save exists (reads
  `~/.edge/games/`, §12). `[N]` -> new-game config (seed/roster/universe size).
- DESIGN: §11, §12, §15.

---

## 1. Game  *(Phase 1)* — the primary screen

```
┌─ EDGE OF THE UNKNOWN ──────────────────────────────── turns 287/300 ─┐
│  .          [7] CORE SPACE (Core)        *  │ S.S. Wayfarer (Trailbl) │
│         ░▒▓ the lanes hum w/ traffic ▓▒░  . │ ----------------------- │
│       *    ! "Welcome to Sol"          .    │ Shields ████████░░ 82%  │
│   .      .-~~~-.       .    =[#####]=     . │ Warp    ███░░░░░░░  3    │
│       . .'~ .o. ~'.       . =[#o#o#]=   .   │ Combat  ████░░░░░░  4    │
│   .     : ~  .O.  ~ :  .  .    |||      .   │ Cloak   ░░░░░░░░░░ off   │
│        . '.~ .o. ~.'      .  (orbital)    . │ Sensors ██████░░░░ TierII│
│     Terra Nova terrestrial  Stardock-Cls0   │ subsystems: all nominal │
│   .       *        .  +        .      *   . │ ----------------------- │
│       ___              ___                  │ Holds 40/60             │
│      [===]=>          <=[===]            *  │  Fuel ████████░░░░ 20   │
│   .   Kestrel       Cabal Marauder (Hail)   │  Org  ████░░░░░░░░ 12   │
│      > Verdani escort (Hail)             .  │  Equ  ██░░░░░░░░░░  8   │
│            Discoveries               *      │ Latinum 14,250 slips    │
│      ✦ Crashed Ship — unlogged (Scan)    .  │ ----------------------- │
│                 1<   3/Sol  6>              │ Band 0 - Core           │
│   .             8?    (7)    12?         *  │  (1)-(7)  (8) (12)      │
├──────────────────────────────────────────────────────────────────────┤
│- arrive in Sector 7.   - Stardock detected.   - 287 turns left.      │
├──────────────────────────────────────────────────────────────────────┤
│ P Dock  S Survey  C Computer  E Engine  M Map  G Log  ^q Quit        │
└──────────────────────────────────────────────────────────────────────┘
```

- **Sector scene (the left 2/3)**: a single composited **`SectorScene`** Static —
  a procedural `edge.art` **starfield base** with the header, planet, port, ships,
  and discoveries stamped over it. It is one widget because a terminal cell holds a
  single glyph and Textual does **not** blend overlapping widgets/layers; the only
  way to show the starfield *behind* the sprites and text is to composite them in
  one grid. Sprites' negative-space cells are left transparent, so stars show
  through their gaps (each body floats in space); text lines clear the stars within
  their own extent so words stay legible, with stars in the margins. Planet / port /
  ship / unlogged-discovery **click hotspots** post the same `ClickableEntry.Picked`
  the keys do. All sprite sizes come from config `scene:` (`SceneArtConfig`).
  Top to bottom: a centred **header** (`[id] REGION (Band)` + flavor + beacon); a
  two-column **orbit band** — **planet** left (name beneath), **port** right (name
  beneath, sprite **vertically centred** against the taller planet); a blank
  **margin**; a **ships row** (no heading); the **Discoveries** row; then the
  **`WarpGrid`** beneath. A missing planet/port shows a muted placeholder so the two
  columns stay put as you warp. The planet's width is always **2×its height** so the
  disc reads round on the ~2:1 cell grid (`scene.planet`, distinct from
  `scene.planet_detail` used by the larger PlanetScreen orbit view, §3).
- **Orbit / ship clicks** open the same screen as the key: planet -> PlanetScreen
  (§3, `S`); a StarDock port -> StarDockScreen (§5) / a plain port -> PortScreen
  (§2), the **same target as `P`**; a hailable ship -> AlienContactScreen (§6) for a
  friendly-band ship or EncounterScreen (§7) for a hostile one.
- **Ships**: up to `scene.max_ships_shown` (default **2**) sprites side by side; when
  two show, the second may be flipped to **face the first** (deterministic per
  sector, `scene.ship_face_inward_chance`). Ships beyond the cap fall to a compact
  **clickable text list** so every contact stays individually hailable.
- **Warps**: the **`WarpGrid`** — a 3x3 grid with the **current sector pinned to the
  centre cell** (non-clickable `(7)`) and outbound warps in the eight cells around
  it (clickable, unexplored dimmed with `?`), **centred** below the scene so the
  current sector sits in the middle. TW2002 sectors warp to <= 6 others, so eight
  surrounding cells suffice.
- **Right 1/3 — status sidebar**: ship name/type; aspect readout with bars
  (shields/warp/combat/cloak/sensors) + a compact **subsystem-integrity line**
  (flags knocked-out components, §4.1); holds bar per commodity; Gun/missile/
  repair-kit counts; latinum; turns; current **distance band**; region mini-map.
  The mini-map is the current sector's neighbourhood, so the sectors drawn next to
  `(7)` are exactly the `WarpGrid`'s targets — both are projected from the one warp
  graph, so they cannot drift.
- **Bottom**: scrolling event ticker (`RichLog`) above a docked **status bar**
  (`Footer`) listing the active key bindings as a persistent reminder — there is
  no command-line input; actions are keystrokes and mouse clicks (§11 grammar).
- **Bindings** (§11): number keys = warp by sector; `P` dock port (§2),
  `S` survey planet (orbit view, §3), `C` computer (§9), `E` engine room (§8),
  `M` galactic map (§10), `G` messages & log (§11), `I` ship info, `^q` quit.
  Clicking a ship row hails it (AlienContact §6 / Encounter §7). Esc cancels a prompt.
- DESIGN: §11, §4 (aspects/holds), §4.1 (integrity line), §9 (turns).

---

## 2. PortScreen  *(Phase 1)* — trading + haggling

The trade UI is a reusable widget (`TradePanel`): the standalone `PortScreen`
below wraps it for a **plain commodities port**, and the StarDock embeds the same
widget as its **Commodities** tab (§5). So whether or not a port is a StarDock,
docking reaches an identical trade experience — only the container differs.

```
┌─ TRADEPORT . Sol Exchange . Class 4 (BBS) ──────────────── Sector 3 ─┐
│                                                                      │
│  Commodity    They    Stock        Price/u   You   Action            │
│  ------------------------------------------------------------        │
│  Fuel Ore     BUY     ████░░░░░ 41%    13 ^    20    [Sell]          │
│  Organics     SELL    ██░░░░░░░ 22%     6 v    12    [Buy ]          │
│  Equipment    BUY     █████░░░░ 58%    14 ^     8    [Sell]          │
│                                                                      │
│  +- Haggle: Sell Fuel Ore --------------------------------+          │
│  | Quote:  13/u  x  20 units  =  260 slips                |          │
│  | Your counter: [ 15 ]/u    fair ~ 13    ( likely        |          │
│  | Round 1 of 2   - "Hah, 14 and not a slip more."        |          │
│  | [A]ccept quote   [O]ffer counter   [Esc] walk away     |          │
│  +--------------------------------------------------------+          │
│                                                                      │
│  ^ port buys from you (you SELL)   v port sells to you (you BUY)     │
│  Latinum 14,250   -   [Q]uick-trade off   -   [Esc] leave dock       │
└──────────────────────────────────────────────────────────────────────┘
```

- **Commodity table**: `DataTable` — port mode (BUY/SELL), stock-ratio bar + %,
  live price (`^`/`v` vs base), player holdings, per-row action. Prices follow
  the §8 stock-ratio formula (negative feedback: selling in lowers the buy price).
- **Haggle panel**: modal mini-game (§8) — quote, counter `Input`, an acceptance
  hint (`( likely` / `o risky` / `x insulting`), round counter (2 rejections ->
  final price; >~30% off -> abort), port line from flavor text.
- **Quick-trade toggle** disables haggling (§8).
- DESIGN: §8 (pricing, haggling), §4 (port classes/commodities).

---

## 3. PlanetScreen  *(Phase 2)* — orbit view

```
┌─ ORBIT . Terra Nova . terrestrial, warm ────────────────── Sector 7 ─┐
│                                                                      │
│  Owner   Federation (Core world)        Citadel  Lv 2                │
│  Habitability  ██████████░░  high     Colonists  1,240,000           │
│  Yield profile   Fuel (low)   Organics (high)   Equip (med)          │
│                                                                      │
│  # Orbital starbase - OPERATIONAL  (defends for owner)               │
│      reactor [+]  screens [+]  gun [+]    [Inspect -> Engine room]   │
│                                                                      │
│  Stores      Ore 8,200   Org 31,400   Equ 5,100   Ftrs 900           │
│  Allocation  [Ore 20%][Org 60%][Equ 15%][Ftrs 5%]  (owner only)      │
│                                                                      │
│  Surface sites detected:  * 2   (1 hidden - sensors Tier II)         │
│                                                                      │
│  [D] Descend to surface    [T] Trade w/ colony    [C] Claim          │
│  [G] Genesis / terraform   [Esc] Break orbit                         │
└──────────────────────────────────────────────────────────────────────┘
```

- **Header**: `planet_type` (sets yield + habitability, §4.2).
- **Planet art**: a **larger, more detailed** orbit-view sprite for the
  `planet_type` (`sprites.PLANETS_LARGE` / `pick_planet_large`) is shown on the
  right, the orbit data on the left — a focal image, distinct from the small
  scene marker the sector view draws (`sprites.PLANETS`), keyed off the same
  planet type.
- **Ownership/production block**: owner (none / alliance / player), habitability
  bar, colonists, `yield_profile` over the trio, citadel level, stores;
  allocation sliders shown **only to the owner** (§8 production).
- **Orbital starbase row**: status (operational / **derelict** = can't power or
  defend, §4.2); `[Inspect]` opens the engine-room view (§8 below) for repair/
  cannibalize/claim.
- **Actions**: `[D]` -> SurfaceScreen (§4); `[C]` claim if unowned & habitable
  (Core worlds off-limits); `[T]` colony trade.
- DESIGN: §4.2 (types/ownership/starbases), §8 (production), §7 (sites).

---

## 4. SurfaceScreen  *(Phase 2)* — descent & site exploration

```
┌─ SURFACE . Terra Nova ─────────────────────────── descent fuel: n/a ─┐
│                                                                      │
│  +--------------------------------------+  Site: Ruined Spire        │
│  | . ^    *?       ^^                   |  rarity  *** Rare          │
│  |   ^^^  [1]     .      *              |  status  unexplored        │
│  | ~~~~~   ^     [2]    ^^^             |                            │
│  |   .  crashed-ship    ~~~~            |  Payload (on explore)      │
│  |     ^^     .       .                 |   - ancient_tech ?         │
│  +--------------------------------------+   - lore fragment          │
│                                                                      │
│  Sites    [1] * Ruined Spire    Rare      unexplored                 │
│           [2] * Crashed Ship    Uncommon  explored -> ancient        │
│           [?] hidden - needs a sensor sweep                          │
│                                                                      │
│  [E] Explore selected   [S] Sensor sweep   [L] Log to codex          │
│  [Esc] Ascend to orbit                                               │
└──────────────────────────────────────────────────────────────────────┘
```

- **Reached** from PlanetScreen's `[D]` Descend (§3); `[Esc]` ascends to orbit.
- **Terrain panel**: simple top-down `Static` map; site markers `[n]`, hidden
  sites shown as `*?` only after a successful sensor sweep.
- **Site detail**: the highlighted site's kind, rarity tier, status, and
  (post-explore) payload — tech item / latinum / lore fragment (§7 Discovery);
  driven by `DataTable` row highlighting.
- **Site list**: `DataTable`/`ListView`; `[S]` sensor sweep reveals hidden finds
  (sensor-rating check, §7/§10 detection); `[L]` logs to the codex.
- DESIGN: §7 (discovery kinds/rarity/hidden), §4.2 (surface_sites).

---

## 5. StarDockScreen  *(Phase 1 shell; tabs fill in Phase 2)*

```
┌─ STARDOCK . Sol ─────────────────────────────────────────────────────┐
│ [ Commodities ][ Shipyard ][ Hardware ][ Bank ][ Tavern ]            │
├──────────────────────────────────────────────────────────────────────┤
│  HARDWARE EMPORIUM                          Latinum 14,250 slips     │
│                                                                      │
│  Components (engine-room parts)     Tier   Price     Action          │
│  ----------------------------------------------------------          │
│   accelerator                       I      2,000     [Install]       │
│   converter                         I      2,000     [Install]       │
│   turbine                           II     8,000*    [Barter ]       │
│   navigator (keystone)              I      2,000     [Install]       │
│     * Tier II = latinum + artifact barter                            │
│                                                                      │
│  Consumables    Repair-kit x1    200     [Buy]                       │
│                 Homing missile   ---     [Buy]                       │
│                 Genesis torpedo  ---     [Buy]                       │
│                                                                      │
│  [R] Repair ship (-> Engine room)   [E] Engine room   [Esc] Undock   │
└──────────────────────────────────────────────────────────────────────┘
```

- **Tabs**: `TabbedContent` — **Commodities** (the default: the §2 `TradePanel`,
  so a StarDock trades through a tab rather than a separate screen), **Shipyard**
  (buy/sell hulls, §4), **Hardware** (components + consumables, the upgrade sink,
  §8), **Bank** (deposit/withdraw, interest, §8), **Tavern** (rumors/contracts,
  Phase 5).
- **Hardware tab** (shown): component list with tech tier + price; Tier II marks
  barter; Tier III is discovery/barter only and won't appear for straight cash
  (§8 constants). `[Install]` opens a slot picker in the Engine room (§8 below).
- **Repair**: full restoration / swaps happen here or at a friendly alien base
  (§4.1).
- DESIGN: §4 (hulls), §4.1 (components/repair), §8 (economy constants).

---

## 6. AlienContactScreen  *(Phase 2)* — dialogue + derived verb menu

```
┌─ CONTACT . Threllian Envoy ──────────────── disposition ████░ amity ─┐
│  standing: friendly (base .72 +.06 you)   alliance: Concord          │
├──────────────────────────────────────────────────────────────────────┤
│  +- they speak -----------------------------------------------+      │
│  | "Trader. Your hull still carries Sol's dust -              |      │
│  |  welcome it. We have drives that would shame               |      │
│  |  your little spindrive."                                   |      │
│  +------------------------------------------------------------+      │
│                                                                      │
│  Say / Do                     +- Dossier (told to you) --+           │
│   [1] Browse tech offers      | Kessrin  hostile-lean    |           │
│   [2] Barter an artifact      |   "raiders; shoot 1st"   |           │
│   [3] Ask about the region    | Federation ally of Core  |           │
│   [4] Propose treaty (cond.)  | Grudges: none vs you     |           │
│   [5] Trade goods             | Last tech: Tier-II       |           │
│   [6] Leave                   |   turbine, screens       |           │
│  (menu derived from params)   +--------------------------+           │
│                                                                      │
│  > _                                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

- **Disposition header**: effective disposition bar (base + per-player offset),
  standing band, alliance (§6).
- **Dialogue panel**: lines from the species' `dialogue_pack` keyed to standing/
  treaty/grudge/mechanic stage, with variant pools + recency ring so repeats
  rephrase (§6.7). Persona-voiced.
- **Verb menu**: **derived** from species params (`trade_posture`, `treaty_mode`,
  `befriend_price`, `signature_mechanic`) — not authored per species (§6.7).
  Greyed verbs show *why* (e.g. treaty `conditional`).
- **Dossier panel**: contact narrates other species (`dossier_other`),
  dispositions, alliances, grudges, last-seen tech (§11 dossier).
- DESIGN: §6.1-6.7 (params, mechanics, dialogue), §8 (barter equivalence).

---

## 7. EncounterScreen  *(Phase 3)* — greeting or fight/flee

```
┌─ ENCOUNTER . Kessrin Raider pack (x3) ──────────── they SHOOT FIRST ─┐
│  disposition █░░░░ hostile     detection: they spotted you           │
├──────────────────────────────────────────────────────────────────────┤
│  "Sol-meat. Your drive-glow led us right to you."                    │
│                                                                      │
│   THEM                            YOU  S.S. Wayfarer                 │
│    > Raider  hull ███████░░░ 70%     Shields  ███░░░░░ 38%           │
│    > Raider  hull ██████████ 99%     Hull     ██████░░ 74%           │
│    > Skiff   hull ████░░░░░░ 40%     Combat spd 4 (-2 intcpt)        │
│    arc: ahead/spinal -> strafe it  [!] thrusters: 1 burner out       │
│                                                                      │
│   Round 3      flee chance  31%  (floor 10%)                         │
│   --------------------------------------------------------           │
│   [F] Fire Main Gun [+]    [M] Missile x3 (ignores arc)              │
│   [E] Evade / strafe       [R] Flee     [K] Field-patch kit x2       │
└──────────────────────────────────────────────────────────────────────┘
```

- **Disposition header**: effective disposition, opener (greeting vs violence),
  detection result (cloak/sensors vs interception; undetected -> free slip, §10).
- **Combatant panels**: enemy group per `pack_behavior`/`escort` with per-ship
  hull + **firing arc** hint (strafe a spinal gun); player shields/hull/combat
  speed + **knocked-out component** flags (§4.1).
- **Round controls**: fight (Main Gun / finite homing missiles), evade, flee
  (chance shown, **clamped >= floor**, §10), field-patch a component (§4.1).
  Taunt/surrender/flee-scorn lines from the dialogue pack (§6.7).
- Peaceful opener reuses the §6 contact panel instead of combat controls.
- DESIGN: §10 (encounter/combat/flee floor), §4.1 (damage/repair), §6.7.

---

## 8. EngineRoomScreen  *(Phase 2)* — subsystems & components

```
┌─ ENGINE ROOM . S.S. Wayfarer ───────────── efficiency bonus: +2 all ─┐
│                                                                      │
│  SPINDRIVE -> warp 3            SCREENS -> shields 82%               │
│   [+] navigator (keystone)      [+] secondary (keystone)             │
│   [+] turbine  [+] accelerator  [+] accelerator [ ]____ [ ]____      │
│   [ ]____      [ ]____          (forward / rear deflection)          │
│                                                                      │
│  THRUSTERS -> combat spd 4      MAIN GUN -> dmg 18 . rate 2          │
│   [+] burner   [!] burner       [+] accelerator [+] linkage          │
│   [ ]____      [ ]____          [ ]____ [ ]____ [ ]____              │
│                                                                      │
│  [+] healthy    [!] knocked-out    [ ] empty slot                    │
│  ----------------------------------------------------------          │
│  Repair-kits x2   On hand: converter x1, turbine x1                  │
│  [P] Field-patch [!]   [I] Install in slot   [X] Cannibalize         │
│  [U] Upgrade (StarDock/base only)            [Esc] Back              │
└──────────────────────────────────────────────────────────────────────┘
```

Subsystem icons (ASCII transliteration for this doc; the TUI renders the
box-drawing/block unicode forms in `sprites.SUBSYSTEMS`):

```
SPINDRIVE   THRUSTERS   SCREENS     MAIN GUN
 >*<          /\          /\          ^
 /#\          ||         /  \        /#\
 |#|         /##\       |    |       |#|
 |#|         \vv/        \  /        |#|
 \#/          vv          \/         |#|
 >v<                                 \#/
```

- **Four subsystem panels** (`spindrive`/`thrusters`/`screens`/`main_gun`), each
  a slot grid on the left — keystone marked, filled `[+]`, empty `[ ]`,
  knocked-out `[!]` — with a tall **representative icon** down the right
  side (colour-keyed: warp cyan, thrust amber, shields blue, gun red —
  `sprites.SUBSYSTEMS`, shown ASCII-transliterated above); the **derived aspect**
  shown in each header (§4.1). The same screen renders an orbital starbase (swap
  thrusters/spindrive for `fusion_reactor`, §4.2).
- **Global bonus**: Spindrive efficiency -> one combat buff, shown in the title
  bar (§4.1).
- **Actions**: `[P]` field-patch (repair-kit, minimal function), `[I]` install
  on-hand component, `[X]` cannibalize (strips a derelict base into parts),
  `[U]` full swap/tier-upgrade (StarDock or friendly base only).
- DESIGN: §4.1 (subsystems/components/repair), §4.2 (starbase variant).

---

## 9. ComputerScreen  *(Phase 1 core; tabs grow through Phase 2)*

```
┌─ SHIP COMPUTER ──────────────────────────────────────────────────────┐
│ [ Map ][ Ports ][ Trade ][ Route ][ Codex ][ Dossier ][ Notes ]      │
├──────────────────────────────────────────────────────────────────────┤
│  PAIR-TRADE FINDER                    scored by profit / turn        │
│                                                                      │
│   Pair               Goods       Dist  Profit/rt  Per-turn v         │
│   --------------------------------------------------------           │
│   Sol <-> Halaf-2     Org/Equ      2      640       320              │
│   Sol <-> Mirach      Fuel/Equ     3      810       270              │
│   Halaf-2 <-> Vega-9  Org/Fuel     4      900       225              │
│                                                                      │
│   selected: Sol <-> Halaf-2    [P] Plot route   [A] Add note         │
│  ------------------------------------------------------------        │
│  Other tabs: Map (explored-universe tree) . Ports (directory w/      │
│  last-seen stock+class) . Route (shortest path, hazard confirm)      │
│  . Codex (finds + lore) . Dossier (species/standing/grudges) .       │
│  Notes (avoid lists)                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

- **Tabs** (`TabbedContent`, §11): **Map** (Tree/DataTable of explored universe),
  **Ports** (directory, last-seen stock + class), **Trade** (pair-trade finder —
  scores opposed-class port pairs by round-trip profit per turn using the live
  price model + shortest path), **Route** (shortest path, one-way aware,
  hop-by-hop send with per-sector hazard confirm), **Codex** (every find + lore;
  fragments become rumor pins on the map), **Dossier** (known species,
  disposition, alliance/player standing, grudges, last-seen tech, threat-tier
  bestiary), **Notes** (avoid lists).
- Because we own the engine these are first-class queries, not screen-scrapers.
- DESIGN: §11, §8 (pricing for finder), §7 (codex), §6 (dossier).

---

## 10. MapScreen  *(retired — WP73; superseded by the Computer's Map tab)*

```
┌─ GALACTIC MAP ────────────────────── you @ Sector 7 . Band 0 (Core) ─┐
│                                                                      │
│   Band 0 Core      Band 1 Hub      Band 2 Frontier   Band 3+         │
│   +-----------+    +-----------+   +-----------+                     │
│   | (1)-(2)   |    | Concord   |   |  * rumor  |     ~ ?             │
│   |  |   |    |    | cluster   |   |           |                     │
│   | (4)-(7@)--+----+ (21)(22)  |~~~+ (40)(41)? |  ....  unknown      │
│   |  |   |    |    |  neutral  |   |           |                     │
│   | (8)-(12)  |    |  lanes ~~ |   | (43)? #?  |                     │
│   +-----------+    +-----------+   +-----------+                     │
│                                                                      │
│   @ you  - warp  ~ neutral lane  * rumor pin  ~ hazard               │
│   P port  o planet  # starbase  ? unexplored                         │
│  ------------------------------------------------------------        │
│   [+/-] zoom   [click] inspect sector   [/] search   [Esc] back      │
└──────────────────────────────────────────────────────────────────────┘
```

- **Banded layout** (`MapView`): distance bands left->right (Core / Hub /
  Frontier / Void), each band a bordered `MapBandPanel` whose border-title is the
  band name; **neutral lanes** are `_MapLane` connectors between the panels
  (always passable, §5/§10). Unexplored shown as `?`. Reached by the `M` key.
- **Overlays**: rumor pins from codex fragments, hazards, ports/planets/
  starbases; clicking a band panel -> sector inspector (ExchangeConflict uniview
  idea, §A.6; `MapBandPanel.Picked`, stubbed in the skeleton).
- DESIGN: §5 (generation/bands/clusters), §10 (territory/lanes), §7 (rumors).

---

## 11. MessagesScreen  *(retired — WP73; superseded by the Computer's Log tab)*

```
┌─ MESSAGES & LOG ─────────────────────────────────────────────────────┐
│ [ Events ][ Comms ][ Bounties ]                                      │
├──────────────────────────────────────────────────────────────────────┤
│  day 4 . 09:12   Stardock: interest accrued +71 slips                │
│  day 4 . 08:50   Kessrin raid reported near Band-2 boundary          │
│  day 4 . 08:31   * Discovery logged: Crashed Ship (Uncommon)         │
│  day 3 . 22:04   Concord envoy: "Our drives await you, trader."      │
│  day 3 . 21:10   Trade: sold 20 Fuel Ore @ 14 -> +280 slips          │
│                                                                      │
│  ------------------------------------------------------------        │
│  [Enter] open   [F] filter   [M] mark read   [Esc] back              │
└──────────────────────────────────────────────────────────────────────┘
```

- **Tabs**: Events (durable `event_log`, §12), Comms (alien/alliance messages,
  Phase 3), Bounties (Phase 3). `RichLog`/`DataTable` with filter.
- DESIGN: §12 (event_log), §9 (ticks generating events).

---

## 12. SpriteGalleryScreen  *(secret dev preview)*

A hidden review screen — **not part of the player flow**. From the Main Menu,
press the unadvertised **`~`** key to open it; `Esc` returns. It previews every
sprite asset in `edge/tui/sprites.py`, **one category per tab** (Planets · Orbit
Views · Ports · Ships · Subsystems), each sprite in a bordered card captioned
with its asset key — so art changes are easy to eyeball and the keys double as a
reference.

```
┌ SPRITE GALLERY · all sprite assets ──────────────────────────────────┐
│ [ Planets ][ Orbit Views ][ Ports ][ Ships ][ Subsystems ]          │
├──────────────────────────────────────────────────────────────────────┤
│  ┌ terrestrial ┐ ┌ jovian ┐ ┌ asteroid_belt ┐ ┌ barren ┐            │
│  │  .-~~~-.    │ │ .-----. │ │ . o . , o .   │ │ .----.  │           │
│  │ ( .o.o. )   │ │(=======)│ │  o . O .  o   │ │( o () )  │           │
│  └─────────────┘ └─────────┘ └───────────────┘ └─────────┘           │
│                                                                      │
│  (Ships tab)                                                         │
│  ┌ player ┐ ┌ freighter ┐ ┌ fighter ┐ ┌ warship ┐ ┌ npc ┐           │
│  │ /==}>  │ │ [===]=>   │ │ <+=-    │ │ <##==>  │ │>--o> │           │
│  └────────┘ └───────────┘ └─────────┘ └─────────┘ └──────┘           │
│                                                                      │
│  (Subsystems tab — icons per §8; ASCII here)                        │
│  ┌ SPINDRIVE ┐ ┌ THRUSTERS ┐ ┌ SCREENS ┐ ┌ MAIN GUN ┐               │
│  │   >*<     │ │    /\     │ │   /\    │ │    ^     │                │
│  │  [|||]    │ │   /||\    │ │  <  >   │ │  [|||]   │                │
│  └───────────┘ └───────────┘ └─────────┘ └──────────┘               │
│ esc Back                                                             │
└──────────────────────────────────────────────────────────────────────┘
```

- Each tab arranges its cards in a grid (the large Orbit Views wrap onto two
  rows so nothing exceeds the 100-col width). Each card tints its art with the
  category colour (planets cyan, ports magenta, ships white, subsystems
  per-icon — warp cyan / thrust amber / shields blue / weapon red) and labels it
  with the dict key. Subsystem icons are unicode in the TUI; this doc shows the
  ASCII transliteration (see §8).
- Reads `sprites` directly: these are static presentation assets, not game
  state, so no DTO/service boundary is crossed.

---

## Keymap convention (WP73 — the normative contract)

Added in the seams-correction arc (SEAMS_PLAN §4, decision D3). New bindings must
follow this; collisions are bugs.

**Reserved global keys** (same meaning on every screen; never rebind locally):

| Key | Meaning |
|-----|---------|
| `Esc` | Back / close the current screen (the only back key — `q` is menu-quit only) |
| `.` | Numbered context-action menu: lists every advertised action on the current screen |
| `?` | Help overlay (keymap + warp legend) |
| `Ctrl+Q` | Quit the app |
| `1`–`9` | Numbered menu/reply selection where a numbered list is shown |

**Verb vocabulary** (a letter keeps one meaning wherever it appears):

| Key | Verb | Screens |
|-----|------|---------|
| `t` | Trade | Port, StarDock (Game: Corp — grandfathered, rename when corp gets a hub) |
| `b` | Buy / Claim-base | StarDock/Starbase buy; Planet claims the base |
| `h` | Haggle / Hail | Ports haggle; Game hails |
| `d` | Deposit / Deliver / Deploy | StarDock deposit, Port deliver, Game deploy, Planet descend |
| `w` | Withdraw / Travel | banking withdraw everywhere (`y` is retired); Game travel |
| `r` | Repair / Rumor / Route-to | context-local but always "restorative/plot" flavored |
| `a` | Attack / Assault / Add | martial on Game/Planet; additive on Computer |
| `g` | Genesis / enGage / loG | destructive `g` actions always confirm (D7) |

**Destructive-confirm rule (D7):** Genesis, Seize Core, Invade, ResignAlliance,
and any first strike (in-sector or from a conversation) go through `ConfirmScreen`
— deny-focused, so a stray Enter never fires them.

**Discoverability:** the Footer shows what fits; `.` (action menu) is the complete
live list; `?` is the reference card. A feature reachable only by hotkey is a bug —
it must also appear in its screen's action menu (automatic once it is a `Binding`).

## Open layout questions (resolve during the Phase 1 UI build)

- **Sidebar width** on narrow terminals (<100 cols): collapse the region mini-map
  first, then the holds bars to a single line.
- **Mini-map vs. full MapScreen**: keep the sidebar node diagram to <= current
  region; everything larger lives in §10.
- **Haggle panel** as modal over PortScreen vs. inline — mocked as modal; revisit
  with Pilot once we feel the flow.
- **Engine-room reuse** for orbital starbases (§4.2): same screen, swapped
  subsystem set — confirm one widget can render both before duplicating.
