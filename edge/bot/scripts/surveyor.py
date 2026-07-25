"""Example bot: descends onto a landable world and excavates its surface sites (GW-WP13).

Demonstrates driving a ground-survey operation end to end through the public service
surface: pick the nearest Survey-access planet, land, walk to and dig every eligible
site, talk to a settlement to resupply when out of supplies, extract once nothing is
left to find. Reads `bot.service.state`/`bot.service.config` directly (the trusted,
sanctioned bot accessor, `ServiceProtocol`) rather than parsing DTOs, matching how the
core groundwar layer itself works. Run with:

    edge-bot --script edge/bot/scripts/surveyor.py --save /tmp/survey.db
"""

from __future__ import annotations

from edge.bot.runner import BotRunner
from edge.core.config import GameConfig
from edge.core.groundwar.access import Survey, ground_access
from edge.core.groundwar.models import SurveyOperation
from edge.core.groundwar.survey import landing_sites, settlement_at, survey_map_for
from edge.core.models import Planet, UniverseState
from edge.core.planets import is_cloud_city_world
from edge.core.rules import (
    BeginSurvey, CombatAction, ExtractGroundOperation, GroundMove, SurveyDig, SurveyLand,
    SurveyTalk, TravelTo, Warp,
)

_STUCK_LIMIT = 3  # consecutive no-progress ticks on one world before bailing


def _pick_planet(state: UniverseState, player_id: int, config: GameConfig) -> Planet | None:
    """A Survey-access world in already-charted space, with something left to find.

    `TravelTo` is route-locked to charted space (checked here before the more expensive
    `ground_access` call), and a world every discovery of which has already been logged
    is excluded — otherwise the bot would re-land on a fully excavated world forever
    (nothing about `ground_access` itself tracks exhaustion, only real state does). A
    Cloud City is excluded outright even when it happens to hold an unclaimed `Discovery`
    row (a bare/staged jovian can from the general `is_landable` surface-site roll,
    GW-WP17): `eligible_surface_site_ids` never surfaces one there regardless, so the
    world would otherwise look "has something to find" and never actually yield it.
    """
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    known = player.explored_sectors | {ship.sector_id}
    open_planet_ids = {
        d.planet_id for d in state.discoveries.values()
        if d.planet_id is not None and d.found_by is None
    }
    candidates = [
        planet for planet in state.planets.values()
        if planet.sector_id in known and planet.id in open_planet_ids
        and not is_cloud_city_world(planet.planet_type, config)
        and isinstance(ground_access(state, player, planet, config), Survey)
    ]
    return min(candidates, key=lambda p: p.id) if candidates else None


def setup(bot: BotRunner) -> None:
    # Per-bot progress tracker, local to this `setup` call (closed over, not a module-level
    # dict) so several surveyors in a `BotSwarm` never share state with each other.
    stuck_key: tuple[int, int, int, int] | None = None
    stuck_count = 0

    @bot.each_turn
    def drive(b: BotRunner) -> None:
        nonlocal stuck_key, stuck_count
        if b.service.encounter_view(b.player_id) is not None:
            b.apply(CombatAction(action="flee"))
            return
        state = b.service.state
        config = b.service.config
        player = state.players[b.player_id]
        op = player.ground_operation

        if op is None:
            if b.game().turns < 1:
                b.stop()
                return
            planet = _pick_planet(state, b.player_id, config)
            if planet is None:
                # Nothing eligible charted yet — push into unexplored space (explorer.py's idiom).
                g = b.game()
                warps = g.sector.warps
                if not warps:
                    b.stop()
                    return
                target = next((w for w in warps if w.kind == "unexplored"), warps[0])
                if not b.apply(Warp(to_sector=target.sector_id)):
                    b.stop()
                return
            ship = state.ships[player.ship_id]
            if ship.sector_id != planet.sector_id:
                if not b.apply(TravelTo(to_sector=planet.sector_id)):
                    b.stop()
                return
            b.apply(BeginSurvey(planet.id))
            return

        if not isinstance(op, SurveyOperation):
            b.stop()  # an assault op landed on this player — not this script's job
            return

        smap = survey_map_for(state, op, config)

        if not op.landed:
            sites = landing_sites(smap, config)
            if not sites:
                b.apply(ExtractGroundOperation(op.operation_id))
                return
            x, y = min(sites)
            b.apply(SurveyLand(op.operation_id, x, y))
            return

        key = (op.operation_id, op.explorer_x, op.explorer_y, op.supplies)
        if stuck_key == key:
            stuck_count += 1
        else:
            stuck_key, stuck_count = key, 0
        if stuck_count >= _STUCK_LIMIT:
            b.apply(ExtractGroundOperation(op.operation_id))
            return

        unfound = [
            s for s in smap.sites
            if s.discovery_id in op.visible_discovery_ids
            and s.discovery_id not in op.resolved_discovery_ids
        ]
        if not unfound:
            b.apply(ExtractGroundOperation(op.operation_id))
            return

        target = min(unfound, key=lambda s: abs(s.x - op.explorer_x) + abs(s.y - op.explorer_y))
        if (op.explorer_x, op.explorer_y) == (target.x, target.y):
            b.apply(SurveyDig(op.operation_id))
            return

        settlement = settlement_at(smap, op.explorer_x, op.explorer_y)
        if op.supplies <= 0:
            if settlement is not None:
                b.apply(SurveyTalk(op.operation_id))
            else:
                b.apply(ExtractGroundOperation(op.operation_id))  # stranded, no supplies
            return

        if not b.apply(GroundMove(op.operation_id, target.x, target.y)):
            b.apply(ExtractGroundOperation(op.operation_id))
