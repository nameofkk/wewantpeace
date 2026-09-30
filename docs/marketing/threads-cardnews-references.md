# 스레드 카드뉴스 레퍼런스 조사 (2026-09-30)

스레드에서 실제로 운영 중인 뉴스·카드뉴스 계정 약 70곳을 로그인 없이 열어, 첫 화면 게시물의 이미지(캐러셀 전 장)와 본문을 직접 확인했다. 로그인 화면으로 넘어간 계정(Guardian, DW, FT, Vox 등)은 보지 못했다.

## 이미지

| 계정 | 표지 | 속 장 | 끝 장 |
|---|---|---|---|
| Politico | 사진 전면, 아래 어둡게, 굵은 흰 헤드라인, 작은 라벨(● BREAKING NEWS) | 단일 이미지 위주 | - |
| Al Jazeera English | 사진 전면, 왼쪽 아래 반투명 상자, 핵심 구절 빨강 | - | - |
| Daily Mail | 사진 전면 + 아래 그라데이션, 빨간 라벨 | - | - |
| War Monitor | 사진 전면, 좁은 대문자 헤드라인, 핵심어 빨강, 날짜 | - | - |
| Ground News | 사진 + 칩 "Trending · United Kingdom · 443 sources" + 헤드라인 | - | - |
| Novara Media | 사진 전면 + 헤드라인 + 한 줄 부제 | 장마다 다른 사진, 번호 원 + 소제목 + 2~3줄, 사진 출처 작게, → | - |
| Times of Israel | 사진 + 위쪽 헤드라인 | 장마다 다른 사진, 반투명 흰 상자에 2~3문장 | - |
| Zeteo | 사진 + 가운데 큰 헤드라인 | 사진 + 어두운 글 영역, THEN/NOW | "read about … at zeteo.com" |
| Let's Talk Palestine | 어두운 사진 + 큰 헤드라인(핵심 구절 색) + 부제 | 10~15장 해설 | 출처 목록 |
| Horizon Geopolitics | 질문형 헤드라인 + 노란 형광 | 한 장 한 항목, >>> | 뉴스레터 구독 CTA |
| Brut | 사진 전면 + 큰 헤드라인, → | 사진 전면 + 흰 라벨 상자 + 노란 강조 | - |
| AJ+ | 콜라주 + 형광펜 헤드라인 | 장마다 1~2문장 | - |
| 뉴닉 | 사진 + 주황 상자 헤드라인 | 질문 말풍선 → 답 → 2~3줄 | 고정 마무리 카드 |

## 본문

- 헤드라인을 본문에 반복하지 않는다. 뉴스 한 문장 + 맥락 한 문장 (Politico, Al Jazeera, Ground News, Middle East Monitor).
- 출처 표기: "according to The Washington Post", "Anadolu reports", "Credits: REUTERS", "📷 AP Photo".
- 링크는 본문 끝 짧은 링크(Reuters·Ground News) 또는 자기 답글(so informed·Novara). so informed 는 본문은 한 문장 + 사진, 자세한 설명 2~4문단과 링크는 자기 답글로 잇는다.
- 해시태그 거의 없음. 이모지는 사진 출처 표시 정도.

## 반영 (worker/social/brief_card.py, brief.py)

표지(사진 전면 + 나라·날짜 칩 + "N sources" 칩 + 노란 핵심 구절 + 한 줄 부제) → 무슨 일 / 왜 중요 / 지켜볼 점(장마다 다른 기사 사진, 번호 원 + 소제목) → 출처 목록 + 주간 브리프 구독. 본문은 뉴스 한 문장 + 맥락 한 문장 + 출처, 지켜볼 점·링크·구독은 자기 답글.
