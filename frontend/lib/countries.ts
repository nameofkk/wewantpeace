export interface CountryInfo {
  code: string;
  name: string;
  flag: string;
  region: string;
}

export const ALL_COUNTRIES: CountryInfo[] = [
  // ── 유럽 ──────────────────────────────────────────────────────
  { code: "UA", name: "우크라이나",      flag: "🇺🇦", region: "유럽" },
  { code: "RU", name: "러시아",          flag: "🇷🇺", region: "유럽" },
  { code: "BY", name: "벨라루스",        flag: "🇧🇾", region: "유럽" },
  { code: "MD", name: "몰도바",          flag: "🇲🇩", region: "유럽" },
  { code: "RS", name: "세르비아",        flag: "🇷🇸", region: "유럽" },
  { code: "XK", name: "코소보",          flag: "🇽🇰", region: "유럽" },
  { code: "BA", name: "보스니아",        flag: "🇧🇦", region: "유럽" },
  { code: "GE", name: "조지아",          flag: "🇬🇪", region: "유럽" },
  { code: "AM", name: "아르메니아",      flag: "🇦🇲", region: "유럽" },
  { code: "AZ", name: "아제르바이잔",    flag: "🇦🇿", region: "유럽" },

  // ── 중동 ──────────────────────────────────────────────────────
  { code: "PS", name: "팔레스타인",      flag: "🇵🇸", region: "중동" },
  { code: "IL", name: "이스라엘",        flag: "🇮🇱", region: "중동" },
  { code: "IR", name: "이란",            flag: "🇮🇷", region: "중동" },
  { code: "IQ", name: "이라크",          flag: "🇮🇶", region: "중동" },
  { code: "SY", name: "시리아",          flag: "🇸🇾", region: "중동" },
  { code: "LB", name: "레바논",          flag: "🇱🇧", region: "중동" },
  { code: "YE", name: "예멘",            flag: "🇾🇪", region: "중동" },
  { code: "SA", name: "사우디아라비아",  flag: "🇸🇦", region: "중동" },
  { code: "TR", name: "튀르키예",        flag: "🇹🇷", region: "중동" },
  { code: "EG", name: "이집트",          flag: "🇪🇬", region: "중동" },
  { code: "JO", name: "요르단",          flag: "🇯🇴", region: "중동" },
  { code: "AE", name: "아랍에미리트",    flag: "🇦🇪", region: "중동" },
  { code: "QA", name: "카타르",          flag: "🇶🇦", region: "중동" },

  // ── 동아시아 ──────────────────────────────────────────────────
  { code: "KP", name: "북한",            flag: "🇰🇵", region: "동아시아" },
  { code: "KR", name: "대한민국",        flag: "🇰🇷", region: "동아시아" },
  { code: "TW", name: "대만",            flag: "🇹🇼", region: "동아시아" },
  { code: "CN", name: "중국",            flag: "🇨🇳", region: "동아시아" },
  { code: "JP", name: "일본",            flag: "🇯🇵", region: "동아시아" },
  { code: "MN", name: "몽골",            flag: "🇲🇳", region: "동아시아" },

  // ── 동남아 ────────────────────────────────────────────────────
  { code: "MM", name: "미얀마",          flag: "🇲🇲", region: "동남아" },
  { code: "PH", name: "필리핀",          flag: "🇵🇭", region: "동남아" },
  { code: "VN", name: "베트남",          flag: "🇻🇳", region: "동남아" },
  { code: "ID", name: "인도네시아",      flag: "🇮🇩", region: "동남아" },
  { code: "TH", name: "태국",            flag: "🇹🇭", region: "동남아" },
  { code: "MY", name: "말레이시아",      flag: "🇲🇾", region: "동남아" },
  { code: "KH", name: "캄보디아",        flag: "🇰🇭", region: "동남아" },
  { code: "LA", name: "라오스",          flag: "🇱🇦", region: "동남아" },

  // ── 남아시아 ──────────────────────────────────────────────────
  { code: "PK", name: "파키스탄",        flag: "🇵🇰", region: "남아시아" },
  { code: "AF", name: "아프가니스탄",    flag: "🇦🇫", region: "남아시아" },
  { code: "IN", name: "인도",            flag: "🇮🇳", region: "남아시아" },
  { code: "BD", name: "방글라데시",      flag: "🇧🇩", region: "남아시아" },
  { code: "LK", name: "스리랑카",        flag: "🇱🇰", region: "남아시아" },
  { code: "NP", name: "네팔",            flag: "🇳🇵", region: "남아시아" },

  // ── 중앙아시아 ────────────────────────────────────────────────
  { code: "KZ", name: "카자흐스탄",      flag: "🇰🇿", region: "중앙아시아" },
  { code: "TJ", name: "타지키스탄",      flag: "🇹🇯", region: "중앙아시아" },
  { code: "KG", name: "키르기스스탄",    flag: "🇰🇬", region: "중앙아시아" },
  { code: "UZ", name: "우즈베키스탄",    flag: "🇺🇿", region: "중앙아시아" },
  { code: "TM", name: "투르크메니스탄",  flag: "🇹🇲", region: "중앙아시아" },

  // ── 아프리카 ──────────────────────────────────────────────────
  { code: "SD", name: "수단",            flag: "🇸🇩", region: "아프리카" },
  { code: "SS", name: "남수단",          flag: "🇸🇸", region: "아프리카" },
  { code: "ET", name: "에티오피아",      flag: "🇪🇹", region: "아프리카" },
  { code: "SO", name: "소말리아",        flag: "🇸🇴", region: "아프리카" },
  { code: "ER", name: "에리트레아",      flag: "🇪🇷", region: "아프리카" },
  { code: "LY", name: "리비아",          flag: "🇱🇾", region: "아프리카" },
  { code: "ML", name: "말리",            flag: "🇲🇱", region: "아프리카" },
  { code: "BF", name: "부르키나파소",    flag: "🇧🇫", region: "아프리카" },
  { code: "NE", name: "니제르",          flag: "🇳🇪", region: "아프리카" },
  { code: "TD", name: "차드",            flag: "🇹🇩", region: "아프리카" },
  { code: "NG", name: "나이지리아",      flag: "🇳🇬", region: "아프리카" },
  { code: "CM", name: "카메룬",          flag: "🇨🇲", region: "아프리카" },
  { code: "CF", name: "중앙아프리카공화국", flag: "🇨🇫", region: "아프리카" },
  { code: "CD", name: "콩고민주공화국",  flag: "🇨🇩", region: "아프리카" },
  { code: "CG", name: "콩고공화국",      flag: "🇨🇬", region: "아프리카" },
  { code: "MZ", name: "모잠비크",        flag: "🇲🇿", region: "아프리카" },
  { code: "ZW", name: "짐바브웨",        flag: "🇿🇼", region: "아프리카" },
  { code: "MA", name: "모로코",          flag: "🇲🇦", region: "아프리카" },
  { code: "DZ", name: "알제리",          flag: "🇩🇿", region: "아프리카" },
  { code: "TN", name: "튀니지",          flag: "🇹🇳", region: "아프리카" },
  { code: "GN", name: "기니",            flag: "🇬🇳", region: "아프리카" },
  { code: "GW", name: "기니비사우",      flag: "🇬🇼", region: "아프리카" },
  { code: "SL", name: "시에라리온",      flag: "🇸🇱", region: "아프리카" },
  { code: "MR", name: "모리타니",        flag: "🇲🇷", region: "아프리카" },

  // ── 남미 ──────────────────────────────────────────────────────
  { code: "VE", name: "베네수엘라",      flag: "🇻🇪", region: "남미" },
  { code: "HT", name: "아이티",          flag: "🇭🇹", region: "남미" },
  { code: "CO", name: "콜롬비아",        flag: "🇨🇴", region: "남미" },
  { code: "EC", name: "에콰도르",        flag: "🇪🇨", region: "남미" },
  { code: "PE", name: "페루",            flag: "🇵🇪", region: "남미" },
  { code: "BO", name: "볼리비아",        flag: "🇧🇴", region: "남미" },
  { code: "BR", name: "브라질",          flag: "🇧🇷", region: "남미" },

  // ── 중미·카리브 ───────────────────────────────────────────────
  { code: "MX", name: "멕시코",          flag: "🇲🇽", region: "중미" },
  { code: "GT", name: "과테말라",        flag: "🇬🇹", region: "중미" },
  { code: "HN", name: "온두라스",        flag: "🇭🇳", region: "중미" },
  { code: "SV", name: "엘살바도르",      flag: "🇸🇻", region: "중미" },
  { code: "NI", name: "니카라과",        flag: "🇳🇮", region: "중미" },
  { code: "CU", name: "쿠바",            flag: "🇨🇺", region: "중미" },

  // ── 북미 ──────────────────────────────────────────────────────
  { code: "US", name: "미국",            flag: "🇺🇸", region: "북미" },

  // ── 서유럽·오세아니아 (주요국) ────────────────────────────────
  { code: "GB", name: "영국",            flag: "🇬🇧", region: "유럽" },
  { code: "FR", name: "프랑스",          flag: "🇫🇷", region: "유럽" },
  { code: "DE", name: "독일",            flag: "🇩🇪", region: "유럽" },
  { code: "AU", name: "호주",            flag: "🇦🇺", region: "오세아니아" },
];

