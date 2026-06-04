# Share Link Deferred Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 공유 링크로 들어온 첫 사용자에게 콘텐츠를 먼저 보여주고, 하단 CTA 배너로 온보딩을 부드럽게 유도한다.

**Architecture:** OnboardingGuard에 공유 페이지 판별 로직 추가 → 공유 페이지면 리다이렉트 스킵 + sessionStorage 플래그 세팅. 새 OnboardingBanner 컴포넌트가 CTA를 표시하고, PWA/App 배너는 온보딩 미완료 시 억제.

**Tech Stack:** Next.js 14 App Router, React, TypeScript, Tailwind CSS, Zustand, lucide-react

---

### Task 1: i18n 키 추가

**Files:**
- Modify: `frontend/lib/i18n.ts:1333` (ko 블록, welcome_cta 근처)
- Modify: `frontend/lib/i18n.ts:2919` (en 블록, welcome_cta 근처)

**Step 1: ko 블록에 2개 키 추가**

`frontend/lib/i18n.ts`의 ko 블록, `welcome_cta: "시작하기",` 바로 아래에 추가:

```typescript
    // 온보딩 CTA 배너 (공유 링크 진입 유저용)
    onboarding_banner_text: "이 이슈가 나에게 미치는 영향 알아보기",
    onboarding_banner_cta: "설정하기",
```

**Step 2: en 블록에 2개 키 추가**

`frontend/lib/i18n.ts`의 en 블록, `welcome_cta: "Get Started",` 바로 아래에 추가:

```typescript
    // Onboarding CTA banner (for share link visitors)
    onboarding_banner_text: "See how this affects you",
    onboarding_banner_cta: "Set up",
```

**Step 3: 빌드 검증**

Run: `cd ~/Projects/wewantpeace/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: 에러 없음 (아직 사용 안 하므로 warning만 가능)

**Step 4: Commit**

```bash
cd ~/Projects/wewantpeace && git add frontend/lib/i18n.ts && git commit -m "feat: add i18n keys for onboarding CTA banner"
```

---

### Task 2: OnboardingGuard 수정 — 공유 페이지 리다이렉트 스킵

**Files:**
- Modify: `frontend/components/ui/onboarding-guard.tsx`

**Step 1: 공유 페이지 판별 + 리다이렉트 스킵 로직 추가**

`frontend/components/ui/onboarding-guard.tsx` 전체를 다음으로 교체:

```typescript
"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth, getFirebaseAuth } from "@/lib/auth";
import { SplashScreen } from "./splash-screen";

/** 공유 링크로 접근 가능한 경로들 */
const SHAREABLE_PATHS = ["/issues/", "/feed", "/map", "/tension"];

function isShareablePage(pathname: string): boolean {
  return SHAREABLE_PATHS.some((p) => pathname.startsWith(p));
}

/**
 * 온보딩 완료 여부를 localStorage로 체크하여
 * 미완료 시 /onboarding으로 리다이렉트.
 * 단, 공유 페이지로 진입한 경우 리다이렉트를 스킵하고 콘텐츠를 먼저 보여줌.
 * 스플래시 화면을 오버레이로 표시하여 children은 항상 렌더링 (데이터 prefetch 가능).
 */
