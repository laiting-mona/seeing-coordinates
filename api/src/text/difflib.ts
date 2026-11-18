// Port of the parts of Python's difflib that the resolver uses: SequenceMatcher ratios and get_close_matches.
// Last edited: 2026-11-17: first version. Follows CPython 3 difflib line by line so scores and tie-breaks match.

import { cmpCodePoint, codePoints } from "./pystr.js";

type Block = [number, number, number];

export class SequenceMatcher {
  private a: string[] = [];
  private b: string[] = [];
  private b2j = new Map<string, number[]>();
  private bpopular = new Set<string>();
  private fullbcount: Map<string, number> | null = null;
  private matchingBlocks: Block[] | null = null;

  constructor(a = "", b = "", private autojunk = true) {
    this.setSeq2(b);
    this.setSeq1(a);
  }

  setSeq1(a: string): void {
    this.a = codePoints(a);
    this.matchingBlocks = null;
  }

  setSeq2(b: string): void {
    this.b = codePoints(b);
    this.matchingBlocks = null;
    this.fullbcount = null;
    this.chainB();
  }

  /** b2j maps each element of b to the indices where it occurs; popular elements are dropped for long b. */
  private chainB(): void {
    const b2j = new Map<string, number[]>();
    this.b.forEach((elt, i) => {
      const list = b2j.get(elt);
      if (list) list.push(i);
      else b2j.set(elt, [i]);
    });
    this.bpopular = new Set();
    const n = this.b.length;
    if (this.autojunk && n >= 200) {
      const ntest = Math.floor(n / 100) + 1;
      for (const [elt, idxs] of b2j) {
        if (idxs.length > ntest) this.bpopular.add(elt);
      }
      for (const elt of this.bpopular) b2j.delete(elt);
    }
    this.b2j = b2j;
  }

  findLongestMatch(alo: number, ahi: number, blo: number, bhi: number): Block {
    const { a, b, b2j } = this;
    let besti = alo;
    let bestj = blo;
    let bestsize = 0;
    let j2len = new Map<number, number>();
    for (let i = alo; i < ahi; i++) {
      const newj2len = new Map<number, number>();
      for (const j of b2j.get(a[i]) ?? []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) ?? 0) + 1;
        newj2len.set(j, k);
        if (k > bestsize) {
          besti = i - k + 1;
          bestj = j - k + 1;
          bestsize = k;
        }
      }
      j2len = newj2len;
    }
    // CPython then extends the match over equal non-junk elements on both sides (this picks up "popular"
    // elements dropped from b2j); no isjunk is ever passed here, so its two junk-only loops never run.
    while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
      besti--; bestj--; bestsize++;
    }
    while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) {
      bestsize++;
    }
    return [besti, bestj, bestsize];
  }

  getMatchingBlocks(): Block[] {
    if (this.matchingBlocks) return this.matchingBlocks;
    const la = this.a.length;
    const lb = this.b.length;
    const queue: Array<[number, number, number, number]> = [[0, la, 0, lb]];
    const blocks: Block[] = [];
    while (queue.length) {
      const [alo, ahi, blo, bhi] = queue.pop() as [number, number, number, number];
      const x = this.findLongestMatch(alo, ahi, blo, bhi);
      const [i, j, k] = x;
      if (k) {
        blocks.push(x);
        if (alo < i && blo < j) queue.push([alo, i, blo, j]);
        if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
      }
    }
    blocks.sort((p, q) => p[0] - q[0] || p[1] - q[1] || p[2] - q[2]);
    const merged: Block[] = [];
    let [i1, j1, k1] = [0, 0, 0];
    for (const [i2, j2, k2] of blocks) {
      if (i1 + k1 === i2 && j1 + k1 === j2) {
        k1 += k2;
      } else {
        if (k1) merged.push([i1, j1, k1]);
        [i1, j1, k1] = [i2, j2, k2];
      }
    }
    if (k1) merged.push([i1, j1, k1]);
    merged.push([la, lb, 0]);
    this.matchingBlocks = merged;
    return merged;
  }

  ratio(): number {
    const matches = this.getMatchingBlocks().reduce((s, blk) => s + blk[2], 0);
    return calculateRatio(matches, this.a.length + this.b.length);
  }

  quickRatio(): number {
    if (this.fullbcount === null) {
      this.fullbcount = new Map();
      for (const elt of this.b) this.fullbcount.set(elt, (this.fullbcount.get(elt) ?? 0) + 1);
    }
    const avail = new Map<string, number>();
    let matches = 0;
    for (const elt of this.a) {
      const numb = avail.has(elt) ? (avail.get(elt) as number) : (this.fullbcount.get(elt) ?? 0);
      avail.set(elt, numb - 1);
      if (numb > 0) matches++;
    }
    return calculateRatio(matches, this.a.length + this.b.length);
  }

  realQuickRatio(): number {
    const la = this.a.length;
    const lb = this.b.length;
    return calculateRatio(Math.min(la, lb), la + lb);
  }
}

