"""Minimal regression tests (plain assert, no pytest) for the core behaviour.

Last edited: 2026-11-10: answers must not change with Python's per-process hash seed (two child
processes with different PYTHONHASHSEED answer the same questions identically).
2026-10-29: data audit (tools/audit_data.py) must report zero hard errors;
entity-table integrity check (no duplicate person/institution under two
ids). 2026-10-28: added checks that institution rosters never top a photographer's
recommendations and that a photographer's own works are reachable (inbound edges). 2026-10-27: tests grouped into functions; added checks for
display_label naming rule, approved-as-in-graph labelling and the faster resolver.
Usage: python test_core.py
"""
import os
import subprocess
import sys
from pathlib import Path

import networkx as nx
from pydantic import ValidationError

import authority
import data_io
import graph_build
import metrics
import schema

# Windows consoles default to cp950 and cannot print ✓ or CJK; force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

passed = 0


def check(name: str, condition: bool) -> None:
    global passed
    assert condition, "FAIL: " + name
    passed += 1
    print("  ✓", name)


def test_schema_rejects_bad_data() -> None:
    for bad in ({"source_tier": "BADTIER", "confidence": 0.5}, {"source_tier": "primary", "confidence": 5}):
        try:
            schema.Relation(source_id="a", target_id="b", kind="influence", claim="c", source_ref="x", **bad)
            raise SystemExit(f"schema should reject {bad}")
        except ValidationError:
            pass
    check("schema 擋掉非法 source_tier 與超範圍 confidence", True)


def test_routing_threshold() -> None:
    check("route 0.70 → auto", authority.route(0.70) == "auto")
    check("route 0.69 → review", authority.route(0.69) == "review")


def test_metrics() -> None:
    check("repetition_rate 抓重複", metrics.repetition_rate(["a", "a", "b"]) == round(1 / 3, 3))
    check("coverage 正確", metrics.coverage(["a"], ["a", "b"]) == 0.5)


def test_display_label_rule() -> None:
    west = {"name_zh": "古斯基", "name_en": "Andreas Gursky", "label_pref": "en"}
    famous = {"name_zh": "明室", "name_en": "Camera Lucida", "label_pref": "zh_en"}
    east = {"name_zh": "森山大道", "name_en": "Daido Moriyama", "label_pref": "zh"}
    overlap = {"name_zh": "LIFE 雜誌", "name_en": "LIFE magazine", "label_pref": "en"}
    check("西方預設 English (中譯)", data_io.display_label(west) == "Andreas Gursky (古斯基)")
    check("中文慣用 中文 (English)", data_io.display_label(famous) == "明室 (Camera Lucida)")
    check("華人圈/東亞 只用中文", data_io.display_label(east) == "森山大道")
    check("中英重疊不重複括號", data_io.display_label(overlap) == "LIFE magazine")


def test_entity_table_integrity() -> None:
    rows = data_io.load_entity_rows()
    check("實體表無同名重複(同類型同英文名只能有一個 id)", data_io.duplicate_entities(rows) == [])
    dupes = data_io.duplicate_entities(rows + [{"id": "wells_2", "type": "person", "name_en": "Liz Wells", "name_zh": "x"}])
    check("duplicate_entities 抓得到第二個 Liz Wells", dupes and "wells" in dupes[0][1])


def test_role_and_year() -> None:
    base = dict(source_id="a", target_id="b", kind="belongs_to", claim="c", source_ref="s", source_tier="primary", confidence=0.85)
    try:
        schema.Relation(**base)
        ok_missing = False
    except Exception:
        ok_missing = True
    check("belongs_to 沒有 role 會被 schema 擋掉", ok_missing)
    try:
        schema.Relation(**dict(base, kind="influence", role="author"))
        ok_wrong = False
    except Exception:
        ok_wrong = True
    check("非 belongs_to 帶 role 會被 schema 擋掉", ok_wrong)
    check("infer_role: 作品→人物 = author", data_io.infer_role("work", "person") == "author")
    check("infer_role: 人物→獎項 = award", data_io.infer_role("person", "institution", "木村伊兵衛寫真賞") == "award")
    check("year_from_claim: 單一年份", data_io.year_from_claim("1975 年成為會員") == 1975)
    check("year_from_claim: 兩個年份不猜,改用事件 id", data_io.year_from_claim("1974–1984 (2009)", "pictures_gen_met_2009") == 2009)


