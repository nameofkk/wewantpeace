# WeWantPeace - Awesome Lists PR 초안

> 작성일: 2026-03-09
> 상태: 초안 준비 완료 (PR 미제출)

---

## 요약: 적합성 판단 결과

| # | 리스트 | Stars | 적합 여부 | 제출 가능 시기 | 비고 |
|---|--------|-------|----------|--------------|------|
| 1 | awesome-selfhosted/awesome-selfhosted | 180k+ | **조건부** | 2026-06-25 이후 | CC-BY-NC-4.0 = non-free 섹션, 4개월 규칙 |
| 2 | jnv/lists | 10k+ | **해당 없음** | - | "리스트의 리스트"이므로 개별 프로젝트 등록 불가 |
| 3 | jivoi/awesome-osint | 18k+ | **적합** | 즉시 가능 | News Digest / Geospatial 카테고리 |
| 4 | EticaAI/awesome-humanitarian-foss | 500+ | **적합** | 즉시 가능 | Humanitarian Platform 카테고리 |
| 5 | DisasterTechCrew/awesome-disastertech | 300+ | **적합** | 즉시 가능 | General solutions 카테고리 |
| 6 | AboutRSS/ALL-about-RSS | 5k+ | **적합** | 즉시 가능 | RSS 기반 수집 플랫폼 |

---

## 1. awesome-selfhosted/awesome-selfhosted

### 적합성 분석

**레포**: https://github.com/awesome-selfhosted/awesome-selfhosted
**데이터 레포**: https://github.com/awesome-selfhosted/awesome-selfhosted-data

#### 문제점

1. **4개월 규칙**: 첫 릴리스가 4개월 이상 경과해야 함.
   - WeWantPeace 첫 커밋: 2026-02-25
   - **최소 제출 가능일: 2026-06-25**

2. **라이선스**: CC-BY-NC-4.0은 "non-free" 라이선스로 분류됨.
   - 메인 리스트(FOSS만)가 아닌 **non-free.md** 섹션에만 등록 가능
   - `licenses-nonfree.yml`에 CC-BY-NC-4.0이 이미 등록되어 있음

3. **소스 코드 공개**: 현재 GitHub 레포가 private이면 문제됨
   - awesome-selfhosted는 `source_code_url` 필수

#### 해결 방안
- 라이선스를 AGPL-3.0으로 변경하면 **메인 리스트** 등록 가능
- 현재 CC-BY-NC-4.0 유지 시 non-free 섹션 등록

#### 카테고리
- 메인 리스트: "Maps and Global Positioning System (GPS)" 또는 "Feed Readers" (RSS 기반이므로)
- non-free: "Analytics" 또는 신규 카테고리 제안 가능

### PR 제출 방식 (awesome-selfhosted-data 레포)

`software/wewantpeace.yml` 파일을 생성하여 PR 제출:

```yaml
# software/wewantpeace.yml
name: WeWantPeace
website_url: https://www.wewantpeace.live
source_code_url: https://github.com/nameofkk/wewantpeace
description: >-
  Real-time global conflict monitoring platform with AI-powered severity scoring,
  interactive map, country-level tension index tracking, and personalized impact analysis.
  Aggregates 58+ RSS/Telegram sources across 69 countries with 5-minute refresh cycle.
licenses:
  - CC-BY-NC-4.0
platforms:
  - Python
  - Nodejs
  - Docker
tags:
  - Maps and Global Positioning System (GPS)
demo_url: https://www.wewantpeace.live
depends_3rdparty: true
```

### PR 본문 초안

```markdown
## Add WeWantPeace - Real-time global conflict monitoring platform

### Description
WeWantPeace is a self-hosted real-time global conflict monitoring platform that aggregates
news from 58+ RSS and Telegram sources across 69 countries. It features AI-powered severity
scoring (0-10 scale), an interactive MapLibre GL map with cluster markers, country-level
tension index tracking, trending keyword detection, and personalized impact analysis.

### Checklist
- [x] The software has been released for more than 4 months
- [x] The pull request adds one software entry
- [x] Description is less than 250 characters
- [x] Installation instructions / documentation are provided
- [x] The software is actively maintained
- [x] The software runs as a web application on the server

### Additional information
- **Tech stack**: FastAPI (Python) + Next.js 14 (React) + PostgreSQL + Redis + Celery
- **Data pipeline**: RSS/Telegram collection → AI normalization → deduplication → clustering → spike detection → tension index → push notifications
- **Self-hosting**: Docker Compose deployment with `docker-compose.yml` provided
- **Demo**: https://www.wewantpeace.live
- **License**: CC-BY-NC-4.0 (non-free section)
```

