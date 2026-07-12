"""Cut generated archetype sheets into responsive port/starbase UI assets.

Source sheets are retained as provenance. Exterior sheets guide the procedural cell-art
grammars; only service banners are cropped because runtime icons stay code-native.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PORTS = ROOT / "images" / "ui" / "ports"
BASES = ROOT / "images" / "ui" / "starbases"
ARCHETYPES = (
    "amorous_imp", "brain_dome_automaton", "canid_technologist",
    "colonial_broodmaster", "cosmic_arbiter", "engineered_aesthete",
    "horned_grudgekeeper", "humanoid_diplomat", "psionic_overlord",
    "ribbon_salvager", "telepath_aristocrat", "temporal_broker",
    "tentacled_envoy", "winged_schemer",
)
BASE_SERVICES = ("status", "station", "trade", "hardware", "bank")


def _aspect_crop(image: Image.Image, ratio: float) -> Image.Image:
    """Centered crop to pixel ratio (already corrected for terminal cell geometry)."""
    width, height = image.size
    current = width / height
    if current > ratio:
        target = round(height * ratio)
        left = (width - target) // 2
        return image.crop((left, 0, left + target, height))
    target = round(width / ratio)
    top = (height - target) // 2
    return image.crop((0, top, width, top + target))


def _save_sizes(image: Image.Image, directory: Path, stem: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    sizes = (((700, 200), "standard"), ((900, 300), "wide"))
    for size, layout in sizes:
        ratio = size[0] / size[1]
        cropped = _aspect_crop(image, ratio).resize(size, Image.Resampling.LANCZOS)
        cropped.save(directory / f"{stem}_{layout}.png", optimize=True)


def build() -> None:
    for archetype in ARCHETYPES:
        sheet = Image.open(BASES / "source" / f"{archetype}_services_sheet.png").convert("RGB")
        cell_w, cell_h = sheet.width // 3, sheet.height // 2

        def panel(column: int, row: int) -> Image.Image:
            # Trim a small gutter allowance so divider pixels never enter the ANSI crop.
            inset = max(2, min(cell_w, cell_h) // 100)
            left, top = column * cell_w + inset, row * cell_h + inset
            right = (column + 1) * cell_w - inset if column < 2 else sheet.width - inset
            bottom = (row + 1) * cell_h - inset if row < 1 else sheet.height - inset
            return sheet.crop((left, top, right, bottom))

        _save_sizes(panel(0, 0), PORTS / "banners", f"{archetype}_trade")
        positions = dict(zip(BASE_SERVICES, ((1, 0), (2, 0), (0, 1), (1, 1), (2, 1)), strict=True))
        for service, (column, row) in positions.items():
            _save_sizes(panel(column, row), BASES / "banners", f"{archetype}_{service}")


if __name__ == "__main__":
    build()
