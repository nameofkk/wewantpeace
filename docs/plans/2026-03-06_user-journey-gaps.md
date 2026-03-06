# 유저 여정 시나리오 갭 5개 개선 플랜

**날짜**: 2026-03-06
**상태**: ✅ 구현 완료 (커밋 b767812)

## 구현 내역

| # | 작업 | 파일 | 상태 |
|---|------|------|------|
| 1 | 국가 OG 이미지 | `frontend/app/(main)/issues/country/[code]/opengraph-image.tsx` | ✅ |
| 2 | 국가 긴장도 추이 차트 | `frontend/app/(main)/issues/country/[code]/client.tsx` | ✅ |
| 3 | 대시보드 주간비교 | `backend/app/routers/admin.py` + `frontend/app/admin/page.tsx` | ✅ |
| 4 | 주간 리포트 공개 웹 | `backend/app/routers/public.py` + `frontend/app/(main)/reports/weekly/` | ✅ |
| 5 | i18n 키 22개 추가 | `frontend/lib/i18n.ts` | ✅ |

## 검증
- Python ast.parse: admin.py, public.py, main.py 모두 OK
- Git push: main → origin/main 완료
