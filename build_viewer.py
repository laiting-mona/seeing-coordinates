"""Render build/graph.json into a single-file interactive viewer (build/viewer.html).

Last edited: 2026-10-28 — fixed black/white theme; removed hint text; UX pass: search box,
type filter chips, neighbour focus on click, clickable verification links, layout frozen after
stabilisation. 2026-10-27: functions + main(); kind labels from schema.KIND_VERB_ZH.

Uses vis-network from cdnjs; data is embedded so the file is portable and can be
published as an artifact. Edges with status `review` are dashed and labelled 待判斷.
Theme is intentionally fixed (black background, white text) by the project owner's request.
Usage: python build_viewer.py
"""
import json
from pathlib import Path

import data_io
from schema import KIND_VERB_ZH

ROOT = Path(__file__).resolve().parent
OUTPUT_HTML = ROOT / "build/viewer.html"

TEMPLATE = r"""<title>觀看的座標 譜系地圖</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap">
<style>
  /* Fixed dark theme (user request: black background, white text) */
  :root{
    --bg:#000000; --surface:#111111; --surface-2:#1a1a1a; --fg:#ffffff; --muted:#9b9b9b; --line:#2a2a2a;
    --accent:#7fd1c8;
    --person:#7fd1c8; --work:#8ab8ea; --concept:#e6a95e; --event:#b89ee6; --institution:#8fd39a;
    --auto:#8fd39a; --review:#e6a95e;
    --font:"Noto Sans TC",system-ui,-apple-system,sans-serif;
    color-scheme:dark;
  }
  html,body{height:100%;margin:0;background:var(--bg);color:var(--fg)}
  *{box-sizing:border-box}
  button,input{font:inherit;color:inherit}
  #app{height:100%;display:flex;flex-direction:column;background:var(--bg);color:var(--fg);
    font-family:var(--font);font-size:14px}
  header{flex:0 0 auto;background:var(--surface);border-bottom:1px solid var(--line);
    padding:10px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px}
  header h1{margin:0;font-size:16px;font-weight:700;white-space:nowrap}
  .stats{font-size:12px;color:var(--muted);white-space:nowrap}
  .search{position:relative;flex:1 1 220px;max-width:360px}
  .search input{width:100%;padding:7px 12px;border-radius:8px;border:1px solid var(--line);
    background:var(--surface-2);outline:none}
  .search input:focus{border-color:var(--accent)}
  .hits{position:absolute;left:0;right:0;top:calc(100% + 4px);background:var(--surface-2);border:1px solid var(--line);
    border-radius:8px;overflow:hidden;z-index:5;display:none;max-height:50vh;overflow-y:auto}
  .hits.open{display:block}
  .hit{padding:8px 12px;cursor:pointer;display:flex;align-items:center;gap:8px}
  .hit:hover,.hit.active{background:#262626}
  .hit .dot{flex:0 0 auto}
  .hit small{color:var(--muted)}
  .legend{display:flex;flex-wrap:wrap;gap:6px;margin-left:auto}
  .chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:4px 10px;border-radius:99px;
    border:1px solid var(--line);background:var(--surface-2);cursor:pointer;user-select:none}
  .chip[aria-pressed="false"]{opacity:.38}
  .chip.static{cursor:default}
  .dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;display:inline-block}
  .btn{padding:5px 10px;border-radius:8px;border:1px solid var(--line);background:var(--surface-2);cursor:pointer;font-size:12px}
  .btn:hover{border-color:var(--accent)}
  #main{flex:1;display:flex;min-height:0;position:relative}
  #net{flex:1;min-width:0;min-height:0}
  #progress{position:absolute;left:0;top:0;height:2px;background:var(--accent);width:0;transition:width .2s;pointer-events:none}
  #panel{flex:0 0 360px;max-width:44vw;background:var(--surface);border-left:1px solid var(--line);
    overflow-y:auto;padding:14px 16px 20px;display:none}
  #panel.open{display:block}
  .phead{display:flex;align-items:flex-start;gap:8px;margin-bottom:10px}
  .phead h2{margin:0;font-size:18px;line-height:1.3;flex:1}
  .ptype{font-size:12px;color:var(--muted);margin:2px 0 12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  .section{font-size:12px;color:var(--muted);margin:14px 0 6px;letter-spacing:.02em}
  .rel{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:8px;background:var(--surface-2)}
  .rel .top{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:4px}
  .rel .arrow{font-weight:600;cursor:pointer;line-height:1.4}
  .rel .arrow:hover{color:var(--accent);text-decoration:underline}
  .rel .verb{color:var(--muted);font-weight:400}
  .badge{font-size:11px;font-weight:600;border-radius:99px;padding:2px 8px;white-space:nowrap}
  .b-auto{background:rgba(143,211,154,.18);color:var(--auto)}
  .b-review{background:rgba(230,169,94,.18);color:var(--review)}
  .rel .claim{font-size:13px;line-height:1.55}
  .rel .meta{font-size:11.5px;color:var(--muted);margin-top:6px;display:flex;flex-wrap:wrap;gap:4px 10px}
  .rel .meta a{color:var(--accent);text-decoration:none}
  .rel .meta a:hover{text-decoration:underline}
  .tag{border:1px solid var(--line);border-radius:6px;padding:0 6px}
  .empty{color:var(--muted);font-size:13px}
  @media(max-width:640px){
    header h1{font-size:15px}
    .legend{margin-left:0}
    #main{flex-direction:column}
    #panel{flex:0 0 auto;max-width:none;max-height:50%;border-left:none;border-top:1px solid var(--line)}
  }
</style>
<div id="app">
  <header>
    <h1>觀看的座標 · 譜系地圖</h1>
    <span class="stats" id="stats"></span>
    <div class="search">
      <input id="q" type="search" placeholder="搜尋人物、著作、概念、機構…" autocomplete="off" aria-label="搜尋節點">
      <div class="hits" id="hits" role="listbox"></div>
    </div>
    <div class="legend" id="legend"></div>
    <button class="btn" id="fit" title="回到全圖">全圖</button>
  </header>
  <div id="main">
    <div id="progress"></div>
    <div id="net"></div>
    <aside id="panel"></aside>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/dist/vis-network.min.js"></script>
<script>
const DATA = /*__DATA__*/;
const KIND = /*__KIND__*/;
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const TYPES = {person:"人物", work:"著作", concept:"概念", event:"事件", institution:"機構"};
const colorOf = t => css("--" + t) || css("--concept");
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const byId = {}; DATA.nodes.forEach(n => byId[n.id] = n);
const neighbours = {}; DATA.nodes.forEach(n => neighbours[n.id] = new Set([n.id]));
DATA.edges.forEach(e => { neighbours[e.from]?.add(e.to); neighbours[e.to]?.add(e.from); });
const isolated = new Set(DATA.nodes.filter(n => neighbours[n.id].size === 1).map(n => n.id));  // no in-graph relation yet
let showIsolated = false;   // hidden by default: they only orbit the map and add no path
document.getElementById("stats").textContent = `${DATA.nodes.length} 節點 · ${DATA.edges.length} 關係`;
const FONT = {color:css("--fg"), size:14, face:"'Noto Sans TC', sans-serif", strokeWidth:3, strokeColor:css("--bg")};
const FONT_DIM = {...FONT, color:"rgba(255,255,255,0)", strokeWidth:0};   // focus mode: non-neighbours lose their label
const LABEL_SCALE = {overview:{min:10, max:22, drawThreshold:8}, focus:{min:16, max:28, drawThreshold:2}};
const hiddenTypes = new Set();
const isHidden = n => hiddenTypes.has(n.type) || (!showIsolated && isolated.has(n.id));

/* ---------- network ---------- */
const nodesDS = new vis.DataSet(DATA.nodes.map(n => ({
  id:n.id, label:n.label, shape:"dot", value: 4 + n.cent * 60, hidden: !showIsolated && isolated.has(n.id),
  color:{background:colorOf(n.type), border:colorOf(n.type), highlight:{background:"#ffffff", border:colorOf(n.type)}},
  font:FONT
})));
const edgesDS = new vis.DataSet(DATA.edges.map((e, i) => ({
  id:i, from:e.from, to:e.to, arrows:{to:{scaleFactor:.6}}, dashes: e.status === "review",
  title: `${(KIND[e.kind] || e.kind)}：${e.claim || ""}`,
  color:{color: e.status === "review" ? css("--review") : "#5a5a5a", highlight:css("--accent"), opacity:.7},
  width: e.status === "review" ? 1 : 1.4
})));
const net = new vis.Network(document.getElementById("net"), {nodes:nodesDS, edges:edgesDS}, {
  physics:{stabilization:{iterations:400, updateInterval:25},
           barnesHut:{gravitationalConstant:-6000, centralGravity:.9, springLength:130, avoidOverlap:.5}},
  interaction:{hover:true, tooltipDelay:150, hideEdgesOnDrag:true, hideEdgesOnZoom:true},
  nodes:{borderWidth:1.5, scaling:{min:6, max:34, label:{enabled:true, min:10, max:22, drawThreshold:8}}},
  edges:{smooth:{type:"continuous"}, selectionWidth:1.5}
});
const progress = document.getElementById("progress");
net.on("stabilizationProgress", p => progress.style.width = (100 * p.iterations / p.total) + "%");
net.once("stabilizationIterationsDone", () => {   // freeze layout: dragging moves one node, nothing jitters
  progress.style.width = "100%"; setTimeout(() => progress.style.width = "0", 400);
  net.setOptions({physics:false}); net.fit({animation:{duration:500}});
});
document.getElementById("fit").onclick = () => { clearSelection(); net.fit({animation:{duration:500}}); };

/* ---------- filters: type chips + isolated-node toggle ---------- */
function applyVisibility(){ nodesDS.update(DATA.nodes.map(n => ({id:n.id, hidden:isHidden(n)}))); }
function renderLegend(){
  document.getElementById("legend").innerHTML =
    Object.keys(TYPES).map(t => `<button class="chip" data-type="${t}" aria-pressed="${!hiddenTypes.has(t)}" title="顯示/隱藏${TYPES[t]}">
        <i class="dot" style="background:${colorOf(t)}"></i>${TYPES[t]}</button>`).join("")
    + `<button class="chip" id="iso" aria-pressed="${showIsolated}" title="尚無已入圖關係的節點">未連結 ${isolated.size}</button>`;
  document.querySelectorAll(".chip[data-type]").forEach(b => b.onclick = () => {
    const t = b.dataset.type; hiddenTypes.has(t) ? hiddenTypes.delete(t) : hiddenTypes.add(t);
    applyVisibility(); renderLegend();
  });
  document.getElementById("iso").onclick = () => { showIsolated = !showIsolated; applyVisibility(); renderLegend(); };
}
renderLegend();

/* ---------- focus on a node: dim everything that is not a neighbour ---------- */
let focused = null;
function applyFocus(id){
  focused = id;
  const keep = id ? neighbours[id] : null;
  net.setOptions({nodes:{scaling:{label:{enabled:true, ...LABEL_SCALE[id ? "focus" : "overview"]}}}});
  nodesDS.update(DATA.nodes.map(n => { const on = !keep || keep.has(n.id); return {id:n.id, opacity: on ? 1 : .12, font: on ? FONT : FONT_DIM}; }));
  edgesDS.update(DATA.edges.map((e, i) => ({id:i, color:{color: e.status === "review" ? css("--review") : "#5a5a5a",
    highlight:css("--accent"), opacity: !keep || (e.from === id || e.to === id) ? .7 : .05}})));
}
function clearSelection(){ net.unselectAll(); applyFocus(null); closePanel(); }

/* ---------- detail panel ---------- */
const panel = document.getElementById("panel");
const nameOf = id => byId[id] ? byId[id].full : id;
function closePanel(){ panel.classList.remove("open"); panel.innerHTML = ""; }
function evidenceHtml(ev){
  if(!ev) return "";
  return ev.split("｜").map(part => {
    const url = part.match(/https?:\/\/\S+/);
    if(url) return `<a href="${esc(url[0])}" target="_blank" rel="noopener">查證來源 ↗</a>`;
    if(/^［.*］$/.test(part.trim())) return `<span class="tag">${esc(part.trim().slice(1, -1))}</span>`;
    return `<span>${esc(part)}</span>`;
  }).join("");
}
function relCard(e, dir){
  const other = dir === "out" ? e.to : e.from;
  const verb = KIND[e.kind] || e.kind;
  const badge = e.status === "review" ? '<span class="badge b-review">待判斷</span>' : '<span class="badge b-auto">入圖</span>';
  const arrow = dir === "out" ? `<span class="verb">${esc(verb)}</span> → ${esc(nameOf(other))}` : `${esc(nameOf(other))} <span class="verb">${esc(verb)}</span> →`;
  return `<div class="rel"><div class="top"><span class="arrow" data-id="${esc(other)}">${arrow}</span>${badge}</div>`
    + `<div class="claim">${esc(e.claim || "")}</div>`
    + `<div class="meta"><span>可信度 ${e.conf}</span><span>${esc(e.tier)} 層</span><span>出處 ${esc(e.ref)}</span>${evidenceHtml(e.evidence)}</div></div>`;
}
function showNode(id){
  const n = byId[id]; if(!n) return;
  const outE = DATA.edges.filter(e => e.from === id), inE = DATA.edges.filter(e => e.to === id);
  let html = `<div class="phead"><h2>${esc(n.full)}</h2><button class="btn" id="close" title="關閉 (Esc)">×</button></div>`
    + `<div class="ptype"><span><i class="dot" style="background:${colorOf(n.type)}"></i> ${TYPES[n.type] || esc(n.type)}</span>`
    + `<span>中心性 ${n.cent}</span><span>${outE.length + inE.length} 條關係</span></div>`;
  if(outE.length) html += `<div class="section">由此出發（${outE.length}）</div>` + outE.map(e => relCard(e, "out")).join("");
  if(inE.length)  html += `<div class="section">指向此處（${inE.length}）</div>` + inE.map(e => relCard(e, "in")).join("");
  if(!outE.length && !inE.length) html += `<p class="empty">此節點目前沒有已入圖的關係。</p>`;
  panel.innerHTML = html; panel.classList.add("open"); panel.scrollTop = 0;
  panel.querySelector("#close").onclick = clearSelection;
  panel.querySelectorAll(".arrow").forEach(a => a.onclick = () => goTo(a.dataset.id));
}
function goTo(id){
  if(!byId[id]) return;
  if(isHidden(byId[id])){ hiddenTypes.delete(byId[id].type); if(isolated.has(id)) showIsolated = true; applyVisibility(); renderLegend(); }
  net.selectNodes([id]);
  net.fit({nodes:[...neighbours[id]], maxZoomLevel:1.5, animation:{duration:500}});   // show the whole neighbourhood
  applyFocus(id); showNode(id);
}
net.on("click", p => { if(p.nodes.length){ applyFocus(p.nodes[0]); showNode(p.nodes[0]); } else clearSelection(); });

/* ---------- search ---------- */
const q = document.getElementById("q"), hits = document.getElementById("hits");
let hitIds = [], activeHit = -1;
function renderHits(){
  hits.innerHTML = hitIds.map((id, i) => `<div class="hit${i === activeHit ? " active" : ""}" data-id="${esc(id)}">`
    + `<i class="dot" style="background:${colorOf(byId[id].type)}"></i><span>${esc(byId[id].full)}</span><small>${TYPES[byId[id].type] || ""}</small></div>`).join("");
  hits.classList.toggle("open", hitIds.length > 0);
  hits.querySelectorAll(".hit").forEach(h => h.onmousedown = ev => { ev.preventDefault(); pick(h.dataset.id); });
}
function pick(id){ q.value = byId[id].full; hitIds = []; renderHits(); goTo(id); q.blur(); }
q.oninput = () => {
  const s = q.value.trim().toLowerCase();
  hitIds = s ? DATA.nodes.filter(n => n.full.toLowerCase().includes(s) || n.id.includes(s)).slice(0, 10).map(n => n.id) : [];
  activeHit = hitIds.length ? 0 : -1; renderHits();
};
q.onkeydown = ev => {
  if(ev.key === "ArrowDown"){ activeHit = Math.min(activeHit + 1, hitIds.length - 1); renderHits(); ev.preventDefault(); }
  else if(ev.key === "ArrowUp"){ activeHit = Math.max(activeHit - 1, 0); renderHits(); ev.preventDefault(); }
  else if(ev.key === "Enter" && hitIds[activeHit]){ pick(hitIds[activeHit]); }
  else if(ev.key === "Escape"){ hitIds = []; renderHits(); q.blur(); }
};
q.onblur = () => setTimeout(() => { hitIds = []; renderHits(); }, 150);
document.addEventListener("keydown", ev => {
  if(ev.key === "Escape" && document.activeElement !== q) clearSelection();
  if(ev.key === "/" && document.activeElement !== q){ ev.preventDefault(); q.focus(); }
});
</script>
"""


