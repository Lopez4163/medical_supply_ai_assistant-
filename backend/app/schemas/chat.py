"""Validated request and response contracts for one persisted chat turn."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.conversations import AssistantElement, ConversationMessagePublic


class _StrictChatModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatTurnRequest(_StrictChatModel):
    client_message_id: UUID
    text: str = Field(min_length=1, max_length=2_000)
    cursor: str | None = Field(default=None, min_length=1, max_length=500)


class ChatTurnResponse(_StrictChatModel):
    conversation_id: UUID
    client_message_id: UUID
    user_message: ConversationMessagePublic
    assistant_message: ConversationMessagePublic
    elements: list[AssistantElement]
    draft_changed: bool
    request_id: UUID
