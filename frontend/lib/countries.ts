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

  // ── 유럽 (추가) ──────────────────────────────────────────────
  { code: "IE", name: "아일랜드",        flag: "🇮🇪", region: "유럽" },
  { code: "IS", name: "아이슬란드",      flag: "🇮🇸", region: "유럽" },
  { code: "LU", name: "룩셈부르크",      flag: "🇱🇺", region: "유럽" },
  { code: "LI", name: "리히텐슈타인",    flag: "🇱🇮", region: "유럽" },
  { code: "MC", name: "모나코",          flag: "🇲🇨", region: "유럽" },
  { code: "MT", name: "몰타",            flag: "🇲🇹", region: "유럽" },
  { code: "AL", name: "알바니아",        flag: "🇦🇱", region: "유럽" },
  { code: "MK", name: "북마케도니아",    flag: "🇲🇰", region: "유럽" },
  { code: "ME", name: "몬테네그로",      flag: "🇲🇪", region: "유럽" },
  { code: "SK", name: "슬로바키아",      flag: "🇸🇰", region: "유럽" },
  { code: "SI", name: "슬로베니아",      flag: "🇸🇮", region: "유럽" },
  { code: "BG", name: "불가리아",        flag: "🇧🇬", region: "유럽" },
  { code: "LT", name: "리투아니아",      flag: "🇱🇹", region: "유럽" },
  { code: "LV", name: "라트비아",        flag: "🇱🇻", region: "유럽" },
  { code: "CY", name: "키프로스",        flag: "🇨🇾", region: "유럽" },
  { code: "AD", name: "안도라",          flag: "🇦🇩", region: "유럽" },
  { code: "SM", name: "산마리노",        flag: "🇸🇲", region: "유럽" },
  { code: "IT", name: "이탈리아",        flag: "🇮🇹", region: "유럽" },
  { code: "ES", name: "스페인",          flag: "🇪🇸", region: "유럽" },
  { code: "PT", name: "포르투갈",        flag: "🇵🇹", region: "유럽" },
  { code: "NL", name: "네덜란드",        flag: "🇳🇱", region: "유럽" },
  { code: "BE", name: "벨기에",          flag: "🇧🇪", region: "유럽" },
  { code: "SE", name: "스웨덴",          flag: "🇸🇪", region: "유럽" },
  { code: "NO", name: "노르웨이",        flag: "🇳🇴", region: "유럽" },
  { code: "DK", name: "덴마크",          flag: "🇩🇰", region: "유럽" },
  { code: "CH", name: "스위스",          flag: "🇨🇭", region: "유럽" },
  { code: "AT", name: "오스트리아",      flag: "🇦🇹", region: "유럽" },
  { code: "GR", name: "그리스",          flag: "🇬🇷", region: "유럽" },
  { code: "CZ", name: "체코",            flag: "🇨🇿", region: "유럽" },
  { code: "HU", name: "헝가리",          flag: "🇭🇺", region: "유럽" },
  { code: "HR", name: "크로아티아",      flag: "🇭🇷", region: "유럽" },
  { code: "FI", name: "핀란드",          flag: "🇫🇮", region: "유럽" },
  { code: "PL", name: "폴란드",          flag: "🇵🇱", region: "유럽" },
  { code: "RO", name: "루마니아",        flag: "🇷🇴", region: "유럽" },
  { code: "EE", name: "에스토니아",      flag: "🇪🇪", region: "유럽" },

  // ── 북미 (추가) ──────────────────────────────────────────────
  { code: "CA", name: "캐나다",          flag: "🇨🇦", region: "북미" },

  // ── 중동 (추가) ──────────────────────────────────────────────
  { code: "BH", name: "바레인",          flag: "🇧🇭", region: "중동" },
  { code: "KW", name: "쿠웨이트",        flag: "🇰🇼", region: "중동" },
  { code: "OM", name: "오만",            flag: "🇴🇲", region: "중동" },

  // ── 아프리카 (추가) ──────────────────────────────────────────
  { code: "AO", name: "앙골라",          flag: "🇦🇴", region: "아프리카" },
  { code: "BJ", name: "베냉",            flag: "🇧🇯", region: "아프리카" },
  { code: "BW", name: "보츠와나",        flag: "🇧🇼", region: "아프리카" },
  { code: "BI", name: "부룬디",          flag: "🇧🇮", region: "아프리카" },
  { code: "CV", name: "카보베르데",      flag: "🇨🇻", region: "아프리카" },
  { code: "DJ", name: "지부티",          flag: "🇩🇯", region: "아프리카" },
  { code: "GQ", name: "적도기니",        flag: "🇬🇶", region: "아프리카" },
  { code: "GA", name: "가봉",            flag: "🇬🇦", region: "아프리카" },
  { code: "GM", name: "감비아",          flag: "🇬🇲", region: "아프리카" },
  { code: "KE", name: "케냐",            flag: "🇰🇪", region: "아프리카" },
  { code: "LS", name: "레소토",          flag: "🇱🇸", region: "아프리카" },
  { code: "LR", name: "라이베리아",      flag: "🇱🇷", region: "아프리카" },
  { code: "MG", name: "마다가스카르",    flag: "🇲🇬", region: "아프리카" },
  { code: "MW", name: "말라위",          flag: "🇲🇼", region: "아프리카" },
  { code: "MU", name: "모리셔스",        flag: "🇲🇺", region: "아프리카" },
  { code: "NA", name: "나미비아",        flag: "🇳🇦", region: "아프리카" },
  { code: "RW", name: "르완다",          flag: "🇷🇼", region: "아프리카" },
  { code: "ST", name: "상투메프린시페",  flag: "🇸🇹", region: "아프리카" },
  { code: "SC", name: "세이셸",          flag: "🇸🇨", region: "아프리카" },
  { code: "ZA", name: "남아공",          flag: "🇿🇦", region: "아프리카" },
  { code: "SZ", name: "에스와티니",      flag: "🇸🇿", region: "아프리카" },
  { code: "TG", name: "토고",            flag: "🇹🇬", region: "아프리카" },
  { code: "TZ", name: "탄자니아",        flag: "🇹🇿", region: "아프리카" },
  { code: "UG", name: "우간다",          flag: "🇺🇬", region: "아프리카" },
  { code: "ZM", name: "잠비아",          flag: "🇿🇲", region: "아프리카" },
  { code: "KM", name: "코모로",          flag: "🇰🇲", region: "아프리카" },
  { code: "CI", name: "코트디부아르",    flag: "🇨🇮", region: "아프리카" },
  { code: "SN", name: "세네갈",          flag: "🇸🇳", region: "아프리카" },
  { code: "GH", name: "가나",            flag: "🇬🇭", region: "아프리카" },

  // ── 남미·중미·카리브 (추가) ──────────────────────────────────
  { code: "CR", name: "코스타리카",          flag: "🇨🇷", region: "중미" },
  { code: "DO", name: "도미니카공화국",      flag: "🇩🇴", region: "중미" },
  { code: "GY", name: "가이아나",            flag: "🇬🇾", region: "남미" },
  { code: "JM", name: "자메이카",            flag: "🇯🇲", region: "중미" },
  { code: "PA", name: "파나마",              flag: "🇵🇦", region: "중미" },
  { code: "PY", name: "파라과이",            flag: "🇵🇾", region: "남미" },
  { code: "SR", name: "수리남",              flag: "🇸🇷", region: "남미" },
  { code: "TT", name: "트리니다드토바고",    flag: "🇹🇹", region: "중미" },
  { code: "UY", name: "우루과이",            flag: "🇺🇾", region: "남미" },
  { code: "CL", name: "칠레",               flag: "🇨🇱", region: "남미" },
  { code: "AR", name: "아르헨티나",          flag: "🇦🇷", region: "남미" },
  { code: "AG", name: "앤티가바부다",        flag: "🇦🇬", region: "중미" },
  { code: "BB", name: "바베이도스",          flag: "🇧🇧", region: "중미" },
  { code: "BS", name: "바하마",              flag: "🇧🇸", region: "중미" },
  { code: "BZ", name: "벨리즈",              flag: "🇧🇿", region: "중미" },
  { code: "DM", name: "도미니카",            flag: "🇩🇲", region: "중미" },
  { code: "GD", name: "그레나다",            flag: "🇬🇩", region: "중미" },
  { code: "KN", name: "세인트키츠네비스",    flag: "🇰🇳", region: "중미" },
  { code: "LC", name: "세인트루시아",        flag: "🇱🇨", region: "중미" },
  { code: "VC", name: "세인트빈센트그레나딘", flag: "🇻🇨", region: "중미" },

  // ── 아시아 (추가) ────────────────────────────────────────────
  { code: "BN", name: "브루나이",        flag: "🇧🇳", region: "동남아" },
  { code: "BT", name: "부탄",            flag: "🇧🇹", region: "남아시아" },
  { code: "MV", name: "몰디브",          flag: "🇲🇻", region: "남아시아" },
  { code: "TL", name: "동티모르",        flag: "🇹🇱", region: "동남아" },
  { code: "SG", name: "싱가포르",        flag: "🇸🇬", region: "동남아" },

  // ── 오세아니아 (추가) ────────────────────────────────────────
  { code: "FJ", name: "피지",            flag: "🇫🇯", region: "오세아니아" },
  { code: "KI", name: "키리바시",        flag: "🇰🇮", region: "오세아니아" },
  { code: "MH", name: "마셜제도",        flag: "🇲🇭", region: "오세아니아" },
  { code: "FM", name: "미크로네시아",    flag: "🇫🇲", region: "오세아니아" },
  { code: "NR", name: "나우루",          flag: "🇳🇷", region: "오세아니아" },
  { code: "PW", name: "팔라우",          flag: "🇵🇼", region: "오세아니아" },
  { code: "PG", name: "파푸아뉴기니",    flag: "🇵🇬", region: "오세아니아" },
  { code: "WS", name: "사모아",          flag: "🇼🇸", region: "오세아니아" },
  { code: "SB", name: "솔로몬제도",      flag: "🇸🇧", region: "오세아니아" },
  { code: "TO", name: "통가",            flag: "🇹🇴", region: "오세아니아" },
  { code: "TV", name: "투발루",          flag: "🇹🇻", region: "오세아니아" },
  { code: "VU", name: "바누아투",        flag: "🇻🇺", region: "오세아니아" },
  { code: "NZ", name: "뉴질랜드",        flag: "🇳🇿", region: "오세아니아" },
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
  // ── 유럽 (추가) ──
  IE: { lat: 53.35, lon: -6.26 },  // 더블린
  IS: { lat: 64.15, lon: -21.94 }, // 레이캬비크
  LU: { lat: 49.61, lon: 6.13 },   // 룩셈부르크시
  LI: { lat: 47.14, lon: 9.52 },   // 파두츠
  MC: { lat: 43.73, lon: 7.42 },   // 모나코
  MT: { lat: 35.90, lon: 14.51 },  // 발레타
  AL: { lat: 41.33, lon: 19.82 },  // 티라나
  MK: { lat: 41.99, lon: 21.43 },  // 스코페
  ME: { lat: 42.44, lon: 19.26 },  // 포드고리차
  SK: { lat: 48.15, lon: 17.11 },  // 브라티슬라바
  SI: { lat: 46.06, lon: 14.51 },  // 류블랴나
  BG: { lat: 42.70, lon: 23.32 },  // 소피아
  LT: { lat: 54.69, lon: 25.28 },  // 빌뉴스
  LV: { lat: 56.95, lon: 24.11 },  // 리가
  CY: { lat: 35.17, lon: 33.36 },  // 니코시아
  AD: { lat: 42.51, lon: 1.52 },   // 안도라라베야
  SM: { lat: 43.94, lon: 12.45 },  // 산마리노시
  IT: { lat: 41.90, lon: 12.50 },  // 로마
  ES: { lat: 40.42, lon: -3.70 },  // 마드리드
  PT: { lat: 38.72, lon: -9.14 },  // 리스본
  NL: { lat: 52.37, lon: 4.90 },   // 암스테르담
  BE: { lat: 50.85, lon: 4.35 },   // 브뤼셀
  SE: { lat: 59.33, lon: 18.07 },  // 스톡홀름
  NO: { lat: 59.91, lon: 10.75 },  // 오슬로
  DK: { lat: 55.68, lon: 12.57 },  // 코펜하겐
  CH: { lat: 46.95, lon: 7.45 },   // 베른
  AT: { lat: 48.21, lon: 16.37 },  // 빈
  GR: { lat: 37.98, lon: 23.73 },  // 아테네
  CZ: { lat: 50.08, lon: 14.42 },  // 프라하
  HU: { lat: 47.50, lon: 19.04 },  // 부다페스트
  HR: { lat: 45.81, lon: 15.98 },  // 자그레브
  FI: { lat: 60.17, lon: 24.94 },  // 헬싱키
  PL: { lat: 52.23, lon: 21.01 },  // 바르샤바
  RO: { lat: 44.43, lon: 26.10 },  // 부쿠레슈티
  EE: { lat: 59.44, lon: 24.75 },  // 탈린
  // ── 북미 (추가) ──
  CA: { lat: 45.42, lon: -75.70 }, // 오타와
  // ── 중동 (추가) ──
  BH: { lat: 26.23, lon: 50.58 },  // 마나마
  KW: { lat: 29.38, lon: 47.99 },  // 쿠웨이트시티
  OM: { lat: 23.59, lon: 58.54 },  // 무스카트
  // ── 아프리카 (추가) ──
  AO: { lat: -8.84, lon: 13.23 },  // 루안다
  BJ: { lat: 6.50, lon: 2.60 },    // 포르토노보
  BW: { lat: -24.65, lon: 25.91 }, // 가보로네
  BI: { lat: -3.38, lon: 29.36 },  // 기테가
  CV: { lat: 14.93, lon: -23.51 }, // 프라이아
  DJ: { lat: 11.59, lon: 43.15 },  // 지부티시
  GQ: { lat: 3.75, lon: 8.78 },    // 말라보
  GA: { lat: 0.39, lon: 9.45 },    // 리브르빌
  GM: { lat: 13.45, lon: -16.58 }, // 반줄
  KE: { lat: -1.29, lon: 36.82 },  // 나이로비
  LS: { lat: -29.31, lon: 27.48 }, // 마세루
  LR: { lat: 6.30, lon: -10.80 },  // 먼로비아
  MG: { lat: -18.88, lon: 47.51 }, // 안타나나리보
  MW: { lat: -13.97, lon: 33.79 }, // 릴롱궤
  MU: { lat: -20.16, lon: 57.50 }, // 포트루이스
  NA: { lat: -22.56, lon: 17.08 }, // 빈트후크
  RW: { lat: -1.94, lon: 29.87 },  // 키갈리
  ST: { lat: 0.34, lon: 6.73 },    // 상투메
  SC: { lat: -4.62, lon: 55.45 },  // 빅토리아
  ZA: { lat: -25.75, lon: 28.19 }, // 프리토리아
  SZ: { lat: -26.31, lon: 31.13 }, // 음바바네
  TG: { lat: 6.17, lon: 1.23 },    // 로메
  TZ: { lat: -6.16, lon: 35.75 },  // 도도마
  UG: { lat: 0.35, lon: 32.58 },   // 캄팔라
  ZM: { lat: -15.39, lon: 28.32 }, // 루사카
  KM: { lat: -11.70, lon: 43.26 }, // 모로니
  CI: { lat: 6.85, lon: -5.29 },   // 야무수크로
  SN: { lat: 14.69, lon: -17.44 }, // 다카르
  GH: { lat: 5.56, lon: -0.19 },   // 아크라
  // ── 남미·중미·카리브 (추가) ──
  CR: { lat: 9.93, lon: -84.08 },  // 산호세
  DO: { lat: 18.47, lon: -69.90 }, // 산토도밍고
  GY: { lat: 6.80, lon: -58.16 },  // 조지타운
  JM: { lat: 18.00, lon: -76.79 }, // 킹스턴
  PA: { lat: 8.98, lon: -79.52 },  // 파나마시티
  PY: { lat: -25.26, lon: -57.58 },// 아순시온
  SR: { lat: 5.87, lon: -55.17 },  // 파라마리보
  TT: { lat: 10.66, lon: -61.51 }, // 포트오브스페인
  UY: { lat: -34.88, lon: -56.17 },// 몬테비데오
  CL: { lat: -33.45, lon: -70.67 },// 산티아고
  AR: { lat: -34.60, lon: -58.38 },// 부에노스아이레스
  AG: { lat: 17.12, lon: -61.85 }, // 세인트존스
  BB: { lat: 13.10, lon: -59.61 }, // 브리지타운
  BS: { lat: 25.05, lon: -77.35 }, // 나소
  BZ: { lat: 17.25, lon: -88.77 }, // 벨모판
  DM: { lat: 15.30, lon: -61.39 }, // 로조
  GD: { lat: 12.05, lon: -61.75 }, // 세인트조지스
  KN: { lat: 17.30, lon: -62.72 }, // 바스테르
  LC: { lat: 14.01, lon: -60.99 }, // 캐스트리스
  VC: { lat: 13.16, lon: -61.23 }, // 킹스타운
  // ── 아시아 (추가) ──
  BN: { lat: 4.93, lon: 114.95 },  // 반다르스리브가완
  BT: { lat: 27.47, lon: 89.64 },  // 팀부
  MV: { lat: 4.18, lon: 73.51 },   // 말레
  TL: { lat: -8.56, lon: 125.57 }, // 딜리
  SG: { lat: 1.35, lon: 103.82 },  // 싱가포르
  // ── 오세아니아 (추가) ──
  FJ: { lat: -18.14, lon: 178.44 },// 수바
  KI: { lat: 1.45, lon: 173.00 },  // 타라와
  MH: { lat: 7.09, lon: 171.38 },  // 마주로
  FM: { lat: 6.92, lon: 158.16 },  // 팔리키르
  NR: { lat: -0.55, lon: 166.92 }, // 야렌
  PW: { lat: 7.50, lon: 134.62 },  // 응에룰무드
  PG: { lat: -6.21, lon: 155.96 }, // 포트모르즈비
  WS: { lat: -13.83, lon: -171.76 },// 아피아
  SB: { lat: -9.43, lon: 160.03 }, // 호니아라
  TO: { lat: -21.21, lon: -175.20 },// 누쿠알로파
  TV: { lat: -8.52, lon: 179.20 }, // 푸나푸티
  VU: { lat: -17.73, lon: 168.32 },// 포트빌라
  NZ: { lat: -41.29, lon: 174.78 },// 웰링턴
};

/** 긴장도 계산 대상 전체 국가 — ALL_COUNTRIES 에서 자동 생성 */
export const ALL_MONITORED_COUNTRIES = ALL_COUNTRIES.map(c => c.code);
