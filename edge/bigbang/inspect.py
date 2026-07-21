"""Dev inspector: list populated universe contents and plot routes (CLI helpers).

Backs `python -m edge.bigbang --list ...` and `--route SRC DST`. Pure formatting
over a `UniverseState` — freshly generated, or rebuilt from a save by the CLI's
`--save` — with no I/O or RNG. Listings are auto-sized tables: every column is
measured against its own content, so a value wider than its header can never shift
the rows out from under it (which the previous hand-padded widths did). Every sector reference is
shown as **both** the authoritative internal sector id and the band-monotone
spatial display id (§5.1: internal stays authoritative, spatial is UI-only), and
a route endpoint accepts either id form. A bare number is read internal-first
(internal ids are small, spatial ids carry a band prefix, so they don't collide);
an `i`/`s` prefix forces the interpretation (`i42`, `s30107`).
"""

from __future__ import annotations

from collections.abc import Sequence
from io import StringIO

from rich import box
from rich.console import Console
from rich.table import Table

from edge.core.movement import plan_route
from edge.core.starbases import is_operational
from edge.core.models import AlienSpecies, Planet, UniverseState

LIST_CATEGORIES = ("ports", "planets", "discoveries", "ships", "starbases", "species")

#: Wider than any listing needs. Rich sizes a table to its *content*, so this only has
#: to be large enough that nothing wraps — the emitted lines stay their natural length,
#: and a narrow terminal soft-wraps (or `| less -S` scrolls) rather than the data being
#: truncated. A dev inspector should never hide a field to fit a window.
_RENDER_WIDTH = 400

#: What an empty / not-applicable cell reads as. One glyph everywhere, so a column of
#: them is obviously "nothing here" rather than a suspicious zero.
_NONE = "—"


def _render(title: str, columns: Sequence[tuple[str, bool]], rows: Sequence[Sequence[str]]) -> str:
    """Render one listing as a plain-text table: `title`, then a rich SIMPLE table.

    `columns` is (header, numeric) — numeric columns right-align so magnitudes line up.
    Colour and highlighting are off: this output is read in terminals, piped into files,
    and asserted on in tests, so it must be deterministic plain text.
    """
    table = Table(box=box.SIMPLE, show_edge=False, pad_edge=False)
    for header, numeric in columns:
        table.add_column(header, justify="right" if numeric else "left", no_wrap=True)
    for row in rows:
        table.add_row(*row)
    buf = StringIO()
    Console(file=buf, width=_RENDER_WIDTH, no_color=True, highlight=False,
            soft_wrap=False).print(table)
    # Rich pads every row out to the table width; strip that trailing run per line so the
    # output diffs, greps, and copies cleanly.
    body = "\n".join(line.rstrip() for line in buf.getvalue().rstrip("\n").split("\n"))
    return f"{title}\n{body}"


def _num(value: int) -> str:
    """A comma-grouped count, or the empty marker when there is none."""
    return f"{value:,}" if value else _NONE


def _spatial(state: UniverseState, sid: int) -> str:
    """The spatial display id for an internal sector id, or `—` if none is cached."""
    sp = state.spatial_ids.get(sid)
    return str(sp) if sp is not None else "—"


def _sec(state: UniverseState, sid: int) -> str:
    """A sector reference as `internal/spatial` (the §5.1 dual id)."""
    return f"{sid}/{_spatial(state, sid)}"


def _spatial_to_internal(state: UniverseState) -> dict[int, int]:
    """Reverse the internal→spatial map (spatial ids are a bijection, §5.1)."""
    return {sp: sid for sid, sp in state.spatial_ids.items()}


