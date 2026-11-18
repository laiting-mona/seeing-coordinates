"""Answer the evaluation question set once with the Python query.py, for the TypeScript parity check.

Last edited: 2026-11-17: first version.
Usage: python tools/python_answers.py [out.jsonl]   (default build/eval/python_answers.jsonl)
Then:  cd api && npm run build && node dist/src/eval/parity.js ../build/eval/python_answers.jsonl
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import run_eval_agent  # noqa: E402  (reuses its answer_all and record shape)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/eval/python_answers.jsonl"
    records = run_eval_agent.answer_all(run_eval_agent.load_questions())
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    print(f"{len(records)} 題 → {out}")


if __name__ == "__main__":
    main()
