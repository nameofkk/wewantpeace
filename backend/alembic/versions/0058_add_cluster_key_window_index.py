"""add cluster_key + window_end composite index (fix slow query → connection pool exhaustion)

0056에서 cluster_key UNIQUE 제약 삭제 시 인덱스도 함께 삭제됨.
그 결과 clusterer.py의 WHERE cluster_key=... AND window_end>=... 쿼리가
풀테이블 스캔 → statement timeout → 커넥션 고갈 → ECHECKOUTTIMEOUT.

Revision ID: 0058
Revises: 0057
"""
from alembic import op

revision = "0058"
down_revision = "0057"


def upgrade() -> None:
    # cluster_key + window_end 복합 인덱스 — clusterer.py 핵심 조회 쿼리용
    # WHERE cluster_key=? AND window_end >= ? ORDER BY last_event_at DESC
    # CONCURRENTLY 제거: alembic은 transaction 내에서 실행되므로
    # CONCURRENTLY는 "cannot run inside a transaction block" 에러 발생.
    # IF NOT EXISTS로 멱등성 보장.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ic_key_window_lastev "
        "ON issue_clusters (cluster_key, window_end DESC, last_event_at DESC)"
    )


def downgrade() -> None:
    op.drop_index("idx_ic_key_window_lastev", table_name="issue_clusters")
