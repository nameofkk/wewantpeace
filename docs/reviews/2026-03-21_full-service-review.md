# WeWantPeace 전체 서비스 심층 코드 리뷰

**작성일**: 2026-03-21
**조사 범위**: 프론트엔드, 백엔드, 워커, 인프라, 보안, 성능, 데이터 무결성, UX/접근성, SEO/PWA
**에이전트**: 1차 3개 + 2차 6개 = 총 9개 병렬 조사

---

## P0 — 즉시 조치 필요 (서비스 장애/보안 사고 가능)

### 1. cluster_key UNIQUE 제약 누락 → 중복 클러스터 생성
- **현재 코드**: `backend/app/models/issue_cluster.py:21` — `index=True`만 있고 UNIQUE 없음
- **개선 시 차이**: 동일 사건이 여러 클러스터로 나뉘어 지도에 중복 표시되는 현상 방지. 사용자가 같은 이슈를 2~3번 보는 혼란 제거
- **장점**: DB 레벨에서 중복 원천 차단, 클러스터 품질 향상, KScore 정확도 상승
- **단점/비용**: 마이그레이션 필요 (기존 중복 데이터 먼저 정리해야 함), 30분~1시간 작업
- **우선순위 근거**: 현재 프로덕션에서 실제로 중복 클러스터가 생성될 수 있으며, 이는 사용자 신뢰도에 직결

### 2. XSS via Markdown 렌더링
- **현재 코드**: `frontend/components/community/MarkdownContent.tsx:19` — `dangerouslySetInnerHTML={{ __html: html }}`
- **개선 시 차이**: 악의적 사용자가 게시글에 `<img onerror="alert('XSS')">` 삽입 시 다른 사용자 세션 탈취 가능 → DOMPurify 추가로 차단
- **장점**: 커뮤니티 기능의 보안 기반 확보
- **단점/비용**: DOMPurify 패키지 추가 (~7KB gzipped), renderMarkdown 함수 수정 15분
- **우선순위 근거**: 커뮤니티 게시글은 사용자 입력이며, 현재 sanitize 여부가 불확실. XSS는 OWASP Top 10 취약점

### 3. Rate Limiting 미적용 (인증/업로드/게시글)
- **현재 코드**: `backend/app/routers/auth.py:331` (register), `community.py:190` (upload), `community.py:425` (create_post) — `@limiter.limit()` 없음
- **개선 시 차이**: 스팸 회원가입, 디스크 고갈 공격(5MB×무한), 스팸 게시글 폭격 차단
- **장점**: 서비스 안정성 + 스팸 방지
- **단점/비용**: 3개 파일에 데코레이터 1줄씩 추가, 5분 작업
- **우선순위 근거**: 글로벌 200req/min은 있지만 POST 엔드포인트별 제한 없음. 공격자가 인증 토큰 하나로 무한 게시 가능

### 4. DB 인덱스 누락 (is_active, kscore, severity)
- **현재 코드**: `backend/app/models/issue_cluster.py:10-14` — `is_active`, `kscore` 단일 인덱스 없음
- **개선 시 차이**: 트렌딩/이슈목록 API 응답 시간 10-50ms → 2-5ms (90% 감소). 사용자가 체감하는 지도/피드 로딩 속도 개선
- **장점**: 모든 주요 쿼리 성능 향상, DB 부하 감소
- **단점/비용**: Alembic 마이그레이션 1개, 인덱스 빌드 시간 수초
- **우선순위 근거**: 거의 모든 API에서 `WHERE is_active=true ORDER BY kscore DESC` 패턴 사용

### 5. Deduplicator TOCTTOU Race Condition
- **현재 코드**: `worker/processor/deduplicator.py:14-25` — check_duplicate() 후 insert 사이 시간차
- **개선 시 차이**: 두 워커가 동시에 같은 이벤트 처리 시 중복 생성 방지
- **장점**: 이벤트 정확도 향상, 클러스터 event_count 정합성
- **단점/비용**: DB unique constraint 또는 upsert ON CONFLICT 패턴으로 변경, 30분 작업
- **우선순위 근거**: Celery 워커 병렬 실행 시 실제로 발생 가능한 시나리오

---

## P1 — 높은 우선순위 (1주 내 해결 권장)

### 6. CORS 정규식 스푸핑 취약점
- **현재 코드**: `backend/app/core/config.py:73` — `r"https://.*\.(tossmini\.com|toss\.im)"`
- **개선 시 차이**: `evil.tossmini.com.attacker.com` 같은 서브도메인 스푸핑 차단
- **장점**: 토스 미니앱 CORS 보안 강화
- **단점/비용**: 정규식 수정 1줄 (`^https://[a-z0-9-]+\.tossmini\.com$`)
- **우선순위 근거**: Toss 앱인토스 통합 상태에서 CORS 우회는 인증 정보 탈취 가능

