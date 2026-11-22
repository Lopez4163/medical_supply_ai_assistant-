from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.products import get_db_session
from app.db.session import get_database_engine
from app.dev.seed_catalog import seed_catalog
from app.main import app
from app.models.catalog import InventoryItem, SkuVariant


@pytest_asyncio.fixture
async def client_and_session() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    engine = get_database_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def get_test_db_session() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_db_session] = get_test_db_session
        try:
            await seed_catalog(session)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client, session
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


def _contains_private_stock(value: object) -> bool:
    return "quantity_on_hand" in json.dumps(value)


@pytest.mark.asyncio
async def test_search_resolves_exact_sku_with_public_safe_limited_availability(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    response = await client.get("/api/v1/products/search", params={"sku": "ppe-nit-m"})

    assert response.status_code == 200
    payload = response.json()
    assert [product["sku"] for product in payload["products"]] == ["PPE-NIT-M"]
    assert payload["products"][0]["availability"] == "limited_stock"
    assert payload["next_cursor"] is None
    assert not _contains_private_stock(payload)


@pytest.mark.asyncio
async def test_search_parent_id_preserves_multiple_sellable_variants(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    response = await client.get("/api/v1/products/search", params={"product_id": "ppe-001"})

    assert response.status_code == 200
    assert {product["sku"] for product in response.json()["products"]} == {
        "PPE-NIT-S",
        "PPE-NIT-M",
        "PPE-NIT-L",
    }


@pytest.mark.asyncio
async def test_search_enforces_structured_filters_and_returns_five_cards_at_most(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    filtered = await client.get(
        "/api/v1/products/search",
        params={"q": "nitrile gloves", "category": "PPE", "size": "medium", "material": "nitrile"},
    )
    first_page = await client.get("/api/v1/products/search", params={"category": "MOB"})

    assert [product["sku"] for product in filtered.json()["products"]] == ["PPE-NIT-M"]
    assert len(first_page.json()["products"]) == 5
    assert first_page.json()["next_cursor"] is not None


@pytest.mark.asyncio
async def test_search_handles_casefolded_unicode_empty_and_unknown_attribute_queries(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    casefolded = await client.get("/api/v1/products/search", params={"q": "NITRILE GLOVES"})
    unicode_query = await client.get("/api/v1/products/search", params={"q": "nitrile gloves ✚"})
    empty = await client.get("/api/v1/products/search", params={"q": "not-a-synthetic-product"})
    unknown_attribute = await client.get(
        "/api/v1/products/search",
        params={"attribute_key": "not_a_catalog_attribute", "attribute_value": "value"},
    )

    assert [product["sku"] for product in casefolded.json()["products"]] == [
        product["sku"] for product in unicode_query.json()["products"]
    ]
    assert casefolded.json()["products"]
    assert empty.json() == {"products": [], "next_cursor": None}
    assert unknown_attribute.json() == {"products": [], "next_cursor": None}


@pytest.mark.asyncio
async def test_search_validates_attribute_pairing_and_filters_generic_attributes(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    missing_value = await client.get("/api/v1/products/search", params={"attribute_key": "color"})
    missing_key = await client.get("/api/v1/products/search", params={"attribute_value": "blue"})
    generic_filter = await client.get(
        "/api/v1/products/search",
        params={"category": "MOB", "attribute_key": "color", "attribute_value": "blue"},
    )

    assert missing_value.status_code == missing_key.status_code == 422
    assert [product["sku"] for product in generic_filter.json()["products"]] == ["MOB-WLK-ADJ-BLU"]


@pytest.mark.asyncio
async def test_search_order_is_stable_when_matching_cursor_context_is_repeated(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    first = await client.get("/api/v1/products/search", params={"category": "MOB"})
    repeated = await client.get("/api/v1/products/search", params={"category": "MOB"})
    cursor = first.json()["next_cursor"]
    assert cursor is not None
    second = await client.get(
        "/api/v1/products/search", params={"category": "MOB", "cursor": cursor}
    )

    assert [product["sku"] for product in first.json()["products"]] == [
        product["sku"] for product in repeated.json()["products"]
    ]
    assert not {product["sku"] for product in first.json()["products"]}.intersection(
        product["sku"] for product in second.json()["products"]
    )


@pytest.mark.asyncio
async def test_search_cursor_preserves_context_without_duplicates_or_skips(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session
    first = await client.get("/api/v1/products/search", params={"category": "MOB"})
    first_payload = first.json()
    second = await client.get(
        "/api/v1/products/search", params={"cursor": first_payload["next_cursor"]}
    )
    second_payload = second.json()
    third = await client.get(
        "/api/v1/products/search", params={"cursor": second_payload["next_cursor"]}
    )
    third_payload = third.json()

    assert first.status_code == second.status_code == third.status_code == 200
    skus = [
        product["sku"]
        for payload in (first_payload, second_payload, third_payload)
        for product in payload["products"]
    ]
    assert len(skus) == 13
    assert len(skus) == len(set(skus))
    assert third_payload["next_cursor"] is None


@pytest.mark.asyncio
async def test_search_rejects_malformed_modified_and_mismatched_cursors(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session
    first = await client.get("/api/v1/products/search", params={"category": "MOB"})
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    malformed = await client.get("/api/v1/products/search", params={"cursor": "not-a-cursor"})
    modified = await client.get("/api/v1/products/search", params={"cursor": f"{cursor}x"})
    mismatched = await client.get(
        "/api/v1/products/search", params={"category": "PPE", "cursor": cursor}
    )

    assert malformed.status_code == modified.status_code == mismatched.status_code == 422


@pytest.mark.asyncio
async def test_product_detail_is_normalized_public_safe_and_handles_discontinued(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    detail = await client.get("/api/v1/products/ppe-nit-m")
    discontinued = await client.get("/api/v1/products/CON-SPILL-1")
    missing = await client.get("/api/v1/products/UNKNOWN")

    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["sku"] == "PPE-NIT-M"
    assert detail_payload["sales_unit"] == "100/box"
    assert detail_payload["indicative_price_usd"] == "11.00"
    assert detail_payload["image_fallback_key"] == "PH PPE"
    assert detail_payload["availability"] == "limited_stock"
    assert not _contains_private_stock(detail_payload)
    assert discontinued.status_code == 200
    assert discontinued.json()["lifecycle_status"] == "discontinued"
    assert discontinued.json()["availability"] == "discontinued"
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_product_detail_returns_the_approved_missing_image_fallback(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    response = await client.get("/api/v1/products/MOB-RLT-STD")

    assert response.status_code == 200
    assert response.json()["primary_image_reference"] is None
    assert response.json()["image_fallback_key"] == "PH Mobility"


@pytest.mark.asyncio
async def test_availability_uses_current_stock_without_exposing_or_mutating_it(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = client_and_session
    inventory = await session.scalar(
        select(InventoryItem)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == "PPE-NIT-M")
    )
    assert inventory is not None
    original_quantity = inventory.quantity_on_hand

    sufficient = await client.post(
        "/api/v1/products/availability", json={"sku": "ppe-nit-m", "quantity": 15}
    )
    insufficient = await client.post(
        "/api/v1/products/availability", json={"sku": "PPE-NIT-M", "quantity": 30}
    )
    await session.refresh(inventory)

    assert sufficient.status_code == insufficient.status_code == 200
    assert sufficient.json() == {
        "sku": "PPE-NIT-M",
        "availability": "limited_stock",
        "quantity_sufficient": True,
        "message": "Limited availability for the requested quantity.",
    }
    assert insufficient.json()["quantity_sufficient"] is False
    assert not _contains_private_stock(insufficient.json())
    assert inventory.quantity_on_hand == original_quantity


@pytest.mark.asyncio
async def test_availability_preserves_limited_status_at_and_above_quantity_boundary(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _session = client_and_session

    exact_stock = await client.post(
        "/api/v1/products/availability", json={"sku": "MOB-WLK-ADJ-BLU", "quantity": 3}
    )
    excess_stock = await client.post(
        "/api/v1/products/availability", json={"sku": "MOB-WLK-ADJ-BLU", "quantity": 4}
    )

    assert (
        exact_stock.json()["availability"] == excess_stock.json()["availability"] == "limited_stock"
    )
    assert exact_stock.json()["quantity_sufficient"] is True
    assert excess_stock.json()["quantity_sufficient"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sku", "expected_availability"),
    [
        ("MOB-WLK-ADJ-BLU", "limited_stock"),
        ("MOB-WLK-ADJ-SLV", "in_stock"),
        ("DIA-GC-MTR-G1", "in_stock"),
        ("DIA-GC-STR-100", "limited_stock"),
        ("OTC-COMP-L", "limited_stock"),
    ],
)
async def test_availability_uses_the_approved_default_threshold_policy(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
    sku: str,
    expected_availability: str,
) -> None:
    client, _session = client_and_session

    response = await client.post("/api/v1/products/availability", json={"sku": sku, "quantity": 1})

    assert response.status_code == 200
    assert response.json()["availability"] == expected_availability


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", [0, -1, True, 1.5, "1", None])
async def test_availability_rejects_invalid_requested_quantities(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession], quantity: object
) -> None:
    client, _session = client_and_session

    response = await client.post(
        "/api/v1/products/availability", json={"sku": "PPE-NIT-M", "quantity": quantity}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_availability_distinguishes_out_discontinued_and_missing_inventory(
    client_and_session: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = client_and_session
    out_of_stock = await client.post(
        "/api/v1/products/availability", json={"sku": "CON-UNDER-10", "quantity": 1}
    )
    discontinued = await client.post(
        "/api/v1/products/availability", json={"sku": "CON-SPILL-1", "quantity": 1}
    )
    inventory = await session.scalar(
        select(InventoryItem)
        .join(SkuVariant, InventoryItem.sku_variant_id == SkuVariant.id)
        .where(SkuVariant.sku == "PPE-NIT-M")
    )
    assert inventory is not None
    await session.delete(inventory)
    await session.flush()
    unavailable = await client.post(
        "/api/v1/products/availability", json={"sku": "PPE-NIT-M", "quantity": 1}
    )

    assert out_of_stock.json()["availability"] == "out_of_stock"
    assert discontinued.json()["availability"] == "discontinued"
    assert unavailable.json()["availability"] == "unavailable"
    assert unavailable.json()["quantity_sufficient"] is False


def test_openapi_catalog_contracts_do_not_expose_private_stock() -> None:
    schema = app.openapi()

    assert "quantity_on_hand" not in json.dumps(schema)
