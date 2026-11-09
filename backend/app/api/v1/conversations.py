"""Authenticated restoration of persisted customer-visible conversation history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.sessions import get_guest_context
from app.db.session import get_db_session
from app.schemas.conversations import ConversationHistoryResponse
from app.services.conversations import (
    ConversationNotFound,
    ConversationService,
    InvalidConversationHistory,
)
from app.services.sessions import GuestContext

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(
    session: AsyncSession = Depends(get_db_session),
) -> ConversationService:
    return ConversationService(session)


@router.get("/current", response_model=ConversationHistoryResponse)
async def get_current_conversation(
    guest: Annotated[GuestContext, Depends(get_guest_context)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationHistoryResponse:
    """Restore stored display snapshots without recalculating current catalog facts."""
    try:
        return await service.get_history(guest=guest)
    except ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation history was not found.") from None
    except InvalidConversationHistory:
        raise HTTPException(
            status_code=500, detail="Conversation history is unavailable."
        ) from None
