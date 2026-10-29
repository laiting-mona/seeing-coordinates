"""Data-pipeline audit: checks the curated dataset for integrity problems.

Last edited: 2026-10-29 — new tool. Written after an audit found hand-scored 'auto'
edges that the scoring formula cannot reproduce, event --belongs_to--> person edges
that reverse the project's direction convention, and canonical works with no author.

Hard errors (must be zero; test_core.py asserts this):
  missing entity / source ids, duplicate (source, target, kind), self-loops,
  duplicate entities, em-dashes in claims or names, event/institution --belongs_to--> person,
  'auto' edges whose confidence the formula cannot reproduce from the cited source's tier,
  relation tier different from its source's tier.
Warnings (reported, not fatal):
  approved edges with no URL anywhere, evidence URL different from the source's URL,
  isolated entities, works with no person author (magazines and translations excepted),
  sources no relation cites.
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
EM_DASH = "—"
URL_IN_EVIDENCE = re.compile(r"查證來源: (\S+?)(?:｜|$)")
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


def hard_errors(entities, sources, relations) -> dict[str, list]:
    errors = collections.defaultdict(list)
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
        match = URL_IN_EVIDENCE.search(r.get("evidence") or "")
        if r["status"] == "approved" and not match and not source.get("ref"):
            warn["approved with no URL (evidence or source)"].append(f"{r['source_id']} -{r['kind']}-> {r['target_id']}")
        if match and source.get("ref") and not match.group(1).startswith(source["ref"].split("?")[0][:40]):
            warn["evidence URL differs from the cited source's URL (second page or upgrade)"].append(r["source_ref"])
    warn["isolated entity"] = [i for i in entities if used[i] == 0]
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
        counted = collections.Counter(items) if name.startswith("evidence URL") else None
        if counted:
            lines += [f"- **{name}**:{len(items)} 條,來源:" + "、".join(f"`{k}`×{v}" for k, v in counted.most_common(MAX_LISTED))]
        else:
            lines += [f"- **{name}**:{len(items)}"] + [f"  - `{x}`" for x in items[:MAX_LISTED]]
    return "\n".join(lines) + "\n"


def audit(root: Path = ROOT, write: bool = True) -> tuple[dict, dict]:
    entities, sources, relations = load()
    errors, warns = hard_errors(entities, sources, relations), warnings(entities, sources, relations)
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
