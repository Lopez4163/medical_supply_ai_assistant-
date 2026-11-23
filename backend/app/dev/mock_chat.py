"""API-08 deterministic provider export used by local mock-mode deployments."""

from app.services.chat import MockChatService

__all__ = ["MockChatService"]
