-- Seeing Coordinates data model v2 (SQLite dialect; runs unchanged on Cloudflare D1).
-- Last edited: 2026-11-17: first draft for the architecture v2 design.
-- Shape follows the Wikibase statement model (a claim with qualifiers, references and a rank)
-- and W3C PROV-O (every evidence row says what source it was derived from and which activity checked it).

PRAGMA foreign_keys = ON;

-- Nodes ---------------------------------------------------------------------------------------
CREATE TABLE entity (
  id          TEXT PRIMARY KEY,                       -- stable slug, never reused
  type        TEXT NOT NULL CHECK (type IN ('person','work','concept','event','institution','group')),
  label_pref  TEXT NOT NULL DEFAULT 'en' CHECK (label_pref IN ('en','zh_en','zh')),
  region      TEXT,                                   -- e.g. TW, JP, CN, KR, HK, SEA, EU, US (for coverage reports)
  created_round INTEGER REFERENCES round(id),
  merged_into TEXT REFERENCES entity(id)              -- set when a duplicate is merged; rows are never deleted
);

CREATE TABLE entity_name (                            -- every spelling a reader might type
  entity_id   TEXT NOT NULL REFERENCES entity(id),
  name        TEXT NOT NULL,
  lang        TEXT NOT NULL,                          -- zh-Hant, zh-Hans, ja, ko, en, ...
  kind        TEXT NOT NULL CHECK (kind IN ('preferred','variant','romanized','translated_title','misspelling')),
  norm        TEXT NOT NULL,                          -- normalised key (s2t, shinjitai->kyujitai, no punctuation, lower)
  PRIMARY KEY (entity_id, name, lang)
);
CREATE INDEX entity_name_norm ON entity_name(norm);

CREATE TABLE entity_external_id (                     -- Wikidata QID, VIAF, ULAN, NDL, NCL ...
  entity_id   TEXT NOT NULL REFERENCES entity(id),
  scheme      TEXT NOT NULL,
  value       TEXT NOT NULL,
  PRIMARY KEY (entity_id, scheme)
);

CREATE TABLE person_detail (
  entity_id   TEXT PRIMARY KEY REFERENCES entity(id),
  birth_year  INTEGER, death_year INTEGER,
  CHECK (death_year IS NULL OR birth_year IS NULL OR death_year >= birth_year)
);

CREATE TABLE work_detail (                            -- what the reading-path planner needs
  entity_id       TEXT PRIMARY KEY REFERENCES entity(id),
  year            INTEGER,                            -- first publication or first showing
  original_lang   TEXT,
  form            TEXT CHECK (form IN ('book','essay','article','photobook','series','exhibition_catalogue','journal','film','other')),
  difficulty      INTEGER CHECK (difficulty BETWEEN 1 AND 3),   -- 1 intro, 2 intermediate, 3 specialist; set by a person
  difficulty_note TEXT,
  has_zh_translation INTEGER CHECK (has_zh_translation IN (0,1))
);

CREATE TABLE edition (                                -- page numbers belong to an edition, not to the work
  id          TEXT PRIMARY KEY,
  work_id     TEXT NOT NULL REFERENCES entity(id),
  lang        TEXT NOT NULL,
  title       TEXT NOT NULL,
  translator  TEXT, publisher TEXT, year INTEGER, isbn TEXT
);

-- Sources and evidence ------------------------------------------------------------------------
CREATE TABLE source (
  id          TEXT PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('web_page','pdf','book','article','catalogue','archive_scan')),
  title       TEXT, author TEXT, publisher TEXT, year INTEGER,
  url         TEXT, host TEXT,
  edition_id  TEXT REFERENCES edition(id),
  tier        TEXT NOT NULL CHECK (tier IN ('primary','institution','critic','popular','other')),
  excluded_reason TEXT                                -- non-null when the host is on the not-acceptable list
);
CREATE INDEX source_host ON source(host);

