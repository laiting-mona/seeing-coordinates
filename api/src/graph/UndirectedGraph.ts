// Undirected simple graph built from sorted nodes and sorted edges, and networkx's bidirectional BFS,
// so the indirect path between two nodes is the same one the Python version returns.
// Last edited: 2026-11-17: first version (port of nx.Graph + _bidirectional_pred_succ, networkx 3.x).

import { cmpCodePoint } from "../text/pystr.js";

export class UndirectedGraph {
  private readonly adj = new Map<string, Map<string, true>>();

  /** QueryEngine._build_undirected: add_nodes_from(sorted(nodes)); add_edges_from(sorted({sorted pairs})). */
  static fromPairs(nodeIds: string[], pairs: Array<[string, string]>): UndirectedGraph {
    const g = new UndirectedGraph();
    for (const id of [...nodeIds].sort(cmpCodePoint)) g.addNode(id);
    const uniq = new Map<string, [string, string]>();
    for (const [u, v] of pairs) {
      const e: [string, string] = cmpCodePoint(u, v) <= 0 ? [u, v] : [v, u];
      uniq.set(e[0] + "\u0000" + e[1], e);
    }
    const edges = [...uniq.values()].sort((p, q) => cmpCodePoint(p[0], q[0]) || cmpCodePoint(p[1], q[1]));
    for (const [u, v] of edges) g.addEdge(u, v);
    return g;
  }

  addNode(id: string): void {
    if (!this.adj.has(id)) this.adj.set(id, new Map());
  }

  addEdge(u: string, v: string): void {
    this.addNode(u);
    this.addNode(v);
    this.adj.get(u)!.set(v, true);
    this.adj.get(v)!.set(u, true);
  }

  has(id: string): boolean {
    return this.adj.has(id);
  }

  private neighbours(id: string): string[] {
    return [...(this.adj.get(id)?.keys() ?? [])];
  }

  /** nx.shortest_path(G, a, b) for an unweighted graph; null when no path or a node is missing. */
  shortestPath(source: string, target: string): string[] | null {
    if (!this.has(source) || !this.has(target)) return null;
    const meet = this.bidirectional(source, target);
    if (!meet) return null;
    const [pred, succ, w0] = meet;
    const path: string[] = [];
    let w: string | null = w0;
    while (w !== null) {
      path.push(w);
      w = pred.get(w) ?? null;
    }
    path.reverse();
    w = succ.get(path[path.length - 1]) ?? null;
    while (w !== null) {
      path.push(w);
      w = succ.get(w) ?? null;
    }
    return path;
  }

  private bidirectional(source: string, target: string): [Map<string, string | null>, Map<string, string | null>, string] | null {
    if (source === target) return [new Map([[target, null]]), new Map([[source, null]]), source];
    const pred = new Map<string, string | null>([[source, null]]);
    const succ = new Map<string, string | null>([[target, null]]);
    let forward = [source];
    let reverse = [target];
    while (forward.length && reverse.length) {
      if (forward.length <= reverse.length) {
        const level = forward;
        forward = [];
        for (const v of level) {
          for (const w of this.neighbours(v)) {
            if (!pred.has(w)) {
              forward.push(w);
              pred.set(w, v);
            }
            if (succ.has(w)) return [pred, succ, w];
          }
        }
      } else {
        const level = reverse;
        reverse = [];
        for (const v of level) {
          for (const w of this.neighbours(v)) {
            if (!succ.has(w)) {
              succ.set(w, v);
              reverse.push(w);
            }
            if (pred.has(w)) return [pred, succ, w];
          }
        }
      }
    }
    return null;
  }
}
