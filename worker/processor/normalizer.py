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
        # 분쟁/전쟁 일반
        "conflict", "warfare", "hostilities", "armed",
        "invasion", "invade", "invading", "invades",
        "occupation", "occupied", "occupying",
        "frontline", "front line", "war zone", "warzone",
        "siege", "ambush", "sniper", "gunfire", "firefight",
        # 병력/무기
        "soldier", "soldiers", "fighter", "fighters", "combatant",
        "weapon", "weapons", "arms", "nuclear", "warhead",
        "nuclear weapon", "nuclear weapons", "ballistic",
        "arms transfer", "arms supply", "weapons transfer",
        "military aid", "military support", "military assistance",
        "military operation", "military action", "military force",
        "armed forces", "armed conflict", "armed group",
        "deployment", "deployed", "mobilization", "reinforcements",
        "war effort", "prolong", "prolonging",
        # 전쟁 범죄 · 극단적 폭력
        "war crime", "war crimes", "ethnic cleansing", "scorched earth",
        "carpet bombing", "cluster bomb", "white phosphorus",
        "indiscriminate", "civilian casualties", "collateral damage",
        # WMD (대량살상무기)
        "chemical attack", "nerve agent", "sarin", "mustard gas",
        "dirty bomb", "radiological", "wmds", "weapons of mass destruction",
        "intercontinental", "icbm", "hypersonic",
    ],
    "terror": [
        "terror", "terrorist", "hostage", "isis", "al-qaeda", "extremist",
        "jihadist", "suicide bomb", "attack on civilians", "beheading",
        "cartel", "drug lord", "drug trafficking", "organized crime", "gang",
        "assassination", "murder", "shooting", "stabbing", "kidnapping",
        # 총기 · 폭탄
        "mass shooting", "school shooting", "active shooter", "gunman",
        "lone wolf", "vehicle attack", "ramming", "pipe bomb", "ied",
        "improvised explosive", "car bomb", "truck bomb",
        # 조직범죄 · 암살
        "assassination attempt", "political assassination", "targeted killing",
        "death squad", "execution", "extrajudicial",
        "hostage crisis", "hostage situation", "bomb threat",
        "domestic terrorism", "bioterrorism", "anthrax",
    ],
    "coup": [
        "coup", "overthrow", "junta", "seized power", "military takeover",
        "martial law", "emergency decree", "suspended constitution",
        "deposed", "detained president",
        "arrested president", "arrested opposition", "imprisoned leader",
        "political prisoner", "opposition leader arrested", "former president arrested",
        "ex-president", "former leader arrested",
        # 정변/체제 위기
        "insurrection", "sedition", "storming", "power grab",
        "authoritarian", "dictatorship", "autocratic",
        "constitutional crisis", "government collapse", "failed state",
        "regime change", "political purge", "political crackdown",
    ],
    "sanctions": [
        "sanctions", "embargo", "trade ban", "export control", "asset freeze",
        "blacklist", "tariff", "economic pressure", "restriction",
        "sanctioned", "penalty", "penalties", "sanctioning",
        # 금융/경제 위기 · 비상조치
        "stock market", "trading halt", "trading suspension", "market shutdown",
        "market crash", "market collapse", "financial crisis", "economic crisis",
        "bank run", "bank holiday", "currency crisis", "default",
        "national emergency", "state of emergency", "emergency powers",
        "ieepa", "executive order", "capital controls",
        # 경제 위기 확장
        "recession", "depression", "economic meltdown", "fiscal crisis",
        "debt crisis", "debt default", "sovereign default", "bailout",
        "hyperinflation", "inflation crisis", "austerity",
        "trade war", "currency manipulation", "supply chain crisis",
        "oil embargo", "energy crisis", "gas crisis", "price shock",
        "government shutdown", "budget crisis",
    ],
    "cyber": [
        "cyberattack", "hacked", "ransomware", "malware", "ddos",
        "data breach", "cyber", "phishing", "vulnerability", "exploit",
        # 대규모 사이버 위협
        "cyber warfare", "state-sponsored", "critical infrastructure",
        "power grid attack", "internet shutdown", "internet blackout",
        "communication blackout", "gps jamming", "satellite attack",
        "deepfake", "disinformation campaign", "information warfare",
        "election interference", "election hacking",
    ],
    "protest": [
        "protest", "demonstration", "rally", "riot", "crowd", "march",
        "unrest", "strike", "uprising", "demonstrators",
        # 대규모 시민 저항
        "civil disobedience", "general strike", "revolution",
        "mass protest", "anti-government", "pro-democracy",
        "crackdown", "tear gas", "water cannon", "rubber bullet",
        "curfew", "internet cut", "media blackout",
        "political unrest", "social unrest", "civil unrest",
    ],
    "diplomacy": [
        "diplomat", "embassy", "treaty", "agreement", "summit",
        "negotiation", "peace deal", "sanctions lifted", "talks",
        "president", "minister", "government", "election", "court", "supreme court",
        "ruling", "law", "policy", "administration", "parliament",
        "national assembly", "legislature", "congress", "senate",
        "opposition", "political crisis", "arrested", "detained",
        # 외교/국제관계
        "foreign affairs", "foreign minister", "foreign ministry",
        "international law", "diplomatic", "bilateral", "multilateral",
        "ending war", "end the war", "peace process", "peace effort",
        "war crimes", "accountability", "ceasefire talks",
        "rapid support forces", "rsf", "paramilitary",
        "flouting", "accuses", "accused of",
        # 정치 위기
        "impeachment", "impeached", "indictment", "indicted",
        "resignation", "expelled", "recalled ambassador",
        "diplomatic crisis", "severed ties", "recalled envoy",
        "persona non grata", "expelled diplomats",
    ],
    "maritime": [
        "naval", "ship", "vessel", "strait", "blockade", "coast guard",
        "maritime", "submarine", "fleet", "tanker",
        # 이주/난민 해상 사망
        "mediterranean", "aegean", "english channel", "migrant", "migrants",
        "refugee", "refugees", "drowned", "drowning", "crossing",
        "boat capsized", "capsized", "shipwreck", "rescue at sea",
        "died trying to cross", "crossing deaths", "smuggled",
        # 해상 위기
        "piracy", "hijacked ship", "seized vessel", "oil spill",
        "shipping disruption", "port blockade", "canal blocked",
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
        # 산업재해 · 인프라 사고
        "nuclear meltdown", "radiation leak", "reactor",
        "chemical spill", "chemical leak", "toxic", "contamination",
        "industrial accident", "factory explosion", "refinery",
        "mine collapse", "building collapse", "bridge collapse",
        "dam burst", "dam failure", "levee breach",
        "power outage", "blackout", "grid failure",
        "train derailment", "plane crash", "aviation disaster",
        "sinkhole", "infrastructure failure",
        # 인도주의 위기
        "humanitarian crisis", "humanitarian disaster", "mass displacement",
        "refugee crisis", "food shortage", "water crisis", "water shortage",
        "shelter in place", "evacuation order",
    ],
    "health": [
        # 전염병·감염
        "outbreak", "epidemic", "pandemic", "infection", "infectious",
        "measles", "cholera", "ebola", "mpox", "monkeypox", "dengue",
        "malaria", "tuberculosis", "polio", "typhoid", "hepatitis",
        "covid", "coronavirus", "influenza", "flu outbreak",
        "bird flu", "avian flu", "h5n1", "h1n1", "sars", "mers",
        "plague", "yellow fever", "zika", "nipah",
        # 보건 기관·조치
        "public health", "health ministry", "health alert", "health emergency",
        "quarantine", "lockdown", "contact tracing", "vaccination campaign",
        "world health organization", "who alert", "cdc alert",
        "disease outbreak", "community transmission", "health crisis",
        # 사망·확산
        "cases confirmed", "deaths from", "hospitalized", "health workers",
        "health authorities", "spreading", "contagious", "contagion",
        # 의약품 · 생물안보
        "drug shortage", "vaccine shortage", "antibiotic resistance",
        "superbug", "lab leak", "biosecurity", "gain of function",
    ],
}

