"""Favors + escort contracts (DESIGN §6.7, §14 — WP57) — pure, deterministic.

Aliens ask the player for jobs and pay for them done. This module owns the *choosing*
and *bookkeeping* of that; the reducers in `core.rules` own the acceptance, delivery,
and combat/movement completion hooks that drive it, and the daily cron owns deadline
expiry. Everything here is a pure function over `UniverseState` with no I/O and no RNG
of its own (`pick_contract` is fully deterministic, so the read-only contact projection
and the accept reducer agree on the exact job — the §6.7 view/reducer lockstep, H4):

- `pick_contract` — at contact time, the single best favor a friendly speaker can offer
  this player, mirroring `dialogue.intel.pick_intel_target`: disposition-gated, targets
  drawn from live state (a port its own book shows short ⇒ deliver; a grudge target ⇒
  destroy, the §6.5 `demand` finally cashable; a bloc merchant en route ⇒ escort).
- completion helpers the reducers call: `complete_destroy_on_kill` /
  `complete_destroy_on_raze` check active destroy jobs at the same hook points as
  bounties (WP44); `advance_convoy` relocates an escorted merchant alongside the player's
  warps and completes on arrival (interview decision 9); `expire_deadlines` fails lapsed
  jobs on the daily clock (next to grudge decay, §6.5).
- `apply_reward` pays a completed job through the existing latinum + attitude rails, so a
  contract is a bounded faucet/lever, never a new economy.

Invariants (DESIGN §13): contract selection is deterministic; rewards conserve (slips are
minted like a bounty, attitude is capped so effective disposition never exceeds 1); a
convoyed merchant is a pure predicate off `Player.contracts`, so replay reconstructs the
convoy exactly.
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.aliens import (
    attitude_locked,
    effective_disposition,
    is_friendly,
)
from edge.core.config import ContractsConfig, GameConfig
from edge.core.enums import Commodity, PortMode
from edge.core.models import AlienSpecies, Contract, Player, UniverseState

# The commodity iteration order used everywhere a deliver target is chosen (canonical, so
# selection is order-independent — the H10 determinism discipline reused for contracts).
_COMMODITIES = (Commodity.FUEL_ORE, Commodity.ORGANICS, Commodity.EQUIPMENT)


# --- offer selection -------------------------------------------------------------


def _speaker_offers(player: Player, speaker: AlienSpecies, config: GameConfig) -> bool:
    """Whether `speaker` will offer this player a favor at all (friendly/allied standing)."""
    if not config.aliens.contracts.enabled:
        return False
    sc = config.roster.species_by_id(speaker.roster_id) if config.roster is not None else None
    if sc is None or sc.contract_posture == "none":
        return False
    allied = player.alliance_id is not None and player.alliance_id == speaker.alliance_id
    return allied or is_friendly(effective_disposition(speaker, player), config.aliens)


def _has_open(player: Player, kind: str) -> bool:
    """An active job of `kind` is already on the player's slate (never double-book a kind)."""
    return any(c.kind == kind and c.status == "active" for c in player.contracts)


def _deliver_target(state: UniverseState) -> tuple[Commodity, int] | None:
    """The commodity a port most wants bought in (largest standing BUY order), or None (§8).

    Drawn from the live order book (WP47): the port that is shortest on a good posts the
    biggest BUY, so the deliver job routes the player toward a real market gap. Deterministic
    — ties break by commodity enum order then port id.
    """
    best: tuple[int, int, int] | None = None  # (qty, -commodity_index, -port_id) sort key
    chosen: Commodity | None = None
    for port_id in sorted(state.port_orders):
        for order in state.port_orders[port_id]:
            if order.side != "buy":
                continue
            idx = _COMMODITIES.index(order.commodity)
            key = (order.qty, -idx, -port_id)
            if best is None or key > best:
                best, chosen = key, order.commodity
    if chosen is None:
        return None
    return chosen, best[0] if best is not None else 0


def _port_sector_for(state: UniverseState, commodity: Commodity) -> int | None:
    """A sector holding a port that BUYs `commodity` — the deliver destination (deterministic)."""
    for port in sorted(state.ports.values(), key=lambda p: p.id):
        line = port.line(commodity)
        if line is not None and line.mode is PortMode.BUY:
            return port.sector_id
    return None


