"""Scoped persistence and restoration of customer-visible conversation snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationMessage
from app.schemas.conversations import (
    AssistantElement,
    ConversationHistoryResponse,
    ConversationMessageContent,
    ConversationMessagePublic,
)
from app.services.sessions import GuestContext

_ELEMENT_SCHEMA_VERSION = 1
_assistant_elements_adapter = TypeAdapter(list[AssistantElement])


class ConversationNotFound(Exception):
    """Raised when a trusted guest context has no associated conversation."""


class DuplicateClientMessage(Exception):
    """Raised when a replayed client message ID needs higher-level reconciliation."""


class InvalidConversationHistory(Exception):
    """Raised when persisted content cannot be safely projected to a public response."""


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_history(self, *, guest: GuestContext) -> ConversationHistoryResponse:
        """Return only the ordered history scoped to the trusted guest context."""
        conversation = await self._get_scoped_conversation(guest=guest)
        messages = list(
            (
                await self._session.scalars(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conversation.id)
                    .order_by(ConversationMessage.server_ordinal)
                )
            ).all()
        )
        return ConversationHistoryResponse(
            conversation_id=conversation.id,
            messages=[self._to_public_message(message) for message in messages],
        )

    async def append_user_message(
        self,
        *,
        guest: GuestContext,
        text: str,
        client_message_id: UUID,
    ) -> ConversationMessagePublic:
        """Append one customer message within the caller-owned transaction."""
        return await self.append_message_in_transaction(
            guest=guest,
            role="user",
            text=text,
            client_message_id=client_message_id,
        )

    async def append_assistant_message(
        self,
        *,
        guest: GuestContext,
        text: str,
        elements: Sequence[AssistantElement],
    ) -> ConversationMessagePublic:
        """Append one validated assistant display snapshot in the caller transaction."""
        return await self.append_message_in_transaction(
            guest=guest,
            role="assistant",
            text=text,
            elements=elements,
        )

    async def append_message_in_transaction(
        self,
        *,
        guest: GuestContext,
        role: Literal["user", "assistant"],
        text: str,
        elements: Sequence[AssistantElement] = (),
        client_message_id: UUID | None = None,
    ) -> ConversationMessagePublic:
        """Append within a caller-owned transaction for future atomic chat orchestration."""
        content = ConversationMessageContent(text=text)
        if role == "user" and elements:
            raise ValueError("User messages cannot contain assistant elements.")
        if role == "assistant" and client_message_id is not None:
            raise ValueError("Assistant messages cannot define a client message ID.")

        validated_elements = _assistant_elements_adapter.validate_python(list(elements))
        conversation = await self._get_scoped_conversation(guest=guest, lock=True)
        if client_message_id is not None:
            duplicate = await self._session.scalar(
                select(ConversationMessage.id).where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.client_message_id == client_message_id,
                )
            )
            if duplicate is not None:
                raise DuplicateClientMessage

        next_ordinal = await self._next_ordinal(conversation_id=conversation.id)
        message = ConversationMessage(
            conversation_id=conversation.id,
            client_message_id=client_message_id,
            server_ordinal=next_ordinal,
            role=role,
            message_kind="turn",
            content_json=content.model_dump(mode="json"),
            elements_json=[element.model_dump(mode="json") for element in validated_elements],
            element_schema_version=_ELEMENT_SCHEMA_VERSION,
        )
        self._session.add(message)
        await self._session.flush()
        return self._to_public_message(message)

    async def get_completed_turn(
        self, *, guest: GuestContext, client_message_id: UUID, lock: bool = False
    ) -> tuple[ConversationMessagePublic, ConversationMessagePublic] | None:
        """Return the persisted user/assistant pair for a safe client-message replay."""
        conversation = await self._get_scoped_conversation(guest=guest, lock=lock)
        user = await self._session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation.id,
                ConversationMessage.client_message_id == client_message_id,
            )
        )
        if user is None:
            return None
        assistant = await self._session.scalar(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation.id,
                ConversationMessage.server_ordinal == user.server_ordinal + 1,
                ConversationMessage.role == "assistant",
            )
        )
        if assistant is None:
            return None
        return self._to_public_message(user), self._to_public_message(assistant)

    async def _get_scoped_conversation(
        self, *, guest: GuestContext, lock: bool = False
    ) -> Conversation:
        statement = select(Conversation).where(
            Conversation.id == guest.conversation_id,
            Conversation.guest_session_id == guest.guest_session_id,
        )
        if lock:
            statement = statement.with_for_update()
        conversation = await self._session.scalar(statement)
        if conversation is None:
            raise ConversationNotFound
        return conversation

    async def _next_ordinal(self, *, conversation_id: UUID) -> int:
        next_ordinal = await self._session.scalar(
            select(func.coalesce(func.max(ConversationMessage.server_ordinal), -1) + 1).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )
        assert next_ordinal is not None
        return int(next_ordinal)

    def _to_public_message(self, message: ConversationMessage) -> ConversationMessagePublic:
        try:
            if message.element_schema_version != _ELEMENT_SCHEMA_VERSION:
                raise ValueError("Unsupported element schema version.")
            content = ConversationMessageContent.model_validate(message.content_json)
            elements = _assistant_elements_adapter.validate_python(message.elements_json)
            return ConversationMessagePublic.model_validate(
                {
                    "id": message.id,
                    "role": message.role,
                    "kind": message.message_kind,
                    "ordinal": message.server_ordinal,
                    "text": content.text,
                    "elements": elements,
                    "created_at": message.created_at,
                }
            )
        except TypeError, ValueError, ValidationError:
            raise InvalidConversationHistory from None
