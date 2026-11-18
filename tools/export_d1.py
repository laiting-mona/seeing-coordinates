"""Load the current flat files into the v2 schema (SQLite, the D1 dialect) and write a SQL file for Cloudflare D1.

Last edited: 2026-11-18: moved from the architecture v2 prototype into tools/; schema read from docs/schema-v2.sql;
writes build/d1/v2_data.sql (schema + rows, no transaction or PRAGMA lines, which D1 rejects) and a JSON report.
Usage: python tools/export_d1.py            (from the repo root)
The answer engine still reads build/graph.json; this copy is the queryable store the v2 pipeline will write to.
"""
import collections
import hashlib
import json
import re
import sqlite3
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "build" / "d1"
OUT = OUT_DIR / "v2.sqlite"
sys.path.insert(0, str(ROOT))
import data_io  # noqa: E402

TAG = re.compile(r"［(\d{4}-\d{2}-\d{2})\s*([^］]*)］")
URL = re.compile(r"(?:查證來源|回查頁): ?(https?://\S+?)(?:｜|］|\s|$)")
QUOTE = re.compile(r"原文[:：](.+?)(?:｜|$)")
ROUND = re.compile(r"第 ?(\d+) ?輪")
STATUS_MAP = {"auto": "approved", "approved": "approved", "review": "review", "rejected": "rejected"}


def action_of(label: str) -> tuple[str, str | None]:
    """Map a free-text tag label to a ledger action and the status it moved the edge to (heuristic)."""
    rules = [("剔除", "reject", "rejected"), ("降", "demote", "review"), ("待查證", "demote", "review"),
             ("換源", "resource", None), ("claim", "fix_claim", None), ("引句", "fix_quote", None),
             ("核可", "approve", "approved"), ("通過", "approve", "approved"), ("使用者決定", "approve", None)]
    for needle, action, to in rules:
        if needle in label:
            return action, to
    return "note", None


def norm(s: str) -> str:
    return re.sub(r"[\s·・．.\-‐–,，、:：()（）《》〈〉「」『』\"'’]", "", s or "").lower()


def evidence_pairs(text: str) -> list[dict]:
    """Walk the ｜-separated evidence text; pair each verification URL with the latest quote seen before it."""
    pairs, last_quote = [], None
    for seg in (text or "").split("｜"):
        q = QUOTE.search(seg)
        if q:
            last_quote = q.group(1).strip()
        for u in URL.findall(seg):
            pairs.append({"url": u, "quote": last_quote})
    return pairs


def load_schema(db: sqlite3.Connection) -> None:
    db.executescript((ROOT / "docs" / "schema-v2.sql").read_text(encoding="utf-8"))


def insert_rounds(db, rels) -> dict:
    seen = {}
    for r in rels:
        for date, label in TAG.findall(r["evidence"]):
            m = ROUND.search(label)
            if m and "擴充" in label:
                n = int(m.group(1))
                seen[n] = min(seen.get(n, date), date)
    for n, date in sorted(seen.items()):
        db.execute("INSERT INTO round VALUES (?,?,?,NULL)", (n, date, f"第 {n} 輪擴充"))
    return seen


def insert_entities(db, ents) -> int:
    for e in ents:
        etype = e["type"]
        db.execute("INSERT INTO entity (id,type,label_pref) VALUES (?,?,?)", (e["id"], etype, e["label_pref"]))
        for name, lang in ((e["name_zh"], "zh-Hant"), (e.get("name_en"), "en")):
            if name:
                db.execute("INSERT OR IGNORE INTO entity_name VALUES (?,?,?,?,?)", (e["id"], name, lang, "preferred", norm(name)))
    return len(ents)


def insert_sources(db, srcs) -> dict:
    by_url = {}
    for s in srcs:
        url = s["ref"] if s["ref"].startswith("http") else None
        host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.") if url else None
        kind = "pdf" if url and url.lower().endswith(".pdf") else ("web_page" if url else "book")
        year = int(s["year"]) if (s.get("year") or "").isdigit() else None
        tier = s["tier"] if s["tier"] in ("primary", "institution", "critic", "popular", "other") else "other"
        db.execute("INSERT INTO source (id,kind,title,author,year,url,host,tier) VALUES (?,?,?,?,?,?,?,?)",
                   (s["id"], kind, s["name_zh"], s["author"], year, url, host, tier))
        if url:
            by_url.setdefault(url, s["id"])
    return by_url


def source_for_url(db, by_url, url, tier) -> str:
    if url in by_url:
        return by_url[url]
    sid = "url_" + hashlib.sha1(url.encode()).hexdigest()[:10]
    host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    db.execute("INSERT OR IGNORE INTO source (id,kind,url,host,tier) VALUES (?,?,?,?,?)",
               (sid, "pdf" if url.lower().endswith(".pdf") else "web_page", url, host, tier))
    by_url[url] = sid
    return sid


