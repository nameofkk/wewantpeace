"""
EventNormalizer: RawEvent 텍스트 → NormalizedEvent 변환.

처리 순서:
1. 언어 감지 (langdetect)
2. Topic 분류 (AI 우선, 실패 시 키워드 폴백)
3. Severity 계산 (AI 우선, 실패 시 키워드 폴백)
4. Confidence 계산 (source tier 기반)
5. dedup_key 생성 (정규화 텍스트 MD5)
6. Geo 정보 추출 (국가 키워드 → 좌표 → geohash5)
"""
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from worker.processor.calibration import INFORMATION_ACCESSIBILITY

logger = logging.getLogger(__name__)

# ── AI 기반 토픽+Severity 분류 ──────────────────────────────────────────────

_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
if not _OPENAI_KEY:
    logger.warning("OpenAI key not set — falling back to keyword classification")

_VALID_TOPICS = frozenset([
    "conflict", "terror", "coup", "sanctions", "cyber",
    "protest", "diplomacy", "maritime", "disaster", "health",
])

_AI_CLASSIFY_PROMPT = """\
You are a crisis/conflict event classifier for a global monitoring system.
Given a news article title and body, classify it into exactly ONE topic and assign a severity score.

## Topics (pick exactly one):
- conflict: Armed conflict, military operations, airstrikes, bombings, war, troops, weapons, casualties from combat
- terror: Terrorism, hostage situations, mass shootings, assassinations, cartel violence, extremist attacks, police/soldiers killed by attackers
- coup: Coups, military takeovers, martial law, government overthrow, insurrection, leader arrested/sentenced for insurrection
- sanctions: Economic sanctions, embargoes, trade bans, tariffs, financial crises, market crashes, economic emergencies
- cyber: Cyberattacks, hacking, ransomware, data breaches, internet shutdowns, election interference
- protest: Protests, demonstrations, riots, civil unrest, strikes, uprisings, crackdowns on protesters
- diplomacy: Diplomatic events, treaties, summits, elections, political developments, peace processes, government policy, birth rate/population stats
- maritime: Naval operations, shipping disruptions, piracy, maritime incidents, migrant crossings, port blockades
- disaster: Natural disasters (floods, earthquakes, storms), industrial accidents, infrastructure failures (tram/train crashes), humanitarian crises, famines
- health: Disease outbreaks, epidemics, pandemics, public health emergencies, vaccination campaigns

## Severity (0-100) — use the FULL range, do NOT cap at 80:
- 0-19: Minimal (routine exercises, policy discussions, population statistics)
- 20-39: Low (minor incidents, diplomatic statements, small protests, 1-2 casualties)
- 40-59: Moderate (significant protests, trade disputes, localized skirmishes, 3-20 casualties)
- 60-79: High (major military operations, severe crises, 20-100 casualties, major political verdicts)
- 80-89: Very High (large-scale attacks, 100+ casualties, war escalation, genocide accusations)
- 90-100: Critical (mass casualties 200+, active war between nations, nuclear threats, confirmed WMD use)

## Severity calibration examples:
- "200 killed in airstrike" → 95
- "School bombing kills 115" → 92
- "Missile strike, 30 dead" → 75
- "Ex-president sentenced to life for insurrection" → 75
- "Police officer killed by gunmen" → 55
- "Protests erupt over economic crisis" → 45
- "Ceasefire talks begin" → 30
- "Military drill conducted" → 20
- "Japan birth rate falls" → 15
- "Snow blankets New York" → 10

## Key rules:
- "state of emergency" in a WAR/MILITARY context → conflict, NOT sanctions
- "nuclear" in power plant context → disaster, NOT conflict
- Military exercises/drills → conflict with severity 20-30
- Tariff/trade policy without military dimension → sanctions
- Leader sentenced/arrested for past coup/insurrection → coup (not diplomacy)
- Read the FULL body context before deciding. Title alone can be misleading.
- When casualties are explicitly mentioned, severity MUST reflect the scale above.
- Entertainment/K-pop/celebrity/tourism articles with NO conflict angle → diplomacy with severity 0. Example: "BTS comeback boosts Korean tourism" → severity 0.

## Sub-topic (optional refinement within topic):
For "conflict": nk_provocation | military_exercise | geopolitical_response | active_combat | arms_transfer | general
For "sanctions": oil_energy | trade_tariff | general
For all other topics: general

Respond ONLY with JSON: {"topic": "...", "sub_topic": "...", "severity": N}"""


_VALID_SUB_TOPICS: dict[str, frozenset[str]] = {
    "conflict": frozenset(["nk_provocation", "military_exercise", "geopolitical_response", "active_combat", "arms_transfer", "general"]),
    "sanctions": frozenset(["oil_energy", "trade_tariff", "general"]),
}


def _classify_with_ai(title: str, body: str) -> Optional[tuple[str, str, int]]:
    """
    GPT-4o-mini로 토픽 + sub_topic + severity 분류.

    Returns:
        (topic, sub_topic, severity) 또는 실패 시 None
    """
    if not _OPENAI_KEY:
        return None

    # 빈 입력 방어
    if not title and not body:
        return None

    user_text = f"Title: {title[:200]}\n\nBody: {body[:500]}"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=_OPENAI_KEY, timeout=30.0)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _AI_CLASSIFY_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0,
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        if not raw:
            return None

        data = json.loads(raw)

        topic = data.get("topic", "").strip().lower()
        severity = data.get("severity")

        # 유효성 검증
        if topic not in _VALID_TOPICS:
            logger.warning("AI 토픽 유효하지 않음: %s (원문: %s)", topic, raw[:100])
            return None
        if not isinstance(severity, (int, float)) or severity < 0 or severity > 100:
            logger.warning("AI severity 범위 초과: %s (원문: %s)", severity, raw[:100])
            return None

        severity = max(0, min(100, int(severity)))

        # sub_topic 추출 (유효하지 않으면 general)
        raw_sub = data.get("sub_topic", "general").strip().lower()
        valid_subs = _VALID_SUB_TOPICS.get(topic)
        sub_topic = raw_sub if (valid_subs and raw_sub in valid_subs) else "general"

        return topic, sub_topic, severity

    except Exception:
        logger.exception("AI 분류 실패 (제목: %s)", title[:80])
        return None

# ── Sub-topic 키워드 기반 분류 ──────────────────────────────────────────────

_SUB_TOPIC_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "conflict": {
        "nk_provocation": [
            "north korea", "pyongyang", "kim jong", "icbm", "hwasong",
            "ballistic missile test", "nuclear test", "slbm",
            "북한", "김정은", "탄도미사일", "핵실험",
        ],
        "military_exercise": [
            "military exercise", "joint exercise", "drill", "war games",
            "freedom shield", "ulchi", "combined exercise", "live fire",
            "합동훈련", "연합훈련", "훈련",
        ],
        "geopolitical_response": [
            "government response", "defense posture", "대응", "조치",
            "성명", "규탄", "diplomatic response",
        ],
        "active_combat": [
            "casualties", "killed", "airstrike", "bombardment",
            "offensive", "ground operation", "shelling", "frontline", "combat",
        ],
        "arms_transfer": [
            "arms transfer", "weapons transfer", "military aid",
            "arms deal", "defense contract",
        ],
    },
    "sanctions": {
        "oil_energy": [
            "oil price", "crude oil", "brent", "opec",
            "energy crisis", "petroleum", "barrel",
        ],
        "trade_tariff": [
            "tariff", "trade war", "trade ban", "export control",
        ],
    },
}


