# WeWantPeace 프로젝트 규칙

## 자동 Git Push
**이 프로젝트에서 파일을 수정할 때마다 작업 완료 후 반드시 자동으로 실행:**
```bash
cd /home/krshin7/Projects/wewantpeace
git add .
git commit -m "작업 내용 한 줄 요약"
git push
```
- remote: `https://github.com/nameofkk/wewantpeace`
- branch: `main`
- 인증: remote URL에 토큰 포함되어 있음 (별도 설정 불필요)
- 커밋 메시지: 한국어 OK, 작업 내용 한 줄 요약

## 배포 정보
- Domain: `https://www.wewantpeace.live`
- Backend: `https://backend-production-3af7.up.railway.app`
- Frontend: `https://frontend-production-f0dd.up.railway.app` (커스텀 도메인: `www.wewantpeace.live`)
- Railway project: `proud-purpose` (ID: `8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed`)
- DB: **Railway Postgres** (같은 Railway 프로젝트의 `Postgres` 서비스, 내부망 `postgres.railway.internal` 전용 — 외부 공개 주소 없음). Redis 도 Railway.
  - Supabase `smxitufpgfuzepldglfo` 는 이관 전 옛 DB (INACTIVE) — 조회하지 말 것
  - 운영 데이터 확인: `railway logs -s worker` / `railway logs -s backend`, 또는 `railway ssh -s Postgres` (22번 포트가 열린 환경에서만)
- Google Play 업로드 키: `mobile/android/app/wewantpeace-release.keystore` (RSA). `signing-key.jks`(EC)는 Play 가 받지 않는다

## railway.json 주의사항
- `railway.json`은 **backend** 서비스용으로 유지 (`Dockerfile.backend`)
- worker 배포 시: 임시로 `Dockerfile.worker`로 변경 후 배포, 즉시 복원
- frontend 배포 시: 임시로 `Dockerfile.frontend`로 변경 후 배포, 즉시 복원

## worker 레플리카 주의사항 (railway-worker.json)
- `railway-worker.json`의 `deploy.numReplicas`는 반드시 `1`로 고정
- 이유: `startCommand`가 `celery worker --beat`로 beat 스케줄러를 워커에 붙여서 돌림. 레플리카를 2 이상으로 올리면 beat가 복제돼 예약 태스크(`sync_dodo_subscriptions` 등)가 중복 실행됨
- beat를 별도 서비스로 분리하기 전까지는 절대 증설 금지 (로컬 `infra/docker-compose.yml`은 `worker-beat`로 이미 분리돼 있음, 프로덕션도 동일하게 분리하면 그때 해제 가능)

## i18n 규칙
- UI 텍스트 수정 시 한국어(ko) + 영어(en) 동시 수정
- `frontend/lib/i18n.ts` — ko/en 블록 모두 업데이트

## normalizer.py 수정 시
- 수정 후 반드시 `python3 scripts/reprocess_topics.py` 실행
