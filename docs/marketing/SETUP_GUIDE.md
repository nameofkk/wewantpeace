# WeWantPeace 마케팅 채널 세팅 가이드

> 신혁님이 직접 수행해야 하는 수동 작업 가이드.
> 코드는 이미 구현 완료 -- 아래 플랫폼별 외부 계정 생성 + Railway 환경변수 등록만 하면 자동 발행이 시작됩니다.

**Railway 환경변수 추가 방법 (공통)**

모든 플랫폼의 환경변수는 **worker 서비스** (서비스 ID: `2ee51089`)에 추가합니다.

```bash
# Railway GraphQL API로 환경변수 추가 (한 번에 하나씩)
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{
    "query": "mutation { variableUpsert(input: { projectId: \"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\", environmentId: \"92d7e229-1071-4b32-a12c-8336ef7be7d5\", serviceId: \"2ee51089\", name: \"변수명\", value: \"값\" }) }"
  }'
```

또는 Railway 대시보드: https://railway.app → 프로젝트 → worker 서비스 → Variables 탭 → "New Variable"

---

## 1. Telegram 채널 (5분, 최우선)

> 난이도: 쉬움 | 비용: 무료 | 승인 대기: 없음

Telegram은 API 제한이 거의 없고, 봇 생성 즉시 사용 가능하여 가장 먼저 세팅하기 좋습니다.

### Step 1: 채널 생성

1. **Telegram 앱** (모바일 또는 데스크톱) 열기
2. 왼쪽 상단 **햄버거 메뉴 (☰)** → **"New Channel"** 클릭
3. 채널 정보 입력:
   - **이름**: `WeWantPeace - Global Conflict Tracker`
   - **설명**: `Real-time global conflict monitoring & severity tracking. 실시간 글로벌 분쟁 추적.`
   - **프로필 사진**: WeWantPeace 로고 업로드 (선택)
4. **Channel Type**: **"Public Channel"** 선택
5. **Public Link** 설정:
   - 우선 시도: `@WeWantPeace`
   - 이미 사용 중이면: `@wewantpeace_live` 또는 `@wewantpeace_alerts`
6. "Create" 버튼으로 채널 생성 완료

### Step 2: 브로드캐스트 봇 생성

1. Telegram에서 **@BotFather** 검색 → 대화 시작
2. `/newbot` 입력
3. 봇 이름 입력: `WeWantPeace Alert Bot`
4. 봇 username 입력: `wewantpeace_alert_bot` (또는 `wewantpeace_broadcast_bot`)
5. BotFather가 **HTTP API 토큰**을 반환합니다:
   ```
   123456789:ABCdefGhIjKlMnOpQrStUvWxYz
   ```
   → 이 토큰을 복사해 둡니다 (= `TELEGRAM_BROADCAST_BOT_TOKEN` 값)

### Step 3: 봇을 채널 관리자로 추가

1. 생성한 채널 열기 → 채널 이름 클릭 → **"Administrators"**
2. **"Add Administrator"** → 방금 만든 봇 (`@wewantpeace_alert_bot`) 검색하여 추가
3. 권한 설정:
   - **"Post Messages"**: 반드시 ON
   - **"Edit Messages of Others"**: ON (권장)
   - 나머지는 OFF 가능
4. "Done" 클릭

### Step 4: 채널 ID 확인

**방법 A — getUpdates API (권장):**

1. 채널에 아무 메시지 하나 직접 작성 (예: "test")
2. 브라우저에서 다음 URL 접속:
   ```
   https://api.telegram.org/bot<봇토큰>/getUpdates
   ```
   예시:
   ```
   https://api.telegram.org/bot123456789:ABCdefGhIjKlMnOpQrStUvWxYz/getUpdates
   ```
3. JSON 응답에서 `"chat"` → `"id"` 값 확인:
   ```json
   "chat": {
     "id": -1001234567890,
     "title": "WeWantPeace - Global Conflict Tracker",
     "type": "channel"
   }
   ```
   → `-1001234567890` 가 채널 ID입니다 (마이너스 포함 전체가 ID)

**방법 B — @username 직접 사용:**

채널이 Public이면 `@WeWantPeace` 를 채널 ID로 사용 가능합니다.
(숫자 ID가 더 안정적이므로 방법 A 권장)

### Step 5: Railway 환경변수 등록

