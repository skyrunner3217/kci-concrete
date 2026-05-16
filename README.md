# 한국 구조공학 학회 논문 데이터베이스

한국콘크리트학회(KCI) 및 한국구조물진단유지관리공학회(KSMI) 발행 논문의 로컬 메타데이터 데이터베이스 및 분석 대시보드.

## 수집 현황

| 학회 | 출판물 | 편수 | 기간 |
|------|--------|------|------|
| KCI | 학회 논문집 (kci01) | 2,801편 | 1989–2026 |
| KCI | 학술대회 논문집 (kci03) | 18,228편 | 1989–2026 |
| **합계** | | **20,945편** | |

## 대시보드

`network/dashboard.html` — 자체 완결형 인터랙티브 대시보드.

- **저자 네트워크**: D3.js Canvas Force Graph (저자 9,560명, 공저 50,282건)
- **트렌드 분석**: 연도별 발행량, 연구 주제 트렌드, 히트맵
- **논문 검색**: 제목·저자·키워드 풀텍스트, 주제 필터, AI 클러스터 필터
- **통계**: 상위 저자, 매개 중심성 분석

## 설치 및 실행

```bash
# 가상환경 생성 (최초 1회)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 대시보드 재생성 (데이터 수집 없이)
bash refresh.sh

# 새 데이터 수집 포함 전체 실행
bash refresh.sh --collect
```

> **주의**: `python3` 대신 반드시 `.venv/bin/python3` 사용.

## 파일 구조

```
├── crawl/scraper.py          # 메인 스크레이퍼
├── analyze/
│   ├── build_network.py      # 공저 네트워크
│   ├── make_dashboard.py     # 대시보드 HTML 생성기
│   └── embed_cluster.py      # 임베딩 + 클러스터링
├── patch_abstracts.py        # 초록 소급 보완
├── patch_conference_pages.py # 학술대회 페이지 소급 보완
├── refresh.sh                # 전체 파이프라인
├── network/dashboard.html    # 인터랙티브 대시보드
└── requirements.txt
```

## 데이터 소스

- **KCI**: `paper.cricit.kr` (로그인 불필요)
- **KSMI**: `auric.or.kr` (로그인 불필요, 동일 URL 구조)

## 라이선스

개인 연구용. 논문 메타데이터는 각 학회 소유.
