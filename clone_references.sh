#!/usr/bin/env bash
# Re-clone the TradeWars 2002 reference codebases analyzed for Project Helix.
# Usage: ./clone_references.sh [target_dir]   (default: ./references)
set -euo pipefail

DIR="${1:-references}"
mkdir -p "$DIR" && cd "$DIR"

REPOS=(
  rdearman/twclone              # C/Postgres: architecture, engine, economy docs
  mrdon/terminal-space          # Python: closest cousin, domain model reference
  drbeco/tradewars              # C clone + original 1986 BASIC source (tw2bas/)
  leonard4/SectorWars           # C++: contains "TW Sector Algorithm.txt"
  jzmiller1/ExchangeConflict2016 # Python: networkx universe-gen experiments
  tarnus/aatraders              # PHP: AAT, sysop feature catalog (large, ~75MB)
  cheevauva/blacknovatraders    # PHP: BlackNova mirror, tuned economy constants
)

for repo in "${REPOS[@]}"; do
  name="${repo#*/}"
  if [ -d "$name" ]; then
    echo "skip: $name already exists"
  else
    git clone --depth 1 "https://github.com/$repo"
  fi
done

echo "Done. Reference code in $(pwd)"
