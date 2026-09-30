"""주간 브리핑 한 호 (2026-09-30).

예전엔 주간 발행물이 넷(월요일 뉴스레터·무료 나라별 브리프·Pro+ 주간 리포트·스레드 주간 카드)으로
따로 만들어졌고, 실제로 나가던 뉴스레터는 AI 연결이 끊겨 7월부터 매주 대체 문구로 발송됐다.
이제 worker/weekly/edition.py 가 한 번 만든 호를 여기 저장하고 네 곳이 같이 읽는다.

data 모양은 worker/weekly/edition.py 의 build_edition() 문서 참고.
"""
from datetime import datetime, timezone

from sqlalchemy import Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class WeeklyEdition(Base):
    __tablename__ = "weekly_editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_key: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)  # "2026-W40"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
    )
    sent_ko_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sent_en_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
