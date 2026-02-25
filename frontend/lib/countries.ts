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
