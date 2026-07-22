"""WP7 — friendly alien species & roster (DESIGN §6, §13).

Covers the pure-core disposition helpers, the roster's reference-integrity validation,
and the big-bang placement invariants (seeded subset, friendly-band clamp, per-band
contact) — plus the determinism guard that species placement does not perturb the
Phase-1 port/planet draws.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from edge.bigbang.aliens import _seed_grudges
from edge.bigbang.generator import generate
from helpers import generate_with_player
from edge.config import load_default_config
from edge.core.aliens import (
    FRIENDLY,
    HOSTILE,
    NEUTRAL,
    apply_spillover,
    attitude_locked,
    disposition_band,
    effective_disposition,
    grudge_shift,
    is_friendly,
    may_occupy,
    npc_stance,
    sour_attitude,
    species_relation,
)
from edge.core.config import GameConfig, RosterConfig
from edge.core.enums import PortClass
from edge.core.events import CoreLawNotice, GrudgeFormed
from edge.core.models import (
    AlienSpecies,
    Encounter,
    EncounterFoe,
    Game,
    Grudge,
    Ownership,
    Planet,
    Player,
    Sector,
    UniverseState,
)
from edge.core.movement import shortest_path
from edge.core.rules import CombatAction, Salvage, Warp, _raise_attitude, apply_result, reduce
from edge.engine.cron import daily_turn_reset

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 80})})
# A larger universe reaches the Deep/Void bands (the 80-sector one stops at Frontier).
WIDE = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 400})})


def _species(sid: int = 1, base: float = 0.7) -> AlienSpecies:
    return AlienSpecies(
        id=sid, roster_id="x", name="X", archetype_id="a", sector_id=11, home_band="Hub",
        tech_level=5, base_disposition=base, disposition_center=base, disposition_variance=0.1,
    )


def _player(attitudes: dict[str, float] | None = None) -> Player:
    return Player(id=1, name="P", ship_id=1, latinum=0, species_attitudes=attitudes or {})


# --- disposition helpers (pure core) ---------------------------------------------

def test_effective_disposition_applies_offset_and_clamps() -> None:
    sp = _species(base=0.7)
    assert effective_disposition(sp, _player()) == pytest.approx(0.7)  # no offset yet
    assert effective_disposition(sp, _player({"x": 0.2})) == pytest.approx(0.9)
    # Clamped to [0, 1] at both ends.
    assert effective_disposition(sp, _player({"x": 0.9})) == pytest.approx(1.0)
    assert effective_disposition(sp, _player({"x": -2.0})) == pytest.approx(0.0)


def test_disposition_band_thresholds() -> None:
    aliens = CFG.aliens  # hostility 0.35 / amity 0.65
    assert disposition_band(0.1, aliens) == HOSTILE
    assert disposition_band(0.5, aliens) == NEUTRAL
    assert disposition_band(0.65, aliens) == FRIENDLY  # amity is inclusive
    assert is_friendly(0.8, aliens) and not is_friendly(0.5, aliens)


# --- roster reference integrity (fails fast at config validation) ----------------

def _roster_mapping(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "core_governing_alliance_id": 1,
        "alliances": [{"id": 1, "name": "Fed"}],
        "species": [{"id": "a", "name": "A", "archetype_id": "x", "disposition_center": 0.8}],
    }
    base.update(overrides)
    return base


def test_roster_validates_minimal() -> None:
    RosterConfig.model_validate(_roster_mapping())


def test_roster_rejects_unknown_governing_alliance() -> None:
    with pytest.raises(ValidationError, match="core_governing_alliance_id"):
        RosterConfig.model_validate(_roster_mapping(core_governing_alliance_id=9))


def test_roster_rejects_unknown_species_alliance() -> None:
    species = [{"id": "a", "name": "A", "archetype_id": "x",
                "disposition_center": 0.8, "alliance_id": 99}]
    with pytest.raises(ValidationError, match="unknown alliance"):
        RosterConfig.model_validate(_roster_mapping(species=species))


def test_roster_rejects_unknown_signature_hook() -> None:
    species = [{"id": "a", "name": "A", "archetype_id": "x", "disposition_center": 0.8,
                "signature_mechanic": {"hook": "not_a_hook"}}]
    with pytest.raises(ValidationError, match="unknown signature hook"):
        RosterConfig.model_validate(_roster_mapping(species=species))


def test_roster_rejects_duplicate_species_id() -> None:
    species = [
        {"id": "a", "name": "A", "archetype_id": "x", "disposition_center": 0.8},
        {"id": "a", "name": "B", "archetype_id": "y", "disposition_center": 0.7},
    ]
    with pytest.raises(ValidationError, match="duplicate species id"):
        RosterConfig.model_validate(_roster_mapping(species=species))


def test_default_roster_is_complete() -> None:
    roster = CFG.roster
    assert roster is not None
    assert roster.core_governing_alliance_id == 1
    assert len(roster.species) >= 10  # a full pool to draw a subset from
    for sp in roster.species:
        # Every species carries a programmatic flavour blurb (dossier/codex narration).
        assert sp.description.strip()
        # Every species' tech-offer tier is a valid ComponentTier name.
        for offer in sp.tech_offers:
            assert offer.tier in {"I", "II", "III"}


# --- big-bang placement invariants -----------------------------------------------

def test_placement_is_seeded_and_deterministic() -> None:
    a = generate(SMALL, 42)
    b = generate(SMALL, 42)
    assert {sid: sp for sid, sp in a.species.items()} == b.species
    # A different seed draws a different placement (subset and/or sectors).
    c = generate(SMALL, 43)
    assert (a.species != c.species) or (len(a.species) != len(c.species))


@pytest.mark.parametrize("seed", range(30))
def test_hub_peaceable_and_placement_outside_core(seed: int) -> None:
    """Band-graded placement (§5/§6): the Hub is peaceable (every innermost-band species
    friendly) and only the governor + Stardock sit in Core Space. Hostiles are allowed —
    and expected — in the outer bands (asserted separately)."""
    state = generate(WIDE, seed)
    assert state.species  # the default roster always places some
    gov = state.game.core_governing_alliance_id
    core = {s.id for s in state.sectors.values() if s.is_galactic_core}
    dock_sector = next(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    innermost = WIDE.bigbang.active_bands()[0].name
    for sp in state.species.values():
        if state.sectors[sp.sector_id].distance_band == innermost:
            assert is_friendly(sp.base_disposition, CFG.aliens)  # Hub stays peaceable
        # No Core placement except the Stardock hub and the governor's own members,
        # who inhabit their capital (WP18, §6.3).
        if sp.sector_id in core:
            assert sp.sector_id == dock_sector or sp.alliance_id == gov
        assert sp.alliance_id is None or sp.alliance_id in state.alliances


def test_outer_bands_spawn_hostiles() -> None:
    """Danger returns to the frontier: across seeds, unaligned raider kinds appear hostile
    in the outer bands — and never in the Hub. (Bloc members stay friendly; a bloc's menace
    is political, activated by alliance standing, §5/§6.3 — so baseline hostiles are the
    unaligned raiders, present in most but not every universe.)"""
    innermost = WIDE.bigbang.active_bands()[0].name  # the Hub
    seeds_with_hostiles = 0
    for seed in range(20):
        state = generate(WIDE, seed)
        hostiles = [
            sp for sp in state.species.values()
            if disposition_band(sp.base_disposition, CFG.aliens) == HOSTILE
        ]
        if hostiles:
            seeds_with_hostiles += 1
            # Hostiles must never sit in the peaceable Hub
            assert not any(state.sectors[sp.sector_id].distance_band == innermost for sp in hostiles)
    assert seeds_with_hostiles >= 10  # the raider kinds surface in most universes


def test_mean_disposition_falls_outward_in_aggregate() -> None:
    """The §13 gradient: aggregated over many seeds at full scale, mean disposition per
    band is non-increasing outward (per-seed it is noisy — the mandated friendly anchor
    plus small samples — so this is a suite-level property, not a per-universe invariant)."""
    from collections import defaultdict
    from statistics import mean

    order = [b.name for b in CFG.bigbang.active_bands()]
    by_band: dict[str, list[float]] = defaultdict(list)
    for seed in range(30):
        state = generate(CFG, seed)  # 1000-sector default (expansive) reaches all bands
        seen: set[str] = set()
        for sp in state.species.values():
            if sp.roster_id in seen:  # one value per kind (ships share a base)
                continue
            seen.add(sp.roster_id)
            by_band[state.sectors[sp.sector_id].distance_band].append(sp.base_disposition)
    means = [mean(by_band[b]) for b in order if by_band[b]]
    assert len(means) == 4, f"expected all four bands populated, got {len(means)}"
    tol = CFG.aliens.disposition_gradient_tolerance
    assert all(a + tol >= b for a, b in zip(means, means[1:])), f"not non-increasing (tol={tol}): {means}"


@pytest.mark.parametrize("seed", range(30))
def test_stardock_hosts_at_least_two_core_welcome_species(seed: int) -> None:
    """The high-traffic hub always greets a new player with ≥2 distinct friendly species."""
    state = generate(WIDE, seed)
    dock_sector = next(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    gov = state.game.core_governing_alliance_id
    at_dock = [sp for sp in state.species.values() if sp.sector_id == dock_sector]
    assert len({sp.roster_id for sp in at_dock}) >= CFG.roster.stardock_contacts  # type: ignore[union-attr]
    for sp in at_dock:
        assert sp.alliance_id in (gov, None)  # Core-welcome: governor's own or unaligned
        assert is_friendly(sp.base_disposition, CFG.aliens)


def test_species_field_home_clusters_within_radius() -> None:
    """A drawn species is met as a *cluster* of ships near its home, not a lone contact.

    Checked on rival-bloc kinds (aligned, non-governor): they are never staged at the
    Stardock or in the Core, so all their ships form a single BFS cluster around the home.
    """
    from collections import defaultdict

    from edge.bigbang.topology import bfs_distances

    radius = CFG.roster.home_cluster_radius  # type: ignore[union-attr]
    checked = 0
    for seed in range(10):
        state = generate(WIDE, seed)
        gov = state.game.core_governing_alliance_id
        by_kind: dict[str, list] = defaultdict(list)
        for sp in sorted(state.species.values(), key=lambda s: s.id):
            by_kind[sp.roster_id].append(sp)
        for ships in by_kind.values():
            home = ships[0]  # lowest id = a band home (placed before the WP23 home cluster)
            if home.alliance_id in (None, gov) or len(ships) < 2:
                continue
            # The band home is met as a *cluster*: at least one satellite sits within radius.
            # (A bloc kind also holds a separate home cluster now, so not *every* ship is near.)
            dist = bfs_distances(state.adjacency, home.sector_id)
            assert sum(1 for s in ships if dist.get(s.sector_id, 10**9) <= radius) >= 2
            checked += 1
    assert checked  # at least one multi-ship cluster was verified


def test_core_bustles_with_governing_traffic() -> None:
    """The Core is busy with governing-alliance traffic — several ships, all governor's own."""
    state = generate(WIDE, 1)
    gov = state.game.core_governing_alliance_id
    core_ids = {i for i, s in state.sectors.items() if s.is_galactic_core}
    core_ships = [s for s in state.species.values() if s.sector_id in core_ids]
    assert len(core_ships) >= CFG.roster.core_traffic  # type: ignore[union-attr]
    assert all(s.alliance_id == gov for s in core_ships)  # Core barred to non-governor


