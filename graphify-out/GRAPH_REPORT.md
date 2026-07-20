# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 338 files · ~9,167,388 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8240 nodes · 36021 edges · 197 communities (169 shown, 28 thin omitted)
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 11582 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7c5f363a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Core Rules & Events Engine
- Sector Scene & Widgets
- Screens, DTOs & Remote Play
- Standing, Corp & Combat Rules
- UI Config & Route Tests
- Aliens & Alliance Admission
- Computer Screen & Alliances Tab
- Disposition Bands & Ship Classes
- Planet & Orbit Views
- Attitude, Disposition & Contracts
- Station Art & Portrait Rendering
- Encounters & Station Archetypes
- Domain Models & Colonizability
- Engine-Room Component Workbench
- Dialogue-Pack Save Guard
- Game Lifecycle & Pathfinding
- Universe Embedding & Bearings
- The Entity & Command Reduce
- TUI Screen Widgets
- Subsystem Layouts & Ownership
- Spacebattle Combat Rules
- UI Mockup Screenshot Harness
- Market Orders & Regions
- Config Schema Models
- Signature Mechanics
- Derived Aspects & Engine Room
- Dialogue Authoring Pipeline
- Bigbang Aliens & Region Control
- Core Governance & Seizure
- Dev Patch Tooling
- Core-Seizure Confirm Screens
- Detail Table Overlay
- Spacebattle Battle Screen
- Server Net & Engine Ticker
- Market Economy & Pricing
- Devtool CLI & Sysop
- Core Rules Tests
- LLM Bot Brain & Console
- Config Loading & Sidecar Merge
- Base Screen Chrome & Saves
- Groundwar Battle Screen
- Planet Terrain & Surface Sites
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- test_ui_black_hole.py
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- test_ui_cloud_city.py
- Community 133
- Community 134
- EngineRoomDTO
- Community 136
- LiveSysopService
- main
- MarketDTO
- Community 140
- Community 141
- TopologyModeConfig
- Community 143
- trader_step
- test_genesis.py
- test_intel_contact.py
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- market_view
- .compose
- Ticker
- StaticGenerator
- .rebuild_adjacency
- Community 160
- .state
- ComputerDTO
- TavernDTO
- .apply
- Community 166
- Community 169
- Community 170
- _SpriteCard
- Community 174
- Community 175
- Community 179
- Community 180
- Community 181
- Community 185
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 202
- Community 203
- graphify.js
- graphify.md
- graphify.md
- __init__.py

## God Nodes (most connected - your core abstractions)
1. `UniverseState` - 525 edges
2. `GameConfig` - 480 edges
3. `Commodity` - 428 edges
4. `reduce()` - 391 edges
5. `EconomyError` - 342 edges
6. `EdgeApp` - 265 edges
7. `apply_result()` - 238 edges
8. `Warp` - 235 edges
9. `ComponentTier` - 233 edges
10. `Event` - 221 edges