def resolve_sector(state: UniverseState, token: str) -> int:
    """Resolve a `--route` endpoint token to an internal sector id.

    Accepts an internal id, a spatial id, or an `i`/`s`-prefixed form to force the
    interpretation. Raises `ValueError` with a helpful message if it resolves to no
    known sector.
    """
    raw = token.strip()
    mode = ""
    if raw[:1].lower() in ("i", "s") and raw[1:].lstrip("-").isdigit():
        mode, raw = raw[0].lower(), raw[1:]
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{token!r} is not a sector id") from None

    rev = _spatial_to_internal(state)
    seed = state.game.seed
    if mode == "s":
        if value in rev:
            return rev[value]
        raise ValueError(f"no sector with spatial id {value} in seed {seed}")
    if mode == "i":
        if value in state.sectors:
            return value
        raise ValueError(f"no sector with internal id {value} in seed {seed}")
    # Bare token: internal-first, then spatial.
    if value in state.sectors:
        return value
    if value in rev:
        return rev[value]
    raise ValueError(f"{value} matches no internal or spatial sector id in seed {seed}")


def _owner(owner: object) -> str:
    """An `Ownership` as `kind` or `kind:ref` — "none" reads as the empty marker."""
    kind = getattr(owner, "kind")
    if not getattr(owner, "is_owned"):
        return _NONE if kind == "none" else str(kind)
    return f"{kind}:{getattr(owner, 'ref')}"


def _band(state: UniverseState, sector_id: int) -> str:
    """The containing sector's distance band (how deep the object sits, §5)."""
    sector = state.sectors.get(sector_id)
    return sector.distance_band if sector is not None else _NONE


def _species_label(species: AlienSpecies) -> str:
    """`Name (archetype)` — who they are and what kind of thing they are, in one cell."""
    return f"{species.name} ({species.archetype_id})" if species.archetype_id else species.name


def _inhabitants(state: UniverseState, planet: Planet) -> str:
    """The peoples living on a world, or the empty marker for an uninhabited one.

    A world can carry a native `population` while `owner` stays "none" (an unaligned
    holding, §4.2) — which is exactly the case this column exists to make visible. A
    colonized world may show more than one people once a player settles atop natives
    (GW-WP09-PRE follow-up); each roster_id resolves against the placed cast, falling
    back to the bare id (rather than hiding a generation fault) for a kind with no
    live instance left.
    """
    names = []
    for roster_id in sorted(planet.population):
        if planet.population[roster_id] <= 0:
            continue
        species = next((s for s in state.species.values() if s.roster_id == roster_id), None)
        names.append(_species_label(species) if species is not None else f"?{roster_id}")
    return ", ".join(names) if names else _NONE


def _special(planet: Planet) -> str:
    """The one field that matters only for this world's type: belt ore, or Cloud City size.

    Asteroid belts carry a finite, never-regrowing `ore_reserve` (shown against what it
    was seeded with) and gas giants carry a built Cloud City's size; every other world
    has neither.
    """
    if planet.ore_reserve_max:
        return f"ore {planet.ore_reserve:,}/{planet.ore_reserve_max:,}"
    if planet.cloud_city_size:
        return f"city {planet.cloud_city_size}"
    return _NONE


def _ports(state: UniverseState) -> str:
    columns = [("id", True), ("sector(int/sp)", False), ("class", False), ("size", True),
               ("name", False)]
    rows = [
        [str(pid), _sec(state, p.sector_id), p.klass.name, str(p.size), p.name]
        for pid, p in ((pid, state.ports[pid]) for pid in sorted(state.ports))
    ]
    return _render(f"ports ({len(state.ports)}):", columns, rows)


def _planets(state: UniverseState) -> str:
    """Worlds with their inhabitants, population, and defensive/economic holdings.

    Wide by design: the whole point of the planet listing is judging a seed's worlds
    without opening the game, so it carries who lives there (species + archetype),
    how many (`colonists`), the siege ladder (citadel level, gun integrity, garrison
    fighters, treasury) and the type-specific reserve, alongside the identity columns.
    """
    columns = [("id", True), ("sector(int/sp)", False), ("band", False), ("type", False),
               ("owner", False), ("species", False), ("pop", True), ("cit", True),
               ("gun", True), ("figs", True), ("treasury", True), ("special", False),
               ("base", False), ("name", False)]
    rows = []
    for plid in sorted(state.planets):
        pl = state.planets[plid]
        rows.append([
            str(plid), _sec(state, pl.sector_id), _band(state, pl.sector_id), pl.planet_type,
            _owner(pl.owner), _inhabitants(state, pl), f"{pl.colonists:,}",
            _num(pl.citadel_level), _num(pl.gun_integrity), _num(pl.fighters),
            _num(pl.treasury), _special(pl),
            "yes" if pl.starbase_id is not None else _NONE, pl.name,
        ])
    return _render(f"planets ({len(state.planets)}):", columns, rows)