---

## 2. jnv/lists

### 적합성 분석

**레포**: https://github.com/jnv/lists

**결론: 해당 없음**

이 레포는 "awesome list들의 메타 리스트"입니다. 개별 프로젝트가 아닌 큐레이션된 리스트(awesome-xxx)만 등록합니다. WeWantPeace는 개별 프로젝트이므로 등록 대상이 아닙니다.

---

## 3. jivoi/awesome-osint

### 적합성 분석

**레포**: https://github.com/jivoi/awesome-osint
**Stars**: 18k+
**적합 여부**: 적합

WeWantPeace는 OSINT(Open Source Intelligence) 도구로 분류될 수 있습니다:
- 공개 RSS/Telegram 소스에서 정보 수집
- AI 기반 분류/심각도 평가
- 지리적 분석 및 시각화
- 실시간 모니터링 및 스파이크 감지

#### 등록 카테고리
- **"News Digest and Discovery Tools"** - 가장 적합
- 또는 **"Geospatial Research and Mapping Tools"** - 지도 기능 강조 시

#### 항목 형식
```markdown
- [Tool Name](URL) - Brief description.
```

### PR 본문 초안

**PR 제목**: `Add WeWantPeace to News Digest and Discovery Tools`

**커밋 메시지**: `Add WeWantPeace - real-time global conflict monitoring platform`

**README.md에 추가할 내용** (News Digest and Discovery Tools 섹션, 알파벳 순):

```markdown
- [WeWantPeace](https://www.wewantpeace.live) - Real-time global conflict monitoring platform that aggregates 58+ open sources (RSS/Telegram) across 69 countries with AI-powered severity scoring, interactive conflict map, and country-level tension index tracking.
```

**PR 본문**:

```markdown
## Add WeWantPeace to News Digest and Discovery Tools

### What is WeWantPeace?

WeWantPeace is a real-time global conflict monitoring and OSINT platform that:

- **Aggregates** 58+ open sources (RSS feeds + Telegram channels) covering 69 countries
- **AI-classifies** each event by topic, severity (0-10), and geographic relevance
- **Visualizes** conflicts on an interactive MapLibre GL map with cluster markers and pulse animations
- **Tracks** country-level tension indices with time-series analysis
- **Detects** spikes and trending keywords using KScore (Key Impact Score) algorithm
- **Delivers** personalized push notifications based on user's interest countries/topics

### Why it belongs in awesome-osint

WeWantPeace is an OSINT tool for monitoring global conflicts and geopolitical events.
It processes publicly available information sources in real-time and provides analytical
capabilities (severity scoring, trend detection, tension indices) that are valuable for
researchers, journalists, analysts, and anyone tracking global security situations.

### Links
- **Live platform**: https://www.wewantpeace.live
- **GitHub**: https://github.com/nameofkk/wewantpeace
- **Tech stack**: FastAPI + Next.js + PostgreSQL + Celery + MapLibre GL

### Self-promotion disclosure
I am the developer of WeWantPeace. This is a self-promotional submission.
```

---

## 4. EticaAI/awesome-humanitarian-foss

### 적합성 분석

**레포**: https://github.com/EticaAI/awesome-humanitarian-foss
**적합 여부**: 적합

WeWantPeace는 인도주의적 목적의 분쟁 모니터링 도구로, 이 리스트의 취지에 부합합니다.

#### 등록 카테고리
현재 카테고리: Education, Healthcare, Humanitarian Platform, Human Rights
- **"Humanitarian Platform"** 또는 새 카테고리 **"Conflict Monitoring / Peacebuilding"** 제안

#### 항목 형식 (테이블)
```markdown
| Category | Name | Repository | Main skills | Tags | Description |
```

### PR 본문 초안

**PR 제목**: `Add WeWantPeace - Real-time conflict monitoring platform`

**테이블에 추가할 행**:

