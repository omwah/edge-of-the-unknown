# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 328 files · ~9,144,042 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 7871 nodes · 34923 edges · 212 communities (182 shown, 30 thin omitted)
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 11786 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8dbfe841`
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
- Community 126
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
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
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
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 183
- Community 184
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
- _operational_core_bases
- .__init__
- .instruct
- _clamp_ship_field
- graphify.js
- graphify.md
- graphify.md
- __init__.py

## God Nodes (most connected - your core abstractions)
1. `UniverseState` - 595 edges
2. `GameConfig` - 432 edges
3. `Commodity` - 415 edges
4. `reduce()` - 363 edges
5. `EconomyError` - 333 edges
6. `Player` - 293 edges
7. `Ownership` - 289 edges
8. `EdgeApp` - 259 edges
9. `AlienSpecies` - 255 edges
10. `Warp` - 245 edges

## Surprising Connections (you probably didn't know these)
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_species_knowledge_is_deterministic_bounded_and_referential()` --calls--> `generate()`  [EXTRACTED]
  tests/test_dialogue_intel.py → edge/bigbang/generator.py
- `test_core_pinned_to_origin()` --calls--> `generate()`  [EXTRACTED]
  tests/test_embedding.py → edge/bigbang/generator.py
- `test_embedding_is_populated_and_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_embedding.py → edge/bigbang/generator.py
- `test_bigbang_rejects_more_warps_than_the_nav_rose_can_show()` --indirect_call--> `ValidationError`  [INFERRED]
  tests/test_config.py → edge/bigbang/validate.py

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

## Communities (212 total, 30 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.08
Nodes (470): _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup() (+462 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.02
Nodes (135): ActiveBinding, Container, Sizes/counts for the SectorView sprite scene (presentation only, no rules)., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, SectorDiscovery (+127 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.03
Nodes (107): ArmamentItem, Aspect, BountyDTO, CommodityLine, CorpMemberDTO, DeploymentOptionDTO, DossierEntry, EncounterDTO (+99 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.03
Nodes (259): GameConfig, Top-level config bundle, validated from the parsed YAML mapping., §4/§10 reference integrity: every hull's `armament` ids resolve in the         `, apply_reward(), Pay a completed contract: latinum faucet + capped attitude warmth toward the iss, player_corp(), The corporation a player belongs to, or None (§4, WP66)., apply_dev_patch() (+251 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.02
Nodes (182): MapNodeDTO, One traversed sector on a plotted route — what the player reads (§11, WP14)., A clickable sector node on the local map: its label's cell box in `rows`.      `, One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, RouteHopDTO, TechOfferDTO, EdgeApp, Tear down the remote loop/thread on exit (WP68). (+174 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.02
Nodes (168): alliance_standing(), base_owner_hostile(), core_status(), governor_hostile(), owner_hostile(), The player's standing with a bloc (0.0 if none), (§6.3)., Whether the Core governor treats the player as an enemy (§6.3, WP38).      True, The player's standing *in the Core* under the current governor (§6.3, WP52). (+160 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.02
Nodes (92): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_engine_room() (+84 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.10
Nodes (30): apply_patch(), Apply (or, in dry-run, preview) a DevPatch and report what changed., market_report(), money_supply(), notices_report(), players_report(), The tavern noticeboard (all entries, indexed for moderation)., Per-player latinum / bank / turns / alliance / standings (bypassing fog). (+22 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.02
Nodes (96): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., pretty_planet_type(), A human-readable label for a `planet_type` key (§4.2). The raw key still keys, AmountStepper, ComposeResult, Horizontal, Pressed (+88 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.06
Nodes (63): decay_grudges(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called., accept(), active(), advance_convoy(), by_id(), complete_destroy_on_kill(), complete_destroy_on_raze() (+55 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.03
Nodes (60): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), Text (+52 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.06
Nodes (52): alliance_standing_shift(), _clamp01(), disposition_band(), effective_disposition(), grudge_shift(), Name the band a disposition value falls in (hostile / neutral / friendly, §6)., The greeting-vs-violence penalty from ill standing with a species' bloc (§6.3)., Base disposition shifted by the player's attitude offset, clamped to [0, 1] (§6) (+44 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.06
Nodes (64): range, enroll(), generate_with_player(), Any, Shared test helpers.  The big bang no longer seeds players — enrolling a player, Enroll a player into an already-generated universe (mutates + returns `state`)., `generate()` then `enroll()` — the common "fresh game with player 1" setup., WP27: logging a find into the codex pays experience_per_discovery. (+56 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.04
Nodes (56): One subsystem panel: its derived aspect and its slot grid (§4.1)., Subsystem, ContextStrip, EmptyState, Any, ComposeResult, Static, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches'). (+48 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.05
Nodes (51): TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Generate a fresh universe on disk and start the background ticker.          The, Reload the saved game by replaying its command log (DESIGN §12).          Return, Validate art coverage and read scene-sprite sizes before a game starts., Run the client-owned engine ticker as a Textual worker (WP61).          The tick (+43 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.10
Nodes (44): EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, A deterministic fingerprint of the live entity state (RNG/adjacency excluded)., state_hash(), _config(), _drift_config() (+36 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.04
Nodes (67): build_graph(), generate(), Build the warp graph and return its adjacency plus the region groups., Generate a validated universe from `(seed, config)`; raise on repeated failure., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).      E, TopologySet (+59 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.08
Nodes (80): Command, Validate `command` for `player_id` and return its delta + events., reduce(), instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice() (+72 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.04
Nodes (53): clear_slot(), Remove the save and its WAL/SHM sidecars so a new game starts clean., Any, ComposeResult, DataTable, Horizontal, Pressed, RowHighlighted (+45 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.06
Nodes (78): build_layouts(), Subsystem, Instantiate intact subsystems from a layout mapping (§4.1).      Base components, Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe, The species sub-RNG must not shift the Phase-1 port/planet draws (golden-master), test_species_placement_does_not_perturb_ports_or_planets(), _base() (+70 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.11
Nodes (10): EncounterScreen, _outcome_note(), ComposeResult, Pressed, Subsystem, Esc leaves a *resolved* engagement; a live fight still has no way out., Concrete end-of-fight copy from the event's counts (PT-26/WP-PR03) — no generic, Static (+2 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.06
Nodes (68): computer_view(), engine_room_view(), _event_player(), event_visible_to(), game_view(), market_view(), messages_view(), Event (+60 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.04
Nodes (104): BaseModel, AspectFormula, BaseServicesConfig, CommodityPricing, ContractsConfig, CorpConfig, CronCadenceConfig, DefenseConfig (+96 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.05
Nodes (70): attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate(), _int(), literalist() (+62 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.09
Nodes (52): derive_aspects(), Ship, Compute the derived scalars for `ship` from its subsystems (§4.1).      A hull w, apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., Command, Apply an engine cron's result: upsert entities + persist its durable trail., Validate, persist, and apply a command; return the events it produced. (+44 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.07
Nodes (67): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line() (+59 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.03
Nodes (121): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+113 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.05
Nodes (77): may_occupy(), Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules, WP16, AllianceConfig, A Core-seizure ladder is meaningful only on a `covets_core` bloc (§6.3, WP50)., One alliance / rival bloc in the roster (DESIGN §6.3).      Joinability (WP38):, AllianceLeadershipChanged, GovernanceChanged, Core Space changed hands to a new governing alliance (§6.3, §4.2, WP49).      `c (+69 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.15
Nodes (27): DevPatchError, _parse_component(), Exception, A malformed or impossible dev patch (unknown target, missing entity, bad key)., Apply a set/add op to a current integer., Parse a "<component>:<tier>" grant key (e.g. 'accelerator:III')., _resolve(), _apply() (+19 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.03
Nodes (48): EngineRoomPreviewDTO, Presentation-only before/after aspects for one prospective install or swap (WP-U, CronTask, GameService, EncounterDTO, Event, Persisted events after `seq`, each with its seq — the reconnect catch-up buffer, Persist the ticker schedule so a reload resumes mid-interval (WP12). (+40 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (33): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+25 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.06
Nodes (33): _amain(), _build_game(), _encode_any(), _error(), GameServer, LobbyServer, Any, Command (+25 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.08
Nodes (55): DrawFn, EconomyConfig, The pricing inputs for one commodity., The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., _force_settlement(), Dev/testing cheat command (NOT part of normal play).  `DevPatch` is a single, ge, Run one order-book settlement now (WP59 sysop op) — a logged, replayable market (+47 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.10
Nodes (30): Resolve a `--route` endpoint token to an internal sector id.      Accepts an int, resolve_sector(), apply_patch_lines(), build_parser(), _build_patch(), cmd_governance(), cmd_list(), cmd_show() (+22 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (58): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+50 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.07
Nodes (28): BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Pressed, Submitted, The LLM pilot's console — a Textual app watching and steering the brain (dev-onl (+20 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.07
Nodes (46): load_config(), load_config_with_sidecar(), load_default_config(), _merge_dialogue(), Any, Path, Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Load the bundled default config (`config/default.yaml`). (+38 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.10
Nodes (28): BaseScreen, The visible service tab's id (the unit every action keys on)., The `.` menu / `?` help / palette list, scoped exactly like the footer (PT-32)., Tabs the base withholds (standing / service-integrity gated) — recorded once at, _at_base(), _footer_keys(), PT-32 — the Starbase's keyboard model: a tab owns its keys.  The third and last, Regression: `P` on a derelict base used to crash the TUI.      A base *is* the p (+20 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 42 - "Community 42"
Cohesion: 0.09
Nodes (33): bfs_distances(), Forward hop distance from `src` to every reachable sector.      Accepts any int-, _best_roundtrip_margin(), _check_degree_cap(), _check_expansive_no_chokepoint(), _check_home_clusters(), _check_planet_ownership(), _check_profitable_pair() (+25 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (30): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., BotRunner (+22 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (28): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+20 more)

### Community 45 - "Community 45"
Cohesion: 0.07
Nodes (13): ABC, BaseException, The saved ticker schedule, or None for a fresh game (WP12)., EngineState, GameMeta, Command, Event, Persistence behind a repository interface (DESIGN §12).  `Repository` is the abs (+5 more)

### Community 46 - "Community 46"
Cohesion: 0.07
Nodes (21): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), AlienContactScreen, ComposeResult, Widget, Re-fetch the view and repaint the conversation **in place** (§6.7).          `pi, Land focus on the new menu — the old reply rows were just removed under it., The reply menu — the one thing that really changes between nodes.          Share (+13 more)

### Community 47 - "Community 47"
Cohesion: 0.22
Nodes (16): _bfs_from(), _pick_by_distance(), plan_move(), Random, Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42)., Hop distance from the nearest `sources` node to every reachable sector (BFS)., Pick the candidate nearest (or farthest, if `maximize`) a target set.      Unrea, _line_state() (+8 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (57): DataObject, accrue_interest(), deposit(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Random (+49 more)

### Community 49 - "Community 49"
Cohesion: 0.05
Nodes (78): describe_payload(), effective_sensor(), entity_contactable(), is_detectable(), Discovery detection + valuation — pure core, no I/O, no RNG (DESIGN §7, WP5).  D, The ship's sensor rating after nebula interference (never negative)., Whether `discovery` is visible to a ship with this sensor rating on entry (§7)., Whether the Entity's presence resolves into openable contact at this sensor rati (+70 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (41): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+33 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.10
Nodes (27): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+19 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (38): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+30 more)

### Community 54 - "Community 54"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (42): Exception, One connected client: the socket, the authenticated account, and the seat it hol, A JSON-RPC error to return to the caller (code + message)., RpcError, Session, A stable hash of the protocol surface — client and server refuse a mismatch at h, wire_fingerprint(), _bound_session() (+34 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (40): compose_horizontal(), flip_row(), Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo, Compose a sprite grid by laying parts left-to-right to fill ``target_w``.      O (+32 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (35): Part, A recombinable sprite fragment, authored as ``cells`` rows and composed to     f, _compose(), _grammar_floor(), _mirror_part(), _mirror_row(), PortGenerator, Random (+27 more)

### Community 58 - "Community 58"
Cohesion: 0.11
Nodes (20): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+12 more)

### Community 59 - "Community 59"
Cohesion: 0.06
Nodes (52): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology, PlanarTopology (+44 more)

### Community 60 - "Community 60"
Cohesion: 0.08
Nodes (34): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl (+26 more)

### Community 61 - "Community 61"
Cohesion: 0.09
Nodes (14): LinkLost, The websocket dropped mid-call — surfaced to the TUI as a retryable status, not, A `GameClient` over a websocket to `edge-server` (WP68) — the hosted-play seam., Open the socket and complete the fingerprint handshake (refuses a build mismatch, connected" / "disconnected" / "closed" — the TUI status-bar link state., Demux the socket: pushed `event` notifications feed the stream; results resolve, One JSON-RPC request/response round-trip (raises `RemoteError`/`LinkLost`)., Authenticate this connection with the server's dedicated operator secret. (+6 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (15): HelpScreen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key (+7 more)

### Community 63 - "Community 63"
Cohesion: 0.09
Nodes (22): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, _add_structure() (+14 more)

### Community 64 - "Community 64"
Cohesion: 0.11
Nodes (45): GarrisonUnit, Battle-state model for the ground-war POC.  Plain mutable dataclasses (this is a, Every action spent — nothing left to do this turn., Structure, Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms() (+37 more)

### Community 65 - "Community 65"
Cohesion: 0.08
Nodes (40): DialoguePack, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace, One conversational beat: its concept, extra placeholders, and Phase-2 reachabili, _branch_closure() (+32 more)

### Community 66 - "Community 66"
Cohesion: 0.12
Nodes (10): FormField, Any, DataTable, HeaderSelected, OptionSelected, RowSelected, Two-pane sysop dashboard: nav left, view right, audit trail below., Enter/click on a players or standings row opens its full dossier. (+2 more)

### Community 67 - "Community 67"
Cohesion: 0.25
Nodes (9): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.04
Nodes (46): AmountPrompt, Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, Carried territory stock + devices for the Deploy screen (§10/§14, WP72)., AmountPrompt, FieldPrompt, Pressed, Submitted (+38 more)

### Community 70 - "Community 70"
Cohesion: 0.11
Nodes (44): fighter_foe(), NpcEntry, owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, The garrison as a single all-round combat foe, scaled by fighter count (§10, WP4, The outcome of an NPC entering a defended sector (§10, WP-PR02).      `destroyed, Resolve `force`'s defenses against `species` drifting in (§10, WP-PR02) — pure,, resolve_npc_entry() (+36 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (40): _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text, Offline CLI tool for testing and developing procedural ASCII art generation. (+32 more)

### Community 72 - "Community 72"
Cohesion: 0.08
Nodes (10): main(), PlaytestService, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable. (+2 more)

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (49): admission_met(), admission_tasks_done(), _alliance_key(), apply_join_standing(), apply_resign_standing(), attitude_offset(), core_bases_razed(), is_criminal() (+41 more)

### Community 74 - "Community 74"
Cohesion: 0.09
Nodes (36): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar (+28 more)

### Community 75 - "Community 75"
Cohesion: 0.14
Nodes (24): CitadelError, Exception, A citadel build/treasury operation was rejected (raised by the reducers)., _enemy_world(), WP54 — citadels: levels, treasury, timed builds, the planetary gun (DESIGN §4.2,, An alliance-owned world in the player's sector, ready to invade (no base)., A single owned colony in the player's sector (no port), ready to fortify., test_build_citadel_pays_up_front_and_opens_a_build() (+16 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (18): Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Deployed forces as glyph-scale presence marks — fighters flying patrol         t (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.07
Nodes (41): CronFn, The pure reducer for a persisted cron name (raises on an unknown name)., resolve_cron(), Generate a fresh universe, persist its meta, enroll player 1, and return., Path, SqliteRepository, Path, test_first_strike_replays_to_identical_hash() (+33 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (14): Battle, Event, Side, One cell of rocky debris (belt scenarios). Blocks fire lines and wings;     dest, A missile salvo in flight — a board object chasing its target ship., One log/FX entry drained by the UI after each rules call., A ship (any footprint cell), wing, rock, or wreckage sits here — one         pie, Every board cell of the piece's footprint (anchored on the centre).         Ship (+6 more)

### Community 79 - "Community 79"
Cohesion: 0.09
Nodes (41): AliensConfig, Disposition thresholds + escape floor for the alien system (DESIGN §6, §10)., entity_species(), The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None., LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., build_species_knowledge(), _candidates() (+33 more)

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
Cohesion: 0.19
Nodes (18): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), main(), _parse_args() (+10 more)

### Community 84 - "Community 84"
Cohesion: 0.27
Nodes (19): validate(), _derelict_base(), _good_world(), _intact_base(), _pair(), Subsystem, WP9 — big-bang validation rejects broken universes (DESIGN §5 step 8)., _stardock() (+11 more)

### Community 85 - "Community 85"
Cohesion: 0.11
Nodes (7): _assert_impl(), Command, EncounterDTO, Event, Protocol, The typed surface of the in-process game service (H16)., ServiceProtocol

### Community 86 - "Community 86"
Cohesion: 0.08
Nodes (35): _make_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, Populate `state.discoveries` deterministically from the seed (§7)., _roll_kind(), _roll_tier() (+27 more)

### Community 87 - "Community 87"
Cohesion: 0.10
Nodes (24): Brain, One pilot: owns the model client, the action catalog, and the paced loop., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end., Answer queued general questions without executing or budgeting an action., Separate queued queries from persistent objective changes. (+16 more)

### Community 88 - "Community 88"
Cohesion: 0.13
Nodes (24): normalize_belt(), Scrub colony/citadel/base affordances off a non-landable spatial world (§4.2)., _dirty_belt(), WP-PR06 — asteroid belts are spatial features, not colony worlds (playtest PT-30, A belt still hosts spatial finds (its sector's discoveries), just not landable s, `normalize_belt` converges a pre-PT-52 (reserve-less) belt on a full field., _state_with_belt(), test_a_haul_is_clamped_to_the_ore_actually_left() (+16 more)

### Community 89 - "Community 89"
Cohesion: 0.05
Nodes (41): LocalMapDTO, The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map(), Bake the local map to fit `width`, overlaying the active route (§6.7/§11)., LocalMapView, Resize, The local sector ego-graph (Computer/Map screen → §10, §11).      A node-and-edg (+33 more)

### Community 90 - "Community 90"
Cohesion: 0.22
Nodes (14): Console, _build_sheet(), _draw_sprite(), export_multipage_pdf(), export_sprite_sheet(), Path, Text, Vector export for the procedural sprites (dev-only sprite sheets).  Lays every r (+6 more)

### Community 91 - "Community 91"
Cohesion: 0.05
Nodes (47): Merge a generated dialogue sidecar onto the default roster and run §13 integrity, validate_sidecar(), AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json() (+39 more)

### Community 92 - "Community 92"
Cohesion: 0.09
Nodes (32): _hostile(), Path, WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., The golden rail: a journey with encounter rolls (and an engagement) reloads (+24 more)

### Community 93 - "Community 93"
Cohesion: 0.14
Nodes (26): list_portraits(), nebular_bloom(), portraits_dir(), Path, Text, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Run image `path` through chafa and return its decoded ANSI string (the cached un, A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35). (+18 more)

### Community 94 - "Community 94"
Cohesion: 0.09
Nodes (33): advance_build(), building(), citadel_defense_mult(), citadel_foe(), conquer(), has_gun(), InvasionOutcome, level_config() (+25 more)

### Community 95 - "Community 95"
Cohesion: 0.14
Nodes (22): BotSetup, BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Enrol a bot on `player_id` and let `setup` register its triggers + turn driver., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), _cfg() (+14 more)

### Community 96 - "Community 96"
Cohesion: 0.11
Nodes (27): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random, Ship (+19 more)

### Community 97 - "Community 97"
Cohesion: 0.43
Nodes (6): WP13 — multi-round haggle sessions (DESIGN §8).  The history penalty that wears, A one-sector universe with a Class-1 port (it BUYS fuel ore) and a docked player, test_daily_cron_resets_attempts(), test_insulting_offer_increments_the_attempt_counter(), test_max_rejections_closes_negotiation_at_fair(), _world()

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (39): alien_drift(), _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16)., _config(), _drift_world(), Path, WP7 — the engine cron reducers and tick scheduler (DESIGN §9).  WP16 adds the `a (+31 more)

### Community 99 - "Community 99"
Cohesion: 0.08
Nodes (10): _assert_impl(), _assert_remote_impl(), GameClient, Command, Event, Protocol, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Apply a command through the in-process service (events fan out via `on_events`). (+2 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.12
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.12
Nodes (26): Adjacency, _annotate(), can_warp(), plan_route(), plan_route_legs(), Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For, The sectors reachable in one hop from `sector_id`. (+18 more)

### Community 103 - "Community 103"
Cohesion: 0.12
Nodes (36): combat_contexts(), DialogueIntegrityError, Exception, Convenience: select a line for a live encounter and return (text, new recency ri, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3, Assert the §13 dialogue-integrity invariants for a roster (raises on failure)., A roster's dialogue packs fail the §13 integrity checks. (+28 more)

### Community 104 - "Community 104"
Cohesion: 0.17
Nodes (26): build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., _one_way_span_world(), _phantom_bridges(), Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic., A world reproducing the PT-56 phantom: a **one-way** warp Z→A joins two sectors, Pairs of *non-adjacent* sectors joined on one row by an unbroken, arm-connected, A graph can fit horizontally while exploding vertically; fitting bounds both axe (+18 more)

### Community 105 - "Community 105"
Cohesion: 0.09
Nodes (39): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, WarpDTO, esc(), Shared character-grid canvas and band palette for baked map/nav views (§11).  Bo, Escape Rich-markup-significant characters in literal cell text., build_nav_strip() (+31 more)

### Community 106 - "Community 106"
Cohesion: 0.12
Nodes (36): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A knocked-out part contributes nothing until it is patched (§4.1). (+28 more)

### Community 107 - "Community 107"
Cohesion: 0.19
Nodes (20): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), FindKind, generate_find_art() (+12 more)

### Community 108 - "Community 108"
Cohesion: 0.04
Nodes (55): Binding, Any, Resize, Screen, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)., Persist local-only presentation settings and apply the theme immediately. (+47 more)

### Community 109 - "Community 109"
Cohesion: 0.09
Nodes (32): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), _discoveries(), format_route(), list_items(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers). (+24 more)

### Community 110 - "Community 110"
Cohesion: 0.13
Nodes (21): get_biome_feature(), _luminance(), any, OpenSimplex, Random, Text, Procedural terrain generation using OpenSimplex noise.  The *gameplay* band layo, Rec.601 perceived luminance of an (r, g, b) triple in 0..1. (+13 more)

### Community 111 - "Community 111"
Cohesion: 0.15
Nodes (15): LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met, Run the embedded engine ticker until stopped (the app's engine worker, §3)., The embedded ticker (tests/shots that step it directly)., The wrapped in-process service (single-player back-compat; never used for remote, _config(), Path, WP61 — the async `GameClient` facade over the in-process service (DESIGN §3/§14) (+7 more)

### Community 112 - "Community 112"
Cohesion: 0.13
Nodes (8): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., Static, Vertical, Widget, The base's standing, on one line, in a bordered panel above the installations.

### Community 113 - "Community 113"
Cohesion: 0.17
Nodes (12): _Coord, MeshTopology, Mesh topology builder (DESIGN §5)., Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who (+4 more)

### Community 114 - "Community 114"
Cohesion: 0.09
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
Cohesion: 0.24
Nodes (14): hourly_port_economy(), market_settlement(), The hourly port-economy tick: order-book market, or the legacy regen (§8, WP47)., The daily order-book settlement: match the book, move goods+latinum, drip purses, _market_config(), _market_world(), A 1-2-3 chain with a shortage port (sector 2) and a surplus port (sector 3)., With the market disabled, `hourly_port_economy` is the exact legacy regen body. (+6 more)

### Community 119 - "Community 119"
Cohesion: 0.15
Nodes (8): Any, Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises)., A `GameService`-shaped synchronous facade over the connected client., A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., RemoteBridge, RemoteService

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.13
Nodes (25): is_colonizable(), Whether a world of this type can be claimed and settled (§4.2).      Colonizable, _at_stardock(), _do(), _eligible_planet(), WP10 — Genesis torpedoes: buy at Stardock, terraform an eligible world (§4.2)., test_buy_genesis_at_stardock_costs_latinum(), test_buy_genesis_requires_stardock() (+17 more)

### Community 123 - "Community 123"
Cohesion: 0.17
Nodes (17): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.22
Nodes (16): concourse_asset(), Path, Text, Static Stardock service raster selection and ANSI rendering.  The source artwork, Return the tab, theme, and layout-specific crop., Render a responsive service panel: 72×12 wide, 56×8 standard., Compatibility wrapper for the original PT-06 asset tests., Compatibility wrapper for the original PT-06 renderer. (+8 more)

### Community 125 - "Community 125"
Cohesion: 0.16
Nodes (12): fractal_noise(), OpenSimplex, Shared procedural-noise helpers for the art generators., Sum several octaves of noise so clusters break up at multiple scales.      Layer, Random, Text, Procedural starfield generation., Per-subtype knobs turning the noise field into stars.      threshold  - noise cu (+4 more)

### Community 126 - "Community 126"
Cohesion: 0.11
Nodes (22): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+14 more)

### Community 127 - "Community 127"
Cohesion: 0.12
Nodes (23): port_unit_price(), Quoted price for a line using the economy config's per-commodity tunables., _grudge_targets(), is_trader(), movement_policy(), NpcTrade, plan_trade(), _player_sectors() (+15 more)

### Community 128 - "Community 128"
Cohesion: 0.10
Nodes (5): _decode_any(), Any, EncounterDTO, Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, T

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.15
Nodes (5): ContactDTO, A peaceful alien contact screen (§6, §6.7, §11)., The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any.

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "Community 132"
Cohesion: 0.23
Nodes (14): WP-PR07 — settling more colonists onto an already-owned colony (playtest PT-11)., Every `TransferCargo` moves goods between ship holds and colony stores without, An owned colony with stores + a ship with cargo and free holds, same sector., _state(), test_batch_load_is_one_delta_and_shares_free_holds(), test_invalid_batch_is_atomic(), test_settle_clamps_to_aboard_and_habitability(), test_settle_rejected_on_uncolonizable_world() (+6 more)

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "Community 135"
Cohesion: 0.15
Nodes (7): PlanetSpriteSize, Footprint bounds (character cells) for one SectorView scene sprite.      A sprit, Planet sprite footprint: height is authored, width is *derived* as 2*height., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SpriteSize, test_scene_art_rejects_min_above_max()

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 137 - "Community 137"
Cohesion: 0.22
Nodes (13): _noncore(), WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., The projection greys FIGHT with the very string the reducer raises (lockstep)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage(), test_attack_blocked_in_the_core_sanctuary(), test_attack_on_a_noncombatant_is_pointless(), test_attack_on_an_influence_gate_species_is_stayed() (+5 more)

### Community 138 - "Community 138"
Cohesion: 0.17
Nodes (8): Any, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.17
Nodes (17): Run one trade for every NPC merchant working a port this firing (§8, WP43)., trader_step(), Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., A 1-2-3 Frontier chain with a trading port at sector 2 (optionally a player ther, A `selvani` merchant (movement_policy trade_seek in the default roster ⇒ a trade, A run of ticked trades (the WP12 rail) is deterministic — the same firings from, _selvani() (+9 more)

### Community 142 - "Community 142"
Cohesion: 0.26
Nodes (11): effective_trade_posture(), The species' trade posture as this player experiences it (§6.1/§6.2 — WP74)., WP74 — the signature-mechanic corpus routes (SEAMS_PLAN A2, decision D4).  The s, Each carrier species' pack routes a choice into its own sig.* namespace (A2 clos, test_alliance_gated_trade_opens_for_sworn_members(), test_escalating_demand_ladder_climbs_and_betrayal_is_permanent(), test_every_dark_hook_has_a_corpus_route(), test_flee_drop_route_pays_once() (+3 more)

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (19): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, main(), Battle, Pressed, Screen (+11 more)

### Community 144 - "Community 144"
Cohesion: 0.21
Nodes (6): Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait., Render a species' portrait image (by `roster_id`) into its allotted cell box., SpeciesPortrait

### Community 145 - "Community 145"
Cohesion: 0.19
Nodes (16): _open_computer(), WP-PR09 — Computer prioritization and navigation continuity (PT-08/09/23/27/31)., PT-31 (§8.1): plotting from Planets, Ports, and the Map all end on Route, no fla, PT-09 (§8.1): a base-hosted port row carries its market open/dark status., PT-23: V acts on the selected row without opening the numeric-sector prompt., _svc(), test_avoid_button_opens_prompt(), test_avoid_key_targets_highlighted_port_planet_and_route_rows() (+8 more)

### Community 146 - "Community 146"
Cohesion: 0.29
Nodes (11): WP58 — the Stardock tavern: rumors, bounty board, noticeboard (DESIGN §14).  Rum, A Stardock in sector 1 (player docked there) + a rare find out in sector 3., test_buy_rumor_logs_a_lead_and_charges(), test_empty_notice_rejected(), test_notice_ring_evicts_oldest(), test_post_notice_appends_sanitised(), test_rumor_exhausts_when_nothing_new(), test_rumor_rejected_off_dock() (+3 more)

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

### Community 156 - "Community 156"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 157 - "Community 157"
Cohesion: 0.22
Nodes (7): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, Grid, TabPane

### Community 158 - "Community 158"
Cohesion: 0.20
Nodes (4): ComposeResult, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th, Install the selected carried component into the selected open base slot., Cannibalize one component from the base into the ship's hold (§4.2).

### Community 159 - "Community 159"
Cohesion: 0.19
Nodes (10): A fresh universe seeded from the game's seed (RNG owned here, §3)., Dense spiral rings use their radial/tangential embedding, not one tall hop colum, test_spiral_layout_spreads_same_radius_sectors_across_columns(), _game(), WP1 checks: enums, port-class triples, and the core domain models., test_models_are_frozen(), test_port_line_lookup(), test_rebuild_adjacency_projects_warps() (+2 more)

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 162 - "Community 162"
Cohesion: 0.29
Nodes (3): CorpDTO, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The player's corporation for the `T` screen — roster, bank, holdings, wars (§4,

### Community 163 - "Community 163"
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 164 - "Community 164"
Cohesion: 0.29
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 165 - "Community 165"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 168 - "Community 168"
Cohesion: 0.19
Nodes (4): PlaytestControls, Click, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 172 - "Community 172"
Cohesion: 0.17
Nodes (6): InterventionForm, ComposeResult, Pressed, Session, Submitted, A small validated form; dismisses with the field values, or None on cancel.

### Community 173 - "Community 173"
Cohesion: 0.25
Nodes (6): LiveSysopService, Any, Event, Synchronous host-admin bridge for `edge-sysop` live hosted interventions.  The d, Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC., Apply an intervention to the authoritative live game as the target player.

### Community 174 - "Community 174"
Cohesion: 0.40
Nodes (4): Debris, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, Scatter drifting-wreckage clumps across the midfield (graveyard     scenarios) —, seed_debris()

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 176 - "Community 176"
Cohesion: 0.22
Nodes (9): Color, Style, Text, Flatten a Rich `Text` sprite into per-cell `(char, style)` rows for stamping., Resolve a (possibly ANSI/named) colour to an explicit RGB triplet colour., Re-resolve every style in `text` to explicit truecolor.      The art palettes us, text_to_cells(), _to_truecolor() (+1 more)

### Community 177 - "Community 177"
Cohesion: 0.32
Nodes (7): _archetype(), assign_station_archetypes(), _builder(), Deterministic builder-archetype assignment for ports and orbital bases., Resolve the species whose configured archetype designed the structure., Stamp every structure's builder archetype after alien regions exist (§5)., test_assignment_is_seeded_roster_driven_and_fixed_after_capture()

### Community 178 - "Community 178"
Cohesion: 0.14
Nodes (24): CronResolver, One persisted engine-cron firing (WP12): which cron, at which tick, and the, RecordedCommand, RecordedMaintenance, _canonical(), export_save(), import_save(), Any (+16 more)

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

### Community 182 - "Community 182"
Cohesion: 0.32
Nodes (4): `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, `BotSwarm` — many bots against one authoritative game (DESIGN §14 — WP69).  The, `ServiceProtocol` — the one typed service seam every consumer programs against (

### Community 183 - "Community 183"
Cohesion: 0.29
Nodes (3): MessagesDTO, The messages & log view, projected from the durable event_log (§12)., The durable event log, newest first (§11, §12).

### Community 184 - "Community 184"
Cohesion: 0.50
Nodes (4): _check_discovery_gradient(), Discovery gradient (§7 / §5 step 8): mean rarity **and** value strictly rising, rarity_value(), The latinum-equivalent value of a rarity tier (the gradient the validator checks

### Community 204 - "_operational_core_bases"
Cohesion: 0.50
Nodes (4): _operational_core_bases(), Operational Core-sector starbases owned by `alliance_id` (the incumbent's grip)., governance_report(), Current Core governor, its grip, and each covets_core bloc's seizure readiness.

### Community 207 - "_clamp_ship_field"
Cohesion: 0.67
Nodes (3): _clamp_ship_field(), Ship, Field-specific validation for a ship integer set/add (raises on hard limits).

## Knowledge Gaps
- **54 isolated node(s):** `FindKind`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script`, `graphify` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Sector Scene & Widgets`, `Community 129`, `Standing, Corp & Combat Rules`, `Community 132`, `Aliens & Alliance Admission`, `UI Config & Route Tests`, `Community 135`, `Disposition Bands & Ship Classes`, `Attitude, Disposition & Contracts`, `Planet & Orbit Views`, `Encounters & Station Archetypes`, `Community 141`, `Dialogue-Pack Save Guard`, `Community 143`, `Universe Embedding & Bearings`, `Game Lifecycle & Pathfinding`, `Community 146`, `Subsystem Layouts & Ownership`, `Market Orders & Regions`, `Config Schema Models`, `Derived Aspects & Engine Room`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `Community 159`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Community 163`, `Core Rules Tests`, `Community 42`, `Community 48`, `Community 49`, `Community 178`, `Community 52`, `Community 182`, `Community 55`, `Community 59`, `Community 61`, `Community 68`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 79`, `Community 83`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 89`, `Community 94`, `Community 95`, `Community 96`, `Community 97`, `Community 98`, `Community 99`, `Community 103`, `Community 111`, `Community 113`, `Community 114`, `Community 115`, `Community 117`, `Community 127`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Standing, Corp & Combat Rules` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Community 132`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Attitude, Disposition & Contracts`, `Community 137`, `Encounters & Station Archetypes`, `Domain Models & Colonizability`, `Community 141`, `Community 142`, `Game Lifecycle & Pathfinding`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `Station Art & Portrait Rendering`, `Subsystem Layouts & Ownership`, `Community 146`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Derived Aspects & Engine Room`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `Community 159`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `Community 168`, `Community 42`, `Community 47`, `Community 48`, `Community 177`, `Community 49`, `Community 178`, `Community 54`, `Community 182`, `Community 184`, `Community 59`, `Community 61`, `Community 70`, `Community 72`, `Community 73`, `Community 75`, `_operational_core_bases`, `Community 77`, `Community 79`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 94`, `Community 95`, `Community 97`, `Community 98`, `Community 99`, `Community 103`, `Community 104`, `Community 106`, `Community 109`, `Community 111`, `Community 113`, `Community 115`, `Community 118`, `Community 127`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `GroundwarConfig` connect `Community 143` to `Core Rules & Events Engine`, `Community 64`, `Groundwar Battle Screen`, `Community 50`, `Config Schema Models`, `Community 62`, `Community 63`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 125 inferred relationships involving `UniverseState` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`UniverseState` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 120 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 120 INFERRED edges - model-reasoned connections that need verification._
- **Are the 326 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 326 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._