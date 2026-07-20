# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 338 files · ~9,161,354 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8164 nodes · 35600 edges · 231 communities (177 shown, 54 thin omitted)
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 11360 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7e9bde15`
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
- GameState
- Community 160
- MessagesDTO
- ComputerDTO
- TavernDTO
- MessagesDTO
- .apply
- Community 166
- .__init__
- ComputerDTO
- Community 169
- Community 170
- TerritoryDTO
- _SpriteCard
- CommodityPricing
- Community 174
- Community 175
- .station_size
- sprites.py
- .__init__
- Community 179
- Community 180
- Community 181
- GwExpedition
- CorpConfig
- CronCadenceConfig
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
- DefenseConfig
- DeviceConfig
- EncountersConfig
- GenesisConfig
- graphify.js
- graphify.md
- graphify.md
- __init__.py
- GovernanceConfig
- GrudgeSeedConfig
- GwDefenses
- GwDifficulty
- GwPlatoon
- GwPressure
- GwResolve
- GwScannerBand
- GwTerrain
- GwWeapon
- HagglingConfig
- MarketConfig
- OwnershipWeights
- PlanetNamesConfig
- PlanetsConfig
- PlanetTypeProfile
- TickerConfig
- StarbaseConfig
- TerritoryConfig

## God Nodes (most connected - your core abstractions)
1. `UniverseState` - 521 edges
2. `GameConfig` - 474 edges
3. `Commodity` - 426 edges
4. `reduce()` - 387 edges
5. `EconomyError` - 340 edges
6. `EdgeApp` - 265 edges
7. `apply_result()` - 236 edges
8. `Warp` - 234 edges
9. `ComponentTier` - 232 edges
10. `Event` - 219 edges

## Surprising Connections (you probably didn't know these)
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_an_alliance_gas_giant_is_generated_with_a_city()` --calls--> `generate()`  [EXTRACTED]
  tests/test_cloud_city.py → edge/bigbang/generator.py
- `test_species_knowledge_is_deterministic_bounded_and_referential()` --calls--> `generate()`  [EXTRACTED]
  tests/test_dialogue_intel.py → edge/bigbang/generator.py
- `test_every_discovery_is_named()` --calls--> `generate()`  [EXTRACTED]
  tests/test_discovery_names.py → edge/bigbang/generator.py
- `test_names_are_deterministic_from_the_seed()` --calls--> `generate()`  [EXTRACTED]
  tests/test_discovery_names.py → edge/bigbang/generator.py

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

