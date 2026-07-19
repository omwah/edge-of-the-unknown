# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 329 files · ~9,145,613 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 7893 nodes · 33671 edges · 191 communities (163 shown, 28 thin omitted)
- Extraction: 69% EXTRACTED · 31% INFERRED · 0% AMBIGUOUS · INFERRED: 10457 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5c9edf08`
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
- Community 139
- Community 140
- Community 141
- Community 143
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 164
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
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
1. `UniverseState` - 494 edges
2. `GameConfig` - 436 edges
3. `Commodity` - 419 edges
4. `reduce()` - 365 edges
5. `EconomyError` - 332 edges
6. `EdgeApp` - 259 edges
7. `ComponentTier` - 230 edges
8. `Warp` - 228 edges
9. `apply_result()` - 222 edges
10. `Event` - 212 edges

## Surprising Connections (you probably didn't know these)
- `test_roster_archetypes_have_palettes()` --calls--> `available_archetypes()`  [EXTRACTED]
  tests/test_art_coverage.py → edge/art/generator.py
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_an_alliance_gas_giant_is_generated_with_a_city()` --calls--> `generate()`  [EXTRACTED]
  tests/test_cloud_city.py → edge/bigbang/generator.py
- `test_species_knowledge_is_deterministic_bounded_and_referential()` --calls--> `generate()`  [EXTRACTED]
  tests/test_dialogue_intel.py → edge/bigbang/generator.py
- `test_roster_rejects_duplicate_species_id()` --indirect_call--> `ValidationError`  [INFERRED]
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

