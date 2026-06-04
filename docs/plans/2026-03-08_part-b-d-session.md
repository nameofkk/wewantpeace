# Part B-D 세션 실행 결과 (2026-03-08)

## 실행 내용

### FAIL 항목 수정

| # | 항목 | 원인 | 조치 |
|---|------|------|------|
| 1 | ACLED env vars Railway 미설정 | ACLED 계정 미가입, 환경변수 미설정 | `.env.example`에 ACLED_EMAIL/PASSWORD 추가. **사용자 액션 필요**: ACLED 가입 후 Railway에 환경변수 설정 |
| 2 | 수렴/이상감지 DB 미저장 | 코드는 구현 완료, 하지만 tension_index 테이블에 칼럼 없음 | migration 0038 추가, TensionIndex 모델/API 응답에 convergence_bonus + anomaly_z 추가 |

### Part B: UI/UX Quick Wins

| # | 항목 | 조치 |
|---|------|------|
| B-1 | PaywallModal 하드코딩 | ko/en 문자열 → i18n 키 4개 (paywall_pro_feature_*) |
| B-2 | PLANS dict 불일치 | 이미 bilingual + 프론트 일치 확인 (변경 불필요) |
| B-3 | 에러 메시지 한국어 하드코딩 | subscriptions.py 5곳 → code 기반 변환 + i18n 키 추가 |

### Part C: Phase 2

| # | 항목 | 상태 |
|---|------|------|
| C-1 | USGS + Travel Advisory | 이전 세션에서 100% 완료 |
| C-2 | impact-factors.ts → JSON import | **이번 세션에서 완료** |
| C-3 | 공개 API 4개 | 이전 세션에서 100% 완료 |
| C-4 | 소셜 어댑터 5개 | 이전 세션에서 100% 완료 |

### Part D: 보류 항목 + CONTEXT.md

- LICENSE (CC BY-NC 4.0) 생성 완료
- CONTEXT.md 전면 업데이트: 공개 API, Phase 완료현황, 보류항목 분류, 미설정 환경변수 목록

## 수정된 파일 (11개)

1. `.env.example` — ACLED 변수 추가
2. `CONTEXT.md` — 전면 업데이트
3. `LICENSE` — 신규 (CC BY-NC 4.0)
4. `backend/alembic/versions/0038_tension_convergence_anomaly.py` — 신규 migration
5. `backend/app/models/tension_index.py` — convergence_bonus, anomaly_z 칼럼
6. `backend/app/routers/tension.py` — TensionOut 스키마 + _tension_to_out
7. `backend/app/routers/subscriptions.py` — 에러 code 기반 통일
8. `frontend/components/ui/PaywallModal.tsx` — i18n 키 사용
9. `frontend/lib/i18n.ts` — paywall/error 키 ko/en
10. `frontend/lib/impact-factors.ts` — generated JSON import
11. `worker/processor/tension_calculator.py` — DB 저장에 convergence_bonus/anomaly_z 포함

## 커밋

- `ad8239d` — pushed to main
