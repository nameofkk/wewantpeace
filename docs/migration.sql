-- =============================================================================
-- WeWantPeace — Combined Migration SQL
-- Generated from Alembic migrations 0001 through 0009
-- Final revision: 0009
--
-- This script is idempotent (safe to run multiple times).
-- Wrap everything in a single transaction.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- alembic_version 테이블 (Alembic 버전 추적)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- =============================================================================
-- 0001: initial_schema
-- =============================================================================

-- source_channels: Telegram 화이트리스트 + RSS 소스
CREATE TABLE IF NOT EXISTS source_channels (
    id              SERIAL PRIMARY KEY,
    channel_id      BIGINT,
    username        VARCHAR(128),
    display_name    VARCHAR(256)                             NOT NULL,
    tier            VARCHAR(1)                               NOT NULL,
    base_confidence FLOAT                                    NOT NULL DEFAULT 0.70,
    language        VARCHAR(8)                                        DEFAULT 'en',
    topics          TEXT[]                                   NOT NULL DEFAULT '{}',
    geo_focus       TEXT[]                                   NOT NULL DEFAULT '{}',
    source_type     VARCHAR(16)                              NOT NULL DEFAULT 'telegram',
    feed_url        TEXT,
    is_active       BOOLEAN                                  NOT NULL DEFAULT true,
    created_at      TIMESTAMP WITH TIME ZONE                 NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE                 NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_source_channels_tier CHECK (tier IN ('A','B','C','D')),
    CONSTRAINT uq_source_channels_channel_id UNIQUE (channel_id)
);

