"""Minimal regression tests (plain assert, no pytest) for the core behaviour.

Last edited: 2026-10-28 — added check that institution rosters never top a photographer's
recommendations. 2026-10-27: tests grouped into functions; added checks for
display_label naming rule, approved-as-in-graph labelling and the faster resolver.
Usage: python test_core.py
"""
import sys

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
    intent, ids, result = query.answer("班雅明 馬格南 有關係嗎 出處在哪")
    check("provenance 意圖判對", intent == "provenance")
    check("對不存在關係回 not found(不編造)", result.get("found") is False)
    check("精確比對解析到班雅明與馬格南", {"benjamin", "magnum"} <= set(ids))
    _, _, fallback = query.answer("隨便亂打一個不存在的 xyz 出處")
    check("無法解析時不爆、仍回 dict", isinstance(fallback, dict))
    check("approved 邊在查詢輸出標為入圖", "入圖" in query.edge_line(
        {"from": "a", "to": "b", "kind": "influence", "confidence": 0.5, "tier": "critic", "source": "s", "status": "approved"}))


def main() -> None:
    test_schema_rejects_bad_data()
    test_routing_threshold()
    test_metrics()
    test_display_label_rule()
    test_graph_build()
    test_recommend_and_query()
    print(f"\n全部通過:{passed} 項 ✓")


if __name__ == "__main__":
    main()
