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
pixi run author-dialogue                       # writes config/dialogue/alien_dialogue.ollama_llama3.1.yaml

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
| `antigravity` | Google Antigravity (`google-antigravity` SDK) | `pip install -e '.[authoring]'` (the `google-antigravity` SDK) + `GEMINI_API_KEY` (or ADC; `ANTIGRAVITY_API_KEY` overrides). `--model` / `ANTIGRAVITY_MODEL` default `gemini-3-pro`. |
| `claude`      | A **Claude Code CLI session** (no API key) | the `claude` CLI installed + logged in. Uses `claude -p --output-format json --json-schema …` (schema-constrained). `--model` optional. |
| `agy`         | An **Antigravity CLI session** (no API key) | the `agy` CLI installed + logged in. Uses `agy -p <prompt>`; JSON is parsed from its stdout. `--model` optional. |
| `cli`         | **Any other agent CLI** (generic)   | `--cli-command '<argv>'` (or `$EDGE_AUTHOR_CLI`) with placeholders `{prompt_file} {schema_file} {out_file} {model}`; the CLI must write the JSON grammar to `{out_file}`. |
| `static`      | A canned valid grammar (no model)   | nothing — used by `--dry-run` and the tests.            |

The `claude` / `agy` / `cli` backends drive a **CLI you are already authenticated to** — no API
key. The prompt and schema are written into a throwaway temp dir, the CLI is invoked, the one
JSON grammar is read back, and the temp dir is always removed afterwards. Example generic use
(any agent CLI that can write a file):

```bash
pixi run author-dialogue --backend cli \
  --cli-command 'some-agent run --prompt-file {prompt_file} --output {out_file}'
```

Install the cloud extras once with: `pixi run -e default pip install -e '.[authoring]'`
(or `pip install -e '.[authoring]'` in your venv) — this pulls in both the `anthropic` and
`google-antigravity` SDKs. The Ollama backend is plain HTTP and needs no extra package.

## Options

```
--backend {ollama,anthropic,antigravity,claude,agy,cli,static}  engine (default: ollama)
--model MODEL                                      override the backend's model id
--cli-command 'ARGV'                              for --backend cli: the CLI argv template
                                                   ({prompt_file} {schema_file} {out_file} {model})
--contexts greeting,trade_open,offer_coordinates,… intents to author (comma-separated)
--species vesk,terran,…                            limit to these roster species ids (default: all)
--out PATH                                         sidecar to write (default: config/dialogue/alien_dialogue.<backend>_<model>.yaml)
--dry-run                                          author one species/context with the static backend and print it
--debug                                            echo each backend request/response (+ raw CLI argv/output) to stderr
```

`--debug` prints the prompt sent to the backend and the grammar that comes back, for every
line — to **stderr**, so stdout (and the `--dry-run` YAML) stay clean. For the CLI backends it
also echoes the exact argv invoked and the CLI's raw stdout/stderr, which is the quickest way
to see why a model's output failed validation. Pairs well with `--dry-run` or `--species X
--contexts greeting` to inspect a single exchange.

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

The sidecar is **candidate content**. You can either:

- **Point at it directly** (no copy-paste). The sidecar's top-level key is `species_grammars`,
  which the config loader splices into each species' `dialogue_pack` by id. List it after the
  base dialogue file (which supplies the `personas` / `generic` fallback the sidecar omits):

  ```yaml
  # config/default.yaml
  dialogue_file:
    - alien_dialogue_default.yaml                 # base: personas + generic + recency_k
    - dialogue/alien_dialogue.ollama_gemma4.yaml  # overrides: species_grammars, by id
  ```

  The species `dialogue_pack` wins over its persona via the runtime fallback chain, so this is
  a clean per-species override — handy for A/B-ing a machine-authored corpus.
- **Or fold the grammars you like** into the live dialogue corpus
  (`config/alien_dialogue_default.yaml`) as a species' `dialogue_pack` override or a `persona`
  pack, for a curated permanent set.

Either way, every generated grammar is already validated (fillable placeholders, no positional
/ escaped braces, non-empty render, defined symbols), and the merged roster + dialogue is
re-checked by `validate_dialogue` (DESIGN §13) on load and in CI — so a bad grammar fails the
build rather than blanking a line in game.

Generation is **not** auto-merged into the live config on purpose: the current roster ships
working hand-authored lines, and the tool should never silently overwrite them.

## Play-testing the dialogue (`--playtest`)

Validation proves a sidecar is *well-formed*; the play-test harness lets you **hear it**. It
drives the **real** `AlienContactScreen` and `server.session.contact_view` against a synthetic
single-game universe — one instance of every roster species — so you can read each species'
lines in motion without launching a game and grinding reputation.

```bash
# Default corpus, in the real contact screen:
pixi run playtest-dialogue
# A freshly-authored sidecar spliced onto the default roster:
pixi run playtest-dialogue --sidecar config/dialogue/alien_dialogue.ollama_gemma4-12b.yaml
# Start on a given species / seed:
pixi run playtest-dialogue --species vesk --seed 7
# Same thing through the authoring CLI:
pixi run author-dialogue --playtest --sidecar config/dialogue/alien_dialogue.<backend>.yaml
```

Press **`c`** for the controls modal and flip the simulated dials live (**↑↓** walks the dials,
**Enter/Space** or **←→** changes the focused one, **Esc**/**`c`** closes and applies):

- **Species** — cycle through the whole roster.
- **Standing** — hostile / neutral / friendly / allied (drives `when: {standing: …}` gating;
  `wary` is Phase-3-inert so it is omitted; `allied` needs the species to carry an alliance).
- **Treaty** / **Intel** — toggles that gate treaty- and `offer_coordinates`-keyed lines.
- **Show disabled** — the runtime's `ui.show_disabled_options` (greys gated rows).
- **Force-enable & traverse** — makes gated replies *selectable* so you can walk every
  branch regardless of standing/treaty/Phase-3 gates.

Inside a conversation, the menu is the node's authored `choices` (resolved species → persona →
generic, falling back to the `generic` persona's `start_context` replies). Press **`f5`** to
re-roll the current line and watch the **recency ring** rephrase it, follow a branch node's
player replies, press **`b`** to step back out of a dead end, and **`f`** to speak a parting
line and break contact. The harness only advances the recency ring; trade/barter/lead actions
are no-ops here, since this is about the words, not the economy.

> Like the rest of this package, the harness is **dev-only**. It is the sole corner of
> `edge.dialogue` that imports `edge.tui` + `textual`; that import is kept off the runtime path
> by loading `playtest` lazily (only the CLI's `--playtest` branch imports it).

## How it fits together

```
edge/dialogue/authoring/
  cli.py        # argparse entry point (the `edge-author-dialogue` / `author-dialogue` command)
  backends.py   # the Backend protocol + ollama / anthropic / antigravity / static adapters
  pipeline.py   # prompt assembly, the strict JSON output schema, validation, pack assembly
  playtest.py   # dev-only play-test TUI (`edge-playtest-dialogue`): real contact screen + dials
```

The pipeline is backend-agnostic; only `backends.py` knows any provider specifics. To add a
backend, implement `generate(prompt, *, schema) -> dict` and register it in `get_backend`.
