"""Add protected support reviews and immutable support inquiries."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261116_04"
down_revision: str | Sequence[str] | None = "20261116_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "guest_session_id", sa.Uuid(), sa.ForeignKey("guest_sessions.id"), nullable=False
        ),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_support_reviews_guest_session_id", "support_reviews", ["guest_session_id"])
    op.create_table(
        "support_inquiries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reference", sa.String(32), unique=True, nullable=False),
        sa.Column(
            "guest_session_id", sa.Uuid(), sa.ForeignKey("guest_sessions.id"), nullable=False
        ),
        sa.Column("operation_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("contact_json", postgresql.JSONB(), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(2_000), nullable=False),
        sa.Column("conversation_context", sa.String(2_000)),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_support_inquiries_guest_session_id", "support_inquiries", ["guest_session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_support_inquiries_guest_session_id", table_name="support_inquiries")
    op.drop_table("support_inquiries")
    op.drop_index("ix_support_reviews_guest_session_id", table_name="support_reviews")
    op.drop_table("support_reviews")