def _classify_sub_topic(text: str, topic: str) -> str:
    """키워드 기반 sub_topic 분류 (AI 실패 시 폴백)."""
    sub_map = _SUB_TOPIC_KEYWORDS.get(topic)
    if not sub_map:
        return "general"

    lower = text.lower()
    best_sub = "general"
    best_count = 0

    for sub, keywords in sub_map.items():
        count = sum(1 for kw in keywords if kw in lower)
        if count > best_count:
            best_count = count
            best_sub = sub

    return best_sub


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
        # 추가: 군사작전 변형
        "airstrikes", "ground invasion", "naval strike",
    ],
    "terror": [
        "terror", "terrorist", "hostage", "isis", "al-qaeda", "extremist",
        "jihadist", "suicide bomb", "attack on civilians", "beheading",
        "assassination", "shooting", "stabbing", "kidnapping",
        # 총기 · 폭탄
        "mass shooting", "school shooting", "active shooter", "gunman",
        "lone wolf", "vehicle attack", "ramming", "pipe bomb", "ied",
        "improvised explosive", "car bomb", "truck bomb",
        # 암살
        "assassination attempt", "political assassination", "targeted killing",
        "death squad", "execution", "extrajudicial",
        "hostage crisis", "hostage situation", "bomb threat",
        "domestic terrorism", "bioterrorism", "anthrax",
    ],
    # REMOVED from terror (일반 범죄 → 오분류 원인):
    # "murder" (일반 살인), "cartel" (마약조직), "drug lord",
    # "drug trafficking", "organized crime", "gang"
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
        # 에너지/원자재 급등 · 시장 충격
        "oil price", "oil surge", "gas spike", "barrel",
        "stock plunge", "market crash", "economic shock",
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
        # 지도자 교체 · 정치 전환
        "supreme leader", "successor", "appointed leader",
        "assembly of experts", "political transition", "regime change",
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
    ("anniversary", -8), ("memorial", -10), ("years ago", -10),
    ("looking back", -8), ("retrospective", -8),
    # 추모/기념 (활성 분쟁 아님)
    ("commemorate", -10), ("commemorat", -10), ("remembrance", -10),
    ("tribute", -10), ("in memory of", -12), ("memorialize", -12),
    ("museum", -10), ("monument", -8), ("memorial service", -15),
    ("vigil", -8), ("honor the victims", -10), ("pay respects", -8),
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
    "haifa": ("IL", 32.79, 34.99),
    "jerusalem": ("IL", 31.77, 35.23),
    "beer sheva": ("IL", 31.25, 34.79),
    "beersheba": ("IL", 31.25, 34.79),
    "netanya": ("IL", 32.33, 34.86),
    "ashkelon": ("IL", 31.67, 34.57),
    "ashdod": ("IL", 31.80, 34.65),
    "idf": ("IL", 31.5, 34.8),
    "iron dome": ("IL", 31.5, 34.8),
    "negev": ("IL", 30.85, 34.78),
    "golan": ("IL", 33.0, 35.75),
    "west bank": ("PS", 31.95, 35.25),
    "rafah": ("PS", 31.28, 34.25),
    "khan younis": ("PS", 31.35, 34.30),
    "khan yunis": ("PS", 31.35, 34.30),
    "jabalia": ("PS", 31.53, 34.48),
    "hamas": ("PS", 31.5, 34.47),
    "hezbollah": ("LB", 33.9, 35.5),
    "gaza": ("PS", 31.5, 34.47),
    "palestine": ("PS", 31.9, 35.3),
    "palestinian": ("PS", 31.9, 35.3),
    "iran": ("IR", 32.0, 53.0),
    "iranian": ("IR", 32.0, 53.0),
    "tehran": ("IR", 35.69, 51.39),
    "isfahan": ("IR", 32.65, 51.68),
    "esfahan": ("IR", 32.65, 51.68),
    "bushehr": ("IR", 28.97, 50.84),
    "tabriz": ("IR", 38.08, 46.29),
    "shiraz": ("IR", 29.59, 52.58),
    "mashhad": ("IR", 36.30, 59.60),
    "qom": ("IR", 34.64, 50.88),
    "ahvaz": ("IR", 31.32, 48.67),
    "bandar abbas": ("IR", 27.19, 56.27),
    "natanz": ("IR", 33.51, 51.92),
    "fordow": ("IR", 34.88, 51.59),
    "khamenei": ("IR", 32.0, 53.0),
    "irgc": ("IR", 32.0, 53.0),
    "persian gulf": ("IR", 26.5, 52.0),
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
    # ── 7순위: null-country 클러스터 분석 보강 (2026-03-15) ────────────────────
    # 호르무즈 해협 → 이란
    "hormuz": ("IR", 27.0, 56.5),
    "strait of hormuz": ("IR", 27.0, 56.5),
    "hormuz strait": ("IR", 27.0, 56.5),
    "호르무즈": ("IR", 27.0, 56.5),
    # 터키 변형
    "türkiye": ("TR", 39.0, 35.0),
    # 러시아 지역
    "kursk": ("RU", 51.73, 36.19),
    "bryansk": ("RU", 53.24, 34.36),
    "belgorod": ("RU", 50.59, 36.59),
    "rostov": ("RU", 47.24, 39.71),
    "crimea": ("RU", 44.95, 34.1),
    "kuril": ("RU", 46.0, 152.0),
    "kuril islands": ("RU", 46.0, 152.0),
    "크림": ("RU", 44.95, 34.1),
    "쿠릴": ("RU", 46.0, 152.0),
    # 우크라이나 지역
    "donetsk": ("UA", 48.0, 37.8),
    "zaporizhzhia": ("UA", 47.84, 35.14),
    "kherson": ("UA", 46.64, 32.62),
    "odesa": ("UA", 46.47, 30.73),
    "odessa": ("UA", 46.47, 30.73),
    "lviv": ("UA", 49.84, 24.03),
    "도네츠크": ("UA", 48.0, 37.8),
    "자포리자": ("UA", 47.84, 35.14),
    "헤르손": ("UA", 46.64, 32.62),
    # 레바논 지역
    "bekaa": ("LB", 33.85, 35.9),
    "beqaa": ("LB", 33.85, 35.9),
    "baalbek": ("LB", 34.0, 36.2),
    "tyre": ("LB", 33.27, 35.2),
    "sidon": ("LB", 33.56, 35.37),
    # tripoli → LY(리비아)로 기존 매핑 유지 (분쟁 맥락에서 리비아 트리폴리가 더 빈번)
    "nabatieh": ("LB", 33.38, 35.48),
    # 파키스탄 지역
    "islamabad": ("PK", 33.69, 73.04),
    "karachi": ("PK", 24.86, 67.01),
    "lahore": ("PK", 31.55, 74.35),
    "peshawar": ("PK", 34.01, 71.58),
    "sindh": ("PK", 26.0, 68.5),
    "khyber pakhtunkhwa": ("PK", 34.5, 71.5),
    "khyber": ("PK", 34.5, 71.5),
    "waziristan": ("PK", 32.3, 69.9),
    "balochistan": ("PK", 28.0, 65.0),
    "lakki marwat": ("PK", 32.61, 70.91),
    # 일본 지역
    "fukushima": ("JP", 37.75, 140.47),
    "osaka": ("JP", 34.69, 135.5),
    "okinawa": ("JP", 26.33, 127.8),
    # 호주 지역
    "queensland": ("AU", -22.0, 144.0),
    "sydney": ("AU", -33.87, 151.21),
    "melbourne": ("AU", -37.81, 144.96),
    "canberra": ("AU", -35.28, 149.13),
    # 케냐 지역
    "nairobi": ("KE", -1.29, 36.82),
    "mombasa": ("KE", -4.04, 39.67),
    # 뉴질랜드 지역
    "kermadec": ("NZ", -29.25, -177.9),
    "kermadec islands": ("NZ", -29.25, -177.9),
    "wellington": ("NZ", -41.29, 174.78),
    "auckland": ("NZ", -36.85, 174.76),
    # 미국 주/도시 추가
    "california": ("US", 36.78, -119.42),
    "chicago": ("US", 41.88, -87.63),
    "seattle": ("US", 47.61, -122.33),
    "detroit": ("US", 42.33, -83.05),
    "minneapolis": ("US", 44.98, -93.27),
    "dallas": ("US", 32.78, -96.8),
    "houston": ("US", 29.76, -95.37),
    "virginia": ("US", 37.43, -78.66),
    "kentucky": ("US", 37.84, -84.27),
    "connecticut": ("US", 41.6, -72.7),
    "denver": ("US", 39.74, -104.99),
    "hawaii": ("US", 19.9, -155.58),
    "alaska": ("US", 64.2, -152.49),
    "ohio": ("US", 40.42, -82.91),
    # "georgia" → GE(코카서스)로 기존 매핑 유지 (분쟁 뉴스 맥락에서 대부분 코카서스 조지아)
    "arizona": ("US", 34.05, -111.09),
    "michigan": ("US", 44.31, -85.6),
    "colorado": ("US", 39.55, -105.78),
    "san francisco": ("US", 37.77, -122.42),
    "boston": ("US", 42.36, -71.06),
    "philadelphia": ("US", 39.95, -75.17),
    "atlanta": ("US", 33.75, -84.39),
    "miami": ("US", 25.76, -80.19),
    "phoenix": ("US", 33.45, -112.07),
    # 영국 지역 추가
    "birmingham": ("GB", 52.49, -1.9),
    "liverpool": ("GB", 53.41, -2.98),
    "edinburgh": ("GB", 55.95, -3.19),
    "belfast": ("GB", 54.6, -5.93),
    "durham": ("GB", 54.78, -1.58),
    "wales": ("GB", 52.13, -3.78),
    # 이라크 지역
    "mosul": ("IQ", 36.34, 43.13),
    "erbil": ("IQ", 36.19, 44.01),
    "basra": ("IQ", 30.51, 47.81),
    "kirkuk": ("IQ", 35.47, 44.39),
    "모술": ("IQ", 36.34, 43.13),
    # 시리아 지역
    "aleppo": ("SY", 36.2, 37.17),
    "homs": ("SY", 34.73, 36.72),
    "idlib": ("SY", 35.93, 36.63),
    "deir ez-zor": ("SY", 35.33, 40.14),
    "알레포": ("SY", 36.2, 37.17),
    # 수단 지역
    "khartoum": ("SD", 15.5, 32.56),
    "darfur": ("SD", 13.5, 25.0),
    "port sudan": ("SD", 19.62, 37.22),
    "하르툼": ("SD", 15.5, 32.56),
    "다르푸르": ("SD", 13.5, 25.0),
    # 예멘 지역
    "sanaa": ("YE", 15.35, 44.21),
    "aden": ("YE", 12.8, 45.04),
    "houthi": ("YE", 15.5, 47.5),
    "houthis": ("YE", 15.5, 47.5),
    "후티": ("YE", 15.5, 47.5),
    # 소말리아 지역
    "mogadishu": ("SO", 2.05, 45.34),
    "al-shabaab": ("SO", 2.0, 45.0),
    "al shabaab": ("SO", 2.0, 45.0),
    # 에티오피아 지역
    "addis ababa": ("ET", 9.02, 38.75),
    "tigray": ("ET", 13.5, 39.5),
    # 인도 지역
    "new delhi": ("IN", 28.61, 77.21),
    "delhi": ("IN", 28.61, 77.21),
    "mumbai": ("IN", 19.08, 72.88),
    "kashmir": ("IN", 34.08, 74.8),
    "카슈미르": ("IN", 34.08, 74.8),
    # 중국 지역
    "shanghai": ("CN", 31.23, 121.47),
    "hong kong": ("CN", 22.32, 114.17),
    "xinjiang": ("CN", 41.75, 84.77),
    "tibet": ("CN", 29.65, 91.13),
    "guangzhou": ("CN", 23.13, 113.26),
    "홍콩": ("CN", 22.32, 114.17),
    "신장": ("CN", 41.75, 84.77),
    # 터키 지역
    "istanbul": ("TR", 41.01, 28.98),
    "akkuyu": ("TR", 36.14, 33.53),
    "이스탄불": ("TR", 41.01, 28.98),
    # 나이지리아 지역
    "lagos": ("NG", 6.52, 3.38),
    "abuja": ("NG", 9.06, 7.49),
    "boko haram": ("NG", 11.85, 13.16),
    # 리비아 지역
    "benghazi": ("LY", 32.12, 20.09),
    "tripoli": ("LY", 32.9, 13.18),
    # 미얀마 추가
    "yangon": ("MM", 16.87, 96.2),
    "naypyidaw": ("MM", 19.76, 96.07),
    # 아프가니스탄 지역
    "kandahar": ("AF", 31.61, 65.71),
    "taliban": ("AF", 33.0, 65.0),
    "탈레반": ("AF", 33.0, 65.0),
    # 멕시코 추가
    "mexico city": ("MX", 19.43, -99.13),
    "sinaloa": ("MX", 24.8, -107.39),
    # 콜롬비아 추가
    "bogota": ("CO", 4.71, -74.07),
    "medellin": ("CO", 6.24, -75.57),
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
    "예루살렘": ("IL", 31.77, 35.23),
    "하이파": ("IL", 32.79, 34.99),
    "텔아비브": ("IL", 32.08, 34.78),
    "팔레스타인": ("PS", 31.9, 35.3),
    "가자": ("PS", 31.5, 34.47),
    "하마스": ("PS", 31.5, 34.47),
    "헤즈볼라": ("LB", 33.9, 35.5),
    "서안지구": ("PS", 31.95, 35.25),
    "이란": ("IR", 32.0, 53.0),
    "테헤란": ("IR", 35.69, 51.39),
    "이스파한": ("IR", 32.65, 51.68),
    "부셰르": ("IR", 28.97, 50.84),
    "혁명수비대": ("IR", 32.0, 53.0),
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
    # ══════════════════════════════════════════════════════════════════════════
    # 전세계 확장: UN 회원국 누락분 보완 (195개국 완성)
    # ══════════════════════════════════════════════════════════════════════════

    # ── 유럽 (누락분) ──────────────────────────────────────────────────────────
    # 아일랜드 IE
    "ireland": ("IE", 53.35, -6.26),
    "irish": ("IE", 53.35, -6.26),
    "dublin": ("IE", 53.35, -6.26),
    "아일랜드": ("IE", 53.35, -6.26),
    # 아이슬란드 IS
    "iceland": ("IS", 64.15, -21.94),
    "icelandic": ("IS", 64.15, -21.94),
    "reykjavik": ("IS", 64.15, -21.94),
    "아이슬란드": ("IS", 64.15, -21.94),
    # 룩셈부르크 LU
    "luxembourg": ("LU", 49.61, 6.13),
    "luxembourgish": ("LU", 49.61, 6.13),
    "룩셈부르크": ("LU", 49.61, 6.13),
    # 리히텐슈타인 LI
    "liechtenstein": ("LI", 47.17, 9.51),
    "vaduz": ("LI", 47.14, 9.52),
    "리히텐슈타인": ("LI", 47.17, 9.51),
    # 모나코 MC
    "monaco": ("MC", 43.73, 7.42),
    "monegasque": ("MC", 43.73, 7.42),
    "모나코": ("MC", 43.73, 7.42),
    # 몰타 MT
    "malta": ("MT", 35.9, 14.51),
    "maltese": ("MT", 35.9, 14.51),
    "valletta": ("MT", 35.9, 14.51),
    "몰타": ("MT", 35.9, 14.51),
    # 알바니아 AL
    "albania": ("AL", 41.33, 19.82),
    "albanian": ("AL", 41.33, 19.82),
    "tirana": ("AL", 41.33, 19.82),
    "알바니아": ("AL", 41.33, 19.82),
    # 북마케도니아 MK
    "north macedonia": ("MK", 41.99, 21.43),
    "macedonia": ("MK", 41.99, 21.43),
    "macedonian": ("MK", 41.99, 21.43),
    "skopje": ("MK", 42.0, 21.43),
    "북마케도니아": ("MK", 41.99, 21.43),
    "마케도니아": ("MK", 41.99, 21.43),
    # 몬테네그로 ME
    "montenegro": ("ME", 42.44, 19.26),
    "montenegrin": ("ME", 42.44, 19.26),
    "podgorica": ("ME", 42.44, 19.26),
    "몬테네그로": ("ME", 42.44, 19.26),
    # 슬로바키아 SK
    "slovakia": ("SK", 48.15, 17.11),
    "slovak": ("SK", 48.15, 17.11),
    "bratislava": ("SK", 48.15, 17.11),
    "슬로바키아": ("SK", 48.15, 17.11),
    # 슬로베니아 SI
    "slovenia": ("SI", 46.05, 14.51),
    "slovenian": ("SI", 46.05, 14.51),
    "ljubljana": ("SI", 46.05, 14.51),
    "슬로베니아": ("SI", 46.05, 14.51),
    # 불가리아 BG
    "bulgaria": ("BG", 42.7, 23.32),
    "bulgarian": ("BG", 42.7, 23.32),
    "sofia": ("BG", 42.7, 23.32),
    "불가리아": ("BG", 42.7, 23.32),
    # 리투아니아 LT
    "lithuania": ("LT", 54.69, 25.28),
    "lithuanian": ("LT", 54.69, 25.28),
    "vilnius": ("LT", 54.69, 25.28),
    "리투아니아": ("LT", 54.69, 25.28),
    # 라트비아 LV
    "latvia": ("LV", 56.95, 24.11),
    "latvian": ("LV", 56.95, 24.11),
    "riga": ("LV", 56.95, 24.11),
    "라트비아": ("LV", 56.95, 24.11),
    # 키프로스 CY
    "cyprus": ("CY", 35.17, 33.36),
    "cypriot": ("CY", 35.17, 33.36),
    "nicosia": ("CY", 35.17, 33.36),
    "키프로스": ("CY", 35.17, 33.36),
    # 안도라 AD
    "andorra": ("AD", 42.51, 1.52),
    "andorran": ("AD", 42.51, 1.52),
    "andorra la vella": ("AD", 42.51, 1.52),
    "안도라": ("AD", 42.51, 1.52),
    # 산마리노 SM
    "san marino": ("SM", 43.94, 12.46),
    "sammarinese": ("SM", 43.94, 12.46),
    "산마리노": ("SM", 43.94, 12.46),
    # 바티칸 VA
    "vatican": ("VA", 41.9, 12.45),
    "vatican city": ("VA", 41.9, 12.45),
    "holy see": ("VA", 41.9, 12.45),
    "바티칸": ("VA", 41.9, 12.45),
    # 몰도바 MD
    "moldova": ("MD", 47.01, 28.86),
    "moldovan": ("MD", 47.01, 28.86),
    "chisinau": ("MD", 47.01, 28.86),
    "몰도바": ("MD", 47.01, 28.86),
    # 보스니아 헤르체고비나 BA
    "bosnia": ("BA", 43.86, 18.41),
    "bosnian": ("BA", 43.86, 18.41),
    "bosnia and herzegovina": ("BA", 43.86, 18.41),
    "sarajevo": ("BA", 43.86, 18.41),
    "보스니아": ("BA", 43.86, 18.41),
    # 코소보 XK
    "kosovo": ("XK", 42.66, 21.17),
    "kosovar": ("XK", 42.66, 21.17),
    "pristina": ("XK", 42.66, 21.17),
    "코소보": ("XK", 42.66, 21.17),
    # 우크라이나/러시아/벨라루스/에스토니아/핀란드/폴란드/루마니아/체코/헝가리/세르비아/크로아티아 → 기존 등록

    # ── 아프리카 (누락분) ──────────────────────────────────────────────────────
    # 앙골라 AO
    "angola": ("AO", -8.84, 13.23),
    "angolan": ("AO", -8.84, 13.23),
    "luanda": ("AO", -8.84, 13.23),
    "앙골라": ("AO", -8.84, 13.23),
    # 베냉 BJ
    "benin": ("BJ", 6.5, 2.63),
    "beninese": ("BJ", 6.5, 2.63),
    "porto-novo": ("BJ", 6.5, 2.63),
    "cotonou": ("BJ", 6.37, 2.39),
    "베냉": ("BJ", 6.5, 2.63),
    # 보츠와나 BW
    "botswana": ("BW", -24.65, 25.91),
    "batswana": ("BW", -24.65, 25.91),
    "gaborone": ("BW", -24.65, 25.91),
    "보츠와나": ("BW", -24.65, 25.91),
    # 부르키나파소 BF
    "burkina faso": ("BF", 12.37, -1.52),
    "burkinabe": ("BF", 12.37, -1.52),
    "ouagadougou": ("BF", 12.37, -1.52),
    "부르키나파소": ("BF", 12.37, -1.52),
    # 카보베르데 CV
    "cabo verde": ("CV", 14.93, -23.51),
    "cape verde": ("CV", 14.93, -23.51),
    "cape verdean": ("CV", 14.93, -23.51),
    "praia": ("CV", 14.93, -23.51),
    "카보베르데": ("CV", 14.93, -23.51),
    # 중앙아프리카공화국 CF
    "central african republic": ("CF", 4.36, 18.56),
    "bangui": ("CF", 4.36, 18.56),
    "중앙아프리카": ("CF", 4.36, 18.56),
    # 코트디부아르 CI
    "ivory coast": ("CI", 5.32, -4.03),
    "cote d'ivoire": ("CI", 5.32, -4.03),
    "ivorian": ("CI", 5.32, -4.03),
    "abidjan": ("CI", 5.36, -4.01),
    "yamoussoukro": ("CI", 6.82, -5.28),
    "코트디부아르": ("CI", 5.32, -4.03),
    # 콩고민주공화국 CD
    "democratic republic of the congo": ("CD", -4.32, 15.31),
    "dr congo": ("CD", -4.32, 15.31),
    "drc": ("CD", -4.32, 15.31),
    "kinshasa": ("CD", -4.32, 15.31),
    "콩고민주공화국": ("CD", -4.32, 15.31),
    # 콩고공화국 CG
    "republic of the congo": ("CG", -4.27, 15.28),
    "congo-brazzaville": ("CG", -4.27, 15.28),
    "brazzaville": ("CG", -4.27, 15.28),
    "콩고": ("CG", -4.27, 15.28),
    # 지부티 DJ
    "djibouti": ("DJ", 11.59, 43.15),
    "djiboutian": ("DJ", 11.59, 43.15),
    "지부티": ("DJ", 11.59, 43.15),
    # 적도기니 GQ
    "equatorial guinea": ("GQ", 3.75, 8.78),
    "equatoguinean": ("GQ", 3.75, 8.78),
    "malabo": ("GQ", 3.75, 8.78),
    "적도기니": ("GQ", 3.75, 8.78),
    # 에리트레아 ER
    "eritrea": ("ER", 15.33, 38.93),
    "eritrean": ("ER", 15.33, 38.93),
    "asmara": ("ER", 15.33, 38.93),
    "에리트레아": ("ER", 15.33, 38.93),
    # 에스와티니 SZ
    "eswatini": ("SZ", -26.31, 31.13),
    "swaziland": ("SZ", -26.31, 31.13),
    "swazi": ("SZ", -26.31, 31.13),
    "mbabane": ("SZ", -26.31, 31.13),
    "에스와티니": ("SZ", -26.31, 31.13),
    # 가봉 GA
    "gabon": ("GA", 0.39, 9.45),
    "gabonese": ("GA", 0.39, 9.45),
    "libreville": ("GA", 0.39, 9.45),
    "가봉": ("GA", 0.39, 9.45),
    # 감비아 GM
    "gambia": ("GM", 13.45, -16.58),
    "gambian": ("GM", 13.45, -16.58),
    "banjul": ("GM", 13.45, -16.58),
    "감비아": ("GM", 13.45, -16.58),
    # 기니 GN
    "guinea": ("GN", 9.64, -13.58),
    "guinean": ("GN", 9.64, -13.58),
    "conakry": ("GN", 9.64, -13.58),
    "기니": ("GN", 9.64, -13.58),
    # 기니비사우 GW
    "guinea-bissau": ("GW", 11.86, -15.6),
    "bissau": ("GW", 11.86, -15.6),
    "기니비사우": ("GW", 11.86, -15.6),
    # 레소토 LS
    "lesotho": ("LS", -29.31, 27.48),
    "basotho": ("LS", -29.31, 27.48),
    "maseru": ("LS", -29.31, 27.48),
    "레소토": ("LS", -29.31, 27.48),
    # 라이베리아 LR
    "liberia": ("LR", 6.3, -10.8),
    "liberian": ("LR", 6.3, -10.8),
    "monrovia": ("LR", 6.3, -10.8),
    "라이베리아": ("LR", 6.3, -10.8),
    # 마다가스카르 MG
    "madagascar": ("MG", -18.88, 47.51),
    "malagasy": ("MG", -18.88, 47.51),
    "antananarivo": ("MG", -18.88, 47.51),
    "마다가스카르": ("MG", -18.88, 47.51),
    # 말라위 MW
    "malawi": ("MW", -13.97, 33.79),
    "malawian": ("MW", -13.97, 33.79),
    "lilongwe": ("MW", -13.97, 33.79),
    "말라위": ("MW", -13.97, 33.79),
    # 모리타니 MR
    "mauritania": ("MR", 18.09, -15.98),
    "mauritanian": ("MR", 18.09, -15.98),
    "nouakchott": ("MR", 18.09, -15.98),
    "모리타니": ("MR", 18.09, -15.98),
    # 모리셔스 MU
    "mauritius": ("MU", -20.16, 57.5),
    "mauritian": ("MU", -20.16, 57.5),
    "port louis": ("MU", -20.16, 57.5),
    "모리셔스": ("MU", -20.16, 57.5),
    # 나미비아 NA
    "namibia": ("NA", -22.56, 17.08),
    "namibian": ("NA", -22.56, 17.08),
    "windhoek": ("NA", -22.56, 17.08),
    "나미비아": ("NA", -22.56, 17.08),
    # 르완다 RW
    "rwanda": ("RW", -1.94, 29.87),
    "rwandan": ("RW", -1.94, 29.87),
    "kigali": ("RW", -1.94, 29.87),
    "르완다": ("RW", -1.94, 29.87),
    # 상투메프린시페 ST
    "sao tome and principe": ("ST", 0.19, 6.61),
    "sao tome": ("ST", 0.19, 6.61),
    "상투메프린시페": ("ST", 0.19, 6.61),
    # 세이셸 SC
    "seychelles": ("SC", -4.68, 55.49),
    "seychellois": ("SC", -4.68, 55.49),
    "victoria": ("SC", -4.62, 55.45),
    "세이셸": ("SC", -4.68, 55.49),
    # 시에라리온 SL
    "sierra leone": ("SL", 8.48, -13.23),
    "sierra leonean": ("SL", 8.48, -13.23),
    "freetown": ("SL", 8.48, -13.23),
    "시에라리온": ("SL", 8.48, -13.23),
    # 남수단 SS
    "south sudan": ("SS", 4.85, 31.58),
    "south sudanese": ("SS", 4.85, 31.58),
    "juba": ("SS", 4.85, 31.58),
    "남수단": ("SS", 4.85, 31.58),
    # 토고 TG
    "togo": ("TG", 6.14, 1.21),
    "togolese": ("TG", 6.14, 1.21),
    "lome": ("TG", 6.14, 1.21),
    "토고": ("TG", 6.14, 1.21),
    # 잠비아 ZM
    "zambia": ("ZM", -15.39, 28.32),
    "zambian": ("ZM", -15.39, 28.32),
    "lusaka": ("ZM", -15.39, 28.32),
    "잠비아": ("ZM", -15.39, 28.32),
    # 코모로 KM
    "comoros": ("KM", -11.7, 43.26),
    "comorian": ("KM", -11.7, 43.26),
    "moroni": ("KM", -11.7, 43.26),
    "코모로": ("KM", -11.7, 43.26),

    # ── 아메리카 (누락분) ──────────────────────────────────────────────────────
    # 코스타리카 CR
    "costa rica": ("CR", 9.93, -84.09),
    "costa rican": ("CR", 9.93, -84.09),
    "san jose": ("CR", 9.93, -84.09),
    "코스타리카": ("CR", 9.93, -84.09),
    # 도미니카공화국 DO
    "dominican republic": ("DO", 18.47, -69.9),
    "dominican": ("DO", 18.47, -69.9),
    "santo domingo": ("DO", 18.47, -69.9),
    "도미니카공화국": ("DO", 18.47, -69.9),
    # 엘살바도르 SV
    "el salvador": ("SV", 13.69, -89.19),
    "salvadoran": ("SV", 13.69, -89.19),
    "san salvador": ("SV", 13.69, -89.19),
    "엘살바도르": ("SV", 13.69, -89.19),
    # 과테말라 GT
    "guatemala": ("GT", 14.63, -90.51),
    "guatemalan": ("GT", 14.63, -90.51),
    "guatemala city": ("GT", 14.63, -90.51),
    "과테말라": ("GT", 14.63, -90.51),
    # 가이아나 GY
    "guyana": ("GY", 6.8, -58.16),
    "guyanese": ("GY", 6.8, -58.16),
    "georgetown": ("GY", 6.8, -58.16),
    "가이아나": ("GY", 6.8, -58.16),
    # 온두라스 HN
    "honduras": ("HN", 14.1, -87.22),
    "honduran": ("HN", 14.1, -87.22),
    "tegucigalpa": ("HN", 14.1, -87.22),
    "온두라스": ("HN", 14.1, -87.22),
    # 자메이카 JM
    "jamaica": ("JM", 18.11, -77.3),
    "jamaican": ("JM", 18.11, -77.3),
    "kingston": ("JM", 18.0, -76.79),
    "자메이카": ("JM", 18.11, -77.3),
    # 니카라과 NI
    "nicaragua": ("NI", 12.11, -86.27),
    "nicaraguan": ("NI", 12.11, -86.27),
    "managua": ("NI", 12.11, -86.27),
    "니카라과": ("NI", 12.11, -86.27),
    # 파나마 PA
    "panama": ("PA", 8.98, -79.52),
    "panamanian": ("PA", 8.98, -79.52),
    "panama city": ("PA", 8.98, -79.52),
    "파나마": ("PA", 8.98, -79.52),
    # 파라과이 PY
    "paraguay": ("PY", -25.26, -57.58),
    "paraguayan": ("PY", -25.26, -57.58),
    "asuncion": ("PY", -25.26, -57.58),
    "파라과이": ("PY", -25.26, -57.58),
    # 수리남 SR
    "suriname": ("SR", 5.85, -55.17),
    "surinamese": ("SR", 5.85, -55.17),
    "paramaribo": ("SR", 5.85, -55.17),
    "수리남": ("SR", 5.85, -55.17),
    # 트리니다드토바고 TT
    "trinidad and tobago": ("TT", 10.65, -61.5),
    "trinidad": ("TT", 10.65, -61.5),
    "trinidadian": ("TT", 10.65, -61.5),
    "port of spain": ("TT", 10.65, -61.5),
    "트리니다드토바고": ("TT", 10.65, -61.5),
    # 우루과이 UY
    "uruguay": ("UY", -34.88, -56.18),
    "uruguayan": ("UY", -34.88, -56.18),
    "montevideo": ("UY", -34.88, -56.18),
    "우루과이": ("UY", -34.88, -56.18),
    # 앤티가바부다 AG
    "antigua and barbuda": ("AG", 17.12, -61.85),
    "antigua": ("AG", 17.12, -61.85),
    "antiguan": ("AG", 17.12, -61.85),
    "st. john's": ("AG", 17.12, -61.85),
    "앤티가바부다": ("AG", 17.12, -61.85),
    # 바베이도스 BB
    "barbados": ("BB", 13.1, -59.61),
    "barbadian": ("BB", 13.1, -59.61),
    "bridgetown": ("BB", 13.1, -59.61),
    "바베이도스": ("BB", 13.1, -59.61),
    # 바하마 BS
    "bahamas": ("BS", 25.03, -77.4),
    "bahamian": ("BS", 25.03, -77.4),
    "nassau": ("BS", 25.06, -77.35),
    "바하마": ("BS", 25.03, -77.4),
    # 벨리즈 BZ
    "belize": ("BZ", 17.25, -88.77),
    "belizean": ("BZ", 17.25, -88.77),
    "belmopan": ("BZ", 17.25, -88.77),
    "벨리즈": ("BZ", 17.25, -88.77),
    # 도미니카 DM
    "dominica": ("DM", 15.3, -61.39),
    "roseau": ("DM", 15.3, -61.39),
    "도미니카연방": ("DM", 15.3, -61.39),
    # 그레나다 GD
    "grenada": ("GD", 12.06, -61.75),
    "grenadian": ("GD", 12.06, -61.75),
    "st. george's": ("GD", 12.06, -61.75),
    "그레나다": ("GD", 12.06, -61.75),
    # 세인트키츠네비스 KN
    "saint kitts and nevis": ("KN", 17.3, -62.73),
    "saint kitts": ("KN", 17.3, -62.73),
    "basseterre": ("KN", 17.3, -62.73),
    "세인트키츠네비스": ("KN", 17.3, -62.73),
    # 세인트루시아 LC
    "saint lucia": ("LC", 13.91, -60.98),
    "st lucia": ("LC", 13.91, -60.98),
    "castries": ("LC", 14.01, -61.0),
    "세인트루시아": ("LC", 13.91, -60.98),
    # 세인트빈센트그레나딘 VC
    "saint vincent and the grenadines": ("VC", 13.16, -61.23),
    "saint vincent": ("VC", 13.16, -61.23),
    "kingstown": ("VC", 13.16, -61.23),
    "세인트빈센트그레나딘": ("VC", 13.16, -61.23),

    # ── 아시아·태평양 (누락분) ─────────────────────────────────────────────────
    # 브루나이 BN
    "brunei": ("BN", 4.94, 114.95),
    "bruneian": ("BN", 4.94, 114.95),
    "bandar seri begawan": ("BN", 4.94, 114.95),
    "브루나이": ("BN", 4.94, 114.95),
    # 부탄 BT
    "bhutan": ("BT", 27.47, 89.64),
    "bhutanese": ("BT", 27.47, 89.64),
    "thimphu": ("BT", 27.47, 89.64),
    "부탄": ("BT", 27.47, 89.64),
    # 몰디브 MV
    "maldives": ("MV", 4.18, 73.51),
    "maldivian": ("MV", 4.18, 73.51),
    "male": ("MV", 4.18, 73.51),
    "몰디브": ("MV", 4.18, 73.51),
    # 몽골 MN
    "mongolia": ("MN", 47.92, 106.91),
    "mongolian": ("MN", 47.92, 106.91),
    "ulaanbaatar": ("MN", 47.92, 106.91),
    "몽골": ("MN", 47.92, 106.91),
    # 라오스 LA
    "laos": ("LA", 17.97, 102.63),
    "laotian": ("LA", 17.97, 102.63),
    "vientiane": ("LA", 17.97, 102.63),
    "라오스": ("LA", 17.97, 102.63),
    # 동티모르 TL
    "timor-leste": ("TL", -8.56, 125.57),
    "east timor": ("TL", -8.56, 125.57),
    "timorese": ("TL", -8.56, 125.57),
    "dili": ("TL", -8.56, 125.57),
    "동티모르": ("TL", -8.56, 125.57),
    # 투르크메니스탄 TM
    "turkmenistan": ("TM", 37.96, 58.38),
    "turkmen": ("TM", 37.96, 58.38),
    "ashgabat": ("TM", 37.96, 58.38),
    "투르크메니스탄": ("TM", 37.96, 58.38),
    # 키르기스스탄 KG
    "kyrgyzstan": ("KG", 42.87, 74.59),
    "kyrgyz": ("KG", 42.87, 74.59),
    "bishkek": ("KG", 42.87, 74.59),
    "키르기스스탄": ("KG", 42.87, 74.59),
    # 카자흐스탄 KZ
    "kazakhstan": ("KZ", 51.17, 71.43),
    "kazakh": ("KZ", 51.17, 71.43),
    "astana": ("KZ", 51.17, 71.43),
    "카자흐스탄": ("KZ", 51.17, 71.43),
    # 피지 FJ
    "fiji": ("FJ", -18.14, 178.44),
    "fijian": ("FJ", -18.14, 178.44),
    "suva": ("FJ", -18.14, 178.44),
    "피지": ("FJ", -18.14, 178.44),
    # 키리바시 KI
    "kiribati": ("KI", 1.87, -157.36),
    "i-kiribati": ("KI", 1.87, -157.36),
    "tarawa": ("KI", 1.45, 173.0),
    "키리바시": ("KI", 1.87, -157.36),
    # 마셜제도 MH
    "marshall islands": ("MH", 7.09, 171.38),
    "marshallese": ("MH", 7.09, 171.38),
    "majuro": ("MH", 7.09, 171.38),
    "마셜제도": ("MH", 7.09, 171.38),
    # 미크로네시아 FM
    "micronesia": ("FM", 6.91, 158.16),
    "micronesian": ("FM", 6.91, 158.16),
    "palikir": ("FM", 6.91, 158.16),
    "미크로네시아": ("FM", 6.91, 158.16),
    # 나우루 NR
    "nauru": ("NR", -0.52, 166.93),
    "nauruan": ("NR", -0.52, 166.93),
    "나우루": ("NR", -0.52, 166.93),
    # 팔라우 PW
    "palau": ("PW", 7.51, 134.58),
    "palauan": ("PW", 7.51, 134.58),
    "ngerulmud": ("PW", 7.5, 134.62),
    "팔라우": ("PW", 7.51, 134.58),
    # 파푸아뉴기니 PG
    "papua new guinea": ("PG", -6.31, 147.18),
    "papuan": ("PG", -6.31, 147.18),
    "port moresby": ("PG", -6.31, 147.18),
    "파푸아뉴기니": ("PG", -6.31, 147.18),
    # 사모아 WS
    "samoa": ("WS", -13.83, -171.76),
    "samoan": ("WS", -13.83, -171.76),
    "apia": ("WS", -13.83, -171.76),
    "사모아": ("WS", -13.83, -171.76),
    # 솔로몬제도 SB
    "solomon islands": ("SB", -9.43, 160.0),
    "honiara": ("SB", -9.43, 160.0),
    "솔로몬제도": ("SB", -9.43, 160.0),
    # 통가 TO
    "tonga": ("TO", -21.21, -175.2),
    "tongan": ("TO", -21.21, -175.2),
    "nukualofa": ("TO", -21.21, -175.2),
    "통가": ("TO", -21.21, -175.2),
    # 투발루 TV
    "tuvalu": ("TV", -8.52, 179.2),
    "tuvaluan": ("TV", -8.52, 179.2),
    "funafuti": ("TV", -8.52, 179.2),
    "투발루": ("TV", -8.52, 179.2),
    # 바누아투 VU
    "vanuatu": ("VU", -17.73, 168.32),
    "ni-vanuatu": ("VU", -17.73, 168.32),
    "port vila": ("VU", -17.73, 168.32),
    "바누아투": ("VU", -17.73, 168.32),

    # ── 한글 국가명 (확장분) ──────────────────────────────────────────────────
    "호주": ("AU", -27.0, 133.0),
    "브라질": ("BR", -14.0, -51.0),
    "캐나다": ("CA", 56.13, -106.35),
    "멕시코": ("MX", 23.0, -102.0),
    "남아프리카": ("ZA", -30.56, 22.94),
    "남아공": ("ZA", -30.56, 22.94),
    "이탈리아": ("IT", 42.83, 12.83),
    "스페인": ("ES", 40.0, -4.0),
    "포르투갈": ("PT", 39.55, -7.86),
    "네덜란드": ("NL", 52.37, 5.23),
    "벨기에": ("BE", 50.85, 4.35),
    "스웨덴": ("SE", 60.13, 18.64),
    "노르웨이": ("NO", 64.5, 17.9),
    "덴마크": ("DK", 56.26, 9.5),
    "스위스": ("CH", 46.82, 8.23),
    "오스트리아": ("AT", 47.52, 14.55),
    "그리스": ("GR", 39.07, 21.82),
    "체코": ("CZ", 49.82, 15.47),
    "헝가리": ("HU", 47.16, 19.5),
    "세르비아": ("RS", 44.02, 21.09),
    "크로아티아": ("HR", 45.1, 15.2),
    "폴란드": ("PL", 51.92, 19.15),
    "루마니아": ("RO", 45.94, 24.97),
    "에스토니아": ("EE", 58.6, 25.01),
    "핀란드": ("FI", 64.0, 26.0),
    "벨라루스": ("BY", 53.71, 27.95),
    "아르메니아": ("AM", 40.07, 45.04),
    "아제르바이잔": ("AZ", 40.14, 47.58),
    "조지아": ("GE", 42.32, 43.36),
    "타지키스탄": ("TJ", 38.86, 71.28),
    "우즈베키스탄": ("UZ", 41.38, 64.59),
    "나이지리아": ("NG", 9.0, 8.0),
    "말리": ("ML", 17.0, -4.0),
    "필리핀": ("PH", 12.88, 121.77),
    "싱가포르": ("SG", 1.35, 103.82),
    "인도네시아": ("ID", -0.79, 113.92),
    "방글라데시": ("BD", 23.68, 90.36),
    "콜롬비아": ("CO", 4.57, -74.3),
    "페루": ("PE", -9.19, -75.02),
    "칠레": ("CL", -35.68, -71.54),
    "아르헨티나": ("AR", -38.42, -63.62),
    "볼리비아": ("BO", -16.29, -63.59),
    "에콰도르": ("EC", -1.83, -78.18),
    "우간다": ("UG", 1.37, 32.29),
    "세네갈": ("SN", 14.5, -14.45),
    "말레이시아": ("MY", 4.21, 101.97),
    "캄보디아": ("KH", 12.57, 104.99),
    "짐바브웨": ("ZW", -20.0, 30.0),
    "탄자니아": ("TZ", -6.37, 34.89),
    "부룬디": ("BI", -3.37, 29.92),
    "모잠비크": ("MZ", -18.67, 35.53),
    "카메룬": ("CM", 7.37, 12.35),
    "차드": ("TD", 15.45, 18.73),
    "니제르": ("NE", 17.61, 8.08),
    "쿠바": ("CU", 21.52, -77.78),
    "네팔": ("NP", 28.39, 84.12),
    "스리랑카": ("LK", 7.87, 80.77),
    "태국": ("TH", 15.87, 100.99),
    "베트남": ("VN", 14.06, 108.28),
    "뉴질랜드": ("NZ", -40.9, 174.89),
    "베네수엘라": ("VE", 8.0, -66.0),
    "아이티": ("HT", 19.0, -72.0),
    "가나": ("GH", 7.95, -1.02),
    "모로코": ("MA", 31.79, -7.09),
    "알제리": ("DZ", 28.03, 1.66),
    "케냐": ("KE", -0.02, 37.91),
}


