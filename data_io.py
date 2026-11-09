"""Shared file I/O for the curated dataset (entities, sources, relations).

Last edited: 2026-11-09: GRAPH_WITH_REVIEW_JSON; load_graph_json(with_review=) so --with-review never
overwrites the formal graph.json. 2026-11-02 (second pass): parse_evidence() splits the accumulated evidence text
into the fields an agent needs (latest verification URL, verbatim quote, verification date,
number of check rounds). The stored field stays as the audit trail; the parsed fields are
attached at build time, never written back. Earlier the same day: infer_role() (rule-based role for a belongs_to edge from the two node
types and the target's name) and year_from_claim() (the one year a claim states, else None),
shared by the migration, extract.ingest and audit_data.
2026-10-29: added duplicate_entities() (build/test guard against the same person
or institution under two ids) and write_text_lf(): generated text files (review queue,
checklist, graph.json, viewer.html) are written with LF on every OS, so the same data
gives byte-identical output on Windows and Linux. 2026-10-27: new module; consolidates
loaders that were duplicated across graph_build, agent, review_queue, extract and
tools/make_checklist; adds display_label()/short_label() implementing the EN-first /
ZH-first naming rule.

All functions take an explicit `root` (project directory) so callers in tools/
and experiments/ can pass their own path; defaults to this file's directory.
"""
import csv
import json
import re
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent
ENTITIES_CSV = "data/seed_entities.csv"
SOURCES_CSV = "data/sources.csv"
RELATIONS_JSONL = "data/raw_relations.jsonl"
GRAPH_JSON = "build/graph.json"
GRAPH_WITH_REVIEW_JSON = "build/graph_with_review.json"   # formal graph plus review edges, for inspection only

IN_GRAPH_STATUSES = ("auto", "approved")   # statuses that enter the formal graph


