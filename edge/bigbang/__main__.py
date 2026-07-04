"""CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--inspect] [--render DIR]`.

A dev entrypoint that generates a universe from the default config and prints a
text report (`--inspect`), lists populated items (`--list ports planets …`), plots
a route between two sectors (`--route SRC DST`, by internal *or* spatial id), writes
an interactive web topology inspector (`--render DIR`, §5), and/or dumps just the
visualization payload as JSON (`--dump-json PATH`).
"""

from __future__ import annotations

import argparse

from edge.bigbang.generator import generate, summarize
from edge.bigbang.inspect import LIST_CATEGORIES, format_route, list_items
from edge.config import load_default_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="edge.bigbang")
    parser.add_argument("--seed", type=int, default=None, help="override the config seed")
    parser.add_argument("--sectors", type=int, default=None, help="override sector_count")
    parser.add_argument(
        "--mode", choices=("trunk", "expansive", "planar"), default=None,
        help="override topology_mode (trunk chokepoints | expansive band-lattice | planar spiderweb, §5)",
    )
    parser.add_argument("--inspect", action="store_true", help="print a universe report")
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
    args = parser.parse_args()

    config = load_default_config()
    bigbang_overrides: dict[str, object] = {}
    if args.sectors is not None:
        bigbang_overrides["sector_count"] = args.sectors
    if args.mode is not None:
        bigbang_overrides["topology_mode"] = args.mode
    if bigbang_overrides:
        config = config.model_copy(
            update={"bigbang": config.bigbang.model_copy(update=bigbang_overrides)}
        )
    # --seed overrides the config default; fall back to it (then 1) when omitted.
    seed = args.seed if args.seed is not None else (config.seed if config.seed is not None else 1)
    state = generate(config, seed)
    did_something = False
    if args.inspect:
        print(summarize(state))
        did_something = True
    # Every id below is specific to this seed; surface it so a --list in one run and
    # a --route in another are never silently read against different universes.
    if args.list or args.route is not None:
        print(f"# universe seed={seed} ({len(state.sectors)} sectors); ids are seed-specific")
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
        print(f"generated universe seed={seed} sectors={len(state.sectors)}")


if __name__ == "__main__":
    main()
