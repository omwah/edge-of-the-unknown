"""CLI: `python -m edge.bigbang [--seed N] [--sectors M] [--inspect]`.

A dev entrypoint that generates a universe from the default config and prints a
text report (the §5 inspector; a matplotlib graph render can come later).
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
    args = parser.parse_args()

    config = load_default_config()
    if args.sectors is not None:
        config = config.model_copy(
            update={"bigbang": config.bigbang.model_copy(update={"sector_count": args.sectors})}
        )
    state = generate(config, args.seed)
    if args.inspect:
        print(summarize(state))
    else:
        print(f"generated universe seed={args.seed} sectors={len(state.sectors)}")


if __name__ == "__main__":
    main()
