-- Usage log for the Seeing Coordinates trial site (D1 database seeing-coordinates-log). Last edited: 2026-11-18: moved into api/migrations; unchanged schema.
-- events: one row per user action. No name, e-mail or IP address is stored.
CREATE TABLE IF NOT EXISTS events (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT    NOT NULL,              -- server time, ISO 8601 UTC
  session  TEXT    NOT NULL,              -- random id generated in the browser
  grp      TEXT    NOT NULL DEFAULT '',   -- trial group code from the ?g= link (club, course, shop)
  type     TEXT    NOT NULL,              -- consent | ask | open | click | map
  question TEXT    NOT NULL DEFAULT '',   -- what the user typed (ask only)
  qid      TEXT    NOT NULL DEFAULT '',   -- question-bank id the answer came from
  intent   TEXT    NOT NULL DEFAULT '',
  sha      TEXT    NOT NULL DEFAULT '',   -- answer fingerprint
  exact    INTEGER NOT NULL DEFAULT 0,    -- 1 when the typed question matched the bank exactly
  target   TEXT    NOT NULL DEFAULT ''    -- clicked source URL (click only)
);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);
CREATE INDEX IF NOT EXISTS events_grp ON events (grp, ts);

-- rate: daily counters for abuse control. k is a salted one-day hash, never the raw IP.
CREATE TABLE IF NOT EXISTS rate (
  k   TEXT    NOT NULL,
  day TEXT    NOT NULL,
  n   INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (k, day)
);
