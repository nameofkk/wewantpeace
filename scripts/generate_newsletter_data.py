#!/usr/bin/env python3
"""뉴스레터 데이터 완전 자동 생성 — DB + GPT(텍스트만) + Python(HTML 조립).

Vol.1 수준 퀄리티 목표:
  - GPT는 텍스트만 생성 (Vol.1 예시 few-shot 포함)
  - HTML은 Python이 Vol.1 블록 스타일 그대로 조립
  - 데이터 기반 섹션(numbers, key_stats, calendar)은 GPT 없이 직접 빌드
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
import re
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 자동 로드 (REDIS_URL, DB URL 등)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# ── 한자→한글 변환 (Groq/Llama 한자 혼입 방지) ──
_CJK_TO_KR = {
    "影響": "영향", "戰爭": "전쟁", "緊張": "긴장", "危機": "위기",
    "經濟": "경제", "安全": "안전", "軍事": "군사", "政治": "정치",
    "平和": "평화", "衝突": "충돌", "攻擊": "공격", "防禦": "방어",
    "協商": "협상", "制裁": "제재", "難民": "난민", "死亡": "사망",
    "被害": "피해", "爆發": "폭발", "增加": "증가", "減少": "감소",
    "地域": "지역", "國際": "국제", "世界": "세계", "石油": "석유",
    "價格": "가격", "上昇": "상승", "下落": "하락", "供給": "공급",
    "需要": "수요", "輸入": "수입", "輸出": "수출",
}
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")

def _fix_cjk(text: str) -> str:
    """한자를 한글로 변환. 사전에 없는 CJK 전체 범위(한자·히라가나·가타카나)는 제거."""
    if not text: return text
    for cjk, kr in _CJK_TO_KR.items():
        text = text.replace(cjk, kr)
    # 나머지 CJK 전체 범위 제거 (한글 U+AC00-D7A3 은 범위 밖이므로 안전)
    text = re.sub(r'[\u3040-\u9fff\u3400-\u4dbf\uf900-\ufaff]+', '', text)
    # 키릴 문자 제거 (Groq llama가 러시아어 단어를 섞는 경우 방지)
    text = re.sub(r'[\u0400-\u04ff]+', '', text)
    return text

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal

# ── 국가명 매핑 ─────────────────────────────────────────────────────────────
COUNTRY_NAMES = {
    "UA": ("Ukraine", "우크라이나"), "RU": ("Russia", "러시아"),
    "IL": ("Israel", "이스라엘"), "PS": ("Palestine", "팔레스타인"),
    "SD": ("Sudan", "수단"), "MM": ("Myanmar", "미얀마"),
    "SY": ("Syria", "시리아"), "YE": ("Yemen", "예멘"),
    "CD": ("DR Congo", "콩고민주공화국"), "ET": ("Ethiopia", "에티오피아"),
    "SO": ("Somalia", "소말리아"), "AF": ("Afghanistan", "아프가니스탄"),
    "IQ": ("Iraq", "이라크"), "LY": ("Libya", "리비아"),
    "NG": ("Nigeria", "나이지리아"), "ML": ("Mali", "말리"),
    "MZ": ("Mozambique", "모잠비크"), "HT": ("Haiti", "아이티"),
    "PK": ("Pakistan", "파키스탄"), "LB": ("Lebanon", "레바논"),
    "CN": ("China", "중국"), "KP": ("North Korea", "북한"),
    "TW": ("Taiwan", "대만"), "IR": ("Iran", "이란"),
    "KR": ("South Korea", "한국"), "JP": ("Japan", "일본"),
    "US": ("United States", "미국"), "GB": ("United Kingdom", "영국"),
    "FR": ("France", "프랑스"), "DE": ("Germany", "독일"),
    "IN": ("India", "인도"), "PH": ("Philippines", "필리핀"),
    "TH": ("Thailand", "태국"), "VN": ("Vietnam", "베트남"),
    "MX": ("Mexico", "멕시코"), "CO": ("Colombia", "콜롬비아"),
    "BR": ("Brazil", "브라질"), "SA": ("Saudi Arabia", "사우디"),
    "AE": ("UAE", "UAE"), "TR": ("Turkey", "튀르키예"),
    # 아프리카
    "BF": ("Burkina Faso", "부르키나파소"), "TD": ("Chad", "차드"),
    "NE": ("Niger", "니제르"), "CM": ("Cameroon", "카메룬"),
    "CF": ("Central African Rep.", "중앙아프리카"), "SS": ("South Sudan", "남수단"),
    "ER": ("Eritrea", "에리트레아"), "DJ": ("Djibouti", "지부티"),
    "BI": ("Burundi", "부룬디"), "RW": ("Rwanda", "르완다"),
    "UG": ("Uganda", "우간다"), "KE": ("Kenya", "케냐"),
    "TZ": ("Tanzania", "탄자니아"), "EG": ("Egypt", "이집트"),
    "TN": ("Tunisia", "튀니지"), "DZ": ("Algeria", "알제리"),
    "MA": ("Morocco", "모로코"),
    # 중앙아시아·코카서스
    "AZ": ("Azerbaijan", "아제르바이잔"), "AM": ("Armenia", "아르메니아"),
    "GE": ("Georgia", "조지아"), "KG": ("Kyrgyzstan", "키르기스스탄"),
    "TJ": ("Tajikistan", "타지키스탄"), "UZ": ("Uzbekistan", "우즈베키스탄"),
    "TM": ("Turkmenistan", "투르크메니스탄"),
    # 남아시아·동남아
    "BD": ("Bangladesh", "방글라데시"), "NP": ("Nepal", "네팔"),
    "LK": ("Sri Lanka", "스리랑카"), "KH": ("Cambodia", "캄보디아"),
    "LA": ("Laos", "라오스"),
    # 중남미
    "VE": ("Venezuela", "베네수엘라"), "PE": ("Peru", "페루"),
    "EC": ("Ecuador", "에콰도르"), "BO": ("Bolivia", "볼리비아"),
    "NI": ("Nicaragua", "니카라과"), "GT": ("Guatemala", "과테말라"),
    "HN": ("Honduras", "온두라스"), "SV": ("El Salvador", "엘살바도르"),
    "CU": ("Cuba", "쿠바"), "DO": ("Dominican Rep.", "도미니카공화국"),
    "JM": ("Jamaica", "자메이카"),
    # 중동·기타
    "JO": ("Jordan", "요르단"), "OM": ("Oman", "오만"),
    "QA": ("Qatar", "카타르"), "KW": ("Kuwait", "쿠웨이트"),
    "BH": ("Bahrain", "바레인"), "BY": ("Belarus", "벨라루스"),
    "RS": ("Serbia", "세르비아"),
}

SEVERITY_COLORS = {5: "#ef4444", 4: "#f97316", 3: "#eab308", 2: "#22c55e", 1: "#94a3b8"}
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
WEEKDAY_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def get_flag(cc: str) -> str:
    if not cc or len(cc) != 2: return "\U0001f3f3\ufe0f"
    return chr(0x1F1E6 + ord(cc[0]) - ord("A")) + chr(0x1F1E6 + ord(cc[1]) - ord("A"))

def cn(cc: str, lang: str) -> str:
    names = COUNTRY_NAMES.get(cc)
    if not names: return cc or "Unknown"
    return names[1] if lang == "kr" else names[0]

def sev_color(sev: int) -> str:
    if sev >= 5: return SEVERITY_COLORS[5]
    return SEVERITY_COLORS.get(sev, "#94a3b8")

def tension_label(score: float, lang: str) -> str:
    if score >= 80: return "위기" if lang == "kr" else "Critical"
    if score >= 60: return "경고" if lang == "kr" else "Warning"
    if score >= 40: return "주의" if lang == "kr" else "Elevated"
    if score >= 20: return "관심" if lang == "kr" else "Watch"
    return "안정" if lang == "kr" else "Stable"

def tension_num(score: float) -> int:
    if score >= 80: return 5
    if score >= 60: return 4
    if score >= 40: return 3
    if score >= 20: return 2
    return 1


# ── AI 호출 (Claude Code 구독 우선, Groq/OpenAI 폴백) ───────────────────────
_CLAUDE_CODE_AVAILABLE: bool | None = None  # None=미확인, True/False=캐시

def _check_claude_code() -> bool:
    """claude CLI 사용 가능 여부 확인 (최초 1회만)."""
    global _CLAUDE_CODE_AVAILABLE
    if _CLAUDE_CODE_AVAILABLE is not None:
        return _CLAUDE_CODE_AVAILABLE
    import shutil
    _CLAUDE_CODE_AVAILABLE = shutil.which("claude") is not None
    return _CLAUDE_CODE_AVAILABLE


def _get_ai_client():
    from openai import AsyncOpenAI
    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if groq_key:
        return AsyncOpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
    if openai_key:
        return AsyncOpenAI(api_key=openai_key), "gpt-4o-mini"
    return None, ""


async def call_gpt(prompt: str, system: str = "", max_tokens: int = 4000, fields_hint: str = "") -> str:
    if fields_hint:
        print(f"    → Claude Code 호출: {fields_hint}")

    # ── 1순위: claude -p (Claude Code 구독) ──
    if _check_claude_code():
        try:
            import subprocess, asyncio
            # CLAUDECODE 환경변수 제거 (중첩 세션 방지 우회)
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)
            env.pop("CLAUDE_CODE_ENTRYPOINT", None)

            cmd = [
                "claude", "-p", prompt,
                "--output-format", "text",
                "--no-session-persistence",
                "--tools", "",               # 도구 비활성화
                "--disable-slash-commands",  # 스킬 시스템 비활성화 (brainstorming 등)
                "--setting-sources", "",     # CLAUDE.md / 유저 설정 로딩 차단
                "--model", "claude-sonnet-4-6",
            ]
            if system:
                cmd += ["--system-prompt", system]

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd, capture_output=True, text=True, timeout=180, env=env
                )
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            if result.stderr:
                print(f"  Claude Code stderr: {result.stderr[:300]}")
        except Exception as e:
            print(f"  Claude Code error: {e}")

    # ── 2순위: Groq / OpenAI API 폴백 ──
    try:
        client, model = _get_ai_client()
        if not client:
            print("  AI 불가: GROQ_API_KEY / OPENAI_API_KEY 미설정")
            return ""
        messages = []
        if system: messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        print(f"    → Groq/OpenAI 폴백: {model}")
        resp = await client.chat.completions.create(
            model=model, messages=messages, temperature=0.7, max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  AI error: {e}")
        return ""


def _parse_gpt_json(result: str) -> dict:
    """GPT/Claude 응답에서 JSON 추출. 앞뒤 텍스트·마크다운 펜스 제거."""
    try:
        cleaned = result.strip()
        # 앞쪽 설명 텍스트 건너뛰기: 첫 번째 { 위치 찾기
        brace_idx = cleaned.find("{")
        fence_idx = cleaned.find("```")
        if fence_idx != -1 and (brace_idx == -1 or fence_idx < brace_idx):
            # ```json ... ``` 블록 추출
            inner = cleaned[fence_idx:].split("\n", 1)
            if len(inner) > 1:
                cleaned = inner[1]
                end = cleaned.rfind("```")
                if end != -1:
                    cleaned = cleaned[:end]
        elif brace_idx > 0:
            # 앞에 텍스트 있으면 { 부터 시작
            cleaned = cleaned[brace_idx:]
        return json.loads(cleaned.strip())
    except Exception as e:
        print(f"  GPT JSON parse error: {e}")
        print(f"  Raw: {result[:300]}")
        return {}


async def generate_editorial(ctx: dict, lang: str, vol: int = 1) -> dict:
    """GPT로 편집 텍스트만 생성 — 3개 순차 호출로 분리. HTML 금지. Vol.1 예시 포함."""
    is_kr = lang == "kr"

    # ── 주간 변동: hero_style (P3-1) ──
    hero_styles_kr = ["질문형 (예: '호르무즈가 막혔는데, 한국은?')", "숫자 강조 (예: '854건 — 이번 주 세계가 감지한 분쟁')", "대비형 (예: '해협 33km, 세계 원유 20%')", "일상 연결 (예: '주유소 가격표가 바뀌고 있어요')"]
    hero_styles_en = ["Question style (e.g. 'Hormuz blocked — what about us?')", "Number-led (e.g. '854 events — the world noticed')", "Contrast (e.g. '33km strait, 20% of world oil')", "Daily life (e.g. 'Your gas station prices are changing')"]
    hero_style = (hero_styles_kr if is_kr else hero_styles_en)[vol % 4]

    # ── 주간 변동: editors_tone (P3-2) ──
    editors_tones_kr = ["분석가 톤 — 데이터 중심, 객관적, 팩트 나열", "이웃 톤 — 친근, 비유 많이, 대화체", "선배 톤 — 경험담, 역사 비교, 교훈"]
    editors_tones_en = ["Analyst tone — data-driven, objective, fact-focused", "Neighbor tone — friendly, metaphors, conversational", "Mentor tone — historical parallels, lessons learned"]
    editors_tone = (editors_tones_kr if is_kr else editors_tones_en)[vol % 3]

    # ── 주간 변동: did_you_know_category (P3-3) ──
    dyk_cats_kr = ["지리/지형 (예: '호르무즈 폭 33km')", "역사 (예: '1973년 오일쇼크 때...')", "경제 (예: '한국 에너지 자급률 16%')", "군사/안보 (예: '세계 핵무기 12,500개')", "인도/생활 (예: '분쟁으로 실향민 1.1억명')"]
    dyk_cats_en = ["Geography (e.g. 'Hormuz is 33km wide')", "History (e.g. '1973 oil shock...')", "Economy (e.g. 'Energy self-sufficiency 16%')", "Military (e.g. '12,500 nuclear weapons globally')", "Humanitarian (e.g. '110M displaced by conflict')"]
    dyk_category = (dyk_cats_kr if is_kr else dyk_cats_en)[vol % 5]

    # ── C: Vol.1 실제 텍스트 Few-Shot (형식+톤 모두 참고) ──
    examples_kr = f"""
[VOL.1 실제 텍스트 — 이 톤·밀도·구조를 그대로 따를 것. ⚠️ 예시 속 지명·숫자 절대 복사 금지. THIS WEEK DATA 숫자만 쓸 것]

◆ preheader (실제):
"해협 하나 막혔는데 기름값이 뛰어요. 23개국 위기, 854건 감지. 한국 긴장도 96.8 — 내가 왜 영향받는지, 2분."
→ 이번 주 버전: "{ctx['events_7d']}건 감지, {ctx['crisis_count']}개국 위기, 긴장도 {ctx['target_tension']} — [이번 주 독자 질문]"

◆ hero_headline (실제):
"호르무즈 해협이 막혔는데,\n한국 원유 70%가\n거길 지나요"
→ 패턴: [구어체 접속사+사건]\n[한국 연결 수치]\n[긴장도]

◆ editors_note_p1 (실제):
"이번 주가 다른 이유 하나. 해협 하나로 세계가 흔들린다는 게 증명됐죠. 이란이 해협 잠그고 결제 화폐를 바꾸라 했어요. 에너지를 무기로, 달러를 흔드는 수."
→ 패턴: [이번 주가 다른 이유]. [핵심 비유]. [구체 행동]. [그것의 의미].

◆ energy_intro (실제):
"유가 $95→$118, 일주일. 지갑까지 오는 위기."
→ 이번 주: "유가 ${ctx['oil_price_past']}→${ctx['oil_price']}, {ctx['energy_period']}. 지갑까지 오는 위기."

◆ deep_dive_p1 (실제):
"폭 33km — 세계 원유 20% 통과. 이란이 봉쇄 — 한국행 유조선이 해협에서 멈췄어요."
→ 패턴: [고유명사] — [수치]. [주체] [행동] — [독자 연결].

◆ did_you_know (실제):
"한국 에너지 자급률 OECD 38국 최하위 16%. 원유 70% 호르무즈 경유. 막히면 비축유 90일 유일 — 못 풀리면 공장 정지."
→ 패턴: [충격 사실+순위]. [연결 수치]. [최악 시나리오].

◆ next_week (실제):
"48시간 시한 경과 — 폭격? 외교 반전? / KOSPI 2,000선 사수 여부 / 유가 $130 비축유 카운트다운"
→ 패턴: 3줄, 각 줄에 구체적 임계값 또는 이분법적 결과.
"""
    examples_en = f"""
[VOL.1 ACTUAL TEXT — copy this tone, density, structure. ⚠️ NEVER copy example locations or numbers. Use THIS WEEK DATA only. ALL TEXT IN ENGLISH.]

◆ preheader (actual):
"One strait blocked and oil jumped. 23 crisis countries, 854 events. Tension 96.8 — why you're affected, 2 min."
→ This week: "{ctx['events_7d']} events, {ctx['crisis_count']} crisis countries, tension {ctx['target_tension']} — [this week's reader question]"

◆ hero_headline (actual):
"Hormuz is blocked —\n70% of Korea's oil\ngoes through there"
→ Pattern: [colloquial hook+event]\n[reader connection with number]\n[tension score]

◆ editors_note_p1 (actual):
"One thing makes this week different. One strait shook the whole world. Iran locked it and demanded yuan payments. Energy as a weapon, the dollar under attack."
→ Pattern: [Why this week is different]. [Core metaphor]. [Specific action]. [What it means].

◆ energy_intro (actual):
"Oil $95→$118, one week. Heading straight to your wallet."
→ This week: "Oil ${ctx['oil_price_past']}→${ctx['oil_price']}, {ctx['energy_period']}. Heading to your wallet."

◆ deep_dive_p1 (actual):
"33km wide — 20% of world oil passes through. Iran blockade — tankers bound for Korea stopped."
→ Pattern: [proper noun] — [number]. [actor] [action] — [reader connection].

◆ did_you_know (actual):
"Korea's energy self-sufficiency: lowest in OECD at 16%. 70% of oil via Hormuz. Blocked = 90-day reserve only — unresolved = factory shutdowns."
→ Pattern: [shocking fact + ranking]. [connected number]. [worst case scenario].
"""
    examples = examples_kr if is_kr else examples_en

    dont_list_kr = """
❌ BANNED PHRASES (즉시 삭제, 대체 필수):
- "영향을 미칠 수 있습니다" → 대신: "주유비가 올라요" / "$X 오릅니다"
- "영향을 미칩니다" (숫자 없이) → 대신: "유가 $X → 주유비 직격"
- "영향을 줄 수 있" → 대신: 구체적 숫자+결과
- "국제 관계에 영향" → 너무 막연. 무엇이 어떻게 바뀌는지 써야 함
- "지켜봐야 합니다" / "예의 주시" / "주시해야" → 대신: 구체적으로 무엇을, 왜
- "중동의 안정성" / "불안정한 상황" → 대신: "레바논 남부 포격" / "가자지구 공습"
- "상황이 계속" / "긴장이 고조" → 추상어 금지
- 학술 용어: "지정학적", "양자적", "다자", "geopolitical" 금지
- 같은 구절 2회 이상 반복 금지 (이스라엘-레바논을 매 문장에 쓰지 마세요. 두 번째부터 "이 갈등", "양측", "휴전")
- 유가 관련 표현은 섹션마다 다르게: 첫 번째 "유가 상승으로" → 두 번째 "$X 돌파" → 세 번째 "배럴당 ↑X%"
- "인한", "인해", "으로 인한" 같은 표현 1회만 허용 — 반복 금지
- 한국어 아닌 단어 절대 금지 (영어·러시아어·아랍어·중국어 모두 금지)

✅ 필수 스타일 규칙:
- ↑↓→ 기호를 적극 사용: "주유비↑ 배달비↑ 난방비↑", "봉쇄 → 유가↑ → 인플레"
- — 구분자로 리듬감: "[사건] — [독자 영향]" 형식. 예: "공습 지속 — 공급망 흔들려요."
- 모든 문장에 숫자 또는 고유 지명: THIS WEEK DATA의 실제 숫자만 사용. 임의 생성 금지.
- 독자 일상 연결: 주유비, 배달비, 장바구니, 난방비, 주식, 여행비용"""

    dont_list_en = """
❌ BANNED PHRASES:
- "may affect" / "could impact" without a number → replace with: "oil +$X"
- "geopolitical tensions" → replace with: specific city/event
- "situation is developing" / "remains to be seen" → banned
- Repeat same phrase more than once → use "this conflict", "both sides", "the ceasefire" instead
- Oil price phrasing must VARY across sections: first "oil surged" → then "$X milestone" → then "Brent ↑X%"
- "due to", "because of", "as a result of" — max 1 use total across all fields

