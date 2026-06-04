# SNS 자동 업로드 시스템 (X/Threads/Instagram)

## 상태: 대기 (앱인토스 반려사유 수정 후 착수)

## 개요
WeWantPeace의 주요 이슈를 X(Twitter), Threads, Instagram에 자동 포스팅하는 시스템 구현.

## 요구사항 (TBD)
- 어떤 이벤트를 포스팅할지 기준 (severity? spike?)
- 포스팅 주기/빈도
- 이미지 포함 여부 (OG 이미지 재활용?)
- 계정 정보 (X/Threads/Instagram API 키)
- 해시태그/멘션 전략

## 기술 스택 (예상)
- X API v2 (tweepy 또는 직접 호출)
- Threads API (Meta Graph API)
- Instagram Graph API (Meta)
- Celery worker 또는 cron job으로 스케줄링

## 다음 단계
- 상세 요구사항 논의 후 플랜 작성
