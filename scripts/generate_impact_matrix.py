#!/usr/bin/env python3
"""
Impact Factor 매트릭스 자동 생성기.

지리적 근접성, 경제적 연관성, 안보 관련성 세 축으로
국가 간 영향도 팩터(geo, sec, eco)를 자동 계산합니다.

데이터 소스:
  - geo: 국가 중심점 간 Haversine 거리 (Natural Earth 좌표)
  - eco: 교역 파트너 순위 (World Bank/IMF DOTS 2023 기준 하드코딩)
  - sec: 동맹/조약/분쟁 관계 (NATO, Five Eyes, QUAD, SCO 등)

사용법:
    python scripts/generate_impact_matrix.py                      # 기본: 30개국 → JSON 출력
    python scripts/generate_impact_matrix.py --output calibration  # calibration.py 직접 업데이트
    python scripts/generate_impact_matrix.py --output json         # JSON 파일 출력
    python scripts/generate_impact_matrix.py --validate            # 수동 팩터와 비교 (drift report)
    python scripts/generate_impact_matrix.py --countries 50        # 50개 기준국 생성
    python scripts/generate_impact_matrix.py --all-pairs           # 모든 국가를 이벤트 대상에 포함

실행 경로: 프로젝트 루트 (~/Projects/wewantpeace/)
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = PROJECT_ROOT / "scripts" / "impact-factors.auto.json"
CALIBRATION_PY = PROJECT_ROOT / "worker" / "processor" / "calibration.py"

# ═══════════════════════════════════════════════════════════════════════════════
# GEOGRAPHIC DATA — Country centroids (ISO Alpha-2 → lat, lon)
# Source: Natural Earth centroid + manual corrections for major countries
# ═══════════════════════════════════════════════════════════════════════════════

COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    # ── East Asia ──
    "KR": (37.5, 127.0),     # 한국
    "KP": (40.0, 127.0),     # 북한
    "JP": (36.2, 138.3),     # 일본
    "CN": (35.9, 104.2),     # 중국
    "TW": (23.7, 121.0),     # 대만
    "MN": (46.9, 103.8),     # 몽골
    "HK": (22.3, 114.2),     # 홍콩
    "MO": (22.2, 113.5),     # 마카오
    # ── Southeast Asia ──
    "VN": (14.1, 108.3),     # 베트남
    "TH": (15.9, 100.9),     # 태국
    "PH": (12.9, 121.8),     # 필리핀
    "MY": (4.2, 101.9),      # 말레이시아
    "SG": (1.4, 103.8),      # 싱가포르
    "ID": (-0.8, 113.9),     # 인도네시아
    "MM": (19.8, 96.1),      # 미얀마
    "KH": (12.6, 105.0),     # 캄보디아
    "LA": (19.9, 102.5),     # 라오스
    "BN": (4.5, 114.7),      # 브루나이
    "TL": (-8.9, 125.7),     # 동티모르
    # ── South Asia ──
    "IN": (20.6, 79.0),      # 인도
    "PK": (30.4, 69.3),      # 파키스탄
    "BD": (23.7, 90.4),      # 방글라데시
    "LK": (7.9, 80.8),       # 스리랑카
    "NP": (28.4, 84.1),      # 네팔
    "BT": (27.5, 90.4),      # 부탄
    "MV": (3.2, 73.2),       # 몰디브
    "AF": (33.9, 67.7),      # 아프가니스탄
    # ── Central Asia ──
    "KZ": (48.0, 68.0),      # 카자흐스탄
    "UZ": (41.4, 64.6),      # 우즈베키스탄
    "TM": (38.9, 59.6),      # 투르크메니스탄
    "KG": (41.2, 74.8),      # 키르기스스탄
    "TJ": (38.9, 71.3),      # 타지키스탄
    # ── Middle East ──
    "IR": (32.4, 53.7),      # 이란
    "IQ": (33.2, 43.7),      # 이라크
    "SA": (23.9, 45.1),      # 사우디아라비아
    "AE": (23.4, 53.8),      # UAE
    "QA": (25.4, 51.2),      # 카타르
    "KW": (29.3, 47.5),      # 쿠웨이트
    "OM": (21.5, 55.9),      # 오만
    "BH": (26.0, 50.5),      # 바레인
    "YE": (15.6, 48.5),      # 예멘
    "SY": (35.0, 38.5),      # 시리아
    "LB": (33.9, 35.9),      # 레바논
    "JO": (30.6, 36.2),      # 요르단
    "IL": (31.0, 34.9),      # 이스라엘
    "PS": (31.9, 35.2),      # 팔레스타인
    "TR": (39.1, 35.2),      # 튀르키예
    "CY": (35.1, 33.4),      # 키프로스
    # ── Europe — Western ──
    "GB": (55.4, -3.4),      # 영국
    "FR": (46.2, 2.2),       # 프랑스
    "DE": (51.2, 10.4),      # 독일
    "IT": (41.9, 12.6),      # 이탈리아
    "ES": (40.5, -3.7),      # 스페인
    "PT": (39.4, -8.2),      # 포르투갈
    "NL": (52.1, 5.3),       # 네덜란드
    "BE": (50.5, 4.5),       # 벨기에
    "LU": (49.8, 6.1),       # 룩셈부르크
    "IE": (53.1, -8.2),      # 아일랜드
    "CH": (46.8, 8.2),       # 스위스
    "AT": (47.5, 14.6),      # 오스트리아
    "MC": (43.7, 7.4),       # 모나코
    "LI": (47.2, 9.6),       # 리히텐슈타인
    "AD": (42.5, 1.5),       # 안도라
    "MT": (35.9, 14.4),      # 몰타
    # ── Europe — Northern ──
    "SE": (60.1, 18.6),      # 스웨덴
    "NO": (60.5, 8.5),       # 노르웨이
    "DK": (56.3, 9.5),       # 덴마크
    "FI": (61.9, 25.7),      # 핀란드
    "IS": (64.1, -19.0),     # 아이슬란드
    # ── Europe — Eastern ──
    "PL": (51.9, 19.1),      # 폴란드
    "CZ": (49.8, 15.5),      # 체코
    "SK": (48.7, 19.7),      # 슬로바키아
    "HU": (47.2, 19.5),      # 헝가리
    "RO": (45.9, 24.9),      # 루마니아
    "BG": (42.7, 25.5),      # 불가리아
    "HR": (45.1, 15.2),      # 크로아티아
    "SI": (46.2, 14.8),      # 슬로베니아
    "RS": (44.0, 21.0),      # 세르비아
    "BA": (43.9, 17.7),      # 보스니아
    "ME": (42.7, 19.4),      # 몬테네그로
    "MK": (41.5, 21.7),      # 북마케도니아
    "AL": (41.2, 20.2),      # 알바니아
    "XK": (42.6, 20.9),      # 코소보
    "EE": (58.6, 25.0),      # 에스토니아
    "LV": (56.9, 24.1),      # 라트비아
    "LT": (55.2, 23.9),      # 리투아니아
    "MD": (47.4, 28.4),      # 몰도바
    "GE": (42.3, 43.4),      # 조지아
    "AM": (40.1, 45.0),      # 아르메니아
    "AZ": (40.1, 47.6),      # 아제르바이잔
    "BY": (53.7, 27.9),      # 벨라루스
    # ── Europe — Post-Soviet ──
    "UA": (48.4, 31.2),      # 우크라이나
    "RU": (61.5, 105.3),     # 러시아
    # ── North America ──
    "US": (39.8, -98.6),     # 미국
    "CA": (56.1, -106.3),    # 캐나다
    "MX": (23.6, -102.6),    # 멕시코
    # ── Central America & Caribbean ──
    "GT": (15.8, -90.2),     # 과테말라
    "BZ": (17.2, -88.5),     # 벨리즈
    "HN": (15.2, -86.2),     # 온두라스
    "SV": (13.8, -88.9),     # 엘살바도르
    "NI": (12.9, -85.2),     # 니카라과
    "CR": (9.7, -83.8),      # 코스타리카
    "PA": (8.5, -80.8),      # 파나마
    "CU": (21.5, -77.8),     # 쿠바
    "JM": (18.1, -77.3),     # 자메이카
    "HT": (19.1, -72.3),     # 아이티
    "DO": (18.7, -70.2),     # 도미니카 공화국
    "TT": (10.7, -61.2),     # 트리니다드토바고
    "BB": (13.2, -59.5),     # 바베이도스
    # ── South America ──
    "BR": (-14.2, -51.9),    # 브라질
    "AR": (-38.4, -63.6),    # 아르헨티나
    "CL": (-35.7, -71.5),    # 칠레
    "CO": (4.6, -74.3),      # 콜롬비아
    "VE": (6.4, -66.6),      # 베네수엘라
    "PE": (-9.2, -75.0),     # 페루
    "EC": (-1.8, -78.2),     # 에콰도르
    "BO": (-16.3, -63.6),    # 볼리비아
    "PY": (-23.4, -58.4),    # 파라과이
    "UY": (-32.5, -55.8),    # 우루과이
    "GY": (5.0, -58.9),      # 가이아나
    "SR": (4.0, -56.0),      # 수리남
    # ── Oceania ──
    "AU": (-25.3, 133.8),    # 호주
    "NZ": (-40.9, 174.9),    # 뉴질랜드
    "PG": (-6.3, 147.2),     # 파푸아뉴기니
    "FJ": (-17.7, 178.1),    # 피지
    "SB": (-9.6, 160.2),     # 솔로몬 제도
    "WS": (-13.8, -172.1),   # 사모아
    "TO": (-21.2, -175.2),   # 통가
    # ── North Africa ──
    "EG": (26.8, 30.8),      # 이집트
    "LY": (26.3, 17.2),      # 리비아
    "TN": (33.9, 9.5),       # 튀니지
    "DZ": (28.0, 1.7),       # 알제리
    "MA": (31.8, -7.1),      # 모로코
    "SD": (12.9, 30.2),      # 수단
    "SS": (6.9, 31.3),       # 남수단
    # ── West Africa ──
    "NG": (9.1, 8.7),        # 나이지리아
    "GH": (7.9, -1.0),       # 가나
    "SN": (14.5, -14.5),     # 세네갈
    "CI": (7.5, -5.5),       # 코트디부아르
    "ML": (17.6, -4.0),      # 말리
    "BF": (12.2, -1.6),      # 부르키나파소
    "NE": (17.6, 8.1),       # 니제르
    "GN": (9.9, -11.8),      # 기니
    "SL": (8.5, -11.8),      # 시에라리온
    "LR": (6.4, -9.4),       # 라이베리아
    "TG": (8.6, 1.2),        # 토고
    "BJ": (9.3, 2.3),        # 베냉
    "GM": (13.4, -16.6),     # 감비아
    "GW": (12.0, -15.2),     # 기니비사우
    "MR": (21.0, -10.9),     # 모리타니
    "CV": (16.0, -24.0),     # 카보베르데
    # ── East Africa ──
    "ET": (9.1, 40.5),       # 에티오피아
    "KE": (-0.0, 37.9),      # 케냐
    "TZ": (-6.4, 34.9),      # 탄자니아
    "UG": (1.4, 32.3),       # 우간다
    "RW": (-1.9, 29.9),      # 르완다
    "BI": (-3.4, 29.9),      # 부룬디
    "SO": (5.2, 46.2),       # 소말리아
    "DJ": (11.8, 43.1),      # 지부티
    "ER": (15.2, 39.8),      # 에리트레아
    # ── Central Africa ──
    "CD": (-4.0, 21.8),      # 콩고민주공화국
    "CG": (-0.2, 15.8),      # 콩고공화국
    "CM": (7.4, 12.4),       # 카메룬
    "CF": (6.6, 20.9),       # 중앙아프리카
    "GA": (-0.8, 11.6),      # 가봉
    "GQ": (1.7, 10.3),       # 적도 기니
    "TD": (15.5, 18.7),      # 차드
    # ── Southern Africa ──
    "ZA": (-30.6, 22.9),     # 남아공
    "ZW": (-20.0, 30.0),     # 짐바브웨
    "MZ": (-18.7, 35.5),     # 모잠비크
    "MW": (-13.3, 34.3),     # 말라위
    "ZM": (-13.1, 27.8),     # 잠비아
    "AO": (-11.2, 17.9),     # 앙골라
    "NA": (-22.6, 17.1),     # 나미비아
    "BW": (-22.3, 24.7),     # 보츠와나
    "SZ": (-26.5, 31.5),     # 에스와티니
    "LS": (-29.6, 28.2),     # 레소토
    "MG": (-18.8, 46.9),     # 마다가스카르
    "MU": (-20.3, 57.6),     # 모리셔스
    "SC": (-4.7, 55.5),      # 세이셸
}

# 전체 국가 목록 (정렬)
ALL_COUNTRIES = sorted(COUNTRY_CENTROIDS.keys())

# ═══════════════════════════════════════════════════════════════════════════════
# TRADE PARTNER DATA — Top 20 trade partners per major country
# Source: World Bank WITS / IMF DOTS 2023 (approximate rankings)
# ═══════════════════════════════════════════════════════════════════════════════

TRADE_PARTNERS: dict[str, list[str]] = {
    "KR": ["CN", "US", "JP", "VN", "HK", "TW", "DE", "AU", "SA", "IN",
            "SG", "MY", "ID", "RU", "TH", "AE", "MX", "GB", "PH", "NL"],
    "US": ["CN", "MX", "CA", "JP", "DE", "KR", "GB", "IN", "TW", "VN",
            "FR", "IT", "NL", "BR", "IE", "SG", "MY", "TH", "CH", "IL"],
    "JP": ["CN", "US", "KR", "TW", "AU", "TH", "VN", "DE", "SA", "AE",
            "ID", "MY", "SG", "IN", "HK", "GB", "FR", "PH", "RU", "CA"],
    "CN": ["US", "JP", "KR", "VN", "TW", "DE", "AU", "MY", "RU", "BR",
            "TH", "IN", "SG", "NL", "ID", "GB", "SA", "HK", "FR", "MX"],
    "TW": ["CN", "US", "JP", "KR", "SG", "HK", "MY", "VN", "DE", "TH",
            "PH", "NL", "IN", "AU", "GB", "ID", "IT", "FR", "SA", "AE"],
    "DE": ["CN", "US", "NL", "FR", "PL", "IT", "AT", "CH", "BE", "CZ",
            "GB", "ES", "HU", "TR", "SE", "RO", "JP", "KR", "RU", "DK"],
    "GB": ["US", "DE", "NL", "FR", "CN", "IE", "BE", "IT", "ES", "NO",
            "TR", "IN", "CH", "SE", "PL", "JP", "AE", "SA", "HK", "KR"],
    "FR": ["DE", "BE", "IT", "ES", "US", "NL", "CN", "GB", "CH", "PL",
            "PT", "CZ", "AT", "SE", "TR", "IE", "JP", "RO", "IN", "DZ"],
    "IT": ["DE", "FR", "US", "CH", "ES", "CN", "NL", "BE", "GB", "PL",
            "AT", "TR", "RO", "RU", "IN", "JP", "CZ", "HU", "SE", "BR"],
    "AU": ["CN", "JP", "KR", "US", "IN", "SG", "NZ", "TH", "MY", "TW",
            "DE", "GB", "VN", "ID", "HK", "AE", "SA", "FR", "IT", "PH"],
    "IN": ["US", "CN", "AE", "SA", "IQ", "SG", "HK", "DE", "KR", "ID",
            "JP", "MY", "BD", "GB", "AU", "NL", "QA", "BE", "VN", "TH"],
    "BR": ["CN", "US", "AR", "NL", "DE", "CL", "SG", "IN", "MX", "JP",
            "KR", "ES", "IT", "CO", "BE", "GB", "SA", "FR", "CA", "TH"],
    "RU": ["CN", "IN", "TR", "KZ", "DE", "NL", "BY", "KR", "IT", "US",
            "JP", "PL", "FR", "AE", "BR", "EG", "FI", "BE", "CZ", "GB"],
    "CA": ["US", "CN", "MX", "JP", "GB", "DE", "KR", "IN", "FR", "IT",
            "NL", "BR", "TW", "CH", "VN", "AU", "BE", "SA", "TH", "SG"],
    "MX": ["US", "CN", "DE", "JP", "KR", "CA", "BR", "MY", "IT", "TW",
            "TH", "NL", "IN", "ES", "FR", "VN", "GB", "CO", "AR", "CL"],
    "SA": ["CN", "IN", "JP", "KR", "US", "AE", "EG", "SG", "DE", "TR",
            "NL", "GB", "FR", "IT", "TH", "PK", "MY", "JO", "BH", "ID"],
    "AE": ["CN", "IN", "SA", "US", "JP", "KR", "DE", "GB", "TR", "IT",
            "TH", "FR", "SG", "NL", "OM", "BH", "IQ", "EG", "PK", "MY"],
    "TR": ["DE", "RU", "CN", "US", "IT", "GB", "FR", "IQ", "ES", "NL",
            "SA", "AE", "PL", "IN", "KR", "BE", "EG", "RO", "BG", "GE"],
    "IL": ["US", "CN", "DE", "GB", "NL", "IN", "TR", "IT", "BE", "FR",
            "JP", "HK", "KR", "CH", "ES", "IE", "TW", "TH", "BR", "AU"],
    "SG": ["CN", "MY", "US", "TW", "HK", "JP", "KR", "ID", "IN", "TH",
            "AU", "DE", "VN", "AE", "FR", "NL", "GB", "SA", "PH", "BR"],
    "NL": ["DE", "BE", "FR", "GB", "US", "CN", "IT", "ES", "PL", "RU",
            "SE", "NO", "IE", "CH", "JP", "CZ", "AT", "TR", "IN", "KR"],
    "PL": ["DE", "CZ", "FR", "IT", "NL", "GB", "US", "CN", "SK", "BE",
            "SE", "ES", "RU", "AT", "HU", "RO", "TR", "UA", "DK", "LT"],
    "SE": ["DE", "NO", "NL", "DK", "FI", "US", "GB", "PL", "FR", "BE",
            "CN", "IT", "ES", "CZ", "AT", "JP", "LT", "EE", "IE", "CH"],
    "NO": ["GB", "DE", "SE", "NL", "US", "DK", "CN", "FR", "PL", "FI",
            "BE", "CA", "IT", "KR", "BR", "ES", "JP", "LT", "CZ", "AT"],
    "CH": ["DE", "US", "FR", "IT", "CN", "GB", "AT", "NL", "ES", "IN",
            "BE", "JP", "PL", "CZ", "HK", "KR", "IE", "SE", "TR", "AE"],
    "EG": ["CN", "SA", "US", "DE", "IT", "TR", "RU", "IN", "AE", "KW",
            "FR", "GB", "UA", "BR", "KR", "ES", "NL", "GR", "JP", "RO"],
    "NG": ["CN", "IN", "US", "NL", "ES", "FR", "BE", "GB", "BR", "DE",
            "IT", "GH", "CI", "TR", "SA", "TG", "CA", "SG", "ZA", "KR"],
    "ZA": ["CN", "DE", "US", "IN", "GB", "SA", "NL", "JP", "AU", "NG",
            "BW", "MZ", "IT", "AE", "BE", "KR", "FR", "BR", "TH", "ES"],
    "PK": ["CN", "AE", "US", "SA", "IN", "DE", "GB", "NL", "KR", "JP",
            "TH", "MY", "ID", "FR", "BD", "IT", "AF", "TR", "SG", "KW"],
    "BD": ["CN", "IN", "US", "SG", "JP", "MY", "HK", "KR", "BR", "ID",
            "DE", "TH", "GB", "AE", "VN", "PK", "AU", "SA", "TW", "IT"],
    "VN": ["CN", "US", "KR", "JP", "TW", "TH", "IN", "AU", "MY", "ID",
            "DE", "SG", "HK", "NL", "GB", "BR", "FR", "PH", "IT", "SA"],
    "TH": ["CN", "US", "JP", "MY", "VN", "AU", "IN", "SG", "KR", "ID",
            "HK", "TW", "DE", "AE", "GB", "NL", "SA", "PH", "CH", "FR"],
    "MY": ["CN", "SG", "US", "JP", "TH", "TW", "KR", "IN", "ID", "HK",
            "VN", "AU", "DE", "NL", "GB", "AE", "PH", "SA", "FR", "IT"],
    "ID": ["CN", "JP", "US", "SG", "IN", "MY", "KR", "TH", "AU", "TW",
            "VN", "DE", "PH", "SA", "AE", "NL", "HK", "BD", "GB", "BR"],
    "PH": ["CN", "JP", "US", "KR", "SG", "TH", "TW", "ID", "HK", "MY",
            "DE", "VN", "AU", "IN", "NL", "AE", "SA", "GB", "FR", "CA"],
    "AR": ["BR", "CN", "US", "CL", "DE", "IN", "NL", "PY", "VN", "IT",
            "MX", "ES", "CA", "UY", "CO", "ID", "TH", "JP", "FR", "GB"],
    "CL": ["CN", "US", "BR", "JP", "KR", "DE", "AR", "CO", "NL", "IN",
            "ES", "MX", "CA", "PE", "IT", "AU", "FR", "GB", "TW", "EC"],
    "CO": ["US", "CN", "BR", "MX", "EC", "DE", "IN", "FR", "CL", "ES",
            "NL", "PE", "TR", "JP", "IT", "CA", "GB", "PA", "KR", "AR"],
    "VE": ["CN", "US", "IN", "BR", "CO", "MX", "TR", "ES", "IT", "DE",
            "CL", "PE", "NL", "RU", "JM", "PA", "EC", "CU", "AR", "JP"],
    "PE": ["CN", "US", "BR", "KR", "IN", "CL", "CA", "JP", "EC", "MX",
            "ES", "CO", "NL", "DE", "BO", "GB", "CH", "IT", "TH", "AR"],
    "UA": ["CN", "PL", "TR", "DE", "RU", "IT", "IN", "NL", "CZ", "HU",
            "EG", "US", "RO", "ES", "GB", "FR", "SK", "BE", "AT", "BG"],
    "GE": ["TR", "CN", "RU", "AZ", "US", "BG", "UA", "AM", "DE", "NL",
            "IT", "IN", "FR", "KZ", "RO", "ES", "GB", "JP", "CZ", "IR"],
    "KZ": ["CN", "IT", "RU", "NL", "TR", "FR", "KR", "US", "IN", "DE",
            "UZ", "GB", "GE", "ES", "SG", "JP", "UA", "FI", "PL", "BE"],
    "CU": ["CN", "ES", "VN", "NL", "MX", "IT", "DE", "BR", "RU", "CA",
            "AR", "FR", "US", "IN", "TR", "BE", "JP", "CL", "CO", "PT"],
    # ── 추가 아프리카 ──
    "KE": ["CN", "IN", "AE", "SA", "US", "JP", "UG", "EG", "GB", "ZA",
            "NL", "DE", "PK", "TZ", "ID", "FR", "MY", "TH", "SG", "RU"],
    "ET": ["CN", "US", "SA", "IN", "AE", "KW", "DE", "JP", "NL", "IT",
            "KR", "TR", "GB", "EG", "DJ", "SD", "ID", "TH", "BE", "VN"],
    "GH": ["CN", "US", "IN", "AE", "NL", "ZA", "GB", "FR", "DE", "NG",
            "BE", "IT", "TR", "CI", "TG", "MY", "ES", "JP", "CA", "BR"],
}

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY ALLIANCE DATA
# ═══════════════════════════════════════════════════════════════════════════════

# NATO 31 members (as of 2024, includes Finland & Sweden)
NATO: set[str] = {
    "US", "CA",  # North America
    "GB", "FR", "DE", "IT", "ES", "PT", "NL", "BE", "LU",  # Western Europe
    "DK", "NO", "IS", "SE", "FI",  # Northern Europe
    "PL", "CZ", "SK", "HU", "RO", "BG", "HR", "SI",  # Central/Eastern
    "EE", "LV", "LT",  # Baltics
    "AL", "ME", "MK",  # Balkans
    "TR", "GR",  # Southeast
}

# Five Eyes intelligence alliance
FIVE_EYES: set[str] = {"US", "GB", "CA", "AU", "NZ"}

# QUAD (Quadrilateral Security Dialogue)
QUAD: set[str] = {"US", "JP", "IN", "AU"}

# SCO (Shanghai Cooperation Organisation) — full members
SCO: set[str] = {"CN", "RU", "IN", "PK", "KZ", "UZ", "KG", "TJ", "IR", "BY"}

# EU (European Union) — for economic/political alignment
EU: set[str] = {
    "FR", "DE", "IT", "ES", "PT", "NL", "BE", "LU", "IE",
    "DK", "SE", "FI", "AT", "CZ", "SK", "HU", "PL",
    "RO", "BG", "HR", "SI", "EE", "LV", "LT",
    "CY", "MT", "GR",
}

# ASEAN
ASEAN: set[str] = {"BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "VN"}

# AUKUS (Australia-UK-US trilateral)
AUKUS: set[str] = {"AU", "GB", "US"}

# GCC (Gulf Cooperation Council)
GCC: set[str] = {"SA", "AE", "QA", "KW", "OM", "BH"}

# CSTO (Collective Security Treaty Organization)
CSTO: set[str] = {"RU", "BY", "KZ", "KG", "TJ", "AM"}

# African Union key security states
AU_KEY: set[str] = {"ZA", "NG", "KE", "ET", "EG", "DZ", "GH", "SN", "TZ", "RW"}

# MERCOSUR
MERCOSUR: set[str] = {"BR", "AR", "UY", "PY"}

# Direct conflict pairs (bidirectional — high sec relevance)
DIRECT_CONFLICT_PAIRS: set[frozenset[str]] = {
    frozenset({"UA", "RU"}),   # Russia-Ukraine war
    frozenset({"KP", "KR"}),   # Korean peninsula
    frozenset({"IL", "PS"}),   # Israel-Palestine
    frozenset({"IL", "IR"}),   # Israel-Iran proxy
    frozenset({"IL", "LB"}),   # Israel-Hezbollah/Lebanon
    frozenset({"IL", "SY"}),   # Israel-Syria
    frozenset({"IL", "YE"}),   # Israel-Houthi/Yemen
    frozenset({"SA", "IR"}),   # Saudi-Iran rivalry
    frozenset({"SA", "YE"}),   # Saudi-Yemen/Houthi
    frozenset({"IN", "PK"}),   # India-Pakistan
    frozenset({"IN", "CN"}),   # India-China border
    frozenset({"CN", "TW"}),   # China-Taiwan
    frozenset({"CN", "PH"}),   # South China Sea
    frozenset({"CN", "JP"}),   # East China Sea / Senkaku
    frozenset({"AM", "AZ"}),   # Armenia-Azerbaijan
    frozenset({"ET", "ER"}),   # Ethiopia-Eritrea
    frozenset({"SD", "SS"}),   # Sudan-South Sudan
    frozenset({"GR", "TR"}),   # Greece-Turkey (Aegean)
    frozenset({"RS", "XK"}),   # Serbia-Kosovo
    frozenset({"MA", "DZ"}),   # Morocco-Algeria (W. Sahara)
    frozenset({"IR", "US"}),   # Iran-US tensions
}

# Proxy conflict linkages — significant involvement in partner's conflicts
PROXY_CONFLICT_LINKS: set[frozenset[str]] = {
    frozenset({"US", "UA"}),   # US support to Ukraine
    frozenset({"RU", "SY"}),   # Russia in Syria
    frozenset({"RU", "IR"}),   # Russia-Iran axis
    frozenset({"US", "IL"}),   # US-Israel alliance
    frozenset({"IR", "LB"}),   # Iran-Hezbollah
    frozenset({"IR", "YE"}),   # Iran-Houthi
    frozenset({"IR", "IQ"}),   # Iran influence in Iraq
    frozenset({"CN", "KP"}),   # China-North Korea
    frozenset({"US", "KR"}),   # US-ROK alliance
    frozenset({"US", "JP"}),   # US-Japan alliance
    frozenset({"US", "TW"}),   # US-Taiwan relations
    frozenset({"TR", "SY"}),   # Turkey in Syria
    frozenset({"TR", "LY"}),   # Turkey in Libya
    frozenset({"RU", "LY"}),   # Russia/Wagner in Libya
    frozenset({"RU", "ML"}),   # Russia/Wagner in Mali
    frozenset({"RU", "CF"}),   # Russia/Wagner in CAR
}

# ═══════════════════════════════════════════════════════════════════════════════
# REGION MAPPING — for same-region baseline sec factor
# ═══════════════════════════════════════════════════════════════════════════════

REGIONS: dict[str, set[str]] = {
    "East Asia": {"KR", "KP", "JP", "CN", "TW", "MN", "HK", "MO"},
    "Southeast Asia": {"VN", "TH", "PH", "MY", "SG", "ID", "MM", "KH", "LA", "BN", "TL"},
    "South Asia": {"IN", "PK", "BD", "LK", "NP", "BT", "MV", "AF"},
    "Central Asia": {"KZ", "UZ", "TM", "KG", "TJ"},
    "Middle East": {"IR", "IQ", "SA", "AE", "QA", "KW", "OM", "BH", "YE", "SY", "LB", "JO", "IL", "PS", "TR", "CY"},
    "Western Europe": {"GB", "FR", "DE", "IT", "ES", "PT", "NL", "BE", "LU", "IE", "CH", "AT", "MC", "LI", "AD", "MT"},
    "Northern Europe": {"SE", "NO", "DK", "FI", "IS"},
    "Eastern Europe": {"PL", "CZ", "SK", "HU", "RO", "BG", "HR", "SI", "RS", "BA", "ME", "MK", "AL", "XK",
                        "EE", "LV", "LT", "MD", "GE", "AM", "AZ", "BY", "UA", "RU", "GR"},
    "North America": {"US", "CA", "MX"},
    "Central America": {"GT", "BZ", "HN", "SV", "NI", "CR", "PA", "CU", "JM", "HT", "DO", "TT", "BB"},
    "South America": {"BR", "AR", "CL", "CO", "VE", "PE", "EC", "BO", "PY", "UY", "GY", "SR"},
    "Oceania": {"AU", "NZ", "PG", "FJ", "SB", "WS", "TO"},
    "North Africa": {"EG", "LY", "TN", "DZ", "MA", "SD", "SS"},
    "West Africa": {"NG", "GH", "SN", "CI", "ML", "BF", "NE", "GN", "SL", "LR", "TG", "BJ", "GM", "GW", "MR", "CV"},
    "East Africa": {"ET", "KE", "TZ", "UG", "RW", "BI", "SO", "DJ", "ER"},
    "Central Africa": {"CD", "CG", "CM", "CF", "GA", "GQ", "TD"},
    "Southern Africa": {"ZA", "ZW", "MZ", "MW", "ZM", "AO", "NA", "BW", "SZ", "LS", "MG", "MU", "SC"},
}

# Build reverse mapping: country → region
_COUNTRY_REGION: dict[str, str] = {}
for _region, _members in REGIONS.items():
    for _cc in _members:
        _COUNTRY_REGION[_cc] = _region


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT HOME COUNTRIES — Top economies + conflict hotspots + regional powers
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_HOME_COUNTRIES: list[str] = [
    # G7
    "US", "GB", "FR", "DE", "IT", "JP", "CA",
    # East Asia key
    "KR", "CN", "TW",
    # BRICS+
    "BR", "IN", "RU", "ZA",
    # Middle East
    "SA", "IL", "TR", "IR", "AE",
    # Southeast Asia
    "VN", "TH", "ID", "PH", "SG", "MY",
    # Oceania
    "AU", "NZ",
    # Others
    "PL", "UA", "EG",
]


# ═══════════════════════════════════════════════════════════════════════════════
# CALCULATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 Haversine 거리 (km)."""
    R = 6371.0  # 지구 반지름 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calc_geo_factor(home: str, event: str) -> float:
    """지리적 근접성 팩터 (0.0~1.0).

    Haversine 거리 기반. 가까울수록 1.0에 근접.
    자국(home==event) → 1.0
    거리 0km → 1.0, 20,000km → 0.0 (선형 감소)
    """
    if home == event:
        return 1.0

    h = COUNTRY_CENTROIDS.get(home)
    e = COUNTRY_CENTROIDS.get(event)
    if not h or not e:
        return 0.3  # 좌표 없는 국가 기본값

    dist = haversine(h[0], h[1], e[0], e[1])

    # 비선형 감소: 가까운 거리에서 더 민감하게
    # 500km 이내 → 0.95+, 2000km → 0.8, 5000km → 0.55, 10000km → 0.25, 20000km → 0.0
    factor = 1.0 - min(1.0, (dist / 20000) ** 0.7)
    return round(factor, 2)


