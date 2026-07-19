# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 333 files · ~9,151,219 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 7991 nodes · 34137 edges · 203 communities (174 shown, 29 thin omitted)
- Extraction: 69% EXTRACTED · 31% INFERRED · 0% AMBIGUOUS · INFERRED: 10562 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ea5be262`
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
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- ._refresh_art
- .__init__
- Community 139
- Community 140
- Community 141
- TopologyModeConfig
- Community 143
- trader_step
- AmountPrompt
- webviz.py
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- market_view
- EmptyState
- Community 157
- DetailOverlay
- SpeciesPortrait
- Community 160
- detail_table.py
- GameState
- TavernDTO
- LeadDTO
- HaggleQuote
- Community 166
- MarketDTO
- .apply
- Community 169
- Community 170
- test_ui_asteroid_belt.py
- TechOfferDTO
- CommodityPricing
- Community 174
- Community 175
- sprites.py
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
1. `UniverseState` - 506 edges
2. `GameConfig` - 454 edges
3. `Commodity` - 419 edges
4. `reduce()` - 368 edges
5. `EconomyError` - 334 edges
6. `EdgeApp` - 259 edges
7. `ComponentTier` - 229 edges
8. `Warp` - 229 edges
9. `apply_result()` - 222 edges
10. `Event` - 212 edges

## Surprising Connections (you probably didn't know these)
- `test_width_grows_monotonically_and_respects_bounds()` --calls--> `compose_horizontal()`  [EXTRACTED]
  tests/test_ship_art.py → edge/art/hull.py
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_species_knowledge_is_deterministic_bounded_and_referential()` --calls--> `generate()`  [EXTRACTED]
  tests/test_dialogue_intel.py → edge/bigbang/generator.py
- `test_core_pinned_to_origin()` --calls--> `generate()`  [EXTRACTED]
  tests/test_embedding.py → edge/bigbang/generator.py
