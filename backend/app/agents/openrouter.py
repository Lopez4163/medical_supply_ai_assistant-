"""Backend-only OpenRouter completion gateway for the future LangGraph provider."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import ceil
from time import perf_counter
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.models.ai import AiUsageRecord

_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    """Safe provider failure suitable for future LangGraph recovery behavior."""

    retryable = False
    error_class = "provider_error"


class OpenRouterConfigurationError(OpenRouterError):
    error_class = "configuration"


class OpenRouterContextLimitError(OpenRouterError):
    error_class = "context_limit"


class OpenRouterTimeoutError(OpenRouterError):
    retryable = True
    error_class = "timeout"


class OpenRouterRateLimitError(OpenRouterError):
    retryable = True
    error_class = "rate_limited"


class OpenRouterUnavailableError(OpenRouterError):
    retryable = True
    error_class = "unavailable"


class OpenRouterMalformedResponseError(OpenRouterError):
    error_class = "malformed_response"


class OpenRouterTransport(Protocol):
    """Minimal injectable HTTP boundary for provider-free tests."""

    async def post(
        self, url: str, *, headers: Mapping[str, str], json: Mapping[str, object]
    ) -> httpx.Response: ...


@dataclass(frozen=True)
class OpenRouterMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: Decimal | None


@dataclass(frozen=True)
class OpenRouterCompletion:
    content: str
    selected_model: str
    provider_model: str | None
    latency_ms: int
    usage: ProviderUsage


def create_openrouter_http_client(settings: Settings) -> httpx.AsyncClient:
    """Create a caller-owned client; the API key remains only in gateway request headers."""
    return httpx.AsyncClient(timeout=settings.openrouter_request_timeout_seconds)


class OpenRouterGateway:
    """One configured-model request; this adapter never changes models or retries requests."""

    def __init__(
        self,
        *,
        settings: Settings,
        transport: OpenRouterTransport,
        session: AsyncSession | None = None,
    ) -> None:
        if settings.openrouter_api_key is None or settings.openrouter_model is None:
            raise OpenRouterConfigurationError("The AI provider is not configured.")
        self._api_key = settings.openrouter_api_key.get_secret_value()
        self._model = settings.openrouter_model
        self._timeout_seconds = settings.openrouter_request_timeout_seconds
        self._max_output_tokens = settings.openrouter_max_output_tokens
        self._context_limit_tokens = settings.openrouter_context_limit_tokens
        self._transport = transport
        self._session = session

    async def complete(
        self,
        *,
        messages: Sequence[OpenRouterMessage],
        correlation_id: UUID,
        conversation_id: UUID | None = None,
    ) -> OpenRouterCompletion:
        estimated_input_tokens = self._estimate_input_tokens(messages)
        if estimated_input_tokens + self._max_output_tokens > self._context_limit_tokens:
            raise OpenRouterContextLimitError(
                "The conversation exceeds the configured context limit."
            )

        started_at = perf_counter()
        try:
            response = await self._transport.post(
                _CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": message.role, "content": message.content} for message in messages
                    ],
                    "max_tokens": self._max_output_tokens,
                },
            )
        except httpx.TimeoutException as error:
            self._record_failure(
                correlation_id, conversation_id, started_at, OpenRouterTimeoutError
            )
            raise OpenRouterTimeoutError("The AI provider timed out. Please try again.") from error
        except httpx.HTTPError as error:
            self._record_failure(
                correlation_id, conversation_id, started_at, OpenRouterUnavailableError
            )
            raise OpenRouterUnavailableError(
                "The AI provider is unavailable. Please try again."
            ) from error

        if response.status_code == 429:
            self._record_failure(
                correlation_id, conversation_id, started_at, OpenRouterRateLimitError
            )
            raise OpenRouterRateLimitError("The AI provider is busy. Please try again shortly.")
        if response.status_code < 200 or response.status_code >= 300:
            self._record_failure(
                correlation_id, conversation_id, started_at, OpenRouterUnavailableError
            )
            raise OpenRouterUnavailableError("The AI provider is unavailable. Please try again.")

        try:
            payload = response.json()
            completion = self._parse_completion(payload, self._elapsed_ms(started_at))
        except (TypeError, ValueError, InvalidOperation) as error:
            self._record_failure(
                correlation_id, conversation_id, started_at, OpenRouterMalformedResponseError
            )
            raise OpenRouterMalformedResponseError(
                "The AI provider returned an invalid response."
            ) from error

        self._record(
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            latency_ms=completion.latency_ms,
            usage=completion.usage,
            provider_model=completion.provider_model,
            outcome="success",
            error_class=None,
        )
        return completion

    def _parse_completion(self, payload: object, latency_ms: int) -> OpenRouterCompletion:
        if not isinstance(payload, dict):
            raise ValueError("response is not an object")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("response choices are missing")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("response content is missing")
        content = message["content"].strip()
        if not content:
            raise ValueError("response content is blank")
        provider_model = payload.get("model")
        if provider_model is not None and (
            not isinstance(provider_model, str) or not provider_model.strip()
        ):
            raise ValueError("response model is invalid")
        return OpenRouterCompletion(
            content=content,
            selected_model=self._model,
            provider_model=provider_model.strip() if isinstance(provider_model, str) else None,
            latency_ms=latency_ms,
            usage=self._parse_usage(payload.get("usage")),
        )

    @staticmethod
    def _parse_usage(raw_usage: object) -> ProviderUsage:
        if raw_usage is None:
            return ProviderUsage(None, None, None, None)
        if not isinstance(raw_usage, dict):
            raise ValueError("response usage is invalid")
        return ProviderUsage(
            input_tokens=OpenRouterGateway._usage_integer(raw_usage.get("prompt_tokens")),
            output_tokens=OpenRouterGateway._usage_integer(raw_usage.get("completion_tokens")),
            total_tokens=OpenRouterGateway._usage_integer(raw_usage.get("total_tokens")),
            estimated_cost_usd=OpenRouterGateway._usage_cost(raw_usage.get("cost")),
        )

    @staticmethod
    def _usage_integer(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("response token usage is invalid")
        return value

    @staticmethod
    def _usage_cost(value: object) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError("response cost is invalid")
        cost = Decimal(str(value))
        if not cost.is_finite() or cost < 0:
            raise ValueError("response cost is invalid")
        return cost

    @staticmethod
    def _estimate_input_tokens(messages: Sequence[OpenRouterMessage]) -> int:
        if not messages:
            raise OpenRouterContextLimitError("At least one message is required.")
        return ceil(sum(len(message.content.encode("utf-8")) for message in messages) / 3)

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    def _record_failure(
        self,
        correlation_id: UUID,
        conversation_id: UUID | None,
        started_at: float,
        error: type[OpenRouterError],
    ) -> None:
        self._record(
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            latency_ms=self._elapsed_ms(started_at),
            usage=ProviderUsage(None, None, None, None),
            provider_model=None,
            outcome="error",
            error_class=error.error_class,
        )

    def _record(
        self,
        *,
        correlation_id: UUID,
        conversation_id: UUID | None,
        latency_ms: int,
        usage: ProviderUsage,
        provider_model: str | None,
        outcome: str,
        error_class: str | None,
    ) -> None:
        if self._session is None:
            return
        self._session.add(
            AiUsageRecord(
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                selected_model=self._model,
                provider_model=provider_model,
                latency_ms=latency_ms,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
                outcome=outcome,
                error_class=error_class,
            )
        )
