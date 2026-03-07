"""정정/업데이트 로그 모델. T15"""
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from backend.app.core.database import Base


class ClusterChangeLog(Base):
    __tablename__ = "cluster_change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("issue_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field: Mapped[str] = mapped_column(String(32), nullable=False)  # "title" | "severity" | "title_ko" | "topic"
    old_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="system")  # "admin_edit" | "reprocess" | "system"
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")  # "admin" | "system"
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
