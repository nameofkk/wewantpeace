# WeWantPeace v2.0 — "Conflict Weather App" 피벗 플랜

## Context

**문제**: 178명 유저, 유료 0명, 73% 단일세션 이탈. 베타 피드백 — "UI 복잡", "설명 부족", "유료화 너무 빠름".
현재 홈은 Bloomberg Terminal 스타일 대시보드(1096줄, 5개 섹션, Sankey SVG, 5축 Radar 차트, 4탭 데이터)로
일반 사용자에게 과도한 정보 밀도.

**인사이트**: 같은 팀의 뉴스레터는 대화체·쉬운 설명으로 좋은 반응 → 앱도 "날씨앱처럼 한눈에 보는 분쟁 영향"으로 피벗.
13개 데이터 수집기 + 위성검증 파이프라인은 유지하되, 사용자에게 보여주는 방식을 완전히 바꿈.

**핵심 제약**: AI가 만든 티가 나면 안 됨. 챗봇 UI 없음, "AI 생성" 라벨 없음. 편집실에서 큐레이션한 느낌.

---

## Phase 1: 백엔드 "So What?" 레이어 확장

> 기존 데이터 파이프라인에 소비자 친화적 필드를 추가. 프론트엔드 변경 없이 독립 배포 가능.

### 1-1. `_build_smart_summary()` 소비자 필드 추가

**파일**: `backend/app/routers/impact.py` (L1839-1953)

현재 반환값:
```python
return {"what_line": ..., "so_what_line": ..., "when_line": ..., "relevant_commodities": ...}
```

추가할 필드:
```python
return {
    "what_line": what_line,
    "so_what_line": so_what_line,
    "when_line": when_line,
    "relevant_commodities": rel_syms,
    # --- 새 필드 ---
    "what_consumer": what_consumer,      # 뉴스레터 톤의 한줄 설명
    "so_what_consumer": so_what_consumer, # "당신의 지갑" 관점
    "when_consumer": when_consumer,       # 구어체 시간 표현
    "wallet_line": wallet_line,           # 직접적 생활 영향 (예: "주유소 가격 ↑ 예상")
}
```

**구현 방법**:
- `what_consumer`: body 첫 문장 대신 `topic + country + severity`로 뉴스레터 톤 생성
  - ko: `"{c_name}에서 {topic_ko} 발생, 심각도 {severity}점으로 {level} 수준"`
  - en: `"{topic_en} in {c_name}, severity {severity} — {level} level"`
  - level: severity>=80 → "위험/Critical", >=60 → "주의/Elevated", >=40 → "관심/Watch", else → "참고/Note"
- `so_what_consumer`: commodity_ref가 있으면 생활 영향으로 변환
  - 유가 → ko: "주유비·택배비 인상 압력" / en: "Gas & shipping cost pressure expected"
  - 곡물 → ko: "식품 가격 불안정 가능성" / en: "Food price volatility possible"
  - 없으면 기존 so_what_line 사용
- `when_consumer`: severity 기반 구어체
  - >=80: ko "바로 영향이 올 수 있어요" / en "Impact could be immediate"
  - >=60: ko "1~2주 안에 느낄 수 있어요" / en "You may feel it in 1-2 weeks"
  - >=40: ko "한두 달 추이를 지켜봐야 해요" / en "Worth watching over 1-2 months"
  - else: ko "직접적 영향은 제한적이에요" / en "Direct impact is limited"
- `wallet_line`: commodity + trade_vol 기반 생활비 영향
  - 유가상승+교역국 → ko "기름값·물가 오를 수 있어요" / en "Gas & prices may rise"
  - 곡물 → ko "장바구니 물가 주의" / en "Grocery prices to watch"
  - 반도체 → ko "전자제품 가격 영향 가능" / en "Electronics prices may be affected"
  - 없으면 null

### 1-2. 위성검증 데이터를 API 응답에 노출

**파일**: `backend/app/routers/impact.py`

현재 상태: `signal_correlator.py`가 클러스터에 `signal_corroboration_count`, `signal_types`, `confidence`를 기록하지만 API 응답 스키마(`ImpactSummaryTopIssue`)에 포함되지 않음.

변경:
- `ImpactSummaryTopIssue` Pydantic 모델에 필드 추가:
  ```python
  signal_corroboration_count: int = 0
  signal_types: list[str] = []      # ["firms_hotspot", "ioda_outage", ...]
  verification_label: str | None = None  # "위성 확인됨" / "Satellite verified"
  ```
- `_build_top_issues()` 함수에서 클러스터의 기존 필드를 그대로 매핑
- `verification_label` 로직:
  - count >= 2 → ko "복수 검증 완료" / en "Multi-source verified"
  - count == 1 → ko "위성 확인됨" / en "Satellite confirmed"
  - count == 0 → null (표시 안 함)

