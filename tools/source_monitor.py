"""Source monitor: re-checks every verification URL the formal graph rests on.

Last edited: 2026-11-16: first version (same day: tls_error state, report wording, CJK quotes matched across stripped tags). For each URL cited by a formal (auto / approved) relation it
records whether the page still answers, where it redirects to, a hash of its text, and whether each
relation's verbatim quote is still on the page. A second run compares with the previous snapshot and
lists what changed (newly unreachable pages, quotes that disappeared, text that changed).

The monitor never edits data/. It only reports; moving a relation back to review stays a human decision.

Outputs (build/ is not version-controlled):
  build/monitor/source_status.jsonl   one row per URL, the latest snapshot
  build/monitor/report.md             summary, items needing attention, changes since the last run

Usage:
  python tools/source_monitor.py                      # all URLs, 1 s between requests to the same host
  python tools/source_monitor.py --sample 50 --seed 7 # a reproducible random sample
  python tools/source_monitor.py --host moma.org      # one host only
Exit code is 0 even when problems are found; read the report.
"""
import argparse
import datetime
import hashlib
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import data_io  # noqa: E402

STATUS_JSONL = "build/monitor/source_status.jsonl"
REPORT_MD = "build/monitor/report.md"
USER_AGENT = "seeing-coordinates-source-monitor/1.0 (link and quote check; one request per page)"
MAX_BYTES = 3_000_000
TEXT_TYPES = ("text/html", "application/xhtml", "text/plain")
TAG = re.compile(r"<[^>]+>")
DROP_BLOCK = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
PUNCT_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                           " ": " ", "　": " "})
# Quote states: found (verbatim after normalising), partial (most word runs present), missing, unchecked.
PARTIAL_THRESHOLD = 0.6
SHINGLE_WORDS = 5
CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def normalise(text: str) -> str:
    """Lower-case text with entities decoded, typographic punctuation folded and whitespace collapsed."""
    text = html.unescape(text or "").translate(PUNCT_MAP)
    return re.sub(r"\s+", " ", text).strip().casefold()


def page_text(body: str) -> str:
    """Visible text of an HTML document, normalised."""
    return normalise(TAG.sub(" ", DROP_BLOCK.sub(" ", body)))


def shingles(text: str) -> list[str]:
    """Runs of SHINGLE_WORDS consecutive words; for scripts without spaces, runs of 10 characters."""
    words = text.split(" ")
    if len(words) >= SHINGLE_WORDS:
        return [" ".join(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)]
    compact = text.replace(" ", "")
    return [compact[i:i + 10] for i in range(0, max(1, len(compact) - 9), 5)]


def quote_state(quote: str | None, text: str | None) -> str:
    """found / partial / missing for a quote against normalised page text; unchecked when either is absent."""
    if not quote or text is None:
        return "unchecked"
    wanted = normalise(quote)
    if not wanted:
        return "unchecked"
    if wanted in text:
        return "found"
    if CJK.search(wanted) and wanted.replace(" ", "") in text.replace(" ", ""):
        return "found"            # CJK text: spaces left by stripped tags (links, emphasis) are not part of the sentence
    runs = shingles(wanted)
    haystack = text if " " in wanted and len(wanted.split(" ")) >= SHINGLE_WORDS else text.replace(" ", "")
    share = sum(1 for run in runs if run in haystack) / len(runs)
    return "partial" if share >= PARTIAL_THRESHOLD else "missing"


def cited_urls(relations: list[dict]) -> dict[str, list[dict]]:
    """Map each verification URL to the formal relations (key and quote) that rest on it."""
    by_url: dict[str, list[dict]] = {}
    for relation in relations:
        if relation.get("status") not in data_io.IN_GRAPH_STATUSES:
            continue
        parsed = data_io.parse_evidence(relation.get("evidence", ""))
        if not parsed["evidence_url"]:
            continue
        key = "|".join(data_io.relation_key(relation))
        by_url.setdefault(parsed["evidence_url"], []).append({"relation": key, "quote": parsed["quote"]})
    return by_url


