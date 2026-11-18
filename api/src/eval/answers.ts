// Shared by the eval runner and the parity check: answer a question set and build one record per question.
// Last edited: 2026-11-17: first version (record shape matches tools/run_eval_agent.py).

import { createHash } from "node:crypto";
import type { HandlerResult } from "../domain/types.js";
import type { QueryEngine } from "../query/QueryEngine.js";

export interface AnswerRecord {
  id: string;
  intent: string;
  resolved: string[];
  answer: string;
  urls: string[];
  sha256: string;
}

/** Evidence URLs an answer exposes, in order, without duplicates (run_eval_agent.cited_urls). */
export function citedUrls(result: HandlerResult): string[] {
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

export function answerAll(engine: QueryEngine, questions: Array<Record<string, string>>): AnswerRecord[] {
  return questions.map((q) => {
    const a = engine.answer(q["問句"]);
    return { id: q["編號"], intent: a.intent, resolved: a.ids.slice(0, 4), answer: a.text, urls: citedUrls(a.result),
             sha256: createHash("sha256").update(a.text, "utf-8").digest("hex") };
  });
}
