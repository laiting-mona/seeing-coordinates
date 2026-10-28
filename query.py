"""Query layer: natural-language question → graph lookup → structured result → text.

Last edited: 2026-10-27 — wrapped state in QueryEngine; resolve() now does an exact
substring pass first (incl. unambiguous person surnames) and falls back to
difflib.get_close_matches at cutoff 0.8 (≈4× faster than the old per-window loop); fixed status label so `approved` edges are
shown as in-graph rather than 待判斷; renderers split per result type.

Pure program (string matching + difflib + networkx), no LLM call. Each handler returns
a dict with a 'type' field (machine-readable skeleton); render() formats it as text.
Usage:
  python query.py "問句"            formatted text
  python query.py --json "問句"     structured dict
  python query.py --test            stability scan over data/test_prompts.json
"""
import difflib
import json
import sys
from pathlib import Path

import networkx as nx

import recommend
from authority import TIER_BASE
from schema import KIND_VERB_ZH

ROOT = Path(__file__).resolve().parent
FUZZY_CUTOFF = 0.8          # 0.75 let 的攝影 match 遲到的攝影; 0.8 keeps genuine typos (桑塔各)
MIN_FORM_LEN, MIN_WINDOW_LEN, MAX_WINDOW_LEN = 2, 4, 14
MIN_SURNAME_LEN = 4

# Surface forms that users type which differ from stored names.
ALIASES = {
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
}

# Keyword → intent, checked in this order (first hit wins).
INTENT_KEYWORDS = [
    ("provenance", ["出處", "根據", "來源", "可信", "真的假的", "查核", "文獻", "腦補", "求證", "依據", "哪來", "憑"]),
    ("authority", ["權威", "平台", "podcast", "網站", "算數", "夠格", "在紅", "有料", "評論來源"]),
    ("path", ["路線", "順序", "三週", "三禮拜", "清單", "讀書計畫", "備課", "循序"]),
    ("recommend", ["推薦", "下一本", "接下來", "讀什麼", "讀啥", "下一步", "該讀", "然後呢", "救救"]),
    ("lineage", ["演變", "之後", "接手", "後來", "怎麼變", "反駁", "繼續講", "發展", "怎麼來", "消逝之後"]),
    ("relation", ["關係", "關聯", "批判", "對話", "差在哪", "差別", "vs", "比起來", "兜", "理一下", "反什麼", "有關", "分不清"]),
]

STARTER_PATH = [  # static three-week starter plan returned by the "path" intent
    ["第1週", "伯格《觀看的方式》", "建立『觀看受意識形態形塑』的問題意識"],
    ["第2週", "桑塔格《論攝影》", "採集與觀看倫理"],
    ["第3週", "巴特《明室》", "刺點/此曾在的現象學;行有餘力接蕭爾《照片的本質》"],
]


def normalize(text: str) -> str:
    """Lower-case and strip spaces so surface forms compare consistently."""
    return text.lower().replace(" ", "")


def is_in_graph(status: str) -> bool:
    """auto and approved relations are in the formal graph; review is pending."""
    return status in ("auto", "approved")


