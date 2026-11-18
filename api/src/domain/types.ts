// Shapes of the graph snapshot (build/graph.json, networkx node-link format) and of handler results.
// Last edited: 2026-11-17: first version.

export interface GraphNode {
  id: string;
  type: string;
  name_zh?: string;
  name_en?: string | null;
  label_pref?: string;
  label?: string;
  short_label?: string;
  centrality?: number;
  [key: string]: unknown;
}

/** Edge attributes as stored on a link (source/target/key removed by the loader). */
export interface EdgeData {
  kind?: string;
  claim?: string | null;
  evidence?: string | null;
  source_ref?: string | null;
  source_tier?: string | null;
  confidence?: number | null;
  status?: string | null;
  role?: string | null;
  year?: number | null;
  evidence_url?: string | null;
  quote?: string | null;
  verified_on?: string | null;
  [key: string]: unknown;
}

export interface NodeLinkJson {
  directed: boolean;
  multigraph: boolean;
  nodes: GraphNode[];
  links: Array<EdgeData & { source: string; target: string; key?: number }>;
}

/** (source, target, data) triple, the shape networkx yields for edges(data=True). */
export type EdgeTriple = [string, string, EdgeData];

/** One edge as the handlers expose it (QueryEngine.edge_record). */
export interface EdgeRecord {
  from: string;
  to: string;
  kind: string | null;
  claim: string | null;
  evidence: string;
  source: string | null;
  tier: string | null;
  confidence: number | null;
  status: string | null;
  role: string | null;
  year: number | null;
  url: string | null;
  quote: string | null;
  verified_on: string | null;
}

export type HandlerResult = Record<string, unknown> & { type: string };

export interface Answer {
  intent: string;
  ids: string[];
  result: HandlerResult;
  text: string;
}
