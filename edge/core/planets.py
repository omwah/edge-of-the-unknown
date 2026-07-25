"""Planetary production — the BNT colonist model shaped by planet_type (§4.2, §8).

Pure functions over the frozen `Planet`: no I/O, no RNG. `produce` advances one
production tick — only an **owned** planet collects (§8). Colonizable worlds turn
(capped) colonists into ore / organics / equipment by `allocation × yield_profile`,
then eat organics as food (growth when fed, starvation when not); uncolonizable
worlds extract instead (jovian fuel-scoop, asteroid mining, barren nothing). The
engine `planet_growth` cron schedules this; the math lives here (CLAUDE.md layering).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from edge.core.config import GameConfig
from edge.core.enums import Commodity
from edge.core.models import UNOWNED, Planet


_PLANET_TYPE_LABELS = {
    "terrestrial_warm": "Warm Terrestrial",
    "terrestrial_cool": "Cool Terrestrial",
    "terrestrial_hot": "Hot Terrestrial",
    "terrestrial_cold": "Cold Terrestrial",
    "jovian": "Jovian",
    "asteroid_belt": "Asteroid Belt",
    "barren": "Barren",
}


def pretty_planet_type(planet_type: str) -> str:
    """A human-readable label for a `planet_type` key (§4.2). The raw key still keys
    config/yield/sprite lookups; this is display-only. Unknown keys fall back to a
    title-cased de-underscoring so a new config type reads sensibly without a map edit."""
    return _PLANET_TYPE_LABELS.get(planet_type, planet_type.replace("_", " ").title())


def is_colonizable(planet_type: str, config: GameConfig) -> bool:
    """Whether a world of this type can be claimed and settled (§4.2).

    Ordinary colonizable worlds are the only *type-based* route to colonists, stores,
    and a citadel — but a staged Cloud City (`is_cloud_city_world`) is a second,
    orthogonal route to colonists/stores on an otherwise-uncolonizable jovian (see
    `colonist_capacity`/`store_blocker`), and citadel eligibility is its own explicit
    `is_cloud_city_world` exclusion in `citadels.open_build`, not this predicate. Do not
    read this as gating transfer/banking/invasion — check the specific seam instead.
    """
    profile = config.planets.types.get(planet_type)
    return bool(profile and profile.colonizable)


def is_landable(planet_type: str, config: GameConfig) -> bool:
    """Whether a ship can descend onto this world's surface (§4.2).

    False for spatial "world objects" with no surface — asteroid belts — which are
    scanned and mined in orbit but never landed on. Unknown types default to landable
    so a new config type reads as an ordinary world without a code edit.
    """
    profile = config.planets.types.get(planet_type)
    return profile is None or profile.landable


def is_extractable(planet_type: str, config: GameConfig) -> bool:
    """Whether this world yields raw goods in orbit without colonists (§4.2).

    The uncolonizable dead worlds that auto-extract: a gas giant's fuel scoop and an
    asteroid belt's mining. Barren worlds extract nothing.
    """
    cfg = config.planets
    if planet_type == "jovian":
        return cfg.jovian_scoop > 0
    if planet_type == "asteroid_belt":
        return cfg.asteroid_mining > 0
    return False


def is_cloud_city_world(planet_type: str, config: GameConfig) -> bool:
    """Whether this type is a gas giant that can carry a Cloud City (§4.2, PT-54).

    Config-gated: a universe that prices staging at 0 has no cities, and every jovian
    stays a bare, unpeopled scoop.
    """
    return planet_type == "jovian" and config.planets.cloud_city_stage_cost > 0


def colonist_capacity(planet: Planet, config: GameConfig) -> int:
    """How many colonists this *world* can hold (§4.2, PT-54) — the capability seam.

    Keyed on the planet, not only its type: a colonizable world holds up to its
    `habitability_cap`; a **gas giant** holds nobody at all until a Cloud City is built,
    and then `cloud_city_size × cloud_city_berths` of them (a station's worth, not a
    world's). Everything else — belts, barren rock, an unstaged jovian — is 0. Shared by
    `Colonize`/`SettleColonists`, `produce`, and the `PlanetDTO` projection, so the
    screen's headroom and the reducer's clamp are the same number.
    """
    if is_cloud_city_world(planet.planet_type, config):
        return planet.cloud_city_size * config.planets.cloud_city_berths
    if is_colonizable(planet.planet_type, config):
        return planet.habitability_cap
    return 0


def colonist_blocker(planet: Planet, config: GameConfig) -> str:
    """Why this world can hold no colonists, or "" when it can (§4.2, PT-54).

    The human reason behind `colonist_capacity(...) == 0`, shared by the reducers that land
    people and the projection that offers to, so the refusal and the affordance agree.
    """
    if colonist_capacity(planet, config) > 0:
        return ""
    if is_cloud_city_world(planet.planet_type, config):
        return "a gas giant has no ground — build a staging area before landing anyone"
    return f"a {pretty_planet_type(planet.planet_type).lower()} cannot hold colonists"


_NO_HOME_SPECIES = "__player__"  # never a real roster_id; the no-roster/no-home-species fallback


def player_species_key(config: GameConfig) -> str:
    """The roster_id the player's own recruited colonists are tagged with (§4.2).

    The roster's `player_species_id` when the roster names one (the common case —
    Stardock recruits and any world the player colonizes are peopled by them); a
    stable sentinel otherwise, since a hand-built config with no roster still needs
    *some* key for Stardock recruits and it must never collide with a real roster_id.
    """
    roster = config.roster
    if roster is not None and roster.player_species_id is not None:
        return roster.player_species_id
    return _NO_HOME_SPECIES


def native_population_key(planet: Planet, config: GameConfig) -> str | None:
    """The native people occupying `planet`, or None (§4.2, GW-WP09-PRE follow-up).

    `population` may hold the player's own recruited people alongside — or instead of
    — a native polity's; this names the native one, for the hostility/access checks
    that only ever cared about "who lives here" in the singular. A Core/governor world
    whose only people happen to share the player's own species has nothing left to
    distinguish — but those worlds are friendly by ownership/alliance regardless, so
    hostility callers never need this for them.
    """
    home = player_species_key(config)
    for key in sorted(planet.population):
        if planet.population[key] > 0 and key != home:
            return key
    return None


def any_population_key(planet: Planet, config: GameConfig) -> str | None:
    """Some people occupying `planet`, preferring a native one, or None (§4.2).

    Unlike `native_population_key`, this does not give up on a world whose only
    people happen to share the player's own species — a Terran-peopled Core capital
    genuinely has settlements to describe, it just isn't a *hostility* subject (no
    unowned world is ever peopled by the player's own kind — see
    `native_population_key`). Generation-time "who lives here" metrics
    (`bigbang.inhabitants.is_friendly_inhabited`) want this; live hostility
    resolution (`groundwar.access._inhabiting_species`) wants the native-only view.
    """
    native = native_population_key(planet, config)
    if native is not None:
        return native
    home = player_species_key(config)
    return home if planet.population.get(home, 0) > 0 else None


def store_blocker(planet: Planet, config: GameConfig) -> str:
    """Why this world can hold no goods in `stores`, or "" when it can (§4.2, PT-54).

    A gas giant has nowhere to put a crate until its Cloud City exists — the reason the
    staging build is paid from the ship's *hold* rather than from stores (§4.2). Every other
    ownable world stores freely; the un-ownable ones (belts) never reach this seam, because
    a transfer already requires ownership.
    """
    if is_cloud_city_world(planet.planet_type, config) and planet.cloud_city_size <= 0:
        return "nothing can be stored on a gas giant until a staging area is built"
    return ""


def cloud_city_next_cost(planet: Planet, config: GameConfig) -> int:
    """The Equipment (carried aboard) that the *next* city size costs, 0 if none can be built.

    Size *n* costs `n × cloud_city_stage_cost` (§4.2), so the first staging area is one
    hold-load and a bigger city is earned. 0 at the `cloud_city_max_size` ceiling, or on a
    world that is not a Cloud City candidate at all.
    """
    cfg = config.planets
    if not is_cloud_city_world(planet.planet_type, config):
        return 0
    target = planet.cloud_city_size + 1
    if target > cfg.cloud_city_max_size:
        return 0
    return cfg.cloud_city_stage_cost * target


def cloud_city_blocker(planet: Planet, ship_equipment: int, owner_ok: bool,
                       config: GameConfig) -> str:
    """Why a `BuildStagingArea` is barred here, or "" when it is allowed (§4.2, PT-54).

    Shared by the reducer (which raises it) and the `PlanetDTO` projection (which greys the
    button and shows it), so the blocker text can never drift. `owner_ok` is the caller's
    ownership verdict — the world is unowned (the build claims it) or already the player's.
    Check order matches the reducer.
    """
    if not is_cloud_city_world(planet.planet_type, config):
        return f"a {pretty_planet_type(planet.planet_type).lower()} cannot carry a cloud city"
    if not owner_ok:
        return "that world is claimed — a cloud city can only be built on your own"
    cost = cloud_city_next_cost(planet, config)
    if cost <= 0:
        return "the cloud city is built out — it cannot grow any further"
    if ship_equipment < cost:
        return f"need {cost} equipment aboard to build (have {ship_equipment})"
    return ""


def genesis_valid_target(planet: Planet, config: GameConfig) -> bool:
    """Whether this world is a legal Genesis target: unowned and an eligible type (§4.2).

    Independent of whether a torpedo is aboard — that's the separate `has_device` axis
    (WP-PR12). Asteroid belts and other ineligible types are excluded because they are
    absent from `genesis.eligible_types`.
    """
    gen = config.genesis
    if gen is None:
        return False
    return not planet.owner.is_owned and planet.planet_type in gen.eligible_types


def genesis_blocker(planet: Planet, has_device: bool, config: GameConfig) -> str:
    """The human reason a Genesis deploy is barred here, or "" when it is allowed (§4.2).

    Shared by the `DeployGenesis` reducer (which raises it) and the `PlanetDTO` projection
    (which shows it), so the error text can never drift (WP-PR12). Check order matches the
    reducer: universe support, then a torpedo aboard, then a valid target (owned vs. type).
    """
    gen = config.genesis
    if gen is None:
        return "genesis torpedoes are not sold in this universe"
    if not has_device:
        return "no genesis torpedo aboard"
    if planet.owner.is_owned:
        return "that world is claimed — genesis only re-forms unclaimed worlds"
    if planet.planet_type not in gen.eligible_types:
        return f"a {planet.planet_type} world cannot be re-formed by genesis"
    return ""


def belt_mining_yield(planet: Planet, config: GameConfig) -> tuple[Commodity, int] | None:
    """The commodity + amount one mining action pulls from a belt (§4.2, PT-30/PT-52).

    Belts yield raw Equipment (metal, thin) in orbit without colonists. Returns None for any
    world that can't be mined this way (not an asteroid belt, or mining disabled in config).
    The nominal amount is `asteroid_mining` — the same seam the auto-collect (`produce`) draws
    on — **clamped to what is left in the belt's finite `ore_reserve`** (PT-52), so the reducer,
    the auto-collect, and the `PlanetDTO.mine_yield` projection can never disagree about what a
    haul is worth. A worked-out belt yields `(EQUIPMENT, 0)` rather than None: it is still a
    belt, it just has nothing left — the caller distinguishes "cannot be mined" from "empty".
    """
    if planet.planet_type != "asteroid_belt":
        return None
    amount = config.planets.asteroid_mining
    if amount <= 0:
        return None
    return (Commodity.EQUIPMENT, max(0, min(amount, planet.ore_reserve)))


def normalize_belt(planet: Planet, config: GameConfig) -> Planet:
    """Scrub colony/citadel/base affordances off a non-landable spatial world (§4.2).

    Asteroid belts are spatial features, not colonies: they never hold colonists, stores,
    allocation, a citadel, a treasury, a garrison, or an owner. Idempotent, so it runs both
    at generation and on any legacy planet re-read without changing an already-clean belt.
    Landable/colonizable worlds pass through untouched. `starbase_id` is cleared here; the
    caller is responsible for dropping the referenced `Starbase` from world state.
    """
    if is_landable(planet.planet_type, config):
        return planet
    # A belt with no reserve *ceiling* was never seeded (a pre-PT-52 world, or a hand-built
    # fixture) — not a worked-out one. Converge it on a full, band-agnostic field so "unseeded"
    # can never read as "spent"; a genuinely exhausted belt keeps `ore_reserve_max > 0` with
    # `ore_reserve == 0` and is left alone. The big bang overwrites this with the band-weighted
    # draw immediately after, so this is only ever the legacy path.
    reserve, reserve_max = planet.ore_reserve, planet.ore_reserve_max
    if reserve_max <= 0:
        reserve = reserve_max = config.planets.belt_reserve_base
    clean = replace(
        planet, owner=UNOWNED, population={},
        allocation={}, stores={}, citadel_level=0, citadel_progress=-1, treasury=0,
        fighters=0, gun_integrity=0, fighter_allocation=0.0, starbase_id=None,
        garrison_infantry=0, garrison_armor=0, garrison_allocation=0.0,
        ore_reserve=reserve, ore_reserve_max=reserve_max,
    )
    return planet if clean == planet else clean


def retype_planet(planet: Planet, new_type: str, config: GameConfig) -> Planet:
    """Return `planet` re-typed to `new_type` with its yield/habitability re-rolled
    from config (§4.2). Deterministic — the type's profile is fixed config, so a
    Genesis retype (WP10) replays exactly. Raises on an unknown type."""
    profile = config.planets.types.get(new_type)
    if profile is None:
        raise ValueError(f"unknown planet_type {new_type!r}")
    belt = new_type == "asteroid_belt"
    return replace(
        planet, planet_type=new_type, habitability_cap=profile.habitability,
        yield_profile={Commodity(k): v for k, v in profile.yield_profile.items()},
        # An ore reserve belongs to a belt (§4.2, PT-52) and a cloud city to a gas giant
        # (PT-54) — re-forming a world must not carry a stale field, or a stale city, along.
        ore_reserve=planet.ore_reserve if belt else 0,
        ore_reserve_max=planet.ore_reserve_max if belt else 0,
        cloud_city_size=planet.cloud_city_size if new_type == "jovian" else 0,
    )


def _add(stores: dict[Commodity, int], commodity: Commodity, amount: int) -> None:
    if amount:
        stores[commodity] = max(0, stores.get(commodity, 0) + amount)


def scale_population(population: Mapping[str, int], old_total: int, new_total: int) -> dict[str, int]:
    """Grow or shrink every people on a world by the same ratio, to exactly `new_total`.

    Largest-remainder rounding (deterministic — ties break on key) keeps a mixed
    colony's proportions stable tick over tick instead of letting round-off silently
    drain one people to feed another (§4.2, GW-WP09-PRE follow-up).
    """
    if old_total <= 0 or new_total == old_total:
        return dict(population)
    shares = {k: v * new_total / old_total for k, v in population.items()}
    floors = {k: int(s) for k, s in shares.items()}
    remainder = new_total - sum(floors.values())
    order = sorted(population, key=lambda k: (-(shares[k] - floors[k]), k))
    for k in order[:remainder]:
        floors[k] += 1
    return {k: v for k, v in floors.items() if v > 0}


def garrison_training(
    config: GameConfig, *, output: float, allocation: float,
    equipment_available: int, current_infantry: int, cap: int,
) -> tuple[int, int]:
    """Infantry minted this tick from a colonist-allocation training share (GW plan D11).

    `raw = output × allocation × train_yield`, clamped to what
    `equipment_available // train_equipment_cost` affords and to the headroom under
    `cap`. Returns `(infantry_gained, equipment_consumed)`; equipment spent is exactly
    `infantry_gained × train_equipment_cost` — conserved, never debt. The canonical
    copy: `produce()` below calls this directly rather than duplicating the formula
    (this module already owns `colonist_capacity`, so putting the function in
    `edge.core.groundwar.assault` instead would risk a `planets.py` ↔ `assault.py`
    import cycle for no benefit). `edge.core.groundwar.assault` and `session.py`
    import it from here for a projected "training X/day" readout.
    """
    assert config.groundwar is not None
    gcfg = config.groundwar.garrison_economy
    headroom = max(0, cap - current_infantry)
    raw = int(output * allocation * gcfg.train_yield)
    if gcfg.train_equipment_cost > 0:
        raw = min(raw, equipment_available // gcfg.train_equipment_cost)
    gained = max(0, min(raw, headroom))
    return gained, gained * gcfg.train_equipment_cost


def produce(planet: Planet, config: GameConfig) -> Planet:
    """Run one production tick for `planet`, returning the updated world (§8).

    A no-op for an unowned planet (only the owner collects, §8) and for a type with
    no profile. Goods only ever accumulate into `stores` (never negative); colonists
    stay within the world's colonist capacity — the habitability cap on a colonizable
    world, the Cloud City's berths on a staged gas giant (§4.2, PT-54). A world may hold
    several peoples at once (`population`, GW-WP09-PRE follow-up); growth/starvation
    scales every one of them by the same ratio, so the mix doesn't drift.
    """
    if not planet.owner.is_owned and not planet.protectorate_controller.is_owned:
        return planet
    cfg = config.planets
    profile = cfg.types.get(planet.planet_type)
    if profile is None:
        return planet

    stores = dict(planet.stores)
    stores_before = dict(planet.stores)
    protectorate_stores = dict(planet.protectorate_stores)
    population = dict(planet.population)
    colonists = planet.colonists
    fighters = planet.fighters
    garrison_infantry = planet.garrison_infantry
    ore_reserve = planet.ore_reserve
    # The one capacity seam (§4.2): >0 means people can live here — on the ground, or in a
    # built Cloud City. A gas giant with no city has none, so it only scoops.
    capacity = colonist_capacity(planet, config)

    if capacity > 0:
        effective = min(colonists, capacity)
        output = effective * cfg.production_rate
        for commodity in Commodity:
            alloc = planet.allocation.get(commodity, 0.0)
            mult = profile.yield_profile.get(commodity.value, 0.0)
            _add(stores, commodity, round(output * alloc * mult))
        # Garrison production (§4.2, WP55): the fighter allocation share mints defenders
        # instead of trade goods — the colony trades output for its own protection.
        if planet.fighter_allocation > 0.0 and config.citadels is not None:
            fighters += round(output * planet.fighter_allocation * config.citadels.fighter_yield)
        # Ground-garrison training (GW plan D11, GW-WP09): a separate colonist-output
        # share mints persistent infantry defenders instead, gated by equipment stores
        # and a population-fraction ceiling. `garrison_armor` is never touched here —
        # no player rail creates armor (only big-bang seeding and its own militia-
        # recovery rail do).
        if planet.garrison_allocation > 0.0 and config.groundwar is not None:
            gcfg = config.groundwar.garrison_economy
            cap = round(capacity * gcfg.cap_frac)
            gained, spent = garrison_training(
                config, output=output, allocation=planet.garrison_allocation,
                equipment_available=stores.get(Commodity.EQUIPMENT, 0),
                current_infantry=garrison_infantry, cap=cap)
            if gained:
                garrison_infantry += gained
                _add(stores, Commodity.EQUIPMENT, -spent)
        # Food: eat organics; grow when fed (capped), else starve.
        need = round(colonists * cfg.food_per_colonist)
        have = stores.get(Commodity.ORGANICS, 0)
        if have >= need:
            stores[Commodity.ORGANICS] = have - need
            new_colonists = min(capacity, colonists + round(colonists * cfg.growth_rate))
            population = scale_population(population, colonists, new_colonists)
            colonists = new_colonists
        elif colonists > 0:
            stores[Commodity.ORGANICS] = 0
            new_colonists = max(0, colonists - round(colonists * cfg.starvation_rate))
            population = scale_population(population, colonists, new_colonists)
            colonists = new_colonists

    if planet.planet_type == "jovian":
        # The scoop runs city or no city — it is the gas giant itself paying out. A Cloud
        # City's people produce *on top of* it, through the colony block above (§4.2, PT-54),
        # against a yield profile with no Organics in it: a sky city imports its food or starves.
        _add(stores, Commodity.FUEL_ORE, cfg.jovian_scoop)
    elif not profile.colonizable:
        # The shared belt seam — already clamped to the finite reserve (PT-52), so an
        # auto-collect can no more mint ore out of a worked-out field than a player can.
        # (A belt is always unowned, so this branch is unreachable today; keeping it honest
        # means it stays correct if a belt ever becomes ownable.)
        haul = belt_mining_yield(planet, config)
        if haul is not None and haul[1] > 0:
            _add(stores, *haul)
            ore_reserve -= haul[1]
    # barren (and any other uncolonizable type) produces nothing.

    # A protectorate remains a native economy. Only the configured share of net
    # positive production enters the controller's separate ledger; ordinary stores
    # and the treasury remain the inhabitants' property (D13).
    if planet.protectorate_controller.is_owned and config.groundwar is not None:
        share = config.groundwar.settlement.protectorate_production_share
        for commodity in Commodity:
            gained = max(0, stores.get(commodity, 0) - stores_before.get(commodity, 0))
            paid = min(gained, round(gained * share))
            if paid:
                stores[commodity] = stores.get(commodity, 0) - paid
                protectorate_stores[commodity] = protectorate_stores.get(commodity, 0) + paid

    if (population == dict(planet.population) and fighters == planet.fighters
            and garrison_infantry == planet.garrison_infantry
            and ore_reserve == planet.ore_reserve and stores == dict(planet.stores)
            and protectorate_stores == dict(planet.protectorate_stores)):
        return planet  # nothing changed (e.g. an empty colony) — skip the rewrite
    return replace(planet, stores=stores, population=population, fighters=fighters,
                   garrison_infantry=garrison_infantry, ore_reserve=ore_reserve,
                   protectorate_stores=protectorate_stores)
