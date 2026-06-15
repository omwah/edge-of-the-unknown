"""edge.store — persistence behind a repository interface (DESIGN §12).

SQLite (WAL), one file per game; tables mirror the §4 entities plus the durable
`event_log` and `config`. The repository interface is the swap point for
PostgreSQL if hosted multiplayer ever demands it.
"""

from __future__ import annotations