✅ MANDATORY STYLE:
- Use ↑↓→ symbols: "gas↑ delivery↑ groceries↑", "blockade → oil↑ → inflation"
- Use — for rhythm: "[event] — [reader impact]" format. Example: "airstrike continues — supply chain shaking."
- Every sentence needs a number or proper noun: use ONLY THIS WEEK'S actual numbers. No invention.
- Connect to reader's daily cost: gas, delivery, groceries, heating, flights"""

    if is_kr:
        system = f"""You are the editor of WeWantPeace newsletter.
한국어 구어체. ~해요 체. 구체적 숫자+비유+기호 필수. 추상 문장 0개.
CRITICAL RULES:
- 반드시 한국어로만 작성
- 모든 문장에 숫자($, %, 명, 건, 일) 또는 고유 지명 포함
- ↑↓→ 기호 적극 사용 (에너지 섹션에 최소 3개)
- — 구분자로 리듬감 (각 섹션 최소 1개)
- Output ONLY valid JSON. No markdown fences.
{dont_list_kr}
⛔ 할루시네이션 방지 (위반 시 출력 거부됨):
- 2015~2024년, 10월 7일, 과거 월(1월/2월/3월/4월) 날짜 사용 ⛔
- NEWS CONTEXT에 없는 사망자 수·이재민 수·부상자 수 생성 ⛔
- event_count(이벤트 감지 건수)를 사상자·사망자 수로 표기 ⛔
- "100만 명 이재민", "하마스 지도자 사망", "10월 7일 테러" 등 훈련 데이터 내용 ⛔
- 날짜 필요 시 반드시 "이번 주" / "최근 7일" / "현재" 사용
STYLE HINTS FOR THIS VOLUME:
- hero_headline 스타일: {hero_style}
- editors_note 톤: {editors_tone}
- did_you_know 카테고리: {dyk_category}"""
    else:
        system = f"""You are the editor of WeWantPeace newsletter.
Write ONLY in English. Casual, punchy tone. Numbers + symbols required in every section.
CRITICAL RULES:
- ALL text in English only. No Korean or other languages.
- Every sentence needs a number or proper noun
- Use ↑↓→ symbols actively (minimum 3 in energy section)
- Use — for rhythm (minimum 1 per section)
- Output ONLY valid JSON. No markdown fences.
{dont_list_en}
⛔ ANTI-HALLUCINATION (violations cause output rejection):
- No dates from 2015-2024, no "October 7th", no past months outside coverage period ⛔
- No casualty/displacement numbers unless explicitly in NEWS CONTEXT ⛔
- event_count = detected events (articles/reports), NOT casualties ⛔
- No training data events: "Hamas leader killed", "Oct 7 attack", "1 million displaced" ⛔
- For dates use "this week" / "past 7 days" / "currently"
STYLE HINTS FOR THIS VOLUME:
- hero_headline style: {hero_style}
- editors_note tone: {editors_tone}
- did_you_know category: {dyk_category}"""

    # ── 공통 데이터 블록 ──
    data_block = f"""⛔ ANTI-HALLUCINATION RULES (VIOLATIONS CAUSE OUTPUT REJECTION):
1. 발행일: {ctx.get('issue_date','이번 주')} | 커버 기간: {ctx.get('week_start','')} ~ {ctx.get('week_end','')}
2. 이 기간 이전 날짜(2015~2024년, 10월 7일, 1~4월 등) 절대 사용 금지 — "이번 주" / "최근 7일" 로 대체
3. 사망자·이재민·부상자 수 = NEWS CONTEXT에 명시된 경우만 사용. 임의 생성 ⛔
4. "events" / "건" = DB가 감지한 이벤트(기사·보고) 건수 ≠ 사상자 수. 혼용 ⛔
5. 뉴스레터에 없어야 할 정보: "100만 명 이재민", "10월 7일 테러", "2023년 공격" — 전부 ⛔

THIS WEEK'S DATA:
- #1 Story: {ctx['top_story']} ({ctx['top_cc']}, {ctx['top_events']} events, severity {ctx['top_sev']})
- #2 Story: {ctx['story_2']} ({ctx['story_2_cc']}, {ctx['story_2_events']} events)
- #3 Story: {ctx['story_3']} ({ctx['story_3_cc']}, {ctx['story_3_events']} events)
- Top 3 tension: {ctx['tension_top3']}
- Target country ({ctx['target_name']}): tension {ctx['target_tension']}, rank #{ctx['target_rank']}, change {ctx['target_delta']}
- Oil: ${ctx['oil_price']} ({ctx['oil_change']}%)
- Wheat: ${ctx['wheat_price']} ({ctx['wheat_change']}%)
- Crisis countries: {ctx['crisis_count']} (prev week: {ctx['crisis_prev']})
- Events: {ctx['events_24h']}(24h) / {ctx['events_7d']}(7d)
- Travel L4: {ctx['travel_l4']} countries / L3: {ctx['travel_l3']} countries
- Oil ({ctx['energy_period']} comparison): ${ctx['oil_price_past']} → ${ctx['oil_price']} ({ctx['oil_change_period']}%)"""

    # ── 호출 1: 서사 앵커 (hero + brief + editors) ──
    top_body = ctx.get('top_story_events', '')
    body_section_1 = f"\nNEWS CONTEXT (#1 실제 기사 요약):\n{top_body}" if top_body else ""

    if is_kr:
        _hero_hint_kr = (
            f'2-3줄, \\n으로 구분. 스타일: {hero_style}. '
            '줄1(핵심 제목, 20-35자): 독자가 1초 만에 이해하는 이번 주 가장 중요한 사건. '
            '반드시: 구체적 주어(기관명/국가명/인물명)+행동+핵심 숫자 또는 결과. '
            "✅좋은 예: 'ICC, 이스라엘 장관 체포 영장 신청 — 382건','이란 핵 협상 결렬 — 유가 $104','이스라엘·레바논 동시 공습 — 중동 131개국 위기'. "
            "⛔나쁜 예: '법원 도장 하나가 흔들렸다'(비유),'국제사회가 주목한다'(주어 모호),'헤이그가 스모트리치에'(주어 어색). "
            f'줄2(독자 일상 연결, 15-25자): 유가방향 ⚠️반드시 {ctx["oil_change"]}% 부호 그대로(양수=↑,음수=↓). '
            f'줄3(데이터 한 줄, 15-20자): 반드시 {ctx["target_name"]} 긴장도 {ctx["target_tension"]}, 변화 {ctx["target_delta"]}.'
        )
        anchor_field_hints = f"""
  "hero_headline": "{_hero_hint_kr}",
  "preheader": "70-90자 필수. 형식: '[숫자1] [숫자2] [숫자3] — [독자 질문?]'. 반드시 현재 데이터 사용: '{ctx['events_7d']}건 감지, {ctx['crisis_count']}개국 위기, 긴장도 {ctx['target_tension']} — [질문]'. — 구분자 필수.",
  "brief_1_title": "#1 스토리. 형식: '[원인] → [결과]' 또는 '[사건], [결과수치]'. 예: '가자 공습 → 유가↑'. 15-25자.",
  "brief_1_desc": "#1 스토리가 독자 주유비/배달비/장바구니에 어떻게 연결되는지 1문장. 숫자 필수.",
  "brief_2_title": "#2 스토리. 같은 형식. 15-25자.",
  "brief_2_desc": "1문장. 독자 일상 연결. 숫자 필수.",
  "brief_3_title": "{ctx['target_name']} 긴장도 {ctx['target_tension']} — 독자에게 이게 의미하는 것. 15-25자.",
  "brief_3_desc": "긴장도 수치가 독자 삶에 미치는 구체적 영향. 1문장.",
  "editors_note_p1": "One striking insight from THIS WEEK. Must include a metaphor. Use — separator. ⚠️ Korean only. ⚠️ No past examples. Example style: '총성 하나가 유가를 흔든다 — 한국 에너지 70% 중동 경유.' Tone: {editors_tone}",
  "editors_note_p2": "연결 — 독자 일상. '주유비↑ 배달비↑' 같은 체인 + 구체 숫자. — 구분자 활용. 예: '주유비 10%↑면 배달비도 따라와요 — 이미 지갑에서 느낍니다.'",
  "editors_note_p3": "마무리 1-2문장. 다음 주 예고 또는 공유 권유. 자연스러운 대화체.",
  "editors_ps": "이탤릭 마무리 한 줄 (⚠️ 'P.S.'로 시작하지 말 것 — 자동 추가됨). 예: '다음 주 이란 핵 회담 결과 확인 필수.'",
  "share_headline": "감성적 1줄. '2분 전과 세상이 달라 보이죠.' 수준의 임팩트. 절대 generic 금지.",
  "share_subtext": "구체적으로 누구에게 공유할지: 출장 동료, 주식 보는 친구, 기름값 걱정 부모님.",
  "pro_cta_headline": "{ctx['target_name']} 긴장도 {ctx['target_tension']} 같은 구체 수치 + Pro 실시간 알림. 1-2줄.",
  "pro_cta_subtext": "Free vs Pro 타이밍 차이. 1문장.\""""
    else:
        anchor_field_hints = f"""
  "hero_headline": "2-3 lines, separated by \\n. Format: [specific event+number]\\n[why it matters globally]\\n[reader's daily life impact]. Style: {hero_style}.",
  "preheader": "70-90 chars. Format: '[stat1], [stat2], [stat3] — [reader question?]'. Use current data: '{ctx['events_7d']} events, {ctx['crisis_count']} crisis countries, tension {ctx['target_tension']} — [question]'. Must use — separator.",
  "brief_1_title": "#1 story. Format: '[cause] → [effect]'. Example: 'Gaza strike → oil↑'. 15-25 chars.",
  "brief_1_desc": "How #1 story connects to reader's gas/delivery/grocery cost. 1 sentence with number.",
  "brief_2_title": "#2 story. Same format. 15-25 chars.",
  "brief_2_desc": "1 sentence, reader life connection, include number.",
  "brief_3_title": "{ctx['target_name']} tension {ctx['target_tension']} headline. What it means. 15-25 chars.",
  "brief_3_desc": "Why this tension score matters to the reader's wallet. 1 sentence.",
  "editors_note_p1": "Core insight this week. Must include metaphor + — separator. Tone: {editors_tone}.",
  "editors_note_p2": "Connect to reader's daily life. 1 analogy + 1 specific number.",
  "editors_note_p3": "Closing: share encouragement + next week preview. 1-2 sentences.",
  "editors_ps": "Italic closing one line (⚠️ do NOT start with 'P.S.' — it is added automatically). Example: 'Check next week for Iran nuclear talks outcome.'",
  "share_headline": "Emotional 1-line. Level of: '2 minutes ago the world looked different.' Never generic.",
  "share_subtext": "Specific people to share with: coworkers, investor friends, family who travel.",
  "pro_cta_headline": "Specific data point like tension {ctx['target_tension']} + Pro real-time alert advantage. 1-2 lines.",
  "pro_cta_subtext": "Free vs Pro timing gap. 1 sentence.\""""

    prompt_anchor = f"""{examples}

{data_block}{body_section_1}

Generate JSON with these TEXT-ONLY fields (NO HTML except <br> in hero_headline):
{{{anchor_field_hints}
}}"""

    # ── 호출 2: 에너지 & 딥다이브 ──
    body_2 = ctx.get('story_2_events_body', '')
    body_3 = ctx.get('story_3_events_body', '')
    body_section_2 = ""
    if top_body: body_section_2 += f"\nNEWS CONTEXT (#1 실제 기사 요약):\n{top_body}"
    if body_2: body_section_2 += f"\nNEWS CONTEXT (#2 실제 기사 요약):\n{body_2}"
    if body_3: body_section_2 += f"\nNEWS CONTEXT (#3 실제 기사 요약):\n{body_3}"

    if is_kr:
        energy_deep_hints = f"""
  "energy_intro": "이 형식 그대로: '유가 ${ctx['oil_price_past']}→${ctx['oil_price']}, {ctx['energy_period']}. [독자 생활 연결].' ⚠️ 위 숫자 그대로 사용. — 구분자 포함.",
  "energy_p1": "가격 변동 사실만. 숫자 3개 이상. '브렌트유 ${ctx['oil_price_past']} → ${ctx['oil_price']} ({ctx['oil_change_period']}%, {ctx['energy_days']}일간). [원인 한 줄].' ⚠️ 이 숫자 사용.",
  "energy_p2": "독자 일상 연쇄. 형식: '주유비↑ 배달비↑ 난방비↑ — 이미 시작.' ↑↓ 기호 3개 이상 필수.",
  "energy_p3": "다음 주 모니터링 포인트. NEWS CONTEXT 기반 이벤트 + 가격 임계값.",
  "deep_dive_title": "NEWS CONTEXT 기반 #1 스토리 제목. 10-20자. ⚠️ NEWS CONTEXT 속 구체 지명 사용.",
  "deep_dive_p1": "NEWS CONTEXT 속 사건 3문장 이내. 각 문장 40자 이내. — 구분자 활용. 형식: '[NEWS CONTEXT 지명] — [NEWS CONTEXT 수치]. [맥락] — [결과].' ⚠️ NEWS CONTEXT 내용만 사용, 과거 사례 금지.",
  "deep_dive_p2": "글로벌 파급 2-3문장. NEWS CONTEXT 기반 숫자 2개 이상. 헤지 금지.",
  "deep_dive_p3": "{ctx['target_name']}에 미치는 구체적 영향. 주유비/배달비/수출입 숫자 포함. 1-2문장.",
  "deep_dive_p4": "다음 주 주목 포인트. NEWS CONTEXT 후속 이벤트. 1문장.",
  "deep_dive_why": "독자를 위한 '그래서 뭐가 문제냐' 2문장. 은유 1개 + NEWS CONTEXT 숫자 1개.",
  "impact_1": "⚠️ 반드시 '{ctx['top_story']}'({ctx['top_events']}건) 단 하나의 이벤트만. 다른 이벤트 혼합 절대 금지. 형식: '[{ctx['top_story']}] — [{ctx['top_events']}건 이벤트 확인].' 사망자·이재민 수는 NEWS CONTEXT에 명시된 경우만, 임의 생성 ⛔",
  "impact_2": "시장 반응: 'oil↑ ${ctx['oil_price']}(+{ctx['oil_change']}%), 해운↑ Y%' 형식. ↑ 기호 필수.",
  "impact_3": "일상 연쇄: '주유비↑ 배달비↑ 장바구니↑' 형식. ↑ 기호 3개.",
  "impact_4": "거시 결과: '인플레↑ → 금리↑ → 증시↓' 연쇄. → 기호 사용.",
  "tension_warning": "긴장도 데이터 {ctx['tension_top3']} 중 가장 충격적인 패턴. 구체 숫자 필수.\""""
    else:
        energy_deep_hints = f"""
  "energy_intro": "Use this exactly: 'Oil ${ctx['oil_price_past']}→${ctx['oil_price']}, {ctx['energy_period']} — heading to your wallet.' ⚠️ Use these exact numbers.",
  "energy_p1": "Price facts. 3+ numbers. 'Brent crude ${ctx['oil_price_past']} → ${ctx['oil_price']} ({ctx['oil_change_period']}%, {ctx['energy_days']} days). [cause].' ⚠️ Use these numbers.",
  "energy_p2": "Daily life chain. Format: 'gas↑ delivery↑ groceries↑ — already starting.' 3+ ↑↓ symbols required.",
  "energy_p3": "Next week monitor point. Based on NEWS CONTEXT + price threshold.",
  "deep_dive_title": "Based on NEWS CONTEXT. 10-20 chars. Include specific location from NEWS CONTEXT.",
  "deep_dive_p1": "Max 3 sentences from NEWS CONTEXT. Max 60 chars each. Use — separator. Format: '[NEWS CONTEXT location] — [NEWS CONTEXT number]. [context] — [result].' ⚠️ NEWS CONTEXT only, no past examples.",
  "deep_dive_p2": "Global impact 2-3 sentences. 2+ numbers from NEWS CONTEXT. No hedges.",
  "deep_dive_p3": "US-specific impact. Gas/delivery/export numbers. 1-2 sentences.",
  "deep_dive_p4": "Next week watch point. Based on NEWS CONTEXT follow-up. 1 sentence.",
  "deep_dive_why": "'So what' for reader. 2 sentences. 1 metaphor + 1 number from NEWS CONTEXT.",
  "impact_1": "Trigger: location+event count from NEWS CONTEXT. Format: '[location] — [{ctx['top_events']} events confirmed].' ⚠️ Casualty/displacement numbers only if explicitly in NEWS CONTEXT. No invention ⛔",
  "impact_2": "Market reaction: 'oil↑ ${ctx['oil_price']}(+{ctx['oil_change']}%), shipping↑ Y%'. ↑ symbol.",
  "impact_3": "Daily chain: 'gas↑ delivery↑ groceries↑'. 3 ↑ symbols.",
  "impact_4": "Macro: 'inflation↑ → rates↑ → stocks↓' chain. → symbol.",
  "tension_warning": "Most alarming pattern in {ctx['tension_top3']}. Specific numbers required.\""""

    prompt_energy_deep = f"""{data_block}{body_section_2}

Generate JSON with these TEXT-ONLY fields:
{{{energy_deep_hints}
}}"""

    # ── 호출 3: 캘린더 & did_you_know ──
    if is_kr:
        calendar_hints = f"""
  "did_you_know": "형식: '[놀라운 사실+숫자.] [놀라운 사실+숫자.] [독자 연결+숫자.]' 카테고리: {dyk_category}. ⚠️ 이번 주 통계 금지 — 배경 지식(지리·역사·경제)으로. 예(지리): '호르무즈 해협 폭 33km — 세계 원유 20% 통과. 페르시아만 원유 매장량 세계 1위. 한국 원유 수입 70% 중동 경유.' 예(경제): '한국 에너지 자급률 OECD 최하위 16%. 배럴당 $10 오르면 주유비 리터당 ↑8원. 비축유 한계 90일.' ⚠️ 구체적 과거 날짜(2023년/2024년/월일) 절대 금지. 각 팩트 25자 이내.",
  "next_week_1": "다음 주 주목 이벤트 #1. 구체 국가/기관 포함. ⚠️ 날짜 숫자 생성 금지(시스템 자동 할당). 1문장.",
  "next_week_2": "다음 주 주목 이벤트 #2. THIS WEEK 스토리 후속. ⚠️ 날짜 숫자 생성 금지. 1문장.",
  "next_week_3": "다음 주 주목 이벤트 #3. 독자 일상 연결. ⚠️ 날짜 숫자 생성 금지. 1문장.",
  "calendar_1_event": "이번 주 핵심 이벤트 서술. 형식: '[주체] [행동] [결과]'. ⚠️ '예상됩니다/될 것으로' 금지. ⚠️ '3월/4월' 등 날짜 수치 금지. 현재형 또는 진행형으로.",
  "calendar_1_tags": "1-2개 태그 (안보/경제/에너지/외교/인도/환경 중 선택)",
  "calendar_2_event": "이번 주 후속 이벤트 #2. 형식: '[주체] [행동]'. ⚠️ '예상됩니다' 금지. ⚠️ 날짜 수치 금지.",
  "calendar_2_tags": "1-2개 태그",
  "calendar_3_event": "이번 주 후속 이벤트 #3. ⚠️ '예상됩니다' 금지. ⚠️ 날짜 수치 금지.",
  "calendar_3_tags": "1-2개 태그",
  "calendar_4_event": "이번 주 후속 이벤트 #4. ⚠️ '예상됩니다' 금지. ⚠️ 날짜 수치 금지.",
  "calendar_4_tags": "1-2개 태그\""""
    else:
        calendar_hints = f"""
  "did_you_know": "Format: '[Surprising fact + number.] [Surprising fact + number.] [Reader impact + number.]' Category: {dyk_category}. ⚠️ NOT stats from THIS WEEK. Use background facts: geography, history, economics. Example (geography): 'Strait of Hormuz is 33km wide — 20% of global oil passes through. Persian Gulf holds 48% of world oil reserves. US imports 6M barrels/day.' Example (economy): 'US energy imports hit $200B/year. Oil +$10/barrel = gas +$0.25/gallon. Strategic reserve holds 90-day supply.' ⚠️ NO specific past dates (2023/2024/month+day). Max 30 chars each fact.",
  "next_week_1": "Next week watch #1. Country/org specific. ⚠️ No date numbers (system assigns). 1 sentence.",
  "next_week_2": "Next week watch #2. THIS WEEK story follow-up. ⚠️ No date numbers. 1 sentence.",
  "next_week_3": "Next week watch #3. Reader daily life connection. ⚠️ No date numbers. 1 sentence.",
  "calendar_1_event": "This week's key event. Format: '[actor] [action] [result]'. ⚠️ No 'expected to/is expected' patterns. ⚠️ No month/date numbers. Use present or active tense.",
  "calendar_1_tags": "1-2 tags (security/economy/energy/diplomacy/humanitarian/climate)",
  "calendar_2_event": "Follow-up event #2. Format: '[actor] [action]'. ⚠️ No 'expected' language. ⚠️ No date numbers.",
  "calendar_2_tags": "1-2 tags",
  "calendar_3_event": "Follow-up event #3. ⚠️ No 'expected' language. ⚠️ No date numbers.",
  "calendar_3_tags": "1-2 tags",
  "calendar_4_event": "Follow-up event #4. ⚠️ No 'expected' language. ⚠️ No date numbers.",
  "calendar_4_tags": "1-2 tags\""""

    prompt_calendar = f"""{data_block}

Generate JSON with these TEXT-ONLY fields:
{{{calendar_hints}
}}"""

    # ── A: 호출 0 — 에디터 브리프 (선행 분석) ──────────────────────────────────
    print("  [0/4] 에디터 브리프 분석 중...")
    all_bodies = "\n".join(filter(None, [top_body, body_2, body_3]))[:1800]
    if is_kr:
        brief_prompt = f"""{data_block}

NEWS CONTEXT (이번 주 실제 기사):
{all_bodies}

이번 주 뉴스를 에디터 시각으로 분석하고 JSON으로 답해라:
{{
  "this_week_hook": "이번 주가 다른 이유 한 문장. '이번 주가 다른 이유 하나.' 로 시작. 추상어 금지, 구체 사건 기반.",
  "core_metaphor": "이번 주 전체를 꿰는 비유 한 줄. 예: '해협 하나로 세계가 흔들린다'. editors_note_p1에 이 비유를 반드시 사용.",
  "reader_blindspot": "독자가 몰랐을 충격 사실 3개. 숫자 포함. 각 1줄. 뉴스 본문 기반.",
  "wallet_chain": "독자 지갑 영향 최단 경로. 예: '이란 봉쇄 → 유가↑ → 주유비↑ → 배달비↑'",
  "headline_angle": "hero_headline에 써야 할 가장 강한 각도. 이번 주 핵심 사실 + 독자 연결. 구어체.",
  "next_week_watch": "다음 주 가장 중요한 모니터링 포인트. 구체 임계값 또는 이분법적 결과 포함."
}}"""
    else:
        brief_prompt = f"""{data_block}

NEWS CONTEXT:
{all_bodies}

Analyze this week's news from an editor's perspective. Return JSON:
{{
  "this_week_hook": "One sentence: why this week is different. Start with 'One thing makes this week different.' No abstract words.",
  "core_metaphor": "One metaphor for the whole week. Example: 'One strait shook the world.' MUST use this in editors_note_p1.",
  "reader_blindspot": "3 shocking facts readers didn't know. Each 1 line with number. Based on news context.",
  "wallet_chain": "Shortest path to reader's wallet. Example: 'Iran blockade → oil↑ → gas↑ → delivery↑'",
  "headline_angle": "Strongest angle for hero_headline. Key fact + reader connection. Colloquial tone.",
  "next_week_watch": "Most important thing to watch next week. Include specific threshold or binary outcome."
}}"""

    r0 = await call_gpt(brief_prompt, system, max_tokens=600, fields_hint="editorial_brief")
    editorial_brief = _parse_gpt_json(r0)

    # 브리프를 이후 호출에 주입할 텍스트로 변환
    brief_injection = ""
    if editorial_brief:
        if is_kr:
            brief_injection = f"""
EDITORIAL BRIEF (이번 주 핵심 각도 — 아래 내용을 반드시 반영할 것):
- 이번 주 훅: {editorial_brief.get('this_week_hook', '')}
- 핵심 비유: {editorial_brief.get('core_metaphor', '')} ← editors_note_p1에 이 비유 사용 필수
- 독자 몰랐던 사실: {editorial_brief.get('reader_blindspot', '')}
- 지갑 영향 경로: {editorial_brief.get('wallet_chain', '')}
- hero 각도: {editorial_brief.get('headline_angle', '')}
- 다음 주 주목: {editorial_brief.get('next_week_watch', '')}
"""
        else:
            brief_injection = f"""
EDITORIAL BRIEF (incorporate ALL of the following into your writing):
- Hook: {editorial_brief.get('this_week_hook', '')}
- Core metaphor: {editorial_brief.get('core_metaphor', '')} ← MUST use in editors_note_p1
- Reader blindspot: {editorial_brief.get('reader_blindspot', '')}
- Wallet chain: {editorial_brief.get('wallet_chain', '')}
- Headline angle: {editorial_brief.get('headline_angle', '')}
- Next week watch: {editorial_brief.get('next_week_watch', '')}
"""

    # ── 4개 순차 호출 ────────────────────────────────────────────────────────
    print("  [1/4] 서사 앵커 생성 중...")
    r1 = await call_gpt(prompt_anchor + brief_injection, system, max_tokens=2000, fields_hint="anchor(hero+brief+editors)")
    p1 = _parse_gpt_json(r1)

    # 호출 1에서 이미 쓴 주요 구절 추출 → 호출 2에 전달해 반복 방지 (안 C)
    used_in_p1 = ""
    if p1 and is_kr:
        used_phrases = []
        for f in ["hero_headline", "brief_1_title", "brief_2_title", "editors_note_p1"]:
            v = p1.get(f, "")
            if v and len(v) > 5:
                used_phrases.append(f"- {v[:60]}")
        if used_phrases:
            used_in_p1 = (
                "\n\nALREADY WRITTEN (이 표현들과 다른 방식으로 쓸 것. 같은 구절 반복 금지):\n"
                + "\n".join(used_phrases[:4])
            )

    print("  [2/4] 에너지·딥다이브 생성 중...")
    r2 = await call_gpt(
        prompt_energy_deep + brief_injection + used_in_p1,
        system, max_tokens=1400, fields_hint="energy+deep_dive+impact"
    )
    p2 = _parse_gpt_json(r2)

    print("  [3/4] 캘린더·did_you_know 생성 중...")
    r3 = await call_gpt(prompt_calendar + brief_injection, system, max_tokens=800, fields_hint="calendar+did_you_know")
    p3 = _parse_gpt_json(r3)

    if not p1 and not p2 and not p3:
        return {}

    # 결과 병합 (p3 → p2 → p1 순서로 덮어씌워 최신 우선)
    merged = {}
    merged.update(p3)
    merged.update(p2)
    merged.update(p1)

    # ── B: 호출 4 — 정제 패스 (Vol.1 스타일로 핵심 필드 개선) ─────────────────
    print("  [4/4] Vol.1 스타일 정제 중...")
    refine_keys = ["editors_note_p1", "editors_note_p2", "deep_dive_p1", "deep_dive_why", "hero_headline"]
    refine_fields = {k: merged[k] for k in refine_keys if merged.get(k)}
    if refine_fields and editorial_brief:
        if is_kr:
            refine_prompt = f"""Vol.1 실제 텍스트 (이 밀도·리듬을 기준으로):
- editors_note: "이번 주가 다른 이유 하나. 해협 하나로 세계가 흔들린다는 게 증명됐죠. 이란이 해협 잠그고 결제 화폐를 바꾸라 했어요."
- deep_dive: "폭 33km — 세계 원유 20% 통과. 이란이 봉쇄 — 한국행 유조선이 해협에서 멈췄어요."

hero_headline 스타일 기준 (사건 유형에 따라 다름):
  [지리·자원 사건] "호르무즈 해협이 막혔는데,\\n한국 원유 70%가\\n거길 지나요" ← 지명이 핵심일 때
  [제도·외교 사건] "ICC, 이스라엘 장관 체포 영장 신청 — 382건\\n유가 $104 → 주유비↑ 배달비↑\\n한국 긴장도 73.8, 이번 주 ▲29.9" ← 기관명+인물명이 핵심일 때
  [전쟁·공격 사건] "러시아 드론, 키이우 공습 — 219건\\n에너지 공급로 불안 → 유가↑\\n한국 긴장도 73.8, ▲29.9 급등" ← 국가+행동이 핵심일 때

hero_headline 절대 금지:
  ⛔ "법원 도장 하나 — 세계가 흔들렸다" (비유, 주어 없음)
  ⛔ "헤이그가 스모트리치에 체포 영장 신청" (주어 어색, '헤이그가' ← 도시가 신청하지 않음)
  ⛔ "한국은?" (질문형 끝맺음, 맥락 없음)

이번 주 핵심 비유: "{editorial_brief.get('core_metaphor', '')}"

아래 텍스트를 위 기준으로 개선해라:
{json.dumps(refine_fields, ensure_ascii=False, indent=2)}

개선 규칙:
1. 단문 폭격 — 문장당 25자 이내 선호
2. editors_note_p1에 핵심 비유 반드시 사용
3. "영향", "상황", "갈등" 같은 추상어 → 구체 지명+숫자로 교체
4. 불필요한 연결어("그리고", "하지만", "또한") 제거
5. 같은 키 이름으로 개선된 값만 반환 (개선 불필요하면 원본 유지)
6. 같은 지명·시설명이 출력 전체에서 2회 초과 등장하면 3번째부터 "이 지역" / "이 시설" / "해당 지점" 으로 교체
JSON만 반환."""
        else:
            refine_prompt = f"""Vol.1 actual text (use this density and rhythm as the standard):
- editors_note: "One thing makes this week different. One strait shook the world. Iran locked it and demanded yuan payments."
- deep_dive: "33km wide — 20% of world oil. Iran blockade — Korea-bound tankers stopped."
- hero: "Hormuz is blocked —\\n70% of Korea's oil\\ngoes through there"

This week's core metaphor: "{editorial_brief.get('core_metaphor', '')}"

Improve the following text to Vol.1 style:
{json.dumps(refine_fields, ensure_ascii=False, indent=2)}

Rules:
1. Short punchy sentences — under 60 chars preferred
2. MUST use core metaphor in editors_note_p1
3. Replace vague words ("impact", "situation", "tensions") with specific locations + numbers
4. Remove filler connectors ("however", "additionally", "furthermore")
5. Return same key names with improved values only (keep original if already good)
6. If same location name / facility name appears more than 2 times total, replace 3rd+ with "this facility" / "this region" / "the site"
Return JSON only."""

        r4 = await call_gpt(refine_prompt, system, max_tokens=800, fields_hint="refine(vol1_style)")
        p4 = _parse_gpt_json(r4)
        if p4:
            merged.update(p4)
            print(f"    → 정제 완료: {list(p4.keys())}")

    # 후처리: CJK/키릴 → 헤지 치환 → 반복 제거
    if is_kr:
        for k, v in merged.items():
            if isinstance(v, str):
                merged[k] = _fix_cjk(v)
        merged = _fix_hedges(merged)
        merged = _deduplicate_phrases(merged, lang="kr")
        merged = _dynamic_dedup_kr(merged)   # 동적 반복 감지 (매주 바뀌는 지명 대응)
    else:
        merged = _deduplicate_phrases(merged, lang="us")

    return merged