def load_entity_rows(root: Path = DEFAULT_ROOT) -> list[dict]:
    """Read seed_entities.csv. Returns a list of row dicts (id, type, name_zh, name_en)."""
    with open(root / ENTITIES_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_entity_names(root: Path = DEFAULT_ROOT) -> dict[str, str]:
    """Return {entity_id: name_zh} for quick display lookups."""
    return {row["id"]: row["name_zh"] for row in load_entity_rows(root)}


def load_source_rows(root: Path = DEFAULT_ROOT) -> list[dict]:
    """Read sources.csv. Returns a list of row dicts (id, name_zh, author, year, tier, kind, ref, relevance)."""
    with open(root / SOURCES_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_relation_dicts(root: Path = DEFAULT_ROOT) -> list[dict]:
    """Read raw_relations.jsonl as plain dicts (one relation per non-empty line)."""
    with open(root / RELATIONS_JSONL, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_relation_dicts(relations: list[dict], root: Path = DEFAULT_ROOT) -> None:
    """Rewrite raw_relations.jsonl with LF line endings (stable diffs across OSes)."""
    with open(root / RELATIONS_JSONL, "w", encoding="utf-8", newline="\n") as f:
        for relation in relations:
            f.write(json.dumps(relation, ensure_ascii=False) + "\n")


def load_graph_json(root: Path = DEFAULT_ROOT, with_review: bool = False) -> dict:
    """Read build/graph.json, or build/graph_with_review.json when with_review (node-link format)."""
    return json.loads((root / (GRAPH_WITH_REVIEW_JSON if with_review else GRAPH_JSON)).read_text(encoding="utf-8"))


def write_text_lf(path: Path, text: str) -> None:
    """Write UTF-8 text with LF line endings regardless of OS (Path.write_text would use CRLF on Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _primary_and_secondary(entity: dict) -> tuple[str, str]:
    """Order the two names by label_pref. Returns (primary, secondary); secondary may be ''."""
    zh, en = entity.get("name_zh") or "", entity.get("name_en") or ""
    pref = entity.get("label_pref") or ("zh" if not en else "en")
    if pref == "zh" or not en:
        return (zh or en), ""
    return (zh, en) if pref == "zh_en" else (en, zh)


def _latin_core(name: str) -> str:
    """Lower-case Latin letters/digits of a name with any parenthetical part removed."""
    without_parens = re.sub(r"[\(（][^\)）]*[\)）]", "", name)
    return re.sub(r"[^a-z0-9]", "", without_parens.lower())


def _names_overlap(a: str, b: str) -> bool:
    """True when the Latin core of one name is contained in the other's (e.g. 'LIFE 雜誌' vs 'LIFE magazine')."""
    ca, cb = _latin_core(a), _latin_core(b)
    return bool(ca and cb) and (ca in cb or cb in ca)


def display_label(entity: dict) -> str:
    """Reader-facing name following the project's naming rule.

    label_pref 'en'    (Western default)           → "English name (中譯)"
    label_pref 'zh_en' (Western, common in zh)     → "中文名 (English name)"
    label_pref 'zh'    (Chinese-world / East Asian) → "中文名" only
    The parenthesis is dropped when the two names overlap (e.g. "Kodachrome").
    Works for CSV rows and graph nodes alike.
    """
    primary, secondary = _primary_and_secondary(entity)
    if not secondary or _names_overlap(primary, secondary):
        return primary
    return f"{primary} ({secondary})"


def short_label(entity: dict) -> str:
    """Primary name only (no parenthesis); used where space is tight, e.g. graph canvas."""
    return _primary_and_secondary(entity)[0]


def duplicate_entities(rows: list[dict]) -> list[tuple[str, list[str]]]:
    """Entities that share (type, normalised English name) under different ids: [(name, [ids])].

    Catches the same person or institution being created twice under two ids (e.g. a second
    'Liz Wells'); a concept and a work with the same title are allowed.
    """
    seen: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        name = (row.get("name_en") or row.get("name_zh") or "").strip().lower()
        if name:
            seen.setdefault((row["type"], name), []).append(row["id"])
    return [(f"{t}:{name}", ids) for (t, name), ids in seen.items() if len(ids) > 1]


EVIDENCE_URL = re.compile(r"(?:查證來源|回查頁): (https?://\S+?)(?:｜|］|$)")
EVIDENCE_QUOTE = re.compile(r"原文:(.+?)(?:｜|$)")
EVIDENCE_DATE = re.compile(r"［(\d{4}-\d{2}-\d{2})")


def parse_evidence(evidence: str) -> dict:
    """Structured view of an evidence string: the latest URL, the latest verbatim quote, the latest check date
    and how many dated check rounds it records. Missing parts are None / 0."""
    text = evidence or ""
    urls, quotes, dates = EVIDENCE_URL.findall(text), EVIDENCE_QUOTE.findall(text), EVIDENCE_DATE.findall(text)
    return {"evidence_url": urls[-1] if urls else None,
            "quote": quotes[-1].strip() if quotes else None,
            "verified_on": max(dates) if dates else None,
            "check_rounds": len(dates)}


AWARD_NAME = re.compile(r"賞|獎|Award|Prize|Prix", re.IGNORECASE)
YEAR_IN_TEXT = re.compile(r"(?<!\d)(1[6-9]\d\d|20[0-2]\d)(?!\d)")
EVENT_ID_YEAR = re.compile(r"_(1[6-9]\d\d|20[0-2]\d)$")


def infer_role(source_type: str, target_type: str, target_name: str = "") -> str | None:
    """Role of a belongs_to edge from the node types (and an award-like target name). None if no rule fits."""
    if target_type == "concept":
        return "movement"
    if source_type == "work" and target_type == "person":
        return "author"
    if target_type == "institution" and AWARD_NAME.search(target_name or ""):
        return "award"
    if target_type == "work":
        return "contributor"
    if target_type == "event":
        return "participant" if source_type in ("person", "work") else "part_of"
    if source_type == "person" and target_type == "institution":
        return "member"
    if target_type == "institution":
        return "part_of"
    return None


def year_from_claim(claim: str, event_id: str = "") -> int | None:
    """The single year a claim states; for an event with a year suffix in its id, that year. None when ambiguous."""
    years = sorted(set(YEAR_IN_TEXT.findall(claim or "")))
    if len(years) == 1:
        return int(years[0])
    match = EVENT_ID_YEAR.search(event_id or "")
    return int(match.group(1)) if match else None


def relation_key(relation: dict) -> tuple[str, str, str]:
    """Identity of a relation for de-duplication: (source_id, target_id, kind)."""
    return relation["source_id"], relation["target_id"], relation["kind"]
