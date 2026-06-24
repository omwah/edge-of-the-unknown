# `edge-author-dialogue` — offline alien-dialogue authoring

Trains the runtime's alien-dialogue **Tracery grammars** with an LLM, **offline**. For each
roster species and a set of intents (greeting, trade, dossier, the `offer_coordinates` "map"
tip, …) it prompts a backend to write a persona-voiced grammar as schema-constrained JSON,
validates and render-smoke-tests it, and writes a config sidecar.

> **Nothing here runs in the game.** The client only ever reads the baked config and expands
> the grammars deterministically (pure `edge.dialogue.render`). This tool is dev-only — the
> one impure corner of `edge.dialogue`, never imported by runtime code. See DESIGN.md §6.7.

## TL;DR

```bash
# 1. See it work with no model or network (uses the built-in StaticBackend):
pixi run author-dialogue --dry-run

# 2. Author the whole roster with a local Ollama model (default backend):
pixi run author-dialogue                       # writes config/dialogue/roster_default.generated.yaml

# 3. Or use a cloud backend:
pixi run author-dialogue --backend anthropic   # needs ANTHROPIC_API_KEY + the .[authoring] extra
pixi run author-dialogue --backend antigravity # needs ANTIGRAVITY_BASE_URL + ANTIGRAVITY_API_KEY
```

The console script is also installed as `edge-author-dialogue` (run it directly outside pixi).

## Backends

| `--backend`   | What it is                          | Needs                                                   |
| ------------- | ----------------------------------- | ------------------------------------------------------- |
| `ollama`      | A local Ollama model (the default)  | a running Ollama server (`OLLAMA_HOST`, default `http://localhost:11434`); `--model` (default `llama3.1`). Plain HTTP — no SDK. |
| `anthropic`   | The Anthropic API (official SDK)    | `pip install -e '.[authoring]'` (the `anthropic` SDK) + `ANTHROPIC_API_KEY`. `--model` default `claude-opus-4-8`. |
| `antigravity` | Google Antigravity (OpenAI-shaped)  | `ANTIGRAVITY_BASE_URL`, `ANTIGRAVITY_API_KEY`, optional `ANTIGRAVITY_MODEL` (default `gemini-3-pro`). |
| `static`      | A canned valid grammar (no model)   | nothing — used by `--dry-run` and the tests.            |

Install the cloud extras once with: `pixi run -e default pip install -e '.[authoring]'`
(or `pip install -e '.[authoring]'` in your venv). The Ollama and Antigravity backends are
plain HTTP and need no extra package.

## Options

```
--backend {ollama,anthropic,antigravity,static}   LLM backend (default: ollama)
--model MODEL                                      override the backend's model id
--contexts greeting,trade_open,offer_coordinates,… intents to author (comma-separated)
--species vesk,terran,…                            limit to these roster species ids (default: all)
--out PATH                                         sidecar to write (default: config/dialogue/roster_default.generated.yaml)
--dry-run                                          author one species/context with the static backend and print it
```

Default contexts: `greeting, trade_open, farewell, dossier_other, offer_coordinates`.

## What it writes

A YAML sidecar keyed by species id, each context holding one grammar line entry:

```yaml
species_grammars:
  vesk:
    greeting:
      - grammar:
          origin: ["#opener#"]
          opener:
            - "The {species} weigh your approach, {player}."
            - "State your business with the {species}, {player}."
    offer_coordinates:
      - grammar:
          origin: ["#opener#"]
          opener:
            - "Seek {target}? Steer for sector {coords}, {player} — {distance} jumps into the {band}. {reward} waits there."
```

Grammars expand from `origin` and may reference the fixed fragment symbols `opener`,
`detail`, `honorific`, `aside`, plus shared fragments declared in the roster's top-level
`grammar:` block. They may use **only** the placeholders allowed for that context (universal
`{player}`/`{species}`/`{alliance}` plus per-intent extras such as
`{target}`/`{coords}`/`{distance}`/`{band}`/`{reward}` for `offer_coordinates`).

## Using the output

The sidecar is **candidate content** — review it, then fold the grammars you like into the
live roster (`config/roster_default.yaml`), either as a species' `dialogue_pack` override or a
`persona` pack. Every generated grammar is already validated (fillable placeholders, non-empty
render, defined symbols), and the live roster is re-checked by `validate_dialogue` (DESIGN §13)
on load and in CI — so a bad grammar fails the build rather than blanking a line in game.

Generation is **not** auto-merged into the live config on purpose: the current roster ships
working hand-authored lines, and the tool should never silently overwrite them.

## How it fits together

```
edge/dialogue/authoring/
  cli.py        # argparse entry point (the `edge-author-dialogue` / `author-dialogue` command)
  backends.py   # the Backend protocol + ollama / anthropic / antigravity / static adapters
  pipeline.py   # prompt assembly, the strict JSON output schema, validation, pack assembly
```

The pipeline is backend-agnostic; only `backends.py` knows any provider specifics. To add a
backend, implement `generate(prompt, *, schema) -> dict` and register it in `get_backend`.
