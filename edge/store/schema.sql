-- Edge of the Unknown — SQLite schema (DESIGN §12).
--
-- Phase 1 persists the reproducibility rail: the game meta (seed + config
-- version) plus the durable command and event logs. Live entity state is
-- reconstructed by regenerating the universe from the seed and replaying the
-- command log (the "(seed, command log)" integrity property, §3) — so the full
-- §4 entity tables are a later snapshot optimisation, not needed for Phase 1.

CREATE TABLE IF NOT EXISTS meta (
    id                          INTEGER PRIMARY KEY CHECK (id = 1),
    seed                        INTEGER NOT NULL,
    config_version              INTEGER NOT NULL,
    created_at                  TEXT    NOT NULL,
    day_number                  INTEGER NOT NULL,
    core_governing_alliance_id  INTEGER
);

-- Every player command, in order — the source of truth for replay.
CREATE TABLE IF NOT EXISTS command_log (
    seq       INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    type      TEXT    NOT NULL,
    payload   TEXT    NOT NULL  -- JSON
);

-- The durable event rail the engine tick loop consumes (DESIGN §3, §9).
CREATE TABLE IF NOT EXISTS event_log (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    tick    INTEGER NOT NULL,
    type    TEXT    NOT NULL,
    payload TEXT    NOT NULL  -- JSON
);
