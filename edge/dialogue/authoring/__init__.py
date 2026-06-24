"""Offline dialogue authoring (DESIGN §6.7) — the one impure corner of `edge.dialogue`.

This subpackage trains the runtime's dialogue grammars with a **local or cloud LLM**, offline:
for each persona/species and intent it prompts a backend to write a persona-voiced Tracery
grammar (schema-constrained JSON), validates and render-smoke-tests it, and emits a config
sidecar. **Nothing here runs in the game client** — the runtime only reads the baked config.

It does network/file I/O, so it is dev-only and is **never imported** by the pure selection /
render / intel modules or by any runtime layer (the import rule that keeps `edge.dialogue`
pure). Backends are pluggable behind the `Backend` protocol: a local Ollama model (default),
the Anthropic API, or Google Antigravity. Run it via the `edge-author-dialogue` console script
(`pixi run author-dialogue …`).
"""

from __future__ import annotations

from edge.dialogue.authoring.backends import Backend, StaticBackend, get_backend
from edge.dialogue.authoring.pipeline import (
    AuthoringRequest,
    author_packs,
    build_prompt,
    output_schema,
    validate_generated,
)

__all__ = [
    "Backend", "StaticBackend", "get_backend",
    "AuthoringRequest", "author_packs", "build_prompt", "output_schema", "validate_generated",
]
