# Graph Report - edge-of-the-unknown  (2026-07-21)

## Corpus Check
- 344 files · ~9,191,248 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8612 nodes · 39177 edges · 194 communities (170 shown, 24 thin omitted)
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 13472 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `821bc0cd`
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
- test_intel_contact.py
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- market_view
- .compose
- Ticker
- StaticGenerator
- Community 160
- .state
- TavernDTO
- Community 166
- Community 169
- Community 170
- _SpriteCard
- Community 174
- Community 175
- landing_sites
- LiveSysopService
- _entity_world
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
1. `UniverseState` - 572 edges
2. `GameConfig` - 550 edges
3. `Commodity` - 451 edges
4. `reduce()` - 414 edges
5. `EconomyError` - 372 edges
6. `EdgeApp` - 267 edges
7. `Warp` - 247 edges
8. `ComponentTier` - 245 edges
9. `apply_result()` - 243 edges
10. `Event` - 236 edges

## Surprising Connections (you probably didn't know these)
- `test_width_grows_monotonically_and_respects_bounds()` --calls--> `compose_horizontal()`  [EXTRACTED]
  tests/test_ship_art.py → edge/art/hull.py
- `test_every_live_band_has_a_contact()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_placement_is_seeded_and_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_roster_alliances_become_entities()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_species_knowledge_is_deterministic_bounded_and_referential()` --calls--> `generate()`  [EXTRACTED]
  tests/test_dialogue_intel.py → edge/bigbang/generator.py

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

