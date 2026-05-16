"""
KCI 논문 의미 기반 군집화
- OpenAI text-embedding-3-small 으로 제목 임베딩
- UMAP 2D 축소 → HDBSCAN 군집화
- GPT-4o-mini 로 클러스터 자동 레이블
- 결과: network/clusters.json
"""

from __future__ import annotations
import json, os, sys, time, hashlib
from pathlib import Path

# ── 경로 설정 ──────────────────────────────────────────────────────────────
BASE   = Path(__file__).parent.parent
DATA   = BASE / "network" / "papers_lite.json"
CACHE  = BASE / "network" / "embeddings_cache.json"   # 재실행 시 API 호출 절약
OUT    = BASE / "network" / "clusters.json"

# ── OpenAI 클라이언트 ───────────────────────────────────────────────────────
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    if not client.api_key:
        sys.exit("❌ OPENAI_API_KEY 환경변수를 설정해주세요.\n   export OPENAI_API_KEY=sk-...")
except ImportError:
    sys.exit("❌ pip install openai")

EMB_MODEL   = "text-embedding-3-small"
LABEL_MODEL = "gpt-4.1-mini"
BATCH_SIZE  = 100   # API 배치 크기

# ── 1. 논문 로드 ────────────────────────────────────────────────────────────
print("📄 논문 로드 중…")
papers = json.loads(DATA.read_text(encoding="utf-8"))
# 제목 한글 + 영문 합산 (없으면 한글만)
texts  = [(p.get("t") or "") + (" " + p.get("te","") if p.get("te") else "") for p in papers]
ids    = [p.get("dn") or p.get("id") or str(i) for i, p in enumerate(papers)]  # dn 기준
print(f"  {len(papers)}편 로드 완료")

# ── 2. 임베딩 (캐시 활용) ───────────────────────────────────────────────────
cache: dict[str, list[float]] = {}
if CACHE.exists():
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    print(f"  캐시 {len(cache)}개 로드")

def cache_key(txt: str) -> str:
    return hashlib.md5(txt.encode()).hexdigest()

def get_embeddings(texts_batch: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMB_MODEL, input=texts_batch)
    return [d.embedding for d in resp.data]

missing_idx  = [i for i, t in enumerate(texts) if cache_key(t) not in cache]
missing_txts = [texts[i] for i in missing_idx]

if missing_txts:
    print(f"  임베딩 요청: {len(missing_txts)}개 (배치 {BATCH_SIZE}씩)…")
    for start in range(0, len(missing_txts), BATCH_SIZE):
        batch = missing_txts[start:start+BATCH_SIZE]
        embs  = get_embeddings(batch)
        for txt, emb in zip(batch, embs):
            cache[cache_key(txt)] = emb
        done = min(start+BATCH_SIZE, len(missing_txts))
        print(f"    {done}/{len(missing_txts)}", end="\r", flush=True)
        if start + BATCH_SIZE < len(missing_txts):
            time.sleep(0.3)   # rate-limit 여유
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    print(f"\n  임베딩 완료 → 캐시 저장")
else:
    print("  모든 임베딩 캐시 히트 ✅")

embeddings_list = [cache[cache_key(t)] for t in texts]

# ── 3. numpy 배열로 변환 ────────────────────────────────────────────────────
import numpy as np
X = np.array(embeddings_list, dtype=np.float32)
print(f"  임베딩 행렬: {X.shape}")

# ── 4. UMAP 축소 (클러스터링용 10D + 시각화용 2D) ────────────────────────────
print("🗺  UMAP 차원 축소 중…")
import umap as umap_lib

# 10D: 클러스터링 품질을 위해 (정보 손실 최소화)
reducer_10d = umap_lib.UMAP(
    n_components=10,
    n_neighbors=30,
    min_dist=0.0,
    metric="cosine",
    random_state=42,
    verbose=False,
)
X10 = reducer_10d.fit_transform(X)
print(f"  10D 완료: {X10.shape}")

# 2D: 시각화 전용
reducer_2d = umap_lib.UMAP(
    n_components=2,
    n_neighbors=15,
    min_dist=0.1,
    metric="cosine",
    random_state=42,
    verbose=False,
)
xy = reducer_2d.fit_transform(X)
print(f"  2D 완료: {xy.shape}")

# ── 5. K-Means 군집화 (개수 지정) ───────────────────────────────────────────
print("🔍 K-Means 군집화 중…")
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# 최적 K 탐색 (30~55 범위 — 콘크리트 세부분야 충분히 분리)
best_k, best_score, best_labels = 40, -1, None
print("  K 탐색 중 (30~55)…")
for k in range(30, 56):
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    lbl = km.fit_predict(X10)
    score = silhouette_score(X10, lbl, sample_size=2000, random_state=42)
    print(f"    K={k}: silhouette={score:.4f}")
    if score > best_score:
        best_k, best_score, best_labels = k, score, lbl

labels = best_labels
print(f"  ✅ 최적 K={best_k} (silhouette={best_score:.4f})")