### 1-3. 캐시 버전 업데이트

**파일**: `backend/app/routers/impact.py` L42
```python
_CACHE_VERSION = "v19"  →  _CACHE_VERSION = "v20"
```

### 검증
- `curl /impact/summary?home_country=KR&lang=ko` 호출 후 새 필드 확인
- 기존 프론트엔드는 새 필드를 무시하므로 하위호환 보장

---

## Phase 2: 홈 화면 리디자인 (핵심 변경)

> 1096줄 `client.tsx`의 5개 섹션을 날씨앱 스타일로 재구성.
> 기존 파일을 점진적으로 수정 (새 파일 최소화).

### 2-0. 새 레이아웃 구조

```
┌──────────────────────────────┐
│  ☀️ Weather Header            │  ← 한줄 요약 + 영향도 점수
│  "오늘의 분쟁 날씨: 흐림"      │
├──────────────────────────────┤
│  🔥 Top Story                │  ← #1 이슈 카드 (소비자 언어)
│  🇮🇱 이스라엘-레바논 교전 격화   │
│  💰 기름값·물가 오를 수 있어요   │  ← wallet_line
│  ⏱️ 바로 영향이 올 수 있어요    │  ← when_consumer
│  ✅ 위성 확인됨                │  ← verification_label
├──────────────────────────────┤
│  📰 More Stories (#2-#5)     │  ← 컴팩트 리스트
├──────────────────────────────┤
│  📊 Watchlist                │  ← 관심국가 긴장도 칩
├──────────────────────────────┤
│  ▼ Data Deep-dive (접힘)     │  ← 기존 4탭 대시보드 (접기)
├──────────────────────────────┤
│  📬 Newsletter CTA           │
│  ⚖️ Disclaimer               │
└──────────────────────────────┘
```

### 2-1. Weather Header (Section A 교체)

**파일**: `frontend/app/(main)/home/client.tsx` Section A (L382-553)

**Before**: Impact Score + RiskRadar(Recharts) + 기준국가 긴장도 + 글로벌 현황 + Watchlist chips
**After**: Weather-style 한줄 요약 + 영향도 점수 (레이더·긴장도 바 제거)

변경 내용:
- RiskRadar 컴포넌트 임포트 제거 (파일 자체는 유지, 이슈 상세에서 사용 가능)
- 기존 Section A의 `<div className="flex items-start gap-4">` 블록 → 새 Weather Header로 교체:

```tsx
{/* Weather Header */}
<div className="rounded-xl border border-border bg-card p-4">
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-2">
      <span className="text-xl">{weatherEmoji(impactScore)}</span>
      <div>
        <h2 className="text-sm font-bold">{weatherLabel(impactScore, lang)}</h2>
        <p className="text-[10px] text-muted-foreground">{updatedTime}</p>
      </div>
    </div>
    <div className="text-right">
      <span className="text-2xl font-extrabold tabular-nums" style={{color}}>
        {Math.round(animatedImpact)}
      </span>
      <span className="text-[9px] text-muted-foreground block">/100</span>
    </div>
  </div>
  <p className="text-[11px] text-foreground/70 leading-relaxed">
    {summary?.summary}
  </p>
</div>
```

- `weatherEmoji(score)`: >=75 "🔴" / >=50 "🟠" / >=25 "🟡" / else "🟢"
- `weatherLabel(score, lang)`: >=75 "위험/Critical" / >=50 "주의/Caution" / >=25 "관심/Watch" / else "안정/Calm"
- 긴장도 바, 글로벌 현황 칩 → 삭제 (정보 과부하 원인)
- Watchlist chips → Section 2-3으로 이동

### 2-2. Top Story 카드 개선 (Section B 수정)

**파일**: `frontend/components/dashboard/SmartSummaryCard.tsx`

**SmartSummaryCardFull 변경**:
- 기존 3-line (what/so_what/when) → 소비자 필드 우선 사용
  - `topIssueRaw.what_consumer ?? topIssueRaw.what_line`
  - `topIssueRaw.so_what_consumer ?? topIssueRaw.so_what_line`
  - `topIssueRaw.when_consumer ?? topIssueRaw.when_line`
  - `topIssueRaw.wallet_line` 있으면 별도 행으로 표시 (💰 아이콘 + 텍스트)
- verification_label 배지 추가:
  - `topIssueRaw.verification_label`이 있으면 topic badge 옆에 표시
  - 스타일: `bg-emerald-500/10 text-emerald-500 text-[8px] px-1.5 rounded`

**SmartSummaryCompact 변경**:
- `soWhatLine`을 `topIssueRaw.so_what_consumer ?? topIssueRaw.so_what_line`으로 교체

### 2-3. Sankey → 제거, Watchlist 이동

**파일**: `frontend/app/(main)/home/client.tsx` Section B (L556-637)

