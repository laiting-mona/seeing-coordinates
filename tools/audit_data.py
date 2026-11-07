"""Data-pipeline audit: checks the curated dataset for integrity problems.

Last edited: 2026-11-07: weak-host warning (wikis, blogs, booksellers, auction houses). 2026-11-03: the URL checks read the latest evidence URL through data_io.parse_evidence (the same view
graph_build exposes); ("award", "part_of") tolerated. 2026-11-02 (second pass): warning for a formal edge whose evidence has no parseable verbatim
quote (self-primary excepted). Earlier the same day: role / year rules. Hard errors: a belongs_to edge without a role, a
role on another kind, a role that contradicts the node types (the rule in data_io.infer_role),
a year outside 1500-2100. Warning: a year the claim does not state and neither the event id nor (for an author edge) the work's
title carries. 2026-10-30: four new warnings from the pipeline check: approved edges whose
confidence differs from the tier formula, formal edges resting only on a book (no URL, no
page), verification URLs on a dev / staging / test host, and entities with no formal edge
(isolated dots in the viewer).
2026-10-29 (second pass): two new hard errors: approved/auto edges whose only
verification URLs are Wikipedia / Baidu Baike / Namu wiki (not acceptable hubs), and data
files with mixed line endings; a new warning for approved edges resting on an other/popular-
tier source; self-primary edges (a work citing itself, tier primary) no longer count as
"approved with no URL". First version the same day: written after an audit
found hand-scored 'auto' edges that the scoring formula cannot reproduce, event
--belongs_to--> person edges that reverse the direction convention, and works with no author.

Hard errors (must be zero; test_core.py asserts this):
  missing entity / source ids, duplicate (source, target, kind), self-loops,
  duplicate entities, em-dashes in claims or names, event/institution --belongs_to--> person,
  'auto' edges whose confidence the formula cannot reproduce from the cited source's tier,
  relation tier different from its source's tier, approved/auto edges verified only by a
  wiki page, mixed line endings in a data file, belongs_to without role / role on another kind /
  role contradicting the node types.
Warnings (reported, not fatal):
  approved edges with no URL anywhere (self-primary excepted), approved edges on an
  other/popular-tier source, evidence URL different from the source's URL, isolated entities,
  entities with no formal edge, works with no person author (magazines and translations
  excepted), sources no relation cites, approved confidence off the tier formula, formal
  edges resting only on a book, verification URLs on a dev/staging/test host.
Writes docs/data-audit.md. Usage: python tools/audit_data.py
"""
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import data_io  # noqa: E402
from authority import AUTO_THRESHOLD, auto_confidence  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

OUTPUT_MD = ROOT / "docs/data-audit.md"
EM_DASH = "\u2014"   # em-dash, written as an escape
URL_IN_EVIDENCE = re.compile(r"查證來源: (\S+?)(?:｜|$)")
WIKI_HOSTS = ("wikipedia.org", "baike.baidu.com", "namu.wiki")   # not acceptable verification hubs
NON_PRODUCTION_HOST = re.compile(r"(^|[./])(dev|staging\d*|test\d*)[.-]")   # e.g. staging2.phaidon.com, test01.ku.dk
# hosts the verification rules do not accept: wikis, personal blogs, booksellers, auction houses, social and
# document-sharing sites. Institution-run blogs are listed in INSTITUTION_BLOGS and pass.
WEAK_HOST = re.compile(r"wiki|blog|wordpress|medium\.com|substack|scribd|pinterest|amazon\.|abebooks|ebay\.|sothebys|phillips\.com|christies|artsy\.net|academia\.edu|researchgate|issuu|tumblr|facebook|instagram|youtube", re.IGNORECASE)
INSTITUTION_BLOGS = {"blogs.getty.edu", "blogs.ncl.ac.uk", "blog.scienceandmediamuseum.org.uk", "samblog.seattleartmuseum.org", "blog.mcny.org", "blog.photoeye.com"}
FORMAL = ("approved", "auto")
# role pairs (stored, rule) a reviewer may legitimately choose: a person -> institution edge can be an award only
# when the name says so, so these are the cases where the stored role is a deliberate refinement of the rule
# (("award", "part_of") covers a work that won a prize given by an institution not named as one, e.g. a biennale's Golden Lion).
ROLE_TOLERATED = {("award", "member"), ("award", "part_of"), ("member", "part_of"), ("participant", "contributor"), ("contributor", "participant")}
DATA_FILES = ("data/seed_entities.csv", "data/sources.csv", "data/raw_relations.jsonl")
# Works that legitimately have no person author edge: periodicals, series, translations, anthologies of others.
AUTHORLESS_OK_TYPES = ("magazine", "journal", "雜誌", "期刊", "季刊", "叢書", "series", "文庫", "Chinese ed", "中譯", "Illuminations")
MAX_LISTED = 40


def load():
    entities = {row["id"]: row for row in data_io.load_entity_rows(ROOT)}
    sources = {row["id"]: row for row in data_io.load_source_rows(ROOT)}
    relations = data_io.load_relation_dicts(ROOT)
    return entities, sources, relations


