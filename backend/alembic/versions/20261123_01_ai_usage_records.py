"""Add persistent OpenRouter usage observations."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261123_01"
down_revision: str | Sequence[str] | None = "20261116_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="RESTRICT"),
        ),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("selected_model", sa.String(200), nullable=False),
        sa.Column("provider_model", sa.String(200)),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Numeric(14, 8)),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("error_class", sa.String(64)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latency_ms >= 0", name="ck_ai_usage_records_latency_nonnegative"),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_usage_records_input_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_usage_records_output_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_ai_usage_records_total_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
            name="ck_ai_usage_records_cost_nonnegative",
        ),
    )
    op.create_index("ix_ai_usage_records_conversation_id", "ai_usage_records", ["conversation_id"])
    op.create_index("ix_ai_usage_records_correlation_id", "ai_usage_records", ["correlation_id"])
    op.create_index("ix_ai_usage_records_recorded_at", "ai_usage_records", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_records_recorded_at", table_name="ai_usage_records")
    op.drop_index("ix_ai_usage_records_correlation_id", table_name="ai_usage_records")
    op.drop_index("ix_ai_usage_records_conversation_id", table_name="ai_usage_records")
    op.drop_table("ai_usage_records")