@pytest.mark.parametrize("seed", range(30))
def test_every_live_band_has_a_contact(seed: int) -> None:
    state = generate(WIDE, seed)
    contact_bands = {state.sectors[sp.sector_id].distance_band for sp in state.species.values()}
    live_bands = {
        s.distance_band for s in state.sectors.values() if not s.is_galactic_core
    }
    assert live_bands <= contact_bands  # every non-empty band has at least one alien


def test_roster_alliances_become_entities() -> None:
    state = generate(SMALL, 1)
    assert state.alliances[1].name == "Terran Federation"
    assert {a.id for a in CFG.roster.alliances} == set(state.alliances)  # type: ignore[union-attr]
    assert any(a.covets_core for a in state.alliances.values())  # the Liberty Front


def test_species_placement_does_not_perturb_ports_or_planets() -> None:
    """The species sub-RNG must not shift the Phase-1 port/planet draws (golden-master)."""
    from dataclasses import replace

    from edge.core.models import Ownership

    no_roster = SMALL.model_copy(update={"roster": None})
    with_roster = SMALL
    a = generate(no_roster, 7)
    b = generate(with_roster, 7)
    # Builder archetypes are assigned after species-controlled regions exist; all
    # economic/generated port fields remain identical.
    def strip_port_archetype(ports):  # type: ignore[no-untyped-def]
        return {pid: replace(port, archetype_id="") for pid, port in ports.items()}
    assert strip_port_archetype(a.ports) == strip_port_archetype(b.ports)
    # Home-cluster carving overlays alliance ownership on some planets (WP23), and the
    # inhabited-universe pass overlays peoples, populations and their holdings on top
    # (GW-WP09-PRE) — both run *after* the planet draw and only where a roster exists.
    # GW-WP09 adds a persistent ground garrison, seeded off the same rng _settle already
    # draws from — another roster-only overlay, not a Phase-1 planet-generation draw.
    # The planet *generation* itself (positions, types, habitability, yields) is what
    # must be unperturbed, so compare with those overlays stripped.
    def strip(ps):  # type: ignore[no-untyped-def]
        return {pid: replace(p, owner=Ownership(), population={},
                             stores={}, allocation={}, citadel_level=0,
                             gun_integrity=0, treasury=0,
                             garrison_infantry=0, garrison_armor=0)
                for pid, p in ps.items()}
    assert strip(a.planets) == strip(b.planets)
    assert not a.species and b.species  # only the alien layer differs


