# 공유 링크 첫 사용자 온보딩 지연 디자인

**날짜:** 2026-03-16
**상태:** 승인됨

## 문제

공유 링크(`/issues/123` 등)로 들어온 첫 사용자가 `OnboardingGuard`에 의해 즉시 `/onboarding`으로 리다이렉트되어, 원래 보려던 콘텐츠를 볼 수 없음. 온보딩 완료 후에도 원래 URL로 복귀하지 않음.

## 해결 방향

공유 페이지로 진입한 첫 사용자에게는 콘텐츠를 먼저 보여주고, 하단 CTA 배너로 온보딩을 부드럽게 유도한다.

## 상세 흐름

```
[첫 사용자] → 공유 링크 /issues/123 진입
  │
  ├─ OnboardingGuard: "공유 페이지" → 리다이렉트 스킵
  │   └─ sessionStorage에 wwp_share_entry=true, wwp_return_url 저장
  │
  ├─ 콘텐츠 정상 표시 (이슈 상세)
  │
  ├─ 하단 CTA 배너 표시 (PWA/앱 배너는 억제)
  │   ├─ "설정하기" 클릭 → /onboarding → 완료 후 returnUrl로 복귀
  │   └─ "X" 닫기 → onboarding_done=true (자유 이용)
  │       └─ wwp_welcome_seen은 미세팅 → 홈에서 WelcomeModal 표시
  │
  └─ [첫 사용자] → 루트 / 또는 /home 직접 진입
      └─ 기존과 동일: /onboarding으로 리다이렉트
```

## 공유 페이지 판별

```ts
const SHAREABLE_PATHS = ["/issues/", "/feed", "/map", "/tension"];
const isSharePage = SHAREABLE_PATHS.some(p => pathname.startsWith(p));
```

## OnboardingGuard 수정

- `onboarding_done` 없어도 공유 페이지면 리다이렉트 안 함
- `sessionStorage`에 `wwp_share_entry=true`와 `wwp_return_url` 저장

## CTA 배너 (OnboardingBanner)

**표시 조건:**
- `onboarding_done` === null
- `sessionStorage.wwp_share_entry` === "true"

**UI:**
- 하단 고정, BottomNav 위
- 그라디언트 배경 (blue → cyan)
- 왼쪽: 텍스트
- 오른쪽: [설정하기] 버튼 + X 닫기

**멘트:**
- 한국어: "이 이슈가 나에게 미치는 영향 알아보기"
- 영어: "See how this affects you"
- 버튼: "설정하기" / "Set up"

**동작:**
- "설정하기" → `router.push("/onboarding")`
- "X" 닫기 → `onboarding_done=true`, 배너 제거

## 배너 우선순위

온보딩 미완료 상태(onboarding_done === null)일 때:
- **OnboardingBanner**: 표시
- **PWAInstallPrompt**: 억제 (조건 추가)
- **SmartAppBanner**: 억제 (조건 추가)

## 온보딩 완료 후 복귀

기존 온보딩 페이지의 `finishOnboarding()`/`handleSkip()`이 이미 `sessionStorage.wwp_return_url`을 체크하여 복귀. 수정 불필요.

## 수정 파일 목록

| 파일 | 변경 내용 |
|------|-----------|
| `components/ui/onboarding-guard.tsx` | 공유 페이지 판별 + 리다이렉트 스킵 |
| `components/ui/OnboardingBanner.tsx` | **신규** — CTA 배너 컴포넌트 |
| `app/(main)/layout.tsx` | OnboardingBanner 추가 |
| `components/ui/pwa-install-prompt.tsx` | 온보딩 미완료 시 억제 조건 |
| `components/ui/smart-app-banner.tsx` | 온보딩 미완료 시 억제 조건 |
| `lib/i18n.ts` | CTA 텍스트 ko/en 추가 |
