"""Public-safe guest-session API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionBootstrapResponse(BaseModel):
    conversation_id: UUID
    expires_at: datetime
    welcome_message: str
    restored: bool


class GuestSessionPublic(BaseModel):
    conversation_id: UUID
    expires_at: datetime
