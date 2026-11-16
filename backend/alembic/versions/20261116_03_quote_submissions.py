"""Add protected quotation reviews, submissions, and outbox records."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261116_03"
down_revision: str | Sequence[str] | None = "20261109_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE quote_draft_status ADD VALUE IF NOT EXISTS 'submitted'")
    op.create_table(
        "protected_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "guest_session_id", sa.Uuid(), sa.ForeignKey("guest_sessions.id"), nullable=False
        ),
        sa.Column("draft_id", sa.Uuid(), sa.ForeignKey("quote_drafts.id"), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_protected_reviews_guest_session_id", "protected_reviews", ["guest_session_id"]
    )
    op.create_index("ix_protected_reviews_draft_id", "protected_reviews", ["draft_id"])
    op.create_table(
        "quote_submissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reference", sa.String(32), unique=True, nullable=False),
        sa.Column(
            "guest_session_id", sa.Uuid(), sa.ForeignKey("guest_sessions.id"), nullable=False
        ),
        sa.Column(
            "draft_id", sa.Uuid(), sa.ForeignKey("quote_drafts.id"), unique=True, nullable=False
        ),
        sa.Column("operation_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_quote_submissions_guest_session_id", "quote_submissions", ["guest_session_id"]
    )
    op.create_table(
        "quote_submission_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Uuid(),
            sa.ForeignKey("quote_submissions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sku_variant_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("sales_unit", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("indicative_unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_quote_submission_lines_quantity_positive"),
        sa.CheckConstraint(
            "indicative_unit_price > 0", name="ck_quote_submission_lines_price_positive"
        ),
        sa.UniqueConstraint(
            "submission_id", "sku", name="uq_quote_submission_lines_submission_sku"
        ),
    )
    op.create_index(
        "ix_quote_submission_lines_submission_id", "quote_submission_lines", ["submission_id"]
    )
    op.create_index(
        "ix_quote_submission_lines_sku_variant_id", "quote_submission_lines", ["sku_variant_id"]
    )
    op.create_table(
        "outbox_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(32), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("job_type", "aggregate_id", name="uq_outbox_jobs_aggregate"),
    )


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely when persisted rows may still
    # reference them; retain `submitted` rather than rewriting live draft state.
    op.drop_table("outbox_jobs")
    op.execute("DROP TABLE IF EXISTS quote_submission_lines")
    op.drop_index("ix_quote_submissions_guest_session_id", table_name="quote_submissions")
    op.drop_table("quote_submissions")
    op.drop_index("ix_protected_reviews_draft_id", table_name="protected_reviews")
    op.drop_index("ix_protected_reviews_guest_session_id", table_name="protected_reviews")
    op.drop_table("protected_reviews")
