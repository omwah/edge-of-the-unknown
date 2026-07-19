# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 334 files · ~9,155,222 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8056 nodes · 35162 edges · 188 communities (166 shown, 22 thin omitted)
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 11286 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ba8a057f`
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
- Community 133
- Community 134
- Community 136
- Community 140
- Community 141
- TopologyModeConfig
- Community 143
- trader_step
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
- Community 157
- Community 160
- TavernDTO
- LeadDTO
- HaggleQuote
- Community 166
- .apply
- Community 169
- Community 170
- CommodityPricing
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
1. `UniverseState` - 517 edges
2. `GameConfig` - 471 edges
3. `Commodity` - 426 edges
4. `reduce()` - 384 edges
5. `EconomyError` - 345 edges
6. `EdgeApp` - 259 edges
7. `Warp` - 234 edges
8. `apply_result()` - 233 edges
9. `ComponentTier` - 232 edges
10. `Event` - 219 edges

## Surprising Connections (you probably didn't know these)
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_species_knowledge_is_deterministic_bounded_and_referential()` --calls--> `generate()`  [EXTRACTED]
  tests/test_dialogue_intel.py → edge/bigbang/generator.py
- `test_every_discovery_is_named()` --calls--> `generate()`  [EXTRACTED]
  tests/test_discovery_names.py → edge/bigbang/generator.py
- `test_names_are_deterministic_from_the_seed()` --calls--> `generate()`  [EXTRACTED]
  tests/test_discovery_names.py → edge/bigbang/generator.py
- `test_core_pinned_to_origin()` --calls--> `generate()`  [EXTRACTED]
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

