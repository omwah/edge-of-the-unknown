# Graph Report - edge-of-the-unknown  (2026-07-21)

## Corpus Check
- 342 files · ~9,183,236 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 8490 nodes · 37943 edges · 211 communities (185 shown, 26 thin omitted)
- Extraction: 67% EXTRACTED · 33% INFERRED · 0% AMBIGUOUS · INFERRED: 12659 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4ebe8815`
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
- graphify.js
- graphify.md
- graphify.md
- __init__.py
- .pricing

## God Nodes (most connected - your core abstractions)
1. `UniverseState` - 565 edges
2. `GameConfig` - 528 edges
3. `Commodity` - 444 edges
4. `reduce()` - 399 edges
5. `EconomyError` - 360 edges
6. `EdgeApp` - 267 edges
7. `Warp` - 242 edges
8. `apply_result()` - 241 edges
9. `ComponentTier` - 240 edges
10. `Event` - 231 edges

## Surprising Connections (you probably didn't know these)
- `test_archetype_icons_are_distinct_procedural_cell_art()` --calls--> `generate_sprite()`  [EXTRACTED]
  tests/test_station_archetype_art.py → edge/art/generator.py
- `test_every_live_band_has_a_contact()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_placement_is_seeded_and_deterministic()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_roster_alliances_become_entities()` --calls--> `generate()`  [EXTRACTED]
  tests/test_aliens.py → edge/bigbang/generator.py
- `test_every_starbase_sector_hosts_a_market()` --calls--> `generate()`  [EXTRACTED]
  tests/test_base_market.py → edge/bigbang/generator.py

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

## Communities (211 total, 26 thin omitted)

### Community 0 - "Core Rules & Events Engine"
Cohesion: 0.09
Nodes (476): AmountPrompt, _MissingArg, _parse_component(), ValueError, The LLM pilot's action vocabulary → ordinary game commands (dev-only).  A decisi, Parse the projected loose-part label ``converter (II) x1``., A decision omitted (or mistyped) a required argument., Example bot: an explorer that pushes into unexplored space, salvaging as it goes (+468 more)

### Community 1 - "Sector Scene & Widgets"
Cohesion: 0.06
Nodes (59): is_colonizable(), Whether a world of this type can be claimed and settled (§4.2).      Colonizable, range, generate_with_player(), Any, `generate()` then `enroll()` — the common "fresh game with player 1" setup., test_no_roster_falls_back_to_federation_stub(), The path from the start sector to Stardock opens pre-explored (round-2).      On (+51 more)

### Community 2 - "Screens, DTOs & Remote Play"
Cohesion: 0.02
Nodes (149): Sizes/counts for the SectorView sprite scene (presentation only, no rules)., The per-type footprint bounds shared by Sector and docked station views., Resolve the original `_paint_station` sizing with per-kind config., SceneArtConfig, ArmamentItem, Aspect, BarracksItem, BountyDTO (+141 more)

### Community 3 - "Standing, Corp & Combat Rules"
Cohesion: 0.12
Nodes (36): _do(), _first_empty(), _first_filled_nonkeystone(), Ship, Subsystem, WP1 — engine-room subsystems, derived aspects, and the slot reducers (§4.1).  Co, No separate cap: filling all 5 spindrive slots at Tier III gives 5 + 2·5., A knocked-out part contributes nothing until it is patched (§4.1). (+28 more)

### Community 4 - "UI Config & Route Tests"
Cohesion: 0.05
Nodes (24): Carried territory stock + devices + this sector's force (§10/§14 — WP72)., TerritoryDTO, Carried territory stock + devices for the Deploy screen (§10/§14, WP72)., Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)., ListPicker, ComposeResult, `options` are (markup label, ref) rows; the ref comes back on dismiss., _DeployRow (+16 more)

### Community 5 - "Aliens & Alliance Admission"
Cohesion: 0.03
Nodes (123): Adjacency, admission_met(), admission_tasks_done(), The admission tasks the player has completed for a bloc (the §6.3 ledger)., Whether the player has completed the bloc's `admission_price` tasks (§6.3)., HardwareItem, One row in the Stardock hardware emporium (UI_MOCKUPS.md §5, DESIGN §8)., port_unit_price() (+115 more)

### Community 6 - "Computer Screen & Alliances Tab"
Cohesion: 0.10
Nodes (34): PlaytestApp, Hosts the real contact screen over the harness service; `c` opens the dial board, Phase-2 — the dev-only dialogue play-test harness (DESIGN §6.7, edge/dialogue/au, PT-39/PT-40: `c` opens the board, ↑↓ walk the dials, Enter/←→ change the focused, PT-38: the harness pins one face per species — the dial is how the others are se, The dial reaches the mounted portrait, not just the DTO (PT-38)., PT-41: standing is not just a bar — a hostile species greets you in a hostile vo, A pack that authors a greeting must author a hostile one (PT-41).      The chain (+26 more)

### Community 7 - "Disposition Bands & Ship Classes"
Cohesion: 0.04
Nodes (101): Game, Port, PortCommodity, A ship hull (DESIGN §4).      A player hull carries `subsystems` (the engine-roo, Holds occupied — trade cargo plus loose (uninstalled) components.          Loose, Colonists aboard, summed across every people the ship carries., Top-level game record (DESIGN §4)., A node in the warp graph (DESIGN §4). `warps_out` are sector ids. (+93 more)

### Community 8 - "Planet & Orbit Views"
Cohesion: 0.05
Nodes (87): CombatConfig, _evade_chance(), flee_chance(), _hit_foe(), _player_damage(), player_foe(), Random, Ship (+79 more)

### Community 9 - "Attitude, Disposition & Contracts"
Cohesion: 0.06
Nodes (46): Cell, A surface-exploration site on a descended planet (UI_MOCKUPS.md §4, §7).      `s, SurfaceSite, blurb_for(), _carve_lakes(), _carve_rivers(), _fbm(), _Flavor (+38 more)

### Community 10 - "Station Art & Portrait Rendering"
Cohesion: 0.03
Nodes (64): The Terra Nova descent scene from UI_MOCKUPS.md §4.      Terrain is produced by, The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.      Mirrors the sidebar, A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).      A fri, The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness., sample_contact(), sample_engine_room(), sample_planet(), sample_surface() (+56 more)

