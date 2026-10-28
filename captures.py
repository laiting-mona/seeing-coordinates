"""Raw capture log (fetched evidence), kept apart from the curated graph.

Last edited: 2026-10-27 — English docstrings; shared read helper; no behaviour change.

Stored as plain JSONL (git-diffable); a content hash de-duplicates entries.
load_sqlite() loads the log into an in-memory SQLite database for ad-hoc queries,
so no binary database file is ever written.
Usage: python captures.py   (prints the latest captures)
"""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "data" / "captures.jsonl"


def read_captures(path: Path = LOG_PATH) -> list[dict]:
    """All capture records, oldest first; empty when the log does not exist."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def capture_hash(url: str, snippet: str) -> str:
    """16-hex-char content hash identifying (url, snippet)."""
    return hashlib.sha256(f"{url}||{snippet}".encode("utf-8")).hexdigest()[:16]


def append_capture(url: str, snippet: str, supports: str = "", note: str = "",
                   path: Path = LOG_PATH) -> tuple[str, bool]:
    """Append one capture unless the same url+snippet exists. Returns (hash, was_added)."""
    digest = capture_hash(url, snippet)
    if any(record["hash"] == digest for record in read_captures(path)):
        return digest, False
    record = {"hash": digest, "url": url,
              "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "snippet": snippet, "supports": supports, "note": note}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return digest, True


def load_sqlite(path: Path = LOG_PATH) -> sqlite3.Connection:
    """Load the capture log into an in-memory SQLite connection with table `captures`."""
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE captures(hash TEXT PRIMARY KEY, url TEXT, "
                       "retrieved_at TEXT, snippet TEXT, supports TEXT, note TEXT)")
    connection.executemany(
        "INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?,?)",
        [(r["hash"], r["url"], r["retrieved_at"], r["snippet"], r.get("supports", ""), r.get("note", ""))
         for r in read_captures(path)])
    connection.commit()
    return connection


def main() -> None:
    connection = load_sqlite()
    count = connection.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
    print(f"captures: {count} 筆")
    for row in connection.execute("SELECT retrieved_at, supports, url FROM captures ORDER BY retrieved_at DESC LIMIT 10"):
        print(" ", row)


if __name__ == "__main__":
    main()
