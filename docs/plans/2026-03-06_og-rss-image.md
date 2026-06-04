# RSS 기사 대표 이미지 → OG 배경 (NYT 스타일)

## Context
OG 이미지에 텍스트만 있으면 스팸처럼 보임. RSS 피드에서 기사 대표 이미지를 추출하여 OG 배경으로 사용하면 NYT/Reuters처럼 신뢰감 있는 프리뷰 생성 가능.

## 데이터 흐름
```
RSS feed → rss_collector (이미지 추출) → raw_metadata["image_url"]
  → normalizer → normalized_events.image_url
  → clusterer → issue_clusters.image_url
  → API (ClusterOut) → OG image (NYT 스타일 배경)
```

## 수정 파일 (10개)

| # | 파일 | 작업 |
|---|------|------|
| 1 | `worker/collector/rss_collector.py` | `_extract_image_url()` 함수 추가, raw_metadata에 저장 |
| 2 | `backend/alembic/versions/0030_add_image_url.py` | **신규** — normalized_events + issue_clusters에 image_url 컬럼 |
| 3 | `backend/app/models/normalized_event.py` | image_url 필드 추가 |
| 4 | `backend/app/models/issue_cluster.py` | image_url 필드 추가 |
| 5 | `worker/processor/normalizer.py` | NormalizeResult에 image_url, normalize() 시그니처 확장 |
| 6 | `worker/tasks.py` | raw_metadata → normalize → NormalizedEvent 파이프라인 연결 |
| 7 | `worker/processor/clusterer.py` | 클러스터 생성/업데이트 시 image_url 전파 |
| 8 | `backend/app/routers/issues.py` | ClusterOut에 image_url 필드 |
| 9 | `frontend/app/(main)/issues/[id]/opengraph-image.tsx` | NYT 스타일 배경 렌더링 |
| 10 | `frontend/app/(main)/issues/country/[code]/opengraph-image.tsx` | 동일 적용 (top_cluster의 image_url) |

## 단계별 구현

### 1. RSS 이미지 추출 (`rss_collector.py`)

`_extract_image_url(entry)` 함수 추가 — 우선순위:
1. `entry.media_content` (medium=image)
2. `entry.media_thumbnail`
3. `entry.enclosures` (type=image/*)
4. 본문 HTML의 첫 `<img src>` (트래킹 픽셀 제외)

`raw_metadata`에 `"image_url": url[:1024]` 추가 (JSON이라 스키마 변경 불필요)

### 2. Alembic 마이그레이션 0030

```python
# normalized_events + issue_clusters 에 image_url String(1024) nullable 추가
# inspect() 멱등성 패턴 사용
```

### 3-4. 모델 필드 추가

`normalized_event.py`, `issue_cluster.py` 각각:
```python
image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
```

### 5. Normalizer 확장 (`normalizer.py`)

- `NormalizeResult` 데이터클래스에 `image_url: Optional[str] = None`
- `normalize()` 시그니처에 `image_url` 파라미터 추가, 그대로 결과에 전달

### 6. tasks.py 파이프라인 연결

```python
image_url = raw_event.raw_metadata.get("image_url") if raw_event.raw_metadata else None
norm = normalize(..., image_url=image_url)
ne = NormalizedEvent(..., image_url=norm.image_url)
```

### 7. Clusterer image_url 전파 (`clusterer.py`)

- 새 클러스터: `image_url=event.image_url`
- 기존 클러스터 업데이트: `if not cluster.image_url and event.image_url: cluster.image_url = event.image_url`

### 8. API 스키마 (`issues.py`)

`ClusterOut`에 `image_url: Optional[str] = None`, `_cluster_to_out()`에 전달

### 9-10. OG 이미지 — NYT 스타일

이미지 있을 때:
```
┌──────────────────────────────────────┐
│     [기사 사진 — 전체 배경]           │
│     opacity: 0.45                    │
│                                      │
│  ┌─ 하단 그라데이션 오버레이 ──────┐ │
│  │ [Logo] WeWantPeace   [Critical] │ │
│  │                                  │ │
│  │  이란-미국 전쟁 긴장 고조        │ │
│  │                                  │ │
│  │ [US] [무장 충돌]  wewantpeace   │ │
│  └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

이미지 없을 때: 기존 네이비 그라데이션 배경 유지 (폴백)

**안전장치:**
- 외부 이미지 fetch 3초 타임아웃 (`AbortSignal.timeout(3000)`)
- 2MB 초과 이미지 건너뜀
- Next.js `revalidate: 120`으로 OG 이미지 캐시

## 기존 데이터

- 기존 클러스터 `image_url = NULL` → 네이비 배경 폴백
- 새로 수집되는 기사부터 이미지 적용

## 검증
1. 마이그레이션 실행: `DATABASE_URL=... alembic upgrade head`
2. `npx next build` 성공
3. 프로덕션 배포 후 새 클러스터에 image_url이 채워지는지 확인
4. `opengraph.xyz`에서 URL 테스트
