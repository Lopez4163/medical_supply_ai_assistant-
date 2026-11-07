from __future__ import annotations

from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal
from typing import cast

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.settings import get_settings
from app.db.session import get_database_engine
from app.dev.catalog_fixtures import CATALOG_FIXTURE, CatalogFixture
from app.dev.seed_catalog import (
    CatalogSeedConflictError,
    CatalogSeedSafetyError,
    run_command,
    seed_catalog,
    validate_fixture,
)
from app.models.catalog import (
    CatalogLifecycleStatus,
    CompatibilityState,
    InventoryItem,
    ProductCategory,
    ProductListing,
    SkuCompatibility,
    SkuVariant,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = get_database_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


def test_catalog_fixture_has_approved_totals_and_category_distribution() -> None:
    validate_fixture(CATALOG_FIXTURE)

    listing_counts = Counter(product.category_code for product in CATALOG_FIXTURE.products)
    sku_counts = Counter(
        product.category_code
        for product in CATALOG_FIXTURE.products
        for _variant in product.variants
    )

    assert listing_counts == {
        "MOB": 10,
        "BTH": 9,
        "DIA": 9,
        "DGN": 8,
        "PPE": 9,
        "WND": 9,
        "CON": 10,
        "OTC": 9,
        "SYR": 7,
    }
    assert sku_counts == {
        "MOB": 13,
        "BTH": 10,
        "DIA": 12,
        "DGN": 10,
        "PPE": 13,
        "WND": 11,
        "CON": 11,
        "OTC": 10,
        "SYR": 10,
    }


@pytest.mark.asyncio
async def test_seed_catalog_persists_the_approved_fixture(db_session: AsyncSession) -> None:
    summary = await seed_catalog(db_session)

    assert summary.categories == 9
    assert summary.listings == 80
    assert summary.variants == 100
    assert summary.inventory_items == 100
    assert summary.compatibilities == 7
    assert await db_session.scalar(select(func.count()).select_from(ProductCategory)) == 9
    assert await db_session.scalar(select(func.count()).select_from(ProductListing)) == 80
    assert await db_session.scalar(select(func.count()).select_from(SkuVariant)) == 100
    assert await db_session.scalar(select(func.count()).select_from(InventoryItem)) == 100

    listing_counts = dict(
        (
            await db_session.execute(
                select(ProductCategory.code, func.count(ProductListing.id))
                .join(ProductListing, ProductListing.category_id == ProductCategory.id)
                .group_by(ProductCategory.code)
            )
        ).all()
    )
    sku_counts = dict(
        (
            await db_session.execute(
                select(ProductCategory.code, func.count(SkuVariant.id))
                .join(ProductListing, ProductListing.category_id == ProductCategory.id)
                .join(SkuVariant, SkuVariant.listing_id == ProductListing.id)
                .group_by(ProductCategory.code)
            )
        ).all()
    )
    assert listing_counts == {
        "MOB": 10,
        "BTH": 9,
        "DIA": 9,
        "DGN": 8,
        "PPE": 9,
        "WND": 9,
        "CON": 10,
        "OTC": 9,
        "SYR": 7,
    }
    assert sku_counts == {
        "MOB": 13,
        "BTH": 10,
        "DIA": 12,
        "DGN": 10,
        "PPE": 13,
        "WND": 11,
        "CON": 11,
        "OTC": 10,
        "SYR": 10,
    }

    expected_listings = {product.product_id: product for product in CATALOG_FIXTURE.products}
    persisted_listings = (
        await db_session.execute(
            select(ProductListing, ProductCategory.code).join(
                ProductCategory, ProductListing.category_id == ProductCategory.id
            )
        )
    ).all()
    assert {listing.product_id for listing, _category_code in persisted_listings} == set(
        expected_listings
    )
    for listing, category_code in persisted_listings:
        expected_listing = expected_listings[listing.product_id]
        assert category_code == expected_listing.category_code
        assert listing.name == expected_listing.name
        assert listing.description == expected_listing.description
        assert listing.searchable_attributes == expected_listing.searchable_attributes
        assert listing.lifecycle_status == CatalogLifecycleStatus.ACTIVE
        assert listing.primary_image_reference is None
        assert listing.image_fallback_key == expected_listing.image_fallback_key

    expected_variants = {
        variant.sku: variant for product in CATALOG_FIXTURE.products for variant in product.variants
    }
    persisted_variants = (
        await db_session.execute(
            select(SkuVariant, InventoryItem).join(
                InventoryItem, InventoryItem.sku_variant_id == SkuVariant.id
            )
        )
    ).all()
    assert {variant.sku for variant, _inventory in persisted_variants} == set(expected_variants)
    for variant, inventory in persisted_variants:
        expected_variant = expected_variants[variant.sku]
        assert variant.selector_attributes == expected_variant.selector_attributes
        assert variant.searchable_attributes == expected_variant.searchable_attributes
        assert variant.sales_unit == expected_variant.sales_unit
        assert variant.indicative_price == expected_variant.indicative_price
        assert variant.lifecycle_status == expected_variant.lifecycle_status
        assert inventory.quantity_on_hand == expected_variant.quantity_on_hand

    nitrile_gloves = await db_session.scalar(
        select(SkuVariant).where(SkuVariant.sku == "PPE-NIT-M")
    )
    assert nitrile_gloves is not None
    assert nitrile_gloves.indicative_price == Decimal("11.00")
    nitrile_inventory = await db_session.scalar(
        select(InventoryItem).where(InventoryItem.sku_variant_id == nitrile_gloves.id)
    )
    assert nitrile_inventory is not None
    assert nitrile_inventory.quantity_on_hand == 15
    assert nitrile_gloves.selector_attributes == {
        "material": "nitrile",
        "package_count": 100,
        "powder_free": True,
        "size": "medium",
        "sterile": False,
    }
    assert nitrile_gloves.sales_unit == "100/box"

    out_of_stock = await db_session.scalar(
        select(SkuVariant).where(SkuVariant.sku == "CON-UNDER-10")
    )
    discontinued = await db_session.scalar(
        select(SkuVariant).where(SkuVariant.sku == "CON-SPILL-1")
    )
    assert out_of_stock is not None
    assert discontinued is not None
    out_of_stock_inventory = await db_session.scalar(
        select(InventoryItem).where(InventoryItem.sku_variant_id == out_of_stock.id)
    )
    discontinued_inventory = await db_session.scalar(
        select(InventoryItem).where(InventoryItem.sku_variant_id == discontinued.id)
    )
    assert out_of_stock_inventory is not None
    assert out_of_stock_inventory.quantity_on_hand == 0
    assert discontinued_inventory is not None
    assert discontinued.lifecycle_status == CatalogLifecycleStatus.DISCONTINUED
    assert discontinued_inventory.quantity_on_hand == 0

    missing_image = await db_session.scalar(
        select(ProductListing).where(ProductListing.product_id == "MOB-002")
    )
    assert missing_image is not None
    assert missing_image.primary_image_reference is None
    assert missing_image.image_fallback_key == "PH Mobility"

    source_variant = aliased(SkuVariant)
    target_variant = aliased(SkuVariant)
    compatibility_pairs = {
        (source.sku, target.sku): state
        for source, target, state in (
            await db_session.execute(
                select(source_variant, target_variant, SkuCompatibility.state)
                .join(
                    SkuCompatibility,
                    SkuCompatibility.source_variant_id == source_variant.id,
                )
                .join(
                    target_variant,
                    SkuCompatibility.target_variant_id == target_variant.id,
                )
            )
        ).all()
    }
    assert compatibility_pairs[("DIA-GC-MTR-G1", "DIA-GC-STR-50")] == CompatibilityState.COMPATIBLE
    assert compatibility_pairs[("DIA-NT-MTR-N2", "DIA-NT-STR-50")] == CompatibilityState.COMPATIBLE
    assert (
        compatibility_pairs[("DIA-GC-MTR-G1", "DIA-NT-STR-50")] == CompatibilityState.INCOMPATIBLE
    )


@pytest.mark.asyncio
async def test_second_seed_run_is_an_idempotent_no_op(db_session: AsyncSession) -> None:
    await seed_catalog(db_session)
    original_inventory = await db_session.scalar(
        select(InventoryItem.quantity_on_hand)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == "PPE-NIT-M")
    )

    summary = await seed_catalog(db_session)

    assert summary.variants == 100
    assert await db_session.scalar(select(func.count()).select_from(SkuVariant)) == 100
    assert (
        await db_session.scalar(
            select(InventoryItem.quantity_on_hand)
            .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
            .where(SkuVariant.sku == "PPE-NIT-M")
        )
        == original_inventory
    )


