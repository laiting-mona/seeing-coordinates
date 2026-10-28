"""Personalised recommendation along the knowledge frontier (no model training).

Last edited: 2026-10-28 — (1) membership edges are context, not readings: a
belongs_to edge is weighted by its target type (institution 0.5, anthology/work
0.7, event 0.8) so award rosters and anthologies cannot crowd out intellectual
links; (2) the frontier now also walks INBOUND edges: a photographer's own works
(work --belongs_to--> person), exhibitions that showed them and texts that discuss
them are candidates too, so "read Koudelka" can lead to Gypsies, not only to awards.

Frontier = unread nodes one hop out from (or into) what the reader has read.
Score = confidence × tier weight × (0.5 + target centrality) × context weight
        (× INBOUND_WEIGHT for an inbound edge).
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
# Membership in an anthology or an exhibition is a weaker but real reading path.
MEMBERSHIP_WEIGHT = {"institution": 0.5, "work": 0.7, "event": 0.8}   # by target type; others 1.0
# Inbound edges that point AT the seed and lead somewhere worth reading.
INBOUND_KINDS = ("belongs_to", "discusses", "study", "review", "interpret", "critique", "exhibit")
INBOUND_WEIGHT = 0.9


def load_graph(root: Path = ROOT) -> nx.MultiDiGraph:
    """Load build/graph.json into a directed multigraph."""
    return nx.node_link_graph(data_io.load_graph_json(root), edges="links", directed=True, multigraph=True)


def edge_context_weight(graph: nx.MultiDiGraph, target: str, edge: dict) -> float:
    """1.0 for an intellectual edge; MEMBERSHIP_WEIGHT[target type] for a belongs_to edge."""
    if edge.get("kind") != "belongs_to":
        return 1.0
    return MEMBERSHIP_WEIGHT.get(graph.nodes[target].get("type"), 1.0)


def edge_score(graph: nx.MultiDiGraph, candidate: str, edge: dict, context_weight: float = 1.0) -> float:
    """confidence × tier weight × (floor + centrality of the candidate) × context weight."""
    tier_weight = TIER_BASE.get(edge.get("source_tier", "other"), TIER_BASE["other"])
    return (edge.get("confidence", 0) * tier_weight
            * (CENTRALITY_FLOOR + graph.nodes[candidate].get("centrality", 0)) * context_weight)


def inbound_candidate(graph: nx.MultiDiGraph, source: str, edge: dict) -> bool:
    """An inbound edge is a reading path when it is a text/exhibition about the seed,
    or the seed's own work (work --belongs_to--> person)."""
    kind = edge.get("kind")
    if kind not in INBOUND_KINDS:
        return False
    if kind == "belongs_to":
        return graph.nodes[source].get("type") == "work"
    return True


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
    """Score every unread neighbour of the seeds, outbound and (selected) inbound.

    Returns {candidate: (score, seed, edge_data, direction)} keeping, per candidate,
    the best supporting edge; direction is "out" (seed → candidate) or "in" (candidate → seed).
    """
    candidates = {}

    def offer(candidate, score, seed, data, direction):
        if candidate not in exclude and (candidate not in candidates or score > candidates[candidate][0]):
            candidates[candidate] = (score, seed, data, direction)

    for seed in seeds:
        if seed not in graph:
            continue
        for _, target, data in graph.out_edges(seed, data=True):
            offer(target, edge_score(graph, target, data, edge_context_weight(graph, target, data)), seed, data, "out")
        for source, _, data in graph.in_edges(seed, data=True):   # the seed's own works, shows and critics
            if inbound_candidate(graph, source, data):
                offer(source, edge_score(graph, source, data, INBOUND_WEIGHT), seed, data, "in")
    return candidates


def format_recommendation(graph: nx.MultiDiGraph, target: str, score: float, seed: str, edge: dict,
                          direction: str = "out") -> dict:
    """Turn one scored candidate into a reader-facing item with reason, source and status."""
    name = lambda node_id: graph.nodes[node_id].get("label") or graph.nodes[node_id].get("name_zh", node_id)
    verb = KIND_VERB_ZH.get(edge.get("kind"), "連結到")
    pending_note = "(待查證,尚未確認)" if edge.get("status") == "review" else ""
    if direction == "in":
        verb = "是其作品" if edge.get("kind") == "belongs_to" else verb + "它"
        reason = f"你已讀「{name(seed)}」;「{name(target)}」{verb}:{edge.get('claim', '')}{pending_note}"
    else:
        reason = f"你已讀「{name(seed)}」,它{verb}「{name(target)}」:{edge.get('claim', '')}{pending_note}"
    return {
        "target": name(target),
        "reason": reason,
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
