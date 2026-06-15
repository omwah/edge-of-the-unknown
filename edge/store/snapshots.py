"""Save integrity: state hashing, replay-rebuild, and portable export (§3, §12).

The canonical save is `(seed, config_version, command log)`: a universe is
regenerated from the seed and the command log replayed to reconstruct live state
(`rebuild`). `state_hash` gives a deterministic fingerprint for golden-master
tests — replaying the same log against the same seed must reproduce the same
hash. `export_save`/`import_save` are the gzipped-JSON portable save (the command
log rather than a dump of every sector, since state is reproducible from it).
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any

from edge.bigbang.generator import generate
from edge.core.config import GameConfig
from edge.core.models import UniverseState
from edge.core.rules import apply_result, reduce
from edge.store import codec
from edge.store.repo import RecordedCommand, Repository

_SAVE_VERSION = 1


@dataclass(frozen=True)
class SaveBundle:
    seed: int
    config_version: int
    created_at: str
    commands: list[RecordedCommand]


def _canonical(obj: Any) -> Any:
    """Recursively convert an entity tree into a JSON-stable, comparable form."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _canonical(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (set, frozenset)):
        return sorted(_canonical(x) for x in obj)
    if isinstance(obj, (list, tuple)):
        return [_canonical(x) for x in obj]
    if isinstance(obj, dict):
        return {str(_canonical(k)): _canonical(v) for k, v in obj.items()}
    return obj


def state_hash(state: UniverseState) -> str:
    """A deterministic fingerprint of the live entity state (RNG/adjacency excluded)."""
    snapshot = {
        "game": state.game,
        "regions": state.regions,
        "sectors": state.sectors,
        "ports": state.ports,
        "planets": state.planets,
        "ships": state.ships,
        "players": state.players,
        "alliances": state.alliances,
    }
    blob = json.dumps(_canonical(snapshot), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def rebuild(config: GameConfig, seed: int, commands: list[RecordedCommand], *,
            created_at: str = "1970-01-01T00:00:00Z") -> UniverseState:
    """Regenerate the universe from the seed and replay the command log (§3)."""
    state = generate(config, seed, created_at=created_at)
    for record in commands:
        apply_result(state, reduce(state, record.player_id, record.command, config))
    return state


def rebuild_from_bundle(config: GameConfig, bundle: SaveBundle) -> UniverseState:
    return rebuild(config, bundle.seed, bundle.commands, created_at=bundle.created_at)


def export_save(repo: Repository) -> bytes:
    """Export a portable, gzipped-JSON save (meta + command log)."""
    meta = repo.load_meta()
    commands = []
    for record in repo.load_commands():
        type_, payload = codec.encode_command(record.command)
        commands.append({"seq": record.seq, "player_id": record.player_id,
                         "type": type_, "payload": payload})
    bundle = {
        "save_version": _SAVE_VERSION,
        "seed": meta.seed,
        "config_version": meta.config_version,
        "created_at": meta.created_at,
        "commands": commands,
    }
    return gzip.compress(json.dumps(bundle).encode("utf-8"))


def import_save(data: bytes) -> SaveBundle:
    """Parse a gzipped-JSON save back into a `SaveBundle`."""
    raw = json.loads(gzip.decompress(data).decode("utf-8"))
    commands = [
        RecordedCommand(seq=c["seq"], player_id=c["player_id"],
                        command=codec.decode_command(c["type"], c["payload"]))
        for c in raw["commands"]
    ]
    return SaveBundle(seed=raw["seed"], config_version=raw["config_version"],
                      created_at=raw["created_at"], commands=commands)
