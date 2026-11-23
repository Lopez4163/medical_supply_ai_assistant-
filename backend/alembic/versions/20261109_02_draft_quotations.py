"""Create session-scoped draft quotation and idempotency persistence.

Revision ID: 20261109_02
Revises: 20261109_01
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261109_02"
down_revision: str | Sequence[str] | None = "20261109_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

quote_draft_status = postgresql.ENUM("active", name="quote_draft_status", create_type=False)
idempotency_operation_status = postgresql.ENUM(
    "committed", name="idempotency_operation_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    quote_draft_status.create(bind, checkfirst=True)
    idempotency_operation_status.create(bind, checkfirst=True)

    op.create_table(
        "quote_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guest_session_id", sa.Uuid(), nullable=False),
        sa.Column("status", quote_draft_status, server_default=sa.text("'active'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 0", name="ck_quote_drafts_version_nonnegative"),
        sa.ForeignKeyConstraint(["guest_session_id"], ["guest_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_drafts_guest_session_id", "quote_drafts", ["guest_session_id"])
    op.create_index(
        "uq_quote_drafts_active_guest_session",
        "quote_drafts",
        ["guest_session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "quote_draft_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("sku_variant_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("indicative_unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_quote_draft_lines_quantity_positive"),
        sa.CheckConstraint("indicative_unit_price > 0", name="ck_quote_draft_lines_price_positive"),
        sa.ForeignKeyConstraint(["draft_id"], ["quote_drafts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sku_variant_id"], ["sku_variants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", "sku_variant_id", name="uq_quote_draft_lines_draft_sku"),
    )
    op.create_index("ix_quote_draft_lines_draft_id", "quote_draft_lines", ["draft_id"])
    op.create_index("ix_quote_draft_lines_sku_variant_id", "quote_draft_lines", ["sku_variant_id"])
    op.create_table(
        "idempotency_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("guest_session_id", sa.Uuid(), nullable=False),
        sa.Column("operation_kind", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            idempotency_operation_status,
            server_default=sa.text("'committed'"),
            nullable=False,
        ),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(operation_kind)) > 0", name="ck_idempotency_operations_kind_not_blank"
        ),
        sa.ForeignKeyConstraint(["guest_session_id"], ["guest_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guest_session_id", "operation_id", name="uq_idempotency_operations_session_operation"
        ),
    )
    op.create_index(
        "ix_idempotency_operations_guest_session_id", "idempotency_operations", ["guest_session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_operations_guest_session_id", table_name="idempotency_operations")
    op.drop_table("idempotency_operations")
    op.drop_index("ix_quote_draft_lines_sku_variant_id", table_name="quote_draft_lines")
    op.drop_index("ix_quote_draft_lines_draft_id", table_name="quote_draft_lines")
    op.drop_table("quote_draft_lines")
    op.drop_index("uq_quote_drafts_active_guest_session", table_name="quote_drafts")
    op.drop_index("ix_quote_drafts_guest_session_id", table_name="quote_drafts")
    op.drop_table("quote_drafts")

    bind = op.get_bind()
    idempotency_operation_status.drop(bind, checkfirst=True)
    quote_draft_status.drop(bind, checkfirst=True)
