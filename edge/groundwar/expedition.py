"""Expedition mode — the peaceful branch of the ground-war POC.

Same backdrop, opposite premise: a lone surveyor lands on a *friendly* world
chasing archaeology leads. Ship sensors mark general areas; the handheld
scanner's hot/cold gradient walks you into the neighborhood; disturbed-ground
clues (visible only within sight range) mark the last few cells; an explicit
dig on the exact cell is the payoff. Inhabited worlds add settlements that
resupply and hint, but push sites away from themselves.

Same contract as the battle stack: all randomness through the seeded rng owned
by `Expedition`, only this module mutates state, the UI reads and drains
`Expedition.events`. Deterministic from `(seed, planet_type, inhabited)` —
which is also the persistence key the app uses to re-mark found sites across
descents in one session.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from random import Random

from edge.groundwar.config import GroundwarConfig
from edge.groundwar.findart import FIND_KINDS, site_name
from edge.groundwar.mapgen import _terrain_grids
from edge.groundwar.model import Event, Vec

ExOutcome = str  # "complete" | "exhausted" | None

_EDGE_MARGIN = 6
_SETTLEMENT_KEEPOUT = 8  # sites never spawn this close to a settlement footprint
_LANDING_KEEPOUT = 22    # ... nor this close to the shuttle's left-middle landing zone

SETTLEMENT_NAMES = (
    "Wayrest", "Karsholm", "Lantern Flats", "Umber's Ford", "Tessene",
    "Quiet Harbor", "Millbrace", "Old Anchorage",
)


@dataclass(slots=True)
class Site:
    id: int
    kind: str
    name: str
    x: int                 # the exact dig cell — never shown until found
    y: int
    area_cx: int           # the ship-sensor general area (circle) — always shown
    area_cy: int
    area_r: int
    clues: list[Vec]       # disturbed-ground cells near the true spot
    found: bool = False
    hinted: bool = False   # a settlement narrowed this circle


@dataclass(slots=True)
class Settlement:
    id: int
    name: str
    cx: int
    cy: int
    x0: int
    y0: int
    x1: int
    y1: int
    hint_given: bool = False

    def inside(self, x: int, y: int) -> bool:
        return self.x0 < x < self.x1 and self.y0 < y < self.y1


@dataclass(slots=True)
class Explorer:
    x: int
    y: int
    supplies: int


@dataclass(slots=True)
class Expedition:
    config: GroundwarConfig
    rng: Random
    seed: int
    planet_type: str
    inhabited: bool
    feature: list[list[str]]
    art: list[list[tuple[str, str, str]]]
    blocked: set[Vec] = field(default_factory=set)   # settlement walls/buildings
    settlements: list[Settlement] = field(default_factory=list)
    sites: list[Site] = field(default_factory=list)
    dug: set[Vec] = field(default_factory=set)       # dry holes this expedition
    explorer: Explorer = field(default_factory=lambda: Explorer(0, 0, 0))
    turn: int = 1
    outcome: ExOutcome | None = None
    events: list[Event] = field(default_factory=list)
    _next_id: int = 1

    def next_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    def in_bounds(self, x: int, y: int) -> bool:
        e = self.config.expedition
        return 0 <= x < e.width and 0 <= y < e.height

    def site_at(self, x: int, y: int) -> Site | None:
        for s in self.sites:
            if (s.x, s.y) == (x, y):
                return s
        return None

    def settlement_at(self, x: int, y: int) -> Settlement | None:
        for s in self.settlements:
            if s.inside(x, y):
                return s
        return None

    def unfound(self) -> list[Site]:
        return [s for s in self.sites if not s.found]

    def log(self, kind: str, text: str, x: int = -1, y: int = -1,
            friendly: bool = True) -> None:
        self.events.append(Event(kind, text, x, y, friendly))


# --- terrain -----------------------------------------------------------------


def move_cost(exp: Expedition, x: int, y: int) -> int:
    """Entry cost on foot; 0 == impassable (hard terrain or settlement masonry)."""
    if (x, y) in exp.blocked:
        return 0
    tc = exp.config.terrain.get(exp.feature[y][x])
    return tc.move_cost if tc else 1


def dist(ax: int, ay: int, bx: int, by: int) -> float:
    return math.hypot(ax - bx, ay - by)


def reachable(exp: Expedition) -> dict[Vec, int]:
    """Dijkstra within one turn's move points from the explorer."""
    e = exp.config.expedition
    start = (exp.explorer.x, exp.explorer.y)
    best: dict[Vec, int] = {start: 0}
    heap: list[tuple[int, Vec]] = [(0, start)]
    while heap:
        cost, (x, y) = heapq.heappop(heap)
        if cost > best.get((x, y), 1 << 30):
            continue
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not exp.in_bounds(nx, ny):
                continue
            step = move_cost(exp, nx, ny)
            if step <= 0:
                continue
            nc = cost + step
            if nc <= e.move and nc < best.get((nx, ny), 1 << 30):
                best[(nx, ny)] = nc
                heapq.heappush(heap, (nc, (nx, ny)))
    del best[start]
    return best


