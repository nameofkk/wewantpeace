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
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# ── GPT 호출 (텍스트만 생성) ─────────────────────────────────────────────────
async def call_gpt(prompt: str, system: str = "") -> str:
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        messages = []
        if system: messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, temperature=0.7, max_tokens=4000,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  GPT error: {e}")
        return ""


async def generate_editorial(ctx: dict, lang: str, vol: int = 1) -> dict:
    """GPT로 편집 텍스트만 생성. HTML 금지. Vol.1 예시 포함."""
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

    # Vol.1 스타일 예시
    examples_kr = """
[Vol.1 예시 — 이 톤과 구체성을 그대로 따라]
hero_headline: "호르무즈 해협이 막혔는데,\n한국 원유 70%가 거길 지나요"
preheader: "해협 하나 막혔는데 기름값이 뛰어요. 23개국 위기, 854건 감지. 한국 긴장도 96.8 — 내가 왜 영향받는지, 2분."
brief_1: "이란-이스라엘 전면전 → 호르무즈 사실상 봉쇄"
brief_2: "걸프 정유소 피격, 한국 원유 직격탄"
brief_3: "한국 긴장도 96.8 — 세계 8위. 왜?"
energy_intro: "유가 $95→$118, 일주일. 지갑까지 오는 위기."
energy_narrative: "브렌트유 $95 → $118 (↑24.2%, 7일간). 한국 체감: 주유비↑ 배달비↑ 난방비↑ — 이미 시작. 다음 주유 때 확인."
deep_dive: "폭 33km — 하루 유조선 21척. 세계 원유 20%가 여기 걸려 있는데 — 이란이 봉쇄 — 한국행 유조선이 해협에서 멈췄어요."
editors_note: "해협 하나로 세계가 흔들린다는 게 증명됐죠. 한국 에너지 70%가 여길 지나요. 중동 미사일이 날면 한국 주유소 가격표가 바뀌는 나라."
impact: "호르무즈 봉쇄 → 원유 차질 → 주유소 가격↑ → 택배·배달비↑ → 인플레 → KOSPI↓"
share_headline: "2분 전과 세상이 달라 보이죠."
share_subtext: "출장 동료, 주식 보는 친구, 기름값 걱정 부모님 — 한 명에게."
did_you_know: "한국 에너지 자급률 OECD 38국 최하위 16%. 원유 70% 호르무즈 경유. 막히면 비축유 90일 유일."
pro_cta: "한국 긴장도 96.8 급등 — Pro는 그 순간 알림을 받아요."
"""
    examples_en = """
[Vol.1 Example — match this tone and specificity. ALL TEXT MUST BE IN ENGLISH ONLY.]
hero_headline: "The Strait of Hormuz is blocked.\n70% of your oil passes through it."
preheader: "One strait blocked, gas prices soaring. 23 crisis countries, 854 events — why it matters to you, in 2 min."
energy_intro: "Oil $95→$118 in one week. The impact is heading to your wallet."
energy_narrative: "Brent crude $95 → $118 (↑24.2%, 7 days). Your daily costs: gas↑ delivery↑ heating↑ — already starting."
editors_note: "One strait proved it can shake the world. When missiles fly in the Middle East, gas station prices change at home."
share_headline: "The world looks different from 2 minutes ago."
share_subtext: "Share with your coworkers, investor friends, and family who travel."
impact: "Hormuz blockade → oil disruption → gas prices↑ → delivery costs↑ → inflation → stocks↓"
"""
    examples = examples_kr if is_kr else examples_en

    dont_list = """
DON'T:
- 추상적 문장 ("tensions are rising", "situation is developing", "긴장이 고조되고 있다")
- 학술 용어 ("geopolitical", "bilateral", "multilateral", "지정학적", "양자적")
- 뻔한 결론 ("time will tell", "remains to be seen", "지켜봐야 할 것")
- 감정적 과장 ("shocking", "devastating", "catastrophic", "충격적", "참혹한")
DO:
- 구체적 숫자와 사실만 ("유가 $104 → $112, 7일" / "Oil $104 → $112, 7 days")
- 일상 연결 ("주유할 때 느낄 수 있어요" / "You'll notice at the pump")
- Vol.1 톤 유지 ("해협 하나 막혔는데 기름값이 뛰어요" / "One strait blocked, gas prices up")
"""
    if is_kr:
        system = f"""You are the editor of WeWantPeace newsletter.
한국어 구어체. ~해요 체. 구체적 숫자와 비유 필수. 추상적 문장 금지.
CRITICAL RULES:
- 반드시 한국어로만 작성. 영어 섞지 마세요.
- Use EXACT numbers from the data (prices, %, event counts, tension scores)
- Connect EVERY point to the reader's daily life (주유비, 장바구니, 배달비, 여행)
- Never use "may", "might" alone — always with specific data: "유가 $118 → 주유비 영향 올 수 있어요"
- No generic filler. Every sentence must have new information.
- Output ONLY valid JSON. No markdown fences.
{dont_list}
STYLE HINTS FOR THIS VOLUME:
- hero_headline 스타일: {hero_style}
- editors_note 톤: {editors_tone}
- did_you_know 카테고리: {dyk_category}"""
    else:
        system = f"""You are the editor of WeWantPeace newsletter.
Write ONLY in English. Casual, conversational tone. Specific numbers and analogies required. No abstract statements.
CRITICAL RULES:
- MUST write ALL text in English only. No Korean or other languages.
- Use EXACT numbers from the data (prices, %, event counts, tension scores)
- Connect EVERY point to the reader's daily life (gas prices, grocery bills, delivery fees, travel costs)
- Never use "may", "might" alone — always with specific data: "Oil $118 → gas prices may rise"
- No generic filler. Every sentence must have new information.
- Output ONLY valid JSON. No markdown fences.
{dont_list}
STYLE HINTS FOR THIS VOLUME:
- hero_headline style: {hero_style}
- editors_note tone: {editors_tone}
- did_you_know category: {dyk_category}"""

    prompt = f"""{examples}

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
- Oil ({ctx['energy_period']} comparison): ${ctx['oil_price_past']} → ${ctx['oil_price']} ({ctx['oil_change_period']}%)

Generate JSON with these TEXT-ONLY fields (NO HTML tags except <br> in hero_headline and <b> for emphasis):
{{
  "hero_headline": "(2-3 lines separated by \\n. #1 story → why it matters to {ctx['target_name']}. Use concrete number.)",
  "preheader": "(1 sentence, 70-90 chars. Hook: specific stat + reader impact.)",
  "brief_1_title": "(#1 story, 15-25 chars, punchy)",
  "brief_1_desc": "(1 sentence connecting to reader's daily life)",
  "brief_2_title": "(#2 story, 15-25 chars)",
  "brief_2_desc": "(1 sentence)",
  "brief_3_title": "({ctx['target_name']} tension headline)",
  "brief_3_desc": "(why this rank/score matters to the reader)",
  "energy_intro": "(1 punchy sentence with price number. Like: {'유가 $X→$Y, Z일. 지갑까지 오는 위기.' if is_kr else 'Oil $X→$Y in Z days. The impact is heading to your wallet.'})",
  "energy_p1": "(paragraph 1: what happened to prices, specific numbers)",
  "energy_p2": "(paragraph 2: how it hits daily life — gas, delivery, groceries)",
  "energy_p3": "(paragraph 3: what to watch next week)",
  "deep_dive_title": "(short title for #1 story deep dive)",
  "deep_dive_p1": "(what happened — facts, timeline, numbers)",
  "deep_dive_p2": "(why it matters globally)",
  "deep_dive_p3": "(how it affects {ctx['target_name']} specifically)",
  "deep_dive_p4": "(what to watch next)",
  "deep_dive_why": "(WHY IT MATTERS — 2-3 sentences, the 'so what' for the reader)",
  "impact_1": "(step 1: triggering event)",
  "impact_2": "(step 2: market reaction — specific: oil↑, shipping↑)",
  "impact_3": "(step 3: daily life — {'주유비↑, 배달비↑, 장바구니↑' if is_kr else 'gas↑, delivery↑, groceries↑'})",
  "impact_4": "(step 4: macro consequence — {'인플레, 금리, 증시' if is_kr else 'inflation, rates, stocks'})",
  "did_you_know": "(1 surprising fact with specific number, related to this week)",
  "editors_note_p1": "(what made this week different — 1 bold statement)",
  "editors_note_p2": "(connect to reader's life with vivid metaphor)",
  "editors_note_p3": "(closing: encouragement to share, see you next week)",
  "editors_ps": "(P.S. — {'한 줄 이탤릭 마무리. 예: 이 뉴스레터가 도움이 되셨다면, 한 분에게 전달해 주세요.' if is_kr else 'One italic closing line. e.g. If this helped, forward it to one person.'})",
  "next_week_1": "(thing to watch #1)",
  "next_week_2": "(thing to watch #2)",
  "next_week_3": "(thing to watch #3)",
  "share_headline": "(catchy 1-line, emotional, not generic)",
  "share_subtext": "(who to share with — specific people: {'출장 동료, 주식 보는 친구, 기름값 걱정 부모님' if is_kr else 'coworkers, investor friends, family who travel'})",
  "pro_cta_headline": "(mention specific data point + Pro real-time advantage)",
  "pro_cta_subtext": "(1 sentence: free vs pro timing gap)",
  "tension_warning": "(1 alarming pattern in tension data with specific numbers)",
  "calendar_1_event": "(tomorrow's expected event)",
  "calendar_1_tags": "(1-2 tags from: {'안보/경제/에너지/외교/인도/환경' if is_kr else 'security/economy/energy/diplomacy/humanitarian/climate'})",
  "calendar_2_event": "(day+2 event)",
  "calendar_2_tags": "(1-2 tags)",
  "calendar_3_event": "(day+3 event)",
  "calendar_3_tags": "(1-2 tags)",
  "calendar_4_event": "(day+4 event)",
  "calendar_4_tags": "(1-2 tags)"
}}"""

    result = await call_gpt(prompt, system)
    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"): cleaned = cleaned[:-3]
        return json.loads(cleaned)
    except Exception as e:
        print(f"  GPT JSON parse error: {e}")
        print(f"  Raw: {result[:300]}")
        return {}


