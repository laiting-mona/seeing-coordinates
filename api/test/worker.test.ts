// Tests for the Cloudflare Worker: routing, the usage log (validation, origin, limits, purge) and /api/answer.
// D1 is stood in for by node:sqlite with the real migration file; static assets by a small fetch function.
// Last edited: 2026-11-18: first version (log cases ported from the 2026-11-15 worker.test.mjs).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { cleanEvent, type D1Like } from "../src/log/usageLog.js";
import worker, { type Env } from "../src/worker.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const API = resolve(HERE, "../..");
const GRAPH = resolve(API, "../build/graph.json");
const SELF = "https://seeing-coordinates.example.workers.dev";
const SESSION = "abcdefghij0123456789";
const ASK = { type: "ask", session: SESSION, group: "ntu-photo", question: "讀完《明室》下一本讀什麼？", qid: "Q0611",
              intent: "recommend", sha: "cf605ac0e842", exact: 0 };

/** D1 stand-in: prepare(sql).bind(...args) with run() and first(column), on an in-memory SQLite database. */
async function d1Shim(schemaSql: string): Promise<D1Like & { raw: any }> {
  const { DatabaseSync } = (await import("node:" + "sqlite")) as any;
  const db = new DatabaseSync(":memory:");
  db.exec(schemaSql);
  const prepare = (sql: string) => ({ bind: (...args: unknown[]) => ({
    run: async () => db.prepare(sql).run(...args),
    first: async (col?: string) => { const row = db.prepare(sql).get(...args); return row ? (col ? row[col] : row) : null; } }) });
  return { prepare, raw: db } as D1Like & { raw: any };
}

/** Static-assets stand-in: graph.json from build/, 404 for everything else. */
const assets = { fetch: async (req: Request | string) => {
  const path = new URL(typeof req === "string" ? req : req.url).pathname;
  return path === "/graph.json" ? new Response(readFileSync(GRAPH, "utf-8"), { headers: { "content-length": "1" } })
                                : new Response("not found", { status: 404 });
} };

async function makeEnv(): Promise<Env & { DB: D1Like & { raw: any } }> {
  const DB = await d1Shim(readFileSync(resolve(API, "migrations/0001_usage_log.sql"), "utf-8"));
  return { ASSETS: assets, DB, RATE_SALT: "test-salt", ALLOWED_ORIGINS: "" };
}

const post = (body: unknown, headers: Record<string, string> = {}) => new Request(`${SELF}/log`, { method: "POST",
  headers: { Origin: SELF, "Content-Type": "application/json", "CF-Connecting-IP": "203.0.113.7", ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body) });

test("a valid event from the site's own origin is stored, without any IP", async () => {
  const env = await makeEnv();
  assert.equal((await worker.fetch(post(ASK), env)).status, 204);
  const row = env.DB.raw.prepare("SELECT * FROM events").get();
  assert.equal(row.question, ASK.question);
  assert.equal(row.grp, "ntu-photo");
  assert.equal(Object.keys(row).some((k) => k.includes("ip")), false);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM rate WHERE k LIKE '%203.0.113%'").get().n, 0);
});

test("other origins, reads, unknown routes and malformed events are refused", async () => {
  const env = await makeEnv();
  assert.equal((await worker.fetch(post(ASK, { Origin: "https://evil.example" }), env)).status, 403);
  assert.equal((await worker.fetch(new Request(`${SELF}/log`), env)).status, 405);
  assert.equal((await worker.fetch(new Request(`${SELF}/api/events`), env)).status, 404);
  assert.equal((await worker.fetch(post("not json"), env)).status, 400);
  assert.equal((await worker.fetch(post({ ...ASK, type: "drop table" }), env)).status, 400);
  assert.equal((await worker.fetch(post({ ...ASK, session: "x'; DROP TABLE events;--" }), env)).status, 400);
  assert.equal((await worker.fetch(post({ ...ASK, question: "" }), env)).status, 400);
  assert.equal((await worker.fetch(post({ type: "click", session: SESSION, target: "javascript:alert(1)" }), env)).status, 400);
  assert.equal((await worker.fetch(post({ ...ASK, question: "長".repeat(5000) }), env)).status, 400);
  assert.equal(cleanEvent({ ...ASK, question: "a".repeat(900) })!.question.length, 500);
  assert.equal((await worker.fetch(post({ ...ASK, question: "Robert'); DROP TABLE events;--" }), env)).status, 204);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM events").get().n, 1);
});

test("an extra origin listed in ALLOWED_ORIGINS gets CORS headers on the preflight", async () => {
  const env = { ...(await makeEnv()), ALLOWED_ORIGINS: "https://seeing-coordinates.pages.dev" };
  const pre = await worker.fetch(new Request(`${SELF}/log`, { method: "OPTIONS", headers: { Origin: "https://seeing-coordinates.pages.dev" } }), env);
  assert.equal(pre.headers.get("Access-Control-Allow-Origin"), "https://seeing-coordinates.pages.dev");
});

test("a session is limited to 200 events a day and old counters are purged", async () => {
  const env = await makeEnv();
  let last = 0;
  for (let i = 0; i < 210; i++) last = (await worker.fetch(post({ type: "open", session: SESSION, qid: "Q0001" }), env)).status;
  assert.equal(last, 429);
  assert.ok(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM events").get().n <= 200);
  env.DB.raw.prepare("INSERT INTO rate (k, day, n) VALUES ('old', '2020-01-01', 5)").run();
  await worker.scheduled({}, env);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM rate WHERE day < date('now')").get().n, 0);
});

test("/api/answer answers from the snapshot; /api/health reports a missing data copy as null", async () => {
  const env = await makeEnv();
  const res = await worker.fetch(new Request(`${SELF}/api/answer?q=${encodeURIComponent("《觀看的方式》看完了，接下來讀什麼比較順？")}`), env);
  const body = await res.json() as { intent: string; ids: string[]; text: string };
  assert.equal(res.headers.get("access-control-allow-origin"), "*");
  assert.equal(body.intent, "recommend");
  assert.equal(body.ids[0], "ways_of_seeing");
  assert.equal((await worker.fetch(new Request(`${SELF}/api/answer`), env)).status, 400);
  const health = await (await worker.fetch(new Request(`${SELF}/api/health`), env)).json() as { ok: boolean; data: unknown };
  assert.equal(health.ok, true);
  assert.equal(health.data, null);
});

test("/api/health counts rows when the D1 data copy is bound", async () => {
  const tables = ["entity", "assertion", "evidence", "source", "review_event"].map((t) => `CREATE TABLE ${t} (id TEXT);`).join("");
  const DATA = await d1Shim(tables + "INSERT INTO entity VALUES ('a'), ('b');");
  const env = { ...(await makeEnv()), DATA };
  const health = await (await worker.fetch(new Request(`${SELF}/api/health`), env)).json() as { data: Record<string, number> };
  assert.equal(health.data.entity, 2);
  assert.equal(health.data.assertion, 0);
});

test("everything else is handed to the static assets", async () => {
  const env = await makeEnv();
  assert.equal((await worker.fetch(new Request(`${SELF}/graph.json`), env)).status, 200);
  assert.equal((await worker.fetch(new Request(`${SELF}/missing.html`), env)).status, 404);
});
