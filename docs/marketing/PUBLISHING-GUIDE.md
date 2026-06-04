# WeWantPeace Newsletter — Weekly Publishing Guide

> 매주 일요일 09:00 발행. 금~토 작성, 토요일 밤 최종 확인.
>
> **R656-R663 기준** · EN/KO 이중 템플릿 · 55개 Handlebars 변수

---

## 1. 새 호 준비 (금요일)

### 1-1. 데이터 파일 복사
```bash
cd docs/marketing

# KR 데이터
cp vol1-kr-sample.json vol{N}-kr.json

# EN 데이터
cp vol1-us-sample.json vol{N}-us.json
```

### 1-2. 블록 디렉토리 생성
```bash
mkdir -p blocks
# 기존 블록을 복사해서 수정하는 게 빠름
for f in blocks/vol1-kr-*.html; do
  cp "$f" "blocks/vol{N}-kr-$(basename "$f" | sed 's/vol1-kr-//')"
done
```

---

## 2. 콘텐츠 작성 (금~토)

### 2-1. JSON 텍스트 변수 수정

| 변수 | 매주 변경 | 참고 |
|------|-----------|------|
| `vol_number` / `next_vol_number` | ✅ | N / N+1 |
| `issue_date` / `issue_date_short` / `issue_datetime` | ✅ | 발행일 |
| `issue_label` / `issue_label_long` | ✅ | 창간→Week 2→... |
| `preheader_text` | ✅ | Gmail 프리뷰, 120자 이내 |
| `hero_image_url` | ✅ | 1200x630px 뉴스 이미지 |
| `crisis_countries_count` / `crisis_prev` / `crisis_current` | ✅ | 위기 국가 수 |
| `crisis_trend` | ✅ | 추세 설명 |
| `events_24h` / `events_7d` | ✅ | API에서 가져오기 |
| `key_stats_line` | ✅ | 핵심 통계 한 줄 |
| `hero_headline_html` | ✅ | 히어로 헤드라인 (HTML) |
| `deep_dive_nav_label` / `deep_dive_title` | ✅ | 이번 주 딥다이브 주제 |
| `total_conflicts` / `urgent_count` / `active_issues_count` | ✅ | API에서 |
| `country_*` (name, code, rank, tension, etc.) | ✅ | 국가별 개인화 |
| `share_headline` / `share_subtext` | 격주 | 공유 문구 |
| `pro_cta_headline_html` / `pro_cta_subtext` | 격주 | Pro 마케팅 문구 |
| `tension_warning_html` | ✅ | 이상 신호 경고문 |
| `mailto_subject` / `mailto_body` | ✅ | URL-encoded |

### 2-2. HTML 블록 파일 작성 (15개)

| 블록 | 파일명 | 매주 완전 재작성 |
|------|--------|-----------------|
| Today's Brief | `vol{N}-kr-todays-brief.html` | ✅ 3개 헤드라인 |
| Tension Table | `vol{N}-kr-tension-table.html` | ✅ TOP 10 국가 |
| Conflicts | `vol{N}-kr-conflicts.html` | ✅ 4개 스토리 |
| Energy Intro | `vol{N}-kr-energy-intro.html` | ✅ 도입부 |
| Energy | `vol{N}-kr-energy.html` | ✅ BREAKING + 분석 |
| Deep Dive | `vol{N}-kr-deep-dive.html` | ✅ 이미지 + 타임라인 |
| Country Issues | `vol{N}-kr-country-issues.html` | ✅ 국가별 이슈 |
| Country Impact | `vol{N}-kr-country-impact.html` | ✅ 영향 분석 |
| Did You Know | `vol{N}-kr-did-you-know.html` | ✅ 팩트 1개 |
| Travel Intro | `vol{N}-kr-travel-intro.html` | ✅ 변경국 수 |
| Travel | `vol{N}-kr-travel.html` | ✅ Level 4/3 국가 |
| Numbers | `vol{N}-kr-numbers.html` | ✅ 6개 숫자 카드 |
| Calendar | `vol{N}-kr-calendar.html` | ✅ D-DAY 일정 |
| Editor's Note | `vol{N}-kr-editors-note.html` | ✅ 에디터 코멘트 |
| Next Week | `vol{N}-kr-next-week.html` | ✅ 3개 예고 |

---

