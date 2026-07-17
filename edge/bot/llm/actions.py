"""The LLM pilot's action vocabulary → ordinary game commands (dev-only).

A decision is one flat JSON object (`DECISION_SCHEMA`): a `reasoning` string, an optional
direct `operator_response`, an `action` name from a closed enum, and the handful of
integer/string arguments the actions use. Flat on purpose — small local models fill a flat
schema far more reliably than nested ones. `ActionCatalog.execute` maps a decision onto a
command and applies it through the `BotRunner` seam, so every pilot move is an ordinary
logged, fog-honest command; rules rejections come back as readable failures (the runner
swallows them), never crashes.

Sector arguments are the **display ids** the observation shows (DESIGN §5.1); the catalog
maps them back to internal ids (`resolve_display_id`, or the current sector's warp list).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.text import Text

from edge.bot.runner import BotRunner
from edge.core.enums import Commodity, Component, ComponentTier, Subsystem
from edge.core.rules import (
    BuyAlienTech, BuyComponent, BuyRumor, Colonize, CombatAction, Deposit, Descend, Dock,
    Explore, Hail, InstallComponent, MineBelt, RecruitColonists, Salvage, SwapComponent,
    Trade, TravelTo, Warp, Withdraw,
)

# The closed action vocabulary. Combat actions are legal only during a live encounter;
# everything else only outside one (usage() tells the model which set applies).
_NORMAL_ACTIONS: list[tuple[str, str]] = [
    ("warp", "warp {sector} — jump through an adjacent warp shown in 'Warps out'"
             " (sector -1 takes an uncharted one-way exit)"),
    ("travel_to", "travel_to {sector} — autopilot a multi-hop route to any charted sector"),
    ("dock_trading_port", "dock_trading_port — enter this sector's commodities market for"
                          " trading only"),
    ("dock_stardock", "dock_stardock — enter Stardock facilities: hardware, bank, colonists,"
                      " rumors, and shipyard"),
    ("dock_starbase", "dock_starbase {starbase_id} — board the orbital starbase here"),
    ("trade", "trade {commodity, units} — trade at the docked port; commodity is"
             " fuel_ore / organics / equipment; direction follows the port's BUY/SELL side"),
    ("buy_component", "buy_component {offer_index} — buy indexed hardware at Stardock or a"
                      " boarded friendly starbase"),
    ("install_component", "install_component {subsystem, slot_index, offer_index} — install"
                          " indexed loose hardware in an empty slot, or swap a filled slot"),
    ("deposit", "deposit {count} — bank that many slips at Stardock or a boarded base"),
    ("withdraw", "withdraw {count} — withdraw that many banked slips at a service point"),
    ("buy_rumor", "buy_rumor — buy one fresh lead from the Stardock tavern"),
    ("salvage", "salvage {discovery_id} — collect/log a salvageable discovery here"),
    ("descend", "descend {planet_id} — land on a planet here to survey its surface"),
    ("explore", "explore {planet_id} — reveal the next surface site of a planet you descended on"),
    ("mine_belt", "mine_belt {planet_id} — hand-mine an asteroid belt here for equipment"),
    ("hail", "hail {species_id} — open peaceful contact with an alien ship here"),
    ("buy_tech", "buy_tech {species_id, offer_index} — buy a hailed species' tech offer"),
    ("recruit_colonists", "recruit_colonists {count} — recruit colonists (at the Stardock)"),
    ("colonize", "colonize {planet_id, count} — settle carried colonists, claiming an unowned world"),
    ("wait", "wait — do nothing this cycle (observe / think)"),
    ("stop", "stop — end the run (only when out of options or told to)"),
]
_COMBAT_ACTIONS: list[tuple[str, str]] = [
    ("fight", "fight — fire the main gun this combat round"),
    ("flee", "flee — attempt to escape (see the shown flee chance)"),
    ("launch_missile", "launch_missile — fire one homing missile (finite supply)"),
]

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string",
                      "description": "1-3 short sentences: why this action, ship's-log style"},
        "operator_response": {
            "type": "string",
            "description": ("direct reply to the operator when acknowledging a new objective "
                            "or reporting its completion; empty otherwise"),
        },
        "action": {"type": "string",
                   # `objective_done` is brain-level (it retires the operator's current
                   # objective, `brain.Brain`), so it rides the enum but not the catalog.
                   "enum": [n for n, _ in _NORMAL_ACTIONS + _COMBAT_ACTIONS] + ["objective_done"]},
        "sector": {"type": "integer", "description": "target sector id; 0 when unused"},
        "commodity": {"type": "string",
                      "description": "fuel_ore / organics / equipment; empty when unused"},
        "units": {"type": "integer", "description": "trade units; 0 when unused"},
        "planet_id": {"type": "integer", "description": "0 when unused"},
        "species_id": {"type": "integer", "description": "0 when unused"},
        "discovery_id": {"type": "integer", "description": "0 when unused"},
        "starbase_id": {"type": "integer", "description": "0 when unused"},
        "offer_index": {"type": "integer", "description": "-1 when unused"},
        "subsystem": {"type": "string",
                      "description": "spindrive / thrusters / screens / main_gun; empty when unused"},
        "slot_index": {"type": "integer", "description": "component slot; -1 when unused"},
        "count": {"type": "integer", "description": "0 when unused"},
    },
    # Every field is required: schema-constrained decoding on small local models drops
    # optional properties entirely, so arguments ride as always-present fields with
    # explicit "unused" values instead (the handlers read only their own keys).
    "required": ["reasoning", "operator_response", "action", "sector", "commodity", "units",
                 "planet_id", "species_id", "discovery_id", "starbase_id", "offer_index",
                 "subsystem", "slot_index", "count"],
}

_COMMODITIES = {
    "fuel_ore": Commodity.FUEL_ORE, "fuel ore": Commodity.FUEL_ORE,
    "fuel": Commodity.FUEL_ORE, "ore": Commodity.FUEL_ORE,
    "organics": Commodity.ORGANICS, "org": Commodity.ORGANICS,
    "equipment": Commodity.EQUIPMENT, "equ": Commodity.EQUIPMENT, "equip": Commodity.EQUIPMENT,
}


def _parse_component(label: str) -> tuple[Component, ComponentTier]:
    """Parse the projected loose-part label ``converter (II) x1``."""
    name, _, rest = label.partition(" (")
    tier_name = rest.split(")", 1)[0]
    try:
        return Component(name), ComponentTier[tier_name]
    except (ValueError, KeyError) as exc:
        raise _MissingArg(f"unrecognized loose hardware {label!r}") from exc


@dataclass(frozen=True)
class ActionOutcome:
    """What executing one decision did — readable either way (ok or rejected)."""

    ok: bool
    summary: str


class ActionCatalog:
    """Executes decisions for one pilot, via that pilot's `BotRunner`."""

    def __init__(self, bot: BotRunner) -> None:
        self.bot = bot
        self._boarded_starbase_id: int | None = None
        self._docked_port_sector_id: int | None = None
        self._stardock_facilities_sector_id: int | None = None

    @property
    def boarded_starbase_id(self) -> int | None:
        """The still-present base the pilot explicitly boarded; movement invalidates it."""
        base = self.bot.current_starbase()
        if base is None or base.starbase_id != self._boarded_starbase_id:
            self._boarded_starbase_id = None
        return self._boarded_starbase_id

    @property
    def docked_port_sector_id(self) -> int | None:
        """The sector where this pilot paid the port docking turn, while still there."""
        if self._docked_port_sector_id is None:
            return None
        if self.bot.game().sector.sector_id != self._docked_port_sector_id:
            self._docked_port_sector_id = None
        return self._docked_port_sector_id

    @property
    def stardock_facilities_sector_id(self) -> int | None:
        """The Stardock whose non-market facilities the pilot explicitly entered."""
        if self._stardock_facilities_sector_id is None:
            return None
        if self.bot.game().sector.sector_id != self._stardock_facilities_sector_id:
            self._stardock_facilities_sector_id = None
        return self._stardock_facilities_sector_id

    # --- what the model may do right now ---------------------------------

    def in_combat(self) -> bool:
        return self.bot.service.encounter_view(self.bot.player_id) is not None

    def usage(self) -> str:
        """The context-appropriate action list, one usage line each."""
        if self.in_combat():
            rows = _COMBAT_ACTIONS + [("wait", "wait — hold this round"), ("stop", "stop — end the run")]
        else:
            rows = _NORMAL_ACTIONS
        return "\n".join(f"- {usage}" for _, usage in rows)

    # --- executing a decision ---------------------------------------------

    def execute(self, decision: dict[str, Any]) -> ActionOutcome:
        name = str(decision.get("action", "")).strip()
        combat = name in {n for n, _ in _COMBAT_ACTIONS}
        if self.in_combat() and not combat and name not in ("wait", "stop"):
            return ActionOutcome(False, "you are in combat — only fight / flee / launch_missile work")
        if combat and not self.in_combat():
            return ActionOutcome(False, "no live combat — that action needs an encounter")
        handler = getattr(self, f"_do_{name}", None)
        if handler is None:
            return ActionOutcome(False, f"unknown action {name!r}")
        try:
            outcome: ActionOutcome = handler(decision)
        except _MissingArg as exc:
            return ActionOutcome(False, str(exc))
        return outcome

    def _apply(self, command: Any) -> ActionOutcome:
        events = self.bot.apply(command)
        if not events:
            return ActionOutcome(False, self.bot.last_error or "the command had no effect")
        # describe_event returns TUI-flavored Rich markup; the pilot wants plain prose.
        lines = [Text.from_markup(self.bot.service.describe_event(e)).plain for e in events]
        return ActionOutcome(True, "; ".join(line for line in lines if line) or "done")

    # --- argument plumbing --------------------------------------------------

    @staticmethod
    def _int_arg(decision: dict[str, Any], key: str) -> int:
        value = decision.get(key)
        if not isinstance(value, int):
            raise _MissingArg(f"action needs an integer {key!r} argument")
        return value

    @staticmethod
    def _str_arg(decision: dict[str, Any], key: str) -> str:
        value = decision.get(key)
        if not isinstance(value, str) or not value.strip():
            raise _MissingArg(f"action needs a non-empty string {key!r} argument")
        return value.strip().lower()

    def _internal_sector(self, shown: int) -> int | None:
        return self.bot.service.resolve_display_id(shown)

    def _at_stardock(self) -> bool:
        sector = self.bot.game().sector
        return (self.stardock_facilities_sector_id == sector.sector_id
                and any(port.is_stardock for port in sector.ports))

    def _bank_available(self) -> bool:
        if self._at_stardock():
            return True
        base = self.bot.current_starbase()
        return (base is not None and self.boarded_starbase_id == base.starbase_id
                and "banking" in base.services)

    # --- movement -------------------------------------------------------------

    def _do_warp(self, decision: dict[str, Any]) -> ActionOutcome:
        shown = self._int_arg(decision, "sector")
        warps = self.bot.game().sector.warps
        if shown == -1:  # take the first uncharted one-way exit
            hidden = next((w for w in warps if w.address_hidden), None)
            if hidden is None:
                return ActionOutcome(False, "no uncharted one-way exit here")
            return self._move(Warp(to_sector=hidden.sector_id))
        match = next((w for w in warps if w.display_id == shown), None)
        if match is None:
            return ActionOutcome(False, f"sector {shown} is not an adjacent warp — "
                                        "use travel_to for distant charted sectors")
        return self._move(Warp(to_sector=match.sector_id))

    def _do_travel_to(self, decision: dict[str, Any]) -> ActionOutcome:
        shown = self._int_arg(decision, "sector")
        internal = self._internal_sector(shown)
        if internal is None:
            return ActionOutcome(False, f"no charted sector {shown} — explore toward it first")
        return self._move(TravelTo(to_sector=internal))

    def _move(self, command: Warp | TravelTo) -> ActionOutcome:
        outcome = self._apply(command)
        if outcome.ok:
            self._boarded_starbase_id = None
            self._docked_port_sector_id = None
            self._stardock_facilities_sector_id = None
        return outcome

    # --- port life --------------------------------------------------------------

    def _do_dock_trading_port(self, decision: dict[str, Any]) -> ActionOutcome:
        base = self.bot.current_starbase()
        if base is not None:
            return ActionOutcome(False, f"this port is hosted by starbase_id {base.starbase_id} — "
                                 "use dock_starbase to board it")
        outcome = self._apply(Dock())
        if outcome.ok:
            self._docked_port_sector_id = self.bot.game().sector.sector_id
            self._boarded_starbase_id = None
            self._stardock_facilities_sector_id = None
        return outcome

    def _do_dock_stardock(self, decision: dict[str, Any]) -> ActionOutcome:
        sector = self.bot.game().sector
        if not any(port.is_stardock for port in sector.ports):
            return ActionOutcome(False, "there is no Stardock in this sector")
        outcome = self._apply(Dock())
        if not outcome.ok:
            return outcome
        self._docked_port_sector_id = sector.sector_id
        self._stardock_facilities_sector_id = sector.sector_id
        self._boarded_starbase_id = None
        return ActionOutcome(True, f"{outcome.summary}; entered Stardock facilities — "
                             "hardware, bank, colonists, rumors, and shipyard available")

    def _do_dock_starbase(self, decision: dict[str, Any]) -> ActionOutcome:
        starbase_id = self._int_arg(decision, "starbase_id")
        base = self.bot.current_starbase()
        if base is None or base.starbase_id != starbase_id:
            return ActionOutcome(False, f"starbase_id {starbase_id} is not in this sector")
        self._boarded_starbase_id = starbase_id
        self._docked_port_sector_id = None
        self._stardock_facilities_sector_id = None
        return ActionOutcome(True, f"boarded {base.name} — standing {base.standing}; "
                             f"services: {', '.join(base.services) or 'none'}")

    def _do_trade(self, decision: dict[str, Any]) -> ActionOutcome:
        raw = str(decision.get("commodity", "")).strip().lower()
        commodity = _COMMODITIES.get(raw)
        if commodity is None:
            return ActionOutcome(False, f"unknown commodity {raw!r} — use fuel_ore / organics / equipment")
        units = self._int_arg(decision, "units")
        if units <= 0:
            return ActionOutcome(False, "units must be positive")
        outcome = self._apply(Trade(commodity=commodity, units=units))
        if outcome.ok:
            return outcome
        # A small model loops on bare rejections; spell out the constraint it hit.
        ship = self.bot.game().ship
        hint = f" — free holds {ship.holds_total - ship.holds_used}/{ship.holds_total}"
        port = self.bot.current_port()
        mode = next((c.mode for c in (port.commodities if port else [])
                     if c.name.lower().replace(" ", "_") == commodity.value), None)
        if mode == "SELL":
            hint += (f"; this port only SELLS {commodity.value} — to sell cargo, "
                     "travel to a port that BUYS it (see Known ports)")
        elif mode == "BUY":
            hint += f"; this port only BUYS {commodity.value} (you sell, it pays)"
        elif mode is None:
            hint += f"; this port does not deal in {commodity.value}"
        return ActionOutcome(False, outcome.summary + hint)

    def _do_recruit_colonists(self, decision: dict[str, Any]) -> ActionOutcome:
        if not self._at_stardock():
            return ActionOutcome(False, "colonist recruitment requires docking at Stardock")
        return self._apply(RecruitColonists(count=self._int_arg(decision, "count")))

    def _do_buy_component(self, decision: dict[str, Any]) -> ActionOutcome:
        index = self._int_arg(decision, "offer_index")
        base = self.bot.current_starbase()
        if base is not None and self.boarded_starbase_id == base.starbase_id:
            hardware = base.hardware
        elif self._at_stardock():
            hardware = self.bot.stardock().hardware
        else:
            return ActionOutcome(False, "buy hardware at Stardock or board a friendly starbase")
        if not 0 <= index < len(hardware):
            return ActionOutcome(False, f"no hardware offer_index {index} at this service point")
        item = hardware[index]
        return self._apply(BuyComponent(Component(item.component), ComponentTier[item.tier]))

    def _do_install_component(self, decision: dict[str, Any]) -> ActionOutcome:
        subsystem = self._str_arg(decision, "subsystem")
        try:
            kind = Subsystem(subsystem)
        except ValueError:
            return ActionOutcome(False, f"unknown subsystem {subsystem!r}")
        slot_index = self._int_arg(decision, "slot_index")
        offer_index = self._int_arg(decision, "offer_index")
        room = self.bot.engine_room()
        if not 0 <= offer_index < len(room.on_hand):
            return ActionOutcome(False, f"no loose-hardware offer_index {offer_index}")
        panel = next((panel for panel in room.subsystems
                      if panel.name.lower().replace(" ", "_") == subsystem), None)
        if panel is None or not 0 <= slot_index < len(panel.slots):
            return ActionOutcome(False, f"no slot {slot_index} in {subsystem}")
        component, tier = _parse_component(room.on_hand[offer_index])
        command = (InstallComponent(kind, slot_index, component, tier)
                   if panel.slots[slot_index].state == "empty"
                   else SwapComponent(kind, slot_index, component, tier))
        return self._apply(command)

    def _do_deposit(self, decision: dict[str, Any]) -> ActionOutcome:
        if not self._bank_available():
            return ActionOutcome(False, "banking requires Stardock or a boarded base with banking")
        return self._apply(Deposit(amount=self._positive_count(decision)))

    def _do_withdraw(self, decision: dict[str, Any]) -> ActionOutcome:
        if not self._bank_available():
            return ActionOutcome(False, "banking requires Stardock or a boarded base with banking")
        return self._apply(Withdraw(amount=self._positive_count(decision)))

    def _do_buy_rumor(self, decision: dict[str, Any]) -> ActionOutcome:
        if not self._at_stardock():
            return ActionOutcome(False, "rumors are sold only after docking at Stardock")
        outcome = self._apply(BuyRumor())
        if not outcome.ok:
            return outcome
        leads = self.bot.service.leads_view(self.bot.player_id)
        return ActionOutcome(True, f"{outcome.summary}; new lead: {leads[-1].summary}"
                             if leads else outcome.summary)

    def _positive_count(self, decision: dict[str, Any]) -> int:
        count = self._int_arg(decision, "count")
        if count <= 0:
            raise _MissingArg("action needs a positive 'count' argument")
        return count

    # --- exploration ---------------------------------------------------------------

    def _do_salvage(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(Salvage(discovery_id=self._int_arg(decision, "discovery_id")))

    def _do_descend(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(Descend(planet_id=self._int_arg(decision, "planet_id")))

    def _do_explore(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(Explore(planet_id=self._int_arg(decision, "planet_id")))

    def _do_mine_belt(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(MineBelt(planet_id=self._int_arg(decision, "planet_id")))

    def _do_colonize(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(Colonize(planet_id=self._int_arg(decision, "planet_id"),
                                    colonists=self._int_arg(decision, "count")))

    # --- aliens ------------------------------------------------------------------------

    def _do_hail(self, decision: dict[str, Any]) -> ActionOutcome:
        outcome = self._apply(Hail(species_id=self._int_arg(decision, "species_id")))
        if not outcome.ok:
            return outcome
        contact = self.bot.service.current_contact_view(self.bot.player_id)
        if contact is None:
            return outcome
        offers = "; ".join(
            f"offer_index {o.index}: {o.label} ({o.mode} {o.price or o.barter_cost})"
            for o in contact.offers if o.available) or "none available"
        return ActionOutcome(True, f'{contact.species} ({contact.standing}): "{contact.opener}"'
                                   f" — tech offers: {offers}")

    def _do_buy_tech(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(BuyAlienTech(species_id=self._int_arg(decision, "species_id"),
                                        offer_index=self._int_arg(decision, "offer_index")))

    # --- combat ------------------------------------------------------------------------

    def _do_fight(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(CombatAction(action="fight"))

    def _do_flee(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(CombatAction(action="flee"))

    def _do_launch_missile(self, decision: dict[str, Any]) -> ActionOutcome:
        return self._apply(CombatAction(action="launch_missile"))

    # --- meta -------------------------------------------------------------------------

    def _do_wait(self, decision: dict[str, Any]) -> ActionOutcome:
        return ActionOutcome(True, "holding position")

    def _do_stop(self, decision: dict[str, Any]) -> ActionOutcome:
        return ActionOutcome(True, "pilot chose to end the run")


class _MissingArg(ValueError):
    """A decision omitted (or mistyped) a required argument."""
