#!/usr/bin/env python3
"""KCI 콘크리트학회 통합 대시보드 생성기 v4 (Canvas 렌더링)
실행: python3 analyze/make_dashboard.py
출력: network/dashboard.html
"""
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NET  = os.path.join(BASE, "network")

def load(name):
    path = os.path.join(NET, name)
    if not os.path.exists(path):
        print(f"[!] 없음: {path}"); sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def main():
    print("데이터 로드 중…")
    graph   = load("graph_d3.json")
    papers  = load("papers_lite.json")
    yearly  = load("yearly_stats.json")
    ap      = load("author_papers.json")
    topics  = load("topic_trends.json")
    clusters_path = os.path.join(NET, "clusters.json")
    clusters = json.load(open(clusters_path, encoding="utf-8")) if os.path.exists(clusters_path) else None

    tp = len(papers)
    ta = len(graph["nodes"])
    tl = len(graph["links"])
    ymin = min(int(y) for y in yearly if yearly[y]["j"]+yearly[y].get("c",0) > 0)
    ymax = max(int(y) for y in yearly)
    top20 = sorted(graph["nodes"], key=lambda x: x.get("paper_count",0), reverse=True)[:20]

    print(f"  논문 {tp}편 / 저자 {ta}명 / 공저 {tl}개 / {ymin}~{ymax}")

    top_rows = "".join(
        f'<tr><td class="rank">{i+1}</td>'
        f'<td><span class="al" data-name="{n["id"]}">{n["id"]}</span></td>'
        f'<td class="dim">{n.get("en","")}</td>'
        f'<td class="num">{n.get("paper_count",0)}</td>'
        f'<td class="num">{n.get("degree",0)}</td>'
        f'<td class="num">{n.get("first_year","")}</td>'
        f'<td class="num">{n.get("last_year","")}</td></tr>'
        for i, n in enumerate(top20)
    )

    # JSON 직렬화
    jg = json.dumps(graph,  ensure_ascii=False, separators=(',',':'))
    jp = json.dumps(papers, ensure_ascii=False, separators=(',',':'))
    jy = json.dumps(yearly, ensure_ascii=False)
    ja = json.dumps(ap,     ensure_ascii=False, separators=(',',':'))
    jt = json.dumps(topics, ensure_ascii=False)

    # AI 군집 데이터: 메타 군집 제외 (50편 미만이거나 학회운영/출판 관련)
    META_CLUSTER_KEYWORDS = ['학회', '출판', '가이드', '윤리', '저자', '세션', '심사', '편집', '구독']
    if clusters:
        real_clusters = [
            c for c in clusters["clusters"]
            if c["count"] >= 50 and not any(kw in c["label_ko"] for kw in META_CLUSTER_KEYWORDS)
        ]
        # 논문 → 군집 맵 (실제 군집에 속한 것만)
        real_cluster_ids = {c["id"] for c in real_clusters}
        paper_cluster_map = {
            item["id"]: item["cluster"]
            for item in clusters["papers"]
            if item["cluster"] in real_cluster_ids
        }
        jc = json.dumps({
            "clusters": real_clusters,
            "map": paper_cluster_map,
        }, ensure_ascii=False, separators=(',',':'))
        print(f"  AI 군집: {len(real_clusters)}개 (메타 제외 후)")
    else:
        jc = "null"
        print("  clusters.json 없음 — AI 군집 기능 비활성화")

    html = build_html(
        year_min=ymin, year_max=ymax,
        total_papers=f"{tp:,}", total_authors=f"{ta:,}", total_links=f"{tl:,}",
        span=ymax-ymin,
        top_rows=top_rows,
        j_graph=jg, j_papers=jp, j_yearly=jy, j_ap=ja, j_topics=jt, j_clusters=jc,
    )

    out = os.path.join(NET, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"저장: {out} ({os.path.getsize(out)//1024} KB)")
    print("열기: open network/dashboard.html")


