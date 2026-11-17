"""Cookie-authenticated anonymous guest session endpoints."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error_responses
from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.sessions import GuestSessionPublic, SessionBootstrapResponse
from app.services.sessions import GuestContext, InvalidGuestSession, SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])

# This dependency documents the opaque guest cookie in OpenAPI.  The session
# service remains the authority for validating its value and expiry.
guest_session_cookie = APIKeyCookie(
    name="bmh_guest", scheme_name="GuestSessionCookie", auto_error=False
)


def get_session_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> SessionService:
    return SessionService(session, settings)


async def require_same_origin(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Require one configured Origin before a browser session cookie is created or renewed."""
    origins = request.headers.getlist("origin")
    if len(origins) != 1 or origins[0] not in settings.quotation_trusted_origins:
        raise HTTPException(status_code=403, detail="Cross-origin request is not allowed.")


async def require_quotation_origin(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Require one configured browser Origin for unsafe quotation mutations."""
    origins = request.headers.getlist("origin")
    if len(origins) != 1:
        raise HTTPException(status_code=403, detail="A valid Origin header is required.")
    origin = origins[0]
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or origin not in settings.quotation_trusted_origins
    ):
        raise HTTPException(status_code=403, detail="Cross-origin request is not allowed.")


async def get_guest_context(
    request: Request,
    _: Annotated[str | None, Depends(guest_session_cookie)],
    service: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GuestContext:
    try:
        context = await service.require_context(
            raw_token=request.cookies.get(settings.guest_session_cookie_name)
        )
        # Authentication is a read-only lookup. Release its implicit transaction so a
        # protected aggregate service can own the following mutation transaction.
        await session.rollback()
        return context
    except InvalidGuestSession:
        raise HTTPException(
            status_code=401,
            detail={"code": "SESSION_NOT_FOUND", "message": "Guest session is missing or invalid."},
        ) from None


@router.post(
    "",
    response_model=SessionBootstrapResponse,
    responses={
        201: {"model": SessionBootstrapResponse, "description": "A new guest session was created."},
        **api_error_responses(403),
    },
)
async def bootstrap_session(
    request: Request,
    response: Response,
    _: Annotated[None, Depends(require_same_origin)],
    service: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionBootstrapResponse:
    bootstrap = await service.bootstrap(
        raw_token=request.cookies.get(settings.guest_session_cookie_name)
    )
    response.status_code = status.HTTP_201_CREATED if bootstrap.created else status.HTTP_200_OK
    response.set_cookie(
        key=settings.guest_session_cookie_name,
        value=bootstrap.raw_token,
        max_age=settings.guest_session_inactivity_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.guest_session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return SessionBootstrapResponse(
        conversation_id=bootstrap.context.conversation_id,
        expires_at=bootstrap.expires_at,
        welcome_message=bootstrap.welcome_message,
        restored=not bootstrap.created,
    )


@router.get("/current", response_model=GuestSessionPublic, responses=api_error_responses(401))
async def get_current_session(
    guest: Annotated[GuestContext, Depends(get_guest_context)],
) -> GuestSessionPublic:
    return GuestSessionPublic(conversation_id=guest.conversation_id, expires_at=guest.expires_at)
