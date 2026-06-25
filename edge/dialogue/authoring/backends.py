"""Pluggable LLM backends for the dialogue authoring pipeline (DESIGN §6.7, dev-only).

Every backend implements one method — `generate(prompt, schema) -> dict` — returning a
schema-valid JSON object (a Tracery grammar). The rest of the pipeline is backend-agnostic;
swap engines with `--backend`. External SDKs/clients are imported lazily inside each adapter
so importing this module never requires `anthropic`, an Ollama server, or Antigravity creds.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
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
        # Ollama's schema mode usually returns clean JSON, but some models (e.g. gemma4:12b)
        # append a second object or trailing prose; _extract_json tolerates that.
        return _extract_json(payload["response"])


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
        return _extract_json(text)


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


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object out of model/CLI output.

    Tolerates the mess small models and agent CLIs produce around the object: ```fences```,
    leading prose, and **trailing junk after a valid object** (a second object, commentary) —
    `raw_decode` reads one complete object and ignores anything after it.
    """
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object in output", text or "<empty>", 0)
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise json.JSONDecodeError(f"expected a JSON object, got {type(obj).__name__}", text, start)
    return obj


def _parse_claude_envelope(text: str) -> dict[str, Any]:
    """Pull the grammar object out of `claude -p --output-format json` output.

    The envelope is `{"type": "result", "result": <structured output>, ...}`; with
    `--json-schema` the result is the grammar (a dict, or a JSON string of one). Defensive: if
    there is no envelope, treat the whole payload as the grammar.
    """
    envelope = _extract_json(text)
    grammar = envelope.get("result", envelope) if "result" in envelope else envelope
    if isinstance(grammar, str):
        return _extract_json(grammar)
    assert isinstance(grammar, dict)
    return grammar


class CliBackend:
    """Drive an authenticated agent **CLI session** (Claude Code, Antigravity, …) to author a
    grammar — no API key, reusing a CLI you already have logged in.

    Generic by construction: the prompt and JSON schema are written into a throwaway temp dir,
    the CLI is invoked, its one schema-valid JSON grammar is read back, and the temp dir is
    **always removed afterwards** (the file the CLI creates is cleaned up by the author tool).
    The rest of the pipeline (assembly, validation, retries) is unchanged.

    Three ways to drive it:
    - `claude` preset — `claude -p --output-format json --json-schema <schema>` with the prompt
      on stdin; the grammar is read from the JSON envelope on stdout (schema-constrained).
    - `agy` preset — the Antigravity CLI (`agy -p`, prompt on stdin); it has no structured-output
      flag, so the grammar JSON is parsed out of its stdout (fences/chatter tolerated).
    - `cli` generic — any other external CLI, via a command template from `--cli-command` /
      `EDGE_AUTHOR_CLI`. Placeholders `{prompt_file}` `{schema_file}` `{out_file}` `{model}` are
      substituted; the CLI is expected to **write the JSON grammar to `{out_file}`**, which the
      backend then reads and deletes. e.g.:
        --cli-command 'some-agent run --prompt-file {prompt_file} --output {out_file}'
    """

    def __init__(self, name: str, model: str | None = None, command: str | None = None,
                 debug: bool = False) -> None:
        self.name = name
        self.model = model or "default"     # used only to name the output sidecar
        self._model_arg = model
        self.debug = debug
        self.command = command or os.environ.get("EDGE_AUTHOR_CLI")
        if name == "cli" and not self.command:
            raise RuntimeError(
                "the 'cli' backend needs a command: pass --cli-command '<argv with "
                "{prompt_file}/{out_file}>' or set EDGE_AUTHOR_CLI"
            )

    def generate(self, prompt: str, *, schema: dict[str, Any]) -> dict[str, Any]:
        schema_text = json.dumps(schema)
        full_prompt = (
            f"{prompt}\n\nReturn ONLY a single JSON object conforming to this JSON Schema — "
            f"no prose, no markdown fences:\n{schema_text}"
        )
        work = Path(tempfile.mkdtemp(prefix="edge-author-cli-"))
        try:
            prompt_file = work / "prompt.txt"
            prompt_file.write_text(full_prompt, encoding="utf-8")
            schema_file = work / "schema.json"
            schema_file.write_text(schema_text, encoding="utf-8")
            out_file = work / "grammar.json"

            if self.command:  # generic template: the CLI writes the grammar to {out_file}
                subs = {"{prompt_file}": str(prompt_file), "{schema_file}": str(schema_file),
                        "{out_file}": str(out_file), "{model}": self._model_arg or ""}

                def _sub(tok: str) -> str:
                    for key, val in subs.items():  # noqa: B023 — `subs` is loop-invariant here
                        tok = tok.replace(key, val)
                    return tok

                argv = [_sub(tok) for tok in shlex.split(self.command)]
                self._run(argv)
                if not out_file.exists():
                    raise RuntimeError(f"{argv[0]} produced no {out_file.name}; check the command")
                return _extract_json(out_file.read_text(encoding="utf-8"))

            if self.name == "claude":  # schema-constrained structured output on stdout
                argv = ["claude", "-p", "--output-format", "json", "--json-schema", schema_text]
                if self._model_arg:
                    argv += ["--model", self._model_arg]
                return _parse_claude_envelope(self._run(argv, stdin=full_prompt))

            # `agy` (Antigravity CLI): print mode with the prompt as a positional arg (it does
            # not read stdin); JSON parsed from free-text stdout.
            argv = ["agy", "-p"]
            if self._model_arg:
                argv += ["--model", self._model_arg]
            argv.append(full_prompt)
            return _extract_json(self._run(argv))
        finally:
            shutil.rmtree(work, ignore_errors=True)  # author tool cleans up the session file

    def _run(self, argv: list[str], *, stdin: str | None = None) -> str:
        if self.debug:
            print(f"  $ {shlex.join(argv)}", file=sys.stderr)
        try:
            proc = subprocess.run(argv, input=stdin, capture_output=True, text=True,  # noqa: S603
                                  timeout=600, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError(f"CLI not found: {argv[0]!r} — is it installed and on PATH?") from exc
        if self.debug:
            if proc.stderr.strip():
                print(f"  ┊ {argv[0]} stderr:\n{proc.stderr.rstrip()}", file=sys.stderr)
            print(f"  ┊ {argv[0]} stdout:\n{proc.stdout.rstrip()}", file=sys.stderr)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout).strip()[-500:]
            raise RuntimeError(f"{argv[0]} exited {proc.returncode}: {tail}")
        return proc.stdout


