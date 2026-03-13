#!/bin/sh
set -e

# ── 토스 미니앱 빌드 환경변수 ──
export NEXT_PUBLIC_IS_TOSS_MINIAPP=true
export NEXT_PUBLIC_API_URL=https://backend-production-3af7.up.railway.app
export NEXT_PUBLIC_SITE_URL=https://www.wewantpeace.live

# Firebase (railway-frontend.json과 동일)
export NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyBlJf58F_C9hkIry1eEV185-S1EQZmt2ps
export NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=auth.wewantpeace.live
export NEXT_PUBLIC_FIREBASE_PROJECT_ID=wewantpeace-14660
export NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=wewantpeace-14660.firebasestorage.app
export NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=736999139205
export NEXT_PUBLIC_FIREBASE_APP_ID=1:736999139205:web:50b36428d7a3fc25e806ec
export NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-60XVQW25QY

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
