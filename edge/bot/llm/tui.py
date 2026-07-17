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
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import TextIO

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

from edge.bot.llm.brain import BotRecord, Brain


class LLMBotApp(App[None]):
    """Start/stop the pilot, read its actions and reasoning, talk to it."""

    TITLE = "Edge of the Unknown — LLM pilot"
    BINDINGS = [
        Binding("ctrl+s", "toggle_bot", "Start"),
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
        self._log_handle: TextIO | None = None
        self._pilot_active = brain.running

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
                if self._pilot_active:
                    yield Button("■ Stop", id="run-toggle", variant="error")
                else:
                    yield Button("▶ Start", id="run-toggle", variant="success")
                yield Input(placeholder="Instruct the pilot… (Enter to send)", id="chat-input")
                yield Static("running" if self._pilot_active else "stopped", id="run-state")
        yield Footer()

    def on_mount(self) -> None:
        if self._log_path is not None:
            self._log_handle = self._log_path.open("a", encoding="utf-8")
            self._log_handle.write(f"\n=== pilot session {datetime.now():%Y-%m-%d %H:%M:%S} — "
                                   f"model {self._brain.llm.model} ===\n")
            self._log_handle.flush()
        chat = self.query_one("#chat", RichLog)
        chat.write("[bold]Operator channel.[/bold] Type instructions below; "
                   "Ctrl-S toggles ▶ Start / ■ Stop to run or pause the pilot.")
        self._set_run_control(self._pilot_active)

    def on_unmount(self) -> None:
        self._brain.request_stop()
        if self._log_handle is not None:
            self._log_handle.close()

    # --- controls -----------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-toggle":
            self.action_toggle_bot()

    def action_toggle_bot(self) -> None:
        """Start or stop the pilot according to the control's current state."""
        if self._pilot_active:
            self.action_stop_bot()
        else:
            self.action_start_bot()

    def action_start_bot(self) -> None:
        if self._brain.running:
            self._chat_note("pilot is already running")
            self._set_run_control(True)
            return
        self._set_run_control(True)
        self.run_worker(self._brain.run, thread=True, exclusive=True, group="brain",
                        exit_on_error=False)

    def action_stop_bot(self) -> None:
        if not self._brain.running:
            self._chat_note("pilot is not running")
            self._set_run_control(False)
            return
        self._brain.request_stop()
        self._chat_note("stop requested — finishing the current cycle…")

    def _set_run_control(self, active: bool) -> None:
        """Keep the shared button and Ctrl-S footer label in sync with pilot state."""
        self._pilot_active = active
        label = "Stop" if active else "Start"
        button = self.query_one("#run-toggle", Button)
        button.label = f"■ {label}" if active else f"▶ {label}"
        button.variant = "error" if active else "success"
        self.query_one("#run-state", Static).update(
            "[green]running[/green]" if active else "[red]stopped[/red]"
        )

        # Textual bindings are immutable values; replace the toggle binding so Footer
        # advertises what Ctrl-S will do *now*, while the action and key stay fixed.
        bindings = self._bindings.key_to_bindings.get("ctrl+s", [])
        self._bindings.key_to_bindings["ctrl+s"] = [
            replace(binding, description=label)
            if binding.action == "toggle_bot" else binding
            for binding in bindings
        ]
        self.refresh_bindings()

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
                self._set_run_control(False)
        self._write_log(record.kind.upper(), record.text, stamp=record.stamp)

    def _record_line(self, kind: str, markup: str, pane: str, *, log: bool = True) -> None:
        self.query_one(pane, RichLog).write(markup)

    def _chat_note(self, text: str) -> None:
        self.query_one("#chat", RichLog).write(f"[dim]{text}[/dim]")

    def _write_log(self, kind: str, text: str, *, stamp: float | None = None) -> None:
        if self._log_handle is None:
            return
        when = datetime.fromtimestamp(stamp) if stamp else datetime.now()
        self._log_handle.write(f"[{when:%H:%M:%S}] {kind:<9} {text}\n")
        self._log_handle.flush()
