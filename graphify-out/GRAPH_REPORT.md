# Graph Report - edge-of-the-unknown  (2026-07-19)

## Corpus Check
- 338 files · ~9,167,547 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8242 nodes · 36025 edges · 217 communities (189 shown, 28 thin omitted)
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 11582 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bca19cb8`
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
- .rebuild_adjacency
- Community 160
- .state
- ComputerDTO
- TavernDTO
- test_sig_corpus.py
- .apply
- Community 166
- InterventionForm
- test_ui_sector_view.py
- Community 169
- Community 170
- _line_state
- _SpriteCard
- HaggleScreen
- Community 174
- Community 175
- landing_sites
- LiveSysopService
- _entity_world
- Community 179
- Community 180
- Community 181
- StardockDTO
- terrain.py
- _feature_glyph
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
- .active_bands
- SurveySettlement
- attack_forbidden
- test_ticked_trading_reproduces_to_an_identical_hash
- graphify.js
- graphify.md
- graphify.md
- __init__.py
- _apply
- .__init__
- .component_price
- .pricing
- .total

## God Nodes (most connected - your core abstractions)
1. `UniverseState` - 525 edges
2. `GameConfig` - 480 edges
3. `Commodity` - 428 edges
4. `reduce()` - 391 edges
5. `EconomyError` - 342 edges
6. `EdgeApp` - 265 edges
7. `apply_result()` - 238 edges
8. `Warp` - 235 edges
9. `ComponentTier` - 233 edges
10. `Event` - 221 edges

## Surprising Connections (you probably didn't know these)
- `test_archetype_icons_are_distinct_procedural_cell_art()` --calls--> `generate_sprite()`  [EXTRACTED]
  tests/test_station_archetype_art.py → edge/art/generator.py
- `test_width_grows_monotonically_and_respects_bounds()` --calls--> `compose_horizontal()`  [EXTRACTED]
  tests/test_ship_art.py → edge/art/hull.py
- `test_every_live_band_has_a_contact()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_placement_is_seeded_and_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_roster_alliances_become_entities()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py

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

