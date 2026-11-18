// Structured handler result → reader-facing text (port of query.render_*; strings must stay identical).
// Last edited: 2026-11-17: first version.

import type { EdgeRecord, HandlerResult } from "../domain/types.js";
import { isInGraph, KIND_VERB_ZH, ROLE_VERB_ZH } from "../domain/vocab.js";
import { pyStr } from "../text/pystr.js";

function verbOf(e: EdgeRecord): string {
  return e.role ? pyStr(ROLE_VERB_ZH[e.role] ?? null) : (KIND_VERB_ZH[e.kind ?? ""] ?? pyStr(e.kind));
}

export function edgeLine(e: EdgeRecord): string {
  const tag = isInGraph(e.status) ? "入圖" : "待判斷";
  return `${e.from} ${verbOf(e)} ${e.to}(可信度 ${pyStr(e.confidence)}、${pyStr(e.tier)}層、出處 ${pyStr(e.source)}、${tag})`;
}

type Renderer = (r: HandlerResult) => string;

const renderRecommend: Renderer = (r) => {
  if (!r.resolved) return "沒抓到你讀過的作者或書,換個講法?";
  const items = r.items as Array<{ target: string; reason: string; source: string }>;
  if (!items.length) return `以「${r.seed}」為起點,鄰居都讀過了,可能要擴充來源。`;
  return `📚 你讀過「${r.seed}」,沿知識前緣建議下一步:\n`
    + items.map((i) => `  • ${i.target} - ${i.reason}（出處:${i.source}）`).join("\n");
};

const renderProvenance: Renderer = (r) => {
  if (!r.resolved) return "說清楚你要查哪兩者的關係,我把出處調出來。";
  if (!r.found) return `🔎 圖上目前沒有「${r.a}」和「${r.b}」的關係,所以我不會編一個給你。`;
  return (r.edges as EdgeRecord[]).map((e) => {
    const tag = isInGraph(e.status) ? "已入圖(查證或可信度達標)" : "⚠ 待人工判斷(尚未確認,不可當定論)";
    return `🔎 查核:${e.from} ${verbOf(e)} ${e.to}\n  主張:${pyStr(e.claim)}\n`
      + `  證據:${e.evidence || "(無)"}\n  出處:${pyStr(e.source)}　來源層:${pyStr(e.tier)}`
      + `　可信度:${pyStr(e.confidence)}\n  狀態:${tag}`;
  }).join("\n");
};

const renderLineage: Renderer = (r) => {
  if (!r.resolved) return "沒抓到要追的概念,換個講法?";
  const lines = [`🧬「${r.concept}」的脈絡:`];
  lines.push(...(r.origin as EdgeRecord[]).map((e) => `  源頭:${edgeLine(e)}`));
  lines.push(...(r.followups as EdgeRecord[]).map((e) => `  後續:${edgeLine(e)}`));
  if (lines.length === 1) lines.push("  圖上還沒有指向它的關係。");
  return lines.join("\n");
};

const renderRelation: Renderer = (r) => {
  if (r.direct) return "🔗 有直接關係:\n" + (r.edges as EdgeRecord[]).map((e) => "  " + edgeLine(e)).join("\n");
  const path = r.path as string[];
  if (path && path.length) return "🔗 沒有直接關係,但有間接連結:" + path.join(" → ");
  return `🔗「${r.a}」和「${r.b}」目前在圖上還沒連起來。`;
};

const renderAuthority: Renderer = (r) => {
  const lines = ["🏛 權威分層與權重(越上面越權威):"];
  lines.push(...(r.tiers as Array<[string, number]>).map(([tier, w]) => `  ${tier}:${pyStr(w)}`));
  lines.push("大眾/推廣型(podcast、評論平台)歸 popular、權重最低,看『現在在討論什麼』用,不當建立正典的依據。");
  lines.push(...(r.popular_examples as EdgeRecord[]).map((e) => `  • ${pyStr(e.source)}:${e.from} ${pyStr(e.kind)} ${e.to}(待查證)`));
  return lines.join("\n");
};

const renderPath: Renderer = (r) =>
  "🗓 三週入門路線(從『觀看的政治』進,循主線遞進):\n"
  + (r.weeks as string[][]).map((w) => `  ${w[0]}:${w[1]} | ${w[2]}`).join("\n");

const renderDefault: Renderer = (r) => {
  const lines = [`ℹ 關於「${r.node}」,圖上的關係:`];
  lines.push(...(r.out as EdgeRecord[]).map((e) => `  → ${edgeLine(e)}`));
  lines.push(...(r.in as EdgeRecord[]).map((e) => `  ← ${edgeLine(e)}`));
  return lines.join("\n");
};

const RENDERERS: Record<string, Renderer> = {
  recommend: renderRecommend, provenance: renderProvenance, lineage: renderLineage, relation: renderRelation,
  authority: renderAuthority, path: renderPath, default: renderDefault,
};

export function renderAnswer(result: HandlerResult): string {
  const renderer = RENDERERS[result.type];
  return renderer ? renderer(result) : "我沒抓到你問的是哪個人、概念或作品,可以講得具體一點。";
}
