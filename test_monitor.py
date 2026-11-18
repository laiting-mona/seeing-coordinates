"""Regression tests for tools/source_monitor.py. No internet: pages are served from a local HTTP server.

Last edited: 2026-11-17: tests for percent-encoding non-ASCII URLs, elided quotes, bracket edits, gzip bodies and bot-check pages. 2026-11-16: first version.
Usage: python test_monitor.py
"""
import http.server
import sys
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import source_monitor as monitor  # noqa: E402

passed = 0
QUOTE = "that which withers in the age of mechanical reproduction is the aura of the work of art"
PAGES = {
    "/found": "<html><body><p>Benjamin wrote: &ldquo;that which withers in the age of <em>mechanical "
              "reproduction</em>\n is the aura of the work of art&rdquo;.</p></body></html>",
    "/partial": "<html><body><p>that which withers in the age of mechanical reproduction is, he says, "
                "the aura of the work of art</p></body></html>",
    "/missing": "<html><body><script>var x = 'the aura of the work of art';</script><p>About the museum.</p></body></html>",
    "/zh": "<html><body><p>攝影小史首次提出攝影中的靈光，早於〈機械複製時代的藝術作品〉。</p></body></html>",
}


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves PAGES, a redirect, a PDF and two error codes."""

    def do_GET(self) -> None:
        if self.path in PAGES:
            self.reply(200, "text/html; charset=utf-8", PAGES[self.path].encode("utf-8"))
        elif self.path == "/moved":
            self.send_response(301)
            self.send_header("Location", "/found")
            self.end_headers()
        elif self.path == "/paper.pdf":
            self.reply(200, "application/pdf", b"%PDF-1.4")
        elif self.path == "/forbidden":
            self.reply(403, "text/plain", b"no robots")
        else:
            self.reply(404, "text/plain", b"not found")

    def reply(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def check(name: str, condition: bool) -> None:
    global passed
    assert condition, "FAIL: " + name
    passed += 1
    print("  ✓", name)


def start_server() -> tuple[http.server.ThreadingHTTPServer, str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_text_matching() -> None:
    text = monitor.page_text(PAGES["/found"])
    check("引句跨標籤、換行與彎引號仍判為 found", monitor.quote_state(QUOTE, text) == "found")
    check("引句被插入字詞時判為 partial", monitor.quote_state(QUOTE, monitor.page_text(PAGES["/partial"])) == "partial")
    check("script 內的文字不算頁面內容，判為 missing", monitor.quote_state(QUOTE, monitor.page_text(PAGES["/missing"])) == "missing")
    check("中文引句可比對", monitor.quote_state("攝影小史首次提出攝影中的靈光", monitor.page_text(PAGES["/zh"])) == "found")
    linked = monitor.page_text("<p>如同中國攝影學者 <a href='#'>顧錚</a> 的評價：張曉始終保持著對於現實的溫情觀察。</p>")
    check("中文引句跨過連結標籤留下的空格仍判為 found", monitor.quote_state("如同中國攝影學者顧錚的評價：張曉始終保持著對於現實的溫情觀察。", linked) == "found")
    korean = monitor.page_text('<p>출범한 " 한국사진작가협회 "는 창립전을 가지며</p>')
    check("韓文引句跨過引號旁的空格仍判為 found", monitor.quote_state('출범한 "한국사진작가협회"는 창립전을 가지며', korean) == "found")
    sjis = '<html><head><meta http-equiv="Content-Type" content="text/html; charset=Shift_JIS"></head><body>木村と土門</body></html>'.encode("cp932")
    check("沒有標頭編碼時讀取 meta 宣告的 Shift_JIS", monitor.sniff_charset(sjis) == "cp932" and "木村と土門" in sjis.decode(monitor.sniff_charset(sjis)))
    contributors = monitor.page_text("<p>Contributors: Liz Heron, Alice Hughes, Karen Knorr, Rosalind Krauss, Dorothea Lange</p>")
    check("以 ... 串接的引句，每段都在頁面上就算 found",
          monitor.quote_state("Contributors: ... Alice Hughes, Karen Knorr, Rosalind Krauss", contributors) == "found")
    check("以 ... 串接但有一段不在頁面上，不算 found",
          monitor.quote_state("Contributors: ... Alice Hughes, Karen Knorr, Rosalind Krauss ... Susan Sontag wrote it", contributors) != "found")
    series = monitor.page_text("<p>Other series include Mexas [1996-97], and the ongoing Organized Freedom [from 1999].</p>")
    check("方括號是引用者的補註，比對時略過", monitor.quote_state("Other series include ... the ongoing Organized Freedom [from 1999]", series) == "found")
    import gzip
    check("gzip 內容先解壓再讀", monitor.decompress(gzip.compress("相片".encode()), "gzip").decode() == "相片")
    challenge = {"http": 200, "body": "<p>Please confirm you are a real human.</p>", "final_url": "u", "error": None}
    check("回傳 200 的機器人驗證頁記為 blocked", monitor.page_state(challenge, "u") == "blocked")
    check("沒有引句或沒有頁面文字時為 unchecked",
          monitor.quote_state(None, text) == "unchecked" and monitor.quote_state(QUOTE, None) == "unchecked")


def test_page_states(base: str) -> None:
    def state(path: str) -> dict:
        return monitor.check_url(base + path, [{"relation": "a|b|discusses", "quote": QUOTE}], 5, "t")
    check("正常頁面為 ok 且引句 found", (state("/found")["state"], state("/found")["quotes"][0]["state"]) == ("ok", "found"))
    moved = state("/moved")
    check("轉址記為 redirected 並保留最終網址", moved["state"] == "redirected" and moved["final_url"].endswith("/found"))
    check("404 記為 gone", state("/nope")["state"] == "gone")
    check("403 記為 blocked，引句不判定", (state("/forbidden")["state"], state("/forbidden")["quotes"][0]["state"]) == ("blocked", "unchecked"))
    check("PDF 記為 not_text，引句不判定", (state("/paper.pdf")["state"], state("/paper.pdf")["quotes"][0]["state"]) == ("not_text", "unchecked"))
    check("連不上的主機記為 unreachable", monitor.check_url("http://127.0.0.1:9/x", [], 2, "t")["state"] == "unreachable")
    check("只差 www 與結尾斜線視為同一頁", monitor.same_page("http://www.a.org/p/", "https://a.org/p"))
    encoded = monitor.request_url("https://topmuseum.jp/upload/2/前衛写真.pdf?q=中平")
    check("非 ASCII 網址先編碼再送出，已編碼的部分不重複編碼", encoded.isascii() and "%E5%89%8D" in encoded
          and monitor.request_url(encoded) == encoded)
    tls = {"http": None, "body": None, "final_url": "u", "error": "URLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"}
    check("憑證驗證失敗另記為 tls_error", monitor.page_state(tls, "u") == "tls_error")


def test_snapshot_diff(base: str) -> None:
    cite = [{"relation": "a|b|discusses", "quote": QUOTE}]
    before = {base + "/x": {"url": base + "/x", "state": "ok", "text_sha256": "old",
                            "quotes": [{"relation": "a|b|discusses", "state": "found"}]}}
    row = monitor.check_url(base + "/missing", cite, 5, "t")
    row["url"] = base + "/x"
    diff = monitor.changes(before, [row])
    check("頁面文字變動與引句消失都列入差異", any("頁面文字有變動" in d for d in diff) and any("引句由 found 變為 missing" in d for d in diff))
    check("引句消失列入需要人工確認", any("引句未在頁面文字中找到" in a for a in monitor.attention([row])))
    merged = monitor.merge_snapshot({"u1": {"url": "u1", "state": "ok"}}, [{"url": "u2", "state": "gone"}])
    check("快照合併保留本次未檢查的網址", [r["url"] for r in merged] == ["u1", "u2"])


def test_selection_and_real_data() -> None:
    urls = [f"https://h{i % 3}.org/{i}" for i in range(30)]
    check("抽樣可重現", monitor.select_urls(urls, None, 5, 7) == monitor.select_urls(urls, None, 5, 7))
    check("host 篩選", all("h1.org" in u for u in monitor.select_urls(urls, "h1.org", None, 0)))
    by_url = monitor.cited_urls(monitor.data_io.load_relation_dicts(monitor.ROOT))
    check("正式圖譜的網址都能取出，且每個網址至少對應一條關係", len(by_url) > 500 and all(by_url.values()))


def main() -> None:
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))   # local server: bypass any system proxy
    server, base = start_server()
    try:
        test_text_matching()
        test_page_states(base)
        test_snapshot_diff(base)
        test_selection_and_real_data()
    finally:
        server.shutdown()
    print(f"\n全部通過:{passed} 項 ✓")


if __name__ == "__main__":
    main()
