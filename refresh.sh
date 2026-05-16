#!/bin/bash
# KCI 대시보드 전체 갱신 스크립트
# 사용: bash refresh.sh
# 새 논문 수집 후 네트워크 재분석 + 대시보드 재생성까지 한 번에 처리합니다.

set -e
cd "$(dirname "$0")"
PYTHON=".venv/bin/python3"

echo "=============================================="
echo " KCI 콘크리트학회 대시보드 갱신"
echo "=============================================="

# 0) 선택: 새 논문 수집 여부
if [ "$1" = "--collect" ]; then
  echo ""
  echo "[1/4] 논문 수집 (추가분만 이어서)..."
  $PYTHON run.py
else
  echo ""
  echo "[1/4] 수집 스킵 (새 수집은 bash refresh.sh --collect)"
fi

# 1) 데이터 전처리
echo ""
echo "[2/4] 데이터 전처리 (papers_lite, yearly_stats, author_papers)..."
$PYTHON << 'EOF'
import json, glob, os
from collections import Counter, defaultdict

base = "meta"
net  = "network"
os.makedirs(net, exist_ok=True)

papers = []
for src in ["journal", "conference"]:
    for f in sorted(glob.glob(f"{base}/{src}/*.json")):
        try:
            with open(f) as fp: papers.append(json.load(fp))
        except: pass

print(f"  논문 {len(papers)}편 로드")

# papers_lite
NON_PAPER = ['발간사','목차','편집위원','심사위원','학회장','[Contents]','[발간사']
lite = []
for p in papers:
    if any(k in p.get('title_ko','') for k in NON_PAPER):
        continue
    authors = [{"n":a.get("ko",""),"e":a.get("en",""),"af":a.get("affiliation","")}
               for a in p.get("authors",[]) if a.get("ko","").strip()]
    lite.append({"dn":p.get("dn",""),"src":p.get("source",""),"soc":p.get("society","KCI"),
                 "y":p.get("year",""),"m":p.get("month",""),"t":p.get("title_ko",""),
                 "te":p.get("title_en",""),"a":authors,"pg":p.get("page",""),
                 "vol":p.get("volume",""),"iss":p.get("issue",""),"url":p.get("detail_url","")})
with open(f"{net}/papers_lite.json","w",encoding="utf-8") as f:
    json.dump(lite,f,ensure_ascii=False,separators=(',',':'))

# yearly_stats
yearly = defaultdict(lambda:{"j":0,"c":0,"authors":set()})
for p in papers:
    y = p.get("year","");
    if not y: continue
    if p.get("source","")=="journal": yearly[y]["j"]+=1
    else: yearly[y]["c"]+=1
    for a in p.get("authors",[]):
        if a.get("ko","").strip(): yearly[y]["authors"].add(a["ko"])
ys = {y:{"j":d["j"],"c":d["c"],"ua":len(d["authors"])} for y,d in sorted(yearly.items())}
with open(f"{net}/yearly_stats.json","w") as f: json.dump(ys,f,ensure_ascii=False)

# author_papers
ap = defaultdict(list)
for p in papers:
    for a in p.get("authors",[]):
        n=a.get("ko","").strip()
        if n: ap[n].append(p.get("dn",""))
with open(f"{net}/author_papers.json","w",encoding="utf-8") as f:
    json.dump(dict(ap),f,ensure_ascii=False,separators=(',',':'))

print(f"  저장 완료 (papers_lite, yearly_stats, author_papers)")
EOF

# 2) 네트워크 재구축
echo ""
echo "[3/4] 저자 공저 네트워크 재구축..."
$PYTHON analyze/build_network.py --min-papers 1

# 3) 대시보드 생성
echo ""
echo "[4/4] 대시보드 HTML 생성..."
$PYTHON analyze/make_dashboard.py

echo ""
echo "=============================================="
echo " 완료! 대시보드를 엽니다..."
echo "=============================================="
open network/dashboard.html
