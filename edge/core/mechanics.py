"""Signature-mechanic hooks (DESIGN §6.2) — pure core, no I/O.

The most reusable idea in the reference catalogue is **one memorable systemic hook per
species** rather than uniform stat-blocks. A species may carry one named hook
(`SpeciesConfig.signature_mechanic`: a hook id + authored `params`); the hook is
implemented once here and data-configured per species.

A hook is a **pure** function ``(MechanicContext) -> MechanicResult``. It audits the
player/species state and the hook's `params` and returns:

- the **stage** it advances to — persisted by the reducer in
  ``Player.species_arcs[roster_id][STAGE_FLAG]`` (the WP30 cross-visit arc store), so a
  ladder replays exactly and later lines gate on it via the ``sig_stage`` fact;
- transient **selection facts** for the sig line the reducer then speaks (e.g. a moral
  ``verdict``), merged into the fact dictionary for that one utterance only; and
- bounded **effects** the reducer applies to core state (an attitude offset shift, an
  alignment/experience nudge, a latinum drop, or forming a grudge).

No hook mutates state or emits events — the ``Converse`` reducer (`edge.core.rules`)
owns both, so mechanics stay replay-safe and the layer graph stays acyclic (this module
imports only `edge.core.config`/`edge.core.models`, and sits below `core.rules`). The
first four hooks land in WP33 (`morality_judge`, `literalist`, `flee_drop`,
`influence_gate`); the transactional remainder (`trojan_gift`, `reprogram_unlock`,
`escalating_demand`, `contract_kill`, the brokers) land in WP37 — an unimplemented hook
resolves to ``None`` (the sig line simply speaks with no effect) rather than raising.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from edge.core.config import AliensConfig, SpeciesConfig
from edge.core.models import AlienSpecies, Player

# The reserved `species_arcs` key a mechanic persists its ladder stage under. It rides
# the existing arc store (WP30), so no new Player field / codec entry — and it surfaces
# to selection as both the `sig_stage` fact and `arc.sig_stage` (edge.dialogue.facts).
STAGE_FLAG = "sig_stage"


@dataclass(frozen=True, slots=True)
class MechanicResult:
    """What a hook decides: a stage to persist, facts to speak under, and bounded effects.

    Every effect is optional and bounded; the reducer clamps and applies them. `facts`
    are transient (they gate only the immediately-spoken sig line — e.g. `{verdict:
    blessed}`), while `stage` persists across visits.
    """

    stage: str  # persisted in species_arcs[roster_id][STAGE_FLAG]; "" ⇒ do not persist
    facts: Mapping[str, object] = field(default_factory=dict)
    attitude_delta: float = 0.0  # shift the player's attitude offset with this species
    alignment_delta: int = 0
    experience_delta: int = 0
    latinum_delta: int = 0  # cargo/latinum dropped to the player (flee_drop)
    grudge: bool = False  # form/deepen this species' vendetta against the player (a curse)


@dataclass(frozen=True, slots=True)
class MechanicContext:
    """The pure inputs a hook audits (no `UniverseState` — hooks read player/species only)."""

    player: Player
    species: AlienSpecies
    sc: SpeciesConfig
    aliens: AliensConfig
    stage: str | None  # the ladder stage reached so far (None ⇒ not yet run)
    params: Mapping[str, Any]
    approach: str | None = None  # the keyword of the reply taken (literalist)


def _num(params: Mapping[str, Any], key: str, default: float) -> float:
    value = params.get(key, default)
    return float(value) if isinstance(value, (int, float)) else default


def _int(params: Mapping[str, Any], key: str, default: int) -> int:
    value = params.get(key, default)
    return int(value) if isinstance(value, (int, float)) else default


# --- the built-in hooks (WP33) ---------------------------------------------------------

def morality_judge(ctx: MechanicContext) -> MechanicResult:
    """Audit cumulative conduct → a moral verdict + a blessing or curse (DESIGN §6.2).

    Typically the roaming `singular_entity` (§7): a non-trading arbiter that reads the
    player's **alignment** counter (the §4/WP27 record of aggression vs. virtue — killing
    friendlies lowers it, hunting hostiles raises it) and dispenses a verdict deterministic
    from that conduct. `bless_alignment` / `curse_alignment` (params) name the bands:

    - at or above `bless_alignment` ⇒ **blessed**: an attitude boon + experience;
    - at or below `curse_alignment` ⇒ **cursed**: the judge's condemnation — a grudge
      (which sours the attitude offset through the WP27 machinery the reducer reuses);
    - between ⇒ **weighed**: the ledger is noted, no effect.

    The `verdict` fact selects the matching `sig.morality_judge.verdict` line; the stage
    (`judged_<verdict>`) persists so a re-visit can react to an earlier judgment.
    """
    alignment = ctx.player.alignment
    if alignment >= _int(ctx.params, "bless_alignment", 3):
        return MechanicResult(
            stage="judged_blessed", facts={"verdict": "blessed"},
            attitude_delta=_num(ctx.params, "blessing_attitude", 0.3),
            experience_delta=_int(ctx.params, "blessing_experience", 20))
    if alignment <= _int(ctx.params, "curse_alignment", -3):
        return MechanicResult(stage="judged_cursed", facts={"verdict": "cursed"}, grudge=True)
    return MechanicResult(stage="judged_weighed", facts={"verdict": "weighed"})


def literalist(ctx: MechanicContext) -> MechanicResult:
    """React only to the player's conversational *approach*, ignoring history (DESIGN §6.2).

    A `memory_model=none` machine mind: the reply is keyed solely to the keyword of the
    approach the player took (via the authored `keyword_map`), so the same words always
    get the same reaction regardless of standing — and a misread offer (e.g. "peace")
    can map to `hostile`. Nothing persists (`stage=""`); the `reaction` fact selects the
    matching `sig.literalist.reply` line.
    """
    keyword_map = ctx.params.get("keyword_map", {})
    reaction = "confused"
    if isinstance(keyword_map, Mapping):
        reaction = str(keyword_map.get(ctx.approach or "", ctx.params.get("default_reaction", "confused")))
    return MechanicResult(stage="", facts={"reaction": reaction})


def flee_drop(ctx: MechanicContext) -> MechanicResult:
    """A weak species flees on contact, dropping collectable cargo packets (DESIGN §6.2).

    One-shot: the first contact drops `drop_latinum` slips (a `cargo_packets` proxy — no
    hold needed, latinum straight to the player) and marks the stage `fled`; a later
    contact finds the packets already scooped (`drop=0`). The `fled` fact selects the
    matching `sig.flee_drop.contact` line.
    """
    drop = 0 if ctx.stage == "fled" else _int(ctx.params, "drop_latinum", 150)
    return MechanicResult(stage="fled", facts={"fled": True}, latinum_delta=drop)


def influence_gate(ctx: MechanicContext) -> MechanicResult:
    """The species can forbid being attacked while in contact (DESIGN §6.2).

    The gating itself is enforced by `attack_forbidden` (the FIGHT/attack reply is
    withheld when `cannot_attack_unbidden`); the hook records that contact was gated so a
    line can name the influence (`influenced` fact). `compel` / `breakthrough` are Phase-5
    depth.
    """
    return MechanicResult(stage="gated", facts={"influenced": True})


# The registry keyed by hook id (DESIGN §6.2 / `KNOWN_SIGNATURE_HOOKS`). WP33 lands these
# four; the rest resolve to `None` in `run_hook` until WP37.
MECHANIC_HOOKS: dict[str, Callable[[MechanicContext], MechanicResult]] = {
    "morality_judge": morality_judge,
    "literalist": literalist,
    "flee_drop": flee_drop,
    "influence_gate": influence_gate,
}


def run_hook(ctx: MechanicContext) -> MechanicResult | None:
    """Run the species' signature hook, or `None` if it has none / is not yet implemented.

    A species with no `signature_mechanic`, or one whose hook is a WP37-and-later type not
    yet in `MECHANIC_HOOKS`, resolves to `None` — the reducer then just speaks the sig line
    with no effect, so authoring a `sig.*` branch never crashes on an inert hook.
    """
    mechanic = ctx.sc.signature_mechanic
    if mechanic is None:
        return None
    hook = MECHANIC_HOOKS.get(mechanic.hook)
    return hook(ctx) if hook is not None else None


def attack_forbidden(sc: SpeciesConfig) -> bool:
    """Whether an `influence_gate` species forbids the player attacking it (DESIGN §6.2).

    Drives the FIGHT/attack reply's availability: a `cannot_attack_unbidden` influence-gate
    species cannot be struck while in contact (the reply is withheld / rejected with a
    reason naming the gate, distinct from the plain Phase-3 attack lock).
    """
    mechanic = sc.signature_mechanic
    return (
        mechanic is not None
        and mechanic.hook == "influence_gate"
        and bool(mechanic.params.get("cannot_attack_unbidden"))
    )