# ── Severity 기본값 ──────────────────────────────────────────────────────────

TOPIC_BASE_SEVERITY: dict[str, int] = {
    "conflict":  60,
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
    # ── 사상자 ──
    ("killed", 10), ("dead", 10), ("casualties", 8), ("deaths", 10),
    ("wounded", 6), ("injured", 5), ("massacre", 15), ("genocide", 20),
    ("mass killing", 15), ("mass grave", 15), ("ethnic cleansing", 20),
    ("war crime", 15), ("crimes against humanity", 18),
    ("exterminated", 18), ("slaughter", 15), ("atrocity", 15),
    # ── 무기/공격 ──
    ("airstrike", 10), ("air strike", 10), ("missile strike", 12), ("explosion", 7),
    ("bomb", 6), ("bombing", 10), ("bombardment", 12),
    ("rocket", 6), ("artillery", 7), ("drone strike", 10), ("shelling", 7),
    ("missile launch", 12), ("missile fired", 12), ("missile attack", 12),
    ("chemical weapon", 18), ("biological weapon", 18), ("nuclear", 20),
    ("chemical attack", 18), ("nerve agent", 18), ("sarin", 18),
    ("dirty bomb", 15), ("icbm", 18), ("hypersonic", 12),
    ("cluster bomb", 12), ("white phosphorus", 12), ("napalm", 12),
    ("carpet bombing", 15), ("indiscriminate", 10),
    # ── 대규모 군사 작전 ──
    ("invasion", 18), ("invading", 18), ("invade", 18),
    ("full-scale", 12), ("all-out", 12), ("total war", 18),
    ("declaration of war", 18), ("declared war", 18), ("act of war", 15),
    ("joint attack", 12), ("joint strike", 12), ("joint operation", 10),
    ("ground offensive", 15), ("ground invasion", 18),
    ("preemptive strike", 15), ("retaliatory strike", 12),
    ("scorched earth", 12), ("siege warfare", 10),
    # ── 속보/긴급 ──
    ("breaking", 5), ("breaking news", 8), ("just in", 5),
    ("launches attack", 12), ("launched attack", 12), ("opens fire", 10),
    ("military offensive", 12), ("commenced", 8), ("underway", 6),
    # ── 국가비상사태 · 금융위기 ──
    ("national emergency", 15), ("state of emergency", 12),
    ("emergency powers", 12), ("ieepa", 12),
    ("trading halt", 10), ("trading suspension", 10), ("market shutdown", 12),
    ("market crash", 10), ("market collapse", 12), ("financial crisis", 10),
    ("stock market crash", 12), ("bank run", 10), ("bank holiday", 8),
    ("currency crisis", 10), ("sovereign default", 15),
    ("capital controls", 8), ("economic collapse", 12),
    ("hyperinflation", 10), ("debt default", 12), ("bailout", 6),
    ("government shutdown", 8), ("fiscal cliff", 8),
    # ── 인프라 · 재난 ──
    ("power grid", 8), ("hospital", 6), ("school", 5),
    ("dam", 8), ("nuclear plant", 15), ("nuclear facility", 15),
    ("water supply", 7),
    ("nuclear meltdown", 20), ("radiation leak", 15), ("reactor breach", 15),
    ("chemical spill", 10), ("toxic", 6), ("contamination", 8),
    ("building collapse", 10), ("bridge collapse", 10), ("dam burst", 12),
    ("mine collapse", 8), ("factory explosion", 10),
    ("train derailment", 8), ("plane crash", 10), ("aviation disaster", 12),
    ("power outage", 6), ("blackout", 6), ("grid failure", 10),
    ("infrastructure failure", 8),
    # ── 규모/범위 ──
    ("massive", 6), ("large-scale", 6), ("widespread", 5), ("unprecedented", 8),
    ("catastrophic", 10), ("devastating", 8), ("major offensive", 10),
    ("deadliest", 10), ("worst ever", 8), ("record-breaking", 6),
    ("historic", 5), ("never before", 8),
    # ── 정치 위기 · 쿠데타 ──
    ("martial law", 15), ("mobilization", 12), ("emergency", 6),
    ("coup", 8), ("overthrow", 10), ("seized power", 12),
    ("insurrection", 15), ("sedition", 12), ("government collapse", 12),
    ("constitutional crisis", 10), ("impeachment", 8), ("impeached", 8),
    ("political assassination", 15), ("assassination attempt", 12),
    ("regime change", 8), ("failed state", 10), ("political purge", 10),
    # ── 긴박성 ──
    ("escalating", 5), ("intensifying", 5), ("imminent", 6), ("erupted", 6),
    ("siege", 8), ("surrounded", 6), ("blockade", 7), ("encircled", 7),
    ("on the brink", 8), ("war footing", 10), ("defcon", 12),
    ("red alert", 8), ("maximum alert", 8),
    # ── 민간인 · 인도주의 ──
    ("civilian", 5), ("capital", 4), ("city center", 4),
    ("humanitarian crisis", 10), ("humanitarian disaster", 12),
    ("mass displacement", 8), ("refugee crisis", 8),
    ("famine", 10), ("food shortage", 8), ("starvation", 10),
    ("water crisis", 8), ("shelter in place", 6), ("evacuation order", 6),
    ("curfew", 5),
    # ── 테러 · 총기 ──
    ("mass shooting", 12), ("school shooting", 15), ("active shooter", 10),
    ("hostage crisis", 10), ("bomb threat", 6), ("suicide attack", 12),
    ("car bomb", 10), ("truck bomb", 12), ("ied", 8),
    # ── 사이버 · 통신 ──
    ("internet shutdown", 8), ("communication blackout", 10),
    ("cyber warfare", 10), ("critical infrastructure", 8),
    ("election interference", 8),
    # ── 보건 ──
    ("pandemic declared", 15), ("global health emergency", 12),
    ("new variant", 6), ("drug resistant", 8), ("superbug", 8),
    ("lab leak", 8), ("biosecurity", 6),
]