# ── 데이터 클래스 ────────────────────────────────────────────────────────────

@dataclass
class NormalizeResult:
    title: str
    title_ko: Optional[str]
    body: str
    body_ko: Optional[str]
    topic: str
    sub_topic: str
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
    image_url: Optional[str] = None


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
                  "war",  # 대부분의 "war" 기사는 실제 분쟁
                  "airstrike", "airstrikes", "ground invasion", "naval strike",
                  "military operation",
                  # WMD · 극단적 폭력
                  "icbm", "hypersonic", "chemical attack", "nerve agent",
                  "dirty bomb", "ethnic cleansing", "genocide", "massacre",
                  "carpet bombing", "cluster bomb", "white phosphorus",
                  "scorched earth", "war crime", "crimes against humanity"},
    "terror":    {"terrorist", "suicide bomb", "isis", "al-qaeda", "jihadist",
                  "beheading",
                  "mass shooting", "school shooting", "active shooter",
                  "car bomb", "truck bomb", "ied", "hostage crisis",
                  "assassination attempt", "bioterrorism", "anthrax"},
                  # REMOVED from STRONG (일반 범죄와 혼동):
                  # "shooting" → weak (일반 총기 사건)
                  # "assassination" → weak (정치 사건)
                  # "kidnapping" → weak (범죄)
                  # "hostage" → weak ("hostage crisis"는 유지)
                  # "murder" → 제거 (일반 살인 ≠ 테러)
                  # "cartel", "drug lord" → 제거 (조직범죄 ≠ 테러)
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


