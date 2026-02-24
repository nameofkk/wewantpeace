#!/bin/bash
# WeWantPeace 테스트 실행 스크립트
# 사용법: bash scripts/run_tests.sh [옵션]
#   -u: 단위 테스트만
#   -i: 통합 테스트만
#   -c: 커버리지 포함

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# 가상환경 활성화 (있으면)
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 의존성 설치 확인
pip install -q pytest pytest-asyncio pytest-cov fakeredis aiosqlite

# 환경변수 설정 (테스트용)
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export REDIS_URL="redis://localhost:6379/0"
export TELEGRAM_BOT_TOKEN="test-token"

echo "============================================"
echo "  WeWantPeace 테스트 실행"
echo "  $(date)"
echo "============================================"

PYTEST_ARGS="-v --tb=short"

case "$1" in
    -u|--unit)
        echo "단위 테스트만 실행..."
        PYTEST_ARGS="$PYTEST_ARGS -m unit"
        ;;
    -i|--integration)
        echo "통합 테스트만 실행..."
        PYTEST_ARGS="$PYTEST_ARGS -m integration"
        ;;
    -c|--coverage)
        echo "커버리지 포함 전체 테스트..."
        PYTEST_ARGS="$PYTEST_ARGS --cov=backend --cov=worker --cov-report=term-missing --cov-report=html:htmlcov"
        ;;
    *)
        echo "전체 테스트 실행..."
        ;;
esac

python -m pytest backend/tests/ $PYTEST_ARGS

echo ""
echo "✅ 테스트 완료"