SEVERITY_DOWN: list[tuple[str, int]] = [
    # 불확실성
    ("alleged", -8), ("unconfirmed", -10), ("rumor", -12),
    ("reportedly", -5), ("claims", -6), ("possibly", -7),
    ("denied", -5), ("false alarm", -15), ("hoax", -15),
    ("satire", -15), ("parody", -15), ("fictional", -15),
    # 완화
    ("ceasefire", -10), ("truce", -10), ("peace deal", -12),
    ("de-escalat", -10), ("withdrawal", -7), ("retreat", -5),
    ("diplomatic solution", -10), ("agreement reached", -8),
    ("tensions eased", -8), ("stand down", -8), ("stepped back", -6),
    # 소규모
    ("minor", -6), ("small-scale", -6), ("limited", -5), ("contained", -5),
    ("isolated incident", -8), ("under control", -8),
    # 훈련/연습 (실제 공격과 혼동 방지)
    ("military exercise", -10), ("drill", -8), ("simulation", -10),
    ("routine patrol", -8), ("scheduled exercise", -10), ("war games", -8),
    ("training exercise", -10), ("annual exercise", -8),
    # 과거 사건 (현재 위협 아님)
    ("anniversary", -6), ("memorial", -6), ("years ago", -8),
    ("looking back", -8), ("retrospective", -8),
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
    # ── 1순위: 빈도 높음 / 분쟁 관련 ────────────────────────────────────────────
    "kiev": ("UA", 50.45, 30.52),
    "sri lanka": ("LK", 7.87, 80.77),
    "colombo": ("LK", 6.93, 79.85),
    # ── 2순위: 코카서스/중앙아시아 ───────────────────────────────────────────────
    "belarus": ("BY", 53.71, 27.95),
    "minsk": ("BY", 53.9, 27.57),
    "belarusian": ("BY", 53.71, 27.95),
    "armenia": ("AM", 40.07, 45.04),
    "yerevan": ("AM", 40.18, 44.51),
    "armenian": ("AM", 40.07, 45.04),
    "azerbaijan": ("AZ", 40.14, 47.58),
    "baku": ("AZ", 40.41, 49.87),
    "tajikistan": ("TJ", 38.86, 71.28),
    "uzbekistan": ("UZ", 41.38, 64.59),
    "cambodia": ("KH", 12.57, 104.99),
    "phnom penh": ("KH", 11.57, 104.92),
    # ── 3순위: 아프리카 ──────────────────────────────────────────────────────────
    "zimbabwe": ("ZW", -20.0, 30.0),
    "harare": ("ZW", -17.83, 31.05),
    "tanzania": ("TZ", -6.37, 34.89),
    "burundi": ("BI", -3.37, 29.92),
    "mozambique": ("MZ", -18.67, 35.53),
    "cameroon": ("CM", 7.37, 12.35),
    "chad": ("TD", 15.45, 18.73),
    "niger": ("NE", 17.61, 8.08),
    # ── 4순위: 미얀마 지역 ───────────────────────────────────────────────────────
    "sagaing": ("MM", 21.88, 95.98),
    "kachin": ("MM", 25.5, 97.5),
    "rakhine": ("MM", 20.0, 93.5),
    "mandalay": ("MM", 21.97, 96.08),
    # ── 5순위: 걸프 소국 (누락으로 인한 지오 실패 해소) ──────────────────────────
    "bahrain": ("BH", 26.07, 50.55),
    "bahraini": ("BH", 26.07, 50.55),
    "manama": ("BH", 26.23, 50.59),
    "qatar": ("QA", 25.35, 51.18),
    "qatari": ("QA", 25.35, 51.18),
    "doha": ("QA", 25.29, 51.53),
    "kuwait": ("KW", 29.31, 47.48),
    "kuwaiti": ("KW", 29.31, 47.48),
    "kuwait city": ("KW", 29.37, 47.98),
    "united arab emirates": ("AE", 23.42, 53.85),
    "uae": ("AE", 23.42, 53.85),
    "emirati": ("AE", 23.42, 53.85),
    "dubai": ("AE", 25.20, 55.27),
    "abu dhabi": ("AE", 24.45, 54.65),
    "oman": ("OM", 21.47, 55.98),
    "omani": ("OM", 21.47, 55.98),
    "muscat": ("OM", 23.59, 58.55),
    "jordan": ("JO", 30.59, 36.24),
    "jordanian": ("JO", 30.59, 36.24),
    "amman": ("JO", 31.95, 35.93),
    "tunisia": ("TN", 33.89, 9.54),
    "tunisian": ("TN", 33.89, 9.54),
    "tunis": ("TN", 36.81, 10.18),
    # ── 6순위: 기타 ──────────────────────────────────────────────────────────────
    "cuba": ("CU", 21.52, -77.78),
    "havana": ("CU", 23.11, -82.37),
    "nepal": ("NP", 28.39, 84.12),
    "kathmandu": ("NP", 27.7, 85.32),
    "tbilisi": ("GE", 41.72, 44.79),
    "georgia": ("GE", 42.32, 43.36),
    "georgian": ("GE", 42.32, 43.36),
    # ── 한글 국가명 (지오 실패율 저감) ──────────────────────────────────────────
    "바레인": ("BH", 26.07, 50.55),
    "카타르": ("QA", 25.35, 51.18),
    "쿠웨이트": ("KW", 29.31, 47.48),
    "아랍에미리트": ("AE", 23.42, 53.85),
    "두바이": ("AE", 25.20, 55.27),
    "아부다비": ("AE", 24.45, 54.65),
    "오만": ("OM", 21.47, 55.98),
    "요르단": ("JO", 30.59, 36.24),
    "튀니지": ("TN", 33.89, 9.54),
    "우크라이나": ("UA", 49.0, 31.0),
    "러시아": ("RU", 61.0, 105.0),
    "이스라엘": ("IL", 31.5, 34.8),
    "팔레스타인": ("PS", 31.9, 35.3),
    "가자": ("PS", 31.5, 34.47),
    "이란": ("IR", 32.0, 53.0),
    "중국": ("CN", 35.0, 105.0),
    "대만": ("TW", 23.7, 121.0),
    "북한": ("KP", 40.3, 127.5),
    "한국": ("KR", 36.5, 127.8),
    "시리아": ("SY", 35.0, 38.0),
    "미얀마": ("MM", 17.0, 96.0),
    "수단": ("SD", 15.0, 32.0),
    "에티오피아": ("ET", 9.0, 38.5),
    "소말리아": ("SO", 5.5, 45.5),
    "레바논": ("LB", 33.9, 35.5),
    "이라크": ("IQ", 33.0, 44.0),
    "아프가니스탄": ("AF", 33.0, 65.0),
    "파키스탄": ("PK", 30.0, 70.0),
    "인도": ("IN", 20.0, 77.0),
    "사우디": ("SA", 24.0, 45.0),
    "사우디아라비아": ("SA", 24.0, 45.0),
    "터키": ("TR", 39.0, 35.0),
    "이집트": ("EG", 26.0, 30.0),
    "예멘": ("YE", 15.5, 47.5),
    "리비아": ("LY", 25.0, 17.0),
    "미국": ("US", 38.0, -97.0),
    "일본": ("JP", 35.0, 138.0),
    "독일": ("DE", 51.0, 9.0),
    "프랑스": ("FR", 46.0, 2.0),
    "영국": ("GB", 54.0, -2.0),
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
    translation_status: str  # ok | failed | skipped
    geo_method: str  # keyword | none
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
                  "nuclear weapon", "nuclear weapons", "warhead", "ballistic missile",
                  "invasion", "invade", "armed conflict", "military conflict",
                  "weapons transfer", "arms transfer",
                  "nuclear", "explosion", "troops deployed", "war zone",
                  # WMD · 극단적 폭력
                  "icbm", "hypersonic", "chemical attack", "nerve agent",
                  "dirty bomb", "ethnic cleansing", "genocide", "massacre",
                  "carpet bombing", "cluster bomb", "white phosphorus",
                  "scorched earth", "war crime", "crimes against humanity"},
    "terror":    {"terrorist", "suicide bomb", "isis", "al-qaeda", "jihadist",
                  "beheading", "cartel", "drug lord", "hostage",
                  "shooting", "assassination", "kidnapping", "murder",
                  "mass shooting", "school shooting", "active shooter",
                  "car bomb", "truck bomb", "ied", "hostage crisis",
                  "assassination attempt", "bioterrorism", "anthrax"},
    "protest":   {"protest", "protests", "riot", "riots", "uprising", "demonstration",
                  "revolution", "general strike", "civil disobedience"},
    "diplomacy": {"summit", "peace deal", "peace process", "treaty", "bilateral",
                  "diplomatic", "foreign minister", "foreign ministry",
                  "impeachment", "impeached", "diplomatic crisis"},
    "coup":      {"coup", "junta", "seized power", "military takeover",
                  "martial law", "deposed", "detained president",
                  "insurrection", "sedition", "constitutional crisis",
                  "government collapse", "failed state"},
    "sanctions": {"sanctions", "embargo", "trade ban", "asset freeze", "blacklist",
                  "national emergency", "state of emergency", "ieepa",
                  "market crash", "market collapse", "trading halt",
                  "financial crisis", "economic crisis", "sovereign default",
                  "hyperinflation", "debt default", "capital controls",
                  "government shutdown"},
    "cyber":     {"cyberattack", "ransomware", "malware", "ddos", "data breach",
                  "cyber warfare", "internet shutdown", "election hacking",
                  "critical infrastructure"},
    "maritime":  {"naval", "strait", "blockade", "submarine", "fleet",
                  "piracy", "hijacked ship", "oil spill"},
    "disaster":  {"earthquake", "tsunami", "typhoon", "hurricane", "volcanic eruption",
                  "flash flood", "landslide", "mudslide", "avalanche",
                  "nuclear meltdown", "radiation leak", "chemical spill",
                  "building collapse", "dam burst", "dam failure",
                  "train derailment", "plane crash", "humanitarian crisis",
                  "famine", "refugee crisis"},
    "health":    {"outbreak", "epidemic", "pandemic", "measles", "cholera", "ebola",
                  "mpox", "monkeypox", "dengue", "covid", "coronavirus",
                  "community transmission", "disease outbreak", "health emergency",
                  "bird flu", "h5n1", "sars", "mers", "plague", "nipah",
                  "global health emergency", "lab leak", "superbug"},
}