def _destroy_target(state: UniverseState, speaker: AlienSpecies) -> AlienSpecies | None:
    """A live species instance the speaker's kind holds a grudge against (§6.5), or None.

    The §6.5 `demand` cashed: the speaker asks the player to settle a score it will not.
    Deterministic — the lowest-id matching instance of the most-grudged kind.
    """
    grudged: set[str] = {
        g.target for g in state.grudges.values()
        if g.holder == speaker.roster_id and g.target != "player"
    }
    if not grudged:
        return None
    candidates = [sp for sp in state.species.values()
                  if sp.roster_id in grudged and sp.id != speaker.id]
    if not candidates:
        return None
    return min(candidates, key=lambda sp: sp.id)


def _escort_target(state: UniverseState, speaker: AlienSpecies,
                   config: GameConfig) -> tuple[AlienSpecies, int] | None:
    """A bloc merchant + destination port sector for an escort job, or None (interview 9).

    The merchant is a `trade_seek` instance of the speaker's bloc, not the speaker itself
    and not StarDock-pinned; the destination is a port sector other than the merchant's.
    Deterministic — lowest-id merchant, lowest-id eligible destination port.
    """
    if config.roster is None:
        return None
    dock_sectors = _dock_sectors(state)
    merchants = [
        sp for sp in state.species.values()
        if sp.id != speaker.id and sp.alliance_id == speaker.alliance_id
        and sp.sector_id not in dock_sectors
        and _movement_policy(config, sp) == "trade_seek"
    ]
    if not merchants:
        return None
    merchant = min(merchants, key=lambda sp: sp.id)
    dest = next(
        (p.sector_id for p in sorted(state.ports.values(), key=lambda p: p.id)
         if p.sector_id != merchant.sector_id),
        None,
    )
    if dest is None:
        return None
    return merchant, dest


def _dock_sectors(state: UniverseState) -> frozenset[int]:
    from edge.core.enums import PortClass
    return frozenset(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)


def _movement_policy(config: GameConfig, sp: AlienSpecies) -> str:
    sc = config.roster.species_by_id(sp.roster_id) if config.roster is not None else None
    return sc.movement_policy if sc is not None else "wander"


def pick_contract(state: UniverseState, speaker: AlienSpecies, player: Player,
                  config: GameConfig) -> Contract | None:
    """The single best favor `speaker` can offer `player`, or None (DESIGN §6.7, WP57).

    Disposition-gated like `pick_intel_target`; the kind is chosen by the speaker's
    `contract_posture` against what the live world affords, in a fixed priority (deliver →
    destroy → escort) so the offer is deterministic. An open job of the same kind suppresses
    a fresh one, so a slate never stacks duplicates. The returned contract carries
    `status="offered"` and an empty deadline — the accept reducer stamps `accepted_day` and
    the real `deadline_day` when the player takes it.
    """
    if not _speaker_offers(player, speaker, config):
        return None
    cc = config.aliens.contracts
    posture = (config.roster.species_by_id(speaker.roster_id).contract_posture
               if config.roster is not None else "any")
    allow = {posture} if posture != "any" else {"deliver", "destroy", "escort"}

    if "deliver" in allow and not _has_open(player, "deliver"):
        target = _deliver_target(state)
        if target is not None:
            commodity, _ = target
            dest = _port_sector_for(state, commodity)
            if dest is not None:
                return _offer(speaker, "deliver", cc,
                              reward=cc.deliver_reward_per_unit * cc.deliver_qty,
                              commodity=commodity, qty=cc.deliver_qty, dest_sector=dest)

    if "destroy" in allow and not _has_open(player, "destroy"):
        foe = _destroy_target(state, speaker)
        if foe is not None:
            return _offer(speaker, "destroy", cc, reward=cc.destroy_reward,
                          target_species_id=foe.id, dest_sector=foe.sector_id)

    if "escort" in allow and not _has_open(player, "escort"):
        escort = _escort_target(state, speaker, config)
        if escort is not None:
            merchant, dest = escort
            return _offer(speaker, "escort", cc, reward=cc.escort_reward,
                          target_species_id=merchant.id, dest_sector=dest)
    return None


