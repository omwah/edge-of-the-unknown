"""Example bot: buys a platoon, drops on a hostile world, and fights it to a decision
(GW-WP13, rewritten GW-WP23).

Demonstrates driving a tactical ground assault end to end through the public service
surface: hire recruits and buy suits/ordnance at a Stardock, find the nearest
droppable Assault-access world, land the platoon, breach the capital, and dictate
terms. The operation's own retrieval clock forces a decision (win/loss/timeout), so
this driver never needs its own stuck-detection the way the survey bot does. Run with:

    edge-bot --script edge/bot/scripts/assaulter.py --save /tmp/assault.db

**Why this is not the simplest possible bot (GW-WP23, D20).** It is the instrument the
balance verdict is read through — GW-WP22 built the spectator so a human could watch a
run and judge the world's difficulty, and a bot that plays badly makes that judgement
impossible: every seed reads "too hard" whether or not it is. Its predecessor stalled
at range 14-16 and never entered a city, so four seeds x two citadel levels produced
four identical rows. Three faults caused that, all fixed here:

1. **Fire outranked closing unconditionally.** The old policy fired whenever anything
   at all was fireable, so the platoon advanced only while nothing was in range and
   froze the moment contact was made. Now a trooper out of position shoots only what
   blocks or threatens the approach (D21).
2. **Fire was spread across every wall cell.** `min(proj.fireable)` picked the
   lexicographically smallest cell each turn, so damage scattered over the whole wall
   and no segment ever fell. Now the platoon concentrates on **one** breach target and
   keeps hitting it until it drops (D22) — the single change that most decides whether
   a run reaches the objective.
3. **Everyone played the same.** Suits differ sharply (a marauder's `structure_mult`
   is what breaks walls; only a command suit has `broadcast_range`), so one policy for
   all of them wasted the platoon. Roles now diverge (D20).

The squad mix is config (`groundwar.bot.squad`, D23) rather than hard-coded, because
composition is itself one of the levers being judged.

**GW-WP30: three of eight troopers were not playing.** Tallying actions per trooper
across seeds showed the default `4 marauder / 3 scout / 1 command` squad spending ~180
actions on marauders, 1-20 on all three scouts together, and **zero** on Command in
every seed measured. So every balance number since GW-WP24 was read off an instrument
fielding half its platoon — without the scout recon and missile-spotting the D27 line
depends on, and without the Command aura. Three coupled faults, all fixed here:

1. **Command was born inside its own hold ring.** It held at `broadcast_range - 1` (13)
   from the objective's near face, and the drop ring starts ~12 cells out, so it was
   never `adrift` and never took a step. It now keeps station on the marauder pack
   (`_move_goal`), with the no-entry rule it actually needs moved to `_advance_cell`.
2. **The scout leash was a freeze.** Over-leash a scout issued no move at all and waited
   for a pack that, being on the attack, only ever got farther away. It now closes back
   on its escort (`_scout_regroup`).
3. **Turn order made fault 2 certain.** The driver acts once and returns, so id-ordering
   let each marauder spend its whole turn before the next trooper was considered and the
   scouts were reached only after the full pack advance — sampling the leash at its
   widest, every turn. Ordering now round-robins on actions remaining.
"""

from __future__ import annotations

import math

from edge.bot.runner import BotRunner
from edge.core.config import GameConfig, GwSuit
from edge.core.enums import PortClass
from edge.core.groundwar.access import Assault, ground_access
from edge.core.groundwar.assault import (
    AssaultCity, AssaultMap, AssaultStructure, assault_map_for, tactical_projection,
)
from edge.core.groundwar.models import AssaultOperation, AssaultTrooper
from edge.core.models import Planet, Ship, UniverseState
from edge.core.rules import (
    BeginAssault, BuySuits, CombatAction, Dock, EndGroundTurn, ExtractGroundOperation,
    GroundBroadcast, GroundDrop, GroundFire, GroundJump, GroundMove, HireRecruits,
    TravelTo, Warp,
)

Vec = tuple[int, int]

