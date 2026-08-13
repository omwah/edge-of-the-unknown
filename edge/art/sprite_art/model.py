"""Versioned in-memory model for generic and compositional sprite art."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from rich.cells import get_character_cell_size

SPRITE_SCHEMA_VERSION = 4
PALETTE_SCHEMA_VERSION = 2
# Kept as the sprite-document version for editor construction call sites.
SCHEMA_VERSION = SPRITE_SCHEMA_VERSION

Axis = Literal["horizontal", "vertical", "fixed"]
SectionOrder = Literal["authored", "reversed"]

COLOR_SET_IDS: tuple[str, ...] = (
    "surface",
    "engine",
    "beacon",
    "window",
    "weapons",
    "defensive",
)

COLOR_SET_CODES: dict[str, str] = {
    "surface": "S",
    "engine": "E",
    "beacon": "B",
    "window": "W",
    "weapons": "A",
    "defensive": "D",
}
COLOR_CODE_TO_SET: dict[str, str] = {
    code: color_set for color_set, code in COLOR_SET_CODES.items()
}
SURFACE_MASK_CODE = COLOR_SET_CODES["surface"]

PROPERTY_IDS: tuple[str, ...] = (
    "thrusters",
    "spindrive",
    "hull",
    "armor",
    "screens",
    "main_gun",
    "weapons",
    "cargo",
    "sensors",
    "bridge",
    "habitat",
    "radiator",
    "hangar",
    "reactor",
    "utility",
    # Station parts. Ships never use these, but the vocabulary is shared so the
    # editor keeps one controlled list.
    "docking",
    "beacon",
    "platform",
    "tower",
)

ARCHETYPE_IDS: tuple[str, ...] = (
    "humanoid_diplomat",
    "canid_technologist",
    "tentacled_envoy",
    "brain_dome_automaton",
    "ribbon_salvager",
    "temporal_broker",
    "cosmic_arbiter",
    "telepath_aristocrat",
    "engineered_aesthete",
    "amorous_imp",
    "horned_grudgekeeper",
    "psionic_overlord",
    "colonial_broodmaster",
    "winged_schemer",
)


class SpriteValidationError(ValueError):
    """A sprite or palette document violates the authoring contract."""


@dataclass
class Variant:
    id: str
    cells: list[str]
    color_mask: list[str]
    weight: int = 1
    archetypes: list[str] = field(default_factory=list)
    """Archetypes this variant is exclusive to; empty means any archetype.

    Selection prefers variants naming the rendered archetype, falls back to the
    un-tagged variants, and only then to the whole section. See
    ``render._choose_variant``."""

    @property
    def width(self) -> int:
        return max((len(row) for row in self.cells), default=0)

    @property
    def height(self) -> int:
        return len(self.cells)

    def validate(self, context: str) -> None:
        if not self.id:
            raise SpriteValidationError(f"{context}: variant id cannot be empty")
        if self.weight < 1:
            raise SpriteValidationError(f"{context}/{self.id}: weight must be at least 1")
        unknown_archetypes = set(self.archetypes) - set(ARCHETYPE_IDS)
        if unknown_archetypes:
            raise SpriteValidationError(
                f"{context}/{self.id}: unknown archetypes {sorted(unknown_archetypes)!r}"
            )
        if len(set(self.archetypes)) != len(self.archetypes):
            raise SpriteValidationError(
                f"{context}/{self.id}: archetypes must be unique"
            )
        if not self.cells:
            raise SpriteValidationError(f"{context}/{self.id}: cells cannot be empty")
        widths = {len(row) for row in self.cells}
        if len(widths) != 1:
            raise SpriteValidationError(
                f"{context}/{self.id}: every row must have the same character count"
            )
        for row_index, row in enumerate(self.cells):
            for column, glyph in enumerate(row):
                if get_character_cell_size(glyph) != 1:
                    raise SpriteValidationError(
                        f"{context}/{self.id}: glyph {glyph!r} at "
                        f"{column},{row_index} is not one terminal cell wide"
                    )
        if len(self.color_mask) != self.height:
            raise SpriteValidationError(
                f"{context}/{self.id}: color_mask must have {self.height} rows"
            )
        mask_widths = {len(row) for row in self.color_mask}
        if mask_widths != {self.width}:
            raise SpriteValidationError(
                f"{context}/{self.id}: color_mask rows must match the "
                f"{self.width}-cell canvas width"
            )
        for row_index, (glyph_row, mask_row) in enumerate(
            zip(self.cells, self.color_mask)
        ):
            for column, (glyph, code) in enumerate(zip(glyph_row, mask_row)):
                if code not in COLOR_CODE_TO_SET:
                    raise SpriteValidationError(
                        f"{context}/{self.id}: unknown color-mask code {code!r} at "
                        f"{column},{row_index}"
                    )
                if glyph == " " and code != SURFACE_MASK_CODE:
                    raise SpriteValidationError(
                        f"{context}/{self.id}: void cell at {column},{row_index} "
                        "must use the Surface color mask"
                    )


@dataclass
class Section:
    id: str
    name: str
    primary_property: str
    secondary_properties: list[str] = field(default_factory=list)
    repeat: int = 1
    variants: list[Variant] = field(default_factory=list)
    archetype_repeats: dict[str, int] = field(default_factory=dict)
    """Per-archetype overrides of ``repeat``; a resolved zero omits the band.

    A baseline ``repeat`` of zero plus a single override makes a band exclusive
    to one archetype. Overrides never change how many random decisions a render
    consumes: the variant draw happens for every section and is discarded when
    the resolved repeat is zero."""

    def repeat_for(self, archetype_id: str | None) -> int:
        """Resolve this section's repetition count for one archetype."""

        if archetype_id is None:
            return self.repeat
        return self.archetype_repeats.get(archetype_id, self.repeat)

    def validate(self, context: str) -> None:
        section_context = f"{context}/{self.id}"
        if not self.id:
            raise SpriteValidationError(f"{context}: section id cannot be empty")
        if self.primary_property not in PROPERTY_IDS:
            raise SpriteValidationError(
                f"{section_context}: unknown primary property {self.primary_property!r}"
            )
        invalid_secondary = set(self.secondary_properties) - set(PROPERTY_IDS)
        if invalid_secondary:
            raise SpriteValidationError(
                f"{section_context}: unknown secondary properties "
                f"{sorted(invalid_secondary)!r}"
            )
        if self.primary_property in self.secondary_properties:
            raise SpriteValidationError(
                f"{section_context}: primary property cannot also be secondary"
            )
        if len(set(self.secondary_properties)) != len(self.secondary_properties):
            raise SpriteValidationError(
                f"{section_context}: secondary properties must be unique"
            )
        if self.repeat < 0:
            raise SpriteValidationError(f"{section_context}: repeat cannot be negative")
        unknown_archetypes = set(self.archetype_repeats) - set(ARCHETYPE_IDS)
        if unknown_archetypes:
            raise SpriteValidationError(
                f"{section_context}: unknown archetype_repeats keys "
                f"{sorted(unknown_archetypes)!r}"
            )
        for archetype_id, repeat in sorted(self.archetype_repeats.items()):
            if repeat < 0:
                raise SpriteValidationError(
                    f"{section_context}: archetype_repeats[{archetype_id!r}] "
                    "cannot be negative"
                )
        if not self.variants:
            raise SpriteValidationError(f"{section_context}: requires at least one variant")
        seen: set[str] = set()
        dimensions: set[tuple[int, int]] = set()
        for variant in self.variants:
            if variant.id in seen:
                raise SpriteValidationError(
                    f"{section_context}: duplicate variant id {variant.id!r}"
                )
            seen.add(variant.id)
            variant.validate(section_context)
            dimensions.add((variant.width, variant.height))
        if len(dimensions) != 1:
            raise SpriteValidationError(
                f"{section_context}: variants must share one rectangular size"
            )


