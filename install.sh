#!/bin/bash
# KCI 콘크리트학회 논문 수집 시스템 - macOS 설치 스크립트
# 실행: bash install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=================================================="
echo " KCI 콘크리트학회 논문 수집 시스템 설치"
echo "=================================================="
echo ""

# Python 확인
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3가 필요합니다."
    echo "   설치: https://www.python.org/downloads/"
    exit 1
fi

echo "✓ Python: $(python3 --version)"

# 가상환경 생성
echo ""
echo "[1/3] 가상환경 생성 (.venv)..."
python3 -m venv "$VENV_DIR"
echo "✓ 가상환경 생성됨: $VENV_DIR"

# 패키지 설치
echo ""
echo "[2/3] 패키지 설치..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install \
    requests \
    beautifulsoup4 \
    lxml \
    tqdm \
    networkx \
    -q

echo "✓ 패키지 설치 완료"

# 디렉토리 구조 생성
echo ""
echo "[3/3] 디렉토리 초기화..."
mkdir -p "$SCRIPT_DIR/meta/journal" "$SCRIPT_DIR/meta/conference"
mkdir -p "$SCRIPT_DIR/papers/journal" "$SCRIPT_DIR/papers/conference"
mkdir -p "$SCRIPT_DIR/logs"
echo "✓ 디렉토리 생성됨"

echo ""
echo "=================================================="
echo " 설치 완료!"
echo ""
echo " 사용법 (가상환경 자동 사용):"
echo ""
echo "   # 전체 수집 (1989년~현재, 수 시간 소요)"
echo "   python3 run.py"
echo ""
echo "   # 최근 5년치만 (테스트 권장)"
echo "   python3 run.py --years 5"
echo ""
echo "   # 학회지만 / 학술대회만"
echo "   python3 run.py --source journal"
echo "   python3 run.py --source conference"
echo ""
echo "   # 현황 확인"
echo "   python3 run.py --stats"
echo ""
echo "   (Ctrl+C로 중단해도 다음 실행 시 이어서 진행됩니다)"
echo "=================================================="
