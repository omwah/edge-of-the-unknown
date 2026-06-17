"""Core enumerations: the canonical TW commodity trio and port classes (§4).

These are *structural* game definitions (what a port class means), not tunable
balance constants — prices/stock/distribution live in config (`default.yaml`).
The eight buy/sell triples follow terminal-space (§A.2); Class 9 is the StarDock.
"""

from __future__ import annotations

from enum import Enum


class Commodity(Enum):
    """The canonical TW2002 trio (DESIGN §4). No fourth commodity (BNT's energy)."""

    FUEL_ORE = "fuel_ore"
    ORGANICS = "organics"
    EQUIPMENT = "equipment"


class Component(Enum):
    """The shared engine-room component vocabulary (DESIGN §4.1).

    Eight fungible part kinds slot into the four subsystems (and WP4 starbase
    reactors). What a part *does* depends on the subsystem it fills; the aspect
    formulas (config) read only how many parts a subsystem carries and their tier.
    """

    ACCELERATOR = "accelerator"
    CONVERTER = "converter"
    RADIATOR = "radiator"
    SECONDARY = "secondary"
    TURBINE = "turbine"
    BURNER = "burner"
    LINKAGE = "linkage"
    NAVIGATOR = "navigator"


class ComponentTier(Enum):
    """Component tech tiers I–III (DESIGN §4.1). Int values give natural ordering.

    Tier I is latinum-buyable; II is latinum + barter; III is barter-only (§8).
    The integer value is the tier's "rank" used by the aspect formulas
    (`per_tier × (tier − 1)`); the name (`I`/`II`/`III`) is the display/serialized form.
    """

    I = 1  # noqa: E741 — Roman-numeral tier name, not an ambiguous identifier
    II = 2
    III = 3


class Subsystem(Enum):
    """The four slotted player-ship subsystems plus the WP4 starbase reactor (§4.1).

    A ship's `shields` / `warp_speed` / `combat_speed` / main-gun aspects are
    *derived* from the components filling these subsystems; `fusion_reactor` powers
    an orbital starbase (the engine-room model minus thrusters/spindrive, §4.2).
    """

    SPINDRIVE = "spindrive"
    THRUSTERS = "thrusters"
    SCREENS = "screens"
    MAIN_GUN = "main_gun"
    FUSION_REACTOR = "fusion_reactor"


class PortMode(Enum):
    """What a port does with a commodity, from the player's point of view.

    BUY = the port *buys* it from the player (the player SELLS into the port);
    SELL = the port *sells* it to the player (the player BUYS from the port).
    Matches the §2 trade-screen `^`/`v` convention.
    """

    BUY = "buy"
    SELL = "sell"


class PortClass(Enum):
    """TW2002 port classes 1–8 (the eight buy/sell triples) plus the StarDock.

    The per-commodity buy/sell pattern of each class lives in `PORT_CLASS_TRADES`.
    """

    CLASS_1 = 1  # BBS
    CLASS_2 = 2  # BSB
    CLASS_3 = 3  # SBB
    CLASS_4 = 4  # SBS
    CLASS_5 = 5  # SSB
    CLASS_6 = 6  # BSS
    CLASS_7 = 7  # SSS
    CLASS_8 = 8  # BBB
    STARDOCK = 9  # sells all goods + hardware emporium (§5)


_B = PortMode.BUY
_S = PortMode.SELL

# Canonical per-commodity trade pattern for each class, in (Fuel Ore, Organics,
# Equipment) order — the classic TW2002 triples. Opposed classes (e.g. CLASS_1
# BBS ↔ CLASS_5 SSB) are what the pair-trade loop and the §5 bigbang "profitable
# pair within 5 hops" validation rely on.
PORT_CLASS_TRADES: dict[PortClass, dict[Commodity, PortMode]] = {
    PortClass.CLASS_1: {Commodity.FUEL_ORE: _B, Commodity.ORGANICS: _B, Commodity.EQUIPMENT: _S},
    PortClass.CLASS_2: {Commodity.FUEL_ORE: _B, Commodity.ORGANICS: _S, Commodity.EQUIPMENT: _B},
    PortClass.CLASS_3: {Commodity.FUEL_ORE: _S, Commodity.ORGANICS: _B, Commodity.EQUIPMENT: _B},
    PortClass.CLASS_4: {Commodity.FUEL_ORE: _S, Commodity.ORGANICS: _B, Commodity.EQUIPMENT: _S},
    PortClass.CLASS_5: {Commodity.FUEL_ORE: _S, Commodity.ORGANICS: _S, Commodity.EQUIPMENT: _B},
    PortClass.CLASS_6: {Commodity.FUEL_ORE: _B, Commodity.ORGANICS: _S, Commodity.EQUIPMENT: _S},
    PortClass.CLASS_7: {Commodity.FUEL_ORE: _S, Commodity.ORGANICS: _S, Commodity.EQUIPMENT: _S},
    PortClass.CLASS_8: {Commodity.FUEL_ORE: _B, Commodity.ORGANICS: _B, Commodity.EQUIPMENT: _B},
    PortClass.STARDOCK: {Commodity.FUEL_ORE: _S, Commodity.ORGANICS: _S, Commodity.EQUIPMENT: _S},
}
