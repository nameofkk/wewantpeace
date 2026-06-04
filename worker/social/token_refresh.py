"""SNS 토큰 자동 갱신 — Threads (Meta Graph API).

Threads access token은 60일 만료. 매주 갱신하여 만료 방지.
갱신 성공 시 Railway 환경변수 업데이트 + 현재 프로세스 메모리 반영.
실패 시 Telegram 어드민 알림.
"""

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

# ── Railway GraphQL API ──────────────────────────────────────────────────────
RAILWAY_API_TOKEN = os.getenv(
    "RAILWAY_API_TOKEN", "383ab19c-f63d-4ad0-ae47-ef816b79645b"
)
RAILWAY_PROJECT_ID = "8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed"
RAILWAY_ENV_ID = "92d7e229-1071-4b32-a12c-8336ef7be7d5"
# worker 서비스 ID (THREADS_ACCESS_TOKEN이 바인딩된 서비스)
RAILWAY_WORKER_SERVICE_ID = "2ee51089-125e-4e77-95e8-0fc3b8935ec5"

# ── Telegram 어드민 알림 ─────────────────────────────────────────────────────
SOCIAL_TG_BOT_TOKEN = os.getenv("SOCIAL_TG_BOT_TOKEN", "")
SOCIAL_TG_CHAT_ID = os.getenv("SOCIAL_TG_CHAT_ID", "")

RAILWAY_GQL_URL = "https://backboard.railway.app/graphql/v2"

# Threads 토큰 갱신 API
THREADS_REFRESH_URL = "https://graph.threads.net/refresh_access_token"


async def _send_admin_alert(message: str) -> bool:
    """Telegram 어드민 채팅으로 경고 메시지 전송."""
    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        logger.warning("Telegram 봇 미설정, 어드민 알림 건너뜀")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": SOCIAL_TG_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            if resp.status_code == 200:
                return True
            logger.error("어드민 알림 전송 실패: %s", resp.text[:200])
            return False
    except Exception:
        logger.exception("어드민 알림 전송 예외")
        return False


async def _update_railway_env_var(name: str, value: str) -> bool:
    """Railway 환경변수를 GraphQL variableUpsert mutation으로 업데이트."""
    mutation = """
    mutation($input: VariableUpsertInput!) {
      variableUpsert(input: $input)
    }
    """
    variables = {
        "input": {
            "projectId": RAILWAY_PROJECT_ID,
            "environmentId": RAILWAY_ENV_ID,
            "serviceId": RAILWAY_WORKER_SERVICE_ID,
            "name": name,
            "value": value,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                RAILWAY_GQL_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {RAILWAY_API_TOKEN}",
                },
                json={"query": mutation, "variables": variables},
            )
            data = resp.json()
            if "errors" in data:
                logger.error("Railway 환경변수 업데이트 실패: %s", data["errors"])
                return False
            logger.info("Railway 환경변수 '%s' 업데이트 완료", name)
            return True
    except Exception:
        logger.exception("Railway GraphQL 호출 실패")
        return False


async def refresh_threads_token() -> dict:
    """Threads access token 갱신.

    Returns:
        {"status": "ok"|"skipped"|"error", "detail": str, "expires_in": int|None}
    """
    from worker.social.adapters import threads_adapter

    current_token = threads_adapter.THREADS_ACCESS_TOKEN
    if not current_token:
        detail = "THREADS_ACCESS_TOKEN 미설정, 갱신 건너뜀"
        logger.info(detail)
        return {"status": "skipped", "detail": detail, "expires_in": None}

    # Step 1: Meta Graph API로 토큰 갱신 요청 (최대 3회 재시도)
    resp = None
    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    THREADS_REFRESH_URL,
                    params={
                        "grant_type": "th_refresh_token",
                        "access_token": current_token,
                    },
                )
            if resp.status_code == 200:
                break
            last_error = f"HTTP {resp.status_code}"
            logger.warning("Threads 토큰 갱신 시도 %d/3 실패: %s", attempt + 1, last_error)
        except Exception as e:
            last_error = str(e)
            logger.warning("Threads 토큰 갱신 시도 %d/3 오류: %s", attempt + 1, e)
        if attempt < 2:
            await asyncio.sleep(5 * (attempt + 1))  # 5초, 10초 대기

    if resp is None or resp.status_code != 200:
        detail = f"Threads 토큰 갱신 3회 시도 실패: {last_error}"
        logger.error(detail)
        await _send_admin_alert(
            f"<b>긴급 보고: Threads 토큰 갱신 실패</b>\n"
            f"\n"
            f"대표님, Threads 토큰 갱신을 3회 시도했으나 모두 실패했습니다.\n"
            f"사유: {last_error}\n"
            f"\n"
            f"수동 갱신이 필요하오니 확인 부탁드립니다.\n"
            f"<i>WeWantPeace 시스템 비서</i>"
        )
        return {"status": "error", "detail": detail, "expires_in": None}

    data = resp.json()
    new_token = data.get("access_token")
    expires_in = data.get("expires_in")

    if not new_token:
        detail = f"응답에 access_token 누락: {data}"
        logger.error(detail)
        await _send_admin_alert(
            f"<b>긴급 보고: Threads 토큰 갱신 실패</b>\n"
            f"\n"
            f"대표님, Threads API 응답에 access_token이 누락되어 갱신에 실패했습니다.\n"
            f"수동 갱신이 필요하오니 확인 부탁드립니다.\n"
            f"<i>WeWantPeace 시스템 비서</i>"
        )
        return {"status": "error", "detail": detail, "expires_in": None}

    # Step 2: 현재 프로세스 메모리 업데이트 (threads_adapter 모듈 레벨 변수)
    threads_adapter.THREADS_ACCESS_TOKEN = new_token
    os.environ["THREADS_ACCESS_TOKEN"] = new_token
    logger.info(
        "Threads 토큰 메모리 갱신 완료 (expires_in=%s초, ~%d일)",
        expires_in,
        (expires_in or 0) // 86400,
    )

    # Step 3: Railway 환경변수 업데이트 (다음 배포/재시작 시 반영)
    railway_ok = await _update_railway_env_var("THREADS_ACCESS_TOKEN", new_token)
    if not railway_ok:
        await _send_admin_alert(
            "<b>보고: Threads 토큰 갱신 부분 완료</b>\n"
            "\n"
            "대표님, Threads 토큰 자체는 정상 갱신되었으나 Railway 환경변수 업데이트에 실패했습니다.\n"
            "Railway 대시보드에서 THREADS_ACCESS_TOKEN을 수동 업데이트해 주시기 바랍니다.\n"
            "<i>WeWantPeace 시스템 비서</i>"
        )
        return {
            "status": "ok",
            "detail": "토큰 갱신 OK, Railway 업데이트 실패",
            "expires_in": expires_in,
        }

    # Step 4: 성공 알림
    days = (expires_in or 0) // 86400
    await _send_admin_alert(
        f"<b>보고: Threads 토큰 갱신 완료</b>\n"
        f"\n"
        f"대표님, Threads 토큰 정상 갱신 완료했습니다.\n"
        f"새 토큰 만료일은 {days}일 후이며, Railway 환경변수도 업데이트되었습니다.\n"
        f"<i>WeWantPeace 시스템 비서</i>"
    )

    return {
        "status": "ok",
        "detail": f"갱신 완료 (만료: {days}일 후)",
        "expires_in": expires_in,
    }
