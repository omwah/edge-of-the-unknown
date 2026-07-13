# Stardock service artwork provenance

- Purpose: PT-06 Colonists-tab station-concourse art.
- Generated: 2026-07-11 with OpenAI's built-in image generation tool.
- Direction: a hopeful colonist recruitment office and queues inside an amber,
  circular, DS9-like orbital promenade; simplified for low-resolution ANSI conversion.
- Source: `stardock_concourse_source.png` (1672×941).
- Derived accessibility assets:
  - `stardock_concourse_high_contrast.png`: contrast-stretched, saturated, and
    posterized with ImageMagick for stronger ANSI separation.
  - `stardock_concourse_monochrome.png`: grayscale, auto-leveled, and
    contrast-stretched with ImageMagick.
- Responsive crops: each colour treatment has a `*_standard.png` 3.5:1 crop and
  a `*_wide.png` 3:1 crop. Both are cut from the centered master composition;
  their pixel aspect matches the physical aspect of the target terminal cells,
  avoiding letterboxing or distortion.
- Runtime conversion: `edge.art.concourse` uses the existing Chafa/Pillow seam in
  `edge.art.portrait`, at 56×8 cells for standard layout and 72×12 for wide.
- Compact 80×24 layout hides the decorative panel; `_CONCOURSE_ART` remains the
  no-asset/no-Chafa fallback.

The image contains no imported third-party asset, logo, written franchise name, or
recognizable character.

## Additional service tabs

Generated on 2026-07-11 with the same built-in image-generation tool and the accepted
concourse master supplied as the visual reference:

- `commodities`: cargo exchange with ore, organics, and equipment displays.
- `shipyard`: exploration hull suspended in an orbital drydock cradle.
- `hardware`: component emporium with large engine-room parts.
- `devices`: defensive-device and munition display island.
- `bank`: circular teller island before a concentric vault.
- `tavern`: circular bar, noticeboard, and conversation booth.

Each tab has its generated `*_source.png` master plus explicit `source`,
`high_contrast`, and `monochrome` standard/wide crops produced with the same ImageMagick
operations and geometry described above. All prompts prohibited text, logos, franchise
insignia, recognizable characters, and exact set recreation.
