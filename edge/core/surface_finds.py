"""Shared archaeological find identities promoted from the groundwar POC.

The production discovery kind remains the authoritative mechanical category.  These
find kinds are presentation subtypes for names and field-sketch art; deriving them from
``(DiscoveryKind, Discovery.id)`` adds no stored state and works for existing saves.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from edge.core.enums import DiscoveryKind


@dataclass(frozen=True, slots=True)
class FindKind:
    key: str
    label: str
    blurb: str
    accent: str


FIND_KINDS: dict[str, FindKind] = {
    "colonnade": FindKind(
        "colonnade", "Sunken Colonnade",
        "A processional avenue, its pillars snapped like reeds.", "light_goldenrod2"),
    "cache": FindKind(
        "cache", "Artifact Cache",
        "Sealed vessels, packed in ash and deliberately hidden.", "orchid"),
    "obelisk": FindKind(
        "obelisk", "Inscribed Obelisk",
        "One standing stone, written top to bottom in an unread script.", "sky_blue1"),
    "leviathan": FindKind(
        "leviathan", "Fossil Leviathan",
        "A ribcage the size of a hangar, older than the mountains.", "wheat1"),
    "beacon": FindKind(
        "beacon", "Precursor Beacon",
        "A machine that has waited a long time. It is still warm.", "spring_green2"),
    "hulk": FindKind(
        "hulk", "Derelict Hulk",
        "A hull split open on impact, its systems long since gone dark.", "grey62"),
}

_VARIANTS: dict[DiscoveryKind, tuple[str, ...]] = {
    DiscoveryKind.RUINS: ("colonnade", "obelisk", "leviathan"),
    DiscoveryKind.ARTIFACT: ("cache", "obelisk", "leviathan"),
    DiscoveryKind.ANCIENT_TECH: ("beacon",),
    DiscoveryKind.CRASHED_SHIP: ("hulk",),
}

_ADJ = ("Sunken", "Silent", "Broken", "Painted", "First", "Sleeping", "Veiled",
        "Hollow", "Amber", "Drowned")
_NOUN = {
    "colonnade": ("Colonnade", "Avenue", "Processional"),
    "cache": ("Cache", "Hoard", "Reliquary"),
    "obelisk": ("Obelisk", "Needle", "Standing Stone"),
    "leviathan": ("Leviathan", "Titan", "Great Bones"),
    "beacon": ("Beacon", "Signal", "Waking Engine"),
    "hulk": ("Hulk", "Wreck", "Derelict"),
}
_SYL_A = ("Ves", "Kor", "Ana", "Thel", "Ur", "Mira", "Osh", "Cael", "Dun", "Ilo")
_SYL_B = ("sara", "eth", "ione", "gart", "ume", "adin", "ka", "or", "eshi", "van")


def site_name(rng: random.Random, kind: str) -> str:
    """Draw one POC-style archaeological proper name."""
    who = rng.choice(_SYL_A) + rng.choice(_SYL_B)
    return f"the {rng.choice(_ADJ)} {rng.choice(_NOUN[kind])} of {who}"


def surface_find_kind(kind: DiscoveryKind, discovery_id: int) -> str | None:
    """Stable POC art/name subtype for a compatible production surface kind."""
    variants = _VARIANTS.get(kind)
    return variants[discovery_id % len(variants)] if variants else None


def surface_find_name(kind: DiscoveryKind, discovery_id: int) -> str | None:
    """Stable POC name for a compatible existing surface discovery."""
    find_kind = surface_find_kind(kind, discovery_id)
    if find_kind is None:
        return None
    rng = random.Random(f"surface-find-name|{kind.value}|{discovery_id}")
    return site_name(rng, find_kind)