아래 3개 변수를 worker 서비스에 추가:

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `TELEGRAM_BROADCAST_BOT_TOKEN` | `123456789:ABCdefGhIjKlMnOpQrStUvWxYz` | BotFather에서 받은 토큰 |
| `TELEGRAM_BROADCAST_CHANNEL_ID` | `-1001234567890` | 채널 숫자 ID (또는 `@username`) |
| `SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED` | `true` | 플랫폼 활성화 |

```bash
# 실행 예시 (3개 명령 순차 실행)
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{"query":"mutation{variableUpsert(input:{projectId:\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\",environmentId:\"92d7e229-1071-4b32-a12c-8336ef7be7d5\",serviceId:\"2ee51089\",name:\"TELEGRAM_BROADCAST_BOT_TOKEN\",value:\"봇토큰\"})}"}'

curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{"query":"mutation{variableUpsert(input:{projectId:\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\",environmentId:\"92d7e229-1071-4b32-a12c-8336ef7be7d5\",serviceId:\"2ee51089\",name:\"TELEGRAM_BROADCAST_CHANNEL_ID\",value:\"채널ID\"})}"}'

curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{"query":"mutation{variableUpsert(input:{projectId:\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\",environmentId:\"92d7e229-1071-4b32-a12c-8336ef7be7d5\",serviceId:\"2ee51089\",name:\"SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED\",value:\"true\"})}"}'
```

### Step 6: 동작 확인

환경변수 등록 후 worker 서비스가 자동 재배포됩니다. 이후:
- 승인된 social_posts 중 `platform='telegram_channel'`인 포스트가 자동 발행됩니다
- Telegram 관리자 봇 (`telegram_bot.py`)의 승인 플로우에서 Telegram Channel도 발행 대상에 포함됩니다

---

## 2. X (Twitter) API (30분)

> 난이도: 보통 | 비용: Free tier 무료 (월 1,500 트윗) | 승인 대기: 즉시~24시간

**현재 상태**: 코드에서 `SOCIAL_PLATFORM_X_ENABLED`의 기본값이 `true`로 되어 있으므로, API 키만 등록하면 즉시 동작합니다.

### Step 1: X Developer 계정 신청

1. https://developer.x.com/ 접속
2. 우측 상단 **"Sign up"** 또는 기존 X 계정으로 로그인
3. **"Developer Portal"** 진입 → **"Sign up for Free Account"**
4. 사용 목적 작성 (200자 이상):
   ```
   WeWantPeace is a non-profit global conflict monitoring platform. We use the
   X API to automatically post real-time conflict severity updates, daily movers
   reports, and spike alerts in bilingual format (English/Korean) to raise
   public awareness about ongoing conflicts worldwide. Our posts include
   AI-generated severity analysis based on aggregated news data.
   ```
5. 약관 동의 → **"Submit"**

### Step 2: 프로젝트 & 앱 생성

1. Developer Portal 왼쪽 사이드바 → **"Projects & Apps"**
2. **"+ Create Project"** 클릭
3. 프로젝트 정보:
   - **Project name**: `WeWantPeace`
   - **Use case**: `Making a bot` 선택
   - **Description**: `Automated conflict severity alerts and daily reports`
4. 프로젝트 내 **App 생성**:
   - **App name**: `wewantpeace-bot`
5. 생성 완료 시 키가 표시됨 → 즉시 복사

### Step 3: 키 발급 및 권한 설정

생성 직후 표시되는 키:
- **API Key** (= Consumer Key) → `X_API_KEY`
- **API Key Secret** (= Consumer Secret) → `X_API_SECRET`

Access Token 발급:
1. App 상세 페이지 → **"Keys and Tokens"** 탭
2. **"Access Token and Secret"** 섹션 → **"Generate"** 클릭
3. 표시되는 값:
   - **Access Token** → `X_ACCESS_TOKEN`
   - **Access Token Secret** → `X_ACCESS_SECRET`

**권한 설정 (중요!):**
1. App 상세 페이지 → **"Settings"** 탭
2. **"User authentication settings"** → **"Set up"** 클릭
3. **App permissions**: **"Read and Write"** 선택 (반드시!)
   - "Read" 만 선택하면 트윗 발행 불가
4. 저장 후 **Access Token을 반드시 재생성** (권한 변경 시 기존 토큰 무효화됨)

