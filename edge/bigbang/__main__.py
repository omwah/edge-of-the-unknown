"""CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--inspect] [--render PATH]`.

A dev entrypoint that generates a universe from the default config and prints a
text report (`--inspect`), lists populated items (`--list ports planets …`), plots
a route between two sectors (`--route SRC DST`, by internal *or* spatial id), and/or
renders the warp graph to a PNG with port sectors highlighted (`--render`, §5).
"""

from __future__ import annotations

import argparse

from edge.bigbang.generator import generate, summarize
from edge.bigbang.inspect import LIST_CATEGORIES, format_route, list_items
from edge.config import load_default_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="edge.bigbang")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--sectors", type=int, default=None, help="override sector_count")
    parser.add_argument(
        "--mode", choices=("trunk", "expansive"), default=None,
        help="override topology_mode (trunk chokepoints | expansive band-lattice, §5)",
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
    parser.add_argument("--render", metavar="PATH", default=None, help="write a graph PNG")
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
    state = generate(config, args.seed)
    did_something = False
    if args.inspect:
        print(summarize(state))
        did_something = True
    # Every id below is specific to this seed; surface it so a --list in one run and
    # a --route in another are never silently read against different universes.
    if args.list or args.route is not None:
        print(f"# universe seed={args.seed} ({len(state.sectors)} sectors); ids are seed-specific")
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
                         f"(this run is seed {args.seed})")
        did_something = True
    if args.render is not None:
        from edge.bigbang.render import render_graph

        render_graph(state, args.render, layout_seed=args.seed)
        print(f"wrote graph to {args.render}")
        did_something = True
    if not did_something:
        print(f"generated universe seed={args.seed} sectors={len(state.sectors)}")


if __name__ == "__main__":
    main()
