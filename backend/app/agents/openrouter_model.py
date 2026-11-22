"""Adapter from the AI-01 gateway to the AI-02 model-step contract."""

from __future__ import annotations

from json import JSONDecodeError, dumps, loads
from typing import Protocol
from uuid import UUID, uuid4

from app.agents.graph import ModelStep, ToolCall
from app.agents.openrouter import OpenRouterCompletion, OpenRouterMessage


class CompletionGateway(Protocol):
    async def complete(
        self, *, messages: list[OpenRouterMessage], correlation_id: UUID
    ) -> OpenRouterCompletion: ...


class GatewayModel:
    def __init__(self, gateway: CompletionGateway) -> None:
        self._gateway = gateway

    async def next_step(self, *, messages: list[dict[str, object]]) -> ModelStep:
        completion = await self._gateway.complete(
            messages=[self._message(item) for item in messages],
            correlation_id=uuid4(),
        )
        try:
            payload = loads(completion.content)
        except JSONDecodeError as error:
            raise ValueError("The model response was not a structured step.") from error
        if not isinstance(payload, dict):
            raise ValueError("The model response was not a structured step.")
        if "tool_calls" in payload:
            raise ValueError("Multiple tool calls are not supported.")
        text = payload.get("text")
        if not isinstance(text, str):
            raise ValueError("The model response was not a structured step.")
        call = payload.get("tool_call")
        return ModelStep(
            text=text,
            tool_call=ToolCall.model_validate(call) if call is not None else None,
        )

    @staticmethod
    def _message(item: dict[str, object]) -> OpenRouterMessage:
        content = item.get("content", "")
        return OpenRouterMessage(
            role=str(item["role"]), content=content if isinstance(content, str) else dumps(content)
        )
