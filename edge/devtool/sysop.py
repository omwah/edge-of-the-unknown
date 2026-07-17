"""`edge-sysop` — a menu-driven admin console over a save (DESIGN §A.4 — WP59).

AAT's admin catalog as a menu, built on rails that already exist. The console is **dev
tooling** (the `devtool`/`tui` exemption tier — never imported by a runtime layer): it opens
a save through `GameService`, shows **Reports** (read-only `devtool.reports` over raw state,
fog bypassed), applies **Interventions** through the **existing `DevPatch` command rail**
(so *every sysop act is a logged, replayable command* — the audit trail is the command log
itself, the twclone lesson), and dumps **Config**.

Interventions reuse `devtool.__main__.apply_patch`, so a settlement pulse, a contract expiry,
a notice deletion, a governor flip, and a latinum grant all persist and replay identically.

`edge-sysop --save PATH` opens the **Textual dashboard** (`sysop_tui.SysopApp`: two-pane
nav, sortable report tables, modal intervention forms with a player picker, an audit-trail
pane, auto-refresh). For a running hosted game, use `--connect WS_URL --game NAME`:
reports replay the local hosted-game DB while interventions go through the authenticated
server's single-writer queue. `--plain` keeps this module's classic text menu; `--report NAME`
prints one report non-interactively and exits (unchanged, for scripting).
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from edge.core.dev import DevPatch
from edge.devtool import reports
from edge.devtool.__main__ import Session, apply_patch
from edge.server.client import RemoteError
from edge.server.env import sysop_password as load_sysop_password
from edge.tui.saves import default_save

_PLAYER_ID = 1

# Report name → (title, function over the session). The console menu and the `--report`
# flag share this table, so a report is added in exactly one place.
_REPORTS: dict[str, str] = {
    "players": "Players",
    "money": "Money supply (conservation audit)",
    "market": "Market order book",
    "standings": "Species standings",
    "governance": "Core governance",
    "notices": "Noticeboard",
}


def run_report(session: Session, name: str) -> list[str]:
    """Produce one report's lines (the single dispatch shared by the menu and `--report`)."""
    session.refresh()
    state, config = session.state, session.config
    if name == "players":
        return reports.players_report(state)
    if name == "money":
        return reports.money_supply(state)
    if name == "market":
        return reports.market_report(state)
    if name == "standings":
        return reports.standings_report(state, config)
    if name == "governance":
        return reports.governance_report(state, config)
    if name == "notices":
        return reports.notices_report(state)
    raise KeyError(name)


def config_dump(session: Session) -> list[str]:
    """A compact resolved-config summary (the Config section)."""
    c = session.config
    return [
        f"config_version: {c.config_version}",
        f"turns_per_day:  {c.turns_per_day}",
        f"market.enabled: {c.economy.market.enabled}",
        f"contracts:      enabled={c.aliens.contracts.enabled} "
        f"deadline={c.aliens.contracts.deadline_days}d",
        f"tavern:         rumor {c.tavern.rumor_price} slips, notice_cap {c.tavern.notice_cap}",
        f"governance:     seizure {c.aliens.governance.seizure_chance}/day "
        f"intrigue {c.aliens.governance.intrigue_chance}/day",
    ]


# --- interventions (all through the DevPatch rail) -------------------------------


def _intervene(session: Session, choice: str) -> None:
    """Prompt for and apply one intervention as a logged `DevPatch` (WP59)."""
    if choice == "latinum":
        amount = int(input("  grant (+) / seize (-) latinum: "))
        apply_patch(session, DevPatch(op="add", target="latinum", value=amount))
    elif choice == "turns":
        turns = int(input("  set turns_remaining: "))
        apply_patch(session, DevPatch(op="set", target="turns_remaining", value=turns))
    elif choice == "teleport":
        sector = int(input("  teleport to internal sector id: "))
        apply_patch(session, DevPatch(op="teleport", target="sector", value=sector))
    elif choice == "flip":
        aid = int(input("  new Core governor alliance id (0 = ungoverned): "))
        apply_patch(session, DevPatch(op="flip_governor", target="game", value=aid))
    elif choice == "settle":
        apply_patch(session, DevPatch(op="force_settlement", target="market"))
    elif choice == "expire":
        cid = int(input("  expire contract id: "))
        apply_patch(session, DevPatch(op="expire_contract", target="contract", ref=cid))
    elif choice == "notice":
        idx = int(input("  delete notice index: "))
        apply_patch(session, DevPatch(op="moderate_notice", target="notice", value=idx))
    else:
        print("  unknown intervention")


