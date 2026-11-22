from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import (
    AlternativesInput,
    AvailabilityInput,
    CompanyInfoInput,
    ReadOnlyTools,
    SearchProductsInput,
    SkuInput,
)
from app.db.session import get_database_engine
from app.dev.seed_catalog import seed_catalog
from app.services.catalog import CatalogService
from app.services.inventory import InventoryService


@pytest_asyncio.fixture
async def tools() -> AsyncIterator[ReadOnlyTools]:
    async with get_database_engine().connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            await seed_catalog(session)
            yield ReadOnlyTools(
                CatalogService(session), InventoryService(session), session_context="guest-a"
            )
        finally:
            await session.close()
            await transaction.rollback()


@pytest.mark.asyncio
async def test_search_pages_at_five_and_details_preserve_variants(tools: ReadOnlyTools) -> None:
    first = await tools.search_products(SearchProductsInput(query="a", category="ppe"))
    assert isinstance(first["products"], list) and len(first["products"]) <= 5
    assert isinstance(first["next_cursor"], str)
    second = await tools.search_products(
        SearchProductsInput(query="a", category="PPE", cursor=first["next_cursor"])
    )
    assert first["products"] != second["products"]
    detail = await tools.get_product_details(SkuInput(sku="PPE-NIT-M"))
    assert detail["found"] is True and isinstance(detail["variant_skus"], list)
    assert "PPE-NIT-S" in detail["variant_skus"]


@pytest.mark.asyncio
async def test_search_cursor_rejects_malformed_tampered_expired_and_cross_context(
    tools: ReadOnlyTools,
) -> None:
    first = await tools.search_products(SearchProductsInput(query="a", category="PPE"))
    cursor = first["next_cursor"]
    assert isinstance(cursor, str)

    for invalid_cursor in ("not-a-cursor", f"{cursor}x"):
        result = await tools.search_products(
            SearchProductsInput(query="a", category="PPE", cursor=invalid_cursor)
        )
        assert result == {"products": [], "next_cursor": None, "error": "invalid_cursor"}

    expired = tools._encode_cursor(
        SearchProductsInput(query="a", category="PPE").cursor_context(),
        5,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await tools.search_products(
        SearchProductsInput(query="a", category="PPE", cursor=expired)
    ) == {
        "products": [],
        "next_cursor": None,
        "error": "invalid_cursor",
    }

    other_guest_tools = ReadOnlyTools(tools._catalog, tools._inventory, session_context="guest-b")
    assert await other_guest_tools.search_products(
        SearchProductsInput(query="a", category="PPE", cursor=cursor)
    ) == {
        "products": [],
        "next_cursor": None,
        "error": "invalid_cursor",
    }
    assert await tools.search_products(
        SearchProductsInput(query="different", category="PPE", cursor=cursor)
    ) == {
        "products": [],
        "next_cursor": None,
        "error": "invalid_cursor",
    }
    assert await tools.search_products(
        SearchProductsInput(query="a", category="DIA", cursor=cursor)
    ) == {
        "products": [],
        "next_cursor": None,
        "error": "invalid_cursor",
    }


@pytest.mark.asyncio
async def test_invalid_sku_unavailable_and_alternatives_are_safe(tools: ReadOnlyTools) -> None:
    assert await tools.get_product_details(SkuInput(sku="MISSING")) == {"found": False}
    availability = await tools.check_availability(AvailabilityInput(sku="CON-UNDER-10", quantity=1))
    assert availability["availability"] == "out_of_stock" and "quantity_on_hand" not in availability
    alternatives = await tools.find_alternatives(AlternativesInput(sku="CON-UNDER-10", quantity=1))
    assert isinstance(alternatives["alternatives"], list) and len(alternatives["alternatives"]) <= 3
    assert (await tools.get_company_info(CompanyInfoInput(fact="hours")))[
        "status"
    ] == "approved_demo_fact"
