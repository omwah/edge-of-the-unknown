"""Deterministic naming generator based on configurable name pools."""

import random
from collections.abc import Iterable

from edge.core.config import NameList, NamesConfig
from edge.core.enums import DiscoveryKind


class NameGenerator:
    """Draws names without replacement from a pool of combinations."""

    def __init__(self, names: NameList | None, fallback_prefix: str, rng: random.Random) -> None:
        self.fallback_prefix = fallback_prefix
        self.fallback_counter = 1
        
        self.combinations: list[str] = []
        if names and names.first_part and names.second_part:
            for first in names.first_part:
                for last in names.second_part:
                    self.combinations.append(f"{first} {last}")
            rng.shuffle(self.combinations)
        self.iter = iter(self.combinations)

    def draw(self) -> str:
        """Draws the next combination. Falls back to numbered prefix if exhausted."""
        try:
            return next(self.iter)
        except StopIteration:
            name = f"{self.fallback_prefix} {self.fallback_counter}"
            self.fallback_counter += 1
            return name


class DiscoveryNamer:
    """Names discoveries per kind from `names.discoveries` (PT-49, DESIGN §7).

    One `NameGenerator` per `DiscoveryKind`, so each kind draws from its own pool without
    replacement (no two nebulae share a name until the pool is exhausted, then it falls back to
    "Nebula 1", "Nebula 2", …). Every generator is seeded off a **names-only sub-RNG**, so
    naming can never perturb the placement draw the §7 gradient and the golden replays depend
    on — adding a name pool changes what things are *called*, never where they *are*.
    """

    def __init__(self, names: NamesConfig | None, rng: random.Random,
                 used: Iterable[str] = ()) -> None:
        pools = names.discoveries if names is not None else {}
        self._by_kind = {
            kind: NameGenerator(pools.get(kind.value), _fallback_prefix(kind), rng)
            for kind in DiscoveryKind
        }
        # Names already spoken for — the later passes (raid caches) run their own namer over the
        # same pools, so without this two Ancient Techs could share a name in one universe.
        self._used = set(used)

    def draw(self, kind: DiscoveryKind) -> str:
        """The next unused name for `kind`. Exhausting a pool falls through to numbering."""
        while True:
            name = self._by_kind[kind].draw()
            if name not in self._used:
                self._used.add(name)
                return name

    def draw_surface(self, kind: DiscoveryKind, discovery_id: int) -> str:
        """Draw a POC surface name if available and unused; fall back to kind namer."""
        from edge.core.surface_finds import surface_find_name

        sname = surface_find_name(kind, discovery_id)
        if sname and sname not in self._used:
            self._used.add(sname)
            return sname
        return self.draw(kind)


def _fallback_prefix(kind: DiscoveryKind) -> str:
    """"black_hole" → "Black Hole" — the numbered fallback when a kind's pool runs dry."""
    return kind.value.replace("_", " ").title()
