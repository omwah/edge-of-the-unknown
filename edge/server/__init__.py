"""edge.server — the game service (DESIGN §3).

Applies commands against a session context, calls the pure `core.rules` reducers,
persists the resulting events, and fans public projections out to clients. Fog of
war is enforced here at the `to_public(context)` boundary. Single-player embeds
this service in-process; multiplayer (Phase 4) swaps the call for JSON-RPC.
"""

from __future__ import annotations
