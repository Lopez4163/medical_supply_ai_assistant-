from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.openrouter import OpenRouterCompletion, ProviderUsage
from app.agents.openrouter_model import GatewayModel


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages = []

    async def complete(self, *, messages, correlation_id):
        self.messages = messages
        return OpenRouterCompletion(
            content=self.content,
            selected_model="provider/model",
            provider_model=None,
            latency_ms=1,
            usage=ProviderUsage(None, None, None, Decimal("0")),
        )


@pytest.mark.asyncio
async def test_adapter_parses_tool_call_and_structured_tool_messages() -> None:
    gateway = FakeGateway(
        '{"text":"","tool_call":{"name":"search_products","arguments":{"query":"gloves"}}}'
    )
    step = await GatewayModel(gateway).next_step(
        messages=[{"role": "tool", "content": {"products": []}}]
    )
    assert step.tool_call is not None and step.tool_call.name == "search_products"
    assert gateway.messages[0].content == '{"products": []}'


@pytest.mark.asyncio
async def test_adapter_rejects_malformed_model_output() -> None:
    with pytest.raises(ValueError, match="structured step"):
        await GatewayModel(FakeGateway("not-json")).next_step(
            messages=[{"role": "user", "content": "hello"}]
        )


@pytest.mark.asyncio
async def test_adapter_rejects_unsupported_multi_tool_payload() -> None:
    payload = '{"text":"","tool_calls":[{"name":"search_products","arguments":{"query":"gloves"}}]}'

    with pytest.raises(ValueError, match="Multiple tool calls"):
        await GatewayModel(FakeGateway(payload)).next_step(
            messages=[{"role": "user", "content": "hello"}]
        )