## 3. 렌더링 & 검증 (토요일)

### 3-1. JSON에서 블록 참조 업데이트
```json
"tension_table_html": "@file:blocks/vol{N}-kr-tension-table.html",
"todays_brief_items_html": "@file:blocks/vol{N}-kr-todays-brief.html",
...
```

### 3-2. 렌더링
```bash
# 개별 렌더
python render-newsletter.py \
  --template newsletter-v1-final-ko.html \
  --data vol{N}-kr.json \
  --output newsletter-v{N}-rendered-kr.html

# 전체 배치 (render-all.sh에 새 variant 추가)
bash render-all.sh
```

### 3-3. 검증 체크리스트

- [ ] **사이즈**: 102KB 이하 (Gmail 클리핑 방지)
- [ ] **미해결 변수**: `WARNING: unresolved` 없음
- [ ] **브라우저 확인**: 렌더된 HTML 파일을 브라우저에서 열어 시각 확인
- [ ] **모바일 시뮬**: Chrome DevTools > 390px 폭에서 레이아웃 깨짐 없는지
- [ ] **링크 확인**: UTM 파라미터 포함된 링크가 올바른지
- [ ] **이미지**: hero_image_url이 로드되는지
- [ ] **날짜**: 모든 날짜가 이번 주인지

---

## 4. 발송 (일요일 09:00)

### 이메일 발송 도구 (미정)
- [ ] Mailchimp / Sendgrid / Brevo 등 선택
- [ ] 수신자 리스트 관리
- [ ] A/B 테스트 (제목줄)

### 발송 전 최종 확인
- [ ] 프리헤더 텍스트 확인
- [ ] 수신거부 링크 동작 확인
- [ ] 테스트 발송 (자신에게 먼저)
- [ ] Gmail, Apple Mail, Outlook에서 렌더링 확인

---

## 5. 파일 네이밍 규칙

```
vol{N}-{country_code}-{block_name}.html    # 블록
vol{N}-{country_code}.json                  # 데이터
newsletter-v{N}-rendered-{country_code}.html # 렌더 결과
```

예시:
- `vol2-kr.json`, `vol2-us.json`
- `blocks/vol2-kr-tension-table.html`
- `newsletter-v2-rendered-kr.html`

---

## 6. 이메일 제목줄 (Subject Line)

오픈율에 가장 큰 영향. 모바일에서 35자 내로 보이므로 핵심을 앞에.

### 공식

```
[WeWantPeace] {긴급도} — {핵심 팩트} ({한국/독자 관련})
```

### 예시 — KR

| Subject | 왜 좋은지 |
|---------|-----------|
| `[WWP] 호르무즈 봉쇄 — 한국 원유 70% 직격` | 핵심 사건 + 독자 연관 |
| `[WWP] 23개국 위기 — 기름값 왜 오르는지 2분` | 숫자 + 호기심 + 시간 |
| `[WWP] 이란 2,048건 폭증 — 당신 주유소 가격표가 바뀝니다` | 구체적 숫자 + 개인 영향 |

### 예시 — EN

| Subject | Why it works |
|---------|-------------|
| `[WWP] Hormuz blocked — 23 countries in crisis` | Event + scale |
| `[WWP] Oil $118, Iran 2,048 events — how it hits your wallet` | Numbers + personal |
| `[WWP] Your country ranked #9 in tension. Here's why.` | Personalized + curiosity |

### 제목줄 규칙

1. **35자 이내** (모바일 가시 영역)
2. **숫자 포함** (23개국, $118, 96.8점)
3. **개인 연관** (한국, 내 지갑, 당신)
4. **긴급감** (봉쇄, 폭증, 급등)
5. **emoji 금지** (스팸 필터 트리거)
6. **대문자 남용 금지** (ALL CAPS → 스팸)

---

## 7. 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| 102KB 초과 | 블록이 너무 큼 | 이미지 제거, 텍스트 축소, 테이블 행 줄이기 |
| 미해결 변수 | JSON에 키 누락 | 스키마 문서 참조해서 추가 |
| Gmail에서 잘림 | 102KB 초과 | 사이즈 줄이기 |
| Outlook 깨짐 | CSS 미지원 | VML fallback 확인 (이미 포함됨) |
| 이미지 안 보임 | 상대 경로 | 절대 URL 사용 |
