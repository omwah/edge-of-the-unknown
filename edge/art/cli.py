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


# Every renderable type, in page order. (ship/subsystem have no generator yet,
_ALL_TYPES = ["port", "planet", "terrain", "starfield", "ship", "subsystem", "discovery"]


def _archetype_paged_sheets(
    entity_type: str,
    subtypes: list[str],
    archetypes: list[str],
    per_page: int,
    *,
    seed: int,
    width: int,
    height: int,
    facing: str = "right",
) -> list[tuple[str, list[tuple[str, Text]], int | None]]:
    """Build one contact sheet per group of ``per_page`` archetypes: archetypes
    become columns, subtypes rows. ``per_page <= 0`` keeps them all on one page.

    Returns ``(title, items, cols)`` sheets for ``export_multipage_pdf``.
    """
    if per_page <= 0:
        per_page = len(archetypes)
    chunks = [archetypes[i:i + per_page] for i in range(0, len(archetypes), per_page)]

    sheets: list[tuple[str, list[tuple[str, Text]], int | None]] = []
    for page, chunk in enumerate(chunks, start=1):
        items: list[tuple[str, Text]] = []
        for st in subtypes:  # subtype-major: rows = subtypes, cols = archetypes
            for arch in chunk:
                sprite = generate_sprite(
                    entity_type=entity_type,
                    subtype=st,
                    seed=seed,
                    width=width,
                    height=height,
                    archetype_id=arch,
                    facing=facing,
                )
                items.append((f"{st} / {arch}", sprite))
        title = f"{entity_type} [{page}/{len(chunks)}]  " + ", ".join(chunk)
        sheets.append((title, items, len(chunk)))
    return sheets


def _export_all_types(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Sweep every renderable type into one multi-page PDF (a page per type)."""
    from edge.art.export import export_multipage_pdf

    if not args.export:
        parser.error("--type all requires --export PATH (a multi-page PDF)")

    sheets: list[tuple[str, list[tuple[str, Text]], int | None]] = []
    for entity_type in _ALL_TYPES:
        subtypes = available_subtypes(entity_type)
        if not subtypes:
            continue  # not implemented yet (e.g. ship, subsystem)
        # Planets render wide (width = 2 * height) like the single-type path.
        width = args.height * 2 if entity_type == "planet" else args.width
        height = args.height

        # Ports, ships, and discoveries carry an archetype (style) axis -> paginate by
        # archetype; other types have no styles, so they get a single page.
        if entity_type in ("port", "ship", "discovery"):
            sheets.extend(
                _archetype_paged_sheets(
                    entity_type,
                    subtypes,
                    available_archetypes(),
                    args.archetypes_per_page,
                    seed=args.seed,
                    width=width,
                    height=height,
                    facing=args.facing,
                )
            )
            continue

        items: list[tuple[str, Text]] = []
        for st in subtypes:
            sprite = generate_sprite(
                entity_type=entity_type,
                subtype=st,
                seed=args.seed,
                width=width,
                height=height,
                archetype_id=None,
            )
            items.append((st, sprite))
        sheets.append((entity_type, items, args.export_cols))

    if not sheets:
        parser.error("no renderable types found to export")

    written = export_multipage_pdf(sheets, args.export)
    total = sum(len(items) for _, items, _ in sheets)
    Console().print(
        f"Wrote {total} sprites across {len(sheets)} pages to {written}"
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Offline CLI tool to generate and preview Edge procedural ASCII art."
    )
    parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=["planet", "terrain", "ship", "port", "subsystem", "starfield", "discovery", "all"],
        help="The category of the entity to generate. 'all' sweeps every "
        "renderable type into a multi-page PDF (one page per type); requires "
        "--export.",
    )
    parser.add_argument(
        "--subtype",
        default=None,
        help="The specific subtype (e.g., terrestrial_warm, fighter, stardock), "
        "or 'all'. Required unless --type all.",
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
    parser.add_argument(
        "--facing",
        type=str,
        default="right",
        choices=["left", "right"],
        help="For ships, which way the hull points: 'right' (canonical) or 'left' "
        "(the same ship flipped). Ignored by other types.",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        metavar="PATH",
        help="Instead of printing, write the rendered sprite(s) to a vector "
        "contact sheet. A '.svg'/'.pdf' suffix writes just that format; any other "
        "path writes both PATH.svg and PATH.pdf. Combine with '--subtype all "
        "--archetype-id all' to dump every style and substyle.",
    )
    parser.add_argument(
        "--export-cols",
        type=int,
        default=None,
        help="Grid column count for the exported sheet (default: near-square, or "
        "one column per archetype when '--archetype-id all' is used).",
    )
    parser.add_argument(
        "--archetypes-per-page",
        type=int,
        default=2,
        metavar="N",
        help="When exporting ports across multiple archetypes, paginate the PDF "
        "to N archetypes per page (columns), with their subtypes as rows "
        "(default 2). Use 0 to keep every archetype on a single page.",
    )

    args = parser.parse_args(argv)

    if args.type == "all":
        _export_all_types(args, parser)
        return

    if args.subtype is None:
        parser.error("--subtype is required (or use --type all)")

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
    export_items: list[tuple[str, Text]] = []
    for st in subtypes_to_run:
        for arch in archetypes_to_run:
            sprite = generate_sprite(
                entity_type=args.type,
                subtype=st,
                seed=args.seed,
                width=args.width,
                height=args.height,
                archetype_id=arch,
                facing=args.facing,
            )
            sprite_width = max(
                (cell_len(line) for line in sprite.plain.split("\n")), default=0
            )
            label = f"{args.type.title()} - {st}"
            short = st
            if arch is not None:
                label += f" / {arch}"
                short += f" / {arch}"
            title = f"{label} ({args.width} x {args.height})"
            rendered.append((title, sprite, sprite_width))
            export_items.append((short, sprite))

    if args.export:
        from edge.art.export import export_multipage_pdf, export_sprite_sheet

        sweeping_archetypes = len(archetypes_to_run) > 1 and archetypes_to_run[0]
        per_page = args.archetypes_per_page
        if sweeping_archetypes and 0 < per_page < len(archetypes_to_run):
            # Paginate the PDF: per_page archetypes (columns) x subtypes (rows).
            sheets = _archetype_paged_sheets(
                args.type, subtypes_to_run, archetypes_to_run, per_page,
                seed=args.seed, width=args.width, height=args.height,
                facing=args.facing,
            )
            pdf = export_multipage_pdf(sheets, args.export)
            console.print(
                f"Wrote {len(export_items)} sprites across {len(sheets)} pages "
                f"to {pdf}"
            )
            return

        # One column per archetype when sweeping archetypes, else near-square.
        cols = args.export_cols
        if cols is None and len(archetypes_to_run) > 1:
            cols = len(archetypes_to_run)
        written = export_sprite_sheet(export_items, args.export, cols=cols)
        plural = "s" if len(export_items) != 1 else ""
        console.print(
            f"Wrote {len(export_items)} sprite{plural} to "
            + ", ".join(str(p) for p in written)
        )
        return

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
