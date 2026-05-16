"""
KCI 콘크리트학회 논문 메타데이터 수집기 v2
=============================================
대상: https://paper.cricit.kr/user/listview/kci2018/
수집 항목: 제목(KO/EN), 저자(KO/EN), 소속, 초록(KO/EN), 키워드(KO/EN),
           권호, 페이지, ISSN — 로그인 불필요

실행:
    python3 crawl/scraper.py                         # 전체 (1989~현재)
    python3 crawl/scraper.py --source journal        # 학회지만
    python3 crawl/scraper.py --source conference     # 학술대회만
    python3 crawl/scraper.py --years 5               # 최근 5년만
    python3 crawl/scraper.py --from-year 2010        # 2010년부터
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup

# ── 상수 ──────────────────────────────────────────────────────────────────────

BASE_URL = "https://paper.cricit.kr/user/listview/kci2018"

SOURCES: dict[str, dict] = {
    "journal": {
        "organCode2": "kci01",
        "label": "콘크리트학회논문집",
        "months": ["02", "04", "06", "08", "10", "12"],
        "start_year": 1989,
    },
    "conference": {
        "organCode2": "kci03",
        "label": "학술대회논문집",
        "months": ["04", "05", "06", "10", "11", "12"],
        "start_year": 1989,
    },
}

ROOT = Path(__file__).parent.parent
META_DIR = ROOT / "meta"
PAPERS_DIR = ROOT / "papers"
LOGS_DIR = ROOT / "logs"
PROGRESS_FILE = ROOT / "logs" / "progress.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

DELAY_MIN = 1.5   # 요청 간 최소 대기(초)
DELAY_MAX = 3.0   # 요청 간 최대 대기(초)


# ── 로깅 ──────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            LOGS_DIR / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

@dataclass
class Author:
    ko: str = ""
    en: str = ""
    affiliation: str = ""


@dataclass
class Keywords:
    ko: list[str] = field(default_factory=list)
    en: list[str] = field(default_factory=list)


@dataclass
class Paper:
    dn: str = ""
    source: str = ""          # "journal" | "conference"
    organCode2: str = ""
    yearmonth: str = ""
    year: str = ""
    month: str = ""

    title_ko: str = ""
    title_en: str = ""
    authors: list[Author] = field(default_factory=list)
    affiliation: str = ""
    abstract_ko: str = ""
    abstract_en: str = ""
    keywords: Keywords = field(default_factory=Keywords)

    volume: str = ""
    issue: str = ""
    page: str = ""
    issn: str = ""

    listing_url: str = ""
    detail_url: str = ""
    scraped_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── 파싱 유틸 ─────────────────────────────────────────────────────────────────

def parse_authors(raw: str) -> list[Author]:
    """
    "김유민(Yu-Min Kim) ; 이문석(Moon-Seok Lee) ; ..."
    → [Author(ko="김유민", en="Yu-Min Kim"), ...]
    """
    authors: list[Author] = []
    if not raw:
        return authors

    for part in re.split(r"\s*;\s*", raw.strip()):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([^(]+)\(([^)]+)\)\s*$", part)
        if m:
            ko = m.group(1).strip()
            en = m.group(2).strip()
            authors.append(Author(ko=ko, en=en))
        else:
            # 영문 이름 없는 경우
            authors.append(Author(ko=part))
    return authors


def parse_keywords(raw: str) -> Keywords:
    """
    키워드 셀에서 한국어/영어 키워드 분리
    형식1: "콘크리트 ; 압축강도 concrete ; compressive strength"
    형식2: "콘크리트; concrete; 압축강도; compressive strength"
    """
    if not raw:
        return Keywords()

    # 세미콜론으로 분리
    parts = [p.strip() for p in re.split(r"[;；]", raw) if p.strip()]

    ko_kws: list[str] = []
    en_kws: list[str] = []

    for part in parts:
        # 한글이 포함되면 한국어 키워드
        if re.search(r"[가-힣]", part):
            ko_kws.append(part)
        elif part:
            en_kws.append(part)

    return Keywords(ko=ko_kws, en=en_kws)


def clean_text(text: str) -> str:
    """공백·개행 정리"""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── HTTP 요청 ─────────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)


def get_page(url: str, retries: int = 3) -> BeautifulSoup | None:
    """URL 가져와서 BeautifulSoup 반환. 실패 시 None."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            log.warning(f"  [시도 {attempt}/{retries}] 요청 실패: {url} → {e}")
            if attempt < retries:
                time.sleep(random.uniform(3, 6))
    log.error(f"  최종 실패: {url}")
    return None


