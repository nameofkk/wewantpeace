#!/usr/bin/env bash
# WeWantPeace 전체 회귀 테스트 스크립트
# 커버리지 80% 이상을 통과 기준으로 설정
#
# 사용법:
#   chmod +x scripts/run_regression.sh
#   ./scripts/run_regression.sh [--ci]

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT_ROOT/.venv"
PYTEST="$VENV/bin/pytest"
MIN_COVERAGE=80
CI_MODE=false

for arg in "$@"; do
  [ "$arg" = "--ci" ] && CI_MODE=true
done

echo "=== WeWantPeace 회귀 테스트 ==="
echo "프로젝트: $PROJECT_ROOT"
echo "CI 모드: $CI_MODE"
echo ""

# venv 확인
if [ ! -f "$PYTEST" ]; then
  echo "[오류] .venv가 없습니다. python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

cd "$PROJECT_ROOT"

# 테스트 실행
echo "[1/3] pytest 실행 중..."
"$PYTEST" backend/tests/ \
  -v \
  --tb=short \
  --cov=backend/app \
  --cov-report=term-missing \
  --cov-report=html:htmlcov \
  --cov-fail-under=$MIN_COVERAGE \
  -x \
  2>&1 | tee /tmp/wwp_test_results.txt

PYTEST_EXIT=${PIPESTATUS[0]}

# 결과 분석
echo ""
echo "[2/3] 결과 분석..."
PASSED=$(grep -c "PASSED" /tmp/wwp_test_results.txt || echo 0)
FAILED=$(grep -c "FAILED" /tmp/wwp_test_results.txt || echo 0)
echo "  통과: $PASSED"
echo "  실패: $FAILED"

# 커버리지 리포트
echo ""
echo "[3/3] 커버리지 리포트: $PROJECT_ROOT/htmlcov/index.html"

if [ $PYTEST_EXIT -ne 0 ]; then
  echo ""
  echo "❌ 회귀 테스트 실패 (exit code: $PYTEST_EXIT)"
  if [ "$CI_MODE" = true ]; then
    exit $PYTEST_EXIT
  fi
else
  echo ""
  echo "✅ 회귀 테스트 통과 (${PASSED}개 통과, 커버리지 ${MIN_COVERAGE}% 이상)"
fi