# ── HTML 빌더 (Vol.1 스타일) ─────────────────────────────────────────────────

def build_tension_table_html(rows: list, lang: str, target_cc: str = "KR") -> str:
    if not rows: return "<p>No data</p>"
    html = ['<table style="width:100%;border-collapse:collapse;">']
    for cc, score, delta in rows[:10]:
        flag, name = get_flag(cc), cn(cc, lang)
        color = sev_color(tension_num(score))
        w = min(int(score), 100)
        ds = f"▲{abs(delta):.1f}" if delta > 0 else f"▼{abs(delta):.1f}" if delta < 0 else "—"
        hl = ' style="background:#fffbeb;"' if cc == target_cc else ""
        you = f' <span style="background:#eab308;color:white;padding:1px 6px;border-radius:8px;font-size:10px;">YOU</span>' if cc == target_cc else ""
        html.append(
            f'<tr{hl}>'
            f'<td style="padding:8px;white-space:nowrap;font-size:13px;">{flag} {name}{you}</td>'
            f'<td style="padding:8px;width:35%;"><div style="background:{color};height:8px;border-radius:4px;width:{w}%;"></div></td>'
            f'<td style="padding:8px;text-align:right;font-weight:bold;color:{color};font-size:13px;">{score:.1f}</td>'
            f'<td style="padding:8px;text-align:right;font-size:11px;color:#666;">{ds}</td></tr>')
    html.append("</table>")
    return "\n".join(html)


