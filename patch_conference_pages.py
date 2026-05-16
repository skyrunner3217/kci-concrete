"""
학술대회 목록 페이지네이션 보완 스크립트
==========================================
기존 conference 수집이 각 권호의 1페이지만 가져온 문제를 보완합니다.
각 yearmonth별로 이미 수집된 dn을 확인하고,
목록 2페이지 이상에 있는 누락 논문을 추가 수집합니다.

실행:
    python3 patch_conference_pages.py               # 전체
    python3 patch_conference_pages.py --dry-run     # 대상 yearmonth만 출력
    python3 patch_conference_pages.py --limit 5     # 최대 5개 권호만
    python3 patch_conference_pages.py --from-year 2010  # 2010년 이후만
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
from typing import NamedTuple

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
            LOGS_DIR / f"patch_pages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

BASE_URL = "https://paper.cricit.kr/user/listview/kci2018"
ORGANCODE2 = "kci03"
DELAY_MIN, DELAY_MAX = 1.5, 3.0

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


def parse_keywords(raw: str) -> dict:
    parts = [p.strip() for p in re.split(r"[;；]", raw) if p.strip()]
    ko, en = [], []
    for p in parts:
        (ko if re.search(r"[가-힣]", p) else en).append(p)
    return {"ko": ko, "en": en}


def get_page(url: str) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as e:
        log.warning(f"  요청 실패: {url} → {e}")
        return None


# ── 목록 파싱 ─────────────────────────────────────────────────────────────────

class ListingEntry(NamedTuple):
    dn: str
    title_ko: str
    page: str


def make_listing_url(yearmonth: str, page: int = 1) -> str:
    url = (
        f"{BASE_URL}/gby_rdoc.asp"
        f"?step=4&organCode=kci&organCode2={ORGANCODE2}"
        f"&yearmonth={yearmonth}&usernum=0&seid=&tbnm=r"
    )
    if page > 1:
        url += f"&page={page}&spage={page}"
    return url


def make_detail_url(dn: str, yearmonth: str) -> str:
    return (
        f"{BASE_URL}/doc_rdoc.asp"
        f"?catvalue=3&returnVal=RD_R&organCode=kci&organCode2={ORGANCODE2}"
        f"&yearmonth={yearmonth}&page=1&dn={dn}&step=&usernum=0&seid="
    )


def _parse_entries_from_soup(soup: BeautifulSoup) -> list[ListingEntry]:
    entries: list[ListingEntry] = []
    rows = soup.select("table.tb-list tr, table tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        dn = ""
        title_ko = ""
        page_info = ""

        link = row.find("a", onclick=True) or row.find("a", href=True)
        full_href = ""
        if link:
            full_href = link.get("onclick", "") or link.get("href", "")

        dn_match = re.search(r"[?&]dn=(\d+)", full_href)
        if not dn_match:
            for cell in cells:
                for cl in cell.find_all("a"):
                    m = re.search(r"[?&]dn=(\d+)", cl.get("href", "") + cl.get("onclick", ""))
                    if m:
                        dn_match = m
                        break
                if dn_match:
                    break

        if not dn_match:
            continue

        dn = dn_match.group(1)

        for cell in cells:
            text = clean_text(cell.get_text())
            if re.search(r"\[표지\]|\[목차\]|^\[안내\]|^\[상세일정\]", text):
                dn = ""
                break
            if len(text) > len(title_ko) and len(text) > 5:
                title_ko = text

        if not dn:
            continue

        for cell in reversed(cells):
            text = clean_text(cell.get_text())
            if re.match(r"^pp?\.\s*\d", text) or re.match(r"^\d+[-~]\d+$", text):
                page_info = text
                break

        entries.append(ListingEntry(dn=dn, title_ko=title_ko, page=page_info))

    return entries


def _parse_total_pages(soup: BeautifulSoup) -> int:
    m = re.search(r"\[Page\s+\d+\s+of\s+(\d+)\]", soup.get_text())
    return int(m.group(1)) if m else 1


def fetch_all_listing_entries(yearmonth: str) -> list[ListingEntry]:
    """해당 yearmonth의 전체 목록 (모든 페이지) 수집"""
    soup = get_page(make_listing_url(yearmonth, 1))
    if soup is None:
        return []
    if soup.find(string=re.compile(r"등록된\s*데이타가\s*없습니다")):
        return []

    all_entries = _parse_entries_from_soup(soup)
    total_pages = _parse_total_pages(soup)

    for p in range(2, total_pages + 1):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        p_soup = get_page(make_listing_url(yearmonth, p))
        if p_soup is None:
            log.warning(f"  {yearmonth} p.{p} 실패 — 중단")
            break
        all_entries.extend(_parse_entries_from_soup(p_soup))

    seen: set[str] = set()
    unique = []
    for e in all_entries:
        if e.dn not in seen:
            seen.add(e.dn)
            unique.append(e)

    return unique


# ── 상세 페이지 파싱 ──────────────────────────────────────────────────────────

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


def fetch_detail(dn: str, yearmonth: str) -> dict | None:
    url = make_detail_url(dn, yearmonth)
    soup = get_page(url)
    if soup is None:
        return None

    result: dict = {}
    for th in soup.find_all("th"):
        label = clean_text(th.get_text())
        td = th.find_next_sibling("td")
        if not td:
            continue
        val = clean_text(td.get_text())

        if re.search(r"논문명|제\s*목|논문\s*제목", label):
            sep = re.search(r"^(.+?)\s*/\s*([A-Z].+)$", val)
            if sep:
                result["title_ko"] = sep.group(1).strip()
                result["title_en"] = sep.group(2).strip()
            else:
                result["title_ko"] = val

        elif re.search(r"저자명|저\s*자", label):
            result["authors"] = parse_authors(val)

        elif re.search(r"소\s*속|Affiliation", label):
            result["affiliation"] = val

        elif re.search(r"요약\s*1|초\s*록|국문", label):
            result["abstract_ko"] = val
        elif re.search(r"요약\s*2|Abstract|영문", label, re.I):
            result["abstract_en"] = val

        elif re.search(r"주제어|핵심어|키워드|Keyword", label, re.I):
            result["keywords"] = parse_keywords(val)

        elif re.search(r"수록사항", label):
            vol_m = re.search(r"Vol\.?\s*(\d+)", val, re.I)
            no_m  = re.search(r"No\.?\s*(\d+)", val, re.I)
            if vol_m: result["volume"] = vol_m.group(1)
            if no_m:  result["issue"]  = no_m.group(1)

        elif re.search(r"^페이지$", label):
            start_m = re.search(r"시작페이지\((\d+)\)", val)
            total_m = re.search(r"총페이지\((\d+)\)", val)
            if start_m:
                start = int(start_m.group(1))
                end = start + int(total_m.group(1)) - 1 if total_m else start
                result["page"] = f"pp.{start}-{end}"
            elif re.match(r"pp?\.\s*\d|\d+[-~]\d+", val):
                result["page"] = val

        elif re.search(r"ISSN", label, re.I):
            result["issn"] = val

    return result if result else None


# ── 마크다운 생성 ─────────────────────────────────────────────────────────────

def rebuild_markdown(d: dict) -> str:
    title_ko    = d.get("title_ko", "")
    title_en    = d.get("title_en", "")
    authors     = d.get("authors", [])
    affiliation = d.get("affiliation", "")
    abstract_ko = d.get("abstract_ko", "")
    abstract_en = d.get("abstract_en", "")
    kw_ko = d.get("keywords", {}).get("ko", [])
    kw_en = d.get("keywords", {}).get("en", [])
    year   = d.get("year", "")
    volume = d.get("volume", "")
    issue  = d.get("issue", "")
    page   = d.get("page", "")
    issn   = d.get("issn", "")
    dn     = d.get("dn", "")
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


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="학술대회 페이지네이션 누락 보완")
    parser.add_argument("--dry-run", action="store_true", help="대상만 출력, 수집 안 함")
    parser.add_argument("--limit", type=int, default=0, help="최대 처리 권호 수 (0=전체)")
    parser.add_argument("--from-year", type=int, default=0, help="이 연도 이후만 처리")
    parser.add_argument("--to-year", type=int, default=0, help="이 연도 이전만 처리")
    args = parser.parse_args()

    conf_meta = META_DIR / "conference"
    conf_papers = PAPERS_DIR / "conference"
    conf_papers.mkdir(parents=True, exist_ok=True)

    # ── 기존 수집 현황 파악 ──────────────────────────────────────────────────
    existing: dict[str, set[str]] = {}   # yearmonth → {dn, ...}
    for jf in conf_meta.glob("*.json"):
        d = json.loads(jf.read_text(encoding="utf-8"))
        ym = d.get("yearmonth", "")
        existing.setdefault(ym, set()).add(d["dn"])

    print(f"\n{'='*60}")
    print(f"  conference 기존 수집: {sum(len(v) for v in existing.values())}편 / {len(existing)}개 권호")
    print(f"{'='*60}")

    # ── 각 yearmonth별 전체 목록 크기 확인 (1페이지에서 total_pages 파악) ────
    target_yms = sorted(existing.keys())
    if args.from_year:
        target_yms = [ym for ym in target_yms if int(ym[:4]) >= args.from_year]
    if args.to_year:
        target_yms = [ym for ym in target_yms if int(ym[:4]) <= args.to_year]

    if args.limit:
        target_yms = target_yms[-args.limit:]   # 최신순으로 limit개

    total_added = 0
    total_failed = 0

    for ym in target_yms:
        year = int(ym[:4])

        # 1페이지만 빠르게 확인해서 total_pages 파악
        soup = get_page(make_listing_url(ym, 1))
        if soup is None:
            log.warning(f"  {ym} 목록 접근 실패")
            continue
        if soup.find(string=re.compile(r"등록된\s*데이타가\s*없습니다")):
            continue

        total_pages = _parse_total_pages(soup)
        current_count = len(existing.get(ym, set()))

        if total_pages <= 1:
            # 페이지가 1개면 이미 다 수집됨
            time.sleep(random.uniform(0.5, 1.0))
            continue

        # 1페이지 entries로 이미 수집된 것과 비교
        all_on_p1 = _parse_entries_from_soup(soup)
        log.info(f"  {ym}: 총 {total_pages}페이지 | 기존={current_count}편")

        if args.dry_run:
            print(f"  {ym}: {total_pages}페이지 (기존 {current_count}편, 예상 추가 ~{(total_pages-1)*len(all_on_p1)}편)")
            time.sleep(random.uniform(0.5, 1.0))
            continue

        # 전체 목록 가져오기 (2페이지~)
        all_entries: list[ListingEntry] = all_on_p1
        for p in range(2, total_pages + 1):
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            p_soup = get_page(make_listing_url(ym, p))
            if p_soup is None:
                log.warning(f"    {ym} p.{p} 실패 — 중단")
                break
            all_entries.extend(_parse_entries_from_soup(p_soup))

        # 이미 수집된 dn 제외
        already = existing.get(ym, set())
        new_entries = [e for e in all_entries if e.dn not in already]

        log.info(f"    전체 {len(all_entries)}편 중 신규 {len(new_entries)}편")

        # 신규 논문 상세 수집
        ym_year  = ym[:4]
        ym_month = ym[4:]

        for i, entry in enumerate(new_entries, 1):
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            dn = entry.dn
            log.info(f"      [{i}/{len(new_entries)}] dn={dn} {entry.title_ko[:40]}...")

            detail = fetch_detail(dn, ym)
            if not detail:
                log.warning(f"        → detail 실패")
                total_failed += 1
                continue

            # 제목 정리 (원문보기 이후 제거)
            title_ko = detail.get("title_ko") or entry.title_ko
            title_ko = re.sub(r"\s*원문보기.*$", "", title_ko).strip()

            paper_data = {
                "dn": dn,
                "source": "conference",
                "organCode2": ORGANCODE2,
                "yearmonth": ym,
                "year": ym_year,
                "month": ym_month,
                "title_ko": title_ko,
                "title_en": detail.get("title_en", ""),
                "authors": detail.get("authors", []),
                "affiliation": detail.get("affiliation", ""),
                "abstract_ko": detail.get("abstract_ko", ""),
                "abstract_en": detail.get("abstract_en", ""),
                "keywords": detail.get("keywords", {"ko": [], "en": []}),
                "volume": detail.get("volume", ""),
                "issue": detail.get("issue", ""),
                "page": detail.get("page", "") or entry.page,
                "issn": detail.get("issn", ""),
                "listing_url": make_listing_url(ym),
                "detail_url": make_detail_url(dn, ym),
                "scraped_at": datetime.now().isoformat(),
            }

            # JSON 저장
            jf = conf_meta / f"{dn}.json"
            jf.write_text(json.dumps(paper_data, ensure_ascii=False, indent=2), encoding="utf-8")

            # MD 저장
            md_path = conf_papers / f"{dn}.md"
            md_path.write_text(rebuild_markdown(paper_data), encoding="utf-8")

            total_added += 1
            log.info(f"        ✓ 저장 완료")

    print(f"\n{'='*60}")
    print(f"  완료: {total_added}편 추가, {total_failed}편 실패")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