def insert_relations(db, rels, by_url, stats) -> None:
    for r in rels:
        aid = hashlib.sha1("|".join([r["source_id"], r["kind"], r["target_id"], r.get("role") or ""]).encode()).hexdigest()[:16]
        try:
            db.execute("INSERT INTO assertion (id,subject_id,predicate,object_id,role,year,claim_zh,status,confidence) VALUES (?,?,?,?,?,?,?,?,?)",
                       (aid, r["source_id"], r["kind"], r["target_id"], r.get("role"), r.get("year"), r["claim"],
                        STATUS_MAP[r["status"]], r["confidence"]))
        except sqlite3.IntegrityError as exc:
            stats["assertion_rejected"].append([r["source_id"], r["kind"], r["target_id"], str(exc)])
            continue
        pairs = evidence_pairs(r["evidence"])
        if not pairs:
            db.execute("INSERT INTO evidence (id,assertion_id,source_id,quote,directness,is_current) VALUES (?,?,?,?,?,1)",
                       (aid + "_0", aid, r["source_ref"], None, "note"))
            stats["evidence_note_only"] += 1
        for i, p in enumerate(pairs):
            current = i == len(pairs) - 1
            sid = r["source_ref"] if current else source_for_url(db, by_url, p["url"], r["source_tier"])
            db.execute("INSERT INTO evidence (id,assertion_id,source_id,quote,directness,is_current) VALUES (?,?,?,?,?,?)",
                       (f"{aid}_{i}", aid, sid, p["quote"], "verbatim" if p["quote"] else "note", int(current)))
            stats["evidence_rows"] += 1
            stats["superseded_rows"] += not current
            if current:
                ref_url = db.execute("SELECT url FROM source WHERE id=?", (sid,)).fetchone()
                if ref_url and ref_url[0] and ref_url[0] != p["url"]:
                    stats["current_url_differs_from_source_ref"] += 1
        for date, label in TAG.findall(r["evidence"]):
            action, to = action_of(label)
            m = ROUND.search(label)
            db.execute("INSERT INTO review_event (assertion_id,round_id,on_date,actor,action,to_status,reason) VALUES (?,?,?,?,?,?,?)",
                       (aid, int(m.group(1)) if m and "擴充" in label else None, date, "migration", action, to, label[:200]))
            stats["review_events"] += 1
            stats["actions"][action] += 1


def integrity(db) -> dict:
    q = lambda sql: db.execute(sql).fetchall()
    return {
        "foreign_key_violations": len(q("PRAGMA foreign_key_check")),
        "approved_without_current_verbatim": q("""SELECT COUNT(*) FROM assertion a WHERE status='approved' AND NOT EXISTS
             (SELECT 1 FROM evidence e WHERE e.assertion_id=a.id AND e.is_current=1 AND e.directness='verbatim')""")[0][0],
        "formal_edge_rows": q("SELECT COUNT(*) FROM formal_edge")[0][0],
        "sources_unused": q("SELECT COUNT(*) FROM source s WHERE NOT EXISTS (SELECT 1 FROM evidence e WHERE e.source_id=s.id)")[0][0],
        "names_shared_by_two_entities": q("SELECT COUNT(*) FROM (SELECT norm FROM entity_name GROUP BY norm HAVING COUNT(DISTINCT entity_id)>1)")[0][0],
        "table_rows": {t: q(f"SELECT COUNT(*) FROM {t}")[0][0] for t in
                       ("entity", "entity_name", "source", "assertion", "evidence", "review_event", "round")},
    }


def table_order(db: sqlite3.Connection) -> list[str]:
    """Tables sorted so every table comes after the tables its foreign keys point to (D1 enforces foreign keys)."""
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    deps = {t: {r[2] for r in db.execute(f"PRAGMA foreign_key_list({t})")} - {t} for t in tables}
    ordered: list[str] = []
    while len(ordered) < len(tables):
        ready = sorted(t for t in tables if t not in ordered and deps[t] <= set(ordered))
        if not ready:
            raise ValueError(f"foreign key cycle among {sorted(set(tables) - set(ordered))}")
        ordered.extend(ready)
    return ordered


def insert_lines(db: sqlite3.Connection, table: str) -> list[str]:
    """One INSERT statement per row, values quoted by SQLite itself."""
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
    sql = f"SELECT 'INSERT INTO {table} ({', '.join(cols)}) VALUES (' || " + " || ', ' || ".join(f"quote({c})" for c in cols) + " || ');' FROM " + table
    return [r[0] for r in db.execute(sql)]


def write_sql(db: sqlite3.Connection, path: Path) -> int:
    """Schema text, then rows table by table in foreign-key order; returns the number of INSERT lines."""
    schema = (ROOT / "docs" / "schema-v2.sql").read_text(encoding="utf-8")
    lines = [line for line in schema.strip().splitlines() if not line.startswith("PRAGMA")]   # D1 enforces foreign keys itself
    rows = 0
    for table in table_order(db):
        batch = insert_lines(db, table)
        rows += len(batch)
        lines.extend(batch)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    db = sqlite3.connect(OUT)
    load_schema(db)
    ents, srcs, rels = data_io.load_entity_rows(ROOT), data_io.load_source_rows(ROOT), data_io.load_relation_dicts(ROOT)
    stats = collections.defaultdict(int)
    stats["assertion_rejected"], stats["actions"] = [], collections.Counter()
    stats["malformed_source_rows"] = [s["id"] for s in srcs if None in s]
    stats["rounds"] = insert_rounds(db, rels)
    stats["entities"] = insert_entities(db, ents)
    by_url = insert_sources(db, srcs)
    insert_relations(db, rels, by_url, stats)
    db.commit()
    inserts = write_sql(db, OUT_DIR / "v2_data.sql")
    report = {"stats": stats, "integrity": integrity(db), "insert_rows": inserts,
              "sql_bytes": (OUT_DIR / "v2_data.sql").stat().st_size}
    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=dict), encoding="utf-8")
    print(json.dumps({"insert_rows": inserts, "table_rows": report["integrity"]["table_rows"], "sql_bytes": report["sql_bytes"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
