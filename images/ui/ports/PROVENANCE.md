# Ordinary-port archetype artwork provenance

- Generated: 2026-07-11/12 with OpenAI's built-in image generation tool.
- Identity: every filename is a species `archetype_id` from
  `config/alien_roster_default.yaml`; there is no separate culture identifier.
- `source/*_exterior_sheet.png`: two-panel exterior references (ordinary port at
  left, orbital starbase at right). These are retained for future use and guide
  the archetype palettes/grammars in `edge/art/port.py`; runtime icons remain
  deterministic procedural cell art, not Chafa rasters.
- `banners/*_trade_{standard,wide}.png`: ordinary-port commodity-exchange panels
  cut from the matching six-panel service source sheet by
  `scripts/build_station_archetype_art.py`.
- Runtime: `edge.art.stations` sends banners through Pillow/Chafa, applying the
  active high-contrast or monochrome treatment without duplicating source crops.

Prompts required simple readable silhouettes, crisp value separation, no words,
letters, labels, logos, insignia, watermarks, recognizable franchise designs, or
third-party assets.
