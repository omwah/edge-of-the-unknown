"""Alien disposition logic (DESIGN §6) — pure core, no I/O.

Disposition is a continuous 0.0 (most hostile) → 1.0 (most friendly) scale, not a
binary flag (CLAUDE.md). A species' authored `base_disposition` is the *base* stance;
the player's per-species **attitude offset** (raised by trade/favours, lowered by
aggression in Phase 3) shifts it into the **effective disposition** that drives
greeting-vs-violence, prices/barter, and tech unlocks. Config thresholds name the
bands (default hostility 0.35 / amity 0.65, §6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from edge.core.config import (
    AliensConfig, AllianceConfig, RosterConfig, SeizureConfig, SpeciesConfig,
)
from edge.core import corp
from edge.core.models import AlienSpecies, Grudge, Ownership, Player, Starbase, UniverseState

HOSTILE = "hostile"
NEUTRAL = "neutral"
FRIENDLY = "friendly"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def attitude_offset(species: AlienSpecies, player: Player) -> float:
    """The player's accumulated attitude offset toward `species` (0.0 if none yet).

    Keyed by `roster_id` (the species kind), so every ship of a species reads the same
    standing — dealing with one Vesk vessel shifts the player's stance with all Vesk.
    """
    return player.species_attitudes.get(species.roster_id, 0.0)


def effective_disposition(species: AlienSpecies, player: Player) -> float:
    """Base disposition shifted by the player's attitude offset, clamped to [0, 1] (§6)."""
    return _clamp01(species.base_disposition + attitude_offset(species, player))


def grudge_shift(species: AlienSpecies, player: Player) -> float:
    """The active-grudge penalty this species applies to the player (§6.5, §10).

    The severity of the vendetta the species kind holds against the player, or 0.0 —
    subtracted from effective disposition before the greeting-vs-violence roll, so a
    wronged species is primed to attack even while its base stance is mild.
    """
    grudge = player.grudges.get(species.roster_id)
    return grudge.severity if grudge is not None else 0.0


def attitude_locked(player: Player, roster_id: str) -> bool:
    """Whether a permanent grudge locks the attitude offset for good (§6.5).

    A `never_forgets` / `betrayal_model=permanent` species' grudge (duration -1)
    floors the offset where the betrayal left it: amends no longer raise it.
    """
    grudge = player.grudges.get(roster_id)
    return grudge is not None and grudge.duration_days < 0


def sour_attitude(
    player: Player, species: AlienSpecies, sc: SpeciesConfig,
    config: AliensConfig, day: int, kills: int, *, cause: str | None = None,
) -> Player:
    """Apply the consequences of destroying `kills` of a species' ships (§6.5, WP27).

    Per kill the attitude offset drops by the species' `attitude_loss_rate` and the
    grudge it holds against the player deepens by `grudge_severity_per_kill` (capped
    at 1.0). A `memory_model: none` species forgets instantly — no souring, no
    grudge. A `never_forgets` or `betrayal_model: permanent` species records the
    grudge as undying (`duration_days -1`), which also locks the offset (§6.5).
    `cause` overrides the recorded grudge cause (a first strike sours like one kill
    but is remembered differently, §10 WP70). Pure — the caller owns event emission.
    """
    if kills <= 0 or sc.memory_model == "none":
        return player
    offset = player.species_attitudes.get(species.roster_id, 0.0)
    new_offset = max(-1.0, offset - sc.attitude_loss_rate * kills)
    permanent = sc.memory_model == "never_forgets" or sc.betrayal_model == "permanent"
    existing = player.grudges.get(species.roster_id)
    severity = min(1.0, (existing.severity if existing is not None else 0.0)
                   + config.grudge_severity_per_kill * kills)
    grudge = Grudge(
        holder=species.roster_id, target="player",
        cause=cause if cause is not None else f"destroyed {species.name} ships",
        severity=round(severity, 6),
        created_day=existing.created_day if existing is not None else day,
        duration_days=-1 if permanent else config.grudge_duration_days,
    )
    return replace(
        player,
        species_attitudes={**player.species_attitudes, species.roster_id: round(new_offset, 6)},
        grudges={**player.grudges, species.roster_id: grudge},
    )


