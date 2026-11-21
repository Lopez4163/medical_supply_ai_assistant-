"""Replaceable deterministic mock implementation of the chat orchestration boundary."""

from __future__ import annotations

import re
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Sequence
from hashlib import sha256
from hmac import compare_digest, new
from json import dumps, loads
from typing import Protocol
from uuid import uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.schemas.chat import ChatTurnRequest, ChatTurnResponse
from app.schemas.conversations import (
    AssistantElement,
    ConfirmationPromptElement,
    ConfirmationPromptSnapshot,
    ConversationMessagePublic,
    InventoryNoticeElement,
    ProductResultsElement,
    QuoteUpdateElement,
    QuoteUpdateSnapshot,
    SupportInquiryFormElement,
    SupportInquiryFormSnapshot,
)
from app.schemas.products import AvailabilityResponse, ProductCardPublic, ProductSearchResponse
from app.services.catalog import CatalogSearchFilters, CatalogService, CatalogVariant
from app.services.conversations import ConversationService
from app.services.inventory import InventoryService
from app.services.quotations import (
    QuotationService,
    QuoteLineNotFound,
    QuoteSessionInvalid,
    QuoteSkuNotFound,
    QuoteSkuUnresolved,
    QuoteVersionConflict,
)
from app.services.sessions import GuestContext

_SKU_PATTERN = re.compile(r"\b([A-Z]{2,4}(?:-[A-Z0-9]+){1,4})\b", re.IGNORECASE)
_ADD_COMMAND = re.compile(
    r"^add\s+(?P<quantity>[1-9]\d*)\s+(?P<sku>[A-Z]{2,4}(?:-[A-Z0-9]+){1,4})$",
    re.IGNORECASE,
)
_REMOVE_COMMAND = re.compile(r"^remove\s+(?P<sku>[A-Z]{2,4}(?:-[A-Z0-9]+){1,4})$", re.IGNORECASE)
_UPDATE_PATTERN = re.compile(
    r"^(?:update|change)\s+(?P<sku>[A-Z]{2,4}(?:-[A-Z0-9]+){1,4})\s+to\s+"
    r"(?P<quantity>[1-9]\d*)$",
    re.IGNORECASE,
)
_SHOW_MORE_COMMAND = "show more"
_RESULTS_PER_PAGE = 5


class ChatProvider(Protocol):
    """Stable provider boundary retained when AI-06 adds LangGraph."""

    async def respond(
        self, *, guest: GuestContext, request: ChatTurnRequest
    ) -> ChatTurnResponse: ...


