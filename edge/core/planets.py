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
from edge.core.models import Planet


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
    """Whether a world of this type can be claimed and settled (§4.2)."""
    profile = config.planets.types.get(planet_type)
    return bool(profile and profile.colonizable)


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
    elif planet.planet_type == "asteroid_belt":
        _add(stores, Commodity.EQUIPMENT, cfg.asteroid_mining)
    # barren (and any other uncolonizable type) produces nothing.

    if (colonists == planet.colonists and fighters == planet.fighters
            and stores == dict(planet.stores)):
        return planet  # nothing changed (e.g. an empty colony) — skip the rewrite
    return replace(planet, stores=stores, colonists=colonists, fighters=fighters)
