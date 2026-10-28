"""Export status=review relations, with investigation notes, to docs/review-queue.md.

Last edited: 2026-10-27 — module-level script turned into functions + main();
loaders from data_io; names use display_label.

The program only assembles; decisions stay with the human reviewer.
Usage: python review_queue.py
"""
import json
from pathlib import Path

import data_io

ROOT = Path(__file__).resolve().parent
NOTES_PATH = ROOT / "data/review_notes.json"
OUTPUT_MD = ROOT / "docs/review-queue.md"


def load_notes(path: Path = NOTES_PATH) -> dict:
    """Investigation notes keyed by 'source->target:kind'; empty when the file is absent."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def render_entry(relation: dict, note: dict, label: dict[str, str]) -> list[str]:
    """Markdown block for one pending relation."""
    name = lambda i: label.get(i, i)
    return [f"## {name(relation['source_id'])} → {name(relation['target_id'])}（{relation['kind']}）",
            f"- 可信度:{relation['confidence']}　來源層:{relation['source_tier']}　出處:{relation.get('source_ref', '')}",
            f"- 主張:{relation['claim']}",
            f"- 調查紀錄:{note.get('investigation', '(待補)')}",
            f"- 參考來源:{'; '.join(note.get('sources', [])) or '(無)'}",
            f"- 我的建議:{note.get('recommendation', '(待補)')}",
            f"- **你的決定:** {note.get('decision') or '________'}", ""]


def build_queue_markdown(pending: list[dict], notes: dict, label: dict[str, str]) -> str:
    header = ["# 待人工判斷佇列（review queue）", "",
              f"共 {len(pending)} 條。程式自動彙整,判斷與決定由你填。", "",
              "> 每條的「你的決定」欄預設空白。你確認後填 approved / rejected / 重構,我再據此更新圖。", ""]
    body = [line for r in pending
            for line in render_entry(r, notes.get(f"{r['source_id']}->{r['target_id']}:{r['kind']}", {}), label)]
    return "\n".join(header + body)


def main() -> None:
    label = {row["id"]: data_io.display_label(row) for row in data_io.load_entity_rows(ROOT)}
    pending = [r for r in data_io.load_relation_dicts(ROOT) if r.get("status") == "review"]
    OUTPUT_MD.parent.mkdir(exist_ok=True)
    OUTPUT_MD.write_text(build_queue_markdown(pending, load_notes(), label), encoding="utf-8")
    print(f"寫出 {len(pending)} 條待判斷關係 → {OUTPUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