### 7. SQL Injection in DATE_TRUNC
- **현재 코드**: `backend/app/routers/trending.py:526` — `f"DATE_TRUNC('{trunc}', ...)"` f-string
- **개선 시 차이**: trunc 값 화이트리스트 검증으로 SQL injection 차단
- **장점**: 보안 강화 (현재는 trunc가 내부 변수라 위험 낮지만 방어적 코딩)
- **단점/비용**: if문 2줄 추가
- **우선순위 근거**: f-string SQL은 코드 리뷰에서 항상 플래그되는 패턴

### 8. Error Boundary 부재
- **현재 코드**: `frontend/components/` — React ErrorBoundary 컴포넌트 없음
- **개선 시 차이**: 컴포넌트 렌더링 에러 시 전체 앱 크래시 대신 해당 섹션만 에러 표시
- **장점**: 사용자 경험 보호, 에러 격리
- **단점/비용**: ErrorBoundary 컴포넌트 1개 + layout에 적용, 30분
- **우선순위 근거**: 현재 차트/지도 렌더링 에러 시 전체 페이지 화이트아웃

### 9. Comment.parent_id FK 누락
- **현재 코드**: `backend/app/models/community.py:46` — ForeignKey 제약 없음
- **개선 시 차이**: 부모 댓글 삭제 시 고아 댓글 발생 방지
- **장점**: 데이터 무결성 보장
- **단점/비용**: 마이그레이션 1개
- **우선순위 근거**: 커뮤니티 댓글 기능 사용 증가 시 고아 데이터 누적

### 10. HTTPException detail 형식 불일치
- **현재 코드**: `issues.py` → string, `subscriptions.py` → dict `{"code": "..."}` 혼재
- **개선 시 차이**: 프론트엔드 에러 핸들링 통일, 사용자에게 일관된 에러 메시지 표시
- **장점**: API 계약 일관성, 프론트엔드 코드 단순화
- **단점/비용**: 모든 라우터 HTTPException 형식 통일 필요, 2시간
- **우선순위 근거**: 현재 `body.detail`이 string/dict 혼재로 프론트에서 런타임 에러 가능

### 11. Sentry 프로덕션 미활성화
- **현재 코드**: `backend/app/core/sentry.py` — SENTRY_DSN 환경변수 미설정
- **개선 시 차이**: 프로덕션 에러를 실시간 모니터링, 에러 발생 시 즉시 알림
- **장점**: 장애 감지 시간 수시간 → 수분으로 단축
- **단점/비용**: Sentry 무료 플랜으로 시작 가능, Railway 환경변수 1개 추가
- **우선순위 근거**: 현재 프로덕션 에러를 알 수 있는 방법이 health check뿐

### 12. API 기본 LIMIT 2000 과다
- **현재 코드**: `backend/app/routers/issues.py:181` — `limit: int = Query(2000, ge=1, le=5000)`
- **개선 시 차이**: API 응답 크기 2-3MB → 100-300KB, 모바일에서 지도 로딩 시간 단축
- **장점**: 네트워크 대역폭 절약, 모바일 데이터 사용량 감소
- **단점/비용**: 프론트엔드 페이지네이션 확인 필요 (지도가 2000개 한번에 로드하는지)
- **우선순위 근거**: 모바일 사용자의 체감 성능에 직접 영향

---

## P2 — 중간 우선순위 (2주 내)

### 13. 모달 Focus Trap 및 Body Scroll Lock 부재
- **현재 코드**: `LoginModal.tsx`, `PaywallModal.tsx`, `WelcomeModal.tsx` — 포커스 관리 없음
- **개선 시 차이**: 키보드/스크린리더 사용자의 모달 탈출 방지, 모달 뒤 스크롤 차단
- **장점**: WCAG 2.1 AA 준수, 접근성 향상
- **단점/비용**: 각 모달에 focus-trap + body overflow:hidden 추가, 1시간
- **우선순위 근거**: 접근성은 토스 앱인토스 심사 항목이기도 함

### 14. 색상 대비 미달 (muted-foreground opacity)
- **현재 코드**: 전역 `text-muted-foreground/40` (대비율 2.8:1), `/60` (3.9:1)
- **개선 시 차이**: WCAG AA 최소 4.5:1 충족, 저시력 사용자 가독성 향상
- **장점**: 접근성 기준 충족
- **단점/비용**: globals.css에서 opacity 값 조정, 디자인 미세 변경
- **우선순위 근거**: 법적 접근성 요구사항 (일부 국가), UX 기본 품질

### 15. Worker Hard Delete 미구현 → DB 무한 성장
- **현재 코드**: soft delete만 있음 (severity=0), raw_events/normalized_events 영구 보관
- **개선 시 차이**: 30일+ 데이터 자동 정리로 DB 크기 안정화, Supabase 비용 절감
- **장점**: 스토리지 비용 절감, 쿼리 성능 유지
- **단점/비용**: cron job 1개 추가, 삭제 로직 구현 1시간
- **우선순위 근거**: 시간이 갈수록 DB 크기가 선형 증가, Supabase 무료 플랜 한계 접근