### Step 4: Railway 환경변수 등록

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `X_API_KEY` | `발급받은 API Key` | Consumer Key |
| `X_API_SECRET` | `발급받은 API Key Secret` | Consumer Secret |
| `X_ACCESS_TOKEN` | `발급받은 Access Token` | OAuth 1.0a |
| `X_ACCESS_SECRET` | `발급받은 Access Token Secret` | OAuth 1.0a |
| `SOCIAL_PLATFORM_X_ENABLED` | `true` | 이미 기본값 true (확인용) |

```bash
# 4개 변수 등록 (값을 실제 키로 교체)
for VAR_PAIR in \
  "X_API_KEY:여기에_API_KEY" \
  "X_API_SECRET:여기에_API_SECRET" \
  "X_ACCESS_TOKEN:여기에_ACCESS_TOKEN" \
  "X_ACCESS_SECRET:여기에_ACCESS_SECRET"; do
  NAME="${VAR_PAIR%%:*}"
  VALUE="${VAR_PAIR#*:}"
  curl -s -X POST https://backboard.railway.app/graphql/v2 \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
    -d "{\"query\":\"mutation{variableUpsert(input:{projectId:\\\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\\\",environmentId:\\\"92d7e229-1071-4b32-a12c-8336ef7be7d5\\\",serviceId:\\\"2ee51089\\\",name:\\\"$NAME\\\",value:\\\"$VALUE\\\"})}\"}"
done
```

### Step 5: 동작 확인

- X 어댑터는 **이미지 자동 첨부**를 지원합니다 (tweepy v1.1 media_upload)
- 비프리미엄 계정 링크 노출 패널티 대비: URL 제거, 브랜드명 CTA만 표시
- 280자 제한 내에서 bilingual 헤드라인 스타일로 포스팅됩니다

### 주의사항

- **Free tier 제한**: 월 1,500 트윗, 읽기 제한 있음
- 트윗 발행 실패 시 로그에 `"X 트윗 발행 실패"` 메시지 확인
- API Key를 **절대 공개 저장소에 커밋하지 않을 것** (환경변수로만 관리)

---

## 3. LinkedIn Company Page (15분)

> 난이도: 보통 | 비용: 무료 | 승인 대기: 앱 심사 필요 (수일~수주)

### Step 1: LinkedIn Company Page 생성 (이미 있으면 건너뛰기)

1. https://www.linkedin.com/ 로그인
2. 왼쪽 사이드바 또는 상단 "For Business" → **"Create a Company Page"**
3. **"Company"** 선택
4. 정보 입력:
   - **Name**: `WeWantPeace`
   - **LinkedIn public URL**: `wewantpeace`
   - **Industry**: `Civic & Social Organization` 또는 `Non-profit Organization Management`
   - **Organization size**: `2-10 employees`
   - **Organization type**: `Nonprofit`
5. **"Create page"** 클릭
6. 생성 후 Company Page URL에서 **Organization ID 확인**:
   - 관리자 페이지 URL: `https://www.linkedin.com/company/12345678/admin/`
   - `12345678`이 Organization ID → `LINKEDIN_ORG_ID` 값

### Step 2: LinkedIn Developer App 생성

1. https://www.linkedin.com/developers/ 접속 → **"Create App"** 클릭
2. App 정보:
   - **App name**: `WeWantPeace Social Bot`
   - **LinkedIn Page**: 방금 만든 `WeWantPeace` Company Page 연결
   - **App logo**: WeWantPeace 로고 업로드
   - **Legal agreement**: 체크
3. **"Create App"** 클릭

### Step 3: 권한(Product) 추가

1. App 상세 → **"Products"** 탭
2. 다음 Product를 **"Request Access"**:
   - **"Share on LinkedIn"** → UGC Post 발행 권한 (필수)
   - **"Sign In with LinkedIn using OpenID Connect"** → 인증용 (선택)
3. **"Share on LinkedIn"**은 Company Page 관리자 인증 후 즉시 승인됩니다
4. 승인 완료 확인: **"Products"** 탭에서 Status가 "Approved"

### Step 4: OAuth2 Access Token 발급

**방법 A — LinkedIn Developer Portal에서 직접 (가장 간단):**

1. App 상세 → **"Auth"** 탭
2. **"OAuth 2.0 tools"** 섹션 → **"Generate token"** 클릭
3. Scope 선택: `w_member_social`, `w_organization_social`
4. 생성된 토큰 복사 → `LINKEDIN_ACCESS_TOKEN`