def calc_eco_factor(home: str, event: str) -> float:
    """경제적 연관성 팩터 (0.0~1.0).

    교역 파트너 순위 기반.
    자국 → 1.0
    Top 3 교역국 → 0.9
    Top 5 → 0.8
    Top 10 → 0.6
    Top 20 → 0.4
    교역 데이터 없음 → 0.2 (기본)

    양방향 확인: home→event 또는 event→home 중 높은 값 사용.
    """
    if home == event:
        return 1.0

    def _rank_score(h: str, e: str) -> float:
        partners = TRADE_PARTNERS.get(h)
        if not partners:
            return 0.0
        if e not in partners:
            return 0.0
        rank = partners.index(e)  # 0-based
        if rank < 3:
            return 0.9
        elif rank < 5:
            return 0.8
        elif rank < 10:
            return 0.6
        else:
            return 0.4

    # 양방향 최대값
    score = max(_rank_score(home, event), _rank_score(event, home))

    if score == 0.0:
        # 둘 다 교역 데이터가 없거나 상대방이 목록에 없는 경우
        # 같은 지역이면 약간 높은 기본값
        home_region = _COUNTRY_REGION.get(home)
        event_region = _COUNTRY_REGION.get(event)
        if home_region and home_region == event_region:
            return 0.3
        return 0.2

    return score