# ── 후처리 1: 헤지 표현 → 직접 표현 치환 ────────────────────────────────────
_KR_HEDGE_MAP = [
    # (원본 패턴, 대체 표현) — 순서 중요: 긴 것 먼저
    ("것으로 예상됩니다",            "전망됩니다"),
    ("것으로 예상돼요",              "전망돼요"),
    ("될 것으로 예상",              "될 전망"),
    ("발생할 것으로",               "발생 예정"),
    ("진행될 것으로",               "진행 예정"),
    ("될 수 있습니다",              "됩니다"),
    ("올라갈 수 있습니다",           "오릅니다"),
    ("올라갈 수 있어요",             "올라요"),
    ("올라갈 수 있",               "오를"),
    ("영향을 미칠 수 있습니다",       "직결됩니다"),
    ("영향을 미칠 수 있어요",         "직결돼요"),
    ("영향을 줄 수 있습니다",         "직결됩니다"),
    ("영향을 줄 수 있어요",           "직결돼요"),
    ("영향을 미칩니다",              "이어집니다"),
    ("영향을 미쳐요",               "이어져요"),
    ("영향받을 수 있",              "직격탄을 맞을 수 있"),
    ("예의 주시해야 합니다",          "확인해야 합니다"),
    ("예의 주시해야 해요",            "확인해야 해요"),
    ("주시해야 합니다",              "체크해야 합니다"),
    ("주시해야 해요",               "체크해야 해요"),
    ("지켜볼 필요가 있습니다",         "확인할 포인트입니다"),
    ("지켜볼 필요가 있어요",           "확인할 포인트예요"),
    ("불안정한 상황",               "충돌 지속"),
    ("중동의 안정성",               "중동 에너지 공급"),
    ("매우 심각합니다",             "심각합니다"),
    ("매우 위급합니다",             "위급합니다"),
    ("더할 수 있습니다",            "악화됩니다"),
]


def _fix_hedges(ed: dict) -> dict:
    """헤지 표현을 직접적 표현으로 치환. 한국어 전용."""
    target_fields = [
        "brief_1_desc", "brief_2_desc", "brief_3_desc",
        "editors_note_p1", "editors_note_p2", "editors_note_p3",
        "energy_p1", "energy_p2", "energy_p3",
        "deep_dive_p1", "deep_dive_p2", "deep_dive_p3", "deep_dive_p4", "deep_dive_why",
        "impact_1", "impact_2", "impact_3", "impact_4",
        "next_week_1", "next_week_2", "next_week_3",
        "tension_warning",
    ]
    fixed = 0
    for field in target_fields:
        text = ed.get(field, "")
        if not text:
            continue
        for hedge, replacement in _KR_HEDGE_MAP:
            if hedge in text:
                text = text.replace(hedge, replacement)
                fixed += 1
        ed[field] = text
    if fixed:
        print(f"    → 헤지 표현 {fixed}건 치환 완료")
    return ed


# ── 후처리 2: 반복 구절 → alias 교체 ─────────────────────────────────────────
_KR_REPEAT_ALIASES: list[tuple[str, list[str]]] = [
    # 사건명 반복 → 대명사/약칭
    ("가자지구 공습으로",    ["이번 공격으로", "해당 작전으로"]),
    ("가자지구 공습",       ["이번 공습", "해당 공격"]),
    ("이스라엘과 레바논의",  ["이 갈등의", "양측의", "해당 분쟁의"]),
    ("이스라엘-레바논의",    ["이 분쟁의", "양측의"]),
    ("이스라엘과 레바논",    ["이 갈등", "양측", "이 분쟁"]),
    ("이스라엘-레바논",      ["이 분쟁", "양측", "이 갈등"]),  # "이 휴전" 금지: "이스라엘-레바논 휴전" → "이 휴전 휴전" 이중치환 방지
    # 역순 형태 (GPT가 레바논-이스라엘 순서로 쓰는 경우 대응)
    ("레바논-이스라엘의",    ["이 분쟁의", "양측의"]),
    ("레바논과 이스라엘의",  ["이 갈등의", "양측의"]),
    ("레바논-이스라엘",      ["이 분쟁", "양측", "이 갈등"]),  # "이 휴전" 금지: 동일 이유
    ("레바논과 이스라엘",    ["이 갈등", "양측", "이 분쟁"]),
    # 가자지구 반복
    ("가자지구의",          ["이 지역의", "현지의"]),
    ("가자지구에",          ["이 지역에", "현지에"]),
    # 유가 표현 반복 방지 (섹션별 다른 표현 사용)
    ("유가 상승으로 인한",   ["배럴당 상승으로", "에너지 가격 급등으로", "$X 돌파로"]),
    ("유가 상승으로 인해",   ["배럴당 상승 여파로", "에너지 가격 급등 여파로"]),
    ("유가 상승으로",        ["배럴당 ↑로", "에너지 비용 급등으로"]),
    ("유가 하락으로 인한",   ["배럴당 하락으로", "에너지 가격 하락으로"]),
    ("유가 하락으로",        ["배럴당 ↓로", "에너지 비용 하락으로"]),
    # 막연 결과 표현 (헤지 치환 후에도 남은 것들)
    ("직결됩니다",          ["파급됩니다", "연결됩니다"]),
    ("이어집니다",          ["파급됩니다", "이어져요"]),
    # 헤지 치환 결과물 과잉 반복 방지 (예상됩니다 → 전망됩니다 × 3회)
    ("전망됩니다",          ["확인됩니다", "이어집니다"]),
    ("전망돼요",            ["확인돼요", "이어져요"]),
    ("예정입니다",          ["됩니다", "이어집니다"]),
    # 에너지 생활비 체인 포맷 반복 (앵커·에너지 두 프롬프트가 동일 포맷 사용)
    ("주유비↑ 배달비↑ 난방비↑", ["생활비↑ 물가↑ 지출↑", "에너지비↑ 운송비↑ 식비↑"]),
    ("주유비↑ 배달비↑",         ["연료비↑ 운송비↑", "에너지비↑ 배달비↑"]),
    ("장바구니↑",               ["식료품비↑", "생필품↑", "물가↑"]),
    ("장바구니 물가",            ["생필품 가격", "소비자 물가"]),
    ("주유소 가격표",            ["주유 단가", "리터당 가격"]),
]

_EN_REPEAT_ALIASES: list[tuple[str, list[str]]] = [
    # Daily life chain — "gas↑ delivery↑ groceries↑" repeats across energy/brief/editors sections
    ("gas↑ delivery↑ groceries↑",  ["fuel↑ shipping↑ inflation↑", "prices↑ bills↑ costs↑"]),
    ("gas↑ delivery↑",              ["fuel costs↑ shipping↑", "energy bills↑ logistics↑"]),
    # Oil price repetition
    ("oil surge",           ["price spike", "crude jump"]),
    ("oil surged",          ["crude climbed", "prices jumped"]),
    ("due to oil",          ["amid rising crude", "with energy costs up"]),
    ("because of oil",      ["amid the price spike", "with crude climbing"]),
    ("oil prices surged",   ["crude hit new highs", "energy costs jumped"]),
    ("oil prices rose",     ["crude climbed", "energy prices gained"]),
    ("the conflict",        ["this war", "the fighting", "the crisis"]),
    ("the war",             ["this conflict", "the fighting"]),
    ("Gaza Strip",          ["the enclave", "this region"]),
    ("Israel and Lebanon",  ["both sides", "the parties", "the combatants"]),
    ("Lebanon and Israel",  ["both sides", "the parties"]),
]

_DEDUP_FIELD_ORDER = [
    "hero_headline", "preheader",
    "brief_1_title", "brief_1_desc",
    "brief_2_title", "brief_2_desc",
    "brief_3_title", "brief_3_desc",
    "editors_note_p1",
    "energy_intro", "energy_p1", "energy_p2", "energy_p3",
    "deep_dive_title", "deep_dive_p1", "deep_dive_p2",
    "deep_dive_p3", "deep_dive_p4", "deep_dive_why",
    "impact_1", "impact_2", "impact_3", "impact_4",
    "editors_note_p2", "editors_note_p3", "editors_ps",
    "tension_warning", "did_you_know",
    "next_week_1", "next_week_2", "next_week_3",
]


def _deduplicate_phrases(ed: dict, lang: str = "kr") -> dict:
    """반복 구절을 alias로 교체. 첫 등장은 원본 유지, 두 번째부터 교체."""
    phrase_seen: dict[str, int] = {}
    replaced = 0
    alias_map = _KR_REPEAT_ALIASES if lang == "kr" else _EN_REPEAT_ALIASES

    for field in _DEDUP_FIELD_ORDER:
        text = ed.get(field, "")
        if not text or not isinstance(text, str):
            continue
        for phrase, aliases in alias_map:
            idx = 0
            while True:
                pos = text.find(phrase, idx)
                if pos == -1:
                    break
                count = phrase_seen.get(phrase, 0)
                if count == 0:
                    phrase_seen[phrase] = 1
                    idx = pos + len(phrase)
                else:
                    alias = aliases[(count - 1) % len(aliases)]
                    text = text[:pos] + alias + text[pos + len(phrase):]
                    phrase_seen[phrase] = count + 1
                    idx = pos + len(alias)
                    replaced += 1
        ed[field] = text

    if replaced:
        print(f"    → 반복 구절 {replaced}건 alias 교체 완료")
    return ed


# 동적 dedup용 suffix 분류표 (suffix 미매칭 구절은 교체 안 함 — 제너릭 폴백 없음)
_LOC_SUFFIX  = ["원전", "공항", "항구", "시설", "기지", "발전소", "항만", "군항",
                "주방", "센터", "병원", "학교", "캠프", "단지", "창고", "막사"]
_REG_SUFFIX  = ["지역", "남부", "북부", "해협", "도시", "해안", "반도", "평원",
                "수로", "마을", "지구", "거리", "구역", "해역", "항만"]
_EVT_SUFFIX  = ["공습", "충돌", "봉쇄", "전쟁", "분쟁", "침공", "포격", "작전",
                "교전", "공격", "폭격", "사태", "사건"]