# 비군사 문맥 패턴 — 이 패턴이 있으면 conflict/terror weak 키워드를 무효화
_NON_MILITARY_CONTEXT: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # 개인 사망 (자살, 병사, 사고사)
    r"killed (him|her|them)self",
    r"took (his|her|their) (own )?life",
    r"(battle|fight|struggle) with (cancer|illness|disease|depression|disorder|addiction|bipolar|alzheimer|dementia|parkinson)",
    r"died (of|from|after) (cancer|illness|disease|heart|stroke|accident|surgery)",
    r"passed away (after|following|due)",
    # 스포츠/경기 문맥 (더 엄격한 패턴)
    r"(sports? match|championship game|tournament final|league match|cup final|race heat) (battle|fight|clash|war)",
    r"(box|boxing|mma|wrestling|ufc|wwe)",
    # 엔터테인먼트/예술 (더 엄격한 패턴)
    r"(film|movie|tv series|documentary)\s+(about|titled|called).{0,30}(battle|fight|war)",
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


# ── 다국어 토픽 키워드 (번역 실패 시 fallback) ─────────────────────────────
_TOPIC_KEYWORDS_MULTILANG: dict[str, dict[str, list[str]]] = {
    "ko": {
        "conflict": ["전쟁", "공격", "미사일", "폭격", "공습", "전투", "군사", "포격", "드론", "사상자", "휴전"],
        "terror": ["테러", "인질", "극단주의", "자폭", "암살", "총격", "납치"],
        "coup": ["쿠데타", "정변", "계엄령", "군부", "탄핵"],
        "sanctions": ["제재", "수출통제", "자산동결", "관세", "금수조치"],
        "cyber": ["사이버", "해킹", "랜섬웨어", "디도스", "악성코드"],
        "protest": ["시위", "집회", "시위대", "폭동", "봉기"],
        "diplomacy": ["외교", "정상회담", "조약", "협상", "평화", "대통령", "총리"],
        "disaster": ["지진", "홍수", "태풍", "화산", "쓰나미", "가뭄", "산사태"],
        "health": ["전염병", "감염", "확진", "사망자", "격리", "백신", "코로나"],
    },
    "ar": {
        "conflict": ["حرب", "هجوم", "صاروخ", "قصف", "غارة", "معركة", "عسكري", "قتلى", "وقف إطلاق النار"],
        "terror": ["إرهاب", "رهينة", "تطرف", "انتحاري", "اغتيال"],
        "coup": ["انقلاب", "أحكام عرفية"],
        "sanctions": ["عقوبات", "حظر", "تعريفة"],
        "diplomacy": ["دبلوماسي", "قمة", "معاهدة", "مفاوضات", "سلام", "رئيس"],
        "disaster": ["زلزال", "فيضان", "إعصار", "بركان", "تسونامي", "جفاف"],
        "health": ["وباء", "عدوى", "إصابات", "حجر صحي", "لقاح"],
    },
    "ru": {
        "conflict": ["война", "атака", "ракета", "бомба", "обстрел", "военный", "наступление", "жертвы", "перемирие"],
        "terror": ["террор", "заложник", "экстремизм", "взрыв", "убийство"],
        "coup": ["переворот", "военное положение"],
        "sanctions": ["санкции", "эмбарго", "тариф"],
        "diplomacy": ["дипломат", "саммит", "переговоры", "мир", "президент"],
        "disaster": ["землетрясение", "наводнение", "тайфун", "вулкан", "цунами", "засуха"],
        "health": ["эпидемия", "инфекция", "заражение", "карантин", "вакцина"],
    },
    "zh": {
        "conflict": ["战争", "攻击", "导弹", "轰炸", "空袭", "军事", "伤亡", "停火"],
        "terror": ["恐怖", "人质", "极端", "自杀式", "暗杀"],
        "coup": ["政变", "戒严"],
        "sanctions": ["制裁", "禁运", "关税"],
        "diplomacy": ["外交", "峰会", "条约", "谈判", "和平", "总统"],
        "disaster": ["地震", "洪水", "台风", "火山", "海啸", "干旱"],
        "health": ["疫情", "感染", "确诊", "隔离", "疫苗"],
    },
    "ja": {
        "conflict": ["戦争", "攻撃", "ミサイル", "爆撃", "空爆", "軍事", "死傷者", "停戦"],
        "terror": ["テロ", "人質", "過激派", "暗殺"],
        "coup": ["クーデター", "戒厳令"],
        "sanctions": ["制裁", "禁輸", "関税"],
        "diplomacy": ["外交", "首脳会談", "条約", "交渉", "平和", "大統領"],
        "disaster": ["地震", "洪水", "台風", "火山", "津波", "干ばつ"],
        "health": ["感染症", "感染", "確認", "隔離", "ワクチン"],
    },
    "fr": {
        "conflict": ["guerre", "attaque", "missile", "bombardement", "frappe", "militaire", "victimes", "cessez-le-feu"],
        "terror": ["terrorisme", "otage", "extrémisme", "attentat", "assassinat"],
        "coup": ["coup d'état", "loi martiale"],
        "sanctions": ["sanctions", "embargo", "tarif"],
        "diplomacy": ["diplomatie", "sommet", "traité", "négociation", "paix", "président"],
        "disaster": ["séisme", "inondation", "ouragan", "volcan", "tsunami", "sécheresse"],
        "health": ["épidémie", "infection", "cas confirmés", "quarantaine", "vaccin"],
    },
    "es": {
        "conflict": ["guerra", "ataque", "misil", "bombardeo", "militar", "víctimas", "alto el fuego"],
        "terror": ["terrorismo", "rehén", "extremismo", "atentado", "asesinato"],
        "coup": ["golpe de estado", "ley marcial"],
        "sanctions": ["sanciones", "embargo", "arancel"],
        "diplomacy": ["diplomacia", "cumbre", "tratado", "negociación", "paz", "presidente"],
        "disaster": ["terremoto", "inundación", "huracán", "volcán", "tsunami", "sequía"],
        "health": ["epidemia", "infección", "casos confirmados", "cuarentena", "vacuna"],
    },
    "de": {
        "conflict": ["Krieg", "Angriff", "Rakete", "Bombardierung", "Militär", "Opfer", "Waffenstillstand"],
        "terror": ["Terrorismus", "Geisel", "Extremismus", "Anschlag", "Ermordung"],
        "coup": ["Staatsstreich", "Kriegsrecht"],
        "sanctions": ["Sanktionen", "Embargo", "Zoll"],
        "diplomacy": ["Diplomatie", "Gipfel", "Vertrag", "Verhandlung", "Frieden", "Präsident"],
        "disaster": ["Erdbeben", "Überschwemmung", "Hurrikan", "Vulkan", "Tsunami", "Dürre"],
        "health": ["Epidemie", "Infektion", "bestätigte Fälle", "Quarantäne", "Impfstoff"],
    },
}