class QueryEngine:
    """Holds the graph plus name indexes and answers questions against it."""

    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
        self.name_zh = {n: graph.nodes[n].get("name_zh", n) for n in graph.nodes}
        self.label = {n: graph.nodes[n].get("label") or self.name_zh[n] for n in graph.nodes}
        self.form_to_id = self._build_form_index()
        self.forms = list(self.form_to_id)

    # ---------- indexing & resolution ----------
    def _build_form_index(self) -> dict[str, str]:
        """Map every normalized surface form to a node id.

        Forms: Chinese name, English name, aliases, and — for persons — the English surname
        when it is unambiguous (users type "sontag", not "Susan Sontag"; "adams" is skipped
        because Ansel and Robert both carry it).
        """
        index = {}
        surname_owners: dict[str, set[str]] = {}
        for node_id, attrs in self.graph.nodes(data=True):
            for form in (attrs.get("name_zh"), attrs.get("name_en")):
                if form and len(normalize(form)) >= MIN_FORM_LEN:
                    index.setdefault(normalize(form), node_id)
            if attrs.get("type") == "person" and attrs.get("name_en"):
                surname = normalize(attrs["name_en"].split()[-1])
                if len(surname) >= MIN_SURNAME_LEN:
                    surname_owners.setdefault(surname, set()).add(node_id)
        for surname, owners in surname_owners.items():
            if len(owners) == 1:
                index.setdefault(surname, next(iter(owners)))
        for alias, node_id in ALIASES.items():
            index[normalize(alias)] = node_id
        return index

    def display(self, node_id: str) -> str:
        """Reader-facing label (EN-first for Western entities, ZH for Chinese-world)."""
        return self.label.get(node_id, node_id)

    def resolve(self, question: str) -> list[str]:
        """Return node ids mentioned in the question, best match first.

        Pass 1: exact substring hits (score 1.0). Pass 2 (only if pass 1 is empty):
        fuzzy match of question substrings against known forms via get_close_matches.
        """
        q = normalize(question)
        exact = {form: node_id for form, node_id in self.form_to_id.items() if form in q}
        # drop a short form that is merely part of a longer matched form (e.g. 塔格 inside 桑塔格)
        exact = {f: n for f, n in exact.items() if not any(f != g and f in g for g in exact)}
        scores: dict[str, float] = {}
        for form, node_id in exact.items():
            scores[node_id] = max(scores.get(node_id, 0), 1.0 if len(form) > 2 else 0.9)
        if not scores:
            windows = {q[i:i + L] for L in range(MIN_WINDOW_LEN, min(MAX_WINDOW_LEN, len(q)) + 1) for i in range(len(q) - L + 1)}
            for window in windows:
                for form in difflib.get_close_matches(window, self.forms, n=2, cutoff=FUZZY_CUTOFF):
                    ratio = round(difflib.SequenceMatcher(None, form, window).ratio(), 2)
                    node_id = self.form_to_id[form]
                    scores[node_id] = max(scores.get(node_id, 0), ratio)
        return [node_id for node_id, _ in sorted(scores.items(), key=lambda kv: -kv[1])]

    @staticmethod
    def classify(question: str) -> str:
        """Map the question to an intent by keyword; 'default' when nothing matches."""
        for intent, keywords in INTENT_KEYWORDS:
            if any(k in question for k in keywords):
                return intent
        return "default"

    # ---------- graph helpers ----------
    def edges_between(self, source: str, target: str) -> list[dict]:
        """All edge-data dicts for source → target (any kind)."""
        return [d for _, t, d in self.graph.out_edges(source, data=True) if t == target]

    def edge_record(self, source: str, target: str, data: dict) -> dict:
        """Flatten one edge into the fields handlers expose."""
        return {"from": self.display(source), "to": self.display(target), "kind": data.get("kind"),
                "claim": data.get("claim"), "evidence": data.get("evidence") or "",
                "source": data.get("source_ref"), "tier": data.get("source_tier"),
                "confidence": data.get("confidence"), "status": data.get("status")}

    def both_directions(self, a: str, b: str) -> list[dict]:
        return ([self.edge_record(a, b, d) for d in self.edges_between(a, b)]
                + [self.edge_record(b, a, d) for d in self.edges_between(b, a)])

    # ---------- intent handlers (return structured dicts) ----------
    def handle_recommend(self, ids: list[str]) -> dict:
        if not ids:
            return {"type": "recommend", "resolved": False}
        items = recommend.recommend(self.graph, ids, top_n=3)
        return {"type": "recommend", "resolved": True, "seed": self.display(ids[0]),
                "items": [{"target": i["target"], "reason": i["reason"], "source": i["source"]} for i in items]}

    def handle_provenance(self, ids: list[str]) -> dict:
        if len(ids) < 2:
            return {"type": "provenance", "resolved": False, "nodes": [self.display(i) for i in ids]}
        edges = self.both_directions(ids[0], ids[1])
        if not edges:
            return {"type": "provenance", "resolved": True, "found": False,
                    "a": self.display(ids[0]), "b": self.display(ids[1])}
        return {"type": "provenance", "resolved": True, "found": True, "edges": edges}

    def handle_lineage(self, ids: list[str]) -> dict:
        if not ids:
            return {"type": "lineage", "resolved": False}
        concept = ids[0]
        predecessors = list(self.graph.predecessors(concept))
        origin = [self.edge_record(u, concept, d) for u in predecessors[:3] for d in self.edges_between(u, concept)]
        followups = [self.edge_record(a, u, d) for u in predecessors[:1]
                     for a in list(self.graph.predecessors(u))[:4] for d in self.edges_between(a, u)]
        return {"type": "lineage", "resolved": True, "concept": self.display(concept),
                "origin": origin, "followups": followups}

    def handle_relation(self, ids: list[str]) -> dict:
        if len(ids) < 2:
            return self.handle_default(ids)
        a, b = ids[0], ids[1]
        edges = self.both_directions(a, b)
        if edges:
            return {"type": "relation", "direct": True, "edges": edges}
        try:
            path = nx.shortest_path(self.graph.to_undirected(as_view=True), a, b)
            return {"type": "relation", "direct": False, "path": [self.display(x) for x in path]}
        except nx.NetworkXException:
            return {"type": "relation", "direct": False, "path": [], "a": self.display(a), "b": self.display(b)}

    def handle_authority(self, _ids: list[str]) -> dict:
        popular = [self.edge_record(u, v, d) for u, v, d in self.graph.edges(data=True)
                   if d.get("source_tier") == "popular"]
        return {"type": "authority", "tiers": sorted(TIER_BASE.items(), key=lambda kv: -kv[1]),
                "popular_examples": popular}

    @staticmethod
    def handle_path(_ids: list[str]) -> dict:
        return {"type": "path", "weeks": STARTER_PATH}

    def handle_default(self, ids: list[str]) -> dict:
        if not ids:
            return {"type": "unresolved"}
        node = ids[0]
        return {"type": "default", "node": self.display(node),
                "out": [self.edge_record(u, v, d) for u, v, d in list(self.graph.out_edges(node, data=True))[:6]],
                "in": [self.edge_record(u, v, d) for u, v, d in list(self.graph.in_edges(node, data=True))[:4]]}

    def answer(self, question: str) -> tuple[str, list[str], dict]:
        """Resolve nodes, classify intent, run the handler. Returns (intent, ids, result)."""
        ids = self.resolve(question)
        intent = self.classify(question)
        handler = {"recommend": self.handle_recommend, "provenance": self.handle_provenance,
                   "lineage": self.handle_lineage, "relation": self.handle_relation,
                   "authority": self.handle_authority, "path": self.handle_path,
                   "default": self.handle_default}[intent]
        return intent, ids, handler(ids)


