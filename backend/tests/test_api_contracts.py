"""Regression coverage for public API envelopes and generated OpenAPI contracts."""

from __future__ import annotations

import httpx
import pytest

from app.core.errors import ApiErrorCode
from app.main import app


def test_openapi_documents_public_errors_and_discriminated_conversation_elements() -> None:
    schema = app.openapi()

    error_response = schema["components"]["schemas"]["ApiErrorResponse"]
    assert error_response["properties"]["error"] == {"$ref": "#/components/schemas/ApiError"}
    assert error_response["required"] == ["error"]
    error = schema["components"]["schemas"]["ApiError"]
    assert set(error["properties"]["code"]["enum"]) == set(ApiErrorCode.__args__)
    assert set(error["required"]) == {"code", "message", "request_id"}
    elements = schema["components"]["schemas"]["ConversationMessagePublic"]["properties"][
        "elements"
    ]["items"]
    assert elements["discriminator"]["propertyName"] == "kind"
    assert "/api/v1/support/inquiries" in schema["paths"]
    for path in ("/api/v1/quotations/submissions", "/api/v1/support/inquiries"):
        assert {"200", "201", "401", "403", "409"} <= set(
            schema["paths"][path]["post"]["responses"]
        )
        assert schema["paths"][path]["post"]["security"] == [{"GuestSessionCookie": []}]
    assert {"200", "201", "403"} <= set(schema["paths"]["/api/v1/sessions"]["post"]["responses"])
    assert schema["paths"]["/api/v1/products/availability"]["post"]["responses"].keys() == {
        "200",
        "404",
        "422",
    }
    assert schema["components"]["securitySchemes"]["GuestSessionCookie"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "bmh_guest",
    }


@pytest.mark.asyncio
async def test_public_errors_have_stable_codes_for_missing_credentials_and_origin() -> None:
    transport = httpx.ASGITransport(app=app)
    request_id = "91b224f2-0f93-4fab-8e70-ee3bdff648ed"
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Request-ID": request_id}
    ) as client:
        missing = await client.get("/api/v1/sessions/current")
        malformed = await client.get("/api/v1/sessions/current", cookies={"bmh_guest": "bad"})
        missing_origin = await client.post("/api/v1/sessions")
        cross_origin = await client.post(
            "/api/v1/sessions", headers={"Origin": "https://untrusted.example"}
        )

    assert missing.status_code == malformed.status_code == 401
    assert missing.json()["error"] == {
        "code": "SESSION_NOT_FOUND",
        "message": "Guest session is missing or invalid.",
        "request_id": request_id,
        "retryable": False,
        "details": None,
    }
    assert missing.headers["x-request-id"] == request_id
    assert malformed.json() == missing.json()
    assert missing_origin.status_code == cross_origin.status_code == 403
    assert missing_origin.json()["error"]["code"] == "VALIDATION_FAILED"
    assert cross_origin.json() == missing_origin.json()
