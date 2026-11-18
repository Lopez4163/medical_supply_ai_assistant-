"""HTTP boundary for the replaceable deterministic mock chat provider."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sessions import get_guest_context, require_quotation_origin
from app.core.errors import api_error_responses
from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.chat import ChatTurnRequest, ChatTurnResponse
from app.services.chat import ChatProvider, MockChatService
from app.services.sessions import GuestContext

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(
    session: AsyncSession = Depends(get_db_session), settings: Settings = Depends(get_settings)
) -> ChatProvider:
    if settings.chat_provider == "mock":
        return MockChatService(session, settings)
    raise HTTPException(
        status_code=503,
        detail={
            "code": "AI_UNAVAILABLE",
            "message": "The configured chat provider is not available.",
        },
    )


@router.post(
    "/messages",
    response_model=ChatTurnResponse,
    responses=api_error_responses(401, 403, 409, 422, 500, 503),
)
async def send_chat_message(
    request: ChatTurnRequest,
    _: Annotated[None, Depends(require_quotation_origin)],
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[ChatProvider, Depends(get_chat_service)],
) -> ChatTurnResponse:
    return await service.respond(guest=guest, request=request)