def _dynamic_dedup_kr(ed: dict) -> dict:
    """4회+ 등장하는 2단어 이상 한글 구절(정적 alias 미포함)을 자동 탐지·교체.
    단일 단어(국가명·일반명사 등)는 제외 — 정적 alias map으로 처리."""
    all_text = " ".join(str(v) for v in ed.values() if isinstance(v, str))
    static_set = {p for p, _ in _KR_REPEAT_ALIASES}

    # ── 반드시 공백 포함 2단어 구절만 처리 (단일 단어 제외) ──────────────────
    candidates: dict[str, int] = {}
    for m in re.finditer(r'[가-힣]{2,}\s[가-힣]{2,}', all_text):
        phrase = m.group()
        if phrase in candidates or phrase in static_set:
            continue
        cnt = all_text.count(phrase)
        if cnt >= 4:
            candidates[phrase] = cnt

    if not candidates:
        return ed

    # 긴 구절 우선 처리 (짧은 것이 긴 것에 포함될 경우 건너뜀)
    for phrase in sorted(candidates, key=lambda p: (-len(p), -candidates[p])):
        if any(phrase != other and phrase in other for other in candidates):
            continue
        last = phrase.split()[-1]
        if any(last == s for s in _LOC_SUFFIX):
            aliases = ["이 시설", "해당 시설", "이 기지"]
        elif any(last == s for s in _REG_SUFFIX):
            aliases = ["이 지역", "해당 지역", "현지"]
        elif any(last == s for s in _EVT_SUFFIX):
            aliases = ["이 사태", "이번 충돌", "해당 사건"]
        else:
            continue  # suffix 미매칭 → 교체 안 함 (일반 복합어·지표명 보호)

        seen = 0
        alias_idx = 0
        for field in _DEDUP_FIELD_ORDER:
            text = ed.get(field, "")
            if not isinstance(text, str) or phrase not in text:
                continue
            new_text = ""
            idx = 0
            while True:
                pos = text.find(phrase, idx)
                if pos == -1:
                    new_text += text[idx:]
                    break
                seen += 1
                new_text += text[idx:pos]
                if seen >= 3:
                    repl = aliases[alias_idx % len(aliases)]
                    alias_idx += 1
                    new_text += repl
                else:
                    new_text += phrase
                idx = pos + len(phrase)
            ed[field] = new_text

        print(f"    → 동적 dedup: '{phrase}' ({candidates[phrase]}회) → '{aliases[0]}' 등")

    # 교체 후 "이 지점 이 지점", "이 시설 이 시설" 같은 연속 대명사 정리
    _DEDUP_PRONOUNS = ["이 시설", "이 지역", "이 사태", "이 지점", "해당 시설",
                       "해당 지역", "해당 사건", "이번 충돌", "해당 장소", "현지"]
    for field in _DEDUP_FIELD_ORDER:
        text = ed.get(field, "")
        if not isinstance(text, str):
            continue
        for pronoun in _DEDUP_PRONOUNS:
            # "이 시설. 이 시설" 또는 "이 시설이 이 시설" 같은 근접 반복 제거
            text = re.sub(
                rf'({re.escape(pronoun)})([\s,·—·]*\w*[\s,·—·]*){re.escape(pronoun)}',
                r'\1\2',
                text
            )
        ed[field] = text

    return ed


def _validate_editorial(ed: dict) -> list:
    """GPT 생성 결과 품질 문제 감지. 경고 목록 반환 (실패 아님 — 로그 목적)."""
    warnings = []
    all_text = " ".join(str(v) for v in ed.values() if isinstance(v, str))
    # CJK 잔여 확인
    if re.search(r'[\u4e00-\u9fff]', all_text):
        cjk_found = set(re.findall(r'[\u4e00-\u9fff]', all_text))
        warnings.append(f"CJK chars remain: {cjk_found}")
    # 반복 감지: 동일 8글자 이상 한글 구절이 3회 이상
    for phrase_len in [8, 12]:
        seen = set()
        texts = [v for v in ed.values() if isinstance(v, str) and len(v) > phrase_len]
        for t in texts:
            for i in range(len(t) - phrase_len):
                phrase = t[i:i+phrase_len]
                if phrase in seen: continue
                seen.add(phrase)
                cnt = all_text.count(phrase)
                if cnt >= 3 and re.search(r'[가-힣]{4}', phrase):
                    warnings.append(f"Repetition({phrase_len}): '{phrase}' x{cnt}")
                    break
    # 필드 최소 길이 확인
    min_lens = {"hero_headline": 15, "editors_note_p1": 30, "deep_dive_p1": 40}
    for field, min_len in min_lens.items():
        val = ed.get(field, "")
        if len(val) < min_len:
            warnings.append(f"Short field: {field} ({len(val)} chars)")
    # ── 할루시네이션 패턴 감지 (CRITICAL) ──
    hallucination_patterns = [
        (r'20(1[5-9]|2[0-4])년', "구형 연도 참조"),
        (r'10월\s*7일', "10월 7일 (2023 Hamas 테러 — 훈련 데이터)"),
        (r'하마스\s*(지도자|대표|수장)', "하마스 지도자 관련 (훈련 데이터 의심)"),
        (r'100만\s*명.*이재민|이재민.*100만\s*명', "100만 명 이재민 (훈련 데이터 의심)"),
        (r'1월|2월|3월|4월', "과거 월 참조 (이번 주 기간 외)"),
    ]
    for pattern, label in hallucination_patterns:
        found = re.findall(pattern, all_text)
        if found:
            # 필드별 위치 특정
            affected = [f for f, v in ed.items() if isinstance(v, str) and re.search(pattern, v)]
            warnings.append(f"🚨 HALLUCINATION: {label} → 필드: {affected}")
    return warnings


def _sanitize_hallucinations(ed: dict) -> dict:
    """검증에서 발견된 할루시네이션 패턴을 필드에서 직접 제거/치환.
    경고 출력 후 해당 필드를 빈 문자열로 초기화해 폴백 사용 유도."""
    critical_patterns = [
        r'20(1[5-9]|2[0-4])년',           # 구형 연도
        r'10월\s*7일',                      # Oct 7 Hamas attack
        r'하마스\s*(지도자|대표|수장)',      # Hamas leader
        r'100만\s*명.*이재민|이재민.*100만\s*명',  # 100만 명 이재민
    ]
    for field, val in list(ed.items()):
        if not isinstance(val, str): continue
        for pattern in critical_patterns:
            if re.search(pattern, val):
                print(f"    ⛔ 할루시네이션 필드 초기화: {field} (패턴: {pattern})")
                ed[field] = ""
                break
    return ed


# ── 폴백 에디터 콘텐츠 빌더 (GPT 실패 시) ───────────────────────────────────

def _build_fallback_editorial(ctx: dict, top_clusters: list, lang: str, vol: int = 1,
                               cluster_event_bodies: dict = None) -> dict:
    """GPT 실패 시 DB 데이터만으로 Vol.1 수준 텍스트 생성."""
    is_kr = lang == "kr"
    target = ctx['target_name']
    target_cc = ctx.get('target_cc', '')   # 국가코드 약어 (US/KR 등), 2차 언급용
    oil = ctx['oil_price']
    oil_ch_str = ctx['oil_change']
    try:
        oil_ch = float(oil_ch_str.replace('+', '')) if oil_ch_str not in ('N/A', '') else 0.0
    except Exception:
        oil_ch = 0.0
    score = ctx['target_tension']
    rank = ctx['target_rank']

    def cl_title(i=0):
        if not top_clusters or i >= len(top_clusters): return ""
        return (top_clusters[i][1] or top_clusters[i][0]) if is_kr else (top_clusters[i][0] or top_clusters[i][1])

    def _trunc_word(s: str, max_len: int) -> str:
        """공백 경계에서 자르기. max_len 이하에서 가장 긴 어절 단위 문자열 반환."""
        if len(s) <= max_len: return s
        cut = s[:max_len].rsplit(' ', 1)[0]
        return cut if cut else s[:max_len]

    def _first_body(cluster_idx: int) -> str:
        """cluster_event_bodies에서 해당 클러스터 body_ko 첫 완성 문장 추출. 영문판에서는 빈 문자열 반환."""
        if not is_kr: return ""  # 영문판에서는 한국어 body_ko 사용 금지
        if not cluster_event_bodies or not top_clusters or cluster_idx >= len(top_clusters): return ""
        cid = top_clusters[cluster_idx][7] if len(top_clusters[cluster_idx]) > 7 else ""
        bodies = cluster_event_bodies.get(cid, [])
        if not bodies: return ""
        raw = bodies[0].lstrip("· ").strip()
        # 첫 완성 문장만 추출: ". " 또는 ".\n" 기준 분리
        for sep in ('. ', '.\n'):
            idx = raw.find(sep)
            if idx > 10:  # 최소 10자 이상 문장
                return raw[:idx + 1]  # 마침표 포함
        # 분리 불가 → 최대 80자로 제한
        return raw[:80].rstrip() if len(raw) > 80 else raw

    t1 = cl_title(0)
    t2 = cl_title(1)
    t3 = cl_title(2)

    # hero_headline
    hero = (
        f"{t1},\n{target} 긴장도 {score}점" if is_kr
        else f"{t1}\n{target} Tension: {score}"
    )

    # preheader — events_7d 사용 (더 큰 숫자, Vol.1 형식)
    _ev7d = ctx.get('events_7d', ctx.get('events_24h', ''))
    preheader = (
        f"{_ev7d}건 감지, {ctx['crisis_count']}개국 위기, 긴장도 {score} — "
        f"내가 왜 영향받는지, 2분."
        if is_kr else
        f"{_ev7d} events, {ctx['crisis_count']} countries in crisis, tension {score} — "
        f"why it matters to you, in 2 min."
    )

    # energy — ↑↓ symbols always included
    _e_arrow = "↑" if oil_ch >= 0 else "↓"
    _oil_past = ctx.get('oil_price_past', oil)
    _ep = ctx.get('energy_period', '7일')
    energy_intro = (
        f"유가 ${_oil_past}→${oil}, {_ep}. {_e_arrow}{abs(oil_ch):.1f}% — 주유비{_e_arrow} 배달비{_e_arrow} 난방비{_e_arrow} 이미 시작." if is_kr
        else f"Oil ${_oil_past}→${oil}, {_ep}. {_e_arrow}{abs(oil_ch):.1f}% — gas{_e_arrow} delivery{_e_arrow} groceries{_e_arrow} already moving."
    )
    energy_p1 = (
        f"브렌트유 ${_oil_past} → ${oil} ({_e_arrow}{abs(oil_ch):.1f}%, {_ep})." if is_kr
        else f"Brent crude ${_oil_past} → ${oil} ({_e_arrow}{abs(oil_ch):.1f}%, {_ep})."
    )
    energy_p2 = (
        f"주유비{_e_arrow} 배달비{_e_arrow} 난방비{_e_arrow} — 이미 시작." if is_kr
        else f"gas{_e_arrow} delivery{_e_arrow} groceries{_e_arrow} — already starting."
    )
    _tgt_short = target_cc if (not is_kr and target_cc) else target  # 영문 2차 언급은 코드 약어
    energy_p3 = (f"다음 주 유가 흐름과 {target} 물가 — 주시하세요." if is_kr
                 else f"Next week: oil trend and {_tgt_short} inflation — watch closely.")

    # deep dive
    ev0 = top_clusters[0][5] if top_clusters else 0
    _body0 = _first_body(0)
    deep_p1 = _body0 if _body0 else (
        f"{t1}: {ev0:,}건 이벤트가 확인됐어요." if is_kr
        else f"{ev0:,} events confirmed this week — situation still evolving."  # t1 중복 방지
    )
    _body2 = _first_body(1)
    _body3 = _first_body(2)
    deep_p2 = (
        _body2 if _body2 else
        ("주요국들이 성명을 내놓고 외교 채널이 가동됐습니다." if is_kr
         else "Major powers issued statements as diplomatic channels activated.")
    )
    deep_p3 = (
        _body3 if _body3 else
        (f"{target}: 에너지·무역·안보 3중 타격." if is_kr
         else f"{_tgt_short}: energy, trade, and security — triple impact.")
    )
    deep_p4 = ("다음 주 공식 입장과 시장 반응 — 놓치지 마세요." if is_kr
               else "Next week: official positions and market reactions — watch closely.")
    deep_why = (f"{t1} — 공급망·에너지·외교 3중 파급." if is_kr
                else "Supply chain, energy, and diplomacy — triple ripple effect.")

    # editors note — — 구분자 포함해야 _editors_note_style_p1() <b> 적용됨
    _arrow_ed = "↑" if oil_ch >= 0 else "↓"
    _body_ed = _first_body(1) or _first_body(0)  # cluster 1 우선 (deep_p1이 cluster 0 사용)
    if is_kr:
        ed_p1 = (
            f"{t1[:20]} — 이번 주 {ctx['crisis_count']}개국이 위기 상태입니다."
            if not _body_ed else
            f"{_body_ed} — 현장은 지금도 진행 중."
        )
        ed_p2 = f"유가 {_arrow_ed}{abs(oil_ch):.1f}%, {target} 긴장도 {score} — 주유비{_arrow_ed} 배달비{_arrow_ed} 지갑까지 옵니다."
        ed_p3 = "다음 주도 함께 살펴봐요. 안전한 한 주 되세요."
        ed_ps = "다음 호 놓치지 마세요 — 매주 일요일 발행."
    else:
        # 영문은 _body_ed 미사용 (한국어 body_ko). t1 반복 방지 위해 긴장도+유가 기반으로 대체
        ed_p1 = (
            f"{target} tension at {score} — oil at ${oil} is deepening the impact across {ctx['crisis_count']} countries."
        )
        ed_p2 = f"Oil {_arrow_ed}{abs(oil_ch):.1f}%, {_tgt_short} tension {score} — gas{_arrow_ed} delivery{_arrow_ed} already in your wallet."
        ed_p3 = "We'll be watching next week too. Stay safe."
        ed_ps = "Don't miss next week — published every Sunday."

    # brief items
    brief_1_title = _trunc_word(t1, 25) if t1 else ("주요 이슈" if is_kr else "Top Issue")
    brief_2_title = _trunc_word(t2, 25) if t2 else (f"{ctx['crisis_count']}개국 위기" if is_kr else f"{ctx['crisis_count']} crisis countries")
    brief_3_title = (f"{target} 긴장도 {score}" if is_kr else f"{_tgt_short} tension {score}")
    _b1_body = _first_body(0)
    _b2_body = _first_body(2)  # cluster 2 우선 (cluster 1은 ed_p1+deep_p2에서 이미 사용)
    ev1 = top_clusters[1][5] if len(top_clusters) > 1 else 0
    brief_1_desc = (
        _b1_body if _b1_body
        else (f"{ev0:,}건 이벤트 — 상황 진행 중." if is_kr else f"{ev0:,} events — situation ongoing.")
    )
    brief_2_desc = (
        _b2_body if _b2_body
        else (f"{ev1:,}건 이벤트 — 에너지·안보 영향." if is_kr else f"{ev1:,} events — energy & security impact.")
    )
    brief_3_desc = (f"세계 {rank}위 — {_arrow_ed}{abs(oil_ch):.1f}% 유가 직격." if is_kr else f"Ranked #{rank} globally — oil {_arrow_ed}{abs(oil_ch):.1f}% direct hit.")

    # next week — t1은 brief_1+deep에서 이미 사용, t2로 분산
    next_1 = (
        (f"{_trunc_word(t2, 20)} 동향" if t2 else f"{t1[:15]} 동향") if is_kr
        else (f"{_trunc_word(t2, 20)} developments" if t2 else f"{t1[:15]} updates")
    )
    next_2 = (f"유가 ${oil} 흐름과 {target} 물가 영향" if is_kr else f"Oil ${oil} trend and {_tgt_short} inflation impact")
    next_3 = (
        (f"{_trunc_word(t3, 18)} 경과" if is_kr else f"{_trunc_word(t3, 18)} follow-up") if t3
        else ("여행 안전 지역 변동" if is_kr else "Travel advisory changes")
    )

    # share
    share_hl = ("2분이면 세계가 보여요." if is_kr else "The world makes sense in 2 minutes.")
    share_sub = ("출장 동료, 주식 보는 친구, 기름값 걱정하는 분께." if is_kr
                 else "Share with coworkers, investors, and anyone who travels.")

    # pro cta — 긴장도 방향에 맞는 동사 사용
    _delta_str = ctx.get('target_delta', '')
    _cta_dir_kr = "급등" if _delta_str.startswith('▲') else ("급락" if _delta_str.startswith('▼') else "변동")
    _cta_dir_en = "surged" if _delta_str.startswith('▲') else ("dropped" if _delta_str.startswith('▼') else "shifted")
    pro_cta = (f"{target} 긴장도 {score} {_cta_dir_kr} —\nPro는 그 순간 알림을 받아요." if is_kr
               else f"{_tgt_short} tension {score} {_cta_dir_en} —\nPro users get instant alerts.")
    pro_sub = ("당신은 일요일에 읽고 있죠." if is_kr else "You're reading this on Sunday.")

    # calendar events
    cal_events = [
        (f"UN 안보리 {t1[:15]} 긴급 회의" if is_kr else f"UN Security Council on {t1[:15]}"),
        (f"{target} 긴장도 동향 발표" if is_kr else f"{_tgt_short} tension index update"),
        (f"주요국 외교 협상 일정" if is_kr else "Key diplomatic negotiations"),
        (f"글로벌 에너지 시장 주간 발표" if is_kr else "Global energy market weekly update"),
    ]
    cal_tags = [
        (["안보", "외교"] if is_kr else ["security", "diplomacy"]),
        (["한국", "안보"] if is_kr else [_tgt_short.lower(), "security"]),
        (["외교", "안보"] if is_kr else ["diplomacy", "security"]),
        (["에너지", "경제"] if is_kr else ["energy", "economy"]),
    ]

    # did_you_know — vol 기반 로테이션
    DYK_LIBRARY_KR = [
        f"한국 에너지 자급률 OECD 38국 최하위 16%. 원유 70% 호르무즈 경유. 막히면 비축유 90일.",
        f"세계 분쟁으로 인한 실향민 1.1억 명 — 역대 최고. 냉전 종식 후 30년 만에 최대.",
        f"글로벌 곡물 가격 지수 3년 연속 상승. 분쟁 지역 식량 위기 47개국에 영향.",
        f"전 세계 핵무기 약 12,500개. 9개국 보유. 한반도 30km 내 집중.",
        f"호르무즈 해협 폭 33km — 하루 유조선 21척. 세계 원유 20%, LNG 25% 통과.",
    ]
    DYK_LIBRARY_EN = [
        f"South Korea's energy self-sufficiency: 16% — OECD's lowest. 70% of oil through Hormuz.",
        f"110 million displaced by conflict globally — the highest on record since World War II.",
        f"Global food price index: rising 3 years straight. 47 countries face crisis-level shortage.",
        f"~12,500 nuclear warheads across 9 countries. Concentrated within 30km of the Korean Peninsula.",
        f"Hormuz Strait: 33km wide — 21 tankers daily. 20% of world oil, 25% of LNG passes through.",
    ]
    dyk_lib = DYK_LIBRARY_KR if is_kr else DYK_LIBRARY_EN
    did_you_know = dyk_lib[vol % len(dyk_lib)]

    return {
        "hero_headline": hero,
        "preheader": preheader,
        "brief_1_title": brief_1_title, "brief_1_desc": brief_1_desc,
        "brief_2_title": brief_2_title, "brief_2_desc": brief_2_desc,
        "brief_3_title": brief_3_title, "brief_3_desc": brief_3_desc,
        "energy_intro": energy_intro,
        "energy_p1": energy_p1, "energy_p2": energy_p2, "energy_p3": energy_p3,
        "deep_dive_title": t1, "deep_dive_p1": deep_p1, "deep_dive_p2": deep_p2,
        "deep_dive_p3": deep_p3, "deep_dive_p4": deep_p4, "deep_dive_why": deep_why,
        "impact_1": (
            (f"분쟁 이슈 — {ev0:,}건 이벤트 직격" if is_kr  # t1 반복 방지
             else f"{ev0:,} events — direct security impact" if ev0
             else "Security situation evolving")
        ),
        "impact_2": (f"유가 {_arrow_ed}{abs(oil_ch):.1f}% — 에너지·원자재 직격" if is_kr
                     else f"Oil {_arrow_ed}{abs(oil_ch):.1f}% — energy & commodity costs"),
        "impact_3": ("물가·환율·운송비 연쇄 영향" if is_kr else "Prices, FX, and freight: chain reaction"),
        "impact_4": (f"{target} 소비·경제 파급" if is_kr else f"{_tgt_short} economy ripple effects"),
        "editors_note_p1": ed_p1, "editors_note_p2": ed_p2, "editors_note_p3": ed_p3,
        "editors_ps": ed_ps,
        "next_week_1": next_1, "next_week_2": next_2, "next_week_3": next_3,
        "share_headline": share_hl, "share_subtext": share_sub,
        "pro_cta_headline": pro_cta, "pro_cta_subtext": pro_sub,
        "tension_warning": "",
        "did_you_know": did_you_know,
        "country_summary": ("에너지·안보·물가 동시 영향." if is_kr else "Energy, security, and prices — all at once."),
        "calendar_1_event": cal_events[0], "calendar_1_tags": cal_tags[0],
        "calendar_2_event": cal_events[1], "calendar_2_tags": cal_tags[1],
        "calendar_3_event": cal_events[2], "calendar_3_tags": cal_tags[2],
        "calendar_4_event": cal_events[3], "calendar_4_tags": cal_tags[3],
    }


