"""CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--stats] [--render DIR]`.

A dev entrypoint that generates a universe from the default config and prints a
text report (`--stats`), lists populated items (`--list ports planets …`), plots
a route between two sectors (`--route SRC DST`, by internal *or* spatial id), writes
an interactive web topology inspector (`--render DIR`, §5), and/or dumps just the
visualization payload as JSON (`--dump-json PATH`).

Generation parameters can be overridden from the command line without editing the
config: `--mode`, plus the shared knobs (`--cluster-min/-max`,
`--intra-group-degree`, `--inter-group-degree`, `--one-way-chance`,
`--core-sector-count`, `--home-cluster-min/-max`) and the trunk-only
`--bridges-min/-max` (which land in the active mode's `topology.<mode>` block).

`--save PATH` inspects an **existing game** instead of a fresh seed, rebuilt from its
command log the same way the server loads it. That is how the listings show state a
big bang never seeds — colonists, citadels, garrisons, treasuries, player holdings.

Layering note: `edge.bigbang` the *library* imports nothing from `store`/`engine`
(the downward-only rule, AGENTS.md). This module is the CLI shell that composes
layers, and its save loading is imported **lazily inside the `--save` branch**, so
importing `edge.bigbang` as a library still never pulls the persistence layers in.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from edge.bigbang.generator import generate, summarize
from edge.bigbang.inspect import LIST_CATEGORIES, format_route, list_items
from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.models import UniverseState

#: Generation flags that a `--save` run cannot honour — the universe comes from the
#: save's own seed and config, so silently ignoring these would be a lie.
_GENERATION_FLAGS = (
    "seed", "sectors", "mode", "cluster_min", "cluster_max", "intra_group_degree",
    "inter_group_degree", "one_way_chance", "core_sector_count", "home_cluster_min",
    "home_cluster_max", "bridges_min", "bridges_max",
)


def _load_save(path: Path, config: GameConfig) -> tuple[UniverseState, int]:
    """Rebuild a saved universe from `path`; return it with the seed it came from.

    Accepts either form the game writes: a SQLite slot, or a portable gzipped-JSON
    bundle (`export_save`). Both replay the durable command log through the real
    reducers, so what you inspect is exactly what the server would load.
    """
    from edge.engine.cron import resolve_cron
    from edge.store.repo import SqliteRepository
    from edge.store.snapshots import import_save, rebuild, rebuild_from_bundle

    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":  # gzip magic — a portable save bundle
        bundle = import_save(data)
        _check_config_version(bundle.config_version, config)
        return rebuild_from_bundle(config, bundle, cron_resolver=resolve_cron), bundle.seed
    # Otherwise a SQLite slot. `SqliteRepository` applies the schema on open, so a
    # non-save file would come back as an empty universe rather than an error — the
    # caller checks the path exists, and a missing `meta` row raises from `load_meta`.
    with SqliteRepository(path) as repo:
        meta = repo.load_meta()
        _check_config_version(meta.config_version, config)
        state = rebuild(config, meta.seed, repo.load_commands(), created_at=meta.created_at,
                        maintenance=repo.load_maintenance(), cron_resolver=resolve_cron)
    return state, meta.seed


class SaveConfigMismatch(Exception):
    """A save written under a different config than the one this build would replay it with."""


def _check_config_version(save_version: int, config: GameConfig) -> None:
    """Refuse a save from another config epoch before replay turns it into nonsense.

    A save is `(seed, config_version, command log)`: the universe is *regenerated* from
    the seed against the **current** config, then the log replayed onto it. If the config
    has moved since, the regenerated universe differs and the log lands on the wrong
    world — surfacing as an arbitrary mid-replay rules error ("that service is offered
    only at a Stardock") that says nothing about the real cause. Catch it up front.
    """
    if save_version != config.config_version:
        raise SaveConfigMismatch(
            f"save is config_version {save_version}, this build is "
            f"{config.config_version} — the universe would regenerate differently and the "
            f"command log would replay onto the wrong world"
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="edge.bigbang")
    parser.add_argument("--seed", type=int, default=None, help="override the config seed")
    parser.add_argument("--sectors", type=int, default=None, help="override sector_count")
    parser.add_argument(
        "--mode", choices=("trunk", "expansive", "planar", "mesh", "spiral"), default=None,
        help="override topology_mode (trunk | expansive | planar | mesh | spiral, §5)",
    )
    # Generation-parameter overrides. The shared knobs apply to every mode; --bridges-min/max
    # are trunk-only and land in the active mode's topology block (a no-op for the others).
    gen = parser.add_argument_group("generation overrides (override config bigbang params)")
    gen.add_argument("--cluster-min", type=int, default=None, help="override cluster_min (shared)")
    gen.add_argument("--cluster-max", type=int, default=None, help="override cluster_max (shared)")
    gen.add_argument("--intra-group-degree", type=float, default=None, help="override intra_group_degree (shared)")
    gen.add_argument("--inter-group-degree", type=float, default=None, help="override inter_group_degree (shared)")
    gen.add_argument("--one-way-chance", type=float, default=None, help="override one_way_chance (shared)")
    gen.add_argument("--core-sector-count", type=int, default=None, help="override core_sector_count (shared)")
    gen.add_argument("--home-cluster-min", type=int, default=None, help="override home_cluster_min (shared)")
    gen.add_argument("--home-cluster-max", type=int, default=None, help="override home_cluster_max (shared)")
    gen.add_argument("--bridges-min", type=int, default=None, help="override topology.<mode>.bridges_min (trunk-only)")
    gen.add_argument("--bridges-max", type=int, default=None, help="override topology.<mode>.bridges_max (trunk-only)")
    parser.add_argument("--stats", action="store_true", help="print a universe report")
    parser.add_argument(
        "--list", nargs="+", metavar="CATEGORY", choices=(*LIST_CATEGORIES, "all"),
        help=f"list populated items: {', '.join(LIST_CATEGORIES)}, or all",
    )
    parser.add_argument(
        "--route", nargs=2, metavar=("SRC", "DST"),
        help="plot the route between two sectors (internal or spatial id; i/s prefix forces)",
    )
    parser.add_argument(
        "--render", metavar="DIR", default=None,
        help="write an interactive web topology inspector (index.html + universe.json)",
    )
    parser.add_argument(
        "--dump-json", metavar="PATH", default=None,
        help="write just the visualization payload as JSON (no HTML)",
    )
    parser.add_argument(
        "--save", metavar="PATH", default=None,
        help="inspect an existing game (SQLite slot or portable save) instead of a fresh "
             "seed — the only way listings show colonists, citadels, garrisons and holdings",
    )
    import sys
    args = parser.parse_args()
    if len(sys.argv) == 1:
        args.stats = True

    config = load_default_config()
    if args.save is not None:
        conflicting = [f"--{f.replace('_', '-')}" for f in _GENERATION_FLAGS
                       if getattr(args, f) is not None]
        if conflicting:
            parser.error(f"--save inspects an existing universe, so it cannot be combined "
                         f"with generation overrides ({', '.join(conflicting)})")
        save_path = Path(args.save)
        if not save_path.is_file():
            parser.error(f"no save file at {save_path}")
        try:
            state, seed = _load_save(save_path, config)
        except Exception as exc:  # a corrupt/foreign file, or a log this build cannot replay
            parser.error(f"could not load {save_path}: {exc}")
        _run_reports(args, parser, state, seed, config, source=f"save {save_path}")
        return

    bigbang_overrides: dict[str, object] = {}
    if args.sectors is not None:
        bigbang_overrides["sector_count"] = args.sectors
    if args.mode is not None:
        bigbang_overrides["topology_mode"] = args.mode
    # Shared knobs map straight onto the flat BigBangConfig fields.
    for field in (
        "cluster_min", "cluster_max", "intra_group_degree", "inter_group_degree",
        "one_way_chance", "core_sector_count", "home_cluster_min", "home_cluster_max",
    ):
        value = getattr(args, field)
        if value is not None:
            bigbang_overrides[field] = value
    # --bridges-min/max live in the selected mode's topology block, not the top level.
    topo_overrides = {k: v for k, v in (
        ("bridges_min", args.bridges_min), ("bridges_max", args.bridges_max),
    ) if v is not None}
    if topo_overrides:
        mode = args.mode if args.mode is not None else config.bigbang.topology_mode
        block = getattr(config.bigbang.topology, mode).model_copy(update=topo_overrides)
        bigbang_overrides["topology"] = config.bigbang.topology.model_copy(update={mode: block})
    if bigbang_overrides:
        config = config.model_copy(
            update={"bigbang": config.bigbang.model_copy(update=bigbang_overrides)}
        )
    # --seed overrides the config default; fall back to it (then 1) when omitted.
    seed = args.seed if args.seed is not None else (config.seed if config.seed is not None else 1)
    state = generate(config, seed)
    _run_reports(args, parser, state, seed, config, source=None)


def _run_reports(args: argparse.Namespace, parser: argparse.ArgumentParser,
                 state: UniverseState, seed: int, config: GameConfig,
                 *, source: str | None) -> None:
    """Print/write whichever reports were asked for, against an already-built universe.

    Shared by the generate path and the `--save` path, so a listing reads identically
    whichever universe it came from; `source` names a save in the provenance header.
    """
    did_something = False
    if args.stats:
        print(summarize(state))
        did_something = True
    # Every id below is specific to this universe; surface it so a --list in one run and
    # a --route in another are never silently read against different universes.
    if args.list or args.route is not None:
        origin = source if source is not None else f"seed={seed}"
        print(f"# universe {origin} ({len(state.sectors)} sectors); ids are seed-specific")
    if args.list:
        categories = LIST_CATEGORIES if "all" in args.list else args.list
        for category in categories:
            print(list_items(state, category))
        did_something = True
    if args.route is not None:
        try:
            print(format_route(state, args.route[0], args.route[1]))
        except ValueError as exc:
            parser.error(f"{exc} — re-run --route with the same --seed you used to --list "
                         f"(this run is seed {seed})")
        did_something = True
    if args.dump_json is not None:
        from edge.bigbang.webviz import dump_json

        dump_json(state, args.dump_json, config=config)
        print(f"wrote visualization payload to {args.dump_json}")
        did_something = True
    if args.render is not None:
        from edge.bigbang.webviz import render_web

        index = render_web(state, args.render, config=config)
        print(f"wrote visualization to {index}")
        did_something = True
    if not did_something:
        origin = f"loaded universe {source}" if source is not None \
            else f"generated universe seed={seed}"
        print(f"{origin} sectors={len(state.sectors)}")


if __name__ == "__main__":
    main()
