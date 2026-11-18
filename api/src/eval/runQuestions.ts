// Answer the whole evaluation question set with the TypeScript engine and write one JSON line per question.
// Last edited: 2026-11-17: first version. The engine is deterministic, so one run per question is enough;
// the Python runner's five runs all agreed (agent_summary.json).
// Usage: node dist/src/eval/runQuestions.js [out.jsonl]   (default build/eval/agent_runs_ts.jsonl)

import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { FileGraphSource } from "../io/graphSource.js";
import { parseCsv } from "../io/csv.js";
import { EVAL_DIR, GRAPH_JSON, QUESTIONS_CSV } from "../io/paths.js";
import { QueryEngine } from "../query/QueryEngine.js";
import { answerAll } from "./answers.js";

async function main(): Promise<void> {
  const out = process.argv[2] ?? resolve(EVAL_DIR, "agent_runs_ts.jsonl");
  const t0 = Date.now();
  const engine = new QueryEngine(await new FileGraphSource(GRAPH_JSON).load());
  const t1 = Date.now();
  const questions = parseCsv(await readFile(QUESTIONS_CSV, "utf-8"));
  const records = answerAll(engine, questions).map((r) => ({ run: 1, ...r }));
  await writeFile(out, records.map((r) => JSON.stringify(r)).join("\n") + "\n", "utf-8");
  const intents = new Map<string, number>();
  for (const r of records) intents.set(r.intent, (intents.get(r.intent) ?? 0) + 1);
  console.log(`${records.length} 題，載入 ${t1 - t0} ms，作答 ${Date.now() - t1} ms → ${out}`);
  console.log("意圖分布:", Object.fromEntries(intents));
  console.log("未解析出節點:", records.filter((r) => !r.resolved.length).length);
}

main();
