// Browser entry for the trial site: the same query engine the Worker uses, bundled into public/engine.js by esbuild.
// Last edited: 2026-11-18: first version. Exposes window.SC = { boot(graphJson), answer(question), ready() }.

import type { HandlerResult, NodeLinkJson } from "./domain/types.js";
import { KnowledgeGraph } from "./graph/KnowledgeGraph.js";
import { QueryEngine } from "./query/QueryEngine.js";

let engine: QueryEngine | null = null;

/** Evidence URLs an answer exposes, in order, without duplicates (same walk as src/eval/answers.ts). */
function citedUrls(result: HandlerResult): string[] {
  const found: string[] = [];
  const walk = (value: unknown): void => {
    if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object") {
      const url = (value as Record<string, unknown>).url;
      if (typeof url === "string" && url.startsWith("http") && !found.includes(url)) found.push(url);
      Object.values(value as Record<string, unknown>).forEach(walk);
    }
  };
  walk(result);
  return found;
}

/** Build the engine from the graph snapshot; returns the build time in milliseconds. */
function boot(graphJson: NodeLinkJson): number {
  const t0 = performance.now();
  engine = new QueryEngine(KnowledgeGraph.fromNodeLink(graphJson));
  return Math.round(performance.now() - t0);
}

/** Answer one question; adds node labels, cited URLs and timing for the page's processing trace. */
function answer(question: string) {
  if (!engine) throw new Error("engine not booted");
  const t0 = performance.now();
  const a = engine.answer(question);
  const labels = a.ids.slice(0, 4).map((id) => ({ id, label: engine!.display(id) }));
  return { intent: a.intent, ids: a.ids.slice(0, 4), labels, result: a.result, text: a.text,
           urls: citedUrls(a.result), ms: Math.round((performance.now() - t0) * 10) / 10 };
}

(globalThis as unknown as { SC: unknown }).SC = { boot, answer, ready: () => engine !== null };