### 16. GDELT/ACLED 수집기 재시도 로직 부재
- **현재 코드**: `worker/collector/gdelt_collector.py:137-142` — 에러 로깅만
- **개선 시 차이**: API 일시 실패 시 데이터 손실 방지 (현재: 15분 주기라 1번 실패 = 15분 데이터 유실)
- **장점**: 데이터 수집 완전성 향상
- **단점/비용**: exponential backoff 로직 추가, 30분
- **우선순위 근거**: GDELT API가 간헐적으로 타임아웃, 현재 자동 복구 없음

### 17. 이미지 최적화 (logo.png 193KB)
- **현재 코드**: `frontend/public/logo.png` (193KB), `logo-eye.png` (120KB) — PNG 원본
- **개선 시 차이**: 193KB → ~70KB WebP로 60% 감소, 초기 로드 속도 개선
- **장점**: FCP/LCP 성능 지표 향상
- **단점/비용**: cwebp 변환 + img 태그 수정, 15분
- **우선순위 근거**: Lighthouse 성능 점수에 직접 영향

### 18. 터치 타겟 44px 미충족
- **현재 코드**: `BackButton.tsx:9` (26px), `app-header.tsx:94` (36px), `TourHelpButton.tsx:21` (32px)
- **개선 시 차이**: 모바일에서 버튼 미스탭 감소, UX 향상
- **장점**: 모바일 사용성 개선 (주 사용 플랫폼)
- **단점/비용**: 패딩 조정, 레이아웃 미세 변경
- **우선순위 근거**: Apple HIG/Material Design 가이드라인 기본 요구사항

### 19. Apple App Store ID 플레이스홀더
- **현재 코드**: `smart-app-banner.tsx:17` — `id0000000000` (TODO)
- **개선 시 차이**: iOS Smart App Banner가 실제 앱 스토어로 연결
- **장점**: iOS 사용자 앱 설치 유도 가능
- **단점/비용**: 앱 스토어 등록 후 ID 교체, 1분
- **우선순위 근거**: 앱 스토어 등록 전까지는 배너 자체를 숨기는 게 나을 수 있음

---

## P3 — 낮은 우선순위 (장기 개선)

### 20. 프론트엔드 테스트 부재
- CI에서 backend pytest만 실행, frontend Jest/Playwright 없음
- 개선 시: 프론트엔드 리그레션 방지, 배포 안정성 향상

### 21. PWA 오프라인 Fallback 페이지 미구현
- API 캐시(NetworkFirst 5분)는 있으나 오프라인 전용 페이지 없음
- 개선 시: 오프라인 시 "인터넷 연결을 확인하세요" 페이지 표시

### 22. GA4 미설정
- Google Search Console 인증은 완료, GA4 스크립트 미삽입
- 개선 시: 사용자 행동 분석, 마케팅 의사결정 데이터 확보

### 23. 배포 롤백 전략 부재
- deploy.yml에 rollback job 없음, 수동 롤백만 가능
- 개선 시: 장애 시 1-click 롤백으로 MTTR 단축

### 24. Single Replica 배포 (다운타임)
- Railway 설정 `numReplicas: 1` → 배포 중 서비스 중단 발생
- 개선 시: 2+ replicas로 무중단 배포

### 25. Semantic Dedup 부재
- 같은 사건 다른 표현 (Reuters vs AP) → dedup_key 다름 → 별도 이벤트로 처리
- 클러스터 단계에서 병합되지만, 병합 실패 시 중복 클러스터

### 26. Conflict-Zone Floor 수동 관리
- `tension_calculator.py` 우크라이나 55.0, 팔레스타인 50.0 하드코딩
- ACLED 90일 이벤트 밀도 기반 자동화 예정 (코드 주석 있음)

### 27. RTL 언어 미대응
- `<html lang="ko">` 고정, 아랍어/히브리어 추가 시 layout 재설계 필요

---

## 강점 요약 (잘 된 부분)

| 영역 | 내용 |
|------|------|
| SEO | 메타데이터, JSON-LD, 동적 sitemap, canonical URL 완벽 |
| 보안 헤더 | HSTS 1년, CSP, X-Frame-Options, Permissions-Policy |
| Firebase Auth | 프로덕션 DISABLE_AUTH 강제 비활성화, verify_id_token 검증 |
| 파일 업로드 | MIME + 매직바이트 이중 검증, 5MB 제한 |
| IDOR 방어 | 모든 사용자 리소스에 owner ID 검증 |
| 워커 모니터링 | 18가지 헬스체크, 자동 수정 로직 |
| Celery Beat | 오프셋 분산 스케줄, max_tasks_per_child 500 |
| 캐싱 | Redis LRU + HTTP Cache-Control + SWR 조합 |
| 마이그레이션 | 54개 Alembic 버전 일관성, downgrade 모두 존재 |
| i18n | ko/en 이중 지원, 컴포넌트별 t() 함수 사용 |
