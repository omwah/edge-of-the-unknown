# Space-battle POC — `edge-spacebattle`

A standalone proof-of-concept for a **positioning-driven, turn-based fleet
combat** mini-game, candidate replacement for the existing ship-combat
mechanism (which is stats + button presses with no skill). Built 2026-07-17 in
the same shape as `edge-groundwar`: pure `config` / `model` / `rules` under a
throwaway Textual shell, all balance in `config/spacebattle_default.yaml`,
**not integrated** with the game until it earns it by being fun.

Run it: `python -m edge.spacebattle` (or `edge-spacebattle` after an editable
reinstall picks up the new entry point).

Inspiration: the space combat of David Weber's *In Fury Born* — momentum,
long-range missile duels that can be out-run or intercepted, closing to energy
range, raking fire down a ship's axis, fighter screens.

## Interview decisions (2026-07-17)

| Question | Decision |
| --- | --- |
| Turn resolution | **Alternating sides** (IGOUGO), like groundwar |
| Missiles | **Traveling salvos** — board objects that chase their target; dodgeable, interceptable |
| Facing | **4 cardinals** (N/S/E/W, 90° rotation) — revised from 8 after the diagonal hull art proved unreadable; bearings/arcs/quadrants still resolve on full octants |
| Damage | **Facing-keyed components** — struck aspect determines what can break |
| Board | **~2–3 screens wide** — 44×22 placement cells, each 7×3 chars, scrolling |
| Mine fog | **Enemy mines hidden** until sensors paint them; own mines always visible |
| Fighters | **Endurance + roles** — fuel-limited wings that strafe, dogfight, intercept; recover to rearm |
| Enemy | **Heuristic bot** in `rules.py` |
| Movement | **Vector-lite** — velocity persists; thrust bends it (small integers) |
| Rotation | **Free 90° with a thrust**; rotating to any facing otherwise costs an action |
| Fleets | **Duel + escorts** — frigate + corvette per side |
| Naming | `edge/spacebattle`, `edge-spacebattle`, `config/spacebattle_default.yaml` |

## The mechanics

- **Placement cells** — the starfield is divided into coarse cells (7×3 chars);
  every asset occupies one cell. Sprites are a new middle-scale ANSI set
  (`sprites.py`): hulls up to 7×3 chars keyed to real ship-class ids
  (`missile_frigate`, `scout_marauder`, `battleship`), authored at E/N and
  glyph-aware-mirrored to the four cardinal facings; fighters are 3-char darts
  (which keep all 8 headings — triangles read fine diagonally). This art is
  deliberately not constrained by the sector-view art — the big art may later be
  redrawn to match it instead.
- **Two actions per ship per turn**, any mix: thrust, rotate, fire main gun,
  launch salvo, launch/recover a fighter wing, lay a mine. Fighter wings get
  their own two actions (dash / strafe / dogfight / intercept).
- **Vector-lite movement** — ships drift by their velocity at end of their
  side's turn (drift markers `+` show next-turn positions). Thrust bends the
  vector toward the cursor and includes one free 90° of facing.
- **Facing is armor and armament** — spinal guns bear dead ahead only, `ahead`
  arcs a forward wedge, turret arrays all round. Hits land on the aspect they
  arrive from: dead ahead/astern are **rakes** (config `raking_bonus`); screens
  ablate per quadrant; once a quadrant is open, hits can knock out the
  components homed there (fore: main gun + sensors, aft: drive, flanks:
  launchers) — the engine-room localized-damage idea projected onto facings.
- **Missile salvos** are board objects (`Salvo`) that chase their target a few
  cells per owner-turn until endurance runs out; each bird rolls to hit on
  arrival, degraded by target speed. Fighters alongside a salvo can intercept.
  Rebalanced after play (interview 2026-07-17, salvos overpowered): a launch
  costs the **whole turn** (`salvo_action_cost: 2`); launchers are flank mounts,
  so the target must lie **abeam or on the quarter** (octant diff 2–3 off the
  bow) — gun posture and missile posture are now different facings; every ship
  has passive terminal **point-defense** (20% per bird, 10% through a downed
  screen quadrant); `velocity_evasion` 0.04 → 0.10 so fast targets shake birds
  off; missiles fly speed 3 (was 4) with one less turn of endurance. The bot
  rotates to present its broadside before launching. Probe: the scripted
  aggressive player went from steamrolling to 12/20 prepared wins and 4/20
  ambush wins, with fights lasting 13–18 turns.
- **Mines** detonate when an enemy hull drifts onto them. Enemy mines are
  hidden until inside sensor range. In combat a mine drops only alongside the
  ship (`deploy_reach`); the full minefield picture is a peacetime luxury.
- **Rocky debris** (belt scenarios; config `rocks:` + per-scenario
  `rock_clusters`/`rock_cluster_size`) — random-walk clumps of rock cells
  seeded across the midfield, drawn with `edge/art/terrain.py`'s asteroid-belt
  vocabulary (⬢/⛬/• boulders, */⸝/./_ debris satellites, deterministic per
  cell). A rock cell blocks main-gun and fighter fire lines, destroys any
  salvo that flies onto it (cover!), and refuses ships/wings/mines as a
  station. A hull that drifts onto one ploughs through: the rock is
  pulverized, the ship stops dead, and the impact does
  `impact_base + impact_per_speed × speed` to the leading aspect (a rake, so
  ramming at speed is ruinous). The bot brakes when its vector leads into
  debris and maneuvers rather than shooting into a blocked line.