# ---------- renderers: structured dict → text ----------
def edge_line(edge: dict) -> str:
    tag = "入圖" if is_in_graph(edge["status"]) else "待判斷"
    return (f"{edge['from']} {KIND_VERB_ZH.get(edge['kind'], edge['kind'])} {edge['to']}"
            f"(可信度 {edge['confidence']}、{edge['tier']}層、出處 {edge['source']}、{tag})")


def render_recommend(r: dict) -> str:
    if not r.get("resolved"):
        return "沒抓到你讀過的作者或書,換個講法?"
    if not r["items"]:
        return f"以「{r['seed']}」為起點,鄰居都讀過了,可能要擴充來源。"
    return (f"📚 你讀過「{r['seed']}」,沿知識前緣建議下一步:\n"
            + "\n".join(f"  • {i['target']} — {i['reason']}（出處:{i['source']}）" for i in r["items"]))


def render_provenance(r: dict) -> str:
    if not r.get("resolved"):
        return "說清楚你要查哪兩者的關係,我把出處調出來。"
    if not r["found"]:
        return f"🔎 圖上目前沒有「{r['a']}」和「{r['b']}」的關係,所以我不會編一個給你。"
    blocks = []
    for e in r["edges"]:
        tag = "已入圖(查證或可信度達標)" if is_in_graph(e["status"]) else "⚠ 待人工判斷(尚未確認,不可當定論)"
        blocks.append(f"🔎 查核:{e['from']} {KIND_VERB_ZH.get(e['kind'], e['kind'])} {e['to']}\n  主張:{e['claim']}\n"
                      f"  證據:{e['evidence'] or '(無)'}\n  出處:{e['source']}　來源層:{e['tier']}"
                      f"　可信度:{e['confidence']}\n  狀態:{tag}")
    return "\n".join(blocks)


