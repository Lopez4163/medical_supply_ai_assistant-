"""Cookie-authenticated anonymous guest session endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.sessions import GuestSessionPublic, SessionBootstrapResponse
from app.services.sessions import GuestContext, InvalidGuestSession, SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> SessionService:
    return SessionService(session, settings)


async def require_same_origin(request: Request) -> None:
    """Reject cross-origin browser bootstraps; future cookie mutations reuse this boundary."""
    origin = request.headers.get("origin")
    if origin is not None and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(status_code=403, detail="Cross-origin request is not allowed.")


async def get_guest_context(
    request: Request,
    service: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GuestContext:
    try:
        return await service.require_context(
            raw_token=request.cookies.get(settings.guest_session_cookie_name)
        )
    except InvalidGuestSession:
        raise HTTPException(
            status_code=401, detail="Guest session is missing or invalid."
        ) from None


@router.post("", response_model=SessionBootstrapResponse)
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


@router.get("/current", response_model=GuestSessionPublic)
async def get_current_session(
    guest: Annotated[GuestContext, Depends(get_guest_context)],
) -> GuestSessionPublic:
    return GuestSessionPublic(conversation_id=guest.conversation_id, expires_at=guest.expires_at)