def build_html(*, year_min, year_max, total_papers, total_authors, total_links,
               span, top_rows, j_graph, j_papers, j_yearly, j_ap, j_topics, j_clusters="null"):
    """HTML을 문자열 연결로 생성 (format() 불사용 → CSS/JS 중괄호 충돌 없음)."""

    CSS = """
:root{
  --bg:#090c14;--s1:#111520;--s2:#181d2e;--s3:#1e2438;
  --bd:#252d48;--bd2:#2e3860;
  --ac:#5b8dee;--gr:#34d399;--or:#fb923c;--rd:#f87171;--pu:#a78bfa;
  --tx:#e2e8f8;--t2:#7c89ae;--t3:#556080;
  --r:12px;--rs:8px;--sh:0 8px 32px rgba(0,0,0,.55);
  --tr:.16s cubic-bezier(.4,0,.2,1);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}
body{font-family:'Pretendard','Apple SD Gothic Neo',-apple-system,sans-serif;
     background:var(--bg);color:var(--tx);font-size:16px;line-height:1.55}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:3px}
.shell{display:flex;flex-direction:column;height:100vh}
header{height:52px;background:var(--s1);border-bottom:1px solid var(--bd);
       display:flex;align-items:center;padding:0 20px;gap:14px;flex-shrink:0}
.logo{width:32px;height:32px;background:linear-gradient(135deg,#5b8dee,#a78bfa);
      border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px}
.htitle{font-size:16px;font-weight:700;letter-spacing:-.3px}
.hsub{font-size:13px;color:var(--t2)}
.hchips{margin-left:auto;display:flex;gap:8px}
.chip{background:var(--s3);border:1px solid var(--bd2);border-radius:20px;
      padding:4px 10px;font-size:13px;color:var(--t2)}
.chip b{color:var(--ac);font-weight:700}
.tabbar{height:42px;background:var(--s1);border-bottom:1px solid var(--bd);
        display:flex;align-items:stretch;padding:0 20px;gap:2px;flex-shrink:0}
.tab{display:flex;align-items:center;gap:6px;padding:0 16px;
     font-size:15px;font-weight:500;color:var(--t2);cursor:pointer;
     border-bottom:2px solid transparent;transition:color var(--tr),border-color var(--tr);
     user-select:none;white-space:nowrap}
.tab:hover{color:var(--tx)}
.tab.active{color:var(--ac);border-bottom-color:var(--ac)}
.panels{flex:1;overflow:hidden;position:relative}
.panel{position:absolute;inset:0;display:none}
.panel.active{display:flex}
/* Network */
#pnet{flex-direction:row}
.sidebar{width:256px;flex-shrink:0;background:var(--s1);
         border-right:1px solid var(--bd);display:flex;flex-direction:column;overflow:hidden}
.sb-top{padding:14px;border-bottom:1px solid var(--bd);display:flex;flex-direction:column;gap:8px}
.sb-top h3{font-size:13px;font-weight:600;color:var(--t2);letter-spacing:.3px}
.inp{width:100%;background:var(--s3);border:1px solid var(--bd2);border-radius:var(--rs);
     padding:7px 10px;font-size:13.5px;color:var(--tx);outline:none;transition:border-color var(--tr)}
.inp:focus{border-color:var(--ac)}
.inp::placeholder{color:var(--t3)}
.frow{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--t2)}
.frow input[type=range]{flex:1;accent-color:var(--ac);cursor:pointer}
.fval{min-width:24px;text-align:right;color:var(--ac);font-weight:700}
.scnt{font-size:12px;color:var(--t3);text-align:right}
.alist{flex:1;overflow-y:auto;padding:5px 0}
.aitem{display:flex;align-items:center;gap:10px;padding:8px 14px;cursor:pointer;
       border-left:2px solid transparent;transition:background var(--tr),border-color var(--tr)}
.aitem:hover{background:var(--s2)}
.aitem.sel{background:rgba(91,141,238,.08);border-left-color:var(--ac)}
.av{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
    justify-content:center;font-size:10px;font-weight:800;flex-shrink:0}
.ain{flex:1;min-width:0}
.an{font-size:15px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.as{font-size:13px;color:var(--t2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ab{font-size:11px;font-weight:700;background:var(--s3);border:1px solid var(--bd2);
    border-radius:10px;padding:1px 7px;flex-shrink:0;color:var(--t2)}
.netcanvas{flex:1;position:relative;overflow:hidden;background:var(--bg)}
#netcvs{width:100%;height:100%;display:block;cursor:default}
#netcvs.drag{cursor:grabbing}
.ctls{position:absolute;left:14px;bottom:14px;display:flex;flex-direction:column;gap:6px}
.cbtn{width:32px;height:32px;background:rgba(17,21,32,.88);border:1px solid var(--bd);
      border-radius:var(--rs);cursor:pointer;display:flex;align-items:center;
      justify-content:center;font-size:15px;color:var(--t2);
      transition:all var(--tr);backdrop-filter:blur(4px)}
.cbtn:hover{background:var(--s3);color:var(--tx)}
.legend{position:absolute;left:14px;top:14px;background:rgba(9,12,20,.9);
        backdrop-filter:blur(6px);border:1px solid var(--bd);border-radius:var(--rs);
        padding:10px 12px;pointer-events:none}
.legend h5{font-size:10px;color:var(--t2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px}
.lr{display:flex;align-items:center;gap:7px;margin-bottom:4px;font-size:12px;color:var(--t2)}
.ld{border-radius:50%;flex-shrink:0}
.nst{position:absolute;right:14px;top:14px;background:rgba(9,12,20,.88);
     backdrop-filter:blur(6px);border:1px solid var(--bd);border-radius:var(--rs);
     padding:6px 12px;font-size:12px;color:var(--t2);pointer-events:none}
.tip{position:fixed;pointer-events:none;opacity:0;
     background:var(--s2);border:1px solid var(--bd2);border-radius:var(--rs);
     padding:9px 12px;font-size:13px;box-shadow:var(--sh);
     transition:opacity .1s;max-width:220px;z-index:9999;line-height:1.6}
/* Drawer */
.drawer{position:absolute;top:0;right:0;bottom:0;width:320px;
        background:var(--s1);border-left:1px solid var(--bd);
        display:flex;flex-direction:column;
        transform:translateX(100%);transition:transform var(--tr);
        z-index:30;box-shadow:-6px 0 28px rgba(0,0,0,.5)}
.drawer.open{transform:translateX(0)}
.dh{padding:16px 16px 12px;border-bottom:1px solid var(--bd);
    display:flex;align-items:flex-start;gap:10px}
.dav{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;
     justify-content:center;font-size:14px;font-weight:800;flex-shrink:0}
.dname{font-size:17px;font-weight:700;line-height:1.3}
.den{font-size:13px;color:var(--t2);margin-top:2px}
.dcls{margin-left:auto;width:28px;height:28px;background:var(--s3);
      border:1px solid var(--bd2);border-radius:6px;cursor:pointer;
      display:flex;align-items:center;justify-content:center;
      font-size:14px;color:var(--t2);flex-shrink:0;transition:all var(--tr)}
.dcls:hover{background:var(--bd2);color:var(--tx)}
.dstats{display:grid;grid-template-columns:1fr 1fr 1fr;padding:12px 16px;
        border-bottom:1px solid var(--bd);gap:8px}
.ds{background:var(--s2);border:1px solid var(--bd);border-radius:var(--rs);padding:8px;text-align:center}
.dsv{font-size:17px;font-weight:700;color:var(--ac)}
.dsl{font-size:11px;color:var(--t2);margin-top:2px}
.dbody{flex:1;overflow-y:auto;padding:12px 16px;display:flex;flex-direction:column;gap:14px}
.dsec h4{font-size:12px;font-weight:600;color:var(--t2);
         text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.ci{display:flex;align-items:center;justify-content:space-between;
    padding:6px 10px;border-radius:var(--rs);cursor:pointer;transition:background var(--tr)}
.ci:hover{background:var(--s3)}
.cn{font-size:13.5px;font-weight:500;color:var(--ac)}
.cc{font-size:12px;color:var(--t2);background:var(--s3);border:1px solid var(--bd);
    border-radius:10px;padding:1px 7px}
a.pi,div.pi{display:flex;flex-direction:column;gap:4px;padding:9px 10px;
    border-radius:var(--rs);border:1px solid var(--bd);background:var(--s2);
    transition:border-color var(--tr),background var(--tr);
    text-decoration:none;color:inherit;margin-bottom:6px}
a.pi:hover,div.pi:hover{border-color:var(--ac);background:rgba(91,141,238,.06)}
.pit{display:flex;align-items:flex-start;gap:8px}
.piy{font-size:10px;font-weight:700;color:var(--ac);background:rgba(91,141,238,.12);
     border-radius:4px;padding:1px 5px;flex-shrink:0;margin-top:1px}
.piti{font-size:13px;font-weight:500;line-height:1.45;color:var(--tx)}
.pim{font-size:12px;color:var(--t2)}
.pilh{font-size:10px;color:var(--ac);margin-top:2px}
.pij{color:var(--ac)}.pic{color:var(--gr)}.pik{color:#fb923c}
/* Trends */
#ptrend{flex-direction:column;overflow-y:auto;padding:0;gap:0}
#ptrend::-webkit-scrollbar{width:5px}
#ptrend::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:3px}
.tgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{background:var(--s1);border:1px solid var(--bd);border-radius:var(--r);padding:18px}
.card-hd{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.card-hd h3{font-size:14px;font-weight:600;color:var(--t2);
            letter-spacing:.2px;flex:1}
.card h3{font-size:14px;font-weight:600;color:var(--t2);
         letter-spacing:.2px;margin-bottom:14px}
.cw{position:relative;height:200px}
.full{grid-column:1/-1}.full .cw{height:240px}
/* 트렌드 필터바 */
.tfilterbar{position:sticky;top:0;z-index:20;background:var(--s1);
            border-bottom:1px solid var(--bd);padding:10px 24px;
            display:flex;flex-wrap:wrap;gap:10px;align-items:center;flex-shrink:0}
.tfilterbar label{font-size:11px;color:var(--t2);display:flex;align-items:center;gap:5px}
/* 통합 세그먼트 컨트롤 */
.seg,.tseg,.sort-seg,.smode-seg{display:flex;border:1px solid var(--bd2);border-radius:var(--rs);overflow:hidden}
.seg-btn,.tseg-btn,.sort-btn,.smode-btn{padding:5px 12px;font-size:12.5px;color:var(--t2);cursor:pointer;
  background:transparent;border:none;transition:all .13s;white-space:nowrap}
.seg-btn.on,.tseg-btn.on,.sort-btn.on,.smode-btn.on{background:var(--ac);color:#fff;font-weight:600}
/* focus-visible 접근성 */
.tab:focus-visible,.cbtn:focus-visible,.tseg-btn:focus-visible,.seg-btn:focus-visible,
.sort-btn:focus-visible,.aitem:focus-visible,.rank-item:focus-visible,.ci:focus-visible,
.stag:focus-visible,.rel-kw:focus-visible,.sg:focus-visible,.exp-btn:focus-visible,
.acard:focus-visible,a.pc:focus-visible,.ttog:focus-visible{
  outline:2px solid var(--ac);outline-offset:2px;
}
.tslider-wrap{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--t2)}
.tslider-wrap input[type=range]{width:100px;accent-color:var(--ac)}
.tsep{width:1px;height:20px;background:var(--bd2)}
/* KPI 행 */
.kpi-strip{display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.kpi{background:var(--s2);border:1px solid var(--bd);border-radius:var(--rs);
     padding:8px 14px;text-align:center;flex:1;min-width:100px}
.kpi-v{font-size:18px;font-weight:800;letter-spacing:-.5px}
.kpi-l{font-size:12px;color:var(--t2);margin-top:2px}
.kpi-d{font-size:11px;font-weight:600;margin-top:1px}
.up{color:var(--gr)}.dn{color:var(--rd)}.flat{color:var(--t2)}
/* Topic toggles */
.topic-toggles{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.ttog{display:flex;align-items:center;gap:5px;padding:3px 9px;border-radius:20px;
      font-size:12px;cursor:pointer;border:1.5px solid;transition:all .15s;user-select:none}
.ttog.off{opacity:.35}
.ttog .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ttog .cagr{font-size:11px;opacity:.75;margin-left:2px}
.topic-ctrl{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.tc-sort{background:var(--s3);border:1px solid var(--bd2);border-radius:var(--rs);
         padding:4px 8px;font-size:11.5px;color:var(--tx);outline:none;cursor:pointer}
.tc-hint{font-size:11px;color:var(--t3)}
/* 성장률 랭킹 */
.rank-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.rank-item{display:flex;align-items:center;gap:8px;padding:7px 10px;
           background:var(--s2);border:1px solid var(--bd);border-radius:var(--rs);
           cursor:pointer;min-width:0}
.rank-item:hover{border-color:var(--ac)}
.rank-no{font-size:12px;color:var(--t3);width:18px;text-align:center;flex-shrink:0}
.rank-name{flex:1;font-size:13px;font-weight:500;
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.rank-bar-wrap{width:72px;height:5px;background:var(--s3);border-radius:3px;flex-shrink:0}
.rank-bar{height:5px;border-radius:3px}
.rank-val{font-size:12px;font-weight:700;width:42px;text-align:right;flex-shrink:0}
/* 저자 클릭 링크 */
.pca-link{cursor:pointer;transition:color var(--tr);border-radius:3px;padding:0 1px}
.pca-link:hover{color:var(--ac);text-decoration:underline}
.pca-sep{color:var(--t3)}
/* 로컬 네트워크 모드 토글 */
#local-mode-tog{display:flex;gap:5px;margin-bottom:5px;align-items:center}
#local-mode-tog .seg-btn{padding:2px 8px;font-size:11px}
/* Heatmap */
#hmap-wrap{overflow-x:auto;padding-bottom:4px}
.hmap-cell{border-radius:2px;cursor:pointer;flex-shrink:0;transition:transform .1s}
.hmap-cell:hover{transform:scale(1.5);z-index:10;position:relative}
.trend-content{padding:20px 24px;display:flex;flex-direction:column;gap:20px}
/* Search */
#psearch{flex-direction:column}
.sbar{padding:12px 20px;background:var(--s1);border-bottom:1px solid var(--bd);
      display:flex;flex-direction:column;gap:8px;flex-shrink:0}
.sbar-row1{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.sinp-wrap{flex:1;min-width:200px;position:relative;display:flex;align-items:center}
.sinp-wrap .ico{position:absolute;left:11px;color:var(--t3);font-size:14px;pointer-events:none}
.sinp{width:100%;background:var(--s2);border:1px solid var(--bd2);
      border-radius:var(--rs);padding:9px 14px 9px 34px;font-size:15px;color:var(--tx);
      outline:none;transition:border-color var(--tr)}
.sinp:focus{border-color:var(--ac)}
.sinp::placeholder{color:var(--t3)}
.sel{background:var(--s2);border:1px solid var(--bd2);border-radius:var(--rs);
     padding:8px 10px;font-size:12.5px;color:var(--tx);outline:none;cursor:pointer}
.yr{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--t2)}
.yri{width:60px;background:var(--s2);border:1px solid var(--bd2);border-radius:var(--rs);
     padding:7px;font-size:12px;color:var(--tx);text-align:center;outline:none}
.rcnt{font-size:11px;color:var(--t2);white-space:nowrap}
/* 대분류 카테고리 pill */
.cat-pill{display:inline-flex;align-items:center;gap:4px;padding:4px 11px;border-radius:20px;
          font-size:11.5px;cursor:pointer;border:1.5px solid var(--bd);
          background:var(--s3);color:var(--t2);transition:all .15s;user-select:none;font-weight:500}
.cat-pill:hover{border-color:var(--bd2);color:var(--tx)}
.cat-pill.open{background:var(--ac);border-color:var(--ac);color:#fff}
.cat-pill.has-active{border-color:var(--ac);color:var(--ac)}
.cat-pill.open.has-active{background:var(--ac);color:#fff}
.cat-cnt{display:inline-flex;align-items:center;justify-content:center;
         min-width:16px;height:16px;border-radius:8px;
         background:rgba(255,255,255,.25);font-size:10px;padding:0 4px;font-weight:700}
.cat-pill:not(.open) .cat-cnt{background:var(--ac);color:#fff}
/* 주제 태그 (세부) */
.stags{display:flex;flex-wrap:wrap;gap:5px;padding:2px 0 4px}
.stag{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:20px;
      font-size:11px;cursor:pointer;border:1.5px solid transparent;
      background:var(--s3);color:var(--t2);transition:all .13s;user-select:none}
.stag:hover{color:var(--tx);border-color:var(--bd2)}
.stag.on{font-weight:600}
.stag .sdot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ai-cluster-row{display:flex;flex-wrap:wrap;gap:4px;padding:3px 0 2px}
.actag{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:20px;
  font-size:11.5px;cursor:pointer;border:1px solid var(--bd2);color:var(--t3);
  background:transparent;transition:all var(--tr);user-select:none;white-space:nowrap}
.actag:hover{color:var(--tx);border-color:var(--bd2)}
.actag.on{font-weight:600}
.actag .acdot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.actag-cnt{font-size:10px;opacity:.6;margin-left:2px}
.stag-clear{background:transparent;border:1px solid var(--bd2);color:var(--t3);font-size:11px;
            border-radius:20px;padding:3px 9px;cursor:pointer;transition:all .13s}
.stag-clear:hover{border-color:var(--rd);color:var(--rd)}
/* 연관 키워드 */
.rel-box{display:flex;align-items:center;gap:6px;padding:6px 0 2px;flex-wrap:wrap}
.rel-label{font-size:10.5px;color:var(--t3);white-space:nowrap}
.rel-kw{background:var(--s3);border:1px solid var(--bd2);border-radius:20px;
        padding:3px 10px;font-size:11px;color:var(--t2);cursor:pointer;transition:all .13s}
.rel-kw:hover{border-color:var(--ac);color:var(--ac)}
/* 검색 컨트롤 행 (정렬·내보내기) */
.sctrl{display:flex;align-items:center;gap:8px;padding:6px 0 2px;flex-wrap:wrap}
/* sort-seg/smode-seg는 통합 .seg 규칙으로 처리됨 */
.exp-btn{display:flex;align-items:center;gap:5px;padding:4px 11px;font-size:11.5px;
         color:var(--t2);background:var(--s3);border:1px solid var(--bd2);
         border-radius:var(--rs);cursor:pointer;transition:all .13s;white-space:nowrap;margin-left:auto}
.exp-btn:hover{border-color:var(--ac);color:var(--ac)}
.rsummary{font-size:11px;color:var(--t3);padding:2px 0}
/* 키워드 트렌드 패널 */
.trend-panel{background:var(--s2);border:1px solid var(--bd);border-radius:var(--rs);
             margin-bottom:12px;display:grid;grid-template-rows:1fr;
             transition:grid-template-rows .25s ease,opacity .2s,margin .2s,border-width .2s}
.trend-panel>*{overflow:hidden;min-height:0;padding:14px 16px}
.trend-panel.collapsed{grid-template-rows:0fr;opacity:0;margin:0;border-width:0}
.trend-panel.collapsed>*{padding:0}
.tp-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.tp-title{font-size:11.5px;font-weight:600;color:var(--tx);flex:1}
.tp-kpis{display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap}
.tp-kpi{background:var(--s1);border:1px solid var(--bd);border-radius:var(--rs);
        padding:6px 12px;text-align:center;flex:1;min-width:80px}
.tp-kpi-v{font-size:15px;font-weight:700;color:var(--ac)}
.tp-kpi-l{font-size:10px;color:var(--t2)}
.tp-chart-wrap{position:relative;height:110px}
.tp-close{width:22px;height:22px;background:var(--s3);border:1px solid var(--bd2);
          border-radius:4px;cursor:pointer;display:flex;align-items:center;justify-content:center;
          font-size:12px;color:var(--t2);flex-shrink:0}
.tp-close:hover{color:var(--tx)}
/* AND/OR 토글 */
.tag-logic{font-size:10px;color:var(--t3);padding:2px 7px;border:1px solid var(--bd2);
           border-radius:10px;cursor:pointer;transition:all .13s;user-select:none}
.tag-logic.and{color:var(--ac);border-color:var(--ac);background:rgba(91,141,238,.1)}
/* 결과 영역 */
.rarea{flex:1;overflow-y:auto;padding:12px 20px}
/* 저자 결과 카드 */
.acard{background:var(--s1);border:1px solid var(--bd);border-radius:var(--rs);
       padding:12px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px;
       cursor:pointer;transition:border-color var(--tr),background var(--tr)}
.acard:hover{border-color:var(--ac);background:rgba(91,141,238,.04)}
.acard-av{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;
          justify-content:center;font-size:12px;font-weight:800;flex-shrink:0}
.acard-info{flex:1;min-width:0}
.acard-name{font-size:13.5px;font-weight:600;color:var(--tx)}
.acard-en{font-size:11px;color:var(--t2)}
.acard-meta{display:flex;gap:8px;margin-top:4px;font-size:11px;color:var(--t2)}
.acard-badge{background:rgba(91,141,238,.1);border:1px solid rgba(91,141,238,.25);
             border-radius:4px;padding:2px 7px;font-size:11px;color:var(--ac);font-weight:600}
/* 논문 카드 */
a.pc,div.pc{background:var(--s1);border:1px solid var(--bd);border-radius:var(--rs);
    padding:13px 16px;margin-bottom:7px;
    transition:border-color var(--tr),background var(--tr);
    cursor:pointer;text-decoration:none;display:block;color:inherit}
a.pc:hover,div.pc:hover{border-color:var(--ac);background:rgba(91,141,238,.04)}
.pct{font-size:15px;font-weight:600;line-height:1.45;margin-bottom:6px}
.pct em{background:rgba(91,141,238,.18);color:var(--ac);font-style:normal;
        border-radius:2px;padding:0 2px}
.pcm{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.badge{border-radius:4px;padding:2px 7px;font-size:11px;font-weight:500;border:1px solid}
.bj{color:var(--ac);border-color:rgba(91,141,238,.3);background:rgba(91,141,238,.08)}
.bc{color:var(--gr);border-color:rgba(52,211,153,.3);background:rgba(52,211,153,.08)}
.bk{color:#fb923c;border-color:rgba(251,146,60,.3);background:rgba(251,146,60,.08)}
.bksmi{color:#fb923c!important;font-weight:600}
.bksmi.on{background:#fb923c!important}
.pca{font-size:13px;color:var(--t2)}
.pctag{font-size:10.5px;background:rgba(167,139,250,.12);border:1px solid rgba(167,139,250,.25);
       color:#a78bfa;border-radius:4px;padding:1px 6px}
.pcai{font-size:10px;border-radius:4px;padding:1px 6px;border:1px solid;opacity:.85}
.nr{text-align:center;padding:60px 20px;color:var(--t2)}
.nri{font-size:36px;margin-bottom:12px}
.nr p{font-size:13px}
.sugbox{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:16px}
.sg{background:var(--s2);border:1px solid var(--bd2);border-radius:20px;
    padding:5px 12px;font-size:12px;color:var(--t2);cursor:pointer;transition:all var(--tr)}
.sg:hover{border-color:var(--ac);color:var(--ac)}
.sec-header{font-size:11px;font-weight:600;color:var(--t2);text-transform:uppercase;
            letter-spacing:.5px;margin:8px 0 6px;padding:0 2px}
.sec-header:first-child{margin-top:0}
/* Stats */
#pstats{flex-direction:column;overflow-y:auto;padding:20px 24px;gap:20px}
.krow{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.kc{background:var(--s1);border:1px solid var(--bd);border-radius:var(--r);
    padding:18px;text-align:center}
.kv{font-size:28px;font-weight:800;letter-spacing:-1px;color:var(--ac)}
.kl{font-size:12px;color:var(--t2);margin-top:4px}
.sgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
table.rt{width:100%;border-collapse:collapse;font-size:14px}
table.rt th{text-align:left;padding:7px 10px;font-size:12px;font-weight:600;
            color:var(--t2);letter-spacing:.2px;
            border-bottom:1px solid var(--bd)}
table.rt td{padding:7px 10px;border-bottom:1px solid rgba(37,45,72,.5)}
table.rt tr:last-child td{border-bottom:none}
td.rank{color:var(--t3);width:28px}
td.dim{color:var(--t2);font-size:11.5px}
td.num{color:var(--t2);text-align:right}
.al{color:var(--ac);cursor:pointer;font-weight:500}
.al:hover{text-decoration:underline}
.bwb{display:flex;align-items:center;gap:7px}
.bwbar{height:5px;border-radius:3px;background:linear-gradient(90deg,var(--pu),var(--ac));flex-shrink:0}
#ptrend::-webkit-scrollbar,#pstats::-webkit-scrollbar{width:5px}
#ptrend::-webkit-scrollbar-thumb,#pstats::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:3px}
"""

    BODY = (
        '<div class="shell">'
        '<header>'
        '  <div class="logo">🏗</div>'
        '  <div>'
        f'    <div class="htitle">한국콘크리트학회 논문 분석</div>'
        f'    <div class="hsub">Korean Concrete Institute · {year_min}–{year_max}</div>'
        '  </div>'
        '  <div class="hchips">'
        f'    <div class="chip">논문 <b>{total_papers}</b>편</div>'
        f'    <div class="chip">저자 <b>{total_authors}</b>명</div>'
        f'    <div class="chip">공저 <b>{total_links}</b>건</div>'
        '  </div>'
        '</header>'
        '<div class="tabbar">'
        '  <div class="tab active" data-tab="net">🕸 저자 네트워크</div>'
        '  <div class="tab" data-tab="trend">📈 트렌드</div>'
        '  <div class="tab" data-tab="search">🔍 논문 검색</div>'
        '  <div class="tab" data-tab="stats">📊 통계</div>'
        '</div>'
        '<div class="panels">'
        # ── Network ──
        '<div id="pnet" class="panel active">'
        '  <div class="sidebar">'
        '    <div class="sb-top">'
        '      <h3>저자 목록</h3>'
        '      <input class="inp" id="asearch" placeholder="이름 검색…">'
        '      <div class="frow">'
        '        <span>최소 논문</span>'
        '        <input type="range" id="minp" min="1" max="50" value="10">'
        '        <span class="fval" id="minpv">10</span>편'
        '      </div>'
        '      <div class="scnt" id="acnt">로드 중…</div>'
        '    </div>'
        '    <div class="alist" id="alist"></div>'
        '  </div>'
        '  <div class="netcanvas">'
        '    <canvas id="netcvs"></canvas>'
        '    <div class="legend">'
        '      <h4>논문 수</h4>'
        '      <div class="lr"><div class="ld" style="width:7px;height:7px;background:#5b8dee"></div>1–4편</div>'
        '      <div class="lr"><div class="ld" style="width:10px;height:10px;background:#34d399"></div>5–19편</div>'
        '      <div class="lr"><div class="ld" style="width:14px;height:14px;background:#fb923c"></div>20–49편</div>'
        '      <div class="lr"><div class="ld" style="width:18px;height:18px;background:#f87171"></div>50편+</div>'
        '    </div>'
        '    <div class="nst" id="nst">시뮬레이션 중…</div>'
        '    <div class="ctls">'
        '      <div class="cbtn" id="bzi">＋</div>'
        '      <div class="cbtn" id="bzo">－</div>'
        '      <div class="cbtn" id="brst">⟳</div>'
        '    </div>'
        '  </div>'
        '  <div class="drawer" id="drawer">'
        '    <div class="dh">'
        '      <div class="dav" id="dav"></div>'
        '      <div><div class="dname" id="dname"></div><div class="den" id="den"></div></div>'
        '      <div class="dcls" id="dcls">✕</div>'
        '    </div>'
        '    <div class="dstats">'
        '      <div class="ds"><div class="dsv" id="dpap">—</div><div class="dsl">논문</div></div>'
        '      <div class="ds"><div class="dsv" id="dcol">—</div><div class="dsl">공저자</div></div>'
        '      <div class="ds"><div class="dsv" id="dyrs">—</div><div class="dsl">활동기간</div></div>'
        '    </div>'
        '    <div id="local-graph" style="border-bottom:1px solid var(--bd);padding:8px 12px;background:var(--bg)">'
        '      <div style="font-size:11px;color:var(--t3);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:.4px">로컬 네트워크</div>'
        '      <svg id="local-svg" width="292" height="160"></svg>'
        '    </div>'
        '    <div class="dbody" id="dbody"></div>'
        '  </div>'
        '</div>'
        # ── Trends ──
        '<div id="ptrend" class="panel">'
        # 상단 필터바
        '  <div class="tfilterbar">'
        '    <label>출처'
        '      <div class="tseg" id="tsrc">'
        '        <div class="tseg-btn on" data-v="all">전체</div>'
        '        <div class="tseg-btn" data-v="journal">학회지</div>'
        '        <div class="tseg-btn" data-v="conference">학술대회</div>'
        '      </div>'
        '    </label>'
        '    <div class="tsep"></div>'
        f'   <div class="tslider-wrap">연도 범위 <input type="range" id="tyrf" min="{year_min}" max="{year_max}" value="{year_min}"><span id="tyrfv">{year_min}</span>–<input type="range" id="tyrt" min="{year_min}" max="{year_max}" value="{year_max}"><span id="tyrtv">{year_max}</span></div>'
        '    <div class="tsep"></div>'
        '    <label>표시 단위'
        '      <div class="tseg" id="tunit">'
        '        <div class="tseg-btn on" data-v="pct">비중(%)</div>'
        '        <div class="tseg-btn" data-v="count">건수</div>'
        '      </div>'
        '    </label>'
        '  </div>'
        # 본문 컨텐츠
        '  <div class="trend-content">'
        # 1. 연도별 차트 + 급성장 + 감소 — 3열 한 행
        '    <div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;align-items:stretch">'
        '      <div class="card" style="display:flex;flex-direction:column">'
        '        <div class="card-hd"><h3>📊 연도별 논문 발행 현황</h3></div>'
        '        <div class="kpi-strip" id="yr-kpis"></div>'
        '        <div class="cw" style="flex:1;min-height:180px"><canvas id="cyr"></canvas></div>'
        '      </div>'
        '      <div class="card">'
        '        <div class="card-hd" style="margin-bottom:10px"><h3>🚀 급성장 주제</h3></div>'
        '        <div id="rank-rise" style="display:flex;flex-direction:column;gap:6px"></div>'
        '      </div>'
        '      <div class="card">'
        '        <div class="card-hd" style="margin-bottom:10px"><h3>📉 감소 주제</h3></div>'
        '        <div id="rank-fall" style="display:flex;flex-direction:column;gap:6px"></div>'
        '      </div>'
        '    </div>'
        # 2. 히트맵(좌) + 주제 트렌드(우) 나란히, 높이 통일
        '    <div style="display:grid;grid-template-columns:auto 1fr;gap:16px;align-items:stretch">'
        # 히트맵 (좌)
        '      <div class="card" style="display:flex;flex-direction:column">'
        '        <div class="card-hd">'
        '          <h3>🗓 주제 × 연도 히트맵</h3>'
        '          <div class="tseg" id="hmgran">'
        '            <div class="tseg-btn" data-v="year">연도별</div>'
        '            <div class="tseg-btn on" data-v="5year">5년 단위</div>'
        '          </div>'
        '        </div>'
        '        <div id="hmap-wrap" style="flex:1;overflow-x:auto;padding-bottom:4px"><div id="hmap"></div></div>'
        '      </div>'
        # 주제 트렌드 (우) — flex-column으로 캔버스가 남은 공간 채움
        '      <div class="card" style="display:flex;flex-direction:column;min-width:0">'
        '        <div class="card-hd">'
        '          <h3>📈 연구 주제 트렌드</h3>'
        '          <div class="topic-ctrl">'
        '            <select class="tc-sort" id="topicSort">'
        '              <option value="total">총량순</option>'
        '              <option value="recent">최근 5년 성장순</option>'
        '              <option value="name">가나다순</option>'
        '            </select>'
        '            <span class="tc-hint" id="topic-hint">최대 8개 선택</span>'
        '          </div>'
        '        </div>'
        '        <div class="topic-toggles" id="topic-toggles"></div>'
        '        <div style="flex:1;min-height:200px;position:relative"><canvas id="ctopic" style="width:100%;height:100%"></canvas></div>'
        '        <p style="font-size:11px;color:var(--t3);margin-top:6px">※ 제목 키워드 기반 자동 분류 · 참고용</p>'
        '      </div>'
        '    </div>'
        # 3. 활동 저자 + 논문당 저자 수
        '    <div class="tgrid">'
        '      <div class="card"><h3>👥 연도별 활동 저자 수</h3><div class="cw"><canvas id="cua"></canvas></div></div>'
        '      <div class="card"><h3>✍️ 논문당 평균 저자 수</h3><div class="cw"><canvas id="cco"></canvas></div></div>'
        '    </div>'
        '  </div>'  # /trend-content
        '</div>'
        # ── Search ──
        '<div id="psearch" class="panel">'
        '  <div class="sbar">'
        '    <div class="sbar-row1">'
        '      <div class="sinp-wrap"><span class="ico">🔍</span>'
        '        <input class="sinp" id="sinp" placeholder="제목 · 저자명 · 키워드 검색…" autocomplete="off">'
        '        <div id="hist-drop" style="display:none;position:absolute;top:100%;left:0;right:0;z-index:50;'
        '          background:var(--s2);border:1px solid var(--bd2);border-radius:var(--rs);'
        '          box-shadow:var(--sh);margin-top:2px"></div>'
        '      </div>'
        '      <div class="tseg" id="ssrc">'
        '        <div class="tseg-btn on" data-v="all">전체</div>'
        '        <div class="tseg-btn" data-v="journal">학회지</div>'
        '        <div class="tseg-btn" data-v="conference">학술대회</div>'
        '      </div>'
        '      <div class="tseg" id="ssoc" style="margin-left:4px">'
        '        <div class="tseg-btn on" data-v="all" title="KCI + KSMI 전체">전체</div>'
        '        <div class="tseg-btn" data-v="KCI" title="한국콘크리트학회">KCI</div>'
        '        <div class="tseg-btn bksmi" data-v="KSMI" title="한국구조물진단유지관리공학회">KSMI</div>'
        '      </div>'
        f'     <div class="yr"><input class="yri" id="yrf" value="{year_min}"><span>–</span><input class="yri" id="yrt" value="{year_max}"></div>'
        '    </div>'
        # 필터 바: 한 줄 (주제 대분류 + AI 세부분야 토글 + OR/AND)
        '    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:3px 0 2px;position:relative">'
        '      <span class="rel-label">주제:</span>'
        '      <div id="cat-pills" style="display:flex;flex-wrap:wrap;gap:4px"></div>'
        '      <span style="margin-left:auto;display:flex;gap:6px;align-items:center">'
        '        <span class="tag-logic" id="tag-logic" onclick="toggleTagLogic()">OR</span>'
        '        <span id="active-tag-clear" style="display:none;cursor:pointer;font-size:11px;color:var(--t3)" onclick="clearAllFilters()">✕ 필터 초기화</span>'
        '      </span>'
        # 드롭다운 (overlay, 공간 안 차지)
        '      <div id="stag-dropdown" style="display:none;position:absolute;top:100%;left:0;right:0;z-index:100;'
        '           background:var(--s1);border:1px solid var(--bd2);border-radius:10px;'
        '           box-shadow:0 8px 32px rgba(0,0,0,.5);padding:10px 12px;margin-top:4px">'
        '        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
        '          <span id="dropdown-cat-label" style="font-size:12px;font-weight:600;color:var(--tx)"></span>'
        '          <span style="margin-left:auto;font-size:11px;color:var(--t3);cursor:pointer" onclick="closeCatDropdown()">✕ 닫기</span>'
        '        </div>'
        '        <div id="stag-row" style="display:flex;flex-wrap:wrap;gap:6px"></div>'
        '      </div>'
        '    </div>'
        # 정렬·컨트롤 행
        '    <div class="sctrl">'
        '      <div class="sort-seg" id="ssort">'
        '        <div class="sort-btn on" data-v="recent">최신순</div>'
        '        <div class="sort-btn" data-v="old">오래된순</div>'
        '        <div class="sort-btn" data-v="rel">관련도순</div>'
        '      </div>'
        '      <div class="rcnt" id="rcnt">—</div>'
        '      <div class="rsummary" id="rsummary"></div>'
        '      <div class="exp-btn" onclick="exportCSV()">↓ CSV</div>'
        '    </div>'
        # 연관 주제 행
        '    <div id="rel-row" class="rel-box" style="display:none"></div>'
        '  </div>'
        '  <div class="rarea" id="rarea">'
        f'    <div class="nr"><div class="nri">🔍</div><p>제목이나 저자 이름을 입력해 <b>{total_papers}편</b>의 논문을 검색하세요</p>'
        '      <div class="sugbox">'
        '        <div class="sg" onclick="setS(\'콘크리트 강도\')">콘크리트 강도</div>'
        '        <div class="sg" onclick="setS(\'철근\')">철근</div>'
        '        <div class="sg" onclick="setS(\'균열\')">균열</div>'
        '        <div class="sg" onclick="setS(\'내구성\')">내구성</div>'
        '        <div class="sg" onclick="setS(\'UHPC\')">UHPC</div>'
        '        <div class="sg" onclick="setS(\'FRP\')">FRP</div>'
        '        <div class="sg" onclick="setS(\'프리스트레스\')">프리스트레스</div>'
        '        <div class="sg" onclick="setS(\'배합\')">배합설계</div>'
        '      </div></div>'
        '  </div>'
        '</div>'
        # ── Stats ──
        '<div id="pstats" class="panel">'
        '  <div class="krow">'
        f'    <div class="kc"><div class="kv">{total_papers}</div><div class="kl">총 논문</div></div>'
        f'    <div class="kc"><div class="kv">{total_authors}</div><div class="kl">등록 저자</div></div>'
        f'    <div class="kc"><div class="kv">{total_links}</div><div class="kl">공저 관계</div></div>'
        f'    <div class="kc"><div class="kv">{span}</div><div class="kl">수집 기간(년)</div></div>'
        '  </div>'
        '  <div id="stat-insights" style="margin:10px 0 14px"></div>'
        '  <div class="sgrid">'
        '    <div class="card"><h3>논문 수 상위 20인</h3>'
        '      <table class="rt"><thead><tr><th>#</th><th>이름</th><th>영문</th>'
        '        <th>논문</th><th>공저자</th><th>시작</th><th>최근</th></tr></thead>'
        f'      <tbody>{top_rows}</tbody></table>'
        '    </div>'
        '    <div class="card"><h3>매개 중심성 상위 (네트워크 허브)</h3><div id="bwlist"></div></div>'
        '  </div>'
        '</div>'
        '</div>'  # /panels
        '</div>'  # /shell
        # 전역 툴팁 (body 수준 - 모든 탭에서 올바른 좌표 사용)
        '<div class="tip" id="tip" style="position:fixed;z-index:9999"></div>'
    )

    JS = r"""
const GRAPH=__GRAPH__;
const PAPERS=__PAPERS__;
const YEARLY=__YEARLY__;
const AP=__AP__;
const TOPICS=__TOPICS__;
const CLUSTERS=__CLUSTERS__;
const YEAR_MIN=__YMIN__;
const YEAR_MAX=__YMAX__;

const PMAP={};PAPERS.forEach(p=>PMAP[p.dn]=p);
const NM={};GRAPH.nodes.forEach(n=>NM[n.id]=n);
const SOCIETIES=[...new Set(PAPERS.map(p=>p.soc||'KCI'))];
// 인접 리스트 (로컬 그래프용)
const ADJ=new Map();
GRAPH.links.forEach(l=>{
  const s=typeof l.source==='object'?l.source.id:l.source;
  const t=typeof l.target==='object'?l.target.id:l.target;
  if(!ADJ.has(s))ADJ.set(s,[]);
  if(!ADJ.has(t))ADJ.set(t,[]);
  ADJ.get(s).push({id:t,w:l.weight||1});
  ADJ.get(t).push({id:s,w:l.weight||1});
});

const nc=c=>c>=50?'#f87171':c>=20?'#fb923c':c>=5?'#34d399':'#5b8dee';
const nr=c=>c>=50?13:c>=20?9:c>=5?6.5:4.5;
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function hl(t,q){if(!q)return esc(t);const re=new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');return esc(t).replace(re,m=>`<em>${m}</em>`)}

// Tabs
let tBuilt=false,sBuilt=false;
document.querySelectorAll('.tab').forEach(t=>{
  t.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    document.getElementById('p'+t.dataset.tab).classList.add('active');
    if(t.dataset.tab==='trend'&&!tBuilt)buildTrends();
    if(t.dataset.tab==='stats'&&!sBuilt)buildStats();
  });
});

// Canvas network
const cvs=document.getElementById('netcvs');
const ctx=cvs.getContext('2d');
let sim,curNodes=[],curLinks=[],transform=d3.zoomIdentity;
let hovNode=null,selId=null,minPF=10,animating=false;

function resize(){
  const r=cvs.parentElement.getBoundingClientRect();
  cvs.width=r.width;cvs.height=r.height;draw();
}

function buildSim(){
  if(sim)sim.stop();
  const W=cvs.width,H=cvs.height;
  curNodes=GRAPH.nodes.filter(n=>n.paper_count>=minPF).map(n=>Object.assign({},n));
  const ids=new Set(curNodes.map(n=>n.id));
  curLinks=GRAPH.links.map(l=>{
    const s=typeof l.source==='object'?l.source.id:l.source;
    const t=typeof l.target==='object'?l.target.id:l.target;
    return {...l,source:s,target:t,w:l.weight};
  }).filter(l=>ids.has(l.source)&&ids.has(l.target));
  document.getElementById('nst').textContent=`시뮬레이션 중… (${curNodes.length}명)`;
  curNodes.forEach(n=>NM[n.id]=n);
  sim=d3.forceSimulation(curNodes)
    .force('link',d3.forceLink(curLinks).id(d=>d.id).distance(60))
    .force('charge',d3.forceManyBody().strength(d=>-80-d.paper_count*.4))
    .force('center',d3.forceCenter(W/2,H/2).strength(.05))
    .force('col',d3.forceCollide().radius(d=>nr(d.paper_count)+2))
    .alphaDecay(.025)
    .on('tick',()=>{if(!animating){animating=true;requestAnimationFrame(loop);}})
    .on('end',()=>{document.getElementById('nst').textContent=`${curNodes.length}명 표시`;draw();});
}

function loop(){animating=false;draw();if(sim&&sim.alpha()>.001){animating=true;requestAnimationFrame(loop);}}

function draw(){
  const W=cvs.width,H=cvs.height;
  ctx.clearRect(0,0,W,H);
  ctx.save();
  ctx.translate(transform.x,transform.y);
  ctx.scale(transform.k,transform.k);
  const hasSel=!!selId;
  // neighbors set
  const nbrs=new Set();
  if(hasSel){nbrs.add(selId);for(const l of curLinks){const s=l.source,t=l.target;if(typeof s!=='object'||typeof t!=='object')continue;if(s.id===selId)nbrs.add(t.id);if(t.id===selId)nbrs.add(s.id);}}
  // Links
  for(const l of curLinks){
    const s=l.source,t=l.target;
    if(typeof s!=='object'||typeof t!=='object')continue;
    const dim=hasSel&&s.id!==selId&&t.id!==selId;
    ctx.globalAlpha=dim?.05:.45;
    ctx.strokeStyle='#252d48';
    ctx.lineWidth=Math.min(l.w*.6,3)/transform.k;
    ctx.beginPath();ctx.moveTo(s.x,s.y);ctx.lineTo(t.x,t.y);ctx.stroke();
  }
  // Nodes
  for(const n of curNodes){
    if(n.x==null)continue;
    const r=nr(n.paper_count),col=nc(n.paper_count);
    const dim=hasSel&&!nbrs.has(n.id);
    ctx.globalAlpha=dim?.07:1;
    ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);
    ctx.fillStyle=col;ctx.fill();
    ctx.strokeStyle='#090c14';ctx.lineWidth=1.5/transform.k;ctx.stroke();
    if(hovNode&&hovNode.id===n.id){
      ctx.globalAlpha=.5;ctx.beginPath();ctx.arc(n.x,n.y,r+3/transform.k,0,Math.PI*2);
      ctx.strokeStyle='#fff';ctx.lineWidth=1.5/transform.k;ctx.stroke();
    }
  }
  ctx.globalAlpha=1;
  // Labels
  const minLabel=minPF>=10?5:20;
  if(transform.k>0.5){
    ctx.textAlign='center';
    for(const n of curNodes){
      if(n.paper_count<minLabel||n.x==null)continue;
      const dim=hasSel&&!nbrs.has(n.id);
      ctx.globalAlpha=dim?.07:.75;
      ctx.font=`${Math.min(11/transform.k,11)}px 'Apple SD Gothic Neo',sans-serif`;
      ctx.fillStyle='#7c89ae';
      ctx.fillText(n.id,n.x,n.y+nr(n.paper_count)+9/transform.k);
    }
  }
  ctx.globalAlpha=1;ctx.restore();
}

// Zoom
const zb=d3.zoom().scaleExtent([.04,14]).on('zoom',e=>{transform=e.transform;draw();});
d3.select(cvs).call(zb);
document.getElementById('bzi').onclick=()=>d3.select(cvs).transition().call(zb.scaleBy,1.5);
document.getElementById('bzo').onclick=()=>d3.select(cvs).transition().call(zb.scaleBy,.67);
document.getElementById('brst').onclick=()=>{
  d3.select(cvs).transition().duration(500).call(zb.transform,d3.zoomIdentity);
  closeDrawer();selId=null;draw();
};

// Hit-test
function nodeAt(mx,my){
  const x=(mx-transform.x)/transform.k,y=(my-transform.y)/transform.k;
  let best=null,bd=Infinity;
  for(const n of curNodes){if(n.x==null)continue;const d2=(n.x-x)**2+(n.y-y)**2,r=nr(n.paper_count)+4;if(d2<r*r&&d2<bd){bd=d2;best=n;}}
  return best;
}

const tip=document.getElementById('tip');
cvs.addEventListener('mousemove',e=>{
  const r=cvs.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  const n=nodeAt(mx,my);
  if(n!==hovNode){hovNode=n;draw();}
  if(n){
    tip.innerHTML=`<b>${esc(n.id)}</b><br><span style="color:var(--t2)">${n.en||''}</span><br>논문 ${n.paper_count}편 · 공저자 ${n.degree}명`;
    tip.style.opacity='1';
    // position:fixed — clientX/Y 직접 사용
    let tx=e.clientX+14,ty=e.clientY-50;
    if(tx+220>window.innerWidth)tx=e.clientX-230;
    if(ty<0)ty=e.clientY+10;
    tip.style.left=tx+'px';tip.style.top=ty+'px';
  }else tip.style.opacity='0';
});
cvs.addEventListener('mouseleave',()=>{hovNode=null;tip.style.opacity='0';draw();});
cvs.addEventListener('click',e=>{
  const r=cvs.getBoundingClientRect();
  const n=nodeAt(e.clientX-r.left,e.clientY-r.top);
  if(n){selId=n.id;openDrawer(n);}else{selId=null;closeDrawer();draw();}
});

// Drag
let dragging=false,dragNode=null;
cvs.addEventListener('mousedown',e=>{
  const r=cvs.getBoundingClientRect();dragNode=nodeAt(e.clientX-r.left,e.clientY-r.top);
  if(dragNode){dragging=true;cvs.classList.add('drag');sim&&sim.alphaTarget(.3).restart();}
});
window.addEventListener('mousemove',e=>{
  if(!dragging||!dragNode)return;
  const r=cvs.getBoundingClientRect();
  dragNode.fx=(e.clientX-r.left-transform.x)/transform.k;
  dragNode.fy=(e.clientY-r.top-transform.y)/transform.k;
  if(!animating){animating=true;requestAnimationFrame(loop);}
});
window.addEventListener('mouseup',()=>{
  if(dragging&&dragNode){dragNode.fx=null;dragNode.fy=null;sim&&sim.alphaTarget(0);}
  dragging=false;dragNode=null;cvs.classList.remove('drag');
});

// Sidebar
function renderList(q=''){
  const ql=q.toLowerCase();
  const f=GRAPH.nodes.filter(n=>n.paper_count>=minPF&&(!ql||n.id.includes(ql)||(n.en||'').toLowerCase().includes(ql)))
    .sort((a,b)=>b.paper_count-a.paper_count).slice(0,150);
  document.getElementById('acnt').textContent=`${f.length}명 표시`;
  document.getElementById('alist').innerHTML=f.map(n=>{
    const c=nc(n.paper_count);
    return `<div class="aitem${selId===n.id?' sel':''}" data-name="${n.id}" onclick="selectById('${n.id}')">
      <div class="av" style="background:${c}22;color:${c}">${n.id[0]||'?'}</div>
      <div class="ain"><div class="an">${esc(n.id)}</div><div class="as">${n.en||n.first_year+'–'+n.last_year}</div></div>
      <div class="ab">${n.paper_count}</div>
    </div>`;
  }).join('');
}
document.getElementById('asearch').addEventListener('input',e=>renderList(e.target.value));
let simTm=null;
document.getElementById('minp').addEventListener('input',e=>{
  minPF=+e.target.value;document.getElementById('minpv').textContent=minPF;
  renderList(document.getElementById('asearch').value);
  clearTimeout(simTm);simTm=setTimeout(buildSim,300); // 디바운스 300ms
});

// Drawer
function openDrawer(n){
  selId=n.id;draw();
  document.querySelectorAll('.aitem').forEach(e=>{
    e.classList.toggle('sel',e.dataset.name===n.id);
    if(e.dataset.name===n.id)e.scrollIntoView({block:'nearest'});
  });
  const c=nc(n.paper_count);
  const dav=document.getElementById('dav');
  dav.textContent=n.id.slice(0,2);
  dav.style.cssText=`width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;flex-shrink:0;background:${c}22;color:${c}`;
  document.getElementById('dname').textContent=n.id;
  document.getElementById('den').textContent=n.en||'';
  document.getElementById('dpap').textContent=n.paper_count;
  document.getElementById('dcol').textContent=n.degree;
  const sp=+n.last_year - +n.first_year;
  document.getElementById('dyrs').textContent=sp>0?sp+'년':'—';
  const collabs=[];
  for(const l of GRAPH.links){
    const s=typeof l.source==='object'?l.source.id:l.source;
    const t=typeof l.target==='object'?l.target.id:l.target;
    if(s===n.id)collabs.push({name:t,cnt:l.weight});
    if(t===n.id)collabs.push({name:s,cnt:l.weight});
  }
  collabs.sort((a,b)=>b.cnt-a.cnt);
  const dns=(AP[n.id]||[]);
  const allP=dns.map(dn=>PMAP[dn]).filter(Boolean).sort((a,b)=>(+b.y||0)-(+a.y||0));
  let html='';
  if(collabs.length){
    html+=`<div class="dsec"><h4>공저자 ${collabs.length}명</h4>
      ${collabs.slice(0,12).map(c=>`<div class="ci" onclick="selectById('${c.name}')">
        <span class="cn">${esc(c.name)}</span><span class="cc">${c.cnt}편</span></div>`).join('')}
    </div>`;
  }
  const _DPG=50;
  const _renderPItems=(arr)=>arr.map(p=>{
    const tag=p.url?`a href="${p.url}" target="_blank" rel="noopener"`:'div';
    const socBadge=p.soc==='KSMI'?' · KSMI':'';
    return `<${tag} class="pi">
      <div class="pit">
        <span class="piy">${p.y}</span>
        <div>
          <div class="piti">${esc(p.t||'(제목 없음)')}</div>
          <div class="pim"><span class="${p.src==='journal'?'pij':(p.soc==='KSMI'?'pik':'pic')}">${p.src==='journal'?'학회지':'학술대회'}${socBadge}</span>${p.vol?' · Vol.'+p.vol:''}</div>
        </div>
      </div>
      ${p.url?'<div class="pilh">↗ 논문 상세 보기</div>':''}
    </${p.url?'a':'div'}>`;
  }).join('');
  const _rem=allP.length-_DPG;
  html+=`<div class="dsec"><h4>논문 ${allP.length}편</h4>
    <div id="dplist">${_renderPItems(allP.slice(0,_DPG))}</div>
    ${_rem>0?`<button class="stag-clear" id="dmore" style="width:100%;margin-top:6px;padding:6px">나머지 ${_rem}편 더 보기</button>`:''}
  </div>`;
  document.getElementById('dbody').innerHTML=html;
  if(_rem>0){
    let _shown=_DPG;
    document.getElementById('dmore').addEventListener('click',()=>{
      const next=Math.min(_shown+_DPG,allP.length);
      document.getElementById('dplist').insertAdjacentHTML('beforeend',_renderPItems(allP.slice(_shown,next)));
      _shown=next;
      const btn=document.getElementById('dmore');
      if(_shown>=allP.length&&btn)btn.remove();
      else if(btn)btn.textContent=`나머지 ${allP.length-_shown}편 더 보기`;
    });
  }
  document.getElementById('drawer').classList.add('open');
  renderLocalGraph(n.id);
}
let localMode='mesh';
function setLocalMode(mode){
  localMode=mode;
  document.querySelectorAll('#local-seg .seg-btn').forEach(b=>{
    b.classList.toggle('on',b.dataset.v===mode);
  });
  if(window._localCenter)renderLocalGraph(window._localCenter);
}
function renderLocalGraph(centerId){
  window._localCenter=centerId;
  const svgEl=document.getElementById('local-svg');
  if(!svgEl)return;
  while(svgEl.firstChild)svgEl.removeChild(svgEl.firstChild);
  // 토글 버튼 (최초 1회 생성)
  const lgEl=document.getElementById('local-graph');
  if(lgEl&&!document.getElementById('local-mode-tog')){
    const tog=document.createElement('div');
    tog.id='local-mode-tog';
    tog.innerHTML=
      '<span style="font-size:10px;color:var(--t3)">연결:</span>'+
      '<div class="seg" id="local-seg">'+
      '<div class="seg-btn" data-v="star" onclick="setLocalMode(\'star\')">직접</div>'+
      '<div class="seg-btn on" data-v="mesh" onclick="setLocalMode(\'mesh\')">전체</div>'+
      '</div>';
    lgEl.insertBefore(tog,svgEl);
  }
  const W=292,H=160;
  const neighbors=(ADJ.get(centerId)||[]).slice().sort((a,b)=>b.w-a.w).slice(0,12);
  if(!neighbors.length)return;
  const neighborIds=new Set(neighbors.map(n=>n.id));
  const nodeData=[{id:centerId,r:12,center:true},
    ...neighbors.map(n=>({id:n.id,r:Math.min(4+n.w*.5,9),center:false,w:n.w}))];
  // star 링크
  const starLinks=neighbors.map(n=>({source:centerId,target:n.id,w:n.w,cross:false}));
  // mesh 교차 링크 (이웃 ↔ 이웃, id1<id2 중복방지)
  const crossLinks=[];
  if(localMode==='mesh'){
    const nbArr=neighbors.map(n=>n.id);
    for(let i=0;i<nbArr.length;i++){
      for(let j=i+1;j<nbArr.length;j++){
        const a=nbArr[i],b=nbArr[j];
        const conn=(ADJ.get(a)||[]).find(x=>x.id===b);
        if(conn)crossLinks.push({source:a,target:b,w:conn.w,cross:true});
      }
    }
  }
  const linkData=[...starLinks,...crossLinks];
  const NS=d3.select(svgEl);
  const link=NS.append('g').selectAll('line').data(linkData).join('line')
    .attr('stroke',d=>d.cross?'#3a4a6e':'#252d48')
    .attr('stroke-width',d=>d.cross?1:Math.min(d.w*.4+.8,3))
    .attr('stroke-dasharray',d=>d.cross?'3,3':null);
  const node=NS.append('g').selectAll('circle').data(nodeData).join('circle')
    .attr('r',d=>d.r)
    .attr('fill',d=>d.center?'#5b8dee':nc(NM[d.id]?.paper_count||1))
    .attr('stroke','#090c14').attr('stroke-width',1.5)
    .style('cursor',d=>d.center?'default':'pointer');
  node.filter(d=>!d.center).on('click',(e,d)=>selectById(d.id));
  node.append('title').text(d=>d.center?d.id:`${d.id} (공저 ${d.w||0}편)`);
  const lbl=NS.append('g').selectAll('text').data(nodeData).join('text')
    .text(d=>{const n=d.id;return n.length>3?n.slice(0,3)+'…':n;})
    .attr('text-anchor','middle').attr('fill',d=>d.center?'#e2e8f8':'#7c89ae')
    .attr('font-size',d=>d.center?10:9).attr('pointer-events','none')
    .attr('dy',d=>d.r+11);
  const sim=d3.forceSimulation(nodeData)
    .force('link',d3.forceLink(linkData).id(d=>d.id).distance(d=>d.cross?42:52))
    .force('charge',d3.forceManyBody().strength(localMode==='mesh'?-110:-90))
    .force('center',d3.forceCenter(W/2,H/2))
    .force('collide',d3.forceCollide(d=>d.r+4));
  sim.on('tick',()=>{
    const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
    link.attr('x1',d=>clamp(d.source.x,0,W)).attr('y1',d=>clamp(d.source.y,0,H))
        .attr('x2',d=>clamp(d.target.x,0,W)).attr('y2',d=>clamp(d.target.y,0,H));
    node.attr('cx',d=>clamp(d.x,d.r,W-d.r)).attr('cy',d=>clamp(d.y,d.r,H-d.r));
    lbl.attr('x',d=>clamp(d.x,d.r,W-d.r)).attr('y',d=>clamp(d.y,d.r,H-d.r));
  });
  setTimeout(()=>sim.stop(),localMode==='mesh'?3200:2500);
}
function closeDrawer(){document.getElementById('drawer').classList.remove('open');selId=null;draw();}
function selectById(name){
  const n=NM[name]||{id:name,en:'',paper_count:(AP[name]||[]).length,degree:0,first_year:'',last_year:''};
  openDrawer(n);
  if(NM[name]&&NM[name].x!=null)zoomToNode(name);
}
document.getElementById('dcls').onclick=e=>{e.stopPropagation();closeDrawer();};
// Escape 키로 드로어 닫기
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer();});

// Init
renderList();
window.addEventListener('resize',()=>{resize();buildSim();});
resize();buildSim();

// ── Search ──────────────────────────────────────────────────────
const TOPIC_KW = {
  // ── 재료 계열 ──────────────────────────────────────────────────────────
  '고강도콘크리트':['고강도','고성능','HSC','HPC','초고강도','ultra-high strength','high strength','high performance concrete','고강도 콘크리트','고성능 콘크리트'],
  'UHPC':['UHPC','UHPFRC','초고성능 콘크리트','ultra-high performance concrete','reactive powder concrete','RPC','Ductal'],
  // 섬유보강: 콘크리트 믹스 내 단섬유 혼입 (재료공학). FRP 외부보강과 구분
  '섬유보강':['강섬유','SFRC','FRC','ECC','SHCC','HPFRCC','PVA 섬유','PVA fiber','PP섬유','PE섬유','폴리프로필렌 섬유','폴리에틸렌 섬유','바잘트 섬유','basalt fiber','섬유 혼입','섬유혼입률','fiber volume fraction','fiber reinforced concrete','하이브리드 섬유','hybrid fiber','단섬유','macro fiber','micro fiber'],
  '재생골재':['순환골재','재생골재','폐콘크리트','recycled aggregate','recycled concrete','순환 골재','재활용 골재'],
  '자기충전':['자기충전','SCC','self-compacting','자기다짐','고유동 콘크리트','자기충전 콘크리트','충전성','고충전','충전성능'],
  '플라이애시':['플라이애시','fly ash','flyash','석탄회','비산재','플라이 애시','포졸란','pozzolan','석탄재'],
  // 실리카퓸: 퓸/흄 표기 변형 모두 포함
  '실리카퓸':['실리카퓸','실리카 퓸','실리카흄','실리카 흄','silica fume','silica-fume','condensed silica fume','마이크로실리카','마이크로 실리카','micro silica','microsilica'],
  '슬래그':['슬래그','slag','고로슬래그','GGBS','GGBFS','고로 슬래그','blast furnace slag'],
  '경량콘크리트':['경량골재','경량콘크리트','lightweight aggregate','lightweight concrete','기포콘크리트','ALC','경량 콘크리트','경량 골재'],
  // ── 구조/설계 계열 ─────────────────────────────────────────────────────
  '내진/내풍':['내진','지진','내풍','seismic','earthquake','내진성능','지진하중','내진설계','내진 성능'],
  // FRP보강: 경화 구조물에 외부 부착하는 연속섬유 복합재 (구조보강). 단섬유 혼입과 구분
  'FRP보강':['FRP','GFRP','CFRP','AFRP','BFRP','FRP 시트','FRP시트','FRP sheet','FRP 판','FRP bar','FRP 봉','FRP 그리드','FRP rebar','탄소섬유 시트','탄소섬유시트','탄소섬유 보강','carbon fiber sheet','유리섬유 보강','아라미드','섬유강화폴리머','fiber reinforced polymer','NSM','EB-FRP','FRP 부착','FRP wrapping'],
  'PSC/PC':['PSC','프리스트레스','prestress','프리캐스트','precast','포스트텐션','프리텐션','post-tension','pre-tension','PC 보','PC 거더'],
  '합성구조':['합성구조','합성 보','합성보','합성 기둥','합성기둥','합성 바닥판','합성슬래브','합성 슬래브','SRC','강-콘크리트','steel-concrete composite','합성 교량','steel concrete composite','강합성'],
  '보-기둥접합':['접합부','joint','beam-column','보-기둥','연결부','접합 상세','보기둥 접합'],
  '교량구조':['교량','bridge','교각','pier','아치교','사장교','현수교','교량구조','교량 설계','교량 거더'],
  '전단설계':['전단강도','전단설계','전단거동','shear strength','shear design','전단철근','사인장','전단 파괴','전단 보강','punching shear','뚫림전단'],
  '피로/충격':['피로','fatigue','반복하중','충격하중','폭발하중','blast load','impact load','피로 수명','피로 균열','동적하중'],
  // PSC/PC의 거더는 교량구조에 포함되므로 '거더' 단독은 교량에만 넣음
  // ── 내구성 계열 ─────────────────────────────────────────────────────────
  '내구성':['내구성','durability','염해','황산염','ASR','알칼리골재','내구 수명','해양 환경','해양 콘크리트'],
  '균열':['균열','crack','cracking','균열폭','균열 제어','균열발생','균열 진전','crack width'],
  '염화물/탄산화':['염화물','탄산화','중성화','carbonation','chloride','염소이온','탄산화 깊이','중성화 깊이'],
  '화재':['화재','fire','내화','폭렬','spalling','고온 노출','화재 저항','화재노출','화재 후','내화성능'],
  '수축':['수축','shrinkage','크리프','creep','건조수축','자기수축','소성수축','장기변형'],
  '철근부식':['부식','corrosion','전기화학','음극방식','탈패시베이션','부식 속도','부식 전류','전기방식','방청','steel corrosion'],
  '동결융해':['동결융해','동결-융해','freeze-thaw','freeze thaw','내동해','동해저항','frost resistance'],
  // ── 공법/현장 계열 ─────────────────────────────────────────────────────
  // 보수·보강: '보강' 단독 제거 (섬유보강/FRP보강/전단보강과 충돌). 구조보수 문맥으로 특정
  '보수·보강':['보수','단면복구','보수공법','구조보강','내진보강','단면증설','단면확대','rehabilitation','retrofitting','seismic retrofit','jacketing','repair of','structural repair','유지보수','유지관리'],
  '포장콘크리트':['포장','pavement','도로포장','콘크리트포장','줄눈','교면포장','도로 포장','포장 콘크리트'],
  '터널/지하':['터널','tunnel','숏크리트','shotcrete','라이닝','lining','지하연속벽','터널 라이닝','굴착','underground'],
  // ── 디지털/환경 계열 ───────────────────────────────────────────────────
  '3D프린팅':['3D 프린팅','3D프린팅','3D printing','3D-프린팅','콘크리트 출력','프린팅 콘크리트','layer-by-layer','contour crafting','콘크리트 3D','3D 프린터','3D 출력','additive manufacturing'],
  'BIM/디지털':['BIM','구조건전성','건전성 모니터링','SHM','디지털 트윈','digital twin','structural health monitoring','안전진단','상태평가','계측 시스템','스마트 콘크리트','IoT','머신러닝','machine learning','인공지능','딥러닝','deep learning','신경망','neural network','인공신경망','데이터 기반','data-driven'],
  // 탄소중립/환경: '탄소' 단독·'carbon' 단독·'CO2' 단독 제거 (탄소섬유 오매칭). 환경성능 복합어로 특정
  '탄소중립/환경':['탄소중립','탄소저감','탄소배출','이산화탄소','CO2 배출','CO2 emission','CO2 reduction','온실가스','greenhouse gas','GHG','저탄소','low-carbon','환경영향','환경부하','environmental impact','embodied carbon','내재탄소','LCA','전과정평가','life cycle assessment','친환경','탄소발자국','carbon footprint','넷제로','net zero','cement replacement','시멘트 대체','탄소 저감','탄소나노','carbon nano'],
  '비파괴검사':['비파괴','NDT','초음파 탐상','음향방출','충격반향','impact echo','GPR','레이더 탐사','비파괴 검사','비파괴 시험','적외선 열화상','전기저항','임피던스'],
};
const TOPIC_COLORS_S=['#5b8dee','#34d399','#fb923c','#f87171','#a78bfa',
  '#38bdf8','#facc15','#f472b6','#4ade80','#e879f9',
  '#22d3ee','#fb7185','#a3e635','#c084fc','#67e8f9',
  '#fde68a','#86efac','#f9a8d4','#93c5fd','#d9f99d','#fca5a5','#c4b5fd',
  '#f59e0b','#10b981','#6366f1','#ec4899','#14b8a6','#8b5cf6','#0ea5e9','#d97706','#84cc16'];

// hexAlpha는 Trends 섹션에서 정의됨 — 여기서는 동일 함수를 재사용
function hexAlphaS(hex,a){return hexAlpha(hex,a);}

// 논문 토픽 캐시
const paperTopics={};
function getPaperTopics(p){
  if(paperTopics[p.dn])return paperTopics[p.dn];
  const text=((p.t||'')+' '+(p.te||'')).toLowerCase();
  const tags=[];
  Object.entries(TOPIC_KW).forEach(([topic,kws])=>{
    if(kws.some(k=>text.includes(k.toLowerCase())))tags.push(topic);
  });
  return(paperTopics[p.dn]=tags);
}

// 검색 상태
const SF={src:'all',soc:'all',sort:'recent',tags:new Set(),tagLogic:'or'};
let trendChart=null,searchHistory=[];

const sinp=document.getElementById('sinp');
const yrf=document.getElementById('yrf');
const yrt=document.getElementById('yrt');
const rarea=document.getElementById('rarea');
const rcnt=document.getElementById('rcnt');
const rsummary=document.getElementById('rsummary');
const stagRow=document.getElementById('stag-row');
const relRow=document.getElementById('rel-row');
const histDrop=document.getElementById('hist-drop');

// 출처 세그먼트
document.querySelectorAll('#ssoc .tseg-btn').forEach(b=>{
  b.addEventListener('click',()=>{
    document.querySelectorAll('#ssoc .tseg-btn').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); SF.soc=b.dataset.v; doSearch();
  });
});
document.querySelectorAll('#ssrc .tseg-btn').forEach(b=>{
  b.addEventListener('click',()=>{
    document.querySelectorAll('#ssrc .tseg-btn').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); SF.src=b.dataset.v; doSearch();
  });
});
// 정렬 세그먼트
document.querySelectorAll('#ssort .sort-btn').forEach(b=>{
  b.addEventListener('click',()=>{
    document.querySelectorAll('#ssort .sort-btn').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); SF.sort=b.dataset.v; doSearch();
  });
});

// 태그 AND/OR 토글
function toggleTagLogic(){
  SF.tagLogic=SF.tagLogic==='or'?'and':'or';
  const el=document.getElementById('tag-logic');
  el.textContent=SF.tagLogic.toUpperCase();
  el.classList.toggle('and',SF.tagLogic==='and');
  if(SF.tags.size>0)doSearch();
}

// ── 계층형 주제 태그 시스템 ────────────────────────────────────────────────
// 대분류 정의 (각 카테고리 → 포함 태그 목록)
const TOPIC_CATS = [
  {id:'material', label:'재료', icon:'🧱', tags:['고강도콘크리트','UHPC','섬유보강','재생골재','자기충전','플라이애시','실리카퓸','슬래그','경량콘크리트']},
  {id:'structure', label:'구조/설계', icon:'🏗️', tags:['내진/내풍','FRP보강','PSC/PC','합성구조','보-기둥접합','교량구조','전단설계','피로/충격']},
  {id:'durability', label:'내구성', icon:'🔬', tags:['내구성','균열','염화물/탄산화','화재','수축','철근부식','동결융해']},
  {id:'construction', label:'공법/현장', icon:'🔧', tags:['보수·보강','포장콘크리트','터널/지하','비파괴검사']},
  {id:'digital', label:'디지털/환경', icon:'💡', tags:['3D프린팅','BIM/디지털','탄소중립/환경']},
];
// TOPIC_KW 키 순서 인덱스 (색상 배정용)
const ALL_TOPIC_KEYS=Object.keys(TOPIC_KW);

let activeCat=null; // 현재 열린 대분류

function getTopicColor(t){
  const i=ALL_TOPIC_KEYS.indexOf(t);
  return TOPIC_COLORS_S[i>=0?i%TOPIC_COLORS_S.length:0];
}

(function buildTopicUI(){
  const catPills=document.getElementById('cat-pills');
  let catHtml='';
  TOPIC_CATS.forEach(cat=>{
    catHtml+=`<div class="cat-pill" id="cat-${cat.id}" data-cat="${cat.id}" onclick="toggleCat('${cat.id}')">${cat.icon} ${cat.label}</div>`;
  });
  catPills.innerHTML=catHtml;
  // 외부 클릭으로 드롭다운 닫기
  document.addEventListener('click',e=>{
    const dd=document.getElementById('stag-dropdown');
    if(dd.style.display!=='none'&&!dd.contains(e.target)&&!e.target.closest('.cat-pill')){
      closeCatDropdown();
    }
  });
})();

function toggleCat(catId){
  const dd=document.getElementById('stag-dropdown');
  if(activeCat===catId){closeCatDropdown();return;}
  activeCat=catId;
  document.querySelectorAll('.cat-pill').forEach(p=>p.classList.toggle('open',p.dataset.cat===catId));
  if(catId==='ai-clusters'){
    document.getElementById('dropdown-cat-label').textContent='⬡ AI 세부분야';
    document.getElementById('stag-row').innerHTML=window._acHtml||'';
    dd.style.display='block';
    return;
  }
  const cat=TOPIC_CATS.find(c=>c.id===catId);
  if(!cat)return;
  document.getElementById('dropdown-cat-label').textContent=cat.icon+' '+cat.label;
  let html='';
  cat.tags.forEach(t=>{
    const c=getTopicColor(t);
    const on=SF.tags.has(t);
    html+=`<div class="stag${on?' on':''}" data-stag="${t}" onclick="toggleSTag('${t}')" style="${on?'background:'+hexAlphaS(c,.15)+';border-color:'+c+';color:'+c:''}">
      <div class="sdot" style="background:${c}"></div>${t}
    </div>`;
  });
  document.getElementById('stag-row').innerHTML=html;
  dd.style.display='block';
}

function closeCatDropdown(){
  activeCat=null;
  document.getElementById('stag-dropdown').style.display='none';
  document.querySelectorAll('.cat-pill').forEach(p=>p.classList.remove('open'));
}

function clearAllFilters(){
  SF.tags.clear();
  SF_ac.clear();
  document.querySelectorAll('.stag,.actag').forEach(el=>{
    el.classList.remove('on');el.style.background='';el.style.borderColor='';el.style.color='';
  });
  refreshCatPills();
  doSearch();
}

function refreshCatPills(){
  TOPIC_CATS.forEach(cat=>{
    const pill=document.getElementById('cat-'+cat.id);
    if(!pill)return;
    const cnt=[...SF.tags].filter(t=>cat.tags.includes(t)).length;
    const isOpen=activeCat===cat.id;
    pill.className='cat-pill'+(isOpen?' open':'')+(cnt>0?' has-active':'');
    pill.innerHTML=`${cat.icon} ${cat.label}${cnt>0?` <span class="cat-cnt">${cnt}</span>`:''}`;
  });
  // AI 세부 pill 업데이트
  const aiPill=document.getElementById('cat-ai-clusters');
  if(aiPill){
    const cnt=SF_ac.size;
    const isOpen=activeCat==='ai-clusters';
    aiPill.className='cat-pill'+(isOpen?' open':'')+(cnt>0?' has-active':'');
    aiPill.textContent='⬡ AI 세부'+(cnt>0?` (${cnt})`:'');
  }
  // 드롭다운 내 태그 상태 업데이트
  if(activeCat&&activeCat!=='ai-clusters'){
    document.querySelectorAll('#stag-row .stag').forEach(el=>{
      const t=el.dataset.stag;
      const c=getTopicColor(t);
      const on=SF.tags.has(t);
      el.classList.toggle('on',on);
      el.style.background=on?hexAlphaS(c,.15):'';
      el.style.borderColor=on?c:'';
      el.style.color=on?c:'';
    });
  }
  // 필터 초기화 버튼 표시
  const anyActive=SF.tags.size>0||SF_ac.size>0;
  const clrBtn=document.getElementById('active-tag-clear');
  if(clrBtn)clrBtn.style.display=anyActive?'inline':'none';
}

function toggleSTag(t){
  if(SF.tags.has(t)){SF.tags.delete(t);}else{SF.tags.add(t);}
  const c=getTopicColor(t);
  const el=document.querySelector(`.stag[data-stag="${t}"]`);
  if(el){
    const on=SF.tags.has(t);
    el.classList.toggle('on',on);
    el.style.background=on?hexAlphaS(c,.15):'';
    el.style.borderColor=on?c:'';
    el.style.color=on?c:'';
  }
  refreshCatPills();
  doSearch();
}
function clearSTags(){
  SF.tags.clear();
  document.querySelectorAll('.stag').forEach(el=>{
    el.classList.remove('on');el.style.background='';el.style.borderColor='';el.style.color='';
  });
  refreshCatPills();
  doSearch();
}

// ── AI 세부분야 군집 필터 ────────────────────────────────────────────────────
const SF_ac=new Set(); // 선택된 AI 클러스터 ID 집합
const AC_COLORS=['#5b8dee','#34d399','#fb923c','#f87171','#a78bfa','#22d3ee','#fbbf24','#f472b6','#86efac','#67e8f9','#fcd34d','#c4b5fd','#6ee7b7','#fdba74'];

(function buildACTagRow(){
  if(!CLUSTERS||!CLUSTERS.clusters||!CLUSTERS.clusters.length)return;
  // AI 세부 cat-pill을 cat-pills에 추가
  const catPills=document.getElementById('cat-pills');
  if(!catPills)return;
  const pill=document.createElement('div');
  pill.id='cat-ai-clusters';
  pill.className='cat-pill';
  pill.dataset.cat='ai-clusters';
  pill.textContent='⬡ AI 세부';
  pill.setAttribute('onclick',"toggleCat('ai-clusters')");
  catPills.appendChild(pill);
  // 클러스터 태그 HTML 빌드 (toggleCat에서 stag-row에 삽입)
  let html='';
  CLUSTERS.clusters.forEach((c,i)=>{
    const col=AC_COLORS[i%AC_COLORS.length];
    html+=`<div class="actag" data-acid="${c.id}" onclick="event.stopPropagation();toggleACTag(${c.id},'${col}')">
      <div class="acdot" style="background:${col}"></div>${c.label_ko}<span class="actag-cnt">${c.count}</span>
    </div>`;
  });
  window._acHtml=html;
})();

function toggleACTag(id,col){
  if(SF_ac.has(id)){SF_ac.delete(id);}else{SF_ac.add(id);}
  const el=document.querySelector(`.actag[data-acid="${id}"]`);
  if(el){
    const on=SF_ac.has(id);
    el.classList.toggle('on',on);
    el.style.background=on?hexAlpha(col,.15):'';
    el.style.borderColor=on?col:'';
    el.style.color=on?col:'';
  }
  doSearch();
}
function clearACTags(){
  SF_ac.clear();
  document.querySelectorAll('.actag').forEach(el=>{
    el.classList.remove('on');el.style.background='';el.style.borderColor='';el.style.color='';
  });
  doSearch();
}
function getPaperCluster(p){
  if(!CLUSTERS)return null;
  return CLUSTERS.map[p.dn]??null;
}
function getClusterInfo(id){
  if(!CLUSTERS)return null;
  return CLUSTERS.clusters.find(c=>c.id===id)||null;
}

// 검색 히스토리
function addHistory(q){
  if(!q||searchHistory.includes(q))return;
  searchHistory.unshift(q);
  if(searchHistory.length>8)searchHistory.pop();
}
sinp.addEventListener('focus',()=>{
  if(!searchHistory.length){histDrop.style.display='none';return;}
  histDrop.innerHTML=searchHistory.map(h=>`<div style="padding:7px 12px;font-size:12.5px;cursor:pointer;transition:background .1s" onmousedown="setS('${h}')" onmouseover="this.style.background='var(--s3)'" onmouseout="this.style.background=''">${h}</div>`).join('');
  histDrop.style.display='block';
});
sinp.addEventListener('blur',()=>setTimeout(()=>{histDrop.style.display='none';},150));

function setS(q){sinp.value=q;histDrop.style.display='none';doSearch();}
let stm=null;
sinp.addEventListener('input',()=>{clearTimeout(stm);stm=setTimeout(doSearch,200);histDrop.style.display='none';});
yrf.addEventListener('change',doSearch);yrt.addEventListener('change',doSearch);

// 관련도 점수
function relScore(p,ql){
  if(!ql)return 0;
  const t=(p.t||'').toLowerCase();
  return (t.startsWith(ql)?10:0)+(t.split(ql).length-1)*3+((p.te||'').toLowerCase().includes(ql)?1:0);
}

function doSearch(){
  const q=sinp.value.trim();
  const ql=q.toLowerCase();
  const yf=+yrf.value||YEAR_MIN, yt=+yrt.value||YEAR_MAX;
  const empty=!q&&SF.src==='all'&&yf===YEAR_MIN&&yt===YEAR_MAX&&SF.tags.size===0&&SF_ac.size===0;

  if(empty){
    rcnt.textContent='—'; rsummary.textContent='';
    rarea.innerHTML=`<div class="nr"><div class="nri">🔍</div><p>제목이나 저자 이름을 입력해 검색하세요<br><span style="font-size:11px;color:var(--t3)">위의 주제 태그로 바로 필터링할 수도 있습니다</span></p><div class="sugbox"><div class="sg" onclick="setS('콘크리트 강도')">콘크리트 강도</div><div class="sg" onclick="setS('철근')">철근</div><div class="sg" onclick="setS('균열')">균열</div><div class="sg" onclick="setS('내구성')">내구성</div><div class="sg" onclick="setS('UHPC')">UHPC</div><div class="sg" onclick="setS('FRP')">FRP</div><div class="sg" onclick="setS('프리스트레스')">프리스트레스</div></div></div>`;
    relRow.style.display='none';
    hideTrendPanel();
    return;
  }

  if(q)addHistory(q);

  // 필터링
  let res=PAPERS.filter(p=>{
    const yr=+p.y; if(yr<yf||yr>yt)return false;
    if(SF.src!=='all'&&p.src!==SF.src)return false;
    if(SF.soc!=='all'&&(p.soc||'KCI')!==SF.soc)return false;
    if(SF.tags.size>0){
      const pt=getPaperTopics(p);
      if(SF.tagLogic==='and'){if(![...SF.tags].every(t=>pt.includes(t)))return false;}
      else{if(![...SF.tags].some(t=>pt.includes(t)))return false;}
    }
    if(SF_ac.size>0){
      const cid=getPaperCluster(p);
      if(cid===null||!SF_ac.has(cid))return false;
    }
    if(!q)return true;
    const auth=(p.a||[]).map(a=>a.n||'').join(' ');
    return(p.t&&p.t.toLowerCase().includes(ql))||(p.te&&p.te.toLowerCase().includes(ql))||auth.toLowerCase().includes(ql);
  });

  const total=res.length;

  // 정렬
  if(SF.sort==='recent')res.sort((a,b)=>(+b.y||0)-(+a.y||0));
  else if(SF.sort==='old')res.sort((a,b)=>(+a.y||0)-(+b.y||0));
  else res.sort((a,b)=>relScore(b,ql)-relScore(a,ql)||(+b.y||0)-(+a.y||0));

  // 결과 요약
  const jCnt=res.filter(p=>p.src==='journal').length;
  const cCnt=res.filter(p=>p.src==='conference').length;
  const yrFreq={};res.forEach(p=>{if(p.y)yrFreq[p.y]=(yrFreq[p.y]||0)+1;});
  const peakYr=Object.entries(yrFreq).sort((a,b)=>b[1]-a[1])[0];
  rcnt.textContent=total+'건'+(total>300?' (상위 300 표시)':'');
  rsummary.textContent=total?`학회지 ${jCnt} · 학술대회 ${cCnt}${peakYr?` · 피크 ${peakYr[0]}년(${peakYr[1]}편)`:''}`:'';

  // 키워드 트렌드 패널
  if(q&&total>0){
    renderTrendPanel(q,res,yrFreq);
  } else {
    hideTrendPanel();
  }

  // 연관 주제
  const tagFreq={};
  res.slice(0,300).forEach(p=>getPaperTopics(p).forEach(t=>{
    if(!SF.tags.has(t))tagFreq[t]=(tagFreq[t]||0)+1;
  }));
  const relTags=Object.entries(tagFreq).sort((a,b)=>b[1]-a[1]).slice(0,8);
  if(relTags.length&&q){
    let rh='<span class="rel-label">연관 주제:</span>';
    relTags.forEach(([t,cnt])=>{
      const c=getTopicColor(t)||'#7c89ae';
      rh+=`<span class="rel-kw" style="border-color:${c}33;color:${c}" onclick="toggleSTag('${t}')">${t} <span style="opacity:.55">${cnt}</span></span>`;
    });
    relRow.innerHTML=rh; relRow.style.display='flex';
  } else {relRow.style.display='none';}

  if(!total){
    rarea.innerHTML=`<div class="nr"><div class="nri">😶</div><p>"${esc(q||[...SF.tags].join(', ')||'')}"에 해당하는 논문이 없습니다</p></div>`;
    return;
  }

  const disp=res.slice(0,300);

  // 저자 카드 (이름 검색 시)
  let authorHtml='';
  if(q&&q.length>=1){
    const matched=GRAPH.nodes.filter(n=>n.id&&n.id.includes(q)||(n.en&&n.en.toLowerCase().includes(ql)))
      .sort((a,b)=>(b.paper_count||0)-(a.paper_count||0)).slice(0,5);
    if(matched.length){
      authorHtml=`<div class="sec-header">👤 저자 (${matched.length}명)</div>`;
      authorHtml+=matched.map(n=>{
        const colors=['#5b8dee','#34d399','#fb923c','#f87171','#a78bfa'];
        const c=colors[(n.id.charCodeAt(0)||0)%colors.length];
        const span=n.last_year&&n.first_year?`${n.first_year}–${n.last_year}`:n.first_year||'';
        return `<div class="acard" onclick="goToAuthor('${n.id}')">
          <div class="acard-av" style="background:${hexAlphaS(c,.18)};color:${c}">${(n.id||'?')[0]}</div>
          <div class="acard-info">
            <div class="acard-name">${hl(n.id,q)}</div>
            <div class="acard-en">${n.en||''}</div>
            <div class="acard-meta"><span>${span}</span>${n.paper_count?`<span>논문 ${n.paper_count}편</span>`:''}</div>
          </div>
          <div class="acard-badge">${n.paper_count||0}편</div>
        </div>`;
      }).join('');
    }
  }

  let paperHtml='';
  if(authorHtml)paperHtml=`<div class="sec-header" style="margin-top:12px">📄 논문 (${total}건${total>300?' · 상위 300':''})</div>`;
  paperHtml+=disp.map(p=>{
    const authSpans=(p.a||[]).filter(a=>a.n).map(a=>`<span class="pca-link" data-author="${esc(a.n)}" onclick="event.stopPropagation();event.preventDefault();goToAuthor(this.dataset.author)">${hl(a.n,q)}</span>`).join('<span class="pca-sep">, </span>');
    const auth=(p.a||[]).map(a=>a.n||'').filter(Boolean).join(', ');
    const tag=p.url?`a href="${p.url}" target="_blank" rel="noopener"`:'div';
    const ptags=getPaperTopics(p).slice(0,3);
    const cid=getPaperCluster(p);
    const ci=cid!==null?getClusterInfo(cid):null;
    const ciIdx=ci?CLUSTERS.clusters.indexOf(ci):-1;
    const ciCol=ciIdx>=0?AC_COLORS[ciIdx%AC_COLORS.length]:null;
    return `<${tag} class="pc">
      <div class="pct">${hl(p.t||'(제목 없음)',q)}</div>
      <div class="pcm">
        <span class="badge ${p.src==='journal'?'bj':(p.soc==='KSMI'?'bk':'bc')}">${p.src==='journal'?'학회지':'학술대회'}${p.soc==='KSMI'?' · KSMI':''}</span>
        <span>${p.y}년${p.m?' '+p.m+'월':''}</span>
        ${p.vol?`<span>Vol.${p.vol}${p.iss?' No.'+p.iss:''}</span>`:''}
        ${authSpans?`<span class="pca">${authSpans}</span>`:''}
        ${ptags.map(t=>`<span class="pctag">${t}</span>`).join('')}
        ${ci?`<span class="pcai" style="color:${ciCol};border-color:${ciCol}44;background:${ciCol}11" title="${ci.description||''}" onclick="event.preventDefault();toggleACTag(${ci.id},'${ciCol}')">⬡ ${ci.label_ko}</span>`:''}
        ${p.url?`<span style="color:var(--ac);margin-left:auto;font-size:11px">↗</span>`:''}</div>
    </${p.url?'a':'div'}>`;
  }).join('');

  rarea.innerHTML=authorHtml+paperHtml;
}

// 키워드 트렌드 패널
function renderTrendPanel(q,res,yrFreq){
  const allYrs=Object.keys(YEARLY).sort();
  const yData=allYrs.map(y=>yrFreq[y]||0);
  const peakYr=allYrs.reduce((p,c)=>(yrFreq[c]||0)>(yrFreq[p]||0)?c:p,allYrs[0]);
  const total=res.length;
  const jCnt=res.filter(p=>p.src==='journal').length;

  // KPI
  const kpiHtml=`
    <div class="tp-kpi"><div class="tp-kpi-v">${total}</div><div class="tp-kpi-l">총 논문</div></div>
    <div class="tp-kpi"><div class="tp-kpi-v" style="color:var(--pu)">${peakYr}</div><div class="tp-kpi-l">피크 연도</div></div>
    <div class="tp-kpi"><div class="tp-kpi-v" style="color:var(--gr)">${yrFreq[peakYr]||0}편</div><div class="tp-kpi-l">피크 편수</div></div>
    <div class="tp-kpi"><div class="tp-kpi-v" style="color:var(--ac)">${((jCnt/total)*100).toFixed(0)}%</div><div class="tp-kpi-l">학회지 비중</div></div>`;

  // 패널 HTML (차트 canvas 포함)
  let panel=document.getElementById('trend-panel');
  if(!panel){
    panel=document.createElement('div');
    panel.id='trend-panel';
    panel.className='trend-panel';
    rarea.parentElement.insertBefore(panel,rarea);
  }
  panel.className='trend-panel';
  panel.innerHTML=`
    <div class="tp-header">
      <div class="tp-title">📈 "<span style="color:var(--ac)">${esc(q)}</span>" 연도별 발행 추이</div>
      <div class="tp-close" onclick="hideTrendPanel()">✕</div>
    </div>
    <div class="tp-kpis">${kpiHtml}</div>
    <div class="tp-chart-wrap"><canvas id="trend-cvs"></canvas></div>`;

  // Chart.js 바 차트
  if(trendChart){trendChart.destroy();trendChart=null;}
  requestAnimationFrame(()=>{
    const cvs=document.getElementById('trend-cvs');
    if(!cvs)return;
    trendChart=new Chart(cvs,{type:'bar',
      data:{labels:allYrs,datasets:[{
        label:'논문 수',data:yData,
        backgroundColor:allYrs.map(y=>y===peakYr?'rgba(167,139,250,.85)':'rgba(91,141,238,.55)'),
        borderRadius:2,borderSkipped:false
      }]},
      options:{responsive:true,maintainAspectRatio:false,
        onClick:(_,items)=>{
          if(!items.length)return;
          const y=allYrs[items[0].index];
          yrf.value=y; yrt.value=y; doSearch();
        },
        plugins:{legend:{display:false},
          tooltip:{backgroundColor:'rgba(17,21,32,.95)',titleColor:'#e2e8f8',bodyColor:'#7c89ae',
            borderColor:'#252d48',borderWidth:1,
            callbacks:{label:c=>`${c.raw}편`,afterLabel:c=>{const y=allYrs[c.dataIndex];const tot=YEARLY[y]?(YEARLY[y].j||0)+(YEARLY[y].c||0):0;return tot?`전체 중 ${(c.raw/tot*100).toFixed(1)}%`:'';}}}},
        scales:{
          x:{ticks:{color:'#7c89ae',font:{size:9},maxTicksLimit:20},grid:{color:'#1e2438'}},
          y:{ticks:{color:'#7c89ae',font:{size:10}},grid:{color:'#1e2438'},beginAtZero:true}
        }
      }
    });
  });
}

function hideTrendPanel(){
  const p=document.getElementById('trend-panel');
  if(p){p.className='trend-panel collapsed';setTimeout(()=>p.remove(),300);}
  if(trendChart){trendChart.destroy();trendChart=null;}
}

// CSV 내보내기
function exportCSV(){
  const q=sinp.value.trim(),ql=q.toLowerCase();
  const yf=+yrf.value||YEAR_MIN,yt=+yrt.value||YEAR_MAX;
  const rows=PAPERS.filter(p=>{
    const yr=+p.y; if(yr<yf||yr>yt)return false;
    if(SF.src!=='all'&&p.src!==SF.src)return false;
    if(SF.tags.size>0){const pt=getPaperTopics(p);if(SF.tagLogic==='and'){if(![...SF.tags].every(t=>pt.includes(t)))return false;}else{if(![...SF.tags].some(t=>pt.includes(t)))return false;}}
    if(!q)return true;
    const auth=(p.a||[]).map(a=>a.n||'').join(' ');
    return(p.t&&p.t.toLowerCase().includes(ql))||(p.te&&p.te.toLowerCase().includes(ql))||auth.toLowerCase().includes(ql);
  });
  const header='제목,영문제목,연도,월,출처,저자,주제태그,URL';
  const lines=rows.map(p=>{
    const auth=(p.a||[]).map(a=>a.n||'').filter(Boolean).join('; ');
    const tags=getPaperTopics(p).join('; ');
    const csv=v=>`"${(v||'').toString().replace(/"/g,'""')}"`;
    return [csv(p.t),csv(p.te),p.y||'',p.m||'',p.src==='journal'?'학회지':'학술대회',csv(auth),csv(tags),csv(p.url)].join(',');
  });
  const blob=new Blob(['﻿'+header+'\n'+lines.join('\n')],{type:'text/csv;charset=utf-8'});
  const a=Object.assign(document.createElement('a'),{href:URL.createObjectURL(blob),download:`kci_${q||'all'}_${Date.now()}.csv`});
  a.click(); URL.revokeObjectURL(a.href);
}

function goToAuthor(name){
  document.querySelector('[data-tab="net"]').click();
  setTimeout(()=>{
    selectById(name);
    zoomToNode(name);
  },350);
}
function zoomToNode(name){
  const n=NM[name]; if(!n||n.x==null)return;
  const W=cvs.clientWidth||cvs.width, H=cvs.clientHeight||cvs.height;
  const k=Math.min(W,H)/120;
  const tx=W/2-n.x*k, ty=H/2-n.y*k;
  d3.select(cvs).transition().duration(650).ease(d3.easeCubicInOut)
    .call(zb.transform, d3.zoomIdentity.translate(tx,ty).scale(k));
}

// ── Trends ──────────────────────────────────────────────────────
const TOPIC_COLORS=['#5b8dee','#34d399','#fb923c','#f87171','#a78bfa',
  '#38bdf8','#facc15','#f472b6','#4ade80','#e879f9',
  '#22d3ee','#fb7185','#a3e635','#c084fc','#67e8f9',
  '#fde68a','#86efac','#f9a8d4','#93c5fd','#d9f99d','#fca5a5','#c4b5fd'];

// 트렌드 필터 전역 상태
const TF={src:'all',yf:YEAR_MIN,yt:YEAR_MAX,unit:'pct',hmGran:'5year'};

let topicChart=null,yrChart=null,uaChart=null,coChart=null;
const activeTopics=new Set();
const MAX_TOPICS=8;

function buildTrends(){
  tBuilt=true;
  // 필터바 이벤트
  document.querySelectorAll('#tsrc .tseg-btn').forEach(b=>{
    b.addEventListener('click',()=>{
      document.querySelectorAll('#tsrc .tseg-btn').forEach(x=>x.classList.remove('on'));
      b.classList.add('on'); TF.src=b.dataset.v; renderAll();
    });
  });
  document.querySelectorAll('#tunit .tseg-btn').forEach(b=>{
    b.addEventListener('click',()=>{
      document.querySelectorAll('#tunit .tseg-btn').forEach(x=>x.classList.remove('on'));
      b.classList.add('on'); TF.unit=b.dataset.v; renderAll();
    });
  });
  document.querySelectorAll('#hmgran .tseg-btn').forEach(b=>{
    b.addEventListener('click',()=>{
      document.querySelectorAll('#hmgran .tseg-btn').forEach(x=>x.classList.remove('on'));
      b.classList.add('on'); TF.hmGran=b.dataset.v; buildHeatmap();
    });
  });
  const tyrf=document.getElementById('tyrf'),tyrt=document.getElementById('tyrt');
  const tyrfv=document.getElementById('tyrfv'),tyrtv=document.getElementById('tyrtv');
  tyrf.addEventListener('input',()=>{
    if(+tyrf.value>+tyrt.value)tyrf.value=tyrt.value; // clamp: from ≤ to
    TF.yf=+tyrf.value;tyrfv.textContent=tyrf.value;renderAll();
  });
  tyrt.addEventListener('input',()=>{
    if(+tyrt.value<+tyrf.value)tyrt.value=tyrf.value; // clamp: to ≥ from
    TF.yt=+tyrt.value;tyrtv.textContent=tyrt.value;renderAll();
  });
  document.getElementById('topicSort').addEventListener('change',e=>sortTopics(e.target.value));

  // 초기 활성 토픽 (총량 상위 8개)
  const allTopics=TOPICS.topics;
  const topicTotals=allTopics.map(t=>({t,sum:TOPICS.years.reduce((a,y)=>a+(TOPICS.data[t][y]||0),0)}))
    .sort((a,b)=>b.sum-a.sum);
  topicTotals.slice(0,MAX_TOPICS).forEach(x=>activeTopics.add(x.t));

  renderTopicToggles(allTopics);
  renderAll();
  renderGrowthRanking();
  buildHeatmap();
}

// CAGR 계산 (최근 5년)
function calcCagr(topic){
  const yrs=TOPICS.years;
  const yt=TOPICS.year_totals;
  const recent=yrs.slice(-6);
  const v0=yt[recent[0]]>0?(TOPICS.data[topic][recent[0]]||0)/yt[recent[0]]:0;
  const v1=yt[recent[recent.length-1]]>0?(TOPICS.data[topic][recent[recent.length-1]]||0)/yt[recent[recent.length-1]]:0;
  if(v0<=0)return v1>0?999:0;
  return Math.pow(v1/v0,1/5)-1;
}

function sortTopics(by){
  const allTopics=[...TOPICS.topics];
  const yt=TOPICS.year_totals;
  if(by==='total'){
    allTopics.sort((a,b)=>TOPICS.years.reduce((s,y)=>s+(TOPICS.data[b][y]||0),0)-TOPICS.years.reduce((s,y)=>s+(TOPICS.data[a][y]||0),0));
  } else if(by==='recent'){
    allTopics.sort((a,b)=>calcCagr(b)-calcCagr(a));
  } else {
    allTopics.sort((a,b)=>a.localeCompare(b,'ko'));
  }
  renderTopicToggles(allTopics);
}

function renderTopicToggles(orderedTopics){
  const toggleBox=document.getElementById('topic-toggles');
  toggleBox.innerHTML=orderedTopics.map(t=>{
    const i=TOPICS.topics.indexOf(t);
    const c=TOPIC_COLORS[i%TOPIC_COLORS.length];
    const on=activeTopics.has(t);
    const cagr=calcCagr(t);
    const cagrStr=cagr===999?'신규':cagr>0.02?`+${(cagr*100).toFixed(0)}%`:cagr<-0.02?`${(cagr*100).toFixed(0)}%`:'';
    const cagrCol=cagr>0.02?'var(--gr)':cagr<-0.02?'var(--rd)':'';
    return `<div class="ttog${on?'':' off'}" data-topic="${t}" style="border-color:${c};color:${c}" onclick="toggleTopic('${t}')">
      <div class="dot" style="background:${c}"></div>${t}${cagrStr?`<span class="cagr" style="color:${cagrCol}">${cagrStr}</span>`:''}
    </div>`;
  }).join('');
}

function toggleTopic(topic){
  if(activeTopics.has(topic)){
    activeTopics.delete(topic);
  } else {
    if(activeTopics.size>=MAX_TOPICS){
      const hint=document.getElementById('topic-hint');
      hint.textContent=`최대 ${MAX_TOPICS}개까지 선택 가능`;
      hint.style.color='var(--rd)';
      setTimeout(()=>{hint.style.color='';hint.textContent=`최대 ${MAX_TOPICS}개 선택`;},1500);
      return;
    }
    activeTopics.add(topic);
  }
  const el=document.querySelector(`.ttog[data-topic="${topic}"]`);
  if(el)el.classList.toggle('off',!activeTopics.has(topic));
  renderTopicChart();
}

// 필터 적용된 연도 목록 반환
function filteredYears(){
  return TOPICS.years.filter(y=>+y>=TF.yf&&+y<=TF.yt);
}
// 필터 적용된 YEARLY 데이터
function filteredYearly(){
  const yrs=Object.keys(YEARLY).sort().filter(y=>+y>=TF.yf&&+y<=TF.yt);
  return {yrs, jD:yrs.map(y=>(TF.src==='conference'?0:YEARLY[y].j||0)),
                 cD:yrs.map(y=>(TF.src==='journal'?0:YEARLY[y].c||0)),
                 uD:yrs.map(y=>YEARLY[y].ua||0)};
}

function renderAll(){
  renderYearlyChart();
  renderTopicChart();
  renderGrowthRanking(); // 연도 필터 변경 시에도 갱신
}

function renderYearlyChart(){
  const {yrs,jD,cD,uD}=filteredYearly();
  const totD=yrs.map((_,i)=>jD[i]+cD[i]);

  // KPI 계산
  const maxIdx=totD.indexOf(Math.max(...totD));
  const last=totD[totD.length-1]||0,prev=totD[totD.length-2]||1;
  const yoy=last-prev;const yoyP=(yoy/prev*100).toFixed(1);
  const avg5=totD.slice(-5).reduce((a,b)=>a+b,0)/Math.min(5,totD.length);
  const kpiEl=document.getElementById('yr-kpis');
  if(kpiEl){
    const yoyC=yoy>0?'up':yoy<0?'dn':'flat';
    const yoySign=yoy>0?'+':'';
    kpiEl.innerHTML=`
      <div class="kpi"><div class="kpi-v" style="color:var(--ac)">${totD.reduce((a,b)=>a+b,0)}</div><div class="kpi-l">기간 내 총 논문</div></div>
      <div class="kpi"><div class="kpi-v" style="color:var(--pu)">${yrs[maxIdx]||'—'}</div><div class="kpi-l">최다 발행 연도</div><div class="kpi-d flat">${Math.max(...totD)}편</div></div>
      <div class="kpi"><div class="kpi-v" style="color:var(--gr)">${avg5.toFixed(0)}</div><div class="kpi-l">최근 5년 연평균</div></div>
      <div class="kpi"><div class="kpi-v" style="color:${yoy>=0?'var(--gr)':'var(--rd)'}">${yoySign}${yoyP}%</div><div class="kpi-l">전년 대비</div><div class="kpi-d ${yoyC}">${yoySign}${yoy}편</div></div>`;
  }

  // YoY 성장률 라인 (보조축)
  const yoyArr=totD.map((v,i)=>i===0?null:(v-(totD[i-1]||0))/(totD[i-1]||1)*100);
  const base={responsive:true,maintainAspectRatio:false,
    plugins:{legend:{labels:{color:'#7c89ae',font:{size:11},boxWidth:12}}},
    scales:{x:{ticks:{color:'#7c89ae',font:{size:10},maxTicksLimit:18},grid:{color:'#1e2438'}}}};

  if(yrChart){yrChart.destroy();}
  yrChart=new Chart('cyr',{type:'bar',
    data:{labels:yrs,datasets:[
      {label:'학회지',data:jD,backgroundColor:'rgba(91,141,238,.75)',borderRadius:2,stack:'s',yAxisID:'yL'},
      {label:'학술대회',data:cD,backgroundColor:'rgba(52,211,153,.65)',borderRadius:2,stack:'s',yAxisID:'yL'},
      {label:'전년비(%)',data:yoyArr,type:'line',borderColor:'#fb923c',backgroundColor:'transparent',
       tension:.4,pointRadius:2,pointBackgroundColor:'#fb923c',borderWidth:1.5,yAxisID:'yR',spanGaps:true}
    ]},
    options:{...base,
      interaction:{mode:'index',intersect:false},
      plugins:{...base.plugins,
        tooltip:{backgroundColor:'rgba(17,21,32,.95)',titleColor:'#e2e8f8',bodyColor:'#7c89ae',
          borderColor:'#252d48',borderWidth:1,
          callbacks:{label:c=>c.dataset.yAxisID==='yR'?`  전년비: ${(c.raw||0).toFixed(1)}%`:`  ${c.dataset.label}: ${c.raw||0}편`}}},
      scales:{...base.scales,
        x:{...base.scales.x,stacked:true},
        yL:{stacked:true,ticks:{color:'#7c89ae',font:{size:10}},grid:{color:'#1e2438'},
            title:{display:true,text:'논문 수',color:'#7c89ae',font:{size:10}}},
        yR:{position:'right',ticks:{color:'#fb923c',font:{size:9},callback:v=>`${v?.toFixed(0)||0}%`},
            grid:{display:false},title:{display:true,text:'전년비',color:'#fb923c',font:{size:9}}}
      }}
  });
}

function renderTopicChart(){
  const years=filteredYears();
  const ytotals=TOPICS.year_totals;
  const allTopics=TOPICS.topics;
  const usePct=TF.unit==='pct';

  const smooth=(arr,w=1)=>arr.map((_,i)=>{
    const s=arr.slice(Math.max(0,i-w),i+w+1).filter(v=>v!=null);
    return s.length?s.reduce((a,b)=>a+b,0)/s.length:0;
  });

  const datasets=allTopics.map((t,i)=>{
    if(!activeTopics.has(t))return null;
    const raw=years.map(y=>{
      const cnt=TOPICS.data[t][y]||0;
      if(usePct){const tot=ytotals[y]||1;return cnt/tot*100;}
      // src 필터 적용
      if(TF.src==='journal')return YEARLY[y]?(TOPICS.data[t][y]||0):0; // 근사값
      return cnt;
    });
    const data=smooth(raw,1);
    const c=TOPIC_COLORS[i%TOPIC_COLORS.length];
    return{label:t,data,borderColor:c,backgroundColor:c+'18',
           fill:false,tension:.4,pointRadius:0,pointHoverRadius:5,borderWidth:2.5};
  }).filter(Boolean);

  const yLabel=usePct?'비중(%)':'건수';
  const yCb=usePct?v=>v.toFixed(1)+'%':v=>v.toFixed(0)+'편';

  if(topicChart){topicChart.destroy();}
  topicChart=new Chart('ctopic',{type:'line',data:{labels:years,datasets},
    options:{responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{display:false},
        tooltip:{backgroundColor:'rgba(17,21,32,.95)',titleColor:'#e2e8f8',
          bodyColor:'#7c89ae',borderColor:'#252d48',borderWidth:1,
          callbacks:{
            label:c=>`  ${c.dataset.label}: ${usePct?(c.raw||0).toFixed(1)+'%':(c.raw||0).toFixed(0)+'편'}`,
            afterBody:items=>{
              const y=years[items[0].dataIndex];
              return usePct?[`  (총 ${TOPICS.year_totals[y]||0}편)`]:[];
            }
          }
        }
      },
      scales:{
        x:{ticks:{color:'#7c89ae',font:{size:10},maxTicksLimit:18},grid:{color:'#1e2438'}},
        y:{ticks:{color:'#7c89ae',font:{size:10},callback:yCb},
           grid:{color:'#1e2438'},
           title:{display:true,text:yLabel,color:'#7c89ae',font:{size:10}}}
      }
    }
  });
}

function renderGrowthRanking(){
  const allTopics=TOPICS.topics;
  const ranked=allTopics.map(t=>({t,cagr:calcCagr(t)})).sort((a,b)=>b.cagr-a.cagr);
  const rise=ranked.filter(x=>x.cagr>0).slice(0,6);
  const fall=ranked.filter(x=>x.cagr<0).sort((a,b)=>a.cagr-b.cagr).slice(0,6);

  function renderList(items,el,isRise){
    const maxV=Math.max(...items.map(x=>Math.abs(x.cagr)));
    el.innerHTML=items.map((x,i)=>{
      const idx=TOPICS.topics.indexOf(x.t);
      const c=TOPIC_COLORS[idx%TOPIC_COLORS.length];
      const pct=x.cagr===999?'신규':`${isRise?'+':''}${(x.cagr*100).toFixed(0)}%`;
      const bw=Math.round(Math.min(Math.abs(x.cagr)/maxV,1)*56);
      return `<div class="rank-item" onclick="activateTopic('${x.t}')">
        <span class="rank-no">${i+1}</span>
        <span class="rank-name">${x.t}</span>
        <div class="rank-bar-wrap"><div class="rank-bar" style="width:${bw}px;background:${c}"></div></div>
        <span class="rank-val" style="color:${isRise?'var(--gr)':'var(--rd)'}">${pct}</span>
      </div>`;
    }).join('');
  }
  const rEl=document.getElementById('rank-rise'),fEl=document.getElementById('rank-fall');
  if(rEl)renderList(rise,rEl,true);
  if(fEl)renderList(fall,fEl,false);
}

function activateTopic(t){
  if(!activeTopics.has(t)){
    if(activeTopics.size>=MAX_TOPICS)activeTopics.delete([...activeTopics][0]);
    activeTopics.add(t);
    renderTopicToggles(TOPICS.topics);
    renderTopicChart();
  }
}

function buildHeatmap(){
  const allTopics=TOPICS.topics;
  const years=TOPICS.years.filter(y=>+y>=TF.yf&&+y<=TF.yt);
  const ytotals=TOPICS.year_totals;
  const gran=TF.hmGran;

  let periods;
  if(gran==='year'){
    periods=years;
  } else {
    periods=[];
    const minY=+years[0]||1989;
    const maxY=+years[years.length-1]||2026;
    for(let y=Math.floor(minY/5)*5;y<=maxY;y+=5)periods.push(String(y));
  }

  // 데이터 집계
  const pdata={},pcnt={};
  for(const t of allTopics){
    pdata[t]={};pcnt[t]={};
    for(const p of periods){
      let cnt=0,tot=0;
      if(gran==='year'){
        cnt=TOPICS.data[t][p]||0;tot=ytotals[p]||0;
      } else {
        for(let y=+p;y<+p+5;y++){const ys=String(y);cnt+=(TOPICS.data[t][ys]||0);tot+=(ytotals[ys]||0);}
      }
      pdata[t][p]=tot>0?cnt/tot*100:0;
      pcnt[t][p]=cnt;
    }
  }

  let maxVal=0;
  for(const t of allTopics)for(const p of periods)if(pdata[t][p]>maxVal)maxVal=pdata[t][p];

  const cellW=gran==='year'?14:20,cellH=16,labelW=120;
  const wrap=document.getElementById('hmap');

  let html=`<div style="display:flex;flex-direction:column;gap:1px;min-width:${labelW+periods.length*(cellW+1)}px">`;
  // 헤더
  html+=`<div style="display:flex;margin-left:${labelW}px;gap:1px">`;
  for(const p of periods){
    const lbl=gran==='5year'?p+'s':p;
    html+=`<div style="width:${cellW}px;font-size:10px;color:#3a4560;text-align:center;writing-mode:vertical-rl;transform:rotate(180deg);padding:3px 0;height:${gran==='year'?28:22}px">${lbl}</div>`;
  }
  html+='</div>';

  for(let ti=0;ti<allTopics.length;ti++){
    const t=allTopics[ti];
    const c=TOPIC_COLORS[ti%TOPIC_COLORS.length];
    const isActive=activeTopics.has(t);
    html+=`<div style="display:flex;align-items:center;gap:1px">`;
    html+=`<div style="width:${labelW}px;font-size:10px;color:${isActive?'#e2e8f8':'#7c89ae'};
      text-align:right;padding-right:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
      cursor:pointer;font-weight:${isActive?'600':'400'}"
      onclick="activateTopic('${t}')" title="${t}">${t}</div>`;
    for(const p of periods){
      const v=pdata[t][p];const cnt2=pcnt[t][p];
      const alpha=maxVal>0?Math.min(v/maxVal,1):0;
      const bg=hexAlpha(c,0.05+alpha*0.9);
      const periodLabel=gran==='5year'?`${p}–${+p+4}년`:`${p}년`;
      html+=`<div class="hmap-cell" style="width:${cellW}px;height:${cellH}px;background:${bg}"
        onmouseenter="showHmapTip(event,'${t}','${periodLabel}',${v.toFixed(1)},${cnt2})"
        onmouseleave="document.getElementById('tip').style.opacity='0'"></div>`;
    }
    html+='</div>';
  }
  // 총 논문 수 행
  html+=`<div style="display:flex;align-items:center;gap:1px;margin-top:4px;border-top:1px solid #1e2438;padding-top:4px">`;
  html+=`<div style="width:${labelW}px;font-size:10px;color:var(--t3);text-align:right;padding-right:8px">총 논문 수</div>`;
  const maxTot=Math.max(...periods.map(p=>{
    if(gran==='year')return ytotals[p]||0;
    let s=0;for(let y=+p;y<+p+5;y++)s+=ytotals[String(y)]||0;return s;
  }));
  for(const p of periods){
    let tot=0;
    if(gran==='year'){tot=ytotals[p]||0;}
    else{for(let y=+p;y<+p+5;y++)tot+=ytotals[String(y)]||0;}
    const alpha2=maxTot>0?tot/maxTot:0;
    html+=`<div class="hmap-cell" style="width:${cellW}px;height:${cellH}px;background:rgba(124,137,174,${(0.08+alpha2*0.6).toFixed(2)})"
      onmouseenter="showHmapTip(event,'총 논문','${gran==='5year'?p+'–'+(+p+4)+'년':p+'년'}',null,${tot})"
      onmouseleave="document.getElementById('tip').style.opacity='0'"></div>`;
  }
  html+='</div></div>';
  wrap.innerHTML=html;

  // 활동 저자·평균 공저자 차트
  const {yrs,uD}=filteredYearly();
  // 평균 저자 수 계산
  const coD=yrs.map(y=>{
    const ps=PAPERS.filter(p=>String(p.y)===y&&(TF.src==='all'||(TF.src==='journal'&&p.src==='journal')||(TF.src==='conference'&&p.src==='conference')));
    if(!ps.length)return null;
    return ps.reduce((s,p)=>s+(p.a||[]).length,0)/ps.length;
  });
  const baseOpts={responsive:true,maintainAspectRatio:false,
    interaction:{mode:'index',intersect:false},
    plugins:{legend:{labels:{color:'#7c89ae',font:{size:11},boxWidth:12}},
      tooltip:{backgroundColor:'rgba(17,21,32,.95)',titleColor:'#e2e8f8',bodyColor:'#7c89ae',borderColor:'#252d48',borderWidth:1}},
    scales:{x:{ticks:{color:'#7c89ae',font:{size:10},maxTicksLimit:16},grid:{color:'#1e2438'}},
            y:{ticks:{color:'#7c89ae',font:{size:10}},grid:{color:'#1e2438'}}}};
  if(uaChart){uaChart.destroy();}
  uaChart=new Chart('cua',{type:'line',data:{labels:yrs,datasets:[{label:'활동 저자 수',data:uD,
    borderColor:'#fb923c',backgroundColor:'rgba(251,146,60,.12)',fill:true,tension:.35,
    pointRadius:2,pointBackgroundColor:'#fb923c'}]},options:baseOpts});
  if(coChart){coChart.destroy();}
  coChart=new Chart('cco',{type:'line',data:{labels:yrs,datasets:[{label:'논문당 평균 저자 수',data:coD,
    borderColor:'#a78bfa',backgroundColor:'rgba(167,139,250,.12)',fill:true,tension:.4,
    pointRadius:2,pointBackgroundColor:'#a78bfa',spanGaps:true}]},
    options:{...baseOpts,scales:{...baseOpts.scales,y:{...baseOpts.scales.y,
      ticks:{...baseOpts.scales.y.ticks,callback:v=>v?v.toFixed(1)+'명':''},
      title:{display:true,text:'명/논문',color:'#7c89ae',font:{size:10}}}}}});
}

function hexAlpha(hex,a){
  const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${Math.max(0,Math.min(1,a)).toFixed(2)})`;
}
function showHmapTip(e,topic,period,pct,cnt){
  const tip=document.getElementById('tip');
  tip.innerHTML=`<b>${topic}</b><br>${period}${pct!=null?`<br>비중: <b>${pct}%</b>`:''}<br>논문: <b>${cnt}편</b>`;
  tip.style.opacity='1';
  // position:fixed — clientX/Y가 viewport 기준으로 바로 사용됨
  let x=e.clientX+14,y=e.clientY-60;
  if(x+220>window.innerWidth)x=e.clientX-230;
  if(y<0)y=e.clientY+10;
  tip.style.left=x+'px';tip.style.top=y+'px';
}

// Stats
function buildStats(){
  sBuilt=true;
  // ── 파생 인사이트 ──────────────────────────────────────────────────
  (function(){
    const el=document.getElementById('stat-insights');
    if(!el)return;
    const yrs=TOPICS.years, last5=yrs.slice(-5), prev5=yrs.slice(-10,-5);
    const growth=TOPICS.topics.map(t=>{
      const s=prev5.reduce((a,y)=>a+(TOPICS.data[t][y]||0),0)||1;
      const e=last5.reduce((a,y)=>a+(TOPICS.data[t][y]||0),0);
      return{t,pct:Math.round((e/s-1)*100)};
    }).filter(x=>!isNaN(x.pct)).sort((a,b)=>b.pct-a.pct);
    const top3=growth.slice(0,3).map(x=>`<span style="color:var(--gr)">↑${x.pct}%</span> ${x.t}`).join(' &nbsp;·&nbsp; ');
    const allYrs=Object.entries(YEARLY).map(([y,d])=>({y,n:d.j+(d.c||0)})).sort((a,b)=>b.n-a.n);
    const peak=allYrs[0];
    const avgCo=Object.entries(YEARLY).sort((a,b)=>+a[0]-+b[0]).slice(-5).map(([y,d])=>{
      const ps=PAPERS.filter(p=>p.y==y);
      const s=ps.reduce((a,p)=>(a+(p.a||[]).length),0);
      return(s/Math.max(ps.length,1)).toFixed(1);
    });
    el.innerHTML=`<div class="card" style="padding:12px 16px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
      <div><div style="font-size:11px;color:var(--t3);margin-bottom:4px">📈 최근 5년 급성장 주제</div><div style="font-size:13px">${top3}</div></div>
      <div><div style="font-size:11px;color:var(--t3);margin-bottom:4px">🏆 역대 최다 발행 연도</div><div style="font-size:13px"><b>${peak.y}년</b> <span style="color:var(--t2)">(${peak.n}편)</span></div></div>
      <div><div style="font-size:11px;color:var(--t3);margin-bottom:4px">👥 최근 5년 평균 공저자</div><div style="font-size:13px">${avgCo.join(' → ')} 명</div></div>
    </div>`;
  })();
  const topBw=GRAPH.nodes.slice().sort((a,b)=>(b.betweenness||0)-(a.betweenness||0)).slice(0,15);
  const maxBw=topBw[0].betweenness||1;
  document.getElementById('bwlist').innerHTML=`
  <table class="rt"><thead><tr><th>#</th><th>이름</th><th>영문</th><th>논문</th><th>중심성</th></tr></thead><tbody>
  ${topBw.map((n,i)=>`<tr><td class="rank">${i+1}</td>
    <td><span class="al" data-name="${n.id}">${n.id}</span></td>
    <td class="dim">${n.en||''}</td><td class="num">${n.paper_count}</td>
    <td><div class="bwb"><div class="bwbar" style="width:${Math.round(n.betweenness/maxBw*70)}px"></div>
      <span style="font-size:10px;color:var(--t2)">${(n.betweenness||0).toFixed(4)}</span></div></td>
  </tr>`).join('')}
  </tbody></table>`;
  document.querySelectorAll('#bwlist .al').forEach(el=>{
    el.addEventListener('click',()=>{
      document.querySelector('[data-tab="net"]').click();
      setTimeout(()=>selectById(el.dataset.name),200);
    });
  });
}
document.querySelectorAll('#pstats .al').forEach(el=>{
  el.addEventListener('click',()=>{
    document.querySelector('[data-tab="net"]').click();
    setTimeout(()=>selectById(el.dataset.name),200);
  });
});
"""

    # JS에 JSON 데이터 주입
    JS_final = JS\
        .replace('__GRAPH__',    j_graph)\
        .replace('__PAPERS__',   j_papers)\
        .replace('__YEARLY__',   j_yearly)\
        .replace('__AP__',       j_ap)\
        .replace('__TOPICS__',   j_topics)\
        .replace('__CLUSTERS__', j_clusters)\
        .replace('__YMIN__',     str(year_min))\
        .replace('__YMAX__',     str(year_max))

    return (
        '<!DOCTYPE html>\n'
        '<html lang="ko">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>KCI 콘크리트학회 논문 분석</title>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>\n'
        f'<style>{CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        + BODY +
        f'\n<script>{JS_final}</script>\n'
        '</body>\n'
        '</html>'
    )

if __name__ == '__main__':
    main()
