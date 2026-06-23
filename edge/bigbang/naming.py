"""Deterministic naming generator based on configurable name pools."""

import random

from edge.core.config import NameList


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