function calculateRatio(matches: number, length: number): number {
  return length ? (2.0 * matches) / length : 1.0;
}

/** difflib.get_close_matches: best n possibilities scoring >= cutoff, ties broken as Python tuples sort. */
export function getCloseMatches(word: string, possibilities: string[], n = 3, cutoff = 0.6): string[] {
  const result: Array<[number, string]> = [];
  const s = new SequenceMatcher();
  s.setSeq2(word);
  for (const x of possibilities) {
    s.setSeq1(x);
    if (s.realQuickRatio() >= cutoff && s.quickRatio() >= cutoff && s.ratio() >= cutoff) {
      result.push([s.ratio(), x]);
    }
  }
  // heapq.nlargest(n, result) == sorted(result, reverse=True)[:n]
  result.sort((p, q) => (q[0] - p[0]) || -cmpCodePoint(p[1], q[1]));
  return result.slice(0, n).map((r) => r[1]);
}

/**
 * get_close_matches over a fixed list of possibilities with identical results, built for repeated calls:
 * - real_quick_ratio depends only on the two lengths, so it is checked first;
 * - quick_ratio is the multiset overlap of characters, computed for all candidates at once from a
 *   character -> (candidate, count) index, so only candidates that share enough characters reach ratio();
 * - results are memoised per word (windows repeat across questions, and a Worker isolate serves many requests).
 */
export class CloseMatcher {
  private readonly forms: string[];
  private readonly lengths: Int32Array;
  private readonly postings = new Map<string, Array<[number, number]>>();
  private readonly cache = new Map<string, string[]>();
  private readonly overlap: Int32Array;

  constructor(possibilities: string[]) {
    this.forms = [...possibilities];
    this.lengths = new Int32Array(this.forms.length);
    this.overlap = new Int32Array(this.forms.length);
    this.forms.forEach((form, idx) => {
      const counts = new Map<string, number>();
      for (const c of codePoints(form)) counts.set(c, (counts.get(c) ?? 0) + 1);
      this.lengths[idx] = codePoints(form).length;
      for (const [c, n] of counts) {
        if (!this.postings.has(c)) this.postings.set(c, []);
        this.postings.get(c)!.push([idx, n]);
      }
    });
  }

  match(word: string, n: number, cutoff: number): string[] {
    const key = `${n}\u0000${cutoff}\u0000${word}`;
    const hit = this.cache.get(key);
    if (hit) return hit;
    const chars = codePoints(word);
    const lb = chars.length;
    const counts = new Map<string, number>();
    for (const c of chars) counts.set(c, (counts.get(c) ?? 0) + 1);
    const touched: number[] = [];
    for (const [c, cb] of counts) {
      for (const [idx, ca] of this.postings.get(c) ?? []) {
        if (this.overlap[idx] === 0) touched.push(idx);
        this.overlap[idx] += Math.min(ca, cb);
      }
    }
    const result: Array<[number, string]> = [];
    const s = new SequenceMatcher();
    s.setSeq2(word);
    for (const idx of touched) {
      const la = this.lengths[idx];
      const common = this.overlap[idx];
      this.overlap[idx] = 0;
      if (calculateRatio(Math.min(la, lb), la + lb) < cutoff || calculateRatio(common, la + lb) < cutoff) continue;
      s.setSeq1(this.forms[idx]);
      const r = s.ratio();
      if (r >= cutoff) result.push([r, this.forms[idx]]);
    }
    result.sort((p, q) => (q[0] - p[0]) || -cmpCodePoint(p[1], q[1]));
    const out = result.slice(0, n).map((r) => r[1]);
    this.cache.set(key, out);
    return out;
  }
}
