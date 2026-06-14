# UI Inspiration Board

Visual and interaction references for the `DESIGN.md` §11 screens, organized so
each entry says **what to steal** and maps back to a screen in
[`../../UI_MOCKUPS.md`](../../UI_MOCKUPS.md). This is a research artifact, not a
spec — it feeds the next step (promoting the ASCII wireframes into a live Textual
skeleton).

External screenshots are **linked, not vendored** (third-party/copyrighted). The
one local, directly-readable reference is `terminal-space` in `references/`.

## Sources at a glance

| # | Source | Medium | Best for |
|---|--------|--------|----------|
| 1 | `terminal-space` (local) | Python terminal client | Layout, sidebar, command grammar, warp animation — our closest cousin |
| 2 | Original TradeWars 2002 | BBS / ANSI | Muscle-memory layout, canonical sector/port text |
| 3 | Textual showcase apps | Textual TUI | Widget idioms (DataTable, tabs, RichLog, sparklines, command palette) |
| 4 | Reference web-game art | PHP web games | Visual/naming flavor only (not layout) |

---

## 1. terminal-space — local, the closest cousin

Source: `references/terminal-space/` (read-only per CLAUDE.md — **reimplement
ideas, don't copy code**; it's `prompt_toolkit`, not Textual, so translate
idioms). Live recording: **asciinema cast**
<https://asciinema.org/a/Rud50qG0utHbHBpHGl60WuRRX> (linked from its README).
**Local captures** of its main menu, game, and port screens (with what-to-steal
notes) live in [`terminal-space/`](terminal-space/README.md).

Concrete patterns harvested, with file pointers and the screen each informs:

- **Single-keystroke command grammar** — `InstantCmd` literal/regex bindings
  (`d` redisplay, `p` port, `a` attack, numbers = warp), Esc-cancelable.
  `tspace/client/sector_prompt.py`, `tspace/client/instant_cmd.py`.
  → **Game** command grammar (§11); we already cite this in DESIGN.
- **Stat-frame sidebar** — a generic `StatFrame(title, [Stat(label, callable)])`
  that auto-pads labels and renders lists as ` - item` lines.
  `tspace/client/ui/stat_frame.py`. → our **Game status sidebar** (Player /
  Holds / Ship panels); take the auto-pad + list-render pattern directly.
- **Game-scene composition** — `VSplit[ HSplit(StatFrames) | terminal-text |
  Frame("Map", warps) ]`. `tspace/client/scene/game.py`.
  → **Game** layout. *Divergence to note:* they put stats **left** and warps in
  a **right** "Map" frame; our §11 layout is the inverse (sector view + warps
  left, stats right). Worth A/B-ing in the skeleton.
- **Animated warp transition** — `WarpDialog`: a starfield that accelerates,
  then an `AnimatedPlanetApproach` when the destination has a port/planet.
  `tspace/client/ui/warp.py`, `ui/starfield.py`, `ui/draw.py`.
  → our optional warp flourish + **MainMenu** starfield (§11 aesthetics).
- **Menu dialog** — forked Dialog with horizontal buttons, shadow, custom
  background. `tspace/client/ui/menu.py`. → **MainMenu**.
- **Port trade table** — built with `tabulate` (buy/sell columns).
  `tspace/client/port_prompt.py`. → **PortScreen** commodity table (we'll use a
  Textual `DataTable`).
- **Fog-of-war DTO** — `to_public(context)` serialization boundary (the pattern
  DESIGN §3 adopts). `tspace/common/models.py`, `tspace/client/models.py`.

---

## 2. Original TradeWars 2002 — the muscle memory

We deliberately honor TW2002 layout/cadence (§11). Use these to get the
canonical **sector display** and **port (CIM)** text format right.

