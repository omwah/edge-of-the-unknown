"""Offline CLI tool for testing and developing procedural ASCII art generation."""

import argparse
from typing import Sequence

from rich.cells import cell_len
from rich.console import Console
from rich.text import Text
from edge.art.generator import (
    available_archetypes,
    available_subtypes,
    generate_sprite,
)


def banner(title: str, width: int, style: str = "bold white") -> Text:
    """Return a banner line: ``title`` centered to ``width`` and padded with dashes.

    Titles wider than ``width`` are never truncated.
    """
    framed = f" {title} "
    return Text(framed.center(max(width, len(framed)), "-"), style=style)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Offline CLI tool to generate and preview Edge procedural ASCII art."
    )
    parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=["planet", "terrain", "ship", "port", "subsystem", "starfield"],
        help="The category of the entity to generate.",
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
        "--archetype-id",
        type=str,
        default=None,
        help="The owner archetype id dictating the stylistic choices "
        "(for ships, ports, and subsystems); e.g. humanoid_diplomat, brain_dome_automaton.",
    )

    args = parser.parse_args(argv)

    if args.type == "planet":
        args.width = args.height * 2

    if args.subtype.lower() == "all":
        subtypes_to_run = available_subtypes(args.type)
        if not subtypes_to_run:
            parser.error(f"--subtype all is not supported for type '{args.type}'")
    else:
        subtypes_to_run = [args.subtype]

    if args.archetype_id is not None and args.archetype_id.lower() == "all":
        archetypes_to_run = available_archetypes()
        if not archetypes_to_run:
            parser.error("--archetype-id all has no archetype styles to render")
    else:
        archetypes_to_run = [args.archetype_id]

    console = Console(force_terminal=True, color_system="truecolor")

    rendered: list[tuple[str, Text, int]] = []
    for st in subtypes_to_run:
        for arch in archetypes_to_run:
            sprite = generate_sprite(
                entity_type=args.type,
                subtype=st,
                seed=args.seed,
                width=args.width,
                height=args.height,
                archetype_id=arch,
            )
            sprite_width = max(
                (cell_len(line) for line in sprite.plain.split("\n")), default=0
            )
            label = f"{args.type.title()} - {st}"
            if arch is not None:
                label += f" / {arch}"
            title = f"{label} ({args.width} x {args.height})"
            rendered.append((title, sprite, sprite_width))

    # Size every banner to the widest sprite/title across the run so the headers
    # are uniform, keeping each title centered within that shared width.
    banner_width = max(
        (max(sprite_width, len(f" {title} ")) for title, _, sprite_width in rendered),
        default=0,
    )

    for title, sprite, _ in rendered:
        header = banner(title, banner_width)
        console.print(header)
        console.print(sprite)
        console.print("-" * header.cell_len)


if __name__ == "__main__":
    main()