# Structures worth shooting while still outside the objective (D21): what stands in the
# way, and what shoots back. Deliberately excludes buildings and sensors — plinking
# those from the approach is exactly the time-wasting the old policy fell into.
_APPROACH_TARGETS = frozenset({"wall", "gate", "turret", "aa", "citadel_gun"})
# Never shot, at any range, in any position. `resolve.civilian_building_destroyed` is
# filed under *Backfire* in the config: levelling a civilian block **adds** 4 Resolve and
# hardens the defenders toward their 120 cap, while every legitimate target drains it. It
# also costs `settlement.civilian_alignment_penalty` and kills civilians outright. A
# free-fire rule that merely picked the nearest target hit houses constantly — a city is
# mostly houses — so the bot spent its best actions raising the number it was trying to
# lower, and traces showed Resolve climbing (100→102) during "successful" assaults.
_NEVER_TARGET = frozenset({"building_civilian"})
# Structures a breach can be forced through. Gates are cheaper (60hp vs 80) but the wall
# is reachable anywhere along the perimeter; both are tried, nearest-first.
_BREACHABLE = frozenset({"wall", "gate"})
# What a trooper *inside* the objective is there to kill. A city interior is mostly wall
# and house, so this is the set that makes the difference between working the objective
# and demolishing scenery.
_PAYLOAD_TARGETS = frozenset({
    "citadel_gun", "aa", "turret", "sensor", "building_military"})
# GW-WP29 (D40 measurement pass): how far a scout may range ahead of the nearest live
# marauder before it stops closing and waits. Found by tracing full-platoon losses on
# the GW-WP26/27 board — a scout was the first casualty in every one, consistently
# dying turns before any marauder made contact. A scout's move (6) and jump_range (10)
# comfortably outpace a marauder's (3/8), and its whole value — `recon_radius: 16`
# ignoring line of sight, `spot_missile_bonus` — needs no proximity to anything at all,
# so nothing in its own tactics is what sent it ahead alone. It was simply running the
# same "close on the goal" logic as every other role on a board large enough that the
# gap this opens is now lethal before marauder support ever arrives.
_SCOUT_LEASH = 6


def _role(suit: GwSuit) -> str:
    """Read a suit's role off its own capabilities, not its id.

    Keys off what the config actually grants so a roster that renames or adds a class
    still resolves: only a command suit can `broadcast`, and the scout is the one
    carrying a jammer. Everything else fights as a breacher.
    """
    if suit.broadcast_range > 0:
        return "command"
    if suit.jam_radius > 0:
        return "scout"
    return "marauder"


def _scout_regroup(
    trooper: AssaultTrooper, op: AssaultOperation, config: GameConfig,
) -> Vec | None:
    """Where a scout that has outrun its escort should head to rejoin it, or None.

    Returns the nearest **live** marauder's cell once that marauder is farther than
    `_SCOUT_LEASH` away; None while the scout is inside the leash (go about your
    business) or when no marauder survives (no pack left to rejoin, so it goes on alone).

    GW-WP30: this replaces `_scout_should_hold`, which was a *freeze* rather than a
    leash. Over-leash it returned True, which cleared `adrift`, which meant the scout
    issued no move at all — and its docstring's assumption that a held scout "resumes
    moving on its own the moment it is back in leash" never came true, because the pack
    it was waiting for is advancing on a fixed objective and only ever gets farther away.
    A trace of the GW-WP26/27 board showed every scout tripping the leash on turn 1 and
    standing still for the remaining twenty-three, so the platoon fought the whole
    operation without the `recon_radius`/`spot_missile_bonus` the D27 silence-the-AA line
    is built on. Closing on the escort keeps the original intent — a scout is never out
    alone — while leaving it a way back into formation.

    Distance is Manhattan, not the Euclidean `_dist` used for range checks elsewhere
    in this module — deliberately: it over-reports how far the scout has run ahead,
    so the leash trips a little early rather than a little late. Tightening it to
    Euclidean would let the scout drift slightly farther before regrouping, which is
    the wrong direction to be wrong in.
    """
    nearest: Vec | None = None
    best: int | None = None
    for m in op.platoon:
        if m.hp <= 0 or _role(config.groundwar.suits[m.suit_id]) != "marauder":
            continue
        gap = abs(trooper.x - m.x) + abs(trooper.y - m.y)
        if best is None or gap < best:
            best, nearest = gap, (m.x, m.y)
    if best is None or best <= _SCOUT_LEASH:
        return None
    return nearest


