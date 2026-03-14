# WeWantPeace 홈 화면 종합 개선 (6개 우선순위)

## Context

홈 화면 종합 진단 결과:
- `/impact/summary` 내부 **37+ 순차 DB 쿼리** → 응답 1-2초 소요
- 수집 데이터 활용률 56% — `economic_indicator`, `anomaly_z`, `is_spike` 등 미사용
- SECTION 1에 한 줄 7개 데이터 밀집, 긴장도 3곳 중복
- 온보딩에서 `homeCountry` 설정 없음 → KScore 개인화 무의미
- `/issues?limit=2000` (200-500KB) 중 Top 5만 사용
- 캐시 TTL 6시간 → 시장 데이터 갱신 지연

## 구현 순서

P5(TTL) → P1(쿼리 최적화) → P6(useClusters 제거) → P2(데이터 활용) → P3(정보 밀도) → P4(온보딩)

---

## P5: 캐시 TTL 단축 (1줄 변경)

**파일**: `backend/app/routers/impact.py`

라인 590:
```python
# before
await redis.set(cache_key, json.dumps(response_data), ex=6 * 3600)
# after
await redis.set(cache_key, json.dumps(response_data), ex=30 * 60)
```

캐시 버전도 v3→v4 범프 (라인 40).

---

## P1: `/impact/summary` 쿼리 병렬화

**파일**: `backend/app/routers/impact.py`

### P1-A: reason 배치 조회 (15개 쿼리 → 2개)

현재 라인 274~316: Top 5 이슈마다 순차로 `_generate_issue_reason()` 호출 (각 2-3 DB 쿼리).

**변경**: 필요한 데이터를 **먼저 배치 조회**, 이후 순수 파이썬으로 reason 생성.

```python
# Step 1: Top 5 클러스터의 country_code 수집
top5_countries = list({c.country_code for c, _ in scored[:5] if c.country_code})

# Step 2: TradeBilateral 배치 조회 (1 쿼리)
trade_q = await db.execute(
    select(TradeBilateral.partner_code, TradeBilateral.total_trade_usd)
    .where(
        TradeBilateral.reporter_code == home,
        TradeBilateral.partner_code.in_(top5_countries),
        TradeBilateral.period_type == "A",
    )
    .order_by(TradeBilateral.period.desc())
)
trade_map = {}
for row in trade_q.fetchall():
    if row[0] not in trade_map:
        trade_map[row[0]] = row[1]

# Step 3: WTI 유가 조회 (1 쿼리, 공유)
oil_q = await db.execute(
    select(CommodityPrice.price_usd, CommodityPrice.change_pct)
    .where(CommodityPrice.symbol == "WTI")
    .order_by(CommodityPrice.price_date.desc())
    .limit(1)
)
oil_row = oil_q.first()

# Step 4: 순수 파이썬 reason 생성 (DB 호출 없음)
for c, impact in scored[:5]:
    reason = _build_reason_sync(c, home, lang, sectors_data, trade_map, oil_row)
    ...
```

`_generate_issue_reason()` → `_build_reason_sync()` (동기 함수)로 교체. 내부 DB 호출 제거, `trade_map`/`oil_row` 파라미터로 전달.

### P1-B: market_snapshot 배치화 (17개 쿼리 → 3개)

현재 `_get_market_snapshot()` (라인 1260~1349): 원자재 3개 + 지수 6개 + 환율 8개 = 17개 순차 쿼리.

