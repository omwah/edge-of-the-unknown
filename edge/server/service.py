"""The in-process game service (DESIGN §3).

`GameService` owns the authoritative `UniverseState` and a `Repository`. It is
the single entry point the TUI (or a bot, or later a network client) uses:
submit a command, the service validates and reduces it through `core.rules`,
persists the command + resulting events durably, then applies the delta to memory
and returns the events. Read access is only through the fog-of-war `*_view`
projections (`session`) — the TUI never touches core state directly.

Single-player embeds this in-process (DESIGN §3); a new game generates a fresh
universe, a loaded game reconstructs state by replaying the saved command log.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from edge.bigbang.generator import generate
from edge.core import dto
from edge.core.config import GameConfig
from edge.core.enums import Commodity
from edge.core.events import Event
from edge.core.models import UniverseState
from edge.core.rules import (
    Command, InstallComponent, JoinGame, ReduceResult, SwapComponent, apply_result, reduce,
)
from edge.dialogue import dialogue_fingerprint
from edge.engine.cron import resolve_cron
from edge.server import session
from edge.store.repo import EngineState, Repository, StateCheckpoint
from edge.store.snapshots import rebuild, replay_tail, state_hash
from edge.store.state_codec import (
    CHECKPOINT_CODEC_VERSION,
    CheckpointCodecError,
    encode_state,
    payload_checksum,
    restore_state,
)

_LOG = logging.getLogger(__name__)
_CHECKPOINT_INTERVAL = 250
LoadProgress = Callable[[str, int, int], None]


class DialogueConfigMismatchError(RuntimeError):
    """The save was made with a different dialogue pack; replay would fail mid-way.

    `_converse_choice` validates choice indices against the live dialogue pack. If the
    sidecar has changed since the save was recorded, a stored `Converse(choice_index=N)`
    may now reference a context or index that no longer exists.  Start a new game.
    """


class GameService:
    def __init__(self, state: UniverseState, config: GameConfig, repo: Repository, *,
                 last_command_seq: int = 0, last_maintenance_seq: int = 0,
                 mutations_since_checkpoint: int = 0) -> None:
        self._state = state
        self._config = config
        self._repo = repo
        # The latest command_log seq applied — the `after_command_seq` stamped on a
        # maintenance firing so replay interleaves it correctly with commands (WP12).
        self._last_command_seq = last_command_seq
        self._last_maintenance_seq = last_maintenance_seq
        self._mutations_since_checkpoint = mutations_since_checkpoint
        # The broadcast seam (WP65): invoked with the (seq, event) pairs just persisted by
        # every `apply` *and* every `apply_maintenance`, so a subscriber (the LocalClient's
        # ticker stream, or the GameServer's fan-out) sees command- and time-driven events on
        # one channel. None in the bare in-process case (tests, bots reading apply results).
        self.on_events: Callable[[Sequence[tuple[int, Event]]], None] | None = None

    @classmethod
    def new_game(cls, config: GameConfig, seed: int, repo: Repository, *,
                 created_at: str = "1970-01-01T00:00:00Z") -> GameService:
        """Generate a fresh universe, persist its meta, enroll player 1, and return.

        The big bang seeds only the shared world; the player is enrolled by appending
        a `JoinGame` command (DESIGN §3), so it lands in the durable log and `load_game`
        replays it to reconstruct the player deterministically — the same path a second
        player would join by in multiplayer.
        """
        state = generate(config, seed, created_at=created_at)
        fp = dialogue_fingerprint(config.roster) if config.roster else None
        repo.save_meta(state.game, dialogue_fingerprint=fp)
        service = cls(state, config, repo)
        service.apply(1, JoinGame())
        return service

    @classmethod
    def load_game(
        cls,
        config: GameConfig,
        repo: Repository,
        *,
        progress: LoadProgress | None = None,
    ) -> GameService:
        """Restore a checkpoint and replay its bounded log tail (§3, §12).

        Raises `DialogueConfigMismatchError` if the save's dialogue fingerprint differs from
        the current config — catching this before replay avoids a mid-way crash in the
        command-log reducer when a stored `Converse(choice_index=N)` no longer resolves.
        Legacy saves without a fingerprint (None) are loaded without the check.
        """
        meta = repo.load_meta()
        if meta.dialogue_fingerprint is not None and config.roster is not None:
            current_fp = dialogue_fingerprint(config.roster)
            if current_fp != meta.dialogue_fingerprint:
                raise DialogueConfigMismatchError(
                    "This save used a different dialogue pack — start a new game "
                    "to use the current config."
                )
        command_head, maintenance_head = repo.log_positions()
        total_records = command_head + maintenance_head
        if progress is not None:
            progress("Reading save", 0, total_records)
        checkpoint = repo.load_checkpoint()
        state: UniverseState | None = None
        command_cursor = 0
        maintenance_cursor = 0
        if (
            checkpoint is not None
            and checkpoint.codec_version == CHECKPOINT_CODEC_VERSION
            and checkpoint.config_version == config.config_version
            and 0 <= checkpoint.command_seq <= command_head
            and 0 <= checkpoint.maintenance_seq <= maintenance_head
            and hmac.compare_digest(
                checkpoint.payload_checksum, payload_checksum(checkpoint.payload)
            )
        ):
            try:
                base = generate(config, meta.seed, created_at=meta.created_at)
                candidate = restore_state(base, checkpoint.payload)
                if not hmac.compare_digest(state_hash(candidate), checkpoint.state_hash):
                    raise CheckpointCodecError("checkpoint state hash does not match")
                state = candidate
                command_cursor = checkpoint.command_seq
                maintenance_cursor = checkpoint.maintenance_seq
                if progress is not None:
                    progress(
                        "Restored checkpoint",
                        command_cursor + maintenance_cursor,
                        total_records,
                    )
            except (CheckpointCodecError, TypeError, ValueError, KeyError, AttributeError):
                _LOG.warning("Ignoring invalid state checkpoint; rebuilding from logs",
                             exc_info=True)

        commands = repo.load_commands_after(command_cursor)
        maintenance = repo.load_maintenance_after(maintenance_cursor)
        replay_offset = command_cursor + maintenance_cursor

        def report_replay(done: int, _tail_total: int) -> None:
            if progress is not None:
                progress("Replaying recent history", replay_offset + done, total_records)

        if state is None:
            state = rebuild(
                config,
                meta.seed,
                commands,
                created_at=meta.created_at,
                maintenance=maintenance,
                cron_resolver=resolve_cron,
                progress=report_replay,
            )
        else:
            replay_tail(
                state,
                config,
                commands,
                maintenance=maintenance,
                cron_resolver=resolve_cron,
                after_command_seq=command_cursor,
                progress=report_replay,
            )
        service = cls(
            state,
            config,
            repo,
            last_command_seq=command_head,
            last_maintenance_seq=maintenance_head,
            mutations_since_checkpoint=len(commands) + len(maintenance),
        )
        if checkpoint is None or commands or maintenance:
            service.checkpoint()
        if progress is not None:
            progress("Ready", total_records, total_records)
        return service

    def checkpoint(self) -> None:
        """Atomically replace the disposable load checkpoint at the current log cursors."""
        try:
            payload, checksum = encode_state(self._state)
            self._repo.save_checkpoint(
                StateCheckpoint(
                    codec_version=CHECKPOINT_CODEC_VERSION,
                    config_version=self._config.config_version,
                    command_seq=self._last_command_seq,
                    maintenance_seq=self._last_maintenance_seq,
                    state_hash=state_hash(self._state),
                    payload_checksum=checksum,
                    payload=payload,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception:
            # Logs have already committed and remain the canonical save.  A
            # checkpoint failure may slow the next load but must not reject play.
            _LOG.exception("Could not write state checkpoint; durable logs are intact")
        finally:
            self._mutations_since_checkpoint = 0

    def _maybe_checkpoint(self) -> None:
        self._mutations_since_checkpoint += 1
        if self._mutations_since_checkpoint >= _CHECKPOINT_INTERVAL:
            self.checkpoint()

    def apply(self, player_id: int, command: Command) -> tuple[Event, ...]:
        """Validate, persist, and apply a command; return the events it produced.

        Reduction happens first and may raise (a rejected command persists
        nothing); then the command + events are recorded durably before the delta
        touches memory, so a persistence failure can't desync the in-memory state.
        """
        result = reduce(self._state, player_id, command, self._config)
        self._last_command_seq = self._repo.append_command(player_id, command)
        appended = [(self._repo.append_event(event), event) for event in result.events]
        apply_result(self._state, result)
        self._maybe_checkpoint()
        if self.on_events is not None and appended:
            self.on_events(appended)
        return result.events

    def apply_maintenance(self, result: ReduceResult, *,
                          cron_name: str | None = None, tick: int = 0) -> None:
        """Apply an engine cron's result: upsert entities + persist its durable trail.

        Unlike `apply`, this records no command_log entry — maintenance is
        time-driven, not a player action. When `cron_name` is given (the ticker
        path), the firing is recorded as a `MaintenanceTick` stamped with the last
        command seq, so reload replays it in the right order (WP12); the resulting
        events are always persisted to the event rail.
        """
        if cron_name is not None:
            self._last_maintenance_seq = self._repo.append_maintenance(
                cron_name, tick, self._last_command_seq
            )
        apply_result(self._state, result)
        appended = [(self._repo.append_event(event), event) for event in result.events]
        if cron_name is not None:
            self._maybe_checkpoint()
        if self.on_events is not None and appended:
            self.on_events(appended)

    def events_since(self, seq: int) -> list[tuple[int, Event]]:
        """Persisted events after `seq`, each with its seq — the reconnect catch-up buffer (WP65).

        The durable rail is the replay buffer: a client that dropped resumes by asking for
        everything after the last seq it saw, and the caller re-applies the same fog filter it
        applies to a live push, so catch-up over a seq window equals the live stream over it.
        """
        return self._repo.load_events_since(seq)

    def save_engine_state(self, tick: int, schedule: dict[str, int]) -> None:
        """Persist the ticker schedule so a reload resumes mid-interval (WP12)."""
        self._repo.save_engine_state(tick, schedule)

    def load_engine_state(self) -> EngineState | None:
        """The saved ticker schedule, or None for a fresh game (WP12)."""
        return self._repo.load_engine_state()

    # --- read-only fog-of-war projections (§3) -------------------------------

    def game_view(self, player_id: int) -> dto.GameState:
        return session.game_view(self._state, player_id, self._config)

    def port_view(self, player_id: int, port_id: int) -> dto.PortDTO:
        return session.port_view(self._state, player_id, port_id, self._config)

    def current_port_view(self, player_id: int) -> dto.PortDTO | None:
        """The trade view for the port in the player's current sector, if any."""
        ship = self._state.ships[self._state.players[player_id].ship_id]
        port = self._state.port_in_sector(ship.sector_id)
        if port is None:
            return None
        return session.port_view(self._state, player_id, port.id, self._config)

    def haggle_quote(self, player_id: int, commodity: Commodity, counter_price: int) -> dto.HaggleQuote:
        """An advisory read on a counter-offer for the docked port (§8). Commits nothing."""
        return session.haggle_quote(self._state, player_id, commodity, counter_price, self._config)

    def map_view(self, player_id: int, *, route_dest: int | None = None,
                 full_graph: bool = False, fit_width: int | None = None) -> dto.LocalMapDTO:
        return session.map_view(self._state, player_id, route_dest=route_dest,
                                full_graph=full_graph, config=self._config, fit_width=fit_width)

    def computer_view(self, player_id: int) -> dto.ComputerDTO:
        return session.computer_view(self._state, player_id, self._config)

    def tavern_view(self, player_id: int) -> dto.TavernDTO:
        """The Stardock tavern: rumors, bounty board, noticeboard (§14, WP58)."""
        return session.tavern_view(self._state, player_id, self._config)

    def corp_view(self, player_id: int) -> dto.CorpDTO | None:
        """The player's corporation for the `T` screen — roster, bank, holdings, wars (§4, WP66)."""
        return session.corp_view(self._state, player_id, self._config)

    def market_view(self, player_id: int) -> dto.MarketDTO:
        """The order-book Market tab: explored ports' open books + last settlement (§8, WP48)."""
        return session.market_view(self._state, self._repo.load_events(), self._config, player_id)

    def route_view(self, player_id: int, dst_sector: int, *,
                   full_graph: bool = False) -> dto.RouteDTO:
        return session.route_view(self._state, player_id, dst_sector, self._config,
                                  full_graph=full_graph)

    def route_legs_view(self, player_id: int, waypoints: list[int]) -> dto.RouteDTO:
        return session.route_legs_view(self._state, player_id, waypoints, self._config)

    def engine_room_view(self, player_id: int) -> dto.EngineRoomDTO:
        return session.engine_room_view(self._state, player_id, self._config)

    def engine_room_preview(
        self, player_id: int, command: InstallComponent | SwapComponent,
    ) -> dto.EngineRoomPreviewDTO:
        return session.engine_room_preview(self._state, player_id, command, self._config)

    def stardock_view(self, player_id: int) -> dto.StardockDTO:
        return session.stardock_view(self._state, player_id, self._config)

    def territory_view(self, player_id: int) -> dto.TerritoryDTO:
        """Carried territory stock + devices for the Deploy screen (§10/§14, WP72)."""
        return session.territory_view(self._state, player_id, self._config)

    def starbase_view(self, player_id: int, starbase_id: int) -> dto.StarbaseDTO:
        """The unified base view — identity, station ops, market, services (§4.2, WP79)."""
        return session.starbase_view(self._state, player_id, starbase_id, self._config)

    def current_starbase_view(self, player_id: int) -> dto.StarbaseDTO | None:
        """The base view for the player's current sector, if a base is present."""
        from edge.core.starbases import base_in_sector

        ship = self._state.ships[self._state.players[player_id].ship_id]
        base = base_in_sector(self._state, ship.sector_id)
        if base is None:
            return None
        return session.starbase_view(self._state, player_id, base.id, self._config)

    def planet_view(self, player_id: int, planet_id: int) -> dto.PlanetDTO:
        return session.planet_view(self._state, player_id, planet_id, self._config)

    def current_planet_view(self, player_id: int) -> dto.PlanetDTO | None:
        """The orbit view for a planet in the player's current sector, if any."""
        ship = self._state.ships[self._state.players[player_id].ship_id]
        planet = next((p for p in self._state.planets.values() if p.sector_id == ship.sector_id), None)
        if planet is None:
            return None
        return session.planet_view(self._state, player_id, planet.id, self._config)

    def ground_operation_view(
        self, player_id: int, *, viewport_x: int = 0, viewport_y: int = 0,
        viewport_width: int | None = None, viewport_height: int | None = None,
        selected_actor_id: int | None = None,
    ) -> dto.SurveyExpeditionDTO | dto.AssaultExpeditionDTO | None:
        """The active operation's fog-safe viewport, or ``None`` while in orbit."""
        return session.ground_operation_view(
            self._state, player_id, self._config,
            viewport_x=viewport_x, viewport_y=viewport_y,
            viewport_width=viewport_width, viewport_height=viewport_height,
            selected_actor_id=selected_actor_id,
        )

    def contact_view(self, player_id: int, species_id: int,
                     active_context: str = "greeting",
                     active_subject: int | None = None) -> dto.ContactDTO:
        """The alien-contact screen for a species in the player's sector (§6, WP9, WP17)."""
        return session.contact_view(self._state, player_id, species_id, self._config,
                                    active_context, active_subject)

    def species_in_sector(self, player_id: int) -> int | None:
        """The id of the (lowest-id) species in the player's sector, or None (§6, WP9)."""
        player = self._state.players[player_id]
        sector_id = self._state.ships[player.ship_id].sector_id
        species = next((s for s in sorted(self._state.species.values(), key=lambda s: s.id)
                        if s.sector_id == sector_id), None)
        return species.id if species is not None else None

    def current_contact_view(self, player_id: int) -> dto.ContactDTO | None:
        """The contact view for the (first) species in the player's sector, if any."""
        species_id = self.species_in_sector(player_id)
        if species_id is None:
            return None
        return session.contact_view(self._state, player_id, species_id, self._config)

    def encounter_view(self, player_id: int) -> dto.EncounterDTO | None:
        """The live hostile encounter (§10, WP24/25), or None when not engaged."""
        return session.encounter_view(self._state, player_id, self._config)

    def leads_view(self, player_id: int) -> list[dto.LeadDTO]:
        """The player's accepted coordinate tips, as plottable Computer-screen rows (§6.7)."""
        return session.leads_view(self._state, player_id, self._config)

    def messages_view(self, player_id: int) -> dto.MessagesDTO:
        """The durable event log, newest first (§11, §12)."""
        return session.messages_view(self._state, self._repo.load_events(), self._config, player_id)

    def describe_event(self, event: Event) -> str:
        """Render one event for the live ticker, with a spatial sector gutter (§5.1, §11).

        Wraps `session.format_log_line` so the TUI gets the leading `S{spatial}` sector tag
        and display ids without reaching into core state. Returns "" for non-player-facing
        events.
        """
        return session.format_log_line(event, self._state)

    def resolve_display_id(self, shown: int) -> int | None:
        """Map a player-typed spatial id (§5.1) back to its internal sector id.

        Identity when no spatial ids exist (the UI showed internal ids), else the
        inverse of `spatial_ids`, or `None` if the number names no sector.
        """
        spatial = self._state.spatial_ids
        if not spatial:
            return shown
        return {v: k for k, v in spatial.items()}.get(shown)

    @property
    def state(self) -> UniverseState:
        """The authoritative state (engine/tests only — not for the TUI)."""
        return self._state

    @property
    def config(self) -> GameConfig:
        return self._config
