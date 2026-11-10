"""Run the evaluation question set through our agent (query.py) several times and record every answer.

Last edited: 2026-11-10.

Usage: python tools/run_eval_agent.py [runs]   (default 5)

Each run is a separate Python process, so nothing carries over between runs (the same "no history"
condition the external chat assistants are tested under). Per question and run we keep the intent,
the resolved node ids, the rendered answer text, the source URLs cited in the answer and a sha256 of
the text. Output: build/eval/agent_runs.jsonl (one line per question x run) and
build/eval/agent_summary.json (counts, and whether the runs agree). Our agent has no sampling and no
thinking-level setting, so a single configuration is run.
"""
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_CSV = ROOT / "data/eval_questions.csv"
OUT_DIR = ROOT / "build/eval"
RUNS_JSONL = OUT_DIR / "agent_runs.jsonl"
SUMMARY_JSON = OUT_DIR / "agent_summary.json"


def load_questions() -> list[dict]:
    with open(QUESTIONS_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cited_urls(result: dict) -> list[str]:
    """Collect the evidence URLs an answer exposes, in order, without duplicates."""
    found = []

    def walk(value):
        if isinstance(value, dict):
            url = value.get("url")
            if isinstance(url, str) and url.startswith("http") and url not in found:
                found.append(url)
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(result)
    return found


def answer_all(questions: list[dict]) -> list[dict]:
    """Answer every question in this process (called inside a fresh child process per run)."""
    sys.path.insert(0, str(ROOT))
    import query  # loaded here so each child process builds its own engine
    records = []
    for q in questions:
        intent, ids, result = query.answer(q["問句"])
        text = query.render(result)
        records.append({"id": q["編號"], "intent": intent, "resolved": ids[:4], "answer": text,
                        "urls": cited_urls(result), "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    return records


def run_once() -> list[dict]:
    """Start a fresh interpreter that answers all questions and returns JSON on stdout."""
    code = ("import json,sys; sys.path.insert(0, r'%s'); import importlib.util as u; "
            "s=u.spec_from_file_location('r', r'%s'); m=u.module_from_spec(s); s.loader.exec_module(m); "
            "print(json.dumps(m.answer_all(m.load_questions()), ensure_ascii=False))") % (ROOT / "tools", __file__)
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return json.loads(out.stdout)


def summarize(questions: list[dict], runs: list[list[dict]]) -> dict:
    by_q = {q["編號"]: q for q in questions}
    agree = sum(1 for i in range(len(questions)) if len({r[i]["sha256"] for r in runs}) == 1)
    first = runs[0]
    return {
        "questions": len(questions), "runs": len(runs), "all_runs_identical": agree,
        "intent": dict(Counter(r["intent"] for r in first)),
        "unresolved": sum(1 for r in first if not r["resolved"]),
        "answers_with_url": sum(1 for r in first if r["urls"]),
        "by_purpose_unresolved": dict(Counter(by_q[r["id"]]["用途"] for r in first if not r["resolved"])),
    }


def write_outputs(questions: list[dict], runs: list[list[dict]], summary: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUNS_JSONL, "w", encoding="utf-8", newline="\n") as f:
        for run_index, records in enumerate(runs, 1):
            for r in records:
                f.write(json.dumps({"run": run_index, **r}, ensure_ascii=False) + "\n")
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    questions = load_questions()
    runs = [run_once() for _ in range(n)]
    summary = summarize(questions, runs)
    write_outputs(questions, runs, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