## Communities (188 total, 22 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.09
Nodes (441): _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup() (+433 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.02
Nodes (113): Container, Sizes/counts for the SectorView sprite scene (presentation only, no rules)., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, SectorDiscovery, SectorPlanetDTO (+105 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.03
Nodes (117): ArmamentItem, Aspect, BountyDTO, CommodityLine, ComputerDTO, CorpMemberDTO, DeploymentOptionDTO, DossierEntry (+109 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.02
Nodes (299): apply_resign_standing(), apply_spillover(), Reputation spillover from a `delta` attitude change toward `subject_id` (§6.4)., Leave the current bloc and let rival hostility lapse to neutral (§6.3, WP38)., Apply the consequences of destroying `kills` of a species' ships (§6.5, WP27)., sour_attitude(), GameConfig, Top-level config bundle, validated from the parsed YAML mapping. (+291 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.02
Nodes (169): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., EdgeApp, Any, Resize, Screen, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo (+161 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.01
Nodes (343): admission_met(), admission_tasks_done(), _alliance_key(), alliance_rivals(), alliance_standing(), alliance_standing_shift(), apply_join_standing(), attitude_locked() (+335 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.09
Nodes (16): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., first_focusable(), focus_content(), TabActivated, Widget, The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target)., Put keyboard focus on `node`'s primary control (see `first_focusable`).      Whe (+8 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.03
Nodes (118): _best_roundtrip_margin(), _check_degree_cap(), _check_discovery_gradient(), _check_expansive_no_chokepoint(), _check_home_clusters(), _check_planet_ownership(), _check_profitable_pair(), _check_reachable() (+110 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.10
Nodes (36): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+28 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.05
Nodes (46): One subsystem panel: its derived aspect and its slot grid (§4.1)., Subsystem, EmptyState, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches')., A consistent 'nothing here' block: what is empty and what fills it., _BayPanel, ComponentWorkbench, ComponentWorkbenchProfile (+38 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.11
Nodes (20): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+12 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.06
Nodes (62): range, generate_with_player(), Any, `generate()` then `enroll()` — the common "fresh game with player 1" setup., WP27: logging a find into the codex pays experience_per_discovery., WP27 Core-law basics: a criminal crossing into the Core is put on notice, once, test_core_law_notice_for_criminals_only(), test_discovery_experience_awarded_on_codex_stamp() (+54 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.19
Nodes (8): Any, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.04
Nodes (67): TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Tick off a Captain's objective (WP-UI11) — local progress only.          Called, Host the app in a browser via `textual-serve` (DESIGN §11, §15; WP68 remote)., _serve(), ContextStrip (+59 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.07
Nodes (70): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, A deterministic fingerprint of the live entity state (RNG/adjacency excluded)., state_hash(), _hostile(), Path (+62 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.04
Nodes (67): build_graph(), generate(), Build the warp graph and return its adjacency plus the region groups., Generate a validated universe from `(seed, config)`; raise on repeated failure., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, one_way_exits(), Targets reachable from `sector_id` with no return edge (sorted, deterministic). (+59 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.03
Nodes (187): accept(), Stamp an offered contract into an active one on the player's slate (WP57)., effective_trade_posture(), The species' trade posture as this player experiences it (§6.1/§6.2 — WP74)., apply_result(), Command, Upsert a reducer's new entities into the mutable container (sanctioned)., Validate `command` for `player_id` and return its delta + events. (+179 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.04
Nodes (52): Any, ComposeResult, DataTable, Horizontal, Pressed, RowHighlighted, Static, Submitted (+44 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.04
Nodes (121): _archetype(), assign_station_archetypes(), _builder(), Deterministic builder-archetype assignment for ports and orbital bases., Resolve the species whose configured archetype designed the structure., Stamp every structure's builder archetype after alien regions exist (§5)., HardwareItem, One row in the Stardock hardware emporium (UI_MOCKUPS.md §5, DESIGN §8). (+113 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.06
Nodes (42): The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_engine_room(), sample_planet(), sample_surface() (+34 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.14
Nodes (25): _port(), WP9 — fog-of-war projections: computer & map views (DESIGN §3, §9, §11)., An NPC-style flat hull (no subsystems) projects no panels, not an error., Each log line's `when` carries the game day + turn-of-day, day rolling on TurnsR, A friendly contact is visible as a present vessel so the player can see/hail it., _species(), test_commodity_line_trend_and_ratio_edges(), test_computer_view_empty_without_discovered_ports() (+17 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.03
Nodes (75): BaseModel, BaseServicesConfig, CorpConfig, CronCadenceConfig, DefenseConfig, DeviceConfig, EncountersConfig, GenesisConfig (+67 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.06
Nodes (67): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+59 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.11
Nodes (22): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+14 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.07
Nodes (67): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line() (+59 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.08
Nodes (56): AllianceLeadershipChanged, An internal coup swapped a bloc's leader (§6.3, WP51).      `old_leader_roster`/, apply_intrigue(), flip_core_governor(), GovernanceDelta, IntrigueDelta, _nearest_legal(), Change the Core's governing alliance and re-key everything that follows (§6.3, § (+48 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.15
Nodes (19): CronFn, The pure reducer for a persisted cron name (raises on an unknown name)., resolve_cron(), _noncore(), Path, WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage() (+11 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.16
Nodes (26): _apply(), _config(), Path, DevPatch dev/testing command — reducer behaviour + replay determinism.  Proves t, The golden-master rail: a DevPatch replays to an identical state hash., The dashboard reloads the DB after its remote service applies through the live g, The force_settlement op is a logged, replayable command — rebuild reproduces it., _state() (+18 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.18
Nodes (5): ContactDTO, A peaceful alien contact screen (§6, §6.7, §11)., The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any.

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (33): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+25 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.04
Nodes (57): CitadelError, Exception, A citadel build/treasury operation was rejected (raised by the reducers)., _clamp_ship_field(), DevPatchError, Exception, Ship, Field-specific validation for a ship integer set/add (raises on hard limits). (+49 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.09
Nodes (49): DrawFn, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., clear_filled(), desired_stock_frac(), generate_orders(), hinterland_drift() (+41 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.06
Nodes (50): apply_patch(), apply_patch_lines(), build_parser(), _build_patch(), cmd_governance(), cmd_list(), cmd_show(), _components() (+42 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (58): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+50 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (31): Brain, BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Path, Pressed (+23 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.06
Nodes (55): load_config(), load_config_with_sidecar(), load_default_config(), _merge_dialogue(), Any, Path, Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Load the bundled default config (`config/default.yaml`). (+47 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.05
Nodes (48): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., notify_success(), Any, The docked one-line screen header: bold title, optional muted context., TitleBar (+40 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.08
Nodes (22): A surface-exploration site on a descended planet (UI_MOCKUPS.md §4, §7).      `s, SurfaceSite, Any, ComposeResult, Pressed, RowHighlighted, Static, Style (+14 more)

### Community 42 - "Community 42"
Cohesion: 0.18
Nodes (18): _bfs_from(), _pick_by_distance(), plan_move(), _player_sectors(), _port_sectors(), Random, Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42)., Hop distance from the nearest `sources` node to every reachable sector (BFS). (+10 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (26): BotSetup, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, BotRunner, Command, Event, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69)., Drives one player of a game through the `ServiceProtocol` seam (dev-tier, WP60). (+18 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (28): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+20 more)

### Community 45 - "Community 45"
Cohesion: 0.06
Nodes (37): ABC, BaseException, CronResolver, Path, GameMeta, Command, Event, Path (+29 more)

### Community 46 - "Community 46"
Cohesion: 0.02
Nodes (117): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), One traversed sector on a plotted route — what the player reads (§11, WP14)., One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, RouteHopDTO, TechOfferDTO, Resize, Static (+109 more)

### Community 47 - "Community 47"
Cohesion: 0.19
Nodes (16): A named cluster from generation (DESIGN §4/§5)., Region, game_view(), The primary game-screen bundle for `player_id` (§11)., test_game_view_surfaces_governor_and_core_status(), _nav_world(), A small graph for the sidebar/gravity projections (WP-A).      Hops from the Cor, WP-UI13 projects immediate navigation facts without leaking hidden contents. (+8 more)

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (46): DataObject, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Random, Ship (+38 more)

### Community 49 - "Community 49"
Cohesion: 0.03
Nodes (134): advance_build(), building(), citadel_defense_mult(), citadel_foe(), conquer(), has_gun(), InvasionOutcome, level_config() (+126 more)

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (39): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+31 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.06
Nodes (28): GameScreen, Event, The live layout tier, computed from the app size directly (resize-event, Whether the sidebar fits — hidden on narrow terminals so the sector view, The event-log lines, most recent last (a single fallback when empty)., Open the fight screen, never a duplicate (WP-fix): a confirm-modal dismiss can, Route a movement interruption (§10, WP24): a violence opener pushes the, Open the unified base view for the starbase here (§4.2, WP80).          No longe (+20 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (36): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+28 more)

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (10): main(), PlaytestService, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable. (+2 more)

### Community 55 - "Community 55"
Cohesion: 0.13
Nodes (42): Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), A remote rules rejection compatible with every local rule-error catch.      JSON, RemoteError, RemoteRulesError, A stable hash of the protocol surface — client and server refuse a mismatch at h, wire_fingerprint(), _bound_session() (+34 more)

### Community 56 - "Community 56"
Cohesion: 0.06
Nodes (50): Procedural ASCII art generation logic., compose_horizontal(), flip_row(), HullStyle, Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port (+42 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (28): _compose(), _grammar_floor(), _mirror_row(), Random, Slot, Text, Expand a left-half row (centre column included) to a full symmetric row:     the, The shortest height this grammar can compose: the smallest part in each     slot (+20 more)

### Community 58 - "Community 58"
Cohesion: 0.13
Nodes (21): get_biome_feature(), _luminance(), any, OpenSimplex, Random, Text, Procedural terrain generation using OpenSimplex noise.  The *gameplay* band layo, Rec.601 perceived luminance of an (r, g, b) triple in 0..1. (+13 more)

### Community 59 - "Community 59"
Cohesion: 0.15
Nodes (13): _Coord, MeshTopology, Mesh topology builder (DESIGN §5)., Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who (+5 more)

### Community 60 - "Community 60"
Cohesion: 0.07
Nodes (39): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl (+31 more)

### Community 61 - "Community 61"
Cohesion: 0.03
Nodes (40): _assert_impl(), _assert_remote_impl(), _decode_any(), LinkLost, LocalClient, Any, Command, EncounterDTO (+32 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (17): HelpScreen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., Site, ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult (+9 more)

### Community 63 - "Community 63"
Cohesion: 0.07
Nodes (28): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, main() (+20 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (42): Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus() (+34 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (42): DialoguePack, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace, One conversational beat: its concept, extra placeholders, and Phase-2 reachabili, _branch_closure() (+34 more)

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
Cohesion: 0.12
Nodes (7): Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)., ComposeResult, Pressed, Vertical, What already sits in this sector, tabular (fog pre-applied upstream)., Apply the same projected blocker to accelerator keys as disabled buttons., TerritoryScreen

### Community 70 - "Community 70"
Cohesion: 0.10
Nodes (48): Sector-deployed fighters + mines holding a sector (DESIGN §10, WP41) — hashed st, SectorForce, fighter_foe(), force_in_sector(), NpcEntry, owner_tag(), The deployed force garrisoning `sector_id`, or None., A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all (+40 more)

### Community 71 - "Community 71"
Cohesion: 0.07
Nodes (38): Color, available_archetypes(), available_subtypes(), Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype(), Style (+30 more)

### Community 72 - "Community 72"
Cohesion: 0.05
Nodes (45): AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json(), get_backend(), OllamaBackend (+37 more)

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (51): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology, PlanarTopology (+43 more)

### Community 74 - "Community 74"
Cohesion: 0.11
Nodes (32): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar (+24 more)

### Community 75 - "Community 75"
Cohesion: 0.24
Nodes (14): hourly_port_economy(), market_settlement(), The hourly port-economy tick: order-book market, or the legacy regen (§8, WP47)., The daily order-book settlement: match the book, move goods+latinum, drip purses, _market_config(), _market_world(), A 1-2-3 chain with a shortage port (sector 2) and a surplus port (sector 3)., With the market disabled, `hourly_port_economy` is the exact legacy regen body. (+6 more)

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
Cohesion: 0.15
Nodes (7): PlanetSpriteSize, Footprint bounds (character cells) for one SectorView scene sprite.      A sprit, Planet sprite footprint: height is authored, width is *derived* as 2*height., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SpriteSize, test_scene_art_rejects_min_above_max()

### Community 80 - "Community 80"
Cohesion: 0.10
Nodes (25): DeployShip, main(), _make_starfield(), Battle, `edge-spacebattle` — the space-battle POC's Textual shell.  Throwaway UI (the `t, A static char-level starfield backdrop with dim placement-grid ticks., One fleet slot during deployment — a hull awaiting a cell and a facing., SpacebattleApp (+17 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (32): alien_dialogue_default.yaml (dialogue corpus), alien_dialogue_species.yaml (species grammars), alien_roster_default.yaml (species roster), default.yaml (game constants), Alien species disposition system, Alliances (rival blocs, join one at a time), Asteroid belt mining (finite reserves), Universe generation (Big Bang) (+24 more)

### Community 82 - "Community 82"
Cohesion: 0.10
Nodes (38): decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command(), encode_dto(), encode_event() (+30 more)

### Community 83 - "Community 83"
Cohesion: 0.19
Nodes (17): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), _parse_args(), Namespace (+9 more)

### Community 84 - "Community 84"
Cohesion: 0.04
Nodes (106): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random, Ship (+98 more)

### Community 85 - "Community 85"
Cohesion: 0.04
Nodes (13): CorpDTO, GameState, MarketDTO, A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The game-screen view bundle (the public counterpart of `UniverseState`)., RouteDTO (+5 more)

### Community 86 - "Community 86"
Cohesion: 0.06
Nodes (49): DiscoveryNamer, _fallback_prefix(), NameGenerator, Random, Deterministic naming generator based on configurable name pools., Draws names without replacement from a pool of combinations., Draws the next combination. Falls back to numbered prefix if exhausted., Names discoveries per kind from `names.discoveries` (PT-49, DESIGN §7).      One (+41 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (26): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.14
Nodes (24): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+16 more)

### Community 89 - "Community 89"
Cohesion: 0.17
Nodes (9): preserve_cursor(), DataTable, RowHighlighted, Keep the highlighted row stable across a clear()+repopulate refresh.      Textua, The commodities trade UI: a live pricing table over the docked port.      Reusab, Rebuild responsive columns while preserving the logical commodity selection., TradePanel, A base-hosted port is a Trade tab, not a second PortScreen navigation layer. (+1 more)

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (29): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+21 more)

### Community 91 - "Community 91"
Cohesion: 0.21
Nodes (4): PlaytestControls, Click, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 92 - "Community 92"
Cohesion: 0.10
Nodes (30): _hostile(), Path, WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., The golden rail: a journey with encounter rolls (and an engagement) reloads (+22 more)

### Community 93 - "Community 93"
Cohesion: 0.14
Nodes (26): list_portraits(), nebular_bloom(), portraits_dir(), Path, Text, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Run image `path` through chafa and return its decoded ANSI string (the cached un, A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35). (+18 more)

### Community 94 - "Community 94"
Cohesion: 0.17
Nodes (20): BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), _cfg(), _commodity(), _event_owner() (+12 more)

### Community 95 - "Community 95"
Cohesion: 0.25
Nodes (11): MarketOrderDTO, One open order on the Computer's Market tab (§8, WP48)., market_view(), The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, _booked_world(), `_world` with an order book: port 1 (explored) buys fuel, port 3 (unexplored) se, test_market_view_is_deterministic(), test_market_view_is_disabled_under_the_legacy_economy() (+3 more)

### Community 96 - "Community 96"
Cohesion: 0.06
Nodes (66): _build_site(), _cell_cost(), dig_trench(), _dist(), generate_survey(), _in_bounds(), _keepout(), _landing() (+58 more)

### Community 97 - "Community 97"
Cohesion: 0.24
Nodes (9): PortCommodity, One commodity line at a port: stock + the pricing inputs (DESIGN §8)., _game(), WP1 checks: enums, port-class triples, and the core domain models., test_models_are_frozen(), test_port_line_lookup(), test_rebuild_adjacency_projects_warps(), test_ship_hold_accounting() (+1 more)

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (41): accrue_interest(), alien_drift(), _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16)., Compound interest on every non-empty bank balance (§8)., _config(), _drift_world() (+33 more)

### Community 99 - "Community 99"
Cohesion: 0.24
Nodes (4): ActionMenuScreen, Any, ComposeResult, Screen

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.11
Nodes (26): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), _discoveries(), format_route(), list_items(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers). (+18 more)

### Community 103 - "Community 103"
Cohesion: 0.14
Nodes (33): combat_contexts(), DialogueIntegrityError, Exception, Convenience: select a line for a live encounter and return (text, new recency ri, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3, Assert the §13 dialogue-integrity invariants for a roster (raises on failure)., A roster's dialogue packs fail the §13 integrity checks. (+25 more)

### Community 104 - "Community 104"
Cohesion: 0.03
Nodes (130): Create the reserved hidden Legendary codex row for the Entity (DESIGN §7, WP35)., _reserve_entity_codex(), is_convoyed(), Whether a species instance is under escort by any player (§6.7, WP57).      A co, Discovery, DiscoveryPayload, Game, Lead (+122 more)

### Community 105 - "Community 105"
Cohesion: 0.08
Nodes (48): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), FindKind, generate_find_art() (+40 more)

### Community 106 - "Community 106"
Cohesion: 0.17
Nodes (25): _do(), WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, A knocked-out part contributes nothing until it is patched (§4.1)., A `subsystems=None` (NPC-style) hull has no engine room to operate on., A one-ship universe: the starter hull with its engine room built (§4.1)., The minimal starter layout must reproduce the Phase-1 balance exactly., A fourth spindrive part raises warp by per_component (Tier I adds nothing more)., A Tier-III part adds per_tier·(tier-1) on top of per_component. (+17 more)

### Community 107 - "Community 107"
Cohesion: 0.31
Nodes (8): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., ModuleType

### Community 108 - "Community 108"
Cohesion: 0.14
Nodes (24): Binding, _action_name(), _all_actions(), _bindings(), _method_source(), _pane_bindings(), Screen, WP-UI05/WP-UI06 — responsive shell and unified action discovery.  Static collisi (+16 more)

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
Cohesion: 0.22
Nodes (6): DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12)., The save was made with a different dialogue pack; replay would fail mid-way., EngineState, The persisted ticker schedule (WP12): the tick counter + each cron's next-due ti

### Community 113 - "Community 113"
Cohesion: 0.02
Nodes (132): ActiveBinding, AmountPrompt, EngineRoomPreviewDTO, Presentation-only before/after aspects for one prospective install or swap (WP-U, Enum, The economy: pricing, trade resolution, haggling, banking, stock regen (§8).  Pu, Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, GameService (+124 more)

### Community 114 - "Community 114"
Cohesion: 0.31
Nodes (9): _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, Every install/cannibalize moves a part between hold and slot — never creates or, A `subsystems=None` hull returns its flat scalars untouched (the NPC path)., test_install_cannibalize_conserve_components(), test_npc_flat_hull_derives_unchanged() (+1 more)

### Community 115 - "Community 115"
Cohesion: 0.29
Nodes (4): Generate a fresh universe on disk and start the background ticker.          The, Reload the saved game by replaying its command log (DESIGN §12).          Return, Validate art coverage and read scene-sprite sizes before a game starts., Run the client-owned engine ticker as a Textual worker (WP61).          The tick

### Community 116 - "Community 116"
Cohesion: 0.14
Nodes (13): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+5 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.33
Nodes (3): Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, Carried territory stock + devices for the Deploy screen (§10/§14, WP72).

### Community 119 - "Community 119"
Cohesion: 0.13
Nodes (9): Any, Sync bridge: drive an async `RemoteClient` from the synchronous TUI (WP68).  The, Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises)., A `GameService`-shaped synchronous facade over the connected client., A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., RemoteBridge (+1 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.50
Nodes (3): AssaultOperation, Frozen active-operation state for ground operations (GW-WP03, GW plan §Hashed st, A live tactical assault (GW plan D7-D11) — hashed core state.      Set on `Playe

### Community 122 - "Community 122"
Cohesion: 0.23
Nodes (3): OptionsScreen, ComposeResult, OptionsScreen — a minimal settings panel off the main menu (WP73, D5).  Local pr

### Community 123 - "Community 123"
Cohesion: 0.17
Nodes (17): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.22
Nodes (16): concourse_asset(), Path, Text, Static Stardock service raster selection and ANSI rendering.  The source artwork, Return the tab, theme, and layout-specific crop., Render a responsive service panel: 72×12 wide, 56×8 standard., Compatibility wrapper for the original PT-06 asset tests., Compatibility wrapper for the original PT-06 renderer. (+8 more)

### Community 125 - "Community 125"
Cohesion: 0.16
Nodes (12): fractal_noise(), OpenSimplex, Shared procedural-noise helpers for the art generators., Sum several octaves of noise so clusters break up at multiple scales.      Layer, Random, Text, Procedural starfield generation., Per-subtype knobs turning the noise field into stars.      threshold  - noise cu (+4 more)

### Community 126 - "test_ui_black_hole.py"
Cohesion: 0.14
Nodes (22): Adjacency, _annotate(), can_warp(), plan_route(), plan_route_legs(), Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For, The sectors reachable in one hop from `sector_id`. (+14 more)

### Community 127 - "Community 127"
Cohesion: 0.50
Nodes (4): note(), note_topic(), Record that `context` was spoken this visit (`asked.<context>: true`)., The session with one fact recorded (a no-op when it already holds).

### Community 128 - "Community 128"
Cohesion: 0.02
Nodes (100): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., AmountStepper, ComposeResult, Horizontal, Pressed, Shared exact-amount field with −/+ stepping for logistics and recruitment., An integer input followed by decrement/increment buttons. (+92 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.23
Nodes (16): _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7). (+8 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.07
Nodes (9): The Stardock services catalog (hardware + shipyard), fog-of-war scoped (§3)., StardockDTO, _assert_impl(), Command, EncounterDTO, Event, Protocol, The typed surface of the in-process game service (H16). (+1 more)

### Community 142 - "TopologyModeConfig"
Cohesion: 0.15
Nodes (9): Every species' `home_band` hint must name a configured distance band (§6)., The parameters specific to one `topology_mode` (DESIGN §5).      Everything a mo, Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).      E, The config block for the selected `topology_mode` (§5 step 5)., The distance bands for the configured `topology_mode` (§5 step 5)., TopologyModeConfig, TopologySet, The config validator enforces same band names across modes (only thresholds (+1 more)

### Community 143 - "Community 143"
Cohesion: 0.08
Nodes (13): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, Battle, Pressed, Screen, One roster slot during deployment — a named trooper awaiting a landing cell. (+5 more)

### Community 144 - "trader_step"
Cohesion: 0.17
Nodes (17): Run one trade for every NPC merchant working a port this firing (§8, WP43)., trader_step(), Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., A 1-2-3 Frontier chain with a trading port at sector 2 (optionally a player ther, A `selvani` merchant (movement_policy trade_seek in the default roster ⇒ a trade, A run of ticked trades (the WP12 rail) is deterministic — the same firings from, _selvani() (+9 more)

### Community 146 - "webviz.py"
Cohesion: 0.31
Nodes (8): build_payload(), _classify_edges(), Any, Render a generated universe to an interactive web page (DESIGN §5).  A dev-only, Write `index.html` + `universe.json` into `out_dir`; return the HTML path., Collapse the directed adjacency into display edges.      A warp `a→b` is two-way, Serialize the generated universe to the JSON shape the web page consumes., render_web()

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
Cohesion: 0.19
Nodes (13): _event_player(), event_visible_to(), messages_view(), The acting/addressed player of an event, if any (its `player_id`/`owner_player_i, Whether `player_id` should receive `event` under the fog-of-war broadcast policy, Project the durable event log into a newest-first message list (§11, §12)., P1 at sector 2 (charted 1-3); P2 at sector 4 (charted 4-5) — disjoint horizons., test_global_event_reaches_every_player() (+5 more)

### Community 157 - "Community 157"
Cohesion: 0.25
Nodes (6): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, TabPane

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

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

### Community 168 - ".apply"
Cohesion: 0.25
Nodes (5): Command, Event, Persisted events after `seq`, each with its seq — the reconnect catch-up buffer, Render one event for the live ticker, with a spatial sector gutter (§5.1, §11)., Validate, persist, and apply a command; return the events it produced.

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 173 - "CommodityPricing"
Cohesion: 0.50
Nodes (3): CommodityPricing, The pricing inputs for one commodity., Per-commodity pricing inputs for the §8 stock-ratio formula.

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
- **54 isolated node(s):** `FindKind`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script`, `graphify` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Community 128`, `Sector Scene & Widgets`, `Community 130`, `Standing, Corp & Combat Rules`, `Community 129`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `Community 141`, `TopologyModeConfig`, `Community 143`, `Dialogue-Pack Save Guard`, `The Entity & Command Reduce`, `trader_step`, `Subsystem Layouts & Ownership`, `Game Lifecycle & Pathfinding`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Core Rules Tests`, `HaggleQuote`, `CommodityPricing`, `Community 46`, `Community 47`, `Community 48`, `Community 49`, `Community 45`, `Community 55`, `Community 59`, `Community 61`, `Community 68`, `Community 70`, `Community 73`, `Community 74`, `Community 76`, `Community 79`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 89`, `Community 94`, `Community 97`, `Community 98`, `Community 103`, `Community 104`, `Community 112`, `Community 113`, `Community 117`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Standing, Corp & Combat Rules` to `Core Rules & Events Engine`, `Community 130`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `Domain Models & Colonizability`, `Community 141`, `TopologyModeConfig`, `Game Lifecycle & Pathfinding`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `webviz.py`, `Subsystem Layouts & Ownership`, `trader_step`, `Community 147`, `Config Schema Models`, `Bigbang Aliens & Region Control`, `market_view`, `Dev Patch Tooling`, `Server Net & Engine Ticker`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 43`, `Community 45`, `Community 47`, `Community 49`, `Community 54`, `Community 55`, `Community 59`, `Community 61`, `Community 70`, `Community 71`, `Community 73`, `Community 75`, `Community 77`, `Community 84`, `Community 85`, `Community 86`, `Community 91`, `Community 95`, `Community 96`, `Community 98`, `Community 102`, `Community 104`, `Community 109`, `Community 112`, `Community 113`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Standing, Corp & Combat Rules` to `Core Rules & Events Engine`, `Community 130`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `Domain Models & Colonizability`, `Community 141`, `Game Lifecycle & Pathfinding`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `webviz.py`, `Subsystem Layouts & Ownership`, `trader_step`, `Market Orders & Regions`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `market_view`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 45`, `Community 47`, `Community 48`, `Community 49`, `Community 61`, `Community 70`, `Community 73`, `Community 75`, `Community 77`, `Community 84`, `Community 85`, `Community 86`, `Community 94`, `Community 95`, `Community 96`, `Community 97`, `Community 98`, `Community 102`, `Community 103`, `Community 104`, `Community 106`, `Community 111`, `Community 113`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 337 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 337 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._