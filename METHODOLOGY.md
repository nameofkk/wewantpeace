# WeWantPeace Methodology
> Version: 1.0 | Last updated: 2026-03-08
> "현재 버전"과 "계획 중인 변경"을 분리하여 기술

## 1. 데이터 소스 (58개 활성 채널)
- RSS 37+, Telegram 12, GDELT 1, ACLED 1, ReliefWeb 1
- 갱신: 5분(RSS/Telegram/Tension/Trending), 15분(GDELT)

## 2. 소스 Tier 시스템
A(0.85+0.05) / B(0.70+0.03) / C(0.55+0.01) / D(0.35), 캡 0.95

## 3. 토픽 분류 (11개)
conflict, terror, coup, sanctions, cyber, protest, diplomacy, maritime, disaster, health, unknown
- AI 우선(GPT-4o-mini) + 키워드 규칙 폴백

## 4. Severity (0-100)
### 현재 버전
base(토픽별) + 키워드 보정(±40 캡) + 사상자 보너스(+30)
### 계획: 정보 접근성 보정
RSF Press Freedom Index 기반 상향 보정 (과소보고 보상)

## 5. Tension Index
Raw = 0.55×EventScore + 0.35×ActivityScore + 0.10×Spillover
### 계획: Conflict-Zone Floor
활성 분쟁지역 최소 점수 보장

## 6. KScore (0-10)
### 현재 버전
raw = 0.30×velocity + 0.10×quality + 0.30×severity + 0.30×spread
KScore = raw × 10 × decay(28h 반감기)
### 계획: Key Impact Score 재설계
사용자 기준 국가(home_country) 기반 영향도로 재정의

## 7. 클러스터링
Filtered Jaccard: 0.15(일반), 0.08(고심각도). AI 판단: 0.10~threshold

## 8. 스파이크 감지
events≥8 AND severity≥40 AND sources≥3 AND age≤48h

## 9. 검증(Verified)
confidence≥0.70 AND Tier A 존재 AND sources≥2

## 10. 모니터링 범위
69개국, 이웃국 쌍 77개(Spillover용)
