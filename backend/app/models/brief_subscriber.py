"""나라별 주간 브리프 구독자 — 로그인 없이 이메일만 (2026-09-30).

회원 뉴스레터(users.email + marketing_agreed_at)와 별개다. 진단 결과 실제 방문자의 90%가
해외인데 대부분 가입하지 않는다. "내가 신경 쓰는 나라 한두 곳의 주 1회 요약"을 2주간
검증하려고 가입 없이 받는 창구를 만들었다.

- 이중 확인(double opt-in): 확인 링크를 누르기 전엔 status=pending, 발송 대상 아님
- consent_at: 개인정보 처리 동의 체크 시각 (GDPR — EU 실방문자가 있다)
- token: 확인·수신거부 링크 공용. 추측 불가 난수
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, TIMESTAMP, Uuid, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, StringArray


class BriefSubscriber(Base):
    __tablename__ = "brief_subscribers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    countries: Mapped[list[str]] = mapped_column(StringArray, nullable=False, default=list)
    lang: Mapped[str] = mapped_column(String(4), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("ix_brief_subscribers_status", "status"),)
