"""Headless seed matrix for the ground assault — the table that sits beside the watching.

GW-WP22 rejected a batch runner, and was right to at the time: with a bot that never
closed with the objective, every row read `retrieval` at turn 24 and the table graded the
bot while looking like it graded the balance. GW-WP23 removed that objection by making the
bot reach and enter the objective, so the matrix returns (D26) — but it returns with the
lesson attached.

**This reports diagnostics, not just outcomes.** A win/loss column alone is exactly the
artefact that misled before: it compresses "the platoon never arrived" and "the platoon
arrived and lost" into one indistinguishable row. So every run also reports *how the
fight went* — when contact happened, when the wall was breached, how fast Resolve
actually fell, and what the platoon had left when it got inside. A degenerate bot then
shows up as a visible column (`breach=—` across the board) instead of hiding behind a
uniform outcome, and the table stays honest about which of the two things it is measuring.

Pairs with the watched run rather than replacing it: the table says *which* seeds are
worth opening in `edge-groundwar --pilot bot`, and the watching says why. Run with:

    python -m edge.groundwar.matrix
    python -m edge.groundwar.matrix --seeds 1,2,3 --citadel 0,2 --cloud-city 2
"""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass

from edge.bot.scripts import assaulter
from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.groundwar.assault import assault_map_for
from edge.core.groundwar.models import AssaultOperation
from edge.core.rules import GroundFire
from edge.groundwar import harness
from edge.groundwar.spectate import RecordingRunner, Scenario, build_state
from edge.server.service import GameService
from edge.store.repo import SqliteRepository

# Generous: a full operation is bounded by its own retrieval clock, so this only has to
# outlast the per-action cadence (one command per step, ~2 actions per trooper per turn).
_MAX_STEPS = 4_000


@dataclass(frozen=True)
class Row:
    """One scenario's run, in the columns a balance read actually needs."""

    scenario: Scenario
    outcome: str
    turns: int
    retrieval_turn: int
    contact_turn: int | None  # first turn the platoon had something worth shooting
    breach_turn: int | None  # first turn a trooper stood inside the objective
    resolve_start: int
    resolve_end: int
    strength: int
    casualties: int
    casualties_at_breach: int | None

    @property
    def resolve_per_turn(self) -> float:
        return (self.resolve_start - self.resolve_end) / max(1, self.turns)

    @property
    def marched(self) -> int | None:
        """Turns spent getting there — the cost GW-WP23's drop standoff exists to cut."""
        return self.breach_turn if self.breach_turn is not None else None


def run_scenario(scenario: Scenario, config: GameConfig) -> Row:
    """Fight one scenario to its decision, headless, recording how it got there."""
    state = build_state(scenario, config)
    service = GameService(state, config, SqliteRepository(":memory:"))
    # The recording runner, not a bare `BotRunner`: contact is read off the commands the
    # bot actually issued, and it is also the exact runner the watched pilot drives — so
    # a row in this table and a run on the screen come from one code path.
    bot = RecordingRunner(service, harness.PLAYER_ID)
    assaulter.setup(bot)

    contact_turn: int | None = None
    breach_turn: int | None = None
    casualties_at_breach: int | None = None
    resolve_start: int | None = None
    last: AssaultOperation | None = None

    for _ in range(_MAX_STEPS):
        if bot.stopped:
            break
        bot.step()
        commands, _events, _rejections = bot.take()
        op = service.state.players[harness.PLAYER_ID].ground_operation
        if not isinstance(op, AssaultOperation):
            break
        last = op
        if resolve_start is None:
            resolve_start = op.resolve
        if not op.dropped:
            continue
        amap = assault_map_for(service.state, op, config)
        capital = next((c for c in amap.cities if c.is_citadel), amap.cities[0])
        if breach_turn is None and any(
                t.hp > 0 and capital.inside(t.x, t.y) for t in op.platoon):
            breach_turn = op.local_turn
            casualties_at_breach = op.casualties
        # A fired shot is the cheapest honest marker of contact: it means something was in
        # range *and* in line of sight, which no distance threshold can tell.
        if contact_turn is None and any(isinstance(c, GroundFire) for c in commands):
            contact_turn = op.local_turn
        if op.outcome is not None:
            break

    assert last is not None, "scenario produced no operation"
    return Row(
        scenario=scenario,
        outcome=last.outcome or "unresolved",
        turns=last.local_turn,
        retrieval_turn=last.retrieval_turn,
        contact_turn=contact_turn,
        breach_turn=breach_turn,
        resolve_start=resolve_start if resolve_start is not None else last.resolve,
        resolve_end=last.resolve,
        strength=last.initial_strength,
        casualties=last.casualties,
        casualties_at_breach=casualties_at_breach,
    )


