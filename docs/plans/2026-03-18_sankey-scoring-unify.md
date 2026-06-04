# Sankey 영향 흐름 ↔ 주요 이슈 정렬 통일

## Context
홈 대시보드에서 **영향 흐름(Sankey)**과 **가장 영향이 큰 이슈/주요 이슈 목록**이 서로 다른 정렬 기준을 사용하여 다른 이슈가 표시됨.
- Sankey: `scored[:3]` = **impact_score** 기준 (severity 70% + kscore 30%)
- 이슈 목록: `pkscore_sorted[:5]` = **personalizedKScore** 기준 (kscore 100%, severity 0%)

사용자 입장에서 같은 화면에 "영향이 큰 이슈"라면서 다른 이슈가 나오면 혼란.

## 결론: impact_score 기준으로 통일 (Option A)

**이유:**
- `impact_score`는 이미 severity(70%) + kscore(30%) **혼합 점수** → 별도 blended score 불필요
- 분쟁 모니터링 앱이므로 심각도(severity)가 핵심 기준이어야 함
- pkscore는 severity를 완전히 무시 → 외교 회담 트위터 트렌드가 진행 중 전쟁보다 상위에 오는 문제
- 피드 페이지(/feed)는 별도 정렬 유지 (뉴스피드 성격이므로 kscore 기반 OK)

## 변경 사항

### 1. 백엔드: pkscore 정렬 제거 → scored 직접 사용
**파일**: `backend/app/routers/impact.py`
- **Line 323-333**: `pkscore_sorted` 계산 삭제, `top5_for_issues = scored[:5]`로 변경
- **Line 41**: `_CACHE_VERSION = "v11"` → `"v12"` (캐시 즉시 무효화)

### 2. 프론트엔드 i18n: 툴팁 텍스트 업데이트
**파일**: `frontend/lib/i18n.ts`
- **Line 1499 (ko)**: "KScore가 높을수록..." → "종합 영향도가 높을수록..."
- **Line 3091 (en)**: "Higher KScore = ..." → "Higher impact score = ..."

### 3. 프론트엔드: 미사용 import 제거
**파일**: `frontend/app/(main)/home/client.tsx`
- **Line 21**: `personalizedKScore` import 제거 (호출하는 곳 없음)

### 4. 프론트엔드: Sankey 코멘트 업데이트
**파일**: `frontend/components/dashboard/ImpactFlowSankey.tsx`
- **Line 295 주석**: 정렬 통일 반영

## 변경하지 않는 것
- `/feed` 페이지 정렬: kscore 기반 유지 (뉴스피드 성격)
- `kscore-utils.ts`: 그대로 유지 (feed/SmartSummary에서 사용)
- Sankey `_compute_impact_flow`: 이미 `scored[:3]` 사용 → 변경 없음
