#!/usr/bin/env bash
#
# build_design_pdf.sh — render docs/DESIGN.md to docs/DESIGN.pdf.
#
# The PDF is a generated artifact (gitignored); regenerate it whenever
# DESIGN.md changes. Requires pandoc and the weasyprint PDF engine.
#
# Usage:
#   ./build_design_pdf.sh                # -> docs/DESIGN.pdf
#   ./build_design_pdf.sh path/out.pdf   # custom output path

set -euo pipefail

# Run relative to the repo root (the directory holding this script).
cd "$(dirname "$0")"

SRC="docs/DESIGN.md"
OUT="${1:-docs/DESIGN.pdf}"
TITLE="Edge of the Unknown — Design Document"

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

pandoc "$SRC" -o "$OUT" \
    --pdf-engine=weasyprint \
    --toc --toc-depth=3 \
    -V geometry:margin=1in \
    --metadata title="$TITLE"

echo "wrote $OUT"
