from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select

from app.agents.openrouter import (
    OpenRouterConfigurationError,
    OpenRouterContextLimitError,
    OpenRouterGateway,
    OpenRouterMalformedResponseError,
    OpenRouterMessage,
    OpenRouterRateLimitError,
    OpenRouterTimeoutError,
    OpenRouterUnavailableError,
)
from app.core.settings import Settings
from app.db.session import get_session_factory
from app.models.ai import AiUsageRecord


class StubTransport:
    def __init__(self, result: httpx.Response | Exception) -> None:
        self.result = result
        self.requests: list[dict[str, object]] = []

    async def post(
        self, url: str, *, headers: Mapping[str, str], json: Mapping[str, object]
    ) -> httpx.Response:
        self.requests.append({"url": url, "headers": dict(headers), "json": dict(json)})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def gateway_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://localhost/medical_supply_test",
        "session_token_hash_secret": SecretStr(
            "test-session-hash-secret-with-at-least-32-characters"
        ),
        "openrouter_api_key": SecretStr("openrouter-test-key"),
        "openrouter_model": "provider/test-model",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def gateway(transport: StubTransport, **settings_overrides: object) -> OpenRouterGateway:
    return OpenRouterGateway(settings=gateway_settings(**settings_overrides), transport=transport)


@pytest.mark.asyncio
async def test_valid_response_returns_provider_usage_and_persists_observation() -> None:
    transport = StubTransport(
        httpx.Response(
            200,
            json={
                "model": "provider/test-model:provider-route",
                "choices": [{"message": {"content": "Synthetic response."}}],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                    "cost": "0.00125",
                },
            },
        )
    )
    correlation_id = uuid4()
    async with get_session_factory()() as session:
        gateway_with_usage = OpenRouterGateway(
            settings=gateway_settings(), transport=transport, session=session
        )
        completion = await gateway_with_usage.complete(
            messages=[OpenRouterMessage(role="user", content="Hello")],
            correlation_id=correlation_id,
        )
        await session.flush()
        record = await session.scalar(
            select(AiUsageRecord).where(AiUsageRecord.correlation_id == correlation_id)
        )
        assert record is not None
        recorded_total_tokens = record.total_tokens
        recorded_cost = record.estimated_cost_usd
        await session.rollback()

    assert completion.content == "Synthetic response."
    assert completion.selected_model == "provider/test-model"
    assert completion.provider_model == "provider/test-model:provider-route"
    assert completion.usage.input_tokens == 11
    assert completion.usage.estimated_cost_usd == Decimal("0.00125")
    assert recorded_total_tokens == 18
    assert recorded_cost == Decimal("0.00125000")
    assert transport.requests[0]["json"] == {
        "model": "provider/test-model",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 512,
    }


@pytest.mark.asyncio
async def test_absent_provider_usage_does_not_invent_usage_or_cost() -> None:
    transport = StubTransport(
        httpx.Response(200, json={"choices": [{"message": {"content": "Synthetic response."}}]})
    )

    completion = await gateway(transport).complete(
        messages=[OpenRouterMessage(role="user", content="Hello")], correlation_id=uuid4()
    )

    assert completion.usage.input_tokens is None
    assert completion.usage.output_tokens is None
    assert completion.usage.total_tokens is None
    assert completion.usage.estimated_cost_usd is None


def test_gateway_requires_explicit_key_and_model() -> None:
    transport = StubTransport(httpx.Response(200))
    settings = Settings(
        database_url="postgresql+psycopg://localhost/medical_supply_test",
        session_token_hash_secret=SecretStr("test-session-hash-secret-with-at-least-32-characters"),
    )

    with pytest.raises(OpenRouterConfigurationError, match="not configured"):
        OpenRouterGateway(settings=settings, transport=transport)


@pytest.mark.parametrize(
    "overrides",
    (
        {"openrouter_model": "not a model"},
        {"openrouter_api_key": SecretStr(" ")},
        {"openrouter_max_output_tokens": 128, "openrouter_context_limit_tokens": 128},
    ),
)
def test_settings_reject_invalid_openrouter_configuration(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        gateway_settings(**overrides)


@pytest.mark.asyncio
async def test_timeout_rate_limit_and_provider_failure_are_safe() -> None:
    timeout = gateway(StubTransport(httpx.ReadTimeout("timeout")))
    rate_limited = gateway(StubTransport(httpx.Response(429, json={"error": {"message": "busy"}})))
    unavailable = gateway(
        StubTransport(httpx.Response(502, json={"error": {"message": "provider failure"}}))
    )
    request = {
        "messages": [OpenRouterMessage(role="user", content="Hello")],
        "correlation_id": uuid4(),
    }

    with pytest.raises(OpenRouterTimeoutError, match="try again"):
        await timeout.complete(**request)
    with pytest.raises(OpenRouterRateLimitError, match="shortly"):
        await rate_limited.complete(**request)
    with pytest.raises(OpenRouterUnavailableError, match="unavailable"):
        await unavailable.complete(**request)


@pytest.mark.asyncio
async def test_malformed_provider_response_and_context_limit_are_rejected() -> None:
    malformed = gateway(StubTransport(httpx.Response(200, json={"choices": [{}]})))

    with pytest.raises(OpenRouterMalformedResponseError, match="invalid response"):
        await malformed.complete(
            messages=[OpenRouterMessage(role="user", content="Hello")], correlation_id=uuid4()
        )
    with pytest.raises(OpenRouterContextLimitError, match="context limit"):
        await gateway(
            StubTransport(httpx.Response(200)),
            openrouter_max_output_tokens=4,
            openrouter_context_limit_tokens=8,
        ).complete(
            messages=[OpenRouterMessage(role="user", content="abcdefghijklmnop")],
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_safe_provider_errors_do_not_expose_credentials() -> None:
    secret = "openrouter-secret-that-must-not-appear"
    gateway_with_secret = OpenRouterGateway(
        settings=gateway_settings(openrouter_api_key=SecretStr(secret)),
        transport=StubTransport(httpx.Response(500, json={"error": {"message": secret}})),
    )

    with pytest.raises(OpenRouterUnavailableError) as error:
        await gateway_with_secret.complete(
            messages=[OpenRouterMessage(role="user", content="Hello")], correlation_id=uuid4()
        )

    assert secret not in str(error.value)
