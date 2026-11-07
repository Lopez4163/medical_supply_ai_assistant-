from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import asdict
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_engine
from app.dev.seed_catalog import seed_catalog
from app.models.catalog import CompatibilityState, InventoryItem, SkuVariant
from app.services.catalog import CatalogSearchFilters, CatalogService
from app.services.inventory import (
    AvailabilityStatus,
    InvalidRequestedQuantity,
    InventoryService,
    ProposedLimitedStockThresholdPolicy,
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
            await seed_catalog(session)
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_exact_sku_lookup_preserves_persisted_catalog_facts(db_session: AsyncSession) -> None:
    result = await CatalogService(db_session).get_sku(sku="PPE-NIT-M")

    assert result is not None
    assert result.product_id == "PPE-001"
    assert result.indicative_price == Decimal("11.00")
    assert result.sales_unit == "100/box"
    assert result.selector_attributes["size"] == "medium"
    assert result.primary_image_reference is None
    assert result.image_fallback_key == "PH PPE"
    assert await CatalogService(db_session).get_sku(sku="MISSING") is None


@pytest.mark.asyncio
async def test_parent_lookup_remains_a_family_with_multiple_variants(
    db_session: AsyncSession,
) -> None:
    family = await CatalogService(db_session).get_product_family(product_id="PPE-001")

    assert family is not None
    assert family.product_id == "PPE-001"
    assert {variant.sku for variant in family.variants} == {"PPE-NIT-S", "PPE-NIT-M", "PPE-NIT-L"}


@pytest.mark.asyncio
async def test_search_enforces_structured_filters_and_stable_ordering(
    db_session: AsyncSession,
) -> None:
    service = CatalogService(db_session)
    filters = CatalogSearchFilters(
        query="nitrile gloves",
        category="PPE",
        size="medium",
        material="nitrile",
    )

    first = await service.search(filters=filters)
    second = await service.search(filters=filters)

    assert [item.sku for item in first] == ["PPE-NIT-M"]
    assert [item.sku for item in first] == [item.sku for item in second]
    assert (
        await service.search(
            filters=CatalogSearchFilters(category="PPE", size="small", material="vinyl")
        )
        == ()
    )


@pytest.mark.asyncio
async def test_search_exact_sku_precedes_keyword_ranking(db_session: AsyncSession) -> None:
    results = await CatalogService(db_session).search(
        filters=CatalogSearchFilters(query="PPE-NIT-M gloves")
    )

    assert results[0].sku == "PPE-NIT-M"


@pytest.mark.asyncio
async def test_search_treats_product_identifier_in_a_keyword_query_as_exact(
    db_session: AsyncSession,
) -> None:
    results = await CatalogService(db_session).search(
        filters=CatalogSearchFilters(query="PPE-001 disposable gloves")
    )

    assert [item.product_id for item in results[:3]] == ["PPE-001", "PPE-001", "PPE-001"]


@pytest.mark.asyncio
async def test_search_supports_category_and_variant_attribute_filters(
    db_session: AsyncSession,
) -> None:
    results = await CatalogService(db_session).search(
        filters=CatalogSearchFilters(category="DIA", model_system="GlowCheck G1")
    )

    assert {item.sku for item in results} == {
        "DIA-GC-STR-50",
        "DIA-GC-STR-100",
        "DIA-GC-MTR-G1",
        "DIA-GC-CTRL",
    }


@pytest.mark.asyncio
async def test_inventory_uses_private_stock_without_exposing_it(db_session: AsyncSession) -> None:
    result = await InventoryService(db_session).check_availability(sku="PPE-NIT-M", quantity=30)

    assert result.availability == AvailabilityStatus.IN_STOCK
    assert not result.is_sufficient
    assert "quantity_on_hand" not in asdict(result)
    assert "15" not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", [0, -1, True])
async def test_inventory_rejects_nonpositive_or_noninteger_quantities(
    db_session: AsyncSession, quantity: int
) -> None:
    with pytest.raises(InvalidRequestedQuantity):
        await InventoryService(db_session).check_availability(sku="PPE-NIT-M", quantity=quantity)


@pytest.mark.asyncio
async def test_inventory_uses_explicit_proposed_threshold_policy(db_session: AsyncSession) -> None:
    service = InventoryService(db_session, threshold_policy=ProposedLimitedStockThresholdPolicy())

    low_stock = await service.check_availability(sku="MOB-WLK-ADJ-BLU", quantity=1)
    out_of_stock = await service.check_availability(sku="CON-UNDER-10", quantity=1)
    infrared = await service.check_availability(sku="DGN-THERM-IR", quantity=1)
    discontinued = await service.check_availability(sku="CON-SPILL-1", quantity=1)

    assert low_stock.availability == AvailabilityStatus.LIMITED_STOCK
    assert low_stock.is_sufficient
    assert out_of_stock.availability == AvailabilityStatus.OUT_OF_STOCK
    assert infrared.availability == AvailabilityStatus.OUT_OF_STOCK
    assert discontinued.availability == AvailabilityStatus.DISCONTINUED


@pytest.mark.asyncio
async def test_missing_inventory_is_unavailable_not_out_of_stock(db_session: AsyncSession) -> None:
    inventory = await db_session.scalar(
        select(InventoryItem)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == "PPE-NIT-M")
    )
    assert inventory is not None
    await db_session.delete(inventory)
    await db_session.flush()

    result = await InventoryService(db_session).check_availability(sku="PPE-NIT-M", quantity=1)

    assert result.availability == AvailabilityStatus.UNAVAILABLE
    assert not result.is_sufficient


