"""payment_history.user_id nullable (웹훅 순서 역전 시 매출 보존)

DodoPayments 웹훅에서 payment.succeeded가 subscription.active보다 먼저 도착하면
구독을 못 찾는다. 기존엔 그냥 return으로 매출을 버렸음.

이제 user/subscription 연결 없이도 일단 PaymentHistory에 기록하고
(dodo_subscription_id는 pg_response에 보관), subscription.active 처리 시 백필한다.
이를 위해 user_id를 nullable로 변경.

Revision ID: 0059
Revises: 0058
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0059"
down_revision = "0058"


def upgrade() -> None:
    op.alter_column(
        "payment_history",
        "user_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )
    # 미연결 매출 백필 조회용 부분 인덱스 (subscription_id IS NULL 인 dodopayments 건만)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ph_orphan_dodo "
        "ON payment_history (platform) "
        "WHERE subscription_id IS NULL"
    )


def downgrade() -> None:
    op.drop_index("idx_ph_orphan_dodo", table_name="payment_history")
    # 주의: NULL user_id 행이 남아 있으면 NOT NULL 복원이 실패한다.
    op.alter_column(
        "payment_history",
        "user_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )
