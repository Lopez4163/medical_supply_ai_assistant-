"""Guest-session and conversation persistence for the synthetic demonstration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GuestSession(Base):
    __tablename__ = "guest_sessions"
    __table_args__ = (Index("ix_guest_sessions_expires_at", "expires_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversation: Mapped[Conversation | None] = relationship(
        back_populates="guest_session", uselist=False
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    guest_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    langgraph_thread_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    welcome_persisted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    guest_session: Mapped[GuestSession] = relationship(back_populates="conversation")
    messages: Mapped[list[ConversationMessage]] = relationship(back_populates="conversation")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint(
            "server_ordinal >= 0", name="ck_conversation_messages_server_ordinal_nonnegative"
        ),
        CheckConstraint(
            "role IN ('assistant', 'user')", name="ck_conversation_messages_role_valid"
        ),
        UniqueConstraint(
            "conversation_id", "client_message_id", name="uq_conversation_messages_client_message"
        ),
        UniqueConstraint(
            "conversation_id", "server_ordinal", name="uq_conversation_messages_server_ordinal"
        ),
        Index(
            "uq_conversation_messages_welcome",
            "conversation_id",
            unique=True,
            postgresql_where=text("message_kind = 'welcome'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="RESTRICT"), nullable=False
    )
    client_message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    server_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    message_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="turn", server_default=text("'turn'")
    )
    content_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    elements_json: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    element_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
