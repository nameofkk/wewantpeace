"""sync_dodo_subscriptions 페이지네이션 회귀 테스트.

버그: client.subscriptions.list(page_size=100).items 는 첫 페이지(최대 100건)만 담는다.
구독이 100건을 넘으면 101번째부터가 동기화에서 통째로 누락됐다.
수정: paginator를 list()로 순회해 전체 페이지를 끌어온다(SDK 자동 페이지네이션).

이 테스트는 .items에는 첫 페이지만, __iter__에는 전체가 들어있는 가짜 paginator를
주입해서, sync가 전체(120건)를 다 읽는지 검증한다. 옛 코드면 100건에서 멈춘다.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from backend.app.core.config import settings
from backend.app.models.subscription import Subscription
from backend.app.models.user import User
from backend.app.routers import admin


class _FakePaginator:
    """Dodo SDK paginator 흉내. .items = 첫 페이지만, 순회 = 전체 페이지."""

    def __init__(self, all_items, page_size=100):
        self._all = list(all_items)
        self.items = self._all[:page_size]  # SDK와 동일: 첫 페이지만

    def __iter__(self):
        return iter(self._all)  # SDK __iter__ 는 has_next_page 따라 전체를 자동 순회


def _make_dsub(i: int, user_id: uuid.UUID):
    return SimpleNamespace(
        subscription_id=f"sub_{i:04d}",
        status="active",
        metadata={"user_id": str(user_id), "plan": "pro", "billing_interval": "monthly"},
        recurring_pre_tax_amount=699,
        currency="USD",
        customer=SimpleNamespace(customer_id=f"cus_{i:04d}"),
        product_id="prod_pro",
        created_at=None,
        next_billing_date=None,
    )


@pytest.mark.asyncio
async def test_sync_reads_all_pages_not_just_first_100(db, monkeypatch):
    """구독이 120건이면 120건 전부 동기화돼야 한다(첫 100건에서 멈추면 버그)."""
    TOTAL = 120
    user_ids = [uuid.uuid4() for _ in range(TOTAL)]
    for uid in user_ids:
        db.add(User(id=uid, firebase_uid=f"fb-{uid.hex[:12]}", plan="free"))
    await db.flush()

    dsubs = [_make_dsub(i, user_ids[i]) for i in range(TOTAL)]

    fake_client = SimpleNamespace(
        subscriptions=SimpleNamespace(list=lambda page_size=100: _FakePaginator(dsubs, page_size)),
        # 결제 백필은 이 테스트 범위 밖 — 빈 목록으로 비활성화
        payments=SimpleNamespace(list=lambda page_size=100: iter([])),
    )

    monkeypatch.setattr(settings, "dodo_api_key", "test_key", raising=False)
    monkeypatch.setattr(settings, "dodo_environment", "test_mode", raising=False)

    # 픽스처가 session.begin()으로 감싸 롤백 격리하므로, 엔드포인트의 commit이
    # 외부 트랜잭션을 닫지 않도록 flush로 치환한다(테스트 격리 유지).
    monkeypatch.setattr(db, "commit", db.flush)

    with patch("dodopayments.DodoPayments", return_value=fake_client):
        result = await admin.sync_dodo_subscriptions(admin=object(), db=db)

    assert result["total_active_in_dodo"] == TOTAL, "전체 페이지를 못 읽음(첫 페이지에서 멈춤)"
    assert result["synced"] == TOTAL

    db_count = (
        await db.execute(
            select(func.count()).select_from(Subscription).where(
                Subscription.platform == "dodopayments",
                Subscription.status == "active",
            )
        )
    ).scalar_one()
    assert db_count == TOTAL, f"DB에 {TOTAL}건 들어가야 하는데 {db_count}건만 들어감"