def reproducible(relation: dict, source_tier: str) -> bool:
    """An 'auto' edge must be explainable by the formula from its one cited source (directness <= 1)."""
    return AUTO_THRESHOLD <= relation["confidence"] <= auto_confidence(source_tier, 1, 1.0) + 1e-9


def verification_urls(relation: dict, source: dict) -> list[str]:
    """Every URL offered as verification: '查證來源' entries in evidence plus the cited source's own URL."""
    urls = URL_IN_EVIDENCE.findall(relation.get("evidence") or "")
    return urls + ([source["ref"]] if source.get("ref", "").startswith("http") else [])


def wiki_only(relation: dict, source: dict) -> bool:
    urls = verification_urls(relation, source)
    return bool(urls) and all(any(host in url for host in WIKI_HOSTS) for url in urls)


def is_weak_host(url: str) -> bool:
    """True when the host is one the rules reject, unless it is an institution-run blog or a scan of the
    primary text itself (Monoskop /images/ files, which the rules accept as the text citing itself)."""
    host = re.sub(r"^https?://", "", url).split("/")[0].lower()
    if host in INSTITUTION_BLOGS or "/images/" in url or "File:" in url:
        return False
    return bool(WEAK_HOST.search(host))


def is_self_primary(relation: dict, source: dict) -> bool:
    """A primary work cited as its own source (authorship or concepts the work itself states)."""
    return source.get("tier") == "primary" and relation["source_ref"] == relation["source_id"]


def mixed_line_endings(root: Path) -> list[str]:
    bad = []
    for name in DATA_FILES:
        data = (root / name).read_bytes()
        crlf, lf = data.count(b"\r\n"), data.count(b"\n")
        if 0 < crlf < lf:
            bad.append(f"{name} (CRLF {crlf} / LF {lf})")
    return bad


def hard_errors(entities, sources, relations, root: Path = ROOT) -> dict[str, list]:
    errors = collections.defaultdict(list)
    errors["mixed line endings in data file"] = mixed_line_endings(root)
    keys = collections.Counter(data_io.relation_key(r) for r in relations)
    errors["duplicate relation"] = [k for k, n in keys.items() if n > 1]
    errors["duplicate entity"] = data_io.duplicate_entities(list(entities.values()))
    for e in entities.values():
        if EM_DASH in (e["name_zh"] or "") + (e["name_en"] or ""):
            errors["em-dash in entity name"].append(e["id"])
    for r in relations:
        s, t, k = data_io.relation_key(r)
        label = f"{s} -{k}-> {t}"
        if s not in entities or t not in entities:
            errors["missing entity id"].append(label)
            continue
        source = sources.get(r["source_ref"])
        if source is None:
            errors["missing source id"].append(f"{label} [{r['source_ref']}]")
            continue
        if s == t:
            errors["self-loop"].append(label)
        if EM_DASH in r["claim"] + (r.get("evidence") or ""):
            errors["em-dash in claim/evidence"].append(label)
        if k == "belongs_to" and entities[t]["type"] == "person" and entities[s]["type"] in ("event", "institution", "concept"):
            errors["reversed belongs_to (event/institution/concept -> person)"].append(label)
        if r["source_tier"] != source["tier"]:
            errors["relation tier differs from source tier"].append(f"{label} ({r['source_tier']} vs {source['tier']})")
        if r["status"] == "auto" and not reproducible(r, source["tier"]):
            errors["'auto' confidence not reproducible from source tier"].append(
                f"{label} (conf {r['confidence']}, source {r['source_ref']} = {source['tier']})")
        if r["status"] in ("approved", "auto") and wiki_only(r, source):
            errors["approved/auto edge verified only by a wiki page"].append(label)
        role = r.get("role")
        if k == "belongs_to" and not role:
            errors["belongs_to without role"].append(label)
        if k != "belongs_to" and role:
            errors["role on a non-belongs_to edge"].append(f"{label} ({role})")
        if k == "belongs_to" and role:
            target = entities[t]
            expected = data_io.infer_role(entities[s]["type"], target["type"], f"{target['name_zh']} {target['name_en'] or ''}")
            if expected and role != expected and not (role, expected) in ROLE_TOLERATED:
                errors["role contradicts the node types"].append(f"{label} ({role}, rule says {expected})")
    return {k: v for k, v in errors.items() if v}


