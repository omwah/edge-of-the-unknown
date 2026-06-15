#!/usr/bin/env bash
#
# build_design_pdf.sh — render docs/DESIGN.md to docs/DESIGN.pdf.
#
# The PDF is a generated artifact (gitignored); regenerate it whenever
# DESIGN.md changes. Requires pandoc and the weasyprint PDF engine.
#
# The UI mockup screenshots in docs/ui/shots/ are appended as a final
# "UI Mockup Screenshots" section so the PDF is a self-contained handout.
# This is done in a temporary combined source — docs/DESIGN.md itself is
# never modified (the screenshots only live in the built PDF).
#
# Usage:
#   ./scripts/build_design_pdf.sh                # -> docs/DESIGN.pdf
#   ./scripts/build_design_pdf.sh path/out.pdf   # custom output path

set -euo pipefail

# Run relative to the repo root (this script lives in scripts/).
cd "$(dirname "$0")/.."

SRC="docs/DESIGN.md"
OUT="${1:-docs/DESIGN.pdf}"
TITLE="Edge of the Unknown — Design Document"
SHOTS_DIR="docs/ui/shots"

# Screenshots to append, in presentation order: "file-stem|Caption".
SHOTS=(
    "main-menu|Main Menu"
    "game|Game Screen — sector view, status sidebar, event ticker"
    "port|Trade Port"
    "stardock|StarDock — services hub (Commodities tab)"
    "planet|Planet — orbit view"
    "surface|Planet Surface — descent & site exploration"
    "map|Galactic Map"
    "computer|Ship Computer"
    "engine-room|Engine Room — subsystems & components"
)

for tool in pandoc weasyprint; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: '$tool' is required but not installed." >&2
        exit 1
    fi
done

if [[ ! -f "$SRC" ]]; then
    echo "error: source '$SRC' not found." >&2
    exit 1
fi

# Build a temporary combined source: DESIGN.md, then the screenshots appendix.
# Clean it up on exit so we never leave a stray file behind.
COMBINED="$(mktemp --tmpdir edge-design.XXXXXX.md)"
trap 'rm -f "$COMBINED"' EXIT

cat "$SRC" > "$COMBINED"

{
    printf '\n\n# UI Mockup Screenshots {.unnumbered}\n\n'
    printf 'Mockups of the Textual TUI screens (the throwaway skeleton). These are '
    printf 'rendered captures, not part of the design spec above.\n'
    for entry in "${SHOTS[@]}"; do
        stem="${entry%%|*}"
        caption="${entry#*|}"
        img="$SHOTS_DIR/$stem.svg"
        [[ -f "$img" ]] || { echo "warn: missing screenshot '$img', skipping." >&2; continue; }
        # Each shot on its own page, under its own subsection heading.
        printf '\n<div style="page-break-before: always"></div>\n\n'
        printf '## %s\n\n' "$caption"
        printf '![](%s){width=100%%}\n' "$img"
    done
} >> "$COMBINED"

pandoc "$COMBINED" -o "$OUT" \
    --pdf-engine=weasyprint \
    --toc --toc-depth=3 \
    --resource-path="$PWD" \
    -V geometry:margin=1in \
    --metadata title="$TITLE"

echo "wrote $OUT"
