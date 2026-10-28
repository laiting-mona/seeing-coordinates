"""Extraction pipeline on the subscription route (no paid API calls).

Last edited: 2026-10-27 — loaders moved to data_io; template read inside the function;
main() dispatches by mode.

  prepare  write one prompt file per source to build/prompts/<source_id>.txt; paste your
           passage, run it in the Claude subscription UI, save the JSON to build/responses/<id>.json
  ingest   validate those JSON files with the schema, score and route them, append new
           relations to data/raw_relations.jsonl (de-duplicated by (source, target, kind))
Usage: python extract.py [prepare|ingest]
"""
import json
import sys
from pathlib import Path

import data_io
from authority import auto_confidence, route
from schema import Relation

ROOT = Path(__file__).resolve().parent
PROMPTS_DIR, RESPONSES_DIR = ROOT / "build/prompts", ROOT / "build/responses"
TEMPLATE_PATH = ROOT / "prompts/extract.txt"


def prompt_for_source(template: str, source: dict) -> str:
    """Compose the extraction prompt for one source row."""
    return (template + f"\n\n# 來源:{source['name_zh']}（{source.get('author', '')}）"
            f"\n# tier: {source['tier']}  ref: {source['id']}\n"
            f"# 在下面貼入你讀到的相關段落,再送進 Claude:\n\n<<貼段落>>\n")


def prepare(root: Path = ROOT) -> int:
    """Write one prompt file per source. Returns the number written."""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    sources = data_io.load_source_rows(root)
    for source in sources:
        (PROMPTS_DIR / f"{source['id']}.txt").write_text(prompt_for_source(template, source), encoding="utf-8")
    return len(sources)


def to_relation(raw: dict) -> Relation:
    """Fill confidence/status for an extracted relation dict and validate it."""
    raw.setdefault("confidence", auto_confidence(raw.get("source_tier", "other"),
                                                 raw.get("n_sources", 1), raw.get("directness", 1.0)))
    raw["status"] = route(raw["confidence"])
    return Relation(**{k: raw[k] for k in Relation.model_fields if k in raw})


def ingest(root: Path = ROOT) -> int:
    """Append new relations from build/responses/*.json. Returns the number added."""
    existing = data_io.load_relation_dicts(root)
    seen = {data_io.relation_key(r) for r in existing}
    added = []
    for response_file in sorted(RESPONSES_DIR.glob("*.json")):
        payload = json.loads(response_file.read_text(encoding="utf-8"))
        for raw in payload.get("relations", []):
            relation = to_relation(raw)
            key = (relation.source_id, relation.target_id, relation.kind)
            if key not in seen:
                added.append(relation.model_dump())
                seen.add(key)
    if added:
        data_io.write_relation_dicts(existing + added, root)
    return len(added)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if mode == "ingest":
        print(f"併入 {ingest()} 條新關係 → {data_io.RELATIONS_JSONL}")
    else:
        print(f"已產生 {prepare()} 份 prompt 於 {PROMPTS_DIR}")


if __name__ == "__main__":
    main()