def _generate_country_summary(cc: str, score: float, oil_change, is_kr: bool) -> str:
    """GPT country_summary 없을 때 DB 기반 2-3문장 생성 — Vol.1 수준 punch."""
    factors = []
    if oil_change is not None and abs(oil_change) > 5:
        factors.append("에너지" if is_kr else "energy")
    if score >= 80:
        factors.append("안보" if is_kr else "security")
    if oil_change is not None and oil_change > 10:
        factors.append("물가" if is_kr else "inflation")
    if cc in ['KR', 'JP', 'TW', 'SG']:
        factors.append("반도체" if is_kr else "semiconductors")
    if score >= 30:
        factors.append("증시" if is_kr else "stocks")
    if not factors:
        factors = ["안보·외교" if is_kr else "security·diplomacy"]
    sep = "·" if is_kr else " & "
    factor_str = sep.join(factors[:4])
    if is_kr:
        if len(factors) >= 3:
            return f"{factor_str} 동시 타격. 과장? 하나면 그래 보이죠. 동시면 다르죠."
        else:
            return f"{factor_str} 직격. 이번 주가 다른 이유."
    else:
        if len(factors) >= 3:
            return f"{factor_str} — all hit at once. One alone? Maybe fine. All together? Different story."
        else:
            return f"{factor_str} — direct hit this week."


# ── HTML 빌더 (Vol.1 스타일) ─────────────────────────────────────────────────

def build_tension_table_html(rows: list, lang: str, target_cc: str = "KR") -> str:
    if not rows: return "<p>No data</p>"
    html = ['<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">']
    # 헤더행
    html.append(
        '<tr>'
        '<td width="22" style="padding:8px 0;font-size:9px;font-weight:600;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;"></td>'
        '<td style="padding:8px 0;font-size:9px;font-weight:600;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">COUNTRY</td>'
        '<td width="52" style="padding:8px 0;font-size:9px;font-weight:600;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;text-align:right;">SCORE</td>'
        '</tr>'
    )
    for i, (cc, score, delta) in enumerate(rows[:10]):
        flag = get_flag(cc)
        name = cn(cc, lang)
        color = sev_color(tension_num(score))
        is_target = cc == target_cc
        is_top = i == 0

        if is_top:
            row_extra = ' style="box-shadow:0 0 0 2px rgba(220,38,38,.1);background:#fff5f5;"'
        elif is_target:
            row_extra = ' style="background:#f8f8f7;"'
        elif i % 2 == 0:
            row_extra = ' style="background:#fafafa;"'
        else:
            row_extra = ''

        rank_txt = f'▶&nbsp;{i+1}' if is_target else str(i+1)
        rank_color = '#18181b' if is_target else ('#dc2626' if is_top else '#a1a1aa')
        rank_weight = '700' if (is_top or is_target) else 'normal'
        pad_rank = '10px 6px' if is_top else ('10px 0 10px 6px' if is_target else '7px 0')

        you_badge = (' <span style="display:inline-block;font-weight:700;font-size:9px;border-radius:2px;color:#fff;background:#18181b;padding:1px 5px;">YOU</span>' if is_target else '')
        name_weight = '800' if (is_top or is_target) else 'normal'
        name_color = '#18181b' if (is_top or is_target) else '#52525b'

        ds_html = ''
        if delta > 0.5:
            ds_html = f'&nbsp;<span style="font-size:10px;color:#dc2626;font-weight:600;white-space:nowrap;">▲{abs(delta):.1f}</span>'
        elif delta < -0.5:
            ds_html = f'&nbsp;<span style="font-size:10px;color:#22c55e;font-weight:600;white-space:nowrap;">▼{abs(delta):.1f}</span>'

        score_font = 'font-family:Georgia,"Times New Roman",serif;'
        score_size = '18px' if is_top else ('16px' if is_target else '13px')
        score_weight = '800' if (is_top or is_target) else '600'
        score_color = '#18181b' if is_target else color

        url = f'https://www.wewantpeace.live/issues/country/{cc}?utm_source=nl&utm_medium=em&utm_campaign=v1'
        pad_cell = '10px 4px' if is_top else '7px 4px'

        html.append(
            f'<tr{row_extra}>'
            f'<td style="padding:{pad_rank};font-size:12px;font-weight:{rank_weight};color:{rank_color};white-space:nowrap;">{rank_txt}</td>'
            f'<td style="padding:{pad_cell};white-space:nowrap;">'
            f'<a href="{url}" style="text-decoration:none;color:{name_color};font-weight:{name_weight};">{flag} {name}{you_badge}</a>{ds_html}'
            f'</td>'
            f'<td style="padding:{pad_cell};text-align:right;{score_font}font-size:{score_size};font-weight:{score_weight};color:{score_color};">{score:.1f}</td>'
            f'</tr>'
        )
    html.append('</table>')
    return '\n'.join(html)


def build_todays_brief_html(items: list, lang: str) -> str:
    """Vol.1 스타일: 번호 뱃지 + 컬러 보더 카드 + desc. 빈 title은 건너뜀."""
    colors = ["#dc2626", "#dc2626", "#18181b"]
    bgs = ["#fef2f2", "#fef2f2", "#fafafa"]
    html = []
    idx = 0  # 실제 렌더 순번 (title 있는 항목만)
    for i, (title, desc) in enumerate(items[:3]):
        if not title:
            continue  # 빈 GPT 결과 skip — 뱃지만 나오는 문제 방지
        c, bg = colors[min(idx, 2)], bgs[min(idx, 2)]
        badge_num = idx + 1
        desc_html = f'<p style="font-size:11px;color:#71717a;margin:4px 0 0;line-height:1.5;">{desc}</p>' if desc else ""
        html.append(
            f'<tr><td style="border-radius:6px;background:{bg};padding:10px 14px;border-left:3px solid {c};">'
            f'<p style="font-size:14px;color:#27272a;margin:0;line-height:1.7;">'
            f'<span style="display:inline-block;font-weight:700;text-align:center;font-size:10px;vertical-align:middle;'
            f'color:#fff;background:{c};border-radius:50%;margin-right:4px;width:18px;height:18px;line-height:18px;">{badge_num}</span>'
            f'<span style="color:#27272a;">{title}</span></p>{desc_html}</td></tr>'
            f'<tr><td height="8"></td></tr>')
        idx += 1
    return "\n".join(html)


def _why_matters(sev: int, kscore: float, cc: str, target_cc: str, lang: str) -> str:
    """cc + kscore 기반 타겟 국가 연결 문구. cc별 특화 → 반복 방지."""
    is_kr = lang == "kr"
    target = cn(target_cc, lang)
    if cc == target_cc:
        return f"이번 주 {target} 핵심 이슈" if is_kr else f"This week's top issue for {target}"
    if kscore >= 8.0:
        # cc별 구체 문구 — 동일 고kscore 클러스터 반복 방지
        _kr_map = {
            "IL": "이스라엘 분쟁 — 중동 유가·공급망 직접 영향",
            "LB": "레바논 분쟁 — 중동 공급로 불안 가중",
            "IR": "이란 — 호르무즈 해협·유가 방향 결정",
            "PS": "가자 전쟁 — 중동 전체 긴장 지속 배경",
            "SY": "시리아 — 지역 불안·난민 공급망 여파",
            "YE": "예멘 — 홍해 해운 경로 위협",
            "SA": "사우디 — OPEC 산유량·유가 직결",
            "UA": "우크라이나 — 에너지·곡물 공급망 영향",
            "RU": "러시아 — 에너지 시장·글로벌 공급 교란",
            "CN": "중국 — 한국 수출입 1위 파트너, 무역 직결",
            "US": "미국 — 달러·금리·수출 정책 직접 영향",
            "TW": "대만 — 반도체 공급망 한국 직격",
            "KP": "북한 — 한반도 안보·대남 리스크",
        }
        _en_map = {
            "IL": "Israel conflict — direct impact on oil & supply chains",
            "LB": "Lebanon — Middle East supply route risk",
            "IR": "Iran — Strait of Hormuz & oil price direction",
            "PS": "Gaza war — underlying Middle East tension driver",
            "UA": "Ukraine — energy & grain supply chain impact",
            "RU": "Russia — energy market & global supply disruption",
            "CN": "China — top trade partner, direct economic link",
            "US": "US — dollar, rates & export policy impact",
        }
        return (_kr_map.get(cc, f"{target} 직접 영향 — 에너지·무역·안보 연계") if is_kr
                else _en_map.get(cc, f"Direct impact on {target} — energy, trade, security"))
    if kscore >= 5.0:
        return f"{target} 에너지·수입 경로 영향 가능" if is_kr else f"May affect {target}'s energy and import routes"
    if sev >= 5:
        return "전 세계 공급망 충격 위험" if is_kr else "Risk of global supply chain shock"
    if sev >= 4:
        return "주요국 외교 대응 촉발" if is_kr else "Triggers major power diplomatic responses"
    return "국제 정세 주시 필요" if is_kr else "International situation to monitor"


def build_conflict_stories_html(clusters: list, lang: str, vol: int = 1,
                                target_cc: str = "KR", skip_first_image: bool = True) -> str:
    """각 카드를 <tr><td> 로 래핑 — 이메일 테이블 컨텍스트에서 올바른 DOM 위치 유지."""
    if not clusters: return ""
    is_kr = lang == "kr"

    label_sets_kr = [("TOP STORY", "주간 요약"), ("긴급", "지속"), ("확대", "주시")]
    label_sets_en = [("TOP STORY", "Weekly"), ("BREAKING", "ONGOING"), ("ESCALATING", "WATCH")]
    labels = (label_sets_kr if is_kr else label_sets_en)[vol % 3]

    rows = []
    for i, cluster in enumerate(clusters[:5]):
        title, title_ko, cc, sev, kscore, event_count, image_url, *_ = cluster
        flag = get_flag(cc)
        color = sev_color(min(sev, 5))
        bg = {"#ef4444": "#fef2f2", "#f97316": "#fff7ed", "#eab308": "#fefce8"}.get(color, "#f8fafc")
        display = (title_ko or title or "") if is_kr else (title or title_ko or "")
        ev_l = f"{event_count}건 확인" if is_kr else f"{event_count} sources confirmed"

        why = _why_matters(sev, kscore or 0, cc or "", target_cc, lang)

        tag = labels[0] if i == 0 else labels[1]
        tag_bg = "#dc2626" if i == 0 else "#71717a"

        # 첫 번째 = 큰 카드 (hero 이미지와 중복 방지: skip_first_image=True면 이미지 생략)
        if i == 0:
            img_html = (
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
                f'<tr><td style="padding:0;">'
                f'<img src="{image_url}" style="display:block;width:100%;max-width:100%;height:auto;border:0;" alt="">'
                f'</td></tr></table>'
            ) if (image_url and not skip_first_image) else ""
            why_html = (
                f'<p style="margin:8px 0 0;padding:8px 10px;background:#fff5f5;border-radius:4px;font-size:11px;color:#dc2626;font-weight:600;">'
                f'{"왜 중요해요?" if is_kr else "Why it matters?"} {why}</p>'
            ) if why else ""
            inner = (
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                f'style="border-radius:8px;border:1px solid #e5e5e5;overflow:hidden;">'
                f'<tr><td>{img_html}</td></tr>'
                f'<tr><td style="padding:14px 16px;">'
                f'<p style="margin:0;">'
                f'<span style="background:{tag_bg};color:white;padding:2px 8px;border-radius:3px;font-size:9px;font-weight:700;letter-spacing:.5px;">{tag}</span>'
                f'</p>'
                f'<p style="font-weight:bold;font-size:15px;margin:8px 0 4px;">{flag} {display[:80]}</p>'
                f'<p style="margin:0;">'
                f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{"심각도" if is_kr else "Severity"} {min(sev, 100)}</span>'
                f'<span style="color:#666;font-size:11px;margin-left:8px;">{ev_l}</span>'
                f'</p>'
                f'{why_html}'
                f'</td></tr></table>'
            )
            rows.append(f'<tr><td style="background:#fff;padding:0 28px 16px;">{inner}</td></tr>')
        else:
            # 2-5번 카드: 이미지 있으면 사이드 이미지 레이아웃
            why_html = (
                f'<p style="font-size:10px;color:#dc2626;margin:2px 0 0;font-weight:600;">{why}</p>'
            ) if why else ""
            if image_url:
                inner = (
                    f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                    f'style="border-radius:6px;border:1px solid #e5e5e5;border-left:3px solid {color};background:{bg};overflow:hidden;">'
                    f'<tr>'
                    f'<td width="160" valign="middle" style="padding:0;vertical-align:middle;">'
                    f'<img src="{image_url}" width="160" style="display:block;width:160px;height:auto;border:0;border-radius:6px 0 0 6px;" alt=""/>'
                    f'</td>'
                    f'<td style="padding:10px 12px;vertical-align:middle;">'
                    f'<p style="margin:0;">'
                    f'<span style="background:{tag_bg};color:white;padding:1px 6px;border-radius:3px;font-size:8px;font-weight:700;letter-spacing:.5px;">{tag}</span>'
                    f'</p>'
                    f'<p style="font-weight:bold;font-size:13px;margin:4px 0 2px;">{flag} {display[:80]}</p>'
                    f'<p style="margin:0;">'
                    f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{"심각도" if is_kr else "Severity"} {min(sev, 100)}</span>'
                    f'<span style="color:#666;font-size:11px;margin-left:8px;">{ev_l}</span>'
                    f'</p>'
                    f'{why_html}'
                    f'</td>'
                    f'</tr></table>'
                )
            else:
                inner = (
                    f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                    f'style="border-radius:6px;border:1px solid #e5e5e5;border-left:3px solid {color};background:{bg};">'
                    f'<tr><td style="padding:10px 12px;">'
                    f'<p style="margin:0;">'
                    f'<span style="background:{tag_bg};color:white;padding:1px 6px;border-radius:3px;font-size:8px;font-weight:700;letter-spacing:.5px;">{tag}</span>'
                    f'</p>'
                    f'<p style="font-weight:bold;font-size:13px;margin:4px 0 2px;">{flag} {display[:80]}</p>'
                    f'<p style="margin:0;">'
                    f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{"심각도" if is_kr else "Severity"} {min(sev, 100)}</span>'
                    f'<span style="color:#666;font-size:11px;margin-left:8px;">{ev_l}</span>'
                    f'</p>'
                    f'{why_html}'
                    f'</td></tr></table>'
                )
            rows.append(f'<tr><td style="background:#fff;padding:0 28px 10px;">{inner}</td></tr>')
    return "\n".join(rows)


def build_energy_html(intro: str, p1: str, p2: str, p3: str, oil_price, oil_change, lang: str,
                      breaking_cluster=None) -> str:
    """Vol.1 스타일: BREAKING 포토카드(선택) + 가격 분석 박스.
    breaking_cluster: (title, title_ko, cc, sev, kscore, event_count, image_url)
    """
    price_str = f"${oil_price:.0f}" if oil_price else "N/A"
    change_str = f"{oil_change:+.1f}%" if oil_change is not None else ""
    change_color = "#dc2626" if (oil_change or 0) > 0 else "#22c55e"
    is_kr = lang == "kr"
    label = "한국 체감" if is_kr else "Impact"

    rows = []

    # 1. BREAKING 포토카드 (이미지 있을 때)
    if breaking_cluster and len(breaking_cluster) >= 7 and breaking_cluster[6]:
        bc_title = (breaking_cluster[1] or breaking_cluster[0]) if is_kr else (breaking_cluster[0] or breaking_cluster[1])
        bc_ev = breaking_cluster[5]
        bc_img = breaking_cluster[6]
        bc_cc = breaking_cluster[2] or ""
        bc_url = f'https://www.wewantpeace.live/issues/country/{bc_cc}?utm_source=nl&utm_medium=em&utm_campaign=v1'
        ev_txt = f"{bc_ev:,}건 · " if is_kr else f"{bc_ev:,} events · "

        rows.append(
            f'<tr><td style="background:#fff;padding:0 28px 16px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-radius:8px;overflow:hidden;background:#7f1d1d;">'
            f'<tr><td style="padding:0;">'
            f'<a href="{bc_url}" style="display:block;">'
            f'<img src="{bc_img}" width="544" style="display:block;width:100%;opacity:.8;border:0;" alt=""/>'
            f'</a></td></tr>'
            f'<tr><td style="padding:18px 20px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td><span style="display:inline-block;background:#dc2626;color:#fff;font-size:9px;font-weight:700;'
            f'padding:2px 6px;border-radius:3px;letter-spacing:.5px;">BREAKING</span>'
            f'<span style="display:inline-block;background:rgba(252,165,165,.3);color:#fca5a5;font-size:9px;'
            f'font-weight:600;padding:2px 6px;border-radius:3px;letter-spacing:.5px;margin-left:4px;">'
            f'{"심각도 100" if is_kr else "Severity 100"}</span></td>'
            f'<td style="text-align:right;"><span style="font-size:10px;color:#fca5a5;">{ev_txt}{"유가" if is_kr else "Oil"} {price_str}</span></td>'
            f'</tr></table>'
            f'<p style="font-size:17px;font-weight:800;color:#f1f5f9;line-height:1.4;margin:8px 0 0;">'
            f'<a href="{bc_url}" style="text-decoration:none;color:#f1f5f9;">{(bc_title or "")[:80]}</a></p>'
            f'<p style="font-size:13px;color:#fecaca;line-height:1.6;margin:6px 0 0;">{intro}</p>'
            f'</td></tr></table>'
            f'</td></tr>'
        )

    # 2. 가격 분석 박스
    rows.append(
        f'<tr><td style="background:#fff;padding:0 28px 24px;">'
        f'<p style="font-size:13px;color:#71717a;line-height:1.6;margin:0 0 16px;">{p1}</p>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
        f' style="border-collapse:collapse;border-radius:8px;border:1px solid #e8e8e3;border-left:4px solid #b45309;margin-bottom:16px;">'
        f'<tr><td style="padding:14px 16px;">'
        f'<p style="font-size:15px;font-weight:700;color:#18181b;margin:0 0 6px;">'
        f'{"유가" if is_kr else "Oil"} {price_str} <span style="color:{change_color};">{change_str}</span></p>'
        f'<p style="font-size:13px;color:#52525b;line-height:1.65;margin:0 0 8px;">{p2}</p>'
        f'<p style="font-size:12px;font-weight:600;color:#18181b;margin:0;"><b>{label}:</b> {p3}</p>'
        f'</td></tr></table>'
        f'</td></tr>'
    )

    return '\n'.join(rows)


def build_deep_dive_html(title: str, p1: str, p2: str, p3: str, p4: str, why: str, lang: str,
                         image_url: str = "", country_rows=None) -> str:
    """Vol.1 스타일: 이미지(선택) + 서술 + 국가 상태 테이블(선택) + WHY IT MATTERS 박스."""
    is_kr = lang == "kr"
    parts = []

    # 1. 딥다이브 이미지
    if image_url:
        parts.append(
            f'<tr><td style="background:#fff;padding:0 28px 10px;">'
            f'<img src="{image_url}" width="544" style="display:block;width:100%;border-radius:8px;border:0;" alt=""/>'
            f'</td></tr>'
        )

    # 2. 서술 단락 + 국가 테이블 + WHY 박스
    paragraphs = ''.join(
        f'<p style="font-size:13px;color:#71717a;line-height:1.6;margin:0 0 16px;">{p}</p>'
        for p in [p1, p2, p3, p4] if p
    )

    table_html = ""
    if country_rows:
        ev_h = "이벤트" if is_kr else "Events"
        table_html = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="width:100%;border-collapse:collapse;font-size:12px;margin:16px 0;">'
            f'<tr>'
            f'<td style="padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">COUNTRY</td>'
            f'<td style="padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">STATUS</td>'
            f'<td width="46" style="padding:8px 0;text-align:right;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">{ev_h}</td>'
            f'</tr>'
        )
        for j, (cc, status, ev_count) in enumerate(country_rows[:6]):
            flag = get_flag(cc)
            cname = cn(cc, lang)
            bg = '#fff5f5' if j == 0 else ('#f8f8f7' if j % 2 == 0 else '#fff')
            ev_color = '#dc2626' if (ev_count or 0) >= 50 else '#71717a'
            name_color = '#dc2626' if j == 0 else '#18181b'
            name_weight = '700' if j == 0 else '600'
            table_html += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:8px 0;font-weight:{name_weight};color:{name_color};">'
                f'{flag} {cname}</td>'
                f'<td style="padding:8px 0;color:#52525b;">{status}</td>'
                f'<td style="padding:8px 0;text-align:right;font-weight:700;color:{ev_color};">'
                f'{ev_count:,}{"건" if is_kr else ""}</td>'
                f'</tr>'
            )
        table_html += '</table>'

    why_box = ""
    if why:
        why_box = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-radius:6px;background:#fafafa;border-left:4px solid #18181b;margin-top:14px;">'
            f'<tr><td style="padding:14px 16px;">'
            f'<p style="font-size:9px;font-weight:600;color:#18181b;margin:0 0 4px;letter-spacing:1.5px;">WHY IT MATTERS</p>'
            f'<p style="font-size:13px;line-height:1.65;margin:0;color:#1e3a5f;">{why}</p>'
            f'</td></tr></table>'
        )

    inner = paragraphs + table_html + why_box
    parts.append(f'<tr><td style="background:#fff;padding:0 28px 24px;">{inner}</td></tr>')
    return '\n'.join(parts)


