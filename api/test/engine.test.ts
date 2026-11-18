// Unit tests for the TypeScript query layer. Fixtures were produced by Python's difflib and networkx
// (see the generator note in the decision log), so passing means "same numbers as the Python version".
// Last edited: 2026-11-17: first version.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { KnowledgeGraph } from "../src/graph/KnowledgeGraph.js";
import { UndirectedGraph } from "../src/graph/UndirectedGraph.js";
import { parseCsv } from "../src/io/csv.js";
import { FileGraphSource } from "../src/io/graphSource.js";
import { GRAPH_JSON } from "../src/io/paths.js";
import { IntentClassifier } from "../src/query/IntentClassifier.js";
import { QueryEngine } from "../src/query/QueryEngine.js";
import { renderAnswer } from "../src/render/renderers.js";
import { CloseMatcher, getCloseMatches, SequenceMatcher } from "../src/text/difflib.js";
import { cmpCodePoint, normalize, pyFloat, pyStr, round2 } from "../src/text/pystr.js";

const FIX = resolve(dirname(fileURLToPath(import.meta.url)), "../../test/fixtures");
const difflibFix = JSON.parse(readFileSync(resolve(FIX, "difflib.json"), "utf-8"));
const pathFix = JSON.parse(readFileSync(resolve(FIX, "shortest_paths.json"), "utf-8"));

test("SequenceMatcher ratios equal Python's on 303 pairs (incl. a 242-element b that triggers autojunk)", () => {
  for (const p of difflibFix.pairs) {
    const s = new SequenceMatcher(p.a, p.b);
    assert.equal(s.ratio(), p.ratio, `ratio ${p.a} / ${p.b}`);
    assert.equal(s.quickRatio(), p.quick, `quick ${p.a} / ${p.b}`);
    assert.equal(s.realQuickRatio(), p.real, `real ${p.a} / ${p.b}`);
  }
});

test("get_close_matches and the indexed CloseMatcher both equal Python's output", () => {
  const matcher = new CloseMatcher(difflibFix.names);
  for (const c of difflibFix.close) {
    assert.deepEqual(getCloseMatches(c.word, difflibFix.names, c.n, c.cutoff), c.out, c.word);
    assert.deepEqual(matcher.match(c.word, c.n, c.cutoff), c.out, `indexed ${c.word}`);
  }
});

test("Python string semantics: code-point order, normalize, float repr, None, round", () => {
  assert.ok(cmpCodePoint("\u{20000}", "￿") > 0);          // astral after BMP, unlike UTF-16 order
  assert.equal(normalize("Roland Barthes"), "rolandbarthes");
  assert.equal(pyFloat(1), "1.0");
  assert.equal(pyFloat(0.75), "0.75");
  assert.equal(pyStr(null), "None");
  assert.equal(round2(0.875), 0.88);
  assert.equal(round2(0.8333333333), 0.83);
});

test("networkx insertion order: parallel edges and predecessor order are kept", () => {
  const g = KnowledgeGraph.fromNodeLink({ directed: true, multigraph: true, nodes: [{ id: "a", type: "person" }, { id: "b", type: "work" }],
    links: [{ source: "b", target: "a", kind: "belongs_to" }, { source: "c", target: "a", kind: "discusses" }, { source: "b", target: "a", kind: "study" }] });
  assert.deepEqual(g.predecessors("a"), ["b", "c"]);
  assert.deepEqual(g.inEdges("a").map(([u, , d]) => `${u}:${d.kind}`), ["b:belongs_to", "b:study", "c:discusses"]);
  assert.deepEqual(g.nodeIds(), ["a", "b", "c"]);
});

test("bidirectional BFS returns the same shortest paths as networkx on 60 node pairs", async () => {
  const g = await new FileGraphSource(GRAPH_JSON).load();
  const u = UndirectedGraph.fromPairs(g.nodeIds(), g.edgePairs());
  for (const f of pathFix) assert.deepEqual(u.shortestPath(f.a, f.b), f.path, `${f.a} -> ${f.b}`);
});

test("intent keywords: first matching intent wins", () => {
  const c = new IntentClassifier();
  assert.equal(c.classify("這兩本書的出處和關係"), "provenance");
  assert.equal(c.classify("接下來讀什麼"), "recommend");
  assert.equal(c.classify("你好"), "default");
});

test("engine answers from the graph and never invents a relation", async () => {
  const engine = new QueryEngine(await new FileGraphSource(GRAPH_JSON).load());
  const a = engine.answer("《觀看的方式》看完了，接下來讀什麼比較順？");
  assert.equal(a.intent, "recommend");
  assert.equal(a.ids[0], "ways_of_seeing");
  assert.match(a.text, /出處:/);
  const none = engine.answer("今天天氣如何");
  assert.equal(none.result.type, "unresolved");
  assert.equal(renderAnswer({ type: "nothing" }), "我沒抓到你問的是哪個人、概念或作品,可以講得具體一點。");
});

test("CSV reader keeps quoted commas and newlines", () => {
  const rows = parseCsv('id,text\n1,"a, b"\n2,"line1\nline2"\n');
  assert.deepEqual(rows, [{ id: "1", text: "a, b" }, { id: "2", text: "line1\nline2" }]);
});
