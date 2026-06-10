"""payment_history.pg_transaction_id 중복 적재 방지 유니크 인덱스

웹훅 재전송 / sync 백필이 같은 결제건을 두 번 적재해서
매출이 부풀려지던 버그(payment.succeeded 도착순서 미보장 + sync 복구 경로 중첩)를
DB 차원에서 막는 백스톱.

(platform, pg_transaction_id, status) 부분 유니크 인덱스:
- status까지 키에 포함 → 같은 거래의 success→refunded 같은 정상 기록은 허용.
- pg_transaction_id IS NULL 인 레거시/내부 기록은 여러 개 허용(부분 인덱스).

주의: 이미 들어가 있는 중복 행을 먼저 정리하지 않으면 유니크 인덱스 생성이 실패한다.
그래서 인덱스 생성 전에 그룹별로 가장 먼저 들어온 행(created_at, id 기준) 하나만 남기고
나머지를 삭제한다.

Revision ID: 0059
Revises: 0058
"""
from alembic import op

revision = "0059"
down_revision = "0058"


def upgrade() -> None:
    # 1) 기존 중복 행 정리 — 그룹별 최초 1건(created_at ASC, id ASC)만 남김.
    #    매출 집계 시점 정확성을 위해 가장 이른 created_at 을 보존.
    op.execute(
        """
        DELETE FROM payment_history p
        USING (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY platform, pg_transaction_id, status
                       ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM payment_history
            WHERE pg_transaction_id IS NOT NULL
        ) d
        WHERE p.id = d.id AND d.rn > 1
        """
    )

    # 2) 부분 유니크 인덱스 생성 (멱등).
    #    CONCURRENTLY 미사용: alembic은 트랜잭션 내에서 돌아서 불가.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_history_pg_txn
        ON payment_history (platform, pg_transaction_id, status)
        WHERE pg_transaction_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("uq_payment_history_pg_txn", table_name="payment_history")