def polite_delay() -> None:
    """요청 간 랜덤 대기 (서버 부하 방지)"""
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


# ── 목록 페이지 파싱 ──────────────────────────────────────────────────────────

def make_listing_url(organCode2: str, yearmonth: str, page: int = 1) -> str:
    url = (
        f"{BASE_URL}/gby_rdoc.asp"
        f"?step=4&organCode=kci&organCode2={organCode2}"
        f"&yearmonth={yearmonth}&usernum=0&seid=&tbnm=r"
    )
    if page > 1:
        url += f"&page={page}&spage={page}"
    return url


def make_detail_url(dn: str, organCode2: str, yearmonth: str) -> str:
    return (
        f"{BASE_URL}/doc_rdoc.asp"
        f"?catvalue=3&returnVal=RD_R&organCode=kci&organCode2={organCode2}"
        f"&yearmonth={yearmonth}&page=1&dn={dn}&step=&usernum=0&seid="
    )


class ListingEntry(NamedTuple):
    dn: str
    title_ko: str
    page: str


def _parse_entries_from_soup(soup: BeautifulSoup) -> list[ListingEntry]:
    """soup에서 ListingEntry 목록 파싱 (단일 페이지)"""
    entries: list[ListingEntry] = []
    rows = soup.select("table.tb-list tr, table tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        dn = ""
        title_ko = ""
        page_info = ""

        # 링크에서 dn 추출
        link = row.find("a", onclick=True) or row.find("a", href=True)
        full_onclick = ""
        if link:
            full_onclick = link.get("onclick", "") or link.get("href", "")

        dn_match = re.search(r"[?&]dn=(\d+)", full_onclick)
        if not dn_match:
            dn_match = re.search(r"goDetail\('?(\d+)'?\)", full_onclick)
        if not dn_match:
            for cell in cells:
                for cl in cell.find_all("a"):
                    href = cl.get("href", "") + cl.get("onclick", "")
                    m = re.search(r"[?&]dn=(\d+)", href)
                    if m:
                        dn_match = m
                        break
                if dn_match:
                    break

        if not dn_match:
            continue

        dn = dn_match.group(1)

        # 제목 추출 (가장 긴 텍스트 셀, [표지]/[목차] 스킵)
        for cell in cells:
            text = clean_text(cell.get_text())
            if re.search(r"\[표지\]|\[목차\]|^\[안내\]|^\[상세일정\]|표지|목차", text):
                title_ko = ""
                dn = ""
                break
            if len(text) > len(title_ko) and len(text) > 5:
                title_ko = text

        if not dn:
            continue

        # 페이지 정보
        for cell in reversed(cells):
            text = clean_text(cell.get_text())
            if re.match(r"^pp?\.\s*\d", text) or re.match(r"^\d+[-~]\d+$", text):
                page_info = text
                break

        entries.append(ListingEntry(dn=dn, title_ko=title_ko, page=page_info))

    return entries


def _parse_total_pages(soup: BeautifulSoup) -> int:
    """'[Page 1 of 14]' 형태에서 총 페이지 수 파싱"""
    text = soup.get_text()
    m = re.search(r"\[Page\s+\d+\s+of\s+(\d+)\]", text)
    return int(m.group(1)) if m else 1


def scrape_issue_listing(organCode2: str, yearmonth: str) -> list[ListingEntry]:
    """
    특정 권호의 논문 목록 수집 (전체 페이지 순회)
    반환: [(dn, title_ko, page), ...]
    """
    # ── 1페이지 ──────────────────────────────────────────────────────────────
    url = make_listing_url(organCode2, yearmonth, page=1)
    soup = get_page(url)
    if soup is None:
        return []

    # "등록된 데이타가 없습니다" 체크
    if soup.find(string=re.compile(r"등록된\s*데이타가\s*없습니다")):
        return []

    all_entries: list[ListingEntry] = _parse_entries_from_soup(soup)
    total_pages = _parse_total_pages(soup)

    # ── 2~N 페이지 ────────────────────────────────────────────────────────────
    for p in range(2, total_pages + 1):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        p_url = make_listing_url(organCode2, yearmonth, page=p)
        p_soup = get_page(p_url)
        if p_soup is None:
            log.warning(f"    목록 {yearmonth} p.{p} 수집 실패 — 이후 페이지 중단")
            break
        all_entries.extend(_parse_entries_from_soup(p_soup))

    if total_pages > 1:
        log.info(f"    목록 {yearmonth}: {total_pages}페이지, {len(all_entries)}편")

    # 중복 제거
    seen: set[str] = set()
    unique: list[ListingEntry] = []
    for e in all_entries:
        if e.dn not in seen:
            seen.add(e.dn)
            unique.append(e)

    return unique


# ── 상세 페이지 파싱 ──────────────────────────────────────────────────────────

def scrape_paper_detail(
    dn: str,
    organCode2: str,
    yearmonth: str,
    fallback_title: str = "",
) -> dict:
    """
    논문 상세 페이지에서 전체 메타데이터 수집
    """
    url = make_detail_url(dn, organCode2, yearmonth)
    soup = get_page(url)

    result: dict = {
        "title_ko": fallback_title,
        "title_en": "",
        "authors_raw": "",
        "authors": [],
        "affiliation": "",
        "abstract_ko": "",
        "abstract_en": "",
        "keywords_raw": "",
        "keywords": {"ko": [], "en": []},
        "volume": "",
        "issue": "",
        "page": "",
        "issn": "",
    }

    if soup is None:
        return result

    # ── 제목 ──────────────────────────────────────────────────────────────────
    # 실제 th 레이블: "논문명" — KO/EN이 "/" 로 연결된 경우 분리
    # 예: "하수슬러지...특성/Properties of Eco-Construction..."
    title_el = soup.find(
        "th", string=re.compile(r"논문명|제\s*목|논문\s*제목|Title.*KO|한국어\s*제목", re.I)
    )
    if title_el:
        sibling = title_el.find_next_sibling("td")
        if sibling:
            raw_title = clean_text(sibling.get_text())
            # "한국어 제목/English Title" 형식 분리
            sep = re.search(r"^(.+?)\s*/\s*([A-Z].+)$", raw_title)
            if sep:
                result["title_ko"] = sep.group(1).strip() or fallback_title
                result["title_en"] = sep.group(2).strip()
            else:
                result["title_ko"] = raw_title or fallback_title

    # 제목을 못 찾은 경우 h2/h3/strong 등 시도
    if not result["title_ko"] or result["title_ko"] == fallback_title:
        for tag in ["h2", "h3", "h4", "strong"]:
            el = soup.find(tag)
            if el:
                text = clean_text(el.get_text())
                if len(text) > 5 and not re.search(r"KCI|콘크리트학회", text):
                    result["title_ko"] = text
                    break

    # ── 저자 ──────────────────────────────────────────────────────────────────
    # 실제 th 레이블: "저자명"
    author_el = soup.find(
        "th", string=re.compile(r"저자명|저\s*자|Author", re.I)
    )
    if author_el:
        sibling = author_el.find_next_sibling("td")
        if sibling:
            raw = clean_text(sibling.get_text())
            result["authors_raw"] = raw
            result["authors"] = [asdict(a) for a in parse_authors(raw)]

    # ── 소속 ──────────────────────────────────────────────────────────────────
    affil_el = soup.find(
        "th", string=re.compile(r"소\s*속|Affiliation", re.I)
    )
    if affil_el:
        sibling = affil_el.find_next_sibling("td")
        if sibling:
            result["affiliation"] = clean_text(sibling.get_text())

    # ── 초록 ──────────────────────────────────────────────────────────────────
    # 실제 th 레이블: "요약1" (국문), "요약2" (영문)
    abstract_ko_el = soup.find(
        "th", string=re.compile(r"요약\s*1|초\s*록|국문\s*초록|한국어\s*초록", re.I)
    )
    if abstract_ko_el:
        sibling = abstract_ko_el.find_next_sibling("td")
        if sibling:
            result["abstract_ko"] = clean_text(sibling.get_text())

    abstract_en_el = soup.find(
        "th", string=re.compile(r"요약\s*2|Abstract|영문\s*초록|영어\s*초록", re.I)
    )
    if abstract_en_el:
        sibling = abstract_en_el.find_next_sibling("td")
        if sibling:
            result["abstract_en"] = clean_text(sibling.get_text())

    # ── 키워드 ────────────────────────────────────────────────────────────────
    # 실제 th 레이블: "주제어"
    kw_el = soup.find(
        "th", string=re.compile(r"주제어|핵심어|키워드|Keyword", re.I)
    )
    if kw_el:
        sibling = kw_el.find_next_sibling("td")
        if sibling:
            raw_kw = clean_text(sibling.get_text())
            result["keywords_raw"] = raw_kw
            kw_parsed = parse_keywords(raw_kw)
            result["keywords"] = {"ko": kw_parsed.ko, "en": kw_parsed.en}

    # ── 권호·페이지·ISSN ──────────────────────────────────────────────────────
    # 실제 구조: "수록사항" → "한국콘크리트학회논문집 , Vol.19 No.6"
    #            "페이지"   → "시작페이지(667) 총페이지(10)"
    #            "ISSN "    → "1229-5515"
    for th in soup.find_all("th"):
        label = clean_text(th.get_text())
        td = th.find_next_sibling("td")
        if not td:
            continue
        val = clean_text(td.get_text())

        if re.search(r"수록사항", label):
            # "Vol.19 No.6" 형식에서 권호 추출
            vol_m = re.search(r"Vol\.?\s*(\d+)", val, re.I)
            no_m  = re.search(r"No\.?\s*(\d+)", val, re.I)
            if vol_m:
                result["volume"] = vol_m.group(1)
            if no_m:
                result["issue"] = no_m.group(1)
        elif re.search(r"^페이지$|^Page$|^pp\.", label, re.I):
            # "시작페이지(667) 총페이지(10)" → "pp.667-676"
            start_m = re.search(r"시작페이지\((\d+)\)", val)
            total_m = re.search(r"총페이지\((\d+)\)", val)
            if start_m:
                start = int(start_m.group(1))
                if total_m:
                    end = start + int(total_m.group(1)) - 1
                    result["page"] = f"pp.{start}-{end}"
                else:
                    result["page"] = f"pp.{start}"
            elif re.match(r"pp?\.\s*\d|\d+[-~]\d+", val):
                result["page"] = val
        elif re.search(r"ISSN", label, re.I):
            result["issn"] = val

    return result


# ── 진행 상태 관리 ────────────────────────────────────────────────────────────

def load_progress() -> dict:
    """저장된 진행 상태 로드"""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_progress(progress: dict) -> None:
    """진행 상태 저장"""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def is_done(progress: dict, source: str, yearmonth: str) -> bool:
    return progress.get(source, {}).get(yearmonth) == "done"


def mark_done(progress: dict, source: str, yearmonth: str) -> None:
    progress.setdefault(source, {})[yearmonth] = "done"


# ── 저장 ──────────────────────────────────────────────────────────────────────

def save_paper(paper: Paper) -> None:
    """논문을 JSON 메타데이터 + Markdown으로 저장"""
    source = paper.source

    # JSON 메타데이터
    meta_dir = META_DIR / source
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_path = meta_dir / f"{paper.dn}.json"
    meta_path.write_text(
        json.dumps(paper.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Markdown
    md_dir = PAPERS_DIR / source
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{paper.dn}.md"
    md_path.write_text(build_markdown(paper), encoding="utf-8")


def build_markdown(p: Paper) -> str:
    """YAML 프론트매터 + 본문 마크다운 생성"""
    authors_ko = " ; ".join(a.ko for a in p.authors if a.ko)
    authors_en = " ; ".join(a.en for a in p.authors if a.en)
    kw_ko = ", ".join(p.keywords.ko)
    kw_en = ", ".join(p.keywords.en)

    frontmatter = f"""\
---
id: "{p.dn}"
source: "{p.source}"
organCode2: "{p.organCode2}"
yearmonth: "{p.yearmonth}"
year: "{p.year}"
month: "{p.month}"
title_ko: "{p.title_ko.replace('"', "'")}"
title_en: "{p.title_en.replace('"', "'")}"
authors_ko: "{authors_ko}"
authors_en: "{authors_en}"
affiliation: "{p.affiliation.replace('"', "'")}"
volume: "{p.volume}"
issue: "{p.issue}"
page: "{p.page}"
issn: "{p.issn}"
keywords_ko: {json.dumps(p.keywords.ko, ensure_ascii=False)}
keywords_en: {json.dumps(p.keywords.en, ensure_ascii=False)}
listing_url: "{p.listing_url}"
detail_url: "{p.detail_url}"
scraped_at: "{p.scraped_at}"
---"""

    body_parts = [f"# {p.title_ko}"]
    if p.title_en:
        body_parts.append(f"**{p.title_en}**")
    body_parts.append("")

    body_parts.append(f"**저자 (KO)**: {authors_ko}")
    if authors_en:
        body_parts.append(f"**Authors (EN)**: {authors_en}")
    if p.affiliation:
        body_parts.append(f"**소속**: {p.affiliation}")
    body_parts.append(f"**연도**: {p.year} | **권**: {p.volume} | **호**: {p.issue} | **페이지**: {p.page}")
    body_parts.append("")

    if p.abstract_ko:
        body_parts.append("## 초록")
        body_parts.append(p.abstract_ko)
        body_parts.append("")

    if p.abstract_en:
        body_parts.append("## Abstract")
        body_parts.append(p.abstract_en)
        body_parts.append("")

    if kw_ko or kw_en:
        body_parts.append("## 키워드")
        if kw_ko:
            body_parts.append(f"**한국어**: {kw_ko}")
        if kw_en:
            body_parts.append(f"**English**: {kw_en}")
        body_parts.append("")

    return frontmatter + "\n\n" + "\n".join(body_parts) + "\n"


# ── 메인 수집 로직 ────────────────────────────────────────────────────────────

def generate_yearmonths(
    source: str,
    start_year: int,
    end_year: int,
) -> list[str]:
    """수집 대상 연도·월 목록 생성 (최신순)"""
    months = SOURCES[source]["months"]
    yearmonths: list[str] = []
    for year in range(end_year, start_year - 1, -1):
        for month in reversed(months):
            yearmonths.append(f"{year}{month}")
    return yearmonths


def scrape_source(
    source: str,
    start_year: int,
    end_year: int,
    progress: dict,
) -> tuple[int, int]:
    """
    특정 source(journal/conference)의 전체 기간 수집
    반환: (수집 성공 수, 스킵 수)
    """
    cfg = SOURCES[source]
    organCode2 = cfg["organCode2"]
    label = cfg["label"]

    yearmonths = generate_yearmonths(source, start_year, end_year)
    total_saved = 0
    total_skipped = 0

    log.info(f"\n{'='*60}")
    log.info(f"[{label}] {start_year}~{end_year}년, {len(yearmonths)}개 권호 대상")
    log.info(f"{'='*60}")

    for ym_idx, yearmonth in enumerate(yearmonths, 1):
        year = yearmonth[:4]
        month = yearmonth[4:]

        # 이미 완료된 권호 스킵
        if is_done(progress, source, yearmonth):
            log.info(f"  [{ym_idx}/{len(yearmonths)}] {yearmonth} — 이미 완료, 스킵")
            total_skipped += 1
            continue

        log.info(f"\n  [{ym_idx}/{len(yearmonths)}] {year}년 {month}월호 수집 중...")
        listing_url = make_listing_url(organCode2, yearmonth)

        # 목록 수집
        entries = scrape_issue_listing(organCode2, yearmonth)

        if not entries:
            log.info(f"    → 논문 없음 (빈 권호)")
            mark_done(progress, source, yearmonth)
            save_progress(progress)
            polite_delay()
            continue

        log.info(f"    → {len(entries)}편 발견")

        # 각 논문 상세 수집
        saved_in_issue = 0
        for paper_idx, entry in enumerate(entries, 1):
            dn = entry.dn

            # 이미 저장된 논문 스킵
            meta_path = META_DIR / source / f"{dn}.json"
            if meta_path.exists():
                log.info(f"      [{paper_idx}/{len(entries)}] dn={dn} — 이미 저장됨")
                saved_in_issue += 1
                continue

            log.info(f"      [{paper_idx}/{len(entries)}] dn={dn} '{entry.title_ko[:30]}...'")

            polite_delay()
            detail = scrape_paper_detail(dn, organCode2, yearmonth, entry.title_ko)

            paper = Paper(
                dn=dn,
                source=source,
                organCode2=organCode2,
                yearmonth=yearmonth,
                year=year,
                month=month,
                title_ko=detail.get("title_ko", entry.title_ko),
                title_en=detail.get("title_en", ""),
                authors=[
                    Author(**a) for a in detail.get("authors", [])
                ],
                abstract_ko=detail.get("abstract_ko", ""),
                abstract_en=detail.get("abstract_en", ""),
                keywords=Keywords(
                    ko=detail.get("keywords", {}).get("ko", []),
                    en=detail.get("keywords", {}).get("en", []),
                ),
                volume=detail.get("volume", ""),
                issue=detail.get("issue", ""),
                page=entry.page or detail.get("page", ""),
                issn=detail.get("issn", ""),
                affiliation=detail.get("affiliation", ""),
                listing_url=listing_url,
                detail_url=make_detail_url(dn, organCode2, yearmonth),
                scraped_at=datetime.now().isoformat(),
            )

            save_paper(paper)
            saved_in_issue += 1
            total_saved += 1
            log.info(f"        ✓ 저장 완료")

        # 권호 완료 표시
        mark_done(progress, source, yearmonth)
        save_progress(progress)
        log.info(f"    → {year}년 {month}월호 완료: {saved_in_issue}편")

    return total_saved, total_skipped


# ── 진입점 ────────────────────────────────────────────────────────────────────

def print_stats() -> None:
    """현재까지 수집 현황 출력"""
    j_meta = list((META_DIR / "journal").glob("*.json")) if (META_DIR / "journal").exists() else []
    c_meta = list((META_DIR / "conference").glob("*.json")) if (META_DIR / "conference").exists() else []
    j_md   = list((PAPERS_DIR / "journal").glob("*.md")) if (PAPERS_DIR / "journal").exists() else []
    c_md   = list((PAPERS_DIR / "conference").glob("*.md")) if (PAPERS_DIR / "conference").exists() else []

    print("\n" + "="*55)
    print("  현재 수집 현황")
    print("="*55)
    print(f"  학회지 논문집   JSON: {len(j_meta):5d}편  │  MD: {len(j_md):5d}편")
    print(f"  학술대회 논문집 JSON: {len(c_meta):5d}편  │  MD: {len(c_md):5d}편")
    print(f"  합계            JSON: {len(j_meta)+len(c_meta):5d}편  │  MD: {len(j_md)+len(c_md):5d}편")
    print("="*55 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="KCI 콘크리트학회 논문 메타데이터 수집기")
    parser.add_argument(
        "--source",
        choices=["journal", "conference", "both"],
        default="both",
        help="수집 대상 (기본: both)",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=0,
        help="최근 N년치만 수집 (0 = 전체, 기본: 전체)",
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=0,
        help="특정 연도부터 수집 (기본: 각 source의 시작년도)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="진행 상태 초기화 후 처음부터 수집",
    )
    args = parser.parse_args()

    current_year = datetime.now().year

    # 진행 상태 로드
    progress = {} if args.reset else load_progress()
    if args.reset:
        log.info("진행 상태 초기화")

    sources_to_run = (
        ["journal", "conference"] if args.source == "both" else [args.source]
    )

    print("\n" + "="*55)
    print("  KCI 콘크리트학회 논문 메타데이터 수집기 v2")
    print(f"  대상: {', '.join(sources_to_run)}")
    print("="*55 + "\n")

    total_saved = 0
    total_skipped = 0

    for source in sources_to_run:
        cfg = SOURCES[source]

        # 시작 연도 결정
        if args.from_year:
            start_year = args.from_year
        elif args.years:
            start_year = current_year - args.years + 1
        else:
            start_year = cfg["start_year"]

        saved, skipped = scrape_source(
            source=source,
            start_year=start_year,
            end_year=current_year,
            progress=progress,
        )
        total_saved += saved
        total_skipped += skipped

    log.info(f"\n수집 완료: 새로 저장 {total_saved}편, 스킵 {total_skipped}권호")
    print_stats()


if __name__ == "__main__":
    main()