**방법 B — 3-legged OAuth2 (수동):**

1. App 상세 → **"Auth"** 탭에서 확인:
   - **Client ID**
   - **Client Secret**
   - **Redirect URL**: `https://www.wewantpeace.live/callback` (임시)
2. 브라우저에서 인증 URL 접속:
   ```
   https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=<CLIENT_ID>&redirect_uri=https://www.wewantpeace.live/callback&scope=w_member_social%20w_organization_social
   ```
3. 로그인 & 권한 동의 → redirect URL의 `?code=` 파라미터 복사
4. 토큰 교환:
   ```bash
   curl -X POST https://www.linkedin.com/oauth/v2/accessToken \
     -d "grant_type=authorization_code" \
     -d "code=<AUTH_CODE>" \
     -d "redirect_uri=https://www.wewantpeace.live/callback" \
     -d "client_id=<CLIENT_ID>" \
     -d "client_secret=<CLIENT_SECRET>"
   ```
5. 응답의 `access_token` 복사

**토큰 유효기간**: 60일. 만료 전 갱신 필요 (refresh_token으로 자동화 가능, 추후 구현).

### Step 5: Railway 환경변수 등록

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `LINKEDIN_ACCESS_TOKEN` | `발급받은 Access Token` | OAuth2 Bearer 토큰 |
| `LINKEDIN_ORG_ID` | `12345678` | Company Page Organization ID |
| `SOCIAL_PLATFORM_LINKEDIN_ENABLED` | `true` | 플랫폼 활성화 |

```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{"query":"mutation{variableUpsert(input:{projectId:\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\",environmentId:\"92d7e229-1071-4b32-a12c-8336ef7be7d5\",serviceId:\"2ee51089\",name:\"LINKEDIN_ACCESS_TOKEN\",value:\"토큰값\"})}"}'

curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{"query":"mutation{variableUpsert(input:{projectId:\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\",environmentId:\"92d7e229-1071-4b32-a12c-8336ef7be7d5\",serviceId:\"2ee51089\",name:\"LINKEDIN_ORG_ID\",value:\"조직ID\"})}"}'

curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{"query":"mutation{variableUpsert(input:{projectId:\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\",environmentId:\"92d7e229-1071-4b32-a12c-8336ef7be7d5\",serviceId:\"2ee51089\",name:\"SOCIAL_PLATFORM_LINKEDIN_ENABLED\",value:\"true\"})}"}'
```

### 주의사항

- LinkedIn Access Token은 **60일 후 만료** → 갱신 자동화를 추후 구현하거나, 달력에 리마인더 설정
- Company Page 연결이 안 되면 `w_organization_social` scope 사용 불가 → 반드시 App과 Company Page를 연결할 것
- 이미지 첨부: registerUpload → PUT upload → ugcPost 3-step으로 자동 처리됨

---

## 4. Threads + Instagram (Meta 앱 통합, 30분)

> 난이도: 높음 | 비용: 무료 | 승인 대기: 앱 심사 필요

Threads와 Instagram은 동일한 **Meta Developer App**에서 관리합니다. 하나의 앱으로 두 플랫폼 토큰을 모두 발급받을 수 있습니다.

### 사전 조건

- **Instagram Business 또는 Creator 계정** 필요 (개인 계정 불가)
- Threads 계정은 Instagram 계정에 자동 연동됨

### Step 1: Instagram 계정을 Professional 계정으로 전환

1. Instagram 앱 → 프로필 → 우측 상단 **햄버거 메뉴 (☰)**
2. **"Settings and privacy"** → **"Account type and tools"** → **"Switch to professional account"**
3. 카테고리: `News & Media Website` 또는 `Non-Governmental Organization`
4. 유형: **"Creator"** 선택 (Business도 가능하나 Creator가 더 유연)
5. 전환 완료 확인

### Step 2: Meta Developer App 생성

1. https://developers.facebook.com/ 접속 → 로그인
2. 상단 **"My Apps"** → **"Create App"**
3. App Type: **"Business"** 선택
4. App 정보:
   - **App name**: `WeWantPeace Social`
   - **Contact email**: 본인 이메일
5. **"Create App"** 클릭

### Step 3: Threads API 제품 추가