export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { loading: authLoading } = useAuth();
  const [checked, setChecked] = useState(false);
  const [splashVisible, setSplashVisible] = useState(true);
  const mountTime = useRef(Date.now());

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    const pathname = window.location.pathname;
    const isOnboardingPage = pathname === "/onboarding";
    const isAdminPage = pathname.startsWith("/admin");

    // 로그인 상태면 온보딩 자동 완료 처리 (이중 리다이렉트 방지)
    const auth = getFirebaseAuth();
    const isLoggedIn =
      !!localStorage.getItem("dev_uid") || !!auth?.currentUser;
    if (!done && isLoggedIn) {
      localStorage.setItem("onboarding_done", "true");
      setChecked(true);
      return;
    }

    // 공유 페이지: 온보딩 미완료여도 리다이렉트 스킵, 플래그만 세팅
    if (!done && isShareablePage(pathname) && !isOnboardingPage) {
      sessionStorage.setItem("wwp_share_entry", "true");
      sessionStorage.setItem("wwp_return_url", pathname + window.location.search);
      setChecked(true);
      return;
    }

    if (!done && !isOnboardingPage && !isAdminPage) {
      router.replace("/onboarding");
    }
    setChecked(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 마운트 시 1회만 실행

  // 온보딩 체크 + auth 로딩 완료 시 최소 800ms 보장 후 스플래시 해제
  useEffect(() => {
    if (!checked || authLoading) return;

    const elapsed = Date.now() - mountTime.current;
    const remaining = Math.max(0, 800 - elapsed);

    const timer = setTimeout(() => setSplashVisible(false), remaining);
    return () => clearTimeout(timer);
  }, [checked, authLoading]);

  // 안전 타임아웃: auth 로딩이 3초 이상 걸리면 강제 해제
  useEffect(() => {
    const timer = setTimeout(() => setSplashVisible(false), 3000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <>
      <SplashScreen visible={splashVisible} />
      {children}
    </>
  );
}
```

핵심 변경: 42-47행 — 공유 페이지면 `sessionStorage`에 플래그 세팅 후 리다이렉트 없이 `return`.

**Step 2: 빌드 검증**

Run: `cd ~/Projects/wewantpeace/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: 에러 없음

**Step 3: Commit**

```bash
cd ~/Projects/wewantpeace && git add frontend/components/ui/onboarding-guard.tsx && git commit -m "feat: skip onboarding redirect for shareable pages"
```

---

### Task 3: OnboardingBanner 컴포넌트 생성

**Files:**
- Create: `frontend/components/ui/OnboardingBanner.tsx`

**Step 1: 컴포넌트 작성**

```typescript
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, X } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { LogoIcon } from "@/components/ui/logo-icon";

/**
 * 공유 링크로 진입한 온보딩 미완료 유저에게 표시하는 하단 CTA 배너.
 *
 * 표시 조건:
 *  - onboarding_done === null (미완료)
 *  - sessionStorage.wwp_share_entry === "true"
 *
 * 동작:
 *  - "설정하기" → /onboarding (returnUrl은 이미 sessionStorage에 저장됨)
 *  - X 닫기 → onboarding_done=true (자유 이용, 홈에서 WelcomeModal 표시)
 */
export function OnboardingBanner() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    const shareEntry = sessionStorage.getItem("wwp_share_entry");
    if (!done && shareEntry === "true") {
      // 약간의 딜레이로 콘텐츠가 먼저 보이도록
      const timer = setTimeout(() => setVisible(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!visible) return null;

  function handleSetup() {
    router.push("/onboarding");
  }

  function handleDismiss() {
    localStorage.setItem("onboarding_done", "true");
    // wwp_welcome_seen은 세팅하지 않음 → 홈에서 WelcomeModal 표시
    sessionStorage.removeItem("wwp_share_entry");
    setVisible(false);
  }

  return (
    <div className="fixed bottom-[72px] left-4 right-4 z-50 rounded-xl border border-blue-500/30 shadow-xl p-3.5 flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300"
      style={{ background: "linear-gradient(135deg, rgba(15,23,42,0.97) 0%, rgba(30,41,59,0.97) 100%)" }}
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/15">
        <LogoIcon height={20} hideText />
      </div>
      <p className="flex-1 text-[12px] font-medium text-slate-200 leading-snug min-w-0">
        {t(lang, "onboarding_banner_text" as any)}
      </p>
      <button
        onClick={handleSetup}
        className="shrink-0 flex items-center gap-1 rounded-lg px-3 py-1.5 text-[11px] font-bold text-white transition-colors"
        style={{ background: "linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)" }}
      >
        {t(lang, "onboarding_banner_cta" as any)}
        <ArrowRight className="h-3 w-3" />
      </button>
      <button
        onClick={handleDismiss}
        className="shrink-0 rounded-lg p-1 text-slate-400 hover:text-slate-200 hover:bg-white/10 transition-colors"
        aria-label={lang === "ko" ? "닫기" : "Close"}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
```

**Step 2: 빌드 검증**

Run: `cd ~/Projects/wewantpeace/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: 에러 없음

**Step 3: Commit**

```bash
cd ~/Projects/wewantpeace && git add frontend/components/ui/OnboardingBanner.tsx && git commit -m "feat: add OnboardingBanner CTA for share link visitors"
```

---

### Task 4: MainLayout에 OnboardingBanner 추가

**Files:**
- Modify: `frontend/app/(main)/layout.tsx`

**Step 1: import 추가**

`frontend/app/(main)/layout.tsx` 상단의 import 섹션에 추가:

```typescript
import { OnboardingBanner } from "@/components/ui/OnboardingBanner";
```

**Step 2: JSX에 OnboardingBanner 배치**

`<PWAInstallPrompt />` 바로 위에 추가:

```diff
      <BottomNav />
+     <OnboardingBanner />
      <PWAInstallPrompt />
      <SmartAppBanner />
```

**Step 3: 빌드 검증**

Run: `cd ~/Projects/wewantpeace/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: 에러 없음

**Step 4: Commit**

```bash
cd ~/Projects/wewantpeace && git add frontend/app/\(main\)/layout.tsx && git commit -m "feat: mount OnboardingBanner in main layout"
```

---

### Task 5: PWAInstallPrompt — 온보딩 미완료 시 억제

**Files:**
- Modify: `frontend/components/ui/pwa-install-prompt.tsx:33-34`

**Step 1: useEffect 시작부에 온보딩 체크 추가**

`frontend/components/ui/pwa-install-prompt.tsx`의 `useEffect` 내부, `if (isDismissed() || isTossMiniApp()) return;` 바로 아래에 추가:

```typescript
    // 온보딩 미완료 유저에게는 표시 안 함 (OnboardingBanner 우선)
    if (!localStorage.getItem("onboarding_done")) return;
```

변경 후 useEffect 시작부:

```typescript
  useEffect(() => {
    if (isDismissed() || isTossMiniApp()) return;
    // 온보딩 미완료 유저에게는 표시 안 함 (OnboardingBanner 우선)
    if (!localStorage.getItem("onboarding_done")) return;

    const handler = (e: Event) => {
```

**Step 2: 빌드 검증**

Run: `cd ~/Projects/wewantpeace/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: 에러 없음

**Step 3: Commit**

```bash
cd ~/Projects/wewantpeace && git add frontend/components/ui/pwa-install-prompt.tsx && git commit -m "feat: suppress PWA banner when onboarding incomplete"
```

---

### Task 6: SmartAppBanner — 온보딩 미완료 시 억제

**Files:**
- Modify: `frontend/components/ui/smart-app-banner.tsx:33-35`

**Step 1: useEffect 시작부에 온보딩 체크 추가**

`frontend/components/ui/smart-app-banner.tsx`의 `useEffect` 내부, `if (isNativeApp() || isStandalone() || isTossMiniApp()) return;` 바로 아래에 추가:

```typescript
    // 온보딩 미완료 유저에게는 표시 안 함 (OnboardingBanner 우선)
    if (!localStorage.getItem("onboarding_done")) return;
```

변경 후 useEffect 시작부:

```typescript
  useEffect(() => {
    // 네이티브 앱(TWA/iOS), standalone, 토스 미니앱이면 표시 안 함
    if (isNativeApp() || isStandalone() || isTossMiniApp()) return;
    // 온보딩 미완료 유저에게는 표시 안 함 (OnboardingBanner 우선)
    if (!localStorage.getItem("onboarding_done")) return;

    // 72시간 내 닫은 적 있으면 무시
```

**Step 2: 빌드 검증**

Run: `cd ~/Projects/wewantpeace/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: 에러 없음

**Step 3: Commit**

```bash
cd ~/Projects/wewantpeace && git add frontend/components/ui/smart-app-banner.tsx && git commit -m "feat: suppress app banner when onboarding incomplete"
```

---

### Task 7: 통합 빌드 검증

**Step 1: TypeScript 전체 빌드**

Run: `cd ~/Projects/wewantpeace/frontend && npx tsc --noEmit --pretty 2>&1 | tail -5`
Expected: 에러 없음

**Step 2: Next.js 빌드**

Run: `cd ~/Projects/wewantpeace/frontend && npm run build 2>&1 | tail -20`
Expected: 빌드 성공

**Step 3: 수동 테스트 체크리스트 (로컬 또는 프로덕션)**

1. 시크릿 모드에서 `/issues/아무ID` 접속 → 콘텐츠 표시 + 하단 CTA 배너 확인
2. CTA "설정하기" 클릭 → 온보딩 페이지 이동 확인
3. 온보딩 완료 후 → 원래 이슈 페이지로 복귀 확인
4. 시크릿 모드에서 `/issues/아무ID` 접속 → X 닫기 → 자유 이용 확인
5. 홈 이동 시 WelcomeModal 표시 확인
6. PWA/앱 배너가 온보딩 미완료 시 안 뜨는지 확인
7. 루트(`/`) 직접 접속 → 기존대로 온보딩으로 리다이렉트 확인

---

### Task 8: 배포

**Step 1: Git push**

```bash
cd ~/Projects/wewantpeace && git push
```

**Step 2: Railway frontend 배포**

```bash
cd ~/Projects/wewantpeace
cat railway.json | grep dockerfilePath  # frontend용인지 확인
RAILWAY_API_TOKEN=383ab19c-f63d-4ad0-ae47-ef816b79645b /home/krshin7/.npm-global/bin/railway up --service frontend --detach
```

**Step 3: 토스 .ait 빌드 (선택)**

프론트엔드 코드만 변경이므로 토스 배포가 필요하면:

```bash
cd ~/Projects/wewantpeace/frontend && sh build-toss.sh
cp ~/Projects/wewantpeace/frontend/wewantpeace.ait "/mnt/c/Users/krshi/OneDrive/바탕 화면/"
```

→ 토스 콘솔에서 수동 업로드
