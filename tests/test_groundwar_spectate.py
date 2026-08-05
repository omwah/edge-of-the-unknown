"""GW-WP22 — the bot pilot drives the production assault screen inside `edge-groundwar`.

The point of the pilot is that it is *not* a simulation: one `GameService`, the
production reducers, and the unmodified `GroundAssaultScreen`. These tests hold that
line — that the bot's commands reach the same state the screen renders, that the screen
crosses the pre-drop/post-drop boundary the bot jumps over, and that a decided operation
freezes on the board instead of being extracted out from under the viewer.
"""

from __future__ import annotations

import pytest

from edge.config import load_default_config
from edge.groundwar import harness
from edge.groundwar.app import GroundwarApp, SetupScreen
from edge.groundwar.spectate import BotDriver, Scenario, describe_command
from edge.tui.composer import PlatoonComposer
from edge.tui.screens.ground_assault import GroundAssaultScreen

CFG = load_default_config()
SCENARIO = Scenario(seed=7, citadel_level=0, habitability_cap=6_000,
                    loadout=(("marauder", 3), ("scout", 1), ("command", 1)))


def _driver(scenario: Scenario = SCENARIO) -> BotDriver:
    return BotDriver.for_scenario(scenario, CFG)


def test_scenario_opens_a_live_operation() -> None:
    """The driver must be handed a world with the operation already open — the screen
    expects to arrive at one, exactly as `PlanetScreen` hands off."""
    operation = _driver().operation()
    assert operation is not None
    assert operation.outcome is None
    assert not operation.dropped
    assert operation.resolve > operation.surrender_threshold


async def test_bot_actions_move_the_screen() -> None:
    """The load-bearing claim: the bot drives the service, and the *unmodified* screen
    reflects it. If `observe` ever stops working this fails, not a snapshot."""
    bot = _driver()
    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)) as pilot:
        app.client = bot.client
        app.push_screen(GroundAssaultScreen(bot.client))
        await pilot.pause()  # let the pushed screen mount and pull its first view
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        for _ in range(40):
            await bot.advance(screen)
            if bot.finished:
                break
        operation = bot.operation()
        assert operation is not None
        assert operation.dropped, "the bot never landed its platoon"
        assert bot.steps > 0
        # The screen's own projection agrees with the state the bot mutated — this is
        # what proves there is one service and not two drifting copies.
        assert screen.view is not None
        assert screen.view.dropped
        assert len(screen.view.troopers) == sum(count for _, count in SCENARIO.loadout)


async def test_the_drop_recomposes_from_chooser_to_map() -> None:
    """`compose` serves a squad chooser before the drop and the map after it. A bot's
    `GroundDrop` crosses that boundary without the screen's placement flow running, so
    `observe` has to recompose — otherwise the viewer watches a stale chooser."""
    bot = _driver()
    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)) as pilot:
        app.client = bot.client
        app.push_screen(GroundAssaultScreen(bot.client))
        await pilot.pause()  # let the pushed screen mount and pull its first view
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        assert screen.view is not None and not screen.view.dropped
        for _ in range(40):
            await bot.advance(screen)
            if screen.view is not None and screen.view.dropped:
                break
        assert screen.view is not None and screen.view.dropped
        assert screen.query("AssaultMapView"), "the map never replaced the squad chooser"


async def test_a_decided_operation_freezes_on_the_board() -> None:
    """The bot's move after an outcome is `ExtractGroundOperation`, which pops the
    screen. The pilot must stop first and leave the evidence up."""
    bot = _driver()
    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)) as pilot:
        app.client = bot.client
        app.push_screen(GroundAssaultScreen(bot.client))
        await pilot.pause()  # let the pushed screen mount and pull its first view
        screen = app.screen
        assert isinstance(screen, GroundAssaultScreen)
        for _ in range(600):
            await bot.advance(screen)
            if bot.finished:
                break
        assert bot.finished, "the run never reached a decision inside the step budget"
        assert not bot.running
        operation = bot.operation()
        assert operation is not None, "the operation was extracted out from under the view"
        assert operation.outcome is not None


def test_pace_controls_stay_within_bounds() -> None:
    bot = _driver()
    for _ in range(40):
        bot.faster()
    assert bot.pace >= 0.05
    for _ in range(60):
        bot.slower()
    assert bot.pace <= 4.0


def test_status_line_reports_the_diagnostic_numbers() -> None:
    """The subtitle is where a viewer reads the balance question: how much clock is
    left, how far Resolve still has to fall, and how far the objective still is."""
    line = _driver().status_line()
    assert "turn" in line and "resolve" in line and "alive" in line


def test_distance_to_objective_is_none_before_the_drop() -> None:
    assert _driver().distance_to_objective() is None


@pytest.mark.parametrize("scenario", [
    SCENARIO,
    Scenario(seed=11, cloud_city_size=2, citadel_level=1),
])
def test_both_topologies_build(scenario: Scenario) -> None:
    """Cloud City is the branch WP16 never tuned, so it must be watchable too."""
    bot = BotDriver.for_scenario(scenario, CFG)
    operation = bot.operation()
    assert operation is not None
    assert bot.service.state.players[harness.PLAYER_ID].ground_operation is operation