## Communities (217 total, 28 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.09
Nodes (461): AmountPrompt, _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes (+453 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.07
Nodes (27): generate_with_player(), Any, `generate()` then `enroll()` — the common "fresh game with player 1" setup., _quill_state(), A fresh game plus one hand-placed quill kind in the player's sector., test_no_roster_falls_back_to_federation_stub(), The path from the start sector to Stardock opens pre-explored (round-2).      On, test_stardock_route_starts_explored() (+19 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.03
Nodes (76): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., SceneArtConfig, One discovery visible in the current sector (§7, WP5).      Obvious phenomena an, A planet present in the current sector (§4.2).      Carries the `planet_type` ke, A vessel present in the current sector (§6, §14).      `role` is the art ship ro, The roaming Entity's always-on in-sector presence hint (DESIGN §7, WP35).      F, An orbital starbase's presence in the sector view (§4.2 — scene sprite + caption, SectorAnomalyDTO (+68 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.13
Nodes (32): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, A knocked-out part contributes nothing until it is patched (§4.1)., A `subsystems=None` (NPC-style) hull has no engine room to operate on. (+24 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.05
Nodes (24): Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)., ListPicker, ComposeResult, `options` are (markup label, ref) rows; the ref comes back on dismiss., _DeployRow, ComposeResult, Horizontal, Pressed (+16 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.03
Nodes (81): alliance_rivals(), Public: the blocs at odds with `alliance_id` (symmetric rivalry, §6.3).      Thi, describe_payload(), A short human-readable phrase for what collecting a payload yields (§7).      On, ArmamentItem, CorpMemberDTO, DeploymentOptionDTO, HardwareItem (+73 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.08
Nodes (47): Game, Top-level game record (DESIGN §4)., A fresh universe seeded from the game's seed (RNG owned here, §3)., build_local_map(), Bake the local ego-graph rows (and legend) centered on the player's sector., test_check_relations_rejects_mutual_intra_bloc_enmity(), test_npc_stance_subtracts_active_grudge(), _bare_state() (+39 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.06
Nodes (68): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), player_foe(), Random, Ship, Subsystem (+60 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.05
Nodes (50): Cell, Container, A surface-exploration site on a descended planet (UI_MOCKUPS.md §4, §7).      `s, SurfaceSite, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm() (+42 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.03
Nodes (72): Exception, A JSON-RPC error returned by the server (a rules rejection or a transport fault), RemoteError, The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_engine_room() (+64 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.06
Nodes (42): One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).      `s, One subsystem panel: its derived aspect and its slot grid (§4.1)., Slot, Subsystem, EmptyState, Any, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches')., A consistent 'nothing here' block: what is empty and what fills it. (+34 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.09
Nodes (36): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar (+28 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.05
Nodes (39): AmountPrompt, FieldPrompt, ComposeResult, Pressed, Static, Submitted, The shared one-field prompt: inline validation, no silent failures.      Subclas, Return (value, None) to accept or (None, reason) to hold the form open. (+31 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.04
Nodes (60): main(), Any, Screen, EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Persist local-only presentation settings and apply the theme immediately., Tick off a Captain's objective (WP-UI11) — local progress only.          Called, Host the app in a browser via `textual-serve` (DESIGN §11, §15; WP68 remote)., Expose current-screen actions through Textual's fuzzy command palette. (+52 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.04
Nodes (46): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., _citadel_stage(), _depletion(), PlanetScreen, PlanetSprite, ComposeResult, Pressed (+38 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.04
Nodes (61): Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, salt_raid_caches(), bearing(), _bfs_tree(), compute_embedding(), _leaf_weights(), Seeded 2D spatial embedding for sectors — the nav rose's sense of direction.  DE, Direction from sector ``src`` to ``dst`` in radians (``atan2``).      Returns `` (+53 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.08
Nodes (78): apply_result(), Upsert a reducer's new entities into the mutable container (sanctioned)., instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting() (+70 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.11
Nodes (45): _check_degree_cap(), _check_discovery_gradient(), _check_expansive_no_chokepoint(), _check_home_clusters(), _check_planet_ownership(), _check_profitable_pair(), _check_reachable(), _check_relations() (+37 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.04
Nodes (84): base_owner_hostile(), Whether an operational base's owner treats the player as an enemy (§4.2, WP40)., hostile_base_in_sector(), An operational base in `sector_id` that engages the player (§4.2, WP40)., An operational base defends its system against a hostile entrant (§4.2, §10 — WP, roll_base_defense(), _home_cluster_bases_intact(), npc_seizure_ready() (+76 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.05
Nodes (75): A remote rules rejection compatible with every local rule-error catch.      JSON, RemoteRulesError, _amain(), _encode_any(), _error(), GameServer, LobbyServer, main() (+67 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.02
Nodes (204): ActiveBinding, _best_roundtrip_margin(), Best per-unit profit buying a commodity from `sell_port` and selling to `buy_por, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, `BotRunner` — the event-trigger + turn-driver harness a bot script uses (DESIGN, `BotSwarm` — many bots against one authoritative game (DESIGN §14 — WP69).  The, decay_grudges(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called. (+196 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.03
Nodes (137): BaseModel, _player_damage(), Main Gun output per round: (damage + the global bonus) × rate (§4.1)., One resolved combat round (WP25/WP26)., RoundResult, AspectFormula, BaseServicesConfig, CombatConfig (+129 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.14
Nodes (28): contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate(), _int(), literalist(), MechanicContext (+20 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.10
Nodes (23): flip_row(), Reflect a full row left<->right: reverse it and swap each asymmetric glyph     t, Slot, The authored row-height of a ship grammar tier (all parts share it)., Pick the tallest tier whose authored height fits ``height``; falls back to     t, _select_grammar(), _tier_height(), _all_glyphs() (+15 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.07
Nodes (28): AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed, Shared exact-amount field with −/+ stepping for logistics and recruitment., An integer input followed by decrement/increment buttons., Clamp an over-cap typed value back to `maximum` in place, so the field can (+20 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.08
Nodes (55): AllianceLeadershipChanged, GovernanceChanged, Core Space changed hands to a new governing alliance (§6.3, §4.2, WP49).      `c, An internal coup swapped a bloc's leader (§6.3, WP51).      `old_leader_roster`/, apply_intrigue(), flip_core_governor(), GovernanceDelta, IntrigueDelta (+47 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.05
Nodes (91): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), _build_game(), Load the game at `db` if it exists, else generate a fresh one there (WP12 resume, Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP, Path, SqliteRepository (+83 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.06
Nodes (44): build_graph(), Build the warp graph and return its adjacency plus the region groups., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, bfs_distances(), Forward hop distance from `src` to every reachable sector.      Accepts any int-, enroll(), Shared test helpers.  The big bang no longer seeds players — enrolling a player (+36 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.03
Nodes (59): Aspect, ComputerDTO, EncounterFoeDTO, GameState, Hold, LocalMapDTO, LogEntry, MessagesDTO (+51 more)

### Community 31 - "Detail Table Overlay"
Cohesion: 0.06
Nodes (33): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+25 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.10
Nodes (30): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology, MeshTopology (+22 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.11
Nodes (47): DrawFn, EconomyConfig, Economy constants (DESIGN §8). All latinum figures in slips., clear_filled(), desired_stock_frac(), generate_orders(), hinterland_drift(), liquidity_drip() (+39 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.11
Nodes (27): apply_patch_lines(), build_parser(), _build_patch(), cmd_governance(), cmd_list(), cmd_show(), _components(), _diff_after() (+19 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (58): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+50 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.07
Nodes (27): BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Pressed, Submitted, The LLM pilot's console — a Textual app watching and steering the brain (dev-onl (+19 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.05
Nodes (54): load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`)., Open the save (loading an existing game, or creating a fresh one from `seed`)., load_config() (+46 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.05
Nodes (38): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, BaseScreen, ComposeResult, Static, Vertical, Widget, `PANE_BINDINGS` minus the verbs *this* base cannot honour right now.          Th (+30 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.07
Nodes (19): BattleScreen, DeployEntry, MapView, Battle, Click, ComposeResult, Key, Text (+11 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.09
Nodes (36): The next unused name for `kind`. Exhausting a pool falls through to numbering., Draw a POC surface name if available and unused; fall back to kind namer., FindKind, Random, Shared archaeological find identities promoted from the groundwar POC.  The prod, Draw one POC-style archaeological proper name., Stable POC art/name subtype for a compatible production surface kind., Stable POC name for a compatible existing surface discovery. (+28 more)

### Community 42 - "Community 42"
Cohesion: 0.02
Nodes (276): is_criminal(), Whether the player's alignment marks them criminal in the governor's eyes (§10)., Apply the consequences of destroying `kills` of a species' ships (§6.5, WP27)., sour_attitude(), GameConfig, Top-level config bundle, validated from the parsed YAML mapping., §4/§10 reference integrity: every hull's `armament` ids resolve in the         `, apply_reward() (+268 more)

### Community 43 - "Community 43"
Cohesion: 0.05
Nodes (31): BotSetup, BotRunner, Command, Event, Run the turn drivers up to `turns` iterations (or until `stop`). Returns the cou, Run each registered turn driver once (the swarm's round-robin unit, WP69)., Drives one player of a game through the `ServiceProtocol` seam (dev-tier, WP60)., Register a trigger fired for every `event_type` a command produces (the TWX idio (+23 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (25): Changed, CountColumn, CountItem, CountSelector, Dropped, PlatoonComposer, _PmButton, Button (+17 more)

### Community 45 - "Community 45"
Cohesion: 0.04
Nodes (62): ABC, BaseException, CronFn, CronResolver, BotSwarm, Round-robin driver for N bots sharing one game (WP69)., Step every bot once per round for `rounds` rounds (or until all have stopped)., money_total() (+54 more)

### Community 46 - "Community 46"
Cohesion: 0.02
Nodes (134): EdgeApp, Resize, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)., Tear down the remote loop/thread on exit (WP68)., Open the numbered context-action menu over the current screen (WP73, D3)., Open contextual help for the current screen (`?` anywhere). (+126 more)

### Community 47 - "Community 47"
Cohesion: 0.08
Nodes (20): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), AlienContactScreen, ComposeResult, Widget, Re-fetch the view and repaint the conversation **in place** (§6.7).          `pi, The reply menu — the one thing that really changes between nodes.          Share, End the conversation: run the host's exit hook, or pop back to the game by defau (+12 more)

### Community 48 - "Community 48"
Cohesion: 0.08
Nodes (54): DataObject, accrue_interest(), deposit(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Random (+46 more)

### Community 49 - "Community 49"
Cohesion: 0.03
Nodes (148): advance_build(), building(), citadel_defense_mult(), citadel_foe(), CitadelError, conquer(), has_gun(), InvasionOutcome (+140 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (40): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+32 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.03
Nodes (68): clear_slot(), Remove the save and its WAL/SHM sidecars so a new game starts clean., ComposeResult, Pressed, RumorModal — reveals the lead a tavern rumour just bought (WP-PR2-03 / PT-35)., RumorModal, Any, ComposeResult (+60 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (36): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+28 more)

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (10): main(), PlaytestService, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable. (+2 more)

### Community 55 - "Community 55"
Cohesion: 0.13
Nodes (25): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothi (+17 more)

### Community 56 - "Community 56"
Cohesion: 0.12
Nodes (23): _ceo_button(), CorpPanels, Any, Button, ComposeResult, Vertical, A CEO-gated verb: members see it disabled with the reason (WP-UI19)., The corp's three panels — or the corpless empty state (presentation only). (+15 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (54): compose_horizontal(), HullStyle, Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Palette for a hull: three shading levels, the navigation-beacon hue pools     (a, Pick the richest grammar tier (listed largest-floor first) whose minimum     foo (+46 more)

### Community 58 - "Community 58"
Cohesion: 0.13
Nodes (21): get_biome_feature(), _luminance(), any, OpenSimplex, Random, Text, Procedural terrain generation using OpenSimplex noise.  The *gameplay* band layo, Rec.601 perceived luminance of an (r, g, b) triple in 0..1. (+13 more)

### Community 59 - "Community 59"
Cohesion: 0.12
Nodes (8): GroundExpeditionScreen, Any, Key, Walk, scan, excavate, and talk through authoritative survey commands., POC camera pan: the cursor rides with the viewport., Enter means "commit the cursor": set down while inbound, march once landed., Whether the cell under the cursor is an advertised drop site., Clear the overlay and stop the clock — also the skip path, so a keypress during

### Community 60 - "Community 60"
Cohesion: 0.08
Nodes (30): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl (+22 more)

### Community 61 - "Community 61"
Cohesion: 0.02
Nodes (49): CorpDTO, HaggleQuote, LeadDTO, MarketDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, A read-only read on a counter-offer before the player commits it (§8).      `fai, A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co (+41 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (16): HelpScreen, Screen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult (+8 more)

### Community 63 - "Community 63"
Cohesion: 0.07
Nodes (28): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, GroundwarApp, main(), `edge-groundwar` — the ground-war POC's Textual shell.  Throwaway UI (the `tui`-, load_config(), Path, Groundwar POC config — a thin adapter over the production schema (GW-WP02).  Bal (+20 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (42): Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus() (+34 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (45): DialoguePack, A named species roster (DESIGN §6): alliances + the species pool drawn from., Dialogue/diplomacy reference integrity (§6, §13): ids and hooks resolve., RosterConfig, Alien dialogue (DESIGN §6.7) — a pure, core-level package.  `edge.dialogue` owns, Intent, is_known_context(), Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace (+37 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (10): FormField, Any, DataTable, HeaderSelected, OptionSelected, RowSelected, Two-pane sysop dashboard: nav left, view right, audit trail below., Enter/click on a players or standings row opens its full dossier. (+2 more)

### Community 67 - "Community 67"
Cohesion: 0.15
Nodes (4): ContactDTO, One alien tech offer (§6, §8): a component or aspect upgrade, for latinum or bar, A peaceful alien contact screen (§6, §6.7, §11)., TechOfferDTO

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.17
Nodes (16): _discoveries(), _planets(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers)., The spatial display id for an internal sector id, or `—` if none is cached., A sector reference as `internal/spatial` (the §5.1 dual id)., Reverse the internal→spatial map (spatial ids are a bijection, §5.1)., Resolve a `--route` endpoint token to an internal sector id.      Accepts an int (+8 more)

### Community 70 - "Community 70"
Cohesion: 0.11
Nodes (46): fighter_foe(), NpcEntry, owner_tag(), A string tag for a force/holding owner — the limpet key (§10, WP56).      ``"all, The garrison as a single all-round combat foe, scaled by fighter count (§10, WP4, The outcome of an NPC entering a defended sector (§10, WP-PR02).      `destroyed, Resolve `force`'s defenses against `species` drifting in (§10, WP-PR02) — pure,, resolve_npc_entry() (+38 more)

### Community 71 - "Community 71"
Cohesion: 0.07
Nodes (50): Color, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+42 more)

### Community 72 - "Community 72"
Cohesion: 0.05
Nodes (47): Merge a generated dialogue sidecar onto the default roster and run §13 integrity, validate_sidecar(), AnthropicBackend, AntigravityBackend, Backend, CliBackend, DebugBackend, _extract_json() (+39 more)

### Community 73 - "Community 73"
Cohesion: 0.08
Nodes (26): OutEdges, Wire one group: a random spanning tree, then edges toward avg degree ~2.5., Wire one group internally as a planar outer-planar graph with zero crossings., `planar` bridging: connects clusters using a planar spiderweb meta-graph., Dense concentric rings numbered outward from sector 1.      Sector 1 has ``max_w, Partition sequential IDs into rings of size ``cap * radius``., Add increasingly long ring chords until endpoints reach the warp cap.          S, Replace eligible two-way chords with paired, distant one-way exits.          The (+18 more)

### Community 74 - "Community 74"
Cohesion: 0.08
Nodes (50): Configuration loading (the I/O seam for the pure `edge.core.config` schema).  Re, Ownership, Ownership of a planet/base/force (DESIGN §4.2, §4-WP66): none / alliance / playe, _base(), WP78 — base-hosted markets (DESIGN §4.2).  A port sharing its sector with an orb, Sector 2 holds a base-hosted port (SELL fuel ore); the player sits there., test_commission_clamps_to_the_purse(), test_corp_host_taxes_outsiders_but_not_members() (+42 more)

### Community 75 - "Community 75"
Cohesion: 0.12
Nodes (32): _clamp_ship_field(), DevPatchError, Exception, Ship, Field-specific validation for a ship integer set/add (raises on hard limits)., A malformed or impossible dev patch (unknown target, missing entity, bad key)., Hosted denials follow the same warning-toast paths as embedded denials., test_remote_rules_error_matches_local_domain_error_catches() (+24 more)

### Community 76 - "Community 76"
Cohesion: 0.12
Nodes (20): _event_player(), The acting/addressed player of an event, if any (its `player_id`/`owner_player_i, Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el (+12 more)

### Community 77 - "Community 77"
Cohesion: 0.10
Nodes (29): _footer_keys(), _open_computer(), PT-32 — the Computer's keyboard model: a tab owns its keys.  The screen binds on, chrome.EdgeScreen pins Back first — it used to fall in behind whatever the     f, PT-51: `P` on the Map plots a course to the highlighted sector and lands on the, Each category pane owns 1..N for its own sub-tabs — so `2` means a different tab, The corporation lives under Relations now, not behind a game-screen hotkey., Parity guard for the `action_descriptors` override (tests/test_ui_actions.py (+21 more)

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
Cohesion: 0.10
Nodes (39): decode_command(), decode_dto(), _decode_dto_body(), decode_event(), _decode_value(), encode_command(), encode_dto(), encode_event() (+31 more)

### Community 83 - "Community 83"
Cohesion: 0.21
Nodes (16): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), _parse_args(), Parse server launch settings, including default storage and operator-secret sour (+8 more)

### Community 84 - "Community 84"
Cohesion: 0.03
Nodes (36): EngineRoomPreviewDTO, Presentation-only before/after aspects for one prospective install or swap (WP-U, CronTask, EngineTicker, Schedules and runs the Phase-1 cron tasks against a `GameService`.      The sche, Resume the saved tick counter + per-cron next-due, if any (WP12)., The embedded ticker (tests/shots that step it directly)., The wrapped in-process service (single-player back-compat; never used for remote (+28 more)

### Community 85 - "Community 85"
Cohesion: 0.02
Nodes (151): _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors(), _grow_cluster() (+143 more)

### Community 86 - "Community 86"
Cohesion: 0.06
Nodes (56): _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7)., _roll_kind() (+48 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (26): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.12
Nodes (29): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, Run the species' signature hook, or `None` if it has none / is not yet implement, run_hook(), _ctx(), WP33 — signature-mechanic framework + first hooks (§6.2).  Two layers: pure-hook, An absent mechanic, and a hook id the code has not grown, both resolve to None., The sig.* verdict corpus resolves under the §13 integrity suite. (+21 more)

### Community 89 - "Community 89"
Cohesion: 0.22
Nodes (3): EngineRoomDTO, The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)., _room()

### Community 90 - "Community 90"
Cohesion: 0.22
Nodes (14): Console, _build_sheet(), _draw_sprite(), export_multipage_pdf(), export_sprite_sheet(), Path, Text, Vector export for the procedural sprites (dev-only sprite sheets).  Lays every r (+6 more)

### Community 91 - "Community 91"
Cohesion: 0.30
Nodes (11): _hazard_logged(), _new_game(), _put_black_hole(), WP-PR05 — black-hole interaction never crashes (playtest note PT-28).  A black h, After entering, the black hole sits in the current sector; logging it (the     s, Drop a black hole into `sector_id`; return its discovery id., The full 2x2 acceptance matrix: mouse/keyboard x nonlethal/lethal, identical., _set_hull() (+3 more)

### Community 92 - "Community 92"
Cohesion: 0.07
Nodes (46): Seed the roster's authored inter-species grudges for the cast pairs (§6.5, WP27), _seed_grudges(), disposition_band(), may_occupy(), Name the band a disposition value falls in (hostile / neutral / friendly, §6)., Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules, WP16, Grudge, A durable, dated grievance (DESIGN §4, §6.5) — the diplomacy layer's memory. (+38 more)

### Community 93 - "Community 93"
Cohesion: 0.14
Nodes (26): list_portraits(), nebular_bloom(), portraits_dir(), Path, Text, Species portrait rendering via chafa (image → Rich Text terminal art).  Not TUI-, Run image `path` through chafa and return its decoded ANSI string (the cached un, A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35). (+18 more)

### Community 94 - "Community 94"
Cohesion: 0.14
Nodes (24): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+16 more)

### Community 95 - "Community 95"
Cohesion: 0.03
Nodes (44): ComputerScreen, ComposeResult, Pressed, TabActivated, Repaint the Route tab from the plotted `RouteDTO` (or the empty state)., The DTO under the highlighted row of `table_id`, or None.          WP-UI21: reso, The subview a category opens on: the requested target if it lives here,, A subview pane carrying its own action keys (PT-32) — the one place a         pa (+36 more)

### Community 96 - "Community 96"
Cohesion: 0.12
Nodes (31): _cell_cost(), _dist(), _nearest_unfound(), path_to(), Pure survey-map generation from real universe discoveries (GW-WP05, GW plan §GW-, Foot-entry cost on the live map; 0 == impassable. Reads the frozen `SurveyMap`., Cheapest walking path (excluding the start cell) over the whole map, or None., Cells reachable in one local movement turn, with their cheapest entry cost. (+23 more)

### Community 97 - "Community 97"
Cohesion: 0.06
Nodes (21): Any, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade (+13 more)

### Community 98 - "Community 98"
Cohesion: 0.17
Nodes (28): _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, _drift_world(), Path, WP7 — the engine cron reducers and tick scheduler (DESIGN §9).  WP16 adds the `a, PT-37: the Stardock sector was an absorbing state, and that was the whole pileup, The symptom PT-37 reported: run the drift cron for a long while and count the cr, WP18: the governing alliance's members may drift into the Core; others never (WP (+20 more)

### Community 99 - "Community 99"
Cohesion: 0.09
Nodes (32): Binding, Any, Screen, Return the one canonical advertised-action list for a screen.      Danger levels, screen_actions(), _binding_rows(), Any, ComposeResult (+24 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.24
Nodes (4): ActionMenuScreen, Any, ComposeResult, Screen

### Community 103 - "Community 103"
Cohesion: 0.13
Nodes (30): A friendly settlement visible on the projected survey map.      ``plaza_x``/``pl, SurveySettlementDTO, ground_operation_view(), Project the player's active survey without exposing its generation identity (GW-, _inhabited_view(), _landed(), MonkeyPatch, Path (+22 more)

### Community 104 - "Community 104"
Cohesion: 0.12
Nodes (24): Adjacency, can_warp(), plan_route(), plan_route_legs(), Describe the fewest-hop route `src -> dst` as a costed, annotated plan.      Com, Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.      For, The sectors reachable in one hop from `sector_id`., Whether a single direct warp `from_sector -> to_sector` is legal. (+16 more)

### Community 105 - "Community 105"
Cohesion: 0.09
Nodes (39): One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, One sector on the nav-rose trail breadcrumb (§11): its spatial id and distance, TrailCrumb, WarpDTO, Shared character-grid canvas and band palette for baked map/nav views (§11).  Bo, build_nav_strip() (+31 more)

### Community 106 - "Community 106"
Cohesion: 0.10
Nodes (14): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., first_focusable(), focus_content(), TabActivated, Widget, The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target)., Put keyboard focus on `node`'s primary control (see `first_focusable`).      Whe (+6 more)

### Community 107 - "Community 107"
Cohesion: 0.17
Nodes (24): range, _do(), _hidden_find_with_neighbor(), _park_and_detect(), _planet_with_sites(), WP5 — discovery salting, the rarity/value gradient, detection, and salvage (§7)., First (state, hidden high-tier find, two-way neighbour sector) over `seeds`., Detection snapshots on entry: a hidden find stays unseen after a sensor upgrade (+16 more)

### Community 108 - "Community 108"
Cohesion: 0.14
Nodes (31): combat_contexts(), DialogueIntegrityError, Exception, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3, Assert the §13 dialogue-integrity invariants for a roster (raises on failure)., A roster's dialogue packs fail the §13 integrity checks., reachable_contexts() (+23 more)

### Community 109 - "Community 109"
Cohesion: 0.10
Nodes (8): LocalMapView, Any, Resize, The local sector ego-graph (Computer/Map screen → §10, §11).      A node-and-edg, Selectable sector nodes, top-to-bottom then left-to-right (cursor home order)., Re-bake the map to the current widget width (no-op without a rebake hook)., Swap in a freshly baked map, preserving the selected sector where possible., Internal id of the keyboard-highlighted sector, or None when empty.

### Community 110 - "Community 110"
Cohesion: 0.04
Nodes (52): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), PlanetSpriteSize (+44 more)

### Community 111 - "Community 111"
Cohesion: 0.09
Nodes (43): is_friendly(), Whether a disposition value sits in the friendly (amity) band., AliensConfig, Disposition thresholds + escape floor for the alien system (DESIGN §6, §10)., entity_species(), The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None., Lead, LocationRef (+35 more)

### Community 112 - "Community 112"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 113 - "Community 113"
Cohesion: 0.06
Nodes (68): A deterministic offline backend — emits a minimal valid grammar (dry-run / tests, StaticBackend, Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_line() (+60 more)

### Community 114 - "Community 114"
Cohesion: 0.03
Nodes (132): admission_met(), admission_tasks_done(), _alliance_key(), alliance_standing(), apply_join_standing(), core_status(), governor_hostile(), owner_hostile() (+124 more)

### Community 115 - "Community 115"
Cohesion: 0.20
Nodes (15): apply_patch(), Apply (or, in dry-run, preview) a DevPatch and report what changed., config_dump(), _intervene(), _lobby_hint(), main(), menu(), _print() (+7 more)

### Community 116 - "Community 116"
Cohesion: 0.14
Nodes (13): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+5 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.06
Nodes (66): Command, Validate `command` for `player_id` and return its delta + events., reduce(), WP27: logging a find into the codex pays experience_per_discovery., WP27 Core-law basics: a criminal crossing into the Core is put on notice, once, test_core_law_notice_for_criminals_only(), test_discovery_experience_awarded_on_codex_stamp(), _generated() (+58 more)

### Community 119 - "Community 119"
Cohesion: 0.15
Nodes (19): A text report of a generated universe (the `--stats` dev view, §5)., summarize(), format_route(), list_items(), Render one category of populated universe items as an id-keyed table., Resolve two endpoints (internal or spatial id) and plot the fewest-hop route., main(), CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--stats] [--render DIR]`. (+11 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.16
Nodes (14): _build_at_radius(), _codes(), _draw_edges(), _label(), _layout_map_nodes(), _local_bfs(), _pointer_line(), The node's display text: `(id)` plus content codes once charted.      The spatia (+6 more)

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
Cohesion: 0.20
Nodes (20): _move_cost(), _passable_components(), Entry cost on foot; 0 == impassable (hard terrain or settlement masonry)., Label the 4-connected passable regions; return (labels, sizes).      Sites and t, _disc(), _planet_with_hidden_and_obvious(), GW-WP05 — survey generation from real universe discoveries (GW plan §GW-M2).  Tw, _survey() (+12 more)

### Community 127 - "Community 127"
Cohesion: 0.11
Nodes (20): cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text, Procedural planet generation using Signed Distance Fields. (+12 more)

### Community 128 - "Community 128"
Cohesion: 0.10
Nodes (36): produce(), Run one production tick for `planet`, returning the updated world (§8).      A n, planet_growth(), Run BNT production for every owned planet (§4.2, §8).      Pure and deterministi, _enemy_world(), WP54 — citadels: levels, treasury, timed builds, the planetary gun (DESIGN §4.2,, An alliance-owned world in the player's sector, ready to invade (no base)., A single owned colony in the player's sector (no port), ready to fortify. (+28 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.14
Nodes (19): _dim(), _feature_colors(), _hex(), _landing_frames(), Live survey expedition over the service/DTO boundary (GW-WP07).  This is the pro, The band's authored (fg, bg) for a feature name — deliberately *not* yet     con, Pin a colour to concrete truecolor, so the terminal cannot theme it away.      N, A rich style whose foreground is legible against the background it actually gets (+11 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.20
Nodes (17): _bar10(), encounter_view(), EncounterDTO, The live hostile encounter (§10, WP24/25), or None when the player is not engage, _assault_state(), _blocker_seen_by_reducer(), _eligible_planet(), _place() (+9 more)

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

### Community 137 - "LiveSysopService"
Cohesion: 0.12
Nodes (17): _bfs_from(), _grudge_targets(), is_trader(), movement_policy(), _pick_by_distance(), plan_move(), _player_sectors(), _port_sectors() (+9 more)

### Community 138 - "main"
Cohesion: 0.09
Nodes (18): GroundCellDTO, One sensor contact, masked until excavation settles the real discovery (G6/G7)., Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, SurveyContactDTO, SurveyExpeditionDTO, The active survey's fog-safe viewport, or ``None`` while in orbit (GW-WP07)., Click (+10 more)

### Community 139 - "MarketDTO"
Cohesion: 0.14
Nodes (9): Resize, Static, Text, `SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait., Render a species' portrait image (by `roster_id`) into its allotted cell box., SpeciesPortrait, ContactReply, Land focus on the new menu — the old reply rows were just removed under it. (+1 more)

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.16
Nodes (10): _haggle_highlighted(), _highlighted_line(), Any, Screen, The (TradePanel, highlighted CommodityLine, port) trio, or (None, None, None)., Shared trade handler: buy/sell a clamped chunk of the highlighted row., Open a counter-offer haggle on the highlighted row (§8); commit on submit., Re-render the trade panel from fresh state after a trade/haggle. (+2 more)

### Community 142 - "TopologyModeConfig"
Cohesion: 0.23
Nodes (5): ComposeResult, RowHighlighted, The commodities trade UI: a live pricing table over the docked port.      Reusab, Rebuild responsive columns while preserving the logical commodity selection., TradePanel

### Community 143 - "Community 143"
Cohesion: 0.27
Nodes (4): Pressed, Mode / planet / seed pickers; platoon composer (assault) or world toggle     (ex, The reusable composer committed a squad — build the raid and drop in., SetupScreen

### Community 144 - "trader_step"
Cohesion: 0.12
Nodes (22): ContactSession, One live conversation visit with an alien (DESIGN §6.7) — the per-contact sessio, arc_facts(), callback_facts(), contact_facts(), encounter_facts(), ensure_session(), note() (+14 more)

### Community 145 - "test_genesis.py"
Cohesion: 0.24
Nodes (14): hourly_port_economy(), market_settlement(), The hourly port-economy tick: order-book market, or the legacy regen (§8, WP47)., The daily order-book settlement: match the book, move goods+latinum, drip purses, _market_config(), _market_world(), A 1-2-3 chain with a shortage port (sector 2) and a surplus port (sector 3)., With the market disabled, `hourly_port_economy` is the exact legacy regen body. (+6 more)

### Community 146 - "test_intel_contact.py"
Cohesion: 0.18
Nodes (5): _code_markup(), Text, 5 right-aligned trail lines: header, up to 3 history entries, you.          Each, 5 detail lines for the keyboard-selected warp target., Render content tokens (S/P Stardock-port, @ planet) colour-coded by type.

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
Cohesion: 0.50
Nodes (3): pick_subsystem(), Engine-room subsystem icons for the TUI (UI_MOCKUPS.md §8).  The procedural `edg, The decorative ASCII icon for an engine-room subsystem (§8).

### Community 155 - "market_view"
Cohesion: 0.17
Nodes (20): accept(), is_convoyed(), Stamp an offered contract into an active one on the player's slate (WP57)., Whether a species instance is under escort by any player (§6.7, WP57).      A co, WP57 — favors + escort contracts (DESIGN §6.7, §14).  The contract system is pur, Sectors 1-2-3 with a fuel-ore-buying port in sector 2, player + ship in sector 1, _ship(), _sp() (+12 more)

### Community 156 - ".compose"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 157 - "Ticker"
Cohesion: 0.23
Nodes (13): _build_site(), generate_survey(), _landing(), Random, Vec, A peaceable walled town: gated walls + homes carve masonry into `blocked`., A passable in-component cell outside every keepout, drawn from a per-site salt., Land near the map's left-middle, but only inside the sites' component. (+5 more)

### Community 158 - "StaticGenerator"
Cohesion: 0.31
Nodes (6): Random, Text, Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.  Un, Generates a frame of random low-contrast static ("snow")., Fill a `width` × `height` frame with weighted random noise glyphs.          `sub, StaticGenerator

### Community 159 - ".rebuild_adjacency"
Cohesion: 0.29
Nodes (13): Run one trade for every NPC merchant working a port this firing (§8, WP43)., trader_step(), A 1-2-3 Frontier chain with a trading port at sector 2 (optionally a player ther, A `selvani` merchant (movement_policy trade_seek in the default roster ⇒ a trade, _selvani(), test_a_distant_player_is_not_warmed(), test_non_trader_species_never_trades(), test_trader_dumps_held_cargo_before_buying() (+5 more)

### Community 160 - "Community 160"
Cohesion: 0.25
Nodes (8): WP1 — engine room subsystems/components/derived aspects, WP2 — Stardock services & multiple ship types, The Basilisk kit (gravity lance, sidewall regen, recon drone), Facing is armor and armament (quadrant screens + localized components), In Fury Born combat inspiration (David Weber), Traveling missile salvos (chasing board objects), Space-battle POC (edge-spacebattle), Vector-lite movement (velocity persists, thrust bends)

### Community 161 - ".state"
Cohesion: 0.36
Nodes (12): _do(), WP66 — corporations: shared bank + assets + corp war (DESIGN §4).  The core inva, Two players (both at sector 1) each with a ship; a planet p1 owns in that sector, test_ceo_leaving_promotes_lowest_id_member(), test_corp_asset_treats_every_member_as_owner(), test_corp_bank_is_non_negative_and_ceo_gated(), test_corp_war_is_mutual_and_hostility_follows(), test_dissolution_rekeys_assets_to_the_departing_ceo() (+4 more)

### Community 162 - "ComputerDTO"
Cohesion: 0.31
Nodes (12): _drop_entity(), _inject(), _knows_a_far_discovery(), Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7), Log-coordinates is a reply on the offer_coordinates node, not the greeting — you, Remove the roaming Entity so a test can isolate the regular coordinate-tip mecha, Point the species' knowledge at a real, reachable, unexplored rare+ discovery., test_accept_lead_without_a_tip_is_rejected() (+4 more)

### Community 163 - "TavernDTO"
Cohesion: 0.20
Nodes (11): MapNodeDTO, A clickable sector node on the local map: its label's cell box in `rows`.      `, _nearest_node(), Index of the node to move to from `hits[idx]` in the pressed direction, or None., Move the selection to the nearest node in the pressed screen direction., The shared arrow-nav helper picks the nearest node in the pressed direction., Left/Right steps to the nearest adjacent *column*, row-nearest, not a far same-r, On an exact column/row-distance tie, the warp-linked candidate wins; else the up (+3 more)

### Community 164 - "test_sig_corpus.py"
Cohesion: 0.26
Nodes (11): effective_trade_posture(), The species' trade posture as this player experiences it (§6.1/§6.2 — WP74)., WP74 — the signature-mechanic corpus routes (SEAMS_PLAN A2, decision D4).  The s, Each carrier species' pack routes a choice into its own sig.* namespace (A2 clos, test_alliance_gated_trade_opens_for_sworn_members(), test_escalating_demand_ladder_climbs_and_betrayal_is_permanent(), test_every_dark_hook_has_a_corpus_route(), test_flee_drop_route_pays_once() (+3 more)

### Community 165 - ".apply"
Cohesion: 0.21
Nodes (4): PlaytestControls, Click, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 167 - "InterventionForm"
Cohesion: 0.17
Nodes (6): InterventionForm, ComposeResult, Pressed, Session, Submitted, A small validated form; dismisses with the field values, or None on cancel.

### Community 168 - "test_ui_sector_view.py"
Cohesion: 0.18
Nodes (7): Walk object rows only; the ship readout is deliberately skipped., StatusDrawerScreen, WP-UI12 — responsive sector view.  Compact replaces the art scene with a locatio, test_objective_visibility_is_one_setting_for_strip_and_sidebar(), test_status_drawer_opens_and_routes_a_pick(), test_status_drawer_up_down_walks_object_rows(), test_wide_sidebar_adds_objectives_checklist()

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 171 - "_line_state"
Cohesion: 0.29
Nodes (12): _line_state(), A 1-2-3-4-5 chain (all Frontier, non-Core) with the player at `player_sector`., _sp_rid(), test_coward_diverges_over_the_drift_timeline(), test_coward_moves_away_from_the_player(), test_hunter_converges_over_the_drift_timeline(), test_hunter_moves_toward_a_grudged_player(), test_hunter_without_a_grudge_just_drifts() (+4 more)

### Community 172 - "_SpriteCard"
Cohesion: 0.22
Nodes (7): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, Grid, TabPane

### Community 173 - "HaggleScreen"
Cohesion: 0.29
Nodes (3): HaggleScreen, ComposeResult, Submitted

### Community 174 - "Community 174"
Cohesion: 0.40
Nodes (4): Debris, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, Scatter drifting-wreckage clumps across the midfield (graveyard     scenarios) —, seed_debris()

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 176 - "landing_sites"
Cohesion: 0.22
Nodes (9): dig_trench(), _in_bounds(), is_landing_site(), landing_sites(), The cells a dig from `(x, y)` opens — a disc of `dig_radius`, clipped to the map, Every cell the shuttle may set down on — the player's drop-site choice.      Two, Whether `(x, y)` is a legal drop site (see `landing_sites`)., Where to rest the drop cursor: the remembered spot when it is still legal, else (+1 more)

### Community 177 - "LiveSysopService"
Cohesion: 0.33
Nodes (5): LiveSysopService, Any, Event, Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC., Apply an intervention to the authoritative live game as the target player.

### Community 178 - "_entity_world"
Cohesion: 0.28
Nodes (9): _entity_world(), A generated world with the Concordance placed in the player's sector., A virtuous player is blessed: stage persisted, attitude up, experience paid, spo, A criminal player is cursed: a permanent grudge forms (never_forgets Entity)., The judgment command replays to the identical state hash (the stage-ladder rail), _submit(), test_judgment_reducer_blesses(), test_judgment_reducer_curses_with_grudge() (+1 more)

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

### Community 183 - "terrain.py"
Cohesion: 0.29
Nodes (7): BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay*, The feature name a noise value falls into (nearest-first, last as fallback)., A `height × width` grid of gameplay feature names, deterministic from the seed., The gameplay band structure for one planet type.      `scale_x`/`scale_y` stretc

### Community 184 - "_feature_glyph"
Cohesion: 0.29
Nodes (7): _feature_glyph(), _glyph_ramp(), The feature's glyphs with cumulative weights (authored weights may be fractional, Draw this cell's glyph against the authored weights, deterministically.      The, Foliage reads as foliage only if the blank-weighted entries survive.      The ol, test_terrain_glyphs_are_stable_and_positional(), test_terrain_glyphs_follow_the_authored_weights()

### Community 204 - ".active_bands"
Cohesion: 0.33
Nodes (3): Every species' `home_band` hint must name a configured distance band (§6)., The config block for the selected `topology_mode` (§5 step 5)., The distance bands for the configured `topology_mode` (§5 step 5).

### Community 205 - "SurveySettlement"
Cohesion: 0.40
Nodes (5): _keepout(), Whether a candidate site cell is too near a settlement or the landing zone., A friendly walled town — resupply + one hint at play time (GW-WP06)., settlement_at(), SurveySettlement

### Community 206 - "attack_forbidden"
Cohesion: 0.33
Nodes (6): attack_forbidden(), Whether an `influence_gate` species forbids the player attacking it (DESIGN §6.2, `attack_forbidden` is true only for a cannot_attack_unbidden influence-gate spec, The reducer rejects an `attack` reply against an influence-gate species by its g, test_attack_reply_gated_by_influence(), test_influence_gate_forbids_attack()

### Community 207 - "test_ticked_trading_reproduces_to_an_identical_hash"
Cohesion: 0.33
Nodes (4): Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., A run of ticked trades (the WP12 rail) is deterministic — the same firings from, test_ticked_trading_reproduces_to_an_identical_hash()

### Community 212 - "_apply"
Cohesion: 0.50
Nodes (4): _apply(), Apply a hook result through the reducer helper against a minimal injected specie, A drain larger than the purse clamps at zero — the no-negative-balance invariant, test_payload_drain_clamps_latinum_at_zero()

## Knowledge Gaps
- **55 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script` (+50 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Community 128`, `Community 129`, `Screens, DTOs & Remote Play`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `Attitude, Disposition & Contracts`, `Station Art & Portrait Rendering`, `Domain Models & Colonizability`, `TopologyModeConfig`, `trader_step`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Bigbang Aliens & Region Control`, `market_view`, `Core Governance & Seizure`, `Core-Seizure Confirm Screens`, `.rebuild_adjacency`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Core Rules Tests`, `Community 42`, `Community 43`, `HaggleScreen`, `Community 45`, `Community 46`, `Community 48`, `Community 49`, `Community 61`, `Community 63`, `Community 65`, `Community 68`, `Community 73`, `Community 74`, `Community 75`, `Community 76`, `Community 79`, `Community 84`, `Community 85`, `Community 86`, `.pricing`, `Community 88`, `Community 92`, `Community 94`, `Community 98`, `Community 106`, `Community 108`, `Community 109`, `Community 110`, `Community 111`, `Community 114`, `Community 117`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `Community 42` to `Core Rules & Events Engine`, `Community 128`, `Sector Scene & Widgets`, `Standing, Corp & Combat Rules`, `test_ui_cloud_city.py`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `LiveSysopService`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `trader_step`, `test_genesis.py`, `Market Orders & Regions`, `Config Schema Models`, `Bigbang Aliens & Region Control`, `market_view`, `Ticker`, `Core-Seizure Confirm Screens`, `.rebuild_adjacency`, `Core Governance & Seizure`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `Dev Patch Tooling`, `.state`, `ComputerDTO`, `Core Rules Tests`, `test_sig_corpus.py`, `Community 43`, `_line_state`, `Community 45`, `Community 48`, `Community 49`, `_entity_world`, `Community 61`, `Community 69`, `Community 70`, `Community 74`, `Community 75`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 92`, `Community 96`, `Community 98`, `Community 103`, `Community 104`, `Community 108`, `Community 110`, `Community 111`, `Community 114`, `Community 118`, `Community 119`, `Community 121`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 42` to `Core Rules & Events Engine`, `Community 128`, `Sector Scene & Widgets`, `test_ui_cloud_city.py`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Planet & Orbit Views`, `LiveSysopService`, `Station Art & Portrait Rendering`, `Universe Embedding & Bearings`, `test_genesis.py`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `The Entity & Command Reduce`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Community 147`, `market_view`, `Bigbang Aliens & Region Control`, `Ticker`, `Core-Seizure Confirm Screens`, `.rebuild_adjacency`, `Core Governance & Seizure`, `Server Net & Engine Ticker`, `Dev Patch Tooling`, `.apply`, `Config Loading & Sidecar Merge`, `Community 43`, `Community 45`, `landing_sites`, `Community 49`, `Community 54`, `Community 61`, `Community 70`, `Community 71`, `Community 73`, `Community 74`, `Community 75`, `.active_bands`, `SurveySettlement`, `Community 84`, `Community 85`, `Community 86`, `Community 92`, `Community 96`, `Community 98`, `Community 103`, `Community 104`, `Community 111`, `Community 114`, `Community 118`, `Community 119`, `test_ui_black_hole.py`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 133 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 133 INFERRED edges - model-reasoned connections that need verification._
- **Are the 339 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 339 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._