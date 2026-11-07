"""Seed the approved synthetic catalog into an already migrated local database."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import and_, or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.dev.catalog_fixtures import CATALOG_FIXTURE, CatalogFixture
from app.models.catalog import (
    CatalogLifecycleStatus,
    ImageProvenanceStatus,
    InventoryItem,
    ProductCategory,
    ProductListing,
    SkuCompatibility,
    SkuVariant,
)

CATALOG_NAMESPACE = UUID("4a1db331-e16f-405d-868a-ef362bcf09c9")


class CatalogSeedError(Exception):
    """Base error for safe catalog seed failures."""


class CatalogSeedConflictError(CatalogSeedError):
    """Raised when existing catalog data differs from the approved fixture."""


class CatalogSeedSafetyError(CatalogSeedError):
    """Raised when the command target is not an approved local seed database."""


@dataclass(frozen=True)
class SeedSummary:
    categories: int
    listings: int
    variants: int
    inventory_items: int
    compatibilities: int


def stable_id(kind: str, identifier: str) -> UUID:
    return uuid5(CATALOG_NAMESPACE, f"{kind}:{identifier}")


def validate_fixture(fixture: CatalogFixture) -> None:
    category_codes = [category.code for category in fixture.categories]
    product_ids = [product.product_id for product in fixture.products]
    skus = [variant.sku for product in fixture.products for variant in product.variants]

    if len(category_codes) != 9 or len(set(category_codes)) != len(category_codes):
        raise CatalogSeedError(
            "Approved catalog fixture must contain exactly nine unique categories."
        )
    if len(product_ids) != 80 or len(set(product_ids)) != len(product_ids):
        raise CatalogSeedError(
            "Approved catalog fixture must contain exactly 80 unique product listings."
        )
    if len(skus) != 100 or len(set(skus)) != len(skus):
        raise CatalogSeedError(
            "Approved catalog fixture must contain exactly 100 unique sellable SKUs."
        )
    if any(product.category_code not in category_codes for product in fixture.products):
        raise CatalogSeedError(
            "Every approved product listing must reference an approved category."
        )
    if any(
        variant.indicative_price <= 0
        for product in fixture.products
        for variant in product.variants
    ):
        raise CatalogSeedError("Approved catalog fixture contains a nonpositive price.")
    if any(
        variant.quantity_on_hand < 0 for product in fixture.products for variant in product.variants
    ):
        raise CatalogSeedError("Approved catalog fixture contains negative inventory.")

    sku_set = set(skus)
    compatibility_pairs: set[frozenset[str]] = set()
    for compatibility in fixture.compatibilities:
        pair = frozenset((compatibility.source_sku, compatibility.target_sku))
        if (
            compatibility.source_sku not in sku_set
            or compatibility.target_sku not in sku_set
            or len(pair) != 2
        ):
            raise CatalogSeedError(
                "Catalog compatibility must reference two distinct approved SKUs."
            )
        if pair in compatibility_pairs:
            raise CatalogSeedError("Catalog fixture contains a duplicate compatibility pair.")
        compatibility_pairs.add(pair)


def _conflict(entity: str, identifier: str) -> CatalogSeedConflictError:
    return CatalogSeedConflictError(
        f"Existing {entity} {identifier!r} differs from the approved synthetic catalog fixture."
    )


async def _assert_no_unexpected_catalog_rows(
    session: AsyncSession, fixture: CatalogFixture
) -> None:
    expected_category_ids = {
        stable_id("category", category.code) for category in fixture.categories
    }
    expected_listing_ids = {
        stable_id("listing", product.product_id) for product in fixture.products
    }
    expected_variant_ids = {
        stable_id("variant", variant.sku)
        for product in fixture.products
        for variant in product.variants
    }
    expected_inventory_ids = {
        stable_id("inventory", variant.sku)
        for product in fixture.products
        for variant in product.variants
    }
    expected_compatibility_ids = {
        stable_id("compatibility", f"{item.source_sku}:{item.target_sku}")
        for item in fixture.compatibilities
    }

    checks = (
        (ProductCategory.id, expected_category_ids, "category"),
        (ProductListing.id, expected_listing_ids, "listing"),
        (SkuVariant.id, expected_variant_ids, "SKU variant"),
        (InventoryItem.id, expected_inventory_ids, "inventory item"),
        (SkuCompatibility.id, expected_compatibility_ids, "compatibility relationship"),
    )
    for column, expected_ids, entity in checks:
        actual_ids = set((await session.scalars(select(column))).all())
        if unexpected_ids := actual_ids - expected_ids:
            raise CatalogSeedConflictError(
                f"Database contains unexpected {entity} rows: {sorted(map(str, unexpected_ids))}."
            )


async def seed_catalog(
    session: AsyncSession,
    fixture: CatalogFixture = CATALOG_FIXTURE,
) -> SeedSummary:
    """Insert the approved fixture once or verify that an identical seed already exists."""
    validate_fixture(fixture)

    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    async with transaction:
        category_ids: dict[str, UUID] = {}
        for category in fixture.categories:
            category_id = stable_id("category", category.code)
            existing = await session.scalar(
                select(ProductCategory).where(ProductCategory.code == category.code)
            )
            if existing is None:
                session.add(
                    ProductCategory(
                        id=category_id,
                        code=category.code,
                        name=category.name,
                        is_active=True,
                    )
                )
            elif (
                existing.id != category_id
                or existing.name != category.name
                or not existing.is_active
            ):
                raise _conflict("category", category.code)
            category_ids[category.code] = category_id

        await session.flush()

        variant_ids: dict[str, UUID] = {}
        for product in fixture.products:
            listing_id = stable_id("listing", product.product_id)
            existing_listing = await session.scalar(
                select(ProductListing).where(ProductListing.product_id == product.product_id)
            )
            expected_listing = {
                "id": listing_id,
                "category_id": category_ids[product.category_code],
                "name": product.name,
                "description": product.description,
                "searchable_attributes": product.searchable_attributes,
                "lifecycle_status": CatalogLifecycleStatus.ACTIVE,
                "primary_image_reference": None,
                "image_fallback_key": product.image_fallback_key,
                "image_provenance_status": ImageProvenanceStatus.PLACEHOLDER,
            }
            if existing_listing is None:
                session.add(ProductListing(**expected_listing, product_id=product.product_id))
            elif any(
                getattr(existing_listing, field) != value
                for field, value in expected_listing.items()
            ):
                raise _conflict("product listing", product.product_id)

            for variant in product.variants:
                variant_id = stable_id("variant", variant.sku)
                existing_variant = await session.scalar(
                    select(SkuVariant).where(SkuVariant.sku == variant.sku)
                )
                expected_variant = {
                    "id": variant_id,
                    "listing_id": listing_id,
                    "selector_attributes": variant.selector_attributes,
                    "searchable_attributes": variant.searchable_attributes,
                    "sales_unit": variant.sales_unit,
                    "indicative_price": variant.indicative_price,
                    "lifecycle_status": variant.lifecycle_status,
                }
                if existing_variant is None:
                    session.add(SkuVariant(**expected_variant, sku=variant.sku))
                elif any(
                    getattr(existing_variant, field) != value
                    for field, value in expected_variant.items()
                ):
                    raise _conflict("SKU variant", variant.sku)
                variant_ids[variant.sku] = variant_id

        await session.flush()

        for product in fixture.products:
            for variant in product.variants:
                inventory_id = stable_id("inventory", variant.sku)
                variant_id = variant_ids[variant.sku]
                existing_inventory = await session.scalar(
                    select(InventoryItem).where(InventoryItem.sku_variant_id == variant_id)
                )
                if existing_inventory is None:
                    session.add(
                        InventoryItem(
                            id=inventory_id,
                            sku_variant_id=variant_id,
                            quantity_on_hand=variant.quantity_on_hand,
                        )
                    )
                elif (
                    existing_inventory.id != inventory_id
                    or existing_inventory.quantity_on_hand != variant.quantity_on_hand
                ):
                    raise _conflict("inventory", variant.sku)

        await session.flush()

        for compatibility in fixture.compatibilities:
            source_variant_id = variant_ids[compatibility.source_sku]
            target_variant_id = variant_ids[compatibility.target_sku]
            compatibility_id = stable_id(
                "compatibility", f"{compatibility.source_sku}:{compatibility.target_sku}"
            )
            existing = await session.scalar(
                select(SkuCompatibility).where(
                    or_(
                        and_(
                            SkuCompatibility.source_variant_id == source_variant_id,
                            SkuCompatibility.target_variant_id == target_variant_id,
                        ),
                        and_(
                            SkuCompatibility.source_variant_id == target_variant_id,
                            SkuCompatibility.target_variant_id == source_variant_id,
                        ),
                    )
                )
            )
            if existing is None:
                session.add(
                    SkuCompatibility(
                        id=compatibility_id,
                        source_variant_id=source_variant_id,
                        target_variant_id=target_variant_id,
                        state=compatibility.state,
                    )
                )
            elif (
                existing.id != compatibility_id
                or existing.source_variant_id != source_variant_id
                or existing.target_variant_id != target_variant_id
                or existing.state != compatibility.state
            ):
                raise _conflict("compatibility relationship", compatibility_id.hex)

        await session.flush()
        await _assert_no_unexpected_catalog_rows(session, fixture)

    return SeedSummary(
        categories=len(fixture.categories),
        listings=len(fixture.products),
        variants=sum(len(product.variants) for product in fixture.products),
        inventory_items=sum(len(product.variants) for product in fixture.products),
        compatibilities=len(fixture.compatibilities),
    )


def _expected_database_name(environment: str) -> str:
    return "medical_supply" if environment == "development" else "medical_supply_test"


async def run_command(environment: str) -> SeedSummary:
    settings = get_settings()
    database_url = make_url(settings.database_url)
    database_name = database_url.database
    expected_database_name = _expected_database_name(environment)
    if database_name != expected_database_name:
        raise CatalogSeedSafetyError(
            f"Refusing to seed database {database_name!r}; expected {expected_database_name!r}."
        )
    if database_url.host not in {"127.0.0.1", "localhost"}:
        raise CatalogSeedSafetyError(
            "Catalog seeding is restricted to a local loopback PostgreSQL host."
        )

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            try:
                return await seed_catalog(session)
            except SQLAlchemyError as error:
                raise CatalogSeedSafetyError(
                    "Catalog tables are unavailable; run 'alembic upgrade head' before seeding."
                ) from error
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("development", "test"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = asyncio.run(run_command(args.environment))
    print(
        "Catalog seed complete: "
        f"{summary.categories} categories, {summary.listings} listings, "
        f"{summary.variants} variants, {summary.inventory_items} inventory items, "
        f"{summary.compatibilities} compatibility relationships."
    )


if __name__ == "__main__":
    main()