# --- generation --------------------------------------------------------------


def _stamp_settlement(exp: Expedition, rng: Random, name: str,
                      x0: int, y0: int, w: int, h: int) -> Settlement:
    """A peaceable walled town: gates on every side, homes, a central plaza."""
    s = Settlement(id=exp.next_id(), name=name, cx=x0 + w // 2, cy=y0 + h // 2,
                   x0=x0, y0=y0, x1=x0 + w - 1, y1=y0 + h - 1)
    exp.settlements.append(s)
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            exp.feature[y][x] = "dust"
            exp.art[y][x] = (" ", "grey35", "grey15")
    gates = {(x0, s.cy), (x0 + w - 1, s.cy), (s.cx, y0), (s.cx, y0 + h - 1)}
    for x in range(x0, x0 + w):
        for y in (y0, y0 + h - 1):
            _wall_or_gate(exp, x, y, gates)
    for y in range(y0 + 1, y0 + h - 1):
        for x in (x0, x0 + w - 1):
            _wall_or_gate(exp, x, y, gates)
    for y in range(y0 + 2, y0 + h - 2, 2):  # homes on a street grid
        for bx in range(x0 + 3, x0 + w - 4, 4):
            for x in (bx, bx + 1):
                if abs(x - s.cx) + abs(y - s.cy) <= 2:
                    continue  # keep the plaza open
                exp.blocked.add((x, y))
                exp.art[y][x] = ("⌂", "navajo_white3", "grey23")
    exp.art[s.cy][s.cx] = ("◉", "bright_cyan", "grey15")  # the plaza well
    return s


def _wall_or_gate(exp: Expedition, x: int, y: int, gates: set[Vec]) -> None:
    if (x, y) in gates:
        exp.art[y][x] = ("▒", "gold3", "grey30")
    else:
        exp.blocked.add((x, y))
        exp.art[y][x] = ("█", "grey62", "grey30")


def _passable_components(exp: Expedition) -> tuple[list[list[int]], dict[int, int]]:
    """Label the 4-connected passable regions; return (labels, sizes).

    Sites and the landing must share one region, or the survey is unwinnable.
    """
    e = exp.config.expedition
    labels = [[-1] * e.width for _ in range(e.height)]
    sizes: dict[int, int] = {}
    label = 0
    for sy in range(e.height):
        for sx in range(e.width):
            if labels[sy][sx] != -1 or move_cost(exp, sx, sy) <= 0:
                continue
            stack = [(sx, sy)]
            labels[sy][sx] = label
            n = 0
            while stack:
                x, y = stack.pop()
                n += 1
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if exp.in_bounds(nx, ny) and labels[ny][nx] == -1 \
                            and move_cost(exp, nx, ny) > 0:
                        labels[ny][nx] = label
                        stack.append((nx, ny))
            sizes[label] = n
            label += 1
    return labels, sizes