- **Drifting wreckage** (graveyard scenarios; config `debris:` + per-scenario
  `debris_clusters`/`debris_cluster_size`; added 2026-07-18) — the main game's
  space-debris sectors (wreck discovery fields, `edge/art/discovery.py`) as a
  second obstacle kind. Same random-walk clumps and the same blocking rules as
  rock (fire lines, salvo shredding, no stationing) — but it's torn hull
  plate: a hull that drifts onto it **smashes through**, taking the lighter
  `debris.impact_base + impact_per_speed × speed` hit, destroying the wreckage
  cell, and **keeping its vector**. Rocks stop you dead; wreckage costs skin —
  sometimes the short way through the graveyard is worth the scrape. Drawn as
  cold steel-grey shards over a hull-steel wash (`sprites.debris_sprite`),
  deliberately never confusable with the belt's warm regolith tans.
- **Starbase assault** (siege scenarios; added 2026-07-18) — the main game's
  way of taking control of a base, projected onto the board. The starbase is a
  `station: true` ship class with a **3×3-cell footprint** rendered with the
  **full main-game art** (`edge/art/port.py` `PortGenerator`, subtype
  `starbase`, rasterized over the footprint). It never thrusts, rotates, or
  drifts; footprint cells block movement and take fire (`Ship.cells` makes
  `ship_at`/salvo contact footprint-aware). It is **heavily defended by a
  perimeter**: an all-round main battery, ring-mounted launchers (`salvo_arc_ok`
  is always true for stations), fighter pickets pre-launched around the ring,
  guard ships at anchor, and a hidden mine ring sown at setup from its own
  `mine_stock`. Its gun damage scales with surviving components exactly like
  the main game's `assault_foe` (`0.5 + 0.5 × integrity`,
  `rules.station_integrity` ≙ `edge.core.starbases.component_integrity`).
  **Disabling reuses the §4.2 emergent-derelict rule**: the `fusion_reactor`
  keystone lives in the **aft quadrant** (the base spawns facing W, so aft is
  the far side); collapse that screen, knock the reactor out, and the base
  goes dark — *taken* by boarding parties without razing the hull. Razing it
  also wins, but leaves nothing to claim. Either way the surviving picket
  scatters (`_check_outcome` resolves the siege objective first).
- **Deployment** replaces the old deploy system, two interfaces per the brief:
  - **Prepared defense** — full peacetime pass: place ships with facings, then
    seed the whole friendly zone with mines and pre-launched fighter screens
    *without moving a ship around*; then the enemy warps in on the far edge.
    Anything placed can be picked back up (`x`) and re-placed — a ship returns
    to the roster as the pending pick with its facing kept, mines and wings
    return to stock.
  - **Ambushed on warp-in** — position and facing only, inside a small warp-in
    pocket, against an enemy already set up with pickets out and mines sown.
  - **Belt skirmish** — the prepared-defense interface fought through an
    asteroid belt: the midfield is full of rocky debris, so gun lines, missile
    lanes, and drift vectors all have to be threaded through the rubble.
  - **Ship graveyard** — the prepared-defense interface fought through
    drifting wreckage (smash-through rules above).
  - **Starbase assault** — the warp-in interface against the fortified base
    and its perimeter (guards, pickets, hidden mine ring).

- **The Basilisk kit** (*On Basilisk Station* interview, 2026-07-17) — four
  additions, one of them player-only:
  - **Gravity lance** — an optional experimental refit chosen at setup: the
    flagship trades half its missile magazine (`lance.salvo_penalty`) for a
    bow weapon that, at knife range (2 cells) through the forward wedge,
    collapses the struck quadrant's screen to zero — no hull damage. Firing
    takes the whole turn and the capacitor recharges over 3 turns. The alien
    opponents never field one. Regen makes the collapse a 2–3-turn window:
    press it or lose it.
  - **Sidewall regeneration** — screens rebuild `screen_regen` (3) per
    quadrant per own turn, but only if the hull took no damage since the last
    own turn. Standing off to let the generators catch up is a real tactic.
  - **Damage-control parties** — `u` spends the whole turn to bring one
    knocked-out component back online (the bot does this too when out of gun
    range with systems down).
  - **Stern-chase kilt** — an aft rake from dead astern against a ship fleeing
    directly away uses `kilt_bonus` (×2.0) instead of the normal rake.
  - **Recon drone** — `p` throws a one-use probe (`recon_drones` per hull,
    player-only in practice) that reveals hidden enemy mines within
    `drone.reveal_radius` of a distant cell — the ambush minefield's counter.

## POC simplifications (knowingly cheap)

- Recovering a battered wing rearms it to full strength (free repair).
- Screens don't regenerate; no per-turn power management.
- The bot never lays mines mid-fight and ignores player mines (it can blunder
  into them — that's the payoff for seeding lanes).
- One piece per cell; ship collisions are prevented by sheering off (velocity
  zeroed), not resolved as ramming.
- Salvo lock needs no sensor check; endurance is the only leash.
- The starbase's fighter pickets burn fuel like any wing and the bot never
  recovers them, so a long siege bleeds the perimeter's fighters on its own.
- A "taken" base ends the battle immediately — no boarding minigame, no
  post-capture state handed anywhere (this POC is still standalone).
- Balance smoke test: scripted aggressive player vs the bot at seed 42 wins the
  ambush scenario on turn 14 with one ship lost — untuned beyond that.

## Verdict

Awaiting playtest. If it replaces the combat mechanism, follow-ups to consider:
multiple player ships from the real game state, hull art unification, screen
regeneration/power, bot minelaying, simultaneous-plot resolution as a variant.
