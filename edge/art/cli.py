"""Offline CLI tool for testing and developing procedural ASCII art generation."""

import argparse
from typing import Sequence

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

    sprite = generate_sprite(
        entity_type=args.type,
        subtype=args.subtype,
        seed=args.seed,
        width=args.width,
        height=args.height,
        owner_species=args.owner_species,
    )

    print(f"--- Generated {args.type} ({args.subtype}) [Size: {args.width}x{args.height}] ---")
    print(sprite)
    print("-" * (args.width + 8))


if __name__ == "__main__":
    main()
