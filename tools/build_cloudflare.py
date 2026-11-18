"""Assemble the static files the Cloudflare Worker serves (api/public/) from the current build outputs.

Last edited: 2026-11-18: first version. Run after graph_build.py and build_viewer.py, from the repo root:
    python tools/build_cloudflare.py
then build the browser engine with `npm run site` inside api/ (esbuild writes api/public/engine.js).
Writes: index.html, config.js, log.js (copied from site/), data.js (question list and source labels for the page),
graph.json (the snapshot the browser and /api/answer both read), map.html (the graph viewer).
"""
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "api" / "public"
SITE_FILES = ("index.html", "config.js", "log.js")


def copy_site() -> None:
    """Hand-written page files, unchanged."""
    for name in SITE_FILES:
        shutil.copy(ROOT / "site" / name, OUT / name)


def write_data_js() -> None:
    """Question bank (for the sidebar and search) and source labels (for 出處 links), as two globals."""
    qs = [[r["編號"], r["問句"], r["角色"], r["需求面向"]]
          for r in csv.DictReader(open(ROOT / "data" / "eval_questions.csv", encoding="utf-8"))]
    src = {r["id"]: [r["name_zh"], r["author"], r["year"], r["tier"], r["ref"]]
           for r in csv.DictReader(open(ROOT / "data" / "sources.csv", encoding="utf-8"))}
    body = "window.QS=" + json.dumps(qs, ensure_ascii=False, separators=(",", ":")) + ";\n"
    body += "window.SRC=" + json.dumps(src, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (OUT / "data.js").write_text(body, encoding="utf-8")


def write_graph() -> None:
    """The engine's snapshot, re-serialised without whitespace."""
    graph = json.loads((ROOT / "build" / "graph.json").read_text(encoding="utf-8"))
    (OUT / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_map() -> None:
    """build_viewer.py output as a full document, with the project's current name."""
    viewer = (ROOT / "build" / "viewer.html").read_text(encoding="utf-8").replace("觀看的座標", "觀看的坐標")
    head = '<!doctype html>\n<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
    (OUT / "map.html").write_text(head + viewer, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    copy_site()
    write_data_js()
    write_graph()
    write_map()
    for path in sorted(OUT.iterdir()):
        print(f"{path.name:12} {path.stat().st_size:>10,}")


if __name__ == "__main__":
    main()