# 테러 관련 외교/행정 맥락 — "테러 조직 지정" 같은 기사에서 terror STRONG 키워드 무효화
# (실제 테러 사건이 아닌 외교·행정·사법 조치에 대한 기사)
_TERROR_DIPLOMATIC_CONTEXT: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # 테러 조직 지정/분류/블랙리스트 — 범위 .{0,60}으로 확장
    r"(designat|classif|label|blacklist|delist|list|declar)\w{0,5}\s.{0,60}\b(terrorist|terror)\b",
    r"\b(terrorist|terror)\b.{0,60}(designation|classification|label|listing|blacklist|delist|list\b)",
    r"\b(terrorist|terror)\s+(organization|group|entity|network)\b",
    # 외교적 압박/촉구 맥락
    r"(push|press|urg|call|pressure)\w{0,5}\s.{0,60}(blacklist|designat|classif|label).{0,30}(terrorist|terror)",
    r"(push|press|urg|call|pressure)\w{0,5}\s.{0,60}(terrorist|terror)",
    # 테러 관련 사법/수사 논의 (실제 사건이 아닌 사후 논의)
    r"(prob|investigat|charg|convict|sentenc|tri|acquit)\w{0,5}.{0,40}(terrorism|terror)\s*(link|ties|connection|charge|count)",
    r"(terrorism|terror)\s*(charge|count|conviction|sentence|trial|probe|investigation)",
    # 테러 방지/대응 정책 논의
    r"(counter|anti).?terror",
    r"(terror|terrorist).{0,20}(policy|legislation|law|act|bill|statute|measure)",
    # 정상회담/회의에서 테러 논의
    r"(summit|conference|meeting|talks|diplomats?).{0,40}(terrorist|terror)",
]]


