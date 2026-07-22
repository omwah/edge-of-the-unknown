# Graph Report - edge-of-the-unknown  (2026-07-21)

## Corpus Check
- 350 files · ~9,209,501 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8886 nodes · 41069 edges · 206 communities (181 shown, 25 thin omitted)
- Extraction: 64% EXTRACTED · 36% INFERRED · 0% AMBIGUOUS · INFERRED: 14596 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fdb1eb90`
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
- RecordingEncounterService
- market_settlement
- test_intel_contact.py
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- test_corp.py
- market_view
- .compose
- Ticker
- StaticGenerator
- Game-state interaction with alien dialogue
- Community 160
- .state
- market_view
- TavernDTO
- RemoteSession
- EngineRoomDTO
- Community 166
- GameState
- event_visible_to
- Community 169
- Community 170
- station_archetypes.py
- _SpriteCard
- messages_view
- Community 174
- Community 175
- landing_sites
- LiveSysopService
- _entity_world
- Community 179
- Community 180
- Community 181
- .boarded_starbase_id
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
1. `UniverseState` - 583 edges
2. `GameConfig` - 574 edges
3. `Commodity` - 461 edges
4. `reduce()` - 429 edges
5. `EconomyError` - 382 edges
6. `EdgeApp` - 267 edges
7. `Warp` - 252 edges
8. `apply_result()` - 252 edges
9. `ComponentTier` - 250 edges
10. `Event` - 246 edges

## Surprising Connections (you probably didn't know these)
- `test_every_live_band_has_a_contact()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_placement_is_seeded_and_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_roster_alliances_become_entities()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_different_seeds_differ()` --calls--> `generate()`  [EXTRACTED]
  tests/test_bigbang.py → edge/bigbang/generator.py

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

## Communities (206 total, 25 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.09
Nodes (505): _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup() (+497 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.05
Nodes (67): one_way_exits(), Targets reachable from `sector_id` with no return edge (sorted, deterministic)., range, generate_with_player(), Any, `generate()` then `enroll()` — the common "fresh game with player 1" setup., _quill_state(), A fresh game plus one hand-placed quill kind in the player's sector. (+59 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.02
Nodes (188): ActiveBinding, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, AllianceRowDTO, ArmamentItem, Aspect, BarracksItem, BountyDTO, CommodityLine (+180 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.11
Nodes (38): InstalledComponent, One component slotted into a subsystem (DESIGN §4.1).      `knocked_out` is set, _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co (+30 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.04
Nodes (49): AmountPrompt, Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, AmountPrompt, FieldPrompt, notify_success(), Pressed, Submitted (+41 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.02
Nodes (201): admission_met(), admission_tasks_done(), core_status(), The admission tasks the player has completed for a bloc (the §6.3 ledger)., Whether the player has completed the bloc's `admission_price` tasks (§6.3)., The player's standing *in the Core* under the current governor (§6.3, WP52)., MarketOrderDTO, One open order on the Computer's Market tab (§8, WP48). (+193 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.03
Nodes (135): describe_payload(), A short human-readable phrase for what collecting a payload yields (§7).      On, DiscoveryPayload, Game, Port, PortCommodity, A ship hull (DESIGN §4).      A player hull carries `subsystems` (the engine-roo, Holds occupied — trade cargo plus loose (uninstalled) components.          Loose (+127 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.10
Nodes (52): EncounterFoe, One hostile ship of an encounter pack (DESIGN §10, WP24).      Stats are resolve, apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., Apply an engine cron's result: upsert entities + persist its durable trail., WP27 arithmetic through the combat reducer: a kill sours the species, forms a, test_kill_consequences_alignment_experience_and_grudge_event(), _engagement() (+44 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.05
Nodes (50): The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_engine_room(), sample_planet(), EncounterScreen, _outcome_note() (+42 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.04
Nodes (44): EngineRoomDTO, One subsystem panel: its derived aspect and its slot grid (§4.1)., The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)., Subsystem, _BayPanel, ComponentWorkbench, ComponentWorkbenchProfile, ComposeResult (+36 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.10
Nodes (34): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar (+26 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.03
Nodes (66): Container, GameScreen, ComposeResult, Event, Static, Text, Location lines the compact tier keeps when the art scene is dropped., The live layout tier, computed from the app size directly (resize-event (+58 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.04
Nodes (58): TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Tick off a Captain's objective (WP-UI11) — local progress only.          Called, Generate a fresh universe on disk and start the background ticker.          The, Reload the saved game by replaying its command log (DESIGN §12).          Return, Validate art coverage and read scene-sprite sizes before a game starts. (+50 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.10
Nodes (36): apply_militia_recovery(), derive_difficulty(), _footprint_passable_frac(), generate_assault_map(), _landing(), Derive battlefield size + surrender threshold from live world state (D11)., Land near the map's left-middle, but only inside the cities' component     (port, Lay out a defended battlefield: terrain + `cities` walled cities, the last one (+28 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.06
Nodes (41): build_graph(), Build the warp graph and return its adjacency plus the region groups., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, _big_expansive_config(), _cross_region_edges(), WP4 — big-bang generation across many seeds (DESIGN §5, §13).  Generates a small, Across seeds, generation yields both intact and derelict bases (WP4). (+33 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.07
Nodes (77): instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting(), _cfg_with_oath(), _cfg_with_repeat_greeting() (+69 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.02
Nodes (180): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology, generate() (+172 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.07
Nodes (58): GovernanceChanged, Core Space changed hands to a new governing alliance (§6.3, §4.2, WP49).      `c, apply_intrigue(), flip_core_governor(), GovernanceDelta, IntrigueDelta, _nearest_legal(), npc_seizure_ready() (+50 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.12
Nodes (46): Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), A remote rules rejection compatible with every local rule-error catch.      JSON, RemoteError, RemoteRulesError, One connected client: the socket, the authenticated account, and the seat it hol, Session, A stable hash of the protocol surface — client and server refuse a mismatch at h (+38 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.05
Nodes (49): Binding, ComposeResult, Static, Shown while the terminal is below the 80×24 floor (WP-UI05).      It never traps, SizeNoticeScreen, LayoutTier, Any, Enum (+41 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.03
Nodes (75): BaseModel, BaseServicesConfig, CorpConfig, CronCadenceConfig, DefenseConfig, DeviceConfig, EncountersConfig, GenesisConfig (+67 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.06
Nodes (67): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+59 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.07
Nodes (40): compose_horizontal(), flip_row(), Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo, Compose a sprite grid by laying parts left-to-right to fill ``target_w``.      O (+32 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.03
Nodes (81): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed, Shared exact-amount field with −/+ stepping for logistics and recruitment. (+73 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.15
Nodes (42): ground_access(), OrbitalOnly, Classify how the player may interact with `planet` from orbit (GW plan §contract, This world is only ever interacted with from orbit (no ground operation).      A, GroundAccess, _owned_reinforceable_state(), _pair(), _planet() (+34 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.06
Nodes (82): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), _build_game(), Load the game at `db` if it exists, else generate a fresh one there (WP12 resume, Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, Path, SqliteRepository (+74 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.07
Nodes (18): GroundExpeditionScreen, _landing_frames(), Any, Click, ComposeResult, Key, Static, Text (+10 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.11
Nodes (22): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+14 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.04
Nodes (49): App, EmptyState, Any, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches')., A consistent 'nothing here' block: what is empty and what fills it., _cell_markup(), ColumnSpec, DetailOverlay (+41 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.12
Nodes (8): OutEdges, Wire one group: a random spanning tree, then edges toward avg degree ~2.5., `trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra, `expansive` bridging (§5 step 2): a band-lattice web with no chokepoints., `planar` bridging: connects clusters using a planar spiderweb meta-graph., Choose a non-Core, genuinely one-way destination far along the spiral., Wire one mesh cluster: a spanning tree over its grid edges, then extra grid edge, Build the topology and return the region groups (the Core is group 0).

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.09
Nodes (49): DrawFn, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., clear_filled(), desired_stock_frac(), generate_orders(), hinterland_drift() (+41 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.06
Nodes (51): Resolve a `--route` endpoint token to an internal sector id.      Accepts an int, resolve_sector(), apply_patch(), apply_patch_lines(), build_parser(), _build_patch(), cmd_list(), cmd_show() (+43 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.08
Nodes (61): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+53 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (29): Brain, BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Path, Pressed (+21 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.05
Nodes (60): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., load_config() (+52 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.04
Nodes (50): A correction clears stale validation copy and restores stable form layout., The docked one-line screen header: bold title, optional muted context., TitleBar, Changed, Posted whenever a count changes (add or remove)., BaseScreen, ComposeResult, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th (+42 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.08
Nodes (17): BattleScreen, MapView, Battle, Click, ComposeResult, Key, Text, Trooper (+9 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.16
Nodes (21): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), generate_find_art(), _pit() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.02
Nodes (329): apply_resign_standing(), Leave the current bloc and let rival hostility lapse to neutral (§6.3, WP38)., Apply the consequences of destroying `kills` of a species' ships (§6.5, WP27)., sour_attitude(), GameConfig, Top-level config bundle, validated from the parsed YAML mapping., §4/§10 reference integrity: every hull's `armament` ids resolve in the         `, player_owns() (+321 more)

### Community 43 - "Community 43"
Cohesion: 0.06
Nodes (37): BotSetup, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., _computer(), _docked_port(), _encounter(), _engine_room(), observe() (+29 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (29): CountColumn, CountItem, CountSelector, Dropped, options_from_suits(), PlatoonComposer, _PmButton, Any (+21 more)

### Community 45 - "Community 45"
Cohesion: 0.05
Nodes (34): ABC, BaseException, CronFn, The pure reducer for a persisted cron name (raises on an unknown name)., resolve_cron(), DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12). (+26 more)

### Community 46 - "Community 46"
Cohesion: 0.03
Nodes (99): EdgeApp, Any, Resize, Screen, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)., Persist local-only presentation settings and apply the theme immediately. (+91 more)

### Community 47 - "Community 47"
Cohesion: 0.03
Nodes (55): ContactChoiceDTO, One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, One authored player reply on a branching dialogue node (§6.7 optional branching), TechOfferDTO, Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait. (+47 more)

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (47): DataObject, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Random, Ship (+39 more)

### Community 49 - "Community 49"
Cohesion: 0.02
Nodes (214): _fallback_prefix(), Random, Deterministic naming generator based on configurable name pools., black_hole" → "Black Hole" — the numbered fallback when a kind's pool runs dry., _finalize_planets(), _host_markets(), _make_port(), _mid_stock() (+206 more)

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (40): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+32 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.04
Nodes (61): ActionDescriptor, clear_slot(), Remove the save and its WAL/SHM sidecars so a new game starts clean., Any, ComposeResult, DataTable, Horizontal, Pressed (+53 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (38): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+30 more)

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (10): main(), PlaytestService, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable. (+2 more)

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (27): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothi (+19 more)

### Community 56 - "Community 56"
Cohesion: 0.24
Nodes (16): _disc(), _planet_with_hidden_and_obvious(), GW-WP05 — survey generation from real universe discoveries (GW plan §GW-M2).  Tw, _survey(), test_already_collected_site_marked_found(), test_already_detected_site_is_visible_regardless_of_sensor(), test_eligibility_is_sensor_monotone_and_non_leaking(), test_every_surface_find_is_artifact_plus_lore() (+8 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (35): Part, A recombinable sprite fragment, authored as ``cells`` rows and composed to     f, _compose(), _grammar_floor(), _mirror_part(), _mirror_row(), PortGenerator, Random (+27 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (41): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+33 more)

### Community 59 - "Community 59"
Cohesion: 0.06
Nodes (56): GroundCellDTO, A friendly settlement visible on the projected survey map.      ``plaza_x``/``pl, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, SurveySettlementDTO, ground_operation_view(), Project the player's active survey without exposing its generation identity (GW-, _dim(), _feature_colors() (+48 more)

### Community 60 - "Community 60"
Cohesion: 0.20
Nodes (5): The Stardock services catalog (hardware + shipyard), fog-of-war scoped (§3)., StardockDTO, _base(), _dock(), _hardware()

### Community 61 - "Community 61"
Cohesion: 0.06
Nodes (17): LinkLost, Any, EncounterDTO, The websocket dropped mid-call — surfaced to the TUI as a retryable status, not, A `GameClient` over a websocket to `edge-server` (WP68) — the hosted-play seam., Open the socket and complete the fingerprint handshake (refuses a build mismatch, connected" / "disconnected" / "closed" — the TUI status-bar link state., Demux the socket: pushed `event` notifications feed the stream; results resolve (+9 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (16): HelpScreen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key (+8 more)

### Community 63 - "Community 63"
Cohesion: 0.04
Nodes (48): GroundwarConfig, GwWeapon, A suit/garrison weapon or missile (§ ground combat)., Ground-operations balance (survey + assault), one YAML source of truth.      Fie, BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay* (+40 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (43): _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus(), cover_at(), defense_phase() (+35 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (43): DialoguePack, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace, One conversational beat: its concept, extra placeholders, and Phase-2 reachabili, _branch_closure() (+35 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (16): FormField, InterventionForm, Any, ComposeResult, DataTable, HeaderSelected, OptionSelected, Pressed (+8 more)

### Community 67 - "Community 67"
Cohesion: 0.15
Nodes (5): ContactDTO, A peaceful alien contact screen (§6, §6.7, §11)., The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any.

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (30): _band(), _discoveries(), format_route(), _inhabitants(), _num(), _owner(), _planets(), _ports() (+22 more)

### Community 70 - "Community 70"
Cohesion: 0.12
Nodes (40): fighter_foe(), owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, The garrison as a single all-round combat foe, scaled by fighter count (§10, WP4, _force(), _generated(), _make_hostile(), _mini_state() (+32 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (36): Color, available_archetypes(), available_subtypes(), Procedural ASCII art generation logic., Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype() (+28 more)

### Community 72 - "Community 72"
Cohesion: 0.08
Nodes (26): AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json(), get_backend(), OllamaBackend (+18 more)

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (94): GwEmplacement, GwSuit, A purchasable powered-armour suit class (GW plan D3)., A static defensive structure (wall/gate/turret/AA/sensor/citadel gun)., _aa_reaction_acc(), _add_structure(), _apply_resolve(), assault_broadcast() (+86 more)

### Community 74 - "Community 74"
Cohesion: 0.05
Nodes (69): attitude_locked(), decay_grudges(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called., Whether a permanent grudge locks the attitude offset for good (§6.5).      A `ne, ContractsConfig, Favors + escort contracts issued through the dialogue system (DESIGN §6.7, §14 —, accept(), active() (+61 more)

### Community 75 - "Community 75"
Cohesion: 0.08
Nodes (58): GroundForceDTO, LoadoutOptionDTO, One platoon-composer row — an affordance the player can actually deploy (GW-WP08, The ground force aboard, as the platoon composer sees it (GW-WP08, D3)., apply_casualties(), apply_reinforcement(), berths_free(), berths_used() (+50 more)

### Community 76 - "Community 76"
Cohesion: 0.08
Nodes (23): _code_markup(), Random, Style, Text, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el (+15 more)

### Community 77 - "Community 77"
Cohesion: 0.08
Nodes (25): _encode_any(), _error(), LobbyServer, Any, Command, Event, Exception, Path (+17 more)

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
Nodes (40): _decode_any(), Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command() (+32 more)

### Community 83 - "Community 83"
Cohesion: 0.15
Nodes (20): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), _amain(), main() (+12 more)

### Community 84 - "Community 84"
Cohesion: 0.19
Nodes (14): LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met, Run the embedded engine ticker until stopped (the app's engine worker, §3)., The wrapped in-process service (single-player back-compat; never used for remote, _config(), Path, WP61 — the async `GameClient` facade over the in-process service (DESIGN §3/§14), _service() (+6 more)

### Community 85 - "Community 85"
Cohesion: 0.01
Nodes (283): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+275 more)

### Community 86 - "Community 86"
Cohesion: 0.04
Nodes (44): Choices belong to nodes, Compiler and validation, Conditions: a small safe expression language, Cross-cutting invariants, Decision summary, Decisions to confirm before DR-WP01, Dialogue system replacement — proposed plan, Domain actions (+36 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (26): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.08
Nodes (35): Subsystem, Empty the fusion reactor's keystone slot — the minimal break that derelicts a ba, _strip_reactor_keystone(), AspectFormula, EngineRoomConfig, The ship-class config for `class_id` — the starter hull or a buyable one., One subsystem's slot layout for a hull (DESIGN §4.1).      `slot_count` fixed sl, Coefficients turning a subsystem's filled slots into a derived aspect (§4.1). (+27 more)

### Community 89 - "Community 89"
Cohesion: 0.29
Nodes (3): MessagesDTO, The messages & log view, projected from the durable event_log (§12)., The durable event log, newest first (§11, §12).

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (29): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+21 more)

### Community 91 - "Community 91"
Cohesion: 0.11
Nodes (27): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random, Ship (+19 more)

### Community 92 - "Community 92"
Cohesion: 0.11
Nodes (19): Wire one group internally as a planar outer-planar graph with zero crossings., Partition sequential IDs into rings of size ``cap * radius``., Add increasingly long ring chords until endpoints reach the warp cap.          S, Replace eligible two-way chords with paired, distant one-way exits.          The, Cache an exact concentric layout for the inspector and nav bearings., Bridge the mesh clusters over grid edges: first a spanning tree across the clust, add_bidirectional(), add_directed() (+11 more)

### Community 93 - "Community 93"
Cohesion: 0.14
Nodes (26): list_portraits(), nebular_bloom(), portraits_dir(), Path, Text, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Run image `path` through chafa and return its decoded ANSI string (the cached un, A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35). (+18 more)

### Community 94 - "Community 94"
Cohesion: 0.22
Nodes (17): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., _inputs() (+9 more)

### Community 95 - "Community 95"
Cohesion: 0.02
Nodes (66): ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state)., The DTO under the highlighted row of `table_id`, or None.          WP-UI21: reso, Summarize the authoritative plotted DTO without duplicating route rules., The subview a category opens on: the requested target if it lives here, (+58 more)

### Community 96 - "Community 96"
Cohesion: 0.10
Nodes (40): _cell_cost(), dig_trench(), _dist(), _in_bounds(), is_landing_site(), landing_sites(), _nearest_unfound(), path_to() (+32 more)

### Community 97 - "Community 97"
Cohesion: 0.10
Nodes (12): BridgedGameClient, Any, A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises)., A `GameService`-shaped synchronous facade over the connected client., An awaitable facade safe to call from Textual's loop (GW-WP07). (+4 more)

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (41): accrue_interest(), alien_drift(), _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16)., Compound interest on every non-empty bank balance (§8)., _config(), _drift_world() (+33 more)

### Community 99 - "Community 99"
Cohesion: 0.07
Nodes (52): _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7). (+44 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.12
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.05
Nodes (40): Architectural decisions, Choosing between the alternatives, Context, Cross-cutting constraints, Decision summary, Decisions to confirm before implementation, Dialogue runtime simplification — alternative proposed plan, DS-WP01 — Spec delta and parity fixtures (S/M) (+32 more)

### Community 103 - "Community 103"
Cohesion: 0.13
Nodes (8): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., Static, Vertical, Widget, The base's standing, on one line, in a bordered panel above the installations.

### Community 104 - "Community 104"
Cohesion: 0.14
Nodes (25): Adjacency, _annotate(), can_warp(), plan_route(), plan_route_legs(), Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For (+17 more)

### Community 105 - "Community 105"
Cohesion: 0.10
Nodes (36): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, WarpDTO, build_nav_strip(), _nearest_free(), _octant(), The main-screen nav rose — a bearing-placed compass of immediate warps (§11).  B (+28 more)

### Community 106 - "Community 106"
Cohesion: 0.14
Nodes (24): CronResolver, Regenerate the universe from the seed and replay the merged timeline (§3, WP12)., rebuild(), _noncore(), WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage(), test_attack_blocked_in_the_core_sanctuary() (+16 more)

### Community 107 - "Community 107"
Cohesion: 0.04
Nodes (120): _archetype(), _builder(), Deterministic builder-archetype assignment for ports and orbital bases., Resolve the species whose configured archetype designed the structure., base_owner_hostile(), Whether an operational base's owner treats the player as an enemy (§4.2, WP40)., player_corp(), The corporation a player belongs to, or None (§4, WP66). (+112 more)

### Community 108 - "Community 108"
Cohesion: 0.14
Nodes (32): combat_contexts(), DialogueIntegrityError, Exception, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3, Assert the §13 dialogue-integrity invariants for a roster (raises on failure)., A roster's dialogue packs fail the §13 integrity checks., reachable_contexts() (+24 more)

### Community 109 - "Community 109"
Cohesion: 0.03
Nodes (81): One traversed sector on a plotted route — what the player reads (§11, WP14)., RouteHopDTO, _derive_tag(), A short uppercase tag from the corp name — internal id, never typed (WP80+)., HaggleScreen, ComposeResult, Submitted, NavRose (+73 more)

### Community 110 - "Community 110"
Cohesion: 0.09
Nodes (12): EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., The embedded ticker (tests/shots that step it directly)., GameServer, Owns one hosted game: the service, the ticker, the single command queue, and ses, Fan freshly-persisted events to every session that should see them (the `on_even, Push queued notifications to one connection until the connection closes (WP65). (+4 more)

### Community 111 - "Community 111"
Cohesion: 0.11
Nodes (35): Lead, LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., A coordinate tip the player accepted from an alien (DESIGN §6.7, the "map" mecha, build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered() (+27 more)

### Community 112 - "Community 112"
Cohesion: 0.08
Nodes (10): _assert_impl(), _assert_remote_impl(), GameClient, Command, Event, Protocol, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Apply a command through the in-process service (events fan out via `on_events`). (+2 more)

### Community 113 - "Community 113"
Cohesion: 0.07
Nodes (57): Merge a generated dialogue sidecar onto the default roster and run §13 integrity, validate_sidecar(), _default_out(), IndentedDumper, _load_existing_packs(), main(), _prompt_yn(), Any (+49 more)

### Community 114 - "Community 114"
Cohesion: 0.09
Nodes (13): CodexEntry, ComputerDTO, ContractDTO, LeadDTO, PlanetDirEntry, PortDirEntry, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, One logged discovery for the Computer's Codex tab (§7, §11, WP11). (+5 more)

### Community 115 - "Community 115"
Cohesion: 0.04
Nodes (64): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), Sizes/counts for the SectorView sprite scene (presentation only, no rules). (+56 more)

### Community 116 - "Community 116"
Cohesion: 0.08
Nodes (20): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+12 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.17
Nodes (20): BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), _cfg(), _commodity(), _event_owner() (+12 more)

### Community 119 - "Community 119"
Cohesion: 0.11
Nodes (16): DistanceBand, _expansive_bands(), _mesh_bands(), _planar_bands(), One distance band (DESIGN §5 step 5): warp-hops from sector 1, inclusive., The parameters specific to one `topology_mode` (DESIGN §5).      Everything a mo, Every species' `home_band` hint must name a configured distance band (§6)., Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).      E (+8 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.17
Nodes (17): is_trader(), movement_policy(), NpcTrade, plan_trade(), _player_sectors(), _port_sectors(), Goal-directed NPC movement policies (DESIGN §8/§10, WP42) — pure core.  Replaces, One resolved NPC trade: the updated port + species and a record of what moved. (+9 more)

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
Cohesion: 0.07
Nodes (9): A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, RouteDTO, _assert_impl(), Command, EncounterDTO, Event, Protocol, The typed surface of the in-process game service (H16). (+1 more)

### Community 127 - "Community 127"
Cohesion: 0.18
Nodes (17): _build_site(), generate_survey(), _landing(), _move_cost(), _passable_components(), Random, Vec, Entry cost on foot; 0 == impassable (hard terrain or settlement masonry). (+9 more)

### Community 128 - "Community 128"
Cohesion: 0.15
Nodes (41): _drop_at(), _dropped(), _map(), _op(), _passable(), Random, GW-WP10 — authoritative tactical assault actions and planetary AI.  Two layers,, A single missile one-shots most emplacements (structure_mult=2.0), so proving (+33 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.22
Nodes (16): _bfs_from(), _pick_by_distance(), plan_move(), Random, Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42)., Hop distance from the nearest `sources` node to every reachable sector (BFS)., Pick the candidate nearest (or farthest, if `maximize`) a target set.      Unrea, _line_state() (+8 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.04
Nodes (35): EngineRoomPreviewDTO, Presentation-only before/after aspects for one prospective install or swap (WP-U, CronTask, GameService, EncounterDTO, Persist the ticker schedule so a reload resumes mid-interval (WP12)., Carried territory stock + devices for the Deploy screen (§10/§14, WP72)., The orbit view for a planet in the player's current sector, if any. (+27 more)

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "EngineRoomDTO"
Cohesion: 0.17
Nodes (9): _Coord, Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who, Partition the grid into contiguous clusters: a deterministic central Core cluste, Number the cells 1..n cluster-by-cluster, returning the sector-id groups (Core i (+1 more)

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 138 - "main"
Cohesion: 0.16
Nodes (15): The next unused name for `kind`. Exhausting a pool falls through to numbering., Draw a POC surface name if available and unused; fall back to kind namer., FindKind, Random, Shared archaeological find identities promoted from the groundwar POC.  The prod, Draw one POC-style archaeological proper name., Stable POC art/name subtype for a compatible production surface kind., Stable POC name for a compatible existing surface discovery. (+7 more)

### Community 139 - "MarketDTO"
Cohesion: 0.13
Nodes (32): _clamp_ship_field(), DevPatchError, Exception, Ship, Field-specific validation for a ship integer set/add (raises on hard limits)., A malformed or impossible dev patch (unknown target, missing entity, bad key)., _apply(), _config() (+24 more)

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.19
Nodes (4): PlaytestControls, Click, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 142 - "TopologyModeConfig"
Cohesion: 0.29
Nodes (13): Run one trade for every NPC merchant working a port this firing (§8, WP43)., trader_step(), A 1-2-3 Frontier chain with a trading port at sector 2 (optionally a player ther, A `selvani` merchant (movement_policy trade_seek in the default roster ⇒ a trade, _selvani(), test_a_distant_player_is_not_warmed(), test_non_trader_species_never_trades(), test_trader_dumps_held_cargo_before_buying() (+5 more)

### Community 143 - "Community 143"
Cohesion: 0.31
Nodes (9): WP74 — the signature-mechanic corpus routes (SEAMS_PLAN A2, decision D4).  The s, Each carrier species' pack routes a choice into its own sig.* namespace (A2 clos, test_alliance_gated_trade_opens_for_sworn_members(), test_escalating_demand_ladder_climbs_and_betrayal_is_permanent(), test_every_dark_hook_has_a_corpus_route(), test_flee_drop_route_pays_once(), test_reprogram_install_flips_the_helot_trade_posture_live(), test_trojan_gift_route_pays_sweetener_then_defuses_for_a_fee() (+1 more)

### Community 144 - "RecordingEncounterService"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 145 - "market_settlement"
Cohesion: 0.15
Nodes (16): hourly_port_economy(), market_settlement(), The hourly port-economy tick: order-book market, or the legacy regen (§8, WP47)., The daily order-book settlement: match the book, move goods+latinum, drip purses, Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., _market_config(), A run of ticked trades (the WP12 rail) is deterministic — the same firings from (+8 more)

### Community 146 - "test_intel_contact.py"
Cohesion: 0.40
Nodes (5): _keepout(), Whether a candidate site cell is too near a settlement or the landing zone., A friendly walled town — resupply + one hint at play time (GW-WP06)., settlement_at(), SurveySettlement

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

### Community 154 - "test_corp.py"
Cohesion: 0.28
Nodes (9): _entity_world(), A generated world with the Concordance placed in the player's sector., A virtuous player is blessed: stage persisted, attitude up, experience paid, spo, A criminal player is cursed: a permanent grudge forms (never_forgets Entity)., The judgment command replays to the identical state hash (the stage-ladder rail), _submit(), test_judgment_reducer_blesses(), test_judgment_reducer_curses_with_grudge() (+1 more)

### Community 155 - "market_view"
Cohesion: 0.31
Nodes (12): _drop_entity(), _inject(), _knows_a_far_discovery(), Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7), Log-coordinates is a reply on the offer_coordinates node, not the greeting — you, Remove the roaming Entity so a test can isolate the regular coordinate-tip mecha, Point the species' knowledge at a real, reachable, unexplored rare+ discovery., test_accept_lead_without_a_tip_is_rejected() (+4 more)

### Community 156 - ".compose"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 157 - "Ticker"
Cohesion: 0.29
Nodes (3): CorpDTO, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The player's corporation for the `T` screen — roster, bank, holdings, wars (§4,

### Community 158 - "StaticGenerator"
Cohesion: 0.31
Nodes (6): Random, Text, Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.  Un, Generates a frame of random low-contrast static ("snow")., Fill a `width` × `height` frame with weighted random noise glyphs.          `sub, StaticGenerator

### Community 159 - "Game-state interaction with alien dialogue"
Cohesion: 0.17
Nodes (11): Determinism and persistence, Dialogue types currently supported, `DialogueWhen.criteria` fact map, Game-state interaction with alien dialogue, Minimal branching model, Other state that gates replies or selects a dialogue path, Runtime boundary, Selection and realization (+3 more)

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 161 - ".state"
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 162 - "market_view"
Cohesion: 0.29
Nodes (3): Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, SurveyExpeditionDTO, The active survey's fog-safe viewport, or ``None`` while in orbit (GW-WP07).

### Community 163 - "TavernDTO"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

### Community 164 - "RemoteSession"
Cohesion: 0.25
Nodes (5): Command, Event, Persisted events after `seq`, each with its seq — the reconnect catch-up buffer, Render one event for the live ticker, with a spatial sector gutter (§5.1, §11)., Validate, persist, and apply a command; return the events it produced.

### Community 165 - "EngineRoomDTO"
Cohesion: 0.40
Nodes (4): Debris, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, Scatter drifting-wreckage clumps across the midfield (graveyard     scenarios) —, seed_debris()

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 168 - "event_visible_to"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Write the dialogue simplification review up into a proposed plan and place it in docs/, Source Nodes

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 171 - "station_archetypes.py"
Cohesion: 0.40
Nodes (4): test_governance_tick_is_deterministic_under_replay(), A short command log ending in BeginAssault, replayed twice from the same seed,, test_begin_assault_replay_is_deterministic(), test_stardock_colonists_themes()

### Community 172 - "_SpriteCard"
Cohesion: 0.29
Nodes (5): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard

### Community 173 - "messages_view"
Cohesion: 0.50
Nodes (3): CommodityPricing, The pricing inputs for one commodity., Per-commodity pricing inputs for the §8 stock-ratio formula.

### Community 174 - "Community 174"
Cohesion: 0.50
Nodes (4): note(), note_topic(), Record that `context` was spoken this visit (`asked.<context>: true`)., The session with one fact recorded (a no-op when it already holds).

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 176 - "landing_sites"
Cohesion: 0.09
Nodes (31): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, AuthoringError, _placeholders_in(), prune_unreachable(), Exception, A generated grammar failed validation (bad placeholder, empty render, …)., Assert a generated grammar is fillable, well-formed, and renders non-empty (§13) (+23 more)

### Community 177 - "LiveSysopService"
Cohesion: 0.50
Nodes (3): pick_subsystem(), Engine-room subsystem icons for the TUI (UI_MOCKUPS.md §8).  The procedural `edg, The decorative ASCII icon for an engine-room subsystem (§8).

### Community 178 - "_entity_world"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Read docs/DIALOGUE_GAME_STATE.md and suggest some simplications. The current system seems quite convoluted and spread across too many different seperate systems. It also feels limited and inflexible., Source Nodes

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

### Community 182 - ".boarded_starbase_id"
Cohesion: 0.67
Nodes (3): _canonical(), Any, Recursively convert an entity tree into a JSON-stable, comparable form.

## Knowledge Gaps
- **137 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script` (+132 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `DialogueChoice` (2× useful, score=1.999633853)
- `ContactSession` (2× useful, score=1.999633853)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Community 129`, `Screens, DTOs & Remote Play`, `Standing, Corp & Combat Rules`, `test_ui_cloud_city.py`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `MarketDTO`, `Domain Models & Colonizability`, `Encounters & Station Archetypes`, `Dialogue-Pack Save Guard`, `Engine-Room Component Workbench`, `TopologyModeConfig`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `UI Mockup Screenshot Harness`, `Config Schema Models`, `Signature Mechanics`, `Core Governance & Seizure`, `Spacebattle Battle Screen`, `.state`, `Market Economy & Pricing`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `Base Screen Chrome & Saves`, `Community 42`, `messages_view`, `Community 45`, `Community 48`, `Community 49`, `Community 61`, `Community 63`, `Community 68`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 77`, `Community 79`, `Community 83`, `Community 84`, `Community 85`, `Community 88`, `Community 91`, `Community 95`, `Community 98`, `Community 99`, `Community 107`, `Community 108`, `Community 109`, `Community 110`, `Community 111`, `Community 112`, `Community 115`, `Community 117`, `Community 118`, `Community 119`, `Community 121`, `test_ui_black_hole.py`?**
  _High betweenness centrality (0.159) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 42` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Community 130`, `Screens, DTOs & Remote Play`, `test_ui_cloud_city.py`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Disposition Bands & Ship Classes`, `MarketDTO`, `Community 141`, `TopologyModeConfig`, `Game Lifecycle & Pathfinding`, `market_settlement`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `test_intel_contact.py`, `UI Mockup Screenshot Harness`, `The Entity & Command Reduce`, `Config Schema Models`, `Community 147`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Config Loading & Sidecar Merge`, `Community 45`, `Community 49`, `Community 54`, `Community 59`, `Community 61`, `Community 70`, `Community 71`, `Community 73`, `Community 74`, `Community 75`, `Community 84`, `Community 85`, `Community 88`, `Community 91`, `Community 96`, `Community 98`, `Community 99`, `Community 106`, `Community 107`, `Community 112`, `Community 119`, `Community 121`, `test_ui_black_hole.py`, `Community 127`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Community 42` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Community 130`, `Screens, DTOs & Remote Play`, `test_ui_cloud_city.py`, `Aliens & Alliance Admission`, `Standing, Corp & Combat Rules`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `Community 128`, `MarketDTO`, `TopologyModeConfig`, `Community 143`, `market_settlement`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `The Entity & Command Reduce`, `Signature Mechanics`, `test_corp.py`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `market_view`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `Community 48`, `Community 49`, `Community 59`, `Community 61`, `Community 69`, `Community 70`, `Community 73`, `Community 74`, `Community 75`, `Community 84`, `Community 85`, `Community 96`, `Community 98`, `Community 99`, `Community 106`, `Community 107`, `Community 108`, `Community 111`, `Community 112`, `Community 115`, `Community 118`, `Community 121`, `test_ui_black_hole.py`, `Community 127`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 158 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 158 INFERRED edges - model-reasoned connections that need verification._
- **Are the 370 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 370 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._