```markdown
| Conflict Monitoring | [WeWantPeace](https://www.wewantpeace.live) | [nameofkk/wewantpeace](https://github.com/nameofkk/wewantpeace) | Python, JavaScript, Docker | conflict, monitoring, OSINT, maps | Real-time global conflict monitoring with AI severity scoring, interactive map, and tension index tracking across 69 countries |
```

**PR 본문**:

```markdown
## Add WeWantPeace - Real-time global conflict monitoring platform

### About

WeWantPeace is a humanitarian-focused platform that monitors global conflicts in real-time.
It aggregates 58+ open sources across 69 countries, providing:

- AI-powered severity scoring for each conflict event
- Interactive conflict map with geographic visualization
- Country-level tension index tracking
- Spike detection and trending analysis
- Personalized alerts for regions of interest

### Humanitarian purpose

The platform's core mission is to increase awareness of global conflicts and their
humanitarian impact. It helps:

- **Journalists** track developing crises in real-time
- **Researchers** analyze conflict patterns and trends
- **NGO workers** monitor situations in their operational areas
- **Citizens** stay informed about global security through personalized impact analysis

### Technical details
- **License**: CC-BY-NC-4.0
- **Stack**: FastAPI (Python) + Next.js (React) + PostgreSQL + Redis + Celery
- **Deployment**: Docker Compose, self-hostable
- **Data sources**: RSS feeds, Telegram channels (all publicly available)

### Category suggestion
I suggest adding a new category "Conflict Monitoring / Peacebuilding" as this area
is currently not represented in the list. Alternatively, it fits under "Humanitarian Platform".
```

---

## 5. DisasterTechCrew/awesome-disastertech

### 적합성 분석

**레포**: https://github.com/DisasterTechCrew/awesome-disastertech
**적합 여부**: 적합

이 리스트에는 이미 CrisisTracker, Ushahidi, DEEP 등 위기 모니터링 도구가 포함되어 있습니다.

#### 등록 카테고리
- **"Awesome projects > General solutions"** - 가장 적합

#### 항목 형식
```markdown
- [Project Name](URL) - Description.
```

### PR 본문 초안

**PR 제목**: `Add WeWantPeace - Real-time global conflict monitoring`

**README.md에 추가할 내용** (General solutions 섹션):

```markdown
- [WeWantPeace](https://www.wewantpeace.live) - Real-time global conflict monitoring platform that aggregates 58+ open sources across 69 countries. Features AI-powered severity scoring, interactive conflict map, country-level tension indices, spike detection, and personalized alerts. ([GitHub](https://github.com/nameofkk/wewantpeace))
```

**PR 본문**:

```markdown
## Add WeWantPeace to General solutions

### What is it?

WeWantPeace is a real-time global conflict monitoring platform designed to help people
track and understand ongoing crises worldwide. Similar to existing entries like CrisisTracker
and Ushahidi, it provides situational awareness through automated data collection and analysis.

### Key features relevant to disaster/crisis tech

- **Real-time monitoring**: 5-minute refresh cycle across 58+ sources (RSS/Telegram)
- **AI severity scoring**: Automated 0-10 severity classification for each event
- **Interactive map**: MapLibre GL-based conflict visualization with clustering
- **Tension index**: Country-level crisis tracking with time-series analysis
- **Spike detection**: Early warning system for escalating situations
- **Push notifications**: Personalized alerts for monitored regions
- **Coverage**: 69 countries currently monitored

### Technical details
- **Stack**: Python (FastAPI) + React (Next.js) + PostgreSQL + Redis
- **Deployment**: Docker Compose
- **License**: CC-BY-NC-4.0
- **Live**: https://www.wewantpeace.live
```

---

## 6. AboutRSS/ALL-about-RSS

### 적합성 분석

**레포**: https://github.com/AboutRSS/ALL-about-RSS
**Stars**: 5k+
**적합 여부**: 적합 (RSS 기반 수집 플랫폼)

WeWantPeace는 37+ RSS 피드를 핵심 데이터 소스로 사용하며, RSS 기반 뉴스 수집/분석 플랫폼입니다.

#### 등록 카테고리
- **"Information Aggregators"** 또는 **"RSS Feed Enhancement"** 섹션

### PR 본문 초안

**PR 제목**: `Add WeWantPeace - RSS-based global conflict monitoring`

**추가할 항목**:

