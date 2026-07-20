# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 338 files · ~9,163,395 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8186 nodes · 35659 edges · 196 communities (170 shown, 26 thin omitted)
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 11370 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3bab7c81`
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
- Community 160
- ComputerDTO
- TavernDTO
- .apply
- Community 166
- .__init__
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
1. `UniverseState` - 521 edges
2. `GameConfig` - 475 edges
3. `Commodity` - 426 edges
4. `reduce()` - 387 edges
5. `EconomyError` - 340 edges
6. `EdgeApp` - 265 edges
7. `apply_result()` - 236 edges
8. `Warp` - 234 edges
9. `ComponentTier` - 232 edges
10. `Event` - 219 edges

## Surprising Connections (you probably didn't know these)
- `test_roster_archetypes_have_palettes()` --calls--> `available_archetypes()`  [EXTRACTED]
  tests/test_art_coverage.py → edge/art/generator.py
- `test_width_grows_monotonically_and_respects_bounds()` --calls--> `compose_horizontal()`  [EXTRACTED]
  tests/test_ship_art.py → edge/art/hull.py
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py
- `test_generation_is_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_bigbang.py → edge/bigbang/generator.py
- `test_an_alliance_gas_giant_is_generated_with_a_city()` --calls--> `generate()`  [EXTRACTED]
  tests/test_cloud_city.py → edge/bigbang/generator.py

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

