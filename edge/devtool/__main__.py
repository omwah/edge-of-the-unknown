"""CLI: `python -m edge.devtool [--save PATH] [--dry-run] <command> …`.

A developer tool to inspect and modify the player in a saved game, so testing
states that are slow to earn (latinum, high-tier components, claimed worlds, a
hull parked in the deep frontier) can be reached instantly.

Edits are applied through the `DevPatch` command (`edge.core.dev`) and recorded
in the save's command log via `GameService.apply`, so they survive Continue/
reload and replay deterministically. `--dry-run` previews a change (running the
reducer but discarding the result) without writing anything.

Run with no subcommand for an interactive REPL; run with a subcommand for a
one-shot scriptable edit. Single-player always uses player id 1.

Subcommands:
  list                          list players in the game
  show [--player N]             detailed player/ship/planets/inventory dump
  set <target> <value>          set a field (e.g. latinum, ship.missiles, aspect.shields)
  add <target> <value>          add to a field
  grant component <name:tier>   grant loose components  (--qty N)
  grant artifact <tier>         grant barter artifacts  (--qty N)
  grant device <id>             grant devices, e.g. genesis_torpedo  (--qty N)
  cargo <commodity> <units>     set a cargo hold's units
  teleport <sector>             move the ship to a sector (internal or spatial id)
  claim <planet_id>             claim a planet for the player
"""

from __future__ import annotations

import argparse
import shlex
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

from edge.bigbang.inspect import resolve_sector
from edge.config import load_default_config
from edge.core.dev import DevPatch, DevPatchError
from edge.core.models import UniverseState
from edge.core.rules import reduce
from edge.server.service import GameService
from edge.server.client import RemoteError
from edge.store.repo import SqliteRepository
from edge.tui.saves import default_save

_PLAYER_ID = 1

if TYPE_CHECKING:
    from edge.devtool.remote import LiveSysopService


# --- session: a loaded save + its repo --------------------------------------


class Session:
    """A loaded save: the service plus the repo (kept for command-log scans)."""

    def __init__(self, path: Path) -> None:
        self.config = load_default_config()
        self.repo = SqliteRepository(path)
        self._local_service = GameService.load_game(self.config, self.repo)
        self.service: GameService | LiveSysopService = self._local_service
        self._live_service: LiveSysopService | None = None
        self.dry_run = False

    @property
    def state(self) -> UniverseState:
        return self._local_service.state

    @property
    def live(self) -> bool:
        return self._live_service is not None

    def attach_live(self, service: LiveSysopService) -> None:
        """Route mutations to a hosted server while retaining local trusted reports."""
        self._live_service = service
        self.service = service
        self.refresh()

    def refresh(self) -> None:
        """Replay newly committed hosted commands before producing an admin report/preview."""
        if self._live_service is not None:
            self._local_service = GameService.load_game(self.config, self.repo)

    def dev_command_count(self) -> int:
        return sum(1 for rc in self.repo.load_commands() if isinstance(rc.command, DevPatch))

    def close(self) -> None:
        if self._live_service is not None:
            self._live_service.close()
        self.repo.close()


def _sec(state: UniverseState, sid: int) -> str:
    sp = state.spatial_ids.get(sid)
    return f"{sid}/{sp}" if sp is not None else str(sid)


# --- read views -------------------------------------------------------------


def cmd_list(session: Session) -> None:
    state = session.state
    print(f"players ({len(state.players)}):")
    print("  id    name                 ship")
    for pid in sorted(state.players):
        p = state.players[pid]
        ship = state.ships.get(p.ship_id)
        ship_label = f"{ship.name} ({ship.type_id})" if ship else "—"
        print(f"  {pid:<4}  {p.name:<19}  {ship_label}")