@dataclass
class Tier:
    id: str
    name: str
    sections: list[Section] = field(default_factory=list)

    def cross_axis_size(self, axis: Axis) -> int:
        if not self.sections:
            return 0
        if axis == "horizontal":
            return max(variant.height for section in self.sections for variant in section.variants)
        if axis == "vertical":
            return max(variant.width for section in self.sections for variant in section.variants)
        first = self.sections[0].variants[0]
        return max(first.width, first.height)

    def composed_length(self, axis: Axis, archetype_id: str | None = None) -> int:
        """Cells this tier occupies along its composition axis for one archetype.

        Columns for a horizontal view, rows for a vertical one. Exact rather
        than approximate, because every variant in a section shares one
        rectangular size. This is what a vertical view's tier selection budgets
        against, mirroring Edge's ``port._grammar_floor``."""

        total = 0
        for section in self.sections:
            if not section.variants:
                continue
            variant = section.variants[0]
            extent = variant.width if axis == "horizontal" else variant.height
            total += extent * section.repeat_for(archetype_id)
        return total

    def validate(self, context: str, axis: Axis) -> None:
        tier_context = f"{context}/{self.id}"
        if not self.id:
            raise SpriteValidationError(f"{context}: tier id cannot be empty")
        if not self.sections:
            raise SpriteValidationError(f"{tier_context}: requires at least one section")
        if axis == "fixed" and len(self.sections) != 1:
            raise SpriteValidationError(
                f"{tier_context}: fixed views require exactly one section"
            )
        seen: set[str] = set()
        cross_sizes: set[int] = set()
        for section in self.sections:
            if section.id in seen:
                raise SpriteValidationError(
                    f"{tier_context}: duplicate section id {section.id!r}"
                )
            seen.add(section.id)
            section.validate(tier_context)
            for variant in section.variants:
                cross_sizes.add(
                    variant.height if axis == "horizontal" else variant.width
                )
        if axis != "fixed" and len(cross_sizes) != 1:
            raise SpriteValidationError(
                f"{tier_context}: every part must share the same cross-axis size"
            )
        # A per-archetype repeat of zero omits a band. Zeroing every band would
        # compose an empty grid, which renders as a blank box rather than an
        # error, so reject it here instead.
        for archetype_id in (None, *ARCHETYPE_IDS):
            if any(section.repeat_for(archetype_id) for section in self.sections):
                continue
            who = archetype_id or "the default archetype"
            raise SpriteValidationError(
                f"{tier_context}: {who} has no section left to compose; at least "
                "one repeat must be positive"
            )