def _offer(speaker: AlienSpecies, kind: str, cc: ContractsConfig, *, reward: int,
           **target: object) -> Contract:
    """Build an `offered` contract shell (accept stamps the day/deadline)."""
    return Contract(
        id=0, kind=kind, issuer=speaker.roster_id, reward_slips=reward,
        reward_attitude=cc.attitude_reward, accepted_day=0, deadline_day=0,
        status="offered", **target,  # type: ignore[arg-type]
    )


def accept(player: Player, offer: Contract, day: int, config: GameConfig) -> Contract:
    """Stamp an offered contract into an active one on the player's slate (WP57)."""
    next_id = max((c.id for c in player.contracts), default=0) + 1
    return replace(offer, id=next_id, status="active", accepted_day=day,
                   deadline_day=day + config.aliens.contracts.deadline_days)


# --- dialogue bindings (shared by the reducer and the read-only projection) ------


def target_label(state: UniverseState, contract: Contract) -> str:
    """A short human label for a contract's target, spoken in the offer line (§6.7, WP57)."""
    where = (str(state.spatial_ids.get(contract.dest_sector, contract.dest_sector))
             if contract.dest_sector is not None else "?")
    if contract.kind == "deliver" and contract.commodity is not None:
        return f"{contract.qty} {contract.commodity.value.replace('_', ' ')} to sector {where}"
    if contract.kind == "destroy":
        foe = (state.species.get(contract.target_species_id)
               if contract.target_species_id is not None else None)
        return foe.name if foe is not None else "a marked foe"
    if contract.kind == "escort":
        merchant = (state.species.get(contract.target_species_id)
                    if contract.target_species_id is not None else None)
        name = merchant.name if merchant is not None else "our merchant"
        return f"{name} to sector {where}"
    return "the job"


def offer_bindings(state: UniverseState, contract: Contract,
                   config: GameConfig) -> dict[str, str]:
    """The `{target}`/`{reward}`/`{deadline}`/`{count}` fills describing a job (§6.7, WP57)."""
    return {
        "target": target_label(state, contract),
        "reward": f"{contract.reward_slips} slips",
        "deadline": str(config.aliens.contracts.deadline_days),
        "count": str(contract.qty),
    }


# --- rewards & bookkeeping -------------------------------------------------------


def apply_reward(player: Player, contract: Contract, state: UniverseState) -> Player:
    """Pay a completed contract: latinum faucet + capped attitude warmth toward the issuer.

    Slips are minted like a kill bounty (a bounded faucet, §8); the attitude offset toward
    the issuer kind rises by `reward_attitude`, capped so effective disposition never
    exceeds 1 (the `_trader_rapport`/tech-sale cap) and never moved while a permanent grudge
    locks it (§6.5). Pure — the caller folds the returned player into its `ReduceResult`.
    """
    new_player = replace(player, latinum=player.latinum + contract.reward_slips)
    issuer = next((sp for sp in state.species.values() if sp.roster_id == contract.issuer), None)
    if issuer is None or contract.reward_attitude <= 0 or attitude_locked(new_player, contract.issuer):
        return new_player
    cap = max(0.0, 1.0 - issuer.base_disposition)
    current = new_player.species_attitudes.get(contract.issuer, 0.0)
    new_offset = round(min(cap, current + contract.reward_attitude), 6)
    if new_offset <= current:
        return new_player
    return replace(new_player,
                   species_attitudes={**new_player.species_attitudes, contract.issuer: new_offset})


def set_status(player: Player, contract_id: int, status: str) -> Player:
    """Return the player with contract `contract_id` moved to `status` (done/failed)."""
    return replace(player, contracts=tuple(
        replace(c, status=status) if c.id == contract_id else c for c in player.contracts))


def active(player: Player, kind: str | None = None) -> list[Contract]:
    """The player's active contracts, optionally filtered to one `kind`."""
    return [c for c in player.contracts
            if c.status == "active" and (kind is None or c.kind == kind)]


def by_id(player: Player, contract_id: int) -> Contract | None:
    return next((c for c in player.contracts if c.id == contract_id), None)


# --- destroy completion (combat / raze hooks) ------------------------------------


