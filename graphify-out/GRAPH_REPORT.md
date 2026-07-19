# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 331 files · ~9,148,055 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 7941 nodes · 33989 edges · 184 communities (157 shown, 27 thin omitted)
- Extraction: 69% EXTRACTED · 31% INFERRED · 0% AMBIGUOUS · INFERRED: 10559 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `787ec2af`
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
- Community 143
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 157
- Community 160
- Community 166
- Community 169
- Community 170
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
1. `UniverseState` - 504 edges
2. `GameConfig` - 444 edges
3. `Commodity` - 420 edges
4. `reduce()` - 368 edges
5. `EconomyError` - 334 edges
6. `EdgeApp` - 259 edges
7. `ComponentTier` - 230 edges
8. `Warp` - 229 edges
9. `apply_result()` - 222 edges
10. `Event` - 212 edges

## Surprising Connections (you probably didn't know these)
- `test_width_grows_monotonically_and_respects_bounds()` --calls--> `compose_horizontal()`  [EXTRACTED]
  tests/test_ship_art.py → edge/art/hull.py
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_different_seeds_differ()` --calls--> `generate()`  [EXTRACTED]
  tests/test_bigbang.py → edge/bigbang/generator.py
- `test_generation_is_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_bigbang.py → edge/bigbang/generator.py
- `test_topology_modes_differ()` --calls--> `generate()`  [EXTRACTED]
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

