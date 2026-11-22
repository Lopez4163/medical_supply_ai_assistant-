"""Create guest session and welcome conversation persistence.

Revision ID: 20261109_01
Revises: 20261107_01
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261109_01"
down_revision: str | Sequence[str] | None = "20261107_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_guest_sessions_expires_at", "guest_sessions", ["expires_at"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guest_session_id", sa.Uuid(), nullable=False),
        sa.Column("langgraph_thread_id", sa.String(length=64), nullable=False),
        sa.Column("welcome_persisted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["guest_session_id"], ["guest_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guest_session_id"),
        sa.UniqueConstraint("langgraph_thread_id"),
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("client_message_id", sa.Uuid(), nullable=True),
        sa.Column("server_ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "message_kind", sa.String(length=32), server_default=sa.text("'turn'"), nullable=False
        ),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "elements_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "element_schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "server_ordinal >= 0", name="ck_conversation_messages_server_ordinal_nonnegative"
        ),
        sa.CheckConstraint(
            "role IN ('assistant', 'user')", name="ck_conversation_messages_role_valid"
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "client_message_id", name="uq_conversation_messages_client_message"
        ),
        sa.UniqueConstraint(
            "conversation_id", "server_ordinal", name="uq_conversation_messages_server_ordinal"
        ),
    )
    op.create_index(
        "uq_conversation_messages_welcome",
        "conversation_messages",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("message_kind = 'welcome'"),
    )


def downgrade() -> None:
    op.drop_index("uq_conversation_messages_welcome", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_index("ix_guest_sessions_expires_at", table_name="guest_sessions")
    op.drop_table("guest_sessions")
