"""Seed the inhabited universe: native polities on generated worlds (GW-WP09-PRE).

Until this pass existed, **nothing ever set `Planet.inhabited_by_species_id`** — the
only writer in the tree cleared it — so a generated universe held 195 worlds and not
one inhabitant. That is not cosmetic: the ground-access classifier calls a world
inhabited when it has live colonists, an inhabiting species, or a built Cloud City,
so every world was either uninhabited (survey) or a Cloud City (orbital-only under
D9), and a world the player colonised was their own and therefore friendly. **No
world could route to assault at all**, and D2's protectorate — whose whole subject is
the unaligned inhabited world — had no instance to apply to.

Three populations are seeded, because their politics differ:

- **Core worlds** hold the governing alliance's people. Friendly, and sanctuary
  besides (G13), but a lived-in capital rather than empty real estate.
- **Home-cluster worlds** hold their bloc's people (§5 step 6, §6.3). Friendly while
  the player stands with that bloc — and assaultable the day they do not.
- **Unaligned worlds** keep `owner=none` *and* carry a species: a people without a
  flag. These are the D2 protectorate's subject and the only worlds a fresh player
  may lawfully assault.

Population is a fraction of the world's own **capacity** (habitability, or a Cloud
City's berths), so a small world holds a small people, and a world that can hold
nobody — a belt, bare rock, an unstaged gas giant — holds nobody. Inhabited worlds
may carry citadel holdings, which is what makes the orbital siege ladder bite before
a ground assault can begin.

Runs after `populate_species` (it needs the placed cast and the carved home clusters)
on its own salted sub-RNG, so it cannot shift the §7 discovery draw or the species
placement order. `produce()` is a no-op on an unowned world, so an unaligned people
is *static*: seeding them turns on no new economic churn. An alliance-owned world
with people does now produce and grow on the daily cron — it always would have, but
before this pass there was never anyone on it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from edge.core.aliens import resolve_species_by_kind
from edge.core.config import GameConfig, InhabitantsConfig
from edge.core.enums import Commodity
from edge.core.groundwar.assault import seed_garrison
from edge.core.models import AlienSpecies, Planet, UniverseState
from edge.core.planets import any_population_key, colonist_capacity, is_cloud_city_world, is_landable
from edge.core.starbases import is_operational

_INHABITANTS_SALT = 0x494E4841  # "INHA"


def seed_inhabitants(state: UniverseState, config: GameConfig) -> None:
    """Give the generated universe its native peoples, populations, and holdings."""
    cfg = config.planets.inhabitants
    if not state.species:  # a universe generated without a roster stays empty
        return
    rng = random.Random(state.game.seed ^ _INHABITANTS_SALT)
    gov = state.game.core_governing_alliance_id

    cast = _Cast.of(state, config)
    for pid in sorted(state.planets):
        planet = state.planets[pid]
        if not _can_hold_a_people(state, planet, config):
            continue
        sector = state.sectors[planet.sector_id]
        chance, candidates = cast.who_lives_here(
            planet, sector.is_galactic_core, sector.distance_band, gov, cfg)
        # Draw unconditionally before the candidate test so the stream stays stable
        # whichever worlds happen to have a plausible people this seed.
        roll = rng.random()
        bias_roll = rng.random()
        if not candidates or roll >= chance:
            continue
        # Beyond the blocs, a **wary** people is likelier: the friendly ones live under
        # a flag, in the Core or a home cluster. This is the same "danger rises with
        # distance from protection" gradient the discovery and species bands use, and
        # it is what makes an unaligned frontier world a ground target rather than a
        # second friendly survey (GW-WP09-PRE).
        if not planet.owner.is_owned and not sector.is_galactic_core:
            if bias_roll < cfg.unaligned_wary_bias:
                candidates = cast.wary_pool(sector.distance_band) or candidates
        species_id = candidates[rng.randrange(len(candidates))]
        state.planets[pid] = _settle(state, planet, species_id, config, rng)

    _guarantee_targets(state, config, rng, cast)


@dataclass(frozen=True, slots=True)
class _Cast:
    """The generated species, indexed the ways the seeding pass asks about them."""

    by_alliance: dict[int, list[int]]
    unaligned: list[int]
    unaligned_by_band: dict[str, list[int]]
    #: The **wary** cast — every species below the amity threshold, flag or no flag.
    #: Unaligned wary peoples are preferred for an unowned world (a people with no bloc
    #: is the cleanest protectorate subject), but a bloc's kind living beyond its
    #: cluster on nobody's world is equally coherent — and necessary, because the roster
    #: skews friendly (§6) and a cast can be drawn with *no* wary unaligned species at
    #: all, which would otherwise leave the universe with nothing to assault.
    wary: list[int]
    wary_by_band: dict[str, list[int]]
    wary_unaligned: list[int]
    wary_unaligned_by_band: dict[str, list[int]]

    @classmethod
    def of(cls, state: UniverseState, config: GameConfig) -> "_Cast":
        amity = config.aliens.amity_threshold
        cast = cls({}, [], {}, [], {}, [], {})
        for sid in sorted(state.species):  # sorted: the pools must not depend on dict order
            species = state.species[sid]
            wary = species.base_disposition < amity
            if wary:
                cast.wary.append(sid)
                cast.wary_by_band.setdefault(species.home_band, []).append(sid)
            if species.alliance_id is None:
                cast.unaligned.append(sid)
                cast.unaligned_by_band.setdefault(species.home_band, []).append(sid)
                if wary:
                    cast.wary_unaligned.append(sid)
                    cast.wary_unaligned_by_band.setdefault(species.home_band, []).append(sid)
            else:
                cast.by_alliance.setdefault(species.alliance_id, []).append(sid)
        return cast

    def wary_pool(self, band: str) -> list[int]:
        """The below-amity species that could live here, best fit first.

        Preference order: an unaligned wary people of this band, any unaligned wary
        people, a wary people of this band, any wary people. Empty only when the whole
        cast is friendly — a real possibility, and the caller's problem to report.
        """
        return (self.wary_unaligned_by_band.get(band) or self.wary_unaligned
                or self.wary_by_band.get(band) or self.wary)

    def who_lives_here(self, planet: Planet, in_core: bool, band: str, gov: int | None,
                       cfg: InhabitantsConfig) -> tuple[float, list[int]]:
        """The chance this world is peopled, and by which species it could be.

        Ownership names the polity: the Core is the governor's, an alliance-held world
        is its bloc's, and everything else is unaligned — a people with no flag, which
        is the shape D2's protectorate needs (`owner=none` beside a species id).
        """
        if in_core:
            return cfg.core_chance, self.by_alliance.get(gov, []) if gov is not None else []
        owner = planet.owner
        if owner.kind == "alliance" and owner.ref is not None:
            return cfg.home_cluster_chance, self.by_alliance.get(owner.ref, [])
        # Unaligned: prefer a species whose home band is this one, so a people is met
        # roughly where its kind lives; fall back to the whole unaligned cast.
        return cfg.band_chance.get(band, 0.0), self.unaligned_by_band.get(band) or self.unaligned


def _guarantee_targets(state: UniverseState, config: GameConfig, rng: random.Random,
                       cast: "_Cast") -> None:
    """Top the assaultable set up to the configured floor **by construction**.

    The probabilistic pass above produces targets only in expectation, and the roster
    deliberately skews friendly (§6), so an unlucky cast can leave a universe with
    nothing to assault — and retrying generation does not reliably fix it, because the
    shortage is in the *species draw*, not the planet draw. So the floor is enforced
    here rather than merely checked, exactly as `_finalize_planets` enforces the
    monotone unowned fraction per seed instead of in expectation.

    Only genuinely unowned, uninhabited, capable worlds outside the Core are used, and
    only wary species settle them, so a topped-up world is indistinguishable from one
    the roll produced. Deepest bands first: a target belongs on the frontier. If the
    cast holds no wary unaligned species at all, nothing can be done here and the
    validator's failure is the honest outcome — a retry redraws the cast.
    """
    cfg = config.planets.inhabitants
    if not cast.wary or cfg.min_assaultable <= 0:
        return
    band_order = [b.name for b in config.bigbang.active_bands()]
    depth = {name: i for i, name in enumerate(band_order)}

    assaultable, _ = ground_target_counts(state, config)
    missing = cfg.min_assaultable - assaultable
    if missing <= 0:
        return
    candidates = _settleable_worlds(state, config)
    # Deepest band first, then by id so the choice is stable for a seed.
    candidates.sort(key=lambda pid: (
        -depth.get(state.sectors[state.planets[pid].sector_id].distance_band, 0), pid))
    for pid in candidates[:missing]:
        planet = state.planets[pid]
        band = state.sectors[planet.sector_id].distance_band
        pool = cast.wary_pool(band)
        species_id = pool[rng.randrange(len(pool))]
        state.planets[pid] = _settle(state, planet, species_id, config, rng)


def _can_hold_a_people(state: UniverseState, planet: Planet, config: GameConfig) -> bool:
    """Whether this world could hold a native population at all.

    Capacity is the seam (§4.2): a belt, bare rock, or an unstaged gas giant holds
    nobody. A world hosting a **derelict** base is skipped too — the starbase
    validator requires a derelict to sit on an unowned *and uninhabited* world, so
    peopling one would invalidate the universe (the same rule `_settle_cluster`
    respects when a bloc claims its cluster).
    """
    if not is_landable(planet.planet_type, config):
        return False
    if colonist_capacity(planet, config) <= 0:
        return False
    if planet.starbase_id is not None:
        base = state.starbases.get(planet.starbase_id)
        if base is not None and not is_operational(base):
            return False
    return True


def _settle(state: UniverseState, planet: Planet, species_id: int, config: GameConfig,
            rng: random.Random) -> Planet:
    """Give `planet` its people, their stores, and any citadel they have raised.

    `species_id` names a placed **instance** (`_Cast`'s pools are drawn from
    `state.species`); `population` is keyed by the kind (`roster_id`, GW-WP09-PRE
    follow-up), so it is resolved here once rather than carried as an instance id a
    later kill could orphan.
    """
    cfg = config.planets.inhabitants
    roster_id = state.species[species_id].roster_id
    capacity = colonist_capacity(planet, config)
    frac = rng.uniform(cfg.population_min_frac, cfg.population_max_frac)
    colonists = max(1, int(capacity * frac))
    thousands = colonists / 1000.0

    stores_total = int(thousands * cfg.stores_per_1k)
    profile = planet.yield_profile or {c: 1.0 / len(Commodity) for c in Commodity}
    total_weight = sum(profile.values()) or 1.0
    stores = {c: int(stores_total * profile.get(c, 0.0) / total_weight) for c in Commodity}

    # An inhabited world may have fortified. L2+ raises the fixed citadel gun, which is
    # a rung of the orbital siege ladder a ground assault must clear first (G12).
    level, gun = 0, 0
    citadels = config.citadels
    roll = rng.random()  # drawn unconditionally, so the stream ignores config gaps
    if citadels is not None and cfg.citadel_max_level > 0 and roll < cfg.citadel_chance:
        level = rng.randint(1, min(cfg.citadel_max_level, len(citadels.levels)))
        if level >= citadels.gun_min_level:
            gun = citadels.gun_hull

    # Persistent ground-defense garrison (GW plan D11, GW-WP09): seeded once, here, off
    # the same salted `rng` `_settle` already draws from (no new stream, so this cannot
    # perturb the discovery/species draw order). A consequence of settlement, not an
    # input to it — `_can_hold_a_people`/`_guarantee_targets`/`target_floors` are unaffected.
    infantry, armor = 0, 0
    if config.groundwar is not None:
        species = state.species[species_id]
        hostile = (config.aliens is not None
                   and species.base_disposition < config.aliens.amity_threshold)
        band = state.sectors[planet.sector_id].distance_band
        infantry, armor = seed_garrison(
            config, capacity=capacity, citadel_level=level, distance_band=band,
            hostile=hostile, alliance_owned=planet.owner.kind == "alliance", rng=rng)

    return replace(
        planet,
        population={roster_id: colonists},
        stores={c: q for c, q in stores.items() if q > 0},
        allocation={c: 1.0 / len(Commodity) for c in Commodity},
        citadel_level=level,
        gun_integrity=gun,
        treasury=int(thousands * cfg.treasury_per_1k) if level > 0 else 0,
        garrison_infantry=infantry,
        garrison_armor=armor,
    )


# --- the generation invariant ------------------------------------------------


def is_assaultable_for_a_fresh_player(
    state: UniverseState, planet: Planet, config: GameConfig
) -> bool:
    """Whether a brand-new player could route this world to assault (GW-WP09-PRE).

    Deliberately *not* the full `ground_access` classifier, which needs a `Player`:
    this is the generation-time question "does the universe field targets at all",
    answered for the baseline player — no attitude, no grudges, governing-alliance
    membership. It therefore reads the species' own base disposition against the
    amity threshold, and honours the two hard boundaries a player cannot move:
    Core sanctuary (G13) and the Cloud City gate (D9).
    """
    species = _inhabitant(state, planet, config)
    if species is None:
        return False
    if state.sectors[planet.sector_id].is_galactic_core:  # G13
        return False
    if is_cloud_city_world(planet.planet_type, config):  # D9 — orbital-only for now
        return False
    return species.base_disposition < config.aliens.amity_threshold


def is_friendly_inhabited(state: UniverseState, planet: Planet, config: GameConfig) -> bool:
    """Whether this world's survey would find settlements to visit (D5/D6)."""
    species = _inhabitant(state, planet, config)
    return species is not None and species.base_disposition >= config.aliens.amity_threshold