def _discoveries(state: UniverseState) -> str:
    columns = [("id", True), ("kind", False), ("rarity", False), ("sector(int/sp)", False),
               ("loc", False), ("hidden", False), ("payload", False), ("name", False)]
    rows = []
    for did in sorted(state.discoveries):
        d = state.discoveries[did]
        loc = f"planet {d.planet_id}#{d.site_slot}" if d.planet_id is not None else "open space"
        rows.append([str(did), d.kind.value, d.rarity_tier.name, _sec(state, d.sector_id),
                     loc, "yes" if d.hidden else _NONE, d.payload.kind.value, d.name])
    return _render(f"discoveries ({len(state.discoveries)}):", columns, rows)


def _ships(state: UniverseState) -> str:
    columns = [("id", True), ("type", False), ("owner", False), ("sector(int/sp)", False),
               ("name", False)]
    rows = []
    for sid in sorted(state.ships):
        s = state.ships[sid]
        owner = str(s.owner_player_id) if s.owner_player_id is not None else "npc"
        rows.append([str(sid), s.type_id, owner, _sec(state, s.sector_id), s.name])
    return _render(f"ships ({len(state.ships)}):", columns, rows)


def _starbases(state: UniverseState) -> str:
    columns = [("id", True), ("sector(int/sp)", False), ("planet", True), ("owner", False),
               ("status", False)]
    rows = []
    for bid in sorted(state.starbases):
        b = state.starbases[bid]
        status = "operational" if is_operational(b) else "derelict"
        rows.append([str(bid), _sec(state, b.sector_id), str(b.planet_id), _owner(b.owner), status])
    return _render(f"starbases ({len(state.starbases)}):", columns, rows)


def _species(state: UniverseState) -> str:
    columns = [("id", True), ("name", False), ("archetype", False), ("roster", False),
               ("sector(int/sp)", False), ("band", False), ("disp", True)]
    rows = []
    for spid in sorted(state.species):
        sp = state.species[spid]
        rows.append([str(spid), sp.name, sp.archetype_id or _NONE, sp.roster_id,
                     _sec(state, sp.sector_id), sp.home_band, f"{sp.base_disposition:.2f}"])
    return _render(f"species ({len(state.species)}):", columns, rows)


_LISTERS = {
    "ports": _ports,
    "planets": _planets,
    "discoveries": _discoveries,
    "ships": _ships,
    "starbases": _starbases,
    "species": _species,
}


def list_items(state: UniverseState, category: str) -> str:
    """Render one category of populated universe items as an id-keyed table."""
    return _LISTERS[category](state)


def format_route(state: UniverseState, src_token: str, dst_token: str) -> str:
    """Resolve two endpoints (internal or spatial id) and plot the fewest-hop route.

    Uses the player ship's `turns_per_warp` for the cost estimate (1 if no ship),
    over the whole directed warp graph (no route-lock — this is a dev inspector).
    """
    src = resolve_sector(state, src_token)
    dst = resolve_sector(state, dst_token)
    tpw = next(iter(state.ships.values())).turns_per_warp if state.ships else 1
    plan = plan_route(state.adjacency, src, dst, allowed=None, turns_per_warp=tpw)
    if not plan.reachable:
        return f"no route {_sec(state, src)} -> {_sec(state, dst)} (unreachable in the directed warp graph)"

    lines = [
        f"route {_sec(state, src)} -> {_sec(state, dst)}  "
        f"({len(plan.hops)} hops, {plan.turn_cost} turns)",
        f"  {_sec(state, src):<16}  (start)",
    ]
    for hop in plan.hops:
        flag = "  [one-way]" if hop.one_way else ""
        lines.append(f"  {_sec(state, hop.sector_id):<16}{flag}")
    return "\n".join(lines)
