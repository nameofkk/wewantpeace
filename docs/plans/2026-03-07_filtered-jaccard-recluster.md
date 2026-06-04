# Filtered Jaccard + 재클러스터링 플랜 (2026-03-07)

## 문제

1. 클러스터링 임계값이 너무 높아 76.6%가 단일이벤트 클러스터
2. 윈도우 12시간 → 24시간으로 확장 필요
3. Time decay 반감기 17h → 28h로 완화 필요
4. KScore에서 severity 가중치 40% → 30%로 균형 필요
5. 같은 country:topic 버킷 내에서 국가/토픽 단어가 Jaccard 유사도를 왜곡

## 해결

### Filtered Jaccard (clusterer.py)
- 국가명/토픽 키워드를 Jaccard 계산에서 제거
- 순수 컨텐츠 유사도만 측정
- `_COUNTRY_STEMS`, `_TOPIC_FILTER_STEMS` frozenset 추가
- `_filtered_en_words()` → `_title_similarity()`에서 사용
- 임계값: 0.25→0.15 (일반), 0.10→0.08 (고severity)
- 윈도우: 720분→1440분 (24h)

### AI 경계 판정 (clusterer.py)
- Filtered Jaccard 0.10~0.20 범위: GPT-4o-mini로 "같은 사건?" 판정
- `_ai_same_event()` 함수 (LRU cache 256)
- `skip_ai=True` 파라미터로 배치 처리 시 비용 절약

### KScore v6 (trending_engine.py + calibration.py)
- 가중치: velocity 0.30, quality 0.10, severity 0.30, spread 0.30
- Decay: λ=0.025 (반감기 28h), floor=0.30

### 재클러스터링 (scripts/recluster.py)
- **Raw SQL 전용** — ORM identity map 문제 완전 제거
- Supabase Pooler 대응: 배치마다 DB 연결 재생성
- `ON CONFLICT DO NOTHING`으로 duplicate key 방지
- `--resume N` 옵션으로 중단 시 재개 가능

## 결과

- 6,523개 이벤트 처리, skip 0, deadlock 0
- 3,680개 클러스터 (새 생성), 2,843개 병합 (43.6% 병합율)
- 단일이벤트 76.7%, 2+이벤트 23.3%, 5+이벤트 178개
- 최대 이벤트 93개, 평균 독립출처 1.45
- 실행 시간: 42.5분

## 수정 파일

| 파일 | 변경 |
|------|------|
| `worker/processor/clusterer.py` | Filtered Jaccard, AI 매칭, 임계값/윈도우 조정 |
| `worker/processor/calibration.py` | decay λ=0.025, floor=0.30 |
| `worker/processor/trending_engine.py` | KScore v6 가중치 |
| `scripts/recluster.py` | Raw SQL 전체 재클러스터링 스크립트 |
