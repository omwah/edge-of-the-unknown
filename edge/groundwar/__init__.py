"""`edge-groundwar` — the ground-war playtest shell.

Originally a standalone proof of concept with its own pure `config`/`model`/`mapgen`/
`rules` engine (a Starship-Troopers-inspired tactical raid). Its mechanics proved out
and were reimplemented for the live game as `edge.core.groundwar`
(survey/assault/settlement — GW-WP01-13), reached through `PlanetScreen.action_descend`
and rendered by `edge.tui.screens.ground_assault`/`ground_expedition`. GW-WP14 retired
the POC's own duplicate engine and retargeted this app onto those same production rules
and screens (`edge.groundwar.harness` builds a throwaway single-planet `GameService`;
`app.py` is now chrome-and-config-only). `findart.py` and `widgets.py` remain live
production dependencies despite living under this nominally-POC package.
"""
