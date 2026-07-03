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
`escalating_demand`, `contract_kill`, `coordinate_broker`, `passage_broker`) land in WP37,
each a stage machine driven by the reply keyword (`MechanicContext.approach`). A hook id
not in `MECHANIC_HOOKS` still resolves to ``None`` (the sig line simply speaks with no
effect) rather than raising, so a roster may name a hook the code has not yet grown.
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


# --- the transactional hooks (WP37) ----------------------------------------------------
#
# Each is a pure stage machine driven by the reply keyword (`ctx.approach`, the last segment
# of the `sig.<hook>.<node>` context the reducer routes into) + the persisted `stage` + the
# authored `params`. Effects stay within the framework's bounded set (attitude / alignment /
# experience / latinum / grudge); the deeper cross-system reach of a few hooks is a documented
# forward seam (the trojan's device/hold-occupying payload and delayed cron trigger, the live
# cross-faction `trade_posture` flip, and `contract_kill`'s actual razing + reward payout —
# WP40). No default species yet routes a `choices` reply into these `sig.*` contexts, so like
# WP33's flee_drop/literalist they are registry-complete + unit-tested but not corpus-wired.

def trojan_gift(ctx: MechanicContext) -> MechanicResult:
    """A 'gift' / 'lower your shields' seeds a delayed harmful payload; a rival sells the
    removal (DESIGN §6.2). Ladder: offered → carried (a sweetener paid up front, the trap now
    aboard) → either defused (paid removal at the counter-market) or sprung (the payload
    detonates, draining latinum). The device/hold-occupying `effect` and cron `delay` are a
    forward seam — here the payload is a bounded latinum loss so the machine stays exercisable
    and replay-safe."""
    stage = ctx.stage or ""
    approach = ctx.approach
    if stage in ("defused", "sprung", "declined"):
        return MechanicResult(stage=stage, facts={"trojan": stage})
    if stage == "carried":
        if approach in ("defuse", "purge", "remove"):
            return MechanicResult(stage="defused", facts={"trojan": "defused"},
                                  latinum_delta=-_int(ctx.params, "removal_cost", 120))
        # Any other contact while carrying: the delayed payload springs.
        return MechanicResult(stage="sprung", facts={"trojan": "sprung"},
                              latinum_delta=-_int(ctx.params, "payload_latinum", 300))
    if approach in ("accept", "lower_shields", "take"):
        return MechanicResult(stage="carried", facts={"trojan": "carried"},
                              latinum_delta=_int(ctx.params, "gift_latinum", 200))
    if approach in ("refuse", "decline"):
        return MechanicResult(stage="declined", facts={"trojan": "declined"})
    return MechanicResult(stage="offered", facts={"trojan": "offered"})


def reprogram_unlock(ctx: MechanicContext) -> MechanicResult:
    """Installing an item flips another faction's `trade_posture` (DESIGN §6.2). The live
    cross-faction posture flip + item consumption need per-player faction state (a forward
    seam); the stage machine here records the install, pays a one-time experience boon, and
    binds `{target}`/`{posture}` for the line. approach: install → unlocked; decline → held."""
    stage = ctx.stage or ""
    approach = ctx.approach
    target = str(ctx.params.get("target_species") or ctx.params.get("source_species") or "them")
    posture = str(ctx.params.get("new_posture", "open"))
    base = {"reprogram_target": target, "reprogram_posture": posture}
    if stage == "unlocked":
        return MechanicResult(stage="unlocked", facts={**base, "reprogram": "unlocked"})
    if approach in ("install", "reprogram", "accept"):
        return MechanicResult(stage="unlocked", facts={**base, "reprogram": "unlocked"},
                              experience_delta=_int(ctx.params, "unlock_experience", 10))
    if approach in ("decline", "refuse"):
        return MechanicResult(stage="declined", facts={**base, "reprogram": "declined"})
    return MechanicResult(stage="offered", facts={**base, "reprogram": "offered"})


