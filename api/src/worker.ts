// Cloudflare Worker for 觀看的坐標: serves the trial site from static assets and three small routes.
//   GET  /api/answer?q=問句  → JSON {intent, ids, result, text}, answered from the graph snapshot only
//   GET  /api/health         → graph snapshot size and row counts of the D1 data copy
//   POST /log                → write-only usage log (consent-based; see src/log/usageLog.ts)
// Last edited: 2026-11-18: one Worker for site + API + log (replaces the R2 query Worker and the separate log Worker);
// the snapshot is read from static assets once per isolate. No account is configured here: bindings are declared in
// wrangler.toml and the account owner fills in the D1 ids after `wrangler d1 create`.

import { AssetsGraphSource, type AssetsLike } from "./io/graphSource.js";
import { handleLog, purgeCounters, reply, corsHeaders, type D1Like } from "./log/usageLog.js";
import { QueryEngine } from "./query/QueryEngine.js";

export interface Env {
  ASSETS: AssetsLike;
  DB: D1Like;            // usage log (events, rate)
  DATA?: D1Like;         // v2 data copy (entity, assertion, evidence, ...)
  ALLOWED_ORIGINS?: string;
  RATE_SALT?: string;
}

const DATA_TABLES = ["entity", "assertion", "evidence", "source", "review_event"];
let enginePromise: Promise<QueryEngine> | null = null;

/** The query engine for this isolate, built once from the static graph snapshot. */
function engineFor(env: Env): Promise<QueryEngine> {
  if (!enginePromise) {
    enginePromise = new AssetsGraphSource(env.ASSETS).load().then((g) => new QueryEngine(g));
    enginePromise.catch(() => { enginePromise = null; });   // retry on the next request after a failed load
  }
  return enginePromise;
}

/** JSON response readable from any origin (the API is public, read-only data). */
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*", "cache-control": "no-store" },
  });
}

/** GET /api/answer: one question in, the engine's answer out. */
async function handleAnswer(url: URL, env: Env): Promise<Response> {
  const question = (url.searchParams.get("q") ?? "").trim().slice(0, 500);
  if (!question) return json({ error: "missing q" }, 400);
  const answer = (await engineFor(env)).answer(question);
  return json({ intent: answer.intent, ids: answer.ids.slice(0, 4), result: answer.result, text: answer.text });
}

/** Row counts of the D1 data copy; null when the binding is missing or the tables are not loaded yet. */
async function dataCounts(env: Env): Promise<Record<string, number> | null> {
  if (!env.DATA) return null;
  try {
    const counts: Record<string, number> = {};
    for (const table of DATA_TABLES) counts[table] = Number(await env.DATA.prepare(`SELECT COUNT(*) AS n FROM ${table}`).bind().first("n"));
    return counts;
  } catch {
    return null;
  }
}

/** GET /api/health: confirms the deploy has the snapshot and, if loaded, the D1 data copy. */
async function handleHealth(env: Env): Promise<Response> {
  const snapshot = await env.ASSETS.fetch(new Request("https://assets.local/graph.json"));
  return json({ ok: snapshot.ok, data: await dataCounts(env) });
}

/** /log accepts POST (and the CORS preflight) only. */
async function routeLog(request: Request, env: Env): Promise<Response> {
  if (request.method === "OPTIONS") return reply(204, null, corsHeaders(request.headers.get("Origin"), env, new URL(request.url).origin));
  if (request.method !== "POST") return reply(405, "method not allowed", { Allow: "POST, OPTIONS" });
  return handleLog(request, env);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/log") return routeLog(request, env);
    if (url.pathname === "/api/answer" && request.method === "GET") return handleAnswer(url, env);
    if (url.pathname === "/api/health" && request.method === "GET") return handleHealth(env);
    if (url.pathname.startsWith("/api/")) return json({ error: "not found" }, 404);
    return env.ASSETS.fetch(request);
  },
  async scheduled(_controller: unknown, env: Env): Promise<void> {
    await purgeCounters(env.DB, new Date().toISOString().slice(0, 10));
  },
};