@pytest.mark.asyncio
async def test_catalog_and_inventory_reads_do_not_mutate_stock(db_session: AsyncSession) -> None:
    inventory = await db_session.scalar(
        select(InventoryItem)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == "MOB-WLK-ADJ-BLU")
    )
    assert inventory is not None
    original_quantity = inventory.quantity_on_hand

    catalog = CatalogService(db_session, threshold_policy=ProposedLimitedStockThresholdPolicy())
    await catalog.get_sku(sku="MOB-WLK-ADJ-BLU")
    await catalog.search(filters=CatalogSearchFilters(category="MOB"))
    await catalog.find_alternatives(sku="MOB-WLK-ADJ-BLU", quantity=4)
    await InventoryService(db_session).check_availability(sku="MOB-WLK-ADJ-BLU", quantity=1)
    await db_session.refresh(inventory)

    assert inventory.quantity_on_hand == original_quantity


@pytest.mark.asyncio
async def test_all_verified_compatibility_pairs_are_order_independent(
    db_session: AsyncSession,
) -> None:
    service = CatalogService(db_session)
    expected_pairs = {
        ("DIA-GC-MTR-G1", "DIA-GC-STR-50"): CompatibilityState.COMPATIBLE,
        ("DIA-GC-MTR-G1", "DIA-GC-STR-100"): CompatibilityState.COMPATIBLE,
        ("DIA-GC-MTR-G1", "DIA-GC-CTRL"): CompatibilityState.COMPATIBLE,
        ("DIA-NT-MTR-N2", "DIA-NT-STR-50"): CompatibilityState.COMPATIBLE,
        ("DIA-CS-LDEV", "DIA-CS-LAN-30G"): CompatibilityState.COMPATIBLE,
        ("DIA-CS-LDEV", "DIA-CS-LAN-33G"): CompatibilityState.COMPATIBLE,
        ("DIA-GC-MTR-G1", "DIA-NT-STR-50"): CompatibilityState.INCOMPATIBLE,
    }

    for (first_sku, second_sku), state in expected_pairs.items():
        assert (
            await service.check_compatibility(first_sku=first_sku, second_sku=second_sku)
        ).state == state
        assert (
            await service.check_compatibility(first_sku=second_sku, second_sku=first_sku)
        ).state == state

    assert (
        await service.check_compatibility(first_sku="external-meter", second_sku="DIA-GC-STR-50")
    ).state == CompatibilityState.UNKNOWN


@pytest.mark.asyncio
async def test_alternatives_are_conservative_sufficient_and_explain_differences(
    db_session: AsyncSession,
) -> None:
    alternatives = await CatalogService(db_session).find_alternatives(
        sku="MOB-WLK-ADJ-BLU", quantity=4
    )

    assert len(alternatives) == 1
    assert alternatives[0].variant.sku == "MOB-WLK-ADJ-SLV"
    assert alternatives[0].difference == "Color: silver instead of blue."


@pytest.mark.asyncio
async def test_alternatives_preserve_hard_requirements_and_exclude_unsafe_candidates(
    db_session: AsyncSession,
) -> None:
    service = CatalogService(db_session)

    assert await service.find_alternatives(sku="PPE-NIT-M", quantity=30) == ()
    assert await service.find_alternatives(sku="CON-SPILL-1", quantity=1) == ()
