"""Agent v1 demo: the program drives; the LLM only does step 3 (relation extraction).

Last edited: 2026-10-27 — module-level loading moved into functions; main() only
dispatches; approved relations are now counted as in-graph (previously only auto).

One round = plan → retrieve → extract (LLM) → score & route → update graph → monitor.
Modes:
  --replay (default) replay already-extracted relations and print the agent trace; zero LLM cost
  --live             describe the subscription-based extraction loop (extract.py prepare/ingest)
"""
import sys
from pathlib import Path

import data_io
import metrics

ROOT = Path(__file__).resolve().parent

# Demo plan: the five mainline authors and the work retrieved for each.
PLAN = ["benjamin", "berger", "sontag", "barthes", "shore"]
RETRIEVED_WORK = {"benjamin": "〈攝影小史〉/〈機械複製時代的藝術作品〉", "berger": "《觀看的方式》",
                  "sontag": "《論攝影》", "barthes": "《明室》", "shore": "《照片的本質》"}
RULE = "═" * 60


def group_relations_by_source(relations: list[dict]) -> dict[str, list[dict]]:
    """Index relations by their source entity id."""
    grouped: dict[str, list[dict]] = {}
    for relation in relations:
        grouped.setdefault(relation["source_id"], []).append(relation)
    return grouped


def all_node_ids(entity_names: dict[str, str], relations: list[dict]) -> set[str]:
    """Coverage denominator: every defined entity plus any id that appears in a relation."""
    return set(entity_names) | {n for r in relations for n in (r["source_id"], r["target_id"])}


def is_in_graph(relation: dict) -> bool:
    return relation["status"] in data_io.IN_GRAPH_STATUSES


def print_round(index: int, seed: str, batch: list[dict], name: dict[str, str]) -> tuple[int, int]:
    """Print one agent round for `seed`; returns (in_graph_count, review_count)."""
    print(f"\n── 第 {index} 輪 ──────────────────────────────")
    print(f"🧠 思考：圖中「{name.get(seed, seed)}」是主線核心,目前由它出發的關係 {len(batch)} 條,選它擴充。")
    print(f"🔧 行動：檢索來源「{RETRIEVED_WORK.get(seed, '')}」,讀取相關段落。")
    print("👁 觀察：取得文字片段(replay:取自已擷取語料)。")
    print(f"🤖 抽取[LLM]：從文字抽出 {len(batch)} 條候選關係(附出處)。")
    in_graph = 0
    for relation in batch:
        mark = "✓入圖" if is_in_graph(relation) else "⟳待判斷"
        in_graph += is_in_graph(relation)
        print(f"     · {name.get(seed, seed)} {relation['kind']} {name.get(relation['target_id'], relation['target_id'])}"
              f"  conf={relation['confidence']} [{relation['source_tier']}] → {mark}")
    return in_graph, len(batch) - in_graph


def print_monitoring(batch: list[dict], covered: set[str], previous_targets: set[str],
                     node_total: int, in_graph: int, review: int) -> None:
    """Repetition rate against earlier rounds and cumulative coverage."""
    targets = {r["target_id"] for r in batch}
    repetition = len(targets & previous_targets) / len(targets) if targets else 0
    coverage = len(covered) / node_total
    print(f"📊 評分分流：{in_graph} 條入圖、{review} 條進判斷佇列。")
    print(f"📈 監控：重複率 R={repetition:.2f}　涵蓋率 C={coverage:.2f}　"
          f"→ {'需擴充' if metrics.should_expand(repetition, len(batch)) else '續跑下一輪'}")


def print_recommendation_demo() -> None:
    """Show the recommender for a reader who has read Sontag's On Photography."""
    print("\n🎯 推薦示範(給『已讀桑塔格《論攝影》』的學習者):")
    try:
        import recommend
        graph = recommend.load_graph()
        for item in recommend.recommend(graph, ["sontag", "on_photography"], top_n=3):
            print(f"   • {item['target']}  — {item['reason'][:46]}…（出處:{item['source']}）")
    except Exception as error:  # graph.json missing until graph_build has run
        print(f"   (推薦模組需先 python graph_build.py;{error})")


def run_replay(root: Path = ROOT) -> None:
    """Replay the stored relations round by round and print the agent trace."""
    name = data_io.load_entity_names(root)
    relations = data_io.load_relation_dicts(root)
    by_source = group_relations_by_source(relations)
    node_total = len(all_node_ids(name, relations))
    print(RULE + "\n觀看的座標 · Agent v1　[replay 模式 · 零 LLM 成本]\n" + RULE)
    covered, previous_targets = set(), set()
    total_in_graph = total_review = 0
    for index, seed in enumerate(PLAN, 1):
        batch = by_source.get(seed, [])
        in_graph, review = print_round(index, seed, batch, name)
        covered |= {n for r in batch for n in (r["source_id"], r["target_id"])}
        print_monitoring(batch, covered, previous_targets, node_total, in_graph, review)
        previous_targets |= {r["target_id"] for r in batch}
        total_in_graph += in_graph
        total_review += review
    print("\n" + RULE)
    print(f"結束:累計入圖 {total_in_graph} 條、判斷佇列 {total_review} 條,覆蓋 {len(covered)}/{node_total} 節點。")
    print_recommendation_demo()
    print(RULE)


def run_live() -> None:
    """Describe the subscription-based (no paid API) extraction loop."""
    print("live 模式:第 3 步改用訂閱版抽取。")
    print("流程:python extract.py prepare → 把 prompt 貼進 Claude 訂閱版 → 存回 build/responses/ →")
    print("      python extract.py ingest → python graph_build.py → 再跑本 agent 檢視。")
    print("(v1 不呼叫付費 API;要全自動無人跑再加 --api,目前依決策先不開。)")


def main() -> None:
    (run_live if "--live" in sys.argv else run_replay)()


if __name__ == "__main__":
    main()
