// Next readings along the knowledge frontier (port of recommend.py; no model training).
// Last edited: 2026-11-17: first version. Score = confidence × tier weight × (0.5 + centrality) × context weight.

import type { EdgeData } from "../domain/types.js";
import { KIND_VERB_ZH, ROLE_VERB_ZH, TIER_BASE } from "../domain/vocab.js";
import type { KnowledgeGraph } from "../graph/KnowledgeGraph.js";
import { cmpCodePoint, pyStr } from "../text/pystr.js";

const CENTRALITY_FLOOR = 0.5;
/** belongs_to edges are context, weighted by the target's type; others 1.0. */
export const MEMBERSHIP_WEIGHT: Record<string, number> = { institution: 0.5, group: 0.5, work: 0.7, event: 0.8 };
const INBOUND_KINDS = new Set(["belongs_to", "discusses", "study", "review", "interpret", "critique", "exhibit"]);
const INBOUND_WEIGHT = 0.9;

export interface Recommendation {
  target: string;
  reason: string;
  source: string;
  status: string;
  score: number;
}

type Candidate = [number, string, EdgeData, "out" | "in"];

export class Recommender {
  constructor(private readonly graph: KnowledgeGraph, private readonly membershipWeight = MEMBERSHIP_WEIGHT) {}

  recommend(readIds: string[], topN = 5): Recommendation[] {
    const read = new Set(readIds);
    const seeds = new Set([...read, ...this.authorsOfReadWorks(read)]);
    const candidates = this.scoreCandidates(seeds, seeds);
    const ranked = [...candidates.entries()].sort((a, b) => (b[1][0] - a[1][0]) || cmpCodePoint(a[0], b[0])).slice(0, topN);
    return ranked.map(([target, [score, seed, edge, dir]]) => this.format(target, score, seed, edge, dir));
  }

  private type(id: string): string | undefined {
    return this.graph.has(id) ? (this.graph.node(id).type as string) : undefined;
  }

  private contextWeight(target: string, edge: EdgeData): number {
    if (edge.kind !== "belongs_to") return 1.0;
    return this.membershipWeight[this.type(target) ?? ""] ?? 1.0;
  }

  private inboundWeight(source: string, edge: EdgeData): number {
    if (edge.kind !== "exhibit") return INBOUND_WEIGHT;
    return INBOUND_WEIGHT * (this.membershipWeight[this.type(source) ?? ""] ?? 1.0);
  }

  private inboundCandidate(source: string, edge: EdgeData): boolean {
    if (!INBOUND_KINDS.has(edge.kind ?? "")) return false;
    if (edge.kind === "belongs_to") return this.type(source) === "work";
    return true;
  }

  private edgeScore(candidate: string, edge: EdgeData, context = 1.0): number {
    const tier = TIER_BASE[edge.source_tier ?? "other"] ?? TIER_BASE.other;
    const centrality = (this.graph.node(candidate).centrality as number | undefined) ?? 0;
    return (edge.confidence ?? 0) * tier * (CENTRALITY_FLOOR + centrality) * context;
  }

  private authorsOfReadWorks(read: Set<string>): Set<string> {
    const authors = new Set<string>();
    for (const id of read) {
      if (this.graph.has(id) && this.type(id) === "work") {
        for (const [, target, data] of this.graph.outEdges(id)) {
          if (data.kind === "belongs_to" && this.type(target) === "person") authors.add(target);
        }
      }
    }
    return authors;
  }

  private scoreCandidates(seeds: Set<string>, exclude: Set<string>): Map<string, Candidate> {
    const candidates = new Map<string, Candidate>();
    const offer = (c: string, score: number, seed: string, data: EdgeData, dir: "out" | "in") => {
      const cur = candidates.get(c);
      if (!exclude.has(c) && (!cur || score > cur[0])) candidates.set(c, [score, seed, data, dir]);
    };
    for (const seed of [...seeds].sort(cmpCodePoint)) {
      if (!this.graph.has(seed)) continue;
      for (const [, target, data] of this.graph.outEdges(seed)) {
        offer(target, this.edgeScore(target, data, this.contextWeight(target, data)), seed, data, "out");
      }
      for (const [source, , data] of this.graph.inEdges(seed)) {
        if (this.inboundCandidate(source, data)) {
          offer(source, this.edgeScore(source, data, this.inboundWeight(source, data)), seed, data, "in");
        }
      }
    }
    return candidates;
  }

  private format(target: string, score: number, seed: string, edge: EdgeData, dir: "out" | "in"): Recommendation {
    const name = (id: string) => (this.graph.node(id).label as string) || (this.graph.node(id).name_zh as string) || id;
    let verb = edge.kind === "belongs_to" && edge.role ? pyStr(ROLE_VERB_ZH[edge.role] ?? null)
      : (KIND_VERB_ZH[edge.kind ?? ""] ?? "連結到");
    const pending = edge.status === "review" ? "(待查證,尚未確認)" : "";
    const claim = "claim" in edge ? pyStr(edge.claim) : "";
    let reason: string;
    if (dir === "in") {
      verb = edge.role === "author" ? "是其作品" : (edge.role === "contributor" ? "收錄它" : verb + "它");
      reason = `你已讀「${name(seed)}」;「${name(target)}」${verb}:${claim}${pending}`;
    } else {
      reason = `你已讀「${name(seed)}」,它${verb}「${name(target)}」:${claim}${pending}`;
    }
    return { target: name(target), reason, source: "source_ref" in edge ? pyStr(edge.source_ref) : "",
             status: (edge.status as string) ?? "", score: Math.round(score * 1000) / 1000 };
  }
}
