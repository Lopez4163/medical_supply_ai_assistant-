"""Validated read-only LangGraph tools over deterministic application services."""

from __future__ import annotations

from base64 import b64decode, urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from hmac import compare_digest, new
from json import JSONDecodeError, dumps, loads
from typing import Protocol

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import get_settings
from app.services.catalog import CatalogSearchFilters, CatalogService
from app.services.company_info import CompanyFact, CompanyInfoService
from app.services.inventory import InventoryService

MAX_RESULTS = 5
MAX_ALTERNATIVES = 3
CURSOR_TTL = timedelta(minutes=5)
_CURSOR_VERSION = 1


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchProductsInput(ToolInput):
    query: str | None = Field(default=None, min_length=1, max_length=200)
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    product_id: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    size: str | None = Field(default=None, min_length=1, max_length=64)
    material: str | None = Field(default=None, min_length=1, max_length=64)
    product_type: str | None = Field(default=None, min_length=1, max_length=64)
    model_system: str | None = Field(default=None, min_length=1, max_length=128)
    capacity: str | int | None = Field(default=None)
    sales_unit: str | None = Field(default=None, min_length=1, max_length=128)
    attributes: dict[str, str | int | bool] | None = Field(default=None)
    cursor: str | None = Field(default=None, min_length=1, max_length=500)

    def to_filters(self) -> CatalogSearchFilters:
        return CatalogSearchFilters(
            query=self.query,
            sku=self.sku,
            product_id=self.product_id,
            category=self.category,
            size=self.size,
            material=self.material,
            product_type=self.product_type,
            model_system=self.model_system,
            capacity=self.capacity,
            sales_unit=self.sales_unit,
            attributes=self.attributes,
        )

    def cursor_context(self) -> dict[str, object]:
        """Canonical public search context; the session is added server-side."""
        values = self.model_dump(exclude={"cursor"})
        return {key: self._normalize_context_value(value) for key, value in values.items()}

    @staticmethod
    def _normalize_context_value(value: object) -> object:
        if isinstance(value, str):
            return value.strip().casefold()
        if isinstance(value, dict):
            return {
                str(key).strip().casefold(): SearchProductsInput._normalize_context_value(item)
                for key, item in sorted(value.items())
            }
        return value


class SkuInput(ToolInput):
    sku: str = Field(min_length=1, max_length=64)


class AvailabilityInput(SkuInput):
    quantity: int = Field(gt=0)


class AlternativesInput(AvailabilityInput):
    compatible_with_sku: str | None = Field(default=None, max_length=64)


class CompanyInfoInput(ToolInput):
    fact: CompanyFact


class ProductToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str
    product_id: str
    name: str
    sales_unit: str
    indicative_price_usd: Decimal
    availability: str


class ReadOnlyToolSet(Protocol):
    async def search_products(self, value: SearchProductsInput) -> dict[str, object]: ...
    async def get_product_details(self, value: SkuInput) -> dict[str, object]: ...
    async def check_availability(self, value: AvailabilityInput) -> dict[str, object]: ...
    async def find_alternatives(self, value: AlternativesInput) -> dict[str, object]: ...
    async def get_company_info(self, value: CompanyInfoInput) -> dict[str, object]: ...


