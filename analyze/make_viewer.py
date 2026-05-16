"""
graph_d3.json → 자립형 HTML 뷰어 생성
실행: python3 analyze/make_viewer.py
출력: network/viewer.html  (브라우저에서 바로 열 수 있음)
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
GRAPH_JSON = ROOT / "network" / "graph_d3.json"
OUT_HTML   = ROOT / "network" / "viewer.html"

data = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
data_js = json.dumps(data, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KCI 콘크리트학회 저자 네트워크</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
          background: #0f1117; color: #e0e0e0; height: 100vh; overflow: hidden; }}

  #app {{ display: flex; height: 100vh; }}

  /* ── 사이드패널 ── */
  #panel {{
    width: 300px; min-width: 300px; background: #161b22;
    border-right: 1px solid #30363d;
    display: flex; flex-direction: column; overflow: hidden;
  }}
  #panel-header {{
    padding: 16px; border-bottom: 1px solid #30363d;
  }}
  #panel-header h1 {{ font-size: 14px; font-weight: 700; color: #58a6ff; margin-bottom: 4px; }}
  #panel-header p  {{ font-size: 11px; color: #8b949e; }}

  #search-wrap {{ padding: 10px 16px; border-bottom: 1px solid #30363d; }}
  #search {{ width: 100%; padding: 7px 10px; background: #0d1117;
             border: 1px solid #30363d; border-radius: 6px;
             color: #e0e0e0; font-size: 13px; }}
  #search:focus {{ outline: none; border-color: #58a6ff; }}

  #filter-wrap {{ padding: 10px 16px; border-bottom: 1px solid #30363d; display:flex; gap:8px; align-items:center; }}
  #filter-wrap label {{ font-size: 12px; color: #8b949e; white-space:nowrap; }}
  #min-papers {{ width: 60px; padding: 4px 8px; background: #0d1117;
                 border: 1px solid #30363d; border-radius: 6px; color: #e0e0e0; font-size: 12px; }}

  #author-list {{ flex: 1; overflow-y: auto; }}
  .author-item {{
    padding: 10px 16px; border-bottom: 1px solid #21262d; cursor: pointer;
    transition: background .15s;
  }}
  .author-item:hover {{ background: #1f2937; }}
  .author-item.selected {{ background: #1a3a5c; border-left: 3px solid #58a6ff; }}
  .author-name {{ font-size: 13px; font-weight: 600; color: #e0e0e0; }}
  .author-meta {{ font-size: 11px; color: #8b949e; margin-top: 2px; }}
  .author-bar {{
    height: 3px; border-radius: 2px; margin-top: 5px;
    background: linear-gradient(90deg, #58a6ff, #1f6feb);
  }}

  /* ── 상세 패널 ── */
  #detail {{
    width: 260px; min-width: 260px; background: #161b22;
    border-left: 1px solid #30363d;
    display: flex; flex-direction: column; overflow: hidden;
  }}
  #detail-content {{ padding: 16px; overflow-y: auto; flex: 1; }}
  #detail-content h2 {{ font-size: 15px; color: #58a6ff; margin-bottom: 4px; }}
  #detail-content .en-name {{ font-size: 12px; color: #8b949e; margin-bottom: 12px; }}
  .stat-row {{ display: flex; justify-content: space-between; padding: 5px 0;
               border-bottom: 1px solid #21262d; font-size: 12px; }}
  .stat-row span:first-child {{ color: #8b949e; }}
  .stat-row span:last-child  {{ color: #e0e0e0; font-weight: 600; }}
  #collab-list {{ margin-top: 12px; }}
  #collab-list h3 {{ font-size: 12px; color: #8b949e; margin-bottom: 6px; }}
  .collab-item {{ font-size: 12px; padding: 4px 0; color: #c9d1d9; border-bottom: 1px solid #21262d; }}
  .collab-item span {{ float: right; color: #58a6ff; font-size: 11px; }}

  /* ── 그래프 캔버스 ── */
  #canvas {{ flex: 1; position: relative; overflow: hidden; }}
  #canvas svg {{ width: 100%; height: 100%; }}

  /* 범례 */
  #legend {{
    position: absolute; bottom: 16px; left: 16px;
    background: rgba(22,27,34,.85); border: 1px solid #30363d;
    border-radius: 8px; padding: 10px 14px; font-size: 11px;
  }}
  #legend h4 {{ color: #8b949e; margin-bottom: 6px; }}
  .legend-row {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; }}
  .legend-dot {{ border-radius: 50%; flex-shrink: 0; }}

  /* 통계 바 */
  #stat-bar {{
    position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
    background: rgba(22,27,34,.85); border: 1px solid #30363d;
    border-radius: 20px; padding: 6px 20px;
    font-size: 12px; color: #8b949e; display: flex; gap: 20px;
  }}
  #stat-bar strong {{ color: #58a6ff; }}

  /* 줌 버튼 */
  #zoom-btns {{
    position: absolute; top: 12px; right: 12px;
    display: flex; flex-direction: column; gap: 4px;
  }}
  .zoom-btn {{
    width: 30px; height: 30px; background: #161b22; border: 1px solid #30363d;
    border-radius: 6px; color: #e0e0e0; font-size: 16px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }}
  .zoom-btn:hover {{ background: #1f2937; }}

  /* 툴팁 */
  #tooltip {{
    position: absolute; display: none;
    background: rgba(22,27,34,.95); border: 1px solid #30363d;
    border-radius: 6px; padding: 8px 12px; font-size: 12px;
    pointer-events: none; max-width: 200px; z-index: 100;
  }}

  /* 하이라이트 */
  .node circle {{ stroke-width: 1.5px; }}
  .node.dimmed circle {{ opacity: .15; }}
  .node.dimmed text  {{ opacity: .1; }}
  .link.dimmed {{ opacity: .05; }}
  .link {{ stroke-opacity: .6; }}
</style>
</head>
<body>
<div id="app">

  <!-- ── 왼쪽 목록 패널 ── -->
  <div id="panel">
    <div id="panel-header">
      <h1>🏗️ KCI 콘크리트학회</h1>
      <p>저자 공저 네트워크 (최근 5년)</p>
    </div>
    <div id="search-wrap">
      <input id="search" type="text" placeholder="저자 이름 검색...">
    </div>
    <div id="filter-wrap">
      <label for="min-papers">최소 논문 수</label>
      <input id="min-papers" type="number" value="2" min="1" max="20">
      <label style="margin-left:auto;font-size:11px;" id="visible-count"></label>
    </div>
    <div id="author-list"></div>
  </div>

  <!-- ── 중앙 그래프 ── -->
  <div id="canvas">
    <svg id="svg"></svg>
    <div id="stat-bar">
      <span>저자 <strong id="s-nodes">-</strong>명</span>
      <span>공저 <strong id="s-links">-</strong>건</span>
      <span>최다 논문 <strong id="s-top">-</strong></span>
    </div>
    <div id="zoom-btns">
      <button class="zoom-btn" id="zoom-in">+</button>
      <button class="zoom-btn" id="zoom-fit">⊡</button>
      <button class="zoom-btn" id="zoom-out">−</button>
    </div>
    <div id="legend">
      <h4>노드 크기 = 논문 수</h4>
      <div class="legend-row"><div class="legend-dot" style="width:8px;height:8px;background:#58a6ff"></div><span>1~4편</span></div>
      <div class="legend-row"><div class="legend-dot" style="width:12px;height:12px;background:#58a6ff"></div><span>5~14편</span></div>
      <div class="legend-row"><div class="legend-dot" style="width:18px;height:18px;background:#f78166"></div><span>15편 이상</span></div>
    </div>
    <div id="tooltip"></div>
  </div>

  <!-- ── 오른쪽 상세 패널 ── -->
  <div id="detail">
    <div id="detail-content">
      <p style="color:#8b949e;font-size:12px;margin-top:40px;text-align:center;">
        저자를 클릭하면<br>상세 정보가 표시됩니다
      </p>
    </div>
  </div>

</div>

<script>
// ── 데이터 ──────────────────────────────────────────────────────────────────
const RAW = {data_js};

// ── 상태 ────────────────────────────────────────────────────────────────────
let minPapers = 2;
let searchQ   = "";
let selected  = null;

// 노드맵
const nodeMap = {{}};
RAW.nodes.forEach(n => nodeMap[n.id] = n);

// 공저자 맵
const collabMap = {{}};  // name → [{{target, weight}}]
RAW.links.forEach(l => {{
  const s = typeof l.source === 'object' ? l.source.id : l.source;
  const t = typeof l.target === 'object' ? l.target.id : l.target;
  if (!collabMap[s]) collabMap[s] = [];
  if (!collabMap[t]) collabMap[t] = [];
  collabMap[s].push({{target: t, weight: l.weight}});
  collabMap[t].push({{target: s, weight: l.weight}});
}});

// ── 필터 ────────────────────────────────────────────────────────────────────
function filteredNodes() {{
  return RAW.nodes.filter(n =>
    n.paper_count >= minPapers &&
    (searchQ === "" ||
     n.id.includes(searchQ) ||
     (n.en && n.en.toLowerCase().includes(searchQ.toLowerCase())))
  );
}}

function filteredLinks(nodeSet) {{
  return RAW.links.filter(l => {{
    const s = typeof l.source === 'object' ? l.source.id : l.source;
    const t = typeof l.target === 'object' ? l.target.id : l.target;
    return nodeSet.has(s) && nodeSet.has(t);
  }});
}}

// ── 색상 / 크기 ─────────────────────────────────────────────────────────────
function nodeRadius(d) {{
  const p = d.paper_count;
  if (p >= 20) return 22;
  if (p >= 15) return 18;
  if (p >= 10) return 14;
  if (p >= 5)  return 11;
  if (p >= 3)  return 8;
  return 6;
}}

function nodeColor(d) {{
  if (d.paper_count >= 15) return "#f78166";
  if (d.paper_count >= 5)  return "#3fb950";
  return "#58a6ff";
}}

// ── D3 세팅 ─────────────────────────────────────────────────────────────────
const svg = d3.select("#svg");
const g   = svg.append("g");

const zoom = d3.zoom()
  .scaleExtent([.05, 8])
  .on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

let simulation, linkSel, nodeSel;

function buildGraph() {{
  g.selectAll("*").remove();

  const fNodes = filteredNodes();
  const nodeSet = new Set(fNodes.map(n => n.id));
  const fLinks  = filteredLinks(nodeSet);

  // stat bar
  const top = [...fNodes].sort((a,b)=>b.paper_count-a.paper_count)[0];
  document.getElementById("s-nodes").textContent = fNodes.length;
  document.getElementById("s-links").textContent = fLinks.length;
  document.getElementById("s-top").textContent   = top ? `${{top.id}} (${{top.paper_count}}편)` : "-";

  // simulation
  simulation = d3.forceSimulation(fNodes)
    .force("link", d3.forceLink(fLinks).id(d => d.id).distance(d => 60 / Math.sqrt(d.weight || 1)))
    .force("charge", d3.forceManyBody().strength(-120))
    .force("center", d3.forceCenter(
      document.getElementById("canvas").clientWidth / 2,
      document.getElementById("canvas").clientHeight / 2
    ))
    .force("collision", d3.forceCollide().radius(d => nodeRadius(d) + 4));

  linkSel = g.append("g").selectAll("line")
    .data(fLinks).join("line")
    .attr("class", "link")
    .attr("stroke", "#30363d")
    .attr("stroke-width", d => Math.min(Math.sqrt(d.weight || 1) * 1.5, 5));

  const nodeG = g.append("g").selectAll("g")
    .data(fNodes).join("g")
    .attr("class", "node")
    .call(d3.drag()
      .on("start", (e,d) => {{ if(!e.active) simulation.alphaTarget(.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on("drag",  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
      .on("end",   (e,d) => {{ if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }})
    )
    .on("click", (e,d) => {{ e.stopPropagation(); selectNode(d); }})
    .on("mouseover", showTooltip)
    .on("mousemove", moveTooltip)
    .on("mouseout",  hideTooltip);

  nodeG.append("circle")
    .attr("r", nodeRadius)
    .attr("fill", nodeColor)
    .attr("stroke", d => d3.color(nodeColor(d)).darker(1));

  nodeG.append("text")
    .text(d => d.id)
    .attr("dy", d => nodeRadius(d) + 10)
    .attr("text-anchor", "middle")
    .attr("font-size", d => d.paper_count >= 10 ? "11px" : "9px")
    .attr("fill", "#c9d1d9")
    .attr("pointer-events", "none");

  nodeSel = nodeG;

  simulation.on("tick", () => {{
    linkSel
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    nodeSel.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
  }});

  svg.on("click", () => clearSelection());
}}

// ── 선택 / 하이라이트 ───────────────────────────────────────────────────────
function selectNode(d) {{
  selected = d;

  // 하이라이트
  const neighbors = new Set((collabMap[d.id] || []).map(c => c.target));
  neighbors.add(d.id);

  nodeSel.classed("dimmed", n => !neighbors.has(n.id));
  linkSel.classed("dimmed", l => {{
    const s = typeof l.source === 'object' ? l.source.id : l.source;
    const t = typeof l.target === 'object' ? l.target.id : l.target;
    return s !== d.id && t !== d.id;
  }});

  // 상세 패널
  renderDetail(d);

  // 목록 패널 선택 표시
  document.querySelectorAll(".author-item").forEach(el => {{
    el.classList.toggle("selected", el.dataset.id === d.id);
  }});
}}

function clearSelection() {{
  selected = null;
  if (nodeSel) nodeSel.classed("dimmed", false);
  if (linkSel) linkSel.classed("dimmed", false);
  document.querySelectorAll(".author-item").forEach(el => el.classList.remove("selected"));
  document.getElementById("detail-content").innerHTML =
    `<p style="color:#8b949e;font-size:12px;margin-top:40px;text-align:center;">
      저자를 클릭하면<br>상세 정보가 표시됩니다</p>`;
}}

// ── 상세 패널 ────────────────────────────────────────────────────────────────
function renderDetail(d) {{
  const collabs = (collabMap[d.id] || [])
    .sort((a,b) => b.weight - a.weight)
    .slice(0, 20);

  const period = d.first_year && d.last_year
    ? `${{d.first_year}} ~ ${{d.last_year}}`
    : d.first_year || "-";

  const collabHTML = collabs.map(c => {{
    const cn = nodeMap[c.target];
    return `<div class="collab-item">
      ${{c.target}}
      ${{cn ? `<small style="color:#8b949e"> ${{cn.en || ''}}</small>` : ''}}
      <span>${{c.weight}}편</span>
    </div>`;
  }}).join("");

  document.getElementById("detail-content").innerHTML = `
    <h2>${{d.id}}</h2>
    <div class="en-name">${{d.en || ''}}</div>
    <div class="stat-row"><span>논문 수</span><span>${{d.paper_count}}편</span></div>
    <div class="stat-row"><span>공저자 수</span><span>${{d.degree}}명</span></div>
    <div class="stat-row"><span>활동 기간</span><span>${{period}}</span></div>
    <div class="stat-row"><span>매개 중심성</span><span>${{(d.betweenness*1000).toFixed(2)}}</span></div>
    <div id="collab-list">
      <h3 style="margin-top:14px;">공저자 (논문 수↓)</h3>
      ${{collabHTML || '<p style="color:#8b949e;font-size:11px;">공저자 없음</p>'}}
    </div>`;
}}

// ── 툴팁 ─────────────────────────────────────────────────────────────────────
const tooltip = document.getElementById("tooltip");
function showTooltip(e, d) {{
  tooltip.style.display = "block";
  tooltip.innerHTML = `<strong>${{d.id}}</strong> ${{d.en ? `<span style="color:#8b949e">(${{d.en}})</span>` : ''}}<br>
    논문 ${{d.paper_count}}편 · 공저자 ${{d.degree}}명<br>
    ${{d.first_year}}~${{d.last_year}}`;
}}
function moveTooltip(e) {{
  tooltip.style.left  = (e.clientX - document.getElementById("canvas").getBoundingClientRect().left + 12) + "px";
  tooltip.style.top   = (e.clientY - document.getElementById("canvas").getBoundingClientRect().top  - 10) + "px";
}}
function hideTooltip()  {{ tooltip.style.display = "none"; }}

// ── 목록 패널 ────────────────────────────────────────────────────────────────
function renderList() {{
  const fNodes = filteredNodes().sort((a,b) => b.paper_count - a.paper_count);
  const maxP   = Math.max(...fNodes.map(n => n.paper_count));

  document.getElementById("visible-count").textContent = fNodes.length + "명";
  const list = document.getElementById("author-list");
  list.innerHTML = fNodes.map(n => `
    <div class="author-item" data-id="${{n.id}}" onclick="jumpTo('${{n.id}}')">
      <div class="author-name">${{n.id}} <span style="color:#8b949e;font-size:10px;">${{n.en || ''}}</span></div>
      <div class="author-meta">논문 ${{n.paper_count}}편 · 공저자 ${{n.degree}}명 · ${{n.first_year}}~${{n.last_year}}</div>
      <div class="author-bar" style="width:${{Math.round(n.paper_count/maxP*100)}}%"></div>
    </div>`).join("");
}}

// ── 저자 목록 → 그래프 포커스 ────────────────────────────────────────────────
function jumpTo(id) {{
  const node = filteredNodes().find(n => n.id === id);
  if (!node) return;
  selectNode(node);

  if (node.x !== undefined) {{
    const rect = document.getElementById("canvas").getBoundingClientRect();
    const cx = rect.width / 2, cy = rect.height / 2;
    const scale = 2;
    svg.transition().duration(600).call(
      zoom.transform,
      d3.zoomIdentity.translate(cx - node.x*scale, cy - node.y*scale).scale(scale)
    );
  }}
}}

// ── 줌 버튼 ──────────────────────────────────────────────────────────────────
document.getElementById("zoom-in").onclick  = () => svg.transition().call(zoom.scaleBy, 1.5);
document.getElementById("zoom-out").onclick = () => svg.transition().call(zoom.scaleBy, 0.67);
document.getElementById("zoom-fit").onclick = () => {{
  const rect  = document.getElementById("canvas").getBoundingClientRect();
  const gBBox = g.node().getBBox();
  if (!gBBox.width) return;
  const scale = Math.min(rect.width/gBBox.width, rect.height/gBBox.height) * 0.9;
  svg.transition().duration(500).call(
    zoom.transform,
    d3.zoomIdentity
      .translate(rect.width/2, rect.height/2)
      .scale(scale)
      .translate(-(gBBox.x + gBBox.width/2), -(gBBox.y + gBBox.height/2))
  );
}};

// ── 이벤트 리스너 ────────────────────────────────────────────────────────────
document.getElementById("search").addEventListener("input", e => {{
  searchQ = e.target.value.trim();
  refresh();
}});
document.getElementById("min-papers").addEventListener("change", e => {{
  minPapers = parseInt(e.target.value) || 1;
  refresh();
}});

function refresh() {{
  buildGraph();
  renderList();
  clearSelection();
}}

// ── 초기화 ───────────────────────────────────────────────────────────────────
buildGraph();
renderList();
</script>
</body>
</html>"""

OUT_HTML.write_text(html, encoding="utf-8")
print(f"✓ 생성 완료: {OUT_HTML}")
print(f"  브라우저에서 열기: open \"{OUT_HTML}\"")