### Community 11 - "Encounters & Station Archetypes"
Cohesion: 0.04
Nodes (51): One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).      `s, One subsystem panel: its derived aspect and its slot grid (§4.1)., Slot, Subsystem, EmptyState, Any, Swap the copy in place (e.g. 'nothing here' vs 'nothing matches')., A consistent 'nothing here' block: what is empty and what fills it. (+43 more)

### Community 12 - "Domain Models & Colonizability"
Cohesion: 0.11
Nodes (36): DialogueLine, DialogueWhen, A line entry's criteria predicate (DESIGN §6.7, salience-scored selection)., One conditional line entry (DESIGN §6.7): a `when` + a realisation + weight., combat_contexts(), Resolve and render one line for `context`, returning (text, updated recency ring, The peaceful contexts a species can reach in conversation (per its params, §6.7), The combat beats a species can be driven to by the encounter reducers (§6.7, WP3 (+28 more)

### Community 13 - "Engine-Room Component Workbench"
Cohesion: 0.05
Nodes (38): AmountPrompt, FieldPrompt, ComposeResult, Pressed, Static, Submitted, Shown while the terminal is below the 80×24 floor (WP-UI05).      It never traps, The shared one-field prompt: inline validation, no silent failures.      Subclas (+30 more)

### Community 14 - "Dialogue-Pack Save Guard"
Cohesion: 0.04
Nodes (62): TUI presentation options (no rules) — the sector-screen warp grid + sidebar., UIConfig, main(), EdgeApp — the Textual application shell for the throwaway TUI skeleton.  Reads o, Generate a fresh universe on disk and start the background ticker.          The, Reload the saved game by replaying its command log (DESIGN §12).          Return, Validate art coverage and read scene-sprite sizes before a game starts., Run the client-owned engine ticker as a Textual worker (WP61).          The tick (+54 more)

### Community 15 - "Game Lifecycle & Pathfinding"
Cohesion: 0.11
Nodes (17): PlanetDTO, The orbit view of a planet (UI_MOCKUPS.md §3, DESIGN §4.2)., The orbit view for a planet in the player's current sector, if any., _belt_dto(), WP-PR06 — the belt orbit screen hides colony/descent affordances (playtest PT-30, _terrestrial_dto(), test_belt_orbit_hides_descent_and_stores(), test_terrestrial_orbit_keeps_descent_and_stores() (+9 more)

### Community 16 - "Universe Embedding & Bearings"
Cohesion: 0.04
Nodes (77): _make_payload(), _make_surface_payload(), Random, Salt the universe with discoveries (DESIGN §5 step 7 / §7, WP5).  Rolls an open-, Salt a legendary technology cache onto each hostile species' homeworld (§7, §10, A rarity-scaled payload (§7/§8): lore for phenomena, then latinum → component, A surface-site payload under the D6 archaeology contract (GW-WP05).      Every e, Populate `state.discoveries` deterministically from the seed (§7). (+69 more)

### Community 17 - "The Entity & Command Reduce"
Cohesion: 0.07
Nodes (79): entity_species(), The placed singular roaming Entity instance (DESIGN §7, WP34/WP35), or None., instance_key(), The per-contact-instance dialogue key for a species ship (DESIGN §6.7, WP29/H7)., contact_view(), The alien-contact screen for a species in the player's sector (§6, §6.7, §11)., _cfg_with_attack_choice(), _cfg_with_band_greeting() (+71 more)

### Community 18 - "TUI Screen Widgets"
Cohesion: 0.04
Nodes (106): _can_hold_a_people(), _Cast, ground_target_counts(), _guarantee_targets(), _inhabitant(), is_assaultable_for_a_fresh_player(), is_friendly_inhabited(), Random (+98 more)

### Community 19 - "Subsystem Layouts & Ownership"
Cohesion: 0.04
Nodes (125): base_owner_hostile(), Whether an operational base's owner treats the player as an enemy (§4.2, WP40)., hostile_base_in_sector(), An operational base in `sector_id` that engages the player (§4.2, WP40)., build_layouts(), build_subsystems(), Subsystem, Instantiate intact subsystems from a layout mapping (§4.1).      Base components (+117 more)

### Community 20 - "Spacebattle Combat Rules"
Cohesion: 0.07
Nodes (78): FighterWing, Mine, _advance_salvos(), apply_damage(), arc_ok(), _beam_facing(), begin_turn(), _bot_ship_action() (+70 more)

### Community 21 - "UI Mockup Screenshot Harness"
Cohesion: 0.13
Nodes (44): Exception, One connected client: the socket, the authenticated account, and the seat it hol, Push queued notifications to one connection until the connection closes (WP65)., A JSON-RPC error to return to the caller (code + message)., RpcError, Session, A stable hash of the protocol surface — client and server refuse a mismatch at h, wire_fingerprint() (+36 more)

### Community 22 - "Market Orders & Regions"
Cohesion: 0.04
Nodes (76): ActiveBinding, Remote play for the LLM pilot: a synchronous facade over `RemoteClient` (dev-onl, Enum, The economy: pricing, trade resolution, haggling, banking, stock regen (§8).  Pu, Move stock `regen_frac` of the way toward `desired_frac * capacity`., regenerate_stock(), Core enumerations: the canonical TW commodity trio and port classes (§4).  These, Movement: warp legality, turn costs, and pathfinding (DESIGN §9).  Pure helpers (+68 more)

### Community 23 - "Config Schema Models"
Cohesion: 0.02
Nodes (86): AspectFormula, BaseServicesConfig, CorpConfig, CronCadenceConfig, DefenseConfig, DeviceConfig, EncountersConfig, EngineRoomConfig (+78 more)

### Community 24 - "Signature Mechanics"
Cohesion: 0.05
Nodes (74): A species' one systemic hook (DESIGN §6.2): a named hook + its params.      Auth, SignatureMechanicConfig, attack_forbidden(), contract_kill(), coordinate_broker(), escalating_demand(), flee_drop(), influence_gate() (+66 more)

### Community 25 - "Derived Aspects & Engine Room"
Cohesion: 0.06
Nodes (49): compose_horizontal(), flip_row(), HullStyle, Part, Random, Text, Shared machinery for compositional *hull* sprites -- ports and ships.  Both port, Palette for a hull: three shading levels, the navigation-beacon hue pools     (a (+41 more)

### Community 26 - "Dialogue Authoring Pipeline"
Cohesion: 0.07
Nodes (28): AmountStepper, _as_int(), ComposeResult, Horizontal, Pressed, Shared exact-amount field with −/+ stepping for logistics and recruitment., An integer input followed by decrement/increment buttons., Clamp an over-cap typed value back to `maximum` in place, so the field can (+20 more)

### Community 27 - "Bigbang Aliens & Region Control"
Cohesion: 0.05
Nodes (75): AllianceConfig, One alliance / rival bloc in the roster (DESIGN §6.3).      Joinability (WP38):, A Core-seizure ladder is meaningful only on a `covets_core` bloc (§6.3, WP50)., AllianceLeadershipChanged, GovernanceChanged, Core Space changed hands to a new governing alliance (§6.3, §4.2, WP49).      `c, An internal coup swapped a bloc's leader (§6.3, WP51).      `old_leader_roster`/, apply_intrigue() (+67 more)