def decay_grudges(player: Player, gain_rates: dict[str, float],
                  config: AliensConfig, day: int) -> Player:
    """One daily tick of grudge cooling (§6.5) — pure, deterministic, cron-called.

    A finite grudge loses its holder's `attitude_gain_rate` of severity per day (the
    species lets it go as the player makes amends) and expires when drained or past
    its `duration_days`. Permanent grudges (duration -1) never decay.
    """
    if not player.grudges:
        return player
    kept: dict[str, Grudge] = {}
    for roster_id, grudge in player.grudges.items():
        if grudge.duration_days < 0:
            kept[roster_id] = grudge
            continue
        severity = round(grudge.severity - gain_rates.get(roster_id, 0.1), 6)
        if severity <= 0.0 or day > grudge.created_day + grudge.duration_days:
            continue  # forgiven or lapsed
        kept[roster_id] = replace(grudge, severity=severity)
    if kept == dict(player.grudges):
        return player
    return replace(player, grudges=kept)


def is_criminal(player: Player, config: AliensConfig) -> bool:
    """Whether the player's alignment marks them criminal in the governor's eyes (§10).

    WP27 ships the flag and an entry notice; full Core-law enforcement is WP38.
    """
    return player.alignment < config.criminal_alignment


def disposition_band(value: float, config: AliensConfig) -> str:
    """Name the band a disposition value falls in (hostile / neutral / friendly, §6)."""
    if value < config.hostility_threshold:
        return HOSTILE
    if value >= config.amity_threshold:
        return FRIENDLY
    return NEUTRAL


def is_friendly(value: float, config: AliensConfig) -> bool:
    """Whether a disposition value sits in the friendly (amity) band."""
    return value >= config.amity_threshold


# --- Inter-species relations & spillover (DESIGN §6.4, WP39) ----------------


def species_relation(
    roster: RosterConfig, a_id: str, b_id: str, config: AliensConfig
) -> float:
    """`a`'s stance toward `b` on a −1..1 scale (§6.4) — asymmetric, alliance-derived.

    A species' own kind is 1.0. An explicit roster `relations` override on `a` wins
    (clamped, one-directional). Otherwise the default is alliance-derived: bloc-mates
    warm to `relation_ally_default`, members of a (symmetric) rival bloc chill to
    `relation_rival_default`, everyone else is neutral (0.0).
    """
    if a_id == b_id:
        return 1.0
    a = roster.species_by_id(a_id)
    if a is None:
        return 0.0
    if b_id in a.relations:
        return max(-1.0, min(1.0, a.relations[b_id]))
    b = roster.species_by_id(b_id)
    if a.alliance_id is None or b is None or b.alliance_id is None:
        return 0.0
    if a.alliance_id == b.alliance_id:
        return config.relation_ally_default
    if b.alliance_id in _rivals_of(roster, a.alliance_id):
        return config.relation_rival_default
    return 0.0


def apply_spillover(
    player: Player, subject_id: str, delta: float,
    roster: RosterConfig, config: AliensConfig,
) -> Mapping[str, float]:
    """Reputation spillover from a `delta` attitude change toward `subject_id` (§6.4).

    Returns the new `species_attitudes` map: each species Y with a strong-enough
    relation from the subject is nudged by `delta × spillover_fraction × relation(subject→Y)`
    — helping the subject warms its friends and chills its enemies (and harming does the
    reverse). The subject itself is untouched (its own change is applied by the caller),
    and a species under a permanent grudge lock is skipped (§6.5). Pure.
    """
    if delta == 0.0:
        return player.species_attitudes
    attitudes = dict(player.species_attitudes)
    for other in roster.species:
        if other.id == subject_id or attitude_locked(player, other.id):
            continue
        rel = species_relation(roster, subject_id, other.id, config)
        if abs(rel) < config.spillover_threshold:
            continue
        nudged = attitudes.get(other.id, 0.0) + delta * config.spillover_fraction * rel
        attitudes[other.id] = round(max(-1.0, min(1.0, nudged)), 6)
    return attitudes