1. App Dashboard → 왼쪽 사이드바 → **"Add Product"**
2. **"Threads API"** 찾기 → **"Set up"** 클릭
3. **"Threads API"** → **"Settings"**:
   - **Instagram account**: WeWantPeace Instagram 계정 연결
4. **Use Case** → **"threads_content_publish"** 활성화 확인

### Step 4: Instagram Graph API 제품 추가

1. App Dashboard → **"Add Product"**
2. **"Instagram Graph API"** → **"Set up"** 클릭
3. **"Instagram API with Instagram Login"** → **"Settings"**:
   - Instagram 계정 연결

### Step 5: Access Token 발급

**Threads Token:**

1. App Dashboard → **"Threads API"** → **"Generate token"**
2. Instagram 계정 선택 → 권한 동의
3. 생성된 토큰 복사 → `THREADS_ACCESS_TOKEN`
4. **User ID 확인**:
   ```bash
   curl "https://graph.threads.net/v1.0/me?fields=id,username&access_token=<THREADS_ACCESS_TOKEN>"
   ```
   → 응답의 `id` 값 = `THREADS_USER_ID`

**Instagram Token:**

1. Meta Graph API Explorer: https://developers.facebook.com/tools/explorer/
2. App 선택 → **"Get User Access Token"** → permissions:
   - `instagram_basic`
   - `instagram_content_publish`
3. **"Generate Access Token"** 클릭 → 로그인 → 동의
4. **User ID 확인**:
   ```bash
   curl "https://graph.instagram.com/v22.0/me?fields=id,username&access_token=<INSTAGRAM_ACCESS_TOKEN>"
   ```
   → 응답의 `id` 값 = `INSTAGRAM_USER_ID`

**장기 토큰 교환 (60일 유효):**

단기 토큰(1시간)을 장기 토큰으로 교환:
```bash
curl "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=<APP_SECRET>&access_token=<SHORT_LIVED_TOKEN>"
```
→ 응답의 `access_token`이 60일 유효 장기 토큰

### Step 6: Railway 환경변수 등록

**Threads:**

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `THREADS_USER_ID` | `1234567890` | Threads 계정 ID |
| `THREADS_ACCESS_TOKEN` | `발급받은 토큰` | Graph API 토큰 |
| `SOCIAL_PLATFORM_THREADS_ENABLED` | `true` | 플랫폼 활성화 |

**Instagram:**

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `INSTAGRAM_USER_ID` | `1234567890` | Instagram 계정 ID |
| `INSTAGRAM_ACCESS_TOKEN` | `발급받은 토큰` | Graph API 토큰 |
| `SOCIAL_PLATFORM_INSTAGRAM_ENABLED` | `true` | 플랫폼 활성화 |

```bash
# Threads 3개 + Instagram 3개 = 총 6개 변수
for VAR_PAIR in \
  "THREADS_USER_ID:유저ID" \
  "THREADS_ACCESS_TOKEN:토큰값" \
  "SOCIAL_PLATFORM_THREADS_ENABLED:true" \
  "INSTAGRAM_USER_ID:유저ID" \
  "INSTAGRAM_ACCESS_TOKEN:토큰값" \
  "SOCIAL_PLATFORM_INSTAGRAM_ENABLED:true"; do
  NAME="${VAR_PAIR%%:*}"
  VALUE="${VAR_PAIR#*:}"
  curl -s -X POST https://backboard.railway.app/graphql/v2 \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
    -d "{\"query\":\"mutation{variableUpsert(input:{projectId:\\\"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\\\",environmentId:\\\"92d7e229-1071-4b32-a12c-8336ef7be7d5\\\",serviceId:\\\"2ee51089\\\",name:\\\"$NAME\\\",value:\\\"$VALUE\\\"})}\"}"
done
```

### 주의사항

- **Instagram은 이미지 필수** — public URL 이미지가 없는 포스트는 자동 스킵됩니다
- Threads는 텍스트 전용 포스트도 가능 (이미지 있으면 IMAGE 모드)
- Threads 500자 제한 / Instagram 캡션 2200자 제한
- Meta 토큰도 **60일 후 만료** → 갱신 필요
- Meta 앱 심사 통과 전에는 **테스트 사용자만** API 사용 가능 → 본인 계정을 테스트 사용자로 추가할 것
  - App Dashboard → **"Roles"** → **"Test Users"** → 본인 Instagram 계정 추가

