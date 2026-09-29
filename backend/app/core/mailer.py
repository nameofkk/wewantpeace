"""트랜잭션 메일 (Resend HTTP API). Railway 는 SMTP 포트를 막아 HTTP 로 보낸다.

admin.py / worker/tasks.py 에도 같은 발송 코드가 있다 — 여기는 백엔드 라우터에서 쓰는
가벼운 버전이고, 키가 없으면 보내지 않고 False 를 돌려준다.
"""
import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_FROM = "WeWantPeace <noreply@wewantpeace.live>"


def send_email(to: str, subject: str, html: str, text: str | None = None,
               headers: dict | None = None, from_addr: str | None = None) -> bool:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        logger.warning("RESEND_API_KEY 없음 — 메일 미발송: %s", subject)
        return False
    payload = {"from": from_addr or DEFAULT_FROM, "to": [to], "subject": subject, "html": html}
    if text:
        payload["text"] = text
    if headers:
        payload["headers"] = headers
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "WeWantPeace/1.0"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception:
        logger.exception("메일 발송 실패: %s", subject)
        return False
