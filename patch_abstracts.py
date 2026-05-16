"""
초록·영문제목·키워드·권호 누락 데이터 보완 스크립트
=====================================================
이미 수집된 JSON 파일 중 abstract_ko가 비어 있는 논문을
detail 페이지에서 재수집하여 보완합니다.

실행:
    python3 patch_abstracts.py                    # 전체 대상
    python3 patch_abstracts.py --source journal   # 학회지만
    python3 patch_abstracts.py --dry-run          # 대상만 확인 (실제 수집 안 함)
    python3 patch_abstracts.py --limit 50         # 최대 50편만
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
META_DIR = ROOT / "meta"
PAPERS_DIR = ROOT / "papers"
LOGS_DIR = ROOT / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            LOGS_DIR / f"patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

BASE_URL = "https://paper.cricit.kr/user/listview/kci2018"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_keywords(raw: str):
    parts = [p.strip() for p in re.split(r"[;；]", raw) if p.strip()]
    ko, en = [], []
    for p in parts:
        (ko if re.search(r"[가-힣]", p) else en).append(p)
    return {"ko": ko, "en": en}


def rebuild_markdown(d: dict) -> str:
    """JSON 데이터로 마크다운 재생성 (fix_data.py 방식과 동일)"""
    title_ko = d.get("title_ko", "")
    title_en = d.get("title_en", "")
    authors = d.get("authors", [])
    affiliation = d.get("affiliation", "")
    abstract_ko = d.get("abstract_ko", "")
    abstract_en = d.get("abstract_en", "")
    kw_ko = d.get("keywords", {}).get("ko", [])
    kw_en = d.get("keywords", {}).get("en", [])
    year = d.get("year", "")
    volume = d.get("volume", "")
    issue = d.get("issue", "")
    page = d.get("page", "")
    issn = d.get("issn", "")
    dn = d.get("dn", "")
    source = d.get("source", "")

    authors_ko = " ; ".join(a.get("ko", "") for a in authors if a.get("ko"))
    authors_en = " ; ".join(a.get("en", "") for a in authors if a.get("en"))

    fm = f"""\
