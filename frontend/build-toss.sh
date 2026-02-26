#!/bin/sh
set -e

# 1) config 교체
cp next.config.toss.js next.config.js

# 2) 동적 라우트 임시 비활성화
mv "app/(main)/issues/[id]" "app/(main)/issues/_id_bak" 2>/dev/null || true
mv "app/(main)/issues/country/[code]" "app/(main)/issues/country/_code_bak" 2>/dev/null || true
mv "app/(main)/community/[postId]" "app/(main)/community/_postId_bak" 2>/dev/null || true

# 3) granite build
npx granite build

# 4) 동적 라우트 복원
mv "app/(main)/issues/_id_bak" "app/(main)/issues/[id]" 2>/dev/null || true
mv "app/(main)/issues/country/_code_bak" "app/(main)/issues/country/[code]" 2>/dev/null || true
mv "app/(main)/community/_postId_bak" "app/(main)/community/[postId]" 2>/dev/null || true

# 5) config 복원 (git에서)
git checkout -- next.config.js
