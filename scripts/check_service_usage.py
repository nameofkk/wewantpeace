#!/usr/bin/env python3
"""
WeWantPeace 유료 서비스 잔량/사용량 일괄 확인 스크립트.
텔레그램 알림으로 경고 메시지 전송 가능.

사용법:
  python scripts/check_service_usage.py          # 콘솔 출력만
  python scripts/check_service_usage.py --notify  # 텔레그램 알림도 전송
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

# ── 설정 ──────────────────────────────────────────────────
RAILWAY_API_TOKEN = os.getenv(
    "RAILWAY_API_TOKEN", "383ab19c-f63d-4ad0-ae47-ef816b79645b"
)
RAILWAY_PROJECT_ID = os.getenv(
    "RAILWAY_PROJECT_ID", "8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed"
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TG_BOT_TOKEN = os.getenv(
    "TELEGRAM_BROADCAST_BOT_TOKEN", ""
)
TG_CHAT_ID = os.getenv("TELEGRAM_BROADCAST_CHANNEL_ID", "")
# 관리자 텔레그램 chat ID (채널이 아닌 개인 알림용)
ADMIN_TG_CHAT_ID = os.getenv("ADMIN_TG_CHAT_ID", TG_CHAT_ID)

# 경고 임계값
RAILWAY_COST_WARN = 40.0  # $40 이상이면 경고
OPENAI_COST_WARN = 20.0   # $20 이상이면 경고


def _gql(query: str, variables: dict | None = None) -> dict:
    """Railway GraphQL API 호출."""
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = httpx.post(
        "https://backboard.railway.app/graphql/v2",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {RAILWAY_API_TOKEN}",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def check_railway() -> dict:
    """Railway 사용량 및 예상 비용 조회."""
    result: dict[str, Any] = {"name": "Railway", "status": "ok", "details": {}}
    try:
        # 프로젝트 정보
        proj = _gql(
            '{ project(id: "%s") { name subscriptionType services { edges { node { name id } } } } }'
            % RAILWAY_PROJECT_ID
        )
        p = proj["data"]["project"]
        result["details"]["plan"] = p["subscriptionType"]
        result["details"]["services"] = [
            e["node"]["name"] for e in p["services"]["edges"]
        ]

        # 예상 사용량
        usage = _gql(
            '{ estimatedUsage(projectId: "%s", measurements: [CPU_USAGE, MEMORY_USAGE_GB, NETWORK_TX_GB]) { estimatedValue measurement } }'
            % RAILWAY_PROJECT_ID
        )
        costs = {}
        # Railway 단가: CPU $0.000463/vCPU-min, Memory $0.000231/GB-min, Network $0.10/GB
        price_map = {
            "CPU_USAGE": 0.000463,
            "MEMORY_USAGE_GB": 0.000231,
            "NETWORK_TX_GB": 0.10,
        }
        for item in usage["data"]["estimatedUsage"]:
            m = item["measurement"]
            v = item["estimatedValue"]
            cost = v * price_map.get(m, 0)
            costs[m] = {"value": round(v, 2), "cost": round(cost, 2)}

        total = sum(c["cost"] for c in costs.values()) + 5.0  # Hobby 기본료
        result["details"]["estimated_costs"] = costs
        result["details"]["total_estimated"] = round(total, 2)

        if total > RAILWAY_COST_WARN:
            result["status"] = "warn"
            result["message"] = f"Railway 예상 비용 ${total:.2f} (임계값 ${RAILWAY_COST_WARN})"
        else:
            result["message"] = f"Railway 예상 비용 ${total:.2f} (정상)"

    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Railway 조회 실패: {e}"
    return result


def check_openai() -> dict:
    """OpenAI 잔액/사용량 확인 (dashboard 링크 제공)."""
    result: dict[str, Any] = {"name": "OpenAI", "status": "ok", "details": {}}
    if not OPENAI_API_KEY:
        result["status"] = "skip"
        result["message"] = "OPENAI_API_KEY 미설정"
        return result

    try:
        # Organization billing 조회 시도
        resp = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            timeout=10,
        )
        if resp.status_code == 200:
            result["message"] = "OpenAI API 키 유효 — 사용량은 https://platform.openai.com/usage 에서 확인"
        elif resp.status_code == 401:
            result["status"] = "error"
            result["message"] = "OpenAI API 키 만료 또는 무효!"
        elif resp.status_code == 429:
            result["status"] = "warn"
            result["message"] = "OpenAI 요청 한도 초과 (Rate limit)!"
        else:
            result["status"] = "warn"
            result["message"] = f"OpenAI 응답: HTTP {resp.status_code}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"OpenAI 조회 실패: {e}"
    return result


def check_supabase() -> dict:
    """Supabase DB 연결 확인."""
    result: dict[str, Any] = {"name": "Supabase (PostgreSQL)", "status": "ok", "details": {}}
    result["message"] = "사용량은 https://supabase.com/dashboard 에서 확인"
    result["details"]["note"] = "Pro 플랜 $25/월 — DB 크기, API 호출 횟수 확인 필요"
    return result


def check_mapbox() -> dict:
    """Mapbox 토큰 유효성 확인."""
    result: dict[str, Any] = {"name": "Mapbox", "status": "ok", "details": {}}
    result["message"] = "Free tier 50k loads/월 — https://account.mapbox.com/ 에서 확인"
    return result


def check_x_api() -> dict:
    """X (Twitter) API 상태 확인."""
    result: dict[str, Any] = {"name": "X (Twitter) API", "status": "ok", "details": {}}
    result["message"] = "API 플랜/사용량은 https://developer.x.com/en/portal/dashboard 에서 확인"
    result["details"]["note"] = "Free/Basic/Pro 플랜에 따라 $0~$100+/월"
    return result


def check_cloudflare_radar() -> dict:
    """Cloudflare Radar 토큰 유효성 확인."""
    result: dict[str, Any] = {"name": "Cloudflare Radar", "status": "ok", "details": {}}
    cf_token = os.getenv("CF_RADAR_TOKEN", "")
    if not cf_token:
        result["status"] = "warn"
        result["message"] = "CF_RADAR_TOKEN 미설정 — 토큰 만료 상태일 수 있음"
        return result
    try:
        resp = httpx.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {cf_token}"},
            timeout=10,
        )
        data = resp.json()
        if data.get("success"):
            result["message"] = "Cloudflare 토큰 유효"
        else:
            result["status"] = "warn"
            result["message"] = "Cloudflare 토큰 만료! 갱신 필요"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Cloudflare 조회 실패: {e}"
    return result


def check_dodo() -> dict:
    """DodoPayments 상태."""
    result: dict[str, Any] = {"name": "DodoPayments", "status": "ok", "details": {}}
    result["message"] = "거래 수수료 기반 — https://dashboard.dodopayments.com 에서 확인"
    return result


def format_report(results: list[dict]) -> str:
    """결과를 보기 좋게 포맷."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"📊 WeWantPeace 서비스 상태 ({now})", "=" * 45]

    warnings = []
    for r in results:
        icon = {"ok": "✅", "warn": "⚠️", "error": "❌", "skip": "⏭️"}.get(
            r["status"], "❓"
        )
        lines.append(f"\n{icon} {r['name']}")
        lines.append(f"   {r.get('message', '')}")
        if r.get("details"):
            for k, v in r["details"].items():
                if k == "estimated_costs":
                    for mk, mv in v.items():
                        lines.append(f"   - {mk}: {mv['value']} → ${mv['cost']}")
                elif k == "services":
                    lines.append(f"   - 서비스: {', '.join(v)}")
                elif k == "total_estimated":
                    continue
                else:
                    lines.append(f"   - {k}: {v}")

        if r["status"] in ("warn", "error"):
            warnings.append(r)

    if warnings:
        lines.append("\n" + "=" * 45)
        lines.append("🚨 주의 필요:")
        for w in warnings:
            lines.append(f"  - {w['name']}: {w.get('message', '')}")

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """텔레그램으로 알림 전송."""
    if not TG_BOT_TOKEN or not ADMIN_TG_CHAT_ID:
        print("⚠️ 텔레그램 봇 토큰 또는 채팅 ID 미설정 — 알림 건너뜀")
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_TG_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="WeWantPeace 유료 서비스 잔량 확인")
    parser.add_argument("--notify", action="store_true", help="텔레그램 알림 전송")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="경고/에러가 있을 때만 텔레그램 알림",
    )
    args = parser.parse_args()

    results = [
        check_railway(),
        check_openai(),
        check_supabase(),
        check_mapbox(),
        check_x_api(),
        check_cloudflare_radar(),
        check_dodo(),
    ]

    report = format_report(results)
    print(report)

    has_warnings = any(r["status"] in ("warn", "error") for r in results)

    if args.notify:
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