## Surprising Connections (you probably didn't know these)
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_species_knowledge_is_deterministic_bounded_and_referential()` --calls--> `generate()`  [EXTRACTED]
  tests/test_dialogue_intel.py → edge/bigbang/generator.py
- `test_every_surface_find_is_artifact_plus_lore()` --calls--> `generate()`  [EXTRACTED]
  tests/test_groundwar_survey.py → edge/bigbang/generator.py
- `test_open_space_payloads_keep_their_variety()` --calls--> `generate()`  [EXTRACTED]
  tests/test_groundwar_survey.py → edge/bigbang/generator.py
- `test_check_relations_rejects_mutual_intra_bloc_enmity()` --indirect_call--> `ValidationError`  [INFERRED]
  tests/test_aliens.py → edge/bigbang/validate.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Engine-room model → localized combat damage → space-battle facing damage** — docs_phase2_plan_engine_room_wp1, docs_phase3_plan_localized_damage_wp26, docs_spacebattle_poc_facing_damage [INFERRED 0.75]
- **ServiceProtocol seam drives bot, LLM pilot, and hosted clients** — docs_scripting_serviceprotocol_seam, docs_scripting_llm_pilot, docs_hosting_remote_client, docs_hosting_edge_server [EXTRACTED 0.85]
- **Dialogue depth: sessions, situational facts, arcs, combat dialogue** — docs_phase3_plan_contact_session_wp28, docs_phase3_plan_situational_facts_wp29, docs_phase3_plan_combat_dialogue_wp31, docs_phase2_plan_dialogue_wp8 [EXTRACTED 0.85]
- **Four competing trading-enjoyability plans** — docs_trading_enjoyability_plan, docs_trading_enjoyability_plan_02, docs_trading_enjoyability_plan_03, docs_trading_enjoyability_plan_04 [EXTRACTED 0.90]
- **Station archetype art pipeline (generation to ANSI runtime)** — images_ui_ports_provenance_openai_image_gen, images_ui_ports_provenance_build_station_archetype_art, images_ui_ports_provenance_chafa_pillow [EXTRACTED 0.85]
- **Fungible component economy across ships and bases** — docs_design_engine_room, docs_design_component_vocabulary, docs_design_orbital_starbases, docs_design_localized_damage [EXTRACTED 0.90]
- **Alliance/territory spine (governance, clusters, ownership)** — docs_design_governing_alliance, docs_design_alliances, docs_design_home_clusters, docs_design_ownership, docs_design_core_space [EXTRACTED 0.85]
- **Distance-scaled risk/reward gradient** — docs_design_distance_bands, docs_design_discoveries, docs_design_alien_species, docs_design_ownership [INFERRED 0.80]

## Communities (197 total, 28 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.09
Nodes (440): _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup() (+432 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.04
Nodes (93): is_colonizable(), Whether a world of this type can be claimed and settled (§4.2).      Colonizable, range, generate_with_player(), Any, `generate()` then `enroll()` — the common "fresh game with player 1" setup., WP27: logging a find into the codex pays experience_per_discovery., WP27 Core-law basics: a criminal crossing into the Core is put on notice, once (+85 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.02
Nodes (117): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, The roaming Entity's always-on in-sector presence hint (DESIGN §7, WP35).      F (+109 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.12
Nodes (36): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A knocked-out part contributes nothing until it is patched (§4.1). (+28 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.05
Nodes (58): _check_discovery_gradient(), Discovery gradient (§7 / §5 step 8): mean rarity **and** value strictly rising, alliance_standing_shift(), grudge_shift(), The greeting-vs-violence penalty from ill standing with a species' bloc (§6.3)., The active-grudge penalty this species applies to the player (§6.5, §10).      T, PackConfig, How an encounter group spawns (DESIGN §6.1). Phase-3 forward-compat. (+50 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.04
Nodes (72): _check_starbases(), Orbital-base invariants (§4.2 / §5 step 8, WP4).      Every base sits in its pla, alliance_rivals(), Public: the blocs at odds with `alliance_id` (symmetric rivalry, §6.3).      Thi, citadel_defense_mult(), has_gun(), Whether `planet` fields an operational citadel gun (§4.2, WP54/WP55)., Whether the L3 siege shield bars invasion of `planet` (§4.2, WP55).      True wh (+64 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.05
Nodes (81): Game, Notice, A ship hull (DESIGN §4).      A player hull carries `subsystems` (the engine-roo, Holds occupied — trade cargo plus loose (uninstalled) components.          Loose, One posted noticeboard message (DESIGN §14 — WP58).      A captain's log pinned, Top-level game record (DESIGN §4)., A node in the warp graph (DESIGN §4). `warps_out` are sector ids., A fresh universe seeded from the game's seed (RNG owned here, §3). (+73 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.07
Nodes (64): CombatConfig, _evade_chance(), flee_chance(), Random, Ship, Subsystem, The chance to slip an `ahead`/`spinal` firing line (a combat-speed contest)., Maybe knock out one component after a hull-reaching volley (§4.1, WP26).      Th (+56 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.02
Nodes (112): Aspect, CommodityLine, EncounterDTO, EncounterFoeDTO, EngineRoomPreviewDTO, Hold, LogEntry, NavStripDTO (+104 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.04
Nodes (55): One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).      `s, One subsystem panel: its derived aspect and its slot grid (§4.1)., Slot, Subsystem, ContextStrip, EmptyState, Any, ComposeResult (+47 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.19
Nodes (13): expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar, Every authored expansion string in a grammar (for placeholder validation)., _grammar_pack(), Phase-2 — Tracery realisation of dialogue grammars (DESIGN §6.7).  Covers `edge., test_expand_does_not_disturb_global_rng() (+5 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.16
Nodes (7): FieldPrompt, Pressed, Submitted, The shared one-field prompt: inline validation, no silent failures.      Subclas, Return (value, None) to accept or (None, reason) to hold the form open., PromptResult, test_modal_close_returns_focus_to_invoker()

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.05
Nodes (53): TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Generate a fresh universe on disk and start the background ticker.          The, Reload the saved game by replaying its command log (DESIGN §12).          Return, Validate art coverage and read scene-sprite sizes before a game starts., Run the client-owned engine ticker as a Textual worker (WP61).          The tick (+45 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.03
Nodes (72): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed (+64 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.03
Nodes (125): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+117 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.07
Nodes (83): Command, Validate `command` for `player_id` and return its delta + events., reduce(), instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice() (+75 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.16
Nodes (31): _best_roundtrip_margin(), _check_degree_cap(), _check_expansive_no_chokepoint(), _check_profitable_pair(), _check_reachable(), _check_stardock(), Exception, Big-bang validation — the Phase-1 subset of DESIGN §5 step 8 / §13.  Asserts the (+23 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.03
Nodes (132): _archetype(), assign_station_archetypes(), _builder(), Deterministic builder-archetype assignment for ports and orbital bases., Resolve the species whose configured archetype designed the structure., Stamp every structure's builder archetype after alien regions exist (§5)., _hit_foe(), _player_damage() (+124 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.05
Nodes (73): _amain(), _encode_any(), _error(), GameServer, LobbyServer, Any, Command, Event (+65 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.02
Nodes (133): ActiveBinding, AmountPrompt, Container, Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, GameService, EncounterDTO, Event (+125 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.02
Nodes (121): BaseModel, Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, citadel_foe(), conquer(), InvasionOutcome, level_config(), _levels(), Random (+113 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.06
Nodes (69): attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate(), _int(), literalist() (+61 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.07
Nodes (40): compose_horizontal(), flip_row(), Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo, Compose a sprite grid by laying parts left-to-right to fill ``target_w``.      O (+32 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.10
Nodes (30): is_extractable(), normalize_belt(), Scrub colony/citadel/base affordances off a non-landable spatial world (§4.2)., Whether this world yields raw goods in orbit without colonists (§4.2).      The, _dirty_belt(), WP-PR06 — asteroid belts are spatial features, not colony worlds (playtest PT-30, A belt still hosts spatial finds (its sector's discoveries), just not landable s, Every belt is born with ore in it, and the deep fields are the rich ones. (+22 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.07
Nodes (59): apply_intrigue(), flip_core_governor(), GovernanceDelta, _home_cluster_bases_intact(), IntrigueDelta, _nearest_legal(), npc_seizure_ready(), _operational_core_bases() (+51 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.06
Nodes (83): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), Path, _build_game(), Load the game at `db` if it exists, else generate a fresh one there (WP12 resume, Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, Path (+75 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.13
Nodes (8): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., Static, Vertical, Widget, The base's standing, on one line, in a bordered panel above the installations.

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.10
Nodes (9): _assert_impl(), _assert_remote_impl(), GameClient, Protocol, The async surface every game consumer programs against (WP61).      Mirrors `Ser, ComposeResult, Static, The excavated artifact card; all identity comes from the refreshed DTO. (+1 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (35): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+27 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.13
Nodes (9): BridgedGameClient, Sync bridge: drive an async `RemoteClient` from the synchronous TUI (WP68).  Mos, Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises)., A `GameService`-shaped synchronous facade over the connected client., An awaitable facade safe to call from Textual's loop (GW-WP07)., Run the full async ``RemoteClient`` surface on its owning background loop., Bridge the async event iterator one item at a time onto Textual's loop. (+1 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.06
Nodes (77): DrawFn, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., port_unit_price(), Move stock `regen_frac` of the way toward `desired_frac * capacity`., Quoted price for a line using the economy config's per-commodity tunables., regenerate_stock() (+69 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.04
Nodes (96): Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, apply_dev_patch(), _clamp_ship_field(), DevPatch, DevPatchError, _expire_contract(), _force_settlement(), _moderate_notice() (+88 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (58): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+50 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (31): Brain, BotRecord, The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Path (+23 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.06
Nodes (55): load_config(), load_config_with_sidecar(), load_default_config(), _merge_dialogue(), Any, Path, Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Load the bundled default config (`config/default.yaml`). (+47 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.07
Nodes (33): BaseScreen, ComposeResult, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th, The visible service tab's id (the unit every action keys on)., The `.` menu / `?` help / palette list, scoped exactly like the footer (PT-32)., Tabs the base withholds (standing / service-integrity gated) — recorded once at, Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Install the selected carried component into the selected open base slot. (+25 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.07
Nodes (19): BattleScreen, DeployEntry, MapView, Battle, Click, ComposeResult, Key, Text (+11 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.16
Nodes (21): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), generate_find_art(), _pit() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.03
Nodes (260): _check_home_clusters(), _check_planet_ownership(), Ownership invariants (§4.2 / §5 step 8): Core governor-owned, unowned fraction, Alliance home-cluster invariants (§5 step 6, §6.3).      Each non-governing bloc, player_foe(), Build the combat foe for a *defending player's* live ship (§14, WP67 — attacker-, GameConfig, Top-level config bundle, validated from the parsed YAML mapping. (+252 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (27): BotSetup, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, BotRunner, Command, Event, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69). (+19 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (26): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+18 more)

### Community 45 - "Community 45"
Cohesion: 0.05
Nodes (39): ABC, BaseException, CronResolver, DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12)., The save was made with a different dialogue pack; replay would fail mid-way., EngineState (+31 more)

### Community 46 - "Community 46"
Cohesion: 0.02
Nodes (174): MapNodeDTO, One traversed sector on a plotted route — what the player reads (§11, WP14)., A clickable sector node on the local map: its label's cell box in `rows`.      `, RouteHopDTO, EdgeApp, Any, Resize, Screen (+166 more)

### Community 47 - "Community 47"
Cohesion: 0.05
Nodes (28): ContactChoiceDTO, One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, One authored player reply on a branching dialogue node (§6.7 optional branching), TechOfferDTO, Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait. (+20 more)

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (49): DataObject, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Enum, Random (+41 more)

### Community 49 - "Community 49"
Cohesion: 0.06
Nodes (72): advance_build(), building(), open_build(), Whether a timed build is currently open on `planet` (§4.2, WP54)., Open a timed build for the next citadel level, paying its cost (§4.2, WP54)., Advance an open build by one production tick, returning `(planet, completed)`., Planet, A planet (DESIGN §4.2): a typed, ownable, producing world.      `planet_type` fi (+64 more)

### Community 50 - "Community 50"
Cohesion: 0.09
Nodes (44): main(), `edge-groundwar` — the ground-war POC's Textual shell.  Throwaway UI (the `tui`-, dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition (+36 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.03
Nodes (68): clear_slot(), Remove the save and its WAL/SHM sidecars so a new game starts clean., ComposeResult, Pressed, RumorModal — reveals the lead a tavern rumour just bought (WP-PR2-03 / PT-35)., RumorModal, Any, ComposeResult (+60 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (38): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+30 more)

### Community 54 - "Community 54"
Cohesion: 0.09
Nodes (9): main(), PlaytestService, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable., `edge-playtest-dialogue` entry point — open the dialogue playtest TUI. (+1 more)

### Community 55 - "Community 55"
Cohesion: 0.10
Nodes (29): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothi (+21 more)

### Community 56 - "Community 56"
Cohesion: 0.08
Nodes (30): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+22 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (35): Part, A recombinable sprite fragment, authored as ``cells`` rows and composed to     f, _compose(), _grammar_floor(), _mirror_part(), _mirror_row(), PortGenerator, Random (+27 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (41): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+33 more)

### Community 59 - "Community 59"
Cohesion: 0.11
Nodes (10): GroundExpeditionScreen, Any, Key, Walk, scan, excavate, and talk through authoritative survey commands., POC camera pan: the cursor rides with the viewport., Enter means "commit the cursor": set down while inbound, march once landed., Whether the cell under the cursor is an advertised drop site., Clear the overlay and stop the clock — also the skip path, so a keypress during (+2 more)

### Community 60 - "Community 60"
Cohesion: 0.06
Nodes (33): _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl, The same actionable Stardock service projections the regular client receives. (+25 more)

### Community 61 - "Community 61"
Cohesion: 0.06
Nodes (19): _decode_any(), Any, Command, EncounterDTO, Event, Apply a command through the in-process service (events fan out via `on_events`)., Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, A `GameClient` over a websocket to `edge-server` (WP68) — the hosted-play seam. (+11 more)

### Community 62 - "Community 62"
Cohesion: 0.10
Nodes (13): ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key, Text, Widget (+5 more)

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (25): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, _add_structure() (+17 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (42): Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus() (+34 more)

### Community 65 - "Community 65"
Cohesion: 0.09
Nodes (38): DialoguePack, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace, One conversational beat: its concept, extra placeholders, and Phase-2 reachabili, _branch_closure() (+30 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (16): FormField, InterventionForm, Any, ComposeResult, DataTable, HeaderSelected, OptionSelected, Pressed (+8 more)

### Community 67 - "Community 67"
Cohesion: 0.13
Nodes (6): ContactDTO, A peaceful alien contact screen (§6, §6.7, §11)., The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any., Plain-language meaning alongside the exact effective-disposition cue.

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.19
Nodes (15): _discoveries(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers)., The spatial display id for an internal sector id, or `—` if none is cached., A sector reference as `internal/spatial` (the §5.1 dual id)., Reverse the internal→spatial map (spatial ids are a bijection, §5.1)., Resolve a `--route` endpoint token to an internal sector id.      Accepts an int (+7 more)

### Community 70 - "Community 70"
Cohesion: 0.13
Nodes (38): owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, _force(), _generated(), _make_hostile(), _mini_state(), WP41 — sector fighters, mines, beacons, black-hole hazards (§10).  Covers the pu, A lethal hazard routes through the WP26 escape pod (WP75 — the A5 seam closed). (+30 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (36): Color, available_archetypes(), available_subtypes(), Procedural ASCII art generation logic., Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype() (+28 more)

### Community 72 - "Community 72"
Cohesion: 0.05
Nodes (47): AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json(), get_backend(), OllamaBackend (+39 more)

### Community 73 - "Community 73"
Cohesion: 0.04
Nodes (65): _Coord, HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology (+57 more)

### Community 74 - "Community 74"
Cohesion: 0.23
Nodes (14): WP-PR07 — settling more colonists onto an already-owned colony (playtest PT-11)., Every `TransferCargo` moves goods between ship holds and colony stores without, An owned colony with stores + a ship with cargo and free holds, same sector., _state(), test_batch_load_is_one_delta_and_shares_free_holds(), test_invalid_batch_is_atomic(), test_settle_clamps_to_aboard_and_habitability(), test_settle_rejected_on_uncolonizable_world() (+6 more)

### Community 75 - "Community 75"
Cohesion: 0.13
Nodes (17): LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Yield events as they are produced — the service pushes both apply + tick events., Run the embedded engine ticker until stopped (the app's engine worker, §3)., The embedded ticker (tests/shots that step it directly)., The wrapped in-process service (single-player back-compat; never used for remote, _config() (+9 more)

### Community 76 - "Community 76"
Cohesion: 0.18
Nodes (12): The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Composites one sector as an *arrival view* (UI_MOCKUPS.md §1, PT-36/PT-44)., Blank the starfield in a region (an asteroid belt's rocks would otherwise, Stamp one markup line at an exact position (blanks overwrite stars, so a (+4 more)

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (31): Assault, ground_access(), OrbitalOnly, Classify how the player may interact with `planet` from orbit (GW plan §contract, This world is only ever interacted with from orbit (no ground operation).      A, This world opens a tactical **assault** once its orbital defences fall (GW-WP08+, Whether the orbital ladder is clear and a platoon could land right now., GroundAccess (+23 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (14): Battle, Event, Side, One cell of rocky debris (belt scenarios). Blocks fire lines and wings;     dest, A missile salvo in flight — a board object chasing its target ship., One log/FX entry drained by the UI after each rules call., A ship (any footprint cell), wing, rock, or wreckage sits here — one         pie, Every board cell of the piece's footprint (anchored on the centre).         Ship (+6 more)

### Community 79 - "Community 79"
Cohesion: 0.10
Nodes (26): ComposeResult, Pressed, Submitted, Enter in a row's amount field submits that row in the colony-supply direction, A modal transfer editor for the player-owned world in the current sector., TransferWorkbenchScreen, _has_scrollable_ancestor(), _new_game() (+18 more)

### Community 80 - "Community 80"
Cohesion: 0.17
Nodes (17): Battle, CombatConfig, DroneConfig, FighterConfig, _gun(), GunStats, LanceConfig, load_config() (+9 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (32): alien_dialogue_default.yaml (dialogue corpus), alien_dialogue_species.yaml (species grammars), alien_roster_default.yaml (species roster), default.yaml (game constants), Alien species disposition system, Alliances (rival blocs, join one at a time), Asteroid belt mining (finite reserves), Universe generation (Big Bang) (+24 more)

### Community 82 - "Community 82"
Cohesion: 0.10
Nodes (38): decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command(), encode_dto(), encode_event() (+30 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (19): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), main(), _parse_args() (+11 more)

### Community 84 - "Community 84"
Cohesion: 0.16
Nodes (6): CronTask, EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3).

### Community 85 - "Community 85"
Cohesion: 0.07
Nodes (48): ContractsConfig, Favors + escort contracts issued through the dialogue system (DESIGN §6.7, §14 —, accept(), active(), advance_convoy(), by_id(), complete_destroy_on_kill(), complete_destroy_on_raze() (+40 more)

### Community 86 - "Community 86"
Cohesion: 0.05
Nodes (61): Create the reserved hidden Legendary codex row for the Entity (DESIGN §7, WP35)., _reserve_entity_codex(), _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component (+53 more)

### Community 87 - "Community 87"
Cohesion: 0.08
Nodes (28): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+20 more)

### Community 89 - "Community 89"
Cohesion: 0.24
Nodes (3): EngineRoomDTO, The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)., _room()

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (29): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+21 more)

### Community 91 - "Community 91"
Cohesion: 0.06
Nodes (25): GameScreen, Event, Whether the sidebar fits — hidden on narrow terminals so the sector view, The event-log lines, most recent last (a single fallback when empty)., Open the fight screen, never a duplicate (WP-fix): a confirm-modal dismiss can, Resume one live survey screen, never stacking duplicates., Route a movement interruption (§10, WP24): a violence opener pushes the, Open the unified base view for the starbase here (§4.2, WP80).          No longe (+17 more)

### Community 92 - "Community 92"
Cohesion: 0.03
Nodes (113): _check_relations(), _check_species(), Alien-placement invariants (§6 / §5 step 8).      Reference integrity (the gover, Inter-species relations are consistent with the alliance structure (§6.4, WP39)., apply_spillover(), attitude_locked(), _clamp01(), disposition_band() (+105 more)

### Community 93 - "Community 93"
Cohesion: 0.19
Nodes (19): list_portraits(), portraits_dir(), Path, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait() (+11 more)

### Community 94 - "Community 94"
Cohesion: 0.14
Nodes (24): CronFn, BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), The pure reducer for a persisted cron name (raises on an unknown name)., resolve_cron() (+16 more)

### Community 95 - "Community 95"
Cohesion: 0.02
Nodes (83): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state)., The DTO under the highlighted row of `table_id`, or None.          WP-UI21: reso (+75 more)

### Community 96 - "Community 96"
Cohesion: 0.07
Nodes (58): _build_site(), _cell_cost(), dig_trench(), _dist(), generate_survey(), _in_bounds(), is_landing_site(), _keepout() (+50 more)

### Community 97 - "Community 97"
Cohesion: 0.14
Nodes (7): Any, Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Any, A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., RemoteService

### Community 98 - "Community 98"
Cohesion: 0.07
Nodes (68): Grudge, A durable, dated grievance (DESIGN §4, §6.5) — the diplomacy layer's memory., accrue_interest(), alien_drift(), _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16)., Run one trade for every NPC merchant working a port this firing (§8, WP43). (+60 more)

### Community 99 - "Community 99"
Cohesion: 0.12
Nodes (26): Binding, Shown while the terminal is below the 80×24 floor (WP-UI05).      It never traps, SizeNoticeScreen, _action_name(), _all_actions(), _bindings(), _method_source(), _pane_bindings() (+18 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.24
Nodes (4): ActionMenuScreen, Any, ComposeResult, Screen

### Community 103 - "Community 103"
Cohesion: 0.06
Nodes (62): GroundCellDTO, One sensor contact, masked until excavation settles the real discovery (G6/G7)., A friendly settlement visible on the projected survey map.      ``plaza_x``/``pl, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, SurveyContactDTO, SurveySettlementDTO, ground_operation_view(), Project the player's active survey without exposing its generation identity (GW- (+54 more)

### Community 104 - "Community 104"
Cohesion: 0.12
Nodes (28): Adjacency, _annotate(), can_warp(), one_way_exits(), plan_route(), plan_route_legs(), Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com (+20 more)

### Community 105 - "Community 105"
Cohesion: 0.17
Nodes (25): build_nav_strip(), _nearest_free(), _octant(), The main-screen nav rose — a bearing-placed compass of immediate warps (§11).  B, Snap a bearing (radians, 0 = east, +y = north) to one of 8 compass octants., The preferred octant, or the closest free one (deterministic +d before -d)., The cell text: spatial id plus content codes once charted (fog masks codes)., Band tint for a charted warp; dim for an uncharted one (matches the local map). (+17 more)

### Community 106 - "Community 106"
Cohesion: 0.22
Nodes (6): Random, Style, Deployed forces as glyph-scale presence marks — fighters flying patrol         t, Base grid from the procedural `edge.art` starfield (seeded per sector)., Crop a sprite to its inked bounding box. Grammars render into the         reques, Sprinkle single glyphs through free sky (padded a cell so they never hug

### Community 107 - "Community 107"
Cohesion: 0.31
Nodes (8): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., ModuleType

### Community 108 - "Community 108"
Cohesion: 0.08
Nodes (53): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., combat_contexts(), DialogueIntegrityError, _entry_strings(), _is_catch_all() (+45 more)

### Community 109 - "Community 109"
Cohesion: 0.15
Nodes (7): LocalMapDTO, The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map(), Bake the local map to fit `width`, overlaying the active route (§6.7/§11)., Selectable sector nodes, top-to-bottom then left-to-right (cursor home order)., Swap in a freshly baked map, preserving the selected sector where possible.

### Community 110 - "Community 110"
Cohesion: 0.06
Nodes (28): layout_tier(), ComposeResult, Horizontal, Resize, Static, Stardock-model header: station exterior at left, active-service scene at right., Exterior-art footprint beside a service banner, from scene config.      `expect_, Exterior and banner sharing one explicitly centered vertical midpoint. (+20 more)

### Community 111 - "Community 111"
Cohesion: 0.10
Nodes (39): entity_species(), The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None., LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered() (+31 more)

### Community 112 - "Community 112"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 113 - "Community 113"
Cohesion: 0.07
Nodes (64): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line() (+56 more)

### Community 114 - "Community 114"
Cohesion: 0.05
Nodes (86): MarketOrderDTO, One open order on the Computer's Market tab (§8, WP48)., _best_pair(), _codex_entries(), computer_view(), _display(), engine_room_view(), _event_player() (+78 more)

### Community 115 - "Community 115"
Cohesion: 0.13
Nodes (20): LiveSysopService, Any, Event, Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC., Apply an intervention to the authoritative live game as the target player., config_dump(), _intervene(), _lobby_hint() (+12 more)

### Community 116 - "Community 116"
Cohesion: 0.11
Nodes (17): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+9 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.07
Nodes (55): apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., Command, Apply an engine cron's result: upsert entities + persist its durable trail., Validate, persist, and apply a command; return the events it produced., _generated(), WP38 — joinable alliances: admission, rival fallout, Core law (§6.3, §10).  Cove, test_advance_then_join_succeeds_and_is_exclusive() (+47 more)

### Community 119 - "Community 119"
Cohesion: 0.15
Nodes (19): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), format_route(), list_items(), Render one category of populated universe items as an id-keyed table., Resolve two endpoints (internal or spatial id) and plot the fewest-hop route., main(), CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--stats] [--render DIR]`. (+11 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.02
Nodes (152): admission_met(), admission_tasks_done(), _alliance_key(), alliance_standing(), apply_join_standing(), apply_resign_standing(), attitude_offset(), base_owner_hostile() (+144 more)

### Community 123 - "Community 123"
Cohesion: 0.17
Nodes (17): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.14
Nodes (23): concourse_asset(), Path, Text, Static Stardock service raster selection and ANSI rendering.  The source artwork, Return the tab, theme, and layout-specific crop., Render a responsive service panel: 72×12 wide, 56×8 standard., Compatibility wrapper for the original PT-06 asset tests., Compatibility wrapper for the original PT-06 renderer. (+15 more)

### Community 125 - "Community 125"
Cohesion: 0.16
Nodes (12): fractal_noise(), OpenSimplex, Shared procedural-noise helpers for the art generators., Sum several octaves of noise so clusters break up at multiple scales.      Layer, Random, Text, Procedural starfield generation., Per-subtype knobs turning the noise field into stars.      threshold  - noise cu (+4 more)

### Community 126 - "test_ui_black_hole.py"
Cohesion: 0.20
Nodes (20): _move_cost(), _passable_components(), Entry cost on foot; 0 == impassable (hard terrain or settlement masonry)., Label the 4-connected passable regions; return (labels, sizes).      Sites and t, _disc(), _planet_with_hidden_and_obvious(), GW-WP05 — survey generation from real universe discoveries (GW plan §GW-M2).  Tw, _survey() (+12 more)

### Community 127 - "Community 127"
Cohesion: 0.23
Nodes (13): FindKind, Random, Shared archaeological find identities promoted from the groundwar POC.  The prod, Draw one POC-style archaeological proper name., Stable POC art/name subtype for a compatible production surface kind., Stable POC name for a compatible existing surface discovery., site_name(), surface_find_kind() (+5 more)

### Community 128 - "Community 128"
Cohesion: 0.14
Nodes (22): CitadelError, Exception, A citadel build/treasury operation was rejected (raised by the reducers)., WP54 — citadels: levels, treasury, timed builds, the planetary gun (DESIGN §4.2,, A single owned colony in the player's sector (no port), ready to fortify., test_build_citadel_pays_up_front_and_opens_a_build(), test_build_rejects_too_few_colonists_or_equipment_or_latinum(), test_build_stalls_without_colonists() (+14 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.25
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 131 - "Community 131"
Cohesion: 0.10
Nodes (19): DeployShip, main(), _make_starfield(), `edge-spacebattle` — the space-battle POC's Textual shell.  Throwaway UI (the `t, A static char-level starfield backdrop with dim placement-grid ticks., One fleet slot during deployment — a hull awaiting a cell and a facing., SpacebattleApp, `python -m edge.spacebattle` / `edge-spacebattle` entry point. (+11 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.29
Nodes (3): CorpDTO, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The player's corporation for the `T` screen — roster, bank, holdings, wars (§4,

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "EngineRoomDTO"
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 138 - "main"
Cohesion: 0.16
Nodes (6): Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, SurveyExpeditionDTO, The active survey's fog-safe viewport, or ``None`` while in orbit (GW-WP07)., Text, Build the immutable viewport once; cursor moves only restyle a copied cell., Drop expired flashes and return what is still lit.

### Community 139 - "MarketDTO"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.08
Nodes (9): A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, RouteDTO, _assert_impl(), Command, EncounterDTO, Event, Protocol, The typed surface of the in-process game service (H16). (+1 more)

### Community 142 - "TopologyModeConfig"
Cohesion: 0.22
Nodes (13): _noncore(), WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., The projection greys FIGHT with the very string the reducer raises (lockstep)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage(), test_attack_blocked_in_the_core_sanctuary(), test_attack_on_a_noncombatant_is_pointless(), test_attack_on_an_influence_gate_species_is_stayed() (+5 more)

### Community 143 - "Community 143"
Cohesion: 0.09
Nodes (10): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, GroundwarApp, HelpScreen, Pressed, Screen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., Mode / planet / seed pickers; platoon composer (assault) or world toggle     (ex (+2 more)

### Community 144 - "trader_step"
Cohesion: 0.04
Nodes (88): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+80 more)

### Community 145 - "test_genesis.py"
Cohesion: 0.29
Nodes (3): MessagesDTO, The messages & log view, projected from the durable event_log (§12)., The durable event log, newest first (§11, §12).

### Community 146 - "test_intel_contact.py"
Cohesion: 0.50
Nodes (4): CorpMemberDTO, One member row on the corp screen (§4, WP66)., corp_view(), The player's corporation for the `T` screen — roster, bank, holdings, wars (§4,

### Community 147 - "Community 147"
Cohesion: 0.22
Nodes (10): _deterministic_color_env(), _isolated_save_dir(), Any, MonkeyPatch, Path, Shared pytest fixtures., Point the TUI save slot at a per-test scratch dir.      `EdgeApp.start_new_game`, Pin terminal color detection so snapshot captures are machine-independent. (+2 more)

### Community 148 - "Community 148"
Cohesion: 0.31
Nodes (10): _color(), _contrast(), _luminance(), WP-UI03 — numerical WCAG contrast gates for every supported semantic theme., WCAG 2 relative luminance for a six-digit sRGB hex color., Normal and muted semantic text stays at or above 4.5:1 on every theme surface., Focus, selection, and disabled-state indicators remain at least 3:1 on all surfa, test_control_indicators_meet_contrast_floor() (+2 more)

### Community 149 - "Community 149"
Cohesion: 0.36
Nodes (9): CaptureFixture, MonkeyPatch, Path, WP9 — the `python -m edge.bigbang` CLI inspector (DESIGN §5)., test_default_prints_summary(), test_dump_json_writes_payload(), test_no_arguments_prints_stats(), test_render_web_writes_page() (+1 more)

### Community 150 - "Community 150"
Cohesion: 0.33
Nodes (9): Trading Enjoyability Plan 01 — the Travelogue, Trading Enjoyability Plan 02 — the competing plan (Dynamic Market), Legibility / Volatility / Graduation levers, Trading Enjoyability Plan 03 — Interactive & Environmental Trade, Cargo mass dynamics, Trading Enjoyability Plan 04 — Preparation and Place-Making, Deterministic port profile, Trade-route travelogue (+1 more)

### Community 151 - "Community 151"
Cohesion: 0.20
Nodes (5): Tests for the procedural discovery sprites (``edge/art/discovery.py``).  The fou, A surface scene is painted edge to edge (sky/ground backgrounds + a     structur, Both the fixed-fallback accent (no archetype) and the archetype-tinted     accen, test_archetype_tint_path_renders(), test_surface_scene_is_not_blank()

### Community 152 - "Community 152"
Cohesion: 0.25
Nodes (9): Project Instructions (AGENTS.md), CLAUDE.md (includes AGENTS.md), Procedural ASCII art generation (edge.art), Command to Event reducer flow, DESIGN.md (authoritative spec), Fog of war at to_public() boundary, Layered downward-only architecture, Seeded reproducibility from (seed, command log) (+1 more)

### Community 153 - "Community 153"
Cohesion: 0.13
Nodes (15): DESIGN.md (authoritative spec), Phase 1 — Walking Skeleton plan, WP4 — big bang gen/validate (M2), WP2 — economy (property-tested, M1), The 'first upgrade' decision (config-driven flat aspect), WP5 — SQLite store + golden-master replay (M3), UI Inspiration Board, Edge of the Unknown — TUI Mockups (+7 more)

### Community 154 - "Community 154"
Cohesion: 0.50
Nodes (3): pick_subsystem(), Engine-room subsystem icons for the TUI (UI_MOCKUPS.md §8).  The procedural `edg, The decorative ASCII icon for an engine-room subsystem (§8).

### Community 155 - "market_view"
Cohesion: 0.32
Nodes (12): WP57 — favors + escort contracts (DESIGN §6.7, §14).  The contract system is pur, Sectors 1-2-3 with a fuel-ore-buying port in sector 2, player + ship in sector 1, _ship(), _sp(), test_abandon_fails_contract(), test_deadline_expiry_on_daily_cron(), test_deliver_rejected_without_cargo_or_at_wrong_port(), test_destroy_completes_on_kill() (+4 more)

### Community 156 - ".compose"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 158 - "StaticGenerator"
Cohesion: 0.31
Nodes (6): Random, Text, Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.  Un, Generates a frame of random low-contrast static ("snow")., Fill a `width` × `height` frame with weighted random noise glyphs.          `sub, StaticGenerator

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 162 - "ComputerDTO"
Cohesion: 0.19
Nodes (13): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, One sector on the nav-rose trail breadcrumb (§11): its spatial id and distance, TrailCrumb, WarpDTO, Nav-rose widget presentation (WP-PR2-07 / PT-48, PT-55).  `NavRose` bakes two cl, _rose() (+5 more)

### Community 163 - "TavernDTO"
Cohesion: 0.24
Nodes (9): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), test_every_archetype_has_responsive_service_art() (+1 more)

### Community 165 - ".apply"
Cohesion: 0.15
Nodes (5): PlaytestControls, Click, ComposeResult, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 172 - "_SpriteCard"
Cohesion: 0.29
Nodes (5): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard

### Community 174 - "Community 174"
Cohesion: 0.40
Nodes (4): Debris, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, Scatter drifting-wreckage clumps across the midfield (graveyard     scenarios) —, seed_debris()

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

## Knowledge Gaps
- **55 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script` (+50 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Community 128`, `Community 129`, `Screens, DTOs & Remote Play`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `EngineRoomDTO`, `Community 141`, `Dialogue-Pack Save Guard`, `Community 143`, `Universe Embedding & Bearings`, `trader_step`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Dialogue Authoring Pipeline`, `market_view`, `Core Governance & Seizure`, `Core-Seizure Confirm Screens`, `Spacebattle Battle Screen`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Community 42`, `Community 45`, `Community 46`, `Community 48`, `Community 49`, `Community 61`, `Community 68`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 79`, `Community 83`, `Community 85`, `Community 86`, `Community 92`, `Community 94`, `Community 98`, `Community 108`, `Community 110`, `Community 111`, `Community 114`, `Community 117`, `Community 121`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 42` to `Community 128`, `Core Rules & Events Engine`, `Sector Scene & Widgets`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Planet & Orbit Views`, `Community 141`, `trader_step`, `Universe Embedding & Bearings`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `The Entity & Command Reduce`, `test_intel_contact.py`, `Market Orders & Regions`, `Config Schema Models`, `Community 147`, `Dialogue Authoring Pipeline`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Ticker`, `Core-Seizure Confirm Screens`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `.apply`, `Config Loading & Sidecar Merge`, `Community 43`, `Community 45`, `Community 49`, `Community 54`, `Community 61`, `Community 71`, `Community 73`, `Community 75`, `Community 77`, `Community 85`, `Community 86`, `Community 92`, `Community 96`, `Community 98`, `Community 103`, `Community 111`, `Community 114`, `Community 119`, `Community 121`, `test_ui_black_hole.py`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Community 42` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Community 128`, `Standing, Corp & Combat Rules`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Community 141`, `TopologyModeConfig`, `trader_step`, `Universe Embedding & Bearings`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `The Entity & Command Reduce`, `test_intel_contact.py`, `Signature Mechanics`, `Dialogue Authoring Pipeline`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `market_view`, `Core-Seizure Confirm Screens`, `.rebuild_adjacency`, `.state`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `Community 45`, `Community 48`, `Community 49`, `Community 61`, `Community 69`, `Community 70`, `Community 73`, `Community 74`, `Community 75`, `Community 77`, `Community 85`, `Community 86`, `Community 92`, `Community 94`, `Community 96`, `Community 98`, `Community 103`, `Community 108`, `Community 111`, `Community 114`, `Community 118`, `Community 119`, `Community 121`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 133 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 133 INFERRED edges - model-reasoned connections that need verification._
- **Are the 339 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 339 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._