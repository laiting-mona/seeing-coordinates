// Keyword-based intent classification (query.INTENT_KEYWORDS): first matching intent wins.
// Last edited: 2026-11-17: first version.

export type Intent = "provenance" | "authority" | "path" | "recommend" | "lineage" | "relation" | "default";

export const INTENT_KEYWORDS: Array<[Intent, string[]]> = [
  ["provenance", ["出處", "根據", "來源", "可信", "真的假的", "查核", "文獻", "腦補", "求證", "依據", "哪來", "憑"]],
  ["authority", ["權威", "平台", "podcast", "網站", "算數", "夠格", "在紅", "有料", "評論來源"]],
  ["path", ["路線", "順序", "三週", "三禮拜", "清單", "讀書計畫", "備課", "循序"]],
  ["recommend", ["推薦", "下一本", "接下來", "讀什麼", "讀啥", "下一步", "該讀", "然後呢", "救救"]],
  ["lineage", ["演變", "之後", "接手", "後來", "怎麼變", "反駁", "繼續講", "發展", "怎麼來", "消逝之後"]],
  ["relation", ["關係", "關聯", "批判", "對話", "差在哪", "差別", "vs", "比起來", "兜", "理一下", "反什麼", "有關", "分不清"]],
];

export class IntentClassifier {
  constructor(private readonly rules: Array<[Intent, string[]]> = INTENT_KEYWORDS) {}

  classify(question: string): Intent {
    for (const [intent, keywords] of this.rules) {
      if (keywords.some((k) => question.includes(k))) return intent;
    }
    return "default";
  }
}