def fetch(url: str, timeout: float) -> dict:
    """One GET. Returns http status, final URL, content type and decoded text (None when not text)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            raw = response.read(MAX_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            is_text = any(content_type.startswith(t) for t in TEXT_TYPES)
            body = raw.decode(charset, errors="replace") if is_text else None
            return {"http": response.status, "final_url": response.geturl(), "content_type": content_type, "body": body,
                    "error": None}
    except urllib.error.HTTPError as error:
        return {"http": error.code, "final_url": url, "content_type": "", "body": None, "error": f"HTTP {error.code}"}
    except Exception as error:  # DNS failure, timeout, TLS error, refused connection
        return {"http": None, "final_url": url, "content_type": "", "body": None,
                "error": type(error).__name__ + ": " + str(error)[:120]}


def same_page(url: str, final_url: str) -> bool:
    """True when a redirect only changed the scheme, a leading www. or a trailing slash."""
    def core(value: str) -> tuple[str, str, str]:
        parts = urllib.parse.urlsplit(value)
        return parts.netloc.lower().removeprefix("www."), parts.path.rstrip("/"), parts.query
    return core(url) == core(final_url)


def page_state(result: dict, url: str) -> str:
    """ok / redirected / blocked / gone / unreachable / tls_error / not_text for one fetch result."""
    if result["http"] is None:
        # A certificate failure usually comes from this machine's certificate store or a filtering proxy,
        # so it is reported apart from pages that do not answer. Verification is never switched off.
        return "tls_error" if "CERTIFICATE_VERIFY_FAILED" in (result["error"] or "") else "unreachable"
    if result["http"] in (401, 403, 429):
        return "blocked"          # the site refuses automated requests; says nothing about the page itself
    if result["http"] >= 400:
        return "gone"
    if result["body"] is None:
        return "not_text"         # PDF or other binary: reachable, quote not checked
    return "ok" if same_page(url, result["final_url"]) else "redirected"


def check_url(url: str, cites: list[dict], timeout: float, now: str) -> dict:
    """Snapshot row for one URL: page state, text hash and the state of every quote that cites it."""
    result = fetch(url, timeout)
    state = page_state(result, url)
    text = page_text(result["body"]) if result["body"] is not None else None
    quotes = [{"relation": c["relation"], "state": quote_state(c["quote"], text)} for c in cites]
    return {"url": url, "state": state, "http": result["http"], "final_url": result["final_url"],
            "error": result["error"], "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
            "checked_at": now, "quotes": quotes}


def select_urls(urls: list[str], host: str | None, sample: int | None, seed: int) -> list[str]:
    """Apply the --host filter and the reproducible --sample to a sorted URL list."""
    if host:
        urls = [u for u in urls if host.lower() in urllib.parse.urlsplit(u).netloc.lower()]
    if sample and sample < len(urls):
        urls = sorted(random.Random(seed).sample(urls, sample))
    return urls


def run(by_url: dict[str, list[dict]], urls: list[str], delay: float, timeout: float) -> list[dict]:
    """Check the URLs in order, waiting `delay` seconds between two requests to the same host."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    last_hit: dict[str, float] = {}
    rows = []
    for index, url in enumerate(urls, 1):
        host = urllib.parse.urlsplit(url).netloc.lower()
        wait = delay - (time.monotonic() - last_hit.get(host, -delay))
        if wait > 0:
            time.sleep(wait)
        rows.append(check_url(url, by_url[url], timeout, now))
        last_hit[host] = time.monotonic()
        if index % 25 == 0 or index == len(urls):
            print(f"  {index}/{len(urls)}", flush=True)
    return rows


def load_snapshot(path: Path) -> dict[str, dict]:
    """Previous snapshot keyed by URL; empty when there is none."""
    if not path.exists():
        return {}
    return {row["url"]: row for row in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if row}


def merge_snapshot(previous: dict[str, dict], rows: list[dict]) -> list[dict]:
    """Latest row per URL: this run's rows replace older ones, URLs not checked this run are kept."""
    merged = dict(previous)
    merged.update({row["url"]: row for row in rows})
    return [merged[url] for url in sorted(merged)]


