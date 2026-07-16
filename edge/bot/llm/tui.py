"""The LLM pilot's console — a Textual app watching and steering the brain (dev-only).

Layout: an **Actions** pane (what the pilot did and what came of it) beside a
**Reasoning** pane (why), a chat strip where the operator types instructions the brain
folds into its next decision, and Start/Stop controls. The brain runs in a thread worker;
every `BotRecord` crosses back onto the UI thread via `call_from_thread`. An optional log
file receives every record as a timestamped line.

This is the *pilot's* console, not the game client — it deliberately renders the bot's
narration, not the game screen (run the real `edge` TUI on the same save afterwards to
sightsee what the pilot did).
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import TextIO

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

from edge.bot.llm.brain import BotRecord, Brain


class LLMBotApp(App[None]):
    """Start/stop the pilot, read its actions and reasoning, talk to it."""

    TITLE = "Edge of the Unknown — LLM pilot"
    BINDINGS = [
        ("ctrl+s", "start_bot", "Start"),
        ("ctrl+x", "stop_bot", "Stop"),
        ("ctrl+q", "quit", "Quit"),
    ]
    CSS = """
    #body { height: 1fr; }
    #actions-pane, #reasoning-pane { width: 1fr; border: round $primary; }
    #reasoning-pane { border: round $secondary; }
    .pane-title { dock: top; height: 1; padding: 0 1; text-style: bold; background: $boost; }
    RichLog { background: transparent; padding: 0 1; }
    #bottom { height: 14; }
    #ship-status { dock: top; height: 3; padding: 0 1; background: $boost; color: $text; }
    #chat { height: 1fr; border: round $accent; }
    #controls { height: 3; align-vertical: middle; }
    #controls Button { margin: 0 1; min-width: 12; }
    #chat-input { width: 1fr; margin: 0 1; }
    #run-state { width: auto; padding: 1 2 0 1; color: $text-muted; }
    """

    def __init__(self, brain: Brain, *, log_file: Path | None = None) -> None:
        super().__init__()
        self._brain = brain
        self._brain.emit = self._emit_from_worker
        self._log_path = log_file
        self._log: TextIO | None = None

    # --- layout -----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="actions-pane"):
                yield Static("⚡ ACTIONS", classes="pane-title")
                yield RichLog(id="actions", wrap=True, markup=True, auto_scroll=True)
            with Vertical(id="reasoning-pane"):
                yield Static("🧠 REASONING", classes="pane-title")
                yield RichLog(id="reasoning", wrap=True, markup=True, auto_scroll=True)
        with Vertical(id="bottom"):
            yield Static("awaiting first status readout…", id="ship-status")
            yield RichLog(id="chat", wrap=True, markup=True, auto_scroll=True)
            with Horizontal(id="controls"):
                yield Button("▶ Start", id="start", variant="success")
                yield Button("■ Stop", id="stop", variant="error")
                yield Input(placeholder="Instruct the pilot… (Enter to send)", id="chat-input")
                yield Static("stopped", id="run-state")
        yield Footer()

    def on_mount(self) -> None:
        if self._log_path is not None:
            self._log = self._log_path.open("a", encoding="utf-8")
            self._log.write(f"\n=== pilot session {datetime.now():%Y-%m-%d %H:%M:%S} — "
                            f"model {self._brain.llm.model} ===\n")
            self._log.flush()
        chat = self.query_one("#chat", RichLog)
        chat.write("[bold]Operator channel.[/bold] Type instructions below; "
                   "▶ Start launches the pilot, ■ Stop pauses it (resume with Start).")

    def on_unmount(self) -> None:
        self._brain.request_stop()
        if self._log is not None:
            self._log.close()

    # --- controls -----------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start_bot()
        elif event.button.id == "stop":
            self.action_stop_bot()

    def action_start_bot(self) -> None:
        if self._brain.running:
            self._chat_note("pilot is already running")
            return
        self.query_one("#run-state", Static).update("[green]running[/green]")
        self.run_worker(self._brain.run, thread=True, exclusive=True, group="brain",
                        exit_on_error=False)

    def action_stop_bot(self) -> None:
        if not self._brain.running:
            self._chat_note("pilot is not running")
            return
        self._brain.request_stop()
        self._chat_note("stop requested — finishing the current cycle…")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        self._record_line("chat", f"[bold magenta]you[/bold magenta] ▸ {escape(text)}", "#chat")
        self._write_log("CHAT", f"operator: {text}")
        self._brain.instruct(text)
        if not self._brain.running:
            # A paused pilot still answers: run exactly one cycle for this instruction.
            self._chat_note("pilot is paused — answering this instruction once")
            self.run_worker(self._brain.run_single, thread=True, exclusive=True,
                            group="brain", exit_on_error=False)

    # --- record routing --------------------------------------------------------------

    def _emit_from_worker(self, record: BotRecord) -> None:
        self.call_from_thread(self._on_record, record)

    def _on_record(self, record: BotRecord) -> None:
        stamp = time.strftime("%H:%M:%S", time.localtime(record.stamp))
        prefix = f"[dim]{stamp}[/dim]"
        text = escape(record.text)  # model-authored text must not read as Rich markup
        if record.kind == "sidebar":  # the condensed StatusSidebar strip, not a log line
            self.query_one("#ship-status", Static).update(text)
            return
        if record.kind == "action":
            self._record_line("action", f"{prefix} [bold cyan]▶ {text}[/bold cyan]", "#actions")
        elif record.kind == "result":
            rejected = record.text.startswith("rejected:")
            color = "red" if rejected else "green"
            self._record_line("result", f"{prefix}   [{color}]{text}[/{color}]", "#actions")
        elif record.kind == "reasoning":
            self._record_line("reasoning", f"{prefix} [italic]{text}[/italic]", "#reasoning")
        elif record.kind == "error":
            self._record_line("error", f"{prefix} [bold red]⚠ {text}[/bold red]", "#actions")
            self._record_line("error", f"[bold red]⚠ {text}[/bold red]", "#chat", log=False)
        else:  # status
            self._record_line("status", f"{prefix} [yellow]{text}[/yellow]", "#chat")
            if record.text == "pilot stopped":
                self.query_one("#run-state", Static).update("[red]stopped[/red]")
        self._write_log(record.kind.upper(), record.text, stamp=record.stamp)

    def _record_line(self, kind: str, markup: str, pane: str, *, log: bool = True) -> None:
        self.query_one(pane, RichLog).write(markup)

    def _chat_note(self, text: str) -> None:
        self.query_one("#chat", RichLog).write(f"[dim]{text}[/dim]")

    def _write_log(self, kind: str, text: str, *, stamp: float | None = None) -> None:
        if self._log is None:
            return
        when = datetime.fromtimestamp(stamp) if stamp else datetime.now()
        self._log.write(f"[{when:%H:%M:%S}] {kind:<9} {text}\n")
        self._log.flush()