def warnings(entities, sources, relations) -> dict[str, list]:
    warn = collections.defaultdict(list)
    used = collections.Counter()
    authored = set()
    for r in relations:
        used[r["source_id"]] += 1
        used[r["target_id"]] += 1
        if r["kind"] == "belongs_to" and entities.get(r["target_id"], {}).get("type") == "person":
            authored.add(r["source_id"])
        source = sources.get(r["source_ref"], {})
        latest_url = data_io.parse_evidence(r.get("evidence") or "")["evidence_url"]   # same view the build exposes
        if r["status"] == "approved" and not latest_url and not source.get("ref") and not is_self_primary(r, source):
            warn["approved with no URL (evidence or source)"].append(f"{r['source_id']} -{r['kind']}-> {r['target_id']}")
        if r["status"] == "approved" and source.get("tier") in ("other", "popular"):
            warn["approved edge resting on an other/popular-tier source (aggregator or legacy label)"].append(r["source_ref"])
        if latest_url and source.get("ref") and not latest_url.startswith(source["ref"].split("?")[0][:40]):
            warn["evidence URL differs from the cited source's URL (second page or upgrade)"].append(r["source_ref"])
        label = f"{r['source_id']} -{r['kind']}-> {r['target_id']}"
        if r["status"] == "approved" and abs(r["confidence"] - auto_confidence(source.get("tier", "other"), 1, 1.0)) > 1e-6:
            warn["approved confidence differs from the tier formula"].append(f"{label} ({r['confidence']})")
        if r.get("year"):
            event = r["target_id"] if entities.get(r["target_id"], {}).get("type") == "event" else (
                r["source_id"] if entities.get(r["source_id"], {}).get("type") == "event" else "")
            title_year = str(r["year"]) in (entities.get(r["source_id"], {}).get("name_en") or "") and r.get("role") == "author"
            if str(r["year"]) not in (r.get("claim") or "") and not data_io.EVENT_ID_YEAR.search(event) and not title_year:
                warn["year not stated in the claim or the event id"].append(f"{label} ({r['year']})")
        if r["status"] in FORMAL and not data_io.parse_evidence(r.get("evidence"))["quote"] and not is_self_primary(r, source):
            warn["formal edge without a verbatim quote in evidence"].append(label)
        urls = verification_urls(r, source)
        if r["status"] in FORMAL and not urls and not is_self_primary(r, source):
            warn["formal edge resting only on a book (no URL, no page): cited source"].append(r["source_ref"])
        if r["status"] in FORMAL and urls and NON_PRODUCTION_HOST.search(re.sub(r"^https?://", "", urls[-1])):
            warn["verification URL on a dev/staging/test host"].append(f"{label}: {urls[-1]}")
        if r["status"] in FORMAL and urls and is_weak_host(urls[-1]):
            warn["verification URL on a wiki, blog, bookseller or auction host (primary-text scans excepted)"].append(f"{label}: {urls[-1]}")
    formal_used = collections.Counter(n for r in relations if r["status"] in FORMAL for n in (r["source_id"], r["target_id"]))
    warn["isolated entity"] = [i for i in entities if used[i] == 0]
    warn["entity with no formal edge (isolated dot in the viewer)"] = [i for i in entities if used[i] and not formal_used[i]]
    warn["work with no person author"] = [
        i for i, e in entities.items() if e["type"] == "work" and i not in authored
        and not any(tag.lower() in (e["name_zh"] + " " + e["name_en"]).lower() for tag in AUTHORLESS_OK_TYPES)]
    cited = {r["source_ref"] for r in relations}
    warn["source cited by no relation"] = [s for s in sources if s not in cited]
    return {k: v for k, v in warn.items() if v}


def render(errors, warns, entities, sources, relations) -> str:
    status = collections.Counter(r["status"] for r in relations)
    lines = ["# 資料流程稽核(tools/audit_data.py 產生)", "",
             f"實體 {len(entities)}、來源 {len(sources)}、關係 {len(relations)}"
             f"(auto {status['auto']}、approved {status['approved']}、review {status['review']}、rejected {status['rejected']})。", "",
             f"## 硬性錯誤:{sum(len(v) for v in errors.values())} 項", ""]
    for name, items in errors.items():
        lines += [f"- **{name}**:{len(items)}"] + [f"  - `{x}`" for x in items[:MAX_LISTED]]
    if not errors:
        lines.append("無。")
    lines += ["", f"## 警告:{sum(len(v) for v in warns.values())} 項(不阻擋建圖,列出供人工判斷)", ""]
    for name, items in warns.items():
        counted = collections.Counter(items) if name.startswith(("evidence URL", "approved edge resting", "formal edge resting")) else None
        if counted:
            lines += [f"- **{name}**:{len(items)} 條,來源:" + "、".join(f"`{k}`×{v}" for k, v in counted.most_common(MAX_LISTED))]
        else:
            lines += [f"- **{name}**:{len(items)}"] + [f"  - `{x}`" for x in items[:MAX_LISTED]]
    return "\n".join(lines) + "\n"


def audit(root: Path = ROOT, write: bool = True) -> tuple[dict, dict]:
    entities, sources, relations = load()
    errors, warns = hard_errors(entities, sources, relations, root), warnings(entities, sources, relations)
    if write:
        data_io.write_text_lf(OUTPUT_MD, render(errors, warns, entities, sources, relations))
    return errors, warns


def main() -> None:
    errors, warns = audit()
    print(f"硬性錯誤 {sum(len(v) for v in errors.values())} 項;警告 {sum(len(v) for v in warns.values())} 項 → {OUTPUT_MD.relative_to(ROOT)}")
    for name, items in errors.items():
        print(f"  ✗ {name}: {len(items)}")
    for name, items in warns.items():
        print(f"  ! {name}: {len(items)}")


if __name__ == "__main__":
    main()
