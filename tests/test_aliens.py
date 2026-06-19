"""WP7 — friendly alien species & roster (DESIGN §6, §13).

Covers the pure-core disposition helpers, the roster's reference-integrity validation,
and the big-bang placement invariants (seeded subset, friendly-band clamp, per-band
contact) — plus the determinism guard that species placement does not perturb the
Phase-1 port/planet draws.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.aliens import (
    FRIENDLY,
    HOSTILE,
    NEUTRAL,
    disposition_band,
    effective_disposition,
    is_friendly,
)
from edge.core.config import GameConfig, RosterConfig
from edge.core.models import AlienSpecies, Player

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 80})})
# A larger universe reaches the Deep/Void bands (the 80-sector one stops at Frontier).
WIDE = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 400})})


def _species(sid: int = 1, base: float = 0.7) -> AlienSpecies:
    return AlienSpecies(
        id=sid, roster_id="x", name="X", archetype_id="a", sector_id=11, home_band="Hub",
        tech_level=5, base_disposition=base, disposition_center=base, disposition_variance=0.1,
    )


def _player(attitudes: dict[int, float] | None = None) -> Player:
    return Player(id=1, name="P", ship_id=1, latinum=0, species_attitudes=attitudes or {})


# --- disposition helpers (pure core) ---------------------------------------------

def test_effective_disposition_applies_offset_and_clamps() -> None:
    sp = _species(base=0.7)
    assert effective_disposition(sp, _player()) == pytest.approx(0.7)  # no offset yet
    assert effective_disposition(sp, _player({1: 0.2})) == pytest.approx(0.9)
    # Clamped to [0, 1] at both ends.
    assert effective_disposition(sp, _player({1: 0.9})) == pytest.approx(1.0)
    assert effective_disposition(sp, _player({1: -2.0})) == pytest.approx(0.0)


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
def test_all_placed_species_are_friendly_and_outside_core(seed: int) -> None:
    state = generate(WIDE, seed)
    assert state.species  # the default roster always places some
    core = {s.id for s in state.sectors.values() if s.is_galactic_core}
    for sp in state.species.values():
        assert is_friendly(sp.base_disposition, CFG.aliens)
        assert sp.sector_id not in core
        assert sp.alliance_id is None or sp.alliance_id in state.alliances


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
    no_roster = SMALL.model_copy(update={"roster": None})
    with_roster = SMALL
    a = generate(no_roster, 7)
    b = generate(with_roster, 7)
    assert a.ports == b.ports
    assert a.planets == b.planets
    assert not a.species and b.species  # only the alien layer differs


def test_no_roster_falls_back_to_federation_stub() -> None:
    state = generate(SMALL.model_copy(update={"roster": None}), 1)
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