export const COUNTRY_MAP = Object.fromEntries(ALL_COUNTRIES.map((c) => [c.code, c]));

const REGION_EN: Record<string, string> = {
  "유럽": "Europe", "중동": "Middle East", "동아시아": "East Asia",
  "동남아": "Southeast Asia", "남아시아": "South Asia", "중앙아시아": "Central Asia",
  "아프리카": "Africa", "남미": "South America", "중미": "Central America", "북미": "North America", "오세아니아": "Oceania",
};

/** 언어에 맞는 국가명 반환. 영어는 Intl.DisplayNames API 사용 */
export function getCountryName(code: string, lang: string): string {
  if (lang === "en") {
    try {
      return new Intl.DisplayNames(["en"], { type: "region" }).of(code) || COUNTRY_MAP[code]?.name || code;
    } catch {
      return COUNTRY_MAP[code]?.name || code;
    }
  }
  return COUNTRY_MAP[code]?.name || code;
}

/** 언어에 맞는 지역명 반환 */
export function getRegionName(region: string, lang: string): string {
  if (lang === "en") return REGION_EN[region] || region;
  return region;
}

/** 국가코드로 국기 이모지 반환 */
export function getFlag(code: string): string {
  return COUNTRY_MAP[code]?.flag ||
    String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1F1E6 + c.charCodeAt(0) - 65));
}