def npc_stance(
    state: UniverseState, roster: RosterConfig, a_id: str, b_id: str, config: AliensConfig
) -> float:
    """`a`'s live stance toward `b` (§6.4) — the relation matrix minus any active grudge.

    The seeded inter-species grudges (`UniverseState.grudges`, WP27) deepen enmity beyond
    the static relation: an active grudge `a`-holds-against-`b` subtracts its severity.
    Consumed by NPC-vs-NPC movement/behaviour policies (WP42) and same-sector conduct.
    """
    stance = species_relation(roster, a_id, b_id, config)
    for grudge in state.grudges.values():
        if grudge.holder == a_id and grudge.target == b_id:
            stance -= grudge.severity
    return max(-1.0, min(1.0, stance))


# --- Alliances (DESIGN §6.3, WP38) ------------------------------------------

# Reserved `species_arcs` key namespace for a bloc's admission-task ledger. The `@`
# prefix can never collide with a roster_id (lowercase identifiers), so the befriend-
# price ledger rides `species_arcs` without a second hashed field (H6 golden batch).
ALLIANCE_ARC_PREFIX = "@alliance:"


def _alliance_key(alliance_id: int) -> str:
    return f"{ALLIANCE_ARC_PREFIX}{alliance_id}"


def admission_tasks_done(player: Player, alliance_id: int) -> frozenset[str]:
    """The admission tasks the player has completed for a bloc (the §6.3 ledger)."""
    ledger = player.species_arcs.get(_alliance_key(alliance_id), {})
    return frozenset(str(task) for task, done in ledger.items() if done)


def record_admission_task(player: Player, alliance_id: int, task: str) -> Player:
    """Mark one admission task complete in the bloc's ledger (pure; WP38)."""
    key = _alliance_key(alliance_id)
    ledger = {**player.species_arcs.get(key, {}), task: True}
    return replace(player, species_arcs={**player.species_arcs, key: ledger})


def admission_met(player: Player, alliance: AllianceConfig) -> bool:
    """Whether the player has completed the bloc's `admission_price` tasks (§6.3)."""
    return set(alliance.admission_price) <= admission_tasks_done(player, alliance.id)


# Reserved `species_arcs` key namespace for a bloc's *Core-seizure* task ledger (WP50) —
# a second `@`-prefixed key so seizure progress never collides with the admission ledger
# (or a roster_id), riding `species_arcs` without another hashed field (H6).
SEIZURE_ARC_PREFIX = "@seizure:"


def _seizure_key(alliance_id: int) -> str:
    return f"{SEIZURE_ARC_PREFIX}{alliance_id}"


def seizure_tasks_done(player: Player, alliance_id: int) -> frozenset[str]:
    """The Core-seizure tasks the player has completed for a bloc (the §6.3 ledger, WP50)."""
    ledger = player.species_arcs.get(_seizure_key(alliance_id), {})
    return frozenset(str(task) for task, done in ledger.items() if done)


def record_seizure_task(player: Player, alliance_id: int, task: str) -> Player:
    """Mark one Core-seizure task complete in the bloc's seizure ledger (pure; WP50)."""
    key = _seizure_key(alliance_id)
    ledger = {**player.species_arcs.get(key, {}), task: True}
    return replace(player, species_arcs={**player.species_arcs, key: ledger})


def core_bases_razed(state: UniverseState, governor_id: int | None) -> int:
    """How many Core-planet starbases are no longer the incumbent governor's (§4.2, WP50).

    A Core base starts owned by the governing alliance and intact; razing it drops it to
    unowned (`_raze_starbase`), and even a subsequent player claim leaves it not-the-
    governor's. So a Core-sector base whose owner is not the current governor counts as
    razed — the seizure's raze tally, derived from state rather than double-booked.
    """
    count = 0
    for base in state.starbases.values():
        if not state.sectors[base.sector_id].is_galactic_core:
            continue
        if not (base.owner.kind == "alliance" and base.owner.ref == governor_id):
            count += 1
    return count