def _has_terror_diplomatic_context(text: str) -> bool:
    """테러 관련 외교/행정/사법 맥락인지 판별. True면 terror STRONG 키워드 무효화."""
    return any(p.search(text) for p in _TERROR_DIPLOMATIC_CONTEXT)


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
    # 추모/기념/박물관 — 활성 분쟁이 아님
    r"(memorial|memorialize|commemorate|commemorat).{0,80}(museum|service|ceremony|event|day|march|park)",
    r"(museum|monument|memorial).{0,80}(honor|remember|tribute|victim|survivor)",
    r"(remembrance|vigil|tribute).{0,80}(held|ceremony|service|gather|candle)",
    r"(in memory of|pay respects|laying wreaths?|wreath.laying)",
]]

# ── 엔터테인먼트/관광 노이즈 패턴 ──────────────────────────────────────────
# K-pop, 아이돌, 관광 등 분쟁 서비스에 무관한 콘텐츠 감지.
# _is_entertainment_noise() 에서 strong conflict 키워드가 없을 때만 필터링됨.
_ENTERTAINMENT_NOISE_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # K-pop 그룹/아이돌
    r"\b(bts|bangtan|blackpink|exo|twice|nct|seventeen|stray kids|aespa|newjeans)\b",
    r"\b(le sserafim|ive\b|txt\b|enhypen|ateez|itzy|mamamoo|red velvet|got7)\b",
    r"\b(g\)?i-?dle|monsta\s*x|super\s*junior|big\s*bang|2ne1|wonder\s*girls|shinee)\b",
    r"\b(k-?pop|k pop|hallyu|한류)\b",
    r"\b(idol|아이돌)\b.{0,60}\b(comeback|tour|concert|album|fan|debut|chart)\b",
    # 컴백/공연/앨범 (엔터테인먼트 맥락)
    r"\b(comeback|컴백)\b.{0,80}\b(stage|무대|concert|콘서트|album|앨범|tour|투어|fan meeting|팬미팅)\b",
    r"\b(concert|콘서트|fan meeting|팬미팅|music festival|음악 축제)\b.{0,60}\b(ticket|sold out|매진|lineup|라인업)\b",
    # 음악 차트/시상식
    r"\b(billboard|melon|spotify|music chart|album chart|gaon|hanteo)\b.{0,40}\b(chart|rank|top|hit|stream)\b",
    # 관광 (위협 문맥 아닌 경우)
    r"\b(tourism|관광)\b.{0,80}\b(boom|revenue|arrivals|industry|visitors|boost|growth|record|increase|증가|호황|수입|활성화)\b",
    r"\b(tourist arrivals|관광객 증가|travel destination|여행지|inbound tourism|방한 관광)\b",
    # 한국 엔터테인먼트/문화 수출
    r"\b(korean wave|문화 수출|cultural export|soft power)\b.{0,60}\b(drama|music|k-?pop|film|movie|entertainment)\b",
    # 연예 뉴스 일반
    r"\b(celebrity|연예인|pop star|가수)\b.{0,60}\b(dating|wedding|marriage|divorce|pregnancy|baby|scandal|comeback)\b",
]]

