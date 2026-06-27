"""Dialogue play-test harness (dev-only — DESIGN §6.7, §13).

Reads the authored dialogue *in motion*: it drives the **real** `AlienContactScreen` and the
**real** `server.session.contact_view` selection path against a synthetic single-game universe,
so an author can hear every species' lines across standing bands, treaty/intel states, and
branch nodes without launching a full game and grinding reputation. A one-key **controls
modal** (F2) switches the simulated dials live:

- **species** — cycle through the whole roster (one instance of each is injected);
- **standing band** — hostile / neutral / friendly / allied (wary is Phase-3 inert);
- **treaty** / **intel available** — toggles that gate treaty- and coordinate-keyed lines;
- **show disabled** — the existing `ui.show_disabled_options` (greys gated rows);
- **force-enable & traverse** — makes gated verbs/choices *selectable* so you can walk every
  branch regardless of standing/treaty/Phase-3 gates.

Backtracking out of a dead-end branch node is provided by the shared contact screen itself
(Backspace; see `edge.tui.screens.contact`).

This is the dev-only impure corner (AGENTS.md): it imports `edge.tui` + `textual`, which the
runtime never does. The boundary is kept by never importing this module from the authoring
package's `__init__` or from runtime — only the CLI imports it, on demand.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from edge import dialogue
from edge.bigbang.generator import generate
from edge.config import (
    DEFAULT_CONFIG_PATH,
    load_config,
    load_config_with_sidecar,
    load_default_config,
)
from edge.core import dto
from edge.core.config import GameConfig
from edge.core.models import AlienSpecies, LocationRef, UniverseState
from edge.core.movement import shortest_path
from edge.core.rules import Converse, JoinGame, apply_result, reduce
from edge.server import session
from edge.tui.screens.contact import AlienContactScreen
from edge.tui.widgets import ClickableEntry

# Standing bands the harness can simulate. `wary` resolves to a neutral band in Phase 2 (it is
# authored but inert), so it is omitted; `allied` needs the species to carry an alliance.
BANDS: tuple[str, ...] = ("hostile", "neutral", "friendly", "allied")
_BAND_BASE = {"hostile": 0.10, "neutral": 0.50, "friendly": 0.90, "allied": 0.90}


class PlaytestService:
    """A duck-typed stand-in for `GameService` exposing just what `AlienContactScreen` touches.

    Wraps a synthetic universe (one player + one instance of every roster species) and applies
    the live **sim dials** (species / band / treaty / intel / force-enable) on each
    `contact_view`, delegating the actual projection to the real `session.contact_view`. The
    only mutation it makes on `apply` is to advance the dialogue recency ring (via the runtime
    `dialogue.speak`), so repeat lines rephrase exactly as in a real game; trade/barter/lead
    commands are accepted as no-ops (their latinum/attitude effects are irrelevant here).
    """

    def __init__(self, config: GameConfig, *, seed: int = 1, player_id: int = 1) -> None:
        self._config = config
        self.pid = player_id
        self.state = self._build_state(config, seed, player_id)
        # Instances are keyed 1..N in roster order; the contact screen targets a species id.
        self.species_ids: list[int] = sorted(self.state.species)
        self.current: int = self.species_ids[0]
        # Sim dials (mutated by the controls modal).
        self.band: str = "friendly"
        self.treaty: bool = False
        self.intel_on: bool = False
        self.force_enable: bool = False

    # --- construction --------------------------------------------------------

    def _build_state(self, config: GameConfig, seed: int, pid: int) -> UniverseState:
        assert config.roster is not None
        state = generate(config, seed)
        apply_result(state, reduce(state, pid, JoinGame(), config))  # what `helpers.enroll` does
        sector = state.ships[state.players[pid].ship_id].sector_id
        state.species.clear()  # a clean, fully-controlled cast (the big bang places none in P2)
        for i, sc in enumerate(config.roster.species, start=1):
            state.species[i] = AlienSpecies(
                id=i, roster_id=sc.id, name=sc.name, archetype_id=sc.archetype_id,
                sector_id=sector, home_band="Hub", tech_level=sc.tech_level,
                base_disposition=sc.disposition_center,
                disposition_center=sc.disposition_center,
                disposition_variance=sc.disposition_variance,
                alliance_id=sc.alliance_id, alliance_role=sc.alliance_role,
                threat_tier=sc.threat_tier, trade_posture=sc.trade_posture,
                treaty_mode=sc.treaty_mode, persona=sc.persona,
            )
        # Seed an attitude entry for every species so "Ask about…"/dossier list all the others.
        player = state.players[pid]
        state.players[pid] = dataclasses.replace(
            player, species_attitudes={sc.id: 0.0 for sc in config.roster.species})
        return state

    # --- the GameService surface the contact screen uses ---------------------

    @property
    def config(self) -> GameConfig:
        return self._config

    def contact_view(self, player_id: int, species_id: int,
                     active_context: str = "greeting",
                     active_subject: int | None = None) -> dto.ContactDTO:
        self._apply_dials(species_id)
        view = session.contact_view(self.state, player_id, species_id, self._config,
                                    active_context, active_subject)

        # Debug: Compute active context and matched "when" clause
        shown = (active_context if (active_context in dialogue._PEACEFUL_CONTEXTS
                                    or active_context.startswith(dialogue.BRANCH_PREFIX))
                 else "greeting")
        representative = session._representative_by_kind(self.state)
        sp = self.state.species[species_id]
        others = [
            rep for rid in sorted(self.state.players[player_id].species_attitudes)
            if rid != sp.roster_id and (rep := representative.get(rid)) is not None
        ]
        if shown == "dossier_other" and not others:
            shown = "greeting"

        player = self.state.players[player_id]
        ring = player.dialogue_recency.get((sp.roster_id, shown), ())
        rng = dialogue.encounter_rng(self.state.game.seed, sp.roster_id, shown, ring)

        from edge.dialogue.intel import pick_intel_target
        intel = pick_intel_target(self.state, player, sp, aliens=self._config.aliens)
        facts = None
        if shown == "offer_coordinates":
            facts = {"has_intel_target": intel is not None}

        entry = dialogue.entry_for(self._config.roster, sp, player, shown,
                                   aliens=self._config.aliens, rng=rng,
                                   treaty=self.treaty, facts=facts)

        debug_when_str = ""
        if entry is not None and entry.when:
            dumped = entry.when.model_dump(exclude_none=True)
            if dumped:
                debug_when_str = ", ".join(f"{k}={v}" for k, v in dumped.items())
            else:
                debug_when_str = "catch-all"
        else:
            debug_when_str = "catch-all"

        view = dataclasses.replace(view, debug_context=shown, debug_when=debug_when_str)

        return self._force(view) if self.force_enable else view


    def apply(self, player_id: int, command: object) -> tuple[object, ...]:
        # Only `Converse` matters for dialogue: advance the recency ring so repeats rephrase.
        if isinstance(command, Converse):
            self._advance_recency(command.species_id, command.context)
        return ()

    # --- sim dials -----------------------------------------------------------

    def _apply_dials(self, species_id: int) -> None:
        """Re-key the target species + player to realise the current band / intel before a view."""
        sp = self.state.species[species_id]
        allied = self.band == "allied" and sp.alliance_id is not None
        self.state.species[species_id] = dataclasses.replace(
            sp, base_disposition=_BAND_BASE[self.band])
        player = self.state.players[self.pid]
        self.state.players[self.pid] = dataclasses.replace(
            player, alliance_id=(sp.alliance_id if allied else None))
        ref = self._far_discovery() if (self.intel_on and self.band in ("friendly", "allied")) else None
        self.state.species_knowledge[sp.roster_id] = (ref,) if ref is not None else ()

    def _far_discovery(self) -> LocationRef | None:
        """A real, reachable, unvisited rare+ discovery to point a coordinate tip at (§6.7)."""
        player = self.state.players[self.pid]
        src = self.state.ships[player.ship_id].sector_id
        for d in self.state.discoveries.values():
            if (d.rarity_tier.value >= 3 and d.found_by is None
                    and d.sector_id not in player.explored_sectors
                    and shortest_path(self.state.adjacency, src, d.sector_id) is not None):
                return LocationRef("discovery", d.id, d.sector_id)
        return None

    def _advance_recency(self, species_id: int, context: str) -> None:
        sp = self.state.species.get(species_id)
        if sp is None or self._config.roster is None:
            return
        player = self.state.players[self.pid]
        ring = player.dialogue_recency.get((sp.roster_id, context), ())
        rng = dialogue.encounter_rng(self.state.game.seed, sp.roster_id, context, ring)
        facts = {"has_intel_target": bool(self.state.species_knowledge.get(sp.roster_id))}
        try:
            _text, new_ring = dialogue.speak(
                self._config.roster, sp, player, context, aliens=self._config.aliens,
                rng=rng, treaty=self.treaty, facts=facts)
        except Exception:
            return  # an un-resolvable context (e.g. a Phase-3 line) — leave the ring be
        recency = dict(player.dialogue_recency)
        recency[(sp.roster_id, context)] = new_ring
        self.state.players[self.pid] = dataclasses.replace(player, dialogue_recency=recency)

    @staticmethod
    def _force(view: dto.ContactDTO) -> dto.ContactDTO:
        """Rewrite every verb/choice to enabled so gated branches become traversable."""
        verbs = [dataclasses.replace(v, enabled=True, reason="") for v in view.verbs]
        choices = [dataclasses.replace(c, enabled=True, reason="") for c in view.choices]
        floor = [dataclasses.replace(v, enabled=True, reason="") for v in view.floor_verbs]
        return dataclasses.replace(view, verbs=verbs, choices=choices, floor_verbs=floor)

    # --- controls (mutators the modal calls) ---------------------------------

    def cycle_species(self, step: int) -> None:
        i = (self.species_ids.index(self.current) + step) % len(self.species_ids)
        self.current = self.species_ids[i]

    def cycle_band(self, step: int) -> None:
        self.band = BANDS[(BANDS.index(self.band) + step) % len(BANDS)]

    def toggle_treaty(self) -> None:
        self.treaty = not self.treaty

    def toggle_intel(self) -> None:
        self.intel_on = not self.intel_on

    def toggle_force_enable(self) -> None:
        self.force_enable = not self.force_enable

    def toggle_show_disabled(self) -> None:
        flag = not self._config.ui.show_disabled_options
        self._config = self._config.model_copy(
            update={"ui": self._config.ui.model_copy(update={"show_disabled_options": flag})})

    def select_species_by_roster(self, roster_id: str) -> bool:
        for sid in self.species_ids:
            if self.state.species[sid].roster_id == roster_id:
                self.current = sid
                return True
        return False

    def species_name(self, species_id: int) -> str:
        sp = self.state.species[species_id]
        return f"{sp.name} ({sp.roster_id}, {sp.persona})"


class PlaytestControls(ModalScreen[None]):
    """The dial board (F2): clickable rows that flip the harness sim state in place."""

    BINDINGS = [Binding("escape", "close", "Close"), Binding("f2", "close", "Close")]

    CSS = """
    PlaytestControls { align: center middle; }
    PlaytestControls #controls-box {
        width: 64; height: auto; padding: 1 2; border: round $primary; background: $surface;
    }
    PlaytestControls #controls-box Static.title { margin-bottom: 1; }
    PlaytestControls #controls-box Static.hint { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, service: PlaytestService) -> None:
        super().__init__()
        self._svc = service

    def compose(self) -> ComposeResult:
        s = self._svc

        def flag(on: bool) -> str:
            return "[green]on[/]" if on else "[dim]off[/]"

        with Vertical(id="controls-box"):
            yield Static("[b]Playtest controls[/]  [dim](Esc / F2 to close)[/]", classes="title")
            yield ClickableEntry(
                f"  [b]Species[/]   {s.species_name(s.current)}", dest="species")
            yield ClickableEntry(f"  [b]Standing[/]  [cyan]{s.band}[/]", dest="band")
            yield ClickableEntry(f"  [b]Treaty[/]    {flag(s.treaty)}", dest="treaty")
            yield ClickableEntry(f"  [b]Intel[/]     {flag(s.intel_on)}", dest="intel")
            yield ClickableEntry(
                f"  [b]Show disabled[/]  {flag(s.config.ui.show_disabled_options)}",
                dest="show_disabled")
            yield ClickableEntry(
                f"  [b]Force-enable & traverse[/]  {flag(s.force_enable)}", dest="force_enable")
            yield Static("[dim]Click a row to change it; close to apply to the conversation.[/]",
                         classes="hint")
        yield Footer()

    @on(ClickableEntry.Picked)
    async def _on_picked(self, msg: ClickableEntry.Picked) -> None:
        svc = self._svc
        match msg.dest:
            case "species":
                svc.cycle_species(1)
            case "band":
                svc.cycle_band(1)
            case "treaty":
                svc.toggle_treaty()
            case "intel":
                svc.toggle_intel()
            case "show_disabled":
                svc.toggle_show_disabled()
            case "force_enable":
                svc.toggle_force_enable()
        await self.recompose()

    def on_click(self, event: events.Click) -> None:
        # Click outside the box (on the backdrop, i.e. the screen itself) to dismiss; clicks on a
        # row or anywhere inside the box land on a child widget and are left to their own handlers.
        if self.get_widget_at(*event.screen_offset)[0] is self:
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class PlaytestApp(App[None]):
    """Hosts the real contact screen over the harness service; F2 opens the dial board."""

    TITLE = "Edge — dialogue playtest"
    BINDINGS = [
        Binding("f2", "controls", "Controls"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, service: PlaytestService) -> None:
        super().__init__()
        self._svc = service

    def on_mount(self) -> None:
        self._show_contact()

    def _show_contact(self) -> None:
        sid = self._svc.current
        # Break-contact (farewell / leave / Escape) opens the controls modal instead of leaving a
        # blank screen, so the tester lands somewhere they can pick another species/band.
        self.push_screen(AlienContactScreen(
            self._svc.contact_view(self._svc.pid, sid), self._svc, self._svc.pid, sid,
            on_exit=self.action_controls, playtest_mode=True))

    def action_controls(self) -> None:
        if isinstance(self.screen, PlaytestControls):
            return  # already open (e.g. a stray Escape) — don't stack duplicates
        self.push_screen(PlaytestControls(self._svc), self._after_controls)

    def _after_controls(self, _result: None) -> None:
        # Rebuild the contact screen so species/band/treaty/intel changes take effect.
        if isinstance(self.screen, AlienContactScreen):
            self.pop_screen()
        self._show_contact()


def _load(args: argparse.Namespace) -> GameConfig:
    if args.sidecar is not None:
        return load_config_with_sidecar(args.sidecar, args.config or DEFAULT_CONFIG_PATH)
    if args.config is not None:
        return load_config(args.config)
    return load_default_config()


def main(argv: list[str] | None = None) -> int:
    """`edge-playtest-dialogue` entry point — open the dialogue playtest TUI."""
    parser = argparse.ArgumentParser(
        prog="edge-playtest-dialogue",
        description="Play-test authored alien dialogue through the real contact screen.")
    parser.add_argument("--sidecar", type=Path, default=None,
                        help="a config/dialogue/*.yaml sidecar to splice onto the default roster")
    parser.add_argument("--config", type=Path, default=None,
                        help="game config to load (default: the bundled config/default.yaml)")
    parser.add_argument("--species", default=None,
                        help="roster id to start on (default: the first species)")
    parser.add_argument("--seed", type=int, default=1, help="universe seed (default: 1)")
    args = parser.parse_args(argv)

    config = _load(args)
    if config.roster is None or not config.roster.species:
        print("config has no species roster to play-test", file=sys.stderr)
        return 2
    service = PlaytestService(config, seed=args.seed)
    if args.species is not None and not service.select_species_by_roster(args.species):
        print(f"no such species {args.species!r} in roster", file=sys.stderr)
        return 2
    PlaytestApp(service).run()
    return 0


if __name__ == "__main__":  # pragma: no cover - manual launch
    raise SystemExit(main())