```python
async def _get_market_snapshot(home_country: str, db: AsyncSession) -> dict | None:
    # 1) 원자재: 1 쿼리 (PostgreSQL DISTINCT ON)
    commodity_q = await db.execute(
        select(CommodityPrice)
        .distinct(CommodityPrice.symbol)
        .where(CommodityPrice.symbol.in_(["WTI", "BRENT", "GOLD"]))
        .order_by(CommodityPrice.symbol, CommodityPrice.price_date.desc())
    )

    # 2) 지수: 1 쿼리
    index_q = await db.execute(
        select(MarketIndex)
        .distinct(MarketIndex.symbol)
        .where(MarketIndex.symbol.in_(["KOSPI", "SPX", "NKY", "DAX", "FTSE", "SSE"]))
        .order_by(MarketIndex.symbol, MarketIndex.index_date.desc())
    )

    # 3) 환율: 1 쿼리 (최신만 — change_pct는 ExchangeRate 모델에 이미 있으면 재활용)
    target_currencies = _HOME_CURRENCIES.get(home_country, ["EUR", "JPY", "GBP", "CNY"])
    rate_q = await db.execute(
        select(ExchangeRate)
        .distinct(ExchangeRate.target_currency)
        .where(
            ExchangeRate.base_currency == "USD",
            ExchangeRate.target_currency.in_(target_currencies),
        )
        .order_by(ExchangeRate.target_currency, ExchangeRate.rate_date.desc())
    )
```

**효과**: 17개 순차 → 3개 배치. 응답시간 -0.8초.

---

## P6: `/issues?limit=2000` 제거 (200-500KB 절약)

### 핵심 아이디어

`/impact/summary`의 `top_issues[]`가 이미 서버에서 Top 5를 계산해서 반환. 홈에서 2000개 클러스터를 불러와 클라이언트에서 정렬할 필요 없음.

### P6-A: 백엔드 — `ImpactSummaryTopIssue` 필드 확장

**파일**: `backend/app/routers/impact.py` (라인 97~105)

```python
class ImpactSummaryTopIssue(BaseModel):
    cluster_id: str
    title: str
    title_en: str | None = None         # 추가: 영어 제목
    impact_score: int
    country_codes: list[str]
    topic: str
    reason: str | None = None
    kscore_delta: float | None = None
    # 새 필드
    event_count: int = 0
    severity: int = 0
    kscore: float = 0.0
    independent_sources: int = 0
    is_spike: bool = False
    confidence: float = 0.0
    first_event_at: str | None = None
    last_event_at: str | None = None
```

top_issues 빌드 (라인 308~316)에서 새 필드 채우기:
```python
top_issues.append(ImpactSummaryTopIssue(
    ...,
    title_en=c.title or "",
    event_count=c.event_count or 0,
    severity=c.severity or 0,
    kscore=round(c.kscore or 0.0, 2),
    independent_sources=c.independent_sources or 0,
    is_spike=c.is_spike or False,
    confidence=round(c.confidence or 0.0, 3),
    first_event_at=c.first_event_at.isoformat() if c.first_event_at else None,
    last_event_at=c.last_event_at.isoformat() if c.last_event_at else None,
))
```

### P6-B: 프론트엔드 — `useClusters()` 제거

**파일**: `frontend/lib/api.ts`

`ImpactSummaryTopIssue` 타입에 새 필드 추가:
```typescript
export interface ImpactSummaryTopIssue {
  cluster_id: string;
  title: string;
  title_en?: string;
  impact_score: number;
  country_codes: string[];
  topic: string;
  reason?: string;
  kscore_delta?: number | null;
  event_count: number;
  severity: number;
  kscore: number;
  independent_sources: number;
  is_spike: boolean;
  confidence: number;
  first_event_at?: string | null;
  last_event_at?: string | null;
}
```

**파일**: `frontend/app/(main)/home/page.tsx`

1. `useClusters` import 제거 (라인 15)
2. `useClusters()` 호출 제거 (라인 145)
3. `topItems` useMemo를 `summary.top_issues` 기반으로 교체 (라인 202~224):