def build_todays_brief_html(items: list, lang: str) -> str:
    """Vol.1 스타일: 번호 뱃지 + 컬러 보더 카드 + desc."""
    colors = ["#dc2626", "#dc2626", "#18181b"]
    bgs = ["#fef2f2", "#fef2f2", "#fafafa"]
    html = []
    for i, (title, desc) in enumerate(items[:3]):
        c, bg = colors[i], bgs[i]
        desc_html = f'<p style="font-size:11px;color:#71717a;margin:4px 0 0;line-height:1.5;">{desc}</p>' if desc else ""
        html.append(
            f'<tr><td style="border-radius:6px;background:{bg};padding:10px 14px;border-left:3px solid {c};">'
            f'<p style="font-size:14px;color:#27272a;margin:0;line-height:1.7;">'
            f'<span style="display:inline-block;font-weight:700;text-align:center;font-size:10px;vertical-align:middle;'
            f'color:#fff;background:{c};border-radius:50%;margin-right:4px;width:18px;height:18px;line-height:18px;">{i+1}</span>'
            f'<span style="color:#27272a;">{title}</span></p>{desc_html}</td></tr>'
            f'<tr><td height="8"></td></tr>')
    return "\n".join(html)


def build_conflict_stories_html(clusters: list, lang: str, vol: int = 1) -> str:
    if not clusters: return ""
    is_kr = lang == "kr"

    # P3-4: conflict_stories 라벨 변동
    label_sets_kr = [("TOP STORY", "주간 요약"), ("긴급", "지속"), ("확대", "주시")]
    label_sets_en = [("TOP STORY", "Weekly"), ("BREAKING", "ONGOING"), ("ESCALATING", "WATCH")]
    labels = (label_sets_kr if is_kr else label_sets_en)[vol % 3]

    html = []
    for i, cluster in enumerate(clusters[:5]):
        title, title_ko, cc, sev, kscore, event_count, image_url = cluster
        flag = get_flag(cc)
        color = sev_color(min(sev, 5))
        bg = {"#ef4444": "#fef2f2", "#f97316": "#fff7ed", "#eab308": "#fefce8"}.get(color, "#f8fafc")
        display = (title_ko or title or "") if is_kr else (title or title_ko or "")
        ev_l = f"{event_count}건 확인" if is_kr else f"{event_count} sources confirmed"

        # "왜 중요" 자동 생성
        if sev >= 5:
            why = "즉각적인 영향 가능" if is_kr else "Immediate impact possible"
        elif sev >= 4:
            why = "주목할 상황" if is_kr else "Situation to watch"
        else:
            why = ""

        # 라벨
        tag = labels[0] if i == 0 else labels[1]
        tag_bg = "#dc2626" if i == 0 else "#71717a"

        # 첫 번째 = 큰 카드
        if i == 0:
            img_html = f'<img src="{image_url}" style="width:100%;max-height:200px;object-fit:cover;border-radius:6px 6px 0 0;" alt="">' if image_url else ""
            why_html = f'<div style="margin-top:8px;padding:8px 10px;background:#fff5f5;border-radius:4px;font-size:11px;color:#dc2626;font-weight:600;">{"왜 중요해요?" if is_kr else "Why it matters?"} {why}</div>' if why else ""
            html.append(
                f'<div style="margin-bottom:16px;border-radius:8px;border:1px solid #e5e5e5;overflow:hidden;">'
                f'{img_html}'
                f'<div style="padding:14px 16px;">'
                f'<span style="background:{tag_bg};color:white;padding:2px 8px;border-radius:3px;font-size:9px;font-weight:700;letter-spacing:.5px;">{tag}</span>'
                f'<div style="font-weight:bold;font-size:15px;margin:8px 0 4px;">{flag} {display[:80]}</div>'
                f'<div style="display:flex;gap:8px;align-items:center;">'
                f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{"심각도" if is_kr else "Severity"} {min(sev, 100)}</span>'
                f'<span style="color:#666;font-size:11px;">{ev_l}</span></div>'
                f'{why_html}'
                f'</div></div>')
        else:
            why_span = f' · <span style="color:#dc2626;font-size:10px;">{why}</span>' if why else ""
            html.append(
                f'<div style="margin-bottom:10px;padding:10px 12px;border-left:3px solid {color};background:{bg};">'
                f'<span style="background:{tag_bg};color:white;padding:1px 6px;border-radius:3px;font-size:8px;font-weight:700;letter-spacing:.5px;">{tag}</span>'
                f'<div style="font-weight:bold;margin:4px 0 2px;">{flag} {display[:80]}</div>'
                f'<div style="display:flex;gap:8px;align-items:center;">'
                f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{"심각도" if is_kr else "Severity"} {min(sev, 100)}</span>'
                f'<span style="color:#666;font-size:11px;">{ev_l}</span>{why_span}</div></div>')
    return "\n".join(html)


