// String helpers that reproduce Python semantics the answers depend on (code-point slicing, sorting, repr).
// Last edited: 2026-11-17: first version.

/** Split into Unicode code points, as Python indexes a str. */
export function codePoints(s: string): string[] {
  return Array.from(s);
}

/** Compare two strings by code point, as Python's < does (JS compares UTF-16 units). */
export function cmpCodePoint(a: string, b: string): number {
  const x = codePoints(a);
  const y = codePoints(b);
  const n = Math.min(x.length, y.length);
  for (let i = 0; i < n; i++) {
    const d = (x[i].codePointAt(0) as number) - (y[i].codePointAt(0) as number);
    if (d !== 0) return d < 0 ? -1 : 1;
  }
  return x.length === y.length ? 0 : x.length < y.length ? -1 : 1;
}

/** Python: text.lower().replace(" ", "") */
export function normalize(text: string): string {
  return text.toLowerCase().split(" ").join("");
}

/** Python str(float): integral values keep ".0". */
export function pyFloat(x: number): string {
  if (!Number.isFinite(x)) return x > 0 ? "inf" : x < 0 ? "-inf" : "nan";
  return Number.isInteger(x) ? x.toFixed(1) : String(x);
}

/** Python f-string formatting of a value that may be None, a float or a string. */
export function pyStr(v: unknown): string {
  if (v === null || v === undefined) return "None";
  if (typeof v === "number") return pyFloat(v);
  return String(v);
}

/** Python round(x, 2) for a double: correctly rounded, ties to even. */
export function round2(x: number): number {
  const scaled = x * 100;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  // decide with the exact decimal expansion to avoid binary noise on the multiplication
  const exact = Number(x.toFixed(2));
  if (Math.abs(diff - 0.5) > 1e-9) return exact;
  return (floor % 2 === 0 ? floor : floor + 1) / 100;
}
