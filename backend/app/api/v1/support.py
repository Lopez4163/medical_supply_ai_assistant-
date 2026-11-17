"""Cookie-authenticated synthetic support inquiry endpoints."""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sessions import get_guest_context, require_quotation_origin
from app.core.errors import api_error_responses
from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.support import (
    SupportInquiryPublic,
    SupportReviewPublic,
    SupportReviewRequest,
    SupportSubmitRequest,
)
from app.services.sessions import GuestContext
from app.services.support import (
    SupportContactUnavailable,
    SupportIdempotencyPayloadMismatch,
    SupportInquiryService,
    SupportReviewInvalid,
    SupportSessionInvalid,
)

router = APIRouter(prefix="/support", tags=["support"])


def get_support_inquiry_service(
    session: AsyncSession = Depends(get_db_session), settings: Settings = Depends(get_settings)
) -> SupportInquiryService:
    return SupportInquiryService(session, settings)


def _raise_support_error(error: Exception) -> NoReturn:
    if isinstance(error, (SupportReviewInvalid, SupportIdempotencyPayloadMismatch)):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CONFIRMATION_INVALID"
                if isinstance(error, SupportReviewInvalid)
                else "VALIDATION_FAILED",
                "message": "The support review or operation is invalid.",
            },
        ) from None
    if isinstance(error, SupportContactUnavailable):
        raise HTTPException(
            status_code=422, detail="No prior contact details are available to reuse."
        ) from None
    if isinstance(error, SupportSessionInvalid):
        raise HTTPException(
            status_code=401,
            detail={"code": "SESSION_NOT_FOUND", "message": "Guest session is missing or invalid."},
        ) from None
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from None
    raise error


@router.post(
    "/review", response_model=SupportReviewPublic, responses=api_error_responses(401, 403, 422)
)
async def review_support_inquiry(
    request: SupportReviewRequest,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[SupportInquiryService, Depends(get_support_inquiry_service)],
) -> SupportReviewPublic:
    try:
        return await service.review(guest=guest, **request.model_dump())
    except (SupportContactUnavailable, SupportSessionInvalid, ValueError) as error:
        _raise_support_error(error)


@router.post(
    "/inquiries",
    response_model=SupportInquiryPublic,
    status_code=201,
    responses={
        200: {"model": SupportInquiryPublic, "description": "Committed idempotent replay."},
        **api_error_responses(401, 403, 409),
    },
)
async def submit_support_inquiry(
    request: SupportSubmitRequest,
    response: Response,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[SupportInquiryService, Depends(get_support_inquiry_service)],
) -> SupportInquiryPublic:
    try:
        result = await service.submit(
            guest=guest, review_token=request.review_token, operation_id=request.operation_id
        )
        if service.last_submission_was_replay:
            response.status_code = 200
        return result
    except (
        SupportIdempotencyPayloadMismatch,
        SupportReviewInvalid,
        SupportSessionInvalid,
    ) as error:
        _raise_support_error(error)


@router.get(
    "/inquiries/reconcile/{operation_id}",
    response_model=SupportInquiryPublic,
    responses=api_error_responses(401, 404),
)
async def reconcile_support_inquiry(
    operation_id: UUID,
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[SupportInquiryService, Depends(get_support_inquiry_service)],
) -> SupportInquiryPublic:
    result = await service.reconcile(guest=guest, operation_id=operation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Support inquiry operation was not found.")
    return result