def render_lineage(r: dict) -> str:
    if not r.get("resolved"):
        return "沒抓到要追的概念,換個講法?"
    lines = [f"🧬「{r['concept']}」的脈絡:"]
    lines += [f"  源頭:{edge_line(e)}" for e in r["origin"]]
    lines += [f"  後續:{edge_line(e)}" for e in r["followups"]]
    if len(lines) == 1:
        lines.append("  圖上還沒有指向它的關係。")
    return "\n".join(lines)


def render_relation(r: dict) -> str:
    if r["direct"]:
        return "🔗 有直接關係:\n" + "\n".join("  " + edge_line(e) for e in r["edges"])
    if r.get("path"):
        return "🔗 沒有直接關係,但有間接連結:" + " → ".join(r["path"])
    return f"🔗「{r['a']}」和「{r['b']}」目前在圖上還沒連起來。"


def render_authority(r: dict) -> str:
    lines = ["🏛 權威分層與權重(越上面越權威):"]
    lines += [f"  {tier}:{weight}" for tier, weight in r["tiers"]]
    lines.append("大眾/推廣型(podcast、評論平台)歸 popular、權重最低,看『現在在討論什麼』用,不當建立正典的依據。")
    lines += [f"  • {e['source']}:{e['from']} {e['kind']} {e['to']}(待查證)" for e in r["popular_examples"]]
    return "\n".join(lines)


def render_path(r: dict) -> str:
    return ("🗓 三週入門路線(從『觀看的政治』進,循主線遞進):\n"
            + "\n".join(f"  {w[0]}:{w[1]} —— {w[2]}" for w in r["weeks"]))


def render_default(r: dict) -> str:
    lines = [f"ℹ 關於「{r['node']}」,圖上的關係:"]
    lines += [f"  → {edge_line(e)}" for e in r["out"]]
    lines += [f"  ← {edge_line(e)}" for e in r["in"]]
    return "\n".join(lines)


RENDERERS = {"recommend": render_recommend, "provenance": render_provenance, "lineage": render_lineage,
             "relation": render_relation, "authority": render_authority, "path": render_path,
             "default": render_default}


def render(result: dict) -> str:
    """Format a handler result as text; unknown types get a polite fallback."""
    renderer = RENDERERS.get(result.get("type"))
    return renderer(result) if renderer else "我沒抓到你問的是哪個人、概念或作品,可以講得具體一點。"


# ---------- module-level engine (loaded once) and compatibility wrappers ----------
ENGINE = QueryEngine(recommend.load_graph())


def answer(question: str) -> tuple[str, list[str], dict]:
    return ENGINE.answer(question)


def run_stability_test(root: Path = ROOT) -> None:
    """Check that paraphrases of the same question resolve to the same intent and the same (unordered) nodes."""
    prompts = json.loads((root / "data/test_prompts.json").read_text(encoding="utf-8"))
    print("穩定性掃描:同一題的多個變體應導到相同意圖與節點\n" + "─" * 60)
    for item in prompts:
        print(f"\n【{item['id']}】{item['persona']}")
        outcomes = set()
        for variant in item["variants"]:
            intent, ids, _ = answer(variant)
            outcomes.add((intent, frozenset(ids[:2])))  # order of the two resolved nodes is not a difference
            shown = ",".join(ENGINE.display(i) for i in ids[:2]) or "(未解析)"
            print(f"  [{intent:<10}] {shown:<14} ｜ {variant[:24]}")
        print(f"  → 一致性:{'✓ 全一致' if len(outcomes) == 1 else f'✗ {len(outcomes)} 種結果'}")


def main() -> None:
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--test" in sys.argv:
        run_stability_test()
    elif positional:
        intent, ids, result = answer(" ".join(positional))
        if "--json" in sys.argv:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            shown = ",".join(ENGINE.display(i) for i in ids[:3]) or "無"
            print(f"[意圖:{intent}　解析:{shown}]\n{render(result)}")
    else:
        print('用法:python query.py "問句"  /  --json "問句"  /  --test')


if __name__ == "__main__":
    main()
