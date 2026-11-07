from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import get_database_engine
from app.models.catalog import (
    CompatibilityState,
    ImageProvenanceStatus,
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


def test_catalog_models_register_with_alembic_metadata() -> None:
    assert {
        "product_categories",
        "product_listings",
        "sku_variants",
        "inventory_items",
        "sku_compatibilities",
    }.issubset(Base.metadata.tables)


def unique_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


async def add_listing(session: AsyncSession) -> tuple[ProductCategory, ProductListing]:
    category = ProductCategory(code=unique_value("CAT"), name=unique_value("Category"))
    listing = ProductListing(
        category=category,
        product_id=unique_value("MOB"),
        name="Adjustable Walker",
        description="Synthetic test listing.",
        searchable_attributes={"mobility_type": "walker"},
        image_fallback_key="PH-MOBILITY",
        image_provenance_status=ImageProvenanceStatus.PLACEHOLDER,
    )
    session.add(listing)
    await session.flush()
    return category, listing


def build_variant(*, listing: ProductListing, sku: str | None = None) -> SkuVariant:
    return SkuVariant(
        listing=listing,
        sku=sku or unique_value("SKU"),
        selector_attributes={"size": "medium"},
        searchable_attributes={"material": "nitrile", "size": "medium"},
        sales_unit="box of 100",
        indicative_price=Decimal("12.50"),
    )


@pytest.mark.asyncio
async def test_catalog_relationships_inventory_compatibility_and_image_metadata_persist(
    db_session: AsyncSession,
) -> None:
    _, listing = await add_listing(db_session)
    listing.primary_image_reference = "catalog/mobility/walker.jpg"
    listing.image_provenance_status = ImageProvenanceStatus.LICENSED_GENERIC

    glowcheck_meter = build_variant(listing=listing, sku="DIA-GC-MTR-G1")
    glowcheck_strips = SkuVariant(
        listing=listing,
        sku="DIA-GC-STR-50",
        selector_attributes={"package_count": 50},
        searchable_attributes={"strip_system": "GlowCheck G1", "package_count": 50},
        sales_unit="box of 50 strips",
        indicative_price=Decimal("24.99"),
    )
    novatrace_strips = SkuVariant(
        listing=listing,
        sku="DIA-NT-STR-50",
        selector_attributes={"package_count": 100},
        searchable_attributes={"strip_system": "NovaTrace N2", "package_count": 100},
        sales_unit="box of 100 strips",
        indicative_price=Decimal("34.99"),
    )
    unknown_variant = SkuVariant(
        listing=listing,
        sku="DIA-CS-LANCET",
        selector_attributes={"gauge": 30},
        searchable_attributes={"lancet_system": "ClickSure", "gauge": 30},
        sales_unit="box of 100 lancets",
        indicative_price=Decimal("8.99"),
    )
    inventory = InventoryItem(variant=glowcheck_meter, quantity_on_hand=8)
    compatibility = SkuCompatibility(
        source_variant=glowcheck_meter,
        target_variant=glowcheck_strips,
        state=CompatibilityState.COMPATIBLE,
    )
    incompatible = SkuCompatibility(
        source_variant=glowcheck_meter,
        target_variant=novatrace_strips,
        state=CompatibilityState.INCOMPATIBLE,
    )
    unknown = SkuCompatibility(
        source_variant=glowcheck_meter,
        target_variant=unknown_variant,
        state=CompatibilityState.UNKNOWN,
    )
    db_session.add_all(
        [
            glowcheck_meter,
            glowcheck_strips,
            novatrace_strips,
            unknown_variant,
            inventory,
            compatibility,
            incompatible,
            unknown,
        ]
    )
    await db_session.commit()

    variants = list(
        await db_session.scalars(select(SkuVariant).where(SkuVariant.listing_id == listing.id))
    )

    assert {variant.sku for variant in variants} == {
        "DIA-GC-MTR-G1",
        "DIA-GC-STR-50",
        "DIA-NT-STR-50",
        "DIA-CS-LANCET",
    }
    assert inventory.sku_variant_id == glowcheck_meter.id
    assert compatibility.source_variant_id == glowcheck_meter.id
    assert compatibility.target_variant_id == glowcheck_strips.id
    assert {compatibility.state, incompatible.state, unknown.state} == {
        CompatibilityState.COMPATIBLE,
        CompatibilityState.INCOMPATIBLE,
        CompatibilityState.UNKNOWN,
    }
    assert listing.primary_image_reference == "catalog/mobility/walker.jpg"
    assert listing.image_fallback_key == "PH-MOBILITY"


@pytest.mark.asyncio
async def test_duplicate_product_id_is_rejected(db_session: AsyncSession) -> None:
    category = ProductCategory(code=unique_value("CAT"), name=unique_value("Category"))
    product_id = unique_value("MOB")
    db_session.add_all(
        [
            ProductListing(
                category=category,
                product_id=product_id,
                name="First listing",
                description="Synthetic test listing.",
                image_fallback_key="PH-MOBILITY",
            ),
            ProductListing(
                category=category,
                product_id=product_id,
                name="Second listing",
                description="Synthetic test listing.",
                image_fallback_key="PH-MOBILITY",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_duplicate_sku_is_rejected(db_session: AsyncSession) -> None:
    _, listing = await add_listing(db_session)
    sku = unique_value("PPE-NIT")
    db_session.add_all(
        [build_variant(listing=listing, sku=sku), build_variant(listing=listing, sku=sku)]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_invalid_category_and_listing_foreign_keys_are_rejected(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        ProductListing(
            category_id=uuid4(),
            product_id=unique_value("MOB"),
            name="Invalid category listing",
            description="Synthetic test listing.",
            image_fallback_key="PH-MOBILITY",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(
        SkuVariant(
            listing_id=uuid4(),
            sku=unique_value("PPE-NIT"),
            selector_attributes={"size": "medium"},
            searchable_attributes={"size": "medium"},
            sales_unit="box of 100",
            indicative_price=Decimal("12.50"),
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("price", [Decimal("0.00"), Decimal("-1.00")])
async def test_zero_and_negative_prices_are_rejected(
    db_session: AsyncSession, price: Decimal
) -> None:
    _, listing = await add_listing(db_session)
    variant = build_variant(listing=listing)
    variant.indicative_price = price
    db_session.add(variant)

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_negative_inventory_is_rejected(db_session: AsyncSession) -> None:
    _, listing = await add_listing(db_session)
    variant = build_variant(listing=listing)
    db_session.add(InventoryItem(variant=variant, quantity_on_hand=-1))

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_duplicate_inventory_for_variant_is_rejected(db_session: AsyncSession) -> None:
    _, listing = await add_listing(db_session)
    variant = build_variant(listing=listing)
    db_session.add_all(
        [
            InventoryItem(variant=variant, quantity_on_hand=1),
            InventoryItem(variant=variant, quantity_on_hand=2),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_duplicate_selector_attributes_under_one_listing_are_rejected(
    db_session: AsyncSession,
) -> None:
    _, listing = await add_listing(db_session)
    first_variant = build_variant(listing=listing)
    second_variant = build_variant(listing=listing)
    second_variant.selector_attributes = {"size": "medium"}
    db_session.add_all([first_variant, second_variant])

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_blank_sales_unit_is_rejected(db_session: AsyncSession) -> None:
    _, listing = await add_listing(db_session)
    variant = build_variant(listing=listing)
    variant.sales_unit = ""
    db_session.add(variant)

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_missing_sales_unit_is_rejected(db_session: AsyncSession) -> None:
    _, listing = await add_listing(db_session)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO sku_variants "
                "(id, listing_id, sku, selector_attributes, searchable_attributes, "
                "indicative_price) "
                "VALUES (:id, :listing_id, :sku, '{}'::jsonb, '{}'::jsonb, :price)"
            ),
            {
                "id": uuid4(),
                "listing_id": listing.id,
                "sku": unique_value("PPE-NIT"),
                "price": Decimal("12.50"),
            },
        )


@pytest.mark.asyncio
async def test_invalid_lifecycle_state_is_rejected(db_session: AsyncSession) -> None:
    _, listing = await add_listing(db_session)
    variant_id = uuid4()
    with pytest.raises(DBAPIError):
        await db_session.execute(
            text(
                "INSERT INTO sku_variants "
                "(id, listing_id, sku, selector_attributes, searchable_attributes, sales_unit, "
                "indicative_price, lifecycle_status) "
                "VALUES (:id, :listing_id, :sku, '{}'::jsonb, '{}'::jsonb, "
                ":sales_unit, :price, :status)"
            ),
            {
                "id": variant_id,
                "listing_id": listing.id,
                "sku": unique_value("PPE-NIT"),
                "sales_unit": "box of 100",
                "price": Decimal("12.50"),
                "status": "retired",
            },
        )


@pytest.mark.asyncio
async def test_compatibility_constraints_are_enforced(db_session: AsyncSession) -> None:
    _, listing = await add_listing(db_session)
    source_variant = build_variant(listing=listing, sku="DIA-NT-MTR-N2")
    target_variant = SkuVariant(
        listing=listing,
        sku="DIA-NT-STR-50",
        selector_attributes={"package_count": 50},
        searchable_attributes={"strip_system": "NovaTrace N2", "package_count": 50},
        sales_unit="box of 50 strips",
        indicative_price=Decimal("24.99"),
    )
    db_session.add_all([source_variant, target_variant])
    await db_session.commit()
    source_variant_id = source_variant.id
    target_variant_id = target_variant.id

    db_session.add(
        SkuCompatibility(
            source_variant=source_variant,
            target_variant=target_variant,
            state=CompatibilityState.COMPATIBLE,
        )
    )
    await db_session.commit()

    db_session.add(
        SkuCompatibility(
            source_variant=target_variant,
            target_variant=source_variant,
            state=CompatibilityState.INCOMPATIBLE,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(
        SkuCompatibility(
            source_variant_id=source_variant_id,
            target_variant_id=uuid4(),
            state=CompatibilityState.UNKNOWN,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    with pytest.raises(DBAPIError):
        await db_session.execute(
            text(
                "INSERT INTO sku_compatibilities "
                "(id, source_variant_id, target_variant_id, state) "
                "VALUES (:id, :source_variant_id, :target_variant_id, :state)"
            ),
            {
                "id": uuid4(),
                "source_variant_id": source_variant_id,
                "target_variant_id": target_variant_id,
                "state": "not_verified",
            },
        )
