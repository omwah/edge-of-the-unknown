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

from edge.bigbang.generator import generate
from edge.core import dto
from edge.core.config import GameConfig
from edge.core.events import Event
from edge.core.models import UniverseState
from edge.core.rules import Command, ReduceResult, apply_result, reduce
from edge.server import session
from edge.store.repo import Repository
from edge.store.snapshots import rebuild


class GameService:
    def __init__(self, state: UniverseState, config: GameConfig, repo: Repository) -> None:
        self._state = state
        self._config = config
        self._repo = repo

    @classmethod
    def new_game(cls, config: GameConfig, seed: int, repo: Repository, *,
                 created_at: str = "1970-01-01T00:00:00Z") -> GameService:
        """Generate a fresh universe, persist its meta, and return a service."""
        state = generate(config, seed, created_at=created_at)
        repo.save_meta(state.game)
        return cls(state, config, repo)

    @classmethod
    def load_game(cls, config: GameConfig, repo: Repository) -> GameService:
        """Reconstruct a saved game by replaying its command log (§3)."""
        meta = repo.load_meta()
        state = rebuild(config, meta.seed, repo.load_commands(), created_at=meta.created_at)
        return cls(state, config, repo)

    def apply(self, player_id: int, command: Command) -> tuple[Event, ...]:
        """Validate, persist, and apply a command; return the events it produced.

        Reduction happens first and may raise (a rejected command persists
        nothing); then the command + events are recorded durably before the delta
        touches memory, so a persistence failure can't desync the in-memory state.
        """
        result = reduce(self._state, player_id, command, self._config)
        self._repo.append_command(player_id, command)
        for event in result.events:
            self._repo.append_event(event)
        apply_result(self._state, result)
        return result.events

    def apply_maintenance(self, result: ReduceResult) -> None:
        """Apply an engine cron's result: upsert entities + persist its events.

        Unlike `apply`, this records no command_log entry — maintenance is
        time-driven, not a player action — only the resulting events.
        """
        apply_result(self._state, result)
        for event in result.events:
            self._repo.append_event(event)

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

    def map_view(self, player_id: int) -> dto.MapDTO:
        return session.map_view(self._state, player_id)

    def computer_view(self, player_id: int) -> dto.ComputerDTO:
        return session.computer_view(self._state, player_id, self._config)

    def messages_view(self, player_id: int) -> dto.MessagesDTO:
        """The durable event log + opening signpost, newest first (§11, §12)."""
        return session.messages_view(self._state, self._repo.load_events())

    def intro_line(self, player_id: int) -> str | None:
        """The opening StarDock signpost for the game-screen ticker (WP-B)."""
        return session.stardock_signpost(self._state)

    @property
    def state(self) -> UniverseState:
        """The authoritative state (engine/tests only — not for the TUI)."""
        return self._state

    @property
    def config(self) -> GameConfig:
        return self._config
