"""Dev inspector: list populated universe contents and plot routes (CLI helpers).

Backs `python -m edge.bigbang --list ...` and `--route SRC DST`. Pure formatting
over a generated `UniverseState`, with no I/O or RNG. Every sector reference is
shown as **both** the authoritative internal sector id and the band-monotone
spatial display id (§5.1: internal stays authoritative, spatial is UI-only), and
a route endpoint accepts either id form. A bare number is read internal-first
(internal ids are small, spatial ids carry a band prefix, so they don't collide);
an `i`/`s` prefix forces the interpretation (`i42`, `s30107`).
"""

from __future__ import annotations

from edge.core.movement import plan_route
from edge.core.starbases import is_operational
from edge.core.models import UniverseState

LIST_CATEGORIES = ("ports", "planets", "discoveries", "ships", "starbases", "species")


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


def _ports(state: UniverseState) -> list[str]:
    rows = [f"ports ({len(state.ports)}):", "  id    sector(int/sp)  class    size  name"]
    for pid in sorted(state.ports):
        p = state.ports[pid]
        rows.append(f"  {pid:<4}  {_sec(state, p.sector_id):<14}  {p.klass.name:<8} {p.size:<4}  {p.name}")
    return rows


def _planets(state: UniverseState) -> list[str]:
    rows = [f"planets ({len(state.planets)}):", "  id    sector(int/sp)  type             owner          base  name"]
    for plid in sorted(state.planets):
        pl = state.planets[plid]
        owner = pl.owner.kind if not pl.owner.is_owned else f"{pl.owner.kind}:{pl.owner.ref}"
        base = "yes" if pl.starbase_id is not None else "-"
        rows.append(
            f"  {plid:<4}  {_sec(state, pl.sector_id):<14}  {pl.planet_type:<15}  {owner:<13}  {base:<4}  {pl.name}"
        )
    return rows


def _discoveries(state: UniverseState) -> list[str]:
    rows = [f"discoveries ({len(state.discoveries)}):", "  id    kind          rarity       sector(int/sp)  loc          hidden  payload"]
    for did in sorted(state.discoveries):
        d = state.discoveries[did]
        loc = f"planet {d.planet_id}#{d.site_slot}" if d.planet_id is not None else "open space"
        rows.append(
            f"  {did:<4}  {d.kind.value:<12}  {d.rarity_tier.name:<11}  {_sec(state, d.sector_id):<14}  "
            f"{loc:<11}  {'yes' if d.hidden else '-':<6}  {d.payload.kind.value}"
        )
    return rows


def _ships(state: UniverseState) -> list[str]:
    rows = [f"ships ({len(state.ships)}):", "  id    type            owner   sector(int/sp)  name"]
    for sid in sorted(state.ships):
        s = state.ships[sid]
        owner = str(s.owner_player_id) if s.owner_player_id is not None else "npc"
        rows.append(f"  {sid:<4}  {s.type_id:<14}  {owner:<6}  {_sec(state, s.sector_id):<14}  {s.name}")
    return rows


def _starbases(state: UniverseState) -> list[str]:
    rows = [f"starbases ({len(state.starbases)}):", "  id    sector(int/sp)  planet  owner          status"]
    for bid in sorted(state.starbases):
        b = state.starbases[bid]
        owner = b.owner.kind if not b.owner.is_owned else f"{b.owner.kind}:{b.owner.ref}"
        status = "operational" if is_operational(b) else "derelict"
        rows.append(f"  {bid:<4}  {_sec(state, b.sector_id):<14}  {b.planet_id:<6}  {owner:<13}  {status}")
    return rows


def _species(state: UniverseState) -> list[str]:
    rows = [f"species ({len(state.species)}):", "  id    name                 roster            sector(int/sp)  band       disp"]
    for spid in sorted(state.species):
        sp = state.species[spid]
        rows.append(
            f"  {spid:<4}  {sp.name:<19}  {sp.roster_id:<16}  {_sec(state, sp.sector_id):<14}  "
            f"{sp.home_band:<9}  {sp.base_disposition:.2f}"
        )
    return rows


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
    return "\n".join(_LISTERS[category](state))


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