- ImpactFlowSankey 블록 전체 제거 (L558-581)
- `ImpactFlowSankey` 임포트 제거
- 파일 자체(`ImpactFlowSankey.tsx`)는 삭제하지 않음 (다른 곳에서 사용 가능성)
- Watchlist chips를 Section A에서 빼서 More Stories 아래 독립 섹션으로 배치

### 2-4. Data Dashboard 접기

**파일**: `frontend/app/(main)/home/client.tsx` Section C (L640-975)

- 기존 4탭 대시보드를 `<details>` + `<summary>` 또는 `useState(false)` 토글로 감쌈
- 기본 상태: 접힘 (collapsed)
- 토글 버튼: "{lang=ko ? '데이터 더 보기' : 'View data'} ▼"

### 2-5. SectorImpactCard 접기

**파일**: `frontend/app/(main)/home/client.tsx` Section D (L978-991)

- Data Dashboard와 함께 접힘 영역 안으로 이동

### 2-6. i18n 키 추가

**파일**: `frontend/lib/i18n.ts`

새 키 (ko/en 동시):
```
dash_weather_critical / dash_weather_caution / dash_weather_watch / dash_weather_calm
dash_wallet_label / dash_verification_multi / dash_verification_satellite
dash_data_expand / dash_data_collapse
dash_consumer_impact_immediate / dash_consumer_impact_weeks / dash_consumer_impact_months / dash_consumer_impact_limited
```

### 2-7. i18n 폴백 수정

**파일**: `frontend/lib/i18n.ts`

현재 (L 마지막 부분의 t 함수):
```typescript
translations[lang][key] ?? translations.ko[key] ?? key
```
→ 변경:
```typescript
translations[lang][key] ?? translations.en[key] ?? key
```
영어가 글로벌 기본값이 되어야 함.

### 검증
- `npm run dev` → 홈 화면에서 Weather Header 확인
- 기존 4탭 데이터가 접힘 상태에서 펼쳐지는지 확인
- Sankey 제거 후 에러 없는지 확인
- 모바일 뷰포트(375px)에서 한 줄 정렬 확인

---

## Phase 3: 피드 & 카드 리디자인

> 피드 카드를 뉴스레터 톤으로 전환.

### 3-1. 피드 카드 소비자 언어 적용

**파일**: `frontend/app/(main)/feed/client.tsx`

- 피드 카드에서 `what_line` 대신 `what_consumer` 표시
- `so_what_line` 대신 `so_what_consumer` 표시
- verification_label 배지 표시

### 3-2. 이슈 상세 페이지에 RiskRadar 이동

**파일**: `frontend/app/(main)/issues/[id]/client.tsx` (또는 해당 상세 페이지)

- 홈에서 제거한 RiskRadar를 이슈 상세의 상단에 배치
- 전문가용 데이터(impact flow, sector risk)도 이슈 상세로 이동 검토

### 3-3. 카드 디자인 개선

**파일**: `frontend/components/dashboard/SmartSummaryCard.tsx`

- what/so_what/when 좌측 컬러 바 → 아이콘으로 교체
  - what → 📰 (없으면 lucide `Newspaper` icon)
  - wallet → 💰 (없으면 lucide `Wallet` icon)
  - when → ⏱️ (없으면 lucide `Clock` icon)
- 폰트 사이즈 약간 증가: 11px → 12px (본문), 9px → 10px (라벨)
- 과도한 뱃지(SPIKE, Tier A, Verified) → 최대 2개만 표시

### 검증
- /feed 페이지에서 카드 렌더링 확인
- 이슈 상세에서 RiskRadar 표시 확인
- 다국어 전환(ko↔en) 시 깨짐 없는지 확인

---

## Phase 4: 온보딩 & 습관 형성

> 첫 경험 개선 + 재방문 유도.

### 4-1. 온보딩 GeoIP 자동감지

**파일**: `frontend/app/(auth)/onboarding/page.tsx`

현재: 3단계 (Hero → 국가선택 → 푸시허용), 89%가 국가선택 스킵
변경:
- 국가선택 단계에서 GeoIP로 1개 국가 자동 선택
- API: 무료 `https://ipapi.co/json/` 또는 Cloudflare의 `cf-ipcountry` 헤더 활용
- 자동선택된 국가를 기본 체크 상태로 표시, 사용자가 해제 가능
- "최소 1개 국가 선택" 유도 (강제는 아님)

### 4-2. Morning Briefing 푸시

**파일**: `worker/push/push_service.py`

새 함수 `send_morning_briefing()`:
- 매일 08:00 (사용자 로컬 시간) 발송
- 내용: 오늘의 영향도 점수 + #1 이슈 what_consumer + wallet_line
- 제목: ko "오늘의 분쟁 날씨" / en "Today's Conflict Weather"
- 본문: ko "{score}점 — {what_consumer}" / en "Score {score} — {what_consumer}"
- 대상: push 토큰이 있는 모든 활성 유저 (free 포함)

