// Write-only usage log for the trial site (Cloudflare D1). The browser can add rows; nothing here reads rows back.
// Last edited: 2026-11-18: ported from the 2026-11-15 logging Worker (worker/src/index.js) into the single Worker;
// same validation, salted one-day client key and daily limits; same-origin requests are allowed without configuration.

const MAX_BODY_BYTES = 4096;
const MAX_PER_CLIENT_PER_DAY = 300;
const MAX_PER_SESSION_PER_DAY = 200;
const TYPES = new Set(["consent", "ask", "open", "click", "map"]);
const RULES: Record<string, RegExp> = {
  session: /^[a-z0-9]{16,32}$/,
  grp: /^[A-Za-z0-9_-]{0,24}$/,
  qid: /^(Q\d{4})?$/,
  intent: /^[a-z_]{0,24}$/,
  sha: /^[a-f0-9]{0,16}$/,
};

/** Minimal shape of a D1 binding, so this file needs no Cloudflare type package. */
export interface D1Like {
  prepare(sql: string): { bind(...args: unknown[]): { run(): Promise<unknown>; first<T = unknown>(column?: string): Promise<T | null> } };
}

export interface LogEnv {
  DB: D1Like;
  ALLOWED_ORIGINS?: string;
  RATE_SALT?: string;
}

export interface UsageEvent {
  type: string; session: string; grp: string; qid: string; intent: string; sha: string;
  question: string; target: string; exact: number;
}

/** Origins allowed to send logs: the Worker's own origin plus the comma-separated ALLOWED_ORIGINS. */
function allowedOrigins(env: LogEnv, self: string): string[] {
  return [self, ...String(env.ALLOWED_ORIGINS ?? "").split(",").map((s) => s.trim()).filter(Boolean)];
}

/** CORS headers for an allowed origin; empty object otherwise. */
export function corsHeaders(origin: string | null, env: LogEnv, self: string): Record<string, string> {
  if (!origin || !allowedOrigins(env, self).includes(origin)) return {};
  return { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
           "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400", Vary: "Origin" };
}

/** Plain response with status, extra headers and no caching. */
export function reply(status: number, text: string | null, headers: Record<string, string>): Response {
  return new Response(text, { status, headers: { "Cache-Control": "no-store", ...headers } });
}

/** Trim a value to a string of at most max characters. */
function clip(value: unknown, max: number): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

/** Validate the request payload. Returns a clean event or null. */
export function cleanEvent(raw: unknown): UsageEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.type !== "string" || !TYPES.has(r.type)) return null;
  const event: UsageEvent = { type: r.type, session: clip(r.session, 32), grp: clip(r.group, 24), qid: clip(r.qid, 5),
    intent: clip(r.intent, 24), sha: clip(r.sha, 16), question: clip(r.question, 500), target: clip(r.target, 300),
    exact: r.exact ? 1 : 0 };
  for (const [field, rule] of Object.entries(RULES)) {
    if (!rule.test(event[field as keyof UsageEvent] as string)) return null;
  }
  if (event.type === "ask" && !event.question) return null;
  if (event.target && !/^https?:\/\//.test(event.target)) return null;
  return event;
}

/** One-day pseudonymous key for a client. The raw IP is hashed with the day and a secret salt and never stored. */
async function clientKey(request: Request, env: LogEnv, day: string): Promise<string> {
  const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";
  const bytes = new TextEncoder().encode(`${ip}|${day}|${env.RATE_SALT ?? ""}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return "c:" + [...digest.slice(0, 8)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Add one to a daily counter and return the new count. */
async function bump(db: D1Like, key: string, day: string): Promise<number> {
  const sql = "INSERT INTO rate (k, day, n) VALUES (?, ?, 1) ON CONFLICT(k, day) DO UPDATE SET n = n + 1 RETURNING n";
  return Number(await db.prepare(sql).bind(key, day).first("n"));
}

/** True when either the client or the session has exceeded its daily allowance. */
async function overLimit(request: Request, env: LogEnv, event: UsageEvent, day: string): Promise<boolean> {
  const client = await bump(env.DB, await clientKey(request, env, day), day);
  const session = await bump(env.DB, "s:" + event.session, day);
  return client > MAX_PER_CLIENT_PER_DAY || session > MAX_PER_SESSION_PER_DAY;
}

/** Insert one validated event with the server's timestamp. */
async function insertEvent(db: D1Like, event: UsageEvent, ts: string): Promise<void> {
  const sql = "INSERT INTO events (ts, session, grp, type, question, qid, intent, sha, exact, target) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
  await db.prepare(sql).bind(ts, event.session, event.grp, event.type, event.question, event.qid, event.intent,
                              event.sha, event.exact, event.target).run();
}

/** Read the body as JSON while enforcing the size limit. Returns null on any problem. */
async function readJson(request: Request): Promise<unknown> {
  if (Number(request.headers.get("Content-Length") ?? 0) > MAX_BODY_BYTES) return null;
  const text = await request.text();
  if (new TextEncoder().encode(text).length > MAX_BODY_BYTES) return null;
  try { return JSON.parse(text); } catch { return null; }
}

/** POST /log: origin check, size check, validation, rate limit, insert. */
export async function handleLog(request: Request, env: LogEnv): Promise<Response> {
  const self = new URL(request.url).origin;
  const cors = corsHeaders(request.headers.get("Origin"), env, self);
  if (!cors["Access-Control-Allow-Origin"]) return reply(403, "origin not allowed", {});
  const event = cleanEvent(await readJson(request));
  if (!event) return reply(400, "invalid event", cors);
  const now = new Date();
  if (await overLimit(request, env, event, now.toISOString().slice(0, 10))) return reply(429, "too many requests", cors);
  await insertEvent(env.DB, event, now.toISOString());
  return reply(204, null, cors);
}

/** Remove counters from earlier days (run daily by the cron trigger). */
export async function purgeCounters(db: D1Like, today: string): Promise<void> {
  await db.prepare("DELETE FROM rate WHERE day < ?").bind(today).run();
}