def _inhabitant(state: UniverseState, planet: Planet, config: GameConfig) -> AlienSpecies | None:
    """*Some* of the world's people, live if possible, durable otherwise (§6, §4.2).

    `any_population_key`, not `native_population_key`: this asks "is there a plausible
    people to describe" for the generation-time assault/friendly *counts*, not "is
    there a hostility subject" — a Terran-peopled Core capital genuinely has
    settlements, it just can never be assaultable (Core sanctuary, checked before this
    is even reached) or read as hostile (Terran's disposition is always friendly-band).
    """
    key = any_population_key(planet, config)
    if key is None:
        return None
    return resolve_species_by_kind(state, key, config.roster)


def ground_target_counts(state: UniverseState, config: GameConfig) -> tuple[int, int]:
    """`(assaultable, friendly_inhabited)` for a fresh player — the seed's target set."""
    assaultable = sum(1 for p in state.planets.values()
                      if is_assaultable_for_a_fresh_player(state, p, config))
    friendly = sum(1 for p in state.planets.values()
                   if is_friendly_inhabited(state, p, config))
    return assaultable, friendly


def _settleable_worlds(state: UniverseState, config: GameConfig) -> list[int]:
    """Free worlds a native people could still be seeded onto (unowned, capable, non-Core).

    Cloud Cities are excluded: D9 keeps them orbital-only, so peopling one adds a
    friendly neighbour but never a ground target.
    """
    return [
        pid for pid in sorted(state.planets)
        if not state.planets[pid].population
        and not state.planets[pid].owner.is_owned
        and not state.sectors[state.planets[pid].sector_id].is_galactic_core
        and not is_cloud_city_world(state.planets[pid].planet_type, config)
        and _can_hold_a_people(state, state.planets[pid], config)
    ]


def target_floors(state: UniverseState, config: GameConfig) -> tuple[int, int]:
    """The floors **this** universe is held to: configured, capped by what it can supply.

    A configured floor is a target for a full-size universe, not a law of nature. A
    small universe may hold only a handful of worlds, and a cast can be drawn with *no*
    below-amity species at all (the roster skews friendly, §6) — in which case no world
    anywhere could be a ground target and demanding one would reject a perfectly valid,
    peaceable universe. Capping by supply keeps the invariant meaningful ("field as many
    targets as you can, up to the configured floor") without making generation
    impossible.

    Both the constructive top-up and the validator read this one seam, so they cannot
    disagree about what the universe owes.
    """
    cfg = config.planets.inhabitants
    amity = config.aliens.amity_threshold
    assaultable, friendly = ground_target_counts(state, config)
    free = len(_settleable_worlds(state, config))
    has_wary = any(s.base_disposition < amity for s in state.species.values())
    assault_floor = min(cfg.min_assaultable, assaultable + free) if has_wary else 0
    friendly_floor = min(cfg.min_friendly_inhabited, friendly + free)
    return assault_floor, friendly_floor
