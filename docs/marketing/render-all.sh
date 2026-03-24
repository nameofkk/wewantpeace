#!/bin/bash
# WeWantPeace Newsletter — Batch Renderer
# Usage: ./render-all.sh [variant-name]
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="../../.venv/bin/python"
FILTER="${1:-}"
PASS=0
FAIL=0

render() {
  local name="$1" template="$2" data="$3" output="$4"
  if [[ -n "$FILTER" && "$name" != "$FILTER" ]]; then return; fi
  echo "--- $name ---"
  if [[ ! -f "$template" || ! -f "$data" ]]; then
    echo "  SKIP: missing file"; FAIL=$((FAIL + 1)); return
  fi
  RESULT=$($PYTHON render-newsletter.py --template "$template" --data "$data" --output "$output" 2>&1)
  echo "  $RESULT"
  if echo "$RESULT" | grep -q "WARNING"; then
    FAIL=$((FAIL + 1))
  else
    PASS=$((PASS + 1))
  fi
}

render "vol1-us" "newsletter-v1-final-en.html" "vol1-us-sample.json" "newsletter-v1-rendered-us.html"
render "vol1-kr" "newsletter-v1-final-ko.html" "vol1-kr-sample.json" "newsletter-v1-rendered-kr.html"

echo "=== $PASS passed, $FAIL warnings ==="
[[ $FAIL -eq 0 ]]
