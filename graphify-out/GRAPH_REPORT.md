# Graph Report - edge-of-the-unknown  (2026-07-22)

## Corpus Check
- 355 files · ~9,224,429 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 9125 nodes · 42503 edges · 209 communities (182 shown, 27 thin omitted)
- Extraction: 64% EXTRACTED · 36% INFERRED · 0% AMBIGUOUS · INFERRED: 15172 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5f3c7642`
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
- BotRunner API (on/each_turn/apply)
- ComputerDTO
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
- Rock
- graphify.js
- graphify.md
- graphify.md
- __init__.py

## God Nodes (most connected - your core abstractions)
1. `UniverseState` - 593 edges
2. `GameConfig` - 590 edges
3. `Commodity` - 467 edges
4. `reduce()` - 439 edges
5. `EconomyError` - 389 edges
6. `EdgeApp` - 274 edges
7. `apply_result()` - 260 edges
8. `Warp` - 257 edges
9. `ComponentTier` - 252 edges
10. `Event` - 251 edges

## Surprising Connections (you probably didn't know these)
- `test_width_grows_monotonically_and_respects_bounds()` --calls--> `compose_horizontal()`  [EXTRACTED]
  tests/test_ship_art.py → edge/art/hull.py
- `test_every_live_band_has_a_contact()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_roster_alliances_become_entities()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_different_seeds_differ()` --calls--> `generate()`  [EXTRACTED]
  tests/test_bigbang.py → edge/bigbang/generator.py
- `test_generation_is_deterministic()` --calls--> `generate()`  [EXTRACTED]
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

## Communities (209 total, 27 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.10
Nodes (489): _MissingArg, ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes, setup(), _commodity(), Example bot: a pair-trader ping-ponging the best trade route (WP60).  The WP48 b (+481 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.05
Nodes (60): range, enroll(), generate_with_player(), Any, Shared test helpers.  The big bang no longer seeds players — enrolling a player, Enroll a player into an already-generated universe (mutates + returns `state`)., `generate()` then `enroll()` — the common "fresh game with player 1" setup., _quill_state() (+52 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.02
Nodes (144): ArmamentItem, Aspect, BountyDTO, CommodityLine, DeploymentOptionDTO, DossierEntry, EncounterDTO, EncounterFoeDTO (+136 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.10
Nodes (39): InstalledComponent, One component slotted into a subsystem (DESIGN §4.1).      `knocked_out` is set, Filled, non-knocked-out components (the ones the aspect formula counts)., _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem (+31 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.12
Nodes (7): Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)., ComposeResult, Pressed, Vertical, What already sits in this sector, tabular (fog pre-applied upstream)., Apply the same projected blocker to accelerator keys as disabled buttons., TerritoryScreen

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.06
Nodes (64): MarketOrderDTO, One open order on the Computer's Market tab (§8, WP48)., build_subsystems(), Instantiate a hull's starting subsystems from its config layout (§4.1).      Ret, MarketSettled, The daily order-book settlement summary (§8, WP47).      One aggregate emitted p, A ship hull (DESIGN §4).      A player hull carries `subsystems` (the engine-roo, Holds occupied — trade cargo plus loose (uninstalled) components.          Loose (+56 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.06
Nodes (65): Game, Top-level game record (DESIGN §4)., A node in the warp graph (DESIGN §4). `warps_out` are sector ids., A fresh universe seeded from the game's seed (RNG owned here, §3)., Sector, build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., _occupy_species() (+57 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.10
Nodes (46): EncounterFoe, One hostile ship of an encounter pack (DESIGN §10, WP24).      Stats are resolve, _engagement(), _fight_state(), _foe(), _forced_knockout_config(), WP25 — combat rounds: the escape floor, arcs, missiles, and full-fight goldens (, A spinal attacker recharges between volleys — even rounds are safe from it. (+38 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.13
Nodes (32): Cell, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor, _flavor_for(), _land_cell() (+24 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.05
Nodes (42): The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_planet(), sample_surface(), EncounterScreen, _outcome_note() (+34 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.03
Nodes (64): EmptyState, FieldPrompt, Any, ComposeResult, Pressed, Static, Submitted, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches'). (+56 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.19
Nodes (13): expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar, Every authored expansion string in a grammar (for placeholder validation)., _grammar_pack(), Phase-2 — Tracery realisation of dialogue grammars (DESIGN §6.7).  Covers `edge., test_expand_does_not_disturb_global_rng() (+5 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.02
Nodes (131): Container, Sizes/counts for the SectorView sprite scene (presentation only, no rules)., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro (+123 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.02
Nodes (118): Binding, DialogueConfigMismatchError, RuntimeError, The save was made with a different dialogue pack; replay would fail mid-way., main(), Any, LoadProgress, Resize (+110 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.11
Nodes (34): apply_militia_recovery(), derive_difficulty(), _footprint_passable_frac(), generate_assault_map(), Derive battlefield size + surrender threshold from live world state (D11)., Lay out a defended battlefield: terrain + `cities` walled cities, the last one, The (infantry, armor) headcount a freshly-inhabited world starts with (D11)., One day's step toward `cap` at `frac` of the remaining headroom.      Rounds, bu (+26 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.06
Nodes (37): build_graph(), Build the warp graph and return its adjacency plus the region groups., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, _big_expansive_config(), _cross_region_edges(), WP4 — big-bang generation across many seeds (DESIGN §5, §13).  Generates a small, The lattice property (§5): removing any single inter-region warp leaves     ever (+29 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.07
Nodes (79): entity_species(), The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None., instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting() (+71 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.03
Nodes (140): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, salt_raid_caches(), bearing(), _bfs_tree(), compute_embedding() (+132 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.07
Nodes (60): AllianceConfig, One alliance / rival bloc in the roster (DESIGN §6.3).      Joinability (WP38):, A Core-seizure ladder is meaningful only on a `covets_core` bloc (§6.3, WP50)., AllianceLeadershipChanged, GovernanceChanged, Core Space changed hands to a new governing alliance (§6.3, §4.2, WP49).      `c, An internal coup swapped a bloc's leader (§6.3, WP51).      `old_leader_roster`/, apply_intrigue() (+52 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (80): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+72 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.14
Nodes (40): Exception, A JSON-RPC error to return to the caller (code + message)., RpcError, A stable hash of the protocol surface — client and server refuse a mismatch at h, wire_fingerprint(), _bound_session(), _config(), _lobby() (+32 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.03
Nodes (106): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+98 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.03
Nodes (153): BaseModel, _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7). (+145 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.05
Nodes (69): attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate(), _int(), literalist() (+61 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.10
Nodes (23): flip_row(), Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Slot, The authored row-height of a ship grammar tier (all parts share it)., Pick the tallest tier whose authored height fits ``height``; falls back to     t, _select_grammar(), _tier_height(), _all_glyphs() (+15 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.03
Nodes (73): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed (+65 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.13
Nodes (47): ground_access(), OrbitalOnly, Classify how the player may interact with `planet` from orbit (GW plan §contract, This world is only ever interacted with from orbit (no ground operation).      A, GroundAccess, The case that could not be written before this WP without hand-building state., test_a_real_generated_world_routes_to_assault(), _owned_reinforceable_state() (+39 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.06
Nodes (77): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), dialogue_fingerprint(), A 16-hex-char hash of the choice-cardinality structure across all species packs., _build_game(), Load the game at `db` if it exists, else generate a fresh one there (WP12 resume, LoadProgress, Restore a checkpoint and replay its bounded log tail (§3, §12).          Raises (+69 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.11
Nodes (12): GroundExpeditionScreen, Any, Key, Text, Walk, scan, excavate, and talk through authoritative survey commands., POC camera pan: the cursor rides with the viewport., Enter means "commit the cursor": set down while inbound, march once landed., Why the survey can't act right now, or `None` if it can — shared by march/ (+4 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.04
Nodes (88): _can_hold_a_people(), _guarantee_targets(), _inhabitant(), is_assaultable_for_a_fresh_player(), is_friendly_inhabited(), Random, Seed the inhabited universe: native polities on generated worlds (GW-WP09-PRE)., The below-amity species that could live here, best fit first.          Preferenc (+80 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (35): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+27 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.06
Nodes (16): BattleScreen, MapView, Click, Key, Ship, Text, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays. (+8 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.10
Nodes (15): OutEdges, Wire one group: a random spanning tree, then edges toward avg degree ~2.5., `trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra, `expansive` bridging (§5 step 2): a band-lattice web with no chokepoints., Wire one group internally as a planar outer-planar graph with zero crossings., Dense concentric rings numbered outward from sector 1.      Sector 1 has ``max_w, Partition sequential IDs into rings of size ``cap * radius``., Add increasingly long ring chords until endpoints reach the warp cap.          S (+7 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.04
Nodes (95): DrawFn, _best_roundtrip_margin(), Best per-unit profit buying a commodity from `sell_port` and selling to `buy_por, decay_grudges(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called., EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips. (+87 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.06
Nodes (45): apply_patch(), build_parser(), _build_patch(), cmd_list(), cmd_show(), _components(), _diff_after(), dispatch() (+37 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.08
Nodes (61): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+53 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (29): Brain, BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Path, Pressed (+21 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.05
Nodes (58): load_config(), load_config_with_sidecar(), load_default_config(), _merge_dialogue(), Any, Path, Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Load the bundled default config (`config/default.yaml`). (+50 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.11
Nodes (24): _at_base(), _footer_keys(), PT-32 — the Starbase's keyboard model: a tab owns its keys.  The third and last, Regression: `P` on a derelict base used to crash the TUI.      A base *is* the p, A verb the base cannot honour is not a key at all — the same rule that withholds, Station carries the Status panel, which every base owes you — a hostile base sho, A fresh universe's base is not yours, so at least one service is gated shut — an, Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+16 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.07
Nodes (20): BattleScreen, DeployEntry, MapView, Battle, Click, ComposeResult, Key, Text (+12 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.16
Nodes (21): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), generate_find_art(), _pit() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.02
Nodes (303): player_foe(), Build the combat foe for a *defending player's* live ship (§14, WP67 — attacker-, GameConfig, Top-level config bundle, validated from the parsed YAML mapping., §4/§10 reference integrity: every hull's `armament` ids resolve in the         `, apply_dev_patch(), _force_settlement(), _moderate_notice() (+295 more)

### Community 43 - "Community 43"
Cohesion: 0.07
Nodes (32): BotSetup, load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`). (+24 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (30): A correction clears stale validation copy and restores stable form layout., Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton (+22 more)

### Community 45 - "Community 45"
Cohesion: 0.04
Nodes (52): ABC, BaseException, CronResolver, The saved ticker schedule, or None for a fresh game (WP12)., EngineState, GameMeta, Command, Event (+44 more)

### Community 46 - "Community 46"
Cohesion: 0.10
Nodes (29): _footer_keys(), _open_computer(), PT-32 — the Computer's keyboard model: a tab owns its keys.  The screen binds on, chrome.EdgeScreen pins Back first — it used to fall in behind whatever the     f, PT-51: `P` on the Map plots a course to the highlighted sector and lands on the, Each category pane owns 1..N for its own sub-tabs — so `2` means a different tab, The corporation lives under Relations now, not behind a game-screen hotkey., Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+21 more)

### Community 47 - "Community 47"
Cohesion: 0.03
Nodes (62): ContactChoiceDTO, One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, One authored player reply on a branching dialogue node (§6.7 optional branching), TechOfferDTO, Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait. (+54 more)

### Community 48 - "Community 48"
Cohesion: 0.10
Nodes (43): DataObject, accrue_interest(), execute_trade(), haggle_acceptance_probability(), improvement_fraction(), Random, Ship, quoted_unit_price() (+35 more)

### Community 49 - "Community 49"
Cohesion: 0.03
Nodes (109): Counter, advance_build(), building(), citadel_defense_mult(), citadel_foe(), CitadelError, conquer(), InvasionOutcome (+101 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (41): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+33 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.08
Nodes (23): Any, ComposeResult, DataTable, Horizontal, Static, Rumors, the bounty board, and the noticeboard (§14, WP58)., Left-aligned Stardock silhouette + the active service's ANSI banner.          Th, The recruitment office (§4.2, WP-PR08 / PT-06): berth occupancy + a recruit cont (+15 more)

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
Cohesion: 0.21
Nodes (19): _move_cost(), _passable_components(), Entry cost on foot; 0 == impassable (hard terrain or settlement masonry)., Label the 4-connected passable regions; return (labels, sizes).      Sites and t, _disc(), _planet_with_hidden_and_obvious(), GW-WP05 — survey generation from real universe discoveries (GW plan §GW-M2).  Tw, _survey() (+11 more)

### Community 57 - "Community 57"
Cohesion: 0.09
Nodes (23): _grammar_floor(), _mirror_row(), Slot, Expand a left-half row (centre column included) to a full symmetric row:     the, The shortest height this grammar can compose: the smallest part in each     slot, Pick the richest grammar tier (listed largest-floor first) whose minimum     sta, _select_grammar(), _mirror_line() (+15 more)

### Community 58 - "Community 58"
Cohesion: 0.11
Nodes (20): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+12 more)

### Community 59 - "Community 59"
Cohesion: 0.09
Nodes (40): _luminance(), Rec.601 perceived luminance of an (r, g, b) triple in 0..1., A friendly settlement visible on the projected survey map.      ``plaza_x``/``pl, SurveySettlementDTO, ground_operation_view(), Project the player's active ground operation through one fog-safe seam.      Sur, _inhabited_view(), _landed() (+32 more)

### Community 61 - "Community 61"
Cohesion: 0.07
Nodes (21): Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Duck-typed `ServiceProtocol`: each method blocks on the async client twin., _SyncClientFacade, LinkLost, Any, Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), The websocket dropped mid-call — surfaced to the TUI as a retryable status, not (+13 more)

### Community 62 - "Community 62"
Cohesion: 0.10
Nodes (13): ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key, Text, Widget (+5 more)

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (26): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, _add_structure() (+18 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (43): _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus(), cover_at(), defense_phase() (+35 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (49): DialoguePack, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, allowed_placeholders(), Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, The placeholder names a variant of `context` may use (validator + authoring)., Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace (+41 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (19): Resolve a `--route` endpoint token to an internal sector id.      Accepts an int, resolve_sector(), FormField, InterventionForm, Any, ComposeResult, DataTable, HeaderSelected (+11 more)

### Community 67 - "Community 67"
Cohesion: 0.13
Nodes (6): ContactDTO, A peaceful alien contact screen (§6, §6.7, §11)., The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any., Plain-language meaning alongside the exact effective-disposition cue.

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (12): ActionCatalog, ActionOutcome, _parse_component(), Any, Parse the projected loose-part label ``converter (II) x1``., What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it. (+4 more)

### Community 69 - "Community 69"
Cohesion: 0.03
Nodes (113): _band(), _discoveries(), format_route(), _inhabitants(), list_items(), _num(), _owner(), _planets() (+105 more)

### Community 70 - "Community 70"
Cohesion: 0.12
Nodes (42): NpcEntry, owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, The outcome of an NPC entering a defended sector (§10, WP-PR02).      `destroyed, Resolve `force`'s defenses against `species` drifting in (§10, WP-PR02) — pure,, resolve_npc_entry(), _force(), _generated() (+34 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (31): Color, available_archetypes(), Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype(), Style, Text, (entity_type, subtype) for a ship `role`, or a free-text ship-name fallback. (+23 more)

### Community 72 - "Community 72"
Cohesion: 0.08
Nodes (25): AnthropicBackend, AntigravityBackend, CliBackend, _extract_json(), get_backend(), OllamaBackend, _parse_claude_envelope(), Any (+17 more)

### Community 73 - "Community 73"
Cohesion: 0.10
Nodes (47): _aa_reaction_acc(), _apply_resolve(), assault_drop(), _Battle, _battle_cover_at(), _battle_move_cost(), broadcast_terms(), _check_casualties() (+39 more)

### Community 74 - "Community 74"
Cohesion: 0.07
Nodes (46): active(), advance_convoy(), apply_reward(), by_id(), complete_destroy_on_kill(), complete_destroy_on_raze(), convoy_for(), _deliver_target() (+38 more)

### Community 75 - "Community 75"
Cohesion: 0.07
Nodes (67): BarracksItem, GroundForceDTO, LoadoutOptionDTO, One buyable hull in the Stardock shipyard, with a stat line (§8, §11)., One row of the Stardock barracks catalog (GW-WP08, D3).      Recruits are *hired, One platoon-composer row — an affordance the player can actually deploy (GW-WP08, The ground force aboard, as the platoon composer sees it (GW-WP08, D3)., ShipyardItem (+59 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (18): Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Deployed forces as glyph-scale presence marks — fighters flying patrol         t (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.06
Nodes (33): _amain(), _encode_any(), _error(), GameServer, LobbyServer, Any, Command, Event (+25 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (12): Battle, Debris, Event, Side, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, A missile salvo in flight — a board object chasing its target ship., One log/FX entry drained by the UI after each rules call., A ship (any footprint cell), wing, rock, or wreckage sits here — one         pie (+4 more)

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
Cohesion: 0.10
Nodes (38): decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command(), encode_dto(), encode_event() (+30 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (19): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), main(), _parse_args() (+11 more)

### Community 84 - "Community 84"
Cohesion: 0.14
Nodes (16): LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met, Run the embedded engine ticker until stopped (the app's engine worker, §3)., The embedded ticker (tests/shots that step it directly)., The wrapped in-process service (single-player back-compat; never used for remote, Tear down remote resources or checkpoint the embedded game on exit., _config(), Path (+8 more)

### Community 85 - "Community 85"
Cohesion: 0.02
Nodes (248): admission_met(), admission_tasks_done(), _alliance_key(), alliance_rivals(), alliance_standing(), alliance_standing_shift(), apply_join_standing(), apply_resign_standing() (+240 more)

### Community 86 - "Community 86"
Cohesion: 0.04
Nodes (44): Choices belong to nodes, Compiler and validation, Conditions: a small safe expression language, Cross-cutting invariants, Decision summary, Decisions to confirm before DR-WP01, Dialogue system replacement — proposed plan, Domain actions (+36 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (26): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.08
Nodes (37): DiscoveryNamer, _fallback_prefix(), NameGenerator, Random, Deterministic naming generator based on configurable name pools., Draws names without replacement from a pool of combinations., Draws the next combination. Falls back to numbered prefix if exhausted., Names discoveries per kind from `names.discoveries` (PT-49, DESIGN §7).      One (+29 more)

### Community 89 - "Community 89"
Cohesion: 0.11
Nodes (4): _decode_any(), EncounterDTO, Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, T

### Community 90 - "Community 90"
Cohesion: 0.11
Nodes (31): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+23 more)

### Community 91 - "Community 91"
Cohesion: 0.08
Nodes (34): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), Random, Ship, Subsystem (+26 more)

### Community 92 - "Community 92"
Cohesion: 0.16
Nodes (14): _cluster_groups(), `planar` bridging: connects clusters using a planar spiderweb meta-graph., Partition `sectors` into contiguous groups of size [cluster_min, cluster_max]., add_directed(), add_ring_motifs(), carve_core(), compute_bands(), OutEdges (+6 more)

### Community 93 - "Community 93"
Cohesion: 0.14
Nodes (26): list_portraits(), nebular_bloom(), portraits_dir(), Path, Text, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Run image `path` through chafa and return its decoded ANSI string (the cached un, A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35). (+18 more)

### Community 94 - "Community 94"
Cohesion: 0.22
Nodes (17): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., _inputs() (+9 more)

### Community 95 - "Community 95"
Cohesion: 0.02
Nodes (69): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state)., The DTO under the highlighted row of `table_id`, or None.          WP-UI21: reso (+61 more)

### Community 96 - "Community 96"
Cohesion: 0.07
Nodes (58): _build_site(), _cell_cost(), dig_trench(), _dist(), generate_survey(), _in_bounds(), is_landing_site(), _keepout() (+50 more)

### Community 97 - "Community 97"
Cohesion: 0.07
Nodes (18): Any, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., RemoteSession, BridgedGameClient, Any, Sync bridge: drive an async `RemoteClient` from the synchronous TUI (WP68).  Mos (+10 more)

### Community 98 - "Community 98"
Cohesion: 0.06
Nodes (82): may_occupy(), Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules, WP16, Grudge, A durable, dated grievance (DESIGN §4, §6.5) — the diplomacy layer's memory., _bfs_from(), _grudge_targets(), _pick_by_distance(), plan_move() (+74 more)

### Community 99 - "Community 99"
Cohesion: 0.11
Nodes (35): apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., Command, Validate, persist, and apply a command; return the events it produced., Apply an engine cron's result: upsert entities + persist its durable trail., test_invasion_commits_fighters_and_flips_ownership_on_victory(), test_invasion_fighters_never_minted_and_repulse_costs_them(), test_command_log_rebuilds_to_identical_hash() (+27 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.06
Nodes (49): `fg` unchanged if it reads against `bg`, else a hue-preserving variant     (ligh, readable_fg(), GroundCellDTO, One sensor contact, masked until excavation settles the real discovery (G6/G7)., Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, SurveyContactDTO, SurveyExpeditionDTO (+41 more)

### Community 102 - "Community 102"
Cohesion: 0.05
Nodes (40): Architectural decisions, Choosing between the alternatives, Context, Cross-cutting constraints, Decision summary, Decisions to confirm before implementation, Dialogue runtime simplification — alternative proposed plan, DS-WP01 — Spec delta and parity fixtures (S/M) (+32 more)

### Community 103 - "Community 103"
Cohesion: 0.15
Nodes (4): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present.

### Community 104 - "Community 104"
Cohesion: 0.12
Nodes (24): Adjacency, _annotate(), can_warp(), plan_route(), plan_route_legs(), Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For, The sectors reachable in one hop from `sector_id`. (+16 more)

### Community 105 - "Community 105"
Cohesion: 0.17
Nodes (25): build_nav_strip(), _nearest_free(), _octant(), The main-screen nav rose — a bearing-placed compass of immediate warps (§11).  B, Snap a bearing (radians, 0 = east, +y = north) to one of 8 compass octants., The preferred octant, or the closest free one (deterministic +d before -d)., The cell text: spatial id plus content codes once charted (fog masks codes)., Band tint for a charted warp; dim for an uncharted one (matches the local map). (+17 more)

### Community 106 - "Community 106"
Cohesion: 0.06
Nodes (63): normalize_belt(), Scrub colony/citadel/base affordances off a non-landable spatial world (§4.2)., Command, Validate `command` for `player_id` and return its delta + events., reduce(), _generated(), test_advance_then_join_succeeds_and_is_exclusive(), test_join_liberty_front_is_free_and_sours_governor() (+55 more)

### Community 107 - "Community 107"
Cohesion: 0.05
Nodes (89): CorpMemberDTO, One member row on the corp screen (§4, WP66)., build_layouts(), Instantiate intact subsystems from a layout mapping (§4.1).      Base components, Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe, A fixed-length slot tuple for one subsystem (DESIGN §4.1).      `slots[i]` is th, An orbital starbase (DESIGN §4.2): the engine-room model minus mobility.      A (+81 more)

### Community 108 - "Community 108"
Cohesion: 0.09
Nodes (47): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., DialogueIntegrityError, Exception, Resolve and render one line for `context`, returning (text, updated recency ring, A roster's dialogue packs fail the §13 integrity checks. (+39 more)

### Community 109 - "Community 109"
Cohesion: 0.02
Nodes (186): One traversed sector on a plotted route — what the player reads (§11, WP14)., RouteHopDTO, EdgeApp, The synchronous game surface the screens read (WP61/WP68).          Single-playe, clear_slot(), Remove the save and its WAL/SHM sidecars so a new game starts clean., _derive_tag(), A short uppercase tag from the corp name — internal id, never typed (WP80+). (+178 more)

### Community 110 - "Community 110"
Cohesion: 0.16
Nodes (8): CronTask, EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., A run of ticked trades (the WP12 rail) is deterministic — the same firings from, test_ticked_trading_reproduces_to_an_identical_hash()

### Community 111 - "Community 111"
Cohesion: 0.10
Nodes (37): Lead, LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., A coordinate tip the player accepted from an alien (DESIGN §6.7, the "map" mecha, build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered() (+29 more)

### Community 112 - "Community 112"
Cohesion: 0.08
Nodes (10): _assert_impl(), _assert_remote_impl(), GameClient, Command, Event, Protocol, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Apply a command through the in-process service (events fan out via `on_events`). (+2 more)

### Community 113 - "Community 113"
Cohesion: 0.07
Nodes (62): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line() (+54 more)

### Community 114 - "Community 114"
Cohesion: 0.25
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 115 - "Community 115"
Cohesion: 0.02
Nodes (133): ActiveBinding, AmountPrompt, Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, One traversed sector on a planned route (excludes the origin)., RouteHop, GameService (+125 more)

### Community 116 - "Community 116"
Cohesion: 0.14
Nodes (13): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+5 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.13
Nodes (26): CronFn, BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), The pure reducer for a persisted cron name (raises on an unknown name)., resolve_cron() (+18 more)

### Community 119 - "Community 119"
Cohesion: 0.33
Nodes (3): Every species' `home_band` hint must name a configured distance band (§6)., The config block for the selected `topology_mode` (§5 step 5)., The distance bands for the configured `topology_mode` (§5 step 5).

### Community 120 - "Community 120"
Cohesion: 0.24
Nodes (10): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war, WP46/47 — order-book market with hard port purses (+2 more)

### Community 121 - "Community 121"
Cohesion: 0.50
Nodes (4): is_trader(), movement_policy(), Whether `sp` is a merchant that runs real trades (movement policy `trade_seek`,, The species' authored movement policy (`wander` if none / no roster).

### Community 123 - "Community 123"
Cohesion: 0.16
Nodes (18): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+10 more)

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
Cohesion: 0.05
Nodes (53): has_gun(), Whether `planet` fields an operational citadel gun (§4.2, WP54/WP55)., Whether the L3 siege shield bars invasion of `planet` (§4.2, WP55).      True wh, siege_shielded(), _home_cluster_bases_intact(), npc_seizure_ready(), _operational_core_bases(), Operational Core-sector starbases owned by `alliance_id` (the incumbent's grip). (+45 more)

### Community 128 - "Community 128"
Cohesion: 0.23
Nodes (30): _drop_at(), _map(), _op(), _passable(), Random, GW-WP10 — authoritative tactical assault actions and planetary AI.  Two layers,, A single missile one-shots most emplacements (structure_mult=2.0), so proving, A city's sensor radius (16 x a 1.4 signature = 22.4 cells) outranges every suit' (+22 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.09
Nodes (11): AssaultTrooperDTO, One player-owned platoon member; casualties remain listed for the manifest., _DropSlot, GroundAssaultScreen, Key, Text, Compose, deploy, command, and extract one authoritative planetary assault., `CroppedMapView`'s cursor-highlight hook: landable pre-drop, else a legal (+3 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.07
Nodes (17): GroundwarApp, HelpScreen, main(), Pressed, Screen, `edge-groundwar` — the ground-war POC's Textual shell.  Throwaway UI (the `tui`-, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., Mode / planet / seed pickers; platoon composer (assault) or world toggle     (ex (+9 more)

### Community 133 - "Community 133"
Cohesion: 0.17
Nodes (15): WP16 — Alien ship movement (alien_drift cron), Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes (+7 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "EngineRoomDTO"
Cohesion: 0.11
Nodes (18): _Coord, MeshTopology, Random, Mesh topology builder (DESIGN §5)., Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi (+10 more)

### Community 136 - "Community 136"
Cohesion: 0.09
Nodes (29): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl (+21 more)

### Community 138 - "main"
Cohesion: 0.14
Nodes (16): The next unused name for `kind`. Exhausting a pool falls through to numbering., Draw a POC surface name if available and unused; fall back to kind namer., FindKind, Random, Shared archaeological find identities promoted from the groundwar POC.  The prod, Draw one POC-style archaeological proper name., Stable POC art/name subtype for a compatible production surface kind., Stable POC name for a compatible existing surface discovery. (+8 more)

### Community 139 - "MarketDTO"
Cohesion: 0.07
Nodes (52): _clamp_ship_field(), DevPatchError, Exception, Ship, Field-specific validation for a ship integer set/add (raises on hard limits)., A malformed or impossible dev patch (unknown target, missing entity, bad key)., Apply a set/add op to a current integer., _resolve() (+44 more)

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.19
Nodes (4): PlaytestControls, Click, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 142 - "TopologyModeConfig"
Cohesion: 0.10
Nodes (30): Procedural ASCII art generation logic., compose_horizontal(), Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo, Compose a sprite grid by laying parts left-to-right to fill ``target_w``.      O (+22 more)

### Community 143 - "Community 143"
Cohesion: 0.31
Nodes (9): WP74 — the signature-mechanic corpus routes (SEAMS_PLAN A2, decision D4).  The s, Each carrier species' pack routes a choice into its own sig.* namespace (A2 clos, test_alliance_gated_trade_opens_for_sworn_members(), test_escalating_demand_ladder_climbs_and_betrayal_is_permanent(), test_every_dark_hook_has_a_corpus_route(), test_flee_drop_route_pays_once(), test_reprogram_install_flips_the_helot_trade_posture_live(), test_trojan_gift_route_pays_sweetener_then_defuses_for_a_fee() (+1 more)

### Community 144 - "RecordingEncounterService"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 145 - "market_settlement"
Cohesion: 0.09
Nodes (21): GroundwarConfig, GwEmplacement, GwSuit, A purchasable powered-armour suit class (GW plan D3)., A static defensive structure (wall/gate/turret/AA/sensor/citadel gun)., Ground-operations balance (survey + assault), one YAML source of truth.      Fie, _add_structure(), AssaultCity (+13 more)

### Community 146 - "test_intel_contact.py"
Cohesion: 0.13
Nodes (29): assault_broadcast(), assault_end_turn(), assault_fire(), assault_jump(), assault_move(), assault_turn_cost(), AssaultMap, _battle_for() (+21 more)

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
Cohesion: 0.11
Nodes (14): CroppedMapView, _FlashHost, LandingAnimationMixin, Any, Click, Protocol, Text, Base widget for a server-cropped, DTO-projected viewport with a moving camera. (+6 more)

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
Cohesion: 0.14
Nodes (24): is_colonizable(), Whether a world of this type can be claimed and settled (§4.2).      Colonizable, _at_stardock(), _do(), _eligible_planet(), WP10 — Genesis torpedoes: buy at Stardock, terraform an eligible world (§4.2)., test_buy_genesis_at_stardock_costs_latinum(), test_buy_genesis_requires_stardock() (+16 more)

### Community 161 - ".state"
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 162 - "market_view"
Cohesion: 0.11
Nodes (15): AssaultCellDTO, AssaultCityDTO, AssaultExpeditionDTO, AssaultGarrisonDTO, One fog-safe cell in the live tactical-assault viewport (GW-WP12).      Terrain,, A currently visible planetary defender; unseen units never cross the seam., Public city objective status for Resolve/broadcast planning., Fog-safe, selected-actor-aware tactical assault view (GW-WP12).      The server (+7 more)

### Community 163 - "TavernDTO"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

### Community 164 - "RemoteSession"
Cohesion: 0.10
Nodes (14): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., first_focusable(), focus_content(), TabActivated, Widget, The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target)., Put keyboard focus on `node`'s primary control (see `first_focusable`).      Whe (+6 more)

### Community 165 - "EngineRoomDTO"
Cohesion: 0.20
Nodes (23): assault_map_for_state(), State-free battlefield regeneration for pure settlement/tests (G5)., AssaultGarrisonUnit, AssaultTrooper, Frozen active-operation state for ground operations (GW-WP03, GW plan §Hashed st, One deployed platoon member — hashed core state (GW-WP10).      Rides `AssaultOp, One live tactical ground defender — hashed core state (GW-WP10).      Rides `Ass, _operation() (+15 more)

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 168 - "event_visible_to"
Cohesion: 0.13
Nodes (22): Backend, DebugBackend, Protocol, Generate one schema-valid JSON grammar for an authoring prompt., Wraps any backend to echo the request/response at the backend boundary to stderr, _default_out(), IndentedDumper, _load_existing_packs() (+14 more)

### Community 169 - "Community 169"
Cohesion: 0.20
Nodes (12): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination), The Basilisk kit (gravity lance, sidewall regen, recon drone), In Fury Born combat inspiration (David Weber) (+4 more)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 171 - "station_archetypes.py"
Cohesion: 0.15
Nodes (17): get_biome_feature(), any, OpenSimplex, Random, Text, Procedural terrain generation using OpenSimplex noise.  The *gameplay* band layo, Return the feature name, and a legible fg/bg colour pair, for a noise value., Resolve a feature name to a specific character based on frequencies. (+9 more)

### Community 172 - "_SpriteCard"
Cohesion: 0.16
Nodes (21): accept(), is_convoyed(), Stamp an offered contract into an active one on the player's slate (WP57)., Whether a species instance is under escort by any player (§6.7, WP57).      A co, WP57 — favors + escort contracts (DESIGN §6.7, §14).  The contract system is pur, Sectors 1-2-3 with a fuel-ore-buying port in sector 2, player + ship in sector 1, _ship(), _sp() (+13 more)

### Community 173 - "messages_view"
Cohesion: 0.20
Nodes (21): _dropped(), A one-sector, droppable hostile world (mirrors `test_groundwar_access.py`'s, _reducer_world(), _species(), test_end_ground_turn_charges_the_configured_macro_turn_quantum(), test_end_ground_turn_rejected_when_no_turns_left(), test_extract_ground_operation_clears_a_live_assault(), test_ground_drop_then_ground_move_ground_fire_and_end_turn() (+13 more)

### Community 174 - "Community 174"
Cohesion: 0.06
Nodes (40): `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, `BotSwarm` — many bots against one authoritative game (DESIGN §14 — WP69).  The, _parse_component(), Dev/testing cheat command (NOT part of normal play).  `DevPatch` is a single, ge, Parse a "<component>:<tier>" grant key (e.g. 'accelerator:III')., Core enumerations: the canonical TW commodity trio and port classes (§4).  These, ContactSession (+32 more)

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 176 - "landing_sites"
Cohesion: 0.22
Nodes (15): CheckpointCodecError, _decode(), _encode(), encode_state(), payload_checksum(), Any, ValueError, Versioned, safe checkpoint encoding for authoritative universe state.  Checkpoin (+7 more)

### Community 177 - "LiveSysopService"
Cohesion: 0.24
Nodes (9): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), test_every_archetype_has_responsive_service_art() (+1 more)

### Community 178 - "_entity_world"
Cohesion: 0.22
Nodes (10): _check_config_version(), _load_save(), main(), ArgumentParser, Exception, Path, Rebuild a saved universe from `path`; return it with the seed it came from., A save written under a different config than the one this build would replay it (+2 more)

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

### Community 182 - ".boarded_starbase_id"
Cohesion: 0.20
Nodes (10): CodexEntry, ContractDTO, PlanetDirEntry, PortDirEntry, One logged discovery for the Computer's Codex tab (§7, §11, WP11)., One known port for the Computer's Ports tab (§11, WP15)., One charted planet for the Computer's Planets tab (§11, §4.2)., One active favor on the Computer's contracts panel (§6.7, §14 — WP57). (+2 more)

### Community 183 - "BotRunner API (on/each_turn/apply)"
Cohesion: 0.25
Nodes (9): Golden-master rail: generate(seed)+replay(command log), WP57-60 — favors/escorts, tavern, sysop console, scripting hooks, BotRunner API (on/each_turn/apply), edge-bot headless bot runner, explorer.py example bot, edge-llm-bot LLM pilot (Ollama), pair_trader.py example bot (exit balance harness), Pilot console Textual app (edge/bot/llm/tui.py) (+1 more)

### Community 204 - "Rock"
Cohesion: 0.40
Nodes (4): One cell of rocky debris (belt scenarios). Blocks fire lines and wings;     dest, Rock, Scatter rocky-debris clumps across the midfield (belt scenarios) — a     random-, seed_rocks()

## Knowledge Gaps
- **131 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script` (+126 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Config Schema Models` to `Core Rules & Events Engine`, `Community 129`, `Standing, Corp & Combat Rules`, `Aliens & Alliance Admission`, `EngineRoomDTO`, `Planet & Orbit Views`, `Disposition Bands & Ship Classes`, `MarketDTO`, `Engine-Room Component Workbench`, `Dialogue-Pack Save Guard`, `market_settlement`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Core Governance & Seizure`, `Core-Seizure Confirm Screens`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `.state`, `RemoteSession`, `EngineRoomDTO`, `Core Rules Tests`, `Community 42`, `_SpriteCard`, `Community 45`, `Community 174`, `Community 47`, `Community 48`, `Community 49`, `Community 61`, `Community 68`, `Community 69`, `Community 74`, `Community 75`, `Community 76`, `Community 77`, `Community 79`, `Community 83`, `Community 84`, `Community 85`, `Community 88`, `Community 91`, `Community 98`, `Community 106`, `Community 107`, `Community 108`, `Community 109`, `Community 111`, `Community 112`, `Community 115`, `Community 117`, `Community 118`, `test_ui_black_hole.py`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 42` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `EngineRoomDTO`, `MarketDTO`, `Community 141`, `Dialogue-Pack Save Guard`, `Game Lifecycle & Pathfinding`, `The Entity & Command Reduce`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `test_intel_contact.py`, `market_settlement`, `Market Orders & Regions`, `Config Schema Models`, `Community 147`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Core-Seizure Confirm Screens`, `Community 160`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `market_view`, `EngineRoomDTO`, `Config Loading & Sidecar Merge`, `Community 43`, `_SpriteCard`, `Community 45`, `Community 174`, `Community 49`, `_entity_world`, `Community 54`, `Community 56`, `Community 59`, `Community 61`, `Community 69`, `Community 70`, `Community 71`, `Community 73`, `Community 74`, `Community 75`, `Community 84`, `Community 85`, `Community 88`, `Community 91`, `Community 96`, `Community 98`, `Community 104`, `Community 106`, `Community 107`, `Community 112`, `Community 115`, `Community 119`, `Community 121`, `test_ui_black_hole.py`, `Community 127`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Community 69` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Community 128`, `Standing, Corp & Combat Rules`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `MarketDTO`, `Community 143`, `The Entity & Command Reduce`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `test_intel_contact.py`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `market_view`, `Core-Seizure Confirm Screens`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `market_view`, `EngineRoomDTO`, `Config Loading & Sidecar Merge`, `Core Rules Tests`, `Community 42`, `_SpriteCard`, `Community 45`, `Community 174`, `messages_view`, `landing_sites`, `Community 49`, `_entity_world`, `Community 48`, `Community 59`, `Community 61`, `Community 66`, `Community 70`, `Community 74`, `Community 75`, `Community 84`, `Community 85`, `Community 88`, `Community 96`, `Community 98`, `Community 99`, `Community 104`, `Community 106`, `Community 107`, `Community 108`, `Community 111`, `Community 112`, `Community 115`, `Community 118`, `test_ui_black_hole.py`, `Community 127`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 162 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 162 INFERRED edges - model-reasoned connections that need verification._
- **Are the 375 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 375 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._