class ReadOnlyTools:
    def __init__(
        self,
        catalog: CatalogService,
        inventory: InventoryService,
        *,
        session_context: str,
        company_info: CompanyInfoService | None = None,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._session_context = session_context
        self._company_info = company_info or CompanyInfoService()

    async def search_products(self, value: SearchProductsInput) -> dict[str, object]:
        offset = self._decode_cursor(value) if value.cursor else 0
        if offset is None:
            return {"products": [], "next_cursor": None, "error": "invalid_cursor"}
        results = await self._catalog.search(filters=value.to_filters())
        page = results[offset : offset + MAX_RESULTS]
        products = [await self._public_product(item.sku) for item in page]
        next_offset = offset + len(page)
        return {
            "products": products,
            "next_cursor": self._encode_cursor(value.cursor_context(), next_offset)
            if len(results) > next_offset
            else None,
        }

    @staticmethod
    def _cursor_key() -> bytes:
        """Derive a dedicated cursor key from the configured server secret."""
        secret = get_settings().session_token_hash_secret.get_secret_value().encode()
        return new(secret, b"ai-02-read-only-search-cursor", sha256).digest()

    def _encode_cursor(
        self, context: dict[str, object], offset: int, *, expires_at: datetime | None = None
    ) -> str:
        expiry = expires_at or datetime.now(UTC) + CURSOR_TTL
        payload = dumps(
            {
                "e": expiry.timestamp(),
                "o": offset,
                "c": context,
                "s": self._session_context,
                "v": _CURSOR_VERSION,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        encoded = urlsafe_b64encode(payload).rstrip(b"=")
        signature = urlsafe_b64encode(new(self._cursor_key(), encoded, sha256).digest()).rstrip(
            b"="
        )
        return f"{encoded.decode()}.{signature.decode()}"

    def _decode_cursor(self, value: SearchProductsInput) -> int | None:
        try:
            if value.cursor is None:
                return None
            encoded, signature = value.cursor.encode().split(b".", 1)
            expected = new(self._cursor_key(), encoded, sha256).digest()
            provided = b64decode(
                signature + b"=" * (-len(signature) % 4), altchars=b"-_", validate=True
            )
            payload = loads(urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4)))
            if (
                not isinstance(payload, dict)
                or not compare_digest(provided, expected)
                or payload.get("v") != _CURSOR_VERSION
                or payload.get("c") != value.cursor_context()
                or payload.get("s") != self._session_context
                or not isinstance(payload.get("e"), (int, float))
                or payload["e"] <= datetime.now(UTC).timestamp()
                or not isinstance(payload.get("o"), int)
                or payload["o"] < MAX_RESULTS
                or payload["o"] % MAX_RESULTS != 0
            ):
                return None
            return payload["o"]
        except JSONDecodeError, TypeError, ValueError:
            return None

    async def get_product_details(self, value: SkuInput) -> dict[str, object]:
        product = await self._public_product(value.sku)
        if product is None:
            return {"found": False}
        family = await self._catalog.get_product_family(product_id=str(product["product_id"]))
        return {
            "found": True,
            "product": product,
            "variant_skus": [item.sku for item in family.variants] if family else [],
        }

    async def check_availability(self, value: AvailabilityInput) -> dict[str, object]:
        result = await self._inventory.check_availability(sku=value.sku, quantity=value.quantity)
        return {
            "sku": result.sku,
            "availability": result.availability.value,
            "quantity_sufficient": result.is_sufficient,
        }

    async def find_alternatives(self, value: AlternativesInput) -> dict[str, object]:
        alternatives = await self._catalog.find_alternatives(
            sku=value.sku, quantity=value.quantity, compatible_with_sku=value.compatible_with_sku
        )
        return {
            "alternatives": [
                {
                    "product": await self._public_product(item.variant.sku),
                    "difference": item.difference,
                }
                for item in alternatives[:MAX_ALTERNATIVES]
            ]
        }

    async def get_company_info(self, value: CompanyInfoInput) -> dict[str, object]:
        result = await self._company_info.get_fact(fact=value.fact)
        return {"fact": result.fact, "value": result.value, "status": "approved_demo_fact"}

    async def _public_product(self, sku: str) -> dict[str, object] | None:
        variant = await self._catalog.get_sku(sku=sku)
        if variant is None:
            return None
        availability = await self._inventory.check_availability(sku=variant.sku, quantity=1)
        return ProductToolResult(
            sku=variant.sku,
            product_id=variant.product_id,
            name=variant.name,
            sales_unit=variant.sales_unit,
            indicative_price_usd=variant.indicative_price,
            availability=availability.availability.value,
        ).model_dump(mode="json")


def create_read_only_langchain_tools(delegate: ReadOnlyToolSet) -> list[BaseTool]:
    """Expose only validated read-only service adapters to the LangGraph ToolNode."""

    @tool("search_products", args_schema=SearchProductsInput)
    async def search_products(**kwargs: object) -> dict[str, object]:
        """Search approved catalog data without changing customer or inventory state."""
        return await delegate.search_products(SearchProductsInput.model_validate(kwargs))

    @tool("get_product_details", args_schema=SkuInput)
    async def get_product_details(**kwargs: object) -> dict[str, object]:
        """Get one resolved sellable SKU and its product-family variants."""
        return await delegate.get_product_details(SkuInput.model_validate(kwargs))

    @tool("check_availability", args_schema=AvailabilityInput)
    async def check_availability(**kwargs: object) -> dict[str, object]:
        """Return categorical availability for a positive requested quantity."""
        return await delegate.check_availability(AvailabilityInput.model_validate(kwargs))

    @tool("find_alternatives", args_schema=AlternativesInput)
    async def find_alternatives(**kwargs: object) -> dict[str, object]:
        """Return at most three validated compatible alternatives."""
        return await delegate.find_alternatives(AlternativesInput.model_validate(kwargs))

    @tool("get_company_info", args_schema=CompanyInfoInput)
    async def get_company_info(**kwargs: object) -> dict[str, object]:
        """Return an approved synthetic business-information fact."""
        return await delegate.get_company_info(CompanyInfoInput.model_validate(kwargs))

    return [
        search_products,
        get_product_details,
        check_availability,
        find_alternatives,
        get_company_info,
    ]
