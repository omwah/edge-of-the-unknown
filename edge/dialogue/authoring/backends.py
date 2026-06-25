"""Pluggable LLM backends for the dialogue authoring pipeline (DESIGN §6.7, dev-only).

Every backend implements one method — `generate(prompt, schema) -> dict` — returning a
schema-valid JSON object (a Tracery grammar). The rest of the pipeline is backend-agnostic;
swap engines with `--backend`. External SDKs/clients are imported lazily inside each adapter
so importing this module never requires `anthropic`, an Ollama server, or Antigravity creds.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Protocol


class Backend(Protocol):
    """Generate one schema-valid JSON grammar for an authoring prompt."""

    name: str

    def generate(self, prompt: str, *, schema: dict[str, Any]) -> dict[str, Any]: ...


class StaticBackend:
    """A deterministic offline backend — emits a minimal valid grammar (dry-run / tests).

    Uses only the universal `{player}`/`{species}` placeholders, so its output is fillable
    for any intent without a model. Lets the pipeline (prompt assembly, validation, YAML
    emission) be exercised end to end with no network or model dependency.
    """

    name = "static"

    def generate(self, prompt: str, *, schema: dict[str, Any]) -> dict[str, Any]:
        return {"origin": ["#opener#"],
                "opener": ["The {species} acknowledge you, {player}.",
                           "Well met, {player}. The {species} hear you."]}


class OllamaBackend:
    """A local Ollama model (the default, offline path) via its HTTP JSON-schema API."""

    name = "ollama"

    def __init__(self, model: str = "llama3.1", host: str | None = None) -> None:
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def generate(self, prompt: str, *, schema: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({
            "model": self.model, "prompt": prompt, "stream": False, "format": schema,
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.host}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:  # noqa: S310 — local dev host
            payload = json.loads(resp.read().decode("utf-8"))
        result: dict[str, Any] = json.loads(payload["response"])
        return result


class AnthropicBackend:
    """The Anthropic API via the official SDK, with schema-constrained structured output.

    Defaults to `claude-opus-4-8`. Reads `ANTHROPIC_API_KEY` from the environment. A single
    call per request; for a large roster run, the pipeline can batch externally (the Message
    Batches API) — kept simple here so the backend stays a thin adapter.
    """

    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model

    def generate(self, prompt: str, *, schema: dict[str, Any]) -> dict[str, Any]:
        import anthropic  # lazy: only needed for this backend (dev extra)

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=self.model, max_tokens=2048,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(b.text for b in resp.content if b.type == "text")
        result: dict[str, Any] = json.loads(text)
        return result


class AntigravityBackend:
    """Google Antigravity as a cloud backend, via the official `google-antigravity` SDK.

    Uses the SDK's structured-output path: the grammar JSON schema is handed straight to
    `LocalAgentConfig(response_schema=…)` (which accepts a JSON-Schema dict) and the
    validated grammar is read back with `ChatResponse.structured_output()`. The model id
    comes from `--model` / `ANTIGRAVITY_MODEL` (default `gemini-3-pro`); auth uses the SDK's
    default credentials (`GEMINI_API_KEY` / ADC) unless `ANTIGRAVITY_API_KEY` overrides it.
    """

    name = "antigravity"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("ANTIGRAVITY_MODEL", "gemini-3-pro")
        # The SDK falls back to GEMINI_API_KEY / ADC; ANTIGRAVITY_API_KEY is an explicit override.
        self.api_key = os.environ.get("ANTIGRAVITY_API_KEY") or None

    def generate(self, prompt: str, *, schema: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        from google.antigravity import Agent, LocalAgentConfig  # lazy: only this backend's dev extra

        async def _run() -> Any:
            config = LocalAgentConfig(
                model=self.model, response_schema=schema,
                **({"api_key": self.api_key} if self.api_key else {}),
            )
            async with Agent(config) as agent:
                response = await agent.chat(prompt)
                return await response.structured_output()

        data = asyncio.run(_run())
        # structured_output() yields a dict (we passed a JSON-Schema dict) or a model instance.
        result: dict[str, Any] = data if isinstance(data, dict) else data.model_dump(exclude_none=True)
        return result


def get_backend(name: str, *, model: str | None = None) -> Backend:
    """Resolve a backend by `--backend` name (ollama / anthropic / antigravity / static)."""
    if name == "static":
        return StaticBackend()
    if name == "ollama":
        return OllamaBackend(model) if model else OllamaBackend()
    if name == "anthropic":
        return AnthropicBackend(model) if model else AnthropicBackend()
    if name == "antigravity":
        return AntigravityBackend(model)
    raise ValueError(f"unknown backend {name!r} (ollama | anthropic | antigravity | static)")