def changes(previous: dict[str, dict], rows: list[dict]) -> list[str]:
    """Human-readable differences between this run and the previous snapshot."""
    out = []
    for row in rows:
        old = previous.get(row["url"])
        if not old:
            continue
        if old["state"] != row["state"]:
            out.append(f"頁面狀態 {old['state']} → {row['state']}：{row['url']}")
        elif old.get("text_sha256") and row.get("text_sha256") and old["text_sha256"] != row["text_sha256"]:
            out.append(f"頁面文字有變動：{row['url']}")
        old_quotes = {q["relation"]: q["state"] for q in old.get("quotes", [])}
        for quote in row["quotes"]:
            before = old_quotes.get(quote["relation"])
            if before == "found" and quote["state"] in ("partial", "missing"):
                out.append(f"引句由 found 變為 {quote['state']}：{quote['relation']}（{row['url']}）")
    return out


def attention(rows: list[dict]) -> list[str]:
    """Rows a person should look at: pages that are gone or unreachable, and quotes no longer on the page."""
    out = []
    for row in rows:
        if row["state"] in ("gone", "unreachable"):
            out.append(f"{row['state']}（{row['error']}）：{row['url']}，影響 {len(row['quotes'])} 條關係")
        for quote in row["quotes"]:
            if quote["state"] == "missing" and row["state"] in ("ok", "redirected"):
                out.append(f"引句未在頁面文字中找到：{quote['relation']}（{row['url']}）")
    return out


def tally(rows: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    """Counts of page states and of quote states across the rows."""
    pages: dict[str, int] = {}
    quotes: dict[str, int] = {}
    for row in rows:
        pages[row["state"]] = pages.get(row["state"], 0) + 1
        for quote in row["quotes"]:
            quotes[quote["state"]] = quotes.get(quote["state"], 0) + 1
    return pages, quotes


def render_report(rows: list[dict], total_urls: int, diff: list[str], first_run: bool) -> str:
    """Markdown report for one run."""
    pages, quotes = tally(rows)
    need = attention(rows)
    lines = ["# 來源監測報告", "",
             f"檢查時間（UTC）：{rows[0]['checked_at'] if rows else '無'}",
             f"本次檢查 {len(rows)} 個網址（正式關係引用的網址共 {total_urls} 個）", "",
             "## 頁面狀態", ""]
    lines += [f"- {state}：{count}" for state, count in sorted(pages.items())]
    lines += ["", "## 引句狀態", ""]
    lines += [f"- {state}：{count}" for state, count in sorted(quotes.items())]
    lines += ["", "狀態說明：blocked 為網站拒絕自動請求，not_text 為 PDF 等非文字檔，tls_error 為本機憑證驗證失敗，"
              "三者的引句列為 unchecked；partial 為引句多數片段仍在頁面上。", "",
              "限制：只讀取伺服器回傳的原始 HTML，不執行頁面上的程式；由程式動態載入的內容會被判為 missing，需人工開頁確認。", "",
              f"## 需要人工確認（{len(need)} 項）", ""]
    lines += [f"- {item}" for item in need] or ["- 無"]
    lines += ["", "## 與上次快照的差異", ""]
    lines += ["- 首次執行，沒有可比較的快照"] if first_run else ([f"- {item}" for item in diff] or ["- 無變動"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-check the verification URLs and quotes of the formal graph.")
    parser.add_argument("--sample", type=int, help="check a random sample of this many URLs")
    parser.add_argument("--seed", type=int, default=0, help="seed for --sample")
    parser.add_argument("--host", help="only URLs whose host contains this text")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests to the same host")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    by_url = cited_urls(data_io.load_relation_dicts(ROOT))
    urls = select_urls(sorted(by_url), args.host, args.sample, args.seed)
    print(f"正式關係引用 {len(by_url)} 個網址，本次檢查 {len(urls)} 個")
    snapshot_path = ROOT / STATUS_JSONL
    previous = load_snapshot(snapshot_path)
    rows = run(by_url, urls, args.delay, args.timeout)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    data_io.write_text_lf(snapshot_path, "".join(json.dumps(row, ensure_ascii=False) + "\n"
                                                  for row in merge_snapshot(previous, rows)))
    data_io.write_text_lf(ROOT / REPORT_MD, render_report(rows, len(by_url), changes(previous, rows), not previous))
    pages, quotes = tally(rows)
    print("頁面：", pages)
    print("引句：", quotes)
    print(f"需要人工確認 {len(attention(rows))} 項；報告：{REPORT_MD}")


if __name__ == "__main__":
    main()