-- Edges ---------------------------------------------------------------------------------------
CREATE TABLE assertion (
  id          TEXT PRIMARY KEY,                       -- hash of (subject, predicate, object, role)
  subject_id  TEXT NOT NULL REFERENCES entity(id),
  predicate   TEXT NOT NULL CHECK (predicate IN ('influence','critique','extend','belongs_to','contrast','discusses',
                                                 'translate','study','review','interpret','exhibit','hosted_by','prerequisite_for')),
  object_id   TEXT NOT NULL REFERENCES entity(id),
  role        TEXT CHECK (role IN ('author','translator','contributor','movement','member','award','participant','part_of')),
  year        INTEGER,                                -- qualifier: the year the relation holds
  claim_zh    TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('proposed','review','approved','rejected')),
  confidence  REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  interpretive INTEGER NOT NULL DEFAULT 0,            -- 1 when the edge is the curator's own reading (needs an expert)
  CHECK ((predicate = 'belongs_to') = (role IS NOT NULL)),
  CHECK (subject_id <> object_id),
  UNIQUE (subject_id, predicate, object_id, role)
);
CREATE INDEX assertion_subject ON assertion(subject_id, status);
CREATE INDEX assertion_object  ON assertion(object_id, status);

CREATE TABLE evidence (                               -- one row per (assertion, source, quote); an assertion may have several
  id          TEXT PRIMARY KEY,
  assertion_id TEXT NOT NULL REFERENCES assertion(id),
  source_id   TEXT NOT NULL REFERENCES source(id),
  quote       TEXT,                                   -- verbatim, as on the page
  quote_lang  TEXT,
  locator     TEXT,                                   -- page, section or paragraph ("p. 96", "§3")
  directness  TEXT NOT NULL CHECK (directness IN ('verbatim','paraphrase','note')),
  is_current  INTEGER NOT NULL DEFAULT 1,             -- 0 once superseded by a later source (kept for the audit trail)
  added_round INTEGER REFERENCES round(id)
);
CREATE INDEX evidence_assertion ON evidence(assertion_id, is_current);

-- Activities (PROV: who did what, when, why) ----------------------------------------------------
CREATE TABLE round (
  id          INTEGER PRIMARY KEY,                    -- 1, 2, ... 26, 27
  started_on  TEXT NOT NULL,
  label       TEXT NOT NULL,                          -- 第 26 輪擴充
  brief_path  TEXT                                    -- the research brief used
);

CREATE TABLE review_event (                           -- append-only decision ledger; replaces the ［...］ tags inside evidence text
  id          INTEGER PRIMARY KEY,
  assertion_id TEXT NOT NULL REFERENCES assertion(id),
  round_id    INTEGER REFERENCES round(id),
  on_date     TEXT NOT NULL,
  actor       TEXT NOT NULL CHECK (actor IN ('curator','research_agent','blind_checker','audit_rule','monitor','migration')),
  action      TEXT NOT NULL CHECK (action IN ('propose','approve','demote','reject','fix_quote','fix_claim','fix_role','resource','merge','note')),
  from_status TEXT, to_status TEXT,
  reason      TEXT
);
CREATE INDEX review_event_assertion ON review_event(assertion_id);

CREATE TABLE check_run (
  id          INTEGER PRIMARY KEY,
  started_at  TEXT NOT NULL,
  tool        TEXT NOT NULL,                          -- source_monitor, quote_check, blind_check
  scope       TEXT                                    -- all, sample:50, host:moma.org
);

CREATE TABLE check_result (                           -- what the monitor saw for one evidence row in one run
  run_id      INTEGER NOT NULL REFERENCES check_run(id),
  evidence_id TEXT NOT NULL REFERENCES evidence(id),
  page_state  TEXT NOT NULL,                          -- ok, redirected, blocked, gone, unreachable, tls_error, not_text
  quote_state TEXT NOT NULL,                          -- found, partial, missing, unchecked
  final_url   TEXT, text_sha256 TEXT,
  PRIMARY KEY (run_id, evidence_id)
);

-- Read-side views ------------------------------------------------------------------------------
CREATE VIEW formal_edge AS
  SELECT a.*, e.quote, e.locator, s.url, s.tier AS source_tier, s.title AS source_title
  FROM assertion a
  JOIN evidence e ON e.assertion_id = a.id AND e.is_current = 1
  JOIN source s   ON s.id = e.source_id
  WHERE a.status = 'approved';
