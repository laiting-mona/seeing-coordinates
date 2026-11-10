"""Turn recorded evaluation runs into one workbook for reading and scoring.

Last edited: 2026-11-10 (seconds and ui_extra columns).

Usage: python tools/eval_report.py [out.xlsx]   (default build/eval/eval_answers.xlsx; needs openpyxl)

Reads data/eval_questions.csv, build/eval/agent_runs.jsonl (from tools/run_eval_agent.py) and, when it
exists, build/eval/external_runs.jsonl (one JSON object per external chat: id, platform, model,
thinking, run, answer, seconds, recorded_at, and optionally ui_extra: interface text kept apart from
the answer, such as Claude's thinking-status lines or Gemini's follow-up chips). Sheets: 我們的Agent
(one row per question, the five answers side by side, whether they agree, intent, resolved nodes,
cited URLs), 外部平台 (one row per recorded chat), 摘要 (counts by purpose, sentence form and intent,
and records per external configuration).
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_CSV = ROOT / "data/eval_questions.csv"
AGENT_RUNS = ROOT / "build/eval/agent_runs.jsonl"
EXTERNAL_RUNS = ROOT / "build/eval/external_runs.jsonl"
DEFAULT_OUT = ROOT / "build/eval/eval_answers.xlsx"
QUESTION_COLS = ["編號", "格", "角色", "需求面向", "變體", "用途", "強弱連結", "句型", "問句", "預期行為"]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def agent_rows(questions: list[dict], runs: list[dict]) -> list[list]:
    by_q = defaultdict(dict)
    for r in runs:
        by_q[r["id"]][r["run"]] = r
    n_runs = max((r["run"] for r in runs), default=0)
    rows = []
    for q in questions:
        rec = by_q.get(q["編號"], {})
        first = rec.get(1, {})
        answers = [rec.get(i, {}).get("answer", "") for i in range(1, n_runs + 1)]
        same = len({rec.get(i, {}).get("sha256") for i in range(1, n_runs + 1)}) == 1
        rows.append([q[c] for c in QUESTION_COLS] + [first.get("intent", ""), ", ".join(first.get("resolved", [])),
                     "是" if same else "否", len(first.get("urls", []))] + answers + ["\n".join(first.get("urls", []))])
    return rows


def external_rows(questions: list[dict], runs: list[dict]) -> list[list]:
    by_id = {q["編號"]: q for q in questions}
    rows = []
    for r in sorted(runs, key=lambda r: (r["id"], r["platform"], r.get("model", ""), r.get("thinking", ""), r["run"])):
        q = by_id.get(r["id"], {})
        rows.append([r["id"], q.get("格", ""), q.get("變體", ""), q.get("問句", ""), r["platform"], r.get("model", ""),
                     r.get("thinking", ""), r["run"], r.get("answer", ""), r.get("seconds", ""), r.get("ui_extra", ""),
                     r.get("recorded_at", "")])
    return rows


def summary_rows(questions: list[dict], runs: list[dict], external: list[dict]) -> list[list]:
    by_q = {q["編號"]: q for q in questions}
    first = [r for r in runs if r["run"] == 1]
    per_q = defaultdict(set)
    for r in runs:
        per_q[r["id"]].add(r["sha256"])
    rows = [["我們的 Agent", "題數", len(first)], ["我們的 Agent", "每題跑幾次", max((r["run"] for r in runs), default=0)],
            ["我們的 Agent", "五次回答完全相同的題數", sum(1 for v in per_q.values() if len(v) == 1)],
            ["我們的 Agent", "解析不到任何節點", sum(1 for r in first if not r["resolved"])],
            ["我們的 Agent", "回答附至少一個查證網址", sum(1 for r in first if r["urls"])]]
    for field in ["用途", "句型"]:
        unresolved = Counter(by_q[r["id"]][field] for r in first if not r["resolved"])
        total = Counter(by_q[r["id"]][field] for r in first)
        rows += [[f"解析失敗率(依{field})", k, f"{unresolved[k]}/{total[k]}"] for k in sorted(total)]
    rows += [["意圖分布", k, v] for k, v in Counter(r["intent"] for r in first).most_common()]
    combos = Counter((r["platform"], r.get("model", ""), r.get("thinking", "")) for r in external)
    rows += [["外部平台紀錄", f"{p} / {m} / {t}", n] for (p, m, t), n in sorted(combos.items())]
    return rows


def write_workbook(out: Path, sheets: dict[str, tuple[list[str], list[list]]]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    wb.remove(wb.active)
    for title, (header, rows) in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(header)
        for row in rows:
            ws.append(row)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDDDDD")
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in list(col)[:60])
            ws.column_dimensions[col[0].column_letter].width = min(60, max(8, width * 0.9))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    with open(QUESTIONS_CSV, encoding="utf-8") as f:
        questions = list(csv.DictReader(f))
    runs, external = load_jsonl(AGENT_RUNS), load_jsonl(EXTERNAL_RUNS)
    n_runs = max((r["run"] for r in runs), default=0)
    agent_header = QUESTION_COLS + ["意圖", "解析節點", "五次一致", "網址數"] + [f"回答{i}" for i in range(1, n_runs + 1)] + ["查證網址"]
    sheets = {"我們的Agent": (agent_header, agent_rows(questions, runs)),
              "外部平台": (["編號", "格", "變體", "問句", "平台", "模型", "思考層級", "第幾次", "回答", "秒數", "介面附帶文字", "記錄時間"],
                       external_rows(questions, external)),
              "摘要": (["項目", "值", "數量"], summary_rows(questions, runs, external))}
    write_workbook(out, sheets)
    print(f"{out}: agent {len(runs)} records, external {len(external)} records")


if __name__ == "__main__":
    main()
