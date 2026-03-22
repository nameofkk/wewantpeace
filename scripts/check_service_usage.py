#!/usr/bin/env python3
"""
WeWantPeace 유료 서비스 잔량/사용량 일괄 확인 + 텔레그램 경고 알림.

크레딧 잔액이 임계값 이하로 떨어지면 텔레그램으로 경고 전송.

사용법:
  python scripts/check_service_usage.py              # 콘솔 출력만
  python scripts/check_service_usage.py --notify      # 항상 텔레그램 알림
  python scripts/check_service_usage.py --warn-only   # 경고 있을 때만 알림
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

# ── Railway 설정 ──────────────────────────────────────────
RAILWAY_API_TOKEN = os.getenv(
    "RAILWAY_API_TOKEN", "383ab19c-f63d-4ad0-ae47-ef816b79645b"
)
RAILWAY_PROJECT_ID = os.getenv(
    "RAILWAY_PROJECT_ID", "8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed"
)
RAILWAY_WORKSPACE_ID = os.getenv(
    "RAILWAY_WORKSPACE_ID", "5d103fc9-0153-4221-b9f1-829a9932ff73"
)

# ── OpenAI (worker에서 가져옴) ────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── 텔레그램 알림 설정 ───────────────────────────────────
TG_BOT_TOKEN = os.getenv(
    "SOCIAL_TG_BOT_TOKEN", "8797103470:AAGmkofyFZZyxELIS3Id28jlMJPyjJSewp8"
)
TG_CHAT_ID = os.getenv("ADMIN_TG_CHAT_ID", "-1003790789028")

# ── 경고 임계값 ──────────────────────────────────────────
RAILWAY_CREDIT_WARN = 3.0    # 크레딧 $3 이하 → 경고
RAILWAY_CREDIT_DANGER = 1.0  # 크레딧 $1 이하 → 위험
RAILWAY_USAGE_WARN = 30.0    # 월 사용량 $30 이상 → 경고


def _gql(query: str) -> dict:
    """Railway GraphQL API 호출."""
    resp = httpx.post(
        "https://backboard.railway.app/graphql/v2",
        json={"query": query},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {RAILWAY_API_TOKEN}",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(data["errors"][0]["message"])
    return data


def check_railway() -> dict:
    """Railway 크레딧 잔액 + 사용량 + 예상 비용."""
    result: dict[str, Any] = {"name": "Railway", "status": "ok", "details": {}}
    try:
        # 1) 크레딧 잔액 & 현재 사용량
        billing = _gql(
            '{ workspace(workspaceId: "%s") { customer { '
            "creditBalance remainingUsageCreditBalance currentUsage "
            "isPrepaying state billingPeriod { start end } "
            "usageLimit { hardLimit softLimit } "
            "} } }" % RAILWAY_WORKSPACE_ID
        )
        c = billing["data"]["workspace"]["customer"]
        credit = c["creditBalance"]
        usage_credit = c["remainingUsageCreditBalance"]
        current_usage = c["currentUsage"]
        state = c["state"]
        period_start = c["billingPeriod"]["start"][:10]
        period_end = c["billingPeriod"]["end"][:10]
        limit = c.get("usageLimit")
        hard_limit = limit["hardLimit"] if limit else None
        soft_limit = limit["softLimit"] if limit else None

        result["details"]["credit_balance"] = f"${credit:.2f}"
        result["details"]["usage_credit"] = f"${usage_credit:.2f}"
        result["details"]["current_usage"] = f"${current_usage:.2f}"
        result["details"]["billing_period"] = f"{period_start} ~ {period_end}"
        result["details"]["state"] = state
        if hard_limit:
            result["details"]["hard_limit"] = f"${hard_limit:.2f}"
        if soft_limit:
            result["details"]["soft_limit"] = f"${soft_limit:.2f}"

        # 2) 예상 월간 비용
        est = _gql(
            '{ estimatedUsage(projectId: "%s", measurements: '
            "[CPU_USAGE, MEMORY_USAGE_GB, NETWORK_TX_GB]) "
            "{ estimatedValue measurement } }" % RAILWAY_PROJECT_ID
        )
        price_map = {
            "CPU_USAGE": 0.000463,
            "MEMORY_USAGE_GB": 0.000231,
            "NETWORK_TX_GB": 0.10,
        }
        total_est = 5.0  # Hobby 기본료
        for item in est["data"]["estimatedUsage"]:
            m = item["measurement"]
            v = item["estimatedValue"]
            total_est += v * price_map.get(m, 0)
        result["details"]["estimated_monthly"] = f"${total_est:.2f}"

        # 3) 서비스 목록
        proj = _gql(
            '{ project(id: "%s") { services { edges { node { name } } } } }'
            % RAILWAY_PROJECT_ID
        )
        svcs = [e["node"]["name"] for e in proj["data"]["project"]["services"]["edges"]]
        result["details"]["services"] = ", ".join(svcs)

        # 4) 경고 판단
        warnings = []
        if credit <= RAILWAY_CREDIT_DANGER:
            warnings.append(f"🔴 크레딧 잔액 ${credit:.2f} — 위험!")
            result["status"] = "error"
        elif credit <= RAILWAY_CREDIT_WARN:
            warnings.append(f"🟡 크레딧 잔액 ${credit:.2f} — 충전 권장")
            result["status"] = "warn"

        if total_est > RAILWAY_USAGE_WARN:
            warnings.append(f"🟡 예상 월 비용 ${total_est:.2f}")
            if result["status"] == "ok":
                result["status"] = "warn"

        if warnings:
            result["message"] = " | ".join(warnings)
        else:
            result["message"] = (
                f"크레딧 ${credit:.2f}, "
                f"이번 달 ${current_usage:.2f} 사용, "
                f"예상 ${total_est:.2f}/월"
            )

    except Exception as e:
        result["status"] = "error"
        result["message"] = f"조회 실패: {e}"
    return result


def check_openai() -> dict:
    """OpenAI API 키 유효성 + 상태 확인."""
    result: dict[str, Any] = {"name": "OpenAI (GPT-4o-mini)", "status": "ok", "details": {}}

    # worker의 env에서 가져올 수 있으면 가져옴
    api_key = OPENAI_API_KEY
    if not api_key:
        try:
            data = _gql(
                '{ variables(projectId: "%s", environmentId: "92d7e229-1071-4b32-a12c-8336ef7be7d5",'
                ' serviceId: "2ee51089-125e-4e77-95e8-0fc3b8935ec5") }' % RAILWAY_PROJECT_ID
            )
            api_key = data["data"]["variables"].get("OPENAI_API_KEY", "")
        except Exception:
            pass

    if not api_key:
        result["status"] = "skip"
        result["message"] = "API 키 미확인"
        return result

    try:
        resp = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            result["message"] = "API 키 정상 — 잔액은 platform.openai.com/usage 확인"
        elif resp.status_code == 401:
            result["status"] = "error"
            result["message"] = "API 키 만료/무효! 즉시 확인 필요"
        elif resp.status_code == 429:
            result["status"] = "warn"
            result["message"] = "Rate limit 초과 또는 잔액 소진!"
        else:
            result["status"] = "warn"
            result["message"] = f"HTTP {resp.status_code} — 확인 필요"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"연결 실패: {e}"
    return result


def check_supabase() -> dict:
    """Supabase DB 연결 상태 확인."""
    result: dict[str, Any] = {"name": "Supabase (DB)", "status": "ok", "details": {}}
    try:
        # Supabase REST API health check
        resp = httpx.get(
            "https://smxitufpgfuzepldglfo.supabase.co/rest/v1/",
            headers={"apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.placeholder"},
            timeout=10,
        )
        # 401도 서버 응답이면 살아있는 것
        if resp.status_code in (200, 401, 403):
            result["message"] = "서버 응답 정상 — 잔액은 supabase.com/dashboard 확인"
        else:
            result["status"] = "warn"
            result["message"] = f"HTTP {resp.status_code} — 확인 필요"
    except Exception:
        result["status"] = "error"
        result["message"] = "Supabase 연결 실패!"
    return result


def check_cloudflare_radar() -> dict:
    """Cloudflare Radar 토큰 상태."""
    result: dict[str, Any] = {"name": "Cloudflare Radar", "status": "ok", "details": {}}
    try:
        data = _gql(
            '{ variables(projectId: "%s", environmentId: "92d7e229-1071-4b32-a12c-8336ef7be7d5",'
            ' serviceId: "2ee51089-125e-4e77-95e8-0fc3b8935ec5") }' % RAILWAY_PROJECT_ID
        )
        cf_token = data["data"]["variables"].get("CF_RADAR_TOKEN", "")
    except Exception:
        cf_token = os.getenv("CF_RADAR_TOKEN", "")

    if not cf_token:
        result["status"] = "warn"
        result["message"] = "토큰 미설정"
        return result

    try:
        resp = httpx.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {cf_token}"},
            timeout=10,
        )
        data = resp.json()
        if data.get("success"):
            result["message"] = "토큰 유효"
        else:
            result["status"] = "warn"
            result["message"] = "토큰 만료! 갱신 필요"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"확인 실패: {e}"
    return result


def check_backend_health() -> dict:
    """백엔드 API 헬스체크."""
    result: dict[str, Any] = {"name": "Backend API", "status": "ok", "details": {}}
    try:
        resp = httpx.get(
            "https://backend-production-3af7.up.railway.app/health",
            timeout=10,
        )
        if resp.status_code == 200:
            result["message"] = "정상 응답"
        else:
            result["status"] = "warn"
            result["message"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"백엔드 다운! {e}"
    return result


def check_frontend_health() -> dict:
    """프론트엔드 상태 확인."""
    result: dict[str, Any] = {"name": "Frontend", "status": "ok", "details": {}}
    try:
        resp = httpx.get("https://www.wewantpeace.live/", timeout=10, follow_redirects=True)
        if resp.status_code == 200:
            result["message"] = "정상 응답"
        else:
            result["status"] = "warn"
            result["message"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"프론트엔드 다운! {e}"
    return result


# ── 리포트 포맷 & 텔레그램 전송 ─────────────────────────

def format_report(results: list[dict]) -> str:
    """콘솔 + 텔레그램용 텍스트 포맷."""
    from datetime import timedelta
    kst = timezone(timedelta(hours=9))
    now_str = datetime.now(kst).strftime("%m/%d %H:%M")

    warnings = []
    ok_items = []
    for r in results:
        if r["status"] in ("warn", "error"):
            warnings.append(r)
        else:
            ok_items.append(r)

    if warnings:
        verdict = f"{len(warnings)}개 항목에서 주의가 필요합니다."
    else:
        verdict = "모든 서비스 정상 가동 중입니다."

    lines = [
        "<b>서비스 잔량/상태 점검 보고</b>",
        f"{now_str} 기준",
        "",
        f"대표님, {len(results)}개 서비스 점검 결과를 보고 드립니다. {verdict}",
    ]

    if warnings:
        lines.append("")
        lines.append("<b>[주의]</b>")
        for w in warnings:
            lines.append(f"  - {w['name']}: {w.get('message', '')}")
            details = w.get("details", {})
            for k in ("credit_balance", "current_usage", "estimated_monthly"):
                if k in details:
                    label = {"credit_balance": "크레딧", "current_usage": "사용량",
                             "estimated_monthly": "예상 비용"}.get(k, k)
                    lines.append(f"    {label}: {details[k]}")

    if ok_items:
        lines.append("")
        lines.append(f"<b>[정상]</b> {len(ok_items)}개: {', '.join(r['name'] for r in ok_items)}")

    lines.append("")
    lines.append("이상 보고 드립니다.")
    lines.append("<i>WeWantPeace 시스템 비서</i>")

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """텔레그램으로 알림 전송."""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ 텔레그램 설정 없음 — 알림 건너뜀")
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="WeWantPeace 유료 서비스 잔량 확인 & 텔레그램 경고"
    )
    parser.add_argument("--notify", action="store_true", help="텔레그램 알림 전송")
    parser.add_argument("--warn-only", action="store_true",
                        help="경고/에러가 있을 때만 텔레그램 알림 (--notify 암시)")
    args = parser.parse_args()

    results = [
        check_railway(),
        check_openai(),
        check_supabase(),
        check_cloudflare_radar(),
        check_backend_health(),
        check_frontend_health(),
    ]

    report = format_report(results)
    print(report)

    has_warnings = any(r["status"] in ("warn", "error") for r in results)

    should_notify = args.notify or args.warn_only
    if should_notify:
        if args.warn_only and not has_warnings:
            print("\n✅ 경고 없음 — 텔레그램 알림 건너뜀")
        else:
            print("\n📤 텔레그램 알림 전송 중...")
            if send_telegram(report):
                print("✅ 전송 완료")
            else:
                print("❌ 전송 실패")

    sys.exit(1 if has_warnings else 0)


if __name__ == "__main__":
    main()