## Communities (194 total, 24 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.09
Nodes (482): _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup() (+474 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.05
Nodes (71): is_colonizable(), Whether a world of this type can be claimed and settled (§4.2).      Colonizable, range, generate_with_player(), Any, `generate()` then `enroll()` — the common "fresh game with player 1" setup., WP27: logging a find into the codex pays experience_per_discovery., WP27 Core-law basics: a criminal crossing into the Core is put on notice, once (+63 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.01
Nodes (196): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SceneArtConfig, ArmamentItem, Aspect, BarracksItem, BountyDTO (+188 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.12
Nodes (34): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A `subsystems=None` (NPC-style) hull has no engine room to operate on. (+26 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.09
Nodes (10): Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, Carried territory stock + devices for the Deploy screen (§10/§14, WP72)., Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)., ComposeResult, Pressed, Vertical, What already sits in this sector, tabular (fog pre-applied upstream). (+2 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.02
Nodes (209): admission_met(), admission_tasks_done(), base_owner_hostile(), core_status(), disposition_band(), Name the band a disposition value falls in (hostile / neutral / friendly, §6)., The admission tasks the player has completed for a bloc (the §6.3 ledger)., Whether the player has completed the bloc's `admission_price` tasks (§6.3). (+201 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.20
Nodes (22): build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., _phantom_bridges(), Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic., Pairs of *non-adjacent* sectors joined on one row by an unbroken, arm-connected, A small branching universe:  1 - 2 - 3 - 4  with a 2 - 5 - 6 spur.      Core hop, _rows(), _strip() (+14 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.06
Nodes (77): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random, Ship (+69 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.04
Nodes (56): The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_engine_room(), sample_planet(), sample_surface() (+48 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.04
Nodes (58): EngineRoomDTO, One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).      `s, One subsystem panel: its derived aspect and its slot grid (§4.1)., The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)., Slot, Subsystem, ContextStrip, EmptyState (+50 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.09
Nodes (36): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar (+28 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.10
Nodes (17): AmountPrompt, FieldPrompt, Pressed, Submitted, The shared one-field prompt: inline validation, no silent failures.      Subclas, Return (value, None) to accept or (None, reason) to hold the form open., A positive-integer prompt (latinum amounts, quantities)., InputType (+9 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.04
Nodes (57): TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), Any, Screen, EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Persist local-only presentation settings and apply the theme immediately., Tick off a Captain's objective (WP-UI11) — local progress only.          Called (+49 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.07
Nodes (55): _add_structure(), apply_militia_recovery(), assault_map_for(), AssaultCity, AssaultDifficulty, AssaultMap, AssaultStructure, derive_difficulty() (+47 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.03
Nodes (113): _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7). (+105 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.04
Nodes (130): apply_result(), Command, Upsert a reducer's new entities into the mutable container (sanctioned)., Validate `command` for `player_id` and return its delta + events., reduce(), instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., Command (+122 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.02
Nodes (163): The big bang: deterministic universe generation from (seed, config) (DESIGN §5)., A text report of a generated universe (the `--stats` dev view, §5)., summarize(), _can_hold_a_people(), _Cast, ground_target_counts(), _guarantee_targets(), _inhabitant() (+155 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.02
Nodes (246): Resolve a `--route` endpoint token to an internal sector id.      Accepts an int, resolve_sector(), AllianceConfig, EngineRoomConfig, One alliance / rival bloc in the roster (DESIGN §6.3).      Joinability (WP38):, A Core-seizure ladder is meaningful only on a `covets_core` bloc (§6.3, WP50)., One subsystem's slot layout for a hull (DESIGN §4.1).      `slot_count` fixed sl, Game-global engine-room tunables (DESIGN §4.1).      The per-subsystem layouts l (+238 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.12
Nodes (44): Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), A remote rules rejection compatible with every local rule-error catch.      JSON, RemoteError, RemoteRulesError, A stable hash of the protocol surface — client and server refuse a mismatch at h, wire_fingerprint(), Hosted denials follow the same warning-toast paths as embedded denials. (+36 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.02
Nodes (136): ActiveBinding, AmountPrompt, Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, GameService, EncounterDTO, Event, The in-process game service (DESIGN §3).  `GameService` owns the authoritative `, Persisted events after `seq`, each with its seq — the reconnect catch-up buffer (+128 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.02
Nodes (133): BaseModel, building(), citadel_defense_mult(), conquer(), InvasionOutcome, level_config(), _levels(), open_build() (+125 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.05
Nodes (73): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+65 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.10
Nodes (23): flip_row(), Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Slot, The authored row-height of a ship grammar tier (all parts share it)., Pick the tallest tier whose authored height fits ``height``; falls back to     t, _select_grammar(), _tier_height(), _all_glyphs() (+15 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.03
Nodes (71): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed (+63 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.14
Nodes (44): ground_access(), OrbitalOnly, Classify how the player may interact with `planet` from orbit (GW plan §contract, This world is only ever interacted with from orbit (no ground operation).      A, GroundAccess, The case that could not be written before this WP without hand-building state., test_a_real_generated_world_routes_to_assault(), _owned_reinforceable_state() (+36 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.06
Nodes (82): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, Path, SqliteRepository, A deterministic fingerprint of the live entity state (RNG/adjacency excluded)., state_hash() (+74 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.08
Nodes (18): The descended-planet view: terrain + the planet's surface sites (§7, WP6)., SurfaceDTO, The descended-planet surface view: terrain + sites (§7, WP6)., Any, ComposeResult, Pressed, RowHighlighted, Static (+10 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.11
Nodes (22): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+14 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (33): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+25 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.12
Nodes (15): build_graph(), Random, Trunk topology builder (DESIGN §5)., `trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra, Base class for all topology builders (DESIGN §5)., Build the warp graph and return its adjacency plus the region groups., TopologyMode, TrunkTopology (+7 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.14
Nodes (33): DrawFn, generate_orders(), match_orders(), MatchFill, Post every port's open orders from `state.ports` (see `orders_from_ports`)., Match the book and return the conserving inter-port settlement (§8).      Per co, One settled match — the event-log record of goods and latinum moving., Latinum moved buyer → seller, in slips. (+25 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.07
Nodes (49): apply_patch_lines(), build_parser(), _build_patch(), cmd_list(), cmd_show(), _components(), _diff_after(), dispatch() (+41 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.13
Nodes (38): _do(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., A hunted player is turned away at the Core Stardock; others dock freely (WP52)., Place an unowned colonizable world in the player's sector (2)., GW-WP09/D11: SetAllocation's `garrison` share joins the trio + `fighter` in the, Sectors 1<->2; a Stardock (sells all) sits in sector 2 with the player., test_bank_deposit_then_withdraw(), test_buy_component_costs_latinum_and_fills_a_hold() (+30 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.07
Nodes (28): BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Pressed, Submitted, The LLM pilot's console — a Textual app watching and steering the brain (dev-onl (+20 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.08
Nodes (39): load_default_config(), _merge_dialogue(), Any, Load the bundled default config (`config/default.yaml`)., Fold one dialogue document onto a roster dict in place (DESIGN §6.7).      Two s, Any, Validate an already-parsed mapping (e.g. from YAML) into a GameConfig., test_config_roundtrips_with_roster() (+31 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.06
Nodes (40): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., BaseScreen, ComposeResult, Static, Vertical (+32 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.16
Nodes (21): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), generate_find_art(), _pit() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.03
Nodes (208): EconomyError, Exception, An illegal economic action (insufficient funds/goods/stock/holds)., Corporation, A player corporation (DESIGN §4, WP66) — shared bank + assets + corp war.      A, _abandon_contract(), _accept_contract(), _accept_corp_invite() (+200 more)

### Community 43 - "Community 43"
Cohesion: 0.04
Nodes (49): BotSetup, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, BotRunner, Command, Event, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69)., Drives one player of a game through the `ServiceProtocol` seam (dev-tier, WP60). (+41 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (32): A correction clears stale validation copy and restores stable form layout., Changed, CountColumn, CountItem, CountSelector, Dropped, options_from_suits(), PlatoonComposer (+24 more)

### Community 45 - "Community 45"
Cohesion: 0.04
Nodes (53): ABC, BaseException, CronFn, CronResolver, list_items(), Render one category of populated universe items as an id-keyed table., _check_config_version(), _load_save() (+45 more)

### Community 46 - "Community 46"
Cohesion: 0.10
Nodes (29): _footer_keys(), _open_computer(), PT-32 — the Computer's keyboard model: a tab owns its keys.  The screen binds on, chrome.EdgeScreen pins Back first — it used to fall in behind whatever the     f, PT-51: `P` on the Map plots a course to the highlighted sector and lands on the, Each category pane owns 1..N for its own sub-tabs — so `2` means a different tab, The corporation lives under Relations now, not behind a game-screen hotkey., Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+21 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (21): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), AlienContactScreen, ComposeResult, Widget, Re-fetch the view and repaint the conversation **in place** (§6.7).          `pi, Land focus on the new menu — the old reply rows were just removed under it., The reply menu — the one thing that really changes between nodes.          Share (+13 more)

### Community 48 - "Community 48"
Cohesion: 0.03
Nodes (123): DataObject, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., _force_settlement(), Run one order-book settlement now (WP59 sysop op) — a logged, replayable market, accrue_interest(), deposit() (+115 more)

### Community 49 - "Community 49"
Cohesion: 0.04
Nodes (113): advance_build(), has_gun(), Whether `planet` fields an operational citadel gun (§4.2, WP54/WP55)., Whether the L3 siege shield bars invasion of `planet` (§4.2, WP55).      True wh, Advance an open build by one production tick, returning `(planet, completed)`., siege_shielded(), assault_blockers(), _friendly() (+105 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (41): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+33 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.02
Nodes (199): EdgeApp, Resize, The synchronous game surface the screens read (WP61/WP68).          Single-playe, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)., Tear down the remote loop/thread on exit (WP68)., Open contextual help for the current screen (`?` anywhere). (+191 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (34): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+26 more)

### Community 54 - "Community 54"
Cohesion: 0.06
Nodes (14): main(), PlaytestControls, PlaytestService, Click, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR (+6 more)

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (23): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, A hostile kill pays its bounty now and leaves its salvage in a visible wreck. (+15 more)

### Community 56 - "Community 56"
Cohesion: 0.18
Nodes (22): eligible_surface_site_ids(), _move_cost(), _passable_components(), Entry cost on foot; 0 == impassable (hard terrain or settlement masonry)., Label the 4-connected passable regions; return (labels, sizes).      Sites and t, The surface discoveries a survey of `planet_id` can resolve *now* (G7 snapshot)., _disc(), _planet_with_hidden_and_obvious() (+14 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (56): compose_horizontal(), HullStyle, Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Palette for a hull: three shading levels, the navigation-beacon hue pools     (a, Resolve an ``archetype_id`` to its palette, falling back to Federation grey. (+48 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (42): Procedural ASCII art generation logic., cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text (+34 more)

### Community 59 - "Community 59"
Cohesion: 0.05
Nodes (39): Container, GroundCellDTO, One sensor contact, masked until excavation settles the real discovery (G6/G7)., Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, SurveyContactDTO, SurveyExpeditionDTO, The active survey's fog-safe viewport, or ``None`` while in orbit (GW-WP07). (+31 more)

### Community 60 - "Community 60"
Cohesion: 0.05
Nodes (43): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl (+35 more)

### Community 61 - "Community 61"
Cohesion: 0.03
Nodes (28): _decode_any(), LinkLost, LocalClient, Any, Command, EncounterDTO, Event, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met (+20 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (15): HelpScreen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key (+7 more)

### Community 63 - "Community 63"
Cohesion: 0.09
Nodes (22): main(), `edge-groundwar` — the ground-war POC's Textual shell.  Throwaway UI (the `tui`-, Groundwar POC config — a thin adapter over the production schema (GW-WP02).  Bal, `python -m edge.groundwar` / `edge-groundwar` entry point., _add_structure(), _footprint_passable_frac(), generate_battle(), Battle (+14 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (42): Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus() (+34 more)

### Community 65 - "Community 65"
Cohesion: 0.03
Nodes (113): _alliance_key(), apply_join_standing(), apply_resign_standing(), apply_spillover(), attitude_locked(), _clamp01(), core_bases_razed(), is_criminal() (+105 more)

### Community 66 - "Community 66"
Cohesion: 0.06
Nodes (33): apply_patch(), Apply (or, in dry-run, preview) a DevPatch and report what changed., config_dump(), _intervene(), _lobby_hint(), main(), menu(), _print() (+25 more)

### Community 67 - "Community 67"
Cohesion: 0.12
Nodes (7): ContactDTO, One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, A peaceful alien contact screen (§6, §6.7, §11)., TechOfferDTO, The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any.

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.14
Nodes (24): _band(), _discoveries(), format_route(), _num(), _owner(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers). (+16 more)

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (35): owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, _force(), _make_hostile(), _mini_state(), WP41 — sector fighters, mines, beacons, black-hole hazards (§10).  Covers the pu, A lethal hazard routes through the WP26 escape pod (WP75 — the A5 seam closed)., Armid is the WP41 mine renamed — same entry damage, spent on detonation. (+27 more)

### Community 71 - "Community 71"
Cohesion: 0.07
Nodes (38): Color, available_archetypes(), available_subtypes(), Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype(), Style (+30 more)

### Community 72 - "Community 72"
Cohesion: 0.05
Nodes (47): Merge a generated dialogue sidecar onto the default roster and run §13 integrity, validate_sidecar(), AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json() (+39 more)

### Community 73 - "Community 73"
Cohesion: 0.18
Nodes (9): _cluster_groups(), Dense concentric rings numbered outward from sector 1.      Sector 1 has ``max_w, Partition sequential IDs into rings of size ``cap * radius``., Add increasingly long ring chords until endpoints reach the warp cap.          S, Replace eligible two-way chords with paired, distant one-way exits.          The, Choose a non-Core, genuinely one-way destination far along the spiral., Cache an exact concentric layout for the inspector and nav bearings., Partition `sectors` into contiguous groups of size [cluster_min, cluster_max]. (+1 more)

### Community 74 - "Community 74"
Cohesion: 0.18
Nodes (19): decay_grudges(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called., accept(), is_convoyed(), Stamp an offered contract into an active one on the player's slate (WP57)., Whether a species instance is under escort by any player (§6.7, WP57).      A co, daily_turn_reset(), Refill every player's turns and advance the game day (TWINSTR.DOC, §9).      Als (+11 more)

### Community 75 - "Community 75"
Cohesion: 0.09
Nodes (54): GwSuit, A purchasable powered-armour suit class (GW plan D3)., apply_casualties(), apply_reinforcement(), berths_free(), berths_used(), clamp_magazine(), groundwar_config() (+46 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (18): Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Deployed forces as glyph-scale presence marks — fighters flying patrol         t (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.05
Nodes (49): CitadelError, Exception, A citadel build/treasury operation was rejected (raised by the reducers)., _clamp_ship_field(), DevPatchError, Exception, Ship, Field-specific validation for a ship integer set/add (raises on hard limits). (+41 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (14): Battle, Event, Side, One cell of rocky debris (belt scenarios). Blocks fire lines and wings;     dest, A missile salvo in flight — a board object chasing its target ship., One log/FX entry drained by the UI after each rules call., A ship (any footprint cell), wing, rock, or wreckage sits here — one         pie, Every board cell of the piece's footprint (anchored on the centre).         Ship (+6 more)

### Community 79 - "Community 79"
Cohesion: 0.10
Nodes (26): ComposeResult, Pressed, Submitted, Enter in a row's amount field submits that row in the colony-supply direction, A modal transfer editor for the player-owned world in the current sector., TransferWorkbenchScreen, _has_scrollable_ancestor(), _new_game() (+18 more)

### Community 80 - "Community 80"
Cohesion: 0.10
Nodes (25): DeployShip, main(), _make_starfield(), Battle, `edge-spacebattle` — the space-battle POC's Textual shell.  Throwaway UI (the `t, A static char-level starfield backdrop with dim placement-grid ticks., One fleet slot during deployment — a hull awaiting a cell and a facing., SpacebattleApp (+17 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (32): alien_dialogue_default.yaml (dialogue corpus), alien_dialogue_species.yaml (species grammars), alien_roster_default.yaml (species roster), default.yaml (game constants), Alien species disposition system, Alliances (rival blocs, join one at a time), Asteroid belt mining (finite reserves), Universe generation (Big Bang) (+24 more)

### Community 82 - "Community 82"
Cohesion: 0.09
Nodes (40): decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command(), encode_dto(), encode_event() (+32 more)

### Community 83 - "Community 83"
Cohesion: 0.19
Nodes (17): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), _parse_args(), Namespace (+9 more)

### Community 84 - "Community 84"
Cohesion: 0.05
Nodes (14): A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, RouteDTO, CronTask, EngineTicker, The engine tick loop (DESIGN §9).  A short tick advances a logical tick counter, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., _assert_impl() (+6 more)

### Community 85 - "Community 85"
Cohesion: 0.02
Nodes (235): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+227 more)

### Community 86 - "Community 86"
Cohesion: 0.16
Nodes (19): WP54 — citadels: levels, treasury, timed builds, the planetary gun (DESIGN §4.2,, A single owned colony in the player's sector (no port), ready to fortify., test_build_citadel_pays_up_front_and_opens_a_build(), test_build_rejects_too_few_colonists_or_equipment_or_latinum(), test_build_stalls_without_colonists(), test_cannot_invade_a_core_world(), test_citadel_foe_derives_from_config(), test_garrison_production_mints_fighters() (+11 more)

### Community 87 - "Community 87"
Cohesion: 0.08
Nodes (28): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+20 more)

### Community 88 - "Community 88"
Cohesion: 0.17
Nodes (20): InstalledComponent, One component slotted into a subsystem (DESIGN §4.1).      `knocked_out` is set, Filled, non-knocked-out components (the ones the aspect formula counts)., _check_slot(), _engine_ship(), _field_patch(), _install_component(), _inv_add() (+12 more)

### Community 89 - "Community 89"
Cohesion: 0.17
Nodes (7): ClusteredTopology, OutEdges, Wire one group: a random spanning tree, then edges toward avg degree ~2.5., `expansive` bridging (§5 step 2): a band-lattice web with no chokepoints., `planar` bridging: connects clusters using a planar spiderweb meta-graph., Build the topology and return the region groups (the Core is group 0)., Base class for topologies built by clustering and bridging groups.

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (29): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+21 more)

### Community 91 - "Community 91"
Cohesion: 0.14
Nodes (15): Lead, A coordinate tip the player accepted from an alien (DESIGN §6.7, the "map" mecha, _line_universe(), Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal, test_movement_errors_name_the_spatial_id_not_the_internal_one() (+7 more)

### Community 92 - "Community 92"
Cohesion: 0.25
Nodes (9): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+1 more)

### Community 93 - "Community 93"
Cohesion: 0.21
Nodes (18): list_portraits(), portraits_dir(), Path, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait(), The face the current species is wearing, and how many it has to choose from (PT- (+10 more)

### Community 94 - "Community 94"
Cohesion: 0.22
Nodes (17): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., _inputs() (+9 more)

### Community 95 - "Community 95"
Cohesion: 0.02
Nodes (83): AllianceRowDTO, LocalMapDTO, One traversed sector on a plotted route — what the player reads (§11, WP14)., One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, RouteHopDTO, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map() (+75 more)

### Community 96 - "Community 96"
Cohesion: 0.07
Nodes (58): _build_site(), _cell_cost(), dig_trench(), _dist(), generate_survey(), _in_bounds(), is_landing_site(), _keepout() (+50 more)

### Community 97 - "Community 97"
Cohesion: 0.06
Nodes (21): Any, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade (+13 more)

### Community 98 - "Community 98"
Cohesion: 0.07
Nodes (66): accrue_interest(), alien_drift(), market_settlement(), _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16)., Run one trade for every NPC merchant working a port this firing (§8, WP43)., Compound interest on every non-empty bank balance (§8). (+58 more)

### Community 99 - "Community 99"
Cohesion: 0.15
Nodes (23): Binding, _action_name(), _all_actions(), _bindings(), _method_source(), _pane_bindings(), Screen, WP-UI05/WP-UI06 — responsive shell and unified action discovery.  Static collisi (+15 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.20
Nodes (5): Open the numbered context-action menu over the current screen (WP73, D3)., ActionMenuScreen, Any, ComposeResult, Screen

### Community 103 - "Community 103"
Cohesion: 0.06
Nodes (51): build_subsystems(), legal_components(), Subsystem, The components installable into `subsystem` on this hull (config layout)., Instantiate a hull's starting subsystems from its config layout (§4.1).      Ret, Discovery, A thing the big bang salted into the universe to be found (DESIGN §4, §7)., Sector-deployed fighters + mines holding a sector (DESIGN §10, WP41) — hashed st (+43 more)

### Community 104 - "Community 104"
Cohesion: 0.18
Nodes (18): Adjacency, can_warp(), plan_route(), plan_route_legs(), Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For, The sectors reachable in one hop from `sector_id`., Whether a single direct warp `from_sector -> to_sector` is legal. (+10 more)

### Community 105 - "Community 105"
Cohesion: 0.17
Nodes (25): build_nav_strip(), _nearest_free(), _octant(), The main-screen nav rose — a bearing-placed compass of immediate warps (§11).  B, Snap a bearing (radians, 0 = east, +y = north) to one of 8 compass octants., The preferred octant, or the closest free one (deterministic +d before -d)., The cell text: spatial id plus content codes once charted (fog masks codes)., Band tint for a charted warp; dim for an uncharted one (matches the local map). (+17 more)

### Community 106 - "Community 106"
Cohesion: 0.10
Nodes (14): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., first_focusable(), focus_content(), TabActivated, Widget, The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target)., Put keyboard focus on `node`'s primary control (see `first_focusable`).      Whe (+6 more)

### Community 107 - "Community 107"
Cohesion: 0.23
Nodes (14): WP-PR07 — settling more colonists onto an already-owned colony (playtest PT-11)., Every `TransferCargo` moves goods between ship holds and colony stores without, An owned colony with stores + a ship with cargo and free holds, same sector., _state(), test_batch_load_is_one_delta_and_shares_free_holds(), test_invalid_batch_is_atomic(), test_settle_clamps_to_aboard_and_habitability(), test_settle_rejected_on_uncolonizable_world() (+6 more)

### Community 108 - "Community 108"
Cohesion: 0.13
Nodes (34): combat_contexts(), DialogueIntegrityError, Exception, Convenience: select a line for a live encounter and return (text, new recency ri, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3, Assert the §13 dialogue-integrity invariants for a roster (raises on failure)., A roster's dialogue packs fail the §13 integrity checks. (+26 more)

### Community 109 - "Community 109"
Cohesion: 0.18
Nodes (8): Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait., Render a species' portrait image (by `roster_id`) into its allotted cell box., SpeciesPortrait, PT-42 — the art panel must not reset on every dialogue step.      A reply used t, test_a_reply_repaints_the_menu_without_rebuilding_the_portrait()

### Community 110 - "Community 110"
Cohesion: 0.22
Nodes (13): _noncore(), WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., The projection greys FIGHT with the very string the reducer raises (lockstep)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage(), test_attack_blocked_in_the_core_sanctuary(), test_attack_on_a_noncombatant_is_pointless(), test_attack_on_an_influence_gate_species_is_stayed() (+5 more)

### Community 111 - "Community 111"
Cohesion: 0.05
Nodes (67): load_config(), load_config_with_sidecar(), Path, Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Build a `GameConfig` with `sidecar` spliced onto the default roster (no integrit, Load and validate a YAML game config from `path`.      A `roster_file:` pointer, AliensConfig, Disposition thresholds + escape floor for the alien system (DESIGN §6, §10). (+59 more)

### Community 112 - "Community 112"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 113 - "Community 113"
Cohesion: 0.07
Nodes (67): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line() (+59 more)

### Community 114 - "Community 114"
Cohesion: 0.42
Nodes (10): _config(), Path, WP61 — the async `GameClient` facade over the in-process service (DESIGN §3/§14), _service(), test_apply_mutates_and_fans_events(), test_apply_rejection_propagates(), test_events_stream_yields_apply_results(), test_game_view_matches_service() (+2 more)

### Community 115 - "Community 115"
Cohesion: 0.03
Nodes (66): Text, What an art panel drew last time, so a rebuilt screen doesn't blink (PT-42).  Se, The art this panel drew last time, or None if it has never been drawn., Record `art` as this panel's latest render and hand it back for painting., remember(), remembered(), layout_tier(), clear_slot() (+58 more)

### Community 116 - "Community 116"
Cohesion: 0.14
Nodes (13): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+5 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.14
Nodes (21): belt_mining_yield(), The commodity + amount one mining action pulls from a belt (§4.2, PT-30/PT-52)., WP-PR06 — asteroid belts are spatial features, not colony worlds (playtest PT-30, A belt still hosts spatial finds (its sector's discoveries), just not landable s, Every belt is born with ore in it, and the deep fields are the rich ones., _state_with_belt(), test_a_haul_is_clamped_to_the_ore_actually_left(), test_a_worked_out_belt_rejects_and_projects_no_haul() (+13 more)

### Community 119 - "Community 119"
Cohesion: 0.24
Nodes (20): _begin(), _land(), _op(), GW-WP06 — authoritative survey actions, persistence, and reward settlement.  Dri, Set the shuttle down on the generated landing zone (GW-WP07-FU2).      Choosing, March until the explorer stands on `site` (marches halt early, so loop)., Teleport a player's explorer onto `(x, y)` — isolates dig/talk from march distan, _stand_on() (+12 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.31
Nodes (8): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., ModuleType

### Community 123 - "Community 123"
Cohesion: 0.17
Nodes (17): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.09
Nodes (33): concourse_asset(), Path, Text, Static Stardock service raster selection and ANSI rendering.  The source artwork, Return the tab, theme, and layout-specific crop., Render a responsive service panel: 72×12 wide, 56×8 standard., Compatibility wrapper for the original PT-06 asset tests., Compatibility wrapper for the original PT-06 renderer. (+25 more)

### Community 125 - "Community 125"
Cohesion: 0.16
Nodes (12): fractal_noise(), OpenSimplex, Shared procedural-noise helpers for the art generators., Sum several octaves of noise so clusters break up at multiple scales.      Layer, Random, Text, Procedural starfield generation., Per-subtype knobs turning the noise field into stars.      threshold  - noise cu (+4 more)

### Community 126 - "test_ui_black_hole.py"
Cohesion: 0.22
Nodes (6): DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12)., The save was made with a different dialogue pack; replay would fail mid-way., EngineState, The persisted ticker schedule (WP12): the tick counter + each cron's next-due ti

### Community 127 - "Community 127"
Cohesion: 0.29
Nodes (8): apply_derived(), Ship, Return `ship` with its stored aspect scalars refreshed from its subsystems., A knocked-out part contributes nothing until it is patched (§4.1)., test_knocked_out_component_does_not_count(), Give the docked ship the starter engine room (so install/derive applies)., test_repair_at_dock_restores_knocked_out_for_latinum(), _with_engine_room()

### Community 128 - "Community 128"
Cohesion: 0.17
Nodes (15): Wire one group internally as a planar outer-planar graph with zero crossings., Bridge the mesh clusters over grid edges: first a spanning tree across the clust, add_bidirectional(), add_directed(), add_ring_motifs(), carve_core(), compute_bands(), OutEdges (+7 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.16
Nodes (16): _dim(), _feature_colors(), _hex(), The band's authored (fg, bg) for a feature name — deliberately *not* yet     con, Pin a colour to concrete truecolor, so the terminal cannot theme it away.      N, A rich style whose foreground is legible against the background it actually gets, Push a colour toward black, keeping its hue., Terrain the shuttle cannot set down on, while inbound.      The same colours as (+8 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.29
Nodes (7): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "EngineRoomDTO"
Cohesion: 0.17
Nodes (12): _Coord, MeshTopology, Mesh topology builder (DESIGN §5)., Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who (+4 more)

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 137 - "LiveSysopService"
Cohesion: 0.43
Nodes (7): _first_filled(), Hang a base off a planet in the player's sector (2); return the base., test_salvage_derelict_starbase_conserves_components(), test_salvage_operational_starbase_rejected(), test_salvage_player_owned_operational_base_allowed(), test_salvage_requires_base_in_sector(), _with_starbase()

### Community 138 - "main"
Cohesion: 0.14
Nodes (16): The next unused name for `kind`. Exhausting a pool falls through to numbering., Draw a POC surface name if available and unused; fall back to kind namer., FindKind, Random, Shared archaeological find identities promoted from the groundwar POC.  The prod, Draw one POC-style archaeological proper name., Stable POC art/name subtype for a compatible production surface kind., Stable POC name for a compatible existing surface discovery. (+8 more)

### Community 139 - "MarketDTO"
Cohesion: 0.33
Nodes (6): encode_command(), Command, A (type tag, JSON-able payload) pair for a command., Command, test_command_round_trips(), test_command_codecs_round_trip()

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.50
Nodes (4): note(), note_topic(), Record that `context` was spoken this visit (`asked.<context>: true`)., The session with one fact recorded (a no-op when it already holds).

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (16): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, Battle, Pressed, Screen, One roster slot during deployment — a named trooper awaiting a landing cell. (+8 more)

### Community 146 - "test_intel_contact.py"
Cohesion: 0.30
Nodes (11): _hazard_logged(), _new_game(), _put_black_hole(), WP-PR05 — black-hole interaction never crashes (playtest note PT-28).  A black h, After entering, the black hole sits in the current sector; logging it (the     s, Drop a black hole into `sector_id`; return its discovery id., The full 2x2 acceptance matrix: mouse/keyboard x nonlethal/lethal, identical., _set_hull() (+3 more)

### Community 147 - "Community 147"
Cohesion: 0.22
Nodes (10): _deterministic_color_env(), _isolated_save_dir(), Any, MonkeyPatch, Path, Shared pytest fixtures., Point the TUI save slot at a per-test scratch dir.      `EdgeApp.start_new_game`, Pin terminal color detection so snapshot captures are machine-independent. (+2 more)

### Community 148 - "Community 148"
Cohesion: 0.31
Nodes (10): _color(), _contrast(), _luminance(), WP-UI03 — numerical WCAG contrast gates for every supported semantic theme., WCAG 2 relative luminance for a six-digit sRGB hex color., Normal and muted semantic text stays at or above 4.5:1 on every theme surface., Focus, selection, and disabled-state indicators remain at least 3:1 on all surfa, test_control_indicators_meet_contrast_floor() (+2 more)

### Community 149 - "Community 149"
Cohesion: 0.15
Nodes (31): CaptureFixture, _demo_save(), _header(), _list_output(), MonkeyPatch, Path, WP9 — the `python -m edge.bigbang` CLI inspector (DESIGN §5)., Rich pads rows to the table width; the renderer strips that so output diffs (+23 more)

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

### Community 155 - "market_view"
Cohesion: 0.25
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 156 - ".compose"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 157 - "Ticker"
Cohesion: 0.29
Nodes (3): CorpDTO, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The player's corporation for the `T` screen — roster, bank, holdings, wars (§4,

### Community 158 - "StaticGenerator"
Cohesion: 0.31
Nodes (6): Random, Text, Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.  Un, Generates a frame of random low-contrast static ("snow")., Fill a `width` × `height` frame with weighted random noise glyphs.          `sub, StaticGenerator

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 161 - ".state"
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 163 - "TavernDTO"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

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

### Community 176 - "landing_sites"
Cohesion: 0.08
Nodes (40): DialoguePack, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace, One conversational beat: its concept, extra placeholders, and Phase-2 reachabili, _branch_closure() (+32 more)

### Community 177 - "LiveSysopService"
Cohesion: 0.25
Nodes (6): LiveSysopService, Any, Event, Synchronous host-admin bridge for `edge-sysop` live hosted interventions.  The d, Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC., Apply an intervention to the authoritative live game as the target player.

### Community 178 - "_entity_world"
Cohesion: 0.50
Nodes (4): _inhabitants(), `Name (archetype)` — who they are and what kind of thing they are, in one cell., The peoples living on a world, or the empty marker for an uninhabited one., _species_label()

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

## Knowledge Gaps
- **55 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script` (+50 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Community 129`, `Screens, DTOs & Remote Play`, `Aliens & Alliance Admission`, `EngineRoomDTO`, `Planet & Orbit Views`, `Encounters & Station Archetypes`, `Domain Models & Colonizability`, `Dialogue-Pack Save Guard`, `Community 143`, `Universe Embedding & Bearings`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Core Governance & Seizure`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `.state`, `Core Rules Tests`, `Community 42`, `Community 43`, `Community 45`, `Community 48`, `Community 49`, `Community 52`, `Community 61`, `Community 65`, `Community 68`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 77`, `Community 79`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 89`, `Community 91`, `Community 95`, `Community 98`, `Community 103`, `Community 106`, `Community 107`, `Community 108`, `Community 111`, `Community 115`, `Community 117`, `Community 118`, `test_ui_black_hole.py`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 85` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `EngineRoomDTO`, `Planet & Orbit Views`, `Game Lifecycle & Pathfinding`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `Community 147`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Server Net & Engine Ticker`, `Devtool CLI & Sysop`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 43`, `Community 45`, `Community 48`, `Community 49`, `Community 54`, `Community 56`, `Community 61`, `Community 65`, `Community 71`, `Community 73`, `Community 74`, `Community 75`, `Community 77`, `Community 84`, `Community 88`, `Community 89`, `Community 96`, `Community 98`, `Community 103`, `Community 111`, `Community 118`, `test_ui_black_hole.py`, `Community 127`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `TUI Screen Widgets` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Standing, Corp & Combat Rules`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `LiveSysopService`, `Game Lifecycle & Pathfinding`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `Subsystem Layouts & Ownership`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Community 42`, `Community 43`, `Community 45`, `Community 48`, `Community 49`, `_entity_world`, `Community 56`, `Community 59`, `Community 61`, `Community 65`, `Community 69`, `Community 70`, `Community 74`, `Community 75`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 91`, `Community 96`, `Community 98`, `Community 103`, `Community 107`, `Community 108`, `Community 110`, `Community 111`, `Community 118`, `Community 119`, `Community 127`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 149 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 149 INFERRED edges - model-reasoned connections that need verification._
- **Are the 360 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 360 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._