def _fmt(value: int | None) -> str:
    return "—" if value is None else str(value)


def render(rows: list[Row]) -> str:
    """The table, plus the two aggregate lines worth reading before any single row."""
    head = (f"{'seed':>5} {'world':<22} {'cit':>3} {'outcome':<11} {'turn':>5} "
            f"{'contact':>7} {'breach':>6} {'resolve':>9} {'Δ/turn':>7} "
            f"{'cas@breach':>10} {'cas':>5}")
    out = [head, "-" * len(head)]
    for r in rows:
        s = r.scenario
        world = (f"cloud city {s.cloud_city_size}" if s.is_cloud_city
                 else s.planet_type)
        out.append(
            f"{s.seed:>5} {world:<22} {s.citadel_level:>3} {r.outcome:<11} "
            f"{r.turns:>2}/{r.retrieval_turn:<2} {_fmt(r.contact_turn):>7} "
            f"{_fmt(r.breach_turn):>6} {r.resolve_start:>4}→{r.resolve_end:<4} "
            f"{r.resolve_per_turn:>7.2f} {_fmt(r.casualties_at_breach):>10} "
            f"{r.casualties:>2}/{r.strength:<2}")

    breached = [r for r in rows if r.breach_turn is not None]
    out.append("")
    out.append(f"breached {len(breached)}/{len(rows)} runs"
               + (f", median breach turn {statistics.median(r.breach_turn for r in breached  # type: ignore[misc]
                                                            ):.0f}" if breached else ""))
    outcomes = sorted({r.outcome for r in rows})
    out.append("outcomes: " + ", ".join(
        f"{o}×{sum(1 for r in rows if r.outcome == o)}" for o in outcomes))
    if len(outcomes) == 1 and not breached:
        out.append("")
        out.append("WARNING: one outcome, no breaches — this table is measuring the bot, "
                   "not the balance. Watch a run before reading anything into it.")
    return "\n".join(out)


def _int_list(raw: str) -> list[int]:
    return [int(part) for part in raw.split(",") if part.strip()]


def _squad(raw: str) -> dict[str, int]:
    """`marauder=4,scout=3,command=1` — the platoon a run lands with.

    Force size is a balance axis in its own right (a couple of marauders should be able
    to take a world, but only on a slim chance; a full platoon should be favoured), and
    it cannot be read off a fixed-squad matrix at all. Overrides `groundwar.bot.squad`
    for the run so the whole scaling curve is measurable from one command.
    """
    out: dict[str, int] = {}
    for part in raw.split(","):
        if not part.strip():
            continue
        name, _, count = part.partition("=")
        out[name.strip()] = int(count)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument("--seeds", default="1,2,3,4", type=_int_list)
    parser.add_argument("--citadel", default="0,2", type=_int_list)
    parser.add_argument("--planet-type", default="terrestrial_warm")
    parser.add_argument("--habitability-cap", default=8_000, type=int)
    parser.add_argument("--cloud-city", default=0, type=int,
                        help="station size; > 0 runs the Cloud City branch instead")
    parser.add_argument("--squad", default=None, type=_squad,
                        help="platoon to land, e.g. marauder=2 or marauder=4,scout=3,command=1")
    args = parser.parse_args(argv)

    config = load_default_config()
    if args.squad is not None:
        assert config.groundwar is not None
        config = config.model_copy(update={"groundwar": config.groundwar.model_copy(
            update={"bot": config.groundwar.bot.model_copy(update={"squad": args.squad})})})
    rows = [
        run_scenario(
            Scenario(
                seed=seed, planet_type=args.planet_type,
                habitability_cap=args.habitability_cap, citadel_level=citadel,
                cloud_city_size=args.cloud_city,
                # The harness stocks the ship from the scenario, while the bot picks what
                # to land from config — both must hear the same squad or the run measures
                # a platoon nobody asked for.
                **({"loadout": tuple(args.squad.items())} if args.squad else {})),
            config)
        for seed in args.seeds
        for citadel in args.citadel
    ]
    print(render(rows))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
