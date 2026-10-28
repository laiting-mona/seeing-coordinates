"""Weight-sensitivity experiment for the recommender (stdlib only, read-only on the graph).

Last edited: 2026-10-27 — module-level script turned into functions + main().

Measures, for several tier-weight vectors, how much the recommendations move:
  top-5 Jaccard  — did the recommended set change?
  Spearman rho   — did the ranking of all candidates change?
Reads ../build/graph.json; writes results/weight_sensitivity.csv; never modifies data.
Usage (from the project root): python experiments/weight_sensitivity.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import data_io  # noqa: E402
from authority import TIER_BASE  # noqa: E402  (single source of truth for baseline weights)

RESULTS_CSV = ROOT / "experiments/results/weight_sensitivity.csv"
CENTRALITY_FLOOR = 0.5
TOP_K = 5

BASE = {k: TIER_BASE[k] for k in ("primary", "institution", "critic", "popular")}
WEIGHT_VECTORS = {
    "baseline": dict(BASE),
    "flat":     {"primary": 0.70, "institution": 0.70, "critic": 0.70, "popular": 0.70},
    "steep":    {"primary": 0.95, "institution": 0.70, "critic": 0.40, "popular": 0.15},
    "swapped":  {"primary": 0.50, "institution": 0.60, "critic": 0.85, "popular": 0.30},
    "pop_0.30": {**BASE, "popular": 0.30},
    "pop_0.15": {**BASE, "popular": 0.15},
    "pop_0.10": {**BASE, "popular": 0.10},
}
READER_PROFILES = {
    "讀過班雅明": ["benjamin"], "讀過巴特": ["barthes"], "讀過桑塔格": ["sontag"],
    "讀過薩考斯基": ["szarkowski"], "讀過伯格": ["berger"], "讀過蕭爾": ["shore"],
}


def index_graph(graph_json: dict) -> tuple[dict, dict]:
    """Return (nodes_by_id, out_links_by_source) from node-link JSON."""
    nodes = {n["id"]: n for n in graph_json["nodes"]}
    out_links: dict[str, list] = {}
    for link in graph_json["links"]:
        out_links.setdefault(link["source"], []).append(link)
    return nodes, out_links


def rank_candidates(profile: list[str], weights: dict, nodes: dict, out_links: dict) -> list[str]:
    """Candidate targets sorted by confidence × tier weight × (floor + centrality), best first."""
    read = set(profile)
    best_score: dict[str, float] = {}
    for seed in profile:
        for link in out_links.get(seed, []):
            target = link["target"]
            if target in read:
                continue
            score = link["confidence"] * weights.get(link["source_tier"], 0.4) * (CENTRALITY_FLOOR + nodes[target].get("centrality", 0))
            best_score[target] = max(best_score.get(target, 0), score)
    return [target for target, _ in sorted(best_score.items(), key=lambda kv: -kv[1])]


def top_k_jaccard(ranking_a: list[str], ranking_b: list[str], k: int = TOP_K) -> float:
    set_a, set_b = set(ranking_a[:k]), set(ranking_b[:k])
    return round(len(set_a & set_b) / len(set_a | set_b), 3) if (set_a | set_b) else 1.0


def spearman_rho(ranking_a: list[str], ranking_b: list[str]) -> float:
    """Rank correlation over the candidates common to both rankings (1.0 when fewer than 2)."""
    common = [x for x in ranking_a if x in ranking_b]
    n = len(common)
    if n < 2:
        return 1.0
    rank_a = {x: i for i, x in enumerate(ranking_a)}
    rank_b = {x: i for i, x in enumerate(ranking_b)}
    squared_diff = sum((rank_a[x] - rank_b[x]) ** 2 for x in common)
    return round(1 - 6 * squared_diff / (n * (n * n - 1)), 3)


def run_experiment(nodes: dict, out_links: dict) -> list[dict]:
    """Average Jaccard and Spearman across reader profiles for each weight vector."""
    baseline = {p: rank_candidates(ids, WEIGHT_VECTORS["baseline"], nodes, out_links) for p, ids in READER_PROFILES.items()}
    results = []
    for name, weights in WEIGHT_VECTORS.items():
        rankings = {p: rank_candidates(ids, weights, nodes, out_links) for p, ids in READER_PROFILES.items()}
        jaccards = [top_k_jaccard(baseline[p], rankings[p]) for p in READER_PROFILES]
        rhos = [spearman_rho(baseline[p], rankings[p]) for p in READER_PROFILES]
        results.append({"weights": name,
                        "avg_top5_jaccard": round(sum(jaccards) / len(jaccards), 3),
                        "avg_spearman": round(sum(rhos) / len(rhos), 3)})
    return results


def write_results(results: list[dict], path: Path = RESULTS_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)


def main() -> None:
    nodes, out_links = index_graph(data_io.load_graph_json(ROOT))
    results = run_experiment(nodes, out_links)
    print(f"{'權重向量':<10}{'top5 Jaccard':<16}{'Spearman 名次相關':<18}")
    for row in results:
        print(f"{row['weights']:<10}{row['avg_top5_jaccard']:<16}{row['avg_spearman']:<18}")
    write_results(results)
    print(f"\n結果寫入 {RESULTS_CSV.relative_to(ROOT)}")
    print("讀法:Jaccard=1 表 top-5 名單沒換;Spearman<1 表名次有變。兩者越低代表對權重越敏感。")


if __name__ == "__main__":
    main()