def build_energy_html(intro: str, p1: str, p2: str, p3: str, oil_price, oil_change, lang: str) -> str:
    """Vol.1 스타일: 인트로 + 가격카드 + 서술 단락."""
    price_str = f"${oil_price:.0f}" if oil_price else "N/A"
    change_str = f"{oil_change:+.1f}%" if oil_change is not None else ""
    is_kr = lang == "kr"
    label = "한국 체감" if is_kr else "Impact"
    html = f"""<p style="font-size:13px;color:#71717a;line-height:1.6;margin:0 0 16px;">{p1}</p>
<table style="width:100%;border-collapse:collapse;border-radius:8px;border:1px solid #e8e8e3;border-left:4px solid #b45309;margin-bottom:16px;">
<tr><td style="padding:14px 16px;">
<p style="font-size:15px;font-weight:700;color:#18181b;margin:0 0 6px;">{"유가" if is_kr else "Oil"} {price_str} <span style="color:#dc2626;">{change_str}</span></p>
<p style="font-size:13px;color:#52525b;line-height:1.65;margin:0 0 8px;">{p2}</p>
<p style="font-size:12px;font-weight:600;color:#18181b;margin:0;"><b>{label}:</b> {p3}</p>
</td></tr></table>"""
    return html


def build_deep_dive_html(title: str, p1: str, p2: str, p3: str, p4: str, why: str, lang: str) -> str:
    """Vol.1 스타일: 서술 + WHY IT MATTERS 박스."""
    html = f"""<p style="font-size:13px;color:#71717a;line-height:1.6;margin:0 0 16px;">{p1}</p>
<p style="font-size:13px;color:#71717a;line-height:1.6;margin:0 0 16px;">{p2}</p>
<p style="font-size:13px;color:#71717a;line-height:1.6;margin:0 0 16px;">{p3}</p>
<p style="font-size:13px;color:#71717a;line-height:1.6;margin:0 0 16px;">{p4}</p>
<table style="width:100%;border-radius:6px;background:#fafafa;border-left:4px solid #18181b;margin-top:14px;">
<tr><td style="padding:14px 16px;">
<p style="font-size:9px;font-weight:600;color:#18181b;margin:0 0 4px;letter-spacing:1.5px;">WHY IT MATTERS</p>
<p style="font-size:13px;line-height:1.65;margin:0;color:#1e3a5f;">{why}</p>
</td></tr></table>"""
    return html


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
    """Vol.1 스타일: 번호 + 영향 체인 + → 화살표."""
    html = '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
    for i, step in enumerate(steps[:4]):
        c = "#dc2626" if i in [0, 3] else "#71717a"
        is_last = i == len(steps[:4]) - 1
        bold = ' style="font-weight:700;color:#dc2626;"' if is_last else ""
        html += f'<tr><td width="24" valign="top" style="text-align:left;padding:4px 0;font-weight:700;color:{c};">{i+1}</td>'
        html += f'<td style="text-align:left;padding:4px 0;"{bold}>{step}</td></tr>'
        if not is_last:
            html += '<tr><td></td><td style="padding:2px 0;color:#d4d4d8;font-size:14px;">→</td></tr>'
    html += '</table>'
    return html