def test_no_roster_falls_back_to_federation_stub() -> None:
    state = generate_with_player(SMALL.model_copy(update={"roster": None}), 1)
    assert state.alliances == {1: type(state.alliances[1])(id=1, name="Federation")}
    assert not state.species
    assert state.players[1].alliance_id == 1


def test_config_roundtrips_with_roster() -> None:
    data = CFG.model_dump()
    assert GameConfig.from_mapping(data).roster == CFG.roster


def test_roster_lookup_helpers() -> None:
    roster = CFG.roster
    assert roster is not None
    assert roster.alliance(1) is not None and roster.alliance(1).name == "Terran Federation"
    assert roster.alliance(999) is None
    assert roster.species_by_id("vesk") is not None
    assert roster.species_by_id("nope") is None


# --- WP16: territory validity (may_occupy) ---


def _occupy_state() -> UniverseState:
    """A tiny world: a Core sector, an empty sector, a rival-owned and an own-owned one."""
    game = Game(1, 1, 1, "t", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors = {
        1: Sector(1, 1, (), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (), "Frontier"),  # empty / neutral
        3: Sector(3, 1, (), "Frontier"),  # holds a rival-alliance planet (bloc 9)
        4: Sector(4, 1, (), "Frontier"),  # holds the species' own-alliance planet (bloc 2)
        5: Sector(5, 1, (), "Frontier"),  # holds an unowned planet
    }
    state.planets = {
        1: Planet(1, 3, "Rival", "barren", owner=Ownership("alliance", 9)),
        2: Planet(2, 4, "Home", "barren", owner=Ownership("alliance", 2)),
        3: Planet(3, 5, "Free", "barren", owner=Ownership("none")),
    }
    return state


def _occupy_species() -> AlienSpecies:
    return AlienSpecies(
        id=1, roster_id="x", name="X", archetype_id="a", sector_id=2, home_band="Frontier",
        tech_level=5, base_disposition=0.7, disposition_center=0.7, disposition_variance=0.1,
        alliance_id=2,
    )


def test_may_occupy_bars_the_core_except_for_the_governor() -> None:
    from dataclasses import replace

    state, sp = _occupy_state(), _occupy_species()  # sp is alliance 2; the Core governor is 1
    assert not may_occupy(state, sp, 1, CFG.aliens)  # a non-governor may not enter the Core
    governor = replace(sp, alliance_id=state.game.core_governing_alliance_id)
    assert may_occupy(state, governor, 1, CFG.aliens)  # the governor's own may roam it (WP18)


def test_may_occupy_bars_rival_territory_allows_neutral_and_own() -> None:
    state, sp = _occupy_state(), _occupy_species()
    assert may_occupy(state, sp, 2, CFG.aliens)  # empty/neutral
    assert not may_occupy(state, sp, 3, CFG.aliens)  # rival bloc's holding
    assert may_occupy(state, sp, 4, CFG.aliens)  # the species' own holding
    assert may_occupy(state, sp, 5, CFG.aliens)  # unowned planet is fine


# --- WP18: Federation humanoid_diplomat roster content ---


def test_federation_members_are_humanoid_diplomats_at_top_of_band() -> None:
    roster = CFG.roster
    assert roster is not None
    gov = roster.core_governing_alliance_id
    members = [s for s in roster.species if s.alliance_id == gov]
    assert members, "the governing alliance must field its own people (WP18)"
    assert any(s.alliance_role == "leader" for s in members)  # a founding leader exists
    roles = {s.alliance_role for s in members}
    assert roles <= {"leader", "member"}
    for sp in members:
        assert sp.alliance_id in {a.id for a in roster.alliances}
        assert sp.archetype_id == "humanoid_diplomat"
        assert sp.persona == "humanoid_diplomat"
        # 100% friendly by construction: even the low end of the spread stays in amity.
        assert sp.disposition_center - sp.disposition_variance >= CFG.aliens.amity_threshold


def test_humanoid_diplomat_persona_passes_dialogue_integrity() -> None:
    from edge.dialogue import validate_dialogue

    assert CFG.roster is not None
    assert "humanoid_diplomat" in CFG.roster.personas
    validate_dialogue(CFG.roster)  # raises on any unfillable/blank context


@pytest.mark.parametrize("seed", range(20))
def test_governing_alliance_inhabits_the_core(seed: int) -> None:
    """≥1 governing-alliance member is settled in the Core; no rival/unaligned is (WP18)."""
    state = generate(WIDE, seed)
    gov = state.game.core_governing_alliance_id
    core = {s.id for s in state.sectors.values() if s.is_galactic_core}
    dock_sector = next(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    in_core = [sp for sp in state.species.values() if sp.sector_id in core]
    gov_in_core = [sp for sp in in_core if sp.alliance_id == gov]
    assert gov_in_core  # the Federation inhabits its own capital
    assert any(sp.alliance_role == "leader" for sp in gov_in_core)  # incl. the founding leader
    # The only non-governor in the Core is a Stardock greeter; no rival/unaligned drifts in.
    for sp in in_core:
        assert sp.alliance_id == gov or sp.sector_id == dock_sector


# --- WP27: consequences — souring, grudges, alignment, Core law -------------------


def _quill_state(seed: int = 3):
    """A fresh game plus one hand-placed quill kind in the player's sector."""
    state = generate_with_player(SMALL, seed)
    ship = state.ships[state.players[1].ship_id]
    sp = AlienSpecies(
        id=max(state.species, default=0) + 1, roster_id="quill", name="Quill",
        archetype_id="ribbon_salvager", sector_id=ship.sector_id, home_band="Hub",
        tech_level=3, base_disposition=0.3, disposition_center=0.3, disposition_variance=0.0,
    )
    state.species[sp.id] = sp
    return state, sp


def test_sour_attitude_drops_offset_and_forms_grudge() -> None:
    """§6.5: kills lower the offset by the species' loss rate and deepen a dated grudge."""
    sc = CFG.roster.species_by_id("quill")
    sp = _species(base=0.5)
    sp = replace(sp, roster_id="quill")
    player = _player()
    soured = sour_attitude(player, sp, sc, CFG.aliens, day=4, kills=2)
    assert soured.species_attitudes["quill"] == pytest.approx(-2 * sc.attitude_loss_rate)
    grudge = soured.grudges["quill"]
    assert grudge.severity == pytest.approx(2 * CFG.aliens.grudge_severity_per_kill)
    assert grudge.created_day == 4
    assert grudge.duration_days == CFG.aliens.grudge_duration_days
    # A second incident deepens the same grudge, keeping the original date.
    again = sour_attitude(soured, sp, sc, CFG.aliens, day=9, kills=1)
    assert again.grudges["quill"].severity > grudge.severity
    assert again.grudges["quill"].created_day == 4


def test_memory_none_forgets_instantly() -> None:
    """A memory_model:none species records nothing — no souring, no grudge (§6.5)."""
    sc = CFG.roster.species_by_id("quill").model_copy(update={"memory_model": "none"})
    sp = replace(_species(base=0.5), roster_id="quill")
    player = _player()
    assert sour_attitude(player, sp, sc, CFG.aliens, day=1, kills=3) is player


@given(kills=st.integers(min_value=1, max_value=5), amends=st.integers(min_value=0, max_value=25))
@settings(max_examples=80, deadline=None)
def test_permanent_betrayal_floors_the_offset(kills: int, amends: int) -> None:
    """§6.5/§13: after betraying a permanent/never_forgets species, no number of
    amends ever raises the attitude offset above where the betrayal left it."""
    sc = CFG.roster.species_by_id("vennrith")
    assert sc.betrayal_model == "permanent"
    sp = replace(_species(base=0.6), roster_id="vennrith", name="Vennrith")
    player = _player()
    soured = sour_attitude(player, sp, sc, CFG.aliens, day=1, kills=kills)
    floored = soured.species_attitudes["vennrith"]
    assert soured.grudges["vennrith"].duration_days == -1  # undying
    assert attitude_locked(soured, "vennrith")
    current = soured
    for _ in range(amends):
        current, _event = _raise_attitude(current, sp, CFG)
    assert current.species_attitudes["vennrith"] == pytest.approx(floored)


def test_grudge_decay_is_deterministic_through_the_daily_timeline() -> None:
    """§6.5: a finite grudge cools by the holder's gain rate per day and lapses; a
    permanent one never moves. Exact values — the cron timeline is replay state."""
    state = generate_with_player(SMALL, 3)
    quill_rate = CFG.roster.species_by_id("quill").attitude_gain_rate
    player = state.players[1]
    state.players[1] = replace(player, grudges={
        "quill": Grudge("quill", "player", "test", 0.2, state.game.day_number, 30),
        "vennrith": Grudge("vennrith", "player", "test", 0.9, state.game.day_number, -1),
    })
    severities = []
    for _ in range(4):
        apply_result(state, daily_turn_reset(state, CFG))
        grudges = state.players[1].grudges
        severities.append(grudges.get("quill").severity if "quill" in grudges else None)
        assert grudges["vennrith"].severity == pytest.approx(0.9)  # permanent: untouched
    expected = []
    value = 0.2
    for _ in range(4):
        value = round(value - quill_rate, 6)
        expected.append(value if value > 0 else None)
    assert severities == pytest.approx(expected)


def test_grudge_shifts_the_violence_roll_input() -> None:
    """§10: an active grudge subtracts its severity from effective disposition."""
    sp = replace(_species(base=0.7), roster_id="quill")
    calm = _player()
    assert grudge_shift(sp, calm) == 0.0
    angry = replace(calm, grudges={"quill": Grudge("quill", "player", "t", 0.4, 1, 30)})
    assert grudge_shift(sp, angry) == pytest.approx(0.4)


def test_kill_consequences_alignment_experience_and_grudge_event() -> None:
    """WP27 arithmetic through the combat reducer: a kill sours the species, forms a
    grudge (event emitted), shifts alignment by the victim's band, and awards xp."""
    state, sp = _quill_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    foe = EncounterFoe(ship_class_id="scout_marauder", name="Q", hull=1, hull_max=50,
                       shields=0, damage=1, firing_arc="all_round", combat_speed=2)
    enc = Encounter(species_id=sp.id, sector_id=ship.sector_id, foes=(foe,),
                    round=0, player_shields=ship.shields)
    state.players[1] = replace(player, active_encounter=enc)
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    after = state.players[1]
    sc = CFG.roster.species_by_id("quill")
    # quill base 0.3 here ⇒ hostile band: lawful bounty.
    assert after.alignment == CFG.aliens.alignment_kill_hostile
    assert after.experience == max(1, round(sc.threat_rating * CFG.aliens.experience_kill_scale))
    assert after.species_attitudes["quill"] == pytest.approx(-sc.attitude_loss_rate)
    assert after.grudges["quill"].severity == pytest.approx(CFG.aliens.grudge_severity_per_kill)
    formed = [e for e in result.events if isinstance(e, GrudgeFormed)]
    assert formed and formed[0].species_kind == "quill" and not formed[0].permanent


def test_discovery_experience_awarded_on_codex_stamp() -> None:
    """WP27: logging a find into the codex pays experience_per_discovery."""
    state = generate_with_player(SMALL, 3)
    ship = state.ships[state.players[1].ship_id]
    # The nearest obvious open-space find in the Hub — the walk there is encounter-free
    # (the Hub's interrupt chance is 0), so the reduction sequence is deterministic.
    candidates = [d for d in state.discoveries.values()
                  if not d.hidden and d.planet_id is None and d.found_by is None
                  and state.sectors[d.sector_id].distance_band == "Hub"]
    assert candidates, "the Hub always salts common obvious finds"
    paths = ((shortest_path(state.adjacency, ship.sector_id, d.sector_id), d)
             for d in sorted(candidates, key=lambda d: d.id))
    path, disc = min(((p, d) for p, d in paths if p is not None), key=lambda t: len(t[0]))
    for hop in path[1:]:
        apply_result(state, reduce(state, 1, Warp(to_sector=hop), SMALL))
    result = reduce(state, 1, Salvage(discovery_id=disc.id), SMALL)
    apply_result(state, result)
    assert state.players[1].experience == CFG.aliens.experience_per_discovery


def test_core_law_notice_for_criminals_only() -> None:
    """WP27 Core-law basics: a criminal crossing into the Core is put on notice, once
    per crossing; a lawful player never is."""
    state = generate_with_player(SMALL, 4)
    player = state.players[1]
    ship = state.ships[player.ship_id]
    assert state.sectors[ship.sector_id].is_galactic_core  # enrolment starts in the Core
    # Walk to the Core's edge — a Core sector with a non-Core neighbour.
    edge, outside = next(
        (sid, n) for sid in sorted(state.adjacency)
        if state.sectors[sid].is_galactic_core
        for n in state.adjacency[sid] if not state.sectors[n].is_galactic_core
    )
    path = shortest_path(state.adjacency, ship.sector_id, edge)
    assert path is not None
    for hop in path[1:]:
        apply_result(state, reduce(state, 1, Warp(to_sector=hop), SMALL))
    # Lawful: out and back in, no notice.
    for hop in (outside, edge):
        result = reduce(state, 1, Warp(to_sector=hop), SMALL)
        apply_result(state, result)
        assert not any(isinstance(e, CoreLawNotice) for e in result.events)
        if state.players[1].active_encounter is not None:
            pytest.skip("intercepted during the walk (rare at this seed)")
    # Criminal: the Core crossing (and only the crossing) draws the patrol's eye.
    state.players[1] = replace(state.players[1], alignment=CFG.aliens.criminal_alignment - 1)
    result = reduce(state, 1, Warp(to_sector=outside), SMALL)
    apply_result(state, result)
    assert not any(isinstance(e, CoreLawNotice) for e in result.events)  # leaving is free
    result = reduce(state, 1, Warp(to_sector=edge), SMALL)
    apply_result(state, result)
    assert sum(isinstance(e, CoreLawNotice) for e in result.events) == 1


def test_seeded_grudges_land_for_cast_pairs() -> None:
    """§6.5: roster grudges become Grudge rows exactly when both kinds are cast."""
    state = generate(SMALL, 3)
    state.species = {
        1: replace(_species(sid=1), roster_id="vennrith"),
        2: replace(_species(sid=2), roster_id="quill"),
    }
    _seed_grudges(state, CFG.roster)
    rows = list(state.grudges.values())
    assert any(g.holder == "vennrith" and g.target == "quill" and g.duration_days == -1
               for g in rows)
    # Remove the target kind: the grudge has no one to hold it against.
    state.species = {1: replace(_species(sid=1), roster_id="vennrith")}
    _seed_grudges(state, CFG.roster)
    assert not any(g.target == "quill" for g in state.grudges.values())


# --- WP34: the singular roaming Entity (§7) ---------------------------------

_ENTITY_MODES = [
    SMALL.model_copy(update={"bigbang": SMALL.bigbang.model_copy(update={"topology_mode": m})})
    for m in ("trunk", "expansive")
]


@pytest.mark.parametrize("mode_cfg", _ENTITY_MODES, ids=["trunk", "expansive"])
@pytest.mark.parametrize("seed", range(50))
def test_singular_entity_unique_and_never_core(mode_cfg, seed: int) -> None:  # type: ignore[no-untyped-def]
    """The Entity is always drawn, exactly once, with no satellites, and never in the Core."""
    state = generate(mode_cfg, seed)
    entity_kinds = {s.id for s in CFG.roster.species if s.singular_entity}
    assert entity_kinds  # the default roster flags the Concordance
    instances = [sp for sp in state.species.values() if sp.roster_id in entity_kinds]
    assert len(instances) == 1  # exactly one, no cluster satellites
    assert not state.sectors[instances[0].sector_id].is_galactic_core


@pytest.mark.parametrize("seed", range(10))
def test_singular_entity_spawns_in_a_deep_band(seed: int) -> None:
    """At the ~1000-sector default scale the Entity spawns in a deep band (its Void hint)."""
    state = generate(CFG, seed)  # the shipped default (expansive, all bands live)
    entity = next(sp for sp in state.species.values()
                  if sp.roster_id == "concordance")
    assert state.sectors[entity.sector_id].distance_band in {"Deep", "Void"}


# --- WP39: inter-species relations, spillover, NPC-vs-NPC (§6.4) ------------------

def test_species_relation_alliance_derived_defaults() -> None:
    roster, al = CFG.roster, CFG.aliens
    # Bloc-mates (both Federation) default to the ally value, both ways.
    assert species_relation(roster, "terran", "centaurian", al) == al.relation_ally_default
    assert species_relation(roster, "centaurian", "terran", al) == al.relation_ally_default
    # Federation rivals the Liberty Front (id 4) → its members chill to the rival default.
    assert species_relation(roster, "terran", "thessbrood", al) == al.relation_rival_default
    # An unaligned raider has no alliance-derived stance.
    assert species_relation(roster, "vesk", "terran", al) == 0.0
    # A species is fully aligned with its own kind.
    assert species_relation(roster, "terran", "terran", al) == 1.0


def test_species_relation_override_wins_and_is_asymmetric() -> None:
    roster, al = CFG.roster, CFG.aliens
    # Authored overrides (quill/vennrith) beat any alliance default, and disagree by direction.
    assert species_relation(roster, "vennrith", "quill", al) == -0.8
    assert species_relation(roster, "quill", "vennrith", al) == -0.5


def test_spillover_warms_friends_and_chills_enemies() -> None:
    roster, al = CFG.roster, CFG.aliens
    player = _player()
    # Helping vennrith (delta +0.4): its bloc-mates warm, its authored enemies chill.
    updated = apply_spillover(player, "vennrith", 0.4, roster, al)
    frac = al.spillover_fraction
    assert updated["quill"] == pytest.approx(0.4 * frac * -0.8)      # enemy → chilled
    assert updated["helot"] == pytest.approx(0.4 * frac * al.relation_ally_default)  # bloc-mate → warmed
    assert "vennrith" not in updated  # the subject itself is untouched here


def test_spillover_reverses_sign_on_harm() -> None:
    roster, al = CFG.roster, CFG.aliens
    # Harming vennrith (delta −0.4): its enemies warm instead.
    updated = apply_spillover(_player(), "vennrith", -0.4, roster, al)
    assert updated["quill"] == pytest.approx(-0.4 * al.spillover_fraction * -0.8)  # > 0
    assert updated["quill"] > 0.0


def test_spillover_skips_permanently_grudged_species() -> None:
    roster, al = CFG.roster, CFG.aliens
    locked = Grudge(holder="quill", target="player", cause="x", severity=0.9,
                    created_day=1, duration_days=-1)
    player = _player().__class__(id=1, name="P", ship_id=1, latinum=0,
                                 grudges={"quill": locked})
    updated = apply_spillover(player, "vennrith", 0.4, roster, al)
    assert "quill" not in updated  # a permanent grudge locks the offset (§6.5)


def test_npc_stance_subtracts_active_grudge() -> None:
    roster, al = CFG.roster, CFG.aliens
    state = UniverseState.new(Game(id=1, seed=1, config_version=CFG.config_version,
                                   created_at="1970-01-01T00:00:00Z"))
    base = species_relation(roster, "vennrith", "quill", al)  # -0.8 authored
    assert npc_stance(state, roster, "vennrith", "quill", al) == pytest.approx(base)
    state.grudges[1] = Grudge(holder="vennrith", target="quill", cause="raid",
                              severity=0.15, created_day=1, duration_days=30)
    assert npc_stance(state, roster, "vennrith", "quill", al) == pytest.approx(
        max(-1.0, base - 0.15))


def test_check_relations_rejects_mutual_intra_bloc_enmity() -> None:
    from edge.bigbang.validate import ValidationError, _check_relations
    roster = RosterConfig.model_validate(_roster_mapping(
        alliances=[{"id": 1, "name": "Fed"}],
        species=[
            {"id": "a", "name": "A", "archetype_id": "x", "disposition_center": 0.8,
             "alliance_id": 1, "relations": {"b": -0.4}},
            {"id": "b", "name": "B", "archetype_id": "y", "disposition_center": 0.8,
             "alliance_id": 1, "relations": {"a": -0.4}},
        ],
    ))
    cfg = CFG.model_copy(update={"roster": roster})
    state = UniverseState.new(Game(id=1, seed=1, config_version=CFG.config_version,
                                   created_at="1970-01-01T00:00:00Z"))
    state.species[1] = AlienSpecies(
        id=1, roster_id="a", name="A", archetype_id="x", sector_id=1, home_band="Hub",
        tech_level=1, base_disposition=0.8, disposition_center=0.8, disposition_variance=0.0,
        alliance_id=1)
    state.species[2] = AlienSpecies(
        id=2, roster_id="b", name="B", archetype_id="y", sector_id=2, home_band="Hub",
        tech_level=1, base_disposition=0.8, disposition_center=0.8, disposition_variance=0.0,
        alliance_id=1)
    with pytest.raises(ValidationError, match="mutually hostile"):
        _check_relations(state, cfg)
