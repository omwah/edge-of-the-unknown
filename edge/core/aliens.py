"""Alien disposition logic (DESIGN §6) — pure core, no I/O.

Disposition is a continuous 0.0 (most hostile) → 1.0 (most friendly) scale, not a
binary flag (CLAUDE.md). A species' authored `base_disposition` is the *base* stance;
the player's per-species **attitude offset** (raised by trade/favours, lowered by
aggression in Phase 3) shifts it into the **effective disposition** that drives
greeting-vs-violence, prices/barter, and tech unlocks. Config thresholds name the
bands (default hostility 0.35 / amity 0.65, §6).
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.config import AliensConfig, AllianceConfig, RosterConfig, SpeciesConfig
from edge.core.models import AlienSpecies, Grudge, Player, UniverseState

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
    config: AliensConfig, day: int, kills: int,
) -> Player:
    """Apply the consequences of destroying `kills` of a species' ships (§6.5, WP27).

    Per kill the attitude offset drops by the species' `attitude_loss_rate` and the
    grudge it holds against the player deepens by `grudge_severity_per_kill` (capped
    at 1.0). A `memory_model: none` species forgets instantly — no souring, no
    grudge. A `never_forgets` or `betrayal_model: permanent` species records the
    grudge as undying (`duration_days -1`), which also locks the offset (§6.5).
    Pure — the caller (a reducer or test) owns event emission.
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
        cause=f"destroyed {species.name} ships",
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
