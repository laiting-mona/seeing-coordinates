"""Personalised recommendation along the knowledge frontier (no model training).

Last edited: 2026-10-28 — membership edges into institutions (award rosters,
magazines) are context, not readings: they now carry CONTEXT_EDGE_WEIGHT so a
high-degree award hub cannot outrank a book or an exhibition.

Frontier = unread nodes one hop out from what the reader has read.
Score = confidence × tier weight × (0.5 + target centrality) × context weight.
Every item carries its reason, source and status, so pending (review) edges are
never presented as fact.
Usage: python recommend.py [read_id ...]
"""
import sys
from pathlib import Path

import networkx as nx

import data_io
from authority import TIER_BASE
from schema import KIND_VERB_ZH

ROOT = Path(__file__).resolve().parent
CENTRALITY_FLOOR = 0.5   # keeps low-centrality targets from scoring zero
# "X belongs_to <institution>" (an award, a magazine) is accurate but is not a next
# reading; an award with 40 winners would otherwise top every photographer's list.
CONTEXT_EDGE_WEIGHT = 0.5
CONTEXT_TARGET_TYPES = ("institution",)


def load_graph(root: Path = ROOT) -> nx.MultiDiGraph:
    """Load build/graph.json into a directed multigraph."""
    return nx.node_link_graph(data_io.load_graph_json(root), edges="links", directed=True, multigraph=True)


def edge_context_weight(graph: nx.MultiDiGraph, target: str, edge: dict) -> float:
    """1.0 for a reading-path edge; CONTEXT_EDGE_WEIGHT for membership in an institution."""
    is_membership = edge.get("kind") == "belongs_to" and graph.nodes[target].get("type") in CONTEXT_TARGET_TYPES
    return CONTEXT_EDGE_WEIGHT if is_membership else 1.0


def authors_of_read_works(graph: nx.MultiDiGraph, read_ids: set[str]) -> set[str]:
    """For each read work, return its author(s): persons linked by work --belongs_to--> person."""
    authors = set()
    for node_id in read_ids:
        if node_id in graph and graph.nodes[node_id].get("type") == "work":
            for _, target, data in graph.out_edges(node_id, data=True):
                if data.get("kind") == "belongs_to" and graph.nodes[target].get("type") == "person":
                    authors.add(target)
    return authors


def score_candidates(graph: nx.MultiDiGraph, seeds: set[str], exclude: set[str]) -> dict[str, tuple]:
    """Score every unread out-neighbour of the seeds. Returns {target: (score, seed, edge_data)}
    keeping, per target, the best supporting edge."""
    candidates = {}
    for seed in seeds:
        if seed not in graph:
            continue
        for _, target, data in graph.out_edges(seed, data=True):
            if target in exclude:
                continue
            tier_weight = TIER_BASE.get(data.get("source_tier", "other"), TIER_BASE["other"])
            score = (data.get("confidence", 0) * tier_weight
                     * (CENTRALITY_FLOOR + graph.nodes[target].get("centrality", 0))
                     * edge_context_weight(graph, target, data))
            if target not in candidates or score > candidates[target][0]:
                candidates[target] = (score, seed, data)
    return candidates


def format_recommendation(graph: nx.MultiDiGraph, target: str, score: float, seed: str, edge: dict) -> dict:
    """Turn one scored candidate into a reader-facing item with reason, source and status."""
    name = lambda node_id: graph.nodes[node_id].get("label") or graph.nodes[node_id].get("name_zh", node_id)
    verb = KIND_VERB_ZH.get(edge.get("kind"), "連結到")
    pending_note = "(待查證,尚未確認)" if edge.get("status") == "review" else ""
    return {
        "target": name(target),
        "reason": f"你已讀「{name(seed)}」,它{verb}「{name(target)}」:{edge.get('claim', '')}{pending_note}",
        "source": edge.get("source_ref", ""),
        "status": edge.get("status", ""),
        "score": round(score, 3),
    }


def recommend(graph: nx.MultiDiGraph, read_ids, top_n: int = 5) -> list[dict]:
    """Recommend the next readings for someone who has read `read_ids`.

    Works are bridged to their authors so a book title alone yields a frontier.
    Returns up to top_n items sorted by score, each with reason / source / status.
    """
    read = set(read_ids)
    seeds = read | authors_of_read_works(graph, read)
    candidates = score_candidates(graph, seeds, exclude=seeds)
    ranked = sorted(candidates.items(), key=lambda kv: -kv[1][0])[:top_n]
    return [format_recommendation(graph, target, *scored) for target, scored in ranked]


def main() -> None:
    graph = load_graph()
    profile = sys.argv[1:] or ["benjamin", "on_photography"]
    for item in recommend(graph, profile):
        print(f"• {item['target']}  [{item['score']}]  — {item['reason']}  (出處:{item['source']})")


if __name__ == "__main__":
    main()