@dataclass(frozen=True, slots=True)
class SeizureProgress:
    """The player's progress toward championing a bloc into the Core (§6.3, WP50).

    Computed once from state and read by *both* the petition reducer (which raises a
    precise reason per unmet gate) and the projection (which renders the checklist), so
    view and reducer stay in lockstep (H4). `ready` is the conjunction the reducer applies.
    """

    alliance_id: int
    is_member: bool
    already_governs: bool
    consented: bool  # standing with the bloc is non-negative (member in good standing)
    tasks_done: frozenset[str]
    tasks_required: tuple[str, ...]
    bases_razed: int
    bases_required: int
    fee: int
    fee_affordable: bool

    @property
    def tasks_met(self) -> bool:
        return set(self.tasks_required) <= self.tasks_done

    @property
    def bases_met(self) -> bool:
        return self.bases_razed >= self.bases_required

    @property
    def ready(self) -> bool:
        return (self.is_member and not self.already_governs and self.consented
                and self.tasks_met and self.bases_met and self.fee_affordable)


def seizure_progress(
    state: UniverseState, player: Player, alliance: AllianceConfig, seizure: SeizureConfig,
) -> SeizureProgress:
    """Assemble the player's `SeizureProgress` against a bloc's ladder (pure; WP50)."""
    gov = state.game.core_governing_alliance_id
    return SeizureProgress(
        alliance_id=alliance.id,
        is_member=player.alliance_id == alliance.id,
        already_governs=gov == alliance.id,
        consented=alliance_standing(player, alliance.id) >= 0.0,
        tasks_done=seizure_tasks_done(player, alliance.id),
        tasks_required=tuple(seizure.price),
        bases_razed=core_bases_razed(state, gov),
        bases_required=seizure.bases_to_raze,
        fee=seizure.fee,
        fee_affordable=player.latinum >= seizure.fee,
    )


def alliance_rivals(roster: RosterConfig | None, alliance_id: int) -> set[int]:
    """Public: the blocs at odds with `alliance_id` (symmetric rivalry, §6.3).

    Thin wrapper over `_rivals_of` for callers outside `aliens` (e.g. territory
    entry-defense, WP-PR02). An absent roster yields no rivals.
    """
    if roster is None:
        return set()
    return _rivals_of(roster, alliance_id)


def _rivals_of(roster: RosterConfig, alliance_id: int) -> set[int]:
    """The blocs at odds with `alliance_id` — rivalry is symmetric (§6.3)."""
    joined = roster.alliance(alliance_id)
    rivals = set(joined.rivals) if joined is not None else set()
    for a in roster.alliances:
        if alliance_id in a.rivals:
            rivals.add(a.id)
    rivals.discard(alliance_id)
    return rivals


def apply_join_standing(player: Player, roster: RosterConfig, alliance_id: int) -> Player:
    """Set standing for joining `alliance_id`: +1 the bloc, −1 its rivals (§6.3, WP38).

    Membership is exclusive, so the joined bloc becomes the player's `alliance_id`;
    every other bloc's standing is left as-is unless it is a (symmetric) rival, which
    sours to −1. Pure — the caller charges the fee and emits the event.
    """
    standing = dict(player.alliance_standing)
    standing[alliance_id] = 1.0
    for rival in _rivals_of(roster, alliance_id):
        standing[rival] = -1.0
    return replace(player, alliance_id=alliance_id, alliance_standing=standing)


def apply_resign_standing(player: Player) -> Player:
    """Leave the current bloc and let rival hostility lapse to neutral (§6.3, WP38).

    Resignation is the amends path: standing resets so the Core governor's sanctuary
    (and any soured bloc) recovers. Gradual re-warming via missions is a later seam.
    """
    return replace(player, alliance_id=None, alliance_standing={})


def alliance_standing(player: Player, alliance_id: int | None) -> float:
    """The player's standing with a bloc (0.0 if none), (§6.3)."""
    if alliance_id is None:
        return 0.0
    return player.alliance_standing.get(alliance_id, 0.0)