**파일**: `worker/tasks.py`

- 새 Celery beat 스케줄: `send_daily_briefings` (매 1시간, UTC 시간대별 배치)
- 기존 `send_daily_engagement` (L2257-2436)과 병합하지 않음 (목적이 다름)

### 4-3. WelcomeModal 개선

**파일**: `frontend/components/ui/WelcomeModal.tsx`

현재: feature 나열 + trust badge
변경:
- "이 앱은 분쟁 날씨앱이에요" 메시지로 교체
- feature 리스트를 3개 → 2개로 줄임:
  1. "세계 분쟁이 내 생활에 미치는 영향을 한눈에"
  2. "13개 기관의 데이터를 실시간 분석"
- Trust badge는 유지 (이미 좋음)

### 검증
- 온보딩 플로우 처음부터 끝까지 테스트 (localStorage 초기화)
- push_service 유닛테스트 (mock FCM)
- WelcomeModal 표시/닫기 확인

---

## Phase 5: 글로벌 인프라

> 글로벌 진출 준비. 현재 글로벌 준비 점수 37/100 → 60+ 목표.

### 5-1. i18n 폴백 영어 전환 (Phase 2-7에서 완료)

### 5-2. PPP 가격 표시 (UI만)

**파일**: `frontend/app/(main)/upgrade/page.tsx` (또는 PaywallModal)

- 현재: $6.99/$9.99 고정
- 변경: 기준국가별 "추천 가격" 표시 로직 추가
  - 백엔드에 `/pricing?country=XX` 엔드포인트 추가
  - 실제 결제 금액 변경은 Stripe 설정이 필요하므로 이 단계에서는 UI 표시만
  - 해당 국가의 PPP 기반 추천가를 "지역 가격 적용 예정" 라벨로 표시

### 5-3. 메타 태그 & OG 이미지 개선

**파일**: `frontend/app/layout.tsx` (루트 레이아웃)

- 영어 기본 title/description 설정
- lang 파라미터에 따른 동적 메타 태그

### 검증
- 영어 브라우저에서 접속 시 영어 UI 확인
- 폴백 동작: 없는 키는 영어로 표시되는지 확인
- OG 태그 확인 (`curl -I` 또는 Twitter Card Validator)

---

## 파일 변경 요약

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `backend/app/routers/impact.py` | 수정 | consumer 필드 + verification 필드 추가 |
| `frontend/app/(main)/home/client.tsx` | 대규모 수정 | Weather Header, Sankey 제거, 데이터 접기 |
| `frontend/components/dashboard/SmartSummaryCard.tsx` | 수정 | consumer 필드 사용, verification 배지 |
| `frontend/lib/i18n.ts` | 수정 | 새 키 추가 + 폴백 en으로 변경 |
| `frontend/app/(auth)/onboarding/page.tsx` | 수정 | GeoIP 자동감지 |
| `frontend/components/ui/WelcomeModal.tsx` | 수정 | 메시지 간소화 |
| `worker/push/push_service.py` | 수정 | morning briefing 함수 추가 |
| `worker/tasks.py` | 수정 | briefing Celery beat 추가 |
| `frontend/app/(main)/feed/client.tsx` | 수정 | consumer 필드 표시 |
| `frontend/app/(main)/issues/[id]/client.tsx` | 수정 | RiskRadar 이동 |

## 의존성

```
Phase 1 (백엔드) ──→ Phase 2 (홈 리디자인) ──→ Phase 3 (피드)
                                              ↘ Phase 4 (온보딩/푸시)
                                              ↘ Phase 5 (글로벌)
```

Phase 1이 완료되어야 Phase 2-5에서 새 필드를 사용 가능.
Phase 2-5는 서로 독립적으로 진행 가능.

## "AI가 한 티 안 나게" 체크리스트

- [ ] "AI가 분석했습니다" 같은 문구 사용 금지
- [ ] 모든 텍스트는 편집자가 작성한 것처럼 자연스럽게
- [ ] 챗봇/대화형 UI 없음
- [ ] "Generated by..." 라벨 없음
- [ ] verification_label도 "위성 확인됨"처럼 자연스러운 표현
- [ ] consumer 필드의 템플릿이 자연스러운 구어체인지 확인
- [ ] 뉴스레터 톤 참조: "호르무즈 해협이 막혔는데, 한국 원유 70%가 거길 지나요"

## 배포 순서

1. Phase 1: backend 배포 (`railway up --service backend`)
2. Phase 2-3: frontend 배포 (`railway up --service frontend` + `sh build-toss.sh`)
3. Phase 4: worker 배포 (`railway up --service worker`)
4. Phase 5: frontend 재배포
