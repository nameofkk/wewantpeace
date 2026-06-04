# WeWantPeace 종합 검토 및 개선 플랜

## Context
플레이스토어/앱스토어 출시 전 최종 검토. 사용자 피드백 반영, 정책 위반 확인, 보안 점검, 버그 수정을 포함한 종합 개선 작업.

---

## 1. 이벤트 타임라인 시간순 정렬 (버그 — 사용자 피드백)

**문제**: 이슈 상세 페이지의 이벤트 타임라인이 `severity` 기준으로 정렬되어 시간이 뒤섞여 보임
**원인**: 백엔드는 `event_time DESC`로 반환하지만, 프론트엔드에서 `.sort((a, b) => b.severity - a.severity)`로 재정렬

**수정 파일**: `frontend/app/(main)/issues/[id]/client.tsx:366-367`
```
변경 전: .sort((a, b) => b.severity - a.severity)
변경 후: .sort((a, b) => new Date(b.event_time).getTime() - new Date(a.event_time).getTime())
```
→ 최신 이벤트가 위에 오는 시간 역순(타임라인 표준)

---

## 2. 피드 정렬 옵션 추가 (기능 — 사용자 피드백)

**문제**: 이슈 목록이 KScore 내림차순 고정, 사용자가 정렬 기준 변경 불가
**현재**: `home/page.tsx:810-821`에서 `personalizedKScore` → `calculated_at` → `severity` 순 고정

**수정 파일**: `frontend/app/(main)/home/page.tsx`
- 정렬 옵션 UI 추가 (드롭다운 or 칩): KScore순(기본) / 최신순 / 심각도순
- 상태: `useState<"kscore" | "latest" | "severity">("kscore")`
- 탭 헤더 우측에 정렬 아이콘 배치
- i18n: `frontend/lib/i18n.ts`에 정렬 관련 문자열 추가 (ko/en)

---

## 3. 라이트 모드 수정 (버그 — 사용자 피드백)

**문제**: 설정에서 라이트 모드 선택해도 어두운 배경 유지
**원인**: `layout.tsx:69`에서 초기 HTML class가 `"dark"`로 설정됨

**수정 파일**: `frontend/app/layout.tsx:69`
- 초기값을 빈 문자열로 설정하고, 인라인 스크립트에서 즉시 theme 적용

**수정 파일**: `frontend/app/globals.css`
- 라이트 모드 CSS 변수 확인 및 누락된 변수 보완

---

## 4. 페이지 전환 로딩 인디케이터 (UX — 사용자 피드백)

**문제**: 이슈 상세 페이지 진입 시 로딩 표시 없이 빈 화면
**신규 파일**: `frontend/app/(main)/issues/[id]/loading.tsx`
- 스켈레톤 UI

---

## 5. 정책 위반 수정

### 5-1. 개인 이메일 노출
**파일**: `frontend/lib/legal-data.ts:2`
→ `krshin7@gmail.com` → `support@wewantpeace.live`

### 5-2. CORS 와일드카드 축소
**파일**: `backend/app/main.py:215`
→ `toss.(im|dev)` → `toss.im`만

---

## 보안 점검 결과 (수정 불필요 — 현재 안전)
- SQL Injection: 파라미터화 쿼리 ✅
- Auth 우회: 프로덕션 강제 비활성화 ✅
- Rate Limiting: 구현됨 ✅
- API 문서: 프로덕션 비활성화 ✅
- 개인정보 정책: 완비 ✅
