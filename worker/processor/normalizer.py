"""
EventNormalizer: RawEvent 텍스트 → NormalizedEvent 변환.

처리 순서:
1. 언어 감지 (langdetect)
2. Topic 분류 (키워드 매칭)
3. Severity 계산 (0~100)
4. Confidence 계산 (source tier 기반)
5. dedup_key 생성 (정규화 텍스트 MD5)
6. Geo 정보 추출 (국가 키워드 → 좌표 → geohash5)
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Topic 분류 키워드 ────────────────────────────────────────────────────────

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "conflict": [
        # 직접 전투
        "attack", "missile", "bomb", "explosion", "airstrike", "artillery",
        "troops", "military", "war", "combat", "offensive", "drone", "strike",
        "killed", "casualties", "ceasefire", "battle", "forces", "shelling",
        "rocket", "mortar", "tank", "infantry", "navy", "airforce",
        # 추가: 분쟁/전쟁 일반
        "conflict", "warfare", "hostilities", "armed",
        "invasion", "invade", "invading", "invades",
        "occupation", "occupied", "occupying",
        "frontline", "front line", "war zone", "warzone",
        "siege", "ambush", "sniper", "gunfire", "firefight",
        # 추가: 병력/무기
        "soldier", "soldiers", "fighter", "fighters", "combatant",
        "weapon", "weapons", "arms", "nuclear", "warhead",
        "nuclear weapon", "nuclear weapons", "ballistic",
        "arms transfer", "arms supply", "weapons transfer",
        "military aid", "military support", "military assistance",
        "military operation", "military action", "military force",
        "armed forces", "armed conflict", "armed group",
        "deployment", "deployed", "mobilization", "reinforcements",
        "war effort", "prolong", "prolonging",
    ],
    "terror": [
        "terror", "terrorist", "hostage", "isis", "al-qaeda", "extremist",
        "jihadist", "suicide bomb", "attack on civilians", "beheading",
        "cartel", "drug lord", "drug trafficking", "organized crime", "gang",
        "assassination", "murder", "shooting", "stabbing", "kidnapping",
    ],
    "coup": [
        "coup", "overthrow", "junta", "seized power", "military takeover",
        "martial law", "emergency decree", "suspended constitution",
        "deposed", "detained president",
        "arrested president", "arrested opposition", "imprisoned leader",
        "political prisoner", "opposition leader arrested", "former president arrested",
        "ex-president", "former leader arrested",
    ],
    "sanctions": [
        "sanctions", "embargo", "trade ban", "export control", "asset freeze",
        "blacklist", "tariff", "economic pressure", "restriction",
        "sanctioned", "penalty", "penalties", "sanctioning",
    ],
    "cyber": [
        "cyberattack", "hacked", "ransomware", "malware", "ddos",
        "data breach", "cyber", "phishing", "vulnerability", "exploit",
    ],
    "protest": [
        "protest", "demonstration", "rally", "riot", "crowd", "march",
        "unrest", "strike", "uprising", "demonstrators",
    ],
    "diplomacy": [
        "diplomat", "embassy", "treaty", "agreement", "summit",
        "negotiation", "peace deal", "sanctions lifted", "talks",
        "president", "minister", "government", "election", "court", "supreme court",
        "ruling", "law", "policy", "administration", "parliament",
        "national assembly", "legislature", "congress", "senate",
        "opposition", "political crisis", "arrested", "detained",
        # 외교/국제관계 추가
        "foreign affairs", "foreign minister", "foreign ministry",
        "international law", "diplomatic", "bilateral", "multilateral",
        "ending war", "end the war", "peace process", "peace effort",
        "war crimes", "accountability", "ceasefire talks",
        "rapid support forces", "rsf", "paramilitary",
        "flouting", "accuses", "accused of",
    ],
    "maritime": [
        "naval", "ship", "vessel", "strait", "blockade", "coast guard",
        "maritime", "submarine", "fleet", "tanker",
        # 이주/난민 해상 사망 (지중해·에게해·홍해 등)
        "mediterranean", "aegean", "english channel", "migrant", "migrants",
        "refugee", "refugees", "drowned", "drowning", "crossing",
        "boat capsized", "capsized", "shipwreck", "rescue at sea",
        "died trying to cross", "crossing deaths", "smuggled",
    ],
    "disaster": [
        "flood", "flooding", "floods", "flash flood",
        "earthquake", "quake", "tremor", "aftershock",
        "tsunami", "typhoon", "hurricane", "cyclone", "tornado",
        "wildfire", "bushfire", "forest fire",
        "drought", "famine", "landslide", "mudslide", "avalanche",
        "eruption", "volcano", "volcanic",
        "storm", "heavy rain", "rainfall", "monsoon",
        "natural disaster", "catastrophe",
        "evacuation", "rescue operation", "emergency declared",
        "missing persons", "disaster relief",
    ],
    "health": [
        # 전염병·감염
        "outbreak", "epidemic", "pandemic", "infection", "infectious",
        "measles", "cholera", "ebola", "mpox", "monkeypox", "dengue",
        "malaria", "tuberculosis", "polio", "typhoid", "hepatitis",
        "covid", "coronavirus", "influenza", "flu outbreak",
        # 보건 기관·조치
        "public health", "health ministry", "health alert", "health emergency",
        "quarantine", "lockdown", "contact tracing", "vaccination campaign",
        "world health organization", "who alert", "cdc alert",
        "disease outbreak", "community transmission", "health crisis",
        # 사망·확산
        "cases confirmed", "deaths from", "hospitalized", "health workers",
        "health authorities", "spreading", "contagious", "contagion",
    ],
}

# ── Severity 기본값 ──────────────────────────────────────────────────────────

TOPIC_BASE_SEVERITY: dict[str, int] = {
    "conflict":  55,
    "terror":    60,
    "coup":      65,
    "sanctions": 45,
    "cyber":     40,
    "protest":   35,
    "diplomacy": 30,
    "maritime":  50,
    "disaster":  50,
    "health":    40,
    "unknown":   20,
}

# ── Severity 보정 키워드 ─────────────────────────────────────────────────────

SEVERITY_UP: list[tuple[str, int]] = [
    # 사상자
    ("killed", 10), ("dead", 10), ("casualties", 8), ("deaths", 10),
    ("wounded", 6), ("injured", 5), ("massacre", 15), ("genocide", 20),
    # 무기/공격
    ("airstrike", 8), ("missile strike", 10), ("explosion", 7), ("bomb", 6),
    ("rocket", 6), ("artillery", 7), ("drone strike", 8), ("shelling", 7),
    ("chemical weapon", 18), ("biological weapon", 18), ("nuclear", 20),
    # 인프라
    ("power grid", 8), ("hospital", 6), ("school", 5), ("market", 4),
    ("dam", 8), ("nuclear plant", 15), ("water supply", 7),
    # 규모/범위
    ("massive", 6), ("large-scale", 6), ("widespread", 5), ("unprecedented", 8),
    ("catastrophic", 10), ("devastating", 8), ("major offensive", 10),
    # 정치/법
    ("martial law", 15), ("mobilization", 12), ("emergency", 6),
    ("coup", 8), ("overthrow", 10), ("seized power", 12),
    # 긴박성
    ("escalating", 5), ("intensifying", 5), ("imminent", 6), ("erupted", 6),
    ("siege", 8), ("surrounded", 6), ("blockade", 7), ("encircled", 7),
    # 민간인
    ("civilian", 5), ("capital", 4), ("city center", 4),
]

SEVERITY_DOWN: list[tuple[str, int]] = [
    # 불확실성
    ("alleged", -8), ("unconfirmed", -10), ("rumor", -12),
    ("reportedly", -5), ("claims", -6), ("possibly", -7),
    ("denied", -5), ("false alarm", -15), ("hoax", -15),
    # 완화
    ("ceasefire", -10), ("truce", -10), ("peace deal", -12),
    ("de-escalat", -10), ("withdrawal", -7), ("retreat", -5),
    ("diplomatic solution", -10), ("agreement reached", -8),
    # 소규모
    ("minor", -6), ("small-scale", -6), ("limited", -5), ("contained", -5),
    ("isolated incident", -8), ("under control", -8),
]

# ── 사상자 수 기반 추가 보정 ────────────────────────────────────────────────
# 숫자 + 사망/부상 패턴 → 규모별 보정값

_CASUALTY_PATTERNS: list[tuple[re.Pattern, float, float]] = [
    # 숫자 앞: "150 killed", "150 people dead", "150 have died"
    (re.compile(r'\b(\d[\d,]*)\s*(?:people\s+)?(?:have\s+)?(?:killed|dead|died)\b', re.I), 1.0, 0),
    (re.compile(r'\b(\d[\d,]*)\s*(?:people\s+)?(?:have\s+)?(?:been\s+killed|been\s+dead|perished|drowned)\b', re.I), 1.0, 0),
    (re.compile(r'\b(\d[\d,]*)\s*(?:people\s+)?deaths?\b', re.I), 1.0, 0),
    (re.compile(r'\b(\d[\d,]*)\s*(?:people\s+)?(?:wounded|injured|hurt)\b', re.I), 0, 0.4),
    (re.compile(r'\b(\d[\d,]*)\s*casualties\b', re.I), 0.6, 0.3),
    # 동사 뒤: "kills 5", "killing at least 20", "left 30 dead"
    (re.compile(r'\bkill(?:s|ed|ing)\s+(?:at\s+least\s+)?(\d[\d,]*)', re.I), 1.0, 0),
    (re.compile(r'\bclaim(?:s|ed|ing)\s+(?:at\s+least\s+)?(\d[\d,]*)\s*(?:lives|people|dead)', re.I), 1.0, 0),
    (re.compile(r'\bleft\s+(?:at\s+least\s+)?(\d[\d,]*)\s*(?:people\s+)?(?:dead|killed|injured)', re.I), 1.0, 0),
    # "more than N", "at least N" + 사망 동사
    (re.compile(r'(?:more than|at least|over)\s+(\d[\d,]*)\s*(?:people\s+)?(?:have\s+)?(?:died|drowned|perished|been killed)\b', re.I), 1.0, 0),
]


def _casualty_bonus(text: str) -> int:
    """사상자 수에서 추가 보정값 계산 (최대 +30)."""
    import math
    total_score = 0.0
    for pattern, kill_w, wound_w in _CASUALTY_PATTERNS:
        for m in pattern.finditer(text):
            try:
                n = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            w = kill_w if kill_w else wound_w
            # 로그 스케일: 1명=3, 10명=7, 100명=13, 1000명=20, 10000명=27
            score = w * (3 + math.log10(max(1, n)) * 6)
            total_score += score
    return min(30, int(total_score))

# ── 국가 키워드 → 코드 + 중심 좌표 ─────────────────────────────────────────

COUNTRY_MAP: dict[str, tuple[str, float, float]] = {
    "ukraine": ("UA", 49.0, 31.0),
    "ukrainian": ("UA", 49.0, 31.0),
    "kyiv": ("UA", 50.45, 30.52),
    "kharkiv": ("UA", 49.99, 36.23),
    "mariupol": ("UA", 47.1, 37.55),
    "russia": ("RU", 61.0, 105.0),
    "russian": ("RU", 61.0, 105.0),
    "moscow": ("RU", 55.75, 37.62),
    "israel": ("IL", 31.5, 34.8),
    "israeli": ("IL", 31.5, 34.8),
    "tel aviv": ("IL", 32.08, 34.78),
    "gaza": ("PS", 31.5, 34.47),
    "palestine": ("PS", 31.9, 35.3),
    "palestinian": ("PS", 31.9, 35.3),
    "iran": ("IR", 32.0, 53.0),
    "iranian": ("IR", 32.0, 53.0),
    "tehran": ("IR", 35.69, 51.39),
    "china": ("CN", 35.0, 105.0),
    "chinese": ("CN", 35.0, 105.0),
    "beijing": ("CN", 39.91, 116.39),
    "taiwan": ("TW", 23.7, 121.0),
    "taipei": ("TW", 25.04, 121.51),
    "north korea": ("KP", 40.3, 127.5),
    "pyongyang": ("KP", 39.02, 125.75),
    "south korea": ("KR", 36.5, 127.8),
    "korea": ("KR", 36.5, 127.8),
    "korean": ("KR", 36.5, 127.8),
    "yoon suk-yeol": ("KR", 37.57, 126.98),
    "yoon suk yeol": ("KR", 37.57, 126.98),
    "seoul": ("KR", 37.57, 126.98),
    "syria": ("SY", 35.0, 38.0),
    "damascus": ("SY", 33.51, 36.29),
    "myanmar": ("MM", 17.0, 96.0),
    "sudan": ("SD", 15.0, 32.0),
    "ethiopia": ("ET", 9.0, 38.5),
    "somalia": ("SO", 5.5, 45.5),
    "venezuela": ("VE", 8.0, -66.0),
    "haiti": ("HT", 19.0, -72.0),
    "lebanon": ("LB", 33.9, 35.5),
    "beirut": ("LB", 33.89, 35.5),
    "iraq": ("IQ", 33.0, 44.0),
    "baghdad": ("IQ", 33.33, 44.44),
    "afghanistan": ("AF", 33.0, 65.0),
    "kabul": ("AF", 34.53, 69.17),
    "pakistan": ("PK", 30.0, 70.0),
    "india": ("IN", 20.0, 77.0),
    "taiwan strait": ("TW", 24.0, 119.5),
    "south china sea": ("CN", 15.0, 115.0),
    # ── 주요국 (누락 시 geohash5="00000" 버킷으로 뭉쳐지는 문제 방지) ─────────
    "united states": ("US", 38.0, -97.0),
    "america": ("US", 38.0, -97.0),
    "american": ("US", 38.0, -97.0),
    "washington": ("US", 38.9, -77.0),
    "pentagon": ("US", 38.87, -77.06),
    "white house": ("US", 38.9, -77.0),
    "new york": ("US", 40.71, -74.01),
    "los angeles": ("US", 34.05, -118.24),
    "florida": ("US", 27.99, -81.76),
    "texas": ("US", 31.0, -100.0),
    # ── 미국 주요 인물/기관 키워드 (트럼프 관세 기사가 JP로 분류되는 문제 방지) ──
    "trump": ("US", 38.0, -97.0),
    "donald trump": ("US", 38.0, -97.0),
    "biden": ("US", 38.0, -97.0),
    "joe biden": ("US", 38.0, -97.0),
    "oval office": ("US", 38.9, -77.0),
    "congress": ("US", 38.89, -77.01),
    "senate": ("US", 38.89, -77.01),
    "u.s.": ("US", 38.0, -97.0),
    "u.s. tariff": ("US", 38.0, -97.0),
    "u.s. sanctions": ("US", 38.0, -97.0),
    "federal reserve": ("US", 40.71, -74.01),
    "wall street": ("US", 40.71, -74.01),
    "cia": ("US", 38.95, -77.15),
    "nsa": ("US", 39.1, -76.77),
    "state department": ("US", 38.9, -77.0),
    # ── 관세/무역 맥락: 미국이 주체인 정책 키워드 (긴 구문 우선 매칭으로 JP보다 높은 가중치) ──
    "tariff on all imports": ("US", 38.0, -97.0),
    "levy on all imports": ("US", 38.0, -97.0),
    "levy on imports": ("US", 38.0, -97.0),
    "import tariff": ("US", 38.0, -97.0),
    "reciprocal tariff": ("US", 38.0, -97.0),
    "universal tariff": ("US", 38.0, -97.0),
    "trump tariff": ("US", 38.0, -97.0),
    "trump's tariff": ("US", 38.0, -97.0),
    "white house tariff": ("US", 38.0, -97.0),
    "mar-a-lago": ("US", 26.68, -80.04),
    "doge": ("US", 38.0, -97.0),
    "elon musk": ("US", 38.0, -97.0),
    "marco rubio": ("US", 38.0, -97.0),
    "pete hegseth": ("US", 38.0, -97.0),
    "uk": ("GB", 54.0, -2.0),
    "britain": ("GB", 54.0, -2.0),
    "british": ("GB", 54.0, -2.0),
    "england": ("GB", 52.0, -1.0),
    "london": ("GB", 51.51, -0.13),
    "manchester": ("GB", 53.48, -2.24),
    "scotland": ("GB", 56.49, -4.2),
    "france": ("FR", 46.0, 2.0),
    "french": ("FR", 46.0, 2.0),
    "paris": ("FR", 48.85, 2.35),
    "germany": ("DE", 51.0, 9.0),
    "german": ("DE", 51.0, 9.0),
    "berlin": ("DE", 52.52, 13.4),
    "mexico": ("MX", 23.0, -102.0),
    "mexican": ("MX", 23.0, -102.0),
    "jalisco": ("MX", 20.66, -103.35),
    "australia": ("AU", -27.0, 133.0),
    "australian": ("AU", -27.0, 133.0),
    "japan": ("JP", 35.0, 138.0),
    "japanese": ("JP", 35.0, 138.0),
    "tokyo": ("JP", 35.68, 139.69),
    "brazil": ("BR", -14.0, -51.0),
    "brazilian": ("BR", -14.0, -51.0),
    "saudi arabia": ("SA", 24.0, 45.0),
    "saudi": ("SA", 24.0, 45.0),
    "riyadh": ("SA", 24.69, 46.72),
    "turkey": ("TR", 39.0, 35.0),
    "turkish": ("TR", 39.0, 35.0),
    "ankara": ("TR", 39.93, 32.87),
    "egypt": ("EG", 26.0, 30.0),
    "cairo": ("EG", 30.06, 31.25),
    "nigeria": ("NG", 9.0, 8.0),
    "nigerian": ("NG", 9.0, 8.0),
    "yemen": ("YE", 15.5, 47.5),
    "yemeni": ("YE", 15.5, 47.5),
    "libya": ("LY", 25.0, 17.0),
    "mali": ("ML", 17.0, -4.0),
    "nato": ("BE", 50.88, 4.47),
    "philippines": ("PH", 12.88, 121.77),
    "philippine": ("PH", 12.88, 121.77),
    "singapore": ("SG", 1.35, 103.82),
    "indonesia": ("ID", -0.79, 113.92),
    "bangladesh": ("BD", 23.68, 90.36),
    "colombia": ("CO", 4.57, -74.3),
    "peru": ("PE", -9.19, -75.02),
    "peruvian": ("PE", -9.19, -75.02),
    "lima": ("PE", -12.05, -77.04),
    "chile": ("CL", -35.68, -71.54),
    "chilean": ("CL", -35.68, -71.54),
    "santiago": ("CL", -33.45, -70.67),
    "argentina": ("AR", -38.42, -63.62),
    "buenos aires": ("AR", -34.6, -58.38),
    "bolivia": ("BO", -16.29, -63.59),
    "ecuador": ("EC", -1.83, -78.18),
    "uganda": ("UG", 1.37, 32.29),
    "senegal": ("SN", 14.5, -14.45),
    "malaysia": ("MY", 4.21, 101.97),
    "estonia": ("EE", 58.6, 25.01),
    "finland": ("FI", 64.0, 26.0),
    "poland": ("PL", 51.92, 19.15),
    "romania": ("RO", 45.94, 24.97),
    # ── 서유럽 (누락 방지) ────────────────────────────────────────────────────
    "italy": ("IT", 42.83, 12.83),
    "italian": ("IT", 42.83, 12.83),
    "rome": ("IT", 41.90, 12.49),
    "milan": ("IT", 45.46, 9.19),
    "venice": ("IT", 45.44, 12.33),
    "naples": ("IT", 40.85, 14.27),
    "spain": ("ES", 40.0, -4.0),
    "spanish": ("ES", 40.0, -4.0),
    "madrid": ("ES", 40.42, -3.70),
    "barcelona": ("ES", 41.39, 2.16),
    "portugal": ("PT", 39.55, -7.86),
    "lisbon": ("PT", 38.72, -9.14),
    "netherlands": ("NL", 52.37, 5.23),
    "dutch": ("NL", 52.37, 5.23),
    "amsterdam": ("NL", 52.37, 4.9),
    "belgium": ("BE", 50.85, 4.35),
    "brussels": ("BE", 50.85, 4.35),
    "sweden": ("SE", 60.13, 18.64),
    "swedish": ("SE", 60.13, 18.64),
    "norway": ("NO", 64.5, 17.9),
    "norwegian": ("NO", 64.5, 17.9),
    "denmark": ("DK", 56.26, 9.5),
    "danish": ("DK", 56.26, 9.5),
    "switzerland": ("CH", 46.82, 8.23),
    "swiss": ("CH", 46.82, 8.23),
    "austria": ("AT", 47.52, 14.55),
    "vienna": ("AT", 48.21, 16.37),
    "greece": ("GR", 39.07, 21.82),
    "greek": ("GR", 39.07, 21.82),
    "athens": ("GR", 37.98, 23.73),
    "czech": ("CZ", 49.82, 15.47),
    "hungary": ("HU", 47.16, 19.5),
    "serbia": ("RS", 44.02, 21.09),
    "croatia": ("HR", 45.1, 15.2),
    "canada": ("CA", 56.13, -106.35),
    "canadian": ("CA", 56.13, -106.35),
    "toronto": ("CA", 43.65, -79.38),
    "ottawa": ("CA", 45.42, -75.69),
    "south africa": ("ZA", -30.56, 22.94),
    "kenya": ("KE", -0.02, 37.91),
    "ghana": ("GH", 7.95, -1.02),
    "morocco": ("MA", 31.79, -7.09),
    "algeria": ("DZ", 28.03, 1.66),
    "thailand": ("TH", 15.87, 100.99),
    "vietnam": ("VN", 14.06, 108.28),
    "new zealand": ("NZ", -40.9, 174.89),
}


# ── 데이터 클래스 ────────────────────────────────────────────────────────────

@dataclass
class NormalizeResult:
    title: str
    title_ko: Optional[str]
    body: str
    topic: str
    entity_anchor: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    geohash5: Optional[str]
    country_code: Optional[str]
    severity: int
    source_tier: str
    confidence: float
    dedup_key: str
    lang: str
    event_time: datetime


# ── 내부 함수들 ──────────────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    try:
        from langdetect import detect
        return detect(text[:500])
    except Exception:
        return "unknown"


def _translate_to_english(text: str, lang: str) -> str:
    """비영어 텍스트를 영어로 번역. 실패 시 원문 반환."""
    if lang in ("en", "unknown"):
        return text
    try:
        from deep_translator import GoogleTranslator
        # 번역 길이 제한 (무료 API 500자)
        chunk = text[:480]
        translated = GoogleTranslator(source="auto", target="en").translate(chunk)
        return translated or text
    except Exception as e:
        logger.warning("번역 실패 (%s→en, %d자): %s", lang, len(text), e)
        return text


def _translate_to_korean(text: str) -> Optional[str]:
    """영어 텍스트를 한국어로 번역. 실패 시 None 반환."""
    try:
        from deep_translator import GoogleTranslator
        chunk = text[:480]
        result = GoogleTranslator(source="en", target="ko").translate(chunk)
        return result or None
    except Exception as e:
        logger.warning("한국어 번역 실패 (%d자): %s", len(text), e)
        return None


# 강력한 신호 키워드 (1개만 있어도 topic 분류 확정)
_STRONG_KEYWORDS: dict[str, set[str]] = {
    "conflict":  {"missile", "airstrike", "artillery", "ceasefire", "shelling",
                  "rocket", "mortar", "offensive", "bombardment", "warplane",
                  # 추가 강력 키워드
                  "nuclear weapon", "nuclear weapons", "warhead", "ballistic missile",
                  "invasion", "invade", "armed conflict", "military conflict",
                  "weapons transfer", "arms transfer"},
    "terror":    {"terrorist", "suicide bomb", "isis", "al-qaeda", "jihadist",
                  "beheading", "cartel", "drug lord", "hostage"},
    "coup":      {"coup", "junta", "seized power", "military takeover",
                  "martial law", "deposed", "detained president"},
    "sanctions": {"sanctions", "embargo", "trade ban", "asset freeze", "blacklist"},
    "cyber":     {"cyberattack", "ransomware", "malware", "ddos", "data breach"},
    "maritime":  {"naval", "strait", "blockade", "submarine", "fleet"},
    "disaster":  {"earthquake", "tsunami", "typhoon", "hurricane", "volcanic eruption",
                  "flash flood", "landslide", "mudslide", "avalanche"},
    "health":    {"outbreak", "epidemic", "pandemic", "measles", "cholera", "ebola",
                  "mpox", "monkeypox", "dengue", "covid", "coronavirus",
                  "community transmission", "disease outbreak", "health emergency"},
}


# 비군사 문맥 패턴 — 이 패턴이 있으면 conflict/terror weak 키워드를 무효화
_NON_MILITARY_CONTEXT: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # 개인 사망 (자살, 병사, 사고사)
    r"killed (him|her|them)self",
    r"took (his|her|their) (own )?life",
    r"(battle|fight|struggle) with (cancer|illness|disease|depression|disorder|addiction|bipolar|alzheimer|dementia|parkinson)",
    r"died (of|from|after) (cancer|illness|disease|heart|stroke|accident|surgery)",
    r"passed away (after|following|due)",
    # 스포츠/경기 문맥
    r"(match|game|tournament|championship|league|cup|race|heat) (battle|fight|clash|war)",
    r"(box|boxing|mma|wrestling|ufc|wwe)",
    # 엔터테인먼트/예술
    r"(film|movie|series|show|episode|album|song|novel|book|play) (battle|fight|war|kills|killed)",
    r"(actor|actress|singer|musician|director|author|artist).{0,60}(dies|died|dead|pass)",
    r"(dies|died|dead).{0,60}(actor|actress|singer|musician|director|artist)",
    # 축제/카니발/전통 행사 — "오렌지 전투", "토마티나" 등
    r"(carnival|festival|celebration|parade|tradition|annual|festivity).{0,100}(battle|fight|war|attack|throw)",
    r"(battle|fight|war|throw).{0,100}(carnival|festival|celebration|parade|tradition|annual)",
    r"(orange|tomato|flower|food|fruit|vegetable).{0,50}(battle|fight|throwing|toss|pelting|hurling)",
    r"(throwing|toss|hurl|pelt).{0,50}(orange|tomato|flower|food|fruit)",
    r"ivrea",          # 이탈리아 오렌지 전투 도시
    r"la tomatina",    # 스페인 토마토 축제
    r"carnival of ",   # 카니발 이벤트
    r"mardi gras",
]]


def _has_non_military_context(text: str) -> bool:
    """비군사 문맥(개인사망·스포츠·엔터)이면 True."""
    for p in _NON_MILITARY_CONTEXT:
        if p.search(text):
            return True
    return False


def _classify_topic(text: str) -> str:
    """
    키워드 매칭으로 topic 분류.
    - 강력 키워드: 1개만 매칭돼도 분류
    - 일반 키워드: 2개 이상 매칭 필요 (오분류 방지)
    - coup / cyber / maritime: 1개도 충분 (도메인이 좁음)
    - 비군사 문맥(개인사망, 스포츠, 엔터)이면 conflict/terror 약한 키워드 무효화
    """
    text_lower = text.lower()
    non_military = _has_non_military_context(text_lower)
    scores: dict[str, int] = {}

    for topic, keywords in TOPIC_KEYWORDS.items():
        # 강력 키워드 체크
        strong = _STRONG_KEYWORDS.get(topic, set())
        strong_hits = sum(1 for kw in strong if kw in text_lower)
        if strong_hits:
            scores[topic] = scores.get(topic, 0) + strong_hits * 3  # 가중치 3배

        # 일반 키워드 체크
        weak_hits = sum(1 for kw in keywords if kw not in strong and kw in text_lower)

        # 비군사 문맥이면 conflict/terror weak 키워드 무효화
        if non_military and topic in ("conflict", "terror"):
            weak_hits = 0

        # coup / cyber / maritime / disaster / health는 도메인이 좁아 1개도 충분
        if topic in ("coup", "cyber", "maritime", "sanctions", "disaster", "health"):
            if weak_hits:
                scores[topic] = scores.get(topic, 0) + weak_hits
        else:
            # conflict / terror / diplomacy / protest는 2개 이상 필요
            if weak_hits >= 2:
                scores[topic] = scores.get(topic, 0) + weak_hits

    return max(scores, key=lambda t: scores[t]) if scores else "unknown"


def _calculate_severity(text: str, topic: str) -> int:
    """
    심각도 산정 (0~100).

    = base(토픽) + keyword_modifier(SEVERITY_UP/DOWN) + casualty_bonus(사상자 수)
    """
    base = TOPIC_BASE_SEVERITY.get(topic, 25)
    text_lower = text.lower()

    # 키워드 보정
    modifier = sum(delta for kw, delta in SEVERITY_UP if kw in text_lower)
    modifier += sum(delta for kw, delta in SEVERITY_DOWN if kw in text_lower)

    # 사상자 수 기반 추가 보정
    modifier += _casualty_bonus(text_lower)

    return max(0, min(100, base + modifier))


def _extract_geo(text: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    """
    국가 코드, 위도, 경도 반환.

    단순 첫 매칭 대신 빈도 기반:
    - 모든 매칭 키워드를 찾아 국가별 등장 횟수 집계
    - 가장 많이 등장한 국가 선택 (동점이면 가장 긴 키워드 우선)
    → "일본 언론이 트럼프 관세 기사 보도" 시 JP보다 US 키워드가 많으면 US 선택
    """
    text_lower = text.lower()
    from collections import defaultdict
    country_hits: dict[str, list[tuple[int, float, float]]] = defaultdict(list)

    for kw in sorted(COUNTRY_MAP.keys(), key=len, reverse=True):
        if kw in text_lower:
            code, lat, lon = COUNTRY_MAP[kw]
            # 키워드 등장 횟수 × 키워드 길이 가중치
            count = text_lower.count(kw)
            weight = count * len(kw)
            country_hits[code].append((weight, lat, lon))

    if not country_hits:
        return None, None, None

    # 국가별 총 가중치 계산 후 최대 선택
    best_code = max(country_hits, key=lambda c: sum(w for w, _, _ in country_hits[c]))
    # 해당 국가의 가장 긴 키워드(대표 좌표) 사용
    best_entry = max(country_hits[best_code], key=lambda x: x[0])
    return best_code, best_entry[1], best_entry[2]


def _make_geohash(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    if lat is None or lon is None:
        return None
    try:
        import geohash2
        return geohash2.encode(lat, lon, precision=5)
    except Exception:
        return None


def _make_dedup_key(text: str) -> str:
    """정규화 텍스트의 MD5 지문."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    words = sorted(cleaned.split())[:60]
    return hashlib.md5(" ".join(words).encode("utf-8")).hexdigest()


