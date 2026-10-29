"""Build the knowledge graph from data/ and write build/graph.json.

Last edited: 2026-10-29 — load_entities() refuses duplicate entities (same type + name under two
ids); graph.json written with LF on every OS. 2026-10-27: split build() into single-purpose functions; loaders
moved to data_io; main() only orchestrates; nodes now carry `label`/`short_label`
(EN-first for Western, ZH for Chinese-world; see data_io.display_label).

Default: only the formal graph (status auto + approved). `--with-review` also
draws the pending relations for inspection. Rejected relations never enter.
Usage: python graph_build.py [--with-review]
"""
import json
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

import data_io
from schema import Entity, Relation

ROOT = Path(__file__).resolve().parent
TOP_CENTRALITY_SHOWN = 5


def load_entities(root: Path = ROOT) -> dict[str, Entity]:
    """Validate seed_entities.csv rows into Entity models keyed by id."""
    rows = data_io.load_entity_rows(root)
    duplicates = data_io.duplicate_entities(rows)
    if duplicates:
        raise ValueError(f"duplicate entities (same type and name under different ids): {duplicates}")
    entities = {}
    for row in rows:
        entity = Entity(**{k: row[k] for k in ("id", "type", "name_zh", "name_en", "label_pref") if row.get(k)})
        entities[entity.id] = entity
    return entities


def load_relations(root: Path = ROOT) -> list[Relation]:
    """Validate raw_relations.jsonl lines into Relation models."""
    return [Relation(**d) for d in data_io.load_relation_dicts(root)]


def select_graph_relations(relations: list[Relation], include_review: bool) -> list[Relation]:
    """Keep the relations that enter the graph: auto + approved (+ review when requested)."""
    allowed = data_io.IN_GRAPH_STATUSES + (("review",) if include_review else ())
    return [r for r in relations if r.status in allowed]


def build_graph(entities: dict[str, Entity], all_relations: list[Relation],
                graph_relations: list[Relation]) -> nx.MultiDiGraph:
    """Assemble a MultiDiGraph: every entity is a node; parallel edges are keyed by kind.

    Nodes referenced only by relations (missing from the CSV) are added as placeholder concepts.
    """
    graph = nx.MultiDiGraph()
    for entity in entities.values():
        attrs = entity.model_dump()
        graph.add_node(entity.id, **attrs, label=data_io.display_label(attrs), short_label=data_io.short_label(attrs))
    for relation in all_relations:
        for node_id in (relation.source_id, relation.target_id):
            if node_id not in graph:
                graph.add_node(node_id, id=node_id, type="concept", name_zh=node_id, name_en=None,
                               label_pref="zh", label=node_id, short_label=node_id)
    for relation in graph_relations:
        graph.add_edge(relation.source_id, relation.target_id, key=relation.kind, **relation.model_dump())
    return graph


def attach_degree_centrality(graph: nx.MultiDiGraph) -> dict[str, float]:
    """Store degree centrality on each node (3 decimals) and return the raw mapping."""
    centrality = nx.degree_centrality(graph)
    for node_id, value in centrality.items():
        graph.nodes[node_id]["centrality"] = round(value, 3)
    return centrality


def write_graph_json(graph: nx.MultiDiGraph, root: Path = ROOT) -> Path:
    """Serialise the graph in node-link format to build/graph.json; returns the path."""
    output_path = root / data_io.GRAPH_JSON
    output_path.parent.mkdir(exist_ok=True)
    payload = nx.node_link_data(graph, edges="links")
    data_io.write_text_lf(output_path, json.dumps(payload, ensure_ascii=False, indent=2))
    return output_path


def summarize(graph: nx.MultiDiGraph, all_relations: list[Relation],
              graph_relations: list[Relation], centrality: dict[str, float]) -> str:
    """Human-readable status line plus the top-centrality nodes."""
    by_status = Counter(r.status for r in all_relations)
    top_nodes = sorted(centrality.items(), key=lambda kv: -kv[1])[:TOP_CENTRALITY_SHOWN]
    top_text = ", ".join(f"{graph.nodes[n]['short_label']}({c:.2f})" for n, c in top_nodes)
    return (f"節點 {graph.number_of_nodes()}  關係(全) {len(all_relations)}  "
            f"正式入圖 {len(graph_relations)}(自動 {by_status['auto']} + 查證確認 {by_status['approved']})  "
            f"待查證 {by_status['review']}  已剔除 {by_status['rejected']}\n"
            f"中心性 Top{TOP_CENTRALITY_SHOWN}: {top_text}")


def build(include_review: bool = False, root: Path = ROOT, verbose: bool = True) -> nx.MultiDiGraph:
    """End-to-end: load → select → build → centrality → write. Returns the graph."""
    entities = load_entities(root)
    relations = load_relations(root)
    graph_relations = select_graph_relations(relations, include_review)
    graph = build_graph(entities, relations, graph_relations)
    centrality = attach_degree_centrality(graph)
    write_graph_json(graph, root)
    if verbose:
        print(summarize(graph, relations, graph_relations, centrality))
    return graph


def main() -> None:
    build(include_review="--with-review" in sys.argv)


if __name__ == "__main__":
    main()