def _classify_topic_multilang(text: str, lang: str) -> Optional[str]:
    """번역 실패 시 원문 언어의 키워드로 토픽 분류 시도."""
    lang_kws = _TOPIC_KEYWORDS_MULTILANG.get(lang)
    if not lang_kws:
        return None
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for topic, keywords in lang_kws.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits >= 1:
            scores[topic] = hits
    return max(scores, key=lambda t: scores[t]) if scores else None


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

    # 키워드 보정 (누적 상한 ±40)
    keyword_delta = sum(delta for kw, delta in SEVERITY_UP if kw in text_lower)
    keyword_delta += sum(delta for kw, delta in SEVERITY_DOWN if kw in text_lower)
    keyword_delta = max(-40, min(40, keyword_delta))

    # 사상자 수 기반 추가 보정 (별도 상한, _casualty_bonus 내부에서 max 30)
    modifier = keyword_delta + _casualty_bonus(text_lower)

    return max(0, min(100, base + modifier))


def _extract_geo(
    text: str,
    title: Optional[str] = None,
) -> tuple[Optional[str], Optional[float], Optional[float]]:
    """
    국가 코드, 위도, 경도 반환.

    빈도 기반 + 제목 3배 가중치:
    - title에서 발견된 키워드는 weight × 3 (제목은 기사의 핵심 주제를 반영)
    - body에서 여러 국가가 언급되어도 title 국가가 우선됨
    """
    from collections import defaultdict
    country_hits: dict[str, list[tuple[int, float, float]]] = defaultdict(list)

    sorted_kws = sorted(COUNTRY_MAP.keys(), key=len, reverse=True)

    # title 매칭 (3배 가중치)
    if title:
        title_lower = title.lower()
        for kw in sorted_kws:
            if kw in title_lower:
                code, lat, lon = COUNTRY_MAP[kw]
                count = title_lower.count(kw)
                weight = count * len(kw) * 3  # 제목 3배 가중치
                country_hits[code].append((weight, lat, lon))

    # body(전체 텍스트) 매칭
    text_lower = text.lower()
    for kw in sorted_kws:
        if kw in text_lower:
            code, lat, lon = COUNTRY_MAP[kw]
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
    """정규화 텍스트의 MD5 지문 (단어 순서 유지)."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    words = cleaned.split()[:60]
    return hashlib.md5(" ".join(words).encode("utf-8")).hexdigest()


def _make_title(text: str, max_len: int = 120) -> str:
    sentences = re.split(r"[.!?\n]", text.strip())
    title = (sentences[0].strip() if sentences else text.strip())
    return title[:max_len - 3] + "..." if len(title) > max_len else title



def _calculate_confidence(tier: str, severity: int) -> float:
    """소스 tier 기반 confidence 계산.

    severity ≥ 75일 때 confidence 자체를 깎지 않음 (실제 고위험 사건의
    신뢰도를 왜곡하므로). auto-verify 조건에서 별도 처리.
    """
    base = {"A": 0.85, "B": 0.70, "C": 0.55, "D": 0.35}.get(tier, 0.50)
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
    if lang in ("en", "unknown"):
        translation_status = "skipped"
    else:
        translation_status = "ok"  # 번역 시도
    text_for_analysis = _translate_to_english(raw_text, lang)
    # 번역 실패 감지: 원문과 동일하면 실패로 판정 (영어가 아닌데 원문 그대로 반환)
    if lang not in ("en", "unknown") and text_for_analysis == raw_text:
        translation_status = "failed"

    topic = _classify_topic(text_for_analysis)

    # C3: 번역 실패 시 원문 언어 키워드로 토픽 분류 재시도
    if topic == "unknown" and lang not in ("en", "unknown"):
        multilang_topic = _classify_topic_multilang(raw_text, lang)
        if multilang_topic:
            topic = multilang_topic

    severity = _calculate_severity(text_for_analysis, topic)
    # 제목 결정 (geo 추출에 활용하기 위해 먼저 계산)
    _raw_title_for_geo = source_title.strip()[:200] if source_title and len(source_title.strip()) > 5 else None
    country_code, lat, lon = _extract_geo(text_for_analysis, title=_raw_title_for_geo)
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

    geo_method = "keyword" if country_code else "none"

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
        translation_status=translation_status,
        geo_method=geo_method,
        event_time=published_at if published_at is not None else collected_at,
    )