def build_country_issues_html(issues: list, lang: str) -> str:
    """Vol.1 스타일: 3열 이슈 테이블."""
    is_kr = lang == "kr"
    html = '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
    html += f'<tr><td style="padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">{"이슈" if is_kr else "Issue"}</td>'
    html += f'<td style="padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">{"상세" if is_kr else "Detail"}</td>'
    html += f'<td width="40" style="text-align:right;padding:8px 0;font-weight:600;font-size:9px;color:#64748b;letter-spacing:1.5px;border-bottom:2px solid #18181b;">{"이벤트" if is_kr else "Events"}</td></tr>'
    for name, detail, count in issues:
        c = "#dc2626" if count and int(str(count).replace(",", "")) >= 10 else "#71717a"
        html += f'<tr><td style="padding:8px 0;font-weight:700;color:#18181b;border-bottom:1px solid #f4f4f5;">{name}</td>'
        html += f'<td style="padding:8px 0;color:#52525b;border-bottom:1px solid #f4f4f5;">{detail}</td>'
        html += f'<td style="text-align:right;padding:8px 0;font-weight:700;color:{c};border-bottom:1px solid #f4f4f5;">{count}{"건" if is_kr else ""}</td></tr>'
    html += '</table>'
    return html


def build_calendar_html(days: list, lang: str, tag_color: str = "#dc2626") -> str:
    """Vol.1 스타일: 날짜열 + 이벤트열 + 태그 색상 회전."""
    is_kr = lang == "kr"
    html = '<table style="width:100%;border-collapse:collapse;font-size:12px;border:1px solid #e5e5e5;border-radius:8px;">'
    for i, (dt, event, tags) in enumerate(days[:4]):
        wd_str = WEEKDAY_KO[dt.weekday()] if is_kr else WEEKDAY_EN[dt.weekday()]
        date_str = f"{dt.month}/{dt.day}"
        bg = "#fafafa" if i % 2 == 1 else "#fff"
        today = " style=\"background:#dc2626;color:white;padding:1px 6px;border-radius:3px;font-size:7px;font-weight:700;\"" if i == 0 else ""
        html += f'<tr><td width="60" valign="middle" style="background:{bg};padding:10px 8px;text-align:center;border-bottom:1px solid #f0f0f0;">'
        html += f'<p style="font-weight:700;font-size:14px;margin:0;">{date_str}</p>'
        html += f'<p style="font-size:9px;color:#71717a;margin:2px 0 0;">{wd_str}</p>'
        if i == 0 and is_kr:
            html += f'<p style="margin:2px 0 0;"><span{today}>D-DAY</span></p>'
        html += f'</td><td style="background:{bg};padding:10px 12px;border-bottom:1px solid #f0f0f0;">'
        html += f'<p style="font-weight:600;font-size:13px;color:#18181b;margin:0 0 4px;">{event}</p>'
        if tags:
            html += '<p style="margin:0;">' + " ".join(f'<span style="font-size:9px;color:{tag_color};">#{t}</span>' for t in tags) + '</p>'
        html += '</td></tr>'
    html += '</table>'
    return html


def build_editors_note_html(p1: str, p2: str, p3: str, ps: str = "", lang: str = "kr") -> str:
    """Vol.1 스타일: 에디터 노트 + P.S."""
    header = "에디터 한마디" if lang == "kr" else "Editor's Note"
    ps_html = f'\n<p style="font-size:12px;line-height:1.6;color:#9d9282;margin:14px 0 0;font-style:italic;">P.S. {ps}</p>' if ps else ""
    return f"""<p style="font-size:20px;letter-spacing:-.3px;color:#2d2418;margin-top:14px;margin-bottom:20px;">{header}</p>
<p style="font-size:14px;line-height:1.8;color:#3d3428;margin:0 0 14px;">{p1}</p>
<p style="font-size:14px;line-height:1.8;color:#3d3428;margin:0 0 14px;">{p2}</p>
<p style="font-size:13px;line-height:1.6;color:#7d7262;margin:0;">{p3}</p>{ps_html}"""


def build_next_week_html(items: list) -> str:
    html = '<table style="width:100%;border-collapse:collapse;margin-top:10px;">'
    colors = ["#ef4444", "#f59e0b", "#f59e0b"]
    for i, item in enumerate(items[:3]):
        c = colors[i] if i < len(colors) else "#94a3b8"
        html += f'<tr><td style="padding:4px 0;"><span style="display:inline-block;width:6px;height:6px;background:{c};border-radius:50%;vertical-align:middle;margin-right:8px;"></span>'
        html += f'<span style="font-size:13px;color:#52525b;">{item}</span></td></tr>'
    html += '</table>'
    return html