---
id: "{dn}"
source: "{source}"
yearmonth: "{d.get('yearmonth', '')}"
year: "{year}"
month: "{d.get('month', '')}"
title_ko: "{title_ko.replace('"', "'")}"
title_en: "{title_en.replace('"', "'")}"
authors_ko: "{authors_ko}"
authors_en: "{authors_en}"
affiliation: "{affiliation.replace('"', "'")}"
volume: "{volume}"
issue: "{issue}"
page: "{page}"
issn: "{issn}"
keywords_ko: {json.dumps(kw_ko, ensure_ascii=False)}
keywords_en: {json.dumps(kw_en, ensure_ascii=False)}
detail_url: "{d.get('detail_url', '')}"
scraped_at: "{d.get('scraped_at', '')}"
---"""

    body = [f"# {title_ko}"]
    if title_en:
        body.append(f"**{title_en}**")
    body.append("")
    body.append(f"**저자**: {authors_ko}")
    if authors_en:
        body.append(f"**Authors**: {authors_en}")
    if affiliation:
        body.append(f"**소속**: {affiliation}")
    body.append(f"**연도**: {year} | **권**: {volume} | **호**: {issue} | **페이지**: {page}")
    body.append("")
    if abstract_ko:
        body.append("## 초록")
        body.append(abstract_ko)
        body.append("")
    if abstract_en:
        body.append("## Abstract")
        body.append(abstract_en)
        body.append("")
    if kw_ko or kw_en:
        body.append("## 키워드")
        if kw_ko:
            body.append(f"**한국어**: {', '.join(kw_ko)}")
        if kw_en:
            body.append(f"**English**: {', '.join(kw_en)}")
        body.append("")

    return fm + "\n\n" + "\n".join(body) + "\n"


# ── detail 페이지 파싱 ────────────────────────────────────────────────────────

def fetch_detail(dn: str, organCode2: str, yearmonth: str) -> dict | None:
    url = (
        f"{BASE_URL}/doc_rdoc.asp"
        f"?catvalue=3&returnVal=RD_R&organCode=kci&organCode2={organCode2}"
        f"&yearmonth={yearmonth}&page=1&dn={dn}&step=&usernum=0&seid="
    )
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
    except requests.RequestException as e:
        log.warning(f"  요청 실패 dn={dn}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    result: dict = {}

    for th in soup.find_all("th"):
        label = clean_text(th.get_text())
        td = th.find_next_sibling("td")
        if not td:
            continue
        val = clean_text(td.get_text())

        # 제목 (KO/EN 분리)
        if re.search(r"논문명|제\s*목|논문\s*제목", label):
            sep = re.search(r"^(.+?)\s*/\s*([A-Z].+)$", val)
            if sep:
                result["title_ko"] = sep.group(1).strip()
                result["title_en"] = sep.group(2).strip()
            else:
                result["title_ko"] = val

        # 저자
        elif re.search(r"저자명|저\s*자", label):
            result["authors_raw"] = val

        # 소속
        elif re.search(r"소\s*속|Affiliation", label):
            result["affiliation"] = val

        # 초록
        elif re.search(r"요약\s*1|초\s*록|국문", label):
            result["abstract_ko"] = val
        elif re.search(r"요약\s*2|Abstract|영문", label, re.I):
            result["abstract_en"] = val

        # 키워드
        elif re.search(r"주제어|핵심어|키워드|Keyword", label, re.I):
            result["keywords_raw"] = val
            result["keywords"] = parse_keywords(val)

        # 수록사항 → 권호
        elif re.search(r"수록사항", label):
            vol_m = re.search(r"Vol\.?\s*(\d+)", val, re.I)
            no_m  = re.search(r"No\.?\s*(\d+)", val, re.I)
            if vol_m:
                result["volume"] = vol_m.group(1)
            if no_m:
                result["issue"] = no_m.group(1)

        # 페이지
        elif re.search(r"^페이지$", label):
            start_m = re.search(r"시작페이지\((\d+)\)", val)
            total_m = re.search(r"총페이지\((\d+)\)", val)
            if start_m:
                start = int(start_m.group(1))
                end = start + int(total_m.group(1)) - 1 if total_m else start
                result["page"] = f"pp.{start}-{end}"
            elif re.match(r"pp?\.\s*\d|\d+[-~]\d+", val):
                result["page"] = val

        # ISSN
        elif re.search(r"ISSN", label, re.I):
            result["issn"] = val

    return result if result else None


# ── 저자 파싱 ─────────────────────────────────────────────────────────────────

def parse_authors(raw: str) -> list[dict]:
    authors = []
    for part in re.split(r"\s*;\s*", raw.strip()):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([^(]+)\(([^)]+)\)\s*$", part)
        if m:
            authors.append({"ko": m.group(1).strip(), "en": m.group(2).strip(), "affiliation": ""})
        else:
            authors.append({"ko": part, "en": "", "affiliation": ""})
    return authors


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="초록·영문제목·키워드·권호 누락 보완")
    parser.add_argument("--source", choices=["journal", "conference", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="대상 목록만 출력")
    parser.add_argument("--limit", type=int, default=0, help="최대 처리 수 (0=전체)")
    parser.add_argument("--from-year", type=int, default=0, help="이 연도 이후만 처리")
    parser.add_argument("--to-year", type=int, default=0, help="이 연도 이전만 처리")
    args = parser.parse_args()

    sources = ["journal", "conference"] if args.source == "both" else [args.source]

    # 보완 대상 수집
    targets: list[dict] = []
    for source in sources:
        meta_dir = META_DIR / source
        if not meta_dir.exists():
            continue
        for jf in sorted(meta_dir.glob("*.json")):
            d = json.loads(jf.read_text(encoding="utf-8"))
            year = int(d.get("year", 0) or 0)
            if args.from_year and year < args.from_year:
                continue
            if args.to_year and year > args.to_year:
                continue
            # abstract_ko 또는 title_en 또는 volume 비어 있으면 대상
            needs_patch = (
                not d.get("abstract_ko")
                or not d.get("title_en")
                or not d.get("volume")
                or not d.get("keywords", {}).get("ko")
            )
            if needs_patch:
                targets.append({"source": source, "path": jf, "data": d})

    print(f"\n{'='*55}")
    print(f"  보완 대상: {len(targets)}편")
    print(f"{'='*55}")

    if args.dry_run:
        for t in targets[:20]:
            d = t["data"]
            print(f"  dn={d['dn']} {d['year']} abstract={bool(d.get('abstract_ko'))} vol={d.get('volume','?')}")
        if len(targets) > 20:
            print(f"  ... 외 {len(targets)-20}편")
        return

    if args.limit:
        targets = targets[: args.limit]
        print(f"  (최대 {args.limit}편만 처리)")

    patched = 0
    failed = 0

    for i, t in enumerate(targets, 1):
        d = t["data"]
        source = t["source"]
        jf: Path = t["path"]
        dn = d["dn"]
        organCode2 = d.get("organCode2", "kci01" if source == "journal" else "kci03")
        yearmonth = d.get("yearmonth", "")

        log.info(f"  [{i}/{len(targets)}] dn={dn} {d.get('year','')}년...")

        time.sleep(random.uniform(1.5, 3.0))
        fetched = fetch_detail(dn, organCode2, yearmonth)

        if not fetched:
            log.warning(f"    → 실패")
            failed += 1
            continue

        changed = False

        # 제목
        if fetched.get("title_ko") and not d.get("title_ko"):
            d["title_ko"] = fetched["title_ko"]
            changed = True
        if fetched.get("title_en") and not d.get("title_en"):
            d["title_en"] = fetched["title_en"]
            changed = True

        # 초록
        if fetched.get("abstract_ko") and not d.get("abstract_ko"):
            d["abstract_ko"] = fetched["abstract_ko"]
            changed = True
        if fetched.get("abstract_en") and not d.get("abstract_en"):
            d["abstract_en"] = fetched["abstract_en"]
            changed = True

        # 키워드
        if fetched.get("keywords") and not d.get("keywords", {}).get("ko"):
            d["keywords"] = fetched["keywords"]
            changed = True

        # 권호
        if fetched.get("volume") and not d.get("volume"):
            d["volume"] = fetched["volume"]
            changed = True
        if fetched.get("issue") and not d.get("issue"):
            d["issue"] = fetched["issue"]
            changed = True

        # 페이지 (리스트 페이지 값보다 detail 값이 더 상세할 경우)
        if fetched.get("page") and not d.get("page"):
            d["page"] = fetched["page"]
            changed = True

        # 저자 (기존 저자 없는 경우만)
        if fetched.get("authors_raw") and not d.get("authors"):
            d["authors"] = parse_authors(fetched["authors_raw"])
            changed = True

        if changed:
            jf.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            # MD 업데이트
            md_path = PAPERS_DIR / source / (jf.stem + ".md")
            md_path.write_text(rebuild_markdown(d), encoding="utf-8")
            patched += 1
            log.info(f"    ✓ 보완 완료 (abstract_ko={bool(d.get('abstract_ko'))} title_en={bool(d.get('title_en'))})")
        else:
            log.info(f"    → 변경 없음")

    print(f"\n{'='*55}")
    print(f"  완료: {patched}편 보완, {failed}편 실패")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
