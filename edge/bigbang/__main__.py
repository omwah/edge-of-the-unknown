"""CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--inspect] [--render PATH]`.

A dev entrypoint that generates a universe from the default config and prints a
text report (`--inspect`) and/or renders the warp graph to a PNG with port
sectors highlighted (`--render`, the §5 inspector).
"""

from __future__ import annotations

import argparse

from edge.bigbang.generator import generate, summarize
from edge.config import load_default_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="edge.bigbang")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--sectors", type=int, default=None, help="override sector_count")
    parser.add_argument("--inspect", action="store_true", help="print a universe report")
    parser.add_argument("--render", metavar="PATH", default=None, help="write a graph PNG")
    args = parser.parse_args()

    config = load_default_config()
    if args.sectors is not None:
        config = config.model_copy(
            update={"bigbang": config.bigbang.model_copy(update={"sector_count": args.sectors})}
        )
    state = generate(config, args.seed)
    if args.inspect:
        print(summarize(state))
    if args.render is not None:
        from edge.bigbang.render import render_graph

        render_graph(state, args.render, layout_seed=args.seed)
        print(f"wrote graph to {args.render}")
    if not args.inspect and args.render is None:
        print(f"generated universe seed={args.seed} sectors={len(state.sectors)}")


if __name__ == "__main__":
    main()