def build_travel_html(advisories: list, lang: str) -> str:
    is_kr = lang == "kr"
    l4 = [a for a in advisories if a["level"] >= 4]
    l3 = [a for a in advisories if a["level"] == 3]
    new_badge = '<span style="background:#dc2626;color:white;font-size:8px;font-weight:700;padding:1px 4px;border-radius:3px;margin-left:2px;vertical-align:middle;">NEW</span>'
    html = []

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
        html.append(f'''<table style="width:100%;border-radius:8px;background:#fef2f2;border:1px solid #fecaca;"><tr><td style="padding:14px 16px;">
<table style="width:100%;"><tr><td><span style="display:inline-block;font-weight:700;font-size:9px;border-radius:3px;letter-spacing:.5px;padding:2px 6px;background:#dc2626;color:white;">LEVEL 4</span></td>
<td align="right"><span style="font-weight:800;color:#dc2626;font-size:22px;">{len(l4)}</span><span style="font-size:12px;color:#dc2626;">{"개국" if is_kr else ""}</span></td></tr></table>
<p style="font-weight:700;font-size:12px;color:#dc2626;margin:6px 0;">{"여행 금지" if is_kr else "Do Not Travel"}</p>
<p style="font-size:11px;line-height:1.6;color:#7f1d1d;margin:0;">{names}</p>{new_line}
</td></tr></table>''')
    if l3:
        names = ", ".join(_name_with_badge(a) for a in l3[:30])
        new_l3 = [a for a in l3 if a.get("new")]
        new_line = ""
        if new_l3:
            new_names = ", ".join(cn(a["cc"], lang) for a in new_l3[:5])
            new_line = f'<p style="font-size:10px;color:#b45309;margin:6px 0 0;font-weight:600;">(+{len(new_l3)}: {new_names})</p>'
        html.append(f'''<table style="width:100%;border-radius:8px;background:#fffbeb;border:1px solid #fde68a;margin-top:12px;"><tr><td style="padding:14px 16px;">
<table style="width:100%;"><tr><td><span style="display:inline-block;font-weight:700;font-size:9px;border-radius:3px;letter-spacing:.5px;padding:2px 6px;background:#b45309;color:white;">LEVEL 3</span></td>
<td align="right"><span style="font-weight:800;color:#b45309;font-size:22px;">{len(l3)}</span><span style="font-size:12px;color:#b45309;">{"개국" if is_kr else ""}</span></td></tr></table>
<p style="font-weight:700;font-size:12px;color:#92400e;margin:6px 0;">{"여행 재고" if is_kr else "Reconsider Travel"}</p>
<p style="font-size:11px;line-height:1.6;color:#78350f;margin:0;">{names}</p>{new_line}
</td></tr></table>''')
    return "\n".join(html)


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
        top_clusters = [(row.title, row.title_ko, row.country_code, row.severity, row.kscore, row.event_count, row.image_url) for row in r.fetchall()]
        data["conflict_stories_html"] = build_conflict_stories_html(top_clusters, lang, vol=vol)

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
            ), {"s": sym, "cutoff": cutoff_date.date()})
            row = r.fetchone()
            if row:
                if target in ("oil", "oil_brent") and oil_price_past is None:
                    oil_price_past = float(row.price_usd)
                elif target == "wheat":
                    wheat_price_past = float(row.price_usd)

        oil_change_period = ((oil_price - oil_price_past) / oil_price_past * 100) if oil_price and oil_price_past else None
        wheat_change_period = ((wheat_price - wheat_price_past) / wheat_price_past * 100) if wheat_price and wheat_price_past else None

        # ── 여행경보 ──
        r = await db.execute(text("SELECT DISTINCT ON (country_code) country_code, level, updated_at FROM travel_advisory WHERE level >= 3 ORDER BY country_code, updated_at DESC"))
        advisories = [{"cc": row.country_code, "level": row.level, "new": row.updated_at >= seven_days_ago if row.updated_at else False} for row in r.fetchall()]
        travel_l4 = len([a for a in advisories if a["level"] >= 4])
        travel_l3 = len([a for a in advisories if a["level"] == 3])
        data["travel_advisory_html"] = build_travel_html(advisories, lang)
        data["travel_advisory_intro_html"] = (
            f"여행 금지 {travel_l4}개국, 여행 재고 {travel_l3}개국." if is_kr
            else f"Do Not Travel: {travel_l4} countries. Reconsider: {travel_l3}."
        )

        # ── country_issues (DB 기반) ──
        r = await db.execute(text("""
            SELECT title, title_ko, event_count FROM issue_clusters
            WHERE is_active = true AND country_code = :cc
            ORDER BY event_count DESC LIMIT 5
        """), {"cc": target_cc})
        country_issues_rows = [(row.title, row.title_ko, row.event_count) for row in r.fetchall()]

        # ── 전주 이벤트 수 (numbers 변동률용) ──
        prev_week_start = seven_days_ago - timedelta(days=7)
        prev_24h_start = twenty_four_hours_ago - timedelta(days=7)
        prev_24h_end = twenty_four_hours_ago - timedelta(days=6)
        r = await db.execute(text("SELECT COUNT(*) FROM normalized_events WHERE event_time >= :s AND event_time < :e"), {"s": prev_24h_start, "e": prev_24h_end})
        events_24h_prev = r.scalar() or 0
        r = await db.execute(text("SELECT COUNT(*) FROM normalized_events WHERE event_time >= :s AND event_time < :e"), {"s": prev_week_start, "e": seven_days_ago})
        events_7d_prev = r.scalar() or 0

        # ── 평균 event_count (하이라이트 라인용) ──
        r = await db.execute(text("SELECT AVG(event_count) FROM issue_clusters WHERE is_active = true AND event_count > 0"))
        avg_event_count = r.scalar() or 1

    # ── GPT 편집 콘텐츠 ──
    def cl_title(c, i=0):
        if not c or i >= len(c): return "N/A"
        t, tko = c[i][0], c[i][1]
        return (tko or t) if is_kr else (t or tko)

    def cl_cc(c, i=0): return cn(c[i][2], lang) if c and i < len(c) else "N/A"
    def cl_ev(c, i=0): return c[i][5] if c and i < len(c) else 0
    def cl_img(c, i=0): return c[i][6] if c and i < len(c) and c[i][6] else ""

    tension_top3 = ", ".join(f"{cn(cc, lang)} {s:.0f}" for cc, s in sorted_tension[:3])

    gpt_ctx = {
        "top_story": cl_title(top_clusters, 0), "top_cc": cl_cc(top_clusters, 0),
        "top_events": cl_ev(top_clusters, 0), "top_sev": top_clusters[0][3] if top_clusters else 0,
        "story_2": cl_title(top_clusters, 1), "story_2_cc": cl_cc(top_clusters, 1), "story_2_events": cl_ev(top_clusters, 1),
        "story_3": cl_title(top_clusters, 2), "story_3_cc": cl_cc(top_clusters, 2), "story_3_events": cl_ev(top_clusters, 2),
        "tension_top3": tension_top3,
        "target_name": cn(target_cc, lang), "target_tension": f"{target_score:.1f}",
        "target_rank": data["country_rank"], "target_delta": data["tension_change"],
        "oil_price": f"{oil_price:.1f}" if oil_price else "N/A",
        "oil_change": f"{oil_change:+.1f}" if oil_change is not None else "N/A",
        "wheat_price": f"{wheat_price:.1f}" if wheat_price else "N/A",
        "wheat_change": f"{wheat_change:+.1f}" if wheat_change is not None else "N/A",
        "crisis_count": crisis_count, "crisis_prev": crisis_prev,
        "events_24h": events_24h, "events_7d": events_7d,
        "travel_l4": travel_l4, "travel_l3": travel_l3,
        "oil_price_past": f"{oil_price_past:.1f}" if oil_price_past else "N/A",
        "oil_change_period": f"{oil_change_period:+.1f}" if oil_change_period is not None else "N/A",
        "energy_period": energy_label, "energy_days": energy_days,
    }

    print("  GPT 편집 콘텐츠 생성 중...")
    ed = await generate_editorial(gpt_ctx, lang, vol=vol)

    # ── HTML 조립 ──
    hero_raw = ed.get("hero_headline", cl_title(top_clusters, 0))
    data["hero_headline_html"] = hero_raw.replace("\n", "<br>\n")
    data["preheader_text"] = ed.get("preheader", "")

    # key_stats_line — 데이터 직접 빌드
    top_cc_name = cl_cc(top_clusters, 0) if top_clusters else "N/A"
    top_cc_ev = cl_ev(top_clusters, 0) if top_clusters else 0
    oil_str = f"${oil_price:.0f}" if oil_price else "N/A"
    oil_ch = f"{oil_change:+.0f}%" if oil_change is not None else ""
    data["key_stats_line"] = (
        f'핵심: <span class="w6 ce">{top_cc_name} {top_cc_ev:,}건</span> · '
        f'<span class="w6 cy">유가 {oil_str}</span>({oil_ch}) · '
        f'<span class="w6 cx">{cn(target_cc, lang)} {target_score:.1f}</span>'
    ) if is_kr else (
        f'Key: <span class="w6 ce">{top_cc_name} {top_cc_ev:,} events</span> · '
        f'<span class="w6 cy">Oil {oil_str}</span>({oil_ch}) · '
        f'<span class="w6 cx">{cn(target_cc, lang)} {target_score:.1f}</span>'
    )

    # Today's brief
    briefs = [
        (ed.get("brief_1_title", ""), ed.get("brief_1_desc", "")),
        (ed.get("brief_2_title", ""), ed.get("brief_2_desc", "")),
        (ed.get("brief_3_title", ""), ed.get("brief_3_desc", "")),
    ]
    data["todays_brief_items_html"] = build_todays_brief_html(briefs, lang)

    # Energy
    data["energy_section_intro_html"] = ed.get("energy_intro", "")
    data["energy_section_html"] = build_energy_html(
        ed.get("energy_intro", ""), ed.get("energy_p1", ""),
        ed.get("energy_p2", ""), ed.get("energy_p3", ""),
        oil_price, oil_change, lang
    )

    # Deep dive
    data["deep_dive_nav_label"] = ed.get("deep_dive_title", "")[:30]
    data["deep_dive_title"] = ed.get("deep_dive_title", "")
    data["deep_dive_section_html"] = build_deep_dive_html(
        ed.get("deep_dive_title", ""),
        ed.get("deep_dive_p1", ""), ed.get("deep_dive_p2", ""),
        ed.get("deep_dive_p3", ""), ed.get("deep_dive_p4", ""),
        ed.get("deep_dive_why", ""), lang
    )

    # Numbers
    top_cc_data = top_clusters[0] if top_clusters else None
    wow_rows = [
        ("위기 국가" if is_kr else "Crisis", str(crisis_prev), str(crisis_count),
         f"+{diff}" if diff > 0 else str(diff)),
    ]
    if oil_price and oil_change:
        prev_oil = oil_price / (1 + oil_change/100) if oil_change != 0 else oil_price
        wow_rows.append(("유가(WTI)" if is_kr else "Oil(WTI)",
                         f"${prev_oil:.0f}", f"${oil_price:.0f}", f"{oil_change:+.0f}%"))
    if target_score:
        wow_rows.append((f"{cn(target_cc, lang)} 긴장도" if is_kr else f"{cn(target_cc, lang)} Tension",
                         f"{target_prev:.1f}", f"{target_score:.1f}", data["tension_change"]))

    # 하이라이트 라인 계산
    highlight_line = None
    if top_clusters and avg_event_count > 0:
        top_ev = top_clusters[0][5]
        ratio = top_ev / avg_event_count
        if ratio >= 2:
            top_name = cl_title(top_clusters, 0)
            if is_kr:
                highlight_line = f"{top_name} {top_ev:,}건은 평소 {avg_event_count:.0f}건 대비 {ratio:.1f}배"
            else:
                highlight_line = f"{top_name}: {top_ev:,} events = {ratio:.1f}x the average ({avg_event_count:.0f})"

    data["numbers_section_html"] = build_numbers_html({
        "events_24h": events_24h, "events_7d": events_7d,
        "events_7d_raw": events_7d if isinstance(events_7d, int) else int(str(events_7d).replace(",", "")),
        "events_24h_prev": events_24h_prev, "events_7d_prev": events_7d_prev,
        "crisis_count": crisis_count, "active_issues": active_issues,
        "top_cc_events": top_cc_ev, "top_cc_name": top_cc_name,
        "wow_rows": wow_rows, "highlight": highlight_line,
    }, lang)

    # Country impact
    steps = [ed.get(f"impact_{i}", "") for i in range(1, 5)]
    data["country_impact_html"] = build_country_impact_html(steps, lang)

    # Country issues (DB 기반)
    issues = []
    for title, title_ko, ev_count in country_issues_rows:
        display = (title_ko or title) if is_kr else (title or title_ko)
        issues.append((display, "", ev_count or 0))
    data["country_issues_html"] = build_country_issues_html(issues, lang)

    # Did you know
    data["did_you_know_html"] = f'<p style="font-size:12px;line-height:1.6;color:#52525b;margin:0;">{ed.get("did_you_know", "")}</p>'

    # Editors note
    data["editors_note_html"] = build_editors_note_html(
        ed.get("editors_note_p1", ""), ed.get("editors_note_p2", ""), ed.get("editors_note_p3", ""),
        ps=ed.get("editors_ps", ""), lang=lang)

    # Next week
    data["next_week_items_html"] = build_next_week_html([
        ed.get("next_week_1", ""), ed.get("next_week_2", ""), ed.get("next_week_3", "")])

    # Calendar — 실제 날짜 + GPT 태그 (P2-4)
    cal_days = []
    for i in range(4):
        dt = now + timedelta(days=i)
        event = ed.get(f"calendar_{i+1}_event", "")
        raw_tags = ed.get(f"calendar_{i+1}_tags", "")
        if isinstance(raw_tags, list):
            tags = raw_tags
        elif isinstance(raw_tags, str) and raw_tags:
            tags = [t.strip() for t in raw_tags.replace("/", ",").split(",") if t.strip()]
        else:
            tags = []
        cal_days.append((dt, event, tags))
    # P3-5: 태그 색상 회전
    tag_colors = ["#dc2626", "#b45309", "#059669"]
    cal_tag_color = tag_colors[vol % 3]
    data["calendar_html"] = build_calendar_html(cal_days, lang, tag_color=cal_tag_color)

    # Share, CTA, etc.
    data["share_headline"] = ed.get("share_headline", "")
    data["share_subtext"] = ed.get("share_subtext", "")
    data["pro_cta_headline_html"] = ed.get("pro_cta_headline", "")
    data["pro_cta_subtext"] = ed.get("pro_cta_subtext", "")
    data["tension_warning_html"] = f'<b>{"이상 신호:" if is_kr else "Warning:"}</b> {ed.get("tension_warning", "")}'

    # Country summary
    data["country_summary"] = ed.get("deep_dive_why", "")[:200]
    data["streak_text"] = ""

    # 고정값
    data["hero_image_url"] = cl_img(top_clusters, 0)
    data["hero_subheadline_html"] = ""
    data["deep_dive_image_url"] = cl_img(top_clusters, 0)
    data["banner_image_url"] = ""
    data["map_snapshot_url"] = ""
    data["og_image_url"] = ""
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
    args = parser.parse_args()

    print(f"=== Newsletter Vol.{args.vol} ({args.lang}) ===")
    data = await generate(args.vol, args.lang)

    import redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(redis_url, decode_responses=True)
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