_RESPONSE_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"정부[의가이]?\s*(대응|발표|입장|조치|방안|성명)",
    r"대응\s*(방안|책|조치|계획|전략)",
    r"외교[부적]\s*(노력|대응|발표|성명)",
    r"(정부|외교부|국방부|대통령실)[이가은는]\s.{0,30}(대응|발표|성명|입장|우려|규탄|촉구)",
    r"government\s+(response|statement|condemn|urge|react|address)",
    r"official\s+(response|statement|position|reaction)",
    r"diplomatic\s+(response|effort|initiative|push)",
    r"(respond|reaction|response)\s+to\s+(crisis|conflict|attack|war|threat)",
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
        hits = sum(1 for kw in keywords if _kw_in_text(kw, text_lower))
        if hits >= 1:
            scores[topic] = hits
    return max(scores, key=lambda t: scores[t]) if scores else None


def _has_non_military_context(text: str) -> bool:
    """비군사 문맥(개인사망·스포츠·엔터)이면 True."""
    for p in _NON_MILITARY_CONTEXT:
        if p.search(text):
            return True
    return False


def _is_entertainment_noise(text: str, title: str | None = None) -> bool:
    """엔터테인먼트/K-pop/관광 노이즈 감지.

    패턴 매칭 후, 강력한 분쟁/테러 키워드가 없으면 노이즈로 판정.
    제목에서 엔터테인먼트 패턴 매칭 시 → 제목에서만 분쟁 키워드 체크
    (뉴스 라운드업에서 "BTS 복귀" + "이란 전쟁" 병기 시 분쟁으로 오분류 방지)
    """
    text_lower = text.lower()
    title_lower = (title or "").lower()

    # 제목에서 엔터테인먼트 패턴 매칭
    title_match = title_lower and any(p.search(title_lower) for p in _ENTERTAINMENT_NOISE_PATTERNS)
    body_match = any(p.search(text_lower) for p in _ENTERTAINMENT_NOISE_PATTERNS)

    if not title_match and not body_match:
        return False

    # 분쟁 키워드 검사 대상: 제목 매칭이면 제목만, 아니면 전체 텍스트
    check_text = title_lower if title_match else text_lower
    for topic in ("conflict", "terror", "coup", "disaster"):
        for kw in _STRONG_KEYWORDS.get(topic, set()):
            if _kw_in_text(kw, check_text):
                return False
    return True


