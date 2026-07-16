"""Minimal Ollama chat client for the LLM pilot (dev-only, stdlib HTTP).

Talks to a local Ollama server's `/api/chat` endpoint with **schema-constrained JSON
output** — the same trick the dialogue-authoring backend uses: `format` carries a JSON
Schema and `think` is disabled, because free reasoning tokens derail schema-constrained
output on small models. The pilot's visible "reasoning" is instead an explicit field of
the constrained decision object (see `actions.DECISION_SCHEMA`).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class OllamaError(RuntimeError):
    """The server was unreachable, errored, or returned no parsable decision."""


class OllamaChat:
    """One chat completion per call against a local Ollama server."""

    def __init__(self, model: str = "gemma4:e4b-128k", host: str | None = None,
                 timeout: float = 300.0) -> None:
        self.model = model
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], *, schema: dict[str, Any]) -> dict[str, Any]:
        """Send a message list; return the schema-shaped decision object."""
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "think": False,  # reasoning rides inside the constrained object instead
            "options": {"temperature": 0.7},
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.host}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 — local dev host
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaError(f"ollama request to {self.host} failed: {exc}") from exc
        content = str(payload.get("message", {}).get("content", ""))
        try:
            return _extract_json(content)
        except json.JSONDecodeError as exc:
            raise OllamaError(f"model returned no parsable JSON decision: {content[:200]!r}") from exc


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object out of model output (fences/trailing prose tolerated)."""
    text = text.strip()
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object in output", text or "<empty>", 0)
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise json.JSONDecodeError(f"expected a JSON object, got {type(obj).__name__}", text, start)
    return obj