def to_viewer_nodes(graph_json: dict) -> list[dict]:
    """Project node-link nodes to the fields the viewer needs (id, label, type, centrality)."""
    return [{"id": n["id"], "label": n.get("short_label") or n.get("name_zh", n["id"]),
             "full": n.get("label") or n.get("name_zh", n["id"]),
             "type": n.get("type", "concept"), "cent": n.get("centrality", 0)}
            for n in graph_json["nodes"]]


def to_viewer_edges(graph_json: dict) -> list[dict]:
    """Project node-link links to the fields the viewer needs (endpoints, kind, claim, provenance)."""
    return [{"from": e["source"], "to": e["target"], "kind": e.get("kind", ""),
             "claim": e.get("claim", ""), "evidence": e.get("evidence", ""),
             "ref": e.get("source_ref", ""), "tier": e.get("source_tier", ""),
             "conf": e.get("confidence", 0), "status": e.get("status", "")}
            for e in graph_json["links"]]


def render_html(nodes: list[dict], edges: list[dict]) -> str:
    """Embed data and kind labels into the HTML template."""
    data_json = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
    kind_json = json.dumps(KIND_VERB_ZH, ensure_ascii=False)
    return TEMPLATE.replace("/*__DATA__*/", data_json).replace("/*__KIND__*/", kind_json)


def build_viewer(root: Path = ROOT) -> tuple[int, int]:
    """Read graph.json, render the viewer, write it. Returns (node_count, edge_count)."""
    graph_json = data_io.load_graph_json(root)
    nodes, edges = to_viewer_nodes(graph_json), to_viewer_edges(graph_json)
    (root / "build/viewer.html").write_text(render_html(nodes, edges), encoding="utf-8")
    return len(nodes), len(edges)


def main() -> None:
    node_count, edge_count = build_viewer()
    print(f"viewer.html 產生,節點 {node_count} 關係 {edge_count}")


if __name__ == "__main__":
    main()