def calc_sec_factor(home: str, event: str) -> float:
    """안보 관련성 팩터 (0.0~1.0).

    동맹/조약/분쟁 관계 기반. 여러 조건의 최대값 사용.

    직접 분쟁 쌍: 0.95
    프록시 분쟁 연관: 0.75
    Five Eyes: 0.80
    AUKUS: 0.75
    QUAD: 0.65
    NATO 동맹: 0.60
    CSTO: 0.55
    SCO: 0.45
    EU: 0.40
    GCC: 0.50
    ASEAN: 0.30
    같은 지역: 0.20
    기본값: 0.10
    """
    if home == event:
        return 1.0

    pair = frozenset({home, event})
    scores: list[float] = []

    # 직접 분쟁
    if pair in DIRECT_CONFLICT_PAIRS:
        scores.append(0.95)

    # 프록시 분쟁
    if pair in PROXY_CONFLICT_LINKS:
        scores.append(0.75)

    # Five Eyes
    if home in FIVE_EYES and event in FIVE_EYES:
        scores.append(0.80)

    # AUKUS
    if home in AUKUS and event in AUKUS:
        scores.append(0.75)

    # QUAD
    if home in QUAD and event in QUAD:
        scores.append(0.65)

    # NATO
    if home in NATO and event in NATO:
        scores.append(0.60)

    # CSTO
    if home in CSTO and event in CSTO:
        scores.append(0.55)

    # GCC
    if home in GCC and event in GCC:
        scores.append(0.50)

    # SCO
    if home in SCO and event in SCO:
        scores.append(0.45)

    # EU
    if home in EU and event in EU:
        scores.append(0.40)

    # ASEAN
    if home in ASEAN and event in ASEAN:
        scores.append(0.30)

    # MERCOSUR
    if home in MERCOSUR and event in MERCOSUR:
        scores.append(0.30)

    # AU key members
    if home in AU_KEY and event in AU_KEY:
        scores.append(0.25)

    # 같은 지역
    home_region = _COUNTRY_REGION.get(home)
    event_region = _COUNTRY_REGION.get(event)
    if home_region and home_region == event_region:
        scores.append(0.20)

    # 분쟁국 인접 보너스: event가 분쟁 쌍 중 하나에 있으면 home에 약간 관련
    for conflict_pair in DIRECT_CONFLICT_PAIRS:
        if event in conflict_pair:
            other = (conflict_pair - {event}).pop()
            if frozenset({home, other}) in DIRECT_CONFLICT_PAIRS:
                scores.append(0.60)
                break
            if frozenset({home, other}) in PROXY_CONFLICT_LINKS:
                scores.append(0.50)
                break

    if scores:
        return round(max(scores), 2)

    return 0.10