def _passable_spot(exp: Expedition, rng: Random, labels: list[list[int]],
                   comp: int, *, tries: int = 200,
                   min_sep_from: list[Vec] | None = None, min_sep: float = 0.0,
                   ) -> Vec | None:
    e = exp.config.expedition
    for _ in range(tries):
        x = rng.randint(_EDGE_MARGIN, e.width - 1 - _EDGE_MARGIN)
        y = rng.randint(_EDGE_MARGIN, e.height - 1 - _EDGE_MARGIN)
        if labels[y][x] != comp:
            continue
        if any(st.x0 - _SETTLEMENT_KEEPOUT <= x <= st.x1 + _SETTLEMENT_KEEPOUT
               and st.y0 - _SETTLEMENT_KEEPOUT <= y <= st.y1 + _SETTLEMENT_KEEPOUT
               for st in exp.settlements):
            continue
        if dist(x, y, 6, e.height // 2) < _LANDING_KEEPOUT:
            continue
        if min_sep_from and any(dist(x, y, px, py) < min_sep for px, py in min_sep_from):
            continue
        return x, y
    return None


def _place_sites(exp: Expedition, rng: Random, found_ids: frozenset[int],
                 labels: list[list[int]], comp: int) -> None:
    e = exp.config.expedition
    n = rng.randint(e.sites_min, e.sites_max)
    min_sep = e.width / (n + 1)
    placed: list[Vec] = []
    kinds = list(FIND_KINDS)
    rng.shuffle(kinds)
    for i in range(n):
        spot = _passable_spot(exp, rng, labels, comp,
                              min_sep_from=placed, min_sep=min_sep) \
            or _passable_spot(exp, rng, labels, comp)
        if spot is None:
            continue
        x, y = spot
        placed.append(spot)
        # The sensor circle contains the true spot but isn't centered on it.
        while True:
            ox = rng.randint(-(e.area_radius - 3), e.area_radius - 3)
            oy = rng.randint(-(e.area_radius - 3), e.area_radius - 3)
            if math.hypot(ox, oy) <= e.area_radius - 3:
                break
        cx = max(2, min(e.width - 3, x + ox))
        cy = max(2, min(e.height - 3, y + oy))
        clues: list[Vec] = []
        for _ in range(60):
            if len(clues) >= e.clue_count:
                break
            dx = rng.randint(-e.clue_radius, e.clue_radius)
            dy = rng.randint(-e.clue_radius, e.clue_radius)
            c = (x + dx, y + dy)
            if c == (x, y) or c in clues or not exp.in_bounds(*c):
                continue
            if move_cost(exp, *c) > 0:
                clues.append(c)
        kind = kinds[i % len(kinds)]
        site = Site(id=i + 1, kind=kind, name=site_name(rng, kind), x=x, y=y,
                    area_cx=cx, area_cy=cy, area_r=e.area_radius, clues=clues,
                    found=(i + 1) in found_ids)
        exp.sites.append(site)


def _place_explorer(exp: Expedition, labels: list[list[int]], comp: int) -> None:
    """Land near the map's left-middle, but only in the sites' component —
    never in a passable pocket the finds can't be walked to from."""
    e = exp.config.expedition
    mid = e.height // 2
    for x in range(4, e.width):
        for dy in range(mid):
            for y in (mid - dy, mid + dy):
                if 0 <= y < e.height and labels[y][x] == comp:
                    exp.explorer = Explorer(x=x, y=y, supplies=e.supplies_start)
                    return
    exp.explorer = Explorer(x=4, y=mid, supplies=e.supplies_start)


def generate_expedition(
    config: GroundwarConfig, *, seed: int, planet_type: str, inhabited: bool,
    found_ids: frozenset[int] = frozenset(),
) -> Expedition:
    """A survey map: terrain, optional settlements, sensor-marked sites, one boot."""
    e = config.expedition
    rng = Random(f"{seed}|expedition|{planet_type}|{int(inhabited)}")
    exp = Expedition(config=config, rng=rng, seed=seed, planet_type=planet_type,
                     inhabited=inhabited, feature=[], art=[])
    exp.feature, exp.art = _terrain_grids(rng, planet_type, e.width, e.height)
    if inhabited:
        names = list(SETTLEMENT_NAMES)
        rng.shuffle(names)
        n = rng.randint(e.settlements_min, e.settlements_max)
        for i in range(n):
            w, h = 18, 9
            for _ in range(40):
                x0 = rng.randint(3, e.width - w - 3)
                y0 = rng.randint(3, e.height - h - 3)
                if not any(abs(x0 - st.x0) < w + 10 and abs(y0 - st.y0) < h + 6
                           for st in exp.settlements):
                    _stamp_settlement(exp, rng, names[i % len(names)], x0, y0, w, h)
                    break
    # After settlements: their walls shape passability, so components come last.
    labels, sizes = _passable_components(exp)
    comp = max(sizes, key=lambda k: sizes[k])
    _place_sites(exp, rng, found_ids, labels, comp)
    _place_explorer(exp, labels, comp)
    exp.log("info", f"Survey shuttle down. {len(exp.sites)} sensor contact(s) "
                    f"marked from orbit — the circles are approximate.")
    return exp


# --- play --------------------------------------------------------------------


def scanner_reading(exp: Expedition) -> tuple[str, Site | None]:
    """The handheld gradient: a banded reading against the nearest unfound site."""
    sites = exp.unfound()
    if not sites:
        return "all contacts resolved", None
    p = exp.explorer
    near = min(sites, key=lambda s: dist(p.x, p.y, s.x, s.y))
    d = dist(p.x, p.y, near.x, near.y)
    for band in exp.config.expedition.scanner:
        if d <= band.within:
            return band.label, near
    return "no signal", near


def visible_clues(exp: Expedition) -> set[Vec]:
    """Disturbed ground you are close enough to notice."""
    e = exp.config.expedition
    p = exp.explorer
    out: set[Vec] = set()
    for s in exp.unfound():
        for c in s.clues:
            if dist(p.x, p.y, *c) <= e.sight:
                out.add(c)
    return out


def _spend(exp: Expedition, n: int) -> None:
    exp.explorer.supplies = max(0, exp.explorer.supplies - n)
    if exp.explorer.supplies <= 0 and exp.outcome is None:
        exp.outcome = "exhausted"
        exp.log("outcome", "Supplies spent — the shuttle recalls you to orbit. "
                           "What you found stays found.", friendly=False)


def path_to(exp: Expedition, x: int, y: int) -> list[Vec] | None:
    """Cheapest walking path (excluding the start cell), over the whole map."""
    if not exp.in_bounds(x, y) or move_cost(exp, x, y) <= 0:
        return None
    start = (exp.explorer.x, exp.explorer.y)
    if (x, y) == start:
        return None
    best: dict[Vec, int] = {start: 0}
    prev: dict[Vec, Vec] = {}
    heap: list[tuple[int, Vec]] = [(0, start)]
    while heap:
        cost, (cx, cy) = heapq.heappop(heap)
        if (cx, cy) == (x, y):
            break
        if cost > best.get((cx, cy), 1 << 30):
            continue
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if not exp.in_bounds(nx, ny):
                continue
            step = move_cost(exp, nx, ny)
            if step <= 0:
                continue
            nc = cost + step
            if nc < best.get((nx, ny), 1 << 30):
                best[(nx, ny)] = nc
                prev[(nx, ny)] = (cx, cy)
                heapq.heappush(heap, (nc, (nx, ny)))
    if (x, y) not in prev:
        return None
    path: list[Vec] = []
    cell = (x, y)
    while cell != start:
        path.append(cell)
        cell = prev[cell]
    path.reverse()
    return path


def do_move(exp: Expedition, x: int, y: int) -> bool:
    """March toward the cell — one supply per turn, however many turns it takes.

    The march halts early if supplies run out, or if previously unseen disturbed
    ground comes into sight along the way (no walking blindly past the prize).
    """
    if exp.outcome is not None:
        return False
    path = path_to(exp, x, y)
    if path is None:
        return False
    e = exp.config.expedition
    seen = visible_clues(exp)
    turns = 0
    i = 0
    while i < len(path) and exp.outcome is None:
        budget = e.move
        while i < len(path):
            step = move_cost(exp, *path[i])
            if step > budget:
                break
            budget -= step
            exp.explorer.x, exp.explorer.y = path[i]
            i += 1
        exp.turn += 1
        turns += 1
        _spend(exp, 1)
        fresh = visible_clues(exp) - seen
        if fresh:
            halted = i < len(path)
            exp.log("hint", "Disturbed ground catches your eye"
                            + (" — you halt the march." if halted else "."),
                    *next(iter(fresh)))
            if halted:
                break
    if turns > 1:
        exp.log("info", f"A march of {turns} turns.")
    return True


def dig_trench(exp: Expedition) -> list[Vec]:
    """The cells a dig from the explorer's stand opens (a disc, dig_radius)."""
    r = exp.config.expedition.dig_radius
    p = exp.explorer
    return [(p.x + dx, p.y + dy)
            for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if dx * dx + dy * dy <= r * r and exp.in_bounds(p.x + dx, p.y + dy)]


def do_dig(exp: Expedition) -> Site | None:
    """Open a trench around where you stand; a site anywhere inside it pays
    off. Re-digging fully spent ground is free — you notice, and don't."""
    if exp.outcome is not None:
        return None
    p = exp.explorer
    trench = dig_trench(exp)
    if all(c in exp.dug for c in trench):
        exp.log("info", "You already turned this ground over — nothing here.")
        return None
    exp.dug.update(trench)
    hits = [s for s in exp.unfound() if (s.x, s.y) in set(trench)]
    if hits:
        site = min(hits, key=lambda s: dist(p.x, p.y, s.x, s.y))
        site.found = True
        exp.log("find", f"Your spade rings on worked stone — {site.name}!",
                site.x, site.y)
        if not exp.unfound():
            exp.outcome = "complete"
            exp.log("outcome", "Every sensor contact resolved. A survey to be "
                               "proud of.", friendly=True)
        return site
    _spend(exp, exp.config.expedition.dig_cost)
    if exp.outcome is None:
        exp.log("dig", "You open a trench: nothing but soil and stones.",
                p.x, p.y)
    return None


def do_talk(exp: Expedition) -> bool:
    """Inside a settlement: resupply, and (once per town) a hint that narrows
    one unfound site's circle."""
    if exp.outcome is not None:
        return False
    p = exp.explorer
    town = exp.settlement_at(p.x, p.y)
    if town is None:
        exp.log("info", "No one to talk to out here.")
        return False
    e = exp.config.expedition
    if p.supplies < e.supplies_start:
        p.supplies = e.supplies_start
        exp.log("info", f"The people of {town.name} refill your packs.")
    candidates = [s for s in exp.unfound() if not s.hinted]
    if town.hint_given or not candidates:
        exp.log("info", f"{town.name} wishes you fair digging.")
        return True
    site = min(candidates, key=lambda s: dist(town.cx, town.cy, s.x, s.y))
    town.hint_given = True
    site.hinted = True
    site.area_cx = max(2, min(e.width - 3, site.x + exp.rng.randint(-2, 2)))
    site.area_cy = max(2, min(e.height - 3, site.y + exp.rng.randint(-2, 2)))
    site.area_r = e.city_hint_radius
    ew = "east" if site.x > town.cx else "west"
    ns = "south" if site.y > town.cy else "north"
    exp.log("hint", f"An elder of {town.name} remembers old stones to the "
                    f"{ns}-{ew} — your chart circle tightens.", site.area_cx,
            site.area_cy)
    return True
