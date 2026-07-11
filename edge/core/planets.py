"""Planetary production — the BNT colonist model shaped by planet_type (§4.2, §8).

Pure functions over the frozen `Planet`: no I/O, no RNG. `produce` advances one
production tick — only an **owned** planet collects (§8). Colonizable worlds turn
(capped) colonists into ore / organics / equipment by `allocation × yield_profile`,
then eat organics as food (growth when fed, starvation when not); uncolonizable
worlds extract instead (jovian fuel-scoop, asteroid mining, barren nothing). The
engine `planet_growth` cron schedules this; the math lives here (CLAUDE.md layering).
"""

from __future__ import annotations

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

    Colonizable worlds are the only ones that hold colonists, colony stores, and
    citadels — so this predicate also gates transfer/citadel/banking/invasion.
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


def belt_mining_yield(planet_type: str, config: GameConfig) -> tuple[Commodity, int] | None:
    """The commodity + per-action amount a player pulls from hand-mining a belt (§4.2, PT-30).

    Belts yield raw Equipment (metal, thin) in orbit without colonists. Returns None for any
    world that can't be hand-mined this way (not an asteroid belt, or mining disabled in
    config). The amount reuses `asteroid_mining` — the same seam the owned-world auto-collect
    (`produce`) draws on — so the two extraction paths stay balanced by one config value.
    """
    if planet_type != "asteroid_belt":
        return None
    amount = config.planets.asteroid_mining
    if amount <= 0:
        return None
    return (Commodity.EQUIPMENT, amount)


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
    clean = replace(
        planet, owner=UNOWNED, inhabited_by_species_id=None, colonists=0,
        allocation={}, stores={}, citadel_level=0, citadel_progress=-1, treasury=0,
        fighters=0, gun_integrity=0, fighter_allocation=0.0, starbase_id=None,
    )
    return planet if clean == planet else clean


def retype_planet(planet: Planet, new_type: str, config: GameConfig) -> Planet:
    """Return `planet` re-typed to `new_type` with its yield/habitability re-rolled
    from config (§4.2). Deterministic — the type's profile is fixed config, so a
    Genesis retype (WP10) replays exactly. Raises on an unknown type."""
    profile = config.planets.types.get(new_type)
    if profile is None:
        raise ValueError(f"unknown planet_type {new_type!r}")
    return replace(
        planet, planet_type=new_type, habitability_cap=profile.habitability,
        yield_profile={Commodity(k): v for k, v in profile.yield_profile.items()},
    )


def _add(stores: dict[Commodity, int], commodity: Commodity, amount: int) -> None:
    if amount:
        stores[commodity] = max(0, stores.get(commodity, 0) + amount)


def produce(planet: Planet, config: GameConfig) -> Planet:
    """Run one production tick for `planet`, returning the updated world (§8).

    A no-op for an unowned planet (only the owner collects, §8) and for a type with
    no profile. Goods only ever accumulate into `stores` (never negative); colonists
    stay within the habitability cap.
    """
    if not planet.owner.is_owned:
        return planet
    cfg = config.planets
    profile = cfg.types.get(planet.planet_type)
    if profile is None:
        return planet

    stores = dict(planet.stores)
    colonists = planet.colonists
    fighters = planet.fighters

    if profile.colonizable:
        effective = min(colonists, planet.habitability_cap)
        output = effective * cfg.production_rate
        for commodity in Commodity:
            alloc = planet.allocation.get(commodity, 0.0)
            mult = profile.yield_profile.get(commodity.value, 0.0)
            _add(stores, commodity, round(output * alloc * mult))
        # Garrison production (§4.2, WP55): the fighter allocation share mints defenders
        # instead of trade goods — the colony trades output for its own protection.
        if planet.fighter_allocation > 0.0 and config.citadels is not None:
            fighters += round(output * planet.fighter_allocation * config.citadels.fighter_yield)
        # Food: eat organics; grow when fed (capped), else starve.
        need = round(colonists * cfg.food_per_colonist)
        have = stores.get(Commodity.ORGANICS, 0)
        if have >= need:
            stores[Commodity.ORGANICS] = have - need
            colonists = min(planet.habitability_cap, colonists + round(colonists * cfg.growth_rate))
        elif colonists > 0:
            stores[Commodity.ORGANICS] = 0
            colonists = max(0, colonists - round(colonists * cfg.starvation_rate))
    elif planet.planet_type == "jovian":
        _add(stores, Commodity.FUEL_ORE, cfg.jovian_scoop)
    else:
        haul = belt_mining_yield(planet.planet_type, config)  # the shared belt-yield seam
        if haul is not None:
            _add(stores, *haul)
    # barren (and any other uncolonizable type) produces nothing.

    if (colonists == planet.colonists and fighters == planet.fighters
            and stores == dict(planet.stores)):
        return planet  # nothing changed (e.g. an empty colony) — skip the rewrite
    return replace(planet, stores=stores, colonists=colonists, fighters=fighters)