@dataclass
class View:
    id: str
    name: str
    axis: Axis
    canonical_facing: str
    mirror_facing: str | None
    tiers: list[Tier] = field(default_factory=list)
    section_order: SectionOrder = "authored"
    """Whether a vertical view stacks its sections as authored or in reverse.

    Ship vertical views are rotations of tail-to-nose horizontal art, so they
    stack ``reversed`` to read nose-up. Art authored directly top-to-bottom,
    such as a station, uses ``authored``."""

    def tier_budget_size(self, tier: Tier, archetype_id: str | None = None) -> int:
        """The height this tier needs, which is what selects it.

        A horizontal view is bounded by its constant structure height; a
        vertical view by the rows its sections stack to. Both are compared
        against the requested height, matching Edge's ship and port
        generators."""

        if self.axis == "vertical":
            return tier.composed_length(self.axis, archetype_id)
        return tier.cross_axis_size(self.axis)

    def validate(self, context: str) -> None:
        view_context = f"{context}/{self.id}"
        if not self.id:
            raise SpriteValidationError(f"{context}: view id cannot be empty")
        if self.axis not in ("horizontal", "vertical", "fixed"):
            raise SpriteValidationError(f"{view_context}: unsupported axis {self.axis!r}")
        if not self.canonical_facing:
            raise SpriteValidationError(
                f"{view_context}: canonical_facing cannot be empty"
            )
        if self.axis == "fixed" and self.mirror_facing is not None:
            raise SpriteValidationError(
                f"{view_context}: fixed views cannot declare a mirror facing"
            )
        if self.section_order not in ("authored", "reversed"):
            raise SpriteValidationError(
                f"{view_context}: unsupported section_order {self.section_order!r}"
            )
        if self.section_order == "reversed" and self.axis != "vertical":
            raise SpriteValidationError(
                f"{view_context}: only vertical views may reverse their section order"
            )
        if not self.tiers:
            raise SpriteValidationError(f"{view_context}: requires at least one tier")
        seen: set[str] = set()
        for tier in self.tiers:
            if tier.id in seen:
                raise SpriteValidationError(
                    f"{view_context}: duplicate tier id {tier.id!r}"
                )
            seen.add(tier.id)
            tier.validate(view_context, self.axis)
        # Tier selection walks the list and takes the first tier that fits, so
        # the ordering key has to be the same quantity the selector compares,
        # and it has to be strictly decreasing: two tiers of equal size make the
        # later one unreachable. Per-archetype repeats make a vertical view's
        # key archetype-dependent, so this has to hold for every archetype.
        archetypes: tuple[str | None, ...] = (None,)
        if self.axis == "vertical":
            archetypes = (None, *ARCHETYPE_IDS)
        for archetype_id in archetypes:
            sizes = [self.tier_budget_size(tier, archetype_id) for tier in self.tiers]
            if any(later >= earlier for earlier, later in zip(sizes, sizes[1:])):
                who = f" for {archetype_id}" if archetype_id else ""
                raise SpriteValidationError(
                    f"{view_context}: tiers must be ordered richest/largest "
                    f"first, each strictly smaller than the last{who}; got {sizes}"
                )


