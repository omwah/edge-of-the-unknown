"""Ground-war proof of concept (edge-groundwar).

A standalone, Starship-Troopers-inspired turn-based tactical raid: powered-armor
Mobile Infantry (Marauder / Scout / Command suits) drop onto a populated world and
must force a planetary surrender — by demonstrated capacity for damage, not
extermination — before the retrieval boat lifts. Reuses the planet terrain art
(`edge.art.terrain`) and mirrors core concepts (citadel levels, planet types) but
touches no live game state; if it proves out it would replace the surface screen
for populated worlds (discoveries staying the mini-game for uninhabited/conquered
ones).

Layering mirrors the main game: `config` / `model` / `mapgen` / `rules` are pure
(seeded `random.Random`, no I/O, no Textual); `app` is the throwaway Textual shell.
"""