def cmd_show(session: Session, player_id: int) -> None:
    state = session.state
    player = state.players.get(player_id)
    if player is None:
        print(f"no such player {player_id}")
        return
    ship = state.ships[player.ship_id]
    owned = [pl for pl in state.planets.values()
             if pl.owner.kind == "player" and pl.owner.ref == player_id]

    print(f"player {player_id}: {player.name}")
    print(f"  location:   sector {_sec(state, ship.sector_id)}")
    print(f"  latinum:    {player.latinum}    bank: {player.bank_balance}    "
          f"turns: {player.turns_remaining}")
    print(f"  codex:      {len(player.codex)} logged    "
          f"artifacts: {_mapping(player.artifacts) or '—'}")
    print(f"  ship:       {ship.name} ({ship.type_id})")
    print(f"    hull:     {ship.hull_current}/{ship.hull_max}    "
          f"holds: {ship.holds_used}/{ship.holds_total}")
    print(f"    aspects:  shields {ship.shields}  warp {ship.warp_speed}  "
          f"combat {ship.combat_speed}  cloak {ship.cloak_rating}  sensors {ship.sensor_rating}")
    print(f"    missiles {ship.missiles}  repair_kits {ship.repair_kits}  "
          f"colonists {ship.colonists}/{ship.colonist_capacity}")
    print(f"    cargo:    {_mapping({c.value: n for c, n in ship.cargo.items()}) or '—'}")
    print(f"    parts:    {_components(ship.components) or '—'}")
    print(f"    devices:  {_mapping(ship.devices) or '—'}")
    if owned:
        print(f"  owned planets ({len(owned)}):")
        for pl in sorted(owned, key=lambda p: p.id):
            print(f"    #{pl.id} {pl.name} — sector {_sec(state, pl.sector_id)} "
                  f"({pl.planet_type}, colonists {pl.colonists})")
    else:
        print("  owned planets: none")
    n_dev = session.dev_command_count()
    if n_dev:
        print(f"  dev commands in log: {n_dev}")


def cmd_governance(session: Session) -> None:
    """Report the Core governance picture (WP52): governor, coveters, incumbent grip."""
    from edge.core.governance import _operational_core_bases, npc_seizure_ready

    state = session.state
    gov_id = state.game.core_governing_alliance_id
    gov = state.alliances.get(gov_id) if gov_id is not None else None
    print(f"Core governor: {gov.name if gov else '— (ungoverned)'} (id {gov_id})")
    print(f"  incumbent operational Core bases: {_operational_core_bases(state, gov_id)}")
    print("  covets_core blocs:")
    coveters = [a for a in state.alliances.values() if a.covets_core and a.id != gov_id]
    if not coveters:
        print("    none")
    for a in sorted(coveters, key=lambda a: a.id):
        ready = npc_seizure_ready(state, session.config, a.id)
        print(f"    #{a.id} {a.name} — seizure-ready: {ready}")


def _mapping(m: Any) -> str:
    return ", ".join(f"{k}x{v}" for k, v in m.items())


def _components(m: Any) -> str:
    return ", ".join(f"{comp.value}({tier.name})x{n}" for (comp, tier), n in m.items())


# --- mutations --------------------------------------------------------------


def _diff_after(session: Session, patch: DevPatch, player_id: int = _PLAYER_ID) -> list[str]:
    """Run the reducer (no persistence) and return human before→after change lines."""
    result = reduce(session.state, player_id, patch, session.config)
    lines: list[str] = []
    for kind, news, live in (
        ("player", result.players, session.state.players),
        ("ship", result.ships, session.state.ships),
        ("planet", result.planets, session.state.planets),
    ):
        for new in news:
            old = live.get(new.id)
            for f in fields(new):
                ov = getattr(old, f.name, None)
                nv = getattr(new, f.name)
                if ov != nv:
                    lines.append(f"    {kind}.{f.name}: {ov!r} -> {nv!r}")
    for ev in result.events:
        detail = getattr(ev, "detail", None)
        if detail:
            lines.insert(0, f"  {detail}")
    return lines


def apply_patch_lines(session: Session, patch: DevPatch,
                      player_id: int = _PLAYER_ID) -> tuple[bool, list[str]]:
    """Apply (or, in dry-run, preview) a DevPatch; return (ok, report lines).

    The player-aware, non-printing form the sysop TUI drives (WP59): the patch is
    reduced and applied *as* `player_id`, so an intervention can target any player.
    """
    session.refresh()
    try:
        preview = _diff_after(session, patch, player_id)  # also validates before we persist
    except (DevPatchError, RemoteError) as exc:
        return False, [f"error: {exc}"]
    if session.dry_run:
        return True, ["dry-run (nothing written):", *preview]
    try:
        session.service.apply(player_id, patch)
    except (DevPatchError, RemoteError) as exc:
        return False, [f"error: {exc}"]
    session.refresh()
    return True, ["applied:", *preview]


def apply_patch(session: Session, patch: DevPatch) -> None:
    """Apply (or, in dry-run, preview) a DevPatch and report what changed."""
    _, lines = apply_patch_lines(session, patch)
    for line in lines:
        print(line)