## Communities (196 total, 26 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.08
Nodes (464): AmountPrompt, _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes (+456 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.05
Nodes (74): genesis_valid_target(), is_colonizable(), Whether this world is a legal Genesis target: unowned and an eligible type (§4.2, Whether a world of this type can be claimed and settled (§4.2).      Colonizable, range, enroll(), generate_with_player(), Any (+66 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.03
Nodes (48): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, SectorDiscovery, AnomalyRow, _code_markup() (+40 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.12
Nodes (36): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A knocked-out part contributes nothing until it is patched (§4.1). (+28 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.08
Nodes (33): build_graph(), Build the warp graph and return its adjacency plus the region groups., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, bfs_distances(), Forward hop distance from `src` to every reachable sector.      Accepts any int-, one_way_exits(), Targets reachable from `sector_id` with no return edge (sorted, deterministic). (+25 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.02
Nodes (230): Adjacency, _discoveries(), format_route(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers)., Resolve two endpoints (internal or spatial id) and plot the fewest-hop route., The spatial display id for an internal sector id, or `—` if none is cached. (+222 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.18
Nodes (19): _finalize_planets(), _host_markets(), _make_port(), _mid_stock(), _normalize_belts(), _place_starbases(), populate(), Random (+11 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.18
Nodes (24): build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., _phantom_bridges(), Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic., Pairs of *non-adjacent* sectors joined on one row by an unbroken, arm-connected, A graph can fit horizontally while exploding vertically; fitting bounds both axe, A small branching universe:  1 - 2 - 3 - 4  with a 2 - 5 - 6 spur.      Core hop, _rows() (+16 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.10
Nodes (48): derive_aspects(), Compute the derived scalars for `ship` from its subsystems (§4.1).      A hull w, EncounterFoe, One hostile ship of an encounter pack (DESIGN §10, WP24).      Stats are resolve, _engagement(), _fight_state(), _foe(), _forced_knockout_config() (+40 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.06
Nodes (49): Cell, A surface-exploration site on a descended planet (UI_MOCKUPS.md §4, §7).      `s, The descended-planet view: terrain + the planet's surface sites (§7, WP6)., SurfaceDTO, SurfaceSite, blurb_for(), _carve_lakes(), _carve_rivers() (+41 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.03
Nodes (78): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, ContextStrip, The docked one-line screen header: bold title, optional muted context., A muted one-to-few-line strip for status/legend copy under the body., TitleBar, The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar (+70 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.06
Nodes (43): One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).      `s, One subsystem panel: its derived aspect and its slot grid (§4.1)., Slot, Subsystem, EmptyState, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches')., A consistent 'nothing here' block: what is empty and what fills it., _BayPanel (+35 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.16
Nodes (15): expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar, Every authored expansion string in a grammar (for placeholder validation)., _entry_strings(), Every authored template string in an entry (variant pool + grammar expansions)., _grammar_pack() (+7 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.06
Nodes (24): AmountPrompt, FieldPrompt, Any, ComposeResult, Pressed, Static, Submitted, The shared one-field prompt: inline validation, no silent failures.      Subclas (+16 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.04
Nodes (55): TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Host the app in a browser via `textual-serve` (DESIGN §11, §15; WP68 remote)., _serve(), notify_error(), next_hint() (+47 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.09
Nodes (24): AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed, Shared exact-amount field with −/+ stepping for logistics and recruitment., An integer input followed by decrement/increment buttons., Clamp an over-cap typed value back to `maximum` in place, so the field can (+16 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.04
Nodes (49): generate(), Generate a validated universe from `(seed, config)`; raise on repeated failure., The §13 gradient: aggregated over many seeds at full scale, mean disposition per, A drawn species is met as a *cluster* of ships near its home, not a lone contact, The Core is busy with governing-alliance traffic — several ships, all governor's, The species sub-RNG must not shift the Phase-1 port/planet draws (golden-master), ≥1 governing-alliance member is settled in the Core; no rival/unaligned is (WP18, The Entity is always drawn, exactly once, with no satellites, and never in the C (+41 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.07
Nodes (77): instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting(), _cfg_with_oath(), _cfg_with_repeat_greeting() (+69 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.19
Nodes (8): _haggle_highlighted(), _highlighted_line(), Any, Screen, The (TradePanel, highlighted CommodityLine, port) trio, or (None, None, None)., Shared trade handler: buy/sell a clamped chunk of the highlighted row., Open a counter-offer haggle on the highlighted row (§8); commit on submit., _trade_highlighted()

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.04
Nodes (134): validate(), build_layouts(), Instantiate intact subsystems from a layout mapping (§4.1).      Base components, Game, Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe, A fixed-length slot tuple for one subsystem (DESIGN §4.1).      `slots[i]` is th, Filled, non-knocked-out components (the ones the aspect formula counts). (+126 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.07
Nodes (30): _amain(), _build_game(), _error(), GameServer, LobbyServer, Any, Command, Event (+22 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.03
Nodes (88): ActiveBinding, EdgeScreen, notify_success(), Shared shell chrome and feedback (UI_UX_OVERHAUL_PLAN.md WP-UI05/WP-UI07).  One, The base every full screen uses: its footer always leads with **Back**.      Tex, ActionDescriptor, LayoutTier, Enum (+80 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.02
Nodes (124): BaseModel, HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open- (+116 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.05
Nodes (71): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+63 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.10
Nodes (23): flip_row(), Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Slot, The authored row-height of a ship grammar tier (all parts share it)., Pick the tallest tier whose authored height fits ``height``; falls back to     t, _select_grammar(), _tier_height(), _all_glyphs() (+15 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.08
Nodes (44): Merge a generated dialogue sidecar onto the default roster and run §13 integrity, validate_sidecar(), _default_out(), IndentedDumper, _load_existing_packs(), main(), _prompt_yn(), Any (+36 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.10
Nodes (43): Alliance, An alliance / rival bloc (DESIGN §4/§6.3).      No alliance is privileged in the, governance_tick(), NPC Core seizures + leadership intrigue on the daily clock (§6.3, WP51).      A, _as_result(), _base(), _champion(), _gov_config() (+35 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.06
Nodes (80): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), dialogue_fingerprint(), A 16-hex-char hash of the choice-cardinality structure across all species packs., Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, Path, SqliteRepository (+72 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.15
Nodes (29): DevPatchError, Exception, A malformed or impossible dev patch (unknown target, missing entity, bad key)., _apply(), _config(), Path, DevPatch dev/testing command — reducer behaviour + replay determinism.  Proves t, The golden-master rail: a DevPatch replays to an identical state hash. (+21 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.09
Nodes (22): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., _citadel_stage(), _depletion(), PlanetScreen — orbit view, wired to the live service (UI_MOCKUPS.md §3, §4.2)., The 0..1 fraction of a belt's ore already mined out (0.0 for any other world, PT, The planet screen's stores + citadel blocks are widget panels: a stores     Data, test_planet_citadel_panel_builds_via_button() (+14 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.05
Nodes (37): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+29 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.12
Nodes (49): Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), A remote rules rejection compatible with every local rule-error catch.      JSON, RemoteError, RemoteRulesError, Exception, One connected client: the socket, the authenticated account, and the seat it hol, A JSON-RPC error to return to the caller (code + message). (+41 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.05
Nodes (88): DrawFn, EconomyConfig, The pricing inputs for one commodity., The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., apply_dev_patch(), _clamp_ship_field(), _expire_contract() (+80 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.07
Nodes (45): apply_patch(), apply_patch_lines(), build_parser(), _build_patch(), cmd_governance(), cmd_list(), cmd_show(), _components() (+37 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (58): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+50 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.07
Nodes (26): BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Pressed, Submitted, Start or stop the pilot according to the control's current state. (+18 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.06
Nodes (55): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., load_config() (+47 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.11
Nodes (24): _at_base(), _footer_keys(), PT-32 — the Starbase's keyboard model: a tab owns its keys.  The third and last, Regression: `P` on a derelict base used to crash the TUI.      A base *is* the p, A verb the base cannot honour is not a key at all — the same rule that withholds, Station carries the Status panel, which every base owes you — a hostile base sho, A fresh universe's base is not yours, so at least one service is gated shut — an, Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+16 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.16
Nodes (21): _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk(), generate_find_art(), _pit() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.03
Nodes (240): GameConfig, Top-level config bundle, validated from the parsed YAML mapping., §4/§10 reference integrity: every hull's `armament` ids resolve in the         `, player_corp(), The corporation a player belongs to, or None (§4, WP66)., deposit(), EconomyError, Exception (+232 more)

### Community 43 - "Community 43"
Cohesion: 0.07
Nodes (27): BotSetup, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, BotRunner, Command, Event, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69). (+19 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (26): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+18 more)

### Community 45 - "Community 45"
Cohesion: 0.05
Nodes (43): ABC, BaseException, CronResolver, DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12)., The save was made with a different dialogue pack; replay would fail mid-way., EngineState (+35 more)

### Community 46 - "Community 46"
Cohesion: 0.02
Nodes (117): _derive_tag(), A short uppercase tag from the corp name — internal id, never typed (WP80+)., HaggleScreen, ComposeResult, Submitted, Pressed, RowHighlighted, Submitted (+109 more)

### Community 47 - "Community 47"
Cohesion: 0.03
Nodes (70): ContactChoiceDTO, ContactDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), A peaceful alien contact screen (§6, §6.7, §11)., PlaytestApp, PlaytestControls, Click, Dialogue play-test harness (dev-only — DESIGN §6.7, §13).  Reads the authored di (+62 more)

### Community 48 - "Community 48"
Cohesion: 0.05
Nodes (82): DataObject, _best_roundtrip_margin(), Best per-unit profit buying a commodity from `sell_port` and selling to `buy_por, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction() (+74 more)

### Community 49 - "Community 49"
Cohesion: 0.04
Nodes (100): cloud_city_art(), The floating-city structure for a city of `size`, shrunk to fit `width`×`height`, has_gun(), Whether `planet` fields an operational citadel gun (§4.2, WP54/WP55)., Whether the L3 siege shield bars invasion of `planet` (§4.2, WP55).      True wh, siege_shielded(), Planet, A planet (DESIGN §4.2): a typed, ownable, producing world.      `planet_type` fi (+92 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (41): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+33 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.03
Nodes (111): EdgeApp, Any, Resize, Screen, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)., Persist local-only presentation settings and apply the theme immediately. (+103 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (34): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+26 more)

### Community 54 - "Community 54"
Cohesion: 0.09
Nodes (9): main(), PlaytestService, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable., `edge-playtest-dialogue` entry point — open the dialogue playtest TUI. (+1 more)

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (23): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothi (+15 more)

### Community 56 - "Community 56"
Cohesion: 0.04
Nodes (44): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+36 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (56): compose_horizontal(), HullStyle, Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Palette for a hull: three shading levels, the navigation-beacon hue pools     (a, Resolve an ``archetype_id`` to its palette, falling back to Federation grey. (+48 more)

### Community 58 - "Community 58"
Cohesion: 0.07
Nodes (35): Procedural ASCII art generation logic., _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+27 more)

### Community 59 - "Community 59"
Cohesion: 0.08
Nodes (18): One sensor contact, masked until excavation settles the real discovery (G6/G7)., SurveyContactDTO, GroundExpeditionScreen, Any, Click, ComposeResult, Key, Static (+10 more)

### Community 60 - "Community 60"
Cohesion: 0.05
Nodes (37): _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl, The same actionable Stardock service projections the regular client receives. (+29 more)

### Community 61 - "Community 61"
Cohesion: 0.05
Nodes (23): Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Owns the loop thread + connected client; `service` is the sync facade., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade, Any, Command, Event (+15 more)

### Community 62 - "Community 62"
Cohesion: 0.10
Nodes (13): ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key, Text, Widget (+5 more)

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (25): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc, Groundwar POC config — a thin adapter over the production schema (GW-WP02).  Bal (+17 more)

### Community 64 - "Community 64"
Cohesion: 0.12
Nodes (43): GarrisonUnit, Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed() (+35 more)

### Community 65 - "Community 65"
Cohesion: 0.06
Nodes (49): DialoguePack, disposition_band(), Name the band a disposition value falls in (hostile / neutral / friendly, §6)., The player's progress toward championing a bloc into the Core (§6.3, WP50)., SeizureProgress, AliensConfig, AllianceConfig, A Core-seizure ladder is meaningful only on a `covets_core` bloc (§6.3, WP50). (+41 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (16): FormField, InterventionForm, Any, ComposeResult, DataTable, HeaderSelected, OptionSelected, Pressed (+8 more)

### Community 67 - "Community 67"
Cohesion: 0.11
Nodes (8): PlanetScreen, Pressed, Build or grow the Cloud City on a gas giant (§4.2, PT-54)., Land a chosen number of carried fighters in a ground assault (§4.2, WP55)., Open the unified base view — all starbase ops live there (§4.2, WP80)., Deploy a Genesis torpedo to terraform this world (§4.2, WP10)., Open the unified transfer editor: haul goods and settle colonists (WP-PR07)., Hand-mine an asteroid belt, taking raw goods aboard (§4.2, PT-30).

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.17
Nodes (12): _Coord, MeshTopology, Mesh topology builder (DESIGN §5)., Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it in, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who (+4 more)

### Community 70 - "Community 70"
Cohesion: 0.16
Nodes (32): _force(), _make_hostile(), _mini_state(), WP41 — sector fighters, mines, beacons, black-hole hazards (§10).  Covers the pu, A lethal hazard routes through the WP26 escape pod (WP75 — the A5 seam closed)., Armid is the WP41 mine renamed — same entry damage, spent on detonation., _species(), test_alien_drift_destroys_hostile_npc_in_a_minefield() (+24 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (36): Color, available_subtypes(), Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, planet_subtype(), port_subtype(), Style, Text, Bridge between the game's typed DTOs and the standalone `edge.art` engine.  `edg (+28 more)

### Community 72 - "Community 72"
Cohesion: 0.07
Nodes (30): AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json(), get_backend(), OllamaBackend (+22 more)

### Community 73 - "Community 73"
Cohesion: 0.08
Nodes (28): _cluster_groups(), OutEdges, Wire one group: a random spanning tree, then edges toward avg degree ~2.5., `expansive` bridging (§5 step 2): a band-lattice web with no chokepoints., Wire one group internally as a planar outer-planar graph with zero crossings., `planar` bridging: connects clusters using a planar spiderweb meta-graph., Dense concentric rings numbered outward from sector 1.      Sector 1 has ``max_w, Partition sequential IDs into rings of size ``cap * radius``. (+20 more)

### Community 74 - "Community 74"
Cohesion: 0.11
Nodes (10): Text, What an art panel drew last time, so a rebuilt screen doesn't blink (PT-42).  Se, The art this panel drew last time, or None if it has never been drawn., Record `art` as this panel's latest render and hand it back for painting., remember(), remembered(), Resize, Rich `Text` is mutable and callers `stylize()` it (a derelict base dims its icon (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.03
Nodes (57): EngineRoomPreviewDTO, Presentation-only before/after aspects for one prospective install or swap (WP-U, CronTask, EngineTicker, The engine tick loop (DESIGN §9).  A short tick advances a logical tick counter, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., Advance one tick, run any now-due crons, and persist the schedule. (+49 more)

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
Cohesion: 0.09
Nodes (25): ComposeResult, Pressed, Submitted, Enter in a row's amount field submits that row in the colony-supply direction, A modal transfer editor for the player-owned world in the current sector., TransferWorkbenchScreen, _has_scrollable_ancestor(), _new_game() (+17 more)

### Community 80 - "Community 80"
Cohesion: 0.10
Nodes (25): DeployShip, main(), _make_starfield(), Battle, `edge-spacebattle` — the space-battle POC's Textual shell.  Throwaway UI (the `t, A static char-level starfield backdrop with dim placement-grid ticks., One fleet slot during deployment — a hull awaiting a cell and a facing., SpacebattleApp (+17 more)

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (32): alien_dialogue_default.yaml (dialogue corpus), alien_dialogue_species.yaml (species grammars), alien_roster_default.yaml (species roster), default.yaml (game constants), Alien species disposition system, Alliances (rival blocs, join one at a time), Asteroid belt mining (finite reserves), Universe generation (Big Bang) (+24 more)

### Community 82 - "Community 82"
Cohesion: 0.08
Nodes (45): MapNodeDTO, A clickable sector node on the local map: its label's cell box in `rows`.      `, _decode_any(), Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, _encode_any(), Wire-encode any service return value (events, DTOs, primitives, and lists thereo, decode_command(), decode_dto() (+37 more)

### Community 83 - "Community 83"
Cohesion: 0.19
Nodes (18): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), main(), _parse_args() (+10 more)

### Community 84 - "Community 84"
Cohesion: 0.06
Nodes (45): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random, Ship (+37 more)

### Community 85 - "Community 85"
Cohesion: 0.07
Nodes (48): attitude_locked(), Whether a permanent grudge locks the attitude offset for good (§6.5).      A `ne, ContractsConfig, Favors + escort contracts issued through the dialogue system (DESIGN §6.7, §14 —, active(), advance_convoy(), apply_reward(), by_id() (+40 more)

### Community 86 - "Community 86"
Cohesion: 0.08
Nodes (36): Create the reserved hidden Legendary codex row for the Entity (DESIGN §7, WP35)., _reserve_entity_codex(), Render a generated universe to an interactive web page (DESIGN §5).  A dev-only, build_subsystems(), Instantiate a hull's starting subsystems from its config layout (§4.1).      Ret, AssaultOperation, Frozen active-operation state for ground operations (GW-WP03, GW plan §Hashed st, A live tactical assault (GW plan D7-D11) — hashed core state.      Set on `Playe (+28 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (26): Brain, One pilot: owns the model client, the action catalog, and the paced loop., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end., Answer queued general questions without executing or budgeting an action., Separate queued queries from persistent objective changes. (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.14
Nodes (24): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+16 more)

### Community 89 - "Community 89"
Cohesion: 0.14
Nodes (13): ClusteredTopology, PlanarTopology, Random, Trunk topology builder (DESIGN §5)., `trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra, Planar topology builder (DESIGN §5)., Base class for all topology builders (DESIGN §5)., Build the topology and return the region groups (the Core is group 0). (+5 more)

### Community 90 - "Community 90"
Cohesion: 0.11
Nodes (31): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+23 more)

### Community 91 - "Community 91"
Cohesion: 0.07
Nodes (17): One traversed sector on a plotted route — what the player reads (§11, WP14)., RouteHopDTO, notify_warning(), Summarize the authoritative plotted DTO without duplicating route rules., Petition to flip the Core to the championed bloc (§6.3, WP50)., EngineRoomScreen, Slot, Render a reducer-validated aspect preview for exactly one selected target. (+9 more)

### Community 92 - "Community 92"
Cohesion: 0.03
Nodes (106): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+98 more)

### Community 93 - "Community 93"
Cohesion: 0.22
Nodes (18): list_portraits(), portraits_dir(), Path, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait() (+10 more)

### Community 94 - "Community 94"
Cohesion: 0.14
Nodes (23): CronFn, BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total(), Total latinum across every store — the numeric H10 conservation invariant (WP69), The pure reducer for a persisted cron name (raises on an unknown name)., resolve_cron() (+15 more)

### Community 95 - "Community 95"
Cohesion: 0.02
Nodes (59): AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state)., The DTO under the highlighted row of `table_id`, or None.          WP-UI21: reso (+51 more)

### Community 96 - "Community 96"
Cohesion: 0.08
Nodes (56): _build_site(), _cell_cost(), dig_trench(), _dist(), generate_survey(), _in_bounds(), _keepout(), _landing() (+48 more)

### Community 97 - "Community 97"
Cohesion: 0.08
Nodes (16): Any, Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., BridgedGameClient, Any, Sync bridge: drive an async `RemoteClient` from the synchronous TUI (WP68).  Mos, A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68). (+8 more)

### Community 98 - "Community 98"
Cohesion: 0.07
Nodes (72): _bfs_from(), _pick_by_distance(), plan_move(), _player_sectors(), _port_sectors(), Random, Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42)., Hop distance from the nearest `sources` node to every reachable sector (BFS). (+64 more)

### Community 99 - "Community 99"
Cohesion: 0.05
Nodes (43): Binding, Shown while the terminal is below the 80×24 floor (WP-UI05).      It never traps, SizeNoticeScreen, Any, Screen, Return the one canonical advertised-action list for a screen.      Danger levels, screen_actions(), ActionMenuScreen (+35 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.11
Nodes (11): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., TabActivated, Shared responsive service navigation for Stardock and orbital bases.      Standa, Switch to `entry_id` and focus its primary content (tab accelerator target)., Drop focus before a programmatic tab switch (see the class docstring)., Never strand focus in a tab that is no longer showing — its keys would stay, Enter on the tab rail drops focus onto the active tab's primary content. (+3 more)

### Community 103 - "Community 103"
Cohesion: 0.16
Nodes (24): A friendly settlement visible on the projected survey map.      ``plaza_x``/``pl, SurveySettlementDTO, ground_operation_view(), Project the player's active survey without exposing its generation identity (GW-, _inhabited_view(), MonkeyPatch, Path, GW-WP07 — fog-safe expedition DTO, client parity, and live Textual flow. (+16 more)

### Community 104 - "Community 104"
Cohesion: 0.14
Nodes (16): can_warp(), Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers, The sectors reachable in one hop from `sector_id`., Whether a single direct warp `from_sector -> to_sector` is legal., One traversed sector on a planned route (excludes the origin)., RouteHop, warp_targets(), WP3 — movement helpers: warp legality and pathfinding (DESIGN §9).  WP14 extends (+8 more)

### Community 105 - "Community 105"
Cohesion: 0.10
Nodes (36): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, WarpDTO, build_nav_strip(), _nearest_free(), _octant(), The main-screen nav rose — a bearing-placed compass of immediate warps (§11).  B (+28 more)

### Community 106 - "Community 106"
Cohesion: 0.19
Nodes (15): _build_at_radius(), _codes(), _draw_edges(), _label(), _layout_map_nodes(), _local_bfs(), _pointer_line(), Local sector ego-graph layout for the Computer → Map tab (§10, §11). Pure.  Lays (+7 more)

### Community 107 - "Community 107"
Cohesion: 0.22
Nodes (9): ComposeResult, Static, Vertical, Keep identity, ownership, habitability, and colony state together., The classifier's one truthful orbit route: survey, assault, or orbital-only., A belt's orbital readout (§4.2, WP-PR06): a spatial feature, scanned/mined, not, A gas giant's Cloud City: what floats there, and what building more would cost., Colony stores vs. the ship's hold, tabular, with haul buttons (§4.2). (+1 more)

### Community 108 - "Community 108"
Cohesion: 0.10
Nodes (48): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., combat_contexts(), DialogueIntegrityError, _is_catch_all(), _placeholders_in() (+40 more)

### Community 109 - "Community 109"
Cohesion: 0.20
Nodes (5): LocalMapDTO, The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map(), Bake the local map to fit `width`, overlaying the active route (§6.7/§11).

### Community 110 - "Community 110"
Cohesion: 0.06
Nodes (29): layout_tier(), ComposeResult, Any, ComposeResult, DataTable, Horizontal, Static, Rumors, the bounty board, and the noticeboard (§14, WP58). (+21 more)

### Community 111 - "Community 111"
Cohesion: 0.11
Nodes (37): entity_species(), The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None., LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered() (+29 more)

### Community 112 - "Community 112"
Cohesion: 0.12
Nodes (12): _bindings(), EncounterDTO, SimpleNamespace, A live encounter that records the commands the screen applies (and never resolve, action name → the key bound to it., The button→action map and the binding table cover exactly the same actions., The `[F]` in a label is the key that fires it — a rename cannot leave the label, Keyboard and mouse are one path: `f` and the FIRE button both apply the same act (+4 more)

### Community 113 - "Community 113"
Cohesion: 0.08
Nodes (43): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, author_line(), AuthoringError, AuthoringRequest, build_prompt(), output_schema() (+35 more)

### Community 114 - "Community 114"
Cohesion: 0.06
Nodes (64): MarketSettled, The daily order-book settlement summary (§8, WP47).      One aggregate emitted p, A ship hull (DESIGN §4).      A player hull carries `subsystems` (the engine-roo, Holds occupied — trade cargo plus loose (uninstalled) components.          Loose, A named cluster from generation (DESIGN §4/§5)., Region, Ship, engine_room_view() (+56 more)

### Community 115 - "Community 115"
Cohesion: 0.33
Nodes (5): LiveSysopService, Any, Event, Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC., Apply an intervention to the authoritative live game as the target player.

### Community 116 - "Community 116"
Cohesion: 0.13
Nodes (15): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError (+7 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.06
Nodes (81): apply_result(), Command, Upsert a reducer's new entities into the mutable container (sanctioned)., Validate `command` for `player_id` and return its delta + events., reduce(), Command, Validate, persist, and apply a command; return the events it produced., §6.5: a finite grudge cools by the holder's gain rate per day and lapses; a (+73 more)

### Community 119 - "Community 119"
Cohesion: 0.17
Nodes (16): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), list_items(), Render one category of populated universe items as an id-keyed table., main(), CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--stats] [--render DIR]`., build_payload(), _classify_edges() (+8 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.02
Nodes (174): admission_met(), admission_tasks_done(), _alliance_key(), alliance_rivals(), alliance_standing(), alliance_standing_shift(), apply_join_standing(), apply_resign_standing() (+166 more)

### Community 122 - "Community 122"
Cohesion: 0.10
Nodes (11): Container, has_save(), Whether a resumable save exists (drives the menu's Continue affordance)., MainMenuScreen, ComposeResult, Pressed, OptionsScreen, ComposeResult (+3 more)

### Community 123 - "Community 123"
Cohesion: 0.17
Nodes (17): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.16
Nodes (20): concourse_asset(), Path, Text, Static Stardock service raster selection and ANSI rendering.  The source artwork, Return the tab, theme, and layout-specific crop., Render a responsive service panel: 72×12 wide, 56×8 standard., Compatibility wrapper for the original PT-06 asset tests., Compatibility wrapper for the original PT-06 renderer. (+12 more)

### Community 125 - "Community 125"
Cohesion: 0.16
Nodes (12): fractal_noise(), OpenSimplex, Shared procedural-noise helpers for the art generators., Sum several octaves of noise so clusters break up at multiple scales.      Layer, Random, Text, Procedural starfield generation., Per-subtype knobs turning the noise field into stars.      threshold  - noise cu (+4 more)

### Community 126 - "test_ui_black_hole.py"
Cohesion: 0.24
Nodes (16): _disc(), _planet_with_hidden_and_obvious(), GW-WP05 — survey generation from real universe discoveries (GW plan §GW-M2).  Tw, _survey(), test_already_collected_site_marked_found(), test_already_detected_site_is_visible_regardless_of_sensor(), test_eligibility_is_sensor_monotone_and_non_leaking(), test_every_surface_find_is_artifact_plus_lore() (+8 more)

### Community 127 - "Community 127"
Cohesion: 0.09
Nodes (28): `fg` unchanged if it reads against `bg`, else a hue-preserving variant     (ligh, readable_fg(), GroundCellDTO, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, FindKind, Random, Shared archaeological find identities promoted from the groundwar POC.  The prod, Draw one POC-style archaeological proper name. (+20 more)

### Community 128 - "Community 128"
Cohesion: 0.07
Nodes (49): advance_build(), building(), citadel_defense_mult(), citadel_foe(), CitadelError, conquer(), InvasionOutcome, level_config() (+41 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.21
Nodes (12): Ship, Service-point resolution — where a ship may repair, buy, and bank (§4.1, §4.2, W, The provider serving a ship's current sector (§4.2, WP53).      `kind` is ``"sta, The service provider for the ship's current sector, or None (§4.1/§4.2, WP53)., The service point offering `service` here, or raise (the reducer gate, WP53)., require_service(), service_point(), ServicePoint (+4 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.19
Nodes (4): AmountPrompt, ComposeResult, Pressed, Enter *in the amount field* commits: typing a number and pressing Enter is inten

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "EngineRoomDTO"
Cohesion: 0.31
Nodes (12): _drop_entity(), _inject(), _knows_a_far_discovery(), Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7), Log-coordinates is a reply on the offer_coordinates node, not the greeting — you, Remove the roaming Entity so a test can isolate the regular coordinate-tip mecha, Point the species' knowledge at a real, reachable, unexplored rare+ discovery., test_accept_lead_without_a_tip_is_rejected() (+4 more)

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 138 - "main"
Cohesion: 0.40
Nodes (3): Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, SurveyExpeditionDTO, The active survey's fog-safe viewport, or ``None`` while in orbit (GW-WP07).

### Community 139 - "MarketDTO"
Cohesion: 0.50
Nodes (4): describe_payload(), A short human-readable phrase for what collecting a payload yields (§7).      On, Log the Entity's reserved codex row on first contact (§7, WP35), folding it into, _stamp_entity_codex()

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.03
Nodes (31): CorpDTO, HaggleQuote, LeadDTO, MarketDTO, MessagesDTO, PortDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, A read-only read on a counter-offer before the player commits it (§8).      `fai (+23 more)

### Community 142 - "TopologyModeConfig"
Cohesion: 0.18
Nodes (15): _noncore(), Path, WP70 — player-initiated first-strike combat (docs/SEAMS_PLAN.md §5; DESIGN §10)., The projection greys FIGHT with the very string the reducer raises (lockstep)., Inject `roster_id` and move it + the player's ship to a shared non-Core sector., _stage(), test_attack_blocked_in_the_core_sanctuary(), test_attack_on_a_noncombatant_is_pointless() (+7 more)

### Community 143 - "Community 143"
Cohesion: 0.06
Nodes (21): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, HelpScreen, main(), Battle, Pressed (+13 more)

### Community 144 - "trader_step"
Cohesion: 0.50
Nodes (4): _quill_state(), A fresh game plus one hand-placed quill kind in the player's sector., WP27 arithmetic through the combat reducer: a kill sours the species, forms a, test_kill_consequences_alignment_experience_and_grudge_event()

### Community 145 - "test_genesis.py"
Cohesion: 0.11
Nodes (22): bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns ``, BFS from ``root`` over out-edges → (visit order, parent, children, depth)., Leaf count per subtree (leaves weigh 1), for proportional wedge sizing.      Pro (+14 more)

### Community 146 - "test_intel_contact.py"
Cohesion: 0.20
Nodes (7): Re-render the trade panel from fresh state after a trade/haggle., _refresh(), DataTable, RowHighlighted, The commodities trade UI: a live pricing table over the docked port.      Reusab, Rebuild responsive columns while preserving the logical commodity selection., TradePanel

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
Cohesion: 0.29
Nodes (14): accept(), Stamp an offered contract into an active one on the player's slate (WP57)., WP57 — favors + escort contracts (DESIGN §6.7, §14).  The contract system is pur, Sectors 1-2-3 with a fuel-ore-buying port in sector 2, player + ship in sector 1, _ship(), _sp(), test_abandon_fails_contract(), test_deadline_expiry_on_daily_cron() (+6 more)

### Community 158 - "StaticGenerator"
Cohesion: 0.31
Nodes (6): Random, Text, Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.  Un, Generates a frame of random low-contrast static ("snow")., Fill a `width` × `height` frame with weighted random noise glyphs.          `sub, StaticGenerator

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 162 - "ComputerDTO"
Cohesion: 0.04
Nodes (78): ArmamentItem, Aspect, BountyDTO, CommodityLine, ComputerDTO, CorpMemberDTO, DeploymentOptionDTO, DossierEntry (+70 more)

### Community 163 - "TavernDTO"
Cohesion: 0.09
Nodes (23): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), _archetype() (+15 more)

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 167 - ".__init__"
Cohesion: 0.67
Nodes (3): nebular_bloom(), Text, A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35).

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 172 - "_SpriteCard"
Cohesion: 0.25
Nodes (6): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, TabPane

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
- **53 isolated node(s):** `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script`, `graphify`, `Workflow: graphify` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Community 128`, `Community 129`, `Screens, DTOs & Remote Play`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Planet & Orbit Views`, `Community 141`, `Dialogue-Pack Save Guard`, `Community 143`, `test_intel_contact.py`, `Subsystem Layouts & Ownership`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Community 154`, `Bigbang Aliens & Region Control`, `market_view`, `Dev Patch Tooling`, `Core Governance & Seizure`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `TavernDTO`, `Core Rules Tests`, `Community 42`, `Community 45`, `Community 46`, `Community 48`, `Community 49`, `Community 61`, `Community 65`, `Community 68`, `Community 69`, `Community 73`, `Community 75`, `Community 76`, `Community 79`, `Community 83`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 89`, `Community 92`, `Community 94`, `Community 95`, `Community 98`, `Community 102`, `Community 108`, `Community 111`, `Community 114`, `Community 117`, `Community 118`, `Community 121`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 42` to `Community 128`, `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Community 130`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Planet & Orbit Views`, `MarketDTO`, `Community 141`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `Subsystem Layouts & Ownership`, `Community 147`, `Config Schema Models`, `Community 154`, `market_view`, `Bigbang Aliens & Region Control`, `Dev Patch Tooling`, `Core Governance & Seizure`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `TavernDTO`, `Config Loading & Sidecar Merge`, `Community 43`, `Community 45`, `Community 47`, `Community 48`, `Community 49`, `Community 54`, `Community 61`, `Community 65`, `Community 69`, `Community 71`, `Community 73`, `Community 75`, `Community 77`, `Community 84`, `Community 85`, `Community 86`, `Community 89`, `Community 92`, `Community 96`, `Community 98`, `Community 103`, `Community 111`, `Community 114`, `Community 118`, `Community 119`, `Community 121`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Aliens & Alliance Admission` to `Core Rules & Events Engine`, `Community 128`, `Community 130`, `Sector Scene & Widgets`, `Standing, Corp & Combat Rules`, `Computer Screen & Alliances Tab`, `Disposition Bands & Ship Classes`, `EngineRoomDTO`, `MarketDTO`, `Community 141`, `TopologyModeConfig`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `Subsystem Layouts & Ownership`, `Config Schema Models`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `market_view`, `Dev Patch Tooling`, `Market Economy & Pricing`, `TavernDTO`, `Devtool CLI & Sysop`, `Core Rules Tests`, `Community 42`, `Community 45`, `Community 47`, `Community 48`, `Community 49`, `Community 61`, `Community 65`, `Community 70`, `Community 75`, `Community 77`, `Community 85`, `Community 86`, `Community 92`, `Community 94`, `Community 96`, `Community 98`, `Community 103`, `Community 106`, `Community 108`, `Community 111`, `Community 114`, `Community 118`, `Community 119`, `Community 121`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 132 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 337 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 337 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._