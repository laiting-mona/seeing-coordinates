// Parity check: the TypeScript engine must give exactly the answers the Python query.py gives on the same graph.
// Last edited: 2026-11-17: first version.
// Usage: node dist/src/eval/parity.js <python_answers.jsonl>   (from tools/python_answers.py on the same graph.json)

import { readFile } from "node:fs/promises";
import { FileGraphSource } from "../io/graphSource.js";
import { parseCsv } from "../io/csv.js";
import { GRAPH_JSON, QUESTIONS_CSV } from "../io/paths.js";
import { QueryEngine } from "../query/QueryEngine.js";
import { answerAll, type AnswerRecord } from "./answers.js";

async function main(): Promise<void> {
  const pyPath = process.argv[2];
  const python = new Map<string, AnswerRecord>();
  for (const line of (await readFile(pyPath, "utf-8")).split("\n")) {
    if (line.trim()) { const r = JSON.parse(line) as AnswerRecord; python.set(r.id, r); }
  }
  const engine = new QueryEngine(await new FileGraphSource(GRAPH_JSON).load());
  const ts = answerAll(engine, parseCsv(await readFile(QUESTIONS_CSV, "utf-8")));
  const diff = { intent: 0, resolved: 0, answer: 0, urls: 0 };
  const examples: string[] = [];
  for (const r of ts) {
    const p = python.get(r.id);
    if (!p) { examples.push(`${r.id}: missing in python file`); continue; }
    const bad: string[] = [];
    if (p.intent !== r.intent) { diff.intent++; bad.push(`intent ${p.intent} / ${r.intent}`); }
    if (JSON.stringify(p.resolved) !== JSON.stringify(r.resolved)) { diff.resolved++; bad.push(`resolved ${p.resolved} / ${r.resolved}`); }
    if (p.sha256 !== r.sha256) { diff.answer++; bad.push("answer text differs"); }
    if (JSON.stringify(p.urls) !== JSON.stringify(r.urls)) { diff.urls++; bad.push("urls differ"); }
    if (bad.length && examples.length < 15) examples.push(`${r.id}: ${bad.join("; ")}`);
  }
  console.log(`${ts.length} 題比對；不同之處：`, diff);
  for (const e of examples) console.log("  " + e);
  process.exitCode = diff.intent + diff.resolved + diff.answer + diff.urls === 0 ? 0 : 1;
}

main();