## Communities (191 total, 28 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.10
Nodes (405): _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup() (+397 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.03
Nodes (87): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, SectorDiscovery, SectorPlanetDTO, SectorShipDTO (+79 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.03
Nodes (79): ArmamentItem, Aspect, BountyDTO, CommodityLine, ComputerDTO, CorpMemberDTO, DeploymentOptionDTO, DossierEntry (+71 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.03
Nodes (214): player_corp(), player_owns(), The corporation a player belongs to, or None (§4, WP66)., Whether `player_id` counts as an owner of a holding (§4.2/§4-WP66).      True fo, apply_dev_patch(), _expire_contract(), _force_settlement(), _moderate_notice() (+206 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.02
Nodes (156): MapNodeDTO, One traversed sector on a plotted route — what the player reads (§11, WP14)., A clickable sector node on the local map: its label's cell box in `rows`.      `, RouteHopDTO, EdgeApp, Resize, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo (+148 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.02
Nodes (173): alliance_standing_shift(), base_owner_hostile(), grudge_shift(), The greeting-vs-violence penalty from ill standing with a species' bloc (§6.3)., Whether an operational base's owner treats the player as an enemy (§4.2, WP40)., The active-grudge penalty this species applies to the player (§6.5, §10).      T, effective_sensor(), entity_codex_discovery() (+165 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.03
Nodes (57): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., notify_warning(), ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state). (+49 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.08
Nodes (37): may_occupy(), `a`'s stance toward `b` on a −1..1 scale (§6.4) — asymmetric, alliance-derived., Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules, WP16, species_relation(), _occupy_species(), _player(), WP7 — friendly alien species & roster (DESIGN §6, §13).  Covers the pure-core di, Band-graded placement (§5/§6): the Hub is peaceable (every innermost-band specie (+29 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.11
Nodes (26): ComposeResult, Pressed, Submitted, Enter in a row's amount field submits that row in the colony-supply direction, A modal transfer editor for the player-owned world in the current sector., TransferWorkbenchScreen, _has_scrollable_ancestor(), _new_game() (+18 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.06
Nodes (64): decay_grudges(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called., accept(), active(), advance_convoy(), apply_reward(), by_id(), complete_destroy_on_kill() (+56 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.05
Nodes (46): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), _archetype() (+38 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.03
Nodes (133): alliance_rivals(), apply_spillover(), attitude_locked(), attitude_offset(), disposition_band(), effective_disposition(), Name the band a disposition value falls in (hostile / neutral / friendly, §6)., Reputation spillover from a `delta` attitude change toward `subject_id` (§6.4). (+125 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.06
Nodes (60): is_colonizable(), Whether a world of this type can be claimed and settled (§4.2).      Colonizable, range, enroll(), generate_with_player(), Any, Shared test helpers.  The big bang no longer seeds players — enrolling a player, Enroll a player into an already-generated universe (mutates + returns `state`). (+52 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.04
Nodes (53): One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).      `s, One subsystem panel: its derived aspect and its slot grid (§4.1)., Slot, Subsystem, ContextStrip, EmptyState, Any, ComposeResult (+45 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.04
Nodes (52): DialogueConfigMismatchError, RuntimeError, The save was made with a different dialogue pack; replay would fail mid-way., main(), Any, Screen, EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Persist local-only presentation settings and apply the theme immediately. (+44 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.05
Nodes (85): _build_game(), Load the game at `db` if it exists, else generate a fresh one there (WP12 resume, Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, Path, SqliteRepository, A deterministic fingerprint of the live entity state (RNG/adjacency excluded)., state_hash() (+77 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.03
Nodes (117): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+109 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.07
Nodes (76): instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting(), _cfg_with_oath(), _cfg_with_repeat_greeting() (+68 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.03
Nodes (78): layout_tier(), clear_slot(), Remove the save and its WAL/SHM sidecars so a new game starts clean., ComposeResult, Pressed, RumorModal — reveals the lead a tavern rumour just bought (WP-PR2-03 / PT-35)., RumorModal, _DockStructureArt (+70 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.05
Nodes (91): load_config(), Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Load and validate a YAML game config from `path`.      A `roster_file:` pointer, build_layouts(), Instantiate intact subsystems from a layout mapping (§4.1).      Base components, Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe, An orbital starbase (DESIGN §4.2): the engine-room model minus mobility.      A (+83 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.03
Nodes (82): EncounterDTO, The live hostile encounter (§10, WP24/25) — the encounter screen's projection., The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The live combat DTO used by the responsive EncounterScreen snapshots., The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_encounter_view() (+74 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.06
Nodes (61): MarketOrderDTO, One open order on the Computer's Market tab (§8, WP48)., A named cluster from generation (DESIGN §4/§5)., Region, _event_player(), event_visible_to(), game_view(), market_view() (+53 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.02
Nodes (180): BaseModel, citadel_foe(), conquer(), InvasionOutcome, _levels(), Random, Citadels — planetary defense levels, treasury, timed builds, and the gun (§4.2,, The immobile foe a planet's citadel gun fields in sector defense (§4.2, WP54). (+172 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.06
Nodes (65): attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate(), _int(), literalist() (+57 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.06
Nodes (77): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random, Ship (+69 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.07
Nodes (66): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line() (+58 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.07
Nodes (50): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+42 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.03
Nodes (106): admission_met(), admission_tasks_done(), _alliance_key(), alliance_standing(), apply_join_standing(), apply_resign_standing(), _clamp01(), core_bases_razed() (+98 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.07
Nodes (51): _clamp_ship_field(), DevPatchError, Exception, Ship, Field-specific validation for a ship integer set/add (raises on hard limits)., A malformed or impossible dev patch (unknown target, missing entity, bad key)., Apply a set/add op to a current integer., _resolve() (+43 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.04
Nodes (30): CronTask, EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., _QueuedCommand, GameService (+22 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (35): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+27 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.06
Nodes (33): _amain(), _encode_any(), _error(), GameServer, LobbyServer, Any, Command, Event (+25 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.09
Nodes (49): DrawFn, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., clear_filled(), desired_stock_frac(), generate_orders(), hinterland_drift() (+41 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.06
Nodes (47): apply_patch(), build_parser(), _build_patch(), cmd_governance(), cmd_list(), cmd_show(), _components(), _diff_after() (+39 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.13
Nodes (38): _do(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., A hunted player is turned away at the Core Stardock; others dock freely (WP52)., Give the docked ship the starter engine room (so install/derive applies)., Place an unowned colonizable world in the player's sector (2)., Sectors 1<->2; a Stardock (sells all) sits in sector 2 with the player., test_bank_deposit_then_withdraw(), test_buy_component_costs_latinum_and_fills_a_hold() (+30 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (31): Brain, BotRecord, The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Path (+23 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.06
Nodes (43): load_default_config(), _merge_dialogue(), Any, Load the bundled default config (`config/default.yaml`)., Fold one dialogue document onto a roster dict in place (DESIGN §6.7).      Two s, Any, Validate an already-parsed mapping (e.g. from YAML) into a GameConfig., Generate a fresh universe on disk and start the background ticker.          The (+35 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.06
Nodes (36): BaseScreen, ComposeResult, Static, Vertical, Widget, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th, The visible service tab's id (the unit every action keys on)., The `.` menu / `?` help / palette list, scoped exactly like the footer (PT-32). (+28 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 42 - "Community 42"
Cohesion: 0.06
Nodes (69): _best_roundtrip_margin(), _check_degree_cap(), _check_discovery_gradient(), _check_expansive_no_chokepoint(), _check_home_clusters(), _check_planet_ownership(), _check_profitable_pair(), _check_reachable() (+61 more)

### Community 43 - "Community 43"
Cohesion: 0.06
Nodes (36): `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`). (+28 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (26): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+18 more)

### Community 45 - "Community 45"
Cohesion: 0.06
Nodes (34): ABC, BaseException, CronResolver, GameMeta, Command, Event, Persistence behind a repository interface (DESIGN §12).  `Repository` is the abs, Events appended after `seq`, each with its own seq — the reconnect replay buffer (+26 more)

### Community 46 - "Community 46"
Cohesion: 0.04
Nodes (39): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, TechOfferDTO, Resize, Static, Text, Render a species' portrait image (by `roster_id`) into its allotted cell box. (+31 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (28): AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed, Shared exact-amount field with −/+ stepping for logistics and recruitment., An integer input followed by decrement/increment buttons., Clamp an over-cap typed value back to `maximum` in place, so the field can (+20 more)

### Community 48 - "Community 48"
Cohesion: 0.08
Nodes (52): DataObject, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Enum (+44 more)

### Community 49 - "Community 49"
Cohesion: 0.04
Nodes (94): advance_build(), building(), citadel_defense_mult(), has_gun(), level_config(), open_build(), Whether `planet` fields an operational citadel gun (§4.2, WP54/WP55)., Whether the L3 siege shield bars invasion of `planet` (§4.2, WP55).      True wh (+86 more)

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (40): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+32 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.07
Nodes (21): Any, ComposeResult, Pressed, RowHighlighted, Static, Style, Text, The right-hand panel: procedural entity art for the highlighted surface site. (+13 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (38): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+30 more)

### Community 54 - "Community 54"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 55 - "Community 55"
Cohesion: 0.12
Nodes (47): Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), A remote rules rejection compatible with every local rule-error catch.      JSON, RemoteError, RemoteRulesError, One connected client: the socket, the authenticated account, and the seat it hol, Session, A stable hash of the protocol surface — client and server refuse a mismatch at h (+39 more)

### Community 56 - "Community 56"
Cohesion: 0.06
Nodes (47): compose_horizontal(), flip_row(), Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo (+39 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (28): _compose(), _grammar_floor(), _mirror_row(), Random, Slot, Text, Expand a left-half row (centre column included) to a full symmetric row:     the, The shortest height this grammar can compose: the smallest part in each     slot (+20 more)

### Community 58 - "Community 58"
Cohesion: 0.09
Nodes (24): Procedural ASCII art generation logic., cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text (+16 more)

### Community 59 - "Community 59"
Cohesion: 0.04
Nodes (65): _Coord, HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology (+57 more)

### Community 60 - "Community 60"
Cohesion: 0.04
Nodes (44): _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl, The same actionable Stardock service projections the regular client receives. (+36 more)

### Community 61 - "Community 61"
Cohesion: 0.04
Nodes (24): Carried territory stock + devices + this sector's force (§10/§14 — WP72)., The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, TerritoryDTO, _decode_any(), LinkLost, Any, EncounterDTO (+16 more)

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
Cohesion: 0.07
Nodes (45): DialoguePack, npc_stance(), `a`'s live stance toward `b` (§6.4) — the relation matrix minus any active grudg, AliensConfig, A named species roster (DESIGN §6): alliances + the species pool drawn from., Dialogue/diplomacy reference integrity (§6, §13): ids and hooks resolve., Disposition thresholds + escape floor for the alien system (DESIGN §6, §10)., RosterConfig (+37 more)

### Community 66 - "Community 66"
Cohesion: 0.16
Nodes (7): Any, HeaderSelected, OptionSelected, RowSelected, Two-pane sysop dashboard: nav left, view right, audit trail below., Enter/click on a players or standings row opens its full dossier., SysopApp

### Community 67 - "Community 67"
Cohesion: 0.07
Nodes (29): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+21 more)

### Community 68 - "Community 68"
Cohesion: 0.17
Nodes (7): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The context-appropriate action list, one usage line each., Warp

### Community 69 - "Community 69"
Cohesion: 0.02
Nodes (108): ActiveBinding, AmountPrompt, Container, AmountPrompt, EdgeScreen, FieldPrompt, notify_success(), Pressed (+100 more)

### Community 70 - "Community 70"
Cohesion: 0.13
Nodes (38): owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, _force(), _generated(), _make_hostile(), _mini_state(), WP41 — sector fighters, mines, beacons, black-hole hazards (§10).  Covers the pu, A lethal hazard routes through the WP26 escape pod (WP75 — the A5 seam closed). (+30 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (36): Color, available_subtypes(), Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, planet_subtype(), port_subtype(), Style, Text, Bridge between the game's typed DTOs and the standalone `edge.art` engine.  `edg (+28 more)

### Community 72 - "Community 72"
Cohesion: 0.10
Nodes (7): PlaytestService, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable., A duck-typed stand-in for `GameService` exposing just what `AlienContactScreen`

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (39): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., combat_contexts(), Resolve and render one line for `context`, returning (text, updated recency ring, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3 (+31 more)

### Community 75 - "Community 75"
Cohesion: 0.08
Nodes (46): CitadelError, Exception, A citadel build/treasury operation was rejected (raised by the reducers)., Command, Validate `command` for `player_id` and return its delta + events., reduce(), _dirty_belt(), WP-PR06 — asteroid belts are spatial features, not colony worlds (playtest PT-30 (+38 more)

### Community 76 - "Community 76"
Cohesion: 0.12
Nodes (18): Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Deployed forces as glyph-scale presence marks — fighters flying patrol         t (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.09
Nodes (26): HardwareItem, One row in the Stardock hardware emporium (UI_MOCKUPS.md §5, DESIGN §8)., build_subsystems(), legal_components(), Subsystem, The components installable into `subsystem` on this hull (config layout)., Instantiate a hull's starting subsystems from its config layout (§4.1).      Ret, engine_room_view() (+18 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (14): Battle, Event, Side, One cell of rocky debris (belt scenarios). Blocks fire lines and wings;     dest, A missile salvo in flight — a board object chasing its target ship., One log/FX entry drained by the UI after each rules call., A ship (any footprint cell), wing, rock, or wreckage sits here — one         pie, Every board cell of the piece's footprint (anchored on the centre).         Ship (+6 more)

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (21): LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered(), _label(), pick_intel_target() (+13 more)

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
Cohesion: 0.18
Nodes (18): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), main(), _parse_args() (+10 more)

### Community 84 - "Community 84"
Cohesion: 0.10
Nodes (29): _footer_keys(), _open_computer(), PT-32 — the Computer's keyboard model: a tab owns its keys.  The screen binds on, chrome.EdgeScreen pins Back first — it used to fall in behind whatever the     f, PT-51: `P` on the Map plots a course to the highlighted sector and lands on the, Each category pane owns 1..N for its own sub-tabs — so `2` means a different tab, The corporation lives under Relations now, not behind a game-screen hotkey., Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+21 more)

### Community 85 - "Community 85"
Cohesion: 0.05
Nodes (15): CorpDTO, MarketDTO, A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, RouteDTO, _assert_impl(), Command (+7 more)

### Community 86 - "Community 86"
Cohesion: 0.06
Nodes (40): _make_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, Populate `state.discoveries` deterministically from the seed (§7)., _roll_kind(), _roll_tier(), salt_discoveries() (+32 more)

### Community 87 - "Community 87"
Cohesion: 0.13
Nodes (20): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., _Bot, _decision(), _LLM (+12 more)

### Community 88 - "Community 88"
Cohesion: 0.07
Nodes (42): Notice, One posted noticeboard message (DESIGN §14 — WP58).      A captain's log pinned, apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., §6.5: a finite grudge cools by the holder's gain rate per day and lapses; a, test_grudge_decay_is_deterministic_through_the_daily_timeline(), _generated(), WP38 — joinable alliances: admission, rival fallout, Core law (§6.3, §10).  Cove (+34 more)

### Community 89 - "Community 89"
Cohesion: 0.17
Nodes (8): ComposeResult, preserve_cursor(), DataTable, RowHighlighted, Keep the highlighted row stable across a clear()+repopulate refresh.      Textua, The commodities trade UI: a live pricing table over the docked port.      Reusab, Rebuild responsive columns while preserving the logical commodity selection., TradePanel

### Community 90 - "Community 90"
Cohesion: 0.11
Nodes (31): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+23 more)

### Community 91 - "Community 91"
Cohesion: 0.05
Nodes (50): load_config_with_sidecar(), Path, Build a `GameConfig` with `sidecar` spliced onto the default roster (no integrit, Merge a generated dialogue sidecar onto the default roster and run §13 integrity, validate_sidecar(), AnthropicBackend, AntigravityBackend, Backend (+42 more)

### Community 92 - "Community 92"
Cohesion: 0.10
Nodes (29): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothi (+21 more)

### Community 93 - "Community 93"
Cohesion: 0.16
Nodes (21): list_portraits(), portraits_dir(), Path, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait() (+13 more)

### Community 94 - "Community 94"
Cohesion: 0.12
Nodes (25): BotSetup, CronFn, BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Enrol a bot on `player_id` and let `setup` register its triggers + turn driver., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69) (+17 more)

### Community 95 - "Community 95"
Cohesion: 0.16
Nodes (8): Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end., Answer queued general questions without executing or budgeting an action., Separate queued queries from persistent objective changes., Sleep out the remainder of the pace window, waking promptly on stop., The human TUI's StatusSidebar, condensed to three lines of plain text.      Same, sidebar()

### Community 96 - "Community 96"
Cohesion: 0.16
Nodes (15): expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar, Every authored expansion string in a grammar (for placeholder validation)., _entry_strings(), Every authored template string in an entry (variant pool + grammar expansions)., _grammar_pack() (+7 more)

### Community 97 - "Community 97"
Cohesion: 0.17
Nodes (16): _discoveries(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers)., The spatial display id for an internal sector id, or `—` if none is cached., A sector reference as `internal/spatial` (the §5.1 dual id)., Reverse the internal→spatial map (spatial ids are a bijection, §5.1)., Resolve a `--route` endpoint token to an internal sector id.      Accepts an int (+8 more)

### Community 98 - "Community 98"
Cohesion: 0.04
Nodes (105): entity_species(), The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None., Grudge, A durable, dated grievance (DESIGN §4, §6.5) — the diplomacy layer's memory., _bfs_from(), _grudge_targets(), is_trader(), movement_policy() (+97 more)

### Community 99 - "Community 99"
Cohesion: 0.05
Nodes (30): ContactDTO, HaggleQuote, A peaceful alien contact screen (§6, §6.7, §11)., A read-only read on a counter-offer before the player commits it (§8).      `fai, _assert_impl(), _assert_remote_impl(), GameClient, LocalClient (+22 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.11
Nodes (31): Adjacency, _annotate(), can_warp(), plan_route(), plan_route_legs(), Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For (+23 more)

### Community 103 - "Community 103"
Cohesion: 0.20
Nodes (20): DialogueIntegrityError, _is_catch_all(), _placeholders_in(), Exception, Assert the §13 dialogue-integrity invariants for a roster (raises on failure)., A roster's dialogue packs fail the §13 integrity checks., validate_dialogue(), test_humanoid_diplomat_persona_passes_dialogue_integrity() (+12 more)

### Community 104 - "Community 104"
Cohesion: 0.20
Nodes (22): build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., _phantom_bridges(), Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic., Pairs of *non-adjacent* sectors joined on one row by an unbroken, arm-connected, A small branching universe:  1 - 2 - 3 - 4  with a 2 - 5 - 6 spur.      Core hop, _rows(), _strip() (+14 more)

### Community 105 - "Community 105"
Cohesion: 0.09
Nodes (39): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, WarpDTO, esc(), Shared character-grid canvas and band palette for baked map/nav views (§11).  Bo, Escape Rich-markup-significant characters in literal cell text., build_nav_strip() (+31 more)

### Community 106 - "Community 106"
Cohesion: 0.12
Nodes (34): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A knocked-out part contributes nothing until it is patched (§4.1). (+26 more)

### Community 107 - "Community 107"
Cohesion: 0.17
Nodes (21): Expedition mode's Textual screens (the peaceful branch of edge-groundwar).  Same, _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), FindKind (+13 more)

### Community 108 - "Community 108"
Cohesion: 0.15
Nodes (23): Binding, _action_name(), _all_actions(), _bindings(), _method_source(), _pane_bindings(), Screen, WP-UI05/WP-UI06 — responsive shell and unified action discovery.  Static collisi (+15 more)

### Community 109 - "Community 109"
Cohesion: 0.15
Nodes (19): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), format_route(), list_items(), Render one category of populated universe items as an id-keyed table., Resolve two endpoints (internal or spatial id) and plot the fewest-hop route., main(), CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--stats] [--render DIR]`. (+11 more)

### Community 110 - "Community 110"
Cohesion: 0.15
Nodes (18): get_biome_feature(), _luminance(), OpenSimplex, Random, Text, Procedural terrain generation using OpenSimplex noise.  The *gameplay* band layo, Rec.601 perceived luminance of an (r, g, b) triple in 0..1., `fg` unchanged if it reads against `bg`, else a hue-preserving variant     (ligh (+10 more)

### Community 111 - "Community 111"
Cohesion: 0.25
Nodes (14): Lead, A coordinate tip the player accepted from an alien (DESIGN §6.7, the "map" mecha, Phase-3 — location-intel planner + species knowledge table (DESIGN §6.7).  Cover, A placed species whose kind knows at least one place, plus a fresh player+ship., The reserved Entity codex row is Legendary but must never enter a knowledge tabl, _speaker_with_knowledge(), _state(), test_entity_tip_is_live_and_outranks_regular_tips() (+6 more)

### Community 112 - "Community 112"
Cohesion: 0.20
Nodes (5): LocalMapDTO, The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map(), Bake the local map to fit `width`, overlaying the active route (§6.7/§11).

### Community 113 - "Community 113"
Cohesion: 0.29
Nodes (9): _noncore(), WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., The projection greys FIGHT with the very string the reducer raises (lockstep)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage(), test_attack_on_a_noncombatant_is_pointless(), test_attack_on_an_influence_gate_species_is_stayed(), test_attack_on_the_entity_finds_no_lock() (+1 more)

### Community 114 - "Community 114"
Cohesion: 0.10
Nodes (14): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., first_focusable(), focus_content(), TabActivated, Widget, The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target)., Put keyboard focus on `node`'s primary control (see `first_focusable`).      Whe (+6 more)

### Community 115 - "Community 115"
Cohesion: 0.18
Nodes (19): _finalize_planets(), _host_markets(), _make_port(), _mid_stock(), _normalize_belts(), _place_starbases(), populate(), Random (+11 more)

### Community 116 - "Community 116"
Cohesion: 0.14
Nodes (13): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+5 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.31
Nodes (9): WP74 — the signature-mechanic corpus routes (SEAMS_PLAN A2, decision D4).  The s, Each carrier species' pack routes a choice into its own sig.* namespace (A2 clos, test_alliance_gated_trade_opens_for_sworn_members(), test_escalating_demand_ladder_climbs_and_betrayal_is_permanent(), test_every_dark_hook_has_a_corpus_route(), test_flee_drop_route_pays_once(), test_reprogram_install_flips_the_helot_trade_posture_live(), test_trojan_gift_route_pays_sweetener_then_defuses_for_a_fee() (+1 more)

### Community 119 - "Community 119"
Cohesion: 0.08
Nodes (16): Any, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade, Any (+8 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.17
Nodes (19): _drop_entity(), _inject(), _knows_a_far_discovery(), Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7), Log-coordinates is a reply on the offer_coordinates node, not the greeting — you, Remove the roaming Entity so a test can isolate the regular coordinate-tip mecha, Point the species' knowledge at a real, reachable, unexplored rare+ discovery., test_accept_lead_without_a_tip_is_rejected() (+11 more)

### Community 122 - "Community 122"
Cohesion: 0.23
Nodes (3): OptionsScreen, ComposeResult, OptionsScreen — a minimal settings panel off the main menu (WP73, D5).  Local pr

### Community 123 - "Community 123"
Cohesion: 0.17
Nodes (17): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.14
Nodes (23): concourse_asset(), Path, Text, Static Stardock service raster selection and ANSI rendering.  The source artwork, Return the tab, theme, and layout-specific crop., Render a responsive service panel: 72×12 wide, 56×8 standard., Compatibility wrapper for the original PT-06 asset tests., Compatibility wrapper for the original PT-06 renderer. (+15 more)

### Community 125 - "Community 125"
Cohesion: 0.16
Nodes (12): fractal_noise(), OpenSimplex, Shared procedural-noise helpers for the art generators., Sum several octaves of noise so clusters break up at multiple scales.      Layer, Random, Text, Procedural starfield generation., Per-subtype knobs turning the noise field into stars.      threshold  - noise cu (+4 more)

### Community 127 - "Community 127"
Cohesion: 0.36
Nodes (12): _do(), WP66 — corporations: shared bank + assets + corp war (DESIGN §4).  The core inva, Two players (both at sector 1) each with a ship; a planet p1 owns in that sector, test_ceo_leaving_promotes_lowest_id_member(), test_corp_asset_treats_every_member_as_owner(), test_corp_bank_is_non_negative_and_ceo_gated(), test_corp_war_is_mutual_and_hostility_follows(), test_dissolution_rekeys_assets_to_the_departing_ceo() (+4 more)

### Community 128 - "Community 128"
Cohesion: 0.04
Nodes (43): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., _citadel_stage(), _depletion(), Descend, PlanetScreen, PlanetSprite (+35 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.15
Nodes (13): _line_universe(), Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal, test_movement_errors_name_the_spatial_id_not_the_internal_one(), test_travel_to_a_lead_off_its_origin_sector_is_charted_only(), test_travel_to_a_logged_lead_flies_the_full_graph() (+5 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "Community 132"
Cohesion: 0.20
Nodes (5): Open the numbered context-action menu over the current screen (WP73, D3)., ActionMenuScreen, Any, ComposeResult, Screen

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "Community 135"
Cohesion: 0.27
Nodes (10): Ship, Service-point resolution — where a ship may repair, buy, and bank (§4.1, §4.2, W, The provider serving a ship's current sector (§4.2, WP53).      `kind` is ``"sta, The service provider for the ship's current sector, or None (§4.1/§4.2, WP53)., The service point offering `service` here, or raise (the reducer gate, WP53)., require_service(), service_point(), ServicePoint (+2 more)

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.28
Nodes (9): _entity_world(), A generated world with the Concordance placed in the player's sector., A virtuous player is blessed: stage persisted, attitude up, experience paid, spo, A criminal player is cursed: a permanent grudge forms (never_forgets Entity)., The judgment command replays to the identical state hash (the stage-ladder rail), _submit(), test_judgment_reducer_blesses(), test_judgment_reducer_curses_with_grudge() (+1 more)

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (19): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, main(), Battle, Pressed, Screen (+11 more)

### Community 145 - "Community 145"
Cohesion: 0.43
Nodes (7): _first_filled(), Hang a base off a planet in the player's sector (2); return the base., test_salvage_derelict_starbase_conserves_components(), test_salvage_operational_starbase_rejected(), test_salvage_player_owned_operational_base_allowed(), test_salvage_requires_base_in_sector(), _with_starbase()

### Community 146 - "Community 146"
Cohesion: 0.40
Nodes (4): _load(), main(), Namespace, `edge-playtest-dialogue` entry point — open the dialogue playtest TUI.

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

### Community 157 - "Community 157"
Cohesion: 0.22
Nodes (7): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, Grid, TabPane

### Community 159 - "Community 159"
Cohesion: 0.50
Nodes (4): _quill_state(), A fresh game plus one hand-placed quill kind in the player's sector., WP27 arithmetic through the combat reducer: a kill sours the species, forms a, test_kill_consequences_alignment_experience_and_grudge_event()

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 164 - "Community 164"
Cohesion: 0.29
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 168 - "Community 168"
Cohesion: 0.14
Nodes (5): PlaytestControls, Click, ComposeResult, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 172 - "Community 172"
Cohesion: 0.16
Nodes (7): FormField, InterventionForm, Pressed, Session, Submitted, One labelled input on an intervention form., A small validated form; dismisses with the field values, or None on cancel.

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
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Config Schema Models` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Community 129`, `Standing, Corp & Combat Rules`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `Planet & Orbit Views`, `Attitude, Disposition & Contracts`, `Station Art & Portrait Rendering`, `Encounters & Station Archetypes`, `Dialogue-Pack Save Guard`, `Community 143`, `Universe Embedding & Bearings`, `Game Lifecycle & Pathfinding`, `Subsystem Layouts & Ownership`, `Market Orders & Regions`, `Derived Aspects & Engine Room`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Core Rules Tests`, `Community 42`, `Community 43`, `Community 45`, `Community 48`, `Community 49`, `Community 55`, `Community 59`, `Community 61`, `Community 65`, `Community 68`, `Community 74`, `Community 75`, `Community 76`, `Community 77`, `Community 79`, `Community 85`, `Community 86`, `Community 88`, `Community 89`, `Community 94`, `Community 98`, `Community 99`, `Community 111`, `Community 114`, `Community 115`, `Community 117`?**
  _High betweenness centrality (0.168) - this node is a cross-community bridge._
- **Why does `GroundwarConfig` connect `Community 143` to `Community 64`, `Groundwar Battle Screen`, `Community 50`, `Config Schema Models`, `Community 62`, `Community 63`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `GameService` connect `Core-Seizure Confirm Screens` to `Core Rules & Events Engine`, `Community 128`, `Screens, DTOs & Remote Play`, `Standing, Corp & Combat Rules`, `UI Config & Route Tests`, `Sector Scene & Widgets`, `Computer Screen & Alliances Tab`, `Community 129`, `Planet & Orbit Views`, `Station Art & Portrait Rendering`, `Encounters & Station Archetypes`, `Community 139`, `Engine-Room Component Workbench`, `Dialogue-Pack Save Guard`, `Game Lifecycle & Pathfinding`, `The Entity & Command Reduce`, `TUI Screen Widgets`, `UI Mockup Screenshot Harness`, `Config Schema Models`, `Derived Aspects & Engine Room`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Server Net & Engine Ticker`, `Devtool CLI & Sysop`, `Community 164`, `Config Loading & Sidecar Merge`, `Base Screen Chrome & Saves`, `Community 42`, `Community 43`, `Community 45`, `Community 46`, `Community 52`, `Community 55`, `Community 60`, `Community 61`, `Community 67`, `Community 69`, `Community 82`, `Community 85`, `Community 86`, `Community 92`, `Community 94`, `Community 98`, `Community 99`, `Community 101`, `Community 112`, `Community 113`, `Community 127`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 122 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 122 INFERRED edges - model-reasoned connections that need verification._
- **Are the 330 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 330 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._