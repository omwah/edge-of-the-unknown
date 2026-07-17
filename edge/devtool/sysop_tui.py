"""The sysop console as a Textual app (DESIGN §A.4 — WP59 follow-up).

A two-pane dashboard over one save: report/config/intervention navigation on the left,
the selected view on the right — tabular reports (players, market, standings, notices)
as **sortable DataTables** (click a header, or click again to reverse), text reports
(money, governance, config) as plain panels. Enter/click on a players or standings row
**drills into the full dossier** (`reports.player_detail` / `reports.species_detail` —
ship location, inventory, standings, grudges); Esc returns to the table. Interventions open **modal forms** with a
player picker where it matters, and still travel the `DevPatch` rail via
`apply_patch_lines`, so every sysop act stays a logged, replayable command. An
**audit-trail pane** at the bottom shows each patch this session with its before→after
diff. Views **auto-refresh** every few seconds (`a` toggles, `r` forces).

Dev tooling (the `devtool`/`tui` exemption tier — never imported by a runtime layer).
Launched by `edge-sysop` (the default; `--plain` keeps the classic text menu).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label, OptionList, RichLog, Select, Static,
)
from textual.widgets.option_list import Option

from edge.bigbang.inspect import resolve_sector
from edge.core.dev import DevPatch
from edge.devtool import reports
from edge.devtool.__main__ import Session, apply_patch_lines

_AUTO_REFRESH_SECS = 5.0

# view id → title. Tabular views render as DataTables; the rest as text panels.
_TABLE_VIEWS = {
    "players": "Players",
    "market": "Market order book",
    "standings": "Species standings",
    "notices": "Noticeboard",
}
_TEXT_VIEWS = {
    "money": "Money supply (conservation audit)",
    "governance": "Core governance",
    "config": "Config",
}
_INTERVENTIONS = {
    "latinum": "Grant / seize latinum",
    "turns": "Set turns",
    "teleport": "Teleport ship",
    "flip": "Flip Core governor",
    "settle": "Force market settlement",
    "expire": "Expire a contract",
    "notice": "Delete a notice",
}


# --- the intervention modal ---------------------------------------------------------


@dataclass
class FormField:
    """One labelled input on an intervention form."""

    key: str
    label: str
    kind: str = "int"  # "int" | "text" | "select"
    options: list[tuple[str, Any]] = field(default_factory=list)  # select choices
    placeholder: str = ""


class InterventionForm(ModalScreen[dict[str, Any] | None]):
    """A small validated form; dismisses with the field values, or None on cancel."""

    BINDINGS = [("escape", "cancel", "Cancel")]
    CSS = """
    InterventionForm { align: center middle; }
    #dialog { width: 64; max-height: 80%; padding: 1 2; border: thick $primary;
              background: $surface; }
    #dialog .hint { color: $text-muted; }
    #dialog Label { margin-top: 1; }
    #dialog #form-error { color: $error; height: auto; }
    #dialog #form-buttons { height: 3; align-horizontal: right; margin-top: 1; }
    #dialog Button { margin-left: 2; min-width: 10; }
    """

    def __init__(self, title: str, fields: list[FormField],
                 hints: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._title = title
        self._fields = fields
        self._hints = hints

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="dialog"):
            yield Static(f"[b]{self._title}[/b]")
            for hint in self._hints:
                yield Static(hint, classes="hint")
            for f in self._fields:
                yield Label(f.label)
                if f.kind == "select":
                    yield Select(f.options, allow_blank=False, id=f"field-{f.key}")
                else:
                    yield Input(placeholder=f.placeholder, id=f"field-{f.key}")
            yield Static("", id="form-error")
            with Horizontal(id="form-buttons"):
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        values: dict[str, Any] = {}
        for f in self._fields:
            widget = self.query_one(f"#field-{f.key}")
            if f.kind == "select":
                values[f.key] = widget.value  # type: ignore[attr-defined]
                continue
            raw = str(widget.value).strip()  # type: ignore[attr-defined]
            if f.kind == "int":
                try:
                    values[f.key] = int(raw)
                except ValueError:
                    self.query_one("#form-error", Static).update(
                        f"'{f.label}' needs an integer (got {raw!r})")
                    return
            else:
                if not raw:
                    self.query_one("#form-error", Static).update(f"'{f.label}' is required")
                    return
                values[f.key] = raw
        self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#apply", Button).press()


# --- the app ------------------------------------------------------------------------


class SysopApp(App[None]):
    """Two-pane sysop dashboard: nav left, view right, audit trail below."""

    TITLE = "edge-sysop"
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("a", "toggle_auto", "Auto-refresh"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]
    CSS = """
    #body { height: 1fr; }
    #nav { width: 26; border-right: solid $primary; }
    #content { width: 1fr; padding: 0 1; }
    #view-title { height: 1; text-style: bold; background: $boost; padding: 0 1; }
    #text-wrap { height: 1fr; }
    #text-body { padding: 0 1; }
    #table { height: 1fr; }
    #audit-pane { height: 9; border-top: solid $secondary; }
    #audit-title { height: 1; padding: 0 1; text-style: bold; background: $boost; }
    #audit { height: 1fr; padding: 0 1; }
    """

    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self._view = "players"
        self._auto = True
        self._sorts: dict[str, tuple[int, bool]] = {}  # view → (column index, reverse)

    # --- layout ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield OptionList(id="nav")
            with Vertical(id="content"):
                yield Static("", id="view-title")
                with VerticalScroll(id="text-wrap"):
                    yield Static("", id="text-body")
                yield DataTable(id="table", zebra_stripes=True, cursor_type="row")
        with Vertical(id="audit-pane"):
            yield Static("AUDIT TRAIL — every intervention is a logged DevPatch command",
                         id="audit-title")
            yield RichLog(id="audit", wrap=True, markup=True, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        nav = self.query_one("#nav", OptionList)
        nav.add_option(Option("[b yellow]REPORTS[/b yellow]", disabled=True))
        for key in (*_TABLE_VIEWS, *("money", "governance")):
            title = _TABLE_VIEWS.get(key) or _TEXT_VIEWS[key]
            nav.add_option(Option(f"  {title}", id=f"view:{key}"))
        nav.add_option(Option("[b yellow]CONFIG[/b yellow]", disabled=True))
        nav.add_option(Option("  Resolved config", id="view:config"))
        nav.add_option(Option("[b yellow]INTERVENE[/b yellow]", disabled=True))
        for key, title in _INTERVENTIONS.items():
            nav.add_option(Option(f"  {title}", id=f"act:{key}"))
        mode = "LIVE hosted queue" if self.session.live else "offline save"
        self._audit_note(f"[dim]session open — {mode} — {self.session.dev_command_count()} dev "
                         f"command(s) already in the log[/dim]")
        self._show_view(self._view)
        self.set_interval(_AUTO_REFRESH_SECS, self._auto_tick)
        self._update_subtitle()

    # --- navigation ----------------------------------------------------------------

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ""
        if oid.startswith("view:"):
            self._show_view(oid.removeprefix("view:"))
        elif oid.startswith("act:"):
            self._open_intervention(oid.removeprefix("act:"))

    # --- views -----------------------------------------------------------------------

    def _show_view(self, view: str) -> None:
        self.session.refresh()
        self._view = view
        state, config = self.session.state, self.session.config
        stamp = time.strftime("%H:%M:%S")
        table = self.query_one("#table", DataTable)
        text_wrap = self.query_one("#text-wrap", VerticalScroll)

        if ":" in view:  # a drill-down detail ("player:3" / "species:7")
            kind, _, ref = view.partition(":")
            lines = (reports.player_detail(state, config, int(ref)) if kind == "player"
                     else reports.species_detail(state, config, int(ref)))
            self.query_one("#view-title", Static).update(
                f"{kind.capitalize()} detail  [dim]· read {stamp} · Esc to go back[/dim]")
            table.display, text_wrap.display = False, True
            self.query_one("#text-body", Static).update("\n".join(lines))
            return

        title = _TABLE_VIEWS.get(view) or _TEXT_VIEWS[view]
        hint = " · Enter/click a row for detail" if view in ("players", "standings") else ""
        self.query_one("#view-title", Static).update(
            f"{title}  [dim]· read {stamp}{hint}[/dim]")
        if view in _TABLE_VIEWS:
            headers, rows = {
                "players": lambda: reports.players_rows(state),
                "market": lambda: reports.market_rows(state),
                "standings": lambda: reports.standings_rows(state, config),
                "notices": lambda: reports.notices_rows(state),
            }[view]()
            table.display, text_wrap.display = True, False
            table.clear(columns=True)
            table.add_columns(*headers)
            table.add_rows(rows)
            self._apply_sort(table)
        else:
            lines = {
                "money": lambda: reports.money_supply(state),
                "governance": lambda: reports.governance_report(state, config),
                "config": self._config_dump,
            }[view]()
            table.display, text_wrap.display = False, True
            self.query_one("#text-body", Static).update("\n".join(lines))

    def _config_dump(self) -> list[str]:
        from edge.devtool.sysop import config_dump
        return config_dump(self.session)

    # --- drill-down details --------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter/click on a players or standings row opens its full dossier."""
        if self._view not in ("players", "standings"):
            return
        ref = event.data_table.get_row(event.row_key)[0]  # the id column
        kind = "player" if self._view == "players" else "species"
        self._show_view(f"{kind}:{ref}")

    def action_back(self) -> None:
        if self._view.startswith("player:"):
            self._show_view("players")
        elif self._view.startswith("species:"):
            self._show_view("standings")

    # --- sortable tables ----------------------------------------------------------------

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        idx = event.column_index
        prev = self._sorts.get(self._view)
        reverse = prev is not None and prev[0] == idx and not prev[1]
        self._sorts[self._view] = (idx, reverse)
        self._apply_sort(event.data_table)

    def _apply_sort(self, table: DataTable) -> None:
        sort = self._sorts.get(self._view)
        if sort is None:
            return
        idx, reverse = sort
        keys = list(table.columns)
        if idx < len(keys):
            table.sort(keys[idx], reverse=reverse)

    # --- refresh ---------------------------------------------------------------------------

    def action_refresh(self) -> None:
        self._show_view(self._view)

    def action_toggle_auto(self) -> None:
        self._auto = not self._auto
        self._update_subtitle()

    def _auto_tick(self) -> None:
        if self._auto and len(self.screen_stack) == 1:  # never repaint under a modal
            self._show_view(self._view)

    def _update_subtitle(self) -> None:
        auto = f"auto-refresh {_AUTO_REFRESH_SECS:g}s" if self._auto else "auto-refresh off"
        mode = "LIVE server queue" if self.session.live else "offline save"
        self.sub_title = f"{mode} · {auto} · every intervention is logged"

    # --- interventions ------------------------------------------------------------------------

    def _player_field(self) -> FormField:
        state = self.session.state
        options = [(f"#{pid} {state.players[pid].name}", pid) for pid in sorted(state.players)]
        return FormField("player", "Player", "select", options)

    def _open_intervention(self, key: str) -> None:
        state = self.session.state
        fields: list[FormField]
        hints: tuple[str, ...] = ()
        if key == "latinum":
            fields = [self._player_field(),
                      FormField("value", "Grant (+) / seize (-) latinum", "int", placeholder="-500")]
        elif key == "turns":
            fields = [self._player_field(),
                      FormField("value", "Set turns_remaining to", "int", placeholder="250")]
        elif key == "teleport":
            fields = [self._player_field(),
                      FormField("sector", "Sector (internal id, or s<spatial id>)", "text",
                                placeholder="42 or s10203")]
        elif key == "flip":
            options: list[tuple[str, Any]] = [("— ungoverned Core", 0)]
            options += [(f"#{a.id} {a.name}", a.id)
                        for a in sorted(state.alliances.values(), key=lambda a: a.id)]
            fields = [FormField("value", "New Core governor", "select", options)]
        elif key == "settle":
            fields = []
            hints = ("Run one market settlement pulse now (port-to-port order matching).",)
        elif key == "expire":
            active = [(pid, c) for pid, p in sorted(state.players.items())
                      for c in p.contracts if c.status == "active"]
            if not active:
                self._audit_note("[dim]no active contracts to expire[/dim]")
                return
            hints = tuple(f"player #{pid}: contract {c.id} — {c.kind} for {c.issuer}, "
                          f"due d{c.deadline_day}" for pid, c in active[:8])
            fields = [self._player_field(), FormField("ref", "Contract id", "int")]
        elif key == "notice":
            if not state.notices:
                self._audit_note("[dim]no notices to delete[/dim]")
                return
            options = [(f"[{i}] d{n.day} #{n.author_player_id}: {n.text[:40]}", i)
                       for i, n in enumerate(state.notices)]
            fields = [FormField("value", "Notice to delete", "select", options)]
        else:
            return
        self.push_screen(InterventionForm(_INTERVENTIONS[key], fields, hints),
                         partial(self._apply_intervention, key))

    def _apply_intervention(self, key: str, values: dict[str, Any] | None) -> None:
        if values is None:
            self._audit_note(f"[dim]{_INTERVENTIONS[key]} — cancelled[/dim]")
            return
        player_id = int(values.get("player", 1))
        try:
            patch = self._build_patch(key, values)
        except ValueError as exc:  # a bad sector token from the teleport form
            self._audit_note(f"[red]error: {exc}[/red]")
            return
        ok, lines = apply_patch_lines(self.session, patch, player_id)
        stamp = time.strftime("%H:%M:%S")
        color = "green" if ok else "red"
        args = {k: v for k, v in values.items() if k != "player"}
        self._audit_note(f"[dim]{stamp}[/dim] [{color}]{_INTERVENTIONS[key]}[/{color}] "
                         f"player #{player_id} {args if args else ''}")
        for line in lines:
            self._audit_note(f"  [{color}]{line.strip()}[/{color}]")
        self._show_view(self._view)

    def _build_patch(self, key: str, values: dict[str, Any]) -> DevPatch:
        if key == "latinum":
            return DevPatch(op="add", target="latinum", value=int(values["value"]))
        if key == "turns":
            return DevPatch(op="set", target="turns_remaining", value=int(values["value"]))
        if key == "teleport":
            sid = resolve_sector(self.session.state, str(values["sector"]))
            return DevPatch(op="teleport", target="sector", value=sid)
        if key == "flip":
            return DevPatch(op="flip_governor", target="game", value=int(values["value"]))
        if key == "settle":
            return DevPatch(op="force_settlement", target="market")
        if key == "expire":
            return DevPatch(op="expire_contract", target="contract", ref=int(values["ref"]))
        if key == "notice":
            return DevPatch(op="moderate_notice", target="notice", value=int(values["value"]))
        raise ValueError(f"unknown intervention {key!r}")

    def _audit_note(self, markup: str) -> None:
        self.query_one("#audit", RichLog).write(markup)
