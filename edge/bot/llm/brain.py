"""The pilot's brain: a paced observe → decide → act loop over Ollama (dev-only).

Each action cycle builds one observation (`describe.observe`), asks the model for one
schema-constrained decision (`reasoning` + `action` + args), executes it through the
`ActionCatalog`, and reports everything as typed `BotRecord`s to a sink (the TUI, a log
file, a print). General operator queries use a separate answer-only schema and never execute
an action or consume a game turn. The loop is **paced to human speed**: a cycle never
completes faster than `pace` seconds wall-clock (model latency counts toward it), so a pilot
plays at roughly the cadence a person clicking the real TUI would.

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
from typing import Literal

from edge.bot.llm.actions import DECISION_SCHEMA, ActionCatalog, ActionOutcome
from edge.bot.llm.describe import observe, sidebar
from edge.bot.llm.ollama import OllamaChat, OllamaError
from edge.bot.runner import BotRunner

SYSTEM_PROMPT = """\
You are the pilot of a starship in Edge of the Unknown, a game of space exploration and
trading descended from TradeWars 2002. Each cycle you receive one observation of what your
ship can see and a list of available actions; you answer with a JSON decision: a short
`reasoning` (1-3 sentences, ship's-log voice, concrete and factual), an
`operator_response`, and exactly one `action` with its arguments.

Your standing goals, in order:
1. Serve the CURRENT OBJECTIVE block, when present — it is the operator's standing order
   and outranks every goal below, every cycle, until you retire it. When (and only when)
   it is fully accomplished, choose the `objective_done` action to retire it. A new objective
   replaces it.
2. Survive — flee fights you are losing; keep some latinum in reserve.
3. Explore outward: chart unexplored warps, survey planets, salvage discoveries.
4. Trade profitably (buy where a port sells cheap, sell where one buys dear) to fund upgrades.

Practical rules:
- Act on what the observation actually shows; ids (sector, planet_id, species_id,
  discovery_id) must come from it verbatim.
- Before plotting movement for an objective, check the `SHIP'S COMPUTER` records for its
  named destination. Match objectives against Stardock location, known ports and planets,
  Codex discoveries, leads, dossier last-seen locations, and contract destinations; use the
  exact displayed sector with `travel_to`. Do not guess a sector or wander when the computer
  already supplies coordinates. If the destination is not in the computer or local sector
  observation, explore for information instead of inventing coordinates.
- Fill in the argument fields your action needs; leave the others at their unused value
  (0, -1 for offer_index, "" for commodity). Set `operator_response` to a concise direct
  acknowledgment when a NEW OBJECTIVE arrives, or a completion report when choosing
  `objective_done`; otherwise set it to "". Example decision:
  {"reasoning": "Sector 12 is an unexplored warp one hop out; charting it serves the
   exploration goal.", "operator_response": "", "action": "warp", "sector": 12,
   "commodity": "", "units": 0, "planet_id": 0, "species_id": 0,
   "discovery_id": 0, "starbase_id": 0, "offer_index": -1, "subsystem": "",
   "slot_index": -1, "count": 0}
- You must dock before trading, and descend before exploring a surface.
- Markets, Stardock facilities, and orbital starbases are different destinations. Use
  `dock_trading_port` only to enter a port's commodities market and trade. At Stardock, use
  `dock_stardock`
  instead when you want hardware, the interest-bearing bank, colonist recruitment, tavern
  rumors, or shipyard services; it costs the same one docking turn. Use `dock_starbase
  {starbase_id}` only to board an orbital starbase; boarding itself costs no turn, and the
  base offers only the services named in its observation.
  Typically only your own operational starbase offers hardware and banking; an open foreign
  base may offer its commodities market, while a hostile or damaged base withholds services.
  Starbases never recruit colonists or sell tavern rumors.
- If an action is rejected, read the reason and try something different, not the same thing.
- Never waste cycles: prefer a concrete action over `wait`.
"""

QUERY_SYSTEM_PROMPT = """\
You are the pilot of a starship in Edge of the Unknown. Answer the operator's general
question directly, concisely, and factually from the supplied observation and conversation
context. This is an answer-only exchange: do not choose, claim, or perform an in-game action,
and do not alter the current objective. Return only the schema-shaped response.
"""

QUERY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "response": {
            "type": "string",
            "description": "a concise direct answer to the operator",
        },
    },
    "required": ["response"],
}

_HISTORY_ROUNDS = 8  # decision/result pairs kept in the model's context

InstructionMode = Literal["objective", "query"]


@dataclass(frozen=True)
class BotRecord:
    """One reportable moment: reasoning / action / result / operator / status / error."""

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
        self._orders: queue.SimpleQueue[tuple[InstructionMode, str]] = queue.SimpleQueue()
        self._fresh_objectives: list[str] = []
        self._pending_queries: list[str] = []
        # The operator's standing order: rendered into EVERY prompt (not just the arrival
        # cycle) until the model retires it with `objective_done` or a newer instruction
        # replaces it — so a multi-cycle directive survives the rolling history window.
        self._objective: str | None = None
        self._last_rejection: tuple[str, str, str] | None = None
        self._history: list[dict[str, str]] = []
        self._stop = threading.Event()
        self._running = threading.Event()
        self._pace_lock = threading.Lock()

    # --- cross-thread controls (the TUI calls these) --------------------------

    def instruct(self, text: str, *, mode: InstructionMode = "objective") -> None:
        """Queue an objective change or answer-only query for the next cycle."""
        self._orders.put((mode, text.strip()))

    def request_stop(self) -> None:
        self._stop.set()

    def adjust_pace(self, delta: float) -> float:
        """Change the live minimum seconds/action, clamped at no artificial delay."""
        with self._pace_lock:
            self.pace = max(0.0, self.pace + delta)
            return self.pace

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

        A queued query is answered without acting; a queued objective is acknowledged while
        beginning work with one action. The pilot then returns to its paused state. A no-op
        when the main loop is already running (the live loop will pick the message up itself).
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
        observation = observe(
            self.bot,
            boarded_starbase_id=self.catalog.boarded_starbase_id,
            docked_port_sector_id=self.catalog.docked_port_sector_id,
            stardock_facilities_sector_id=self.catalog.stardock_facilities_sector_id,
        )
        if self._pending_queries:
            self._answer_queries(observation)
            return False

        game = self.bot.game()
        if game.turns <= 0:
            self._emit("status", "out of turns — the day is spent")
            return True

        decision = self.llm.chat(self._messages(observation), schema=DECISION_SCHEMA)
        if self._stop.is_set():  # stop pressed while the model was thinking
            return True

        reasoning = str(decision.get("reasoning", "")).strip() or "(no reasoning given)"
        operator_response = str(decision.get("operator_response", "")).strip()
        action = str(decision.get("action", "")).strip()
        # Show only the arguments actually in play (unused fields ride as 0 / -1 / "").
        args = {k: v for k, v in decision.items()
                if k not in ("reasoning", "operator_response", "action")
                and v not in (None, 0, -1, "")}
        self._emit("reasoning", reasoning)
        if operator_response:
            self._emit("operator", operator_response)
        self._emit("action", f"{action} {json.dumps(args)}" if args else action)

        if action == "objective_done":  # brain-level: retire the standing order
            outcome = self._retire_objective(operator_response_sent=bool(operator_response))
        else:
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
        for objective in self._fresh_objectives:  # consumed: ordinary history from here on
            self._history.append({"role": "user", "content": f"NEW OBJECTIVE: {objective}"})
        self._fresh_objectives.clear()
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

    def _answer_queries(self, observation: str) -> None:
        """Answer queued general questions without executing or budgeting an action."""
        queries = list(self._pending_queries)
        parts = [observation]
        if self._objective:
            parts += ["", "== CURRENT OBJECTIVE (context only; do not change it) ==",
                      self._objective]
        parts += ["", "== OPERATOR QUERIES ==", *[f"- {query}" for query in queries]]
        user = {"role": "user", "content": "\n".join(parts)}
        response = self.llm.chat(
            [{"role": "system", "content": QUERY_SYSTEM_PROMPT}, *self._history, user],
            schema=QUERY_SCHEMA,
        )
        answer = str(response.get("response", "")).strip() or "I have no answer to report."
        del self._pending_queries[:len(queries)]
        self._emit("operator", answer)
        self._history.append({"role": "user", "content": "\n".join(
            f"OPERATOR QUERY: {query}" for query in queries
        )})
        self._history.append({"role": "assistant", "content": answer})
        del self._history[:-2 * _HISTORY_ROUNDS]

    # --- prompt assembly ---------------------------------------------------------

    def _messages(self, observation: str) -> list[dict[str, str]]:
        parts = [observation, "", "== AVAILABLE ACTIONS ==", self.catalog.usage()]
        if self._objective:
            parts += ["- objective_done — the CURRENT OBJECTIVE is fully accomplished; retire it",
                      "", "== CURRENT OBJECTIVE (the operator's standing order) ==",
                      self._objective,
                      "Check SHIP'S COMPUTER for this objective's sector before navigating."]
        if self._fresh_objectives:  # arrival-cycle acknowledgment (then ordinary history)
            parts += ["", "== NEW OBJECTIVE (acknowledge directly, then begin work) =="]
            parts += [f"- {objective}" for objective in self._fresh_objectives]
        parts += ["", "Choose exactly one action now."]
        user = {"role": "user", "content": "\n".join(parts)}
        return [{"role": "system", "content": SYSTEM_PROMPT}, *self._history, user]

    def _drain_orders(self) -> None:
        """Separate queued queries from persistent objective changes."""
        while True:
            try:
                mode, text = self._orders.get_nowait()
            except queue.Empty:
                return
            if not text:
                continue
            if mode == "query":
                self._pending_queries.append(text)
            else:
                self._fresh_objectives[:] = [text]
                replaced = " (replaces the previous objective)" if self._objective else ""
                self._objective = text
                self._emit("status", f"objective set: {text}{replaced}")

    def _retire_objective(self, *, operator_response_sent: bool) -> ActionOutcome:
        if self._objective is None:
            return ActionOutcome(False, "there is no current objective to retire")
        done, self._objective = self._objective, None
        if not operator_response_sent:
            self._emit("operator", f"Objective complete: {done}")
        return ActionOutcome(True, f"objective accomplished and retired: {done}")

    # --- plumbing ------------------------------------------------------------------

    def _emit(self, kind: str, text: str) -> None:
        self.emit(BotRecord(kind=kind, text=text))

    def _pace_sleep(self, started: float) -> None:
        """Sleep out the remainder of the pace window, waking promptly on stop."""
        while not self._stop.is_set():
            with self._pace_lock:
                pace = self.pace
            remaining = pace - (time.monotonic() - started)
            if remaining <= 0:
                return
            time.sleep(min(0.2, remaining))