_INTERVENTIONS = {
    "latinum": "Grant / seize latinum",
    "turns": "Set turns",
    "teleport": "Teleport ship",
    "flip": "Flip Core governor",
    "settle": "Force market settlement",
    "expire": "Expire a contract",
    "notice": "Delete a notice",
}


# --- the interactive menu --------------------------------------------------------


def _print(lines: list[str]) -> None:
    for line in lines:
        print(line)


def menu(session: Session) -> None:
    """The top-level console loop: Reports / Interventions / Config / Quit."""
    print("edge-sysop — admin console (every intervention is a logged, replayable command).")
    while True:
        print("\n[R]eports  [I]nterventions  [C]onfig  [Q]uit")
        try:
            head = input("sysop> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if head in ("q", "quit", "exit"):
            return
        if head.startswith("r"):
            for key, title in _REPORTS.items():
                print(f"  {key:<11} {title}")
            name = input("report> ").strip().lower()
            if name in _REPORTS:
                _print(run_report(session, name))
            else:
                print("  unknown report")
        elif head.startswith("i"):
            for key, title in _INTERVENTIONS.items():
                print(f"  {key:<10} {title}")
            _intervene(session, input("intervene> ").strip().lower())
        elif head.startswith("c"):
            _print(config_dump(session))


def _lobby_hint(path: Path) -> str | None:
    """A pointed error when the target is the multiplayer lobby registry, not a game save.

    `edge-server --accounts accounts.db` keeps accounts/sessions and a **games index**
    there; each hosted game world is its own save DB under `--games-dir`. If `path`
    looks like that registry, return an error message listing the per-game DBs to open
    instead; otherwise None.
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        tables = {row[0] for row in
                  conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"accounts", "games"} <= tables:
            return None
        rows = conn.execute("SELECT game_id, name, db_path FROM games ORDER BY game_id").fetchall()
        listing = "\n".join(f"  #{gid} {name}: --save {db}" for gid, name, db in rows) \
            or "  (no hosted games created yet)"
        return (f"{path} is the multiplayer lobby registry (accounts/sessions/games index), "
                f"not a game save.\nEach hosted game is its own save DB — open one of:\n{listing}\n"
                "Reports are safe reads. For live intervention, open the selected game DB with "
                "--save and add --connect/--game so changes enter the server queue.")
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="edge-sysop", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save", metavar="PATH", default=None,
                        help="save DB to open (default: the single ~/.edge/games slot)")
    parser.add_argument("--connect", metavar="WS_URL",
                        help="administer a running hosted game through edge-server")
    parser.add_argument("--password",
                        help="operator secret (default $EDGE_SYSOP_PASSWORD, then ./.env)")
    parser.add_argument("--env-file", type=Path,
                        help="dotenv file for EDGE_SYSOP_PASSWORD (default: ./.env)")
    parser.add_argument("--game", metavar="NAME",
                        help="hosted game name (required with --connect)")
    parser.add_argument("--report", metavar="NAME", choices=sorted(_REPORTS),
                        help="print one report non-interactively and exit")
    parser.add_argument("--plain", action="store_true",
                        help="use the classic text menu instead of the Textual dashboard")
    args = parser.parse_args(argv)
    if args.connect:
        args.password = load_sysop_password(args.password, dotenv_path=args.env_file)
    if args.connect and (not args.password or args.game is None):
        parser.error("--connect needs --game and a sysop password from --password, "
                     "EDGE_SYSOP_PASSWORD, or the selected .env file")
    live_service = None
    if args.connect:
        from edge.devtool.remote import LiveSysopService
        try:
            live_service = LiveSysopService(args.connect, args.password, args.game)
        except (OSError, RemoteError, TimeoutError) as exc:
            parser.error(f"live sysop connection failed: {exc}")
    if args.save:
        save_path = Path(args.save)
    elif live_service is not None:
        save_path = live_service.save_path
    else:
        save_path = default_save()
    if not save_path.exists():
        if live_service is not None:
            live_service.close()
        parser.error(f"no save at {save_path} — start a game first (or pass --save PATH)")
    try:
        session = Session(save_path)
    except LookupError:  # a DB with no game meta: a lobby registry, or not ours at all
        if live_service is not None:
            live_service.close()
        parser.error(_lobby_hint(save_path)
                     or f"{save_path} is not a game save (it has no game meta)")
    try:
        if live_service is not None:
            session.attach_live(live_service)
        if args.report is not None:
            _print(run_report(session, args.report))
        elif args.plain:
            menu(session)
        else:
            from edge.devtool.sysop_tui import SysopApp  # lazy: Textual only when needed
            SysopApp(session).run()
    finally:
        session.close()


if __name__ == "__main__":
    main()