### Community 28 - "Core Governance & Seizure"
Cohesion: 0.06
Nodes (84): Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.      BF, shortest_path(), dialogue_fingerprint(), A 16-hex-char hash of the choice-cardinality structure across all species packs., _build_game(), Load the game at `db` if it exists, else generate a fresh one there (WP12 resume, Generate a fresh universe, persist its meta, enroll player 1, and return., Reconstruct a saved game by replaying the merged command+maintenance log (§3, WP (+76 more)

### Community 29 - "Dev Patch Tooling"
Cohesion: 0.06
Nodes (43): build_graph(), Build the warp graph and return its adjacency plus the region groups., assign_spiral_spatial_ids(), Assign the spiral's contiguous display sequence beginning at ``S10001``.      Un, one_way_exits(), Targets reachable from `sector_id` with no return edge (sorted, deterministic)., _big_expansive_config(), _cross_region_edges() (+35 more)

### Community 30 - "Core-Seizure Confirm Screens"
Cohesion: 0.12
Nodes (6): _assert_impl(), _assert_remote_impl(), GameClient, EncounterDTO, Protocol, The async surface every game consumer programs against (WP61).      Mirrors `Ser

### Community 31 - "Detail Table Overlay"
Cohesion: 0.05
Nodes (37): App, _cell_markup(), ColumnSpec, DetailOverlay, DetailTable, _plain(), Any, ComposeResult (+29 more)

### Community 32 - "Spacebattle Battle Screen"
Cohesion: 0.08
Nodes (10): BattleScreen, Key, Ship, Text, Keep the placement cell comfortably inside the viewport., Deploy the fleet (mode depends on scenario), then fight the IGOUGO battle., Starbase-defense scenario: the station on the board is the player's., The full main-game starbase art (`edge.art.port.PortGenerator`),         rasteri (+2 more)

### Community 33 - "Server Net & Engine Ticker"
Cohesion: 0.13
Nodes (27): HomeClusterError, Exception, A non-governing bloc could not be given a valid home cluster (§5 step 6)., BigBangError, _cluster_groups(), ClusteredTopology, ExpansiveTopology, MeshTopology (+19 more)

### Community 34 - "Market Economy & Pricing"
Cohesion: 0.09
Nodes (51): DrawFn, EconomyConfig, The Stardock latinum price for a component tier, or None if barter-only., Economy constants (DESIGN §8). All latinum figures in slips., _force_settlement(), Run one order-book settlement now (WP59 sysop op) — a logged, replayable market, clear_filled(), desired_stock_frac() (+43 more)

### Community 35 - "Devtool CLI & Sysop"
Cohesion: 0.03
Nodes (107): apply_dev_patch(), _clamp_ship_field(), DevPatchError, _expire_contract(), _moderate_notice(), _parse_component(), Exception, Ship (+99 more)

### Community 36 - "Core Rules Tests"
Cohesion: 0.09
Nodes (58): _do(), _first_filled(), _line_universe(), WP3 — command reducers over a tiny hand-built universe (DESIGN §3)., Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored., A logged coordinate lead is the map (§6.7): TravelTo its destination routes over, A lead is the map only *from where it was obtained* (§6.7): away from the origin, Player-facing route/warp errors must speak in spatial ids (§5.1), never internal (+50 more)

### Community 37 - "LLM Bot Brain & Console"
Cohesion: 0.06
Nodes (29): Brain, BotRecord, One reportable moment: reasoning / action / result / operator / status / error., LLMBotApp, ComposeResult, InstructionMode, Path, Pressed (+21 more)

### Community 38 - "Config Loading & Sidecar Merge"
Cohesion: 0.04
Nodes (79): CronFn, A text report of a generated universe (the `--stats` dev view, §5)., summarize(), list_items(), Render one category of populated universe items as an id-keyed table., _check_config_version(), _load_save(), main() (+71 more)

### Community 39 - "Base Screen Chrome & Saves"
Cohesion: 0.05
Nodes (43): The unified base view (§4.2, WP79) — one screen, state-gated tabs.      `standin, StarbaseDTO, The unified base view — identity, station ops, market, services (§4.2, WP79)., The base view for the player's current sector, if a base is present., BaseScreen, ComposeResult, Static, Vertical (+35 more)

### Community 40 - "Groundwar Battle Screen"
Cohesion: 0.09
Nodes (14): BattleScreen, MapView, Click, ComposeResult, Key, Text, Widget, Scrolling viewport over the battlefield; renders art + pieces + overlays. (+6 more)

### Community 41 - "Planet Terrain & Surface Sites"
Cohesion: 0.13
Nodes (26): Stable POC art/name subtype for a compatible production surface kind., surface_find_kind(), _blank(), _draw_beacon(), _draw_cache(), _draw_colonnade(), _draw_leviathan(), _draw_obelisk() (+18 more)

### Community 42 - "Community 42"
Cohesion: 0.03
Nodes (206): apply_resign_standing(), Mark one Core-seizure task complete in the bloc's seizure ledger (pure; WP50)., Leave the current bloc and let rival hostility lapse to neutral (§6.3, WP38)., record_seizure_task(), EconomyError, Exception, An illegal economic action (insufficient funds/goods/stock/holds)., _abandon_contract() (+198 more)

### Community 43 - "Community 43"
Cohesion: 0.04
Nodes (63): BotSetup, `edge.bot` — a TWX-style scripting harness for bots (DESIGN §14 — WP60).  Dev-ti, load_script(), main(), open_service(), Path, `edge-bot --script path.py --save game.db [--seed N] [--turns N] [--player N]` (, Import a bot script by file path (it must define `setup(bot)`). (+55 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (32): A correction clears stale validation copy and restores stable form layout., Changed, CountColumn, CountItem, CountSelector, Dropped, options_from_suits(), PlatoonComposer (+24 more)

### Community 45 - "Community 45"
Cohesion: 0.05
Nodes (42): ABC, BaseException, CronResolver, DialogueConfigMismatchError, RuntimeError, The saved ticker schedule, or None for a fresh game (WP12)., The save was made with a different dialogue pack; replay would fail mid-way., EngineState (+34 more)

### Community 46 - "Community 46"
Cohesion: 0.03
Nodes (120): EdgeApp, Any, Resize, Screen, Recompute the layout tier and apply its class across the screen stack., Push, then stamp the current tier class on the new screen (WP-UI07).          Mo, Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)., Persist local-only presentation settings and apply the theme immediately. (+112 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (21): ContactChoiceDTO, One authored player reply on a branching dialogue node (§6.7 optional branching), AlienContactScreen, ComposeResult, Widget, Re-fetch the view and repaint the conversation **in place** (§6.7).          `pi, Land focus on the new menu — the old reply rows were just removed under it., The reply menu — the one thing that really changes between nodes.          Share (+13 more)

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (45): DataObject, accrue_interest(), execute_trade(), haggle_acceptance_probability(), HaggleResult, improvement_fraction(), Random, Ship (+37 more)

### Community 49 - "Community 49"
Cohesion: 0.03
Nodes (148): BaseModel, advance_build(), building(), citadel_defense_mult(), citadel_foe(), CitadelError, conquer(), has_gun() (+140 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (41): dig_trench(), dist(), do_dig(), do_move(), do_talk(), Expedition, Explorer, generate_expedition() (+33 more)

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (32): AccountStore, AuthError, GameRecord, Exception, Path, `edge/server/accounts.py` — identity, kept out of core (WP64, H15).  DESIGN §3/§, Verify credentials and mint a session token (constant-time hash compare)., Resolve a token to its account id, or raise if unknown/expired. (+24 more)

### Community 52 - "Community 52"
Cohesion: 0.02
Nodes (126): One traversed sector on a plotted route — what the player reads (§11, WP14)., RouteHopDTO, Resize, Static, Text, Render a species' portrait image (by `roster_id`) into its allotted cell box., SpeciesPortrait, ContactReply (+118 more)

### Community 53 - "Community 53"
Cohesion: 0.10
Nodes (36): _accent_hue(), _base_cell(), _clamp8(), DiscoveryGenerator, _hex(), _horizon(), _hx(), _mix() (+28 more)

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (10): main(), PlaytestService, ComposeResult, One representative sector per place a contact can happen: the Core, then each ba, Re-key the target species + player to realise the current band / intel before a, Every artifact tier the roster barters for — one of each is enough to unlock BAR, A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7), Rewrite every reply to enabled so gated branches become traversable. (+2 more)

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (27): _hostile(), WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§1, Friendly band never rolls violence; hostile band always does; the middle     int, Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min., A multi-hop journey stops *in* the sector where a detected encounter fired —, An undetected slip-away emits EncounterEvaded and the journey continues., A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attac, The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothi (+19 more)

### Community 56 - "Community 56"
Cohesion: 0.05
Nodes (68): _alliance_key(), alliance_standing(), alliance_standing_shift(), apply_join_standing(), _clamp01(), core_bases_razed(), core_status(), governor_hostile() (+60 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (28): _compose(), _grammar_floor(), _mirror_row(), Random, Slot, Text, Expand a left-half row (centre column included) to a full symmetric row:     the, The shortest height this grammar can compose: the smallest part in each     slot (+20 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (42): Procedural ASCII art generation logic., cloud_city_art(), _cloud_city_cells(), get_atmosphere_color(), get_outline_char(), PlanetGenerator, Random, Text (+34 more)

### Community 59 - "Community 59"
Cohesion: 0.16
Nodes (5): GroundExpeditionScreen, Any, Walk, scan, excavate, and talk through authoritative survey commands., Enter means "commit the cursor": set down while inbound, march once landed., Whether the cell under the cursor is an advertised drop site.

### Community 60 - "Community 60"
Cohesion: 0.07
Nodes (38): The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only)., _computer(), _docked_port(), _encounter(), _engine_room(), observe(), EncounterDTO, Render the pilot's fog-of-war projections as a compact text observation (dev-onl (+30 more)

### Community 61 - "Community 61"
Cohesion: 0.06
Nodes (18): Any, Command, Event, Fan freshly-persisted events to the stream, filtered to this seat (the WP65 seam, Apply a command through the in-process service (events fan out via `on_events`)., Yield events as they are produced — the service pushes both apply + tick events., A `GameClient` over a websocket to `edge-server` (WP68) — the hosted-play seam., Open the socket and complete the fingerprint handshake (refuses a build mismatch (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (15): HelpScreen, Contextual how-to-play help (`?` anywhere), after `edge.tui.screens.help`., ExMapView, ExpeditionScreen, FindModal, Click, ComposeResult, Key (+7 more)

### Community 63 - "Community 63"
Cohesion: 0.07
Nodes (30): GwEmplacement, GwWeapon, A suit/garrison weapon or missile (§ ground combat)., A static defensive structure (wall/gate/turret/AA/sensor/citadel gun)., BiomeBands, feature_at(), generate_feature_grid(), Pure gameplay terrain seam for ground operations (GW-WP02).  Owns the *gameplay* (+22 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (42): Every action spent — nothing left to do this turn., Trooper, _aa_reaction_acc(), _apply_resolve(), broadcast_terms(), _check_casualties(), _check_cowed(), _command_bonus() (+34 more)

### Community 65 - "Community 65"
Cohesion: 0.03
Nodes (129): DialoguePack, _assign_region_control(), _band_disposition(), _base_for(), build_alliances(), _carve_home_clusters(), _clamp01(), _cluster_sectors() (+121 more)

### Community 66 - "Community 66"
Cohesion: 0.17
Nodes (7): Any, HeaderSelected, OptionSelected, RowSelected, Two-pane sysop dashboard: nav left, view right, audit trail below., Enter/click on a players or standings row opens its full dossier., SysopApp

### Community 67 - "Community 67"
Cohesion: 0.16
Nodes (5): ContactDTO, A peaceful alien contact screen (§6, §6.7, §11)., The alien-contact screen for a species in the player's sector (§6, WP9, WP17)., The id of the (lowest-id) species in the player's sector, or None (§6, WP9)., The contact view for the (first) species in the player's sector, if any.

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (10): ActionCatalog, ActionOutcome, Any, What executing one decision did — readable either way (ok or rejected)., Executes decisions for one pilot, via that pilot's `BotRunner`., The still-present base the pilot explicitly boarded; movement invalidates it., The sector where this pilot paid the port docking turn, while still there., The Stardock whose non-market facilities the pilot explicitly entered. (+2 more)

### Community 69 - "Community 69"
Cohesion: 0.19
Nodes (18): _discoveries(), format_route(), _ports(), Dev inspector: list populated universe contents and plot routes (CLI helpers)., Resolve two endpoints (internal or spatial id) and plot the fewest-hop route., Render one listing as a plain-text table: `title`, then a rich SIMPLE table., The spatial display id for an internal sector id, or `—` if none is cached., A sector reference as `internal/spatial` (the §5.1 dual id). (+10 more)

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (37): NpcEntry, The outcome of an NPC entering a defended sector (§10, WP-PR02).      `destroyed, Resolve `force`'s defenses against `species` drifting in (§10, WP-PR02) — pure,, resolve_npc_entry(), _force(), _make_hostile(), _mini_state(), WP41 — sector fighters, mines, beacons, black-hole hazards (§10).  Covers the pu (+29 more)

### Community 71 - "Community 71"
Cohesion: 0.07
Nodes (38): Color, available_archetypes(), available_subtypes(), Return the known subtypes for an entity type.      Lets callers (e.g. the CLI) e, Return the archetype ids that have a defined art palette.      Lets the CLI enum, planet_subtype(), port_subtype(), Style (+30 more)

### Community 72 - "Community 72"
Cohesion: 0.07
Nodes (28): AnthropicBackend, AntigravityBackend, CliBackend, _extract_json(), get_backend(), OllamaBackend, _parse_claude_envelope(), Any (+20 more)

### Community 73 - "Community 73"
Cohesion: 0.08
Nodes (18): OutEdges, Wire one group: a random spanning tree, then edges toward avg degree ~2.5., `trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra, `expansive` bridging (§5 step 2): a band-lattice web with no chokepoints., Wire one group internally as a planar outer-planar graph with zero crossings., Dense concentric rings numbered outward from sector 1.      Sector 1 has ``max_w, Partition sequential IDs into rings of size ``cap * radius``., Add increasingly long ring chords until endpoints reach the warp cap.          S (+10 more)

### Community 74 - "Community 74"
Cohesion: 0.18
Nodes (10): _band(), _num(), _owner(), _planets(), An `Ownership` as `kind` or `kind:ref` — "none" reads as the empty marker., The containing sector's distance band (how deep the object sits, §5)., The one field that matters only for this world's type: belt ore, or Cloud City s, Worlds with their inhabitants, population, and defensive/economic holdings. (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.08
Nodes (59): GwSuit, A purchasable powered-armour suit class (GW plan D3)., GroundForceDTO, LoadoutOptionDTO, One platoon-composer row — an affordance the player can actually deploy (GW-WP08, The ground force aboard, as the platoon composer sees it (GW-WP08, D3)., apply_casualties(), berths_free() (+51 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (18): Random, Style, The world you've arrived at: a big disc anchored toward the right edge,, The port — or the starbase that takes its slot (§4.2, WP80). Beside a         pl, Up to N ships riding the open sky left of the primary body, staggered by, A space find: the scene's primary body when the sector has no planet,         el, Overflow ships beyond the sprite cap (still hailable) and the roaming         En, Deployed forces as glyph-scale presence marks — fighters flying patrol         t (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.08
Nodes (20): _error(), LobbyServer, Any, Command, Event, Path, Enqueue a command and await its events — the one path that mutates state., Track a session so it receives this game's pushed events (the lobby calls it on (+12 more)

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
Cohesion: 0.11
Nodes (34): _decode_any(), Inverse of the server's `_encode_any`: unwrap DTO/event envelopes, recurse lists, _encode_any(), Wire-encode any service return value (events, DTOs, primitives, and lists thereo, decode_command(), decode_dto(), _decode_dto_body(), decode_event() (+26 more)

### Community 83 - "Community 83"
Cohesion: 0.09
Nodes (25): dotenv_value(), Path, Small stdlib-only environment loader for server operator settings.  Edge deliber, Read one shell-like `KEY=value` from a local dotenv file without mutating `os.en, Resolve CLI → process environment → local `.env` sysop-secret precedence., sysop_password(), _amain(), GameServer (+17 more)

### Community 84 - "Community 84"
Cohesion: 0.08
Nodes (25): A plotted route for the Computer's Route tab (§11, WP14).      Read-only and spa, RouteDTO, LocalClient, An embedded `GameClient` over an in-process `GameService` (WP61).      Every met, Run the embedded engine ticker until stopped (the app's engine worker, §3)., The embedded ticker (tests/shots that step it directly)., The wrapped in-process service (single-player back-compat; never used for remote, The synchronous game surface the screens read (WP61/WP68).          Single-playe (+17 more)

### Community 85 - "Community 85"
Cohesion: 0.02
Nodes (187): alliance_rivals(), attitude_locked(), attitude_offset(), decay_grudges(), effective_disposition(), grudge_shift(), One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called., The player's accumulated attitude offset toward `species` (0.0 if none yet). (+179 more)

### Community 86 - "Community 86"
Cohesion: 0.09
Nodes (34): _finalize_planets(), _host_markets(), _make_port(), _mid_stock(), _normalize_belts(), _place_starbases(), populate(), Random (+26 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (26): Brain, InstructionMode, One pilot: owns the model client, the action catalog, and the paced loop., Queue an objective change or answer-only query for the next cycle., Change the live minimum seconds/action, clamped at no artificial delay., Blocking loop; run in a worker thread. Restartable after a stop., One cycle while paused — lets the operator chat with a stopped pilot.          A, One observe→decide→act cycle. Returns True when the run should end. (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.12
Nodes (29): apply_derived(), Ship, Return `ship` with its stored aspect scalars refreshed from its subsystems., _check_slot(), _combat_action(), _combat_salvage(), _engine_ship(), _escape_pod() (+21 more)

### Community 89 - "Community 89"
Cohesion: 0.22
Nodes (3): EngineRoomDTO, The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)., _room()

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (28): Console, _archetype_paged_sheets(), banner(), _export_all_types(), main(), ArgumentParser, Namespace, Text (+20 more)

### Community 91 - "Community 91"
Cohesion: 0.12
Nodes (24): Merge a generated dialogue sidecar onto the default roster and run §13 integrity, validate_sidecar(), Backend, DebugBackend, Protocol, Generate one schema-valid JSON grammar for an authoring prompt., Wraps any backend to echo the request/response at the backend boundary to stderr, _default_out() (+16 more)

### Community 92 - "Community 92"
Cohesion: 0.13
Nodes (26): _author_dossier_other(), _author_dossier_other_branches(), _author_dossier_self(), _author_dossier_self_branches(), author_packs(), _collect_branch_targets(), grammar_schema(), _intent_brief() (+18 more)

### Community 93 - "Community 93"
Cohesion: 0.21
Nodes (18): list_portraits(), portraits_dir(), Path, Resolve the portrait directory: the default, an absolute path, or repo-root-rela, All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<e, Pick one portrait file for `roster_id`, or None if the species has none.      Wi, resolve_portrait(), The face the current species is wearing, and how many it has to choose from (PT- (+10 more)

### Community 94 - "Community 94"
Cohesion: 0.14
Nodes (24): assign_spatial_ids(), _field_digits(), Spatial sector numbering — the player-facing display id (DESIGN §5.1).  Derives, Digit width for a 1-based field whose biggest value is `largest`., Map each old sector id to a spatial id `band·region·ordinal` (DESIGN §5.1)., band_for_hops(), The band name whose [min_hops, max_hops] contains `hops`., DistanceBand (+16 more)

### Community 95 - "Community 95"
Cohesion: 0.02
Nodes (88): Container, AllianceRowDTO, One bloc on the Computer's Alliances tab (§6.3, WP38 — surfaced WP72)., next_hint(), ObjectivesStrip, Any, Static, The hint for the first objective still open ('' when all are done). (+80 more)

### Community 96 - "Community 96"
Cohesion: 0.04
Nodes (116): GameConfig, Top-level config bundle, validated from the parsed YAML mapping., §4/§10 reference integrity: every hull's `armament` ids resolve in the         `, describe_payload(), effective_sensor(), entity_codex_discovery(), entity_contactable(), is_detectable() (+108 more)

### Community 97 - "Community 97"
Cohesion: 0.08
Nodes (14): BridgedGameClient, Any, A synchronous `GameService`-shaped facade over an async `RemoteClient` (WP68)., The static shared config, loaded locally for rendering (never wired, WP68)., Owns the background asyncio loop a `RemoteClient` runs on (WP68).      The loop, Schedule `coro` on the client's loop and block until it completes (or raises)., A `GameService`-shaped synchronous facade over the connected client., An awaitable facade safe to call from Textual's loop (GW-WP07). (+6 more)

### Community 98 - "Community 98"
Cohesion: 0.14
Nodes (38): accrue_interest(), alien_drift(), _pinned_species(), Species staged at the Stardock — the hub's standing welcome; they don't wander (, Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16)., Compound interest on every non-empty bank balance (§8)., _config(), _drift_world() (+30 more)

### Community 99 - "Community 99"
Cohesion: 0.15
Nodes (23): Binding, _action_name(), _all_actions(), _bindings(), _method_source(), _pane_bindings(), Screen, WP-UI05/WP-UI06 — responsive shell and unified action discovery.  Static collisi (+15 more)

### Community 100 - "Community 100"
Cohesion: 0.10
Nodes (10): HelpScreen, ComposeResult, OptionSelected, Pressed, Screen, Compact scenario picker + a per-side fleet-composition table.      A scrolling [, Reset both columns to a scenario's designed fleet composition., Contextual how-to-play help (`?` anywhere), after `edge.groundwar.app`. (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (11): CorpActions, The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer), The int key of the highlighted row in `table_id`, or None., Run the corp verb this button names; True if it was one of ours., Charter with a derived tag, uniquifying on a tag collision (never typed)., CEO invites a captain by player id (the two-step consent join, WP66/WP76)., Accept the invite selected in the invites table (or the only one)., CEO expels the roster member selected in the roster table. (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.09
Nodes (21): ActionDescriptor, LayoutTier, Any, Enum, Screen, Shared presentation types and semantic Textual themes., Return the one canonical advertised-action list for a screen.      Danger levels, screen_actions() (+13 more)

### Community 103 - "Community 103"
Cohesion: 0.13
Nodes (27): DiscoveryPayload, What collecting a discovery yields (DESIGN §7) — a small tagged value.      `kin, ground_operation_view(), Project the player's active survey without exposing its generation identity (GW-, A full-graph lead route may cross unexplored space — fog hides its hazards., test_route_hazards_hide_unexplored_dangers(), _inhabited_view(), _landed() (+19 more)

### Community 104 - "Community 104"
Cohesion: 0.18
Nodes (13): can_warp(), The sectors reachable in one hop from `sector_id`., Whether a single direct warp `from_sector -> to_sector` is legal., warp_targets(), WP3 — movement helpers: warp legality and pathfinding (DESIGN §9).  WP14 extends, test_plan_route_hops_cost_and_one_way(), test_plan_route_is_a_valid_walk(), test_plan_route_legs_concatenates() (+5 more)

### Community 105 - "Community 105"
Cohesion: 0.07
Nodes (49): MapNodeDTO, One outbound warp — the single, information-rich warp affordance (§5.1, §11)., A one-way warp to an uncharted sector hides its destination id (PT-48): sensors, The destination as shown on the warp: the plain spatial id, or — when hidden —, A clickable sector node on the local map: its label's cell box in `rows`.      `, WarpDTO, Shared character-grid canvas and band palette for baked map/nav views (§11).  Bo, build_nav_strip() (+41 more)

### Community 106 - "Community 106"
Cohesion: 0.09
Nodes (16): Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)., first_focusable(), focus_content(), TabActivated, Widget, The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target)., Put keyboard focus on `node`'s primary control (see `first_focusable`).      Whe (+8 more)

### Community 107 - "Community 107"
Cohesion: 0.13
Nodes (8): PlanetScreen, Pressed, Build or grow the Cloud City on a gas giant (§4.2, PT-54)., Land a chosen number of carried fighters in a ground assault (§4.2, WP55)., Open the unified base view — all starbase ops live there (§4.2, WP80)., Deploy a Genesis torpedo to terraform this world (§4.2, WP10)., Open the unified transfer editor: haul goods and settle colonists (WP-PR07)., Hand-mine an asteroid belt, taking raw goods aboard (§4.2, PT-30).

### Community 108 - "Community 108"
Cohesion: 0.20
Nodes (20): DialogueIntegrityError, _is_catch_all(), _placeholders_in(), Exception, Assert the §13 dialogue-integrity invariants for a roster (raises on failure)., A roster's dialogue packs fail the §13 integrity checks., validate_dialogue(), test_humanoid_diplomat_persona_passes_dialogue_integrity() (+12 more)

### Community 109 - "Community 109"
Cohesion: 0.05
Nodes (21): LocalMapDTO, The local sector ego-graph for the Computer → Map tab (§10, §11).      `rows` ar, The local sector ego-graph from UI_MOCKUPS.md §10.      A node-and-edge graph ce, sample_map(), Bake the local map to fit `width`, overlaying the active route (§6.7/§11)., LocalMapView, Picked, Click (+13 more)

### Community 110 - "Community 110"
Cohesion: 0.09
Nodes (25): Path, Text, Species-archetype port/starbase raster selection and ANSI rendering., Return one responsive banner crop; icons remain procedural cell art., render_station_art(), station_asset(), _treatment(), PlanetSpriteSize (+17 more)

### Community 111 - "Community 111"
Cohesion: 0.12
Nodes (33): LocationRef, A pointer to a place of interest an alien may know about (DESIGN §6.7 intel)., build_species_knowledge(), _candidates(), _entity_offerable(), _is_unencountered(), _label(), pick_intel_target() (+25 more)

### Community 112 - "Community 112"
Cohesion: 0.25
Nodes (3): The Stardock tavern — rumors, the bounty board, and the noticeboard (§14, WP58)., TavernDTO, The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58).

### Community 113 - "Community 113"
Cohesion: 0.11
Nodes (35): Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialog, author_line(), AuthoringError, AuthoringRequest, build_prompt(), extend_packs(), _placeholders_in(), prune_unreachable() (+27 more)

### Community 114 - "Community 114"
Cohesion: 0.06
Nodes (70): A named cluster from generation (DESIGN §4/§5)., Region, engine_room_view(), _event_player(), event_visible_to(), format_log_line(), game_view(), market_view() (+62 more)

### Community 115 - "Community 115"
Cohesion: 0.13
Nodes (13): layout_tier(), Horizontal, Resize, Static, Stardock-model header: station exterior at left, active-service scene at right., Exterior and banner sharing one explicitly centered vertical midpoint., _StationArt, StationArtHeader (+5 more)

### Community 116 - "Community 116"
Cohesion: 0.13
Nodes (14): main(), `edge-llm-bot` — launch the Ollama pilot's console over a local save or a hosted, _extract_json(), OllamaChat, OllamaError, Any, RuntimeError, Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).  Talks to (+6 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (19): DialogueChoice, An authored **player reply** on a line entry (DESIGN §6.7, optional branching)., _gate_choice(), Gate one authored reply, greying it with a reason (§6.7).      The mechanical ac, _choice(), _dto(), _gate(), The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order (+11 more)

### Community 118 - "Community 118"
Cohesion: 0.03
Nodes (116): effective_trade_posture(), The species' trade posture as this player experiences it (§6.1/§6.2 — WP74)., apply_result(), Command, Upsert a reducer's new entities into the mutable container (sanctioned)., Validate `command` for `player_id` and return its delta + events., reduce(), Command (+108 more)

### Community 119 - "Community 119"
Cohesion: 0.26
Nodes (19): _begin(), _land(), _op(), GW-WP06 — authoritative survey actions, persistence, and reward settlement.  Dri, Set the shuttle down on the generated landing zone (GW-WP07-FU2).      Choosing, March until the explorer stands on `site` (marches halt early, so loop)., Teleport a player's explorer onto `(x, y)` — isolates dig/talk from march distan, _stand_on() (+11 more)

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (19): DevPatch sysop intervention through command queue, edge-server (authoritative game host), Single-writer command queue per open game (H14), edge-sysop live administration dashboard, JSON-RPC 2.0 versioned wire codec (server/wire.py), Golden-master rail: generate(seed)+replay(command log), Phases 5 & 4 — Depth, then Multiplayer, WP53-56 — forward bases, citadels, planetary war (+11 more)

### Community 121 - "Community 121"
Cohesion: 0.12
Nodes (9): Text, The art this panel drew last time, or None if it has never been drawn., Record `art` as this panel's latest render and hand it back for painting., remember(), remembered(), Resize, Rich `Text` is mutable and callers `stylize()` it (a derelict base dims its icon, test_remember_hands_back_copies_so_callers_may_stylize() (+1 more)

### Community 123 - "Community 123"
Cohesion: 0.17
Nodes (17): Durable save = (seed, command log, maintenance log) SQLite, Reconnect via durable event rail (events_since, H15), Phase 2 — Exploration & Discovery (the pivot), WP7 — friendly alien species & roster, WP9 — alien contact: tech barter + latinum sales, WP8 — dialogue system (config-driven, recency ring), WP5 — discovery system: rarity, sensors, codex, WP12 — durable engine maintenance (cron effects survive reload) (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.12
Nodes (25): concourse_asset(), Path, Text, Static Stardock service raster selection and ANSI rendering.  The source artwork, Return the tab, theme, and layout-specific crop., Render a responsive service panel: 72×12 wide, 56×8 standard., Compatibility wrapper for the original PT-06 asset tests., Compatibility wrapper for the original PT-06 renderer. (+17 more)

### Community 125 - "Community 125"
Cohesion: 0.16
Nodes (12): fractal_noise(), OpenSimplex, Shared procedural-noise helpers for the art generators., Sum several octaves of noise so clusters break up at multiple scales.      Layer, Random, Text, Procedural starfield generation., Per-subtype knobs turning the noise field into stars.      threshold  - noise cu (+4 more)

### Community 126 - "test_ui_black_hole.py"
Cohesion: 0.17
Nodes (11): _depletion(), ComposeResult, Static, Vertical, Keep identity, ownership, habitability, and colony state together., The classifier's one truthful orbit route: survey, assault, or orbital-only., A belt's orbital readout (§4.2, WP-PR06): a spatial feature, scanned/mined, not, A gas giant's Cloud City: what floats there, and what building more would cost. (+3 more)

### Community 127 - "Community 127"
Cohesion: 0.16
Nodes (15): expand(), grammar_strings(), Tracery realisation of dialogue grammars (DESIGN §6.7) — pure, deterministic.  A, Deterministically expand a Tracery grammar to one string (§6.7).      `rules` ar, Every authored expansion string in a grammar (for placeholder validation)., _entry_strings(), Every authored template string in an entry (variant pool + grammar expansions)., _grammar_pack() (+7 more)

### Community 128 - "Community 128"
Cohesion: 0.19
Nodes (12): `planar` bridging: connects clusters using a planar spiderweb meta-graph., add_directed(), add_ring_motifs(), carve_core(), compute_bands(), OutEdges, Random, Graph primitives, the Core carve, motifs, and distance bands (DESIGN §5).  The w (+4 more)

### Community 129 - "Community 129"
Cohesion: 0.34
Nodes (16): _cfg(), _do(), _fight_to_the_end(), Path, WP67 — attacker-driven PvP: combat, territory, outlawry (DESIGN §14, H18).  A Pv, A service with player 1 (attacker) and an injected player 2 (defender) in one fr, Fire fight rounds until the encounter clears; return every event produced (throu, test_a_kill_pods_the_defender_and_salvages_to_the_victor() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.16
Nodes (16): _dim(), _feature_colors(), _hex(), The band's authored (fg, bg) for a feature name — deliberately *not* yet     con, Pin a colour to concrete truecolor, so the terminal cannot theme it away.      N, A rich style whose foreground is legible against the background it actually gets, Push a colour toward black, keeping its hue., Terrain the shuttle cannot set down on, while inbound.      The same colours as (+8 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (11): debris_sprite(), _facings(), _hflip(), Rows, ANSI sprite sets for the space-battle POC.  Ships are multi-character sprites si, Deterministic debris scatter for a rock cell: (dx, dy, char, style)     offsets, Deterministic wreckage scatter for a debris cell — same contract as     `rock_sp, The four cardinal aspects from the two authored ones. (+3 more)

### Community 132 - "test_ui_cloud_city.py"
Cohesion: 0.43
Nodes (7): _blocker_seen_by_reducer(), _eligible_planet(), _place(), Sit the ship over `planet`, with or without a Genesis torpedo aboard., test_ineligible_type_blocker_names_the_type(), test_no_torpedo_blocker(), test_owned_world_blocker()

### Community 133 - "Community 133"
Cohesion: 0.19
Nodes (14): Phase 3 — Danger (topology modes, the Entity, dialogue depth), WP31 — combat dialogue live, WP25 — combat rounds: weapons schema, arcs, escape floor, WP27 — consequences: attitude, grudges, alignment/experience, WP28 — per-contact dialogue session, WP24 — encounter core: interrupt, detection, disposition, pack, WP23 — alliance home clusters + neutral lanes, WP22 — hostile-band placement + config epoch (v3) (+6 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (14): WP38 — joinable alliances + Core law, WP49-52 — dynamic Core governance flip, Playtest tuning notes, Playtest Remediation Plan 01 (WP-PR01-12), WP-PR10 — responsive shell, status drawer, nav rose, Playtest Remediation Plan 02 (WP-PR2-01..15), WP-PR2-01 — tabbed-screen keyboard model (a tab owns its keys), WP-PR2-05 — sector-scene compositing / arrival view (+6 more)

### Community 135 - "EngineRoomDTO"
Cohesion: 0.17
Nodes (8): _Coord, The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the tw, Size a near-square R×C grid holding exactly `n` cells and list those cells in, Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visi, Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) who, Partition the grid into contiguous clusters: a deterministic central Core cluste, Number the cells 1..n cluster-by-cluster, returning the sector-id groups (Core i, Every grid-adjacent sector pair `(u, v)` with `u < v` — the only edges any mesh

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (6): MapView, Click, Widget, Scrolling viewport (in chars) over the cell board; sprites + overlays., Every cell an alive enemy gun currently bears on (arc + range) — the         mir, Background tints per placement cell: zones, ranges, wing reach, the         opti

### Community 137 - "LiveSysopService"
Cohesion: 0.11
Nodes (28): _bfs_from(), _grudge_targets(), is_trader(), movement_policy(), NpcTrade, _pick_by_distance(), plan_move(), plan_trade() (+20 more)

### Community 138 - "main"
Cohesion: 0.19
Nodes (7): One sensor contact, masked until excavation settles the real discovery (G6/G7)., SurveyContactDTO, Click, ComposeResult, Static, Scrolling server-projected viewport with mouse cursor selection., SurveyMapView

### Community 139 - "MarketDTO"
Cohesion: 0.20
Nodes (7): Any, Owns the loop thread + connected client; `service` is the sync facade., Run a client coroutine on the loop thread; block until it answers., Connect, auth (registering a fresh account when needed), and take a seat., Duck-typed `ServiceProtocol`: each method blocks on the async client twin., RemoteSession, _SyncClientFacade

### Community 140 - "Community 140"
Cohesion: 0.29
Nodes (7): edge --serve browser client (textual-serve), edge --connect remote client, Phase 1.5 — Navigation & QoL follow-ups, Gravity arrows (<< / -- / >>) numbering-independent, WP-D binary rename to edge + --serve web server, WP-E/WP-G spatial sector numbering (dual-id, UI-only display_id), TravelTo multi-hop route-locked warp

### Community 141 - "Community 141"
Cohesion: 0.14
Nodes (7): ComposeResult, Pressed, RumorModal — reveals the lead a tavern rumour just bought (WP-PR2-03 / PT-35)., RumorModal, Buy a rumour at the tavern, then reveal the lead it bought (§14, WP58; PT-35)., The tier class must be on a screen before its first layout.      It used to be s, test_a_pushed_screen_opens_at_its_final_size()

### Community 142 - "TopologyModeConfig"
Cohesion: 0.08
Nodes (15): HaggleScreen, ComposeResult, Submitted, PortScreen, ComposeResult, Fulfil the first active deliver favor targeting this dock (§6.7, WP57)., preserve_cursor(), DataTable (+7 more)

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (19): GroundwarConfig, Ground-operations balance (survey + assault), one YAML source of truth.      Fie, DeployEntry, GroundwarApp, main(), Battle, Pressed, Screen (+11 more)

### Community 144 - "trader_step"
Cohesion: 0.29
Nodes (3): Event, Route a movement interruption (§10, WP24): a violence opener pushes the, Open contact with a specific species in this sector (§6, WP9).          A hail c

### Community 145 - "test_genesis.py"
Cohesion: 0.15
Nodes (16): hourly_port_economy(), market_settlement(), The hourly port-economy tick: order-book market, or the legacy regen (§8, WP47)., The daily order-book settlement: match the book, move goods+latinum, drip purses, Advance one tick, run any now-due crons, and persist the schedule., Tick on a real-time timer until `stop()` (the asyncio task, §3)., _market_config(), A run of ticked trades (the WP12 rail) is deterministic — the same firings from (+8 more)

### Community 146 - "test_intel_contact.py"
Cohesion: 0.06
Nodes (25): _code_markup(), NavRose, Text, The central compass rose display widget., The always-visible nav rose — the sole main-screen warp affordance (§11).      A, 5 right-aligned trail lines: header, up to 3 history entries, you.          Each, 5 detail lines for the keyboard-selected warp target., Move the selection to the nearest warp in the pressed screen direction. (+17 more)

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

### Community 154 - "Community 154"
Cohesion: 0.20
Nodes (5): _landing_frames(), Key, POC camera pan: the cursor rides with the viewport., The shuttle falling onto `(x, y)`: descent, plume, then the explorer standing th, Clear the overlay and stop the clock — also the skip path, so a keypress during

### Community 155 - "market_view"
Cohesion: 0.25
Nodes (3): LeadDTO, A coordinate tip the player has accepted (§6.7), as a plottable Computer/Map row, The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7).

### Community 156 - ".compose"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 157 - "Ticker"
Cohesion: 0.29
Nodes (3): CorpDTO, The player's corporation — roster, bank, holdings, wars (§4, WP66). None ⇒ no co, The player's corporation for the `T` screen — roster, bank, holdings, wars (§4,

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
Cohesion: 0.29
Nodes (3): HaggleQuote, A read-only read on a counter-offer before the player commits it (§8).      `fai, An advisory read on a counter-offer for the docked port (§8). Commits nothing.

### Community 162 - "ComputerDTO"
Cohesion: 0.31
Nodes (12): _drop_entity(), _inject(), _knows_a_far_discovery(), Phase-4 — the intel "map" mechanic end to end through the reducers (DESIGN §6.7), Log-coordinates is a reply on the offer_coordinates node, not the greeting — you, Remove the roaming Entity so a test can isolate the regular coordinate-tip mecha, Point the species' knowledge at a real, reachable, unexplored rare+ discovery., test_accept_lead_without_a_tip_is_rejected() (+4 more)

### Community 163 - "TavernDTO"
Cohesion: 0.29
Nodes (3): MarketDTO, The order-book market for the Computer's Market tab (§8, WP48).      Fog-respect, The order-book Market tab: explored ports' open books + last settlement (§8, WP4

### Community 164 - "test_sig_corpus.py"
Cohesion: 0.29
Nodes (3): Fog-safe live survey view consumed by local and remote clients (GW-WP07).      O, SurveyExpeditionDTO, The active survey's fog-safe viewport, or ``None`` while in orbit (GW-WP07).

### Community 165 - ".apply"
Cohesion: 0.21
Nodes (4): PlaytestControls, Click, The dial board (`c`): focusable rows that flip the harness sim state in place., Step the focused dial (left/right). A toggle flips whichever way you push it.

### Community 166 - "Community 166"
Cohesion: 0.36
Nodes (7): Image, _aspect_crop(), build(), Path, Cut generated archetype sheets into responsive port/starbase UI assets.  Source, Centered crop to pixel ratio (already corrected for terminal cell geometry)., _save_sizes()

### Community 167 - "InterventionForm"
Cohesion: 0.16
Nodes (7): FormField, InterventionForm, Pressed, Session, Submitted, One labelled input on an intervention form., A small validated form; dismisses with the field values, or None on cancel.

### Community 168 - "test_ui_sector_view.py"
Cohesion: 0.38
Nodes (7): deposit(), Move latinum on-hand into the bank (no negative on-hand balance)., Move latinum from the bank to on-hand (no negative bank balance)., withdraw(), _bank(), test_banking_error_paths(), test_deposit_withdraw_conserve_total_and_reject_overdraw()

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (6): groundwar_default.yaml (ground balance), Citadels and orbital assault ladder, Ground operations (survey & assault), Ground Operations Integration Plan, Ground-war POC (edge-groundwar), Planetary Resolve meter (surrender not extermination)

### Community 170 - "Community 170"
Cohesion: 0.47
Nodes (6): Ordinary-port archetype artwork provenance, scripts/build_station_archetype_art.py, Chafa/Pillow ANSI raster conversion seam, OpenAI built-in image generation tool, Orbital-starbase archetype artwork provenance, Stardock service artwork provenance

### Community 171 - "_line_state"
Cohesion: 0.33
Nodes (10): _line_state(), A 1-2-3-4-5 chain (all Frontier, non-Core) with the player at `player_sector`., _sp_rid(), test_coward_diverges_over_the_drift_timeline(), test_coward_moves_away_from_the_player(), test_hunter_moves_toward_a_grudged_player(), test_hunter_without_a_grudge_just_drifts(), test_patrol_prefers_the_home_band() (+2 more)

### Community 172 - "_SpriteCard"
Cohesion: 0.25
Nodes (6): ComposeResult, Text, Vertical, One sprite: its key as a caption above the art.      The key is a content line (, _SpriteCard, TabPane

### Community 173 - "HaggleScreen"
Cohesion: 0.33
Nodes (3): Text, Build the immutable viewport once; cursor moves only restyle a copied cell., Drop expired flashes and return what is still lit.

### Community 174 - "Community 174"
Cohesion: 0.40
Nodes (4): Debris, One cell of drifting wreckage (graveyard scenarios). Blocks fire lines     and s, Scatter drifting-wreckage clumps across the midfield (graveyard     scenarios) —, seed_debris()

### Community 175 - "Community 175"
Cohesion: 0.50
Nodes (4): Domain-warped fractal-noise density field + radial envelope, fractal_noise multi-octave OpenSimplex sampler (edge/art/noise.py), _generate_nebula() in edge/art/discovery.py, Nebula generator fractal-noise rewrite

### Community 176 - "landing_sites"
Cohesion: 0.33
Nodes (5): Intent, is_known_context(), Dialogue **intents**, grouped by core game concept (DESIGN §6.7).  An *intent* i, Whether `context` is in the closed vocabulary, a `sig.*`, a `branch.*` namespace, One conversational beat: its concept, extra placeholders, and Phase-2 reachabili

### Community 177 - "LiveSysopService"
Cohesion: 0.33
Nodes (5): LiveSysopService, Any, Event, Blocking `apply(player_id, DevPatch)` facade over the hosted admin RPC., Apply an intervention to the authoritative live game as the target player.

### Community 178 - "_entity_world"
Cohesion: 0.50
Nodes (4): _inhabitants(), `Name (archetype)` — who they are and what kind of thing they are, in one cell., The peoples living on a world, or the empty marker for an uninhabited one., _species_label()

### Community 179 - "Community 179"
Cohesion: 0.67
Nodes (3): Species portrait prompts (EGA pixel art), EGA high-contrast palette portrait style, Species portrait roster (Terran, Vesk, Selvani, Helot, Quill, Concordance...)

### Community 184 - "_feature_glyph"
Cohesion: 0.18
Nodes (10): GroundCellDTO, One server-projected cell in a survey viewport (GW-WP07).      The client receiv, _feature_glyph(), _glyph_ramp(), The feature's glyphs with cumulative weights (authored weights may be fractional, Draw this cell's glyph against the authored weights, deterministically.      The, The town's real open centre, as projected — not a guess (the old heuristic, Foliage reads as foliage only if the blank-weighted entries survive.      The ol (+2 more)

### Community 204 - ".active_bands"
Cohesion: 0.15
Nodes (9): The parameters specific to one `topology_mode` (DESIGN §5).      Everything a mo, Every species' `home_band` hint must name a configured distance band (§6)., Per-`topology_mode` config blocks, keyed by mode name (DESIGN §5 step 5).      E, The config block for the selected `topology_mode` (§5 step 5)., The distance bands for the configured `topology_mode` (§5 step 5)., TopologyModeConfig, TopologySet, The config validator enforces same band names across modes (only thresholds (+1 more)

### Community 215 - ".pricing"
Cohesion: 0.50
Nodes (3): CommodityPricing, The pricing inputs for one commodity., Per-commodity pricing inputs for the §8 stock-ratio formula.

## Knowledge Gaps
- **55 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `edge-of-the-unknown`, `build_design_pdf.sh script`, `clone_references.sh script` (+50 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Commodity` connect `Core Rules & Events Engine` to `Community 129`, `Screens, DTOs & Remote Play`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `LiveSysopService`, `Encounters & Station Archetypes`, `Domain Models & Colonizability`, `Dialogue-Pack Save Guard`, `Community 143`, `Universe Embedding & Bearings`, `TopologyModeConfig`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `test_intel_contact.py`, `UI Mockup Screenshot Harness`, `Market Orders & Regions`, `Config Schema Models`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Core-Seizure Confirm Screens`, `.rebuild_adjacency`, `Spacebattle Battle Screen`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `.state`, `Core Rules Tests`, `Community 42`, `Community 43`, `Community 45`, `Community 48`, `Community 49`, `Community 52`, `Community 56`, `Community 61`, `Community 63`, `Community 65`, `Community 68`, `Community 73`, `Community 75`, `.active_bands`, `Community 77`, `Community 76`, `Community 79`, `Community 83`, `Community 84`, `Community 85`, `Community 86`, `.pricing`, `Community 94`, `Community 96`, `Community 98`, `Community 103`, `Community 106`, `Community 109`, `Community 110`, `Community 111`, `Community 114`, `Community 117`, `Community 118`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Why does `GameConfig` connect `Community 96` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Aliens & Alliance Admission`, `Computer Screen & Alliances Tab`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `LiveSysopService`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `TUI Screen Widgets`, `Subsystem Layouts & Ownership`, `test_genesis.py`, `Community 147`, `Market Orders & Regions`, `Config Schema Models`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Core-Seizure Confirm Screens`, `.rebuild_adjacency`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `.apply`, `Config Loading & Sidecar Merge`, `Community 42`, `Community 43`, `Community 45`, `Community 49`, `Community 54`, `Community 56`, `Community 61`, `Community 65`, `Community 70`, `Community 71`, `Community 73`, `Community 75`, `.active_bands`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 98`, `Community 103`, `Community 114`, `Community 118`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `UniverseState` connect `TUI Screen Widgets` to `Core Rules & Events Engine`, `Sector Scene & Widgets`, `Standing, Corp & Combat Rules`, `Aliens & Alliance Admission`, `Disposition Bands & Ship Classes`, `Planet & Orbit Views`, `LiveSysopService`, `Domain Models & Colonizability`, `Universe Embedding & Bearings`, `The Entity & Command Reduce`, `test_genesis.py`, `Subsystem Layouts & Ownership`, `Market Orders & Regions`, `Signature Mechanics`, `Bigbang Aliens & Region Control`, `Core Governance & Seizure`, `Core-Seizure Confirm Screens`, `.rebuild_adjacency`, `Server Net & Engine Ticker`, `Market Economy & Pricing`, `Devtool CLI & Sysop`, `ComputerDTO`, `Core Rules Tests`, `Config Loading & Sidecar Merge`, `test_ui_sector_view.py`, `Community 42`, `Community 43`, `_line_state`, `Community 45`, `Community 48`, `Community 49`, `_entity_world`, `Community 56`, `Community 61`, `Community 65`, `Community 69`, `Community 70`, `Community 74`, `Community 75`, `SurveySettlement`, `Community 84`, `Community 85`, `Community 86`, `Community 88`, `Community 96`, `Community 98`, `Community 103`, `Community 110`, `Community 111`, `Community 114`, `Community 118`, `Community 119`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `UniverseState` (e.g. with `Commodity` and `Component`) actually correct?**
  _`UniverseState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 142 inferred relationships involving `GameConfig` (e.g. with `HomeClusterError` and `BigBangError`) actually correct?**
  _`GameConfig` has 142 INFERRED edges - model-reasoned connections that need verification._
- **Are the 353 inferred relationships involving `Commodity` (e.g. with `BigBangError` and `ClusteredTopology`) actually correct?**
  _`Commodity` has 353 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `reduce()` (e.g. with `._dock()` and `._salvage()`) actually correct?**
  _`reduce()` has 3 INFERRED edges - model-reasoned connections that need verification._