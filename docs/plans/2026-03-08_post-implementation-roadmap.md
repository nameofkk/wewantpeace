# 구현 후 로드맵: 검증 → B-Launch → 성장 루프

> 작성: 2026-03-08 | 구현 커밋: 128feb6

## 현재 상태
- KScore Phase 1 + Conflict Floor + IA 보정 + 200개국 확대 구현 완료
- 24개 파일, 705줄 추가 / 71줄 삭제
- reprocess 완료 (프로덕션 DB)
- **검증 Phase 1 완료 (2026-03-08)**:
  - DB 마이그레이션 0037 적용 확인
  - CONFLICT_FLOOR 17개국 전부 정상 (10개국 정확히 floor 작동)
  - 200개국 확대: 129개국 활성 (기존 64 → 129)
  - IA 보정: KP avg_sev=72.33 (보정 효과 확인)
  - KScore 개인화: KR/US/JP 관점별 순위 차이 직관적으로 정확
  - 참고: MM/CF/ML/NE 등 아프리카·동남아는 event_score=0 → RSS 소스 확대 필요

---

## 1단계: 검증 (1주)

### KScore 검증
- [ ] KR 기준: 북한 미사일 > 브라질 시위 확인
- [ ] 최소 50개 실제 클러스터 수동 검토
- [ ] 직관과 맞지 않는 팩터 튜닝 (이란 핵/일본 지진 등)
- [ ] 10개 기준국별 상위 10개 이슈 KScore 비교표 생성

### Tension Index 검증
- [ ] UA Conflict Floor ≥55 유지 확인 (새벽 시간대)
- [ ] KP/CN 이벤트 severity 보정 합리성 확인
- [ ] Spillover 반영 검증 (인접국 긴장도 전파)
- [ ] 30일 소급 분석: 오탐/누락 카운트

### 부하 테스트
- [ ] 120×120 팩터 JSON 모바일 파싱 시간 측정
- [ ] FCM 페이로드 4KB 제한 확인 (Spike Alert + "왜 중요한지")
- [ ] 200개국 동적 필터링 사이클 실행 시간 측정

---

## 2단계: B-Launch (검증 완료 후 2주)

### GitHub 공개 (wewantpeace-methodology)
- [ ] README.md (검증된 실제 수치로)
- [ ] METHODOLOGY.md
- [ ] DATA_DICTIONARY.md
- [ ] 4주 샘플 JSON
- [ ] CC BY-NC 4.0 라이센스

### 배포 순서
- Day 0: 저장소 공개
- Week 1: r/dataisbeautiful, r/datasets 포스팅
- Week 2: Show HN 포스팅

### 톤 가이드
- "방법론 + 데이터 + 피드백 요청" 프레이밍
- 서비스 링크는 README에만
- 포스트 본문에 제품 홍보 절대 금지

---

## 3단계: 성장 루프 (B-Launch 이후 지속)

### 자동 콘텐츠 엔진
- worker/social/ 기반 Daily/Spike/Weekly 카드
- X(Twitter), LinkedIn, 네이버 카페 자동 포스팅 파이프라인
- 위기 순간 자동 콘텐츠 생성 → 바이럴 트리거

### 공개 API
- Tension Index API 개발자 커뮤니티 타깃
- 블로거 위젯, 트레이딩 봇 연동 사례

### 구독 전환 최적화
- Spike Alert 3회 → Pro 전환 유도
- 7일 무료체험 전환율 측정
- Pro → Pro+ 업그레이드 트리거 분석

---

## 바이럴 무기: 케이스 스터디
- 과거 데이터 소급 분석으로 "X 사건을 N시간 전 탐지" 사례 구축
- B-Launch 콘텐츠의 핵심 자산
- World Monitor의 "스크린샷 바이럴" 대응 전략

## 최대 리스크
- 기술 아님 → 유저 부재
- 100명 유저 목표도 쉽지 않음
- 부정확한 데이터로 공개 시 신뢰 붕괴