_EN_SUFFIXES = ("s", "es", "ed", "ing", "er", "ers", "ion", "ions", "ment", "ments")


def _kw_in_text(kw: str, text: str) -> bool:
    """단어 경계를 고려한 키워드 매칭. 'coup'이 'coupang'에 매칭되지 않도록.

    영어(ASCII only) 키워드는 일반 접미사(s, es, ed, ing, er, ers, ion, ions,
    ment, ments)가 붙은 변형도 매칭 허용. 한국어/아랍어 등 비-ASCII 키워드는
    기존 엄격 매칭 유지.
    """
    idx = text.find(kw)
    while idx != -1:
        before_ok = idx == 0 or not text[idx - 1].isalnum()
        end = idx + len(kw)
        if before_ok:
            # 정확히 단어 끝이면 바로 매칭
            if end >= len(text) or not text[end].isalnum():
                return True
            # 영어(ASCII) 키워드에 한해 접미사 허용
            if kw.isascii():
                tail = text[end:]
                for sfx in _EN_SUFFIXES:
                    if tail.startswith(sfx):
                        sfx_end = end + len(sfx)
                        if sfx_end >= len(text) or not text[sfx_end].isalnum():
                            return True
        idx = text.find(kw, idx + 1)
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

    terror_diplomatic = _has_terror_diplomatic_context(text_lower)

    for topic, keywords in TOPIC_KEYWORDS.items():
        # 강력 키워드 체크
        strong = _STRONG_KEYWORDS.get(topic, set())
        strong_hits = sum(1 for kw in strong if _kw_in_text(kw, text_lower))
        # 테러 외교 맥락이면 terror STRONG 무효화 (조직 지정/블랙리스트 기사)
        if topic == "terror" and strong_hits and terror_diplomatic:
            strong_hits = 0
        if strong_hits:
            scores[topic] = scores.get(topic, 0) + strong_hits * 3  # 가중치 3배

        # 일반 키워드 체크
        weak_hits = sum(1 for kw in keywords if kw not in strong and _kw_in_text(kw, text_lower))

        # 비군사 문맥이면 conflict/terror weak 키워드 무효화
        if non_military and topic in ("conflict", "terror"):
            weak_hits = 0
        # 테러 외교 맥락이면 terror weak 키워드도 무효화
        if topic == "terror" and terror_diplomatic:
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


