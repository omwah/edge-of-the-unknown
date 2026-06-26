"""`edge-author-dialogue` — the offline dialogue authoring command (DESIGN §6.7, dev-only).

Drives a pluggable LLM backend — a local Ollama model (default), the Anthropic / Antigravity
APIs, or an authenticated **CLI session** (`--backend claude` for Claude Code, `--backend agy`
for the Antigravity CLI, or `--backend cli` with any external agent CLI via `--cli-command` —
all needing no API key) — to author persona-voiced
Tracery grammars for each roster species and a set of intents,
validates them, and writes a config sidecar the runtime can load. Each run is written to a
file named for the backend and model that produced it
(`config/dialogue/alien_dialogue.<backend>_<model>.yaml`) so authored corpora don't clobber
each other; `--out` overrides the path. The runtime never calls an LLM — this only shapes
config. Run via `pixi run author-dialogue …`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from edge.config import load_default_config, validate_sidecar
from edge.dialogue import select
from edge.dialogue.authoring.backends import Backend, DebugBackend, get_backend
from edge.dialogue.authoring.pipeline import author_packs

# Where backend/model-named grammar sidecars are written when `--out` is not given.
_OUT_DIR = Path("config/dialogue")

# A sensible default set of intents to author (the Phase-2 friendly path + the map mechanic).
_DEFAULT_CONTEXTS = ("greeting", "trade_open", "farewell", "dossier_other", "offer_coordinates")

# Placeholder samples that ground the model on how the location-tip line is filled at runtime.
_EXAMPLES: dict[str, dict[str, str]] = {
    "dossier_other": {"subject": "the Vesk"},
    "offer_coordinates": {
        "target": "ancient ruins", "coords": "42", "distance": "5",
        "band": "Deep", "reward": "a Tier III component",
    },
}


def _default_out(backend: Backend) -> Path:
    """The sidecar path for a backend, named for its backend id and resolved model.

    e.g. `config/dialogue/alien_dialogue.anthropic_claude-opus-4-8.yaml`. The model id is
    sanitised (slashes, colons, whitespace -> `-`) so it is a safe filename component.
    """
    model = getattr(backend, "model", backend.name)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(model)).strip("-")
    return _OUT_DIR / f"alien_dialogue.{backend.name}_{slug}.yaml"


def _voices(species: Any, only: set[str] | None) -> dict[str, str]:
    """A `{species_id -> voice description}` map for the (optionally filtered) roster."""
    voices: dict[str, str] = {}
    for sc in species:
        if only and sc.id not in only:
            continue
        blurb = sc.description or f"a {sc.archetype_id} species"
        voices[sc.id] = f"{sc.name}: {blurb} (speaking voice / persona: {sc.persona})"
    return voices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edge-author-dialogue", description=__doc__)
    parser.add_argument("--backend", default="ollama",
                        choices=["ollama", "anthropic", "antigravity", "claude", "agy", "cli",
                                 "static"],
                        help="engine: ollama/anthropic/antigravity (API), claude/agy/cli "
                             "(an authenticated CLI session, no key), static (default: ollama)")
    parser.add_argument("--model", default=None, help="override the backend's model id")
    parser.add_argument("--cli-command", default=None,
                        help="for --backend cli: the CLI argv template, e.g. "
                             "'antigravity run --prompt-file {prompt_file} --output {out_file}' "
                             "(placeholders: {prompt_file} {schema_file} {out_file} {model}); "
                             "falls back to $EDGE_AUTHOR_CLI")
    parser.add_argument("--contexts", default=",".join(_DEFAULT_CONTEXTS),
                        help="comma-separated intent keys to author")
    parser.add_argument("--species", default=None,
                        help="comma-separated species ids to author (default: all)")
    parser.add_argument("--out", default=None,
                        help="where to write the generated sidecar (default: "
                             "config/dialogue/alien_dialogue.<backend>_<model>.yaml)")
    parser.add_argument("--retries", type=int, default=4,
                        help="regeneration attempts per line before giving up (default: 4)")
    parser.add_argument("--branch-passes", type=int, default=2,
                        help="rounds of branch-node authoring after base contexts "
                             "(0 = skip branch authoring, default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="author one species/context with the static backend and print it")
    parser.add_argument("--debug", action="store_true",
                        help="echo each backend request/response (and raw CLI argv/output) to "
                             "stderr")
    parser.add_argument("--validate", metavar="PATH", default=None,
                        help="validate an existing sidecar YAML against the default roster "
                             "and exit (no authoring); exits 0 on success, 1 on integrity "
                             "error, 2 on structural/config error")
    args = parser.parse_args(argv)

    if args.validate is not None:
        try:
            validate_sidecar(Path(args.validate))
            print(f"OK: {args.validate}")
            return 0
        except select.DialogueIntegrityError as exc:
            print(f"integrity error: {exc}", file=sys.stderr)
            return 1
        except (ValueError, Exception) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    cfg = load_default_config()
    if cfg.roster is None:
        print("no roster configured", file=sys.stderr)
        return 2

    contexts = tuple(c.strip() for c in args.contexts.split(",") if c.strip())
    only = {s.strip() for s in args.species.split(",")} if args.species else None
    voices = _voices(cfg.roster.species, only)

    if args.dry_run:
        backend = get_backend("static")
        if args.debug:
            backend = DebugBackend(backend)
        first = dict(list(voices.items())[:1])
        packs = author_packs(backend, first, contexts[:1], examples=_EXAMPLES,
                             branch_passes=args.branch_passes)
        yaml.safe_dump(packs, sys.stdout, sort_keys=False, allow_unicode=True)
        print("\n# dry run — validated, not written", file=sys.stderr)
        return 0

    backend = get_backend(args.backend, model=args.model, command=args.cli_command,
                          debug=args.debug)
    if args.debug:
        backend = DebugBackend(backend)
    print(f"authoring {len(voices)} species × {len(contexts)} intents via {backend.name}…",
          file=sys.stderr)
    packs = author_packs(backend, voices, contexts, examples=_EXAMPLES, retries=args.retries,
                         branch_passes=args.branch_passes)

    out = Path(args.out) if args.out else _default_out(backend)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"species_grammars": packs}, fh, sort_keys=False, allow_unicode=True)
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