def alliance_standing_shift(player: Player, species: AlienSpecies) -> float:
    """The greeting-vs-violence penalty from ill standing with a species' bloc (§6.3).

    Negative standing with the species' alliance is subtracted from effective
    disposition before the §10 violence roll (like `grudge_shift`), so a rival bloc's
    members are primed to attack a player aligned against them. 0.0 for an unaligned
    species or non-negative standing.
    """
    standing = alliance_standing(player, species.alliance_id)
    return -standing if standing < 0.0 else 0.0


def governor_hostile(state: UniverseState, player: Player) -> bool:
    """Whether the Core governor treats the player as an enemy (§6.3, WP38).

    True when the player is *not* a governing member and holds negative standing with
    the governing bloc — the case that makes the Core unsafe (engaged on sight).
    """
    gov = state.game.core_governing_alliance_id
    if gov is None or player.alliance_id == gov:
        return False
    return alliance_standing(player, gov) < 0.0


def core_status(state: UniverseState, player: Player) -> str:
    """The player's standing *in the Core* under the current governor (§6.3, WP52).

    A positional label the game screen surfaces so a governance flip is legible:
    ``"safe"`` when the player governs or belongs to the governing bloc (or the Core
    is ungoverned); ``"hunted"`` when `governor_hostile` (a non-member at negative
    standing — engaged on sight, denied the haven); ``"unwelcome"`` for the middle
    case (a non-member at neutral/positive standing — tolerated but not home). Pure,
    derived from the same live fields the reducers key off, so it can never disagree
    with them.
    """
    gov = state.game.core_governing_alliance_id
    if gov is None or player.alliance_id == gov:
        return "safe"
    return "hunted" if alliance_standing(player, gov) < 0.0 else "unwelcome"


def owner_hostile(state: UniverseState, owner: Ownership, player: Player) -> bool:
    """Whether a holding's owner treats the player as an enemy (§4.2, WP40/WP54).

    The shared owner-hostility rule behind base and citadel-gun defense: an
    alliance-owned holding engages a player who is hostile to that bloc (the Core
    governor via `governor_hostile`; any other bloc at negative standing). Unowned and
    player-owned holdings never engage the player.
    """
    if owner.kind == "alliance" and owner.ref is not None:
        if owner.ref == state.game.core_governing_alliance_id:
            return governor_hostile(state, player)
        return alliance_standing(player, owner.ref) < 0.0
    if owner.kind == "corp":  # a corp holding engages a rival-corp player (corp war, WP66)
        return corp.owner_at_war_with_player(state, owner, player)
    return False


def base_owner_hostile(state: UniverseState, base: Starbase, player: Player) -> bool:
    """Whether an operational base's owner treats the player as an enemy (§4.2, WP40).

    A base defends its planetary system against entrants hostile to its owner. Delegates
    to `owner_hostile` (the same rule the citadel gun uses, WP54).
    """
    return owner_hostile(state, base.owner, player)


def may_occupy(
    state: UniverseState, species: AlienSpecies, sector_id: int, config: AliensConfig
) -> bool:
    """Whether `species` is allowed to sit in `sector_id` (Phase-2 alliance rules, WP16).

    The Core Space admits only the governing alliance's own members — it is their
    capital (WP18); every other species is barred. A sector holding a **rival**
    alliance's planet (owned by an alliance other than the species') is off-limits;
    empty/neutral sectors and the species' own holdings are fine. Pure and
    side-effect-free, so the cron and tests share it. Phase 3 widens the rival check
    from "different alliance" to "at war with / holds a grudge" (§6.4).
    """
    sector = state.sectors[sector_id]
    if sector.is_galactic_core:
        # The governor's members may inhabit/roam their capital; all others are barred.
        return species.alliance_id == state.game.core_governing_alliance_id
    for planet in state.planets.values():
        if planet.sector_id != sector_id:
            continue
        owner = planet.owner
        if owner.kind == "alliance" and owner.ref != species.alliance_id:
            return False  # a rival bloc's holding is off-limits
    return True