```typescript
const topItems = useMemo(() => {
  if (!summary?.top_issues?.length) return [];
  return summary.top_issues.map((ti, i) => ({
    id: i,
    keyword: lang === "en" && ti.title_en ? ti.title_en : ti.title,
    keyword_ko: ti.title,
    kscore: ti.kscore,
    topic: ti.topic,
    country_codes: ti.country_codes,
    cluster_ids: [ti.cluster_id],
    event_count: ti.event_count,
    severity: ti.severity,
    reason: ti.reason || "",
    calculated_at: ti.last_event_at,
    first_event_at: ti.first_event_at,
    independent_sources: ti.independent_sources,
    is_spike: ti.is_spike,
    confidence: ti.confidence,
  } as TrendingItem));
}, [summary, lang]);
```

4. `reasonMap` useMemo 제거 (라인 194~200) — reason이 이미 top_issues에 포함

**효과**: 홈 로딩 시 200-500KB 네트워크 전송 제거. API 호출 6개→5개.

---

## P2: 미활용 데이터 활용

### P2-A: anomaly_z "급변" + convergence_bonus "다중위기" 뱃지

**파일**: `backend/app/routers/tension.py`

`/tension/all` 응답 모델에 필드 추가 (현재 `raw_score`, `tension_level`만 반환):
```python
# TensionAllItem 모델 확장
class TensionAllItem(BaseModel):
    country_code: str
    raw_score: float
    tension_level: int
    anomaly_z: float | None = None         # 추가
    convergence_bonus: float = 0.0         # 추가
```

`/all` 엔드포인트 응답 빌드에서 새 필드 포함.

**파일**: `frontend/lib/api.ts` — `TensionAllItem` 타입 확장
**파일**: `frontend/app/(main)/home/page.tsx` — 관심국가 칩에 뱃지:

```tsx
{isAnomaly && <span className="text-[7px] px-1 rounded bg-red-500/20 text-red-400 font-bold">{t(lang, "dash_badge_anomaly")}</span>}
{isConverging && <span className="text-[7px] px-1 rounded bg-purple-500/20 text-purple-400 font-bold">{t(lang, "dash_badge_convergence")}</span>}
```

### P2-B: is_spike "급등" + confidence "검증됨" 뱃지 (Impact Chain)

P6에서 `top_issues`에 `is_spike`, `confidence` 추가 완료. 이를 활용:

```tsx
{topIssue.is_spike && <span className="text-[8px] px-1 rounded bg-red-500/10 text-red-400">급등</span>}
{topIssue.confidence >= 0.7 && <span className="text-[8px] px-1 rounded bg-emerald-500/10 text-emerald-400">검증됨</span>}
```

### P2-C: economic_indicator 활용 (Pro 분석 강화)

**파일**: `backend/app/routers/impact.py` — Pro 분석 생성 블록 (라인 358~540)

현재 GDP만 1곳에서 사용 (라인 682). 추가 지표 활용:

```python
EXTRA_INDICATORS = [
    ("FP.CPI.TOTL.ZG", "inflation"),
    ("NE.TRD.GNFS.ZS", "trade_openness"),
    ("BN.CAB.XOKA.CD", "current_account"),
]
```

각 지표를 economy/trade 분석 텍스트에 반영:
- 인플레이션 > 5% → "원자재 상승 시 추가 물가 압력"
- 교역/GDP > 80% → "글로벌 공급망 교란에 높은 노출"
- 경상수지 적자 → "외환 유출 리스크"

### P2-D: trade direction (순수출/순수입)

**파일**: `backend/app/routers/impact.py` — `TradePartnerOut` 모델 확장

```python
class TradePartnerOut(BaseModel):
    country_code: str
    trade_volume_usd: float
    dependency_pct: float
    export_usd: float | None = None      # 추가
    import_usd: float | None = None      # 추가
    trade_balance: str | None = None     # "surplus" | "deficit"
```

프론트 교역 탭에 방향 표시 ("순수출"/"순수입").

---

## P3: SECTION 1 정보 밀도 정리

**파일**: `frontend/app/(main)/home/page.tsx`

