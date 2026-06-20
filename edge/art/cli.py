"""Offline CLI tool for testing and developing procedural ASCII art generation."""

import argparse
from typing import Sequence

from rich.console import Console
from edge.art.generator import generate_sprite


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Offline CLI tool to generate and preview Edge procedural ASCII art."
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=["planet", "terrain", "ship", "port", "subsystem"],
        help="The main entity type to generate.",
    )
    parser.add_argument(
        "--subtype",
        required=True,
        help="The specific subtype (e.g., terrestrial_warm, fighter, stardock).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="The deterministic seed (default 42).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=40,
        help="Target bounding width in characters.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=20,
        help="Target bounding height in lines.",
    )
    parser.add_argument(
        "--owner-species",
        type=str,
        default=None,
        help="The species dictating the stylistic choices (for ships, ports, and subsystems).",
    )

    args = parser.parse_args(argv)

    if args.subtype.lower() == "all" and args.type in ("terrain", "planet"):
        from edge.art.generator import _TERRAIN_GEN
        subtypes_to_run = list(_TERRAIN_GEN.biomes_registry.keys())
    else:
        subtypes_to_run = [args.subtype]

    console = Console(force_terminal=True, color_system="truecolor")
    for st in subtypes_to_run:
        sprite = generate_sprite(
            entity_type=args.type,
            subtype=st,
            seed=args.seed,
            width=args.width,
            height=args.height,
            owner_species=args.owner_species,
        )

        header_text = f" {args.type.title()} - {st} ({args.width} x {args.height}) "
        console.print(header_text.center(args.width, "-"))
        console.print(sprite)
        console.print("-" * args.width)


if __name__ == "__main__":
    main()
