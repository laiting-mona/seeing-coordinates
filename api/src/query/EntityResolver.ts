// Finds the graph nodes a question mentions: exact surface forms first, difflib-style fuzzy windows second.
// Last edited: 2026-11-17: first version, ported from query.QueryEngine._build_form_index / resolve;
// same day: fuzzy pass uses CloseMatcher (length buckets), identical results, much faster.

import type { KnowledgeGraph } from "../graph/KnowledgeGraph.js";
import { CloseMatcher, SequenceMatcher } from "../text/difflib.js";
import { cmpCodePoint, codePoints, normalize, round2 } from "../text/pystr.js";

export const FUZZY_CUTOFF = 0.8;           // 0.75 let 的攝影 match 遲到的攝影; 0.8 keeps genuine typos (桑塔各)
const MIN_FORM_LEN = 2;
const MIN_WINDOW_LEN = 4;
const MAX_WINDOW_LEN = 14;
const MIN_SURNAME_LEN = 4;

/** Surface forms users type that differ from stored names (query.ALIASES). */
export const ALIASES: Record<string, string> = {
  "索引": "krauss", "index": "krauss",
  "新地誌": "new_topographics_1975", "new topographics": "new_topographics_1975",
  "庶民": "vernacular", "冷面": "deadpan",
  "布列松": "cartier_bresson", "cartier-bresson": "cartier_bresson", "cartier bresson": "cartier_bresson",
  "布迪厄": "bourdieu", "伯格": "berger",
  "克萊因": "klein", "柯特茲": "kertesz", "阿巴斯": "arbus",
  "馬格南": "magnum", "泰特": "tate", "大都會": "met", "現代美術館": "moma", "伊士曼": "eastman", "阿爾勒": "arles",
  "觀看的方式": "ways_of_seeing", "ways of seeing": "ways_of_seeing",
  "論攝影": "on_photography", "on photography": "on_photography",
  "明室": "camera_lucida", "camera lucida": "camera_lucida",
};

export class EntityResolver {
  readonly formToId: Map<string, string>;
  private readonly matcher: CloseMatcher;

  constructor(private readonly graph: KnowledgeGraph, aliases: Record<string, string> = ALIASES) {
    this.formToId = EntityResolver.buildFormIndex(graph, aliases);
    this.matcher = new CloseMatcher([...this.formToId.keys()]);
  }

  /** Chinese name, English name, unambiguous English surname of a person, then aliases (which override). */
  static buildFormIndex(graph: KnowledgeGraph, aliases: Record<string, string>): Map<string, string> {
    const index = new Map<string, string>();
    const surnameOwners = new Map<string, Set<string>>();
    const setDefault = (form: string, id: string) => { if (!index.has(form)) index.set(form, id); };
    for (const node of graph.nodes()) {
      for (const form of [node.name_zh, node.name_en]) {
        if (form && codePoints(normalize(form)).length >= MIN_FORM_LEN) setDefault(normalize(form), node.id);
      }
      if (node.type === "person" && node.name_en) {
        const parts = node.name_en.trim().split(/\s+/);
        const surname = normalize(parts[parts.length - 1]);
        if (codePoints(surname).length >= MIN_SURNAME_LEN) {
          if (!surnameOwners.has(surname)) surnameOwners.set(surname, new Set());
          surnameOwners.get(surname)!.add(node.id);
        }
      }
    }
    for (const [surname, owners] of surnameOwners) {
      if (owners.size === 1) setDefault(surname, [...owners][0]);
    }
    for (const [alias, id] of Object.entries(aliases)) index.set(normalize(alias), id);
    return index;
  }

  /** Node ids mentioned in the question, best match first. */
  resolve(question: string): string[] {
    const q = normalize(question);
    const scores = new Map<string, number>();
    const bump = (id: string, s: number) => scores.set(id, Math.max(scores.get(id) ?? 0, s));
    let exact = [...this.formToId].filter(([form]) => q.includes(form));
    // drop a short form that is merely part of a longer matched form (塔格 inside 桑塔格)
    exact = exact.filter(([f]) => !exact.some(([g]) => f !== g && g.includes(f)));
    for (const [form, id] of exact) bump(id, codePoints(form).length > 2 ? 1.0 : 0.9);
    if (scores.size === 0) {
      for (const window of this.windows(q)) {
        for (const form of this.matcher.match(window, 2, FUZZY_CUTOFF)) {
          bump(this.formToId.get(form)!, round2(new SequenceMatcher(form, window).ratio()));
        }
      }
    }
    return [...scores.entries()].sort((x, y) => y[1] - x[1]).map(([id]) => id);   // stable, like sorted()
  }

  /** Every substring of length 4..14 (code points), deduplicated and sorted by code point. */
  private windows(q: string): string[] {
    const cps = codePoints(q);
    const set = new Set<string>();
    for (let len = MIN_WINDOW_LEN; len <= Math.min(MAX_WINDOW_LEN, cps.length); len++) {
      for (let i = 0; i + len <= cps.length; i++) set.add(cps.slice(i, i + len).join(""));
    }
    return [...set].sort(cmpCodePoint);
  }
}