def build_numbers_html(stats: dict, lang: str) -> str:
    """Vol.1 스타일: 2×3 KPI 그리드 + 변동률 뱃지 + 하이라이트 + 주간 비교 테이블."""
    is_kr = lang == "kr"

    def _change_badge(curr, prev):
        if not prev or prev == 0: return ""
        pct = (curr - prev) / prev * 100
        if abs(pct) < 0.5: return ""
        arrow = "↑" if pct > 0 else "↓"
        color = "#dc2626" if pct > 0 else "#22c55e"
        return f'<span style="font-size:9px;color:{color};font-weight:600;"> {arrow}{abs(pct):.0f}%</span>'

    ev24_badge = _change_badge(stats["events_24h"], stats.get("events_24h_prev"))
    ev7d_badge = _change_badge(stats["events_7d_raw"], stats.get("events_7d_prev"))

    cards = [
        (str(stats["events_24h"]), "24h " + ("분쟁" if is_kr else "conflicts"), "#dc2626", ev24_badge),
        (f"{stats['top_cc_events']:,}", f"{stats['top_cc_name']} 7" + ("일" if is_kr else "d"), "#dc2626", ""),
        (str(stats["crisis_count"]), "위기 국가" if is_kr else "Crisis countries", "#dc2626", ""),
        (str(stats["active_issues"]), "진행 중 이슈" if is_kr else "Active issues", "#18181b", ""),
        (f"{stats['events_7d']:,}", "7" + ("일 이벤트" if is_kr else "d events"), "#18181b", ev7d_badge),
        ("100+", "모니터링 소스" if is_kr else "Sources", "#18181b", ""),
    ]
    rows_html = ""
    for i in range(0, 6, 3):
        cells = ""
        for j in range(3):
            idx = i + j
            val, label, color, badge = cards[idx]
            cells += f'<td width="33%" style="padding:4px;"><table style="width:100%;border:1px solid #e5e5e5;border-radius:8px;{"border-top:3px solid "+color+";" if idx < 3 else ""}">'
            cells += f'<tr><td align="center" style="padding:12px 8px;">'
            cells += f'<p style="font-weight:800;color:{color};margin:0;font-size:22px;">{val}{badge}</p>'
            cells += f'<p style="font-size:10px;color:#71717a;margin:4px 0 0;">{label}</p>'
            cells += f'</td></tr></table></td>'
        rows_html += f"<tr>{cells}</tr>"

    # 하이라이트 라인 (top cluster가 평균 대비 N배면)
    highlight_html = ""
    hl = stats.get("highlight")
    if hl:
        highlight_html = f'<p style="font-size:12px;color:#dc2626;font-weight:600;margin:10px 0 0;padding:8px 12px;background:#fef2f2;border-radius:6px;border-left:3px solid #dc2626;">{hl}</p>'

    # 주간 비교 테이블
    wow = stats.get("wow_rows", [])
    wow_html = ""
    if wow:
        wow_html = '<table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:8px;margin:16px 0 0;"><tr><td style="padding:14px 16px;">'
        wow_html += f'<p style="font-weight:600;font-size:9px;color:#94a3b8;letter-spacing:1.5px;margin:0 0 8px;">WEEK-OVER-WEEK</p>'
        wow_html += '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
        wow_html += '<tr><td style="color:#94a3b8;padding:3px 0;font-size:9px;"></td>'
        wow_html += f'<td style="text-align:right;color:#94a3b8;padding:3px 0;font-size:9px;">{"전주" if is_kr else "Prev"}</td>'
        wow_html += f'<td style="text-align:right;color:#94a3b8;padding:3px 0;font-size:9px;">{"이번 주" if is_kr else "This wk"}</td>'
        wow_html += f'<td style="text-align:right;color:#94a3b8;padding:3px 0;font-size:9px;">{"변화" if is_kr else "Change"}</td></tr>'
        for label, prev, curr, change_str in wow:
            wow_html += f'<tr><td style="color:#e2e8f0;padding:5px 0;">{label}</td>'
            wow_html += f'<td style="text-align:right;color:#64748b;padding:5px 0;">{prev}</td>'
            wow_html += f'<td style="text-align:right;color:#ef4444;font-weight:700;padding:5px 0;">{curr}</td>'
            wow_html += f'<td style="text-align:right;color:#ef4444;font-weight:600;font-size:10px;padding:5px 0;">{change_str}</td></tr>'
        wow_html += '</table></td></tr></table>'

    return f'<table style="width:100%;border-collapse:collapse;">{rows_html}</table>{highlight_html}{wow_html}'


def build_country_impact_html(steps: list, lang: str) -> str:
    """Vol.1 스타일: 번호 + 영향 체인 + 연결 화살표."""
    is_kr = lang == "kr"
    connector_labels = (
        ["→ 시장 반응", "→ 내 지갑에", "→ 최종 영향"]
        if is_kr else
        ["→ market reaction", "→ your wallet", "→ final impact"]
    )
    html = '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
    items = steps[:4]
    for i, step in enumerate(items):
        is_last = i == len(items) - 1
        num_color = "#dc2626" if i == 0 else ("#dc2626" if is_last else "#71717a")
        text_style = 'font-weight:700;color:#dc2626;' if is_last else 'color:#27272a;'
        html += (
            f'<tr>'
            f'<td width="24" valign="top" style="text-align:center;padding:6px 0;font-weight:800;font-size:13px;color:{num_color};">{i+1}</td>'
            f'<td style="padding:6px 0 6px 4px;{text_style}line-height:1.5;">{step}</td>'
            f'</tr>'
        )
        if not is_last:
            label = connector_labels[i] if i < len(connector_labels) else "→"
            html += (
                f'<tr>'
                f'<td width="24" style="text-align:center;padding:1px 0;color:#d4d4d8;font-size:13px;line-height:1;">↓</td>'
                f'<td style="padding:2px 0 2px 4px;font-size:10px;font-weight:600;color:#a1a1aa;letter-spacing:.3px;">{label}</td>'
                f'</tr>'
            )
    html += '</table>'
    return html


def build_country_issues_html(issues: list, lang: str) -> str:
    """Vol.1 스타일: 3열 이슈 테이블. DB값 HTML escape 적용."""
    import html as _html_lib
    is_kr = lang == "kr"
    if not issues:
        return ""
    html = '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
    html += f'<tr><td style="padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">{"이슈" if is_kr else "Issue"}</td>'
    html += f'<td style="padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">{"상세" if is_kr else "Detail"}</td>'
    html += f'<td width="40" style="text-align:right;padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">{"이벤트" if is_kr else "Events"}</td></tr>'
    for name, detail, count in issues:
        c = "#dc2626" if count and int(str(count).replace(",", "")) >= 10 else "#71717a"
        safe_name = _html_lib.escape(str(name or ""))
        safe_detail = _html_lib.escape(str(detail or ""))
        html += f'<tr><td style="padding:8px 0;font-weight:700;color:#18181b;border-bottom:1px solid #f4f4f5;">{safe_name}</td>'
        html += f'<td style="padding:8px 0;color:#52525b;border-bottom:1px solid #f4f4f5;">{safe_detail}</td>'
        html += f'<td style="text-align:right;padding:8px 0;font-weight:700;color:{c};border-bottom:1px solid #f4f4f5;">{count}{"건" if is_kr else ""}</td></tr>'
    html += '</table>'
    return html


def build_calendar_html(days: list, lang: str, tag_color: str = "#dc2626") -> str:
    """Vol.1 스타일: 날짜열 + 이벤트열 + 태그 색상 회전."""
    from datetime import date as _date
    is_kr = lang == "kr"
    today_date = _date.today()
    html = '<table style="width:100%;border-collapse:collapse;font-size:12px;border:1px solid #e5e5e5;border-radius:8px;">'
    for i, (dt, event, tags) in enumerate(days[:4]):
        wd_str = WEEKDAY_KO[dt.weekday()] if is_kr else WEEKDAY_EN[dt.weekday()]
        date_str = f"{dt.month}/{dt.day}"
        bg = "#fafafa" if i % 2 == 1 else "#fff"
        ev_date = dt.date() if hasattr(dt, 'date') else dt
        # 날짜 기반 뱃지: 오늘=D-DAY, 미래=예정, 과거=없음
        if is_kr:
            if ev_date == today_date:
                badge_style = "background:#dc2626;color:white;padding:1px 6px;border-radius:3px;font-size:7px;font-weight:700;"
                badge_text = "D-DAY"
            elif ev_date > today_date:
                badge_style = "background:#3b82f6;color:white;padding:1px 6px;border-radius:3px;font-size:7px;font-weight:700;"
                badge_text = "예정"
            else:
                badge_style, badge_text = "", ""
        else:
            badge_style, badge_text = "", ""
        html += f'<tr><td width="60" valign="middle" style="background:{bg};padding:10px 8px;text-align:center;border-bottom:1px solid #f0f0f0;">'
        html += f'<p style="font-weight:700;font-size:14px;margin:0;">{date_str}</p>'
        html += f'<p style="font-size:9px;color:#71717a;margin:2px 0 0;">{wd_str}</p>'
        if badge_text:
            html += f'<p style="margin:2px 0 0;"><span style="{badge_style}">{badge_text}</span></p>'
        html += f'</td><td style="background:{bg};padding:10px 12px;border-bottom:1px solid #f0f0f0;">'
        html += f'<p style="font-weight:600;font-size:13px;color:#18181b;margin:0 0 4px;">{event}</p>'
        if tags:
            html += '<p style="margin:0;">' + " ".join(f'<span style="font-size:9px;color:{tag_color};">#{t}</span>' for t in tags) + '</p>'
        html += '</td></tr>'
    html += '</table>'
    return html


def _build_hero_headline_html(raw: str) -> str:
    """히어로 헤드라인을 계층형 스타일 HTML로 변환.
    첫 줄: 26px bold (핵심 주장)
    중간 줄: 18px medium (부가 정보)
    마지막 줄: 13px (KPI/수치 등)
    """
    lines = [l.strip() for l in (raw or "").strip().split("\n") if l.strip()]
    if not lines:
        return raw or ""
    if len(lines) == 1:
        return f'<span style="font-size:26px;font-weight:900;display:block;line-height:1.25;">{lines[0]}</span>'
    parts = []
    for i, line in enumerate(lines):
        if i == 0:
            # 핵심 — 크고 굵게
            parts.append(
                f'<span style="font-size:26px;font-weight:900;display:block;'
                f'line-height:1.25;margin-bottom:10px;">{line}</span>'
            )
        elif i == len(lines) - 1:
            # 마지막 — 작게 (KPI, 긴장도 등)
            parts.append(
                f'<span style="font-size:13px;font-weight:600;display:block;'
                f'color:rgba(255,255,255,.7);margin-top:6px;letter-spacing:.2px;">{line}</span>'
            )
        else:
            # 중간 — 보통 크기
            parts.append(
                f'<span style="font-size:18px;font-weight:600;display:block;'
                f'line-height:1.4;margin-bottom:5px;color:rgba(255,255,255,.92);">{line}</span>'
            )
    return "\n".join(parts)


def _editors_note_style_p1(text: str) -> str:
    """p1: — 또는 첫 문장 이후 핵심 주장을 <b> bold 처리."""
    for sep in [' — ', '. ', '。']:
        idx = text.find(sep)
        if idx > 8 and idx < len(text) - 10:
            after = text[idx + len(sep):]
            if len(after) > 10:
                return f"{text[:idx + len(sep)]}<b>{after}</b>"
    return text


