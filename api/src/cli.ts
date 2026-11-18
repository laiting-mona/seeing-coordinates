// Command line: answer one question from the graph.
// Last edited: 2026-11-17: first version.
// Usage: node dist/src/cli.js "問句"   |   node dist/src/cli.js --json "問句"

import { FileGraphSource } from "./io/graphSource.js";
import { GRAPH_JSON } from "./io/paths.js";
import { QueryEngine } from "./query/QueryEngine.js";

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const question = args.filter((a) => !a.startsWith("--")).join(" ");
  if (!question) {
    console.log('用法:node dist/src/cli.js "問句"  /  --json "問句"');
    return;
  }
  const engine = new QueryEngine(await new FileGraphSource(GRAPH_JSON).load());
  const answer = engine.answer(question);
  if (args.includes("--json")) {
    console.log(JSON.stringify(answer.result, null, 2));
  } else {
    const shown = answer.ids.slice(0, 3).map((i) => engine.display(i)).join(",") || "無";
    console.log(`[意圖:${answer.intent}　解析:${shown}]\n${answer.text}`);
  }
}

main();