- **Break Into Chat — TW2002** (screenshots): <https://breakintochat.com/wiki/TradeWars_2002>
  - Title screen — `https://breakintochat.com/w/images/7/72/Tradewars-2002-title-1.png` → **MainMenu**
  - StarDock docking — `https://breakintochat.com/w/images/5/50/Tradewars-2002-stardock.png` → **StarDockScreen**
  - Planet landing (Terra) — `https://breakintochat.com/w/images/6/6e/Tradewars-2002-terra.png` → **PlanetScreen / SurfaceScreen**
  - StarDock in the TWTerm helper — `https://breakintochat.com/w/images/e/ef/Twterm-stardock.png` → **ComputerScreen** (the community helper overlays we're absorbing as first-class)
  - Alien derelict art — `https://breakintochat.com/w/images/c/c7/AlienDerelict1.gif` → discovery flavor
- **MobyGames screenshots**: <https://www.mobygames.com/game/3340/trade-wars-2002/screenshots/>
- **TradeWars Museum — Gypsy's Big Dummy's Guide** (canonical text walkthroughs of
  the sector/port prompts): <https://wiki.classictw.com/index.php/Gypsy's_Big_Dummy's_Guide_to_TradeWars_Text>
- **v1 documentation text**: <http://wiki.classictw.com/index.php/TradeWars_2002_v1_Documentation_Text>

**What to steal:** the sector-display block ordering (sector #, beacon, ports/
planets/ships, warps line), the terse prompt cadence, and the StarDock framing —
for authenticity, then modernize with widgets.

---

## 3. Textual showcase apps — widget idioms

Run `textual demo` (after `pip install textual`) for a live gallery; widget
reference: <https://textual.textualize.io/widget_gallery/>. Curated list:
<https://github.com/oleksis/awesome-textualize-projects>.

| App | Link | Idiom to steal | Our screen |
|-----|------|----------------|------------|
| **Harlequin** (SQL IDE) | <https://harlequin.sh> · <https://github.com/tconbeer/harlequin> | Dense `DataTable`, results pane, tree sidebar | **ComputerScreen** (port directory, pair-trade finder), **MapScreen** tree |
| **Posting** (HTTP client) | <https://posting.sh> · <https://github.com/darrenburns/posting> | `TabbedContent`, command palette, keyboard-first nav with mouse affordances | **StarDockScreen** / **ComputerScreen** tabs, our command grammar |
| **Toolong** (log viewer) | <https://github.com/Textualize/toolong> | `RichLog` tailing, search, merge | **Game** event ticker, **MessagesScreen** |
| **Dolphie** (DB dashboard) | <https://github.com/charles-001/dolphie> | Live `Sparkline`/bar dashboards, panels | **Game** status sidebar bars (shields/holds/aspects) |

---

## 4. Reference web-game art (flavor only)

These are PHP **web** games — useful for visual motifs and naming, **not**
layout. Assets are already in-repo (read-only):

- `references/blacknovatraders/images/` — ship sprites (`marauder.gif`,
  `transport.gif`, `tfighter.gif`), `largeplanet.gif`. → ship-class / planet
  naming and silhouette flavor.
- `references/aatraders/images/` — galaxy/space backdrops (`3dgalaxybase.*`,
  `bgspace.jpg`). → MapScreen / title backdrop mood.

---

## Mapping: our screen → steal-from

| Screen (UI_MOCKUPS) | Primary references |
|---|---|
| MainMenu | TW2002 title (2); terminal-space MenuDialog + starfield (1) |
| Game | terminal-space scene + StatFrame (1); TW2002 sector display (2); Dolphie bars, Toolong ticker (3) |
| PortScreen | terminal-space port table (1); TW2002 port/CIM (2); Harlequin DataTable (3) |
| PlanetScreen / SurfaceScreen | TW2002 Terra landing (2) |
| StarDockScreen | TW2002 stardock (2); Posting tabs (3) |
| AlienContactScreen | (new ground — §6.7; lean on Posting panels + dialogue layout) |
| EncounterScreen | terminal-space battle scene `tspace/client/scene/battle.py` (1) |
| EngineRoomScreen | (new ground — §4.1; Lightspeed engine-room layout, see Appendix B) |
| ComputerScreen | TWTerm helper (2); Harlequin + Posting (3) |
| MapScreen | terminal-space warp/Map frame (1); Harlequin tree (3); aatraders backdrops (4) |
| MessagesScreen | Toolong (3) |

---

## Next steps

The project is a [pixi](https://pixi.sh) project (`pyproject.toml` + `pixi.lock`,
conda-forge); all tooling runs through `pixi run`.

1. **Browse live**: `pixi run python -m textual` for the interactive demo/widget
   gallery (the `textual-dev` CLI also gives `pixi run textual colors` and
   `pixi run textual borders` design explorers, plus `run --dev` / `console` /
   `serve` for our own app). Optionally run the cousin —
   `cd references/terminal-space && make pyenv && make run` — to feel the
   InstantCmd/sidebar flow, or just watch the asciinema cast.
2. **Skeleton (done for Game + Port)**: a throwaway Textual skeleton fed by dummy
   DTOs lives in `edge/tui/`. Launch it with `pixi run tui`; regenerate the SVG
   screenshots in `docs/ui/shots/` with `pixi run shots`. It uses the StatFrame
   sidebar pattern and the Harlequin/Dolphie widget idioms above.
3. **Add the remaining Phase-1 screens** to the skeleton — StarDock (tabs),
   Computer (pair-trade finder DataTable), Map — then iterate to taste.
4. **Capture** any third-party screenshots worth pinning into
   `docs/ui/inspiration/img/` (prefer links for copyrighted game captures; only
   vendor what we generate ourselves or that is clearly license-OK).
</content>