def escalating_demand(ctx: MechanicContext) -> MechanicResult:
    """Befriending opens a ladder of mounting demands; comply and standing holds, fail once
    and `betrayal_model=permanent` triggers (DESIGN §6.2). The `demand_ladder` param names the
    rungs; each comply climbs one (a small attitude reward) until satisfied (a boon), while a
    single refuse routes through the WP27 grudge machinery (permanent for these species)."""
    ladder = ctx.params.get("demand_ladder", [])
    rungs = [str(x) for x in ladder] if isinstance(ladder, (list, tuple)) else []
    stage = ctx.stage or ""
    if stage in ("satisfied", "betrayed"):
        return MechanicResult(stage=stage, facts={"demand": stage})
    tail = stage.split("_", 1)[1] if stage.startswith("demand_") else ""
    rung = int(tail) if tail.isdigit() else 0
    approach = ctx.approach
    if approach in ("refuse", "fail", "defy"):
        return MechanicResult(stage="betrayed", facts={"demand": "betrayed"}, grudge=True)
    if approach in ("comply", "obey", "donate", "pay"):
        nxt = rung + 1
        if not rungs or nxt >= len(rungs):
            return MechanicResult(stage="satisfied", facts={"demand": "satisfied"},
                                  attitude_delta=_num(ctx.params, "satisfied_attitude", 0.25),
                                  experience_delta=_int(ctx.params, "satisfied_experience", 15))
        return MechanicResult(stage=f"demand_{nxt}", facts={"demand": rungs[nxt], "rung": nxt},
                              attitude_delta=_num(ctx.params, "step_attitude", 0.05))
    label = rungs[rung] if rung < len(rungs) else "tribute"
    return MechanicResult(stage=f"demand_{rung}", facts={"demand": label, "rung": rung})


def contract_kill(ctx: MechanicContext) -> MechanicResult:
    """Pays for razing the starbases of named rival species so the patron can move in
    (DESIGN §6.2). WP37 authors and gates the contract; the razing mechanics + reward payout
    land in WP40. Ladder: offered → contracted (obligation taken) or declined (a `redemption`
    path leaves it recoverable). `targets`/`reward` bind the line and drive WP40."""
    stage = ctx.stage or ""
    approach = ctx.approach
    targets = ctx.params.get("targets", [])
    target = str(targets[0]) if isinstance(targets, (list, tuple)) and targets else "a rival"
    base = {"contract_target": target}
    if stage == "contracted":
        return MechanicResult(stage="contracted", facts={**base, "contract": "contracted"})
    if approach in ("accept", "take"):
        return MechanicResult(stage="contracted", facts={**base, "contract": "contracted"})
    if approach in ("decline", "refuse"):
        return MechanicResult(stage="declined", facts={**base, "contract": "declined"})
    return MechanicResult(stage="offered", facts={**base, "contract": "offered"})


def coordinate_broker(ctx: MechanicContext) -> MechanicResult:
    """A predatory species that trades in the coordinates of undefended worlds (DESIGN §6.2).
    The friendly slice — buying tips — is the live map mechanic (`offer_coordinates`, §6.7);
    the hostile side authored here **extorts**: pay it off (a latinum drain) or refuse and earn
    its vendetta. approach: pay → paid; refuse → spurned (grudge)."""
    stage = ctx.stage or ""
    approach = ctx.approach
    if stage in ("paid", "spurned"):
        return MechanicResult(stage=stage, facts={"broker": stage})
    if approach in ("pay", "appease"):
        return MechanicResult(stage="paid", facts={"broker": "paid"},
                              latinum_delta=-_int(ctx.params, "extort_latinum", 250))
    if approach in ("refuse", "defy"):
        return MechanicResult(stage="spurned", facts={"broker": "spurned"}, grudge=True)
    return MechanicResult(stage="extorted", facts={"broker": "extorted"})


def passage_broker(ctx: MechanicContext) -> MechanicResult:
    """Sells information / special transit for goods or the player's home base (DESIGN §6.2).
    The hostile side authored here **misleads**: paying the price buys nothing (a latinum
    drain, no benefit); refusing simply ends it. approach: pay → misled; refuse → declined."""
    stage = ctx.stage or ""
    approach = ctx.approach
    if stage in ("misled", "declined"):
        return MechanicResult(stage=stage, facts={"passage": stage})
    if approach in ("pay", "accept"):
        return MechanicResult(stage="misled", facts={"passage": "misled"},
                              latinum_delta=-_int(ctx.params, "price_latinum", 200))
    if approach in ("refuse", "decline"):
        return MechanicResult(stage="declined", facts={"passage": "declined"})
    return MechanicResult(stage="offered", facts={"passage": "offered"})


# The registry keyed by hook id (DESIGN §6.2 / `KNOWN_SIGNATURE_HOOKS`). WP33 landed the first
# four; WP37 adds the transactional remainder. An id absent here still resolves to `None` in
# `run_hook` (an inert sig line), so the roster may name a hook the code has not yet grown.
MECHANIC_HOOKS: dict[str, Callable[[MechanicContext], MechanicResult]] = {
    "morality_judge": morality_judge,
    "literalist": literalist,
    "flee_drop": flee_drop,
    "influence_gate": influence_gate,
    "trojan_gift": trojan_gift,
    "reprogram_unlock": reprogram_unlock,
    "escalating_demand": escalating_demand,
    "contract_kill": contract_kill,
    "coordinate_broker": coordinate_broker,
    "passage_broker": passage_broker,
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