def _calculate_severity(text: str, topic: str, title: str | None = None) -> int:
    """
    심각도 산정 (0~100).

    = base(토픽) + keyword_modifier(SEVERITY_UP/DOWN) + casualty_bonus(사상자 수)
    """
    base = TOPIC_BASE_SEVERITY.get(topic, 25)
    text_lower = text.lower()

    # 키워드 보정 (누적 상한 ±40)
    keyword_delta = sum(delta for kw, delta in SEVERITY_UP if _kw_in_text(kw, text_lower))
    keyword_delta += sum(delta for kw, delta in SEVERITY_DOWN if _kw_in_text(kw, text_lower))
    keyword_delta = max(-40, min(40, keyword_delta))

    # 사상자 수 기반 추가 보정 (별도 상한, _casualty_bonus 내부에서 max 30)
    modifier = keyword_delta + _casualty_bonus(text_lower)

    # response article severity 감소
    if title:
        for p in _RESPONSE_PATTERNS:
            if p.search(title):
                modifier -= 15
                break

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

    # response pattern 감지 — 대응/성명 기사는 title 가중치 낮춤
    is_response = False
    if title:
        for p in _RESPONSE_PATTERNS:
            if p.search(title):
                is_response = True
                break

    title_multiplier = 1 if is_response else 3

    # title 매칭 (조건부 가중치)
    if title:
        title_lower = title.lower()
        for kw in sorted_kws:
            if _kw_in_text(kw, title_lower):
                code, lat, lon = COUNTRY_MAP[kw]
                count = title_lower.count(kw)
                weight = count * len(kw) * title_multiplier
                country_hits[code].append((weight, lat, lon))

    # body(전체 텍스트) 매칭
    text_lower = text.lower()
    for kw in sorted_kws:
        if _kw_in_text(kw, text_lower):
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
    image_url: Optional[str] = None,
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

    # AI 우선 분류 (토픽 + severity 동시), 실패 시 기존 규칙 폴백
    _title_for_ai = source_title.strip()[:200] if source_title and len(source_title.strip()) > 5 else _make_title(text_for_analysis)
    ai_result = _classify_with_ai(_title_for_ai, text_for_analysis)

    if ai_result is not None:
        topic, sub_topic, severity = ai_result
        logger.debug("AI 분류: topic=%s, sub=%s, severity=%d (제목: %s)", topic, sub_topic, severity, _title_for_ai[:60])
    else:
        # 폴백: 기존 키워드 기반 분류
        topic = _classify_topic(text_for_analysis)
        if topic == "unknown" and lang not in ("en", "unknown"):
            multilang_topic = _classify_topic_multilang(raw_text, lang)
            if multilang_topic:
                topic = multilang_topic
        severity = _calculate_severity(text_for_analysis, topic, title=source_title)
        sub_topic = _classify_sub_topic(text_for_analysis, topic)
        logger.debug("규칙 폴백: topic=%s, sub=%s, severity=%d (제목: %s)", topic, sub_topic, severity, _title_for_ai[:60])

    # 엔터테인먼트/K-pop/관광 노이즈 후처리 — AI·규칙 분류 모두에 적용
    _combined_text = f"{source_title or ''} {text_for_analysis}"
    if _is_entertainment_noise(_combined_text, title=source_title):
        logger.info("엔터테인먼트 노이즈 감지 → unknown/sev=0 (제목: %s)", _title_for_ai[:60])
        topic = "unknown"
        sub_topic = "general"
        severity = 0

    # 제목 결정 (geo 추출에 활용하기 위해 먼저 계산)
    _raw_title_for_geo = source_title.strip()[:200] if source_title and len(source_title.strip()) > 5 else None
    country_code, lat, lon = _extract_geo(text_for_analysis, title=_raw_title_for_geo)
    geohash5 = _make_geohash(lat, lon)

    # 정보 접근성 보정: 언론 자유도 낮은 국가의 severity 상향
    if country_code:
        _ia_mod = INFORMATION_ACCESSIBILITY.get(country_code, 1.0)
        if _ia_mod != 1.0:
            _orig_sev = severity
            severity = min(100, int(severity * _ia_mod))
            logger.debug("IA보정: %s sev %d→%d (×%.2f)", country_code, _orig_sev, severity, _ia_mod)

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

    # 한국어 본문: 원문이 한국어면 직접 저장, 아니면 본문 앞 500자 한국어 번역
    body_ko: Optional[str] = None
    if lang == "ko":
        body_ko = raw_text[:2000]
    else:
        body_ko = _translate_to_korean(text_for_analysis[:500])

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
        body_ko=body_ko,
        topic=topic,
        sub_topic=sub_topic,
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
        image_url=image_url,
    )
