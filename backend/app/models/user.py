from datetime import datetime, time, timezone
from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Integer, JSON, SmallInteger,
    String, TIMESTAMP, Text, Time, UniqueConstraint, Uuid
)
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from backend.app.core.database import Base, StringArray


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    firebase_uid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default="free")

    # 프로필
    nickname: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # 계정 상태 및 권한
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")

    # 약관 동의
    agreed_terms_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    agreed_privacy_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    marketing_agreed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # 정지
    suspended_until: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    suspend_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_active: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint("plan IN ('free','pro','pro_plus')", name="ck_users_plan"),
        CheckConstraint("status IN ('active','suspended','deleted')", name="ck_users_status"),
        CheckConstraint("role IN ('user','moderator','admin')", name="ck_users_role"),
    )

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_moderator(self) -> bool:
        return self.role in ("moderator", "admin")

    def is_active(self) -> bool:
        return self.status == "active"


class UserArea(Base):
    __tablename__ = "user_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    area_type: Mapped[str] = mapped_column(String(16), nullable=False, default="country")
    country_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notify_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_fast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "area_type IN ('country','polygon','radius')", name="ck_user_areas_type"
        ),
    )


class UserPushToken(Base):
    __tablename__ = "user_push_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    fcm_token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_used: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "fcm_token", name="uq_user_push_tokens"),
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ko")
    min_severity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=35)
    topics: Mapped[list[str]] = mapped_column(
        StringArray,
        nullable=False,
        default=lambda: ["conflict", "terror", "coup", "sanctions", "cyber", "protest"],
    )
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Seoul")
    min_kscore: Mapped[float] = mapped_column(nullable=False, default=3.0)