def test_describe_command_names_the_decision() -> None:
    """The log line is the only place a viewer sees *why* the board changed."""
    from edge.core.rules import GroundFire

    line = describe_command(GroundFire(operation_id=1, actor_id=3, x=40, y=12))
    assert "GroundFire" in line and "actor=3" in line and "x=40" in line


# --- integration with the playtest shell it now lives in ------------------------


async def test_setup_screen_offers_a_pilot_toggle() -> None:
    """The pilot is a mode of `edge-groundwar`, not a second program — so the choice
    has to be on the setup screen next to the other scenario knobs."""
    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.screen
        assert isinstance(screen, SetupScreen)
        assert not screen.bot_pilot
        await pilot.click("#pilot")
        assert screen.bot_pilot
        assert "bot" in str(screen.query_one("#pilot").label)


async def test_bot_controls_are_inert_without_a_pilot() -> None:
    """A human playing the same shell must not have the spectator keys do anything."""
    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)):
        assert app.bot is None
        app.action_toggle_bot()
        await app.action_step_bot()
        app.action_bot_faster()
        assert app.bot is None


@pytest.mark.parametrize("mode", ["assault", "cloud_city"])
async def test_launching_with_the_bot_pilot_starts_a_watched_run(mode: str) -> None:
    """The whole user path in one test: pick the pilot on the setup screen, commit a
    squad, and end up watching the production assault screen fight itself.

    Parametrized over both topologies because GW-WP16 shipped the Cloud City assault
    but left this shell preview-only — a station could not be played *or* watched here,
    and its balance is the less tuned of the two.
    """
    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)) as pilot:
        setup = app.screen
        assert isinstance(setup, SetupScreen)
        setup.mode = mode
        setup.bot_pilot = True
        setup._update()
        setup.post_message(PlatoonComposer.Dropped({"marauder": 2, "command": 1}))
        await pilot.pause()
        assert isinstance(app.screen, GroundAssaultScreen)
        assert app.bot is not None and app.bot.running
        # Not `== 1`: the run auto-starts, so its own interval timer may already have
        # taken a step by the time this line runs. That it advances at all is the claim.
        before = app.bot.steps
        await app.advance_bot()
        assert app.bot.steps > before
        assert app.bot.operation() is not None


async def test_a_stale_bot_does_not_survive_into_a_new_run() -> None:
    """Escaping a bot-piloted run early must not leave a live bot behind to crash the
    next one.

    `action_extract` (Escape) clears the operation straight through the shared client,
    never touching `BotDriver` — so a bot backed out of mid-run is left `running=True`,
    `finished=False`, with no operation of its own. Before this fix, starting a *second*,
    human-piloted run left that orphaned bot attached: its timer kept ticking against the
    new screen (any `GroundAssaultScreen` passes `advance_bot`'s check), `drive()` saw its
    own `op is None`, tried to open a fresh assault, and called `b.game()` — which crashes
    because the harness's throwaway single-sector state never populates `state.regions`.
    """
    from edge.core.rules import ExtractGroundOperation

    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)) as pilot:
        setup = app.screen
        assert isinstance(setup, SetupScreen)
        setup.bot_pilot = True
        setup._update()
        setup.post_message(PlatoonComposer.Dropped({"marauder": 2, "command": 1}))
        await pilot.pause()
        assert isinstance(app.screen, GroundAssaultScreen)
        bot = app.bot
        assert bot is not None and bot.running and not bot.finished

        # Escape out mid-run, exactly as `action_extract` does: clear the operation
        # through the shared client, then pop back to setup — without telling the bot.
        operation = bot.operation()
        assert operation is not None
        await bot.client.apply(ExtractGroundOperation(operation.operation_id))
        app.pop_screen()
        assert app.bot is bot and bot.running and not bot.finished
        assert bot.operation() is None

        # Now play a second, human-piloted run.
        setup2 = app.screen
        assert isinstance(setup2, SetupScreen)
        setup2.bot_pilot = False
        setup2._update()
        setup2.post_message(PlatoonComposer.Dropped({"marauder": 2, "command": 1}))
        await pilot.pause()
        assert isinstance(app.screen, GroundAssaultScreen)
        assert app.bot is None, "the orphaned bot must be detached before a new run starts"

        # The orphaned bot's timer (if it survived) would have crashed on its next tick —
        # advancing here is what a background tick would have done.
        await app.advance_bot()


async def test_start_bot_pilot_attaches_and_advances() -> None:
    """`start_bot_pilot` is what the setup screen calls after pushing the screen."""
    bot_world = _driver()
    app = GroundwarApp(CFG)
    async with app.run_test(size=(120, 40)) as pilot:
        app.client = bot_world.client
        app.push_screen(GroundAssaultScreen(bot_world.client))
        await pilot.pause()
        app.start_bot_pilot(bot_world.client, "test scenario")
        assert app.bot is not None and app.bot.running
        await app.advance_bot()
        assert app.bot.steps == 1
        app.action_toggle_bot()
        assert not app.bot.running