def complete_destroy_on_kill(player: Player, species: AlienSpecies) -> tuple[Player, list[Contract]]:
    """Mark done any active destroy job targeting the killed species instance (WP57).

    Called from the combat reducer at the same point kill bounties are paid (WP44). Returns
    the updated player (statuses flipped) and the list of newly-completed contracts so the
    caller can pay rewards + emit events. Rewards are *not* applied here (the caller owns the
    single latinum mutation), keeping this pure and composable.
    """
    done = [c for c in active(player, "destroy") if c.target_species_id == species.id]
    new_player = player
    for c in done:
        new_player = set_status(new_player, c.id, "done")
    return new_player, done


def complete_destroy_on_raze(player: Player, starbase_id: int) -> tuple[Player, list[Contract]]:
    """Mark done any active destroy job targeting the razed starbase (WP57, WP40 hook)."""
    done = [c for c in active(player, "destroy") if c.target_starbase_id == starbase_id]
    new_player = player
    for c in done:
        new_player = set_status(new_player, c.id, "done")
    return new_player, done


# --- escort = convoy warp (interview decision 9) ---------------------------------


def is_convoyed(state: UniverseState, species_id: int) -> bool:
    """Whether a species instance is under escort by any player (§6.7, WP57).

    A convoyed merchant leaves the drift/trader rails (`alien_drift` and `trader_step` skip
    it) and instead moves with the escorting player's warps — one predicate, so replay
    reconstructs the convoy exactly rather than the merchant wandering off mid-escort.
    """
    return any(
        c.kind == "escort" and c.status == "active" and c.target_species_id == species_id
        for player in state.players.values()
        for c in player.contracts
    )


def convoy_for(player: Player, from_sector: int) -> list[Contract]:
    """Active escort contracts whose merchant should move with a hop departing `from_sector`.

    The convoy follows only when the merchant is *in the sector the player is leaving*
    (interview decision 9): a hop taken from elsewhere leaves the merchant waiting (the
    convoy suspends, resumes on return) — the caller checks the merchant's live position
    against `from_sector`.
    """
    return active(player, "escort")


def advance_convoy(state: UniverseState, player: Player, from_sector: int, to_sector: int,
                   day: int, positions: dict[int, AlienSpecies] | None = None
                   ) -> tuple[Player, list[AlienSpecies], list[Contract]]:
    """Move escorted merchants with a player's hop and complete arrivals (§6.7, WP57).

    For each active escort contract whose merchant currently sits in `from_sector`, relocate
    the merchant to `to_sector` (it rides in the same `ReduceResult` as the player's warp, so
    convoy replays exactly). A merchant that thereby reaches its destination sector completes
    the contract — the caller pays the reward and emits the event. `positions` is an optional
    id→instance override carrying the merchant's *live* position through a multi-hop journey
    (mid-reduce `state` is not yet mutated, so a plain state read would freeze the merchant
    after one hop); the loop feeds each hop's relocation back in. Returns
    `(player, moved_merchants, completed_contracts)`; the player is unchanged except for
    completed statuses (rewards are applied by the caller's single latinum mutation).
    """
    moved: list[AlienSpecies] = []
    completed: list[Contract] = []
    new_player = player
    for c in active(new_player, "escort"):
        if c.target_species_id is None:
            continue
        merchant = (positions or {}).get(c.target_species_id) or state.species.get(c.target_species_id)
        if merchant is None or merchant.sector_id != from_sector:
            continue  # the convoy is suspended — merchant is elsewhere, waiting
        relocated = replace(merchant, sector_id=to_sector)
        moved.append(relocated)
        if to_sector == c.dest_sector:
            new_player = set_status(new_player, c.id, "done")
            completed.append(c)
    return new_player, moved, completed


# --- deadline expiry (daily cron) ------------------------------------------------


def expire_deadlines(player: Player, day: int) -> tuple[Player, list[Contract]]:
    """Fail every active contract past its deadline (DESIGN §6.7, WP57 — daily cron).

    Runs next to grudge decay on the daily clock; a lapsed escort simply releases its
    merchant back to the drift rails (the `is_convoyed` predicate goes false once the job is
    no longer active). Returns the updated player + the newly-failed contracts for events.
    """
    lapsed = [c for c in active(player) if day > c.deadline_day]
    new_player = player
    for c in lapsed:
        new_player = set_status(new_player, c.id, "failed")
    return new_player, lapsed
