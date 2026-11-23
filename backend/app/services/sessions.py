"""Durable anonymous guest-session lifecycle management."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.models.conversation import Conversation, ConversationMessage, GuestSession


def utc_now() -> datetime:
    return datetime.now(UTC)


class InvalidGuestSession(Exception):
    """Raised when a supplied opaque guest credential cannot access protected state."""


@dataclass(frozen=True)
class GuestContext:
    guest_session_id: UUID
    conversation_id: UUID
    expires_at: datetime


@dataclass(frozen=True)
class SessionBootstrap:
    context: GuestContext
    expires_at: datetime
    welcome_message: str
    created: bool
    raw_token: str


class SessionService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._session = session
        self._settings = settings
        self._now = now

    async def bootstrap(self, *, raw_token: str | None) -> SessionBootstrap:
        now = self._now()
        async with self._session.begin():
            existing = await self._find_valid_session(raw_token=raw_token, now=now)
            if existing is not None:
                assert raw_token is not None
                guest_session, conversation = existing
                guest_session.last_activity_at = now
                guest_session.expires_at = self._expires_at(now)
                return SessionBootstrap(
                    context=GuestContext(
                        guest_session.id, conversation.id, guest_session.expires_at
                    ),
                    expires_at=guest_session.expires_at,
                    welcome_message=self._settings.welcome_message,
                    created=False,
                    raw_token=raw_token,
                )

            new_token = secrets.token_urlsafe(32)
            guest_session = GuestSession(
                token_hash=self._hash_token(new_token),
                last_activity_at=now,
                expires_at=self._expires_at(now),
            )
            conversation = Conversation(
                guest_session=guest_session,
                langgraph_thread_id=str(uuid4()),
                welcome_persisted_at=now,
            )
            self._session.add(
                ConversationMessage(
                    conversation=conversation,
                    server_ordinal=0,
                    role="assistant",
                    message_kind="welcome",
                    content_json={"text": self._settings.welcome_message},
                    elements_json=[],
                    element_schema_version=1,
                )
            )
            await self._session.flush()

        return SessionBootstrap(
            context=GuestContext(guest_session.id, conversation.id, guest_session.expires_at),
            expires_at=guest_session.expires_at,
            welcome_message=self._settings.welcome_message,
            created=True,
            raw_token=new_token,
        )

    async def require_context(self, *, raw_token: str | None) -> GuestContext:
        existing = await self._find_valid_session(raw_token=raw_token, now=self._now())
        if existing is None:
            raise InvalidGuestSession
        guest_session, conversation = existing
        return GuestContext(guest_session.id, conversation.id, guest_session.expires_at)

    async def renew_activity(self, *, guest_session_id: UUID) -> None:
        """Renew only a still-valid session inside a caller-owned protected transaction."""
        now = self._now()
        guest_session = await self._session.scalar(
            select(GuestSession)
            .where(GuestSession.id == guest_session_id)
            .where(GuestSession.revoked_at.is_(None))
            .where(GuestSession.expires_at > now)
            .with_for_update()
        )
        if guest_session is None:
            raise InvalidGuestSession
        guest_session.last_activity_at = now
        guest_session.expires_at = self._expires_at(now)

    async def _find_valid_session(
        self, *, raw_token: str | None, now: datetime
    ) -> tuple[GuestSession, Conversation] | None:
        if not raw_token:
            return None
        result = await self._session.execute(
            select(GuestSession, Conversation)
            .join(Conversation, Conversation.guest_session_id == GuestSession.id)
            .where(GuestSession.token_hash == self._hash_token(raw_token))
            .where(GuestSession.revoked_at.is_(None))
            .where(GuestSession.expires_at > now)
        )
        return result.one_or_none()

    def _expires_at(self, now: datetime) -> datetime:
        return now + timedelta(days=self._settings.guest_session_inactivity_days)

    def _hash_token(self, raw_token: str) -> str:
        return hmac.new(
            self._settings.session_token_hash_secret.get_secret_value().encode(),
            raw_token.encode(),
            hashlib.sha256,
        ).hexdigest()
