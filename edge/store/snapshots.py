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
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any

from edge.bigbang.generator import generate
from edge.core.config import GameConfig
from edge.core.models import UniverseState
from edge.core.rules import ReduceResult, apply_result, reduce
from edge.store import codec
from edge.store.repo import RecordedCommand, RecordedMaintenance, Repository

_SAVE_VERSION = 2  # v2 adds the maintenance timeline (WP12)

# A pure cron reducer resolved by name (WP12). Injected by the caller so the store
# layer never imports the engine layer — `edge.engine.cron.resolve_cron` is the
# production resolver passed in by the server's `load_game`.
CronResolver = Callable[[str], Callable[[UniverseState, GameConfig], ReduceResult]]


@dataclass(frozen=True)
class SaveBundle:
    seed: int
    config_version: int
    created_at: str
    commands: list[RecordedCommand]
    maintenance: list[RecordedMaintenance] = field(default_factory=list)


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
        "starbases": state.starbases,
        "discoveries": state.discoveries,
        "ships": state.ships,
        "players": state.players,
        "alliances": state.alliances,
        "species": state.species,
    }
    blob = json.dumps(_canonical(snapshot), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def rebuild(config: GameConfig, seed: int, commands: list[RecordedCommand], *,
            created_at: str = "1970-01-01T00:00:00Z",
            maintenance: list[RecordedMaintenance] | None = None,
            cron_resolver: CronResolver | None = None) -> UniverseState:
    """Regenerate the universe from the seed and replay the merged timeline (§3, WP12).

    Player commands and engine-cron firings (`maintenance`) form one total order:
    each maintenance tick replays right after the command whose seq it recorded
    (`after_command_seq`, with 0 meaning "before any command"), in its own seq
    order. Re-running the pure cron reducer — never storing its derived effect —
    keeps the `(seed, log)` determinism rail and `state_hash` honest.
    """
    state = generate(config, seed, created_at=created_at)
    by_after: dict[int, list[RecordedMaintenance]] = defaultdict(list)
    for m in maintenance or []:
        by_after[m.after_command_seq].append(m)
    if by_after and cron_resolver is None:
        raise ValueError("maintenance records require a cron_resolver to replay")

    def run_maintenance(after_seq: int) -> None:
        for m in sorted(by_after.get(after_seq, ()), key=lambda r: r.seq):
            assert cron_resolver is not None  # guarded above when by_after is non-empty
            apply_result(state, cron_resolver(m.cron_name)(state, config))

    run_maintenance(0)
    for record in commands:
        apply_result(state, reduce(state, record.player_id, record.command, config))
        run_maintenance(record.seq)
    return state


def rebuild_from_bundle(config: GameConfig, bundle: SaveBundle, *,
                        cron_resolver: CronResolver | None = None) -> UniverseState:
    return rebuild(config, bundle.seed, bundle.commands, created_at=bundle.created_at,
                   maintenance=bundle.maintenance, cron_resolver=cron_resolver)


def export_save(repo: Repository) -> bytes:
    """Export a portable, gzipped-JSON save (meta + command log)."""
    meta = repo.load_meta()
    commands = []
    for record in repo.load_commands():
        type_, payload = codec.encode_command(record.command)
        commands.append({"seq": record.seq, "player_id": record.player_id,
                         "type": type_, "payload": payload})
    maintenance = [
        {"seq": m.seq, "after_command_seq": m.after_command_seq,
         "cron_name": m.cron_name, "tick": m.tick}
        for m in repo.load_maintenance()
    ]
    bundle = {
        "save_version": _SAVE_VERSION,
        "seed": meta.seed,
        "config_version": meta.config_version,
        "created_at": meta.created_at,
        "commands": commands,
        "maintenance": maintenance,
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
    maintenance = [
        RecordedMaintenance(seq=m["seq"], after_command_seq=m["after_command_seq"],
                            cron_name=m["cron_name"], tick=m["tick"])
        for m in raw.get("maintenance", [])  # v1 saves had no maintenance timeline
    ]
    return SaveBundle(seed=raw["seed"], config_version=raw["config_version"],
                      created_at=raw["created_at"], commands=commands, maintenance=maintenance)