- `test_embedding_is_populated_and_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_embedding.py → edge/bigbang/generator.py

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

## Communities (203 total, 29 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.09
Nodes (433): AmountPrompt, _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes (+425 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.02
Nodes (167): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., SceneArtConfig, MapNodeDTO, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, A clickable sector node on the local map: its label's cell box in `rows`.      `, SectorDiscovery (+159 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.05
Nodes (52): Aspect, CommodityLine, ComputerDTO, EncounterFoeDTO, Hold, LogEntry, MessagesDTO, NavStripDTO (+44 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.03
Nodes (257): Apply the consequences of destroying `kills` of a species' ships (§6.5, WP27)., sour_attitude(), GameConfig, Top-level config bundle, validated from the parsed YAML mapping., apply_reward(), Pay a completed contract: latinum faucet + capped attitude warmth toward the iss, player_corp(), The corporation a player belongs to, or None (§4, WP66). (+249 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.03
Nodes (127): EdgeApp, Any, Resize, Screen, The synchronous game surface the screens read (WP61/WP68).          Single-playe, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05). (+119 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.02
Nodes (245): admission_met(), admission_tasks_done(), _alliance_key(), alliance_rivals(), alliance_standing(), alliance_standing_shift(), apply_join_standing(), apply_resign_standing() (+237 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.02
Nodes (74): AllianceRowDTO, One traversed sector on a plotted route — what the player reads (§11, WP14)., One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., RouteHopDTO, ComputerScreen, ComposeResult, Pressed, TabActivated (+66 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.04
Nodes (95): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+87 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.06
Nodes (60): ContractsConfig, Favors + escort contracts issued through the dialogue system (DESIGN §6.7, §14 —, accept(), active(), advance_convoy(), by_id(), complete_destroy_on_kill(), complete_destroy_on_raze() (+52 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.07
Nodes (32): One subsystem panel: its derived aspect and its slot grid (§4.1)., Subsystem, _BayPanel, ComponentWorkbench, ComponentWorkbenchProfile, ComposeResult, Horizontal, Message (+24 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.18
Nodes (18): apply_patch(), Apply (or, in dry-run, preview) a DevPatch and report what changed., config_dump(), _intervene(), _lobby_hint(), main(), menu(), _print() (+10 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.05
Nodes (71): is_colonizable(), Whether a world of this type can be claimed and settled (§4.2).      Colonizable, range, enroll(), generate_with_player(), Any, Shared test helpers.  The big bang no longer seeds players — enrolling a player, Enroll a player into an already-generated universe (mutates + returns `state`). (+63 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.02
Nodes (135): ActiveBinding, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, `BotSwarm` — many bots against one authoritative game (DESIGN §14 — WP69).  The, ArmamentItem, BountyDTO, CorpMemberDTO (+127 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.03
Nodes (84): Container, TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Tick off a Captain's objective (WP-UI11) — local progress only.          Called, Reload the saved game by replaying its command log (DESIGN §12).          Return, Validate art coverage and read scene-sprite sizes before a game starts. (+76 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.11
Nodes (39): Command, Event, Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, _config(), _drift_config(), Path, WP6 — the in-process GameService + fog-of-war projections (DESIGN §3)., Enrolment is a recorded `JoinGame` (not seeded by the big bang), so a second (+31 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.04
Nodes (73): build_graph(), generate(), Build the warp graph and return its adjacency plus the region groups., Generate a validated universe from `(seed, config)`; raise on repeated failure., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, bfs_distances(), Forward hop distance from `src` to every reachable sector.      Accepts any int- (+65 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.06
Nodes (90): instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting(), _cfg_with_oath(), _cfg_with_repeat_greeting() (+82 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.04
Nodes (59): HaggleScreen, ComposeResult, Submitted, Any, ComposeResult, DataTable, Horizontal, Pressed (+51 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.09
Nodes (54): Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe, _base(), WP78 — base-hosted markets (DESIGN §4.2).  A port sharing its sector with an orb, Sector 2 holds a base-hosted port (SELL fuel ore); the player sits there., test_commission_clamps_to_the_purse(), test_corp_host_taxes_outsiders_but_not_members(), test_derelict_base_market_is_dark() (+46 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.03
Nodes (60): The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_planet(), sample_surface(), Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises). (+52 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.08
Nodes (52): A named cluster from generation (DESIGN §4/§5)., Region, game_view(), The primary game-screen bundle for `player_id` (§11)., The scene paints the floating city from the same fact the orbit view reads., test_the_sector_scene_sees_the_city(), _booked_world(), _nav_world() (+44 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.03
Nodes (79): BaseModel, BaseServicesConfig, CorpConfig, CronCadenceConfig, DefenseConfig, DeviceConfig, EncountersConfig, GenesisConfig (+71 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.05
Nodes (71): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+63 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.11
Nodes (22): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+14 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.04
Nodes (90): AnthropicBackend, AntigravityBackend, CliBackend, _extract_json(), get_backend(), OllamaBackend, _parse_claude_envelope(), Any (+82 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.02
Nodes (159): _archetype(), assign_station_archetypes(), _builder(), Deterministic builder-archetype assignment for ports and orbital bases., Resolve the species whose configured archetype designed the structure., Stamp every structure's builder archetype after alien regions exist (§5)., may_occupy(), Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules, WP16 (+151 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.06
Nodes (56): is_extractable(), normalize_belt(), Scrub colony/citadel/base affordances off a non-landable spatial world (§4.2)., Whether this world yields raw goods in orbit without colonists (§4.2).      The, Command, Validate `command` for `player_id` and return its delta + events., reduce(), _dirty_belt() (+48 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.09
Nodes (46): apply_dev_patch(), _clamp_ship_field(), DevPatchError, _expire_contract(), _force_settlement(), _moderate_notice(), _parse_component(), Exception (+38 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.06
Nodes (14): ContactDTO, A peaceful alien contact screen (§6, §6.7, §11)., Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, Rewrite every reply to enabled so gated branches become traversable., _assert_impl(), _assert_remote_impl(), GameClient (+6 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.09
Nodes (21): App, ColumnSpec, DetailTable, HeaderSelected, RowHighlighted, Submitted, Text, Replace the backing rows (presentation copy only), keeping the         cursor on (+13 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.06
Nodes (37): _amain(), _encode_any(), _error(), GameServer, LobbyServer, main(), Any, Command (+29 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.09
Nodes (52): DrawFn, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., clear_filled(), desired_stock_frac(), generate_orders(), hinterland_drift() (+44 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.10
Nodes (22): build_parser(), _build_patch(), cmd_list(), cmd_show(), _components(), _diff_after(), dispatch(), main() (+14 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (58): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+50 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (29): BotRecord, The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Pressed, Submitted (+21 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.05
Nodes (49): load_default_config(), _merge_dialogue(), Any, Load the bundled default config (`config/default.yaml`)., Fold one dialogue document onto a roster dict in place (DESIGN §6.7).      Two s, PlanetSpriteSize, Any, Footprint bounds (character cells) for one SectorView scene sprite.      A sprit (+41 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.06
Nodes (35): BaseScreen, ComposeResult, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th, The visible service tab's id (the unit every action keys on)., The `.` menu / `?` help / palette list, scoped exactly like the footer (PT-32)., Tabs the base withholds (standing / service-integrity gated) — recorded once at, Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Install the selected carried component into the selected open base slot. (+27 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.06
Nodes (49): Cell, A surface-exploration site on a descended planet (UI_MOCKUPS.md §4, §7).      `s, SurfaceSite, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor (+41 more)

### Community 42 - "Community 42"
Cohesion: 0.09
Nodes (49): _best_roundtrip_margin(), _check_degree_cap(), _check_discovery_gradient(), _check_expansive_no_chokepoint(), _check_home_clusters(), _check_planet_ownership(), _check_profitable_pair(), _check_reachable() (+41 more)

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (14): BotSetup, BotRunner, Command, Event, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69)., Drives one player of a game through the `ServiceProtocol` seam (dev-tier, WP60)., Register a trigger fired for every `event_type` a command produces (the TWX idio (+6 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (27): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+19 more)

### Community 45 - "Community 45"
Cohesion: 0.03
Nodes (128): ABC, BaseException, CronFn, CronResolver, load_script(), main(), open_service(), Path (+120 more)

### Community 46 - "Community 46"
Cohesion: 0.07
Nodes (21): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), AlienContactScreen, ComposeResult, Widget, Re-fetch the view and repaint the conversation **in place** (§6.7).          `pi, Land focus on the new menu — the old reply rows were just removed under it., The reply menu — the one thing that really changes between nodes.          Share (+13 more)

### Community 47 - "Community 47"
Cohesion: 0.11
Nodes (20): AmountStepper, ComposeResult, Horizontal, Pressed, An integer input followed by decrement/increment buttons., `+` / `−` on the Colonists tab: step the amount by the stepper's own step., _open_invade(), SimpleNamespace (+12 more)

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (45): DataObject, execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Random, Ship, quoted_unit_price() (+37 more)

### Community 49 - "Community 49"
Cohesion: 0.06
Nodes (70): advance_build(), building(), Whether a timed build is currently open on `planet` (§4.2, WP54)., Advance an open build by one production tick, returning `(planet, completed)`., Planet, A planet (DESIGN §4.2): a typed, ownable, producing world.      `planet_type` fi, _add(), belt_mining_yield() (+62 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (41): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+33 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.05
Nodes (37): LayoutTier, Enum, GameScreen, _presence_lines(), ComposeResult, Event, Static, Text (+29 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (36): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+28 more)

### Community 54 - "Community 54"
Cohesion: 0.07
Nodes (12): main(), PlaytestControls, PlaytestService, Click, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR (+4 more)

### Community 55 - "Community 55"
Cohesion: 0.15
Nodes (37): A stable hash of the protocol surface — client and server refuse a mismatch at h, wire_fingerprint(), _bound_session(), _config(), _lobby(), Path, Session, WP63 — the websocket JSON-RPC game server (DESIGN §3/§14, H14).  Two layers: fas (+29 more)

### Community 56 - "Community 56"
Cohesion: 0.08
Nodes (26): flip_row(), Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Random, Slot, Text, The authored row-height of a ship grammar tier (all parts share it)., Pick the tallest tier whose authored height fits ``height``; falls back to     t, Generate a procedural ship sprite, hued by owner ``archetype_id`` and         po (+18 more)

### Community 57 - "Community 57"
Cohesion: 0.06
Nodes (51): compose_horizontal(), HullStyle, Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Palette for a hull: three shading levels, the navigation-beacon hue pools     (a, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo (+43 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (41): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+33 more)

### Community 59 - "Community 59"
Cohesion: 0.17
Nodes (12): _Coord, MeshTopology, Mesh topology builder (DESIGN §5)., Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who (+4 more)

### Community 60 - "Community 60"
Cohesion: 0.05
Nodes (40): _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl, The same actionable Stardock service projections the regular client receives. (+32 more)

### Community 61 - "Community 61"
Cohesion: 0.06
Nodes (21): _decode_any(), LinkLost, Any, Command, EncounterDTO, Event, Apply a command through the in-process service (events fan out via `on_events`)., The websocket dropped mid-call — surfaced to the TUI as a retryable status, not (+13 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (15): HelpScreen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key (+7 more)

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (24): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, _add_structure() (+16 more)

### Community 64 - "Community 64"
Cohesion: 0.12
Nodes (43): GarrisonUnit, Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed() (+35 more)

### Community 65 - "Community 65"
Cohesion: 0.09
Nodes (38): DialoguePack, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, allowed_placeholders(), Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, The placeholder names a variant of `context` may use (validator + authoring)., Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace (+30 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (16): FormField, InterventionForm, Any, ComposeResult, DataTable, HeaderSelected, OptionSelected, Pressed (+8 more)

### Community 67 - "Community 67"
Cohesion: 0.25
Nodes (9): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.06
Nodes (19): Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)., ListPicker, ComposeResult, `options` are (markup label, ref) rows; the ref comes back on dismiss., _DeployRow, ComposeResult, Horizontal, Pressed (+11 more)

### Community 70 - "Community 70"
Cohesion: 0.13
Nodes (38): owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, _force(), _generated(), _make_hostile(), _mini_state(), WP41 — sector fighters, mines, beacons, black-hole hazards (§10).  Covers the pu, A lethal hazard routes through the WP26 escape pod (WP75 — the A5 seam closed). (+30 more)

### Community 71 - "Community 71"
Cohesion: 0.06
Nodes (51): Color, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+43 more)

### Community 72 - "Community 72"
Cohesion: 0.09
Nodes (31): load_config(), load_config_with_sidecar(), Path, Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Build a `GameConfig` with `sidecar` spliced onto the default roster (no integrit, Merge a generated dialogue sidecar onto the default roster and run §13 integrity, Load and validate a YAML game config from `path`.      A `roster_file:` pointer, validate_sidecar() (+23 more)

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (50): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology, PlanarTopology (+42 more)

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (35): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar (+27 more)

### Community 75 - "Community 75"
Cohesion: 0.05
Nodes (58): citadel_defense_mult(), citadel_foe(), conquer(), has_gun(), InvasionOutcome, level_config(), _levels(), open_build() (+50 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (18): Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Deployed forces as glyph-scale presence marks — fighters flying patrol         t (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (31): Assault, ground_access(), OrbitalOnly, Classify how the player may interact with `planet` from orbit (GW plan §contract, This world is only ever interacted with from orbit (no ground operation).      A, This world opens a tactical **assault** once its orbital defences fall (GW-WP08+, Whether the orbital ladder is clear and a platoon could land right now., GroundAccess (+23 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (14): Battle, Event, Side, One cell of rocky debris (belt scenarios). Blocks fire lines and wings;     dest, A missile salvo in flight — a board object chasing its target ship., One log/FX entry drained by the UI after each rules call., A ship (any footprint cell), wing, rock, or wreckage sits here — one         pie, Every board cell of the piece's footprint (anchored on the centre).         Ship (+6 more)

### Community 79 - "Community 79"
Cohesion: 0.11
Nodes (28): LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), _drop_entity(), _inject(), _knows_a_far_discovery(), Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7), Log-coordinates is a reply on the offer_coordinates node, not the greeting — you (+20 more)

### Community 80 - "Community 80"
Cohesion: 0.10
Nodes (25): DeployShip, main(), _make_starfield(), Battle, `edge-spacebattle` — the space-battle POC's Textual shell.  Throwaway UI (the `t, A static char-level starfield backdrop with dim placement-grid ticks., One fleet slot during deployment — a hull awaiting a cell and a facing., SpacebattleApp (+17 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (32): alien_dialogue_default.yaml (dialogue corpus), alien_dialogue_species.yaml (species grammars), alien_roster_default.yaml (species roster), default.yaml (game constants), Alien species disposition system, Alliances (rival blocs, join one at a time), Asteroid belt mining (finite reserves), Universe generation (Big Bang) (+24 more)

### Community 82 - "Community 82"
Cohesion: 0.10
Nodes (39): decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command(), encode_dto(), encode_event() (+31 more)

### Community 83 - "Community 83"
Cohesion: 0.21
Nodes (16): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), _parse_args(), Parse server launch settings, including default storage and operator-secret sour (+8 more)

### Community 84 - "Community 84"
Cohesion: 0.09
Nodes (49): _engagement(), _fight_state(), _foe(), _forced_knockout_config(), _hostile(), Path, WP25 — combat rounds: the escape floor, arcs, missiles, and full-fight goldens (, A spinal attacker recharges between volleys — even rounds are safe from it. (+41 more)

### Community 85 - "Community 85"
Cohesion: 0.05
Nodes (12): CorpDTO, A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The descended-planet view: terrain + the planet's surface sites (§7, WP6)., RouteDTO, SurfaceDTO, EncounterDTO, Protocol (+4 more)

### Community 86 - "Community 86"
Cohesion: 0.11
Nodes (23): DiscoveryNamer, _fallback_prefix(), NameGenerator, Random, Deterministic naming generator based on configurable name pools., Draws names without replacement from a pool of combinations., Draws the next combination. Falls back to numbered prefix if exhausted., Names discoveries per kind from `names.discoveries` (PT-49, DESIGN §7).      One (+15 more)

### Community 87 - "Community 87"
Cohesion: 0.08
Nodes (28): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+20 more)

### Community 88 - "Community 88"
Cohesion: 0.14
Nodes (24): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+16 more)

### Community 89 - "Community 89"
Cohesion: 0.15
Nodes (10): ComposeResult, preserve_cursor(), DataTable, RowHighlighted, Keep the highlighted row stable across a clear()+repopulate refresh.      Textua, The commodities trade UI: a live pricing table over the docked port.      Reusab, Rebuild responsive columns while preserving the logical commodity selection., TradePanel (+2 more)

### Community 90 - "Community 90"
Cohesion: 0.22
Nodes (14): Console, _build_sheet(), _draw_sprite(), export_multipage_pdf(), export_sprite_sheet(), Path, Text, Vector export for the procedural sprites (dev-only sprite sheets).  Lays every r (+6 more)

### Community 91 - "Community 91"
Cohesion: 0.07
Nodes (46): CitadelError, Exception, A citadel build/treasury operation was rejected (raised by the reducers)., apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., Apply an engine cron's result: upsert entities + persist its durable trail., _generated(), test_advance_then_join_succeeds_and_is_exclusive() (+38 more)

### Community 92 - "Community 92"
Cohesion: 0.09
Nodes (36): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), WP27: logging a find into the codex pays experience_per_discovery., WP27 Core-law basics: a criminal crossing into the Core is put on notice, once, test_core_law_notice_for_criminals_only(), test_discovery_experience_awarded_on_codex_stamp(), The path from the start sector to Stardock opens pre-explored (round-2).      On, test_stardock_route_starts_explored() (+28 more)

### Community 93 - "Community 93"
Cohesion: 0.19
Nodes (19): list_portraits(), portraits_dir(), Path, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait() (+11 more)

### Community 94 - "Community 94"
Cohesion: 0.17
Nodes (21): BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), _cfg(), _commodity(), _event_owner() (+13 more)

### Community 95 - "Community 95"
Cohesion: 0.07
Nodes (46): player_foe(), Build the combat foe for a *defending player's* live ship (§14, WP67 — attacker-, HardwareItem, One row in the Stardock hardware emporium (UI_MOCKUPS.md §5, DESIGN §8)., build_layouts(), build_subsystems(), _counts(), derive_aspects() (+38 more)

### Community 96 - "Community 96"
Cohesion: 0.09
Nodes (42): _build_site(), _dist(), generate_survey(), _in_bounds(), _keepout(), _landing(), _move_cost(), _passable_components() (+34 more)

### Community 97 - "Community 97"
Cohesion: 0.08
Nodes (33): Game, A ship hull (DESIGN §4).      A player hull carries `subsystems` (the engine-roo, Holds occupied — trade cargo plus loose (uninstalled) components.          Loose, Top-level game record (DESIGN §4)., A fresh universe seeded from the game's seed (RNG owned here, §3)., Ship, _enemy_world(), An alliance-owned world in the player's sector, ready to invade (no base). (+25 more)

### Community 98 - "Community 98"
Cohesion: 0.06
Nodes (75): accrue_interest(), Compound interest on a bank balance (engine cron applies; math is pure)., _bfs_from(), _pick_by_distance(), plan_move(), Random, Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42)., Hop distance from the nearest `sources` node to every reachable sector (BFS). (+67 more)

### Community 99 - "Community 99"
Cohesion: 0.13
Nodes (17): LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Yield events as they are produced — the service pushes both apply + tick events., Run the embedded engine ticker until stopped (the app's engine worker, §3)., The embedded ticker (tests/shots that step it directly)., The wrapped in-process service (single-player back-compat; never used for remote, _config() (+9 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.12
Nodes (24): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), _discoveries(), format_route(), list_items(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers). (+16 more)

### Community 103 - "Community 103"
Cohesion: 0.11
Nodes (38): combat_contexts(), DialogueIntegrityError, _is_catch_all(), _placeholders_in(), Exception, Convenience: select a line for a live encounter and return (text, new recency ri, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3 (+30 more)

### Community 104 - "Community 104"
Cohesion: 0.14
Nodes (30): A node in the warp graph (DESIGN §4). `warps_out` are sector ids., Sector, build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., _one_way_span_world(), _phantom_bridges(), Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic., Dense spiral rings use their radial/tangential embedding, not one tall hop colum (+22 more)

### Community 105 - "Community 105"
Cohesion: 0.09
Nodes (41): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, One sector on the nav-rose trail breadcrumb (§11): its spatial id and distance, TrailCrumb, WarpDTO, esc(), Shared character-grid canvas and band palette for baked map/nav views (§11).  Bo (+33 more)

### Community 106 - "Community 106"
Cohesion: 0.12
Nodes (36): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A knocked-out part contributes nothing until it is patched (§4.1). (+28 more)

### Community 107 - "Community 107"
Cohesion: 0.19
Nodes (20): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), FindKind, generate_find_art() (+12 more)

### Community 108 - "Community 108"
Cohesion: 0.05
Nodes (49): Binding, Open the numbered context-action menu over the current screen (WP73, D3)., Shown while the terminal is below the 80×24 floor (WP-UI05).      It never traps, SizeNoticeScreen, Any, Screen, Return the one canonical advertised-action list for a screen.      Danger levels, screen_actions() (+41 more)

### Community 109 - "Community 109"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 110 - "Community 110"
Cohesion: 0.24
Nodes (9): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), test_every_archetype_has_responsive_service_art() (+1 more)

### Community 111 - "Community 111"
Cohesion: 0.18
Nodes (18): build_species_knowledge(), Random, Assign each present species **kind** a seeded subset of places it knows (§6.7)., Up to `k` distinct items drawn without replacement, weighted (deterministic)., _weighted_sample(), Phase-3 — location-intel planner + species knowledge table (DESIGN §6.7).  Cover, A placed species whose kind knows at least one place, plus a fresh player+ship., The reserved Entity codex row is Legendary but must never enter a knowledge tabl (+10 more)

### Community 112 - "Community 112"
Cohesion: 0.20
Nodes (5): LocalMapDTO, The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map(), Bake the local map to fit `width`, overlaying the active route (§6.7/§11).

### Community 113 - "Community 113"
Cohesion: 0.04
Nodes (48): Text, What an art panel drew last time, so a rebuilt screen doesn't blink (PT-42).  Se, The art this panel drew last time, or None if it has never been drawn., Record `art` as this panel's latest render and hand it back for painting., remember(), remembered(), layout_tier(), ComposeResult (+40 more)

### Community 114 - "Community 114"
Cohesion: 0.08
Nodes (35): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), Random, Ship, Subsystem (+27 more)

### Community 115 - "Community 115"
Cohesion: 0.14
Nodes (14): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., _depletion(), The 0..1 fraction of a belt's ore already mined out (0.0 for any other world, PT, _jovian(), _orbit(), WP-PR2-15c — the Cloud City orbit screen (playtest PT-54).  A gas giant explains (+6 more)

### Community 116 - "Community 116"
Cohesion: 0.09
Nodes (20): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+12 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.18
Nodes (19): _finalize_planets(), _host_markets(), _make_port(), _mid_stock(), _normalize_belts(), _place_starbases(), populate(), Random (+11 more)

### Community 119 - "Community 119"
Cohesion: 0.22
Nodes (5): Any, A `GameService`-shaped synchronous facade over the connected client., A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., RemoteService

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.12
Nodes (10): FieldPrompt, ComposeResult, Pressed, Static, Submitted, The shared one-field prompt: inline validation, no silent failures.      Subclas, Return (value, None) to accept or (None, reason) to hold the form open., A correction clears stale validation copy and restores stable form layout. (+2 more)

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
Cohesion: 0.18
Nodes (18): Adjacency, can_warp(), plan_route(), plan_route_legs(), Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For, The sectors reachable in one hop from `sector_id`., Whether a single direct warp `from_sector -> to_sector` is legal. (+10 more)

### Community 127 - "Community 127"
Cohesion: 0.36
Nodes (12): _do(), WP66 — corporations: shared bank + assets + corp war (DESIGN §4).  The core inva, Two players (both at sector 1) each with a ship; a planet p1 owns in that sector, test_ceo_leaving_promotes_lowest_id_member(), test_corp_asset_treats_every_member_as_owner(), test_corp_bank_is_non_negative_and_ceo_gated(), test_corp_war_is_mutual_and_hostility_follows(), test_dissolution_rekeys_assets_to_the_departing_ceo() (+4 more)

### Community 128 - "Community 128"
Cohesion: 0.08
Nodes (16): PlanetScreen, ComposeResult, Pressed, Static, Vertical, Keep identity, ownership, habitability, and colony state together., A belt's orbital readout (§4.2, WP-PR06): a spatial feature, scanned/mined, not, A gas giant's Cloud City: what floats there, and what building more would cost. (+8 more)

### Community 129 - "Community 129"
Cohesion: 0.36
Nodes (15): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+7 more)

### Community 130 - "Community 130"
Cohesion: 0.23
Nodes (16): _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7). (+8 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "Community 132"
Cohesion: 0.33
Nodes (5): LiveSysopService, Any, Event, Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC., Apply an intervention to the authoritative live game as the target player.

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "Community 135"
Cohesion: 0.17
Nodes (8): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., Static, Vertical, Widget, The base's standing, on one line, in a bordered panel above the installations.

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 137 - "._refresh_art"
Cohesion: 0.23
Nodes (14): WP-PR07 — settling more colonists onto an already-owned colony (playtest PT-11)., Every `TransferCargo` moves goods between ship holds and colony stores without, An owned colony with stores + a ship with cargo and free holds, same sector., _state(), test_batch_load_is_one_delta_and_shares_free_holds(), test_invalid_batch_is_atomic(), test_settle_clamps_to_aboard_and_habitability(), test_settle_rejected_on_uncolonizable_world() (+6 more)

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 142 - "TopologyModeConfig"
Cohesion: 0.15
Nodes (9): Every species' `home_band` hint must name a configured distance band (§6)., The parameters specific to one `topology_mode` (DESIGN §5).      Everything a mo, Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).      E, The config block for the selected `topology_mode` (§5 step 5)., The distance bands for the configured `topology_mode` (§5 step 5)., TopologyModeConfig, TopologySet, The config validator enforces same band names across modes (only thresholds (+1 more)

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (16): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, main(), Battle, Pressed, Screen (+8 more)

### Community 144 - "trader_step"
Cohesion: 0.29
Nodes (13): Run one trade for every NPC merchant working a port this firing (§8, WP43)., trader_step(), A 1-2-3 Frontier chain with a trading port at sector 2 (optionally a player ther, A `selvani` merchant (movement_policy trade_seek in the default roster ⇒ a trade, _selvani(), test_a_distant_player_is_not_warmed(), test_non_trader_species_never_trades(), test_trader_dumps_held_cargo_before_buying() (+5 more)

### Community 145 - "AmountPrompt"
Cohesion: 0.19
Nodes (4): AmountPrompt, ComposeResult, Pressed, Enter *in the amount field* commits: typing a number and pressing Enter is inten

### Community 146 - "webviz.py"
Cohesion: 0.24
Nodes (11): build_payload(), _classify_edges(), dump_json(), Any, Path, Render a generated universe to an interactive web page (DESIGN §5).  A dev-only, Write just the visualization payload to `path` (no HTML)., Write `index.html` + `universe.json` into `out_dir`; return the HTML path. (+3 more)

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
Cohesion: 0.31
Nodes (6): Random, Text, Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.  Un, Generates a frame of random low-contrast static ("snow")., Fill a `width` × `height` frame with weighted random noise glyphs.          `sub, StaticGenerator

### Community 155 - "market_view"
Cohesion: 0.21
Nodes (12): _event_player(), event_visible_to(), format_log_line(), market_view(), messages_view(), Event, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The acting/addressed player of an event, if any (its `player_id`/`owner_player_i (+4 more)

### Community 156 - "EmptyState"
Cohesion: 0.21
Nodes (6): EmptyState, Any, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches')., A consistent 'nothing here' block: what is empty and what fills it., SlotGlyphs, InputType

### Community 157 - "Community 157"
Cohesion: 0.25
Nodes (6): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, TabPane

### Community 158 - "DetailOverlay"
Cohesion: 0.18
Nodes (6): DetailOverlay, Any, ComposeResult, RowSelected, Vertical, The compact-tier row detail: every column (folded ones included).

### Community 159 - "SpeciesPortrait"
Cohesion: 0.21
Nodes (6): Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait., Render a species' portrait image (by `roster_id`) into its allotted cell box., SpeciesPortrait

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 161 - "detail_table.py"
Cohesion: 0.27
Nodes (6): _cell_markup(), _plain(), DetailTable — the standardized Computer table (WP-UI21).  One widget for every C, The stable key of the highlighted row, or None., Numeric-aware sort key: '1,240', 'S12', '87%' sort as numbers., _sort_value()

### Community 163 - "TavernDTO"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 164 - "LeadDTO"
Cohesion: 0.25
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 165 - "HaggleQuote"
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 167 - "MarketDTO"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

### Community 168 - ".apply"
Cohesion: 0.25
Nodes (5): Command, Event, Persisted events after `seq`, each with its seq — the reconnect catch-up buffer, Render one event for the live ticker, with a spatial sector gutter (§5.1, §11)., Validate, persist, and apply a command; return the events it produced.

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 171 - "test_ui_asteroid_belt.py"
Cohesion: 0.47
Nodes (5): _belt_dto(), WP-PR06 — the belt orbit screen hides colony/descent affordances (playtest PT-30, _terrestrial_dto(), test_belt_orbit_hides_descent_and_stores(), test_terrestrial_orbit_keeps_descent_and_stores()

### Community 173 - "CommodityPricing"
Cohesion: 0.50
Nodes (3): CommodityPricing, The pricing inputs for one commodity., Per-commodity pricing inputs for the §8 stock-ratio formula.

### Community 174 - "Community 174"
Cohesion: 0.40
Nodes (4): Debris, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, Scatter drifting-wreckage clumps across the midfield (graveyard     scenarios) —, seed_debris()

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 176 - "sprites.py"
Cohesion: 0.50
Nodes (3): pick_subsystem(), Engine-room subsystem icons for the TUI (UI_MOCKUPS.md §8).  The procedural `edg, The decorative ASCII icon for an engine-room subsystem (§8).

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

## Knowledge Gaps
- **54 isolated node(s):** `FindKind`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script`, `graphify` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Sector Scene & Widgets`, `Community 130`, `Standing, Corp & Combat Rules`, `Community 129`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `Attitude, Disposition & Contracts`, `._refresh_art`, `Engine-Room Component Workbench`, `TopologyModeConfig`, `Community 143`, `Dialogue-Pack Save Guard`, `trader_step`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `Game Lifecycle & Pathfinding`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Core Rules Tests`, `HaggleQuote`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 45`, `CommodityPricing`, `Community 48`, `Community 49`, `Community 59`, `Community 61`, `Community 68`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 79`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 89`, `Community 91`, `Community 94`, `Community 95`, `Community 97`, `Community 98`, `Community 99`, `Community 103`, `Community 104`, `Community 114`, `Community 117`, `Community 118`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Standing, Corp & Combat Rules` to `Core Rules & Events Engine`, `Community 130`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Attitude, Disposition & Contracts`, `Community 139`, `Domain Models & Colonizability`, `Engine-Room Component Workbench`, `TopologyModeConfig`, `Game Lifecycle & Pathfinding`, `Universe Embedding & Bearings`, `trader_step`, `webviz.py`, `The Entity & Command Reduce`, `Community 147`, `Market Orders & Regions`, `Config Schema Models`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `market_view`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 45`, `Community 49`, `Community 54`, `Community 59`, `Community 61`, `Community 71`, `Community 72`, `Community 73`, `Community 75`, `Community 77`, `Community 85`, `Community 91`, `Community 95`, `Community 96`, `Community 98`, `Community 99`, `Community 109`, `Community 114`, `Community 118`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Standing, Corp & Combat Rules` to `Core Rules & Events Engine`, `Community 130`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Attitude, Disposition & Contracts`, `._refresh_art`, `Domain Models & Colonizability`, `Engine-Room Component Workbench`, `Universe Embedding & Bearings`, `trader_step`, `webviz.py`, `The Entity & Command Reduce`, `Subsystem Layouts & Ownership`, `Market Orders & Regions`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `market_view`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Community 42`, `Community 45`, `Community 48`, `Community 49`, `Community 61`, `Community 70`, `Community 72`, `Community 73`, `Community 75`, `Community 77`, `Community 79`, `Community 85`, `Community 91`, `Community 94`, `Community 95`, `Community 96`, `Community 97`, `Community 98`, `Community 99`, `Community 102`, `Community 103`, `Community 104`, `Community 106`, `Community 111`, `Community 113`, `Community 118`, `Community 127`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 128 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 128 INFERRED edges - model-reasoned connections that need verification._
- **Are the 330 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 330 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._