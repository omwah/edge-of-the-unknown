# Orbital-starbase archetype artwork provenance

- Generated: 2026-07-11/12 with OpenAI's built-in image generation tool.
- Identity: every filename is a species `archetype_id` from
  `config/alien_roster_default.yaml`; there is no separate culture identifier.
- `source/*_services_sheet.png`: exact 3×2 masters. Panel order is port Trade;
  starbase Status, Station, Trade, Hardware, and Bank.
- `banners/*_{status,station,trade,hardware,bank}_{standard,wide}.png`: responsive
  crops built deterministically by `scripts/build_station_archetype_art.py`.
- `icons/`: retained raster crops for possible future use. The current runtime
  icon deliberately continues the procedural `edge.art.port` band-grammar method,
  with structure and palette derived from the exterior reference sheets.
- Runtime condition treatments: derelicts are dark/desaturated with fixed damage
  scars; hostile bases receive alarm-red illumination. Theme and condition filters
  run before Chafa conversion and are memoized with the render key.

Prompts prohibited words, letters, labels, logos, insignia, watermarks,
recognizable franchise designs, and imported third-party assets.
