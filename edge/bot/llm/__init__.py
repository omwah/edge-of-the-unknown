"""The LLM pilot — an Ollama-driven bot playing through the `ServiceProtocol` seam (dev-tier).

Like `edge/dialogue/authoring/`, this package is a **dev-only impure corner**: it does HTTP
I/O (a local Ollama server) and imports Textual for its own console app. The runtime game
never imports it. The pilot acts only through ordinary commands via `BotRunner`, so a pilot
run is an ordinary replayable command log like any other bot (docs/SCRIPTING.md).
"""