def generate_matrix(
    home_countries: list[str],
    event_countries: list[str] | None = None,
    min_combined: float = 0.0,
) -> dict[str, dict[str, dict[str, float]]]:
    """Impact factor 매트릭스 생성.

    Args:
        home_countries: 기준국 목록 (사용자 관점)
        event_countries: 이벤트 발생국 목록 (None이면 COUNTRY_CENTROIDS 전체)
        min_combined: 이 값 이하의 combined factor는 제외 (희소화)

    Returns:
        {home: {event: {geo, sec, eco}}} 구조
    """
    if event_countries is None:
        event_countries = ALL_COUNTRIES

    matrix: dict[str, dict[str, dict[str, float]]] = {}

    for home in sorted(home_countries):
        if home not in COUNTRY_CENTROIDS:
            print(f"[WARN] 좌표 없는 기준국 건너뜀: {home}", file=sys.stderr)
            continue

        pairs: dict[str, dict[str, float]] = {}
        for event in event_countries:
            if event not in COUNTRY_CENTROIDS:
                continue

            geo = calc_geo_factor(home, event)
            eco = calc_eco_factor(home, event)
            sec = calc_sec_factor(home, event)

            # 최소 combined threshold 필터
            combined = geo * 0.33 + sec * 0.34 + eco * 0.33
            if combined < min_combined:
                continue

            pairs[event] = {"geo": geo, "sec": sec, "eco": eco}

        # 자국은 항상 포함
        if home not in pairs:
            pairs[home] = {"geo": 1.0, "sec": 1.0, "eco": 1.0}

        # combined 기준 내림차순 정렬 → 상위 국가가 먼저
        sorted_pairs = dict(
            sorted(
                pairs.items(),
                key=lambda x: -(x[1]["geo"] * 0.33 + x[1]["sec"] * 0.34 + x[1]["eco"] * 0.33),
            )
        )
        matrix[home] = sorted_pairs

    return matrix


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION — Compare auto-generated vs manual factors
# ═══════════════════════════════════════════════════════════════════════════════