```markdown
- [WeWantPeace](https://www.wewantpeace.live) [![Open-Source Software](https://github.com/AboutRSS/ALL-about-RSS/raw/master/media/open-source.png)](https://github.com/nameofkk/wewantpeace) - Real-time global conflict monitoring platform that aggregates 37+ RSS feeds across 69 countries with AI-powered analysis, interactive map, and severity scoring.
```

**PR 본문**:

```markdown
## Add WeWantPeace - RSS-based global conflict monitoring platform

WeWantPeace heavily relies on RSS as its primary data collection mechanism:

- **37+ RSS feeds** from major news agencies (Reuters, AP, BBC, Al Jazeera, etc.)
- Automated RSS collection with 5-minute refresh cycles via Celery Beat
- AI-powered analysis pipeline: RSS collection → normalization → deduplication → clustering
- Additional sources: 12 Telegram channels + 3 APIs

The platform transforms raw RSS feeds into actionable conflict intelligence with
severity scoring, geographic mapping, and trend analysis.

### Links
- **Live**: https://www.wewantpeace.live
- **GitHub**: https://github.com/nameofkk/wewantpeace
- **License**: CC-BY-NC-4.0
```

---

## 추가 탐색 결과: 기타 잠재 리스트

### 현재 적합하지 않은 리스트

| 리스트 | 사유 |
|--------|------|
| jnv/lists | 개별 프로젝트 아닌 "리스트의 리스트" |
| analysis-tools-dev/static-analysis | 코드 분석 도구 전용 (해당 없음) |
| TechforgoodCAST/awesome-techforgood | peace/conflict 카테고리 없음 |
| hal9ai/awesome-dataviz | 라이브러리/프레임워크 위주 (플랫폼 아님) |
| obazoud/awesome-dashboard | 대시보드 도구/프레임워크 위주 |

### 향후 고려할 리스트

| 리스트 | 비고 |
|--------|------|
| awesome-selfhosted (메인) | 2026-06-25 이후 제출 가능 (4개월 규칙) |
| sindresorhus/awesome | "awesome list" 자체를 등록 (WeWantPeace 전용 awesome 리스트 필요) |

---

## 제출 우선순위 및 일정

### 즉시 제출 가능 (2026-03 현재)

1. **jivoi/awesome-osint** (18k stars) - 가장 높은 노출 효과
2. **DisasterTechCrew/awesome-disastertech** - 정확한 카테고리 매칭
3. **EticaAI/awesome-humanitarian-foss** - 인도주의적 목적 강조

### 조건부 제출

4. **AboutRSS/ALL-about-RSS** (5k stars) - RSS 기반 특성 강조
5. **awesome-selfhosted** (180k stars) - 2026-06-25 이후 (레포 공개 + 4개월 경과 필요)

---

## 체크리스트: PR 제출 전 준비사항

- [ ] GitHub 레포를 public으로 전환 (현재 private일 수 있음)
- [ ] 영어 README.md 추가 또는 번역 (현재 한국어)
- [ ] Docker Compose 기반 설치 가이드 정비 (`infra/docker-compose.yml`)
- [ ] `.env.example` 파일 정비 (필수 환경변수 문서화)
- [ ] 데모 스크린샷 또는 GIF 추가
- [ ] GitHub Release / tag 생성 (버전 넘버링)
- [ ] LICENSE 파일 SPDX 형식 확인 (CC-BY-NC-4.0)
- [ ] awesome-selfhosted 제출 시: 라이선스 변경 검토 (AGPL-3.0 → 메인 리스트 등록 가능)

---

## 핵심 권고사항

### 1. 라이선스 전략
현재 CC-BY-NC-4.0은 awesome-selfhosted에서 "non-free"로 분류됩니다.
**AGPL-3.0으로 변경을 강력히 권고합니다**:
- awesome-selfhosted 메인 리스트 등록 가능 (180k stars 노출)
- AGPL-3.0도 상업적 사용을 실질적으로 제한 (소스 공개 의무)
- 대부분의 awesome 리스트에서 FOSS로 인정

### 2. 영어 README 필수
현재 README.md가 한국어입니다. 국제 awesome 리스트에 PR을 제출하려면:
- 영어 README를 별도로 작성하거나
- README.md를 영어로 전환하고 한국어는 README.ko.md로 이동

### 3. 레포 공개
GitHub 레포가 public이어야 소스 코드 링크를 제공할 수 있습니다.
awesome-selfhosted는 `source_code_url` 필수 필드입니다.
