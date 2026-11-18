// Controlled vocabulary shared by every module: node types, relation kinds, roles, tiers and their labels.
// Last edited: 2026-11-17: first version, ported from schema.py and authority.py (values must stay identical).

export type NodeType = "person" | "work" | "concept" | "event" | "institution" | "group";
export type Kind =
  | "influence" | "critique" | "extend" | "belongs_to" | "contrast" | "discusses"
  | "translate" | "study" | "review" | "interpret" | "exhibit";
export type Role = "author" | "contributor" | "movement" | "member" | "award" | "participant" | "part_of";
export type Tier = "primary" | "institution" | "critic" | "popular" | "other";
export type Status = "auto" | "review" | "approved" | "rejected";

/** Chinese verb shown for each relation kind (schema.KIND_VERB_ZH). */
export const KIND_VERB_ZH: Record<string, string> = {
  influence: "影響了", critique: "批判了", extend: "延伸自", belongs_to: "屬於",
  contrast: "對照於", discusses: "討論了", translate: "翻譯了", study: "研究了",
  review: "評論了", interpret: "詮釋了", exhibit: "展出了",
};

/** Chinese verb for a belongs_to edge, by role (schema.ROLE_VERB_ZH). */
export const ROLE_VERB_ZH: Record<string, string> = {
  author: "作者是", contributor: "收錄於", movement: "屬於流派", member: "成員於",
  award: "獲獎", participant: "參與", part_of: "隸屬於",
};

/** Source tier weights, highest first (authority.TIER_BASE). Insertion order is the display order. */
export const TIER_BASE: Record<string, number> = {
  primary: 0.85, institution: 0.75, critic: 0.6, popular: 0.3, other: 0.4,
};

/** auto and approved relations are in the formal graph; review is pending. */
export function isInGraph(status: string | null | undefined): boolean {
  return status === "auto" || status === "approved";
}