-- raw_events: 원본 수집 데이터
CREATE TABLE IF NOT EXISTS raw_events (
    id                UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    source_channel_id INT              REFERENCES source_channels(id) ON DELETE SET NULL,
    source_type       VARCHAR(16)      NOT NULL,
    external_id       VARCHAR(256)     NOT NULL,
    raw_text          TEXT             NOT NULL,
    raw_metadata      JSONB            NOT NULL DEFAULT '{}',
    lang              VARCHAR(8),
    collected_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    processed         BOOLEAN          NOT NULL DEFAULT false,
    CONSTRAINT uq_raw_events_source_external UNIQUE (source_type, external_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_events_processed
    ON raw_events (processed, collected_at);

CREATE INDEX IF NOT EXISTS idx_raw_events_source_type
    ON raw_events (source_type, collected_at);

-- normalized_events: 정규화된 이벤트
CREATE TABLE IF NOT EXISTS normalized_events (
    id               UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_event_id     UUID             REFERENCES raw_events(id) ON DELETE SET NULL,
    title            TEXT             NOT NULL,
    body             TEXT,
    topic            VARCHAR(32)      NOT NULL,
    entity_anchor    VARCHAR(256),
    lat              FLOAT,
    lon              FLOAT,
    geohash5         VARCHAR(8),
    country_code     VARCHAR(4),
    severity         SMALLINT         NOT NULL DEFAULT 0,
    source_tier      VARCHAR(1)       NOT NULL,
    confidence       FLOAT            NOT NULL DEFAULT 0.0,
    dedup_key        VARCHAR(64)      NOT NULL,
    is_duplicate     BOOLEAN          NOT NULL DEFAULT false,
    event_time       TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ne_geohash_topic
    ON normalized_events (geohash5, topic, event_time);

CREATE INDEX IF NOT EXISTS idx_ne_dedup
    ON normalized_events (dedup_key);

CREATE INDEX IF NOT EXISTS idx_ne_country
    ON normalized_events (country_code, event_time);

-- issue_clusters: 클러스터링된 이슈
CREATE TABLE IF NOT EXISTS issue_clusters (
    id                  UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_key         VARCHAR(512)     NOT NULL,
    geohash5            VARCHAR(8)       NOT NULL,
    topic               VARCHAR(32)      NOT NULL,
    entity_anchor       VARCHAR(256),
    country_code        VARCHAR(4),
    lat                 FLOAT,
    lon                 FLOAT,
    title               TEXT             NOT NULL,
    event_count         INT              NOT NULL DEFAULT 0,
    severity            SMALLINT         NOT NULL DEFAULT 0,
    confidence          FLOAT            NOT NULL DEFAULT 0.0,
    kscore              FLOAT            NOT NULL DEFAULT 0.0,
    is_spike            BOOLEAN          NOT NULL DEFAULT false,
    spike_at            TIMESTAMP WITH TIME ZONE,
    source_tiers        TEXT[]           NOT NULL DEFAULT '{}',
    independent_sources INT              NOT NULL DEFAULT 0,
    first_event_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    last_event_at       TIMESTAMP WITH TIME ZONE NOT NULL,
    window_start        TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end          TIMESTAMP WITH TIME ZONE NOT NULL,
    is_verified         BOOLEAN          NOT NULL DEFAULT false,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cluster_geo
    ON issue_clusters (geohash5, last_event_at);

CREATE INDEX IF NOT EXISTS idx_cluster_spike
    ON issue_clusters (is_spike, spike_at);

CREATE INDEX IF NOT EXISTS idx_cluster_country
    ON issue_clusters (country_code, last_event_at);

-- cluster_events: 클러스터 ↔ 이벤트 연결
CREATE TABLE IF NOT EXISTS cluster_events (
    cluster_id UUID NOT NULL REFERENCES issue_clusters(id) ON DELETE CASCADE,
    event_id   UUID NOT NULL REFERENCES normalized_events(id) ON DELETE CASCADE,
    PRIMARY KEY (cluster_id, event_id)
);

-- tension_index: 긴장도 지수 (TimescaleDB 하이퍼테이블)
CREATE TABLE IF NOT EXISTS tension_index (
    "time"          TIMESTAMP WITH TIME ZONE NOT NULL,
    country_code    VARCHAR(4)   NOT NULL,
    region_code     VARCHAR(16),
    raw_score       FLOAT        NOT NULL DEFAULT 0.0,
    tension_level   SMALLINT     NOT NULL DEFAULT 0,
    event_score     FLOAT                 DEFAULT 0.0,
    accel_score     FLOAT                 DEFAULT 0.0,
    spillover_score FLOAT                 DEFAULT 0.0,
    percentile_30d  FLOAT                 DEFAULT 0.0,
    PRIMARY KEY ("time", country_code)
);

CREATE INDEX IF NOT EXISTS idx_ti_country
    ON tension_index (country_code, "time");

-- TimescaleDB 하이퍼테이블 생성 (TimescaleDB 없으면 skip)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('tension_index', 'time', if_not_exists => TRUE);
    END IF;
END$$;

-- trending_keywords
CREATE TABLE IF NOT EXISTS trending_keywords (
    id            SERIAL PRIMARY KEY,
    keyword       VARCHAR(256)             NOT NULL,
    normalized_kw VARCHAR(256)             NOT NULL,
    kscore        FLOAT                    NOT NULL DEFAULT 0.0,
    topic         VARCHAR(32),
    country_codes TEXT[]                   NOT NULL DEFAULT '{}',
    cluster_ids   UUID[]                   NOT NULL DEFAULT '{}',
    scope         VARCHAR(64)              NOT NULL DEFAULT 'global',
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    valid_until   TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kw_scope_score
    ON trending_keywords (scope, kscore DESC, calculated_at);

-- users
CREATE TABLE IF NOT EXISTS users (
    id           UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(128)     NOT NULL UNIQUE,
    email        VARCHAR(256),
    plan         VARCHAR(16)      NOT NULL DEFAULT 'free',
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_active  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_users_plan CHECK (plan IN ('free','pro','pro_plus'))
);

-- user_areas
CREATE TABLE IF NOT EXISTS user_areas (
    id               SERIAL PRIMARY KEY,
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    area_type        VARCHAR(16)  NOT NULL DEFAULT 'country',
    country_code     VARCHAR(4),
    geojson          JSONB,
    label            VARCHAR(128),
    notify_verified  BOOLEAN      NOT NULL DEFAULT true,
    notify_fast      BOOLEAN      NOT NULL DEFAULT false,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_user_areas_type CHECK (area_type IN ('country','polygon','radius'))
);

CREATE INDEX IF NOT EXISTS idx_user_areas_user
    ON user_areas (user_id);

-- user_push_tokens
CREATE TABLE IF NOT EXISTS user_push_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fcm_token  VARCHAR(512) NOT NULL,
    platform   VARCHAR(16)  NOT NULL DEFAULT 'web',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_used  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_push_tokens UNIQUE (user_id, fcm_token)
);

-- user_preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id           UUID       PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    language          VARCHAR(8) NOT NULL DEFAULT 'ko',
    min_severity      SMALLINT   NOT NULL DEFAULT 35,
    topics            TEXT[]     NOT NULL DEFAULT '{conflict,terror,coup,sanctions,cyber,protest}',
    quiet_hours_start TIME,
    quiet_hours_end   TIME,
    timezone          VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul'
);

-- =============================================================================
-- 0002: add_title_ko
-- =============================================================================

ALTER TABLE issue_clusters
    ADD COLUMN IF NOT EXISTS title_ko VARCHAR;

-- =============================================================================
-- 0003: timescaledb_retention
-- =============================================================================

-- tension_index 90일 보존 정책 (TimescaleDB 있을 때만)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM add_retention_policy(
            'tension_index',
            INTERVAL '90 days',
            if_not_exists => true
        );
    END IF;
END$$;

-- 성능 개선 인덱스

CREATE INDEX IF NOT EXISTS idx_raw_events_collected_at
    ON raw_events (collected_at DESC)
    WHERE processed = false;

CREATE INDEX IF NOT EXISTS idx_normalized_events_event_time_country
    ON normalized_events (event_time DESC, country_code)
    WHERE is_duplicate = false;

CREATE INDEX IF NOT EXISTS idx_issue_clusters_last_event_at_severity
    ON issue_clusters (last_event_at DESC, severity)
    WHERE severity >= 30;

-- NormalizedEvent dedup_key 유니크 제약 (TOCTOU 완화)
CREATE UNIQUE INDEX IF NOT EXISTS idx_normalized_events_dedup_key_unique
    ON normalized_events (dedup_key)
    WHERE is_duplicate = false;

-- =============================================================================
-- 0004: user_expansion
-- =============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname           VARCHAR(30);
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name       VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio                VARCHAR(200);
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image_url  VARCHAR(512);
ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_year         SMALLINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS status             VARCHAR(16) NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN IF NOT EXISTS role               VARCHAR(16) NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN IF NOT EXISTS agreed_terms_at    TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS agreed_privacy_at  TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS marketing_agreed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_until    TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspend_reason     VARCHAR(200);

-- 유니크 인덱스 (nickname)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_users_nickname'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT uq_users_nickname UNIQUE (nickname);
    END IF;
END$$;

-- CHECK 제약
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_users_status'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_status
            CHECK (status IN ('active', 'suspended', 'deleted'));
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_users_role'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_role
            CHECK (role IN ('user', 'moderator', 'admin'));
    END IF;
END$$;

-- =============================================================================
-- 0005: community
-- =============================================================================

-- posts
CREATE TABLE IF NOT EXISTS posts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        REFERENCES users(id) ON DELETE SET NULL,
    cluster_id    UUID,
    title         VARCHAR(200) NOT NULL,
    content       TEXT         NOT NULL,
    post_type     VARCHAR(16)  NOT NULL DEFAULT 'discussion',
    status        VARCHAR(16)  NOT NULL DEFAULT 'active',
    view_count    INT          NOT NULL DEFAULT 0,
    comment_count INT          NOT NULL DEFAULT 0,
    like_count    INT          NOT NULL DEFAULT 0,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT ck_posts_type   CHECK (post_type IN ('discussion','question','analysis')),
    CONSTRAINT ck_posts_status CHECK (status IN ('active','hidden','deleted'))
);

CREATE INDEX IF NOT EXISTS ix_posts_user_id    ON posts (user_id);
CREATE INDEX IF NOT EXISTS ix_posts_cluster_id ON posts (cluster_id);
CREATE INDEX IF NOT EXISTS ix_posts_created_at ON posts (created_at);
CREATE INDEX IF NOT EXISTS ix_posts_post_type  ON posts (post_type);

-- comments
CREATE TABLE IF NOT EXISTS comments (
    id         UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id    UUID       NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id    UUID       REFERENCES users(id) ON DELETE SET NULL,
    parent_id  UUID,
    content    TEXT       NOT NULL,
    status     VARCHAR(16) NOT NULL DEFAULT 'active',
    like_count INT        NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT ck_comments_status CHECK (status IN ('active','hidden','deleted'))
);

CREATE INDEX IF NOT EXISTS ix_comments_post_id   ON comments (post_id);
CREATE INDEX IF NOT EXISTS ix_comments_user_id   ON comments (user_id);
CREATE INDEX IF NOT EXISTS ix_comments_parent_id ON comments (parent_id);

-- comment_reactions
CREATE TABLE IF NOT EXISTS comment_reactions (
    id            SERIAL PRIMARY KEY,
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    comment_id    UUID        NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    reaction_type VARCHAR(16) NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT uq_comment_reactions       UNIQUE (user_id, comment_id),
    CONSTRAINT ck_comment_reaction_type   CHECK (reaction_type IN ('like','dislike'))
);

-- post_reactions
CREATE TABLE IF NOT EXISTS post_reactions (
    id            SERIAL PRIMARY KEY,
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id       UUID        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    reaction_type VARCHAR(16) NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT uq_post_reactions      UNIQUE (user_id, post_id),
    CONSTRAINT ck_post_reaction_type  CHECK (reaction_type IN ('like','dislike'))
);

-- reports
CREATE TABLE IF NOT EXISTS reports (
    id          SERIAL PRIMARY KEY,
    reporter_id UUID        REFERENCES users(id) ON DELETE SET NULL,
    target_type VARCHAR(16) NOT NULL,
    target_id   VARCHAR(64) NOT NULL,
    reason      VARCHAR(200) NOT NULL,
    status      VARCHAR(16)  NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by UUID        REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT ck_reports_target_type CHECK (target_type IN ('post','comment','user')),
    CONSTRAINT ck_reports_status      CHECK (status IN ('pending','resolved','dismissed'))
);

CREATE INDEX IF NOT EXISTS ix_reports_status ON reports (status);

-- admin_logs
CREATE TABLE IF NOT EXISTS admin_logs (
    id          BIGSERIAL PRIMARY KEY,
    admin_id    UUID        REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(64) NOT NULL,
    target_type VARCHAR(32),
    target_id   VARCHAR(64),
    detail      JSONB,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_admin_logs_admin_id   ON admin_logs (admin_id);
CREATE INDEX IF NOT EXISTS ix_admin_logs_created_at ON admin_logs (created_at);

-- =============================================================================
-- 0006: subscriptions
-- =============================================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan             VARCHAR(16) NOT NULL,
    status           VARCHAR(16) NOT NULL DEFAULT 'active',
    billing_key      VARCHAR(200),
    customer_key     VARCHAR(64),
    amount           INT         NOT NULL DEFAULT 4900,
    currency         VARCHAR(4)  NOT NULL DEFAULT 'KRW',
    started_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    expires_at       TIMESTAMP WITH TIME ZONE,
    cancelled_at     TIMESTAMP WITH TIME ZONE,
    next_billing_at  TIMESTAMP WITH TIME ZONE,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT ck_subscriptions_status CHECK (status IN ('active','cancelled','expired','trial')),
    CONSTRAINT ck_subscriptions_plan   CHECK (plan IN ('pro','pro_plus'))
);

CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions (user_id);
CREATE INDEX IF NOT EXISTS ix_subscriptions_status  ON subscriptions (status);

CREATE TABLE IF NOT EXISTS payment_history (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id   UUID        REFERENCES subscriptions(id) ON DELETE SET NULL,
    amount            INT         NOT NULL,
    currency          VARCHAR(4)  NOT NULL DEFAULT 'KRW',
    status            VARCHAR(16) NOT NULL,
    pg_transaction_id VARCHAR(200),
    pg_response       JSONB,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT ck_payment_status CHECK (status IN ('success','failed','refunded'))
);

CREATE INDEX IF NOT EXISTS ix_payment_history_user_id ON payment_history (user_id);

-- =============================================================================
-- 0007: terms
-- =============================================================================

CREATE TABLE IF NOT EXISTS term_versions (
    id           SERIAL PRIMARY KEY,
    type         VARCHAR(16)  NOT NULL,
    version      VARCHAR(20)  NOT NULL,
    content      TEXT         NOT NULL,
    effective_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT ck_term_versions_type    CHECK (type IN ('terms','privacy')),
    CONSTRAINT uq_term_type_version     UNIQUE (type, version)
);

CREATE TABLE IF NOT EXISTS user_consents (
    id           SERIAL PRIMARY KEY,
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    term_type    VARCHAR(16) NOT NULL,
    term_version VARCHAR(20) NOT NULL,
    agreed_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    ip_address   VARCHAR(45),
    user_agent   VARCHAR(500)
);

CREATE INDEX IF NOT EXISTS ix_user_consents_user_id ON user_consents (user_id);

-- 초기 약관 데이터 (이미 존재하면 skip)
INSERT INTO term_versions (type, version, content, effective_at)
SELECT 'terms', '1.0',
$$제1조(목적)
이 약관은 WeWantPeace(이하 "회사")가 제공하는 서비스의 이용조건 및 절차, 회사와 이용자의 권리·의무 및 책임사항을 규정함을 목적으로 합니다.

제2조(정의)
① "서비스"란 회사가 제공하는 세계정세 알림·지도·커뮤니티 플랫폼을 말합니다.
② "회원"이란 본 약관에 동의하고 서비스를 이용하는 자를 말합니다.
③ "Pro 회원"이란 유료 구독을 통해 추가 기능을 이용하는 회원을 말합니다.
④ "콘텐츠"란 회원이 서비스 내에서 작성·게시한 게시물, 댓글 등을 말합니다.

제3조(서비스 제공 및 변경)
① 회사는 연중무휴 24시간 서비스를 제공합니다.
② 회사는 서비스 내용을 변경할 경우 최소 7일 전에 공지합니다.
③ 정기점검 등 기술상 이유로 서비스가 일시 중단될 수 있습니다.

제4조(이용계약 체결)
① 서비스 이용은 만 14세 이상만 가능합니다.
② 이용자는 회원가입 시 본 약관 및 개인정보처리방침에 동의해야 합니다.
③ 허위 정보 제공 시 이용이 제한될 수 있습니다.

제5조(회원 의무 및 금지행위)
회원은 다음 행위를 해서는 안 됩니다:
① 타인의 계정 도용 또는 허위 정보 등록
② 허위 뉴스, 선동적 콘텐츠 게시
③ 스팸, 광고성 게시물 반복 게시
④ 저작권 침해 콘텐츠 게시
⑤ 혐오 발언, 명예훼손 발언
⑥ 서비스 해킹 또는 비정상적 접근 시도
⑦ 다중 계정 생성 및 어뷰징

제6조(서비스 제공자 의무)
① 회사는 안정적인 서비스 제공을 위해 최선을 다합니다.
② 회사는 이용자의 개인정보를 개인정보처리방침에 따라 보호합니다.
③ 회원의 불만·피해 구제에 최선을 다합니다.

제7조(유료서비스 및 결제)
① Pro 구독: 월 4,900원 / Pro+ 구독: 월 9,900원 (VAT 포함)
② 결제는 토스페이먼츠를 통한 정기결제 방식으로 진행됩니다.
③ 구독 취소 시 현재 기간 만료까지 서비스 이용 가능합니다.
④ 서비스 이용 후 7일 이내에는 전액 환불이 가능합니다.
⑤ 환불 요청: krshin7@naver.com

제8조(책임제한)
① 천재지변, 불가항력에 의한 서비스 장애는 회사 책임에서 제외됩니다.
② Firebase, Toss Payments 등 제3자 서비스 장애는 회사 책임에서 제외됩니다.
③ 이용자 귀책으로 발생한 손해는 회사가 책임지지 않습니다.

제9조(분쟁해결)
서비스 이용 관련 분쟁은 한국소비자원 또는 전자거래분쟁조정위원회를 통해 해결할 수 있습니다.

제10조(준거법 및 관할)
본 약관은 대한민국 법률을 준거법으로 하며, 분쟁 시 서울중앙지방법원을 전속 관할로 합니다.

부칙
본 약관은 2025년 1월 1일부터 시행합니다.$$,
'2025-01-01 00:00:00+00'::TIMESTAMPTZ
WHERE NOT EXISTS (
    SELECT 1 FROM term_versions WHERE type = 'terms' AND version = '1.0'
);

INSERT INTO term_versions (type, version, content, effective_at)
SELECT 'privacy', '1.0',
$$개인정보처리방침

WeWantPeace(이하 "회사")는 개인정보보호법, 정보통신망 이용촉진 및 정보보호 등에 관한 법률을 준수합니다.

1. 수집하는 개인정보 항목
[필수] 이메일 주소, 닉네임, 생년도, 소셜로그인 식별자(Google UID 등)
[선택] 프로필 사진, 자기소개(bio)
[자동] IP주소, 접속 로그, 쿠키, 서비스 이용 기록

2. 수집 목적 및 이용 목적
- 회원 가입 및 관리
- 서비스 제공 및 개인화
- 유료 서비스 결제 처리
- 불법 이용 방지 및 보안
- 서비스 개선을 위한 통계 분석

3. 보유 및 이용 기간
- 회원 탈퇴 시 즉시 파기 (닉네임 및 이메일 익명 처리)
- 단, 관련 법령에 따라 보관:
  * 계약/청약 철회 기록: 5년 (전자상거래법)
  * 소비자 불만 처리: 3년 (전자상거래법)
  * 부정 이용 방지: 1년

4. 개인정보 제3자 제공
- Firebase (Google Inc.): 인증 서비스 제공 목적
- Toss Payments (주식회사 토스페이먼츠): 결제 처리 목적
- 법령에 따른 수사기관 요청 시 제공 가능

5. 개인정보 처리 위탁
- 클라우드 인프라: Fly.io (서버 운영)
- 위탁 업무 외 개인정보 처리 금지 계약 체결

6. 이용자 권리 행사 방법
이용자는 언제든지 다음 권리를 행사할 수 있습니다:
- 개인정보 열람, 정정, 삭제 요청
- 개인정보 처리 정지 요청
- 요청 처리: 14일 이내
- 연락처: krshin7@naver.com

7. 자동 수집 장치 (쿠키)
- 세션 관리 및 서비스 이용 분석에 쿠키 사용
- 브라우저 설정으로 쿠키 거부 가능 (일부 서비스 제한 가능)

8. 개인정보 안전성 확보 조치
- 개인정보 전송 시 HTTPS(TLS) 암호화
- 접근 권한 최소화 (역할 기반 접근 제어)
- 비밀번호 해시화 저장
- 정기적 보안 점검

9. 개인정보 보호책임자
성명: WeWantPeace 개인정보 보호담당자
이메일: krshin7@naver.com
연락처: krshin7@naver.com

10. 고지의 의무
이 개인정보처리방침은 변경될 경우 서비스 내 공지사항 또는 이메일을 통해 사전 고지합니다.

시행일: 2025년 1월 1일$$,
'2025-01-01 00:00:00+00'::TIMESTAMPTZ
WHERE NOT EXISTS (
    SELECT 1 FROM term_versions WHERE type = 'privacy' AND version = '1.0'
);

-- =============================================================================
-- 0008: community_dislike_images
-- =============================================================================

ALTER TABLE posts ADD COLUMN IF NOT EXISTS dislike_count INT NOT NULL DEFAULT 0;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS images JSONB;

-- =============================================================================
-- 0009: user_preferences_kscore
-- =============================================================================

ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS min_kscore FLOAT NOT NULL DEFAULT 1.0;

-- =============================================================================
-- alembic_version: 최종 리비전 기록
-- =============================================================================

DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('0009');

COMMIT;