/** 국가별 고정 중심 좌표 (수도/중심점 기준) — 지도 마커 위치 안정화용 */
export const COUNTRY_CENTERS: Record<string, { lat: number; lon: number }> = {
  // 유럽·코카서스
  UA: { lat: 50.45, lon: 30.52 },  // 키이우
  RU: { lat: 55.75, lon: 37.62 },  // 모스크바
  BY: { lat: 53.90, lon: 27.57 },  // 민스크
  MD: { lat: 47.01, lon: 28.86 },  // 키시너우
  RS: { lat: 44.79, lon: 20.47 },  // 베오그라드
  XK: { lat: 42.66, lon: 21.17 },  // 프리슈티나
  BA: { lat: 43.86, lon: 18.41 },  // 사라예보
  GE: { lat: 41.69, lon: 44.80 },  // 트빌리시
  AM: { lat: 40.18, lon: 44.51 },  // 예레반
  AZ: { lat: 40.41, lon: 49.87 },  // 바쿠
  GB: { lat: 51.51, lon: -0.13 },  // 런던
  FR: { lat: 48.86, lon: 2.35 },   // 파리
  DE: { lat: 52.52, lon: 13.41 },  // 베를린
  // 중동
  PS: { lat: 31.90, lon: 35.20 },  // 라말라
  IL: { lat: 31.77, lon: 35.22 },  // 예루살렘
  IR: { lat: 35.69, lon: 51.39 },  // 테헤란
  IQ: { lat: 33.31, lon: 44.37 },  // 바그다드
  SY: { lat: 33.51, lon: 36.29 },  // 다마스쿠스
  LB: { lat: 33.89, lon: 35.50 },  // 베이루트
  YE: { lat: 15.37, lon: 44.21 },  // 사나
  SA: { lat: 24.71, lon: 46.68 },  // 리야드
  TR: { lat: 39.93, lon: 32.85 },  // 앙카라
  EG: { lat: 30.04, lon: 31.24 },  // 카이로
  JO: { lat: 31.95, lon: 35.93 },  // 암만
  AE: { lat: 24.45, lon: 54.65 },  // 아부다비
  QA: { lat: 25.29, lon: 51.53 },  // 도하
  // 동아시아
  KP: { lat: 39.02, lon: 125.75 }, // 평양
  KR: { lat: 37.57, lon: 126.98 }, // 서울
  TW: { lat: 25.03, lon: 121.57 }, // 타이베이
  CN: { lat: 39.90, lon: 116.40 }, // 베이징
  JP: { lat: 35.68, lon: 139.69 }, // 도쿄
  MN: { lat: 47.92, lon: 106.91 }, // 울란바토르
  // 동남아
  MM: { lat: 19.76, lon: 96.07 },  // 네피도
  PH: { lat: 14.60, lon: 120.98 }, // 마닐라
  VN: { lat: 21.03, lon: 105.85 }, // 하노이
  ID: { lat: -6.21, lon: 106.85 }, // 자카르타
  TH: { lat: 13.76, lon: 100.50 }, // 방콕
  MY: { lat: 3.14, lon: 101.69 },  // 쿠알라룸푸르
  KH: { lat: 11.56, lon: 104.93 }, // 프놈펜
  LA: { lat: 17.97, lon: 102.63 }, // 비엔티안
  // 남아시아
  PK: { lat: 33.69, lon: 73.04 },  // 이슬라마바드
  AF: { lat: 34.53, lon: 69.17 },  // 카불
  IN: { lat: 28.61, lon: 77.21 },  // 뉴델리
  BD: { lat: 23.81, lon: 90.41 },  // 다카
  LK: { lat: 6.93, lon: 79.85 },   // 콜롬보
  NP: { lat: 27.72, lon: 85.32 },  // 카트만두
  // 중앙아시아
  KZ: { lat: 51.17, lon: 71.43 },  // 아스타나
  TJ: { lat: 38.56, lon: 68.77 },  // 두샨베
  KG: { lat: 42.87, lon: 74.59 },  // 비슈케크
  UZ: { lat: 41.30, lon: 69.28 },  // 타슈켄트
  TM: { lat: 37.95, lon: 58.38 },  // 아시가바트
  // 아프리카
  SD: { lat: 15.59, lon: 32.53 },  // 하르툼
  SS: { lat: 4.85, lon: 31.60 },   // 주바
  ET: { lat: 9.02, lon: 38.75 },   // 아디스아바바
  SO: { lat: 2.05, lon: 45.32 },   // 모가디슈
  ER: { lat: 15.34, lon: 38.93 },  // 아스마라
  LY: { lat: 32.90, lon: 13.18 },  // 트리폴리
  ML: { lat: 12.65, lon: -8.00 },  // 바마코
  BF: { lat: 12.37, lon: -1.52 },  // 와가두구
  NE: { lat: 13.51, lon: 2.11 },   // 니아메
  TD: { lat: 12.11, lon: 15.04 },  // 은자메나
  NG: { lat: 9.06, lon: 7.49 },    // 아부자
  CM: { lat: 3.87, lon: 11.52 },   // 야운데
  CF: { lat: 4.36, lon: 18.56 },   // 방기
  CD: { lat: -4.32, lon: 15.31 },  // 킨샤사
  CG: { lat: -4.27, lon: 15.28 },  // 브라자빌
  MZ: { lat: -25.97, lon: 32.57 }, // 마푸투
  ZW: { lat: -17.83, lon: 31.05 }, // 하라레
  MA: { lat: 34.02, lon: -6.84 },  // 라바트
  DZ: { lat: 36.75, lon: 3.04 },   // 알제
  TN: { lat: 36.81, lon: 10.17 },  // 튀니스
  GN: { lat: 9.64, lon: -13.58 },  // 코나크리
  GW: { lat: 11.86, lon: -15.60 }, // 비사우
  SL: { lat: 8.48, lon: -13.23 },  // 프리타운
  MR: { lat: 18.09, lon: -15.98 }, // 누악쇼트
  // 남미
  VE: { lat: 10.49, lon: -66.88 }, // 카라카스
  HT: { lat: 18.54, lon: -72.34 }, // 포르토프랭스
  CO: { lat: 4.71, lon: -74.07 },  // 보고타
  EC: { lat: -0.18, lon: -78.47 }, // 키토
  PE: { lat: -12.05, lon: -77.04 },// 리마
  BO: { lat: -16.50, lon: -68.15 },// 라파스
  BR: { lat: -15.79, lon: -47.88 },// 브라질리아
  // 중미
  MX: { lat: 19.43, lon: -99.13 }, // 멕시코시티
  GT: { lat: 14.63, lon: -90.51 }, // 과테말라시티
  HN: { lat: 14.07, lon: -87.19 }, // 테구시갈파
  SV: { lat: 13.69, lon: -89.19 }, // 산살바도르
  NI: { lat: 12.11, lon: -86.27 }, // 마나과
  CU: { lat: 23.11, lon: -82.37 }, // 아바나
  // 북미·오세아니아
  US: { lat: 38.91, lon: -77.04 }, // 워싱턴DC
  AU: { lat: -35.28, lon: 149.13 },// 캔버라
};

/** 긴장도 계산 대상 전체 국가 (분쟁·갈등·지정학적 위험 기준) */
export const ALL_MONITORED_COUNTRIES = [
  // 주요국
  "US", "GB", "FR", "DE", "JP", "AU",
  // 유럽·코카서스
  "UA", "RU", "BY", "MD", "RS", "XK", "BA", "GE", "AM", "AZ",
  // 중동
  "PS", "IL", "IR", "IQ", "SY", "LB", "YE", "SA", "TR", "EG",
  // 동아시아
  "KP", "TW", "CN", "KR",
  // 동남아
  "MM", "PH", "VN", "ID", "TH",
  // 남아시아·중앙아시아
  "PK", "AF", "IN", "BD", "KZ", "TJ", "KG",
  // 아프리카
  "SD", "SS", "ET", "SO", "LY", "ML", "BF", "NE", "NG", "CM",
  "CF", "CD", "MZ", "TD", "GN", "ER", "DZ", "TN", "MA",
  // 아메리카
  "VE", "HT", "CO", "EC", "MX", "NI", "CU", "GT", "HN",
];