## Communities (184 total, 27 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.08
Nodes (447): AmountPrompt, _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes (+439 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.03
Nodes (90): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, The roaming Entity's always-on in-sector presence hint (DESIGN §7, WP35).      F (+82 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.02
Nodes (95): ArmamentItem, Aspect, BountyDTO, CodexEntry, CommodityLine, ComputerDTO, ContractDTO, CorpMemberDTO (+87 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.03
Nodes (238): GameConfig, Top-level config bundle, validated from the parsed YAML mapping., player_corp(), The corporation a player belongs to, or None (§4, WP66)., deposit(), EconomyError, Exception, Move latinum on-hand into the bank (no negative on-hand balance). (+230 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.02
Nodes (138): One traversed sector on a plotted route — what the player reads (§11, WP14)., RouteHopDTO, EdgeApp, Resize, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)., Tear down the remote loop/thread on exit (WP68). (+130 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.02
Nodes (175): admission_met(), admission_tasks_done(), base_owner_hostile(), The admission tasks the player has completed for a bloc (the §6.3 ledger)., Whether the player has completed the bloc's `admission_price` tasks (§6.3)., Whether an operational base's owner treats the player as an enemy (§4.2, WP40)., player_owns(), Whether `player_id` counts as an owner of a holding (§4.2/§4-WP66).      True fo (+167 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.03
Nodes (57): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state)., The DTO under the highlighted row of `table_id`, or None.          WP-UI21: reso (+49 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.04
Nodes (92): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+84 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.09
Nodes (25): ComposeResult, Pressed, Submitted, Enter in a row's amount field submits that row in the colony-supply direction, A modal transfer editor for the player-owned world in the current sector., TransferWorkbenchScreen, _has_scrollable_ancestor(), _new_game() (+17 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.06
Nodes (58): attitude_locked(), Whether a permanent grudge locks the attitude offset for good (§6.5).      A `ne, ContractsConfig, Favors + escort contracts issued through the dialogue system (DESIGN §6.7, §14 —, active(), advance_convoy(), apply_reward(), by_id() (+50 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.17
Nodes (10): Resize, Static, Exterior-art footprint beside a service banner, from scene config.      `expect_, station_icon_dimensions(), _StationArt, Scaling the left-hand silhouette must never route it through port art., The published reference is only trusted for the sector being drawn: a caller, test_docked_header_rejects_a_reference_from_another_sector() (+2 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.03
Nodes (107): _alliance_key(), alliance_rivals(), alliance_standing(), apply_join_standing(), apply_resign_standing(), attitude_offset(), _clamp01(), core_bases_razed() (+99 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.07
Nodes (52): range, enroll(), generate_with_player(), Any, Shared test helpers.  The big bang no longer seeds players — enrolling a player, Enroll a player into an already-generated universe (mutates + returns `state`)., `generate()` then `enroll()` — the common "fresh game with player 1" setup., test_no_roster_falls_back_to_federation_stub() (+44 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.03
Nodes (75): ActiveBinding, One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).      `s, One subsystem panel: its derived aspect and its slot grid (§4.1)., Slot, Subsystem, AmountPrompt, ContextStrip, EdgeScreen (+67 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.03
Nodes (79): Container, TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), Any, EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Persist local-only presentation settings and apply the theme immediately., Tick off a Captain's objective (WP-UI11) — local progress only.          Called (+71 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.06
Nodes (80): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, Path, SqliteRepository, A deterministic fingerprint of the live entity state (RNG/adjacency excluded)., state_hash() (+72 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.05
Nodes (49): build_graph(), Build the warp graph and return its adjacency plus the region groups., bfs_distances(), Forward hop distance from `src` to every reachable sector.      Accepts any int-, Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).      E, TopologySet, A drawn species is met as a *cluster* of ships near its home, not a lone contact, test_species_field_home_clusters_within_radius() (+41 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.03
Nodes (189): apply_result(), Command, Upsert a reducer's new entities into the mutable container (sanctioned)., Validate `command` for `player_id` and return its delta + events., Legal sectors a fleeing pack may warp to (§10, WP-PR03) — pure, stable order., reduce(), _retreat_destinations(), instance_key() (+181 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.03
Nodes (70): clear_slot(), Save-slot location and lifecycle (DESIGN §12).  One file per game in WAL mode un, Lightweight save metadata for the menu (WP-UI11) — no replay needed., Remove the save and its WAL/SHM sidecars so a new game starts clean., SaveSummary, ComposeResult, Pressed, RumorModal — reveals the lead a tavern rumour just bought (WP-PR2-03 / PT-35). (+62 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.05
Nodes (88): Alliance, Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe, A ship hull (DESIGN §4).      A player hull carries `subsystems` (the engine-roo, Holds occupied — trade cargo plus loose (uninstalled) components.          Loose, An alliance / rival bloc (DESIGN §4/§6.3).      No alliance is privileged in the, Ship, corp_view() (+80 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.05
Nodes (44): The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_engine_room(), sample_planet(), sample_surface() (+36 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.06
Nodes (66): MarketOrderDTO, One open order on the Computer's Market tab (§8, WP48)., A named cluster from generation (DESIGN §4/§5)., Region, _event_player(), event_visible_to(), game_view(), market_view() (+58 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.02
Nodes (139): BaseModel, CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random (+131 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.05
Nodes (71): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+63 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.04
Nodes (62): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+54 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.07
Nodes (55): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, author_line(), AuthoringError, AuthoringRequest, build_prompt(), grammar_schema() (+47 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.04
Nodes (80): _archetype(), _builder(), Resolve the species whose configured archetype designed the structure., alliance_standing_shift(), grudge_shift(), The greeting-vs-violence penalty from ill standing with a species' bloc (§6.3)., The active-grudge penalty this species applies to the player (§6.5, §10).      T, PackConfig (+72 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.11
Nodes (40): governance_tick(), NPC Core seizures + leadership intrigue on the daily clock (§6.3, WP51).      A, _as_result(), _base(), _champion(), _gov_config(), _gov_world(), _intrigue_world() (+32 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.09
Nodes (47): apply_dev_patch(), _clamp_ship_field(), DevPatchError, _expire_contract(), _force_settlement(), _moderate_notice(), _parse_component(), Exception (+39 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.04
Nodes (30): GameService, EncounterDTO, Event, Apply an engine cron's result: upsert entities + persist its durable trail., Persisted events after `seq`, each with its seq — the reconnect catch-up buffer, Persist the ticker schedule so a reload resumes mid-interval (WP12)., Carried territory stock + devices for the Deploy screen (§10/§14, WP72)., The alien-contact screen for a species in the player's sector (§6, WP9, WP17). (+22 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (34): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+26 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.06
Nodes (32): _amain(), _build_game(), _error(), GameServer, LobbyServer, main(), Any, Command (+24 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.07
Nodes (67): DrawFn, EconomyConfig, The pricing inputs for one commodity., The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., clear_filled(), desired_stock_frac(), generate_orders() (+59 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.11
Nodes (25): build_parser(), _build_patch(), cmd_governance(), cmd_list(), cmd_show(), _components(), _diff_after(), dispatch() (+17 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (56): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal, A hunted player is turned away at the Core Stardock; others dock freely (WP52). (+48 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (29): BotRecord, The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Pressed, Submitted (+21 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.05
Nodes (59): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., load_config() (+51 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.05
Nodes (39): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, BaseScreen, ComposeResult, Static, Vertical, Widget, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th (+31 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.06
Nodes (46): Cell, A surface-exploration site on a descended planet (UI_MOCKUPS.md §4, §7).      `s, SurfaceSite, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor (+38 more)

### Community 42 - "Community 42"
Cohesion: 0.04
Nodes (103): _finalize_planets(), _host_markets(), _make_port(), _mid_stock(), _normalize_belts(), _place_starbases(), populate(), Random (+95 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (28): `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, BotRunner, Command, Event, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69)., Drives one player of a game through the `ServiceProtocol` seam (dev-tier, WP60). (+20 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (26): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+18 more)

### Community 45 - "Community 45"
Cohesion: 0.05
Nodes (40): ABC, BaseException, CronResolver, DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12)., The save was made with a different dialogue pack; replay would fail mid-way., EngineState (+32 more)

### Community 46 - "Community 46"
Cohesion: 0.04
Nodes (48): ContactChoiceDTO, ContactDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), A peaceful alien contact screen (§6, §6.7, §11)., One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, TechOfferDTO, Resize, Static (+40 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (28): AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed, Shared exact-amount field with −/+ stepping for logistics and recruitment., An integer input followed by decrement/increment buttons., Clamp an over-cap typed value back to `maximum` in place, so the field can (+20 more)

### Community 48 - "Community 48"
Cohesion: 0.06
Nodes (69): DataObject, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), port_unit_price() (+61 more)

### Community 49 - "Community 49"
Cohesion: 0.04
Nodes (116): cloud_city_art(), The floating-city structure for a city of `size`, shrunk to fit `width`×`height`, Planet, A planet (DESIGN §4.2): a typed, ownable, producing world.      `planet_type` fi, _add(), belt_mining_yield(), colonist_blocker(), colonist_capacity() (+108 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (39): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+31 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.08
Nodes (14): GameScreen, Event, Whether the sidebar fits — hidden on narrow terminals so the sector view, The event-log lines, most recent last (a single fallback when empty)., Open the fight screen, never a duplicate (WP-fix): a confirm-modal dismiss can, Route a movement interruption (§10, WP24): a violence opener pushes the, Open the unified base view for the starbase here (§4.2, WP80).          No longe, Hail the first friendly species in this sector (H is a shortcut; click a ship to (+6 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (34): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+26 more)

### Community 54 - "Community 54"
Cohesion: 0.04
Nodes (55): main(), PlaytestApp, PlaytestControls, PlaytestService, Click, ComposeResult, Dialogue play-test harness (dev-only — DESIGN §6.7, §13).  Reads the authored di, One representative sector per place a contact can happen: the Core, then each ba (+47 more)

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (42): Exception, One connected client: the socket, the authenticated account, and the seat it hol, A JSON-RPC error to return to the caller (code + message)., RpcError, Session, A stable hash of the protocol surface — client and server refuse a mismatch at h, wire_fingerprint(), _bound_session() (+34 more)

### Community 56 - "Community 56"
Cohesion: 0.10
Nodes (23): flip_row(), Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Slot, The authored row-height of a ship grammar tier (all parts share it)., Pick the tallest tier whose authored height fits ``height``; falls back to     t, _select_grammar(), _tier_height(), _all_glyphs() (+15 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (56): compose_horizontal(), HullStyle, Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Palette for a hull: three shading levels, the navigation-beacon hue pools     (a, Resolve an ``archetype_id`` to its palette, falling back to Federation grey. (+48 more)

### Community 58 - "Community 58"
Cohesion: 0.07
Nodes (37): Procedural ASCII art generation logic., _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+29 more)

### Community 59 - "Community 59"
Cohesion: 0.09
Nodes (24): _Coord, MeshTopology, OutEdges, Wire one group internally as a planar outer-planar graph with zero crossings., Dense concentric rings numbered outward from sector 1.      Sector 1 has ``max_w, Partition sequential IDs into rings of size ``cap * radius``., Add increasingly long ring chords until endpoints reach the warp cap.          S, Replace eligible two-way chords with paired, distant one-way exits.          The (+16 more)

### Community 60 - "Community 60"
Cohesion: 0.08
Nodes (24): _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl, The same actionable Stardock service projections the regular client receives. (+16 more)

### Community 61 - "Community 61"
Cohesion: 0.06
Nodes (18): Any, Command, Event, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Apply a command through the in-process service (events fan out via `on_events`)., Yield events as they are produced — the service pushes both apply + tick events., A `GameClient` over a websocket to `edge-server` (WP68) — the hosted-play seam., Open the socket and complete the fingerprint handshake (refuses a build mismatch (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.06
Nodes (25): GroundwarApp, HelpScreen, main(), Pressed, `edge-groundwar` — the ground-war POC's Textual shell.  Throwaway UI (the `tui`-, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., Mode / planet / seed pickers; platoon composer (assault) or world toggle     (ex, The reusable composer committed a squad — build the raid and drop in. (+17 more)

### Community 63 - "Community 63"
Cohesion: 0.09
Nodes (22): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, _add_structure() (+14 more)

### Community 64 - "Community 64"
Cohesion: 0.11
Nodes (45): GarrisonUnit, Battle-state model for the ground-war POC.  Plain mutable dataclasses (this is a, Every action spent — nothing left to do this turn., Structure, Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms() (+37 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (46): DialoguePack, decay_grudges(), is_criminal(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called., Whether the player's alignment marks them criminal in the governor's eyes (§10)., AliensConfig, A named species roster (DESIGN §6): alliances + the species pool drawn from., Dialogue/diplomacy reference integrity (§6, §13): ids and hooks resolve. (+38 more)

### Community 66 - "Community 66"
Cohesion: 0.07
Nodes (21): Resolve a `--route` endpoint token to an internal sector id.      Accepts an int, resolve_sector(), apply_patch_lines(), Apply (or, in dry-run, preview) a DevPatch; return (ok, report lines).      The, FormField, InterventionForm, Any, ComposeResult (+13 more)

### Community 67 - "Community 67"
Cohesion: 0.25
Nodes (9): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.03
Nodes (54): Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, FieldPrompt, Pressed, Submitted, The shared one-field prompt: inline validation, no silent failures.      Subclas, Return (value, None) to accept or (None, reason) to hold the form open., A required-text prompt (notes, notices, beacons, names). (+46 more)

### Community 70 - "Community 70"
Cohesion: 0.11
Nodes (42): Encounter, A live hostile encounter (DESIGN §10, WP24) — hashed core state.      Set on `Pl, fighter_foe(), owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, The garrison as a single all-round combat foe, scaled by fighter count (§10, WP4, encounter_facts(), The live-fight facts a combat beat selects under (§6.7, WP31).      Derived enti (+34 more)

### Community 71 - "Community 71"
Cohesion: 0.07
Nodes (38): Color, available_archetypes(), available_subtypes(), Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype(), Style (+30 more)

### Community 72 - "Community 72"
Cohesion: 0.10
Nodes (35): Backend, DebugBackend, Protocol, Generate one schema-valid JSON grammar for an authoring prompt., Wraps any backend to echo the request/response at the backend boundary to stderr, _default_out(), IndentedDumper, _load_existing_packs() (+27 more)

### Community 73 - "Community 73"
Cohesion: 0.07
Nodes (24): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., ClusteredTopology, ExpansiveTopology, PlanarTopology, Wire one group: a random spanning tree, then edges toward avg degree ~2.5., Trunk topology builder (DESIGN §5). (+16 more)

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (35): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar (+27 more)

### Community 75 - "Community 75"
Cohesion: 0.07
Nodes (51): advance_build(), building(), citadel_defense_mult(), citadel_foe(), CitadelError, conquer(), InvasionOutcome, level_config() (+43 more)

### Community 76 - "Community 76"
Cohesion: 0.12
Nodes (18): Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Deployed forces as glyph-scale presence marks — fighters flying patrol         t (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (31): Assault, ground_access(), OrbitalOnly, Classify how the player may interact with `planet` from orbit (GW plan §contract, This world is only ever interacted with from orbit (no ground operation).      A, This world opens a tactical **assault** once its orbital defences fall (GW-WP08+, Whether the orbital ladder is clear and a platoon could land right now., GroundAccess (+23 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (14): Battle, Event, Side, One cell of rocky debris (belt scenarios). Blocks fire lines and wings;     dest, A missile salvo in flight — a board object chasing its target ship., One log/FX entry drained by the UI after each rules call., A ship (any footprint cell), wing, rock, or wreckage sits here — one         pie, Every board cell of the piece's footprint (anchored on the centre).         Ship (+6 more)

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (22): LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered(), _label(), pick_intel_target() (+14 more)

### Community 80 - "Community 80"
Cohesion: 0.10
Nodes (25): DeployShip, main(), _make_starfield(), Battle, `edge-spacebattle` — the space-battle POC's Textual shell.  Throwaway UI (the `t, A static char-level starfield backdrop with dim placement-grid ticks., One fleet slot during deployment — a hull awaiting a cell and a facing., SpacebattleApp (+17 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (32): alien_dialogue_default.yaml (dialogue corpus), alien_dialogue_species.yaml (species grammars), alien_roster_default.yaml (species roster), default.yaml (game constants), Alien species disposition system, Alliances (rival blocs, join one at a time), Asteroid belt mining (finite reserves), Universe generation (Big Bang) (+24 more)

### Community 82 - "Community 82"
Cohesion: 0.07
Nodes (51): MapNodeDTO, A clickable sector node on the local map: its label's cell box in `rows`.      `, _decode_any(), Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, _encode_any(), Wire-encode any service return value (events, DTOs, primitives, and lists thereo, decode_command(), decode_dto() (+43 more)

### Community 83 - "Community 83"
Cohesion: 0.10
Nodes (31): apply_patch(), Apply (or, in dry-run, preview) a DevPatch and report what changed., config_dump(), _intervene(), _lobby_hint(), main(), menu(), _print() (+23 more)

### Community 84 - "Community 84"
Cohesion: 0.10
Nodes (29): _footer_keys(), _open_computer(), PT-32 — the Computer's keyboard model: a tab owns its keys.  The screen binds on, chrome.EdgeScreen pins Back first — it used to fall in behind whatever the     f, PT-51: `P` on the Map plots a course to the highlighted sector and lands on the, Each category pane owns 1..N for its own sub-tabs — so `2` means a different tab, The corporation lives under Relations now, not behind a game-screen hotkey., Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+21 more)

### Community 85 - "Community 85"
Cohesion: 0.04
Nodes (20): CorpDTO, HaggleQuote, LeadDTO, MarketDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect (+12 more)

### Community 86 - "Community 86"
Cohesion: 0.05
Nodes (60): _make_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, Populate `state.discoveries` deterministically from the seed (§7)., _roll_kind(), _roll_tier() (+52 more)

### Community 87 - "Community 87"
Cohesion: 0.08
Nodes (28): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+20 more)

### Community 88 - "Community 88"
Cohesion: 0.14
Nodes (24): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+16 more)

### Community 89 - "Community 89"
Cohesion: 0.23
Nodes (5): DataTable, RowHighlighted, The commodities trade UI: a live pricing table over the docked port.      Reusab, Rebuild responsive columns while preserving the logical commodity selection., TradePanel

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (29): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+21 more)

### Community 91 - "Community 91"
Cohesion: 0.08
Nodes (25): AnthropicBackend, AntigravityBackend, CliBackend, _extract_json(), get_backend(), OllamaBackend, _parse_claude_envelope(), Any (+17 more)

### Community 92 - "Community 92"
Cohesion: 0.12
Nodes (27): EncounterFoe, One hostile ship of an encounter pack (DESIGN §10, WP24).      Stats are resolve, _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues. (+19 more)

### Community 93 - "Community 93"
Cohesion: 0.19
Nodes (19): list_portraits(), portraits_dir(), Path, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait() (+11 more)

### Community 94 - "Community 94"
Cohesion: 0.12
Nodes (25): BotSetup, CronFn, BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Enrol a bot on `player_id` and let `setup` register its triggers + turn driver., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69) (+17 more)

### Community 95 - "Community 95"
Cohesion: 0.13
Nodes (21): apply_intrigue(), flip_core_governor(), GovernanceDelta, _home_cluster_bases_intact(), IntrigueDelta, _nearest_legal(), npc_seizure_ready(), _operational_core_bases() (+13 more)

### Community 96 - "Community 96"
Cohesion: 0.11
Nodes (19): _best_roundtrip_margin(), _check_degree_cap(), _check_discovery_gradient(), _check_expansive_no_chokepoint(), _check_home_clusters(), _check_planet_ownership(), _check_profitable_pair(), _check_species() (+11 more)

### Community 97 - "Community 97"
Cohesion: 0.14
Nodes (10): Any, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade, Exception (+2 more)

### Community 98 - "Community 98"
Cohesion: 0.07
Nodes (72): may_occupy(), Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules, WP16, _bfs_from(), _pick_by_distance(), plan_move(), _player_sectors(), _port_sectors(), Random (+64 more)

### Community 99 - "Community 99"
Cohesion: 0.08
Nodes (25): CronTask, EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met (+17 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.06
Nodes (52): Adjacency, A text report of a generated universe (the `--stats` dev view, §5)., summarize(), _discoveries(), format_route(), list_items(), _planets(), _ports() (+44 more)

### Community 103 - "Community 103"
Cohesion: 0.14
Nodes (30): combat_contexts(), DialogueIntegrityError, _is_catch_all(), _placeholders_in(), Exception, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3, Assert the §13 dialogue-integrity invariants for a roster (raises on failure). (+22 more)

### Community 104 - "Community 104"
Cohesion: 0.18
Nodes (24): build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., _one_way_span_world(), _phantom_bridges(), Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic., A world reproducing the PT-56 phantom: a **one-way** warp Z→A joins two sectors, Pairs of *non-adjacent* sectors joined on one row by an unbroken, arm-connected, A small branching universe:  1 - 2 - 3 - 4  with a 2 - 5 - 6 spur.      Core hop (+16 more)

### Community 105 - "Community 105"
Cohesion: 0.10
Nodes (37): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, WarpDTO, Shared character-grid canvas and band palette for baked map/nav views (§11).  Bo, build_nav_strip(), _nearest_free(), _octant() (+29 more)

### Community 106 - "Community 106"
Cohesion: 0.12
Nodes (36): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A knocked-out part contributes nothing until it is patched (§4.1). (+28 more)

### Community 107 - "Community 107"
Cohesion: 0.16
Nodes (22): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), FindKind, generate_find_art() (+14 more)

### Community 108 - "Community 108"
Cohesion: 0.05
Nodes (44): Binding, Screen, Open the numbered context-action menu over the current screen (WP73, D3)., Expose current-screen actions through Textual's fuzzy command palette., layout_tier(), Any, Screen, Return the one canonical advertised-action list for a screen.      Danger levels (+36 more)

### Community 109 - "Community 109"
Cohesion: 0.11
Nodes (7): _assert_impl(), Command, EncounterDTO, Event, Protocol, The typed surface of the in-process game service (H16)., ServiceProtocol

### Community 110 - "Community 110"
Cohesion: 0.14
Nodes (16): nebular_bloom(), Text, Run image `path` through chafa and return its decoded ANSI string (the cached un, A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35)., Render image `path` to a Rich `Text` fitted within a `cols`×`rows` character-cel, render_portrait(), _render_portrait_ansi(), Path (+8 more)

### Community 111 - "Community 111"
Cohesion: 0.26
Nodes (13): Phase-3 — location-intel planner + species knowledge table (DESIGN §6.7).  Cover, A placed species whose kind knows at least one place, plus a fresh player+ship., The reserved Entity codex row is Legendary but must never enter a knowledge tabl, _speaker_with_knowledge(), _state(), test_entity_tip_is_live_and_outranks_regular_tips(), test_entity_tip_reoffers_only_after_it_moves(), test_explored_or_logged_places_are_never_revealed() (+5 more)

### Community 112 - "Community 112"
Cohesion: 0.06
Nodes (15): LocalMapDTO, The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map(), Bake the local map to fit `width`, overlaying the active route (§6.7/§11)., LocalMapView, Any, Resize (+7 more)

### Community 113 - "Community 113"
Cohesion: 0.15
Nodes (10): Text, What an art panel drew last time, so a rebuilt screen doesn't blink (PT-42).  Se, The art this panel drew last time, or None if it has never been drawn., Record `art` as this panel's latest render and hand it back for painting., remember(), remembered(), Responsive archetype icon + service banner header shared by ports and starbases., Rich `Text` is mutable and callers `stylize()` it (a derelict base dims its icon (+2 more)

### Community 114 - "Community 114"
Cohesion: 0.12
Nodes (12): first_focusable(), focus_content(), TabActivated, Widget, The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target)., Put keyboard focus on `node`'s primary control (see `first_focusable`).      Whe, Shared responsive service navigation for Stardock and orbital bases.      Standa, Switch to `entry_id` and focus its primary content (tab accelerator target). (+4 more)

### Community 115 - "Community 115"
Cohesion: 0.19
Nodes (12): `planar` bridging: connects clusters using a planar spiderweb meta-graph., add_directed(), add_ring_motifs(), carve_core(), compute_bands(), OutEdges, Random, Graph primitives, the Core carve, motifs, and distance bands (DESIGN §5).  The w (+4 more)

### Community 116 - "Community 116"
Cohesion: 0.14
Nodes (13): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+5 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.18
Nodes (14): has_gun(), Whether `planet` fields an operational citadel gun (§4.2, WP54/WP55)., Whether the L3 siege shield bars invasion of `planet` (§4.2, WP55).      True wh, siege_shielded(), assault_blockers(), _friendly(), _inhabiting_species(), _is_inhabited() (+6 more)

### Community 119 - "Community 119"
Cohesion: 0.12
Nodes (10): Any, Sync bridge: drive an async `RemoteClient` from the synchronous TUI (WP68).  The, Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises)., A `GameService`-shaped synchronous facade over the connected client., A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., RemoteBridge (+2 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.16
Nodes (5): _code_markup(), Text, 5 right-aligned trail lines: header, up to 3 history entries, you.          Each, 5 detail lines for the keyboard-selected warp target., Render content tokens (S/P Stardock-port, @ planet) colour-coded by type.

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
Cohesion: 0.30
Nodes (11): _hazard_logged(), _new_game(), _put_black_hole(), WP-PR05 — black-hole interaction never crashes (playtest note PT-28).  A black h, After entering, the black hole sits in the current sector; logging it (the     s, Drop a black hole into `sector_id`; return its discovery id., The full 2x2 acceptance matrix: mouse/keyboard x nonlethal/lethal, identical., _set_hull() (+3 more)

### Community 127 - "Community 127"
Cohesion: 0.36
Nodes (12): _do(), WP66 — corporations: shared bank + assets + corp war (DESIGN §4).  The core inva, Two players (both at sector 1) each with a ship; a planet p1 owns in that sector, test_ceo_leaving_promotes_lowest_id_member(), test_corp_asset_treats_every_member_as_owner(), test_corp_bank_is_non_negative_and_ceo_gated(), test_corp_war_is_mutual_and_hostility_follows(), test_dissolution_rekeys_assets_to_the_departing_ceo() (+4 more)

### Community 128 - "Community 128"
Cohesion: 0.03
Nodes (52): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., notify_warning(), Petition to flip the Core to the championed bloc (§6.3, WP50)., ConfirmScreen, ComposeResult, Pressed (+44 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.24
Nodes (3): EngineRoomDTO, The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)., _room()

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
Cohesion: 0.33
Nodes (4): base_in_sector(), The orbital base in `sector_id`, or None (WP78).      At most one exists — the b, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present.

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (18): GroundwarConfig, GwEmplacement, GwSuit, GwWeapon, A suit/garrison weapon or missile (§ ground combat)., A purchasable powered-armour suit class (GW plan D3)., A static defensive structure (wall/gate/turret/AA/sensor/citadel gun)., Ground-operations balance (survey + assault), one YAML source of truth.      Fie (+10 more)

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
Cohesion: 0.25
Nodes (6): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, TabPane

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

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
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Sector Scene & Widgets`, `Community 129`, `Standing, Corp & Combat Rules`, `UI Config & Route Tests`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `Attitude, Disposition & Contracts`, `Encounters & Station Archetypes`, `Engine-Room Component Workbench`, `Dialogue-Pack Save Guard`, `Community 143`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `Game Lifecycle & Pathfinding`, `Subsystem Layouts & Ownership`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Derived Aspects & Engine Room`, `Bigbang Aliens & Region Control`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Core Rules Tests`, `Community 42`, `Community 43`, `Community 45`, `Community 48`, `Community 49`, `Community 54`, `Community 55`, `Community 59`, `Community 61`, `Community 65`, `Community 68`, `Community 70`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 77`, `Community 79`, `Community 85`, `Community 86`, `Community 88`, `Community 89`, `Community 92`, `Community 94`, `Community 96`, `Community 97`, `Community 98`, `Community 99`, `Community 103`, `Community 109`, `Community 112`, `Community 114`, `Community 117`?**
  _High betweenness centrality (0.164) - this node is a cross-community bridge._
- **Why does `GroundwarConfig` connect `Community 143` to `Core Rules & Events Engine`, `Community 64`, `Groundwar Battle Screen`, `Community 50`, `Config Schema Models`, `Community 62`, `Community 63`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Standing, Corp & Combat Rules` to `Core Rules & Events Engine`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Attitude, Disposition & Contracts`, `Community 139`, `Encounters & Station Archetypes`, `Domain Models & Colonizability`, `Game Lifecycle & Pathfinding`, `The Entity & Command Reduce`, `Subsystem Layouts & Ownership`, `Community 147`, `Market Orders & Regions`, `Config Schema Models`, `Derived Aspects & Engine Room`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Dev Patch Tooling`, `Core-Seizure Confirm Screens`, `Market Economy & Pricing`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 43`, `Community 45`, `Community 48`, `Community 49`, `Community 54`, `Community 59`, `Community 61`, `Community 70`, `Community 71`, `Community 73`, `Community 75`, `Community 77`, `Community 85`, `Community 86`, `Community 95`, `Community 96`, `Community 97`, `Community 98`, `Community 99`, `Community 102`, `Community 109`, `Community 118`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 125 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 125 INFERRED edges - model-reasoned connections that need verification._
- **Are the 330 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 330 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._