def _editors_note_style_p2(text: str) -> str:
    """p2: — 구분자 이후 또는 후반 구절에 배경 하이라이트 적용."""
    if not text:
        return text
    # 1순위: — 구분자
    for sep in [' — ', '— ']:
        idx = text.rfind(sep)
        if idx > len(text) // 3:
            after = text[idx + len(sep):]
            if 8 <= len(after) <= 100:
                return (
                    f'{text[:idx + len(sep)]}'
                    f'<span style="background:#f5f0e4;padding:0 3px;border-radius:2px;">{after}</span>'
                )
    # 2순위: 마지막 문장 (. 기준)
    for sep in ['. ', '。']:
        idx = text.rfind(sep, len(text) // 2)
        if idx != -1:
            after = text[idx + len(sep):]
            if 8 <= len(after) <= 100:
                return (
                    f'{text[:idx + len(sep)]}'
                    f'<span style="background:#f5f0e4;padding:0 3px;border-radius:2px;">{after}</span>'
                )
    # 3순위: 마지막 콤마 구절 (텍스트 후반 2/3에서)
    comma_idx = text.rfind(', ', len(text) * 2 // 3)
    if comma_idx != -1:
        after = text[comma_idx + 2:]
        if 10 <= len(after) <= 80:
            return (
                f'{text[:comma_idx + 2]}'
                f'<span style="background:#f5f0e4;padding:0 3px;border-radius:2px;">{after}</span>'
            )
    return text


def build_editors_note_html(p1: str, p2: str, p3: str, ps: str = "", lang: str = "kr") -> str:
    """Vol.1 스타일: 에디터 노트 + P.S.
    - p1: 첫 문장 후 핵심 주장 <b> bold
    - p2: — 이후 key phrase 배경 하이라이트
    - p3: 마무리 (이탤릭 소자)
    """
    header = "에디터 한마디" if lang == "kr" else "Editor's Note"
    p1_html = _editors_note_style_p1(p1) if p1 else ""
    p2_html = _editors_note_style_p2(p2) if p2 else ""
    # GPT가 "P.S." 또는 "*" 마크다운을 포함할 경우 제거
    ps_clean = re.sub(r'^[Pp][.\s]*[Ss][.\s]*\s*', '', ps).strip().lstrip('*_').rstrip('*_') if ps else ""
    ps_html = (
        f'\n<p class="nk fc h6 m0" style="color:#7d7262;margin-top:16px;font-style:italic;">P.S. {ps_clean}</p>'
        if ps_clean else ""
    )
    return (
        f'<p class="nk w9 m0" style="font-size:20px;letter-spacing:-.3px;color:#2d2418;'
        f'margin-top:14px;margin-bottom:20px;">{header}</p>'
        f'<p class="nk fe h8 m0" style="font-size:14px;line-height:1.8;color:#3d3428;margin:0 0 14px;">{p1_html}</p>'
        f'<p class="nk fe h8 m0" style="font-size:14px;line-height:1.8;color:#3d3428;margin:0 0 14px;">{p2_html}</p>'
        f'<p class="nk fd h6 m0" style="font-size:13px;line-height:1.6;color:#7d7262;margin:0;">{p3}</p>'
        f'{ps_html}'
    )


def build_next_week_html(items: list) -> str:
    colors = ["#ef4444", "#f59e0b", "#f59e0b"]
    filtered = [item for item in items[:3] if item and item.strip()]
    if not filtered:
        return ""
    html = '<table style="width:100%;border-collapse:collapse;margin-top:10px;">'
    for i, item in enumerate(filtered):
        c = colors[i] if i < len(colors) else "#94a3b8"
        html += f'<tr><td style="padding:4px 0;"><span style="display:inline-block;width:6px;height:6px;background:{c};border-radius:50%;vertical-align:middle;margin-right:8px;"></span>'
        html += f'<span style="font-size:13px;color:#52525b;">{item}</span></td></tr>'
    html += '</table>'
    return html


def build_travel_html(advisories: list, lang: str) -> str:
    """각 섹션을 <tr><td> 로 래핑 — 이메일 테이블 컨텍스트에서 올바른 DOM 위치 유지."""
    is_kr = lang == "kr"
    l4 = [a for a in advisories if a["level"] >= 4]
    l3 = [a for a in advisories if a["level"] == 3]
    new_badge = '<span style="background:#dc2626;color:white;font-size:8px;font-weight:700;padding:1px 4px;border-radius:3px;margin-left:2px;vertical-align:middle;">NEW</span>'
    rows = []

    def _name_with_badge(a):
        flag = get_flag(a["cc"])
        name = cn(a["cc"], lang)
        if a.get("new"):
            return f'{flag} <b>{name}</b>{new_badge}'
        return f'{flag} {name}'

    if l4:
        names = ", ".join(_name_with_badge(a) for a in l4[:25])
        new_l4 = [a for a in l4 if a.get("new")]
        new_line = ""
        if new_l4:
            new_names = ", ".join(cn(a["cc"], lang) for a in new_l4[:5])
            new_line = f'<p style="font-size:10px;color:#dc2626;margin:6px 0 0;font-weight:600;">(+{len(new_l4)}: {new_names})</p>'
        inner = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-radius:8px;background:#fef2f2;border:1px solid #fecaca;"><tr><td style="padding:14px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td><span style="display:inline-block;font-weight:700;font-size:9px;border-radius:3px;letter-spacing:.5px;padding:2px 6px;background:#dc2626;color:white;">LEVEL 4</span></td>
<td align="right"><span style="font-weight:800;color:#dc2626;font-size:22px;">{len(l4)}</span><span style="font-size:12px;color:#dc2626;">{"개국" if is_kr else ""}</span></td></tr></table>
<p style="font-weight:700;font-size:12px;color:#dc2626;margin:6px 0;">{"여행 금지" if is_kr else "Do Not Travel"}</p>
<p style="font-size:11px;line-height:1.6;color:#7f1d1d;margin:0;">{names}</p>{new_line}
</td></tr></table>'''
        rows.append(f'<tr><td style="background:#fff;padding:0 28px 12px;">{inner}</td></tr>')
    if l3:
        names = ", ".join(_name_with_badge(a) for a in l3[:30])
        new_l3 = [a for a in l3 if a.get("new")]
        new_line = ""
        if new_l3:
            new_names = ", ".join(cn(a["cc"], lang) for a in new_l3[:5])
            new_line = f'<p style="font-size:10px;color:#b45309;margin:6px 0 0;font-weight:600;">(+{len(new_l3)}: {new_names})</p>'
        inner = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-radius:8px;background:#fffbeb;border:1px solid #fde68a;"><tr><td style="padding:14px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td><span style="display:inline-block;font-weight:700;font-size:9px;border-radius:3px;letter-spacing:.5px;padding:2px 6px;background:#b45309;color:white;">LEVEL 3</span></td>
<td align="right"><span style="font-weight:800;color:#b45309;font-size:22px;">{len(l3)}</span><span style="font-size:12px;color:#b45309;">{"개국" if is_kr else ""}</span></td></tr></table>
<p style="font-weight:700;font-size:12px;color:#92400e;margin:6px 0;">{"여행 재고" if is_kr else "Reconsider Travel"}</p>
<p style="font-size:11px;line-height:1.6;color:#78350f;margin:0;">{names}</p>{new_line}
</td></tr></table>'''
        rows.append(f'<tr><td style="background:#fff;padding:0 28px 12px;">{inner}</td></tr>')
    return "\n".join(rows)


# ── 메인 생성 ─────────────────────────────────────────────────────────────────

async def generate(vol: int, lang: str) -> dict:
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    twenty_four_hours_ago = now - timedelta(hours=24)
    target_cc = "KR" if lang == "kr" else "US"
    is_kr = lang == "kr"

    data = {}

    async with AsyncSessionLocal() as db:
        # ── 메타 ──
        data["vol_number"] = vol
        data["next_vol_number"] = vol + 1
        data["current_year"] = now.year
        wd = now.weekday()
        if is_kr:
            data["issue_date"] = f"{now.year}.{now.month:02d}.{now.day:02d}"
            data["issue_date_short"] = f"{now.month}.{now.day} {WEEKDAY_KO[wd]}요일"
            data["issue_datetime"] = f"{now.year}.{now.month}.{now.day} {WEEKDAY_KO[wd]} 09:00"
        else:
            data["issue_date"] = now.strftime("%B %d, %Y")
            data["issue_date_short"] = now.strftime("%b %d, %a")
            data["issue_datetime"] = now.strftime("%Y.%m.%d %a 09:00")
        data["issue_label"] = f"Vol.{vol}"
        data["issue_label_long"] = f"Vol.{vol}"

        # ── 클러스터 통계 ──
        r = await db.execute(text("SELECT COUNT(*) FROM issue_clusters WHERE is_active = true AND severity >= 2"))
        total_conflicts = r.scalar() or 0
        data["total_conflicts"] = total_conflicts

        r = await db.execute(text("SELECT COUNT(*) FROM issue_clusters WHERE is_active = true AND severity >= 4"))
        data["urgent_count"] = r.scalar() or 0

        r = await db.execute(text("SELECT COUNT(*) FROM issue_clusters WHERE is_active = true"))
        active_issues = r.scalar() or 0
        data["active_issues_count"] = active_issues

        r = await db.execute(text(
            "SELECT COUNT(DISTINCT country_code) FROM issue_clusters "
            "WHERE is_active = true AND severity >= 4 AND country_code IS NOT NULL"))
        crisis_count = r.scalar() or 0
        data["crisis_countries_count"] = crisis_count
        data["crisis_current"] = crisis_count

        r = await db.execute(text(
            "SELECT COUNT(DISTINCT country_code) FROM issue_clusters "
            "WHERE is_active = true AND severity >= 4 AND country_code IS NOT NULL AND created_at < :cutoff"
        ), {"cutoff": seven_days_ago})
        crisis_prev = r.scalar() or crisis_count
        data["crisis_prev"] = crisis_prev

        diff = crisis_count - crisis_prev
        if diff > 0: data["crisis_trend"] = f"{diff}개국 증가" if is_kr else f"↑{diff}"
        elif diff < 0: data["crisis_trend"] = f"{abs(diff)}개국 감소" if is_kr else f"↓{abs(diff)}"
        else: data["crisis_trend"] = "변동 없음" if is_kr else "—"

        # ── 이벤트 수 ──
        r = await db.execute(text("SELECT COUNT(*) FROM normalized_events WHERE event_time >= :c"), {"c": twenty_four_hours_ago})
        events_24h = r.scalar() or 0
        data["events_24h"] = events_24h

        r = await db.execute(text("SELECT COUNT(*) FROM normalized_events WHERE event_time >= :c"), {"c": seven_days_ago})
        events_7d = r.scalar() or 0
        data["events_7d"] = f"{events_7d:,}"

        # ── 상위 클러스터 (복합 가중: event_count 중심) ──
        r = await db.execute(text("""
            SELECT id, title, title_ko, country_code, severity, kscore, event_count, image_url
            FROM issue_clusters WHERE is_active = true AND severity >= 2
            ORDER BY (event_count * 2 + kscore) DESC
            LIMIT 10
        """))
        top_clusters = [
            (row.title, row.title_ko, row.country_code, row.severity, row.kscore, row.event_count, row.image_url, str(row.id))
            for row in r.fetchall()
        ]
        data["conflict_stories_html"] = build_conflict_stories_html(top_clusters, lang, vol=vol, target_cc=target_cc)

        # ── 상위 3개 클러스터 body_ko 로딩 (GPT context 주입용) ──
        cluster_event_bodies = {}
        if top_clusters:
            top3_ids = [c[7] for c in top_clusters[:3]]
            for cluster_id in top3_ids:
                r2 = await db.execute(text("""
                    SELECT ne.body_ko, ne.title_ko, ne.severity
                    FROM cluster_events ce
                    JOIN normalized_events ne ON ne.id = ce.event_id
                    WHERE ce.cluster_id = :cid
                      AND ne.body_ko IS NOT NULL AND ne.body_ko != ''
                    ORDER BY ne.severity DESC, ne.event_time DESC
                    LIMIT 5
                """), {"cid": cluster_id})
                bodies = []
                for brow in r2.fetchall():
                    snippet = (brow.body_ko or "")[:300].strip()
                    if snippet:
                        bodies.append(f"· {snippet}")
                cluster_event_bodies[cluster_id] = bodies

        # ── 긴장도 ──
        r = await db.execute(text("SELECT DISTINCT ON (country_code) country_code, raw_score FROM tension_index WHERE country_code IS NOT NULL ORDER BY country_code, time DESC"))
        tension_current = {row.country_code: row.raw_score for row in r.fetchall()}

        r = await db.execute(text("SELECT DISTINCT ON (country_code) country_code, raw_score FROM tension_index WHERE country_code IS NOT NULL AND time < :c ORDER BY country_code, time DESC"), {"c": seven_days_ago})
        tension_prev = {row.country_code: row.raw_score for row in r.fetchall()}

        sorted_tension = sorted(tension_current.items(), key=lambda x: x[1], reverse=True)[:10]
        tension_rows = [(cc, score, score - tension_prev.get(cc, score)) for cc, score in sorted_tension]
        data["tension_table_html"] = build_tension_table_html(tension_rows, lang, target_cc)

        target_score = tension_current.get(target_cc, 0)
        target_prev = tension_prev.get(target_cc, target_score)
        target_delta = target_score - target_prev
        data["country_name"] = cn(target_cc, lang)
        data["country_code"] = target_cc
        data["tension_score"] = f"{target_score:.1f}"
        data["tension_level"] = tension_num(target_score)
        data["tension_level_text"] = tension_label(target_score, lang)
        data["tension_change"] = f"▲{abs(target_delta):.1f}" if target_delta > 0 else f"▼{abs(target_delta):.1f}" if target_delta < 0 else "—"
        data["prev_tension"] = f"{target_prev:.1f}"
        all_sorted = sorted(tension_current.items(), key=lambda x: x[1], reverse=True)
        data["country_rank"] = next((i+1 for i, (cc, _) in enumerate(all_sorted) if cc == target_cc), 0)

        # ── 원자재 ──
        oil_price, oil_change, wheat_price, wheat_change = None, None, None, None
        for sym, name in [("WTI", "oil"), ("BRENT", "oil_brent"), ("WHEAT", "wheat")]:
            r = await db.execute(text("SELECT price_usd, change_pct FROM commodity_price WHERE symbol = :s ORDER BY price_date DESC LIMIT 1"), {"s": sym})
            row = r.fetchone()
            if row:
                if name == "oil" and not oil_price: oil_price, oil_change = float(row.price_usd), float(row.change_pct or 0)
                elif name == "oil_brent" and not oil_price: oil_price, oil_change = float(row.price_usd), float(row.change_pct or 0)
                elif name == "wheat": wheat_price, wheat_change = float(row.price_usd), float(row.change_pct or 0)

        # ── 원자재 기간별 가격 (7d/30d/90d) ──
        energy_period_idx = vol % 3  # 0=7d, 1=30d, 2=90d
        energy_days = [7, 30, 90][energy_period_idx]
        energy_label = ["7일", "30일", "분기"][energy_period_idx] if is_kr else ["7d", "30d", "Quarter"][energy_period_idx]
        cutoff_date = now - timedelta(days=energy_days)
        oil_price_past, wheat_price_past = None, None
        for sym, target in [("WTI", "oil"), ("BRENT", "oil_brent"), ("WHEAT", "wheat")]:
            r = await db.execute(text(
                "SELECT price_usd FROM commodity_price WHERE symbol = :s AND price_date <= :cutoff ORDER BY price_date DESC LIMIT 1"
            ), {"s": sym, "cutoff": cutoff_date.strftime("%Y-%m-%d")})
            row = r.fetchone()
            if row:
                if target in ("oil", "oil_brent") and oil_price_past is None:
                    oil_price_past = float(row.price_usd)
                elif target == "wheat":
                    wheat_price_past = float(row.price_usd)

        oil_change_period = ((oil_price - oil_price_past) / oil_price_past * 100) if oil_price and oil_price_past else None
        wheat_change_period = ((wheat_price - wheat_price_past) / wheat_price_past * 100) if wheat_price and wheat_price_past else None

        # ── 여행경보 ──
        thirty_days_ago = now - timedelta(days=30)
        r = await db.execute(text("SELECT DISTINCT ON (country_code) country_code, level, updated_at FROM travel_advisory WHERE level >= 3 ORDER BY country_code, updated_at DESC"))
        advisories = [{"cc": row.country_code, "level": row.level, "new": row.updated_at >= thirty_days_ago if row.updated_at else False} for row in r.fetchall()]
        travel_l4 = len([a for a in advisories if a["level"] >= 4])
        travel_l3 = len([a for a in advisories if a["level"] == 3])
        data["travel_advisory_html"] = build_travel_html(advisories, lang)
        data["travel_advisory_intro_html"] = (
            f"여행 금지 {travel_l4}개국, 여행 재고 {travel_l3}개국." if is_kr
            else f"Do Not Travel: {travel_l4} countries. Reconsider: {travel_l3}."
        )

        # ── country_issues (DB 기반, description 컬럼 존재 여부 사전 체크) ──
        # try/except 대신 information_schema로 체크 — asyncpg 트랜잭션 오염 방지
        try:
            r_col = await db.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='issue_clusters' AND column_name='description' LIMIT 1"
            ))
            _country_issues_has_detail = r_col.scalar() is not None
        except Exception:
            _country_issues_has_detail = False

        if _country_issues_has_detail:
            r = await db.execute(text("""
                SELECT title, title_ko, event_count, description
                FROM issue_clusters
                WHERE is_active = true AND country_code = :cc
                ORDER BY event_count DESC LIMIT 5
            """), {"cc": target_cc})
            country_issues_rows = [(row.title, row.title_ko, row.event_count, row.description) for row in r.fetchall()]
        else:
            r = await db.execute(text("""
                SELECT title, title_ko, event_count FROM issue_clusters
                WHERE is_active = true AND country_code = :cc
                ORDER BY event_count DESC LIMIT 5
            """), {"cc": target_cc})
            country_issues_rows = [(row.title, row.title_ko, row.event_count, None) for row in r.fetchall()]

        # ── streak_text — 긴장도 연속 상승/하락 주 수 계산 ──
        # 양수: 연속 상승, 음수: 연속 하락
        streak_weeks = 0
        try:
            prev_s = float(target_score)
            direction = None  # "rising" | "falling"
            for w in range(1, 9):
                r_st = await db.execute(text(
                    "SELECT raw_score FROM tension_index WHERE country_code=:cc AND time < :t "
                    "ORDER BY time DESC LIMIT 1"
                ), {"cc": target_cc, "t": now - timedelta(weeks=w)})
                row_st = r_st.fetchone()
                if not row_st:
                    break
                past_s = float(row_st.raw_score)
                if direction is None:
                    if prev_s > past_s + 0.5:
                        direction = "rising"
                    elif prev_s < past_s - 0.5:
                        direction = "falling"
                    else:
                        break  # 변화 없음
                if direction == "rising" and past_s < prev_s - 0.5:
                    streak_weeks += 1
                    prev_s = past_s
                elif direction == "falling" and past_s > prev_s + 0.5:
                    streak_weeks -= 1
                    prev_s = past_s
                else:
                    break
        except Exception:
            streak_weeks = 0

        # ── 전주 이벤트 수 (numbers 변동률용) ──
        prev_week_start = seven_days_ago - timedelta(days=7)
        prev_24h_start = twenty_four_hours_ago - timedelta(days=7)
        prev_24h_end = twenty_four_hours_ago - timedelta(days=6)
        r = await db.execute(text("SELECT COUNT(*) FROM normalized_events WHERE event_time >= :s AND event_time < :e"), {"s": prev_24h_start, "e": prev_24h_end})
        events_24h_prev = r.scalar() or 0
        r = await db.execute(text("SELECT COUNT(*) FROM normalized_events WHERE event_time >= :s AND event_time < :e"), {"s": prev_week_start, "e": seven_days_ago})
        events_7d_prev = r.scalar() or 0

        # ── 평균 event_count (하이라이트 라인용) — 상위 20개 평균으로 비교해야 의미 있음 ──
        r = await db.execute(text(
            "SELECT AVG(ec) FROM (SELECT event_count AS ec FROM issue_clusters "
            "WHERE is_active = true AND event_count > 0 ORDER BY event_count DESC LIMIT 20) sub"
        ))
        avg_event_count = float(r.scalar() or 1)

        # ── 시장 지수 & 환율 (numbers WoW용) ──
        kospi_val, kospi_prev_val = None, None
        nasdaq_val, nasdaq_prev_val = None, None
        usd_krw, usd_krw_prev = None, None
        if is_kr:
            r = await db.execute(text(
                "SELECT value FROM market_index WHERE symbol='KOSPI' "
                "ORDER BY index_date DESC LIMIT 2"
            ))
            rows_ki = r.fetchall()
            if len(rows_ki) >= 1: kospi_val = float(rows_ki[0].value)
            if len(rows_ki) >= 2: kospi_prev_val = float(rows_ki[1].value)
            r = await db.execute(text(
                "SELECT rate FROM exchange_rate WHERE base_currency='USD' AND target_currency='KRW' "
                "ORDER BY rate_date DESC LIMIT 2"
            ))
            rows_fx = r.fetchall()
            if len(rows_fx) >= 1: usd_krw = float(rows_fx[0].rate)
            if len(rows_fx) >= 2: usd_krw_prev = float(rows_fx[1].rate)
        else:
            r = await db.execute(text(
                "SELECT value FROM market_index WHERE symbol='NASDAQ' "
                "ORDER BY index_date DESC LIMIT 2"
            ))
            rows_nq = r.fetchall()
            if len(rows_nq) >= 1: nasdaq_val = float(rows_nq[0].value)
            if len(rows_nq) >= 2: nasdaq_prev_val = float(rows_nq[1].value)

    # ── GPT 편집 콘텐츠 ──
    def cl_title(c, i=0):
        if not c or i >= len(c): return "N/A"
        t, tko = c[i][0], c[i][1]
        return (tko or t) if is_kr else (t or tko)

    def cl_cc(c, i=0): return cn(c[i][2], lang) if c and i < len(c) else "N/A"
    def cl_ev(c, i=0): return c[i][5] if c and i < len(c) else 0
    def cl_img(c, i=0): return c[i][6] if c and i < len(c) and c[i][6] else ""

    tension_top3 = ", ".join(f"{cn(cc, lang)} {s:.0f}" for cc, s in sorted_tension[:3])

    def _bodies_to_ctx(cluster_idx: int) -> str:
        """클러스터 idx의 body_ko 요약 3건을 문자열로 반환."""
        if cluster_idx >= len(top_clusters): return ""
        cid = top_clusters[cluster_idx][7]
        bodies = cluster_event_bodies.get(cid, [])
        return "\n".join(bodies[:3]) if bodies else ""

    gpt_ctx = {
        "top_story": cl_title(top_clusters, 0), "top_cc": cl_cc(top_clusters, 0),
        "top_events": cl_ev(top_clusters, 0), "top_sev": top_clusters[0][3] if top_clusters else 0,
        "story_2": cl_title(top_clusters, 1), "story_2_cc": cl_cc(top_clusters, 1), "story_2_events": cl_ev(top_clusters, 1),
        "story_3": cl_title(top_clusters, 2), "story_3_cc": cl_cc(top_clusters, 2), "story_3_events": cl_ev(top_clusters, 2),
        "tension_top3": tension_top3,
        "target_name": cn(target_cc, lang), "target_cc": target_cc, "target_tension": f"{target_score:.1f}",
        "target_rank": data["country_rank"], "target_delta": data["tension_change"],
        "oil_price": f"{oil_price:.1f}" if oil_price else "N/A",
        "oil_change": f"{oil_change:+.1f}" if oil_change is not None else "N/A",
        "wheat_price": f"{wheat_price:.1f}" if wheat_price else "N/A",
        "wheat_change": f"{wheat_change:+.1f}" if wheat_change is not None else "N/A",
        "crisis_count": crisis_count, "crisis_prev": crisis_prev,
        "events_24h": events_24h, "events_7d": f"{events_7d:,}" if isinstance(events_7d, int) else events_7d,
        "travel_l4": travel_l4, "travel_l3": travel_l3,
        "oil_price_past": f"{oil_price_past:.1f}" if oil_price_past else "N/A",
        "oil_change_period": f"{oil_change_period:+.1f}" if oil_change_period is not None else "N/A",
        "energy_period": energy_label, "energy_days": energy_days,
        # 실제 뉴스 본문 (body_ko) — GPT context 품질 개선
        "top_story_events": _bodies_to_ctx(0),
        "story_2_events_body": _bodies_to_ctx(1),
        "story_3_events_body": _bodies_to_ctx(2),
        # ── 날짜 정보 — 할루시네이션 방지 필수 ──
        "issue_date": data.get("issue_date", now.strftime("%Y.%m.%d")),
        "week_start": seven_days_ago.strftime("%Y-%m-%d"),
        "week_end": now.strftime("%Y-%m-%d"),
    }

    # ── DB 기반 폴백 콘텐츠 사전 생성 (GPT 실패 보험) ──
    fallback = _build_fallback_editorial(gpt_ctx, top_clusters, lang, vol=vol,
                                          cluster_event_bodies=cluster_event_bodies)

    print("  GPT 편집 콘텐츠 생성 중...")
    ed = await generate_editorial(gpt_ctx, lang, vol=vol)
    if not ed:
        print("  ⚠ GPT 완전 실패 → DB 기반 폴백 사용")
        ed = fallback
        ed["_fallback"] = True
        data["_fallback_used"] = True
    else:
        # 할루시네이션 자동 제거 (CRITICAL 패턴은 필드 초기화)
        ed = _sanitize_hallucinations(ed)
        # GPT 부분 실패 시 fallback으로 빈 필드 보충
        _missing_keys = [k for k, v in fallback.items() if not k.startswith("_") and not ed.get(k)]
        if _missing_keys:
            for k in _missing_keys:
                ed[k] = fallback[k]
            print(f"  ⚠ GPT 부분 실패: {len(_missing_keys)}개 필드 fallback 보충 → {_missing_keys[:5]}")
            data["_fallback_partial"] = True
        # 품질 검증 (경고만 출력, 실패 아님)
        warnings = _validate_editorial(ed)
        if warnings:
            hallucination_warns = [w for w in warnings if "HALLUCINATION" in w]
            other_warns = [w for w in warnings if "HALLUCINATION" not in w]
            if hallucination_warns:
                print(f"  🚨 할루시네이션 감지 ({len(hallucination_warns)}건) — 해당 필드 초기화됨:")
                for w in hallucination_warns:
                    print(f"    {w}")
            if other_warns:
                print(f"  ⚠ 품질 경고 ({len(other_warns)}건):")
                for w in other_warns:
                    print(f"    - {w}")
        else:
            print("  ✓ 품질 검증 통과")

    # ── HTML 조립 ──
    top_cc_name = cl_cc(top_clusters, 0) if top_clusters else "N/A"
    top_cc_ev = cl_ev(top_clusters, 0) if top_clusters else 0
    oil_str = f"${oil_price:.0f}" if oil_price else "N/A"
    oil_ch = (
        f"↑{oil_change:.1f}%" if (oil_change is not None and oil_change > 0.05)
        else f"↓{abs(oil_change):.1f}%" if (oil_change is not None and oil_change < -0.05)
        else ("→0%" if oil_change is not None else "")
    )

    hero_raw = (ed.get("hero_headline", "") or fallback.get("hero_headline", cl_title(top_clusters, 0)))
    # 유가 방향 강제 보정: GPT가 잘못된 방향(↑/↓) 생성하는 경우 데이터 기반으로 교체
    if hero_raw and oil_price and oil_change is not None:
        import re as _re_hero
        _oil_dir = "↑" if oil_change > 0.05 else "↓" if oil_change < -0.05 else "→"
        _wrong_dir = "↓" if _oil_dir == "↑" else "↑"
        _hero_lines = hero_raw.strip().split("\n")
        if len(_hero_lines) >= 2:
            _l2 = _hero_lines[1]
            # 유가 언급 라인에서 방향 기호가 틀리면 교체
            if "유가" in _l2 or "주유비" in _l2 or "oil" in _l2.lower():
                if _wrong_dir in _l2:
                    _hero_lines[1] = _l2.replace(f"주유비{_wrong_dir}", f"주유비{_oil_dir}") \
                                        .replace(f"배달비{_wrong_dir}", f"배달비{_oil_dir}") \
                                        .replace(f"난방비{_wrong_dir}", f"난방비{_oil_dir}") \
                                        .replace(f"장바구니{_wrong_dir}", f"장바구니{_oil_dir}")
                    hero_raw = "\n".join(_hero_lines)
                    print(f"    ↺ 히어로 유가 방향 보정: {_wrong_dir}→{_oil_dir}")
    data["hero_headline_html"] = _build_hero_headline_html(hero_raw)
    data["preheader_text"] = ed.get("preheader", "").strip() or fallback.get("preheader", "")

    # key_stats_line — 데이터 직접 빌드
    data["key_stats_line"] = (
        f'핵심: <span class="w6 ce">{top_cc_name} {top_cc_ev:,}건</span> · '
        f'<span class="w6 cy">유가 {oil_str}</span>({oil_ch}) · '
        f'<span class="w6 cx">{cn(target_cc, lang)} {target_score:.1f}</span>'
    ) if is_kr else (
        f'Key: <span class="w6 ce">{top_cc_name} {top_cc_ev:,} events</span> · '
        f'<span class="w6 cy">Oil {oil_str}</span>({oil_ch}) · '
        f'<span class="w6 cx">{cn(target_cc, lang)} {target_score:.1f}</span>'
    )

    # Today's brief — 빈 title 허용하지 않음
    brief_fallbacks_titles = [
        fallback.get("brief_1_title", cl_title(top_clusters, 0)),
        fallback.get("brief_2_title", cl_title(top_clusters, 1)),
        fallback.get("brief_3_title", cn(target_cc, lang) + (f" 긴장도 {target_score:.1f}" if is_kr else f" Tension {target_score:.1f}")),
    ]
    briefs = []
    for i in range(3):
        title = ed.get(f"brief_{i+1}_title", "").strip() or brief_fallbacks_titles[i]
        desc = ed.get(f"brief_{i+1}_desc", "").strip() or fallback.get(f"brief_{i+1}_desc", "")
        briefs.append((title, desc))
    data["todays_brief_items_html"] = build_todays_brief_html(briefs, lang)

    # Energy — breaking_cluster: 에너지 관련 국가(이미지 있는 것 우선)
    energy_cc_list = ['IR', 'SA', 'IQ', 'KW', 'QA', 'AE', 'RU', 'YE']
    energy_cluster = next(
        (c for c in top_clusters if c[2] in energy_cc_list and c[6]),
        top_clusters[0] if top_clusters else None
    )
    # energy_intro + energy_p1 — 항상 Python 직접 생성 (GPT 불신뢰, 데이터 기반)
    if oil_price and oil_price_past:
        _oc = oil_change_period or 0.0
        _arrow = "↑" if _oc >= 0 else "↓"
        if is_kr:
            energy_intro = (
                f"유가 ${oil_price_past:.1f}→${oil_price:.1f}, {energy_label}. "
                f"{_arrow}{abs(_oc):.1f}% — 주유비{_arrow} 배달비{_arrow} 난방비{_arrow} 이미 시작."
            )
            energy_p1_base = (
                f"브렌트유 ${oil_price_past:.1f} → ${oil_price:.1f} "
                f"({_arrow}{abs(_oc):.1f}%, {energy_days}일간)."
            )
        else:
            energy_intro = (
                f"Oil ${oil_price_past:.1f}→${oil_price:.1f}, {energy_label}. "
                f"{_arrow}{abs(_oc):.1f}% — gas{_arrow} delivery{_arrow} groceries{_arrow} already moving."
            )
            energy_p1_base = (
                f"Brent crude ${oil_price_past:.1f} → ${oil_price:.1f} "
                f"({_arrow}{abs(_oc):.1f}%, {energy_days} days)."
            )
    elif oil_price and oil_change is not None:
        # oil_price_past 없음 → 변화율로 역산
        _calc_past = round(oil_price / (1 + oil_change / 100), 1) if oil_change else oil_price
        _arrow = "↑" if oil_change >= 0 else "↓"
        if is_kr:
            energy_intro = (
                f"유가 ${_calc_past:.1f}→${oil_price:.1f}, 7일. "
                f"{_arrow}{abs(oil_change):.1f}% — 주유비{_arrow} 배달비{_arrow} 난방비{_arrow} 이미 시작."
            )
        else:
            energy_intro = (
                f"Oil ${_calc_past:.1f}→${oil_price:.1f}, 7d. "
                f"{_arrow}{abs(oil_change):.1f}% — gas{_arrow} delivery{_arrow} groceries{_arrow} already moving."
            )
        energy_p1_base = (
            f"브렌트유 ${_calc_past:.1f} → ${oil_price:.1f} ({_arrow}{abs(oil_change):.1f}%, 7일)." if is_kr
            else f"Brent crude ${_calc_past:.1f} → ${oil_price:.1f} ({_arrow}{abs(oil_change):.1f}%, 7d)."
        )
    else:
        energy_intro = fallback.get("energy_intro", "")
        energy_p1_base = ""

    # GPT energy_p1에 내용이 있으면 base 뒤에 붙임, 없으면 기본값
    _gpt_p1 = ed.get("energy_p1", "").strip()
    if _gpt_p1 and len(_gpt_p1) > 20 and "↑" in _gpt_p1 or "→" in _gpt_p1:
        energy_p1 = _gpt_p1
    else:
        energy_p1 = energy_p1_base or fallback.get("energy_p1", "")

    # energy_p2: GPT에 ↑ 있으면 사용, 없으면 강제 생성
    _gpt_p2 = ed.get("energy_p2", "").strip()
    if _gpt_p2 and ("↑" in _gpt_p2 or "↓" in _gpt_p2):
        energy_p2 = _gpt_p2
    else:
        _arrow2 = "↑" if (oil_change_period or 0) >= 0 else "↓"
        energy_p2 = (
            f"주유비{_arrow2} 배달비{_arrow2} 난방비{_arrow2} — 이미 시작." if is_kr
            else f"gas{_arrow2} delivery{_arrow2} groceries{_arrow2} — already starting."
        )
    energy_p3 = ed.get("energy_p3", "").strip() or fallback.get("energy_p3", "")
    data["energy_section_intro_html"] = energy_intro
    data["energy_section_html"] = build_energy_html(
        energy_intro, energy_p1, energy_p2, energy_p3,
        oil_price, oil_change, lang,
        breaking_cluster=energy_cluster
    )

    # Deep dive — deep_dive_title 비어있으면 1위 클러스터 제목으로 폴백
    _raw_dd_title = ed.get("deep_dive_title", "").strip() or fallback.get("deep_dive_title", cl_title(top_clusters, 0))
    data["deep_dive_nav_label"] = _raw_dd_title[:30]
    data["deep_dive_title"] = _raw_dd_title

    # deep_dive country_rows: 상위 클러스터별 국가 집계
    dd_country_rows = []
    seen_dd_cc = set()
    for c in top_clusters[:8]:
        cc_val = c[2]
        if cc_val and cc_val not in seen_dd_cc:
            status = ((c[1] or c[0]) if is_kr else (c[0] or c[1]) or "")[:30]
            dd_country_rows.append((cc_val, status, c[5]))
            seen_dd_cc.add(cc_val)
        if len(dd_country_rows) >= 5:
            break

    data["deep_dive_section_html"] = build_deep_dive_html(
        _raw_dd_title,
        ed.get("deep_dive_p1", "").strip() or fallback.get("deep_dive_p1", ""),
        ed.get("deep_dive_p2", "").strip() or fallback.get("deep_dive_p2", ""),
        ed.get("deep_dive_p3", "").strip() or fallback.get("deep_dive_p3", ""),
        ed.get("deep_dive_p4", "").strip() or fallback.get("deep_dive_p4", ""),
        ed.get("deep_dive_why", "").strip() or fallback.get("deep_dive_why", ""),
        lang,
        image_url=cl_img(top_clusters, 0),
        country_rows=dd_country_rows
    )

    # Numbers
    wow_rows = [
        ("위기 국가" if is_kr else "Crisis", str(crisis_prev), str(crisis_count),
         f"+{diff}" if diff > 0 else str(diff)),
    ]
    if oil_price and oil_change:
        prev_oil = oil_price / (1 + oil_change/100) if oil_change != 0 else oil_price
        wow_rows.append(("유가(WTI 주간)" if is_kr else "Oil(WTI wk)",
                         f"${prev_oil:.0f}", f"${oil_price:.0f}", f"{oil_change:+.0f}%"))
    if target_score:
        wow_rows.append((f"{cn(target_cc, lang)} 긴장도" if is_kr else f"{cn(target_cc, lang)} Tension",
                         f"{target_prev:.1f}", f"{target_score:.1f}", data["tension_change"]))
    # 시장 지수 (언어별 분기) — highlight_line과 중복 방지를 위해 top_ev_label 행 제거
    if is_kr:
        if kospi_val and kospi_prev_val:
            kospi_chg = (kospi_val - kospi_prev_val) / kospi_prev_val * 100
            wow_rows.append(("KOSPI", f"{kospi_prev_val:,.0f}", f"{kospi_val:,.0f}", f"{kospi_chg:+.1f}%"))
        if usd_krw and usd_krw_prev:
            krw_chg = (usd_krw - usd_krw_prev) / usd_krw_prev * 100
            wow_rows.append(("원달러 환율", f"{usd_krw_prev:,.0f}", f"{usd_krw:,.0f}", f"{krw_chg:+.1f}%"))
    else:
        if nasdaq_val and nasdaq_prev_val:
            nq_chg = (nasdaq_val - nasdaq_prev_val) / nasdaq_prev_val * 100
            wow_rows.append(("NASDAQ", f"{nasdaq_prev_val:,.0f}", f"{nasdaq_val:,.0f}", f"{nq_chg:+.1f}%"))

    # 하이라이트 라인 계산 (상위 20개 평균 대비)
    highlight_line = None
    if top_clusters and avg_event_count > 0:
        top_ev = top_clusters[0][5]
        ratio = top_ev / avg_event_count
        if ratio >= 1.5:
            top_name = cl_title(top_clusters, 0)
            ratio_str = f"{ratio:.1f}"
            if is_kr:
                highlight_line = f"{top_name} {top_ev:,}건 — 주요 이슈 평균 {avg_event_count:.0f}건 대비 {ratio_str}배"
            else:
                highlight_line = f"{top_name}: {top_ev:,} events — {ratio_str}x the top-20 average ({avg_event_count:.0f})"

    data["numbers_section_html"] = build_numbers_html({
        "events_24h": events_24h, "events_7d": events_7d,
        "events_7d_raw": events_7d if isinstance(events_7d, int) else int(str(events_7d).replace(",", "")),
        "events_24h_prev": events_24h_prev, "events_7d_prev": events_7d_prev,
        "crisis_count": crisis_count, "active_issues": active_issues,
        "top_cc_events": top_cc_ev, "top_cc_name": top_cc_name,
        "wow_rows": wow_rows, "highlight": highlight_line,
    }, lang)

    # Country impact — GPT 실패 시 폴백 사용
    _impact_fallbacks = [
        fallback.get("impact_1", cl_title(top_clusters, 0)),
        fallback.get("impact_2", "국제 원자재·에너지 가격 변동" if is_kr else "International commodity & energy price shifts"),
        fallback.get("impact_3", "물가·환율·운송비 영향" if is_kr else "Inflation, freight, supply chain disruption"),
        fallback.get("impact_4", "국내 수입·소비·경제 파급" if is_kr else "Domestic economy — prices, jobs, stocks"),
    ]
    steps = []
    for i in range(1, 5):
        step = ed.get(f"impact_{i}", "").strip()
        steps.append(step or _impact_fallbacks[i - 1])
    data["country_impact_html"] = build_country_impact_html(steps, lang)

    # Country issues (DB 기반, description 컬럼 활용)
    issues = []
    for row_data in country_issues_rows:
        title, title_ko, ev_count = row_data[0], row_data[1], row_data[2]
        desc = row_data[3] if len(row_data) > 3 else None
        display = (title_ko or title) if is_kr else (title or title_ko)
        if not desc and display:
            parts = display.split()
            desc = " ".join(parts[-3:]) if len(parts) > 3 else ""
        issues.append((display, desc or "", ev_count or 0))
    data["country_issues_html"] = build_country_issues_html(issues, lang)

    # Did you know — GPT 결과 최소 40자 이상이어야 사용, 아니면 라이브러리 사용
    _gpt_dyk = ed.get("did_you_know", "").strip()
    dyk_text = _gpt_dyk if len(_gpt_dyk) >= 40 else fallback.get("did_you_know", "")
    # 팩트를 '. ' 또는 마침표로 분리해서 구조화된 박스로 렌더링
    import re as _re
    _dyk_facts = [s.strip() for s in _re.split(r'(?<=[.!?])\s+', dyk_text) if len(s.strip()) >= 10]
    if len(_dyk_facts) >= 2:
        _icons = ["📍", "📊", "💡"]
        _rows = "".join(
            f'<tr><td style="padding:6px 0;border-bottom:1px solid #f0f0f0;vertical-align:top;">'
            f'<span style="font-size:13px;margin-right:6px;">{_icons[i % len(_icons)]}</span>'
            f'<span style="font-size:12px;color:#27272a;line-height:1.5;">{fact}</span>'
            f'</td></tr>'
            for i, fact in enumerate(_dyk_facts[:3])
        )
        data["did_you_know_html"] = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'{_rows}</table>'
        )
    else:
        data["did_you_know_html"] = f'<p style="font-size:12px;line-height:1.6;color:#52525b;margin:0;">{dyk_text}</p>'

    # Editors note
    data["editors_note_html"] = build_editors_note_html(
        ed.get("editors_note_p1", "").strip() or fallback.get("editors_note_p1", ""),
        ed.get("editors_note_p2", "").strip() or fallback.get("editors_note_p2", ""),
        ed.get("editors_note_p3", "").strip() or fallback.get("editors_note_p3", ""),
        ps=ed.get("editors_ps", "").strip() or fallback.get("editors_ps", ""),
        lang=lang)

    # Next week
    data["next_week_items_html"] = build_next_week_html([
        ed.get("next_week_1", "").strip() or fallback.get("next_week_1", ""),
        ed.get("next_week_2", "").strip() or fallback.get("next_week_2", ""),
        ed.get("next_week_3", "").strip() or fallback.get("next_week_3", ""),
    ])

    # Calendar — 실제 날짜 + GPT/폴백 태그
    cal_days = []
    for i in range(4):
        dt = now + timedelta(days=i)
        event = ed.get(f"calendar_{i+1}_event", "").strip() or fallback.get(f"calendar_{i+1}_event", "")
        raw_tags = ed.get(f"calendar_{i+1}_tags", "") or fallback.get(f"calendar_{i+1}_tags", [])
        if isinstance(raw_tags, list):
            tags = raw_tags
        elif isinstance(raw_tags, str) and raw_tags:
            tags = [t.strip() for t in raw_tags.replace("/", ",").split(",") if t.strip()]
        else:
            tags = []
        cal_days.append((dt, event, tags))
    tag_colors = ["#dc2626", "#b45309", "#059669"]
    cal_tag_color = tag_colors[vol % 3]
    data["calendar_html"] = build_calendar_html(cal_days, lang, tag_color=cal_tag_color)

    # Share, CTA
    data["share_headline"] = ed.get("share_headline", "").strip() or fallback.get("share_headline", "")
    data["share_subtext"] = ed.get("share_subtext", "").strip() or fallback.get("share_subtext", "")
    data["pro_cta_subtext"] = ed.get("pro_cta_subtext", "").strip() or fallback.get("pro_cta_subtext", "")

    # pro_cta_headline_html — \n → <br>, 강조 키워드 볼드
    raw_cta = ed.get("pro_cta_headline", "").strip() or fallback.get("pro_cta_headline", "")
    if raw_cta:
        formatted_cta = raw_cta.replace("\n", "<br>\n")
        for kw in ["그 순간", "real-time", "instantly", "즉시"]:
            formatted_cta = formatted_cta.replace(kw, f'<b style="color:#eab308;">{kw}</b>')
        data["pro_cta_headline_html"] = formatted_cta
    else:
        _cta_word_kr = "급등" if target_delta > 5 else ("급락" if target_delta < -5 else "변동")
        _cta_word_en = "surged" if target_delta > 5 else ("dropped" if target_delta < -5 else "shifted")
        data["pro_cta_headline_html"] = (
            f'{cn(target_cc, lang)} 긴장도 {target_score:.1f} {_cta_word_kr} —<br>'
            f'Pro는 <b style="color:#eab308;">그 순간</b> 알림을 받아요.'
            if is_kr else
            f'{cn(target_cc, lang)} tension {target_score:.1f} {_cta_word_en} —<br>'
            f'Pro users get <b style="color:#eab308;">real-time</b> alerts.'
        )

    # tension_warning_html — DB 기반 자동 생성
    at_100 = len([s for _, s, _ in tension_rows if s >= 99])
    base_warning = ""
    if at_100 >= 4:
        base_warning = (
            f"TOP {at_100}개국 긴장도 100점 — 역대급 동시 위기."
            if is_kr else
            f"Top {at_100} countries all at 100 — historic simultaneous crisis."
        )
    gpt_warning = ed.get("tension_warning", "").strip()
    final_warning = gpt_warning or base_warning
    if final_warning:
        data["tension_warning_html"] = f'<b>{"이상 신호:" if is_kr else "Warning:"}</b> {final_warning}'
    else:
        data["tension_warning_html"] = ""

    # Country summary — 항상 DB 기반 짧은 펀치 문체 사용 (deep_dive_why는 너무 길고 verbose)
    data["country_summary"] = _generate_country_summary(target_cc, target_score, oil_change, is_kr)

    # streak_text — DB 계산 결과 사용 (양수=상승, 음수=하락)
    if streak_weeks >= 2:
        data["streak_text"] = f"{streak_weeks}주 연속 상승" if is_kr else f"Rising {streak_weeks} weeks"
    elif streak_weeks == 1:
        data["streak_text"] = "지난주 대비 상승" if is_kr else "Up from last week"
    elif streak_weeks <= -2:
        data["streak_text"] = f"{abs(streak_weeks)}주 연속 하락" if is_kr else f"Falling {abs(streak_weeks)} weeks"
    elif streak_weeks == -1:
        data["streak_text"] = "지난주 대비 하락" if is_kr else "Down from last week"
    else:
        # 연속 추세 없음 — 긴장도가 높으면 "지속 위기", 낮으면 ""
        if target_score >= 80:
            data["streak_text"] = "위기 지속" if is_kr else "Sustained crisis"
        elif target_score >= 50:
            data["streak_text"] = "긴장 지속" if is_kr else "Elevated tension"
        else:
            data["streak_text"] = ""

    # 고정값 — 히어로 이미지 품질 필터
    def _pick_hero_image(clusters: list) -> str:
        """thumbnail/small 키워드 URL 제외. 최대 3개 클러스터 순서대로 시도."""
        bad_patterns = [
            "thumbnail", "/thumb/", "/small/", "50x50", "100x100",
            "150x150", "200x200", "icon", "avatar", "logo",
        ]
        for i in range(min(3, len(clusters))):
            url = cl_img(clusters, i)
            if not url:
                continue
            url_lower = url.lower()
            if any(bad in url_lower for bad in bad_patterns):
                print(f"    ⚠ 히어로 이미지 품질 낮음(건너뜀): cluster[{i}] {url[:80]}")
                continue
            return url
        # 모두 부적합이면 첫 번째 URL 그대로 사용
        return cl_img(clusters, 0)

    data["hero_image_url"] = _pick_hero_image(top_clusters)
    data["hero_subheadline_html"] = ""
    # deep_dive는 #2 클러스터 이미지로 차별화 (hero/conflict 카드 #1과 중복 방지)
    data["deep_dive_image_url"] = cl_img(top_clusters, 1) or cl_img(top_clusters, 0)
    data["banner_image_url"] = ""
    data["map_snapshot_url"] = ""
    data["og_image_url"] = cl_img(top_clusters, 0)
    data["editors_name"] = "WeWantPeace Team"
    data["editors_photo_url"] = ""
    data["preview_text"] = data["preheader_text"]

    share_text = data["share_headline"]
    data["social_share_text"] = share_text
    data["mailto_subject"] = quote(f"WeWantPeace Vol.{vol} — {share_text[:40]}")
    data["mailto_body"] = quote(f"{share_text}\n\nhttps://www.wewantpeace.live/?ref=share")
    data["call_to_action_text"] = "앱에서 실시간 확인" if is_kr else "Check live in the app"
    data["call_to_action_url"] = "https://www.wewantpeace.live/"
    data["call_to_action_html"] = ""
    data["sponsor_section_html"] = ""
    data["sponsor_logo_url"] = ""
    data["featured_quote"] = ""
    data["featured_quote_author"] = ""
    data["additional_resources_html"] = ""
    data["footer_address"] = "WeWantPeace | wewantpeace.live"
    data["unsubscribe_url"] = "#"
    data["web_version_url"] = "https://wewantpeace.live/newsletter"

    data["_generated_at"] = now.isoformat()
    data["_lang"] = lang
    data["_status"] = "draft"

    return data


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vol", type=int, required=True)
    parser.add_argument("--lang", choices=["kr", "us"], required=True)
    parser.add_argument("--test", action="store_true",
                        help="테스트 생성 — Redis 키를 'test-' 접두어로 저장하고 latest_draft_vol 미업데이트")
    args = parser.parse_args()

    is_test = args.test
    print(f"=== Newsletter Vol.{args.vol} ({args.lang}){' [TEST]' if is_test else ''} ===")
    data = await generate(args.vol, args.lang)

    import redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(redis_url, decode_responses=True)

    # 최종 CJK 클린업: HTML 포함 모든 문자열 필드에서 한자/가나 제거
    def _deep_fix_cjk(obj):
        if isinstance(obj, str):
            return _fix_cjk(obj)
        elif isinstance(obj, dict):
            return {k: _deep_fix_cjk(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_deep_fix_cjk(i) for i in obj]
        return obj
    data = _deep_fix_cjk(data)

    if is_test:
        # 테스트 생성: 별도 키에 저장 (24h TTL), vol 카운터 영향 없음
        key = f"admin:newsletter:draft:test-{args.lang}"
        r.set(key, json.dumps(data, ensure_ascii=False, default=str), ex=86400)
        print(f"  ⚠ TEST 모드: '{key}' 저장 (24h TTL, vol 카운터 미변경)")
    else:
        key = f"admin:newsletter:draft:vol{args.vol}-{args.lang}"
        r.set(key, json.dumps(data, ensure_ascii=False, default=str), ex=90*86400)

    filled = len([k for k in data if not k.startswith('_') and data[k] not in ('', 0, None)])
    empty = len([k for k in data if not k.startswith('_') and data[k] in ('', 0, None)])
    print(f"\nSaved: {key} ({len(json.dumps(data)):,} bytes)")
    print(f"  conflicts: {data['total_conflicts']} | crisis: {data['crisis_countries_count']}")
    print(f"  events: {data['events_24h']}(24h) / {data['events_7d']}(7d)")
    print(f"  tension: {data['country_name']} {data['tension_score']} (#{data['country_rank']})")
    print(f"  hero: {data.get('hero_headline_html', '')[:80]}")
    print(f"  filled: {filled} | empty: {empty}")


if __name__ == "__main__":
    asyncio.run(main())
