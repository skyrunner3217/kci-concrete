"""
수집된 데이터 후처리 스크립트
1. 제목 정리: "논문제목원문보기 / ENDNOTE / 저자..." → "논문제목"
2. JSON + MD 파일 동시 업데이트

실행:
    python3 fix_data.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
META_DIR = ROOT / "meta"
PAPERS_DIR = ROOT / "papers"


def clean_title(raw: str) -> str:
    """
    목록 페이지에서 긁어온 지저분한 제목 정리.
    형식: "논문제목원문보기 / ENDNOTE / 저자(EN) ; ... - 학회지:Vol.X No.X (YYYY-MM)"
    """
    # "원문보기" 이전까지만 추출
    m = re.match(r"^(.+?)원문보기", raw)
    if m:
        return m.group(1).strip()
    # 없으면 " - 학회지명" 이전까지
    m = re.match(r"^(.+?)\s*-\s*한국콘크리트학회", raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


def rebuild_markdown(d: dict) -> str:
    """JSON 데이터에서 마크다운 재생성"""
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
    detail_url = d.get("detail_url", "")
    scraped_at = d.get("scraped_at", "")

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
detail_url: "{detail_url}"
scraped_at: "{scraped_at}"
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


def main() -> None:
    sources = ["journal", "conference"]
    total_fixed = 0

    for source in sources:
        meta_dir = META_DIR / source
        papers_dir = PAPERS_DIR / source

        if not meta_dir.exists():
            continue

        json_files = sorted(meta_dir.glob("*.json"))
        fixed_in_source = 0

        for jf in json_files:
            d = json.loads(jf.read_text(encoding="utf-8"))
            original_title = d.get("title_ko", "")
            cleaned = clean_title(original_title)

            if cleaned == original_title:
                continue  # 변경 없음

            d["title_ko"] = cleaned

            # JSON 업데이트
            jf.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

            # MD 업데이트
            md_path = papers_dir / (jf.stem + ".md")
            md_path.write_text(rebuild_markdown(d), encoding="utf-8")

            fixed_in_source += 1

        print(f"[{source}] 제목 정리 완료: {fixed_in_source}편")
        total_fixed += fixed_in_source

    print(f"\n총 {total_fixed}편 정리 완료")

    # 샘플 출력
    print("\n[제목 샘플]")
    for source in sources:
        meta_dir = META_DIR / source
        if not meta_dir.exists():
            continue
        for jf in sorted(meta_dir.glob("*.json"))[:3]:
            d = json.loads(jf.read_text(encoding="utf-8"))
            auths = d.get("authors", [])
            if auths and auths[0].get("ko") != "편집부":
                print(f"  {d['title_ko'][:60]}")


if __name__ == "__main__":
    main()
