"""Immutable synthetic support-inquiry persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupportReview(Base):
    __tablename__ = "support_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    guest_session_id: Mapped[UUID] = mapped_column(ForeignKey("guest_sessions.id"), index=True)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportInquiry(Base):
    __tablename__ = "support_inquiries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reference: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    guest_session_id: Mapped[UUID] = mapped_column(ForeignKey("guest_sessions.id"), index=True)
    operation_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    contact_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(2_000), nullable=False)
    conversation_context: Mapped[str | None] = mapped_column(String(2_000))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