def _make_title(text: str, max_len: int = 120) -> str:
    sentences = re.split(r"[.!?\n]", text.strip())
    title = (sentences[0].strip() if sentences else text.strip())
    return title[:max_len - 3] + "..." if len(title) > max_len else title



def _calculate_confidence(tier: str, severity: int) -> float:
    base = {"A": 0.85, "B": 0.70, "C": 0.55, "D": 0.35}.get(tier, 0.50)
    if severity >= 75:
        base = max(0.30, base - 0.05)
    return round(min(0.95, base), 2)


# ── 공개 API ─────────────────────────────────────────────────────────────────

def is_relevant(result: "NormalizeResult") -> bool:
    """
    정규화 결과가 서비스에 표시할 가치가 있는지 판단.

    - topic이 unknown이 아님 → 항상 통과
    - topic이 unknown이면:
        severity > 20 (보정 키워드가 하나 이상 붙은 경우)이어야 통과.
        country_code만 있다고 해서 통과시키지 않음.
        (스포츠·연예·인간미담 등 나라 이름이 나오는 잡음 차단)
    """
    if result.topic != "unknown":
        return True
    # unknown 토픽은 보정 키워드로 severity가 올라간 경우에만 관련성 있음
    return result.severity > 20


def normalize(
    raw_text: str,
    source_tier: str,
    collected_at: datetime,
    source_title: Optional[str] = None,
    published_at: Optional[datetime] = None,
) -> NormalizeResult:
    """
    RawEvent 텍스트 → NormalizeResult (동기).

    source_title: RSS entry.title 등 원본 제목 (있으면 본문 추출 제목보다 우선).
    published_at: 실제 기사/메시지 발행 시간. 없으면 collected_at 사용.
    """
    lang = _detect_language(raw_text)

    # 비영어 텍스트는 영어로 번역하여 분류/지오 추출에 활용
    text_for_analysis = _translate_to_english(raw_text, lang)

    topic = _classify_topic(text_for_analysis)
    severity = _calculate_severity(text_for_analysis, topic)
    country_code, lat, lon = _extract_geo(text_for_analysis)
    geohash5 = _make_geohash(lat, lon)
    confidence = _calculate_confidence(source_tier, severity)
    dedup_key = _make_dedup_key(raw_text)  # 원문 기반으로 중복 검사

    # 제목 결정: RSS 원본 title 우선 (있으면 번역), 없으면 본문 첫 문장 추출
    if source_title and len(source_title.strip()) > 5:
        raw_title = source_title.strip()[:200]
        # 비영어 제목도 영어로
        title_lang = _detect_language(raw_title)
        title_en = _translate_to_english(raw_title, title_lang) if title_lang not in ("en", "unknown") else raw_title
        title = title_en[:120]
    else:
        title = _make_title(text_for_analysis)

    # 한국어 제목: 뉴스 원제목(title)을 그대로 번역 (이벤트 타임라인 표시용)
    title_ko = _translate_to_korean(title)

    entity_anchor: Optional[str] = country_code
    if not entity_anchor:
        m = re.search(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b", text_for_analysis)
        if m:
            entity_anchor = m.group(1)[:64]

    return NormalizeResult(
        title=title,
        title_ko=title_ko,
        body=text_for_analysis[:2000],  # 번역된 본문 저장
        topic=topic,
        entity_anchor=entity_anchor,
        lat=lat,
        lon=lon,
        geohash5=geohash5,
        country_code=country_code,
        severity=severity,
        source_tier=source_tier,
        confidence=confidence,
        dedup_key=dedup_key,
        lang=lang,
        event_time=published_at if published_at is not None else collected_at,
    )