---

## 5. Product Hunt Upcoming (20분)

> 난이도: 쉬움 | 비용: 무료 | API 키 불필요 (수동 등록)

Product Hunt에는 API 연동이 아니라 수동으로 "Upcoming" 페이지를 등록합니다.

### Step 1: Product Hunt 계정 생성

1. https://www.producthunt.com/ 접속 → **"Sign up"**
2. X(Twitter) 또는 이메일로 가입

### Step 2: Upcoming 페이지 등록

1. 로그인 후 https://www.producthunt.com/posts/new 접속
2. 또는 우측 상단 **"+"** → **"Post a product"**
3. 제품 정보:
   - **Name**: `WeWantPeace`
   - **Tagline**: `Real-time global conflict severity tracker` (60자 이내)
   - **Description**:
     ```
     WeWantPeace monitors 50+ global conflicts in real-time, providing
     AI-powered severity scores, daily trend analysis, and spike alerts.
     Track the world's conflicts on an interactive map with bilingual
     (EN/KO) analysis.
     ```
   - **Website**: `https://www.wewantpeace.live`
   - **Topics**: `Artificial Intelligence`, `News`, `Data Visualization`, `Social Impact`
   - **Thumbnail**: WeWantPeace 로고 또는 지도 스크린샷

### Step 3: Launch 설정

1. **"Ship"** 으로 Upcoming 페이지 생성 (아직 정식 Launch가 아님)
2. Upcoming 페이지가 생기면 구독자 모집 시작
3. 정식 Launch 날짜를 정해서 예약 가능

### Step 4: Launch Day 준비 (추후)

- Launch 전 최소 100명 이상 Upcoming 구독자 목표
- Launch Day에 맞춰 소셜 미디어 전체 채널에 동시 공지
- Hunter (다른 사람이 제품을 소개해주는 것)를 구하면 노출량 증가

---

## 6. Reddit 카르마 빌딩 전략 (장기)

> 난이도: 높음 (시간 투자 필요) | 비용: 무료 | API 연동: 추후

Reddit은 **즉시 자동 포스팅이 불가능**합니다. 신규 계정의 홍보성 포스트는 즉시 삭제/벤 당합니다.

### Phase 1: 계정 카르마 빌딩 (2-4주)

1. https://www.reddit.com/ → 계정 생성 (username: `wewantpeace_live` 등)
2. 타겟 서브레딧에서 **댓글 활동**으로 카르마 축적:
   - r/worldnews — 분쟁 관련 뉴스 기사에 분석적 댓글
   - r/geopolitics — 심층 분석 댓글
   - r/dataisbeautiful — 데이터 시각화 관련 댓글
   - r/MapPorn — 지도 기반 비주얼 관련 댓글
   - r/InternetIsBeautiful — 유용한 웹사이트 공유 (추후 포스팅 대상)
3. **최소 100 comment karma** 달성 목표
4. 홍보성 댓글 절대 금지 — 순수한 참여만

### Phase 2: 첫 포스트 (카르마 100+ 후)

1. **r/InternetIsBeautiful** — 가장 적합한 서브레딧
   - 제목: `I built a real-time global conflict severity tracker with AI analysis`
   - 규칙: 자기 프로젝트 포스팅 허용 (단 스팸 아닌 것)
2. **r/dataisbeautiful** — `[OC]` 태그로 데이터 시각화 포스트
3. **r/SideProject** — 사이드 프로젝트 공유 전용

### Phase 3: API 자동화 (추후)

- Reddit API로 자동 포스팅은 계정이 충분히 성숙한 후에 검토
- 현재 코드에 Reddit 어댑터는 없으므로 별도 개발 필요

---

## 7. GitHub Awesome Lists PR 제출 (30분)

> 난이도: 쉬움 | 비용: 무료 | 효과: 지속적 유입

### 타겟 Awesome Lists

| Repository | 추가 위치 | 우리 카테고리 |
|-----------|----------|-------------|
| `sindresorhus/awesome` | 메인 Awesome 리스트 | 신청 기준 높음 (나중에) |
| `topics/awesome-nextjs` | Next.js Projects | Web Applications |
| `analysis-tools-dev/static-analysis` | - | 해당 없음 |
| `vinta/awesome-python` | Data Analysis / Web | Web Frameworks (FastAPI) |
| `sdmg15/Best-websites-a-programmer-should-visit` | - | When you get bored |
| `bradtraversy/design-resources-for-developers` | - | UI/Maps |

