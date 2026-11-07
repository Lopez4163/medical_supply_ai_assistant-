"""Create the catalog relational foundation.

Revision ID: 20261107_01
Revises: 20261106_01
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261107_01"
down_revision: str | Sequence[str] | None = "20261106_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

catalog_lifecycle_status = postgresql.ENUM(
    "active", "discontinued", name="catalog_lifecycle_status", create_type=False
)
image_provenance_status = postgresql.ENUM(
    "permitted_supplier",
    "licensed_generic",
    "ai_generated",
    "placeholder",
    name="image_provenance_status",
    create_type=False,
)
compatibility_state = postgresql.ENUM(
    "compatible", "incompatible", "unknown", name="compatibility_state", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    catalog_lifecycle_status.create(bind, checkfirst=True)
    image_provenance_status.create(bind, checkfirst=True)
    compatibility_state.create(bind, checkfirst=True)

    op.create_table(
        "product_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("length(btrim(code)) > 0", name="ck_product_categories_code_not_blank"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_product_categories_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "product_listings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "searchable_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "lifecycle_status",
            catalog_lifecycle_status,
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("primary_image_reference", sa.String(length=2048), nullable=True),
        sa.Column("image_fallback_key", sa.String(length=128), nullable=False),
        sa.Column(
            "image_provenance_status",
            image_provenance_status,
            server_default=sa.text("'placeholder'"),
            nullable=False,
        ),
        sa.Column("image_reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "length(btrim(product_id)) > 0", name="ck_product_listings_product_id_not_blank"
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_product_listings_name_not_blank"),
        sa.CheckConstraint(
            "length(btrim(image_fallback_key)) > 0",
            name="ck_product_listings_image_fallback_key_not_blank",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )
    op.create_index("ix_product_listings_category_id", "product_listings", ["category_id"])
    op.create_table(
        "sku_variants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column(
            "selector_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "searchable_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("sales_unit", sa.String(length=128), nullable=False),
        sa.Column("indicative_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "lifecycle_status",
            catalog_lifecycle_status,
            server_default=sa.text("'active'"),
            nullable=False,
        ),
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
        sa.CheckConstraint("length(btrim(sku)) > 0", name="ck_sku_variants_sku_not_blank"),
        sa.CheckConstraint(
            "length(btrim(sales_unit)) > 0", name="ck_sku_variants_sales_unit_not_blank"
        ),
        sa.CheckConstraint(
            "indicative_price > 0", name="ck_sku_variants_indicative_price_positive"
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["product_listings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
        sa.UniqueConstraint(
            "listing_id",
            "selector_attributes",
            name="uq_sku_variants_listing_selector_attributes",
        ),
    )
    op.create_index("ix_sku_variants_listing_id", "sku_variants", ["listing_id"])
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sku_variant_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity_on_hand >= 0", name="ck_inventory_items_quantity_on_hand_nonnegative"
        ),
        sa.ForeignKeyConstraint(["sku_variant_id"], ["sku_variants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku_variant_id"),
    )
    op.create_table(
        "sku_compatibilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_variant_id", sa.Uuid(), nullable=False),
        sa.Column("target_variant_id", sa.Uuid(), nullable=False),
        sa.Column("state", compatibility_state, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_variant_id <> target_variant_id",
            name="ck_sku_compatibilities_distinct_variants",
        ),
        sa.ForeignKeyConstraint(["source_variant_id"], ["sku_variants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_variant_id"], ["sku_variants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sku_compatibilities_unordered_variant_pair "
        "ON sku_compatibilities "
        "(LEAST(source_variant_id, target_variant_id), "
        "GREATEST(source_variant_id, target_variant_id))"
    )


def downgrade() -> None:
    op.drop_index("uq_sku_compatibilities_unordered_variant_pair", table_name="sku_compatibilities")
    op.drop_table("sku_compatibilities")
    op.drop_table("inventory_items")
    op.drop_index("ix_sku_variants_listing_id", table_name="sku_variants")
    op.drop_table("sku_variants")
    op.drop_index("ix_product_listings_category_id", table_name="product_listings")
    op.drop_table("product_listings")
    op.drop_table("product_categories")

    bind = op.get_bind()
    compatibility_state.drop(bind, checkfirst=True)
    image_provenance_status.drop(bind, checkfirst=True)
    catalog_lifecycle_status.drop(bind, checkfirst=True)
