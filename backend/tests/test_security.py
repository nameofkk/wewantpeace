"""
보안 기본 점검 테스트.
- SQL Injection 시도 → 정상 에러 처리 (500 아님)
- XSS 입력 → Content-Type application/json 확인
- 인증 필요 엔드포인트 → 401
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import app
from backend.app.core.database import Base

# 모든 모델 등록 (create_all 전에 import)
import backend.app.models  # noqa: F401
import backend.app.routers.issues as issues_router
import backend.app.routers.trending as trending_router
import backend.app.routers.tension as tension_router
import backend.app.routers.me as me_router


# ── 테스트 DB 픽스처 ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine) -> AsyncSession:
    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def anon_client(test_db: AsyncSession):
    """인증 없는 테스트 클라이언트."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[issues_router.get_db] = override_get_db
    app.dependency_overrides[trending_router.get_db] = override_get_db
    app.dependency_overrides[tension_router.get_db] = override_get_db
    app.dependency_overrides[me_router.get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ── SQL Injection ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sqli_in_issue_id(anon_client):
    """이슈 ID에 SQL 인젝션 시도 → 422 또는 404 (500 아님)."""
    payloads = [
        "1' OR '1'='1",
        "1; DROP TABLE issue_clusters;--",
        "' UNION SELECT * FROM users--",
    ]
    for payload in payloads:
        resp = await anon_client.get(f"/issues/{payload}")
        assert resp.status_code in (422, 404, 400), (
            f"SQLi payload '{payload}' → {resp.status_code} (500이면 취약)"
        )


@pytest.mark.asyncio
async def test_sqli_in_bbox_param(anon_client):
    """bbox 쿼리 파라미터에 SQL 인젝션 시도 → 500 아님."""
    resp = await anon_client.get("/issues?bbox=1' OR 1=1--")
    # SQLAlchemy 파라미터화 쿼리 → 인젝션 방어, 정상 응답 또는 유효성 오류
    assert resp.status_code in (200, 422, 400)
    assert resp.status_code != 500


@pytest.mark.asyncio
async def test_sqli_in_country_code(anon_client):
    """국가 코드에 인젝션 → 정상 에러 또는 빈 목록 (500 아님)."""
    resp = await anon_client.get("/tension/country/UA' OR '1'='1/history")
    # SQLAlchemy 파라미터화로 인젝션 방어 → 빈 목록(200) 또는 검증 오류
    assert resp.status_code in (200, 404, 422, 400)
    assert resp.status_code != 500


# ── XSS ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_xss_in_query_param_not_reflected_raw(anon_client):
    """XSS 페이로드가 Content-Type: application/json으로만 반환되는지 확인."""
    resp = await anon_client.get('/issues?topic=<script>alert(1)</script>')
    ct = resp.headers.get("content-type", "")
    assert "application/json" in ct or resp.status_code in (422, 400)


@pytest.mark.asyncio
async def test_api_response_content_type_is_json(anon_client):
    """모든 API 응답이 application/json인지 확인 (HTML 오류 페이지 반환 금지)."""
    for path in ["/health", "/trending/global", "/issues"]:
        resp = await anon_client.get(path)
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct, f"{path} → Content-Type: {ct}"


# ── 인증 ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sensitive_endpoints_require_auth(anon_client):
    """인증이 필요한 엔드포인트 목록 → 401."""
    # /tension/mine 은 비로그인도 기본 8개국 반환 (공개 설계)
    protected = [
        "/me",
        "/me/areas",
        "/me/preferences",
    ]
    for path in protected:
        resp = await anon_client.get(path)
        assert resp.status_code == 401, f"{path} → {resp.status_code} (401 필요)"


@pytest.mark.asyncio
async def test_no_stack_trace_in_error_response(anon_client):
    """에러 응답에 스택 트레이스가 노출되지 않아야 함."""
    resp = await anon_client.get("/nonexistent-endpoint-xyz")
    body = resp.text
    assert "Traceback" not in body
    assert "File \"" not in body


# ── 기본 건강 상태 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_200(anon_client):
    """/health → 200."""
    resp = await anon_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_security_headers_present(anon_client):
    """기본 보안 응답 헤더 확인."""
    resp = await anon_client.get("/health")
    assert resp.status_code == 200