class MockChatService:
    """Own one complete mock turn; a future LangGraph provider replaces only routing."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._conversations = ConversationService(session)
        self._quotations = QuotationService(session, settings)

    async def respond(self, *, guest: GuestContext, request: ChatTurnRequest) -> ChatTurnResponse:
        transaction = (
            self._session.begin_nested()
            if self._session.in_transaction()
            else self._session.begin()
        )
        async with transaction:
            # Locking the session-scoped conversation makes a duplicate client message wait for
            # the first turn and then return its committed display snapshot instead of re-running.
            existing = await self._conversations.get_completed_turn(
                guest=guest, client_message_id=request.client_message_id, lock=True
            )
            if existing is not None:
                user_message, assistant_message = existing
                return self._response(
                    guest=guest,
                    request=request,
                    user_message=user_message,
                    assistant_message=assistant_message,
                )
            user_message = await self._conversations.append_message_in_transaction(
                guest=guest,
                role="user",
                text=request.text,
                client_message_id=request.client_message_id,
            )
            text, elements, draft_changed = await self._mock_response(guest=guest, request=request)
            assistant_message = await self._conversations.append_message_in_transaction(
                guest=guest, role="assistant", text=text, elements=elements
            )
        return self._response(
            guest=guest,
            request=request,
            user_message=user_message,
            assistant_message=assistant_message,
            draft_changed=draft_changed,
        )

    @staticmethod
    def _response(
        *,
        guest: GuestContext,
        request: ChatTurnRequest,
        user_message: ConversationMessagePublic,
        assistant_message: ConversationMessagePublic,
        draft_changed: bool | None = None,
    ) -> ChatTurnResponse:
        changed = (
            any(element.kind == "quote_update" for element in assistant_message.elements)
            if draft_changed is None
            else draft_changed
        )
        return ChatTurnResponse(
            conversation_id=guest.conversation_id,
            client_message_id=request.client_message_id,
            user_message=user_message,
            assistant_message=assistant_message,
            elements=assistant_message.elements,
            draft_changed=changed,
            request_id=uuid5(request.client_message_id, "mock-chat-response"),
        )

    async def _mock_response(
        self, *, guest: GuestContext, request: ChatTurnRequest
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        normalized = request.text.strip()
        lowered = normalized.casefold()
        if request.cursor is not None:
            if lowered != _SHOW_MORE_COMMAND:
                return "Use the provided cursor only with the exact request 'show more'.", (), False
            return await self._page_from_cursor(guest=guest, cursor=request.cursor)
        if lowered == _SHOW_MORE_COMMAND:
            return "There is no active product-results page to continue.", (), False
        add = _ADD_COMMAND.fullmatch(normalized)
        if add is not None:
            return await self._add_line(
                guest=guest,
                request=request,
                quantity=int(add["quantity"]),
                sku=add["sku"],
            )
        remove = _REMOVE_COMMAND.fullmatch(normalized)
        if remove is not None:
            return await self._remove_line(guest=guest, request=request, sku=remove["sku"])
        update = _UPDATE_PATTERN.fullmatch(normalized)
        if update is not None:
            return await self._update_line(
                guest=guest,
                request=request,
                sku=update["sku"],
                quantity=int(update["quantity"]),
            )
        if "review" in lowered and ("quote" in lowered or "draft" in lowered):
            draft = await self._quotations.get_draft(guest=guest)
            if draft is None or not draft.lines:
                return "There is no draft quotation to review yet.", (), False
            return (
                "Your draft is ready for review. Provide contact and fulfillment details "
                "in the quotation review form.",
                [
                    QuoteUpdateElement(
                        kind="quote_update",
                        quote=QuoteUpdateSnapshot(draft_id=draft.id, version=draft.version),
                    ),
                    ConfirmationPromptElement(
                        kind="confirmation_prompt",
                        prompt=ConfirmationPromptSnapshot(
                            title="Review quotation",
                            message=(
                                "Reviewing does not submit a quotation. Confirmation is handled "
                                "by the protected quotation endpoint."
                            ),
                            confirm_label="Review quotation",
                        ),
                    ),
                ],
                False,
            )
        if "support" in lowered or "contact" in lowered:
            return (
                "You can optionally create a synthetic support inquiry after explicit opt-in, "
                "review, and confirmation.",
                [
                    SupportInquiryFormElement(
                        kind="support_inquiry_form",
                        form=SupportInquiryFormSnapshot(
                            title="Contact support",
                            description="Opt in to prepare a synthetic support inquiry; it does "
                            "not notify real staff.",
                        ),
                    )
                ],
                False,
            )
        sku = self._sku(normalized)
        if sku is not None and any(
            word in lowered for word in ("stock", "available", "availability")
        ):
            return await self._inventory_notice(sku=sku, quantity=self._quantity(normalized))
        if sku is not None and "alternative" in lowered:
            return await self._alternatives(sku=sku, quantity=self._quantity(normalized))
        if "search" in lowered or "show" in lowered or "find" in lowered or sku is not None:
            return await self._search(guest=guest, text=normalized, sku=sku)
        if "company" in lowered or "hours" in lowered or "location" in lowered:
            return (
                "This is a synthetic demonstration. I can help with the demonstration catalog, "
                "availability, quotations, or support inquiry guidance.",
                (),
                False,
            )
        return (
            "I can help search the synthetic catalog, check categorical availability, or "
            "prepare a draft quotation when you name an SKU and quantity.",
            (),
            False,
        )

    async def _search(
        self, *, guest: GuestContext, text: str, sku: str | None
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        query = sku or self._search_query(text)
        variants = await CatalogService(self._session).search(
            filters=CatalogSearchFilters(query=query)
        )
        return await self._product_results(guest=guest, query=query, variants=variants, offset=0)

    async def _product_results(
        self,
        *,
        guest: GuestContext,
        query: str | None,
        variants: Sequence[CatalogVariant],
        offset: int,
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        cards = [
            await self._card(variant) for variant in variants[offset : offset + _RESULTS_PER_PAGE]
        ]
        if not cards:
            return (
                "I could not find a matching synthetic catalog item. Please provide a SKU or "
                "a more specific product description.",
                (),
                False,
            )
        next_offset = offset + len(cards)
        next_cursor = (
            self._encode_cursor(guest=guest, query=query, offset=next_offset)
            if next_offset < len(variants)
            else None
        )
        return (
            "Here are matching synthetic catalog items. Prices and availability are indicative "
            "and must be rechecked before review.",
            [
                ProductResultsElement(
                    kind="product_results",
                    result_context="search",
                    result_set=ProductSearchResponse(products=cards, next_cursor=next_cursor),
                )
            ],
            False,
        )

    async def _page_from_cursor(
        self, *, guest: GuestContext, cursor: str
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        decoded = self._decode_cursor(guest=guest, cursor=cursor)
        if decoded is None:
            return "That product-results cursor is invalid or has expired. Search again.", (), False
        query, offset = decoded
        variants = await CatalogService(self._session).search(
            filters=CatalogSearchFilters(query=query)
        )
        return await self._product_results(
            guest=guest, query=query, variants=variants, offset=offset
        )

    async def _inventory_notice(
        self, *, sku: str, quantity: int
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        check = await InventoryService(self._session).check_availability(sku=sku, quantity=quantity)
        message = "Availability is categorical and does not reserve stock."
        return (
            message,
            [
                InventoryNoticeElement(
                    kind="inventory_notice",
                    notice=AvailabilityResponse(
                        sku=check.sku,
                        availability=check.availability,
                        quantity_sufficient=check.is_sufficient,
                        message=message,
                    ),
                )
            ],
            False,
        )

    async def _alternatives(
        self, *, sku: str, quantity: int
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        alternatives = await CatalogService(self._session).find_alternatives(
            sku=sku, quantity=quantity
        )
        # Alternatives are already compatibility- and quantity-filtered by CatalogService.
        # Keep the approved public cap at three regardless of a future provider's wording.
        cards = [await self._card(alternative.variant) for alternative in alternatives[:3]]
        if not cards:
            return (
                "I could not find a suitable categorical-availability alternative for "
                "that request.",
                (),
                False,
            )
        return (
            "Here are compatible synthetic catalog alternatives. Availability remains categorical "
            "and is rechecked before quotation review.",
            [
                ProductResultsElement(
                    kind="product_results",
                    result_context="alternatives",
                    result_set=ProductSearchResponse(products=cards, next_cursor=None),
                )
            ],
            False,
        )

    async def _add_line(
        self, *, guest: GuestContext, request: ChatTurnRequest, quantity: int, sku: str
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        draft = await self._quotations.get_draft(guest=guest)
        try:
            updated = await self._quotations.add_line(
                guest=guest,
                sku=sku.upper(),
                quantity=quantity,
                expected_version=draft.version if draft else 0,
                operation_id=uuid5(request.client_message_id, "add-quote-line"),
            )
        except QuoteSkuNotFound, QuoteSkuUnresolved, QuoteVersionConflict, QuoteSessionInvalid:
            return (
                "I could not add that item safely. Please verify the SKU and try again after "
                "refreshing the draft.",
                (),
                False,
            )
        return (
            "I added the requested item to your draft quotation. This does not reserve inventory "
            "or submit a quotation.",
            [
                QuoteUpdateElement(
                    kind="quote_update",
                    quote=QuoteUpdateSnapshot(draft_id=updated.id, version=updated.version),
                )
            ],
            True,
        )

    async def _remove_line(
        self, *, guest: GuestContext, request: ChatTurnRequest, sku: str
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        draft = await self._quotations.get_draft(guest=guest)
        if draft is None:
            return "There is no matching draft line to remove.", (), False
        line = next((item for item in draft.lines if item.sku == sku.upper()), None)
        if line is None:
            return "There is no matching draft line to remove.", (), False
        try:
            updated = await self._quotations.remove_line(
                guest=guest,
                line_id=line.id,
                expected_version=draft.version,
                operation_id=uuid5(request.client_message_id, "remove-quote-line"),
            )
        except QuoteLineNotFound, QuoteVersionConflict, QuoteSessionInvalid:
            return (
                "I could not remove that line safely. Refresh the draft and try again.",
                (),
                False,
            )
        return (
            "I removed the draft line.",
            [
                QuoteUpdateElement(
                    kind="quote_update",
                    quote=QuoteUpdateSnapshot(draft_id=updated.id, version=updated.version),
                )
            ],
            True,
        )

    async def _update_line(
        self, *, guest: GuestContext, request: ChatTurnRequest, sku: str, quantity: int
    ) -> tuple[str, Sequence[AssistantElement], bool]:
        draft = await self._quotations.get_draft(guest=guest)
        if draft is None:
            return "There is no matching draft line to update.", (), False
        line = next((item for item in draft.lines if item.sku == sku.upper()), None)
        if line is None:
            return "There is no matching draft line to update.", (), False
        try:
            updated = await self._quotations.update_line(
                guest=guest,
                line_id=line.id,
                quantity=quantity,
                mode="replace",
                expected_version=draft.version,
                operation_id=uuid5(request.client_message_id, "update-quote-line"),
            )
        except QuoteLineNotFound, QuoteVersionConflict, QuoteSessionInvalid:
            return (
                "I could not update that line safely. Refresh the draft and try again.",
                (),
                False,
            )
        return (
            "I updated the draft-line quantity.",
            [
                QuoteUpdateElement(
                    kind="quote_update",
                    quote=QuoteUpdateSnapshot(draft_id=updated.id, version=updated.version),
                )
            ],
            True,
        )

    async def _card(self, variant: CatalogVariant) -> ProductCardPublic:
        check = await InventoryService(self._session).check_availability(
            sku=variant.sku, quantity=1
        )
        return ProductCardPublic(
            sku=variant.sku,
            product_id=variant.product_id,
            name=variant.name,
            category_code=variant.category_code,
            category_name=variant.category_name,
            sales_unit=variant.sales_unit,
            indicative_price_usd=variant.indicative_price,
            lifecycle_status=variant.lifecycle_status,
            selector_attributes=variant.selector_attributes,
            primary_image_reference=variant.primary_image_reference,
            image_fallback_key=variant.image_fallback_key,
            availability=check.availability,
        )

    @staticmethod
    def _sku(text: str) -> str | None:
        match = _SKU_PATTERN.search(text)
        return match.group(1).upper() if match else None

    @staticmethod
    def _quantity(text: str) -> int:
        match = re.search(r"\b(\d+)\b", text)
        return int(match.group(1)) if match else 1

    @staticmethod
    def _search_query(text: str) -> str | None:
        words = re.sub(
            r"\b(search|show|find|for|please|products?)\b", "", text, flags=re.IGNORECASE
        ).strip()
        return words or None

    def _encode_cursor(self, *, guest: GuestContext, query: str | None, offset: int) -> str:
        payload = dumps(
            {"guest": str(guest.guest_session_id), "offset": offset, "query": query, "version": 1},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        encoded = urlsafe_b64encode(payload).rstrip(b"=")
        signature = (
            new(
                self._settings.session_token_hash_secret.get_secret_value().encode(),
                encoded,
                sha256,
            )
            .hexdigest()
            .encode()
        )
        return f"{encoded.decode()}.{signature.decode()}"

    def _decode_cursor(self, *, guest: GuestContext, cursor: str) -> tuple[str | None, int] | None:
        try:
            encoded, signature = cursor.encode().split(b".", maxsplit=1)
            expected = (
                new(
                    self._settings.session_token_hash_secret.get_secret_value().encode(),
                    encoded,
                    sha256,
                )
                .hexdigest()
                .encode()
            )
            if not compare_digest(signature, expected):
                return None
            payload = loads(urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4)))
            if (
                not isinstance(payload, dict)
                or payload.get("version") != 1
                or payload.get("guest") != str(guest.guest_session_id)
                or not isinstance(payload.get("offset"), int)
                or payload["offset"] < _RESULTS_PER_PAGE
                or payload["offset"] % _RESULTS_PER_PAGE != 0
                or (payload.get("query") is not None and not isinstance(payload["query"], str))
            ):
                return None
            return payload.get("query"), payload["offset"]
        except TypeError, ValueError:
            return None


# API-08 is deliberately replaceable by the future LangGraph orchestration boundary.
ChatService = MockChatService