n_clusters = best_k
n_noise    = 0   # K-Means는 모든 논문을 군집에 할당
print(f"  군집 수: {n_clusters}개")

# ── 6. 클러스터별 대표 제목 수집 ─────────────────────────────────────────────
from collections import defaultdict
cluster_papers: dict[int, list[str]] = defaultdict(list)
for i, lbl in enumerate(labels):
    cluster_papers[int(lbl)].append(texts[i])

# 각 클러스터에서 대표 제목 최대 15개 (중심에 가까운 순)
# 중심 = 클러스터 내 xy 평균에 가장 가까운 논문들
cluster_centers: dict[int, np.ndarray] = {}
for lbl in cluster_papers:
    idxs = [i for i, l in enumerate(labels) if l == lbl]
    pts  = xy[idxs]
    cluster_centers[lbl] = pts.mean(axis=0)

def top_titles_for_cluster(lbl: int, n: int = 15) -> list[str]:
    idxs  = [i for i, l in enumerate(labels) if l == lbl]
    pts   = xy[idxs]
    ctr   = cluster_centers[lbl]
    dists = np.linalg.norm(pts - ctr, axis=1)
    order = np.argsort(dists)
    return [texts[idxs[j]] for j in order[:n]]

# ── 7. GPT 자동 레이블링 ────────────────────────────────────────────────────
print("🏷  GPT 클러스터 레이블링 중…")

def label_cluster(lbl: int) -> dict:
    sample_titles = top_titles_for_cluster(lbl)
    prompt = f"""다음은 콘크리트 구조물 연구 논문 {len(cluster_papers[lbl])}편의 군집에서 대표 논문 제목들이야.
이 군집의 연구 세부 분야를 간결하게 정의해줘.

제목들:
{chr(10).join(f'- {t}' for t in sample_titles)}

JSON으로만 답해줘 (다른 텍스트 없이):
{{
  "label_ko": "한국어 세부 분야명 (5~15자)",
  "label_en": "English subdomain name (2~4 words)",
  "keywords": ["핵심키워드1", "핵심키워드2", "핵심키워드3", "핵심키워드4", "핵심키워드5"],
  "description": "한 줄 설명 (20~40자)"
}}"""

    try:
        resp = client.chat.completions.create(
            model=LABEL_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.2,
            response_format={"type":"json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"  ⚠ 클러스터 {lbl} 레이블 실패: {e}")
        return {
            "label_ko": f"군집 {lbl}",
            "label_en": f"Cluster {lbl}",
            "keywords": [],
            "description": ""
        }

cluster_labels: dict[int, dict] = {}
sorted_clusters = sorted(cluster_papers.keys(), key=lambda l: -len(cluster_papers[l]))

for lbl in sorted_clusters:
    info = label_cluster(lbl)
    cluster_labels[lbl] = info
    print(f"  [{lbl:2d}] {len(cluster_papers[lbl]):4d}편 → {info['label_ko']} | {info['label_en']}")
    time.sleep(0.2)

# ── 8. 결과 조합 ─────────────────────────────────────────────────────────────
print("💾 결과 저장 중…")

# 군집 정보
clusters_info = []
for lbl in sorted_clusters:
    info = cluster_labels[lbl]
    cx, cy = cluster_centers[lbl]
    clusters_info.append({
        "id":          lbl,
        "label_ko":    info["label_ko"],
        "label_en":    info["label_en"],
        "keywords":    info["keywords"],
        "description": info["description"],
        "count":       len(cluster_papers[lbl]),
        "cx":          round(float(cx), 4),
        "cy":          round(float(cy), 4),
    })

# 논문별 클러스터 + 2D 좌표
paper_clusters = []
for i, p in enumerate(papers):
    paper_clusters.append({
        "id":      ids[i],               # dn 기준 (papers_lite의 dn 필드)
        "cluster": int(labels[i]),
        "x":       round(float(xy[i,0]), 4),
        "y":       round(float(xy[i,1]), 4),
    })

import numpy as np

class NumpyEncoder(json.JSONEncoder):
    """numpy int/float → Python 기본 타입으로 변환"""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

result = {
    "model":    EMB_MODEL,
    "n_papers": len(papers),
    "n_clusters": n_clusters,
    "n_noise":   int(n_noise),
    "clusters":  clusters_info,
    "papers":    paper_clusters,
}

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, cls=NumpyEncoder), encoding="utf-8")
size_kb = OUT.stat().st_size // 1024
print(f"\n✅ 완료! → {OUT}  ({size_kb} KB)")
print(f"   군집 {n_clusters}개 / 논문 {len(papers)}편 / 미분류 {n_noise}편")
print("\n군집 요약:")
for c in clusters_info[:10]:
    print(f"  {c['label_ko']:15s} | {c['count']:4d}편 | {', '.join(c['keywords'][:3])}")
if len(clusters_info) > 10:
    print(f"  ... 외 {len(clusters_info)-10}개 군집")
