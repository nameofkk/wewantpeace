"""기자 이메일 CSV → 발송용 CSV 변환 스크립트"""
import csv
import html

# 매체별 추천 템플릿 + 제목
TEMPLATE_MAP = {
    "연합뉴스": ("A", "195개국 분쟁 실시간 모니터링 — 취재 참고 도구 공유"),
    "한겨레":   ("A", "195개국 분쟁 실시간 모니터링 — 취재 참고 도구 공유"),
    "중앙일보": ("A", "195개국 분쟁 실시간 모니터링 — 취재 참고 도구 공유"),
    "조선일보": ("A", "195개국 분쟁 실시간 모니터링 — 취재 참고 도구 공유"),
    "동아일보": ("A", "195개국 분쟁 실시간 모니터링 — 취재 참고 도구 공유"),
    "매일경제": ("B", "분쟁 리스크가 한국 경제에 미치는 영향, 실시간 수치로 봅니다"),
    "한국경제": ("B", "분쟁 리스크가 한국 경제에 미치는 영향, 실시간 수치로 봅니다"),
    "헤럴드경제": ("B", "분쟁 리스크가 한국 경제에 미치는 영향, 실시간 수치로 봅니다"),
    "아시아경제": ("B", "분쟁 리스크가 한국 경제에 미치는 영향, 실시간 수치로 봅니다"),
    "전자신문": ("C", "플레이스토어 뉴스 1위 앱 — 스타트업 출신 개발자의 분쟁 모니터링 서비스"),
}

INPUT = "docs/journalist-emails.csv"
OUTPUT = "docs/marketing/cold-email-send-list.csv"

rows = []
with open(INPUT, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader, 1):
        매체 = row["매체"].strip()
        이름 = row["이름"].strip()
        이메일 = row["이메일"].strip()
        대표기사 = html.unescape(row.get("대표기사", "").strip())

        # 공용 계정 스킵
        if "공용" in 이름 or not 이메일:
            continue

        tpl, subject = TEMPLATE_MAP.get(매체, ("A", "195개국 분쟁 실시간 모니터링 — 취재 참고 도구 공유"))

        # 이름 없는 경우 (전자신문 등) 비고에 표시
        비고 = ""
        if not 이름:
            비고 = "이름 없음 - 발송 전 확인 필요"

        rows.append({
            "순번": len(rows) + 1,
            "매체": 매체,
            "이름": 이름,
            "이메일": 이메일,
            "추천템플릿": tpl,
            "제목": subject,
            "대표기사": 대표기사,
            "비고": 비고,
        })

with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["순번", "매체", "이름", "이메일", "추천템플릿", "제목", "대표기사", "비고"])
    writer.writeheader()
    writer.writerows(rows)

print(f"완료: {len(rows)}명 (공용계정 제외)")
print(f"출력: {OUTPUT}")

# 매체별 통계
from collections import Counter
stats = Counter(r["매체"] for r in rows)
for 매체, cnt in stats.most_common():
    tpl = TEMPLATE_MAP.get(매체, ("A",))[0]
    print(f"  {매체}: {cnt}명 (템플릿 {tpl}안)")
