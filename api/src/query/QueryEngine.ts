// Answers a question from the graph only: resolve nodes, classify the intent, run one handler.
// Last edited: 2026-11-17: first version, ported from query.QueryEngine (handlers return the same dicts).

import type { Answer, EdgeData, EdgeRecord, HandlerResult } from "../domain/types.js";
import { TIER_BASE } from "../domain/vocab.js";
import type { KnowledgeGraph } from "../graph/KnowledgeGraph.js";
import { UndirectedGraph } from "../graph/UndirectedGraph.js";
import { Recommender } from "../recommend/Recommender.js";
import { renderAnswer } from "../render/renderers.js";
import { EntityResolver } from "./EntityResolver.js";
import { IntentClassifier, type Intent } from "./IntentClassifier.js";

/** Static three-week starter plan returned by the "path" intent. */
export const STARTER_PATH: string[][] = [
  ["第1週", "伯格《觀看的方式》", "建立『觀看受意識形態形塑』的問題意識"],
  ["第2週", "桑塔格《論攝影》", "採集與觀看倫理"],
  ["第3週", "巴特《明室》", "刺點/此曾在的現象學;行有餘力接蕭爾《照片的本質》"],
];

export class QueryEngine {
  readonly resolver: EntityResolver;
  private readonly classifier: IntentClassifier;
  private readonly recommender: Recommender;
  private readonly undirected: UndirectedGraph;

  constructor(private readonly graph: KnowledgeGraph) {
    this.resolver = new EntityResolver(graph);
    this.classifier = new IntentClassifier();
    this.recommender = new Recommender(graph);
    this.undirected = UndirectedGraph.fromPairs(graph.nodeIds(), graph.edgePairs());
  }

  display(id: string): string {
    return this.graph.label(id);
  }

  answer(question: string): Answer {
    const ids = this.resolver.resolve(question);
    const intent = this.classifier.classify(question);
    const result = this.handle(intent, ids);
    return { intent, ids, result, text: renderAnswer(result) };
  }

  handle(intent: Intent, ids: string[]): HandlerResult {
    switch (intent) {
      case "recommend": return this.handleRecommend(ids);
      case "provenance": return this.handleProvenance(ids);
      case "lineage": return this.handleLineage(ids);
      case "relation": return this.handleRelation(ids);
      case "authority": return this.handleAuthority();
      case "path": return { type: "path", weeks: STARTER_PATH };
      default: return this.handleDefault(ids);
    }
  }

  // ---------- graph helpers ----------
  edgeRecord(source: string, target: string, d: EdgeData): EdgeRecord {
    const get = <T>(k: string): T | null => (d[k] === undefined ? null : (d[k] as T));
    return {
      from: this.display(source), to: this.display(target), kind: get("kind"), claim: get("claim"),
      evidence: (d.evidence as string) || "", source: get("source_ref"), tier: get("source_tier"),
      confidence: get("confidence"), status: get("status"), role: get("role"), year: get("year"),
      url: get("evidence_url"), quote: get("quote"), verified_on: get("verified_on"),
    };
  }

  private bothDirections(a: string, b: string): EdgeRecord[] {
    return [...this.graph.edgesBetween(a, b).map((d) => this.edgeRecord(a, b, d)),
            ...this.graph.edgesBetween(b, a).map((d) => this.edgeRecord(b, a, d))];
  }

  // ---------- handlers ----------
  private handleRecommend(ids: string[]): HandlerResult {
    if (!ids.length) return { type: "recommend", resolved: false };
    const items = this.recommender.recommend(ids, 3);
    return { type: "recommend", resolved: true, seed: this.display(ids[0]),
             items: items.map((i) => ({ target: i.target, reason: i.reason, source: i.source })) };
  }

  private handleProvenance(ids: string[]): HandlerResult {
    if (ids.length < 2) return { type: "provenance", resolved: false, nodes: ids.map((i) => this.display(i)) };
    const edges = this.bothDirections(ids[0], ids[1]);
    if (!edges.length) return { type: "provenance", resolved: true, found: false, a: this.display(ids[0]), b: this.display(ids[1]) };
    return { type: "provenance", resolved: true, found: true, edges };
  }

  private handleLineage(ids: string[]): HandlerResult {
    if (!ids.length) return { type: "lineage", resolved: false };
    const concept = ids[0];
    const preds = this.graph.has(concept) ? this.graph.predecessors(concept) : [];
    const origin = preds.slice(0, 3).flatMap((u) => this.graph.edgesBetween(u, concept).map((d) => this.edgeRecord(u, concept, d)));
    const followups = preds.slice(0, 1).flatMap((u) =>
      this.graph.predecessors(u).slice(0, 4).flatMap((a) => this.graph.edgesBetween(a, u).map((d) => this.edgeRecord(a, u, d))));
    return { type: "lineage", resolved: true, concept: this.display(concept), origin, followups };
  }

  private handleRelation(ids: string[]): HandlerResult {
    if (ids.length < 2) return this.handleDefault(ids);
    const [a, b] = ids;
    const edges = this.bothDirections(a, b);
    if (edges.length) return { type: "relation", direct: true, edges };
    const path = this.undirected.shortestPath(a, b);
    if (path) return { type: "relation", direct: false, path: path.map((x) => this.display(x)) };
    return { type: "relation", direct: false, path: [], a: this.display(a), b: this.display(b) };
  }

  private handleAuthority(): HandlerResult {
    const popular = this.graph.allEdges().filter(([, , d]) => d.source_tier === "popular").map(([u, v, d]) => this.edgeRecord(u, v, d));
    const tiers = Object.entries(TIER_BASE).sort((x, y) => y[1] - x[1]);
    return { type: "authority", tiers, popular_examples: popular };
  }

  private handleDefault(ids: string[]): HandlerResult {
    if (!ids.length) return { type: "unresolved" };
    const node = ids[0];
    const out = this.graph.has(node) ? this.graph.outEdges(node).slice(0, 6) : [];
    const inn = this.graph.has(node) ? this.graph.inEdges(node).slice(0, 4) : [];
    return { type: "default", node: this.display(node),
             out: out.map(([u, v, d]) => this.edgeRecord(u, v, d)), in: inn.map(([u, v, d]) => this.edgeRecord(u, v, d)) };
  }
}