### 현재 문제
- Row 4 (라인 280~312): 1줄에 국기+긴장도+점수+게이지+라벨+이슈수+고영향수 = 7개
- Row 5 (라인 314~346): 글로벌 현황 (극심/심각/경계 카운트) — 긴장도 중복
- Row 6 (라인 348~385): 관심국가 칩 — 긴장도 중복

### 변경

**Row 4 → 2줄로 분리 + Row 5 통합**:

```tsx
{/* Row 4a: 홈 긴장도 + 글로벌 현황 (통합) */}
<div className="flex items-center gap-2 text-[11px] mb-1.5 flex-wrap">
  <span className="text-base">{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
  <span className={cn("font-bold tabular-nums", tc.text)}>{Math.round(animatedHomeScore)}</span>
  <div className="h-1.5 w-12 rounded-full bg-muted overflow-hidden">
    <div className={cn("h-full rounded-full", tc.bar)} style={{width: `${Math.min(homeScore,100)}%`}} />
  </div>
  <span className={cn("text-[9px]", tc.text)}>{tensionLabelShort(homeScore, lang)}</span>
  <span className="text-muted-foreground/30">|</span>
  {/* 극심/심각/경계 인라인 (숫자만) */}
  {extremeCount > 0 && <span className="flex items-center gap-0.5"><span className="h-1.5 w-1.5 rounded-full bg-red-900 animate-pulse"/><span className="text-[9px] text-red-300 font-medium">{extremeCount}</span></span>}
  {severeCount > 0 && <span className="flex items-center gap-0.5"><span className="h-1.5 w-1.5 rounded-full bg-red-500"/><span className="text-[9px] text-red-400 font-medium">{severeCount}</span></span>}
  {alertCount > 0 && <span className="flex items-center gap-0.5"><span className="h-1.5 w-1.5 rounded-full bg-orange-500"/><span className="text-[9px] text-orange-300 font-medium">{alertCount}</span></span>}
</div>

{/* Row 4b: 이슈 통계 + 업데이트 시간 */}
<div className="flex items-center gap-3 text-[10px] text-muted-foreground mb-3">
  <span>이슈 <strong>{summary?.total_active_issues ?? 0}</strong></span>
  <span className="text-red-400">고영향 <strong>{summary?.critical_issues_count ?? 0}</strong></span>
  {updatedTime && <span className="ml-auto">{updatedTime}</span>}
</div>
```

**기존 Row 5 (글로벌 현황 별도 줄) 전체 제거** — Row 4a에 통합됨.

**영어 길이 대응**: `tensionLabelShort()` 함수 추가:
```typescript
function tensionLabelShort(score: number, lang: "ko" | "en") {
  if (score >= 80) return lang === "ko" ? "극심" : "Ext.";
  if (score >= 60) return lang === "ko" ? "심각" : "Sev.";
  if (score >= 40) return lang === "ko" ? "경계" : "Alt.";
  if (score >= 20) return lang === "ko" ? "주의" : "Cau.";
  return lang === "ko" ? "안정" : "OK";
}
```

---

## P4: 온보딩에 홈 국가 설정 추가

**파일**: `frontend/app/(auth)/onboarding/page.tsx`

### 문제
온보딩 Step 1에서 "관심국가" (watchlist) 2개만 선택. `homeCountry`는 기본값 "KR"로 store에 하드코딩. 비한국 사용자는 온보딩 후에도 KR 기준 리포트를 봄.

### 변경

Step 1 상단에 "나의 국가" 선택 UI 추가 (관심국가 선택 위에):