@dataclass
class Sprite:
    schema_version: int
    id: str
    name: str
    kind: str
    role: str
    description: str
    views: dict[str, View] = field(default_factory=dict)
    source: str | None = None

    def validate(self) -> None:
        if self.schema_version != SPRITE_SCHEMA_VERSION:
            raise SpriteValidationError(
                f"{self.id or 'sprite'}: unsupported schema_version "
                f"{self.schema_version}; expected {SPRITE_SCHEMA_VERSION}"
            )
        if not self.id or not self.role:
            raise SpriteValidationError("sprite id and role cannot be empty")
        if not self.views:
            raise SpriteValidationError(f"{self.id}: requires at least one view")
        for key, view in self.views.items():
            if key != view.id:
                raise SpriteValidationError(
                    f"{self.id}: view key {key!r} does not match id {view.id!r}"
                )
            view.validate(self.id)


@dataclass
class ColorSet:
    colors: list[str]

    def validate(self, context: str) -> None:
        if not 1 <= len(self.colors) <= 4:
            raise SpriteValidationError(
                f"{context} requires between one and four colors"
            )
        if any(not color for color in self.colors):
            raise SpriteValidationError(f"{context} colors cannot be empty")

    def color_for_slot(self, slot: int) -> str:
        """Return one glyph-shading slot, falling back to the full-block color."""

        return self.colors[slot] if slot < len(self.colors) else self.colors[0]


@dataclass
class Palette:
    color_sets: dict[str, ColorSet]

    def validate(self, context: str) -> None:
        actual = set(self.color_sets)
        expected = set(COLOR_SET_IDS)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise SpriteValidationError(
                f"{context} color sets are controlled; missing={missing}, extra={extra}"
            )
        for color_set_id in COLOR_SET_IDS:
            self.color_sets[color_set_id].validate(f"{context}.{color_set_id}")

    def color_set(self, color_set_id: str) -> ColorSet:
        return self.color_sets[color_set_id]


@dataclass
class PaletteCatalog:
    schema_version: int
    archetypes: dict[str, Palette]
    fallback_archetype: str = "humanoid_diplomat"

    def validate(self) -> None:
        if self.schema_version != PALETTE_SCHEMA_VERSION:
            raise SpriteValidationError(
                "palette catalog has unsupported schema_version "
                f"{self.schema_version}; expected {PALETTE_SCHEMA_VERSION}"
            )
        actual = set(self.archetypes)
        expected = set(ARCHETYPE_IDS)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise SpriteValidationError(
                f"palette archetypes are controlled; missing={missing}, extra={extra}"
            )
        if self.fallback_archetype != "humanoid_diplomat":
            raise SpriteValidationError(
                "fallback_archetype must remain 'humanoid_diplomat'"
            )
        for archetype_id, palette in self.archetypes.items():
            palette.validate(archetype_id)

    def resolve(self, archetype_id: str | None) -> Palette:
        return self.archetypes.get(
            (archetype_id or "").lower(),
            self.archetypes[self.fallback_archetype],
        )
