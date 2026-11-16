"""Cookie-authenticated direct controls for a guest's draft quotation."""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sessions import get_guest_context, require_quotation_origin
from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.quotations import (
    AddQuoteLineRequest,
    DeleteQuoteLineRequest,
    DraftQuotePublic,
    DraftQuoteResponse,
    QuoteReviewPublic,
    QuoteReviewRequest,
    QuoteSubmissionPublic,
    QuoteSubmitRequest,
    UpdateQuoteLineRequest,
)
from app.services.quotations import (
    IdempotencyPayloadMismatch,
    QuotationService,
    QuoteLineNotFound,
    QuoteReviewInvalid,
    QuoteSessionInvalid,
    QuoteSkuNotFound,
    QuoteSkuUnresolved,
    QuoteVersionConflict,
)
from app.services.sessions import GuestContext

router = APIRouter(prefix="/quotations", tags=["quotations"])


def get_quotation_service(
    session: AsyncSession = Depends(get_db_session), settings: Settings = Depends(get_settings)
) -> QuotationService:
    return QuotationService(session, settings)


def _raise_quote_error(error: Exception) -> NoReturn:
    if isinstance(error, QuoteVersionConflict):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "QUOTE_VERSION_CONFLICT",
                "message": "The quotation changed. Refresh and review it again.",
            },
        ) from None
    if isinstance(error, IdempotencyPayloadMismatch):
        raise HTTPException(
            status_code=409, detail="This operation ID was already used for another action."
        ) from None
    if isinstance(error, QuoteLineNotFound):
        raise HTTPException(status_code=404, detail="Quotation line was not found.") from None
    if isinstance(error, QuoteSessionInvalid):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "GUEST_SESSION_INVALID",
                "message": "Guest session is missing or invalid.",
            },
        ) from None
    if isinstance(error, QuoteSkuUnresolved):
        raise HTTPException(
            status_code=422, detail="Select a sellable SKU variant before adding it to a quotation."
        ) from None
    if isinstance(error, QuoteSkuNotFound):
        raise HTTPException(status_code=404, detail="Product SKU was not found.") from None
    if isinstance(error, QuoteReviewInvalid):
        raise HTTPException(
            status_code=409, detail="The quotation review is invalid or expired."
        ) from None
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from None
    raise error


@router.get("/draft", response_model=DraftQuoteResponse)
async def get_draft_quote(
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> DraftQuoteResponse:
    return DraftQuoteResponse(draft=await service.get_draft(guest=guest))


@router.post("/draft/lines", response_model=DraftQuotePublic)
async def add_quote_line(
    request: AddQuoteLineRequest,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> DraftQuotePublic:
    try:
        return await service.add_line(guest=guest, **request.model_dump())
    except (
        QuoteVersionConflict,
        IdempotencyPayloadMismatch,
        QuoteLineNotFound,
        QuoteSkuNotFound,
        QuoteSkuUnresolved,
        QuoteSessionInvalid,
    ) as error:
        _raise_quote_error(error)


@router.patch("/draft/lines/{line_id}", response_model=DraftQuotePublic)
async def update_quote_line(
    line_id: UUID,
    request: UpdateQuoteLineRequest,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> DraftQuotePublic:
    try:
        return await service.update_line(guest=guest, line_id=line_id, **request.model_dump())
    except (
        QuoteVersionConflict,
        IdempotencyPayloadMismatch,
        QuoteLineNotFound,
        QuoteSessionInvalid,
    ) as error:
        _raise_quote_error(error)


@router.delete("/draft/lines/{line_id}", response_model=DraftQuotePublic)
async def delete_quote_line(
    line_id: UUID,
    request: DeleteQuoteLineRequest,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> DraftQuotePublic:
    """Use Document 07's request body so DELETE remains idempotency/version protected."""
    try:
        return await service.remove_line(guest=guest, line_id=line_id, **request.model_dump())
    except (
        QuoteVersionConflict,
        IdempotencyPayloadMismatch,
        QuoteLineNotFound,
        QuoteSessionInvalid,
    ) as error:
        _raise_quote_error(error)


@router.post("/draft/review", response_model=QuoteReviewPublic)
async def review_quote_draft(
    request: QuoteReviewRequest,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> QuoteReviewPublic:
    try:
        return await service.review_draft(
            guest=guest,
            expected_version=request.expected_version,
            contact=request.contact.model_dump(),
            fulfillment=request.fulfillment,
            delivery_city=request.delivery_city,
        )
    except (QuoteVersionConflict, QuoteSessionInvalid, QuoteReviewInvalid, ValueError) as error:
        _raise_quote_error(error)


@router.post("/submissions", response_model=QuoteSubmissionPublic, status_code=201)
async def submit_quote(
    request: QuoteSubmitRequest,
    response: Response,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> QuoteSubmissionPublic:
    try:
        result = await service.submit_draft(
            guest=guest,
            review_token=request.review_token,
            expected_version=request.expected_version,
            operation_id=request.operation_id,
        )
        if service.last_submission_was_replay:
            response.status_code = 200
        return result
    except (
        QuoteVersionConflict,
        QuoteSessionInvalid,
        QuoteReviewInvalid,
        IdempotencyPayloadMismatch,
    ) as error:
        _raise_quote_error(error)


@router.get("/submissions/reconcile/{operation_id}", response_model=QuoteSubmissionPublic)
async def reconcile_quote_submission(
    operation_id: UUID,
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> QuoteSubmissionPublic:
    result = await service.reconcile_submission(guest=guest, operation_id=operation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Submission operation was not found.")
    return result
