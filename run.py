"""
KCI 콘크리트학회 논문 수집 시스템 - 메인 실행기

사용법:
    python3 run.py                      # 전체 수집 (1989~현재)
    python3 run.py --years 5            # 최근 5년치
    python3 run.py --source journal     # 학회지만
    python3 run.py --source conference  # 학술대회만
    python3 run.py --stats              # 현황만 출력
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# 가상환경 Python 우선 사용
_VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"
PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable
META_DIR = ROOT / "meta"
PAPERS_DIR = ROOT / "papers"


def print_stats() -> None:
    j_meta = list((META_DIR / "journal").glob("*.json")) if (META_DIR / "journal").exists() else []
    c_meta = list((META_DIR / "conference").glob("*.json")) if (META_DIR / "conference").exists() else []
    j_md   = list((PAPERS_DIR / "journal").glob("*.md")) if (PAPERS_DIR / "journal").exists() else []
    c_md   = list((PAPERS_DIR / "conference").glob("*.md")) if (PAPERS_DIR / "conference").exists() else []

    print("\n" + "="*55)
    print("  수집 현황")
    print("="*55)
    print(f"  학회지 논문집   JSON: {len(j_meta):5d}편  │  MD: {len(j_md):5d}편")
    print(f"  학술대회 논문집 JSON: {len(c_meta):5d}편  │  MD: {len(c_md):5d}편")
    print(f"  합계            JSON: {len(j_meta)+len(c_meta):5d}편  │  MD: {len(j_md)+len(c_md):5d}편")
    print("="*55)
    print(f"\n  저장 위치:")
    print(f"    메타데이터: {META_DIR}/")
    print(f"    마크다운:   {PAPERS_DIR}/\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="KCI 콘크리트학회 논문 수집 시스템")
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
        help="최근 N년치만 수집 (0 = 전체)",
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=0,
        help="특정 연도부터 수집",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="처음부터 다시 수집 (진행 상태 무시)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="현황만 출력하고 종료",
    )
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    # 스크래퍼 실행
    cmd = [PYTHON, "crawl/scraper.py"]
    if args.source != "both":
        cmd += ["--source", args.source]
    if args.years:
        cmd += ["--years", str(args.years)]
    if args.from_year:
        cmd += ["--from-year", str(args.from_year)]
    if args.reset:
        cmd += ["--reset"]

    print("\n" + "="*55)
    print("  KCI 콘크리트학회 논문 수집 시스템")
    print("="*55)
    print(f"  Python: {PYTHON}")
    print(f"  명령: {' '.join(cmd)}")
    print("  중단: Ctrl+C (다음 실행 시 이어서 수집됩니다)")
    print("="*55 + "\n")

    try:
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"\n⚠️  스크래퍼가 비정상 종료되었습니다 (코드: {result.returncode})")
            print("   logs/ 폴더의 로그 파일을 확인하세요.")
            sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\n⏸  수집 중단됨. 다음 실행 시 이어서 진행됩니다.")

    print_stats()


if __name__ == "__main__":
    main()