```tsx
{step === 1 && (
  <div className="flex-1 flex flex-col min-h-0 animate-fadeIn">
    {/* 나의 국가 선택 (새 섹션) */}
    <div className="mb-4 pb-3 border-b border-border/30">
      <h3 className="text-sm font-bold text-center mb-1">{t(lang, "ob_home_country_title")}</h3>
      <p className="text-xs text-muted-foreground text-center mb-3">{t(lang, "ob_home_country_desc")}</p>
      {/* 추천 국가 6개 (빠른 선택) */}
      <div className="flex flex-wrap gap-2 justify-center mb-2">
        {["KR","US","JP","CN","GB","DE"].map(code => (
          <button key={code} onClick={() => setHomeCountryLocal(code)}
            className={cn("flex items-center gap-1 px-3 py-1.5 rounded-full text-sm",
              homeCountryLocal === code ? "bg-primary text-primary-foreground" : "bg-muted"
            )}>
            <span>{getFlag(code)}</span>
            <span>{getCountryName(code, lang)}</span>
          </button>
        ))}
      </div>
      {/* "다른 국가" 드롭다운 */}
      <button className="text-xs text-muted-foreground underline mx-auto block">
        {t(lang, "ob_home_country_other")}
      </button>
    </div>

    {/* 기존: 관심국가 선택 */}
    ...
```

`handleNext()` (라인 155~164)에서 Step 1 완료 시 `setHomeCountry(homeCountryLocal)` 호출.

### i18n 키 추가
```
ob_home_country_title: "나의 국가" / "My Country"
ob_home_country_desc: "글로벌 이슈가 내 나라에 미치는 영향을 확인하세요" / "See how global issues impact your country"
ob_home_country_other: "다른 국가 선택" / "Choose another country"
```

---

## i18n 키 종합 (ko + en 모두)

```
dash_badge_anomaly: "급변" / "Surge"
dash_badge_convergence: "다중위기" / "Multi-crisis"
dash_badge_spike: "급등" / "Spike"
dash_badge_verified: "검증됨" / "Verified"
dash_trade_surplus: "순수출" / "Surplus"
dash_trade_deficit: "순수입" / "Deficit"
ob_home_country_title: "나의 국가" / "My Country"
ob_home_country_desc: "글로벌 이슈가 내 나라에 미치는 영향을 확인하세요" / "See how global issues impact your country"
ob_home_country_other: "다른 국가 선택" / "Choose another country"
```

---

## 수정 파일 요약

| 파일 | P5 | P1 | P6 | P2 | P3 | P4 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| `backend/app/routers/impact.py` | TTL | 배치쿼리 | top_issues 확장 | 경제지표 | | |
| `backend/app/routers/tension.py` | | | | anomaly_z/conv | | |
| `frontend/app/(main)/home/page.tsx` | | | useClusters제거 | 뱃지 | 밀도정리 | |
| `frontend/lib/api.ts` | | | 타입확장 | 타입확장 | | |
| `frontend/lib/i18n.ts` | | | | 뱃지키 | 약어 | 온보딩키 |
| `frontend/app/(auth)/onboarding/page.tsx` | | | | | | homeCountry |

---

## 검증

1. **P5**: 캐시 30분 확인 — 배포 후 30분 내 시장 데이터 갱신 확인
2. **P1**: `/impact/summary` 응답 시간 — 배포 전후 비교 (목표: 2초→0.5초)
3. **P6**: 홈 네트워크 탭 — `/issues` 호출 없어야 함, `top_issues`에 새 필드 포함
4. **P2**: 관심국가 칩 "급변" 뱃지 표시, Impact Chain "급등"/"검증됨" 뱃지, Pro 분석에 인플레이션/교역비중 언급
5. **P3**: 모바일 320px에서 SECTION 1 줄바꿈 안 깨짐, 영어 모드 정상
6. **P4**: 온보딩 Step 1에서 홈 국가 선택 → 완료 후 홈 리포트에 선택한 국가 반영

## 배포

1. Backend 배포 (railway.json = Dockerfile.backend 확인)
2. Frontend 배포 (railway.json swap → Dockerfile.frontend → 배포 → swap back)
3. 토스 빌드: `cd frontend && sh build-toss.sh` → 바탕화면 복사 → 콘솔 수동 업로드