class DebugBackend:
    """Wraps any backend to echo the request/response at the backend boundary to stderr.

    `--debug` routes each `generate` through this: the outgoing prompt and the parsed grammar
    coming back are printed (to stderr, so stdout / the `--dry-run` YAML stay clean). Wrapping
    is transparent — `name`/`model` are forwarded so the sidecar is still named for the inner
    backend. CLI backends additionally echo their argv and raw stdout/stderr (see `CliBackend`).
    """

    def __init__(self, inner: Backend) -> None:
        self.inner = inner
        self.name = inner.name
        self.model = getattr(inner, "model", inner.name)

    def generate(self, prompt: str, *, schema: dict[str, Any]) -> dict[str, Any]:
        print(f"\n┌─ {self.name} ← prompt ───\n{prompt}\n└─", file=sys.stderr)
        result = self.inner.generate(prompt, schema=schema)
        rendered = json.dumps(result, indent=2, ensure_ascii=False)
        print(f"┌─ {self.name} → response ───\n{rendered}\n└─\n", file=sys.stderr)
        return result


def get_backend(name: str, *, model: str | None = None, command: str | None = None,
                debug: bool = False) -> Backend:
    """Resolve a backend by `--backend` name.

    Engines: ollama / anthropic / antigravity (API/SDK), claude / agy / cli (an authenticated
    CLI session, no key), static (offline test stub). `debug` enables raw CLI echo on the CLI
    backends; the request/response echo is added separately by wrapping in `DebugBackend`.
    """
    if name == "static":
        return StaticBackend()
    if name == "ollama":
        return OllamaBackend(model) if model else OllamaBackend()
    if name == "anthropic":
        return AnthropicBackend(model) if model else AnthropicBackend()
    if name == "antigravity":
        return AntigravityBackend(model)
    if name in ("claude", "agy", "cli"):
        return CliBackend(name, model=model, command=command, debug=debug)
    raise ValueError(
        f"unknown backend {name!r} "
        f"(ollama | anthropic | antigravity | claude | agy | cli | static)"
    )
