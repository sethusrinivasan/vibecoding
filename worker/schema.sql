-- D1 telemetry schema — mirrors the local SQLite schema used by TelemetryStore
-- Run once: wrangler d1 execute greeting-telemetry --file=worker/schema.sql

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,   -- ISO-8601 UTC
    event_type  TEXT    NOT NULL,   -- e.g. "greeting", "tcp_request"
    duration_ns INTEGER NOT NULL,   -- wall-clock nanoseconds
    success     INTEGER NOT NULL,   -- 1 = ok, 0 = fault/error
    error_msg   TEXT                -- NULL when success=1
);

CREATE INDEX IF NOT EXISTS idx_event_type ON events (event_type);