## Communities (231 total, 54 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.10
Nodes (433): _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup() (+425 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.06
Nodes (61): one_way_exits(), Targets reachable from `sector_id` with no return edge (sorted, deterministic)., range, generate_with_player(), Any, `generate()` then `enroll()` — the common "fresh game with player 1" setup., WP27: logging a find into the codex pays experience_per_discovery., WP27 Core-law basics: a criminal crossing into the Core is put on notice, once (+53 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.02
Nodes (117): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, The roaming Entity's always-on in-sector presence hint (DESIGN §7, WP35).      F, Deployed forces visible in the sector (§10, WP41 — surfaced with classic TW fog), An orbital starbase's presence in the sector view (§4.2 — scene sprite + caption (+109 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.12
Nodes (34): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, A knocked-out part contributes nothing until it is patched (§4.1)., A `subsystems=None` (NPC-style) hull has no engine room to operate on. (+26 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.04
Nodes (119): _best_roundtrip_margin(), _check_degree_cap(), _check_discovery_gradient(), _check_expansive_no_chokepoint(), _check_home_clusters(), _check_planet_ownership(), _check_profitable_pair(), _check_reachable() (+111 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.03
Nodes (135): HardwareItem, MarketOrderDTO, One open order on the Computer's Market tab (§8, WP48)., One row in the Stardock hardware emporium (UI_MOCKUPS.md §5, DESIGN §8)., build_subsystems(), Instantiate a hull's starting subsystems from its config layout (§4.1).      Ret, AssaultOperation, Frozen active-operation state for ground operations (GW-WP03, GW plan §Hashed st (+127 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.11
Nodes (22): DiscoveryNamer, _fallback_prefix(), Random, Deterministic naming generator based on configurable name pools., Names discoveries per kind from `names.discoveries` (PT-49, DESIGN §7).      One, The next unused name for `kind`. Exhausting a pool falls through to numbering., black_hole" → "Black Hole" — the numbered fallback when a kind's pool runs dry., NameList (+14 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.10
Nodes (39): _build_at_radius(), build_local_map(), _codes(), _draw_edges(), _label(), _layout_map_nodes(), _local_bfs(), local_layout_bearings() (+31 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.12
Nodes (33): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+25 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.08
Nodes (22): A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_planet(), EngineRoomScreen, Slot, Render a reducer-validated aspect preview for exactly one selected target., _capture() (+14 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.02
Nodes (141): ArmamentItem, Aspect, BountyDTO, CommodityLine, CorpMemberDTO, DeploymentOptionDTO, DossierEntry, EncounterDTO (+133 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.09
Nodes (48): DialoguePack, DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar, Resolve and render one line for `context`, returning (text, updated recency ring (+40 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.04
Nodes (45): EmptyState, FieldPrompt, Any, ComposeResult, Pressed, Static, Submitted, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches'). (+37 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.03
Nodes (80): Container, TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), Any, EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Persist local-only presentation settings and apply the theme immediately., Tick off a Captain's objective (WP-UI11) — local progress only.          Called (+72 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.03
Nodes (70): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed (+62 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.03
Nodes (89): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+81 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.09
Nodes (65): instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting(), _cfg_with_oath(), _cfg_with_repeat_greeting() (+57 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.05
Nodes (43): Any, ComposeResult, DataTable, Horizontal, Pressed, RowHighlighted, Static, Submitted (+35 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.04
Nodes (114): base_owner_hostile(), Whether an operational base's owner treats the player as an enemy (§4.2, WP40)., hostile_base_in_sector(), An operational base in `sector_id` that engages the player (§4.2, WP40)., build_layouts(), Instantiate intact subsystems from a layout mapping (§4.1).      Base components, Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe (+106 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.10
Nodes (20): _amain(), _build_game(), _error(), LobbyServer, Any, Command, Event, Path (+12 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.02
Nodes (133): ActiveBinding, AmountPrompt, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Enum, The economy: pricing, trade resolution, haggling, banking, stock regen (§8).  Pu, Core enumerations: the canonical TW commodity trio and port classes (§4).  These, Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, CronTask (+125 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.09
Nodes (23): BaseModel, BaseServicesConfig, GwBattlefield, GwEmplacement, GwGarrison, GwGarrisonClass, GwSuit, HardwareConfig (+15 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.06
Nodes (67): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+59 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.07
Nodes (40): compose_horizontal(), flip_row(), Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo, Compose a sprite grid by laying parts left-to-right to fill ``target_w``.      O (+32 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.06
Nodes (67): Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line(), author_packs(), AuthoringError (+59 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.08
Nodes (49): core_bases_razed(), How many Core-planet starbases are no longer the incumbent governor's (§4.2, WP5, The player's progress toward championing a bloc into the Core (§6.3, WP50)., Assemble the player's `SeizureProgress` against a bloc's ladder (pure; WP50)., seizure_progress(), SeizureProgress, A `covets_core` bloc's Core-seizure ladder (DESIGN §6.3, WP50).      The price a, SeizureConfig (+41 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.07
Nodes (70): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, A deterministic fingerprint of the live entity state (RNG/adjacency excluded)., state_hash(), _hostile(), Path (+62 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.08
Nodes (49): _clamp_ship_field(), DevPatchError, Exception, Ship, Field-specific validation for a ship integer set/add (raises on hard limits)., A malformed or impossible dev patch (unknown target, missing entity, bad key)., DevApplied, A dev/testing `DevPatch` mutated the player (see `core.dev`).      `detail` is a (+41 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.11
Nodes (7): ContactDTO, One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, A peaceful alien contact screen (§6, §6.7, §11)., TechOfferDTO, The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any.

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (33): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+25 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.12
Nodes (49): Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), A remote rules rejection compatible with every local rule-error catch.      JSON, RemoteError, RemoteRulesError, Exception, One connected client: the socket, the authenticated account, and the seat it hol, A JSON-RPC error to return to the caller (code + message). (+41 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.08
Nodes (55): DrawFn, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., _force_settlement(), Run one order-book settlement now (WP59 sysop op) — a logged, replayable market, port_unit_price(), Quoted price for a line using the economy config's per-commodity tunables. (+47 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.06
Nodes (48): apply_patch(), build_parser(), _build_patch(), cmd_governance(), cmd_list(), cmd_show(), _components(), _diff_after() (+40 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.08
Nodes (60): Lead, A coordinate tip the player accepted from an alien (DESIGN §6.7, the "map" mecha, _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over (+52 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (29): BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Pressed, Submitted, The LLM pilot's console — a Textual app watching and steering the brain (dev-onl (+21 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.04
Nodes (64): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), list_items(), Render one category of populated universe items as an id-keyed table., main(), CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--stats] [--render DIR]`., load_config(), load_config_with_sidecar() (+56 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.07
Nodes (36): The docked one-line screen header: bold title, optional muted context., TitleBar, BaseScreen, ComposeResult, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th, The visible service tab's id (the unit every action keys on)., The `.` menu / `?` help / palette list, scoped exactly like the footer (PT-32)., Tabs the base withholds (standing / service-integrity gated) — recorded once at (+28 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.16
Nodes (21): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), generate_find_art(), _pit() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.02
Nodes (263): player_corp(), player_owns(), The corporation a player belongs to, or None (§4, WP66)., Whether `player_id` counts as an owner of a holding (§4.2/§4-WP66).      True fo, apply_dev_patch(), _expire_contract(), _moderate_notice(), _parse_component() (+255 more)

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (26): BotSetup, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, BotRunner, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69)., Drives one player of a game through the `ServiceProtocol` seam (dev-tier, WP60)., Register the per-iteration driver — the bot's main loop body. (+18 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (25): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+17 more)

### Community 45 - "Community 45"
Cohesion: 0.05
Nodes (47): ABC, BaseException, CronResolver, DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12)., The save was made with a different dialogue pack; replay would fail mid-way., EngineState (+39 more)

### Community 46 - "Community 46"
Cohesion: 0.02
Nodes (163): MapNodeDTO, One traversed sector on a plotted route — what the player reads (§11, WP14)., A clickable sector node on the local map: its label's cell box in `rows`.      `, RouteHopDTO, EdgeApp, Resize, The synchronous game surface the screens read (WP61/WP68).          Single-playe, Recompute the layout tier and apply its class across the screen stack. (+155 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (21): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), AlienContactScreen, ComposeResult, Widget, Re-fetch the view and repaint the conversation **in place** (§6.7).          `pi, Land focus on the new menu — the old reply rows were just removed under it., The reply menu — the one thing that really changes between nodes.          Share (+13 more)

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (48): DataObject, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Random, Ship (+40 more)

### Community 49 - "Community 49"
Cohesion: 0.03
Nodes (139): _finalize_planets(), _host_markets(), _make_port(), _mid_stock(), _normalize_belts(), _place_starbases(), populate(), Random (+131 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (41): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+33 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.10
Nodes (29): _footer_keys(), _open_computer(), PT-32 — the Computer's keyboard model: a tab owns its keys.  The screen binds on, chrome.EdgeScreen pins Back first — it used to fall in behind whatever the     f, PT-51: `P` on the Map plots a course to the highlighted sector and lands on the, Each category pane owns 1..N for its own sub-tabs — so `2` means a different tab, The corporation lives under Relations now, not behind a game-screen hotkey., Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+21 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (38): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+30 more)

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (10): main(), PlaytestService, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable. (+2 more)

### Community 55 - "Community 55"
Cohesion: 0.13
Nodes (25): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothi (+17 more)

### Community 56 - "Community 56"
Cohesion: 0.08
Nodes (13): Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)., _DeployRow, ComposeResult, Horizontal, Pressed, Text, Vertical, What already sits in this sector, tabular (fog pre-applied upstream). (+5 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (35): Part, A recombinable sprite fragment, authored as ``cells`` rows and composed to     f, _compose(), _grammar_floor(), _mirror_part(), _mirror_row(), PortGenerator, Random (+27 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (41): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+33 more)

### Community 59 - "Community 59"
Cohesion: 0.07
Nodes (23): GroundCellDTO, One sensor contact, masked until excavation settles the real discovery (G6/G7)., Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, SurveyContactDTO, SurveyExpeditionDTO, The active survey's fog-safe viewport, or ``None`` while in orbit (GW-WP07)., _feature_style() (+15 more)

### Community 60 - "Community 60"
Cohesion: 0.06
Nodes (37): _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl, The same actionable Stardock service projections the regular client receives. (+29 more)

### Community 61 - "Community 61"
Cohesion: 0.07
Nodes (16): LinkLost, Any, EncounterDTO, The websocket dropped mid-call — surfaced to the TUI as a retryable status, not, A `GameClient` over a websocket to `edge-server` (WP68) — the hosted-play seam., Open the socket and complete the fingerprint handshake (refuses a build mismatch, connected" / "disconnected" / "closed" — the TUI status-bar link state., Demux the socket: pushed `event` notifications feed the stream; results resolve (+8 more)

### Community 62 - "Community 62"
Cohesion: 0.09
Nodes (15): HelpScreen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key (+7 more)

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (26): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, Groundwar POC config — a thin adapter over the production schema (GW-WP02).  Bal (+18 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (42): Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus() (+34 more)

### Community 65 - "Community 65"
Cohesion: 0.06
Nodes (58): A named species roster (DESIGN §6): alliances + the species pool drawn from., Dialogue/diplomacy reference integrity (§6, §13): ids and hooks resolve., RosterConfig, grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Every authored expansion string in a grammar (for placeholder validation)., _branch_closure(), build_chain() (+50 more)

### Community 66 - "Community 66"
Cohesion: 0.06
Nodes (34): _discoveries(), format_route(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers)., Resolve two endpoints (internal or spatial id) and plot the fewest-hop route., The spatial display id for an internal sector id, or `—` if none is cached., A sector reference as `internal/spatial` (the §5.1 dual id). (+26 more)

### Community 67 - "Community 67"
Cohesion: 0.12
Nodes (23): _grudge_targets(), is_trader(), movement_policy(), NpcTrade, plan_trade(), _player_sectors(), _port_sectors(), Goal-directed NPC movement policies (DESIGN §8/§10, WP42) — pure core.  Replaces (+15 more)

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.15
Nodes (13): _Coord, MeshTopology, Mesh topology builder (DESIGN §5)., Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who (+5 more)

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (35): owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, _force(), _make_hostile(), _mini_state(), WP41 — sector fighters, mines, beacons, black-hole hazards (§10).  Covers the pu, A lethal hazard routes through the WP26 escape pod (WP75 — the A5 seam closed)., Armid is the WP41 mine renamed — same entry damage, spent on detonation. (+27 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (36): Color, available_archetypes(), available_subtypes(), Procedural ASCII art generation logic., Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype() (+28 more)

### Community 72 - "Community 72"
Cohesion: 0.05
Nodes (50): AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json(), get_backend(), OllamaBackend (+42 more)

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (52): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology, PlanarTopology (+44 more)

### Community 74 - "Community 74"
Cohesion: 0.16
Nodes (21): _enemy_world(), WP54 — citadels: levels, treasury, timed builds, the planetary gun (DESIGN §4.2,, An alliance-owned world in the player's sector, ready to invade (no base)., A single owned colony in the player's sector (no port), ready to fortify., test_build_citadel_pays_up_front_and_opens_a_build(), test_build_rejects_too_few_colonists_or_equipment_or_latinum(), test_build_stalls_without_colonists(), test_cannot_invade_a_core_world() (+13 more)

### Community 75 - "Community 75"
Cohesion: 0.07
Nodes (16): EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., The embedded ticker (tests/shots that step it directly)., _encode_any(), GameServer, Owns one hosted game: the service, the ticker, the single command queue, and ses, Fan freshly-persisted events to every session that should see them (the `on_even (+8 more)

### Community 76 - "Community 76"
Cohesion: 0.14
Nodes (15): Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Composites one sector as an *arrival view* (UI_MOCKUPS.md §1, PT-36/PT-44)., Base grid from the procedural `edge.art` starfield (seeded per sector). (+7 more)

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
Cohesion: 0.10
Nodes (25): DeployShip, main(), _make_starfield(), Battle, `edge-spacebattle` — the space-battle POC's Textual shell.  Throwaway UI (the `t, A static char-level starfield backdrop with dim placement-grid ticks., One fleet slot during deployment — a hull awaiting a cell and a facing., SpacebattleApp (+17 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (32): alien_dialogue_default.yaml (dialogue corpus), alien_dialogue_species.yaml (species grammars), alien_roster_default.yaml (species roster), default.yaml (game constants), Alien species disposition system, Alliances (rival blocs, join one at a time), Asteroid belt mining (finite reserves), Universe generation (Big Bang) (+24 more)

### Community 82 - "Community 82"
Cohesion: 0.09
Nodes (41): _decode_any(), Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command() (+33 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (19): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), main(), _parse_args() (+11 more)

### Community 84 - "Community 84"
Cohesion: 0.10
Nodes (46): _engagement(), _fight_state(), _foe(), _forced_knockout_config(), WP25 — combat rounds: the escape floor, arcs, missiles, and full-fight goldens (, A spinal attacker recharges between volleys — even rounds are safe from it., Hull 0 (§10, WP26): the ship, cargo, and stores are lost; the escape pod —     a, A config where every hull-reaching volley knocks a component out of exactly (+38 more)

### Community 85 - "Community 85"
Cohesion: 0.12
Nodes (20): AspectFormula, EngineRoomConfig, The ship-class config for `class_id` — the starter hull or a buyable one., One subsystem's slot layout for a hull (DESIGN §4.1).      `slot_count` fixed sl, Coefficients turning a subsystem's filled slots into a derived aspect (§4.1)., Game-global engine-room tunables (DESIGN §4.1).      The per-subsystem layouts l, A ship class (DESIGN §4).      A hull with an engine room carries a `subsystems`, ShipClassConfig (+12 more)

### Community 86 - "Community 86"
Cohesion: 0.18
Nodes (20): _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7). (+12 more)

### Community 87 - "Community 87"
Cohesion: 0.08
Nodes (28): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+20 more)

### Community 88 - "Community 88"
Cohesion: 0.15
Nodes (23): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+15 more)

### Community 89 - "Community 89"
Cohesion: 0.17
Nodes (8): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., Static, Vertical, Widget, The base's standing, on one line, in a bordered panel above the installations.

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (29): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+21 more)

### Community 91 - "Community 91"
Cohesion: 0.19
Nodes (4): PlaytestControls, Click, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 92 - "Community 92"
Cohesion: 0.02
Nodes (277): Seed the roster's authored inter-species grudges for the cast pairs (§6.5, WP27), _seed_grudges(), admission_met(), admission_tasks_done(), _alliance_key(), alliance_standing(), alliance_standing_shift(), apply_join_standing() (+269 more)

### Community 93 - "Community 93"
Cohesion: 0.18
Nodes (20): list_portraits(), portraits_dir(), Path, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait() (+12 more)

### Community 94 - "Community 94"
Cohesion: 0.17
Nodes (20): BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), _cfg(), _commodity(), _event_owner() (+12 more)

### Community 95 - "Community 95"
Cohesion: 0.03
Nodes (57): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state)., The DTO under the highlighted row of `table_id`, or None.          WP-UI21: reso (+49 more)

### Community 96 - "Community 96"
Cohesion: 0.08
Nodes (52): _build_site(), _cell_cost(), dig_trench(), _dist(), generate_survey(), _in_bounds(), _keepout(), _landing() (+44 more)

### Community 97 - "Community 97"
Cohesion: 0.19
Nodes (6): Any, A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., A `GameService`-shaped synchronous facade over the connected client., Bridge the async event iterator one item at a time onto Textual's loop., RemoteService

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (38): accrue_interest(), alien_drift(), _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16)., Compound interest on every non-empty bank balance (§8)., _config(), _drift_world() (+30 more)

### Community 99 - "Community 99"
Cohesion: 0.05
Nodes (46): Binding, Screen, Open the numbered context-action menu over the current screen (WP73, D3)., Expose current-screen actions through Textual's fuzzy command palette., Shown while the terminal is below the 80×24 floor (WP-UI05).      It never traps, SizeNoticeScreen, Any, Screen (+38 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.12
Nodes (9): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., TabActivated, Shared responsive service navigation for Stardock and orbital bases.      Standa, Switch to `entry_id` and focus its primary content (tab accelerator target)., Drop focus before a programmatic tab switch (see the class docstring)., Never strand focus in a tab that is no longer showing — its keys would stay, Enter on the tab rail drops focus onto the active tab's primary content. (+1 more)

### Community 103 - "Community 103"
Cohesion: 0.20
Nodes (18): A friendly settlement visible on the projected survey map., SurveySettlementDTO, ground_operation_view(), Project the player's active survey without exposing its generation identity (GW-, MonkeyPatch, Path, GW-WP07 — fog-safe expedition DTO, client parity, and live Textual flow., A loaded/reconnected session cannot strand the player behind the G9 blocker. (+10 more)

### Community 104 - "Community 104"
Cohesion: 0.19
Nodes (19): _bfs_from(), _pick_by_distance(), plan_move(), Random, Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42)., Hop distance from the nearest `sources` node to every reachable sector (BFS)., Pick the candidate nearest (or farthest, if `maximize`) a target set.      Unrea, _line_state() (+11 more)

### Community 105 - "Community 105"
Cohesion: 0.16
Nodes (26): SectorDTO, build_nav_strip(), _nearest_free(), _octant(), The main-screen nav rose — a bearing-placed compass of immediate warps (§11).  B, Snap a bearing (radians, 0 = east, +y = north) to one of 8 compass octants., The preferred octant, or the closest free one (deterministic +d before -d)., The cell text: spatial id plus content codes once charted (fog masks codes). (+18 more)

### Community 106 - "Community 106"
Cohesion: 0.25
Nodes (3): Any, Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat.

### Community 107 - "Community 107"
Cohesion: 0.14
Nodes (17): arc_facts(), callback_facts(), contact_facts(), encounter_facts(), note(), note_topic(), Shared dialogue fact assembly (DESIGN §6.7, WP28) — pure, no I/O, no RNG.  The *, The facts the live contact session contributes (empty when none, or another's). (+9 more)

### Community 108 - "Community 108"
Cohesion: 0.26
Nodes (11): effective_trade_posture(), The species' trade posture as this player experiences it (§6.1/§6.2 — WP74)., WP74 — the signature-mechanic corpus routes (SEAMS_PLAN A2, decision D4).  The s, Each carrier species' pack routes a choice into its own sig.* namespace (A2 clos, test_alliance_gated_trade_opens_for_sworn_members(), test_escalating_demand_ladder_climbs_and_betrayal_is_permanent(), test_every_dark_hook_has_a_corpus_route(), test_flee_drop_route_pays_once() (+3 more)

### Community 109 - "Community 109"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 110 - "Community 110"
Cohesion: 0.04
Nodes (57): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), Text (+49 more)

### Community 111 - "Community 111"
Cohesion: 0.12
Nodes (33): LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered(), _label(), pick_intel_target() (+25 more)

### Community 112 - "Community 112"
Cohesion: 0.09
Nodes (10): _assert_impl(), _assert_remote_impl(), GameClient, Command, Event, Protocol, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Apply a command through the in-process service (events fan out via `on_events`). (+2 more)

### Community 113 - "Community 113"
Cohesion: 0.19
Nodes (6): BridgedGameClient, Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises)., An awaitable facade safe to call from Textual's loop (GW-WP07)., Run the full async ``RemoteClient`` surface on its owning background loop., RemoteBridge

### Community 114 - "Community 114"
Cohesion: 0.27
Nodes (10): _event_player(), event_visible_to(), The acting/addressed player of an event, if any (its `player_id`/`owner_player_i, Whether `player_id` should receive `event` under the fog-of-war broadcast policy, P1 at sector 2 (charted 1-3); P2 at sector 4 (charted 4-5) — disjoint horizons., test_global_event_reaches_every_player(), test_no_event_about_an_unexplored_absent_sector_reaches_a_player(), test_private_event_reaches_only_its_actor() (+2 more)

### Community 115 - "Community 115"
Cohesion: 0.19
Nodes (13): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, One sector on the nav-rose trail breadcrumb (§11): its spatial id and distance, TrailCrumb, WarpDTO, Nav-rose widget presentation (WP-PR2-07 / PT-48, PT-55).  `NavRose` bakes two cl, _rose() (+5 more)

### Community 116 - "Community 116"
Cohesion: 0.11
Nodes (18): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError (+10 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.21
Nodes (23): apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., Apply an engine cron's result: upsert entities + persist its durable trail., _begin(), _op(), GW-WP06 — authoritative survey actions, persistence, and reward settlement.  Dri, March until the explorer stands on `site` (marches halt early, so loop)., Teleport a player's explorer onto `(x, y)` — isolates dig/talk from march distan (+15 more)

### Community 119 - "Community 119"
Cohesion: 0.14
Nodes (22): Adjacency, _annotate(), can_warp(), plan_route(), plan_route_legs(), Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For, The sectors reachable in one hop from `sector_id`. (+14 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.02
Nodes (194): CombatConfig, _archetype(), assign_station_archetypes(), _builder(), Deterministic builder-archetype assignment for ports and orbital bases., Resolve the species whose configured archetype designed the structure., Stamp every structure's builder archetype after alien regions exist (§5)., build_payload() (+186 more)

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
Cohesion: 0.24
Nodes (16): _disc(), _planet_with_hidden_and_obvious(), GW-WP05 — survey generation from real universe discoveries (GW plan §GW-M2).  Tw, _survey(), test_already_collected_site_marked_found(), test_already_detected_site_is_visible_regardless_of_sensor(), test_eligibility_is_sensor_monotone_and_non_leaking(), test_every_surface_find_is_artifact_plus_lore() (+8 more)

### Community 127 - "Community 127"
Cohesion: 0.23
Nodes (13): FindKind, Random, Shared archaeological find identities promoted from the groundwar POC.  The prod, Draw one POC-style archaeological proper name., Stable POC art/name subtype for a compatible production surface kind., Stable POC name for a compatible existing surface discovery., site_name(), surface_find_kind() (+5 more)

### Community 128 - "Community 128"
Cohesion: 0.50
Nodes (3): Random, Deployed forces as glyph-scale presence marks — fighters flying patrol         t, Sprinkle single glyphs through free sky (padded a cell so they never hug

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.25
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "EngineRoomDTO"
Cohesion: 0.18
Nodes (12): market_settlement(), The daily order-book settlement: match the book, move goods+latinum, drip purses, Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., _market_config(), A run of ticked trades (the WP12 rail) is deterministic — the same firings from, The market crons ride the WP12 replay rail: same firings ⇒ identical `state_hash, test_market_tick_posts_a_book_then_settlement_moves_goods() (+4 more)

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 138 - "main"
Cohesion: 0.29
Nodes (13): Run one trade for every NPC merchant working a port this firing (§8, WP43)., trader_step(), A 1-2-3 Frontier chain with a trading port at sector 2 (optionally a player ther, A `selvani` merchant (movement_policy trade_seek in the default roster ⇒ a trade, _selvani(), test_a_distant_player_is_not_warmed(), test_non_trader_species_never_trades(), test_trader_dumps_held_cargo_before_buying() (+5 more)

### Community 139 - "MarketDTO"
Cohesion: 0.29
Nodes (3): CorpDTO, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The player's corporation for the `T` screen — roster, bank, holdings, wars (§4,

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.07
Nodes (9): A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, RouteDTO, _assert_impl(), Command, EncounterDTO, Event, Protocol, The typed surface of the in-process game service (H16). (+1 more)

### Community 142 - "TopologyModeConfig"
Cohesion: 0.17
Nodes (17): CronFn, The pure reducer for a persisted cron name (raises on an unknown name)., resolve_cron(), _noncore(), Path, WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage() (+9 more)

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (19): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, main(), Battle, Pressed, Screen (+11 more)

### Community 144 - "trader_step"
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 145 - "test_genesis.py"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

### Community 146 - "test_intel_contact.py"
Cohesion: 0.31
Nodes (12): _drop_entity(), _inject(), _knows_a_far_discovery(), Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7), Log-coordinates is a reply on the offer_coordinates node, not the greeting — you, Remove the roaming Entity so a test can isolate the regular coordinate-tip mecha, Point the species' knowledge at a real, reachable, unexplored rare+ discovery., test_accept_lead_without_a_tip_is_rejected() (+4 more)

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
Cohesion: 0.15
Nodes (9): Every species' `home_band` hint must name a configured distance band (§6)., The parameters specific to one `topology_mode` (DESIGN §5).      Everything a mo, Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).      E, The config block for the selected `topology_mode` (§5 step 5)., The distance bands for the configured `topology_mode` (§5 step 5)., TopologyModeConfig, TopologySet, The config validator enforces same band names across modes (only thresholds (+1 more)

### Community 155 - "market_view"
Cohesion: 0.25
Nodes (5): Command, Event, Persisted events after `seq`, each with its seq — the reconnect catch-up buffer, Render one event for the live ticker, with a spatial sector gutter (§5.1, §11)., Validate, persist, and apply a command; return the events it produced.

### Community 156 - ".compose"
Cohesion: 0.21
Nodes (6): Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait., Render a species' portrait image (by `roster_id`) into its allotted cell box., SpeciesPortrait

### Community 157 - "Ticker"
Cohesion: 0.17
Nodes (12): _entity_here(), Move the player into the Entity's sector at a given sensor rating; return the En, The sector view always shows the Entity's presence (computed live), never names, The hint is absent where the Entity is not, present where it is — from its curre, The reducer re-checks the gate (H2): an under-sensored Hail raises, never contac, First Hail past the gate collects the reserved Legendary codex row (once-only,, The contact projection flags the Entity so the TUI fills the portrait slot (WP35, test_contact_view_marks_singular_entity() (+4 more)

### Community 158 - "StaticGenerator"
Cohesion: 0.31
Nodes (6): Random, Text, Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.  Un, Generates a frame of random low-contrast static ("snow")., Fill a `width` × `height` frame with weighted random noise glyphs.          `sub, StaticGenerator

### Community 159 - "GameState"
Cohesion: 0.24
Nodes (3): EngineRoomDTO, The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)., _room()

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 161 - "MessagesDTO"
Cohesion: 0.31
Nodes (8): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., ModuleType

### Community 163 - "TavernDTO"
Cohesion: 0.28
Nodes (9): _entity_world(), A generated world with the Concordance placed in the player's sector., A virtuous player is blessed: stage persisted, attitude up, experience paid, spo, A criminal player is cursed: a permanent grudge forms (never_forgets Entity)., The judgment command replays to the identical state hash (the stage-ladder rail), _submit(), test_judgment_reducer_blesses(), test_judgment_reducer_curses_with_grudge() (+1 more)

### Community 164 - "MessagesDTO"
Cohesion: 0.29
Nodes (3): MessagesDTO, The messages & log view, projected from the durable event_log (§12)., The durable event log, newest first (§11, §12).

### Community 165 - ".apply"
Cohesion: 0.29
Nodes (5): Command, Event, Register a trigger fired for every `event_type` a command produces (the TWX idio, Submit a command, dispatch its events to triggers, and swallow rejections (WP60), TriggerHandler

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 167 - ".__init__"
Cohesion: 0.19
Nodes (14): LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met, Run the embedded engine ticker until stopped (the app's engine worker, §3)., The wrapped in-process service (single-player back-compat; never used for remote, _config(), Path, WP61 — the async `GameClient` facade over the in-process service (DESIGN §3/§14), _service() (+6 more)

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 171 - "TerritoryDTO"
Cohesion: 0.33
Nodes (3): Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, Carried territory stock + devices for the Deploy screen (§10/§14, WP72).

### Community 172 - "_SpriteCard"
Cohesion: 0.29
Nodes (5): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard

### Community 173 - "CommodityPricing"
Cohesion: 0.50
Nodes (3): CommodityPricing, The pricing inputs for one commodity., Per-commodity pricing inputs for the §8 stock-ratio formula.

### Community 174 - "Community 174"
Cohesion: 0.40
Nodes (4): Debris, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, Scatter drifting-wreckage clumps across the midfield (graveyard     scenarios) —, seed_debris()

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 177 - "sprites.py"
Cohesion: 0.50
Nodes (3): pick_subsystem(), Engine-room subsystem icons for the TUI (UI_MOCKUPS.md §8).  The procedural `edg, The decorative ASCII icon for an engine-room subsystem (§8).

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

## Knowledge Gaps
- **53 isolated node(s):** `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script`, `graphify`, `Workflow: graphify` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **54 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Screens, DTOs & Remote Play`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Domain Models & Colonizability`, `Dialogue-Pack Save Guard`, `Subsystem Layouts & Ownership`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 43`, `Community 45`, `Community 46`, `Community 48`, `Community 49`, `Community 61`, `Community 65`, `Community 67`, `Community 68`, `Community 69`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 79`, `Community 83`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 92`, `Community 94`, `Community 98`, `Community 102`, `Community 111`, `Community 112`, `Community 117`, `Community 121`, `Community 129`, `main`, `Community 141`, `Community 143`, `trader_step`, `Community 154`, `.__init__`, `CommodityPricing`, `GwExpedition`, `CorpConfig`, `CronCadenceConfig`, `DefenseConfig`, `DeviceConfig`, `EncountersConfig`, `GenesisConfig`, `GovernanceConfig`, `GrudgeSeedConfig`, `GwDefenses`, `GwDifficulty`, `GwPlatoon`, `GwPressure`, `GwResolve`, `GwScannerBand`, `GwTerrain`, `GwWeapon`, `HagglingConfig`, `MarketConfig`, `OwnershipWeights`, `PlanetNamesConfig`, `PlanetsConfig`, `PlanetTypeProfile`, `TickerConfig`, `StarbaseConfig`, `TerritoryConfig`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 121` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `EngineRoomDTO`, `Planet & Orbit Views`, `main`, `Community 141`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `Subsystem Layouts & Ownership`, `Community 147`, `Market Orders & Regions`, `Config Schema Models`, `Community 154`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Config Loading & Sidecar Merge`, `.__init__`, `Community 42`, `Community 43`, `Community 45`, `Community 49`, `Community 54`, `Community 61`, `Community 67`, `Community 69`, `Community 71`, `Community 73`, `Community 77`, `Community 85`, `Community 86`, `Community 91`, `Community 92`, `Community 93`, `Community 96`, `Community 98`, `Community 103`, `Community 104`, `Community 109`, `Community 112`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Community 42` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Standing, Corp & Combat Rules`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `EngineRoomDTO`, `Planet & Orbit Views`, `Disposition Bands & Ship Classes`, `main`, `Domain Models & Colonizability`, `Community 141`, `TopologyModeConfig`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `test_intel_contact.py`, `Subsystem Layouts & Ownership`, `Market Orders & Regions`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Ticker`, `Dev Patch Tooling`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `TavernDTO`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `.__init__`, `Community 45`, `Community 48`, `Community 49`, `Community 61`, `Community 66`, `Community 67`, `Community 70`, `Community 73`, `Community 74`, `Community 77`, `Community 86`, `Community 92`, `Community 93`, `Community 94`, `Community 96`, `Community 98`, `Community 103`, `Community 104`, `Community 107`, `Community 108`, `Community 110`, `Community 111`, `Community 112`, `Community 114`, `Community 118`, `Community 121`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 337 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 337 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._