@pytest.mark.asyncio
async def test_seed_rejects_conflicting_existing_catalog_records(db_session: AsyncSession) -> None:
    await seed_catalog(db_session)
    inventory = await db_session.scalar(
        select(InventoryItem)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == "PPE-NIT-M")
    )
    assert inventory is not None
    inventory.quantity_on_hand = 99
    await db_session.commit()

    with pytest.raises(CatalogSeedConflictError, match="inventory"):
        await seed_catalog(db_session)


@pytest.mark.asyncio
async def test_invalid_fixture_rolls_back_all_seed_writes(db_session: AsyncSession) -> None:
    first_product = CATALOG_FIXTURE.products[0]
    invalid_variant = replace(
        first_product.variants[0],
        lifecycle_status=cast(CatalogLifecycleStatus, "not-a-valid-lifecycle-status"),
    )
    invalid_product = replace(
        first_product, variants=(invalid_variant, *first_product.variants[1:])
    )
    invalid_fixture = CatalogFixture(
        categories=CATALOG_FIXTURE.categories,
        products=(invalid_product, *CATALOG_FIXTURE.products[1:]),
        compatibilities=CATALOG_FIXTURE.compatibilities,
    )

    with pytest.raises((DBAPIError, StatementError)):
        await seed_catalog(db_session, fixture=invalid_fixture)

    assert await db_session.scalar(select(func.count()).select_from(ProductCategory)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ProductListing)) == 0
    assert await db_session.scalar(select(func.count()).select_from(SkuVariant)) == 0


@pytest.mark.asyncio
async def test_seed_command_rejects_an_unapproved_database_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://medical_supply_app:local@127.0.0.1:55432/unapproved"
    )
    get_settings.cache_clear()

    with pytest.raises(CatalogSeedSafetyError, match="expected 'medical_supply_test'"):
        await run_command("test")