**가장 효과적인 타겟:**

1. **`awesome-selfhosted/awesome-selfhosted`** — "Analytics / Monitoring" 카테고리
2. **`awesome-open-source`** 관련 리스트
3. **OSINT (Open Source Intelligence)** 관련 리스트

### PR 제출 방법

1. 타겟 리포지토리 Fork
2. README.md에 WeWantPeace 항목 추가 (알파벳순):
   ```markdown
   - [WeWantPeace](https://www.wewantpeace.live) - Real-time global conflict severity tracker with AI-powered analysis and interactive map. `Python` `Next.js`
   ```
3. PR 생성:
   - **Title**: `Add WeWantPeace - Real-time conflict tracker`
   - **Body**: 프로젝트 설명 + 스크린샷 + 왜 이 리스트에 적합한지
4. 각 리스트의 CONTRIBUTING.md 규칙을 반드시 따를 것

---

## 환경변수 전체 요약

아래는 모든 플랫폼의 Railway worker 서비스 환경변수 총 목록입니다.

### 현재 코드에 구현된 변수명 (정확한 변수명)

```bash
# === Kill Switches (config.py) ===
SOCIAL_AUTOGEN_ENABLED=true           # 콘텐츠 자동 생성 ON/OFF
SOCIAL_AUTOPUBLISH_LOW_ENABLED=false  # low-risk 자동 발행 (14일 후 검토)
SPIKE_SOCIAL_SEVERITY_MIN=60          # 스파이크 알림 최소 severity

# === 플랫폼별 활성화 ===
SOCIAL_PLATFORM_X_ENABLED=true                    # 기본값 true
SOCIAL_PLATFORM_THREADS_ENABLED=false              # 기본값 false
SOCIAL_PLATFORM_INSTAGRAM_ENABLED=false            # 기본값 false
SOCIAL_PLATFORM_LINKEDIN_ENABLED=false             # 기본값 false
SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED=false     # 기본값 false

# === X (Twitter) — x_adapter.py ===
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_SECRET=

# === Threads — threads_adapter.py ===
THREADS_USER_ID=
THREADS_ACCESS_TOKEN=

# === Instagram — instagram_adapter.py ===
INSTAGRAM_USER_ID=
INSTAGRAM_ACCESS_TOKEN=

# === LinkedIn — linkedin_adapter.py ===
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_ORG_ID=

# === Telegram Channel — telegram_channel_adapter.py ===
TELEGRAM_BROADCAST_BOT_TOKEN=
TELEGRAM_BROADCAST_CHANNEL_ID=
```

### 우선순위별 세팅 순서

| 순서 | 플랫폼 | 소요 시간 | 환경변수 수 | 난이도 |
|------|--------|----------|------------|--------|
| 1 | Telegram 채널 | 5분 | 3개 | 쉬움 |
| 2 | X (Twitter) | 30분 | 5개 | 보통 |
| 3 | LinkedIn | 15분 | 3개 | 보통 |
| 4 | Threads | 30분 | 3개 | 높음 |
| 5 | Instagram | (Threads와 동시) | 3개 | 높음 |
| 6 | Product Hunt | 20분 | 0개 | 쉬움 |
| 7 | Reddit | 2-4주 | 0개 | 높음 |
| 8 | GitHub Awesome Lists | 30분 | 0개 | 쉬움 |

---

## 토큰 갱신 리마인더

다음 토큰들은 만료 기한이 있으므로 달력에 리마인더를 설정하세요:

| 플랫폼 | 유효 기간 | 갱신 방법 |
|--------|----------|----------|
| LinkedIn Access Token | 60일 | OAuth2 refresh token 또는 재발급 |
| Threads Access Token | 60일 | Graph API refresh endpoint |
| Instagram Access Token | 60일 | `ig_refresh_token` grant type |
| X (Twitter) | 만료 없음 | Access Token 재발급 필요 시 Developer Portal |
| Telegram Bot Token | 만료 없음 | BotFather에서 `/revoke` 후 재발급 |

**갱신 자동화**: 추후 worker에 토큰 갱신 로직을 추가할 수 있습니다. 현재는 수동 갱신 필요.