def _build_patch(session: Session, args: argparse.Namespace) -> DevPatch | None:
    """Turn parsed args into a DevPatch, resolving sector tokens etc. None on user error."""
    cmd = args.command
    if cmd in ("set", "add"):
        return DevPatch(op=cmd, target=args.target, value=args.value)
    if cmd == "grant":
        return DevPatch(op="grant", target=args.what, key=args.key, value=args.qty)
    if cmd == "cargo":
        return DevPatch(op="cargo", target=args.commodity, value=args.units)
    if cmd == "teleport":
        try:
            sid = resolve_sector(session.state, args.sector)
        except ValueError as exc:
            print(f"error: {exc}")
            return None
        return DevPatch(op="teleport", target="sector", value=sid)
    if cmd == "claim":
        return DevPatch(op="claim", target="planet", ref=args.planet_id)
    if cmd == "flip_governor":
        # value 0 ⇒ ungoverned Core (mirrors dev.py's convention).
        return DevPatch(op="flip_governor", target="game", value=args.alliance_id)
    return None


def dispatch(session: Session, args: argparse.Namespace) -> None:
    """Run one parsed command against the session."""
    cmd = args.command
    if cmd == "list":
        cmd_list(session)
    elif cmd == "show":
        cmd_show(session, getattr(args, "player", _PLAYER_ID))
    elif cmd == "governance":
        cmd_governance(session)
    else:
        patch = _build_patch(session, args)
        if patch is not None:
            apply_patch(session, patch)


# --- argument parsing -------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="edge.devtool", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save", metavar="PATH", default=None,
                        help="save DB to open (default: the single ~/.edge/games slot)")
    parser.add_argument("--dry-run", action="store_true",
                        help="preview the change without writing it")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="list players")
    p_show = sub.add_parser("show", help="detailed player dump")
    p_show.add_argument("--player", type=int, default=_PLAYER_ID)

    for op in ("set", "add"):
        p = sub.add_parser(op, help=f"{op} a numeric field")
        p.add_argument("target", help="e.g. latinum, turns_remaining, ship.missiles, aspect.shields")
        p.add_argument("value", type=int)

    p_grant = sub.add_parser("grant", help="grant components / artifacts / devices")
    p_grant.add_argument("what", choices=("component", "artifact", "device"))
    p_grant.add_argument("key", help="component 'name:tier', artifact tier I/II/III, or device id")
    p_grant.add_argument("--qty", type=int, default=1)

    p_cargo = sub.add_parser("cargo", help="set a cargo hold")
    p_cargo.add_argument("commodity", help="fuel_ore | organics | equipment")
    p_cargo.add_argument("units", type=int)

    p_tp = sub.add_parser("teleport", help="move the ship to a sector")
    p_tp.add_argument("sector", help="internal or spatial sector id (i/s prefix forces)")

    p_claim = sub.add_parser("claim", help="claim a planet for the player")
    p_claim.add_argument("planet_id", type=int)

    sub.add_parser("governance", help="report Core governor, coveters, incumbent grip")
    p_flip = sub.add_parser("flip_governor", help="flip the Core governing alliance")
    p_flip.add_argument("alliance_id", type=int, help="alliance id (0 ⇒ ungoverned Core)")

    return parser


# --- interactive REPL -------------------------------------------------------

_REPL_HELP = """commands:
  list | show [--player N]
  set <target> <value> | add <target> <value>
  grant component <name:tier> [--qty N] | grant artifact <tier> [--qty N] | grant device <id> [--qty N]
  cargo <commodity> <units> | teleport <sector> | claim <planet_id>
  governance | flip_governor <alliance_id>
  dry-run [on|off]   toggle preview mode
  help | quit"""


def repl(session: Session, parser: argparse.ArgumentParser) -> None:
    print(f"edge devtool — interactive (dry-run {'on' if session.dry_run else 'off'}). "
          "type 'help' or 'quit'.")
    while True:
        try:
            line = input("player> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        tokens = shlex.split(line)
        head = tokens[0].lower()
        if head in ("quit", "exit", "q"):
            break
        if head in ("help", "?"):
            print(_REPL_HELP)
            continue
        if head == "dry-run":
            if len(tokens) > 1:
                session.dry_run = tokens[1].lower() in ("on", "true", "1", "yes")
            else:
                session.dry_run = not session.dry_run
            print(f"dry-run {'on' if session.dry_run else 'off'}")
            continue
        try:
            args = parser.parse_args(tokens)
        except SystemExit:  # argparse already printed the usage/error
            continue
        if args.command is None:
            print(_REPL_HELP)
            continue
        dispatch(session, args)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    save_path = Path(args.save) if args.save else default_save()
    if not save_path.exists():
        parser.error(f"no save at {save_path} — start a game first (or pass --save PATH)")
    session = Session(save_path)
    session.dry_run = args.dry_run
    try:
        if args.command is None:
            repl(session, parser)
        else:
            dispatch(session, args)
    finally:
        session.close()


if __name__ == "__main__":
    main()