def _pack_centroid(op: AssaultOperation, config: GameConfig) -> Vec | None:
    """The live marauder pack's centre of mass — what the command suit keeps station on.

    Centroid rather than nearest marauder, because what Command projects is an *area*
    (`command_radius`): standing on the middle of the pack covers the most of it. None
    when no marauder is left, which drops Command back to its own broadcast-range goal.
    """
    pack = [t for t in op.platoon if t.hp > 0
            and _role(config.groundwar.suits[t.suit_id]) == "marauder"]
    if not pack:
        return None
    return (sum(t.x for t in pack) // len(pack), sum(t.y for t in pack) // len(pack))


def _pick_planet(state: UniverseState, player_id: int, config: GameConfig) -> Planet | None:
    """A droppable Assault-access world in already-charted space (`TravelTo`-reachable)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    known = player.explored_sectors | {ship.sector_id}
    candidates = []
    for planet in state.planets.values():
        if planet.sector_id not in known:
            continue
        access = ground_access(state, player, planet, config)
        if isinstance(access, Assault) and access.droppable:
            candidates.append(planet)
    return min(candidates, key=lambda p: p.id) if candidates else None


def _stardock_sector(state: UniverseState) -> int | None:
    return next(
        (p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)


def _squad_plan(config: GameConfig) -> dict[str, int]:
    assert config.groundwar is not None
    return {sid: n for sid, n in sorted(config.groundwar.bot.squad.items()) if n > 0}


def _ensure_loadout(b: BotRunner, state: UniverseState, config: GameConfig) -> bool:
    """Buy one missing loadout ingredient per call. Returns True once ready to drop.

    Fills the configured mix (D23) instead of buying `next(iter(suits))` six times, which
    made role-differentiated play impossible to express. An unaffordable class is not
    fatal: the bot drops with whatever it did manage to buy, so a poor purse shows up as
    a weaker platoon in the watched run rather than as a bot that refuses to play.
    """
    player = state.players[b.player_id]
    ship = state.ships[player.ship_id]
    plan = _squad_plan(config)
    if not plan:
        b.stop()
        return False
    wanted = sum(plan.values())
    if all(ship.suits.get(sid, 0) >= n for sid, n in plan.items()) and ship.recruits >= wanted:
        return True
    sector = _stardock_sector(state)
    if sector is None:
        b.stop()
        return False
    # The configured mix is a *goal*, not a precondition, and the difference matters:
    # a universe can make it unreachable (recruit capacity below the squad size, a thin
    # purse), and a bot that treats an unreachable goal as "not ready yet" oscillates
    # forever — travel to Stardock, fail to buy, warp off hunting a world, travel back.
    # A run that did exactly this burned all 160 ticks on 80 warps and 80 travels without
    # ever opening an operation. So: once armed at all, only detour to a Stardock while
    # actually standing in one.
    if ship.suits and ship.recruits > 0 and ship.sector_id != sector:
        return True
    if ship.sector_id != sector:
        if not b.apply(TravelTo(to_sector=sector)):
            b.stop()
        return False
    if b.current_port() is None:
        b.apply(Dock())
        return False
    owned = sum(ship.suits.values())
    for suit_id, count in plan.items():
        have = ship.suits.get(suit_id, 0)
        if have >= count:
            continue
        if b.apply(BuySuits(suit_id=suit_id, count=count - have)):
            return False
        if owned:
            break  # can't afford this class — go with what's already in the hold
        b.stop()  # can't afford even one suit — nothing more this script can do
        return False
    crew = min(wanted, max(1, sum(ship.suits.values())))
    if ship.recruits < crew:
        if not b.apply(HireRecruits(count=crew - ship.recruits)):
            if ship.recruits > 0:
                return True
            b.stop()
        return False
    return True


def _drop_cells(amap: AssaultMap, config: GameConfig, count: int) -> list[Vec]:
    assert config.groundwar is not None
    lx, ly = amap.landing_x, amap.landing_y
    cells: list[Vec] = []
    max_radius = max(amap.width, amap.height)
    for radius in range(max_radius):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if radius > 0 and abs(dx) != radius and abs(dy) != radius:
                    continue
                x, y = lx + dx, ly + dy
                if not (0 <= x < amap.width and 0 <= y < amap.height):
                    continue
                if (x, y) in amap.blocked:
                    continue
                tc = config.groundwar.terrain.get(amap.feature[y][x])
                if tc is not None and tc.move_cost <= 0:
                    continue
                if (x, y) not in cells:
                    cells.append((x, y))
                if len(cells) >= count:
                    return cells
    return cells


def _choose_drop(
    ship: Ship, amap: AssaultMap, config: GameConfig
) -> tuple[tuple[str, int, int], ...]:
    assert config.groundwar is not None
    ceiling = min(ship.recruits, config.groundwar.max_troopers)
    suit_ids: list[str] = []
    for suit_id, owned in sorted(ship.suits.items()):
        for _ in range(owned):
            if len(suit_ids) >= ceiling:
                break
            suit_ids.append(suit_id)
        if len(suit_ids) >= ceiling:
            break
    if not suit_ids:
        return ()
    cells = _drop_cells(amap, config, len(suit_ids))
    n = min(len(suit_ids), len(cells))
    return tuple((suit_ids[i], *cells[i]) for i in range(n))


def _alive(op: AssaultOperation, s: AssaultStructure) -> bool:
    return op.structure_hp.get(s.id, s.hp_max) > 0


def _target_city(amap: AssaultMap, op: AssaultOperation) -> AssaultCity:
    """The capital while it stands, since broadcasting over it is how a raid is won."""
    open_cities = [c for c in amap.cities if c.id not in op.cowed_cities]
    if not open_cities:
        return amap.cities[0]
    return next((c for c in open_cities if c.is_citadel), open_cities[0])


def _centroid(platoon: tuple[AssaultTrooper, ...]) -> Vec:
    live = [t for t in platoon if t.hp > 0]
    if not live:
        return (0, 0)
    return (sum(t.x for t in live) // len(live), sum(t.y for t in live) // len(live))


def _breach(
    amap: AssaultMap, op: AssaultOperation, city: AssaultCity,
) -> AssaultStructure | None:
    """The single perimeter structure the whole platoon is working on (D22).

    Concentration is the point. Damaged candidates sort first, so once a segment has
    been hit the platoon keeps hitting *that* one until it falls instead of drifting to
    whichever cell happens to sort lowest — the specific defect that held the old bot
    to ~1.6 Resolve per turn while it chipped an entire wall evenly and breached none
    of it.

    Returns None once anyone is through, which is the signal to stop breaching. Without
    that check the platoon simply starts on the *next* nearest wall segment — a city
    perimeter never runs out of them — and a GW-WP23 trace showed exactly that: nine
    different wall segments picked over twenty-four turns, several actually destroyed,
    and the objective never entered.
    """
    if any(t.hp > 0 and city.inside(t.x, t.y) for t in op.platoon):
        return None
    cx, cy = _centroid(op.platoon)
    best: tuple[int, int, int] | None = None
    chosen: AssaultStructure | None = None
    for s in amap.structures:
        if s.city_id != city.id or s.kind not in _BREACHABLE or not _alive(op, s):
            continue
        damaged = 0 if op.structure_hp.get(s.id, s.hp_max) < s.hp_max else 1
        key = (damaged, abs(s.x - cx) + abs(s.y - cy), s.id)
        if best is None or key < best:
            best, chosen = key, s
    return chosen


def _target_value(
    amap: AssaultMap, op: AssaultOperation, config: GameConfig, cell: Vec, actor: Vec,
    *, inside: bool = False,
) -> float | None:
    """How much this cell is worth shooting, or None if it must not be shot.

    Ranked by the Resolve each kill actually drains **per shot it takes to get there**,
    not per kill. Per-kill ranking already put walls last, but not nearly far enough
    down: a wall segment pays 2 Resolve for 200hp, which at a marauder's 56 damage
    against structures is four actions for half a point apiece, against three points a
    shot for a sensor or a military block. Dividing by the shots a kill costs is what
    makes that six-to-one gap visible to the chooser, and it is why lowering
    `resolve.wall_breached` cannot fix wall-plinking: walls are already bottom of the
    order, and demoting last place changes no decision.

    Garrison units get a proximity bump on top: a shooter three cells away is doing
    damage now, and a platoon that walks past live infantry to plink a distant sensor
    gets wiped.

    `inside` refuses walls outright. Within the objective they are never worth an action
    — the perimeter is already breached, interior segments block line of sight rather
    than the advance, and a trooper that shoots the wall in front of it instead of
    walking around it burns the retrieval clock at 0.5 Resolve a turn. Refusing the
    shot leaves the trooper `adrift` and it closes on something that matters instead.
    """
    assert config.groundwar is not None
    r = config.groundwar.resolve
    for u in op.garrison_units:
        if (u.x, u.y) == cell and u.hp > 0:
            near = abs(u.x - actor[0]) + abs(u.y - actor[1]) <= 3
            return r.garrison_killed + (4.0 if near else 0.0)
    # GW-WP25: ask the map what stands on the cell rather than scanning for an exact
    # anchor match. An anchor comparison silently returns None for every cell of a
    # footprint except its north-west corner — and None here means "must not shoot",
    # so the bot would refuse to fire at most of any building it could see.
    s = amap.structure_at(*cell)
    if s is not None and _alive(op, s):
        if s.kind in _NEVER_TARGET or (inside and s.kind in _BREACHABLE):
            return None
        value = {
            "citadel_gun": r.citadel_gun_destroyed, "aa": r.aa_destroyed,
            "turret": r.turret_destroyed, "sensor": r.sensor_destroyed,
            "building_military": r.military_building_destroyed,
            "wall": r.wall_breached, "gate": r.wall_breached,
        }.get(s.kind, 0.0)
        return value / _shots_to_kill(config, s)
    return None


def _shots_to_kill(config: GameConfig, s: AssaultStructure) -> float:
    """Roughly how many actions this structure costs, in marauder rifle shots.

    A nominal shooter, not the actual one: the point is the *ratio* between target kinds,
    and that ratio barely moves with who is holding the trigger. Keeping it nominal also
    keeps the ordering stable across a mixed platoon, so two troopers looking at the same
    two targets agree on which to shoot.
    """
    assert config.groundwar is not None
    suits = config.groundwar.suits
    ref = suits.get("marauder") or next(iter(suits.values()))
    per_shot = max(1.0, ref.weapon.damage * ref.weapon.structure_mult)
    return max(1.0, s.hp_max / per_shot)


def _worth_firing(
    amap: AssaultMap, op: AssaultOperation, cell: Vec, breach: AssaultStructure | None,
) -> bool:
    """D21: while out of position, shoot only what blocks or threatens the approach."""
    if breach is not None and breach.covers(*cell):
        return True
    for u in op.garrison_units:
        if (u.x, u.y) == cell and u.hp > 0:
            return True  # it is shooting back — answering it is never a waste
    s = amap.structure_at(*cell)
    if s is not None and _alive(op, s):
        return s.kind in _APPROACH_TARGETS and s.kind not in _BREACHABLE
    return False


def _hunt_goal(
    amap: AssaultMap, op: AssaultOperation, city: AssaultCity, trooper: AssaultTrooper,
) -> Vec | None:
    """The nearest thing inside the objective actually worth walking to.

    "Head for the city centre" was the old inside-goal, and it is the other half of the
    wall-plinking problem: a trooper standing on the centre is not `adrift`, so it stops
    moving and shoots whatever is in line of sight — in a built-up interior, a wall.
    Aiming at live emplacements and garrison instead keeps it closing on Resolve until
    there is none left to take.
    """
    best: tuple[int, int, int] | None = None
    goal: Vec | None = None
    for u in op.garrison_units:
        if u.hp <= 0 or not city.inside(u.x, u.y):
            continue
        key = (abs(u.x - trooper.x) + abs(u.y - trooper.y), u.y, u.x)
        if best is None or key < best:
            best, goal = key, (u.x, u.y)
    for s in amap.structures:
        if s.city_id != city.id or s.kind not in _PAYLOAD_TARGETS or not _alive(op, s):
            continue
        # Walk to the *nearest* cell of the footprint, not its anchor: heading for the
        # far corner of a depot walks past the near face you could already be shooting.
        for cx, cy in s.cells:
            key = (abs(cx - trooper.x) + abs(cy - trooper.y), cy, cx)
            if best is None or key < best:
                best, goal = key, (cx, cy)
    return goal


def _nearest_city_cell(city: AssaultCity, at: Vec) -> Vec:
    """The cell of the city's footprint closest to `at` — its near face, in effect."""
    return (min(max(at[0], city.x0), city.x1), min(max(at[1], city.y0), city.y1))


def _move_goal(
    city: AssaultCity, breach: AssaultStructure | None, suit: GwSuit, role: str,
    *, at: Vec, inside: bool, hunt: Vec | None = None,
    pack: Vec | None = None, regroup: Vec | None = None,
) -> tuple[Vec, int]:
    """Where this role wants to be, and how close is close enough.

    Marauders and scouts head for the breach, then the city centre once through. A scout
    that has outrun its escort (`regroup`, GW-WP30) drops everything and closes back on
    it first — stopping a cell *inside* the leash rather than exactly on it, so it settles
    into formation instead of oscillating across the boundary every turn.

    Command keeps station on the **marauder pack** (`pack`), at `command_radius - 1`.
    GW-WP30: it used to hold at `broadcast_range - 1` from the city's near face, and that
    number is larger than the distance the drop ring starts at — measured across seeds,
    the landing zone sits ~12 cells off the objective against a hold of 13. So Command
    was *born* inside its own hold ring, was never `adrift`, and took zero actions in an
    entire operation. That is not merely one idle trooper: `command_move_bonus`,
    `command_acc_bonus` and `command_radius` are what the config calls the suit's primary
    reason to exist (D31), and the marauders walked out of that aura on turn 1 and never
    came back. Following the pack is what keeps the aura on the platoon it is for.

    Broadcasting still works from there — better, in fact. Following the pack only ever
    moves Command *toward* the objective, so `city_range <= broadcast_range` is satisfied
    more readily than at the old standoff, and `can_broadcast` is checked before movement
    every step regardless of where it happens to be standing.

    What D31 and GW-WP26 actually forbid — Command entering the objective — is enforced
    where it belongs, as a keep-out filter on the cells it may step to (`_advance_cell`),
    not by parking it out of usefulness. With no marauder left there is no pack to follow,
    so it falls back to the near-face standoff and waits to say the words.

    `inside` overrides the breach goal, and must: a trooper already past the wall that
    still walked toward the perimeter breach would march back *out* of the objective it
    just entered, which is precisely what an early GW-WP23 trace showed it doing.
    """
    if inside:
        return (hunt or (city.cx, city.cy)), 0
    if regroup is not None:
        return regroup, max(1, _SCOUT_LEASH - 1)
    if role == "command":
        if pack is not None:
            return pack, max(1, suit.command_radius - 1)
        return _nearest_city_cell(city, at), max(1, suit.broadcast_range - 1)
    if breach is not None:
        return (breach.x, breach.y), 1
    return (city.cx, city.cy), 0


def _advance_cell(
    reachable: frozenset[Vec], goal: Vec, *, keep_out: AssaultCity | None,
) -> Vec | None:
    """The reachable cell closest to `goal`, or None if there is nowhere to go.

    `keep_out` excludes the objective's interior — Command's hard rule (D31): it wins by
    surviving to dictate terms, so it may shadow the platoon right up to the wall but
    never through it. Applied as a filter on the *candidate cells* rather than as a check
    on the chosen one, because the goal it closes on is the marauder pack and the pack is
    very often inside the city: a post-hoc rejection would cancel the move and freeze the
    suit exactly the way GW-WP30 exists to stop. If every reachable cell is inside the
    objective the filter yields, since standing still in a city is worse than moving
    through it.
    """
    cells = reachable
    if keep_out is not None:
        outside = frozenset(c for c in cells if not keep_out.inside(*c))
        if outside:
            cells = outside
    if not cells:
        return None
    return min(cells, key=lambda c: (abs(c[0] - goal[0]) + abs(c[1] - goal[1]), c))


def _live_aa(
    amap: AssaultMap, op: AssaultOperation, city: AssaultCity,
) -> list[AssaultStructure]:
    return [s for s in amap.structures
            if s.city_id == city.id and s.kind == "aa" and _alive(op, s)]


def _aa_covers(aa: list[AssaultStructure], config: GameConfig, x: int, y: int) -> bool:
    """Euclidean, because that is what the rules use (`assault._dist` is `math.hypot`).

    Manhattan here was a live bug: it over-reports distance, so cells the AA genuinely
    covers read as safe and the bot jumped into a hot umbrella on turn 0 — taking exactly
    the casualties D27's tactic exists to avoid, on the turn it was least necessary.
    A safety check must never be looser than the rule it is protecting against.

    GW-WP25: measured from the battery's **firing cell** (`ox/oy`), which is the cell
    `assault._dist` measures from. Using the anchor of a 2x2 battery would put this
    check up to a cell and a half off — in whichever direction the footprint happens
    to extend — and the same rule applies: err toward calling a cell dangerous.
    """
    assert config.groundwar is not None
    reach = config.groundwar.defenses.aa.range
    return any(math.hypot(s.ox - x, s.oy - y) <= reach for s in aa)


def _jump_into_city(
    amap: AssaultMap, op: AssaultOperation, city: AssaultCity, config: GameConfig,
    trooper: AssaultTrooper, jumpable: frozenset[Vec],
) -> Vec | None:
    """The cell to jump to, or None if jumping now would be suicide or pointless (D27).

    The intended line the whole GW-WP24 tuning is built around: stand off, missile the
    AA, then jump the wall the turn it goes quiet. So this refuses to jump while any
    live AA covers the landing cell — `point_blank_bonus` ramps AA accuracy toward the
    muzzle, and a trooper jumping into a hot umbrella is close to dead on arrival, which
    is exactly the disincentive that made jump jets dead weight before AA became
    silenceable.

    Deepest cell wins: the point of spending a charge is to clear the wall outright, not
    to shuffle up to it.
    """
    if trooper.jump_charges <= 0:
        return None
    aa = _live_aa(amap, op, city)
    inside_cells = [c for c in jumpable
                    if city.inside(*c) and not _aa_covers(aa, config, *c)]
    if not inside_cells:
        return None
    return min(inside_cells, key=lambda c: (abs(c[0] - city.cx) + abs(c[1] - city.cy), c))


def _missile_target(
    amap: AssaultMap, op: AssaultOperation, city: AssaultCity, trooper: AssaultTrooper,
    missile_targets: frozenset[Vec],
) -> Vec | None:
    """A live AA battery to spend a missile on — the thing that opens the jump window.

    Missiles are the only weapon that outranges AA (13/12 against its 12), so this is
    the one shot the platoon can take without walking into the umbrella first. Nothing
    else is worth a missile while an AA still stands.
    """
    if trooper.missiles <= 0:
        return None
    for s in _live_aa(amap, op, city):
        # Any cell of the battery is a legal aim point — a missile that hits its south
        # face kills it exactly as dead, and insisting on the anchor would pass up shots
        # the projection is offering.
        for cell in s.cells:
            if cell in missile_targets:
                return cell
    return None


def setup(bot: BotRunner) -> None:
    @bot.each_turn
    def drive(b: BotRunner) -> None:
        # A hostile space encounter en route would otherwise risk the ship (and with it
        # every recruit/suit aboard, per `_escape_pod`) — break it off first, like explorer.py.
        if b.service.encounter_view(b.player_id) is not None:
            b.apply(CombatAction(action="flee"))
            return
        state = b.service.state
        config = b.service.config
        assert config.groundwar is not None
        player = state.players[b.player_id]
        op = player.ground_operation

        if op is None:
            if not _ensure_loadout(b, state, config):
                return
            if b.game().turns < 1:
                b.stop()
                return
            planet = _pick_planet(state, b.player_id, config)
            if planet is None:
                # Nothing eligible charted yet — push into unexplored space.
                g = b.game()
                warps = g.sector.warps
                if not warps:
                    b.stop()
                    return
                target = next((w for w in warps if w.kind == "unexplored"), warps[0])
                if not b.apply(Warp(to_sector=target.sector_id)):
                    b.stop()
                return
            ship = state.ships[player.ship_id]
            if ship.sector_id != planet.sector_id:
                if not b.apply(TravelTo(to_sector=planet.sector_id)):
                    b.stop()
                return
            if not b.apply(BeginAssault(planet.id)):
                b.stop()
            return

        if not isinstance(op, AssaultOperation):
            b.stop()  # a survey op landed on this player — not this script's job
            return

        if op.outcome is not None:
            b.apply(ExtractGroundOperation(op.operation_id))
            return

        amap = assault_map_for(state, op, config)

        if not op.dropped:
            ship = state.ships[player.ship_id]
            placements = _choose_drop(ship, amap, config)
            if not placements:
                b.apply(ExtractGroundOperation(op.operation_id))
                return
            if not b.apply(GroundDrop(op.operation_id, placements)):
                b.apply(ExtractGroundOperation(op.operation_id))
            return

        city = _target_city(amap, op)
        breach = _breach(amap, op, city)

        # Command acts first: a live broadcast ends the fight outright, and spending it a
        # turn late is the most expensive mistake available.
        #
        # GW-WP30: everyone else goes round-robin — most actions remaining first — rather
        # than strictly by id. This driver returns after every single action and is
        # re-entered from the top, so an id-ordered list let the first marauder spend its
        # *whole* turn before the second was even considered, and the scouts (sorting
        # last) were only ever reached once all four marauders had made their full
        # advance. That is the worst possible moment to ask "has this scout outrun its
        # escort?", and the answer was yes on every turn from the first. Interleaving
        # samples the formation mid-advance, which is what it actually looks like.
        ordered = sorted(
            op.platoon,
            key=lambda t: (0 if _role(config.groundwar.suits[t.suit_id]) == "command" else 1,
                           -t.actions, t.id))

        for trooper in ordered:
            if trooper.hp <= 0 or trooper.actions <= 0:
                continue
            suit = config.groundwar.suits[trooper.suit_id]
            role = _role(suit)
            proj = tactical_projection(op, amap, config, actor_id=trooper.id)

            if proj.can_broadcast:
                b.apply(GroundBroadcast(op.operation_id, trooper.id))
                return

            inside = city.inside(trooper.x, trooper.y)
            # GW-WP29/WP30: a scout that has outrun its marauder escort closes back on it
            # before doing anything else. It still never jumps (a jump can reopen that gap
            # in one action, faster than walking ever could) — that stays gated on role
            # below, not on the leash, so an escorted scout cannot leap into a city either.
            regroup = (_scout_regroup(trooper, op, config)
                       if role == "scout" and not inside else None)

            # D27's line, in order: silence the battery, then jump the wall it was
            # guarding. Both outrank closing on foot — a marauder that walks toward the
            # wall instead of spending a missile is choosing the five-shot breach over
            # the one-turn entry, which is the choice this tuning exists to make wrong.
            # Firing is not gated on the leash: a missile does not break formation, so a
            # regrouping scout that somehow carries one should still take the shot.
            if not inside:
                aim = _missile_target(amap, op, city, trooper, proj.missile_targets)
                if aim is not None:
                    b.apply(GroundFire(op.operation_id, trooper.id, *aim, missile=True))
                    return
                # GW-WP29: the D27 silence-then-jump breach stays a marauder's tactic
                # (command already avoids it by holding at range). A scout's own escort
                # leash only throttles *walking* speed — one jump's `jump_range: 10`
                # clears the whole leash in a single action, so an "escorted" scout
                # could still leap alone into a city interior an escort was supposed to
                # keep it out of. Nothing about a scout's job needs it inside first: its
                # recon and missile-spotting both work from the approach.
                if role != "scout":
                    leap = _jump_into_city(amap, op, city, config, trooper, proj.jumpable)
                    if leap is not None:
                        b.apply(GroundJump(op.operation_id, trooper.id, *leap))
                        return

            hunt = _hunt_goal(amap, op, city, trooper) if inside else None
            pack = _pack_centroid(op, config) if role == "command" else None
            (gx, gy), hold = _move_goal(city, breach, suit, role, at=(trooper.x, trooper.y),
                                        inside=inside, hunt=hunt, pack=pack, regroup=regroup)
            adrift = abs(trooper.x - gx) + abs(trooper.y - gy) > hold
            # Command shadows the pack but never follows it through the wall (D31).
            keep_out = city if role == "command" and not inside else None

            # Spend the turn's *first* action closing, then shoot with the rest. Without
            # this a trooper with any target in range simply never moves again: a
            # GW-WP23 trace had one enter the capital on turn 6 and then stand on the
            # same cell for eighteen turns, firing, while the retrieval clock ran out.
            # Trading one of two actions keeps the advance honest without giving up the
            # firefight.
            if adrift and proj.reachable and trooper.actions >= config.groundwar.actions_per_turn:
                cell = _advance_cell(proj.reachable, (gx, gy), keep_out=keep_out)
                if cell is not None and cell != (trooper.x, trooper.y):
                    b.apply(GroundMove(op.operation_id, *cell, actor_id=trooper.id))
                    return

            if proj.fireable:
                if inside:
                    # In the objective: shoot what actually breaks their will, best value
                    # first. *Not* "everything standing" — civilian blocks and interior
                    # walls are both excluded outright, and among what is left a citadel
                    # gun pays about seven times a turret per action spent.
                    scored = [
                        (-value, abs(c[0] - trooper.x) + abs(c[1] - trooper.y), c)
                        for c in sorted(proj.fireable)
                        if (value := _target_value(
                            amap, op, config, c, (trooper.x, trooper.y),
                            inside=True)) is not None]
                    if scored:
                        _, _, (tx, ty) = min(scored)
                        b.apply(GroundFire(op.operation_id, trooper.id, tx, ty))
                        return
                worth = [c for c in sorted(proj.fireable)
                         if _worth_firing(amap, op, c, breach)]
                # Command never trades shots it doesn't have to; it is the win condition.
                if worth and role != "command":
                    if breach is not None and (breach.x, breach.y) in worth:
                        tx, ty = breach.x, breach.y  # concentrate (D22)
                    else:
                        # Same value ordering as inside — a turret covering the approach
                        # is worth twice what plinking the wall beside it is.
                        tx, ty = min(worth, key=lambda c: (
                            -(_target_value(amap, op, config, c, (trooper.x, trooper.y))
                              or 0.0),
                            abs(c[0] - trooper.x) + abs(c[1] - trooper.y), c))
                    b.apply(GroundFire(op.operation_id, trooper.id, tx, ty))
                    return

            if adrift and proj.reachable:
                cell = _advance_cell(proj.reachable, (gx, gy), keep_out=keep_out)
                if cell is not None and cell != (trooper.x, trooper.y):
                    b.apply(GroundMove(op.operation_id, *cell, actor_id=trooper.id))
                    return
        b.apply(EndGroundTurn(op.operation_id))
