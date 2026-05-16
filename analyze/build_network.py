"""
저자 공저 네트워크 구축
========================
수집된 JSON 메타데이터에서 저자 간 공저 관계를 파악해
NetworkX 그래프를 생성하고 다양한 형식으로 내보냅니다.

출력:
    network/graph.graphml     → Gephi, yEd 등에서 열 수 있음
    network/graph.gexf        → Gephi 전용 (연도 타임라인 지원)
    network/graph_d3.json     → 웹 대시보드용 D3.js 형식
    network/stats.json        → 저자별 통계
    network/top_authors.txt   → 논문 수 / 중심성 기준 상위 저자

실행:
    python3 analyze/build_network.py
    python3 analyze/build_network.py --min-papers 2   # 2편 이상 저자만
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).parent.parent
META_DIR = ROOT / "meta"
OUT_DIR = ROOT / "network"


# ── 데이터 로드 ───────────────────────────────────────────────────────────────

def load_papers() -> list[dict]:
    papers = []
    for source in ("journal", "conference"):
        meta_dir = META_DIR / source
        if not meta_dir.exists():
            continue
        for jf in sorted(meta_dir.glob("*.json")):
            d = json.loads(jf.read_text(encoding="utf-8"))
            d["_source"] = source
            papers.append(d)
    return papers


def extract_real_title(raw: str) -> str:
    """제목에서 쓰레기 텍스트 제거 (fix_data.py 실행 전 대비)"""
    m = re.match(r"^(.+?)원문보기", raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


# ── 그래프 구축 ───────────────────────────────────────────────────────────────

def build_graph(papers: list[dict], min_papers: int = 1) -> nx.Graph:
    """
    공저 네트워크 그래프 구축
    - 노드: 저자 (한국어 이름 기준)
    - 엣지: 같은 논문에 공저한 경우
    - 노드 속성: paper_count, en_name, years
    - 엣지 속성: weight(공동 논문 수), papers(논문 목록)
    """
    # 저자별 논문 목록
    author_papers: dict[str, list[dict]] = defaultdict(list)
    # 저자 영문 이름 매핑 (가장 많이 등장한 것 선택)
    author_en_names: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for paper in papers:
        authors = paper.get("authors", [])
        # 편집부, 단독 저자가 아닌 논문
        real_authors = [
            a for a in authors
            if a.get("ko") and a["ko"] not in ("편집부", "편집위원회")
        ]
        if not real_authors:
            continue

        year = paper.get("year", "")
        title = extract_real_title(paper.get("title_ko", ""))
        dn = paper.get("dn", "")

        for a in real_authors:
            ko = a["ko"]
            en = a.get("en", "")
            author_papers[ko].append({
                "dn": dn,
                "title": title,
                "year": year,
                "source": paper.get("source", ""),
            })
            if en:
                author_en_names[ko][en] += 1

    # min_papers 필터
    valid_authors = {
        ko for ko, plist in author_papers.items()
        if len(plist) >= min_papers
    }
    print(f"  유효 저자: {len(valid_authors)}명 (논문 {min_papers}편 이상)")

    G = nx.Graph()

    # 노드 추가
    for ko in valid_authors:
        plist = author_papers[ko]
        years = sorted(set(p["year"] for p in plist if p["year"]))
        # 가장 많이 나온 영문 이름 선택
        en_name = ""
        if author_en_names[ko]:
            en_name = max(author_en_names[ko], key=author_en_names[ko].get)

        G.add_node(
            ko,
            en_name=en_name,
            paper_count=len(plist),
            years=",".join(years),
            first_year=years[0] if years else "",
            last_year=years[-1] if years else "",
        )

    # 엣지 추가 (공저 관계)
    for paper in papers:
        authors = paper.get("authors", [])
        real_authors = [
            a["ko"] for a in authors
            if a.get("ko")
            and a["ko"] not in ("편집부", "편집위원회")
            and a["ko"] in valid_authors
        ]
        if len(real_authors) < 2:
            continue

        title = extract_real_title(paper.get("title_ko", ""))
        year = paper.get("year", "")
        dn = paper.get("dn", "")

        for a1, a2 in combinations(real_authors, 2):
            if G.has_edge(a1, a2):
                G[a1][a2]["weight"] += 1
                G[a1][a2]["papers"].append(dn)
            else:
                G.add_edge(a1, a2, weight=1, papers=[dn], first_year=year)

    return G


# ── 통계 계산 ─────────────────────────────────────────────────────────────────

def compute_stats(G: nx.Graph) -> dict[str, dict]:
    print("  중심성 계산 중...")
    degree_cent = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)

    try:
        eigenvector = nx.eigenvector_centrality(G, weight="weight", max_iter=500)
    except nx.PowerIterationFailedConvergence:
        eigenvector = {n: 0.0 for n in G.nodes()}

    stats = {}
    for node in G.nodes(data=True):
        name = node[0]
        attrs = node[1]
        stats[name] = {
            "ko": name,
            "en": attrs.get("en_name", ""),
            "paper_count": attrs.get("paper_count", 0),
            "years": attrs.get("years", ""),
            "first_year": attrs.get("first_year", ""),
            "last_year": attrs.get("last_year", ""),
            "degree": G.degree(name),
            "degree_centrality": round(degree_cent.get(name, 0), 4),
            "betweenness_centrality": round(betweenness.get(name, 0), 6),
            "eigenvector_centrality": round(eigenvector.get(name, 0), 6),
            "collaborator_count": G.degree(name),
        }

    return stats


# ── 내보내기 ──────────────────────────────────────────────────────────────────

def export_graphml(G: nx.Graph, path: Path) -> None:
    """Gephi, yEd 등에서 열 수 있는 GraphML"""
    # papers 리스트를 문자열로 변환 (GraphML은 리스트 속성 미지원)
    G2 = G.copy()
    for u, v, data in G2.edges(data=True):
        G2[u][v]["papers"] = ",".join(data.get("papers", []))
    nx.write_graphml(G2, str(path))
    print(f"  → {path}")


def export_gexf(G: nx.Graph, path: Path) -> None:
    """Gephi GEXF (타임라인 지원)"""
    G2 = G.copy()
    for u, v, data in G2.edges(data=True):
        G2[u][v]["papers"] = ",".join(data.get("papers", []))
    nx.write_gexf(G2, str(path))
    print(f"  → {path}")


def export_d3_json(G: nx.Graph, stats: dict, path: Path) -> None:
    """
    D3.js force-directed graph 형식
    {"nodes": [...], "links": [...]}
    """
    nodes = []
    for name, s in stats.items():
        nodes.append({
            "id": name,
            "en": s["en"],
            "paper_count": s["paper_count"],
            "degree": s["degree"],
            "betweenness": s["betweenness_centrality"],
            "eigenvector": s["eigenvector_centrality"],
            "first_year": s["first_year"],
            "last_year": s["last_year"],
            "years": s["years"],
        })

    links = []
    for u, v, data in G.edges(data=True):
        links.append({
            "source": u,
            "target": v,
            "weight": data.get("weight", 1),
            "paper_count": data.get("weight", 1),
        })

    data = {"nodes": nodes, "links": links}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {path}")


def export_top_authors(stats: dict, path: Path, top_n: int = 50) -> None:
    """상위 저자 텍스트 보고서"""
    lines = ["=" * 70]
    lines.append(f"  KCI 콘크리트학회 저자 네트워크 — 상위 저자 (Top {top_n})")
    lines.append("=" * 70)

    # 논문 수 기준
    by_papers = sorted(stats.values(), key=lambda x: x["paper_count"], reverse=True)
    lines.append("\n[논문 수 Top 50]")
    lines.append(f"{'순위':>4}  {'저자(한국어)':12}  {'저자(영문)':25}  {'논문수':>5}  {'공저자수':>6}  {'기간'}")
    lines.append("-" * 70)
    for i, s in enumerate(by_papers[:top_n], 1):
        period = f"{s['first_year']}~{s['last_year']}" if s["first_year"] else "-"
        lines.append(
            f"{i:>4}  {s['ko']:12}  {s['en']:25}  {s['paper_count']:>5}  "
            f"{s['collaborator_count']:>6}  {period}"
        )

    # 매개 중심성 기준
    by_betweenness = sorted(stats.values(), key=lambda x: x["betweenness_centrality"], reverse=True)
    lines.append("\n\n[매개 중심성(Betweenness) Top 30]")
    lines.append(f"{'순위':>4}  {'저자(한국어)':12}  {'저자(영문)':25}  {'매개중심성':>12}  {'논문수':>5}")
    lines.append("-" * 70)
    for i, s in enumerate(by_betweenness[:30], 1):
        lines.append(
            f"{i:>4}  {s['ko']:12}  {s['en']:25}  {s['betweenness_centrality']:>12.6f}  {s['paper_count']:>5}"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  → {path}")


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="저자 공저 네트워크 구축")
    parser.add_argument(
        "--min-papers",
        type=int,
        default=1,
        help="최소 논문 수 (기본: 1, 권장: 2 이상)",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  KCI 콘크리트학회 저자 공저 네트워크 구축")
    print("=" * 60)

    # 1. 데이터 로드
    print("\n[1/4] 논문 데이터 로드...")
    papers = load_papers()
    print(f"  논문 {len(papers)}편 로드")

    # 2. 그래프 구축
    print(f"\n[2/4] 그래프 구축 (min_papers={args.min_papers})...")
    G = build_graph(papers, min_papers=args.min_papers)
    print(f"  노드(저자): {G.number_of_nodes()}명")
    print(f"  엣지(공저): {G.number_of_edges()}건")

    # 연결 컴포넌트 통계
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    print(f"  연결 컴포넌트: {len(components)}개")
    print(f"  최대 컴포넌트 크기: {len(components[0])}명")

    # 3. 통계
    print("\n[3/4] 중심성 통계 계산...")
    stats = compute_stats(G)

    # 4. 내보내기
    print("\n[4/4] 파일 내보내기...")
    export_graphml(G, OUT_DIR / "graph.graphml")
    export_gexf(G, OUT_DIR / "graph.gexf")
    export_d3_json(G, stats, OUT_DIR / "graph_d3.json")
    export_top_authors(stats, OUT_DIR / "top_authors.txt")

    # stats JSON
    stats_path = OUT_DIR / "stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {stats_path}")

    # 요약 출력
    all_stats = list(stats.values())
    top3 = sorted(all_stats, key=lambda x: x["paper_count"], reverse=True)[:5]

    print("\n" + "=" * 60)
    print("  완료! 상위 저자 (논문 수 기준)")
    print("=" * 60)
    for s in top3:
        print(f"  {s['ko']} ({s['en']}) — {s['paper_count']}편, 공저자 {s['collaborator_count']}명")

    print(f"\n  출력 폴더: {OUT_DIR}/")
    print(f"  Gephi에서 열기: network/graph.gexf")
    print(f"  웹 시각화용:    network/graph_d3.json")


if __name__ == "__main__":
    main()
