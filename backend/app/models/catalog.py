"""Relational catalog foundation for synthetic product data."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CatalogLifecycleStatus(StrEnum):
    ACTIVE = "active"
    DISCONTINUED = "discontinued"


class CompatibilityState(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class ImageProvenanceStatus(StrEnum):
    PERMITTED_SUPPLIER = "permitted_supplier"
    LICENSED_GENERIC = "licensed_generic"
    AI_GENERATED = "ai_generated"
    PLACEHOLDER = "placeholder"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class ProductCategory(Base):
    __tablename__ = "product_categories"
    __table_args__ = (
        CheckConstraint("length(btrim(code)) > 0", name="ck_product_categories_code_not_blank"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_product_categories_name_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    listings: Mapped[list[ProductListing]] = relationship(back_populates="category")


class ProductListing(Base):
    __tablename__ = "product_listings"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(product_id)) > 0", name="ck_product_listings_product_id_not_blank"
        ),
        CheckConstraint("length(btrim(name)) > 0", name="ck_product_listings_name_not_blank"),
        CheckConstraint(
            "length(btrim(image_fallback_key)) > 0",
            name="ck_product_listings_image_fallback_key_not_blank",
        ),
        Index("ix_product_listings_category_id", "category_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_categories.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    searchable_attributes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    lifecycle_status: Mapped[CatalogLifecycleStatus] = mapped_column(
        Enum(
            CatalogLifecycleStatus,
            name="catalog_lifecycle_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CatalogLifecycleStatus.ACTIVE,
        server_default=text("'active'"),
    )
    primary_image_reference: Mapped[str | None] = mapped_column(String(2048))
    image_fallback_key: Mapped[str] = mapped_column(String(128), nullable=False)
    image_provenance_status: Mapped[ImageProvenanceStatus] = mapped_column(
        Enum(
            ImageProvenanceStatus,
            name="image_provenance_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ImageProvenanceStatus.PLACEHOLDER,
        server_default=text("'placeholder'"),
    )
    image_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    category: Mapped[ProductCategory] = relationship(back_populates="listings")
    variants: Mapped[list[SkuVariant]] = relationship(back_populates="listing")


class SkuVariant(Base):
    __tablename__ = "sku_variants"
    __table_args__ = (
        CheckConstraint("length(btrim(sku)) > 0", name="ck_sku_variants_sku_not_blank"),
        CheckConstraint(
            "length(btrim(sales_unit)) > 0", name="ck_sku_variants_sales_unit_not_blank"
        ),
        CheckConstraint("indicative_price > 0", name="ck_sku_variants_indicative_price_positive"),
        UniqueConstraint(
            "listing_id",
            "selector_attributes",
            name="uq_sku_variants_listing_selector_attributes",
        ),
        Index("ix_sku_variants_listing_id", "listing_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_listings.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    selector_attributes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    searchable_attributes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    sales_unit: Mapped[str] = mapped_column(String(128), nullable=False)
    indicative_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    lifecycle_status: Mapped[CatalogLifecycleStatus] = mapped_column(
        Enum(
            CatalogLifecycleStatus,
            name="catalog_lifecycle_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=CatalogLifecycleStatus.ACTIVE,
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    listing: Mapped[ProductListing] = relationship(back_populates="variants")
    inventory: Mapped[InventoryItem | None] = relationship(back_populates="variant", uselist=False)
    compatibility_sources: Mapped[list[SkuCompatibility]] = relationship(
        back_populates="source_variant", foreign_keys="SkuCompatibility.source_variant_id"
    )
    compatibility_targets: Mapped[list[SkuCompatibility]] = relationship(
        back_populates="target_variant", foreign_keys="SkuCompatibility.target_variant_id"
    )


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint(
            "quantity_on_hand >= 0", name="ck_inventory_items_quantity_on_hand_nonnegative"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sku_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("sku_variants.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    quantity_on_hand: Mapped[int] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    variant: Mapped[SkuVariant] = relationship(back_populates="inventory")


class SkuCompatibility(Base):
    __tablename__ = "sku_compatibilities"
    __table_args__ = (
        CheckConstraint(
            "source_variant_id <> target_variant_id",
            name="ck_sku_compatibilities_distinct_variants",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("sku_variants.id", ondelete="RESTRICT"), nullable=False
    )
    target_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("sku_variants.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[CompatibilityState] = mapped_column(
        Enum(CompatibilityState, name="compatibility_state", values_callable=_enum_values),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )

    source_variant: Mapped[SkuVariant] = relationship(
        back_populates="compatibility_sources", foreign_keys=[source_variant_id]
    )
    target_variant: Mapped[SkuVariant] = relationship(
        back_populates="compatibility_targets", foreign_keys=[target_variant_id]
    )


Index(
    "uq_sku_compatibilities_unordered_variant_pair",
    func.least(SkuCompatibility.source_variant_id, SkuCompatibility.target_variant_id),
    func.greatest(SkuCompatibility.source_variant_id, SkuCompatibility.target_variant_id),
    unique=True,
)