def load_manual_factors() -> dict:
    """calibration.py에서 수동 정의 IMPACT_FACTORS를 로드."""
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from worker.processor.calibration import IMPACT_FACTORS
        return IMPACT_FACTORS
    except ImportError:
        # AST 파싱 폴백
        import ast
        source = CALIBRATION_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "IMPACT_FACTORS":
                        return ast.literal_eval(node.value)
        print("[ERROR] IMPACT_FACTORS를 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)


def validate_against_manual(auto_matrix: dict) -> None:
    """수동 팩터와 자동 생성 팩터 비교 → drift report 출력."""
    manual = load_manual_factors()

    print("\n" + "=" * 72)
    print("  IMPACT FACTOR DRIFT REPORT — 수동(manual) vs 자동(auto)")
    print("=" * 72)

    total_pairs = 0
    total_drift = {"geo": 0.0, "sec": 0.0, "eco": 0.0}
    max_drifts: list[tuple[str, str, str, float, float, float]] = []

    for home in sorted(manual.keys()):
        if home not in auto_matrix:
            print(f"\n  [SKIP] {home}: 자동 매트릭스에 없음")
            continue

        print(f"\n  ── {home} ──")
        auto_pairs = auto_matrix[home]

        for event in sorted(manual[home].keys()):
            m = manual[home][event]
            a = auto_pairs.get(event, {"geo": 0.3, "sec": 0.1, "eco": 0.2})

            d_geo = a["geo"] - m["geo"]
            d_sec = a["sec"] - m["sec"]
            d_eco = a["eco"] - m["eco"]
            d_abs = abs(d_geo) + abs(d_sec) + abs(d_eco)

            total_pairs += 1
            total_drift["geo"] += abs(d_geo)
            total_drift["sec"] += abs(d_sec)
            total_drift["eco"] += abs(d_eco)

            # 유의미한 drift만 표시 (3축 합 0.3 이상)
            marker = ""
            if d_abs >= 0.6:
                marker = " !!!"
            elif d_abs >= 0.3:
                marker = " !"

            if d_abs >= 0.15:
                print(
                    f"    {event}: "
                    f"geo {m['geo']:.2f}→{a['geo']:.2f} ({d_geo:+.2f})  "
                    f"sec {m['sec']:.2f}→{a['sec']:.2f} ({d_sec:+.2f})  "
                    f"eco {m['eco']:.2f}→{a['eco']:.2f} ({d_eco:+.2f})"
                    f"{marker}"
                )

            max_drifts.append((home, event, "total", d_abs, 0.0, 0.0))

    # 요약 통계
    print("\n" + "─" * 72)
    print("  요약 통계")
    print("─" * 72)

    if total_pairs > 0:
        print(f"  비교 쌍: {total_pairs}개")
        print(f"  평균 drift (geo): {total_drift['geo'] / total_pairs:.3f}")
        print(f"  평균 drift (sec): {total_drift['sec'] / total_pairs:.3f}")
        print(f"  평균 drift (eco): {total_drift['eco'] / total_pairs:.3f}")
        avg_total = sum(total_drift.values()) / total_pairs
        print(f"  평균 drift (합계): {avg_total:.3f}")

        # 최대 drift Top 10
        max_drifts.sort(key=lambda x: -x[3])
        print(f"\n  최대 drift Top 10:")
        for home, event, _, d, _, _ in max_drifts[:10]:
            m = manual[home][event]
            a = auto_matrix[home].get(event, {"geo": 0.3, "sec": 0.1, "eco": 0.2})
            print(
                f"    {home}→{event}: "
                f"manual({m['geo']:.1f},{m['sec']:.1f},{m['eco']:.1f}) "
                f"auto({a['geo']:.2f},{a['sec']:.2f},{a['eco']:.2f}) "
                f"drift={d:.2f}"
            )

    print()


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def write_json(matrix: dict, output_path: Path) -> None:
    """JSON 파일로 출력."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(matrix, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    output_path.write_text(json_str, encoding="utf-8")

    total_pairs = sum(len(v) for v in matrix.values())
    print(f"[OK] {output_path}")
    print(f"  기준국: {len(matrix)}개")
    print(f"  총 영향 쌍: {total_pairs}개")


def update_calibration_py(matrix: dict) -> None:
    """calibration.py의 IMPACT_FACTORS를 업데이트.

    기존 수동 정의된 값을 자동 생성 값으로 교체합니다.
    SUPPORTED_HOME_COUNTRIES도 업데이트합니다.
    """
    source = CALIBRATION_PY.read_text(encoding="utf-8")

    # IMPACT_FACTORS dict 텍스트 생성
    lines = ["IMPACT_FACTORS: dict[str, dict[str, dict[str, float]]] = {"]
    for home in matrix:
        lines.append(f'    "{home}": {{')
        pairs = matrix[home]
        # 상위 20개만 포함 (calibration.py가 너무 커지지 않게)
        for i, (event, factors) in enumerate(pairs.items()):
            if i >= 20 and home != event:
                continue
            lines.append(
                f'        "{event}": '
                f'{{"geo": {factors["geo"]}, "sec": {factors["sec"]}, "eco": {factors["eco"]}}},'
            )
        lines.append("    },")
    lines.append("}")

    new_impact = "\n".join(lines)

    # 기존 IMPACT_FACTORS 블록 교체
    # 패턴: IMPACT_FACTORS: dict[...] = { ... }
    pattern = (
        r'IMPACT_FACTORS: dict\[str, dict\[str, dict\[str, float\]\]\] = \{.*?\n\}'
    )
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        # 타입 어노테이션 없이 시도
        pattern = r'IMPACT_FACTORS\s*=\s*\{.*?\n\}'
        match = re.search(pattern, source, re.DOTALL)

    if match:
        new_source = source[:match.start()] + new_impact + source[match.end():]
        CALIBRATION_PY.write_text(new_source, encoding="utf-8")
        print(f"[OK] {CALIBRATION_PY.relative_to(PROJECT_ROOT)} 업데이트 완료")
        print(f"  기준국: {len(matrix)}개")
        total = sum(min(len(v), 20) for v in matrix.values())
        print(f"  영향 쌍: ~{total}개 (기준국당 최대 20개)")
    else:
        print("[ERROR] IMPACT_FACTORS 블록을 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)


def print_summary(matrix: dict) -> None:
    """매트릭스 통계 요약 출력."""
    print("\n" + "=" * 60)
    print("  Impact Factor Matrix 생성 완료")
    print("=" * 60)
    print(f"  기준국(home): {len(matrix)}개")
    total_pairs = sum(len(v) for v in matrix.values())
    print(f"  총 영향 쌍: {total_pairs:,}개")
    avg_pairs = total_pairs / len(matrix) if matrix else 0
    print(f"  기준국당 평균: {avg_pairs:.0f}개 이벤트국")

    # 각 축별 평균
    all_geos, all_secs, all_ecos = [], [], []
    for pairs in matrix.values():
        for factors in pairs.values():
            all_geos.append(factors["geo"])
            all_secs.append(factors["sec"])
            all_ecos.append(factors["eco"])

    if all_geos:
        print(f"\n  팩터 평균:")
        print(f"    geo: {sum(all_geos)/len(all_geos):.3f}")
        print(f"    sec: {sum(all_secs)/len(all_secs):.3f}")
        print(f"    eco: {sum(all_ecos)/len(all_ecos):.3f}")

    # 상위 영향 쌍 (combined 기준)
    print(f"\n  Combined 최상위 쌍 (home→event):")
    top_pairs: list[tuple[str, str, float]] = []
    for home, pairs in matrix.items():
        for event, f in pairs.items():
            if home == event:
                continue
            combined = f["geo"] * 0.33 + f["sec"] * 0.34 + f["eco"] * 0.33
            top_pairs.append((home, event, combined))

    top_pairs.sort(key=lambda x: -x[2])
    for home, event, c in top_pairs[:15]:
        f = matrix[home][event]
        print(
            f"    {home}→{event}: combined={c:.2f} "
            f"(geo={f['geo']:.2f}, sec={f['sec']:.2f}, eco={f['eco']:.2f})"
        )

    print()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Impact Factor 매트릭스 자동 생성 (geo/sec/eco)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/generate_impact_matrix.py                      # 기본 30개국 → JSON
  python scripts/generate_impact_matrix.py --output calibration  # calibration.py 업데이트
  python scripts/generate_impact_matrix.py --validate            # 수동 vs 자동 비교
  python scripts/generate_impact_matrix.py --countries 50        # 50개 기준국
  python scripts/generate_impact_matrix.py --all-pairs           # 모든 이벤트국 포함
  python scripts/generate_impact_matrix.py --list-countries      # 지원 국가 목록 출력
        """,
    )
    parser.add_argument(
        "--output",
        choices=["json", "calibration", "stdout"],
        default="json",
        help="출력 형식 (기본: json 파일)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="수동 팩터와 비교하여 drift report 출력",
    )
    parser.add_argument(
        "--countries",
        type=int,
        default=30,
        help="생성할 기준국 수 (기본: 30, 최대: 전체 국가 수)",
    )
    parser.add_argument(
        "--home-list",
        type=str,
        default=None,
        help="기준국 목록 (쉼표 구분, 예: KR,US,JP). 지정 시 --countries 무시",
    )
    parser.add_argument(
        "--all-pairs",
        action="store_true",
        help="모든 국가를 이벤트 대상에 포함 (기본: 전체)",
    )
    parser.add_argument(
        "--top-events",
        type=int,
        default=0,
        help="기준국당 상위 N개 이벤트국만 포함 (0=전체, 기본: 0)",
    )
    parser.add_argument(
        "--min-combined",
        type=float,
        default=0.0,
        help="최소 combined factor threshold (이하 제외, 기본: 0.0)",
    )
    parser.add_argument(
        "--list-countries",
        action="store_true",
        help="지원 국가 목록 출력 후 종료",
    )
    args = parser.parse_args()

    # 국가 목록 출력
    if args.list_countries:
        print(f"지원 국가: {len(ALL_COUNTRIES)}개\n")
        for i, cc in enumerate(ALL_COUNTRIES):
            coord = COUNTRY_CENTROIDS[cc]
            region = _COUNTRY_REGION.get(cc, "?")
            trade = "T" if cc in TRADE_PARTNERS else " "
            print(f"  {cc} ({coord[0]:6.1f}, {coord[1]:7.1f})  [{region}] {trade}")
            if (i + 1) % 30 == 0:
                print()
        print(f"\n  T = 교역 데이터 보유 ({len(TRADE_PARTNERS)}개국)")
        return

    # 기준국 결정
    if args.home_list:
        home_countries = [c.strip().upper() for c in args.home_list.split(",")]
        unknown = [c for c in home_countries if c not in COUNTRY_CENTROIDS]
        if unknown:
            print(f"[ERROR] 알 수 없는 국가 코드: {', '.join(unknown)}", file=sys.stderr)
            sys.exit(1)
    else:
        home_countries = DEFAULT_HOME_COUNTRIES[:args.countries]
        # countries가 기본 목록보다 많으면 ALL_COUNTRIES에서 추가
        if args.countries > len(DEFAULT_HOME_COUNTRIES):
            remaining = [c for c in ALL_COUNTRIES if c not in set(home_countries)]
            home_countries.extend(remaining[:args.countries - len(DEFAULT_HOME_COUNTRIES)])

    print(f"[INFO] 기준국 {len(home_countries)}개로 매트릭스 생성 중...", file=sys.stderr)

    # 매트릭스 생성
    matrix = generate_matrix(
        home_countries=home_countries,
        event_countries=ALL_COUNTRIES if args.all_pairs else None,
        min_combined=args.min_combined,
    )

    # 상위 N개 이벤트국만 유지
    if args.top_events > 0:
        for home in matrix:
            pairs = matrix[home]
            # combined 기준 정렬 후 상위 N개 + 자국
            sorted_events = sorted(
                pairs.items(),
                key=lambda x: -(x[1]["geo"] * 0.33 + x[1]["sec"] * 0.34 + x[1]["eco"] * 0.33),
            )
            kept = {}
            count = 0
            for event, factors in sorted_events:
                if event == home or count < args.top_events:
                    kept[event] = factors
                    if event != home:
                        count += 1
            matrix[home] = kept

    # 요약 출력
    print_summary(matrix)

    # 검증 모드
    if args.validate:
        validate_against_manual(matrix)

    # 출력
    if args.output == "json":
        write_json(matrix, OUTPUT_JSON)
    elif args.output == "calibration":
        update_calibration_py(matrix)
        # sync_impact_factors.py도 실행
        print("\n[INFO] sync_impact_factors.py 실행으로 프론트엔드 JSON도 동기화하세요:")
        print(f"  python scripts/sync_impact_factors.py")
    elif args.output == "stdout":
        json.dump(matrix, sys.stdout, indent=2, ensure_ascii=False, sort_keys=False)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
