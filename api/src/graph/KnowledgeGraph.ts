// Directed multigraph over the formal relations, with networkx's iteration order (insertion order everywhere),
// so handlers that take "the first N edges" pick the same edges as the Python version.
// Last edited: 2026-11-17: first version.

import type { EdgeData, EdgeTriple, GraphNode, NodeLinkJson } from "../domain/types.js";

export class KnowledgeGraph {
  private readonly nodeMap = new Map<string, GraphNode>();
  private readonly succ = new Map<string, Map<string, EdgeData[]>>();
  private readonly pred = new Map<string, Map<string, EdgeData[]>>();

  /** Build from networkx node-link JSON: nodes in list order, then links in list order. */
  static fromNodeLink(json: NodeLinkJson): KnowledgeGraph {
    const g = new KnowledgeGraph();
    for (const node of json.nodes) g.addNode(node.id, node);
    for (const link of json.links) {
      const { source, target, key: _key, ...data } = link;
      g.addEdge(source, target, data);
    }
    return g;
  }

  addNode(id: string, attrs: Partial<GraphNode> = {}): void {
    if (!this.nodeMap.has(id)) {
      this.nodeMap.set(id, { ...attrs, id } as GraphNode);
      this.succ.set(id, new Map());
      this.pred.set(id, new Map());
    }
  }

  addEdge(u: string, v: string, data: EdgeData): void {
    this.addNode(u);
    this.addNode(v);
    const out = this.succ.get(u) as Map<string, EdgeData[]>;
    const inn = this.pred.get(v) as Map<string, EdgeData[]>;
    if (!out.has(v)) out.set(v, []);
    if (!inn.has(u)) inn.set(u, []);
    out.get(v)!.push(data);
    // networkx shares one dict between succ[u][v] and pred[v][u]
    inn.set(u, out.get(v)!);
  }

  has(id: string): boolean {
    return this.nodeMap.has(id);
  }

  node(id: string): GraphNode {
    const n = this.nodeMap.get(id);
    if (!n) throw new Error(`unknown node ${id}`);
    return n;
  }

  nodeIds(): string[] {
    return [...this.nodeMap.keys()];
  }

  nodes(): GraphNode[] {
    return [...this.nodeMap.values()];
  }

  /** out_edges(n, data=True): targets in insertion order, each target's parallel edges in key order. */
  outEdges(id: string): EdgeTriple[] {
    const out: EdgeTriple[] = [];
    for (const [v, list] of this.succ.get(id) ?? []) for (const d of list) out.push([id, v, d]);
    return out;
  }

  /** in_edges(n, data=True): sources in insertion order. */
  inEdges(id: string): EdgeTriple[] {
    const out: EdgeTriple[] = [];
    for (const [u, list] of this.pred.get(id) ?? []) for (const d of list) out.push([u, id, d]);
    return out;
  }

  predecessors(id: string): string[] {
    return [...(this.pred.get(id)?.keys() ?? [])];
  }

  edgesBetween(source: string, target: string): EdgeData[] {
    return [...(this.succ.get(source)?.get(target) ?? [])];
  }

  /** edges(data=True): by node order, then each node's out edges. */
  allEdges(): EdgeTriple[] {
    const out: EdgeTriple[] = [];
    for (const id of this.nodeMap.keys()) out.push(...this.outEdges(id));
    return out;
  }

  /** Every (u, v) pair of edges() without data, for building the undirected view. */
  edgePairs(): Array<[string, string]> {
    return this.allEdges().map(([u, v]) => [u, v]);
  }

  label(id: string): string {
    const n = this.nodeMap.get(id);
    if (!n) return id;
    return (n.label as string) || (n.name_zh as string) || id;
  }
}