def test_parse_evidence() -> None:
    ev = "說明｜［2026-10-28 上網查證通過］｜查證來源: https://a.org/x｜［2026-10-29 全量回查:頁面明載］原文:quoted words｜回查頁: https://a.org/y"
    parsed = data_io.parse_evidence(ev)
    check("parse_evidence 取最後一個網址", parsed["evidence_url"] == "https://a.org/y")
    check("parse_evidence 取原文引句", parsed["quote"] == "quoted words")
    check("parse_evidence 取最後查核日期與輪數", parsed["verified_on"] == "2026-10-29" and parsed["check_rounds"] == 2)
    check("parse_evidence 空字串不爆", data_io.parse_evidence("")["quote"] is None)


def test_data_audit() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    import audit_data
    errors, _ = audit_data.audit(write=False)
    check("資料稽核無硬性錯誤(id、重複、方向、層級、auto 可重現)", not errors)


def test_graph_build() -> nx.MultiDiGraph:
    graph = graph_build.build(verbose=False)
    check("圖至少 60 節點", graph.number_of_nodes() >= 60)
    check("節點帶 label/short_label", all("label" in d and "short_label" in d for _, d in graph.nodes(data=True)))
    check("正式圖不含 review/rejected 邊", all(d["status"] in data_io.IN_GRAPH_STATUSES for _, _, d in graph.edges(data=True)))
    parallel = nx.MultiDiGraph()
    parallel.add_edge("x", "y", key="influence")
    parallel.add_edge("x", "y", key="critique")
    check("MultiDiGraph 保留同對不同 kind 的平行邊", parallel.number_of_edges() == 2)
    return graph


def test_recommend_and_query() -> None:
    import query
    import recommend  # imported after graph.json is rebuilt
    graph = recommend.load_graph()
    items = recommend.recommend(graph, ["on_photography"], top_n=3)
    check("只給書名也能推薦(書→作者橋接)", len(items) > 0)
    check("推薦帶 status 欄", all("status" in item for item in items))
    top_for_photographer = recommend.recommend(graph, ["friedlander"], top_n=1)[0]["target"]
    check("得獎名單(institution)不會成為攝影家的第一推薦", "Award" not in top_for_photographer)
    koudelka_top2 = " ".join(i["target"] for i in recommend.recommend(graph, ["koudelka"], top_n=2))
    check("攝影家的自身著作能被推薦(走入邊)", "Gypsies" in koudelka_top2 or "Exiles" in koudelka_top2)
    intent, ids, result = query.answer("班雅明 馬格南 有關係嗎 出處在哪")
    check("provenance 意圖判對", intent == "provenance")
    check("對不存在關係回 not found(不編造)", result.get("found") is False)
    check("精確比對解析到班雅明與馬格南", {"benjamin", "magnum"} <= set(ids))
    _, _, fallback = query.answer("隨便亂打一個不存在的 xyz 出處")
    check("無法解析時不爆、仍回 dict", isinstance(fallback, dict))
    check("approved 邊在查詢輸出標為入圖", "入圖" in query.edge_line(
        {"from": "a", "to": "b", "kind": "influence", "confidence": 0.5, "tier": "critic", "source": "s", "status": "approved"}))


DETERMINISM_QUESTIONS = [
    "我攝影系三年級,報告要比較桑塔格和巴特對攝影的看法,兩人差在哪裡?",
    "讀完桑塔格《論攝影》下一本讀什麼",
    "表演 攝影 辛蒂雪曼 文本",
    "台灣報導攝影從《人間》雜誌開始,還有哪些人和文本?誰影響誰?",
]


def answers_with_seed(seed: str) -> str:
    """Answer DETERMINISM_QUESTIONS in a child process whose string hashing uses `seed`."""
    code = ("import sys, query; sys.stdout.reconfigure(encoding='utf-8'); "
            "print('\\n=====\\n'.join(query.render(query.answer(q)[2]) for q in sys.argv[1:]))")
    env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run([sys.executable, "-c", code, *DETERMINISM_QUESTIONS], cwd=Path(__file__).parent,
                         capture_output=True, text=True, encoding="utf-8", env=env, check=True)
    return out.stdout


def test_answers_do_not_depend_on_hash_seed() -> None:
    check("同一問句在不同 hash 種子的行程得到相同回答", answers_with_seed("1") == answers_with_seed("12345"))


def main() -> None:
    test_schema_rejects_bad_data()
    test_routing_threshold()
    test_metrics()
    test_display_label_rule()
    test_entity_table_integrity()
    test_role_and_year()
    test_parse_evidence()
    test_data_audit()
    test_graph_build()
    test_recommend_and_query()
    test_answers_do_not_depend_on_hash_seed()
    print(f"\n全部通過:{passed} 項 ✓")


if __name__ == "__main__":
    main()
