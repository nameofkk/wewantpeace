"""
Rate limiter (slowapi) — shared instance for use across routers.

Railway/Cloudflare 뒤에서 실제 클라이언트 IP를 식별하기 위해
X-Forwarded-For 헤더를 우선 사용하고, 없으면 client.host로 폴백.
"""
from starlette.requests import Request
from slowapi import Limiter


def _get_real_client_ip(request: Request) -> str:
    """X-Forwarded-For 헤더에서 실제 클라이언트 IP 추출.

    X-Forwarded-For 형식: "client, proxy1, proxy2"
    첫 번째 IP가 원본 클라이언트 IP.
    Cloudflare의 CF-Connecting-IP도 우선 확인.
    """
    # Cloudflare가 설정하는 단일 클라이언트 IP 헤더 (가장 신뢰도 높음)
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # 프록시 체인의 첫 번째 IP (클라이언트 원본)
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()

    # 폴백: 직접 연결 IP
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_get_real_client_ip, default_limits=["200/minute"])
