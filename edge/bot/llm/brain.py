"""The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only).

Each cycle builds one observation (`describe.observe`), asks the model for one
schema-constrained decision (`reasoning` + `action` + args), executes it through the
`ActionCatalog`, and reports everything as typed `BotRecord`s to a sink (the TUI, a log
file, a print). The loop is **paced to human speed**: a cycle never completes faster than
`pace` seconds wall-clock (model latency counts toward it), so a pilot plays at roughly
the cadence a person clicking the real TUI would.

Thread-shaped for the TUI: `run()` blocks (run it in a worker thread); `instruct()` and
`request_stop()` are safe to call from any other thread.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from edge.bot.llm.actions import DECISION_SCHEMA, ActionCatalog
from edge.bot.llm.describe import observe, sidebar
from edge.bot.llm.ollama import OllamaChat, OllamaError
from edge.bot.runner import BotRunner

SYSTEM_PROMPT = """\
You are the pilot of a starship in Edge of the Unknown, a game of space exploration and
trading descended from TradeWars 2002. Each cycle you receive one observation of what your
ship can see and a list of available actions; you answer with a JSON decision: a short
`reasoning` (1-3 sentences, ship's-log voice, concrete and factual) and exactly one `action`
with its arguments.

Your standing goals, in order:
1. Respond to a fresh operator instruction (the OPERATOR INSTRUCTIONS block, when present)
   above all else — answer it in your reasoning and act on it now. Earlier OPERATOR lines
   in the conversation are past context you already handled, not standing orders.
2. Survive — flee fights you are losing; keep some latinum in reserve.
3. Explore outward: chart unexplored warps, survey planets, salvage discoveries.
4. Trade profitably (buy where a port sells cheap, sell where one buys dear) to fund upgrades.

Practical rules:
- Act on what the observation actually shows; ids (sector, planet_id, species_id,
  discovery_id) must come from it verbatim.
- Fill in the argument fields your action needs; leave the others at their unused value
  (0, -1 for offer_index, "" for commodity). Example decision:
  {"reasoning": "Sector 12 is an unexplored warp one hop out; charting it serves the
   exploration goal.", "action": "warp", "sector": 12, "commodity": "", "units": 0,
   "planet_id": 0, "species_id": 0, "discovery_id": 0, "offer_index": -1, "count": 0}
- You must dock before trading, and descend before exploring a surface.
- If an action is rejected, read the reason and try something different, not the same thing.
- Never waste cycles: prefer a concrete action over `wait`.
"""

_HISTORY_ROUNDS = 8  # decision/result pairs kept in the model's context


@dataclass(frozen=True)
class BotRecord:
    """One reportable moment: kind is reasoning / action / result / chat / status / error."""

    kind: str
    text: str
    stamp: float = field(default_factory=time.time)


Sink = Callable[[BotRecord], None]


class Brain:
    """One pilot: owns the model client, the action catalog, and the paced loop."""

    def __init__(self, bot: BotRunner, llm: OllamaChat, *, pace: float = 6.0,
                 max_actions: int = 0, emit: Sink | None = None) -> None:
        self.bot = bot
        self.llm = llm
        self.pace = pace
        self.max_actions = max_actions  # 0 => unlimited
        self.emit: Sink = emit or (lambda record: None)
        self.catalog = ActionCatalog(bot)
        self.actions_taken = 0
        self._orders: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._fresh_orders: list[str] = []  # drained this cycle; answered once, then history
        self._last_rejection: tuple[str, str, str] | None = None
        self._history: list[dict[str, str]] = []
        self._stop = threading.Event()
        self._running = threading.Event()

    # --- cross-thread controls (the TUI calls these) --------------------------

    def instruct(self, text: str) -> None:
        """Queue an operator instruction; picked up at the start of the next cycle."""
        self._orders.put(text.strip())

    def request_stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    # --- the loop --------------------------------------------------------------

    def run(self) -> None:
        """Blocking loop; run in a worker thread. Restartable after a stop."""
        self._stop.clear()
        self._running.set()
        self._emit("status", f"pilot online — model {self.llm.model} @ {self.llm.host}, "
                             f"pace {self.pace:g}s/action")
        try:
            self._emit("sidebar", sidebar(self.bot))
            while not self._stop.is_set():
                started = time.monotonic()
                try:
                    if self._cycle():
                        break
                except OllamaError as exc:
                    self._emit("error", f"{exc} — retrying next cycle")
                except Exception as exc:  # noqa: BLE001 — keep the TUI alive, report, halt
                    self._emit("error", f"pilot halted on an unexpected error: {exc!r}")
                    break
                self._pace_sleep(started)
        finally:
            self._running.clear()
            self._emit("status", "pilot stopped")

    def run_single(self) -> None:
        """One cycle while paused — lets the operator chat with a stopped pilot.

        The queued instruction is observed, answered (reasoning + one action), and the
        pilot returns to its paused state. A no-op when the main loop is already running
        (the live loop will pick the instruction up itself).
        """
        if self._running.is_set():
            return
        self._stop.clear()
        self._running.set()
        try:
            self._cycle()
        except OllamaError as exc:
            self._emit("error", str(exc))
        except Exception as exc:  # noqa: BLE001 — report, stay paused
            self._emit("error", f"pilot errored answering the instruction: {exc!r}")
        finally:
            self._running.clear()
            self._emit("status", "pilot idle — still paused (▶ Start to resume)")

    def _cycle(self) -> bool:
        """One observe→decide→act cycle. Returns True when the run should end."""
        self._drain_orders()
        game = self.bot.game()
        if game.turns <= 0:
            self._emit("status", "out of turns — the day is spent")
            return True

        observation = observe(self.bot)
        decision = self.llm.chat(self._messages(observation), schema=DECISION_SCHEMA)
        if self._stop.is_set():  # stop pressed while the model was thinking
            return True

        reasoning = str(decision.get("reasoning", "")).strip() or "(no reasoning given)"
        action = str(decision.get("action", "")).strip()
        # Show only the arguments actually in play (unused fields ride as 0 / -1 / "").
        args = {k: v for k, v in decision.items()
                if k not in ("reasoning", "action") and v not in (None, 0, -1, "")}
        self._emit("reasoning", reasoning)
        self._emit("action", f"{action} {json.dumps(args)}" if args else action)

        outcome = self.catalog.execute(decision)
        self._emit("result", ("" if outcome.ok else "rejected: ") + outcome.summary)
        self._emit("sidebar", sidebar(self.bot))
        self.actions_taken += 1

        # Rolling memory: the decision and what came of it (observations stay per-cycle).
        result_note = f"RESULT: {'ok' if outcome.ok else 'REJECTED'} — {outcome.summary}"
        repeat = (action, str(args), outcome.summary)
        if not outcome.ok and repeat == self._last_rejection:
            result_note += ("\nThat exact action just failed the same way. Do NOT repeat it — "
                            "choose a different action this time.")
        self._last_rejection = repeat if not outcome.ok else None
        for order in self._fresh_orders:  # consumed: ordinary history from here on
            self._history.append({"role": "user", "content": f"OPERATOR: {order}"})
        self._history.append({"role": "assistant", "content": json.dumps(decision)})
        self._history.append({"role": "user", "content": result_note})
        del self._history[:-2 * _HISTORY_ROUNDS]

        if action == "stop" and outcome.ok:
            self._emit("status", "pilot ended the run")
            return True
        if self.max_actions and self.actions_taken >= self.max_actions:
            self._emit("status", f"action budget spent ({self.max_actions})")
            return True
        return False

    # --- prompt assembly ---------------------------------------------------------

    def _messages(self, observation: str) -> list[dict[str, str]]:
        parts = [observation, "", "== AVAILABLE ACTIONS ==", self.catalog.usage()]
        if self._fresh_orders:  # answered this cycle only; kept as ordinary history after
            parts += ["", "== OPERATOR INSTRUCTIONS (respond to these now) =="]
            parts += [f"- {order}" for order in self._fresh_orders]
        parts += ["", "Choose exactly one action now."]
        user = {"role": "user", "content": "\n".join(parts)}
        return [{"role": "system", "content": SYSTEM_PROMPT}, *self._history, user]

    def _drain_orders(self) -> None:
        """Move queued chat into this cycle's fresh-order list (each answered exactly once).

        A consumed instruction then rides the rolling history as an ordinary message —
        recent context, not a permanent standing order — and fades with the window.
        """
        self._fresh_orders.clear()
        while True:
            try:
                order = self._orders.get_nowait()
            except queue.Empty:
                return
            if order:
                self._fresh_orders.append(order)
                self._emit("status", f"operator instruction received: {order}")

    # --- plumbing ------------------------------------------------------------------

    def _emit(self, kind: str, text: str) -> None:
        self.emit(BotRecord(kind=kind, text=text))

    def _pace_sleep(self, started: float) -> None:
        """Sleep out the remainder of the pace window, waking promptly on stop."""
        while not self._stop.is_set():
            remaining = self.pace - (time.monotonic() - started)
            if remaining <= 0:
                return
            time.sleep(min(0.2, remaining))
