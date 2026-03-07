# Filtered Jaccard + AI 매칭 + KScore v6 리밸런싱

## 완료일: 2026-03-08

## Context

클러스터링 품질 문제:
- 기존 Jaccard threshold(0.25)가 너무 높아서 같은 사건의 다른 매체 기사가 별도 클러스터로 분리됨
- 그런데 낮추면 "Iran nuclear talks"와 "Iran missile strikes"처럼 다른 사건이 한 클러스터에 합쳐짐
- 원인: Jaccard가 국가명/토픽 키워드(iran, attack, conflict...)를 유사도로 카운팅

## 해결: Filtered Jaccard

국가명/토픽 키워드를 Jaccard 계산에서 제거 → 콘텐츠 고유 단어만으로 유사도 측정

### 변경 파일

1. **`worker/processor/clusterer.py`**
   - `_COUNTRY_STEMS`, `_TOPIC_FILTER_STEMS` frozenset 추가
   - `_filtered_en_words()` 함수 추가
   - `_title_similarity()` → filtered Jaccard 사용
   - `MIN_TITLE_OVERLAP`: 0.25 → 0.15
   - `MIN_TITLE_OVERLAP_HIGH_SEV`: 0.10 → 0.08
   - `WINDOW_MINUTES`: 720 → 1440 (24h)
   - AI 매칭: `AI_MATCH_LOW=0.10`, `AI_MATCH_HIGH=0.20` 경계 구간에서 GPT-4o-mini 판정

2. **`worker/processor/calibration.py`**
   - `DECAY_LAMBDA`: 0.04 → 0.025 (더 완만한 감쇠)
   - `DECAY_FLOOR`: 0.15 → 0.30 (최소 30% 유지)

3. **`worker/processor/trending_engine.py`**
   - KScore 가중치: velocity 30%, quality 10%, severity 30%, spread 30%
   - (기존: 25/15/40/20 → severity 편중 해소)

4. **`scripts/recluster.py`** (신규)
   - 전체 재클러스터링 스크립트
   - flock 파일 잠금 (중복 실행 방지)
   - 데드락 재시도 로직
   - Raw SQL 배치 처리

## 재클러스터링 결과

| 항목 | Before | After |
|------|--------|-------|
| 클러스터 수 | 1,286 | 3,680 |
| 매핑 수 | 1,580 | 6,523 |
| 단일이벤트 | - | 76.7% |
| 2+이벤트 | - | 23.3% |
| 5+이벤트 | - | 178개 |
| 최대 이벤트 | - | 93개 |
| 평균 독립출처 | - | 1.45 |
| 소요시간 | - | 42분 |

## 주의사항

- Supabase Pooler(port 5432)는 session mode → `SET statement_timeout = 0` 동작함
- Direct connection(`db.xxx.supabase.co`)은 WSL에서 unreachable
- recluster 실행 시 Railway 워커 반드시 중지 후 실행
- 재클러스터링 완료 후 워커 재배포 필요
